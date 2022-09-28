from django.urls import re_path

from contact import views

app_name = "contact"

# Add views.
urlpatterns = [
    re_path(r'^$', views.ContactView.as_view(), name='contact'),
]
