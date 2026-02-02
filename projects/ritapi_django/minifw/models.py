from django.db import models


class MiniFWEvent(models.Model):
    """
    Model untuk menyimpan events dari MiniFW-AI
    Data di-sync dari /opt/minifw_ai/logs/events.jsonl
    """
    timestamp = models.DateTimeField(db_index=True)
    segment = models.CharField(max_length=50, db_index=True)
    client_ip = models.GenericIPAddressField(db_index=True)
    domain = models.CharField(max_length=255, db_index=True)
    action = models.CharField(max_length=20, db_index=True)  # allow, monitor, block
    score = models.IntegerField()
    reasons = models.JSONField(default=list)
    
    class Meta:
        db_table = 'minifw_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'action']),
            models.Index(fields=['client_ip', '-timestamp']),
            models.Index(fields=['segment', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.timestamp} - {self.client_ip} - {self.domain} - {self.action}"


class MiniFWBlockedIP(models.Model):
    """
    Model untuk tracking IP yang di-block
    """
    ip_address = models.GenericIPAddressField(unique=True)
    blocked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    segment = models.CharField(max_length=50)
    reason = models.TextField()
    score = models.IntegerField()
    auto_blocked = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'minifw_blocked_ips'
        ordering = ['-blocked_at']
    
    def __str__(self):
        return f"{self.ip_address} - {self.segment}"
