# QA Matrix

## Core Launch

| Area | Scenario | Expected Result |
|---|---|---|
| Launch | Run `pythonw dynaclip.py` | App starts with no visible console |
| Launch | Run built `dist/DynaClip.exe` | App starts with tray icon and no error dialogs |
| Single instance | Launch app twice | Second launch shows already-running message |

## Dynamic Island

| Area | Scenario | Expected Result |
|---|---|---|
| Reveal | Move pointer to top 5px of monitor | Compact island appears on that monitor |
| Expand | Click compact island | Island expands with animation |
| Collapse | Move away / press `Esc` | Island collapses and hides after delay |
| Hotkey | Press `Ctrl+Shift+Space` | Island toggles open/collapsed |

## Clipboard Formats

| Area | Scenario | Expected Result |
|---|---|---|
| Text | Copy text and add/capture it | Text item appears in history |
| Text restore | Click text item | Clipboard contains original text |
| Files | Copy one or more files in Explorer | File item appears in history |
| Files restore | Click file item | Clipboard contains original file list |
| Image | Copy bitmap image | Image item appears in history |
| Image restore | Click image item | Clipboard contains bitmap image |

## Detail Windows

| Area | Scenario | Expected Result |
|---|---|---|
| Open | Double-click any clip card | Pop-out detail window opens |
| Multi-window | Open multiple different clips | Multiple detail windows can stay open |
| Close | Close one detail window | Only that window closes |
| Delete | Delete clip from detail window | Clip is removed and window closes |

## Settings / Persistence

| Area | Scenario | Expected Result |
|---|---|---|
| Duplicates | Toggle duplicate handling | Setting persists after restart |
| Auto-capture | Toggle auto-capture | Setting persists after restart |
| Startup | Toggle run at startup | Registry value and startup launcher update |

## Tray / Logging

| Area | Scenario | Expected Result |
|---|---|---|
| Tray left click | Click tray icon | Island toggles |
| Tray right click | Open tray menu | Menu actions appear and work |
| Logs | Use the app for several actions | `%LOCALAPPDATA%\DynaClip\logs\dynaclip.log` is written |

## Multi-monitor

| Area | Scenario | Expected Result |
|---|---|---|
| Monitor A | Trigger on monitor A | Island appears centered on monitor A |
| Monitor B | Trigger on monitor B | Island appears centered on monitor B |
| Transition | Move between monitors and trigger again | Position updates correctly |
