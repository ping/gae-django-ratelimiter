
import logging
import functools
from hashlib import md5
import re
from django.http import HttpResponse
from django.core.urlresolvers import resolve
from google.appengine.api import memcache, users

from .settings import (
    RATELIMITER_ENABLED, RATELIMITER_CACHE_PREFIX,
    RATELIMITER_CACHE_MINUTES, RATELIMITER_CACHE_REQUESTS,
    RATELIMITER_COOLDOWN_LAST_REQ, RATELIMITER_COOLDOWN_MINUTES,
    RATELIMITER_INCLUDE_URL_NAMES, RATELIMITER_EXCLUDE_URL_NAMES,
    RATELIMITER_EXCLUDE_AUTHENTICATED, RATELIMITER_EXCLUDE_ADMINS,
)

logger = logging.getLogger(__name__)


class HttpResponseThrottled(HttpResponse):
    status_code = 429
    reason_phrase = 'Too Many Requests'

    def __init__(self, content=b'', *args, **kwargs):
        super(HttpResponseThrottled, self).__init__(
            content,
            content_type='text/plain; charset=utf-8',
            *args, **kwargs)
        if not content:
            self.content = '{} {}\nPlease try again later.'.format(
                self.status_code, self.reason_phrase
            )


class RateLimiter(object):
    """Encapsulates the main logic for rate limiting"""

    enabled = RATELIMITER_ENABLED
    # The time interval
    minutes = RATELIMITER_CACHE_MINUTES
    # Number of allowed requests in that interval
    requests = RATELIMITER_CACHE_REQUESTS
    # Prefix for memcache key
    prefix = RATELIMITER_CACHE_PREFIX
    # if True, throttling cool down starts after the last req
    cooldown_from_last_request = RATELIMITER_COOLDOWN_LAST_REQ
    # Cooldown interval in minutes if cooldown_from_last_request is True
    cooldown_minutes = RATELIMITER_COOLDOWN_MINUTES
    # if False, rate limits also include authenticated users (django/google)
    exclude_authenticated = RATELIMITER_EXCLUDE_AUTHENTICATED
    # if False, rate limits also include authenticated users (django/google)
    exclude_admins = RATELIMITER_EXCLUDE_ADMINS

    # Is mutually exclusive with RateLimiter.exclude_url_names.
    # When defined, all urlnames not in include_url_names
    # will be excluded.
    include_url_names = RATELIMITER_INCLUDE_URL_NAMES

    # Is mutually exclusive with RateLimiter.include_url_names.
    # When defined, all urlnames not in include_url_names
    # will be included.
    exclude_url_names = RATELIMITER_EXCLUDE_URL_NAMES

    # GAE internal IP addresses
    # https://cloud.google.com/appengine/docs/standard/python/config/cronref#originating_ip_address
    # https://cloud.google.com/appengine/docs/standard/python/taskqueue/push/creating-handlers#writing_a_push_task_request_handler
    gae_internal_ips = ('0.1.0.1', '0.1.0.2')

    # Basic bogon ip ranges
    bogon_ip_re = re.compile(
        r'10\.|127\.|169\.254\.|192\.0\.0\.|192\.168\.|'
        '172\.1[6-9]\.|172\.2[0-9]\.|172\.3[0-1]\.')

    def __init__(self, **options):
        for key, value in options.items():
            setattr(self, key, value)

    def _is_bogon_ip(self, ip):
        if self.bogon_ip_re.match(ip):
            return True
        return False

    def ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            x_forwarded_for_ip = x_forwarded_for.split(',')[-1].strip()
            if not (x_forwarded_for_ip in self.gae_internal_ips
                    or self._is_bogon_ip(x_forwarded_for_ip)):
                return x_forwarded_for_ip
        return request.META.get('REMOTE_ADDR', '')

    def should_ratelimit(self, request):
        if not self.enabled:
            return False

        # Skip cron tasks
        # https://cloud.google.com/appengine/docs/standard/python/config/cronref#cron_requests
        # Safe to use as is because this is protected by GAE
        if request.META.get('X-Appengine-Cron', '') == 'true':
            return False

        # Skip GAE internal IP addresses
        if self.ip(request) in self.gae_internal_ips:
            return False

        if self.exclude_admins:
            try:
                # Django admin
                if request.user.is_authenticated and (
                        request.user.is_staff or request.user.is_superuser):
                    return False
                # GAE admin
                if users.get_current_user() and users.is_current_user_admin():
                    return False
            except AttributeError as ae:
                logger.warning(ae.message)

        try:
            if self.exclude_authenticated and (
                    request.user.is_authenticated() or
                    users.get_current_user()):
                return False
        except AttributeError as ae:
            logger.warning(ae.message)

        if self.exclude_url_names:
            for url_name in self.exclude_url_names:
                if url_name == resolve(request.path_info).url_name:
                    return False
            return True

        if self.include_url_names:
            for url_name in self.include_url_names:
                if url_name == resolve(request.path_info).url_name:
                    return True
            return False
        return True

    def disallowed(self, request):
        """Override this method if you want to log incidents"""
        return HttpResponseThrottled()

    def current_key(self, request):
        """Override this to use a different cache key"""
        # Google's memcache key len is max 250 bytes
        # https://cloud.google.com/appengine/docs/standard/python/memcache/
        m = md5()
        # Use a basic hash of the UA
        m.update(request.META.get('HTTP_USER_AGENT', ''))
        return '{}_{}_{}_{}'.format(
            self.prefix,
            self.ip(request),
            m.hexdigest(),
            self.minutes,
        )

    def expire_after(self):
        """Used for setting the memcache expiry"""
        return (self.minutes) * 60

    def cached_count(self, key):
        return memcache.get(key, 0) or 0

    def cache_incr(self, key):
        # add first, to ensure the key exists
        added = memcache.add(key, 0, time=self.expire_after())
        if not added and self.cooldown_from_last_request:
            # already exists so we extend the memcache expiry
            # by another interval
            memcache.set(
                key, self.cached_count(key), time=self.cooldown_minutes * 60)
        memcache.incr(key)

    def check(self, request):
        if not self.should_ratelimit(request):
            return None, 0

        # Increment rate limiting counter
        self.cache_incr(self.current_key(request))
        cached_count = self.cached_count(self.current_key(request))

        if cached_count > self.requests:
            return self.disallowed(request), cached_count

        return None, cached_count


# Middleware
class RateLimiterMiddleware(RateLimiter):

    def __init__(self, get_response=None, **options):
        self.get_response = get_response
        super(RateLimiterMiddleware, self).__init__(**options)

    # For Django>=1.10
    # https://docs.djangoproject.com/en/1.11/topics/http/middleware/#upgrading-pre-django-1-10-style-middleware
    def __call__(self, request):
        response = self.process_request(request)
        if not response:
            response = self.get_response(request)
        response = self.process_response(request, response)
        return response

    def process_request(self, request):
        res, _ = self.check(request)
        return res

    def process_response(self, request, response):
        if response.status_code < 400 and self.should_ratelimit(request):
            response['X-Rate-Limit-Remaining-{}'.format(self.minutes)] = (
                self.requests - self.cached_count(self.current_key(request)))
        return response


# Decorator
# Modified from
# https://github.com/simonw/ratelimitcache/blob/master/ratelimitcache.py
class ratelimit(RateLimiter):

    def __call__(self, fn):
        def wrapper(request, *args, **kwargs):
            return self.view_wrapper(request, fn, *args, **kwargs)
        functools.update_wrapper(wrapper, fn)
        return wrapper

    def view_wrapper(self, request, fn, *args, **kwargs):
        res, cached_count = self.check(request)
        if res:
            return res

        res = fn(request, *args, **kwargs)
        if cached_count:
            res['X-Rate-Limit-Remaining-{}'.format(self.minutes)] = (
                self.requests - cached_count)
        return res
