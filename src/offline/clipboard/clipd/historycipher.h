// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QDir>
#include <QFile>
#include <QSaveFile>
#include <QStandardPaths>
#include <sodium.h>
#include <stdexcept>
#include <cstring>

class HistoryCipher {
    unsigned char key[crypto_secretbox_KEYBYTES]{};
public:
    HistoryCipher() = default;
    HistoryCipher(const HistoryCipher &) = delete;
    ~HistoryCipher() { sodium_memzero(key, sizeof key); }

    static QByteArray read(const QString &path) {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly)) throw std::runtime_error("Cannot open clipboard history");
        auto data = file.readAll();
        if (file.error() != QFileDevice::NoError) throw std::runtime_error("Cannot read clipboard history");
        return data;
    }

    static void write(const QString &path, const QByteArray &data) {
        QSaveFile file(path);
        if (!file.open(QIODevice::WriteOnly) || !file.setPermissions(QFile::ReadOwner | QFile::WriteOwner)
            || file.write(data) != data.size() || !file.commit())
            throw std::runtime_error("Cannot save clipboard history");
    }

    void initialize(bool existing) {
        if (sodium_init() < 0) throw std::runtime_error("Cannot initialize clipboard encryption");
        const auto dir = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + "/mac-tahoe-liquid-kde";
        const auto path = dir + "/clipboard.key";
        if (!QFile::exists(path) && !existing) {
            if (!QDir().mkpath(dir)) throw std::runtime_error("Cannot create clipboard key directory");
            crypto_secretbox_keygen(key);
            write(path, QByteArray::fromRawData(reinterpret_cast<const char *>(key), sizeof key));
        } else {
            auto data = read(path);
            if (data.size() != sizeof key) throw std::runtime_error("Invalid clipboard key");
            memcpy(key, data.constData(), sizeof key);
            sodium_memzero(data.data(), data.size());
        }
    }

    QString imageName(const QString &id) const {
        const auto bytes = id.toLatin1();
        unsigned char digest[crypto_generichash_BYTES];
        crypto_generichash(digest, sizeof digest, reinterpret_cast<const unsigned char *>(bytes.constData()),
                           bytes.size(), key, sizeof key);
        return QString::fromLatin1(QByteArray(reinterpret_cast<const char *>(digest), sizeof digest).toHex());
    }

    void seal(const QString &path, const QByteArray &plain) const {
        QByteArray data(crypto_secretbox_NONCEBYTES + crypto_secretbox_MACBYTES + plain.size(), Qt::Uninitialized);
        auto *nonce = reinterpret_cast<unsigned char *>(data.data());
        randombytes_buf(nonce, crypto_secretbox_NONCEBYTES);
        crypto_secretbox_easy(nonce + crypto_secretbox_NONCEBYTES,
            reinterpret_cast<const unsigned char *>(plain.constData()), plain.size(), nonce, key);
        write(path, data);
    }

    QByteArray open(const QString &path) const {
        const auto data = read(path);
        const auto overhead = crypto_secretbox_NONCEBYTES + crypto_secretbox_MACBYTES;
        if (data.size() < overhead) throw std::runtime_error("Incomplete clipboard record");
        QByteArray plain(data.size() - overhead, Qt::Uninitialized);
        const auto *nonce = reinterpret_cast<const unsigned char *>(data.constData());
        if (crypto_secretbox_open_easy(reinterpret_cast<unsigned char *>(plain.data()),
            nonce + crypto_secretbox_NONCEBYTES, data.size() - crypto_secretbox_NONCEBYTES, nonce, key))
            throw std::runtime_error("Clipboard authentication failed");
        return plain;
    }
};
