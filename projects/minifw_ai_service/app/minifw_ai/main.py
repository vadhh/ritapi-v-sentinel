from __future__ import annotations
import os

# VSentinel Hard Guard
if os.getenv("GAMBLING_ONLY") != "1":
    raise SystemExit("VSentinel Critical: Non-gambling mode detected. Shutting down.")

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
from minifw_ai.collector_flow import FlowTracker, build_feature_vector_24, stream_conntrack_flows

# NEW: Import state manager for dynamic state transitions (TODO 4.1/4.2)
from minifw_ai.state_manager import StateManager, ProtectionState

# NEW: Import MLP engine
try:
    from minifw_ai.utils.mlp_engine import get_mlp_detector
    MLP_AVAILABLE = True
except Exception:
    MLP_AVAILABLE = False
    get_mlp_detector = None

# NEW: Import YARA scanner
try:
    from minifw_ai.utils.yara_scanner import get_yara_scanner
    YARA_AVAILABLE = True
except Exception:
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

def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

def score_and_decide(domain: str, denied: bool, sni_denied: bool, asn_denied: bool, burst_hit: int, weights: dict, thresholds, mlp_score: int = 0, yara_score: int = 0, hard_threat_override: bool = False, hard_threat_reason: str | None = None, pre_reasons: list[str] | None = None):
    score = 0
    reasons = list(pre_reasons) if pre_reasons else []
    
    # CRITICAL: Hard threat override bypasses normal scoring
    if hard_threat_override:
        if hard_threat_reason:
            reasons.append(hard_threat_reason)
        reasons.append("hard_threat_gate_override")
        return 100, reasons, "block"

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

def evaluate_hard_threat(flows: list, flow_freq: int, flow_freq_threshold: int) -> tuple[bool, str | None]:
    if flow_freq >= flow_freq_threshold:
        return True, "flow_frequency"

    for flow in flows:
        if flow.pkt_count < 5:
            continue

        # Rule 1: PPS Saturation (>200 packets/sec)
        if flow.pkts_per_sec > 200:
            return True, "pps_saturation"

        # Rule 2: Burst Flood (>300 packets in 1 second)
        if flow.max_burst_pkts_1s > 300:
            return True, "burst_flood"

        # Rule 3: Bot-like Small Packets (>95% small packets + short duration)
        if flow.small_pkt_ratio > 0.95 and flow.duration < 3:
            return True, "bot_like_small_packets"

        # Rule 4: Extreme Interarrival Regularity (std < 5ms with high PPS)
        if hasattr(flow, 'interarrival_std_ms') and flow.interarrival_std_ms < 5 and flow.pkts_per_sec > 100:
            return True, "bot_regular_timing"

    return False, None

def init_mlp_detector(ai_enabled: bool) -> tuple[Any, bool]:
    if not ai_enabled:
        return None, False
    if not MLP_AVAILABLE:
        logging.warning("[MLP] MLP engine not available (install scikit-learn)")
        return None, False

    mlp_model_path = os.environ.get("MINIFW_MLP_MODEL")
    mlp_threshold = float(os.environ.get("MINIFW_MLP_THRESHOLD", "0.5"))

    if mlp_model_path and Path(mlp_model_path).exists():
        try:
            mlp_detector = get_mlp_detector(
                model_path=mlp_model_path,
                threshold=mlp_threshold
            )
            if mlp_detector.model_loaded:
                logging.info(f"[MLP] Loaded model from: {mlp_model_path}")
                logging.info(f"[MLP] Threshold: {mlp_threshold}")
                return mlp_detector, True
        except Exception as e:
            logging.warning(f"[MLP] Failed to load model: {e}")
    else:
        logging.info("[MLP] No model configured (set MINIFW_MLP_MODEL environment variable)")

    return None, False

def init_yara_scanner(ai_enabled: bool) -> tuple[Any, bool]:
    if not ai_enabled:
        return None, False
    if not YARA_AVAILABLE:
        logging.warning("[YARA] YARA scanner not available (install yara-python)")
        return None, False

    yara_rules_dir = os.environ.get("MINIFW_YARA_RULES")
    if yara_rules_dir and Path(yara_rules_dir).exists():
        try:
            yara_scanner = get_yara_scanner(rules_dir=yara_rules_dir)
            if yara_scanner.rules_loaded:
                stats = yara_scanner.get_stats()
                logging.info(f"[YARA] Loaded rules from: {yara_rules_dir}")
                logging.info(f"[YARA] Rules loaded: {stats['rules_loaded']}")
                return yara_scanner, True
        except Exception as e:
            logging.warning(f"[YARA] Failed to load rules: {e}")
    else:
        logging.info("[YARA] No rules configured (set MINIFW_YARA_RULES environment variable)")

    return None, False

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

    # Determine initial protection state from environment
    _initial_ai = _env_flag("AI_ENABLED", True)
    _initial_degraded = os.environ.get("DEGRADED_MODE", "0") == "1"
    if _initial_degraded or not _initial_ai:
        _initial_state = ProtectionState.BASELINE_PROTECTION
    else:
        _initial_state = ProtectionState.AI_ENHANCED_PROTECTION

    state_manager = StateManager(initial_state=_initial_state)
    logging.info(f"[STATE] Initial protection state: {state_manager.get_current_state().value}")
    
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
    
    # NEW: Initialize flow tracker with LRU capping
    max_flows = _safe_int_cast(os.environ.get("MINIFW_MAX_FLOWS"), 20000)
    flow_tracker = FlowTracker(flow_timeout=300, max_flows=max_flows)

    # NEW: Initialize AI modules (Layer 2) with graceful degradation
    mlp_detector, mlp_enabled = init_mlp_detector(state_manager.is_ai_enabled())
    yara_scanner, yara_enabled = init_yara_scanner(state_manager.is_ai_enabled())
    
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
            logging.warning("Failed to start Zeek SNI event stream - continuing in degraded mode", exc_info=True)
            zeek_iter = None

    # NEW: Conntrack flow stream for baseline tracking
    conntrack_path = os.environ.get("MINIFW_CONNTRACK_PATH", "/proc/net/nf_conntrack")
    flow_iter = None
    try:
        flow_iter = stream_conntrack_flows(conntrack_path)
    except Exception:
        logging.warning("Failed to start conntrack flow stream - hard gates may be degraded", exc_info=True)

    flow_freq_window = _safe_int_cast(os.environ.get("MINIFW_FLOW_FREQ_WINDOW_SEC"), 60)
    flow_freq_threshold = _safe_int_cast(os.environ.get("MINIFW_FLOW_FREQ_THRESHOLD"), 200)
    flow_freq_tracker = BurstTracker(window_seconds=flow_freq_window, max_size=20000)
    flow_pkt_size = _safe_int_cast(os.environ.get("MINIFW_FLOW_PKT_SIZE_ESTIMATE"), 1500)

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

    def pump_flows():
        if flow_iter is None:
            return
        for _ in range(5):
            try:
                src_ip, dst_ip, dst_port, proto = next(flow_iter)
                flow_tracker.update_flow(src_ip, dst_ip, dst_port, proto, pkt_size=flow_pkt_size)
                flow_freq_tracker.add(src_ip)
            except Exception:
                logging.warning("Error pumping conntrack flow", exc_info=True)
                break
    
    # NEW: Counter for flow record exports
    flow_export_counter = 0
    flow_export_interval = 100  # Export flow records every 100 DNS queries

    # PLUGGABLE DNS BACKEND: Support multiple DNS sources
    dns_events = None
    dns_source = os.environ.get("MINIFW_DNS_SOURCE", "file")  # file, journald, udp, none
    degraded_mode = os.environ.get("DEGRADED_MODE", "0") == "1"
    
    if dns_source == "none" or degraded_mode:
        logging.warning(f"[DEGRADED_MODE] DNS telemetry disabled (source={dns_source}, degraded={degraded_mode})")
        logging.warning(f"[DEGRADED_MODE] Running with flow tracking and hard-threat gates only (Fail-Closed Security)")
        # Create empty iterator that yields None indefinitely
        def empty_dns_iterator():
            import time
            while True:
                yield None, None
                time.sleep(1)  # Yield empty event every second to keep loop alive
        dns_events = empty_dns_iterator()
    else:
        try:
            if dns_source == "file":
                logging.info(f"[DNS_COLLECTOR] Using file source: {dns_log}")
                dns_events = stream_dns_events_file(dns_log)
            elif dns_source == "journald":
                logging.warning(f"[DNS_COLLECTOR] journald source not yet implemented, falling back to degraded mode")
                def empty_dns_iterator():
                    import time
                    while True:
                        yield None, None
                        time.sleep(1)
                dns_events = empty_dns_iterator()
            elif dns_source == "udp":
                from minifw_ai.collector_dnsmasq import stream_dns_events_udp
                dns_port = int(os.environ.get("MINIFW_DNS_UDP_PORT", "5514"))
                logging.info(f"[DNS_COLLECTOR] Using UDP source on port {dns_port}")
                dns_events = stream_dns_events_udp(port=dns_port)
            else:
                logging.warning(f"[DNS_COLLECTOR] Unknown DNS source: {dns_source}, using file as fallback")
                dns_events = stream_dns_events_file(dns_log)
            
            logging.info(f"[DNS_COLLECTOR] Successfully initialized DNS event stream (source={dns_source})")
        except Exception as e:
            logging.warning(f"[DEGRADED_MODE] DNS collector failed to initialize: {e}")
            logging.warning(f"[DEGRADED_MODE] Continuing with IP filtering and flow tracking only (Fail-Closed Security)...")
            # Create empty generator to keep service running
            def empty_dns_iterator():
                import time
                while True:
                    yield None, None
                    time.sleep(1)
            dns_events = empty_dns_iterator()

    for client_ip, domain in dns_events:
        pump_zeek()
        pump_flows()

        # Dynamic state transition check (TODO 4.1/4.2)
        state_manager.record_dns_event(client_ip, domain)
        state_changed, new_state, transition_reason = state_manager.check_and_transition()
        if state_changed:
            _ai_on = state_manager.is_ai_enabled()
            mlp_detector, mlp_enabled = init_mlp_detector(_ai_on)
            yara_scanner, yara_enabled = init_yara_scanner(_ai_on)
            logging.warning(
                f"[STATE_TRANSITION] {new_state.value} | MLP={mlp_enabled} YARA={yara_enabled} | {transition_reason}"
            )

        # CRITICAL: Skip empty events from degraded mode DNS iterator
        # But ALWAYS run flow-based hard-threat gates via pump_flows() above
        if client_ip is None or domain is None:
            # In degraded mode: only run flow-based detection (no DNS-based scoring)
            # Hard-threat gates still execute every iteration via pump_flows()
            continue
        
        mlp_score = 0
        mlp_proba = 0.0
        yara_score = 0
        yara_matches = []
        hard_threat = False
        hard_threat_reason = None
        score = 0
        action = "allow"
        reasons = []
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

            # Layer 1: Hard threat gates (mandatory)
            flows_for_client = flow_tracker.get_flows_for_client(client_ip)
            flow_freq = flow_freq_tracker.get_rate(client_ip)
            hard_threat, hard_threat_reason = evaluate_hard_threat(
                flows_for_client,
                flow_freq,
                flow_freq_threshold
            )
            if hard_threat:
                logging.warning(f"[HARD_GATE] Triggered: {client_ip} - {hard_threat_reason}")

            # Layer 2: AI risk amplifier (conditional)
            flow_for_ai = flows_for_client[-1] if flows_for_client else None
            if state_manager.is_ai_enabled() and mlp_enabled and mlp_detector and flow_for_ai and flow_for_ai.pkt_count >= 5:
                try:
                    is_threat, proba = mlp_detector.is_suspicious(flow_for_ai, return_probability=True)
                    mlp_proba = proba
                    if is_threat:
                        mlp_score = int(proba * 100)
                except Exception:
                    logging.warning("[MLP] Inference failed; continuing without MLP", exc_info=True)

            if state_manager.is_ai_enabled() and yara_enabled and yara_scanner:
                try:
                    payload = f"{domain} {sni}".encode('utf-8')
                    matches = yara_scanner.scan_payload(payload, timeout=5)
                    if matches:
                        yara_matches = matches
                        severity_scores = {'critical': 100, 'high': 75, 'medium': 50, 'low': 25}
                        max_severity_score = max(
                            severity_scores.get(m.get_severity(), 25) for m in matches
                        )
                        yara_score = max_severity_score
                        for match in matches[:3]:
                            reasons.append(f"yara_{match.rule}")
                except Exception:
                    logging.warning("[YARA] Scan failed; continuing without YARA", exc_info=True)

            score, reasons, action = score_and_decide(
                domain, denied, sni_denied, asn_denied, burst_hit,
                weights, thr, mlp_score, yara_score,
                hard_threat_override=hard_threat,
                hard_threat_reason=hard_threat_reason,
                pre_reasons=reasons
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
                        'ai_verdict': 'threat' if (hard_threat or mlp_score > 50 or yara_score > 50) else 'normal',
                        'ai_confidence': (1.0 if hard_threat else max(mlp_proba, yara_score / 100.0)) if flow.client_ip == client_ip else None,
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