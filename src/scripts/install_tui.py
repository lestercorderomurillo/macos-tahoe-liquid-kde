"""Interactive terminal wizard for ``sudo ./install`` / ``sudo ./uninstall``.

Pure stdlib (curses). cli.py only enters this on a real TTY with no CLI
flags and no MTTKDE_NO_CONFIRM; any exception here makes cli.py fall
back to the classic confirm-and-flags flow, so the wizard can never
block an install. The model (``Wizard``) is curses-free and unit-tested;
only ``run_wizard`` touches the screen.
"""

from __future__ import annotations

import curses

from cli import ALL_FEATURES, DEFAULT_FEATURES, FEATURE_DESC, _coerce_int
from paths import read_version


GROUPS = [
    ("Theme", [
        "fonts", "color_schemes", "plasma_theme", "window_decorations",
        "kvantum", "icons", "cursors", "wallpapers", "global_theme",
        "layout",
    ]),
    ("KDE components", [
        "plasmoids", "globalmenu", "acrylic_glass", "sounds", "gtk",
        "sddm", "plymouth", "apps", "nautilus", "nautilus_bookmarks",
        "portals", "kconf_update",
    ]),
]

THEME_MODES = ("auto", "light", "dark")

# (key, label, lo, hi, unit)
_INT_ROWS = {
    "oled_interval": ("Shift interval", 1, 59, "min"),
    "oled_max_shift": ("Max shift", 1, 16, "px"),
}

_WARNING = {
    "install": ("In development — install at your own risk.",
                "Do not install on production / work systems."),
    "uninstall": ("This will reset your desktop to Breeze defaults.",
                  "Only the selected components are removed."),
}


def _label(key: str) -> str:
    name = key.replace("_", " ").title()
    desc = FEATURE_DESC.get(key, "")
    return f"{name} — {desc}" if desc else name


class Wizard:
    """Selection model: rows, cursor, and edits over a feature dict."""

    def __init__(self, feat: dict[str, object], mode: str = "install"):
        self.mode = mode
        self.feat: dict[str, object] = dict(feat)
        self.save = False
        self.rows: list[tuple[str, str]] = self._build_rows()
        self.cursor = 0
        if not self._selectable(self.cursor):
            self.move(1)

    def _build_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for title, keys in GROUPS:
            rows.append(("header", title))
            rows.extend(("toggle", k) for k in keys)
        if self.mode == "install":
            rows.append(("header", "Activation"))
            rows.append(("toggle", "apply_theme"))
            rows.append(("radio", "theme_mode"))
            rows.append(("toggle", "oled_care"))
            rows.append(("int", "oled_interval"))
            rows.append(("int", "oled_max_shift"))
        return rows

    def _selectable(self, i: int) -> bool:
        return 0 <= i < len(self.rows) and self.rows[i][0] != "header"

    def current(self) -> tuple[str, str]:
        return self.rows[self.cursor]

    def move(self, delta: int) -> None:
        i = self.cursor
        while True:
            i += delta
            if not 0 <= i < len(self.rows):
                return
            if self._selectable(i):
                self.cursor = i
                return

    def activate(self) -> None:
        """Space: flip a toggle or cycle a radio."""
        kind, key = self.current()
        if kind == "toggle":
            self.feat[key] = not bool(self.feat.get(key, True))
        elif kind == "radio":
            self.adjust(1)

    def adjust(self, delta: int) -> None:
        """Left/right: cycle the radio or step an int within its bounds."""
        kind, key = self.current()
        if kind == "radio":
            mode = str(self.feat.get(key, "auto"))
            i = THEME_MODES.index(mode) if mode in THEME_MODES else 0
            self.feat[key] = THEME_MODES[(i + delta) % len(THEME_MODES)]
        elif kind == "int":
            _, lo, hi, _ = _INT_ROWS[key]
            cur = _coerce_int(self.feat.get(key), lo, lo, hi)
            self.feat[key] = max(lo, min(hi, cur + delta))
        elif kind == "toggle":
            self.feat[key] = not bool(self.feat.get(key, True))

    def set_all(self, value: bool) -> None:
        for kind, key in self.rows:
            if kind == "toggle" and key != "apply_theme":
                self.feat[key] = value

    def reset(self) -> None:
        for k, v in DEFAULT_FEATURES.items():
            self.feat[k] = v

    def enabled_count(self) -> tuple[int, int]:
        toggles = [key for kind, key in self.rows if kind == "toggle"]
        return sum(bool(self.feat.get(k, True)) for k in toggles), len(toggles)

    def result(self) -> dict[str, object]:
        out = {k: v for k, v in self.feat.items() if k in DEFAULT_FEATURES}
        out["_save"] = self.save
        return out


# ── curses view ───────────────────────────────────────────────────────

_KEY_ENTER = (curses.KEY_ENTER, 10, 13)
_ESC = 27


def _put(scr, y: int, x: int, text: str, attr: int = 0) -> None:
    """Clipped addstr — writing the bottom-right cell raises curses.error."""
    h, w = scr.getmaxyx()
    if not 0 <= y < h or x >= w:
        return
    try:
        scr.addnstr(y, x, text, max(0, w - x - 1), attr)
    except curses.error:
        pass


def _row_text(wiz: Wizard, kind: str, key: str) -> str:
    if kind == "header":
        return key
    if kind == "toggle":
        mark = "x" if wiz.feat.get(key, True) else " "
        return f"[{mark}] {_label(key)}"
    if kind == "radio":
        mode = str(wiz.feat.get(key, "auto"))
        parts = " ".join(
            f"(•) {m}" if m == mode else f"( ) {m}" for m in THEME_MODES)
        return f"Theme mode:  {parts}"
    label, lo, hi, unit = _INT_ROWS[key]
    val = _coerce_int(wiz.feat.get(key), lo, lo, hi)
    return f"{label}:  ‹ {val} {unit} ›  ({lo}-{hi})"


def _draw_select(scr, wiz: Wizard, top: int) -> int:
    scr.erase()
    h, w = scr.getmaxyx()
    title = f" MacTahoe Liquid KDE {read_version()} — {wiz.mode} "
    _put(scr, 0, max(0, (w - len(title)) // 2), title,
         curses.A_BOLD | curses.A_REVERSE)
    body_top, body_h = 2, max(1, h - 4)

    # Keep the cursor visible.
    if wiz.cursor < top:
        top = wiz.cursor
    if wiz.cursor >= top + body_h:
        top = wiz.cursor - body_h + 1
    top = max(0, min(top, max(0, len(wiz.rows) - body_h)))

    for i in range(top, min(len(wiz.rows), top + body_h)):
        kind, key = wiz.rows[i]
        y = body_top + i - top
        if kind == "header":
            _put(scr, y, 2, key, curses.A_BOLD | curses.A_UNDERLINE)
            continue
        attr = curses.A_REVERSE if i == wiz.cursor else 0
        _put(scr, y, 4, _row_text(wiz, kind, key), attr)

    _put(scr, h - 1, 2,
         "space toggle · ←/→ adjust · a all · n none · r reset · "
         "Enter continue · q quit", curses.A_DIM)
    return top


def _draw_summary(scr, wiz: Wizard, cursor: int) -> list[str]:
    scr.erase()
    h, w = scr.getmaxyx()
    title = f" MacTahoe Liquid KDE {read_version()} — summary "
    _put(scr, 0, max(0, (w - len(title)) // 2), title,
         curses.A_BOLD | curses.A_REVERSE)

    warn_attr = curses.A_BOLD
    if curses.has_colors():
        warn_attr |= curses.color_pair(1)
    for i, line in enumerate(_WARNING[wiz.mode]):
        _put(scr, 2 + i, 2, line, warn_attr)

    on, total = wiz.enabled_count()
    verb = "Installing" if wiz.mode == "install" else "Removing"
    _put(scr, 5, 2, f"{verb} {on} of {total} components", curses.A_BOLD)
    off = [key for kind, key in wiz.rows
           if kind == "toggle" and not wiz.feat.get(key, True)]
    if off:
        skipped = "Skipped: " + ", ".join(k.replace("_", " ") for k in off)
        _put(scr, 6, 2, skipped, curses.A_DIM)
    y = 8
    if wiz.mode == "install":
        _put(scr, y, 2, f"Theme mode: {wiz.feat.get('theme_mode', 'auto')}")
        if wiz.feat.get("oled_care"):
            _put(scr, y + 1, 2,
                 f"OLED care: every {wiz.feat.get('oled_interval', 5)} min, "
                 f"max {wiz.feat.get('oled_max_shift', 8)} px")
        y += 3

    items = []
    if wiz.mode == "install":
        mark = "x" if wiz.save else " "
        items.append(f"[{mark}] Save selection to features.json")
    items.append("< Confirm >")
    items.append("< Back >")
    for i, item in enumerate(items):
        attr = curses.A_REVERSE if i == cursor else 0
        _put(scr, y + i, 4, item, attr)

    _put(scr, h - 1, 2,
         "space toggle · Enter select · Esc back · q quit", curses.A_DIM)
    return items


def _select_screen(scr, wiz: Wizard) -> str:
    top = 0
    while True:
        top = _draw_select(scr, wiz, top)
        ch = scr.getch()
        if ch in (curses.KEY_UP, ord("k")):
            wiz.move(-1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            wiz.move(1)
        elif ch == ord(" "):
            wiz.activate()
        elif ch in (curses.KEY_LEFT, ord("-")):
            wiz.adjust(-1)
        elif ch in (curses.KEY_RIGHT, ord("+"), ord("=")):
            wiz.adjust(1)
        elif ch == ord("a"):
            wiz.set_all(True)
        elif ch == ord("n"):
            wiz.set_all(False)
        elif ch == ord("r"):
            wiz.reset()
        elif ch in _KEY_ENTER:
            return "summary"
        elif ch in (ord("q"), _ESC):
            return "cancel"


def _summary_screen(scr, wiz: Wizard) -> str:
    cursor = 0
    while True:
        items = _draw_summary(scr, wiz, cursor)
        confirm_i = len(items) - 2
        back_i = len(items) - 1
        ch = scr.getch()
        if ch in (curses.KEY_UP, ord("k")):
            cursor = max(0, cursor - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            cursor = min(len(items) - 1, cursor + 1)
        elif ch == ord(" ") and wiz.mode == "install" and cursor == 0:
            wiz.save = not wiz.save
        elif ch in _KEY_ENTER:
            if cursor == confirm_i:
                return "done"
            if cursor == back_i:
                return "back"
            if wiz.mode == "install" and cursor == 0:
                wiz.save = not wiz.save
        elif ch == _ESC:
            return "back"
        elif ch == ord("q"):
            return "cancel"


def _run(scr, wiz: Wizard) -> dict[str, object] | None:
    curses.curs_set(0)
    scr.keypad(True)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, -1)
    screen = "select"
    while True:
        if screen == "select":
            nxt = _select_screen(scr, wiz)
            if nxt == "cancel":
                return None
            screen = "summary"
        else:
            nxt = _summary_screen(scr, wiz)
            if nxt == "cancel":
                return None
            if nxt == "back":
                screen = "select"
                continue
            return wiz.result()


def run_wizard(feat: dict[str, object],
               mode: str = "install") -> dict[str, object] | None:
    """Full-screen selection wizard. Returns the updated feature dict
    (plus a ``_save`` bool the caller pops), or None if the user quit.
    curses.wrapper restores the terminal on return or exception."""
    wiz = Wizard(feat, mode)
    return curses.wrapper(lambda scr: _run(scr, wiz))
