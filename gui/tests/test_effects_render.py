"""Run from gui/:  ..\\venv-gui\\Scripts\\python -m unittest discover -s tests -t . -v"""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import effects, render  # noqa: E402
from core.paths import ffmpeg_path, ffprobe_path  # noqa: E402

INFO = render.MediaInfo(duration=10.0, width=1920, height=1080, fps="30", has_audio=True)


def cmd_for(presets, **kw):
    with tempfile.TemporaryDirectory() as tmp:
        kw.setdefault("tmpdir", tmp)
        return render.build_command(INFO, "in.mp4", "out.mp4", presets=presets, ffmpeg="ffmpeg", **kw)


def graph(cmd):
    return cmd[cmd.index("-filter_complex") + 1]


class PresetData(unittest.TestCase):
    def test_every_pack_member_is_a_preset(self):
        for pack, members in effects.PACKS.items():
            for m in members:
                self.assertIn(m, effects.PRESETS, f"{pack} -> {m}")

    def test_packs_have_at_most_one_layout(self):
        for pack, members in effects.PACKS.items():
            layouts = [m for m in members if effects.PRESETS[m].stage == effects.LAYOUT]
            self.assertLessEqual(len(layouts), 1, pack)

    def test_pack_names_do_not_shadow_presets(self):
        self.assertFalse(set(effects.PACKS) & set(effects.PRESETS))

    def test_normalize(self):
        names, warns = effects.normalize(["youtube-vlog", "punchy", "nope", "vertical", "hd"])
        self.assertEqual(names.count("punchy"), 1)
        self.assertNotIn("nope", names)
        self.assertIn("vertical", names)
        self.assertNotIn("hd", names)  # second layout dropped
        self.assertEqual(len(warns), 2)


class Chain(unittest.TestCase):
    def test_canonical_order_ignores_input_order(self):
        a = effects.build_chain(["sharpen", "vertical", "punchy"], width=1920, height=1080)
        b = effects.build_chain(["vertical", "punchy", "sharpen"], width=1920, height=1080)
        self.assertEqual(a.vf, b.vf)
        self.assertTrue(a.vf.startswith("split[fxa][fxb]"))

    def test_size_tracking(self):
        self.assertEqual(effects.build_chain(["vertical"], width=1920, height=1080).size, (1080, 1920))
        self.assertEqual(effects.build_chain(["square"], width=1920, height=1080).size, (1080, 1080))
        self.assertEqual(effects.build_chain(["hd"], width=1280, height=720).size, (1920, 1080))

    def test_zoom_uses_current_size_and_input_fps(self):
        c = effects.build_chain(["vertical", "zoomin"], width=1920, height=1080, fps="30000/1001")
        self.assertIn("s=1080x1920", c.vf)
        self.assertIn("fps=30000/1001", c.vf)

    def test_watermark_width_is_fraction_of_final_frame(self):
        c = effects.build_chain(["vertical", "watermark"], {"watermark": {"path": "l.png"}},
                                width=1920, height=1080)
        self.assertEqual(c.logo_w, 162)  # 15% of 1080, even

    def test_missing_parameters_raise(self):
        with self.assertRaises(ValueError):
            effects.build_chain(["caption"], width=1920, height=1080, tmpdir="x")
        with self.assertRaises(ValueError):
            effects.build_chain(["watermark"], width=1920, height=1080)

    def test_voice_plus_loudnorm_normalizes_once(self):
        c = effects.build_chain(["voice", "loudnorm"], width=1920, height=1080)
        self.assertTrue(c.norm)
        self.assertEqual(len(c.af), 1)


class Command(unittest.TestCase):
    def test_single_ffmpeg_graph(self):
        cmd = cmd_for(["youtube-vlog"], speed=1.25)
        self.assertEqual(cmd.count("-filter_complex"), 1)
        self.assertEqual(cmd.count("-i"), 1)

    def test_overlay_runs_before_layout_on_input_pixels(self):
        fx = [{"type": "box", "x": 10, "y": 10, "w": 50, "h": 50, "start": 1, "end": 2}]
        g = graph(cmd_for(["vertical"], overlay_effects=fx))
        self.assertLess(g.index("drawbox"), g.index("split[fxa]"))

    def test_fade_out_is_timed_after_speed(self):
        g = graph(cmd_for(["fade"], speed=2.0))  # 10 s / 2 = 5 s -> fade out starts at 4.5
        self.assertIn("setpts=PTS/2,fade=t=in:st=0:d=0.5,fade=t=out:st=4.5:d=0.5", g)
        self.assertIn("atempo=2,afade=t=in:st=0:d=0.5,afade=t=out:st=4.5:d=0.5", g)

    def test_loudnorm_before_audio_fade(self):
        g = graph(cmd_for(["fade", "loudnorm"]))
        self.assertLess(g.index("loudnorm"), g.index("afade"))

    def test_window_shifts_overlay_and_fades_on_window_length(self):
        fx = [{"type": "box", "x": 0, "y": 0, "w": 10, "h": 10, "start": 12, "end": 14}]
        cmd = cmd_for(["fade"], overlay_effects=fx, window=(10.0, 20.0))
        self.assertIn("between(t,2.000,4.000)", graph(cmd))
        self.assertIn("fade=t=out:st=9.5:d=0.5", graph(cmd))
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))

    def test_audio_copied_when_nothing_touches_it(self):
        cmd = cmd_for(["punchy"])
        self.assertEqual(cmd[cmd.index("-c:a") + 1], "copy")
        self.assertIn("0:a", cmd)

    def test_mute_has_no_dangling_audio_label(self):
        fx = [{"type": "mute", "start": 1, "end": 2}]
        cmd = cmd_for(["mute"], overlay_effects=fx)
        self.assertIn("-an", cmd)
        self.assertNotIn("[outa]", graph(cmd))

    def test_overlay_mute_alone_reencodes_audio(self):
        fx = [{"type": "mute", "start": 1, "end": 2}]
        cmd = cmd_for(["punchy"], overlay_effects=fx)
        self.assertEqual(cmd[cmd.index("-c:a") + 1], "aac")

    def test_no_audio_source(self):
        info = render.MediaInfo(10.0, 1920, 1080, "30", False)
        with tempfile.TemporaryDirectory() as tmp:
            cmd = render.build_command(info, "in.mp4", "out.mp4", presets=["voice", "fade"],
                                       tmpdir=tmp, ffmpeg="ffmpeg")
        self.assertIn("-an", cmd)
        self.assertNotIn("[0:a]", graph(cmd))

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            cmd_for([], speed=3.0)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            render.build_command(INFO, "a.mp4", "a.mp4", presets=[], tmpdir=tmp)

    def test_logo_input_index_follows_overlay_images(self):
        fx = [{"type": "image", "path": "p.png", "x": 0, "y": 0}]
        cmd = cmd_for(["watermark"], overlay_effects=fx, params={"watermark": {"path": "logo.png"}})
        self.assertEqual(cmd.count("-i"), 3)
        self.assertIn("[2:v]scale=", graph(cmd))


@unittest.skipUnless(os.path.exists(ffmpeg_path()), "bundled ffmpeg not present")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.src = os.path.join(cls.tmp.name, "src.mp4")
        cls.logo = os.path.join(cls.tmp.name, "logo.png")
        subprocess.run([ffmpeg_path(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=s=1280x720:d=4:r=30", "-f", "lavfi", "-i", "sine=f=440:d=4",
                        "-c:v", "libx264", "-c:a", "aac", "-shortest", cls.src], check=True)
        subprocess.run([ffmpeg_path(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=red:s=200x100:d=1", "-frames:v", "1", cls.logo], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def probe(self, path, entries):
        return subprocess.check_output(
            [ffprobe_path(), "-v", "error", "-show_entries", entries, "-of", "csv=p=0", path],
            text=True).strip()

    def test_everything_in_one_process(self):
        out = os.path.join(self.tmp.name, "out.mp4")
        fx = [{"type": "blur", "x": 100, "y": 100, "w": 300, "h": 200, "start": 0.5, "end": 1.5},
              {"type": "text", "text": "Halo: dunia's", "x": 50, "y": 50, "start": 0, "end": 2},
              {"type": "mute", "start": 1, "end": 2}]
        logs = []
        real_run = render.run_ffmpeg
        with mock.patch("core.render.run_ffmpeg", side_effect=real_run) as p:  # ffprobe calls don't count
            ok = render.render(self.src, out, presets=["shorts", "caption", "watermark", "zoomin"],
                               params={"caption": {"text": "Judul: tes", "duration": 2},
                                       "watermark": {"path": self.logo}},
                               overlay_effects=fx, speed=2.0, quality="fast", log=logs.append)
        self.assertTrue(ok, "\n".join(logs[-15:]))
        self.assertEqual(p.call_count, 1)  # the whole point: ONE ffmpeg process
        self.assertEqual(self.probe(out, "stream=width,height").splitlines()[0], "1080,1920")
        dur = float(self.probe(out, "format=duration"))
        self.assertAlmostEqual(dur, 2.0, delta=0.25)  # 4 s at 2x

    def test_every_pack_renders(self):
        for pack in effects.PACKS:
            with self.subTest(pack=pack):
                out = os.path.join(self.tmp.name, f"{pack}.mp4")
                logs = []
                ok = render.render(self.src, out, presets=[pack], quality="fast", log=logs.append,
                                   window=(0.0, 1.0))
                self.assertTrue(ok, "\n".join(logs[-10:]))
                self.assertTrue(os.path.getsize(out) > 0)


if __name__ == "__main__":
    unittest.main()
