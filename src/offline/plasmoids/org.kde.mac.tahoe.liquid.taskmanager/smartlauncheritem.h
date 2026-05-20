/*
    SPDX-FileCopyrightText: 2016, 2019 Kai Uwe Broulik <kde@privat.broulik.de>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include <QObject>
#include <QUrl>
#include <QWeakPointer>
#include <qqmlregistration.h>

#include "smartlauncherbackend.h"

namespace SmartLauncher {

/**
 * Per-launcher SmartLauncher state exposed to QML.
 *
 * Each task icon owns one Item — the Item subscribes to the singleton
 * Backend for updates about its specific ``launcherUrl`` (the .desktop
 * URL of the app). Count / progress / urgent come from the Unity-style
 * dbus protocol the Backend listens to.
 *
 * Backend is shared across all Items via a weak_ptr — created lazily
 * on the first Item, destroyed when the last Item goes away.
 */
class Item : public QObject
{
    Q_OBJECT
    QML_NAMED_ELEMENT(SmartLauncherItem)

    /// .desktop URL identifying the app this item tracks.
    Q_PROPERTY(QUrl launcherUrl READ launcherUrl WRITE setLauncherUrl NOTIFY launcherUrlChanged)

    /// Numeric badge value (e.g. unread mail count). Renders only when
    /// ``countVisible`` is also true.
    Q_PROPERTY(int count READ count NOTIFY countChanged)
    Q_PROPERTY(bool countVisible READ countVisible NOTIFY countVisibleChanged)

    /// Progress bar value 0..100. Renders only when
    /// ``progressVisible`` is also true.
    Q_PROPERTY(int progress READ progress NOTIFY progressChanged)
    Q_PROPERTY(bool progressVisible READ progressVisible NOTIFY progressVisibleChanged)

    /// "Needs attention" flag — QML usually wobbles the icon.
    Q_PROPERTY(bool urgent READ urgent NOTIFY urgentChanged)

public:
    explicit Item(QObject* parent = nullptr);
    ~Item() override = default;

    // Property getters / setters

    QUrl launcherUrl() const;
    void setLauncherUrl(const QUrl& launcherUrl);

    int count() const;
    bool countVisible() const;
    int progress() const;
    bool progressVisible() const;
    bool urgent() const;

Q_SIGNALS:
    // Property-change signals

    void launcherUrlChanged(const QUrl& launcherUrl);

    void countChanged(int count);
    void countVisibleChanged(bool countVisible);
    void progressChanged(int progress);
    void progressVisibleChanged(bool progressVisible);
    void urgentChanged(bool urgent);

private:
    /// Lazily attach to the shared Backend and start listening for
    /// updates. Called from setLauncherUrl on first non-empty URL.
    void init();

    /// Pull the current values out of Backend's cache (the launcher
    /// may already have received updates before we connected) and emit
    /// the right *Changed signals.
    void populate();

    /// Reset to zero and emit *Changed for everything — used on
    /// launcher-URL clear or when the underlying app goes away.
    void clear();

    void setCount(int count);
    void setCountVisible(bool countVisible);
    void setProgress(int progress);
    void setProgressVisible(bool progressVisible);
    void setUrgent(bool urgent);

    // Shared Backend (created lazily, ref-counted)

    static std::weak_ptr<Backend> s_backend;
    std::shared_ptr<Backend> m_backendPtr;

    // Per-Item state

    QUrl m_launcherUrl;
    QString m_storageId;

    bool m_inited = false;

    int m_count = 0;
    bool m_countVisible = false;
    int m_progress = 0;
    bool m_progressVisible = false;
    bool m_urgent = false;
};

} // namespace SmartLauncher
