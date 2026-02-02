# Panduan Instalasi RITAPI V-Sentinel & MiniFW-AI

## 📋 Ringkasan

Installer ini menggabungkan instalasi 2 komponen:

1. **RITAPI V-Sentinel** - Aplikasi web Django untuk dashboard dan manajemen
2. **MiniFW-AI** - Service backend untuk keamanan yang berjalan sebagai systemd service

## 🚀 Instalasi Cepat (10 Menit)

### Prasyarat

- Ubuntu 20.04/22.04 atau Debian 11/12
- Akses root (sudo)
- Koneksi internet

### Langkah 1: Persiapan File

Ekstrak kedua project dan susun seperti ini:

```
ritapi_minifw_installer/
├── unified_installer.sh          # Script installer utama
├── ritapi_django/                # Project Django (dari rt.zip)
│   ├── manage.py
│   ├── requirements.txt
│   ├── ritapi_v_sentinel/
│   ├── minifw/
│   ├── templates/
│   └── ... (semua file Django)
└── minifw_ai_service/            # MiniFW-AI service (dari bundle)
    ├── app/
    ├── config/
    ├── requirements.txt
    ├── systemd/
    └── ...
```

### Langkah 2: Persiapan Direktori

```bash
# Buat direktori installer
mkdir -p ritapi_minifw_installer
cd ritapi_minifw_installer

# Copy installer script
cp /path/to/unified_installer.sh .

# Ekstrak project Django
mkdir ritapi_django
cd ritapi_django
unzip /path/to/rt.zip
mv * ../ritapi_django/  # Pindahkan semua file ke ritapi_django
cd ..

# Ekstrak MiniFW-AI service
mkdir minifw_ai_service
cd minifw_ai_service
unzip /path/to/ritapi_v_sentinel_minifw_ai_bundle_updated.zip
mv * ../minifw_ai_service/  # Pindahkan semua file ke minifw_ai_service
cd ..
```

### Langkah 3: Jalankan Installer

```bash
# Pastikan di dalam direktori ritapi_minifw_installer
chmod +x unified_installer.sh

# Jalankan installer
sudo ./unified_installer.sh install
```

### Langkah 4: Ikuti Proses Instalasi

Installer akan melakukan:
1. ✅ Install dependencies sistem (Python, Redis, Nginx, dll)
2. ✅ Install RITAPI Django application
3. ✅ Install MiniFW-AI service
4. ✅ Setup Gunicorn untuk Django
5. ✅ Konfigurasi Nginx
6. ✅ Membuat admin user Django (opsional)
7. ✅ Start semua services

## 📁 Struktur Setelah Instalasi

```
/opt/
├── ritapi_v_sentinel/           # Django Application
│   ├── venv/                    # Python virtual environment
│   ├── manage.py
│   ├── minifw/                  # MiniFW CRUD module
│   ├── templates/
│   ├── static/
│   ├── media/
│   └── logs/
└── minifw_ai/                   # MiniFW-AI Service
    ├── venv/                    # Python virtual environment
    ├── app/                     # MiniFW-AI application
    ├── config/
    │   ├── policy.json          # Konfigurasi utama
    │   └── feeds/               # Feed lists
    │       ├── allow_domains.txt
    │       ├── deny_domains.txt
    │       ├── deny_ips.txt
    │       └── deny_asn.txt
    └── logs/
```

## 🎮 Perintah Manajemen

### Mengecek Status

```bash
sudo ./unified_installer.sh status
```

Atau manual:

```bash
# Status semua services
sudo systemctl status ritapi-gunicorn
sudo systemctl status minifw-ai
sudo systemctl status nginx
sudo systemctl status redis-server
```

### Mengelola Services

```bash
# Restart Django
sudo systemctl restart ritapi-gunicorn

# Restart MiniFW-AI
sudo systemctl restart minifw-ai

# Restart Nginx
sudo systemctl restart nginx

# Restart semua
sudo systemctl restart ritapi-gunicorn minifw-ai nginx
```

### Melihat Logs

```bash
# Django logs (real-time)
sudo journalctl -u ritapi-gunicorn -f

# MiniFW-AI logs (real-time)
sudo journalctl -u minifw-ai -f

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Nginx access logs
sudo tail -f /var/log/nginx/access.log
```

### Membuat Admin User (jika dilewati saat instalasi)

```bash
cd /opt/ritapi_v_sentinel
sudo -u www-data ./venv/bin/python manage.py createsuperuser
```

## 🌐 Mengakses Aplikasi

Setelah instalasi selesai:

### Web Dashboard
```
http://IP-SERVER-ANDA/
```

Atau jika di mesin lokal:
```
http://localhost/
```

### Login Page
```
http://IP-SERVER-ANDA/auth/login/
```

## ⚙️ Konfigurasi

### 1. Django Settings

File: `/opt/ritapi_v_sentinel/ritapi_v_sentinel/settings.py`

Konfigurasi yang mungkin perlu diubah:
- `ALLOWED_HOSTS` - Tambahkan domain/IP server Anda
- `SECRET_KEY` - Ganti dengan key yang aman
- Database settings (jika tidak pakai SQLite)

Setelah ubah settings:
```bash
sudo systemctl restart ritapi-gunicorn
```

### 2. MiniFW-AI Configuration

File: `/opt/minifw_ai/config/policy.json`

Edit konfigurasi sesuai kebutuhan, lalu restart:
```bash
sudo systemctl restart minifw-ai
```

### 3. Nginx Configuration

File: `/etc/nginx/sites-available/ritapi`

Setelah edit:
```bash
sudo nginx -t  # Test konfigurasi
sudo systemctl restart nginx
```

## 🔧 Troubleshooting

### Django Tidak Bisa Akses

**Cek service:**
```bash
sudo systemctl status ritapi-gunicorn
sudo journalctl -u ritapi-gunicorn -n 50
```

**Cek permissions:**
```bash
ls -la /opt/ritapi_v_sentinel
```

Harus owned by `www-data:www-data`

### MiniFW-AI Tidak Jalan

**Cek service:**
```bash
sudo systemctl status minifw-ai
sudo journalctl -u minifw-ai -n 50
```

**Cek ipset:**
```bash
sudo ipset list minifw_block_v4
```

### Permission Error saat CRUD

Jalankan permission fix:
```bash
cd /opt/ritapi_v_sentinel
# Dari fix sebelumnya
sudo ./fix_permissions.sh
```

Atau manual:
```bash
sudo chown -R www-data:www-data /opt/minifw_ai/config
sudo chmod -R 755 /opt/minifw_ai/config
sudo find /opt/minifw_ai/config -type f -exec chmod 644 {} \;
```

### Nginx Error 502 Bad Gateway

**Cek Gunicorn:**
```bash
sudo systemctl status ritapi-gunicorn
```

**Cek binding:**
```bash
sudo netstat -tulpn | grep 8000
```

Harus ada Gunicorn listening di 127.0.0.1:8000

### Redis Connection Error

**Start Redis:**
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**Cek status:**
```bash
sudo systemctl status redis-server
```

## 🗑️ Uninstall

Untuk menghapus semua komponen:

```bash
sudo ./unified_installer.sh uninstall
```

Ini akan:
- Stop dan disable semua services
- Hapus `/opt/ritapi_v_sentinel`
- Hapus `/opt/minifw_ai`
- Hapus konfigurasi Nginx
- Hapus ipset

**Note:** Paket sistem (Python, Nginx, dll) tidak akan dihapus.

## 📊 Monitoring

### Melihat Statistik MiniFW-AI

Via web dashboard:
```
http://IP-SERVER/ops/minifw/
```

Via command line:
```bash
# Lihat blocked IPs
sudo ipset list minifw_block_v4

# Lihat logs
sudo journalctl -u minifw-ai -n 100
```

### Monitoring Services

```bash
# Cek semua services
sudo systemctl status ritapi-gunicorn minifw-ai nginx redis-server

# Auto-refresh status (setiap 2 detik)
watch -n 2 'systemctl status ritapi-gunicorn minifw-ai nginx'
```

## 🔐 Keamanan

### Rekomendasi Production

1. **Ganti SECRET_KEY Django**
```bash
sudo nano /opt/ritapi_v_sentinel/ritapi_v_sentinel/settings.py
# Ganti SECRET_KEY dengan key random
```

2. **Set DEBUG = False**
```python
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com', 'IP-SERVER']
```

3. **Setup HTTPS dengan Let's Encrypt**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

4. **Enable Firewall**
```bash
sudo ufw enable
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
```

5. **Secure Redis**
```bash
sudo nano /etc/redis/redis.conf
# Set: bind 127.0.0.1
# Set: requirepass your-strong-password
sudo systemctl restart redis-server
```

## 📝 File Penting

| File/Directory | Deskripsi |
|---------------|-----------|
| `/opt/ritapi_v_sentinel` | Django application |
| `/opt/minifw_ai` | MiniFW-AI service |
| `/etc/systemd/system/ritapi-gunicorn.service` | Django systemd service |
| `/etc/systemd/system/minifw-ai.service` | MiniFW-AI systemd service |
| `/etc/nginx/sites-available/ritapi` | Nginx config |
| `/var/log/nginx/` | Nginx logs |
| `/opt/ritapi_v_sentinel/logs/` | Django logs |
| `/opt/minifw_ai/logs/` | MiniFW-AI logs |

## 🆘 Bantuan & Support

### Informasi untuk Support

Jika ada masalah, kumpulkan informasi ini:

```bash
# Status services
sudo ./unified_installer.sh status > status_report.txt

# Logs
sudo journalctl -u ritapi-gunicorn -n 100 > django_logs.txt
sudo journalctl -u minifw-ai -n 100 > minifw_logs.txt

# Permissions
ls -laR /opt/ritapi_v_sentinel > permissions.txt
ls -laR /opt/minifw_ai >> permissions.txt

# System info
uname -a > system_info.txt
cat /etc/os-release >> system_info.txt
```

### Kontak

Untuk masalah atau pertanyaan:
1. Cek logs terlebih dahulu
2. Verifikasi semua services berjalan
3. Cek permissions pada direktori config

## ✅ Checklist Post-Installation

- [ ] Semua services running (`systemctl status`)
- [ ] Web dashboard bisa diakses
- [ ] Admin user sudah dibuat
- [ ] MiniFW-AI service active
- [ ] CRUD operations bekerja
- [ ] Logs tidak ada error critical
- [ ] Firewall dikonfigurasi (jika perlu)
- [ ] HTTPS disetup (untuk production)
- [ ] Backup strategy direncanakan

## 🔄 Update & Maintenance

### Update Django Application

```bash
cd /opt/ritapi_v_sentinel
sudo -u www-data ./venv/bin/pip install -r requirements.txt --upgrade
sudo -u www-data ./venv/bin/python manage.py migrate
sudo systemctl restart ritapi-gunicorn
```

### Update MiniFW-AI

```bash
cd /opt/minifw_ai
sudo -u www-data ./venv/bin/pip install -r requirements.txt --upgrade
sudo systemctl restart minifw-ai
```

### Backup

Backup yang disarankan:
```bash
# Database Django
sudo -u www-data /opt/ritapi_v_sentinel/venv/bin/python manage.py dumpdata > backup_django_$(date +%Y%m%d).json

# Konfigurasi MiniFW-AI
sudo tar -czf backup_minifw_config_$(date +%Y%m%d).tar.gz /opt/minifw_ai/config/

# Media files
sudo tar -czf backup_media_$(date +%Y%m%d).tar.gz /opt/ritapi_v_sentinel/media/
```

---

**Version:** 1.0  
**Last Updated:** Januari 2026  
**Status:** Production Ready
