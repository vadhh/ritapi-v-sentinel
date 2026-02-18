from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin", password="admin-pass-123"
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="regular-pass-123"
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")

    def test_login_superuser_success(self):
        response = self.client.post(
            reverse("login"),
            {"username": "admin", "password": "admin-pass-123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("ops_dashboard"))

    def test_login_non_superuser_rejected(self):
        response = self.client.post(
            reverse("login"),
            {"username": "regular", "password": "regular-pass-123"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertTrue(form.errors)
        self.assertIn("__all__", form.errors)
        self.assertIn("permission", form.errors["__all__"][0].lower())

    def test_login_invalid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {"username": "admin", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertTrue(form.errors)

    def test_authenticated_superuser_redirected(self):
        self.client.login(username="admin", password="admin-pass-123")
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 302)

    def test_logout(self):
        self.client.login(username="admin", password="admin-pass-123")
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("login"))

    def test_change_password_requires_login(self):
        response = self.client.get(reverse("change_password"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_change_password_success(self):
        self.client.login(username="admin", password="admin-pass-123")
        response = self.client.post(
            reverse("change_password"),
            {
                "old_password": "admin-pass-123",
                "new_password1": "new-secure-pass-456",
                "new_password2": "new-secure-pass-456",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password("new-secure-pass-456"))
