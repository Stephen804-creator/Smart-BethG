"""Network tool with SSRF checks, bounded time, and bounded response size."""
import ipaddress
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from execution.execution_engine import ExecutionPermit

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 30


def _validate_url(url):
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("URL is missing or too long.")
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are allowed.")
    if not parts.hostname or parts.username or parts.password:
        raise ValueError("URL must have a hostname and must not contain embedded credentials.")
    hostname = parts.hostname.rstrip(".").lower()
    if hostname in {"localhost", "metadata.google.internal"} or hostname.endswith((".localhost", ".local", ".internal")):
        raise PermissionError("Requests to local or internal hostnames are blocked.")

    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [literal]
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError("The destination hostname could not be resolved.") from exc
        addresses = []
        for info in infos:
            try:
                addresses.append(ipaddress.ip_address(info[4][0]))
            except ValueError:
                continue

    if not addresses:
        raise ValueError("The destination hostname did not resolve to an IP address.")
    if any(not address.is_global for address in addresses):
        raise PermissionError("Requests to private, loopback, link-local, or reserved IP addresses are blocked.")
    return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path or "/", parts.query, ""))


class _ValidatedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NetworkTool:
    def get(self, permit: ExecutionPermit, url: str, timeout=15):
        if permit.action != "network.request":
            raise PermissionError("Invalid execution permit.")
        safe_url = _validate_url(url)
        timeout = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))
        # Do not silently inherit environment proxy settings in a way that
        # could route a checked URL to an unvalidated internal destination.
        opener = build_opener(ProxyHandler({}), _ValidatedRedirectHandler())
        request = Request(
            safe_url,
            headers={
                "User-Agent": "SmartBethG/1.0",
                "Accept": "text/plain, text/html, application/json, application/xml, */*;q=0.1",
            },
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                content = response.read(MAX_RESPONSE_BYTES + 1)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise ValueError("Network response exceeded the configured 2 MiB limit.")
                return content.decode("utf-8", errors="replace")
        except HTTPError:
            raise
        except URLError as exc:
            raise ValueError("The requested URL could not be fetched.") from exc
