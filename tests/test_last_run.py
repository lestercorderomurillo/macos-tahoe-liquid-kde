"""Last-run JSON tracker."""

import json
import os
import subprocess
from pathlib import Path

import pytest


def test_last_run_records_completed(sandbox, repo, monkeypatch):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(sandbox / ".local/share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(sandbox / ".config"))

    rc = subprocess.run(
        ["python3", "-c",
         "from installer.state import RunTracker;"
         "t = RunTracker('install', ['--dark', '--no-gtk', '--save'], 'dark');"
         "t.start(); t.mark_completed(); t.finalize(0)"],
        check=False, env={**os.environ,
                          "HOME": str(sandbox),
                          "XDG_STATE_HOME": "",
                          "XDG_DATA_HOME": str(sandbox / ".local/share"),
                          "XDG_CONFIG_HOME": str(sandbox / ".config")},
        cwd=str(repo / "src/scripts"),
    ).returncode
    assert rc == 0

    last = sandbox / ".local/state/mac-tahoe-liquid-kde/last-run.json"
    assert last.is_file()
    payload = json.loads(last.read_text())
    assert payload["script"] == "install"
    assert payload["argv"] == ["--dark", "--no-gtk", "--save"]
    assert payload["command"] == "./install --dark --no-gtk --save"
    assert payload["status"] == "completed"
    assert payload["theme_mode"] == "dark"


def test_last_run_records_aborted(sandbox, repo):
    rc = subprocess.run(
        ["python3", "-c",
         "from installer.state import RunTracker;"
         "t = RunTracker('install', [], 'auto');"
         "t.start(); t.mark_aborted(); t.finalize(0)"],
        check=False, env={**os.environ, "HOME": str(sandbox)},
        cwd=str(repo / "src/scripts"),
    ).returncode
    assert rc == 0
    last = sandbox / ".local/state/mac-tahoe-liquid-kde/last-run.json"
    assert json.loads(last.read_text())["status"] == "aborted"


def test_last_run_records_failure(sandbox, repo):
    rc = subprocess.run(
        ["python3", "-c",
         "from installer.state import RunTracker;"
         "t = RunTracker('install', [], 'auto'); t.start(); t.finalize(1)"],
        check=False, env={**os.environ, "HOME": str(sandbox)},
        cwd=str(repo / "src/scripts"),
    ).returncode
    assert rc == 0
    last = sandbox / ".local/state/mac-tahoe-liquid-kde/last-run.json"
    assert json.loads(last.read_text())["status"] == "failed"
