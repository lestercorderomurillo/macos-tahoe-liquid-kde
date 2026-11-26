"""Show Plasma's system-wide calendar provider settings inside Liquid KDE."""

import gettext
from pathlib import Path

from PyQt6.QtCore import QLibraryInfo, QMetaObject, QObject, QUrl, pyqtSlot


class SettingsTranslations(QObject):
    def __init__(self, translate, parent):
        super().__init__(parent)
        self.translate = translate

    @pyqtSlot(str, result=str)
    @pyqtSlot(str, "QVariant", result=str)
    @pyqtSlot(str, "QVariant", "QVariant", result=str)
    def i18n(self, message, *args):
        text = self.translate(message)
        for index, value in enumerate(args, 1):
            text = text.replace(f"%{index}", str(value))
        return text

    @pyqtSlot(str, str, result=str)
    def i18nd(self, domain, message):
        return gettext.dgettext(domain, message)

    @pyqtSlot(str, str, str, result=str)
    def i18ndc(self, domain, context, message):
        return gettext.dpgettext(domain, context, message)


def provider_settings(translate, widget_package, parent):
    try:
        from PyQt6.QtQuickWidgets import QQuickWidget
    except ImportError:
        return {}
    plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "plasmacalendarplugins"
    sources = {
        "pimevents": widget_package / "contents/ui/config/ConfigPimEvents.qml",
        "holidaysevents": plugins / "holidays/HolidaysConfig.qml",
        "astronomicalevents": plugins / "astronomicalevents/AstronomicalEventsConfig.qml",
    }
    result = {}
    for key, source in sources.items():
        if not source.is_file():
            continue
        view = QQuickWidget(parent)
        view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        view.setMinimumHeight(240)
        view.setClearColor(parent.palette().window().color())
        view.rootContext().setContextObject(SettingsTranslations(translate, view))
        view.setSource(QUrl.fromLocalFile(str(source)))
        if view.status() != QQuickWidget.Status.Ready:
            view.deleteLater()
            continue
        page = view.rootObject()
        view.calendar_changed = False
        if hasattr(page, "configurationChanged"):
            page.configurationChanged.connect(lambda target=view: setattr(target, "calendar_changed", True))
        result[key] = view
    return result


def save_provider_settings(pages):
    for page in pages.values():
        settings = page.rootObject()
        if page.isEnabled() and (page.calendar_changed or settings.property("unsavedChanges")):
            QMetaObject.invokeMethod(settings, "saveConfig")
            page.calendar_changed = False
