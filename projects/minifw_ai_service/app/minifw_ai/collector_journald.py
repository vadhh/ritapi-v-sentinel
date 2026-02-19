"""
journald DNS collector for systemd-resolved environments.

Streams DNS query events from systemd-resolved via journalctl subprocess.
No additional Python dependencies required (uses subprocess.Popen).

Privilege Requirements (TODO 5.2):
    The process running this collector must have read access to the
    systemd journal. This is achieved by ONE of:
      - Running as root (typical for systemd services)
      - Adding the service user to the 'systemd-journal' group:
            sudo usermod -aG systemd-journal www-data
      - Setting ACLs on /var/log/journal/ or /run/log/journal/

    If neither condition is met, journalctl returns a permission error
    and the collector falls back to yielding (None, None) indefinitely,
    which keeps the service in BASELINE_PROTECTION mode.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from typing import Iterator, Optional, Tuple

# --- Patterns for systemd-resolved log lines (verified against systemd v245+) ---

# "Looking up RR for example.com IN A"  — emitted for every new lookup
_RE_LOOKUP = re.compile(
    r"Looking up RR for\s+(\S+)\s+IN\s+", re.IGNORECASE
)

# "Transaction 3083 for <example.com IN AAAA> scope dns on eth0/*"
_RE_TRANSACTION = re.compile(
    r"Transaction\s+\d+\s+for\s+<(\S+)\s+IN\s+", re.IGNORECASE
)

# "Added positive unauthenticated cache entry for example.com IN A"
# "Added positive authenticated cache entry for example.com IN AAAA"
_RE_CACHE_ADD = re.compile(
    r"Added positive\s+\S+\s+cache entry for\s+(\S+)\s+IN\s+", re.IGNORECASE
)

# "Positive cache hit for example.com IN A"  (present in some systemd versions)
_RE_CACHE_HIT = re.compile(
    r"Positive cache hit for\s+(\S+)\s+IN\s+", re.IGNORECASE
)

# "DNSSEC validation succeeded for example.com IN A"
_RE_DNSSEC = re.compile(
    r"DNSSEC validation\s+\S+\s+for\s+(\S+)\s+IN\s+", re.IGNORECASE
)

# dnsmasq-style: "query[A] example.com from 192.168.1.5"  (dnsmasq forwarding via resolved)
_RE_DNSMASQ_QUERY = re.compile(
    r"query\[\S+\]\s+(\S+)\s+from\s+(\S+)"
)

_RECONNECT_DELAY = 5  # seconds before restarting journalctl after unexpected exit


def parse_resolved_log(line: str) -> Optional[Tuple[str, str]]:
    """
    Parse a systemd-resolved log line for DNS query information.

    Returns (client_ip, domain) on match, None otherwise.
    For systemd-resolved, client_ip defaults to '127.0.0.1' because
    resolved acts as the local stub resolver.
    """
    if not line:
        return None

    # Try dnsmasq-style first (most specific, has client IP)
    m = _RE_DNSMASQ_QUERY.search(line)
    if m:
        return m.group(2), m.group(1)

    # systemd-resolved patterns (client is always localhost stub resolver)
    # Priority: lookup > transaction > cache add > cache hit > dnssec
    for pattern in (_RE_LOOKUP, _RE_TRANSACTION, _RE_CACHE_ADD, _RE_CACHE_HIT, _RE_DNSSEC):
        m = pattern.search(line)
        if m:
            domain = m.group(1).rstrip(".")
            if domain:
                return "127.0.0.1", domain

    return None


def stream_dns_events_journald(
    unit: str = "systemd-resolved",
) -> Iterator[Tuple[str, str]]:
    """
    Stream DNS events from journald by tailing a systemd unit's logs.

    Spawns ``journalctl -u <unit> -f -o cat --no-pager -n 0`` and parses
    each line for DNS queries.

    Fail-open guarantees:
        - journalctl not found  -> logs warning, yields (None, None) forever
        - Permission denied     -> logs warning, yields (None, None) forever
        - Unexpected exit       -> waits 5s, restarts subprocess
    """
    cmd = [
        "journalctl",
        "-u", unit,
        "-f",           # follow (like tail -f)
        "-o", "cat",    # plain message text, no metadata prefix
        "--no-pager",
        "-n", "0",      # skip existing entries, only new ones
    ]

    while True:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # line-buffered
            )
        except FileNotFoundError:
            logging.warning(
                "[DNS_COLLECTOR] journalctl not found — "
                "journald collector unavailable, falling back to BASELINE_PROTECTION"
            )
            while True:
                yield None, None
                time.sleep(1)
        except PermissionError:
            logging.warning(
                "[DNS_COLLECTOR] Permission denied running journalctl — "
                "add service user to systemd-journal group. "
                "Falling back to BASELINE_PROTECTION"
            )
            while True:
                yield None, None
                time.sleep(1)
        except Exception as e:
            logging.warning(
                f"[DNS_COLLECTOR] Failed to start journalctl: {e} — "
                "falling back to BASELINE_PROTECTION"
            )
            while True:
                yield None, None
                time.sleep(1)

        logging.info(
            f"[DNS_COLLECTOR] journalctl subprocess started (unit={unit}, pid={proc.pid})"
        )

        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                evt = parse_resolved_log(line)
                if evt:
                    yield evt
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            return
        except Exception as e:
            logging.warning(f"[DNS_COLLECTOR] Error reading journalctl output: {e}")

        # Process exited unexpectedly — clean up and reconnect
        ret = proc.poll()
        if ret is None:
            proc.terminate()
            proc.wait()

        # Check stderr for permission issues
        try:
            stderr_out = proc.stderr.read()
            if stderr_out:
                logging.warning(f"[DNS_COLLECTOR] journalctl stderr: {stderr_out.strip()}")
                if "permission" in stderr_out.lower() or "access" in stderr_out.lower():
                    logging.warning(
                        "[DNS_COLLECTOR] journalctl access denied — "
                        "add service user to systemd-journal group. "
                        "Falling back to BASELINE_PROTECTION"
                    )
                    while True:
                        yield None, None
                        time.sleep(1)
        except Exception:
            pass

        logging.warning(
            f"[DNS_COLLECTOR] journalctl exited (code={ret}), "
            f"reconnecting in {_RECONNECT_DELAY}s..."
        )
        time.sleep(_RECONNECT_DELAY)
