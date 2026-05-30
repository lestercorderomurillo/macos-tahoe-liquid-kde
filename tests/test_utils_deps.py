from types import SimpleNamespace

import utils


def test_dep_available_treats_ecm_as_cmake_package(monkeypatch):
    seen = []

    monkeypatch.setattr(utils, "have", lambda cmd: cmd == "cmake")

    def fake_run_user(cmd, **kwargs):
        seen.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(utils, "run_user", fake_run_user)

    assert utils._dep_available("ecm") is True
    assert seen == [[
        "cmake",
        "--find-package",
        "-DNAME=ECM",
        "-DCOMPILER_ID=GNU",
        "-DLANGUAGE=CXX",
        "-DMODE=EXIST",
    ]]


def test_dep_available_reports_ecm_missing_when_cmake_cannot_find_it(monkeypatch):
    monkeypatch.setattr(utils, "have", lambda cmd: cmd == "cmake")
    monkeypatch.setattr(
        utils,
        "run_user",
        lambda *a, **kw: SimpleNamespace(returncode=1),
    )

    assert utils._dep_available("ecm") is False
