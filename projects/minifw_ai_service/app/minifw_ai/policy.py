from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class SegmentThreshold:
    block_threshold: int
    monitor_threshold: int

class Policy:
    def __init__(self, path: str):
        self.path = Path(path)
        self.cfg = json.loads(self.path.read_text(encoding="utf-8"))

    def thresholds(self, segment: str) -> SegmentThreshold:
        segs = self.cfg.get("segments", {})
        seg = segs.get(segment) or segs.get("default") or {"block_threshold": 60, "monitor_threshold": 40}
        return SegmentThreshold(int(seg["block_threshold"]), int(seg["monitor_threshold"]))

    def segment_subnets(self) -> dict[str, list[str]]:
        return self.cfg.get("segment_subnets", {})

    def features(self) -> dict:
        return self.cfg.get("features", {})

    def enforcement(self) -> dict:
        return self.cfg.get("enforcement", {})

    def collectors(self) -> dict:
        return self.cfg.get("collectors", {})

    def burst(self) -> dict:
        return self.cfg.get("burst", {})
