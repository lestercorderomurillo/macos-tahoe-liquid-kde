"""Legacy cache JSON compat tests — REMOVED.

The previous content pinned the shape of a deprecated cache file
that v0.17+ no longer reads. No production code path consults that
format any more; the tests were exercising dead code in the test
module that imported it.

The wallpapers offline-bundling change (v0.17.0) removed the
download cache entirely. Any "compat" with the old format is now
moot — there is nothing to be compatible with.
"""
