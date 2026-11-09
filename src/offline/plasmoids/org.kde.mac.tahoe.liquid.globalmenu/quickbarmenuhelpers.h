/*
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>
    SPDX-FileCopyrightText: 2016 Chinmoy Ranjan Pradhan <chinmoyrp65@gmail.com>
    SPDX-FileCopyrightText: 2026 QuickBar contributors
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

    Adapted from QuickBar appmenumodel.cpp at
    213a583adfd257ed420c77ef2cf1443a709a3425.
    Disabled and hidden actions are excluded from search results.
*/
#pragma once
#include <QAction>
#include <QMenu>
#include <QSet>

namespace QuickBarMenu {
inline QString visibleMenuText(const QString &text)
{
    QString out;
    out.reserve(text.size());
    for (qsizetype i = 0; i < text.size(); ++i) {
        const QChar ch = text.at(i);
        if (ch == QLatin1Char('&')) {
            if (i + 1 < text.size() && text.at(i + 1) == QLatin1Char('&')) {
                out += QLatin1Char('&');
                ++i;
            }
            continue;
        }
        out += ch;
    }
    return out;
}

inline void collectMenuActions(QMenu *menu, QList<QAction *> &result, QSet<QMenu *> &visited)
{
    if (!menu || visited.contains(menu)) {
        return;
    }
    visited.insert(menu);

    for (QAction *action : menu->actions()) {
        if (!action || action->isSeparator() || !action->isVisible() || !action->isEnabled()) {
            continue;
        }
        if (QMenu *subMenu = action->menu()) {
            collectMenuActions(subMenu, result, visited);
        } else if (!action->text().isEmpty()) {
            result.append(action);
        }
    }
}
}
