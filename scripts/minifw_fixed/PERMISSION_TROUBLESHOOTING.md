# MiniFW-AI Permission Error Troubleshooting Guide

## The Error You're Seeing

```
Error saving policy: [Errno 13] Permission denied: '/opt/minifw_ai/config/policy.json.backup'
Error writing feed allow_domains: [Errno 13] Permission denied: '/opt/minifw_ai/config/feeds/allow_domains.txt.backup'
```

This means your Django application doesn't have write permissions to the `/opt/minifw_ai/config/` directory.

## Quick Fix (Recommended)

We've created an automated script to fix all permissions. Run this:

```bash
# Make the script executable
chmod +x fix_permissions.sh

# Run the script with sudo
sudo ./fix_permissions.sh
```

The script will:
1. ✅ Create necessary directories
2. ✅ Create default configuration files
3. ✅ Set correct ownership (to your web server user)
4. ✅ Set correct permissions (755 for directories, 644 for files)
5. ✅ Test write access
6. ✅ Verify everything works

## Manual Fix (Alternative)

If you prefer to fix permissions manually:

### Step 1: Find Your Web Server User

```bash
# Common web server users:
# - www-data (Debian/Ubuntu with Apache/Nginx)
# - nginx (CentOS/RHEL with Nginx)
# - apache (CentOS/RHEL with Apache)

# Check which user is running your Django app
ps aux | grep gunicorn
# or
ps aux | grep uwsgi
# or
ps aux | grep python
```

### Step 2: Create Directories

```bash
sudo mkdir -p /opt/minifw_ai/config/feeds
```

### Step 3: Set Ownership

Replace `www-data` with your actual web server user:

```bash
sudo chown -R www-data:www-data /opt/minifw_ai/config
```

### Step 4: Set Permissions

```bash
# Directories need 755 (rwxr-xr-x)
sudo find /opt/minifw_ai/config -type d -exec chmod 755 {} \;

# Files need 644 (rw-r--r--)
sudo find /opt/minifw_ai/config -type f -exec chmod 644 {} \;
```

### Step 5: Verify

```bash
# Check ownership
ls -la /opt/minifw_ai/config

# Test write access (replace www-data with your user)
sudo -u www-data touch /opt/minifw_ai/config/test.txt
sudo rm /opt/minifw_ai/config/test.txt
```

## Understanding the Fix

### What Changed in the Code

The updated `services.py` now:
1. **Tries to create backups** but won't fail if permissions are denied
2. **Provides better error messages** showing which directory has permission issues
3. **Still attempts to save** the configuration even if backup fails

### Why Backups Might Fail

The original code tried to create `.backup` files, which requires:
- Read permission on the original file
- Write permission on the directory
- Write permission to create the backup file

If any of these fail, the backup creation fails. The new code handles this gracefully.

## Testing After Fix

1. **Test the permission fix:**
   ```bash
   # As your web server user
   sudo -u www-data touch /opt/minifw_ai/config/feeds/test.txt
   sudo -u www-data rm /opt/minifw_ai/config/feeds/test.txt
   ```

2. **Restart Django:**
   ```bash
   sudo systemctl restart your-django-service
   # or
   sudo systemctl restart gunicorn
   # or
   sudo systemctl restart uwsgi
   ```

3. **Test CRUD in the web interface:**
   - Go to MiniFW Policy page
   - Try updating a configuration
   - You should see success instead of permission errors

## Common Issues and Solutions

### Issue 1: "Operation not permitted"
**Cause:** Running as non-root user
**Solution:** Use `sudo` when running the fix script or manual commands

### Issue 2: "No such file or directory"
**Cause:** `/opt/minifw_ai/config` doesn't exist
**Solution:** Run the fix_permissions.sh script or manually create the directory

### Issue 3: Django still can't write
**Cause:** Wrong web server user identified
**Solution:**
```bash
# Find the correct user
ps aux | grep gunicorn | grep -v grep | awk '{print $1}' | head -1
# or check Django process owner in htop/top
```

### Issue 4: SELinux blocking access (RHEL/CentOS)
**Cause:** SELinux security policy
**Solution:**
```bash
# Check if SELinux is enforcing
getenforce

# If yes, allow httpd to write
sudo chcon -R -t httpd_sys_rw_content_t /opt/minifw_ai/config

# Or add SELinux policy
sudo semanage fcontext -a -t httpd_sys_rw_content_t "/opt/minifw_ai/config(/.*)?"
sudo restorecon -R /opt/minifw_ai/config
```

### Issue 5: AppArmor blocking access (Ubuntu)
**Cause:** AppArmor security policy
**Solution:**
```bash
# Check AppArmor status
sudo aa-status

# Adjust AppArmor profile if needed
sudo vim /etc/apparmor.d/usr.sbin.nginx
# or
sudo vim /etc/apparmor.d/usr.sbin.apache2

# Add: /opt/minifw_ai/config/** rw,
# Then reload: sudo apparmor_parser -r /etc/apparmor.d/usr.sbin.nginx
```

## Verification Checklist

After applying the fix, verify:
- [ ] `/opt/minifw_ai/config` exists
- [ ] `/opt/minifw_ai/config/feeds` exists
- [ ] Directory owner is your web server user
- [ ] Directories have 755 permissions
- [ ] Files have 644 permissions
- [ ] Web server user can create files in the directory
- [ ] Django application is restarted
- [ ] CRUD operations work in web interface

## Security Best Practices

1. **Don't use 777 permissions** - It's too permissive
2. **Use specific user/group** - Only the web server user needs access
3. **Monitor logs** - Check Django logs regularly for permission issues
4. **Keep backups** - Even if automatic backups fail, do manual backups periodically

## Directory Structure

After fix, you should have:
```
/opt/minifw_ai/
└── config/
    ├── policy.json (644, owned by www-data:www-data)
    ├── policy.json.backup (644, optional)
    └── feeds/
        ├── allow_domains.txt (644)
        ├── deny_domains.txt (644)
        ├── deny_ips.txt (644)
        └── deny_asn.txt (644)
```

## Still Having Issues?

If you're still experiencing problems after applying the fix:

1. **Check Django logs:**
   ```bash
   sudo tail -f /var/log/django/error.log
   # or wherever your Django logs are
   ```

2. **Check system logs:**
   ```bash
   sudo tail -f /var/log/syslog
   # or
   sudo journalctl -u your-django-service -f
   ```

3. **Enable debug logging in services.py:**
   The error messages will show in Django logs

4. **Verify file system:**
   ```bash
   df -h /opt/minifw_ai/config  # Check if filesystem is full
   mount | grep /opt            # Check if read-only
   ```

## Contact & Support

If issues persist, provide this information:
- Output of: `ls -la /opt/minifw_ai/config`
- Output of: `ps aux | grep gunicorn`
- Django error logs
- Operating system and version
- Web server (Apache/Nginx) and version

---

**Remember:** Always restart your Django application after fixing permissions!
