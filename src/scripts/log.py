import sys

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
RESET = "\033[0m"
BOLD = "\033[1m"

_step_counter = 0
errors: list[str] = []
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
        "                   .:'\n"
        "                 __ :'__\n"
        "              .'`__`-'__`'.\n"
        "             :__________.-'\n"
        "             :_________:\n"
        "              :_________`-;\n"
        "               `.__.-.__.'\n"
    )
    print()
    for line in art.splitlines():
        print(f"  {RED}{BOLD}{line}{RESET}")
    print()
    print(f"  {GREEN}{BOLD}        MacTahoe Liquid KDE {WHITE}v{version}{RESET}")
    print(f"  {WHITE}            Developed by Lester{RESET}")
    print()
