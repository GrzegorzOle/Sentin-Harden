# -*- mode: python ; coding: utf-8 -*-
"""Freeze configuration for the desktop application.

Deliberately a directory build rather than a single file. Two reasons, both
binding:

* PySide6 is under the LGPL. A directory layout keeps its libraries replaceable,
  which is the condition the licence puts on shipping it inside a closed
  artifact. A single-file build unpacks to a temporary directory and does not
  meet it.
* The installer produces a directory installation anyway, so nothing is gained
  by packing the runtime into one file and then unpacking it on every start.

The rule base travels with the artifact as data. It is read through
``paths.resource``, which resolves to the extraction directory once frozen, so
nothing here may assume a path relative to the sources.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PROJECT = Path(SPECPATH)

# The whole rule base, keeping its directory layout. Loading walks the tree and
# reads meta.yaml per target, so the shape matters as much as the files.
datas = [
    (str(PROJECT / "rules"), "rules"),
    (str(PROJECT / "assets"), "assets"),
    (str(PROJECT / "NOTICE"), "."),
    (str(PROJECT / "LICENSE"), "."),
]

# The window icon travels as data and is set by the application itself, which is
# the only route that works on Linux - PyInstaller embeds an icon on Windows and
# macOS only, and warns about it everywhere else. So the embedded icon is asked
# for on those two platforms and left alone on the third.
ICON = PROJECT / "assets" / "sentin-harden.ico" if os.name == "nt" else None

# yaml and jsonschema reach for parts of themselves by name, which the import
# graph does not see.
hiddenimports = collect_submodules("jsonschema") + [
    "yaml",
    "yaml.cyaml",
]

# Nothing outside the audit window is used. Leaving the rest in costs a few
# hundred megabytes and lengthens the signing step for no gain.
excludes = [
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSerialPort",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtSql",
    "tkinter",
    "unittest",
    "pydoc_data",
]

a = Analysis(
    [str(PROJECT / "sentin_harden" / "__main__.py")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Sentin-Harden",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # A console would appear behind the window on every start. Faults are shown
    # in the window itself rather than on a stream nobody reads.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Audit reads much that an ordinary account cannot, and remediation writes
    # to places it certainly cannot. The application recognises this and says so
    # rather than reporting an item as unmet, so it starts without demanding
    # elevation and asks for it only where a change is to be made.
    uac_admin=False,
    icon=str(ICON) if ICON and ICON.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Sentin-Harden",
)
