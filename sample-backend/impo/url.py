from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


ALLOWED_HOSTS = {"impo.com.uy", "www.impo.com.uy"}
BASES_PREFIX = "/bases/"
IMPO_HOME = "https://www.impo.com.uy"


class ImpoUrlError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalUrl:
    canonical: str
    json_url: str

    @property
    def path_segments(self) -> list[str]:
        path = urlparse(self.canonical).path.strip("/")
        return [seg for seg in path.split("/") if seg]


def _resolve_hostname(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ImpoUrlError(f"No se pudo resolver el hostname: {hostname}") from exc
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
            raise ImpoUrlError(f"localhost no permitido: {addr}")
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise ImpoUrlError(f"Direccion no permitida: {addr}")
        if str(ip) == "169.254.169.254":
            raise ImpoUrlError("Metadata cloud no permitido")
        if ip.is_private:
            raise ImpoUrlError(f"IP privada no permitida: {addr}")


def _validate_host(hostname: str) -> None:
    if not hostname:
        raise ImpoUrlError("Hostname invalido")
    if hostname not in ALLOWED_HOSTS:
        raise ImpoUrlError(f"Dominio no permitido: {hostname}. Solo IMPO es aceptado.")
    # NOTE: DNS/IP safety resolution is performed at download time in
    # impo/client.py (check_impo_ip_safety), not here, so that URL
    # normalization stays deterministic and offline-testable.


def check_impo_ip_safety(hostname: str) -> None:
    """Resolve the hostname and reject loopback/private/link-local addresses.

    This is the SSRF guard and is intentionally invoked at download time so
    URL normalization remains offline-deterministic.
    """
    _check_ip_safety(hostname)


_NORMA_SLUG = re.compile(r"^(?P<slug>[A-Za-z][A-Za-z0-9-]*?)\d*$")
_NORMA_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")


def _is_norma_segment(segment: str) -> bool:
    return bool(_NORMA_SEGMENT.match(segment)) and "-" in segment and segment.split("-")[-1].isdigit()


def _is_article_segment(segment: str) -> bool:
    return segment.isdigit()


def normalize_impo_url(raw_url: str) -> CanonicalUrl:
    if not raw_url or not raw_url.strip():
        raise ImpoUrlError("URL vacia")
    url = raw_url.strip()

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ImpoUrlError("Solo se permiten URLs http o https")
    if parsed.username or parsed.password:
        raise ImpoUrlError("URLs con credenciales embebidas no estan permitidas")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ImpoUrlError("Hostname invalido")

    if scheme == "http":
        scheme = "https"

    path = parsed.path.rstrip("/")
    if not path:
        raise ImpoUrlError("La URL debe contener una ruta /bases/")

    if not path.startswith(BASES_PREFIX):
        raise ImpoUrlError("La ruta debe comenzar con /bases/")

    _validate_host(hostname)

    relative = path[len(BASES_PREFIX):]
    segments = [seg for seg in relative.split("/") if seg]
    if len(segments) < 2:
        raise ImpoUrlError("URL de norma incompleta")

    if not _is_norma_segment(segments[1]):
        if _is_article_segment(segments[1]):
            raise ImpoUrlError("Falta el identificador de norma")
        raise ImpoUrlError("Identificador de norma invalido")

    norma_segments = [segments[0], segments[1]]
    canonical_path = f"{BASES_PREFIX}{'/'.join(norma_segments)}"
    canonical = urlunparse((scheme, hostname, canonical_path, "", "", ""))
    json_url = urlunparse((scheme, hostname, canonical_path, "", "json=true", ""))
    return CanonicalUrl(canonical=canonical, json_url=json_url)


def slug_from_canonical(canonical_url: str) -> str:
    parsed = urlparse(canonical_url)
    relative = parsed.path.strip("/")
    segments = [seg for seg in relative.split("/") if seg]
    if len(segments) >= 2:
        return f"{segments[0]}-{segments[1]}"
    return relative