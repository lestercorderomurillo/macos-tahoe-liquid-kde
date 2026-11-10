"""Regression coverage for the Acrylic Glass + Wobbly Windows handoff."""

import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "src/offline/kwin-effects/acrylic-glass/src"


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def wobbly_native(tmp_path_factory):
    if not shutil.which("c++") or not shutil.which("pkg-config"):
        pytest.skip("C++ compiler and Qt6Core development files required")
    flags = subprocess.run(
        ["pkg-config", "--cflags", "--libs", "Qt6Core"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if flags.returncode:
        pytest.skip("Qt6Core development files required")

    work = tmp_path_factory.mktemp("acrylic-wobbly")
    probe = work / "probe.cpp"
    binary = work / "probe"
    probe.write_text(
        r'''
#include "wobbly_shape.h"

#include <chrono>
#include <cassert>
#include <cmath>

using namespace std::chrono_literals;

int main()
{
    KWin::WobblyShapeParameters parameters;
    QRectF geometry(100, 100, 400, 300);
    const QPointF cursor(101, 101);

    KWin::WobblyShape shape(parameters, geometry, cursor, false);
    const QRectF moved = geometry.translated(40, 0);
    shape.advance(20ms, moved);

    const QPointF flat(moved.x() + moved.width() * 0.5,
                       moved.y() + moved.height() * 0.5);
    const QPointF deformed = shape.map(0.5, 0.5, moved);
    assert(QPointF::dotProduct(deformed - flat, deformed - flat) > 0.0001);

    KWin::WobblyShape resize(parameters, geometry, geometry.bottomRight(), true);
    const QRectF wider(100, 100, 460, 300);
    resize.noteGeometryStep(wider);
    resize.advance(20ms, wider);
    assert(std::abs(resize.map(0, 0.5, wider).x() - wider.left()) < 0.000001);
    assert(std::abs(resize.map(0.5, 0, wider).y() - wider.top()) < 0.000001);
    assert(std::abs(resize.map(0.5, 1, wider).y() - wider.bottom()) < 0.000001);
    resize.noteGeometryFinished(wider);
    bool active = true;
    for (int frame = 0; frame < 1000 && active; ++frame) {
        active = resize.advance(16ms, wider);
    }
    assert(!active);
    assert(resize.map(1, 1, wider) == wider.bottomRight());

    shape.beginMovedResized(cursor + QPointF(40, 0), moved, false);
    const QPointF reused = shape.map(0.5, 0.5, moved);
    assert(QPointF::dotProduct(reused - deformed, reused - deformed) < 0.000001);

    const auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch());
    KWin::WobblyShapeTracker tracker(parameters, moved, cursor, false);
    tracker.shape().noteGeometryFinished(moved);

    assert(tracker.advance(now + 10ms, moved));
    assert(tracker.retirePending());
    assert(!tracker.advance(now + 20ms, moved));

    tracker.beginMovedResized(cursor, moved, false);
    assert(!tracker.retirePending());
    assert(tracker.advance(now + 30ms, moved));
}
''',
        encoding="utf-8",
    )
    subprocess.run(
        [
            "c++",
            "-std=c++20",
            "-fPIC",
            f"-I{ROOT}",
            str(probe),
            str(ROOT / "wobbly_shape.cpp"),
            "-o",
            str(binary),
            *shlex.split(flags.stdout),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    subprocess.run([str(binary)], check=True, capture_output=True, timeout=10)


def test_wobbly_native_physics_reuses_state_and_retires_after_final_frame(wobbly_native):
    """The native probe above must complete."""


def test_wobbly_connections_and_parameters_follow_the_effect():
    effect = _read("effect.cpp")
    for signal in (
        "windowStartUserMovedResized",
        "windowStepUserMovedResized",
        "windowFinishUserMovedResized",
    ):
        assert signal in effect
    for property_name in (
        "stiffness",
        "drag",
        "moveFactor",
        "minVelocity",
        "maxVelocity",
        "stopVelocity",
        "minAcceleration",
        "maxAcceleration",
        "stopAcceleration",
        "xTessellation",
        "yTessellation",
    ):
        assert f'property("{property_name}")' in effect
    assert 'property(resizing ? "resizeWobble" : "moveWobble")' in effect


def test_wobbly_drag_restart_reuses_only_a_live_spring_model():
    effect = _read("effect.cpp")
    start = effect.split("void BlurEffect::slotWindowStartUserMovedResized", 1)[1]
    start = start.split("\n}\n", 1)[0]
    assert "it->second.retirePending()" in start
    assert "it->second.beginMovedResized(cursorPosition, geometry, resizing)" in start
    assert "wobblyShapes.erase(it)" in start
    assert start.index("retirePending()") < start.index("wobblyShapes.erase(it)")


def test_wobbly_glass_uses_frame_local_mask_and_destination_background():
    glass = _read("shaders/glass.glsl")
    core = _read("shaders/glass_core.glsl")
    noise = _read("shaders/noise.frag")
    noise_core = _read("shaders/noise_core.frag")
    for shader in (glass, core, noise, noise_core):
        assert "vec2 localPos = uv - box.xy;" in shader
        assert "lgRoundedRectDistance(localPos" in shader
    for shader in (glass, core):
        assert "vec2 backgroundUV = vec2(vertex.x / safeBackgroundSize.x" in shader


def test_wobbly_mesh_is_clipped_and_captures_the_complete_surface():
    effect = _read("effect.cpp")
    assert "appendClippedTriangle(" in effect
    assert "clipPolygonToRect(" in effect
    assert "clipRect.x() - deviceBackgroundRect.x()" in effect
    assert "? Region(Rect(backgroundRect))" in effect
    assert "viewport.mapFromDeviceCoordinatesContained(deviceRegion) & backgroundRect" in effect


def test_wobbly_source_and_abi_gates_are_built():
    cmake = _read("CMakeLists.txt")
    assert "wobbly_shape.cpp" in cmake
    header = _read("wobbly_shape.h")
    assert "#if ACRYLIC_GLASS_KWIN_6_7" in header
    assert "AnimationClock m_clock;" in header
    assert "std::chrono::milliseconds m_clock;" in header
    effect = _read("effect.cpp")
    assert "it->second.advance(view, w->frameGeometry())" in effect
    assert "it->second.advance(presentTime, w->frameGeometry())" in effect


def test_transformed_windows_remain_blurred_only_while_wobbly_owns_them():
    effect = _read("effect.cpp")
    should_blur = effect.split("bool BlurEffect::shouldBlur(", 1)[1]
    should_blur = should_blur.split("\n}\n", 1)[0]
    assert "const bool wobblyTransformed" in should_blur
    assert "(mask & PAINT_WINDOW_TRANSFORMED) && !wobblyTransformed" in should_blur


@pytest.mark.parametrize("backend", ["wayland", "x11"])
def test_native_mesh_preserves_holes_and_output_coordinates(tmp_path, backend):
    """Execute the production mesh loop with an offset output and split region."""
    flags = subprocess.run(["pkg-config", "--cflags", "--libs", "Qt6Gui"],
                           capture_output=True, text=True)
    if flags.returncode or not shutil.which("c++"):
        pytest.skip("C++ and Qt6Gui development files required")
    effect = _read("effect.cpp")
    helpers = effect.split("namespace {", 1)[1].split("} // namespace", 1)[0]
    mesh = effect.split("    std::vector<GLVertex2D> wobblyVertices;", 1)[1].split(
        "    // 3. Framebuffer", 1)[0].replace("return;", 'assert(false && "unexpected empty mesh");')
    cpp = tmp_path / "mesh.cpp"
    cpp.write_text(r"""
#include "wobbly_shape.h"
#include <QVector2D>
#include <QRegion>
#include <algorithm>
#include <array>
#include <vector>
#include <map>
#include <cassert>
#include <cmath>
using namespace KWin;
using Rect = QRect;
struct GLVertex2D { QVector2D position; QVector2D texcoord; };
struct Region {
    std::vector<QRect> values;
    const auto& rects() const { return values; }
};
struct Viewport {
    qreal scale() const { return 1.25; }
    QPointF mapToRenderTarget(QPointF p) const { return p * scale() - QPointF(1000, 0); }
};
struct Window { qreal x() const { return 900; } qreal y() const { return 80; } };
struct Data {
    qreal xScale() const { return 1; } qreal yScale() const { return 1; }
    qreal xTranslation() const { return 0; } qreal yTranslation() const { return 0; }
};
""" + helpers + r"""
void run() {
    const QRectF frameRect(900, 80, 400, 300);
    Window window; auto* w = &window; Viewport viewport; Data data;
    std::map<Window*, WobblyShapeTracker> shapes;
    shapes.try_emplace(w, WobblyShapeParameters{}, frameRect, frameRect.topLeft(), false);
    auto wobblyIt = shapes.begin();
    const bool wobblySurface = true, finiteClip = true;
    const QRect deviceBackgroundRect(123, 98, 504, 379);
#ifdef GLASS_X11
    const QRect scaledBackgroundRect(0, 0, 504, 379);
#else
    const QRect scaledBackgroundRect(1123, 98, 504, 379);
#endif
    // The right half intentionally has no blur, and output coordinates
    // differ from global scaled coordinates by 1000 pixels.
    Region blurShape{{QRect(900, 80, 200, 300)}};
    Region deviceRegion{{deviceBackgroundRect}};
    std::vector<GLVertex2D> wobblyVertices;
""" + mesh + r"""
    assert(!wobblyVertices.empty());
    double area = 0;
    for (size_t i = 0; i < wobblyVertices.size(); i += 3) {
        area += std::abs(triangleArea(wobblyVertices[i], wobblyVertices[i+1], wobblyVertices[i+2])) / 2;
    }
    assert(std::abs(area - 200 * 300 * 1.25 * 1.25) < 0.1);
    for (const auto& vertex : wobblyVertices) {
        assert(vertex.position.x() >= 1.99 && vertex.position.x() <= 252.01);
        assert(vertex.position.y() >= 1.99 && vertex.position.y() <= 377.01);
    }
}
int main() { run(); }
""")
    binary = tmp_path / "mesh"
    result = subprocess.run(["c++", "-std=c++20", "-fPIC", f"-I{ROOT}",
                             *(["-DGLASS_X11"] if backend == "x11" else []),
                             str(cpp), str(ROOT / "wobbly_shape.cpp"), "-o", str(binary),
                             *shlex.split(flags.stdout)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    subprocess.run([str(binary)], check=True, capture_output=True)


def test_native_wobbly_property_compatibility(tmp_path):
    """Run the actual property reader against modern and legacy Qt properties."""
    flags = subprocess.run(["pkg-config", "--cflags", "--libs", "Qt6Core"],
                           capture_output=True, text=True)
    if flags.returncode or not shutil.which("c++"):
        pytest.skip("C++ and Qt6Core development files required")
    source = _read("effect.cpp")
    reader = source[source.index("std::optional<WobblyShapeParameters> BlurEffect::readWobblyParameters"):]
    reader = reader.split("\nvoid BlurEffect::slotWindowStartUserMovedResized", 1)[0]
    cpp = tmp_path / "properties.cpp"
    cpp.write_text(r'''
#include "wobbly_shape.h"
#include <QObject>
#include <QVariant>
#include <optional>
#include <cassert>
using namespace KWin;
using Effect = QObject;
struct Handler {
    QObject object;
    bool loaded = true;
    Effect* findEffect(const QString&) { return loaded ? &object : nullptr; }
};
struct BlurEffect {
    Handler* effects;
    std::optional<WobblyShapeParameters> readWobblyParameters(bool resizing) const;
};
''' + reader + r'''
int main() {
    Handler handler;
    BlurEffect effect{&handler};
    auto& object = handler.object;
    object.setProperty("moveWobble", true);
    object.setProperty("resizeWobble", true);
    assert(!effect.readWobblyParameters(false));
    object.setProperty("xTesselation", 12.0);
    object.setProperty("yTesselation", 17.0);
    auto legacy = effect.readWobblyParameters(false);
    assert(legacy && legacy->xTessellation == 12 && legacy->yTessellation == 17);
    object.setProperty("xTessellation", 20);
    object.setProperty("yTessellation", 24);
    auto modern = effect.readWobblyParameters(false);
    assert(modern && modern->xTessellation == 20 && modern->yTessellation == 24);
    object.setProperty("xTessellation", 0);
    assert(!effect.readWobblyParameters(false));
    object.setProperty("xTessellation", QVariant());
    object.setProperty("yTessellation", QVariant());
    object.setProperty("moveWobble", false);
    assert(!effect.readWobblyParameters(false));
    assert(effect.readWobblyParameters(true));
    handler.loaded = false;
    assert(!effect.readWobblyParameters(true));
}
''')
    binary = tmp_path / "properties"
    result = subprocess.run(["c++", "-std=c++20", "-fPIC", f"-I{ROOT}", str(cpp),
                             "-o", str(binary), *shlex.split(flags.stdout)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    subprocess.run([str(binary)], check=True, capture_output=True)
