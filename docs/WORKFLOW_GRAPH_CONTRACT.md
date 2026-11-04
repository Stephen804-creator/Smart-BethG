# Smart BethG workflow graph contract — Stage 1

**Status:** Initial contract implementation; graph execution is not enabled by this document.

## Purpose

Smart BethG is moving from an ordered list of workflow steps toward a versioned directed graph. The graph contract is the durable representation that validation, publication, execution and the future visual editor will share. This Stage 1 contract defines the data shape and validates it. Stage 2 is responsible for executing dependencies and branches.

## Top-level format

A graph document uses:

- `format`: `smartbethg.workflow.graph`
- `schema_version`: `1.0`
- `trigger`: a versioned trigger contract. Stage 1 supports the manual trigger contract.
- `nodes`: nodes with stable IDs, node type/version, configuration, typed input mappings and declared outputs.
- `edges`: explicit directed control-flow and optional data-flow connections.

Node IDs and edge IDs are stable strings matching `^[A-Za-z][A-Za-z0-9_-]{0,79}$`. A node's type version is explicit. Unknown node types or versions fail validation.

## Node shape

A node contains `id`, `type`, `version`, `config`, `inputs` and `outputs`. Input mappings identify a source node/output and expected data type. Output declarations use the supported JSON types: object, array, string, number, integer, boolean and null. Integer output can feed a number input; other mismatches fail validation.

The initial built-in contract recognizes the existing trusted types: mission, research, artifact, social_content and condition, plus the terminal end node. This is a definition allowlist, not a claim that every node has a new graph executor. Arbitrary shell/code node types are not allowed.

## Edges and graph rules

A control-flow edge has an ID, source node ID and target node ID. The special source ID `$trigger` represents the workflow trigger. A data-flow edge additionally names a source output and target input; it must agree with the target node's typed input mapping.

Validation rejects unknown endpoints, duplicate IDs, missing data edges, incompatible data types, self-links, cycles, unreachable nodes and nodes without a path to an end node. Cycles are rejected in Stage 1; loops require a later explicit bounded-loop contract and execution semantics. At least one end node is required.

## Trigger contract

The first supported trigger is `manual`, version 1, with an object-shaped input schema. The trigger's declared properties are the available outputs from `$trigger`. Schedules, webhooks and polling are later stages and must not be advertised as available by this contract.

## Legacy sequential compatibility

`WorkflowGraphValidator.from_legacy_steps` converts the existing ordered step array into a linear graph, preserving each step's ID, type and configuration. It adds a manual trigger and an end node. It is a compatibility conversion/validation helper only; it does not change existing database storage or route execution.

Legacy definitions continue to be handled by the existing workflow service and sequential executor until the later persistence/publication and graph-execution work is completed. A failed conversion must be surfaced for repair; callers must not silently discard the original definition.

## Explicit limitations

- This contract does not yet persist graph documents as the canonical workflow record.
- It does not yet create immutable published workflow versions.
- Workflow runs are not yet pinned to immutable published snapshots.
- It does not implement branch scheduling, loops, retries or graph execution.
- Detailed per-node configuration schemas and the unified registry belong to later Stage 1/Stage 3 work; the current validator checks the shared envelope and declared data types.

## Verification

The focused unit tests are in `tests/test_workflow_graph.py`. They cover valid typed graphs, non-mutation, stable/unique IDs, unknown types/endpoints, data type mismatches, unmapped inputs, cycles, reachability, terminal paths, schema versions and conversion from legacy sequential definitions.
