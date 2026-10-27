#!/usr/bin/env python3
"""Check local media dependencies without network, credentials, or installation."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


def binary_info(name):
    path = shutil.which(name)
    if not path:
        return {"status": "missing"}
    try:
        result = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10)
        if result.returncode:
            return {"status": "unusable", "path": path}
        lines = (result.stdout or result.stderr).splitlines()
        return {"status": "pass", "path": path, "version": lines[0][:180] if lines else "unknown"}
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        return {"status": "unusable", "path": path, "error_kind": type(exc).__name__}


def encoder_info(ffmpeg):
    result = {"status": "not_checked", "libx264": False, "aac": False}
    if ffmpeg["status"] != "pass":
        return result
    try:
        run = subprocess.run([ffmpeg["path"], "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=10)
        if run.returncode:
            result["status"] = "unusable"
            return result
        names = set()
        for line in run.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 2 and len(fields[0]) == 6 and fields[0][0] in "VAS":
                names.add(fields[1])
        result.update(status="pass", libx264="libx264" in names, aac="aac" in names)
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        result.update(status="unusable", error_kind=type(exc).__name__)
    return result


def pillow_info():
    try:
        from PIL import Image, ImageDraw
        with Image.new("RGB", (16, 16)) as image:
            ImageDraw.Draw(image).text((0, 0), "1", fill="white")
        return {"status": "pass", "version": getattr(Image, "__version__", "unknown")}
    except Exception as exc:
        return {"status": "unusable", "error_kind": type(exc).__name__}


def numpy_info():
    try:
        import numpy
        numpy.asarray([0.0, 1.0]).mean()
        return {"status": "pass", "version": numpy.__version__}
    except Exception as exc:
        return {"status": "unusable", "error_kind": type(exc).__name__}


def workspace_info(workspace):
    path = Path(workspace).expanduser().resolve()
    if not path.is_dir():
        return {"status": "missing", "path": str(path)}
    try:
        with tempfile.TemporaryFile(prefix="video-recreation-check-", dir=path) as probe:
            probe.write(b"check")
            probe.flush()
        return {"status": "pass", "path": str(path)}
    except OSError as exc:
        return {"status": "not_writable", "path": str(path), "error_kind": type(exc).__name__}


def inspect_environment(workspace, host="other"):
    python_ok = sys.version_info >= (3, 9)
    ffmpeg = binary_info("ffmpeg")
    ffprobe = binary_info("ffprobe")
    encoders = encoder_info(ffmpeg)
    pillow = pillow_info()
    numpy = numpy_info()
    downloader = {"status": "found" if shutil.which("yt-dlp") else "missing", "path": shutil.which("yt-dlp")}
    folder = workspace_info(workspace)
    probe_ready = python_ok and ffmpeg["status"] == "pass" and folder["status"] == "pass"
    render_ready = probe_ready and encoders["libx264"]
    warnings = []
    if ffprobe["status"] != "pass":
        warnings.append("ffprobe unavailable: FFmpeg metadata fallback is approximate.")
    if pillow["status"] != "pass":
        warnings.append("Pillow unavailable: contact-sheet sampling is unavailable.")
    if numpy["status"] != "pass":
        warnings.append("NumPy unavailable: optional dance beat/motion diagnostics are unavailable.")
    if not encoders["libx264"]:
        warnings.append("libx264 unavailable: the bundled renderer cannot encode video.")
    if not encoders["aac"]:
        warnings.append("AAC encoder unavailable: the bundled renderer cannot encode audio.")
    return {
        "host_declared": host,
        "platform": platform.system(),
        "checks": {
            "python": {"status": "pass" if python_ok else "unsupported", "version": platform.python_version()},
            "ffmpeg": ffmpeg, "ffprobe": ffprobe, "encoders": encoders,
            "pillow": pillow, "numpy": numpy, "yt_dlp": downloader, "workspace": folder,
        },
        "local_media_status": "pass" if probe_ready else "fail",
        "capabilities": {
            "probe_decode": probe_ready,
            "sample_contact_sheets": probe_ready and pillow["status"] == "pass",
            "render_silent": render_ready,
            "render_with_audio": render_ready and encoders["aac"],
            "dance_diagnostics": probe_ready and ffprobe["status"] == "pass" and numpy["status"] == "pass",
            "download_dependencies": probe_ready and ffprobe["status"] == "pass" and downloader["status"] == "found",
        },
        "host_tools": {name: "not_checked" for name in (
            "image_generation", "motion_generation", "network_access", "artifact_delivery")},
        "warnings": warnings,
        "scope": "Local dependency checks only; no model selection, API calls, or media validation.",
    }


def save_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex", "muse", "muse-code", "other"), default="other")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--report")
    args = parser.parse_args()
    try:
        report = inspect_environment(args.workspace, args.host)
        if args.report:
            save_report(args.report, report)
    except (OSError, ValueError) as exc:
        print("Environment check/report failed: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["local_media_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
