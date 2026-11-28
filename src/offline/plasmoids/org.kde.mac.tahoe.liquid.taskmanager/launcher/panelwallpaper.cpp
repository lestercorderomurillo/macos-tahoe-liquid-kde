// SPDX-License-Identifier: GPL-3.0-or-later
#include "panelwallpaper.h"
#include "inkpixels.h"
#include "contrastpreset.h"
#include "materialsample.h"
#include "glasssettings.h"

#include <PlasmaActivities/Consumer>
#include <Plasma/Containment>
#include <Plasma/Corona>
#include <QQmlProperty>
#include <QPointer>
#include <QDir>
#include <QDBusConnection>
#include "backdropgeometry.h"
#include <QEvent>
#include <QFutureWatcher>
#include <QGuiApplication>
#include <QImageReader>
#include <QPalette>
#include <QScreen>
#include <QTimer>
#include <QtConcurrentRun>
#include <limits>
#include <optional>

namespace {
using namespace Qt::StringLiterals;

QImage loadWallpaper(const QString &source, QSize screen, bool dark, int fillMode)
{
    const QUrl url(source);
    const QString path = url.isLocalFile() ? url.toLocalFile() : source;
    if (!QDir::isAbsolutePath(path)) return {};
    QString file = path;
    if (QFileInfo(path).isDir()) {
        if (url.fragment() == u"day-night") return {};
        dark = url.fragment() == u"dark" || (url.fragment() != u"light" && dark);
        const QDir package(path);
        const QStringList folders = dark ? QStringList{u"contents/images_dark"_s, u"contents/images"_s}
                                         : QStringList{u"contents/images"_s};
        for (const auto &folder : folders) {
            const QDir images(package.filePath(folder));
            // Prefer an image sized for this output, then the nearest aspect
            // ratio and resolution. Plasma wallpapers often ship both crops.
            double best = std::numeric_limits<double>::infinity();
            for (const auto &name : images.entryList(QDir::Files | QDir::Readable)) {
                const auto candidate = images.filePath(name);
                const QSize size = QImageReader(candidate).size();
                if (size.isEmpty()) continue;
                const double x = double(screen.width()) / size.width();
                const double y = double(screen.height()) / size.height();
                const double cost = 4 * std::abs(std::log(x / y)) + std::abs(std::log(std::max(x, y)));
                if (cost < best) {
                    best = cost;
                    file = candidate;
                }
            }
            if (std::isfinite(best)) break;
        }
    }
    QImageReader reader(file);
    const auto size = reader.size();
    if (size.isEmpty() || reader.imageCount() > 1) return {};
    reader.setAutoTransform(true);
    auto image = reader.read();
    if (!image.isNull() && fillMode >= 3) {
        const bool rotated = reader.transformation() & QImageIOHandler::TransformationRotate90;
        const QSize nativeSize = rotated ? size.transposed() : size;
        image.setText(u"nativeWidth"_s, QString::number(nativeSize.width()));
        image.setText(u"nativeHeight"_s, QString::number(nativeSize.height()));
    }
    return image;
}

struct Wallpaper {
    QSize screen;
    QImage image;
    QColor background;
    int mode;
    bool blur;
    QColor pixel(QPointF point) const
    {
        if (image.isNull()) return background;
        const QPointF local = point;
        const QSizeF area = screen;
        QSizeF size = image.size();
        if (mode >= 3) size = QSizeF(image.text(u"nativeWidth"_s).toInt(), image.text(u"nativeHeight"_s).toInt());
        switch (mode) {
        case 0: size = area; break; // Stretch
        case 1: size.scale(area, Qt::KeepAspectRatio); break;
        case 2: size.scale(area, Qt::KeepAspectRatioByExpanding); break;
        case 4: size.setWidth(area.width()); break; // Tile vertically
        case 5: size.setHeight(area.height()); break; // Tile horizontally
        }
        if (size.isEmpty()) return {};
        const QPointF offset((area.width() - size.width()) / 2, (area.height() - size.height()) / 2);
        double x = (local.x() - offset.x()) / size.width();
        double y = (local.y() - offset.y()) / size.height();
        if (mode == 3 || mode == 5) x = local.x() / size.width() - std::floor(local.x() / size.width());
        if (mode == 3 || mode == 4) y = local.y() / size.height() - std::floor(local.y() / size.height());
        if (x < 0 || y < 0 || x >= 1 || y >= 1) return blur ? QColor() : background;
        return GlassInk::composite(background, image.pixelColor(int(x * image.width()), int(y * image.height())));
    }
};

struct WallpaperSpec {
    QSize screen;
    QRect panel;
    QString plugin;
    QString source;
    QColor color;
    int mode;
    bool blur;
    bool dark;
    bool panelScrim;
    bool operator==(const WallpaperSpec &) const = default;
};

std::optional<Wallpaper> panelWallpaper(const WallpaperSpec &spec)
{
    QImage image;
    if (spec.plugin != u"org.kde.color") {
        if (spec.plugin != u"org.kde.image" && spec.plugin != u"org.kde.slideshow") return {};
        image = loadWallpaper(spec.source, spec.screen, spec.dark, spec.mode);
        if (image.isNull()) return {};
    }
    return Wallpaper{spec.screen, std::move(image), spec.color, spec.mode, spec.blur};
}

// One observer and one result for all applets sharing this panel window.
class PanelInk : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QColor baseForeground READ baseForeground NOTIFY changed)
    Q_PROPERTY(quint64 revision READ revision NOTIFY changed)
public:
    PanelInk(QQuickWindow *window, Plasma::Containment *panel)
        : QObject(window), m_window(window), m_panel(panel)
    {
        if (panel->containmentType() != Plasma::Containment::Desktop)
            QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"), QStringLiteral("/org/kde/MacTahoe/Glass"),
                QStringLiteral("org.kde.MacTahoe.Glass"), QStringLiteral("controlBackdrop"),
                this, SLOT(panelBackdrop(int,QRect,QRect,QByteArray,QString)));
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("inkPixels"), this, SLOT(pixelReply(int,QRect,QString,QByteArray)));
        connect(&m_frame, &MaterialSample::changed, this, [this] { ++m_revision; Q_EMIT changed(); });
        m_refresh.setSingleShot(true);
        connect(&m_refresh, &QTimer::timeout, this, &PanelInk::refresh);
        connect(&m_settings, &GlassSettings::changed, this, [this] {
            if (!m_settings.dynamicTinting()) clearSamples();
            schedule();
        });
        connect(&m_activities, &KActivities::Consumer::currentActivityChanged, this, &PanelInk::schedule);
        connect(panel, &Plasma::Containment::screenChanged, this, &PanelInk::schedule);
        connect(panel->corona(), &Plasma::Corona::screenOwnerChanged, this, &PanelInk::schedule);
        connect(panel->corona(), &Plasma::Corona::containmentAdded, this, &PanelInk::schedule);
        connect(panel->corona(), &Plasma::Corona::screenGeometryChanged, this, &PanelInk::schedule);
        connect(window, &QWindow::screenChanged, this, &PanelInk::schedule);
        connect(window, &QWindow::widthChanged, this, &PanelInk::schedule);
        connect(window, &QWindow::heightChanged, this, &PanelInk::schedule);
        connect(window, &QWindow::xChanged, this, &PanelInk::schedule);
        connect(window, &QWindow::yChanged, this, &PanelInk::schedule);
        // KDE can change the package's day/night image with the application palette.
        window->installEventFilter(this);
        schedule();
    }
    QColor baseForeground() const { return qGuiApp->palette().color(QPalette::Active, QPalette::WindowText); }
    quint64 revision() const { return m_revision; }
    Q_INVOKABLE QColor foregroundFor(QRectF bounds, QColor base, QColor fill, const QJsonObject &profile,
                                     MaterialSample *material, QColor reference, QObject *owner = nullptr, int run = -1)
    {
        if (m_window->size().isEmpty()) return base;
        GlassInk::Samples samples;
        GlassInk::zonePoints(bounds, profile.value(u"sampleCount"_s).toInt(15), [&](QPointF p) {
            const QColor rendered = material ? material->at(p) : QColor();
            const QColor foreground = rendered.isValid() ? rendered : fill;
            QColor exact;
            if (profile.value(u"scope"_s) == u"letter"_s && m_panel && m_panel->containmentType() != Plasma::Containment::Desktop) {
                m_pixels.locate(m_window->geometry(), u"mttkde-panel-ink"_s);
                exact = m_pixels.at(p);
            }
            if (foreground.isValid() && foreground.alpha() == 255) {
                samples.add(foreground);
            } else if (exact.isValid() || (!m_liveColors.isEmpty() && m_liveFrame == m_window->geometry())) {
                QColor surface = exact;
                if (!surface.isValid()) {
                    const auto cell = [&](double pos, int origin, int size) { return std::clamp(int((pos - origin) * 64 / size), 0, 63); };
                    const auto point = p + m_liveFrame.topLeft();
                    const int index = 3 * (64 * cell(point.y(), m_liveBounds.y(), m_liveBounds.height())
                                          + cell(point.x(), m_liveBounds.x(), m_liveBounds.width()));
                    const auto *rgb = reinterpret_cast<const uchar *>(m_liveColors.constData()) + index;
                    surface = QColor(rgb[0], rgb[1], rgb[2]);
                }
                const auto frame = m_frame.at(p);
                if (frame.isValid()) surface = GlassInk::composite(surface, frame);
                const auto scrim = QColor::fromRgbF(0, 0, 0, PanelWallpaper::scrimOpacityAt(p.y() / m_window->height()));
                samples.add(GlassInk::composite(GlassInk::composite(surface, scrim), foreground));
            } else if (m_wallpaperPixels && m_requested) {
                QColor surface = m_wallpaperPixels->pixel(m_requested->panel.topLeft() + p);
                if (m_requested->panelScrim) surface = GlassInk::composite(surface,
                    QColor::fromRgbF(0, 0, 0, PanelWallpaper::scrimOpacityAt(p.y() / m_window->height())));
                samples.add(GlassInk::composite(surface, foreground));
            }
        });
        const auto corrected = m_history.tone(samples, reference, ContrastPreset::settings(profile), owner, run);
        return GlassInk::applyRoleCorrection(base, reference, corrected);
    }
    bool observes(Plasma::Containment *panel) const { return m_panel == panel; }

Q_SIGNALS:
    void changed();

private Q_SLOTS:
    void pixelReply(int pid, const QRect &frame, const QString &role, const QByteArray &data)
    {
        if (m_pixels.receive(pid, frame, role, data)) { ++m_revision; Q_EMIT changed(); }
    }
    void schedule() { m_refresh.start(0); }
    void panelBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &rgb, const QString &role)
    {
        if (role != u"mttkde-panel-ink" || pid != QCoreApplication::applicationPid() || !m_settings.dynamicTinting()
            || frame != m_window->geometry() || bounds.isEmpty() || rgb.size() != 64 * 64 * 3) return;
        m_frame.findWindowFrame(m_window, QStringLiteral("widgets/panel-background"));
        if (m_liveColors == rgb && m_liveBounds == bounds && m_liveFrame == frame) return;
        m_pixels.locate(frame, role);
        m_liveColors = rgb;
        m_liveBounds = bounds;
        m_liveFrame = frame;
        ++m_revision;
        Q_EMIT changed();
    }

private:
    bool eventFilter(QObject *object, QEvent *event) override
    {
        if (event->type() == QEvent::ApplicationPaletteChange || event->type() == QEvent::PaletteChange) {
            schedule();
            Q_EMIT changed();
        }
        return QObject::eventFilter(object, event);
    }

    void clearSamples()
    {
        ++m_generation;
        m_requested.reset();
        m_wallpaperPixels.reset();
        m_pixels.locate({}, {});
        m_liveColors.clear();
        ++m_revision;
        Q_EMIT changed();
    }

    void refresh()
    {
        if (!m_settings.dynamicTinting() || !m_panel || !m_window->screen() || m_window->size().isEmpty()) return;
        Plasma::Containment *desktop = nullptr;
        const auto currentActivity = m_activities.currentActivity();
        for (auto *containment : m_panel->corona()->containments()) {
            if (containment->containmentType() == Plasma::Containment::Desktop
                && (containment->activity().isEmpty() || containment->activity() == currentActivity)
                && int(m_panel->screen()) >= 0 && containment->screen() == m_panel->screen()) {
                desktop = containment;
                break;
            }
        }
        if (m_desktop != desktop) {
            if (m_desktop) disconnect(m_desktop, nullptr, this, nullptr);
            m_desktop = desktop;
            if (desktop) {
                connect(desktop, &Plasma::Containment::wallpaperGraphicsObjectChanged, this, &PanelInk::schedule);
                connect(desktop, &Plasma::Containment::wallpaperPluginChanged, this, &PanelInk::schedule);
            }
        }
        auto *wallpaper = desktop ? desktop->property("wallpaperGraphicsObject").value<QObject *>() : nullptr;
        if (m_wallpaper != wallpaper) {
            if (m_wallpaper) disconnect(m_wallpaper, nullptr, this, nullptr);
            m_wallpaper = wallpaper;
            if (wallpaper) QQmlProperty(wallpaper, u"configuration"_s).connectNotifySignal(this, SLOT(schedule()));
        }
        auto *config = wallpaper ? wallpaper->property("configuration").value<QObject *>() : nullptr;
        if (config != m_config) {
            if (m_config) disconnect(m_config, nullptr, this, nullptr);
            m_config = config;
            if (config) {
                for (const auto &key : {u"Image"_s, u"Color"_s, u"FillMode"_s, u"Blur"_s})
                    QQmlProperty(config, key).connectNotifySignal(this, SLOT(schedule()));
            }
        }
        if (!desktop || !wallpaper) {
            clearSamples();
            return;
        }
        const QRect screen = m_window->screen()->geometry();
        const QPoint origin = m_window->width() == screen.width() ? QPoint() : m_window->position() - screen.topLeft();
        const auto plugin = desktop->wallpaperPlugin();
        const auto setting = [config](const char *key) { return config ? config->property(key) : QVariant{}; };
        auto background = setting("Color").value<QColor>();
        if (!background.isValid()) background = plugin == u"org.kde.color" ? QColor(u"#1d99f3"_s) : QColor(Qt::white);
        const auto fillMode = setting("FillMode");
        const QString source = setting("Image").toString();
        const QUrl url(source);
        const bool automaticVariant = url.fragment().isEmpty()
            && QFileInfo(url.isLocalFile() ? url.toLocalFile() : source).isDir();
        const WallpaperSpec spec{screen.size(), QRect(origin, m_window->size()), plugin,
            source, background, fillMode.isValid() ? fillMode.toInt() : 2,
            setting("Blur").toBool(), automaticVariant && GlassInk::luminance(qGuiApp->palette().color(QPalette::Window)) < .179,
            m_panel->containmentType() != Plasma::Containment::Desktop};
        if (m_requested == spec) return;
        m_requested = spec;
        // Keep the displayed ink while decoding. A superseded job cannot publish.
        const auto generation = ++m_generation;
        auto *job = new QFutureWatcher<std::optional<Wallpaper>>(this);
        connect(job, &QFutureWatcher<std::optional<Wallpaper>>::finished, this, [this, job, generation] {
            job->deleteLater();
            if (generation != m_generation) return;
            m_wallpaperPixels = job->result();
            ++m_revision;
            Q_EMIT changed();
        });
        job->setFuture(QtConcurrent::run(panelWallpaper, spec));
    }
    InkPixels m_pixels;
    QQuickWindow *m_window;
    QPointer<Plasma::Containment> m_panel, m_desktop;
    QPointer<QObject> m_wallpaper, m_config;
    KActivities::Consumer m_activities;
    GlassSettings m_settings;
    QTimer m_refresh;
    std::optional<WallpaperSpec> m_requested;
    quint64 m_generation = 0;
    GlassInk::FlipHistory m_history;
    MaterialSample m_frame;
    QByteArray m_liveColors;
    QRect m_liveBounds, m_liveFrame;
    std::optional<Wallpaper> m_wallpaperPixels;
    quint64 m_revision = 0;
};
}

QObject *PanelWallpaper::sourceFor(QQuickWindow *window, QObject *containment) const
{
    auto *panel = qobject_cast<Plasma::Containment *>(containment);
    if (!window || !panel || !panel->corona()) return nullptr;
    for (auto *source : window->findChildren<PanelInk *>(Qt::FindDirectChildrenOnly)) {
        if (source->observes(panel)) return source;
    }
    return new PanelInk(window, panel);
}

qreal PanelWallpaper::scrimOpacityAt(qreal position)
{
    constexpr double peak = 0.10;
    constexpr double decay = 5.0;
    const double tail = std::exp(-decay);
    return peak * (std::exp(-decay * std::clamp(position, 0., 1.)) - tail) / (1. - tail);
}

#include "panelwallpaper.moc"
