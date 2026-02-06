"""
VortexL2 Port Forward Management

Uses HAProxy for high-performance production-grade port forwarding.
HAProxy must be manually enabled by user before it runs.
"""

from __future__ import annotations

from .config import GlobalConfig
from .haproxy_manager import HAProxyManager


def get_forward_manager(config=None):
    """
    Get forward manager based on current mode.
    
    Returns:
        HAProxyManager if forward_mode is 'haproxy',
        SocatManager if forward_mode is 'socat',
        None otherwise.
    """
    global_config = GlobalConfig()
    mode = global_config.forward_mode
    
    if mode == "haproxy":
        return HAProxyManager(config)
    elif mode == "socat":
        from .socat_manager import SocatManager
        return SocatManager(config)
    return None


def get_forward_mode() -> str:
    """Get current forward mode (none or haproxy)."""
    return GlobalConfig().forward_mode


def set_forward_mode(mode: str) -> None:
    """Set forward mode (none or haproxy)."""
    GlobalConfig().forward_mode = mode


# For backward compatibility
ForwardManager = HAProxyManager
