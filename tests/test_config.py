import os
import subprocess
import sys
import unittest


class TestEnvironmentConfiguration(unittest.TestCase):
    def test_production_registration_defaults_closed(self):
        env = os.environ.copy()
        env["SMART_BETHG_ENV"] = "production"
        env["DATABASE_URL"] = "postgresql://example:example@localhost:5432/smartbethg"
        env["SMART_BETHG_SECRET_KEY"] = "test-only-secret"
        env["SMART_BETHG_SESSION_HTTPS_ONLY"] = "true"
        env.pop("SMART_BETHG_REGISTRATION_OPEN", None)
        result = subprocess.run(
            [sys.executable, "-c", "import config; print(config.REGISTRATION_OPEN)"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_production_registration_requires_explicit_opt_in(self):
        env = os.environ.copy()
        env["SMART_BETHG_ENV"] = "production"
        env["DATABASE_URL"] = "postgresql://example:example@localhost:5432/smartbethg"
        env["SMART_BETHG_SECRET_KEY"] = "test-only-secret"
        env["SMART_BETHG_SESSION_HTTPS_ONLY"] = "true"
        env["SMART_BETHG_REGISTRATION_OPEN"] = "true"
        result = subprocess.run(
            [sys.executable, "-c", "import config; print(config.REGISTRATION_OPEN)"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")

    def test_unknown_environment_fails_closed(self):
        env = os.environ.copy()
        env["SMART_BETHG_ENV"] = "prod"
        env.pop("SMART_BETHG_SECRET_KEY", None)
        result = subprocess.run(
            [sys.executable, "-c", "import config"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SMART_BETHG_ENV must be one of", result.stderr)


if __name__ == "__main__":
    unittest.main()
