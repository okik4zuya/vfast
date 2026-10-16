import os
import shutil
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk

from core import effects, settings
from core import spec as specmod
from core.media import has_audio_stream, list_videos, video_fps
from core.render import SPEED_TIERS, render
from widgets.spec_bar import ask_load_path, spec_menu
from widgets.tooltip import Tooltip
from widgets.video_pane import VideoPane

if TYPE_CHECKING:
    from app import App

_SECTIONS = (
    ("Format (pilih satu)", (effects.LAYOUT,)),
    ("Look & kualitas", (effects.LOOK,)),
    ("Gerak", (effects.ZOOM, effects.FADE)),
    ("Teks & logo", (effects.CAPTION, effects.WATERMARK)),
    ("Audio", (effects.AUDIO,)),
)
_PACK_PLACEHOLDER = "Pilih paket..."
_COPY_PLACEHOLDER = "Salin dari..."
_PREVIEW_DELAY_MS = 250
_RESOLUTION_KINDS = ("file_changed", "resolution_changed")


class EffectsPanel(ctk.CTkFrame):
    """Effects + saved Overlay effects + speed + audio, rendered in ONE ffmpeg pass (core/render.py).

    Widgets are only a view of `self.session.spec` (core/spec.py): they are filled from it by
    `_sync_widgets` and write back only through `session.update` on a user edit, so changing video or
    leaving the panel can never leak settings between videos. The panel is destroyed on every navigation;
    `destroy()` flushes the pending save."""

    def __init__(self, parent, app: "App"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.videos = []
        self.session = specmod.EffectsSession(self.after, self._cancel_after)
        self._vars: dict[str, ctk.BooleanVar] = {}
        self._boxes: dict[str, ctk.CTkCheckBox] = {}
        self._fps = "30"
        self._tmp: str | None = None
        self._preview_job = None
        self._output_dirty = False
        self._build()
        self._refresh_files()

    # ---- helpers ---------------------------------------------------------------------------
    def _cancel_after(self, handle):
        try:
            self.after_cancel(handle)
        except tk.TclError:
            pass

    def _after_safe(self, fn):
        try:
            self.after(0, fn)
        except (tk.TclError, RuntimeError):
            pass  # panel destroyed while a worker was running

    def _tmpdir(self) -> str:
        if self._tmp is None or not os.path.isdir(self._tmp):
            self._tmp = tempfile.mkdtemp(prefix="vfast_fx_")
        return self._tmp

    # ---- layout ----------------------------------------------------------------------------
    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        paned = tk.PanedWindow(self, orient="horizontal", sashwidth=6, sashrelief="raised",
                               bd=0, bg=self.winfo_toplevel().cget("bg"))
        paned.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

        pane = VideoPane(paned, self._on_video_change,
                         hint="Live preview shows format, look, zoom, caption and audio. Overlay "
                              "effects, logo, speed and fades show only in the 10s test render.")
        paned.add(pane, minsize=260, width=400, stretch="always")
        self.video_menu = pane.video_menu
        self.mpv_embed = pane.mpv_embed

        right = ctk.CTkScrollableFrame(paned, fg_color="transparent")
        right.grid_columnconfigure(0, weight=1)
        paned.add(right._parent_frame, minsize=260, width=340, stretch="always")

        r = 0
        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=r, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(head, text="Effects", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        self.spec_menu = spec_menu(head, self._save_spec, self._load_spec, self._reset_spec)
        self.spec_menu.pack(side="right")
        r += 1

        # banner: load warnings + validation issues (hidden when empty)
        self.banner = ctk.CTkFrame(right, fg_color=("#fde68a", "#78350f"), corner_radius=6)
        self.banner.grid(row=r, column=0, sticky="ew", pady=(0, 6))
        self.banner_label = ctk.CTkLabel(self.banner, text="", justify="left", anchor="w", wraplength=300,
                                         text_color=("#451a03", "#fef3c7"))
        self.banner_label.pack(fill="x", padx=8, pady=(6, 2))
        banner_btns = ctk.CTkFrame(self.banner, fg_color="transparent")
        banner_btns.pack(fill="x", padx=8, pady=(0, 6))
        self.keep_btn = ctk.CTkButton(banner_btns, text="Keep spec", width=80, command=self._keep_spec)
        self.keep_btn.pack(side="left", padx=(0, 6))
        ctk.CTkButton(banner_btns, text="Reset spec", width=80, command=self._reset_spec).pack(side="left")
        self.banner.grid_remove()
        r += 1

        pack_row = ctk.CTkFrame(right, fg_color="transparent")
        pack_row.grid(row=r, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(pack_row, text="Paket:").pack(side="left", padx=(0, 6))
        self.pack_menu = ctk.CTkOptionMenu(pack_row, values=list(effects.PACKS), width=170,
                                           command=self._apply_pack)
        self.pack_menu.set(_PACK_PLACEHOLDER)
        self.pack_menu.pack(side="left")
        r += 1

        for title, stages in _SECTIONS:
            ctk.CTkLabel(right, text=title, font=ctk.CTkFont(weight="bold")).grid(
                row=r, column=0, sticky="w", pady=(8, 2))
            r += 1
            grid = ctk.CTkFrame(right, fg_color="transparent")
            grid.grid(row=r, column=0, sticky="ew")
            for c in range(3):
                grid.grid_columnconfigure(c, weight=1, uniform=title)
            names = [n for n, p in effects.PRESETS.items() if p.stage in stages]
            for i, name in enumerate(names):
                var = ctk.BooleanVar(value=False)
                box = ctk.CTkCheckBox(grid, text=name, variable=var, width=20, checkbox_width=18,
                                      checkbox_height=18, command=lambda n=name: self._on_toggle(n))
                box.grid(row=i // 3, column=i % 3, sticky="w", pady=2)
                Tooltip(box, effects.PRESETS[name].desc)
                self._vars[name], self._boxes[name] = var, box
            r += 1

        # parameters for caption / watermark
        ctk.CTkLabel(right, text="Parameter", font=ctk.CTkFont(weight="bold")).grid(
            row=r, column=0, sticky="w", pady=(8, 2))
        r += 1
        params = ctk.CTkFrame(right, fg_color="transparent")
        params.grid(row=r, column=0, sticky="ew")
        params.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(params, text="caption").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.caption_entry = ctk.CTkEntry(params, placeholder_text="teks caption")
        self.caption_entry.grid(row=0, column=1, sticky="ew", pady=2)
        self.caption_dur = ctk.CTkEntry(params, width=54, placeholder_text="detik")
        self.caption_dur.grid(row=0, column=2, padx=(6, 0), pady=2)
        Tooltip(self.caption_dur, "Lama tampil (detik, dari awal video). Kosong = sepanjang video.")
        ctk.CTkLabel(params, text="logo").grid(row=1, column=0, sticky="w", padx=(0, 6))
        self.logo_entry = ctk.CTkEntry(params, placeholder_text="path gambar logo")
        self.logo_entry.grid(row=1, column=1, sticky="ew", pady=2)
        ctk.CTkButton(params, text="...", width=30, command=self._browse_logo).grid(
            row=1, column=2, padx=(6, 0), pady=2)
        for e in (self.caption_entry, self.caption_dur, self.logo_entry):
            e.bind("<KeyRelease>", lambda _e: self._on_params_changed())
        r += 1

        # speed + overlay
        sp = ctk.CTkFrame(right, fg_color="transparent")
        sp.grid(row=r, column=0, sticky="ew", pady=(8, 0))
        sp.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(sp, text="Speed").grid(row=0, column=0, padx=(0, 8))
        self.speed_slider = ctk.CTkSlider(sp, from_=0.5, to=2.0, number_of_steps=30,
                                          command=self._on_speed)
        self.speed_slider.grid(row=0, column=1, sticky="ew")
        self.speed_label = ctk.CTkLabel(sp, text="1.00x", width=46)
        self.speed_label.grid(row=0, column=2, padx=(6, 0))
        r += 1

        ov = ctk.CTkFrame(right, fg_color="transparent")
        ov.grid(row=r, column=0, sticky="ew", pady=(6, 0))
        self.overlay_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(ov, text="Sertakan efek Overlay tersimpan", variable=self.overlay_var,
                        command=self._on_use_overlay, checkbox_width=18, checkbox_height=18).pack(side="left")
        self.overlay_label = ctk.CTkLabel(ov, text="", text_color="gray60")
        self.overlay_label.pack(side="left", padx=(6, 0))
        r += 1

        q = ctk.CTkFrame(right, fg_color="transparent")
        q.grid(row=r, column=0, sticky="w", pady=(10, 0))
        ctk.CTkLabel(q, text="Quality:").pack(side="left", padx=(0, 10))
        saved = settings.get("effects_quality", "balanced")
        self.quality_var = ctk.StringVar(value=saved if saved in SPEED_TIERS else "balanced")
        for label, val in (("Fast", "fast"), ("Balanced", "balanced"), ("High", "high")):
            ctk.CTkRadioButton(q, text=label, variable=self.quality_var, value=val, width=20,
                               command=lambda: settings.set("effects_quality", self.quality_var.get())
                               ).pack(side="left", padx=(0, 10))
        r += 1

        self.live_var = ctk.BooleanVar(value=bool(settings.get("effects_live", True)))
        ctk.CTkCheckBox(right, text="Live preview di mpv", variable=self.live_var,
                        command=self._on_live_toggle, checkbox_width=18, checkbox_height=18).grid(
            row=r, column=0, sticky="w", pady=(8, 0))
        r += 1

        out = ctk.CTkFrame(right, fg_color="transparent")
        out.grid(row=r, column=0, sticky="ew", pady=(8, 4))
        out.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(out, text="Output:").grid(row=0, column=0, sticky="w")
        self.output_entry = ctk.CTkEntry(out)
        self.output_entry.grid(row=0, column=1, padx=8, sticky="ew")
        self.output_entry.bind("<KeyRelease>", lambda _e: setattr(self, "_output_dirty", True))
        r += 1

        runs = ctk.CTkFrame(right, fg_color="transparent")
        runs.grid(row=r, column=0, sticky="ew", pady=(4, 4))
        self.copy_menu = ctk.CTkOptionMenu(runs, values=[_COPY_PLACEHOLDER], width=110,
                                           command=self._copy_from)
        self.copy_menu.set(_COPY_PLACEHOLDER)
        self.copy_menu.pack(side="left")
        self.render_btn = ctk.CTkButton(runs, text="Render", width=80, command=lambda: self._start(False))
        self.render_btn.pack(side="right")
        self.test_btn = ctk.CTkButton(runs, text="Test 10s", width=72, command=lambda: self._start(True))
        self.test_btn.pack(side="right", padx=(0, 6))

    # ---- videos ----------------------------------------------------------------------------
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
        media = self._current_video()
        if not self.session.switch_video(media.path if media else None):
            # a render is running: put the dropdown back, nothing else changes
            cur = self.session.video
            self.video_menu.set(os.path.basename(cur) if cur else "(no videos found)")
            return
        self._fps = "30"
        with self.session.applying():
            self._sync_widgets()
        self._output_dirty = False
        self._suggest_output(media)
        others = [v.name for v in self.videos if media is None or v.path != media.path]
        self.copy_menu.configure(values=others or [_COPY_PLACEHOLDER])
        self.copy_menu.set(_COPY_PLACEHOLDER)
        self._cancel_preview_job()
        if media:
            vf, af, size, speed = self._preview_graphs(media)
            self.mpv_embed.set_aspect(*(size if all(size) else (media.width, media.height)))
            try:
                self.mpv_embed.load(media.path, vf=vf, af=af)
                if speed != 1.0:
                    self.mpv_embed.set_speed(speed)
            except OSError as e:
                self.app.log(f"[Effects] Failed to start mpv preview: {e}")
            self._start_probe(media)
        else:
            self.mpv_embed.stop()
        self._show_issues()

    def _suggest_output(self, media):
        if self._output_dirty:
            return
        self.output_entry.delete(0, "end")
        if media:
            self.output_entry.insert(0, f"{os.path.splitext(media.name)[0]}_fx.mp4")

    def _start_probe(self, media):
        gen = self.session.generation

        def worker():
            audio = has_audio_stream(media.path)
            fps = video_fps(media.path)
            fp = specmod.fingerprint(media.path, media.duration, media.width, media.height)
            self._after_safe(lambda: self._on_probe(gen, fp, audio, fps))

        threading.Thread(target=worker, daemon=True).start()

    def _on_probe(self, gen: int, fp, audio: bool, fps: str):
        if fp is None or self.session.apply_probe(gen, fp, audio) is None:
            return  # file vanished, or the user already switched to another video
        self._fps = fps
        self._update_audio_boxes()
        if "zoomin" in self.session.spec["presets"]:
            self._schedule_preview()
        self._show_issues()

    # ---- spec <-> widgets ------------------------------------------------------------------
    def _sync_widgets(self):
        """spec -> widgets. Call inside `session.applying()` so nothing writes back."""
        spec = self.session.spec
        chosen = set(spec["presets"])
        for n, var in self._vars.items():
            var.set(n in chosen)
        self._show_pack()
        cap = spec["params"].get("caption", {})
        self._set_entry(self.caption_entry, cap.get("text", ""))
        dur = cap.get("duration", 0)
        self._set_entry(self.caption_dur, f"{dur:g}" if dur else "")
        self._set_entry(self.logo_entry, spec["params"].get("watermark", {}).get("path", ""))
        self.speed_slider.set(spec["speed"])
        self.speed_label.configure(text=f"{spec['speed']:.2f}x")
        self.overlay_var.set(spec["use_overlay"])
        all_fx = specmod.load_overlay(self.session.video) if self.session.video else []
        n_fx, n_ok = len(all_fx), len(specmod.usable_overlay(all_fx))
        self.overlay_label.configure(text=f"({n_ok} efek" + (f", {n_fx - n_ok} belum lengkap" if n_fx != n_ok else "")
                                     + "; edit di panel Overlay)")
        self._update_audio_boxes()

    def _show_pack(self):
        self.pack_menu.set(specmod.effective_pack(self.session.spec) or _PACK_PLACEHOLDER)

    def _update_audio_boxes(self):
        """Audio presets can't do anything on a video without an audio track."""
        for n, box in self._boxes.items():
            if effects.PRESETS[n].stage == effects.AUDIO and n != "mute":
                box.configure(state="normal" if self.session.has_audio else "disabled")

    @staticmethod
    def _set_entry(entry, text: str):
        entry.delete(0, "end")
        if text:
            entry.insert(0, text)

    def _params_from_widgets(self) -> dict:
        try:
            dur = max(0.0, float(self.caption_dur.get().strip() or 0))
        except ValueError:
            dur = 0.0
        return {"caption": {"text": self.caption_entry.get(), "duration": dur},
                "watermark": {"path": self.logo_entry.get().strip()}}

    def _on_toggle(self, name: str):
        if self._vars[name].get() and effects.PRESETS[name].stage == effects.LAYOUT:
            for other, p in effects.PRESETS.items():
                if other != name and p.stage == effects.LAYOUT:
                    self._vars[other].set(False)
        self.session.update(presets=[n for n, v in self._vars.items() if v.get()])
        self._show_pack()
        self._after_edit()

    def _apply_pack(self, pack: str):
        if pack not in effects.PACKS:
            self._show_pack()
            return
        self.session.update(presets=effects.normalize([pack])[0], pack=pack)
        with self.session.applying():
            self._sync_widgets()
        self._after_edit()

    def _on_params_changed(self):
        self.session.update(params=self._params_from_widgets())
        self._schedule_preview()

    def _browse_logo(self):
        path = filedialog.askopenfilename(title="Pilih logo", filetypes=[("Gambar", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self._set_entry(self.logo_entry, path)
            self._on_params_changed()

    def _on_speed(self, value: float):
        v = round(float(value), 2)
        self.speed_label.configure(text=f"{v:.2f}x")
        self.session.update(speed=v)
        self._schedule_preview()

    def _on_use_overlay(self):
        self.session.update(use_overlay=bool(self.overlay_var.get()))
        self.session.revalidate()
        self._show_issues()

    def _after_edit(self):
        self._schedule_preview()
        self._show_issues()

    def _copy_from(self, name: str):
        self.copy_menu.set(_COPY_PLACEHOLDER)
        other = next((v for v in self.videos if v.name == name), None)
        if not other:
            return
        warns = self.session.copy_from(other.path)
        for w in warns:
            self.app.log(f"[Effects] {name}: {w}")
        with self.session.applying():
            self._sync_widgets()
        self._after_edit()

    def _reset_spec(self):
        if self.session.running:
            return
        self.session.reset()
        with self.session.applying():
            self._sync_widgets()
        self._after_edit()

    def _save_spec(self):
        if not self.session.video:
            self.app.log("[Effects] No video selected.")
            return
        path = self.session.default_export_path()  # always next to the video, named after it
        try:
            self.session.export_to(path)
            self.app.log(f"[Effects] Spec saved: {path}")
        except OSError as e:
            self.app.log(f"[Effects] Could not save spec: {e}")

    def _load_spec(self):
        if not self.session.video or self.session.running:
            return
        path = ask_load_path(self.session.video, "Effects")
        if not path:
            return
        ok, warns = self.session.import_from(path)
        for w in warns:
            self.app.log(f"[Effects] {os.path.basename(path)}: {w}")
        if ok:
            with self.session.applying():
                self._sync_widgets()
            self.app.log(f"[Effects] Spec loaded: {os.path.basename(path)}")
            self._after_edit()
        else:
            self._show_issues()

    def _keep_spec(self):
        self.session.accept_source()
        self._show_issues()

    def _show_issues(self):
        s = self.session
        msgs = list(s.warnings) + [i.message for i in s.issues] + ([s.save_error] if s.save_error else [])
        if not msgs:
            self.banner.grid_remove()
            return
        self.banner_label.configure(text="\n".join("• " + m for m in msgs))
        self.keep_btn.configure(
            state="normal" if any(i.kind in _RESOLUTION_KINDS for i in s.issues) else "disabled")
        self.banner.grid()

    # ---- live preview ----------------------------------------------------------------------
    def _preview_graphs(self, media) -> tuple[str, str, tuple[int, int], float]:
        """(vf, af, frame size, speed) for mpv, from the current spec. Empty when live preview is off."""
        spec = self.session.spec
        if not self.live_var.get():
            return "", "", (0, 0), 1.0
        names, _ = effects.normalize(spec["presets"])
        # the logo needs an extra input and a caption needs text: neither is part of the live graph
        cap = (spec["params"].get("caption") or {}).get("text", "").strip()
        names = [n for n in names if n != "watermark" and not (n == "caption" and not cap)]
        try:
            chain = effects.build_chain(names, spec["params"], width=media.width, height=media.height,
                                        fps=self._fps, tmpdir=self._tmpdir())
        except ValueError as exc:
            self.app.log(f"[Effects] Preview: {exc}")
            return "", "", (0, 0), 1.0
        vf, af = effects.preview_filters(chain)
        return vf, af, chain.size, spec["speed"]

    def _schedule_preview(self):
        self._cancel_preview_job()
        self._preview_job = self.after(_PREVIEW_DELAY_MS, self._apply_preview)

    def _cancel_preview_job(self):
        if self._preview_job is not None:
            self._cancel_after(self._preview_job)
            self._preview_job = None

    def _apply_preview(self):
        self._preview_job = None
        media = self._current_video()
        if not media or not self.mpv_embed.is_running():
            return
        vf, af, size, speed = self._preview_graphs(media)
        self.mpv_embed.set_aspect(*(size if all(size) else (media.width, media.height)))
        self.mpv_embed.set_filters(vf, af)
        self.mpv_embed.set_speed(speed)

    def _on_live_toggle(self):
        settings.set("effects_live", bool(self.live_var.get()))
        self._apply_preview()

    # ---- render ----------------------------------------------------------------------------
    def _set_busy(self, busy: bool):
        state = "disabled" if busy else "normal"
        for w in (self.video_menu, self.render_btn, self.test_btn, self.spec_menu, self.copy_menu, self.pack_menu):
            w.configure(state=state)

    def _start(self, test: bool):
        if self.session.running:
            return
        if not self.app.ensure_project_dir():
            return
        media = self._current_video()
        if not media:
            self.app.log("[Effects] No video selected.")
            return
        snap = self.session.snapshot()  # frozen now; overlay effects read fresh from disk
        names, _ = effects.normalize(snap["presets"])
        if not names and snap["speed"] == 1.0 and not snap["overlay_effects"]:
            self.app.log("[Effects] Nothing to apply: pick a pack/preset, change speed, or add Overlay effects.")
            return
        name = self.output_entry.get().strip()
        if not name:
            self.app.log("[Effects] Output filename required.")
            return
        base, ext = os.path.splitext(name)
        out = os.path.join(self.app.project.project_dir, f"{base}_test{ext}" if test else name)
        quality = self.quality_var.get()

        def begin(window):
            self.session.flush()   # what is on disk is exactly what gets rendered
            self.session.running = True
            self._set_busy(True)

            def worker():
                try:
                    ok = render(snap["video"], out, presets=snap["presets"], params=snap["params"],
                                overlay_effects=snap["overlay_effects"], speed=snap["speed"],
                                window=window, quality=quality, log=self.app.log)
                    if ok:
                        self.app.log_result(f"[Effects] Done: {os.path.basename(out)}", out)
                finally:
                    self.session.running = False
                    self._after_safe(lambda: self._set_busy(False))

            threading.Thread(target=worker, daemon=True).start()

        if not test:
            begin(None)
            return

        def on_time(t):
            if t is None:
                self.app.log("[Effects] Could not read mpv position, try again.")
                return
            end = min(t + 10.0, media.duration) if media.duration else t + 10.0
            begin((t, end))

        self.mpv_embed.get_time_pos_async(on_time)

    # ---- teardown --------------------------------------------------------------------------
    def destroy(self):
        # Navigation destroys the panel: persist whatever is pending before the widgets go.
        try:
            self.session.flush()
        except Exception:  # never block teardown on a save problem
            pass
        self._cancel_preview_job()
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)
        super().destroy()
