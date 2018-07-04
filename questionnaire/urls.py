from django.conf.urls import url

from questionnaire import views

app_name = "questionnaire"

# Add views.
urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='index'),
    url(r'^(?P<questionnaire_id>.+)/$', views.QuestionnaireView.as_view(), name='questionnaire'),
]
