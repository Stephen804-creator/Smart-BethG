# Smart BethG - Design Rules (agents: read before any UI change)
Reference: smartbethg-mockup.html. Tokens: tokens.json. Match them exactly.

## Golden rule
Home is CHAT ONLY. Never add features, lists, dashboards or progress to Home.

## Home (first screen after onboarding)
- Top bar: menu (left), logo, temporary-chat icon, new-chat icon, avatar (right).
- Greeting + 4 small suggestion cards (tap = start that task).
- Composer: "+" (Files, Photos, Camera, Folders), mode pill (Plan / Balanced / Build), mic, send.
- Temporary chat: not saved, never used for export. Shows a purple-outlined composer.

## Where everything else lives
- Menu drawer, collapsible groups: Recents, Projects, Tasks & Missions, Artifacts, then Settings.
- Avatar popover: Profile, Settings, Sign out.
- Settings: Appearance (Dark/Light/System), Font, System instructions, Connectors, Data & privacy.
- Tasks & Missions: own page. Progress = thin green bar inside each item.
- Artifact page: Preview/Code toggle, code icon, "..." menu (Download, Export to GitHub, Copy link).

## Adding a new feature - process
1. State which screen/group it belongs in and why. WAIT for approval.
2. Prefer a new item inside an existing collapsible group or a sub-page.
3. Never add a new section to Home. Never put two features' content on one page.
4. Reuse tokens/components; no new colors or fonts.
5. Update smartbethg-mockup.html first, then the code.
