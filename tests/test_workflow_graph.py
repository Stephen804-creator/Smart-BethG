import copy
import unittest

from services.workflow_graph import WorkflowGraphValidator


def valid_graph():
    return {
        "format": "smartbethg.workflow.graph",
        "schema_version": "1.0",
        "trigger": {
            "type": "manual",
            "version": 1,
            "input_schema": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
            },
        },
        "nodes": [
            {
                "id": "research-topic",
                "type": "research",
                "version": 1,
                "config": {},
                "inputs": {
                    "topic": {
                        "source": {"node_id": "$trigger", "output": "topic"},
                        "type": "string",
                    }
                },
                "outputs": {"result": {"type": "object"}},
            },
            {
                "id": "finish",
                "type": "end",
                "version": 1,
                "config": {},
                "inputs": {},
                "outputs": {},
            },
        ],
        "edges": [
            {
                "id": "start-research",
                "from_node_id": "$trigger",
                "from_output": "topic",
                "to_node_id": "research-topic",
                "to_input": "topic",
            },
            {
                "id": "research-finish",
                "from_node_id": "research-topic",
                "to_node_id": "finish",
            },
        ],
    }


class TestWorkflowGraphValidator(unittest.TestCase):
    def test_accepts_valid_typed_graph(self):
        graph = valid_graph()
        self.assertEqual(WorkflowGraphValidator.validate(graph), graph)

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
