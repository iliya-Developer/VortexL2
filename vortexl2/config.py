"""
VortexL2 Configuration Management

Handles loading/saving configuration from /etc/vortexl2/config.yaml
with secure file permissions.
"""

import os
import uuid
import socket
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any


CONFIG_DIR = Path("/etc/vortexl2")
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class Config:
    """Configuration manager for VortexL2."""
    
    # Default values
    DEFAULTS = {
        "version": "1.0.0",
        "role": None,  # "IRAN" or "KHAREJ"
        "ip_iran": None,
        "ip_kharej": None,
        "iran_iface_ip": "10.30.30.1/30",
        "remote_forward_ip": "10.30.30.2",
        "forwarded_ports": [],
    }
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load configuration from file or create defaults."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception:
                self._config = {}
        
        # Apply defaults for missing keys
        for key, default in self.DEFAULTS.items():
            if key not in self._config:
                self._config[key] = default

        # Migrate old "OUTSIDE" role to "KHAREJ"
        if self._config.get("role") == "OUTSIDE":
            self._config["role"] = "KHAREJ"
            self._save()

    
    def _save(self) -> None:
        """Save configuration to file with secure permissions."""
        # Create config directory if not exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Write config
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
        
        # Set secure permissions (owner read/write only)
        os.chmod(CONFIG_FILE, 0o600)
    
    def save(self) -> None:
        """Public method to save configuration."""
        self._save()
    
    @property
    def role(self) -> Optional[str]:
        return self._config.get("role")
    
    @role.setter
    def role(self, value: str) -> None:
        if value not in ("IRAN", "KHAREJ", None):
            raise ValueError("Role must be 'IRAN' or 'KHAREJ'")
        self._config["role"]  = value
        self._save()
    
    @property
    def ip_iran(self) -> Optional[str]:
        return self._config.get("ip_iran")
    
    @ip_iran.setter
    def ip_iran(self, value: str) -> None:
        self._config["ip_iran"] = value
        self._save()
    
    @property
    def ip_kharej(self) -> Optional[str]:
        return self._config.get("ip_kharej")
    
    @ip_kharej.setter
    def ip_kharej(self, value: str) -> None:
        self._config["ip_kharej"] = value
        self._save()
    
    @property
    def iran_iface_ip(self) -> str:
        return self._config.get("iran_iface_ip", "10.30.30.1/30")
    
    @iran_iface_ip.setter
    def iran_iface_ip(self, value: str) -> None:
        self._config["iran_iface_ip"] = value
        self._save()
    
    @property
    def remote_forward_ip(self) -> str:
        return self._config.get("remote_forward_ip", "10.30.30.2")
    
    @remote_forward_ip.setter
    def remote_forward_ip(self, value: str) -> None:
        self._config["remote_forward_ip"] = value
        self._save()
    
    @property
    def forwarded_ports(self) -> List[int]:
        return self._config.get("forwarded_ports", [])
    
    @forwarded_ports.setter
    def forwarded_ports(self, value: List[int]) -> None:
        self._config["forwarded_ports"] = value
        self._save()
    
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
        return bool(
            self.role and 
            self.ip_iran and 
            self.ip_kharej
        )
    
    def get_local_ip(self) -> Optional[str]:
        """Get local IP based on role."""
        if self.role == "IRAN":
            return self.ip_iran
        elif self.role == "KHAREJ":
            return self.ip_kharej
        return None
    
    def get_remote_ip(self) -> Optional[str]:
        """Get remote IP based on role."""
        if self.role == "IRAN":
            return self.ip_kharej
        elif self.role == "KHAREJ":
            return self.ip_iran
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()
