# -*- mode: python ; coding: utf-8 -*-

import os

repo_root = os.path.abspath(os.getcwd())
spec_dir = os.path.join(repo_root, 'tools', 'canary-mailer')
project_root = os.path.abspath(os.path.join(spec_dir, os.pardir, os.pardir))

a = Analysis(
    [os.path.join(spec_dir, 'app.py')],
    pathex=[spec_dir, project_root],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='canary-mailer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    distpath=os.path.join(project_root, 'dist'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='canary-mailer',
)
