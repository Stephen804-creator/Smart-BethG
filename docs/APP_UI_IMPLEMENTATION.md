# Smart BethG UI implementation aligned to the approved mockups

The approved smartbethg-approved-screens.zip is the UI/UX source of truth. The implementation follows its screen hierarchy, responsive composition, navigation placement, spacing, colors, typography, and interaction patterns. Content and functionality are supplied by the live product; mockup copy is not treated as a requirement when the current backend does not support it.

## Screen map

### Public and first-run
- /welcome — responsive public marketing page.
- /pricing — Subscribe and Pay as You Go view switcher. Pricing values follow the supplied mockup; payment actions report that payment processing is not enabled.
- /onboarding — splash followed by four navigable/swipeable onboarding slides.
- /login — open registration/sign-in flow. First-run users are routed through onboarding.
- /terms, /privacy — legal documents.

### Authenticated app
- / and /chat — the approved chat-only Home; the legacy index.html now includes this template rather than rendering dashboard content.
- /profile — account summary from the signed-in account.
- /settings — appearance, font, Mentor, learning history, system instructions, connectors, and data/privacy entry points.
- /workspace/projects — owner-scoped projects with create/archive actions.
- /workspace/tasks — owner-scoped missions; exact percentages are shown only when known, otherwise progress is indeterminate.
- /workspace/artifacts — artifact preview/code views, download, and copy-link actions.
- /workspace/connectors — live catalog, search/categories, action details, install/OAuth, and disconnect.
- /workspace/credits — actual token budget and model usage, clearly distinguished from billing credits.
- /workspace/instructions — local custom instructions included with AI chat requests.
- /workspace/privacy — data handling and policy links.
- /workspace/files — uploaded-file list, download, and delete.
- /workspace/learned — explicitly states that learning-history records are not active yet.
- /workspace/lab — approved Lab hub structure; software/hardware runtimes are not connected in this release.

## Interaction behavior

- Home remains conversation-only. Projects, tasks, artifacts, settings, connectors, and usage are separate screens.
- Plan, Balanced, and Build are sent to the agent. Plan mode does not execute classified tools. Build mode prefers supported build work but cannot bypass approvals or capability limits.
- Mentor is a saved browser preference and changes the response context.
- Temporary Chat uses a separate API path and in-memory client transcript. It does not create a saved conversation or enter conversation exports. It is chat-only; file attachments are disabled. Messages are still sent to the selected AI provider, which may process them under its own terms.
- Uploaded files are saved to the user's file library. When attached to a regular chat, their owner-scoped extracted text is included as untrusted source context. Attachment requests are kept in chat synthesis rather than silently routed to tool execution.
- Appearance and font preferences are saved in the browser. Dark is the default; Light and System are supported.
- Registration stays open for eligible adults; there are no invite codes or allow-list controls.

## Explicitly not claimed as complete

- Payment processing is not enabled.
- The full Learn-as-you-build lesson, quiz, rewrite-battle, and reward system is not active; its Settings history page reports this plainly.
- Lab execution experiences (software, hardware simulation, board integration, desktop export) are not connected to working runtimes in this release.
- Independent age assurance remains a separate launch gate; the account's age checkbox is self-attestation, not age verification.

## Verification

The PR includes route smoke tests and targeted tests for temporary-chat non-persistence, mode behavior, Mentor context, attachment context, connector state, and UI routing. CI is still being checked; a green result is not claimed until the latest workflow runs finish.
