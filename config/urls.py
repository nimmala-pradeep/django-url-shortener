from django.contrib import admin
from django.urls import include, path

handler404 = "shortener.views.not_found"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("shortener.urls")),
]
