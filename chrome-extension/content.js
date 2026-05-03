(function () {
  document.addEventListener(
    "copy",
    () => {
      reportSelection();
    },
    true
  );

  document.addEventListener(
    "cut",
    () => {
      reportSelection();
    },
    true
  );

  function reportSelection() {
    const text = getSelectedText();
    if (!text) {
      return;
    }

    chrome.runtime.sendMessage({
      type: "capture-copy",
      payload: {
        text,
        title: document.title,
        url: location.href
      }
    });
  }

  function getSelectedText() {
    const active = document.activeElement;
    if (
      active &&
      (active.tagName === "TEXTAREA" ||
        (active.tagName === "INPUT" && /^(text|search|url|tel|password)$/i.test(active.type)))
    ) {
      const start = active.selectionStart ?? 0;
      const end = active.selectionEnd ?? 0;
      return active.value.slice(start, end).trim();
    }

    return String(window.getSelection() || "").trim();
  }
})();
