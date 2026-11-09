"""Static guards for the Dock Task Manager QML against Plasma API removals."""

import re
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
UI = REPO / "src/offline/plasmoids/org.kde.mac.tahoe.liquid.taskmanager/contents/ui"


def test_taskmanager_does_not_use_removed_window_thumbnail():
    """Plasma 6.8 removed the X11-only PlasmaCore.WindowThumbnail type.
    Referencing it makes ToolTipInstance.qml fail to compile, which takes
    down the whole applet and leaves the dock empty."""
    offenders = [
        path.relative_to(REPO).as_posix()
        for path in sorted(UI.rglob("*.qml"))
        if re.search(r"\bWindowThumbnail\s*\{", path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_dock_themed_icons_follow_both_modes_and_preserve_custom_pixmaps(tmp_path):
    if not shutil.which('c++') or not shutil.which('pkg-config'):
        pytest.skip('C++ and Qt6 development files required')
    flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'Qt6Gui'],
                           capture_output=True, text=True, timeout=10)
    if flags.returncode:
        pytest.skip('Qt6Gui development files required')
    backend = (UI.parent.parent / 'backend.cpp').read_text()
    method = backend.split('QVariant Backend::iconSource(', 1)[1].split('\n}\n', 1)[0]
    task = (UI / 'Task.qml').read_text()
    assert ': backend.iconSource(task.model.decoration)' in task
    assert 'source: task.dockIconSource' in task
    assert 'target: tasksRoot.iconThemeWatcher' in task
    watcher = (UI.parent.parent / 'launcher/iconthemewatcher.h').read_text()
    assert 'QTimer::singleShot(0, this, &IconThemeWatcher::changed)' in watcher
    for component in ('org.kde.mac-tahoe-liquid-kde.launcher/contents/ui/CompactRepresentation.qml',
                      'org.kde.mac-tahoe-liquid-kde.trashcan/contents/ui/main.qml'):
        assert 'NativeLauncher.IconThemeWatcher {' in (UI.parents[2] / component).read_text()
    source = tmp_path / 'icons.cpp'
    source.write_text(r'''
#include <QGuiApplication>
#include <QIcon>
#include <QImage>
#include <QPixmap>
#include <QVariant>
#include <QDir>
#include <QFile>
#include <cassert>
struct Backend { static QVariant iconSource(const QVariant &); };
''' + 'QVariant Backend::iconSource(' + method + '\n}\n' + r'''
int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    const QString root = QString::fromLocal8Bit(argv[1]);
    for (const QString &mode : {QStringLiteral("light"), QStringLiteral("dark")}) {
        QDir().mkpath(root + "/" + mode + "/16x16/apps");
        QFile index(root + "/" + mode + "/index.theme");
        assert(index.open(QIODevice::WriteOnly));
        index.write("[Icon Theme]\nName=test\nDirectories=16x16/apps\n"
                    "[16x16/apps]\nSize=16\nType=Fixed\nContext=Applications\n");
        index.close();
        QImage image(16, 16, QImage::Format_ARGB32);
        image.fill(mode == "light" ? Qt::white : Qt::black);
        assert(image.save(root + "/" + mode + "/16x16/apps/example.png"));
    }
    QIcon::setThemeSearchPaths({root});
    QIcon::setThemeName("light");
    QIcon original = QIcon::fromTheme("example");
    assert(!original.isNull());
    original.pixmap(16, 16); // Materialize the outgoing icon before switching.
    const QVariant source = Backend::iconSource(QVariant::fromValue(original));
    assert(source.metaType() == QMetaType::fromType<QString>());
    for (const QString &mode : {QStringLiteral("dark"), QStringLiteral("light"), QStringLiteral("dark")}) {
        QIcon::setThemeName(mode);
        const auto image = QIcon::fromTheme(source.toString()).pixmap(16, 16).toImage();
        assert(image.pixelColor(8, 8) == (mode == "light" ? QColor(Qt::white) : QColor(Qt::black)));
    }
    QPixmap pixels(16, 16);
    pixels.fill(Qt::red);
    const QIcon custom(pixels);
    const auto preserved = Backend::iconSource(QVariant::fromValue(custom)).value<QIcon>();
    assert(preserved.cacheKey() == custom.cacheKey());
    assert(preserved.pixmap(16, 16).toImage().pixelColor(8, 8) == QColor(Qt::red));
    assert(Backend::iconSource(QStringLiteral("example")).toString() == "example");
    assert(!Backend::iconSource(QVariant()).isValid());
}
''')
    binary = tmp_path / 'icons'
    subprocess.run(['c++', '-std=c++17', '-fPIC', str(source), '-o', str(binary),
                    *shlex.split(flags.stdout)], check=True, capture_output=True, timeout=60)
    subprocess.run([str(binary), str(tmp_path / 'themes')], check=True,
                   env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), timeout=15)


def test_dock_role_icons_are_unnamed_resource_icons(tmp_path):
    """A theme basename must never replace the artwork selected for a Dock role."""
    if not shutil.which('c++') or not shutil.which('pkg-config'):
        pytest.skip('C++ and Qt6 development files required')
    flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'Qt6Gui'], capture_output=True, text=True)
    libexec = subprocess.run(['pkg-config', '--variable=libexecdir', 'Qt6Core'], capture_output=True, text=True)
    rcc = Path(libexec.stdout.strip()) / 'rcc'
    if flags.returncode or not rcc.is_file():
        pytest.skip('Qt6 development tools required')
    import xml.etree.ElementTree as ET
    resources = ET.Element('RCC')
    group = ET.SubElement(resources, 'qresource', prefix='/qt/qml/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager/icons')
    icons = UI.parent / 'icons'
    for path in sorted(icons.glob('*/*.svg')):
        ET.SubElement(group, 'file', alias=path.relative_to(icons).as_posix()).text = str(path)
    qrc = tmp_path / 'icons.qrc'
    ET.ElementTree(resources).write(qrc)
    generated = tmp_path / 'resources.cpp'
    subprocess.run([str(rcc), str(qrc), '-o', str(generated)], check=True, capture_output=True)
    backend = (UI.parent.parent / 'backend.cpp').read_text()
    method = backend.split('QVariant Backend::dockRoleIcon(', 1)[1].split('\n}\n', 1)[0]
    source = tmp_path / 'roles.cpp'
    source.write_text(r'''#include <QGuiApplication>
#include <QIcon>
#include <QImage>
#include <QVariant>
#include <cassert>
struct Backend { static QVariant dockRoleIcon(const QString &, bool); };
''' + 'QVariant Backend::dockRoleIcon(' + method + '\n}\n' + r'''
int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    const QString root = QString::fromLocal8Bit(argv[1]);
    for (const bool dark : {false, true, false}) {
        for (const auto role : {"files", "browser", "mail", "calendar", "notes", "photos", "music", "video", "store", "settings"}) {
            const QVariant result = Backend::dockRoleIcon(QString::fromLatin1(role), dark);
            assert(result.metaType() == QMetaType::fromType<QIcon>());
            const QIcon icon = result.value<QIcon>();
            assert(icon.name().isEmpty()); // Kirigami must not re-resolve a theme name.
            const QImage actual = icon.pixmap(64,64).toImage();
            assert(!actual.isNull());
            if (dark) {
                const QColor plate = actual.pixelColor(9, 20);
                assert(plate.alpha() > 200);
                assert(plate.red() + plate.green() + plate.blue() < 300);
            }
            const QIcon expected(root + (dark ? "/dark/" : "/light/") + QString::fromLatin1(role) + ".svg");
            assert(actual == expected.pixmap(64,64).toImage());
        }
    }
}
''')
    binary = tmp_path / 'roles'
    subprocess.run(['c++', '-std=c++17', '-fPIC', str(source), str(generated), '-o', str(binary),
                    *shlex.split(flags.stdout)], check=True, capture_output=True, timeout=60)
    subprocess.run([str(binary), str(icons)], check=True,
                   env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), timeout=15)
