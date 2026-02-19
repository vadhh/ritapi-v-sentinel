"""
Unit tests for the journald DNS collector.

All subprocess interactions are mocked — no real journalctl is needed.
"""

import itertools
import types
from unittest import mock

import pytest

from minifw_ai.collector_journald import (
    parse_resolved_log,
    stream_dns_events_journald,
)


# ---------------------------------------------------------------------------
# parse_resolved_log tests
# ---------------------------------------------------------------------------

class TestParseResolvedLog:
    def test_cache_hit(self):
        line = "Positive cache hit for example.com IN A"
        assert parse_resolved_log(line) == ("127.0.0.1", "example.com")

    def test_cache_hit_trailing_dot(self):
        line = "Positive cache hit for example.com. IN AAAA"
        assert parse_resolved_log(line) == ("127.0.0.1", "example.com")

    def test_lookup_rr(self):
        line = "Looking up RR for cdn.example.net IN A"
        assert parse_resolved_log(line) == ("127.0.0.1", "cdn.example.net")

    def test_transaction_line(self):
        line = "Transaction 3083 for <cdn.example.net IN AAAA> scope dns on eth0/*"
        assert parse_resolved_log(line) == ("127.0.0.1", "cdn.example.net")

    def test_transaction_line_regular_prefix(self):
        # systemd-resolved v255 emits "Regular transaction N for ..."
        line = "Regular transaction 3083 for <cdn.example.net IN AAAA> scope dns on ens33/*"
        assert parse_resolved_log(line) == ("127.0.0.1", "cdn.example.net")

    def test_cache_add(self):
        # systemd-resolved v255 uses two qualifier words: "unauthenticated non-confidential"
        line = "Added positive unauthenticated non-confidential cache entry for cdn.example.net IN A"
        assert parse_resolved_log(line) == ("127.0.0.1", "cdn.example.net")

    def test_cache_add_single_qualifier(self):
        # Older systemd versions use a single qualifier word
        line = "Added positive unauthenticated cache entry for cdn.example.net IN A"
        assert parse_resolved_log(line) == ("127.0.0.1", "cdn.example.net")

    def test_dnssec_validation(self):
        line = "DNSSEC validation succeeded for secure.example.org IN A"
        assert parse_resolved_log(line) == ("127.0.0.1", "secure.example.org")

    def test_dnsmasq_forwarded(self):
        line = "dnsmasq[123]: query[A] test.local from 192.168.1.5"
        assert parse_resolved_log(line) == ("192.168.1.5", "test.local")

    def test_non_dns_line(self):
        assert parse_resolved_log("Clock synchronized to time server") is None

    def test_empty_line(self):
        assert parse_resolved_log("") is None

    def test_none_safe(self):
        # parse_resolved_log checks for falsy input
        assert parse_resolved_log(None) is None


# ---------------------------------------------------------------------------
# stream_dns_events_journald tests
# ---------------------------------------------------------------------------

def _make_mock_proc(stdout_lines, returncode=0, stderr_text=""):
    """Create a mock Popen process with the given stdout lines."""
    proc = mock.MagicMock()
    proc.stdout = iter(stdout_lines)
    proc.stderr = mock.MagicMock()
    proc.stderr.read.return_value = stderr_text
    proc.pid = 12345
    proc.poll.return_value = returncode
    proc.terminate = mock.MagicMock()
    proc.wait = mock.MagicMock()
    return proc


class TestStreamDnsEventsJournald:
    @mock.patch("minifw_ai.collector_journald.subprocess.Popen")
    def test_yields_parsed_events(self, mock_popen):
        """DNS lines are parsed and yielded as (ip, domain) tuples."""
        lines = [
            "Positive cache hit for example.com IN A\n",
            "Some irrelevant log line\n",
            "Looking up RR for test.org IN A\n",
        ]
        mock_popen.return_value = _make_mock_proc(lines)

        gen = stream_dns_events_journald(unit="systemd-resolved")
        events = list(itertools.islice(gen, 2))

        assert events == [
            ("127.0.0.1", "example.com"),
            ("127.0.0.1", "test.org"),
        ]

    @mock.patch("minifw_ai.collector_journald.time.sleep")
    @mock.patch("minifw_ai.collector_journald.subprocess.Popen")
    def test_journalctl_not_found(self, mock_popen, mock_sleep):
        """FileNotFoundError yields (None, None) indefinitely."""
        mock_popen.side_effect = FileNotFoundError("journalctl not found")

        gen = stream_dns_events_journald()
        results = list(itertools.islice(gen, 3))

        assert results == [(None, None)] * 3

    @mock.patch("minifw_ai.collector_journald.time.sleep")
    @mock.patch("minifw_ai.collector_journald.subprocess.Popen")
    def test_permission_denied(self, mock_popen, mock_sleep):
        """PermissionError yields (None, None) indefinitely."""
        mock_popen.side_effect = PermissionError("not allowed")

        gen = stream_dns_events_journald()
        results = list(itertools.islice(gen, 3))

        assert results == [(None, None)] * 3

    @mock.patch("minifw_ai.collector_journald.time.sleep")
    @mock.patch("minifw_ai.collector_journald.subprocess.Popen")
    def test_reconnect_on_unexpected_exit(self, mock_popen, mock_sleep):
        """If journalctl exits, collector waits and restarts."""
        # First call: process exits immediately (empty stdout)
        proc1 = _make_mock_proc([], returncode=1)
        # Second call: yields one event then exhausts
        proc2 = _make_mock_proc(
            ["Positive cache hit for retry.com IN A\n"],
            returncode=0,
        )
        mock_popen.side_effect = [proc1, proc2]

        gen = stream_dns_events_journald()
        event = next(gen)

        assert event == ("127.0.0.1", "retry.com")
        # sleep was called for reconnect delay
        mock_sleep.assert_called_with(5)

    @mock.patch("minifw_ai.collector_journald.subprocess.Popen")
    def test_filters_noise(self, mock_popen):
        """Non-DNS lines are silently skipped."""
        lines = [
            "Started systemd-resolved service\n",
            "Clock synchronized\n",
            "Positive cache hit for real.event IN A\n",
            "Stopped systemd-resolved service\n",
        ]
        mock_popen.return_value = _make_mock_proc(lines)

        gen = stream_dns_events_journald()
        events = list(itertools.islice(gen, 1))

        assert events == [("127.0.0.1", "real.event")]

    @mock.patch("minifw_ai.collector_journald.time.sleep")
    @mock.patch("minifw_ai.collector_journald.subprocess.Popen")
    def test_stderr_permission_falls_back(self, mock_popen, mock_sleep):
        """If stderr contains 'permission', collector enters permanent fallback."""
        proc = _make_mock_proc([], returncode=1, stderr_text="Failed to open journal: Permission denied")
        mock_popen.return_value = proc

        gen = stream_dns_events_journald()
        results = list(itertools.islice(gen, 3))

        assert results == [(None, None)] * 3

    @mock.patch("minifw_ai.collector_journald.subprocess.Popen")
    def test_custom_unit(self, mock_popen):
        """Custom unit name is passed to journalctl."""
        mock_popen.return_value = _make_mock_proc(
            ["Positive cache hit for test.com IN A\n"]
        )

        gen = stream_dns_events_journald(unit="dnsmasq")
        next(gen)

        call_args = mock_popen.call_args[0][0]
        assert "-u" in call_args
        unit_idx = call_args.index("-u")
        assert call_args[unit_idx + 1] == "dnsmasq"
