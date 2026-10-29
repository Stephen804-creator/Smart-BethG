# Smart BethG - Design Rules (agents: read before any UI change)
Reference: smartbethg-mockup.html. Tokens: tokens.json. Match them exactly.
This is our own design. Do not copy other apps' layouts.

## Product rules (never change without owner approval)
- Registration is ALWAYS open. This is a public app. Never add invite codes, allow-lists or switches that close sign-up.
- Keep rate limits and daily token/spend budgets. They protect the public app.

## Golden rule
Home is CHAT ONLY. Never add features, lists, dashboards or progress to Home.

## Onboarding (first launch)
Splash -> 4 swipe slides (Meet Smart BethG, Do real work, Connect your tools, You choose how it works) with dots, Skip and Next -> Create account (Google or email, "No invite needed") -> Home.

## Home
- Top bar: menu (left), logo, temporary-chat icon, avatar (right). No other icons.
- Greeting + small credits chip (tap = Credit usage page).
- Task blocks (2-column grid, scrolls, can grow): Create slides, Write a report, Build an app, Analyze data, Build a website, Plan a project, Research a topic, Draft an email. Tap = start that task.
- Composer: "+" (Files, Photos, Camera, Folders), mode pill, mic, send.
- Mode picker is a bottom sheet: Plan (thinks first, asks before acting), Balanced (default), Build (creates and runs things).
- Temporary chat: not saved, never used for export. Purple-outlined composer.

## Menu drawer (collapsible groups)
New chat, Recents, Projects, Tasks & Missions, Artifacts, Settings. New chat lives here, not in the top bar.

## Avatar popover
Profile, Settings, Sign out.

## Settings
Appearance (Dark/Light/System), Font (Default/Readable/Mono), System instructions, Connectors, Data & privacy.

## Connectors (inside Settings only)
- Search bar, then scrollable category chips (All, Development, E-commerce, Productivity, Communication, Design; add more as needed).
- Each row: logo, name, one-line note, "+" to connect (turns into a green check when connected).
- Tapping a row opens a detail page: what it does, how to connect (3 steps), "Try asking" examples, Connect button.
- Never list connectors anywhere else.

## Credit usage
Own page from the Home chip: credits left, progress bar, reset date, usage by Chat/Build/Research, "Get more credits".

## Tasks & Missions
Own page. Progress = thin green bar inside each item.

## Artifact page
- Preview/Code toggle, code icon, "..." menu (Download, Export to GitHub, Copy link).
- Code tab is split: file list on the left, a draggable divider line, code of the selected file on the right.
- Every file row has a "..." menu (Export, Copy code, Send to GitHub).

## Adding a new feature - process
1. State which screen/group it belongs in and why. WAIT for approval.
2. Prefer a new item inside an existing collapsible group, category or sub-page.
3. Never add a new section to Home. Never put two features' content on one page.
4. Reuse tokens/components; no new colors or fonts.
5. Update smartbethg-mockup.html first, then the code.
