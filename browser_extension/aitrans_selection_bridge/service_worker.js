const BRIDGE_URL = "http://127.0.0.1:8765/v1/selection";
const BRIDGE_HEADER = "selection-v1";

chrome.runtime.onMessage.addListener((message, sender) => {
  if (!message || !message.payload) {
    return;
  }

  const isSelection = message.type === "aitrans-selection";
  const isPageContext = message.type === "aitrans-page-context";
  if (!isSelection && !isPageContext) {
    return;
  }

  const frameUrl = message.payload.frame_url || message.payload.url || "";
  const payload = {
    ...message.payload,
    version: 1,
    type: isSelection ? "selection" : "page",
    url: sender?.tab?.url || message.payload.url || "",
    title: sender?.tab?.title || message.payload.title || "",
    frame_url: frameUrl
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
    // The desktop app may be closed. Browser interaction must stay unaffected.
  });
});
