from django.conf.urls import url

from questionnaire import views

app_name = "questionnaire"

# Add views.
urlpatterns = [
    url(r'^p/(?P<study>[a-z\-_]+)/$', views.StudyView.as_view(), name='study'),
    url(r'^q/(?P<study>[a-z\-_]+)/$', views.QuestionnaireView.as_view(), name='questionnaire'),
    url(r'^q/(?P<study>[a-z\-_]+)/(?P<questionnaire_id>[a-z0-9\-_]+)/?$', views.QuestionnaireView.as_view(), name='questionnaire'),
    url(r'^$', views.IndexView.as_view(), name='index'),
]
