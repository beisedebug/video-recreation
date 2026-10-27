"""Offline contract tests plus real FFmpeg decoding; never contacts a website."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


# Keep dynamic script imports from leaving bytecode in the checkout.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "download_reference.py"
SPEC = importlib.util.spec_from_file_location("reference_downloader_test_subject", SCRIPT)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)


class ReferenceDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="reference-download-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.ffmpeg = reference.tool_path("ffmpeg")
        if not cls.ffmpeg or not reference.tool_path("ffprobe"):
            raise unittest.SkipTest("real FFmpeg and ffprobe required for offline fixtures")
        cls.video = cls.base / "fixture.mp4"
        cls.audio = cls.base / "audio.m4a"
        subprocess.run([cls.ffmpeg, "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                        "color=c=blue:s=96x64:r=12:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(cls.video)], check=True, capture_output=True)
        subprocess.run([cls.ffmpeg, "-v", "error", "-nostdin", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1", "-c:a", "aac", str(cls.audio)],
                       check=True, capture_output=True)
        cls.corrupt = cls.base / "corrupt.mp4"
        cls.corrupt.write_bytes(b"invalid video https://secret.invalid/?token=PRIVATE")
        cls.counter = 0

    def args(self, source=None, **overrides):
        type(self).counter += 1
        values = dict(command="acquire", source=str(source or self.video),
                      out_dir=str(self.base / f"request-{self.counter}"),
                      cookies_from_browser="none", quality="best", timeout=30,
                      wait_page=0, wechat_online="never")
        values.update(overrides)
        return SimpleNamespace(**values)

    def stub_backend(self, *, result=None, mutate=None):
        self.calls = []

        def download(url, directory, quality, cookies, audio_only, timeout):
            self.calls.append((url, directory, quality, cookies, audio_only, timeout))
            print("raw private URL https://signed.invalid/video?token=PRIVATE", file=sys.stderr)
            if result is not None:
                return result
            target = directory / "downloaded.mp4"
            shutil.copyfile(self.video, target)
            payload = {"ok": True, "files": [{"path": str(target)}],
                       "cookies_from_browser": None if cookies == "none" else cookies,
                       "webpage_url": url, "warnings": ["PRIVATE"]}
            if mutate:
                mutate(payload, directory)
            return payload

        return SimpleNamespace(normalize_url=lambda value: value,
                               is_spotify_url=lambda value: False,
                               is_wechat_channels_url=lambda value: False,
                               download_media=download)

    def test_local_copy_decodes_and_preserves_original(self):
        before = reference.sha256_file(self.video)
        args = self.args()
        result = reference.acquire(args)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["files"][0]["decoded_frames"], 12)
        self.assertEqual(result["files"][0]["verification"], "full-decode")
        self.assertEqual(reference.sha256_file(self.video), before)
        self.assertNotEqual(Path(result["files"][0]["path"]), self.video)
        manifest = Path(result["manifest"])
        self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)
        data = json.loads(manifest.read_text())
        self.assertEqual(data["files"][0]["path"], "media/reference.mp4")
        self.assertEqual(data["status"], "verified")
        self.assertEqual(data["source"]["type"], "local")

    def test_cli_local_entry(self):
        args = self.args()
        run = subprocess.run([sys.executable, str(SCRIPT), "acquire", str(self.video),
                              "--out-dir", args.out_dir, "--timeout", "30"],
                             capture_output=True, text=True, timeout=40)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)["ok"])

    def test_local_audio_and_corruption_rejected(self):
        for source in (self.audio, self.corrupt):
            with self.subTest(source=source.name):
                result = reference.acquire(self.args(source))
                self.assertFalse(result["ok"])
                self.assertEqual(result["stage"], "verify")
                manifest = Path(result["manifest"])
                self.assertEqual(json.loads(manifest.read_text())["status"], "failed")
                self.assertNotIn("PRIVATE", manifest.read_text())

    def test_existing_directory_is_untouched(self):
        args = self.args()
        root = Path(args.out_dir)
        root.mkdir()
        marker = root / "keep.txt"
        marker.write_text("preserve")
        result = reference.acquire(args)
        self.assertEqual(result["stage"], "output_exists")
        self.assertEqual(list(root.iterdir()), [marker])
        self.assertNotIn("manifest", result)

    def test_remote_anonymous_and_no_source_url_persistence(self):
        source = "https://example.test/watch?id=7&token=PRIVATE"
        args = self.args(source)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(reference, "load_backend", return_value=self.stub_backend()):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = reference.acquire(args)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.calls[0][3], "none")
        self.assertFalse(result["cookie_policy"]["used"])
        data = json.loads(Path(result["manifest"]).read_text())
        self.assertEqual(data["source"], {"type": "https", "host": "example.test",
                         "input_sha256": hashlib.sha256(source.encode()).hexdigest()})
        for text in (json.dumps(result), Path(result["manifest"]).read_text(), stdout.getvalue(), stderr.getvalue()):
            self.assertNotIn("PRIVATE", text)
            self.assertNotIn("https://", text)

    def test_explicit_cookie_browser_is_forwarded(self):
        args = self.args("https://example.test/watch", cookies_from_browser="chrome")
        with patch.object(reference, "load_backend", return_value=self.stub_backend()):
            result = reference.acquire(args)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.calls[0][3], "chrome")
        self.assertEqual(result["cookie_policy"], {"requested": "chrome", "used": True, "browser": "chrome"})

    def test_unexpected_cookie_use_rejected(self):
        def mutate(payload, directory):
            payload["cookies_from_browser"] = "chrome"
        with patch.object(reference, "load_backend", return_value=self.stub_backend(mutate=mutate)):
            result = reference.acquire(self.args("https://example.test/watch"))
        self.assertEqual(result["stage"], "cookie_policy")
        manifest = json.loads(Path(result["manifest"]).read_text())
        self.assertTrue(manifest["cookie_policy"]["used"])
        self.assertEqual(manifest["cookie_policy"]["browser"], "chrome")

    def test_failed_cookie_attempt_does_not_claim_no_cookie_use(self):
        backend = self.stub_backend(result={"ok": False, "stage": "metadata"})
        with patch.object(reference, "load_backend", return_value=backend):
            result = reference.acquire(self.args("https://example.test/watch", cookies_from_browser="chrome"))
        manifest = json.loads(Path(result["manifest"]).read_text())
        self.assertIsNone(manifest["cookie_policy"]["used"])
        self.assertEqual(manifest["cookie_policy"]["requested"], "chrome")

    def test_remote_false_empty_or_nonobject_results_rejected(self):
        for payload, expected in (({"ok": False, "stage": "metadata", "error": "token=PRIVATE"}, "metadata"),
                                  ({"ok": True, "files": []}, "backend_result"),
                                  ({"ok": "true", "files": []}, "backend_result"),
                                  ({"ok": True, "files": [None]}, "backend_result"),
                                  ([], "backend_result")):
            with self.subTest(payload=payload):
                with patch.object(reference, "load_backend", return_value=self.stub_backend(result=payload)):
                    result = reference.acquire(self.args("https://example.test/watch?token=PRIVATE"))
                self.assertFalse(result["ok"])
                self.assertEqual(result["stage"], expected)
                self.assertNotIn("PRIVATE", json.dumps(result))
                self.assertNotIn("PRIVATE", Path(result["manifest"]).read_text())

    def test_remote_path_boundary(self):
        for mode in ("outside", "symlink", "missing", "relative", "traversal"):
            def mutate(payload, directory):
                if mode == "outside":
                    path = self.video
                elif mode == "symlink":
                    path = directory / "linked.mp4"
                    path.symlink_to(self.video)
                elif mode == "missing":
                    path = directory / "missing.mp4"
                elif mode == "relative":
                    path = Path("downloaded.mp4")
                else:
                    path = directory / ".." / "media" / "downloaded.mp4"
                payload["files"] = [{"path": str(path)}]
            with self.subTest(mode=mode):
                with patch.object(reference, "load_backend", return_value=self.stub_backend(mutate=mutate)):
                    result = reference.acquire(self.args("https://example.test/watch"))
                self.assertEqual(result["stage"], "path_boundary", result)

    def test_backend_ok_cannot_bypass_actual_decode(self):
        def mutate(payload, directory):
            Path(payload["files"][0]["path"]).write_bytes(b"not a video")
            payload["files"][0]["verification"] = "full-decode"
        with patch.object(reference, "load_backend", return_value=self.stub_backend(mutate=mutate)):
            result = reference.acquire(self.args("https://example.test/watch"))
        self.assertEqual(result["stage"], "verify")

    def test_cover_stream_is_not_a_video_reference(self):
        probe = {"streams": [{"codec_type": "video", "width": 96, "height": 64,
                              "disposition": {"attached_pic": 1}}, {"codec_type": "audio"}],
                 "format": {"duration": "1"}}
        with patch.object(reference, "run_media", return_value=subprocess.CompletedProcess([], 0, json.dumps(probe), "")):
            with self.assertRaises(reference.AcquireError) as caught:
                reference.verify_video(self.video, 30)
        self.assertEqual(caught.exception.stage, "verify")

    def test_probe_success_without_decoded_frames_is_rejected(self):
        probe = {"streams": [{"codec_type": "video", "width": 96, "height": 64,
                              "disposition": {"attached_pic": 0}, "avg_frame_rate": "12/1"}],
                 "format": {"duration": "1"}}
        responses = [subprocess.CompletedProcess([], 0, json.dumps(probe), ""),
                     subprocess.CompletedProcess([], 0, "frame=0\nprogress=end\n", "")]
        with patch.object(reference, "run_media", side_effect=responses):
            with self.assertRaises(reference.AcquireError) as caught:
                reference.verify_video(self.video, 30)
        self.assertEqual(caught.exception.stage, "verify")

    def test_wechat_manual_and_setup_states_preserved(self):
        for stage in ("manual_action_required", "wechat_setup_required"):
            backend = self.stub_backend()
            backend.is_wechat_channels_url = lambda value: True
            def run_wechat(*args):
                self.wx_args = args
                return {"ok": False, "stage": stage, "error": "PRIVATE", "manual_action": "PRIVATE"}
            backend.run_wechat_adapter = run_wechat
            with patch.object(reference, "load_backend", return_value=backend):
                result = reference.acquire(self.args("https://weixin.qq.com/sph/public-token",
                                                    wait_page=90, wechat_online="allowed"))
            self.assertEqual(result["stage"], stage)
            self.assertEqual(self.wx_args[3:], ("allowed", 90, True))
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_spotify_and_nonhttps_stop_before_backend(self):
        for source, stage in (("https://open.spotify.com/track/abc", "unsupported_audio_source"),
                              ("http://example.test/video", "validate"),
                              ("https://[malformed/video", "validate"),
                              ("https://127.0.0.1/video", "validate")):
            with patch.object(reference, "load_backend", side_effect=AssertionError("must not run")):
                result = reference.acquire(self.args(source))
            self.assertEqual(result["stage"], stage)

    def test_doctor_has_no_subprocess_or_network_dependency(self):
        with patch.object(reference.subprocess, "run", side_effect=AssertionError("no subprocess")), \
                patch.object(reference, "load_backend", side_effect=AssertionError("no backend")):
            result = reference.doctor()
        self.assertTrue(result["local_video_ready"])
        self.assertFalse(result["network_checked"])
        self.assertFalse(result["installed_or_updated"])

    def test_cli_disallows_auto_cookies(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                reference.build_parser().parse_args(["acquire", "x", "--out-dir", "y", "--cookies-from-browser", "auto"])

    def test_vendored_ytdlp_argv_ignores_configuration(self):
        backend = reference.load_backend()
        recorded = []
        def run(command, stage, timeout, **kwargs):
            recorded.append(command)
            return subprocess.CompletedProcess(command, 0, '{"id":"fixture"}', "")
        with patch.object(backend, "require_tool", return_value="/stub/yt-dlp"), patch.object(backend, "run_command", side_effect=run):
            backend.load_metadata_once("https://example.test/watch", None, 10)
            backend.load_metadata_once("https://example.test/watch", "chrome", 10)
        for command in recorded:
            self.assertIn("--ignore-config", command)
            self.assertIn("--no-cache-dir", command)
        self.assertNotIn("--cookies-from-browser", recorded[0])
        self.assertEqual(recorded[1][recorded[1].index("--cookies-from-browser") + 1], "chrome")


if __name__ == "__main__":
    unittest.main(verbosity=2)
