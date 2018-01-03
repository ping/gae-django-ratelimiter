# gae-django-ratelimiter

A basic Django request rate limiter (X requests per Y minutes) for use on Google App Engine (GAE).

Just Good Enough™ for weekend projects.

## Features

1. Available as middleware ``gae_django_ratelimiter.RateLimiterMiddleware`` or request decorator ``@ratelimit``
1. Does not limit GAE tasks by default
1. Does not do much else

Compatible with Django versions >=1.4, <=1.11

## Usage

### Basic

1. Add the ``gae_django_ratelimiter`` folder to your project path

1. Use either the decorator for individual views OR include it in your ``INSTALLED_APPS`` and ``MIDDLEWARE_CLASSES`` (Django<=1.9) or ``MIDDLEWARE`` (Django>=1.10) in your app's  ``settings.py`` to apply it globally.

```python
# views.py
from gae_django_ratelimiter import ratelimit

@ratelimit(requests=30, minutes=2)
def a_view(request):
    # ...
```

```python
# settings.py

# Custom Configuration
GAE_DJANGO_RATELIMITER_ENABLED = True
GAE_DJANGO_RATELIMITER_CACHE_PREFIX = 'lolcat'
GAE_DJANGO_RATELIMITER_CACHE_MINUTES = 2
GAE_DJANGO_RATELIMITER_CACHE_REQUESTS = 30

# For Django <= 1.9. For newer versions set MIDDLEWARE instead
# Take care to insert it after SessionMiddleware and AuthenticationMiddleware
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # ...
    'gae_django_ratelimiter.RateLimiterMiddleware',
    # ...
)

# ...

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    # ...
    'gae_django_ratelimiter',
    # ...
)
```

### Settings

- ``GAE_DJANGO_RATELIMITER_ENABLED``
  - Enables rate limiting. Default ``True``.
- ``GAE_DJANGO_RATELIMITER_CACHE_PREFIX``
  - Memcache key prefix. Default ``gaerl``.
- ``GAE_DJANGO_RATELIMITER_CACHE_MINUTES``
  - Interval in minutes. Default ``2``.
- ``GAE_DJANGO_RATELIMITER_CACHE_REQUESTS``
  - Requests per interval. Default ``20``.
- ``GAE_DJANGO_RATELIMITER_COOLDOWN_LAST_REQ``
  - The backoff interval starts from the more recent request after throttling has kicked in. Default ``False``.
- ``GAE_DJANGO_RATELIMITER_COOLDOWN_MINUTES``
  - The backoff interval in minutes if ``GAE_DJANGO_RATELIMITER_COOLDOWN_LAST_REQ`` is True. Equal to ``GAE_DJANGO_RATELIMITER_CACHE_MINUTES`` by default.
- ``GAE_DJANGO_RATELIMITER_INCLUDE_URL_NAMES``
  - List of url names to include. If defined, any url names not in list will be excluded. Default ``[]``.
- ``GAE_DJANGO_RATELIMITER_EXCLUDE_URL_NAMES``
  - List of url names to exclude. If defined, any url names not in list will be included. Default ``[]``.
- ``GAE_DJANGO_RATELIMITER_EXCLUDE_AUTHENTICATED``
  - Exclude authenticated users from limiting. Default ``True``.
- ``GAE_DJANGO_RATELIMITER_EXCLUDE_ADMINS``
  - Exclude admin users from limiting. Default ``True``.


### Advance

You can subclass the decorator or middleware for your own custom logic.
If using your own middleware, remember to add your own middleware class instead.

#### Example: Rate limit a crawler bot without affecting other users

```python
# myratelimiter.py
import re
import logging
from gae_django_ratelimiter import ratelimit, RateLimiterMiddleware


OFFENDING_UA_RE = re.compile(r'^BadBot')

# Use either a Decorator or Middleware

# Decorator
class myratelimit(ratelimit):

    def should_ratelimit(self, request):
        if not super(myratelimit, self).should_ratelimit(request):
            return False

        ua = request.META.get('HTTP_USER_AGENT', '')
        return OFFENDING_UA_RE.search(ua)

    def disallowed(self, request):
        logging.warn('Too many requests from {}'.format(
            request.META.get('REMOTE_ADDR', ''),
        )
        return super(myratelimit, self).disallowed(request)


# Middleware
class MyRateLimiterMiddleware(RateLimiterMiddleware):

    def should_ratelimit(self, request):
        if not super(MyRateLimiterMiddleware, self).should_ratelimit(request):
            return False

        ua = request.META.get('HTTP_USER_AGENT', '')
        return OFFENDING_UA_RE.search(ua)
```
