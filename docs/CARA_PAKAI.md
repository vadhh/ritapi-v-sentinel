# 🎯 Cara Menggunakan Unified Installer

## Langkah-Langkah Mudah

### 1️⃣ Persiapan File (2 menit)

Anda membutuhkan 2 file zip dari project Anda:
- `rt.zip` - Django project
- `ritapi_v_sentinel_minifw_ai_bundle_updated.zip` - MiniFW-AI service

**Buat folder baru dan kumpulkan semua file:**

```bash
# Buat folder instalasi
mkdir ~/ritapi_installation
cd ~/ritapi_installation

# Copy file-file ini ke folder tersebut:
# 1. rt.zip (dari project Django Anda)
# 2. ritapi_v_sentinel_minifw_ai_bundle_updated.zip (dari MiniFW-AI)
# 3. unified_installer.sh (dari hasil download)
# 4. prepare_installation.sh (dari hasil download)
```

Struktur folder harus seperti ini:
```
~/ritapi_installation/
├── rt.zip
├── ritapi_v_sentinel_minifw_ai_bundle_updated.zip
├── unified_installer.sh
└── prepare_installation.sh
```

### 2️⃣ Persiapan Instalasi (30 detik)

```bash
cd ~/ritapi_installation

# Buat scripts executable
chmod +x *.sh

# Jalankan preparation script
./prepare_installation.sh
```

Script akan:
- ✅ Ekstrak `rt.zip` ke folder `ritapi_django/`
- ✅ Ekstrak MiniFW-AI ke folder `minifw_ai_service/`
- ✅ Menyiapkan struktur yang benar untuk installer

### 3️⃣ Install! (5-10 menit)

```bash
# Jalankan installer
sudo ./unified_installer.sh install
```

Installer akan otomatis:
1. ✅ Install semua dependencies (Python, Nginx, Redis, dll)
2. ✅ Install RITAPI Django application
3. ✅ Install MiniFW-AI service
4. ✅ Setup Gunicorn untuk Django
5. ✅ Konfigurasi Nginx
6. ✅ Setup systemd services
7. ✅ Tanya apakah mau buat admin user
8. ✅ Start semua services

### 4️⃣ Selesai! 🎉

Akses web dashboard:
```
http://IP-SERVER-ANDA/
```

Atau jika di localhost:
```
http://localhost/
```

---

## 📋 Setelah Instalasi

### Membuat Admin User (jika dilewati)

```bash
cd /opt/ritapi_v_sentinel
sudo -u www-data ./venv/bin/python manage.py createsuperuser
```

### Cek Status Services

```bash
sudo ./unified_installer.sh status
```

Atau:
```bash
sudo systemctl status ritapi-gunicorn
sudo systemctl status minifw-ai
sudo systemctl status nginx
```

### Lihat Logs

```bash
# Django logs
sudo journalctl -u ritapi-gunicorn -f

# MiniFW-AI logs
sudo journalctl -u minifw-ai -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
```

---

## 🔧 Troubleshooting

### Jika ada error saat instalasi:

1. **Cek log error:**
   ```bash
   sudo journalctl -u ritapi-gunicorn -n 50
   sudo journalctl -u minifw-ai -n 50
   ```

2. **Restart services:**
   ```bash
   sudo systemctl restart ritapi-gunicorn
   sudo systemctl restart minifw-ai
   sudo systemctl restart nginx
   ```

3. **Fix permissions (khusus untuk MiniFW-AI config):**
   ```bash
   sudo chown -R www-data:www-data /opt/minifw_ai/config
   sudo chmod -R 755 /opt/minifw_ai/config
   ```

### Web tidak bisa diakses?

```bash
# Cek apakah Gunicorn running
sudo systemctl status ritapi-gunicorn

# Cek apakah Nginx running
sudo systemctl status nginx

# Restart keduanya
sudo systemctl restart ritapi-gunicorn nginx
```

### Permission error saat CRUD di MiniFW?

Gunakan fix script yang sudah disediakan:
```bash
cd ~/ritapi_installation/minifw_fixed
sudo ./fix_permissions.sh
```

---

## 🗑️ Uninstall

Untuk remove semua komponen:

```bash
cd ~/ritapi_installation
sudo ./unified_installer.sh uninstall
```

---

## 📚 Dokumentasi Lengkap

Untuk informasi lebih detail, baca:
- `PANDUAN_INSTALASI_LENGKAP.md` - Panduan lengkap
- `README_INSTALLER.md` - Quick reference
- `minifw_fixed/QUICKSTART.md` - Fix untuk CRUD issues

---

## ✅ Quick Checklist

Setelah instalasi, pastikan:
- [ ] Web dashboard bisa diakses
- [ ] Bisa login (jika sudah buat admin user)
- [ ] MiniFW dashboard bisa diakses di `/ops/minifw/`
- [ ] Semua services running (cek dengan `./unified_installer.sh status`)
- [ ] CRUD operations bekerja (tambah/edit data di MiniFW)

---

## 💡 Tips

1. **Gunakan IP statis** atau domain untuk server production
2. **Setup HTTPS** dengan Let's Encrypt untuk production
3. **Backup** konfigurasi secara berkala
4. **Monitor logs** untuk mendeteksi issue lebih awal
5. **Update dependencies** secara berkala untuk security

---

**Butuh bantuan?** Cek file `PANDUAN_INSTALASI_LENGKAP.md` untuk troubleshooting detail!
