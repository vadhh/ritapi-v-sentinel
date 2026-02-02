# utils/logging.py
import hashlib
# Pastikan path import model ini benar
from log_channel.models import RequestLog 


def log_request(ip, path, method, size, score, action, reasons, label, duration_ms=None):
    """
    Mencatat detail request ke database RequestLog.

    Parameter:
        ip (str): Alamat IP sumber.
        path (str): Path URL.
        method (str): Metode HTTP.
        size (int): Ukuran body request (bytes).
        score (float): Skor risiko dari mesin deteksi.
        action (str): Keputusan akhir ('allow', 'block', 'monitor').
        reasons (str): Detail alasan/pemicu keputusan.
        label (str): Label yang ditetapkan oleh detektor.
        duration_ms (int, optional): Durasi sesi dalam milidetik.
    """
    try:
        RequestLog.objects.create(
            ip_address=ip,
            path=path,
            method=method,
            body_size=size,
            score=score,
            # Diubah: decision menjadi action
            action=action,
            # Diubah: reason menjadi reasons
            reasons=reasons,
            # Field Baru: label
            label=label,
            # Dihapus: service_id
            # Dihapus: hmac_signature_hash
            session_duration_ms=duration_ms,
        )
    except Exception as e:
        # Never fail request because of logging
        # Anda mungkin ingin menambahkan logging error di sini
        # print(f"Error logging request: {e}") 
        pass