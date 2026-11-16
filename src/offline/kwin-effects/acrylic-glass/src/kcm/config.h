/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include "ui_config.h"
#include <KCModule>
#include <QWidget>
#include <QJsonObject>
#include <QMap>
#include <QComboBox>

namespace KWin {

class LiquidGlassEffectConfig : public KCModule
{
    Q_OBJECT

public:
    explicit LiquidGlassEffectConfig(QObject* parent, const KPluginMetaData& data);
    ~LiquidGlassEffectConfig() override;

    void load() override;
    void save() override;
    void defaults() override;

private:
    void applyPreset(int index);
    void selectComponent(int index);
    void captureComponent();
    void showComponent();
    QJsonObject controls() const;
    QJsonObject presetAt(int index) const;
    QString component() const;
    QString profileKey(int index) const;
    QComboBox *m_componentSelector = nullptr;
    QJsonObject m_materials;
    QJsonObject m_profiles;
    int m_activePresetIndex = 0;
    QMap<QString, QWidget *> m_controls;
    bool m_loading = false;
    int m_componentIndex = 0;
    ::Ui::GlassEffectConfig ui;
};

} // namespace KWin
