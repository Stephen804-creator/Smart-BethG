// Smart BethG native shell configuration.
//
// Smart BethG is a server-rendered FastAPI app, not a static single-page
// build, so there are no static files to bundle into the app. Instead the
// native shell loads the DEPLOYED site in a webview (Capacitor's
// server.url). The URL comes from an environment variable so nothing about
// where you deploy is hardcoded - the same shell works for your test
// onrender.com URL now and your real domain later.
//
//   SMART_BETHG_URL=https://your-app.onrender.com npx cap sync
import type { CapacitorConfig } from "@capacitor/cli";

const url = process.env.SMART_BETHG_URL;
if (!url) {
  throw new Error(
    "Set SMART_BETHG_URL to the deployed https:// address of Smart BethG " +
      "(e.g. SMART_BETHG_URL=https://your-app.onrender.com) before running cap commands."
  );
}
if (!url.startsWith("https://")) {
  throw new Error("SMART_BETHG_URL must be https:// - the session cookie is HTTPS-only in production.");
}

const config: CapacitorConfig = {
  appId: "com.smartbethg.app",
  appName: "Smart BethG",
  // Required by Capacitor even when loading a remote URL; holds a minimal
  // placeholder page shown only if the remote site can't be reached.
  webDir: "www",
  server: {
    url,
    cleartext: false,
  },
};

export default config;
