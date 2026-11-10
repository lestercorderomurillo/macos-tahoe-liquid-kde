"""Exercise the production blur gate with synthetic KWin window metadata."""

import shlex
import shutil
import subprocess

import pytest


@pytest.fixture(scope="module")
def blur_gate(tmp_path_factory):
    from pathlib import Path

    if not shutil.which("c++") or not shutil.which("pkg-config"):
        pytest.skip("C++ compiler and Qt6Core development files required")
    flags = subprocess.run(["pkg-config", "--cflags", "--libs", "Qt6Core"],
                           capture_output=True, text=True, timeout=10)
    if flags.returncode:
        pytest.skip("Qt6Core development files required")
    source = (Path(__file__).resolve().parents[1] /
              "src/offline/kwin-effects/acrylic-glass/src/effect.cpp").read_text()
    method = source.split("bool BlurEffect::shouldBlur(", 1)[1].split("\n}\n", 1)[0]
    work = tmp_path_factory.mktemp("acrylic-filter")
    harness = work / "gate.cpp"
    harness.write_text(r'''
#include <QString>
#include <QStringList>
#include <QVariant>
#include <QtGlobal>
#include <iostream>
constexpr int WindowForceBlurRole = 1, PAINT_WINDOW_TRANSFORMED = 2;
constexpr int OverlayLayer = 3, ActiveLayer = 4;
struct Window {
    QString cls, name;
    QString resourceClass() const { return cls; }
    QString resourceName() const { return name; }
    int layer() const { return 0; }
};
struct EffectWindow {
    Window meta;
    bool isDesktop() const { return false; }
    QVariant data(int) const { return true; }
    const Window *window() const { return &meta; }
};
struct WindowPaintData {
    double xScale() const { return 1; }
    double yScale() const { return 1; }
    double xTranslation() const { return 0; }
    double yTranslation() const { return 0; }
};
struct Effects {
    bool activeFullScreenEffect() const { return false; }
} handler;
auto effects = &handler;
struct BlurEffect {
    bool m_whitelist;
    QStringList m_windowClasses;
    bool shouldBlur(const EffectWindow *, int, const WindowPaintData &) const;
};
''' + "bool BlurEffect::shouldBlur(" + method + "\n}\n" + r'''
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    EffectWindow window{{QString::fromUtf8(argv[1]), QString::fromUtf8(argv[2])}};
    BlurEffect effect{QString::fromUtf8(argv[3]) == "whitelist",
                      QString::fromUtf8(argv[4]).split(',')};
    std::cout << effect.shouldBlur(&window, 0, WindowPaintData{});
}
''')
    binary = work / "gate"
    subprocess.run(["c++", "-std=c++17", "-fPIC", str(harness), "-o", str(binary),
                    *shlex.split(flags.stdout)], check=True, capture_output=True, timeout=60)
    return binary


@pytest.mark.parametrize("cls,name,mode,entries,expected", [
    ("VirtualBoxVM", "VirtualBoxVM", "blacklist", "", "0"),
    ("VirtualBoxVM", "guest", "blacklist", "custom-app", "0"),
    ("guest", "VirtualBoxVM", "blacklist", "custom-app", "0"),
    ("virtualboxvm", "guest", "blacklist", "", "0"),
    ("guest", "VIRTUALBOXVM", "blacklist", "", "0"),
    ("VirtualBoxVM", "guest", "whitelist", "VirtualBoxVM", "0"),
    ("guest", "VirtualBoxVM", "whitelist", "guest", "0"),
    ("VirtualBox", "VirtualBox", "blacklist", "", "1"),
    ("VirtualBox Manager", "VirtualBox", "blacklist", "", "1"),
    ("org.kde.dolphin", "dolphin", "blacklist", "custom-app", "1"),
    ("custom-app", "custom-app", "blacklist", "custom-app", "0"),
    ("custom-app", "custom-app", "whitelist", "custom-app", "1"),
    ("org.kde.dolphin", "dolphin", "whitelist", "custom-app", "0"),
])
def test_vm_surfaces_skip_glass_without_changing_other_filters(
        blur_gate, cls, name, mode, entries, expected):
    result = subprocess.run([str(blur_gate), cls, name, mode, entries],
                            capture_output=True, text=True, check=True, timeout=5)
    assert result.stdout == expected
