#!/usr/bin/env python3
"""Graphical sudo fallback when a PolicyKit agent is unavailable."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from localization import tr

    app = QApplication(sys.argv[:1])
    password, accepted = QInputDialog.getText(
        None, tr("Administrator authentication"), tr("Password:"), QLineEdit.EchoMode.Password)
    if not accepted:
        raise SystemExit(1)
    # sudo reads this private pipe; never send the password to application logs.
    sys.stdout.write(password + "\n")
