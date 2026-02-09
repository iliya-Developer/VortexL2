"""
VortexL2 EasyTier UI Components

UI functions for EasyTier tunnel management.
"""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from .easytier_manager import EasyTierConfig, EasyTierManager, EasyTierConfigManager


console = Console()


def show_easytier_main_menu() -> str:
    """Display EasyTier main menu."""
    menu_items = [
        ("1", "TCP Optimization"),
        ("2", "Create EasyTier Tunnel"),
        ("3", "Delete Tunnel"),
        ("4", "List Tunnels"),
        ("5", "Restart Tunnel"),
        ("6", "Port Forwards"),
        ("7", "Tunnel Auto-Restart"),
        ("8", "View Logs"),
        ("9", "DNS Manager"),
        ("0", "Exit"),
    ]
    
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Description", style="white")
    
    for opt, desc in menu_items:
        table.add_row(f"[{opt}]", desc)
    
    console.print(Panel(table, title="[bold white]EasyTier Menu[/]", border_style="green"))
    
    return Prompt.ask("\n[bold cyan]Select option[/]", default="0")


def show_easytier_tunnel_list(manager: EasyTierConfigManager):
    """Display list of EasyTier tunnels with peer info."""
    tunnels = manager.get_all_tunnels()
    
    if not tunnels:
        console.print("[yellow]No EasyTier tunnels configured.[/]")
        return
    
    # Basic tunnel info table
    table = Table(title="EasyTier Tunnels", box=box.ROUNDED)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="magenta")
    table.add_column("Interface", style="yellow")
    table.add_column("Local IP", style="green")
    table.add_column("Peer IP", style="cyan")
    table.add_column("Port", style="white")
    table.add_column("Status", style="white")
    
    for i, config in enumerate(tunnels, 1):
        mgr = EasyTierManager(config)
        is_running, status = mgr.get_status()
        status_display = f"[green]{status}[/]" if is_running else f"[red]{status}[/]"
        
        table.add_row(
            str(i),
            config.name,
            config.interface_name,
            config.local_ip or "-",
            config.peer_ip or "-",
            str(config.port),
            status_display
        )
    
    console.print(table)
    
    # Get peer info for running tunnels
    for config in tunnels:
        mgr = EasyTierManager(config)
        is_running, _ = mgr.get_status()
        
        if is_running:
            peers = mgr.get_peer_info()
            if peers:
                console.print(f"\n[bold cyan]Peer Stats for {config.name}:[/]")
                
                peer_table = Table(box=box.SIMPLE)
                peer_table.add_column("IP", style="green")
                peer_table.add_column("Host", style="magenta")
                peer_table.add_column("Type", style="yellow")
                peer_table.add_column("Latency", style="cyan")
                peer_table.add_column("Loss", style="red")
                peer_table.add_column("RX", style="blue")
                peer_table.add_column("TX", style="blue")
                peer_table.add_column("Tunnel", style="white")
                
                for peer in peers:
                    # Color latency based on value
                    lat = peer.get('latency', '-') or '-'
                    if lat != '-':
                        try:
                            lat_val = float(lat.replace('ms', '').strip())
                            if lat_val < 50:
                                lat = f"[green]{lat}[/]"
                            elif lat_val < 100:
                                lat = f"[yellow]{lat}[/]"
                            else:
                                lat = f"[red]{lat}[/]"
                        except:
                            pass
                    
                    # Color loss
                    loss = peer.get('loss', '-') or '-'
                    if loss != '-' and loss != '0.0%':
                        loss = f"[red]{loss}[/]"
                    elif loss == '0.0%':
                        loss = f"[green]{loss}[/]"
                    
                    peer_table.add_row(
                        peer.get('ipv4', '-'),
                        peer.get('hostname', '-'),
                        peer.get('cost', '-'),
                        lat,
                        loss,
                        peer.get('rx', '-') or '-',
                        peer.get('tx', '-') or '-',
                        peer.get('tunnel', '-') or '-'
                    )
                
                console.print(peer_table)


def prompt_easytier_side() -> Optional[str]:
    """Prompt for EasyTier tunnel side."""
    console.print("\n[bold white]Select Server Role:[/]")
    console.print("  [bold cyan][1][/] [green]IRAN[/]")
    console.print("  [bold cyan][2][/] [magenta]KHAREJ[/]")
    console.print("  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select role[/]", default="1")
    
    if choice == "1":
        return "IRAN"
    elif choice == "2":
        return "KHAREJ"
    return None


def prompt_easytier_config(config: EasyTierConfig, side: str) -> bool:
    """Prompt for EasyTier tunnel configuration."""
    console.print(f"\n[bold white]Configure EasyTier Tunnel: {config.name}[/]")
    console.print(f"[bold]Role: [{'green' if side == 'IRAN' else 'magenta'}]{side}[/][/]")
    console.print("[dim]Enter configuration values. Press Enter for defaults.[/]\n")
    
    # Set defaults based on side
    if side == "IRAN":
        default_ip = "10.155.155.1"
        default_hostname = "iran"
    else:
        default_ip = "10.155.155.2"
        default_hostname = "kharej"
    
    # Local IP (tunnel interface IP)
    console.print("[dim]This is the IP for the tunnel interface (not your server's public IP)[/]")
    local_ip = Prompt.ask("[bold yellow]Tunnel Interface IP[/]", default=default_ip)
    config._config["local_ip"] = local_ip
    
    # Peer IP (remote server's PUBLIC IP)
    if side == "IRAN":
        console.print("\n[dim]Enter the PUBLIC IP of the Kharej server[/]")
        peer_label = "[bold cyan]Kharej Server Public IP[/]"
    else:
        console.print("\n[dim]Enter the PUBLIC IP of the Iran server[/]")
        peer_label = "[bold cyan]Iran Server Public IP[/]"
    
    peer_ip = Prompt.ask(peer_label)
    if not peer_ip:
        console.print("[red]Peer IP is required![/]")
        return False
    config._config["peer_ip"] = peer_ip
    
    # Port
    console.print("\n[dim]Port for EasyTier mesh (same on both sides)[/]")
    port_str = Prompt.ask("[bold yellow]Port[/]", default="2070")
    try:
        port = int(port_str)
        config._config["port"] = port
    except ValueError:
        console.print("[red]Invalid port number[/]")
        return False
    
    # Network secret
    console.print("\n[dim]Shared secret for the mesh network (must match on all nodes)[/]")
    secret = Prompt.ask("[bold yellow]Network Secret[/]", default="vortexl2")
    config._config["network_secret"] = secret
    
    # Hostname
    console.print("\n[dim]Hostname for this node[/]")
    hostname = Prompt.ask("[bold yellow]Hostname[/]", default=default_hostname)
    config._config["hostname"] = hostname
    
    # Remote forward IP (for port forwarding, IRAN only)
    if side == "IRAN":
        console.print("\n[dim]IP to forward ports to (usually the Kharej tunnel IP)[/]")
        remote_forward = Prompt.ask("[bold yellow]Remote Forward IP[/]", default="10.155.155.2")
        config._config["remote_forward_ip"] = remote_forward
    else:
        config._config["remote_forward_ip"] = "10.155.155.1"
    
    console.print("\n[green]✓ Configuration complete![/]")
    return True


def prompt_select_easytier_tunnel(manager: EasyTierConfigManager) -> Optional[str]:
    """Prompt to select an EasyTier tunnel."""
    tunnels = manager.list_tunnels()
    
    if not tunnels:
        console.print("[yellow]No EasyTier tunnels available.[/]")
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
        if choice in tunnels:
            return choice
    
    console.print("[red]Invalid selection[/]")
    return None


def prompt_tunnel_name() -> Optional[str]:
    """Prompt for tunnel name."""
    console.print("\n[dim]Enter a unique name for the tunnel (alphanumeric and dashes only)[/]")
    name = Prompt.ask("[bold magenta]Tunnel Name[/]", default="tunnel1")
    
    # Sanitize
    name = "".join(c if c.isalnum() or c == "-" else "-" for c in name.lower())
    return name if name else None
