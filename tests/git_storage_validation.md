# Installer Git storage validation — v0.61.19

The shared implementation preserves `.git` and full commit/tree ancestry while
retiring verified published file caches and older-version merged branches.
Both editions use it; Golden Gate delegates for its own clone and a selected
Tahoe sibling. Updaters retain dirty, staged, deleted, untracked and divergent
work, including equal-VERSION unpublished commits and ignored-file collisions.
New cleanup messages are translated in every supported language; catalog
completeness and format-field regressions cover them. No desktop, visual asset,
native backend, ABI or SDK behavior changed.

## Focused development and integration

Linux host, Python 3.14, Git 2.55.0; disposable Git fixtures, no live installer:

```sh
python3 -m pytest tests/test_repository_cache.py tests/test_repository_history.py tests/test_repository_maintenance.py tests/test_auto_update.py tests/test_git_process_maintenance.py tests/test_release_screenshots.py tests/test_static.py tests/test_release_update.py tests/test_multilanguage.py tests/test_localization.py -q
```

210 passed. The 173 affected updater/cache/provenance checks also passed in a
Golden Gate source prepared from the candidate with
`GOLDEN_GATE_TAHOE_SOURCE=<candidate> MAC_TAHOE_NO_UPDATE_CHECK=true python3 installer --prepare`.
Golden Gate's complete wrapper suite passed 95 tests. Collection is 2124 Tahoe
tests; collection is not a claim that every conditional native check ran locally.

A network-disabled, read-only KDE neon container with Git 2.43.0 passed the
173 updater/history/cache/maintenance/Trace2, localization and provenance checks. The synthetic history uses
successive binary asset replacements, main and dev pulls, a merge from an old
release base, repeated cleanup of hydrated promisor blobs, and historical lazy
retrieval. Fresh `--filter=blob:none` clones and legacy shallow clones also
passed the update lifecycle: verified clean legacy releases acquire ancestry
without downloading historical assets; development sources are not migrated.
Remote main/dev may advance with equal-VERSION unpublished work: cleanup of a
verified public checkout does not fetch those commits or move cached roles.
Missing older tag metadata is not lazily fetched during the read-only audit.
Tests preserve current tips, tags, private branches/tags, stashes,
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
not edited. These clones included active remote development branches at the
final measurement (2026-10-31 09:07 UTC); their available objects were preserved.
The checked-out inputs were published v0.61.17: Tahoe
`36d21558242cb4130622f4441adff49bc6b2d477` and Golden Gate `8b6b2742914d8980acf79de6944877c9cce17bea`.

| Git store | Before (allocated bytes) | After | Recovered | Public obsolete blobs | Merged cached refs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tahoe | 2075348992 | 368025600 | 82.3% | 670 | 6 |
| Golden Gate | 765485056 | 86126592 | 88.7% | 464 | 4 |

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

Reviewed Dock v0.61.18 screenshots and their original provenance are retained.
The integration preserves that release’s runtime and
[validation evidence](native/dock_alignment_validation.md) unchanged.
The console-only modules and updater functions are excluded from the visual
fingerprint; regression checks still reject visible-label/entry changes.
`release-screenshots verify` is required on both final commits. No new VM,
visual captures, host desktop changes or duplicate local distro matrix is
justified by these changes.

## Candidate executable content

The immutable v0.61.19 tag identifies the final source. These executable hashes
make the focused evidence independent of later documentation/commit metadata.

| Path | SHA-256 |
| --- | --- |
| `src/scripts/cli.py` | `3219ecf03b8efe5ace3361cab78bcbf9315779597dfbe985a618af642aa32679` |
| `src/scripts/repository_cache.py` | `b6fc1e63b904cd187eb73cdc63b0b7dd82365404bc45325ac8f91845be337711` |
| `src/scripts/repository_history.py` | `fe9c75469315b0404f12ed05268a4badd458cf29d30358e81a6606de5bc8fa1a` |
| `src/scripts/repository_maintenance.py` | `e49637a96b4fe11ef3385fbfd3d85738d5a0b10ede4613c71835020210aa8da7` |
| `src/scripts/localization.py` | `1e30f09f5e467f0e4d60c5865968893cb4514ecacf34058ebd93697bde6aed69` |
| `src/scripts/locales/pt_BR.json` | `6d1c99c55c2a04557125649262d61ce7772e1a7e9a3b0c33ea2130709aadf8b0` |
| `src/scripts/locales/de.json` | `533771b3d88ad7cbade6c50337aec53c04f2b917c99d8ee8bf21ea0ae131b854` |
| `src/scripts/release_screenshots.py` | `4afaf72f3c553fe3bb5d53b6c53bff497d064e6faafc5356eaf0711dc1228390` |
