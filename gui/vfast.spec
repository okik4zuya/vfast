# -*- mode: python ; coding: utf-8 -*-
# Build with: venv-gui\Scripts\pyinstaller gui\vfast.spec --noconfirm
# (works from any cwd — all paths below are resolved relative to this spec file via SPECPATH)
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.dirname(SPECPATH)

# collect_submodules() imports the named package using the current sys.path;
# pathex is only applied to sys.path later, inside Analysis(), so gui/ (where
# panels/ lives) must be added here or collect_submodules('panels') silently
# returns [].
sys.path.insert(0, SPECPATH)

# yt-dlp lazily imports its extractor plugins at runtime; PyInstaller's static
# analysis can't see those, so collect every submodule explicitly (needed for
# core/download.py's --run-yt-dlp re-entry point, see main.py).
YT_DLP_IMPORTS = collect_submodules('yt_dlp')

# app.py._show_panel() resolves panel modules via importlib.import_module()
# using string names built from a dict, so PyInstaller's static analysis can't
# see them either — collect the panels package explicitly.
PANEL_IMPORTS = collect_submodules('panels')

a = Analysis(
    [os.path.join(SPECPATH, 'main.py')],
    pathex=[SPECPATH],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'bin', 'ffmpeg.exe'), 'bin'),
        (os.path.join(ROOT, 'bin', 'ffprobe.exe'), 'bin'),
        (os.path.join(ROOT, 'bin', 'mpv.exe'), 'bin'),
        (os.path.join(ROOT, 'assets', 'icon', 'app-icon.ico'), 'assets/icon'),
        (os.path.join(SPECPATH, 'VERSION'), '.'),
        (os.path.join(ROOT, 'venv-gui', 'Lib', 'site-packages', 'customtkinter'), 'customtkinter'),
    ],
    hiddenimports=YT_DLP_IMPORTS + PANEL_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='vfast',
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
    icon=os.path.join(ROOT, 'assets', 'icon', 'app-icon.ico'),
)
