/*
    SPDX-FileCopyrightText: 2013 Aurélien Gâteau <agateau@kde.org>
    SPDX-FileCopyrightText: 2013-2015 Eike Hein <hein@kde.org>
    SPDX-FileCopyrightText: 2017 Ivan Cukic <ivan.cukic@kde.org>
    SPDX-FileCopyrightText: 2022 ivan tkachenko <me@ratijas.tk>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

const defaultIconName = "start-here-kde-symbolic";

function iconOrDefault(formFactor, preferredIconName) {
    return (formFactor === PlasmaCore.Types.Vertical && preferredIconName === "")
        ? defaultIconName : preferredIconName;
}
