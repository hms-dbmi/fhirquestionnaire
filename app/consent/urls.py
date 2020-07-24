from django.conf.urls import url

from consent import views

app_name = "consent"

# Add views.
urlpatterns = [
    url(r'^p/(?P<project_id>.+)/$', views.ProjectView.as_view(), name='project'),
    url(r'^d/(?P<study>.+)/$', views.DownloadView.as_view(), name='download'),
    url(r'^c/neer/$', views.NEERView.as_view(), name='neer'),
    url(r'^c/rant/$', views.RANTView.as_view(), name='rant'),
    url(r'^c/asd/$', views.ASDView.as_view(), name='asd'),
    url(r'^c/asd/quiz/$', views.ASDQuizView.as_view(), name='asd-quiz'),
    url(r'^c/asd/signature/$', views.ASDSignatureView.as_view(), name='asd-signature'),
    url(r'^$', views.IndexView.as_view(), name='index'),
]
