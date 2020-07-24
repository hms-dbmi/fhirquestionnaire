from django.conf.urls import url

from questionnaire import views

app_name = "questionnaire"

# Add views.
urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^p/(?P<project_id>.+)/$', views.ProjectView.as_view(), name='project'),
    url(r'^q/asd/$', views.ASDView.as_view(), name='asd'),
    url(r'^q/neer/$', views.NEERView.as_view(), name='neer'),
    url(r'^q/rant/$', views.RANTView.as_view(), name='rant'),
]
