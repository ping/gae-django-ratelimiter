from django.http import HttpResponse
from gae_django_ratelimiter import ratelimit


def random(request):
    return HttpResponse('random')


def notrandom(request):
    return HttpResponse('notrandom')


@ratelimit(prefix='gaerl', minutes=1, requests=5)
def decorated(request):
    return HttpResponse('notrandom')
