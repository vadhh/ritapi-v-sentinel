# 🖥️ MiniFW-AI VM Installation Guide

Complete step-by-step guide to install MiniFW-AI on a Virtual Machine, from VM setup to receiving and processing network logs.

---

## 📋 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [VM Setup](#2-vm-setup)
3. [System Preparation](#3-system-preparation)
4. [Install MiniFW-AI](#4-install-minifw-ai)
5. [Configure dnsmasq DNS Logging](#5-configure-dnsmasq-dns-logging)
6. [Configure nftables Firewall](#6-configure-nftables-firewall)
7. [Start MiniFW-AI Service](#7-start-minifw-ai-service)
8. [V-Sentinel Regulatory Compliance](#8-v-sentinel-regulatory-compliance)
9. [Verification & Testing](#9-verification--testing)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Ubuntu 22.04 LTS / Debian 12 |
| **RAM** | 2 GB (4 GB recommended) |
| **Disk** | 10 GB free space |
| **CPU** | 2 vCPUs |
| **Network** | Internet access for package downloads |
| **Access** | Root/sudo privileges |

### Software Requirements (Will be installed)

- Python 3.10+
- dnsmasq (DNS server)
- nftables (Firewall)
- ipset (IP set management)

---

## 2. VM Setup

### 2.1 Create the Virtual Machine

**For VirtualBox:**
```bash
# Create VM with these settings:
# - Name: minifw-ai-gateway
# - Type: Linux
# - Version: Ubuntu (64-bit)
# - RAM: 2048 MB
# - Disk: 20 GB (dynamically allocated)
```

**For VMware:**
```bash
# Create VM with these settings:
# - Guest OS: Ubuntu 64-bit
# - RAM: 2048 MB
# - Disk: 20 GB
# - Network: Bridged (to act as gateway)
```

**For Proxmox/KVM:**
```bash
# Create VM via CLI or web interface:
qm create 100 --name minifw-ai-gateway --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0
```

### 2.2 Network Configuration

**CRITICAL:** MiniFW-AI acts as a **network gateway**. Configure networking properly:

**Option A: Single NIC (Testing/Development)**
```bash
# VM gets IP via DHCP or static
# Clients point DNS to this VM
```

**Option B: Dual NIC Gateway (Production)**
```bash
# NIC 1: External (WAN) - gets internet
# NIC 2: Internal (LAN) - serves clients
```

### 2.3 Install Operating System

1. Download Ubuntu 22.04 LTS Server ISO
2. Boot VM from ISO
3. Follow installation wizard:
   - Language: English
   - Keyboard: Your layout
   - Network: Configure static IP (recommended)
   - Storage: Use entire disk
   - Profile: Create your admin user
   - SSH: Install OpenSSH server ✓

### 2.4 First Boot Configuration

After installation completes and VM reboots:

```bash
# Login with your created user

# Update system
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl wget git vim htop net-tools

# Set timezone
sudo timedatectl set-timezone Asia/Jakarta  # Change to your timezone

# Reboot to apply all updates
sudo reboot
```

---

## 3. System Preparation

### 3.1 Install System Dependencies

```bash
# Update package list
sudo apt update

# Install required packages
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    dnsmasq \
    nftables \
    ipset \
    git \
    curl

# Verify installations
python3 --version   # Should be 3.10+
dnsmasq --version   # Should show version info
nft --version       # Should show version info
```

### 3.2 Create Application Directory Structure

```bash
# Create MiniFW-AI directories
sudo mkdir -p /opt/minifw_ai/{app,config/feeds,logs,models,venv}

# Set ownership (will be adjusted later)
sudo chown -R $USER:$USER /opt/minifw_ai
```

### 3.3 Clone the Repository

```bash
# Clone the repository
cd /tmp
git clone https://github.com/vadhh/ritapi-v-sentinel.git

# Navigate to MiniFW-AI project
cd ritapi-v-sentinel/projects/minifw_ai_service
```

---

## 4. Install MiniFW-AI

### 4.1 Copy Application Files

```bash
# Copy application code
sudo cp -r app/minifw_ai /opt/minifw_ai/app/

# Copy configuration files
sudo cp config/policy.json /opt/minifw_ai/config/
sudo cp config/feeds/*.txt /opt/minifw_ai/config/feeds/

# Copy systemd service file
sudo cp systemd/minifw-ai.service /etc/systemd/system/
```

### 4.2 Create Python Virtual Environment

```bash
# Create virtual environment
sudo python3 -m venv /opt/minifw_ai/venv

# Activate virtual environment
source /opt/minifw_ai/venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 4.3 Install Python Dependencies

```bash
# Still with venv activated
pip install fastapi>=0.100.0
pip install uvicorn>=0.23.0
pip install pydantic>=2.7.0
pip install sqlalchemy>=2.0.0
pip install numpy>=1.24.0
pip install pandas>=2.0.0
pip install scikit-learn>=1.3.0
pip install joblib>=1.3.0
pip install watchdog>=3.0.0
pip install rich>=13.0.0

# Or install from requirements.txt
pip install -r /tmp/ritapi-v-sentinel/projects/minifw_ai_service/requirements.txt

# Deactivate venv
deactivate
```

### 4.4 Create Run Script

```bash
# Create the runner script
sudo tee /opt/minifw_ai/run_minifw.sh > /dev/null << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH=/opt/minifw_ai/app
exec /opt/minifw_ai/venv/bin/python -m minifw_ai
EOF

# Make executable
sudo chmod +x /opt/minifw_ai/run_minifw.sh
```

### 4.5 Configure Environment Variables

```bash
# Create environment directory
sudo mkdir -p /etc/minifw
sudo chmod 755 /etc/minifw

# Generate secrets
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_PASS=$(openssl rand -base64 12)

# Create environment file
sudo tee /etc/minifw/minifw.env > /dev/null << EOF
MINIFW_SECRET_KEY=${SECRET_KEY}
MINIFW_ADMIN_PASSWORD=${ADMIN_PASS}
MINIFW_POLICY=/opt/minifw_ai/config/policy.json
MINIFW_FEEDS=/opt/minifw_ai/config/feeds
MINIFW_LOG=/opt/minifw_ai/logs/events.jsonl
EOF

# Secure the file
sudo chmod 600 /etc/minifw/minifw.env

# Save admin password for later
echo "⚠️  ADMIN PASSWORD: ${ADMIN_PASS}"
echo "⚠️  Save this password! It is stored in /etc/minifw/minifw.env"
```

---

## 5. Configure dnsmasq DNS Logging

### 5.1 Enable DNS Query Logging

MiniFW-AI reads DNS queries from dnsmasq logs. This is the **entry point** for all traffic analysis.

```bash
# Backup original config
sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup

# Create log file
sudo touch /var/log/dnsmasq.log
sudo chmod 640 /var/log/dnsmasq.log
```

### 5.2 Configure dnsmasq

```bash
# Add logging configuration to dnsmasq
sudo tee -a /etc/dnsmasq.conf > /dev/null << 'EOF'

# ============================================
# MiniFW-AI DNS Logging Configuration
# ============================================

# Enable query logging
log-queries

# Log to specific file
log-facility=/var/log/dnsmasq.log

# Optional: Set upstream DNS servers
# server=8.8.8.8
# server=8.8.4.4

# Optional: Listen on all interfaces
# interface=*

# Optional: Disable DHCP if only using as DNS
# no-dhcp-interface=
EOF
```

### 5.3 Configure dnsmasq as Primary DNS

**For the VM to capture DNS from clients:**

```bash
# Edit dnsmasq to listen on the LAN interface
# Find your LAN interface name first
ip addr show

# Add to dnsmasq.conf:
sudo tee -a /etc/dnsmasq.conf > /dev/null << 'EOF'
# Listen on all interfaces (or specify your LAN interface)
listen-address=0.0.0.0

# Don't read /etc/resolv.conf
no-resolv

# Upstream DNS servers
server=8.8.8.8
server=1.1.1.1
EOF
```

### 5.4 Restart dnsmasq

```bash
# Restart dnsmasq service
sudo systemctl restart dnsmasq

# Enable on boot
sudo systemctl enable dnsmasq

# Check status
sudo systemctl status dnsmasq

# Verify logging is working
sudo tail -f /var/log/dnsmasq.log
# (Make a DNS query from another terminal or client to test)
```

---

## 6. Configure nftables Firewall

MiniFW-AI uses **nftables** to block malicious IPs.

### 6.1 Initialize nftables

```bash
# Ensure nftables is running
sudo systemctl enable nftables
sudo systemctl start nftables

# Create the filter table and chain
sudo nft add table inet filter 2>/dev/null || true
sudo nft add chain inet filter forward '{ type filter hook forward priority 0; policy accept; }' 2>/dev/null || true
```

### 6.2 Create the Block Set

```bash
# Create IP set with timeout (IPs auto-expire after 24 hours)
sudo nft add set inet filter minifw_block_v4 '{ type ipv4_addr; flags timeout; timeout 86400s; }' 2>/dev/null || true

# Add the drop rule for blocked IPs
sudo nft add rule inet filter forward ip saddr @minifw_block_v4 drop 2>/dev/null || true

# Verify the setup
sudo nft list ruleset
```

### 6.3 Alternative: Using ipset (Fallback)

```bash
# If you prefer ipset over native nftables sets:
sudo ipset create minifw_block_v4 hash:ip timeout 86400 -exist

# Verify
sudo ipset list minifw_block_v4
```

---

## 7. Start MiniFW-AI Service

### 7.1 Update Systemd Service File

```bash
# Ensure the service file has the EnvironmentFile directive
sudo tee /etc/systemd/system/minifw-ai.service > /dev/null << 'EOF'
[Unit]
Description=MiniFW-AI (RitAPI-AI V-Sentinel - Gateway Metadata Layer)
After=network.target dnsmasq.service
Wants=dnsmasq.service

[Service]
Type=simple
EnvironmentFile=/etc/minifw/minifw.env
Environment=MINIFW_POLICY=/opt/minifw_ai/config/policy.json
Environment=MINIFW_FEEDS=/opt/minifw_ai/config/feeds
Environment=MINIFW_LOG=/opt/minifw_ai/logs/events.jsonl
ExecStart=/opt/minifw_ai/run_minifw.sh
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
```

### 7.2 Start the Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable MiniFW-AI to start on boot
sudo systemctl enable minifw-ai

# Start MiniFW-AI
sudo systemctl start minifw-ai

# Check status
sudo systemctl status minifw-ai
```

---

## 8. Verification & Testing

### 8.1 Verify Service is Running

```bash
# Check service status
sudo systemctl status minifw-ai --no-pager

# Expected output should show "active (running)"
```

### 8.2 Check Logs

```bash
# View MiniFW-AI service logs
sudo journalctl -u minifw-ai -f

# View event log file
sudo tail -f /opt/minifw_ai/logs/events.jsonl
```

### 8.3 Test DNS Logging

```bash
# From another terminal, make DNS queries
dig google.com @127.0.0.1
dig youtube.com @127.0.0.1

# Check if dnsmasq logged them
sudo tail -f /var/log/dnsmasq.log

# You should see lines like:
# query[A] google.com from 127.0.0.1
```

### 8.4 Test Threat Detection

```bash
# Query a domain that matches the deny list
dig slot-gacor-test.com @127.0.0.1
dig casino-test.com @127.0.0.1

# Check MiniFW-AI events
sudo tail /opt/minifw_ai/logs/events.jsonl | jq .

# You should see events with "action": "monitor" or "action": "block"
```

### 8.5 Verify Blocking Works

```bash
# Check if any IPs have been blocked
sudo nft list set inet filter minifw_block_v4

# Or with ipset
sudo ipset list minifw_block_v4
```

### 8.6 Test from a Client Machine

1. **Configure Client DNS:**
   - Point client's DNS to the MiniFW-AI VM's IP address
   
2. **Make DNS Queries from Client:**
   ```bash
   # On client machine
   nslookup google.com <MINIFW_VM_IP>
   ```

3. **Verify Logs Show Client IP:**
   ```bash
   # On MiniFW-AI VM
   sudo tail -f /var/log/dnsmasq.log
   # Should show: query[A] google.com from <CLIENT_IP>
   ```

---

## 8. V-Sentinel Regulatory Compliance

### 🔒 Overview

V-Sentinel implements **regulator-grade closure controls** to ensure the system operates exclusively as a gambling-only network security solution. This section documents the compliance mechanisms.

### 8.1 Gambling-Only Configuration

The V-Sentinel system includes fail-closed validation controls at multiple stages:

**Install-Time Validation:**
```bash
# The installer validates gambling-only configuration before proceeding
# If GAMBLING_ONLY is not set to 1, installation will fail with:
# Error: V-Sentinel must be configured as gambling-only (GAMBLING_ONLY=1)
```

**Runtime Validation:**
```bash
# Even if installed, the service will refuse to start if:
# 1. /etc/ritapi/vsentinel.env is missing
# 2. GAMBLING_ONLY is not set to 1
# 3. ALLOWED_DETECTION_TYPES is not set to "gambling"

# Check service validation
sudo journalctl -u minifw-ai -n 20 --no-pager | grep "V-SENTINEL"
```

### 8.2 Configuration Files

**Location:** `/etc/ritapi/vsentinel.env`

This file contains critical regulatory settings:

```bash
# Critical: Set to 1 to enable gambling-only mode
GAMBLING_ONLY=1

# Allowed detection types - MUST be set to "gambling" for compliance
ALLOWED_DETECTION_TYPES=gambling

# Machine Learning Policy Engine Configuration
MODEL_NAME=v_sentinel_mlp
MODEL_VERSION=mlp_v2

# Regulatory Policy Identifiers
POLICY_ID=V-SENTINEL-GOV-01
POLICY_VERSION=1.0
```

**Important:** This file is readable only by root (chmod 640) and cannot be modified without administrative access.

### 8.3 Regulatory Validation Scripts

Three validation scripts enforce gambling-only operation:

#### Scope Gate (Install-Time)
```bash
# Location: /opt/minifw_ai/scripts/vsentinel_scope_gate.sh
# Purpose: Validates configuration before installation proceeds
# Exit Code: 0 = safe to proceed, 1 = installation fails

# Run manually to verify configuration:
sudo /opt/minifw_ai/scripts/vsentinel_scope_gate.sh
```

#### Runtime Guard (Service Start)
```bash
# Location: /opt/minifw_ai/scripts/vsentinel_runtime_guard.sh
# Purpose: Validates configuration before service starts
# Called by: systemd as ExecStartPre

# systemd will call this automatically before starting minifw-ai
# If validation fails, the service will not start

# View validation logs:
sudo journalctl -u minifw-ai -e
```

#### Self-Test (Post-Install)
```bash
# Location: /opt/minifw_ai/scripts/vsentinel_selftest.sh
# Purpose: Verifies installation and generates regulatory proof packs
# Run after: Services have started

# Run manually to generate proof pack:
sudo /opt/minifw_ai/scripts/vsentinel_selftest.sh

# Check proof packs:
ls -la /var/log/ritapi/proof_packs/
cat /var/log/ritapi/proof_packs/selftest_*.json | jq .
```

### 8.4 Proof Packs for Regulatory Auditing

The self-test script generates JSON proof packs containing:

```json
{
  "selftest_timestamp": "2026-02-03T12:34:56Z",
  "hostname": "minifw-ai-vm",
  "kernel_version": "5.15.0-56-generic",
  "selftest_result": "PASS",
  "services": {
    "ritapi-gunicorn": { "active": true, "enabled": true },
    "minifw-ai": { "active": true, "enabled": true },
    "nginx": { "active": true, "enabled": true }
  },
  "configuration": {
    "gambling_only": "1",
    "config_file": "/etc/ritapi/vsentinel.env",
    "config_readable": true
  },
  "ipset": {
    "minifw_block_v4_exists": true
  },
  "failed_checks": []
}
```

**Location:** `/var/log/ritapi/proof_packs/selftest_TIMESTAMP.json`

These proof packs can be:
- ✅ Exported to auditors as evidence of compliance
- ✅ Automatically archived for compliance records
- ✅ Used to verify system configuration at any point in time

### 8.5 Log Rotation for Compliance

All system logs are rotated with regulatory retention periods:

```bash
# Configuration: /etc/logrotate.d/ritapi-vsentinel
# Audit logs: 30-day retention
# Standard logs: 14-day retention
# Schedule: Daily

# Check log rotation schedule:
sudo logrotate -d /etc/logrotate.d/ritapi-vsentinel

# View current logs:
ls -la /var/log/nginx/*.log
ls -la /opt/ritapi_v_sentinel/logs/
ls -la /opt/minifw_ai/logs/
ls -la /var/log/ritapi/
```

### 8.6 Fail-Closed Design

The system implements fail-closed controls:

| Stage | Validation | Failure Behavior |
|-------|-----------|------------------|
| **Install** | Scope gate checks GAMBLING_ONLY=1 | Installation halts, no override possible |
| **Service Start** | Runtime guard checks configuration | systemd refuses to start the service |
| **Operation** | Self-test verifies all components | Non-critical failures are logged, critical failures prevent operation |

### 8.7 Verification Checklist

After installation, verify compliance:

```bash
# 1. Check configuration file exists
sudo test -f /etc/ritapi/vsentinel.env && echo "✓ Config exists" || echo "✗ Config missing"

# 2. Verify GAMBLING_ONLY setting
sudo grep "GAMBLING_ONLY=1" /etc/ritapi/vsentinel.env && echo "✓ GAMBLING_ONLY is set" || echo "✗ GAMBLING_ONLY not set correctly"

# 3. Check runtime guard script
sudo test -x /opt/minifw_ai/scripts/vsentinel_runtime_guard.sh && echo "✓ Guard script exists" || echo "✗ Guard script missing"

# 4. Verify service won't start without validation
sudo systemctl status minifw-ai | grep "active (running)" && echo "✓ Service is running" || echo "✗ Service not running"

# 5. Check proof pack directory
sudo test -d /var/log/ritapi/proof_packs && echo "✓ Proof pack directory exists" || echo "✗ Proof pack directory missing"

# 6. View latest proof pack
sudo ls -t /var/log/ritapi/proof_packs/ | head -1 | xargs -I {} sudo cat /var/log/ritapi/proof_packs/{} | jq '.selftest_result'
```

All checks should return `✓` (success).

---

## 9. Troubleshooting

### 9.1 Service Won't Start

```bash
# Check detailed logs
sudo journalctl -u minifw-ai -n 50 --no-pager

# Common issues:
# 1. Python path incorrect - verify PYTHONPATH in run_minifw.sh
# 2. Missing dependencies - reinstall requirements
# 3. Permission issues - check /opt/minifw_ai permissions
```

### 9.2 V-Sentinel Validation Failures

If you see V-Sentinel errors in the logs:

```bash
# Check configuration file
sudo cat /etc/ritapi/vsentinel.env

# Verify GAMBLING_ONLY is set correctly
sudo grep "GAMBLING_ONLY=1" /etc/ritapi/vsentinel.env || echo "ERROR: GAMBLING_ONLY not set to 1"

# Verify ALLOWED_DETECTION_TYPES
sudo grep "ALLOWED_DETECTION_TYPES=gambling" /etc/ritapi/vsentinel.env || echo "ERROR: ALLOWED_DETECTION_TYPES not set to gambling"

# Run the runtime guard manually to see detailed errors
sudo /opt/minifw_ai/scripts/vsentinel_runtime_guard.sh

# Check file permissions (should be 640, owned by root)
sudo ls -la /etc/ritapi/vsentinel.env
```

### 9.3 No DNS Logs Appearing

```bash
# Check dnsmasq status
sudo systemctl status dnsmasq

# Verify dnsmasq.conf has log-queries
grep "log-queries" /etc/dnsmasq.conf

# Check log file permissions
ls -la /var/log/dnsmasq.log

# Ensure dnsmasq is listening
ss -tuln | grep :53
```

### 9.4 Events Not Being Written

```bash
# Check if events.jsonl exists
ls -la /opt/minifw_ai/logs/

# Check if MiniFW-AI can write to log directory
sudo -u root touch /opt/minifw_ai/logs/test.txt && rm /opt/minifw_ai/logs/test.txt

# Verify policy.json is valid JSON
python3 -m json.tool /opt/minifw_ai/config/policy.json
```

### 9.4 nftables Rules Not Working

```bash
# Verify nftables is loaded
sudo nft list ruleset

# If empty, re-run setup:
sudo nft add table inet filter
sudo nft add chain inet filter forward '{ type filter hook forward priority 0; policy accept; }'
sudo nft add set inet filter minifw_block_v4 '{ type ipv4_addr; flags timeout; timeout 86400s; }'
sudo nft add rule inet filter forward ip saddr @minifw_block_v4 drop
```

### 9.5 Permission Denied Errors

```bash
# Fix ownership of MiniFW-AI directory
sudo chown -R root:root /opt/minifw_ai

# Ensure log directory is writable
sudo chmod 755 /opt/minifw_ai/logs

# Fix environment file permissions
sudo chmod 600 /etc/minifw/minifw.env
```

---

## 📊 Verification Checklist

After completing the installation, verify all components:

| Component | Command | Expected Result |
|-----------|---------|-----------------|
| MiniFW-AI Service | `sudo systemctl status minifw-ai` | Active (running) |
| dnsmasq Service | `sudo systemctl status dnsmasq` | Active (running) |
| DNS Logging | `sudo tail /var/log/dnsmasq.log` | Shows DNS queries |
| Event Logging | `sudo tail /opt/minifw_ai/logs/events.jsonl` | Shows JSON events |
| nftables Rules | `sudo nft list ruleset` | Shows minifw_block_v4 set |
| DNS Resolution | `dig google.com @127.0.0.1` | Returns valid response |

---

## 📁 Final Directory Structure

```
/opt/minifw_ai/
├── app/
│   └── minifw_ai/
│       ├── __init__.py
│       ├── main.py           # Main event loop
│       ├── collector_dnsmasq.py
│       ├── collector_flow.py
│       ├── feeds.py
│       ├── policy.py
│       ├── enforce.py        # nftables integration
│       ├── events.py
│       ├── burst.py
│       └── utils/
│           ├── mlp_engine.py
│           └── yara_scanner.py
├── config/
│   ├── policy.json           # Scoring thresholds
│   └── feeds/
│       ├── allow_domains.txt
│       ├── deny_domains.txt
│       ├── deny_ips.txt
│       └── deny_asn.txt
├── logs/
│   └── events.jsonl          # Detection events
├── venv/                     # Python virtual environment
└── run_minifw.sh            # Startup script

/etc/minifw/
└── minifw.env               # Environment variables

/etc/systemd/system/
└── minifw-ai.service        # Systemd unit file

/var/log/
└── dnsmasq.log              # DNS query logs (entry point)
```

---

## 🎉 Success!

If all verification steps pass, your MiniFW-AI system is now:

1. ✅ **Receiving DNS queries** via dnsmasq
2. ✅ **Processing events** through the scoring engine
3. ✅ **Logging detections** to events.jsonl
4. ✅ **Ready to block** malicious IPs via nftables

### Next Steps

1. **Configure client devices** to use this VM as their DNS server
2. **Customize policy.json** to adjust thresholds for your environment
3. **Add domains to deny_domains.txt** for custom blocking
4. **Monitor events.jsonl** for threat detections
5. **Optional:** Install the MLP model for AI-powered detection

---

## 📚 References

- [MiniFW-AI Documentation](https://github.com/vadhh/ritapi-v-sentinel/tree/main/projects/minifw_ai_service)
- [dnsmasq Manual](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html)
- [nftables Wiki](https://wiki.nftables.org/)

---

**Version:** 1.0  
**Last Updated:** 2026-02-02  
**Platform:** Ubuntu 22.04 LTS / Debian 12