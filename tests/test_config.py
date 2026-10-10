import os
import subprocess
import sys
import unittest


class TestEnvironmentConfiguration(unittest.TestCase):
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
