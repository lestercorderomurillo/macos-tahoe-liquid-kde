"""Run production controls on a private bus, with deterministic hardware changes."""
import sys
from pathlib import Path
from PyQt6.QtCore import (QAbstractListModel, QModelIndex, QObject, QUrl, QMetaObject,
                         Qt, QPoint, pyqtSlot, pyqtProperty, qInstallMessageHandler)
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtWidgets import QApplication
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtTest import QTest

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
    c.setData(('import QtQuick\n' + source).encode(), QUrl())
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
    QMetaObject.invokeMethod(obj, 'clicked', Qt.ConnectionType.DirectConnection)
    QTest.qWait(10)

# Native imports must load even when the desktop services and hardware are absent.
for name in ('ControlView.qml','BatteryView.qml','WifiView.qml','NotificationsView.qml'):
    component(name)

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
battery.setProperty('hasInternalBatteries',True);QTest.qWait(10)
assert child(power,'batteryPercent').property('text') == '73%'
battery.setProperty('percent',41);QTest.qWait(10)
assert child(power,'batteryPercent').property('text') == '41%'
profile = child(power,'powerProfile')
assert profile.property('currentIndex') == 1
profiles.setProperty('activeProfile','power-saver');QTest.qWait(10)
assert profile.property('currentIndex') == 0


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
    def close(self,index): self.calls.append(('close',index.row()))
    @pyqtSlot(int)
    def clear(self,flags): self.calls.append(('clear',flags))
    def setData(self,index,value,role):
        self.calls.append(('group',index.row(),value));return True
history=History()
notifications=component('NotificationsView.qml',{'history':history})
notifications.setWidth(400);notifications.setHeight(700);QTest.qWait(30)
click(child(notifications,'notificationOpen'));assert history.calls[-1]==('open',0)
click(child(notifications,'notificationAction'));assert history.calls[-1]==('action',0,'test-action')
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

networkHandler = fake('''QtObject {
    property bool scanning: false
    property var calls: []
    function activateConnection(path,device,specific) { calls = ["activate",path,device,specific]; }
    function deactivateConnection(path,device) { calls = ["deactivate",path,device]; }
    function addAndActivateConnection(device,specific) { calls = ["new",device,specific]; }
}''')
networks=Rows([dict(Type=14,ConnectionState=0,ConnectionPath='/saved',DevicePath='/device',SpecificPath='/ap',Name='Test Wi-Fi',ConnectionIcon='network-wireless')])
wireless.setProperty('wirelessEnabled',True);devices.setProperty('wirelessDeviceAvailable',True)
netView=component('WifiView.qml',{'wireless':wireless,'devices':devices,'handler':networkHandler,'connections':networks})
netView.setWidth(400);netView.setHeight(500);QTest.qWait(30)
networkRow=child(netView,'networkRow');assert networkRow.property('visible')
click(networkRow);assert networkHandler.property('calls').toVariant()==['activate','/saved','/device','/ap']
networks.update(0,'ConnectionState',2)
click(networkRow);assert networkHandler.property('calls').toVariant()==['deactivate','/saved','/device']
networks.update(0,'ConnectionState',0);networks.update(0,'ConnectionPath','')
click(networkRow);assert networkHandler.property('calls').toVariant()==['new','/device','/ap']


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
print('DESKTOP_CONTROLS_OK: native imports, external audio changes, mute, unavailable output, wireless requests, hardware blocking, unavailable adapter, notification inhibition ownership')
