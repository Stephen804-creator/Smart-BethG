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
