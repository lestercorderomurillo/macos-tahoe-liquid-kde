/*
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/

#pragma once

#include <KUser>
#include <Plasma/Applet>
#include <QAbstractItemModel>
#include <QPointer>
#include <memory>

class QQuickItem;
class QMenu;

/**
 * Global menu applet — the macOS-style menubar that sits at the top of
 * the screen and shows the active window's File/Edit/View/etc.
 *
 * The QML side renders a horizontal strip of buttons backed by the
 * ``model`` property (a flattened MenuModel). When the user clicks a
 * top-level item we open a native QMenu rooted at that index — KMenuBar
 * style — and forward keyboard navigation back through ``trigger()``.
 *
 * Two extra menus live alongside the per-window one:
 *
 *   - ``windowMenu``: the close / minimize / maximize / move-to-screen
 *     submenu spawned from the window-title button.
 *   - ``systemMenu``: the system-wide (About this Computer / System
 *     Settings / Shutdown / …) menu.
 *
 * View mode toggles between FullView (full menubar across the panel)
 * and CompactView (single "≡" button — used when horizontal space is
 * tight).
 */
class AppMenuApplet : public Plasma::Applet
{
    Q_OBJECT

    /// Backing containment — exposed for QML to query screen / panel state.
    Q_PROPERTY(QObject* containment READ containment CONSTANT)

    /// MenuModel currently displayed. Re-assigned whenever the focused
    /// window changes.
    Q_PROPERTY(QAbstractItemModel* model READ model WRITE setModel NOTIFY modelChanged)

    /// FullView vs CompactView — see ViewType below.
    Q_PROPERTY(int view READ view WRITE setView NOTIFY viewChanged)

    /// Top-level menu index currently shown (-1 = no menu open).
    Q_PROPERTY(int currentIndex READ currentIndex NOTIFY currentIndexChanged)

    /// The QML row of menu buttons — kept as a property so the C++ side
    /// can ask for child positions when placing the popup QMenu.
    Q_PROPERTY(QQuickItem* buttonGrid READ buttonGrid WRITE setButtonGrid NOTIFY buttonGridChanged)

public:
    /// Visual mode of the applet.
    enum ViewType
    {
        FullView, ///< Full menubar (default for top panels).
        CompactView, ///< Single hamburger button (narrow contexts).
    };

    // Lifecycle

    explicit AppMenuApplet(QObject* parent, const KPluginMetaData& data, const QVariantList& args);
    ~AppMenuApplet() override;

    void init() override;

    // Property accessors

    int currentIndex() const;
    QQuickItem* buttonGrid() const;
    void setButtonGrid(QQuickItem* buttonGrid);
    QAbstractItemModel* model() const;
    void setModel(QAbstractItemModel* model);
    int view() const;
    void setView(int type);

Q_SIGNALS:
    // Property-change signals

    void modelChanged();
    void viewChanged();
    void currentIndexChanged();
    void buttonGridChanged();

    /// Fired when the user keyboards into menu index ``index`` — QML
    /// uses this to focus the corresponding button.
    void requestActivateIndex(int index);

    /// "About This Computer" menu entry selected.
    void aboutRequested();

public Q_SLOTS:
    // QML-triggered actions

    /// Pop the menu for top-level index ``idx``, anchored to ``ctx``
    /// (the QML button representing that entry).
    void trigger(QQuickItem* ctx, int idx);

    /// Open the window-title submenu (close / minimize / etc).
    void triggerWindowMenu(QQuickItem* ctx);

    /// Open the system-wide menu (About / Settings / Shutdown / …).
    void triggerSystemMenu(QQuickItem* ctx);

protected:
    /// Intercept Plasma applet events to forward keyboard navigation
    /// into the active QMenu (left/right between top-level entries).
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    /// Build the QMenu shown when the user clicks top-level index ``idx``.
    /// Returns a freshly-allocated, parent-less menu — caller owns it.
    QMenu* createMenu(int idx) const;

    void setCurrentIndex(int currentIndex);

    /// Cleanup hooks — reset currentIndex / unparent the QMenu when
    /// the popup closes so the QML highlight de-activates.
    void onMenuAboutToHide();
    void onWindowMenuAboutToHide();
    void onSystemMenuAboutToHide();

    // State

    int m_currentIndex = -1;
    int m_viewType = FullView;

    QPointer<QMenu> m_currentMenu;
    QPointer<QMenu> m_sourceMenu;
    QPointer<QQuickItem> m_buttonGrid;
    QPointer<QAbstractItemModel> m_model;

    std::unique_ptr<QMenu> m_windowMenu;
    QPointer<QMenu> m_systemMenu;

    /// Refcount tracking the number of live AppMenuApplet instances —
    /// used to lazy-init / tear down process-wide menu integration.
    static int s_refs;
};
