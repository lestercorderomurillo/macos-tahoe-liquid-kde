// SPDX-License-Identifier: GPL-3.0-or-later
#include <KCModule>
#include <KColorButton>
#include <KConfigGroup>
#include <KPluginFactory>
#include <KSharedConfig>
#include <QApplication>
#include <QCheckBox>
#include <QClipboard>
#include <QComboBox>
#include <QDoubleSpinBox>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPushButton>
#include <QSpinBox>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <memory>

static void require(bool ok, const QString &message)
{
    if (!ok) {
        fprintf(stderr, "%s\n", qPrintable(message));
        std::exit(1);
    }
}

template <class T> static T *control(KCModule *module, const QString &name)
{
    auto *result = module->widget()->findChild<T *>(name);
    require(result, name + QStringLiteral(" missing"));
    return result;
}

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    // Offscreen has no clipboard owner; KColorButton expects MIME data.
    app.clipboard()->setText(QString());
    require(argc == 5, QStringLiteral("plugin, preset JSON, saved selection and tint required"));
    QFile input(QString::fromLocal8Bit(argv[2]));
    require(input.open(QIODevice::ReadOnly), QStringLiteral("presets unreadable"));
    const auto presets = QJsonDocument::fromJson(input.readAll()).array();
    auto defaults = presets.at(0).toObject().value(QStringLiteral("values")).toObject();
    defaults.insert(QStringLiteral("BlurDecorations"), true);
    auto config = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    KConfigGroup group(config, QStringLiteral("Effect-liquidglass"));
    const QString savedPreset = QString::fromLocal8Bit(argv[3]);
    if (savedPreset != QStringLiteral("absent")) {
        group.writeEntry("MaterialPreset", savedPreset.toInt());
        group.writeEntry("BlurStrength", 6.25);
    }
    const int savedTint = QString::fromLocal8Bit(argv[4]).toInt();
    group.writeEntry("BackingTint", savedTint);
    group.writeEntry("WindowCornerRadius", 13.5);
    group.writeEntry("WindowClasses", "preserved-app");
    group.writeEntry("MaterialOpacity", 0.0); // Retired opacity must not hide the glass.
    group.writeEntry("AcrylicGlassType", 2); // Retired settings cannot select another kernel.
    config->sync();
    const KPluginMetaData meta(QString::fromLocal8Bit(argv[1]));
    auto open = [&] {
        auto result = KPluginFactory::instantiatePlugin<KCModule>(meta);
        require(bool(result), result.errorString);
        auto module = std::unique_ptr<KCModule>(result.plugin);
        module->load();
        return module;
    };
    auto module = open();
    const auto capture = qEnvironmentVariable("GLASS_KCM_CAPTURE");
    if (!capture.isEmpty()) {
        if (qEnvironmentVariableIsSet("GLASS_KCM_CAPTURE_PRESET")) {
            auto *selection = control<QComboBox>(module.get(), QStringLiteral("kcfg_MaterialPreset"));
            const int index = qEnvironmentVariableIntValue("GLASS_KCM_CAPTURE_PRESET");
            selection->setCurrentIndex(index);
            selection->activated(index);
        }
        module->widget()->resize(620, 700);
        module->widget()->show();
        app.processEvents();
        require(module->widget()->grab().save(capture), QStringLiteral("capture failed"));
        module->load();
    }
    auto *selector = control<QComboBox>(module.get(), QStringLiteral("kcfg_MaterialPreset"));
    require(selector->count() == 3, QStringLiteral("exactly three appearances"));
    require(selector->itemText(0) == QStringLiteral("Tahoe (Clear)") && selector->itemText(1) == QStringLiteral("Tahoe (Frosted)")
            && selector->itemText(2) == QStringLiteral("Golden Gate (Official)"),
            QStringLiteral("Golden Gate clear must not be offered"));
    require(selector->currentIndex() == (savedPreset == QStringLiteral("2") ? 2 : savedTint),
            QStringLiteral("saved preset identity changed"));
    require(control<QDoubleSpinBox>(module.get(), QStringLiteral("kcfg_BlurStrength"))->value()
                == (savedPreset == QStringLiteral("absent") ? defaults["BlurStrength"].toDouble() : 6.25),
            QStringLiteral("loading changed saved optics"));
    require(!module->widget()->findChild<QWidget *>(QStringLiteral("kcfg_AcrylicGlassType")), QStringLiteral("blur type must be removed"));
    require(!module->widget()->findChild<QWidget *>(QStringLiteral("kcfg_MaterialOpacity")), QStringLiteral("glass opacity must be removed"));
    const auto verifyControls = [&](const QJsonObject &values) {
        for (auto it = values.constBegin(); it != values.constEnd(); ++it) {
            const auto name = QStringLiteral("kcfg_") + it.key();
            auto *widget = control<QWidget>(module.get(), name);
            if (auto *number = qobject_cast<QDoubleSpinBox *>(widget))
                require(std::abs(number->value() - it.value().toDouble()) < 0.00001, name);
            else if (auto *integer = qobject_cast<QSpinBox *>(widget))
                require(integer->value() == it.value().toInt(), name);
            else if (auto *toggle = qobject_cast<QCheckBox *>(widget))
                require(toggle->isChecked() == it.value().toBool(), name);
            else if (auto *color = qobject_cast<KColorButton *>(widget))
                require(color->color() == QColor(it.value().toString()), name);
            else require(false, name + QStringLiteral(" unknown control type"));
        }
    };
    // A fresh KCM must show the same optics as installing or restoring Tahoe.
    // KConfig omits default-valued keys, so every material control matters.
    if (savedPreset == QStringLiteral("absent")) {
        verifyControls(defaults);
    }
    require(!module->widget()->findChild<QWidget *>(QStringLiteral("kcfg_BackgroundColor")), QStringLiteral("flat background color must be removed"));
    require(!module->widget()->findChild<QWidget *>(QStringLiteral("kcfg_BackgroundAutomatic")), QStringLiteral("automatic toggle must be removed"));
    require(!module->widget()->findChild<QWidget *>(QStringLiteral("kcfg_BackgroundOpacity")), QStringLiteral("flat background opacity must be removed"));
    require(control<QSpinBox>(module.get(), QStringLiteral("kcfg_BackingTint"))->isHidden(),
            QStringLiteral("legacy preset identity must not expose a background toggle"));
    for (int i : {1, 2, 0}) {
        selector->setCurrentIndex(i);
        selector->activated(i);
        auto values = presets.at(i == 2 ? 1 : 0).toObject().value(QStringLiteral("values")).toObject();
        if (i != 0) {
            values.insert(QStringLiteral("BlurStrength"), 12.0);
            values.insert(QStringLiteral("MagnifyGlassStrength"), 0.02);
            values.insert(QStringLiteral("RgbDriftStrength"), 10.0);
            values.insert(QStringLiteral("RefractionWidth"), 38.0);
            values.insert(QStringLiteral("HighlightWidth"), 16.0);
            values.insert(QStringLiteral("NoiseStrength"), 0);
            values.insert(QStringLiteral("BlurDecorations"), true);
            if (i == 2) {
                values.insert(QStringLiteral("DarkGradientOverlay"), true);
                values.insert(QStringLiteral("BlurStrength"), 4.0);
                values.insert(QStringLiteral("MagnifyGlassStrength"), 0.032);
                values.insert(QStringLiteral("RgbDriftStrength"), 8.0);
                values.insert(QStringLiteral("RefractionWidth"), 64.0);
                values.insert(QStringLiteral("Brightness"), 1.1);
                values.insert(QStringLiteral("Contrast"), 1.0);
                values.insert(QStringLiteral("Saturation"), 1.13);
                for (const QString stop : {QStringLiteral("Top"), QStringLiteral("Center"), QStringLiteral("Bottom")}) {
                    values.insert("Gradient" + stop + "Color", QStringLiteral("#cecece"));
                }
                values.insert(QStringLiteral("GradientTopOpacity"), 1.0);
                values.insert(QStringLiteral("GradientCenterOpacity"), 0.69);
                values.insert(QStringLiteral("GradientCenterPosition"), 0.56);
                values.insert(QStringLiteral("GradientBottomOpacity"), 0.0);
            }
        }
        verifyControls(values);
        require(control<QSpinBox>(module.get(), QStringLiteral("kcfg_BackingTint"))->value() == (i != 0 ? 1 : 0), QStringLiteral("preset background state"));
        control<QPushButton>(module.get(), QStringLiteral("resetPreset"))->click();
        verifyControls(values);
        module->save();
        config->reparseConfiguration();
        require(group.readEntry("MaterialPreset", -1) == presets.at(i == 2 ? 1 : 0).toObject()["value"].toInt(),
                QStringLiteral("saved preset ID changed"));
        for (auto it = values.constBegin(); it != values.constEnd(); ++it) {
            if (it.value().isDouble())
                require(std::abs(group.readEntry(it.key(), defaults.value(it.key()).toDouble()) - it.value().toDouble()) < 0.00001, it.key() + QStringLiteral(" not saved"));
            else if (it.value().isBool())
                require(group.readEntry(it.key(), defaults.value(it.key()).toBool()) == it.value().toBool(), it.key());
            else require(group.readEntry(it.key(), QColor(defaults.value(it.key()).toString())) == QColor(it.value().toString()), it.key());
        }
        module.reset();
        module = open();
        selector = control<QComboBox>(module.get(), QStringLiteral("kcfg_MaterialPreset"));
        require(selector->currentIndex() == i, QStringLiteral("reopening changed selected preset"));
        verifyControls(values);
        require(control<QSpinBox>(module.get(), QStringLiteral("kcfg_BackingTint"))->value() == (i != 0 ? 1 : 0),
                QStringLiteral("appearance or reopening lost the backing tint"));
    }
    auto *blur = control<QDoubleSpinBox>(module.get(), QStringLiteral("kcfg_BlurStrength"));
    blur->setValue(8.25);
    auto *color = control<KColorButton>(module.get(), QStringLiteral("kcfg_GradientTopColor"));
    color->setColor(QColor("#265a81"));
    module->save();
    module.reset();
    module = open();
    require(control<QDoubleSpinBox>(module.get(), QStringLiteral("kcfg_BlurStrength"))->value() == 8.25, QStringLiteral("reopening resets overrides"));
    require(control<KColorButton>(module.get(), QStringLiteral("kcfg_GradientTopColor"))->color() == QColor("#265a81"), QStringLiteral("custom color lost"));
    selector = control<QComboBox>(module.get(), QStringLiteral("kcfg_MaterialPreset"));
    selector->setCurrentIndex(1);
    selector->activated(1);
    module->load(); // Cancel discards pending preset changes.
    require(control<QDoubleSpinBox>(module.get(), QStringLiteral("kcfg_BlurStrength"))->value() == 8.25, QStringLiteral("cancel failed"));
    require(selector->currentIndex() == 0, QStringLiteral("cancel retained preset"));
    control<QPushButton>(module.get(), QStringLiteral("resetPreset"))->click();
    require(control<QDoubleSpinBox>(module.get(), QStringLiteral("kcfg_BlurStrength"))->value() == defaults["BlurStrength"].toDouble(), QStringLiteral("restore preset failed"));
    require(control<QDoubleSpinBox>(module.get(), QStringLiteral("kcfg_WindowCornerRadius"))->value() == 13.5, QStringLiteral("preset reset corners"));
    module->save();
    config->reparseConfiguration();
    require(group.readEntry("WindowClasses", QString()) == QStringLiteral("preserved-app"), QStringLiteral("preset reset rules"));
    for (const QString stop : {QStringLiteral("Top"), QStringLiteral("Center"), QStringLiteral("Bottom")}) {
        auto *light = control<KColorButton>(module.get(), "kcfg_Gradient" + stop + "Color");
        auto *dark = control<KColorButton>(module.get(), "kcfg_Gradient" + stop + "DarkColor");
        light->setColor(QColor("#ffeecc"));
        dark->setColor(QColor("#123456"));
    }
    control<QCheckBox>(module.get(), QStringLiteral("kcfg_DarkGradientOverlay"))->setChecked(false);
    module->save();
    module.reset();
    module = open();
    for (const QString stop : {QStringLiteral("Top"), QStringLiteral("Center"), QStringLiteral("Bottom")}) {
        auto *light = control<KColorButton>(module.get(), "kcfg_Gradient" + stop + "Color");
        auto *dark = control<KColorButton>(module.get(), "kcfg_Gradient" + stop + "DarkColor");
        require(light->color() == QColor("#ffeecc") && dark->color() == QColor("#123456"),
                QStringLiteral("mode colors must persist independently"));
        require(!light->isEnabled() && !dark->isEnabled(), QStringLiteral("disabled gradient has active colors"));
    }
    module.reset();
    config->reparseConfiguration();
    for (const QString stop : {QStringLiteral("Top"), QStringLiteral("Center"), QStringLiteral("Bottom")}) {
        group.deleteEntry("Gradient" + stop + "DarkColor");
    }
    group.writeEntry("BackgroundAutomatic", false);
    group.writeEntry("BackgroundColor", QColor(Qt::red));
    group.writeEntry("BackgroundOpacity", 0.99);
    group.sync();
    module = open();
    for (const QString stop : {QStringLiteral("Top"), QStringLiteral("Center"), QStringLiteral("Bottom")}) {
        auto *dark = control<KColorButton>(module.get(), "kcfg_Gradient" + stop + "DarkColor");
        require(dark->color() == QColor("#ffeecc"), QStringLiteral("legacy color must survive in both modes"));
        dark->setColor(QColor(Qt::black));
    }
    module->save();
    module.reset();
    module = open();
    for (const QString stop : {QStringLiteral("Top"), QStringLiteral("Center"), QStringLiteral("Bottom")}) {
        require(control<KColorButton>(module.get(), "kcfg_Gradient" + stop + "DarkColor")->color() == QColor(Qt::black),
                QStringLiteral("explicit default black must not fall back to legacy light color"));
    }
    fprintf(stderr, "Material presets, custom color, save/reopen, cancel and restore verified\n");
}
