# Installer storage validation — v0.61.15

The changed paths are the `install`/`installer` entry points, shared
`repository_maintenance.py`, Golden Gate's downloader dispatch and the
nonvisual source fingerprint used to retain reviewed screenshots. Both editions
use the shared implementation. No native backend, SDK, rendered UI, material or
installed desktop asset changes.

## Source and environment

- Release source: immutable Tahoe tag `v0.61.15` and its companion Golden Gate
  release pin. The implementation was finalized at Tahoe `7d37001`; subsequent
  release changes affect version/documentation only.
- `repository_maintenance.py` SHA-256:
  `a3979d5ed5a542f7c4ab1c18951bb4f62c08501873f9c41946c57f9ac9cb058d`.
- Both Tahoe entry points have SHA-256:
  `b817aa983386af3bcb392c04fcc17381a05b950c9e4d4cd72edcaafa2f52cbb8`.
- Linux x86_64 (CachyOS), Python 3.14.7, Git 2.55.0; isolated repositories and
  prepared Golden Gate source under `/tmp`. No live installation or host
  desktop changes.

## Focused validation

```sh
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_repository_maintenance.py tests/test_auto_update.py \
  tests/test_release_update.py tests/test_release_screenshots.py \
  tests/test_installer_ui.py tests/test_localization.py tests/test_multilanguage.py -q
```

The focused set has 166 passing checks, with affected console/fingerprint checks
rerun after the final adjustment (90 passed). It covers actual Git repacking and
space recovery while retaining refs, stashes, old unreferenced objects, reflogs,
index contents, staged/unstaged/untracked files and conflict-resolution caches.
Immediate-expiry settings and explicitly enabled destructive maintenance tasks
cannot enable deletion. A pre-fix `gc --no-prune` control failed by deleting the
conflict-resolution cache; packing-only maintenance preserves it. Automatic tasks
were forced and repeated to exercise retirement of redundant packs.

Entry-point tests exercise restart signals from older published updaters and
confirm that a maintenance failure still opens the wizard. Linked worktrees and
shared object stores are skipped. Screenshot tests verify that nonvisual
maintenance changes preserve provenance, while visible labels and graphical
entry-point changes still invalidate it.

Golden Gate's wrapper suite (`python3 -m pytest tests -q`) passed all 89 checks
locally and at [the implementation CI run](https://github.com/lestercorderomurillo/macos-golden-gate-liquid-kde/actions/runs/41174382179).
Coverage includes local staging, release fallback, checksum/version handling,
manual maintenance dispatch, read-only entry points and maintenance failures.
Affected shared checks are also run on the content-addressed source printed by:

```sh
GOLDEN_GATE_TAHOE_SOURCE=/tmp/tahoe-smart-cleanup ./installer --prepare
# In the printed source directory:
python3 -m pytest tests/test_repository_maintenance.py tests/test_auto_update.py tests/test_release_update.py -q
```

## Integration and limits

The development full suite on prepared Golden Gate source exercised 2,047 cases:
2,024 passed, four skipped and 19 failed. Two missing console translations were
corrected and their affected tests passed. The other 17 failures require local
D-Bus/X11 sockets denied by the sandbox. Those failures are coverage limits;
the local full suite is not reported as passing. The final set collects 2,048
cases, including the older-updater restart regression.

Required `test.yml` push runs on both `main` and `dev` for both exact release
commits remain the publication gate. They supply complete configured CI and
distro coverage; earlier-commit or PR results do not replace that gate.
No duplicate local distro matrix or unrelated desktop lifecycle run was started.

Both editions' existing screenshots verify with `release-screenshots verify`
(Golden Gate additionally uses `--repo` and `--tahoe-repo`). Their original
v0.61.12 capture provenance is retained; no new captures were warranted.
Compaction preserves historical assets referenced by commits and can recover
little from an already packed clone. It requires temporary disk space and
does not promise a particular final repository size.
