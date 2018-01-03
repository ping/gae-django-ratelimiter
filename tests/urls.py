from django.conf.urls import url
import views

urlpatterns = [
    url(r'^random/?$', views.random, name='random'),
    url(r'^notrandom/?$', views.notrandom, name='notrandom'),
    url(r'^decorated/?$', views.decorated, name='decorated'),
]
