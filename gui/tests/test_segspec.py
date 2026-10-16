"""Cut/Trim specs and the explicit save/load by file name (no tkinter, no ffmpeg)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import segspec, sidecar  # noqa: E402
from tests.test_spec import FakeClock, fp  # noqa: E402


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Base(unittest.TestCase):
    session_cls = segspec.CutSession
    suffix = ".cut.json"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.s = self.session_cls(self.clock.schedule, self.clock.cancel)

    def video(self, name):
        p = os.path.join(self.tmp.name, name)
        open(p, "wb").close()
        return p

    def sidecar(self, video):
        return os.path.splitext(video)[0] + self.suffix


class CutPersistence(Base):
    def test_named_after_the_video_and_restored(self):
        a = self.video("clip.mp4")
        self.s.switch_video(a)
        self.s.update(ranges=[["00:00:05.000", "00:00:08.000"], ["00:01:00.000", "00:01:30.000"]])
        self.s.flush()
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "clip.cut.json")))
        self.s.switch_video(None)
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["ranges"][1], ["00:01:00.000", "00:01:30.000"])

    def test_no_leak_between_videos(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(ranges=[["0:0:1", "0:0:2"]])
        self.s.switch_video(b)
        self.assertEqual(self.s.spec["ranges"], [])
        self.assertFalse(os.path.exists(self.sidecar(b)))
        self.assertTrue(os.path.exists(self.sidecar(a)))     # flushed on switch

    def test_late_timer_cannot_overwrite_newer_data(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(ranges=[["0:0:1", "0:0:2"]])
        self.s.switch_video(b)
        self.s.switch_video(a)
        self.s.update(ranges=[["0:0:1", "0:0:2"], ["0:0:5", "0:0:6"]])
        self.s.flush()
        self.clock.fire_all(including_cancelled=True, oldest_last=True)
        self.assertEqual(len(sidecar.read_sidecar(a, segspec.CUT)[0]["ranges"]), 2)
        self.assertFalse(os.path.exists(self.sidecar(b)))

    def test_empty_ranges_remove_the_file(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(ranges=[["0:0:1", "0:0:2"]])
        self.s.flush()
        self.s.update(ranges=[])
        self.s.flush()
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_half_typed_values_are_kept_verbatim(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(ranges=[["00:0", ""], ["abc", "00:00:03"]])
        self.s.flush()
        self.s.switch_video(None)
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["ranges"], [["00:0", ""], ["abc", "00:00:03"]])

    def test_corrupt_and_garbage_are_safe(self):
        a = self.video("a.mp4")
        with open(self.sidecar(a), "w", encoding="utf-8") as f:
            f.write("{oops")
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["ranges"], [])
        self.assertTrue(os.path.exists(self.sidecar(a) + ".bak"))
        clean, warns = segspec.sanitize_cut({"ranges": [["1", "2"], "x", [1], ["a", "b", "c"], [3, 4.5]]})
        self.assertEqual(clean["ranges"], [["1", "2"], ["3", "4.5"]])
        self.assertEqual(len(warns), 3)

    def test_validation(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(ranges=[["00:00:01", "00:00:02"], ["00:01:00", "00:01:10"], ["zz", "00:00:02"],
                              ["00:00:05", "00:00:03"], ["", ""]])
        issues = self.s.apply_probe(self.s.generation, fp(duration=30.0))
        self.assertEqual(sorted((i.kind, i.index) for i in issues),
                         [("bad_range", 3), ("bad_time", 2), ("range_out_of_range", 1)])

    def test_file_changed_is_reported_and_keep_restamps(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.apply_probe(self.s.generation, fp())
        self.s.update(ranges=[["0:0:1", "0:0:2"]])
        self.s.flush()
        self.s.switch_video(None)
        self.s.switch_video(a)
        issues = self.s.apply_probe(self.s.generation, fp(size=999, mtime=9999.0))
        self.assertEqual([i.kind for i in issues], ["file_changed"])
        self.assertEqual(self.s.spec["ranges"], [["0:0:1", "0:0:2"]])     # untouched
        self.s.accept_source()
        self.assertEqual(self.s.issues, [])


class TrimPersistence(Base):
    session_cls = segspec.TrimSession
    suffix = ".trim.json"

    def test_default_is_whole_video_and_leaves_no_file(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(start="", end="", bulk=[])
        self.s.flush()
        self.assertFalse(os.path.exists(self.sidecar(a)))

    def test_round_trip_and_per_video(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(start="00:00:10.000", end="00:00:20.000", bulk=[["0:0:1", "0:0:2"], ["0:0:3", "0:0:4"]])
        self.s.switch_video(b)
        self.assertEqual((self.s.spec["start"], self.s.spec["end"], self.s.spec["bulk"]), ("", "", []))
        self.s.switch_video(a)
        self.assertEqual(self.s.spec["end"], "00:00:20.000")
        self.assertEqual(len(self.s.spec["bulk"]), 2)

    def test_validation(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(start="00:00:40", end="00:00:50", bulk=[["00:00:50", "00:01:00"]])
        issues = self.s.apply_probe(self.s.generation, fp(duration=30.0))
        kinds = sorted((i.kind, i.index) for i in issues)
        self.assertIn(("range_out_of_range", 0), kinds)
        self.assertIn(("end_beyond_video", -1), kinds)
        self.assertEqual(sum(1 for k, _ in kinds if k == "range_out_of_range"), 2)   # trim + bulk row


class SaveAndLoadByName(Base):
    def test_export_to_any_name_then_import_into_another_video(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.update(ranges=[["0:0:1", "0:0:2"]])
        target = os.path.join(self.tmp.name, "my-cuts.json")
        self.s.export_to(target)
        self.assertTrue(os.path.exists(target))
        self.s.switch_video(b)
        ok, warns = self.s.import_from(target)
        self.assertTrue(ok)
        self.assertEqual(self.s.spec["ranges"], [["0:0:1", "0:0:2"]])
        self.s.flush()
        self.assertTrue(os.path.exists(self.sidecar(b)))          # importing also persists by b's name

    def test_default_export_name_follows_the_video(self):
        a = self.video("my clip.mp4")
        self.s.switch_video(a)
        self.assertEqual(os.path.basename(self.s.default_export_path()), "my clip.cut.json")

    def test_export_even_when_default(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        target = os.path.join(self.tmp.name, "empty.json")
        self.s.export_to(target)
        self.assertEqual(read_json(target)["ranges"], [])

    def test_unusable_file_changes_nothing_and_is_not_renamed(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        self.s.update(ranges=[["0:0:1", "0:0:2"]])
        bad = os.path.join(self.tmp.name, "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("not json")
        ok, warns = self.s.import_from(bad)
        self.assertFalse(ok)
        self.assertTrue(warns)
        self.assertEqual(self.s.spec["ranges"], [["0:0:1", "0:0:2"]])
        self.assertTrue(os.path.exists(bad))
        self.assertFalse(os.path.exists(bad + ".bak"))
        newer = os.path.join(self.tmp.name, "newer.json")
        write_json(newer, {"version": 99, "ranges": [["1", "2"]]})
        self.assertFalse(self.s.import_from(newer)[0])

    def test_importing_a_trim_file_into_cut_does_not_crash_or_leak_fields(self):
        a = self.video("a.mp4")
        self.s.switch_video(a)
        trim_file = os.path.join(self.tmp.name, "x.trim.json")
        write_json(trim_file, {"version": 1, "start": "0:0:5", "end": "0:0:9", "bulk": [["1", "2"]]})
        ok, _ = self.s.import_from(trim_file)
        self.assertTrue(ok)
        self.assertEqual(self.s.spec["ranges"], [])
        self.assertNotIn("start", self.s.spec)

    def test_import_never_takes_the_source_stamp(self):
        a, b = self.video("a.mp4"), self.video("b.mp4")
        self.s.switch_video(a)
        self.s.apply_probe(self.s.generation, fp(width=640, height=360))
        self.s.update(ranges=[["0:0:1", "0:0:2"]])
        target = os.path.join(self.tmp.name, "t.json")
        self.s.export_to(target)
        self.assertEqual(read_json(target)["source"]["width"], 640)
        self.s.switch_video(b)
        self.s.apply_probe(self.s.generation, fp())
        self.s.import_from(target)
        self.s.flush()
        saved, _ = sidecar.read_sidecar(b, segspec.CUT)
        self.assertEqual(saved["source"]["width"], 1920)


class Schemas(unittest.TestCase):
    def test_sidecar_names_are_distinct_per_tool(self):
        names = {sidecar.sidecar_path("C:/v/clip.mp4", s) for s in (segspec.CUT, segspec.TRIM)}
        self.assertEqual(names, {"C:/v/clip.cut.json", "C:/v/clip.trim.json"})


if __name__ == "__main__":
    unittest.main()
