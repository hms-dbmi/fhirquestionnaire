from django.urls import include, re_path
from rest_framework import routers

from api.apps import ApiConfig
from api import views

# Set the app name
app_name = ApiConfig.name

# Wire up our API using automatic URL routing.
urlpatterns = [
    re_path(r'^consent/(?P<study>[\w\d-]+)/(?P<ppm_id>[\d]+)/?$', views.ConsentView.as_view(), name='consent'),
    re_path(r'^consent/(?P<study>[\w\d-]+)/?$', views.ConsentsView.as_view(), name='consents'),
    re_path(r'^questionnaire/?$', views.QuestionnaireView.as_view(), name='questionnaire'),
    re_path(r'^questionnaire/(?P<questionnaire_id>[\w\d-]+)/?$', views.QuestionnaireView.as_view(), name='questionnaire'),
]
