from django import forms
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Count
from django.core.paginator import Paginator
from django.shortcuts import redirect, render # pyright: ignore[reportMissingModuleSource]
from django.views.decorators.http import require_POST
from .models import Vote


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
                messages.success(request, "Your account is ready. You are now signed in.")
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


def home(request):
    is_admin = request.user.is_authenticated and (
        request.user.is_staff or request.user.is_superuser
    )
    vote_totals = {
        row["candidate"]: row["total"]
        for row in Vote.objects.values("candidate").annotate(total=Count("id"))
    }
    recent_votes = None
    if is_admin:
        recent_votes = Paginator(
            Vote.objects.order_by("-date_created"),
            50,
        ).get_page(request.GET.get("page"))
    return render(request, 'main/home.html', {
        "vote_totals": vote_totals,
        "recent_votes": recent_votes,
        "is_admin": is_admin,
    })


import json

from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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
                "votes": voters,
                "vote": {
                    "email": vote.email,
                    "candidate": vote.candidate,
                    "date_created": vote.date_created.isoformat(),
                },
        }
    )
    print(voters)

    return JsonResponse({
        "message": "Vote recorded",
        "vote_id": vote.pk,
        "results": voters
    })
