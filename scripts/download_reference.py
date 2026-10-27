#!/usr/bin/env python3
"""Acquire one reference video into a private, exclusive directory.

No installation or update is performed. URLs and backend logs are never written
to the manifest. Calling acquire is the explicit download action; the invoking
assistant is responsible for having the user's authorization, including cookies
or optional third-party WeChat resolution.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit


VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "qiaomu-download"
BROWSERS = ("none", "chrome", "edge", "firefox", "safari")
QUALITY = ("best", "1080p", "720p", "480p")
NEXT_ACTIONS = {
    "output_exists": "Choose a new --out-dir; the existing directory was not changed.",
    "validate": "Provide one local video file or a public HTTPS video URL without credentials or a custom port.",
    "unsupported_audio_source": "Spotify links provide audio, not a dance or camera reference. Supply a video source.",
    "dependency": "Check doctor and make the listed missing tools available; no tools were installed or updated.",
    "metadata": "Check the supplied link. If login is required, use only an already-authorized browser session explicitly.",
    "download": "Check the link, network and available disk space, then retry with a new --out-dir.",
    "timeout": "Check the source and backend status before retrying with a new --out-dir or a larger --timeout.",
    "verify": "Supply a complete playable video. The acquired file did not pass video-stream and full-decode checks.",
    "backend_result": "The downloader did not return verified file candidates. Check the backend before retrying.",
    "path_boundary": "The downloader returned a missing, linked, or out-of-directory file. Stop and inspect the backend.",
    "cookie_policy": "The backend reported cookie use outside the requested policy. Stop and inspect the backend.",
    "wechat_setup_required": "Use an already configured WeChat backend. Installation, certificates and proxy changes require separate setup; online resolution requires explicit share-URL consent.",
    "manual_action_required": "Manually open and play the reference in desktop WeChat, then retry in a new --out-dir with --wait-page 90. Do not automate WeChat UI.",
    "local_configuration": "Check the existing WeChat backend, config and FFmpeg paths; no settings were changed.",
    "local_download": "Check the existing WeChat backend connection and source, then retry in a new --out-dir.",
    "online_resolver": "The authorized WeChat resolver did not return usable media. Use the existing local backend or supply a local file.",
    "interrupted": "The acquisition was interrupted. Inspect existing backend activity before retrying in a new --out-dir.",
    "filesystem": "Check permissions and free space for the private output directory.",
}


class AcquireError(RuntimeError):
    def __init__(self, stage: str):
        self.stage = stage if stage in NEXT_ACTIONS else "download"
        super().__init__(self.stage)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tool_path(name: str) -> str | None:
    value = os.environ.get(f"QIAOMU_{name.upper().replace('-', '_')}_BIN") or shutil.which(name)
    if not value:
        return None
    path = Path(value).expanduser()
    return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None


def doctor() -> dict[str, Any]:
    """Local file/dependency inspection only: no subprocess or network requests."""
    tools = {name: tool_path(name) for name in ("ffmpeg", "ffprobe", "yt-dlp")}
    local_ready = bool(tools["ffmpeg"] and tools["ffprobe"])
    runtime = (VENDOR / "scripts" / "download.py").is_file()
    return {
        "ok": local_ready,
        "command": "doctor",
        "tools": tools,
        "local_video_ready": local_ready,
        "https_video_ready": local_ready and bool(tools["yt-dlp"]) and runtime,
        "vendored_runtime_present": runtime,
        "wechat_backend": "not_checked",
        "network_checked": False,
        "installed_or_updated": False,
    }


def save_manifest(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_name(".manifest.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def source_info(source: str) -> tuple[dict[str, Any], str | Path]:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        parsed = urlsplit(source)
    except ValueError:
        raise AcquireError("validate") from None
    if parsed.scheme:
        try:
            port = parsed.port
        except ValueError:
            raise AcquireError("validate") from None
        host = (parsed.hostname or "").rstrip(".").lower()
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or port or host == "localhost" or host.endswith(".localhost")):
            raise AcquireError("validate")
        try:
            if not ipaddress.ip_address(host.strip("[]")).is_global:
                raise AcquireError("validate")
        except ValueError:
            pass
        if host == "open.spotify.com" or host.endswith(".spotify.com") or host == "spotify.link":
            raise AcquireError("unsupported_audio_source")
        url = urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))
        return {"type": "https", "host": host, "input_sha256": digest}, url
    try:
        path = Path(source).expanduser().resolve(strict=True)
        if not path.is_file():
            raise AcquireError("validate")
    except (OSError, ValueError):
        raise AcquireError("validate") from None
    return {"type": "local", "host": None, "input_sha256": digest}, path


def load_backend():
    path = VENDOR / "scripts" / "download.py"
    if not path.is_file():
        raise AcquireError("dependency")
    spec = importlib.util.spec_from_file_location("video_recreation_reference_backend", path)
    if spec is None or spec.loader is None:
        raise AcquireError("dependency")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_backend(url: str, media_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    # Backend errors may contain signed URLs. Capture and discard all raw text.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            backend = load_backend()
            normalized = backend.normalize_url(url)
            if backend.is_spotify_url(normalized):
                raise AcquireError("unsupported_audio_source")
            if backend.is_wechat_channels_url(normalized):
                result = backend.run_wechat_adapter(
                    normalized, media_dir, args.timeout, args.wechat_online, args.wait_page, True)
            else:
                result = backend.download_media(
                    normalized, media_dir, args.quality, args.cookies_from_browser, False, args.timeout)
        except AcquireError:
            raise
        except subprocess.TimeoutExpired:
            raise AcquireError("timeout") from None
        except Exception as exc:
            stage = getattr(exc, "stage", "download")
            raise AcquireError(stage) from None
    if not isinstance(result, dict):
        raise AcquireError("backend_result")
    if result.get("ok") is not True:
        raise AcquireError(result.get("stage", "backend_result"))
    return result


def checked_candidate(value: Any, media_dir: Path) -> Path:
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise AcquireError("path_boundary")
    path = Path(value)
    try:
        relative = path.relative_to(media_dir)
        if not relative.parts or ".." in relative.parts:
            raise AcquireError("path_boundary")
        current = media_dir
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise AcquireError("path_boundary")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(media_dir) or not stat.S_ISREG(path.lstat().st_mode):
            raise AcquireError("path_boundary")
    except (OSError, ValueError):
        raise AcquireError("path_boundary") from None
    return resolved


def run_media(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AcquireError("timeout") from None
    except OSError:
        raise AcquireError("dependency") from None
    if result.returncode:
        raise AcquireError("verify")
    return result


def verify_video(path: Path, timeout: int) -> dict[str, Any]:
    ffprobe, ffmpeg = tool_path("ffprobe"), tool_path("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise AcquireError("dependency")
    result = run_media([
        ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries",
        "stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,duration:stream_disposition=attached_pic:format=duration,format_name",
        "-of", "json", str(path)], min(timeout, 120))
    try:
        probe = json.loads(result.stdout)
        streams = probe.get("streams") or []
        videos = [s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")]
        if not videos:
            raise AcquireError("verify")
        video = videos[0]
        duration = float(video.get("duration") or probe.get("format", {}).get("duration") or 0)
        width, height = int(video.get("width") or 0), int(video.get("height") or 0)
        if not math.isfinite(duration) or duration <= 0 or min(width, height) <= 0 or path.stat().st_size <= 0:
            raise AcquireError("verify")
    except (ValueError, TypeError, AttributeError, KeyError):
        raise AcquireError("verify") from None
    decoded = run_media([
        ffmpeg, "-v", "error", "-nostdin", "-xerror", "-protocol_whitelist", "file,pipe",
        "-i", str(path), "-map", "0:V:0", "-map", "0:a?", "-progress", "pipe:1",
        "-nostats", "-f", "null", "-"], timeout)
    counts = re.findall(r"^frame=\s*(\d+)\s*$", decoded.stdout, re.M)
    if not counts or int(counts[-1]) <= 0 or decoded.stderr.strip():
        raise AcquireError("verify")
    return {
        "path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size,
        "width": width, "height": height,
        "fps": video.get("avg_frame_rate") or video.get("r_frame_rate"),
        "duration_seconds": duration, "video_codec": video.get("codec_name"),
        "audio_streams": sum(s.get("codec_type") == "audio" for s in streams),
        "decoded_frames": int(counts[-1]), "verification": "full-decode",
    }


def acquire(args: argparse.Namespace) -> dict[str, Any]:
    root: Path | None = None
    manifest: Path | None = None
    state: dict[str, Any] = {
        "schema_version": 1, "status": "started", "command": "acquire", "files": [],
        "source": {"type": "unvalidated", "host": None,
                   "input_sha256": hashlib.sha256(args.source.encode("utf-8")).hexdigest()},
        "cookie_policy": {"requested": args.cookies_from_browser,
                          "used": False if args.cookies_from_browser == "none" else None,
                          "browser": None},
        "request": {"quality": args.quality, "timeout_seconds": args.timeout,
                    "wait_page_seconds": args.wait_page, "wechat_online": args.wechat_online},
    }
    try:
        requested_root = Path(args.out_dir).expanduser().absolute()
        try:
            requested_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        except FileExistsError:
            raise AcquireError("output_exists") from None
        root = requested_root.resolve(strict=True)
        media_dir = root / "media"
        media_dir.mkdir(mode=0o700)
        manifest = root / "manifest.json"
        save_manifest(manifest, state)
        state["source"], source = source_info(args.source)
        if not doctor()["local_video_ready"]:
            raise AcquireError("dependency")
        if isinstance(source, Path):
            state["cookie_policy"].update(used=False, browser=None)
            suffix = source.suffix.lower()
            if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
                suffix = ".media"
            target = media_dir / ("reference" + suffix)
            shutil.copyfile(source, target)
            candidates = [{"path": str(target)}]
        else:
            result = run_backend(source, media_dir, args)
            candidates = result.get("files")
            browser = result.get("cookies_from_browser")
            if browser is not None and browser not in BROWSERS[1:]:
                state["cookie_policy"].update(used=None, browser=None)
                raise AcquireError("cookie_policy")
            state["cookie_policy"].update(used=browser is not None, browser=browser)
            if browser is not None and browser != args.cookies_from_browser:
                raise AcquireError("cookie_policy")
            if state["source"]["host"] == "weixin.qq.com":
                state["authentication_channel"] = (
                    "authorized_online_resolver" if result.get("share_url_sent_to_resolver") is True
                    else "existing_local_wechat_backend")
        if not isinstance(candidates, list) or not candidates:
            raise AcquireError("backend_result")
        verified = []
        seen: set[Path] = set()
        for item in candidates:
            if not isinstance(item, dict):
                raise AcquireError("backend_result")
            path = checked_candidate(item.get("path"), media_dir)
            if path in seen:
                continue
            seen.add(path)
            info = verify_video(path, args.timeout)
            path.chmod(0o600)
            verified.append(info)
        state["files"] = [{**item, "path": str(Path(item["path"]).relative_to(root))} for item in verified]
        state["status"] = "verified"
        save_manifest(manifest, state)
        return {"ok": True, "command": "acquire", "manifest": str(manifest),
                "files": verified, "cookie_policy": state["cookie_policy"]}
    except KeyboardInterrupt:
        failure = AcquireError("interrupted")
    except AcquireError as exc:
        failure = exc
    except (OSError, ValueError):
        failure = AcquireError("filesystem")
    except Exception:
        failure = AcquireError("backend_result")
    state.update(status="failed", stage=failure.stage, next_action=NEXT_ACTIONS[failure.stage])
    saved = False
    if manifest is not None:
        try:
            save_manifest(manifest, state)
            saved = True
        except OSError:
            pass
    result = {"ok": False, "command": "acquire", "stage": failure.stage,
              "next_action": NEXT_ACTIONS[failure.stage]}
    if saved:
        result["manifest"] = str(manifest)
    return result


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="inspect local dependency paths; no network or installation")
    get = sub.add_parser("acquire", help="acquire and fully decode one reference video")
    get.add_argument("source", metavar="SOURCE")
    get.add_argument("--out-dir", required=True, help="new private directory; must not already exist")
    get.add_argument("--cookies-from-browser", choices=BROWSERS, default="none")
    get.add_argument("--quality", choices=QUALITY, default="best")
    get.add_argument("--timeout", type=positive_int, default=1200)
    get.add_argument("--wait-page", type=nonnegative_int, default=0)
    get.add_argument("--wechat-online", choices=("never", "allowed"), default="never",
                     help="allowed requires prior authorization to send the share URL to the resolver")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = doctor() if args.command == "doctor" else acquire(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
