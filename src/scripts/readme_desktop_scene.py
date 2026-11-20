"""Capture desktop components over the edition wallpaper, and the actual wizard pages."""

import json
import time

from PIL import Image, ImageStat
from release_screenshots import INSTALLER_PAGES, require


def open_notification_history(vm):
    widgets = json.loads(
        vm.action(
            "plasma",
            'var a=[];panels().forEach(p=>p.widgets().forEach(w=>{if(w.type.endsWith(".notifications"))a.push(w.geometry)}));print(JSON.stringify(a))',
        )
    )
    require(len(widgets) == 1, "Missing notification history button")
    g = widgets[0]
    vm.click(round(2 * g["x"] + g["width"]), round(2 * g["y"] + g["height"]))
    time.sleep(0.6)


def clear_notification_history(vm, snapshot):
    open_notification_history(vm)
    _, record = snapshot()
    matches = [
        w
        for w in record["windows"]
        if w["caption"] == "mttkde-notifications" and not w["hidden"]
    ]
    require(len(matches) == 1, "Cannot clear notification history")
    g = matches[0]["geometry"]
    vm.click(2 * (g["x"] + g["width"] - 20), 2 * (g["y"] + 22))
    time.sleep(0.3)
    vm.click(1200, 890)


def photograph_desktop(vm, edition, mode, guest, snapshot, save, taken):
    def visible(record):
        return [w for w in record["windows"] if not w["hidden"]]

    def panel(case, title, identifier):
        widgets = json.loads(
            vm.action(
                "plasma",
                'var a=[]; panels().forEach(p=>{if(p.location==="top")p.widgets().forEach(w=>a.push({id:w.type,g:w.geometry}));}); print(JSON.stringify(a));',
            )
        )
        geometry = next(w["g"] for w in widgets if w["id"].endswith("." + identifier))
        vm.click(
            round(geometry["x"] * 2 + geometry["width"]),
            round(geometry["y"] * 2 + geometry["height"]),
        )
        vm.move(900, 700)
        time.sleep(0.9)
        try:
            im, record = snapshot()
            matches = [w for w in visible(record) if w["caption"] == title]
            require(len(matches) == 1, f"Wrong window for {case}")
            x, y, width, height = [
                matches[0]["geometry"][key] * 2 for key in ("x", "y", "width", "height")
            ]
            save(im.crop((x, y, x + width, y + height)), record, case)
        finally:
            vm.click(1200, 890)

    vm.action("clean-desktop")
    for case, identifier in [
        ("wifi", "wifi"),
        ("battery", "battery"),
        ("calendar", "digitalclock"),
        ("control", "controlcenter"),
        ("notifications", "notifications"),
    ]:
        if taken(case):
            continue
        if case == "notifications":
            clear_notification_history(vm, snapshot)
            guest("notify")
        title = {"control": "control-center"}.get(case, case)
        panel(case, "mttkde-" + title, identifier)
    vm.action("launcher")
    vm.move(900, 700)
    time.sleep(1)
    im, record = snapshot()
    require(
        any(
            w["caption"].startswith("mttkde-") and w["appletPopup"]
            for w in visible(record)
        ),
        "Missing launcher",
    )
    save(im, record, "launcher")
    vm.key("esc")
    vm.click(1200, 890)
    vm.click(2600, 980, "right")
    time.sleep(0.6)
    im, record = snapshot()
    require(
        any(
            "plasma" in w["resourceClass"] and w["type"] not in (1, 2)
            for w in visible(record)
        ),
        "Missing context menu",
    )
    save(im, record, "context")
    vm.key("esc")
    vm.action("launch", "about")
    vm.action(
        "arrange",
        json.dumps(
            {
                "About This Computer (preview)": {
                    "x": 720,
                    "y": 160,
                    "width": 400,
                    "height": 740,
                }
            }
        ),
    )
    im, record = snapshot()
    require(
        any("About This Computer" in w["caption"] for w in visible(record)),
        "Missing system information",
    )
    save(im, record, "about")
    vm.action("clean-desktop")
    for page in INSTALLER_PAGES:
        if taken("installer-" + page):
            continue
        state = vm.action("wizard", page)
        im, record = snapshot()
        require(
            state["page"] == page
            and any(
                w["caption"] == state["title"] and w["active"] for w in visible(record)
            ),
            "Wrong wizard page: " + page,
        )
        save(im, dict(record, page=page), "installer-" + page)
    vm.action("clean-desktop")
    photograph_materials(vm, edition, mode, guest, snapshot, save, taken)


def photograph_materials(vm, edition, mode, guest, snapshot, save, taken):
    def one(im, record, case, match):
        wins = [w for w in record["windows"] if not w["hidden"] and match(w)]
        require(len(wins) == 1, f"Cannot identify {case}")
        g = wins[0]["geometry"]
        box = (
            max(0, 2 * g["x"] - 12),
            max(0, 2 * g["y"] - 12),
            min(im.width, 2 * (g["x"] + g["width"]) + 12),
            min(im.height, 2 * (g["y"] + g["height"]) + 12),
        )
        save(im.crop(box), record, case)

    clear_notification_history(vm, snapshot)
    guest("notify-group")
    open_notification_history(vm)
    vm.move(900, 700)
    time.sleep(0.6)
    im, record = snapshot()
    one(
        im,
        record,
        "notification-history",
        lambda w: w["caption"] == "mttkde-notifications",
    )
    vm.click(1200, 890)
    guest("clipboard")
    vm.action("launcher")
    time.sleep(0.7)
    im, record = snapshot()
    apps = next(
        w
        for w in record["windows"]
        if w["caption"] == "mttkde-apps" and not w["hidden"]
    )
    search = next(
        (
            w
            for w in record["windows"]
            if w["caption"] == "mttkde-search" and not w["hidden"]
        ),
        apps,
    )
    g = search["geometry"]
    vm.click(round(2 * g["x"] + g["width"]), round(2 * g["y"] + min(48, g["height"])))
    vm.remote(
        "sudo",
        "python3",
        "/home/tester/release-capture/source/tests/vm/clipboard_input.py",
        "29",
        "5",
    )
    vm.move(900, 700)
    time.sleep(1)
    im, record = snapshot()
    one(im, record, "clipboard", lambda w: w["caption"] == "mttkde-apps")
    vm.key("esc")
    vm.click(1000, 900)
    vm.action("clean-desktop")
    for style in (
        "regular",
        "clear",
        "red",
        "blue",
        "green",
        "orange",
        "purple",
        "gray",
        "yellow",
        "pink",
    ):
        if taken("dock-" + style):
            continue
        evidence = guest("dock", style, mode)
        vm.action(
            "plasma",
            'panels().forEach(p=>{if(p.location==="bottom")p.hiding="none";});',
        )
        vm.move(1910, 2159)
        time.sleep(0.6)
        vm.move(900, 700)
        time.sleep(0.6)
        im, record = snapshot()
        require(
            not any(w["type"] == 0 for w in record["windows"]),
            "An extra application is visible in the Dock",
        )
        one(
            im,
            dict(record, **evidence),
            "dock-" + style,
            lambda w: w["type"] == 2 and w["geometry"]["y"] > 100,
        )
    guest("dock", "regular", mode)

    if mode == "light" and not taken("boot"):
        vm.action("boot")
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            from pathlib import Path

            frame = Path(folder) / "boot.png"
            vm.get(
                "/home/tester/release-capture/source/tests/vm/output/plymouth-boot-splash.png",
                frame,
            )
            with Image.open(frame) as im:
                save(
                    im.copy(),
                    {
                        "renderer": "Plymouth",
                        "source_frame": "plymouth-boot-splash.png",
                    },
                    "boot",
                )


def verify_dock_tints(red_path, blue_path, pins):
    """Check the photographed Apps icon and every pin against both calibration tints."""

    def chroma(path):
        with Image.open(path) as image:
            image = image.convert("RGB")
            # The panel crop includes the outer margin and one cell for Trash.
            pitch = image.width / (len(pins) + 2.57)
            samples = []
            for i in range(len(pins) + 1):
                center = (i + 0.79) * pitch
                patch = image.crop(
                    (
                        round(center - 0.24 * pitch),
                        round(image.height * 0.34),
                        round(center + 0.24 * pitch),
                        round(image.height * 0.7),
                    )
                )
                red, _, blue = ImageStat.Stat(patch).mean
                samples.append(red - blue)
            return image.size, samples

    red_size, red = chroma(red_path)
    blue_size, blue = chroma(blue_path)
    require(red_size == blue_size, "Dock layout changed between tints")
    for name, warm, cool in zip(["Apps", *pins], red, blue, strict=True):
        require(warm > 5 and cool < -5, f"Missing rendered Dock tint for {name}")
