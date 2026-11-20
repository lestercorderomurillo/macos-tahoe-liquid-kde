"""Verify and replace existing README capture slots across an edition's translations."""

import hashlib
import json
import re
from pathlib import Path

from release_screenshots import digest, require

PREFIX = "src/screenshots/previews/"


def inventory(repo):
    gallery = repo / PREFIX
    primary = gallery.parent / "readme-capture.json"
    data = json.loads(primary.read_text())
    edition = data["edition"]
    (separate,) = gallery.glob(f"readme-{edition}-notifications-provenance-*.json")
    manifests = {primary: data, separate: json.loads(separate.read_text())}
    documents = {p: p.read_text() for p in sorted(repo.glob("README*.md"))}
    slots = {}
    for doc in [repo / "README.md", *[p for p in documents if p.name != "README.md"]]:
        sources = re.findall(
            r'<img\b[^>]*\bsrc="(' + PREFIX + r'[^"]+)"', documents[doc]
        )
        require(
            sources and len(set(sources)) == len(sources),
            f"Missing or duplicate captures in {doc}",
        )
        if slots:
            require(
                set(sources) == {PREFIX + row[0] for row in slots.values()},
                f"Capture mismatch in {doc}",
            )
            continue
        for src in sources:
            filename = Path(src).name
            match = re.fullmatch(
                r"(readme-"
                + edition
                + r"-(light|dark)-[a-z0-9-]+)-([a-f0-9]{12})\.webp",
                filename,
            )
            require(
                match and src == PREFIX + filename, f"Unexpected capture path: {src}"
            )
            name, mode, suffix = match.groups()
            owner, key = (
                (separate, filename)
                if filename in manifests[separate]["images"]
                else (primary, "previews/" + filename)
            )
            record = manifests[owner]["images"][key]
            checksum = digest(gallery / filename)
            require(
                name not in slots
                and checksum == record["sha256"]
                and checksum.startswith(suffix),
                f"Invalid slot or checksum: {src}",
            )
            slots[name] = (filename, mode, owner, key)
    recorded = {
        Path(key).name
        for data in manifests.values()
        for key in data["images"]
        if re.match("readme-" + edition + r"-(light|dark)-", Path(key).name)
    }
    require(
        recorded == {row[0] for row in slots.values()},
        "README omits recorded photography",
    )
    return edition, documents, manifests, slots


def stage(repo, edition, bundle, names=None):
    actual, documents, manifests, slots = inventory(repo)
    require(actual == edition, "Destination edition differs from requested edition")
    batch = json.loads((bundle / "manifest.json").read_text())
    if names is None:
        names = [
            name
            for name in batch["frames"]
            if name.startswith("readme-" + edition + "-")
        ]
    require(bool(names), "No capture slots selected")
    require(
        re.fullmatch("[0-9a-f]{40}", batch["source_commit"])
        and re.fullmatch("[0-9a-f]{64}", batch["vm_image_sha256"])
        and batch["environment"],
        "Missing capture source or environment",
    )
    gallery = repo / PREFIX
    pending = []
    touched = set()
    for name in sorted(set(names)):
        require(name in slots, f"Unknown README slot: {name}")
        previous, mode, owner, key = slots[name]
        record = batch["frames"][name]
        photo = (bundle / (name + ".webp")).read_bytes()
        sha = hashlib.sha256(photo).hexdigest()
        require(
            record["sha256"] == sha
            and record["mode"] == mode
            and record["edition"] == edition,
            f"Capture evidence mismatch: {name}",
        )
        require(
            photo[:4] == b"RIFF" and photo[8:12] == b"WEBP", f"Invalid WebP: {name}"
        )
        current = f"{name}-{sha[:12]}.webp"
        if previous == current:
            require(digest(gallery / previous) == sha, "Hash prefix collision")
            continue
        images = manifests[owner]["images"]
        del images[key]
        images[key.replace(previous, current)] = dict(
            record,
            replaces=PREFIX + previous,
            source_commit=batch["source_commit"],
            vm_image_sha256=batch["vm_image_sha256"],
            capture_environment=batch["environment"],
        )
        for doc, text in documents.items():
            documents[doc] = text.replace(PREFIX + previous, PREFIX + current)
        pending.append((previous, current, photo))
        touched.add(owner)
    for previous, current, photo in pending:
        (gallery / current).write_bytes(photo)
    for owner in sorted(touched):
        data = manifests[owner]
        if owner.parent == gallery:
            # Partial refreshes carry source/environment per frame.
            for row in data["images"].values():
                for field in (
                    "source_commit",
                    "vm_image_sha256",
                    "capture_environment",
                ):
                    if field in data:
                        row.setdefault(field, data[field])
            for field in ("source_commit", "vm_image_sha256", "capture_environment"):
                data.pop(field, None)
        payload = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()
        target = owner
        if owner.parent == gallery:
            target = owner.with_name(
                re.sub(
                    r"-[a-f0-9]{12}\.json$",
                    "-" + hashlib.sha256(payload).hexdigest()[:12] + ".json",
                    owner.name,
                )
            )
        target.write_bytes(payload)
        if target != owner:
            owner.unlink()
    if pending:
        for doc, text in documents.items():
            doc.write_text(text)
        for previous, _, _ in pending:
            (gallery / previous).unlink()
    return len(pending)
