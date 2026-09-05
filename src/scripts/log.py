import atexit
import errno
import os
import secrets
import stat
import sys

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
WHITE = "\033[1;37m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Apple 1977-1998 rainbow logo bands, top → bottom. 256-color codes —
# basic ANSI has no orange or purple.
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

_CONFIGURED_PROGRESS_FILE = os.environ.get("MTTKDE_PROGRESS_FILE")
PROGRESS_FILE = _CONFIGURED_PROGRESS_FILE or (
    f"/tmp/mttkde-install-progress-{os.getpid()}-{secrets.token_hex(8)}"
)
DONE_MARKER = "__DONE__"


def _open_progress_file(*, truncate: bool) -> int:
    """Open the progress channel without following or damaging hostile paths.

    The GUI creates this file with ``mkstemp`` before privilege escalation.
    Classic/TUI runs lazily create their per-process random path here.  Never
    use O_TRUNC until fstat has proved that the opened inode is a regular,
    single-link file owned by the effective user.
    """
    flags = os.O_WRONLY
    # GUI runs create and own this channel before privilege escalation.  If
    # the GUI has already reaped its supervisor and removed the channel, a
    # still-unwinding privileged CLI must not resurrect a stale file that no
    # process will watch or clean up.  Classic/TUI runs retain lazy creation
    # for their private, random per-process path.
    if _CONFIGURED_PROGRESS_FILE is None:
        flags |= os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    if not truncate:
        flags |= os.O_APPEND

    fd = os.open(PROGRESS_FILE, flags, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EPERM, "progress path is not a regular file")
        if info.st_uid != os.geteuid():
            raise OSError(errno.EPERM, "progress file has the wrong owner")
        if info.st_nlink != 1:
            raise OSError(errno.EPERM, "progress file has multiple links")
        os.fchmod(fd, 0o600)
        if truncate:
            os.ftruncate(fd, 0)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError(errno.EIO, "short progress-file write")
        view = view[written:]


def _progress_write(record: str) -> None:
    fd: int | None = None
    try:
        fd = _open_progress_file(truncate=False)
        _write_all(fd, (record + "\n").encode("utf-8"))
    except OSError:
        pass
    finally:
        if fd is not None:
            os.close(fd)


def progress_reset() -> None:
    global _step_counter
    _step_counter = 0
    fd: int | None = None
    try:
        fd = _open_progress_file(truncate=True)
    except OSError:
        pass
    finally:
        if fd is not None:
            os.close(fd)


def progress_done(exit_code: int) -> None:
    _progress_write(f"{DONE_MARKER}\t{int(exit_code)}")


if _CONFIGURED_PROGRESS_FILE is None:
    # GUI-owned paths are removed by the GUI after QProcess completion.  The
    # classic/TUI path only needs to survive until this interpreter exits.
    def _cleanup_default_progress_file(path: str = PROGRESS_FILE) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass

    atexit.register(_cleanup_default_progress_file)


_last_ended_blank = False


def step(title: str) -> None:
    global _step_counter, _last_ended_blank
    _step_counter += 1
    if not _last_ended_blank:
        print()
    print(f"{GREEN}{BOLD}  Step {_step_counter}: {title}{RESET}")
    _last_ended_blank = False
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


# Shared with the install TUI (install_tui.py) so both render the same logo.
APPLE_ART = (
    "                   .:'",
    "                 __ :'__",
    "              .'`__`-'__`'.",
    "             :__________.-'",
    "             :_________:",
    "              :_________`-;",
    "               `.__.-.__.'",
)


def banner(version: str) -> None:
    art = APPLE_ART
    print()
    for line, colour in zip(art, _APPLE_RAINBOW):
        print(f"  {colour}{BOLD}{line}{RESET}")
    # Extra art rows beyond the palette reuse the last colour.
    for extra in art[len(_APPLE_RAINBOW):]:
        print(f"  {_APPLE_RAINBOW[-1]}{BOLD}{extra}{RESET}")
    print()
    print(f"  {GREEN}{BOLD}        MacTahoe Liquid KDE {WHITE}v{version}{RESET}")
    print(f"  {WHITE}            Developed by Lester{RESET}")
    print()
