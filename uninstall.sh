#!/bin/bash
#
# VortexL2 Uninstaller
# L2TPv3 Tunnel Manager for Ubuntu/Debian
#
# Usage: bash <(curl -Ls https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/uninstall.sh)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/vortexl2"
BIN_PATH="/usr/local/bin/vortexl2"
SYSTEMD_DIR="/etc/systemd/system"
CONFIG_DIR="/etc/vortexl2"
LOG_DIR="/var/log/vortexl2"
DATA_DIR="/var/lib/vortexl2"

echo -e "${CYAN}"
cat << 'EOF'
 __      __        _            _     ___  
 \ \    / /       | |          | |   |__ \ 
  \ \  / /__  _ __| |_ _____  _| |      ) |
   \ \/ / _ \| '__| __/ _ \ \/ / |     / / 
    \  / (_) | |  | ||  __/>  <| |____/ /_ 
     \/ \___/|_|   \__\___/_/\_\______|____|
EOF
echo -e "${NC}"
echo -e "${RED}VortexL2 Uninstaller${NC}"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

# Confirm uninstall
echo -e "${YELLOW}This will completely remove VortexL2 from your system.${NC}"
echo -e "${YELLOW}Your tunnel configurations will be deleted!${NC}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [[ "$confirm" != "yes" && "$confirm" != "YES" && "$confirm" != "y" ]]; then
    echo -e "${GREEN}Uninstall cancelled.${NC}"
    exit 0
fi

echo ""

# Stop services
echo -e "${YELLOW}[1/6] Stopping VortexL2 services...${NC}"
systemctl stop vortexl2-tunnel.service 2>/dev/null || true
systemctl stop vortexl2-forward-daemon.service 2>/dev/null || true
systemctl stop haproxy.service 2>/dev/null || true
# Stop any socat services
systemctl stop 'vortexl2-socat-*.service' 2>/dev/null || true
pkill -f 'socat.*TCP-LISTEN' 2>/dev/null || true
echo -e "${GREEN}  ✓ Services stopped${NC}"

# Stop and remove EasyTier
echo -e "${YELLOW}[2/6] Stopping and removing EasyTier...${NC}"
# Stop all EasyTier services
for svc in $(systemctl list-units --all --plain --no-legend 'vortexl2-easytier-*.service' 2>/dev/null | awk '{print $1}'); do
    systemctl stop "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
done
# Kill any remaining easytier processes
pkill -f 'easytier-core' 2>/dev/null || true
pkill -f 'easytier-cli' 2>/dev/null || true
# Remove EasyTier binaries
rm -f /usr/local/bin/easytier-core
rm -f /usr/local/bin/easytier-cli
# Remove EasyTier service files
rm -f "$SYSTEMD_DIR"/vortexl2-easytier-*.service
echo -e "${GREEN}  ✓ EasyTier removed${NC}"

# Remove DNS Manager
echo -e "${YELLOW}[3/7] Removing DNS Manager...${NC}"
rm -f /usr/local/bin/vortexl2-dns-check
rm -f /etc/cron.d/vortexl2-dns
echo -e "${GREEN}  ✓ DNS Manager removed${NC}"

# Disable services
echo -e "${YELLOW}[4/7] Disabling VortexL2 services...${NC}"
systemctl disable vortexl2-tunnel.service 2>/dev/null || true
systemctl disable vortexl2-forward-daemon.service 2>/dev/null || true
systemctl disable haproxy.service 2>/dev/null || true
echo -e "${GREEN}  ✓ Services disabled${NC}"

# Remove systemd service files
echo -e "${YELLOW}[5/7] Removing systemd service files...${NC}"
rm -f "$SYSTEMD_DIR/vortexl2-tunnel.service"
rm -f "$SYSTEMD_DIR/vortexl2-forward-daemon.service"
rm -f "$SYSTEMD_DIR/vortexl2-forward@.service"
rm -f "$SYSTEMD_DIR"/vortexl2-socat-*.service
rm -f /etc/modules-load.d/vortexl2.conf
systemctl daemon-reload
echo -e "${GREEN}  ✓ Service files removed${NC}"

# Remove VortexL2 files
echo -e "${YELLOW}[6/7] Removing VortexL2 files...${NC}"
rm -rf "$INSTALL_DIR"
rm -f "$BIN_PATH"
echo -e "${GREEN}  ✓ Installation files removed${NC}"

# Remove configuration and data
echo -e "${YELLOW}[7/7] Removing configuration and data...${NC}"
rm -rf "$CONFIG_DIR"
rm -rf "$LOG_DIR"
rm -rf "$DATA_DIR"
echo -e "${GREEN}  ✓ Configuration removed${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  VortexL2 Uninstallation Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${CYAN}VortexL2 has been successfully removed.${NC}"
echo ""
echo -e "${YELLOW}Note: HAProxy was NOT removed (you may be using it for other purposes).${NC}"
echo -e "${YELLOW}To remove HAProxy: sudo apt remove haproxy${NC}"
echo ""
