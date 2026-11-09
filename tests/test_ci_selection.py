"""CI partitions preserve coverage and avoid repeating package queries."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location('ci_selection_probe', ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shards_cover_every_test_file_exactly_once():
    shard = load('.github/scripts/test_shard.py')
    parts = [set(shard.select_files(ROOT, index, 2)) for index in range(2)]
    expected = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'tests').rglob('test_*.py')}
    assert parts[0] and parts[1]
    assert not parts[0] & parts[1]
    assert parts[0] | parts[1] == expected
    with pytest.raises(ValueError):
        shard.select_files(ROOT, 2, 2)


def test_package_queries_are_deduplicated_without_hiding_failure(monkeypatch):
    runner = load('tests/containers/run_in_container.py')
    calls = []
    def query(args, **kwargs):
        calls.append(args[-1])
        return SimpleNamespace(returncode=int(args[-1] == 'missing'), stderr='')
    monkeypatch.setattr(runner.subprocess, 'run', query)
    result = runner._probe_packages(['apt', 'show'], ['found', 'missing', 'found'])
    assert sorted(calls) == ['found', 'missing']
    assert result['found'].returncode == 0
    assert result['missing'].returncode == 1
