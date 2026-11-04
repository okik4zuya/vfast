"""Range preview / jump logic against a fake player and a manual timer (no tkinter, no mpv)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.range_nav import RangeNav  # noqa: E402


class FakePlayer:
    """Plays at 1x; `tick()` advances time by one poll interval (0.1 s) when not paused."""

    def __init__(self, duration=100.0):
        self.pos, self.paused, self.running, self.duration = 0.0, True, True, duration
        self.seeks, self.scrubs, self.pauses = [], [], 0
        self.jobs = []

    # player API
    def is_running(self):
        return self.running

    def seek_to(self, seconds, pause=True):
        self.pos, self.paused = seconds, pause
        self.seeks.append((round(seconds, 3), pause))

    def pause(self):
        self.paused = True
        self.pauses += 1

    def seek_to_throttled(self, seconds):
        self.scrubs.append(seconds)

    def get_time_pos_async(self, cb):
        cb(self.pos if self.running else None)

    # fake timer (Tk's after / after_cancel)
    def schedule(self, ms, fn):
        self.jobs.append(fn)
        return len(self.jobs) - 1

    def cancel(self, job):
        self.jobs[job] = None

    def tick(self):
        """Run the pending timer callback, then advance playback by 0.1 s. False when nothing is pending."""
        pending = [j for j in self.jobs if j]
        self.jobs = []
        if not pending:
            return False
        if not self.paused:
            self.pos = min(self.pos + 0.1, self.duration)
        for job in pending:
            job()
        return True

    def run(self, limit=2000):
        for _ in range(limit):
            if not self.tick():
                return
        raise AssertionError("preview never finished")


def nav_for(player):
    logs = []
    return RangeNav(player, player.schedule, player.cancel, log=logs.append, tag="T"), logs


class Preview(unittest.TestCase):
    def test_plain_preview_plays_start_to_end_then_parks_on_end(self):
        p = FakePlayer()
        nav, _ = nav_for(p)
        nav.preview("00:00:10", "00:00:12")
        p.run()
        self.assertEqual(p.seeks[0], (10.0, False))
        self.assertEqual(p.seeks[-1], (12.0, True))   # exactly End, paused
        self.assertEqual(len(p.seeks), 2)

    def test_join_preview_skips_the_removed_part(self):
        p = FakePlayer()
        nav, _ = nav_for(p)
        nav.preview("00:00:10", "00:00:30", join=True, lead=1.0, tail=1.0)
        p.run()
        self.assertEqual(p.seeks, [(9.0, False), (30.0, False), (31.0, True)])

    def test_join_lead_is_clamped_at_zero_and_tail_at_duration(self):
        p = FakePlayer(duration=20.0)
        nav, _ = nav_for(p)
        nav.preview("00:00:01", "00:00:19.5", join=True, lead=2.0, tail=2.0, duration=20.0)
        p.run()
        self.assertEqual(p.seeks[0], (0.0, False))
        self.assertEqual(p.seeks[-1], (20.0, True))

    def test_stale_position_after_seek_does_not_end_the_phase_early(self):
        class Laggy(FakePlayer):
            """The first two position reads after a seek still return the OLD position."""
            lag = 0

            def seek_to(self, seconds, pause=True):
                self.stale = self.pos
                self.lag = 2
                super().seek_to(seconds, pause)

            def get_time_pos_async(self, cb):
                if self.lag:
                    self.lag -= 1
                    cb(self.stale)
                else:
                    cb(self.pos)

        p = Laggy()
        p.pos = 99.0                      # far past End when the preview starts
        nav, _ = nav_for(p)
        nav.preview("00:00:10", "00:00:11")
        p.run()
        self.assertEqual(p.seeks[-1], (11.0, True))
        self.assertEqual(len(p.seeks), 2)  # not finished by the stale 99.0 read: it played 10 -> 11

    def test_new_preview_or_jump_cancels_the_running_one(self):
        p = FakePlayer()
        nav, _ = nav_for(p)
        nav.preview("00:00:10", "00:00:50")
        for _ in range(5):
            p.tick()
        nav.goto(3.0)
        self.assertEqual(p.seeks[-1], (3.0, True))
        self.assertFalse(p.tick())        # nothing left polling
        self.assertEqual(p.pos, 3.0)

    def test_stops_when_mpv_goes_away(self):
        p = FakePlayer()
        nav, _ = nav_for(p)
        nav.preview("00:00:10", "00:00:50")
        p.tick()
        p.running = False
        p.run()                           # must terminate, not poll forever

    def test_stalled_player_does_not_poll_forever(self):
        p = FakePlayer(duration=12.0)     # file ends before `until`
        nav, _ = nav_for(p)
        nav.preview("00:00:10", "00:00:30")
        p.run()
        self.assertTrue(p.paused)


class Jumps(unittest.TestCase):
    def test_goto_text_parses_and_jumps_paused(self):
        p = FakePlayer()
        nav, logs = nav_for(p)
        nav.goto_text("00:01:02.500", "Start")
        self.assertEqual(p.seeks, [(62.5, True)])
        self.assertEqual(logs, [])

    def test_bad_or_empty_time_logs_instead_of_jumping(self):
        p = FakePlayer()
        nav, logs = nav_for(p)
        nav.goto_text("", "End")
        nav.goto_text("abc", "Start")
        self.assertEqual(p.seeks, [])
        self.assertEqual(len(logs), 2)

    def test_preview_validates_range(self):
        p = FakePlayer()
        nav, logs = nav_for(p)
        nav.preview("00:00:20", "00:00:10")
        nav.preview("", "00:00:10")
        self.assertEqual(p.seeks, [])
        self.assertEqual(len(logs), 2)

    def test_not_running_is_reported(self):
        p = FakePlayer()
        p.running = False
        nav, logs = nav_for(p)
        nav.goto_text("00:00:05", "Start")
        nav.preview("00:00:05", "00:00:10")
        self.assertEqual(p.seeks, [])
        self.assertEqual(len(logs), 2)

    def test_scrub_cancels_preview_and_uses_throttled_seek(self):
        p = FakePlayer()
        nav, _ = nav_for(p)
        nav.preview("00:00:10", "00:00:50")
        nav.scrub(7.0)
        self.assertEqual(p.scrubs, [7.0])
        self.assertFalse(p.tick())


if __name__ == "__main__":
    unittest.main()
