# hello-world
just another repository
Tongpurpurpur, wants to learn stuff and loves flat white

## Clawde — an orange-crab desktop pet 🦀

A tiny rust-orange crab that lives on your screen. It scuttles along the
bottom, blinks its eye-stalks, waves its claws, naps — and **when you click
it, it opens Claude** ([claude.ai](https://claude.ai)) in your browser. It's a
frameless, always-on-top, transparent window built with pure standard-library
`tkinter`, so there is **nothing to install** — just Python.

### Run it (Windows)

Double-click **`run_pet.bat`**, or from a terminal:

```bat
python pet.py
```

(Python for Windows already ships with `tkinter`. If `python` isn't found,
install it from python.org and tick "Add Python to PATH".)

### Play with it

| Action | What happens |
| --- | --- |
| Left-click the crab | Opens Claude — the claws pop up and a heart appears |
| Drag the crab | Pick it up and drop it anywhere |
| Right-click the crab | Menu: **Open Claude** / **Come here** / **Sit & stay** / **Quit** |
| Press `Esc` | Quit |

Left on its own it decides what to do: scuttles to a random spot, stands and
breathes, or curls up for a nap (watch for the floating `z`).

### Make it yours

- **Change what a click opens:** edit the one line `LAUNCH_URL = "https://claude.ai"`
  near the top of [`pet.py`](pet.py) — point it at any URL.
- **Recolor / reshape it:** the crab is drawn with canvas shapes (no image
  assets); tweak the palette constants or the `draw()` method.

### Notes

- The transparent, shaped window relies on a Windows-only tkinter feature
  (`-transparentcolor`). On macOS/Linux it still runs, but the crab sits on a
  solid square instead of floating freely.
- Heads-up: Claude doesn't have an official orange-crab mascot — the real ones
  are the blue Claude Code cloud-robot and Anthropic's rust-orange sparkle.
  This crab just borrows Claude's signature orange. 🦀
