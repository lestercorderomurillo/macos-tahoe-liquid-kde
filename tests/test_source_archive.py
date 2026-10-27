from pathlib import Path
import subprocess
import tarfile


def test_source_archive_omits_gallery_and_preserves_installation_sources(tmp_path):
    root = Path(__file__).resolve().parents[1]
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitattributes").write_bytes((root / ".gitattributes").read_bytes())
    files = ("src/screenshots/gallery.png", "src/screenshots/vm/proof.png",
             "src/installer/assets/preview.png", "src/offline/wallpapers/image.jpg",
             "src/scripts/launcher_defaults.py", "tests/test_example.py",
             "LICENSE", "NOTICE", "LICENSES/component.txt", "VERSION", "installer")
    for name in files:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
                    "user.email=test@example.invalid", "commit", "-qm", "fixture"], check=True)
    archive = tmp_path / "source.tar"
    subprocess.run(["git", "-C", str(repo), "archive", "-o", str(archive), "HEAD"], check=True)
    with tarfile.open(archive) as bundle:
        names = set(bundle.getnames())
    assert not any(name.startswith("src/screenshots/") for name in names)
    assert set(files[2:]) <= names
    assert all((repo / name).is_file() for name in files)
