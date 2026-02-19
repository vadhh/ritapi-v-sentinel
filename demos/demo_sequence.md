# V-Sentinel Real-Time Demo — Presenter Script

**Audience**: Technical evaluators, security ops teams
**Duration**: ~15 minutes
**VM requirements**: MiniFW-AI running, dnsmasq configured, nftables active

---

## Pre-Demo Checklist (5 minutes before)

```bash
# 1. Verify services are running
sudo systemctl status minifw-ai.service
sudo systemctl status ritapi-gunicorn.service

# 2. Check prerequisites
./demos/demo_traffic_gen.sh --check

# 3. OPTIONAL: Lower policy thresholds for cleaner BLOCK events
#    (production threshold=60 requires combined signals; demo policy=35 blocks on single query)
./demos/demo_traffic_gen.sh --setup-demo-policy

# 4. Clear any old block entries
sudo nft flush set inet filter minifw_block_v4

# 5. Confirm the detected dashboard URL:
./demos/demo_traffic_gen.sh --check
#    Then open browser tabs:
#    Tab 1: http://<detected-ip>/ops/minifw/events/    (MiniFW Events Viewer)
#    Tab 2: http://<detected-ip>/blocking/              (Django Blocked IPs)
#    Tab 3: http://<detected-ip>/ops/minifw/audit-logs/ (MiniFW Audit Log)
```

---

## Scoring Reference Card

| Signal | Points Added | Trigger |
|--------|-------------|---------|
| DNS denied domain | +41 | Query matches `deny_domains.txt` |
| TLS SNI denied | +34 | SNI field in TLS handshake matches deny list |
| ASN denied | +15 | Source ASN matches `deny_asn.txt` |
| Burst detection | +10 | >240 DNS queries/min from one IP |
| Hard gate (PPS/SYN) | 100 (override) | >200 pps or >300 pkts/1s burst |

| Segment | Monitor at | Block at |
|---------|-----------|---------|
| default (all others) | 40 pts | 60 pts |
| student (10.10.0.0/16) | 20 pts | 40 pts |
| staff (10.20.0.0/16) | 60 pts | 80 pts |
| admin (10.30.0.0/16) | 70 pts | 90 pts |

> **Demo policy** (via `--setup-demo-policy`): default threshold lowered to 35.
> A single denied domain query (41 pts) triggers **BLOCK** immediately.

---

## Step 0 — Establish Baseline (30 seconds)

**Say**: *"This is the V-Sentinel real-time enforcement dashboard. Right now the network is quiet. Let me show you what it looks like when threat activity starts."*

**Show**:
1. Open **Tab 1** (MiniFW Events Viewer)
2. Point out: empty events list, current policy segment thresholds
3. Open **Tab 2** (Django Blocked IPs) — show empty block list

**Terminal**:
```bash
sudo nft list set inet filter minifw_block_v4
# Expected: empty set
```

---

## Step 1 — Scenario A: DNS Denied Domain (1 minute)

**Say**: *"The first threat layer is DNS feed matching. V-Sentinel watches all DNS queries on the network. The moment a client queries a domain on our deny list — gambling, malware distribution, known C2 — the system scores that IP and takes action."*

**Run**:
```bash
./demos/demo_traffic_gen.sh --scenario A
# OR (Python version, more controlled):
python3 demos/demo_dns_flood.py --mode denied --rate 60 --verbose
```

**Say while running**: *"I'm querying `slots.example.com` — that matches our `*.slot*` deny pattern. Watch the Events Viewer."*

**Point to Tab 1** — Events Viewer updates in near-real-time:
- `domain`: slots.example.com
- `reason`: dns_denied_domain
- `score`: 41
- `action`: **BLOCK** (demo policy) or **MONITOR** (production)

**Say**: *"Within seconds of that query, the source IP is scored. With our demo policy active, a single denied domain query pushes the score above the block threshold and the IP is added to the kernel-level nftables enforcement set."*

**Show in terminal**:
```bash
sudo nft list set inet filter minifw_block_v4
# Expected: IP address visible in the set
```

---

## Step 2 — Scenario B: Burst Detection (1 minute)

**Say**: *"The second layer is behavioral rate analysis. A user querying a domain once might be accidental. But 300 DNS queries per minute from a single endpoint? That's either a botnet C2 beacon or an exfiltration channel."*

**Run**:
```bash
./demos/demo_traffic_gen.sh --scenario B
# OR:
python3 demos/demo_dns_flood.py --mode burst --rate 300 --duration 30
```

**Say while running**: *"I'm generating DNS queries at 300 per minute — above V-Sentinel's 240/min burst threshold. Watch how the event reasons change as the burst counter trips."*

**Point to Tab 1** — show:
- First events: reason=dns_denied_domain only, score=41
- After burst threshold crossed: reason adds `burst_behavior`, score jumps to 51

**Say**: *"There's the escalation. The system doesn't just block and forget — it correlates signals. The burst detection adds weight to an already-suspicious IP."*

---

## Step 3 — Scenario D: Multi-Layer Combined (1 minute)

**Say**: *"Real attacks don't come in isolation. Let me trigger multiple detection layers at once and show you how V-Sentinel aggregates threat intelligence."*

**Run**:
```bash
./demos/demo_traffic_gen.sh --scenario D
# OR:
python3 demos/demo_dns_flood.py --mode combined --rate 300 --duration 45
```

**Point to Tab 1** — show events with multiple reasons:
```
reasons: ["dns_denied_domain", "burst_behavior"]
score: 51
action: BLOCK
```

**Say**: *"The scoring pipeline is additive. DNS denied domain adds 41 points, burst detection adds 10. Each layer independently contributes. An attacker who avoids one detection method still gets caught by the others."*

---

## Step 4 — Scenario C: Hard Gate — Immediate Block (1 minute)

**Say**: *"Some threats don't need scoring deliberation. A 300-packet-per-second SYN flood? That's a DoS attack. V-Sentinel has hard gates that bypass the scoring pipeline entirely and block immediately."*

> **Note**: Requires `hping3` and `sudo`. Skip if running from VM itself (block your own access carefully).

**Run in a second terminal**:
```bash
# From the demo VM or an attacker machine:
sudo hping3 -S -p 80 --faster <VM_IP> -c 3000
```

**Or use the script**:
```bash
sudo ./demos/demo_traffic_gen.sh --scenario C
```

**Point to Tab 1** — show dramatic event:
- `score`: **100**
- `reason`: burst_flood / pps_saturation + `hard_threat_gate_override`
- `action`: **BLOCK**
- `deliberation time`: essentially instant (no scoring pipeline)

**Say**: *"Score of 100. Zero deliberation. The hard gate detected over 300 packets per second burst and short-circuited the entire ML pipeline. This protects the scoring system itself from being overwhelmed during a flood attack."*

---

## Step 5 — Show Enforcement + Audit (30 seconds)

**Say**: *"Let me show you the enforcement is real — this isn't just logging. These IPs are being enforced at the kernel level with nftables."*

**Terminal**:
```bash
sudo nft list set inet filter minifw_block_v4
```

**Expected output**:
```
table inet filter {
  set minifw_block_v4 {
    type ipv4_addr
    flags timeout
    elements = { 127.0.0.1 timeout 86400s expires ..., ... }
  }
}
```

**Say**: *"The nftables `minifw_block_v4` set is what actually drops packets at the kernel level — before they reach any application. The timeout is configurable; default is 24 hours."*

**Show Tab 2** (Django Blocked IPs):
- *"And here's the operator view in the management dashboard — the same block entries, with timestamps and reasons, available to your ops team."*

**Show Tab 3** (MiniFW Audit Log):
- *"Every admin action, every policy change, every block event is recorded in the audit log. Full accountability trail."*

---

## Demo Wrap-Up (30 seconds)

**Say**: *"To summarize what you just saw:*

- *DNS feed matching: denied domain → scored and blocked in under 5 seconds*
- *Behavioral rate analysis: burst detection triggers on sustained high-rate queries*
- *Multi-layer scoring: signals combine for higher confidence blocks*
- *Hard gates: volumetric attacks blocked immediately at score=100*
- *Dual-dashboard: MiniFW admin for real-time events, Django for operator workflows*
- *Kernel enforcement: nftables, not just logging — actual packet drops"*

---

## Post-Demo Cleanup

```bash
# Restore production policy thresholds
./demos/demo_traffic_gen.sh --restore-policy

# Clear demo block entries (optional — they expire in 24h anyway)
sudo nft flush set inet filter minifw_block_v4

# Verify services still healthy
sudo systemctl status minifw-ai.service
sudo systemctl status ritapi-gunicorn.service
```

---

## Troubleshooting

### Events not appearing in dashboard
- Check MiniFW is reading dnsmasq log: `tail -f /var/log/dnsmasq.log`
- Check MiniFW service: `sudo journalctl -u minifw-ai.service -f`
- Verify `dnsmasq_log_path` in `policy.json` matches actual log location
- DNS queries must go *through* dnsmasq to be logged — `dig @127.0.0.1` works if dnsmasq is on port 53

### Score=41 but action=MONITOR instead of BLOCK
- Production policy has `block_threshold=60` — single denied domain (41 pts) → MONITOR
- Run `./demos/demo_traffic_gen.sh --setup-demo-policy` to lower threshold to 35
- Or use Scenario B/D (combined burst+denied = 51 pts; still MONITOR in default, but visible escalation)

### nft command fails
- `sudo apt install nftables`
- Check nftables is running: `sudo systemctl status nftables`
- The set `minifw_block_v4` is created by MiniFW at startup via ipset/nft

### hping3 not found (Scenario C)
```bash
sudo apt install hping3
```

### MiniFW events not reachable via Django
```bash
sudo systemctl status ritapi-gunicorn.service minifw-ai.service
sudo journalctl -u minifw-ai.service --no-pager -n 50
# Verify Nginx is proxying correctly:
curl -I http://localhost/ops/minifw/events/
```

---

## Alternative: Live Traffic Tap (Advanced)

If showing real traffic instead of generated traffic:
```bash
# Watch dnsmasq log in real-time for organic queries
tail -f /var/log/dnsmasq.log | grep -E "slot|casino|malware"
```
> **Note**: Organic threat traffic is unpredictable. The generated demo gives consistent, narrable results.
