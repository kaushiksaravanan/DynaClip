const searchInput = document.getElementById("search-input");
const addClipboardButton = document.getElementById("add-clipboard");
const clearButton = document.getElementById("clear-items");
const captureToggle = document.getElementById("capture-toggle");
const hoverCopyToggle = document.getElementById("hover-copy-toggle");
const hoverDelaySelect = document.getElementById("hover-delay");
const status = document.getElementById("status");
const itemsContainer = document.getElementById("items");
const itemTemplate = document.getElementById("item-template");

let state = { items: [], captureEnabled: true, autoCopyOnHover: false, hoverDelayMs: 800 };
let query = "";
let hoverTimer = null;

searchInput.addEventListener("input", () => {
  query = searchInput.value.trim().toLowerCase();
  render();
});

addClipboardButton.addEventListener("click", async () => {
  try {
    const text = (await navigator.clipboard.readText()).trim();
    if (!text) {
      setStatus("Clipboard is empty or does not contain text.");
      return;
    }

    const response = await sendMessage({
      type: "add-text",
      text,
      meta: { title: "Manual add", host: "Chrome" }
    });
    state = response.state;
    setStatus("Added current clipboard text.");
    render();
  } catch (error) {
    setStatus("Chrome blocked clipboard read. Click in the panel and try again.");
  }
});

clearButton.addEventListener("click", async () => {
  const response = await sendMessage({ type: "clear-items" });
  state = response.state;
  setStatus("Cleared this browser session history.");
  render();
});

captureToggle.addEventListener("click", async () => {
  const response = await sendMessage({
    type: "set-capture-enabled",
    enabled: !state.captureEnabled
  });
  state = response.state;
  setStatus(state.captureEnabled ? "Auto capture enabled." : "Auto capture paused.");
  render();
});

hoverCopyToggle.addEventListener("click", async () => {
  const response = await sendMessage({
    type: "set-hover-settings",
    enabled: !state.autoCopyOnHover,
    delayMs: Number(hoverDelaySelect.value)
  });
  state = response.state;
  setStatus(state.autoCopyOnHover ? "Hover copy enabled." : "Hover copy disabled.");
  render();
});

hoverDelaySelect.addEventListener("change", async () => {
  const response = await sendMessage({
    type: "set-hover-settings",
    enabled: state.autoCopyOnHover,
    delayMs: Number(hoverDelaySelect.value)
  });
  state = response.state;
  setStatus(`Hover delay set to ${(state.hoverDelayMs / 1000).toFixed(1)}s.`);
  render();
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "session" || !changes.clipboardState?.newValue) {
    return;
  }
  state = changes.clipboardState.newValue;
  render();
});

bootstrap();

async function bootstrap() {
  const response = await sendMessage({ type: "get-state" });
  state = response.state;
  render();
}

async function sendMessage(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) {
    throw new Error(response?.error || "Request failed");
  }
  return response;
}

function render() {
  captureToggle.textContent = state.captureEnabled ? "Auto capture on" : "Auto capture off";
  captureToggle.setAttribute("aria-pressed", String(state.captureEnabled));
  hoverCopyToggle.textContent = state.autoCopyOnHover ? "Hover copy on" : "Hover copy off";
  hoverCopyToggle.setAttribute("aria-pressed", String(state.autoCopyOnHover));
  hoverDelaySelect.value = String(state.hoverDelayMs);

  const items = state.items.filter((item) => {
    if (!query) {
      return true;
    }
    const haystack = `${item.text} ${item.source?.title || ""} ${item.source?.host || ""}`.toLowerCase();
    return haystack.includes(query);
  });

  itemsContainer.replaceChildren();

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = query
      ? "No clips match the current search."
      : "Copy text in any tab, or use Add from clipboard.";
    itemsContainer.append(empty);
  } else {
    items.forEach((item) => {
      const node = itemTemplate.content.firstElementChild.cloneNode(true);
      node.querySelector(".item-meta").textContent = formatMeta(item);
      node.querySelector(".item-text").textContent = item.text;
      const itemMain = node.querySelector(".item-main");
      itemMain.addEventListener("click", () => copyItem(item));
      itemMain.addEventListener("mouseenter", () => scheduleHoverCopy(item));
      itemMain.addEventListener("mouseleave", cancelHoverCopy);
      node.querySelector(".delete-button").addEventListener("click", () => removeItem(item.id));
      itemsContainer.append(node);
    });
  }

  if (!state.items.length) {
    setStatus(state.captureEnabled ? "Waiting for copied text." : "Auto capture is paused.");
  }
}

async function copyItem(item) {
  cancelHoverCopy();
  await navigator.clipboard.writeText(item.text);
  setStatus(`Copied clip from ${item.source?.host || "Chrome"}.`);
}

function scheduleHoverCopy(item) {
  cancelHoverCopy();
  if (!state.autoCopyOnHover) {
    return;
  }
  setStatus(`Hovering will copy in ${(state.hoverDelayMs / 1000).toFixed(1)}s.`);
  hoverTimer = window.setTimeout(() => {
    hoverTimer = null;
    copyItem(item).catch(() => {
      setStatus("Chrome blocked clipboard write.");
    });
  }, state.hoverDelayMs);
}

function cancelHoverCopy() {
  if (hoverTimer !== null) {
    window.clearTimeout(hoverTimer);
    hoverTimer = null;
  }
}

async function removeItem(id) {
  const response = await sendMessage({ type: "delete-item", id });
  state = response.state;
  setStatus("Deleted clip.");
  render();
}

function formatMeta(item) {
  const timestamp = new Date(item.createdAt);
  const time = Number.isNaN(timestamp.getTime())
    ? "Now"
    : timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return `${item.source?.host || "Chrome"} • ${time}`;
}

function setStatus(message) {
  status.textContent = message;
}
