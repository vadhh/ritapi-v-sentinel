V-SENTINEL USB DEMO
===================

Prerequisites
-------------
- Docker Desktop running (Windows: Docker Desktop with WSL2 integration enabled)
- OR Docker Engine running (Linux)

Quick Start
-----------
1. Open a terminal (Windows: open WSL2 terminal)
2. Navigate to this USB drive:
     cd /path/to/usb    (Linux)
     cd /mnt/d/         (WSL2 — adjust drive letter)
3. Run the demo:
     bash demo.sh

   First run loads Docker images (~2-4 GB). Subsequent runs are instant.

4. Open your browser:
     Django Admin:  http://localhost:8000/admin/
     MiniFW Web:    http://localhost:8080/

   Login: admin / admin123

Stop the Demo
-------------
    bash stop.sh

Or press Ctrl+C in the demo.sh terminal, then run bash stop.sh.

Reset Demo Data
---------------
    bash demos/demo_ctl.sh reset
    bash demos/demo_ctl.sh seed

Troubleshooting
---------------
- "Docker is not running": Start Docker Desktop and wait for it to fully start.
- "Container not ready after 60s": Run `docker logs vsentinel-django` to see errors.
- Port 8000 or 8080 in use: Stop any other running Docker stacks first.
