"""Photograph the same document, desktop and active menus in both appearances."""

import csv
import io
import json
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter
from release_screenshots import digest, require


def photograph(vm, profile, edition, output, manifest, *, materials_only=False):
    import fcntl

    with (output / ".photograph.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _photograph(vm, profile, edition, output, manifest, materials_only)


def _photograph(vm, profile, edition, output, manifest, materials_only):
    helper = Path(__file__).with_name("readme_shell_guest.py")
    manifest["capture_tools"] = {
        p.name: digest(p)
        for p in (
            helper,
            Path(__file__),
            helper.with_name("readme_desktop_scene.py"),
            helper.with_name("readme_dock_photo.py"),
        )
    }
    manifest["scene_sha256"] = digest(helper)
    manifest["controller_sha256"] = digest(Path(__file__))
    vm.put(helper, "/home/tester/release-capture/readme_shell_guest.py")
    dock = helper.with_name("readme_dock_photo.py")
    vm.put(dock, "/home/tester/release-capture/readme_dock_photo.py")

    def guest(action, *args):
        return json.loads(
            vm.remote(
                "python3",
                "/home/tester/release-capture/readme_shell_guest.py",
                action,
                edition,
                *args,
            ).splitlines()[-1]
        )

    def snapshot():
        record = guest("snapshot")
        path = output / ("current-" + edition + ".png")
        vm.get("/home/tester/release-capture/readme.png", path)
        with Image.open(path) as im:
            require(list(im.size) == profile["resolution"], "Unexpected display size")
            return im.convert("RGB"), record

    def words(im):
        buf = io.BytesIO()
        im.save(buf, "PNG")
        tsv = subprocess.check_output(
            [
                "tesseract",
                "stdin",
                "stdout",
                "--psm",
                "6",
                "-c",
                "tessedit_create_tsv=1",
            ],
            input=buf.getvalue(),
            stderr=subprocess.DEVNULL,
        )
        return list(csv.DictReader(io.StringIO(tsv.decode()), delimiter="\t"))

    def save(im, record, case):
        name = f"readme-{edition}-{mode}-{case}"
        if case.startswith("installer-") or case == "context":
            windows = [w for w in record["windows"] if not w["hidden"]]
            matches = (
                [w for w in windows if w["type"] == 0 and w["active"]]
                if case.startswith("installer-")
                else [
                    w
                    for w in windows
                    if "plasmashell" in w["resourceClass"] and w["type"] not in (1, 2)
                ]
            )
            require(len(matches) == 1, "Cannot frame " + case)
            g = matches[0]["geometry"]
            margin = 96
            box = (
                max(0, 2 * g["x"] - margin),
                max(0, 2 * g["y"] - margin),
                min(im.width, 2 * (g["x"] + g["width"]) + margin),
                min(im.height, 2 * (g["y"] + g["height"]) + margin),
            )
            im = im.crop(box)
            record = dict(record, crop=box)
        path = output / (name + ".webp")
        im.thumbnail((2048, 1152), Image.Resampling.LANCZOS)
        im.save(path, quality=92, method=4)
        manifest["frames"][name] = dict(
            record,
            case=case,
            mode=mode,
            edition=edition,
            sha256=digest(path),
            capture_tools=manifest["capture_tools"].copy(),
            profile_sha256=manifest.get("profile_sha256"),
        )
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    for mode in ("light", "dark"):
        guest("clock")
        vm.action("mode", mode)
        vm.action("clean-desktop")

        def taken(case, mode=mode):
            record = manifest["frames"].get(f"readme-{edition}-{mode}-{case}")
            return bool(record) and (
                not case.startswith("dock-")
                or (
                    not any(w["type"] == 0 for w in record.get("windows", []))
                    and record.get("macOSDockIcons") is False
                    and record.get("icon_theme", "").startswith(
                        "MacTahoeLiquidKde-Icons-"
                    )
                )
            )

        if materials_only:
            from readme_desktop_scene import photograph_materials

            photograph_materials(vm, edition, mode, guest, snapshot, save, taken)
            continue
        if not taken("menu"):
            guest("editor")
            vm.move(*profile["pointer"])
            time.sleep(1)
            im, record = snapshot()
            top = im.crop((0, 0, 1600, 64))
            gray = top.convert("L")
            labels = words(top)
            if not any(w["text"].strip() == "File" for w in labels):
                for morph in [ImageFilter.MaxFilter(9), ImageFilter.MinFilter(9)]:
                    flat = ImageChops.difference(gray, gray.filter(morph)).point(
                        lambda v: 0 if v > 26 else 255
                    )
                    labels = words(flat)
                    if any(w["text"].strip() == "File" for w in labels):
                        break
            candidates = [w for w in labels if w["text"].strip() == "File"]
            require(
                len(candidates) == 1,
                "Cannot identify File on the active panel: "
                + str([w["text"] for w in labels]),
            )
            item = candidates[0]
            vm.click(
                int(item["left"]) + int(item["width"]) // 2,
                int(item["top"]) + int(item["height"]) // 2,
            )
            time.sleep(0.65)
            im, record = snapshot()
            labels = [w["text"] for w in words(im.crop((0, 0, 1200, 1050)))]
            require(
                "Open" in " ".join(labels)
                and any(
                    w["type"] == 0 and "Field Notes.txt" in w["caption"]
                    for w in record["windows"]
                ),
                "File menu or document missing",
            )
            save(im, record, "menu")
            vm.key("esc")
            vm.action("clean-desktop")
        for accent in ("blue", "red"):
            if taken("finder-" + accent):
                continue
            state = guest("finder", accent, mode)
            require(state["accent"] == accent, "Wrong accent")
            if not taken("finder"):
                im, record = snapshot()
                save(im, record, "finder")
            vm.qmp(
                "send-key",
                {
                    "keys": [
                        {"type": "qcode", "data": "ctrl"},
                        {"type": "qcode", "data": "a"},
                    ]
                },
            )
            vm.move(*profile["pointer"])
            time.sleep(0.6)
            im, record = snapshot()
            require(
                any(
                    w["active"] and "nautilus" in w["resourceClass"].lower()
                    for w in record["windows"]
                ),
                "Files lost focus",
            )
            save(im, dict(record, accent=accent), "finder-" + accent)
        vm.action("clean-desktop")
        from readme_desktop_scene import photograph_desktop

        photograph_desktop(vm, edition, mode, guest, snapshot, save, taken)
