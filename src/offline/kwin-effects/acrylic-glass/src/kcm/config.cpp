/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>
    SPDX-License-Identifier: GPL-2.0-or-later
*/
#include "config.h"
#include "glassconfig.h"
#include "presets.h"

#include "kwineffects_interface.h"
#include <KConfigGroup>
#include <KPluginFactory>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

namespace KWin {

K_PLUGIN_CLASS(LiquidGlassEffectConfig)

LiquidGlassEffectConfig::LiquidGlassEffectConfig(QObject* parent, const KPluginMetaData& data)
    : KCModule(parent, data)
{
    ui.setupUi(widget());
    const auto presets = QJsonDocument::fromJson(materialPresetsJson).array();
    int row = 0;
    for (const auto &entry : presets) {
        const int value = entry.toObject().value(QStringLiteral("value")).toInt();
        for (int variant : {0, 1}) {
            if (value == 2 && variant == 0) {
                continue; // Golden Gate clear is not offered in the selector.
            }
            ui.kcfg_MaterialPreset->setItemData(row, value);
            ui.kcfg_MaterialPreset->setItemData(row++, variant, Qt::UserRole + 1);
        }
    }
    connect(ui.kcfg_BackingTint, &QSpinBox::valueChanged,
            ui.kcfg_MaterialPreset, &PresetComboBox::setBackingTint);
    BlurConfig::instance("kwinrc");
    addConfig(BlurConfig::self(), widget());

    // Only a deliberate selection resets the material. Loading a saved preset
    // must retain its individual overrides, including after Cancel or reopening.
    connect(ui.kcfg_MaterialPreset, &QComboBox::activated, this, &LiquidGlassEffectConfig::applyPreset);
    connect(ui.resetPreset, &QPushButton::clicked, this, [this] {
        applyPreset(ui.kcfg_MaterialPreset->currentIndex());
    });
    const auto updateGradient = [this](bool enabled) {
        ui.kcfg_GradientTopColor->setEnabled(enabled);
        ui.kcfg_GradientTopDarkColor->setEnabled(enabled);
        ui.kcfg_GradientCenterColor->setEnabled(enabled);
        ui.kcfg_GradientCenterDarkColor->setEnabled(enabled);
        ui.kcfg_GradientCenterOpacity->setEnabled(enabled);
        ui.kcfg_GradientCenterPosition->setEnabled(enabled);
        ui.kcfg_GradientBottomColor->setEnabled(enabled);
        ui.kcfg_GradientBottomDarkColor->setEnabled(enabled);
        ui.kcfg_GradientTopOpacity->setEnabled(enabled);
        ui.kcfg_GradientBottomOpacity->setEnabled(enabled);
    };
    connect(ui.kcfg_DarkGradientOverlay, &QCheckBox::toggled, this, updateGradient);
    updateGradient(ui.kcfg_DarkGradientOverlay->isChecked());

    // Keep the filtering mode deterministic even if older configs had both unset.
    if (!ui.kcfg_BlurMatching->isChecked() && !ui.kcfg_BlurNonMatching->isChecked()) {
        ui.kcfg_BlurNonMatching->setChecked(true);
    }
}

LiquidGlassEffectConfig::~LiquidGlassEffectConfig() { }

void LiquidGlassEffectConfig::applyPreset(int index)
{
    const auto presets = QJsonDocument::fromJson(materialPresetsJson).array();
    if (index < 0 || index >= ui.kcfg_MaterialPreset->count()) {
        return;
    }
    const int value = ui.kcfg_MaterialPreset->itemData(index).toInt();
    const int variant = ui.kcfg_MaterialPreset->itemData(index, Qt::UserRole + 1).toInt();
    QJsonObject preset;
    for (const auto &entry : presets) {
        if (entry.toObject().value(QStringLiteral("value")).toInt() == value) {
            preset = entry.toObject();
            break;
        }
    }
    if (preset.isEmpty()) {
        return;
    }
    ui.kcfg_BackingTint->setValue(variant);
    auto values = preset.value(QStringLiteral("values")).toObject();
    if (variant) {
        const auto overrides = preset.value(QStringLiteral("tinted_values")).toObject();
        for (auto it = overrides.constBegin(); it != overrides.constEnd(); ++it) {
            values.insert(it.key(), it.value());
        }
    }
    for (auto it = values.constBegin(); it != values.constEnd(); ++it) {
        auto *control = widget()->findChild<QWidget *>(QStringLiteral("kcfg_") + it.key());
        if (auto *number = qobject_cast<QDoubleSpinBox *>(control)) {
            number->setValue(it.value().toDouble());
        } else if (auto *integer = qobject_cast<QSpinBox *>(control)) {
            integer->setValue(it.value().toInt());
        } else if (auto *toggle = qobject_cast<QCheckBox *>(control)) {
            toggle->setChecked(it.value().toBool());
        } else if (auto *color = qobject_cast<KColorButton *>(control)) {
            color->setColor(QColor(it.value().toString()));
        }
    }
}

void LiquidGlassEffectConfig::load()
{
    KCModule::load();
    const KConfigGroup group(BlurConfig::self()->config(), QStringLiteral("Effect-liquidglass"));
    // Older settings used one color in both modes. Preserve it until edited.
    if (!group.hasKey("GradientTopDarkColor")) {
        ui.kcfg_GradientTopDarkColor->setColor(ui.kcfg_GradientTopColor->color());
    }
    if (!group.hasKey("GradientCenterDarkColor")) {
        ui.kcfg_GradientCenterDarkColor->setColor(ui.kcfg_GradientCenterColor->color());
    }
    if (!group.hasKey("GradientBottomDarkColor")) {
        ui.kcfg_GradientBottomDarkColor->setColor(ui.kcfg_GradientBottomColor->color());
    }
}

void LiquidGlassEffectConfig::save()
{
    KCModule::save();

    // KConfigSkeleton removes entries equal to schema defaults. Retain the
    // selection explicitly, using stable IDs rather than combo-box positions.
    auto group = BlurConfig::self()->config()->group(QStringLiteral("Effect-liquidglass"));
    group.writeEntry("MaterialPreset", ui.kcfg_MaterialPreset->presetValue());
    group.writeEntry("GradientTopDarkColor", ui.kcfg_GradientTopDarkColor->color());
    group.writeEntry("GradientCenterDarkColor", ui.kcfg_GradientCenterDarkColor->color());
    group.writeEntry("GradientBottomDarkColor", ui.kcfg_GradientBottomDarkColor->color());
    group.sync();

    OrgKdeKwinEffectsInterface interface(QStringLiteral("org.kde.KWin"), QStringLiteral("/Effects"), QDBusConnection::sessionBus());

    if (QGuiApplication::platformName() == QStringLiteral("xcb")) {
        interface.reconfigureEffect(QStringLiteral("liquidglass_x11"));
    } else {
        interface.reconfigureEffect(QStringLiteral("liquidglass"));
    }
}

} // namespace KWin

#include "config.moc"
#include "moc_config.cpp"
