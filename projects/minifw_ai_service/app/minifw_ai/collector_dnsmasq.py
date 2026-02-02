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

def stream_dns_events_udp(port: int = 5514, bind_ip: str = "0.0.0.0") -> Iterator[Tuple[str, str]]:
    """
    Listens for DNS log lines via UDP syslog/netcat stream.
    Yields (client_ip, domain) tuples.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((bind_ip, port))
        print(f"[*] DNS Collector listening on UDP {bind_ip}:{port}")
    except PermissionError:
        print(f"[!] Error: Cannot bind to UDP port {port}. Logic will be skipped.")
        return

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            raw_text = data.decode('utf-8', errors='replace')
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
    """
    if not os.path.exists(log_path):
        print(f"[!] Error: DNS log file not found at {log_path}. Logic will be skipped.")
        return

    print(f"[*] DNS Collector reading from {log_path}")
    with open(log_path, 'r') as f:
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
                        # Handle case where file is moved/deleted during getsize
                        print(f"[!] Log file {log_path} not found. Retrying...")
                        time.sleep(1)
                        continue

                    if current_pos > file_size and file_size > 0:
                        print(f"[!] Log file rotated. Re-opening {log_path}")
                        f.close()
                        f = open(log_path, 'r')
                        # No seek, start from beginning of new file
                    continue

                evt = parse_dnsmasq(line)
                if evt:
                    yield evt
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[!] Error reading log file: {e}")
                time.sleep(1)
