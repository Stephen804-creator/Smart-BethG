"""Canonical, versioned workflow graph contract.

This module validates definitions only. It does not execute graphs; the existing
sequential executor remains the compatibility runtime until Stage 2.
"""
import copy
import json
import re


FORMAT = "smartbethg.workflow.graph"
SCHEMA_VERSION = "1.0"
MAX_NODES = 50
MAX_EDGES = 100
MAX_DEFINITION_BYTES = 100_000
_NODE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
_SCHEMA_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
_NODE_OUTPUTS = {
    "mission": {"result": {"type": "object"}},
    "research": {"result": {"type": "object"}},
    "artifact": {"result": {"type": "object"}},
    "social_content": {"result": {"type": "object"}},
    "condition": {"matched": {"type": "boolean"}},
    "end": {},
}


class WorkflowGraphValidator:
    """Validate the Stage 1 graph document without executing it."""

    @classmethod
    def validate(cls, definition):
        if not isinstance(definition, dict):
            raise ValueError("Workflow graph must be an object.")
        try:
            encoded = json.dumps(definition, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("Workflow graph must contain JSON-compatible values.") from exc
        if len(encoded) > MAX_DEFINITION_BYTES:
            raise ValueError("Workflow graph exceeds the 100000-byte limit.")

        graph = copy.deepcopy(definition)
        if graph.get("format") != FORMAT:
            raise ValueError("Unsupported workflow graph format.")
        if graph.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported workflow graph schema version.")
        cls._validate_trigger(graph.get("trigger"))

        nodes = graph.get("nodes")
        edges = graph.get("edges")
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES:
            raise ValueError(f"Workflow graph must contain between 1 and {MAX_NODES} nodes.")
        if not isinstance(edges, list) or len(edges) > MAX_EDGES:
            raise ValueError(f"Workflow graph must contain at most {MAX_EDGES} edges.")

        node_by_id = {}
        output_types = {"$trigger": cls._trigger_outputs(graph["trigger"])}
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                raise ValueError(f"Node {index + 1} must be an object.")
            node_id = node.get("id")
            if not isinstance(node_id, str) or not _NODE_ID.fullmatch(node_id):
                raise ValueError(f"Node {index + 1} has an invalid stable ID.")
            if node_id in node_by_id:
                raise ValueError(f"Duplicate node ID: {node_id}.")
            node_type = node.get("type")
            if node_type not in _NODE_OUTPUTS:
                raise ValueError(f"Node '{node_id}' has an unsupported type.")
            version = node.get("version")
            if isinstance(version, bool) or version != 1:
                raise ValueError(f"Node '{node_id}' uses an unsupported node version.")
            if not isinstance(node.get("config", {}), dict):
                raise ValueError(f"Node '{node_id}' config must be an object.")
            inputs = node.get("inputs", {})
            outputs = node.get("outputs", _NODE_OUTPUTS[node_type])
            if not isinstance(inputs, dict) or not isinstance(outputs, dict):
                raise ValueError(f"Node '{node_id}' inputs and outputs must be objects.")
            if node_type == "end" and outputs:
                raise ValueError(f"End node '{node_id}' cannot declare outputs.")
            for output_name, schema in outputs.items():
                if not isinstance(output_name, str) or not output_name:
                    raise ValueError(f"Node '{node_id}' has an invalid output name.")
                cls._validate_schema(schema, f"Node '{node_id}' output '{output_name}'")
            for input_name, mapping in inputs.items():
                if not isinstance(input_name, str) or not input_name:
                    raise ValueError(f"Node '{node_id}' has an invalid input name.")
                if not isinstance(mapping, dict) or not isinstance(mapping.get("source"), dict):
                    raise ValueError(f"Node '{node_id}' input '{input_name}' has an invalid mapping.")
                source = mapping["source"]
                if not isinstance(source.get("node_id"), str) or not isinstance(source.get("output"), str):
                    raise ValueError(f"Node '{node_id}' input '{input_name}' requires a source node and output.")
                if mapping.get("type") not in _SCHEMA_TYPES:
                    raise ValueError(f"Node '{node_id}' input '{input_name}' requires a supported type.")
            node_by_id[node_id] = node
            output_types[node_id] = {name: schema.get("type") for name, schema in outputs.items()}

        edge_ids = set()
        outgoing = {node_id: [] for node_id in node_by_id}
        incoming = {node_id: [] for node_id in node_by_id}
        adjacency = {node_id: [] for node_id in node_by_id}
        trigger_targets = []
        mapped_inputs = set()
        for index, edge in enumerate(edges):
            if not isinstance(edge, dict):
                raise ValueError(f"Edge {index + 1} must be an object.")
            edge_id = edge.get("id")
            if not isinstance(edge_id, str) or not _NODE_ID.fullmatch(edge_id) or edge_id in edge_ids:
                raise ValueError(f"Edge {index + 1} has an invalid or duplicate ID.")
            edge_ids.add(edge_id)
            source_id, target_id = edge.get("from_node_id"), edge.get("to_node_id")
            if source_id != "$trigger" and source_id not in node_by_id:
                raise ValueError(f"Edge '{edge_id}' references an unknown source node.")
            if target_id not in node_by_id:
                raise ValueError(f"Edge '{edge_id}' references an unknown target node.")
            if source_id == target_id:
                raise ValueError(f"Edge '{edge_id}' cannot connect a node to itself.")

            source_output, target_input = edge.get("from_output"), edge.get("to_input")
            if (source_output is None) != (target_input is None):
                raise ValueError(f"Edge '{edge_id}' must define both data ports or neither.")
            if source_output is not None:
                source_outputs = output_types[source_id]
                if source_output not in source_outputs:
                    raise ValueError(f"Edge '{edge_id}' references an undeclared source output.")
                target_node = node_by_id[target_id]
                mapping = target_node.get("inputs", {}).get(target_input)
                if not mapping or mapping["source"] != {"node_id": source_id, "output": source_output}:
                    raise ValueError(f"Edge '{edge_id}' does not match the target input mapping.")
                source_type = source_outputs[source_output]
                target_type = mapping["type"]
                if not cls._types_compatible(source_type, target_type):
                    raise ValueError(f"Edge '{edge_id}' has an incompatible input/output type.")
                mapped_inputs.add((target_id, target_input))

            if source_id == "$trigger":
                trigger_targets.append(target_id)
            else:
                outgoing[source_id].append(edge)
                adjacency[source_id].append(target_id)
            incoming[target_id].append(edge)

        for node_id, node in node_by_id.items():
            for input_name in node.get("inputs", {}):
                if (node_id, input_name) not in mapped_inputs:
                    raise ValueError(f"Node '{node_id}' input '{input_name}' has no matching graph edge.")

        end_ids = {node_id for node_id, node in node_by_id.items() if node["type"] == "end"}
        if not end_ids:
            raise ValueError("Workflow graph must contain at least one end node.")
        for node_id, node in node_by_id.items():
            if node["type"] == "end" and outgoing[node_id]:
                raise ValueError(f"End node '{node_id}' cannot have outgoing edges.")
            if node["type"] != "end" and not outgoing[node_id]:
                raise ValueError(f"Node '{node_id}' has no path to a downstream node.")

        cls._assert_acyclic(node_by_id, adjacency)
        reachable = set()
        stack = list(dict.fromkeys(trigger_targets))
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stack.extend(adjacency[current])
        unreachable = set(node_by_id) - reachable
        if unreachable:
            raise ValueError("Unreachable workflow nodes: " + ", ".join(sorted(unreachable)) + ".")

        can_reach_end = set(end_ids)
        changed = True
        while changed:
            changed = False
            for node_id in node_by_id:
                if node_id not in can_reach_end and any(target in can_reach_end for target in adjacency[node_id]):
                    can_reach_end.add(node_id)
                    changed = True
        dead_ends = set(node_by_id) - can_reach_end
        if dead_ends:
            raise ValueError("Nodes cannot reach an end node: " + ", ".join(sorted(dead_ends)) + ".")

        return graph

    @classmethod
    def from_legacy_steps(cls, steps):
        """Convert the existing ordered-step format into a linear graph.

        The adapter preserves each legacy step ID, type and config. It adds a
        manual trigger and terminal node; it does not claim graph execution.
        """
        from services.workflow_service import WorkflowService

        legacy = WorkflowService.validate_steps(steps, require_nonempty=True)
        nodes = [
            {
                "id": step["id"],
                "type": step["type"],
                "version": 1,
                "config": step["config"],
                "inputs": {},
                "outputs": copy.deepcopy(_NODE_OUTPUTS[step["type"]]),
            }
            for step in legacy
        ]
        nodes.append({
            "id": "workflow-end",
            "type": "end",
            "version": 1,
            "config": {},
            "inputs": {},
            "outputs": {},
        })
        edges = []
        previous = "$trigger"
        for index, node in enumerate(nodes):
            edge_id = f"edge-{index + 1}"
            edges.append({
                "id": edge_id,
                "from_node_id": previous,
                "to_node_id": node["id"],
            })
            previous = node["id"]
        graph = {
            "format": FORMAT,
            "schema_version": SCHEMA_VERSION,
            "trigger": {
                "type": "manual",
                "version": 1,
                "input_schema": {"type": "object", "properties": {}},
            },
            "nodes": nodes,
            "edges": edges,
        }
        return cls.validate(graph)

    @staticmethod
    def _validate_trigger(trigger):
        if not isinstance(trigger, dict):
            raise ValueError("Workflow graph requires a trigger contract.")
        if trigger.get("type") != "manual" or trigger.get("version") != 1:
            raise ValueError("Unsupported workflow trigger type or version.")
        WorkflowGraphValidator._validate_schema(trigger.get("input_schema"), "Trigger input")

    @staticmethod
    def _validate_schema(schema, label):
        if not isinstance(schema, dict) or schema.get("type") not in _SCHEMA_TYPES:
            raise ValueError(f"{label} must declare a supported JSON data type.")
        if schema["type"] == "object":
            properties = schema.get("properties", {})
            if not isinstance(properties, dict):
                raise ValueError(f"{label} object properties must be an object.")
            for name, child in properties.items():
                WorkflowGraphValidator._validate_schema(child, f"{label}.{name}")

    @staticmethod
    def _trigger_outputs(trigger):
        schema = trigger["input_schema"]
        if schema["type"] != "object":
            return {}
        return {name: item["type"] for name, item in schema.get("properties", {}).items()}

    @staticmethod
    def _types_compatible(source_type, target_type):
        return source_type == target_type or (source_type == "integer" and target_type == "number")

    @staticmethod
    def _assert_acyclic(node_by_id, adjacency):
        indegree = {node_id: 0 for node_id in node_by_id}
        for targets in adjacency.values():
            for target in targets:
                indegree[target] += 1
        ready = [node_id for node_id, degree in indegree.items() if degree == 0]
        visited = 0
        while ready:
            current = ready.pop()
            visited += 1
            for target in adjacency[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        if visited != len(node_by_id):
            raise ValueError("Workflow graph contains a cycle; loops are not supported in Stage 1.")
