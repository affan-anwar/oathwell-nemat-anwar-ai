import ipaddress
import socket
from urllib.parse import urlparse


def resolve(host: str, port: int):
    return socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)


def validate_site_url(url: str, allow_private: bool = False) -> str:
    p = urlparse(url)
    if p.scheme not in ("https", "http") or (p.scheme == "http" and not allow_private):
        raise ValueError("URL must use https")
    if not p.hostname or p.username or p.password:
        raise ValueError("URL must have a host and no embedded credentials")
    try:
        infos = resolve(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror:
        raise ValueError("Host does not resolve")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not allow_private and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                                  or ip.is_multicast or ip.is_unspecified):
            raise ValueError("URL points to a private or internal address")
    return url.rstrip("/")
