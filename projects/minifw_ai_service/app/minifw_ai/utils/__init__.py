"""
MiniFW-AI Utilities Package
"""
from .mlp_engine import MLPThreatDetector, get_mlp_detector

try:
    from .yara_scanner import YARAScanner, YARAMatch, get_yara_scanner
    YARA_AVAILABLE = True
except ImportError:
    YARA_AVAILABLE = False
    YARAScanner = None
    YARAMatch = None
    get_yara_scanner = None

__all__ = [
    'MLPThreatDetector',
    'get_mlp_detector',
    'YARAScanner',
    'YARAMatch', 
    'get_yara_scanner',
    'YARA_AVAILABLE'
]
