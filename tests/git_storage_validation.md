# Installer Git storage validation — v0.61.18

The shared implementation preserves `.git` and full commit/tree ancestry while
retiring verified published file caches and older-version merged branches.
Both editions use it; Golden Gate delegates for its own clone and a selected
Tahoe sibling. Updaters retain dirty, staged, deleted, untracked and divergent
work, including equal-VERSION unpublished commits and ignored-file collisions.
No desktop, visual asset, native backend, ABI or SDK behavior changed.

## Focused development and integration

Linux host, Python 3.14, Git 2.55.0; disposable Git fixtures, no live installer:

```sh
python3 -m pytest tests/test_repository_cache.py tests/test_repository_history.py tests/test_repository_maintenance.py tests/test_auto_update.py tests/test_git_process_maintenance.py tests/test_release_screenshots.py tests/test_static.py tests/test_release_update.py -q
```

164 passed. The 127 affected updater/cache/provenance checks also passed in a
Golden Gate source prepared from the candidate with
`GOLDEN_GATE_TAHOE_SOURCE=<candidate> MAC_TAHOE_NO_UPDATE_CHECK=true python3 installer --prepare`.
Golden Gate's complete wrapper suite passed 95 tests. Collection is 2104 Tahoe
tests; collection is not a claim that every conditional native check ran locally.

A network-disabled, read-only KDE neon container with Git 2.43.0 passed the
84 updater/history/cache/maintenance/Trace2 checks. The synthetic history uses
successive binary asset replacements, main and dev pulls, a merge from an old
release base, repeated cleanup of hydrated promisor blobs, and historical lazy
retrieval. Tests preserve current tips, tags, private branches/tags, stashes,
reflog-only and dangling work, index contents, edited/deleted/untracked files,
linked worktrees, recovery journals and shared stores. Concurrent work aborts
eviction; interrupted stages and a terminated process recover only our own
marked locks. Unrecognized recovery metadata and external locks are preserved.
Trace2's negative control detects Git's default auto-maintenance, while actual
updater processes suppress it. Ignored-file overwrite controls reproduced the
old failure before `--no-overwrite-ignore` was added.

## Real repository storage measurements

Only independent disposable canonical clones were modified. The original
working checkouts, other agents' branches, captures and development files were
not edited. Inputs were published v0.61.17: Tahoe
`36d21558242cb4130622f4441adff49bc6b2d477` and Golden Gate `8b6b2742914d8980acf79de6944877c9cce17bea`.

| Git store | Before (allocated bytes) | After | Recovered | Public obsolete blobs | Merged cached refs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tahoe | 2039590912 | 332283904 | 83.7% | 670 | 6 |
| Golden Gate | 746897408 | 68452352 | 90.8% | 464 | 4 |

Tahoe retains all 930 commits in HEAD's graph; canonical tags, current source
and main/dev positions remain. `git fsck --full` passed and an ordinary
`git pull --ff-only` still works. Savings vary with retained branch snapshots,
unmerged remote work and historical assets; these numbers are not fixed size
promises. Private/development/unverified stores use packing only. Missing public
historical blobs require origin connectivity when first requested.

## Release gates and visual provenance

Required `test.yml` **push** runs on main and dev must pass for each exact
release commit before publication. Inspect the immutable tag's SHA against
[Tahoe CI](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml)
and [Golden Gate CI](https://github.com/lestercorderomurillo/macos-golden-gate-liquid-kde/actions/workflows/test.yml).
Required CI supplies the complete suite and configured distro matrix; the Git
version probes above do not replace distro/native qualification.
Publication uses each repository's release workflow, Tahoe first, followed by
its published immutable archive checksum and Golden Gate pin verification.

Existing reviewed screenshots and their original provenance are retained.
The console-only modules and updater functions are excluded from the visual
fingerprint; regression checks still reject visible-label/entry changes.
`release-screenshots verify` is required on both final commits. No new VM,
visual captures, host desktop changes or duplicate local distro matrix is
justified by these changes.

## Candidate executable content

The immutable v0.61.18 tag identifies the final source. These executable hashes
make the focused evidence independent of later documentation/commit metadata.

| Path | SHA-256 |
| --- | --- |
| `src/scripts/cli.py` | `3219ecf03b8efe5ace3361cab78bcbf9315779597dfbe985a618af642aa32679` |
| `src/scripts/repository_cache.py` | `9239685a02865020e68864e1e67288d64d0fb998fd104703813ab5089977f805` |
| `src/scripts/repository_history.py` | `631b811fa28c64b155827b993d84a3c3afcb0084f2e4ea9b68ba8c17e134a333` |
| `src/scripts/repository_maintenance.py` | `e49637a96b4fe11ef3385fbfd3d85738d5a0b10ede4613c71835020210aa8da7` |
