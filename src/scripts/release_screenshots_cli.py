"""Maintainer entry point for version-bound screenshot capture and release checks."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import subprocess

from release_screenshots import ROOT, EDITIONS, commit_id, digest, require, stage, validate, verify_committed, verify_recipe, git


def publish(repo, ref, tahoe=None):
    record = verify_committed(repo, ref, tahoe=tahoe)
    tag = 'v' + git(repo, 'show', commit_id(repo, ref) + ':VERSION')
    require(commit_id(repo, tag) == commit_id(repo, ref), 'Release tag does not point to the verified commit')
    prerelease = ['--prerelease', '--latest=false'] if re.search(r'rc\.?[0-9]+$', tag) else []
    subprocess.run(['gh', 'release', 'create', tag, '--verify-tag', '--title', tag, '--generate-notes', *prerelease],
                   cwd=repo, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('capture', help='Capture all required frames in fresh disposable VMs')
    capture.add_argument('--ref', default='HEAD')
    capture.add_argument('--vm-image', type=Path, required=True)
    capture.add_argument('--output', type=Path, required=True)
    capture.add_argument('--reuse', type=Path, help='Reuse reviewed frames whose visual inputs are unchanged')
    capture.add_argument('--only-system-menu', action='store_true',
                         help='Capture only the two editions of the system menu in light and dark mode')
    history_stage = sub.add_parser('stage-notification-photos', help='Replace the existing README notification photographs')
    history_stage.add_argument('--bundle', type=Path, required=True)
    history_stage.add_argument('--edition', choices=EDITIONS, required=True)
    history_stage.add_argument('--destination', type=Path, required=True)
    installer_photos = sub.add_parser('stage-readme-installer', help='Stage the reviewed light and dark wizard pages in TESTING.md')
    installer_photos.add_argument('--bundle', type=Path, required=True)
    installer_photos.add_argument('--edition', choices=EDITIONS, required=True)
    installer_photos.add_argument('--destination', type=Path, required=True)
    audit = sub.add_parser('readme-photos', help='Verify and list the existing README capture slots')
    audit.add_argument('--destination', type=Path, default=ROOT)
    photos = sub.add_parser('stage-readme-photos', help='Replace selected existing README photographs')
    photos.add_argument('--bundle', type=Path, required=True)
    photos.add_argument('--edition', choices=EDITIONS, required=True)
    photos.add_argument('--destination', type=Path, required=True)
    photos.add_argument('--slot', action='append', help='Exact slot name; repeat to select multiple')
    shell = sub.add_parser('capture-readme-photos', help='Photograph the README and installer on each edition wallpaper')
    shell.add_argument('--dock-only', action='store_true', help='Capture the two multicolor Dock animations only')
    shell.add_argument('--ref', default='HEAD')
    shell.add_argument('--vm-image', type=Path, required=True)
    shell.add_argument('--output', type=Path, required=True)
    shell.add_argument('--edition', choices=EDITIONS, action='append')
    shell.add_argument('--guest-package', type=Path, action='append', default=[], help='Offline SDK dependency for the prepared guest')
    previews = sub.add_parser('file-previews', help='Capture focused Nautilus/Dolphin installer previews only')
    previews.add_argument('--ref', default='HEAD')
    previews.add_argument('--resume', action='store_true', help='Reuse this failed capture overlay with the identical source archive')
    previews.add_argument('--vm-image', type=Path, required=True)
    previews.add_argument('--output', type=Path, required=True)
    preview_stage = sub.add_parser('stage-file-previews', help='Stage four visually reviewed file-manager previews')
    preview_stage.add_argument('--bundle', type=Path, required=True)
    preview_stage.add_argument('--reviewed', action='store_true', required=True,
                               help='Confirm each of the four original frames was visually inspected')
    review = sub.add_parser('review', help='Record a decision for images you have visually inspected')
    review.add_argument('--ref', default='HEAD')
    review.add_argument('--bundle', type=Path, required=True)
    review.add_argument('--approve', nargs='+', default=[])
    review.add_argument('--reject', nargs='+', default=[])
    stage_parser = sub.add_parser('stage', help='Install the complete reviewed screenshot set in one edition')
    stage_parser.add_argument('--ref', default='HEAD', help='Tahoe source ref')
    stage_parser.add_argument('--bundle', type=Path, required=True)
    stage_parser.add_argument('--edition', choices=EDITIONS, required=True)
    stage_parser.add_argument('--destination', type=Path, required=True)
    for name in ('verify', 'publish'):
        command = sub.add_parser(name, help='Reject stale, incomplete or unreviewed committed screenshots')
        command.add_argument('--ref', default='HEAD')
        command.add_argument('--tahoe-repo', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'capture-readme-photos':
            from readme_shell_capture import capture
            capture(args.repo.resolve(), args.ref, args.vm_image, args.output.resolve(),
                    args.edition or list(EDITIONS), args.guest_package, dock_only=args.dock_only)
        elif args.command == 'stage-readme-installer':
            from release_readme_photos import stage_installer_gallery
            stage_installer_gallery(args.destination.resolve(), args.edition, args.bundle.resolve())
        elif args.command == 'readme-photos':
            from release_readme_photos import inventory
            edition, documents, _, slots = inventory(args.destination)
            print(f'{edition}: {len(slots)} verified slots in {len(documents)} READMEs')
            print('\n'.join(slots))
        elif args.command in ('stage-readme-photos', 'stage-notification-photos'):
            from release_readme_photos import stage as stage_photos
            names = ([f'readme-{args.edition}-{mode}-notifications' for mode in ('light', 'dark')]
                     if args.command == 'stage-notification-photos' else args.slot)
            count = stage_photos(args.destination, args.edition, args.bundle, names)
            print(f'Updated {count} README photographs.')
        elif args.command == 'stage-file-previews':
            from release_capture import stage_file_previews
            stage_file_previews(args.repo.resolve(), args.bundle.resolve())
            print('Staged four reviewed, focused file-manager previews.')
        elif args.command == 'file-previews':
            from release_capture import capture_file_previews
            capture_file_previews(args.repo, args.ref, args.vm_image, args.output, resume=args.resume)
            print('Captured four file-manager previews; inspect each before publishing.')
        elif args.command == 'capture':
            from release_capture import capture as run_capture
            verify_recipe(args.repo, args.ref)
            run_capture(args.repo, args.ref, args.vm_image, args.output, reuse=args.reuse,
                        system_menu_only=args.only_system_menu)
            print(f'Captured all frames. Visually inspect {args.output / "frames"} before review.')
        elif args.command == 'review':
            manifest = validate(args.repo, args.ref, args.bundle, reviewed=False)
            require(bool(args.approve or args.reject), 'Specify frame names to approve or reject after inspection')
            require(not set(args.approve) & set(args.reject), 'A frame cannot be both approved and rejected')
            require(set(args.approve + args.reject) <= manifest['frames'].keys(), 'Unknown review frame')
            path = args.bundle / 'review.json'
            review = json.loads(path.read_text()) if path.exists() else {
                'manifest_sha256': digest(args.bundle / 'manifest.json'), 'approved': {}, 'rejected': {}}
            require(review['manifest_sha256'] == digest(args.bundle / 'manifest.json'), 'Review belongs to another capture run')
            for decision, opposite, names in [('approved', 'rejected', args.approve), ('rejected', 'approved', args.reject)]:
                for name in names:
                    review[decision][name] = manifest['frames'][name]['sha256']
                    review[opposite].pop(name, None)
            path.write_text(json.dumps(review, indent=2) + '\n')
            print(f"Reviewed: {len(review['approved'])} approved, {len(review['rejected'])} rejected / {len(manifest['frames'])} frames")
        elif args.command == 'stage':
            manifest = validate(args.repo, args.ref, args.bundle)
            require((args.destination / 'VERSION').read_text().strip() == manifest['version'], 'Destination version mismatch')
            stage(args.destination, args.edition, args.bundle, manifest)
            print('Staged the complete reviewed screenshot set; commit it before publishing.')
        elif args.command == 'verify':
            record = verify_committed(args.repo, args.ref, tahoe=args.tahoe_repo)
            print('Screenshots verified; original capture v' + record['version'])
        elif args.command == 'publish':
            publish(args.repo, args.ref, args.tahoe_repo)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Release screenshots blocked: {exc}\n')
    return 0
