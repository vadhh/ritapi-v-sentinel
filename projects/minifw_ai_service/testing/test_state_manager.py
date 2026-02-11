"""Unit tests for the Dynamic State Transition System (TODO 4.1/4.2)."""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

# Ensure GAMBLING_ONLY is set before importing minifw modules
os.environ.setdefault("GAMBLING_ONLY", "1")

from minifw_ai.state_manager import (
    ProtectionState,
    StateManager,
    TelemetryHealth,
)


# ---------------------------------------------------------------------------
# TelemetryHealth tests
# ---------------------------------------------------------------------------

class TestTelemetryHealth:
    def test_initial_state(self):
        h = TelemetryHealth()
        assert h.event_count == 0
        assert h.consecutive_healthy == 0
        assert h.consecutive_unhealthy == 0

    def test_record_dns_event_updates_counters(self):
        h = TelemetryHealth()
        h.record_dns_event()
        assert h.event_count == 1
        assert h.last_event_time > 0

    def test_check_health_healthy(self):
        h = TelemetryHealth(check_interval=0, telemetry_timeout=60)
        h.record_dns_event()
        assert h.check_health() is True
        assert h.consecutive_healthy == 1
        assert h.consecutive_unhealthy == 0

    def test_check_health_unhealthy_no_events(self):
        h = TelemetryHealth(check_interval=0, telemetry_timeout=60)
        # No events recorded
        assert h.check_health() is False
        assert h.consecutive_unhealthy == 1
        assert h.consecutive_healthy == 0

    def test_check_health_unhealthy_stale_events(self):
        h = TelemetryHealth(check_interval=0, telemetry_timeout=5)
        h.record_dns_event()
        # Simulate time passing beyond timeout
        h.last_event_time = time.monotonic() - 10
        assert h.check_health() is False
        assert h.consecutive_unhealthy == 1

    def test_upgrade_threshold(self):
        h = TelemetryHealth(check_interval=0, upgrade_threshold=3)
        h.record_dns_event()
        for _ in range(2):
            h.check_health()
            assert h.ready_for_upgrade() is False
        h.check_health()
        assert h.ready_for_upgrade() is True

    def test_downgrade_threshold(self):
        h = TelemetryHealth(check_interval=0, downgrade_threshold=2)
        h.check_health()
        assert h.requires_downgrade() is False
        h.check_health()
        assert h.requires_downgrade() is True

    def test_counter_reset_on_flip(self):
        h = TelemetryHealth(check_interval=0, telemetry_timeout=60)
        # Build up unhealthy
        h.check_health()
        h.check_health()
        assert h.consecutive_unhealthy == 2

        # Now record event → healthy check resets unhealthy
        h.record_dns_event()
        h.check_health()
        assert h.consecutive_healthy == 1
        assert h.consecutive_unhealthy == 0

    def test_throttle_skips_early_checks(self):
        h = TelemetryHealth(check_interval=9999, telemetry_timeout=60)
        h.record_dns_event()
        # Force first check
        h.last_check_time = 0
        h.check_health()
        assert h.consecutive_healthy == 1

        # Second call within interval should not increment
        h.check_health()
        assert h.consecutive_healthy == 1


# ---------------------------------------------------------------------------
# StateManager tests
# ---------------------------------------------------------------------------

class TestStateManager:
    @pytest.fixture
    def state_file(self, tmp_path):
        return str(tmp_path / "deployment_state.json")

    def _make_manager(self, state_file, initial=ProtectionState.BASELINE_PROTECTION):
        with mock.patch.dict(os.environ, {
            "MINIFW_STATE_CHECK_INTERVAL": "0",
            "MINIFW_STATE_UPGRADE_THRESHOLD": "3",
            "MINIFW_STATE_DOWNGRADE_THRESHOLD": "2",
            "MINIFW_TELEMETRY_TIMEOUT": "60",
        }):
            return StateManager(initial_state=initial, state_file_path=state_file)

    def test_initial_state(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        assert sm.get_current_state() == ProtectionState.BASELINE_PROTECTION
        assert sm.is_ai_enabled() is False

    def test_is_ai_enabled_enhanced(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.AI_ENHANCED_PROTECTION)
        assert sm.is_ai_enabled() is True

    def test_upgrade_transition(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        # Record DNS events to make telemetry healthy
        sm.record_dns_event("10.0.0.1", "example.com")

        # 3 checks needed for upgrade
        for i in range(3):
            changed, state, reason = sm.check_and_transition()
            if i < 2:
                assert changed is False
            else:
                assert changed is True
                assert state == ProtectionState.AI_ENHANCED_PROTECTION
                assert "telemetry_healthy" in reason

        assert sm.is_ai_enabled() is True

    def test_downgrade_transition(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.AI_ENHANCED_PROTECTION)
        # No DNS events → telemetry unhealthy

        # 2 checks needed for downgrade
        changed, _, _ = sm.check_and_transition()
        assert changed is False
        changed, state, reason = sm.check_and_transition()
        assert changed is True
        assert state == ProtectionState.BASELINE_PROTECTION
        assert "telemetry_lost" in reason
        assert sm.is_ai_enabled() is False

    def test_no_transition_in_steady_state(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.AI_ENHANCED_PROTECTION)
        sm.record_dns_event("10.0.0.1", "example.com")

        # Healthy checks when already enhanced should not trigger transition
        for _ in range(10):
            changed, state, _ = sm.check_and_transition()
            assert changed is False
            assert state == ProtectionState.AI_ENHANCED_PROTECTION

    def test_no_upgrade_when_already_enhanced(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.AI_ENHANCED_PROTECTION)
        sm.record_dns_event("10.0.0.1", "example.com")

        for _ in range(5):
            changed, _, _ = sm.check_and_transition()
            assert changed is False

    def test_no_downgrade_when_already_baseline(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        # No events → unhealthy but already baseline
        for _ in range(5):
            changed, _, _ = sm.check_and_transition()
            assert changed is False

    def test_record_dns_event_ignores_none(self, state_file):
        sm = self._make_manager(state_file)
        sm.record_dns_event(None, None)
        assert sm._health.event_count == 0

    def test_state_file_persistence(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        sm.record_dns_event("10.0.0.1", "example.com")

        # Trigger upgrade
        for _ in range(3):
            sm.check_and_transition()

        assert sm.get_current_state() == ProtectionState.AI_ENHANCED_PROTECTION

        # Verify state file written
        data = json.loads(Path(state_file).read_text())
        assert data["current_protection_state"] == "AI_ENHANCED_PROTECTION"
        assert len(data["state_transitions"]) == 1
        assert data["state_transitions"][0]["new_state"] == "AI_ENHANCED_PROTECTION"
        assert data["state_transitions"][0]["trigger"] == "telemetry_restored"
        assert data["state_transitions"][0]["operator_intervention"] is False

    def test_state_file_restored_on_init(self, state_file):
        # Write a state file first
        Path(state_file).write_text(json.dumps({
            "current_protection_state": "AI_ENHANCED_PROTECTION",
            "state_transitions": [],
        }))

        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        # Should restore to enhanced from file
        assert sm.get_current_state() == ProtectionState.AI_ENHANCED_PROTECTION

    def test_corrupt_state_file_handled(self, state_file):
        Path(state_file).write_text("NOT VALID JSON {{{")
        # Should not crash
        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        assert sm.get_current_state() == ProtectionState.BASELINE_PROTECTION

    def test_missing_state_file_handled(self, state_file):
        # File doesn't exist — should not crash
        sm = self._make_manager(state_file, ProtectionState.AI_ENHANCED_PROTECTION)
        assert sm.get_current_state() == ProtectionState.AI_ENHANCED_PROTECTION

    def test_state_file_preserves_existing_fields(self, state_file):
        # Simulate installer-written deployment_state.json
        installer_data = {
            "install_timestamp": "2026-02-10T00:00:00Z",
            "version": "1.0.0",
            "status": "AI_ENHANCED_PROTECTION",
        }
        Path(state_file).write_text(json.dumps(installer_data))

        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        sm.record_dns_event("10.0.0.1", "example.com")
        for _ in range(3):
            sm.check_and_transition()

        data = json.loads(Path(state_file).read_text())
        # New fields added
        assert data["current_protection_state"] == "AI_ENHANCED_PROTECTION"
        assert len(data["state_transitions"]) == 1
        # Existing installer fields preserved
        assert data["install_timestamp"] == "2026-02-10T00:00:00Z"
        assert data["version"] == "1.0.0"
        assert data["status"] == "AI_ENHANCED_PROTECTION"

    def test_state_transitions_capped_at_100(self, state_file):
        # Write a state file with 99 transitions
        Path(state_file).write_text(json.dumps({
            "state_transitions": [{"n": i} for i in range(99)],
        }))

        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        sm.record_dns_event("10.0.0.1", "example.com")
        for _ in range(3):
            sm.check_and_transition()

        data = json.loads(Path(state_file).read_text())
        assert len(data["state_transitions"]) == 100

    def test_get_status_summary(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)
        summary = sm.get_status_summary()
        assert summary["current_state"] == "BASELINE_PROTECTION"
        assert summary["ai_enabled"] is False
        assert summary["telemetry_event_count"] == 0

    def test_upgrade_then_downgrade_cycle(self, state_file):
        sm = self._make_manager(state_file, ProtectionState.BASELINE_PROTECTION)

        # Upgrade: record events + 3 healthy checks
        sm.record_dns_event("10.0.0.1", "example.com")
        for _ in range(3):
            sm.check_and_transition()
        assert sm.get_current_state() == ProtectionState.AI_ENHANCED_PROTECTION

        # Simulate telemetry loss
        sm._health.last_event_time = time.monotonic() - 120
        # Need 2 unhealthy checks
        for _ in range(2):
            sm.check_and_transition()
        assert sm.get_current_state() == ProtectionState.BASELINE_PROTECTION

        # Verify 2 transitions in state file
        data = json.loads(Path(state_file).read_text())
        assert len(data["state_transitions"]) == 2
        assert data["state_transitions"][0]["new_state"] == "AI_ENHANCED_PROTECTION"
        assert data["state_transitions"][1]["new_state"] == "BASELINE_PROTECTION"
