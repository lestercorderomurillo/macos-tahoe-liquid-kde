// SPDX-License-Identifier: GPL-3.0-or-later
#include "materialsample.h"
#include "glassink.h"
#include <QGlyphRun>
#include <QPainterPath>
#include <QTextLayout>
#include <QMap>
#include <limits>

MaterialSample::MaterialSample(QObject *parent) : QObject(parent)
{
    m_timer.setSingleShot(true);
    connect(&m_timer, &QTimer::timeout, this, &MaterialSample::capture);
}

void MaterialSample::setSource(QQuickItem *item)
{
    if (m_source == item) return;
    if (m_source) disconnect(m_source, nullptr, this, nullptr);
    m_source = item;
    m_pixels = {};
    m_pending.clear();
    if (item) {
        if (item->metaObject()->indexOfSignal("repaintNeeded()") >= 0)
            connect(item, SIGNAL(repaintNeeded()), this, SLOT(invalidate()));
        connect(item, &QQuickItem::windowChanged, this, &MaterialSample::invalidate);
        connect(item, &QQuickItem::visibleChanged, this, &MaterialSample::invalidate);
        connect(item, &QQuickItem::widthChanged, this, &MaterialSample::invalidate);
        connect(item, &QQuickItem::heightChanged, this, &MaterialSample::invalidate);
        connect(item, &QObject::destroyed, this, [this] {
            m_pixels = {};
            ++m_revision;
            Q_EMIT changed();
        });
    }
    invalidate();
    ++m_revision;
    Q_EMIT sourceChanged();
    Q_EMIT changed();
}

void MaterialSample::findWindowFrame(QQuickWindow *window, const QString &name)
{
    if (!window || !window->contentItem()) { setSource(nullptr); return; }
    auto items = window->contentItem()->childItems();
    auto *content = window->property("mainItem").value<QQuickItem *>();
    while (!items.isEmpty()) {
        auto *item = items.takeFirst();
        if (item == content || !item->isVisible()) continue;
        const auto path = item->property("imagePath").toString();
        const auto original = item->property("_mttkde_glass_source").toString();
        if ((path == name || original == name) && item->width() >= window->width() * .8
            && item->height() >= window->height() * .8 && item->childItems().isEmpty()) {
            setSource(item);
            return;
        }
        items.append(item->childItems());
    }
    setSource(nullptr);
}

void MaterialSample::invalidate()
{
    m_dirty = true;
    if (!m_pending && !m_timer.isActive()) m_timer.start(16);
}

void MaterialSample::capture()
{
    if (!m_source || !m_source->window() || !m_source->isVisible() || !m_source->window()->isVisible()
        || m_source->size().isEmpty()) return;
    m_dirty = false;
    // Qt scales the requested logical size with the render window's DPR.
    m_pending = m_source->grabToImage();
    if (!m_pending) return;
    connect(m_pending.data(), &QQuickItemGrabResult::ready, this, [this] {
        const auto image = m_pending->image();
        m_pending.clear();
        if (image != m_pixels) {
            m_pixels = image;
            ++m_revision;
            Q_EMIT changed();
        }
        if (m_dirty) invalidate();
    });
}

QColor MaterialSample::at(QPointF scenePoint) const
{
    if (!m_source || m_pixels.isNull() || m_source->size().isEmpty()) return {};
    const auto local = m_source->mapFromScene(scenePoint);
    if (!m_source->boundingRect().contains(local)) return {};
    const int x = qBound(0, int(local.x() * m_pixels.width() / m_source->width()), m_pixels.width() - 1);
    const int y = qBound(0, int(local.y() * m_pixels.height() / m_source->height()), m_pixels.height() - 1);
    return m_pixels.pixelColor(x, y);
}

QList<QColor> MaterialSample::smoothGlyphColors(const QList<QColor> &colors) const
{
    return GlassInk::smoothGlyphColors(colors);
}

QVariantList MaterialSample::textRuns(const QString &text, const QFont &font, qreal width,
                                      int wrapMode, int alignment, bool letters)
{
    QString content = text;
    content.replace(QLatin1Char('\n'), QChar::LineSeparator);
    QTextOption options;
    options.setWrapMode(static_cast<QTextOption::WrapMode>(wrapMode));
    options.setAlignment(Qt::Alignment(alignment) & Qt::AlignHorizontal_Mask);
    QTextLayout layout(content, font);
    layout.setTextOption(options);
    layout.beginLayout();
    qreal y = 0;
    for (auto line = layout.createLine(); line.isValid(); line = layout.createLine()) {
        line.setLineWidth(std::max(1., width));
        line.setPosition({0, y});
        y += line.height();
    }
    layout.endLayout();
    QVariantList result;
    for (int n = 0; n < layout.lineCount(); ++n) {
        const auto line = layout.lineAt(n);
        const int end = line.textStart() + line.textLength();
        if (!letters) {
            result.append(QVariantMap{{QStringLiteral("text"), text.mid(line.textStart(), line.textLength())},
                                      {QStringLiteral("bounds"), line.naturalTextRect()}});
            continue;
        }
        QMap<int, QPointF> clusters;
        for (const auto &run : line.glyphRuns(-1, -1, QTextLayout::RetrieveAll)) {
            const auto indices = run.stringIndexes();
            const auto glyphs = run.glyphIndexes();
            const auto positions = run.positions();
            for (qsizetype i = 0; i < glyphs.size(); ++i) {
                if (clusters.contains(indices[i])) continue;
                const auto path = run.rawFont().pathForGlyph(glyphs[i]);
                const auto bounds = path.boundingRect();
                QPointF point = bounds.center();
                if (!path.isEmpty() && !path.contains(point)) {
                    double best = std::numeric_limits<double>::infinity();
                    for (int y = 0; y < 15; ++y) for (int x = 0; x < 15; ++x) {
                        const QPointF p(bounds.left() + bounds.width() * (x + .5) / 15,
                                        bounds.top() + bounds.height() * (y + .5) / 15);
                        const auto delta = p - bounds.center();
                        const double distance = QPointF::dotProduct(delta, delta);
                        if (distance < best && path.contains(p)) { best = distance; point = p; }
                    }
                }
                clusters.insert(indices[i], positions[i] + point);
            }
        }
        if (!clusters.contains(line.textStart())) clusters.insert(line.textStart(), line.naturalTextRect().topLeft());
        for (auto i = clusters.begin(); i != clusters.end(); ++i) {
            const auto next = std::next(i);
            const int limit = next == clusters.end() ? end : next.key();
            result.append(QVariantMap{{QStringLiteral("text"), text.mid(i.key(), limit - i.key())},
                {QStringLiteral("line"), n}, {QStringLiteral("lineTop"), line.y()},
                {QStringLiteral("bounds"), QRectF(i.value() - QPointF(.25, .25), QSizeF(.5, .5))}});
        }
    }
    return result;
}
