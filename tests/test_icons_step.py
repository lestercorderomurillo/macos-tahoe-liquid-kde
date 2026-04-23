from pathlib import Path

from installer.steps import icons


def test_assemble_preserves_upstream_alias_symlinks(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    src = repo / "src/actions/16"
    links = repo / "links/actions/16"
    src.mkdir(parents=True)
    links.mkdir(parents=True)

    (repo / "src/index.theme").write_text(
        "[Icon Theme]\n"
        "Name=MacTahoe\n"
        "Inherits=hicolor,breeze\n"
        "Directories=actions/16\n"
        "\n"
        "[actions/16]\n"
        "Size=16\n"
        "Context=Actions\n"
        "Type=Fixed\n"
    )
    (src / "list-add.svg").write_text("<svg/>")
    (src / "add.svg").write_text("<svg>old</svg>")
    (links / "add.svg").symlink_to("list-add.svg")

    cache = tmp_path / "cache"
    monkeypatch.setattr(icons, "CACHE", cache)

    icons._assemble(repo, "MacTahoeLiquidKde-Icons")

    out = cache / "MacTahoeLiquidKde-Icons/actions/16/add.svg"
    assert out.is_symlink()
    assert out.readlink() == Path("list-add.svg")
    assert out.resolve().read_text() == "<svg/>"
