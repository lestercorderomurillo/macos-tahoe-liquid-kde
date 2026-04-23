import sys


HELP = """\
Usage: python3 -m installer <command> [args...]

Commands:
  install        Install MacTahoe Liquid KDE
  uninstall      Uninstall MacTahoe Liquid KDE
  theme-switch   Switch / apply light or dark theme
  transparency   Tune background opacity across Kvantum, Plasma, GTK
  svgzc          Decode/encode .svgz Plasma theme files for editing
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0

    cmd, rest = argv[0], argv[1:]

    if cmd == "install":
        from installer.cli import run_install
        return run_install(rest)
    if cmd == "uninstall":
        from installer.cli import run_uninstall
        return run_uninstall(rest)
    if cmd in {"theme-switch", "theme_switch"}:
        from installer.theme_switch import main as ts_main
        return ts_main(rest)
    if cmd == "transparency":
        from installer.transparency import main as t_main
        return t_main(rest)
    if cmd == "svgzc":
        from installer.svgzc import main as s_main
        return s_main(rest)

    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
