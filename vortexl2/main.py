#!/usr/bin/env python3
"""
VortexL2 - L2TPv3 & EasyTier Tunnel Manager

Main entry point and CLI handler.
"""

import sys
import os
import argparse
import subprocess
import signal

# CRITICAL: Fix sys.path BEFORE any vortexl2 imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vortexl2.haproxy_manager import HAProxyManager
from vortexl2 import __version__
from vortexl2.config import TunnelConfig, ConfigManager, GlobalConfig
from vortexl2.tunnel import TunnelManager
from vortexl2.forward import get_forward_manager, get_forward_mode, set_forward_mode, ForwardManager
from vortexl2 import ui


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n")
    ui.console.print("[yellow]Interrupted. Goodbye![/]")
    sys.exit(0)


def check_root():
    """Check if running as root."""
    if os.geteuid() != 0:
        ui.show_error("VortexL2 must be run as root (use sudo)")
        sys.exit(1)


def get_tunnel_mode() -> str:
    """Get current tunnel mode from global config."""
    global_config = GlobalConfig()
    return global_config.tunnel_mode


def restart_forward_daemon():
    """Restart the forward daemon service to pick up config changes."""
    mode = get_forward_mode()
    
    if mode == "haproxy":
        subprocess.run("systemctl start haproxy", shell=True, capture_output=True)
    
    subprocess.run("systemctl restart vortexl2-forward-daemon", shell=True, capture_output=True)


# ============================================
# L2TPv3 HANDLERS (existing)
# ============================================

def cmd_apply():
    """Apply all tunnel configurations (idempotent)."""
    tunnel_mode = get_tunnel_mode()
    
    if tunnel_mode == "easytier":
        return cmd_apply_easytier()
    
    # L2TPv3 mode
    manager = ConfigManager()
    tunnels = manager.get_all_tunnels()
    
    if not tunnels:
        print("VortexL2: No tunnels configured, skipping")
        return 0
    
    errors = 0
    for config in tunnels:
        if not config.is_configured():
            print(f"VortexL2: Tunnel '{config.name}' not fully configured, skipping")
            continue
        
        tunnel = TunnelManager(config)
        success, msg = tunnel.full_setup()
        print(f"Tunnel '{config.name}': {msg}")
        
        if not success:
            errors += 1
    
    print("VortexL2: Tunnel setup complete.")
    return 1 if errors > 0 else 0


def cmd_apply_easytier():
    """Apply all EasyTier tunnel configurations."""
    from vortexl2.easytier_manager import EasyTierConfigManager, EasyTierManager
    
    manager = EasyTierConfigManager()
    tunnels = manager.get_all_tunnels()
    
    if not tunnels:
        print("VortexL2: No EasyTier tunnels configured, skipping")
        return 0
    
    errors = 0
    for config in tunnels:
        if not config.is_configured():
            print(f"VortexL2: EasyTier tunnel '{config.name}' not fully configured, skipping")
            continue
        
        tunnel_mgr = EasyTierManager(config)
        success, msg = tunnel_mgr.start_tunnel()
        print(f"EasyTier tunnel '{config.name}': {msg}")
        
        if not success:
            errors += 1
    
    print("VortexL2: EasyTier tunnel setup complete.")
    return 1 if errors > 0 else 0


def handle_prerequisites():
    """Handle prerequisites installation."""
    ui.show_banner()
    tunnel_mode = get_tunnel_mode()
    
    ui.show_info("Applying TCP performance optimization...")
    from vortexl2.tcp_optimizer import setup_tcp_optimization
    success, opt_msg = setup_tcp_optimization()
    ui.show_output(opt_msg, "TCP Optimization")
    
    if success:
        ui.show_success("TCP optimization applied successfully")
    else:
        ui.show_warning("TCP optimization partially failed")
    
    if tunnel_mode == "l2tpv3":
        ui.show_info("Installing L2TP prerequisites...")
        tunnel = TunnelManager(TunnelConfig("temp"))
        success, msg = tunnel.install_prerequisites()
        ui.show_output(msg, "Prerequisites Installation")
        
        if success:
            ui.show_success("Prerequisites installed successfully")
        else:
            ui.show_error(msg)
    else:
        ui.show_info("EasyTier mode - L2TP modules not needed")
        ui.show_success("TCP optimization complete")
    
    ui.wait_for_enter()


def handle_create_tunnel(manager: ConfigManager):
    """Handle L2TPv3 tunnel creation."""
    ui.show_banner()
    
    side = ui.prompt_tunnel_side()
    if not side:
        return
    
    name = ui.prompt_tunnel_name()
    if not name:
        return
    
    if manager.tunnel_exists(name):
        ui.show_error(f"Tunnel '{name}' already exists")
        ui.wait_for_enter()
        return
    
    config = manager.create_tunnel(name)
    ui.show_info(f"Tunnel '{name}' will use interface {config.interface_name}")
    
    if not ui.prompt_tunnel_config(config, side, manager):
        ui.show_error("Configuration cancelled.")
        ui.wait_for_enter()
        return
    
    ui.show_info("Starting tunnel...")
    tunnel = TunnelManager(config)
    success, msg = tunnel.full_setup()
    ui.show_output(msg, "Tunnel Setup")
    
    if success:
        config.save()
        ui.show_success(f"Tunnel '{name}' created and started successfully!")
    else:
        ui.show_error("Tunnel creation failed. Config not saved.")
    
    ui.wait_for_enter()


def handle_delete_tunnel(manager: ConfigManager):
    """Handle L2TPv3 tunnel deletion."""
    ui.show_banner()
    ui.show_tunnel_list(manager)
    
    tunnels = manager.list_tunnels()
    if not tunnels:
        ui.show_warning("No tunnels to delete")
        ui.wait_for_enter()
        return
    
    selected = ui.prompt_select_tunnel(manager)
    if not selected:
        return
    
    if not ui.confirm(f"Are you sure you want to delete tunnel '{selected}'?", default=False):
        return
    
    config = manager.get_tunnel(selected)
    if config:
        tunnel = TunnelManager(config)
        forward = ForwardManager(config)
        
        if config.forwarded_ports:
            ui.show_info("Clearing port forwards...")
            for port in list(config.forwarded_ports):
                forward.remove_forward(port)
        
        ui.show_info("Stopping tunnel...")
        success, msg = tunnel.full_teardown()
        ui.show_output(msg, "Tunnel Teardown")
    
    manager.delete_tunnel(selected)
    ui.show_success(f"Tunnel '{selected}' deleted")
    ui.wait_for_enter()


def handle_list_tunnels(manager: ConfigManager):
    """Handle listing L2TPv3 tunnels."""
    ui.show_banner()
    ui.show_tunnel_list(manager)
    ui.wait_for_enter()


def handle_forwards_menu(manager: ConfigManager):
    """Handle port forwards submenu."""
    ui.show_banner()
    
    config = ui.prompt_select_tunnel_for_forwards(manager)
    if not config:
        return
    
    while True:
        ui.show_banner()
        current_mode = get_forward_mode()
        forward = get_forward_manager(config)
        
        ui.console.print(f"[bold]Managing forwards for tunnel: [magenta]{config.name}[/][/]\n")
        
        if current_mode == "none":
            ui.console.print("[yellow]⚠ Port forwarding is DISABLED. Select option 6 to enable.[/]\n")
        else:
            ui.console.print(f"[green]Forward mode: {current_mode.upper()}[/]\n")
        
        if forward:
            forwards = forward.list_forwards()
            if forwards:
                ui.show_forwards_list(forwards)
        else:
            temp_manager = HAProxyManager(config)
            forwards = temp_manager.list_forwards()
            if forwards:
                ui.show_forwards_list(forwards)
        
        choice = ui.show_forwards_menu(current_mode)
        
        if choice == "0":
            break
        elif choice == "1":
            if current_mode == "none":
                ui.show_error("Please select a port forward mode first! (Option 6)")
            else:
                ports = ui.prompt_ports()
                if ports:
                    config_manager = HAProxyManager(config)
                    success, msg = config_manager.add_multiple_forwards(ports)
                    ui.show_output(msg, "Add Forwards to Config")
                    restart_forward_daemon()
                    ui.show_success("Forwards added. Daemon restarted.")
            ui.wait_for_enter()
        elif choice == "2":
            ports = ui.prompt_ports()
            if ports:
                config_manager = HAProxyManager(config)
                success, msg = config_manager.remove_multiple_forwards(ports)
                ui.show_output(msg, "Remove Forwards from Config")
                if current_mode != "none":
                    restart_forward_daemon()
            ui.wait_for_enter()
        elif choice == "3":
            ui.wait_for_enter()
        elif choice == "4":
            if current_mode == "none":
                ui.show_error("Port forwarding is disabled. Enable a mode first.")
            else:
                restart_forward_daemon()
                ui.show_success("Forward daemon restarted.")
            ui.wait_for_enter()
        elif choice == "5":
            if current_mode == "none":
                ui.show_error("Port forwarding is disabled.")
            elif forward:
                success, msg = forward.validate_and_reload()
                ui.show_output(msg, "Validate & Reload")
            ui.wait_for_enter()
        elif choice == "6":
            mode_choice = ui.show_forward_mode_menu(current_mode)
            new_mode = None
            if mode_choice == "1":
                new_mode = "none"
            elif mode_choice == "2":
                new_mode = "haproxy"
            elif mode_choice == "3":
                new_mode = "socat"
            
            if new_mode and new_mode != current_mode:
                if current_mode == "haproxy":
                    subprocess.run("systemctl stop haproxy", shell=True, capture_output=True)
                elif current_mode == "socat":
                    from vortexl2.socat_manager import stop_all_socat
                    stop_all_socat()
                
                set_forward_mode(new_mode)
                ui.show_success(f"Forward mode changed to: {new_mode.upper()}")
                
                if new_mode != "none":
                    if ui.Confirm.ask("Start port forwarding now?", default=True):
                        restart_forward_daemon()
                else:
                    subprocess.run("systemctl stop haproxy", shell=True, capture_output=True)
            ui.wait_for_enter()
        elif choice == "7":
            from vortexl2.cron_manager import (
                get_auto_restart_status,
                add_auto_restart_cron,
                remove_auto_restart_cron
            )
            
            enabled, status = get_auto_restart_status()
            ui.console.print(f"\n[bold]Current status:[/] {status}\n")
            
            cron_choice = ui.Prompt.ask("[bold cyan]1=Enable, 2=Disable, 0=Cancel[/]", default="0")
            
            if cron_choice == "1":
                interval = ui.Prompt.ask("[bold cyan]Interval (minutes)[/]", default="60")
                try:
                    success, msg = add_auto_restart_cron(int(interval))
                    ui.show_success(msg) if success else ui.show_error(msg)
                except ValueError:
                    ui.show_error("Invalid interval")
            elif cron_choice == "2":
                success, msg = remove_auto_restart_cron()
                ui.show_success(msg) if success else ui.show_error(msg)
            ui.wait_for_enter()


def handle_logs(manager: ConfigManager):
    """Handle log viewing."""
    ui.show_banner()
    tunnel_mode = get_tunnel_mode()
    
    if tunnel_mode == "easytier":
        services = ["vortexl2-easytier-*.service", "vortexl2-forward-daemon.service"]
    else:
        services = ["vortexl2-tunnel.service", "vortexl2-forward-daemon.service"]
    
    for service in services:
        result = subprocess.run(
            f"journalctl -u {service} -n 20 --no-pager",
            shell=True, capture_output=True, text=True
        )
        output = result.stdout or result.stderr or "No logs available"
        ui.show_output(output, f"Logs: {service}")
    
    ui.wait_for_enter()


# ============================================
# EASYTIER HANDLERS
# ============================================

def handle_easytier_create_tunnel():
    """Handle EasyTier tunnel creation."""
    from vortexl2.easytier_manager import EasyTierConfigManager, EasyTierManager
    from vortexl2.easytier_ui import (
        prompt_easytier_side, prompt_easytier_config, prompt_tunnel_name
    )
    
    ui.show_banner()
    
    manager = EasyTierConfigManager()
    
    side = prompt_easytier_side()
    if not side:
        return
    
    name = prompt_tunnel_name()
    if not name:
        return
    
    if manager.tunnel_exists(name):
        ui.show_error(f"Tunnel '{name}' already exists")
        ui.wait_for_enter()
        return
    
    config = manager.create_tunnel(name)
    ui.show_info(f"Tunnel '{name}' will use interface {config.interface_name}")
    
    if not prompt_easytier_config(config, side):
        ui.show_error("Configuration cancelled.")
        ui.wait_for_enter()
        return
    
    ui.show_info("Starting EasyTier tunnel...")
    tunnel_mgr = EasyTierManager(config)
    success, msg = tunnel_mgr.start_tunnel()
    ui.show_output(msg, "EasyTier Tunnel Setup")
    
    if success:
        config.save()
        ui.show_success(f"EasyTier tunnel '{name}' created and started!")
    else:
        ui.show_error("Tunnel creation failed. Config not saved.")
    
    ui.wait_for_enter()


def handle_easytier_delete_tunnel():
    """Handle EasyTier tunnel deletion."""
    from vortexl2.easytier_manager import EasyTierConfigManager, EasyTierManager
    from vortexl2.easytier_ui import show_easytier_tunnel_list, prompt_select_easytier_tunnel
    
    ui.show_banner()
    
    manager = EasyTierConfigManager()
    show_easytier_tunnel_list(manager)
    
    tunnels = manager.list_tunnels()
    if not tunnels:
        ui.show_warning("No tunnels to delete")
        ui.wait_for_enter()
        return
    
    selected = prompt_select_easytier_tunnel(manager)
    if not selected:
        return
    
    if not ui.confirm(f"Are you sure you want to delete tunnel '{selected}'?", default=False):
        return
    
    config = manager.get_tunnel(selected)
    if config:
        tunnel_mgr = EasyTierManager(config)
        success, msg = tunnel_mgr.full_teardown()
        ui.show_output(msg, "Tunnel Teardown")
    
    manager.delete_tunnel(selected)
    ui.show_success(f"EasyTier tunnel '{selected}' deleted")
    ui.wait_for_enter()


def handle_easytier_list_tunnels():
    """Handle listing EasyTier tunnels."""
    from vortexl2.easytier_manager import EasyTierConfigManager
    from vortexl2.easytier_ui import show_easytier_tunnel_list
    
    ui.show_banner()
    manager = EasyTierConfigManager()
    show_easytier_tunnel_list(manager)
    ui.wait_for_enter()


def handle_easytier_restart_tunnel():
    """Handle EasyTier tunnel restart."""
    from vortexl2.easytier_manager import EasyTierConfigManager, EasyTierManager
    from vortexl2.easytier_ui import show_easytier_tunnel_list, prompt_select_easytier_tunnel
    
    ui.show_banner()
    
    manager = EasyTierConfigManager()
    show_easytier_tunnel_list(manager)
    
    selected = prompt_select_easytier_tunnel(manager)
    if not selected:
        return
    
    config = manager.get_tunnel(selected)
    if config:
        tunnel_mgr = EasyTierManager(config)
        ui.show_info(f"Restarting tunnel '{selected}'...")
        success, msg = tunnel_mgr.restart_tunnel()
        
        if success:
            ui.show_success(msg)
        else:
            ui.show_error(msg)
    
    ui.wait_for_enter()


def handle_easytier_forwards_menu():
    """Handle EasyTier port forwards (uses same HAProxy/Socat)."""
    from vortexl2.easytier_manager import EasyTierConfigManager
    from vortexl2.easytier_ui import prompt_select_easytier_tunnel
    
    ui.show_banner()
    
    manager = EasyTierConfigManager()
    tunnels = manager.get_all_tunnels()
    
    if not tunnels:
        ui.show_warning("No EasyTier tunnels. Create one first.")
        ui.wait_for_enter()
        return
    
    # Select tunnel
    selected = prompt_select_easytier_tunnel(manager)
    if not selected:
        return
    
    config = manager.get_tunnel(selected)
    if not config:
        return
    
    # Use the same forwards menu logic with EasyTier config
    # Create a dummy L2TP config wrapper for compatibility
    from vortexl2.config import TunnelConfig
    
    # Create compatible config for HAProxy manager
    class EasyTierConfigWrapper:
        def __init__(self, et_config):
            self.name = et_config.name
            self.remote_forward_ip = et_config.remote_forward_ip
            self._forwarded_ports = et_config.forwarded_ports
            self._et_config = et_config
        
        @property
        def forwarded_ports(self):
            return self._et_config.forwarded_ports
        
        def add_port(self, port):
            self._et_config.add_port(port)
        
        def remove_port(self, port):
            self._et_config.remove_port(port)
    
    wrapper = EasyTierConfigWrapper(config)
    
    while True:
        ui.show_banner()
        current_mode = get_forward_mode()
        
        ui.console.print(f"[bold]Managing forwards for EasyTier tunnel: [magenta]{config.name}[/][/]\n")
        
        if current_mode == "none":
            ui.console.print("[yellow]⚠ Port forwarding is DISABLED. Select option 6 to enable.[/]\n")
        else:
            ui.console.print(f"[green]Forward mode: {current_mode.upper()}[/]\n")
        
        # Show current forwards
        forwards = []
        for port in config.forwarded_ports:
            forwards.append({
                "port": port,
                "remote": f"{config.remote_forward_ip}:{port}",
                "active": True if current_mode != "none" else False
            })
        if forwards:
            ui.show_forwards_list(forwards)
        
        choice = ui.show_forwards_menu(current_mode)
        
        if choice == "0":
            break
        elif choice == "1":
            if current_mode == "none":
                ui.show_error("Please select a port forward mode first! (Option 6)")
            else:
                ports = ui.prompt_ports()
                if ports:
                    from vortexl2.haproxy_manager import HAProxyManager
                    hap_manager = HAProxyManager(wrapper)
                    success, msg = hap_manager.add_multiple_forwards(ports)
                    ui.show_output(msg, "Add Forwards")
                    restart_forward_daemon()
            ui.wait_for_enter()
        elif choice == "2":
            ports = ui.prompt_ports()
            if ports:
                from vortexl2.haproxy_manager import HAProxyManager
                hap_manager = HAProxyManager(wrapper)
                success, msg = hap_manager.remove_multiple_forwards(ports)
                ui.show_output(msg, "Remove Forwards")
                if current_mode != "none":
                    restart_forward_daemon()
            ui.wait_for_enter()
        elif choice == "3":
            ui.wait_for_enter()
        elif choice == "4":
            restart_forward_daemon()
            ui.show_success("Forward daemon restarted.")
            ui.wait_for_enter()
        elif choice == "5":
            ui.show_info("Validating and reloading...")
            restart_forward_daemon()
            ui.show_success("Reloaded.")
            ui.wait_for_enter()
        elif choice == "6":
            mode_choice = ui.show_forward_mode_menu(current_mode)
            new_mode = None
            if mode_choice == "1":
                new_mode = "none"
            elif mode_choice == "2":
                new_mode = "haproxy"
            elif mode_choice == "3":
                new_mode = "socat"
            
            if new_mode and new_mode != current_mode:
                set_forward_mode(new_mode)
                ui.show_success(f"Forward mode: {new_mode.upper()}")
                if new_mode != "none":
                    restart_forward_daemon()
            ui.wait_for_enter()
        elif choice == "7":
            ui.show_info("Auto-restart cron is available in main forwards menu")
            ui.wait_for_enter()


def handle_easytier_cron_menu():
    """Handle EasyTier tunnel auto-restart cron configuration."""
    from vortexl2 import cron_manager
    
    while True:
        ui.clear_screen()
        ui.show_banner()
        
        # Get current status
        enabled, schedule = cron_manager.get_easytier_cron_status()
        status_text = f"[green]{schedule}[/]" if enabled else "[red]Disabled[/]"
        
        ui.console.print(f"\n[bold white]EasyTier Tunnel Auto-Restart[/]")
        ui.console.print(f"Current Status: {status_text}\n")
        
        ui.console.print("[bold cyan][1][/] Enable (Every 5 minutes)")
        ui.console.print("[bold cyan][2][/] Enable (Every 15 minutes)")
        ui.console.print("[bold cyan][3][/] Enable (Every 30 minutes)")
        ui.console.print("[bold cyan][4][/] Enable (Every hour)")
        ui.console.print("[bold cyan][5][/] Disable")
        ui.console.print("[bold cyan][0][/] Back")
        
        choice = ui.Prompt.ask("\n[bold cyan]Select option[/]", default="0")
        
        if choice == "0":
            break
        elif choice == "1":
            success, msg = cron_manager.add_easytier_cron(5)
        elif choice == "2":
            success, msg = cron_manager.add_easytier_cron(15)
        elif choice == "3":
            success, msg = cron_manager.add_easytier_cron(30)
        elif choice == "4":
            success, msg = cron_manager.add_easytier_cron(60)
        elif choice == "5":
            success, msg = cron_manager.remove_easytier_cron()
        else:
            ui.show_warning("Invalid option")
            ui.wait_for_enter()
            continue
        
        if success:
            ui.show_success(msg)
        else:
            ui.show_error(msg)
        ui.wait_for_enter()


def handle_dns_menu():
    """Handle DNS Manager menu."""
    from vortexl2 import dns_manager
    from vortexl2 import dns_ui
    
    while True:
        ui.clear_screen()
        ui.show_banner()
        
        # Show current status
        dns_ui.show_dns_status()
        
        choice = dns_ui.show_dns_menu()
        
        if choice == "0":
            break
        elif choice == "1":
            # Scan & Apply Best DNS
            dns_ui.scan_dns_with_progress()
            ui.wait_for_enter()
        elif choice == "2":
            # View Current DNS (already shown above)
            ui.wait_for_enter()
        elif choice == "3":
            # Set Auto-Check Interval
            hours = dns_ui.prompt_check_interval()
            if hours:
                success, msg = dns_manager.set_check_interval(hours)
                if success:
                    ui.show_success(msg)
                else:
                    ui.show_error(msg)
            ui.wait_for_enter()
        elif choice == "4":
            # Enable Auto-Check
            config = dns_manager.get_dns_config()
            hours = config.get('check_interval_hours', 4)
            success, msg = dns_manager.update_dns_cron(hours)
            if success:
                ui.show_success(msg)
            else:
                ui.show_error(msg)
            ui.wait_for_enter()
        elif choice == "5":
            # Disable Auto-Check
            success, msg = dns_manager.remove_dns_cron()
            if success:
                ui.show_success(msg)
            else:
                ui.show_error(msg)
            ui.wait_for_enter()
        else:
            ui.show_warning("Invalid option")
            ui.wait_for_enter()


# ============================================
# MAIN MENU
# ============================================

def main_menu():
    """Main interactive menu loop."""
    check_root()
    signal.signal(signal.SIGINT, signal_handler)
    ui.clear_screen()
    
    tunnel_mode = get_tunnel_mode()
    
    if tunnel_mode == "easytier":
        main_menu_easytier()
    else:
        main_menu_l2tpv3()


def main_menu_l2tpv3():
    """L2TPv3 main menu loop."""
    manager = ConfigManager()
    
    while True:
        ui.show_banner()
        choice = ui.show_main_menu()
        
        try:
            if choice == "0":
                ui.console.print("\n[bold green]Goodbye![/]\n")
                break
            elif choice == "1":
                handle_prerequisites()
            elif choice == "2":
                handle_create_tunnel(manager)
            elif choice == "3":
                handle_delete_tunnel(manager)
            elif choice == "4":
                handle_list_tunnels(manager)
            elif choice == "5":
                handle_forwards_menu(manager)
            elif choice == "6":
                handle_logs(manager)
            else:
                ui.show_warning("Invalid option")
                ui.wait_for_enter()
        except KeyboardInterrupt:
            continue
        except Exception as e:
            ui.show_error(f"Error: {e}")
            ui.wait_for_enter()


def main_menu_easytier():
    """EasyTier main menu loop."""
    from vortexl2.easytier_ui import show_easytier_main_menu
    from vortexl2.easytier_manager import EasyTierConfigManager
    from vortexl2 import cron_manager
    
    while True:
        ui.show_banner()
        choice = show_easytier_main_menu()
        
        try:
            if choice == "0":
                ui.console.print("\n[bold green]Goodbye![/]\n")
                break
            elif choice == "1":
                handle_prerequisites()
            elif choice == "2":
                handle_easytier_create_tunnel()
            elif choice == "3":
                handle_easytier_delete_tunnel()
            elif choice == "4":
                handle_easytier_list_tunnels()
            elif choice == "5":
                handle_easytier_restart_tunnel()
            elif choice == "6":
                handle_easytier_forwards_menu()
            elif choice == "7":
                # Tunnel Auto-Restart Cron
                handle_easytier_cron_menu()
            elif choice == "8":
                handle_logs(ConfigManager())
            elif choice == "9":
                handle_dns_menu()
            else:
                ui.show_warning("Invalid option")
                ui.wait_for_enter()
        except KeyboardInterrupt:
            continue
        except Exception as e:
            ui.show_error(f"Error: {e}")
            ui.wait_for_enter()


def main():
    """CLI entry point."""
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(
        description="VortexL2 - L2TPv3 & EasyTier Tunnel Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  (none)     Open interactive management panel
  apply      Apply all tunnel configurations (used by systemd)

Examples:
  sudo vortexl2           # Open management panel
  sudo vortexl2 apply     # Apply all tunnels (for systemd)
        """
    )
    parser.add_argument(
        'command',
        nargs='?',
        choices=['apply'],
        help='Command to run'
    )
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'VortexL2 {__version__}'
    )
    
    args = parser.parse_args()
    
    if args.command == 'apply':
        check_root()
        sys.exit(cmd_apply())
    else:
        main_menu()


if __name__ == "__main__":
    main()
