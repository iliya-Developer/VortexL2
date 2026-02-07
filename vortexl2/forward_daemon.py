#!/usr/bin/env python3
"""
VortexL2 Forward Daemon

Manages HAProxy-based port forwarding based on global config.
HAProxy is NOT auto-started - user must enable forward mode first.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vortexl2.config import ConfigManager, GlobalConfig
from vortexl2.forward import get_forward_manager, get_forward_mode


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vortexl2/forward-daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ForwardDaemon:
    """Manages HAProxy-based port forwarding."""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.forward_manager = None
        self.running = False
    
    async def start(self):
        """Start the forward daemon."""
        logger.info("Starting VortexL2 Forward Daemon")
        
        # Get forward mode
        mode = get_forward_mode()
        logger.info(f"Forward mode: {mode}")

        # Log WireGuard status
        try:
            from vortexl2.wireguard_manager import WireGuardManager
            if WireGuardManager.is_interface_up():
                logger.info("WireGuard encryption layer: ACTIVE (traffic routed through wg_vortex)")
            else:
                logger.info("WireGuard encryption layer: INACTIVE (direct L2TP routing)")
        except Exception:
            pass
        
        if mode == "none":
            logger.info("Port forwarding is DISABLED. Use 'sudo vortexl2' to enable HAProxy mode.")
            # Stop both HAProxy and any socat services
            subprocess.run("systemctl stop haproxy", shell=True, capture_output=True)
            subprocess.run("pkill -f 'socat.*TCP-LISTEN'", shell=True, capture_output=True)
            self.running = True
            # Just wait - don't start any forwarding
            try:
                while self.running:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in forward daemon: {e}")
            return
        
        # Handle specific modes
        if mode == "haproxy":
            logger.info("Starting HAProxy-based port forwarding")
            # Stop any socat processes first to free ports
            subprocess.run("pkill -f 'socat.*TCP-LISTEN'", shell=True, capture_output=True)
            # Ensure HAProxy service is running
            result = subprocess.run(
                "systemctl start haproxy",
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                logger.warning(f"Could not start HAProxy: {result.stderr}")
        elif mode == "socat":
            logger.info("Starting Socat-based port forwarding")
            # Stop HAProxy first to free ports
            logger.info("Stopping HAProxy to free ports for Socat...")
            subprocess.run("systemctl stop haproxy", shell=True, capture_output=True)
            
        self.running = True
        
        # Get forward manager
        self.forward_manager = get_forward_manager(None)
        
        if not self.forward_manager:
            logger.error("Failed to get HAProxy manager")
            return
        
        # Start all forwards
        logger.info(f"Starting {mode} forwards for all configured tunnels")
        success, msg = await self.forward_manager.start_all_forwards()
        if not success:
            logger.error(f"Failed to start port forwards: {msg}")
        else:
            logger.info(msg)
        
        logger.info("Forward Daemon started successfully")
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in forward daemon: {e}")
    
    async def stop(self):
        """Stop the forward daemon."""
        logger.info("Stopping VortexL2 Forward Daemon")
        self.running = False
        
        if self.forward_manager:
            logger.info("Stopping active forwards")
            await self.forward_manager.stop_all_forwards()
        
        logger.info("Forward Daemon stopped")


async def main():
    """Main entry point."""
    daemon = ForwardDaemon()
    
    # Setup signal handlers
    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(daemon.stop())
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        await daemon.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
