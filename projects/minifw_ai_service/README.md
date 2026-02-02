MiniFW-AI for RitAPI-AI V-Sentinel (client-installed)
====================================================

Goal
----
MiniFW-AI is the gateway metadata protection layer for RitAPI-AI V-Sentinel.
It does NOT require:
- client browser proxy settings
- TLS MITM / CA import
- mitmproxy

It works by:
1) Collecting metadata signals (DNS queries; optional Zeek TLS SNI)
2) Scoring signals with a policy per network segment
3) Enforcing blocks using nftables/ipset
4) Writing audit events to JSONL for dashboard/export

Quick start (DNS-only)
----------------------
1) Install dependencies (Debian/Ubuntu):
   sudo ./scripts/install.sh

2) Enable dnsmasq query logging:
   sudo ./scripts/enable_dnsmasq_logging.sh
   sudo systemctl restart dnsmasq || true

3) Start MiniFW-AI as a service:
   sudo ./scripts/install_systemd.sh
   sudo systemctl status minifw-ai --no-pager

4) Tail events:
   tail -f /opt/minifw_ai/logs/events.jsonl

Optional: Zeek TLS SNI
----------------------
If Zeek is installed and /var/log/zeek/ssl.log exists, enable it:
   sudo ./scripts/enable_zeek_sni.sh

Configuration
-------------
- Policy: /opt/minifw_ai/config/policy.json
- Feeds:  /opt/minifw_ai/config/feeds/*.txt
- Logs:   /opt/minifw_ai/logs/events.jsonl

Safety note
-----------
This package installs firewall rules affecting forwarding traffic. Ensure the system
is truly the gateway/router for the client LAN/VLAN(s) and you have console access
during first deployment.
