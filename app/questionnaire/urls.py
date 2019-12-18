from django.conf.urls import url

from questionnaire import views

app_name = "questionnaire"

# Add views.
urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^p/(?P<study>[a-z\-_]+)/$', views.StudyView.as_view(), name='study'),
    url(r'^q/(?P<study>[a-z\-_]+)/$', views.QuestionnaireView.as_view(), name='questionnaire'),
]
