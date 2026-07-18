"""Interactive terminal wizard for ``sudo ./install`` / ``sudo ./uninstall``.

Pure stdlib (curses). cli.py only enters this on a real TTY with no CLI
flags and no MTTKDE_NO_CONFIRM; any exception here makes cli.py fall
back to the classic confirm-and-flags flow, so the wizard can never
block an install. The model (``Wizard``) is curses-free and unit-tested;
only ``run_wizard`` / ``run_progress`` touch the screen.
"""

from __future__ import annotations

import os
import re
import sys
import threading

# curses is stdlib on most distros, but openSUSE splits it into a
# separate package (python3-curses). This module must still import so
# the model tests run and cli.py can fall back to the classic flow.
try:
    import curses
except ImportError:
    curses = None  # type: ignore[assignment]

from cli import ALL_FEATURES, DEFAULT_FEATURES, FEATURE_DESC, _coerce_int
from log import DONE_MARKER, PROGRESS_FILE
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

    def _build_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for title, keys in GROUPS:
            if rows:
                rows.append(("spacer", ""))
            rows.append(("header", title))
            rows.extend(("toggle", k) for k in keys)
        if self.mode == "install":
            rows.append(("spacer", ""))
            rows.append(("header", "Activation"))
            rows.append(("toggle", "apply_theme"))
            rows.append(("radio", "theme_mode"))
            rows.append(("toggle", "oled_care"))
            rows.append(("int", "oled_interval"))
            rows.append(("int", "oled_max_shift"))
        return rows

    def _selectable(self, i: int) -> bool:
        return (0 <= i < len(self.rows)
                and self.rows[i][0] != "spacer")

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

    def _group_keys(self, header: str) -> list[str]:
        keys, active = [], False
        for kind, key in self.rows:
            if kind == "header":
                active = key == header
            elif active and kind == "toggle":
                keys.append(key)
        return keys

    def toggle_group(self, header: str) -> None:
        """Space on a group header: all on → all off, otherwise all on."""
        keys = self._group_keys(header)
        if not keys:
            return
        all_on = all(bool(self.feat.get(k, True)) for k in keys)
        for k in keys:
            self.feat[k] = not all_on

    def activate(self) -> None:
        """Space: flip a toggle, cycle a radio, or toggle a whole group."""
        kind, key = self.current()
        if kind == "header":
            self.toggle_group(key)
        elif kind == "toggle":
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
#
# Skinned to match the CLI log palette (log.py): green ✓ accents,
# yellow values, red warnings, dim hints, and the Apple rainbow logo
# when the terminal is tall enough.

# Key constants must survive a missing curses module — the model tests
# import this file on distros without python3-curses.
_KEY_ENTER = (curses.KEY_ENTER, 10, 13) if curses is not None else (10, 13)
_ESC = 27


_P_RED, _P_GREEN, _P_YELLOW, _P_DIM = 1, 2, 3, 4
_P_RAINBOW = (5, 6, 7, 8, 9, 10)  # pairs for APPLE_ART bands, top → bottom
_P_WHITE = 11
_DYN_PAIR_START = 12  # dynamic pairs for 256-color log passthrough

_HAVE_COLOR = False
_BG = -1


def _init_colors() -> None:
    global _HAVE_COLOR, _BG
    _HAVE_COLOR = curses.has_colors()
    if not _HAVE_COLOR:
        return
    curses.start_color()
    try:
        curses.use_default_colors()
        _BG = -1
    except curses.error:
        _BG = curses.COLOR_BLACK
    c256 = curses.COLORS >= 256
    # (pair, 256-color code from log.py, basic fallback)
    palette = [
        (_P_RED, 196, curses.COLOR_RED),
        (_P_GREEN, 46, curses.COLOR_GREEN),
        (_P_YELLOW, 226, curses.COLOR_YELLOW),
        (_P_DIM, 244, curses.COLOR_WHITE),
        # Apple 1977-1998 rainbow bands (same codes as log._APPLE_RAINBOW).
        (_P_RAINBOW[0], 46, curses.COLOR_GREEN),
        (_P_RAINBOW[1], 226, curses.COLOR_YELLOW),
        (_P_RAINBOW[2], 208, curses.COLOR_YELLOW),
        (_P_RAINBOW[3], 196, curses.COLOR_RED),
        (_P_RAINBOW[4], 165, curses.COLOR_MAGENTA),
        (_P_RAINBOW[5], 33, curses.COLOR_BLUE),
        (_P_WHITE, 231, curses.COLOR_WHITE),
    ]
    for pair, code, fallback in palette:
        try:
            curses.init_pair(pair, code if c256 else fallback, _BG)
        except curses.error:
            pass


def _c(pair: int, extra: int = 0) -> int:
    attr = curses.color_pair(pair) if _HAVE_COLOR else 0
    if pair == _P_DIM and not _HAVE_COLOR:
        attr |= curses.A_DIM
    return attr | extra


def _put(scr, y: int, x: int, text: str, attr: int = 0) -> int:
    """Clipped addstr — writing the bottom-right cell raises curses.error,
    and non-UTF-8 locales raise UnicodeEncodeError on ✓/‹/█ glyphs. Skip
    the cell rather than crash the UI. Returns the x position after the
    text for segment-based drawing."""
    h, w = scr.getmaxyx()
    if not 0 <= y < h or x >= w:
        return x
    try:
        scr.addnstr(y, x, text, max(0, w - x - 1), attr)
    except (curses.error, UnicodeEncodeError):
        pass
    return x + len(text)


def _draw_header(scr) -> int:
    """Centred title line. No logo here — the rainbow Apple appears
    once, in the CLI banner printed before the TUI starts. Returns the
    first body row."""
    _, w = scr.getmaxyx()
    name = "MacTahoe Liquid KDE"
    ver = f" v{read_version()}"
    x = max(0, (w - len(name + ver)) // 2)
    x = _put(scr, 0, x, name, _c(_P_GREEN, curses.A_BOLD))
    _put(scr, 0, x, ver, curses.A_BOLD)
    return 2


def _draw_footer(scr, text: str) -> None:
    h, _ = scr.getmaxyx()
    _put(scr, h - 1, 2, text, _c(_P_DIM))


def _draw_row(scr, y: int, wiz: Wizard, i: int) -> None:
    kind, key = wiz.rows[i]
    sel = i == wiz.cursor
    if kind == "spacer":
        return
    if kind == "header":
        if sel:
            _put(scr, y, 0, "›", _c(_P_GREEN, curses.A_BOLD))
        x = _put(scr, y, 2, key, _c(_P_GREEN, curses.A_BOLD))
        if sel:
            _put(scr, y, x, "  (space toggles the group)", _c(_P_DIM))
        return
    if sel:
        _put(scr, y, 2, "›", _c(_P_GREEN, curses.A_BOLD))
    focus = curses.A_BOLD if sel else 0

    if kind == "toggle":
        on = bool(wiz.feat.get(key, True))
        x = _put(scr, y, 4, "[", focus)
        x = _put(scr, y, x, "✓" if on else " ", _c(_P_GREEN, curses.A_BOLD))
        x = _put(scr, y, x, "] ", focus)
        _put(scr, y, x, _label(key), focus if on else _c(_P_DIM, focus))
        return
    if kind == "radio":
        mode = str(wiz.feat.get(key, "auto"))
        x = _put(scr, y, 4, "Theme mode:  ", focus)
        for m in THEME_MODES:
            if m == mode:
                x = _put(scr, y, x, f"(•) {m}",
                         _c(_P_YELLOW, curses.A_BOLD | focus))
            else:
                x = _put(scr, y, x, f"( ) {m}", _c(_P_DIM, focus))
            x = _put(scr, y, x, "  ")
        return
    label, lo, hi, unit = _INT_ROWS[key]
    val = _coerce_int(wiz.feat.get(key), lo, lo, hi)
    oled_on = bool(wiz.feat.get("oled_care", False))
    x = _put(scr, y, 4, f"{label}:  ", focus if oled_on else _c(_P_DIM))
    x = _put(scr, y, x, f"‹ {val} {unit} ›",
             _c(_P_YELLOW, curses.A_BOLD | focus) if oled_on else _c(_P_DIM))
    x = _put(scr, y, x, f"  {lo}-{hi}", _c(_P_DIM))
    if not oled_on:
        _put(scr, y, x, "  (OLED care is off)", _c(_P_DIM))


_SELECT_PROMPT = {
    "install": "Please select the components you want to install",
    "uninstall": "Please select the components you want to remove",
}


def _draw_select(scr, wiz: Wizard, top: int) -> int:
    scr.erase()
    h, w = scr.getmaxyx()
    body_top = _draw_header(scr)
    prompt = _SELECT_PROMPT.get(wiz.mode, _SELECT_PROMPT["install"])
    _put(scr, body_top, max(2, (w - len(prompt)) // 2), prompt, _c(_P_DIM))
    body_top += 2
    body_h = max(1, h - body_top - 2)

    # Keep the cursor visible.
    if wiz.cursor < top:
        top = wiz.cursor
    if wiz.cursor >= top + body_h:
        top = wiz.cursor - body_h + 1
    top = max(0, min(top, max(0, len(wiz.rows) - body_h)))

    for i in range(top, min(len(wiz.rows), top + body_h)):
        _draw_row(scr, body_top + i - top, wiz, i)

    if top + body_h < len(wiz.rows):
        _put(scr, body_top + body_h, 4, "…", _c(_P_DIM))
    _draw_footer(scr, "space toggle · ←/→ adjust · a all · n none · "
                      "r reset · Enter continue · q quit")
    return top


def _draw_summary(scr, wiz: Wizard, cursor: int) -> list[str]:
    scr.erase()
    y = _draw_header(scr)

    for line in _WARNING[wiz.mode]:
        _put(scr, y, 2, line, _c(_P_RED, curses.A_BOLD))
        y += 1
    y += 1

    on, total = wiz.enabled_count()
    verb = "Installing" if wiz.mode == "install" else "Removing"
    x = _put(scr, y, 2, "✓ ", _c(_P_GREEN, curses.A_BOLD))
    _put(scr, y, x, f"{verb} {on} of {total} components", curses.A_BOLD)
    y += 1
    off = [key for kind, key in wiz.rows
           if kind == "toggle" and not wiz.feat.get(key, True)]
    if off:
        skipped = "Skipped: " + ", ".join(k.replace("_", " ") for k in off)
        _put(scr, y, 2, skipped, _c(_P_DIM))
        y += 1
    y += 1
    if wiz.mode == "install":
        x = _put(scr, y, 2, "Theme mode: ")
        _put(scr, y, x, str(wiz.feat.get("theme_mode", "auto")),
             _c(_P_YELLOW, curses.A_BOLD))
        y += 1
        if wiz.feat.get("oled_care"):
            x = _put(scr, y, 2, "OLED care: ")
            _put(scr, y, x,
                 f"every {wiz.feat.get('oled_interval', 5)} min, "
                 f"max {wiz.feat.get('oled_max_shift', 8)} px",
                 _c(_P_YELLOW, curses.A_BOLD))
            y += 1
        y += 1

    items = []
    if wiz.mode == "install":
        items.append("save")
    items.append("< Confirm >")
    items.append("< Back >")
    for i, item in enumerate(items):
        sel = i == cursor
        if sel:
            _put(scr, y, 2, "›", _c(_P_GREEN, curses.A_BOLD))
        focus = curses.A_BOLD if sel else 0
        if item == "save":
            x = _put(scr, y, 4, "[", focus)
            x = _put(scr, y, x, "✓" if wiz.save else " ",
                     _c(_P_GREEN, curses.A_BOLD))
            x = _put(scr, y, x, "] ", focus)
            _put(scr, y, x, "Save selection to features.json", focus)
        elif item == "< Confirm >":
            _put(scr, y, 4, item, _c(_P_GREEN, curses.A_BOLD | focus))
        else:
            _put(scr, y, 4, item, focus if sel else _c(_P_DIM))
        y += 1

    _draw_footer(scr, "space toggle · Enter select · Esc back · q quit")
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
    if curses is None:
        raise RuntimeError("curses unavailable")
    wiz = Wizard(feat, mode)
    return curses.wrapper(lambda scr: _run(scr, wiz))


# ── live progress screen (issue #44 phase 2) ──────────────────────────
#
# The install body runs on a worker thread with sys.stdout/stderr
# redirected to a log file; the screen polls the same progress file the
# GUI installer consumes and tails the log underneath a step list.

# Plain-ASCII spinner so it renders even on non-UTF-8 locales.
_SPINNER = ("-", "\\", "|", "/")

# The captured log carries ANSI escapes from log.py; strip them and
# re-apply native curses colours based on content.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[0-9A-Za-z]")

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _read_progress_records() -> list[str]:
    """Raw progress lines (each ``N\\tTITLE``), dropping the trailing
    ``__DONE__`` marker if present."""
    out: list[str] = []
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line:
                    out.append(line)
    except OSError:
        return out
    if out and out[-1].startswith(DONE_MARKER):
        out.pop()
    return out


def _read_log_tail(path: str, n: int) -> list[str]:
    """Last ``n`` lines of the captured install log, verbatim — ANSI
    escapes preserved (rendered natively by _ansi_segments) and blank
    lines kept so the log reads exactly like the classic CLI output.
    Trailing blanks are trimmed so the tail always ends on real text."""
    if n <= 0:
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [ln.rstrip("\n") for ln in fh]
    except OSError:
        return []
    while lines and not lines[-1].strip():
        lines.pop()
    return lines[-n:]


# ── ANSI → curses passthrough for the live log ────────────────────────
# log.py colours its output with SGR escapes (\033[0;32m etc.); render
# them with the same colours instead of stripping to monochrome.

_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

_BASIC_FG_PAIR = {
    31: _P_RED, 32: _P_GREEN, 33: _P_YELLOW,
    37: _P_WHITE, 90: _P_DIM,
}

_dyn_pairs: dict[int, int] = {}


def _pair_for_256(code: int) -> int:
    """Curses pair for an xterm-256 foreground, allocated on demand.
    Falls back to 0 (default colours) when the terminal can't host it."""
    if not _HAVE_COLOR or curses.COLORS < 256:
        return 0
    if code in _dyn_pairs:
        return _dyn_pairs[code]
    pair = _DYN_PAIR_START + len(_dyn_pairs)
    if pair >= curses.COLOR_PAIRS:
        return 0
    try:
        curses.init_pair(pair, code, _BG)
    except curses.error:
        return 0
    _dyn_pairs[code] = pair
    return pair


def _ansi_segments(line: str) -> list[tuple[str, int]]:
    """Split an SGR-coloured line into (text, curses attr) segments so
    the live log keeps log.py's original colours."""
    if curses is None:
        return [(_strip_ansi(line), 0)]
    segments: list[tuple[str, int]] = []
    pair, bold, dim = 0, False, False

    def attr() -> int:
        a = curses.color_pair(pair) if (_HAVE_COLOR and pair) else 0
        if bold:
            a |= curses.A_BOLD
        if dim:
            a |= curses.A_DIM
        return a

    pos = 0
    for m in _SGR_RE.finditer(line):
        if m.start() > pos:
            segments.append((_strip_ansi(line[pos:m.start()]), attr()))
        codes = [int(c) for c in m.group(1).split(";") if c] or [0]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                pair, bold, dim = 0, False, False
            elif c == 1:
                bold = True
            elif c == 2:
                dim = True
            elif c == 22:
                bold = dim = False
            elif c in _BASIC_FG_PAIR:
                pair = _BASIC_FG_PAIR[c]
            elif 30 <= c <= 36:
                pair = 0
            elif c == 39:
                pair = 0
            elif c == 38 and i + 2 < len(codes) and codes[i + 1] == 5:
                pair = _pair_for_256(codes[i + 2])
                i += 2
            i += 1
        pos = m.end()
    if pos < len(line):
        segments.append((_strip_ansi(line[pos:]), attr()))
    return [(text, a) for text, a in segments if text]


def _draw_bar(scr, y: int, x: int, width: int, frac: float) -> None:
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    x = _put(scr, y, x, "█" * filled, _c(_P_WHITE, curses.A_BOLD))
    _put(scr, y, x, "░" * max(0, width - filled), _c(_P_DIM))


# Three big phases instead of the raw 27-step list; the fine-grained
# detail scrolls by in the live log underneath.
_PHASES = {
    "install": ("VERIFICATION", "BUILDING", "INSTALLING"),
    "uninstall": ("VERIFICATION", "RESTORING", "REMOVING"),
}

# Uninstall steps that restore Breeze before the payload removal loop.
_RESTORE_TITLES = {
    "Removing Theme Switcher", "Removing OLED Care",
    "Resetting Layout", "Applying Changes",
}


def _phase_index(mode: str, records: list[str]) -> int:
    """Map the emitted step() records onto the coarse phase rail.
    max() keeps the rail monotonic — the late config re-check titled
    'Verification' must not bounce the UI back to phase 0."""
    idx = 0
    for rec in records:
        _, _, title = rec.partition("\t")
        if mode == "install":
            low = title.lower()
            if low.startswith("building"):
                idx = max(idx, 1)
            elif low.startswith(("installing", "applying", "skipping",
                                 "restarting", "retrying")):
                idx = max(idx, 2)
        else:
            if title in _RESTORE_TITLES:
                idx = max(idx, 1)
            elif title.startswith(("Removing", "Restarting")):
                idx = max(idx, 2)
    return idx


def _draw_phases(scr, y: int, w: int, mode: str, phase: int,
                 finished: bool, rc_ok: bool, frame: int) -> None:
    labels = _PHASES.get(mode, _PHASES["install"])
    spinner = _SPINNER[frame % len(_SPINNER)]
    gap = "     "
    width = sum(len(lb) + 2 for lb in labels) + len(gap) * (len(labels) - 1)
    x = max(2, (w - width) // 2)
    for i, label in enumerate(labels):
        if finished and not rc_ok and i == phase:
            x = _put(scr, y, x, "✗ ", _c(_P_RED, curses.A_BOLD))
            x = _put(scr, y, x, label, _c(_P_RED, curses.A_BOLD))
        elif i < phase or finished:
            x = _put(scr, y, x, "✓ ", _c(_P_GREEN, curses.A_BOLD))
            x = _put(scr, y, x, label, _c(_P_GREEN, curses.A_BOLD))
        elif i == phase:
            x = _put(scr, y, x, f"{spinner} ", _c(_P_YELLOW, curses.A_BOLD))
            x = _put(scr, y, x, label, _c(_P_WHITE, curses.A_BOLD))
        else:
            x = _put(scr, y, x, "  ")
            x = _put(scr, y, x, label, _c(_P_DIM))
        if i < len(labels) - 1:
            x = _put(scr, y, x, gap)


def _draw_progress(scr, mode: str, records: list[str], total: int,
                   finished: bool, rc_ok: bool, frame: int,
                   log_path: str) -> None:
    scr.erase()
    h, w = scr.getmaxyx()
    y = _draw_header(scr)

    # Live log fills the middle; phase rail + bar + status pin to the
    # bottom so the progress block sits under the output, not above it.
    log_h = max(0, h - y - 5)
    if log_h > 0:
        for i, line in enumerate(_read_log_tail(log_path, log_h)):
            x = 2
            for text, attr in _ansi_segments(line):
                x = _put(scr, y + i, x, text, attr)

    _draw_phases(scr, h - 4, w, mode, _phase_index(mode, records),
                 finished, rc_ok, frame)

    # The estimate can miss best-effort steps (the layout retry only
    # runs on failure), so clamp — never show 27/26.
    current = min(len(records), total) if total > 0 else len(records)
    frac = (current / total) if total > 0 else 0.0
    if finished:
        frac = 1.0
    frac = max(0.0, min(1.0, frac))
    pct = f" {int(round(frac * 100)):3d}%"
    _draw_bar(scr, h - 3, 2, max(1, w - 4 - len(pct)), frac)
    _put(scr, h - 3, max(1, w - 4 - len(pct)) + 2, pct, _c(_P_DIM))

    # Centred status line at the very bottom.
    if finished and rc_ok:
        msg = "✓ Done — press any key to exit."
        attr = _c(_P_GREEN, curses.A_BOLD)
    elif finished:
        msg = f"✗ Finished with errors — full log: {log_path}"
        attr = _c(_P_RED, curses.A_BOLD)
    else:
        msg = "Working…  press Ctrl-C to abort"
        attr = _c(_P_DIM)
    _put(scr, h - 1, max(2, (w - len(msg)) // 2), msg, attr)
    scr.refresh()


def _progress_main(scr, thread, result: dict, total: int, mode: str,
                   log_path: str) -> None:
    _init_colors()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    scr.keypad(True)
    scr.timeout(200)  # redraw cadence while the body works
    frame = 0
    while True:
        records = _read_progress_records()
        finished = not thread.is_alive()
        _draw_progress(scr, mode, records, total, finished,
                       result.get("rc") == 0, frame, log_path)
        frame += 1
        if finished:
            scr.timeout(-1)
            try:
                scr.getch()
            except curses.error:
                pass
            return
        try:
            scr.getch()
        except curses.error:
            pass


def run_progress(runner, total: int, mode: str = "install") -> int:
    """Run ``runner`` (a zero-arg callable returning an exit code) behind
    the live progress screen. The body always runs exactly once: if the
    UI can't start, the body runs in the foreground; if the UI dies
    mid-run, we wait for the worker thread and return its rc."""
    if curses is None:
        return int(runner())

    log_path = os.environ.get("MTTKDE_INSTALL_LOG", "/tmp/mttkde-install.log")
    try:
        logf = open(log_path, "w", buffering=1, encoding="utf-8")
    except OSError:
        return int(runner())

    result: dict = {"rc": None}

    def work() -> None:
        try:
            result["rc"] = int(runner())
        except Exception:
            import traceback
            traceback.print_exc()
            result["rc"] = 1

    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = logf
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    ui_error = None
    interrupted = False
    try:
        curses.wrapper(
            lambda scr: _progress_main(scr, thread, result, total, mode,
                                       log_path))
    except KeyboardInterrupt:
        # Match classic-flow semantics: Ctrl-C aborts the whole process
        # (cli.run_install prints Aborted / rc 130); the daemon worker
        # and its children die with it, same as a classic mid-step ^C.
        interrupted = True
        raise
    except Exception as exc:  # UI died — the install keeps going below
        ui_error = exc
    finally:
        if not interrupted:
            thread.join()
        sys.stdout, sys.stderr = old_out, old_err
        try:
            logf.close()
        except OSError:
            pass
    if ui_error is not None:
        print(f"  progress screen failed ({ui_error}) — "
              f"full log: {log_path}")
    return int(result["rc"] if result["rc"] is not None else 1)
