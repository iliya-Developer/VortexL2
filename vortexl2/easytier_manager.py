"""
VortexL2 EasyTier Tunnel Manager

Manages EasyTier mesh tunnel configuration and operations.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import yaml

logger = logging.getLogger(__name__)

# Paths
EASYTIER_BIN = Path("/usr/local/bin/easytier-core")
EASYTIER_CLI = Path("/usr/local/bin/easytier-cli")
CONFIG_DIR = Path("/etc/vortexl2")
TUNNELS_DIR = CONFIG_DIR / "tunnels"


class EasyTierConfig:
    """Configuration for an EasyTier tunnel."""
    
    DEFAULTS = {
        "name": "tunnel1",
        "tunnel_type": "easytier",
        "local_ip": "10.155.155.1",  # Interface IP
        "peer_ip": None,              # Remote server IP
        "port": 2070,                 # Listen/connect port
        "network_secret": "vortexl2",
        "interface_name": "tun1",
        "hostname": "node1",
        "forwarded_ports": [],
        "remote_forward_ip": None,    # For port forwarding target
    }
    
    def __init__(self, name: str, config_data: Dict[str, Any] = None, auto_save: bool = True):
        self._name = name
        self._config: Dict[str, Any] = {}
        self._file_path = TUNNELS_DIR / f"{name}.yaml"
        self._auto_save = auto_save
        
        if config_data:
            self._config = config_data
        else:
            self._load()
        
        # Apply defaults
        for key, default in self.DEFAULTS.items():
            if key not in self._config:
                self._config[key] = default
        
        self._config["name"] = name
        self._config["tunnel_type"] = "easytier"
    
    def _load(self) -> None:
        if self._file_path.exists():
            try:
                with open(self._file_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception:
                self._config = {}
    
    def _save(self) -> None:
        if not self._auto_save:
            return
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._file_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
        os.chmod(self._file_path, 0o600)
    
    def save(self) -> None:
        """Force save configuration."""
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._file_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
        os.chmod(self._file_path, 0o600)
        self._auto_save = True
    
    def delete(self) -> bool:
        if self._file_path.exists():
            self._file_path.unlink()
            return True
        return False
    
    # Properties
    @property
    def name(self) -> str:
        return self._config.get("name", self._name)
    
    @property
    def local_ip(self) -> str:
        return self._config.get("local_ip", "10.155.155.1")
    
    @local_ip.setter
    def local_ip(self, value: str) -> None:
        self._config["local_ip"] = value
        self._save()
    
    @property
    def peer_ip(self) -> Optional[str]:
        return self._config.get("peer_ip")
    
    @peer_ip.setter
    def peer_ip(self, value: str) -> None:
        self._config["peer_ip"] = value
        self._save()
    
    @property
    def port(self) -> int:
        return self._config.get("port", 2070)
    
    @port.setter
    def port(self, value: int) -> None:
        self._config["port"] = value
        self._save()
    
    @property
    def network_secret(self) -> str:
        return self._config.get("network_secret", "vortexl2")
    
    @network_secret.setter
    def network_secret(self, value: str) -> None:
        self._config["network_secret"] = value
        self._save()
    
    @property
    def interface_name(self) -> str:
        return self._config.get("interface_name", "tun1")
    
    @interface_name.setter
    def interface_name(self, value: str) -> None:
        self._config["interface_name"] = value
        self._save()
    
    @property
    def hostname(self) -> str:
        return self._config.get("hostname", "node1")
    
    @hostname.setter
    def hostname(self, value: str) -> None:
        self._config["hostname"] = value
        self._save()
    
    @property
    def forwarded_ports(self) -> List[int]:
        return self._config.get("forwarded_ports", [])
    
    @forwarded_ports.setter
    def forwarded_ports(self, value: List[int]) -> None:
        self._config["forwarded_ports"] = value
        self._save()
    
    @property
    def remote_forward_ip(self) -> Optional[str]:
        return self._config.get("remote_forward_ip")
    
    @remote_forward_ip.setter
    def remote_forward_ip(self, value: str) -> None:
        self._config["remote_forward_ip"] = value
        self._save()
    
    def add_port(self, port: int) -> None:
        ports = self.forwarded_ports
        if port not in ports:
            ports.append(port)
            self.forwarded_ports = ports
    
    def remove_port(self, port: int) -> None:
        ports = self.forwarded_ports
        if port in ports:
            ports.remove(port)
            self.forwarded_ports = ports
    
    def is_configured(self) -> bool:
        return bool(self.peer_ip)
    
    def to_dict(self) -> Dict[str, Any]:
        return self._config.copy()
    
    def get_command_args(self) -> List[str]:
        """Generate command line arguments for easytier-core."""
        args = [
            str(EASYTIER_BIN),
            "-i", self.local_ip,
            "--hostname", self.hostname,
            "--network-secret", self.network_secret,
            "--default-protocol", "tcp",
            "--listeners", f"tcp://[::]:{self.port}", f"tcp://0.0.0.0:{self.port}",
            "--multi-thread",
            "--dev-name", self.interface_name,
            "--rpc-portal", "127.0.0.1:15888",  # Required for easytier-cli to work
        ]
        
        if self.peer_ip:
            args.extend(["--peers", f"tcp://{self.peer_ip}:{self.port}"])
        
        return args
    
    def get_command_string(self) -> str:
        """Get full command as string."""
        return " ".join(self.get_command_args())


class EasyTierManager:
    """Manages EasyTier tunnel operations."""
    
    def __init__(self, config: EasyTierConfig):
        self.config = config
        self._service_name = f"vortexl2-easytier-{config.name}"
    
    def _run_command(self, cmd: str) -> Tuple[bool, str, str]:
        """Execute shell command."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def check_easytier_installed(self) -> bool:
        """Check if EasyTier binary is installed."""
        return EASYTIER_BIN.exists() and os.access(EASYTIER_BIN, os.X_OK)
    
    def check_tunnel_exists(self) -> bool:
        """Check if tunnel interface exists."""
        success, stdout, _ = self._run_command(f"ip link show {self.config.interface_name}")
        return success
    
    def _create_service_file(self) -> Tuple[bool, str]:
        """Create systemd service file for this tunnel."""
        cmd = self.config.get_command_string()
        
        service_content = f"""[Unit]
Description=VortexL2 EasyTier Tunnel - {self.config.name}
After=network.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={cmd}
Restart=on-failure
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
"""
        try:
            service_path = Path(f"/etc/systemd/system/{self._service_name}.service")
            with open(service_path, 'w') as f:
                f.write(service_content)
            
            self._run_command("systemctl daemon-reload")
            return True, f"Service file created: {self._service_name}"
        except Exception as e:
            return False, f"Failed to create service: {e}"
    
    def start_tunnel(self) -> Tuple[bool, str]:
        """Start the EasyTier tunnel."""
        if not self.check_easytier_installed():
            return False, "EasyTier binary not found at /usr/local/bin/easytier-core"
        
        if not self.config.is_configured():
            return False, "Tunnel not fully configured (missing peer IP)"
        
        # Create/update service file
        success, msg = self._create_service_file()
        if not success:
            return False, msg
        
        # Enable and start service
        self._run_command(f"systemctl enable {self._service_name}")
        success, _, stderr = self._run_command(f"systemctl start {self._service_name}")
        
        if not success:
            return False, f"Failed to start tunnel: {stderr}"
        
        return True, f"EasyTier tunnel '{self.config.name}' started"
    
    def stop_tunnel(self) -> Tuple[bool, str]:
        """Stop the EasyTier tunnel."""
        self._run_command(f"systemctl stop {self._service_name}")
        self._run_command(f"systemctl disable {self._service_name}")
        return True, f"EasyTier tunnel '{self.config.name}' stopped"
    
    def restart_tunnel(self) -> Tuple[bool, str]:
        """Restart the EasyTier tunnel."""
        # Update service file first
        self._create_service_file()
        success, _, stderr = self._run_command(f"systemctl restart {self._service_name}")
        
        if not success:
            return False, f"Failed to restart tunnel: {stderr}"
        
        return True, f"EasyTier tunnel '{self.config.name}' restarted"
    
    def get_status(self) -> Tuple[bool, str]:
        """Get tunnel status."""
        success, stdout, stderr = self._run_command(f"systemctl is-active {self._service_name}")
        is_active = success and "active" in stdout
        
        if is_active:
            return True, "Running"
        else:
            return False, "Stopped"
    
    def get_peer_info(self) -> List[Dict[str, Any]]:
        """Get peer information from easytier-cli peer command.
        
        Returns list of peers with their stats:
        - ipv4: IP address
        - hostname: peer hostname
        - cost: connection cost (Local, p2p, etc.)
        - latency: latency in ms
        - loss: packet loss percentage
        - rx: received bytes
        - tx: transmitted bytes
        - tunnel: tunnel type (tcp, udp, etc.)
        - nat: NAT type
        """
        if not EASYTIER_CLI.exists():
            return []
        
        success, stdout, stderr = self._run_command(f"{EASYTIER_CLI} peer")
        if not success or not stdout:
            return []
        
        peers = []
        lines = stdout.strip().split('\n')
        
        # Parse table with Unicode box-drawing characters
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip header and separator lines (contain ┌ ├ └ ─ or header text)
            if any(c in line for c in '┌├└─┬┴┼'):
                continue
            if 'ipv4' in line.lower() or 'hostname' in line.lower():
                continue
            
            # Data lines start with │
            if not line.startswith('│'):
                continue
            
            # Parse pipe-separated values (using Unicode │)
            parts = [p.strip() for p in line.split('│') if p.strip()]
            
            if len(parts) >= 7:
                try:
                    peer = {
                        'ipv4': parts[0],
                        'hostname': parts[1],
                        'cost': parts[2],
                        'latency': parts[3] if parts[3] != '-' else None,
                        'loss': parts[4] if parts[4] != '-' else None,
                        'rx': parts[5] if parts[5] != '-' else None,
                        'tx': parts[6] if parts[6] != '-' else None,
                        'tunnel': parts[7] if len(parts) > 7 and parts[7] != '-' else None,
                        'nat': parts[8] if len(parts) > 8 else None,
                    }
                    peers.append(peer)
                except (IndexError, ValueError):
                    continue
        
        return peers
    
    def full_setup(self) -> Tuple[bool, str]:
        """Full tunnel setup (create and start)."""
        return self.start_tunnel()
    
    def full_teardown(self) -> Tuple[bool, str]:
        """Full tunnel teardown (stop and remove service)."""
        self.stop_tunnel()
        
        # Remove service file
        service_path = Path(f"/etc/systemd/system/{self._service_name}.service")
        if service_path.exists():
            service_path.unlink()
            self._run_command("systemctl daemon-reload")
        
        return True, f"EasyTier tunnel '{self.config.name}' removed"


class EasyTierConfigManager:
    """Manages multiple EasyTier tunnel configurations."""
    
    def __init__(self):
        self._ensure_dirs()
    
    def _ensure_dirs(self) -> None:
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
    
    def list_tunnels(self) -> List[str]:
        """List all EasyTier tunnel names."""
        if not TUNNELS_DIR.exists():
            return []
        
        tunnels = []
        for f in TUNNELS_DIR.glob("*.yaml"):
            try:
                with open(f, 'r') as file:
                    data = yaml.safe_load(file) or {}
                    if data.get("tunnel_type") == "easytier":
                        tunnels.append(f.stem)
            except Exception:
                pass
        return sorted(tunnels)
    
    def get_tunnel(self, name: str) -> Optional[EasyTierConfig]:
        file_path = TUNNELS_DIR / f"{name}.yaml"
        if file_path.exists():
            return EasyTierConfig(name)
        return None
    
    def get_all_tunnels(self) -> List[EasyTierConfig]:
        return [EasyTierConfig(name) for name in self.list_tunnels()]
    
    def create_tunnel(self, name: str) -> EasyTierConfig:
        """Create new EasyTier tunnel config (not saved yet)."""
        tunnel = EasyTierConfig(name, auto_save=False)
        # Use tunnel name as interface name (Linux allows up to 15 chars)
        iface_name = name[:15] if len(name) > 15 else name
        tunnel._config["interface_name"] = iface_name
        tunnel._config["hostname"] = name
        return tunnel
    
    def delete_tunnel(self, name: str) -> bool:
        tunnel = self.get_tunnel(name)
        if tunnel:
            # Stop tunnel first
            manager = EasyTierManager(tunnel)
            manager.full_teardown()
            return tunnel.delete()
        return False
    
    def tunnel_exists(self, name: str) -> bool:
        return (TUNNELS_DIR / f"{name}.yaml").exists()
