// SPDX-License-Identifier: GPL-3.0-or-later
#include "glasssettings.h"
#include "glassink.h"
#include <KConfigGroup>
#include <KWindowEffects>
#include <QRegion>
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
#include <QScreen>
#include <QStandardPaths>
#include <QTimer>
#include <cmath>

class GlassSettingsStore : public QObject
{
    Q_OBJECT
public:
    bool dynamicTinting = true;
    QJsonObject materials;
    QJsonObject assets;
    Plasma::Theme theme;
    QFileSystemWatcher watcher;
    QTimer debounce;
    QByteArray publishedDocks;
    QByteArray publishedCorners;
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
            auto *root = quick->contentItem();
            if (root) objects.append(root->findChildren<QObject *>());
            // PlasmaQuick::Dialog parents its painted frame visually to the
            // window, but its QObject owner is the shared QML engine.
            if (root && component == QStringLiteral("apps")) {
                const auto *content = window->property("mainItem").value<QQuickItem *>();
                auto items = root->childItems();
                while (!items.isEmpty()) {
                    auto *item = items.takeLast();
                    if (item == content) continue;
                    objects.append(item);
                    items.append(item->childItems());
                }
            }
        }
        const QString frameSource = window->property("_mttkde_glass_frame_source").toString();
        for (auto *object : objects) {
            if (object->metaObject()->indexOfProperty("imagePath") < 0) continue;
            QString source = object->property("_mttkde_glass_source").toString();
            if (source.isEmpty()) source = object->property("imagePath").toString();
            const QString surfaceComponent = source == QStringLiteral("widgets/panel-background") ? (component == QStringLiteral("dock") ? component : QStringLiteral("panel")) : component;
            const QString assetSource = !frameSource.isEmpty() && source == QStringLiteral("dialogs/background")
                ? frameSource : source;
            auto path = projectTheme ? assets.value(prefix + surfaceComponent + QLatin1Char('/') + assetSource).toString() : QString();
            if (projectTheme && assetSource != source && !QFile::exists(path)) {
                path = QStandardPaths::locate(QStandardPaths::GenericDataLocation,
                    QStringLiteral("plasma/desktoptheme/") + theme.themeName() + QLatin1Char('/') + assetSource + QStringLiteral(".svgz"));
            }
            if (path.isEmpty() || !QFile::exists(path)) {
                if (!object->property("_mttkde_glass_source").toString().isEmpty()) object->setProperty("imagePath", source);
                continue;
            }
            object->setProperty("_mttkde_glass_source", source);
            if (object->property("imagePath").toString() != path) object->setProperty("imagePath", path);
            // Dialog manages blur from a separate default frame. Submit the
            // visible replacement's mask so glass ends at the painted edge.
            auto *item = qobject_cast<QQuickItem *>(object);
            if (item && item->isVisible() && item->size().toSize() == window->size()
                && source == QStringLiteral("dialogs/background")
                && (!frameSource.isEmpty() || window->property("_mttkde_custom_frame_mask").toBool())) {
                const QRegion region = item->property("mask").value<QRegion>();
                if (!region.isEmpty()) {
                    if (window->mask() != region) window->setMask(region);
                    KWindowEffects::enableBlurBehind(window, true, region);
                    window->setProperty("_mttkde_custom_frame_mask", !frameSource.isEmpty());
                }
            }
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
        QJsonArray corners;
        for (auto *window : qGuiApp->allWindows()) {
            if (!window->isVisible()) continue;
            const auto corner = window->property("_mttkde_display_corners").toSizeF();
            if (!corner.isEmpty() && window->screen()) {
                corners.append(QJsonObject{{QStringLiteral("output"), window->screen()->name()},
                    {QStringLiteral("extent"), corner.width()}, {QStringLiteral("control"), corner.height()}});
            }
            if (window->property("_mttkde_glass_component").toString() != QStringLiteral("dock")) continue;
            const QRect g = window->geometry();
            docks.append(QJsonObject{{QStringLiteral("pid"), qGuiApp->applicationPid()},
                {QStringLiteral("x"), g.x()}, {QStringLiteral("y"), g.y()},
                {QStringLiteral("width"), g.width()}, {QStringLiteral("height"), g.height()}});
        }
        const auto publish = [force](const QJsonArray &entries, QByteArray &previous, const QString &name) {
            const auto json = QJsonDocument(entries).toJson(QJsonDocument::Compact);
            if (!force && json == previous) return;
            previous = json;
            auto signal = QDBusMessage::createSignal(QStringLiteral("/org/kde/MacTahoe/Glass"),
                QStringLiteral("org.kde.MacTahoe.Glass"), name);
            signal << QString::fromUtf8(json);
            QDBusConnection::sessionBus().send(signal);
        };
        publish(docks, publishedDocks, QStringLiteral("windowsChanged"));
        publish(corners, publishedCorners, QStringLiteral("displayCornersChanged"));
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
        const bool tinting = group.readEntry("DynamicTinting", true);
        if (current == materials && paths == assets && dynamicTinting == tinting) return;
        dynamicTinting = tinting;
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
            || event->type() == QEvent::Hide || event->type() == QEvent::Move || event->type() == QEvent::Resize
            || event->type() == QEvent::ScreenChangeInternal) {
            if (auto *window = qobject_cast<QWindow *>(object)) {
                QPointer<QWindow> guarded(window);
                QTimer::singleShot(0, this, [this, guarded] { if (guarded) refresh(guarded); publishWindows(); });
            }
        }
        return false;
    }
};

bool GlassSettings::dynamicTinting() const
{
    return GlassSettingsStore::instance()->dynamicTinting;
}

GlassSettings::GlassSettings(QObject *parent) : QObject(parent)
{
    connect(GlassSettingsStore::instance(), &GlassSettingsStore::changed, this, &GlassSettings::changed);
}
GlassSettings::~GlassSettings()
{
    if (m_window && !m_displayCorners.isEmpty()) {
        m_window->setProperty("_mttkde_display_corners", QVariant());
        GlassSettingsStore::instance()->publishWindows();
    }
}

void GlassSettings::setDisplayCorners(QSizeF geometry)
{
    if (m_displayCorners == geometry) return;
    m_displayCorners = geometry;
    if (m_window) {
        m_window->setProperty("_mttkde_display_corners", geometry);
        GlassSettingsStore::instance()->publishWindows();
    }
    Q_EMIT changed();
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
void GlassSettings::setFrameSource(const QString &source)
{
    if (m_frameSource == source) return;
    m_frameSource = source;
    if (m_window) m_window->setProperty("_mttkde_glass_frame_source", source);
    GlassSettingsStore::instance()->refresh(m_window);
    Q_EMIT changed();
}
void GlassSettings::setWindow(QWindow *window)
{
    if (m_window == window) return;
    const bool hasDisplayCorners = !m_displayCorners.isEmpty();
    if (m_window && hasDisplayCorners) m_window->setProperty("_mttkde_display_corners", QVariant());
    m_window = window;
    if (m_window && hasDisplayCorners) m_window->setProperty("_mttkde_display_corners", m_displayCorners);
    if (hasDisplayCorners) GlassSettingsStore::instance()->publishWindows();
    if (m_window) {
        m_window->setProperty("_mttkde_glass_component", m_component);
        m_window->setProperty("_mttkde_glass_frame_source", m_frameSource);
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

QColor GlassSettings::notificationForeground(QColor base, QColor backdrop, QColor fill) const
{
    if (!dynamicTinting() || !backdrop.alpha()) return base;
    GlassInk::Samples samples(base, GlassInk::control);
    samples.add(GlassInk::composite(backdrop, fill));
    return samples.resolve(base);
}

QColor GlassSettings::animatedNotificationForeground(QObject *item, QWindow *window, QColor base, QColor backdrop, QColor fill)
{
    m_ink.observe(window);
    return m_ink.color(item, base, notificationForeground(base, backdrop, fill));
}
