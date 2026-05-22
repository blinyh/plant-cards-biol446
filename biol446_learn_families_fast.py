"""
Plant Family Quiz  —  identify plant families from photos
Controls:  [Enter] submit / next   [Ctrl+T] hint   [Esc] skip
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
import os, sys, json, random, re, platform
from pathlib import Path
from PIL import Image, ImageTk

# ── Ask the user to locate the plantfamilies folder ───────────────────────────
def ask_for_base_dir(root_win, remembered: str = "") -> Path | None:
    msg = (
        "Please locate your 'plantfamilies' folder.\n\n"
        "This folder should contain:\n"
        "  • one sub-folder per plant family (with photos inside)\n"
        "  • family_texts.txt"
    )

    if remembered:
        msg = (
            f"Folder not found:\n{remembered}\n\n"
            "Please locate your 'plantfamilies' folder."
        )

    messagebox.showinfo("Plant Family Quiz — Setup", msg, parent=root_win)

    chosen = filedialog.askdirectory(
        title="Select your 'plantfamilies' folder",
        parent=root_win
    )

    return Path(chosen) if chosen else None

def resolve_base_dir(root_win) -> Path:
    chosen = ask_for_base_dir(root_win)

    if not chosen:
        messagebox.showerror(
            "No folder selected",
            "Cannot start without a folder. Exiting."
        )
        root_win.destroy()
        sys.exit(1)

    return chosen

# ── Platform font name ────────────────────────────────────────────────────────
FONT = "SF Pro Display" if platform.system() == "Darwin" else "Segoe UI"

IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}

# ── Colours ───────────────────────────────────────────────────────────────────
BG     = "#0d1117"
CARD   = "#161b22"
ACCENT = "#6ebd5e"
RED    = "#f85149"
GOLD   = "#d29922"
TEXT   = "#e6edf3"
MUTED  = "#8b949e"
BORDER = "#30363d"

# ── Font scaling ──────────────────────────────────────────────────────────────
# All sizes are defined at the reference width; they scale proportionally.
REF_W = 1080   # design width in pixels

# Base sizes at REF_W
_BASE = dict(title=16, score=13, btn=10, hint=11, result=14,
             label=22, entry=24, controls=11)

def _scaled(base_size: int, width: int) -> int:
    factor = max(0.55, min(2.0, width / REF_W))   # clamp so it never gets silly
    return max(8, round(base_size * factor))

# ── Helpers ───────────────────────────────────────────────────────────────────
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

def load_descriptions(path: Path):
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    result = {}
    for m in re.finditer(r"\((\w+):\s*([^)]+)\)", raw, re.IGNORECASE):
        result[m.group(1).lower()] = m.group(2).strip()
    return result

def list_images(folder: Path):
    try:
        return [folder / f for f in os.listdir(folder)
                if Path(f).suffix.lower() in IMG_EXTS]
    except Exception:
        return []

def list_families(base: Path):
    try:
        return [d for d in os.listdir(base)
                if (base / d).is_dir() and d.lower() != "__pycache__"]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM SLIDER
# ══════════════════════════════════════════════════════════════════════════════
class FancySlider(tk.Canvas):
    PAD = 14

    def __init__(self, parent, variable, from_=1.0, to=10.0,
                 resolution=0.1, command=None, **kw):
        super().__init__(parent, height=28, highlightthickness=0, bg=BG, **kw)
        self._var  = variable
        self._min  = from_
        self._max  = to
        self._res  = resolution
        self._cmd  = command
        self._drag = False
        self.bind("<Configure>",       lambda e: self._draw())
        self.bind("<Button-1>",        self._click)
        self.bind("<B1-Motion>",       self._drag_move)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", False))

    def _val_to_x(self, val):
        w = self.winfo_width()
        return self.PAD + (val - self._min) / (self._max - self._min) * (w - 2*self.PAD)

    def _x_to_val(self, x):
        w    = self.winfo_width()
        frac = max(0.0, min(1.0, (x - self.PAD) / (w - 2*self.PAD)))
        raw  = self._min + frac * (self._max - self._min)
        return round(round(raw / self._res) * self._res, 6)

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 4: return
        cy = self.winfo_height() // 2
        tx = self._val_to_x(self._var.get())
        self.create_line(self.PAD, cy, w - self.PAD, cy,
                         fill=BORDER, width=5, capstyle="round")
        self.create_line(self.PAD, cy, tx, cy,
                         fill=ACCENT, width=5, capstyle="round")
        r = 9
        self.create_oval(tx-r, cy-r, tx+r, cy+r, fill=ACCENT, outline=BG, width=2)

    def _set(self, x):
        val = self._x_to_val(x)
        self._var.set(val)
        self._draw()
        if self._cmd: self._cmd(val)

    def _click(self, e):
        self._drag = True
        self._set(e.x)

    def _drag_move(self, e):
        if self._drag: self._set(e.x)


# ══════════════════════════════════════════════════════════════════════════════
# SETUP DIALOG
# ══════════════════════════════════════════════════════════════════════════════
class SetupDialog(tk.Toplevel):

    def __init__(self, parent, families):
        super().__init__(parent)
        self.title("Plant Family Quiz — Setup")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.grab_set()

        self.emphasized = set()
        self._vars      = {}
        self._weight    = tk.DoubleVar(value=3.0)

        self._build(families)

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h   = min(800, sw-80), min(780, sh-80)
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        parent.wait_window(self)

    def _build(self, families):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(22, 4))

        emoji_font = ("Apple Color Emoji" if platform.system() == "Darwin"
                      else "Segoe UI Emoji", 28)
        tk.Label(hdr, text="🌿", bg=BG, fg=ACCENT,
                 font=emoji_font).pack(side="left", padx=(0, 10))

        title_col = tk.Frame(hdr, bg=BG)
        title_col.pack(side="left")
        tk.Label(title_col, text="Plant Family Quiz", bg=BG, fg=TEXT,
                 font=("Georgia", 24, "bold")).pack(anchor="w")
        tk.Label(title_col, text="flashcard trainer", bg=BG, fg=MUTED,
                 font=("Georgia", 11, "italic")).pack(anchor="w")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(12, 0))

        tk.Label(self, bg=BG, fg=MUTED, justify="left", wraplength=740,
                 font=(FONT, 16),
                 text=("This quiz will cycle through pictures of plants and ask you to "
                       "identify the families. Optional: check boxes for the families "
                       "you're most uncomfortable with and adjust how much they are "
                       "emphasized (you can edit this later during the quiz).")
                 ).pack(anchor="w", padx=28, pady=(10, 2))

        srow = tk.Frame(self, bg=BG)
        srow.pack(fill="x", padx=28, pady=(10, 4))
        tk.Label(srow, text="Emphasis multiplier:", bg=BG, fg=MUTED,
                 font=(FONT, 16)).pack(side="left")

        self._slider_lbl = tk.Label(srow, text="3.0×", bg=BG, fg=ACCENT,
                                     font=(FONT, 10, "bold"))
        self._slider_lbl.pack(side="right")

        def _on_slide(val):
            self._slider_lbl.config(text=f"{float(val):.1f}×")

        FancySlider(srow, variable=self._weight, from_=1.0, to=10.0,
                    resolution=0.1, command=_on_slide, width=340
                    ).pack(side="left", padx=(12, 0), fill="x", expand=True)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(8, 0))

        grid = tk.Frame(self, bg=BG)
        grid.pack(fill="both", expand=True, padx=28, pady=10)

        names    = sorted(families, key=str.lower)
        col_size = (len(names) + 2) // 3

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
                tk.Checkbutton(row, variable=var, bg=BG, activebackground=BG,
                               fg=TEXT, activeforeground=TEXT, selectcolor=BG,
                               relief="flat", bd=0, cursor="hand2").pack(side="left")
                lbl = tk.Label(row, text=name.capitalize(),
                               bg=BG, fg=TEXT, font=(FONT, 16), cursor="hand2")
                lbl.pack(side="left")
                lbl.bind("<Button-1>", lambda e, v=var: v.set(not v.get()))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(4, 0))

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
        self.root.minsize(600, 440)

        self.root.withdraw()
        self.BASE_DIR  = resolve_base_dir(self.root)
        self.TEXT_FILE = self.BASE_DIR / "family_texts.txt"

        self.descriptions = load_descriptions(self.TEXT_FILE)
        self.families     = list_families(self.BASE_DIR)

        if not self.families:
            messagebox.showerror(
                "No families found",
                f"No sub-folders found in:\n{self.BASE_DIR}\n\nPlease check the folder and restart.",
                parent=self.root,
            )
            self.root.destroy()
            sys.exit(1)

        self.current  = None
        self._img_ref = None
        self.hint_on  = False
        self.revealed = False
        self.correct  = 0
        self.total    = 0

        dlg = SetupDialog(self.root, self.families)
        self.emphasized = dlg.emphasized
        self.weight     = getattr(dlg, "weight", 3.0)
        self.root.deiconify()

        # ── Named Font objects — mutated in-place on resize ───────────────────
        self._f_title    = tkfont.Font(family=FONT, size=16, weight="bold")
        self._f_score    = tkfont.Font(family=FONT, size=13, weight="bold")
        self._f_btn      = tkfont.Font(family=FONT, size=10, weight="bold")
        self._f_hint     = tkfont.Font(family=FONT, size=11, slant="italic")
        self._f_result   = tkfont.Font(family=FONT, size=14, weight="bold")
        self._f_label    = tkfont.Font(family=FONT, size=22)
        self._f_entry    = tkfont.Font(family=FONT, size=24)
        self._f_controls = tkfont.Font(family=FONT, size=11)

        self._build_ui()
        self._next_question()

        # Trigger an initial scale pass once the window is actually drawn
        self.root.after(50, lambda: self._scale_fonts(self.root.winfo_width()))

    # ── Font scaling ──────────────────────────────────────────────────────────
    def _scale_fonts(self, width: int):
        self._f_title   .config(size=_scaled(_BASE["title"],    width))
        self._f_score   .config(size=_scaled(_BASE["score"],    width))
        self._f_btn     .config(size=_scaled(_BASE["btn"],      width))
        self._f_hint    .config(size=_scaled(_BASE["hint"],     width))
        self._f_result  .config(size=_scaled(_BASE["result"],   width))
        self._f_label   .config(size=_scaled(_BASE["label"],    width))
        self._f_entry   .config(size=_scaled(_BASE["entry"],    width))
        self._f_controls.config(size=_scaled(_BASE["controls"], width))

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        top = tk.Frame(self.root, bg=BG, pady=8)
        top.pack(fill="x", padx=16)

        tk.Label(top, text="🌿 Plant Family Quiz", bg=BG, fg=TEXT,
                 font=self._f_title).pack(side="left")

        btn = tk.Label(top, text="Families / Edit Emphasis", bg=CARD, fg=MUTED,
                       font=self._f_btn, padx=10, pady=4, cursor="hand2")
        btn.pack(side="right", padx=(8, 0))
        btn.bind("<Button-1>", self._open_settings)

        self.score_lbl = tk.Label(top, text="0 / 0", bg=BG, fg=MUTED,
                                   font=self._f_score)
        self.score_lbl.pack(side="right")

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        img_area = tk.Frame(self.root, bg=BG)
        img_area.pack(expand=True, fill="both", padx=16, pady=(10, 4))
        self.img_lbl = tk.Label(img_area, bg=BG)
        self.img_lbl.pack(expand=True)

        self.hint_lbl = tk.Label(self.root, text="", bg=CARD, fg=GOLD,
                                  font=self._f_hint, wraplength=940,
                                  justify="center", pady=6, padx=12)
        self.hint_lbl.pack(fill="x", padx=16, pady=2)

        self.result_lbl = tk.Label(self.root, text="", bg=BG,
                                    font=self._f_result, pady=4)
        self.result_lbl.pack()

        bottom = tk.Frame(self.root, bg=BG, pady=10)
        bottom.pack(fill="x", padx=16)

        tk.Label(bottom, text="Family:", bg=BG, fg=MUTED,
                 font=self._f_label).pack(side="left", padx=(0, 6))

        self.entry = tk.Entry(bottom, font=self._f_entry, width=22,
                              bg="#21262d", fg=TEXT, insertbackground=TEXT,
                              relief="flat", bd=4, highlightthickness=1,
                              highlightbackground=BORDER, highlightcolor=ACCENT)
        self.entry.pack(side="left", ipady=5)

        tk.Label(bottom, text="  [Enter] Submit · [Ctrl+T] Hint · [Esc] Skip",
                 bg=BG, fg=MUTED, font=self._f_controls).pack(side="left", padx=10)

        self.entry.bind("<Return>",   self._on_enter)
        self.root.bind("<Escape>",    self._on_escape)
        self.root.bind("<Control-t>", self._toggle_hint)
        self.root.bind("<Control-T>", self._toggle_hint)
        self.root.bind("<Configure>", self._on_resize)
        self.entry.focus_set()

    # ── Resize handler ────────────────────────────────────────────────────────
    _last_w = 0

    def _on_resize(self, e):
        if e.widget is not self.root:
            return
        # Redraw image every resize
        if hasattr(self, "_imgpath"):
            self._show_image(self._imgpath)
        # Only rescale fonts when width actually changes (avoids spam)
        if e.width != self._last_w:
            self._last_w = e.width
            self._scale_fonts(e.width)

    # ── Folder management ─────────────────────────────────────────────────────
    def _change_folder(self, _=None):
        chosen = filedialog.askdirectory(
            title="Select your 'plantfamilies' folder", parent=self.root)
        if not chosen:
            return
        self.BASE_DIR     = Path(chosen)
        self.TEXT_FILE    = self.BASE_DIR / "family_texts.txt"
        self.families     = list_families(self.BASE_DIR)
        self.descriptions = load_descriptions(self.TEXT_FILE)
        self._next_question()

    def _open_settings(self, _=None):
        dlg = SetupDialog(self.root, self.families)
        self.emphasized = dlg.emphasized
        self.weight     = getattr(dlg, "weight", self.weight)

    # ── Quiz logic ────────────────────────────────────────────────────────────
    def _pick_family(self):
        weights = [self.weight if f.lower() in self.emphasized else 1.0
                   for f in self.families]
        return random.choices(self.families, weights=weights, k=1)[0]

    def _next_question(self):
        for _ in range(20):
            name = self._pick_family()
            imgs = list_images(self.BASE_DIR / name)
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

    def _show_image(self, path: Path):
        try:
            img = Image.open(path)
        except Exception as e:
            self.result_lbl.config(text=f"Can't open image: {e}", fg=RED)
            return
        aw = max(self.root.winfo_width()  - 40, 400)
        ah = max(self.root.winfo_height() - 200, 250)
        img.thumbnail((aw, ah), Image.LANCZOS)
        self._img_ref = ImageTk.PhotoImage(img)
        self.img_lbl.config(image=self._img_ref)

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
        ok = levenshtein(guess, self.current) <= 1
        if ok: self.correct += 1
        self._reveal(correct_guess=ok, guess=guess)
        self._update_score()

    def _reveal(self, correct_guess=None, guess="", skipped=False):
        self.revealed = True
        self.hint_lbl.config(text="")
        self.entry.config(state="disabled")
        name = self.current.capitalize()

        if skipped:
            self.result_lbl.config(
                text=f"⏭  Skipped — Answer: {name}   [Enter] next", fg=MUTED)
            self.entry.config(highlightbackground=MUTED)
        elif correct_guess:
            self.result_lbl.config(
                text=f"✓  {name} — Correct!   [Enter] next", fg=ACCENT)
            self.entry.config(highlightbackground=ACCENT)
        else:
            self.result_lbl.config(
                text=f'✗  "{guess}" is wrong — Answer: {name}   [Enter] next', fg=RED)
            self.entry.config(highlightbackground=RED)

        desc = self.descriptions.get(self.current, "")
        if desc:
            self.hint_lbl.config(text=f"{name}: {desc}")

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
        self.score_lbl.config(
            text=f"{self.correct} / {self.total}  ({pct}%)", fg=color)


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()

    if platform.system() == "Windows":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    PlantQuiz(root)
    root.mainloop()