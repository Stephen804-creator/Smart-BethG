"""SSRF-resistant HTTP(S) fetcher with DNS pinning and bounded responses."""
import http.client
import ipaddress
import socket
import ssl
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit

from execution.execution_engine import ExecutionPermit

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 30
MAX_REDIRECTS = 5
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def _validated_destination(url):
    """Validate a URL and return its canonical URL plus one vetted, pinned IP."""
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("URL is missing or too long.")
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are allowed.")
    if not parts.hostname or parts.username or parts.password:
        raise ValueError("URL must have a hostname and must not contain embedded credentials.")
    hostname = parts.hostname.rstrip(".").lower()
    if hostname in {"localhost", "metadata.google.internal"} or hostname.endswith(
        (".localhost", ".local", ".internal")
    ):
        raise PermissionError("Requests to local or internal hostnames are blocked.")

    port = parts.port or (443 if scheme == "https" else 80)
    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [literal]
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError("The destination hostname could not be resolved.") from exc
        addresses = []
        for info in infos:
            try:
                addresses.append(ipaddress.ip_address(info[4][0].split("%", 1)[0]))
            except ValueError:
                continue

    if not addresses:
        raise ValueError("The destination hostname did not resolve to an IP address.")
    # Reject mixed public/private answers rather than picking only the public
    # answer. The actual TCP connection below uses a vetted address directly,
    # so the HTTP stack cannot resolve the hostname a second time.
    if any(not address.is_global for address in addresses):
        raise PermissionError("Requests to private, loopback, link-local, or reserved IP addresses are blocked.")

    authority_host = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    authority = authority_host if port == default_port else f"{authority_host}:{port}"
    canonical = urlunsplit((scheme, authority, parts.path or "/", parts.query, ""))
    return canonical, hostname, port, str(addresses[0])


def _validate_url(url):
    """Compatibility validator used by callers and security tests."""
    return _validated_destination(url)[0]


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, hostname, port, pinned_ip, timeout):
        super().__init__(hostname, port=port, timeout=timeout)
        self.pinned_ip = pinned_ip

    def connect(self):
        self.sock = socket.create_connection(
            (self.pinned_ip, self.port), self.timeout, self.source_address
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname, port, pinned_ip, timeout):
        super().__init__(hostname, port=port, timeout=timeout, context=ssl.create_default_context())
        self.pinned_ip = pinned_ip

    def connect(self):
        raw_socket = socket.create_connection(
            (self.pinned_ip, self.port), self.timeout, self.source_address
        )
        try:
            # TLS verifies the original hostname even though TCP is pinned to
            # the already-vetted IP address.
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except Exception:
            raw_socket.close()
            raise


class NetworkTool:
    def get(self, permit: ExecutionPermit, url: str, timeout=15):
        if permit.action != "network.request":
            raise PermissionError("Invalid execution permit.")
        timeout = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))
        current_url = url

        for redirect_count in range(MAX_REDIRECTS + 1):
            safe_url, hostname, port, pinned_ip = _validated_destination(current_url)
            parts = urlsplit(safe_url)
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection_type = _PinnedHTTPSConnection if parts.scheme == "https" else _PinnedHTTPConnection
            connection = connection_type(hostname, port, pinned_ip, timeout)
            authority_host = f"[{hostname}]" if ":" in hostname else hostname
            default_port = 443 if parts.scheme == "https" else 80
            host_header = authority_host if port == default_port else f"{authority_host}:{port}"

            try:
                connection.request(
                    "GET",
                    path,
                    headers={
                        "Host": host_header,
                        "User-Agent": "SmartBethG/1.0",
                        "Accept": "text/plain, text/html, application/json, application/xml, */*;q=0.1",
                        "Connection": "close",
                    },
                )
                response = connection.getresponse()
                if response.status in REDIRECT_STATUSES and response.getheader("Location"):
                    location = response.getheader("Location")
                    response.read(MAX_RESPONSE_BYTES + 1)
                    response.close()
                    connection.close()
                    if redirect_count >= MAX_REDIRECTS:
                        raise ValueError("The destination exceeded the configured redirect limit.")
                    current_url = urljoin(safe_url, location)
                    continue

                content = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
                reason = response.reason
                headers = response.headers
                response.close()
                if len(content) > MAX_RESPONSE_BYTES:
                    raise ValueError("Network response exceeded the configured 2 MiB limit.")
                if status >= 400:
                    raise HTTPError(safe_url, status, reason, headers, None)
                return content.decode("utf-8", errors="replace")
            finally:
                connection.close()

        raise ValueError("The destination exceeded the configured redirect limit.")
