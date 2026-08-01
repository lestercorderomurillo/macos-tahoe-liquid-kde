"""Sound-theme payload and install lifecycle."""

from __future__ import annotations


def test_bundled_sound_theme_is_freedesktop_compatible(offline):
    theme = offline / "sounds/MacTahoeLiquidKde"
    index = (theme / "index.theme").read_text(encoding="utf-8")
    notice = (theme / "NOTICE").read_text(encoding="utf-8")
    stereo = theme / "stereo"

    assert "[Sound Theme]" in index
    assert "Name=MacTahoe Liquid KDE" in index
    assert "Directories=stereo" in index
    assert "Example=theme-demo" in index
    assert "stable macOS Tahoe 26.6" in notice
    assert "25G72" in notice
    assert "122-26025" in notice
    assert (
        "7ff36da0dee7334aa90056e3cd5a3435deb9e5f74e344561618016cd26034d12"
        in notice
    )
    assert "SoundActivateItem resource in 26.6 is replaced" in notice
    assert "No Big Sur sound-theme payload is included" in notice

    sounds = sorted(stereo.glob("*.oga"))
    assert len(sounds) == 44
    assert all(sound.stat().st_size > 1_000 for sound in sounds)

    required = {
        "audio-volume-change.oga",
        "battery-low.oga",
        "bell-window-system.oga",
        "desktop-login.oga",
        "desktop-logout.oga",
        "device-added.oga",
        "device-removed.oga",
        "dialog-error.oga",
        "dialog-information.oga",
        "dialog-warning.oga",
        "message-new-instant.oga",
        "power-plug.oga",
        "power-unplug.oga",
        "theme-demo.oga",
        "trash-empty.oga",
    }
    assert required <= {sound.name for sound in sounds}


def _wire_step(monkeypatch, tmp_path):
    from steps import sounds

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    source = tmp_path / "offline/MacTahoeLiquidKde"
    stereo = source / "stereo"
    stereo.mkdir(parents=True)
    (source / "index.theme").write_text(
        "[Sound Theme]\nName=MacTahoe Liquid KDE\nDirectories=stereo\n"
    )
    (stereo / "bell.oga").write_bytes(b"OggS-test")

    destination = tmp_path / "data/sounds/MacTahoeLiquidKde"
    monkeypatch.setattr(sounds, "OFFLINE_DIR", source)
    monkeypatch.setattr(sounds, "DEST_DIR", destination)
    monkeypatch.setattr(sounds, "ok", lambda _message: None)
    monkeypatch.setattr(sounds, "warn", lambda _message: None)
    monkeypatch.setattr(sounds, "info", lambda _message: None)
    return sounds, destination


def test_install_copies_and_selects_sound_theme(monkeypatch, tmp_path):
    sounds, destination = _wire_step(monkeypatch, tmp_path)
    writes: list[tuple[str, ...]] = []
    monkeypatch.setenv("FEAT_APPLY_THEME", "true")
    monkeypatch.setattr(
        sounds, "kw_write",
        lambda *args: writes.append(args) or True,
    )

    sounds.install()

    assert (destination / "stereo/bell.oga").is_file()
    assert any(args[-2:] == ("Theme", sounds.THEME_ID) for args in writes)
    assert any(args[-2:] == ("Enable", "true") for args in writes)


def test_no_apply_theme_stages_without_selecting(monkeypatch, tmp_path):
    sounds, destination = _wire_step(monkeypatch, tmp_path)
    writes: list[tuple[str, ...]] = []
    monkeypatch.setenv("FEAT_APPLY_THEME", "false")
    monkeypatch.setattr(
        sounds, "kw_write",
        lambda *args: writes.append(args) or True,
    )

    sounds.install()

    assert destination.is_dir()
    assert writes == []


def test_uninstall_restores_ocean_only_when_ours_is_active(
        monkeypatch, tmp_path):
    sounds, destination = _wire_step(monkeypatch, tmp_path)
    destination.mkdir(parents=True)
    writes: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        sounds, "kw_read",
        lambda *_args: sounds.THEME_ID,
    )
    monkeypatch.setattr(
        sounds, "kw_write",
        lambda *args: writes.append(args) or True,
    )

    sounds.uninstall()

    assert not destination.exists()
    assert any(
        args[-2:] == ("Theme", sounds.FALLBACK_THEME_ID)
        for args in writes
    )


def test_uninstall_preserves_a_user_selected_theme(monkeypatch, tmp_path):
    sounds, destination = _wire_step(monkeypatch, tmp_path)
    destination.mkdir(parents=True)
    writes: list[tuple[str, ...]] = []
    monkeypatch.setattr(sounds, "kw_read", lambda *_args: "custom-theme")
    monkeypatch.setattr(
        sounds, "kw_write",
        lambda *args: writes.append(args) or True,
    )

    sounds.uninstall()

    assert not destination.exists()
    assert writes == []
