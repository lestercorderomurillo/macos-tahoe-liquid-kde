#!/usr/bin/env python3
"""Graphical sudo fallback when a PolicyKit agent is unavailable."""

import sys

from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit

if __name__ == "__main__":
    app = QApplication(sys.argv[:1])
    password, accepted = QInputDialog.getText(
        None, "Administrator authentication", "Password:", QLineEdit.EchoMode.Password)
    if not accepted:
        raise SystemExit(1)
    # sudo reads this private pipe; never send the password to application logs.
    sys.stdout.write(password + "\n")
