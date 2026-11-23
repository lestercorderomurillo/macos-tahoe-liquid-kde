// SPDX-License-Identifier: GPL-3.0-or-later
#include "panelwallpaper.h"
#include "glassink.h"

#include <QDBusConnection>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDir>
#include <QFutureWatcher>
#include <QGuiApplication>
#include <QImageReader>
#include <QPalette>
#include <QQuickWindow>
#include <QScreen>
#include <QtConcurrentRun>
#include <limits>
#include <memory>
#include <optional>

namespace {
using namespace Qt::StringLiterals;

constexpr auto plasma = "org.kde.plasmashell";
const auto shellPath = u"/PlasmaShell"_s;
const auto shellInterface = u"org.kde.PlasmaShell"_s;

QColor wallpaperColor(const QVariant &value, QColor fallback)
{
    if (const QColor color = value.value<QColor>(); color.isValid()) return color;
    // QColor is marshalled by Qt D-Bus as a structure containing its QRgb.
    const auto argument = value.value<QDBusArgument>();
    if (argument.currentSignature() != u"(u)") return fallback;
    uint rgba = 0;
    argument.beginStructure();
    argument >> rgba;
    argument.endStructure();
    return QColor::fromRgba(rgba);
}

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
    // Keep native dimensions for centered and tiled images, even when the
    // decoded copy is smaller. Qt only needs a small image for contrast.
    if (size.width() > 512 || size.height() > 512) reader.setScaledSize(size.scaled(512, 512, Qt::KeepAspectRatio));
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
    QString source;
    QColor color;
    int mode;
    bool blur;
    bool dark;
    bool operator==(const WallpaperSpec &) const = default;
};

class Wallpapers : public QObject
{
    Q_OBJECT
public:
    Wallpapers()
    {
        connect(&m_timer, &QTimer::timeout, this, [this] {
            for (auto i = m_outputs.cbegin(); i != m_outputs.cend(); ++i) refresh(i.key(), i.value());
        });
        QDBusConnection::sessionBus().connect(QString::fromLatin1(plasma), shellPath, shellInterface,
                                               u"wallpaperChanged"_s, this, SLOT(refreshOutput(uint)));
    }

    void addWatcher(int screen, QSize size)
    {
        auto &output = m_outputs[screen];
        if (!output) output = std::make_shared<Output>();
        ++output->watchers;
        resize(screen, size);
        if (!m_timer.isActive()) m_timer.start(2000);
    }

    void removeWatcher(int screen)
    {
        const auto output = m_outputs.value(screen);
        if (!output || --output->watchers) return;
        m_outputs.remove(screen);
        if (m_outputs.isEmpty()) m_timer.stop();
    }

    void resize(int screen, QSize size)
    {
        const auto output = m_outputs.value(screen);
        if (output && output->size != size) {
            output->size = size;
            refresh(screen, output);
        }
    }

    const Wallpaper *current(int screen) const
    {
        const auto output = m_outputs.value(screen);
        return output && output->wallpaper ? &*output->wallpaper : nullptr;
    }

Q_SIGNALS:
    void changed(int screen);

private:
    struct Output {
        int watchers = 0;
        QSize size;
        bool pending = false;
        std::optional<WallpaperSpec> spec;
        std::optional<Wallpaper> wallpaper;
    };

    Q_SLOT void refreshOutput(uint screen)
    {
        if (const auto output = m_outputs.value(int(screen))) refresh(int(screen), output);
    }

    void refresh(int screen, std::shared_ptr<Output> output)
    {
        if (output->pending) return;
        output->pending = true;
        // Read the active desktop's live configuration map. Slide changes
        // update that map before Plasma saves the desktop configuration.
        auto call = QDBusMessage::createMethodCall(QString::fromLatin1(plasma), shellPath, shellInterface, u"wallpaper"_s);
        call << uint(screen);
        auto *query = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(call, 2000), this);
        connect(query, &QDBusPendingCallWatcher::finished, this, [this, query, output, screen] {
            const QDBusPendingReply<QVariantMap> reply = *query;
            query->deleteLater();
            output->pending = false;
            if (m_outputs.value(screen) != output || reply.isError()) return;
            const auto config = reply.value();
            const auto plugin = config.value(u"wallpaperPlugin"_s).toString();
            const bool solid = plugin == u"org.kde.color";
            if (!solid && plugin != u"org.kde.image" && plugin != u"org.kde.slideshow") {
                output->spec.reset();
                if (output->wallpaper) {
                    output->wallpaper.reset();
                    Q_EMIT changed(screen);
                }
                return;
            }
            const WallpaperSpec spec{
                output->size,
                config.value(u"Image"_s).toString(),
                wallpaperColor(config.value(u"Color"_s), solid ? QColor(u"#1d99f3"_s) : QColor(Qt::white)),
                config.value(u"FillMode"_s, 2).toInt(),
                config.value(u"Blur"_s).toBool(),
                GlassInk::luminance(qGuiApp->palette().color(QPalette::Window)) < .179
            };
            if (output->spec == spec) return;
            output->spec = spec;
            output->pending = true;
            auto *job = new QFutureWatcher<std::optional<Wallpaper>>(this);
            connect(job, &QFutureWatcher<std::optional<Wallpaper>>::finished, this, [this, job, output, screen] {
                job->deleteLater();
                output->pending = false;
                if (m_outputs.value(screen) != output) return;
                output->wallpaper = job->result();
                Q_EMIT changed(screen);
            });
            job->setFuture(QtConcurrent::run([spec, solid]() -> std::optional<Wallpaper> {
                QImage image = solid ? QImage() : loadWallpaper(spec.source, spec.screen, spec.dark, spec.mode);
                if (image.isNull() && !solid) return std::nullopt;
                return Wallpaper{spec.screen, std::move(image), spec.color, spec.mode, spec.blur};
            }));
        });
    }

    QTimer m_timer;
    QHash<int, std::shared_ptr<Output>> m_outputs;
};

Wallpapers &wallpapers()
{
    static Wallpapers store;
    return store;
}
}

PanelWallpaper::PanelWallpaper(QObject *parent) : QObject(parent)
{
    connect(&wallpapers(), &Wallpapers::changed, this, [this](int screen) {
        if (screen == m_screen) revise();
    });
}

PanelWallpaper::~PanelWallpaper()
{
    if (m_screen >= 0) wallpapers().removeWatcher(m_screen);
}

void PanelWallpaper::setWatching(bool watching)
{
    if (m_watching == watching) return;
    m_watching = watching;
    if (!watching && m_screen >= 0) {
        wallpapers().removeWatcher(m_screen);
        m_screen = -1;
        m_transition.reset();
    }
    Q_EMIT watchingChanged();
}

void PanelWallpaper::revise()
{
    ++m_revision;
    Q_EMIT changed();
}

qreal PanelWallpaper::scrimOpacityAt(qreal position)
{
    constexpr double peak = 0.10;
    constexpr double decay = 5.0;
    const double tail = std::exp(-decay);
    return peak * (std::exp(-decay * std::clamp(position, 0., 1.)) - tail) / (1. - tail);
}

QColor PanelWallpaper::foregroundAt(QQuickItem *item, int screenNumber, QPointF center, QColor base)
{
    if (!m_watching || screenNumber < 0 || !item || !item->window() || !item->window()->screen()) return base;
    const auto *window = item->window();
    const auto screen = window->screen()->geometry();
    if (m_screen != screenNumber) {
        if (m_screen >= 0) wallpapers().removeWatcher(m_screen);
        m_screen = screenNumber;
        wallpapers().addWatcher(m_screen, screen.size());
    } else {
        wallpapers().resize(m_screen, screen.size());
    }
    const auto *wallpaper = wallpapers().current(m_screen);
    if (!wallpaper) return base;

    // A full-width top panel is anchored to its output. Wayland clients can
    // report a window-local origin even on a secondary output.
    const QPointF origin = window->width() == screen.width() ? screen.topLeft() : window->position();
    const QPointF point = origin + center;
    const QSizeF radius(std::clamp(item->width() / 3, 3., 42.), std::clamp(item->height() / 4, 2., 6.));
    const auto target = GlassInk::sample(base, m_transition.target(item, base), GlassInk::label, point, radius, [&](QPointF sample) {
        const QPointF local = sample - screen.topLeft();
        const QColor pixel = wallpaper->pixel(QPointF(std::clamp(local.x(), 0., double(screen.width() - 1)),
                                                     std::clamp(local.y(), 0., double(screen.height() - 1))));
        if (!pixel.isValid()) return QColor();
        // Interpolate the same samples used by the Qt Quick gradient.
        const double position = std::clamp((sample.y() - origin.y()) / std::max(1, window->height()), 0., 1.);
        const double segment = position * 8;
        const double left = std::floor(segment);
        const double right = std::min(8., left + 1);
        QColor scrim = Qt::black;
        scrim.setAlphaF(std::lerp(scrimOpacityAt(left / 8), scrimOpacityAt(right / 8), segment - left));
        return GlassInk::composite(pixel, scrim);
    });
    return m_transition.color(item, base, target);
}

#include "panelwallpaper.moc"
