
import json
from unittest.mock import AsyncMock

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .consumer import VoteConsumer2
from django.test import TestCase
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from .models import Vote


User = get_user_model()


class AccountFlowTests(TestCase):
	def test_dashboard_is_public(self):
		response = self.client.get("/")

		self.assertEqual(response.status_code, 200)

	def test_registration_activates_and_signs_in_user(self):
		response = self.client.post("/account/", {
			"form_type": "register",
			"username": "newvoter",
			"email": "voter@example.com",
			"password1": "A-secure-test-password-872!",
			"password2": "A-secure-test-password-872!",
		})

		self.assertRedirects(response, "/")
		user = User.objects.get(username="newvoter")
		self.assertTrue(user.is_active)
		self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

	def test_voter_details_are_visible_only_to_admins(self):
		Vote.objects.create(email="private-one@example.com", candidate="Candidate A")
		Vote.objects.create(email="private-two@example.com", candidate="Candidate A")
		Vote.objects.create(email="private-three@example.com", candidate="Candidate B")

		public_response = self.client.get("/")

		self.assertEqual(public_response.status_code, 200)
		self.assertEqual(public_response.context["vote_totals"], {"Candidate A": 2, "Candidate B": 1})
		self.assertIsNone(public_response.context["recent_votes"])
		self.assertNotContains(public_response, "private-one@example.com")
		self.assertNotContains(public_response, "private-two@example.com")

		admin = User.objects.create_superuser(
			username="reviewer",
			email="reviewer@example.com",
			password="Admin-test-password-872!",
		)
		self.client.force_login(admin)
		admin_response = self.client.get("/")
		self.assertEqual(len(admin_response.context["recent_votes"]), 3)
		self.assertContains(admin_response, "private-one@example.com")
		self.assertContains(admin_response, "private-two@example.com")

	def test_dashboard_paginates_older_vote_history(self):
		admin = User.objects.create_superuser(
			username="historyviewer",
			email="history@example.com",
			password="test-pass-872!",
		)
		self.client.force_login(admin)
		Vote.objects.bulk_create([
			Vote(email=f"archive-{index}@example.com", candidate="Candidate A")
			for index in range(51)
		])

		response = self.client.get("/?page=2")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["recent_votes"].number, 2)
		self.assertEqual(len(response.context["recent_votes"]), 1)
		self.assertContains(response, "Page 2 of 2")

	@override_settings(CHANNEL_LAYERS={
		"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
	})
	def test_google_vote_persists_and_broadcasts_updated_results(self):
		Vote.objects.create(email="existing@example.com", candidate="Candidate A")
		channel_layer = get_channel_layer()
		assert channel_layer is not None
		channel_name = async_to_sync(channel_layer.new_channel)()
		async_to_sync(channel_layer.group_add)("vote_results", channel_name)

		response = self.client.post(
			"/google/",
			data=json.dumps({
				"email": "incoming@example.com",
				"candidate": "Candidate B",
			}),
			content_type="application/json",
		)
		event = async_to_sync(channel_layer.receive)(channel_name)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["results"], {"Candidate A": 1, "Candidate B": 1})
		self.assertEqual(event["votes"], {"Candidate A": 1, "Candidate B": 1})
		self.assertEqual(event["vote"]["candidate"], "Candidate B")
		self.assertEqual(event["vote"]["email"], "incoming@example.com")

	def test_live_voter_details_are_sent_only_to_admins(self):
		event = {
			"votes": {"Candidate A": 1},
			"vote": {
				"email": "private@example.com",
				"candidate": "Candidate A",
				"date_created": "2026-10-01T12:00:00+00:00",
			},
		}
		for user, should_include_details in (
			(AnonymousUser(), False),
			(User(is_staff=True), True),
		):
			with self.subTest(admin=should_include_details):
				consumer = VoteConsumer2({"user": user}, None, None)
				consumer.is_admin = user.is_authenticated and (user.is_staff or user.is_superuser)
				consumer.send = AsyncMock()
				async_to_sync(consumer.vote_update)(event)
				payload = json.loads(consumer.send.call_args.kwargs["text_data"])
				self.assertEqual("vote" in payload, should_include_details)
				if should_include_details:
					self.assertEqual(payload["vote"]["email"], "private@example.com")
