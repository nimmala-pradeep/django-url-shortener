from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/shorten", views.shorten, name="shorten"),
    path("api/stats/<str:code>", views.stats, name="stats"),
    path("<str:code>", views.follow, name="follow"),  # keep last
]
