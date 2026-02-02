"""
Flow Collector for RitAPI V-Sentinel MiniFW-AI
Collects flow-level statistics from conntrack for MLP feature extraction.
"""
from __future__ import annotations
import time
import hashlib
from pathlib import Path
from typing import Iterator, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field
import math


@dataclass
class FlowStats:
    """Track statistics for a single flow (5-tuple)"""
    client_ip: str
    dst_ip: str
    dst_port: int
    proto: str
    
    # Timing
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    # Packet/byte counters
    pkt_count: int = 0
    bytes_sent: int = 0
    bytes_recv: int = 0
    
    # Packet sizes for stats
    pkt_sizes: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    # Inter-arrival times (in ms)
    interarrival_times: deque = field(default_factory=lambda: deque(maxlen=500))
    last_pkt_time: Optional[float] = None
    
    # Burst tracking (1-second windows)
    burst_windows: deque = field(default_factory=lambda: deque(maxlen=60))  # last 60 seconds
    current_window_start: float = field(default_factory=time.time)
    current_window_pkts: int = 0
    current_window_bytes: int = 0
    
    # Domain/DNS info (optional, will be enriched later)
    domain: str = ""
    sni: str = ""
    tls_seen: bool = False
    
    def update(self, pkt_size: int, direction: str = "out") -> None:
        """Update flow stats with new packet"""
        now = time.time()
        self.last_seen = now
        self.pkt_count += 1
        
        if direction == "out":
            self.bytes_sent += pkt_size
        else:
            self.bytes_recv += pkt_size
            
        self.pkt_sizes.append(pkt_size)
        
        # Inter-arrival time
        if self.last_pkt_time is not None:
            iat_ms = (now - self.last_pkt_time) * 1000
            self.interarrival_times.append(iat_ms)
        self.last_pkt_time = now
        
        # Burst tracking
        if now - self.current_window_start >= 1.0:
            # Save current window and start new one
            self.burst_windows.append({
                'pkts': self.current_window_pkts,
                'bytes': self.current_window_bytes
            })
            self.current_window_start = now
            self.current_window_pkts = 0
            self.current_window_bytes = 0
        
        self.current_window_pkts += 1
        self.current_window_bytes += pkt_size
    
    def get_duration(self) -> float:
        """Get flow duration in seconds"""
        return max(0.1, self.last_seen - self.first_seen)
    
    def get_total_bytes(self) -> int:
        """Get total bytes (sent + received)"""
        return self.bytes_sent + self.bytes_recv
    
    def get_bytes_per_sec(self) -> float:
        """Calculate bytes per second"""
        duration = self.get_duration()
        return self.get_total_bytes() / duration if duration > 0 else 0.0
    
    def get_pkts_per_sec(self) -> float:
        """Calculate packets per second"""
        duration = self.get_duration()
        return self.pkt_count / duration if duration > 0 else 0.0
    
    # Property shortcuts for convenience (used in hard gates)
    @property
    def duration(self) -> float:
        """Shortcut for get_duration()"""
        return self.get_duration()
    
    @property
    def pkts_per_sec(self) -> float:
        """Shortcut for get_pkts_per_sec()"""
        return self.get_pkts_per_sec()
    
    @property
    def bytes_per_sec(self) -> float:
        """Shortcut for get_bytes_per_sec()"""
        return self.get_bytes_per_sec()
    
    @property
    def max_burst_pkts_1s(self) -> int:
        """Shortcut for get_max_burst_pkts_1s()"""
        return self.get_max_burst_pkts_1s()
    
    @property
    def max_burst_bytes_1s(self) -> int:
        """Shortcut for get_max_burst_bytes_1s()"""
        return self.get_max_burst_bytes_1s()
    
    @property
    def small_pkt_ratio(self) -> float:
        """Shortcut for get_small_pkt_ratio()"""
        return self.get_small_pkt_ratio()
    
    @property
    def interarrival_std_ms(self) -> float:
        """Shortcut for get_interarrival_std()"""
        return self.get_interarrival_std()
    
    def get_avg_pkt_size(self) -> float:
        """Calculate average packet size"""
        if not self.pkt_sizes:
            return 0.0
        return sum(self.pkt_sizes) / len(self.pkt_sizes)
    
    def get_pkt_size_std(self) -> float:
        """Calculate packet size standard deviation"""
        if len(self.pkt_sizes) < 2:
            return 0.0
        avg = self.get_avg_pkt_size()
        variance = sum((x - avg) ** 2 for x in self.pkt_sizes) / len(self.pkt_sizes)
        return math.sqrt(variance)
    
    def get_inbound_outbound_ratio(self) -> float:
        """Calculate ratio of inbound to outbound bytes"""
        if self.bytes_recv == 0 and self.bytes_sent == 0:
            return 1.0
        return self.bytes_recv / (self.bytes_sent + 1)
    
    def get_max_burst_pkts_1s(self) -> int:
        """Get maximum burst packets in any 1-second window"""
        if not self.burst_windows:
            return self.current_window_pkts
        return max(w['pkts'] for w in self.burst_windows)
    
    def get_max_burst_bytes_1s(self) -> int:
        """Get maximum burst bytes in any 1-second window"""
        if not self.burst_windows:
            return self.current_window_bytes
        return max(w['bytes'] for w in self.burst_windows)
    
    def get_interarrival_mean_ms(self) -> float:
        """Get mean inter-arrival time in milliseconds"""
        if not self.interarrival_times:
            return 0.0
        return sum(self.interarrival_times) / len(self.interarrival_times)
    
    def get_interarrival_std_ms(self) -> float:
        """Get standard deviation of inter-arrival times"""
        if len(self.interarrival_times) < 2:
            return 0.0
        mean = self.get_interarrival_mean_ms()
        variance = sum((x - mean) ** 2 for x in self.interarrival_times) / len(self.interarrival_times)
        return math.sqrt(variance)
    
    def get_interarrival_p95_ms(self) -> float:
        """Get 95th percentile of inter-arrival times"""
        if not self.interarrival_times:
            return 0.0
        sorted_times = sorted(self.interarrival_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx] if idx < len(sorted_times) else sorted_times[-1]
    
    def get_small_pkt_ratio(self) -> float:
        """Get ratio of small packets (< 120 bytes)"""
        if not self.pkt_sizes:
            return 0.0
        small_count = sum(1 for s in self.pkt_sizes if s < 120)
        return small_count / len(self.pkt_sizes)


class FlowTracker:
    """Track all active flows and compute statistics"""
    
    def __init__(self, flow_timeout: int = 300):
        """
        Args:
            flow_timeout: Flow timeout in seconds (default 5 minutes)
        """
        self.flows: dict[str, FlowStats] = {}
        self.flow_timeout = flow_timeout
        self.last_cleanup = time.time()
    
    def _flow_key(self, client_ip: str, dst_ip: str, dst_port: int, proto: str) -> str:
        """Generate unique flow key"""
        return f"{client_ip}:{dst_ip}:{dst_port}:{proto}"
    
    def update_flow(self, client_ip: str, dst_ip: str, dst_port: int, proto: str, 
                   pkt_size: int = 0, direction: str = "out") -> FlowStats:
        """Update or create flow"""
        key = self._flow_key(client_ip, dst_ip, dst_port, proto)
        
        if key not in self.flows:
            self.flows[key] = FlowStats(
                client_ip=client_ip,
                dst_ip=dst_ip,
                dst_port=dst_port,
                proto=proto
            )
        
        flow = self.flows[key]
        if pkt_size > 0:
            flow.update(pkt_size, direction)
        
        return flow
    
    def get_flow(self, client_ip: str, dst_ip: str, dst_port: int, proto: str) -> Optional[FlowStats]:
        """Get flow stats if exists"""
        key = self._flow_key(client_ip, dst_ip, dst_port, proto)
        return self.flows.get(key)
    
    def enrich_with_dns(self, client_ip: str, domain: str) -> None:
        """Enrich flows from this client with domain info"""
        for flow in self.flows.values():
            if flow.client_ip == client_ip and not flow.domain:
                flow.domain = domain
    
    def enrich_with_sni(self, client_ip: str, sni: str) -> None:
        """Enrich flows from this client with SNI/TLS info"""
        for flow in self.flows.values():
            if flow.client_ip == client_ip:
                flow.sni = sni
                flow.tls_seen = True
    
    def cleanup_old_flows(self, force: bool = False) -> int:
        """Remove expired flows"""
        now = time.time()
        
        # Only cleanup every 60 seconds unless forced
        if not force and (now - self.last_cleanup) < 60:
            return 0
        
        self.last_cleanup = now
        expired_keys = []
        
        for key, flow in self.flows.items():
            if (now - flow.last_seen) > self.flow_timeout:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.flows[key]
        
        return len(expired_keys)
    
    def get_all_active_flows(self) -> list[FlowStats]:
        """Get all active flows"""
        return list(self.flows.values())


def parse_conntrack_line(line: str) -> Optional[tuple]:
    """
    Parse /proc/net/nf_conntrack line
    Example format:
    ipv4     2 tcp      6 117 ESTABLISHED src=192.168.1.100 dst=8.8.8.8 sport=54321 dport=443 ...
    """
    try:
        parts = line.split()
        if len(parts) < 10:
            return None
        
        proto = parts[0]  # ipv4/ipv6
        l4_proto = parts[2]  # tcp/udp/icmp
        
        # Extract IPs and ports
        src_ip = None
        dst_ip = None
        src_port = 0
        dst_port = 0
        
        for part in parts:
            if part.startswith('src='):
                src_ip = part.split('=')[1]
            elif part.startswith('dst='):
                dst_ip = part.split('=')[1]
            elif part.startswith('sport='):
                src_port = int(part.split('=')[1])
            elif part.startswith('dport='):
                dst_port = int(part.split('=')[1])
        
        if src_ip and dst_ip and dst_port:
            return (src_ip, dst_ip, dst_port, l4_proto)
        
        return None
    except Exception:
        return None


def stream_conntrack_flows(conntrack_path: str = "/proc/net/nf_conntrack") -> Iterator[tuple]:
    """
    Stream flows from conntrack
    Yields: (src_ip, dst_ip, dst_port, proto)
    """
    p = Path(conntrack_path)
    
    while True:
        try:
            if not p.exists():
                time.sleep(5)
                continue
            
            with p.open("r") as f:
                for line in f:
                    parsed = parse_conntrack_line(line.strip())
                    if parsed:
                        yield parsed
            
            # Poll every 5 seconds
            time.sleep(5)
            
        except Exception:
            time.sleep(5)
            continue


def build_feature_vector_24(flow: FlowStats) -> list[float]:
    """
    Build 24-feature vector from FlowStats for MLP input
    Order matches MLP schema v1 from the document
    """
    # Basic flow (8)
    duration_sec = flow.get_duration()
    pkt_count_total = float(flow.pkt_count)
    bytes_total = float(flow.get_total_bytes())
    bytes_per_sec = flow.get_bytes_per_sec()
    pkts_per_sec = flow.get_pkts_per_sec()
    avg_pkt_size = flow.get_avg_pkt_size()
    pkt_size_std = flow.get_pkt_size_std()
    inbound_outbound_ratio = flow.get_inbound_outbound_ratio()
    
    # Burst & periodicity (6)
    max_burst_pkts_1s = float(flow.get_max_burst_pkts_1s())
    max_burst_bytes_1s = float(flow.get_max_burst_bytes_1s())
    interarrival_mean_ms = flow.get_interarrival_mean_ms()
    interarrival_std_ms = flow.get_interarrival_std_ms()
    interarrival_p95_ms = flow.get_interarrival_p95_ms()
    small_pkt_ratio = flow.get_small_pkt_ratio()
    
    # TLS (6)
    tls_seen = 1.0 if flow.tls_seen else 0.0
    tls_handshake_time_ms = 0.0  # TODO: implement if TLS handshake timing available
    
    # JA3 hash bucket (not yet implemented, placeholder)
    ja3_hash_bucket = 0.0
    
    sni_len = float(len(flow.sni)) if flow.sni else 0.0
    alpn_h2 = 0.0  # TODO: detect HTTP/2 ALPN
    cert_self_signed_suspect = 0.0  # TODO: implement if cert validation available
    
    # DNS / domain behavior (4)
    dns_seen = 1.0 if flow.domain else 0.0
    fqdn_len = float(len(flow.domain)) if flow.domain else 0.0
    
    # Count dots in domain for subdomain depth
    subdomain_depth = float(flow.domain.count('.') - 1) if flow.domain else 0.0
    
    # Domain repeat (TODO: needs global tracking, placeholder for now)
    domain_repeat_5min = 0.0
    
    return [
        # Basic flow (8)
        duration_sec,
        pkt_count_total,
        bytes_total,
        bytes_per_sec,
        pkts_per_sec,
        avg_pkt_size,
        pkt_size_std,
        inbound_outbound_ratio,
        
        # Burst & periodicity (6)
        max_burst_pkts_1s,
        max_burst_bytes_1s,
        interarrival_mean_ms,
        interarrival_std_ms,
        interarrival_p95_ms,
        small_pkt_ratio,
        
        # TLS (6)
        tls_seen,
        tls_handshake_time_ms,
        ja3_hash_bucket,
        sni_len,
        alpn_h2,
        cert_self_signed_suspect,
        
        # DNS / domain behavior (4)
        dns_seen,
        fqdn_len,
        subdomain_depth,
        domain_repeat_5min,
    ]