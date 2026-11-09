# v0.61.20 clock synchronization validation

## Scope and reproduced cause

The automatic login service selected light at 15:18 before systemd-timesyncd
corrected a dual-boot RTC to 21:18. Monotonic journal entries put service start
at boot +99.058s, synchronization at +101.289s and service completion at
+102.476s. This is an ordering failure, not a six-hour theme transition.

The shared standalone theme switcher now queries enabled NTP synchronization
before selecting an automatic mode. It waits at most 30 monotonic seconds per
attempt and exits 75 without applying a theme when synchronization is pending
or cannot be verified. The systemd user service retries that status after 15s.
Explicit light/dark modes, disabled NTP and non-systemd scheduling retain their
previous behavior. No RTC, timezone or NTP configuration is changed.

Both editions use the same switcher and scheduler. No native backend, SDK,
material, palette, layout, wallpaper asset or capture input changed. The visual
fingerprint excludes only clock-readiness code and its exact retry settings;
regressions prove that mode selection, rendering, readiness exit status and
service command changes still invalidate retained screenshots.

## Focused development and prepared-edition checks

Environment: CachyOS, Linux 7.2.0-1-cachyos, glibc 2.44, system Python/pytest.
Source baseline: `a693843a32ebf90c43fb21533b16ef3946b4e56f`; source identity is the
commit containing this report, with these executable content SHA-256 values:

- `src/scripts/theme_switch.py`: `578b8ec1e91d7861faa614a9c81d728267fdd7641c0316a792ce28bfbaf601a3`
- `src/offline/mac-tahoe-liquid-kde-theme.service`: `29e74a6905dd664507d162e220023e3f19de412eeb0a34812cfd250b588e70b0`

Commands (pytest runs use isolated HOME/config and mocked desktop operations):

```sh
python3 -m pytest tests/test_clock_sync.py tests/test_theme_switch.py tests/test_session_env.py tests/test_openrc_scheduler.py tests/test_apply_safety.py tests/test_apply_portability.py -q
python3 -m pytest tests/test_clock_sync.py tests/test_release_screenshots.py -q
```

Results: 238 and 57 passed respectively; the clock tests overlap intentionally
with the independent provenance regression check. The initial sandbox run had
145 passes and one permission failure when binding an isolated Unix socket;
the unconfined isolated run above resolved that environmental restriction.

Golden Gate `python3 installer --prepare` staged the local development source
with its edition defaults. The combined seven-file selection above passed all
282 tests against the prepared source. Golden Gate's full wrapper suite passed
95 tests (`python3 -m pytest tests -q`). `git diff --check` passed.

## Release integration and coverage limits

Publication requires successful `test.yml` push runs on both `main` and `dev`
for each exact release commit, followed by the guarded release workflows.
An initial v0.61.20 CI run caught the stale README test-count badge (2124
instead of 2138); the badge was corrected before the final exact-SHA runs.
These runs supply the full shared suite and configured distro matrix; local
focused checks do not substitute for that gate. Consult the immutable release
commit's GitHub Actions runs for the final CI results.

The dual-boot clock jump and delayed/unavailable synchronization were simulated
without changing the host clock, running the live installer or applying a host
theme. An actual reboot with Windows was not performed. OpenRC/dinit retain
their existing cron path and have focused scheduler regression coverage here,
not new live distro qualification. No screenshots were recaptured: the change
only delays automatic theme selection until the existing time service is ready.
Existing reviewed image hashes, window identity checks and original provenance
remain mandatory for both editions' release validation.
