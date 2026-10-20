# Smart BethG Engineering Standards

## Purpose

Smart BethG must remain understandable and changeable as its AI providers, application features, and deployment model evolve. These standards make code review repeatable and help new contributors understand not only what a component does, but why its boundaries and safeguards exist.

## Python conventions

- Follow PEP 8: four spaces for indentation, `snake_case` for variables/functions/modules, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Keep functions focused on one responsibility. Extract a helper when it gives a meaningful name to a rule or removes repeated behavior; do not split code into modules solely to increase the file count.
- Add type hints to new or materially changed public functions and service boundaries. Use precise return types and avoid introducing `Any` where a real contract can be expressed.
- Use docstrings for modules, classes, and public functions when their purpose, invariants, side effects, or usage would not be obvious from the signature.
- Prefer explicit control flow and domain-specific exceptions over clever expressions, broad exception swallowing, or hidden fallback behavior.
- Keep comments focused on intent, constraints, security implications, and maintenance invariants. Do not narrate obvious syntax or use dates as a substitute for explanation.
- Avoid unrelated cleanup in a behavior-changing patch. Small, reviewable changes are easier to validate and revert.

## Architecture and boundaries

- Keep PostgreSQL as the sole supported application database. Database-backed tests must use the shared PostgreSQL test harness; do not introduce SQLite fallbacks that can hide PostgreSQL-specific behavior.
- Keep HTTP concerns (request parsing, status codes, response serialization) at API boundaries; put reusable business rules in services; keep persistence access behind clearly named database/repository functions where practical.
- Treat authentication, authorization, tenant/workspace isolation, CSRF, CORS, secret handling, and file-path validation as explicit contracts—not incidental implementation details.
- Keep AI-provider-specific request/response handling behind adapters. Provider selection and application business rules should not depend on provider-specific payloads.
- Make configuration explicit and validated. Do not silently replace a failed provider, database, or security configuration with a weaker mode.
- Explain non-obvious architectural decisions in the relevant module or an architecture decision record. State the problem, the chosen constraint, and what future changes must preserve.

## Testing strategy

### Unit tests
Test one function or service rule at a time: input validation, provider selection, permission decisions, normalization, and error mapping. Use deterministic fixtures and mocks only at genuine external boundaries. Do not mock the behavior that the test is intended to verify.

### Integration tests
Verify real interactions between components, especially PostgreSQL persistence, transaction behavior, authentication/authorization, API routing, and service-to-database contracts. Use the repository's isolated PostgreSQL test harness for database-backed tests.

### End-to-end tests
Verify complete user-visible workflows through the application's public interfaces—for example, authentication, creating a task, processing it through the selected provider or a deterministic test adapter, and retrieving its result. Keep E2E coverage focused on critical journeys rather than duplicating every unit assertion.

### Regression and failure reporting
- Every bug fix should include a regression test that fails before the fix when practical.
- Test success must be based on executed results, not compilation alone or a reviewer's expectation.
- When a check fails, preserve the actual error output and identify the failing command/job before changing code. Never label a check as passing when logs or results are unavailable.
- CI must exercise the same supported database and critical runtime assumptions as the application.
- Keep tests isolated, repeatable, and safe to run concurrently; tests must not depend on shared production data or developer-specific local state.

## Quality gates and adoption

Introduce enforcement in stages so the repository does not acquire a large set of new failures that obscure existing defects:

1. **Establish the baseline:** capture current unit, PostgreSQL integration, syntax, dependency-audit, and secret-scan results. Record each failure with evidence.
2. **Resolve existing blockers:** fix confirmed defects and investigate dependency vulnerabilities and secret-scan findings individually. Do not suppress a finding without a documented, justified exception.
3. **Standardize changed code:** apply consistent formatting and linting to files touched by each refactoring change; avoid unrelated repository-wide formatting churn.
4. **Add automated enforcement:** after the baseline is understood, introduce a formatter/linter and, where useful, type checking with pinned or bounded tool versions. Run checks in CI and document the exact local commands.
5. **Refactor incrementally:** extract modules only after tests protect current behavior. Each step should have a clear responsibility, a small diff, and tests appropriate to the risk.
6. **Release only on evidence:** require relevant checks to pass, review security findings, and document any known limitations before a change is considered ready to merge or deploy.

## Definition of done for a refactoring change

A change is ready for review when its purpose and trade-offs are clear, names and formatting are consistent, boundaries remain explicit, behavior is covered by appropriate tests, security-sensitive behavior is preserved, and the relevant CI results have been inspected. A green check is necessary evidence, but it does not replace code review or architectural judgment.
