/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>
    SPDX-License-Identifier: GPL-2.0-or-later
*/
#include "blur_config.h"
#include "blurconfig.h"

#include <KPluginFactory>
#include "kwineffects_interface.h"

namespace KWin
{

K_PLUGIN_CLASS(LiquidGlassEffectConfig)

LiquidGlassEffectConfig::LiquidGlassEffectConfig(QObject *parent, const KPluginMetaData &data)
    : KCModule(parent, data)
{
    ui.setupUi(widget());
    BlurConfig::instance("kwinrc");
    addConfig(BlurConfig::self(), widget());

    connect(ui.presetCombo, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &LiquidGlassEffectConfig::applyPreset);
}

LiquidGlassEffectConfig::~LiquidGlassEffectConfig()
{
}

void LiquidGlassEffectConfig::applyPreset(int index)
{
    // Clear = 3, Frosted = 12
    const int blurValues[] = { 3, 12 };
    if (index < 0 || index >= 2) return;

    BlurConfig::setBlurStrength(blurValues[index]);
    BlurConfig::setNoiseStrength(0);
    BlurConfig::self()->save();

    markAsChanged();
}

void LiquidGlassEffectConfig::save()
{
    KCModule::save();

    OrgKdeKwinEffectsInterface interface(QStringLiteral("org.kde.KWin"),
                                         QStringLiteral("/Effects"),
                                         QDBusConnection::sessionBus());

    if (QGuiApplication::platformName() == QStringLiteral("xcb")) {
        interface.reconfigureEffect(QStringLiteral("liquidglass_x11"));
    } else {
        interface.reconfigureEffect(QStringLiteral("liquidglass"));
    }
}

} // namespace KWin

#include "blur_config.moc"
#include "moc_blur_config.cpp"
