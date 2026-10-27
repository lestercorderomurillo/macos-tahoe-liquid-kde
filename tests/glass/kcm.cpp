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
    require(argc == 4, QStringLiteral("plugin, preset JSON and saved selection required"));
    QFile input(QString::fromLocal8Bit(argv[2]));
    require(input.open(QIODevice::ReadOnly), QStringLiteral("presets unreadable"));
    const auto presets = QJsonDocument::fromJson(input.readAll()).array();
    const auto defaults = presets.at(0).toObject().value(QStringLiteral("values")).toObject();
    auto config = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    KConfigGroup group(config, QStringLiteral("Effect-liquidglass"));
    const QString savedPreset = QString::fromLocal8Bit(argv[3]);
    if (savedPreset != QStringLiteral("absent")) {
        group.writeEntry("MaterialPreset", savedPreset.toInt());
        group.writeEntry("BlurStrength", 6.25);
    }
    group.writeEntry("WindowCornerRadius", 13.5);
    group.writeEntry("WindowClasses", "preserved-app");
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
    auto *selector = control<QComboBox>(module.get(), QStringLiteral("kcfg_MaterialPreset"));
    require(selector->count() == 2, QStringLiteral("exactly two presets"));
    require(selector->itemText(0) == QStringLiteral("Tahoe") && selector->itemText(1) == QStringLiteral("Golden Gate"),
            QStringLiteral("only Tahoe and Golden Gate are available"));
    require(selector->currentIndex() == (savedPreset == QStringLiteral("2") ? 1 : 0),
            QStringLiteral("saved preset identity changed"));
    require(control<QDoubleSpinBox>(module.get(), QStringLiteral("kcfg_BlurStrength"))->value()
                == (savedPreset == QStringLiteral("absent") ? defaults["BlurStrength"].toDouble() : 6.25),
            QStringLiteral("loading changed saved optics"));
    require(!module->widget()->findChild<QWidget *>(QStringLiteral("kcfg_AcrylicGlassType")), QStringLiteral("blur type must be removed"));
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
    for (int i : {1, 0}) {
        selector->setCurrentIndex(i);
        selector->activated(i);
        const auto values = presets.at(i).toObject().value(QStringLiteral("values")).toObject();
        verifyControls(values);
        module->save();
        config->reparseConfiguration();
        require(group.readEntry("MaterialPreset", -1) == presets.at(i).toObject()["value"].toInt(),
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
    fprintf(stderr, "Material presets, custom color, save/reopen, cancel and restore verified\n");
}
