from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse


ALLOWED_HOSTS = {
    "www.gub.uy",
    "gub.uy",
    "juntadepartamentallavalleja.gub.uy",
    "new.jdl.uy",
    "www.lavalleja.gub.uy",
    "lavalleja.gub.uy",
    "sit.mvot.gub.uy",
    "www.impo.com.uy",
    "impo.com.uy",
}


class DeptoUrlError(ValueError):
    pass


def _resolve_hostname(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise DeptoUrlError(f"No se pudo resolver el hostname: {hostname}") from exc
    addresses: list[str] = []
    for info in infos:
        addr = info[4][0]
        try:
            ipaddress.ip_address(addr)
        except ValueError:
            continue
        addresses.append(addr)
    return addresses


def _check_ip_safety(hostname: str) -> None:
    for addr in _resolve_hostname(hostname):
        ip = ipaddress.ip_address(addr)
        if ip.is_loopback:
            raise DeptoUrlError(f"localhost no permitido: {addr}")
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise DeptoUrlError(f"Direccion no permitida: {addr}")
        if str(ip) == "169.254.169.254":
            raise DeptoUrlError("Metadata cloud no permitido")
        if ip.is_private:
            raise DeptoUrlError(f"IP privada no permitida: {addr}")


def validate_depto_url(raw_url: str) -> str:
    if not raw_url or not raw_url.strip():
        raise DeptoUrlError("URL vacia")
    url = raw_url.strip()
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise DeptoUrlError("Solo se permiten URLs http o https")
    if parsed.username or parsed.password:
        raise DeptoUrlError("URLs con credenciales embebidas no estan permitidas")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise DeptoUrlError("Hostname invalido")
    if hostname not in ALLOWED_HOSTS:
        raise DeptoUrlError(f"Dominio no permitido: {hostname}")
    if scheme == "http":
        scheme = "https"
    path = parsed.path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return urlunparse((scheme, hostname, path, "", parsed.query, ""))


def check_depto_ip_safety(hostname: str) -> None:
    """SSRF guard resolved at download time (keeps validation offline-deterministic)."""
    if hostname not in ALLOWED_HOSTS:
        raise DeptoUrlError(f"Dominio no permitido: {hostname}")
    _check_ip_safety(hostname)


def is_redirect_allowed(location: str) -> bool:
    """Return True only if a redirect target stays within allowed hosts."""
    if not location:
        return False
    parsed = urlparse(location)
    host = (parsed.hostname or "").lower()
    return host in ALLOWED_HOSTS