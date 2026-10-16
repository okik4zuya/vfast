"""Switching / persistence behaviour of the Effects spec (no tkinter, no ffmpeg)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import spec  # noqa: E402


class FakeClock:
    """Stands in for tk's after/after_cancel; `fire_all(including_cancelled=True)` simulates a late timer."""

    def __init__(self):
        self.jobs = []  # [handle, fn, cancelled]

    def schedule(self, ms, fn):
        job = [len(self.jobs), fn, False]
        self.jobs.append(job)
        return job[0]

    def cancel(self, handle):
        self.jobs[handle][2] = True

    def fire_all(self, including_cancelled=False, oldest_last=False):
        for job in (reversed(self.jobs) if oldest_last else list(self.jobs)):
            if including_cancelled or not job[2]:
                job[2] = True
                job[1]()


def fp(**kw):
    base = {"size": 100, "mtime": 1000.0, "duration": 10.0, "width": 1920, "height": 1080}
    base.update(kw)
    return base


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.s = spec.EffectsSession(self.clock.schedule, self.clock.cancel)

    def video(self, name):
        p = os.path.join(self.tmp.name, name)
        open(p, "wb").close()
        return p

    def sidecar(self, video):
        return spec.spec_path(video)


class Switching(Base):
    def test_no_leak_between_videos_and_restore_on_return(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["punchy", "fade"], speed=1.25,
                      params={"caption": {"text": "Halo", "duration": 3}})
        self.s.switch_video(b)
        self.assertEqual(self.s.spec["presets"], [])
        self.assertEqual(self.s.spec["params"], {})
        self.assertEqual(self.s.spec["speed"], 1.0)
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["presets"], ["punchy", "fade"])
        self.assertEqual(self.s.spec["speed"], 1.25)
        self.assertEqual(self.s.spec["params"]["caption"]["text"], "Halo")

    def test_switching_flushes_pending_edit_to_the_old_video(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["bw"])            # debounce still pending
        self.s.switch_video(b)
        self.assertTrue(os.path.exists(self.sidecar(a)))
        self.assertFalse(os.path.exists(self.sidecar(b)))

    def test_late_timer_never_touches_the_new_video_or_overwrites_newer_data(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["bw"])
        self.s.switch_video(b)
        self.s.switch_video(a)
        self.s.update(presets=["bw", "grain"])
        self.s.flush()
        # every stale timer fires late, the oldest one LAST (worst case for an overwrite)
        self.clock.fire_all(including_cancelled=True, oldest_last=True)
        self.assertFalse(os.path.exists(self.sidecar(b)))
        saved, _ = spec.read_spec(a)
        self.assertEqual(saved["presets"], ["bw", "grain"])

    def test_viewing_only_leaves_no_file(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.apply_probe(self.s.generation, fp(), True)
        self.s.switch_video(None)
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_back_to_default_removes_the_sidecar(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["bw"])
        self.s.flush()
        self.assertTrue(os.path.exists(self.sidecar(a)))
        self.s.update(presets=[])
        self.s.flush()
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_ui_applying_does_not_write_back(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        with self.s.applying():
            self.s.update(presets=["bw"], speed=1.5)   # widget callbacks firing while the UI is filled
        self.assertEqual(self.s.spec["presets"], [])
        self.s.flush()
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_switch_refused_while_rendering(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.running = True
        self.assertFalse(self.s.switch_video(b))
        self.assertEqual(self.s.video, a)

    def test_stale_probe_is_ignored(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        gen_a = self.s.generation
        self.s.switch_video(b)
        self.assertIsNone(self.s.apply_probe(gen_a, fp(duration=1.0), False))
        self.assertIsNone(self.s.current)
        self.assertIsNotNone(self.s.apply_probe(self.s.generation, fp(), True))

    def test_snapshot_is_detached_from_later_edits(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["bw"])
        snap = self.s.snapshot()
        self.s.update(presets=["bw", "grain"], speed=2.0)
        self.assertEqual(snap["presets"], ["bw"])
        self.assertEqual(snap["speed"], 1.0)

    def test_snapshot_reads_overlay_fresh(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.assertEqual(self.s.snapshot()["overlay_effects"], [])
        with open(spec.overlay_path(a), "w", encoding="utf-8") as f:
            json.dump({"effects": [{"type": "box", "x": 0, "y": 0, "w": 1, "h": 1}]}, f)
        self.assertEqual(len(self.s.snapshot()["overlay_effects"]), 1)


class OverlayToggle(Base):
    def _overlay(self, video):
        with open(spec.overlay_path(video), "w", encoding="utf-8") as f:
            json.dump({"effects": [{"type": "box", "start": 50, "x": 0, "y": 0, "w": 5, "h": 5}]}, f)

    def test_use_overlay_off_excludes_effects_from_render_and_validation(self):
        a = self.video("a.mp4")
        self._overlay(a)
        self.s.switch_video(a)
        self.assertEqual(len(self.s.snapshot()["overlay_effects"]), 1)
        self.s.update(use_overlay=False)
        self.assertEqual(self.s.snapshot()["overlay_effects"], [])
        self.assertEqual(self.s.apply_probe(self.s.generation, fp(duration=10.0), True), [])

    def test_use_overlay_persists_and_is_part_of_default(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(use_overlay=False)
        self.s.flush()
        self.s.switch_video(None)
        self.s.switch_video(a)
        self.assertFalse(self.s.spec["use_overlay"])
        self.s.update(use_overlay=True)
        self.s.flush()
        self.assertFalse(os.path.exists(self.sidecar(a)))


class PackLabel(Base):
    def test_pack_persists_across_switch_and_reload(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(presets=spec.effects.normalize(["youtube-vlog"])[0], pack="youtube-vlog")
        self.s.flush()
        self.s.switch_video(None)
        self.s.switch_video(a)
        self.assertEqual(spec.effective_pack(self.s.spec), "youtube-vlog")

    def test_hand_editing_hides_the_label_and_restoring_brings_it_back(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        members = spec.effects.normalize(["shorts"])[0]
        self.s.update(presets=members, pack="shorts")
        self.s.update(presets=members + ["grain"])
        self.assertEqual(spec.effective_pack(self.s.spec), "")
        self.s.update(presets=members)
        self.assertEqual(spec.effective_pack(self.s.spec), "shorts")

    def test_pack_is_per_video_and_unknown_pack_is_dropped(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["bw"], pack="fix-audio")
        self.s.flush()
        self.s.switch_video(b)
        self.assertEqual(spec.effective_pack(self.s.spec), "")
        clean, _ = spec.sanitize({"presets": ["bw"], "pack": "ghost-pack"})
        self.assertEqual(clean["pack"], "")

    def test_pack_alone_is_still_default(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(pack="shorts")          # no presets: nothing worth saving
        self.s.flush()
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_copy_from_copies_the_pack(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(presets=spec.effects.normalize(["tiktok"])[0], pack="tiktok")
        self.s.flush()
        self.s.switch_video(b)
        self.s.copy_from(a)
        self.assertEqual(spec.effective_pack(self.s.spec), "tiktok")


class Validation(Base):
    def test_no_audio_flags_audio_presets(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["voice"])
        issues = self.s.apply_probe(self.s.generation, fp(), False)
        self.assertEqual([i.kind for i in issues], ["no_audio"])

    def test_effect_after_end_of_shorter_video(self):
        a = self.video("a.mp4")
        with open(spec.overlay_path(a), "w", encoding="utf-8") as f:
            json.dump({"effects": [{"type": "box", "start": 2, "end": 3, "x": 0, "y": 0, "w": 5, "h": 5},
                                   {"type": "box", "start": 20, "end": 25, "x": 0, "y": 0, "w": 5, "h": 5}]}, f)
        self.s.switch_video(a)
        issues = self.s.apply_probe(self.s.generation, fp(duration=10.0), True)
        self.assertEqual([(i.kind, i.index) for i in issues], [("effect_out_of_range", 1)])

    def test_resolution_and_file_change_are_reported_not_applied(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.apply_probe(self.s.generation, fp(), True)
        self.s.update(presets=["bw"])
        self.s.flush()
        self.s.switch_video(None)
        self.s.switch_video(a)
        issues = self.s.apply_probe(self.s.generation, fp(size=999, mtime=5000.0, width=1280, height=720), True)
        self.assertEqual({i.kind for i in issues}, {"file_changed", "resolution_changed"})
        self.assertEqual(self.s.spec["presets"], ["bw"])      # spec untouched
        self.s.accept_source()
        self.assertEqual(self.s.issues, [])
        self.s.flush()
        saved, _ = spec.read_spec(a)
        self.assertEqual(saved["source"]["width"], 1280)

    def test_reset_clears_everything(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["bw"], speed=1.5)
        self.s.reset()
        self.assertEqual(self.s.spec["presets"], [])
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_copy_from_takes_settings_but_not_source(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.apply_probe(self.s.generation, fp(width=640, height=360), True)
        self.s.update(presets=["vintage"], speed=1.1)
        self.s.flush()
        self.s.switch_video(b)
        self.s.apply_probe(self.s.generation, fp(), True)
        self.s.copy_from(a)
        self.s.flush()
        saved, _ = spec.read_spec(b)
        self.assertEqual(saved["presets"], ["vintage"])
        self.assertEqual(saved["source"]["width"], 1920)       # b's own stamp, not a's


class Robustness(Base):
    def test_corrupt_json_is_backed_up_and_defaults_used(self):
        a = self.video("a.mp4")
        with open(self.sidecar(a), "w", encoding="utf-8") as f:
            f.write("{not json")
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["presets"], [])
        self.assertTrue(self.s.warnings)
        self.assertTrue(os.path.exists(self.sidecar(a) + ".bak"))
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_newer_version_is_not_overwritten_blindly(self):
        a = self.video("a.mp4")
        with open(self.sidecar(a), "w", encoding="utf-8") as f:
            json.dump({"version": 99, "presets": ["bw"]}, f)
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["presets"], [])
        self.assertTrue(os.path.exists(self.sidecar(a) + ".bak"))

    def test_unknown_presets_and_bad_values_are_cleaned_with_warnings(self):
        a = self.video("a.mp4")
        with open(self.sidecar(a), "w", encoding="utf-8") as f:
            json.dump({"version": 1, "presets": ["bw", "ghost", "bw"], "speed": 9,
                       "params": {"caption": {"text": " ", "duration": -3}, "x": 1}}, f)
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["presets"], ["bw"])
        self.assertEqual(self.s.spec["speed"], 1.0)
        self.assertEqual(self.s.spec["params"], {})
        self.assertEqual(len(self.s.warnings), 2)

    def test_write_failure_is_reported_not_raised(self):
        a = self.video("a.mp4")
        s = spec.EffectsSession(self.clock.schedule, self.clock.cancel,
                                writer=lambda v, sp: (_ for _ in ()).throw(OSError("disk full")))
        s.switch_video(a)
        s.update(presets=["bw"])
        s.flush()
        self.assertIn("disk full", s.save_error)

    def test_atomic_write_leaves_no_tmp_file(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(presets=["bw"])
        self.s.flush()
        self.assertFalse(os.path.exists(self.sidecar(a) + ".tmp"))


if __name__ == "__main__":
    unittest.main()
