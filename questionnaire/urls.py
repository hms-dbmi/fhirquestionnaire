from django.conf.urls import url

from questionnaire import views

app_name = "questionnaire"

# Add views.
urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^p/(?P<project_id>.+)/$', views.ProjectView.as_view(), name='project'),
    url(r'^q/(?P<questionnaire_id>.+)/$', views.QuestionnaireView.as_view(), name='questionnaire'),
]
