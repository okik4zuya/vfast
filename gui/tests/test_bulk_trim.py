"""bulk_trim: every row is accounted for in the log and the result (no ffmpeg: trim_video is mocked)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import trim  # noqa: E402


class RowProblem(unittest.TestCase):
    def test_valid_row(self):
        self.assertIsNone(trim.row_problem("00:00:05", "00:00:20.5"))

    def test_empty_row_is_not_a_mistake(self):
        self.assertEqual(trim.row_problem("", " "), "empty")

    def test_half_filled_and_invalid(self):
        self.assertEqual(trim.row_problem("", "00:00:20"), "Start is empty")
        self.assertEqual(trim.row_problem("00:00:05", ""), "End is empty")
        self.assertIn("invalid time", trim.row_problem("abc", "00:00:20"))
        self.assertIn("not after", trim.row_problem("00:00:20", "00:00:05"))

    def test_incomplete_rows_ignores_unused_empty_rows(self):
        rows = [("", ""), ("00:00:01", ""), ("00:00:01", "00:00:02")]
        self.assertEqual(trim.incomplete_rows(rows), [(2, "End is empty")])


class BulkTrim(unittest.TestCase):
    def run_bulk(self, rows, ok_for=lambda path: True):
        logs, calls = [], []

        def fake_trim(inp, start, end, out, log=print, preset="fast", crf=18):
            calls.append(os.path.basename(out))
            return ok_for(out)

        with mock.patch.object(trim, "trim_video", fake_trim):
            result = trim.bulk_trim("in.mp4", rows, "outdir", is_video=True, log=logs.append)
        return result, calls, logs

    def test_skipped_first_row_keeps_row_numbering_and_is_logged(self):
        rows = [("", "00:00:10"), ("00:00:20", "00:00:30"), ("00:00:40", "00:00:50")]
        result, calls, logs = self.run_bulk(rows)
        self.assertEqual(calls, ["clip_2.mp4", "clip_3.mp4"])
        self.assertEqual(result.created, [2, 3])
        self.assertEqual(result.skipped, [(1, "Start is empty")])
        self.assertTrue(any("Row 1 skipped: Start is empty" in line for line in logs))
        self.assertIn("row 1: Start is empty", logs[-1])

    def test_ffmpeg_failure_is_reported_not_hidden(self):
        rows = [("00:00:00", "00:00:05"), ("00:00:10", "00:00:15")]
        result, _, logs = self.run_bulk(rows, ok_for=lambda p: not p.endswith("clip_1.mp4"))
        self.assertEqual(result.failed, [1])
        self.assertEqual(result.created, [2])
        self.assertIn("ffmpeg failed on row 1", logs[-1])


if __name__ == "__main__":
    unittest.main()
