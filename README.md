# Smart BethG — Batches 1–7

This package contains the requested code for Batches 1–7 in both PV and LV trees.

## Batches
1. FastAPI API Layer
2. Real Tool Layer
3. Authentication & Authorization
4. Database Foundation
5. Application Services
6. Knowledge / Validation / Memory
7. Provider & AI Account Management

## Important integration notes
- `main_fastapi.py` is the FastAPI migration target. It does not claim the old Flask `main.py`/`routes.py` have already been replaced.
- Existing security-control-plane files are not duplicated. Tool wrappers are designed to consume the existing `ExecutionPermit` boundary.
- Google/OpenAI/Anthropic/Gemini/local model adapters are provider boundaries; SDK installation and credentials are deployment work.
- Provider credentials are intentionally not returned by API list endpoints. `CredentialStore` is an in-memory development seam, not production secret storage.
- Docker, terminal, network and browser operations are live-capability boundaries and must remain approval/policy controlled.
- The current repository code may require the existing Batch 1–4 foundation to be reconciled with these files before running as one integrated application.
