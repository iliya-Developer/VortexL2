VortexL2 - Advanced L2TPv3 Tunnel Manager v2.0

Professional L2TPv3 Tunnel Management for Iranian & International Servers

A comprehensive CLI tool for managing multiple L2TPv3 tunnels simultaneously with high-speed port forwarding using HAProxy.

🌟 Key Features

🏗️ Advanced Architecture

· Multi-Tunnel System: Unlimited tunnel management on a single server
· HAProxy Integration: High-performance port forwarding
· Systemd Services: Automatic startup and service management

🔧 Technical Capabilities

· Interactive TUI: Rich library-based user interface
· Advanced Validation: Prevents duplicates and ensures uniqueness
· Configuration Management: YAML storage with 0600 permissions
· Comprehensive Logging: Complete logging system for troubleshooting

🚀 Performance

· One-Line Installation: Quick and easy setup
· High Availability: Designed for production environments
· Low Latency: Optimized architecture for minimal delay
· Scalable: Supports heavy traffic loads

📦 Installation & Setup

Method 1: Direct Installation

```bash
# Download and run installation script
curl -sSL https://raw.githubusercontent.com/karenserver71/VortexL2/main/install.sh | sudo bash
```

Method 2: Manual Installation

```bash
# Clone repository
git clone https://github.com/karenserver71/VortexL2.git
cd VortexL2

# Install dependencies
sudo apt-get update
sudo apt-get install -y python3-pip haproxy iproute2
pip3 install -r requirements.txt

# Install package
sudo python3 setup.py install

# Enable services
sudo systemctl daemon-reload
sudo systemctl enable vortexl2-tunnel
sudo systemctl enable vortexl2-forward-daemon
```

🚀 Execution Commands

Main Management Panel

```bash
# Run interactive management panel
sudo vortexl2

# With advanced options
sudo vortexl2 --tunnel all --log-level debug
```

Tunnel Management

```bash
# Apply all tunnels (for system boot)
sudo vortexl2 apply

# Check tunnel status
sudo vortexl2 status

# Show specific tunnel information
sudo vortexl2 show tunnel1
```

Service Management

```bash
# Check service status
sudo systemctl status vortexl2-tunnel
sudo systemctl status vortexl2-forward-daemon
sudo systemctl status haproxy

# View logs
journalctl -u vortexl2-tunnel -f
journalctl -u vortexl2-forward-daemon -f
sudo tail -f /var/log/vortexl2/tunnel.log
```

📊 Tunnel Configuration Example

Iran Side Configuration

```
Side: IRAN
Local IP: 185.100.100.100
Remote IP: 95.179.200.200
Interface IP: 10.30.30.1/30
Tunnel ID: 1000
Peer Tunnel ID: 2000
Session ID: 10
Peer Session ID: 20
Forwarded Ports: 443,80,2053,2083,8443
```

Kharej Side Configuration

```
Side: KHAREJ
Local IP: 95.179.200.200
Remote IP: 185.100.100.100
Interface IP: 10.30.30.2/30
Tunnel ID: 2000
Peer Tunnel ID: 1000
Session ID: 20
Peer Session ID: 10
```

🔍 Troubleshooting Commands

Check Tunnel Status

```bash
# Show L2TP tunnels
ip l2tp show tunnel

# Show L2TP sessions
ip l2tp show session

# Check interfaces
ip addr show | grep l2tpeth

# Test tunnel connectivity
ping 10.30.30.2 -c 4
```

Check Port Forwarding

```bash
# List listening ports (HAProxy)
ss -tlnp | grep haproxy

# Check HAProxy status
sudo systemctl status haproxy

# Test port forwarding
curl -I http://localhost:80
```

⚙️ Configuration Files Structure

```
/etc/vortexl2/
├── tunnels/                    # Tunnel configurations
│   ├── tunnel1.yaml
│   ├── tunnel2.yaml
│   └── haproxy-ports.conf
├── vortexl2.conf              # Main configuration
└── logs/                      # System logs

/var/log/vortexl2/
├── tunnel.log
├── forward.log
└── haproxy.log
```

🗑️ Uninstallation

Complete Removal

```bash
# Stop services
sudo systemctl stop vortexl2-tunnel vortexl2-forward-daemon haproxy
sudo systemctl disable vortexl2-tunnel vortexl2-forward-daemon

# Remove files
sudo rm -rf /opt/vortexl2 /etc/vortexl2 /var/lib/vortexl2 /var/log/vortexl2
sudo rm /usr/local/bin/vortexl2
sudo rm /etc/systemd/system/vortexl2-*.service

# Restore HAProxy if needed
if [ -f /etc/haproxy/haproxy.cfg.bak ]; then
    sudo cp /etc/haproxy/haproxy.cfg.bak /etc/haproxy/haproxy.cfg
    sudo systemctl restart haproxy
fi

# Reload systemd
sudo systemctl daemon-reload
```

📄 License

MIT License

👤 Author & Support

· Developer: Karen Server
· Telegram Support: @karenserver_support
· GitHub Issues: https://github.com/karenserver71/VortexL2/issues

---

⚠️ Security Notice: L2TPv3 provides no encryption by itself. Use IPsec or other VPNs for sensitive traffic.

✅ Note: This project is designed for legal use and network restriction bypassing.
