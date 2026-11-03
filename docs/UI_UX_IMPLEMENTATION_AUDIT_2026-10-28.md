# Smart BethG UI/UX implementation audit — 2026-10-28

## Design source and scope

The existing Figma file contains frames named **02 — Smart BethG desktop workspace**, **03 — AI assistant conversation**, and **04 — Mobile home**. The Figma MCP hit the Starter-plan tool-call limit during this implementation, so a fresh screenshot/context inspection and direct Figma canvas edits could not be completed in this pass. This PR therefore applies the existing Smart BethG UI direction already represented in the repository's UI/UX work; it must not be described as a pixel-perfect Figma-to-code verification.

## Implemented in this branch

- Added a shared responsive style layer for grouped dashboard navigation, expandable dashboard panels, chat starter cards, response-option disclosure, light-theme tokens, typography preferences, and compact sidebar states.
- Grouped navigation into **Workspace** and **Explore**, with links to the relevant in-page sections.
- Reworked the dashboard hero to make **Start a conversation** the primary action and provide a clear route to workspace management and the getting-started guide.
- Collapsed secondary dashboard areas—projects/missions, capabilities, active missions, artifacts, and system status—into native disclosure panels to reduce first-screen clutter.
- Added a six-step plain-language getting-started guide to login and dashboard pages. It supports next/back, direct step navigation, skip/close, Escape, focus restoration, and remembering completion when local storage is available.
- Added chat welcome content and prompt starters for building an application, exploring an idea, learning a topic, and organising a project.
- Moved response routing into an expandable **Response options** disclosure so the conversation and composer remain the main focus.
- Updated in-page navigation behavior so a sidebar/hero link opens its target disclosure before scrolling to it.
- Kept existing API endpoints and application behavior in place; this change does not claim any new backend capabilities are available.

## Verification still required

- Run the repository's GitHub Actions test and security workflows on this exact PR head.
- Render the affected Jinja templates with representative data (including empty and populated capabilities/missions/artifacts).
- Verify login/register/logout and the first-visit/returning-user onboarding journeys in a real browser.
- Verify chat welcome prompts, existing conversation history, sending/retrying messages, pending approvals, and response routing.
- Check keyboard-only navigation, focus visibility, Escape handling, screen-reader labels, contrast, and mobile/tablet/desktop breakpoints.
- Compare real browser screenshots against the named Figma frames and make any required visual corrections after Figma MCP access is available again.

## Release gate

Do not merge until CI passes and the browser journeys above are checked. A source-level structural check confirmed balanced HTML disclosure/dialog tags in the modified templates and one chat welcome renderer; it does not replace template rendering or browser testing.
