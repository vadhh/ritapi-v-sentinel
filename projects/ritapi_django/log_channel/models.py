from django.db import models
from django.utils.translation import gettext_lazy as _

class RequestLog(models.Model):
    """
    Log setiap request yang diproses, mencakup konteks permintaan 
    dan hasil deteksi dari Edge Intelligence Gate / MiniFW-AI.
    """
    # ------------------ CONTEXT & REQUEST DATA ------------------
    
    ip_address = models.GenericIPAddressField(help_text=_("Source IP address."))
    path = models.CharField(max_length=255, help_text=_("Requested URL path."))
    method = models.CharField(max_length=10)
    body_size = models.IntegerField(help_text=_("Request body size in bytes."))
    timestamp = models.DateTimeField(auto_now_add=True)
    
    session_duration_ms = models.BigIntegerField(
        null=True, 
        blank=True, 
        help_text=_("Duration of session in milliseconds (relevant for session behavior anomalies).")
    )
    
    # ------------------ DETECTION RESULT (MiniFW-AI & Policy Scope) ------------------
    
    # Skor Risiko dari Detektor
    score = models.FloatField(help_text=_("Risk score (e.g., 0.0 to 1.0) from the detection engine."))
    
    # Label Spesifik (e.g., "gambling_possible", "clean_or_unknown")
    label = models.CharField(
        max_length=100, 
        help_text=_("Specific label assigned by the detector based on policy.")
    )
    
    # Keputusan Akhir/Tindakan (e.g., "allow", "block", "monitor")
    action = models.CharField(
        max_length=20, 
        help_text=_("Final action taken: 'allow', 'block', or 'monitor'.")
    )
    
    # Alasan Deteksi (Bisa banyak)
    reasons = models.TextField(
        blank=True, 
        null=True, 
        help_text=_("Detailed reasons or list of features/rules that triggered the action.")
    )

    class Meta:
        verbose_name = _("Request Log")
        verbose_name_plural = _("Request Logs")

    @property
    def status(self):
        """Derived status: SUCCESS jika action adalah 'allow', selain itu FAIL/MONITOR."""
        lower_action = self.action.lower()
        if lower_action == "allow":
            return "SUCCESS"
        elif lower_action == "monitor":
            return "MONITOR"
        else: # block atau tindakan lain yang dianggap negatif
            return "FAIL"

    def __str__(self):
        # Menggunakan label/action untuk identifikasi karena detection_engine dihapus
        return f"[{self.action.upper()} | {self.label.upper()}] {self.ip_address} {self.path} (Score: {self.score})"