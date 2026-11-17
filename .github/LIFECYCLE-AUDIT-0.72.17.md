# Lifecycle audit and v0.72.17 qualification

The audit found and fixed three reproducible uninstall defects and one release-checker defect. Shared code remains in Tahoe; Golden Gate stages the same implementation with its edition defaults.

## Project overview and review scope

Golden Gate handles source discovery, verified release downloads and isolated content-addressed staging. Tahoe owns the native wizard, serialized elevated backend, component installation recipes, desktop services and assets. Component fingerprints determine payload reuse; session services and shortcuts require separate lifecycle cleanup.

Reviewed the recent PR descriptions and available review threads in both repositories, current lifecycle implementations and caller graph, and existing CI. There were no open PRs. Relevant merged work includes [clipboard #123](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/pull/123), [window button placement #125](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/pull/125), [appearance synchronization #126](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/pull/126), and Golden Gate's paired staging/maintenance changes. The button-layout preservation context is already present in current uninstall code. The previous implementation's [CI passed](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43977972674).

Open appearance reports #130 and #133 were inspected. Their design changes and new-feature requests are outside these nonvisual fixes. This is a bounded lifecycle review, not an exhaustive audit of every native plugin or PR diff.

## Confirmed defects

- GTK uninstall deleted custom `gtk.css`, dark stylesheets, KDE-generated CSS and unrelated/edited files in `assets` and `windows-assets`. Cleanup now compares files with installed project sources before removing those sources. It recognizes generated adaptive sheets and copied bundled aliases, preserves foreign symlinks, and removes only unchanged project copies. Unknown files survive; an absent reference is not proof of ownership.
- Clipboard uninstall crashed on syntactically valid but incorrectly shaped saved JSON such as `null`, `[]` or `{"keys":42}`. Validate the saved key list before considering shortcut restoration; invalid records no longer block daemon/payload cleanup.
- Clipboard history deletion suppressed permission/I/O errors and reported success while private history remained. Errors now reach the installer, and a subsequent removal can discover and delete the remaining history.

- Release validation rejected annotated tags when Actions represented them locally as lightweight tags. Fetch the remote object into `FETCH_HEAD` and verify its peeled commit against `HEAD`, without overwriting local tags. The failed [v0.72.16 workflow](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/runs/43987031019) published nothing; its immutable tag is retained. Both editions deliver as v0.72.17.

## Focused evidence

Before changes, five GTK cases and five clipboard cases failed against the original implementation. The disposable VM independently reproduced deletion of seeded custom files, the invalid-state exception and false success with a kernel-enforced nonwritable history directory.

Passing checks on the final affected code:

- `python3 -m pytest tests/test_release_evidence.py -q --tb=short`: 11 passed. The new real-Git annotated-tag case reproduced the exact failure before the fix; lightweight tags, shallow gallery fetching and wrong remote commit rejection also pass.

- `python3 -m pytest tests/test_gtk_uninstall.py -q --tb=short`: 8 passed, including bundled aliases, copied/adaptive stylesheets, edited files, foreign links and repeated cleanup.
- `python3 -m pytest tests/test_clipboard_step.py -q --tb=short`: 22 passed, including invalid saved state and deletion failure/retry, plus existing shortcut and daemon lifecycle cases.
- GTK upgrade and directly affected install/reinstall caller tests: 6 passed. Passing install-path evidence was reused because subsequent changes only affected cleanup.
- Golden Gate prepared-source GTK/clipboard regressions: 30 passed. Its unchanged wrapper suite: 102 passed.
- `python3 src/scripts/component_manifest.py` and paired `git diff --check`: passed. Only GTK, clipboard and their recipes changed in the component ledger.
- `tests/vm/uninstall_safety.py --output <guest-output>`: real selected backend install and reinstall for GTK + clipboard in both edition defaults, then component uninstall. Each preserved custom CSS/artwork and removed 129 unchanged GTK assets. Actual running clipboard daemon cleanup, corrupt-state handling, permission failure and successful retry passed.
- A held system installer lock rejected a concurrent uninstall backend with exit code 2 before mutation. A probe attempted during actual installation was also refused; it was subsequently run with a controlled holder to verify the backend's response explicitly.

The guest was a new disposable overlay of the locally available KDE neon reference snapshot, Plasma 6.8.1 / Qt 6.11.1 Wayland. Host desktop settings were never changed. Exact affected source hashes, commands and guest results are in [machine-readable evidence](LIFECYCLE-AUDIT-0.72.17.json); local command logs remain under `build/lifecycle-audit-gtk/` and are not tracked.

## Coverage limits

The VM installs/reinstalls only the changed components with `--no-apply-theme`, then executes their real uninstall recipes. It does not qualify a complete desktop teardown, reboot, X11, automatic appearance boundaries, other SDK branches or physical GPUs. No rendering implementation changed, and no new photographs were needed. Existing photographs keep their original provenance. Unknown/custom GTK files are intentionally retained, including when an installed reference has already been lost. The full remote CI matrix remains enabled and asynchronous; submission is not a passing result.
