from django.urls import re_path

from questionnaire import views

app_name = "questionnaire"

# Add views.
urlpatterns = [
    re_path(r'^p/(?P<study>[a-z\-_]+)/$', views.StudyView.as_view(), name='study'),
    re_path(r'^q/(?P<study>[a-z\-_]+)/$', views.QuestionnaireView.as_view(), name='questionnaire'),
    re_path(r'^$', views.IndexView.as_view(), name='index'),
]
