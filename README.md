# hello-world
just another repository
Tongpurpurpur, wants to learn stuff and loves flat white

## Flat White — a desktop pet 🐾

A tiny creature that lives on your screen. It wanders along the bottom,
blinks, dozes off, and shows a little heart when you poke it. It's a
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
| Left-click the pet | Poke it — it perks up and shows a heart |
| Drag the pet | Pick it up and drop it anywhere |
| Right-click the pet | Menu: **Come here** / **Sit & stay** / **Quit** |
| Press `Esc` | Quit |

Left on its own it decides what to do: strolls to a random spot, stands and
breathes, or curls up for a nap (watch for the floating `z`).

### Notes

- The transparent, shaped window relies on a Windows-only tkinter feature
  (`-transparentcolor`). On macOS/Linux it still runs, but the pet sits on a
  solid square instead of floating freely.
- It's a single file — [`pet.py`](pet.py). The pet is drawn with canvas shapes
  (no image assets), so tweak the palette or shapes near the top of the file
  to make it your own.
