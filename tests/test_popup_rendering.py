"""Real parsers/renderers for popup surfaces and Xwayland blur requests."""

import os
import shlex
import shutil
import subprocess
import sys

import pytest


def test_light_and_dark_menu_surfaces_keep_matching_frame_opacity(repo):
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    import configparser

    samples = []
    for name in ("mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark"):
        root = repo / "src/offline/kvantum/mac-tahoe-liquid-kde"
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read(root / (name + ".kvconfig"))
        factor = 1 - int(config["%General"]["reduce_menu_opacity"]) / 100
        renderer = svg.QSvgRenderer((root / (name + ".svg")).read_bytes())
        alphas = []
        for element in ("menu-normal", "path4382-5", "path4714-2"):
            image = gui.QImage(64, 64, gui.QImage.Format.Format_ARGB32)
            image.fill(0)
            painter = gui.QPainter(image)
            renderer.render(painter, element, core.QRectF(0, 0, 64, 64))
            painter.end()
            alphas.append(image.pixelColor(48, 48).alpha() * factor)
        assert len(set(alphas)) == 1, "Popup frame and interior must match"
        samples.append(alphas[0])
    # Dark menus are slightly clearer than the unchanged light surfaces.
    assert abs(samples[0] / 255 - .55) < .01
    assert abs(samples[1] / 255 - .48) < .01


@pytest.mark.parametrize("mode", ["", "Dark"])
def test_menu_contours_remain_visible_above_translucent_fill(repo, mode):
    svg = pytest.importorskip("PyQt6.QtSvg")
    gui = pytest.importorskip("PyQt6.QtGui")
    core = pytest.importorskip("PyQt6.QtCore")
    path = repo / "src/offline/kvantum/mac-tahoe-liquid-kde" / ("mac-tahoe-liquid-kde" + mode + ".svg")
    renderer = svg.QSvgRenderer(str(path))
    for element, inset in (("menu-normal-top", 0), ("menu-shadow-top", 16)):
        size = renderer.boundsOnElement(element).size().toSize() * 4
        image = gui.QImage(size, gui.QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = gui.QPainter(image)
        renderer.render(painter, element, core.QRectF(0, 0, size.width(), size.height()))
        painter.end()
        x = size.width() // 2
        outer, inner, body = (image.pixelColor(x, inset + y) for y in (1, 4, 12))
        assert outer.red() < inner.red()
        assert abs(body.alphaF() - (.48 if mode else .55)) < .01
        assert outer.alphaF() > body.alphaF() and inner.alphaF() > body.alphaF()
        assert image.pixelColor(x, inset + 7) == body
        assert body.red() == (0 if mode else 255)


@pytest.mark.parametrize("legacy", [False, True])
def test_gtk4_stylesheets_parse_without_errors(repo, tmp_path, legacy):
    gi = pytest.importorskip("gi")
    if not callable(getattr(gi, "require_version", None)):
        pytest.skip("PyGObject required; the gi namespace alone is insufficient")
    from theme_switch import gtk4_compatible_css
    import theme_switch
    import shutil
    from unittest.mock import patch
    staged = tmp_path / "themes"
    shutil.copytree(repo / "src/offline/gtk", staged)
    version = (4, 14) if legacy else theme_switch._gtk4_version()
    with patch.object(theme_switch, "_gtk4_version", return_value=version):
        for path in staged.glob("*/gtk-4.0/*.css"):
            path.write_text(gtk4_compatible_css(path.read_text()))
    script = """
import gi, pathlib, sys
try: gi.require_version('Gtk','4.0')
except ValueError: sys.exit(77)
from gi.repository import Gtk
errors=[]
for path in pathlib.Path(sys.argv[1]).glob('*/gtk-4.0/*.css'):
    provider=Gtk.CssProvider()
    provider.connect('parsing-error',lambda p,s,e: errors.append(str(e)) if e.domain=='gtk-css-parser-error-quark' else None)
    provider.load_from_path(str(path))
assert not errors, errors
"""
    env = os.environ | {
        "GTK_THEME": "Adwaita",
        "XDG_CONFIG_HOME": str(tmp_path),
        "HOME": str(tmp_path),
    }
    result = subprocess.run(
        [sys.executable, "-c", script, str(staged)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 77:
        pytest.skip("GTK4 introspection required")
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_qt_menu_text_contrasts_with_each_theme(repo, tmp_path):
    pytest.importorskip("PyQt6.QtWidgets")
    script = r'''
import sys
from collections import Counter
from PyQt6.QtWidgets import QApplication, QMenu

app = QApplication([])
if app.setStyle("kvantum") is None:
    sys.exit(77)
menu = QMenu()
action = menu.addAction("Create New")
menu.addAction("Paste Clipboard Contents...")
menu.addAction("Undo").setEnabled(False)
menu.ensurePolished()
menu.resize(menu.sizeHint())
menu.show()
app.processEvents()

def luminance(rgb):
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
              for v in (channel / 255 for channel in rgb)]
    return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))

for selected in (False, True):
    if selected:
        menu.setActiveAction(action)
        app.processEvents()
    image = menu.grab().toImage()
    rect = menu.actionGeometry(action).adjusted(12, 2, -12, -2)
    pixels = Counter(image.pixelColor(x, y).getRgb()[:3]
                     for y in range(rect.top(), rect.bottom())
                     for x in range(rect.left(), rect.right()))
    background = pixels.most_common(1)[0][0]
    bg = luminance(background)
    readable_pixels = 0
    for rgb, count in pixels.items():
        fg = luminance(rgb)
        contrast = (max(bg, fg) + .05) / (min(bg, fg) + .05)
        if contrast >= 4.5:
            readable_pixels += count
    assert readable_pixels >= 20, (selected, background, readable_pixels)
'''
    source = repo / "src/offline/kvantum/mac-tahoe-liquid-kde"
    for name in ("mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark"):
        home = tmp_path / name
        config = home / "config"
        theme = config / "Kvantum" / name
        theme.mkdir(parents=True)
        for extension in ("svg", "kvconfig"):
            shutil.copyfile(source / f"{name}.{extension}", theme / f"{name}.{extension}")
        (config / "Kvantum/kvantum.kvconfig").write_text(f"[General]\ntheme={name}\n")
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG")}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(config),
                   XDG_CONFIG_DIRS=str(home / "system"), QT_QPA_PLATFORM="offscreen")
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                capture_output=True, text=True, timeout=20)
        if result.returncode == 77:
            pytest.skip("Kvantum Qt 6 style plugin required")
        assert result.returncode == 0, name + "\n" + result.stdout + result.stderr


def test_xwayland_property_is_read_and_invalid_data_never_means_full_blur(
    repo, tmp_path
):
    for tool in ("Xvfb", "c++", "pkg-config"):
        if not shutil.which(tool):
            pytest.skip(f"{tool} required")
    flags = subprocess.run(
        ["pkg-config", "--cflags", "--libs", "Qt6Gui", "xcb"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if flags.returncode:
        pytest.skip("Qt6Gui and XCB development files required")
    source = (
        repo / "src/offline/kwin-effects/acrylic-glass/src/effect.cpp"
    ).read_text()
    block = source.split("    // Xwayland still advertises blur", 1)[1].split(
        "    // Plasma's translucent menus", 1
    )[0]
    block = block.removesuffix("#if defined(GLASS_X11)\n") + "#endif\n"
    block = block[block.index("#if KWIN_BUILD_X11") :]
    code = (
        r"""
#include <QRegion>
#include <QRect>
#include <xcb/xcb.h>
#include <memory>
#include <optional>
#include <climits>
#include <cstdlib>
#include <cassert>
#include <vector>
#define KWIN_BUILD_X11 1
using Region=QRegion;
using Rect=QRect;
namespace Xcb { struct Result { QRect rect; QRect toRect() const { return rect; } }; Result fromXNative(QRect r) { return {r}; } }
struct Window { xcb_window_t id; long windowId() const { return id; } };
struct Effects { xcb_connection_t *connection; xcb_connection_t *xcbConnection() const { return connection; } };
std::optional<Region> read(Effects *effects, Window *w, xcb_atom_t net_wm_blur_region, bool *missing = nullptr) {
    std::optional<Region> content;
"""
        + block
        + r"""
    if (missing) *missing = legacyBlurPropertyMissing;
    return content;
}
int main() {
    auto *connection=xcb_connect(nullptr,nullptr);assert(!xcb_connection_has_error(connection));
    auto *screen=xcb_setup_roots_iterator(xcb_get_setup(connection)).data;
    auto id=xcb_generate_id(connection);
    xcb_create_window(connection,XCB_COPY_FROM_PARENT,id,screen->root,0,0,100,100,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,screen->root_visual,0,nullptr);
    const char name[]="_KDE_NET_WM_BLUR_BEHIND_REGION";
    auto *reply=xcb_intern_atom_reply(connection,xcb_intern_atom(connection,false,sizeof(name)-1,name),nullptr);
    auto atom=reply->atom;free(reply);
    Effects effects{connection};Window w{id};
    bool missing = false;
    assert(!read(&effects,&w,atom,&missing) && missing);
    auto set=[&](std::vector<uint32_t> data,xcb_atom_t type=XCB_ATOM_CARDINAL) {
        xcb_change_property(connection,XCB_PROP_MODE_REPLACE,id,atom,type,32,data.size(),data.data());xcb_flush(connection);
    };
    set({});assert(read(&effects,&w,atom).has_value() && read(&effects,&w,atom)->isEmpty());
    set({3,4,20,30});assert(*read(&effects,&w,atom)==QRegion(QRect(3,4,20,30)));
    set({3,4,20});assert(!read(&effects,&w,atom,&missing) && !missing);
    set({3,4,20,30},XCB_ATOM_STRING);assert(!read(&effects,&w,atom,&missing) && !missing);
    set({3,4,UINT32_MAX,30});assert(!read(&effects,&w,atom));
    set({uint32_t(INT_MAX),4,20,30});assert(!read(&effects,&w,atom));
    set(std::vector<uint32_t>(16388,1));assert(!read(&effects,&w,atom));
    w.id=0;assert(!read(&effects,&w,atom));
    xcb_disconnect(connection);
}
"""
    )
    cpp = tmp_path / "property.cpp"
    cpp.write_text(code)
    binary = tmp_path / "property"
    result = subprocess.run(
        [
            "c++",
            "-std=c++20",
            "-fPIC",
            str(cpp),
            "-o",
            str(binary),
            *shlex.split(flags.stdout),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    read_fd, write_fd = os.pipe()
    server = subprocess.Popen(
        [
            "Xvfb",
            "-displayfd",
            str(write_fd),
            "-screen",
            "0",
            "640x480x24",
            "-nolisten",
            "tcp",
        ],
        pass_fds=(write_fd,),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.close(write_fd)
    try:
        import select

        assert select.select([read_fd], [], [], 10)[0], "Xvfb did not start"
        display = os.read(read_fd, 32).decode().strip()
        subprocess.run(
            [str(binary)],
            env=os.environ | {"DISPLAY": ":" + display},
            check=True,
            timeout=10,
        )
    finally:
        os.close(read_fd)
        server.terminate()
        server.wait(timeout=10)
