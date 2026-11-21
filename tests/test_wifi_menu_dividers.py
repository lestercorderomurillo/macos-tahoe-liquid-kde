"""The Wi-Fi menu never shows two dividers in a row."""
import re
from pathlib import Path

WIFI = Path(__file__).resolve().parents[1] / (
    "src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/WifiView.qml")


def test_divider_before_network_list_hides_with_the_list():
    # Without Wi-Fi the network list is hidden, so the divider after the
    # wired rows would sit right above the one before "Wi-Fi Settings…".
    text = WIFI.read_text()
    match = re.search(r"StatusMenuDivider\s*\{([^}]*)\}\s*QQC\.ScrollView\s*\{\s*id:\s*networkScroll", text)
    assert match, "the network list must follow a divider"
    assert re.search(r"visible:\s*networkScroll\.visible", match.group(1))
