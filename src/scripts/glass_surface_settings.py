#!/usr/bin/env python3
"""Apply per-component background transparency to owned installed assets.

No session changes occur on import. SVG edits preserve original geometry,
shadows, masks and borders. Every generation starts from a recorded baseline.
"""
from __future__ import annotations
import argparse
import configparser
import io
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
TILES = ("center", "top", "bottom", "left", "right", "topleft", "topright", "bottomleft", "bottomright")
COMPONENTS = ("general", "finder", "menus", "popups", "apps", "search", "control-center", "about", "dock", "panel")


def validate(materials: dict) -> dict:
    if not isinstance(materials, dict) or set(materials) - set(COMPONENTS):
        raise ValueError("Unknown glass component")
    for component, values in materials.items():
        if not isinstance(values, dict):
            raise ValueError(f"Invalid settings for {component}")
        for key in ("SurfaceTransparencyLight", "SurfaceTransparencyDark"):
            value = values.get(key)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"Invalid {key} for {component}")
    return materials


def _read_svg(data: bytes) -> ET.Element:
    return ET.fromstring(gzip.decompress(data) if data.startswith(b"\x1f\x8b") else data)


def patch_svg(data: bytes, ids: tuple[str, ...], transparency: float) -> bytes:
    """Detach referenced paint nodes so shared border/mask uses stay untouched."""
    root = _read_svg(data)
    indexed = {node.get("id"): node for node in root.iter() if node.get("id")}
    alpha = format(1 - transparency / 100, ".8g")
    visited = set()

    def paint_alpha(node, seen=None):
        seen = set() if seen is None else seen
        if node in seen:
            return None
        seen.add(node)
        style = dict(part.split(":", 1) for part in node.get("style", "").split(";") if ":" in part)
        if style.get("fill", node.get("fill", "")).startswith("#"):
            return float(style.get("opacity", node.get("opacity", "1")))
        href = node.get(f"{{{XLINK}}}href", node.get("href", ""))
        children = list(node)
        if href.startswith("#") and href[1:] in indexed:
            children.insert(0, indexed[href[1:]])
        for child in children:
            value = paint_alpha(child, seen)
            if value is not None:
                return value
        return None

    centre = next((indexed[k] for k in ("center", "window-normal", "menu-normal") if k in ids and k in indexed), None)
    if centre is None:
        raise ValueError("Surface has no recognized centre paint")
    original_alpha = paint_alpha(centre)
    if original_alpha is None:
        raise ValueError("Surface has no recognized background fill")
    if abs(float(alpha) - original_alpha) < 1e-8:
        return data

    def visit(node):
        if node in visited:
            return
        visited.add(node)
        href = node.get(f"{{{XLINK}}}href", node.get("href", ""))
        if href.startswith("#") and href[1:] in indexed:
            # Replace use with a private clone, preserving the instance transform.
            import copy
            clone = copy.deepcopy(indexed[href[1:]])
            for child in clone.iter():
                child.attrib.pop("id", None)
            attrs = {k: v for k, v in node.attrib.items() if k not in (f"{{{XLINK}}}href", "href")}
            node.tag = f"{{{SVG}}}g"
            node.attrib.clear()
            x, y = attrs.pop("x", "0"), attrs.pop("y", "0")
            if x != "0" or y != "0":
                attrs["transform"] = attrs.get("transform", "") + f" translate({x},{y})"
            node.attrib.update(attrs)
            node.append(clone)
        style = dict(part.split(":", 1) for part in node.get("style", "").split(";") if ":" in part)
        fill = style.get("fill", node.get("fill", ""))
        # Surface paint only; referenced gradients are shadows or edge optics.
        node_alpha = float(style.get("opacity", node.get("opacity", "1")))
        if fill.startswith("#") and abs(node_alpha - original_alpha) < 1e-8 and node.tag.rsplit("}", 1)[-1] in ("path", "rect", "polygon"):
            if "opacity" in style:
                style["opacity"] = alpha
            else:
                node.set("opacity", alpha)
            if style:
                node.set("style", ";".join(f"{k}:{v}" for k, v in style.items()))
        for child in list(node):
            visit(child)

    for id_ in ids:
        if id_ in indexed:
            visit(indexed[id_])
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    result = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return gzip.compress(result, mtime=0) if data.startswith(b"\x1f\x8b") else result


def atomic_write(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise ValueError(f"Refusing to replace a symbolic link: {path}")
    if path.exists() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".glass-")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(materials: dict, data_home: Path, config_home: Path, state_home: Path) -> list[Path]:
    materials = validate(materials)
    state = state_home / "mac-tahoe-liquid-kde/glass-surfaces"
    state.mkdir(parents=True, exist_ok=True)
    with (state / "apply.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest_path = state / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        previous_outputs = manifest.get("outputs", {})
        changes: dict[Path, bytes] = {}
        assets = {}

        def baseline(path: Path) -> bytes:
            if path.is_symlink() or not path.resolve().is_relative_to(data_home.resolve()) and not path.resolve().is_relative_to(config_home.resolve()):
                raise ValueError(f"Unowned surface path: {path}")
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            entry = manifest.get(str(path), {})
            # A reinstall or external edit creates a new baseline, never overwrite it with an old backup.
            if entry.get("applied") != digest:
                entry = {"base": digest, "applied": digest}
                atomic_write(state / (digest + ".svg"), data)
                manifest[str(path)] = entry
            return (state / (entry["base"] + ".svg")).read_bytes()

        def patch(path: Path, component: str, light: bool, ids: tuple[str, ...], output: Path | None = None):
            if component not in materials or not path.is_file():
                return
            key = "SurfaceTransparencyLight" if light else "SurfaceTransparencyDark"
            data = patch_svg(baseline(path), ids, materials[component][key])
            target = output or path
            changes[target] = data
            mode = "Light" if light else "Dark"
            relative = path.relative_to(data_home / "plasma/desktoptheme" / ("MacTahoeLiquidKde-" + mode))
            source = relative.with_suffix("").as_posix()
            digest = hashlib.sha256(data).hexdigest()
            generated = data_home / "mac-tahoe-liquid-kde/glass-surfaces" / (digest + ".svgz")
            changes[generated] = data
            assets[mode + "/" + component + "/" + source] = str(generated)

        for suffix in ("Light", "Dark"):
            light = suffix == "Light"
            theme = data_home / "plasma/desktoptheme" / ("MacTahoeLiquidKde-" + suffix)
            background = theme / "dialogs/background.svgz"
            for component, source in (("apps", background), ("search", theme / "dialogs/launcher-search.svgz")):
                patch(source, component, light, TILES, theme / "dialogs" / ("glass-" + component + ".svgz"))
            for name in ("dialogs/background.svgz", "widgets/background.svgz", "widgets/translucentbackground.svgz", "widgets/tooltip.svgz"):
                patch(theme / name, "popups", light, TILES)
            patch(theme / "widgets/panel-background.svgz", "dock", light, TILES,
                  theme / "widgets/glass-dock.svgz")
            patch(theme / "widgets/panel-background.svgz", "panel", light, TILES)

        for name in ("mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark"):
            light = not name.endswith("Dark")
            path = config_home / "Kvantum" / name / (name + ".svg")
            if not path.is_file():
                continue
            source = baseline(path)
            root = _read_svg(source)
            menu_ids = tuple(n.get("id") for n in root.iter() if n.get("id", "").startswith("menu-normal"))
            window_ids = tuple(n.get("id") for n in root.iter() if n.get("id", "").startswith("window-normal"))
            key = "SurfaceTransparencyLight" if light else "SurfaceTransparencyDark"
            data = source
            if "menus" in materials:
                data = patch_svg(data, menu_ids, materials["menus"][key])
            if "general" in materials:
                data = patch_svg(data, window_ids, materials["general"][key])
            changes[path] = data
            # Kvantum selects application-specific themes through its Applications map.
            if "finder" in materials:
                finder_name = "mac-tahoe-liquid-kdeFinder" + ("" if light else "Dark")
                finder = config_home / "Kvantum" / finder_name
                changes[finder / (finder_name + ".svg")] = patch_svg(data, window_ids, materials["finder"][key])
                settings = path.with_suffix(".kvconfig")
                if settings.is_file():
                    changes[finder / (finder_name + ".kvconfig")] = settings.read_bytes()

        chooser = config_home / "Kvantum/kvantum.kvconfig"
        if "finder" in materials and chooser.is_file():
            config = configparser.ConfigParser(interpolation=None, strict=False)
            config.optionxform = str
            config.read(chooser)
            theme = config.get("General", "theme", fallback="")
            if theme in ("mac-tahoe-liquid-kde", "mac-tahoe-liquid-kdeDark"):
                if not config.has_section("Applications"):
                    config.add_section("Applications")
                # Preserve unrelated application mappings, including a user's explicit Dolphin theme.
                owned = ("mac-tahoe-liquid-kdeFinder", "mac-tahoe-liquid-kdeFinderDark")
                other = any("dolphin" in [a.strip() for a in apps.split(",")] for key, apps in config.items("Applications") if key not in owned)
                if not other:
                    for key in owned:
                        config.remove_option("Applications", key)
                    config.set("Applications", owned[theme.endswith("Dark")], "dolphin")
                    out = io.StringIO()
                    config.write(out, space_around_delimiters=False)
                    changes[chooser] = out.getvalue().encode()

        changes[data_home / "mac-tahoe-liquid-kde/glass-surfaces/assets.json"] = (json.dumps(assets, sort_keys=True) + "\n").encode()
        # Validate all assets before committing anything. Retain originals for rollback.
        for path, data in changes.items():
            if path.is_symlink() or not (path.resolve().is_relative_to(data_home.resolve()) or path.resolve().is_relative_to(config_home.resolve())):
                raise ValueError(f"Unowned output path: {path}")
            if path.suffix in (".svg", ".svgz"):
                _read_svg(data)
        originals = {path: path.read_bytes() if path.exists() else None for path in changes}
        committed = []
        try:
            for path, data in changes.items():
                if path.suffix in (".svg", ".svgz"):
                    _read_svg(data)
                if originals[path] != data:
                    atomic_write(path, data)
                    committed.append(path)
                if str(path) in manifest:
                    manifest[str(path)]["applied"] = hashlib.sha256(data).hexdigest()
            manifest["outputs"] = {str(path): hashlib.sha256(data).hexdigest() for path, data in changes.items() if str(path) not in manifest}
            atomic_write(manifest_path, (json.dumps(manifest, indent=2) + "\n").encode())
        except Exception:
            for path in reversed(committed):
                if originals[path] is None:
                    path.unlink()
                else:
                    atomic_write(path, originals[path])
            raise
        # Bound the content-addressed live cache to the current generation.
        # Do not remove a file edited externally or any user theme asset.
        generated = data_home / "mac-tahoe-liquid-kde/glass-surfaces"
        for filename, digest in previous_outputs.items():
            path = Path(filename)
            if (path not in changes and path.parent == generated and path.suffix == ".svgz"
                    and not path.is_symlink() and path.is_file()
                    and hashlib.sha256(path.read_bytes()).hexdigest() == digest):
                try:
                    path.unlink()
                except OSError:
                    pass  # Cache cleanup is optional; the applied generation remains valid.
        return committed


def restore(data_home: Path, config_home: Path, state_home: Path) -> None:
    """Restore only bytes still owned by this helper, preserving outside edits."""
    state = state_home / "mac-tahoe-liquid-kde/glass-surfaces"
    manifest_path = state / "manifest.json"
    if not manifest_path.is_file():
        return
    with (state / "apply.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = json.loads(manifest_path.read_text())
        for filename, entry in manifest.items():
            if filename == "outputs":
                continue
            path = Path(filename)
            if path.is_symlink() or not (path.resolve().is_relative_to(data_home.resolve()) or path.resolve().is_relative_to(config_home.resolve())):
                continue
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == entry["applied"]:
                atomic_write(path, (state / (entry["base"] + ".svg")).read_bytes())
        # The asset map is the live bridge's override registry. Clear it even
        # if another process is retaining older rendered textures.
        mapping = data_home / "mac-tahoe-liquid-kde/glass-surfaces/assets.json"
        if mapping.is_file() and not mapping.is_symlink():
            atomic_write(mapping, b"{}\n")
        chooser = config_home / "Kvantum/kvantum.kvconfig"
        if chooser.is_file() and not chooser.is_symlink():
            config = configparser.ConfigParser(interpolation=None, strict=False)
            config.optionxform = str
            config.read(chooser)
            if config.has_section("Applications"):
                for key in ("mac-tahoe-liquid-kdeFinder", "mac-tahoe-liquid-kdeFinderDark"):
                    if config.get("Applications", key, fallback="") == "dolphin":
                        config.remove_option("Applications", key)
                out = io.StringIO()
                config.write(out, space_around_delimiters=False)
                atomic_write(chooser, out.getvalue().encode())
        for filename, digest in manifest.get("outputs", {}).items():
            path = Path(filename)
            if path == mapping or path == chooser or path.is_symlink():
                continue
            if not (path.resolve().is_relative_to(data_home.resolve()) or path.resolve().is_relative_to(config_home.resolve())):
                continue
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                path.unlink()
        manifest_path.unlink()


def reload_qt_surfaces(switcher: Path) -> bool:
    """Reuse the installed switcher's live style cycle, including older installs.

    Read the style under its existing transition lock so an overlapping mode
    selection cannot be overwritten by a stale style restoration.
    """
    import runpy
    if not switcher.is_file():
        return False
    runtime = runpy.run_path(str(switcher))
    with runtime["_theme_transition_lock"]():
        style = runtime["_kread"]("kdeglobals", "KDE", "widgetStyle")
        if style.lower() != "mactahoe" and not style.lower().startswith("kvantum"):
            return True
        return runtime["cycle_widget_style_live"](style)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--apply", action="store_true")
    action.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    home = Path.home()
    try:
        if args.reload:
            # Nix packages the Python modules together behind shell wrappers;
            # the ordinary installer supplies a standalone Python executable.
            switcher = Path(__file__).resolve().with_name("theme_switch.py")
            if not switcher.is_file():
                switcher = home / ".local/bin/mac-tahoe-theme-switch"
            return 0 if reload_qt_surfaces(switcher) else 1
        materials = json.load(sys.stdin)
        changed = apply(materials, Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")),
                        Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")),
                        Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")))
        print(json.dumps({"changed": [str(path) for path in changed]}))
    except (OSError, ValueError, ET.ParseError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
