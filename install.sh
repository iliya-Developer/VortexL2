#!/bin/bash
#
# VortexL2 Installer
# L2TPv3 Tunnel Manager for Ubuntu/Debian
#
# Usage: curl -fsSL https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/install.sh | sudo bash
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
REPO_URL="https://github.com/iliya-Developer/VortexL2.git"
REPO_BRANCH="main"

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
echo -e "${GREEN}VortexL2 Installer${NC}"
echo -e "${CYAN}L2TPv3 Tunnel Manager for Ubuntu/Debian${NC}"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

# Check OS
if ! command -v apt-get &> /dev/null; then
    echo -e "${RED}Error: This installer requires apt-get (Debian/Ubuntu)${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/6] Installing system dependencies...${NC}"
apt-get update -qq
# Install haproxy for high-performance port forwarding (not auto-started)
apt-get install -y -qq python3 python3-pip python3-venv git iproute2 haproxy wireguard-tools

# Install kernel modules package
KERNEL_VERSION=$(uname -r)
echo -e "${YELLOW}[2/6] Installing kernel modules for ${KERNEL_VERSION}...${NC}"
apt-get install -y -qq "linux-modules-extra-${KERNEL_VERSION}" 2>/dev/null || \
    echo -e "${YELLOW}Warning: Could not install linux-modules-extra (may already be available)${NC}"

# Load L2TP modules
echo -e "${YELLOW}[3/6] Loading L2TP kernel modules...${NC}"
modprobe l2tp_core 2>/dev/null || true
modprobe l2tp_netlink 2>/dev/null || true
modprobe l2tp_eth 2>/dev/null || true

# Ensure modules load on boot
cat > /etc/modules-load.d/vortexl2.conf << 'EOF'
l2tp_core
l2tp_netlink
l2tp_eth
EOF

echo -e "${YELLOW}[4/6] Installing VortexL2...${NC}"

# Always remove existing installation and reinstall fresh
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Removing existing installation...${NC}"
    rm -rf "$INSTALL_DIR"
fi

# Clone or download repository
if command -v git &> /dev/null; then
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
        echo -e "${YELLOW}Git clone failed, trying manual download...${NC}"
        mkdir -p "$INSTALL_DIR"
        # If git fails, try downloading as archive
        curl -fsSL "https://github.com/iliya-Developer/VortexL2/archive/refs/heads/${REPO_BRANCH}.tar.gz" | \
            tar -xz -C "$INSTALL_DIR" --strip-components=1
    }
else
    mkdir -p "$INSTALL_DIR"
    curl -fsSL "https://github.com/iliya-Developer/VortexL2/archive/refs/heads/${REPO_BRANCH}.tar.gz" | \
        tar -xz -C "$INSTALL_DIR" --strip-components=1
fi

# Install Python dependencies
echo -e "${YELLOW}[5/6] Installing Python dependencies...${NC}"
# Try apt first (works on most systems), then fallback to pip
apt-get install -y -qq python3-rich python3-yaml 2>/dev/null || {
    echo -e "${YELLOW}Apt packages not available, trying pip...${NC}"
    pip3 install --quiet --break-system-packages rich pyyaml 2>/dev/null || \
    pip3 install --quiet rich pyyaml 2>/dev/null || {
        echo -e "${RED}Failed to install Python dependencies${NC}"
        echo -e "${YELLOW}Try manually: apt install python3-rich python3-yaml${NC}"
        exit 1
    }
}

# Create launcher script
cat > "$BIN_PATH" << 'EOF'
#!/bin/bash
# VortexL2 Launcher
exec python3 /opt/vortexl2/vortexl2/main.py "$@"
EOF
chmod +x "$BIN_PATH"

# Install systemd units
echo -e "${YELLOW}[6/6] Installing systemd services...${NC}"
cp "$INSTALL_DIR/systemd/vortexl2-tunnel.service" "$SYSTEMD_DIR/"
cp "$INSTALL_DIR/systemd/vortexl2-forward-daemon.service" "$SYSTEMD_DIR/"
cp "$INSTALL_DIR/systemd/vortexl2-wireguard.service" "$SYSTEMD_DIR/"

# Create config directories
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/tunnels"
mkdir -p /var/lib/vortexl2
mkdir -p /var/log/vortexl2
mkdir -p /etc/vortexl2/haproxy
mkdir -p /etc/vortex/wg
chmod 700 "$CONFIG_DIR"
chmod 755 /var/lib/vortexl2
chmod 755 /var/log/vortexl2
chown root:root /etc/vortexl2/haproxy || true
chmod 755 /etc/vortexl2/haproxy || true
chmod 700 /etc/vortex/wg

# Reload systemd
systemctl daemon-reload

# ---- CLEANUP OLD SERVICES ----
echo -e "${YELLOW}Cleaning up old services...${NC}"

# Stop and disable old socat-based forward services
systemctl stop 'vortexl2-forward@*.service' 2>/dev/null || true
systemctl disable 'vortexl2-forward@*.service' 2>/dev/null || true
rm -f "$SYSTEMD_DIR/vortexl2-forward@.service" 2>/dev/null || true

# Remove old nftables rules if they exist
if command -v nft &> /dev/null; then
    nft delete table inet vortexl2_filter 2>/dev/null || true
    nft delete table ip vortexl2_nat 2>/dev/null || true
fi
rm -f /etc/nftables.d/vortexl2-forward.nft 2>/dev/null || true
rm -f /etc/sysctl.d/99-vortexl2-forward.conf 2>/dev/null || true

# Stop old forward daemon if running (will be restarted with new config)
systemctl stop vortexl2-forward-daemon.service 2>/dev/null || true

echo -e "${GREEN}  ✓ Old services cleaned up${NC}"

# Enable services (but don't auto-start forwarding - user chooses mode)
systemctl enable vortexl2-tunnel.service 2>/dev/null || true
systemctl enable vortexl2-forward-daemon.service 2>/dev/null || true
# Don't auto-enable haproxy - only enable if user selects haproxy mode

# Start/Restart services
echo -e "${YELLOW}Starting VortexL2 services...${NC}"

# For tunnel service: restart if active, otherwise just enable (it runs on-demand)
if systemctl is-active --quiet vortexl2-tunnel.service 2>/dev/null; then
    systemctl restart vortexl2-tunnel.service
    echo -e "${GREEN}  ✓ vortexl2-tunnel service restarted${NC}"
else
    # Start once to apply any existing configurations
    systemctl start vortexl2-tunnel.service 2>/dev/null || true
    echo -e "${GREEN}  ✓ vortexl2-tunnel service started${NC}"
fi

# NOTE: Forward daemon and HAProxy are NOT auto-started
# User must select forward mode (socat/haproxy) in the panel to enable port forwarding
echo -e "${YELLOW}  ℹ Port forwarding is DISABLED by default${NC}"
echo -e "${YELLOW}  ℹ Use 'sudo vortexl2' → Port Forwards → Change Mode to enable${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  VortexL2 Installation Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo -e "  1. Run: ${GREEN}sudo vortexl2${NC}"
echo -e "  2. Create Tunnel (select IRAN or KHAREJ)"
echo -e "  3. Configure IPs"
echo -e "  4. Add port forwards (Iran side only)"
echo ""
echo -e "${YELLOW}Quick start:${NC}"
echo -e "  ${GREEN}sudo vortexl2${NC}       - Open management panel"
echo ""
echo -e "${CYAN}For Iran side port forwarding:${NC}"
echo -e "  Use menu option 5 to add ports like: 443,80,2053"
echo ""
echo -e "${CYAN}Encryption:${NC}"
echo -e "  Use menu option 6 to enable WireGuard encryption layer"
echo -e "  This adds kernel-level encryption inside the L2TP tunnel"
echo ""
