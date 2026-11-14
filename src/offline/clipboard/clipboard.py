#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal clipboard popup: text + image history, search, pin, copy, delete.
Talks to the mac-tahoe-clipd service (org.mactahoe.Clipboard) over D-Bus."""
import json, os, re, shutil, signal, subprocess, sys, time
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QSize, pyqtSignal
from PyQt6.QtDBus import QDBusConnection, QDBusInterface
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea,
                             QPushButton, QLabel, QFrame, QAbstractButton, QSizePolicy)

APP_ID = "mac-tahoe-clipboard"
DATA = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "mac-tahoe-liquid-kde")
OLD_PINS_FILE = os.path.join(DATA, "clipboard-pins.json")
LOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), APP_ID + ".pid")
DAEMON = os.path.expanduser("~/.local/bin/mac-tahoe-clipd")

POPUP_W = 800
CAP_LINES = 5          # collapsed text row: at most this many lines ...
CAP_CHARS = 300        # ... or this many characters
EXPANDED_CHARS = 3000  # expanded text row: at most this many characters
THUMB_MAX_W, THUMB_MAX_H = 560, 300
ZWSP = "​"
LINE = "rgba(127,127,127,0.30)"


# ── text helpers ───────────────────────────────────────────────────────────

def soft_breaks(text):
    """Let QLabel wrap long unbroken runs (URLs, hashes) by adding zero-width break points."""
    def run(tok):
        tok = re.sub(r"([/?&=#_\-.,:;@])(?=\S)", "\\1" + ZWSP, tok)
        out = []
        for seg in tok.split(ZWSP):
            out.append(ZWSP.join(seg[i:i + 28] for i in range(0, len(seg), 28)) if len(seg) > 28 else seg)
        return ZWSP.join(out)
    return "".join(part if (not part or part.isspace()) else run(part) for part in re.split(r"(\s+)", text))


def display_text(text, expanded):
    """Return (shown_text, was_truncated). Never cuts silently: truncation always ends in an ellipsis."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    body = "\n".join(lines)
    if expanded:
        if len(body) > EXPANDED_CHARS:
            return body[:EXPANDED_CHARS].rstrip() + f"\n… {len(body) - EXPANDED_CHARS} more characters", True
        return body, False
    cut = False
    if len(lines) > CAP_LINES:
        lines = lines[:CAP_LINES]; cut = True
    body = "\n".join(lines)
    if len(body) > CAP_CHARS:
        body = body[:CAP_CHARS]; cut = True
    return (body.rstrip() + "…" if cut else body), cut


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".0 ", " ")
        n /= 1024


def haystack(item):
    if item["kind"] == "image":
        return f"image {item.get('w', 0)}x{item.get('h', 0)} {item.get('w', 0)} × {item.get('h', 0)} png picture screenshot"
    return item.get("text", "")


# ── backend ────────────────────────────────────────────────────────────────

class DaemonBackend:
    """Client for the mac-tahoe-clipd service. Items: dict(id, kind, text | w,h,bytes,path, ts, pinned)."""
    def __init__(self):
        self.iface = QDBusInterface("org.mactahoe.Clipboard", "/Clipboard", "org.mactahoe.Clipboard",
                                    QDBusConnection.sessionBus())

    def available(self):
        return self.iface.isValid()

    def _call(self, name, *args):
        a = self.iface.call(name, *args).arguments()
        return a[0] if a else None

    def entries(self):
        raw = self._call("list") if self.available() else "[]"
        try:
            data = json.loads(raw or "[]")
        except ValueError:
            return []
        return [d for d in data if isinstance(d, dict) and d.get("id") and d.get("kind") in ("text", "image")]

    def current_id(self):
        v = self._call("currentId") if self.available() else ""
        return v if isinstance(v, str) else ""

    def copy(self, item_id): self.iface.call("copy", item_id)
    def remove(self, item_id): self.iface.call("remove", item_id)
    def clear(self): self.iface.call("clearHistory")
    def set_pinned(self, item_id, pinned): self.iface.call("setPinned", item_id, bool(pinned))
    def add_text(self, text, pinned): self.iface.call("addText", text, bool(pinned))


def ensure_daemon(timeout=3.0):
    """Start the service if it isn't running (normally autostarted at login)."""
    be = DaemonBackend()
    if be.available():
        return be
    if os.path.exists(DAEMON):
        subprocess.Popen([DAEMON], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            time.sleep(0.1)
            be = DaemonBackend()
            if be.available():
                break
    return be


def migrate_old_pins(be):
    """One-time import of pins saved by the first version of this popup."""
    try:
        with open(OLD_PINS_FILE, encoding="utf-8") as f:
            old = [s for s in json.load(f) if isinstance(s, str) and s]
    except (OSError, ValueError, TypeError):
        return
    if be.available():
        for t in reversed(old):
            be.add_text(t, True)
        shutil.move(OLD_PINS_FILE, OLD_PINS_FILE + ".migrated")


# ── widgets ────────────────────────────────────────────────────────────────

class IconButton(QAbstractButton):
    """Flat, palette-aware glyph button: copy / pin / delete."""
    def __init__(self, kind, tip, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.active = False
        self.locked = False   # greyed out: action unavailable (delete on a pinned item)
        self.setToolTip(tip)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        base = pal.color(pal.ColorRole.WindowText)
        hover = self.underMouse() and not self.locked
        if self.locked:
            col = QColor(base); col.setAlphaF(0.25)
        elif self.kind == "delete" and hover:
            col = QColor(255, 95, 87)
        elif self.active:
            col = QColor(pal.color(pal.ColorRole.Highlight))
        else:
            col = QColor(base); col.setAlphaF(0.95 if hover else 0.62)
        if hover or self.isDown():
            bg = QColor(col if (self.kind == "delete" or self.active) else base)
            bg.setAlphaF(0.22 if self.isDown() else 0.14)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(bg); p.drawRoundedRect(QRectF(self.rect()), 8, 8)
        p.translate(14, 14)
        p.setPen(QPen(col, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        getattr(self, "_" + self.kind)(p, col)

    def _copy(self, p, col):
        front = QRectF(-6, -3, 9, 9.5)
        keep = QPainterPath(); keep.addRect(QRectF(-14, -14, 28, 28))
        hole = QPainterPath(); hole.addRoundedRect(front.adjusted(-1.8, -1.8, 1.8, 1.8), 3, 3)
        p.save(); p.setClipPath(keep.subtracted(hole))
        p.drawRoundedRect(QRectF(-3, -6.5, 9, 9.5), 2, 2)
        p.restore()
        p.drawRoundedRect(front, 2, 2)

    def _pin(self, p, col):
        p.rotate(40)
        head = QPainterPath(); head.addRoundedRect(QRectF(-3.4, -8, 6.8, 8.5), 1.6, 1.6)
        if self.active:
            p.setBrush(col)
        p.drawPath(head); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(-5.5, 0.5), QPointF(5.5, 0.5)); p.drawLine(QPointF(0, 0.5), QPointF(0, 8))

    def _delete(self, p, col):
        p.drawLine(QPointF(-6, -4), QPointF(6, -4))
        p.drawPolyline([QPointF(-2, -4), QPointF(-2, -6.3), QPointF(2, -6.3), QPointF(2, -4)])
        body = QPainterPath(); body.moveTo(-4.4, -4); body.lineTo(-3.7, 5.2)
        body.quadTo(-3.6, 6.4, -2.4, 6.4); body.lineTo(2.4, 6.4); body.quadTo(3.6, 6.4, 3.7, 5.2); body.lineTo(4.4, -4)
        p.drawPath(body)
        p.drawLine(QPointF(-1.4, -1), QPointF(-1.2, 3.4)); p.drawLine(QPointF(1.4, -1), QPointF(1.2, 3.4))


class Thumb(QWidget):
    """Image preview: aspect-correct, rounded, hairline border; shows a placeholder if the file is missing."""
    def __init__(self, path, w, h, cache):
        super().__init__()
        self.pix = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if path and os.path.exists(path):
            self.pix = cache.get(path)
            if self.pix is None:
                img = QImage(path)
                if not img.isNull():
                    w, h = img.width(), img.height()
                    dpr = 2.0
                    scale = min(THUMB_MAX_W / w, THUMB_MAX_H / h, 1.0)
                    self.pix = QPixmap.fromImage(img.scaled(max(1, int(w * scale * dpr)), max(1, int(h * scale * dpr)),
                                                            Qt.AspectRatioMode.KeepAspectRatio,
                                                            Qt.TransformationMode.SmoothTransformation))
                    self.pix.setDevicePixelRatio(dpr)
                    cache[path] = self.pix
        if self.pix is not None:
            lw, lh = int(self.pix.width() / self.pix.devicePixelRatio()), int(self.pix.height() / self.pix.devicePixelRatio())
            self.setFixedSize(max(1, lw), max(1, lh))
        else:
            self.setFixedSize(THUMB_MAX_W, 64)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath(); clip.addRoundedRect(r, 8, 8)
        if self.pix is not None:
            p.save(); p.setClipPath(clip); p.drawPixmap(self.rect(), self.pix); p.restore()
        else:
            c = QColor(127, 127, 127, 40); p.setPen(Qt.PenStyle.NoPen); p.setBrush(c); p.drawPath(clip)
            p.setPen(QColor(127, 127, 127, 200)); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Preview unavailable")
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(127, 127, 127, 90), 1)); p.drawPath(clip)


class Row(QFrame):
    def __init__(self, popup, item, current, expanded, divider):
        super().__init__()
        self.popup, self.item = popup, item
        self.id, self.kind = item["id"], item["kind"]
        self.text = item.get("text", "") if self.kind == "text" else ""
        self.pinned, self.is_current, self.expanded, self.divider = bool(item.get("pinned")), current, expanded, divider
        self.selected = False
        self.marked = False
        self.thumb = None
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QHBoxLayout(self); outer.setContentsMargins(14, 8, 8, 9); outer.setSpacing(6)
        col = QVBoxLayout(); col.setSpacing(4); col.setContentsMargins(0, 2, 0, 2)
        self.more = None; self.truncated = False; self.label = None; self.caption = None
        if self.kind == "text":
            shown, self.truncated = display_text(self.text, expanded)
            self.label = QLabel(soft_breaks(shown)); self.label.setWordWrap(True)
            self.label.setTextFormat(Qt.TextFormat.PlainText)
            self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
            col.addWidget(self.label)
            if self.truncated or expanded:
                self.more = QPushButton("Show less" if expanded else "Show more")
                self.more.setFlat(True); self.more.setCursor(Qt.CursorShape.PointingHandCursor)
                self.more.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                self.more.setToolTip("Collapse  (Ctrl+E)" if expanded else "Show full text  (Ctrl+E)")
                self.more.setStyleSheet("QPushButton{border:none;padding:0;text-align:left;color:palette(highlight);}"
                                        "QPushButton:hover{text-decoration:underline;}")
                self.more.clicked.connect(lambda: popup.toggle_expand(self.id))
                col.addWidget(self.more, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            self.thumb = Thumb(item.get("path"), item.get("w", 0), item.get("h", 0), popup.thumb_cache)
            col.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignLeft)
            self.caption = QLabel(f"Image · {item.get('w', 0)} × {item.get('h', 0)} · {human_size(item.get('bytes', 0))}")
            f = self.caption.font(); f.setPointSizeF(max(7.0, f.pointSizeF() - 1.5)); self.caption.setFont(f)
            self.caption.setStyleSheet("color:rgba(127,127,127,0.95);")
            self.caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            col.addWidget(self.caption)
        outer.addLayout(col, 1)

        acts = QHBoxLayout(); acts.setSpacing(0); acts.setContentsMargins(0, 0, 0, 0)
        self.b_copy = IconButton("copy", "Copy  (Enter)")
        self.b_pin = IconButton("pin", "Unpin  (Ctrl+P)" if self.pinned else "Pin  (Ctrl+P)")
        self.b_pin.active = self.pinned
        self.b_del = IconButton("delete", "Pinned \u2014 unpin to delete" if self.pinned else "Delete  (Del)")
        self.b_del.locked = self.pinned
        self.b_copy.clicked.connect(lambda: popup.choose(self.id))
        self.b_pin.clicked.connect(lambda: popup.toggle_pin(self.id))
        self.b_del.clicked.connect(lambda: popup.delete(self.id))
        for b in (self.b_copy, self.b_pin, self.b_del):
            acts.addWidget(b)
        outer.addLayout(acts, 0)
        outer.setAlignment(acts, Qt.AlignmentFlag.AlignTop)

    def set_selected(self, v):
        if v != self.selected:
            self.selected = v; self.update()

    def set_marked(self, v):
        if v != self.marked:
            self.marked = v; self.update()

    def mouseMoveEvent(self, ev):  # only real pointer motion moves the selection (not rows scrolling under it)
        self.popup.hover(self); super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self.rect().contains(ev.position().toPoint()):
            mods = ev.modifiers()
            if mods & Qt.KeyboardModifier.ControlModifier:
                self.popup.toggle_mark(self.id)
            elif mods & Qt.KeyboardModifier.ShiftModifier:
                self.popup.mark_range_to(self.id)
            else:
                self.popup.choose(self.id)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        box = QRectF(self.rect()).adjusted(1, 1, -1, -2)
        if self.marked:
            hl = QColor(pal.color(pal.ColorRole.Highlight)); fill = QColor(hl); fill.setAlphaF(0.26 if self.selected else 0.18)
            p.setBrush(fill); p.setPen(QPen(hl, 1.5)); p.drawRoundedRect(box, 10, 10)
        elif self.selected:
            c = QColor(pal.color(pal.ColorRole.WindowText)); c.setAlphaF(0.12)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(c); p.drawRoundedRect(QRectF(self.rect()).adjusted(0, 0, 0, -1), 10, 10)
        elif self.divider:
            c = QColor(127, 127, 127, 70)
            p.setPen(QPen(c, 1)); y = self.height() - 0.5
            p.drawLine(QPointF(14, y), QPointF(self.width() - 14, y))
        if self.is_current:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(pal.color(pal.ColorRole.Highlight))
            p.drawRoundedRect(QRectF(2, 10, 3, max(8, self.height() - 21)), 1.5, 1.5)


class KeyCap(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet("QLabel{border:1px solid rgba(127,127,127,0.45);border-radius:5px;padding:0 5px;"
                           "background:rgba(127,127,127,0.12);}")
        f = self.font(); f.setPointSizeF(max(7.0, f.pointSizeF() - 1.5)); self.setFont(f)


class Popup(QWidget):
    finished = pyqtSignal()

    def __init__(self, backend, auto_close=True):
        super().__init__()
        self.backend, self.auto_close = backend, auto_close
        self.setWindowTitle("Clipboard")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.items = []
        self.current = ""
        self.expanded = set()
        self.thumb_cache = {}
        self.rows = []
        self.sel = 0
        self.marked = set()
        self.anchor = 0
        self.ready = False
        self.empty_msg = None

        root = QVBoxLayout(self); root.setContentsMargins(14, 14, 14, 12); root.setSpacing(10)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search clipboard"); self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(34)
        self.search.setStyleSheet("QLineEdit{border-radius:17px;padding:0 14px;background:rgba(127,127,127,0.18);"
                                  f"border:1px solid {LINE};}}")
        self.search.textChanged.connect(lambda _: self.refresh(reset=True))
        self.search.installEventFilter(self)
        root.addWidget(self.search)

        # The list lives in its own bordered panel so items are clearly separated from the popup chrome.
        self.panel = QFrame(); self.panel.setObjectName("panel")
        self.panel.setStyleSheet(f"QFrame#panel{{border:1px solid {LINE};border-radius:14px;background:rgba(127,127,127,0.07);}}")
        pl = QVBoxLayout(self.panel); pl.setContentsMargins(4, 4, 4, 4); pl.setSpacing(0)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QScrollArea>QWidget>QWidget{background:transparent;}"
                                  "QScrollBar:vertical{width:8px;background:transparent;margin:2px;}"
                                  "QScrollBar::handle:vertical{background:rgba(127,127,127,0.4);border-radius:3px;min-height:24px;}"
                                  "QScrollBar::add-line,QScrollBar::sub-line{height:0;}")
        self.body = QWidget(); self.body_l = QVBoxLayout(self.body)
        self.body_l.setContentsMargins(0, 0, 4, 0); self.body_l.setSpacing(0)
        self.scroll.setWidget(self.body)
        pl.addWidget(self.scroll)
        root.addWidget(self.panel, 1)

        foot = QHBoxLayout(); foot.setSpacing(5); foot.setContentsMargins(2, 0, 0, 0)
        for key, what in (("Enter", "Copy"), ("Ctrl+P", "Pin"), ("Ctrl+A", "Select all"), ("Del", "Delete"), ("Esc", "Close")):
            foot.addWidget(KeyCap(key))
            w = QLabel(what); w.setStyleSheet("color:rgba(127,127,127,0.95);"); foot.addWidget(w)
            foot.addSpacing(5)
        foot.addStretch(1)
        self.status = QLabel(""); self.status.setStyleSheet("color:palette(highlight);font-weight:bold;"); self.status.hide()
        foot.addWidget(self.status)
        self.clear_btn = QPushButton("Clear all"); self.clear_btn.setFlat(True)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor); self.clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_btn.setToolTip("Remove all history (pinned items stay)")
        self.clear_btn.clicked.connect(self.clear_clicked)
        self._flash_timer = QTimer(self); self._flash_timer.setSingleShot(True); self._flash_timer.timeout.connect(self.end_flash)
        self._clear_armed = False
        self._clear_timer = QTimer(self); self._clear_timer.setSingleShot(True); self._clear_timer.timeout.connect(self.disarm_clear)
        foot.addWidget(self.clear_btn)
        root.addLayout(foot)

        self.resize(POPUP_W, 360)
        self.reload(reset=True)
        QTimer.singleShot(400, lambda: setattr(self, "ready", True))

    # ── model ──
    def reload(self, reset=False):
        self.items = self.backend.entries()
        self.current = self.backend.current_id()
        self.refresh(reset=reset)

    def entries(self):
        pins = sorted((i for i in self.items if i.get("pinned")), key=lambda i: -i.get("ts", 0))
        rest = [i for i in self.items if not i.get("pinned")]
        out = pins + rest
        q = self.search.text().strip().lower()
        return [i for i in out if q in haystack(i).lower()] if q else out

    def selected_id(self):
        return self.rows[self.sel].id if 0 <= self.sel < len(self.rows) else None

    def selected_row(self):
        return self.rows[self.sel] if 0 <= self.sel < len(self.rows) else None

    def refresh(self, reset=False):
        keep = None if reset else self.selected_id()
        while self.body_l.count():
            it = self.body_l.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None); w.deleteLater()
        self.rows = []
        entries = self.entries()
        self.empty_msg = None
        if not entries:
            q = self.search.text().strip()
            if not self.backend.available():
                title, sub = "Clipboard service unavailable", "mac-tahoe-clipd isn’t running."
            elif q:
                title, sub = "No results", f"Nothing matches “{q}”."
            else:
                title, sub = "Nothing copied yet", "Text and images you copy will appear here."
            box = QLabel(f"<div style='text-align:center'><b>{title}</b><br><span style='opacity:0.6'>{sub}</span></div>")
            box.setAlignment(Qt.AlignmentFlag.AlignCenter); box.setTextFormat(Qt.TextFormat.RichText)
            box.setMinimumHeight(140); self.empty_msg = box
            self.body_l.addWidget(box)
        else:
            has_pins = any(i.get("pinned") for i in entries)
            for n, item in enumerate(entries):
                pinned = bool(item.get("pinned"))
                if has_pins and (n == 0 or bool(entries[n - 1].get("pinned")) != pinned):
                    self.body_l.addWidget(self.header("Pinned" if pinned else "Recent"))
                last_in_section = n == len(entries) - 1 or bool(entries[n + 1].get("pinned")) != pinned
                row = Row(self, item, item["id"] == self.current, item["id"] in self.expanded, divider=not last_in_section)
                self.rows.append(row); self.body_l.addWidget(row)
        self.body_l.addStretch(1)
        self.sel = 0
        if keep is not None:
            for i, r in enumerate(self.rows):
                if r.id == keep:
                    self.sel = i; break
        self.marked &= {r.id for r in self.rows}
        self.anchor = self.sel
        self.apply_selection(scroll=not reset)
        self.clear_btn.setEnabled(any(not i.get("pinned") for i in self.items))
        QTimer.singleShot(0, self.fit)

    def header(self, text):
        l = QLabel(text.upper()); l.setContentsMargins(12, 8, 0, 3)
        f = l.font(); f.setPointSizeF(max(7.0, f.pointSizeF() - 2)); f.setBold(True)
        l.setFont(f); l.setStyleSheet("color:rgba(127,127,127,0.95);")
        return l

    def fit(self):
        maxh = 560
        scr = self.screen()
        if scr is not None:
            maxh = max(300, int(scr.availableGeometry().height() * 0.8))
        self.body.setFixedWidth(max(100, self.scroll.viewport().width()))
        content = self.body.sizeHint().height()
        if self.body_l.hasHeightForWidth():
            content = max(content, self.body_l.totalHeightForWidth(self.body.width()))
        chrome = 14 + 34 + 10 + 10 + 30 + 12 + 6 + 10
        self.resize(POPUP_W, max(240, min(maxh, content + chrome)))

    def apply_selection(self, scroll=True):
        for i, r in enumerate(self.rows):
            r.set_selected(i == self.sel)
            r.set_marked(r.id in self.marked)
        if not self._flash_timer.isActive():
            self.end_flash()
        if scroll and 0 <= self.sel < len(self.rows):
            self.scroll.ensureWidgetVisible(self.rows[self.sel], 0, 8)

    def step(self, delta, extend=False):
        if self.rows:
            if extend and not self.marked:
                self.anchor = self.sel
            self.sel = max(0, min(len(self.rows) - 1, self.sel + delta))
            if extend:
                self.mark_range(self.anchor, self.sel)
            self.apply_selection()

    # ── multi-select ──
    def mark_range(self, a, b):
        lo, hi = sorted((a, b))
        self.marked = {r.id for r in self.rows[lo:hi + 1]}

    def mark_range_to(self, item_id):
        for i, r in enumerate(self.rows):
            if r.id == item_id:
                if not self.marked:
                    self.anchor = self.sel
                self.sel = i; self.mark_range(self.anchor, i); self.apply_selection(scroll=False); return

    def toggle_mark(self, item_id):
        self.marked ^= {item_id}
        for i, r in enumerate(self.rows):
            if r.id == item_id:
                self.sel = i; self.anchor = i
        self.apply_selection(scroll=False)

    def select_all(self):
        self.marked = {r.id for r in self.rows}
        self.apply_selection(scroll=False)

    def flash(self, msg, ms=2500):
        self.status.setText(msg); self.status.show()
        self._flash_timer.start(ms)

    def end_flash(self):
        n = len(self.marked)
        self.status.setText(f"{n} selected"); self.status.setVisible(n > 0)

    def clear_marks(self):
        self.marked = set(); self.apply_selection(scroll=False)

    def targets(self):
        """Entries an action applies to: the marked ones, otherwise the current one."""
        if self.marked:
            return [r.id for r in self.rows if r.id in self.marked]
        sid = self.selected_id()
        return [sid] if sid is not None else []

    def hover(self, row):
        if row in self.rows:
            self.sel = self.rows.index(row); self.apply_selection(scroll=False)

    # ── actions ──
    def choose(self, item_id):
        self.backend.copy(item_id)
        QTimer.singleShot(80, self.finished.emit)

    def toggle_pin(self, item_id):
        self.pin_many([item_id])

    def pin_many(self, item_ids):
        chosen = [i for i in self.items if i["id"] in set(item_ids)]
        if not chosen:
            return
        make_pinned = any(not i.get("pinned") for i in chosen)   # mixed selection -> pin them all
        for i in chosen:
            if bool(i.get("pinned")) != make_pinned:
                self.backend.set_pinned(i["id"], make_pinned)
        self.reload()

    def delete(self, item_id):
        self.delete_many([item_id])

    def delete_many(self, item_ids):
        """Pinned items are never deleted: unpin them first."""
        item_ids = list(item_ids)
        pinned = {i["id"] for i in self.items if i.get("pinned")}
        doomed = [i for i in item_ids if i not in pinned]
        if len(doomed) < len(item_ids):
            self.flash("Pinned items stay \u2014 unpin to delete")
        if not doomed:
            return
        old = self.sel
        for i in doomed:
            self.expanded.discard(i); self.marked.discard(i)
            self.backend.remove(i)
        self.reload(reset=True)
        self.sel = min(old, len(self.rows) - 1) if self.rows else 0
        self.anchor = self.sel
        self.apply_selection()

    def toggle_expand(self, item_id):
        item = next((i for i in self.items if i["id"] == item_id), None)
        if item is None or item["kind"] != "text":
            return
        self.expanded ^= {item_id}
        self.refresh()

    def clear_clicked(self):
        if not self._clear_armed:
            self._clear_armed = True; self.clear_btn.setText("Clear all?")
            self.clear_btn.setStyleSheet("QPushButton{color:#ff5f57;font-weight:bold;}")
            self._clear_timer.start(3000); return
        self.disarm_clear()
        self.backend.clear()
        self.reload(reset=True)

    def disarm_clear(self):
        self._clear_armed = False; self.clear_btn.setText("Clear all"); self.clear_btn.setStyleSheet("")

    # ── input ──
    def eventFilter(self, obj, ev):
        if obj is self.search and ev.type() == ev.Type.KeyPress:
            k, m = ev.key(), ev.modifiers()
            ctrl = bool(m & Qt.KeyboardModifier.ControlModifier)
            shift = bool(m & Qt.KeyboardModifier.ShiftModifier)
            if k == Qt.Key.Key_Down: self.step(1, extend=shift); return True
            if k == Qt.Key.Key_Up: self.step(-1, extend=shift); return True
            if k == Qt.Key.Key_PageDown: self.step(4, extend=shift); return True
            if k == Qt.Key.Key_PageUp: self.step(-4, extend=shift); return True
            if ctrl and k == Qt.Key.Key_A:
                self.select_all(); return True
            sid = self.selected_id()
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if sid is not None: self.choose(sid)
                return True
            if k == Qt.Key.Key_Delete and (self.marked or not self.search.text()):
                self.delete_many(self.targets()); return True        # with text typed, Delete edits the text instead
            if ctrl and sid is not None:
                if k == Qt.Key.Key_P: self.pin_many(self.targets()); return True
                if k == Qt.Key.Key_D: self.delete_many(self.targets()); return True
                if k == Qt.Key.Key_E: self.toggle_expand(sid); return True
        return super().eventFilter(obj, ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            if self.marked:
                self.clear_marks()          # first Esc drops the multi-selection, the next one closes
            else:
                self.finished.emit()
        else:
            super().keyPressEvent(ev)

    def changeEvent(self, ev):
        if self.auto_close and ev.type() == ev.Type.ActivationChange and self.ready and not self.isActiveWindow():
            self.finished.emit()
        super().changeEvent(ev)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if ev.oldSize().width() != ev.size().width():
            QTimer.singleShot(0, self.fit)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.search.setFocus()
        self.sel = 0; self.anchor = 0; self.apply_selection(scroll=True)    # first entry is focused on open

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(self.palette().color(self.palette().ColorRole.Window)); bg.setAlphaF(0.92)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        edge = QColor(255, 255, 255, 46) if bg.lightnessF() < 0.5 else QColor(0, 0, 0, 40)
        p.setBrush(bg); p.setPen(QPen(edge, 1)); p.drawRoundedRect(r, 20, 20)


# ── process plumbing ──────────────────────────────────────────────────────

def toggle_singleton():
    """Second launch closes the first (Meta+V toggles). Returns True if it closed a running one."""
    try:
        with open(LOCK) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        with open(f"/proc/{pid}/cmdline") as f:
            if "clipboard.py" in f.read():
                os.kill(pid, signal.SIGTERM)
                return True
    except (OSError, ValueError):
        pass
    with open(LOCK, "w") as f:
        f.write(str(os.getpid()))
    return False


def main():
    if toggle_singleton():
        return 0
    app = QApplication(sys.argv)
    app.setDesktopFileName(APP_ID); app.setApplicationName(APP_ID)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    pump = QTimer(); pump.start(150); pump.timeout.connect(lambda: None)  # let Python run signal handlers
    be = ensure_daemon()
    migrate_old_pins(be)
    w = Popup(be)
    w.finished.connect(app.quit)
    w.show()
    rc = app.exec()
    pump.stop(); w.backend = None; w.hide(); w.deleteLater(); app.processEvents()
    del w
    try:
        with open(LOCK) as f:
            if f.read().strip() == str(os.getpid()):
                os.remove(LOCK)
    except OSError:
        pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
