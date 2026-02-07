"""
VortexL2 WireGuard Encryption Layer Manager

Manages WireGuard as a secondary encryption layer running inside the L2TPv3 tunnel.
Architecture: L2TPv3 (carrier) -> WireGuard (encryption) -> Port Forwarding

Keys are stored in /etc/vortex/wg/ for persistence.
WireGuard uses L2TP internal IPs as endpoints and 10.8.0.x as its own subnet.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Dict, Optional

logger = logging.getLogger(__name__)

# WireGuard configuration paths
WG_CONFIG_DIR = Path("/etc/vortex/wg")
WG_PRIVATE_KEY_FILE = WG_CONFIG_DIR / "privatekey"
WG_PUBLIC_KEY_FILE = WG_CONFIG_DIR / "publickey"
WG_CONF_FILE = WG_CONFIG_DIR / "wg_vortex.conf"
WG_INTERFACE = "wg_vortex"
WG_LISTEN_PORT = 51820
WG_MTU = 1380
L2TP_MTU_WITH_WG = 1450
BBR_SYSCTL_FILE = Path("/etc/sysctl.d/99-vortexl2-bbr.conf")
WG_SYSTEMD_FILE = Path("/etc/systemd/system/vortexl2-wireguard.service")


def _run(cmd: str, timeout: int = 30) -> Tuple[bool, str, str]:
    """Execute a shell command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


class WireGuardManager:
    """Manages WireGuard encryption layer for VortexL2 tunnels."""

    def __init__(self, config=None):
        """
        Initialize WireGuard manager.

        Args:
            config: TunnelConfig instance (optional for status-only operations)
        """
        self.config = config

    # ------------------------------------------------------------------
    # Dependency checks
    # ------------------------------------------------------------------

    @staticmethod
    def check_wireguard_installed() -> bool:
        """Check if wireguard-tools is installed."""
        ok, _, _ = _run("which wg")
        return ok

    @staticmethod
    def install_wireguard() -> Tuple[bool, str]:
        """Install wireguard-tools and load the kernel module."""
        steps = []

        # Install wireguard-tools
        steps.append("Installing wireguard-tools...")
        ok, out, err = _run("apt-get install -y wireguard-tools", timeout=120)
        if not ok:
            return False, f"Failed to install wireguard-tools: {err}"
        steps.append("wireguard-tools installed successfully")

        # Ensure iproute2 is present
        ok, _, _ = _run("which ip")
        if not ok:
            steps.append("Installing iproute2...")
            _run("apt-get install -y iproute2", timeout=60)

        # Load WireGuard kernel module
        steps.append("Loading wireguard kernel module...")
        ok, _, err = _run("modprobe wireguard")
        if not ok:
            steps.append(f"Warning: Could not load wireguard module: {err}")
            steps.append("WireGuard may still work via userspace (wireguard-go)")
        else:
            steps.append("wireguard module loaded")

        # Persist module loading on boot
        modules_file = Path("/etc/modules-load.d/vortexl2-wireguard.conf")
        try:
            modules_file.write_text("wireguard\n")
            steps.append("Module configured to load on boot")
        except Exception as e:
            steps.append(f"Warning: Could not persist module loading: {e}")

        steps.append("WireGuard installation complete!")
        return True, "\n".join(steps)

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    @staticmethod
    def generate_keys(force: bool = False) -> Tuple[bool, str]:
        """
        Generate WireGuard private/public key pair.
        Keys are stored in /etc/vortex/wg/ and persist across reboots.
        Idempotent: skips generation if keys already exist unless force=True.
        """
        WG_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(str(WG_CONFIG_DIR), 0o700)

        # Skip if keys already exist and force is not set
        if not force and WG_PRIVATE_KEY_FILE.exists() and WG_PUBLIC_KEY_FILE.exists():
            return True, "Keys already exist (use force=True to regenerate)"

        # Generate private key
        ok, privkey, err = _run("wg genkey")
        if not ok or not privkey:
            return False, f"Failed to generate private key: {err}"

        # Write private key
        WG_PRIVATE_KEY_FILE.write_text(privkey + "\n")
        os.chmod(str(WG_PRIVATE_KEY_FILE), 0o600)

        # Derive public key
        ok, pubkey, err = _run(f"echo '{privkey}' | wg pubkey")
        if not ok or not pubkey:
            return False, f"Failed to derive public key: {err}"

        # Write public key
        WG_PUBLIC_KEY_FILE.write_text(pubkey + "\n")
        os.chmod(str(WG_PUBLIC_KEY_FILE), 0o644)

        return True, f"Keys generated and stored in {WG_CONFIG_DIR}"

    @staticmethod
    def get_keys() -> Dict[str, Optional[str]]:
        """Read existing keys from disk."""
        keys = {"private_key": None, "public_key": None}
        if WG_PRIVATE_KEY_FILE.exists():
            keys["private_key"] = WG_PRIVATE_KEY_FILE.read_text().strip()
        if WG_PUBLIC_KEY_FILE.exists():
            keys["public_key"] = WG_PUBLIC_KEY_FILE.read_text().strip()
        return keys

    # ------------------------------------------------------------------
    # WireGuard interface management
    # ------------------------------------------------------------------

    def enable(self, tunnel_config, side: str, peer_public_key: str) -> Tuple[bool, str]:
        """
        Enable WireGuard encryption layer on top of an L2TP tunnel.

        Args:
            tunnel_config: TunnelConfig with L2TP internal IPs
            side: "IRAN" or "KHAREJ"
            peer_public_key: The remote peer's WireGuard public key

        Returns:
            (success, message)
        """
        steps = []

        # Validate inputs
        if not peer_public_key or len(peer_public_key) < 40:
            return False, "Invalid peer public key"

        # Ensure keys exist
        keys = self.get_keys()
        if not keys["private_key"]:
            ok, msg = self.generate_keys()
            if not ok:
                return False, f"Key generation failed: {msg}"
            keys = self.get_keys()
            steps.append("Generated new WireGuard keys")

        # Determine IPs based on side
        if side == "IRAN":
            wg_ip = "10.8.0.1/24"
            wg_local_ip = "10.8.0.1"
        else:
            wg_ip = "10.8.0.2/24"
            wg_local_ip = "10.8.0.2"

        # L2TP internal IP of the peer is the WireGuard endpoint
        l2tp_peer_ip = tunnel_config.remote_forward_ip
        if not l2tp_peer_ip:
            # Fallback: derive from interface IP
            iface_ip = tunnel_config.interface_ip.split('/')[0]
            parts = iface_ip.split('.')
            # Guess peer: if we are .1, peer is .2 and vice versa
            last = int(parts[3])
            parts[3] = str(last + 1 if last % 2 == 1 else last - 1)
            l2tp_peer_ip = '.'.join(parts)

        steps.append(f"WireGuard local IP: {wg_ip}")
        steps.append(f"WireGuard endpoint (L2TP peer): {l2tp_peer_ip}:{WG_LISTEN_PORT}")

        # Write wg-quick config file
        ok, msg = self._write_wg_config(
            private_key=keys["private_key"],
            wg_ip=wg_ip,
            peer_public_key=peer_public_key,
            endpoint=f"{l2tp_peer_ip}:{WG_LISTEN_PORT}",
        )
        if not ok:
            return False, f"Failed to write WireGuard config: {msg}"
        steps.append("WireGuard config written")

        # Tear down existing interface if present (idempotent)
        self._teardown_interface()

        # Bring up WireGuard interface using wg-quick
        ok, out, err = _run(f"wg-quick up {WG_CONF_FILE}")
        if not ok:
            # wg-quick may fail if interface already exists, try manual approach
            ok2, msg2 = self._manual_setup(
                keys["private_key"], wg_ip, peer_public_key,
                f"{l2tp_peer_ip}:{WG_LISTEN_PORT}"
            )
            if not ok2:
                return False, f"Failed to bring up WireGuard: {err}\nManual fallback also failed: {msg2}"
            steps.append("WireGuard interface created (manual fallback)")
        else:
            steps.append("WireGuard interface is UP")

        # Enable BBR congestion control
        ok, msg = self.enable_bbr()
        steps.append(f"BBR: {msg}")

        # Install systemd service for persistence
        ok, msg = self._install_systemd_service()
        if ok:
            steps.append("Systemd service installed for persistence")
        else:
            steps.append(f"Warning: Could not install systemd service: {msg}")

        # Update tunnel config
        tunnel_config.wireguard_enabled = True
        tunnel_config.wireguard_ip = wg_ip
        tunnel_config.wireguard_peer_public_key = peer_public_key
        tunnel_config.wireguard_side = side

        steps.append(f"\n✓ WireGuard encryption layer enabled!")
        return True, "\n".join(steps)

    def disable(self, tunnel_config=None) -> Tuple[bool, str]:
        """
        Disable WireGuard encryption layer.

        Args:
            tunnel_config: TunnelConfig to update (optional)

        Returns:
            (success, message)
        """
        steps = []

        # Tear down interface
        self._teardown_interface()
        steps.append("WireGuard interface removed")

        # Stop and disable systemd service
        _run("systemctl stop vortexl2-wireguard.service")
        _run("systemctl disable vortexl2-wireguard.service")
        steps.append("Systemd service stopped")

        # Update tunnel config if provided
        if tunnel_config:
            tunnel_config.wireguard_enabled = False
            steps.append("Tunnel config updated")

        steps.append("✓ WireGuard encryption layer disabled")
        return True, "\n".join(steps)

    def _teardown_interface(self) -> None:
        """Tear down WireGuard interface if it exists (idempotent)."""
        # Try wg-quick down first
        _run(f"wg-quick down {WG_CONF_FILE}")
        # Fallback: delete interface directly
        _run(f"ip link delete {WG_INTERFACE}")

    def _manual_setup(self, private_key: str, wg_ip: str,
                      peer_public_key: str, endpoint: str) -> Tuple[bool, str]:
        """Manual WireGuard setup without wg-quick as fallback."""
        steps = []

        # Create interface
        ok, _, err = _run(f"ip link add dev {WG_INTERFACE} type wireguard")
        if not ok and "File exists" not in err:
            return False, f"Failed to create interface: {err}"

        # Write private key to temp file for wg setconf
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
            f.write(private_key)
            privkey_file = f.name
        os.chmod(privkey_file, 0o600)

        try:
            # Set private key and listen port
            ok, _, err = _run(
                f"wg set {WG_INTERFACE} listen-port {WG_LISTEN_PORT} "
                f"private-key {privkey_file} "
                f"peer {peer_public_key} "
                f"endpoint {endpoint} "
                f"allowed-ips 10.8.0.0/24 "
                f"persistent-keepalive 25"
            )
            if not ok:
                return False, f"Failed to configure WireGuard: {err}"
        finally:
            os.unlink(privkey_file)

        # Assign IP address
        ok, _, err = _run(f"ip addr add {wg_ip} dev {WG_INTERFACE}")
        if not ok and "File exists" not in err:
            return False, f"Failed to assign IP: {err}"

        # Set MTU
        ok, _, err = _run(f"ip link set dev {WG_INTERFACE} mtu {WG_MTU}")
        if not ok:
            steps.append(f"Warning: Could not set MTU: {err}")

        # Bring up interface
        ok, _, err = _run(f"ip link set dev {WG_INTERFACE} up")
        if not ok:
            return False, f"Failed to bring up interface: {err}"

        return True, "Manual setup complete"

    def _write_wg_config(self, private_key: str, wg_ip: str,
                         peer_public_key: str, endpoint: str) -> Tuple[bool, str]:
        """Write wg-quick compatible configuration file."""
        WG_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        config = f"""# VortexL2 WireGuard Encryption Layer
# Auto-generated - do not edit manually

[Interface]
PrivateKey = {private_key}
Address = {wg_ip}
ListenPort = {WG_LISTEN_PORT}
MTU = {WG_MTU}

[Peer]
PublicKey = {peer_public_key}
Endpoint = {endpoint}
AllowedIPs = 10.8.0.0/24
PersistentKeepalive = 25
"""
        try:
            WG_CONF_FILE.write_text(config)
            os.chmod(str(WG_CONF_FILE), 0o600)
            return True, "Config written"
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # BBR congestion control
    # ------------------------------------------------------------------

    @staticmethod
    def enable_bbr() -> Tuple[bool, str]:
        """
        Enable Google BBR congestion control system-wide.
        Persisted via /etc/sysctl.d/99-vortexl2-bbr.conf.
        Idempotent: safe to run multiple times.
        """
        # Check if BBR is already active
        ok, current, _ = _run("sysctl net.ipv4.tcp_congestion_control")
        if ok and "bbr" in current:
            return True, "BBR already enabled"

        # Check if BBR module is available
        _run("modprobe tcp_bbr")

        # Apply sysctl settings
        sysctl_content = (
            "# VortexL2 BBR congestion control\n"
            "net.core.default_qdisc = fq\n"
            "net.ipv4.tcp_congestion_control = bbr\n"
        )

        try:
            BBR_SYSCTL_FILE.parent.mkdir(parents=True, exist_ok=True)
            BBR_SYSCTL_FILE.write_text(sysctl_content)
        except Exception as e:
            return False, f"Failed to write sysctl config: {e}"

        # Apply immediately
        _run("sysctl -w net.core.default_qdisc=fq")
        ok, _, err = _run("sysctl -w net.ipv4.tcp_congestion_control=bbr")
        if not ok:
            return False, f"Failed to enable BBR: {err}"

        return True, "BBR congestion control enabled and persisted"

    # ------------------------------------------------------------------
    # Systemd service for persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _install_systemd_service() -> Tuple[bool, str]:
        """Install systemd service to persist WireGuard across reboots."""
        service_content = f"""[Unit]
Description=VortexL2 WireGuard Encryption Layer
After=network-online.target vortexl2-tunnel.service
Wants=network-online.target
Requires=vortexl2-tunnel.service
Documentation=https://github.com/iliya-Developer/VortexL2

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/wg-quick up {WG_CONF_FILE}
ExecStop=/usr/bin/wg-quick down {WG_CONF_FILE}
ExecReload=/usr/bin/wg-quick down {WG_CONF_FILE} ; /usr/bin/wg-quick up {WG_CONF_FILE}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        try:
            WG_SYSTEMD_FILE.write_text(service_content)
            _run("systemctl daemon-reload")
            _run("systemctl enable vortexl2-wireguard.service")
            return True, "Service installed and enabled"
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @staticmethod
    def is_interface_up() -> bool:
        """Check if wg_vortex interface exists and is up."""
        ok, out, _ = _run(f"ip link show {WG_INTERFACE}")
        return ok and "UP" in out

    @staticmethod
    def get_status() -> Dict:
        """
        Get comprehensive WireGuard status.

        Returns dict with keys:
            installed, interface_up, public_key, listen_port,
            peer_public_key, peer_endpoint, latest_handshake,
            transfer_rx, transfer_tx, wg_ip
        """
        status = {
            "installed": False,
            "interface_up": False,
            "public_key": None,
            "listen_port": None,
            "peer_public_key": None,
            "peer_endpoint": None,
            "latest_handshake": None,
            "transfer_rx": "0 B",
            "transfer_tx": "0 B",
            "wg_ip": None,
            "bbr_enabled": False,
        }

        # Check if installed
        ok, _, _ = _run("which wg")
        status["installed"] = ok

        if not ok:
            return status

        # Read public key from file
        if WG_PUBLIC_KEY_FILE.exists():
            status["public_key"] = WG_PUBLIC_KEY_FILE.read_text().strip()

        # Check interface
        ok, out, _ = _run(f"ip link show {WG_INTERFACE}")
        status["interface_up"] = ok and "UP" in out

        # Get interface IP
        ok, out, _ = _run(f"ip -4 addr show {WG_INTERFACE}")
        if ok and out:
            import re
            match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+/\d+)', out)
            if match:
                status["wg_ip"] = match.group(1)

        # Get WireGuard-specific status
        ok, out, _ = _run(f"wg show {WG_INTERFACE}")
        if ok and out:
            for line in out.split('\n'):
                line = line.strip()
                if line.startswith("public key:"):
                    status["public_key"] = line.split(":", 1)[1].strip()
                elif line.startswith("listening port:"):
                    status["listen_port"] = line.split(":", 1)[1].strip()
                elif line.startswith("peer:"):
                    status["peer_public_key"] = line.split(":", 1)[1].strip()
                elif line.startswith("endpoint:"):
                    status["peer_endpoint"] = line.split(":", 1)[1].strip()
                elif line.startswith("latest handshake:"):
                    status["latest_handshake"] = line.split(":", 1)[1].strip()
                elif line.startswith("transfer:"):
                    transfer = line.split(":", 1)[1].strip()
                    parts = transfer.split(",")
                    if len(parts) >= 2:
                        status["transfer_rx"] = parts[0].strip().replace("received", "").strip()
                        status["transfer_tx"] = parts[1].strip().replace("sent", "").strip()

        # Check BBR
        ok, out, _ = _run("sysctl net.ipv4.tcp_congestion_control")
        status["bbr_enabled"] = ok and "bbr" in out

        return status

    # ------------------------------------------------------------------
    # L2TP MTU adjustment
    # ------------------------------------------------------------------

    @staticmethod
    def update_l2tp_mtu(interface_name: str, mtu: int = L2TP_MTU_WITH_WG) -> Tuple[bool, str]:
        """Update L2TP interface MTU for WireGuard compatibility."""
        ok, _, err = _run(f"ip link set dev {interface_name} mtu {mtu}")
        if not ok:
            return False, f"Failed to set L2TP MTU to {mtu}: {err}"
        return True, f"L2TP MTU set to {mtu}"
