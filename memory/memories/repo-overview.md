---
name: repo-overview
description: What vfast is, its subprojects, and known issues found on first analysis
metadata:
  type: project
  tier: T1
  created: 2026-09-11 10:48
  updated: 2026-09-11 10:48
---

# Repo Overview

vfast is a Windows batch-script video-processing toolkit built around bundled `ffmpeg`/`ffprobe`/
`ffplay`/`mpv` binaries (`bin/`), driven by `vfast_v0.8.bat` (current version) — a menu-driven CLI:
merge, change speed, add/remove/extract audio, trim, cut, screen recording, transcribe.

## Layout

| Path | Holds |
|---|---|
| `vfast_v0.8.bat` | current entry point / menu script |
| `legacy/` | superseded versions `vfast.bat` .. `vfast_v0.7.bat` — history, not active code |
| `bin/` | ffmpeg, ffprobe, ffplay, mpv binaries + mpv register/unregister scripts |
| `modules/` | `transcribe.py`, `transcribe_yt.py` — Python helpers called from the .bat menu |
| `venv/` | Python venv used by `modules/` and by `yt2s/` (one level up) |
| `yt2s/` | separate subproject: YouTube-to-shorts pipeline (download → transcribe → AI plan → trim → clip). Has its own `CLAUDE.md`/`README.md` — read those directly rather than duplicating here. |
| `device_list.txt` | `ffmpeg -devices`-style dump — looks like a scratch/debug output, not source |
| `gui/` | customtkinter GUI replacement for `vfast_v0.8.bat` — see [[gui-rewrite]] |
| `venv-gui/` | dedicated venv for `gui/` (customtkinter + yt-dlp only, no whisper/torch) |

## Known issues (yt2s, from its own CLAUDE.md)

- `generate_transcript.py` writes `shorts_transcription.json` to CWD, not the workspace (bug)
- `core/execute.py` is a stub, imported but never called
- `core/clips.py` (`create_clips`) implemented but not wired into the menu
- `config.json`'s `ai_model` field is unused (model chosen interactively instead)
- Naming inconsistency: menu option 2 calls `research_flow`, which actually transcribes

## Change log

- 2026-09-11: Initial repo analysis and memory scaffold created.
