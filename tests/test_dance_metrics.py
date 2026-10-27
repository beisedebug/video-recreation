"""Thirteen offline CLI scenarios using disposable synthetic audio/video."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

try:
    import numpy as np
except ImportError:
    np = None


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RATE = 22050


class DanceMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if np is None or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise unittest.SkipTest("NumPy, FFmpeg and ffprobe required for offline fixtures")
        temporary = tempfile.TemporaryDirectory(prefix="dance-metrics-tests-")
        cls.addClassCleanup(temporary.cleanup)
        cls.directory = Path(temporary.name)

        # Known 120 BPM transients, starting at 0.25 seconds.
        click_samples = np.zeros(12 * RATE)
        pulse_t = np.arange(round(0.035 * RATE)) / RATE
        pulse = 0.8 * np.sin(2 * np.pi * 1300 * pulse_t) * np.exp(-pulse_t * 150)
        for onset in np.arange(0.25, 12, 0.5):
            start = round(onset * RATE)
            click_samples[start:start + len(pulse)] += pulse
        cls.clicks = cls.wav("clicks-120-bpm.wav", click_samples)
        cls.silence = cls.wav("silence.wav", np.zeros(8 * RATE))
        cls.short = cls.wav("short.wav", 0.2 * np.sin(2 * np.pi * 440 * np.arange(RATE // 2) / RATE))
        cls.tone = cls.wav("steady-tone.wav", 0.2 * np.sin(2 * np.pi * 440 * np.arange(8 * RATE) / RATE))
        cls.noise = cls.wav("nonrhythmic-noise.wav", np.random.default_rng(17).normal(0, 0.08, 10 * RATE))
        cls.static = cls.video("static-no-audio.mp4", False)
        cls.moving = cls.video("moving-no-audio.mp4", True)
        cls.tiny = cls.video("one-frame.mp4", False, fps=12, seconds=1 / 12)
        cls.variant = cls.directory / "moving-double-size-and-fps.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(cls.moving),
                        "-vf", "scale=384:216:flags=neighbor,fps=48", "-an", "-c:v", "libx264",
                        "-crf", "0", "-pix_fmt", "yuv444p", str(cls.variant)],
                       check=True, capture_output=True, timeout=30)

    @classmethod
    def wav(cls, name, samples):
        path = cls.directory / name
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(RATE)
            output.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
        return path

    @classmethod
    def video(cls, name, moving, width=192, height=108, fps=24, seconds=2):
        path = cls.directory / name
        command = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                   "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-an",
                   "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv444p", str(path)]
        frames = []
        for index in range(round(fps * seconds)):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            x = int(10 + (index / fps) * 45) if moving else 10
            frame[30:65, x:x + 30] = 255
            frames.append(frame.tobytes())
        subprocess.run(command, input=b"".join(frames), capture_output=True, check=True, timeout=30)
        return path

    def cli(self, script, *arguments, expected=0):
        process = subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *map(str, arguments)],
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(process.returncode, expected, (script, arguments, process.stdout, process.stderr))
        return json.loads(process.stdout)

    def assert_no_beats(self, path, status):
        result = self.cli("beat_analysis.py", path)
        self.assertEqual(result["status"], status, result)
        self.assertEqual(result["candidates"], [], result)

    def test_known_120_bpm_and_json_output(self):
        output = self.directory / "clicks-result.json"
        beats = self.cli("beat_analysis.py", self.clicks, "--output", output)
        self.assertEqual(beats["status"], "candidates_found", beats)
        candidate = beats["candidates"][0]
        self.assertLess(abs(candidate["bpm"] - 120), 1)
        self.assertGreaterEqual(len(candidate["beat_grid_s"]), 22)
        self.assertLess(max(abs((time % 0.5) - 0.25) for time in candidate["beat_grid_s"]), 0.04)
        self.assertEqual(len(beats["tempo_octave_checks"]), 2)
        self.assertIn("musical_meter_and_downbeats", beats["not_checked"])
        self.assertNotIn("downbeats", beats)
        self.assertNotIn("downbeats", candidate)
        self.assertEqual(json.loads(output.read_text()), beats)

    def test_silence_has_no_beats(self):
        self.assert_no_beats(self.silence, "silent")

    def test_short_audio_has_no_beats(self):
        self.assert_no_beats(self.short, "too_short")

    def test_steady_tone_has_no_beats(self):
        self.assert_no_beats(self.tone, "weak_rhythm")

    def test_noise_has_no_beats(self):
        self.assert_no_beats(self.noise, "weak_rhythm")

    def test_silent_video_has_no_audio(self):
        self.assert_no_beats(self.static, "no_audio")

    def test_duration_limit_truncates_beat_analysis(self):
        result = self.cli("beat_analysis.py", self.clicks, "--duration", 1)
        self.assertEqual(result["status"], "too_short")
        self.assertLessEqual(result["duration_analyzed_s"], 1)

    def test_static_and_moving_video_metrics_and_json_output(self):
        output = self.directory / "motion-result.json"
        motion = self.cli("motion_check.py", self.static, self.moving, "--output", output)
        self.assertEqual(motion["preprocessing"]["fps"], 12)
        self.assertEqual((motion["preprocessing"]["width"], motion["preprocessing"]["height"]), (160, 90))
        still, active = motion["results"]
        self.assertEqual(still["status"], "measured")
        self.assertEqual(active["status"], "measured")
        self.assertEqual(still["overall"]["mean_abs_difference_0_255"], 0)
        self.assertGreater(active["overall"]["mean_abs_difference_0_255"], 0.5)
        for result in (still, active):
            with self.subTest(input=Path(result["input"]).name):
                self.assertEqual(len(result["segments"]), 4)
                self.assertEqual(sum(segment["frame_pairs"] for segment in result["segments"]),
                                 result["overall"]["frame_pairs"])
                self.assertEqual(result["segments"][-1]["frame_pairs"], 5)
                weighted = sum(segment["mean_abs_difference_0_255"] * segment["frame_pairs"]
                               for segment in result["segments"]) / result["overall"]["frame_pairs"]
                self.assertLess(abs(weighted - result["overall"]["mean_abs_difference_0_255"]), 1e-5)
        self.assertEqual(json.loads(output.read_text()), motion)

    def test_frame_rate_and_size_are_normalized(self):
        motion = self.cli("motion_check.py", self.moving, self.variant)
        original, variant = motion["results"]
        self.assertEqual(original["frames_decoded"], variant["frames_decoded"])
        self.assertNotEqual(original["source"]["width"], variant["source"]["width"])
        self.assertNotEqual(original["source"]["avg_frame_rate"], variant["source"]["avg_frame_rate"])
        self.assertLess(abs(original["overall"]["mean_abs_difference_0_255"] -
                            variant["overall"]["mean_abs_difference_0_255"]), 0.05)

    def test_custom_motion_duration_and_dimensions(self):
        motion = self.cli("motion_check.py", self.moving, "--duration", 0.75,
                          "--fps", 8, "--width", 128, "--height", 128)
        self.assertEqual(motion["results"][0]["frames_decoded"], 6)
        self.assertEqual(len(motion["results"][0]["segments"]), 2)

    def test_one_frame_video_has_no_motion_pairs(self):
        motion = self.cli("motion_check.py", self.tiny)
        self.assertEqual(motion["results"][0]["status"], "too_short")

    def test_audio_has_no_video(self):
        motion = self.cli("motion_check.py", self.silence)
        self.assertEqual(motion["results"][0]["status"], "no_video")

    def test_missing_input_does_not_skip_valid_input(self):
        motion = self.cli("motion_check.py", self.directory / "missing.mp4", self.static, expected=1)
        self.assertEqual(motion["results"][0]["status"], "error")
        self.assertEqual(motion["results"][1]["status"], "measured")


if __name__ == "__main__":
    unittest.main(verbosity=2)
