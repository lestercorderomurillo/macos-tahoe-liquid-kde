"""Published updates must not install an arbitrary development branch tip."""
import subprocess

import pytest


@pytest.mark.parametrize("case", ["published", "dirty", "diverged", "wrong-version", "offline"])
def test_update_uses_verified_release_commit(tmp_path, monkeypatch, case):
    import cli

    def git(root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    def commit(root, version):
        (root / "VERSION").write_text(version + "\n")
        git(root, "add", "VERSION")
        git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-qm", version)
        return git(root, "rev-parse", "HEAD")

    remote = tmp_path / "remote"
    remote.mkdir()
    git(remote, "init", "-q")
    commit(remote, "1.0.0")
    checkout = tmp_path / "checkout"
    git(tmp_path, "clone", "-q", str(remote), str(checkout))
    release = commit(remote, "2.0.0" if case != "wrong-version" else "1.5.0")
    git(remote, "tag", "v2.0.0")
    commit(remote, "3.0.0")  # unpublished branch tip must never be installed
    if case == "dirty":
        (checkout / "VERSION").write_text("local edit\n")
    if case == "diverged":
        commit(checkout, "1.1.0")
    before = git(checkout, "rev-parse", "HEAD")
    content = (checkout / "VERSION").read_text()

    calls, execs = [], []
    def invoke(*args, capture=False):
        calls.append(args)
        if args[0] == "fetch":
            assert args[2] == "https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde.git"
            args = (*args[:2], str(remote if case != "offline" else tmp_path / "missing"), *args[3:])
        return subprocess.run(["git", "-C", str(checkout), *args], text=True, capture_output=True)

    monkeypatch.setattr(cli, "REPO_ROOT", checkout)
    monkeypatch.setattr(cli, "read_version", lambda: "1.0.0")
    monkeypatch.setattr(cli, "fetch_latest_release", lambda: "2.0.0")
    monkeypatch.setattr(cli, "_git", invoke)
    monkeypatch.setattr(cli.os, "execv", lambda *args: execs.append(args))
    monkeypatch.delenv("MAC_TAHOE_UPDATED", raising=False)
    monkeypatch.delenv("MAC_TAHOE_NO_UPDATE_CHECK", raising=False)
    cli.auto_update_and_reexec([], prog="installer")
    assert not any(call[0] == "pull" for call in calls)
    if case == "published":
        assert git(checkout, "rev-parse", "HEAD") == release
        assert (checkout / "VERSION").read_text() == "2.0.0\n"
        assert execs == [(str(checkout / "installer"), [str(checkout / "installer")])]
    else:
        assert git(checkout, "rev-parse", "HEAD") == before
        assert (checkout / "VERSION").read_text() == content
        assert execs == []


@pytest.mark.parametrize("uninstall", [False, True])
def test_update_happens_before_options_and_never_on_uninstall(monkeypatch, uninstall):
    import cli
    import installer_ui
    events = []
    monkeypatch.setattr(installer_ui, "drop_root_to_invoking_user", lambda: 0)
    monkeypatch.setattr(cli, "auto_update_and_reexec", lambda *a, **k: events.append("update"))
    monkeypatch.setattr(installer_ui, "launch_preview", lambda *a: events.append("wizard") or 0)
    assert installer_ui.main(["--uninstall"] if uninstall else []) == 0
    assert events == (["wizard"] if uninstall else ["update", "wizard"])
