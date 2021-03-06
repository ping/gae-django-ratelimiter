from django.conf import settings

RATELIMITER_ENABLED = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_ENABLED', True)
RATELIMITER_CACHE_PREFIX = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_CACHE_PREFIX', 'gaerl')

RATELIMITER_CACHE_MINUTES = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_CACHE_MINUTES', 2)
RATELIMITER_CACHE_REQUESTS = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_CACHE_REQUESTS', 20)

RATELIMITER_COOLDOWN_LAST_REQ = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_COOLDOWN_LAST_REQ', False)

RATELIMITER_COOLDOWN_MINUTES = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_COOLDOWN_MINUTES',
    RATELIMITER_CACHE_MINUTES)

# Expects a list of url names (urlconf)
RATELIMITER_INCLUDE_URL_NAMES = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_INCLUDE_URL_NAMES', [])
# Expects a list of url names (urlconf)
RATELIMITER_EXCLUDE_URL_NAMES = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_EXCLUDE_URL_NAMES', [])

RATELIMITER_EXCLUDE_AUTHENTICATED = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_EXCLUDE_AUTHENTICATED', True)

RATELIMITER_EXCLUDE_ADMINS = getattr(
    settings, 'GAE_DJANGO_RATELIMITER_EXCLUDE_ADMINS', True)
