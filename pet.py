"""
Clawde -- a tiny orange-crab desktop pet.

A frameless, always-on-top, transparent window with a little rust-orange crab
that scuttles along the bottom of your screen, blinks, waves its claws, naps,
and -- when you click it -- launches Claude in your browser. Pure
standard-library tkinter, so there is nothing to install.

Controls
--------
  * Left-click the crab ...... launch Claude (claude.ai)
  * Drag the crab ............ pick it up and drop it anywhere
  * Right-click the crab ..... menu: Open Claude / Come here / Sit & stay / Quit
  * Esc ...................... quit

Runs best on Windows, where tkinter can paint a truly transparent window.
See run_pet.bat for a double-click launcher.
"""

import math
import random
import tkinter as tk
import webbrowser

# What a click opens. Point this at anything -- a URL (opens in your default
# browser) works everywhere.
LAUNCH_URL = "https://claude.ai"

# The "chroma key" colour. Anything painted in this colour becomes fully
# transparent on Windows, which is how we get a shaped, borderless pet.
TRANSPARENT = "#00ff00"

SIZE = 150            # window is SIZE x SIZE pixels
FPS = 33              # animation tick in milliseconds (~30 fps)
WALK_SPEED = 2.2      # pixels per tick while walking

# Claude rust-orange crab palette.
SHELL = "#e5703b"
SHELL_DARK = "#c1531f"
SHELL_LIGHT = "#f4a065"
LEG = "#c1531f"
EYE_WHITE = "#fff6ef"
DARK = "#3a2118"
HEART = "#ff8fa3"


class Pet:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Clawde")
        self.root.overrideredirect(True)          # no title bar / borders
        self.root.attributes("-topmost", True)     # float above everything
        try:
            # Windows: make the key colour transparent + drop taskbar entry.
            self.root.attributes("-transparentcolor", TRANSPARENT)
            self.root.attributes("-toolwindow", True)
        except tk.TclError:
            pass  # non-Windows: the crab just shows on a solid square.

        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # Start near the bottom-right, "standing" on the taskbar line.
        self.x = self.sw - SIZE - 40
        self.y = self.sh - SIZE - 48
        self.root.geometry(f"{SIZE}x{SIZE}+{int(self.x)}+{int(self.y)}")

        self.canvas = tk.Canvas(
            self.root, width=SIZE, height=SIZE,
            bg=TRANSPARENT, highlightthickness=0,
        )
        self.canvas.pack()

        # --- animation / behaviour state ------------------------------------
        self.facing = 1            # 1 = right, -1 = left
        self.state = "idle"        # idle | walking | sleeping | happy
        self.target_x = self.x     # where a walking crab is heading
        self.timer = 90            # ticks until the next decision
        self.bob = 0.0             # phase for the idle bob / walk cycle
        self.blink = 0             # >0 means eyes are currently closed
        self.happy = 0             # >0 means claws-up + heart (just launched)
        self.cooldown = 0          # ticks before a click can launch again
        self.dragging = False
        self.drag_dx = 0
        self.drag_dy = 0

        # --- input ----------------------------------------------------------
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_menu)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Open Claude", command=self.launch)
        self.menu.add_command(label="Come here", command=self.wander)
        self.menu.add_command(label="Sit & stay", command=self.sit)
        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self.root.destroy)

        self.tick()

    # ---------------------------------------------------------------- input
    def on_press(self, event):
        self.dragging = True
        self.drag_dx = event.x
        self.drag_dy = event.y
        self._press_x = event.x_root
        self._press_y = event.y_root

    def on_drag(self, event):
        if not self.dragging:
            return
        self.x = event.x_root - self.drag_dx
        self.y = event.y_root - self.drag_dy
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

    def on_release(self, event):
        self.dragging = False
        # A small movement counts as a click (launch), not a drag.
        moved = abs(event.x_root - self._press_x) + abs(event.y_root - self._press_y)
        if moved < 6:
            self.launch()
        else:
            self.state = "idle"
            self.timer = 60

    def on_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def launch(self):
        # Wave the claws and open Claude, with a short cooldown so a stray
        # double click doesn't spawn two tabs.
        self.state = "happy"
        self.happy = 24
        self.timer = 24
        self.blink = 0
        if self.cooldown == 0:
            self.cooldown = 45
            try:
                webbrowser.open(LAUNCH_URL, new=2)
            except Exception:
                pass

    def wander(self):
        self.state = "walking"
        self.target_x = random.randint(20, self.sw - SIZE - 20)
        self.facing = 1 if self.target_x > self.x else -1
        self.timer = 240

    def sit(self):
        self.state = "sleeping"
        self.timer = 400

    # ------------------------------------------------------------ behaviour
    def decide(self):
        """Pick the next thing to do when the current action runs out."""
        roll = random.random()
        if roll < 0.45:
            self.wander()
        elif roll < 0.7:
            self.state = "idle"
            self.timer = random.randint(60, 150)
        else:
            self.state = "sleeping"
            self.timer = random.randint(150, 320)

    def tick(self):
        if not self.dragging:
            self.bob += 0.18
            self.timer -= 1
            if self.cooldown > 0:
                self.cooldown -= 1

            if self.state == "walking":
                dx = self.target_x - self.x
                if abs(dx) <= WALK_SPEED:
                    self.state = "idle"
                    self.timer = random.randint(50, 120)
                else:
                    step = WALK_SPEED if dx > 0 else -WALK_SPEED
                    self.facing = 1 if step > 0 else -1
                    self.x += step
                    self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

            if self.happy > 0:
                self.happy -= 1
            if self.state == "happy" and self.happy == 0:
                self.state = "idle"
                self.timer = random.randint(40, 90)

            if self.timer <= 0:
                self.decide()

            # Occasional blink while awake.
            if self.blink > 0:
                self.blink -= 1
            elif self.state != "sleeping" and random.random() < 0.02:
                self.blink = 6

        self.draw()
        self.root.after(FPS, self.tick)

    # ---------------------------------------------------------------- render
    def draw(self):
        c = self.canvas
        c.delete("all")
        cx = SIZE / 2

        walking = self.state == "walking"
        sleeping = self.state == "sleeping"

        amp = 5 if walking else 2.0
        bob = abs(math.sin(self.bob)) * amp
        base = SIZE - 18                 # ground line the legs rest on
        oy = -bob
        cy = base - 30 + oy              # centre of the shell

        # Soft shadow on the "floor".
        c.create_oval(cx - 40, base - 2, cx + 40, base + 9 - bob * 0.2,
                      fill=SHELL_DARK, outline="")

        # --- legs (3 per side, shuffle while walking) -----------------------
        shuffle = math.sin(self.bob * 2) * (4 if walking else 1)
        for side in (-1, 1):
            for i, ly in enumerate((-8, 2, 12)):
                sx = cx + side * 30
                ex = cx + side * 46
                phase = shuffle * (1 if i % 2 == 0 else -1) * side
                c.create_line(sx, cy + ly, ex, cy + ly + 10 + phase,
                              fill=LEG, width=4, capstyle="round")

        # --- claws (raised when happy) --------------------------------------
        raise_amt = 16 if self.state == "happy" else 0
        for side in (-1, 1):
            # arm
            ax = cx + side * 34
            ay = cy + 4 - raise_amt
            c.create_line(cx + side * 22, cy, ax, ay,
                          fill=SHELL, width=7, capstyle="round")
            # pincer: two overlapping ovals forming a "C"
            open_gap = 5 if (self.state == "happy" and self.happy % 8 < 4) else 2
            c.create_oval(ax + side * -8, ay - 12, ax + side * 12, ay + 2 - open_gap,
                          fill=SHELL, outline=SHELL_DARK)
            c.create_oval(ax + side * -8, ay - 1 + open_gap, ax + side * 12, ay + 12,
                          fill=SHELL, outline=SHELL_DARK)

        # --- shell ----------------------------------------------------------
        c.create_oval(cx - 42, cy - 26, cx + 42, cy + 26,
                      fill=SHELL, outline=SHELL_DARK, width=2)
        # highlight sheen
        c.create_oval(cx - 30, cy - 22, cx + 6, cy - 4, fill=SHELL_LIGHT, outline="")
        # a couple of shell speckles
        for dx, dy in ((-16, 10), (14, 8), (0, 16)):
            c.create_oval(cx + dx - 2, cy + dy - 2, cx + dx + 2, cy + dy + 2,
                          fill=SHELL_DARK, outline="")

        # --- eyes on stalks -------------------------------------------------
        for side in (-1, 1):
            ex = cx + side * 14
            stalk_top = cy - 34
            c.create_line(ex, cy - 20, ex, stalk_top, fill=SHELL_DARK, width=4)
            if sleeping or self.blink > 0:
                c.create_line(ex - 6, stalk_top, ex + 6, stalk_top, fill=DARK, width=3)
            else:
                c.create_oval(ex - 7, stalk_top - 8, ex + 7, stalk_top + 6,
                              fill=EYE_WHITE, outline=SHELL_DARK)
                look = self.facing * 2
                c.create_oval(ex - 3 + look, stalk_top - 4, ex + 3 + look, stalk_top + 3,
                              fill=DARK, outline="")

        # --- mouth ----------------------------------------------------------
        my = cy - 4
        if self.state == "happy":
            c.create_arc(cx - 10, my - 6, cx + 10, my + 10,
                         start=200, extent=140, style="arc", outline=DARK, width=2)
        elif sleeping:
            c.create_oval(cx - 3, my, cx + 3, my + 5, outline=DARK, width=2)
            zz = int(self.bob * 4) % 3
            c.create_text(cx + 34, cy - 40 - zz * 5, text="z", fill=SHELL_DARK,
                          font=("Segoe UI", 10 + zz * 2, "bold"))
        else:
            c.create_line(cx - 6, my, cx, my + 3, cx + 6, my,
                          fill=DARK, width=2, smooth=True)

        # Heart pop when clicked/launched.
        if self.happy > 0:
            hy = cy - 44 - (24 - self.happy) + oy
            self._heart(cx + 20, hy, 7)

    def _heart(self, x, y, r):
        c = self.canvas
        c.create_oval(x - r, y - r, x, y, fill=HEART, outline="")
        c.create_oval(x, y - r, x + r, y, fill=HEART, outline="")
        c.create_polygon(x - r, y - r * 0.4, x + r, y - r * 0.4, x, y + r * 1.2,
                         fill=HEART, outline="")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Pet().run()
