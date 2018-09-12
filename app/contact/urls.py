from django.conf.urls import url

from contact import views

app_name = "contact"

# Add views.
urlpatterns = [
    url(r'^$', views.ContactView.as_view(), name='contact'),
]
