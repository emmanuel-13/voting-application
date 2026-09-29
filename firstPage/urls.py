from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name="home"),
    path(
        "google/",
        receive_google_vote,
        name="google_vote"
    ),
]