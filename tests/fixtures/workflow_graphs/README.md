# Workflow graph contract fixtures

These small JSON documents are reusable contract fixtures for the Stage 1 workflow graph validator.

- `valid_linear.json`: valid manual-trigger → research → end graph with one typed trigger input.
- `invalid_cycle.json`: same graph with a back-edge that creates a cycle.
- `invalid_unreachable.json`: adds an end node that cannot be reached from the trigger.
- `invalid_type_mismatch.json`: maps a string trigger output to a boolean input.

The invalid fixtures are expected to raise `ValueError` with the corresponding structural validation message. Keep these fixtures representative and free of secrets or user data.
