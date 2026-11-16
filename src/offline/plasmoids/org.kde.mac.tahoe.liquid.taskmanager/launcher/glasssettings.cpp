// SPDX-License-Identifier: GPL-3.0-or-later
#include "glasssettings.h"
#include <KConfigGroup>
#include <KSharedConfig>
#include <Plasma/Theme>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QJsonArray>
#include <QDir>
#include <QEvent>
#include <QFile>
#include <QFileSystemWatcher>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQuickWindow>
#include <QQuickItem>
#include <QStandardPaths>
#include <QTimer>
#include <cmath>

class GlassSettingsStore : public QObject
{
    Q_OBJECT
public:
    QJsonObject materials;
    QJsonObject assets;
    Plasma::Theme theme;
    QFileSystemWatcher watcher;
    QTimer debounce;
    QByteArray publishedDocks;
    static GlassSettingsStore *instance()
    {
        static auto *store = new GlassSettingsStore(qGuiApp);
        return store;
    }
    explicit GlassSettingsStore(QObject *parent) : QObject(parent)
    {
        debounce.setSingleShot(true);
        debounce.setInterval(40);
        connect(&debounce, &QTimer::timeout, this, &GlassSettingsStore::reload);
        // Directory watching survives atomic replacement of kwinrc.
        watcher.addPath(QStandardPaths::writableLocation(QStandardPaths::ConfigLocation));
        connect(&watcher, &QFileSystemWatcher::directoryChanged, &debounce, qOverload<>(&QTimer::start));
        connect(&watcher, &QFileSystemWatcher::fileChanged, &debounce, qOverload<>(&QTimer::start));
        connect(&theme, &Plasma::Theme::themeChanged, this, [this] { refreshWindows(); Q_EMIT changed(); });
        QDBusConnection::sessionBus().connect(QString(), QStringLiteral("/org/kde/MacTahoe/Glass"),
            QStringLiteral("org.kde.MacTahoe.Glass"), QStringLiteral("changed"), this, SLOT(reload()));
        QDBusConnection::sessionBus().connect(QString(), QStringLiteral("/org/kde/MacTahoe/Glass"),
            QStringLiteral("org.kde.MacTahoe.Glass"), QStringLiteral("requestWindows"), this, SLOT(republishWindows()));
        qGuiApp->installEventFilter(this);
        reload();
    }
    void refresh(QWindow *window)
    {
        if (!window) return;
        const bool projectTheme = theme.themeName().startsWith(QStringLiteral("MacTahoeLiquidKde-"));
        QString component = window->property("_mttkde_glass_component").toString();
        if (component.isEmpty()) component = QStringLiteral("popups");
        // PanelView initializes its title after the applet attaches. Reassert
        // the component identity when the native surface is shown/reloaded.
        if (component == QStringLiteral("dock")) window->setTitle(QStringLiteral("mttkde-dock"));
        const auto prefix = theme.themeName().endsWith(QStringLiteral("-Light")) ? QStringLiteral("Light/") : QStringLiteral("Dark/");
        QList<QObject *> objects = window->findChildren<QObject *>();
        if (auto *quick = qobject_cast<QQuickWindow *>(window)) {
            if (quick->contentItem()) objects.append(quick->contentItem()->findChildren<QObject *>());
        }
        for (auto *object : objects) {
            if (object->metaObject()->indexOfProperty("imagePath") < 0) continue;
            QString source = object->property("_mttkde_glass_source").toString();
            if (source.isEmpty()) source = object->property("imagePath").toString();
            const QString surfaceComponent = source == QStringLiteral("widgets/panel-background") ? (component == QStringLiteral("dock") ? component : QStringLiteral("panel")) : component;
            const auto path = projectTheme ? assets.value(prefix + surfaceComponent + QLatin1Char('/') + source).toString() : QString();
            if (path.isEmpty() || !QFile::exists(path)) {
                if (!object->property("_mttkde_glass_source").toString().isEmpty()) object->setProperty("imagePath", source);
                continue;
            }
            object->setProperty("_mttkde_glass_source", source);
            if (object->property("imagePath").toString() != path) object->setProperty("imagePath", path);
        }
    }
    void refreshWindows()
    {
        for (auto *window : qGuiApp->allWindows()) refresh(window);
        publishWindows();
    }
    void publishWindows(bool force = false)
    {
        // Layer-shell panels have no compositor-visible title on Wayland.
        // Publish only tagged Dock bounds, including the owning process, so
        // the effect does not guess from panel position or thickness.
        QJsonArray docks;
        for (auto *window : qGuiApp->allWindows()) {
            if (!window->isVisible() || window->property("_mttkde_glass_component").toString() != QStringLiteral("dock")) continue;
            const QRect g = window->geometry();
            docks.append(QJsonObject{{QStringLiteral("pid"), qGuiApp->applicationPid()},
                {QStringLiteral("x"), g.x()}, {QStringLiteral("y"), g.y()},
                {QStringLiteral("width"), g.width()}, {QStringLiteral("height"), g.height()}});
        }
        const auto json = QJsonDocument(docks).toJson(QJsonDocument::Compact);
        if (!force && json == publishedDocks) return;
        publishedDocks = json;
        auto signal = QDBusMessage::createSignal(QStringLiteral("/org/kde/MacTahoe/Glass"),
            QStringLiteral("org.kde.MacTahoe.Glass"), QStringLiteral("windowsChanged"));
        signal << QString::fromUtf8(json);
        QDBusConnection::sessionBus().send(signal);
    }
public Q_SLOTS:
    void republishWindows() { publishWindows(true); }
    void reload()
    {
        const auto path = QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) + QStringLiteral("/kwinrc");
        if (QFile::exists(path) && !watcher.files().contains(path)) watcher.addPath(path);
        const auto config = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
        config->reparseConfiguration();
        const KConfigGroup group(config, QStringLiteral("Effect-liquidglass"));
        const auto current = QJsonDocument::fromJson(group.readEntry("ComponentMaterials", QString()).toUtf8()).object();
        QFile file(QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)
            + QStringLiteral("/mac-tahoe-liquid-kde/glass-surfaces/assets.json"));
        QJsonObject paths;
        if (file.open(QIODevice::ReadOnly)) paths = QJsonDocument::fromJson(file.readAll()).object();
        if (current == materials && paths == assets) return;
        materials = current;
        assets = paths;
        refreshWindows();
        Q_EMIT changed();
    }
Q_SIGNALS:
    void changed();
protected:
    bool eventFilter(QObject *object, QEvent *event) override
    {
        if (event->type() == QEvent::Show || event->type() == QEvent::Expose
            || event->type() == QEvent::Hide || event->type() == QEvent::Move || event->type() == QEvent::Resize) {
            if (auto *window = qobject_cast<QWindow *>(object)) {
                QPointer<QWindow> guarded(window);
                QTimer::singleShot(0, this, [this, guarded] { if (guarded) refresh(guarded); publishWindows(); });
            }
        }
        return false;
    }
};

GlassSettings::GlassSettings(QObject *parent) : QObject(parent)
{
    connect(GlassSettingsStore::instance(), &GlassSettingsStore::changed, this, &GlassSettings::changed);
}
void GlassSettings::setComponent(const QString &component)
{
    if (m_component == component) return;
    m_component = component;
    if (m_window) {
        m_window->setProperty("_mttkde_glass_component", component);
        if (component == QStringLiteral("dock")) m_window->setTitle(QStringLiteral("mttkde-dock"));
    }
    GlassSettingsStore::instance()->refresh(m_window);
    Q_EMIT changed();
}
void GlassSettings::setWindow(QWindow *window)
{
    if (m_window == window) return;
    m_window = window;
    if (m_window) {
        m_window->setProperty("_mttkde_glass_component", m_component);
        if (m_component == QStringLiteral("dock")) m_window->setTitle(QStringLiteral("mttkde-dock"));
    }
    GlassSettingsStore::instance()->refresh(m_window);
    Q_EMIT changed();
}
qreal GlassSettings::opacity(const QString &key) const
{
    const auto v = GlassSettingsStore::instance()->materials.value(m_component).toObject().value(key);
    if (!v.isDouble() || !std::isfinite(v.toDouble())) return -1;
    return 1.0 - qBound(0.0, v.toDouble(), 100.0) / 100.0;
}
qreal GlassSettings::lightOpacity() const { return opacity(QStringLiteral("SurfaceTransparencyLight")); }
qreal GlassSettings::darkOpacity() const { return opacity(QStringLiteral("SurfaceTransparencyDark")); }
#include "glasssettings.moc"
