from django.urls import re_path

from consent import views

app_name = "consent"

# Add views.
urlpatterns = [
    re_path(r'^p/(?P<study>[a-z\-_]+)/$', views.StudyView.as_view(), name='study'),
    re_path(r'^d/(?P<study>[a-z\-_]+)/$', views.DownloadView.as_view(), name='download'),
    re_path(r'^d/(?P<study>[a-z\-_]+)/(?P<ppm_id>[\d]+)/$', views.AdminDownloadView.as_view(), name='admin-download'),

    re_path(r'^c/asd/$', views.ASDView.as_view(), name='asd'),
    re_path(r'^c/asd/quiz/$', views.ASDQuizView.as_view(), name='asd-quiz'),
    re_path(r'^c/asd/signature/$', views.ASDSignatureView.as_view(), name='asd-signature'),
    re_path(r'^c/(?P<study>[a-z\-_]+)/$', views.ConsentView.as_view(), name='consent'),
    re_path(r'^$', views.IndexView.as_view(), name='index'),
]
