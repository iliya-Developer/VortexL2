# VortexL2

**L2TPv3 & EasyTier Tunnel Manager for Ubuntu/Debian**

A modular, production-quality CLI tool for managing L2TPv3 or EasyTier mesh tunnels with HAProxy-based port forwarding.

```
 __      __        _            _     ___  
 \ \    / /       | |          | |   |__ \ 
  \ \  / /__  _ __| |_ _____  _| |      ) |
   \ \/ / _ \| '__| __/ _ \ \/ / |     / / 
    \  / (_) | |  | ||  __/>  <| |____/ /_ 
     \/ \___/|_|   \__\___/_/\_\______|____|
                                    v4.0.0
```

## ✨ Features

- 🔧 Interactive TUI management panel with Rich
- 🌐 **Two tunnel types:** L2TPv3 or EasyTier mesh
- 🚀 **HAProxy port forwarding**: High performance, manual activation
- 🔄 Systemd integration for persistence
- 📦 One-liner installation

## 📦 Installation

```bash
bash <(curl -Ls https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/install.sh)
```

During installation, choose:
- **L2TPv3** - Traditional L2TP Ethernet tunnel
- **EasyTier** - Modern mesh VPN tunnel

### Install Specific Version

```bash
bash <(curl -Ls https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/install.sh) v4.0.0
```

## 🚀 Quick Start

```bash
sudo vortexl2
```

### L2TPv3 Mode
1. Create Tunnel → Select IRAN or KHAREJ
2. Configure IPs and tunnel IDs
3. Add port forwards (IRAN side only)

### EasyTier Mode
1. Create Tunnel → Select IRAN or KHAREJ
2. Configure mesh IP, peer IP, port, secret
3. Add port forwards

## 📋 Configuration Examples

### L2TPv3 Setup

| Parameter | IRAN | KHAREJ |
|-----------|------|--------|
| Local IP | 1.2.3.4 | 5.6.7.8 |
| Remote IP | 5.6.7.8 | 1.2.3.4 |
| Interface IP | 10.30.30.1/30 | 10.30.30.2/30 |
| Tunnel ID | 1000 | 2000 |

### EasyTier Setup

| Parameter | IRAN | KHAREJ |
|-----------|------|--------|
| Tunnel IP | 10.155.155.1 | 10.155.155.2 |
| Peer IP | (Kharej public) | (Iran public) |
| Port | 2070 | 2070 |
| Secret | vortexl2 | vortexl2 |

## 🔧 Services

```bash
# Check status
sudo systemctl status vortexl2-tunnel          # L2TPv3
sudo systemctl status vortexl2-easytier-*      # EasyTier
sudo systemctl status vortexl2-forward-daemon

# View logs
journalctl -u vortexl2-forward-daemon -f
```

## 🔍 Troubleshooting

### L2TPv3 Issues
- Verify matching tunnel IDs (swapped on each side)
- Check firewall allows IP protocol 115
- Verify modules: `lsmod | grep l2tp`

### EasyTier Issues
- Verify same secret on both nodes
- Check firewall allows the port (default 2070)
- Check tunnel IP can ping peer

## 🔄 Uninstall

```bash
bash <(curl -Ls https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/uninstall.sh)
```

## ⚠️ Security

- **L2TPv3**: NO encryption. Use IPsec or encrypted apps.
- **EasyTier**: Built-in encryption.

## 📄 License

MIT License

## 👤 Author

Telegram: @iliyadevsh