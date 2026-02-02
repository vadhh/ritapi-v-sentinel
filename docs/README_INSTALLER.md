# RITAPI V-Sentinel & MiniFW-AI - Unified Installer

## 🚀 Instalasi Super Cepat

### 1. Download file-file ini:
- `rt.zip` (Django project)
- `ritapi_v_sentinel_minifw_ai_bundle_updated.zip` (MiniFW-AI service)
- `unified_installer.sh` (installer script)
- `prepare_installation.sh` (preparation script)

### 2. Persiapan (30 detik)

```bash
# Letakkan semua file di satu folder
mkdir ritapi_install
cd ritapi_install

# Copy semua file yang didownload ke folder ini
# Lalu jalankan:
chmod +x *.sh
./prepare_installation.sh
```

### 3. Install (5-10 menit)

```bash
sudo ./unified_installer.sh install
```

**Selesai!** 🎉

Akses: `http://IP-SERVER-ANDA/`

---

## 📚 Dokumentasi Lengkap

Baca `PANDUAN_INSTALASI_LENGKAP.md` untuk:
- Troubleshooting
- Konfigurasi detail
- Manajemen services
- Security hardening

---

## ⚡ Perintah Penting

```bash
# Status semua services
sudo ./unified_installer.sh status

# Restart Django
sudo systemctl restart ritapi-gunicorn

# Restart MiniFW-AI
sudo systemctl restart minifw-ai

# Lihat logs
sudo journalctl -u ritapi-gunicorn -f
sudo journalctl -u minifw-ai -f

# Uninstall
sudo ./unified_installer.sh uninstall
```

---

## 🎯 Komponen yang Terinstall

### 1. RITAPI V-Sentinel (Django)
- Lokasi: `/opt/ritapi_v_sentinel`
- Service: `ritapi-gunicorn.service`
- Port: 8000 (internal, via Gunicorn)
- Web UI: http://IP-SERVER/

### 2. MiniFW-AI Service
- Lokasi: `/opt/minifw_ai`
- Service: `minifw-ai.service`
- Config: `/opt/minifw_ai/config/policy.json`
- IPSet: `minifw_block_v4`

### 3. Services Lainnya
- Nginx (reverse proxy) - Port 80/443
- Redis (caching/queue)
- Gunicorn (WSGI server)

---

## 🔧 Troubleshooting Cepat

**Web tidak bisa diakses?**
```bash
sudo systemctl restart ritapi-gunicorn nginx
```

**Permission error?**
```bash
sudo chown -R www-data:www-data /opt/minifw_ai/config
sudo chmod -R 755 /opt/minifw_ai/config
```

**Service error?**
```bash
sudo journalctl -u ritapi-gunicorn -n 50
sudo journalctl -u minifw-ai -n 50
```

---

## 📁 File Structure

```
ritapi_install/
├── unified_installer.sh          ← Installer utama
├── prepare_installation.sh       ← Preparation script
├── PANDUAN_INSTALASI_LENGKAP.md  ← Panduan lengkap
├── README_INSTALLER.md           ← File ini
├── rt.zip                        ← Django project
├── ritapi_v_sentinel_minifw_ai_bundle_updated.zip  ← MiniFW-AI
├── ritapi_django/                ← (auto-extracted)
└── minifw_ai_service/            ← (auto-extracted)
```

Setelah instalasi:
```
/opt/
├── ritapi_v_sentinel/   ← Django app
└── minifw_ai/           ← MiniFW-AI service
```

---

## ✅ Checklist

- [ ] Download semua file
- [ ] Jalankan `prepare_installation.sh`
- [ ] Jalankan `sudo ./unified_installer.sh install`
- [ ] Buat admin user
- [ ] Akses web dashboard
- [ ] Test CRUD operations
- [ ] Cek MiniFW-AI service running

---

**Version:** 1.0  
**Platform:** Ubuntu 20.04/22.04, Debian 11/12  
**Requirements:** Root access, Internet connection
