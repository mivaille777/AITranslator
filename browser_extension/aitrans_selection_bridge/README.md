# AITrans Selection Bridge

This companion extension lets AITranslator read webpage selections directly from the DOM instead of synthesizing `Ctrl+C`.

## How it works

1. `content.js` reads `window.getSelection()` after the user's mouse-up event. It also captures bounded nearby text, the nearest heading, page title, and URL.
2. The Manifest V3 service worker forwards that structured snapshot to `http://127.0.0.1:8765/v1/selection`.
3. AITranslator listens only on the local loopback interface and keeps the newest snapshot briefly.
4. Automatic mouse translation prefers the fresh browser snapshot. If the extension is unavailable or the snapshot does not match the current gesture, AITranslator falls back to Word COM / Windows UI Automation.
5. Neither path synthesizes `Ctrl+C` or `Ctrl+V`.

## Install in Chrome

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked**.
4. Select this folder: `browser_extension/aitrans_selection_bridge`.
5. Keep AITranslator running and refresh any already-open webpage once after installing the extension.

## Install in Microsoft Edge

1. Open `edge://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked**.
4. Select this folder: `browser_extension/aitrans_selection_bridge`.
5. Keep AITranslator running and refresh any already-open webpage once after installing the extension.

## Scope and privacy

- The desktop receiver binds to `127.0.0.1:8765`; it is not exposed on the LAN.
- The extension sends data only when a non-empty selection exists.
- Payloads are bounded and include selected text plus limited nearby reading context.
- AITranslator does not log the raw selected text or raw page URL in the bridge server.
- Normal webpages cannot use the custom bridge request path through a CORS preflight; the intended sender is the installed extension service worker.

## Current limitation

Chrome/Edge built-in PDF viewers are extension-owned pages and do not expose their DOM to an ordinary webpage content script. AITranslator therefore continues to use the Stage-2 Windows UI Automation path for browser PDF selection. A dedicated PDF bridge can be added separately later.
