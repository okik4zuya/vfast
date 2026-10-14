# vfast

A Windows video-processing toolkit: a simple desktop front-end for **ffmpeg** and **mpv**. Pick a
project folder, choose a tool from the sidebar, run. No command line needed.

## Features

| Tool | What it does |
|---|---|
| Merge | Join several videos into one |
| Speed | Speed up or slow down a video |
| Add / Remove / Extract Audio | Replace, strip or pull out the audio track |
| Denoise | Reduce background noise (RNNoise) |
| Trim | Keep a time range, with a live mpv preview |
| Cut | Remove one or more segments, with a live mpv preview and timeline |
| Overlay | Censor (box, blur, pixelate), add text or a logo, or mute, for a time range |
| Screen Record | Capture the screen and microphone |
| Download | Fetch videos with yt-dlp |

Everything runs locally. The network is only used by the Download panel.

## Install

Download `vfast-setup.exe` and run it, or run from source (below). Windows 10/11, 64-bit.

## Run from source

Requirements: Python 3.11+ and the ffmpeg/mpv binaries (see below).

```
python -m venv venv-gui
venv-gui\Scripts\pip install -r gui\requirements.txt
venv-gui\Scripts\python gui\main.py [project-folder]
```

### Bundled binaries (not in this repo)

`ffmpeg.exe`, `ffprobe.exe`, `ffplay.exe` and `mpv.exe` are too large for git. Download them and
place them in `bin/`:

- ffmpeg / ffprobe / ffplay: https://www.gyan.dev/ffmpeg/builds/ (full build)
- mpv: https://mpv.io/installation/

The RNNoise denoise model is already included at `bin/models/rnnoise-general.rnnn`.

## Build the installer

From the repo root:

```
venv-gui\Scripts\pip install -r gui\requirements-build.txt
venv-gui\Scripts\pyinstaller gui\vfast.spec --noconfirm --clean --distpath dist --workpath build
makensis gui\installer.nsi
```

This produces `dist\vfast.exe` and `vfast-setup.exe` (needs [NSIS](https://nsis.sourceforge.io/)).
The app version lives in one place, `gui/VERSION`; the About tab, the installer and the exe all
read it.

## Layout

| Path | Holds |
|---|---|
| `gui/` | The app (customtkinter): `app.py`, `panels/`, `widgets/`, `core/` (ffmpeg/mpv logic) |
| `bin/` | ffmpeg, mpv and the denoise model (binaries are git-ignored) |
| `assets/icon/` | App icon (SVG source, ICO, generator script) |
| `modules/` | Small Python helpers for transcription |
| `legacy/` | The original batch-script versions (`vfast.bat` to `vfast_v0.8.bat`), kept for history |

## Credits

[FFmpeg](https://ffmpeg.org), [mpv](https://mpv.io), [yt-dlp](https://github.com/yt-dlp/yt-dlp),
[RNNoise](https://github.com/xiph/rnnoise), [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).
Bundled third-party tools keep their own licenses.
