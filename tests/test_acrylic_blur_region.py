"""Run the actual blur-region method with real Qt regions and small window doubles."""
import shlex
import shutil
import subprocess
import os

import pytest


def test_client_regions_only_move_for_server_decorations(repo, tmp_path):
    if not shutil.which('c++') or not shutil.which('pkg-config'):
        pytest.skip('C++ and Qt6 development files required')
    flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'Qt6Core', 'Qt6Gui'],
                           capture_output=True, text=True)
    if flags.returncode:
        pytest.skip('Qt6 development files required')
    text = (repo / 'src/offline/kwin-effects/acrylic-glass/src/effect.cpp').read_text()
    method = text[text.index('Region BlurEffect::blurRegion('):text.index('// Per-frame entry points')]
    frame_logic = text[text.index('    if (m_blurDecorations && w->decorationHasAlpha()'):
                       text.index('    // Commit (or evict).')]
    source = tmp_path / 'regions.cpp'
    source.write_text('''
#include <QRegion>
#include <QRectF>
#include <QImage>
#include <QPainter>
#include "roundedblurshape.h"
#include <optional>
#include <unordered_map>
#include <cassert>
using Region = QRegion;
using Rect = QRect;
struct EffectWindow {
    bool decorated = false;
    enum Type { Normal, Popup, AppletPopup, Menu, Dropdown, Context, Tooltip, Dock } type = Normal;
    QRectF contentsRect() const { return QRectF(10, 20, 100, 80); }
    bool decoration() const { return decorated; }
    bool decorationHasAlpha() const { return false; }
    QRectF frameGeometry() const { return QRectF(0, 0, 120, 120); }
    int x() const { return 0; }
    int y() const { return 0; }
    bool isDock() const { return type == Dock; }
    bool isTooltip() const { return type == Tooltip; }
    bool isMenu() const { return type == Menu; }
    bool isDropdownMenu() const { return type == Dropdown; }
    bool isPopupMenu() const { return type == Context; }
    bool isPopupWindow() const { return type == Popup; }
    bool isAppletPopup() const { return type == AppletPopup; }
};
struct BlurEffectData { std::optional<Region> content, frame; };
struct BlurEffect {
    std::unordered_map<EffectWindow*, BlurEffectData> m_windows;
    Region blurRegion(EffectWindow*) const;
    bool m_blurDecorations = true;
    bool decorationSupportsBlurBehind(EffectWindow*) const { return false; }
    Region decorationBlurRegion(EffectWindow*) const { return {}; }
    std::optional<Region> implicitFrame(EffectWindow* w) const {
        std::optional<Region> frame;
''' + frame_logic + '''
        return frame;
    }
};
''' + method + '''
QRegion rasterizedRoundedRect(const QRect &bounds, int radius, int alphaThreshold = 128) {
    QImage image(bounds.size(), QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);
    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setPen(Qt::NoPen);
    painter.setBrush(Qt::white);
    painter.drawRoundedRect(QRectF(image.rect()), radius, radius);
    painter.end();
    QRegion region;
    for (int y = 0; y < image.height(); ++y) {
        int start = -1;
        for (int x = 0; x <= image.width(); ++x) {
            const bool opaque = x < image.width() && qAlpha(image.pixel(x, y)) >= alphaThreshold;
            if (opaque && start < 0) start = x;
            if (!opaque && start >= 0) {
                region += QRect(start, y, x - start, 1);
                start = -1;
            }
        }
    }
    return region.translated(bounds.topLeft());
}
int main() {
    BlurEffect effect;
    EffectWindow window;
    auto& state = effect.m_windows[&window];
    state.content = Region(QRect(10, 20, 30, 20));
    assert(effect.blurRegion(&window) == Region(QRect(10, 20, 30, 20)));
    window.decorated = true;
    assert(effect.blurRegion(&window) == Region(QRect(20, 40, 30, 20)));
    state.content = Region();
    assert(effect.blurRegion(&window) == Region(QRect(10, 20, 100, 80)));
    state.content.reset();
    state.frame = Region(QRect(0, 0, 120, 20));
    assert(effect.blurRegion(&window) == *state.frame);
    state.content = Region(QRect(0, 0, 200, 200));
    assert(effect.blurRegion(&window) == (*state.frame | Region(QRect(10, 20, 100, 80))));
    window.decorated = false;
    const Region capsule = Region(QRect(10, 20, 80, 80), QRegion::Ellipse)
        | Region(QRect(30, 20, 80, 80), QRegion::Ellipse) | Region(QRect(50, 20, 20, 80));
    state.content = capsule;
    for (auto type : {EffectWindow::Popup, EffectWindow::AppletPopup, EffectWindow::Menu,
                      EffectWindow::Dropdown, EffectWindow::Context, EffectWindow::Tooltip,
                      EffectWindow::Dock}) {
        window.type = type;
        // A late Plasma shell role must not retain the initial normal frame.
        state.frame = Region(QRect(0, 0, 120, 120));
        assert(effect.blurRegion(&window) == capsule);
        state.frame = effect.implicitFrame(&window);
        assert(!state.frame.has_value());
        assert(effect.blurRegion(&window) == capsule);
    }
    window.type = EffectWindow::Normal;
    assert(effect.implicitFrame(&window) == Region(QRect(0, 0, 120, 120)));

    // Recover the client curve for both the detached capsule and popup panel.
    // Keep custom cutouts and asymmetric shapes on the existing render path.
    for (int radius : {6, 9, 14, 16, 22, 23, 36}) {
        const QRect bounds(0, 0, 640, radius == 36 ? 72 : 600);
        const QRegion rounded = rasterizedRoundedRect(bounds, radius);
        const auto inferred = roundedBlurRadius(rounded, bounds);
        assert(inferred && std::abs(*inferred - radius) <= 1);
        const QRegion alphaMask = rasterizedRoundedRect(bounds, radius, 1);
        const auto alphaRadius = roundedBlurRadius(alphaMask, bounds);
        assert(alphaRadius && std::abs(*alphaRadius - radius) <= 3);
        const QRegion hole = rounded - QRect(200, 20, 10, 10);
        assert(!roundedBlurRadius(hole, bounds));
        const QRegion asymmetric = rounded | QRect(0, bounds.height() - radius, radius, radius);
        assert(!roundedBlurRadius(asymmetric, bounds));
        assert(!roundedBlurRadius(rounded, bounds.adjusted(0, 0, 1, 0)));
        const auto client = clientBlurShape(rounded.translated(12, 8));
        assert(client && client->bounds == bounds.translated(12, 8));
        assert(std::abs(client->radius - radius) <= 1);
        assert(!clientBlurShape(hole));
    }
    // Kvantum's native integer ellipse mask has asymmetric top/bottom rows.
    // The real 249x274 menu with radius 9 must not fall back to hard steps.
    for (int radius : {6, 9, 16, 22, 52}) {
        const QRect bounds(4, 4, 249, 274);
        QRegion native(bounds.adjusted(radius, 0, -radius, 0));
        native += QRegion(bounds.adjusted(0, radius, 0, -radius));
        for (int x : {bounds.x(), bounds.x() + bounds.width() - 2 * radius}) {
            for (int y : {bounds.y(), bounds.y() + bounds.height() - 2 * radius}) {
                native += QRegion(QRect(x, y, 2 * radius, 2 * radius), QRegion::Ellipse);
            }
        }
        const auto shape = clientBlurShape(native);
        assert(shape && shape->bounds == bounds && shape->radius == radius);
        assert(shape->integerEllipse);
        assert(shape->surfaceRect() == QRectF(bounds).adjusted(1, 1, -1, -1));
        assert(shape->cornerRadius() == radius - 1);
        QPainterPath inner;
        inner.addRoundedRect(shape->surfaceRect(), shape->cornerRadius(), shape->cornerRadius());
        assert((QRegion(inner.toFillPolygon().toPolygon()) - native).isEmpty());
        assert(!clientBlurShape(native - QRect(100, 20, 10, 10)));
        assert(!clientBlurShape(native | QRect(4, 4, radius, radius)));
    }
    assert(!roundedBlurRadius(QRegion(), QRect(0, 0, 640, 72)));
    assert(!roundedBlurRadius(QRegion(QRect(0, 0, 640, 72)), QRect(0, 0, 640, 72)));
    const auto square = clientBlurShape(QRegion(QRect(8, 12, 300, 32)));
    assert(square && square->radius == 0 && square->bounds == QRect(8, 12, 300, 32));
    assert(!square->integerEllipse && square->surfaceRect() == square->bounds);
}
''')
    binary = tmp_path / 'regions'
    subprocess.run(['c++', '-std=c++20', '-fPIC', str(source), '-o', str(binary),
                    '-I', str(repo / 'src/offline/kwin-effects/acrylic-glass/src'),
                    *shlex.split(flags.stdout)], check=True, capture_output=True, timeout=60)
    subprocess.run([str(binary)], check=True, capture_output=True, timeout=10)


def test_x11_plasma_popup_gets_alpha_visual_fallback_blur(repo):
    source = (repo / "src/offline/kwin-effects/acrylic-glass/src/effect.cpp").read_text()
    helper = source.split("static bool hasAlphaVisual(", 1)[1].split("#endif", 1)[0]
    fallback = source.split(
        "// Plasma's translucent menus do not publish the legacy blur-region",
        1,
    )[1].split("#endif", 1)[0]
    assert 'resourceClass() == QStringLiteral("plasmashell")' in fallback
    assert "w->isMenu()" in fallback
    assert "w->isDropdownMenu()" in fallback
    assert "w->isPopupMenu()" in fallback
    assert "w->isAppletPopup()" in fallback
    assert "pictFormats.data->direct.alpha_mask != 0" in helper
    assert "cache.insert(visual, alphaVisual)" in helper
    assert "hasAlphaVisual(effects->xcbConnection(), attributes->visual)" in fallback
    assert "legacyBlurPropertyMissing && !content.has_value()" in fallback
    assert "content = Region(w->contentsRect().toRect())" in fallback


def test_real_svg_capsule_radius_at_fractional_scales(repo, tmp_path):
    if not shutil.which('cmake') or not shutil.which('c++'):
        pytest.skip('CMake and C++ required')
    (tmp_path / 'CMakeLists.txt').write_text('''
cmake_minimum_required(VERSION 3.20)
project(CapsuleMaskTest LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
find_package(Qt6 QUIET COMPONENTS Gui)
find_package(KF6Svg QUIET CONFIG)
if(NOT TARGET KF6::Svg OR NOT TARGET Qt6::Gui)
    message(STATUS "CAPSULE_MASK_SDK_MISSING")
    return()
endif()
add_executable(capsule capsule.cpp)
target_link_libraries(capsule PRIVATE KF6::Svg Qt6::Gui)
target_include_directories(capsule PRIVATE "${GLASS_SOURCE}")
''')
    (tmp_path / 'capsule.cpp').write_text('''
#include <KSvg/FrameSvg>
#include <QGuiApplication>
#include "roundedblurshape.h"
#include <cassert>
int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    for (int index = 1; index < argc; ++index) {
        for (qreal scale : {1., 1.25, 1.5, 1.75, 2.}) {
            KSvg::FrameSvg frame;
            frame.setImagePath(QString::fromLocal8Bit(argv[index]));
            frame.setDevicePixelRatio(scale);
            frame.resizeFrame(QSizeF(634, 104));
            const QRegion mask = frame.mask();
            const QRect bounds(0, 0, 634, 104);
            const auto shape = clientBlurShape(mask);
            const QString path = QString::fromLocal8Bit(argv[index]);
            const int expected = path.contains("launcher-search") ? 52
                : path.contains("panel-background") ? 16 : 22;
            assert(shape && shape->bounds == bounds);
            assert(std::abs(shape->radius - expected) <= (expected == 52 ? 0 : 2));
            assert(!roundedBlurRadius(mask - QRect(200, 20, 10, 10), bounds));
            assert(!roundedBlurRadius(mask | QRect(0, 80, 24, 24), bounds));
        }
    }
}
''')
    build = tmp_path / 'build'
    config = subprocess.run(['cmake', '-S', str(tmp_path), '-B', str(build),
                             f'-DGLASS_SOURCE={repo}/src/offline/kwin-effects/acrylic-glass/src'],
                            capture_output=True, text=True, timeout=30)
    if 'CAPSULE_MASK_SDK_MISSING' in config.stdout:
        pytest.skip('KSvg development SDK required')
    assert config.returncode == 0, config.stdout + config.stderr
    subprocess.run(['cmake', '--build', str(build), '-j', '2'],
                   check=True, capture_output=True, timeout=60)
    themes = repo / 'src/offline/plasma-theme'
    subprocess.run([str(build / 'capsule'), *[
        str(themes / f'MacTahoeLiquidKde-{mode}/{surface}.svgz')
        for mode in ('Light', 'Dark')
        for surface in ('dialogs/launcher-search', 'dialogs/background',
                        'widgets/tooltip', 'widgets/panel-background')]],
        env=os.environ | {'QT_QPA_PLATFORM': 'offscreen'},
        check=True, capture_output=True, timeout=10)
