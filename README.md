# 🎁 RITAPI V-Sentinel & MiniFW-AI - Complete Installation Package

## 📦 Apa Ini?

Ini adalah **paket installer lengkap all-in-one** yang berisi:

✅ **RITAPI V-Sentinel** - Django Web Application (Dashboard & Management)  
✅ **MiniFW-AI** - Backend Security Service  
✅ **Semua dependencies dan konfigurasi**  
✅ **Dokumentasi lengkap**  
✅ **CRUD fix untuk MiniFW**  

**Tinggal ekstrak dan install!** Tidak perlu download file tambahan.

---

## 🚀 Instalasi Super Cepat (3 Langkah)

### 1️⃣ Ekstrak Package

```bash
# Ekstrak file zip
unzip ritapi_complete_installer.zip
cd ritapi_complete_installer
```

### 2️⃣ Jalankan Installer

```bash
# Buat executable
chmod +x install.sh

# Install!
sudo ./install.sh
```

### 3️⃣ Pilih Menu Install

```
Pilih opsi:

  1. Install (Instalasi Lengkap)    ← Pilih ini
  2. Status (Cek Services)
  3. Uninstall (Hapus Semua)
  4. Exit
```

**Selesai!** Akses web di: `http://IP-SERVER-ANDA/`

---

## 📁 Struktur Package

```
ritapi_complete_installer/
├── install.sh                    ← INSTALLER UTAMA (jalankan ini!)
├── README.md                     ← File ini
├── projects/
│   ├── ritapi_django/           ← Django Web Application
│   │   ├── manage.py
│   │   ├── requirements.txt
│   │   ├── minifw/              ← MiniFW CRUD module
│   │   ├── templates/
│   │   └── ...
│   └── minifw_ai_service/       ← MiniFW-AI Backend Service
│       ├── app/
│       ├── config/
│       ├── systemd/
│       └── ...
├── scripts/
│   └── minifw_fixed/            ← CRUD fix & permissions
│       ├── fix_permissions.sh
│       └── ...
└── docs/
    ├── CARA_PAKAI.md            ← Panduan praktis
    ├── PANDUAN_INSTALASI_LENGKAP.md  ← Dokumentasi lengkap
    └── ...
```

---

## 🎯 Yang Akan Terinstall

### 1. RITAPI V-Sentinel (Django)
- **Lokasi:** `/opt/ritapi_v_sentinel`
- **Service:** `ritapi-gunicorn.service`
- **Port:** 8000 (internal via Gunicorn)
- **Web:** http://IP-SERVER/

### 2. MiniFW-AI Service
- **Lokasi:** `/opt/minifw_ai`
- **Service:** `minifw-ai.service`
- **Config:** `/opt/minifw_ai/config/policy.json`
- **IPSet:** `minifw_block_v4`

### 3. Dependencies
- Python 3 + Virtual Environments
- Nginx (reverse proxy)
- Gunicorn (WSGI server)
- Redis (caching/queue)
- NFTables & IPSet
- SQLite (database)

---

## ⚡ Perintah Penting

### Cek Status

```bash
sudo ./install.sh status
```

Atau manual:
```bash
sudo systemctl status ritapi-gunicorn
sudo systemctl status minifw-ai
sudo systemctl status nginx
```

### Restart Services

```bash
# Django
sudo systemctl restart ritapi-gunicorn

# MiniFW-AI
sudo systemctl restart minifw-ai

# Nginx
sudo systemctl restart nginx

# Semua sekaligus
sudo systemctl restart ritapi-gunicorn minifw-ai nginx
```

### Lihat Logs

```bash
# Django (real-time)
sudo journalctl -u ritapi-gunicorn -f

# MiniFW-AI (real-time)
sudo journalctl -u minifw-ai -f

# Nginx
sudo tail -f /var/log/nginx/error.log
```

### Buat Admin User

```bash
cd /opt/ritapi_v_sentinel
sudo -u www-data ./venv/bin/python manage.py createsuperuser
```

### Uninstall

```bash
sudo ./install.sh uninstall
```

---

## 🔧 Troubleshooting

### Web tidak bisa diakses?

```bash
# Restart services
sudo systemctl restart ritapi-gunicorn nginx

# Cek logs
sudo journalctl -u ritapi-gunicorn -n 50
```

### Permission error di MiniFW CRUD?

```bash
cd scripts/minifw_fixed
sudo ./fix_permissions.sh
```

### Service tidak start?

```bash
# Lihat error detail
sudo journalctl -u ritapi-gunicorn -n 100
sudo journalctl -u minifw-ai -n 100

# Cek config
sudo nginx -t
```

---

## 📚 Dokumentasi Lengkap

Baca file-file di folder `docs/`:

- **`CARA_PAKAI.md`** - Panduan step-by-step praktis ⭐ Baca ini dulu!
- **`PANDUAN_INSTALASI_LENGKAP.md`** - Dokumentasi detail lengkap
- **`README_INSTALLER.md`** - Quick reference

---

## 🌟 Fitur Installer

✅ **Auto-detect** web server user (www-data/nginx/apache)  
✅ **Auto-install** semua dependencies  
✅ **Auto-setup** Python virtual environments  
✅ **Auto-configure** Nginx, Gunicorn, systemd  
✅ **Auto-apply** CRUD fixes untuk MiniFW  
✅ **Interactive menu** yang user-friendly  
✅ **Colored output** untuk kemudahan  
✅ **Error handling** yang baik  
✅ **Verification** struktur package  
✅ **Status check** built-in  
✅ **Uninstall** yang bersih  

---

## 🎓 Tutorial Video Style

### Langkah 1: Ekstrak
```bash
unzip ritapi_complete_installer.zip
cd ritapi_complete_installer
```

### Langkah 2: Install
```bash
chmod +x install.sh
sudo ./install.sh
```

### Langkah 3: Pilih Install
```
Pilihan [1-4]: 1   ← Ketik 1 lalu Enter
```

### Langkah 4: Ikuti Prompt
- Installer akan bertanya apakah mau lanjut → Ketik `y`
- Tunggu proses instalasi (5-10 menit)
- Akan ditanya buat admin user → Pilih sesuai kebutuhan

### Langkah 5: Akses Web
```
http://IP-SERVER-ANDA/
```

**DONE!** 🎉

---

## 💡 Tips Pro

1. **Gunakan screen/tmux** saat install via SSH
   ```bash
   screen -S install
   sudo ./install.sh
   # Ctrl+A, D untuk detach
   ```

2. **Catat IP server** sebelum install
   ```bash
   hostname -I
   ```

3. **Siapkan password admin** sebelum install

4. **Backup config** secara berkala
   ```bash
   sudo tar -czf backup_$(date +%Y%m%d).tar.gz \
       /opt/ritapi_v_sentinel \
       /opt/minifw_ai/config
   ```

5. **Setup firewall** untuk production
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

---

## ✅ Checklist Post-Installation

- [ ] Web dashboard bisa diakses
- [ ] Bisa login dengan admin user
- [ ] MiniFW dashboard tersedia di `/ops/minifw/`
- [ ] Semua services running (`./install.sh status`)
- [ ] CRUD operations bekerja (test add/edit di MiniFW)
- [ ] Logs tidak ada error kritis
- [ ] IP blocking bekerja (cek `ipset list minifw_block_v4`)

---

## 🆘 Butuh Bantuan?

1. **Cek logs** terlebih dahulu
2. **Baca dokumentasi** di folder `docs/`
3. **Jalankan status check:** `sudo ./install.sh status`
4. **Test ulang permission:** `cd scripts/minifw_fixed && sudo ./fix_permissions.sh`

---

## 🔐 Keamanan Production

Untuk deployment production:

1. **Ganti Django SECRET_KEY**
2. **Set DEBUG = False**
3. **Setup HTTPS dengan Let's Encrypt**
4. **Enable firewall (UFW)**
5. **Setup strong passwords**
6. **Regular backups**
7. **Monitor logs**

---

## 📋 System Requirements

- **OS:** Ubuntu 20.04/22.04, Debian 11/12
- **RAM:** Minimal 2GB (4GB recommended)
- **Disk:** Minimal 5GB free space
- **Network:** Internet connection untuk download dependencies
- **Access:** Root/sudo access

---

## 🎁 Package Contents

- ✅ Complete Django project
- ✅ Complete MiniFW-AI service
- ✅ All installer scripts
- ✅ CRUD fixes
- ✅ Permission fix scripts
- ✅ Complete documentation
- ✅ Systemd service files
- ✅ Nginx configuration templates

**Total package size:** ~20-30MB (uncompressed)  
**Installation time:** 5-10 minutes  
**Difficulty level:** ⭐ Easy (tinggal jalankan!)

---

## 🚀 Mulai Sekarang!

```bash
# 1. Ekstrak
unzip ritapi_complete_installer.zip
cd ritapi_complete_installer

# 2. Install
chmod +x install.sh
sudo ./install.sh

# 3. Akses
# http://IP-SERVER-ANDA/
```

**Semudah itu!** 🎉

---

**Version:** 2.0 (All-in-One Complete Package)  
**Last Updated:** Januari 2026  
**Status:** Production Ready  
**License:** As per original projects
