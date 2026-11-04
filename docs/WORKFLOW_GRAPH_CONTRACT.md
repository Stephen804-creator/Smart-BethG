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

## Legacy sequential compatibility and publication

`WorkflowGraphValidator.from_legacy_steps` converts the existing ordered step array into a linear graph, preserving each step's ID, type and configuration. It adds a manual trigger and an end node.

When a workflow is published, the service stores both the exact legacy step definition used by the current sequential executor and its validated graph representation in an immutable version snapshot. The published version is append-only for UPDATE operations. Editing a workflow creates a new draft version and does not mutate earlier snapshots.

New runs store the exact published snapshot ID. The workflow executor and continuation callbacks load the run's pinned step definition, not the mutable workflow row. Existing clients that call validate and then run remain compatible: the first run after validation publishes that validated draft before enqueueing it. A dedicated publish endpoint is also available.

Historical runs created before snapshot support retain a NULL snapshot reference. The system does not fabricate historical snapshots; those runs use the legacy version check and may be unrecoverable if the workflow was subsequently edited.

Malformed legacy JSON is exposed as an invalid definition instead of being silently treated as an empty workflow. Metadata-only edits are blocked until the owner explicitly supplies replacement steps. The original malformed JSON and replacement are recorded in the recovery table.

## Explicit limitations

- The graph representation is persisted in published snapshots, but current execution remains sequential. Graph scheduling, branching, loops, retries and data-port runtime resolution are not implemented here.
- The compatibility boundary supports lossless conversion in both directions for a simple linear workflow. The graph-to-legacy adapter rejects branches, data-port mappings, unsupported triggers and any graph shape that cannot be represented without changing behavior.
- Detailed per-node configuration schemas and the unified node registry remain later Stage 1/Stage 3 work.
- The graph contract currently recognizes a bounded set of trusted node types and rejects arbitrary shell/code nodes.

## Verification

The focused graph tests are in `tests/test_workflow_graph.py`, using reusable valid and invalid documents from `tests/fixtures/workflow_graphs/`. Workflow publication, immutable snapshots, run pinning, version reads, append-only behavior, duplication, ownership and malformed-legacy recovery are covered in `tests/test_workflow_service.py` and `tests/test_units_10_15_services.py`. PostgreSQL integration exercises the additive migration path.
