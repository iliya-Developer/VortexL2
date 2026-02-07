"""
VortexL2 Terminal User Interface

Rich-based TUI with ASCII banner and menu system.
"""

import os
import sys
import re
import subprocess
from typing import Optional, List

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich import box
except ImportError:
    print("Error: 'rich' library is required. Install with: pip install rich")
    sys.exit(1)

from . import __version__
from .config import TunnelConfig, ConfigManager


console = Console()


def get_local_ip() -> Optional[str]:
    """Auto-detect the server's primary IP address."""
    try:
        # Method 1: Get IP from default route interface
        result = subprocess.run(
            "ip route get 8.8.8.8 | grep -oP 'src \\K[0-9.]+'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip()
            if is_valid_ip(ip):
                return ip
        
        # Method 2: Fallback to hostname -I
        result = subprocess.run(
            "hostname -I | awk '{print $1}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip()
            if is_valid_ip(ip):
                return ip
    except Exception:
        pass
    
    return None


def is_valid_ip(ip: str) -> bool:
    """Validate IPv4 address format."""
    if not ip:
        return False
    # Remove CIDR if present
    ip_only = ip.split('/')[0]
    parts = ip_only.split('.')
    if len(parts) != 4:
        return False
    try:
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False
        return True
    except ValueError:
        return False


def prompt_valid_ip(label: str, default: str = None, required: bool = True) -> Optional[str]:
    """Prompt for IP address with validation."""
    while True:
        ip = Prompt.ask(label, default=default if default else None)
        if not ip:
            if required:
                console.print("[red]This field is required[/]")
                continue
            return None
        if is_valid_ip(ip):
            return ip
        console.print(f"[red]Invalid IP address: {ip}[/]")
        console.print("[dim]Format: X.X.X.X (each part 0-255)[/]")


def prompt_encap_type() -> str:
    """Prompt user to select encapsulation type."""
    console.print("\n[bold cyan]Select Encapsulation Type:[/]")
    console.print("  [1] IP  - Direct IP encapsulation")
    console.print("  [2] UDP - UDP encapsulation")
    console.print("[dim]Default: IP encapsulation[/dim]\n")
    
    choice = Prompt.ask(
        "[bold cyan]Select encapsulation[/]",
        choices=["1", "2"],
        default="1"
    )
    
    return "ip" if choice == "1" else "udp"


def prompt_udp_port() -> int:
    """Prompt user for UDP port."""
    while True:
        port_str = Prompt.ask(
            "[bold cyan]UDP port[/]",
            default="55555"
        )
        
        try:
            port = int(port_str)
            if 1 <= port <= 65535:
                return port
            console.print("[red]Port must be between 1 and 65535[/]")
        except ValueError:
            console.print("[red]Invalid port number[/]")



ASCII_BANNER = r"""
 __      __        _            _     ___  
 \ \    / /       | |          | |   |__ \ 
  \ \  / /__  _ __| |_ _____  _| |      ) |
   \ \/ / _ \| '__| __/ _ \ \/ / |     / / 
    \  / (_) | |  | ||  __/>  <| |____/ /_ 
     \/ \___/|_|   \__\___/_/\_\______|____|
"""


def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def show_banner():
    """Display the ASCII banner with developer info."""
    clear_screen()
    
    banner_text = Text(ASCII_BANNER, style="bold cyan")
    
    # Print banner
    console.print(banner_text)
    
    # Developer info bar
    console.print(Panel(
        f"[bold white]Telegram:[/] [cyan]@iliyadevsh[/]  |  [bold white]Version:[/] [red]{__version__}[/]  |  [bold white]GitHub:[/] [cyan]github.com/iliya-Developer[/]",
        title="[bold white]VortexL2 - L2TPv3 Tunnel Manager[/]",
        border_style="cyan",
        box=box.ROUNDED
    ))
    console.print()


def show_main_menu() -> str:
    """Display main menu and get user choice."""
    menu_items = [
        ("1", "Install/Verify Prerequisites"),
        ("2", "Create Tunnel"),
        ("3", "Delete Tunnel"),
        ("4", "List Tunnels"),
        ("5", "Port Forwards"),
        ("6", "Manage Secure Encryption (WireGuard)"),
        ("7", "View Logs"),
        ("0", "Exit"),
    ]
    
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Description", style="white")
    
    for opt, desc in menu_items:
        table.add_row(f"[{opt}]", desc)
    
    console.print(Panel(table, title="[bold white]Main Menu[/]", border_style="blue"))
    
    return Prompt.ask("\n[bold cyan]Select option[/]", default="0")


def show_forwards_menu(forward_mode: str = "none") -> str:
    """Display forwards submenu."""
    # Mode indicator
    mode_colors = {"none": "dim", "haproxy": "green", "socat": "yellow"}
    mode_color = mode_colors.get(forward_mode, "dim")
    mode_label = f"[{mode_color}]{forward_mode.upper()}[/]"
    
    menu_items = [
        ("1", "Add Port Forwards"),
        ("2", "Remove Port Forwards"),
        ("3", "List Port Forwards"),
        ("4", "Restart All Forwards"),
        ("5", "Validate & Reload"),
        ("6", f"Change Forward Mode (Current: {mode_label})"),
        ("7", "Setup Auto-Restart (Cron)"),
        ("0", "Back to Main Menu"),
    ]
    
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Description", style="white")
    
    for opt, desc in menu_items:
        table.add_row(f"[{opt}]", desc)
    
    console.print(Panel(table, title="[bold white]Port Forwards[/]", border_style="green"))
    
    return Prompt.ask("\n[bold cyan]Select option[/]", default="0")


def show_forward_mode_menu(current_mode: str) -> str:
    """Display forward mode selection menu."""
    modes = [
        ("1", "none", "Disabled - Port forwarding off"),
        ("2", "haproxy", "HAProxy - High performance port forwarding"),
        ("3", "socat", "Socat - Simple port forwarding"),
        ("0", "", "Cancel"),
    ]
    
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Mode", style="yellow", width=10)
    table.add_column("Description", style="white")
    
    for opt, mode, desc in modes:
        current = " [green]✓[/]" if mode == current_mode else ""
        table.add_row(f"[{opt}]", mode + current, desc)
    
    console.print(Panel(table, title="[bold white]Select Forward Mode[/]", border_style="yellow"))
    
    return Prompt.ask("\n[bold cyan]Select mode[/]", default="0")


def show_tunnel_list(manager: ConfigManager):
    """Display list of all configured tunnels with status."""
    from .tunnel import TunnelManager
    
    tunnels = manager.get_all_tunnels()
    
    if not tunnels:
        console.print("[yellow]No tunnels configured.[/]")
        return
    
    table = Table(title="Configured Tunnels", box=box.ROUNDED)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="magenta")
    table.add_column("Local IP", style="green")
    table.add_column("Remote IP", style="cyan")
    table.add_column("Interface", style="yellow")
    table.add_column("Tunnel ID", style="white")
    table.add_column("Status", style="white")
    
    for i, config in enumerate(tunnels, 1):
        tunnel_mgr = TunnelManager(config)
        is_running = tunnel_mgr.check_tunnel_exists()
        status = "[green]Running[/]" if is_running else "[red]Stopped[/]"
        
        table.add_row(
            str(i),
            config.name,
            config.local_ip or "-",
            config.remote_ip or "-",
            config.interface_name,
            str(config.tunnel_id),
            status
        )
    
    console.print(table)


def prompt_tunnel_name() -> Optional[str]:
    """Prompt for new tunnel name."""
    console.print("\n[dim]Enter a unique name for the tunnel (alphanumeric and dashes only)[/]")
    name = Prompt.ask("[bold magenta]Tunnel Name[/]", default="tunnel1")
    
    # Sanitize name
    name = "".join(c if c.isalnum() or c == "-" else "-" for c in name.lower())
    return name if name else None


def prompt_select_tunnel(manager: ConfigManager) -> Optional[str]:
    """Prompt user to select a tunnel from list."""
    tunnels = manager.list_tunnels()
    
    if not tunnels:
        console.print("[yellow]No tunnels available.[/]")
        return None
    
    console.print("\n[bold white]Available Tunnels:[/]")
    for i, name in enumerate(tunnels, 1):
        console.print(f"  [bold cyan][{i}][/] {name}")
    console.print(f"  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select tunnel[/]", default="0")
    
    try:
        idx = int(choice)
        if idx == 0:
            return None
        if 1 <= idx <= len(tunnels):
            return tunnels[idx - 1]
    except ValueError:
        # Maybe they typed the name directly
        if choice in tunnels:
            return choice
    
    console.print("[red]Invalid selection[/]")
    return None


def prompt_tunnel_side() -> Optional[str]:
    """Prompt for tunnel side (Iran or Kharej)."""
    console.print("\n[bold white]Select Server Side:[/]")
    console.print("  [bold cyan][1][/] [green]IRAN[/]")
    console.print("  [bold cyan][2][/] [magenta]KHAREJ[/]")
    console.print("  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select side[/]", default="1")
    
    if choice == "1":
        return "IRAN"
    elif choice == "2":
        return "KHAREJ"
    else:
        return None


def prompt_tunnel_config(config: TunnelConfig, side: str, manager: ConfigManager = None) -> bool:
    """Prompt user for tunnel configuration based on side with duplicate validation."""
    console.print(f"\n[bold white]Configure Tunnel: {config.name}[/]")
    console.print(f"[bold]Side: [{'green' if side == 'IRAN' else 'magenta'}]{side}[/][/]")
    console.print("[dim]Enter configuration values. Press Enter to use defaults.[/]\n")
    
    # Get used values for duplicate checking (exclude current tunnel if editing)
    used_values = {}
    if manager:
        used_values = manager.get_used_values(exclude_tunnel=config.name)
    
    # Set defaults based on side
    if side == "IRAN":
        default_interface_ip = "10.30.30.1"
        default_remote_forward = "10.30.30.2"
        default_tunnel_id = 1000
        default_peer_tunnel_id = 2000
        default_session_id = 10
        default_peer_session_id = 20
    else:  # KHAREJ
        default_interface_ip = "10.30.30.2"
        default_remote_forward = "10.30.30.1"
        default_tunnel_id = 2000
        default_peer_tunnel_id = 1000
        default_session_id = 20
        default_peer_session_id = 10
    
    # Local IP (with validation and auto-detection)
    detected_ip = get_local_ip()
    if detected_ip:
        console.print(f"[dim]Detected server IP: [green]{detected_ip}[/][/]")
        default_local = config.local_ip or detected_ip
    else:
        default_local = config.local_ip or ""
    
    local_ip = prompt_valid_ip(
        "[bold green]Local Server Public IP[/] (this server)",
        default=default_local if default_local else None,
        required=True
    )
    if not local_ip:
        return False
    config.local_ip = local_ip
    
    # Remote IP (with validation)
    if side == "IRAN":
        remote_label = "[bold cyan]Kharej Server Public IP[/]"
    else:
        remote_label = "[bold cyan]Iran Server Public IP[/]"
    
    default_remote = config.remote_ip or ""
    remote_ip = prompt_valid_ip(
        remote_label,
        default=default_remote if default_remote else None,
        required=True
    )
    if not remote_ip:
        return False
    config.remote_ip = remote_ip
    
    # Encapsulation type
    console.print("\n[dim]Select L2TP encapsulation mode[/]")
    encap_type = prompt_encap_type()
    config.encap_type = encap_type
    console.print(f"[green]✓ Encapsulation: {encap_type.upper()}[/]")
    
    # UDP port (if UDP mode)
    if encap_type == "udp":
        console.print("\n[dim]Enter UDP port for L2TP tunnel[/]")
        udp_port = prompt_udp_port()
        config.udp_port = udp_port
        console.print(f"[green]✓ UDP Port: {udp_port}[/]")
    
    
    # Interface IP (with validation and duplicate check)
    console.print(f"\n[dim]Configure tunnel interface IP (for {config.interface_name})[/]")
    while True:
        interface_ip = prompt_valid_ip(
            "[bold yellow]Interface IP[/]",
            default=default_interface_ip,
            required=True
        )
        if not interface_ip:
            return False
        
        # Check for duplicate interface IP
        interface_ip_only = interface_ip.split('/')[0]
        if used_values and interface_ip_only in used_values.get("interface_ips", set()):
            console.print(f"[red]Error: Interface IP {interface_ip_only} is already used by another tunnel![/]")
            console.print("[dim]Please enter a different IP address.[/]")
            continue
        break
    
    # Auto append /30 if not already present
    if "/" not in interface_ip:
        interface_ip = f"{interface_ip}/30"
    config.interface_ip = interface_ip
    
    # Remote forward target IP (only relevant for Iran, with validation)
    if side == "IRAN":
        remote_forward = prompt_valid_ip(
            "[bold yellow]Remote Forward Target IP[/]",
            default=default_remote_forward,
            required=True
        )
        if not remote_forward:
            return False
        config.remote_forward_ip = remote_forward
    else:
        config.remote_forward_ip = default_remote_forward
    
    # Tunnel IDs with duplicate validation
    console.print("\n[dim]Configure L2TPv3 tunnel IDs (press Enter to use defaults)[/]")
    
    # Tunnel ID
    while True:
        tunnel_id_input = Prompt.ask(
            "[bold yellow]Tunnel ID[/]",
            default=str(default_tunnel_id)
        )
        try:
            tunnel_id = int(tunnel_id_input)
            if used_values and tunnel_id in used_values.get("tunnel_ids", set()):
                console.print(f"[red]Error: Tunnel ID {tunnel_id} is already used by another tunnel![/]")
                continue
            break
        except ValueError:
            console.print("[red]Invalid number, please enter an integer[/]")
    config.tunnel_id = tunnel_id
    
    # Peer Tunnel ID
    while True:
        peer_tunnel_id_input = Prompt.ask(
            "[bold yellow]Peer Tunnel ID[/]",
            default=str(default_peer_tunnel_id)
        )
        try:
            peer_tunnel_id = int(peer_tunnel_id_input)
            if used_values and peer_tunnel_id in used_values.get("peer_tunnel_ids", set()):
                console.print(f"[red]Error: Peer Tunnel ID {peer_tunnel_id} is already used by another tunnel![/]")
                continue
            break
        except ValueError:
            console.print("[red]Invalid number, please enter an integer[/]")
    config.peer_tunnel_id = peer_tunnel_id
    
    # Session ID
    while True:
        session_id_input = Prompt.ask(
            "[bold yellow]Session ID[/]",
            default=str(default_session_id)
        )
        try:
            session_id = int(session_id_input)
            if used_values and session_id in used_values.get("session_ids", set()):
                console.print(f"[red]Error: Session ID {session_id} is already used by another tunnel![/]")
                continue
            break
        except ValueError:
            console.print("[red]Invalid number, please enter an integer[/]")
    config.session_id = session_id
    
    # Peer Session ID
    while True:
        peer_session_id_input = Prompt.ask(
            "[bold yellow]Peer Session ID[/]",
            default=str(default_peer_session_id)
        )
        try:
            peer_session_id = int(peer_session_id_input)
            if used_values and peer_session_id in used_values.get("peer_session_ids", set()):
                console.print(f"[red]Error: Peer Session ID {peer_session_id} is already used by another tunnel![/]")
                continue
            break
        except ValueError:
            console.print("[red]Invalid number, please enter an integer[/]")
    config.peer_session_id = peer_session_id
    
    console.print("\n[green]✓ Configuration saved![/]")
    return True


def prompt_ports() -> str:
    """Prompt user for ports to forward."""
    console.print("\n[dim]Enter ports as comma-separated list (e.g., 443,80,2053)[/]")
    return Prompt.ask("[bold cyan]Ports[/]")


def prompt_select_tunnel_for_forwards(manager: ConfigManager) -> Optional[TunnelConfig]:
    """Prompt to select a tunnel for port forwarding."""
    tunnels = manager.get_all_tunnels()
    
    if not tunnels:
        console.print("[yellow]No tunnels available. Create one first.[/]")
        return None
    
    if len(tunnels) == 1:
        return tunnels[0]
    
    console.print("\n[bold white]Select tunnel for port forwards:[/]")
    for i, tunnel in enumerate(tunnels, 1):
        console.print(f"  [bold cyan][{i}][/] {tunnel.name}")
    console.print(f"  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select tunnel[/]", default="1")
    
    try:
        idx = int(choice)
        if idx == 0:
            return None
        if 1 <= idx <= len(tunnels):
            return tunnels[idx - 1]
    except ValueError:
        pass
    
    console.print("[red]Invalid selection[/]")
    return None


def show_success(message: str):
    """Display success message."""
    console.print(f"\n[bold green]✓[/] {message}")


def show_error(message: str):
    """Display error message."""
    console.print(f"\n[bold red]✗[/] {message}")


def show_warning(message: str):
    """Display warning message."""
    console.print(f"\n[bold yellow]![/] {message}")


def show_info(message: str):
    """Display info message."""
    console.print(f"\n[bold cyan]ℹ[/] {message}")


def show_forwards_list(forwards: list):
    """Display port forwards in a table."""
    if not forwards:
        console.print("[yellow]No port forwards configured[/]")
        return
    
    table = Table(title="Port Forwards", box=box.ROUNDED)
    table.add_column("Port", style="cyan", justify="right")
    table.add_column("Remote Target", style="white")
    table.add_column("Status", style="white")
    table.add_column("Sessions", style="white")
    
    for fwd in forwards:
        # Check for 'active' key (new format) or 'running' key (old format)
        if "active" in fwd:
            is_active = fwd.get("active", False)
            status = "active" if is_active else "inactive"
            status_style = "green" if is_active else "red"
            sessions = str(fwd.get("active_sessions", 0))
        elif "running" in fwd:
            # Old format compatibility
            is_running = fwd.get("running", False)
            status = "active" if is_running else "inactive"
            status_style = "green" if is_running else "red"
            sessions = str(fwd.get("active_sessions", 0))
        else:
            # Fallback
            status = fwd.get("status", "unknown")
            status_style = "green" if status == "active" else "red"
            sessions = "-"
        
        table.add_row(
            str(fwd["port"]),
            fwd.get("remote", "-"),
            f"[{status_style}]{status}[/]",
            sessions
        )
    
    console.print(table)


def show_output(output: str, title: str = "Output"):
    """Display command output in a panel."""
    console.print(Panel(output, title=title, border_style="dim"))


def wait_for_enter():
    """Wait for user to press Enter."""
    console.print()
    Prompt.ask("[dim]Press Enter to continue[/]", default="")


def confirm(message: str, default: bool = False) -> bool:
    """Ask for confirmation."""
    return Confirm.ask(message, default=default)


def show_wireguard_menu() -> str:
    """Display WireGuard encryption submenu."""
    menu_items = [
        ("1", "Install/Enable Secure Layer"),
        ("2", "Disable Secure Layer"),
        ("3", "View Status/Keys"),
        ("0", "Back to Main Menu"),
    ]

    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Description", style="white")

    for opt, desc in menu_items:
        table.add_row(f"[{opt}]", desc)

    console.print(Panel(table, title="[bold white]Secure Encryption (WireGuard)[/]", border_style="magenta"))

    return Prompt.ask("\n[bold cyan]Select option[/]", default="0")


def show_wireguard_status(status: dict):
    """Display WireGuard status in a rich table."""
    table = Table(title="WireGuard Status", box=box.ROUNDED)
    table.add_column("Property", style="cyan", width=22)
    table.add_column("Value", style="white")

    installed = status.get("installed", False)
    iface_up = status.get("interface_up", False)

    table.add_row("Installed", "[green]Yes[/]" if installed else "[red]No[/]")
    table.add_row("Interface (wg_vortex)", "[green]UP[/]" if iface_up else "[red]DOWN[/]")
    table.add_row("WireGuard IP", status.get("wg_ip") or "-")
    table.add_row("Listen Port", str(status.get("listen_port") or "-"))
    table.add_row("Public Key", status.get("public_key") or "-")
    table.add_row("Peer Public Key", status.get("peer_public_key") or "-")
    table.add_row("Peer Endpoint", status.get("peer_endpoint") or "-")
    table.add_row("Latest Handshake", status.get("latest_handshake") or "-")
    table.add_row("Transfer RX", status.get("transfer_rx", "0 B"))
    table.add_row("Transfer TX", status.get("transfer_tx", "0 B"))
    table.add_row("BBR Enabled", "[green]Yes[/]" if status.get("bbr_enabled") else "[red]No[/]")

    console.print(table)

    # Show public key prominently for easy sharing
    pub = status.get("public_key")
    if pub:
        console.print(Panel(
            f"[bold green]{pub}[/]",
            title="[bold white]Your Public Key (share with peer)[/]",
            border_style="green",
            box=box.ROUNDED
        ))


def prompt_peer_public_key() -> Optional[str]:
    """Prompt user to paste the remote peer's WireGuard public key."""
    console.print("\n[dim]Paste the WireGuard public key from the OTHER server.[/]")
    console.print("[dim]You can get it by running option 3 (View Status/Keys) on the peer.[/]")
    key = Prompt.ask("[bold magenta]Peer Public Key[/]")
    if key and len(key.strip()) >= 40:
        return key.strip()
    console.print("[red]Invalid key. A WireGuard public key is a 44-character base64 string.[/]")
    return None


def prompt_wireguard_side() -> Optional[str]:
    """Prompt for WireGuard side (IRAN or KHAREJ)."""
    console.print("\n[bold white]Select this server's role:[/]")
    console.print("  [bold cyan][1][/] [green]IRAN[/]  (10.8.0.1)")
    console.print("  [bold cyan][2][/] [magenta]KHAREJ[/] (10.8.0.2)")
    console.print("  [bold cyan][0][/] Cancel")

    choice = Prompt.ask("\n[bold cyan]Select side[/]", default="0")

    if choice == "1":
        return "IRAN"
    elif choice == "2":
        return "KHAREJ"
    return None
