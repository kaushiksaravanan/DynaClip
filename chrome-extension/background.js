const STORAGE_KEY = "clipboardState";
const MAX_ITEMS = 50;

chrome.runtime.onInstalled.addListener(async () => {
  await ensureState();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender)
    .then((result) => sendResponse({ ok: true, ...result }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));
  return true;
});

async function handleMessage(message, sender) {
  switch (message?.type) {
    case "capture-copy":
      return captureCopy(message.payload, sender);
    case "get-state":
      return { state: await getState() };
    case "add-text":
      return { state: await addItem(message.text, message.meta) };
    case "delete-item":
      return { state: await deleteItem(message.id) };
    case "clear-items":
      return { state: await updateState((state) => ({ ...state, items: [] })) };
    case "set-capture-enabled":
      return {
        state: await updateState((state) => ({
          ...state,
          captureEnabled: Boolean(message.enabled)
        }))
      };
    case "set-hover-settings":
      return {
        state: await updateState((state) => ({
          ...state,
          autoCopyOnHover: Boolean(message.enabled),
          hoverDelayMs: normalizeHoverDelay(message.delayMs)
        }))
      };
    default:
      throw new Error(`Unsupported message: ${message?.type ?? "unknown"}`);
  }
}

async function captureCopy(payload, sender) {
  const text = normalizeText(payload?.text);
  if (!text) {
    return { state: await getState() };
  }

  const state = await getState();
  if (!state.captureEnabled) {
    return { state };
  }

  const source = buildSource(payload, sender);
  return { state: await addItem(text, source) };
}

function buildSource(payload, sender) {
  const tab = sender?.tab;
  const url = payload?.url || tab?.url || "";
  let host = "Chrome";

  try {
    host = url ? new URL(url).host : host;
  } catch {
    host = "Chrome";
  }

  return {
    title: payload?.title || tab?.title || host,
    url,
    host
  };
}

function normalizeText(value) {
  if (typeof value !== "string") {
    return "";
  }
  return value.replace(/\s+/g, " ").trim();
}

async function addItem(text, meta = {}) {
  return updateState((state) => {
    const normalized = normalizeText(text);
    if (!normalized) {
      return state;
    }

    const duplicateIndex = state.items.findIndex((item) => item.text === normalized);
    const duplicate = duplicateIndex >= 0 ? state.items[duplicateIndex] : null;
    const items = state.items.filter((item) => item.text !== normalized);

    items.unshift({
      id: duplicate?.id || `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      text: normalized,
      createdAt: new Date().toISOString(),
      source: {
        title: meta.title || meta.host || "Chrome",
        url: meta.url || "",
        host: meta.host || "Chrome"
      }
    });

    return {
      ...state,
      items: items.slice(0, MAX_ITEMS)
    };
  });
}

async function deleteItem(id) {
  return updateState((state) => ({
    ...state,
    items: state.items.filter((item) => item.id !== id)
  }));
}

async function ensureState() {
  const state = await getState();
  await chrome.storage.session.set({ [STORAGE_KEY]: state });
  return state;
}

async function getState() {
  const stored = await chrome.storage.session.get(STORAGE_KEY);
  const state = stored[STORAGE_KEY];
  return {
    items: Array.isArray(state?.items) ? state.items : [],
    captureEnabled: state?.captureEnabled !== false,
    autoCopyOnHover: Boolean(state?.autoCopyOnHover),
    hoverDelayMs: normalizeHoverDelay(state?.hoverDelayMs)
  };
}

function normalizeHoverDelay(value) {
  const allowed = new Set([400, 800, 1200, 2000]);
  const numeric = Number(value);
  return allowed.has(numeric) ? numeric : 800;
}

async function updateState(updater) {
  const current = await getState();
  const next = updater(current);
  await chrome.storage.session.set({ [STORAGE_KEY]: next });
  return next;
}
