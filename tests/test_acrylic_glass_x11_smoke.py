"""Load a caller-provided Acrylic Glass X11 module in an isolated KWin."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_kwin_x11_loads_exact_acrylic_glass_module(tmp_path):
    plugin = os.environ.get("MTTKDE_X11_PLUGIN")
    if not plugin:
        pytest.skip("Set MTTKDE_X11_PLUGIN to a freshly built liquidglass_x11.so")
    plugin = Path(plugin).resolve()
    if not plugin.is_file():
        pytest.fail(f"X11 plugin does not exist: {plugin}")
    for binary in ("Xvfb", "xdpyinfo", "kwin_x11", "dbus-run-session", "qdbus6"):
        if not shutil.which(binary):
            pytest.fail(f"{binary} required for isolated KWin X11 smoke test")

    root = tmp_path.resolve()
    expected_hash = hashlib.sha256(plugin.read_bytes()).hexdigest()
    script = r'''
root="$1"
source_plugin="$2"
plugins="$root/qt6/plugins/kwin-x11/effects/plugins"
mkdir -p "$plugins" "$root/config" "$root/data" "$root/cache" \
    "$root/home" "$root/runtime"
chmod 700 "$root/runtime"
cp "$source_plugin" "$plugins/liquidglass.so"
Xvfb -displayfd 1 -screen 0 1280x800x24 -nolisten tcp \
    >"$root/display" 2>"$root/xvfb.log" &
xvfb=$!
kwin=
cleanup() {
    [ -z "$kwin" ] || kill "$kwin" 2>/dev/null || true
    kill "$xvfb" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT
for _ in $(seq 1 100); do
    [ -s "$root/display" ] && break
    sleep 0.1
done
display=$(cat "$root/display")
[[ "$display" =~ ^[0-9]+$ ]] || { cat "$root/xvfb.log"; exit 1; }
kill -0 "$xvfb"
export DISPLAY=":$display"
xdpyinfo >/dev/null
export QT_QPA_PLATFORM=xcb
export QT_PLUGIN_PATH="$root/qt6/plugins"
export QT_USE_PORTAL=0
export XDG_CONFIG_HOME="$root/config"
export XDG_DATA_HOME="$root/data"
export XDG_CACHE_HOME="$root/cache"
export XDG_RUNTIME_DIR="$root/runtime"
export HOME="$root/home"
kwin_x11 --no-kactivities >"$root/kwin.log" 2>&1 &
kwin=$!
ready=false
for _ in $(seq 1 150); do
    if qdbus6 org.kde.KWin /KWin org.kde.KWin.supportInformation \
        >/dev/null 2>&1; then
        ready=true
        break
    fi
    kill -0 "$kwin" 2>/dev/null || break
    sleep 0.1
done
[ "$ready" = true ] || { cat "$root/kwin.log"; exit 1; }
owner=$(qdbus6 org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.GetConnectionUnixProcessID org.kde.KWin)
[ "$owner" = "$kwin" ] || { echo 'Private compositor identity mismatch'; exit 1; }
loaded=$(qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect liquidglass)
[ "$loaded" = true ] || { cat "$root/kwin.log"; exit 1; }
grep -Fxq true <(qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.isEffectLoaded liquidglass)
grep -Fxq true <(qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.isEffectSupported liquidglass)
grep -Fxq liquidglass <(qdbus6 org.kde.KWin /Effects org.freedesktop.DBus.Properties.Get org.kde.kwin.Effects activeEffects)
grep -Fxq true <(qdbus6 org.kde.KWin /Compositor org.freedesktop.DBus.Properties.Get org.kde.kwin.Compositing active)
grep -F "$plugins/liquidglass.so" "/proc/$kwin/maps" >/dev/null

'''
    env = {key: value for key, value in os.environ.items() if key in ("PATH", "LANG")}
    log_path = root / "smoke.log"
    with log_path.open("w") as log:
        result = subprocess.run(
            ["dbus-run-session", "--", "bash", "-euc", script, "x11-smoke",
             str(root), str(plugin)],
            env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90,
        )
    assert result.returncode == 0, log_path.read_text(encoding="utf-8")
    assert hashlib.sha256(plugin.read_bytes()).hexdigest() == expected_hash
