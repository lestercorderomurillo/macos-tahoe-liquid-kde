"""Step helper unit tests — REMOVED.

Single test that probed a helper in isolation. The helper is now
called from the real install path inside the container matrix
(tests/containers/run_in_container.py), which is a stronger
assertion than calling it directly with mocked args.
"""
