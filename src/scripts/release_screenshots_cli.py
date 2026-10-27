"""Maintainer entry point for version-bound screenshot capture and release checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from release_screenshots import ROOT, EDITIONS, commit_id, digest, require, stage, validate, verify_committed, verify_recipe


def publish(repo, ref, tahoe=None):
    record = verify_committed(repo, ref, tahoe=tahoe)
    tag = 'v' + record['version']
    require(commit_id(repo, tag) == commit_id(repo, ref), 'Release tag does not point to the verified commit')
    subprocess.run(['gh', 'release', 'create', tag, '--verify-tag', '--title', tag, '--generate-notes'],
                   cwd=repo, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('capture', help='Capture all required frames in fresh disposable VMs')
    capture.add_argument('--ref', default='HEAD')
    capture.add_argument('--vm-image', type=Path, required=True)
    capture.add_argument('--output', type=Path, required=True)
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
        if args.command == 'capture':
            from release_capture import capture as run_capture
            verify_recipe(args.repo, args.ref)
            run_capture(args.repo, args.ref, args.vm_image, args.output)
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
            print('Screenshots verified for v' + record['version'])
        elif args.command == 'publish':
            publish(args.repo, args.ref, args.tahoe_repo)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Release screenshots blocked: {exc}\n')
    return 0
