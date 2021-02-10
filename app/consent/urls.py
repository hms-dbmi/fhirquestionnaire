from django.conf.urls import url

from consent import views

app_name = "consent"

# Add views.
urlpatterns = [
    url(r'^p/(?P<study>[a-z\-_]+)/$', views.StudyView.as_view(), name='study'),
    url(r'^d/(?P<study>[a-z\-_]+)/$', views.DownloadView.as_view(), name='download'),

    url(r'^c/asd/$', views.ASDView.as_view(), name='asd'),
    url(r'^c/asd/quiz/$', views.ASDQuizView.as_view(), name='asd-quiz'),
    url(r'^c/asd/signature/$', views.ASDSignatureView.as_view(), name='asd-signature'),
    url(r'^c/(?P<study>[a-z\-_]+)/$', views.ConsentView.as_view(), name='consent'),
    url(r'^$', views.IndexView.as_view(), name='index'),
]
