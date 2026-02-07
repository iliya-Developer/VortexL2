"""
VortexL2 Configuration Management

Handles loading/saving multiple tunnel configurations from /etc/vortexl2/tunnels/
Each tunnel has its own YAML config file.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any


CONFIG_DIR = Path("/etc/vortexl2")
TUNNELS_DIR = CONFIG_DIR / "tunnels"
GLOBAL_CONFIG_FILE = CONFIG_DIR / "config.yaml"


class GlobalConfig:
    """Global configuration for VortexL2 (forward mode, etc.)."""
    
    VALID_FORWARD_MODES = ["none", "haproxy", "socat"]
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load global configuration from file."""
        if GLOBAL_CONFIG_FILE.exists():
            try:
                with open(GLOBAL_CONFIG_FILE, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception:
                self._config = {}
    
    def _save(self) -> None:
        """Save global configuration to file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(GLOBAL_CONFIG_FILE, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
        os.chmod(GLOBAL_CONFIG_FILE, 0o600)
    
    @property
    def forward_mode(self) -> str:
        """Get forwarding mode: 'none' or 'haproxy'."""
        mode = self._config.get("forward_mode", "none")
        if mode not in self.VALID_FORWARD_MODES:
            return "none"
        return mode
    
    @forward_mode.setter
    def forward_mode(self, value: str) -> None:
        """Set forwarding mode."""
        if value not in self.VALID_FORWARD_MODES:
            raise ValueError(f"Invalid forward mode: {value}. Must be one of {self.VALID_FORWARD_MODES}")
        self._config["forward_mode"] = value
        self._save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()


class TunnelConfig:
    """Configuration for a single tunnel."""
    
    # Default values for new tunnels
    DEFAULTS = {
        "name": "tunnel1",
        "local_ip": None,
        "remote_ip": None,
        "interface_ip": "10.30.30.1/30",
        "remote_forward_ip": "10.30.30.2",
        "tunnel_id": 1000,
        "peer_tunnel_id": 2000,
        "session_id": 10,
        "peer_session_id": 20,
        "interface_index": 0,
        "forwarded_ports": [],
        "encap_type": "ip",      # "ip" or "udp"
        "udp_port": 55555,       # Only used when encap_type == "udp"
        "wireguard_enabled": False,
        "wireguard_ip": None,
        "wireguard_peer_public_key": None,
        "wireguard_side": None,   # "IRAN" or "KHAREJ"
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
        
        # Apply defaults for missing keys
        for key, default in self.DEFAULTS.items():
            if key not in self._config:
                self._config[key] = default
        
        # Ensure name matches
        self._config["name"] = name
    
    def _load(self) -> None:
        """Load configuration from file."""
        if self._file_path.exists():
            try:
                with open(self._file_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception:
                self._config = {}
    
    def _save(self) -> None:
        """Save configuration to file if auto_save is enabled."""
        if not self._auto_save:
            return
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(self._file_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
        
        os.chmod(self._file_path, 0o600)
    
    def save(self) -> None:
        """Public method to force save configuration (ignores auto_save)."""
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(self._file_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
        
        os.chmod(self._file_path, 0o600)
        self._auto_save = True  # Enable auto_save after manual save
    
    def delete(self) -> bool:
        """Delete this tunnel's config file."""
        if self._file_path.exists():
            self._file_path.unlink()
            return True
        return False
    
    @property
    def name(self) -> str:
        return self._config.get("name", self._name)
    
    @name.setter
    def name(self, value: str) -> None:
        self._config["name"] = value
        self._save()
    
    @property
    def local_ip(self) -> Optional[str]:
        return self._config.get("local_ip")
    
    @local_ip.setter
    def local_ip(self, value: str) -> None:
        self._config["local_ip"] = value
        self._save()
    
    @property
    def remote_ip(self) -> Optional[str]:
        return self._config.get("remote_ip")
    
    @remote_ip.setter
    def remote_ip(self, value: str) -> None:
        self._config["remote_ip"] = value
        self._save()
    
    @property
    def interface_ip(self) -> str:
        return self._config.get("interface_ip", "10.30.30.1/24")
    
    @interface_ip.setter
    def interface_ip(self, value: str) -> None:
        self._config["interface_ip"] = value
        self._save()
    
    @property
    def remote_forward_ip(self) -> str:
        return self._config.get("remote_forward_ip", "10.30.30.2")
    
    @remote_forward_ip.setter
    def remote_forward_ip(self, value: str) -> None:
        self._config["remote_forward_ip"] = value
        self._save()
    
    @property
    def tunnel_id(self) -> int:
        return self._config.get("tunnel_id", 1000)
    
    @tunnel_id.setter
    def tunnel_id(self, value: int) -> None:
        self._config["tunnel_id"] = value
        self._save()
    
    @property
    def peer_tunnel_id(self) -> int:
        return self._config.get("peer_tunnel_id", 2000)
    
    @peer_tunnel_id.setter
    def peer_tunnel_id(self, value: int) -> None:
        self._config["peer_tunnel_id"] = value
        self._save()
    
    @property
    def session_id(self) -> int:
        return self._config.get("session_id", 10)
    
    @session_id.setter
    def session_id(self, value: int) -> None:
        self._config["session_id"] = value
        self._save()
    
    @property
    def peer_session_id(self) -> int:
        return self._config.get("peer_session_id", 20)
    
    @peer_session_id.setter
    def peer_session_id(self, value: int) -> None:
        self._config["peer_session_id"] = value
        self._save()
    
    @property
    def interface_index(self) -> int:
        return self._config.get("interface_index", 0)
    
    @interface_index.setter
    def interface_index(self, value: int) -> None:
        self._config["interface_index"] = value
        self._save()
    
    @property
    def interface_name(self) -> str:
        """Get the interface name for this tunnel (l2tpeth0, l2tpeth1, etc.)"""
        return f"l2tpeth{self.interface_index}"
    
    @property
    def forwarded_ports(self) -> List[int]:
        return self._config.get("forwarded_ports", [])
    
    @forwarded_ports.setter
    def forwarded_ports(self, value: List[int]) -> None:
        self._config["forwarded_ports"] = value
        self._save()
    
    @property
    def wireguard_enabled(self) -> bool:
        """Get whether WireGuard encryption is enabled."""
        return bool(self._config.get("wireguard_enabled", False))

    @wireguard_enabled.setter
    def wireguard_enabled(self, value: bool) -> None:
        """Set WireGuard enabled state."""
        self._config["wireguard_enabled"] = bool(value)
        self._save()

    @property
    def wireguard_ip(self) -> Optional[str]:
        """Get WireGuard interface IP (e.g. 10.8.0.1/24)."""
        return self._config.get("wireguard_ip")

    @wireguard_ip.setter
    def wireguard_ip(self, value: str) -> None:
        """Set WireGuard interface IP."""
        self._config["wireguard_ip"] = value
        self._save()

    @property
    def wireguard_peer_public_key(self) -> Optional[str]:
        """Get WireGuard peer public key."""
        return self._config.get("wireguard_peer_public_key")

    @wireguard_peer_public_key.setter
    def wireguard_peer_public_key(self, value: str) -> None:
        """Set WireGuard peer public key."""
        self._config["wireguard_peer_public_key"] = value
        self._save()

    @property
    def wireguard_side(self) -> Optional[str]:
        """Get WireGuard side (IRAN or KHAREJ)."""
        return self._config.get("wireguard_side")

    @wireguard_side.setter
    def wireguard_side(self, value: str) -> None:
        """Set WireGuard side."""
        if value not in ("IRAN", "KHAREJ", None):
            raise ValueError("wireguard_side must be 'IRAN', 'KHAREJ', or None")
        self._config["wireguard_side"] = value
        self._save()

    @property
    def wireguard_peer_ip(self) -> Optional[str]:
        """Get the WireGuard peer IP (without CIDR) based on side."""
        if not self.wireguard_enabled or not self.wireguard_side:
            return None
        if self.wireguard_side == "IRAN":
            return "10.8.0.2"
        else:
            return "10.8.0.1"

    @property
    def encap_type(self) -> str:
        """Get encapsulation type: 'ip' or 'udp'."""
        return self._config.get("encap_type", "ip")
    
    @encap_type.setter
    def encap_type(self, value: str) -> None:
        """Set encapsulation type."""
        if value not in ["ip", "udp"]:
            raise ValueError("encap_type must be 'ip' or 'udp'")
        self._config["encap_type"] = value
        self._save()
    
    @property
    def udp_port(self) -> int:
        """Get UDP port (only used for encap udp mode)."""
        return self._config.get("udp_port", 55555)
    
    @udp_port.setter
    def udp_port(self, value: int) -> None:
        """Set UDP port."""
        if not (1 <= value <= 65535):
            raise ValueError("UDP port must be between 1 and 65535")
        self._config["udp_port"] = value
        self._save()
    
    def get_tunnel_ids(self) -> Dict[str, int]:
        """Get all tunnel IDs as a dictionary."""
        return {
            "tunnel_id": self.tunnel_id,
            "peer_tunnel_id": self.peer_tunnel_id,
            "session_id": self.session_id,
            "peer_session_id": self.peer_session_id,
        }
    
    def add_port(self, port: int) -> None:
        """Add a port to forwarded ports list."""
        ports = self.forwarded_ports
        if port not in ports:
            ports.append(port)
            self.forwarded_ports = ports
    
    def remove_port(self, port: int) -> None:
        """Remove a port from forwarded ports list."""
        ports = self.forwarded_ports
        if port in ports:
            ports.remove(port)
            self.forwarded_ports = ports
    
    def is_configured(self) -> bool:
        """Check if basic configuration is complete."""
        return bool(self.local_ip and self.remote_ip)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()


class ConfigManager:
    """Manages multiple tunnel configurations."""
    
    def __init__(self):
        self._ensure_dirs()
    
    def _ensure_dirs(self) -> None:
        """Ensure config directories exist."""
        TUNNELS_DIR.mkdir(parents=True, exist_ok=True)
    
    def list_tunnels(self) -> List[str]:
        """List all configured tunnel names."""
        if not TUNNELS_DIR.exists():
            return []
        
        tunnels = []
        for f in TUNNELS_DIR.glob("*.yaml"):
            tunnels.append(f.stem)  # filename without extension
        return sorted(tunnels)
    
    def get_tunnel(self, name: str) -> Optional[TunnelConfig]:
        """Get a tunnel config by name."""
        file_path = TUNNELS_DIR / f"{name}.yaml"
        if file_path.exists():
            return TunnelConfig(name)
        return None
    
    def get_all_tunnels(self) -> List[TunnelConfig]:
        """Get all tunnel configurations."""
        return [TunnelConfig(name) for name in self.list_tunnels()]
    
    def create_tunnel(self, name: str) -> TunnelConfig:
        """Create a new tunnel config in memory (not saved until explicitly called)."""
        # Find next available interface index
        used_indices = set()
        for tunnel in self.get_all_tunnels():
            used_indices.add(tunnel.interface_index)
        
        # Find first available index
        new_index = 0
        while new_index in used_indices:
            new_index += 1
        
        # Create new tunnel config (auto_save=False means no file created yet)
        tunnel = TunnelConfig(name, auto_save=False)
        tunnel._config["interface_index"] = new_index
        tunnel._config["name"] = name
        
        # Set unique default tunnel IDs based on index
        # This helps avoid ID conflicts between tunnels
        base_tunnel_id = 1000 + (new_index * 100)
        tunnel._config["tunnel_id"] = base_tunnel_id
        tunnel._config["peer_tunnel_id"] = base_tunnel_id + 1000
        tunnel._config["session_id"] = 10 + new_index
        tunnel._config["peer_session_id"] = 20 + new_index
        
        # Don't save here - config file will be created only after successful tunnel setup
        return tunnel
    
    def delete_tunnel(self, name: str) -> bool:
        """Delete a tunnel configuration."""
        tunnel = self.get_tunnel(name)
        if tunnel:
            return tunnel.delete()
        return False
    
    def tunnel_exists(self, name: str) -> bool:
        """Check if a tunnel with this name exists."""
        return (TUNNELS_DIR / f"{name}.yaml").exists()
    
    def get_used_values(self, exclude_tunnel: str = None) -> Dict[str, set]:
        """
        Get all values currently in use by existing tunnels.
        
        Args:
            exclude_tunnel: Tunnel name to exclude from the check (for editing existing tunnel)
        
        Returns:
            Dictionary with sets of used values for each field
        """
        used = {
            "tunnel_ids": set(),
            "peer_tunnel_ids": set(),
            "session_ids": set(),
            "peer_session_ids": set(),
            "interface_ips": set(),
            "local_ips": set(),
            "remote_ips": set(),
        }
        
        for tunnel in self.get_all_tunnels():
            if exclude_tunnel and tunnel.name == exclude_tunnel:
                continue
            
            used["tunnel_ids"].add(tunnel.tunnel_id)
            used["peer_tunnel_ids"].add(tunnel.peer_tunnel_id)
            used["session_ids"].add(tunnel.session_id)
            used["peer_session_ids"].add(tunnel.peer_session_id)
            
            if tunnel.interface_ip:
                # Store without CIDR for comparison
                ip_only = tunnel.interface_ip.split('/')[0]
                used["interface_ips"].add(ip_only)
            
            if tunnel.local_ip:
                used["local_ips"].add(tunnel.local_ip)
            if tunnel.remote_ip:
                used["remote_ips"].add(tunnel.remote_ip)
        
        return used
    
    def is_value_duplicate(self, field: str, value, exclude_tunnel: str = None) -> bool:
        """
        Check if a value is already in use by another tunnel.
        
        Args:
            field: Field name (tunnel_id, session_id, interface_ip, etc.)
            value: Value to check
            exclude_tunnel: Tunnel name to exclude from the check
        
        Returns:
            True if value is duplicate, False otherwise
        """
        used = self.get_used_values(exclude_tunnel)
        
        field_map = {
            "tunnel_id": "tunnel_ids",
            "peer_tunnel_id": "peer_tunnel_ids",
            "session_id": "session_ids",
            "peer_session_id": "peer_session_ids",
            "interface_ip": "interface_ips",
            "local_ip": "local_ips",
            "remote_ip": "remote_ips",
        }
        
        if field not in field_map:
            return False
        
        # For interface_ip, strip CIDR notation
        if field == "interface_ip" and isinstance(value, str):
            value = value.split('/')[0]
        
        return value in used[field_map[field]]

