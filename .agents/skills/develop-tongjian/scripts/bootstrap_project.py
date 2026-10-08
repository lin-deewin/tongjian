#!/usr/bin/env python3
"""Restore the accepted project snapshot into an empty directory."""
import argparse
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        parser.error('target must be a nonexistent or empty directory')
    source = Path(__file__).resolve().parents[1] / 'assets/project-baseline'
    if not (source / 'dist/index.html').is_file():
        parser.error('baseline assets are missing')
    shutil.copytree(source, target, dirs_exist_ok=True)
    print(f'Restored local project: {target}')
    print('Serve dist over HTTP; production identity is not included.')


if __name__ == '__main__':
    main()
