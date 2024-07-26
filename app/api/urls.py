from django.urls import re_path

from api.apps import ApiConfig
from api import views

# Set the app name
app_name = ApiConfig.name

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    re_path(r'^consent/(?P<study>[\w\d-]+)/(?P<ppm_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[\d]+)/?$', views.ConsentView.as_view(), name='consent'),
    re_path(r'^consent/(?P<study>[\w\d-]+)/?$', views.ConsentsView.as_view(), name='consents'),
    re_path(r'^questionnaire/?$', views.QuestionnaireView.as_view(), name='questionnaire'),
    re_path(r'^questionnaire/(?P<questionnaire_id>[\w\d-]+)/?$', views.QuestionnaireView.as_view(), name='questionnaire'),
]
