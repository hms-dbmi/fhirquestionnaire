from django.conf.urls import url

from consent import views

app_name = "consent"

# Add views.
urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^p/(?P<project_id>.+)/$', views.ProjectView.as_view(), name='project'),
    url(r'^q/(?P<questionnaire_id>.+)/$', views.ConsentView.as_view(), name='consent'),
]
