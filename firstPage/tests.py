from django.test import TestCase


class AccountFlowTests(TestCase):
	def test_dashboard_redirects_anonymous_users_to_account_page(self):
		response = self.client.get("/")

		self.assertRedirects(response, "/account/?next=/")

	def test_registration_logs_user_in_and_opens_dashboard(self):
		response = self.client.post("/account/", {
			"form_type": "register",
			"username": "newvoter",
			"email": "voter@example.com",
			"password1": "A-secure-test-password-872!",
			"password2": "A-secure-test-password-872!",
		})

		self.assertRedirects(response, "/")
		self.assertTrue(self.client.session.get("_auth_user_id"))
		self.assertEqual(self.client.get("/").status_code, 200)

	def test_user_can_login_after_logging_out(self):
		self.client.post("/account/", {
			"form_type": "register",
			"username": "returningvoter",
			"email": "returning@example.com",
			"password1": "A-secure-test-password-872!",
			"password2": "A-secure-test-password-872!",
		})
		self.client.post("/logout/")

		response = self.client.post("/account/", {
			"form_type": "login",
			"username": "returningvoter",
			"password": "A-secure-test-password-872!",
		})

		self.assertRedirects(response, "/")
		self.assertTrue(self.client.session.get("_auth_user_id"))
