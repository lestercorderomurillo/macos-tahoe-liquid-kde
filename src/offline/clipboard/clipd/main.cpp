// SPDX-License-Identifier: GPL-3.0-or-later
// mac-tahoe-clipd: records clipboard text and images, serves them to the clipboard popup over D-Bus.
#include "historycipher.h"
#include <QBuffer>
#include <sys/stat.h>
#include <QCryptographicHash>
#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusReply>
#include <QDir>
#include <QDateTime>
#include <QRegularExpression>
#include <utility>
#include <QFile>
#include <QGuiApplication>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMimeData>
#include <QLockFile>
#include <memory>
#include <QStandardPaths>
#include <QTextDocumentFragment>
#include <QTimer>
#include <KSystemClipboard>

namespace {
constexpr int kMaxUnpinned = 40;
constexpr qint64 kMaxText = 1024 * 1024;       // 1 MB of text per item
constexpr qint64 kMaxImagePixels = 40'000'000; // ~ 8K x 5K
}

struct Item {
    QString id, kind, text;
    int w = 0, h = 0;
    qint64 bytes = 0, ts = 0;
    bool pinned = false;
};

class Store : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.mactahoe.Clipboard")
public:
    Store()
    {
        m_dir = QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) + "/mac-tahoe-liquid-kde/clipboard";
        if (!QDir().mkpath(m_dir + "/images") ||
            !QFile::setPermissions(m_dir, QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner))
            throw std::runtime_error("Cannot secure clipboard directory");
        lock = std::make_unique<QLockFile>(m_dir + "/store.lock");
        lock->setStaleLockTime(0);
        if (!lock->tryLock()) throw std::runtime_error("Clipboard history is in use");
        cipher.initialize(QFile::exists(m_dir + "/index.enc") || !QDir(m_dir + "/images").entryList({"*.enc"}).isEmpty());
        load();
        m_debounce.setSingleShot(true);
        m_debounce.setInterval(40);   // coalesce bursts from one copy without dropping quick successive copies
        connect(&m_debounce, &QTimer::timeout, this, &Store::capture);
        connect(KSystemClipboard::instance(), &KSystemClipboard::changed, this, [this](QClipboard::Mode mode) {
            if (mode == QClipboard::Clipboard) {
                m_currentId.clear();
                m_debounce.start();
            }
        });
        QTimer::singleShot(300, this, &Store::capture); // pick up whatever is on the clipboard right now
    }

public Q_SLOTS:
    QString version() { return QStringLiteral("1"); }

    // Lets the uninstaller stop the service without signals; replies before exiting.
    void quit() { QTimer::singleShot(50, qApp, &QCoreApplication::quit); }

    QString list()
    {
        QJsonArray arr;
        for (const Item &it : std::as_const(m_items)) {
            QJsonObject o{{"id", it.id}, {"kind", it.kind}, {"ts", double(it.ts)}, {"pinned", it.pinned}};
            if (it.kind == "text") o["text"] = it.text;
            else { o["w"] = it.w; o["h"] = it.h; o["bytes"] = double(it.bytes); o["thumbnail"] = thumbnail(it.id); }
            arr.append(o);
        }
        return QString::fromUtf8(QJsonDocument(arr).toJson(QJsonDocument::Compact));
    }

    QString currentId() const { return m_currentId; }

    void copy(const QString &id)
    {
        int i = indexOf(id);
        if (i < 0) return;
        Item it = m_items.takeAt(i);
        it.ts = now();
        m_items.prepend(it);
        auto *md = new QMimeData;
        if (it.kind == "text") {
            md->setText(it.text);
        } else {
            const auto png = imageData(id);
            QImage img = QImage::fromData(png, "PNG");
            if (img.isNull()) { delete md; return; }
            md->setImageData(img);
            md->setData("image/png", png);
        }
        KSystemClipboard::instance()->setMimeData(md, QClipboard::Clipboard);
        save();
    }

    void remove(const QString &id)
    {
        int i = indexOf(id);
        if (i < 0 || m_items.at(i).pinned) return;
        dropFiles(m_items.at(i));
        m_items.removeAt(i);
        save();
    }

    void clearHistory()
    {
        for (int i = m_items.size() - 1; i >= 0; --i) {
            if (!m_items.at(i).pinned) { dropFiles(m_items.at(i)); m_items.removeAt(i); }
        }
        save();
    }

    void setPinned(const QString &id, bool pinned)
    {
        int i = indexOf(id);
        if (i < 0) return;
        m_items[i].pinned = pinned;
        prune();
        save();
    }

    void addText(const QString &text, bool pinned)
    {
        Item it;
        if (!textItem(text, it)) return;
        it.pinned = pinned;
        insert(it);
        save();
    }

Q_SIGNALS:
    void changed();

private:
    std::unique_ptr<QLockFile> lock;
    HistoryCipher cipher;
    QHash<QString, QString> previews;
    QByteArray imageData(const QString &id) const {
        auto png = cipher.open(imagePath(id));
        if (QCryptographicHash::hash("img" + png, QCryptographicHash::Sha1).toHex() != id.toLatin1())
            throw std::runtime_error("Clipboard image does not match its index");
        return png;
    }

    QString thumbnail(const QString &id) {
        if (!previews.contains(id)) {
            const auto image = QImage::fromData(imageData(id), "PNG");
            QByteArray png;
            QBuffer buffer(&png);
            buffer.open(QIODevice::WriteOnly);
            image.scaled(160, 120, Qt::KeepAspectRatio, Qt::SmoothTransformation).save(&buffer, "PNG");
            previews.insert(id, QString::fromLatin1(png.toBase64()));
        }
        return previews.value(id);
    }
    QString m_dir;
    QString m_currentId;
    QList<Item> m_items; // newest first
    QTimer m_debounce;

    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    QString imagePath(const QString &id) const { return m_dir + "/images/" + cipher.imageName(id) + ".enc"; }
    int indexOf(const QString &id) const
    {
        for (int i = 0; i < m_items.size(); ++i)
            if (m_items.at(i).id == id) return i;
        return -1;
    }
    void dropFiles(const Item &it) {
        if (it.kind == "image") {
            previews.remove(it.id);
            QFile::remove(imagePath(it.id));
        }
    }

    static bool textItem(const QString &text, Item &out)
    {
        if (text.trimmed().isEmpty() || text.toUtf8().size() > kMaxText) return false;
        out.kind = "text"; out.text = text;
        out.id = QString::fromLatin1(QCryptographicHash::hash("txt" + text.toUtf8(), QCryptographicHash::Sha1).toHex());
        out.ts = now();
        return true;
    }

    // Plain text from whatever the source offered: standard text/plain, a charset variant, the X11
    // names (UTF8_STRING / STRING / TEXT) some XWayland apps use, or, as a last resort, text/html.
    static QString textOf(const QMimeData *md)
    {
        if (md->hasText()) {
            const QString t = md->text();
            if (!t.trimmed().isEmpty()) return t;
        }
        const QStringList formats = md->formats();
        for (const QString &f : formats) {
            if (f.startsWith(QLatin1String("text/plain"), Qt::CaseInsensitive) || f == QLatin1String("UTF8_STRING")) {
                const QString t = QString::fromUtf8(md->data(f));
                if (!t.trimmed().isEmpty()) return t;
            }
        }
        for (const QString &f : {QStringLiteral("STRING"), QStringLiteral("TEXT")}) {
            if (formats.contains(f)) {
                const QString t = QString::fromLatin1(md->data(f));
                if (!t.trimmed().isEmpty()) return t;
            }
        }
        // HTML is only a text source when no image came with it: "copy image" offers <img> markup plus the picture.
        if (!md->hasImage() && formats.contains(QStringLiteral("text/html"))) {
            QString t = QTextDocumentFragment::fromHtml(QString::fromUtf8(md->data(QStringLiteral("text/html")))).toPlainText();
            t.remove(QChar::ObjectReplacementCharacter);   // inline images/objects render as U+FFFC
            if (!t.trimmed().isEmpty()) return t;
        }
        return {};
    }

    // Build an Item from clipboard data; pngOut receives the encoded PNG for images.
    bool build(const QMimeData *md, Item &it, QByteArray *pngOut)
    {
        if (!md || md->hasFormat("x-kde-passwordManagerHint")) return false; // never record secrets
        // Real text wins over an image: spreadsheet cells, rich-text copies and the like offer both,
        // and the text is what the user meant. Pure images (screenshots, "copy image") have none.
        const QString text = textOf(md);
        if (!text.isEmpty()) return textItem(text, it);
        if (md->hasImage()) {
            QImage img = qvariant_cast<QImage>(md->imageData());
            if (img.isNull() || qint64(img.width()) * img.height() > kMaxImagePixels) return false;
            QByteArray png;
            QBuffer buf(&png); buf.open(QIODevice::WriteOnly);
            if (!img.save(&buf, "PNG")) return false;
            it.kind = "image"; it.w = img.width(); it.h = img.height(); it.bytes = png.size(); it.ts = now();
            it.id = QString::fromLatin1(QCryptographicHash::hash("img" + png, QCryptographicHash::Sha1).toHex());
            if (pngOut) *pngOut = png;
            return true;
        }
        return false;
    }

    void capture()
    {
        Item it; QByteArray png;
        if (!build(KSystemClipboard::instance()->mimeData(QClipboard::Clipboard), it, &png)) return;
        if (it.kind == "image" && !QFile::exists(imagePath(it.id))) {
            cipher.seal(imagePath(it.id), png);
        }
        m_currentId = it.id;
        insert(it);
        save();
    }

    void insert(Item it)
    {
        int i = indexOf(it.id);
        if (i >= 0) { it.pinned = m_items.at(i).pinned; m_items.removeAt(i); }
        m_items.prepend(it);
        prune();
    }

    void prune()
    {
        int unpinned = 0;
        for (int i = 0; i < m_items.size(); ++i) {
            if (m_items.at(i).pinned) continue;
            if (++unpinned > kMaxUnpinned) { dropFiles(m_items.at(i)); m_items.removeAt(i--); }
        }
    }

    void load()
    {
        const QString legacy = m_dir + "/index.json";
        const QString encrypted = m_dir + "/index.enc";
        // Leave the legacy originals intact until the encrypted index commits.
        QDir images(m_dir + "/images");
        const auto originals = images.entryList({"*.png"}, QDir::Files);
        for (const QString &name : originals) {
            if (!QRegularExpression("^[0-9a-f]{40}\\.png$").match(name).hasMatch()) continue;
            cipher.seal(imagePath(name.left(40)), HistoryCipher::read(images.filePath(name)));
        }
        QJsonDocument doc;
        if (QFile::exists(encrypted)) doc = QJsonDocument::fromJson(cipher.open(encrypted));
        else if (QFile::exists(legacy)) doc = QJsonDocument::fromJson(HistoryCipher::read(legacy));
        else doc = QJsonDocument(QJsonArray());
        if (!doc.isArray()) throw std::runtime_error("Invalid clipboard index");
        for (const QJsonValue &v : doc.array()) {
            QJsonObject o = v.toObject(); Item it;
            it.id = o["id"].toString(); it.kind = o["kind"].toString(); it.text = o["text"].toString();
            it.w = o["w"].toInt(); it.h = o["h"].toInt(); it.bytes = qint64(o["bytes"].toDouble());
            it.ts = qint64(o["ts"].toDouble()); it.pinned = o["pinned"].toBool();
            if (!QRegularExpression(QStringLiteral("^[0-9a-f]{40}$")).match(it.id).hasMatch()
                || (it.kind != "text" && it.kind != "image")) continue;
            if (it.kind == "text") {
                Item checked;
                if (!textItem(it.text, checked) || checked.id != it.id) continue;
            } else if (!QFile::exists(imagePath(it.id))) continue;
            if (indexOf(it.id) < 0) m_items.append(it);
        }
        const auto pins = m_dir + "/../clipboard-pins.json";
        if (QFile::exists(pins)) {
            const auto old = QJsonDocument::fromJson(HistoryCipher::read(pins));
            if (!old.isArray()) throw std::runtime_error("Invalid legacy clipboard pins");
            for (const auto &value : old.array()) {
                Item item;
                if (textItem(value.toString(), item) && indexOf(item.id) < 0) {
                    item.pinned = true;
                    m_items.append(item);
                }
            }
        }
        prune();
        if (QFile::exists(legacy) || QFile::exists(pins) || !originals.isEmpty()) {
            save();
            for (const QString &name : originals)
                if (QRegularExpression("^[0-9a-f]{40}\\.png$").match(name).hasMatch() && !images.remove(name))
                    throw std::runtime_error("Cannot remove legacy clipboard image");
        }
        for (const QString &path : {legacy, pins, pins + ".migrated"})
            if (QFile::exists(path) && !QFile::remove(path))
                throw std::runtime_error("Cannot remove legacy clipboard history");
    }

    void save()
    {
        QJsonArray arr;
        for (const Item &it : std::as_const(m_items)) {
            QJsonObject o{{"id", it.id}, {"kind", it.kind}, {"ts", double(it.ts)}, {"pinned", it.pinned}};
            if (it.kind == "text") o["text"] = it.text; else { o["w"] = it.w; o["h"] = it.h; o["bytes"] = double(it.bytes); }
            arr.append(o);
        }
        cipher.seal(m_dir + "/index.enc", QJsonDocument(arr).toJson(QJsonDocument::Compact));
        Q_EMIT changed();
    }


};

int main(int argc, char **argv)
{
    umask(0077);
    QGuiApplication app(argc, argv);
    app.setApplicationName("mac-tahoe-clipd");
    app.setQuitOnLastWindowClosed(false);
    QDBusConnection bus = QDBusConnection::sessionBus();
    if (!bus.registerService("org.mactahoe.Clipboard")) return 0; // already running
    try {
        Store store;
        bus.registerObject("/Clipboard", &store, QDBusConnection::ExportAllSlots | QDBusConnection::ExportAllSignals);
        return app.exec();
    } catch (const std::exception &error) {
        qCritical("%s", error.what());
        return 1;
    }
}

#include "main.moc"
