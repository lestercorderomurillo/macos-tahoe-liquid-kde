"""Run a feature step. Each step is a Python module under ``src/scripts/steps``."""

import importlib
from types import ModuleType

from log import errors
from utils import check_cancelled


PHASES = ("deps", "download", "build", "install", "uninstall", "restart_plasma")


def step_module(feature: str) -> ModuleType | None:
    name = feature.replace("-", "_")
    try:
        return importlib.import_module(f"steps.{name}")
    except ModuleNotFoundError:
        return None


def step_exists(feature: str) -> bool:
    return step_module(feature) is not None


def step_has_phase(feature: str, phase: str) -> bool:
    mod = step_module(feature)
    return mod is not None and callable(getattr(mod, phase, None))


def step_deps(feature: str) -> list[tuple[str, str]]:
    mod = step_module(feature)
    if mod is None or not callable(getattr(mod, "deps", None)):
        return []
    out: list[tuple[str, str]] = []
    for entry in mod.deps():
        if isinstance(entry, tuple):
            out.append(entry)
        else:
            cmd, _, pkg = str(entry).partition(":")
            out.append((cmd, pkg or cmd))
    return out


def run_phase(feature: str, phase: str) -> bool:
    check_cancelled()
    mod = step_module(feature)
    if mod is None or not callable(getattr(mod, phase, None)):
        return True
    before = len(errors)
    try:
        getattr(mod, phase)()
    except Exception as exc:
        from log import fail
        fail(f"{feature}: {phase} raised {type(exc).__name__}: {exc}")
        return False
    check_cancelled()
    return len(errors) == before
