
import sys
import unittest
import copy
import time
from hashlib import md5
try:
    import unittest.mock as compat_mock
except ImportError:
    import mock as compat_mock

from django.test import Client
from django.core.exceptions import ImproperlyConfigured
try:    # pragma: no cover
    from google.appengine.ext import testbed
except ImportError:
    sys.path.insert(1, 'gae_sdk/google_appengine')
    sys.path.insert(1, 'gae_sdk/google_appengine/lib/yaml/lib/')
    from google.appengine.ext import testbed

from django.conf import settings
from django import setup as django_setup

required_middleware = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]

try:
    from gae_django_ratelimiter import RateLimiterMiddleware
    from gae_django_ratelimiter.ratelimiter import RateLimiter
    from middleware import TestRateLimiterMiddleware
except ImproperlyConfigured:
    settings.configure()
    settings.ALLOWED_HOSTS = ['testserver']
    settings.ROOT_URLCONF = 'urls'
    settings.MIDDLEWARE_CLASSES = required_middleware
    settings.INSTALLED_APPS = [
        'django.contrib.sessions',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'tests',
    ]
    from gae_django_ratelimiter import RateLimiterMiddleware
    from gae_django_ratelimiter.ratelimiter import RateLimiter
    from middleware import TestRateLimiterMiddleware

django_setup()


class RateLimiterTests(unittest.TestCase):

    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_memcache_stub()
        self.testbed.init_app_identity_stub()

        settings.MIDDLEWARE_CLASSES = (
            required_middleware + ['middleware.TestRateLimiterMiddleware'])

        self.request = compat_mock.Mock()
        self.request.META = {
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_USER_AGENT': 'Mozilla/5.0 RATELIMITER',
        }
        self.request.url_name = 'random'

    def tearDown(self):
        self.testbed.deactivate()

    def test_basic(self):
        req = copy.deepcopy(self.request)

        test_requests = 9
        test_minutes = 1
        test_prefix = 'xyz'
        rl = RateLimiter(
            requests=test_requests, minutes=test_minutes, prefix=test_prefix)

        self.assertEqual(test_requests, rl.requests)
        self.assertEqual(test_minutes, rl.minutes)
        self.assertEqual(test_prefix, rl.prefix)

        self.assertEquals(req.META['REMOTE_ADDR'], rl.ip(req))
        req.META['HTTP_X_FORWARDED_FOR'] = '::1'
        self.assertEquals(req.META['HTTP_X_FORWARDED_FOR'], rl.ip(req))

        m = md5()
        m.update(req.META.get('HTTP_USER_AGENT', ''))
        self.assertEqual(
            '{}_{}_{}_{}'.format('xyz', rl.ip(req), m.hexdigest(), rl.minutes),
            rl.current_key(req))

    def test_disabled(self):
        from middleware import DisabledRateLimiterMiddleware
        settings.MIDDLEWARE_CLASSES = (
            required_middleware + ['middleware.DisabledRateLimiterMiddleware'])

        c = Client()
        res = c.get('/random')
        self.assertEqual(200, res.status_code)
        self.assertIsNone(
            res.get('X-Rate-Limit-Remaining-{}'.format(
                DisabledRateLimiterMiddleware.minutes)))

    def test_gae_internal(self):
        c = Client()

        gae_ip = '0.1.0.1'
        res = c.get('/random', **{'REMOTE_ADDR': gae_ip})
        self.assertEqual(200, res.status_code)
        self.assertIsNone(
            res.get('X-Rate-Limit-Remaining-{}'.format(
                TestRateLimiterMiddleware.requests)))

        res = c.get('/random', **{'X-Appengine-Cron': 'true'})
        self.assertEqual(200, res.status_code)
        self.assertIsNone(
            res.get('X-Rate-Limit-Remaining-{}'.format(
                TestRateLimiterMiddleware.requests)))

        res = c.get(
            '/random',
            **{'REMOTE_ADDR': '192.168.0.1', 'HTTP_X_FORWARDED_FOR': gae_ip})
        self.assertEqual(200, res.status_code)
        self.assertIsNotNone(
            res.get('X-Rate-Limit-Remaining-{}'.format(
                TestRateLimiterMiddleware.minutes)))

    def test_xforwardedfor(self):
        req = copy.deepcopy(self.request)
        req.META['HTTP_X_FORWARDED_FOR'] = '::1'
        rl = RateLimiter()
        self.assertEquals(req.META['HTTP_X_FORWARDED_FOR'], rl.ip(req))

        # bogon IP
        req.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1'
        self.assertEquals(req.META['REMOTE_ADDR'], rl.ip(req))

    def test_cooldownfromlastreq(self):

        from middleware import CooldownRateLimiterMiddleware
        settings.MIDDLEWARE_CLASSES = (
            required_middleware + ['middleware.CooldownRateLimiterMiddleware'])

        c = Client()
        window_time = CooldownRateLimiterMiddleware.minutes * 60

        for i in range(CooldownRateLimiterMiddleware.requests):
            res = c.get('/random')
            self.assertEqual(200, res.status_code)
            time.sleep(window_time // CooldownRateLimiterMiddleware.requests)

        res = c.get('/random')
        self.assertEqual(429, res.status_code)
        # wait till cache expires
        time.sleep(CooldownRateLimiterMiddleware.cooldown_minutes * 60)
        res = c.get('/random')
        self.assertEqual(200, res.status_code)

    def test_include_url_names(self):
        settings.MIDDLEWARE_CLASSES = (
            required_middleware + ['middleware.IncludeRateLimiterMiddleware'])
        c = Client()
        res_include = c.get('/random')
        res_exclude = c.get('/notrandom')
        self.assertIsNotNone(
            res_include.get('X-Rate-Limit-Remaining-{}'.format(
                RateLimiterMiddleware.minutes)))
        self.assertIsNone(
            res_exclude.get('X-Rate-Limit-Remaining-{}'.format(
                RateLimiterMiddleware.minutes)))

    def test_exclude_url_names(self):
        settings.MIDDLEWARE_CLASSES = (
            required_middleware + ['middleware.ExcludeRateLimiterMiddleware'])

        c = Client()
        res_include = c.get('/notrandom')
        res_exclude = c.get('/random')
        self.assertIsNotNone(
            res_include.get('X-Rate-Limit-Remaining-{}'.format(
                RateLimiterMiddleware.minutes)))
        self.assertIsNone(
            res_exclude.get('X-Rate-Limit-Remaining-{}'.format(
                RateLimiterMiddleware.minutes)))

    def _loginUser(self, email='user@example.com', id='123', is_admin=False):
        self.testbed.setup_env(
            user_email=email,
            user_id=id,
            user_is_admin='1' if is_admin else '0',
            overwrite=True)

    def test_admin_user(self):
        from middleware import (
            ExcludeAuthAdminRateLimiterMiddleware,
        )
        middlewares = [
            ExcludeAuthAdminRateLimiterMiddleware,
        ]

        for m in middlewares:
            settings.MIDDLEWARE_CLASSES = (
                required_middleware + ['{}.{}'.format(
                    m.__module__, m.__name__
                )])

            c = Client()
            res = c.get('/random')
            self.assertEqual(200, res.status_code)
            self.assertIsNotNone(
                res.get('X-Rate-Limit-Remaining-{}'.format(
                    m.minutes)), '{} failed'.format(m.__name__))

            self._loginUser(is_admin=True)
            res = c.get('/random')
            self.assertEqual(200, res.status_code)
            if m.exclude_admins:
                self.assertIsNone(
                    res.get('X-Rate-Limit-Remaining-{}'.format(
                        m.minutes)), '{} failed'.format(m.__name__))
            else:
                self.assertIsNotNone(
                    res.get('X-Rate-Limit-Remaining-{}'.format(
                        m.minutes)), '{} failed'.format(m.__name__))

    def test_authenticated_user(self):
        from middleware import (
            ExcludeAuthRateLimiterMiddleware,
            IncludeAuthRateLimiterMiddleware,
            ExcludeAuthAdminRateLimiterMiddleware,
        )
        middlewares = [
            ExcludeAuthRateLimiterMiddleware,
            IncludeAuthRateLimiterMiddleware,
            ExcludeAuthAdminRateLimiterMiddleware,
        ]

        for m in middlewares:
            settings.MIDDLEWARE_CLASSES = (
                required_middleware + ['{}.{}'.format(
                    m.__module__, m.__name__
                )])

            c = Client()
            res = c.get('/random')
            self.assertEqual(200, res.status_code)
            self.assertIsNotNone(
                res.get('X-Rate-Limit-Remaining-{}'.format(
                    m.minutes)), '{} failed'.format(m.__name__))

            self._loginUser()
            res = c.get('/random')
            self.assertEqual(200, res.status_code)
            if m.exclude_authenticated:
                self.assertIsNone(
                    res.get('X-Rate-Limit-Remaining-{}'.format(
                        m.minutes)), '{} failed'.format(m.__name__))
            else:
                self.assertIsNotNone(
                    res.get('X-Rate-Limit-Remaining-{}'.format(
                        m.minutes)), '{} failed'.format(m.__name__))


class RateLimiterMiddlewareTests(unittest.TestCase):

    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_memcache_stub()

    def tearDown(self):
        self.testbed.deactivate()

    def test_basic(self):
        settings.MIDDLEWARE_CLASSES = (
            required_middleware + ['middleware.TestRateLimiterMiddleware'])

        c = Client()
        for i in range(1, TestRateLimiterMiddleware.requests + 2):
            res = c.get('/random')
            if i <= TestRateLimiterMiddleware.requests:
                self.assertEqual(
                    TestRateLimiterMiddleware.requests - i,
                    int(res.get('X-Rate-Limit-Remaining-{}'.format(
                        TestRateLimiterMiddleware.minutes), '-1')))
            else:
                self.assertIsNone(
                    res.get('X-Rate-Limit-Remaining-{}'.format(
                        TestRateLimiterMiddleware.requests)))

    def test_django1_10(self):
        settings.MIDDLEWARE_CLASSES = (
            required_middleware + ['middleware.TestRateLimiterMiddleware'])

        c = Client()
        res = c.get('/random')
        self.assertEqual(
            TestRateLimiterMiddleware.requests - 1,
            int(res.get('X-Rate-Limit-Remaining-{}'.format(
                TestRateLimiterMiddleware.minutes))))


class RateLimitDecoratorTests(unittest.TestCase):

    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_memcache_stub()

    def tearDown(self):
        self.testbed.deactivate()

    def test_basic(self):
        # settings.MIDDLEWARE_CLASSES = required_middleware

        requests_limit = 5
        minutes = 1
        c = Client()
        for i in range(1, requests_limit + 2):
            res = c.get('/decorated')

            if i <= requests_limit:
                self.assertEqual(
                    requests_limit - i,
                    int(res.get('X-Rate-Limit-Remaining-{}'.format(
                        minutes), '-1'))
                )
            else:
                self.assertIsNone(
                    res.get('X-Rate-Limit-Remaining-{}'.format(minutes)))
