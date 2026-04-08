#!/usr/bin/env python3
"""
Inventaria arquivos locais de MEDIA para apoiar migração para bucket.

Uso:
  python3 scripts/storage/audit_local_media.py
  MEDIA_ROOT=/caminho/custom python3 scripts/storage/audit_local_media.py
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class FileEntry:
    path: str
    size_bytes: int
    md5: str


def md5sum(file_path: Path) -> str:
    digest = hashlib.md5()  # noqa: S324 - checksum para inventário, não para segurança
    with file_path.open('rb') as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    media_root = Path(os.getenv('MEDIA_ROOT', 'media')).resolve()
    if not media_root.exists():
        print(
            json.dumps(
                {
                    'media_root': str(media_root),
                    'exists': False,
                    'total_files': 0,
                    'total_size_bytes': 0,
                    'files': [],
                },
                indent=2,
            )
        )
        return

    files: list[FileEntry] = []
    for file_path in sorted(path for path in media_root.rglob('*') if path.is_file()):
        files.append(
            FileEntry(
                path=str(file_path.relative_to(media_root)).replace('\\', '/'),
                size_bytes=file_path.stat().st_size,
                md5=md5sum(file_path),
            )
        )

    print(
        json.dumps(
            {
                'media_root': str(media_root),
                'exists': True,
                'total_files': len(files),
                'total_size_bytes': sum(file.size_bytes for file in files),
                'files': [asdict(file) for file in files],
            },
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
