
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.test import TestCase
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Vote


User = get_user_model()


class AccountFlowTests(TestCase):
	def test_dashboard_redirects_anonymous_users_to_account_page(self):
		response = self.client.get("/")

		self.assertRedirects(response, "/account/?next=/")

	def test_registration_waits_for_admin_approval(self):
		response = self.client.post("/account/", {
			"form_type": "register",
			"username": "newvoter",
			"email": "voter@example.com",
			"password1": "A-secure-test-password-872!",
			"password2": "A-secure-test-password-872!",
		}, follow=True)

		self.assertEqual(response.redirect_chain, [("/account/", 302)])
		user = User.objects.get(username="newvoter")
		self.assertFalse(user.is_active)
		self.assertFalse(self.client.session.get("_auth_user_id"))
		self.assertContains(response, "An administrator must approve")

	def test_admin_approval_allows_user_to_login(self):
		self.client.post("/account/", {
			"form_type": "register",
			"username": "returningvoter",
			"email": "returning@example.com",
			"password1": "A-secure-test-password-872!",
			"password2": "A-secure-test-password-872!",
		})
		user = User.objects.get(username="returningvoter")

		response = self.client.post("/account/", {
			"form_type": "login",
			"username": "returningvoter",
			"password": "A-secure-test-password-872!",
		})
		self.assertEqual(response.status_code, 200)
		self.assertFalse(self.client.session.get("_auth_user_id"))

		admin = User.objects.create_superuser(
			username="reviewer",
			email="reviewer@example.com",
			password="Admin-test-password-872!",
		)
		self.client.force_login(admin)
		response = self.client.post(reverse("admin:auth_user_changelist"), {
			"action": "approve_accounts",
			"_selected_action": [str(user.pk)],
			"index": "0",
		})
		self.assertEqual(response.status_code, 302)
		user.refresh_from_db()
		self.assertTrue(user.is_active)
		self.client.logout()

		response = self.client.post("/account/", {
			"form_type": "login",
			"username": "returningvoter",
			"password": "A-secure-test-password-872!",
		})

		self.assertRedirects(response, "/")
		self.assertTrue(self.client.session.get("_auth_user_id"))

	def test_dashboard_loads_saved_totals_and_recent_vote_details(self):
		user = User.objects.create_user(username="approvedvoter", password="test-pass-872!")
		self.client.force_login(user)
		Vote.objects.create(email="private-one@example.com", candidate="Candidate A")
		Vote.objects.create(email="private-two@example.com", candidate="Candidate A")
		Vote.objects.create(email="private-three@example.com", candidate="Candidate B")

		response = self.client.get("/")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["vote_totals"], {"Candidate A": 2, "Candidate B": 1})
		self.assertEqual(len(response.context["recent_votes"]), 3)
		self.assertContains(response, "Candidate A")
		self.assertContains(response, "Candidate B")
		self.assertNotContains(response, "private-one@example.com")

	def test_dashboard_paginates_older_vote_history(self):
		user = User.objects.create_user(username="historyviewer", password="test-pass-872!")
		self.client.force_login(user)
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
