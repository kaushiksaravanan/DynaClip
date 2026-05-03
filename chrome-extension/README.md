# Chrome Extension Prototype

This folder contains a minimal Manifest V3 Chrome extension that mirrors the core DynaClip idea inside Chrome with a single popup.

## What it does

- Keeps copied text in one browser popup
- Stores history in `chrome.storage.session` so it clears when the browser session ends
- Auto-captures text copied from web pages and text inputs
- Lets you search, re-copy, delete, clear, and manually add the current clipboard text
- Optional auto-copy when hovering a clip for a configurable timeout

## Load it in Chrome

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `chrome-extension` folder
5. Click the DynaClip toolbar icon to open the popup

## Hover behavior

- Chrome does not support opening an extension popup just by hovering the toolbar icon.
- After the popup is open, you can enable **Hover copy** and choose a delay.
- With that enabled, hovering a clip copies it automatically after the timeout.

## Notes

- This captures text copy events from pages, not file lists or bitmap images like the Windows desktop app.
- Clipboard reads for **Add from clipboard** depend on Chrome allowing the read in the popup context.
