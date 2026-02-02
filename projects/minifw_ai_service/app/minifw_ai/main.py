from __future__ import annotations
import os
import json
import logging
import subprocess
from pathlib import Path
from collections import OrderedDict
from typing import Any

from minifw_ai.policy import Policy
from minifw_ai.feeds import FeedMatcher
from minifw_ai.netutil import ip_in_any_subnet
from minifw_ai.events import Event, EventWriter, now_iso
from minifw_ai.enforce import ipset_create, ipset_add, nft_apply_forward_drop
from minifw_ai.collector_dnsmasq import stream_dns_events_file
from minifw_ai.collector_zeek import stream_zeek_sni_events
from minifw_ai.burst import BurstTracker

# NEW: Import flow collector
from minifw_ai.collector_flow import FlowTracker, build_feature_vector_24

# NEW: Import MLP engine
try:
    from minifw_ai.utils.mlp_engine import get_mlp_detector
    MLP_AVAILABLE = True
except ImportError:
    MLP_AVAILABLE = False
    get_mlp_detector = None

# NEW: Import YARA scanner
try:
    from minifw_ai.utils.yara_scanner import get_yara_scanner
    YARA_AVAILABLE = True
except ImportError:
    YARA_AVAILABLE = False
    get_yara_scanner = None

# NEW: Import Sector Lock system
try:
    from minifw_ai.sector_lock import get_sector_lock, get_sector_config
    from minifw_ai.sector_config import get_threshold_adjustment, is_iomt_priority
    SECTOR_LOCK_AVAILABLE = True
except ImportError:
    SECTOR_LOCK_AVAILABLE = False
    get_sector_lock = None

def segment_for_ip(ip: str, mapping: dict[str, list[str]]) -> str:
    for seg, cidrs in mapping.items():
        if ip_in_any_subnet(ip, cidrs):
            return seg
    return "default"

def _safe_int_cast(value: Any, default: int) -> int:
    """Safely cast a value to int, returning default on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def score_and_decide(domain: str, denied: bool, sni_denied: bool, asn_denied: bool, burst_hit: int, weights: dict, thresholds, mlp_score: int = 0, yara_score: int = 0, hard_threat_override: bool = False):
    score = 0
    reasons = []
    
    # CRITICAL: Hard threat override bypasses normal scoring
    if hard_threat_override:
        return 100, ["hard_threat_gate_override"], "block"

    if denied:
        score += _safe_int_cast(weights.get("dns_weight"), 40)
        reasons.append("dns_denied_domain")
    if sni_denied:
        score += _safe_int_cast(weights.get("sni_weight"), 35)
        reasons.append("tls_sni_denied_domain")
    if asn_denied:
        score += _safe_int_cast(weights.get("asn_weight"), 15)
        reasons.append("asn_denied")
    if burst_hit:
        score += int(weights.get("burst_weight", 10)); reasons.append("burst_behavior")
    
    # NEW: Add MLP score (weight configurable, default 30)
    if mlp_score > 0:
        mlp_weight = int(weights.get("mlp_weight", 30))
        score += mlp_score * mlp_weight // 100  # mlp_score is 0-100
        reasons.append(f"mlp_threat_score_{mlp_score}")
    
    # NEW: Add YARA score (weight configurable, default 35)
    if yara_score > 0:
        yara_weight = int(weights.get("yara_weight", 35))
        score += yara_score * yara_weight // 100  # yara_score is 0-100
        reasons.append(f"yara_match_score_{yara_score}")

    score = max(0, min(100, score))

    block_thr = _safe_int_cast(thresholds.block_threshold, 90)
    monitor_thr = _safe_int_cast(thresholds.monitor_threshold, 60)

    if score >= block_thr:
        return score, reasons, "block"
    if score >= monitor_thr:
        return score, reasons, "monitor"
    return score, reasons, "allow"

def run():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    policy_path = os.environ.get("MINIFW_POLICY", "/opt/minifw_ai/config/policy.json")
    feeds_dir = os.environ.get("MINIFW_FEEDS", "/opt/minifw_ai/config/feeds")
    log_path = os.environ.get("MINIFW_LOG", "/opt/minifw_ai/logs/events.jsonl")
    
    # NEW: Flow records output path
    flow_records_path = os.environ.get("MINIFW_FLOW_RECORDS", "/opt/minifw_ai/logs/flow_records.jsonl")

    pol = Policy(policy_path)
    feeds = FeedMatcher(feeds_dir)
    writer = EventWriter(log_path)
    
    # NEW: Initialize Sector Lock (Factory-Set Configuration)
    sector_lock = None
    sector_config = {}
    sector_name = "unknown"
    iomt_subnets = []  # For hospital sector
    
    if SECTOR_LOCK_AVAILABLE:
        try:
            sector_lock = get_sector_lock()
            sector_config = sector_lock.get_sector_config()
            sector_name = sector_lock.get_sector()
            
            logging.info(f"[SECTOR_LOCK] Device sector: {sector_name} (LOCKED)")
            logging.info(f"[SECTOR_LOCK] Config: {sector_config.get('description', 'N/A')}")
            
            # Load sector-specific feeds
            extra_feeds = sector_config.get('extra_feeds', [])
            if extra_feeds:
                loaded = feeds.load_sector_feeds(extra_feeds)
                logging.info(f"[SECTOR_LOCK] Loaded {loaded} sector-specific feed patterns")
            
            # Get IoMT subnets for hospital sector (from policy.json, not hardcoded)
            if sector_lock.is_hospital():
                iomt_subnets = pol.cfg.get('iomt_subnets', [])
                if iomt_subnets:
                    logging.info(f"[SECTOR_LOCK] Hospital mode: IoMT subnets = {iomt_subnets}")
                else:
                    logging.warning("[SECTOR_LOCK] Hospital mode but no iomt_subnets in policy.json")
            
        except RuntimeError as e:
            logging.critical(f"[SECTOR_LOCK] FATAL: {e}")
            logging.critical("[SECTOR_LOCK] Device cannot start without valid sector config")
            return
        except Exception as e:
            logging.error(f"[SECTOR_LOCK] Warning: {e} - continuing without sector lock")
    else:
        logging.warning("[SECTOR_LOCK] Sector lock module not available")
    
    # NEW: Initialize flow tracker
    flow_tracker = FlowTracker(flow_timeout=300)
    
    # NEW: Initialize MLP detector if available
    mlp_detector = None
    mlp_enabled = False
    if MLP_AVAILABLE:
        mlp_model_path = os.environ.get("MINIFW_MLP_MODEL")
        mlp_threshold = float(os.environ.get("MINIFW_MLP_THRESHOLD", "0.5"))
        
        if mlp_model_path and Path(mlp_model_path).exists():
            try:
                mlp_detector = get_mlp_detector(
                    model_path=mlp_model_path,
                    threshold=mlp_threshold
                )
                if mlp_detector.model_loaded:
                    mlp_enabled = True
                    print(f"[MLP] Loaded model from: {mlp_model_path}")
                    print(f"[MLP] Threshold: {mlp_threshold}")
            except Exception as e:
                print(f"[MLP] Failed to load model: {e}")
        else:
            print("[MLP] No model configured (set MINIFW_MLP_MODEL environment variable)")
    else:
        print("[MLP] MLP engine not available (install scikit-learn)")
    
    # NEW: Initialize YARA scanner if available
    yara_scanner = None
    yara_enabled = False
    if YARA_AVAILABLE:
        yara_rules_dir = os.environ.get("MINIFW_YARA_RULES")
        
        if yara_rules_dir and Path(yara_rules_dir).exists():
            try:
                yara_scanner = get_yara_scanner(rules_dir=yara_rules_dir)
                if yara_scanner.rules_loaded:
                    yara_enabled = True
                    print(f"[YARA] Loaded rules from: {yara_rules_dir}")
                    stats = yara_scanner.get_stats()
                    print(f"[YARA] Rules loaded: {stats['rules_loaded']}")
            except Exception as e:
                print(f"[YARA] Failed to load rules: {e}")
        else:
            print("[YARA] No rules configured (set MINIFW_YARA_RULES environment variable)")
    else:
        print("[YARA] YARA scanner not available (install yara-python)")
    
    # NEW: Create flow records writer
    flow_records_file = Path(flow_records_path)
    flow_records_file.parent.mkdir(parents=True, exist_ok=True)

    enf = pol.enforcement()
    set_name = enf.get("ipset_name_v4", "minifw_block_v4")
    timeout = _safe_int_cast(enf.get("ip_timeout_seconds"), 86400)
    table = enf.get("nft_table", "inet")
    chain = enf.get("nft_chain", "forward")

    try:
        ipset_create(set_name, timeout)
        nft_apply_forward_drop(set_name, table=table, chain=chain)
    except (ValueError, subprocess.CalledProcessError) as e:
        logging.critical(f"FATAL: Could not initialize firewall rules. Exiting. Error: {e}")
        return # Exit if firewall can't be set up

    burst_cfg = pol.burst()
    monitor_qpm = _safe_int_cast(burst_cfg.get("dns_queries_per_minute_monitor"), 120)
    block_qpm = _safe_int_cast(burst_cfg.get("dns_queries_per_minute_block"), 240)
    burst = BurstTracker(window_seconds=60)

    seg_map = pol.segment_subnets()
    weights = pol.features()
    col = pol.collectors()
    dns_log = col.get("dnsmasq_log_path", "/var/log/dnsmasq.log")
    zeek_ssl = col.get("zeek_ssl_log_path", "/var/log/zeek/ssl.log")
    use_zeek = bool(col.get("use_zeek_sni", False))

    zeek_iter = None
    MAX_SNI_CACHE_SIZE = 10000 
    last_sni = OrderedDict()
    
    if use_zeek:
        try:
            zeek_iter = stream_zeek_sni_events(zeek_ssl)
        except Exception:
            logging.error("Failed to start Zeek SNI event stream.", exc_info=True)
            zeek_iter = None

    def pump_zeek():
        if zeek_iter is None:
            return
        for _ in range(3):
            try:
                client_ip, sni = next(zeek_iter)
                last_sni[client_ip] = sni
                # NEW: Enrich flows with SNI
                flow_tracker.enrich_with_sni(client_ip, sni)
            except Exception:
                logging.warning("Error pumping zeek event", exc_info=True)
                break
    
    # NEW: Counter for flow record exports
    flow_export_counter = 0
    flow_export_interval = 100  # Export flow records every 100 DNS queries

    for client_ip, domain in stream_dns_events_file(dns_log):
        pump_zeek()
        try:
            segment = segment_for_ip(client_ip, seg_map)
            thr = pol.thresholds(segment)
            
            # NEW: Apply sector-specific threshold adjustments
            if sector_config:
                block_adj = sector_config.get('block_threshold_adjustment', 0)
                monitor_adj = sector_config.get('monitor_threshold_adjustment', 0)
                if block_adj or monitor_adj:
                    # Create adjusted thresholds
                    from minifw_ai.policy import SegmentThreshold
                    thr = SegmentThreshold(
                        max(10, thr.block_threshold + block_adj),
                        max(10, thr.monitor_threshold + monitor_adj)
                    )

            if feeds.domain_allowed(domain):
                denied = False
            else:
                denied = feeds.domain_denied(domain)

            sni = last_sni.get(client_ip, "")
            sni_denied = bool(sni and (not feeds.domain_allowed(sni)) and feeds.domain_denied(sni))

            asn_denied = False  # placeholder for offline ASN integration

            qpm = burst.add(client_ip)
            burst_hit = 1 if (qpm >= block_qpm or qpm >= monitor_qpm) else 0
            
            # NEW: HARD THREAT GATES (Must override MLP)
            # These are absolute behavioral rules that indicate saturation attacks
            hard_threat = False
            hard_threat_reason = None
            
            # Get flow for hard threat detection
            flow = flow_tracker.get_flow(client_ip, "", 0, "tcp") if mlp_enabled or yara_enabled else None
            
            if flow and flow.pkt_count >= 5:
                # Rule 1: PPS Saturation (>200 packets/sec)
                if flow.pkts_per_sec > 200:
                    hard_threat = True
                    hard_threat_reason = "pps_saturation"
                    logging.warning(f"[HARD_GATE] PPS saturation detected: {flow.pkts_per_sec:.2f} pps from {client_ip}")
                
                # Rule 2: Burst Flood (>300 packets in 1 second)
                elif flow.max_burst_pkts_1s > 300:
                    hard_threat = True
                    hard_threat_reason = "burst_flood"
                    logging.warning(f"[HARD_GATE] Burst flood detected: {flow.max_burst_pkts_1s} pkts/s from {client_ip}")
                
                # Rule 3: Bot-like Small Packets (>95% small packets + short duration)
                elif flow.small_pkt_ratio > 0.95 and flow.duration < 3:
                    hard_threat = True
                    hard_threat_reason = "bot_like_small_packets"
                    logging.warning(f"[HARD_GATE] Bot-like pattern: {flow.small_pkt_ratio:.2%} small pkts from {client_ip}")
                
                # Rule 4: Extreme Interarrival Regularity (std < 5ms with high PPS)
                elif hasattr(flow, 'interarrival_std_ms') and flow.interarrival_std_ms < 5 and flow.pkts_per_sec > 100:
                    hard_threat = True
                    hard_threat_reason = "bot_regular_timing"
                    logging.warning(f"[HARD_GATE] Bot timing pattern: {flow.interarrival_std_ms:.2f}ms std from {client_ip}")
            
            # If hard threat detected, force BLOCK regardless of MLP
            if hard_threat:
                # Force maximum score
                mlp_score = 100
                mlp_proba = 1.0
                reasons.append(hard_threat_reason)
                logging.info(f"[HARD_GATE] Forcing BLOCK: {client_ip} - {hard_threat_reason}")
            else:
                # NEW: Get MLP score for this flow (if MLP enabled)
                mlp_score = 0
                mlp_proba = 0.0
                if mlp_enabled and mlp_detector and flow and flow.pkt_count >= 5:
                    is_threat, proba = mlp_detector.is_suspicious(flow, return_probability=True)
                    mlp_proba = proba
                    if is_threat:
                        mlp_score = int(proba * 100)  # Convert to 0-100 scale
            
            # NEW: YARA scanning on domain/payload (if YARA enabled)
            yara_score = 0
            yara_matches = []
            if yara_enabled and yara_scanner:
                # Scan domain name as payload
                # In real SSL interception, this would be decrypted payload
                payload = f"{domain} {sni}".encode('utf-8')
                matches = yara_scanner.scan_payload(payload, timeout=5)
                
                if matches:
                    yara_matches = matches
                    # Calculate score based on severity
                    severity_scores = {'critical': 100, 'high': 75, 'medium': 50, 'low': 25}
                    max_severity_score = max(
                        severity_scores.get(m.get_severity(), 25) for m in matches
                    )
                    yara_score = max_severity_score
                    
                    # Add match details to reasons (will be used later)
                    for match in matches[:3]:  # Top 3 matches
                        reasons.append(f"yara_{match.rule}")

            score, reasons, action = score_and_decide(
                domain, denied, sni_denied, asn_denied, burst_hit, 
                weights, thr, mlp_score, yara_score, 
                hard_threat_override=hard_threat
            )

            if action == "block":
                ipset_add(set_name, client_ip, timeout)
            
            # NEW: Hospital sector IoMT high-priority alerting
            if sector_lock and sector_lock.is_hospital() and iomt_subnets:
                if ip_in_any_subnet(client_ip, iomt_subnets):
                    if score >= thr.monitor_threshold:
                        logging.critical(f"[IOMT_ALERT] Medical device anomaly: {client_ip} -> {domain} (score={score})")
                        # Add IoMT flag to reasons
                        if 'iomt_device_alert' not in reasons:
                            reasons.append('iomt_device_alert')

            writer.write(Event(ts=now_iso(), segment=segment, client_ip=client_ip, domain=domain,
                               action=action, score=score, reasons=reasons, sector=sector_name))
        except KeyboardInterrupt:
            logging.info("Caught KeyboardInterrupt, shutting down.")
            break
        except Exception:
            logging.error("Unhandled exception in main event loop", exc_info=True)
        
        # NEW: Enrich flow tracker with DNS domain
        flow_tracker.enrich_with_dns(client_ip, domain)
        
        # NEW: Export flow records periodically
        flow_export_counter += 1
        if flow_export_counter >= flow_export_interval:
            # Cleanup old flows
            cleaned = flow_tracker.cleanup_old_flows()
            
            # Export active flows with features
            active_flows = flow_tracker.get_all_active_flows()
            
            with flow_records_file.open('a', encoding='utf-8') as f:
                for flow in active_flows:
                    # Only export flows with reasonable data
                    if flow.pkt_count < 5:  # Skip very small flows
                        continue
                    
                    features = build_feature_vector_24(flow)
                    
                    record = {
                        'timestamp': flow.first_seen,
                        'client_ip': flow.client_ip,
                        'dst_ip': flow.dst_ip,
                        'dst_port': flow.dst_port,
                        'proto': flow.proto,
                        'domain': flow.domain,
                        'sni': flow.sni,
                        'segment': segment_for_ip(flow.client_ip, seg_map),
                        'features': features,
                        'duration': flow.get_duration(),
                        'packets': flow.pkt_count,
                        'bytes': flow.get_total_bytes(),
                        # Include decision info if available
                        'action': action if flow.client_ip == client_ip else None,
                        'score': score if flow.client_ip == client_ip else None,
                        # NEW: AI Verdict (auditability)
                        'ai_verdict': 'threat' if (mlp_score > 50 or yara_score > 50) else 'normal',
                        'ai_confidence': max(mlp_proba, yara_score / 100.0) if flow.client_ip == client_ip else None,
                        'hard_threat_override': hard_threat if flow.client_ip == client_ip else None,
                        'hard_threat_reason': hard_threat_reason if (flow.client_ip == client_ip and hard_threat) else None,
                        # NEW: Include MLP prediction if available
                        'mlp_enabled': mlp_enabled,
                        'mlp_proba': mlp_proba if flow.client_ip == client_ip else None,
                        'mlp_score': mlp_score if flow.client_ip == client_ip else None,
                        # NEW: Include YARA matches if available
                        'yara_enabled': yara_enabled,
                        'yara_score': yara_score if flow.client_ip == client_ip else None,
                        'yara_matches': [m.to_dict() for m in yara_matches] if (flow.client_ip == client_ip and yara_matches) else [],
                        'label': None,  # To be labeled later for training
                        'label_reason': None
                    }
                    
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
            # Reset counter
            flow_export_counter = 0
            
            # Print status
            if len(active_flows) > 0:
                print(f"[FlowCollector] Exported {len(active_flows)} flows, cleaned {cleaned} old flows")

if __name__ == "__main__":
    run()