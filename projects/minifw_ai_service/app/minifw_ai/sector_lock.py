"""
Sector Lock - Factory-Set Deployment Configuration

This module provides an immutable sector configuration that is set at
factory/deployment time and cannot be changed via the Admin UI.

Priority:
1. Environment Variable: MINIFW_SECTOR (for containers/dev)
2. Lock File: /opt/minifw_ai/config/sector_lock.json (production hardware)
3. Fallback: Fail closed (system cannot start without valid sector)
"""

from __future__ import annotations
import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Production lock file path
LOCK_FILE_PATH = Path(
    os.environ.get("MINIFW_SECTOR_LOCK_FILE", "/opt/minifw_ai/config/sector_lock.json")
)

# Development fallback path (relative to project)
DEV_LOCK_FILE_PATH = (
    Path(__file__).parent.parent.parent.parent / "config" / "sector_lock.json"
)


class SectorLock:
    """
    Singleton class that enforces factory-set sector configuration.

    Once initialized, the sector CANNOT be changed programmatically.
    This prevents a compromised Admin UI from changing device identity.
    """

    _instance: Optional["SectorLock"] = None
    _sector: Optional[str] = None
    _config: Dict[str, Any] = {}
    _initialized: bool = False

    def __new__(cls) -> "SectorLock":
        if cls._instance is None:
            cls._instance = super(SectorLock, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._load_sector()
            SectorLock._initialized = True

    def _get_valid_sectors(self) -> list[str]:
        """Get list of valid sector values."""
        # Import here to avoid circular imports
        from models.user import SectorType

        return [s.value for s in SectorType]

    def _load_sector(self) -> None:
        """
        Load sector from environment or lock file.

        Priority 1: Environment Variable (Container/Dev)
        Priority 2: Lock File (Production Hardware)
        Fallback: Error (Fail Closed)
        """
        valid_sectors = self._get_valid_sectors()

        # Priority 1: Environment Variable
        env_sector = os.getenv("MINIFW_SECTOR")

        if env_sector:
            sector_lower = env_sector.lower().strip()
            if sector_lower in valid_sectors:
                self._sector = sector_lower
                logger.info(f"[SECTOR_LOCK] Loaded from ENV: {self._sector}")
                self._load_config()
                return
            else:
                logger.critical(
                    f"[SECTOR_LOCK] Invalid MINIFW_SECTOR in ENV: {env_sector}"
                )
                logger.critical(f"[SECTOR_LOCK] Valid sectors: {valid_sectors}")
                raise RuntimeError(f"Invalid Sector Configuration: {env_sector}")

        # Priority 2: Production Lock File
        lock_file = LOCK_FILE_PATH if LOCK_FILE_PATH.exists() else DEV_LOCK_FILE_PATH

        if lock_file.exists():
            try:
                with open(lock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sector_value = data.get("sector", "").lower().strip()

                    if sector_value in valid_sectors:
                        self._sector = sector_value
                        logger.info(
                            f"[SECTOR_LOCK] Loaded from LOCKFILE: {self._sector}"
                        )
                        self._load_config()
                        return
                    else:
                        logger.critical(
                            f"[SECTOR_LOCK] Invalid sector in lock file: {sector_value}"
                        )
                        raise RuntimeError(
                            f"Invalid Sector in Lock File: {sector_value}"
                        )

            except json.JSONDecodeError as e:
                logger.critical(f"[SECTOR_LOCK] Corrupted lock file: {e}")
                raise RuntimeError("Corrupted Sector Lock File")
            except Exception as e:
                logger.critical(f"[SECTOR_LOCK] Failed to read lock file: {e}")
                raise RuntimeError(f"Failed to read Sector Lock File: {e}")

        # Fallback: Fail Closed
        logger.critical("[SECTOR_LOCK] NO SECTOR CONFIGURED. System cannot start.")
        logger.critical(
            f"[SECTOR_LOCK] Set MINIFW_SECTOR env var or create {LOCK_FILE_PATH}"
        )
        raise RuntimeError("Missing Sector Configuration. Device is unprovisioned.")

    def _load_config(self) -> None:
        """Load sector-specific policy configuration."""
        from minifw_ai.sector_config import SECTOR_POLICIES
        from models.user import SectorType

        try:
            sector_enum = SectorType(self._sector)
            self._config = SECTOR_POLICIES.get(sector_enum, {})
            logger.info(
                f"[SECTOR_LOCK] Loaded config for {self._sector}: {list(self._config.keys())}"
            )
        except ValueError:
            self._config = {}
            logger.warning(
                f"[SECTOR_LOCK] No policy config found for sector: {self._sector}"
            )

    def get_sector(self) -> str:
        """Get the locked sector value."""
        return self._sector or ""

    def get_sector_config(self) -> Dict[str, Any]:
        """Get sector-specific policy configuration."""
        return self._config.copy()

    def is_locked(self) -> bool:
        """Check if sector is locked (always True once initialized)."""
        return self._initialized and self._sector is not None

    def is_school(self) -> bool:
        """Check if this device is configured for school sector."""
        return self._sector == "school"

    def is_hospital(self) -> bool:
        """Check if this device is configured for hospital sector."""
        return self._sector == "hospital"

    def is_government(self) -> bool:
        """Check if this device is configured for government sector."""
        return self._sector == "government"

    def is_finance(self) -> bool:
        """Check if this device is configured for finance sector."""
        return self._sector == "finance"

    def is_legal(self) -> bool:
        """Check if this device is configured for legal sector."""
        return self._sector == "legal"

    def is_establishment(self) -> bool:
        """Check if this device is configured for establishment sector."""
        return self._sector == "establishment"

    def __repr__(self) -> str:
        return f"<SectorLock sector={self._sector} locked={self.is_locked()}>"


# Global singleton accessor
_sector_lock: Optional[SectorLock] = None


def get_sector_lock() -> SectorLock:
    """
    Get the global SectorLock singleton instance.

    This is the recommended way to access sector configuration.
    """
    global _sector_lock
    if _sector_lock is None:
        _sector_lock = SectorLock()
    return _sector_lock


def get_sector() -> str:
    """Convenience function to get current sector."""
    return get_sector_lock().get_sector()


def get_sector_config() -> Dict[str, Any]:
    """Convenience function to get sector config."""
    return get_sector_lock().get_sector_config()
