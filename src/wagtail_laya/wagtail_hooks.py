from django.urls import include, path
from wagtail import hooks


@hooks.register("register_admin_urls")
def register_admin_urls():
    return [path("laya/", include("wagtail_laya.urls", namespace="wagtail_laya"))]
