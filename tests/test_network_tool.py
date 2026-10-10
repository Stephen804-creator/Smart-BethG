import unittest
from unittest.mock import patch

from execution.execution_engine import ExecutionPermit
from network.network_tool import NetworkTool, _validate_url


class TestNetworkToolSafety(unittest.TestCase):
    def test_rejects_non_http_schemes(self):
        with self.assertRaises(ValueError):
            _validate_url("file:///etc/passwd")

    def test_rejects_loopback_and_private_addresses(self):
        for url in ("http://127.0.0.1/", "http://10.0.0.8/", "http://[::1]/"):
            with self.subTest(url=url):
                with self.assertRaises(PermissionError):
                    _validate_url(url)

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(ValueError):
            _validate_url("https://user:password@example.com/")

    @patch("network.network_tool.socket.getaddrinfo")
    def test_rejects_public_hostname_resolving_to_private_ip(self, resolve):
        resolve.return_value = [
            (2, 1, 6, "", ("192.168.1.10", 443))
        ]
        with self.assertRaises(PermissionError):
            _validate_url("https://example.test/")

    def test_requires_valid_execution_permit(self):
        with self.assertRaises(PermissionError):
            NetworkTool().get(
                ExecutionPermit("id", "filesystem.read", "workspace:x", "low"),
                "https://example.com",
            )


if __name__ == "__main__":
    unittest.main()
