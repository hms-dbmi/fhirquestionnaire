from django.conf.urls import url

from consent import views

app_name = "consent"

# Add views.
urlpatterns = [
    url(r'^p/(?P<study>[a-z\-_]+)/$', views.StudyView.as_view(), name='study'),
    url(r'^d/(?P<study>[a-z\-_]+)/$', views.DownloadView.as_view(), name='download'),

    # Autism has its own views due to its 'involved' consent format
    url(r'^c/autism/$', views.AutismView.as_view(), name='autism'),
    url(r'^c/autism/quiz/$', views.AutismQuizView.as_view(), name='autism-quiz'),
    url(r'^c/autism/signature/$', views.AutismSignatureView.as_view(), name='autism-signature'),
    url(r'^c/(?P<study>[a-z\-_]+)/$', views.ConsentView.as_view(), name='consent'),
    url(r'^$', views.IndexView.as_view(), name='index'),
]
