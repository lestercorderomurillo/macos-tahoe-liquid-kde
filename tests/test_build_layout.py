"""Build-layout file-existence tests — REMOVED.

The previous content walked src/offline/ and asserted that named
files existed (cursors, fonts, plasma themes, etc.). All it caught
was someone deleting a file by accident. The real failure mode
when an asset is missing is one specific feature breaking on
install — the install step itself fail-fasts with a clear message
("Wallpapers source not found at …"), so the file-existence check
duplicates that bail without adding signal.

The plasmoid ID-vs-directory-name check survived because that one
caught a real shipped bug (v0.9.0 globalmenu); it now lives in
tests/test_preflight.py::test_plasmoid_id_consistency_across_repo.
"""
