from __future__ import annotations
from pathlib import Path
import fnmatch
import logging

logger = logging.getLogger(__name__)

class FeedMatcher:
    def __init__(self, feeds_dir: str):
        self.feeds_dir = Path(feeds_dir)
        self.deny_domains = self._load_lines(self.feeds_dir / "deny_domains.txt")
        self.allow_domains = self._load_lines(self.feeds_dir / "allow_domains.txt")
        self.deny_ips = set(self._load_lines(self.feeds_dir / "deny_ips.txt"))
        self.deny_asn = set(self._load_lines(self.feeds_dir / "deny_asn.txt"))

    @staticmethod
    def _load_lines(path: Path) -> list[str]:
        if not path.exists():
            return []
        lines: list[str] = []
        for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            lines.append(ln)
        return lines

    def load_sector_feeds(self, extra_feeds: list[str]) -> int:
        """
        Load additional sector-specific feeds into deny_domains.
        
        Args:
            extra_feeds: List of feed filenames (e.g., ["school_blacklist.txt"])
            
        Returns:
            Number of new patterns loaded
        """
        loaded_count = 0
        for feed_name in extra_feeds:
            feed_path = self.feeds_dir / feed_name
            if feed_path.exists():
                patterns = self._load_lines(feed_path)
                self.deny_domains.extend(patterns)
                loaded_count += len(patterns)
                logger.info(f"[FEEDS] Loaded {len(patterns)} patterns from {feed_name}")
            else:
                logger.warning(f"[FEEDS] Sector feed not found: {feed_path}")
        return loaded_count

    def domain_allowed(self, domain: str) -> bool:
        return any(fnmatch.fnmatch(domain, pat) for pat in self.allow_domains)

    def domain_denied(self, domain: str) -> bool:
        return any(fnmatch.fnmatch(domain, pat) for pat in self.deny_domains)

    def ip_denied(self, ip: str) -> bool:
        return ip in self.deny_ips

    def asn_denied(self, asn: str) -> bool:
        return asn in self.deny_asn

