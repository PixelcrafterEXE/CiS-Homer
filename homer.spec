# -*- mode: python ; coding: utf-8 -*-
# Run from the project root:  pyinstaller --noconfirm homer.spec
#
# SPECPATH is set by PyInstaller to the directory containing this file
# (the project root), so all paths below are relative to that.

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

spec_dir = Path(SPECPATH)
software_dir = spec_dir / "Software"

block_cipher = None

ttkbootstrap_datas, ttkbootstrap_bins, ttkbootstrap_hidden = collect_all("ttkbootstrap")
matplotlib_datas,   matplotlib_bins,   matplotlib_hidden   = collect_all("matplotlib")

extra_datas = [
    (str(software_dir / "res"), "res"),
    *ttkbootstrap_datas,
    *matplotlib_datas,
]

# On Windows, PyInstaller's tkinter hook sometimes omits the Tcl msgcat
# package from the bundle, causing a TclError on first ttkbootstrap init.
# Explicitly include the full Tcl library directory to avoid this.
if sys.platform == "win32":
    tcl_dir = Path(sys.base_prefix) / "tcl"
    if tcl_dir.is_dir():
        for entry in tcl_dir.iterdir():
            if entry.is_dir():
                extra_datas.append((str(entry), entry.name))

a = Analysis(
    [str(software_dir / "main.py")],
    pathex=[str(software_dir)],
    binaries=ttkbootstrap_bins + matplotlib_bins,
    datas=extra_datas,
    hiddenimports=[
        "serial.tools.list_ports",
        "PIL._tkinter_finder",
        *ttkbootstrap_hidden,
        *matplotlib_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(software_dir / "build_hook.py")],
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
    name="homer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
