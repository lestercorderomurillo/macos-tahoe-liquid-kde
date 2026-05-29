"""Apply step DBus / subprocess safety tests — REMOVED.

The previous content monkeypatched every external command the
apply step shells out to, then asserted the install path called
them in a specific order with specific arguments. Two problems:

1. Pinning call-order via monkeypatch tests the test's mental
   model of the apply step, not the apply step itself. A
   refactor that swaps to a single combined DBus call is
   *better* code but fails the test.
2. None of these calls actually reached a DBus broker. A green
   run did not prove plasmashell received KWin.reconfigure;
   it proved the test's mock saw the call.

Real coverage for the apply step:
- ``tests/test_preflight.py::test_dbus_session_passes_with_address_env``
  — DBus address resolution probed against the live env.
- A maintainer running ``sudo ./install`` on a live Plasma 6
  session and watching the theme actually change. No unit test
  substitutes for that.
"""
