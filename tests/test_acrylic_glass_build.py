"""Acrylic Glass cmake build test — REMOVED.

Same shape of false signal as test_cmake: a successful build of the
KWin effect does not prove KWin loads it. The destination-path
preflight (tests/test_preflight.py) catches the path-mismatch class
of bug. A real "the effect loads in KWin" assertion needs a live
KWin instance, which the suite cannot provide.
"""
