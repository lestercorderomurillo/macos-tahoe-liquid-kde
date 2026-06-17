import os
import sys

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Apple Computer 1977-1998 rainbow logo (top → bottom): green, yellow,
# orange, red, purple, blue. We use 256-color codes for orange and
# purple since the basic ANSI palette has no orange or purple.
_APPLE_RAINBOW = (
    "\033[38;5;46m",   # green (leaf)
    "\033[38;5;226m",  # yellow
    "\033[38;5;208m",  # orange
    "\033[38;5;196m",  # red
    "\033[38;5;165m",  # purple / magenta
    "\033[38;5;33m",   # blue
)

_step_counter = 0
errors: list[str] = []

# ── Progress file ───────────────────────────────────────────────────────
# The installer UI does NOT parse our stdout (that path is fragile across
# the pkexec / sudo privilege boundary and deadlocks on the confirm
# prompt). Instead every ``step()`` appends its title to a fixed,
# world-readable file; the UI launches the install in the background and
# just watches this file for changes to drive its progress bar.
#
# Format (tab-separated, one record per line):
#   <n>\t<title>          one per step, n is the running step counter
#   __DONE__\t<exitcode>  written once when the run finishes
#
# A fixed /tmp path is used deliberately: the installer writes it (as the
# invoking user, after cli.py drops euid) and the UI reads it, so it has to
# live somewhere both sides can reach regardless of $HOME / $XDG_RUNTIME_DIR
# differences between the root-launched process and the user's session.
PROGRESS_FILE = os.environ.get(
    "MTTKDE_PROGRESS_FILE", "/tmp/mttkde-install-progress")
DONE_MARKER = "__DONE__"


def _progress_write(record: str) -> None:
    """Best-effort append to the progress file. Never raises — a progress
    hiccup must not abort an install."""
    try:
        with open(PROGRESS_FILE, "a", encoding="utf-8") as fh:
            fh.write(record + "\n")
            fh.flush()
    except OSError:
        pass


def progress_reset() -> None:
    """Truncate the progress file at the start of a run and make it
    world-readable so the user-side UI can watch it."""
    global _step_counter
    _step_counter = 0
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as fh:
            fh.write("")
        os.chmod(PROGRESS_FILE, 0o644)
    except OSError:
        pass


def progress_done(exit_code: int) -> None:
    """Write the terminal marker so the UI knows to flip to success/error."""
    _progress_write(f"{DONE_MARKER}\t{int(exit_code)}")


# True when the most recent log.py emission ended with a blank line.
# ``info()`` consults this so it can skip its leading blank when
# ``note()`` (or another helper) just printed one — otherwise steps
# without per-item ``ok()`` lines stack two blanks between the
# step description and the summary count.
_last_ended_blank = False


def step(title: str) -> None:
    global _step_counter, _last_ended_blank
    _step_counter += 1
    if not _last_ended_blank:
        print()
    print(f"{GREEN}{BOLD}  Step {_step_counter}: {title}{RESET}")
    _last_ended_blank = False
    # Mirror the step title into the progress file the UI watches.
    _progress_write(f"{_step_counter}\t{title}")


def note(msg: str) -> None:
    global _last_ended_blank
    if msg:
        print(f"  {msg}")
    print()
    _last_ended_blank = True


def info(msg: str) -> None:
    global _last_ended_blank
    if not _last_ended_blank:
        print()
    print(f"  {BOLD}{msg}{RESET}")
    _last_ended_blank = False


def ok(msg: str) -> None:
    global _last_ended_blank
    print(f"  {GREEN}✓{RESET}  {msg}")
    _last_ended_blank = False


def reinstall(msg: str) -> None:
    global _last_ended_blank
    print(f"  {GREEN}↺{RESET}  {msg} (reinstalled)")
    _last_ended_blank = False


def warn(msg: str) -> None:
    global _last_ended_blank
    print(f"  {YELLOW}⚠{RESET}  {msg}")
    _last_ended_blank = False


def fail(msg: str) -> None:
    global _last_ended_blank
    print(f"  {RED}✗{RESET}  {msg}", file=sys.stderr)
    errors.append(msg)
    _last_ended_blank = False


def banner(version: str) -> None:
    art = (
        "                   .:'",
        "                 __ :'__",
        "              .'`__`-'__`'.",
        "             :__________.-'",
        "             :_________:",
        "              :_________`-;",
        "               `.__.-.__.'",
    )
    print()
    # Apple Computer rainbow: top line uses the leaf-green; the body's
    # six rows map onto the six bands of the original logo (green,
    # yellow, orange, red, purple, blue). One color per line so the
    # gradient reads as a stripe.
    for line, colour in zip(art, _APPLE_RAINBOW):
        print(f"  {colour}{BOLD}{line}{RESET}")
    # If we ever add more art rows than colours, fall through to the
    # last colour so we never crash on a misaligned tuple.
    for extra in art[len(_APPLE_RAINBOW):]:
        print(f"  {_APPLE_RAINBOW[-1]}{BOLD}{extra}{RESET}")
    print()
    print(f"  {GREEN}{BOLD}        MacTahoe Liquid KDE {WHITE}v{version}{RESET}")
    print(f"  {WHITE}            Developed by Lester{RESET}")
    print()
