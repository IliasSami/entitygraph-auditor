"""SSRF-safe URL fetcher (PRD FR-23 retrieval, FR-24 security, §18 threat model).

This module is the single SSRF gate for outbound HTTP(S) retrieval:

* Only ``http``/``https`` URLs are accepted; dangerous schemes such as
  ``file``/``ftp``/``gopher``/``data`` are refused (``SSRF_SCHEME``) and other
  non-http schemes are refused as ``SCHEME_UNSUPPORTED``.
* Every target — the initial URL, each redirect hop, and ``robots.txt`` — is
  validated *before* bytes are requested.  The hostname is resolved with
  ``socket.getaddrinfo`` and **every** returned address is checked against the
  denied ranges (loopback, link-local/cloud metadata, private, CGNAT 100.64/10,
  unspecified, multicast/reserved, plus IPv4-mapped/6to4/Teredo embedded IPv4),
  together with ``localhost``/``*.localhost``/``*.local`` hostname rules and
  decimal/hex/octal IPv4 encodings.
* A transport wrapper re-validates every request as it leaves the client so a
  second DNS answer observed after the pre-flight check (DNS rebinding) is
  rejected as well — PRD FR-24 "re-check after DNS resolution and redirects".
* Responses are streamed with a byte cap (partial bodies are discarded),
  connect/read timeouts, a strict MIME allowlist, redirect limits, and
  robots.txt handling with a per-host cache.

``fetch_url`` never executes JavaScript and never runs any page content: the
body is returned as decoded text only and ``render_mode`` is always
``text_only``.  Per PRD §0 rule 11 and FR-23, fetched text is untrusted data —
this module only retrieves it; it never obeys instructions found in it.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

__all__ = [
    "TEXT_ONLY_NOTE",
    "FetchBlocked",
    "FetchResult",
    "clear_robots_cache",
    "fetch_url",
]

DEFAULT_USER_AGENT = "EntityGraphAuditor/0.1 (+local audit tool)"

#: Honest limitation appended to every result: a text-only fetch validates none
#: of the JS-rendering / indexing / bot-access properties (PRD FR-02, FR-23).
TEXT_ONLY_NOTE = (
    "Text-only fetch: does not validate JS rendering, indexing or bot access."
)

ALLOWED_SCHEMES = frozenset({"http", "https"})

#: Non-http schemes that are classic SSRF/local-file vectors -> SSRF_SCHEME.
DANGEROUS_SCHEMES = frozenset(
    {
        "data",
        "dict",
        "file",
        "ftp",
        "gopher",
        "jar",
        "javascript",
        "ldap",
        "mailto",
        "tftp",
        "ws",
        "wss",
    }
)

#: Content types accepted for a page fetch (PRD FR-23). JSON is rejected.
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/xhtml+xml",
        "application/xml",
        "text/html",
        "text/markdown",
        "text/plain",
        "text/xml",
    }
)

HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

ROBOTS_TIMEOUT_S = 3.0
ROBOTS_MAX_BYTES = 500_000

#: Hostnames that are never fetched unless allow_private=True (FR-24).
BLOCKED_HOSTNAMES = frozenset(
    {"localhost", "instance-data", "metadata.google", "metadata.google.internal"}
)
BLOCKED_HOSTNAME_SUFFIXES = (
    ".localhost",
    ".local",
    ".metadata.google.internal",
)

#: Explicit denied ranges (IPv4 + IPv6), version-independent (FR-24).
DENIED_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        # IPv4
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",  # carrier-grade NAT
        "127.0.0.0/8",  # loopback
        "169.254.0.0/16",  # link-local incl. 169.254.169.254 metadata
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",  # TEST-NET-1
        "192.168.0.0/16",
        "198.18.0.0/15",  # benchmarking
        "198.51.100.0/24",  # TEST-NET-2
        "203.0.113.0/24",  # TEST-NET-3
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved + broadcast
        # IPv6
        "::/128",  # unspecified
        "::1/128",  # loopback
        "64:ff9b::/96",  # NAT64 (embedded IPv4)
        "fc00::/7",  # unique local
        "fe80::/10",  # link-local
        "ff00::/8",  # multicast
        "2002::/16",  # 6to4 (embedded IPv4)
    )
)

_HEX_OR_DEC_TOKEN = re.compile(r"0[xX][0-9a-fA-F]+|[0-9]+")
_DOTTED_IP_TOKEN = re.compile(r"[0-9a-fA-FxX]+(?:\.[0-9a-fA-FxX]+)+")
_CHARSET_RE = re.compile(r"charset\s*=\s*[\"']?([A-Za-z0-9._+-]+)", re.IGNORECASE)


@dataclass
class FetchResult:
    """Outcome of a successful, SSRF-validated fetch (PRD FR-23 / FR-02).

    ``render_mode`` is always ``text_only``: this module never renders
    JavaScript, so ``limitations`` must keep the honest text-only note.
    """

    url: str
    final_url: str
    status: int
    content_type: str
    body_text: str
    fetched_at: str
    canonical_url: str | None
    title: str | None
    robots: str | None
    redirects: list[str]
    size_bytes: int
    render_mode: str = "text_only"
    limitations: list[str] = field(default_factory=list)
    blocked_reason: str | None = None


class FetchBlocked(Exception):
    """A fetch was refused by a security or policy gate.

    ``code`` is a stable machine-readable reason:

    ``SSRF_PRIVATE_ADDRESS``, ``SSRF_SCHEME``, ``ROBOTS_DISALLOWED``,
    ``TOO_MANY_REDIRECTS``, ``TIMEOUT``, ``TOO_LARGE``, ``MIME_UNSUPPORTED``,
    ``DNS_FAILURE``, ``HTTP_ERROR``, ``SCHEME_UNSUPPORTED``.

    The exception message is a safe human summary; it never includes resolver
    internals or any proxy credentials (FR-24).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# Address / host validation (the SSRF gate)
# --------------------------------------------------------------------------- #


def _ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return ``host`` parsed as an IP literal, including odd encodings.

    Handles bracketed/standard literals via ``ipaddress`` and decimal, hex
    (``0x7f000001``), octal (``0177.0.0.1``) and shortened (``127.1``) IPv4
    forms via ``socket.inet_aton`` — the encodings browsers historically accept
    but naive host checks miss.  Returns ``None`` for ordinary hostnames.
    """
    cleaned = host.strip().strip("[]").rstrip(".")
    if not cleaned:
        return None
    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        pass
    candidate: str | None = None
    if _HEX_OR_DEC_TOKEN.fullmatch(cleaned):
        candidate = cleaned
    elif "." in cleaned and _DOTTED_IP_TOKEN.fullmatch(cleaned):
        candidate = cleaned
    if candidate is None:
        return None
    try:
        return ipaddress.ip_address(socket.inet_aton(candidate))
    except (OSError, ValueError):
        return None


def _ip_denied(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True when ``ip`` must not be fetched (loopback/private/link-local/...).

    Embedded IPv4 inside IPv6 (``::ffff:``-mapped, 6to4, Teredo) is unwrapped
    and checked against the IPv4 rules as well (FR-24).
    """
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped
        if mapped is not None and _ip_denied(mapped):
            return True
        sixtofour = getattr(ip, "sixtofour", None)
        if sixtofour is not None and _ip_denied(sixtofour):
            return True
        teredo = getattr(ip, "teredo", None)
        if teredo is not None:
            for part in teredo:
                if _ip_denied(part):  # type: ignore[arg-type]
                    return True
    for network in DENIED_NETWORKS:
        if ip.version == network.version and ip in network:
            return True
    # Default deny: anything not globally routable is refused.
    return not ip.is_global


def _hostname_denied(host: str) -> bool:
    """True for localhost-style and cloud-metadata hostnames (FR-24)."""
    normalized = host.lower().rstrip(".")
    if normalized in BLOCKED_HOSTNAMES:
        return True
    return any(normalized.endswith(suffix) for suffix in BLOCKED_HOSTNAME_SUFFIXES)


def _resolve_host(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve ``host`` and return every address; raise DNS_FAILURE on error.

    All returned addresses are collected so the caller can reject the target
    if *any* answer is in a denied range (rebinding defence).
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        raise FetchBlocked("DNS_FAILURE", f"Could not resolve host '{host}'.") from None
    resolved: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        try:
            resolved.append(ipaddress.ip_address(sockaddr[0]))
        except (ValueError, IndexError):
            continue
    if not resolved:
        raise FetchBlocked("DNS_FAILURE", f"Could not resolve host '{host}'.")
    return resolved


def _validate_target(url: str, *, allow_private: bool) -> None:
    """Validate scheme + host + resolved addresses of ``url`` before any I/O.

    Raises :class:`FetchBlocked` with ``SSRF_SCHEME``/``SCHEME_UNSUPPORTED``
    for bad schemes, ``SSRF_PRIVATE_ADDRESS`` for denied hosts/addresses and
    ``DNS_FAILURE`` when the name cannot be resolved.  With
    ``allow_private=True`` (admin dev opt-in, FR-24) the address restrictions
    are lifted; the http/https scheme allowlist is still enforced.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        raise FetchBlocked("SCHEME_UNSUPPORTED", "The URL could not be parsed.") from None
    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        if scheme in DANGEROUS_SCHEMES:
            raise FetchBlocked(
                "SSRF_SCHEME",
                f"URL scheme '{scheme}' is not permitted; only http and https are fetched.",
            )
        raise FetchBlocked(
            "SCHEME_UNSUPPORTED",
            "Only http:// and https:// URLs are supported.",
        )
    try:
        port = parts.port
    except ValueError:
        raise FetchBlocked("SCHEME_UNSUPPORTED", "The URL port is invalid.") from None
    host = parts.hostname
    if not host:
        raise FetchBlocked("SCHEME_UNSUPPORTED", "The URL has no hostname.")
    if allow_private:
        return
    normalized_host = host.lower().rstrip(".")
    if _hostname_denied(normalized_host):
        raise FetchBlocked(
            "SSRF_PRIVATE_ADDRESS",
            f"Host '{normalized_host}' targets a private or local network.",
        )
    literal = _ip_literal(normalized_host)
    if literal is not None:
        if _ip_denied(literal):
            raise FetchBlocked(
                "SSRF_PRIVATE_ADDRESS",
                "The URL targets a private, loopback, link-local or reserved address.",
            )
        return
    default_port = 443 if scheme == "https" else 80
    for ip in _resolve_host(normalized_host, port or default_port):
        if _ip_denied(ip):
            raise FetchBlocked(
                "SSRF_PRIVATE_ADDRESS",
                f"Host '{normalized_host}' resolves to a private, loopback, "
                "link-local or reserved address.",
            )


def _is_local_target(url: str) -> bool:
    """Best-effort local-target check (no DNS) used for robots/dev decisions."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = parts.hostname
    if not host:
        return False
    normalized = host.lower().rstrip(".")
    if _hostname_denied(normalized):
        return True
    literal = _ip_literal(normalized)
    return literal is not None and _ip_denied(literal)


class _SSRFGuardedTransport(httpx.AsyncBaseTransport):
    """Wrap a transport so every outbound request re-runs the SSRF validation.

    httpx issues one request per redirect hop through the transport, so this
    re-checks the *connected* request — PRD FR-24 "re-check after DNS
    resolution and redirects", §18 SSRF mitigation.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport, *, allow_private: bool) -> None:
        self._inner = inner
        self._allow_private = allow_private

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        _validate_target(str(request.url), allow_private=self._allow_private)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


# --------------------------------------------------------------------------- #
# robots.txt (PRD FR-23 policy handling)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _RobotsFile:
    """Cached robots.txt outcome: parsed text, or ``None`` + a note."""

    text: str | None
    note: str


_ROBOTS_CACHE: dict[tuple[str, str, str], _RobotsFile] = {}


def clear_robots_cache() -> None:
    """Reset the per-host robots.txt cache (useful for tests and long runs)."""
    _ROBOTS_CACHE.clear()


def _ua_token(user_agent: str) -> str:
    return user_agent.split("/", 1)[0].strip().lower()


def _agent_matches(agent: str, ua_token: str) -> bool:
    """Conservative user-agent match (both prefixes count; empty never matches)."""
    if not agent or not ua_token:
        return False
    return ua_token == agent or ua_token.startswith(agent) or agent.startswith(ua_token)


def _robots_allows(robots_text: str, user_agent: str, path: str) -> tuple[bool, str]:
    """Evaluate ``path`` against robots.txt content for ``user_agent``.

    Deliberately simple (PRD FR-23 asks for simple parsing, no external
    dependency): group selection by user-agent, prefix path matching, longest
    rule wins with Allow winning ties (RFC 9309).  Returns
    ``(allowed, limitations_note)``.
    """
    ua_token = _ua_token(user_agent)
    groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[bool, str]] = []
    saw_rule = False
    for raw_line in robots_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        directive, _, value = line.partition(":")
        directive = directive.strip().lower()
        value = value.strip()
        if directive == "user-agent":
            if saw_rule:
                if agents:
                    groups.append((agents, rules))
                agents, rules = [], []
                saw_rule = False
            if value:
                agents.append(value.lower())
        elif directive in ("allow", "disallow"):
            if not value:
                continue  # empty rule = no restriction
            saw_rule = True
            rules.append((directive == "allow", value))
        # Sitemap/Crawl-delay/other directives are ignored.
    if agents:
        groups.append((agents, rules))

    specific = [
        group
        for group in groups
        if any(a != "*" and _agent_matches(a, ua_token) for a in group[0])
    ]
    wildcard = [group for group in groups if any(a == "*" for a in group[0])]
    selected = specific or wildcard
    if not selected:
        return True, "robots.txt: no rule for this agent"

    best_length = -1
    best_allow = True
    matched_any = False
    for _group_agents, group_rules in selected:
        for is_allow, rule_path in group_rules:
            if not path.startswith(rule_path):
                continue
            matched_any = True
            length = len(rule_path)
            if length > best_length or (
                length == best_length and is_allow and not best_allow
            ):
                best_length, best_allow = length, is_allow
    if not matched_any:
        return True, "robots.txt: allowed (no disallow rule for this path)"
    if best_allow:
        return True, "robots.txt: allowed (an Allow rule matched this path)"
    return False, "robots.txt: disallowed"


def _robots_request_url(target_url: str) -> str:
    """Build ``{scheme}://{authority}/robots.txt`` for ``target_url`` (no userinfo)."""
    parts = urlsplit(target_url)
    host = parts.hostname or ""
    display = f"[{host}]" if ":" in host else host
    authority = display + (f":{parts.port}" if parts.port else "")
    return f"{parts.scheme}://{authority}/robots.txt"


async def _robots_file(
    client: httpx.AsyncClient,
    target_url: str,
    *,
    user_agent: str,
    allow_private: bool,
) -> _RobotsFile:
    """Fetch (and cache per scheme/host/UA) the robots.txt for ``target_url``.

    Fetch failures are treated permissively (this is a permissive-by-default
    audit tool): the outcome and reason are recorded in ``limitations``.
    """
    parts = urlsplit(target_url)
    key = (parts.scheme.lower(), (parts.netloc or "").lower(), _ua_token(user_agent))
    cached = _ROBOTS_CACHE.get(key)
    if cached is not None:
        return cached

    robots_url = _robots_request_url(target_url)
    entry: _RobotsFile
    try:
        _validate_target(robots_url, allow_private=allow_private)
        status, headers, body, _final = await _send(
            client,
            robots_url,
            user_agent=user_agent,
            timeout_s=ROBOTS_TIMEOUT_S,
            max_bytes=ROBOTS_MAX_BYTES,
        )
    except FetchBlocked as exc:
        entry = _RobotsFile(
            None,
            f"robots.txt: could not be fetched ({exc.code}); treated as allowed "
            "(permissive default)",
        )
    else:
        if status == 200:
            entry = _RobotsFile(body.decode("utf-8-sig", errors="replace"), "")
        elif status in (404, 410):
            entry = _RobotsFile(None, "robots.txt: no file")
        elif status >= 500:
            entry = _RobotsFile(
                None, "robots.txt: server error; treated as allowed (permissive default)"
            )
        else:
            entry = _RobotsFile(
                None, "robots.txt: unavailable; treated as allowed (permissive default)"
            )
    _ROBOTS_CACHE[key] = entry
    return entry


async def _enforce_robots(
    client: httpx.AsyncClient,
    target_url: str,
    *,
    user_agent: str,
    allow_private: bool,
    limitations: list[str],
) -> None:
    """Raise ``ROBOTS_DISALLOWED`` when robots.txt forbids ``target_url``.

    For localhost/dev targets fetched with ``allow_private=True`` the robots
    check is skipped and the skip is disclosed in ``limitations``.
    """
    if allow_private and _is_local_target(target_url):
        note = "robots.txt: skipped for local/dev target (allow_private=True)"
        if note not in limitations:
            limitations.append(note)
        return
    robots = await _robots_file(
        client, target_url, user_agent=user_agent, allow_private=allow_private
    )
    if robots.text is None:
        if robots.note not in limitations:
            limitations.append(robots.note)
        return
    path = urlsplit(target_url).path or "/"
    allowed, note = _robots_allows(robots.text, user_agent, path)
    if note not in limitations:
        limitations.append(note)
    if not allowed:
        raise FetchBlocked(
            "ROBOTS_DISALLOWED",
            "robots.txt on this host disallows fetching this URL for this user agent.",
        )


# --------------------------------------------------------------------------- #
# Request execution
# --------------------------------------------------------------------------- #


async def _send(
    client: httpx.AsyncClient,
    url: str,
    *,
    user_agent: str,
    timeout_s: float,
    max_bytes: int,
) -> tuple[int, dict[str, str], bytes, str]:
    """Perform one streamed GET, enforcing timeout and ``max_bytes``.

    Redirect responses are returned without a body so the caller can follow
    them manually (each hop is re-validated).  When the byte limit is exceeded
    the body is discarded and ``TOO_LARGE`` is raised — a partial body is
    never returned to the caller.
    """
    request_headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
    }
    try:
        async with client.stream(
            "GET",
            url,
            headers=request_headers,
            follow_redirects=False,
            timeout=httpx.Timeout(timeout_s),
        ) as response:
            status = response.status_code
            response_url = str(response.url)
            headers = {key.lower(): value for key, value in response.headers.items()}
            if status in REDIRECT_STATUSES and headers.get("location"):
                return status, headers, b"", response_url
            declared = (headers.get("content-length") or "").strip()
            if declared.isdigit() and int(declared) > max_bytes:
                raise FetchBlocked(
                    "TOO_LARGE", f"Response exceeds the {max_bytes}-byte size limit."
                )
            chunks: list[bytes] = []
            received = 0
            async for chunk in response.aiter_bytes():
                received += len(chunk)
                if received > max_bytes:
                    raise FetchBlocked(
                        "TOO_LARGE", f"Response exceeds the {max_bytes}-byte size limit."
                    )
                chunks.append(chunk)
            return status, headers, b"".join(chunks), response_url
    except FetchBlocked:
        raise
    except httpx.TimeoutException as exc:
        raise FetchBlocked(
            "TIMEOUT", f"Request did not complete within the {timeout_s:g}s timeout."
        ) from exc
    except httpx.ConnectError as exc:
        raise FetchBlocked(
            "DNS_FAILURE", "Could not resolve or connect to the target host."
        ) from exc
    except httpx.HTTPError as exc:
        raise FetchBlocked(
            "HTTP_ERROR", "The HTTP request failed before a response was received."
        ) from exc


# --------------------------------------------------------------------------- #
# Response decoding / metadata (no script execution)
# --------------------------------------------------------------------------- #


def _decode_body(content_type_header: str, raw: bytes) -> str:
    """Decode with the declared charset, falling back to UTF-8 (replacement tolerated)."""
    encodings: list[str] = []
    match = _CHARSET_RE.search(content_type_header or "")
    if match:
        encodings.append(match.group(1))
    encodings.append("utf-8")
    for encoding in encodings:
        try:
            return raw.decode(encoding, errors="replace")
        except LookupError:
            continue
    return raw.decode("utf-8", errors="replace")


def _html_metadata(
    body_text: str, base_url: str
) -> tuple[str | None, str | None, str | None]:
    """Extract ``(title, canonical_url, robots_meta)`` with a non-fetching parser.

    ``BeautifulSoup`` with the stdlib ``html.parser`` never executes scripts,
    loads frames or fetches subresources — the page body is plain data.
    """
    soup = BeautifulSoup(body_text, "html.parser")
    title: str | None = None
    if soup.title is not None:
        title = soup.title.get_text(strip=True) or None
    canonical: str | None = None
    link = soup.find("link", rel="canonical")
    if link is not None and link.get("href"):
        canonical = urljoin(base_url, str(link["href"]).strip())
    robots_meta: str | None = None
    meta = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.IGNORECASE)})
    if meta is not None and meta.get("content"):
        robots_meta = str(meta["content"]).strip()
    return title, canonical, robots_meta


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


async def fetch_url(
    url: str,
    *,
    allow_private: bool = False,
    timeout_s: float = 10.0,
    max_bytes: int = 5_000_000,
    user_agent: str = DEFAULT_USER_AGENT,
    respect_robots: bool = True,
    max_redirects: int = 5,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FetchResult:
    """Fetch ``url`` safely and return text-only page data (PRD FR-23/FR-24).

    Security gates, in order: scheme allowlist → hostname/IP validation
    (literal, alternate encodings, DNS answers) → robots.txt → per-hop
    redirect re-validation → size/timeout/MIME limits.  All gates raise
    :class:`FetchBlocked` with a machine-readable ``.code``.

    Args:
        url: Absolute http(s) URL to fetch.
        allow_private: Admin/dev opt-in to reach private/loopback targets;
            also skips robots.txt for local targets.
        timeout_s: Connect + read timeout in seconds for page requests.
        max_bytes: Hard cap on response bytes; larger bodies are discarded.
        user_agent: User agent sent (and matched against robots.txt).
        respect_robots: Consult robots.txt before fetching.
        max_redirects: Maximum redirect hops; each hop is re-validated.
        transport: Optional ``httpx.AsyncBaseTransport`` (e.g.
            ``httpx.MockTransport``) so tests run without any network access.
            SSRF validation still runs for every request.

    Returns:
        :class:`FetchResult` with honest ``limitations``; ``render_mode`` is
        always ``text_only`` because this function never executes JavaScript.

    Raises:
        FetchBlocked: A security/policy gate refused the fetch; inspect
            ``.code`` for the machine-readable reason.
        ValueError: Invalid limits were supplied.
    """
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if max_redirects < 0:
        raise ValueError("max_redirects must not be negative")

    limitations: list[str] = [TEXT_ONLY_NOTE]

    # Pre-flight validation before any socket work (FR-24).
    _validate_target(url, allow_private=allow_private)

    inner = transport if transport is not None else httpx.AsyncHTTPTransport()
    guarded = _SSRFGuardedTransport(inner, allow_private=allow_private)

    current_url = url
    redirects: list[str] = []
    status = 0
    headers: dict[str, str] = {}
    body = b""
    final_url = url

    async with httpx.AsyncClient(
        transport=guarded,
        timeout=httpx.Timeout(timeout_s),
        follow_redirects=False,
        trust_env=False,  # ignore HTTP(S)_PROXY/.netrc — no proxy credential use
    ) as client:
        for _hop in range(max_redirects + 1):
            _validate_target(current_url, allow_private=allow_private)
            if respect_robots:
                await _enforce_robots(
                    client,
                    current_url,
                    user_agent=user_agent,
                    allow_private=allow_private,
                    limitations=limitations,
                )
            status, headers, body, final_url = await _send(
                client,
                current_url,
                user_agent=user_agent,
                timeout_s=timeout_s,
                max_bytes=max_bytes,
            )
            location = headers.get("location")
            if status in REDIRECT_STATUSES and location:
                if len(redirects) >= max_redirects:
                    raise FetchBlocked(
                        "TOO_MANY_REDIRECTS",
                        f"More than {max_redirects} redirects were returned; stopping.",
                    )
                next_url = urljoin(current_url, location)
                try:
                    next_scheme = (urlsplit(next_url).scheme or "").lower()
                except ValueError:
                    raise FetchBlocked(
                        "SCHEME_UNSUPPORTED",
                        "A redirect target could not be parsed as a URL.",
                    ) from None
                current_scheme = (urlsplit(current_url).scheme or "").lower()
                if current_scheme == "https" and next_scheme == "http":
                    # Downgrades are only allowed towards public hosts.
                    if _is_local_target(next_url):
                        raise FetchBlocked(
                            "SSRF_PRIVATE_ADDRESS",
                            "Refusing an HTTPS-to-HTTP redirect towards a private or local host.",
                        )
                    limitations.append(
                        "Redirect downgraded the connection from HTTPS to HTTP for a public host."
                    )
                redirects.append(next_url)
                current_url = next_url
                continue
            if status in REDIRECT_STATUSES:
                limitations.append(
                    "Redirect response had no Location header; treated as the final response."
                )
            break

    if redirects:
        limitations.append(f"Followed {len(redirects)} redirect(s).")
    if status >= 400:
        raise FetchBlocked("HTTP_ERROR", f"The server returned HTTP {status}.")

    content_type_header = headers.get("content-type", "")
    mime = content_type_header.split(";")[0].strip().lower()
    if mime not in ALLOWED_CONTENT_TYPES:
        if not content_type_header:
            raise FetchBlocked(
                "MIME_UNSUPPORTED",
                "The response has no Content-Type header; a text content type is required.",
            )
        raise FetchBlocked(
            "MIME_UNSUPPORTED",
            f"Content type '{mime[:100]}' is not supported for page fetch; expected "
            "HTML, XHTML, XML, plain text or Markdown.",
        )

    body_text = _decode_body(content_type_header, body)
    title: str | None = None
    canonical_url: str | None = None
    robots_meta: str | None = None
    if mime in HTML_CONTENT_TYPES:
        try:
            title, canonical_url, robots_meta = _html_metadata(body_text, final_url)
        except Exception:
            # Metadata extraction is best-effort; it must never fail a fetch.
            title, canonical_url, robots_meta = None, None, None

    return FetchResult(
        url=url,
        final_url=final_url,
        status=status,
        content_type=content_type_header,
        body_text=body_text,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        canonical_url=canonical_url,
        title=title,
        robots=robots_meta,
        redirects=redirects,
        size_bytes=len(body),
        render_mode="text_only",
        limitations=limitations,
        blocked_reason=None,
    )
