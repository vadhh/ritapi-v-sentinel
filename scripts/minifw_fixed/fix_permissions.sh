#!/bin/bash

# MiniFW-AI Configuration Directory Permission Fix Script
# This script sets the correct permissions for the Django app to manage MiniFW-AI configs

echo "=========================================="
echo "MiniFW-AI Permission Fix Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration paths
CONFIG_DIR="/opt/minifw_ai/config"
FEEDS_DIR="/opt/minifw_ai/config/feeds"
POLICY_FILE="/opt/minifw_ai/config/policy.json"

# Get the Django user (you may need to adjust this)
# Common Django users: www-data, nginx, apache, your-app-user
echo "Detecting web server user..."

# Try to detect the web server user
if id "www-data" &>/dev/null; then
    WEB_USER="www-data"
    WEB_GROUP="www-data"
elif id "nginx" &>/dev/null; then
    WEB_USER="nginx"
    WEB_GROUP="nginx"
elif id "apache" &>/dev/null; then
    WEB_USER="apache"
    WEB_GROUP="apache"
else
    echo -e "${YELLOW}Warning: Could not auto-detect web server user${NC}"
    echo "Please enter the user that runs your Django application:"
    read -p "Django user: " WEB_USER
    read -p "Django group (press enter for same as user): " WEB_GROUP
    WEB_GROUP=${WEB_GROUP:-$WEB_USER}
fi

echo -e "${GREEN}Using user: $WEB_USER, group: $WEB_GROUP${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    echo "Usage: sudo bash $0"
    exit 1
fi

# Create directories if they don't exist
echo "Step 1: Creating directories..."
mkdir -p "$CONFIG_DIR"
mkdir -p "$FEEDS_DIR"
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Create default policy.json if it doesn't exist
echo "Step 2: Creating default config files..."
if [ ! -f "$POLICY_FILE" ]; then
    cat > "$POLICY_FILE" << 'EOF'
{
  "segments": {
    "critical": {
      "block_threshold": 80,
      "monitor_threshold": 60
    },
    "production": {
      "block_threshold": 75,
      "monitor_threshold": 50
    },
    "staging": {
      "block_threshold": 85,
      "monitor_threshold": 65
    },
    "default": {
      "block_threshold": 70,
      "monitor_threshold": 45
    }
  },
  "segment_subnets": {
    "critical": [],
    "production": [],
    "staging": [],
    "default": []
  },
  "features": {
    "dns_weight": 40,
    "sni_weight": 35,
    "asn_weight": 15,
    "burst_weight": 10
  },
  "enforcement": {
    "enabled": true,
    "ipset_name": "minifw_block_v4"
  },
  "burst": {
    "window_seconds": 10,
    "threshold": 100
  }
}
EOF
    echo -e "${GREEN}✓ Created default policy.json${NC}"
else
    echo -e "${YELLOW}ℹ policy.json already exists, skipping${NC}"
fi

# Create default feed files
FEED_FILES=("allow_domains.txt" "deny_domains.txt" "deny_ips.txt" "deny_asn.txt")
for feed in "${FEED_FILES[@]}"; do
    FEED_PATH="$FEEDS_DIR/$feed"
    if [ ! -f "$FEED_PATH" ]; then
        cat > "$FEED_PATH" << EOF
# MiniFW-AI Feed File: $feed
# Created by permission fix script
# Add one entry per line

EOF
        echo -e "${GREEN}✓ Created $feed${NC}"
    else
        echo -e "${YELLOW}ℹ $feed already exists, skipping${NC}"
    fi
done
echo ""

# Set ownership
echo "Step 3: Setting ownership..."
chown -R "$WEB_USER:$WEB_GROUP" "$CONFIG_DIR"
echo -e "${GREEN}✓ Ownership set to $WEB_USER:$WEB_GROUP${NC}"
echo ""

# Set permissions
echo "Step 4: Setting permissions..."
# Directories: rwxr-xr-x (755)
find "$CONFIG_DIR" -type d -exec chmod 755 {} \;
# Files: rw-r--r-- (644)
find "$CONFIG_DIR" -type f -exec chmod 644 {} \;
echo -e "${GREEN}✓ Permissions set (directories: 755, files: 644)${NC}"
echo ""

# Verify permissions
echo "Step 5: Verifying permissions..."
echo ""
echo "Directory permissions:"
ls -ld "$CONFIG_DIR"
ls -ld "$FEEDS_DIR"
echo ""
echo "File permissions:"
ls -l "$POLICY_FILE" 2>/dev/null || echo "policy.json not found"
ls -l "$FEEDS_DIR"/*.txt 2>/dev/null || echo "No feed files found"
echo ""

# Test write access
echo "Step 6: Testing write access..."
TEST_FILE="$CONFIG_DIR/.test_write_access"
if sudo -u "$WEB_USER" touch "$TEST_FILE" 2>/dev/null; then
    echo -e "${GREEN}✓ Write access test PASSED${NC}"
    rm -f "$TEST_FILE"
else
    echo -e "${RED}✗ Write access test FAILED${NC}"
    echo "The Django user ($WEB_USER) cannot write to $CONFIG_DIR"
    exit 1
fi
echo ""

# Summary
echo "=========================================="
echo -e "${GREEN}Permission Fix Complete!${NC}"
echo "=========================================="
echo ""
echo "Summary:"
echo "  Config directory: $CONFIG_DIR"
echo "  Owner: $WEB_USER:$WEB_GROUP"
echo "  Directory permissions: 755 (rwxr-xr-x)"
echo "  File permissions: 644 (rw-r--r--)"
echo ""
echo "Next steps:"
echo "  1. Restart your Django application"
echo "  2. Test CRUD operations in the web interface"
echo "  3. If still having issues, check Django logs"
echo ""
echo -e "${GREEN}Done!${NC}"
