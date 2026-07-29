"""
Flat White -- a tiny desktop pet.

A frameless, always-on-top, transparent window with a little creature that
wanders along the bottom of your screen, blinks, dozes off, and reacts when
you poke it. Pure standard-library tkinter, so there is nothing to install.

Controls
--------
  * Left-click the pet ....... poke it (it perks up and shows a heart)
  * Drag the pet ............. pick it up and drop it anywhere
  * Right-click the pet ...... menu: Come here / Sit & stay / Quit
  * Esc ...................... quit

Runs best on Windows, where tkinter can paint a truly transparent window.
See run_pet.bat for a double-click launcher.
"""

import random
import tkinter as tk

# The "chroma key" colour. Anything painted in this colour becomes fully
# transparent on Windows, which is how we get a shaped, borderless pet.
TRANSPARENT = "#ff00ff"

SIZE = 140            # window is SIZE x SIZE pixels
FPS = 33              # animation tick in milliseconds (~30 fps)
WALK_SPEED = 2.2      # pixels per tick while walking

# A soft "flat white" palette, in honour of the README.
BODY = "#f4f1ec"
BODY_SHADE = "#ddd7cc"
CHEEK = "#f6c9c0"
DARK = "#3a3a3a"
HEART = "#ff6b81"


class Pet:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Flat White")
        self.root.overrideredirect(True)          # no title bar / borders
        self.root.attributes("-topmost", True)     # float above everything
        try:
            # Windows: make the key colour transparent + drop taskbar entry.
            self.root.attributes("-transparentcolor", TRANSPARENT)
            self.root.attributes("-toolwindow", True)
        except tk.TclError:
            pass  # non-Windows: the pet just shows on a solid square.

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
        self.target_x = self.x     # where a walking pet is heading
        self.timer = 90            # ticks until the next decision
        self.bob = 0.0             # phase for the idle bob / walk cycle
        self.blink = 0             # >0 means eyes are currently closed
        self.happy = 0             # >0 means showing a heart
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
        # A small movement counts as a poke rather than a drag.
        moved = abs(event.x_root - self._press_x) + abs(event.y_root - self._press_y)
        if moved < 6:
            self.poke()
        else:
            self.state = "idle"
            self.timer = 60

    def on_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def poke(self):
        self.state = "happy"
        self.happy = 24
        self.timer = 24
        self.blink = 0

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
        import math
        c = self.canvas
        c.delete("all")
        cx = SIZE / 2

        walking = self.state == "walking"
        sleeping = self.state == "sleeping"

        # Vertical bob: a gentle breathe when idle, a bouncier step when walking.
        amp = 6 if walking else 2.5
        bob = abs(math.sin(self.bob)) * amp
        base = SIZE - 24          # ground line the feet rest on
        top = base - 72 - bob     # top of the head
        body_cx = cx

        # Soft shadow on the "floor".
        squash = 6 + bob
        c.create_oval(cx - 34, base - 4, cx + 34, base + 8 - squash * 0.2,
                      fill=BODY_SHADE, outline="")

        # Feet (little steps alternate while walking).
        step = math.sin(self.bob) * (5 if walking else 0)
        for side, phase in ((-1, step), (1, -step)):
            fx = body_cx + side * 15
            c.create_oval(fx - 9, base - 8 + phase, fx + 9, base + 6 + phase,
                          fill=BODY, outline=BODY_SHADE)

        # Body -- a rounded blob.
        c.create_oval(body_cx - 40, top, body_cx + 40, base + 4,
                      fill=BODY, outline=BODY_SHADE, width=2)

        # Ears.
        for side in (-1, 1):
            ex = body_cx + side * 26
            c.create_polygon(
                ex - 12, top + 20, ex + 12, top + 20, ex + side * 4, top - 12,
                fill=BODY, outline=BODY_SHADE, smooth=True,
            )

        eye_y = top + 34
        if sleeping:
            # Closed, content eyes + floating "z".
            for side in (-1, 1):
                ex = body_cx + side * 16
                c.create_line(ex - 7, eye_y, ex + 7, eye_y, fill=DARK, width=3)
            zz = int(self.bob * 4) % 3
            c.create_text(body_cx + 34, top - 6 - zz * 6,
                          text="z", fill=DARK, font=("Segoe UI", 10 + zz * 2, "bold"))
        else:
            closed = self.blink > 0
            for side in (-1, 1):
                ex = body_cx + side * 16
                if closed:
                    c.create_line(ex - 7, eye_y, ex + 7, eye_y, fill=DARK, width=3)
                else:
                    look = self.facing * 2
                    c.create_oval(ex - 7, eye_y - 8, ex + 7, eye_y + 8,
                                  fill="white", outline=DARK, width=1)
                    c.create_oval(ex - 3 + look, eye_y - 3, ex + 3 + look, eye_y + 5,
                                  fill=DARK, outline="")
            # Cheeks.
            for side in (-1, 1):
                cxk = body_cx + side * 30
                c.create_oval(cxk - 6, eye_y + 8, cxk + 6, eye_y + 18,
                              fill=CHEEK, outline="")

        # Mouth.
        my = eye_y + 16
        if self.state == "happy":
            c.create_arc(body_cx - 9, my - 4, body_cx + 9, my + 12,
                         start=200, extent=140, style="arc", outline=DARK, width=2)
        elif not sleeping:
            c.create_line(body_cx - 5, my, body_cx, my + 4, body_cx + 5, my,
                          fill=DARK, width=2, smooth=True)

        # Heart pop when poked.
        if self.happy > 0:
            hy = top - 10 - (24 - self.happy)
            self._heart(body_cx + 26, hy, 7)

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
