"""Capture the README Shell and Finder accent scenes in a disposable desktop."""

import json
import subprocess
import tempfile
from pathlib import Path

from release_capture import PROFILE, Guest, capture_lock
from release_screenshots import commit_id, digest, require

PREPARED_NEON = "74004cc15d7180e9b23c93a2c097824853375651b0984f68d9e940c45d461703"


def capture(repo, ref, image, output, editions, packages, *, dock_only=False):
    if not dock_only:
        languages = subprocess.check_output(
            ["tesseract", "--list-langs"], text=True
        ).splitlines()
        require(
            "eng" in languages, "The README capture host needs the English Tesseract model"
        )
    source = commit_id(repo, ref)
    image = image.resolve()
    profile = json.loads(PROFILE.read_text())
    checksum = digest(image)
    require(
        checksum in (PREPARED_NEON, profile["vm_image_sha256"]), "Unexpected capture VM"
    )
    info = json.loads(
        subprocess.check_output(["qemu-img", "info", "--output=json", image])
    )
    require(
        not info.get("backing-filename") and not info.get("dirty-flag"),
        "Expected sealed capture base",
    )
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "source_commit": source,
        "vm_image_sha256": checksum,
        "environment": {},
        "frames": {},
        "profile_sha256": digest(PROFILE),
        "packages": {p.name: digest(p) for p in packages},
    }
    with capture_lock(), tempfile.TemporaryDirectory(dir=output) as scratch:
        archive = Path(scratch) / "source.tar"
        subprocess.run(
            ["git", "-C", repo, "archive", "-o", archive, source], check=True
        )
        for edition in dict.fromkeys(editions):
            with (
                tempfile.TemporaryDirectory(dir=scratch) as work,
                Guest(Path(work), profile, image, archive, edition) as vm,
            ):
                if not dock_only:
                    vm.action("configure-indexer")
                if packages:
                    for package in packages:
                        vm.put(package, "/tmp/" + package.name)
                    vm.remote(
                        "sudo", "dpkg", "-i", *["/tmp/" + p.name for p in packages]
                    )
                manifest["environment"][edition] = vm.action("setup", edition)
                from readme_shell_scene import photograph

                photograph(vm, profile, edition, output, manifest, dock_only=dock_only)
                if dock_only:
                    continue
                from readme_desktop_scene import verify_dock_tints

                for mode in ("light", "dark"):
                    stem = f"readme-{edition}-{mode}-dock-"
                    verify_dock_tints(
                        output / (stem + "red.webp"),
                        output / (stem + "blue.webp"),
                        profile["pins"],
                    )
