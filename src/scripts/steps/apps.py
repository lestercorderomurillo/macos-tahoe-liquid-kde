"""Optional applications survive theme removal."""
from dock_apps import install_selected
from installer_choices import selected


def install() -> None:
    install_selected(selected())


def uninstall() -> None:
    pass
