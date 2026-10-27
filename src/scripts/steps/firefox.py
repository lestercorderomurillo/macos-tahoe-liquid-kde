"""Install the bundled MacTahoe Firefox CSS without touching profile data.

The visual assets are a maintained, data-only fork of the Firefox CSS/SVG in
vinceliuice's MacTahoe-gtk-theme. Its shell installer is deliberately not
included or executed: this step owns profile discovery, backups, managed CSS
imports, and reversible preference changes.
"""

from __future__ import annotations

from localization import tr

import configparser
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from steps._helpers import HOME, info, offline, ok, warn


THEME_DIRNAME = "MacTahoeLiquidKde"
THEME_SOURCE_NAME = "firefox"
OWNERSHIP_MARKER = ".mttkde-firefox-theme.json"
STATE_VERSION = 1

CHROME_START = "/* >>> MacTahoe Liquid KDE Firefox theme >>> */"
CHROME_END = "/* <<< MacTahoe Liquid KDE Firefox theme <<< */"
USER_START = "// >>> MacTahoe Liquid KDE Firefox theme >>>"
USER_END = "// <<< MacTahoe Liquid KDE Firefox theme <<<"

CHROME_BLOCKS = {
    "userChrome.css": (
        f'{CHROME_START}\n@import url("{THEME_DIRNAME}/userChrome.css");\n'
        f"{CHROME_END}\n"
    ),
    "userContent.css": (
        f'{CHROME_START}\n@import url("{THEME_DIRNAME}/userContent.css");\n'
        f"{CHROME_END}\n"
    ),
}
USER_BLOCK = (
    f"{USER_START}\n"
    'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);\n'
    f"{USER_END}\n"
)
LEGACY_PREF_LINES = (
    'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);',
    'user_pref("browser.tabs.drawInTitlebar", true);',
    'user_pref("browser.uidensity", 0);',
    'user_pref("layers.acceleration.force-enabled", true);',
    'user_pref("mozilla.widget.use-argb-visuals", true);',
    'user_pref("widget.gtk.rounded-bottom-corners.enabled", true);',
    'user_pref("svg.context-properties.content.enabled", true);',
)


def _state_root() -> Path:
    return HOME / ".local/state/mac-tahoe-liquid-kde/firefox"


def _manifest_path() -> Path:
    return _state_root() / "manifest.json"


def _theme_source() -> Path:
    return offline(THEME_SOURCE_NAME, THEME_DIRNAME)


def _xdg_config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured).expanduser() if configured else HOME / ".config"


def _profile_id(profile: Path) -> str:
    digest = hashlib.sha256(os.fsencode(str(profile))).hexdigest()[:16]
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", profile.name).strip("-")
    return f"{safe_name or 'profile'}-{digest}"


def _load_manifest() -> dict[str, object]:
    path = _manifest_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": STATE_VERSION, "profiles": {}}
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        return {"version": STATE_VERSION, "profiles": {}}
    return data


def _atomic_write(path: Path, text: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode if mode is not None else 0o600)
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _save_manifest(manifest: dict[str, object]) -> None:
    root = _state_root()
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    _atomic_write(
        _manifest_path(),
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        0o600,
    )


def _candidate_roots() -> list[Path]:
    """Only Firefox owns these roots; Gecko compatibility is not UI compatibility."""
    return [
        _xdg_config_home() / "mozilla/firefox",
        HOME / ".mozilla/firefox",
        HOME / ".var/app/org.mozilla.firefox/.mozilla/firefox",
        HOME / ".var/app/org.mozilla.firefox/config/mozilla/firefox",
        HOME / "snap/firefox/common/.mozilla/firefox",
    ]


def _retired_roots() -> list[Path]:
    """Old broad discovery is retained solely for exclusion and owned cleanup.

    In particular, Zen's UI must never receive Firefox CSS (issue #104).
    Keep lexical roots distinct here: a Firefox symlink into a fork's root
    must still be recognized as belonging to that fork.
    """
    roots = [
        HOME / ".librewolf",
        HOME / ".floorp",
        HOME / ".waterfox",
        HOME / ".zen",
        _xdg_config_home() / "zen",
    ]
    flatpak = HOME / ".var/app"
    if flatpak.is_dir():
        for app in flatpak.iterdir():
            roots.extend((
                app / ".mozilla/firefox",
                app / ".librewolf",
                app / ".floorp",
                app / ".waterfox",
                app / ".zen",
                app / "config/zen",
            ))
    snap = HOME / "snap"
    if snap.is_dir():
        for app in snap.iterdir():
            roots.extend((
                app / "common/.mozilla/firefox",
                app / "common/.librewolf",
                app / "common/.floorp",
            ))
    supported = set(_candidate_roots())
    return list(dict.fromkeys(root for root in roots if root not in supported))


def _profiles_from_ini(root: Path) -> list[Path]:
    ini = root / "profiles.ini"
    if not ini.is_file():
        return []
    parser = configparser.RawConfigParser(interpolation=None)
    try:
        parser.read(ini, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeError):
        warn(tr('Firefox: could not parse {ini}', ini=ini))
        return []
    profiles: list[Path] = []
    for section in parser.sections():
        if not section.lower().startswith("profile"):
            continue
        raw = parser.get(section, "Path", fallback="").strip()
        if not raw or "\x00" in raw:
            continue
        candidate = Path(raw).expanduser()
        if parser.getboolean(section, "IsRelative", fallback=True):
            candidate = root / candidate
        profiles.append(candidate)
    return profiles


def _discover_profiles(roots: list[Path]) -> list[Path]:
    """Find initialized registered and orphaned profiles within specific roots."""
    found: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        candidates = _profiles_from_ini(root)
        try:
            candidates.extend(
                child for child in root.iterdir()
                if child.is_dir() and (child / "prefs.js").is_file()
            )
        except OSError:
            continue
        for profile in candidates:
            try:
                resolved = profile.resolve(strict=True)
            except OSError:
                continue
            if resolved.is_dir() and (resolved / "prefs.js").is_file():
                found.setdefault(str(resolved), resolved)
    return sorted(found.values(), key=str)


def discover_profiles() -> list[Path]:
    """Find Firefox profiles, excluding profiles also registered by a fork."""
    retired = set(_discover_profiles(_retired_roots()))
    return [
        profile for profile in _discover_profiles(_candidate_roots())
        if profile not in retired
    ]


def _copy_entry(source: Path, destination: Path) -> None:
    """Copy one UI configuration entry without dereferencing child links."""
    if source.is_symlink():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _snapshot_profile(profile: Path, root: Path | None) -> Path | None:
    """Back up all files this feature may affect, plus profile metadata.

    A failed backup is a hard boundary for this profile: the caller must not
    modify it.  Browser databases (bookmarks, logins, cookies, history) are
    never touched, so copying them would add huge cost without improving the
    rollback of this CSS-only feature.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = _state_root() / "snapshots" / stamp / _profile_id(profile)
    try:
        _state_root().mkdir(parents=True, exist_ok=True)
        _state_root().chmod(0o700)
        destination.mkdir(parents=True, mode=0o700)
        for name in ("prefs.js", "user.js", "chrome"):
            source = profile / name
            if source.is_symlink() and name == "chrome":
                (destination / "chrome.symlink").write_text(
                    os.readlink(source), encoding="utf-8"
                )
                resolved = source.resolve(strict=True)
                _copy_entry(resolved, destination / "chrome")
            elif source.exists() or source.is_symlink():
                _copy_entry(source, destination / name)
        if root is not None and (root / "profiles.ini").is_file():
            shutil.copy2(root / "profiles.ini", destination / "profiles.ini")
        (destination / "PROFILE_PATH.txt").write_text(
            str(profile) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        warn(tr('Firefox: backup failed for {profile} ({exc}); profile skipped', profile=profile, exc=exc))
        return None
    return destination


def _root_for_profile(profile: Path) -> Path | None:
    for root in _candidate_roots():
        try:
            profile.relative_to(root.resolve(strict=False))
        except (OSError, ValueError):
            continue
        return root
    return None


def _is_legacy_theme_symlink(chrome: Path) -> bool:
    """Recognize the destructive vinceliuice installer layout precisely."""
    if not chrome.is_symlink():
        return False
    try:
        entrypoint = _read_text(chrome / "userChrome.css")
    except OSError:
        return False
    return (
        '@import "MacTahoe/theme.css"' in entrypoint
        or '@import "WhiteSur/theme.css"' in entrypoint
    )


def _original_record(profile: Path, snapshot: Path) -> dict[str, object]:
    chrome = profile / "chrome"
    legacy = _is_legacy_theme_symlink(chrome)
    user_chrome = chrome / "userChrome.css"
    user_content = chrome / "userContent.css"
    user_js = profile / "user.js"

    def existed_before_ours(path: Path, start: str, end: str) -> bool:
        if not path.exists():
            return False
        try:
            text = _read_text(path)
        except OSError:
            return True
        if start not in text:
            return True
        clean, valid = _without_block(text, start, end)
        return not valid or bool(clean.strip())

    return {
        "path": str(profile),
        "backup": str(snapshot),
        "chrome_kind": (
            "legacy-theme-symlink" if legacy
            else "symlink" if chrome.is_symlink()
            else "directory" if chrome.is_dir()
            else "missing"
        ),
        # A recognized upstream installer symlink is retained in backups but
        # deliberately not restored live: uninstall must return normal Firefox.
        "user_chrome_existed": not legacy and existed_before_ours(
            user_chrome, CHROME_START, CHROME_END
        ),
        "user_content_existed": not legacy and existed_before_ours(
            user_content, CHROME_START, CHROME_END
        ),
        "user_js_existed": existed_before_ours(user_js, USER_START, USER_END),
        "theme_existed": (
            not legacy
            and (chrome / THEME_DIRNAME).exists()
            and not (chrome / THEME_DIRNAME / OWNERSHIP_MARKER).is_file()
        ),
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="surrogateescape")


def _without_block(text: str, start: str, end: str) -> tuple[str, bool]:
    if start not in text:
        return text, True
    start_at = text.find(start)
    end_at = text.find(end, start_at + len(start))
    if end_at < 0:
        return text, False
    end_at += len(end)
    if end_at < len(text) and text[end_at] == "\n":
        end_at += 1
    return text[:start_at] + text[end_at:], True


def _prepend_css_block(path: Path, block: str) -> None:
    old = _read_text(path) if path.exists() else ""
    clean, valid = _without_block(old, CHROME_START, CHROME_END)
    if not valid:
        raise ValueError(tr('managed marker is incomplete in {path}', path=path))
    # CSS requires @charset to be the first statement.  Preserve it there and
    # place our @import immediately afterward; all imports then precede rules.
    match = re.match(r"^(\ufeff?@charset\s+[^;]+;[ \t]*\r?\n)", clean, re.I)
    if match:
        new = match.group(1) + block + clean[match.end():]
    else:
        new = block + clean
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    _atomic_write(path, new, mode)


def _append_user_block(path: Path) -> None:
    old = _read_text(path) if path.exists() else ""
    clean, valid = _without_block(old, USER_START, USER_END)
    if not valid:
        raise ValueError(tr('managed marker is incomplete in {path}', path=path))
    separator = "" if not clean or clean.endswith("\n") else "\n"
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    _atomic_write(path, clean + separator + USER_BLOCK, mode)


def _prepare_chrome_dir(profile: Path, migrate_legacy: bool = False) -> Path:
    chrome = profile / "chrome"
    if chrome.is_symlink():
        # Upstream commonly replaces chrome/ with a shared symlink.  Convert it
        # to an independent directory so profiles can never affect each other.
        resolved = chrome.resolve(strict=True)
        if not resolved.is_dir():
            raise OSError(tr('chrome symlink target is not a directory: {resolved}', resolved=resolved))
        staged = profile / ".chrome.mttkde-stage"
        if staged.is_symlink():
            staged.unlink()
        elif staged.exists():
            shutil.rmtree(staged)
        if migrate_legacy:
            staged.mkdir()
        else:
            shutil.copytree(resolved, staged, symlinks=True)
        previous = profile / ".chrome.mttkde-previous"
        if previous.exists() or previous.is_symlink():
            raise OSError(tr('stale recovery path exists: {previous}', previous=previous))
        os.replace(chrome, previous)
        try:
            os.replace(staged, chrome)
        except OSError:
            os.replace(previous, chrome)
            raise
        previous.unlink()  # the previous entry is the symlink, never its target
    elif chrome.exists() and not chrome.is_dir():
        raise OSError(tr('chrome exists but is not a directory'))
    else:
        chrome.mkdir(parents=True, exist_ok=True)
    return chrome


def _remove_legacy_user_prefs(path: Path) -> None:
    """Remove only the exact preference lines appended by upstream's script."""
    if not path.is_file():
        return
    old = _read_text(path)
    lines = old.splitlines(keepends=True)
    clean = "".join(
        line for line in lines if line.strip() not in LEGACY_PREF_LINES
    )
    if clean != old:
        _atomic_write(path, clean, path.stat().st_mode & 0o777)


def _install_payload(chrome: Path) -> None:
    source = _theme_source()
    marker = source / OWNERSHIP_MARKER
    if not source.is_dir() or not marker.is_file():
        raise OSError(tr('bundled Firefox theme is incomplete: {source}', source=source))
    destination = chrome / THEME_DIRNAME
    staged = chrome / f".{THEME_DIRNAME}.mttkde-stage"
    if staged.exists() and not staged.is_symlink():
        shutil.rmtree(staged)
    elif staged.is_symlink():
        staged.unlink()
    shutil.copytree(source, staged, symlinks=True)
    previous = chrome / f".{THEME_DIRNAME}.mttkde-previous"
    if previous.exists() or previous.is_symlink():
        if staged.is_dir():
            shutil.rmtree(staged)
        raise OSError(tr('stale recovery path exists: {previous}', previous=previous))
    had_destination = destination.exists() or destination.is_symlink()
    if had_destination:
        os.replace(destination, previous)
    try:
        os.replace(staged, destination)
    except OSError:
        if had_destination:
            os.replace(previous, destination)
        raise
    if had_destination:
        if previous.is_symlink():
            previous.unlink()
        else:
            shutil.rmtree(previous)


def _markers_are_valid(profile: Path) -> bool:
    checks = (
        (profile / "chrome/userChrome.css", CHROME_START, CHROME_END),
        (profile / "chrome/userContent.css", CHROME_START, CHROME_END),
        (profile / "user.js", USER_START, USER_END),
    )
    for path, start, end in checks:
        if not path.is_file():
            continue
        try:
            _, valid = _without_block(_read_text(path), start, end)
        except OSError:
            return False
        if not valid:
            warn(tr('Firefox: incomplete managed marker in {path}; profile skipped', path=path))
            return False
    return True


def _install_profile(profile: Path, manifest: dict[str, object]) -> bool:
    profiles = manifest.setdefault("profiles", {})
    assert isinstance(profiles, dict)
    key = str(profile)
    if not _markers_are_valid(profile):
        return False
    snapshot = _snapshot_profile(profile, _root_for_profile(profile))
    if snapshot is None:
        return False
    if key not in profiles:
        profiles[key] = _original_record(profile, snapshot)
        _save_manifest(manifest)  # durable recovery state before any write
    try:
        record = profiles[key]
        assert isinstance(record, dict)
        migrate_legacy = record.get("chrome_kind") == "legacy-theme-symlink"
        chrome = _prepare_chrome_dir(profile, migrate_legacy=migrate_legacy)
        _install_payload(chrome)
        for name, block in CHROME_BLOCKS.items():
            _prepend_css_block(chrome / name, block)
        if migrate_legacy:
            _remove_legacy_user_prefs(profile / "user.js")
        _append_user_block(profile / "user.js")
    except (OSError, ValueError) as exc:
        warn(tr('Firefox: {value1} was not themed ({exc})', value1=profile.name, exc=exc))
        return False
    ok(tr('Firefox profile themed: {value1}', value1=profile.name))
    return True


def _clean_file(path: Path, start: str, end: str, remove_if_empty: bool) -> bool:
    if not path.is_file():
        return True
    old = _read_text(path)
    clean, valid = _without_block(old, start, end)
    if not valid:
        warn(tr('Firefox: incomplete managed marker in {path}; left untouched', path=path))
        return False
    if clean == old:
        return True
    if remove_if_empty and not clean.strip():
        path.unlink()
    else:
        _atomic_write(path, clean, path.stat().st_mode & 0o777)
    return True


def _restore_colliding_theme(chrome: Path, record: dict[str, object]) -> None:
    if not record.get("theme_existed"):
        return
    backup = Path(str(record.get("backup", ""))) / "chrome" / THEME_DIRNAME
    destination = chrome / THEME_DIRNAME
    if not backup.exists() or destination.exists():
        return
    _copy_entry(backup, destination)


def _uninstall_profile(profile: Path, record: dict[str, object] | None) -> bool:
    chrome = profile / "chrome"
    success = True
    if chrome.is_dir():
        success &= _clean_file(
            chrome / "userChrome.css", CHROME_START, CHROME_END,
            remove_if_empty=not bool(record and record.get("user_chrome_existed")),
        )
        success &= _clean_file(
            chrome / "userContent.css", CHROME_START, CHROME_END,
            remove_if_empty=not bool(record and record.get("user_content_existed")),
        )
        theme = chrome / THEME_DIRNAME
        if (theme / OWNERSHIP_MARKER).is_file():
            if theme.is_symlink():
                theme.unlink()
            else:
                shutil.rmtree(theme)
        if record:
            _restore_colliding_theme(chrome, record)
        if record and record.get("chrome_kind") in (
            "missing", "legacy-theme-symlink",
        ):
            try:
                chrome.rmdir()  # only succeeds when truly empty
            except OSError:
                pass
    success &= _clean_file(
        profile / "user.js", USER_START, USER_END,
        remove_if_empty=(
            not bool(record and record.get("user_js_existed"))
            or bool(record and record.get("chrome_kind") == "legacy-theme-symlink")
        ),
    )
    if success:
        ok(tr('Firefox profile restored: {value1}', value1=profile.name))
    return success


def install() -> None:
    profiles = discover_profiles()
    manifest = _load_manifest()
    _retire_profiles(manifest, set(profiles))
    if not profiles:
        warn(tr('No initialized Firefox profiles found — run Firefox once, then reinstall'))
        info(tr('Firefox theme: 0 profiles changed'))
        return
    changed = sum(_install_profile(profile, manifest) for profile in profiles)
    _save_manifest(manifest)
    info(tr('Firefox theme: {changed}/{value2} profiles installed; restart browsers to apply', changed=changed, value2=len(profiles)))


def _has_managed_theme(profile: Path) -> bool:
    if (profile / "chrome" / THEME_DIRNAME / OWNERSHIP_MARKER).is_file():
        return True
    for relative, marker in (
        ("chrome/userChrome.css", CHROME_START),
        ("chrome/userContent.css", CHROME_START),
        ("user.js", USER_START),
    ):
        path = profile / relative
        try:
            if path.is_file() and marker in _read_text(path):
                return True
        except OSError:
            continue
    return False


def _retire_profiles(manifest: dict[str, object], supported: set[Path]) -> None:
    """Undo earlier Firefox CSS in forks, even on a Zen-only installation."""
    saved = manifest["profiles"]
    assert isinstance(saved, dict)
    targets = {
        Path(key) for key, record in saved.items()
        if isinstance(key, str) and isinstance(record, dict)
    }
    targets.update(
        profile for profile in _discover_profiles(_retired_roots())
        if _has_managed_theme(profile)
    )
    for profile in sorted(targets - supported, key=str):
        if not profile.is_dir() or not _markers_are_valid(profile):
            continue
        snapshot = _snapshot_profile(profile, None)
        if snapshot is None:
            continue
        key = str(profile)
        record = saved.get(key)
        if not isinstance(record, dict):
            record = _original_record(profile, snapshot)
            saved[key] = record
            _save_manifest(manifest)
        try:
            # Detach shared chrome before removing imports from it.
            if (profile / "chrome").is_symlink():
                _prepare_chrome_dir(profile)
            if _uninstall_profile(profile, record):
                del saved[key]
                _save_manifest(manifest)
        except (OSError, ValueError) as exc:
            warn(tr('Firefox: could not restore {profile} ({exc}); recovery state retained', profile=profile, exc=exc))


def uninstall() -> None:
    manifest = _load_manifest()
    profiles = discover_profiles()
    _retire_profiles(manifest, set(profiles))
    saved = manifest.get("profiles", {})
    saved = saved if isinstance(saved, dict) else {}
    targets: dict[str, tuple[Path, dict[str, object] | None]] = {}
    for key, value in saved.items():
        if isinstance(key, str) and isinstance(value, dict) and Path(key) in profiles:
            targets[key] = (Path(key), value)
    for profile in profiles:
        targets.setdefault(str(profile), (profile, None))
    restored = 0
    for profile, record in targets.values():
        if profile.is_dir() and _uninstall_profile(profile, record):
            restored += 1
            saved.pop(str(profile), None)
    if saved:
        _save_manifest(manifest)
    elif restored == len(targets):
        try:
            _manifest_path().unlink()
        except FileNotFoundError:
            pass
    info(tr('Firefox theme: {restored}/{value2} profiles restored; backups retained', restored=restored, value2=len(targets)))
