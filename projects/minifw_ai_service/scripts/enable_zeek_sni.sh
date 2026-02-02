#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo $0"; exit 1; fi

apt-get update
apt-get install -y zeek || true

python3 - <<'PY'
import json, pathlib
p = pathlib.Path("/opt/minifw_ai/config/policy.json")
cfg = json.loads(p.read_text(encoding="utf-8"))
cfg.setdefault("collectors", {})
cfg["collectors"]["use_zeek_sni"] = True
p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print("policy.json updated: use_zeek_sni = true")
PY

echo "Restart: sudo systemctl restart minifw-ai"
