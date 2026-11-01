"""Ensure every registered single-file runtime has a build and smoke-test asset."""
import re
import unittest
from pathlib import Path

from services.runtime_registry import RUNTIME_DEFINITIONS


ROOT = Path(__file__).resolve().parents[1]


class TestRuntimeImageAssets(unittest.TestCase):
    def test_every_registered_runtime_has_a_dockerfile(self):
        for runtime_id in RUNTIME_DEFINITIONS:
            with self.subTest(runtime_id=runtime_id):
                dockerfile = ROOT / "execution-images" / runtime_id / "Dockerfile"
                self.assertTrue(dockerfile.is_file(), f"Missing {dockerfile}")
                content = dockerfile.read_text(encoding="utf-8")
                self.assertIn("USER 65534:65534", content)
                self.assertIn("ENTRYPOINT []", content)
                self.assertNotIn("USER root", content)

    def test_every_registered_runtime_has_a_smoke_program(self):
        source = (ROOT / "scripts" / "verify_runtime_image.py").read_text(encoding="utf-8")
        sample_block = source.split("SAMPLES = {", 1)[1].split("\n}", 1)[0]
        sample_ids = set(re.findall(r'^\s*"([a-z0-9_-]+)":', sample_block, re.MULTILINE))
        self.assertEqual(sample_ids, set(RUNTIME_DEFINITIONS))

    def test_workflow_builds_and_verifies_every_registered_runtime(self):
        workflow = (ROOT / ".github" / "workflows" / "runtime-images.yml").read_text(encoding="utf-8")
        for runtime_id in RUNTIME_DEFINITIONS:
            with self.subTest(runtime_id=runtime_id):
                self.assertIn(f"runtime: {runtime_id}", workflow)
                self.assertIn(f"execution-images/{runtime_id}/Dockerfile", workflow)
        self.assertIn("publish_images", workflow)
        self.assertIn("provenance: true", workflow)
        self.assertIn("sbom: true", workflow)
