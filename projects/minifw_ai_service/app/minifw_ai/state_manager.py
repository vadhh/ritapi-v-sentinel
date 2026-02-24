"""Dynamic State Transition System for MiniFW-AI.

Manages automatic transitions between BASELINE_PROTECTION (hard gates only)
and AI_ENHANCED_PROTECTION (hard gates + MLP + YARA) based on DNS telemetry
health. Hard gates remain active in all states.

TODO items: 4.1 (upgrade logic) and 4.2 (downgrade safety).
"""

from __future__ import annotations

import json
import logging
import os
import time
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class ProtectionState(Enum):
    """Protection states for MiniFW-AI."""

    BASELINE_PROTECTION = "BASELINE_PROTECTION"
    AI_ENHANCED_PROTECTION = "AI_ENHANCED_PROTECTION"


class TelemetryHealth:
    """Tracks DNS telemetry health via event flow monitoring.

    Uses consecutive healthy/unhealthy check counts to determine
    when state transitions should occur, avoiding flapping.
    """

    def __init__(
        self,
        check_interval: int = 30,
        upgrade_threshold: int = 3,
        downgrade_threshold: int = 2,
        telemetry_timeout: int = 60,
    ):
        self.check_interval = check_interval
        self.upgrade_threshold = upgrade_threshold
        self.downgrade_threshold = downgrade_threshold
        self.telemetry_timeout = telemetry_timeout

        self.last_event_time: float = 0.0
        self.event_count: int = 0
        self.last_check_time: float = 0.0
        self.consecutive_healthy: int = 0
        self.consecutive_unhealthy: int = 0

    def record_dns_event(self) -> None:
        """Record receipt of a real DNS event."""
        self.last_event_time = time.monotonic()
        self.event_count += 1

    def check_health(self) -> bool:
        """Check if DNS telemetry is healthy.

        Throttled to run at most once per check_interval seconds.
        Returns True if DNS events were received within telemetry_timeout.
        """
        now = time.monotonic()
        if self.last_check_time and (now - self.last_check_time) < self.check_interval:
            # Not time to check yet; return last known state
            return self.consecutive_healthy > 0

        self.last_check_time = now

        healthy = (
            self.last_event_time > 0
            and (now - self.last_event_time) < self.telemetry_timeout
        )

        if healthy:
            self.consecutive_healthy += 1
            self.consecutive_unhealthy = 0
        else:
            self.consecutive_unhealthy += 1
            self.consecutive_healthy = 0

        return healthy

    def ready_for_upgrade(self) -> bool:
        """True when telemetry has been healthy long enough to upgrade."""
        return self.consecutive_healthy >= self.upgrade_threshold

    def requires_downgrade(self) -> bool:
        """True when telemetry has been unhealthy long enough to downgrade."""
        return self.consecutive_unhealthy >= self.downgrade_threshold


class StateManager:
    """Orchestrates protection state transitions.

    Monitors DNS telemetry health and triggers transitions between
    BASELINE_PROTECTION and AI_ENHANCED_PROTECTION. Hard gates remain
    active regardless of state.
    """

    def __init__(
        self,
        initial_state: ProtectionState,
        state_file_path: str = "/var/log/ritapi/deployment_state.json",
    ):
        self._state = initial_state
        self._state_file = Path(state_file_path)

        # Read config from env with safe defaults (no new mandatory vars)
        check_interval = _safe_env_int("MINIFW_STATE_CHECK_INTERVAL", 30)
        upgrade_threshold = _safe_env_int("MINIFW_STATE_UPGRADE_THRESHOLD", 3)
        downgrade_threshold = _safe_env_int("MINIFW_STATE_DOWNGRADE_THRESHOLD", 2)
        telemetry_timeout = _safe_env_int("MINIFW_TELEMETRY_TIMEOUT", 60)

        self._health = TelemetryHealth(
            check_interval=check_interval,
            upgrade_threshold=upgrade_threshold,
            downgrade_threshold=downgrade_threshold,
            telemetry_timeout=telemetry_timeout,
        )

        # Try to load existing state from file
        self._load_existing_state()

    def _load_existing_state(self) -> None:
        """Load state from deployment_state.json if it exists."""
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                saved_state = data.get("current_protection_state")
                if saved_state:
                    for ps in ProtectionState:
                        if ps.value == saved_state:
                            self._state = ps
                            logging.info(
                                f"[STATE] Restored state from {self._state_file}: {ps.value}"
                            )
                            break
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logging.warning(f"[STATE] Could not load state file: {e}")

    def get_current_state(self) -> ProtectionState:
        return self._state

    def is_ai_enabled(self) -> bool:
        """True when current state is AI_ENHANCED_PROTECTION."""
        return self._state == ProtectionState.AI_ENHANCED_PROTECTION

    def record_dns_event(self, client_ip: str | None, domain: str | None) -> None:
        """Record a DNS event. Ignores None/None (degraded mode placeholders)."""
        if client_ip is not None and domain is not None:
            self._health.record_dns_event()

    def check_and_transition(self) -> tuple[bool, ProtectionState, str]:
        """Check telemetry health and trigger state transition if needed.

        Returns:
            (changed, new_state, reason) — changed is True only if a
            transition occurred this call.
        """
        self._health.check_health()

        if (
            self._state == ProtectionState.BASELINE_PROTECTION
            and self._health.ready_for_upgrade()
        ):
            reason = (
                f"telemetry_healthy_{self._health.upgrade_threshold}_consecutive_checks"
            )
            self._transition_to(
                ProtectionState.AI_ENHANCED_PROTECTION,
                trigger="telemetry_restored",
                reason=reason,
            )
            return True, self._state, reason

        if (
            self._state == ProtectionState.AI_ENHANCED_PROTECTION
            and self._health.requires_downgrade()
        ):
            reason = (
                f"telemetry_lost_{self._health.downgrade_threshold}_consecutive_checks"
            )
            self._transition_to(
                ProtectionState.BASELINE_PROTECTION,
                trigger="telemetry_lost",
                reason=reason,
            )
            return True, self._state, reason

        return False, self._state, ""

    def _transition_to(
        self, new_state: ProtectionState, trigger: str, reason: str
    ) -> None:
        old_state = self._state
        self._state = new_state

        logging.warning(
            f"[STATE_TRANSITION] {old_state.value} -> {new_state.value} | "
            f"trigger={trigger} | reason={reason}"
        )

        transition_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_state": old_state.value,
            "new_state": new_state.value,
            "trigger": trigger,
            "reason": reason,
            "operator_intervention": False,
        }
        self._update_deployment_state(transition_record)

    def _update_deployment_state(self, transition_record: dict[str, Any]) -> None:
        """Atomic write to deployment_state.json.

        Preserves existing installer-written fields. Appends to
        state_transitions array (capped at 100 entries).
        """
        data: dict[str, Any] = {}
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

        data["current_protection_state"] = self._state.value
        data["last_state_check"] = datetime.now(timezone.utc).isoformat()

        transitions = data.get("state_transitions", [])
        if not isinstance(transitions, list):
            transitions = []
        transitions.append(transition_record)
        # Cap at last 100 transitions
        data["state_transitions"] = transitions[-100:]

        # Atomic write: temp file + rename
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._state_file.parent), suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                os.replace(tmp_path, str(self._state_file))
            except BaseException:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as e:
            logging.warning(f"[STATE] Failed to write state file: {e}")

    def get_status_summary(self) -> dict[str, Any]:
        """Status summary for periodic logging."""
        return {
            "current_state": self._state.value,
            "ai_enabled": self.is_ai_enabled(),
            "telemetry_event_count": self._health.event_count,
            "consecutive_healthy_checks": self._health.consecutive_healthy,
            "consecutive_unhealthy_checks": self._health.consecutive_unhealthy,
        }


def _safe_env_int(name: str, default: int) -> int:
    """Read an integer from environment with fallback."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default
