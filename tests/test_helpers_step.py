# USELESS: helpers in isolation — destination correctness for actual Plasma load is not validated
from steps import _helpers


def test_as_root_re_elevates_and_restores_in_safe_order(monkeypatch):
    calls = []

    monkeypatch.setattr(_helpers.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(_helpers.os, "getegid", lambda: 1000)
    monkeypatch.setattr(_helpers.os, "seteuid", lambda value: calls.append(("seteuid", value)))
    monkeypatch.setattr(_helpers.os, "setegid", lambda value: calls.append(("setegid", value)))

    with _helpers._as_root():
        calls.append(("body", None))

    assert calls == [
        ("seteuid", 0),
        ("setegid", 0),
        ("body", None),
        ("setegid", 1000),
        ("seteuid", 1000),
    ]
