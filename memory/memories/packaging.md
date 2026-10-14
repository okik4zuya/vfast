---
name: packaging
description: PyInstaller build + NSIS installer pipeline for vfast GUI — verified end-to-end, incl. the yt-dlp frozen-mode fix
metadata:
  type: project
  tier: T0
  created: 2026-09-12 10:48
  updated: 2026-10-14 18:18
---

# vfast GUI packaging: PyInstaller + NSIS

Verified end-to-end in session (2026-09-12): built `dist/vfast.exe` via PyInstaller, then
`vfast-setup.exe` via NSIS, from a clean `venv-gui` (PyInstaller wasn't installed — added
`gui/requirements-build.txt` for it, kept separate from `gui/requirements.txt` since it's a
build-only tool, not a runtime dependency).

## Build commands (from repo root)

```
venv-gui\Scripts\pip install -r gui\requirements-build.txt   # once
venv-gui\Scripts\pyinstaller gui\vfast.spec --noconfirm --distpath dist --workpath build
makensis gui\installer.nsi
```
`makensis.exe` lives at `C:\Program Files (x86)\NSIS\makensis.exe` (installed, not on PATH).

## Bugs found and fixed this session

1. **`gui/vfast.spec` paths were wrong relative to invocation directory.** The old spec used
   bare relative paths (`'gui/main.py'`, `'bin/ffmpeg.exe'`) with a comment saying "build from
   repo root" — but PyInstaller `chdir`s into the spec file's own directory before resolving
   paths, so `pyinstaller gui/vfast.spec` failed with `script 'gui/gui/main.py' not found`. Fixed
   by resolving every path through PyInstaller's injected `SPECPATH` variable
   (`os.path.join(SPECPATH, ...)` / `os.path.join(os.path.dirname(SPECPATH), ...)`), which works
   regardless of cwd.
2. **`gui/installer.nsi` relative paths were also wrong** for the same underlying reason but the
   opposite direction: NSIS resolves relative `File`/`Icon`/`OutFile` paths relative to the
   **script's own directory** (`gui/`), not cwd — confirmed empirically (`File "dist\vfast.exe"`
   with cwd=repo root still failed with "no files found" until changed to `"..\dist\vfast.exe"`).
   Fixed all three: `File "..\dist\${APP_EXE}"`, `Icon "..\assets\icon\app-icon.ico"`,
   `OutFile "..\vfast-setup.exe"` (so the installer lands at the repo root, matching where `dist/`
   and `build/` already land).
3. **Download panel would have been silently broken in the shipped installer.**
   `core/download.py`'s `_yt_dlp_cmd()` unconditionally returned
   `[sys.executable, "-m", "yt_dlp"]` — works in dev (venv python), but in a frozen PyInstaller
   exe `sys.executable` **is** `vfast.exe`, which has no `-m` flag support, and yt-dlp was never
   `import`ed anywhere in the codebase so PyInstaller's static analysis wouldn't have bundled it
   at all even if invocation were fixed. **Fix (three-part):**
   - `gui/main.py`: added a `--run-yt-dlp` re-entry point (`_run_yt_dlp()`, checked in
     `if __name__ == "__main__"` before the normal GUI path) that does `import yt_dlp;
     yt_dlp.main(argv)`. This import is what makes PyInstaller's analysis trace yt-dlp at all.
   - `core/download.py`: `_yt_dlp_cmd()` now branches on `sys.frozen` — frozen returns
     `[sys.executable, "--run-yt-dlp"]`, dev keeps the old `-m yt_dlp` form.
   - `gui/vfast.spec`: added `hiddenimports=collect_submodules('yt_dlp')` — yt-dlp lazy-loads its
     extractor plugins at runtime in a way plain static analysis can miss even when the top-level
     `import yt_dlp` is traced.
   - **Verified for real**, not just headlessly: `dist\vfast.exe --run-yt-dlp --version` printed
     the yt-dlp version, and `dist\vfast.exe --run-yt-dlp -j --no-playlist <youtube-url>` made a
     real network request and got a real yt-dlp response (a JS-runtime warning from yt-dlp itself,
     unrelated to packaging — same warning would occur in dev mode).

## App icon now wired in (was flagged as pending in [[app-icon]]/[[status]])

- `gui/app.py`: added `_resource_path()` (resolves against `sys._MEIPASS` when frozen, repo root
  in dev) and calls `self.iconbitmap(_resource_path("assets/icon/app-icon.ico"))` in `App.__init__`
  wrapped in `try/except` (so a missing icon file never crashes the GUI).
- `gui/vfast.spec`: added `assets/icon/app-icon.ico` to `datas` (so it's present at `_MEIPASS` at
  runtime) and `icon=...` on the `EXE(...)` call (so the built .exe itself carries the icon in
  Explorer/taskbar). PyInstaller build log confirmed "Copying icon to EXE".
- `gui/installer.nsi`: added `Icon`/`UninstallIcon` (installer/uninstaller exe icon), version-info
  keys (`VIProductVersion`, `VIAddVersionKey` — includes `LegalCopyright`, avoiding a NSIS
  warning), a desktop shortcut alongside the existing Start Menu one, and extra
  `Software\...\Uninstall\vfast` registry keys (`DisplayIcon`, `DisplayVersion`, `Publisher`,
  `NoModify`, `NoRepair`) so the app shows up properly in Windows' "Apps & features" list.

## `.gitignore` created (repo had none, and isn't a git repo yet — `git init` not done, not asked)

Excludes venvs, `__pycache__`, PyInstaller `build`/`dist`, `*-setup.exe`, and the four large
third-party binaries in `bin/` (ffmpeg/ffplay/ffprobe/mpv, ~670MB combined — far too big for a
normal git repo; anyone cloning fresh needs to re-fetch these into `bin/` before building).

## `panels/` package missing from frozen exe (found post-session, fixed 2026-09-12 later)

User launched the shipped `dist/vfast.exe` and hit `ModuleNotFoundError: No module named 'panels'`
at startup. Root cause chain (two bugs stacked):

1. **`gui/app.py`'s `_show_panel()` resolves every panel via `importlib.import_module()`** with a
   module-name string built from a dict (`{"merge": ("panels.merge", "MergePanel"), ...}`) — a
   dynamic import PyInstaller's static analysis can't see, so `panels/` was never bundled at all.
2. **First attempted fix (`hiddenimports=YT_DLP_IMPORTS + collect_submodules('panels')`) silently
   did nothing.** `collect_submodules()` imports the named package using whatever is on `sys.path`
   *at the moment it's called* — but `pathex` (which would put `gui/`, where `panels/` lives, on
   `sys.path`) is only applied later, inside the `Analysis(...)` constructor. So
   `collect_submodules('panels')` returned `[]` with no error, and a rebuild without `--clean` just
   reused PyInstaller's stale TOC cache, masking the no-op fix as a success on first inspection.
   **Real fix:** `sys.path.insert(0, SPECPATH)` near the top of `gui/vfast.spec`, *before* the
   `collect_submodules('panels')` call. Confirmed by grepping `panels` out of
   `build/vfast/Analysis-00.toc` post-build (14 matches, all 10 panel submodules present).

**Lesson for any future dynamic-import hiddenimports in this spec:** `collect_submodules()` needs
the target package importable from the *current* `sys.path` at spec-execution time — for anything
living under `gui/` (not an installed site-package like `yt_dlp`), that means `sys.path.insert(0,
SPECPATH)` first. And after editing `hiddenimports`/spec logic, always rebuild with
`--clean` (or manually `rm -rf build/vfast dist/vfast.exe`) — `--noconfirm` alone can silently keep
a stale cached build.

## Change log

- 2026-09-12: first end-to-end verified build of `dist/vfast.exe` + `vfast-setup.exe`; fixed the
  three bugs above; wired in the app icon; created `.gitignore`.
- 2026-09-12 (later): found and fixed the `panels/` frozen-exe `ModuleNotFoundError` above (two
  stacked bugs: dynamic `importlib.import_module` invisible to static analysis, then a
  `collect_submodules` sys.path-timing no-op in the first attempted fix). Verified via TOC grep and
  a real exe launch (stayed running past a 6s timeout instead of crashing immediately).
- 2026-10-14 18:18: Rebuilt `dist/vfast.exe` (`pyinstaller gui/vfast.spec --noconfirm --clean --distpath dist --workpath build`, ~3.5 min) and `vfast-setup.exe` (makensis) after the ICO fix; exe now embeds 7 RT_ICON images. Includes the panels, loading overlay and layout pass. See [[app-icon]].
