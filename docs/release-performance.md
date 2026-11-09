# Release validation performance

The v0.66.3 release removes repeated work while retaining the supported VM
qualification workflows and all eleven container targets, including the staging
KWin SDK. A version/CI-only release reuses reviewed captures with their original
provenance; changes to visible output still require the affected views.

## Reference measurement

The final successful v0.63rc2 validation used commit
`42355cce248b6704c8d1d52c71ad66ffc38c4ee1`:

- [main](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/42363170316)
- [dev](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/42363170526)

From the first job start to the last job completion: **886 seconds** (14m 46s).
Summed job execution: **12,546 seconds** (209m 06s). The target is at most
**443 seconds** elapsed on a comparable successful candidate, with cold and warm
cache conditions reported separately. These figures exclude developer edits,
failed candidates and screenshot creation; they are not whole-release timings.

## Coverage allocation

| Layer | Before | Now |
| --- | --- | --- |
| General tests | Full suite in primary and every distro, on both branches | Full suite once per commit, two disjoint file shards |
| Distro compatibility | Dependency probes, native builds and repeated full suite | All package mappings, paths, native builds, platform/native rendering tests |
| Main promotion | Repeat identical dev execution | Promote the same commit without another job or polling gate |
| Pull requests | Independent checks | Independent checks retained |
| VM qualification | Disposable distro desktops | Retained; run affected scenarios when desktop behavior changes |
| Screenshot evidence | Reviewed capture provenance | Retained; reuse unchanged views without rewriting capture versions |
| README test count | Manual number, recursive collection test | Actual CI status badge |

The container selection retains distro packages, preflight/session restoration,
KCM/material controls, GTK/Qt popup rendering, Dock QML geometry, icon rendering
and the native X11 load test where that SDK is provided. Pure business logic,
source invariants, updater scenarios and documentation validation still run in
the general suite. Passing history alone is not a reason to delete a regression.

## Transfers and dependency freshness

Container build contexts omit the 176 MiB documentation gallery. Installation
archives already exclude that gallery through `.gitattributes`; compressing PNGs
inside another archive would not address duplicate uploads or repeated tests.
Fonts are bundled in a deterministic `tar.xz` payload: 111,841,008 bytes
become 39,096,872 bytes (65% smaller). Installation verifies every filename,
size and SHA-256 before writing. The wizard preview font remains directly
available. Installed font bytes and filenames are unchanged; identical fonts
keep their inodes and skip font-cache rebuilding. Icons and cursors already
use compressed archives; JPEG wallpapers are not recompressed.

Screenshot reuse compares decoded font bytes. Only the exact reviewed
packaging implementations are treated as visually equivalent; future code
edits or changed font bytes invalidate that equivalence.

SDK images use the runner's direct Docker build path with `--pull`. They are
not uploaded to Actions cache: their multi-gigabyte layers exceeded cache
capacity and evicted useful compiler entries. Dependencies are resolved fresh
on each validation. The neon SDK uses the same Ubuntu LTS base, pinned archive
key and signed User Edition repositories as KDE's official Docker recipe,
installing the official settings and upgrading base packages as in that recipe,
then asserting its real neon distribution identity. It omits the
full desktop image and explicitly installs the headless rendering prerequisites.
The full neon desktop VM qualification workflow is unchanged. Only the small compiler caches persist between runs.
Package probes deduplicate mapped packages and parallelize independent
apt/pacman metadata reads; lock-taking managers stay sequential.

Both repositories still need successful `test.yml` runs on `dev` and `main` for
the exact release commit. The main run is an evidence check, not an unconditional
skip. Failed, cancelled, wrong-commit, PR-only or missing dev evidence cannot
satisfy it. Release publication still verifies screenshot provenance and the
Golden Gate immutable Tahoe checksum.

With identical `git archive | gzip -6` settings, the complete install archive
fell from 172,919,480 to 137,082,341 bytes (20.7% smaller). This compares archive
content, not the one-time Git upload of the new compressed font payload.

## Compilation reuse and measured scheduling

CMake uses ccache in CI, with separate per-distro stores. Compiler bytes, flags
and preprocessed header content participate in cache keys; direct mode is
disabled, and no relaxed correctness options are enabled. SDK and native runtime
checks still execute. The general suite is split using recorded JUnit file
durations in `.github/test-durations.json`, preserving one shard per file so
module-scoped native fixtures are not rebuilt in multiple workers.

The published runtime candidate improved elapsed validation to 526 seconds,
but did not meet the 443-second target. The final workflow removes SDK cache
uploads, preserves compiler caches, and balances test shards using measured
file durations. Its result is recorded separately with the final CI links.

The font payload and installer are the published v0.63.0 bytes. Subsequent CI-only
optimizations do not rewrite that release tag or change the installed desktop.

Publication invokes the mandatory provenance check inside `publish` once,
instead of calling `verify` immediately before the same check runs again.
The exact-commit gate polls every ten seconds while retaining its sixty-minute
limit and refusal of failed, skipped or mismatched runs.

## Current focused optimization

SDK Docker layers are reused within each distro's weekly cache scope, with
base-image pulls retained. Compiler caches use standard direct lookup, compiler
content checks and 1 GiB per shard/distro; no unsafe sloppiness is enabled. The
installer uses ccache when installed, preserving explicit environment and
cached launcher choices. Source changes with restored old timestamps still
invalidate the build graph, while unchanged builds retain their object files.

Launcher categories retain their already-resolved app models. Multiple model
notifications in one event-loop turn share one selection update. The Loader
keeps its declarative binding without a duplicate assignment handler. No visual
layout or search debounce changes are introduced.

Removed tests only inspected workflow text, enumerated required test filenames,
or repeated a Plasma property check now exercised by the native launcher probe.
The disjoint-shard behavioral test remains because it detects missing/doubled
coverage. Compiler tests execute a binary after edits with old timestamps and
exercise absent, automatic and explicitly selected compiler launchers.

The offline agent graph lives in Golden Gate's `tools/repo_graph.py` and accepts
`--repo` for Tahoe. It emits shortest caller chains first and bounded output.
It is an inferred navigation index, not a promise of exhaustive test selection.
No remote runtime speedup is claimed until a comparable warm-cache run exists.
