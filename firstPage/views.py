from django import forms
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import redirect, render # pyright: ignore[reportMissingModuleSource]
from django.views.decorators.http import require_POST

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")


def account(request):
    if request.user.is_authenticated:
        return redirect("home")

    login_form = AuthenticationForm(request=request)
    registration_form = RegistrationForm()

    if request.method == "POST":
        if request.POST.get("form_type") == "register":
            registration_form = RegistrationForm(request.POST)
            if registration_form.is_valid():
                user = registration_form.save()
                login(request, user)
                return redirect("home")
        else:
            login_form = AuthenticationForm(request=request, data=request.POST)
            if login_form.is_valid():
                login(request, login_form.get_user())
                return redirect("home")

    return render(request, "main/account.html", {
        "login_form": login_form,
        "registration_form": registration_form,
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect("account")


@login_required(login_url="account")
def home(request):
    return render(request, 'main/home.html')


import json

from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Vote


@csrf_exempt
def receive_google_vote(request):

    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required"},
            status=405
        )

    try:
        data = json.loads(request.body)

        email = data.get("email")
        candidate = data.get("candidate")

        if not email or not candidate:
            return JsonResponse(
                {"error": "Email and candidate are required"},
                status=400
            )

        vote = Vote.objects.create(
            email=email,
            candidate=candidate
        )

    except IntegrityError:
        return JsonResponse(
            {"error": "This email has already voted"},
            status=409
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid JSON"},
            status=400
        )

    # Get current results
    voters = {}

    votes = Vote.objects.values("candidate")

    for vote_data in votes:
        candidate_name = vote_data["candidate"]

        voters[candidate_name] = (
            voters.get(candidate_name, 0) + 1
        )

    # Broadcast to WebSocket clients
    channel_layer = get_channel_layer()

    assert channel_layer is not None
    async_to_sync(channel_layer.group_send)(
        "vote_results",
        {
            "type": "vote_update",
            "votes": voters
        }
    )
    print(voters)

    return JsonResponse({
        "message": "Vote recorded",
        "vote_id": vote.id,
        "results": voters
    })