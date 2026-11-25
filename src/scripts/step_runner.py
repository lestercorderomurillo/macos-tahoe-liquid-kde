"""Run a feature step. Each step is a Python module under ``src/scripts/steps``."""

from localization import tr

import importlib
from types import ModuleType

from log import errors, fail, warnings
from state import record_component
from utils import check_cancelled


PHASES = ("deps", "download", "build", "install", "uninstall", "restart_plasma")


def step_module(feature: str) -> ModuleType | None:
    name = feature.replace("-", "_")
    try:
        return importlib.import_module(f"steps.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"steps.{name}":
            return None
        raise


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
    record_component(feature, phase, "running")
    before = len(errors)
    warning_count = len(warnings)
    try:
        module = step_module(feature)
        operation = getattr(module, phase, None)
        if not callable(operation):
            raise AttributeError(f"steps.{feature}.{phase}")
        result = operation()
        if (result is False or (type(result) is int and result != 0)) and len(errors) == before:
            fail(f"{feature}.{phase}: {result}")
        check_cancelled()
    except KeyboardInterrupt:
        record_component(feature, phase, "aborted", 130)
        raise
    except Exception as exc:
        fail(tr('{feature}: {phase} raised {value3}: {exc}', feature=feature, phase=phase, value3=type(exc).__name__, exc=exc))
    failed = len(errors) > before
    messages = warnings[warning_count:] + errors[before:]
    status = "failed" if failed else "warning" if messages else "completed"
    record_component(feature, phase, status, int(failed), messages)
    return not failed
