"""Offline regression tests for the duration sent by the Grok video client."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


# Keep dynamic script imports from leaving bytecode in the checkout.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "grok_video.py"
SPEC = importlib.util.spec_from_file_location("grok_video_duration_test_subject", SCRIPT)
grok = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(grok)


class GrokVideoDurationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="grok-video-duration-tests-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        (self.directory / "prompt.txt").write_text("A fixed camera observes a dancer.")

    def build(self, duration):
        path = self.directory / "spec.json"
        path.write_text(json.dumps({
            "base_url": "https://video.invalid/v1",
            "model": "grok-imagine-video-1.5",
            "duration": duration,
            "resolution": "720p",
            "aspect_ratio": "16:9",
            "prompt_file": "prompt.txt",
        }))
        return grok.build(path)

    def sent_duration(self, duration):
        base, payload, public = self.build(duration)
        # Intercept the actual HTTP transport so this checks the serialized body
        # consumed by a provider, with no network or generation side effects.
        with patch.object(grok.request, "build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"request_id":"offline-job"}')
            grok.api(base, "/videos/generations", "offline-placeholder", payload)
            req = opener.return_value.open.call_args.args[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.full_url, "https://video.invalid/v1/videos/generations")
        sent = json.loads(req.data)["duration"]
        self.assertEqual(public["duration"], sent)
        self.assertIs(type(public["duration"]), type(sent))
        return sent

    def test_whole_seconds_are_json_integers(self):
        for duration in (4, 4.0, "4", "4.0"):
            with self.subTest(duration=duration):
                sent = self.sent_duration(duration)
                self.assertIs(type(sent), int)
                self.assertEqual(sent, 4)

    def test_fractional_seconds_are_preserved(self):
        for duration in (4.5, "4.5", 0.25):
            with self.subTest(duration=duration):
                sent = self.sent_duration(duration)
                self.assertIs(type(sent), float)
                self.assertEqual(sent, float(duration))

    def test_invalid_durations_still_fail_before_transport(self):
        for duration in (0, -1, "nan", "inf", "-inf"):
            with self.subTest(duration=duration):
                with patch.object(grok.request, "build_opener") as opener:
                    with self.assertRaises(grok.JobError):
                        self.build(duration)
                    opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
