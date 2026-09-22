# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Partiu (pure SQLite + tkinter, no external deps)."""

import os
import sys

SPEC_DIR = os.path.abspath(SPECPATH)  # noqa: F821
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
ENTRY = os.path.join(PROJECT_ROOT, "run.py")

a = Analysis(
    [ENTRY],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="partiu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
    codesign_identity=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="partiu",
)

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name="Partiu.app",
        icon=None,
        bundle_identifier="com.partiu.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleName": "Partiu",
            "CFBundleDisplayName": "Partiu",
            "CFBundleShortVersionString": "0.1.0",
            "LSMinimumSystemVersion": "12.0",
        },
    )
