from django.shortcuts import render # pyright: ignore[reportMissingModuleSource]

# Create your views here.
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