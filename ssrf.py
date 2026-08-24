from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
        "instance-data",
    }
)

BLOCKED_NETS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("2001:db8::/32"),
)

BLOCKED_MSG = "blocked: not a public url"


def _blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return _blocked_ip(addr.ipv4_mapped)
    if (
        addr.is_loopback
        or addr.is_unspecified
        or addr.is_private
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or not addr.is_global
    ):
        return True
    return any(addr in net for net in BLOCKED_NETS)


def validate_url(url: str) -> str | None:
    """Return an error message if url is unsafe, else None."""
    if not isinstance(url, str) or not url.strip():
        return BLOCKED_MSG
    try:
        parsed = urlparse(url)
    except ValueError:
        return BLOCKED_MSG
    if parsed.scheme not in ("http", "https"):
        return BLOCKED_MSG
    if parsed.username is not None or parsed.password is not None:
        return BLOCKED_MSG
    if "@" in (parsed.netloc or ""):
        return BLOCKED_MSG
    host = parsed.hostname
    if not host:
        return BLOCKED_MSG
    host_folded = host.rstrip(".").casefold()
    if host_folded in BLOCKED_HOSTS:
        return BLOCKED_MSG
    try:
        port = parsed.port
    except ValueError:
        return BLOCKED_MSG
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    if port not in (80, 443):
        return BLOCKED_MSG
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return BLOCKED_MSG
    if not infos:
        return BLOCKED_MSG
    for info in infos:
        sockaddr = info[4]
        ip_s = sockaddr[0]
        if isinstance(ip_s, str) and ip_s.startswith("::ffff:"):
            ip_s = ip_s.split("::ffff:")[-1]
        try:
            ip = ipaddress.ip_address(ip_s)
        except ValueError:
            return BLOCKED_MSG
        if _blocked_ip(ip):
            return BLOCKED_MSG
    return None
