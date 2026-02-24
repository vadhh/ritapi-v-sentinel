from __future__ import annotations
import socket
from typing import Iterator, Tuple, Optional
import time
import os


def parse_dnsmasq(line: str) -> Optional[Tuple[str, str]]:
    if " query[" not in line or " from " not in line:
        return None
    try:
        # Expected format: dnsmasq[1]: query[A] somedomain.com from 1.2.3.4
        right = line.split(" query[", 1)[1]
        domain = right.split("] ", 1)[1].split(" ", 1)[0].strip()
        client_ip = line.rsplit(" from ", 1)[1].strip()
        return client_ip, domain
    except Exception:
        return None


def stream_dns_events_udp(
    port: int = 5514, bind_ip: str = "0.0.0.0"
) -> Iterator[Tuple[str, str]]:
    """
    Listens for DNS log lines via UDP syslog/netcat stream.
    Yields (client_ip, domain) tuples.
    If port is already in use, enters degraded mode and yields empty events indefinitely.
    CRITICAL: Never exits - runs forever even if port bind fails.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((bind_ip, port))
        print(f"[*] DNS Collector listening on UDP {bind_ip}:{port}")
    except PermissionError:
        print(f"[!] Warning: Cannot bind to UDP port {port} (permission denied).")
        print(
            "[BASELINE_PROTECTION] DNS UDP collection disabled, service continues with other functions."
        )
        # Yield empty events indefinitely - NEVER EXIT
        while True:
            time.sleep(10)
            yield None, None
    except OSError as e:
        if e.errno == 98:  # EADDRINUSE
            print(f"[!] Warning: UDP port {port} already in use (EADDRINUSE).")
            print(
                "[BASELINE_PROTECTION] DNS UDP collection disabled, service continues with other functions."
            )
        else:
            print(f"[!] Warning: Cannot bind to UDP port {port}: {e}")
            print(
                "[BASELINE_PROTECTION] DNS UDP collection disabled, service continues with other functions."
            )
        # Yield empty events indefinitely - NEVER EXIT
        while True:
            time.sleep(10)
            yield None, None

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            raw_text = data.decode("utf-8", errors="replace")
            # print(f"[DEBUG] Received raw UDP: {raw_text!r}")

            # Netcat might batch lines, so we split them
            for line in raw_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                evt = parse_dnsmasq(line)
                if evt:
                    yield evt
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[!] UDP Socket error: {e}")


def stream_dns_events_file(log_path: str) -> Iterator[Tuple[str, str]]:
    """
    Tails a dnsmasq log file and yields (client_ip, domain) tuples.
    If log file is not found, enters degraded mode and waits indefinitely.
    CRITICAL: Never exits - runs forever in wait/retry mode.
    """
    if not os.path.exists(log_path):
        print(f"[!] Warning: DNS log file not found at {log_path}.")
        print(
            "[BASELINE_PROTECTION] Service will continue monitoring for file creation..."
        )
        print(
            "[BASELINE_PROTECTION] Other security functions remain active (Fail-Closed)"
        )
        # Wait indefinitely for file to appear - NEVER EXIT
        while not os.path.exists(log_path):
            time.sleep(10)  # Check every 10 seconds
            # Yield nothing, but keep generator alive for other collectors
            yield None, None  # Empty event signals degraded mode
        print(f"[*] DNS log file detected at {log_path}, resuming normal operation")

    print(f"[*] DNS Collector reading from {log_path}")
    f = None
    while True:  # Outer loop for reconnection
        try:
            if f is None:
                f = open(log_path, "r")
                f.seek(0, os.SEEK_END)

            while True:
                try:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        # Check for file rotation
                        current_pos = f.tell()
                        try:
                            file_size = os.path.getsize(log_path)
                        except FileNotFoundError:
                            # File deleted - close and wait for recreation
                            print(
                                f"[!] Log file {log_path} deleted. Waiting for recreation..."
                            )
                            if f:
                                f.close()
                                f = None
                            # Yield empty events while waiting
                            while not os.path.exists(log_path):
                                time.sleep(5)
                                yield None, None
                            print(f"[*] Log file recreated. Resuming...")
                            break  # Break inner loop to reopen file

                        if current_pos > file_size and file_size > 0:
                            print(f"[!] Log file rotated. Re-opening {log_path}")
                            f.close()
                            f = open(log_path, "r")
                            # No seek, start from beginning of new file
                        continue

                    evt = parse_dnsmasq(line)
                    if evt:
                        yield evt
                except KeyboardInterrupt:
                    raise  # Propagate to outer loop
                except Exception as e:
                    print(f"[!] Error reading log file: {e}")
                    time.sleep(1)
        except KeyboardInterrupt:
            print("[*] DNS Collector shutting down gracefully")
            if f:
                f.close()
            break  # Only exit on explicit interrupt
        except Exception as e:
            print(f"[!] Fatal error in DNS collector: {e}. Restarting collector...")
            if f:
                f.close()
                f = None
            time.sleep(5)  # Wait before reconnecting
            # Continue outer loop - NEVER EXIT


# --- Backward compatibility for older tests/modules -------------------------
def stream_dns_events(
    source: str = "file",
    *,
    log_path: str = "/var/log/dnsmasq.log",
    udp_port: int = 5514,
    bind_ip: str = "0.0.0.0",
):
    """
    Compatibility shim.

    Why this exists:
    - Older tests import `stream_dns_events` directly.
    - Internals now expose specific backends (file/udp/journald/none).
    - This keeps imports stable and prevents pytest collection failures.

    Design choice:
    - For `none` / `journald` we return an empty iterator (finite).
      This avoids "infinite test hangs" under pytest.
      Production uses the main engine loop, not this shim.
    """
    src = (source or "none").lower()

    if src == "file":
        return stream_dns_events_file(log_path)
    if src == "udp":
        return stream_dns_events_udp(port=udp_port, bind_ip=bind_ip)
    if src == "journald":
        from minifw_ai.collector_journald import stream_dns_events_journald

        return stream_dns_events_journald()
    if src == "none":
        return iter([])

    raise ValueError(f"Unknown DNS source: {source}")
