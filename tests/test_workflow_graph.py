import copy
import json
import unittest
from pathlib import Path

from services.workflow_graph import WorkflowGraphValidator


def load_fixture(name):
    fixture_path = Path(__file__).parent / "fixtures" / "workflow_graphs" / name
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def valid_graph():
    return load_fixture("valid_linear.json")

class TestWorkflowGraphValidator(unittest.TestCase):

    def test_reusable_invalid_fixtures_are_rejected(self):
        invalid_fixtures = {
            "invalid_cycle.json": "contains a cycle",
            "invalid_unreachable.json": "Unreachable",
            "invalid_type_mismatch.json": "incompatible",
        }
        for fixture_name, message in invalid_fixtures.items():
            with self.subTest(fixture=fixture_name):
                with self.assertRaisesRegex(ValueError, message):
                    WorkflowGraphValidator.validate(load_fixture(fixture_name))

    def test_accepts_valid_typed_graph(self):
        graph = valid_graph()
        self.assertEqual(WorkflowGraphValidator.validate(graph), graph)


    def test_rejects_non_standard_nan_values(self):
        graph = valid_graph()
        graph["nodes"][0]["config"] = {"threshold": float("nan")}
        with self.assertRaisesRegex(ValueError, "JSON-compatible"):
            WorkflowGraphValidator.validate(graph)

    def test_does_not_mutate_input(self):
        graph = valid_graph()
        original = copy.deepcopy(graph)
        WorkflowGraphValidator.validate(graph)
        self.assertEqual(graph, original)

    def test_rejects_duplicate_node_ids(self):
        graph = valid_graph()
        graph["nodes"].append(copy.deepcopy(graph["nodes"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate node ID"):
            WorkflowGraphValidator.validate(graph)


    def test_rejects_node_config_field_with_wrong_type(self):
        graph = WorkflowGraphValidator.from_legacy_steps([
            {"id": "research-node", "type": "research", "config": {"query": "valid"}},
        ])
        graph["nodes"][0]["config"]["query"] = ["not", "text"]
        with self.assertRaisesRegex(ValueError, "config field 'query' must be string"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_non_string_items_in_node_config_array(self):
        graph = WorkflowGraphValidator.from_legacy_steps([
            {"id": "research-node", "type": "research",
             "config": {"topic": "cloud", "source_urls": ["https://example.com"]}},
        ])
        graph["nodes"][0]["config"]["source_urls"].append(42)
        with self.assertRaisesRegex(ValueError, "source_urls must be array"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_unsupported_condition_operator_in_node_config(self):
        graph = WorkflowGraphValidator.from_legacy_steps([
            {"id": "research-node", "type": "research", "config": {"topic": "cloud"}},
            {"id": "condition-node", "type": "condition",
             "config": {"source_step_id": "research-node", "path": "result.score",
                        "operator": "equals"}},
        ])
        next(node for node in graph["nodes"] if node["id"] == "condition-node")["config"]["operator"] = "execute_anything"
        with self.assertRaisesRegex(ValueError, "unsupported condition operator"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_unknown_node_type(self):
        graph = valid_graph()
        graph["nodes"][0]["type"] = "shell"
        with self.assertRaisesRegex(ValueError, "unsupported type"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_unknown_edge_target(self):
        graph = valid_graph()
        graph["edges"][0]["to_node_id"] = "missing-node"
        with self.assertRaisesRegex(ValueError, "unknown target"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_incompatible_input_mapping(self):
        graph = valid_graph()
        graph["nodes"][0]["inputs"]["topic"]["type"] = "boolean"
        with self.assertRaisesRegex(ValueError, "incompatible"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_unmapped_input(self):
        graph = valid_graph()
        graph["nodes"][0]["inputs"]["unused"] = {
            "source": {"node_id": "$trigger", "output": "topic"},
            "type": "string",
        }
        with self.assertRaisesRegex(ValueError, "no matching graph edge"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_cycles(self):
        graph = valid_graph()
        graph["edges"].append({
            "id": "cycle-back",
            "from_node_id": "finish",
            "to_node_id": "research-topic",
        })
        with self.assertRaisesRegex(ValueError, "contains a cycle"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_unreachable_nodes(self):
        graph = valid_graph()
        graph["nodes"].append({
            "id": "orphan",
            "type": "end",
            "version": 1,
            "config": {},
            "inputs": {},
            "outputs": {},
        })
        with self.assertRaisesRegex(ValueError, "Unreachable"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_nodes_without_end_path(self):
        graph = valid_graph()
        graph["edges"] = graph["edges"][:1]
        with self.assertRaisesRegex(ValueError, "no path to a downstream"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_unknown_schema_version(self):
        graph = valid_graph()
        graph["schema_version"] = "2.0"
        with self.assertRaisesRegex(ValueError, "schema version"):
            WorkflowGraphValidator.validate(graph)


    def test_rejects_non_object_manual_trigger_schema(self):
        graph = valid_graph()
        graph["trigger"]["input_schema"] = {"type": "string"}
        with self.assertRaisesRegex(ValueError, "must be an object"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_invalid_schema_type_without_crashing(self):
        graph = valid_graph()
        graph["nodes"][0]["outputs"] = {"result": {"type": ["object"]}}
        with self.assertRaisesRegex(ValueError, "output contract"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_non_string_edge_endpoint_without_crashing(self):
        graph = valid_graph()
        graph["edges"][0]["to_node_id"] = {"invalid": "node"}
        with self.assertRaisesRegex(ValueError, "unknown target"):
            WorkflowGraphValidator.validate(graph)

    def test_rejects_node_version_not_integer(self):
        graph = valid_graph()
        graph["nodes"][0]["version"] = 1.0
        with self.assertRaisesRegex(ValueError, "unsupported node version"):
            WorkflowGraphValidator.validate(graph)

    def test_converts_legacy_sequential_steps(self):
        graph = WorkflowGraphValidator.from_legacy_steps([
            {"id": "research-1", "type": "research", "config": {"topic": "cloud"}},
            {"id": "artifact-1", "type": "artifact", "config": {"name": "report"}},
        ])
        self.assertEqual([node["id"] for node in graph["nodes"]],
                         ["research-1", "artifact-1", "workflow-end"])
        self.assertEqual(len(graph["edges"]), 3)
        self.assertEqual(graph["edges"][0]["from_node_id"], "$trigger")
        self.assertEqual(graph["edges"][-1]["to_node_id"], "workflow-end")


    def test_legacy_graph_conversion_round_trips_without_loss(self):
        steps = [
            {"id": "research-1", "type": "research", "config": {"topic": "cloud"}},
            {"id": "artifact-1", "type": "artifact", "config": {"name": "report"}},
        ]
        graph = WorkflowGraphValidator.from_legacy_steps(steps)
        self.assertEqual(WorkflowGraphValidator.to_legacy_steps(graph), steps)

    def test_graph_to_legacy_rejects_data_mappings(self):
        with self.assertRaisesRegex(ValueError, "data mappings"):
            WorkflowGraphValidator.to_legacy_steps(valid_graph())

    def test_graph_to_legacy_rejects_branching_graphs(self):
        graph = WorkflowGraphValidator.from_legacy_steps([
            {"id": "research-1", "type": "research", "config": {}},
        ])
        graph["nodes"].insert(1, {
            "id": "social",
            "type": "social_content",
            "version": 1,
            "config": {},
            "inputs": {},
            "outputs": {"result": {"type": "object"}},
        })
        graph["edges"] = [
            {"id": "start", "from_node_id": "$trigger", "to_node_id": "research-1"},
            {"id": "research-end", "from_node_id": "research-1", "to_node_id": "workflow-end"},
            {"id": "research-social", "from_node_id": "research-1", "to_node_id": "social"},
            {"id": "social-end", "from_node_id": "social", "to_node_id": "workflow-end"},
        ]
        with self.assertRaisesRegex(ValueError, "Branching graphs"):
            WorkflowGraphValidator.to_legacy_steps(graph)

    def test_legacy_adapter_preserves_existing_condition_configuration(self):
        config = {
            "source_step_id": "research-1",
            "path": "result.score",
            "operator": "gte",
            "value": 0.8,
        }
        graph = WorkflowGraphValidator.from_legacy_steps([
            {"id": "research-1", "type": "research", "config": {"topic": "cloud"}},
            {"id": "check-score", "type": "condition", "config": config},
        ])
        condition = next(node for node in graph["nodes"] if node["id"] == "check-score")
        self.assertEqual(condition["config"], config)
        self.assertEqual(condition["outputs"]["matched"], {"type": "boolean"})


if __name__ == "__main__":
    unittest.main()
