/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include "ui_blur_config.h"
#include <KCModule>
#include <QWidget>

namespace KWin
{

class LiquidGlassEffectConfig : public KCModule
{
    Q_OBJECT

public:
    explicit LiquidGlassEffectConfig(QObject *parent, const KPluginMetaData &data);
    ~LiquidGlassEffectConfig() override;

    void save() override;

private:
    void applyPreset(int index);
    ::Ui::BlurEffectConfig ui;
};

} // namespace KWin
