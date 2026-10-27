#!/usr/bin/env python3
"""Compare normalized adjacent-frame pixel differences, not dance accuracy.

Requires existing FFmpeg, ffprobe and NumPy. Processes local files, streaming
frames through a pipe without shared scratch directories or network access.
Usage: python3 motion_check.py reference.mp4 generated.mp4 [--output motion.json]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

try:
    import numpy as np
except ImportError:
    np = None


NOT_CHECKED = [
    "pose_or_gesture_accuracy", "dance_quality_or_force", "subject_camera_motion_separation",
    "cut_flash_exposure_or_texture_change_separation", "optical_flow_or_3d_velocity",
    "event_time_alignment_between_inputs", "audio_or_beat_synchronization",
]


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


def dimension(value: str) -> int:
    number = int(value)
    if not 16 <= number <= 2048:
        raise argparse.ArgumentTypeError("must be an integer from 16 through 2048")
    return number


def probe(path: Path) -> dict:
    process = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                              "-show_streams", "-show_format", "-of", "json", str(path)],
                             capture_output=True, text=True, check=False)
    if process.returncode:
        raise RuntimeError("ffprobe could not read input: " + process.stderr.strip()[-1500:])
    return json.loads(process.stdout)


def summary(values) -> dict:
    if not len(values):
        return {"frame_pairs": 0, "mean_abs_difference_0_255": None,
                "mean_abs_difference_0_1": None, "median_abs_difference_0_255": None,
                "p95_abs_difference_0_255": None, "max_abs_difference_0_255": None}
    return {
        "frame_pairs": len(values),
        "mean_abs_difference_0_255": round(float(np.mean(values)), 6),
        "mean_abs_difference_0_1": round(float(np.mean(values)) / 255, 8),
        "median_abs_difference_0_255": round(float(np.median(values)), 6),
        "p95_abs_difference_0_255": round(float(np.percentile(values, 95)), 6),
        "max_abs_difference_0_255": round(float(np.max(values)), 6),
    }


def measure(filename: str, args, preprocessing: dict) -> dict:
    path = Path(filename).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("input must be a local file")
    metadata = probe(path)
    streams = [stream for stream in metadata.get("streams", [])
               if stream.get("codec_type") == "video" and not stream.get("disposition", {}).get("attached_pic")]
    result = {"input": str(path), "status": None, "frames_decoded": 0,
              "overall": summary([]), "segments": []}
    if not streams:
        return {**result, "status": "no_video", "reason": "No non-cover-art video stream was found."}
    stream = streams[0]
    result["source"] = {key: stream.get(key) for key in
                        ("index", "width", "height", "avg_frame_rate", "sample_aspect_ratio", "start_time", "duration")}
    command = ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
               "-i", str(path), "-map", f"0:{stream['index']}", "-an"]
    if args.duration is not None:
        command.extend(["-t", str(args.duration)])
    command.extend(["-vf", preprocessing["ffmpeg_filter"], "-pix_fmt", "gray",
                    "-f", "rawvideo", "-threads", "1", "pipe:1"])
    frame_size = args.width * args.height
    differences = []
    count = 0
    previous = None
    # An isolated anonymous temporary file avoids stderr pipe deadlocks without
    # creating, reusing, or deleting any shared frame directory.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            while True:
                raw = process.stdout.read(frame_size)
                if not raw:
                    break
                if len(raw) != frame_size:
                    raise RuntimeError("FFmpeg returned a partial raw frame")
                current = np.frombuffer(raw, dtype=np.uint8).astype(np.int16)
                if previous is not None:
                    differences.append(float(np.mean(np.abs(current - previous))))
                previous = current
                count += 1
            returncode = process.wait()
            if returncode:
                errors.seek(0)
                raise RuntimeError("FFmpeg video decode failed: " + errors.read().decode(errors="replace").strip()[-1500:])
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                process.wait()
    result["frames_decoded"] = count
    result["sampled_frame_timeline_s"] = {"first": 0.0 if count else None,
                                           "last": round((count - 1) / args.fps, 6) if count else None}
    if count < 2:
        return {**result, "status": "too_short", "reason": "Fewer than two sampled frames; frame-difference values are undefined."}
    values = np.asarray(differences)
    # Assign each difference to its frame-pair midpoint. At 12 fps, each complete
    # 0.5-second interval contains six pairs; keep the final partial segment.
    midpoints = (np.arange(len(values)) + 0.5) / args.fps
    indices = np.floor(midpoints / 0.5).astype(int)
    covered_end = (count - 1) / args.fps
    for index in range(int(indices[-1]) + 1):
        subset = values[indices == index]
        result["segments"].append({"start_s": round(index * 0.5, 6),
                                   "end_s": round(min((index + 1) * 0.5, covered_end), 6),
                                   **summary(subset)})
    result.update(status="measured", overall=summary(values),
                  pair_coverage_duration_s=round(covered_end, 6))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--fps", type=positive, default=12.0)
    parser.add_argument("--width", type=dimension, default=160)
    parser.add_argument("--height", type=dimension, default=90)
    parser.add_argument("--duration", type=positive, help="analyze the first N seconds of every input; default: entire video")
    parser.add_argument("--output", type=Path, help="also save this JSON to a file")
    args = parser.parse_args()
    if args.fps < 2 or args.fps > 120:
        parser.error("fps must be between 2 and 120")
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if np is None:
        missing.append("numpy")
    if missing:
        print(json.dumps({"status": "dependency_missing", "missing": missing, "not_checked": NOT_CHECKED}))
        return 1
    preprocessing = {
        "fps": args.fps, "width": args.width, "height": args.height,
        "pixel_format": "gray", "scale_filter": "area", "fit": "preserve display aspect ratio, center-pad black",
        "sample_origin": "first decoded video frame = 0 seconds; reset PTS then nearest-frame fps sampling",
        "segment_seconds": 0.5, "segment_assignment": "frame-pair midpoint; final partial segment retained",
        "requested_duration_limit_s": args.duration,
        "ffmpeg_filter": (f"setpts=PTS-STARTPTS,fps=fps={args.fps}:start_time=0:round=near,"
                          f"scale=w='min({args.width},{args.height}*dar)':h='min({args.height},{args.width}/dar)':flags=area,"
                          f"setsar=1,pad={args.width}:{args.height}:(ow-iw)/2:(oh-ih)/2:color=black,format=gray"),
    }
    results = []
    code = 0
    for filename in args.inputs:
        try:
            results.append(measure(filename, args, preprocessing))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            results.append({"input": filename, "status": "error", "error": str(exc)})
            code = 1
    result = {
        "schema_version": 1, "status": "complete" if not code else "completed_with_errors",
        "metric": "mean absolute grayscale difference between adjacent uniformly sampled frames",
        "preprocessing": preprocessing, "results": results, "not_checked": NOT_CHECKED,
        "interpretation": "This mixes subject motion, camera motion, cuts, flashes, exposure, texture and compression changes. It is not pose accuracy, physical speed, force, dance quality or a pass/fail score. There is no universal target range.",
        "comparison_note": "All inputs use the same sampling, size and grayscale pipeline. Different framing, aspect ratios/padding, scene content, duration or event alignment can still change the metric; compare matching intervals and inspect frames.",
    }
    try:
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
    except OSError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
