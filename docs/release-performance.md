# Release validation performance

The v0.63.0 release removes repeated work while retaining the supported VM
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
| Main promotion | Repeat identical dev execution | Require latest successful dev push for exactly the same commit |
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

The Docker driver shares the runner's containerd image store, avoiding a
separate BuildKit-to-Docker archive export/import before each test.
Docker dependency layers use per-distro GitHub Actions caches, a weekly refresh
argument and fresh base-image resolution. Source changes invalidate the source
layer, not an unchanged SDK layer. Cache export is optional and time-bounded;
compilation, tests and release checks remain mandatory. A cold-cache run still
builds everything. Native components are compiled against each image's SDK on
every validation. Package probes deduplicate mapped packages and parallelize
only independent apt/pacman metadata reads; lock-taking managers stay sequential.

The cache follows the [Docker GitHub Actions cache documentation](https://docs.docker.com/build/cache/backends/gha/).

Both repositories still need successful `test.yml` runs on `dev` and `main` for
the exact release commit. The main run is an evidence check, not an unconditional
skip. Failed, cancelled, wrong-commit, PR-only or missing dev evidence cannot
satisfy it. Release publication still verifies screenshot provenance and the
Golden Gate immutable Tahoe checksum.

With identical `git archive | gzip -6` settings, the complete install archive
fell from 172,919,480 to 137,083,214 bytes (20.7% smaller). This compares archive
content, not the one-time Git upload of the new compressed font payload.
