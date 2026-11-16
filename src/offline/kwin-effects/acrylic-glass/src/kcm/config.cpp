/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>
    SPDX-License-Identifier: GPL-2.0-or-later
*/
#include "config.h"
#include "glassconfig.h"
#include "presets.h"
#include "../componentmaterials.h"
#include <KLocalizedString>
#include <QFormLayout>
#include <QProcess>
#include <QStandardPaths>
#include <QDir>
#include <QLabel>
#include <QDBusMessage>
#include <QSignalBlocker>

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
    m_componentSelector = new QComboBox(widget());
    m_componentSelector->setObjectName(QStringLiteral("componentSelector"));
    const QStringList labels = {i18n("General windows"), i18n("Finder"), i18n("Menus / Shell"),
        i18n("Other Plasma popups"), i18n("Apps + Clipboard"), i18n("Search capsule"),
        i18n("Control Center"), i18n("About This Computer"), i18n("Dock"), i18n("Menu bar")};
    for (int i = 0; i < GlassMaterials::components.size(); ++i)
        m_componentSelector->addItem(labels.at(i), GlassMaterials::components.at(i));
    ui.presetGroupForm->addRow(i18n("Component"), m_componentSelector);
    auto *error = new QLabel(widget());
    error->setObjectName(QStringLiteral("applyError"));
    error->setWordWrap(true);
    error->hide();
    ui.presetGroupForm->addRow(error);
    for (const auto &entry : {QStringLiteral("BlurCoverage"), QStringLiteral("SurfaceTransparencyLight"), QStringLiteral("SurfaceTransparencyDark")}) {
        auto *number = new QDoubleSpinBox(widget());
        number->setObjectName(QStringLiteral("kcfg_") + entry);
        number->setDecimals(2);
        if (entry == QStringLiteral("BlurCoverage")) {
            number->setRange(0, 1);
            number->setSingleStep(.01);
            number->setToolTip(i18n("Amount of blurred backdrop in the centre. 1 keeps full blur; lower values reveal more sharp background."));
            ui.surfaceGroupForm->addRow(i18n("Blur coverage"), number);
        } else {
            number->setRange(0, 100);
            number->setSuffix(QStringLiteral(" %"));
            number->setToolTip(i18n("Background transparency only. 0% is opaque; 100% is transparent. Text, borders and icons stay intact."));
            ui.surfaceGroupForm->addRow(entry.endsWith(QStringLiteral("Light")) ? i18n("Transparency — light") : i18n("Transparency — dark"), number);
        }
    }
    const auto keys = presetAt(0).value(QStringLiteral("values")).toObject().keys();
    for (const auto &key : keys) {
        if (key == QStringLiteral("BlurDecorations")) continue;
        auto *control = widget()->findChild<QWidget *>(QStringLiteral("kcfg_") + key);
        if (!control) continue;
        m_controls.insert(key, control);
        // The component editor is transactional and must not bind its current
        // component's values to the historical global KConfigSkeleton keys.
        control->setObjectName(QStringLiteral("component_") + key);
    }
    BlurConfig::instance("kwinrc");
    addConfig(BlurConfig::self(), widget());
    for (auto it = m_controls.begin(); it != m_controls.end(); ++it) {
        auto *control = it.value();
        control->setObjectName(QStringLiteral("kcfg_") + it.key());
        const auto changed = [this] { if (!m_loading) { captureComponent(); setNeedsSave(true); } };
        if (auto *number = qobject_cast<QDoubleSpinBox *>(control)) connect(number, &QDoubleSpinBox::valueChanged, this, changed);
        else if (auto *integer = qobject_cast<QSpinBox *>(control)) connect(integer, &QSpinBox::valueChanged, this, changed);
        else if (auto *toggle = qobject_cast<QCheckBox *>(control)) connect(toggle, &QCheckBox::toggled, this, changed);
        else if (auto *color = qobject_cast<KColorButton *>(control)) connect(color, &KColorButton::changed, this, changed);
    }
    connect(m_componentSelector, &QComboBox::currentIndexChanged, this, &LiquidGlassEffectConfig::selectComponent);

    // Presets retain their own component edits. Only Restore resets a preset;
    // switching selection and Cancel remain purely in-memory operations.
    connect(ui.kcfg_MaterialPreset, &QComboBox::activated, this, &LiquidGlassEffectConfig::applyPreset);
    connect(ui.resetPreset, &QPushButton::clicked, this, [this] {
        const int index = ui.kcfg_MaterialPreset->currentIndex();
        m_materials = GlassMaterials::defaults(presetAt(index), index != 0);
        m_profiles[profileKey(index)] = m_materials;
        showComponent();
        setNeedsSave(true);
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
    captureComponent();
    if (!m_materials.isEmpty()) m_profiles[profileKey(m_activePresetIndex)] = m_materials;
    m_activePresetIndex = index;
    ui.kcfg_BackingTint->setValue(variant);
    m_materials = GlassMaterials::defaults(preset, variant != 0);
    const auto saved = m_profiles.value(profileKey(index)).toObject();
    for (const auto &component : GlassMaterials::components)
        m_materials[component] = GlassMaterials::merge(m_materials.value(component).toObject(), saved.value(component).toObject());
    showComponent();
    setNeedsSave(true);
}

QJsonObject LiquidGlassEffectConfig::presetAt(int index) const
{
    const auto presets = QJsonDocument::fromJson(materialPresetsJson).array();
    return presets.at(index == 2 ? 1 : 0).toObject();
}

QString LiquidGlassEffectConfig::profileKey(int index) const
{
    return QString::number(ui.kcfg_MaterialPreset->itemData(index).toInt()) + QLatin1Char(':')
        + QString::number(ui.kcfg_MaterialPreset->itemData(index, Qt::UserRole + 1).toInt());
}

QString LiquidGlassEffectConfig::component() const
{
    return m_componentSelector->itemData(m_componentIndex).toString();
}

QJsonObject LiquidGlassEffectConfig::controls() const
{
    QJsonObject values;
    for (auto it = m_controls.begin(); it != m_controls.end(); ++it) {
        if (auto *number = qobject_cast<QDoubleSpinBox *>(it.value())) values[it.key()] = number->value();
        else if (auto *integer = qobject_cast<QSpinBox *>(it.value())) values[it.key()] = integer->value();
        else if (auto *toggle = qobject_cast<QCheckBox *>(it.value())) values[it.key()] = toggle->isChecked();
        else if (auto *color = qobject_cast<KColorButton *>(it.value())) values[it.key()] = color->color().name(QColor::HexRgb);
    }
    return values;
}

void LiquidGlassEffectConfig::captureComponent()
{
    if (!m_loading && !m_materials.isEmpty())
        m_materials[component()] = GlassMaterials::merge(m_materials.value(component()).toObject(), controls());
}

void LiquidGlassEffectConfig::showComponent()
{
    m_loading = true;
    const auto values = m_materials.value(component()).toObject();
    for (auto it = m_controls.begin(); it != m_controls.end(); ++it) {
        const auto value = values.value(it.key());
        if (auto *number = qobject_cast<QDoubleSpinBox *>(it.value())) number->setValue(value.toDouble());
        else if (auto *integer = qobject_cast<QSpinBox *>(it.value())) integer->setValue(value.toInt());
        else if (auto *toggle = qobject_cast<QCheckBox *>(it.value())) toggle->setChecked(value.toBool());
        else if (auto *color = qobject_cast<KColorButton *>(it.value())) color->setColor(QColor(value.toString()));
    }
    m_loading = false;
}

void LiquidGlassEffectConfig::selectComponent(int index)
{
    captureComponent();
    m_componentIndex = index;
    showComponent();
}

void LiquidGlassEffectConfig::load()
{
    KCModule::load();
    const KConfigGroup group(BlurConfig::self()->config(), QStringLiteral("Effect-liquidglass"));
    const int index = ui.kcfg_MaterialPreset->currentIndex();
    m_activePresetIndex = index;
    m_profiles = QJsonDocument::fromJson(group.readEntry("ComponentMaterialProfiles", QString()).toUtf8()).object();
    m_materials = GlassMaterials::read(group, presetAt(index), index != 0, presetAt(0).value(QStringLiteral("values")).toObject());
    showComponent();
    setNeedsSave(false);
}

void LiquidGlassEffectConfig::defaults()
{
    KCModule::defaults();
    m_profiles = {};
    m_materials = {};
    applyPreset(ui.kcfg_MaterialPreset->currentIndex());
}

void LiquidGlassEffectConfig::save()
{
    captureComponent();
    auto *error = widget()->findChild<QLabel *>(QStringLiteral("applyError"));
    error->hide();
    QString helper = QStandardPaths::findExecutable(QStringLiteral("mac-tahoe-glass-surfaces"));
    if (helper.isEmpty()) helper = QDir::homePath() + QStringLiteral("/.local/bin/mac-tahoe-glass-surfaces");
    QProcess apply;
    apply.start(helper, {QStringLiteral("--apply")});
    bool applied = apply.waitForStarted(3000);
    if (applied) {
        apply.write(QJsonDocument(m_materials).toJson(QJsonDocument::Compact));
        apply.closeWriteChannel();
        applied = apply.waitForFinished(15000) && apply.exitStatus() == QProcess::NormalExit && apply.exitCode() == 0;
    }
    if (!applied) {
        apply.kill();
        apply.waitForFinished(1000);
        const auto details = QString::fromUtf8(apply.readAllStandardError());
        error->setText(i18n("Could not apply background transparency: %1", details.isEmpty() ? apply.errorString() : details));
        error->show();
        setNeedsSave(true);
        return;
    }
    KCModule::save();

    // KConfigSkeleton removes entries equal to schema defaults. Retain the
    // selection explicitly, using stable IDs rather than combo-box positions.
    auto group = BlurConfig::self()->config()->group(QStringLiteral("Effect-liquidglass"));
    group.writeEntry("MaterialPreset", ui.kcfg_MaterialPreset->presetValue());
    const auto general = m_materials.value(QStringLiteral("general")).toObject();
    for (auto it = general.begin(); it != general.end(); ++it) {
        if (it.value().isBool()) group.writeEntry(it.key(), it.value().toBool());
        else if (it.value().isDouble()) group.writeEntry(it.key(), it.value().toDouble());
        else group.writeEntry(it.key(), QColor(it.value().toString()));
    }
    m_profiles[profileKey(m_activePresetIndex)] = m_materials;
    group.writeEntry("ComponentMaterialProfiles", QString::fromUtf8(QJsonDocument(m_profiles).toJson(QJsonDocument::Compact)));
    group.writeEntry("ComponentMaterials", QString::fromUtf8(QJsonDocument(m_materials).toJson(QJsonDocument::Compact)));
    group.sync();
    QDBusConnection::sessionBus().send(QDBusMessage::createSignal(QStringLiteral("/org/kde/MacTahoe/Glass"),
        QStringLiteral("org.kde.MacTahoe.Glass"), QStringLiteral("changed")));
    const auto result = QJsonDocument::fromJson(apply.readAllStandardOutput()).object();
    bool qtChanged = false;
    for (const auto &path : result.value(QStringLiteral("changed")).toArray())
        qtChanged |= path.toString().contains(QStringLiteral("/Kvantum/"));
    if (qtChanged) {
        QProcess::startDetached(helper, {QStringLiteral("--reload")});
    }

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
