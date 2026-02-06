"""
VortexL2 Socat Port Forwarding Manager

Manages simple TCP port forwarding using socat.
Each port gets its own socat process.
Compatible with HAProxyManager interface.
"""

import subprocess
import re
import asyncio
from typing import List, Dict, Tuple, Optional
from vortexl2.config import ConfigManager


def run_command(cmd: str) -> Tuple[bool, str, str]:
    """Execute a shell command and return success, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


class SocatManager:
    """Manages socat-based port forwarding."""
    
    def __init__(self, config=None):
        """
        Initialize Socat manager.
        
        Args:
            config: Tunnel configuration object (optional)
        """
        self.config = config
    
    def check_socat_installed(self) -> bool:
        """Check if socat is installed."""
        success, _, _ = run_command("which socat")
        return success
        
    def _is_port_listening(self, port: int) -> bool:
        """Check if a port is listening (helper)."""
        cmd = f"netstat -tlnp 2>/dev/null | grep -E ':{port}\\b'"
        success, _, _ = run_command(cmd)
        return success

    def _get_port_process(self, port: int) -> Optional[str]:
        """Get process using the port."""
        cmd = f"lsof -i :{port} -t 2>/dev/null | head -1"
        success, stdout, _ = run_command(cmd)
        if success and stdout.strip():
            pid = stdout.strip()
            # check if it is socat
            ps_cmd = f"ps -p {pid} -o comm="
            _, ps_out, _ = run_command(ps_cmd)
            proc_name = ps_out.strip()
            return f"{proc_name} (PID: {pid})"
        return None

    def start_forward(self, local_port: int, remote_ip: str, remote_port: int) -> Tuple[bool, str]:
        """Start socat forward for a single port."""
        if not self.check_socat_installed():
            return False, "socat is not installed. Install with: apt-get install socat"
        
        # Check if port is already in use
        if self._is_port_listening(local_port):
            proc = self._get_port_process(local_port)
            return False, f"Port {local_port} is already in use by: {proc or 'unknown process'}"
        
        # Build socat command
        cmd = f"nohup socat TCP-LISTEN:{local_port},fork,reuseaddr TCP:{remote_ip}:{remote_port} >/dev/null 2>&1 &"
        
        success, stdout, stderr = run_command(cmd)
        if not success:
            return False, f"Failed to start socat: {stderr}"
        
        # Verify it started
        import time
        time.sleep(0.5)
        if self._is_port_listening(local_port):
            return True, f"Socat forward started: {local_port} → {remote_ip}:{remote_port}"
        else:
            return False, "Socat process did not start successfully (check logs)"
    
    def stop_forward(self, local_port: int) -> Tuple[bool, str]:
        """Stop socat forward for a specific port."""
        if not self._is_port_listening(local_port):
            return True, f"Port {local_port} is not being forwarded"
        
        # Kill socat process listening on this port
        # Using pkill with full command matching carefully
        cmd = f"pkill -f 'socat.*TCP-LISTEN:{local_port}[^0-9]'"
        run_command(cmd)
        
        # Verify it stopped
        import time
        time.sleep(0.5)
        if not self._is_port_listening(local_port):
            return True, f"Stopped socat forward on port {local_port}"
        else:
            return False, f"Failed to stop socat on port {local_port}"

    # -- HAProxyManager Interface Compatibility --

    def create_forward(self, port: int) -> Tuple[bool, str]:
        """Add a port forward (Interface Compatibility)."""
        if not self.config:
            return False, "No tunnel configuration provided"
            
        if port in self.config.forwarded_ports:
            return False, f"Port {port} already in forwarded list"

        remote_ip = self.config.remote_forward_ip
        if not remote_ip:
             return False, "Remote forward IP not configured for this tunnel"

        # Try to start socat first
        success, msg = self.start_forward(port, remote_ip, port)
        if not success:
            return False, msg
            
        # If successful, add to config
        self.config.add_port(port)
        return True, f"Port forward for {port} started (socat)"

    def remove_forward(self, port: int) -> Tuple[bool, str]:
        """Remove a port forward (Interface Compatibility)."""
        if not self.config:
             return False, "No tunnel configuration provided"
             
        if port not in self.config.forwarded_ports:
            return False, f"Port {port} is not in forwarded list"
            
        # Stop socat
        success, msg = self.stop_forward(port)
        if not success:
            return False, msg
            
        # Remove from config
        self.config.remove_port(port)
        return True, f"Port forward {port} removed"

    def add_multiple_forwards(self, ports_str: str) -> Tuple[bool, str]:
        """Add multiple forwards."""
        ports = []
        try:
            for part in ports_str.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    ports.extend(range(start, end + 1))
                else:
                    ports.append(int(part))
        except ValueError:
            return False, "Invalid port format"
            
        results = []
        for port in ports:
            success, msg = self.create_forward(port)
            results.append(msg)
            
        return True, "\n".join(results)

    def remove_multiple_forwards(self, ports_str: str) -> Tuple[bool, str]:
        """Remove multiple forwards."""
        ports = []
        try:
             for part in ports_str.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    ports.extend(range(start, end + 1))
                else:
                    ports.append(int(part))
        except ValueError:
            return False, "Invalid port format"
            
        results = []
        for port in ports:
            if port in self.config.forwarded_ports:
                success, msg = self.remove_forward(port)
                results.append(msg)
                
        return True, "\n".join(results)

    def list_forwards(self) -> List[Dict]:
        """List all configured port forwards (Interface Compatibility)."""
        forwards = []
        
        # Use ConfigManager if self.config is not set, or just use self.config
        cm = ConfigManager()
        tunnels = cm.get_all_tunnels()
        
        for tunnel in tunnels:
            remote_ip = getattr(tunnel, 'remote_forward_ip', None)
            if not remote_ip:
                continue
            
            for port in tunnel.forwarded_ports:
                active = self._is_port_listening(port)
                proc = self._get_port_process(port) if active else None
                
                # Check directly if socat is the process
                is_socat = False
                if proc and "socat" in proc:
                    is_socat = True
                
                status_str = "Active (Socat)" if is_socat and active else ("Active (Other)" if active else "Stopped")
                
                forwards.append({
                    "port": port,
                    "tunnel": tunnel.name,
                    "remote": f"{remote_ip}:{port}",
                    "active": active,
                    "process": proc,
                    "status_str": status_str, # Extra info
                    "active_sessions": 0, # Placeholder
                    "stats": {} # Placeholder
                })
        return forwards

    def validate_and_reload(self) -> Tuple[bool, str]:
        """Validate configuration (No-op in Socat)."""
        return True, "Socat config valid (managed per process)"
        
    async def start_all_forwards(self) -> Tuple[bool, str]:
        """Start all configured forwards (Async for compatibility)."""
        cm = ConfigManager()
        tunnels = cm.get_all_tunnels()
        count = 0
        errors = []
        
        for tunnel in tunnels:
            remote_ip = getattr(tunnel, 'remote_forward_ip', None)
            if not remote_ip:
                continue
                
            for port in tunnel.forwarded_ports:
                success, msg = self.start_forward(port, remote_ip, port)
                if success:
                    count += 1
                else:
                    errors.append(f"{port}: {msg}")
        
        if errors:
            return False, f"Started {count} forwards, but errors occurred:\n" + "\n".join(errors)
        return True, f"Started {count} socat forwards"
        
    async def stop_all_forwards(self) -> Tuple[bool, str]:
        """Stop all socat forwards (Async wrapper)."""
        # Kill all socat processes
        cmd = "pkill -f 'socat.*TCP-LISTEN'"
        run_command(cmd)
        
        import time
        time.sleep(0.5)
        
        # Verify
        remaining = []
        # Re-check via listing
        # Simple check via pgrep
        success, stdout, _ = run_command("pgrep -f 'socat.*TCP-LISTEN'")
        if success and stdout.strip():
             return False, "Some socat processes failed to stop"
             
        return True, "All socat forwards stopped"


    async def restart_all_forwards(self) -> Tuple[bool, str]:
        """Restart all configured port forwards."""
        await self.stop_all_forwards()
        return await self.start_all_forwards()


def stop_all_socat() -> Tuple[bool, str]:
    """Convenience function to stop all socat forwards."""
    # Run async function synchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    manager = SocatManager()
    return loop.run_until_complete(manager.stop_all_forwards())

