"""Clipboard popup behaviour: rows, thumbnails, search, keyboard, mouse, pins, multi-select, delete.

Runs the real PyQt6 popup offscreen against an in-memory backend.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets")
pytest.importorskip("PyQt6.QtDBus")
pytest.importorskip("PyQt6.QtTest")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt, QPoint  # noqa: E402
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPalette  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "clip", Path(__file__).resolve().parents[1] / "src/offline/clipboard/clipboard.py")
clip = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clip)

app = QApplication.instance() or QApplication([])
TMP = tempfile.mkdtemp()

LONG_URL = "https://example.com/" + "/".join(f"segment{i}" for i in range(40)) + "?q=" + "x" * 80
MULTI = "\n".join(f"line {i}" for i in range(20))
PARA = ("The quick brown fox jumps over the lazy dog. " * 12).strip()
HUGE = "A" * 5000
CODE = "def f(x):\n    if x:\n        return 1\n    return 0"
CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
_n = [0]


def T(text, pinned=False):
    _n[0] += 1
    return {"id": "t" + str(abs(hash(text))), "kind": "text", "text": text, "pinned": pinned, "ts": 1000 - _n[0]}


def I(w, h, pinned=False, missing=False):  # noqa: E743
    _n[0] += 1
    path = os.path.join(TMP, f"img{_n[0]}.png")
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(255, 120, 40))
    g.setColorAt(1, QColor(30, 80, 255))
    p.fillRect(img.rect(), g)
    p.end()
    if not missing:
        img.save(path, "PNG")
    return {"id": f"i{_n[0]}", "kind": "image", "w": w, "h": h, "path": path, "pinned": pinned, "ts": 1000 - _n[0],
            "bytes": os.path.getsize(path) if not missing else 1234}


class Fake:
    def __init__(self, items=None, current="", ok=True):
        self.items = [dict(i) for i in (items or [])]
        self.cur, self.ok = current, ok
        self.copied, self.removed, self.cleared, self.pins_set, self.added = [], [], 0, [], []

    def available(self): return self.ok
    def entries(self): return [dict(i) for i in self.items]
    def current_id(self): return self.cur
    def copy(self, i): self.copied.append(i)
    def remove(self, i): self.removed.append(i); self.items = [x for x in self.items if x["id"] != i]
    def clear(self): self.cleared += 1; self.items = [x for x in self.items if x.get("pinned")]
    def add_text(self, t, pinned): self.added.append((t, pinned))

    def set_pinned(self, i, b):
        self.pins_set.append((i, b))
        for x in self.items:
            if x["id"] == i:
                x["pinned"] = b


def make(items=None, current="", ok=True):
    be = Fake(items, current, ok)
    p = clip.Popup(be, auto_close=False)
    done = []
    p.finished.connect(lambda: done.append(1))
    p.done, p.be = done, be
    p.show()
    settle()
    return p


def settle(ms=60): QTest.qWait(ms)
def key(p, k, mod=Qt.KeyboardModifier.NoModifier): QTest.keyClick(p.search, k, mod); settle(30)


def click(w, pos=None):
    QTest.mouseClick(w, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos if pos is not None else w.rect().center())
    settle(40)


def clipped(row): lb = row.label; return lb.height() + 1 < lb.heightForWidth(lb.width())
def texts(p): return [r.text for r in p.rows]
def ids(p): return [r.id for r in p.rows]


class Tests(unittest.TestCase):
    def tearDown(self):
        for w in QApplication.topLevelWidgets():
            w.close(); w.deleteLater()
        QTest.qWait(20)

    # ── helpers ──
    def test_display_text_rules(self):
        self.assertEqual(clip.display_text("hello", False), ("hello", False))
        s, cut = clip.display_text(MULTI, False)
        self.assertTrue(cut and s.endswith("\u2026")); self.assertEqual(s.count("\n"), clip.CAP_LINES - 1)
        s, cut = clip.display_text("x" * 500, False)
        self.assertTrue(cut and s.endswith("\u2026") and len(s) <= clip.CAP_CHARS + 1)
        s, cut = clip.display_text(HUGE, True)
        self.assertTrue(cut); self.assertIn("2000 more characters", s)
        self.assertEqual(clip.display_text(MULTI, True), (MULTI, False))
        self.assertEqual(clip.display_text("\n\n  hi\r\nthere\n\n", False)[0], "  hi\nthere")
        self.assertEqual(clip.display_text("emoji \U0001F600 \u65e5\u672c", False)[0], "emoji \U0001F600 \u65e5\u672c")

    def test_soft_breaks_and_sizes(self):
        out = clip.soft_breaks(LONG_URL)
        self.assertIn(clip.ZWSP, out); self.assertEqual(out.replace(clip.ZWSP, ""), LONG_URL)
        t = "a  b\tc\nd"
        self.assertEqual(clip.soft_breaks(t), t)
        self.assertEqual(clip.soft_breaks("y" * 100).replace(clip.ZWSP, ""), "y" * 100)
        self.assertEqual(clip.human_size(512), "512 B"); self.assertEqual(clip.human_size(2048), "2 KB")
        self.assertEqual(clip.human_size(1536), "1.5 KB"); self.assertEqual(clip.human_size(5 * 1024 * 1024), "5 MB")

    # ── states ──
    def test_empty_history(self):
        p = make([])
        self.assertIn("Nothing copied yet", p.empty_msg.text()); self.assertFalse(p.clear_btn.isEnabled()); self.assertEqual(p.rows, [])
        key(p, Qt.Key.Key_Return); key(p, Qt.Key.Key_D, CTRL); key(p, Qt.Key.Key_P, CTRL); key(p, Qt.Key.Key_E, CTRL)
        self.assertEqual((p.be.copied, p.be.removed, p.be.pins_set, p.done), ([], [], [], []))

    def test_service_unavailable(self):
        self.assertIn("unavailable", make([], ok=False).empty_msg.text())

    # ── text rows never clip ──
    def test_rows_fit_content(self):
        p = make([T("short one"), T(PARA), T(LONG_URL), T(MULTI), T(CODE), T("emoji \U0001F600 \u65e5\u672c\u8a9e caf\u00e9"), T(HUGE), T("tail")])
        for r in p.rows:
            self.assertFalse(clipped(r), f"clipped: {r.text[:30]!r}")
        h = {r.text: r.height() for r in p.rows}
        self.assertLess(h["short one"], h[PARA]); self.assertLess(h["short one"], h[MULTI])
        for r in p.rows:
            shown, cut = clip.display_text(r.text, False)
            self.assertEqual(r.more is not None, cut, r.text[:20])
            self.assertEqual(r.label.text().replace(clip.ZWSP, ""), shown)

    def test_expand_collapse_mouse_and_key(self):
        p = make([T(MULTI), T("x")])
        r = p.rows[0]; h0 = r.height()
        click(r.more); r = p.rows[0]
        self.assertEqual(p.be.copied, []); self.assertGreater(r.height(), h0)
        self.assertEqual(r.label.text().replace(clip.ZWSP, ""), MULTI)
        self.assertEqual(r.more.text(), "Show less"); self.assertFalse(clipped(r))
        click(r.more); self.assertEqual(p.rows[0].height(), h0)
        key(p, Qt.Key.Key_E, CTRL); self.assertGreater(p.rows[0].height(), h0)
        key(p, Qt.Key.Key_E, CTRL); self.assertEqual(p.rows[0].height(), h0)
        p2 = make([T(HUGE)]); click(p2.rows[0].more)
        self.assertFalse(clipped(p2.rows[0])); self.assertIn("more characters", p2.rows[0].label.text())

    # ── image rows ──
    def test_image_row_preview(self):
        p = make([I(640, 360), T("t")])
        r = p.rows[0]
        self.assertEqual(r.kind, "image"); self.assertIsNotNone(r.thumb.pix)
        self.assertLessEqual(r.thumb.width(), clip.THUMB_MAX_W); self.assertLessEqual(r.thumb.height(), clip.THUMB_MAX_H)
        self.assertAlmostEqual(r.thumb.width() / r.thumb.height(), 640 / 360, delta=0.03)
        self.assertEqual(r.caption.text().split(" \u00b7 ")[1], "640 \u00d7 360"); self.assertIn("KB", r.caption.text())
        self.assertIsNone(r.more); self.assertGreater(r.height(), r.thumb.height())

    def test_image_sizes_and_aspect(self):
        dims = [(4000, 1000), (300, 2000), (40, 30), (1, 1), (2000, 2000)]
        p = make([I(w, h) for w, h in dims])
        for r, (w, h) in zip(p.rows, dims):
            tw, th = r.thumb.width(), r.thumb.height()
            self.assertLessEqual(tw, clip.THUMB_MAX_W); self.assertLessEqual(th, clip.THUMB_MAX_H)
            self.assertGreater(tw, 0); self.assertGreater(th, 0)
            if w > 8 and h > 8:
                self.assertAlmostEqual(tw / th, w / h, delta=0.05 * (w / h) + 0.05)
        self.assertEqual((p.rows[2].thumb.width(), p.rows[2].thumb.height()), (40, 30))  # small images are not upscaled

    def test_image_missing_file_placeholder(self):
        p = make([I(640, 360, missing=True)])
        r = p.rows[0]
        self.assertIsNone(r.thumb.pix); self.assertGreater(r.thumb.height(), 0)
        click(r, QPoint(30, r.height() // 2)); settle(150)
        self.assertEqual(len(p.be.copied), 1)

    def test_image_actions_mouse_keyboard(self):
        a, b, c = I(640, 360), I(100, 100), T("txt")
        p = make([a, b, c])
        click(p.rows[0].b_copy); settle(150)
        self.assertEqual(p.be.copied, [a["id"]]); self.assertEqual(len(p.done), 1)
        p = make([a, b, c]); click(p.rows[1].b_pin)
        self.assertEqual(p.be.pins_set, [(b["id"], True)]); self.assertEqual(p.rows[0].id, b["id"]); self.assertEqual(p.be.copied, [])
        click(p.rows[0].b_pin); self.assertEqual(p.be.pins_set[-1], (b["id"], False))
        click(p.rows[0].b_del)
        self.assertEqual(p.be.removed, [a["id"]]); self.assertEqual(len(p.rows), 2); self.assertEqual(p.be.copied, [])
        p = make([a, b])
        key(p, Qt.Key.Key_E, CTRL); self.assertEqual(len(p.rows), 2)          # expand is a no-op for images
        key(p, Qt.Key.Key_Down); key(p, Qt.Key.Key_D, CTRL)
        self.assertEqual(p.be.removed, [b["id"]]); self.assertEqual(ids(p), [a["id"]])
        key(p, Qt.Key.Key_Return); settle(150); self.assertEqual(p.be.copied, [a["id"]])

    def test_search_images_and_text(self):
        p = make([I(640, 360), I(100, 50), T("hello 640 world"), T("other")])
        p.search.setText("640"); settle(); self.assertEqual(len(p.rows), 2)
        p.search.setText("image"); settle(); self.assertEqual([r.kind for r in p.rows], ["image", "image"])
        p.search.setText("100x50"); settle(); self.assertEqual(len(p.rows), 1)
        p.search.setText("zzz"); settle(); self.assertIn("No results", p.empty_msg.text())

    # ── window ──
    def test_window_height_bounds_and_scroll(self):
        one = make([T("a")])
        self.assertGreaterEqual(one.height(), 240)
        many = make([T(f"{i} " + PARA) if i % 3 else I(800, 500) for i in range(40)])
        mx = many.screen().availableGeometry().height() * 0.8
        self.assertLessEqual(many.height(), mx + 1); self.assertGreater(many.height(), one.height())
        sb = many.scroll.verticalScrollBar()
        self.assertGreater(sb.maximum(), 0)
        for _ in range(60):
            key(many, Qt.Key.Key_Down)
        self.assertEqual(many.sel, 39); self.assertGreater(sb.value(), 0)
        top = many.rows[39].mapTo(many.scroll.viewport(), QPoint(0, 0)).y()
        self.assertTrue(0 <= top <= many.scroll.viewport().height())

    def test_resize_rewraps(self):
        p = make([T(PARA), T(LONG_URL)])
        h1 = [r.height() for r in p.rows]
        p.setFixedWidth(900); settle(120)
        h2 = [r.height() for r in p.rows]
        self.assertTrue(all(h2[i] <= h1[i] for i in range(2)) and any(h2[i] < h1[i] for i in range(2)))
        for r in p.rows:
            self.assertFalse(clipped(r))

    # ── boundaries ──
    def test_panel_and_dividers(self):
        p = make([T("a"), T("b"), T("c")])
        self.assertIn("border", p.panel.styleSheet()); self.assertIs(p.scroll.parent(), p.panel)
        self.assertEqual([r.divider for r in p.rows], [True, True, False])
        p = make([T("p1", True), T("p2", True), T("r1"), T("r2")])
        self.assertEqual([r.divider for r in p.rows], [True, False, True, False])    # no divider at section ends
        pr = p.panel.geometry()
        self.assertGreater(pr.left(), 0); self.assertGreater(p.height() - pr.bottom(), 20)   # footer sits outside the panel
        self.assertGreater(pr.top(), p.search.geometry().bottom())
        for r in p.rows:
            self.assertTrue(p.panel.rect().contains(r.mapTo(p.panel, QPoint(0, 0))))

    def test_divider_pixels_drawn(self):
        r = make([T("a"), T("b")]).rows[0]
        img = r.grab().toImage()
        y = img.height() - 1
        self.assertTrue(all(img.pixelColor(x, y).alpha() > 0 for x in range(20, img.width() - 20, 40)))

    # ── keyboard ──
    def test_keyboard_nav_and_enter(self):
        p = make([T(s) for s in ("a1", "b2", "c3", "d4", "e5", "f6", "g7")])
        key(p, Qt.Key.Key_Up); self.assertEqual(p.sel, 0)
        key(p, Qt.Key.Key_Down); key(p, Qt.Key.Key_Down); self.assertEqual(p.sel, 2)
        key(p, Qt.Key.Key_PageDown); self.assertEqual(p.sel, 6)
        key(p, Qt.Key.Key_Down); self.assertEqual(p.sel, 6)
        key(p, Qt.Key.Key_PageUp); self.assertEqual(p.sel, 2)
        key(p, Qt.Key.Key_Return); settle(150)
        self.assertEqual(p.be.copied, [p.rows[2].id]); self.assertEqual(p.done, [1])

    def test_escape_closes(self):
        p = make([T("a")])
        QTest.keyClick(p, Qt.Key.Key_Escape); settle(30)
        self.assertEqual(len(p.done), 1)

    def test_pin_unpin_keyboard(self):
        a, b, c = T("a"), T("b"), T("c")
        p = make([a, b, c]); key(p, Qt.Key.Key_Down); key(p, Qt.Key.Key_P, CTRL)
        self.assertEqual(texts(p), ["b", "a", "c"]); self.assertEqual(p.be.pins_set, [(b["id"], True)])
        self.assertTrue(p.rows[0].pinned and p.rows[0].b_pin.active); self.assertEqual(p.selected_id(), b["id"])
        key(p, Qt.Key.Key_P, CTRL)
        self.assertEqual(texts(p), ["a", "b", "c"]); self.assertEqual(p.be.copied, [])

    def test_delete_keyboard(self):
        p = make([T("a"), T("b"), T("c")]); key(p, Qt.Key.Key_Down); key(p, Qt.Key.Key_D, CTRL)
        self.assertEqual(texts(p), ["a", "c"]); self.assertEqual(p.sel, 1)
        key(p, Qt.Key.Key_D, CTRL); key(p, Qt.Key.Key_D, CTRL)
        self.assertEqual(p.rows, []); self.assertIn("Nothing copied yet", p.empty_msg.text())
        key(p, Qt.Key.Key_D, CTRL); self.assertEqual(p.be.copied, [])

    # ── mouse ──
    def test_mouse_row_click_copies(self):
        p = make([T("alpha"), T("beta")]); r = p.rows[1]
        click(r, QPoint(40, r.height() // 2)); settle(150)
        self.assertEqual(p.be.copied, [r.id]); self.assertEqual(p.done, [1])

    def test_mouse_icons_are_independent(self):
        a, b, c = T("alpha"), T("beta"), T("gamma")
        p = make([a, b, c]); click(p.rows[0].b_copy); settle(150)
        self.assertEqual(p.be.copied, [a["id"]]); self.assertEqual(len(p.done), 1)
        p = make([a, b, c]); click(p.rows[1].b_pin)
        self.assertEqual(p.be.copied, []); self.assertEqual(p.rows[0].text, "beta"); self.assertTrue(p.rows[0].pinned)
        click(p.rows[0].b_pin); self.assertEqual(texts(p), ["alpha", "beta", "gamma"])
        click(p.rows[2].b_del)
        self.assertEqual(p.be.removed, [c["id"]]); self.assertEqual(len(p.rows), 2); self.assertEqual((p.be.copied, p.done), ([], []))

    def test_icon_tooltips(self):
        p = make([T("a")]); r = p.rows[0]
        self.assertIn("Enter", r.b_copy.toolTip()); self.assertIn("Ctrl+P", r.b_pin.toolTip()); self.assertIn("Del", r.b_del.toolTip())
        click(r.b_pin); self.assertTrue(p.rows[0].b_pin.toolTip().startswith("Unpin"))

    def test_hover_moves_selection_only_on_motion(self):
        p = make([T("a"), T("b"), T("c")]); r2 = p.rows[2]
        QTest.mouseMove(p.scroll.viewport(), r2.mapTo(p.scroll.viewport(), QPoint(30, 10))); settle()
        self.assertEqual(p.sel, 2)
        key(p, Qt.Key.Key_Up); self.assertEqual(p.sel, 1)

    # ── pins / clear / current ──
    def test_pins_sections_order(self):
        old, new = T("old-pin", True), T("new-pin", True)
        old["ts"], new["ts"] = 5, 50
        p = make([T("a"), old, T("b"), new])
        self.assertEqual(texts(p), ["new-pin", "old-pin", "a", "b"])

        def heads(w):
            return [x.text() for x in w.body.findChildren(clip.QLabel) if x.text() in ("PINNED", "RECENT")]
        self.assertEqual(heads(p), ["PINNED", "RECENT"])
        self.assertEqual(heads(make([T("a")])), [])
        self.assertEqual(heads(make([T("only", True)])), ["PINNED"])

    def test_clear_all_two_step_keeps_pins(self):
        p = make([T("a"), T("b"), T("pin", True), I(10, 10)]); click(p.clear_btn)
        self.assertEqual(p.clear_btn.text(), "Clear all?"); self.assertEqual(p.be.cleared, 0)
        QTest.qWait(3200)
        self.assertEqual(p.clear_btn.text(), "Clear all"); self.assertEqual(p.be.cleared, 0)
        click(p.clear_btn); click(p.clear_btn)
        self.assertEqual(p.be.cleared, 1); self.assertEqual(texts(p), ["pin"]); self.assertFalse(p.clear_btn.isEnabled())

    def test_current_indicator(self):
        a, b = T("a"), T("b")
        p = make([a, b], current=b["id"])
        self.assertEqual([r.is_current for r in p.rows], [False, True])

    # ── width / first-entry focus ──
    def test_width_and_first_entry_focus(self):
        p = make([T("a"), T("b")])
        self.assertEqual(p.width(), clip.POPUP_W); self.assertGreaterEqual(clip.POPUP_W, 780)
        self.assertEqual(p.sel, 0); self.assertTrue(p.rows[0].selected); self.assertFalse(p.rows[1].selected)
        key(p, Qt.Key.Key_Return); settle(150)
        self.assertEqual(p.be.copied, [p.rows[0].id])                             # Enter right away copies the first entry
        pp = make([T("x"), T("pin", True), T("y")])
        self.assertTrue(pp.rows[0].selected and pp.rows[0].pinned)               # pinned entry comes first and is focused
        pp.search.setText("y"); settle()
        self.assertTrue(pp.rows[0].selected and pp.sel == 0)                    # after filtering the first match is focused
        pp.search.setText(""); settle(); self.assertEqual(pp.sel, 0)

    # ── multi-select and delete ──
    def test_ctrl_a_selects_all_and_delete_removes_only_unpinned(self):
        a, b, c, d, e = T("a"), T("b", True), I(50, 50), T("d"), I(30, 30, True)
        p = make([a, b, c, d, e]); key(p, Qt.Key.Key_A, CTRL)
        self.assertEqual(p.marked, {x["id"] for x in (a, b, c, d, e)}); self.assertEqual(p.status.text(), "5 selected")
        key(p, Qt.Key.Key_Delete)
        self.assertEqual(sorted(p.be.removed), sorted(x["id"] for x in (a, c, d)))        # pinned text + pinned image survive
        self.assertEqual(sorted([r.text for r in p.rows if r.kind == "text"] + [r.id for r in p.rows if r.kind == "image"]),
                         sorted(["b", e["id"]]))
        self.assertTrue(all(r.pinned for r in p.rows)); self.assertEqual(p.be.copied, [])
        self.assertIn("unpin", p.status.text().lower())
        key(p, Qt.Key.Key_A, CTRL); key(p, Qt.Key.Key_Delete); key(p, Qt.Key.Key_D, CTRL)   # only pins left
        self.assertEqual(len(p.rows), 2); self.assertEqual(len(p.be.removed), 3)

    def test_pinned_cannot_be_deleted_until_unpinned(self):
        a, b = T("a", True), T("b")
        p = make([a, b]); r = p.rows[0]
        self.assertTrue(r.b_del.locked); self.assertIn("unpin", r.b_del.toolTip().lower()); self.assertFalse(p.rows[1].b_del.locked)
        click(r.b_del); key(p, Qt.Key.Key_Delete); key(p, Qt.Key.Key_D, CTRL)
        self.assertEqual(p.be.removed, []); self.assertEqual(len(p.rows), 2)
        click(p.rows[0].b_pin)                                                            # unpin "a"
        row_a = next(x for x in p.rows if x.id == a["id"])
        self.assertFalse(row_a.b_del.locked)
        click(row_a.b_del); self.assertEqual(p.be.removed, [a["id"]])

    def test_delete_key_semantics(self):
        a, b, c = T("alpha"), T("beta"), T("gamma")
        p = make([a, b, c]); key(p, Qt.Key.Key_Delete)
        self.assertEqual(p.be.removed, [a["id"]]); self.assertEqual(texts(p), ["beta", "gamma"])    # no marks -> current entry
        p = make([a, b, c]); QTest.keyClicks(p.search, "gam"); settle(); key(p, Qt.Key.Key_Left); key(p, Qt.Key.Key_Delete)
        self.assertEqual(p.be.removed, []); self.assertEqual(p.search.text(), "ga")                 # text typed -> Delete edits the text
        p = make([a, b, c]); p.search.setText("a"); settle(); key(p, Qt.Key.Key_A, CTRL); key(p, Qt.Key.Key_Delete)
        self.assertEqual(sorted(p.be.removed), sorted([a["id"], b["id"], c["id"]]))                 # marked entries win even with search text
        p = make([a, b, c]); p.search.setText("gam"); settle(); key(p, Qt.Key.Key_A, CTRL); key(p, Qt.Key.Key_Delete)
        self.assertEqual(p.be.removed, [c["id"]])                                                    # only the visible ones are selected
        p.search.setText(""); settle(); self.assertEqual(texts(p), ["alpha", "beta"])

    def test_shift_range_ctrl_click_escape(self):
        items = [T(x) for x in "abcde"]
        p = make(items)
        key(p, Qt.Key.Key_Down, SHIFT); key(p, Qt.Key.Key_Down, SHIFT)
        self.assertEqual(p.marked, {items[0]["id"], items[1]["id"], items[2]["id"]})
        key(p, Qt.Key.Key_Up, SHIFT); self.assertEqual(p.marked, {items[0]["id"], items[1]["id"]})
        QTest.keyClick(p.search, Qt.Key.Key_Escape); settle()
        self.assertEqual(p.marked, set()); self.assertEqual(p.done, [])                      # first Esc clears the selection
        QTest.keyClick(p.search, Qt.Key.Key_Escape); settle(30)
        self.assertEqual(len(p.done), 1)                                                     # second Esc closes
        p = make(items)

        def click_mod(w, m):
            QTest.mouseClick(w, Qt.MouseButton.LeftButton, m, QPoint(40, w.height() // 2)); settle(40)
        click_mod(p.rows[1], CTRL); click_mod(p.rows[3], CTRL)
        self.assertEqual(p.marked, {items[1]["id"], items[3]["id"]}); self.assertEqual(p.be.copied, [])
        click_mod(p.rows[1], CTRL); self.assertEqual(p.marked, {items[3]["id"]})
        click_mod(p.rows[0], SHIFT); self.assertEqual(p.be.copied, [])
        p.clear_marks(); click(p.rows[2], QPoint(40, p.rows[2].height() // 2)); settle(150)
        self.assertEqual(p.be.copied, [items[2]["id"]])                                      # plain click still copies

    def test_bulk_pin_and_marks_survive(self):
        a, b, c = T("a"), T("b", True), T("c")
        p = make([a, b, c]); key(p, Qt.Key.Key_A, CTRL); key(p, Qt.Key.Key_P, CTRL)
        self.assertEqual(sorted(i for i, v in p.be.pins_set if v), sorted([a["id"], c["id"]]))
        self.assertTrue(all(r.pinned for r in p.rows))                                       # mixed selection -> pin them all
        self.assertEqual(len(p.marked), 3)
        key(p, Qt.Key.Key_P, CTRL); self.assertFalse(any(r.pinned for r in p.rows))          # all pinned -> unpin all
        key(p, Qt.Key.Key_D, CTRL); self.assertEqual(len(p.be.removed), 3)                   # Ctrl+D also deletes the selection

    def test_icons_delete_only_their_row_even_with_marks(self):
        a, b, c = T("a"), T("b"), T("c")
        p = make([a, b, c]); key(p, Qt.Key.Key_A, CTRL)
        click(p.rows[1].b_del)
        self.assertEqual(p.be.removed, [b["id"]]); self.assertEqual(len(p.rows), 2); self.assertEqual(p.marked, {a["id"], c["id"]})

    # ── plumbing ──
    def test_migrate_old_pins(self):
        clip.OLD_PINS_FILE = os.path.join(tempfile.mkdtemp(), "clipboard-pins.json")
        with open(clip.OLD_PINS_FILE, "w") as f:
            json.dump(["one", "two", 5, ""], f)
        be = Fake([])
        clip.migrate_old_pins(be)
        self.assertEqual(be.added, [("two", True), ("one", True)])
        self.assertFalse(os.path.exists(clip.OLD_PINS_FILE)); self.assertTrue(os.path.exists(clip.OLD_PINS_FILE + ".migrated"))
        with open(clip.OLD_PINS_FILE, "w") as f:
            f.write("{broken")
        be = Fake([]); clip.migrate_old_pins(be); self.assertEqual(be.added, [])
        with open(clip.OLD_PINS_FILE, "w") as f:
            json.dump(["x"], f)
        be = Fake([], ok=False); clip.migrate_old_pins(be); self.assertTrue(os.path.exists(clip.OLD_PINS_FILE))
        os.remove(clip.OLD_PINS_FILE); clip.migrate_old_pins(Fake([]))                       # missing file: no crash

    def test_backend_parsing_is_defensive(self):
        be = clip.DaemonBackend.__new__(clip.DaemonBackend)
        be.available = lambda: True
        for raw, n in (("not json", 0), ("{}", 0), ("[]", 0),
                       ('[{"id":"a","kind":"text","text":"x"},{"kind":"text"},{"id":"b","kind":"weird"},5]', 1)):
            be._call = lambda name, *a, raw=raw: raw
            self.assertEqual(len(be.entries()), n, raw)

    def test_renders_in_light_and_dark(self):
        items = [T("sudo systemctl restart sddm", True), I(766, 452), T("short one"), T(PARA), I(300, 700), T(LONG_URL), T(MULTI)]
        try:
            for win, txt in ((QColor(36, 38, 40), QColor(235, 235, 235)), (QColor(246, 246, 247), QColor(30, 30, 30))):
                pal = QPalette()
                pal.setColor(QPalette.ColorRole.Window, win); pal.setColor(QPalette.ColorRole.WindowText, txt)
                pal.setColor(QPalette.ColorRole.Text, txt); pal.setColor(QPalette.ColorRole.Base, win)
                pal.setColor(QPalette.ColorRole.Highlight, QColor(10, 132, 255))
                app.setPalette(pal)
                for popup in (make(items, current=items[1]["id"]), make([])):
                    self.assertFalse(popup.grab().isNull())
        finally:
            app.setPalette(QPalette())

    def test_singleton_toggle(self):
        clip.LOCK = os.path.join(tempfile.mkdtemp(), "lock.pid")
        child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)", "clipboard.py"])
        try:
            with open(clip.LOCK, "w") as f:
                f.write(str(child.pid))
            self.assertTrue(clip.toggle_singleton()); child.wait(timeout=5)
            self.assertEqual(child.returncode, -signal.SIGTERM)
        finally:
            if child.poll() is None:
                child.kill()
        with open(clip.LOCK, "w") as f:
            f.write("999999")
        self.assertFalse(clip.toggle_singleton())
        with open(clip.LOCK) as f:
            self.assertEqual(f.read(), str(os.getpid()))
        other = subprocess.Popen(["sleep", "30"])
        try:
            with open(clip.LOCK, "w") as f:
                f.write(str(other.pid))
            self.assertFalse(clip.toggle_singleton()); self.assertIsNone(other.poll())    # never kills an unrelated process
        finally:
            other.kill()
        with open(clip.LOCK, "w") as f:
            f.write("garbage")
        self.assertFalse(clip.toggle_singleton())
