#!/usr/bin/env python3
"""Exercise seekable archive validation with real piped SSH input."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

BOOTSTRAP = Path(__file__).resolve().parents[2] / 'remote/scripts/bootstrap.py'
OPTIONS = json.dumps({'action': 'install', 'system': False, 'force': False, 'components': []})


def archive(extra=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as bundle:
        payload = b'import sys; print("BOOTSTRAP_OK", sys.argv[1]); raise SystemExit(0)\n'
        entry = tarfile.TarInfo('module/portable_module.py')
        entry.size = len(payload)
        bundle.addfile(entry, io.BytesIO(payload))
        # Force extraction to revisit data well before the end of the gzip stream.
        payload = bytes(range(256)) * 1024
        entry = tarfile.TarInfo('module/padding')
        entry.size = len(payload)
        bundle.addfile(entry, io.BytesIO(payload))
        if extra:
            bundle.addfile(extra)
    return output.getvalue()


def run(payload):
    return subprocess.run([sys.executable, str(BOOTSTRAP), OPTIONS], input=payload,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)


def main():
    result = run(archive())
    assert result.returncode == 0, result.stderr
    assert b'BOOTSTRAP_OK install' in result.stdout
    for name, kind in [('module/../escape', tarfile.REGTYPE),
                       ('/absolute', tarfile.REGTYPE), ('other/file', tarfile.REGTYPE),
                       ('module/link', tarfile.SYMTYPE), ('module/hard', tarfile.LNKTYPE),
                       ('module/fifo', tarfile.FIFOTYPE)]:
        entry = tarfile.TarInfo(name)
        entry.type = kind
        if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            entry.linkname = '../escape'
        result = run(archive(entry))
        assert result.returncode != 0, name
        assert b'Unsafe module archive member' in result.stderr, result.stderr
        assert b'BOOTSTRAP_OK' not in result.stdout
    print('Piped bootstrap and unsafe archive rejection tests passed')


if __name__ == '__main__':
    main()
