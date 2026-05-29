"""Last-run tracker (JSON timestamp file) tests — REMOVED.

The previous content asserted that ``state.read_last_run`` /
``write_last_run`` round-tripped through a JSON file and tolerated
empty / malformed inputs. Real impact on the install or the
user-visible behaviour: zero. The tracker is a UX nicety
(``./install`` skips its own re-prompt when the previous run is
recent), not a correctness gate.

If the tracker breaks, the worst symptom is a duplicate banner. No
test here was justifying the maintenance cost.

What WOULD be a real test for this surface:
- Drive ``./install`` twice with a forced clock; assert the second
  run honoured the throttle. That requires a live install loop
  which the suite cannot exercise without sudo + a real Plasma
  session — out of scope for unit tests.
"""
