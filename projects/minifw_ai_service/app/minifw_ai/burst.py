from __future__ import annotations
from collections import deque, OrderedDict
import time

class BurstTracker:
    def __init__(self, window_seconds: int = 60, max_size: int = 20000):
        self.window = window_seconds
        self.max_size = max_size
        self.q = OrderedDict()

    def add(self, ip: str) -> int:
        now = time.time()
        
        # LRU Logic: If IP exists, move to end (most recently used).
        # If new and full, pop first (least recently used).
        if ip in self.q:
            self.q.move_to_end(ip)
        elif len(self.q) >= self.max_size:
            self.q.popitem(last=False)
        
        # Get or create deque for this IP
        if ip not in self.q:
            self.q[ip] = deque()
        dq = self.q[ip]
        
        dq.append(now)
        
        # Cleanup old timestamps for this IP
        while dq and (now - dq[0]) > self.window:
            dq.popleft()
            
        return len(dq)

