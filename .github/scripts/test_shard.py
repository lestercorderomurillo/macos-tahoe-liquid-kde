"""Run disjoint file shards so module-scoped native fixtures are built once."""
from pathlib import Path
import subprocess
import sys


def select_files(root: Path, index: int, count: int) -> list[str]:
    if count < 1 or not 0 <= index < count:
        raise ValueError('Invalid shard index/count')
    files = sorted(path.relative_to(root).as_posix()
                   for path in (root / 'tests').rglob('test_*.py')
                   if 'containers' not in path.relative_to(root / 'tests').parts)
    return files[index::count]


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    index, count = map(int, sys.argv[1:])
    files = select_files(root, index, count)
    if not files:
        raise ValueError('Empty test shard')
    return subprocess.call([sys.executable, '-m', 'pytest', *files, '-q',
                            '--durations=10', f'--junitxml=build/ci/shard-{index}.xml'], cwd=root)


if __name__ == '__main__':
    raise SystemExit(main())
