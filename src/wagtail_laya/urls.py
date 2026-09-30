from django.urls import path

from wagtail_laya import views

app_name = "wagtail_laya"

urlpatterns = [
    path("suggest/", views.suggest, name="suggest"),
    path("rate/", views.rate, name="rate"),
]
