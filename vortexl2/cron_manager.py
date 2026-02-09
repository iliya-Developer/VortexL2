#!/usr/bin/env python3
"""
VortexL2 Cron Manager
Manages automatic restart of port forwarding daemon via cron jobs.

IMPORTANT: This only restarts the port forwarding service (vortexl2-forward-daemon),
NOT the tunnel service. Tunnels remain active during port forward restarts.
"""

import subprocess
import os
from typing import Tuple


def get_cron_jobs() -> str:
    """Get current cron jobs for root user."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout
        return ""
    except Exception:
        return ""


def has_vortexl2_cron() -> bool:
    """Check if VortexL2 auto-restart cron job exists."""
    cron_content = get_cron_jobs()
    return "vortexl2-forward-daemon" in cron_content


def add_auto_restart_cron(interval_minutes: int = 60) -> Tuple[bool, str]:
    """
    Add cron job to restart port forwarding daemon periodically.
    
    Args:
        interval_minutes: Restart interval in minutes (default: 60)
    
    Returns:
        (success, message)
    """
    try:
        # Get existing cron jobs
        existing_cron = get_cron_jobs()
        
        # Remove old VortexL2 cron entries if they exist
        lines = [line for line in existing_cron.split('\n') 
                 if 'vortexl2-forward-daemon' not in line and line.strip()]
        
        # Determine cron schedule based on interval
        if interval_minutes == 60:
            schedule = "0 * * * *"  # Every hour at minute 0
            description = "every hour"
        elif interval_minutes == 30:
            schedule = "*/30 * * * *"  # Every 30 minutes
            description = "every 30 minutes"
        elif interval_minutes == 15:
            schedule = "*/15 * * * *"  # Every 15 minutes
            description = "every 15 minutes"
        elif interval_minutes == 5:
            schedule = "*/5 * * * *"  # Every 5 minutes
            description = "every 5 minutes"
        else:
            schedule = f"*/{interval_minutes} * * * *"
            description = f"every {interval_minutes} minutes"
        
        # Add new cron entry (only restarts port forwarding daemon, tunnels stay up)
        new_entry = f"{schedule} systemctl restart vortexl2-forward-daemon >/dev/null 2>&1"
        lines.append(new_entry)
        
        # Write back to crontab
        new_cron = '\n'.join(lines) + '\n'
        
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=new_cron, timeout=5)
        
        if process.returncode == 0:
            return True, f"Auto-restart configured to run {description}"
        else:
            return False, f"Failed to update crontab: {stderr}"
    
    except Exception as e:
        return False, f"Error setting up cron job: {e}"


def remove_auto_restart_cron() -> Tuple[bool, str]:
    """Remove VortexL2 auto-restart cron job."""
    try:
        existing_cron = get_cron_jobs()
        
        if "vortexl2-forward-daemon" not in existing_cron:
            return True, "No auto-restart cron job found (already disabled)"
        
        # Remove VortexL2 cron entries
        lines = [line for line in existing_cron.split('\n') 
                 if 'vortexl2-forward-daemon' not in line and line.strip()]
        
        # Write back to crontab
        new_cron = '\n'.join(lines) + '\n' if lines else ''
        
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=new_cron, timeout=5)
        
        if process.returncode == 0:
            return True, "Auto-restart cron job removed"
        else:
            return False, f"Failed to update crontab: {stderr}"
    
    except Exception as e:
        return False, f"Error removing cron job: {e}"


def get_auto_restart_status() -> Tuple[bool, str]:
    """
    Get status of auto-restart cron job.
    
    Returns:
        (enabled, schedule_description)
    """
    cron_content = get_cron_jobs()
    
    for line in cron_content.split('\n'):
        if 'vortexl2-forward-daemon' in line:
            # Parse schedule
            parts = line.split()
            if len(parts) >= 5:
                minute = parts[0]
                if minute == "0":
                    return True, "Every hour"
                elif minute == "*/30":
                    return True, "Every 30 minutes"
                elif minute == "*/15":
                    return True, "Every 15 minutes"
                elif minute == "*/5":
                    return True, "Every 5 minutes"
                else:
                    return True, f"Custom schedule: {' '.join(parts[:5])}"
    
    return False, "Disabled"


# ============================================
# EasyTier Tunnel Auto-Restart Cron
# ============================================

def has_easytier_cron() -> bool:
    """Check if EasyTier tunnel auto-restart cron job exists."""
    cron_content = get_cron_jobs()
    return "vortexl2-easytier" in cron_content


def add_easytier_cron(interval_minutes: int = 60) -> Tuple[bool, str]:
    """
    Add cron job to restart all EasyTier tunnel services periodically.
    
    Args:
        interval_minutes: Restart interval in minutes (default: 60)
    
    Returns:
        (success, message)
    """
    try:
        existing_cron = get_cron_jobs()
        
        # Remove old EasyTier cron entries if they exist
        lines = [line for line in existing_cron.split('\n') 
                 if 'vortexl2-easytier' not in line and line.strip()]
        
        # Determine cron schedule based on interval
        if interval_minutes == 60:
            schedule = "0 * * * *"
            description = "every hour"
        elif interval_minutes == 30:
            schedule = "*/30 * * * *"
            description = "every 30 minutes"
        elif interval_minutes == 15:
            schedule = "*/15 * * * *"
            description = "every 15 minutes"
        elif interval_minutes == 5:
            schedule = "*/5 * * * *"
            description = "every 5 minutes"
        else:
            schedule = f"*/{interval_minutes} * * * *"
            description = f"every {interval_minutes} minutes"
        
        # Add new cron entry - restart all EasyTier tunnel services
        cmd = "for svc in /etc/systemd/system/vortexl2-easytier-*.service; do [ -f \\\"$svc\\\" ] && systemctl restart $(basename \\\"$svc\\\"); done"
        new_entry = f"{schedule} {cmd} >/dev/null 2>&1"
        lines.append(new_entry)
        
        # Write back to crontab
        new_cron = '\n'.join(lines) + '\n'
        
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=new_cron, timeout=5)
        
        if process.returncode == 0:
            return True, f"EasyTier auto-restart configured to run {description}"
        else:
            return False, f"Failed to update crontab: {stderr}"
    
    except Exception as e:
        return False, f"Error setting up cron job: {e}"


def remove_easytier_cron() -> Tuple[bool, str]:
    """Remove EasyTier tunnel auto-restart cron job."""
    try:
        existing_cron = get_cron_jobs()
        
        if "vortexl2-easytier" not in existing_cron:
            return True, "No EasyTier auto-restart cron job found (already disabled)"
        
        # Remove EasyTier cron entries
        lines = [line for line in existing_cron.split('\n') 
                 if 'vortexl2-easytier' not in line and line.strip()]
        
        # Write back to crontab
        new_cron = '\n'.join(lines) + '\n' if lines else ''
        
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=new_cron, timeout=5)
        
        if process.returncode == 0:
            return True, "EasyTier auto-restart cron job removed"
        else:
            return False, f"Failed to update crontab: {stderr}"
    
    except Exception as e:
        return False, f"Error removing cron job: {e}"


def get_easytier_cron_status() -> Tuple[bool, str]:
    """
    Get status of EasyTier tunnel auto-restart cron job.
    
    Returns:
        (enabled, schedule_description)
    """
    cron_content = get_cron_jobs()
    
    for line in cron_content.split('\n'):
        if 'vortexl2-easytier' in line:
            parts = line.split()
            if len(parts) >= 5:
                minute = parts[0]
                if minute == "0":
                    return True, "Every hour"
                elif minute == "*/30":
                    return True, "Every 30 minutes"
                elif minute == "*/15":
                    return True, "Every 15 minutes"
                elif minute == "*/5":
                    return True, "Every 5 minutes"
                else:
                    return True, f"Custom schedule: {' '.join(parts[:5])}"
    
    return False, "Disabled"
