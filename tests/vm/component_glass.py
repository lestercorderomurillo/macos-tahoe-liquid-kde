#!/usr/bin/env python3
"""Qualify the requested Dock defaults through the installed KCM in a disposable VM.

Leaves all three material profiles at factory values, with the edition default
selected. Never run against the user's desktop.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE / "src/scripts"))
from release_capture_guest import session, run, plasma, windows, wait_for_dock_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("tahoe", "golden-gate"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    session()  # Requires the disposable QEMU DMI marker before any write.
    expected_edition = "MacTahoe" if args.edition == "tahoe" else "MacGoldenGate"
    marker = Path.home() / ".local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher/contents/edition"
    assert marker.read_text().strip() == expected_edition, "Wrong installed edition"
    assert json.loads((SOURCE / "src/scripts/defaults.json").read_text())["wallpaper"] == expected_edition
    from PIL import Image, ImageChops, ImageStat
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    build = output / "native"
    build.mkdir(exist_ok=True)
    (build / "CMakeLists.txt").write_text("""cmake_minimum_required(VERSION 3.22)
project(ComponentGlassProbe LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
find_package(ECM REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
find_package(Qt6 REQUIRED COMPONENTS Widgets)
find_package(KF6 REQUIRED COMPONENTS KCMUtils CoreAddons)
add_executable(component-apply """ + str(SOURCE / "tests/glass/component_apply.cpp") + """)
target_link_libraries(component-apply PRIVATE Qt6::Widgets KF6::KCMUtils KF6::CoreAddons)
""")
    run("cmake", "-S", str(build), "-B", str(build / "build"), timeout=120)
    run("cmake", "--build", str(build / "build"), "-j2", timeout=180)
    executable = build / "build/component-apply"
    plugin = Path(run("qtpaths6", "--plugin-dir")) / "kwin/effects/configs/kwin_liquidglass_config.so"
    expected = {"BlurStrength": 5.0, "MagnifyGlassStrength": .1,
                "BlurCoverage": .98, "SurfaceTransparencyLight": 98.5,
                "SurfaceTransparencyDark": 98.5, "DarkGradientOverlay": False}
    edition_preset = 0 if args.edition == "tahoe" else 2
    records = []

    def apply(**request):
        path = output / "request.json"
        path.write_text(json.dumps({"component": "dock", "values": {}, **request}))
        return json.loads(run(str(executable), str(plugin), str(path), timeout=60).splitlines()[-1])

    def saved(key="ComponentMaterials"):
        return json.loads(run("kreadconfig6", "--file", "kwinrc", "--group", "Effect-liquidglass", "--key", key))

    def check_dock():
        dock = saved()["dock"]
        assert all(dock[k] == v for k, v in expected.items()), dock
        assert apply(save=False) == expected
        return wait_for_dock_geometry()

    def capture(name):
        check_dock()
        path = output / (name + ".png")
        previous = None
        for _ in range(20):
            run("spectacle", "-b", "-n", "-f", "-o", str(path), timeout=30)
            with Image.open(path) as image:
                current = image.convert("RGB").copy()
            if previous is not None and current.tobytes() == previous.tobytes():
                return current
            previous = current
            time.sleep(.2)
        raise RuntimeError("Dock frame did not settle")

    wallpaper = (Path.home() / ".local/share/wallpapers" / expected_edition).as_uri()
    plasma('desktops().forEach(d=>{d.wallpaperPlugin="org.kde.image";'
           'd.currentConfigGroup=["Wallpaper","org.kde.image","General"];'
           'd.writeConfig("Image",' + json.dumps(wallpaper) + ');});')
    # Factory restoration is deliberate fixture setup, never a disguised
    # restoration of a previously mutated test configuration.
    for preset in range(3):
        assert apply(preset=preset, restore=True) == expected
        records.append({"preset": preset, "factory_dock": saved()["dock"]})
    baseline_profiles = saved("ComponentMaterialProfiles")
    try:
        apply(preset=edition_preset)
        before = saved()
        # Opening/changing a control without Apply must not leak test settings.
        apply(values={"DarkGradientOverlay": True, "BlurStrength": 9.0}, save=False)
        assert saved() == before
        check_dock()
        # Applying another component must leave every Dock parameter unchanged.
        apply(component="apps", values={"BlurStrength": 7.0})
        changed = saved()
        assert changed["apps"]["BlurStrength"] == 7.0
        assert all(changed[key] == value for key, value in before.items() if key != "apps")
        apply(component="apps", values={"BlurStrength": before["apps"]["BlurStrength"]})
        assert saved() == before
        assert saved("ComponentMaterialProfiles") == baseline_profiles
        windows("workspace.windowList().filter(w=>!w.dock && !w.desktop).forEach(w=>w.minimized=true);")
        switch = str(Path.home() / ".local/bin/mac-tahoe-theme-switch")
        for appearance in ("light", "dark"):
            run(switch, appearance, timeout=180)
            reference = None
            for preset in range(3):
                assert apply(preset=preset) == expected
                frame = capture(f"preset-{preset}-{appearance}")
                docks = [w for w in windows() if w["type"] == 2 and w["geometry"]["y"] > 0]
                assert len(docks) == 1, docks
                g = docks[0]["geometry"]
                # The pinned VM uses 3840x2160 at scale 2.
                crop = frame.crop(tuple(round(2 * n) for n in (g["x"], g["y"], g["x"] + g["width"], g["y"] + g["height"])))
                if reference is not None:
                    assert crop.size == reference.size, "Preset changed Dock geometry"
                    difference = ImageStat.Stat(ImageChops.difference(reference, crop)).mean
                    assert max(difference) < 1.0, ("Preset changed Dock pixels", appearance, preset, difference)
                reference = crop
                records.append({"preset": preset, "appearance": appearance, "dock": saved()["dock"],
                                "capture_sha256": hashlib.sha256((output / f"preset-{preset}-{appearance}.png").read_bytes()).hexdigest()})
        records.append({"cancel": "passed", "component_isolation": "passed", "preset_pixel_consistency": "passed"})
    finally:
        # No enabled gradient, custom blur or alpha may survive qualification.
        for preset in range(3):
            assert apply(preset=preset, restore=True) == expected
        apply(preset=edition_preset)
        check_dock()
    profiles = saved("ComponentMaterialProfiles")
    assert profiles == baseline_profiles
    records.append({"final_profiles": profiles, "final_preset": edition_preset})
    (output / "results.json").write_text(json.dumps(records, indent=2))
    print("COMPONENT_GLASS_INTENT_PASSED", args.edition)


if __name__ == "__main__":
    main()
