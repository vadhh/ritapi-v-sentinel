# MiniFW-AI CRUD Fix - Installation Guide

## Quick Installation Steps

### 1. Backup Current Files
Before applying the fix, backup your current files:

```bash
# Backup minifw app
cp -r /path/to/your/project/minifw /path/to/your/project/minifw.backup

# Backup templates
cp -r /path/to/your/project/templates/ops_template/minifw_config /path/to/your/project/templates/ops_template/minifw_config.backup
```

### 2. Apply the Fix

Copy the fixed files to your Django project:

```bash
# Copy minifw app files
cp minifw_fixed/minifw/views.py /path/to/your/project/minifw/
cp minifw_fixed/minifw/services.py /path/to/your/project/minifw/

# Copy template files
cp minifw_fixed/templates/ops_template/minifw_config/*.html /path/to/your/project/templates/ops_template/minifw_config/
```

### 3. Restart Django Application

```bash
# If using systemd
sudo systemctl restart your-django-service

# Or if using gunicorn/uwsgi
sudo systemctl restart gunicorn
sudo systemctl restart uwsgi

# Or if developing locally
# Just restart your Django development server
python manage.py runserver
```

### 4. Verify the Fix

1. **Test without MiniFW-AI service running:**
   ```bash
   # Stop the MiniFW-AI service
   sudo systemctl stop minifw-ai
   
   # Try to add/edit configurations via web interface
   # It should work without errors
   ```

2. **Test SweetAlert notifications:**
   - Make a configuration change
   - Verify SweetAlert popup appears
   - Test both "Restart Service" and "Later" options

3. **Test service restart:**
   - Click "Restart Service" in SweetAlert
   - Verify service restarts successfully
   - Check service status: `sudo systemctl status minifw-ai`

## Detailed File Changes

### Modified Files:
1. `minifw/views.py` - Removed automatic service restarts, updated messages
2. `minifw/services.py` - Enhanced file/directory handling
3. `templates/ops_template/minifw_config/feeds.html` - Added SweetAlert
4. `templates/ops_template/minifw_config/policy.html` - Added SweetAlert
5. `templates/ops_template/minifw_config/blocked_ips.html` - Added SweetAlert

### No Changes Required To:
- Database migrations
- URL configurations
- Models
- Other Django apps
- Requirements/dependencies

## Troubleshooting

### Issue: CRUD operations still fail when service is stopped

**Solution:**
1. Check file permissions on `/opt/minifw_ai/config/` directory
2. Ensure the Django process has write permissions:
   ```bash
   sudo chown -R django-user:django-group /opt/minifw_ai/config/
   sudo chmod -R 755 /opt/minifw_ai/config/
   ```

### Issue: SweetAlert not appearing

**Solution:**
1. Clear browser cache
2. Verify SweetAlert2 is loaded in base.html:
   ```bash
   grep -n "sweetalert2" /path/to/templates/base.html
   ```
3. Check browser console for JavaScript errors

### Issue: Restart button doesn't work

**Solution:**
1. Verify CSRF token is present in templates
2. Check URL name is correct: `{% url "minifw_service_control" %}`
3. Verify the service control endpoint exists in urls.py

### Issue: Directory permission errors

**Solution:**
1. Create directories manually with correct permissions:
   ```bash
   sudo mkdir -p /opt/minifw_ai/config/feeds
   sudo chown -R django-user:django-group /opt/minifw_ai/
   sudo chmod -R 755 /opt/minifw_ai/
   ```

## Configuration Paths

The fix expects these paths to exist (they will be created automatically if missing):
- `/opt/minifw_ai/config/policy.json` - Main policy configuration
- `/opt/minifw_ai/config/feeds/` - Feed files directory
  - `allow_domains.txt`
  - `deny_domains.txt`
  - `deny_ips.txt`
  - `deny_asn.txt`

## Permissions Checklist

Ensure the Django application user has:
- ✅ Read access to all config files
- ✅ Write access to `/opt/minifw_ai/config/` directory
- ✅ Write access to `/opt/minifw_ai/config/feeds/` directory
- ✅ Execute permissions on `systemctl` commands (via sudo if needed)

## Security Considerations

1. **Backup files**: The fix creates `.backup` files before overwriting configs
2. **CSRF protection**: All forms include CSRF tokens
3. **Permission handling**: Errors are caught and logged instead of exposing system details
4. **Service control**: Restart requires explicit user confirmation via SweetAlert

## Testing Checklist

After installation, verify:
- [ ] Can view feeds without service running
- [ ] Can add entries to feeds without service running
- [ ] Can remove entries from feeds without service running
- [ ] Can edit policy without service running
- [ ] SweetAlert appears for successful operations
- [ ] "Restart Service" button works correctly
- [ ] "Later" button dismisses alert properly
- [ ] Error messages display in SweetAlert for failures
- [ ] Backup files are created before overwrites
- [ ] Manual service restart still works from dashboard

## Rollback Procedure

If you need to revert the changes:

```bash
# Restore from backup
cp -r /path/to/your/project/minifw.backup/* /path/to/your/project/minifw/
cp -r /path/to/your/project/templates/ops_template/minifw_config.backup/* /path/to/your/project/templates/ops_template/minifw_config/

# Restart Django
sudo systemctl restart your-django-service
```

## Support

For issues or questions:
1. Check the MINIFW_CRUD_FIX_README.md for detailed technical documentation
2. Review browser console for JavaScript errors
3. Check Django logs for backend errors
4. Verify file permissions and paths

## Version Information

- Fix Version: 1.0
- Compatible with: Django 3.2+
- Required: SweetAlert2 11.10.7+ (already in base.html)
- Python: 3.8+
