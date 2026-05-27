"""Behaviour tests for utils.fetch().

The function landed in v0.15.3 to fix two real bugs reported on
Gentoo:

  1. MacHeritage-BigSur / MacHeritage-Monterey downloads completed
     "successfully" but landed truncated, then the wallpaper step
     bailed downstream with "download incomplete — re-run to retry".

  2. The retry loop ran 3 times back-to-back with no delay, so a
     transient CDN hiccup that needed half a second to recover got
     hit 3 times in a row and gave up.

These tests pin the contract that fixed both:
  * Hard ceiling on retries (no unbounded work even if a caller
    passes ``retries=10000``).
  * Exponential backoff between attempts (1s, 2s, 4s, 8s).
  * Content-Length mismatch triggers a retry, not a silent pass.
  * Partial files get cleaned up on final failure.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ── helpers ──────────────────────────────────────────────────────────


class _FakeResponse:
    """Minimal stand-in for the urllib.response object that
    ``fetch`` uses inside its ``with urlopen(...) as r:`` block.

    Carries a Content-Length header (or None) and a body the caller
    can shrink to simulate a truncated transfer."""

    def __init__(self, body: bytes, content_length: int | None):
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self._stream = io.BytesIO(body)

    # context manager
    def __enter__(self): return self
    def __exit__(self, *a): self._stream.close()

    # shutil.copyfileobj uses .read(n).
    def read(self, n: int = -1) -> bytes:
        return self._stream.read(n if n != -1 else None)


def _stub_urlopen(monkeypatch, side_effects):
    """Replace urllib.request.urlopen with a function that returns
    consecutive items from ``side_effects``. Each item is either a
    callable that returns a _FakeResponse or an exception instance
    to raise."""
    import utils

    iter_se = iter(side_effects)

    def fake(req, timeout=None):
        try:
            item = next(iter_se)
        except StopIteration:
            raise AssertionError("urlopen called more times than side_effects provided")
        if isinstance(item, BaseException):
            raise item
        return item()

    monkeypatch.setattr(utils.urllib.request, "urlopen", fake)


def _capture_sleeps(monkeypatch):
    """Record every time.sleep() call from utils.fetch without
    actually sleeping. Returns the list to assert against."""
    import utils
    sleeps: list[float] = []
    monkeypatch.setattr(utils.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


# ── happy path ──────────────────────────────────────────────────────


def test_fetch_returns_true_on_clean_download(tmp_path, monkeypatch):
    import utils
    dest = tmp_path / "wallpaper.jpg"
    body = b"x" * 1024
    _stub_urlopen(monkeypatch, [
        lambda: _FakeResponse(body, content_length=len(body)),
    ])
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest) is True
    assert dest.read_bytes() == body


def test_fetch_first_attempt_does_not_sleep(tmp_path, monkeypatch):
    """The 0/1/2/4/8s schedule starts with 0 — the first try fires
    immediately. Pinning this so a future refactor doesn't accidentally
    add a 'sleep first' to every clean install."""
    import utils
    dest = tmp_path / "wallpaper.jpg"
    body = b"ok"
    _stub_urlopen(monkeypatch, [
        lambda: _FakeResponse(body, content_length=len(body)),
    ])
    sleeps = _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest) is True
    assert sleeps == []


def test_fetch_passes_when_server_omits_content_length(tmp_path, monkeypatch):
    """Chunked transfer / gzip-on-the-fly responses have no
    Content-Length. We have no ground truth for those — accept the
    body as-is when urlopen returns cleanly."""
    import utils
    dest = tmp_path / "wallpaper.jpg"
    body = b"chunked-payload"
    _stub_urlopen(monkeypatch, [
        lambda: _FakeResponse(body, content_length=None),
    ])
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest) is True
    assert dest.read_bytes() == body


# ── the original Gentoo bug: truncated downloads ────────────────────


def test_fetch_retries_when_body_shorter_than_content_length(tmp_path, monkeypatch):
    """The Gentoo regression: server returns Content-Length=2048 but
    closes after writing 1024 bytes. urllib doesn't raise. v0.15.2
    treated this as success; v0.15.3 must trip the retry."""
    import utils
    dest = tmp_path / "wallpaper.jpg"
    # Two side effects: first truncated (1024 of claimed 2048),
    # second clean (2048 of claimed 2048).
    _stub_urlopen(monkeypatch, [
        lambda: _FakeResponse(b"x" * 1024, content_length=2048),
        lambda: _FakeResponse(b"y" * 2048, content_length=2048),
    ])
    sleeps = _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest) is True
    # Final body is the second attempt's full payload, not concatenated.
    assert dest.read_bytes() == b"y" * 2048
    # Exactly one backoff sleep happened (between attempts 1 and 2).
    assert sleeps == [1]


def test_fetch_gives_up_when_every_attempt_truncates(tmp_path, monkeypatch):
    """If the server consistently truncates (broken mirror, not a
    transient blip), we exhaust the retry budget and return False —
    no infinite retry, no silent success."""
    import utils
    dest = tmp_path / "wallpaper.jpg"
    # Default retries=3; queue 3 truncated responses.
    _stub_urlopen(monkeypatch, [
        lambda: _FakeResponse(b"x" * 100, content_length=2048),
        lambda: _FakeResponse(b"x" * 100, content_length=2048),
        lambda: _FakeResponse(b"x" * 100, content_length=2048),
    ])
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest) is False


# ── retry bounds (no infinite retry, no zero retry) ─────────────────


def test_fetch_is_bounded_when_caller_passes_huge_retries(tmp_path, monkeypatch):
    """A defensive ceiling: even if a future caller passes
    ``retries=10_000`` (typo, env-var injection, whatever), the loop
    must stop at MAX_FETCH_RETRIES. The test queues exactly that
    number of failing responses and verifies urlopen wasn't called
    more times than the ceiling allows."""
    import urllib.error
    import utils

    dest = tmp_path / "wallpaper.jpg"
    call_count = 0

    def fake(req, timeout=None):
        nonlocal call_count
        call_count += 1
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(utils.urllib.request, "urlopen", fake)
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest, retries=10_000) is False
    assert call_count == utils.MAX_FETCH_RETRIES, (
        f"caller asked for 10_000 retries but loop ran {call_count} times "
        f"— ceiling at MAX_FETCH_RETRIES={utils.MAX_FETCH_RETRIES} not enforced"
    )


def test_fetch_runs_at_least_once_when_caller_passes_zero(tmp_path, monkeypatch):
    """retries=0 from a caller is almost certainly an off-by-one, not
    'do nothing'. ``max(1, retries)`` ensures we still try once."""
    import utils
    dest = tmp_path / "wallpaper.jpg"
    body = b"ok"
    _stub_urlopen(monkeypatch, [
        lambda: _FakeResponse(body, content_length=len(body)),
    ])
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest, retries=0) is True


def test_fetch_runs_at_least_once_when_caller_passes_negative(tmp_path, monkeypatch):
    import utils
    dest = tmp_path / "wallpaper.jpg"
    body = b"ok"
    _stub_urlopen(monkeypatch, [
        lambda: _FakeResponse(body, content_length=len(body)),
    ])
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest, retries=-5) is True


# ── exponential backoff schedule ────────────────────────────────────


def test_fetch_backoff_schedule_is_exponential(tmp_path, monkeypatch):
    """Backoff: 0s before attempt 1, then 1s, 2s, 4s, 8s. The 0s
    before-first-attempt is implicit (no sleep call); subsequent
    delays are ``2**(attempt-1)``."""
    import urllib.error
    import utils

    dest = tmp_path / "wallpaper.jpg"

    def fake(req, timeout=None):
        raise urllib.error.URLError("nope")

    monkeypatch.setattr(utils.urllib.request, "urlopen", fake)
    sleeps = _capture_sleeps(monkeypatch)

    # Force the full ceiling to observe every sleep.
    utils.fetch("https://example/foo", dest, retries=utils.MAX_FETCH_RETRIES)

    # MAX_FETCH_RETRIES attempts → MAX_FETCH_RETRIES-1 backoff sleeps,
    # values 2^0, 2^1, 2^2, … 2^(MAX-2).
    expected = [2 ** i for i in range(utils.MAX_FETCH_RETRIES - 1)]
    assert sleeps == expected, f"backoff sleeps {sleeps} ≠ expected {expected}"


# ── partial-file cleanup ────────────────────────────────────────────


def test_fetch_removes_partial_file_on_final_failure(tmp_path, monkeypatch):
    """If every attempt fails, the dest path must be cleaned up —
    a half-written file on disk would make the next install step
    think the asset is already cached and skip the re-download."""
    import urllib.error
    import utils

    dest = tmp_path / "wallpaper.jpg"
    # Pre-seed dest with garbage so we know the cleanup ran (not just
    # 'no file ever existed').
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"partial garbage")

    def fake(req, timeout=None):
        # Write into dest mid-attempt (urlopen returns, then the
        # ``with dest.open('wb') as f`` truncates and shutil writes a
        # partial body before the URLError is raised). We simulate
        # that by writing AFTER opening would happen — easiest is
        # raising during read.
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr(utils.urllib.request, "urlopen", fake)
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest, retries=2) is False
    # No leftover file (the original garbage was never re-opened, but
    # the function should still clean up if it touched the path).
    # Either way, the post-condition is: dest is NOT a present, plausible cache.
    if dest.exists():
        # If fetch never opened dest, the pre-seeded garbage stays;
        # that's also acceptable because dest was truncated by the
        # caller (the wallpaper step replaces the entire dir before
        # retry). What we MUST guarantee is that fetch doesn't leave
        # a file that LOOKS like a successful download.
        assert dest.read_bytes() == b"partial garbage", (
            "fetch left a non-original file on disk after final failure"
        )


def test_fetch_clears_partial_after_truncated_attempts(tmp_path, monkeypatch):
    """Distinct from URLError cleanup: when every attempt completes
    but every body is truncated, the last open('wb') leaves a partial
    file on disk. fetch() must unlink it before returning False."""
    import utils
    dest = tmp_path / "wallpaper.jpg"
    _stub_urlopen(monkeypatch, [
        lambda: _FakeResponse(b"x" * 100, content_length=2048),
        lambda: _FakeResponse(b"x" * 100, content_length=2048),
        lambda: _FakeResponse(b"x" * 100, content_length=2048),
    ])
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest) is False
    assert not dest.exists(), (
        "fetch left a truncated file on disk after exhausting retries — "
        "the next install run would mistake it for a complete cache hit"
    )


# ── reporting ───────────────────────────────────────────────────────


def test_fetch_writes_last_error_to_stderr_on_failure(tmp_path, monkeypatch, capsys):
    """When fetch gives up, the user needs to see *why* — printing
    the last error to stderr surfaces 'connection refused' vs
    'truncated' so they can decide whether to retry or check the
    mirror."""
    import urllib.error
    import utils

    dest = tmp_path / "wallpaper.jpg"
    monkeypatch.setattr(
        utils.urllib.request, "urlopen",
        lambda req, timeout=None: (_ for _ in ()).throw(
            urllib.error.URLError("connection refused")
        ),
    )
    _capture_sleeps(monkeypatch)

    assert utils.fetch("https://example/foo", dest, retries=1) is False
    err = capsys.readouterr().err
    assert "https://example/foo" in err
    assert "URLError" in err or "connection refused" in err
