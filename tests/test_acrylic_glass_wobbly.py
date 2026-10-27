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


def test_wobbly_tracker_keeps_the_final_frame_before_retiring():
    wobbly = _read("wobbly_shape.cpp")
    advance = wobbly.split("WobblyShapeTracker::advance(", 1)[1]
    assert "if (m_retirePending)" in advance
    assert "m_retirePending = true" in advance
    assert "return true;" in advance
    header = _read("wobbly_shape.h")
    assert "bool retirePending() const" in header


def test_wobbly_physics_matches_the_upstream_integration_model():
    wobbly = _read("wobbly_shape.cpp")
    assert "std::chrono::milliseconds(10)" in wobbly
    assert "Pair WobblyShape::computeBezierPoint(" in wobbly
    assert "computeBezierPoint(m_position, u, v)" in wobbly
    assert "const qreal px[4]" in wobbly
    assert "const qreal py[4]" in wobbly
    assert "3 * (1 - u) * (1 - u) * u" in wobbly
    assert "3 * (1 - v) * (1 - v) * v" in wobbly
    assert "m_parameters.stiffness" in wobbly
    assert "m_parameters.moveFactor" in wobbly
    assert "m_wobbling = !(accelerationSum < m_parameters.stopAcceleration" in wobbly
    header = _read("wobbly_shape.h")
    assert "std::array<Pair, 16> m_position" in header
    assert "std::array<Pair, 16> m_velocity" in header
    assert "std::array<Pair, 16> m_acceleration" in header


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
    assert "clipRect.x() - scaledBackgroundRect.x()" in effect
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
