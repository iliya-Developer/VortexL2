"""
VortexL2 DNS Manager UI

TUI for DNS manager with Rich components.
"""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

from .dns_manager import (
    scan_and_apply_best_dns,
    get_dns_config,
    get_check_interval,
    set_check_interval,
    get_dns_cron_status,
    update_dns_cron,
    remove_dns_cron,
    get_current_system_dns,
    normalize_dns_list,
    RAW_DNS_LIST,
)

console = Console()


def show_dns_menu() -> str:
    """Display DNS manager menu."""
    menu_items = [
        ("1", "Scan & Apply Best DNS"),
        ("2", "View Current DNS"),
        ("3", "Set Auto-Check Interval"),
        ("4", "Enable Auto-Check"),
        ("5", "Disable Auto-Check"),
        ("0", "Back"),
    ]
    
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Description", style="white")
    
    for opt, desc in menu_items:
        table.add_row(f"[{opt}]", desc)
    
    console.print(Panel(table, title="[bold white]DNS Manager[/]", border_style="blue"))
    
    return Prompt.ask("\n[bold cyan]Select option[/]", default="0")


def show_dns_status():
    """Display current DNS status."""
    config = get_dns_config()
    current_dns = get_current_system_dns()
    cron_enabled, cron_status = get_dns_cron_status()
    
    table = Table(box=box.ROUNDED, show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Current System DNS", current_dns or "Unknown")
    table.add_row("Last Applied DNS", f"{config.get('current_dns_name', 'N/A')} ({config.get('current_dns', 'N/A')})")
    table.add_row("Last Check", config.get('last_check', 'Never'))
    table.add_row("Auto-Check Interval", f"{config.get('check_interval_hours', 4)} hours")
    table.add_row("Auto-Check Status", f"[green]{cron_status}[/]" if cron_enabled else f"[red]{cron_status}[/]")
    
    console.print(Panel(table, title="[bold white]DNS Status[/]", border_style="blue"))


def scan_dns_with_progress() -> None:
    """Scan DNS servers with progress display."""
    console.print("\n[bold cyan]🌐 Scanning DNS Servers...[/]\n")
    console.print(f"[dim]Testing domains: chatgpt.com, one.one.one.one[/]\n")
    
    results = []
    failed = []
    
    def callback(name, ip, status, score):
        if status == "ok":
            results.append((score, name, ip))
            console.print(f"[green]✓[/] {name:<28} {ip:<15} [cyan]{score}ms[/]")
        else:
            failed.append((name, ip))
            console.print(f"[red]✗[/] {name:<28} {ip:<15} [dim]FAIL[/]")
    
    success, message, best_info = scan_and_apply_best_dns(callback)
    
    console.print("")
    
    if success and best_info:
        console.print(Panel(
            f"[bold green]🏆 Best DNS Selected[/]\n\n"
            f"[bold]{best_info['name']}[/] → [cyan]{best_info['ip']}[/]\n"
            f"Score: [green]{best_info['score']}ms[/]\n\n"
            f"[dim]{message}[/]",
            border_style="green"
        ))
    else:
        console.print(f"[red]❌ {message}[/]")


def prompt_check_interval() -> Optional[int]:
    """Prompt for auto-check interval."""
    console.print("\n[bold white]Set Auto-Check Interval[/]\n")
    console.print("[dim]DNS will be scanned and best one applied automatically.[/]\n")
    
    console.print("  [bold cyan][1][/] Every 1 hour")
    console.print("  [bold cyan][2][/] Every 2 hours")
    console.print("  [bold cyan][3][/] Every 4 hours (default)")
    console.print("  [bold cyan][4][/] Every 6 hours")
    console.print("  [bold cyan][5][/] Every 12 hours")
    console.print("  [bold cyan][6][/] Every 24 hours")
    console.print("  [bold cyan][7][/] Custom")
    console.print("  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select[/]", default="3")
    
    intervals = {"1": 1, "2": 2, "3": 4, "4": 6, "5": 12, "6": 24}
    
    if choice == "0":
        return None
    elif choice == "7":
        custom = Prompt.ask("[bold cyan]Enter hours (1-24)[/]", default="4")
        try:
            hours = int(custom)
            if 1 <= hours <= 24:
                return hours
            console.print("[red]Invalid value. Use 1-24.[/]")
            return None
        except:
            console.print("[red]Invalid number.[/]")
            return None
    elif choice in intervals:
        return intervals[choice]
    
    return None
