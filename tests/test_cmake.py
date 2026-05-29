"""CMake configure-time tests — REMOVED.

The previous content ran ``cmake -S src/... -B build/...`` and
asserted the configure step returned 0. Useless: a successful
configure does NOT prove the produced .so lands at a path Plasma
walks (the bug in v0.8.4-v0.8.6 was exactly that: cmake configured
cleanly, compiled cleanly, but installed to ``~/.local/lib/qt6/``
which Qt6 ignored).

The real check is "did the compiled artefact end up where qmake6
reports Qt6 walks?". That now lives in:

- ``tests/test_preflight.py::test_check_paths_passes_for_production_destinations``
  (regex-validates each step's DEST_* constant against the allowed
  roots derived from qmake6 -query)
- ``tests/containers/run_in_container.py`` step_preflight_destinations()
  (runs the validation inside each per-distro container with the
  distro's real Qt6 layout).

Those two together cover what test_cmake was pretending to.
"""
