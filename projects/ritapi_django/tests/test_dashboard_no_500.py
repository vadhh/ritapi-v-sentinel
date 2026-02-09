"""
Comprehensive Dashboard Smoke Tests
====================================
Ensures all dashboard pages and API endpoints return non-500 responses.
Covers: HTML pages, JSON APIs, DRF endpoints, authenticated & unauthenticated access.

Run with:
    python manage.py test tests.test_dashboard_no_500 -v2
"""

from unittest.mock import patch, MagicMock, PropertyMock

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings


# ---------------------------------------------------------------------------
# Stub middleware that depends on Redis / external services so the test
# suite can run with just SQLite and no infrastructure.
# ---------------------------------------------------------------------------
MIDDLEWARE_FOR_TESTS = [
    # Skip RateLimiterMiddleware (needs Redis)
    # Skip SecurityEnforcementMiddleware (dynamic imports)
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


def _mock_minifw_services():
    """Return a dict of patch targets and their return values for MiniFW services."""
    return {
        "minifw.services.MiniFWService.get_status": {
            "active": False,
            "enabled": False,
            "status": "stopped",
        },
        "minifw.services.MiniFWStats.get_stats": {
            "total_events": 0,
            "blocked": 0,
            "monitored": 0,
            "allowed": 0,
            "top_blocked_ips": {},
            "top_blocked_domains": {},
            "by_segment": {},
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
            "draw": 1,
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "data": [],
        },
        "minifw.services.AuditService.get_logs": {"total": 0, "logs": []},
        "minifw.services.AuditService.get_statistics": {
            "total": 0,
            "critical": 0,
            "warning": 0,
            "info": 0,
        },
        "minifw.services.AuditService.export_logs": "[]",
        "minifw.services.RBACService.check_permission": True,
        "minifw.services.RBACService.get_user_role": "SUPER_ADMIN",
        "minifw.services.RBACService.can_modify_policy": True,
        "minifw.services.RBACService.can_execute_enforcement": True,
        "minifw.services.RBACService.can_access_audit": True,
        "minifw.services.RBACService.can_export_data": True,
    }


@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class DashboardSmokeTestBase(TestCase):
    """Base class that creates a superuser and provides helper assertions."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@test.local",
            password="TestPass123!",
        )
        cls.regular_user = User.objects.create_user(
            username="viewer",
            email="viewer@test.local",
            password="TestPass123!",
        )

    def setUp(self):
        self.client = Client()

    def login_superuser(self):
        self.client.login(username="admin", password="TestPass123!")

    def login_regular(self):
        self.client.login(username="viewer", password="TestPass123!")

    def assert_no_500(self, response, url):
        """Assert response is NOT a server error (5xx)."""
        self.assertLess(
            response.status_code,
            500,
            f"URL {url} returned {response.status_code} (expected < 500)",
        )


# ===========================================================================
# 1. Public / Unauthenticated Endpoints
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestPublicEndpoints(DashboardSmokeTestBase):
    """Test endpoints that should work without authentication."""

    def test_healthz(self):
        """GET /healthz should return 200."""
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")

    def test_home_redirects_unauthenticated(self):
        """GET / should redirect unauthenticated users to login."""
        resp = self.client.get("/", follow=False)
        self.assertIn(resp.status_code, [301, 302])

    def test_login_page(self):
        """GET /login/ should render without 500."""
        resp = self.client.get("/login/")
        self.assert_no_500(resp, "/login/")

    def test_auth_login_page(self):
        """GET /auth/login/ should render without 500."""
        resp = self.client.get("/auth/login/")
        self.assert_no_500(resp, "/auth/login/")


# ===========================================================================
# 2. Authenticated Redirect Tests
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestAuthRedirects(DashboardSmokeTestBase):
    """Unauthenticated access to /ops/ should redirect, never 500."""

    OPS_URLS = [
        "/ops/",
        "/ops/asn/asn-checker/",
        "/ops/asn/asn-config/",
        "/ops/ip-reputation/",
        "/ops/ip-reputation/internal-ip/",
        "/ops/alerts/",
        "/ops/blocked-ips/",
        "/ops/blocked-ips/blocked-map/",
        "/ops/json-schema/",
        "/ops/geo-block/",
        "/ops/requestlogs/",
        "/ops/minifw/dashboard/",
        "/ops/minifw/policy/",
        "/ops/minifw/feeds/",
        "/ops/minifw/blocked-ips/",
        "/ops/minifw/audit-logs/",
        "/ops/minifw/events/",
        "/ops/minifw/users/",
    ]

    def test_ops_pages_redirect_when_unauthenticated(self):
        """All /ops/ pages should redirect (302) for anonymous users, never 500."""
        for url in self.OPS_URLS:
            with self.subTest(url=url):
                resp = self.client.get(url, follow=False)
                self.assert_no_500(resp, url)
                self.assertIn(
                    resp.status_code,
                    [301, 302, 403],
                    f"{url} returned {resp.status_code}, expected redirect/forbidden",
                )


# ===========================================================================
# 3. Ops Dashboard Pages (Authenticated Superuser)
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestOpsDashboardPages(DashboardSmokeTestBase):
    """Test all ops HTML dashboard pages render without 500 for superuser."""

    def setUp(self):
        super().setUp()
        self.login_superuser()

    def test_ops_main_dashboard(self):
        resp = self.client.get("/ops/")
        self.assert_no_500(resp, "/ops/")

    def test_ops_asn_checker(self):
        resp = self.client.get("/ops/asn/asn-checker/")
        self.assert_no_500(resp, "/ops/asn/asn-checker/")

    def test_ops_asn_config(self):
        resp = self.client.get("/ops/asn/asn-config/")
        self.assert_no_500(resp, "/ops/asn/asn-config/")

    def test_ops_ip_reputation(self):
        resp = self.client.get("/ops/ip-reputation/")
        self.assert_no_500(resp, "/ops/ip-reputation/")

    def test_ops_internal_ip(self):
        resp = self.client.get("/ops/ip-reputation/internal-ip/")
        self.assert_no_500(resp, "/ops/ip-reputation/internal-ip/")

    def test_ops_alerts(self):
        resp = self.client.get("/ops/alerts/")
        self.assert_no_500(resp, "/ops/alerts/")

    def test_ops_alerts_chart_data(self):
        resp = self.client.get("/ops/alerts/alert_chart_data/")
        self.assert_no_500(resp, "/ops/alerts/alert_chart_data/")
        self.assertEqual(resp["Content-Type"], "application/json")

    def test_ops_blocked_ips(self):
        resp = self.client.get("/ops/blocked-ips/")
        self.assert_no_500(resp, "/ops/blocked-ips/")

    def test_ops_blocked_ip_map(self):
        resp = self.client.get("/ops/blocked-ips/blocked-map/")
        self.assert_no_500(resp, "/ops/blocked-ips/blocked-map/")

    def test_ops_blocked_ip_data(self):
        resp = self.client.get("/ops/blocked-ips/blocked-map/data/")
        self.assert_no_500(resp, "/ops/blocked-ips/blocked-map/data/")
        self.assertEqual(resp["Content-Type"], "application/json")

    def test_ops_json_schema(self):
        resp = self.client.get("/ops/json-schema/")
        self.assert_no_500(resp, "/ops/json-schema/")

    def test_ops_geo_block(self):
        resp = self.client.get("/ops/geo-block/")
        self.assert_no_500(resp, "/ops/geo-block/")

    def test_ops_requestlogs(self):
        resp = self.client.get("/ops/requestlogs/")
        self.assert_no_500(resp, "/ops/requestlogs/")

    def test_ops_requestlog_data(self):
        resp = self.client.get("/ops/requestlogs/api/")
        self.assert_no_500(resp, "/ops/requestlogs/api/")

    def test_ops_requestlog_chart_data(self):
        resp = self.client.get("/ops/requestlogs/chart-data/")
        self.assert_no_500(resp, "/ops/requestlogs/chart-data/")

    def test_ops_requestlog_export(self):
        resp = self.client.get("/ops/requestlogs/export/")
        self.assert_no_500(resp, "/ops/requestlogs/export/")


# ===========================================================================
# 4. MiniFW Dashboard Pages (require mocking external services)
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestMiniFWDashboardPages(DashboardSmokeTestBase):
    """Test MiniFW ops pages render without 500 (services mocked)."""

    def setUp(self):
        super().setUp()
        self.login_superuser()
        # Start patches for all MiniFW services
        self._patches = []
        for target, return_value in _mock_minifw_services().items():
            p = patch(target, return_value=return_value)
            p.start()
            self._patches.append(p)

    def tearDown(self):
        for p in self._patches:
            p.stop()
        super().tearDown()

    def test_minifw_dashboard(self):
        resp = self.client.get("/ops/minifw/dashboard/")
        self.assert_no_500(resp, "/ops/minifw/dashboard/")

    def test_minifw_policy(self):
        resp = self.client.get("/ops/minifw/policy/")
        self.assert_no_500(resp, "/ops/minifw/policy/")

    def test_minifw_feeds(self):
        resp = self.client.get("/ops/minifw/feeds/")
        self.assert_no_500(resp, "/ops/minifw/feeds/")

    def test_minifw_blocked_ips(self):
        resp = self.client.get("/ops/minifw/blocked-ips/")
        self.assert_no_500(resp, "/ops/minifw/blocked-ips/")

    def test_minifw_audit_logs(self):
        resp = self.client.get("/ops/minifw/audit-logs/")
        self.assert_no_500(resp, "/ops/minifw/audit-logs/")

    def test_minifw_events(self):
        resp = self.client.get("/ops/minifw/events/")
        self.assert_no_500(resp, "/ops/minifw/events/")

    def test_minifw_users(self):
        resp = self.client.get("/ops/minifw/users/")
        self.assert_no_500(resp, "/ops/minifw/users/")


# ===========================================================================
# 5. MiniFW JSON API Endpoints (Authenticated)
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestMiniFWAPIEndpoints(DashboardSmokeTestBase):
    """Test MiniFW API endpoints return valid JSON, no 500."""

    def setUp(self):
        super().setUp()
        self.login_superuser()
        self._patches = []
        for target, return_value in _mock_minifw_services().items():
            p = patch(target, return_value=return_value)
            p.start()
            self._patches.append(p)

    def tearDown(self):
        for p in self._patches:
            p.stop()
        super().tearDown()

    def test_api_stats(self):
        resp = self.client.get("/ops/minifw/api/stats/")
        self.assert_no_500(resp, "/ops/minifw/api/stats/")
        self.assertEqual(resp["Content-Type"], "application/json")

    def test_api_service_status(self):
        resp = self.client.get("/ops/minifw/api/service-status/")
        self.assert_no_500(resp, "/ops/minifw/api/service-status/")

    def test_api_recent_events(self):
        resp = self.client.get("/ops/minifw/api/events/")
        self.assert_no_500(resp, "/ops/minifw/api/events/")
        data = resp.json()
        self.assertIn("events", data)

    def test_api_events_datatable(self):
        resp = self.client.get("/ops/minifw/api/events/datatable/?draw=1&start=0&length=10")
        self.assert_no_500(resp, "/ops/minifw/api/events/datatable/")

    def test_api_audit_logs(self):
        resp = self.client.get("/ops/minifw/api/audit/logs/")
        self.assert_no_500(resp, "/ops/minifw/api/audit/logs/")

    def test_api_audit_statistics(self):
        resp = self.client.get("/ops/minifw/api/audit/statistics/")
        self.assert_no_500(resp, "/ops/minifw/api/audit/statistics/")

    def test_api_audit_export(self):
        resp = self.client.get("/ops/minifw/api/audit/export/")
        self.assert_no_500(resp, "/ops/minifw/api/audit/export/")

    def test_api_users_list(self):
        resp = self.client.get("/ops/minifw/api/users/")
        self.assert_no_500(resp, "/ops/minifw/api/users/")

    def test_api_current_user(self):
        resp = self.client.get("/ops/minifw/api/auth/current-user/")
        self.assert_no_500(resp, "/ops/minifw/api/auth/current-user/")

    def test_api_sector_lock(self):
        resp = self.client.get("/ops/minifw/api/sector-lock/")
        self.assert_no_500(resp, "/ops/minifw/api/sector-lock/")


# ===========================================================================
# 6. DRF API Endpoints
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestDRFAPIEndpoints(DashboardSmokeTestBase):
    """Test DRF-based API endpoints do not return 500."""

    def test_asn_lookup_missing_body(self):
        """POST /asn/lookup/ with empty body should not 500."""
        resp = self.client.post("/asn/lookup/", {}, content_type="application/json")
        self.assert_no_500(resp, "/asn/lookup/")

    def test_asn_history(self):
        """GET /asn/history/ should not 500."""
        resp = self.client.get("/asn/history/")
        self.assert_no_500(resp, "/asn/history/")

    def test_ip_reputation_lookup_missing_body(self):
        """POST /ip-reputation/lookup/ with empty body should not 500."""
        resp = self.client.post(
            "/ip-reputation/lookup/", {}, content_type="application/json"
        )
        self.assert_no_500(resp, "/ip-reputation/lookup/")

    @patch("alert.services.AlertService.create_alert")
    def test_alert_create(self, mock_create):
        """POST /alerts/create/ with valid data should not 500."""
        mock_create.return_value = MagicMock(id=1)
        resp = self.client.post(
            "/alerts/create/",
            {"alert_type": "Test", "ip_address": "10.0.0.1", "detail": "Test alert"},
            content_type="application/json",
        )
        self.assert_no_500(resp, "/alerts/create/")

    def test_alert_list(self):
        """GET /alerts/list/ should not 500."""
        resp = self.client.get("/alerts/list/")
        self.assert_no_500(resp, "/alerts/list/")

    def test_blocking_list_blocked(self):
        """GET /blocking/blocked/ should not 500."""
        resp = self.client.get("/blocking/blocked/")
        self.assert_no_500(resp, "/blocking/blocked/")

    def test_blocking_check_ip(self):
        """GET /blocking/check/<ip>/ should not 500."""
        resp = self.client.get("/blocking/check/192.168.1.1/")
        self.assert_no_500(resp, "/blocking/check/192.168.1.1/")

    def test_json_schema_list(self):
        """GET /json/schemas/ should not 500."""
        resp = self.client.get("/json/schemas/")
        self.assert_no_500(resp, "/json/schemas/")


# ===========================================================================
# 7. Ops CRUD Endpoints (POST) - Superuser
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestOpsCRUDEndpoints(DashboardSmokeTestBase):
    """Test POST-based CRUD ops endpoints do not return 500."""

    def setUp(self):
        super().setUp()
        self.login_superuser()

    def test_geo_block_create(self):
        resp = self.client.post(
            "/ops/geo-block/create/",
            {"country_code": "CN", "action": "block", "description": "Test", "is_active": "true"},
        )
        self.assert_no_500(resp, "/ops/geo-block/create/")

    def test_geo_block_create_missing_country(self):
        resp = self.client.post(
            "/ops/geo-block/create/",
            {"action": "block"},
        )
        self.assert_no_500(resp, "/ops/geo-block/create/")
        self.assertEqual(resp.status_code, 400)

    def test_geo_block_delete_nonexistent(self):
        resp = self.client.post("/ops/geo-block/delete/99999/")
        self.assert_no_500(resp, "/ops/geo-block/delete/99999/")
        self.assertEqual(resp.status_code, 404)

    def test_geo_block_update_nonexistent(self):
        resp = self.client.post(
            "/ops/geo-block/update/99999/",
            {"country_code": "US", "action": "allow"},
        )
        self.assert_no_500(resp, "/ops/geo-block/update/99999/")
        self.assertEqual(resp.status_code, 404)

    def test_internal_ip_create(self):
        resp = self.client.post(
            "/ops/ip-reputation/internal-ip/create/",
            {"ip_address": "10.0.0.1", "list_type": "allow", "reason": "Test"},
        )
        self.assert_no_500(resp, "/ops/ip-reputation/internal-ip/create/")

    def test_internal_ip_create_invalid_ip(self):
        resp = self.client.post(
            "/ops/ip-reputation/internal-ip/create/",
            {"ip_address": "not-an-ip", "list_type": "allow"},
        )
        self.assert_no_500(resp, "/ops/ip-reputation/internal-ip/create/")
        self.assertEqual(resp.status_code, 400)

    def test_internal_ip_delete_nonexistent(self):
        resp = self.client.post("/ops/ip-reputation/internal-ip/delete/99999/")
        self.assert_no_500(resp, "/ops/ip-reputation/internal-ip/delete/99999/")
        self.assertIn(resp.status_code, [404])

    def test_jsonschema_create(self):
        resp = self.client.post(
            "/ops/json-schema/create/",
            {
                "name": "Test Schema",
                "endpoint": "/api/test",
                "method": "POST",
                "schema_json": '{"type": "object"}',
                "description": "Test",
                "rollout_mode": "monitor",
                "version": "v1",
            },
        )
        self.assert_no_500(resp, "/ops/json-schema/create/")

    def test_jsonschema_create_invalid_json(self):
        resp = self.client.post(
            "/ops/json-schema/create/",
            {
                "name": "Bad Schema",
                "endpoint": "/api/bad",
                "schema_json": "not-valid-json{{{",
            },
        )
        self.assert_no_500(resp, "/ops/json-schema/create/")
        self.assertEqual(resp.status_code, 400)

    def test_asn_update_score(self):
        resp = self.client.post(
            "/ops/asn/asn-update-score/",
            {"asn_number": "AS12345", "name": "Test ASN", "score": "75"},
        )
        self.assert_no_500(resp, "/ops/asn/asn-update-score/")
        # Should redirect after POST
        self.assertIn(resp.status_code, [301, 302])


# ===========================================================================
# 8. Alert Operations
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestAlertOperations(DashboardSmokeTestBase):
    """Test alert dashboard operations."""

    def setUp(self):
        super().setUp()
        self.login_superuser()

    def test_alert_dashboard_with_filters(self):
        resp = self.client.get("/ops/alerts/?q=test&severity=high")
        self.assert_no_500(resp, "/ops/alerts/?q=test&severity=high")

    def test_alert_chart_data_periods(self):
        for period in ["1d", "7d", "30d", "all"]:
            with self.subTest(period=period):
                resp = self.client.get(f"/ops/alerts/alert_chart_data/?period={period}")
                self.assert_no_500(resp, f"/ops/alerts/alert_chart_data/?period={period}")
                data = resp.json()
                self.assertIn("labels", data)
                self.assertIn("data", data)

    def test_resolve_nonexistent_alert(self):
        """Resolving a non-existent alert should return 404, not 500."""
        resp = self.client.post("/ops/alerts/resolve/99999/")
        self.assert_no_500(resp, "/ops/alerts/resolve/99999/")
        self.assertEqual(resp.status_code, 404)


# ===========================================================================
# 9. Blocking Operations
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestBlockingOperations(DashboardSmokeTestBase):
    """Test blocking dashboard operations."""

    def setUp(self):
        super().setUp()
        self.login_superuser()

    def test_blocked_ip_dashboard_with_filters(self):
        resp = self.client.get("/ops/blocked-ips/?q=192.168&severity=high&status=active")
        self.assert_no_500(resp, "/ops/blocked-ips/?q=192.168&severity=high&status=active")

    @patch("blocking.services.BlockingService.block_ip")
    def test_block_ip_manual(self, mock_block):
        mock_block.return_value = MagicMock()
        resp = self.client.post("/ops/blocked-ips/block/10.0.0.1/", follow=False)
        self.assert_no_500(resp, "/ops/blocked-ips/block/10.0.0.1/")

    @patch("blocking.services.BlockingService.unblock_ip")
    def test_unblock_ip(self, mock_unblock):
        mock_unblock.return_value = True
        resp = self.client.post("/ops/blocked-ips/unblock/10.0.0.1/", follow=False)
        self.assert_no_500(resp, "/ops/blocked-ips/unblock/10.0.0.1/")


# ===========================================================================
# 10. MiniFW Service Control & POST Endpoints
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestMiniFWServiceControl(DashboardSmokeTestBase):
    """Test MiniFW POST-based control endpoints."""

    def setUp(self):
        super().setUp()
        self.login_superuser()
        self._patches = []
        for target, return_value in _mock_minifw_services().items():
            p = patch(target, return_value=return_value)
            p.start()
            self._patches.append(p)

    def tearDown(self):
        for p in self._patches:
            p.stop()
        super().tearDown()

    @patch("minifw.services.MiniFWService.restart", return_value=True)
    def test_service_restart(self, _mock):
        resp = self.client.post(
            "/ops/minifw/service/control/",
            {"action": "restart"},
            HTTP_REFERER="/ops/minifw/dashboard/",
        )
        self.assert_no_500(resp, "/ops/minifw/service/control/")

    @patch("minifw.services.MiniFWService.stop", return_value=True)
    def test_service_stop(self, _mock):
        resp = self.client.post(
            "/ops/minifw/service/control/",
            {"action": "stop"},
            HTTP_REFERER="/ops/minifw/dashboard/",
        )
        self.assert_no_500(resp, "/ops/minifw/service/control/")

    @patch("minifw.services.MiniFWService.start", return_value=True)
    def test_service_start(self, _mock):
        resp = self.client.post(
            "/ops/minifw/service/control/",
            {"action": "start"},
            HTTP_REFERER="/ops/minifw/dashboard/",
        )
        self.assert_no_500(resp, "/ops/minifw/service/control/")


# ===========================================================================
# 11. Authentication Flow
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestAuthenticationFlow(DashboardSmokeTestBase):
    """Test login/logout/change-password flows."""

    def test_login_valid_superuser(self):
        resp = self.client.post(
            "/login/",
            {"username": "admin", "password": "TestPass123!"},
            follow=True,
        )
        self.assert_no_500(resp, "/login/")

    def test_login_invalid_credentials(self):
        resp = self.client.post(
            "/login/",
            {"username": "admin", "password": "wrongpassword"},
        )
        self.assert_no_500(resp, "/login/")

    def test_login_non_superuser(self):
        resp = self.client.post(
            "/login/",
            {"username": "viewer", "password": "TestPass123!"},
        )
        self.assert_no_500(resp, "/login/")

    def test_logout(self):
        self.login_superuser()
        resp = self.client.get("/logout/", follow=True)
        self.assert_no_500(resp, "/logout/")

    def test_change_password_get(self):
        self.login_superuser()
        resp = self.client.get("/change-password/")
        self.assert_no_500(resp, "/change-password/")

    def test_home_authenticated_superuser(self):
        self.login_superuser()
        resp = self.client.get("/", follow=False)
        self.assert_no_500(resp, "/")
        self.assertIn(resp.status_code, [301, 302])


# ===========================================================================
# 12. Edge Cases & Error Handling
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestEdgeCases(DashboardSmokeTestBase):
    """Test edge cases that might trigger 500 errors."""

    def setUp(self):
        super().setUp()
        self.login_superuser()

    def test_pagination_out_of_range(self):
        """Requesting page 99999 should not 500 (Django paginator handles it)."""
        resp = self.client.get("/ops/alerts/?page=99999")
        self.assert_no_500(resp, "/ops/alerts/?page=99999")

    def test_pagination_invalid_string(self):
        """Non-numeric page param should not 500."""
        resp = self.client.get("/ops/alerts/?page=abc")
        self.assert_no_500(resp, "/ops/alerts/?page=abc")

    def test_requestlog_filters(self):
        resp = self.client.get("/ops/requestlogs/?q=10.0.0&action=block")
        self.assert_no_500(resp, "/ops/requestlogs/?q=10.0.0&action=block")

    def test_blocked_ips_empty_filters(self):
        resp = self.client.get("/ops/blocked-ips/?q=&severity=&status=")
        self.assert_no_500(resp, "/ops/blocked-ips/?q=&severity=&status=")

    def test_asn_checker_search(self):
        resp = self.client.get("/ops/asn-checker/?search=1.1.1.1")
        self.assert_no_500(resp, "/ops/asn-checker/?search=1.1.1.1")

    def test_asn_config_search(self):
        resp = self.client.get("/ops/asn-config/?cfg_search=AS12345")
        self.assert_no_500(resp, "/ops/asn-config/?cfg_search=AS12345")

    def test_json_schema_delete_nonexistent(self):
        resp = self.client.post("/ops/json-schema/delete/99999/")
        self.assert_no_500(resp, "/ops/json-schema/delete/99999/")
        self.assertEqual(resp.status_code, 404)

    def test_json_schema_update_nonexistent(self):
        resp = self.client.post(
            "/ops/json-schema/update/99999/",
            {"name": "x", "endpoint": "/x", "schema_json": "{}"},
        )
        self.assert_no_500(resp, "/ops/json-schema/update/99999/")
        self.assertEqual(resp.status_code, 404)

    def test_json_schema_toggle_nonexistent(self):
        resp = self.client.post("/ops/json-schema/toggle/99999/")
        self.assert_no_500(resp, "/ops/json-schema/toggle/99999/")
        self.assertEqual(resp.status_code, 404)

    def test_method_not_allowed_on_post_endpoints(self):
        """GET on POST-only endpoints should not 500."""
        post_only_urls = [
            "/ops/geo-block/create/",
            "/ops/ip-reputation/internal-ip/create/",
        ]
        for url in post_only_urls:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assert_no_500(resp, url)
                self.assertIn(resp.status_code, [405, 400, 302, 301])


# ===========================================================================
# 13. MiniFW User Management API
# ===========================================================================

@override_settings(
    MIDDLEWARE=MIDDLEWARE_FOR_TESTS,
    DATABASES=TEST_DATABASES,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestMiniFWUserManagementAPI(DashboardSmokeTestBase):
    """Test MiniFW user management CRUD API endpoints."""

    def setUp(self):
        super().setUp()
        self.login_superuser()
        self._patches = []
        for target, return_value in _mock_minifw_services().items():
            p = patch(target, return_value=return_value)
            p.start()
            self._patches.append(p)

    def tearDown(self):
        for p in self._patches:
            p.stop()
        super().tearDown()

    def test_create_user_missing_fields(self):
        """POST with missing fields should return 400, not 500."""
        resp = self.client.post(
            "/ops/minifw/api/users/create/",
            "{}",
            content_type="application/json",
        )
        self.assert_no_500(resp, "/ops/minifw/api/users/create/")
        self.assertEqual(resp.status_code, 400)

    def test_create_user_invalid_json(self):
        """POST with malformed JSON should return 400, not 500."""
        resp = self.client.post(
            "/ops/minifw/api/users/create/",
            "not json",
            content_type="application/json",
        )
        self.assert_no_500(resp, "/ops/minifw/api/users/create/")
        self.assertEqual(resp.status_code, 400)

    def test_update_nonexistent_user(self):
        """PUT to non-existent user should return 404, not 500."""
        resp = self.client.put(
            "/ops/minifw/api/users/99999/",
            '{"role": "VIEWER"}',
            content_type="application/json",
        )
        self.assert_no_500(resp, "/ops/minifw/api/users/99999/")
        self.assertIn(resp.status_code, [404])

    def test_change_password_too_short(self):
        """Short password should return 400, not 500."""
        resp = self.client.put(
            f"/ops/minifw/api/users/{self.regular_user.id}/password/",
            '{"password": "short"}',
            content_type="application/json",
        )
        self.assert_no_500(resp, "/ops/minifw/api/users/.../password/")
        self.assertEqual(resp.status_code, 400)

    def test_delete_nonexistent_user(self):
        """DELETE non-existent user should return 404, not 500."""
        resp = self.client.delete("/ops/minifw/api/users/99999/delete/")
        self.assert_no_500(resp, "/ops/minifw/api/users/99999/delete/")
        self.assertIn(resp.status_code, [404])

    def test_delete_self(self):
        """Deleting own account should return 400, not 500."""
        resp = self.client.delete(
            f"/ops/minifw/api/users/{self.superuser.id}/delete/"
        )
        self.assert_no_500(resp, "/ops/minifw/api/users/self/delete/")
        self.assertEqual(resp.status_code, 400)
