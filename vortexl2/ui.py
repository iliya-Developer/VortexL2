"""
VortexL2 Terminal User Interface

Rich-based TUI with ASCII banner and menu system.
"""

import os
import sys
from typing import Optional, Callable

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
from .config import Config


console = Console()


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


def show_banner(config: Config):
    """Display the ASCII banner with system info."""
    clear_screen()
    
    role = config.role or "NOT SET"
    role_color = "green" if config.role == "IRAN" else "cyan" if config.role == "KHAREJ" else "yellow"
    
    banner_text = Text(ASCII_BANNER, style="bold cyan")
    
    # Get server IP
    server_ip = config.get_local_ip() or "Not configured"
    
    # Print banner
    console.print(banner_text)
    
    # Contact info bar
    console.print(Panel(
        f"[bold white]Telegram:[/] [cyan]@iliyadevsh[/]  |  [bold white]Version:[/] [red]{__version__}[/]  |  [bold white]GitHub:[/] [cyan]github.com/iliya-Developer[/]",
        border_style="white",
        box=box.ROUNDED
    ))
    
    # Server info
    info_lines = [
        f"[bold white]Server IP:[/] [yellow]{server_ip}[/]",
        f"[bold white]Role:[/] [{role_color}]{role}[/]",
    ]
    
    if config.ip_iran:
        info_lines.append(f"[bold white]Iran IP:[/] [green]{config.ip_iran}[/]")
    if config.ip_kharej:
        info_lines.append(f"[bold white]Kharej IP:[/] [cyan]{config.ip_kharej}[/]")
    
    console.print(Panel(
        "\n".join(info_lines),
        title="[bold white]VortexL2 - L2TPv3 Tunnel Manager[/]",
        border_style="cyan",
        box=box.ROUNDED
    ))
    console.print()


def show_main_menu() -> str:
    """Display main menu and get user choice."""
    menu_items = [
        ("1", "Install/Verify Prerequisites"),
        ("2", "Configure Endpoints"),
        ("3", "Create/Start Tunnel"),
        ("4", "Stop/Delete Tunnel"),
        ("5", "Port Forwards (Iran only)"),
        ("6", "Status/Diagnostics"),
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


def show_forwards_menu() -> str:
    """Display forwards submenu."""
    menu_items = [
        ("1", "Add Port Forwards"),
        ("2", "Remove Port Forwards"),
        ("3", "List Port Forwards"),
        ("4", "Restart All Forwards"),
        ("5", "Stop All Forwards"),
        ("6", "Start All Forwards"),
        ("0", "Back to Main Menu"),
    ]
    
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Description", style="white")
    
    for opt, desc in menu_items:
        table.add_row(f"[{opt}]", desc)
    
    console.print(Panel(table, title="[bold white]Port Forwards[/]", border_style="green"))
    
    return Prompt.ask("\n[bold cyan]Select option[/]", default="0")


def prompt_role() -> Optional[str]:
    """Prompt user to select role."""
    console.print("\n[bold white]Select Server Role:[/]")
    console.print("  [bold cyan][1][/] IRAN (receives port forwards)")
    console.print("  [bold cyan][2][/] KHAREJ (remote tunnel endpoint)")
    console.print("  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select role[/]", default="0")
    
    if choice == "1":
        return "IRAN"
    elif choice == "2":
        return "KHAREJ"
    return None


def prompt_endpoints(config: Config) -> bool:
    """Prompt user for endpoint IPs."""
    console.print("\n[bold white]Configure Endpoint IPs[/]")
    console.print("[dim]Enter the public IPs for both tunnel sides.[/]\n")
    
    # Iran IP
    default_iran = config.ip_iran or ""
    ip_iran = Prompt.ask(
        "[bold green]Iran Server Public IP[/]",
        default=default_iran if default_iran else None
    )
    if not ip_iran:
        console.print("[red]Iran IP is required[/]")
        return False
    
    # Kharej IP
    default_kharej = config.ip_kharej or ""
    ip_kharej = Prompt.ask(
        "[bold cyan]Kharej Server Public IP[/]",
        default=default_kharej if default_kharej else None
    )
    if not ip_kharej:
        console.print("[red]Kharej IP is required[/]")
        return False
    
    config.ip_iran = ip_iran
    config.ip_kharej = ip_kharej
    
    # Iran interface IP (only if IRAN role)
    if config.role == "IRAN":
        console.print("\n[dim]Configure tunnel interface IP (for l2tpeth0)[/]")
        default_iface = config.iran_iface_ip
        iran_iface = Prompt.ask(
            "[bold green]Iran l2tpeth0 IP (CIDR)[/]",
            default=default_iface
        )
        config.iran_iface_ip = iran_iface
        
        # Remote forward IP
        default_remote = config.remote_forward_ip
        remote_ip = Prompt.ask(
            "[bold green]Remote Forward Target IP[/]",
            default=default_remote
        )
        config.remote_forward_ip = remote_ip
    
    console.print("\n[green]✓ Configuration saved![/]")
    return True


def prompt_ports() -> str:
    """Prompt user for ports to forward."""
    console.print("\n[dim]Enter ports as comma-separated list (e.g., 443,80,2053)[/]")
    return Prompt.ask("[bold cyan]Ports[/]")


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


def show_status(status_data: dict):
    """Display tunnel status in a formatted table."""
    table = Table(title="Tunnel Status", box=box.ROUNDED)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Role", status_data.get("role", "Not set") or "Not set")
    table.add_row("Configured", "Yes" if status_data.get("configured") else "No")
    table.add_row("Tunnel Exists", "[green]Yes[/]" if status_data.get("tunnel_exists") else "[red]No[/]")
    table.add_row("Session Exists", "[green]Yes[/]" if status_data.get("session_exists") else "[red]No[/]")
    table.add_row("Interface Up", "[green]Yes[/]" if status_data.get("interface_up") else "[red]No[/]")
    table.add_row("Interface IP", status_data.get("interface_ip") or "None")
    
    console.print(table)
    
    if status_data.get("tunnel_info"):
        console.print(Panel(status_data["tunnel_info"], title="Tunnel Info", border_style="dim"))
    
    if status_data.get("session_info"):
        console.print(Panel(status_data["session_info"], title="Session Info", border_style="dim"))


def show_forwards_list(forwards: list):
    """Display port forwards in a table."""
    if not forwards:
        console.print("[yellow]No port forwards configured[/]")
        return
    
    table = Table(title="Port Forwards", box=box.ROUNDED)
    table.add_column("Port", style="cyan", justify="right")
    table.add_column("Remote Target", style="white")
    table.add_column("Status", style="white")
    table.add_column("Enabled", style="white")
    
    for fwd in forwards:
        status_style = "green" if fwd["status"] == "active" else "red"
        enabled_style = "green" if fwd["enabled"] == "enabled" else "yellow"
        
        table.add_row(
            str(fwd["port"]),
            fwd["remote"],
            f"[{status_style}]{fwd['status']}[/]",
            f"[{enabled_style}]{fwd['enabled']}[/]"
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
