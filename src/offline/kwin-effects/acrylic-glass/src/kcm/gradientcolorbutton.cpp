// SPDX-License-Identifier: GPL-2.0-or-later
#include "gradientcolorbutton.h"

#include <QAction>
#include <QApplication>
#include <QClipboard>
#include <QColorDialog>
#include <QDrag>
#include <QDropEvent>
#include <QMimeData>
#include <QMouseEvent>
#include <QStyleOptionButton>
#include <QStylePainter>

GradientColorButton::GradientColorButton(QWidget *parent)
    : QPushButton(parent)
{
    setAcceptDrops(true);
    setContextMenuPolicy(Qt::ActionsContextMenu);
    connect(this, &QPushButton::clicked, this, [this] {
        auto *dialog = new QColorDialog(color(), this);
        dialog->setAttribute(Qt::WA_DeleteOnClose);
        connect(dialog, &QColorDialog::colorSelected, this, &GradientColorButton::setColor);
        dialog->open();
    });

    auto *copy = new QAction(QCoreApplication::translate("QLineEdit", "&Copy"), this);
    copy->setShortcut(QKeySequence::Copy);
    copy->setShortcutContext(Qt::WidgetShortcut);
    connect(copy, &QAction::triggered, this, [this] {
        QApplication::clipboard()->setMimeData(colorMimeData());
    });
    addAction(copy);

    auto *paste = new QAction(QCoreApplication::translate("QLineEdit", "&Paste"), this);
    paste->setShortcut(QKeySequence::Paste);
    paste->setShortcutContext(Qt::WidgetShortcut);
    connect(paste, &QAction::triggered, this, [this] {
        const QColor pasted = readColor(QApplication::clipboard()->mimeData());
        if (pasted.isValid()) setColor(pasted);
    });
    addAction(paste);
}

void GradientColorButton::setColor(const QColor &color)
{
    if (m_color == color) return;
    m_color = color;
    update();
    Q_EMIT colorChanged(color);
}

void GradientColorButton::paintEvent(QPaintEvent *event)
{
    QPushButton::paintEvent(event);
    QStyleOptionButton option;
    initStyleOption(&option);
    const auto contents = style()->subElementRect(QStyle::SE_PushButtonContents, &option, this);
    const auto swatch = contents.adjusted(3, 3, -3, -3);
    if (swatch.isEmpty()) return;
    QStylePainter painter(this);
    painter.fillRect(swatch, isEnabled() && m_color.isValid() ? m_color : palette().button().color());
    painter.setPen(palette().mid().color());
    painter.drawRect(swatch.adjusted(0, 0, -1, -1));
}

void GradientColorButton::mousePressEvent(QMouseEvent *event)
{
    m_pressPosition = event->position().toPoint();
    QPushButton::mousePressEvent(event);
}

void GradientColorButton::mouseMoveEvent(QMouseEvent *event)
{
    if (!event->buttons().testFlag(Qt::LeftButton) || !m_color.isValid()
        || (event->position().toPoint() - m_pressPosition).manhattanLength() < QApplication::startDragDistance()) {
        QPushButton::mouseMoveEvent(event);
        return;
    }
    auto *drag = new QDrag(this);
    drag->setMimeData(colorMimeData());
    QPixmap swatch(24, 18);
    swatch.fill(m_color);
    drag->setPixmap(swatch);
    setDown(false);
    drag->exec(Qt::CopyAction);
    drag->deleteLater();
}

void GradientColorButton::dragEnterEvent(QDragEnterEvent *event)
{
    if (isEnabled() && readColor(event->mimeData()).isValid()) event->acceptProposedAction();
}

void GradientColorButton::dropEvent(QDropEvent *event)
{
    const QColor dropped = readColor(event->mimeData());
    if (!isEnabled() || !dropped.isValid()) return;
    setColor(dropped);
    event->acceptProposedAction();
}

QMimeData *GradientColorButton::colorMimeData() const
{
    auto *data = new QMimeData;
    data->setColorData(m_color);
    data->setText(m_color.name());
    return data;
}

QColor GradientColorButton::readColor(const QMimeData *data)
{
    if (!data) return {};
    if (data->hasColor()) return data->colorData().value<QColor>();
    const auto text = data->text();
    return text.startsWith(QLatin1Char('#')) ? QColor(text) : QColor();
}
