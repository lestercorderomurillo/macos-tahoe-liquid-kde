// SPDX-License-Identifier: GPL-2.0-or-later
#include "menushortcutsender.h"
#include "qwayland-fake-input.h"
#include <QWaylandClientExtension>
#include <QGuiApplication>
#include <KWindowSystem>
#include <qguiapplication_platform.h>
#if QT_CONFIG(xcb)
#include <X11/Xlib.h>
#include <X11/extensions/XTest.h>
#include <fixx11h.h>
#endif

namespace {
class ShellInput : public QWaylandClientExtensionTemplate<ShellInput>, public QtWayland::org_kde_kwin_fake_input
{
public:
    ShellInput() : QWaylandClientExtensionTemplate<ShellInput>(6)
    {
        connect(this, &QWaylandClientExtension::activeChanged, this, [this] {
            if (isActive()) authenticate(QStringLiteral("plasmashell"), QStringLiteral("Application menu shortcut"));
        });
        initialize();
    }
    ~ShellInput() override { if (isActive()) destroy(); }
};
// Only the explicit, single-chord Edit commands offered by the fallback menu.
// Keysyms allow the compositor to resolve the current keyboard layout.
uint keySym(Qt::Key key)
{
    if (key >= Qt::Key_A && key <= Qt::Key_Z) return 'a' + key - Qt::Key_A;
    return 0;
}
}
class MenuShortcutSender::Private {
public:
    std::unique_ptr<ShellInput> wayland;
};
MenuShortcutSender::MenuShortcutSender(QObject *parent) : QObject(parent), d(std::make_unique<Private>())
{
    if (KWindowSystem::isPlatformWayland()) {
        d->wayland = std::make_unique<ShellInput>();
        connect(d->wayland.get(), &QWaylandClientExtension::activeChanged, this, &MenuShortcutSender::availabilityChanged);
    }
}
MenuShortcutSender::~MenuShortcutSender() = default;
bool MenuShortcutSender::available() const
{
    if (d->wayland) return d->wayland->isActive() && d->wayland->QWaylandClientExtension::version() >= 6;
#if QT_CONFIG(xcb)
    if (auto *x11 = qGuiApp->nativeInterface<QNativeInterface::QX11Application>()) {
        int event, error, major, minor;
        return XTestQueryExtension(x11->display(), &event, &error, &major, &minor);
    }
#endif
    return false;
}
bool MenuShortcutSender::send(const QKeySequence &sequence)
{
    if (!available() || sequence.count() != 1) return false;
    const auto combination = sequence[0];
    const uint symbol = keySym(combination.key());
    if (!symbol) return false;
    QList<uint> modifiers;
    if (combination.keyboardModifiers() & Qt::ControlModifier) modifiers << 0xffe3;
    if (combination.keyboardModifiers() & Qt::AltModifier) modifiers << 0xffe9;
    if (combination.keyboardModifiers() & Qt::MetaModifier) modifiers << 0xffeb;
    if (combination.keyboardModifiers() & Qt::ShiftModifier) modifiers << 0xffe1;
    if (d->wayland) {
        for (uint mod : modifiers) d->wayland->keyboard_keysym(mod, 1);
        d->wayland->keyboard_keysym(symbol, 1);
        d->wayland->keyboard_keysym(symbol, 0);
        for (auto it = modifiers.crbegin(); it != modifiers.crend(); ++it) d->wayland->keyboard_keysym(*it, 0);
        return true;
    }
#if QT_CONFIG(xcb)
    auto *x11 = qGuiApp->nativeInterface<QNativeInterface::QX11Application>();
    if (!x11) return false;
    Display *display = x11->display();
    const auto key = XKeysymToKeycode(display, symbol);
    if (!key) return false;
    QList<unsigned int> codes;
    for (uint mod : modifiers) {
        const auto code = XKeysymToKeycode(display, mod);
        if (!code) return false;
        codes << code;
    }
    for (auto code : codes) XTestFakeKeyEvent(display, code, true, CurrentTime);
    XTestFakeKeyEvent(display, key, true, CurrentTime);
    XTestFakeKeyEvent(display, key, false, CurrentTime);
    for (auto it = codes.crbegin(); it != codes.crend(); ++it) XTestFakeKeyEvent(display, *it, false, CurrentTime);
    XFlush(display);
    return true;
#else
    return false;
#endif
}
