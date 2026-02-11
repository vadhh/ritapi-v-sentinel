import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, Client

from .services import DeploymentStateService


class DeploymentStateServiceTest(TestCase):
    """Unit tests for DeploymentStateService."""

    def _write_state_file(self, tmpdir, data):
        path = os.path.join(tmpdir, 'deployment_state.json')
        with open(path, 'w') as f:
            json.dump(data, f)
        return path

    def test_get_state_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_state_file(tmpdir, {
                'current_protection_state': 'BASELINE_PROTECTION',
            })
            with patch.object(DeploymentStateService, 'STATE_FILE', path):
                state = DeploymentStateService.get_state()
        self.assertEqual(state['protection_state'], 'BASELINE_PROTECTION')
        self.assertFalse(state['ai_enabled'])
        self.assertFalse(state['service_unavailable'])

    def test_get_state_enhanced(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_state_file(tmpdir, {
                'current_protection_state': 'AI_ENHANCED_PROTECTION',
            })
            with patch.object(DeploymentStateService, 'STATE_FILE', path):
                state = DeploymentStateService.get_state()
        self.assertEqual(state['protection_state'], 'AI_ENHANCED_PROTECTION')
        self.assertTrue(state['ai_enabled'])
        self.assertFalse(state['service_unavailable'])

    def test_get_state_missing_file(self):
        with patch.object(DeploymentStateService, 'STATE_FILE', '/nonexistent/path.json'):
            state = DeploymentStateService.get_state()
        self.assertEqual(state['protection_state'], 'UNAVAILABLE')
        self.assertFalse(state['ai_enabled'])
        self.assertTrue(state['service_unavailable'])
        self.assertIn('not found', state['unavailable_reason'])

    def test_get_state_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'deployment_state.json')
            with open(path, 'w') as f:
                f.write('{invalid json!!!')
            with patch.object(DeploymentStateService, 'STATE_FILE', path):
                state = DeploymentStateService.get_state()
        self.assertEqual(state['protection_state'], 'UNAVAILABLE')
        self.assertTrue(state['service_unavailable'])

    def test_get_state_fallback_status_field(self):
        """Falls back to 'status' key when 'current_protection_state' missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_state_file(tmpdir, {
                'status': 'AI_ENHANCED_PROTECTION',
            })
            with patch.object(DeploymentStateService, 'STATE_FILE', path):
                state = DeploymentStateService.get_state()
        self.assertTrue(state['ai_enabled'])

    def test_filter_ai_reasons(self):
        reasons = ['feed_deny', 'mlp_anomaly', 'burst_flood', 'yara_match', 'mlp_high']
        filtered = DeploymentStateService.filter_ai_reasons(reasons)
        self.assertEqual(filtered, ['feed_deny', 'burst_flood'])

    def test_filter_ai_reasons_non_list(self):
        self.assertEqual(DeploymentStateService.filter_ai_reasons('string'), 'string')

    def test_filter_event_baseline_removes_score(self):
        event = {
            'ts': '2026-02-11T10:00:00',
            'client_ip': '10.0.0.1',
            'domain': 'example.com',
            'action': 'block',
            'score': 85,
            'segment': 'office',
            'reasons': ['feed_deny', 'mlp_anomaly'],
        }
        filtered = DeploymentStateService.filter_event_for_baseline(event)
        self.assertNotIn('score', filtered)
        self.assertEqual(filtered['reasons'], ['feed_deny'])
        self.assertEqual(filtered['client_ip'], '10.0.0.1')

    def test_filter_stats_baseline_hides_monitored(self):
        stats = {
            'total_events': 100,
            'blocked': 40,
            'monitored': 20,
            'allowed': 40,
            'top_blocked_ips': {'10.0.0.1': 5},
            'top_blocked_domains': {'bad.com': 3},
            'by_segment': {
                'office': {'blocked': 10, 'monitored': 5, 'allowed': 15},
                'lab': {'blocked': 2, 'monitored': 1, 'allowed': 8},
            },
        }
        filtered = DeploymentStateService.filter_stats_for_baseline(stats)
        self.assertIsNone(filtered['monitored'])
        self.assertNotIn('monitored', filtered['by_segment']['office'])
        self.assertNotIn('monitored', filtered['by_segment']['lab'])
        # Other stats preserved
        self.assertEqual(filtered['blocked'], 40)
        self.assertEqual(filtered['top_blocked_ips'], {'10.0.0.1': 5})


def _mock_deployment_state(ai_enabled):
    """Helper to create a mock deployment state."""
    if ai_enabled:
        return {
            'protection_state': 'AI_ENHANCED_PROTECTION',
            'ai_enabled': True,
            'last_state_check': None,
            'service_unavailable': False,
            'unavailable_reason': None,
            'raw': {},
        }
    return {
        'protection_state': 'BASELINE_PROTECTION',
        'ai_enabled': False,
        'last_state_check': None,
        'service_unavailable': False,
        'unavailable_reason': None,
        'raw': {},
    }


MOCK_STATS = {
    'total_events': 10,
    'blocked': 4,
    'monitored': 3,
    'allowed': 3,
    'top_blocked_ips': {'10.0.0.1': 2},
    'top_blocked_domains': {'bad.com': 1},
    'by_segment': {
        'office': {'blocked': 2, 'monitored': 1, 'allowed': 2},
    },
}

MOCK_EVENTS = [
    {
        'ts': '2026-02-11T10:00:00',
        'client_ip': '10.0.0.1',
        'domain': 'bad.com',
        'action': 'block',
        'score': 85,
        'segment': 'office',
        'reasons': ['feed_deny', 'mlp_anomaly'],
    },
]


class DashboardViewBaselineTest(TestCase):
    """Test dashboard view hides AI metrics in BASELINE mode."""

    def setUp(self):
        from .models import UserProfile
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        UserProfile.objects.create(user=self.user, role='ADMIN', sector='ESTABLISHMENT')
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    @patch('minifw.views.DeploymentStateService.get_state',
           return_value=_mock_deployment_state(False))
    @patch('minifw.views.MiniFWStats.get_stats', return_value=MOCK_STATS.copy())
    @patch('minifw.views.MiniFWStats.get_recent_events', return_value=MOCK_EVENTS.copy())
    @patch('minifw.views.MiniFWIPSet.list_blocked_ips', return_value=[])
    @patch('minifw.views.MiniFWService.get_status',
           return_value={'active': True, 'enabled': True, 'status': 'running'})
    @patch('minifw.views.SectorLock.get_sector', return_value='establishment')
    @patch('minifw.views.SectorLock.get_description', return_value='Standard')
    def test_dashboard_baseline_hides_monitored(self, *mocks):
        response = self.client.get('/ops/minifw/dashboard/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('Monitored', content)
        self.assertNotIn('Score', content)
        self.assertIn('Baseline Protection', content)

    @patch('minifw.views.DeploymentStateService.get_state',
           return_value=_mock_deployment_state(True))
    @patch('minifw.views.MiniFWStats.get_stats', return_value=MOCK_STATS.copy())
    @patch('minifw.views.MiniFWStats.get_recent_events', return_value=MOCK_EVENTS.copy())
    @patch('minifw.views.MiniFWIPSet.list_blocked_ips', return_value=[])
    @patch('minifw.views.MiniFWService.get_status',
           return_value={'active': True, 'enabled': True, 'status': 'running'})
    @patch('minifw.views.SectorLock.get_sector', return_value='establishment')
    @patch('minifw.views.SectorLock.get_description', return_value='Standard')
    def test_dashboard_enhanced_shows_all(self, *mocks):
        response = self.client.get('/ops/minifw/dashboard/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Monitored', content)
        self.assertIn('Score', content)
        self.assertIn('AI-Enhanced Protection', content)


class ApiStatsBaselineTest(TestCase):
    """Test API endpoints filter for baseline mode."""

    def setUp(self):
        from .models import UserProfile
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        UserProfile.objects.create(user=self.user, role='ADMIN', sector='ESTABLISHMENT')
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    @patch('minifw.views.DeploymentStateService.get_state',
           return_value=_mock_deployment_state(False))
    @patch('minifw.views.MiniFWStats.get_stats', return_value=MOCK_STATS.copy())
    def test_api_stats_baseline_filtered(self, *mocks):
        response = self.client.get('/ops/minifw/api/stats/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsNone(data['monitored'])

    @patch('minifw.views.DeploymentStateService.get_state',
           return_value=_mock_deployment_state(False))
    @patch('minifw.views.MiniFWStats.get_recent_events', return_value=MOCK_EVENTS.copy())
    def test_api_events_baseline_no_score(self, *mocks):
        response = self.client.get('/ops/minifw/api/events/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        for event in data['events']:
            self.assertNotIn('score', event)
            for reason in event.get('reasons', []):
                self.assertFalse(reason.startswith('mlp_'))
                self.assertFalse(reason.startswith('yara_'))
