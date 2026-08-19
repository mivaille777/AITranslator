const BRIDGE_URL = "http://127.0.0.1:8765/v1/selection";
const BRIDGE_HEADER = "selection-v1";

chrome.runtime.onMessage.addListener((message, sender) => {
  if (!message || message.type !== "aitrans-selection" || !message.payload) {
    return;
  }

  const payload = {
    ...message.payload,
    version: 1,
    type: "selection",
    tab_url: sender?.tab?.url || ""
  };

  fetch(BRIDGE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-AITrans-Bridge": BRIDGE_HEADER
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  }).catch(() => {
    // The desktop app may be closed. Selection capture should remain silent
    // and must never interfere with normal browser interaction.
  });
});
