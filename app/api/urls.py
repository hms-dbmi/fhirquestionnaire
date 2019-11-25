from django.urls import include, re_path
from rest_framework import routers

from api.apps import ApiConfig
from api import views

# Set the app name
app_name = ApiConfig.name

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    re_path(r'^consent/(?P<study>[\w\d-]+)/(?P<ppm_id>[\d]+)/?$', views.ConsentView.as_view(), name='consent'),
    re_path(r'^consent/(?P<study>[\w\d-]+)/?$', views.ConsentsView.as_view(), name='consents'),
]
