"""
Plant Family Quiz  —  identify plant families from photos
Controls:  [Enter] submit / next   [Ctrl+T] hint   [Esc] skip
"""

import tkinter as tk
import os, random, re
from PIL import Image, ImageTk

# ── Paths ──────────────────────────────────────────────────────────────────────

## CHANGE DIRECTORY TO WHERE YOU HAVE THE PLANTFAMILIES FOLDER SAVED ##
## should look something like this: r"C:\Users\me\Onedrive\Desktop\school\biol446\plantfamilies"
BASE_DIR  = #insert here#

TEXT_FILE = os.path.join(BASE_DIR, "family_texts.txt")
IMG_EXTS  = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}

# ── Colours & font ─────────────────────────────────────────────────────────────
BG     = "#0d1117"
CARD   = "#161b22"
ACCENT = "#6ebd5e"
RED    = "#f85149"
GOLD   = "#d29922"
TEXT   = "#e6edf3"
MUTED  = "#8b949e"
BORDER = "#30363d"
FONT   = "Segoe UI"

# ── Fuzzy string distance — allows 1 typo ─────────────────────────────────────
def levenshtein(a, b):
    a, b = a.lower(), b.lower()
    if len(a) < len(b): a, b = b, a
    prev = list(range(len(b) + 1))
    for c1 in a:
        curr = [prev[0] + 1]
        for j, c2 in enumerate(b):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(c1 != c2)))
        prev = curr
    return prev[-1]

# ── Read family descriptions from text file ───────────────────────────────────
def load_descriptions(path):
    with open(path, encoding="utf-8") as f: raw = f.read()
    result = {}
    for m in re.finditer(r"\((\w+):\s*([^)]+)\)", raw, re.IGNORECASE):
        result[m.group(1).lower()] = m.group(2).strip()
    return result

# ── List image files in a folder ──────────────────────────────────────────────
def list_images(folder):
    return [os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMG_EXTS]

# ── List sub-folders (each = one plant family) ────────────────────────────────
def list_families(base):
    return [d for d in os.listdir(base)
            if os.path.isdir(os.path.join(base, d)) and d.lower() != "__pycache__"]


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM SLIDER  —  circle thumb on a rounded line, drawn with Canvas
# ══════════════════════════════════════════════════════════════════════════════
class FancySlider(tk.Canvas):

    PAD = 14   # horizontal padding so the thumb circle doesn't clip the edge

    def __init__(self, parent, variable, from_=1.0, to=10.0,
                 resolution=0.1, command=None, **kw):
        super().__init__(parent, height=28, highlightthickness=0,
                         bg=BG, **kw)
        self._var  = variable
        self._min  = from_
        self._max  = to
        self._res  = resolution
        self._cmd  = command       # called with the new value whenever it changes
        self._drag = False

        self.bind("<Configure>",       lambda e: self._draw())
        self.bind("<Button-1>",        self._click)
        self.bind("<B1-Motion>",       self._drag_move)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", False))

    # convert a slider value to an x pixel position
    def _val_to_x(self, val):
        w = self.winfo_width()
        return self.PAD + (val - self._min) / (self._max - self._min) * (w - 2*self.PAD)

    # convert an x pixel position to a slider value (clamped + snapped to resolution)
    def _x_to_val(self, x):
        w    = self.winfo_width()
        frac = max(0.0, min(1.0, (x - self.PAD) / (w - 2*self.PAD)))
        raw  = self._min + frac * (self._max - self._min)
        return round(round(raw / self._res) * self._res, 6)   # snap to grid

    def _draw(self):
        self.delete("all")
        w  = self.winfo_width()
        if w < 4: return
        cy = self.winfo_height() // 2   # vertical centre of canvas
        tx = self._val_to_x(self._var.get())

        # full track — grey, thick, rounded ends
        self.create_line(self.PAD, cy, w - self.PAD, cy,
                         fill=BORDER, width=5, capstyle="round")

        # filled portion left of thumb — green, same thickness
        self.create_line(self.PAD, cy, tx, cy,
                         fill=ACCENT, width=5, capstyle="round")

        # thumb — solid green circle
        r = 9
        self.create_oval(tx-r, cy-r, tx+r, cy+r,
                         fill=ACCENT, outline=BG, width=2)

    def _set(self, x):
        val = self._x_to_val(x)
        self._var.set(val)
        self._draw()
        if self._cmd: self._cmd(val)    # notify caller

    def _click(self, e):
        self._drag = True
        self._set(e.x)

    def _drag_move(self, e):
        if self._drag: self._set(e.x)


# ══════════════════════════════════════════════════════════════════════════════
# SETUP DIALOG  —  shown at startup and when "Families / Edit Emphasis" is clicked
# ══════════════════════════════════════════════════════════════════════════════
class SetupDialog(tk.Toplevel):

    def __init__(self, parent, families):
        super().__init__(parent)
        self.title("Plant Family Quiz — Setup")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.grab_set()                          # block main window until closed

        self.emphasized = set()
        self._vars      = {}                     # {family_lower: BooleanVar}
        self._weight    = tk.DoubleVar(value=3.0)

        self._build(families)

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h   = min(800, sw-80), min(780, sh-80)
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")   # center on screen

        parent.wait_window(self)

    def _build(self, families):

        # ── Fancy header ─────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(22, 4))

        tk.Label(hdr, text="🌿", bg=BG, fg=ACCENT,
                 font=("Segoe UI Emoji", 28)).pack(side="left", padx=(0, 10))

        title_col = tk.Frame(hdr, bg=BG)
        title_col.pack(side="left")

        tk.Label(title_col, text="Plant Family Quiz", bg=BG, fg=TEXT,
                 font=("Georgia", 24, "bold")).pack(anchor="w")   # large serif title

        tk.Label(title_col, text="flashcard trainer", bg=BG, fg=MUTED,
                 font=("Georgia", 11, "italic")).pack(anchor="w") # small subtitle

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(12, 0))

        # ── Blurb ─────────────────────────────────────────────────────────────
        tk.Label(self, bg=BG, fg=MUTED, justify="left", wraplength=740,
                 font=(FONT, 10),
                 text=("This quiz will cycle through pictures of plants and ask you to "
                       "identify the families. Optional: check boxes for the families "
                       "you're most uncomfortable with and adjust how much they are "
                       "emphasized (you can edit this later during the quiz).")
                 ).pack(anchor="w", padx=28, pady=(10, 2))

        # ── Slider row ────────────────────────────────────────────────────────
        srow = tk.Frame(self, bg=BG)
        srow.pack(fill="x", padx=28, pady=(10, 4))

        tk.Label(srow, text="Emphasis multiplier:", bg=BG, fg=MUTED,
                 font=(FONT, 10)).pack(side="left")

        self._slider_lbl = tk.Label(srow, text="3.0×", bg=BG, fg=ACCENT,
                                     font=(FONT, 10, "bold"))
        self._slider_lbl.pack(side="right")

        def _on_slide(val):
            self._slider_lbl.config(text=f"{float(val):.1f}×")   # update label beside slider

        FancySlider(srow, variable=self._weight,
                    from_=1.0, to=10.0, resolution=0.1,
                    command=_on_slide, width=340
                    ).pack(side="left", padx=(12, 0), fill="x", expand=True)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(8, 0))

        # ── 3-column checkbox grid ────────────────────────────────────────────
        grid = tk.Frame(self, bg=BG)
        grid.pack(fill="both", expand=True, padx=28, pady=10)

        names    = sorted(families, key=str.lower)    # A → Z
        col_size = (len(names) + 2) // 3              # how many rows per column

        for col_idx in range(3):
            col = tk.Frame(grid, bg=BG)
            col.grid(row=0, column=col_idx, sticky="nw", padx=(0, 24))
            grid.columnconfigure(col_idx, weight=1)

            chunk = names[col_idx * col_size : (col_idx+1) * col_size]

            for name in chunk:
                var = tk.BooleanVar(value=False)
                self._vars[name.lower()] = var

                row = tk.Frame(col, bg=BG)
                row.pack(anchor="w", pady=1)

                tk.Checkbutton(
                    row, variable=var,
                    bg=BG, activebackground=BG,
                    fg=TEXT, activeforeground=TEXT,
                    selectcolor=BG,           # no fill colour — plain empty square
                    relief="flat", bd=0, cursor="hand2"
                ).pack(side="left")

                lbl = tk.Label(row, text=name.capitalize(),
                               bg=BG, fg=TEXT, font=(FONT, 10), cursor="hand2")
                lbl.pack(side="left")
                lbl.bind("<Button-1>", lambda e, v=var: v.set(not v.get()))  # click label = toggle

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(4, 0))

        # ── Footer ────────────────────────────────────────────────────────────
        foot = tk.Frame(self, bg=BG, pady=10)
        foot.pack(fill="x", padx=28)

        self._status = tk.Label(foot, bg=BG, fg=MUTED, font=(FONT, 10), text="")
        self._status.pack(side="left")

        tk.Button(foot, text="Start Quiz  →", bg=ACCENT, fg=BG,
                  font=(FONT, 11, "bold"), relief="flat", padx=16, pady=6,
                  activebackground="#57a84a", cursor="hand2",
                  command=self._confirm).pack(side="right")

        for var in self._vars.values():
            var.trace_add("write", lambda *_: self._update_status())
        self._update_status()
        self.bind("<Return>", lambda e: self._confirm())

    def _update_status(self):
        n = sum(1 for v in self._vars.values() if v.get())
        self._status.config(
            text="All families weighted equally" if n == 0
                 else f"{n} {'family' if n==1 else 'families'} emphasized",
            fg=MUTED if n == 0 else GOLD)

    def _confirm(self):
        self.emphasized = {k for k, v in self._vars.items() if v.get()}
        self.weight     = self._weight.get()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN QUIZ WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class PlantQuiz:

    def __init__(self, root):
        self.root = root
        self.root.title("🌿 Plant Family Quiz")
        self.root.configure(bg=BG)
        self.root.geometry("1080x760")
        self.root.minsize(720, 560)

        self.descriptions = load_descriptions(TEXT_FILE)
        self.families     = list_families(BASE_DIR)
        self.current      = None
        self._img_ref     = None    # must hold reference or image gets garbage-collected
        self.hint_on      = False
        self.revealed     = False
        self.correct      = 0
        self.total        = 0

        self.root.withdraw()                         # hide while setup dialog is open
        dlg = SetupDialog(self.root, self.families)
        self.emphasized = dlg.emphasized
        self.weight     = getattr(dlg, "weight", 3.0)
        self.root.deiconify()

        self._build_ui()
        self._next_question()

    # ── Weighted random family pick ───────────────────────────────────────────
    def _pick_family(self):
        weights = [self.weight if f.lower() in self.emphasized else 1.0
                   for f in self.families]
        return random.choices(self.families, weights=weights, k=1)[0]

    # ── Build all widgets ─────────────────────────────────────────────────────
    def _build_ui(self):
        top = tk.Frame(self.root, bg=BG, pady=8)
        top.pack(fill="x", padx=16)

        tk.Label(top, text="🌿 Plant Family Quiz", bg=BG, fg=TEXT,
                 font=(FONT, 16, "bold")).pack(side="left")

        # Button to reopen setup dialog mid-quiz
        btn = tk.Label(top, text="Families / Edit Emphasis", bg=CARD, fg=MUTED,
                       font=(FONT, 10, "bold"), padx=10, pady=4, cursor="hand2")
        btn.pack(side="right", padx=(8, 0))
        btn.bind("<Button-1>", self._open_settings)

        self.score_lbl = tk.Label(top, text="0 / 0", bg=BG, fg=MUTED,
                                   font=(FONT, 13, "bold"))
        self.score_lbl.pack(side="right")

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        img_area = tk.Frame(self.root, bg=BG)
        img_area.pack(expand=True, fill="both", padx=16, pady=(10, 4))
        self.img_lbl = tk.Label(img_area, bg=BG)
        self.img_lbl.pack(expand=True)

        self.hint_lbl = tk.Label(self.root, text="", bg=CARD, fg=GOLD,
                                  font=(FONT, 11, "italic"), wraplength=940,
                                  justify="center", pady=6, padx=12)
        self.hint_lbl.pack(fill="x", padx=16, pady=2)

        self.result_lbl = tk.Label(self.root, text="", bg=BG,
                                    font=(FONT, 14, "bold"), pady=4)
        self.result_lbl.pack()

        bottom = tk.Frame(self.root, bg=BG, pady=10)
        bottom.pack(fill="x", padx=16)

        tk.Label(bottom, text="Family:", bg=BG, fg=MUTED,
                 font=(FONT, 24)).pack(side="left", padx=(0, 6))

        self.entry = tk.Entry(bottom, font=(FONT, 26), width=26,
                              bg="#21262d", fg=TEXT, insertbackground=TEXT,
                              relief="flat", bd=4, highlightthickness=1,
                              highlightbackground=BORDER, highlightcolor=ACCENT)
        self.entry.pack(side="left", ipady=5)

        tk.Label(bottom, text="  [Enter] Submit · [Ctrl+T] Hint · [Esc] Skip",
                 bg=BG, fg=MUTED, font=(FONT, 20)).pack(side="left", padx=10)

        self.entry.bind("<Return>",   self._on_enter)
        self.root.bind("<Escape>",    self._on_escape)
        self.root.bind("<Control-t>", self._toggle_hint)
        self.root.bind("<Control-T>", self._toggle_hint)
        self.root.bind("<Configure>", self._on_resize)
        self.entry.focus_set()

    def _open_settings(self, _=None):
        dlg = SetupDialog(self.root, self.families)
        self.emphasized = dlg.emphasized
        self.weight     = getattr(dlg, "weight", self.weight)

    def _next_question(self):
        for _ in range(20):
            name = self._pick_family()
            imgs = list_images(os.path.join(BASE_DIR, name))
            if imgs: break
        else:
            self.result_lbl.config(text="⚠ No images found!", fg=RED)
            return

        self.current  = name.lower()
        self._imgpath = random.choice(imgs)
        self.hint_on  = False
        self.revealed = False

        self.hint_lbl.config(text="")
        self.result_lbl.config(text="")
        self.entry.config(state="normal", highlightbackground=BORDER)
        self.entry.delete(0, "end")
        self.entry.focus_set()
        self._show_image(self._imgpath)

    def _show_image(self, path):
        try:
            img = Image.open(path)
        except Exception as e:
            self.result_lbl.config(text=f"Can't open image: {e}", fg=RED)
            return
        aw = max(self.root.winfo_width()  - 40, 600)
        ah = max(self.root.winfo_height() - 220, 300)
        img.thumbnail((aw, ah), Image.LANCZOS)           # scale to fit, keep aspect ratio
        self._img_ref = ImageTk.PhotoImage(img)
        self.img_lbl.config(image=self._img_ref)

    def _on_resize(self, e):
        if e.widget is self.root and hasattr(self, "_imgpath"):
            self._show_image(self._imgpath)

    def _on_enter(self, _=None):
        if self.revealed: self._next_question()
        else:             self._submit()

    def _on_escape(self, _=None):
        if self.revealed: self._next_question()
        else:             self._reveal(skipped=True)

    def _submit(self):
        guess = self.entry.get().strip()
        if not guess: return
        self.total += 1
        ok = levenshtein(guess, self.current) <= 1   # 1 typo allowed
        if ok: self.correct += 1
        self._reveal(correct_guess=ok, guess=guess)
        self._update_score()

    def _reveal(self, correct_guess=None, guess="", skipped=False):
        self.revealed = True
        self.hint_lbl.config(text="")
        self.entry.config(state="disabled")
        name = self.current.capitalize()

        if skipped:
            self.result_lbl.config(text=f"⏭  Skipped — Answer: {name}   [Enter] next", fg=MUTED)
            self.entry.config(highlightbackground=MUTED)
        elif correct_guess:
            self.result_lbl.config(text=f"✓  {name} — Correct!   [Enter] next", fg=ACCENT)
            self.entry.config(highlightbackground=ACCENT)
        else:
            self.result_lbl.config(text=f'✗  "{guess}" is wrong — Answer: {name}   [Enter] next', fg=RED)
            self.entry.config(highlightbackground=RED)

        desc = self.descriptions.get(self.current, "")
        if desc: self.hint_lbl.config(text=f"{name}: {desc}")

    def _toggle_hint(self, _=None):
        if self.revealed: return
        self.hint_on = not self.hint_on
        if self.hint_on:
            desc = self.descriptions.get(self.current, "No description available.")
            self.hint_lbl.config(text=f"Hint: {desc}")
        else:
            self.hint_lbl.config(text="")

    def _update_score(self):
        pct   = int(100 * self.correct / self.total) if self.total else 0
        color = ACCENT if pct >= 70 else (GOLD if pct >= 40 else RED)
        self.score_lbl.config(text=f"{self.correct} / {self.total}  ({pct}%)", fg=color)


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)   # crisp text on HiDPI screens
    except Exception:
        pass
    PlantQuiz(root)
    root.mainloop()
