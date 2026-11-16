# CI/CD performance

Measured on 2026-11-16 using GitHub-hosted Ubuntu runners. Durations below
measure job execution, including setup and cache transfers; queue time is
excluded. Full-CI duration spans the first job start to the last job finish.
A single sample is evidence for that run, not a guaranteed service level.

| Operation | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| Tahoe release publication | 43 s | 11 s | 74.4% |
| Golden Gate release publication | 62 s | 25 s | 59.7% |
| Full CI, first v0.72.9 execution | 515 s | 407 s | 21.0% |
| Full CI, cache-ready same commit | 515 s | 250 s | 51.5% |

The release jobs and the cache-ready full matrix exceed the requested 50%
reduction. The cache-ready benchmark reran the exact released commit
`794b9f4fce23380747f2d331c28cc825732a2211` after its initial matrix finished;
all 16 jobs passed, with no omitted distro or test partition. The first full-CI run
for the new version does **not** meet that target: Nix rebuilds versioned
packages, and SDK transfers vary. Cache-ready results are reported separately;
they must not be presented as the first execution of a new release.

## Sources

- [Cache-ready benchmark, same v0.72.9 commit](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43896093436): 250 seconds, all jobs passed.

- [Baseline full CI, v0.72.6](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43887347286).
- [Final v0.72.9 full CI](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43894824738): all 16 jobs passed.
- [Tahoe baseline publication](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43887347238) and [v0.72.9 publication](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43894823690).
- [Golden Gate baseline publication](https://github.com/lestercorderomurillo/macos-golden-gate-liquid-kde/actions/runs/43887549715) and [v0.72.9 publication](https://github.com/lestercorderomurillo/macos-golden-gate-liquid-kde/actions/runs/43895780681).
- [Golden Gate v0.72.9 checks](https://github.com/lestercorderomurillo/macos-golden-gate-liquid-kde/actions/runs/43894917889): passed.

## Preserved coverage

The primary suite changed from two disjoint partitions to four. JUnit totals
increased from 2,558 to 2,564 cases, with zero failures or errors and the same
six skipped cases. All eleven distro legs remain enabled, as do the Nix
module/package checks, dependency mapping and native component builds.

Weekly source-free SDK images avoid repeating dependency installation.
Compiler caches retain content checks. Missing caches rebuild normally; an
optional registry upload failure cannot suppress the tests. Nix reuses its
content-addressed store. Release validation retains immutable pins, archive
checksums, source fingerprints and existing gallery provenance. Main promotion
does not repeat dev's matrix; Markdown-only changes do not launch runtime CI.

These are CI and publication measurements, not new live-Plasma VM evidence.
The installed desktop implementation was unchanged by this optimization.
