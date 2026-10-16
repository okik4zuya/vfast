import os
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk
from PIL import Image, ImageTk

from core import overlayspec, settings
from core import spec as specmod
from core.media import list_videos, format_duration
from core.cut import parse_time
from core.overlay import EFFECT_TYPES, overlay_media, preview_frame
from widgets.delete_control import confirm_delete, make_delete_button
from widgets.spec_bar import SpecBanner, ask_load_path, new_session, spec_menu
from widgets.video_pane import VideoPane

if TYPE_CHECKING:
    from app import App

_SPEED_TIERS = {
    "fast": ("veryfast", 23),
    "balanced": ("fast", 18),
    "high": ("slow", 16),
}

# Per-type entry layout: one inner list per visual line, each item (key, entry width).
_XYWH = [("x", 46), ("y", 46), ("w", 46), ("h", 46)]
_LAYOUT = {
    "box": [_XYWH, [("color", 90)]],
    "blur": [_XYWH, [("strength", 60)]],
    "pixelate": [_XYWH, [("block", 60)]],
    "text": [[("text", 230)], [("x", 46), ("y", 46), ("size", 46)], [("color", 80), ("bg", 90)]],
    "image": [[("path", 200)], _XYWH],
    "mute": [],
}
_DEFAULTS = {"strength": "20", "block": "16", "size": "36"}
_NUMERIC = {"x", "y", "w", "h", "strength", "block", "size"}
_OPTIONAL = {"bg", "color"}  # may stay empty (engine default); image w/h are optional too
_GEOMETRY_TYPES = ("box", "blur", "pixelate")
_ADD_LABEL = "+ Add effect"
_BAD = "#dc2626"


def _short_time(raw: str) -> str:
    try:
        t = parse_time(raw)
    except ValueError:
        return raw
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:04.1f}" if h else f"{int(m):02d}:{s:04.1f}"


class EffectRow(ctk.CTkFrame):
    """One effect as an accordion item: a one-line summary (click to select) plus a body with the
    editable fields that is only shown while the row is selected."""

    def __init__(self, parent, panel: "OverlayPanel", spec: dict | None = None):
        super().__init__(parent, corner_radius=6)
        self.panel = panel
        self.index = 0
        self.entries: dict[str, ctk.CTkEntry] = {}
        self._default_border = ctk.ThemeManager.theme["CTkEntry"]["border_color"]
        spec = spec or {}

        # ---- summary line ----
        self.summary = ctk.CTkFrame(self, fg_color="transparent")
        self.summary.pack(fill="x", padx=6, pady=4)
        self.name_lbl = ctk.CTkLabel(self.summary, text="", width=84, anchor="w",
                                     font=ctk.CTkFont(weight="bold"))
        self.name_lbl.pack(side="left")
        make_delete_button(self.summary, lambda: panel.request_delete(self)).pack(side="right")
        ctk.CTkButton(self.summary, text="⧉", width=26,
                      command=lambda: panel.duplicate_row(self)).pack(side="right", padx=(0, 22))
        self.info_lbl = ctk.CTkLabel(self.summary, text="", anchor="w")
        self.info_lbl.pack(side="left", fill="x", expand=True)
        for w in (self, self.summary, self.name_lbl, self.info_lbl):
            w.bind("<Button-1>", lambda e: panel.select_row(self))

        # ---- body (shown only when selected) ----
        # One flow of small label+entry groups that wraps to the available width, so wide panes use
        # their horizontal room instead of stacking every field on its own line.
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.flow = ctk.CTkFrame(self.body, fg_color="transparent")
        self.flow.pack(fill="x")
        self.flow.bind("<Configure>", lambda e: self._reflow())
        self._flow_sig = None
        self.fixed_groups: list = []
        self.field_groups: list = []

        g = self._group(self.fixed_groups)
        ctk.CTkLabel(g, text="type").pack(side="left", padx=(0, 3))
        self.type_menu = ctk.CTkOptionMenu(g, values=list(EFFECT_TYPES), width=96,
                                           command=lambda _: self._type_changed())
        self.type_menu.set(spec.get("type", "box"))
        self.type_menu.pack(side="left")
        self.start = self._time_entry("start", True, spec.get("start"))
        self.end = self._time_entry("end", False, spec.get("end"))
        self._rebuild_fields(spec)
        self.refresh_summary()
        self.initial = self.raw()  # to tell later whether the user has edited this row

    def is_untouched(self) -> bool:
        return self.raw() == self.initial

    def _group(self, bucket: list) -> ctk.CTkFrame:
        g = ctk.CTkFrame(self.flow, fg_color="transparent")
        bucket.append(g)
        return g

    def _reflow(self):
        # place(), not grid(): grid would align the groups of different lines into shared columns.
        width = self.flow.winfo_width()
        groups = self.fixed_groups + self.field_groups
        sig = (width, len(groups))
        if width <= 1 or sig == self._flow_sig:
            return
        self._flow_sig = sig
        self.flow.update_idletasks()
        x = y = rowh = 0
        for g in groups:
            gw, gh = g.winfo_reqwidth(), g.winfo_reqheight()
            if x + gw > width and x > 0:
                y += rowh + 4
                x = rowh = 0
            g.place(x=x, y=y)
            x += gw + 10
            rowh = max(rowh, gh)
        self.flow.configure(height=y + rowh)

    def _time_entry(self, label: str, is_start: bool, value) -> ctk.CTkEntry:
        g = self._group(self.fixed_groups)
        ctk.CTkLabel(g, text=label).pack(side="left", padx=(0, 3))
        e = ctk.CTkEntry(g, placeholder_text="whole video", width=108)
        if value not in (None, ""):
            e.insert(0, format_duration(float(value)) if isinstance(value, (int, float)) else str(value))
        e.pack(side="left", padx=(0, 3))
        e.bind("<KeyRelease>", lambda ev: self._changed())
        e.bind("<FocusOut>", lambda ev: self._changed())
        ctk.CTkButton(g, text="⏺", width=28,
                      command=lambda: self.panel.set_time(self, is_start)).pack(side="left")
        return e

    # ---- fields ----
    def _type_changed(self):
        self._rebuild_fields()
        self.refresh_summary()
        self.panel.boxes_changed()

    def _rebuild_fields(self, spec: dict | None = None):
        old = {k: e.get() for k, e in self.entries.items()}
        for g in self.field_groups:
            g.destroy()
        self.field_groups = []
        self.entries = {}
        kind = self.type_menu.get()
        for items in _LAYOUT[kind]:
            for key, width in items:
                g = self._group(self.field_groups)
                ctk.CTkLabel(g, text=key).pack(side="left", padx=(0, 3))
                e = ctk.CTkEntry(g, width=width)
                default = "white" if (kind, key) == ("text", "color") else                     "black" if (kind, key) == ("box", "color") else _DEFAULTS.get(key, "")
                val = (spec or {}).get(key, old.get(key, default))
                if (kind, key) == ("text", "color") and val == "black" and not spec:
                    val = "white"  # color carried over from a box row's black default
                if val not in (None, ""):
                    e.insert(0, str(val))
                e.pack(side="left")
                e.bind("<KeyRelease>", lambda ev: self._changed())
                e.bind("<FocusOut>", lambda ev: self._changed())
                self.entries[key] = e
                if kind == "image" and key == "path":
                    ctk.CTkButton(g, text="…", width=28, command=self._browse_image).pack(side="left", padx=(3, 0))
        if kind == "mute":
            g = self._group(self.field_groups)
            ctk.CTkLabel(g, text="audio silenced between start and end", text_color="gray60").pack(side="left")
        self._flow_sig = None
        self.after_idle(self._reflow)

    def _browse_image(self):
        path = filedialog.askopenfilename(title="Overlay image",
                                          filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.entries["path"].delete(0, "end")
            self.entries["path"].insert(0, path)
            self._changed()

    def _changed(self):
        self.refresh_summary()
        self.panel.boxes_changed()

    # ---- state ----
    def set_index(self, i: int):
        self.index = i
        self.refresh_summary()

    def set_selected(self, on: bool):
        if on:
            self.body.pack(fill="x", padx=8, pady=(0, 8))
            self.configure(border_width=2, border_color="#2563eb")
        else:
            self.body.pack_forget()
            self.configure(border_width=0)

    def refresh_summary(self):
        kind = self.type_menu.get()
        self.name_lbl.configure(text=f"{self.index + 1}  {kind}")
        s, e = self.start.get().strip(), self.end.get().strip()
        when = "whole video" if not (s or e) else f"{_short_time(s) if s else '0'} → {_short_time(e) if e else 'end'}"
        warn = False
        if kind in _GEOMETRY_TYPES:
            g = self.geometry()
            detail = f"({g[0]},{g[1]}) {g[2]}×{g[3]}" if g else "(region not set)"
            warn = g is None
        elif kind == "text":
            t = self.entries["text"].get().strip()
            detail = f"“{t[:16]}{'…' if len(t) > 16 else ''}”" if t else "(no text)"
            warn = not t
        elif kind == "image":
            p = self.entries["path"].get().strip()
            detail = os.path.basename(p) if p else "(no file)"
            warn = not p
        else:
            detail = ""
            warn = not (s or e)
        self.info_lbl.configure(text=f"{when}   {detail}".strip(),
                                text_color="#d97706" if warn else ("gray10", "gray90"))

    def set_times(self, start: str | None = None, end: str | None = None):
        for widget, val in ((self.start, start), (self.end, end)):
            if val is not None:
                widget.delete(0, "end")
                widget.insert(0, val)
        self._changed()

    def set_geometry(self, **vals):
        """Fill x/y/w/h (only the ones this effect type has)."""
        for k, v in vals.items():
            if k in self.entries:
                self.entries[k].delete(0, "end")
                self.entries[k].insert(0, str(int(v)))
        self.refresh_summary()

    def geometry(self) -> tuple[int, int, int, int] | None:
        try:
            return tuple(int(float(self.entries[k].get())) for k in ("x", "y", "w", "h"))
        except (KeyError, ValueError):
            return None

    def active_at(self, t: float) -> bool:
        try:
            s = parse_time(self.start.get().strip()) if self.start.get().strip() else 0.0
            e = parse_time(self.end.get().strip()) if self.end.get().strip() else float("inf")
        except ValueError:
            return True
        return s <= t <= e

    def raw(self) -> dict:
        """Current values as strings, no validation (used to duplicate a row)."""
        d = {"type": self.type_menu.get(), "start": self.start.get().strip(), "end": self.end.get().strip()}
        d.update({k: e.get() for k, e in self.entries.items()})
        return d

    def _mark(self, widget, bad: bool):
        widget.configure(border_color=_BAD if bad else self._default_border)

    def to_dict(self) -> dict:
        """Raises ValueError with a readable message and marks the offending field red."""
        for w in [self.start, self.end, *self.entries.values()]:
            self._mark(w, False)
        kind = self.type_menu.get()
        fx: dict = {"type": kind}

        def fail(widget, msg):
            self._mark(widget, True)
            raise ValueError(msg)

        for key, widget in (("start", self.start), ("end", self.end)):
            raw = widget.get().strip()
            if raw:
                try:
                    parse_time(raw)
                except ValueError:
                    fail(widget, f"'{key}' is not a valid time: {raw!r}")
                fx[key] = raw
        if kind == "mute" and not (fx.get("start") or fx.get("end")):
            fail(self.start, "mute needs start and/or end")
        for items in _LAYOUT[kind]:
            for key, _ in items:
                widget = self.entries[key]
                raw = widget.get().strip()
                if not raw:
                    if key in _OPTIONAL or (kind == "image" and key in ("w", "h")):
                        continue
                    fail(widget, f"{kind}: '{key}' is empty")
                if key in _NUMERIC:
                    try:
                        fx[key] = int(float(raw))
                    except ValueError:
                        fail(widget, f"{kind}: '{key}' must be a number, got {raw!r}")
                else:
                    fx[key] = raw
        return fx


class OverlayPanel(ctk.CTkFrame):
    """Thin front end over core/overlay.py. Same two-pane layout as CutPanel (the mpv preview is a
    foreign HWND, so it must stay off any Canvas-backed scrolling container — see CutPanel).

    Left pane: watch and find times (video picker, mpv, transport). Right pane: edit — a still-frame
    canvas on top (Tk widgets cannot be drawn over the mpv window, so boxes are dragged here and
    converted back to video pixels), then the effect list (accordion: only the selected row is open)."""

    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._running = False
        self.videos = []
        self.rows: list[EffectRow] = []
        self.selected: EffectRow | None = None
        self._frame_img: Image.Image | None = None  # last grabbed frame, native resolution
        self._frame_tk = None
        self._frame_t = 0.0
        self._frame_scale = 1.0
        self._drag_start: tuple[int, int] | None = None
        self.session = new_session(self, overlayspec.OverlaySession)
        self._build()
        self._refresh_files()

    # ---- layout ----
    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        paned = tk.PanedWindow(self, orient="horizontal", sashwidth=6, sashrelief="raised",
                               bd=0, bg=self.winfo_toplevel().cget("bg"))
        paned.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

        pane = VideoPane(paned, self._on_video_change,
                         hint="Find the moment here, then use ⏺ next to an effect's start/end "
                              "to take the current time.")
        paned.add(pane, minsize=260, width=400, stretch="always")
        self.video_menu = pane.video_menu
        self.mpv_embed = pane.mpv_embed

        right = ctk.CTkScrollableFrame(paned, fg_color="transparent")
        right.grid_columnconfigure(0, weight=1)
        paned.add(right._parent_frame, minsize=260, width=340, stretch="always")

        head_row = ctk.CTkFrame(right, fg_color="transparent")
        head_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(head_row, text="Overlay", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        self.spec_menu = spec_menu(head_row, self._save_spec, self._load_spec, self._reset_spec)
        self.spec_menu.pack(side="right")

        self.banner = SpecBanner(right, on_keep=self._keep_spec)
        self.banner.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.banner.grid_remove()

        self.canvas = tk.Canvas(right, height=150, bg="#202020", highlightthickness=0, cursor="crosshair")
        self.canvas.grid(row=2, column=0, sticky="ew")
        self.canvas.bind("<Configure>", lambda e: self._render_canvas())
        self.canvas.bind("<ButtonPress-1>", self._drag_begin)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        fbar = ctk.CTkFrame(right, fg_color="transparent")
        fbar.grid(row=3, column=0, sticky="ew", pady=(4, 8))
        ctk.CTkButton(fbar, text="Grab frame", width=90, command=lambda: self._show_frame(False)).pack(
            side="left", padx=(0, 6))
        ctk.CTkButton(fbar, text="Preview effects", width=110, command=lambda: self._show_frame(True)).pack(
            side="left", padx=(0, 8))
        self.coord_label = ctk.CTkLabel(fbar, text="", text_color="gray60", anchor="w")
        self.coord_label.pack(side="left")

        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=4, column=0, sticky="ew")
        self.effects_label = ctk.CTkLabel(head, text="Effects (0)", font=ctk.CTkFont(weight="bold"))
        self.effects_label.pack(side="left")
        self.add_menu = ctk.CTkOptionMenu(head, values=list(EFFECT_TYPES), width=120,
                                          command=self._add_from_menu)
        self.add_menu.set(_ADD_LABEL)
        self.add_menu.pack(side="right")

        self.rows_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.rows_frame.grid(row=5, column=0, sticky="ew", pady=(4, 0))
        self.rows_frame.grid_columnconfigure(0, weight=1)

        speed = ctk.CTkFrame(right, fg_color="transparent")
        speed.grid(row=6, column=0, pady=(10, 0), sticky="w")
        ctk.CTkLabel(speed, text="Quality:").pack(side="left", padx=(0, 10))
        saved = settings.get("overlay_quality", "balanced")
        self.speed_var = ctk.StringVar(value=saved if saved in _SPEED_TIERS else "balanced")
        self.speed_var.trace_add("write", lambda *_: settings.set("overlay_quality", self.speed_var.get()))
        for label, val in (("Fast", "fast"), ("Balanced", "balanced"), ("High", "high")):
            ctk.CTkRadioButton(speed, text=label, variable=self.speed_var, value=val, width=20).pack(
                side="left", padx=(0, 10))

        out = ctk.CTkFrame(right, fg_color="transparent")
        out.grid(row=7, column=0, pady=(8, 4), sticky="ew")
        out.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(out, text="Output:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(out)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")

        runs = ctk.CTkFrame(right, fg_color="transparent")
        runs.grid(row=8, column=0, pady=(8, 4), sticky="ew")
        ctk.CTkButton(runs, text="Run Overlay", width=96, command=self._run_full).pack(side="right")
        ctk.CTkButton(runs, text="Test 10s", width=80, command=self._run_test).pack(side="right", padx=(0, 6))

    # ---- video / rows ----
    def _refresh_files(self):
        project_dir = self.app.project.project_dir
        self.videos = list_videos(project_dir) if project_dir else []
        self.video_menu.configure(values=[v.name for v in self.videos] or ["(no videos found)"])
        self.video_menu.set(self.app.preferred_video(self.videos))
        self._on_video_change()

    def _current_video(self):
        name = self.video_menu.get()
        media = next((v for v in self.videos if v.name == name), None)
        if media:
            self.app.selected_video = media.path  # survives switching panels
        return media

    def _on_video_change(self):
        self._persist()  # whatever is on screen belongs to the video being left
        media = self._current_video()
        self.session.switch_video(media.path if media else None)
        self._frame_img = None
        with self.session.applying():
            self._sync_widgets()
        self._render_canvas()
        if media:
            fp = specmod.fingerprint(media.path, media.duration, media.width, media.height)
            if fp:
                self.session.apply_probe(self.session.generation, fp)
        self._show_issues()
        self.output_entry.delete(0, "end")
        if media:
            base, ext = os.path.splitext(media.name)
            self.output_entry.insert(0, f"{base}_overlay{ext}")
            self.mpv_embed.set_aspect(media.width, media.height)
            try:
                self.mpv_embed.load(media.path)
            except OSError as e:
                self.app.log(f"[Overlay] Failed to start mpv preview: {e}")
        else:
            self.mpv_embed.stop()

    def _add_from_menu(self, kind: str):
        self.add_menu.set(_ADD_LABEL)
        self.add_row({"type": kind})

    def add_row(self, spec: dict | None = None) -> EffectRow:
        row = EffectRow(self.rows_frame, self, spec)
        self.rows.append(row)
        self._renumber()
        self.select_row(row)
        self._persist()
        return row

    def duplicate_row(self, row: EffectRow):
        self.add_row(row.raw())

    def _clear_rows(self):
        for r in self.rows:
            r.destroy()
        self.rows = []
        self.selected = None
        self._renumber()

    def request_delete(self, row: EffectRow):
        """Confirm first, unless the row is still exactly as it was created."""
        if not row.is_untouched() and not confirm_delete(
                "Delete effect", f"Delete effect {row.index + 1} ({row.type_menu.get()}, "
                                 f"{row.info_lbl.cget('text')})?", parent=self.winfo_toplevel()):
            return
        self.delete_row(row)

    def delete_row(self, row: EffectRow):
        if row not in self.rows:
            return
        self.rows.remove(row)
        row.destroy()
        if self.selected is row:
            self.selected = None
        self._renumber()
        if self.rows and self.selected is None:
            self.select_row(self.rows[0])
        self._draw_boxes()
        self._persist()

    def _renumber(self):
        for i, r in enumerate(self.rows):
            r.grid(row=i, column=0, sticky="ew", pady=3)
            r.set_index(i)
        self.effects_label.configure(text=f"Effects ({len(self.rows)})")

    def select_row(self, row: EffectRow):
        self.selected = row
        for r in self.rows:
            r.set_selected(r is row)
        self._draw_boxes()

    def boxes_changed(self):
        self._draw_boxes()
        self._persist()

    def set_time(self, row: EffectRow, is_start: bool):
        self.select_row(row)
        if not self.mpv_embed.is_running():
            self.app.log("[Overlay] mpv preview is not running.")
            return

        def on_result(seconds):
            if seconds is None:
                self.app.log("[Overlay] Could not read mpv position — try again.")
                return
            s = format_duration(seconds)
            row.set_times(start=s if is_start else None, end=None if is_start else s)

        self.mpv_embed.get_time_pos_async(on_result)

    # ---- spec ----
    def collect_effects(self) -> list[dict] | None:
        """All rows as engine dicts, or None (after logging why and opening the bad row)."""
        out = []
        for i, r in enumerate(self.rows):
            try:
                out.append(r.to_dict())
            except ValueError as e:
                self.select_row(r)
                self.app.log(f"[Overlay] Effect {i + 1}: {e}")
                return None
        return out

    # ---- spec (<video>.overlay.json) ----
    @staticmethod
    def _row_spec(row: "EffectRow") -> dict:
        """One row as saved: exactly what is on screen (half-finished rows included), no validation."""
        return overlayspec.clean_effect(row.raw())

    def _sync_widgets(self):
        """spec -> widgets. Call inside `session.applying()` so nothing writes back."""
        self._clear_rows()
        for fx in self.session.spec["effects"]:
            self.add_row(fx)

    def _persist(self):
        """widgets -> spec."""
        if self.session.video is None:
            return
        try:
            effects = [self._row_spec(r) for r in self.rows]
        except tk.TclError:
            return  # widgets already gone
        self.session.update(effects=effects)
        self.session.revalidate()
        self._show_issues()

    def _show_issues(self):
        s = self.session
        msgs = list(s.warnings) + [i.message for i in s.issues] + ([s.save_error] if s.save_error else [])
        self.banner.show(msgs, can_keep=any(i.kind in ("file_changed", "resolution_changed") for i in s.issues))

    def _keep_spec(self):
        self.session.accept_source()
        self._show_issues()

    def _reset_spec(self):
        if not self.session.video:
            return
        if self.rows and not confirm_delete("Reset spec", f"Remove all {len(self.rows)} effect(s) of this video?",
                                            parent=self.winfo_toplevel()):
            return
        self.session.reset()
        with self.session.applying():
            self._sync_widgets()
        self._draw_boxes()
        self._show_issues()

    def _save_spec(self):
        """Write now, next to the video, named after it (same file the autosave keeps up to date)."""
        if not self.session.video:
            self.app.log("[Overlay] No video selected.")
            return
        self._persist()
        path = self.session.default_export_path()
        try:
            self.session.export_to(path)
            self.app.log(f"[Overlay] Spec saved: {path}")
        except OSError as e:
            self.app.log(f"[Overlay] Could not save spec: {e}")

    def _load_spec(self):
        if not self.session.video:
            self.app.log("[Overlay] No video selected.")
            return
        path = ask_load_path(self.session.video, "Overlay")
        if not path:
            return
        ok, warns = self.session.import_from(path)
        for w in warns:
            self.app.log(f"[Overlay] {os.path.basename(path)}: {w}")
        if ok:
            with self.session.applying():
                self._sync_widgets()
            self._draw_boxes()
            self.app.log(f"[Overlay] Loaded {len(self.rows)} effect(s) from {os.path.basename(path)}")
        self._show_issues()

    def destroy(self):
        # Navigation destroys the panel: persist what is on screen (an entry may not have lost focus yet).
        try:
            self._persist()
            self.session.flush()
        except Exception:
            pass
        super().destroy()

    # ---- frame canvas ----
    def _show_frame(self, with_effects: bool):
        media = self._current_video()
        if not media:
            self.app.log("[Overlay] No video selected.")
            return
        effects = []
        if with_effects:
            effects = self.collect_effects()
            if effects is None:
                return

        def on_time(t):
            if t is None:
                self.app.log("[Overlay] Could not read mpv position — try again.")
                return

            def worker():
                png = os.path.join(tempfile.gettempdir(), f"vfast_overlay_frame_{os.getpid()}.png")
                ok = preview_frame(media.path, t, png, effects, grid=False, log=lambda m: None)
                if not ok:
                    self.app.log("[Overlay] Frame extraction failed.")
                    return
                img = Image.open(png)
                img.load()
                self.after(0, lambda: self._set_frame(img, t))

            threading.Thread(target=worker, daemon=True).start()

        self.mpv_embed.get_time_pos_async(on_time)

    def _set_frame(self, img: Image.Image, t: float):
        self._frame_img = img
        self._frame_t = t
        self.coord_label.configure(text=f"{format_duration(t)} · {img.width}×{img.height}")
        self._render_canvas()

    def _render_canvas(self):
        self.canvas.delete("all")
        cw = max(self.canvas.winfo_width(), 50)
        if self._frame_img is None:
            self.canvas.configure(height=150)
            self.canvas.create_text(cw / 2, 75, fill="gray60", justify="center",
                                    text="Press “Grab frame”, then drag\na region to fill the selected effect")
            return
        img = self._frame_img
        self._frame_scale = cw / img.width
        ch = max(1, int(img.height * self._frame_scale))
        self.canvas.configure(height=ch)
        self._frame_tk = ImageTk.PhotoImage(img.resize((cw, ch), Image.LANCZOS))
        self.canvas.create_image(0, 0, image=self._frame_tk, anchor="nw")
        self._draw_boxes()

    def _draw_boxes(self):
        """Selected effect's region in red; other effects active at the frame time dimmed/dashed."""
        self.canvas.delete("box")
        if self._frame_img is None:
            return
        s = self._frame_scale
        for r in self.rows:
            if r.type_menu.get() not in _GEOMETRY_TYPES and r is not self.selected:
                continue
            g = r.geometry()
            if not g or (r is not self.selected and not r.active_at(self._frame_t)):
                continue
            x, y, w, h = g
            if r is self.selected:
                self.canvas.create_rectangle(x * s, y * s, (x + w) * s, (y + h) * s,
                                             outline="#ff3b30", width=2, tags="box")
            else:
                self.canvas.create_rectangle(x * s, y * s, (x + w) * s, (y + h) * s,
                                             outline="#9ca3af", dash=(4, 3), tags="box")

    def _to_video(self, cx: float, cy: float) -> tuple[int, int]:
        img = self._frame_img
        x = min(max(int(round(cx / self._frame_scale)), 0), img.width)
        y = min(max(int(round(cy / self._frame_scale)), 0), img.height)
        return x, y

    def _drag_begin(self, e):
        if self._frame_img is None:
            return
        self._drag_start = (e.x, e.y)

    def _drag_move(self, e):
        if self._drag_start is None:
            return
        self.canvas.delete("drag")
        x0, y0 = self._drag_start
        self.canvas.create_rectangle(x0, y0, e.x, e.y, outline="#ff3b30", width=2, tags="drag")

    def _drag_end(self, e):
        if self._drag_start is None:
            return
        x0, y0 = self._to_video(*self._drag_start)
        x1, y1 = self._to_video(e.x, e.y)
        self._drag_start = None
        self.canvas.delete("drag")
        row = self.selected
        if row is None:
            self.app.log("[Overlay] Add or select an effect first.")
            return
        x, y = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0), abs(y1 - y0)
        if w < 2 and h < 2:  # a click, not a drag: only place x/y (text/image anchor)
            row.set_geometry(x=x, y=y)
        else:
            row.set_geometry(x=x, y=y, w=w, h=h)
        self.coord_label.configure(text=f"x{x} y{y} {w}×{h}")
        self._draw_boxes()
        self._persist()

    # ---- run ----
    def _start(self, test: bool):
        if self._running:
            return
        if not self.app.ensure_project_dir():
            return
        media = self._current_video()
        if not media:
            self.app.log("[Overlay] No video selected.")
            return
        effects = self.collect_effects()
        if effects is None:
            return
        if not effects:
            self.app.log("[Overlay] Add at least one effect.")
            return
        name = self.output_entry.get().strip()
        if not name:
            self.app.log("[Overlay] Output filename required.")
            return
        base, ext = os.path.splitext(name)
        output_path = os.path.join(self.app.project.project_dir, f"{base}_test{ext}" if test else name)
        preset, crf = _SPEED_TIERS[self.speed_var.get()]

        def begin(window):
            self._persist()
            self.session.flush()   # the file on disk is exactly what gets rendered
            self._running = True

            def worker():
                try:
                    ok = overlay_media(media.path, effects, output_path, log=self.app.log,
                                       preset=preset, crf=crf, window=window)
                    if ok:
                        self.app.log_result(f"[Overlay] Done: {os.path.basename(output_path)}", output_path)
                finally:
                    self._running = False

            threading.Thread(target=worker, daemon=True).start()

        if not test:
            begin(None)
            return

        def on_time(t):
            if t is None:
                self.app.log("[Overlay] Could not read mpv position — try again.")
                return
            end = min(t + 10.0, media.duration) if media.duration else t + 10.0
            begin((t, end))

        self.mpv_embed.get_time_pos_async(on_time)

    def _run_test(self):
        self._start(test=True)

    def _run_full(self):
        self._start(test=False)
