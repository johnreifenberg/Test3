# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

a = Analysis(
    ['backend/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('frontend', 'frontend'),
        ('templates', 'templates'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'backend',
        'backend.api',
        'backend.api.routes',
        'backend.engine',
        'backend.engine.calculator',
        'backend.engine.distributions',
        'backend.engine.sensitivity',
        'backend.engine.terminal_value',
        'backend.models',
        'backend.models.model',
        'backend.models.stream',
        'backend.services',
        'backend.services.persistence',
        'backend.services.excel_export',
        'multipart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Inflection',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
