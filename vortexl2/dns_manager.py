"""
VortexL2 DNS Manager

Scans multiple DNS servers, tests latency, and automatically applies the best one.
Supports periodic auto-check via cron.
"""

import subprocess
import time
import os
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import yaml

# Configuration
DNS_CONFIG_FILE = Path("/etc/vortexl2/dns_config.yaml")
DEFAULT_CHECK_INTERVAL = 4  # hours

# Test domains for DNS validation
TEST_DOMAIN_1 = "chatgpt.com"
TEST_DOMAIN_2 = "one.one.one.one"

TIMEOUT = 2.8  # seconds for nslookup
REPEAT = 2     # repetitions for averaging

# DNS servers list
RAW_DNS_LIST = [
    ("رادار", "10.202.10.10"), ("رادار", "10.202.10.11"),
    ("سرویس 403", "10.202.10.202"), ("سرویس 403", "10.202.10.102"),
    ("بگذر", "185.55.226.26"), ("بگذر", "185.55.225.25"),
    ("شکن", "178.22.122.100"), ("شکن", "185.51.200.2"),
    ("شاتل", "85.15.1.14"), ("شاتل", "85.15.1.15"),
    ("الکترو", "78.157.42.100"), ("الکترو", "78.157.42.101"),
    ("هاستیران", "172.29.2.100"),
    
    ("Server IR", "194.104.158.48"), ("Server IR", "194.104.158.78"),
    ("Level3", "209.244.0.3"), ("Level3", "209.244.0.4"),
    ("OpenDNS", "208.67.222.222"), ("OpenDNS", "208.67.220.220"),
    
    ("Gaming DNS 1", "78.157.42.100"), ("Gaming DNS 1", "185.43.135.1"),
    ("Gaming DNS 2", "156.154.70.1"), ("Gaming DNS 2", "156.154.71.1"),
    ("Gaming DNS 3", "149.112.112.112"), ("Gaming DNS 3", "149.112.112.10"),
    ("Gaming DNS 4", "185.108.22.133"), ("Gaming DNS 4", "185.108.22.134"),
    ("Gaming DNS 5", "85.214.41.206"), ("Gaming DNS 5", "89.15.250.41"),
    ("Gaming DNS 6", "9.9.9.9"), ("Gaming DNS 6", "109.69.8.51"),
    ("Gaming DNS 7", "8.26.56.26"), ("Gaming DNS 7", "8.26.247.20"),
    ("Gaming DNS 8", "185.121.177.177"), ("Gaming DNS 8", "169.239.202.202"),
    ("Gaming DNS 9", "185.231.182.126"), ("Gaming DNS 9", "185.43.135.1"),
    ("Gaming DNS 10", "185.43.135.1"), ("Gaming DNS 10", "46.16.216.25"),
    ("Gaming DNS 11", "185.213.182.126"), ("Gaming DNS 11", "185.43.135.1"),
    ("Gaming DNS 12", "199.85.127.10"), ("Gaming DNS 12", "185.231.182.126"),
    ("Gaming DNS 13", "91.239.100.100"), ("Gaming DNS 13", "37.152.182.112"),
    ("Gaming DNS 14", "8.26.56.26"), ("Gaming DNS 14", "8.20.247.20"),
    ("Gaming DNS 15", "78.157.42.100"), ("Gaming DNS 15", "1.1.1.1"),
    ("Gaming DNS 16", "87.135.66.81"), ("Gaming DNS 16", "76.76.10.4"),
    
    ("مخابرات/شاتل/آسیاتک/رایتل", "91.239.100.100"), ("مخابرات/شاتل/آسیاتک/رایتل", "89.233.43.71"),
    ("پارس آنلاین", "46.224.1.221"), ("پارس آنلاین", "46.224.1.220"),
    ("همراه اول", "208.67.220.200"), ("همراه اول", "208.67.222.222"),
    ("ایرانسل", "109.69.8.51"),
    ("ایرانسل", "74.82.42.42"),
    ("مخابرات", "8.8.8.8"), ("مخابرات", "8.8.4.4"),
    ("مخابرات", "4.4.4.4"), ("مخابرات", "4.2.2.4"),
    ("مخابرات", "195.46.39.39"), ("مخابرات", "195.46.39.40"),
    ("مبین نت", "10.44.8.8"), ("مبین نت", "8.8.8.8"),
    ("سایر اپراتورها", "199.85.127.10"), ("سایر اپراتورها", "199.85.126.10"),
    
    # International
    ("Cloudflare", "1.1.1.1"), ("Cloudflare", "1.0.0.1"),
    ("Google", "8.8.8.8"), ("Google", "8.8.4.4"),
    ("Quad9", "9.9.9.9"), ("Quad9", "149.112.112.112"),
]


def _run(cmd: List[str], timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    """Execute command with optional timeout."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)


def has_cmd(name: str) -> bool:
    """Check if a command is available."""
    try:
        result = subprocess.run(["which", name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except:
        return False


def systemd_resolved_active() -> bool:
    """Check if systemd-resolved is active."""
    try:
        p = _run(["systemctl", "is-active", "systemd-resolved"], timeout=2.0)
        return p.stdout.strip() == "active"
    except:
        return False


def get_default_iface() -> str:
    """Get default network interface."""
    try:
        p = _run(["bash", "-c", "ip route show default | awk '{print $5}' | head -n1"])
        return (p.stdout or "").strip() or "eth0"
    except:
        return "eth0"


def normalize_dns_list(raw: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Remove duplicates and invalid entries."""
    seen = set()
    out = []
    for name, ip in raw:
        ip = ip.strip()
        if ip == "0.0.0.0" or not ip:
            continue
        if ip in seen:
            continue
        seen.add(ip)
        out.append((name.strip(), ip))
    return out


def nslookup_latency_ms(domain: str, dns_ip: str) -> Optional[float]:
    """Test DNS latency using nslookup."""
    total = 0.0
    ok = 0
    for _ in range(REPEAT):
        t0 = time.time()
        try:
            p = _run(["nslookup", domain, dns_ip], timeout=TIMEOUT)
            if p.returncode == 0:
                total += (time.time() - t0) * 1000
                ok += 1
        except subprocess.TimeoutExpired:
            pass
        except:
            pass
    if ok == 0:
        return None
    return round(total / ok, 1)


def score_dns(dns_ip: str) -> Optional[Tuple[float, float, float]]:
    """Score a DNS server by testing both domains."""
    lat1 = nslookup_latency_ms(TEST_DOMAIN_1, dns_ip)
    if lat1 is None:
        return None
    lat2 = nslookup_latency_ms(TEST_DOMAIN_2, dns_ip)
    if lat2 is None:
        return None
    score = round((lat1 + lat2) / 2.0, 1)
    return score, lat1, lat2


def apply_dns(dns_ip: str) -> Tuple[bool, str]:
    """Apply DNS setting to the system."""
    try:
        if has_cmd("resolvectl") and systemd_resolved_active():
            iface = get_default_iface()
            p1 = _run(["resolvectl", "dns", iface, dns_ip])
            if p1.returncode != 0:
                return False, f"resolvectl dns failed: {p1.stderr}"
            
            _run(["resolvectl", "domain", iface, "~."])
            _run(["resolvectl", "flush-caches"])
            return True, f"Applied via systemd-resolved on {iface}: DNS={dns_ip}"
        
        if has_cmd("nmcli"):
            p = _run(["bash", "-c", "nmcli -t -f NAME,DEVICE c show --active | head -n1"])
            line = (p.stdout or "").strip()
            if line:
                conn = line.split(":")[0]
                p2 = _run(["nmcli", "c", "modify", conn, "ipv4.dns", dns_ip, "ipv4.ignore-auto-dns", "yes"])
                if p2.returncode == 0:
                    _run(["nmcli", "c", "down", conn])
                    _run(["nmcli", "c", "up", conn])
                    return True, f"Applied via NetworkManager: {conn} DNS={dns_ip}"
        
        # Fallback to /etc/resolv.conf
        with open("/etc/resolv.conf", "w") as f:
            f.write(f"nameserver {dns_ip}\n")
        return True, f"Applied by writing /etc/resolv.conf: DNS={dns_ip}"
    
    except Exception as e:
        return False, f"Failed to apply DNS: {e}"


def scan_and_apply_best_dns(callback=None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Scan all DNS servers and apply the best one.
    
    callback: Optional function(name, ip, status, score) for progress updates
    
    Returns: (success, message, best_dns_info)
    """
    if not has_cmd("nslookup"):
        return False, "nslookup not found. Install: sudo apt install -y dnsutils", None
    
    dns_list = normalize_dns_list(RAW_DNS_LIST)
    results: List[Tuple[float, str, str, float, float]] = []
    
    for name, ip in dns_list:
        s = score_dns(ip)
        if s is None:
            if callback:
                callback(name, ip, "fail", None)
            continue
        score, lat1, lat2 = s
        if callback:
            callback(name, ip, "ok", score)
        results.append((score, name, ip, lat1, lat2))
    
    if not results:
        return False, "No DNS server could resolve both test domains.", None
    
    best = sorted(results, key=lambda x: x[0])[0]
    score, name, ip, lat1, lat2 = best
    
    best_info = {
        "name": name,
        "ip": ip,
        "score": score,
        "latency1": lat1,
        "latency2": lat2,
    }
    
    success, msg = apply_dns(ip)
    if success:
        # Save to config
        save_dns_config(ip, name)
        return True, f"Best DNS: {name} ({ip}) - Score: {score}ms\n{msg}", best_info
    else:
        return False, f"Found best DNS but failed to apply: {msg}", best_info


def get_dns_config() -> Dict[str, Any]:
    """Get current DNS configuration."""
    if DNS_CONFIG_FILE.exists():
        try:
            with open(DNS_CONFIG_FILE, 'r') as f:
                return yaml.safe_load(f) or {}
        except:
            pass
    return {
        "check_interval_hours": DEFAULT_CHECK_INTERVAL,
        "current_dns": None,
        "current_dns_name": None,
        "last_check": None,
    }


def save_dns_config(dns_ip: str, dns_name: str) -> None:
    """Save DNS configuration."""
    DNS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    config = get_dns_config()
    config["current_dns"] = dns_ip
    config["current_dns_name"] = dns_name
    config["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(DNS_CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


def set_check_interval(hours: int) -> Tuple[bool, str]:
    """Set the auto-check interval in hours."""
    config = get_dns_config()
    config["check_interval_hours"] = hours
    DNS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DNS_CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    # Update cron
    return update_dns_cron(hours)


def get_check_interval() -> int:
    """Get current check interval in hours."""
    config = get_dns_config()
    return config.get("check_interval_hours", DEFAULT_CHECK_INTERVAL)


def update_dns_cron(hours: int) -> Tuple[bool, str]:
    """Update cron job for DNS auto-check."""
    cron_marker = "# VortexL2 DNS Auto-Check"
    cron_cmd = f"0 */{hours} * * * root /usr/local/bin/vortexl2-dns-check {cron_marker}"
    cron_file = Path("/etc/cron.d/vortexl2-dns")
    
    try:
        with open(cron_file, 'w') as f:
            f.write(f"SHELL=/bin/bash\n")
            f.write(f"PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin\n")
            f.write(f"{cron_cmd}\n")
        os.chmod(cron_file, 0o644)
        return True, f"DNS auto-check scheduled every {hours} hours"
    except Exception as e:
        return False, f"Failed to create cron job: {e}"


def remove_dns_cron() -> Tuple[bool, str]:
    """Remove DNS auto-check cron job."""
    cron_file = Path("/etc/cron.d/vortexl2-dns")
    try:
        if cron_file.exists():
            cron_file.unlink()
        return True, "DNS auto-check disabled"
    except Exception as e:
        return False, f"Failed to remove cron job: {e}"


def get_dns_cron_status() -> Tuple[bool, str]:
    """Get DNS cron job status."""
    cron_file = Path("/etc/cron.d/vortexl2-dns")
    if cron_file.exists():
        try:
            content = cron_file.read_text()
            # Extract interval from cron
            import re
            match = re.search(r'\*/(\d+)', content)
            if match:
                hours = match.group(1)
                return True, f"Every {hours} hours"
        except:
            pass
        return True, "Enabled"
    return False, "Disabled"


def get_current_system_dns() -> Optional[str]:
    """Get current system DNS."""
    try:
        if has_cmd("resolvectl") and systemd_resolved_active():
            p = _run(["resolvectl", "status"])
            # Parse DNS Server line
            for line in p.stdout.split('\n'):
                if 'DNS Servers:' in line or 'Current DNS Server:' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        return parts[1].strip().split()[0]
        
        # Try /etc/resolv.conf
        if os.path.exists("/etc/resolv.conf"):
            with open("/etc/resolv.conf", 'r') as f:
                for line in f:
                    if line.strip().startswith("nameserver"):
                        return line.split()[1]
    except:
        pass
    return None
