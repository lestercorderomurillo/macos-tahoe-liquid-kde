# Appearance synchronization

KDE can change its palette without reloading Kvantum's SVG material or GTK's
installed theme. The old installer also removed the background follower, and
the timer's `auto` command could override a later manual choice. A correct
`kdeglobals` file therefore did not establish that open applications matched it.

The session follower now observes KDE color/global themes (including the
look-and-feel defaults that KConfig omits from personal files), Plasma style,
Kvantum and GTK settings. It serializes application with the standalone switcher,
records its own changes, and cancels stale work when a newer native selection
arrives. Manual choices replace the project's automatic preference. Native KDE
automatic appearance retains KDE's scheduler; the project `auto` policy uses
06:00 and 18:00. Both update the same effective appearance across components.

The follower is started after installation activation and through a KDE session
autostart on systemd, OpenRC and dinit. Home Manager uses a session service.
`mac-tahoe-theme-switch light`, `dark` and `auto` remain the user commands.
`follow-system` explicitly reconciles the current desktop mode. Internal
`scheduled` and `session` invocations preserve an existing manual preference.

## Qualification scope

The change affects the shared Python switcher, its installer lifecycle, scheduler
entry points and Home Manager integration. Both editions use this implementation;
Golden Gate staging changes material/default inputs. No shader or KWin ABI is
changed. Unit checks cover state selection, cancellation, own-write feedback,
failed application, clock readiness, lifecycle and scheduler compatibility.
Live qualification must additionally cover native KDE/GTK selections, rapid
sequences, actual automatic boundaries and live Qt/Kvantum/GTK rendering in both
editions. Installation and reinstallation run only in a disposable Plasma VM.

The initial host inspection was read-only: KDE and Kvantum both named their dark
variants, supporting investigation of stale running state rather than assuming
that the saved configuration was light. The qualification VM uses KDE neon,
Plasma 6.8.1 and Qt 6.11.1 on Wayland. The user's host is CachyOS, Plasma 6.7.4
and Qt 6.11.2; the VM does not establish identical distribution or physical GPU
coverage. Current qualification commands and results belong in release evidence.

The VM also checks preserved native-auto selection and customized blur,
refraction, gradient opacity and popup radius while the probe process identities
remain unchanged. The regular Task Manager is added beside the icons-only Dock
for a focused visual check; it is not represented as covered by the loose QML
probe, because the compiled applet resolves its own resource module. Both
launcher presets are checked with each edition's installed material.

The public gallery is unchanged. Private qualification frames and raw logs stay
in the maintainer's ignored build directory; release evidence records their
hashes and the installed source identities. No host appearance was changed.
