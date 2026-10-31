"""Tests for the unified software/hardware capability catalog."""
import unittest

from services.engineering_capability_registry import (
    CAPABILITIES,
    list_engineering_capabilities,
)


class TestEngineeringCapabilityRegistry(unittest.TestCase):
    def test_registry_exposes_one_catalog_for_software_hardware_and_embedded(self):
        result = list_engineering_capabilities()
        domains = {item["domain"] for item in result["capabilities"]}
        self.assertTrue({"software", "hardware", "embedded", "cross_domain"} <= domains)
        self.assertEqual(result["registry_version"], 1)

    def test_hardware_targets_are_not_misclassified_as_languages_or_runtimes(self):
        by_id = {item.id: item for item in CAPABILITIES}
        self.assertEqual(by_id["esp32"].category, "hardware_target")
        self.assertEqual(by_id["arduino-uno"].category, "hardware_target")
        self.assertEqual(by_id["verilog"].category, "hardware_description_language")
        self.assertEqual(by_id["kicad"].category, "engineering_tool")
        self.assertEqual(by_id["python"].category, "language_runtime")
        self.assertEqual(by_id["express"].category, "framework_profile")
        self.assertEqual(by_id["esp32"].domain, "hardware")

    def test_only_python_is_described_as_implemented_execution_runtime(self):
        result = list_engineering_capabilities()
        implemented = {
            item["id"] for item in result["capabilities"]
            if item["category"] == "language_runtime" and item["status"] == "implemented"
        }
        self.assertEqual(implemented, {"python"})

    def test_external_tools_are_not_claimed_as_connected(self):
        result = list_engineering_capabilities()
        by_id = {item["id"]: item for item in result["capabilities"]}
        for tool_id in ("wokwi", "kicad", "easyeda"):
            self.assertEqual(by_id[tool_id]["status"], "integration_candidate")
            self.assertEqual(by_id[tool_id]["integration"], "external_connector" if tool_id != "kicad" else "local_agent_or_remote_tool")

    def test_domain_filter_includes_cross_domain_execution_profiles(self):
        result = list_engineering_capabilities("hardware")
        domains = {item["domain"] for item in result["capabilities"]}
        self.assertEqual(domains, {"hardware", "embedded", "cross_domain"})
        ids = {item["id"] for item in result["capabilities"]}
        self.assertIn("cloud-sandbox", ids)
        self.assertIn("esp-idf", ids)

    def test_invalid_domain_is_rejected(self):
        with self.assertRaises(ValueError):
            list_engineering_capabilities("arbitrary")

    def test_registry_does_not_expose_runtime_images_or_secrets(self):
        result = list_engineering_capabilities()
        serialized = repr(result).lower()
        self.assertNotIn("sha256:", serialized)
        self.assertNotIn("docker_allowed_images", serialized)
        self.assertNotIn("api_key", serialized)

    def test_workspace_modes_keep_hardware_and_combined_as_planned(self):
        result = list_engineering_capabilities()
        statuses = {item["id"]: item["status"] for item in result["workspace_types"]}
        self.assertEqual(statuses["hardware"], "planned")
        self.assertEqual(statuses["software_hardware"], "planned")


if __name__ == "__main__":
    unittest.main()
