import json
import os
import re
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE, "static")


class TestPwaAssets(unittest.TestCase):
    def test_manifest_is_valid_json_with_required_fields(self):
        with open(os.path.join(STATIC, "manifest.json")) as f:
            manifest = json.load(f)
        for key in ("name", "short_name", "start_url", "display", "icons"):
            self.assertIn(key, manifest)

    def test_every_manifest_icon_exists_on_disk(self):
        with open(os.path.join(STATIC, "manifest.json")) as f:
            manifest = json.load(f)
        for icon in manifest["icons"]:
            path = os.path.join(BASE, icon["src"].lstrip("/"))
            self.assertTrue(os.path.exists(path), f"manifest references missing icon {icon['src']}")

    def test_every_service_worker_shell_asset_that_is_static_exists(self):
        """
        A service worker that precaches a file that doesn't exist makes
        cache.addAll() reject, so the whole install silently fails - this
        would break offline shell caching with no visible error.
        """
        with open(os.path.join(STATIC, "service-worker.js")) as f:
            src = f.read()
        block = re.search(r"SHELL_ASSETS\s*=\s*\[(.*?)\]", src, re.S).group(1)
        assets = re.findall(r'"([^"]+)"', block)
        self.assertGreater(len(assets), 0)
        for asset in assets:
            if asset.startswith("/static/"):
                path = os.path.join(BASE, asset.lstrip("/"))
                self.assertTrue(os.path.exists(path), f"service worker precaches missing file {asset}")

    def test_service_worker_never_intercepts_api_or_auth(self):
        with open(os.path.join(STATIC, "service-worker.js")) as f:
            src = f.read()
        self.assertIn('"/api/"', src)
        self.assertIn('"/auth/"', src)

    def test_native_shell_does_not_hardcode_a_deployment_url(self):
        with open(os.path.join(BASE, "native", "capacitor.config.ts")) as f:
            src = f.read()
        self.assertIn("process.env.SMART_BETHG_URL", src)
        # The server URL must come from the env-derived variable, never a
        # string literal (comments/examples mentioning a hostname are fine).
        self.assertNotRegex(src, r'url\s*:\s*["\']https?://')
        self.assertRegex(src, r"server\s*:\s*\{[^}]*\burl\b")


if __name__ == "__main__":
    unittest.main()
