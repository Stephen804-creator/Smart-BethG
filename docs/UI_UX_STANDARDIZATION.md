# Smart BethG UI/UX Standardization

Branch: `uiux/standardize-design-system`

## Scope
This pass establishes a consistent shared visual language for the dashboard, chat, and authentication screens without changing API contracts or inventing new capabilities.

## Changes
- Consolidated responsive control, form, auth, chat, approval, navigation, and workspace styles in `static/css/main.css`.
- Added responsive behavior for narrow screens, reduced-motion support, visible keyboard focus, and consistent icon-button states.
- Standardized the chat brand/title and navigation links.
- Removed the non-functional command-search field from chat instead of implying search/command execution is available there.
- Removed the static “Available” claim from the assistant header because provider readiness is configuration-dependent.
- Replaced internal implementation wording about mission records with user-facing copy.
- Added active-page semantics to dashboard and chat navigation.
- Moved the authentication page's component styling out of its inline stylesheet and into the shared stylesheet.

## Verification checklist
- Verify live layout at mobile, tablet, and desktop breakpoints.
- Test topbar actions, auth-mode toggling, Google sign-in visibility, password visibility, project/mission forms, provider selection, conversation history, and approvals end to end.
- Review remaining inline styles and ensure every visible control has a real action.
- Run automated tests and accessibility checks before merging.
- This branch is a UI/UX standardization pass, not a claim that the full application is production-ready.
