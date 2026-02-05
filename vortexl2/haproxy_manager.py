"""
VortexL2 HAProxy Port Forward Manager

Uses HAProxy for production-grade port forwarding with excellent performance.
Manages HAProxy configuration dynamically based on tunnel configurations.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import json
import signal
from pathlib import Path
from vortexl2.config import ConfigManager
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

# HAProxy configuration paths
HAPROXY_CONFIG_DIR = Path("/etc/vortexl2/haproxy")
HAPROXY_CONFIG_FILE = HAPROXY_CONFIG_DIR / "vortexl2.cfg"
HAPROXY_STATS_FILE = Path("/var/lib/vortexl2/haproxy-stats")
HAPROXY_SOCKET = Path("/var/run/haproxy.sock")


@dataclass
class ForwardSession:
    """Represents an active port forwarding session (for compatibility)."""
    port: int
    remote_ip: str
    remote_port: int
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    bytes_sent: int = 0
    bytes_received: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return {
            "port": self.port,
            "remote_ip": self.remote_ip,
            "remote_port": self.remote_port,
            "created_at": self.created_at,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
        }


class HAProxyManager:
    """Manages HAProxy for port forwarding."""
    
    def __init__(self, config):
        """
        Initialize HAProxy manager.
        
        Args:
            config: Tunnel configuration object
        """
        # `config` may be either a single TunnelConfig or a ConfigManager
        self.config = config
        self.running = False
        self.stats = {
            "connections": 0,
            "total_bytes_sent": 0,
            "total_bytes_received": 0,
            "errors": 0,
        }
        
        # Ensure directories exist
        HAPROXY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        Path("/var/lib/vortexl2").mkdir(parents=True, exist_ok=True)
        
        # Check if HAProxy is installed
        if not self._check_haproxy_installed():
            logger.error("HAProxy is not installed. Install with: apt-get install haproxy")
            
    def _check_haproxy_installed(self) -> bool:
        """Check if HAProxy is installed and accessible."""
        try:
            result = subprocess.run(
                ["haproxy", "-v"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _generate_haproxy_config(self) -> str:
        """Generate HAProxy configuration file for all tunnels."""
        # Always build configuration from all tunnels on disk to keep HAProxy
        # config in sync with the canonical configs in /etc/vortexl2/tunnels.
        cm = ConfigManager()
        tunnels = cm.get_all_tunnels()

        # Start with global configuration
        config = """# HAProxy configuration for VortexL2
# Auto-generated - do not edit manually

global
    maxconn 10000
    log stdout local0
    log stdout local1 notice
    chroot /var/lib/haproxy
    stats socket /var/run/haproxy.sock mode 660 level admin
    stats timeout 30s
    daemon

defaults
    log     global
    mode    tcp
    option  tcplog
    option  dontlognull
    option  redispatch
    retries 3
    timeout connect 5000
    timeout client  50000
    timeout server  50000

"""
        
        # For each tunnel and port create dedicated frontend+backend
        for tunnel in tunnels:
            remote_ip = getattr(tunnel, 'remote_forward_ip', None)
            tunnel_name = tunnel.name
            if not remote_ip:
                logger.debug(f"Skipping tunnel {tunnel_name}: no remote_forward_ip")
                continue
            if not getattr(tunnel, 'forwarded_ports', None):
                logger.debug(f"Skipping tunnel {tunnel_name}: no forwarded_ports")
                continue

            for port in tunnel.forwarded_ports:
                backend_name = f"{tunnel_name}_backend_{port}"
                frontend_name = f"{tunnel_name}_port_{port}"

                config += f"""backend {backend_name}
    balance roundrobin
    mode tcp
    server remote_host_{port} {remote_ip}:{port} check
    default-server inter 10s fall 3 rise 2

"""

                config += f"""frontend {frontend_name}
    mode tcp
    bind 0.0.0.0:{port}
    default_backend {backend_name}

"""
        
        return config
    
    def _write_config_file(self, config_content: str) -> bool:
        """Write HAProxy configuration to file."""
        try:
            HAPROXY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Write with temp file for atomicity
            temp_file = HAPROXY_CONFIG_FILE.with_suffix('.cfg.tmp')
            with open(temp_file, 'w') as f:
                f.write(config_content)
            
            # Validate configuration
            result = subprocess.run(
                ["haproxy", "-c", "-f", str(temp_file)],
                capture_output=True,
                timeout=10,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"HAProxy config validation failed:\n{result.stderr}")
                temp_file.unlink()
                return False
            
            # Move temp file to actual location
            temp_file.replace(HAPROXY_CONFIG_FILE)
            logger.info(f"Generated HAProxy config: {HAPROXY_CONFIG_FILE}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write HAProxy config: {e}")
            return False
    
    def _reload_haproxy(self) -> bool:
        """Reload HAProxy configuration gracefully."""
        try:
            # Use systemctl if available, otherwise direct command
            result = subprocess.run(
                ["systemctl", "reload", "haproxy"],
                capture_output=True,
                timeout=10
            )
            
            if result.returncode != 0:
                # Try direct reload
                result = subprocess.run(
                    ["haproxy", "-f", str(HAPROXY_CONFIG_FILE), "-p", "/var/run/haproxy.pid", "-sf", "$(cat /var/run/haproxy.pid 2>/dev/null)"],
                    shell=False,
                    capture_output=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    logger.error(f"HAProxy reload failed: {result.stderr.decode()}")
                    return False
            
            logger.info("HAProxy reloaded successfully")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("HAProxy reload timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to reload HAProxy: {e}")
            return False
    
    def create_forward(self, port: int) -> Tuple[bool, str]:
        """Add a port forward."""
        if port in self.config.forwarded_ports:
            return False, f"Port {port} already forwarding"
        
        # Add to config
        self.config.add_port(port)
        
        # Regenerate and reload HAProxy config
        config = self._generate_haproxy_config()
        if not self._write_config_file(config):
            # Rollback
            self.config.remove_port(port)
            return False, f"Failed to update HAProxy config for port {port}"
        
        if not self._reload_haproxy():
            # Rollback
            self.config.remove_port(port)
            return False, f"Failed to reload HAProxy for port {port}"
        
        remote_ip = self.config.remote_forward_ip
        return True, f"Port forward for {port} created (-> {remote_ip}:{port})"
    
    def remove_forward(self, port: int) -> Tuple[bool, str]:
        """Remove a port forward."""
        if port not in self.config.forwarded_ports:
            return False, f"Port {port} not found"
        
        # Remove from config
        self.config.remove_port(port)
        
        # Regenerate and reload HAProxy config
        config = self._generate_haproxy_config()
        if not self._write_config_file(config):
            # Rollback
            self.config.add_port(port)
            return False, f"Failed to update HAProxy config for port {port}"
        
        if not self._reload_haproxy():
            # Rollback
            self.config.add_port(port)
            return False, f"Failed to reload HAProxy for port {port}"
        
        return True, f"Port forward for {port} removed"

    def validate_and_reload(self) -> Tuple[bool, str]:
        """Validate generated HAProxy config and reload HAProxy gracefully.

        Returns (success, message).
        """
        try:
            config = self._generate_haproxy_config()
            if not config:
                return False, "No HAProxy configuration generated (no tunnels or missing data)"

            # Write and validate config
            if not self._write_config_file(config):
                return False, "HAProxy configuration validation failed"

            # Reload HAProxy
            if not self._reload_haproxy():
                return False, "HAProxy reload failed"

            return True, "HAProxy configuration validated and reloaded successfully"
        except Exception as e:
            return False, f"Error during validate_and_reload: {e}"
    
    def add_multiple_forwards(self, ports_str: str) -> Tuple[bool, str]:
        """Add multiple port forwards from comma-separated string."""
        results = []
        ports = [p.strip() for p in ports_str.split(',') if p.strip()]
        
        for port_str in ports:
            try:
                port = int(port_str)
                success, msg = self.create_forward(port)
                results.append(f"Port {port}: {msg}")
            except ValueError:
                results.append(f"Port '{port_str}': Invalid port number")
        
        return True, "\n".join(results)
    
    def remove_multiple_forwards(self, ports_str: str) -> Tuple[bool, str]:
        """Remove multiple port forwards from comma-separated string."""
        results = []
        ports = [p.strip() for p in ports_str.split(',') if p.strip()]
        
        for port_str in ports:
            try:
                port = int(port_str)
                success, msg = self.remove_forward(port)
                results.append(f"Port {port}: {msg}")
            except ValueError:
                results.append(f"Port '{port_str}': Invalid port number")
        
        return True, "\n".join(results)
    
    def list_forwards(self) -> List[Dict]:
        """List all configured port forwards from all tunnels."""
        forwards = []
        
        # Get all tunnels to show all forwards
        cm = ConfigManager()
        tunnels = cm.get_all_tunnels()
        
        for tunnel in tunnels:
            remote_ip = getattr(tunnel, 'remote_forward_ip', None)
            if not remote_ip:
                continue
                
            for port in tunnel.forwarded_ports:
                forwards.append({
                    "port": port,
                    "tunnel": tunnel.name,
                    "remote": f"{remote_ip}:{port}",
                    "running": self._is_port_listening(port),
                    "active_sessions": 0,
                    "stats": {
                        "connections": 0,
                        "total_bytes_sent": 0,
                        "total_bytes_received": 0,
                        "errors": 0,
                    }
                })
        
        return forwards
    
    def _is_port_listening(self, port: int) -> bool:
        """Check if a port is listening."""
        try:
            # Check using ss with multiple patterns
            result = subprocess.run(
                f"ss -tlnp 2>/dev/null | grep -E ':{port}\\b'",
                shell=True,
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return True
            
            # Fallback: check with netstat
            result = subprocess.run(
                f"netstat -tlnp 2>/dev/null | grep -E ':{port}\\b'",
                shell=True,
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def start_all_forwards(self) -> Tuple[bool, str]:
        """Start all configured port forwards from all tunnels."""
        # Get all tunnels from disk regardless of how manager was initialized
        cm = ConfigManager()
        tunnels = cm.get_all_tunnels()
        
        # Check if any tunnels have forwarded ports
        has_forwards = any(t.forwarded_ports for t in tunnels)
        if not has_forwards:
            return True, "No port forwards configured across all tunnels"
        
        # Generate and write configuration
        config = self._generate_haproxy_config()
        if not self._write_config_file(config):
            return False, "Failed to write HAProxy configuration"
        
        # Start/reload HAProxy
        try:
            # First, try to reload if already running
            if Path("/var/run/haproxy.pid").exists():
                logger.info("HAProxy already running, reloading configuration")
                if not self._reload_haproxy():
                    return False, "Failed to reload HAProxy"
            else:
                logger.info("Starting HAProxy service")
                # Start HAProxy with -D flag to daemonize
                result = subprocess.run(
                    ["haproxy", "-f", str(HAPROXY_CONFIG_FILE), "-p", "/var/run/haproxy.pid", "-D"],
                    capture_output=True,
                    timeout=10,
                    text=True
                )
                
                if result.returncode != 0:
                    stderr_msg = result.stderr if result.stderr else "Unknown error"
                    return False, f"Failed to start HAProxy: {stderr_msg}"
                
                logger.info("HAProxy started successfully")
            
            self.running = True
            # Collect all forwarded ports from all tunnels
            all_ports = set()
            for tunnel in tunnels:
                all_ports.update(tunnel.forwarded_ports)
            ports_str = ", ".join(sorted(str(p) for p in all_ports))
            msg = f"HAProxy port forwarding started for ports: {ports_str}" if ports_str else "HAProxy started (no active forwards)"
            logger.info(msg)
            return True, msg
            
        except Exception as e:
            logger.error(f"Exception in start_all_forwards: {e}")
            return False, f"Error starting HAProxy: {e}"
    
    async def stop_all_forwards(self) -> Tuple[bool, str]:
        """Stop all configured port forwards."""
        try:
            result = subprocess.run(
                ["systemctl", "stop", "haproxy"],
                capture_output=True,
                timeout=10
            )
            
            self.running = False
            return True, "HAProxy port forwarding stopped"
            
        except Exception as e:
            return False, f"Error stopping HAProxy: {e}"
    
    async def restart_all_forwards(self) -> Tuple[bool, str]:
        """Restart all configured port forwards."""
        await self.stop_all_forwards()
        await asyncio.sleep(1)
        return await self.start_all_forwards()
    
    def start_in_background(self) -> bool:
        """Start forwarding in background (HAProxy handles this internally)."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def run():
                success, msg = await self.start_all_forwards()
                if not success:
                    logger.error(msg)
                    return False
                
                # Keep running
                while self.running:
                    await asyncio.sleep(1)
                
                return True
            
            loop.run_until_complete(run())
            return True
        except Exception as e:
            logger.error(f"Failed to start background forwarding: {e}")
            return False


# Backward compatibility alias
ForwardManager = HAProxyManager
