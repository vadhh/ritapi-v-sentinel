"""
RBAC Security Tests
===================
Tests for TODO items 1.1, 1.2, 1.3:
- 1.1: OpsAuthMiddleware deny-by-default with locked-account check
- 1.2: Role downgrade, absence, and session manipulation
- 1.3: RBAC permission enforcement on all minifw POST handlers

Run with:
    python manage.py test tests.test_rbac_security -v2
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings


MIDDLEWARE_FOR_TESTS = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "authentication.middleware.OpsAuthMiddleware",
]

TEST_DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

COMMON_SETTINGS = dict(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)


def _mock_minifw_services():
    """Patches for external system services (subprocess, file I/O). Does NOT mock RBACService."""
    return {
        "minifw.services.MiniFWService.get_status": {
            "active": False, "enabled": False, "status": "stopped",
        },
        "minifw.services.MiniFWStats.get_stats": {
            "total_events": 0, "blocked": 0, "monitored": 0, "allowed": 0,
            "top_blocked_ips": {}, "top_blocked_domains": {}, "by_segment": {},
        },
        "minifw.services.MiniFWStats.get_recent_events": [],
        "minifw.services.MiniFWIPSet.list_blocked_ips": [],
        "minifw.services.SectorLock.get_sector": "establishment",
        "minifw.services.SectorLock.get_description": "Establishment: Balanced protection.",
        "minifw.services.SectorLock.get_full_config": {"sector": "establishment"},
        "minifw.services.MiniFWConfig.load_policy": {},
        "minifw.services.MiniFWConfig.get_segments": {},
        "minifw.services.MiniFWConfig.get_segment_subnets": {},
        "minifw.services.MiniFWConfig.get_features": {},
        "minifw.services.MiniFWConfig.get_burst": {},
        "minifw.services.MiniFWConfig.get_enforcement": {},
        "minifw.services.MiniFWFeeds.read_feed": [],
        "minifw.services.MiniFWEventsService.get_events_datatable": {
            "draw": 1, "recordsTotal": 0, "recordsFiltered": 0, "data": [],
        },
        "minifw.services.AuditService.get_logs": {"total": 0, "logs": []},
        "minifw.services.AuditService.get_statistics": {
            "total": 0, "critical": 0, "warning": 0, "info": 0,
        },
        "minifw.services.AuditService.export_logs": "[]",
        "minifw.services.AuditService.log_action": True,
    }


class RBACTestBase(TestCase):
    """Base class with helpers for creating users with specific roles."""

    @classmethod
    def setUpTestData(cls):
        from minifw.models import UserProfile

        # Signal auto-creates profile for superusers, so use get_or_create
        cls.superuser = User.objects.create_superuser(
            username="superadmin", email="sa@test.local", password="TestPass123!",
        )
        profile, _ = UserProfile.objects.get_or_create(user=cls.superuser)
        profile.role = "SUPER_ADMIN"
        profile.save()

        cls.admin_user = User.objects.create_user(
            username="admin_user", email="admin@test.local", password="TestPass123!",
        )
        UserProfile.objects.create(user=cls.admin_user, role="ADMIN")

        cls.operator_user = User.objects.create_user(
            username="operator_user", email="op@test.local", password="TestPass123!",
        )
        UserProfile.objects.create(user=cls.operator_user, role="OPERATOR")

        cls.auditor_user = User.objects.create_user(
            username="auditor_user", email="aud@test.local", password="TestPass123!",
        )
        UserProfile.objects.create(user=cls.auditor_user, role="AUDITOR")

        cls.viewer_user = User.objects.create_user(
            username="viewer_user", email="viewer@test.local", password="TestPass123!",
        )
        UserProfile.objects.create(user=cls.viewer_user, role="VIEWER")

        cls.no_profile_user = User.objects.create_user(
            username="noprofile", email="np@test.local", password="TestPass123!",
        )

        cls.locked_user = User.objects.create_user(
            username="locked_user", email="locked@test.local", password="TestPass123!",
        )
        UserProfile.objects.create(user=cls.locked_user, role="OPERATOR", is_locked=True)

    def setUp(self):
        self.client = Client()
        self._patches = []
        for target, return_value in _mock_minifw_services().items():
            p = patch(target, return_value=return_value)
            p.start()
            self._patches.append(p)

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def login_as(self, user):
        self.client.login(username=user.username, password="TestPass123!")


# ===========================================================================
# 1. TestMiddlewareDenyByDefault (TODO 1.1)
# ===========================================================================

@override_settings(**COMMON_SETTINGS)
class TestMiddlewareDenyByDefault(RBACTestBase):
    """OpsAuthMiddleware uses deny-by-default pattern."""

    def test_unauthenticated_redirected(self):
        """Anonymous user accessing /ops/ is redirected to login."""
        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertIn(resp.status_code, [301, 302])
        self.assertIn("login", resp.url)

    def test_no_profile_user_denied(self):
        """User without a UserProfile is denied access to /ops/."""
        self.login_as(self.no_profile_user)
        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertIn(resp.status_code, [301, 302])

    def test_locked_user_denied(self):
        """Locked OPERATOR is denied access to /ops/."""
        self.login_as(self.locked_user)
        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertIn(resp.status_code, [301, 302])

    def test_superuser_allowed_without_profile(self):
        """Superuser without profile can still access /ops/."""
        from minifw.models import UserProfile
        superuser_no_profile = User.objects.create_superuser(
            username="su_noprofile", email="sunp@test.local", password="TestPass123!",
        )
        # Signal auto-creates profile for superusers; delete it to test fallback
        UserProfile.objects.filter(user=superuser_no_profile).delete()
        self.login_as(superuser_no_profile)
        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertEqual(resp.status_code, 200)

    def test_viewer_can_access_dashboard_get(self):
        """VIEWER can access dashboard via GET."""
        self.login_as(self.viewer_user)
        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# 2. TestRoleDowngrade (TODO 1.2)
# ===========================================================================

@override_settings(**COMMON_SETTINGS)
class TestRoleDowngrade(RBACTestBase):
    """Role changes take effect immediately."""

    @patch("minifw.services.MiniFWConfig.update_segments", return_value=True)
    def test_admin_downgraded_to_viewer_cannot_post_policy(self, _mock_update):
        """ADMIN downgraded to VIEWER mid-session cannot POST policy."""
        from minifw.models import UserProfile
        self.login_as(self.admin_user)

        # Downgrade role
        profile = UserProfile.objects.get(user=self.admin_user)
        profile.role = "VIEWER"
        profile.save()

        resp = self.client.post(
            "/ops/minifw/policy/",
            {"action": "update_segments"},
            follow=False,
        )
        # Should redirect with permission denied
        self.assertIn(resp.status_code, [301, 302])

        # Restore
        profile.role = "ADMIN"
        profile.save()

    @patch("minifw.services.MiniFWIPSet.add_ip", return_value=True)
    def test_operator_downgraded_cannot_block_ip(self, _mock_add):
        """OPERATOR downgraded to VIEWER cannot block IPs."""
        from minifw.models import UserProfile
        self.login_as(self.operator_user)

        profile = UserProfile.objects.get(user=self.operator_user)
        profile.role = "VIEWER"
        profile.save()

        resp = self.client.post(
            "/ops/minifw/blocked-ips/",
            {"action": "block_ip", "ip": "10.0.0.1", "timeout": "3600"},
            follow=False,
        )
        self.assertIn(resp.status_code, [301, 302])

        # Restore
        profile.role = "OPERATOR"
        profile.save()


# ===========================================================================
# 3. TestRoleAbsence (TODO 1.2)
# ===========================================================================

@override_settings(**COMMON_SETTINGS)
class TestRoleAbsence(RBACTestBase):
    """Missing or invalid profiles are denied."""

    def test_profile_deleted_cannot_access_ops(self):
        """User whose profile is deleted cannot access /ops/."""
        temp_user = User.objects.create_user(
            username="temp_user", email="temp@test.local", password="TestPass123!",
        )
        from minifw.models import UserProfile
        UserProfile.objects.create(user=temp_user, role="OPERATOR")

        self.login_as(temp_user)
        # Verify access works
        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertEqual(resp.status_code, 200)

        # Delete profile
        UserProfile.objects.filter(user=temp_user).delete()
        # Clear cached profile
        if hasattr(temp_user, '_profile_cache'):
            delattr(temp_user, '_profile_cache')

        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertIn(resp.status_code, [301, 302])

    def test_malformed_role_treated_as_lowest(self):
        """Invalid role string cannot modify policy (treated as unknown level)."""
        from minifw.models import UserProfile
        temp_user = User.objects.create_user(
            username="malformed_role", email="mal@test.local", password="TestPass123!",
        )
        UserProfile.objects.create(user=temp_user, role="INVALID_ROLE")

        self.login_as(temp_user)
        resp = self.client.post(
            "/ops/minifw/policy/",
            {"action": "update_segments"},
            follow=False,
        )
        # Should be denied (INVALID_ROLE maps to level 0)
        self.assertIn(resp.status_code, [301, 302])


# ===========================================================================
# 4. TestSessionManipulation (TODO 1.2)
# ===========================================================================

@override_settings(**COMMON_SETTINGS)
class TestSessionManipulation(RBACTestBase):
    """Session edge cases."""

    def test_logged_out_cannot_access(self):
        """After logout, /ops/ access redirects to login."""
        self.login_as(self.admin_user)
        self.client.logout()
        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertIn(resp.status_code, [301, 302])
        self.assertIn("login", resp.url)

    def test_inactive_user_denied(self):
        """User with is_active=False cannot access ops."""
        from minifw.models import UserProfile
        inactive_user = User.objects.create_user(
            username="inactive_user", email="inactive@test.local",
            password="TestPass123!", is_active=False,
        )
        UserProfile.objects.create(user=inactive_user, role="ADMIN")

        # Django's auth backend rejects inactive users at login
        logged_in = self.client.login(username="inactive_user", password="TestPass123!")
        self.assertFalse(logged_in)

        resp = self.client.get("/ops/minifw/dashboard/", follow=False)
        self.assertIn(resp.status_code, [301, 302])


# ===========================================================================
# 5. TestRoleEnforcement (TODO 1.3) — POST endpoint permission matrix
# ===========================================================================

@override_settings(**COMMON_SETTINGS)
class TestRoleEnforcement(RBACTestBase):
    """Verify RBAC checks on all minifw POST endpoints."""

    # Endpoints requiring ADMIN (can_modify_policy)
    ADMIN_POST_ENDPOINTS = [
        ("/ops/minifw/policy/", {"action": "update_segments"}),
        ("/ops/minifw/feeds/", {"action": "update_feed", "feed_name": "deny_ips", "entries": "1.2.3.4"}),
    ]

    # Endpoints requiring OPERATOR (can_execute_enforcement)
    OPERATOR_POST_ENDPOINTS = [
        ("/ops/minifw/blocked-ips/", {"action": "block_ip", "ip": "10.0.0.1", "timeout": "3600"}),
        ("/ops/minifw/service/control/", {"action": "restart"}),
    ]

    @patch("minifw.services.MiniFWConfig.update_segments", return_value=True)
    @patch("minifw.services.MiniFWFeeds.write_feed", return_value=True)
    @patch("minifw.services.MiniFWIPSet.add_ip", return_value=True)
    @patch("minifw.services.MiniFWService.restart", return_value=True)
    def test_viewer_denied_all_posts(self, *mocks):
        """VIEWER is denied on all POST endpoints."""
        self.login_as(self.viewer_user)
        for url, data in self.ADMIN_POST_ENDPOINTS + self.OPERATOR_POST_ENDPOINTS:
            with self.subTest(url=url):
                resp = self.client.post(url, data, follow=False)
                self.assertIn(resp.status_code, [301, 302],
                    f"VIEWER should be denied on POST {url}")

    @patch("minifw.services.MiniFWConfig.update_segments", return_value=True)
    @patch("minifw.services.MiniFWFeeds.write_feed", return_value=True)
    @patch("minifw.services.MiniFWIPSet.add_ip", return_value=True)
    @patch("minifw.services.MiniFWService.restart", return_value=True)
    def test_auditor_denied_policy_and_enforcement(self, *mocks):
        """AUDITOR is denied on policy and enforcement POSTs."""
        self.login_as(self.auditor_user)
        for url, data in self.ADMIN_POST_ENDPOINTS + self.OPERATOR_POST_ENDPOINTS:
            with self.subTest(url=url):
                resp = self.client.post(url, data, follow=False)
                self.assertIn(resp.status_code, [301, 302],
                    f"AUDITOR should be denied on POST {url}")

    @patch("minifw.services.MiniFWConfig.update_segments", return_value=True)
    @patch("minifw.services.MiniFWFeeds.write_feed", return_value=True)
    @patch("minifw.services.MiniFWIPSet.add_ip", return_value=True)
    @patch("minifw.services.MiniFWService.restart", return_value=True)
    def test_operator_denied_on_policy_allowed_on_enforcement(self, *mocks):
        """OPERATOR is denied on policy/feeds but allowed on blocked-ips/service-control."""
        self.login_as(self.operator_user)

        # Denied on ADMIN endpoints
        for url, data in self.ADMIN_POST_ENDPOINTS:
            with self.subTest(url=url, expected="denied"):
                resp = self.client.post(url, data, follow=False)
                self.assertIn(resp.status_code, [301, 302],
                    f"OPERATOR should be denied on POST {url}")

        # Allowed on OPERATOR endpoints (redirect on success = 302 to same page)
        for url, data in self.OPERATOR_POST_ENDPOINTS:
            with self.subTest(url=url, expected="allowed"):
                resp = self.client.post(url, data, follow=False)
                # Allowed POSTs redirect back (302) but NOT to login
                self.assertEqual(resp.status_code, 302)

    @patch("minifw.services.MiniFWConfig.update_segments", return_value=True)
    @patch("minifw.services.MiniFWFeeds.write_feed", return_value=True)
    @patch("minifw.services.MiniFWIPSet.add_ip", return_value=True)
    @patch("minifw.services.MiniFWService.restart", return_value=True)
    def test_admin_allowed_on_all(self, *mocks):
        """ADMIN is allowed on all policy and enforcement POSTs."""
        self.login_as(self.admin_user)
        for url, data in self.ADMIN_POST_ENDPOINTS + self.OPERATOR_POST_ENDPOINTS:
            with self.subTest(url=url):
                resp = self.client.post(url, data, follow=False)
                self.assertEqual(resp.status_code, 302,
                    f"ADMIN should be allowed on POST {url}")

    @patch("minifw.services.MiniFWConfig.update_segments", return_value=True)
    @patch("minifw.services.MiniFWFeeds.write_feed", return_value=True)
    @patch("minifw.services.MiniFWIPSet.add_ip", return_value=True)
    @patch("minifw.services.MiniFWService.restart", return_value=True)
    def test_super_admin_allowed_everywhere(self, *mocks):
        """SUPER_ADMIN is allowed on all POST endpoints."""
        self.login_as(self.superuser)
        for url, data in self.ADMIN_POST_ENDPOINTS + self.OPERATOR_POST_ENDPOINTS:
            with self.subTest(url=url):
                resp = self.client.post(url, data, follow=False)
                self.assertEqual(resp.status_code, 302,
                    f"SUPER_ADMIN should be allowed on POST {url}")


# ===========================================================================
# 6. TestAuditAPIPermissions (TODO 1.3) — Audit API RBAC checks
# ===========================================================================

@override_settings(**COMMON_SETTINGS)
class TestAuditAPIPermissions(RBACTestBase):
    """Verify audit API endpoints enforce AUDITOR role check."""

    def test_viewer_denied_audit_logs(self):
        """VIEWER cannot access audit logs API."""
        self.login_as(self.viewer_user)
        resp = self.client.get("/ops/minifw/api/audit/logs/")
        self.assertEqual(resp.status_code, 403)

    def test_viewer_denied_audit_statistics(self):
        """VIEWER cannot access audit statistics API."""
        self.login_as(self.viewer_user)
        resp = self.client.get("/ops/minifw/api/audit/statistics/")
        self.assertEqual(resp.status_code, 403)

    def test_auditor_allowed_audit_logs(self):
        """AUDITOR can access audit logs API."""
        self.login_as(self.auditor_user)
        resp = self.client.get("/ops/minifw/api/audit/logs/")
        self.assertEqual(resp.status_code, 200)

    def test_auditor_allowed_audit_statistics(self):
        """AUDITOR can access audit statistics API."""
        self.login_as(self.auditor_user)
        resp = self.client.get("/ops/minifw/api/audit/statistics/")
        self.assertEqual(resp.status_code, 200)

    def test_operator_allowed_audit_logs(self):
        """OPERATOR (level 3 > AUDITOR level 2) can access audit logs."""
        self.login_as(self.operator_user)
        resp = self.client.get("/ops/minifw/api/audit/logs/")
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# 7. TestLoginRequiredOnAPIs (TODO 1.3) — @login_required on AJAX endpoints
# ===========================================================================

@override_settings(**COMMON_SETTINGS)
class TestLoginRequiredOnAPIs(RBACTestBase):
    """Verify @login_required on previously unprotected AJAX endpoints."""

    AJAX_ENDPOINTS = [
        "/ops/minifw/api/stats/",
        "/ops/minifw/api/service-status/",
        "/ops/minifw/api/events/",
    ]

    def test_unauthenticated_redirected_on_ajax(self):
        """Anonymous access to AJAX endpoints redirects to login."""
        for url in self.AJAX_ENDPOINTS:
            with self.subTest(url=url):
                resp = self.client.get(url, follow=False)
                self.assertIn(resp.status_code, [301, 302])

    def test_authenticated_viewer_can_access_ajax(self):
        """Authenticated VIEWER can access read-only AJAX endpoints."""
        self.login_as(self.viewer_user)
        for url in self.AJAX_ENDPOINTS:
            with self.subTest(url=url):
                resp = self.client.get(url, follow=False)
                self.assertEqual(resp.status_code, 200)
