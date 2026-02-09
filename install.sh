#!/bin/bash
#
# VortexL2 Installer
# L2TPv3 & EasyTier Tunnel Manager for Ubuntu/Debian
#
# Usage: 
#   bash <(curl -Ls https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/install.sh)
#   bash <(curl -Ls https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/install.sh) v1.1.0
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
GITHUB_REPO="iliya-Developer/VortexL2"
REPO_URL="https://github.com/${GITHUB_REPO}.git"
REPO_BRANCH="dev"

# Get version from argument (if provided)
VERSION="${1:-}"

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
echo -e "${CYAN}L2TPv3 & EasyTier Tunnel Manager${NC}"
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

# ============================================
# TUNNEL TYPE SELECTION
# ============================================
echo -e "${YELLOW}Select Tunnel Type:${NC}"
echo -e "  ${CYAN}[1]${NC} L2TPv3  - Traditional L2TP Ethernet tunnel"
echo -e "  ${CYAN}[2]${NC} EasyTier - Mesh VPN tunnel"
echo ""
read -p "Enter choice [1/2] (default: 1): " TUNNEL_CHOICE

case "$TUNNEL_CHOICE" in
    2)
        TUNNEL_MODE="easytier"
        echo -e "${GREEN}✓ Selected: EasyTier${NC}"
        ;;
    *)
        TUNNEL_MODE="l2tpv3"
        echo -e "${GREEN}✓ Selected: L2TPv3${NC}"
        ;;
esac
echo ""

# VERSION CHECK
# ============================================
check_version_exists() {
    local version="$1"
    local url="https://github.com/${GITHUB_REPO}/archive/refs/tags/${version}.tar.gz"
    if curl --output /dev/null --silent --head --fail "$url"; then
        return 0
    else
        return 1
    fi
}

get_latest_version() {
    local latest
    latest=$(curl -fsSL "https://api.github.com/repos/${GITHUB_REPO}/releases/latest" 2>/dev/null | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -n "$latest" ]; then
        echo "$latest"
    else
        echo ""
    fi
}

# Check if version supports EasyTier (v4.0.0+)
version_supports_easytier() {
    local version="$1"
    # main branch always has latest
    if [ "$version" = "main" ]; then
        return 0
    fi
    # Extract version number (remove 'v' prefix)
    local ver_num="${version#v}"
    local major="${ver_num%%.*}"
    # EasyTier requires v4.0.0 or higher
    if [ "$major" -ge 4 ] 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

if [ -n "$VERSION" ]; then
    echo -e "${YELLOW}Checking version: ${VERSION}${NC}"
    if [[ ! "$VERSION" =~ ^v ]]; then
        VERSION="v${VERSION}"
    fi
    if check_version_exists "$VERSION"; then
        # Check EasyTier compatibility
        if [ "$TUNNEL_MODE" = "easytier" ] && ! version_supports_easytier "$VERSION"; then
            echo -e "${RED}✗ Error: Version ${VERSION} does not support EasyTier!${NC}"
            echo -e "${YELLOW}EasyTier requires v4.0.0 or higher.${NC}"
            echo -e "${YELLOW}Installing from ${REPO_BRANCH} branch instead...${NC}"
            DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/archive/refs/heads/${REPO_BRANCH}.tar.gz"
            INSTALL_VERSION="${REPO_BRANCH} (EasyTier)"
        else
            echo -e "${GREEN}✓ Version ${VERSION} found!${NC}"
            DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/archive/refs/tags/${VERSION}.tar.gz"
            INSTALL_VERSION="$VERSION"
        fi
    else
        echo -e "${RED}✗ Error: Version ${VERSION} not found on GitHub!${NC}"
        echo -e "${YELLOW}Available versions: https://github.com/${GITHUB_REPO}/releases${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}No version specified. Checking for latest release...${NC}"
    LATEST_VERSION=$(get_latest_version)
    
    # For EasyTier, check if latest version supports it
    if [ "$TUNNEL_MODE" = "easytier" ]; then
        if [ -n "$LATEST_VERSION" ] && version_supports_easytier "$LATEST_VERSION"; then
            echo -e "${GREEN}✓ Latest release: ${LATEST_VERSION}${NC}"
            DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/archive/refs/tags/${LATEST_VERSION}.tar.gz"
            INSTALL_VERSION="$LATEST_VERSION"
        else
            echo -e "${YELLOW}Latest release (${LATEST_VERSION:-none}) does not support EasyTier.${NC}"
            echo -e "${YELLOW}Installing from ${REPO_BRANCH} branch (v4.0.0+)...${NC}"
            DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/archive/refs/heads/${REPO_BRANCH}.tar.gz"
            INSTALL_VERSION="${REPO_BRANCH} (EasyTier)"
        fi
    else
        if [ -n "$LATEST_VERSION" ]; then
            echo -e "${GREEN}✓ Latest release: ${LATEST_VERSION}${NC}"
            DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/archive/refs/tags/${LATEST_VERSION}.tar.gz"
            INSTALL_VERSION="$LATEST_VERSION"
        else
            echo -e "${YELLOW}No releases found. Installing from ${REPO_BRANCH} branch...${NC}"
            DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/archive/refs/heads/${REPO_BRANCH}.tar.gz"
            INSTALL_VERSION="${REPO_BRANCH}"
        fi
    fi
fi

echo -e "${CYAN}Installing version: ${INSTALL_VERSION}${NC}"
echo ""

# ============================================
# INSTALL DEPENDENCIES
# ============================================
echo -e "${YELLOW}[1/6] Installing system dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv curl haproxy socat

if [ "$TUNNEL_MODE" = "l2tpv3" ]; then
    apt-get install -y -qq iproute2
    
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
else
    echo -e "${YELLOW}[2/6] Skipping kernel modules (not needed for EasyTier)...${NC}"
    echo -e "${YELLOW}[3/6] Skipping L2TP setup (EasyTier mode)...${NC}"
fi

# ============================================
# DOWNLOAD AND INSTALL
# ============================================
echo -e "${YELLOW}[4/6] Installing VortexL2 (${INSTALL_VERSION})...${NC}"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Removing existing installation...${NC}"
    rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"
echo -e "${YELLOW}Downloading from: ${DOWNLOAD_URL}${NC}"

if ! curl -fsSL "$DOWNLOAD_URL" | tar -xz -C "$INSTALL_DIR" --strip-components=1; then
    echo -e "${RED}Error: Failed to download VortexL2${NC}"
    exit 1
fi

echo -e "${GREEN}✓ VortexL2 ${INSTALL_VERSION} downloaded successfully${NC}"

# ============================================
# EASYTIER BINARY SETUP
# ============================================
if [ "$TUNNEL_MODE" = "easytier" ]; then
    echo -e "${YELLOW}Setting up EasyTier binaries...${NC}"
    
    # Stop any running EasyTier services first (to avoid "Text file busy")
    echo -e "${YELLOW}Stopping running EasyTier processes...${NC}"
    systemctl stop 'vortexl2-easytier-*' 2>/dev/null || true
    killall -9 easytier-core 2>/dev/null || true
    killall -9 easytier-cli 2>/dev/null || true
    pkill -9 -f easytier 2>/dev/null || true
    sleep 2
    
    # Force remove old binaries
    rm -f /usr/local/bin/easytier-core 2>/dev/null || true
    rm -f /usr/local/bin/easytier-cli 2>/dev/null || true
    
    # Detect architecture
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64|amd64)
            EASYTIER_ARCH="linux-x86_64"
            ;;
        armv7l|armhf)
            EASYTIER_ARCH="linux-armv7"
            ;;
        aarch64|arm64)
            EASYTIER_ARCH="linux-x86_64"
            echo -e "${YELLOW}Warning: arm64 detected, trying x86_64 binaries...${NC}"
            ;;
        *)
            echo -e "${RED}Error: Unsupported architecture: ${ARCH}${NC}"
            echo -e "${YELLOW}Supported: x86_64, armv7${NC}"
            exit 1
            ;;
    esac
    
    EASYTIER_SRC="$INSTALL_DIR/core/easytier/$EASYTIER_ARCH"
    
    if [ -d "$EASYTIER_SRC" ]; then
        cp "$EASYTIER_SRC/easytier-core" /usr/local/bin/
        cp "$EASYTIER_SRC/easytier-cli" /usr/local/bin/
        chmod +x /usr/local/bin/easytier-core
        chmod +x /usr/local/bin/easytier-cli
        echo -e "${GREEN}✓ EasyTier binaries installed (${EASYTIER_ARCH})${NC}"
    else
        echo -e "${RED}Error: EasyTier binaries not found for ${EASYTIER_ARCH}${NC}"
        exit 1
    fi
fi

# ============================================
# PYTHON DEPENDENCIES
# ============================================
echo -e "${YELLOW}[5/6] Installing Python dependencies...${NC}"
apt-get install -y -qq python3-rich python3-yaml 2>/dev/null || {
    echo -e "${YELLOW}Apt packages not available, trying pip...${NC}"
    pip3 install --quiet --break-system-packages rich pyyaml 2>/dev/null || \
    pip3 install --quiet rich pyyaml 2>/dev/null || {
        echo -e "${RED}Failed to install Python dependencies${NC}"
        echo -e "${YELLOW}Try manually: apt install python3-rich python3-yaml${NC}"
        exit 1
    }
}

# ============================================
# CREATE LAUNCHER AND CONFIG
# ============================================
cat > "$BIN_PATH" << 'EOF'
#!/bin/bash
# VortexL2 Launcher
exec python3 /opt/vortexl2/vortexl2/main.py "$@"
EOF
chmod +x "$BIN_PATH"

# Install DNS check script
cp "$INSTALL_DIR/scripts/vortexl2-dns-check" /usr/local/bin/
chmod +x /usr/local/bin/vortexl2-dns-check

# Install dnsutils for nslookup
apt-get install -y -qq dnsutils 2>/dev/null || true

# Save installed version and tunnel mode
echo "$INSTALL_VERSION" > "$INSTALL_DIR/.version"

# Create config directories
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/tunnels"
mkdir -p /var/lib/vortexl2
mkdir -p /var/log/vortexl2
mkdir -p /etc/vortexl2/haproxy
chmod 700 "$CONFIG_DIR"
chmod 755 /var/lib/vortexl2
chmod 755 /var/log/vortexl2

# Save tunnel mode to global config
cat > "$CONFIG_DIR/config.yaml" << EOF
tunnel_mode: $TUNNEL_MODE
forward_mode: none
EOF
chmod 600 "$CONFIG_DIR/config.yaml"

# ============================================
# SYSTEMD SERVICES
# ============================================
echo -e "${YELLOW}[6/6] Installing systemd services...${NC}"

if [ "$TUNNEL_MODE" = "l2tpv3" ]; then
    cp "$INSTALL_DIR/systemd/vortexl2-tunnel.service" "$SYSTEMD_DIR/"
fi
cp "$INSTALL_DIR/systemd/vortexl2-forward-daemon.service" "$SYSTEMD_DIR/"

systemctl daemon-reload

# ============================================
# CLEANUP OLD SERVICES
# ============================================
echo -e "${YELLOW}Cleaning up old services...${NC}"
systemctl stop 'vortexl2-forward@*.service' 2>/dev/null || true
systemctl disable 'vortexl2-forward@*.service' 2>/dev/null || true
rm -f "$SYSTEMD_DIR/vortexl2-forward@.service" 2>/dev/null || true

if command -v nft &> /dev/null; then
    nft delete table inet vortexl2_filter 2>/dev/null || true
    nft delete table ip vortexl2_nat 2>/dev/null || true
fi
rm -f /etc/nftables.d/vortexl2-forward.nft 2>/dev/null || true
rm -f /etc/sysctl.d/99-vortexl2-forward.conf 2>/dev/null || true

systemctl stop vortexl2-forward-daemon.service 2>/dev/null || true

echo -e "${GREEN}  ✓ Old services cleaned up${NC}"

# ============================================
# ENABLE SERVICES
# ============================================
if [ "$TUNNEL_MODE" = "l2tpv3" ]; then
    systemctl enable vortexl2-tunnel.service 2>/dev/null || true
fi
systemctl enable vortexl2-forward-daemon.service 2>/dev/null || true

# Start services
echo -e "${YELLOW}Starting VortexL2 services...${NC}"

if [ "$TUNNEL_MODE" = "l2tpv3" ]; then
    if systemctl is-active --quiet vortexl2-tunnel.service 2>/dev/null; then
        systemctl restart vortexl2-tunnel.service
        echo -e "${GREEN}  ✓ vortexl2-tunnel service restarted${NC}"
    else
        systemctl start vortexl2-tunnel.service 2>/dev/null || true
        echo -e "${GREEN}  ✓ vortexl2-tunnel service started${NC}"
    fi
elif [ "$TUNNEL_MODE" = "easytier" ]; then
    # Restart all EasyTier tunnel services that were previously configured
    for service in /etc/systemd/system/vortexl2-easytier-*.service; do
        if [ -f "$service" ]; then
            svc_name=$(basename "$service")
            echo -e "${YELLOW}  Restarting ${svc_name}...${NC}"
            systemctl restart "$svc_name" 2>/dev/null || true
            echo -e "${GREEN}  ✓ ${svc_name} restarted${NC}"
        fi
    done
fi

echo -e "${YELLOW}  ℹ Port forwarding is DISABLED by default${NC}"
echo -e "${YELLOW}  ℹ Use 'sudo vortexl2' → Port Forwards → Change Mode to enable${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  VortexL2 ${INSTALL_VERSION} Installation Complete!${NC}"
echo -e "${GREEN}  Tunnel Mode: ${TUNNEL_MODE^^}${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo -e "  1. Run: ${GREEN}sudo vortexl2${NC}"
if [ "$TUNNEL_MODE" = "l2tpv3" ]; then
    echo -e "  2. Create Tunnel (select IRAN or KHAREJ)"
    echo -e "  3. Configure IPs"
else
    echo -e "  2. Create EasyTier Tunnel (configure mesh)"
    echo -e "  3. Set peer IP and secret"
fi
echo -e "  4. Add port forwards"
echo ""
echo -e "${YELLOW}Quick start:${NC}"
echo -e "  ${GREEN}sudo vortexl2${NC}       - Open management panel"
echo ""
echo -e "${CYAN}Install specific version:${NC}"
echo -e "  ${GREEN}bash <(curl -Ls https://raw.githubusercontent.com/${GITHUB_REPO}/main/install.sh) v1.1.0${NC}"
echo ""
echo -e "${RED}Security Note:${NC}"
if [ "$TUNNEL_MODE" = "l2tpv3" ]; then
    echo -e "  L2TPv3 has NO encryption. For sensitive traffic,"
    echo -e "  consider adding IPsec or WireGuard on top."
else
    echo -e "  EasyTier uses encryption by default."
fi
echo ""
