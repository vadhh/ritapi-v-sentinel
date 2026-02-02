"""
YARA Scanner Engine for MiniFW-AI
Payload scanning for gambling, malware, and API abuse detection.

This module provides:
- YARAScanner class for payload scanning
- Rule compilation and caching
- Evidence-grade output with metadata
- Multi-category rule support
"""
from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

try:
    import yara
    YARA_AVAILABLE = True
except ImportError:
    YARA_AVAILABLE = False
    yara = None

logger = logging.getLogger(__name__)


@dataclass
class YARAMatch:
    """Represents a YARA rule match with evidence."""
    rule: str
    namespace: str
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    strings: List[tuple] = field(default_factory=list)  # (offset, identifier, data)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            'rule': self.rule,
            'namespace': self.namespace,
            'tags': self.tags,
            'meta': self.meta,
            'match_count': len(self.strings),
            'timestamp': self.timestamp
        }
    
    def get_severity(self) -> str:
        """Get severity from metadata."""
        return self.meta.get('severity', 'medium')
    
    def get_category(self) -> str:
        """Get category from metadata."""
        return self.meta.get('category', 'unknown')


class YARAScanner:
    """
    YARA-based payload scanner for threat detection.
    
    Scans payloads against compiled YARA rules for:
    - Gambling site detection
    - Malware patterns
    - API abuse attempts
    - General suspicious patterns
    """
    
    def __init__(
        self,
        rules_dir: Optional[str] = None,
        enable_caching: bool = True,
        max_scan_size: int = 10 * 1024 * 1024  # 10MB default
    ):
        """
        Initialize YARA scanner.
        
        Args:
            rules_dir: Directory containing YARA rule files
            enable_caching: Enable compiled rules caching
            max_scan_size: Maximum payload size to scan (bytes)
        """
        if not YARA_AVAILABLE:
            raise ImportError(
                "yara-python is required for YARA scanning. "
                "Install with: pip install yara-python"
            )
        
        self.enable_caching = enable_caching
        self.max_scan_size = max_scan_size
        
        # Default rules directory
        if rules_dir is None:
            rules_dir = os.getenv(
                'MINIFW_YARA_RULES',
                '/opt/minifw_ai/yara_rules'
            )
        
        self.rules_dir = Path(rules_dir)
        
        # Compiled rules cache
        self.compiled_rules: Optional[yara.Rules] = None
        self.rules_loaded = False
        
        # Statistics
        self.total_scans = 0
        self.total_matches = 0
        self.scans_by_category = {}
        
        # Try to load rules if directory exists
        if self.rules_dir.exists():
            try:
                self.compile_rules()
            except Exception as e:
                logger.warning(f"Failed to auto-load YARA rules: {e}")
    
    def compile_rules(self, rules_dir: Optional[str] = None) -> bool:
        """
        Compile YARA rules from directory.
        
        Args:
            rules_dir: Directory containing .yar files
            
        Returns:
            True if compilation successful
            
        Raises:
            FileNotFoundError: If rules directory doesn't exist
            yara.Error: If compilation fails
        """
        if rules_dir:
            self.rules_dir = Path(rules_dir)
        
        if not self.rules_dir.exists():
            raise FileNotFoundError(f"YARA rules directory not found: {self.rules_dir}")
        
        logger.info(f"Compiling YARA rules from: {self.rules_dir}")
        
        # Find all .yar and .yara files
        rule_files = []
        rule_files.extend(self.rules_dir.glob("**/*.yar"))
        rule_files.extend(self.rules_dir.glob("**/*.yara"))
        
        if not rule_files:
            logger.warning(f"No YARA rule files found in {self.rules_dir}")
            return False
        
        # Build namespace dict for compilation
        # Namespace = category (gambling, malware, api_abuse, etc.)
        rule_dict = {}
        
        for rule_file in rule_files:
            # Use parent directory name as namespace
            namespace = rule_file.parent.name
            
            if namespace not in rule_dict:
                rule_dict[namespace] = str(rule_file)
            else:
                # Multiple files in same category - need to handle differently
                # For now, just use first file per category
                logger.debug(f"Multiple files in {namespace}, using {rule_dict[namespace]}")
        
        try:
            # Compile all rules
            self.compiled_rules = yara.compile(filepaths=rule_dict)
            self.rules_loaded = True
            
            logger.info(f"✓ Compiled {len(rule_dict)} YARA rule namespaces")
            logger.debug(f"Namespaces: {list(rule_dict.keys())}")
            
            return True
            
        except yara.Error as e:
            logger.error(f"YARA compilation error: {e}")
            raise
    
    def scan_payload(
        self,
        payload: bytes | str,
        timeout: int = 60,
        return_strings: bool = True
    ) -> List[YARAMatch]:
        """
        Scan payload with YARA rules.
        
        Args:
            payload: Payload to scan (bytes or string)
            timeout: Scan timeout in seconds
            return_strings: Include matched strings in results
            
        Returns:
            List of YARAMatch objects
        """
        if not self.rules_loaded:
            logger.warning("YARA rules not loaded, skipping scan")
            return []
        
        # Convert string to bytes if needed
        if isinstance(payload, str):
            payload = payload.encode('utf-8', errors='ignore')
        
        # Check size limit
        if len(payload) > self.max_scan_size:
            logger.warning(f"Payload too large ({len(payload)} bytes), skipping")
            return []
        
        try:
            # Perform scan
            matches = self.compiled_rules.match(
                data=payload,
                timeout=timeout
            )
            
            # Update stats
            self.total_scans += 1
            self.total_matches += len(matches)
            
            # Convert to YARAMatch objects
            results = []
            
            for match in matches:
                # Extract matched strings if requested
                matched_strings = []
                if return_strings and match.strings:
                    for s in match.strings:
                        # Handle new yara-python object structure (v4.x+)
                        if hasattr(s, 'instances'):
                            for i in s.instances:
                                matched_strings.append((
                                    i.offset, 
                                    s.identifier, 
                                    i.matched_data.decode('utf-8', errors='ignore')
                                ))
                        # Handle legacy tuple structure (offset, identifier, data)
                        elif isinstance(s, tuple) and len(s) >= 3:
                             matched_strings.append((
                                s[0], 
                                s[1], 
                                s[2].decode('utf-8', errors='ignore')
                             ))
                
                yara_match = YARAMatch(
                    rule=match.rule,
                    namespace=match.namespace,
                    tags=list(match.tags) if match.tags else [],
                    meta=dict(match.meta) if match.meta else {},
                    strings=matched_strings
                )
                
                results.append(yara_match)
                
                # Update category stats
                category = yara_match.get_category()
                self.scans_by_category[category] = self.scans_by_category.get(category, 0) + 1
            
            if results:
                logger.info(f"YARA scan: {len(results)} matches in {len(payload)} bytes")
            
            return results
            
        except Exception as e:
            logger.error(f"YARA scan error: {e}")
            return []
    
    def scan_file(self, filepath: str, **kwargs) -> List[YARAMatch]:
        """
        Scan a file with YARA rules.
        
        Args:
            filepath: Path to file to scan
            **kwargs: Additional arguments for scan_payload
            
        Returns:
            List of YARAMatch objects
        """
        if not self.rules_loaded:
            return []
        
        file_path = Path(filepath)
        
        if not file_path.exists():
            logger.error(f"File not found: {filepath}")
            return []
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > self.max_scan_size:
            logger.warning(f"File too large ({file_size} bytes): {filepath}")
            return []
        
        try:
            with file_path.open('rb') as f:
                payload = f.read()
            
            return self.scan_payload(payload, **kwargs)
            
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {e}")
            return []
    
    def get_match_summary(self, matches: List[YARAMatch]) -> dict:
        """
        Get summary of YARA matches.
        
        Args:
            matches: List of YARAMatch objects
            
        Returns:
            Dictionary with match summary
        """
        if not matches:
            return {
                'total_matches': 0,
                'categories': {},
                'severities': {},
                'rules': []
            }
        
        categories = {}
        severities = {}
        
        for match in matches:
            # Count by category
            category = match.get_category()
            categories[category] = categories.get(category, 0) + 1
            
            # Count by severity
            severity = match.get_severity()
            severities[severity] = severities.get(severity, 0) + 1
        
        return {
            'total_matches': len(matches),
            'categories': categories,
            'severities': severities,
            'rules': [m.rule for m in matches],
            'highest_severity': max(severities.keys(), key=lambda k: {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(k, 0)) if severities else 'low'
        }
    
    def get_stats(self) -> dict:
        """
        Get scanner statistics.
        
        Returns:
            Dictionary with scanner stats
        """
        return {
            'rules_loaded': self.rules_loaded,
            'rules_dir': str(self.rules_dir),
            'total_scans': self.total_scans,
            'total_matches': self.total_matches,
            'match_rate': self.total_matches / self.total_scans if self.total_scans > 0 else 0.0,
            'scans_by_category': self.scans_by_category,
            'max_scan_size': self.max_scan_size
        }
    
    def reset_stats(self):
        """Reset scanner statistics."""
        self.total_scans = 0
        self.total_matches = 0
        self.scans_by_category = {}


# Singleton instance
_scanner_instance: Optional[YARAScanner] = None


def get_yara_scanner(
    rules_dir: Optional[str] = None,
    force_reload: bool = False
) -> YARAScanner:
    """
    Get singleton YARA scanner instance.
    
    Args:
        rules_dir: Path to YARA rules directory
        force_reload: Force reload of scanner
        
    Returns:
        YARAScanner instance
    """
    global _scanner_instance
    
    if _scanner_instance is None or force_reload:
        _scanner_instance = YARAScanner(rules_dir=rules_dir)
    
    return _scanner_instance
