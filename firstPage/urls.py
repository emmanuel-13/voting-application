from django.urls import path
from .views import *

urlpatterns = [
    path('account/', account, name="account"),
    path('logout/', logout_view, name="logout"),
    path('', home, name="home"),
    path(
        "google/",
        receive_google_vote,
        name="google_vote"
    ),
]