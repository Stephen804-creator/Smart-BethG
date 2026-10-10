# Smart BethG — native shell (Android / iOS)

**What this is:** a thin native app that opens your *deployed* Smart BethG
site in a webview. It is not a separate codebase, and it does not work
offline — chat needs a live connection to an AI provider by design.

**What this is not (honest limits):**
- It can't be built without your own machine: Android needs Android Studio,
  iOS needs a Mac with Xcode. Nothing here has been built or run by me.
- **Apple may reject it.** App Store guideline 4.2 rejects apps that are
  little more than a website in a wrapper. Google Play is more lenient.
  If iOS store distribution matters, the reliable path is adding genuinely
  native features (push notifications, share sheet, etc.) — or just using the
  installable PWA, which needs no store at all.
- Store accounts cost money and take time: Apple Developer ($99/year),
  Google Play ($25 one-time). Store review is outside anyone's control.

## Easiest option first: the PWA (no store, no build)
Open your deployed URL in Chrome (Android) or Safari (iOS) → menu →
"Add to Home Screen" / "Install app". This already works today.

## Building the Android shell
1. Install Node.js and Android Studio.
2. `cd native && npm install`
3. `SMART_BETHG_URL=https://your-app.onrender.com npx cap add android`
4. `SMART_BETHG_URL=https://your-app.onrender.com npx cap sync`
5. `npm run android` → build/run from Android Studio.

## Building the iOS shell (Mac only)
Same as above with `npx cap add ios` and `npm run ios`.

## Desktop
Capacitor doesn't target desktop. Options: install the PWA from Chrome/Edge
(Install icon in the address bar) — no build needed — or wrap the URL with
Tauri/Electron, which I have not set up.

## Changing your domain later
Nothing to edit in code: re-run `cap sync` with the new `SMART_BETHG_URL`.
Also update the Google OAuth redirect URI and re-check any allowed origins.
