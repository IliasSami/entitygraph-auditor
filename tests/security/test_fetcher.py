"""Security tests for the SSRF-guarded HTTP fetcher (PRD FR-23, FR-24, §18).

Every test runs fully offline.  Outbound requests are served by an
``httpx.MockTransport`` handed to :func:`fetch_url` through its ``transport``
keyword, and DNS is answered by a deterministic local resolver installed over
``socket.getaddrinfo`` — no socket is ever opened, so the suite is fast and
reproducible in CI without network access.

Covered threat-model items (§18):

* SSRF by scheme, private/loopback/link-local/metadata IPs, alternate integer
  /hex/octal address encodings, embedded IPv4 inside IPv6, and hostnames.
* SSRF by redirect (each hop re-validated) and by DNS answers that change
  between lookups (re-validation runs again inside the guarded transport).
* Resource exhaustion: oversized bodies, redirect loops, timeouts.
* robots.txt policy (FR-23) and the content-type allowlist with JSON refused
  (FR-24).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Callable, Coroutine, Iterator

import httpx
import pytest
from ega_api.services import fetcher as fetcher_module
from ega_api.services.fetcher import (
    TEXT_ONLY_NOTE,
    FetchBlocked,
    FetchResult,
    clear_robots_cache,
    fetch_url,
)

# --------------------------------------------------------------------------- #
# Offline plumbing
# --------------------------------------------------------------------------- #

#: Address returned for every non-literal hostname unless ``RESOLVE`` overrides it.
PUBLIC_IP = "93.184.216.34"

#: Per-test DNS answers: host -> list of IPs, or an exception to raise.
RESOLVE: dict[str, list[str] | BaseException] = {}


def _fake_getaddrinfo(host: str, port: int | None, *args: object, **kwargs: object):
    """Deterministic stand-in for ``socket.getaddrinfo`` (never hits the network)."""
    override = RESOLVE.get(host)
    if isinstance(override, BaseException):
        raise override
    if override is None:
        try:
            ipaddress.ip_address(host)
            addresses = [host]
        except ValueError:
            addresses = [PUBLIC_IP]
    else:
        addresses = override
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 0))
        for address in addresses
    ]


@pytest.fixture(autouse=True)
def _offline_dns(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate DNS and the module-level robots cache between tests."""
    RESOLVE.clear()
    clear_robots_cache()
    monkeypatch.setattr(fetcher_module.socket, "getaddrinfo", _fake_getaddrinfo)
    yield
    RESOLVE.clear()
    clear_robots_cache()


def run(coro: Coroutine[object, object, FetchResult]) -> FetchResult:
    """Run a coroutine to completion on a fresh, closed event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


Handler = Callable[[httpx.Request], httpx.Response]


def make_transport(handler: Handler) -> httpx.MockTransport:
    """Wrap a sync handler in a mock transport (no network access)."""
    return httpx.MockTransport(handler)


def fetch(url: str, handler: Handler, **kwargs: object) -> Coroutine[object, object, FetchResult]:
    """``fetch_url`` against a mock transport."""
    kwargs.setdefault("transport", make_transport(handler))
    return fetch_url(url, **kwargs)  # type: ignore[arg-type]


def robots_allow(request: httpx.Request) -> httpx.Response | None:
    """Shared handler fragment: serve a permissive robots.txt, else ``None``."""
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    return None


def doc_handler(
    content_type: str = "text/html", body: str = "<html>ok</html>"
) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return robots_allow(request) or httpx.Response(
            200, text=body, headers={"content-type": content_type}
        )

    return handler


# --------------------------------------------------------------------------- #
# Blocked targets (FR-23 / FR-24 / §18)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",
        "http://127.0.0.9:8080/x",
        "http://[::1]/x",
        "http://10.1.2.3/x",
        "http://192.168.0.1/x",
        "http://172.16.0.1/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://100.64.0.1/x",
        "http://0.0.0.0/x",
        "http://224.0.0.1/x",
        "http://240.0.0.1/x",
        # Alternate encodings of 127.0.0.1 (FR-24 "alternate IP encodings").
        "http://2130706433/x",
        "http://0x7f000001/x",
        "http://0177.0.0.1/x",
        "http://127.1/x",
        # Embedded IPv4 inside IPv6.
        "http://[::ffff:127.0.0.1]/x",
        "http://[::ffff:169.254.169.254]/x",
        "http://[2002:7f00:1::]/x",
        # Hostnames.
        "http://localhost/x",
        "http://foo.localhost/x",
        "http://printer.local/x",
    ],
)
def test_private_and_reserved_targets_are_blocked(url: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may leave the process for a blocked target")

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch(url, handler))
    assert excinfo.value.code == "SSRF_PRIVATE_ADDRESS"
    assert excinfo.value.args and excinfo.value.args[0]


def test_hostname_resolving_to_a_private_address_is_blocked() -> None:
    RESOLVE["internal.example"] = ["10.0.0.5", PUBLIC_IP]  # one bad answer is enough

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://internal.example/x", lambda request: httpx.Response(200)))
    assert excinfo.value.code == "SSRF_PRIVATE_ADDRESS"


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://example.com/x", "gopher://example.com/x"]
)
def test_non_http_scheme_is_blocked(url: str) -> None:
    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch(url, lambda request: httpx.Response(200)))
    assert excinfo.value.code == "SSRF_SCHEME"


def test_unsupported_scheme_is_not_silently_ignored() -> None:
    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("bitcoin:1abc", lambda request: httpx.Response(200)))
    assert excinfo.value.code == "SCHEME_UNSUPPORTED"


def test_redirect_to_a_dangerous_scheme_is_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        return httpx.Response(302, headers={"location": "file:///etc/passwd"})

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/start", handler))
    assert excinfo.value.code == "SSRF_SCHEME"


# --------------------------------------------------------------------------- #
# allow_private (admin/dev opt-in, FR-24)
# --------------------------------------------------------------------------- #


def test_allow_private_permits_a_loopback_target() -> None:
    result = run(
        fetch("http://127.0.0.1:9000/local", doc_handler("text/plain", "hello"), allow_private=True)
    )
    assert isinstance(result, FetchResult)
    assert result.status == 200
    assert result.body_text == "hello"
    assert any("skipped for local/dev target" in note for note in result.limitations)


def test_allow_private_does_not_lift_the_scheme_allowlist() -> None:
    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("file:///etc/passwd", lambda request: httpx.Response(200), allow_private=True))
    assert excinfo.value.code == "SSRF_SCHEME"


# --------------------------------------------------------------------------- #
# Redirects (each hop re-validated)
# --------------------------------------------------------------------------- #


def test_redirect_to_a_metadata_endpoint_is_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        return httpx.Response(
            302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
        )

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/start", handler))
    assert excinfo.value.code == "SSRF_PRIVATE_ADDRESS"


def test_redirect_to_loopback_is_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        return httpx.Response(301, headers={"location": "http://127.0.0.1:1/"})

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/start", handler))
    assert excinfo.value.code == "SSRF_PRIVATE_ADDRESS"


def test_too_many_redirects_is_capped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        step = int(request.url.path.rsplit("n", 1)[-1])
        return httpx.Response(302, headers={"location": f"http://example.com/n{step + 1}"})

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/n0", handler))
    assert excinfo.value.code == "TOO_MANY_REDIRECTS"


def test_public_redirect_chain_is_followed_and_recorded() -> None:
    targets = {"/a": "/b", "/b": "/c"}

    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        if request.url.path in targets:
            return httpx.Response(
                302, headers={"location": f"http://example.com{targets[request.url.path]}"}
            )
        return httpx.Response(200, text="done", headers={"content-type": "text/plain"})

    result = run(fetch("http://example.com/a", handler))
    assert result.redirects == ["http://example.com/b", "http://example.com/c"]
    assert result.final_url == "http://example.com/c"
    assert result.status == 200
    assert result.body_text == "done"


def test_https_to_http_downgrade_of_a_public_host_is_disclosed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        if request.url.scheme == "https":
            return httpx.Response(302, headers={"location": "http://example.com/insecure"})
        return httpx.Response(200, text="ok", headers={"content-type": "text/plain"})

    result = run(fetch("https://example.com/secure", handler))
    assert result.status == 200
    assert result.final_url == "http://example.com/insecure"
    assert any("downgraded" in note for note in result.limitations)


def test_dns_rebinding_after_the_first_lookup_is_revalidated() -> None:
    """A DNS answer that flips to loopback after the first request is refused."""
    RESOLVE["rebind.example"] = [PUBLIC_IP]
    page_requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        page_requests.append(request.url.path)
        RESOLVE["rebind.example"] = ["127.0.0.1"]  # attacker flips the record
        return httpx.Response(302, headers={"location": "http://rebind.example/next"})

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://rebind.example/x", handler))
    assert excinfo.value.code == "SSRF_PRIVATE_ADDRESS"
    assert page_requests == ["/x"]


# --------------------------------------------------------------------------- #
# Resource limits (FR-24)
# --------------------------------------------------------------------------- #


def test_oversized_body_is_aborted() -> None:
    payload = b"A" * (6 * 1024 * 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        return httpx.Response(200, content=payload, headers={"content-type": "text/html"})

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/big", handler, max_bytes=5 * 1024 * 1024))
    assert excinfo.value.code == "TOO_LARGE"


def test_body_at_the_limit_is_accepted() -> None:
    payload = b"B" * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        return httpx.Response(200, content=payload, headers={"content-type": "text/html"})

    result = run(fetch("http://example.com/ok", handler, max_bytes=1024))
    assert result.size_bytes == 1024
    assert result.body_text == "B" * 1024


def test_timeout_maps_to_the_timeout_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out", request=request)

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/slow", handler, timeout_s=0.2))
    assert excinfo.value.code == "TIMEOUT"


def test_dns_failure_maps_to_the_dns_failure_code() -> None:
    RESOLVE["no-such-host.invalid"] = socket.gaierror("name or service not known")

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://no-such-host.invalid/x", lambda request: httpx.Response(200)))
    assert excinfo.value.code == "DNS_FAILURE"


def test_http_error_status_is_surfaced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        return httpx.Response(503, text="unavailable")

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/error", handler))
    assert excinfo.value.code == "HTTP_ERROR"
    assert "503" in str(excinfo.value)


@pytest.mark.parametrize("timeout_s,max_bytes,max_redirects", [(0, 10, 5), (1, 0, 5), (1, 10, -1)])
def test_invalid_limits_raise_value_error(
    timeout_s: float, max_bytes: int, max_redirects: int
) -> None:
    with pytest.raises(ValueError):
        run(
            fetch(
                "http://example.com/",
                lambda request: httpx.Response(200),
                timeout_s=timeout_s,
                max_bytes=max_bytes,
                max_redirects=max_redirects,
            )
        )


# --------------------------------------------------------------------------- #
# Content-type allowlist (FR-24)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "content_type",
    ["application/pdf", "application/octet-stream", "image/png", "video/mp4"],
)
def test_disallowed_content_types_are_refused(content_type: str) -> None:
    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/file", doc_handler(content_type)))
    assert excinfo.value.code == "MIME_UNSUPPORTED"


def test_json_content_type_is_rejected() -> None:
    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/data.json", doc_handler("application/json")))
    assert excinfo.value.code == "MIME_UNSUPPORTED"


def test_a_missing_content_type_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            return seen
        return httpx.Response(200, content=b"bare")

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/bare", handler))
    assert excinfo.value.code == "MIME_UNSUPPORTED"


@pytest.mark.parametrize("content_type", ["text/html", "text/plain", "application/xhtml+xml"])
def test_allowed_content_types_pass(content_type: str) -> None:
    result = run(fetch("http://example.com/doc", doc_handler(content_type)))
    assert isinstance(result, FetchResult)
    assert result.content_type.split(";")[0].strip() == content_type


# --------------------------------------------------------------------------- #
# robots.txt (FR-23)
# --------------------------------------------------------------------------- #


def test_robots_disallow_blocks_the_fetch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, text="secret")

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/private/page", handler))
    assert excinfo.value.code == "ROBOTS_DISALLOWED"


def test_robots_allow_permits_the_fetch_and_is_disclosed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, text="hello", headers={"content-type": "text/plain"})

    result = run(fetch("http://example.com/public/page", handler))
    assert result.status == 200
    assert any("robots.txt" in note for note in result.limitations)


def test_robots_can_be_skipped_by_the_caller() -> None:
    robots_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            robots_calls["n"] += 1
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, text="hello", headers={"content-type": "text/plain"})

    result = run(fetch("http://example.com/blocked-by-robots", handler, respect_robots=False))
    assert result.status == 200
    assert robots_calls["n"] == 0
    assert not any("robots.txt" in note for note in result.limitations)


def test_robots_disallow_is_honoured_across_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /hidden\n")
        return httpx.Response(302, headers={"location": "http://example.com/hidden/x"})

    with pytest.raises(FetchBlocked) as excinfo:
        run(fetch("http://example.com/start", handler))
    assert excinfo.value.code == "ROBOTS_DISALLOWED"


def test_robots_is_fetched_once_per_host() -> None:
    robots_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen = robots_allow(request)
        if seen is not None:
            robots_calls["n"] += 1
            return seen
        return httpx.Response(200, text="ok", headers={"content-type": "text/plain"})

    run(fetch("http://example.com/one", handler))
    run(fetch("http://example.com/two", handler))
    assert robots_calls["n"] == 1


# --------------------------------------------------------------------------- #
# Happy path / honesty
# --------------------------------------------------------------------------- #


def test_successful_fetch_populates_every_field() -> None:
    body = (
        '<html><head><title>Hi</title><link rel="canonical" href="/canon"/>'
        '<meta name="robots" content="noindex"/></head><body>x</body></html>'
    )
    result = run(fetch("http://example.com/page", doc_handler("text/html; charset=utf-8", body)))

    assert isinstance(result, FetchResult)
    assert result.url == "http://example.com/page"
    assert result.final_url == "http://example.com/page"
    assert result.status == 200
    assert result.redirects == []
    assert result.content_type == "text/html; charset=utf-8"
    assert result.body_text == body
    assert result.size_bytes == len(body.encode("utf-8"))
    assert result.title == "Hi"
    assert result.canonical_url == "http://example.com/canon"
    assert result.robots == "noindex"
    assert result.render_mode == "text_only"
    assert result.blocked_reason is None
    assert TEXT_ONLY_NOTE in result.limitations
    assert any("robots.txt" in note for note in result.limitations)
    assert "T" in result.fetched_at


def test_fetch_blocked_carries_a_machine_readable_code() -> None:
    exc = FetchBlocked("SSRF_PRIVATE_ADDRESS", "The URL targets a private address.")
    assert exc.code == "SSRF_PRIVATE_ADDRESS"
    assert str(exc) == "The URL targets a private address."


def test_page_content_is_returned_as_inert_text() -> None:
    payload = "<script>fetch('http://example.com/steal')</script>"
    result = run(fetch("http://example.com/js", doc_handler("text/html", payload)))
    assert result.body_text == payload
    assert result.render_mode == "text_only"
