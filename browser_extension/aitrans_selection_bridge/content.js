(() => {
  const CONTEXT_LIMIT = 900;
  const SIGNATURE_WINDOW_MS = 120;
  const PAGE_DEBOUNCE_MS = 90;
  let lastSignature = "";
  let lastSentAt = 0;
  let lastPageSignature = "";
  let pageTimer = null;

  function cleanText(value) {
    return String(value || "")
      .replace(/\u0000/g, "")
      .replace(/[\t ]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function activeInputSelection() {
    const element = document.activeElement;
    if (!(element instanceof HTMLTextAreaElement) && !(element instanceof HTMLInputElement)) {
      return null;
    }
    const start = Number(element.selectionStart);
    const end = Number(element.selectionEnd);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return null;
    }
    const value = String(element.value || "");
    return {
      text: cleanText(value.slice(start, end)),
      before: cleanText(value.slice(Math.max(0, start - CONTEXT_LIMIT), start)),
      after: cleanText(value.slice(end, end + CONTEXT_LIMIT)),
      element
    };
  }

  function rangeElement(range) {
    const node = range.commonAncestorContainer;
    if (!node) {
      return null;
    }
    return node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
  }

  function semanticContainer(element) {
    if (!(element instanceof Element)) {
      return null;
    }
    return (
      element.closest("p, li, td, th, blockquote, figcaption, article, section") ||
      element.closest("div") ||
      element
    );
  }

  function nearbyText(container, selectedText) {
    if (!(container instanceof Element)) {
      return { before: "", after: "" };
    }
    const block = cleanText(container.innerText || container.textContent || "");
    if (!block || !selectedText) {
      return { before: "", after: "" };
    }
    const index = block.indexOf(selectedText);
    if (index < 0) {
      return {
        before: block.slice(0, CONTEXT_LIMIT),
        after: ""
      };
    }
    return {
      before: block.slice(Math.max(0, index - CONTEXT_LIMIT), index).trim(),
      after: block.slice(index + selectedText.length, index + selectedText.length + CONTEXT_LIMIT).trim()
    };
  }

  function nearestHeading(element) {
    if (!(element instanceof Element)) {
      return "";
    }

    const section = element.closest("section, article");
    if (section) {
      const ownHeading = section.querySelector(":scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > h5, :scope > h6");
      if (ownHeading) {
        return cleanText(ownHeading.innerText || ownHeading.textContent || "").slice(0, 1024);
      }
    }

    let current = element;
    for (let depth = 0; current && depth < 8; depth += 1) {
      let sibling = current.previousElementSibling;
      for (let steps = 0; sibling && steps < 12; steps += 1) {
        if (/^H[1-6]$/.test(sibling.tagName)) {
          return cleanText(sibling.innerText || sibling.textContent || "").slice(0, 1024);
        }
        const nested = sibling.querySelector?.("h1, h2, h3, h4, h5, h6");
        if (nested) {
          return cleanText(nested.innerText || nested.textContent || "").slice(0, 1024);
        }
        sibling = sibling.previousElementSibling;
      }
      current = current.parentElement;
    }
    return "";
  }

  function currentPageHeading() {
    const heading = document.querySelector("h1, main h2, article h2, h2");
    return cleanText(heading?.innerText || heading?.textContent || "").slice(0, 1024);
  }

  function buildPayload() {
    const inputSelection = activeInputSelection();
    if (inputSelection?.text) {
      return {
        text: inputSelection.text,
        context_before: inputSelection.before,
        context_after: inputSelection.after,
        heading: nearestHeading(inputSelection.element),
        url: location.href,
        frame_url: location.href,
        title: document.title || "",
        top_level: window.top === window,
        captured_at_ms: Date.now()
      };
    }

    const selection = window.getSelection();
    if (!selection || selection.rangeCount < 1 || selection.isCollapsed) {
      return null;
    }
    const text = cleanText(selection.toString());
    if (!text) {
      return null;
    }

    let range;
    try {
      range = selection.getRangeAt(0);
    } catch (_error) {
      return null;
    }
    const element = rangeElement(range);
    const container = semanticContainer(element);
    const context = nearbyText(container, text);

    return {
      text,
      context_before: context.before,
      context_after: context.after,
      heading: nearestHeading(element),
      url: location.href,
      frame_url: location.href,
      title: document.title || "",
      top_level: window.top === window,
      captured_at_ms: Date.now()
    };
  }

  function publishSelection() {
    const payload = buildPayload();
    if (!payload?.text) {
      return;
    }
    const now = Date.now();
    const signature = `${payload.url}\n${payload.text}`;
    if (signature === lastSignature && now - lastSentAt < SIGNATURE_WINDOW_MS) {
      return;
    }
    lastSignature = signature;
    lastSentAt = now;
    try {
      chrome.runtime.sendMessage({
        type: "aitrans-selection",
        payload
      });
    } catch (_error) {
      // Never let the companion extension alter page selection behavior.
    }
  }

  function publishPageContext(force = false) {
    if (window.top !== window || document.visibilityState === "hidden") {
      return;
    }
    const payload = {
      url: location.href,
      frame_url: location.href,
      title: document.title || "",
      heading: currentPageHeading(),
      top_level: true,
      captured_at_ms: Date.now()
    };
    const signature = `${payload.url}\n${payload.title}`;
    if (!force && signature === lastPageSignature) {
      return;
    }
    lastPageSignature = signature;
    try {
      chrome.runtime.sendMessage({
        type: "aitrans-page-context",
        payload
      });
    } catch (_error) {
      // Page context is an optional companion signal and must stay silent.
    }
  }

  function schedulePageContext(force = false) {
    if (pageTimer !== null) {
      clearTimeout(pageTimer);
    }
    pageTimer = setTimeout(() => {
      pageTimer = null;
      publishPageContext(force);
    }, PAGE_DEBOUNCE_MS);
  }

  function wrapHistoryMethod(name) {
    const original = history[name];
    if (typeof original !== "function") {
      return;
    }
    history[name] = function (...args) {
      const result = original.apply(this, args);
      schedulePageContext(true);
      return result;
    };
  }

  document.addEventListener(
    "mouseup",
    () => {
      // Let Chromium commit the DOM Selection before reading it.
      setTimeout(publishSelection, 0);
    },
    true
  );

  document.addEventListener(
    "keyup",
    (event) => {
      if (event.key === "Shift" || event.shiftKey) {
        setTimeout(publishSelection, 0);
      }
    },
    true
  );

  window.addEventListener("focus", () => schedulePageContext(true), true);
  window.addEventListener("pageshow", () => schedulePageContext(true), true);
  window.addEventListener("hashchange", () => schedulePageContext(true), true);
  window.addEventListener("popstate", () => schedulePageContext(true), true);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      schedulePageContext(true);
    }
  });
  wrapHistoryMethod("pushState");
  wrapHistoryMethod("replaceState");
  schedulePageContext(true);
})();
