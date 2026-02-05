#!/usr/bin/env python3
"""Fail-fast validation for /etc/ritapi/vsentinel.env."""

from __future__ import annotations

import sys
from pathlib import Path

ENV_FILE = Path("/etc/ritapi/vsentinel.env")

REQUIRED_VARS = [
    "DJANGO_SECRET_KEY",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "DB_HOST",
    "DB_PORT",
    "MINIFW_SECRET_KEY",
    "MINIFW_ADMIN_PASSWORD",
]

INSECURE_VALUES = {
    "changeme",
    "change_me",
    "replace_me",
    "default",
    "insecure",
    "your-secret-key-change-this-in-production",
}


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] in ("\"", "'") and value[-1] == value[0]:
            value = value[1:-1]
        data[key] = value
    return data


def is_insecure_value(value: str) -> bool:
    return value.strip().lower() in INSECURE_VALUES


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not ENV_FILE.exists():
        fail(f"CRITICAL: ENV file '{ENV_FILE}' is missing. Service start aborted.")

    env = parse_env_file(ENV_FILE)

    missing = [key for key in REQUIRED_VARS if not env.get(key)]
    if missing:
        for key in missing:
            fail(f"CRITICAL: ENV var '{key}' is missing or empty. Service start aborted.")

    insecure = [key for key in REQUIRED_VARS if is_insecure_value(env.get(key, ""))]
    if insecure:
        for key in insecure:
            fail(
                f"CRITICAL: ENV var '{key}' has insecure default value. "
                "Service start aborted."
            )

    print("VSentinel: Unified environment validated.")


if __name__ == "__main__":
    main()
