# Quick Start Guide -- RITAPI V-Sentinel

Get the platform running on a fresh Ubuntu/Debian server in three steps.

## Prerequisites

- Ubuntu 20.04+ or Debian 11+ (Ubuntu 22.04 / Debian 12 recommended)
- Root or sudo access
- Internet connectivity (for package downloads)
- 2 GB RAM minimum, 4 GB recommended

## 1. Clone or Extract the Repository

```bash
git clone <repository-url> ritapi-v-sentinel
cd ritapi-v-sentinel
```

Or if working from a ZIP archive:

```bash
unzip ritapi_complete_installer.zip
cd ritapi-v-sentinel
```

## 2. Run the Installer

```bash
chmod +x install.sh
sudo ./install.sh install
```

This installs all system dependencies (PostgreSQL, Redis, Nginx, nftables, ipset, Python), creates virtual environments, runs Django migrations, and configures systemd services. The process takes a few minutes depending on your connection speed.

To use the interactive menu instead, run `sudo ./install.sh` without arguments and select option 1.

## 3. Verify the Installation

```bash
sudo ./install.sh status
```

All services should report as active: `postgresql`, `ritapi-gunicorn`, `minifw-ai`, `nginx`.

Access the dashboard at:

```
http://<YOUR_SERVER_IP>/
```

## Post-Install

**Create an admin user** (if the installer did not prompt you):

```bash
cd /opt/ritapi_v_sentinel
sudo -u www-data ./venv/bin/python manage.py createsuperuser
```

**Check service logs:**

```bash
sudo journalctl -u ritapi-gunicorn -f
sudo journalctl -u minifw-ai -f
```

**Restart services:**

```bash
sudo systemctl restart ritapi-gunicorn
sudo systemctl restart minifw-ai
```

**Run the self-test** (generates a regulatory proof pack):

```bash
sudo /opt/ritapi-v-sentinel/scripts/vsentinel_selftest.sh
```

## Configuration

All configuration lives in `/etc/ritapi/vsentinel.env`. The installer generates secrets automatically. To review or modify settings:

```bash
sudo nano /etc/ritapi/vsentinel.env
```

After editing, restart the affected service:

```bash
sudo systemctl restart ritapi-gunicorn   # For Django changes
sudo systemctl restart minifw-ai         # For MiniFW changes
```

## Troubleshooting

**Service not starting?**

```bash
sudo systemctl status ritapi-gunicorn
sudo systemctl status minifw-ai
sudo journalctl -u ritapi-gunicorn -n 50
sudo journalctl -u minifw-ai -n 50
```

**400 Bad Request on the dashboard?** Your server IP may not be in the allowed hosts list:

```bash
sudo sed -i "s/^DJANGO_ALLOWED_HOSTS=\(.*\)$/DJANGO_ALLOWED_HOSTS=\1,YOUR_SERVER_IP/" /etc/ritapi/vsentinel.env
sudo systemctl restart ritapi-gunicorn
```

**Permission errors on MiniFW CRUD?**

```bash
cd scripts/minifw_fixed
sudo ./fix_permissions.sh
```

## Next Steps

- See `README.md` for full architecture, configuration reference, and API endpoints.
- See `docs/ROLLBACK_SOP.md` for backup and rollback procedures.
- See `RESILIENCE_QUICKSTART.md` for BASELINE_PROTECTION mode details.
