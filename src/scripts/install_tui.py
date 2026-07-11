"""Interactive curses wizard for ``sudo ./install``.

This is the terminal-only selection UI described in issue #44. It replaces
the plain ``[Y/n]`` confirm screen with a navigable checklist of components,
a theme-mode picker, and OLED-care options. It is only entered from
``cli.run_install`` when a real TTY is present and no CLI flags or
``MTTKDE_NO_CONFIRM`` are set, so the graphical installer (``./installer``)
and headless/CI runs are never affected.

Everything here is stdlib (``curses``) so the install stays fully offline.
"""

import curses
import os
import re
import sys
import threading

from cli import (
    ALL_FEATURES,
    DEFAULT_FEATURES,
    FEATURE_DESC,
    _coerce_int,
    save_features,
)
from log import DONE_MARKER, PROGRESS_FILE

# Display grouping for the checklist. Every entry in ALL_FEATURES appears
# exactly once; order here is presentation order only (build order lives in
# cli.INSTALL_ORDER and is untouched).
GROUPS = [
    ("Theme", [
        "wallpapers", "fonts", "cursors", "plasma_theme",
        "window_decorations", "kvantum", "color_schemes", "icons",
        "global_theme", "layout",
    ]),
    ("KDE components", [
        "plasmoids", "globalmenu", "acrylic_glass",
        "sounds", "gtk", "sddm", "plymouth", "apps",
        "nautilus", "nautilus_bookmarks", "portals",
    ]),
    ("Activation", ["apply_theme", "oled_care"]),
]

_GROUP_MAP = dict(GROUPS)

THEME_MODES = ["auto", "light", "dark"]


class _WizardState:
    def __init__(self, feat):
        rows = []
        for gname, keys in GROUPS:
            rows.append(("group", gname, None))
            for k in keys:
                rows.append(("item", gname, k))
        self.rows = rows
        self.on = {k: bool(feat.get(k, True)) for k in ALL_FEATURES}
        self.theme_mode = str(feat.get("theme_mode", "auto"))
        self.oled = bool(feat.get("oled_care", False))
        # OLED care is opt-in; keep its checklist state in sync with the
        # dedicated flag so the box doesn't show enabled when oled is off.
        self.on["oled_care"] = self.oled
        self.oled_interval = _coerce_int(feat.get("oled_interval"), 5, 1, 59)
        self.oled_max_shift = _coerce_int(feat.get("oled_max_shift"), 8, 1, 16)
        self.screen = "select"
        self.sel = 0
        self.top = 0
        self.save = False
        self.base_feat = dict(feat)


def _to_feat(state: _WizardState) -> dict:
    out = dict(state.base_feat)
    for key in ALL_FEATURES:
        out[key] = state.on.get(key, True)
    out["theme_mode"] = state.theme_mode
    out["oled_care"] = state.oled
    out["oled_interval"] = state.oled_interval
    out["oled_max_shift"] = state.oled_max_shift
    return out


def _toggle_group(state: _WizardState, gname: str) -> None:
    keys = _GROUP_MAP.get(gname, [])
    if not keys:
        return
    all_on = all(state.on.get(k, True) for k in keys)
    for k in keys:
        state.on[k] = not all_on


def _norm(ch):
    """Normalize a key event to a comparable token. ``curses.get_wch`` returns
    a ``str`` for printable characters and an ``int`` (``curses.KEY_*``) for
    special keys, while tests/synthetic callers may pass ``ord("x")`` ints.
    Printable-ASCII ints collapse to their ``str`` form; special key ints are
    left untouched so arrow keys keep matching ``curses.KEY_UP`` et al."""
    if isinstance(ch, str):
        return ch
    if isinstance(ch, int) and 32 <= ch <= 126:
        return chr(ch)
    return ch


def _is_enter(ch) -> bool:
    return ch in (curses.KEY_ENTER, 10, "\n", 13, "\r")


def _handle_select(state: _WizardState, ch) -> str | None:
    c = _norm(ch)
    n = len(state.rows)
    if c in (curses.KEY_UP, "k"):
        state.sel = (state.sel - 1) % n
    elif c in (curses.KEY_DOWN, "j"):
        state.sel = (state.sel + 1) % n
    elif c == " ":
        kind, gname, key = state.rows[state.sel]
        if kind == "group":
            _toggle_group(state, gname)
        else:
            state.on[key] = not state.on.get(key, True)
            if key == "oled_care":
                state.oled = state.on[key]
    elif _is_enter(ch):
        state.screen = "theme"
    elif c == "a":
        for k in ALL_FEATURES:
            state.on[k] = True
    elif c == "r":
        for k in ALL_FEATURES:
            state.on[k] = bool(DEFAULT_FEATURES.get(k, True))
    return None


def _handle_theme(state: _WizardState, ch) -> str | None:
    c = _norm(ch)
    if c in (curses.KEY_RIGHT, curses.KEY_DOWN, "l"):
        i = (THEME_MODES.index(state.theme_mode) + 1) % len(THEME_MODES)
        state.theme_mode = THEME_MODES[i]
    elif c in (curses.KEY_LEFT, curses.KEY_UP, "h"):
        i = (THEME_MODES.index(state.theme_mode) - 1) % len(THEME_MODES)
        state.theme_mode = THEME_MODES[i]
    elif _is_enter(ch):
        # Skip the OLED config screen entirely when OLED care is off — the
        # user only needs it to tune interval/max-shift. Enabling OLED from
        # the checklist re-activates this screen (state.oled becomes True).
        state.screen = "oled" if state.oled else "summary"
    elif ch == 27:
        state.screen = "select"
    return None


def _handle_oled(state: _WizardState, ch) -> str | None:
    c = _norm(ch)
    if c == " ":
        state.oled = not state.oled
        state.on["oled_care"] = state.oled
    elif c in ("-", "_"):
        state.oled_interval = _coerce_int(state.oled_interval - 1, 5, 1, 59)
    elif c in ("=", "+"):
        state.oled_interval = _coerce_int(state.oled_interval + 1, 5, 1, 59)
    elif c in ("[", "{"):
        state.oled_max_shift = _coerce_int(state.oled_max_shift - 1, 8, 1, 16)
    elif c in ("]", "}"):
        state.oled_max_shift = _coerce_int(state.oled_max_shift + 1, 8, 1, 16)
    elif _is_enter(ch):
        state.screen = "summary"
    elif ch == 27:
        state.screen = "theme"
    return None


def _handle_summary(state: _WizardState, ch) -> str | None:
    c = _norm(ch)
    if _is_enter(ch):
        if state.save:
            save_features(_to_feat(state))
        return "confirm"
    elif c == "s":
        state.save = not state.save
    elif ch == 27:
        state.screen = "select"
    return None


def _handle(state: _WizardState, ch) -> str | None:
    if state.screen == "select":
        return _handle_select(state, ch)
    if state.screen == "theme":
        return _handle_theme(state, ch)
    if state.screen == "oled":
        return _handle_oled(state, ch)
    if state.screen == "summary":
        return _handle_summary(state, ch)
    return None


def _setup_curses(stdscr) -> None:
    """Shared terminal setup for the wizard and the progress screen."""
    global _GREEN_ATTR, _RED_ATTR
    _GREEN_ATTR = 0
    _RED_ATTR = 0
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    try:
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            _GREEN_ATTR = curses.color_pair(1)
            _RED_ATTR = curses.color_pair(2)
    except curses.error:
        pass


def _safe_addstr(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x < 0:
        return
    maxlen = w - x - 1
    if maxlen <= 0:
        return
    try:
        stdscr.addstr(y, x, text[:maxlen], attr)
    except (curses.error, UnicodeEncodeError):
        # Non-UTF-8 locale: a glyph can't be encoded for the terminal.
        # Skip the cell rather than crash the whole UI.
        pass


def _draw_select(stdscr, state: _WizardState, h: int, w: int) -> None:
    _safe_addstr(stdscr, 0, 2, " MacTahoe Liquid KDE installer ", curses.A_BOLD)
    _safe_addstr(stdscr, 1, 2,
                 "space=toggle  a=all  r=reset  Enter=next  up/down=move",
                 curses.A_DIM)
    max_rows = max(1, h - 5)
    top = state.top
    if state.sel < top:
        top = state.sel
    if state.sel >= top + max_rows:
        top = state.sel - max_rows + 1
    state.top = top
    y = 3
    for i in range(top, min(top + max_rows, len(state.rows))):
        if y >= h - 1:
            break
        kind, gname, key = state.rows[i]
        if kind == "group":
            attr = curses.A_BOLD
            if i == state.sel:
                attr |= curses.A_REVERSE
            _safe_addstr(stdscr, y, 2, gname, attr)
        else:
            mark = "[x]" if state.on.get(key, True) else "[ ]"
            label = FEATURE_DESC.get(key, key)
            line = f"  {mark} {label}"
            attr = curses.A_REVERSE if i == state.sel else 0
            _safe_addstr(stdscr, y, 2, line, attr)
        y += 1
    _safe_addstr(stdscr, h - 1, 2, "Enter -> theme mode", curses.A_DIM)


def _center_top(h: int, body_h: int) -> int:
    """Vertical anchor for a body block of ``body_h`` lines so it sits centred
    between the two-line header and the footer on tall terminals, falling back
    to the top (row 3) when the window is too short."""
    return max(3, 3 + max(0, (h - 5 - body_h) // 2))


def _draw_theme(stdscr, state: _WizardState, h: int, w: int) -> None:
    _safe_addstr(stdscr, 0, 2, " Theme mode ", curses.A_BOLD)
    _safe_addstr(stdscr, 1, 2,
                 "left/right or up/down choose   Enter=next   Esc=back",
                 curses.A_DIM)
    y = _center_top(h, len(THEME_MODES))
    for m in THEME_MODES:
        mark = "(o)" if m == state.theme_mode else "( )"
        attr = curses.A_REVERSE if m == state.theme_mode else 0
        _safe_addstr(stdscr, y, 2, f"  {mark} {m}", attr)
        y += 1
    if state.oled:
        _safe_addstr(stdscr, h - 1, 2, "Enter -> OLED care options",
                     curses.A_DIM)
    else:
        _safe_addstr(stdscr, h - 1, 2,
                     "Enter -> summary  (OLED care is off — enable it in the "
                     "list to configure)", curses.A_DIM)


def _draw_oled(stdscr, state: _WizardState, h: int, w: int) -> None:
    _safe_addstr(stdscr, 0, 2, " OLED care (optional) ", curses.A_BOLD)
    _safe_addstr(stdscr, 1, 2,
                 "space=toggle  -/= interval  [/] max-shift  Enter=next  Esc=back",
                 curses.A_DIM)
    body_h = 6 if not state.oled else 5
    y = _center_top(h, body_h)
    mark = "[x]" if state.oled else "[ ]"
    _safe_addstr(stdscr, y, 2, f"  {mark} Enable OLED pixel-shift",
                 curses.A_REVERSE if state.oled else 0)
    y += 2
    _safe_addstr(stdscr, y, 2, f"  Interval: {state.oled_interval} min   (- / =)")
    y += 1
    _safe_addstr(stdscr, y, 2, f"  Max shift: {state.oled_max_shift} px   ( [ / ] )")
    if not state.oled:
        _safe_addstr(stdscr, y + 1, 2,
                     "  (disabled - values ignored)", curses.A_DIM)
    _safe_addstr(stdscr, h - 1, 2, "Enter -> summary", curses.A_DIM)


def _draw_summary(stdscr, state: _WizardState, h: int, w: int) -> None:
    _safe_addstr(stdscr, 0, 2, " Summary ", curses.A_BOLD)
    _safe_addstr(stdscr, 1, 2, "Enter=install  s=toggle save  Esc=back",
                 curses.A_DIM)
    enabled = [k for k in ALL_FEATURES if state.on.get(k, True)]
    y = 3
    _safe_addstr(stdscr, y, 2, f"  Theme mode : {state.theme_mode}")
    y += 1
    oled_txt = f"  OLED care  : {'on' if state.oled else 'off'}"
    if state.oled:
        oled_txt += f" ({state.oled_interval}m, {state.oled_max_shift}px)"
    _safe_addstr(stdscr, y, 2, oled_txt)
    y += 1
    _safe_addstr(stdscr, y, 2,
                 f"  Components : {len(enabled)}/{len(ALL_FEATURES)} enabled")
    y += 2
    maxw = max(10, w - 4)
    line = "  "
    for k in enabled:
        add = k + ", "
        if len(line) + len(add) > maxw:
            _safe_addstr(stdscr, y, 2, line.rstrip(", "))
            y += 1
            line = "  " + add
        else:
            line += add
    if line.strip():
        _safe_addstr(stdscr, y, 2, line.rstrip(", "))
        y += 1
    save_mark = "[x]" if state.save else "[ ]"
    _safe_addstr(stdscr, h - 2, 2,
                 f"  {save_mark} Save these choices to features.json",
                 curses.A_REVERSE if state.save else 0)
    _safe_addstr(stdscr, h - 1, 2, "Enter -> begin installation", curses.A_DIM)


def _draw(stdscr, state: _WizardState) -> None:
    try:
        stdscr.erase()
        stdscr.border()
    except curses.error:
        pass
    h, w = stdscr.getmaxyx()
    if state.screen == "select":
        _draw_select(stdscr, state, h, w)
    elif state.screen == "theme":
        _draw_theme(stdscr, state, h, w)
    elif state.screen == "oled":
        _draw_oled(stdscr, state, h, w)
    elif state.screen == "summary":
        _draw_summary(stdscr, state, h, w)
    try:
        stdscr.refresh()
    except curses.error:
        pass


def _wizard_main(stdscr, feat: dict) -> dict:
    _setup_curses(stdscr)
    state = _WizardState(feat)
    while True:
        _draw(stdscr, state)
        try:
            ch = stdscr.get_wch()
        except curses.error:
            ch = -1
        if ch == curses.KEY_RESIZE:
            continue
        if _handle(state, ch) == "confirm":
            return _to_feat(state)


def run_wizard(feat: dict) -> dict:
    """Run the interactive selection UI and return the (possibly modified)
    feature dict. Raises on terminal/input errors; callers should fall back
    to the classic confirm() path."""
    return curses.wrapper(_wizard_main, feat)


# ---------------------------------------------------------------------------
# Live progress screen (issue #44, Fase 2)
# ---------------------------------------------------------------------------

def _read_progress_records() -> list[str]:
    """Return raw progress lines (each ``N\\tTITLE``), dropping a trailing
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
    if out and out[-1].startswith(DONE_MARKER + "\t"):
        out.pop()
    return out


# Plain-ASCII spinner so it renders even on non-UTF-8 locales (the braille
# spinners would trip the UnicodeEncodeError guard).
_SPINNER = ("-", "\\", "|", "/")

# The install log is captured verbatim (it carries ANSI colour escapes from
# log.py); strip them before drawing so they don't show as literal garbage,
# then re-apply native curses colours based on content.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[0-9A-Za-z]")

# Native attribute for log lines; set to colour pairs in _setup_curses when
# the terminal supports colour, otherwise left as 0 (plain).
_GREEN_ATTR = 0
_RED_ATTR = 0


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _read_log_tail(path: str, n: int) -> list[str]:
    """Return the last ``n`` non-empty lines of the install log, most recent
    last. ANSI escapes are stripped so the curses window shows clean text."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [_strip_ansi(ln.rstrip("\n")) for ln in fh if ln.strip()]
    except OSError:
        return []
    return lines[-n:]


def _log_attr(line: str) -> int:
    low = line.lower()
    if "✓" in line:
        return _GREEN_ATTR
    if "✗" in line or "⚠" in line or "fail" in low or "error" in low:
        return _RED_ATTR
    return 0


def _draw_bar(stdscr, y: int, x: int, w: int, frac: float) -> None:
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * w))
    bar = "█" * filled + "░" * max(0, w - filled)
    _safe_addstr(stdscr, y, x, bar)


def _draw_progress(stdscr, records: list[str], total: int, finished: bool,
                    ok: bool, frame: int, log_path: str) -> None:
    try:
        stdscr.erase()
        stdscr.border()
    except curses.error:
        pass
    h, w = stdscr.getmaxyx()
    _safe_addstr(stdscr, 0, 2, " Installing MacTahoe Liquid KDE ",
                 curses.A_BOLD)
    current = len(records)
    # The step estimate may over-count best-effort steps (e.g. the layout
    # retry that only runs on failure), so clamp the live fraction; once the
    # install is finished it is 100% regardless of the estimate mismatch.
    frac = (current / total) if total > 0 else 0.0
    if finished:
        frac = 1.0
    frac = max(0.0, min(1.0, frac))
    pct = int(round(frac * 100))
    _safe_addstr(stdscr, 1, 2,
                 f"  {current}/{total} steps  ({pct}%)", curses.A_DIM)
    _draw_bar(stdscr, 2, 2, max(1, w - 4), frac)

    # Reserve space at the bottom for a live tail of the install log; the rest
    # of the window holds the scrolling step list.
    log_reserved = 7
    list_top = 4
    list_bottom = max(list_top, h - log_reserved - 1)
    log_top = list_bottom + 1
    log_bottom = h - 2

    max_rows = max(1, list_bottom - list_top)
    # Scroll so the most recent (current) step is always visible.
    start = max(0, current - max_rows)
    y = list_top
    spinner = _SPINNER[frame % len(_SPINNER)]
    for idx in range(start, min(start + max_rows, current)):
        if y > list_bottom:
            break
        rec = records[idx]
        _, _, title = rec.partition("\t")
        if idx == current - 1 and not finished:
            mark = spinner  # animated liveness on the active step
        elif idx == current - 1:
            mark = "✔" if ok else "✗"
        else:
            mark = " "
        _safe_addstr(stdscr, y, 2,
                     f"  {mark} {title}"[: w - 3],
                     curses.A_REVERSE if idx == current - 1 else 0)
        y += 1

    # Live log tail under the step list.
    if log_top <= log_bottom:
        _safe_addstr(stdscr, log_top, 2,
                     "  ── live log ──", curses.A_DIM)
        tail = _read_log_tail(log_path, log_bottom - log_top)
        ly = log_top + 1
        for line in tail:
            if ly > log_bottom:
                break
            _safe_addstr(stdscr, ly, 2, "  " + line[: w - 3], _log_attr(line))
            ly += 1

    if finished:
        msg = "  Done — press any key to exit." if ok else \
              "  Finished with errors — press any key to exit."
        _safe_addstr(stdscr, h - 1, 2, msg,
                     curses.A_BOLD if ok else curses.A_REVERSE)
    else:
        _safe_addstr(stdscr, h - 1, 2,
                     "  Working…  (Ctrl-C to abort)", curses.A_DIM)
    try:
        stdscr.refresh()
    except curses.error:
        pass


def _progress_main(stdscr, runner, total: int) -> int:
    _setup_curses(stdscr)

    # The install body prints ANSI to stdout; capture it to a log file so it
    # does not fight the curses screen. The progress file is the live source.
    log_path = os.environ.get("MTTKDE_PROGRESS_LOG",
                              "/tmp/mttkde-install.log")
    try:
        logf = open(log_path, "w", buffering=1, encoding="utf-8")
    except OSError:
        logf = None
    old_out, old_err = sys.stdout, sys.stderr
    if logf is not None:
        sys.stdout = logf
        sys.stderr = logf

    result: dict = {"rc": 1}

    def work() -> None:
        try:
            result["rc"] = int(runner())
        except Exception:
            import traceback
            traceback.print_exc()
            result["rc"] = 1
        finally:
            sys.stdout = old_out
            sys.stderr = old_err

    thread = threading.Thread(target=work, daemon=True)
    thread.start()

    stdscr.timeout(200)
    finished = False
    frame = 0
    try:
        while True:
            records = _read_progress_records()
            if not thread.is_alive():
                finished = True
            _draw_progress(stdscr, records, total, finished,
                           ok=result["rc"] == 0, frame=frame, log_path=log_path)
            frame += 1
            if finished:
                stdscr.timeout(-1)
                try:
                    stdscr.get_wch()
                except curses.error:
                    pass
                break
            try:
                stdscr.get_wch()
            except curses.error:
                pass
    finally:
        thread.join(timeout=1)
        sys.stdout, sys.stderr = old_out, old_err
        if logf is not None:
            try:
                logf.close()
            except OSError:
                pass
    return int(result.get("rc", 1))


def run_progress(runner, total: int) -> int:
    """Run ``runner`` (a zero-arg callable returning an exit code) while
    showing a live curses progress screen sourced from ``PROGRESS_FILE``.

    Falls back to running ``runner`` directly if curses is unavailable or
    raises, so the install never silently dies behind the progress UI."""
    try:
        return curses.wrapper(_progress_main, runner, total)
    except Exception:
        return int(runner())
