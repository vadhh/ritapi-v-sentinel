import logging
from django.http import JsonResponse
from django.conf import settings
# Import RedisClientSingleton yang diasumsikan berada di utils/redis_client.py
from utils.redis_client import RedisClientSingleton 
from utils.ip import get_client_ip
# Hapus: from utils.request_utils import get_tenant_from_request
# Hapus: from decision_engine.metrics import RATE_LIMIT_HITS
from utils.logging import log_request


logger = logging.getLogger(__name__)

class RateLimiterMiddleware:
    """
    Middleware sederhana untuk rate limit per-IP (Single-Tenant).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit = getattr(settings, "RATE_LIMIT_REQUESTS", 20)  # default 20 req
        self.rate_window = getattr(settings, "RATE_LIMIT_WINDOW", 60)   # default 60 detik

    def __call__(self, request):
        path = request.path

        # contoh: skip health checks dan path admin/internal
        if (
            path == "/"   
            or path.startswith("/admin")
            or path.startswith("/static")
            or path.startswith("/__debug__")
            or path.startswith("/login")
            or path.startswith("/accounts/login")
            or path.startswith("/ops")
            or path.startswith("/logout")
            or path.startswith("/tls")
            or path.startswith("/healthz")
            or path.startswith("/readyz")
            or path.startswith("/demo")
            or path.startswith("/metrics")
        ):
            return self.get_response(request)
        
        client_ip = get_client_ip(request)

        redis_client = RedisClientSingleton.get_client()
        if redis_client and client_ip:
            
            # Hapus: tenant_id = get_tenant_from_request(request)
            
            # Kunci Redis kini hanya bergantung pada IP dan Path
            path_key = request.path.split("?")[0].replace("/", "_")
            # Ubah kunci: ritapi:rate:{client_ip}:{path_key}
            rate_key = f"ritapi:rate:{client_ip}:{path_key}" 
            # Ubah kunci: ritapi:rate_log:{client_ip}:{path_key}
            log_key = f"ritapi:rate_log:{client_ip}:{path_key}" 
            
            try:
                current = redis_client.incr(rate_key)
                if current == 1:
                    redis_client.expire(rate_key, self.rate_window)

                if current > self.rate_limit:
                    # hanya log sekali per window
                    if not redis_client.exists(log_key):
                        logger.warning(
                            f"Rate limit exceeded for IP {client_ip}: {current}/{self.rate_limit} "
                            f"(window {self.rate_window}s)"
                        )
                        redis_client.setex(log_key, self.rate_window, "1")
                        
                        # ✅ Tambahkan ke log sistem (disesuaikan dengan model log terakhir)
                        try:
                            log_request(
                                ip=client_ip,
                                path=request.path,
                                method=request.method,
                                size=len(request.body or b""),
                                score=0.9,  # Skor tinggi untuk rate limit block
                                action="block", # Diubah dari 'decision'
                                reasons="RATE_LIMIT_EXCEEDED", # Diubah dari 'reason'
                                label="rate_limit_block" # Label baru
                                # duration_ms tidak tersedia di sini, biarkan default None
                            )
                        except Exception as e:
                            logger.error(f"Failed to log rate limit event: {e}")
                            
                    # Hapus: RATE_LIMIT_HITS.labels(ip=client_ip, tenant=tenant_id).inc()
                    
                    return JsonResponse(
                        {
                            "error": "Too Many Requests",
                            "detail": f"Rate limit exceeded ({self.rate_limit}/{self.rate_window}s)"
                        },
                        status=429
                    )
            except Exception as e:
                logger.error(f"Rate limiter Redis error: {e}")
                # fallback: jangan blok request jika ada masalah Redis

        return self.get_response(request)