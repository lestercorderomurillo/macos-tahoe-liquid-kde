"""Bounded, offline inputs for the icon material builder.

SPDX-License-Identifier: GPL-3.0-or-later
Copyright (C) 2026 Lester Cordero Murillo
"""
from __future__ import annotations

import hashlib
import posixpath
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


MAX_BYTES = 1024 * 1024 * 1024
MAX_MEMBERS = 150_000


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or not path.parts:
        raise ValueError(f"Unsafe archive path: {name}")
    return str(path)


def checked_link(name: str, target: str) -> str:
    if not target or target.startswith("/") or "\\" in target:
        raise ValueError(f"Unsafe link: {name} -> {target}")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    safe_name(resolved)
    return resolved


def unpack(source: Path, destination: Path) -> None:
    """Validate the complete archive before writing; never traverse an archive link."""
    archive = source
    if source.name.endswith(".zst"):
        archive = destination.parent / "source.tar"
        # Stream with a hard byte limit instead of buffering a decompression bomb.
        with archive.open("xb") as output:
            process = subprocess.Popen(["zstd", "-dc", str(source)], stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)
            try:
                total = 0
                while chunk := process.stdout.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError("Decompressed archive exceeds 1 GiB")
                    output.write(chunk)
                if process.wait() != 0:
                    raise ValueError("Cannot decompress the source icon archive")
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
    with tarfile.open(archive) as bundle:
        members = {}
        total = 0
        for member in bundle:
            name = safe_name(member.name)
            if name in members:
                raise ValueError(f"Duplicate archive path: {name}")
            if not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError(f"Unsupported archive member: {name}")
            if member.issym():
                checked_link(name, member.linkname)
            total += member.size
            members[name] = member
            if len(members) > MAX_MEMBERS or total > MAX_BYTES:
                raise ValueError("Source archive exceeds the input limits")
        for name in members:
            for parent in PurePosixPath(name).parents:
                entry = members.get(str(parent))
                if entry is not None and not entry.isdir():
                    raise ValueError(f"Archive path traverses a non-directory: {name}")
        destination.mkdir()
        for name, member in sorted(members.items()):
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                path.mkdir(exist_ok=True)
            elif member.isfile():
                with bundle.extractfile(member) as src, path.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
        for name, member in sorted(members.items()):
            if member.issym():
                (destination / name).symlink_to(member.linkname)
        validate_links(destination)


def validate_links(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            try:
                target = path.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ValueError(f"Broken or cyclic link: {path}") from exc
            if not target.is_relative_to(root.resolve()):
                raise ValueError(f"Link escapes the bundle: {path}")


def inventory(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[name] = {"link": path.readlink().as_posix()}
        elif path.is_file():
            result[name] = {"sha256": digest(path)}
    return result
