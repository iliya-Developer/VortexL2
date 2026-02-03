# VortexL2

**L2TPv3 Ethernet Tunnel Manager for Ubuntu/Debian**

A modular, production-quality CLI tool for managing L2TPv3 tunnels and TCP port forwarding via socat.

```
 __      __        _            _     ___  
 \ \    / /       | |          | |   |__ \ 
  \ \  / /__  _ __| |_ _____  _| |      ) |
   \ \/ / _ \| '__| __/ _ \ \/ / |     / / 
    \  / (_) | |  | ||  __/>  <| |____/ /_ 
     \/ \___/|_|   \__\___/_/\_\______|____|
```

## ✨ Features

- 🔧 Interactive TUI management panel with Rich
- 🌐 L2TPv3 Ethernet tunnel (encap ip mode)
- 🔀 TCP port forwarding via socat (Iran side)
- 🔄 Systemd integration for persistence
- 📦 One-liner installation
- 🛡️ Secure configuration with 0600 permissions

## 📦 Quick Install

```bash
bash <(curl -Ls https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/install.sh)
```

## 🚀 First Run

### 1. Open the Management Panel

```bash
sudo vortexl2
```

### 2. Select Your Role

- **IRAN**: The server that receives connections and forwards ports
- **KHAREJ**: The remote tunnel endpoint (e.g., server outside Iran)

### 3. Configure Endpoints

Enter the public IPs for both servers when prompted:
- Iran Server Public IP
- Kharej Server Public IP

### 4. Create Tunnel

Select "Create/Start Tunnel" from the menu.

### 5. Add Port Forwards (Iran side only)

Select "Port Forwards" and add ports like: `443,80,2053`

## 🎯 Usage Examples

### Iran Side Setup

```bash
# Open panel
sudo vortexl2

# 1. Install prerequisites (option 1)
# 2. Configure endpoints (option 2)
#    - Select role: IRAN
#    - Enter Iran public IP: YOUR_IRAN_IP
#    - Enter Kharej public IP: YOUR_KHAREJ_IP
#    - Iran l2tpeth0 IP: 10.30.30.1/30 (default)
#    - Remote Forward IP: 10.30.30.2 (default)
# 3. Create tunnel (option 3)
# 4. Add port forwards (option 5 → 1)
#    - Enter ports: 443,80,2053
```

### kharej Side Setup

```bash
# Open panel
sudo vortexl2

# 1. Install prerequisites (option 1)
# 2. Configure endpoints (option 2)
#    - Select role: KHAREJ
#    - Enter Iran public IP: IRAN_SERVER_IP
#    - Enter Kharej public IP: YOUR_KHAREJ_IP
# 3. Create tunnel (option 3)
```

## 📋 Commands

| Command | Description |
|---------|-------------|
| `sudo vortexl2` | Open management panel |
| `sudo vortexl2 --version` | Show version |

## 🔍 Troubleshooting

### Check Tunnel Status

```bash
# Show L2TP tunnels
ip l2tp show tunnel

# Show L2TP sessions
ip l2tp show session

# Check interface
ip addr show l2tpeth0
```

### Check Port Forwards

```bash
# List listening ports
ss -ltnp | grep socat

# Check service status
systemctl status vortexl2-forward@443
```

### View Logs

```bash
# Tunnel service logs
journalctl -u vortexl2-tunnel -f

# Forward service logs
journalctl -u vortexl2-forward@443 -f
```

### Common Issues

**❌ Tunnel not working**
1. Ensure both sides have configured with correct IPs
2. Check firewall allows IP protocol 115 (L2TPv3)
3. Verify kernel modules are loaded: `lsmod | grep l2tp`

**❌ Port forward not working**
1. Check socat is installed: `which socat`
2. Verify tunnel is up: `ping 10.30.30.2` (from Iran side)
3. Check service status: `systemctl status vortexl2-forward@PORT`

**❌ Interface l2tpeth0 not found**
1. Ensure session is created (not just tunnel)
2. Check kernel modules: `modprobe l2tp_eth`
3. Recreate tunnel from panel

## 🔧 Configuration

Configuration is stored in `/etc/vortexl2/config.yaml`:

```yaml
version: "1.0.0"
role: "IRAN"
ip_iran: "1.2.3.4"
ip_kharej: "5.6.7.8"
iran_iface_ip: "10.30.30.1/30"
remote_forward_ip: "10.30.30.2"
forwarded_ports:
  - 443
  - 80
  - 2053
```

## 🏗️ Architecture

```
                    ┌─────────────────┐
                    │   IRAN Server   │
                    │   1.2.3.4       │
                    │                 │
                    │  ┌───────────┐  │
 Users ──────────►  │  │  socat    │  │
 (443,80,2053)      │  │  forwards │  │
                    │  └─────┬─────┘  │
                    │        │        │
                    │  ┌─────▼─────┐  │
                    │  │ l2tpeth0  │  │
                    │  │10.30.30.1 │  │
                    │  └─────┬─────┘  │
                    └────────┼────────┘
                             │
                      L2TPv3 Tunnel
                      (encap ip)
                             │
                    ┌────────┼────────┐
                    │  ┌─────▼─────┐  │
                    │  │ l2tpeth0  │  │
                    │  │10.30.30.2 │  │
                    │  └───────────┘  │
                    │                 │
                    │ KHAREJ Server  │
                    │   5.6.7.8       │
                    └─────────────────┘
```

## 📁 Project Structure

```
VortexL2/
├── vortexl2/
│   ├── __init__.py     # Package info
│   ├── main.py         # CLI entry point
│   ├── config.py       # Configuration management
│   ├── tunnel.py       # L2TPv3 tunnel operations
│   ├── forward.py      # Port forward management
│   └── ui.py           # Rich TUI interface
├── systemd/
│   ├── vortexl2-tunnel.service      # Tunnel boot service
│   └── vortexl2-forward@.service    # Template for forwards
├── install.sh          # Installation script
└── README.md           # This file
```

## ⚠️ Security Notice

**L2TPv3 provides NO encryption!**

The tunnel transports raw Ethernet frames over IP without any encryption. This is suitable for:
- ✅ Bypassing network restrictions
- ✅ Creating L2 connectivity
- ❌ NOT secure for sensitive data in transit

For encrypted traffic, consider:
- Adding IPsec on top of L2TPv3
- Using WireGuard as an alternative
- Encrypting application-level traffic (TLS/HTTPS)

## 🔄 Uninstall

```bash
# Stop services
sudo systemctl stop vortexl2-tunnel
sudo systemctl disable vortexl2-tunnel

# Remove files
sudo rm -rf /opt/vortexl2
sudo rm /usr/local/bin/vortexl2
sudo rm /etc/systemd/system/vortexl2-*
sudo rm -rf /etc/vortexl2

# Reload systemd
sudo systemctl daemon-reload
```

## 📄 License

MIT License

## 👤 Author

VortexL2 Team

---

**Version 1.0.0**
