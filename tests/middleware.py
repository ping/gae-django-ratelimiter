from gae_django_ratelimiter import RateLimiterMiddleware


class TestRateLimiterMiddleware(RateLimiterMiddleware):
    requests = 3
    minutes = 0.5
    prefix = 'xyz'


class DisabledRateLimiterMiddleware(RateLimiterMiddleware):
    enabled = False


class CooldownRateLimiterMiddleware(RateLimiterMiddleware):
    requests = 2
    minutes = 2.0/60
    cooldown_from_last_request = True
    cooldown_minutes = 0.1


class ExcludeRateLimiterMiddleware(RateLimiterMiddleware):
    exclude_url_names = ['random']


class IncludeRateLimiterMiddleware(RateLimiterMiddleware):
    include_url_names = ['random']


class ExcludeAuthRateLimiterMiddleware(RateLimiterMiddleware):
    exclude_authenticated = True
    exclude_admins = True


class IncludeAuthRateLimiterMiddleware(RateLimiterMiddleware):
    exclude_authenticated = False
    exclude_admins = False


class ExcludeAuthAdminRateLimiterMiddleware(RateLimiterMiddleware):
    exclude_authenticated = False
    exclude_admins = True
