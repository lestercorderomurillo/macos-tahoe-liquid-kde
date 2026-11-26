"""Exercise Qt paths, package metadata, native builds and platform runtime tests.

The matrix installs the shipped icon themes in a disposable home, loads the built
Dock module and resolves the icons using the distro's own Qt. Debian also loads
the X11 effect. Full Plasma session lifecycle checks live under tests/vm.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

REPO = Path("/repo")
sys.path.insert(0, str(REPO / "src/scripts"))


def _collect_dep_tokens() -> list[tuple[str, str]]:
    """Walk every step module's deps() and collect the unique
    ``(cmd_token, arch_fallback)`` pairs.

    Each step lists its deps as either ``"binary"`` (binary IS the
    Arch package name), ``"binary:arch-pkg"`` (binary differs from
    the Arch package name), or an equivalent two-string tuple. We probe
    the translated package: non-Arch families require an explicit
    distro._PACKAGE_MAP row, while Arch and its descendants may use the
    declared Arch fallback.

    Sources of truth: ``cli._BASE_DEPS`` and src/scripts/steps/*.py.
    String and tuple tokens returned from deps(), plus literal direct
    ``package_for()`` calls, are picked up automatically, so a new package
    dependency gets probed without editing this file.

    Plus qmake6, which is required by the build helpers for path
    discovery even if no compiled step happens to declare it.
    """
    import importlib
    import pkgutil

    seen: dict[str, str] = {}

    def remember(cmd: str, arch_pkg: str, source: str) -> None:
        previous = seen.get(cmd)
        if previous is not None and previous != arch_pkg:
            raise RuntimeError(
                f"conflicting Arch fallbacks for {cmd!r}: "
                f"{previous!r} versus {arch_pkg!r} in {source}"
            )
        seen[cmd] = arch_pkg

    cli = importlib.import_module("cli")
    for cmd, arch_pkg in cli._BASE_DEPS:
        remember(cmd, arch_pkg, "cli._BASE_DEPS")

    steps_pkg = importlib.import_module("steps")
    for mod_info in pkgutil.iter_modules(steps_pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"steps.{mod_info.name}")

        source_path = Path(mod.__file__)
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_package_for = (
                isinstance(func, ast.Name) and func.id == "package_for"
            ) or (
                isinstance(func, ast.Attribute) and func.attr == "package_for"
            )
            if not is_package_for or not node.args:
                continue
            fallback_node = node.args[1] if len(node.args) > 1 else node.args[0]
            try:
                cmd = ast.literal_eval(node.args[0])
                arch_pkg = ast.literal_eval(fallback_node)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"{source_path.name}:{node.lineno}: direct package_for() "
                    "arguments must be literal strings"
                ) from exc
            if not isinstance(cmd, str) or not isinstance(arch_pkg, str):
                raise RuntimeError(
                    f"{source_path.name}:{node.lineno}: direct package_for() "
                    "arguments must be strings"
                )
            remember(
                cmd.strip(), arch_pkg.strip(),
                f"{source_path.name}:{node.lineno} package_for()",
            )

        deps_fn = getattr(mod, "deps", None)
        if deps_fn is None:
            continue
        tokens = list(deps_fn())
        # The wizard activates extra icon renderer and desktop widget dependencies.
        with patch.dict(os.environ, {"MTTKDE_WIZARD_OPTIONS": '{"desktop_widgets":true}'}):
            tokens.extend(deps_fn())
        for tok in tokens:
            if isinstance(tok, tuple) and len(tok) == 2:
                cmd, arch_pkg = tok
                if not isinstance(cmd, str) or not isinstance(arch_pkg, str):
                    raise ValueError(
                        f"steps.{mod_info.name}.deps() returned "
                        f"malformed tuple {tok!r}"
                    )
            elif isinstance(tok, str):
                cmd, _, arch_pkg = tok.partition(":")
                arch_pkg = arch_pkg.strip() or cmd
            else:
                raise ValueError(
                    f"steps.{mod_info.name}.deps() returned "
                    f"unsupported token {tok!r}"
                )
            cmd = cmd.strip()
            arch_pkg = arch_pkg.strip()
            if not cmd or not arch_pkg:
                raise ValueError(f"Empty dependency in steps.{mod_info.name}: {tok!r}")
            remember(cmd, arch_pkg, f"steps.{mod_info.name}.deps()")

    # qmake6 is required by path discovery independently of feature
    # selection. Route it through remember() so a compiled step cannot
    # silently declare a conflicting Arch fallback.
    remember("qmake6", "qt6-base", "Qt6 path discovery")
    return sorted(seen.items())


def _q(label: str, cmd: list[str]) -> str | None:
    print(f"  ── {label}")
    if not shutil.which(cmd[0]):
        print(f"     FAIL: {cmd[0]} not on PATH")
        return None
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"     FAIL: {' '.join(cmd)} returned {res.returncode}")
        print(f"           {res.stderr.strip()}")
        return None
    out = res.stdout.strip()
    if not Path(out).is_absolute() or not Path(out).is_dir():
        print(f"     FAIL: {label} returned an invalid directory: {out!r}")
        return None
    print(f"     {out}")
    return out


def step_qmake6_directly() -> tuple[str | None, str | None]:
    print("=== qmake6 path discovery ===")
    plugins = _q("QT_INSTALL_PLUGINS", ["qmake6", "-query", "QT_INSTALL_PLUGINS"])
    qml = _q("QT_INSTALL_QML", ["qmake6", "-query", "QT_INSTALL_QML"])
    return plugins, qml


def step_distro_layer(expected_plugins: str | None,
                      expected_qml: str | None) -> bool:
    print("\n=== distro.py layer (Qt6 paths) ===")
    import distro

    print(f"  current_distro(): {distro.current_distro()}")
    print(f"  qt6_install_hint(): {distro.qt6_install_hint()}")
    try:
        layer_plugins = str(distro.qt6_plugins_dir())
        layer_qml = str(distro.qt6_qml_dir())
        layer_lib = str(distro.system_lib_dir())
    except distro.Qt6PathsMissing as exc:
        print(f"  FAIL: Qt6PathsMissing — {exc}")
        return False

    print(f"  qt6_plugins_dir():  {layer_plugins}")
    print(f"  qt6_qml_dir():      {layer_qml}")
    print(f"  system_lib_dir():   {layer_lib}")

    ok = True
    if expected_plugins and layer_plugins != expected_plugins:
        print(f"  FAIL: qt6_plugins_dir mismatch — qmake6 said "
              f"{expected_plugins!r}, layer said {layer_plugins!r}")
        ok = False
    if expected_qml and layer_qml != expected_qml:
        print(f"  FAIL: qt6_qml_dir mismatch — qmake6 said "
              f"{expected_qml!r}, layer said {layer_qml!r}")
        ok = False
    if ok:
        print("  PASS: distro layer agrees with qmake6")
    return ok


def _probe_packages(probe: list[str], packages: list[str]) -> dict:
    # apt/pacman metadata reads are independent. Other managers may lock their
    # shared metadata cache, so keep those sequential.
    packages = list(dict.fromkeys(packages))
    workers = 4 if probe[0] in ('apt', 'pacman') else 1
    def query(package):
        return subprocess.run([*probe, package], check=False, capture_output=True,
                              text=True, timeout=120)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip(packages, pool.map(query, packages)))


def step_package_manager_layer() -> bool:
    """Tier 2: the distro layer knows how to install packages here, AND
    the common deps() tokens map to packages that exist in the distro's
    repos. Probes the repo with the distro-native ``show / info / -Si``
    command; finding a package is treated as PASS, not finding it as
    FAIL with the name we tried."""
    print("\n=== distro.py layer (package manager) ===")
    import distro

    try:
        cmd = distro.package_manager_install_cmd()
    except distro.UnsupportedDistroError as exc:
        print(f"  FAIL: {exc}")
        return False

    binary = cmd[0]
    print(f"  package_manager_install_cmd(): {' '.join(cmd)}")
    if not shutil.which(binary):
        print(f"  FAIL: {binary} is not on PATH")
        return False
    print(f"  PASS: {binary} is on PATH")

    # Probe each common deps() token. If the mapped package doesn't
    # exist in the distro's repo, the install would fail at runtime —
    # better to know now.
    probers = {
        "arch":     ["pacman", "-Si"],
        "fedora":   ["dnf", "info", "--quiet"],
        "rhel":     ["dnf", "info", "--quiet"],
        "centos":   ["dnf", "info", "--quiet"],
        "opensuse": ["zypper", "--non-interactive", "search", "--type", "package", "--provides", "--match-exact"],
        "debian":   ["apt", "show"],
        "ubuntu":   ["apt", "show"],
    }
    d = distro.current_distro()
    if d not in probers:
        for parent in distro.distro_id_like():
            if parent in probers:
                d = parent
                break
    probe = probers.get(d)
    if probe is None:
        print(f"  FAIL: no repo-probe for distro {distro.current_distro()!r}")
        return False

    ok = True
    mapped = []
    for cmd_token, arch_fallback in _collect_dep_tokens():
        try:
            pkg = distro.package_for(cmd_token, arch_fallback)
        except distro.PackageMappingError as exc:
            print(f"  ── probe {cmd_token!r}")
            print(f"     FAIL: {exc}")
            ok = False
            continue
        mapped.append((cmd_token, pkg))
    results = _probe_packages(probe, [pkg for _, pkg in mapped])
    for cmd_token, pkg in mapped:
        print(f"  ── probe {cmd_token!r} → {pkg!r}")
        res = results[pkg]
        if res.returncode == 0:
            print(f"     PASS")
            continue

        print(f"     FAIL: probe returned {res.returncode}")
        print((res.stdout + res.stderr).strip()[-600:])
        ok = False
    return ok


def step_preflight_destinations() -> bool:
    """Run the same path-allowlist regex that the real preflight uses
    against every step's known install destination. Catches a refactor
    that adds a new .so without listing it in _enumerate_destinations,
    AND proves that on THIS distro all the destinations sit in
    allowed roots (Qt6 plugin dir + Qt6 QML dir + $HOME-relative)."""
    print("\n=== preflight: destination paths ===")
    import preflight
    ok = True
    for label, path in preflight._enumerate_destinations():
        reason = preflight._validate_path(path)
        if reason is None:
            print(f"  PASS: {label} → {path}")
        else:
            print(f"  FAIL: {label} → {path}  ({reason})")
            ok = False
    return ok


_CMAKE_COMPONENTS = (
    # (label, source path under repo)
    ("menu-style", "src/offline/menu-style"),
    ("clipboard", "src/offline/clipboard/clipd"),
    ("dock-taskmanager",
     "src/offline/plasmoids/org.kde.mac.tahoe.liquid.taskmanager"),
    ("globalmenu",
     "src/offline/plasmoids/org.kde.mac.tahoe.liquid.globalmenu"),
    ("acrylic-glass",
     "src/offline/kwin-effects/acrylic-glass"),
)

# Components that must be *compiled*, not just configured. The
# acrylic-glass effect links KWin's private effect ABI, which is not
# stable across Plasma feature releases — a configure pass cannot catch
# a removed header (wayland/blur.h) or a changed virtual signature
# (prePaint* losing presentTime in 6.7). Compiling it here turns each
# distro container into a real per-Plasma-version build gate, so the
# matrix flags a 6.6→6.7-style break before a user hits it. The
# plasmoids also use Plasma APIs that can change between feature releases.
_COMPILE_COMPONENTS = frozenset(label for label, _ in _CMAKE_COMPONENTS)


def _compile_component(label: str, build: Path) -> bool:
    """``make`` an already-configured component and surface compiler
    errors. Returns True on a clean build. Used for KWin-ABI components
    where configure success does not imply the source still matches the
    installed Plasma's private headers."""
    nproc = os.cpu_count() or 1
    print(f"     compiling ({label}: make -j{nproc}) …")
    res = subprocess.run(
        ["make", "-C", str(build), f"-j{nproc}"],
        check=False, capture_output=True, text=True, cwd=str(REPO),
    )
    if res.returncode == 0:
        print(f"     PASS (configure + compile)")
        return True
    tail = (res.stdout or "") + (res.stderr or "")
    # Echo the compiler error lines (and the 'fatal error: ... No such
    # file' for a removed header) so the matrix names the exact ABI break
    # — the whole point of compiling here.
    for line in tail.splitlines():
        if (
            "error:" in line
            or "fatal error" in line
            or line.startswith("make")
            and "Error" in line
        ):
            print(f"     {line}")
    print(f"     FAIL: compile exited {res.returncode}")
    return False


def step_cmake_configure() -> bool:
    """Run cmake configure for every compiled component. Each component
    is configured with no hints — the only thing keeping this honest is
    that the Dockerfile installed exactly what ``deps()`` asks for. If
    the configure fails because a KF6 / Plasma / KWin component is
    missing, the corresponding ``deps()`` token is missing from the
    step module — that's a real regression, not a flake."""
    print("\n=== cmake configure (deps() coverage check) ===")
    ok_all = True
    for label, relpath in _CMAKE_COMPONENTS:
        src = REPO / relpath
        if not (src / "CMakeLists.txt").is_file():
            print(f"  FAIL: {label} — no CMakeLists.txt at {src}")
            ok_all = False
            continue
        build = REPO / "build" / "container-cmake" / label
        if build.is_dir():
            shutil.rmtree(build, ignore_errors=True)
        build.mkdir(parents=True, exist_ok=True)
        print(f"  ── {label}: cmake -S {src} -B {build}")
        res = subprocess.run(
            ["cmake", "-S", str(src), "-B", str(build)],
            check=False, capture_output=True, text=True, cwd=str(REPO),
        )
        if res.returncode == 0:
            if label in _COMPILE_COMPONENTS:
                # KWin-ABI component: configure isn't enough — compile it
                # so a removed header / changed virtual signature on this
                # distro's Plasma version actually fails the matrix.
                if not _compile_component(label, build):
                    ok_all = False
                continue
            print(f"     PASS")
            continue
        ok_all = False
        tail = (res.stdout or "") + (res.stderr or "")
        # Surface the cmake error lines plus enough context to name
        # the missing package. CMake's "CMake Error at <file>:<line>
        # (find_package):" lines are followed by the actual package
        # name 2-4 lines later, often as a verbatim find_package
        # argument inside a Config.cmake's find_dependency() call.
        # Without that follow-up, the operator only sees the
        # CMakeFindDependencyMacro line and has no idea which dep is
        # missing.
        lines = tail.splitlines()
        in_error = False
        error_lines_left = 0
        for line in lines:
            is_error_start = (
                line.startswith("CMake Error")
                or "Could NOT find" in line
                or "missing:" in line
                or "FATAL_ERROR" in line
            )
            if is_error_start:
                in_error = True
                error_lines_left = 8
                print(f"     {line}")
                continue
            if in_error:
                if error_lines_left > 0 and line.strip():
                    print(f"     {line}")
                    error_lines_left -= 1
                elif not line.strip():
                    # Blank line — end of this error block.
                    in_error = False
                    error_lines_left = 0
        print(f"     FAIL: cmake configure exited {res.returncode}")
    return ok_all


def step_bundled_kvantum_build() -> bool:
    """Compile the offline Qt 6 engine where no distro engine is present."""
    print("\n=== bundled Kvantum Qt 6 fallback ===")
    from steps import kvantum

    if not kvantum._bundled_engine_required():
        print("  SKIP: distro-owned Qt 6 engine/package path")
        return True
    kvantum.build()
    missing = [path for path in kvantum.build_artifacts() if not path.is_file()]
    if missing:
        for path in missing:
            print(f"  FAIL: missing build artefact {path}")
        return False

    if not kvantum._install_bundled_engine():
        print("  FAIL: bundled engine install returned false")
        return False
    destination = kvantum._engine_destination()
    installed = (destination, kvantum.ENGINE_MARKER, kvantum.ENGINE_LICENSE)
    missing = [path for path in installed if not path.is_file()]
    if missing:
        for path in missing:
            print(f"  FAIL: missing installed file {path}")
        return False

    linkage = subprocess.run(
        ["ldd", str(destination)], check=False, capture_output=True, text=True,
    )
    if linkage.returncode != 0 or "not found" in linkage.stdout:
        print("  FAIL: installed Kvantum plugin has unresolved libraries")
        print(linkage.stdout)
        return False

    return True


def remove_test_engine():
    from steps import kvantum

    outputs = (kvantum._engine_destination(), kvantum.ENGINE_MARKER, kvantum.ENGINE_LICENSE)
    kvantum._remove_bundled_engine()
    leftovers = [str(path) for path in outputs if path.exists()]
    if leftovers:
        raise RuntimeError("Kvantum uninstall leftovers: " + ", ".join(leftovers))


PLATFORM_TESTS = (
    "tests/test_distro_packages.py",
    "tests/test_preflight.py",
    "tests/test_session_env.py",
    "tests/test_glass_presets.py",
    "tests/test_popup_rendering.py",
    "tests/test_taskmanager_qml.py",
    "tests/test_globalmenu_model.py",
    "tests/test_reserved_menu_icons.py",
    "tests/test_status_icons.py",
    "tests/test_acrylic_glass_x11_smoke.py",
)


def step_pytest() -> bool:
    print("\n=== pytest ===")
    import distro

    tests = list(PLATFORM_TESTS)
    if not os.environ.get("MTTKDE_X11_PLUGIN") and distro.current_distro() != "debian":
        tests.remove("tests/test_acrylic_glass_x11_smoke.py")
        print("X11 module load is covered by the Debian X11 SDK leg.", flush=True)
    with tempfile.TemporaryDirectory() as temp:
        report = Path(temp) / "results.xml"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *tests, "-q", "-rs", "--durations=10", "-x",
             f"--junitxml={report}"], cwd=REPO,
            env=os.environ | {"MTTKDE_REQUIRE_NATIVE_GLOBALMENU": "1"},
        )
        if result.returncode:
            return False
        cases = ET.parse(report).findall(".//testcase")
        skipped = [case for case in cases if case.find("skipped") is not None]
        for case in skipped:
            print(f"Missing platform coverage: {case.get('classname')}.{case.get('name')}")
        return bool(cases) and not skipped


def main() -> int:
    try:
        from PIL import Image  # noqa: F401 — required by icon rendering tests
    except ImportError as exc:
        print(f"FAIL: Pillow is required by the test suite: {exc}")
        return 1
    for command in ("git", "rsvg-convert"):
        if not shutil.which(command):
            print(f"FAIL: {command} is required by the test suite")
            return 1
    target = os.environ.get("MTTKDE_EXPECT_DISTRO")
    if target:
        import distro
        expected = {"arch-kdeunstable": "arch", "opensuse": "opensuse-tumbleweed"}.get(target, target)
        if distro.current_distro() != expected:
            print(f"FAIL: {target} expected ID={expected}, found {distro.current_distro()}")
            return 1
    plugins, qml = step_qmake6_directly()
    layer_ok = step_distro_layer(plugins, qml)
    pkg_ok = step_package_manager_layer()
    preflight_ok = step_preflight_destinations()
    cmake_ok = step_cmake_configure()
    from steps import kvantum
    install_engine = kvantum._bundled_engine_required()
    try:
        kvantum_ok = step_bundled_kvantum_build()
        dock_build = REPO / "build/container-cmake/dock-taskmanager"
        dock_plugin, = dock_build.rglob("org.kde.mac.tahoe.liquid.taskmanager.so")
        icons_ok = subprocess.run([
            sys.executable, str(REPO / "tests/containers/installed_icons.py"), "--dock-plugin", str(dock_plugin), "--materials",
        ], check=False).returncode == 0
        tests_ok = step_pytest()
    finally:
        if install_engine and kvantum.ENGINE_MARKER.is_file():
            remove_test_engine()

    print("\n=== summary ===")
    print(f"  qmake6 plugins:     {plugins or '(missing)'}")
    print(f"  qmake6 qml:         {qml or '(missing)'}")
    print(f"  Qt6 layer:          {'PASS' if layer_ok else 'FAIL'}")
    print(f"  Package mgr layer:  {'PASS' if pkg_ok else 'FAIL'}")
    print(f"  Preflight paths:    {'PASS' if preflight_ok else 'FAIL'}")
    print(f"  CMake cfg+compile:  {'PASS' if cmake_ok else 'FAIL'}")
    print(f"  Kvantum Qt6 build:  {'PASS' if kvantum_ok else 'FAIL'}")
    print(f"  Installed icons:    {'PASS' if icons_ok else 'FAIL'}")
    print(f"  Pytest suite:       {'PASS' if tests_ok else 'FAIL'}")

    if plugins is None or qml is None:
        print("  → qmake6 not available — install the Qt6 base development package")
        return 1
    if not all((
        layer_ok, pkg_ok, preflight_ok, cmake_ok, kvantum_ok, icons_ok, tests_ok,
    )):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
