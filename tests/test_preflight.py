"""Preflight invariants — the four checks that gate every install run.

Each check is exercised against the real repo state (no mocks for the
plasmoid tree or the Qt6 path discovery), so a refactor that drifts
the layout JS, the metadata IDs, or the install destinations gets
caught here before it ships."""

import json
from pathlib import Path

import pytest

import preflight
from paths import OFFLINE_DIR


# ── 1. destination-path regex ────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/etc/sddm.conf.d/mac-tahoe.conf",
    "/usr/share/sounds/MacTahoe",
    "/usr/share/wallpapers/MacTahoe",
])
def test_validate_path_accepts_allowed_roots(path):
    assert preflight._validate_path(path) is None


def test_validate_path_accepts_qmake6_reported_qt6_roots():
    """Qt6 plugin / QML roots come from distro.qt6_*_dir() at validate
    time, so the allowed-roots list adapts to whatever libdir
    convention this distro uses. On Arch that's /usr/lib/qt6, on
    Fedora /usr/lib64/qt6, on Debian /usr/lib/x86_64-linux-gnu/qt6 —
    all should validate cleanly."""
    from distro import qt6_plugins_dir, qt6_qml_dir, Qt6PathsMissing
    try:
        plugins = str(qt6_plugins_dir())
        qml = str(qt6_qml_dir())
    except Qt6PathsMissing:
        pytest.skip("qmake6 not on PATH in this test environment")
    for path in (
        f"{plugins}/plasma/applets/foo.so",
        f"{qml}/plasma/applet/org/kde/foo",
    ):
        assert preflight._validate_path(path) is None, path


@pytest.mark.parametrize("path,reason", [
    ("/tmp/payload", "tmp path used as install dest"),
    ("/usr/lib//qt6/plugins/foo", "double slash"),
    ("/usr/lib/qt6/plugins/../etc/passwd", "parent traversal"),
    ("/etc/passwd", "outside allowed roots"),
    ("/var/log/anything", "outside allowed roots"),
])
def test_validate_path_rejects_dangerous_paths(path, reason):
    got = preflight._validate_path(path)
    assert got is not None
    assert reason in got


def test_validate_path_rejects_root_when_home_is_user(monkeypatch, tmp_path):
    """/root paths leak the privilege-escalated user's home — ONLY a
    problem when the real user's home is somewhere else (the typical
    sudo-drop scenario). Pinning a user home explicitly so this stays
    deterministic regardless of who runs the test."""
    fake_home = tmp_path / "home/lester"
    fake_home.mkdir(parents=True)
    monkeypatch.setattr(preflight, "_HOME", fake_home)
    got = preflight._validate_path("/root/.local/share/icons")
    assert got is not None
    assert "leaks /root home" in got


def test_validate_path_accepts_root_when_home_is_root(monkeypatch, tmp_path):
    """Container / embedded scenario: the only user IS root, /root IS
    the legitimate home. /root paths must NOT be rejected then,
    otherwise the installer can't run on those targets."""
    monkeypatch.setattr(preflight, "_HOME", Path("/root"))
    assert preflight._validate_path("/root/.local/share/icons") is None
    assert preflight._validate_path("/root/.config/kdeglobals") is None


def test_validate_path_accepts_user_home():
    home = preflight._home()
    assert preflight._validate_path(str(home / ".local/share/icons")) is None
    assert preflight._validate_path(str(home / ".config/kdeglobals")) is None
    assert preflight._validate_path(str(home / ".cache/foo")) is None


def test_enumerate_destinations_covers_all_compiled_steps():
    """Every step that ships a compiled artefact must have its install
    destination listed in ``_enumerate_destinations`` — otherwise a new
    ``.so`` could ship to an unvalidated path and the regex check would
    silently miss it."""
    labels = {label for label, _ in preflight._enumerate_destinations()}
    # Compiled C++ destinations.
    assert "globalmenu .so" in labels
    assert "globalmenu QML module" in labels
    assert "taskmanager .so" in labels
    assert "taskmanager QML module" in labels
    assert "acrylic-glass plugin dir" in labels


def test_check_paths_passes_for_production_destinations():
    """The production destinations must all sit in allowed roots —
    this is what the install-time check asserts. If a refactor adds a
    ``.so`` destination outside ``$HOME`` / ``/usr/lib/qt6`` /
    ``/etc/sddm.conf.d`` / ``/usr/share``, this test catches it."""
    for label, path in preflight._enumerate_destinations():
        reason = preflight._validate_path(path)
        assert reason is None, f"{label}: {path} → {reason}"


def test_check_paths_handles_missing_qmake6(monkeypatch):
    """When qmake6 is absent, ``_enumerate_destinations()`` raises
    ``Qt6PathsMissing``. ``_check_paths()`` must catch it and return
    ``False`` with a user-friendly ``fail()`` that mentions
    ``qmake6`` — not a crash with a raw traceback."""
    from distro import Qt6PathsMissing

    fails: list[str] = []
    monkeypatch.setattr(preflight, "fail", fails.append)
    monkeypatch.setattr(preflight, "ok", lambda _msg: None)
    monkeypatch.setattr(preflight, "warn", lambda _msg: None)

    def _raise_qm():
        raise Qt6PathsMissing("qmake6 not found")
    monkeypatch.setattr(preflight, "_enumerate_destinations", _raise_qm)

    assert preflight._check_paths() is False
    assert any("qmake6" in f for f in fails), (
        f"expected fail() mentioning qmake6, got: {fails}"
    )


def test_home_is_resolved_per_call_not_cached(monkeypatch, tmp_path):
    """Regression for the container-matrix failure on Arch + Fedora:
    a previous test would prime ``preflight._HOME`` to a sandbox
    tmpdir (via the conftest sandbox fixture's ``$HOME`` setenv),
    that tmpdir would survive into a later test that ran on a
    different effective home, and ``_validate_path`` rejected
    ``/root/.local/share/plasma/plasmoids`` with ``leaks /root home``
    inside the container even though ``/root`` IS the real home
    there. The fix is to stop caching: ``_home()`` resolves
    ``Path.home()`` per call unless something has explicitly
    overridden ``_HOME``. This test pins both halves of the contract.

    Phase 1: with no override, two successive calls under different
    ``$HOME`` env values must report different homes — proving the
    cache is gone.

    Phase 2: with ``_HOME`` explicitly set, calls must honour the
    override — proving the test seam still works for the two existing
    tests that pin ``_HOME`` to ``/root`` / a fake user dir.
    """
    # Phase 1 — env-driven, no cache
    fake_a = tmp_path / "home-a"
    fake_a.mkdir()
    fake_b = tmp_path / "home-b"
    fake_b.mkdir()
    monkeypatch.setattr(preflight, "_HOME", None)
    monkeypatch.setenv("HOME", str(fake_a))
    first = preflight._home()
    monkeypatch.setenv("HOME", str(fake_b))
    second = preflight._home()
    assert first == fake_a, f"first call should resolve to {fake_a}, got {first}"
    assert second == fake_b, (
        f"second call should resolve to {fake_b}, got {second} — "
        "_home() is caching across calls, which is what broke the "
        "container matrix"
    )

    # Phase 2 — explicit override still wins
    pinned = tmp_path / "pinned"
    pinned.mkdir()
    monkeypatch.setattr(preflight, "_HOME", pinned)
    monkeypatch.setenv("HOME", str(fake_a))
    assert preflight._home() == pinned, (
        "explicit preflight._HOME override should beat $HOME — the "
        "two tests at test_validate_path_rejects_root_when_home_is_user "
        "and test_validate_path_accepts_root_when_home_is_root depend "
        "on this seam"
    )


# ── 2. plasmoid ID consistency ───────────────────────────────────────────

def test_plasmoid_id_consistency_across_repo():
    """For every plasmoid in ``src/offline/plasmoids/``: directory name
    must equal ``metadata.json`` ``KPlugin.Id``. Was an actual bug in
    v0.9.0 — globalmenu's source dir was kebab-case while the .so /
    QML / layout JS / cmake target all used dotted form. v0.10 renamed
    the dir; this test pins it so the drift can't come back."""
    plasmoids = OFFLINE_DIR / "plasmoids"
    assert plasmoids.is_dir(), plasmoids

    seen = 0
    for plasmoid_dir in sorted(plasmoids.iterdir()):
        if not plasmoid_dir.is_dir():
            continue
        metadata = plasmoid_dir / "metadata.json"
        if not metadata.is_file():
            continue
        seen += 1
        plugin_id = json.loads(metadata.read_text())["KPlugin"]["Id"]
        assert plasmoid_dir.name == plugin_id, (
            f"directory ``{plasmoid_dir.name}`` does not match metadata "
            f"KPlugin.Id ``{plugin_id}`` — Qt QML module URI requires "
            f"the path-form to match the dotted Id, and Plasma resolves "
            f"the package by directory name. Mismatch = applet doesn't load."
        )
    assert seen >= 4, f"expected at least 4 plasmoids, saw {seen}"


def test_layout_js_references_real_plasmoid_ids():
    """Every ``addWidget("...")`` call in the layout JS for a custom
    plasmoid must resolve to a metadata Id that exists on disk —
    otherwise the layout script silently leaves a hole in the panel
    when plasmashell can't find the package."""
    layout_js = (OFFLINE_DIR / "layouts/mac-tahoe.js").read_text()
    plasmoids_dir = OFFLINE_DIR / "plasmoids"
    real_ids = {
        json.loads((p / "metadata.json").read_text())["KPlugin"]["Id"]
        for p in plasmoids_dir.iterdir()
        if (p / "metadata.json").is_file()
    }
    # Custom MacTahoe plasmoid IDs in the layout JS.
    import re
    addwidget_calls = re.findall(
        r'addWidget\("(org\.kde\.mac[^"]+)"\)', layout_js,
    )
    for plugin_id in addwidget_calls:
        assert plugin_id in real_ids, (
            f"layout JS references ``{plugin_id}`` but no plasmoid "
            f"with that metadata.Id exists in src/offline/plasmoids/"
        )


# ── 3. Qt6 path discovery (lives in distro.py now) ──────────────────────

def test_qt6_query_returns_none_when_no_tools_present(monkeypatch):
    """When neither qmake6, qtpaths6, nor pkg-config is on PATH the
    private query chain returns None. The public ``qt6_plugins_dir()``
    then falls back to the per-distro libdir table (verified against
    on-disk reality) — see the two tests below for both paths."""
    import distro
    monkeypatch.setattr(distro.shutil, "which", lambda _: None)
    assert distro._qt6_plugins_query() is None
    assert distro._qt6_qml_query() is None


def test_qt6_falls_back_to_known_libdir_when_qmake6_missing(monkeypatch):
    """v0.15.1: if qmake6 / qtpaths6 / pkg-config are all absent but
    /etc/os-release identifies a distro whose Qt6 libdir we know AND
    that libdir actually exists on disk, return it. Plasma 6 must
    already be installed for the dir to exist, so we're not guessing
    — just reading what's already there."""
    import distro
    monkeypatch.setattr(distro.shutil, "which", lambda _: None)
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", None)
    monkeypatch.setattr(distro, "_QT_QML_CACHE", None)
    monkeypatch.setattr(distro, "current_distro", lambda: "arch")
    monkeypatch.setattr(distro, "distro_id_like", lambda: ())
    monkeypatch.setattr(distro, "_fallback_qt6_libdir",
                        lambda: distro.Path("/usr/lib/qt6")
                                if distro.Path("/usr/lib/qt6").is_dir() else None)
    # Each subdir is independent — qt6-tools brings /usr/lib/qt6/plugins
    # but qt6-declarative is what installs /usr/lib/qt6/qml. The
    # container CI image carries the former without the latter, so
    # check each fallback against its own on-disk reality.
    if distro.Path("/usr/lib/qt6/plugins").is_dir():
        assert str(distro.qt6_plugins_dir()) == "/usr/lib/qt6/plugins"
    if distro.Path("/usr/lib/qt6/qml").is_dir():
        assert str(distro.qt6_qml_dir()) == "/usr/lib/qt6/qml"


def test_qt6_raises_when_no_tools_and_no_fallback_dir(monkeypatch, tmp_path):
    """If qmake6 is missing AND the per-distro libdir doesn't exist on
    disk (e.g. an unrecognised distro, or Plasma 6 isn't installed
    yet), refuse to guess. Better to fail loudly than write .so files
    to a directory Qt6 doesn't scan."""
    import distro
    monkeypatch.setattr(distro.shutil, "which", lambda _: None)
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", None)
    monkeypatch.setattr(distro, "_QT_QML_CACHE", None)
    monkeypatch.setattr(distro, "_fallback_qt6_libdir", lambda: None)
    with pytest.raises(distro.Qt6PathsMissing):
        distro.qt6_plugins_dir()
    with pytest.raises(distro.Qt6PathsMissing):
        distro.qt6_qml_dir()


def test_install_destinations_anchor_to_qmake6_libdir(monkeypatch, tmp_path):
    """The v0.14.x Gentoo regression was: qmake6 reports
    ``/usr/lib64/qt6/plugins`` but the installer hardcoded
    ``/usr/lib/qt6/plugins`` for its writes. After v0.15.0 every Qt
    destination is rooted at the qmake6-reported dir; this test
    pretends the libdir lives under a tmp path and asserts each step's
    destination still resolves inside it.

    If a future refactor silently re-introduces a ``/usr/lib`` literal,
    relative_to() raises ValueError and the test pins it."""
    import distro
    fake_plugins = tmp_path / "fake-lib64/qt6/plugins"
    fake_qml = tmp_path / "fake-lib64/qt6/qml"
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", fake_plugins)
    monkeypatch.setattr(distro, "_QT_QML_CACHE", fake_qml)

    from steps import acrylic_glass, globalmenu, plasmoids
    for label, dest, expected_root in (
        ("globalmenu .so",       globalmenu.DEST_SO,             fake_plugins),
        ("globalmenu QML",       globalmenu.DEST_QML_DIR,        fake_qml),
        ("taskmanager .so",      plasmoids.TASKMANAGER_DEST_SO,  fake_plugins),
        ("taskmanager QML",      plasmoids.TASKMANAGER_DEST_QML, fake_qml),
        ("acrylic-glass plugin", acrylic_glass._plugin_dir(),    fake_plugins),
    ):
        # relative_to() raises ValueError if dest is not under root —
        # that IS the failure mode the v0.14.x Gentoo bug hit.
        dest.relative_to(expected_root)


def test_qt6_query_skips_tools_that_exit_nonzero(monkeypatch):
    """A qmake6 that exits non-zero (broken Qt install, sandboxed env)
    must not be treated as a successful path discovery — fall through
    to the next tool in the chain. With every tool failing AND the
    libdir fallback stubbed out, qt6_plugins_dir() raises."""
    from types import SimpleNamespace
    import distro
    monkeypatch.setattr(distro.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        distro.subprocess, "run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="oops"),
    )
    monkeypatch.setattr(distro, "_QT_PLUGINS_CACHE", None)
    monkeypatch.setattr(distro, "_fallback_qt6_libdir", lambda: None)
    assert distro._qt6_plugins_query() is None
    with pytest.raises(distro.Qt6PathsMissing):
        distro.qt6_plugins_dir()


# ── 4. KDE Plasma version (v0.15.6) ─────────────────────────────────


def test_plasma_version_accepts_6_6(monkeypatch):
    """plasmashell --version output: "plasmashell 6.6.4". The version
    extractor must accept the canonical form."""
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        preflight, "run_user",
        lambda *a, **kw: SimpleNamespace(
            returncode=0, stdout="plasmashell 6.6.4\n", stderr="",
        ),
    )
    assert preflight._check_plasma_version() is True


def test_plasma_version_accepts_future_majors(monkeypatch):
    """7.0+ must pass even though we compile against 6.6 — newer
    Plasma is forward-compatible with our plasmoids."""
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        preflight, "run_user",
        lambda *a, **kw: SimpleNamespace(
            returncode=0, stdout="plasmashell 7.0.0\n", stderr="",
        ),
    )
    assert preflight._check_plasma_version() is True


def test_plasma_version_rejects_too_old(monkeypatch):
    """Plasma 6.5 (or earlier) is below our 6.6+ minimum. The check
    must fail loudly with the actual detected version + the floor."""
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        preflight, "run_user",
        lambda *a, **kw: SimpleNamespace(
            returncode=0, stdout="plasmashell 6.5.5\n", stderr="",
        ),
    )
    assert preflight._check_plasma_version() is False


def test_plasma_version_rejects_when_plasmashell_missing(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda _cmd: None)
    assert preflight._check_plasma_version() is False


def test_plasma_version_rejects_unparseable_output(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        preflight, "run_user",
        lambda *a, **kw: SimpleNamespace(
            returncode=0, stdout="garbage no numbers here\n", stderr="",
        ),
    )
    assert preflight._check_plasma_version() is False


def test_plasma_version_drops_privs_in_child(monkeypatch):
    """Regression guard for the v0.15.6 setuid abort. When the
    installer runs as sudo (real UID=0, effective UID=SUDO_USER),
    Qt6's getuid()!=geteuid() guard aborts plasmashell --version with
    a FATAL setuid error before parsing any args. The check MUST go
    through ``utils.run_user`` (which sets preexec_fn=drop_privs_in_child
    so the child has matching real/effective/saved UIDs)."""
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")

    seen_runner = []

    def fake_run_user(cmd, **kwargs):
        seen_runner.append(cmd)
        return SimpleNamespace(returncode=0, stdout="plasmashell 6.6\n", stderr="")

    monkeypatch.setattr(preflight, "run_user", fake_run_user)
    # If the implementation regressed to plain subprocess.run, this
    # would still pass via the inherited subprocess mock, so trap
    # subprocess.run to ensure it isn't reached.
    def boom(*a, **kw):
        raise AssertionError("plasmashell --version reached subprocess.run "
                             "directly — must go through run_user to dodge "
                             "Qt6's setuid abort under sudo")
    monkeypatch.setattr(preflight.subprocess, "run", boom)

    assert preflight._check_plasma_version() is True
    assert seen_runner and seen_runner[0][0] == "plasmashell"


def test_plasma_version_falls_back_to_package_metadata_after_timeout(monkeypatch):
    """Real openSUSE Plasma sessions can hang on ``plasmashell --version``
    even though Plasma itself is up and running. Preflight should fall
    back to distro package metadata before failing the whole install."""
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        preflight,
        "plasma_version_probe_cmds",
        lambda: (["rpm", "-q", "--qf", "%{VERSION}\\n", "plasma6-workspace"],),
    )

    seen = []

    def fake_run_user(cmd, **kwargs):
        seen.append(cmd)
        if cmd[:2] == ["plasmashell", "--version"]:
            raise preflight.subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        if cmd[:2] == ["plasmashell", "-v"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:2] == ["rpm", "-q"]:
            return SimpleNamespace(returncode=0, stdout="6.6.5\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd!r}")

    monkeypatch.setattr(preflight, "run_user", fake_run_user)

    assert preflight._check_plasma_version() is True
    assert seen[:3] == [
        ["plasmashell", "--version"],
        ["plasmashell", "-v"],
        ["rpm", "-q", "--qf", "%{VERSION}\\n", "plasma6-workspace"],
    ]


# ── 5. KDE config tools ─────────────────────────────────────────────


def test_kde_config_tools_pass_when_both_present(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    assert preflight._check_kde_config_tools() is True


def test_kde_config_tools_fail_when_kwriteconfig6_missing(monkeypatch):
    monkeypatch.setattr(
        preflight.shutil, "which",
        lambda cmd: None if cmd == "kwriteconfig6" else f"/usr/bin/{cmd}",
    )
    assert preflight._check_kde_config_tools() is False


def test_kde_config_tools_fail_when_kreadconfig6_missing(monkeypatch):
    monkeypatch.setattr(
        preflight.shutil, "which",
        lambda cmd: None if cmd == "kreadconfig6" else f"/usr/bin/{cmd}",
    )
    assert preflight._check_kde_config_tools() is False


# ── 6. DBus session bus ─────────────────────────────────────────────


def test_dbus_session_passes_with_address_env(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS",
                       "unix:path=/run/user/1000/bus")
    assert preflight._check_dbus_session() is True


def test_dbus_session_falls_back_to_xdg_runtime_bus(monkeypatch, tmp_path):
    """sudo can strip DBUS_SESSION_BUS_ADDRESS. The XDG_RUNTIME_DIR/bus
    socket is the canonical fallback path systemd-user exposes."""
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    runtime = tmp_path / "run-user-1000"
    runtime.mkdir()
    (runtime / "bus").touch()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    assert preflight._check_dbus_session() is True


def test_dbus_session_fails_when_both_address_and_socket_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "nonexistent"))
    assert preflight._check_dbus_session() is False


# ── 7. kded6 health (soft) ──────────────────────────────────────────


def test_kded6_check_is_soft_when_not_running(monkeypatch):
    """kded6 not running is a soft failure — install can still
    complete, the user just may need to re-login. preflight returns
    True so the install proceeds."""
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        preflight.subprocess, "run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    assert preflight._check_kded_running() is True


def test_kded6_check_passes_when_running(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        preflight.subprocess, "run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="1234\n", stderr=""),
    )
    assert preflight._check_kded_running() is True


def test_kded6_check_passes_when_pgrep_missing(monkeypatch):
    """Skipping is also a soft pass — pgrep isn't strictly required
    for the install."""
    monkeypatch.setattr(preflight.shutil, "which",
                        lambda cmd: None if cmd == "pgrep" else f"/usr/bin/{cmd}")
    assert preflight._check_kded_running() is True


# ── 8. disk space ───────────────────────────────────────────────────


def test_disk_space_passes_with_plenty_free(monkeypatch, tmp_path):
    from collections import namedtuple
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(
        preflight.shutil, "disk_usage",
        lambda _p: Usage(total=10**12, used=0, free=10**12),
    )
    assert preflight._check_disk_space() is True


def test_disk_space_fails_when_usr_below_floor(monkeypatch):
    """Less than _MIN_FREE_USR_MB free where the Qt6 plugin dir
    lives → fail (compiled .so won't fit / writes will EIO)."""
    from collections import namedtuple
    Usage = namedtuple("Usage", "total used free")
    # 10 MB free — below the 50 MB floor.
    monkeypatch.setattr(
        preflight.shutil, "disk_usage",
        lambda _p: Usage(total=10**9, used=10**9 - 10*1024*1024,
                         free=10 * 1024 * 1024),
    )
    assert preflight._check_disk_space() is False


def test_disk_space_soft_skip_when_qt6_paths_missing(monkeypatch):
    """If Qt6 isn't discoverable, step 3 already failed with a hint.
    Disk space probe shouldn't crash — just warn-and-skip."""
    import distro
    def boom():
        raise distro.Qt6PathsMissing("no qt6")
    monkeypatch.setattr(preflight, "qt6_plugins_dir", boom)
    assert preflight._check_disk_space() is True  # soft — doesn't block
