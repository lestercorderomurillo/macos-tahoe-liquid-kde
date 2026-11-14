"""One system-wide install/removal transaction across editions and checkouts."""

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat


class InstallerBusy(RuntimeError):
    pass


@contextmanager
def installer_lock(path=Path('/run/lock/mac-tahoe-liquid-kde-installer.lock')):
    # Called before the root backend drops its effective identity. Keep this
    # inode forever: unlinking a locked file lets another opener lock a new one.
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            raise OSError('Unsafe installer lock: owner, type, permissions or link count changed')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise InstallerBusy('Another installation or removal is running. Wait for it to finish before trying again.') from None
        yield
    finally:
        os.close(fd)
