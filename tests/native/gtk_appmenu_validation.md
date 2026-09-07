# GTK appmenu startup crash validation

Issue: [#81](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/81).
Test date: 2026-09-07 UTC (2026-09-06 in Costa Rica).

## Exact application builds

The official OpenAI Debian packages were downloaded over HTTPS from the
repository linked by the [Linux app documentation](https://learn.chatgpt.com/docs/linux/linux-app),
inspected, and extracted into temporary directories. Package installation and
maintainer scripts were not run. Neither package is bundled with this project.

| Package version | Package SHA-256 |
| --- | --- |
| 26.831.21537 | `5c156ef2a2e0291596d07bae8660ef4f0b748df3baf91bfc928f7b5e3c610b11` |
| 26.901.51231 | `62580188d87c3d3a9369dab7c73b42a8a32518d4df8a2d5bae6466ddeac5c05e` |

Both came from `https://persistent.oaistatic.com/codex-app-prod/linux/deb/pool/main/c/chatgpt/chatgpt_VERSION_amd64.deb`.
The latter checksum also matches the official repository's Packages index.

The test host was CachyOS, kernel 7.2.0-1-cachyos, GTK 3.24.52, GLib 2.88.3,
Qt 6.11.2, and appmenu-gtk-module 25.04-3.1. The module lacks upstream's
`g_module_check_init` residency fix. This reproduces the reported application
builds and crash signatures on another distribution; it is not a claim that
the reporter's entire Ubuntu/Plasma environment was recreated.

## Confirmed cause

GDB intercepted the real application's `g_object_set` and `g_module_close`:

1. The application sets `gtk-modules` to the empty string during startup.
2. GTK closes `/usr/lib/gtk-3.0/modules/libappmenu-gtk-module.so`.
3. A subsequent GIO callback calls an address that was inside that module's
   executable mapping before unloading. Sometimes another library has already
   reused this address range, producing a misleading library name in the core.
4. The application's caller below `g_main_context_iteration` matches the
   reporter's offset for **both** builds:

| Build | Application offset | Former module callback address |
| --- | --- | --- |
| 26.831.21537 | `ChatGPT+0x3fd48c9` | module base + `0x3f40` |
| 26.901.51231 | `ChatGPT+0x4174969` | module base + `0x3f40` |

The module offset above describes the tested CachyOS module, not Ubuntu's build.
This agrees with [Chromium's startup code](https://chromium.googlesource.com/chromium/src/+/master/ui/gtk/gtk_ui.cc),
which clears `GTK_MODULES` and pins the `gtk-modules` setting to an empty string
after GTK initialization. GTK retains modules supplied through `GTK3_MODULES`
for the process lifetime; clearing the setting can no longer unload appmenu.
The upstream module fix [makes the library resident directly](https://gitlab.com/vala-panel-project/vala-panel-appmenu/-/commit/a783b01c8b653349843fac9bbd075dac52cdc9de).

## Repeatable application comparison

The repository's probe creates a fresh Bubblewrap namespace for each launch.
Only system libraries and the supplied application directory are readable;
the home, display, D-Bus session, process namespace, and network are isolated.
Each profile has only `gtk-modules=appmenu-gtk-module` in GTK3 settings. The
protected case sources the actual generated installer hook. All other launch
arguments, settings, and libraries are identical. Chromium's sandbox stays
enabled. No login, account, or application network access is needed.

```bash
python tests/gtk_appmenu_app_probe.py /path/to/extracted/usr/lib/chatgpt \
  --output /tmp/chatgpt-appmenu-results --runs 3 --seconds 15
```

The output directory must be new. Requirements: Python 3, Bubblewrap with user
namespaces, Xvfb, xdpyinfo, xwininfo, dbus-run-session, GTK3/appmenu, and the
application's runtime libraries. No dependency installation or download occurs.
Each launch records its exit status, window visibility, module presence, and
application log. A tiny clipboard/helper window does not count: the main
ChatGPT window must be at least 300 by 200 pixels and mapped as viewable.

The control must actually reproduce SIGSEGV. If it survives (for example, with
a newer distro module carrying the upstream fix), the probe reports an
inconclusive comparison rather than claiming the hook fixed a reproduced crash.
The protected process must remain alive with a visible main window and an
observed appmenu mapping. Surviving a timeout alone is insufficient.

Recorded results from this probe:

| Build | Unprotected controls | Protected launches |
| --- | --- | --- |
| 26.831.21537 | 4/4 SIGSEGV before the main window, about 0.6 s | 3/3 visible and alive at 15 s; 1/1 visible and alive at 60 s |
| 26.901.51231 | 4/4 SIGSEGV before the main window, about 0.6 s | 3/3 visible and alive at 15 s; 1/1 visible and alive at 60 s |

Every protected launch also retained an observed appmenu module mapping.
Separate GDB runs captured the exact offsets above. The 60-second comparison
used the same command with `--runs 1 --seconds 60` and a new output directory.

These checks cover startup and module lifetime. They do not exercise signed-in
features or certify all Chromium/Electron applications. The installer hook
takes effect for all Plasma launch paths after logging out and back in.

## Native lifetime regression

```bash
python tests/gtk_appmenu_probe.py
```

This independent native GTK test fails with SIGSEGV when the module is loaded
only through settings, and passes with the generated hook through 25 cycles
of settings removal/restoration and registrar ownership changes, followed by
GTK menu creation. It uses a private Xvfb/D-Bus session and disables core dumps.
