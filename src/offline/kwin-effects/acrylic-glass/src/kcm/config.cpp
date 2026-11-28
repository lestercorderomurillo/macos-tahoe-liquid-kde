/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>
    SPDX-License-Identifier: GPL-2.0-or-later
*/
#include "config.h"
#include "../../../../plasmoids/org.kde.mac.tahoe.liquid.taskmanager/launcher/contrastpreset.h"
#include <QFileDialog>
#include <QSaveFile>
#include <QMessageBox>
#include <QPlainTextEdit>
#include "glassconfig.h"
#include "presets.h"
#include "../componentmaterials.h"
#include <KLocalizedString>
#include <QDialogButtonBox>
#include <QFormLayout>
#include <QHBoxLayout>
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
    : KCModule(qobject_cast<QWidget *>(parent), data)
{
    if (this->parent() != parent)
        setParent(parent);
    ui.setupUi(widget());
    auto *contrast = new QPushButton(i18n("Adaptive Contrast presets…"), widget());
    ui.presetGroupForm->addRow(contrast);
    connect(contrast, &QPushButton::clicked, this, &LiquidGlassEffectConfig::editContrast);
    const auto presets = QJsonDocument::fromJson(materialPresetsJson).array();
    int row = 0;
    for (const auto &entry : presets) {
        const int value = entry.toObject().value(QStringLiteral("value")).toInt();
        ui.kcfg_MaterialPreset->addItem(entry.toObject().value(QStringLiteral("title")).toString(), value);
        ui.kcfg_MaterialPreset->setItemData(row++, entry.toObject().value(QStringLiteral("variant")).toInt(), Qt::UserRole + 1);
    }
    connect(ui.kcfg_BackingTint, &QSpinBox::valueChanged,
            ui.kcfg_MaterialPreset, &PresetComboBox::setBackingTint);
    m_componentSelector = new QComboBox(widget());
    m_componentSelector->setObjectName(QStringLiteral("componentSelector"));
    const QStringList labels = {i18n("Application windows"), i18n("Finder"), i18n("Menus / Shell"),
        i18n("Plasma widget popups"), i18n("Apps + Clipboard"), i18n("Search capsule"),
        i18n("Control Center"), i18n("About This Computer"), i18n("Dock"), i18n("Top panel")};
    for (int i = 0; i < GlassMaterials::components.size(); ++i)
        m_componentSelector->addItem(labels.at(i), GlassMaterials::components.at(i));
    ui.presetGroupForm->addRow(i18n("Component"), m_componentSelector);
    auto *rowLayout = new QHBoxLayout;
    rowLayout->addStretch();
    auto *copy = new QPushButton(i18n("Copy values"), widget());
    auto *paste = new QPushButton(i18n("Paste values"), widget());
    copy->setObjectName(QStringLiteral("copyComponentValues"));
    paste->setObjectName(QStringLiteral("pasteComponentValues"));
    paste->setEnabled(false);
    rowLayout->addWidget(copy);
    rowLayout->addWidget(paste);
    ui.presetGroupForm->addRow(rowLayout);
    connect(copy, &QPushButton::clicked, this, [this, paste] {
        captureComponent();
        m_copiedValues = m_materials.value(component()).toObject();
        paste->setEnabled(!m_copiedValues.isEmpty());
    });
    connect(paste, &QPushButton::clicked, this, [this] {
        if (m_materials.value(component()) == m_copiedValues) return;
        m_materials[component()] = m_copiedValues;
        showComponent();
        setNeedsSave(true);
    });
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
            ui.surfaceGroupForm->addRow(entry.endsWith(QStringLiteral("Light")) ? i18n("Transparency SVG (Light)") : i18n("Transparency SVG (Dark)"), number);
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
        else if (auto *color = qobject_cast<GradientColorButton *>(control)) connect(color, &GradientColorButton::colorChanged, this, changed);
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
    if (index < 0 || index >= ui.kcfg_MaterialPreset->count()) return;
    const auto preset = presetAt(index);
    const int variant = preset.value(QStringLiteral("variant")).toInt();
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
    return presets.at(index).toObject();
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
        else if (auto *color = qobject_cast<GradientColorButton *>(it.value())) values[it.key()] = color->color().name(QColor::HexRgb);
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
        else if (auto *color = qobject_cast<GradientColorButton *>(it.value())) color->setColor(QColor(value.toString()));
    }
    m_loading = false;
}

void LiquidGlassEffectConfig::selectComponent(int index)
{
    captureComponent();
    m_componentIndex = index;
    showComponent();
}

void LiquidGlassEffectConfig::editContrast()
{
    QDialog dialog(widget());
    dialog.setWindowTitle(i18n("Adaptive Contrast presets"));
    auto *layout = new QVBoxLayout(&dialog);
    auto *selector = new QComboBox(&dialog);
    selector->addItem(i18n("Default"));
    selector->addItem(i18n("Custom"));
    selector->setCurrentIndex(m_contrastPreset == ContrastPreset::empty() ? 0 : 1);
    layout->addWidget(selector);
    auto *edit = new QPlainTextEdit(&dialog);
    layout->addWidget(edit);
    const auto show = [&](const QJsonObject &preset) {
        edit->setPlainText(QString::fromUtf8(QJsonDocument(preset).toJson()));
    };
    const auto defaults = [] {
        auto preset = ContrastPreset::empty();
        preset.insert(QStringLiteral("components"), ContrastPreset::defaults());
        return preset;
    };
    auto custom = m_contrastPreset == ContrastPreset::empty() ? defaults() : m_contrastPreset;
    const auto read = [&](QJsonObject &document) {
        QJsonParseError error;
        const auto parsed = QJsonDocument::fromJson(edit->toPlainText().toUtf8(), &error);
        QJsonObject profiles;
        const QString problem = error.error == QJsonParseError::NoError
            ? ContrastPreset::resolve(parsed.object(), profiles) : error.errorString();
        if (!problem.isEmpty()) {
            QMessageBox::warning(&dialog, dialog.windowTitle(), i18n("Invalid contrast preset: %1", problem));
            return false;
        }
        document = parsed.object();
        return true;
    };
    const auto select = [&](int index) {
        edit->setReadOnly(index == 0);
        show(index == 0 ? defaults() : custom);
    };
    select(selector->currentIndex());
    connect(selector, &QComboBox::activated, &dialog, [&](int index) {
        if (!index && !edit->isReadOnly() && !read(custom)) {
            selector->setCurrentIndex(1);
            return;
        }
        select(index);
    });
    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel, &dialog);
    layout->addWidget(buttons);
    auto *import = buttons->addButton(i18n("Import JSON…"), QDialogButtonBox::ActionRole);
    connect(import, &QPushButton::clicked, &dialog, [&] {
        const auto path = QFileDialog::getOpenFileName(&dialog, import->text(), {}, QStringLiteral("JSON (*.json)"));
        if (path.isEmpty()) return;
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly)) {
            QMessageBox::warning(&dialog, import->text(), file.errorString());
            return;
        }
        const auto previous = edit->toPlainText();
        edit->setPlainText(QString::fromUtf8(file.readAll()));
        if (!read(custom)) { edit->setPlainText(previous); return; }
        selector->setCurrentIndex(1);
        select(1);
    });
    auto *exportButton = buttons->addButton(i18n("Export JSON…"), QDialogButtonBox::ActionRole);
    connect(exportButton, &QPushButton::clicked, &dialog, [&] {
        QJsonObject preset;
        if (!read(preset)) return;
        const auto path = QFileDialog::getSaveFileName(&dialog, exportButton->text(), {}, QStringLiteral("JSON (*.json)"));
        if (path.isEmpty()) return;
        QSaveFile file(path);
        const auto bytes = QJsonDocument(preset).toJson();
        if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size() || !file.commit())
            QMessageBox::warning(&dialog, exportButton->text(), file.errorString());
    });
    connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
    connect(buttons, &QDialogButtonBox::accepted, &dialog, [&] {
        QJsonObject preset = ContrastPreset::empty();
        if (selector->currentIndex() && !read(preset)) return;
        if (m_contrastPreset != preset) {
            m_contrastPreset = preset;
            setNeedsSave(true);
        }
        dialog.accept();
    });
    dialog.resize(640, 480);
    dialog.exec();
}

void LiquidGlassEffectConfig::load()
{
    KCModule::load();
    const KConfigGroup group(BlurConfig::self()->config(), QStringLiteral("Effect-liquidglass"));
    const int index = ui.kcfg_MaterialPreset->currentIndex();
    const auto saved = QJsonDocument::fromJson(group.readEntry("AdaptiveContrastPreset", QByteArray())).object();
    QJsonObject resolved;
    m_contrastPreset = ContrastPreset::resolve(saved, resolved).isEmpty() ? saved : ContrastPreset::empty();
    m_activePresetIndex = index;
    m_profiles = QJsonDocument::fromJson(group.readEntry("ComponentMaterialProfiles", QString()).toUtf8()).object();
    m_materials = GlassMaterials::read(group, presetAt(index), index != 0, presetAt(0).value(QStringLiteral("values")).toObject());
    showComponent();
    setNeedsSave(false);
}

void LiquidGlassEffectConfig::defaults()
{
    KCModule::defaults();
    m_contrastPreset = ContrastPreset::empty();
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
    group.writeEntry("AdaptiveContrastPreset", QJsonDocument(m_contrastPreset).toJson(QJsonDocument::Compact));
    group.writeEntry("MaterialPreset", ui.kcfg_MaterialPreset->presetValue());
    const auto general = m_materials.value(QStringLiteral("general")).toObject();
    for (auto it = general.begin(); it != general.end(); ++it) {
        if (it.key() == QStringLiteral("BlurDecorations")) continue; // Saved by the global checkbox.
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

    // An XWayland settings window still controls the Wayland compositor.
    for (const QString &effect : {QStringLiteral("liquidglass"), QStringLiteral("liquidglass_x11")}) {
        auto loaded = interface.isEffectLoaded(effect);
        loaded.waitForFinished();
        if (!loaded.isError() && loaded.value()) interface.reconfigureEffect(effect);
    }
}

} // namespace KWin

// The installed Settings app hosts the same editor as KWin's effect module.
extern "C" Q_DECL_EXPORT void mttkde_attach_glass_editor(QWidget *host)
{
    auto *editor = new KWin::LiquidGlassEffectConfig(host, KPluginMetaData());
    auto *controls = editor->widget();
    auto *layout = qobject_cast<QBoxLayout *>(host->layout());
    if (!layout) {
        layout = new QVBoxLayout(host);
        layout->addWidget(controls);
    }
    layout->setContentsMargins(0, 0, 0, 0);

    auto *buttons = new QDialogButtonBox(QDialogButtonBox::RestoreDefaults | QDialogButtonBox::Reset
                                         | QDialogButtonBox::Apply, host);
    auto *apply = buttons->button(QDialogButtonBox::Apply);
    auto *reset = buttons->button(QDialogButtonBox::Reset);
    buttons->setObjectName(QStringLiteral("glassEditorButtons"));
    layout->insertWidget(0, buttons);
    QObject::connect(apply, &QPushButton::clicked, editor, &KCModule::save);
    QObject::connect(reset, &QPushButton::clicked, editor, &KCModule::load);
    QObject::connect(buttons->button(QDialogButtonBox::RestoreDefaults), &QPushButton::clicked,
                     editor, &KCModule::defaults);
    const auto updateActions = [editor, apply, reset] {
        apply->setEnabled(editor->needsSave());
        reset->setEnabled(editor->needsSave());
    };
    QObject::connect(editor, &KCModule::needsSaveChanged, buttons, updateActions);
    editor->load();
    updateActions();
}

#include "config.moc"
#include "moc_config.cpp"
