import ipaddress
from urllib.parse import urlparse

from flask import current_app


class UrlValidationError(ValueError):
    pass


def validate_provider_url(raw_url: str) -> str:
    if not raw_url:
        raise UrlValidationError("URL vacia")

    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in ("http", "https"):
        raise UrlValidationError("Solo se permiten URLs http o https")

    if parsed.username or parsed.password:
        raise UrlValidationError("URLs con credenciales embebidas no estan permitidas")

    hostname = parsed.hostname or ""
    if not hostname:
        raise UrlValidationError("Hostname invalido")

    allowed_private = current_app.config.get("PROVIDER_ALLOWED_PRIVATE_HOSTS", [])

    is_private_host = hostname in allowed_private or hostname == "localhost"

    if not is_private_host and parsed.scheme != "https":
        raise UrlValidationError("HTTPS es requerido para proveedores externos")

    try:
        import socket
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise UrlValidationError(f"No se pudo resolver el hostname: {hostname}")

    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            if hostname not in allowed_private and hostname != "localhost":
                raise UrlValidationError(f"Direccion no permitida: {addr}")
        if ip.is_private and hostname not in allowed_private:
            raise UrlValidationError(f"Direccion privada no permitida: {hostname}")
        if str(ip) == "169.254.169.254":
            raise UrlValidationError("Metadata cloud no permitido")

    path = parsed.path.rstrip("/")
    if not path:
        path = ""
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{hostname}{(':' + str(parsed.port)) if parsed.port else ''}{path}{query}"