from django.db import models


class JsonSchema(models.Model):
    name = models.CharField(max_length=100)
    endpoint = models.CharField(
        max_length=255, help_text="Path prefix or full path, e.g. /api/data"
    )
    method = models.CharField(max_length=10, help_text="GET, POST, etc.")
    schema_json = models.JSONField()
    description = models.TextField(blank=True, null=True)

    version = models.CharField(
        max_length=32, default="v1", help_text="Schema version, e.g., v1, v2-beta"
    )

    rollout_mode = models.CharField(
        max_length=16,
        choices=(
            ("monitor", "Monitor only"),
            ("enforce", "Strict enforcement"),
        ),
        default="monitor",
        help_text="If enforce, invalid schema will be blocked. If monitor, only logged.",
    )

    is_active = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        # unique_together sekarang hanya menggunakan endpoint, method, dan version
        unique_together = ("endpoint", "method", "version")

    def __str__(self):
        # Representasi string yang lebih pendek karena tidak ada referensi layanan
        return f"{self.name} [{self.method} {self.endpoint}] v{self.version} - {self.rollout_mode}"
