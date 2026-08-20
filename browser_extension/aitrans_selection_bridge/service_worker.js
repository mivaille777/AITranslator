const BRIDGE_URL = "http://127.0.0.1:8765/v1/selection";
const BRIDGE_HEADER = "selection-v1";
const PAGE_SCHEMES = ["http://", "https://", "file://", "chrome-extension://", "edge-extension://"];

function sendToDesktop(payload) {
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
}

function normalizedTabUrl(tab) {
  return String(tab?.url || tab?.pendingUrl || "").trim();
}

function publishTabContext(tab) {
  if (!tab?.active) {
    return;
  }
  const url = normalizedTabUrl(tab);
  if (!url || !PAGE_SCHEMES.some((prefix) => url.startsWith(prefix))) {
    return;
  }
  sendToDesktop({
    version: 1,
    type: "page",
    url,
    frame_url: url,
    title: String(tab.title || ""),
    heading: "",
    top_level: true,
    captured_at_ms: Date.now()
  });
}

function publishTabById(tabId) {
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError || !tab) {
      return;
    }
    publishTabContext(tab);
  });
}

function publishFocusedWindowTab(windowId) {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    return;
  }
  chrome.tabs.query({ active: true, windowId }, (tabs) => {
    if (chrome.runtime.lastError || !tabs?.length) {
      return;
    }
    publishTabContext(tabs[0]);
  });
}

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
  sendToDesktop({
    ...message.payload,
    version: 1,
    type: isSelection ? "selection" : "page",
    url: sender?.tab?.url || message.payload.url || "",
    title: sender?.tab?.title || message.payload.title || "",
    frame_url: frameUrl
  });
});

chrome.tabs.onActivated.addListener(({ tabId }) => publishTabById(tabId));
chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
  if (!tab?.active) {
    return;
  }
  if (changeInfo.url || changeInfo.title || changeInfo.status === "complete") {
    publishTabContext(tab);
  }
});
chrome.windows.onFocusChanged.addListener(publishFocusedWindowTab);
