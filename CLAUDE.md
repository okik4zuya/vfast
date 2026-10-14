# vfast — Project Instructions

Windows video-processing toolkit (ffmpeg/mpv wrapper + `yt2s` YouTube-to-shorts subproject). Not
an ARTi research project — only ARTi's `memory/` folder *convention* is used here for persistent
project memory, project-local (not the default `~/.claude/projects/.../memory/`).

Read every session: `memory/MEMORY.md`, `memory/todo-list.md`, `memory/status.md`.

`yt2s/` is a subproject with its own `CLAUDE.md` and `README.md` — read those directly when
working inside `yt2s/` rather than duplicating their content here.

## Memory rules

- `memory/` holds exactly three files flat: `MEMORY.md`, `todo-list.md`, `status.md`. Every topic
  file goes in `memory/memories/`, read on demand.
- `MEMORY.md` = index, pointers only, one line each — never content.
- `todo-list.md` = contiguous `- [ ]`/`- [x]` items only, no narrative.
- `status.md` = narrative: one "Current state" block overwritten in place each session (never
  stacked), archive below.
- One file per topic — update it rather than creating a near-duplicate; read it before advising on
  that topic. Link with `[[slug]]`, don't restate across files.
- **Timestamps:** run a date command, never guess. Set `created` on creation, `updated` on every
  write, add one `## Change log` line.

Frontmatter for every memory file:

```
---
name: kebab-case-slug
description: one-line summary, specific enough to judge relevance later
metadata:
  type: project | user | feedback | reference
  tier: T0 | T1
  created: yyyy-mm-dd HH:mm
  updated: yyyy-mm-dd HH:mm
---
```

...content, then `## Change log` at the bottom.

## Session end

Fired by any phrasing meaning "we're done" — "update memory", "update status", "end session":

1. Update the relevant memory file(s).
2. Overwrite `status.md`'s "Current state" block.
3. Check off / add `todo-list.md` items.
