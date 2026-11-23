"""Show Plasma's system-wide calendar provider settings inside Liquid KDE."""

import gettext
from pathlib import Path

from PyQt6.QtCore import QLibraryInfo, QMetaObject, QObject, QUrl, pyqtSlot


class _Translations(QObject):
    def __init__(self, translate, parent):
        super().__init__(parent)
        self.translate = translate

    @pyqtSlot(str, result=str)
    def i18n(self, message):
        return self.translate(message)

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
        view.rootContext().setContextObject(_Translations(translate, view))
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
