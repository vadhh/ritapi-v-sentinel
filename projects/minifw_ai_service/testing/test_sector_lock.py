#!/usr/bin/env python3
"""
Sector Lock Unit Tests

Tests for the factory-set sector configuration system.
Verifies:
- Sector loading from environment variable
- Sector loading from config file
- Sector config retrieval
- Immutability constraints
- Invalid sector handling

Usage:
    cd /home/stardhoom/minifw-ai
    PYTHONPATH=app MINIFW_SECTOR=school pytest testing/test_sector_lock.py -v
"""
import sys
import os
from pathlib import Path

# Add app to path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / 'app'))

import pytest


class TestSectorLock:
    """Test cases for SectorLock singleton."""
    
    def setup_method(self):
        """Reset singleton state before each test."""
        # Reset the singleton for clean tests
        from minifw_ai import sector_lock
        sector_lock._sector_lock = None
        sector_lock.SectorLock._instance = None
        sector_lock.SectorLock._initialized = False
    
    def test_sector_loads_from_env_school(self, monkeypatch):
        """Test that sector loads correctly from MINIFW_SECTOR env var."""
        monkeypatch.setenv("MINIFW_SECTOR", "school")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        
        assert lock.get_sector() == "school"
        assert lock.is_locked() is True
        assert lock.is_school() is True
        assert lock.is_hospital() is False
    
    def test_sector_loads_from_env_hospital(self, monkeypatch):
        """Test hospital sector loading."""
        monkeypatch.setenv("MINIFW_SECTOR", "hospital")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        
        assert lock.get_sector() == "hospital"
        assert lock.is_hospital() is True
        assert lock.is_school() is False
    
    def test_sector_loads_from_env_case_insensitive(self, monkeypatch):
        """Test that sector matching is case-insensitive."""
        monkeypatch.setenv("MINIFW_SECTOR", "SCHOOL")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        
        assert lock.get_sector() == "school"
        assert lock.is_school() is True
    
    def test_invalid_sector_raises_error(self, monkeypatch):
        """Test that invalid sector raises RuntimeError."""
        monkeypatch.setenv("MINIFW_SECTOR", "invalid_sector")
        
        from minifw_ai.sector_lock import get_sector_lock
        
        with pytest.raises(RuntimeError, match="Invalid Sector"):
            get_sector_lock()
    
    def test_missing_sector_raises_error(self, monkeypatch):
        """Test that missing sector config raises RuntimeError."""
        # Remove env var and ensure no lock file exists
        monkeypatch.delenv("MINIFW_SECTOR", raising=False)
        # Monkey-patch the paths to non-existent locations
        from minifw_ai import sector_lock
        monkeypatch.setattr(sector_lock, 'LOCK_FILE_PATH', Path('/nonexistent/path.json'))
        monkeypatch.setattr(sector_lock, 'DEV_LOCK_FILE_PATH', Path('/nonexistent/dev.json'))

        with pytest.raises(RuntimeError, match="Missing Sector"):
            sector_lock.get_sector_lock()
    
    def test_school_config_has_safesearch(self, monkeypatch):
        """Test that school sector config has SafeSearch enabled."""
        monkeypatch.setenv("MINIFW_SECTOR", "school")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        config = lock.get_sector_config()
        
        assert config.get("force_safesearch") is True
        assert config.get("block_vpns") is True
        assert "school_blacklist.txt" in config.get("extra_feeds", [])
    
    def test_hospital_config_has_iomt(self, monkeypatch):
        """Test that hospital sector config has IoMT priority."""
        monkeypatch.setenv("MINIFW_SECTOR", "hospital")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        config = lock.get_sector_config()
        
        assert config.get("iomt_high_priority") is True
        assert config.get("strict_pii_logging") is False  # HIPAA compliance
    
    def test_finance_config_has_tor_blocking(self, monkeypatch):
        """Test that finance sector blocks Tor."""
        monkeypatch.setenv("MINIFW_SECTOR", "finance")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        config = lock.get_sector_config()
        
        assert config.get("block_tor") is True
        assert config.get("pci_compliance_mode") is True
    
    def test_government_config_has_geo_ip(self, monkeypatch):
        """Test that government sector has geo-IP restrictions."""
        monkeypatch.setenv("MINIFW_SECTOR", "government")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        config = lock.get_sector_config()
        
        assert config.get("geo_ip_strict") is True
        assert config.get("log_retention_days") == 365
    
    def test_legal_config_has_exfiltration_watch(self, monkeypatch):
        """Test that legal sector watches for data exfiltration."""
        monkeypatch.setenv("MINIFW_SECTOR", "legal")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        config = lock.get_sector_config()
        
        assert config.get("data_exfiltration_watch") is True
        assert config.get("confidentiality_mode") is True
    
    def test_establishment_config_is_balanced(self, monkeypatch):
        """Test that establishment sector has balanced defaults."""
        monkeypatch.setenv("MINIFW_SECTOR", "establishment")
        
        from minifw_ai.sector_lock import get_sector_lock
        lock = get_sector_lock()
        config = lock.get_sector_config()
        
        assert config.get("standard_protection") is True
        assert config.get("block_threshold_adjustment", 0) == 0
    
    def test_singleton_pattern(self, monkeypatch):
        """Test that SectorLock is a true singleton."""
        monkeypatch.setenv("MINIFW_SECTOR", "school")
        
        from minifw_ai.sector_lock import get_sector_lock, SectorLock
        
        lock1 = get_sector_lock()
        lock2 = get_sector_lock()
        lock3 = SectorLock()
        
        assert lock1 is lock2
        assert lock1 is lock3


class TestSectorConfig:
    """Test cases for sector_config.py helper functions."""
    
    def test_get_threshold_adjustment_school(self):
        """Test threshold adjustment for school sector."""
        from minifw_ai.sector_config import get_threshold_adjustment
        from models.user import SectorType
        
        block_adj = get_threshold_adjustment(SectorType.SCHOOL, "block")
        monitor_adj = get_threshold_adjustment(SectorType.SCHOOL, "monitor")
        
        assert block_adj < 0  # School should be stricter
        assert monitor_adj < 0
    
    def test_get_threshold_adjustment_hospital(self):
        """Test threshold adjustment for hospital sector."""
        from minifw_ai.sector_config import get_threshold_adjustment
        from models.user import SectorType
        
        monitor_adj = get_threshold_adjustment(SectorType.HOSPITAL, "monitor")
        
        assert monitor_adj == -20  # Much more sensitive
    
    def test_get_extra_feeds_school(self):
        """Test extra feeds for school sector."""
        from minifw_ai.sector_config import get_extra_feeds
        from models.user import SectorType
        
        feeds = get_extra_feeds(SectorType.SCHOOL)
        
        assert "school_blacklist.txt" in feeds
    
    def test_should_force_safesearch(self):
        """Test SafeSearch check for different sectors."""
        from minifw_ai.sector_config import should_force_safesearch
        from models.user import SectorType
        
        assert should_force_safesearch(SectorType.SCHOOL) is True
        assert should_force_safesearch(SectorType.HOSPITAL) is False
        assert should_force_safesearch(SectorType.ESTABLISHMENT) is False
    
    def test_should_block_vpns(self):
        """Test VPN blocking check for different sectors."""
        from minifw_ai.sector_config import should_block_vpns
        from models.user import SectorType
        
        assert should_block_vpns(SectorType.SCHOOL) is True
        assert should_block_vpns(SectorType.HOSPITAL) is False
    
    def test_is_iomt_priority(self):
        """Test IoMT priority check for different sectors."""
        from minifw_ai.sector_config import is_iomt_priority
        from models.user import SectorType
        
        assert is_iomt_priority(SectorType.HOSPITAL) is True
        assert is_iomt_priority(SectorType.SCHOOL) is False
        assert is_iomt_priority(SectorType.FINANCE) is False


class TestSectorTypeEnum:
    """Test the updated SectorType enum."""
    
    def test_all_six_sectors_exist(self):
        """Verify all 6 required sectors exist."""
        from models.user import SectorType
        
        expected_sectors = {"hospital", "school", "government", "finance", "legal", "establishment"}
        actual_sectors = {s.value for s in SectorType}
        
        assert actual_sectors == expected_sectors
    
    def test_obsolete_sectors_removed(self):
        """Verify obsolete sectors (corporate, general) are removed."""
        from models.user import SectorType
        
        sector_values = {s.value for s in SectorType}
        
        assert "corporate" not in sector_values
        assert "general" not in sector_values


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
