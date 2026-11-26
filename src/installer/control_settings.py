"""Control Center pages for the installed Settings window."""

import shutil

# Native detail views and actions match the panel's ControlView.qml.
VIEWS = {
    "volume": ("Volume", "speaker", "AudioView"),
    "bluetooth": ("Bluetooth", "bluetooth", "BluetoothView"),
    "wifi": ("Wi-Fi", "wifi", "WifiView"),
    "focus": ("Focus", "moon", "FocusSwitch"),
    "battery": ("Battery", "battery", "BatteryView"),
    "media": ("Now Playing", "music", "MediaView"),
    "notifications": ("Notifications", "bell", "NotificationsView"),
}
ACTIONS = {
    "sharing": ("File Sharing", "airdrop-off", "KDE Connect", ("kdeconnect-app",)),
    "overview": ("Overview", "stage-manager", "Overview", (
        "qdbus6", "org.kde.kglobalaccel", "/component/kwin",
        "org.kde.kglobalaccel.Component.invokeShortcut", "Overview")),
    "mirroring": ("Screen Mirroring", "mirroring", "Display Settings…", ("systemsettings", "kcm_kscreen")),
    "screenshot": ("Screenshot", "screenshot", "Screenshot", ("spectacle", "-r", "-d", "300")),
}
MERGED = {"focus": "notifications", "media": "volume", "overview": "windows",
          "mirroring": "display", "screenshot": "display"}
CONTROLS = VIEWS | ACTIONS
PAGES = {key: (entry[0], entry[1], ()) for key, entry in CONTROLS.items() if key not in MERGED}


def add_page_controls(window, page):
    from wizard_window import section_heading

    if page in VIEWS or page in ACTIONS or page == "display":
        add_controls(window, page)
    for key, parent in MERGED.items():
        if parent != page or key == "mirroring":
            continue
        if key == "media":
            window.body.addWidget(section_heading(window, window.t(CONTROLS[key][0])))
        add_controls(window, key)


def add_controls(window, page):
    from PyQt6.QtCore import QProcess, QTimer, QUrl, Qt
    from PyQt6.QtWidgets import QFileDialog, QVBoxLayout
    from wizard_window import CONTROL_SYMBOLS, GlassButton

    panel = window.option_card()
    column = QVBoxLayout(panel)
    window.body.addWidget(panel)
    if page in ACTIONS:
        _, _, title, command = ACTIONS[page]
        if page == "sharing":
            send = GlassButton(window.t("Choose a file…"))
            send.setEnabled(shutil.which("kdeconnect-handler") is not None)
            def share():
                files, _ = QFileDialog.getOpenFileNames(window, window.t("File Sharing"))
                if files:
                    QProcess.startDetached("kdeconnect-handler", [QUrl.fromLocalFile(f).toString() for f in files])
            send.clicked.connect(share)
            column.addWidget(send, alignment=Qt.AlignmentFlag.AlignLeft)
        button = GlassButton(window.t(title))
        button.setEnabled(shutil.which(command[0]) is not None)
        button.clicked.connect(lambda: QProcess.startDetached(command[0], list(command[1:])))
        column.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        return

    try:
        from PyQt6.QtQml import QQmlEngine
        from PyQt6.QtQuickWidgets import QQuickWidget
    except ImportError:
        column.addWidget(window.label("Unavailable"))
        return
    from calendar_provider_settings import SettingsTranslations
    if not hasattr(window, "control_engine"):
        window.control_engine = QQmlEngine(window)
        window.control_engine.rootContext().setContextObject(SettingsTranslations(window.t, window.control_engine))
    view = QQuickWidget(window.control_engine, panel)
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    view.setClearColor(Qt.GlobalColor.transparent)
    source = "DisplayView" if page == "display" else VIEWS[page][2]
    view.setSource(QUrl.fromLocalFile(str(CONTROL_SYMBOLS.parent / (source + ".qml"))))
    root = view.rootObject()
    if root is None:
        label = window.label("Unavailable")
        label.setToolTip("\n".join(error.toString() for error in view.errors()))
        column.addWidget(label)
        view.deleteLater()
        return
    if page in ("volume", "display"):
        title, module = (("Audio outputs", "kcm_pulseaudio") if page == "volume"
                         else ("Display Settings…", "kcm_kscreen"))
        root.setProperty("detailed", True)
        settings = GlassButton(window.t(title))
        settings.setEnabled(shutil.which("systemsettings") is not None)
        settings.clicked.connect(lambda: QProcess.startDetached("systemsettings", [module]))
        root.detailsRequested.connect(settings.click)
        if page == "display":
            from PyQt6.QtWidgets import QHBoxLayout
            row = QHBoxLayout()
            row.addWidget(window.label("Screen Mirroring"), 1)
            row.addWidget(settings)
            column.addLayout(row)
        else:
            column.addWidget(settings, alignment=Qt.AlignmentFlag.AlignLeft)
    def resize():
        view.setFixedHeight(max(42, round(root.implicitHeight())))
    # Qt Quick layouts can change implicit size while destroying their children.
    # Resize on the event loop while the hosting widget is still alive.
    timer = QTimer(view)
    timer.setInterval(0)
    timer.setSingleShot(True)
    timer.timeout.connect(resize)
    root.implicitHeightChanged.connect(timer.start)
    resize()
    column.insertWidget(0, view)
