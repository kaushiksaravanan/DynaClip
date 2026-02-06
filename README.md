# DynaClip 📋

**Your clipboard, but better.**

Ever copied something, then copied something else, and lost that first thing forever? Yeah, we've all been there. DynaClip remembers everything you copy so you don't have to.

---

## What is it?

DynaClip is a tiny clipboard history tool that lives at the top of your screen. Just move your mouse to the top edge—boom, there it is. Move away, and it hides. Simple.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 📋 DynaClip    [＋ Add] [⚙]    🔍 Search...    │ item1 │ item2 │ item3 │ │
└──────────────────────────────────────────────────────────────────────────┘
```

## Why you'll like it

- **It stays out of your way** — Only shows up when you need it
- **Works on all your monitors** — Got 2 screens? 3? It follows your mouse
- **Looks good** — Automatically matches your Windows dark/light theme
- **Privacy first** — Nothing saved to disk. Close the app, history's gone
- **Fast** — Click any item to copy it back. That's it.

---

## Getting Started

### Just want to run it?

Double-click **`DynaClip.bat`** and you're done.

(Make sure you have Python installed. Most Windows machines do these days.)

### Want a standalone .exe?

```
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name DynaClip dynaclip.py
```

You'll find it in the `dist` folder.

> ⚠️ **Heads up:** Windows might complain about the .exe (it's a false positive—happens with all PyInstaller apps). Either tell your antivirus to chill, or just stick with the .bat file.

---

## How to use it

| What you want | What you do |
|---------------|-------------|
| See your clipboard history | Move mouse to top of screen |
| Hide it | Move mouse away |
| Reuse something you copied | Click on it |
| Delete something | Hit the × button |
| Find something specific | Start typing in the search box |
| Change settings | Click the ⚙ gear |
| Quit | Gear → Exit |

---

## Settings

Click the ⚙ to:

- **Clear All** — Wipe your history clean
- **Allow Duplicates** — Copied the same thing twice? Your call if you want both
- **Exit** — Close DynaClip

---

## Good to know

**Is it safe?**
Yes. It doesn't save anything to files, doesn't connect to the internet, and doesn't run any background stuff. Your clipboard history exists only in memory while the app is running.

**What's in the folder?**
```
dynaclip/
├── dynaclip.py      ← The actual app
├── DynaClip.bat     ← Double-click this to run
└── README.md        ← You're reading it
```

**It's not showing up!**
Make sure your mouse is really at the very top edge (within 5 pixels). Also check if you're in a fullscreen app—that can block it.

**Wrong monitor?**
The bar shows up on whatever monitor you trigger it from. Move your mouse to the top of the other monitor to get it there.

---

## License

MIT — Do whatever you want with it.

---

Made with ☕ and mild frustration at losing copied text one too many times.
