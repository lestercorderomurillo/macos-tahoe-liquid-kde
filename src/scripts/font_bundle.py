"""Verified offline font payload; extraction never uses archive paths."""
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile


def unpacked_fonts(payload: bytes, manifest: dict) -> dict[str, bytes]:
    if hashlib.sha256(payload).hexdigest() != manifest['archive_sha256']:
        raise ValueError('Font archive checksum mismatch')
    expected = manifest['files']
    result = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:xz') as archive:
        for member in archive:
            name = member.name
            if (not member.isfile() or name != Path(name).name
                    or Path(name).suffix not in ('.otf', '.ttf')
                    or name in result or name not in expected
                    or member.size != expected[name]['size']):
                raise ValueError('Invalid font archive member')
            data = archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != expected[name]['sha256']:
                raise ValueError('Font checksum mismatch')
            result[name] = data
    if result.keys() != expected.keys():
        raise ValueError('Incomplete font archive')
    return result


@contextmanager
def font_sources(source: Path, installed: Path):
    loose = sorted([*source.glob('*.otf'), *source.glob('*.ttf')])
    archive = source / 'fonts.tar.xz'
    if not archive.exists():
        yield loose
        return
    manifest = json.loads((source / 'fonts.json').read_text())
    # Validate the complete payload before touching any installed file.
    contents = unpacked_fonts(archive.read_bytes(), manifest)
    with tempfile.TemporaryDirectory(prefix='mttkde-fonts-') as directory:
        paths = list(loose)
        for name, data in contents.items():
            target = installed / name
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == manifest['files'][name]['sha256']:
                paths.append(target)
                continue
            path = Path(directory) / name
            path.write_bytes(data)
            paths.append(path)
        yield paths
