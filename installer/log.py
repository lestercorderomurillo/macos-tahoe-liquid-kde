import sys

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
RESET = "\033[0m"
BOLD = "\033[1m"

_step_counter = 0
errors: list[str] = []


def step(title: str) -> None:
    global _step_counter
    _step_counter += 1
    print()
    print(f"{GREEN}{BOLD}  Step {_step_counter}: {title}{RESET}")


def note(msg: str) -> None:
    if msg:
        print(f"  {msg}")
    print()


def info(msg: str) -> None:
    print()
    print(f"  {BOLD}{msg}{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")


def reinstall(msg: str) -> None:
    print(f"  {GREEN}↺{RESET}  {msg} (reinstalled)")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET}  {msg}", file=sys.stderr)
    errors.append(msg)


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
