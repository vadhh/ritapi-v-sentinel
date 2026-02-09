from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """Extended profile for RBAC. OneToOneField keeps default auth.User intact."""

    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin'),
        ('ADMIN', 'Admin'),
        ('OPERATOR', 'Operator'),
        ('AUDITOR', 'Auditor'),
        ('VIEWER', 'Viewer'),
    ]

    SECTOR_CHOICES = [
        ('HOSPITAL', 'Hospital'),
        ('SCHOOL', 'School'),
        ('GOVERNMENT', 'Government'),
        ('FINANCE', 'Finance'),
        ('LEGAL', 'Legal'),
        ('ESTABLISHMENT', 'Establishment'),
    ]

    ROLE_HIERARCHY = {
        'SUPER_ADMIN': 5,
        'ADMIN': 4,
        'OPERATOR': 3,
        'AUDITOR': 2,
        'VIEWER': 1,
    }

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='VIEWER')
    sector = models.CharField(max_length=20, choices=SECTOR_CHOICES, default='ESTABLISHMENT')
    full_name = models.CharField(max_length=255, blank=True, default='')
    department = models.CharField(max_length=255, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')

    is_locked = models.BooleanField(default=False)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'minifw_user_profiles'

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    # ---- permission helpers ----

    def _role_level(self):
        return self.ROLE_HIERARCHY.get(self.role, 0)

    def has_permission(self, required_role):
        required = self.ROLE_HIERARCHY.get(required_role, 99)
        return self._role_level() >= required

    def can_modify_policy(self):
        return self.has_permission('ADMIN')

    def can_execute_enforcement(self):
        return self.has_permission('OPERATOR')

    def can_access_audit(self):
        return self.has_permission('AUDITOR')

    def can_export_data(self):
        return self.has_permission('AUDITOR')


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


class AuditLog(models.Model):
    """
    Model for tracking user actions and system events.
    Ported from FastAPI minifw_ai_service.
    """
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    username = models.CharField(max_length=150, db_index=True)
    user_role = models.CharField(max_length=50)
    user_sector = models.CharField(max_length=50, null=True, blank=True)
    action = models.CharField(max_length=100, db_index=True)
    severity = models.CharField(max_length=20, default='info')
    resource_type = models.CharField(max_length=100, null=True, blank=True)
    resource_id = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    success = models.BooleanField(default=True)
    before_value = models.JSONField(null=True, blank=True)
    after_value = models.JSONField(null=True, blank=True)
    extra_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'minifw_audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['severity', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.username} - {self.action}"
