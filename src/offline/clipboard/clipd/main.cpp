// SPDX-License-Identifier: GPL-3.0-or-later
// mac-tahoe-clipd: records clipboard text and images, serves them to the clipboard popup over D-Bus.
#include <QBuffer>
#include <QCryptographicHash>
#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusReply>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMimeData>
#include <QSaveFile>
#include <QStandardPaths>
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
        QDir().mkpath(m_dir + "/images");
        QFile::setPermissions(m_dir, QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner);
        load();
        m_debounce.setSingleShot(true);
        m_debounce.setInterval(90);
        connect(&m_debounce, &QTimer::timeout, this, &Store::capture);
        connect(KSystemClipboard::instance(), &KSystemClipboard::changed, this, [this](QClipboard::Mode mode) {
            if (mode == QClipboard::Clipboard)
                m_debounce.start();
        });
        if (m_items.isEmpty())
            seedFromKlipper();
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
            else { o["w"] = it.w; o["h"] = it.h; o["bytes"] = double(it.bytes); o["path"] = imagePath(it.id); }
            arr.append(o);
        }
        return QString::fromUtf8(QJsonDocument(arr).toJson(QJsonDocument::Compact));
    }

    QString currentId()
    {
        Item it;
        return build(KSystemClipboard::instance()->mimeData(QClipboard::Clipboard), it, nullptr) ? it.id : QString();
    }

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
            QImage img(imagePath(id), "PNG");
            if (img.isNull()) { delete md; return; }
            QByteArray png; QBuffer buf(&png); buf.open(QIODevice::WriteOnly); img.save(&buf, "PNG");
            md->setImageData(img);
            md->setData("image/png", png);
        }
        KSystemClipboard::instance()->setMimeData(md, QClipboard::Clipboard);
        save();
    }

    void remove(const QString &id)
    {
        int i = indexOf(id);
        if (i < 0) return;
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
    QString m_dir;
    QList<Item> m_items; // newest first
    QTimer m_debounce;

    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    QString imagePath(const QString &id) const { return m_dir + "/images/" + id + ".png"; }
    int indexOf(const QString &id) const
    {
        for (int i = 0; i < m_items.size(); ++i)
            if (m_items.at(i).id == id) return i;
        return -1;
    }
    void dropFiles(const Item &it) { if (it.kind == "image") QFile::remove(imagePath(it.id)); }

    static bool textItem(const QString &text, Item &out)
    {
        if (text.trimmed().isEmpty() || text.toUtf8().size() > kMaxText) return false;
        out.kind = "text"; out.text = text;
        out.id = QString::fromLatin1(QCryptographicHash::hash("txt" + text.toUtf8(), QCryptographicHash::Sha1).toHex());
        out.ts = now();
        return true;
    }

    // Build an Item from clipboard data; pngOut receives the encoded PNG for images.
    bool build(const QMimeData *md, Item &it, QByteArray *pngOut)
    {
        if (!md || md->hasFormat("x-kde-passwordManagerHint")) return false; // never record secrets
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
        if (md->hasText()) return textItem(md->text(), it);
        return false;
    }

    void capture()
    {
        Item it; QByteArray png;
        if (!build(KSystemClipboard::instance()->mimeData(QClipboard::Clipboard), it, &png)) return;
        if (it.kind == "image" && !QFile::exists(imagePath(it.id))) {
            QSaveFile f(imagePath(it.id));
            if (!f.open(QIODevice::WriteOnly)) return;
            f.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
            f.write(png); f.commit();
        }
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
        QFile f(m_dir + "/index.json");
        if (!f.open(QIODevice::ReadOnly)) return;
        for (const QJsonValue &v : QJsonDocument::fromJson(f.readAll()).array()) {
            QJsonObject o = v.toObject(); Item it;
            it.id = o["id"].toString(); it.kind = o["kind"].toString(); it.text = o["text"].toString();
            it.w = o["w"].toInt(); it.h = o["h"].toInt(); it.bytes = qint64(o["bytes"].toDouble());
            it.ts = qint64(o["ts"].toDouble()); it.pinned = o["pinned"].toBool();
            if (it.id.isEmpty() || (it.kind == "image" && !QFile::exists(imagePath(it.id)))) continue;
            m_items.append(it);
        }
    }

    void save()
    {
        QJsonArray arr;
        for (const Item &it : std::as_const(m_items)) {
            QJsonObject o{{"id", it.id}, {"kind", it.kind}, {"ts", double(it.ts)}, {"pinned", it.pinned}};
            if (it.kind == "text") o["text"] = it.text; else { o["w"] = it.w; o["h"] = it.h; o["bytes"] = double(it.bytes); }
            arr.append(o);
        }
        QSaveFile f(m_dir + "/index.json");
        if (f.open(QIODevice::WriteOnly)) {
            f.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
            f.write(QJsonDocument(arr).toJson(QJsonDocument::Compact)); f.commit();
        }
        Q_EMIT changed();
    }

    void seedFromKlipper()
    {
        QDBusInterface k("org.kde.klipper", "/klipper", "org.kde.klipper.klipper", QDBusConnection::sessionBus());
        if (!k.isValid()) return;
        QDBusReply<QStringList> r = k.call("getClipboardHistoryMenu");
        if (!r.isValid()) return;
        const QStringList texts = r.value();
        qint64 t = now() - texts.size() * 1000;
        for (int i = texts.size() - 1; i >= 0; --i) { // oldest first so the newest ends on top
            Item it;
            if (!textItem(texts.at(i), it)) continue; // image placeholders ("▨ WxH") are not text
            if (texts.at(i).startsWith(QChar(0x25A8)) && texts.at(i).size() < 24) continue;
            it.ts = t; t += 1000;
            insert(it);
        }
        save();
    }
};

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    app.setApplicationName("mac-tahoe-clipd");
    app.setQuitOnLastWindowClosed(false);
    QDBusConnection bus = QDBusConnection::sessionBus();
    if (!bus.registerService("org.mactahoe.Clipboard")) return 0; // already running
    Store store;
    bus.registerObject("/Clipboard", &store, QDBusConnection::ExportAllSlots | QDBusConnection::ExportAllSignals);
    return app.exec();
}

#include "main.moc"
