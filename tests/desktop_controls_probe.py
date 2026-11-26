"""Run production controls on a private bus, with deterministic hardware changes."""
import sys
import os
import subprocess
import time
import json
from pathlib import Path
from PyQt6.QtCore import (QAbstractListModel, QModelIndex, QObject, QUrl, QMetaObject,
                         Qt, QPoint, QPointF, Q_ARG, pyqtSlot, pyqtProperty, qInstallMessageHandler)
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTextDocument, QColor
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtTest import QTest
from PyQt6 import sip

# KDE caches desktop-entry lookups. Register both senders before the first
# notification so history recognizes them in a clean SDK container.
applications = Path(os.environ['XDG_DATA_HOME']) / 'applications'
applications.mkdir(parents=True, exist_ok=True)
for desktop, name in (('notification-review', 'Notification Review'), ('discord', 'Discord')):
    (applications / f'{desktop}.desktop').write_text(
        f'[Desktop Entry]\nType=Application\nName={name}\nExec=true\n')

# Include the fixture's senders in KDE's application index on distributions
# whose session normally supplies a vendor-prefixed menu.
menus = Path(os.environ['XDG_CONFIG_HOME']) / 'menus'
menus.mkdir(parents=True, exist_ok=True)
(menus / 'applications.menu').write_text(
    '<Menu><Name>Applications</Name><DefaultAppDirs/><Include><All/></Include></Menu>')
os.environ['XDG_MENU_PREFIX'] = ''

app = QApplication([])
engine = QQmlEngine()
engine.rootContext().setContextProperty('i18n', engine.evaluate('''(function(text) {
    for (var i = 1; i < arguments.length; i++) text = text.replace('%' + i, arguments[i]);
    return text;
})'''))
engine.rootContext().setContextProperty('i18nd', engine.evaluate('''(function(domain, text) {
    for (var i = 2; i < arguments.length; i++) text = text.replace('%' + (i - 1), arguments[i]);
    return text;
})'''))
root = Path(sys.argv[1]) / 'src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui'
errors, keep = [], []
def report(kind, context, text):
    if any(token in text for token in ('ReferenceError:', 'TypeError:', 'Unable to assign', 'Binding loop')):
        errors.append(text)
qInstallMessageHandler(report)

def component(name, properties=None):
    c = QQmlComponent(engine, QUrl.fromLocalFile(str(root / name)))
    assert c.isReady(), [e.toString() for e in c.errors()]
    obj = c.createWithInitialProperties(properties or {})
    assert obj is not None, [e.toString() for e in c.errors()]
    keep.extend([c, obj]); QTest.qWait(30)
    return obj

def fake(source):
    c = QQmlComponent(engine)
    c.setData(('import QtQuick\n' + source).encode(), QUrl.fromLocalFile(str(root / '_probe.qml')))
    assert c.isReady(), [e.toString() for e in c.errors()]
    obj = c.create(); assert obj is not None
    keep.extend([c,obj]); return obj

def child(obj, name):
    pending = [obj]
    seen = set()
    while pending:
        value = pending.pop()
        if value in seen: continue
        seen.add(value)
        if value.objectName() == name: return value
        pending.extend(value.children())
        if hasattr(value, 'childItems'): pending.extend(value.childItems())
    raise AssertionError(name + ': ' + '\n'.join(errors))

def click(obj):
    assert obj.property('enabled'), obj.objectName()
    QMetaObject.invokeMethod(obj, 'triggered' if obj.metaObject().indexOfSignal(b'triggered()') >= 0 else 'clicked', Qt.ConnectionType.DirectConnection)
    QTest.qWait(10)

# Native imports must load even when the desktop services and hardware are absent.
for name in ('ControlView.qml','BatteryView.qml','WifiView.qml','NotificationsView.qml'):
    component(name)

# Notification windows and the process-wide frontend must load independently
# of the stock KDE applet, and multiple bars must elect only one popup host.
notices = root.parents[2] / 'org.kde.mac-tahoe-liquid-kde.notifications/contents/ui'
noticeHost = fake('''import org.kde.mac.tahoe.launcher as Native
import org.kde.notificationmanager as Notifications
import "''' + QUrl.fromLocalFile(str(notices)).toString() + '''" as Notices
Item {
    id: host
    property color notificationTextColor: "black"
    property color notificationBackgroundColor: "white"
    property color notificationDisabledColor: "gray"
    property var service: Notices.NotificationPopups
    property var popupState: function() { return [service.popups.count, service.windows.count, service.host === host, service.available.width, service.popups.urgencies, service.inhibited, service.historyVisible, service.popups.showExpired]; }
    property var visibleNotices: function() {
        const result = [];
        for (let i = 0; i < service.windows.count; ++i) {
            const popup = service.windows.objectAt(i);
            if (popup && popup.visible) result.push(popup);
        }
        return result;
    }
    property QtObject settings: QtObject {
        property date notificationsInhibitedUntil: new Date(0)
        property bool notificationsInhibitedByApplication: false
        property bool inhibitNotificationsWhenFullscreen: false
        property bool fullscreenFocused: false
        property bool inhibitNotificationsWhenScreensMirrored: false
        property bool screensMirrored: false
        property bool jobsInNotifications: true
        property var popupBlacklistedApplications: []
        property var popupBlacklistedServices: []
        property var doNotDisturbPopupWhitelistedApplications: []
        property var doNotDisturbPopupWhitelistedServices: []
        property bool criticalPopupsInDoNotDisturbMode: true
        property bool lowPriorityPopups: false
        property int popupTimeout: 5000
        property bool permanentJobPopups: true
        function save() {}
    }
    property QtObject plasmoid: QtObject {
        property QtObject containment: QtObject {
            property rect screenGeometry: Qt.rect(0, 0, 1920, 1080)
            property rect availableScreenRect: Qt.rect(0, 32, 1920, 1048)
        }
    }
    property bool normalAllowed: !!(service.popups.urgencies & Notifications.Notifications.NormalUrgency)
    property var secondHost: Item { property var plasmoid: host.plasmoid; property bool historyVisible: false }
    function addHost() { service.adopt(secondHost); }
    function removeHost() { service.forget(host); }
    function resetHosts() { service.forget(secondHost); service.adopt(host); }
    property var banner: Native.NotificationBanner {
        mainItem: Item { width: 360; height: 120 }
    }
    function inhibit() { service.settings.notificationsInhibitedUntil = new Date(Date.now() + 60000); service.settings.save(); }
    function restore() { service.settings.notificationsInhibitedUntil = new Date(0); service.settings.save(); }
    Component.onCompleted: { service.settings = settings; service.adopt(host); }
}''')
noticeService = noticeHost.property('service')
assert noticeService.property('host') == noticeHost
QMetaObject.invokeMethod(noticeHost, 'addHost'); QTest.qWait(10)
assert noticeService.property('host') == noticeHost
QMetaObject.invokeMethod(noticeHost, 'removeHost'); QTest.qWait(10)
assert noticeService.property('host') == noticeHost.property('secondHost')
QMetaObject.invokeMethod(noticeHost, 'resetHosts'); QTest.qWait(10)
assert noticeService.property('host') == noticeHost
assert noticeHost.property('normalAllowed')
QMetaObject.invokeMethod(noticeHost, 'inhibit'); QTest.qWait(10)
assert noticeService.property('inhibited') and not noticeHost.property('normalAllowed')
QMetaObject.invokeMethod(noticeHost, 'restore'); QTest.qWait(10)
assert not noticeService.property('inhibited') and noticeHost.property('normalAllowed')
banner = noticeHost.property('banner')
assert banner.property('mainItem').parentItem() == banner.contentItem()
assert not banner.property('takeFocus')
banner.setProperty('takeFocus', True); assert banner.property('takeFocus')
banner.setProperty('isCritical', True); assert banner.property('isCritical')

# Exercise the real D-Bus manager and history, including the default exclusion
# of unidentified applications. A mock list cannot prove receipt or retention.
nativeView = component('NotificationsView.qml', {'standalone': True})
nativeView.setWidth(344); nativeView.setHeight(700)
nativeHistory = nativeView.property('history')
def notify(app, summary, body, desktop, timeout=0, replace=0):
    sender = subprocess.Popen([
        'gdbus', 'call', '--session', '--dest', 'org.freedesktop.Notifications',
        '--object-path', '/org/freedesktop/Notifications', '--method',
        'org.freedesktop.Notifications.Notify', app, str(replace), '',
        summary, body, '[]', "{'desktop-entry': <'" + desktop + "'>}", str(timeout)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 5
    while sender.poll() is None and time.monotonic() < deadline:
        QTest.qWait(10)
    assert sender.poll() == 0, sender.communicate(timeout=1)
    output, _ = sender.communicate(timeout=1)
    QTest.qWait(100)
    return int(output.split('uint32 ')[1].split(',')[0])

def notification_body(card):
    document = QTextDocument()
    document.setHtml(child(card, 'notificationBody').property('text'))
    return document.toPlainText().strip()

def visible_notices():
    # Read the binding after the native grouping model and window delegates settle.
    QTest.qWait(50)
    return noticeHost.property('visibleNotices').call().toVariant()

notify('Notification Review', 'A real notification', 'Retained when history opens', 'notification-review')
assert nativeHistory.property('count') == 1
QMetaObject.invokeMethod(noticeService, 'markSeen'); QTest.qWait(100)
assert nativeHistory.property('count') == 1
assert nativeHistory.property('expiredNotificationsCount') == 1
click(child(nativeView, 'clearHistory')); QTest.qWait(100)
assert nativeHistory.property('count') == 0

# Real application messages must stack in the installed popup frontend, retain
# their individual bodies, and never replay sounds when the stack is expanded.
ids = [notify('discord', 'Message ' + str(i), 'Body ' + str(i), 'discord') for i in range(3)]
popups = visible_notices()
assert len(popups) == 1, (len(popups), errors, noticeHost.property('popupState').call().toVariant(), nativeHistory.property('count'), nativeHistory.property('expiredNotificationsCount'))
stack = child(popups[0].property('mainItem'), 'notificationStackSurface')
assert stack.property('depth') == 2
card = child(stack, 'notificationCard')
assert child(card, 'notificationApplicationName').property('text') == 'Discord'
assert child(card, 'notificationSummary').property('text') == 'Message 2'
assert notification_body(card) == 'Body 2', (notification_body(card), errors)
sounded = noticeService.property('soundedIds').toVariant()
QMetaObject.invokeMethod(card, 'open'); QTest.qWait(100)
expanded_notices = visible_notices()
assert len(expanded_notices) == 4
# A group spans separate native banner windows. Neither the most common
# background nor a local exception may invert any member's theme foreground.
for light in (True, False):
    noticeHost.setProperty('notificationTextColor', QColor('white' if light else 'black'))
    noticeHost.setProperty('notificationBackgroundColor', QColor('black' if light else 'white'))
    for majority, minority in ((0, 1), (1, 0)):
        for i, pane in enumerate(expanded_notices):
            channel = minority if i == 0 else majority
            sample = dict(pid=os.getpid(), x=pane.x(), y=pane.y(), width=pane.width(),
                          height=pane.height(), rgb=[channel] * 3)
            QMetaObject.invokeMethod(pane, 'updateBackdrop', Q_ARG(str, json.dumps(sample)))
        QTest.qWait(30)
        inks = [child(pane.property('mainItem'), 'notificationSummary').property('color')
                for pane in expanded_notices]
        assert all((ink.lightnessF() > .5) == light for ink in inks), ([ink.name() for ink in inks], errors)
noticeHost.setProperty('notificationTextColor', QColor('black'))
noticeHost.setProperty('notificationBackgroundColor', QColor('white'))
QMetaObject.invokeMethod(card, 'open'); QTest.qWait(100)
assert len(visible_notices()) == 1
assert noticeService.property('soundedIds').toVariant() == sounded
noticeHost.property('settings').setProperty('popupTimeout', 40)
assert notify('discord', 'Edited message', 'Edited body', 'discord', replace=ids[-1]) == ids[-1]
popups = visible_notices()
assert len(popups) == 1
assert child(popups[0].property('mainItem'), 'notificationSummary').property('text') == 'Edited message'
assert notification_body(popups[0].property('mainItem')) == 'Edited body'
noticeHost.property('settings').setProperty('popupTimeout', 5000)
notify('Notification Review', 'Another app', 'Separate stack', 'notification-review')
assert len(visible_notices()) == 2
QMetaObject.invokeMethod(noticeService, 'markSeen'); QTest.qWait(100)
assert len(visible_notices()) == 0
assert nativeHistory.property('expiredNotificationsCount') == 4, (
    nativeHistory.property('count'), nativeHistory.property('expiredNotificationsCount'),
    noticeHost.property('popupState').call().toVariant(), errors)
click(child(nativeView, 'clearHistory')); QTest.qWait(100)
assert nativeHistory.property('count') == 0
notify('discord', 'Expiring one', 'First', 'discord', timeout=1200)
notify('discord', 'Expiring two', 'Second', 'discord', timeout=1200)
popups = visible_notices()
assert len(popups) == 1
assert child(popups[0].property('mainItem'), 'notificationStackSurface').property('depth') == 1
QMetaObject.invokeMethod(child(popups[0].property('mainItem'), 'notificationCard'), 'open')
QTest.qWait(100)
expanded = visible_notices()
assert len(expanded) == 3
assert not child(expanded[0], 'notificationExpiry').property('running')
assert child(expanded[1], 'notificationExpiry').property('running')
QTest.qWait(1400)
assert len(visible_notices()) == 0
assert nativeHistory.property('expiredNotificationsCount') == 2
click(child(nativeView, 'clearHistory')); QTest.qWait(100)
assert nativeHistory.property('count') == 0

# The same native window must follow real backdrop samples independently of
# the desktop mode. Samples for another process/window must not affect it.
noticeForContrast = noticeHost.property('banner')
noticeForContrast.setGeometry(100, 100, 364, 100)
noticeForContrast.setProperty('visible', True)
sample = dict(pid=os.getpid(), x=100, y=100, width=364, height=100, rgb=[1,1,1])
QMetaObject.invokeMethod(noticeForContrast, 'updateBackdrop', Q_ARG(str, json.dumps(sample)))
assert noticeForContrast.property('backdropColor').lightnessF() == 1
rounded = dict(sample, width=365, rgb=[0,0,0])
QMetaObject.invokeMethod(noticeForContrast, 'updateBackdrop', Q_ARG(str, json.dumps(rounded)))
assert noticeForContrast.property('backdropColor').lightnessF() == 0
for invalid in (dict(sample, pid=os.getpid()+1), dict(sample, width=370),
                dict(sample, y=140), dict(sample, rgb=[-1,0,0])):
    QMetaObject.invokeMethod(noticeForContrast, 'updateBackdrop', Q_ARG(str, json.dumps(invalid)))
    assert noticeForContrast.property('backdropColor').lightnessF() == 0
sample['rgb'] = [0,0,0]
QMetaObject.invokeMethod(noticeForContrast, 'updateBackdrop', Q_ARG(str, json.dumps(sample)))
assert noticeForContrast.property('backdropColor').lightnessF() == 0
noticeForContrast.setProperty('visible', False)
contrast = fake('''import "NotificationContrast.js" as Contrast
import org.kde.mac.tahoe.launcher as Native
Item {
    Native.GlassSettings { id: ink; component: "notifications" }
    property color base: "white"
    property color backdrop: "white"
    property color surface: "transparent"
    property color foreground: ink.notificationForeground(base, backdrop, surface)
    property bool enabledContrast: ink.dynamicTinting
    property real contrastRatio: Contrast.ratio(Contrast.luminance(foreground), Contrast.luminance(backdrop))
    property real baseRatio: Contrast.ratio(Contrast.luminance(base), Contrast.luminance(backdrop))
}''')
for base in ('#eeeeee', '#333333'):
    contrast.setProperty('base', QColor(base))
    for backdrop in ('white', 'black', '#808080'):
        contrast.setProperty('backdrop', QColor(backdrop)); QTest.qWait(10)
        adjusted = contrast.property('foreground')
        original = QColor(base)
        assert abs(adjusted.red() - original.red()) <= 102
        def separation(color):
            y = ((color.redF() + .055) / 1.055) ** 2.4 if color.redF() > .04045 else color.redF() / 12.92
            return 1.16 * y ** (1/3) - .16 if y > 216/24389 else y * 24389/2700
        surface = separation(QColor(backdrop))
        before = abs(separation(original) - surface)
        assert abs(separation(adjusted) - surface) >= before
        if before >= .33:
            assert adjusted == original
        if not contrast.property('enabledContrast'):
            assert adjusted == original, (base, backdrop)

sink = fake('QtObject { property bool muted: false; property int volume: 20000; property string description: "Test output" }')
audio = component('AudioView.qml', {'sink':sink})
slider = child(audio, 'volumeSlider'); mute = child(audio,'muteButton')
assert slider.property('value') == 20000
# Enlarging the click target must not stretch the reference-size glyph.
mute.setWidth(48); mute.setHeight(48); QTest.qWait(10)
assert child(mute, 'controlIcon').width() == 16
assert child(mute, 'controlIcon').height() == 16
sink.setProperty('volume',40000); QTest.qWait(10)
assert slider.property('value') == 40000
click(mute); assert sink.property('muted')
slider.setProperty('value', 30000)
QMetaObject.invokeMethod(slider, 'moved', Qt.ConnectionType.DirectConnection)
assert sink.property('volume') == 30000 and not sink.property('muted')
slider.setProperty('value', 0)
QMetaObject.invokeMethod(slider, 'moved', Qt.ConnectionType.DirectConnection)
assert sink.property('volume') == 0 and sink.property('muted')
sink.setProperty('muted',False); QTest.qWait(10); assert not mute.property('checked')
audio.setProperty('sink',None); QTest.qWait(10)
assert not slider.property('enabled') and not mute.property('enabled')

# The standalone menus use the same production content with a bounded glass surface.
for name in ('WifiView.qml','BatteryView.qml'):
    menu = component('StatusMenuPopup.qml', {'source': QUrl.fromLocalFile(str(root/name))})
    assert menu.implicitHeight() > 40 and menu.implicitWidth() == 328

# Browser sessions without track metadata must keep the neutral placeholder.
player = fake('QtObject { property string track: ""; property string identity: "Chrome"; property string artUrl: ""; property string artist: ""; property bool canPlay: false; property bool canPause: false; property bool canGoNext: false; property bool canGoPrevious: false; property int playbackStatus: 0 }')
media = component('MediaView.qml', {'player':player})
assert child(media,'trackTitle').property('text') == 'Nothing playing'
player.setProperty('track','A track'); QTest.qWait(10)
assert child(media,'trackTitle').property('text') == 'A track'

wireless = fake('QtObject { property bool wirelessEnabled: true; property bool wirelessHwEnabled: true }')
devices = fake('QtObject { property bool wirelessDeviceAvailable: true }')
handler = fake('''QtObject {
    property bool scanning: false
    property int requests: 0
    property bool requested: true
    function enableWireless(value) { requested = value; requests++; }
}''')
wifi = component('WifiView.qml', {'wireless':wireless,'devices':devices,'handler':handler})
toggle = child(wifi,'wirelessToggle')
click(toggle); assert handler.property('requests') == 1 and not handler.property('requested')
wireless.setProperty('wirelessEnabled',False);QTest.qWait(10);assert not toggle.property('checked')
wireless.setProperty('wirelessHwEnabled',False);QTest.qWait(10);assert not toggle.property('enabled')
wireless.setProperty('wirelessHwEnabled',True);devices.setProperty('wirelessDeviceAvailable',False)
QTest.qWait(10);assert not toggle.property('enabled')

settings = fake('''QtObject {
    property date notificationsInhibitedUntil: new Date(0)
    property bool notificationsInhibitedByApplication: false
    property int saves: 0
    function save() { saves++; }
}''')
focus = component('FocusSwitch.qml',{'settings':settings})
focus.setProperty('checked',True);click(focus)
assert settings.property('saves') == 1
settings.setProperty('notificationsInhibitedByApplication',True);QTest.qWait(10)
assert not focus.property('enabled')


# Hardware rows are real QAbstractListModel roles, so delegate contracts execute.
class Rows(QAbstractListModel):
    def __init__(self, rows):
        super().__init__(); self.rows = rows
        self.roles = {Qt.ItemDataRole.UserRole + i: key.encode() for i,key in enumerate(rows[0])}
    def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.rows)
    def roleNames(self): return self.roles
    def data(self, index, role):
        return self.rows[index.row()].get(self.roles[role].decode()) if index.isValid() and role in self.roles else None
    def update(self, index, key, value):
        self.rows[index][key] = value
        role = next(r for r,k in self.roles.items() if k.decode() == key)
        self.dataChanged.emit(self.index(index,0),self.index(index,0),[role]); QTest.qWait(20)

# Saved and discovered networks stay separate and retain their native actions.
networkRows = Rows([
    dict(Name='Saved Wi-Fi', Type=2, ConnectionPath='/saved', DevicePath='/wifi', SpecificPath='/ap', ConnectionState=0, SecurityType=6),
    dict(Name='Open Wi-Fi', Type=2, ConnectionPath='', DevicePath='/wifi', SpecificPath='/open', ConnectionState=0, SecurityType=0),
    dict(Name='Wired', Type=1, ConnectionPath='/wired', DevicePath='/ethernet', SpecificPath='', ConnectionState=0, SecurityType=0),
])
networkHandler = fake('''QtObject {
    property bool scanning: false
    property string action: ""
    property string path: ""
    property var calls: []
    function requestScan() { action="scan"; }
    function activateConnection(connection, device, specific) { action="activate"; path=connection; calls=[connection,device,specific]; }
    function deactivateConnection(connection, device) { action="deactivate"; path=connection; calls=[connection,device]; }
    function addAndActivateConnection(device, specific) { action="add"; path=specific; calls=[device,specific]; }
}''')
wireless.setProperty('wirelessEnabled',True)
wireless.setProperty('wirelessHwEnabled',True)
devices.setProperty('wirelessDeviceAvailable',True)
netMenu=component('WifiView.qml',{'wireless':wireless,'devices':devices,'handler':networkHandler,'connections':networkRows})
# Use production enum values, independent of NetworkManagerQt's numeric API.
enums=fake('''import org.kde.plasma.networkmanagement as Network
QtObject { property int wireless: Network.Enums.Wireless; property int wired: Network.Enums.Wired; property int activated: Network.Enums.Activated; property int activating: Network.Enums.Activating }''')
for index in (0,1):networkRows.update(index,'Type',enums.property('wireless'))
networkRows.update(2,'Type',enums.property('wired'))
def menuRows(menu, name):
    pending=[menu]; seen=set(); found=[]
    while pending:
        item=pending.pop()
        if item in seen:continue
        seen.add(item)
        if item.objectName()==name:found.append(item)
        pending.extend(item.children())
        if hasattr(item,'childItems'):pending.extend(item.childItems())
    return found
saved=next(r for r in menuRows(netMenu,'networkRow') if r.property('text')=='Saved Wi-Fi')
other=next(r for r in menuRows(netMenu,'otherNetworkRow') if r.property('text')=='Open Wi-Fi')
assert saved.property('visible') and saved.property('secured') and not other.property('visible')
click(saved);assert networkHandler.property('action')=='activate' and networkHandler.property('calls').toVariant()==['/saved','/wifi','/ap']
networkRows.update(0,'ConnectionState',enums.property('activated'))
assert saved.property('selected')
click(saved);assert networkHandler.property('action')=='deactivate' and networkHandler.property('calls').toVariant()==['/saved','/wifi']
click(child(netMenu,'otherNetworks'));assert netMenu.property('otherNetworksExpanded') and networkHandler.property('action')=='scan'
assert other.property('visible') and not other.property('secured')
click(other);assert networkHandler.property('action')=='add' and networkHandler.property('calls').toVariant()==['/wifi','/open']
networkRows.update(1,'ConnectionState',enums.property('activating'))
assert other.property('busy') and not other.property('enabled')
assert not any(r.property('visible') for r in menuRows(netMenu,'networkRow') if r.property('text')=='Wired')
networkHandler.setProperty('scanning',True);assert not child(netMenu,'scanNetworks').property('enabled')
wireless.setProperty('wirelessHwEnabled',False);assert not saved.property('enabled')
wireless.setProperty('wirelessHwEnabled',True)

screens = Rows([dict(displayName='test-display',label='External monitor',maxBrightness=100,brightness=60)])
control = fake('''QtObject {
    property var displays
    property bool isBrightnessAvailable: true
    property string selected: ""
    property int requested: -1
    function setBrightness(name, value) { selected=name; requested=value; }
}''')
control.setProperty('displays',screens)
display = component('DisplayView.qml', {'control':control})
brightness = child(display,'brightnessSlider')
assert brightness.property('value') == 60
screens.update(0,'brightness',35);assert brightness.property('value') == 35
brightness.setProperty('value',75)
QMetaObject.invokeMethod(brightness,'moved',Qt.ConnectionType.DirectConnection)
assert control.property('selected') == 'test-display' and control.property('requested') == 75

threeScreens=Rows([dict(displayName=name,label=name,maxBrightness=100,brightness=60)
                   for name in ('First monitor','Second monitor','Third monitor')])
control.setProperty('displays',threeScreens);QTest.qWait(30)
labels=[]
pending=[display]; seen=set()
while pending:
    item=pending.pop()
    if item in seen: continue
    seen.add(item)
    if item.objectName() == 'displayLabel': labels.append(item)
    pending.extend(item.children())
    if hasattr(item,'childItems'): pending.extend(item.childItems())
assert len(labels) == 3 and not any(label.property('visible') for label in labels)
display.setProperty('detailed', True); QTest.qWait(30)
assert all(label.property('visible') for label in labels)
assert {label.property('text') for label in labels} == {'First monitor','Second monitor','Third monitor'}

profiles = fake('''QtObject {
    property bool isPowerProfileDaemonInstalled: true
    property var profiles: ["power-saver","balanced","performance"]
    property string activeProfile: "balanced"
    property string profileError: ""
    property string requested: ""
    function setProfile(value) { requested=value; }
}''')
battery = fake('''QtObject {
    property bool hasInternalBatteries: false
    property int percent: 73
    property int state: 0
    property bool pluggedIn: true
}''')
power = component('BatteryView.qml',{'battery':battery,'profiles':profiles})
assert child(power,'batteryPercent').property('text') == 'No internal battery'
assert not child(power,'peripheralBattery').property('visible')
battery.setProperty('hasInternalBatteries',True);QTest.qWait(10)
assert child(power,'batteryPercent').property('text') == '73%'
battery.setProperty('percent',41);QTest.qWait(10)
assert child(power,'batteryPercent').property('text') == '41%'
profile = child(power,'powerProfile')
assert profile.property('currentIndex') == 1
profiles.setProperty('activeProfile','power-saver');QTest.qWait(10)
assert profile.property('currentIndex') == 0
assert profile.property('displayText') == 'Low Power'
profile.setProperty('currentIndex',2)
QMetaObject.invokeMethod(profile,'activated',Qt.ConnectionType.DirectConnection,Q_ARG(int,2))
assert profiles.property('requested') == 'performance'
battery.setProperty('pluggedIn',False);QTest.qWait(10)
assert child(power,'batterySource').property('text') == 'Power Source: Battery'
battery.setProperty('pluggedIn',True);QTest.qWait(10)
assert child(power,'batterySource').property('text') == 'Power Source: Power Adapter'
# Render and operate the styled selector through real input. KDE's desktop style
# expects a text input content item when placing its popup, even when read-only.
powerWindow=QQuickWindow();powerWindow.setGeometry(0,0,320,280)
power.setParentItem(powerWindow.contentItem());power.setWidth(280);power.setHeight(power.implicitHeight())
powerWindow.show();QTest.qWait(50)
position=profile.mapToScene(QPointF(profile.width()/2,profile.height()/2)).toPoint()
QTest.mouseClick(powerWindow,Qt.MouseButton.LeftButton,pos=position);QTest.qWait(30)
assert engine.newQObject(profile).property('popup').property('visible').toBool()
QTest.keyClick(powerWindow,Qt.Key.Key_Home);QTest.keyClick(powerWindow,Qt.Key.Key_Return);QTest.qWait(20)
assert profiles.property('requested') == 'power-saver'
powerWindow.close()



# Exercise actual pointer and keyboard activation, not only signal dispatch.
window = QQuickWindow(); window.setGeometry(0,0,100,40)
button = component('PanelButton.qml',{'symbol':'network-wireless','label':'Wi-Fi'})
button.setParentItem(window.contentItem());button.setWidth(40);button.setHeight(32)
activations=[];button.clicked.connect(lambda:activations.append(True))
window.show();QTest.qWait(30)
QTest.mouseClick(window,Qt.MouseButton.LeftButton,pos=QPoint(20,16));QTest.qWait(10)
assert len(activations)==1
button.forceActiveFocus();QTest.keyClick(window,Qt.Key.Key_Space);QTest.qWait(10)
assert len(activations)==2
window.close()


# The menu-bar clock is exactly as wide as its text, so its hover capsule gets
# room on both sides; other capsules stay the size of their item.
panel = fake("""import QtQuick.Layouts
Item {
    width: 400; height: 32
    GridLayout {
        Item {
            property Item applet: Item {
                objectName: "probeClock"; width: 120; height: 32
                property var plasmoid: ({ pluginName: "org.kde.plasma.digitalclock" })
                property bool expanded: false
            }
        }
        Item { Item { id: panelItem } }
    }
    StatusTrayStyle { panelItem: panelItem }
}""")
QTest.qWait(30)
clock = panel.findChild(QQuickItem, 'probeClock') or child(panel, 'probeClock')
capsules = [item for item in clock.childItems() if item.z() == -1]  # StatusTrayStyle's hover capsule
assert len(capsules) == 1, capsules
assert capsules[0].width() > clock.width(), (capsules[0].width(), clock.width())
assert capsules[0].x() == (clock.width() - capsules[0].width()) / 2  # centred on the text
clockWindow = QQuickWindow()
clockWindow.setGeometry(0, 0, 200, 50)
clock.setParentItem(clockWindow.contentItem())
clock.setX(40)
clockWindow.show()
QTest.mouseMove(clockWindow, QPoint(10, 42)); QTest.qWait(40)
assert not capsules[0].isVisible()
QTest.mouseMove(clockWindow, QPoint(62, 16)); QTest.qWait(40)
assert capsules[0].isVisible()
QTest.mouseMove(clockWindow, QPoint(10, 42)); QTest.qWait(40)
assert not capsules[0].isVisible()
clockWindow.close()
plain = fake('Item { width: 32; height: 32; PanelCapsule { objectName: "probePlainCapsule" } }')
assert child(plain, 'probePlainCapsule').width() == 32


# Changing a monochrome tray icon to a coloured, padded icon must undo
# the mask and measure its new visible bounds without changing the hit area.
from PyQt6.QtGui import QImage
for name, colour, inset in (("full", "#555555", 0), ("padded", "#bf1428", 3)):
    image = QImage(22, 22, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    for x in range(inset, 22-inset):
        for y in range(inset, 22-inset):
            image.setPixelColor(x, y, QColor(colour))
    assert image.save(str(applications / (name + ".png")))
trayWindow = QQuickWindow()
trayWindow.setGeometry(0, 0, 32, 32)
trayItem = fake('''import org.kde.kirigami as Kirigami
Item {
    width: 32; height: 32
    Kirigami.Icon { id: icon; objectName: "sampleGlyph"; width: 22; height: 22 }
    TrayArtwork { glyph: icon }
}''')
trayItem.setParentItem(trayWindow.contentItem())
trayWindow.show()
glyph = child(trayItem, "sampleGlyph")
for name, scale, mask in (("full", 16/22, True), ("padded", 1, False)):
    glyph.setProperty("source", QUrl.fromLocalFile(str(applications / (name + ".png"))))
    for attempt in range(60):
        QTest.qWait(50)
        if abs(glyph.scale()-scale) < .03 and glyph.property("isMask") == mask:
            break
    assert abs(glyph.scale()-scale) < .03, (name, glyph.scale(), errors)
    assert glyph.property("isMask") == mask
trayWindow.close()


# The capsule is absent at rest and appears for hover, drag or keyboard focus.
window = QQuickWindow(); window.setGeometry(0,0,260,100)
glass = component('GlassSlider.qml', {'width':200, 'height':22, 'value':0.5})
glass.setParentItem(window.contentItem()); glass.setX(30); glass.setY(30)
thumb = child(glass, 'glassSliderHandle')
window.show(); QTest.mouseMove(window,QPoint(250,90)); QTest.qWait(200)
assert thumb.opacity() == 0
centre = thumb.x()+thumb.width()/2
QTest.mouseMove(window,QPoint(130,41)); QTest.qWait(200)
assert glass.property('hovered') and thumb.opacity() == 1
assert thumb.width() > thumb.height()
assert thumb.x()+thumb.width()/2 == centre and glass.property('value') == 0.5
QTest.mousePress(window,Qt.MouseButton.LeftButton,pos=QPoint(130,41))
QTest.mouseMove(window,QPoint(190,41)); QTest.qWait(30)
QTest.mouseRelease(window,Qt.MouseButton.LeftButton,pos=QPoint(190,41))
assert glass.property('value') > 0.7
QTest.mouseMove(window,QPoint(250,90)); QTest.qWait(200)
assert thumb.opacity() == 0  # A mouse click must not leave a persistent knob.
glass.setFocus(False); glass.forceActiveFocus(Qt.FocusReason.TabFocusReason); QTest.qWait(200)
value = glass.property('value')
QTest.keyClick(window,Qt.Key.Key_Left)
assert glass.property('value') < value and thumb.opacity() == 1
glass.setProperty('enabled',False); QTest.qWait(200)
assert thumb.opacity() == 0
window.close()


class History(Rows):
    def __init__(self):
        super().__init__([dict(applicationIconName='dialog-information',applicationName='Test app',
            isGroup=False,isGroupExpanded=False,closable=True,summary='Message',body='Body',type=1,
            percentage=0,hasDefaultAction=True,actionNames=['test-action'],actionLabels=['Run action'],
            jobState=1,suspendable=True,killable=True,hasReplyAction=True)])
        self.calls=[]
    @pyqtProperty(int,constant=True)
    def count(self): return 1
    @pyqtProperty(int,constant=True)
    def expiredNotificationsCount(self): return 1
    @pyqtSlot(QModelIndex)
    def invokeDefaultAction(self,index): self.calls.append(('open',index.row()))
    @pyqtSlot(QModelIndex,str)
    def invokeAction(self,index,action): self.calls.append(('action',index.row(),action))
    @pyqtSlot(QModelIndex,str,int)
    def reply(self,index,text,flags): self.calls.append(('reply',index.row(),text,flags))
    @pyqtSlot(QModelIndex)
    def suspendJob(self,index): self.calls.append(('pause',index.row()))
    @pyqtSlot(QModelIndex)
    def resumeJob(self,index): self.calls.append(('resume',index.row()))
    @pyqtSlot(QModelIndex)
    def killJob(self,index): self.calls.append(('cancel',index.row()))
    @pyqtSlot(QModelIndex)
    def stopTimeout(self,index): self.calls.append(('stop-timeout',index.row()))
    @pyqtSlot(QModelIndex)
    def close(self,index): self.calls.append(('close',index.row()))
    @pyqtSlot(QModelIndex)
    def expire(self,index): self.calls.append(('expire',index.row()))
    @pyqtSlot(int)
    def clear(self,flags): self.calls.append(('clear',flags))
    def setData(self,index,value,role):
        self.calls.append(('group',index.row(),value));return True
history=History()
notifications=component('NotificationsView.qml',{'history':history})
notifications.setWidth(344);notifications.setHeight(700);QTest.qWait(30)
assert child(notifications,'notificationCard').width() == 316
click(child(notifications,'notificationOpen'));assert history.calls[-1]==('open',0)
click(child(notifications,'notificationAction'));assert history.calls[-1]==('action',0,'test-action')
# The production notification popup uses the launcher's shared menu renderer.
options = child(notifications, 'notificationOptionsMenu')
assert options.property('fitContents')
QMetaObject.invokeMethod(options, 'moveSelection', Q_ARG('QVariant', 1))
assert options.property('selectedIndex') == 1  # Skip the hidden group action.
QMetaObject.invokeMethod(options, 'activate', Q_ARG('QVariant', 1))
assert history.calls[-1] == ('open', 0) and not options.property('visible')
history.update(0, 'actionNames', [])
history.update(0, 'actionLabels', [])
QTest.qWait(20)
history.update(0, 'actionLabels', ['Replacement action'])
history.update(0, 'actionNames', ['replacement'])
QTest.qWait(20)
click(child(notifications, 'notificationAction'))
assert history.calls[-1] == ('action', 0, 'replacement')
reply=child(notifications,'notificationReply');send=child(notifications,'notificationSend')
assert not send.property('enabled')
reply.setProperty('text','A reply');QTest.qWait(10);click(send)
assert history.calls[-1][:3]==('reply',0,'A reply') and reply.property('text')==''
click(child(notifications,'notificationPause'));assert history.calls[-1]==('pause',0)
history.update(0,'jobState',2)
click(child(notifications,'notificationPause'));assert history.calls[-1]==('resume',0)
click(child(notifications,'notificationCancel'));assert history.calls[-1]==('cancel',0)
click(child(notifications,'notificationDismiss'));assert history.calls[-1]==('close',0)
click(child(notifications,'clearHistory'));assert history.calls[-1][0]=='clear'
history.update(0,'isGroup',True)
click(child(notifications,'notificationGroup'));assert history.calls[-1]==('group',0,True)


# Render the real native banner across palette changes without reconstructing it.
# A new QQuickWindow must follow its host rather than freezing its initial theme.
role = fake('''QtObject {
    property string notificationId: "1"
    property string applicationIconName: "dialog-information"
    property string applicationName: "Notify Me"
    property string summary: "A persistent notification"
    property string body: "The text and surface follow the current mode."
    property bool isGroup: false
    property bool isGroupExpanded: false
    property bool closable: true
    property bool hasDefaultAction: false
    property bool hasReplyAction: false
    property bool suspendable: false
    property bool killable: false
    property int type: 1
    property int urgency: 2
    property int timeout: 0
    property int jobState: 0
    property int percentage: 0
    property bool resident: false
    property var actionNames: []
    property var actionLabels: []
}''')
notice = component(str(notices / 'NotificationPopup.qml'), {'model':role, 'index':0,
                   'history':history, 'settings':noticeHost.property('settings')})
notice.setProperty('visible', True)
from PyQt6.QtGui import QColor
frames=[]
for dark in (False, True, False):
    notice.setProperty('foregroundColor', QColor('white' if dark else 'black'))
    notice.setProperty('backgroundColor', QColor('black' if dark else 'white'))
    # Compare settled pixels after the 50 ms hold and 250 ms transition.
    QTest.qWait(400)
    assert child(notice,'notificationCard').property('lightMode') != dark
    rendered=notice.grabWindow(); assert not rendered.isNull()
    text=[rendered.pixelColor(x,y) for x in range(68,rendered.width()-24)
          for y in range(26,rendered.height()-25)
          if rendered.pixelColor(x,y).alphaF() > .95]
    assert text and (sum(p.lightnessF() for p in text)/len(text) > .5) == dark
    frames.append(rendered.constBits().asstring(rendered.sizeInBytes()))
assert frames[0] != frames[1] and frames[0] == frames[2]
# Jobs stay on KDE's job-expiry path rather than the notification-member model.
role.setProperty('type', 2)
QMetaObject.invokeMethod(child(notice, 'notificationExpiry'), 'triggered')
assert history.calls[-1] == ('expire', 0)
notice.close()


# Only physical active links belong in the overview; bridges must not leak.
summaryRows=Rows([dict(Type=4,ConnectionState=2,Name='docker0'),
                  dict(Type=13,ConnectionState=2,Name='Ethernet LAN'),
                  dict(Type=14,ConnectionState=0,Name='Offline Wi-Fi')])
overview=component('ControlView.qml', {'connections':summaryRows, 'batteryState':battery})
summary=child(overview,'connectionSummary')
assert summary.property('subtitle') == 'Connected'
assert summary.property('text') == 'Network'
battery.setProperty('hasInternalBatteries',False);QTest.qWait(10)
assert not child(overview,'batteryTile').property('visible')
battery.setProperty('hasInternalBatteries',True);QTest.qWait(10)
assert child(overview,'batteryTile').property('visible')
summaryRows.update(1,'ConnectionState',0)
summaryRows.update(2,'ConnectionState',2);QTest.qWait(10)
assert summary.property('subtitle') == 'Offline Wi-Fi'
assert summary.property('text') == 'Wi-Fi'



preferences=fake('QtObject { property bool showAudio: true }')
overview.setProperty('preferences',preferences)
click(child(overview,'editControlsButton'))
assert overview.property('section') == 'EditControls.qml'
editor=overview
audioChoice=child(editor,'showAudio');assert audioChoice.property('checked')
audioChoice.setProperty('checked',False);click(audioChoice)
assert not preferences.property('showAudio')
preferences.setProperty('showAudio',True);QTest.qWait(10)
assert audioChoice.property('checked')

# Render the production tile over transparency with each edition's SVG marker.
# An edition-local gradient must not survive compositor gradient exclusion.
import tempfile
from PyQt6.QtGui import QPalette, QColor
with tempfile.TemporaryDirectory() as directory:
    for golden in (False, True):
        svg = Path(directory) / ('golden.svg' if golden else 'tahoe.svg')
        marker = '<rect id="hint-clear-surface" width="1" height="1"/>' if golden else ''
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">' + marker + '</svg>')
        tile_source = (root / 'ControlTile.qml').read_text().replace('imagePath: "dialogs/background"', 'imagePath: "' + str(svg) + '"')
        c = QQmlComponent(engine)
        c.setData(tile_source.encode(), QUrl.fromLocalFile(str(root / 'tile-probe.qml')))
        assert c.isReady(), [e.toString() for e in c.errors()]
        tile = c.create(); assert tile is not None
        keep.extend([c, tile])
        tile_window = QQuickWindow(); tile_window.setColor(QColor(Qt.GlobalColor.transparent))
        tile_window.setGeometry(0,0,200,120)
        tile.setParentItem(tile_window.contentItem());tile.setWidth(200);tile.setHeight(120)
        tile_window.show(); QTest.qWait(80)
        assert tile.property('goldenGate') == golden
        for light in (True, False, True):
            palette = QPalette(app.palette())
            palette.setColor(QPalette.ColorRole.WindowText, QColor('black' if light else 'white'))
            palette.setColor(QPalette.ColorRole.Window, QColor('white' if light else 'black'))
            app.setPalette(palette);QTest.qWait(80)
            assert tile.property('lightMode') == light
            image = tile_window.grabWindow();assert not image.isNull()
            top,bottom = image.pixelColor(100,25),image.pixelColor(100,95)
            assert top == bottom, ('Tile contains a vertical tint', golden,light,top.getRgb(),bottom.getRgb())
            expected = 46 if light else 31
            assert abs(top.alpha() - expected) <= 2, ('Tile fill changed',golden,light,top.getRgb())
        tile_window.close()

assert not errors, '\n'.join(errors)
# Destroy QML consumers while their Python-owned model fixtures are still
# alive. Interpreter shutdown otherwise destroys these in arbitrary order.
from PyQt6 import sip
QMetaObject.invokeMethod(noticeHost, 'removeHost'); QTest.qWait(30)
for value in reversed(keep):
    if not sip.isdeleted(value):
        sip.delete(value)
sip.delete(engine)
print('DESKTOP_CONTROLS_OK: native imports, external audio changes, mute, unavailable output, wireless requests, hardware blocking, unavailable adapter, notification inhibition ownership')
