"""Overlay spec persistence, compatibility with the skill CLI / old files, and Effects skipping unfinished rows."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import overlayspec, sidecar, spec  # noqa: E402
from core.overlay import effect_problem  # noqa: E402
from tests.test_segspec import Base, read_json, write_json  # noqa: E402
from tests.test_spec import fp  # noqa: E402


class EffectProblem(unittest.TestCase):
    def test_complete_and_incomplete(self):
        self.assertIsNone(effect_problem({"type": "blur", "x": "10", "y": 5, "w": 30, "h": 20}))
        self.assertIn("'w'", effect_problem({"type": "box", "x": 1, "y": 2, "h": 3}))
        self.assertIn("angka", effect_problem({"type": "box", "x": "a", "y": 2, "w": 1, "h": 3}))
        self.assertIn("'text'", effect_problem({"type": "text", "text": "  ", "x": 1, "y": 1}))
        self.assertIsNone(effect_problem({"type": "text", "text": "Hi", "x": 1, "y": 1}))
        self.assertIn("mute", effect_problem({"type": "mute"}))
        self.assertIsNone(effect_problem({"type": "mute", "end": "00:00:03"}))
        self.assertIn("tidak valid", effect_problem({"type": "mute", "start": "zz"}))
        self.assertIn("tipe", effect_problem({"type": "sparkle"}))


class Sanitize(unittest.TestCase):
    def test_clean_effect(self):
        self.assertEqual(overlayspec.clean_effect(
            {"type": "text", "start": " 00:00:01 ", "end": "", "text": "Hi", "x": "10", "y": "2.0", "size": "36",
             "color": "white", "bg": ""}),
            {"type": "text", "start": "00:00:01", "text": "Hi", "x": 10, "y": 2, "size": 36, "color": "white"})
        self.assertEqual(overlayspec.clean_effect({"type": "box", "x": "abc"}), {"type": "box", "x": "abc"})

    def test_old_formats_still_load(self):
        # the format the panel and the skill CLI always wrote: no version, no source
        old, w = overlayspec.sanitize_overlay({"effects": [{"type": "blur", "x": 1, "y": 2, "w": 3, "h": 4}]})
        self.assertEqual(len(old["effects"]), 1)
        self.assertEqual(w, [])
        with tempfile.TemporaryDirectory() as tmp:
            bare = os.path.join(tmp, "bare.json")
            write_json(bare, [{"type": "mute", "end": 3}])                      # the CLI also accepted a bare list
            loaded, _ = sidecar.read_file(bare, overlayspec.OVERLAY)
            self.assertEqual(loaded["effects"], [{"type": "mute", "end": 3}])

    def test_unknown_types_and_junk_are_dropped_with_warnings(self):
        s, w = overlayspec.sanitize_overlay({"effects": [{"type": "sparkle"}, "x", {"type": "box", "x": 1}]})
        self.assertEqual([e["type"] for e in s["effects"]], ["box"])
        self.assertEqual(len(w), 2)

    def test_written_file_is_readable_by_cli_and_effects_loaders(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = os.path.join(tmp, "v.mp4")
            open(v, "wb").close()
            sidecar.write_sidecar(v, {"effects": [{"type": "blur", "x": 1, "y": 2, "w": 3, "h": 4}],
                                      "source": None}, overlayspec.OVERLAY)
            data = read_json(os.path.join(tmp, "v.overlay.json"))
            self.assertEqual(data["effects"][0]["type"], "blur")       # what vfast_overlay.py reads: data["effects"]
            self.assertEqual(len(spec.load_overlay(v)), 1)             # what the Effects panel reads


class OverlayPersistence(Base):
    session_cls = overlayspec.OverlaySession
    suffix = ".overlay.json"

    def test_round_trip_per_video_without_leak(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(effects=[{"type": "blur", "x": 1, "y": 2, "w": 3, "h": 4, "start": "00:00:01"}])
        self.s.switch_video(b)
        self.assertEqual(self.s.spec["effects"], [])
        self.assertFalse(os.path.exists(self.sidecar(b)))
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["effects"][0]["start"], "00:00:01")

    def test_half_finished_rows_are_kept(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(effects=[{"type": "box", "x": 10}, {"type": "text", "text": "Hi"}])
        self.s.flush()
        self.s.switch_video(None)
        self.s.switch_video(a)
        self.assertEqual(len(self.s.spec["effects"]), 2)

    def test_validation(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(effects=[
            {"type": "box", "x": 10, "y": 10, "w": 5, "h": 5},                        # fine
            {"type": "box", "x": 10},                                                  # incomplete
            {"type": "blur", "x": 10, "y": 10, "w": 5, "h": 5, "start": "00:05:00"},   # after the end
            {"type": "box", "x": 5000, "y": 10, "w": 5, "h": 5},                       # outside the frame
        ])
        issues = self.s.apply_probe(self.s.generation, fp(duration=30.0, width=1920, height=1080))
        self.assertEqual(sorted((i.kind, i.index) for i in issues),
                         [("effect_out_of_frame", 3), ("effect_out_of_range", 2), ("incomplete", 1)])

    def test_resolution_change_warns_about_pixel_positions(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.apply_probe(self.s.generation, fp())
        self.s.update(effects=[{"type": "box", "x": 1, "y": 1, "w": 2, "h": 2}])
        self.s.flush()
        self.s.switch_video(None)
        self.s.switch_video(a)
        issues = self.s.apply_probe(self.s.generation, fp(width=1280, height=720))
        self.assertEqual([i.kind for i in issues], ["resolution_changed"])
        self.assertIn("piksel", issues[0].message)

    def test_deleting_every_effect_removes_the_file(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(effects=[{"type": "mute", "end": 3}])
        self.s.flush()
        self.s.update(effects=[])
        self.s.flush()
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_late_timer_cannot_overwrite_newer_data(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(effects=[{"type": "mute", "end": 3}])
        self.s.switch_video(b)
        self.s.switch_video(a)
        self.s.update(effects=[{"type": "mute", "end": 3}, {"type": "mute", "end": 9}])
        self.s.flush()
        self.clock.fire_all(including_cancelled=True, oldest_last=True)
        self.assertEqual(len(sidecar.read_sidecar(a, overlayspec.OVERLAY)[0]["effects"]), 2)
        self.assertFalse(os.path.exists(self.sidecar(b)))


class EffectsSkipsUnfinishedRows(Base):
    def test_snapshot_drops_incomplete_effects_and_validation_reports_them(self):
        a = self.video("a.mp4")
        sess = spec.EffectsSession(self.clock.schedule, self.clock.cancel)
        sess.switch_video(a)
        write_json(spec.overlay_path(a), {"effects": [{"type": "box", "x": 1, "y": 1, "w": 2, "h": 2},
                                                      {"type": "box", "x": 1}]})
        self.assertEqual(len(sess.snapshot()["overlay_effects"]), 1)
        issues = sess.apply_probe(sess.generation, fp())
        self.assertEqual([i.kind for i in issues], ["incomplete"])


if __name__ == "__main__":
    unittest.main()
