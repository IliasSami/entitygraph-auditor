"""SSRF-safe web URL fetcher for EntityGraph Auditor (PRD FR-23 / §18)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx


class SSRFException(Exception):
    """Raised when a URL attempts to connect to a prohibited local or private IP."""
    pass


class FetchException(Exception):
    """Raised when URL retrieval fails due to HTTP error, size limit, or timeout."""
    pass


def validate_url_safety(url: str) -> str:
    """Validate that the target URL does not resolve to private/local/link-local networks."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFException(f"Invalid URL scheme: '{parsed.scheme}'. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFException("URL lacks a valid hostname.")

    # Check for direct IP in hostname
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise SSRFException(f"Direct IP {hostname} is in a restricted network range.")
    except ValueError:
        # Not a raw IP literal; resolve via DNS
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for entry in addr_info:
                ip_str = entry[4][0]
                resolved_ip = ipaddress.ip_address(ip_str)
                if resolved_ip.is_private or resolved_ip.is_loopback or resolved_ip.is_link_local or resolved_ip.is_reserved or resolved_ip.is_multicast:
                    raise SSRFException(f"Hostname '{hostname}' resolves to restricted IP {ip_str}.")
        except socket.gaierror as e:
            raise FetchException(f"Failed to resolve DNS for hostname '{hostname}': {e}") from e

    return url


def fetch_url(url: str, timeout_seconds: float = 10.0, max_bytes: int = 5 * 1024 * 1024) -> str:
    """Safely fetch HTML or text content from a remote URL with size and timeout guards."""
    safe_url = validate_url_safety(url)

    headers = {
        "User-Agent": "EntityGraphAuditor/0.1.0 (+https://github.com/entitygraph/auditor; bot)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True, max_redirects=3) as client:
            response = client.get(safe_url, headers=headers)
            response.raise_for_status()

            # Enforce size limit
            content_bytes = response.content
            if len(content_bytes) > max_bytes:
                raise FetchException(f"Response size ({len(content_bytes)} bytes) exceeds limit of {max_bytes} bytes.")

            return response.text
    except httpx.HTTPStatusError as e:
        raise FetchException(f"HTTP error {e.response.status_code} fetching URL: {e}") from e
    except httpx.RequestError as e:
        raise FetchException(f"Network error fetching URL: {e}") from e
