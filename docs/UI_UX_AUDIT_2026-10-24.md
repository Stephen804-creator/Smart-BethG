# Smart BethG UI/UX Audit — 2026-10-24

Scope: repository-backed static review of the dashboard, chat, authentication, shared styles, and frontend JavaScript on `uiux/standardize-design-system`. This is not a claim that every journey has been exercised in a browser. Runtime and responsive checks remain required.

Status meanings:
- **Partial** — useful implementation exists, but important gaps remain.
- **Needs runtime verification** — source indicates intent, but browser/API behavior has not been proven here.
- **Missing** — no complete user-facing implementation was found in the reviewed frontend.

## 17-unit assessment

1. **Design system and branding — Partial.** Shared tokens and reusable component styles exist in `static/css/main.css`; branding is consistent. Remaining: remove inline `style.cssText` from `static/js/topbar.js`, check contrast and typography at real device sizes, and consolidate duplicate rules.

2. **Layout and navigation — Partial.** Home/chat navigation, active-page semantics, and responsive sidebar logic exist. Only a small set of top-level destinations is exposed; verify mobile drawer close behavior, keyboard operation, and focus return.

3. **Dashboard and home — Partial.** Project/mission forms, live lists, quick actions, and capability cards are wired to application data. Improve hierarchy so the primary action is immediately obvious; verify empty/error/loading states and ensure capability actions always resolve to a real destination.

4. **AI chat interface — Partial; composer improved in this branch.** Conversation messages, history loading, provider choice, send, and error notices exist. The composer now supports multiline input and explains Enter/Shift+Enter. Still missing or unverified: markdown/code rendering and copy controls, retry affordance, stop/cancel, regenerate, long-response handling, and robust streaming/progress.

5. **Agent interaction and status — Partial.** The UI surfaces provider fallback and intent notes and includes approval review. There is no complete visible plan → execution → validation progress timeline yet. Do not display a ready/available state unless the backend confirms it.

6. **Conversation management — Partial.** New conversation and history reopening exist. Rename, delete with confirmation, and conversation search are absent or unverified. Active history styling and busy-state protection are now implemented.

7. **Providers and model selection — Partial.** Auto and catalog-driven provider/model selection are implemented. Provider-loading failures and an empty provider catalog now expose a status message and retry action; verify the wording matches actual backend fallback behavior. Never expose API keys.

8. **Forms and input — Partial.** Labels, browser validation, submit disabling, and status messages exist in several flows. Audit all forms for consistent inline errors, retained user input after failures, disabled/loading states, and keyboard/mobile usability.

9. **Authentication and account — Partial.** Login/register toggle, password visibility, CSRF requests, and conditional Google login exist. Password recovery/reset and clearer account/session-expiry recovery are not present in the reviewed page. Verify registration errors and accessible focus after failure.

10. **Settings and personalisation — Missing as a complete area.** The topbar account panel shows account identity; it is not a settings centre. Do not label it “Settings” until actual preferences exist. Add provider defaults, theme/accessibility preferences, and save/reset feedback only when backed by persisted functionality.

11. **Notifications and feedback — Partial.** Usage/account panels and inline operation feedback exist. A standalone notifications control had no real notification feed, so it was removed rather than left as a dead control. A persistent notification centre is still missing.

12. **Loading, empty, error, recovery — Partial.** Some lists show loading/empty states and network errors. Conversation history and provider failures now have visible retry controls; failed sends restore the typed prompt. Conversation switching is temporarily disabled while a reply is in progress. Continue distinguishing “no data” from “could not load data” and verify retries against backend failures.

13. **Responsive design — Needs runtime verification.** Responsive rules exist and the composer now adapts to narrow screens. Test at narrow Android widths, tablet, laptop, zoomed text, landscape, and with the keyboard open. Check horizontal overflow, clipped popovers, sidebar overlays, and touch target size.

14. **Accessibility — Partial.** Semantic landmarks, labels, live regions, focus styling, and reduced-motion support exist. Audit keyboard-only flows, focus visibility/return, live announcement noise, contrast, dialog semantics, and all dynamically created controls.

15. **Security and privacy UX — Partial.** CSRF-protected actions and explicit operation approval are visible. Review the approval payload UI for secrets or sensitive values, explain the exact action/resource before approval, and test expired sessions and denied permissions. No security claim is made by this visual audit alone.

16. **Task execution and workflow UX — Partial.** Projects/missions and approval decisions exist, but the core agent loop is not consistently visible as a single journey. Show plan, current step, progress, validation, result/artifact, and honest cancellation/recovery states when supported by backend events.

17. **Production polish and QA — Needs verification; not merge-ready based on this review alone.** The current GitHub Actions test workflow is failing on the branch. The connector did not return job details, so the failing step is unresolved. Run the workflow locally or inspect the GitHub Actions job logs before merge; add browser-level tests for critical journeys and accessibility checks.

## Changes made during this pass

- Removed the dashboard's non-functional global search field rather than implying search works.
- Removed the unsupported notifications control rather than presenting a dead-end action.
- Changed the topbar account action's visible/accessibility meaning from Settings to Account.
- Removed the duplicated chat-page hero heading.
- Replaced the single-line chat input with a multiline textarea and added a keyboard hint.
- Replaced chat history/approval inline styles with reusable classes; added active-history styling.
- Added accessible status messages and retry controls for failed history/provider loading; failed sends restore the user's text.
- Prevented switching conversations or starting a new chat while a response is pending.
- Moved account/usage popover styles from JavaScript inline styles into responsive shared CSS.
- Added responsive composer styling and retained the existing provider selector and send behavior.
- Kept all work on `uiux/standardize-design-system`; `main` was not modified.

## Required next pass, in order

1. Resolve the failing CI workflow and add/repair frontend smoke tests.
2. Test login/register/logout, dashboard project/mission creation, provider loading, send/error/retry, conversation switching, and approval decisions end-to-end.
3. Improve chat history and message actions without inventing backend capabilities.
4. Replace inline JavaScript styling with shared CSS classes and verify focus/contrast.
5. Test phone/tablet/desktop layouts and keyboard/screen-reader behavior.
6. Only then mark the branch ready for review; do not merge while CI is failing or key journeys remain untested.


## 2026-10-24 — Comparison-video layout pass

The supplied reference recording shows features grouped into navigation menus and settings screens, while the current Smart BethG home page exposes project forms, mission forms, capability cards, mission cards, artifacts, and infrastructure status in one long scroll. The current dashboard has been adjusted to reduce that first-screen density.

- Added expandable **Workspace** and **Explore** groups to the sidebar.
- Wrapped project/mission management, capabilities, active missions, artifacts, and system status in accessible native disclosure panels, closed by default.
- Made sidebar section links open the corresponding panel before navigation.
- Added clear primary actions for **Start a conversation** and **Manage workspace** in the hero; removed the repeated bottom-of-page chat call-to-action.
- Made optional navigation links conditional so empty sections do not leave links pointing to missing panels.
- Kept the existing forms, API endpoints, and capability actions in place; this is a presentation/organization pass, not a claim that additional backend features now exist.

### Remaining work from the reference comparison

- Design and implement a real first-run onboarding flow that explains the workspace, provider setup, privacy/permissions, and how to begin—without implying setup steps are complete when they are not.
- Give high-level areas dedicated views rather than continuing to grow a single dashboard template.
- Review the feature inventory and move future features into grouped navigation only when their screens and behaviors are implemented.
- Verify the updated Jinja output and run CI plus mobile/keyboard/browser checks before calling the redesign complete.


## Onboarding content rule — user-approved direction (2026-10-24)

Onboarding must explain Smart BethG from the user's point of view. Do not expose implementation details, backend/frontend terminology, provider/model names, configuration internals, or claims about which technologies power the product. Keep the visible experience centered on **Auto** and on what the product can genuinely do today.

Proposed onboarding sequence:

1. **Welcome to Smart BethG** — “A workspace for thinking through tasks, having conversations, and organizing work with an AI assistant.”
2. **Tell it what you want to do** — explain that the user can describe a question, problem, idea, or task in everyday language and add relevant context.
3. **Work through a conversation** — show how to ask follow-up questions, clarify the result, and refine the response until it is useful.
4. **Keep work organized** — explain Projects & Missions as a way to group work and record objectives; show artifacts only as available results the user can open.
5. **Review before acting** — where a task asks for approval, explain that the user can review the proposed action and choose whether to approve it. Never imply all actions happen automatically or that every integration is connected.
6. **You're ready** — invite the user to start a conversation with a simple prompt such as “Help me plan my next project.”

Content guardrails:
- No “we use this model/provider/framework/API” wording.
- No backend/frontend, server, database, infrastructure, configuration, or setup jargon in user-facing onboarding.
- Do not expose model/provider selection; present **Auto** as the user-facing choice.
- Describe only current, working capabilities. Label unavailable or planned capabilities as unavailable/planned in internal planning, not as something the user can already do.
- Keep each step short, plain-language, and skippable; let users reopen the guide later from Help.
- Do not force users through onboarding before they can start using the product.
