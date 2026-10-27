#!/usr/bin/env python3
"""Offline, constant-tempo BPM candidates and beat grids; never infers downbeats.

Requires an existing FFmpeg, ffprobe and NumPy. Input must be a local file.
Usage: python3 beat_analysis.py reference.mp4 [--duration 30] [--output beats.json]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

try:
    import numpy as np
except ImportError:
    np = None


NOT_CHECKED = [
    "musical_meter_and_downbeats", "bar_and_phrase_boundaries",
    "dance_pose_or_action_timing", "audio_video_synchronization",
    "time_varying_tempo", "musical_interpretation_of_half_or_double_tempo",
]


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


def probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
               "-show_streams", "-show_format", "-of", "json", str(path)]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode:
        raise RuntimeError("ffprobe could not read input: " + process.stderr.strip()[-1500:])
    return json.loads(process.stdout)


def number_or_none(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def spectral_flux(samples, window: int, hop: int):
    """Bounded relative positive spectral change, with chunked FFT memory use."""
    frames = np.lib.stride_tricks.sliding_window_view(samples, window)[::hop]
    taper = np.hanning(window)
    previous = None
    pieces = []
    for offset in range(0, len(frames), 512):
        magnitude = np.abs(np.fft.rfft(frames[offset:offset + 512] * taper, axis=1))
        before = np.vstack([magnitude[0] if previous is None else previous, magnitude[:-1]])
        numerator = np.maximum(magnitude - before, 0).sum(axis=1)
        denominator = magnitude.sum(axis=1) + before.sum(axis=1)
        pieces.append(np.divide(numerator, denominator, out=np.zeros_like(numerator),
                                where=denominator > 1e-10))
        previous = magnitude[-1]
    flux = np.concatenate(pieces)
    # A stationary spectrum may have tiny numerical/phase fluctuations. Do not
    # normalize them to full-strength onsets; keep the relative flux scale.
    envelope = np.maximum(flux - np.median(flux), 0)
    return flux, np.convolve(envelope, np.ones(3) / 3, mode="same")


def find_onsets(envelope, hop_seconds: float, window_seconds: float):
    median = float(np.median(envelope))
    mad = float(np.median(np.abs(envelope - median)))
    threshold = max(0.015, median + 3 * mad, 0.08 * float(envelope.max()))
    indices = np.flatnonzero((envelope[1:-1] > envelope[:-2]) &
                            (envelope[1:-1] >= envelope[2:]) &
                            (envelope[1:-1] >= threshold)) + 1
    accepted = []
    gap = max(1, round(0.1 / hop_seconds))
    for index in sorted(indices, key=lambda i: -envelope[i]):
        if all(abs(int(index) - other) >= gap for other in accepted):
            accepted.append(int(index))
    accepted.sort()
    indices = np.asarray(accepted, dtype=int)
    return indices * hop_seconds + window_seconds / 2, envelope[indices], threshold


def autocorrelations(envelope, low: int, high: int):
    centered = envelope - envelope.mean()
    n = len(centered)
    fft_size = 1 << (2 * n - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=fft_size)
    products = np.fft.irfft(spectrum * spectrum.conj(), n=fft_size)[:n]
    cumulative = np.concatenate(([0.0], np.cumsum(centered * centered)))
    values = {}
    for lag in range(low, min(high, n - 2) + 1):
        denominator = math.sqrt(float(cumulative[n - lag] * (cumulative[n] - cumulative[lag])))
        values[lag] = float(products[lag] / denominator) if denominator > 1e-12 else 0.0
    return values


def fit_grid(period, onset_times, weights, duration, hop_seconds):
    # The phase is only an onset-alignment hypothesis. It carries no meter or
    # downbeat information, even when its fit is excellent.
    tolerance = min(0.08, 0.16 * period)
    best = None
    for phase in np.arange(0, period, hop_seconds):
        grid = np.arange(phase, duration, period)
        if len(grid) < 3:
            continue
        distances = np.abs(((onset_times - phase + period / 2) % period) - period / 2)
        coverage = float(weights[distances <= tolerance].sum() / weights.sum())
        neighbors = np.searchsorted(onset_times, grid)
        left = onset_times[np.clip(neighbors - 1, 0, len(onset_times) - 1)]
        right = onset_times[np.clip(neighbors, 0, len(onset_times) - 1)]
        grid_distances = np.minimum(np.abs(grid - left), np.abs(grid - right))
        support = float(np.mean(grid_distances <= tolerance))
        alignment = float(np.average(np.maximum(0, 1 - distances / tolerance), weights=weights))
        score = (coverage * support * alignment) ** (1 / 3)
        if best is None or score > best[0]:
            best = (score, float(phase), grid, coverage, support,
                    float(np.average(distances, weights=weights)))
    return best, tolerance


def analyze(args) -> dict:
    path = Path(args.input).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("input must be a local file")
    metadata = probe(path)
    streams = [stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "audio"]
    parameters = {
        "sample_rate_hz": 22050, "channels": 1, "window_samples": 1024,
        "hop_samples": 256, "onset_envelope_step_s": 256 / 22050,
        "bpm_min": args.bpm_min, "bpm_max": args.bpm_max,
        "minimum_duration_s": args.min_duration, "silence_rms_dbfs_threshold": -65.0,
        "minimum_onsets": 4, "minimum_correlation": 0.25,
        "minimum_grid_support": 0.5, "minimum_onset_coverage": 0.5,
        "requested_duration_limit_s": args.duration,
    }
    result = {
        "schema_version": 1, "input": str(path), "status": None,
        "method": "relative spectral flux, normalized autocorrelation, constant-tempo onset-grid fit",
        "parameters": parameters, "duration_analyzed_s": 0.0,
        "candidates": [], "tempo_octave_checks": [], "onsets": [],
        "not_checked": NOT_CHECKED,
        "interpretation": "BPM and beat grids are candidates, not verified musical beats. A grid phase cannot establish a bar's first beat. Evidence scores are heuristic, not probabilities.",
        "timeline": {"origin": "first decoded audio sample = 0 seconds",
                     "note": "Audio-stream timestamps are supplied separately; verify alignment before using these times as video event times. Windowing, codecs and onset estimation limit timing accuracy; displayed decimals are not a precision guarantee."},
    }
    if not streams:
        return {**result, "status": "no_audio", "reason": "No audio stream was found; no beat estimate was attempted."}
    stream = streams[0]
    result["timeline"]["audio_stream_start_time_s"] = number_or_none(stream.get("start_time"))
    result["timeline"]["container_start_time_s"] = number_or_none(metadata.get("format", {}).get("start_time"))
    result["parameters"]["audio_stream_index"] = stream["index"]
    command = ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
               "-i", str(path), "-map", f"0:{stream['index']}", "-vn"]
    if args.duration is not None:
        command.extend(["-t", str(args.duration)])
    command.extend(["-ac", "1", "-ar", "22050", "-f", "f32le", "pipe:1"])
    process = subprocess.run(command, capture_output=True, check=False)
    if process.returncode:
        raise RuntimeError("FFmpeg audio decode failed: " + process.stderr.decode(errors="replace").strip()[-1500:])
    samples = np.frombuffer(process.stdout, dtype="<f4").astype(np.float64)
    if not len(samples):
        return {**result, "status": "empty_audio", "reason": "The selected stream decoded to zero samples."}
    if not np.isfinite(samples).all():
        raise ValueError("decoded audio contains non-finite samples")
    sample_rate = parameters["sample_rate_hz"]
    duration = len(samples) / sample_rate
    rms = float(np.sqrt(np.mean(samples * samples)))
    result.update(duration_analyzed_s=round(duration, 6), audio_rms_dbfs=(round(20 * math.log10(rms), 3) if rms else None),
                  audio_peak_amplitude=float(np.max(np.abs(samples))))
    if rms <= 10 ** (parameters["silence_rms_dbfs_threshold"] / 20):
        return {**result, "status": "silent", "reason": "Audio RMS is at or below the reported silence threshold; no BPM or grid is returned."}
    if duration < args.min_duration:
        return {**result, "status": "too_short", "reason": "Audio is shorter than minimum_duration_s; no reliable periodicity estimate was attempted."}
    window, hop = parameters["window_samples"], parameters["hop_samples"]
    flux, envelope = spectral_flux(samples, window, hop)
    onset_times, weights, threshold = find_onsets(envelope, hop / sample_rate, window / sample_rate)
    parameters["onset_envelope_threshold"] = float(threshold)
    result["onsets"] = [{"time_s": round(float(time), 4), "relative_flux_strength": round(float(weight), 5)}
                        for time, weight in zip(onset_times, weights)]
    result["diagnostics"] = {"onset_count": len(onset_times), "maximum_relative_spectral_flux": float(flux.max())}
    if len(onset_times) < parameters["minimum_onsets"] or flux.max() < 0.02:
        return {**result, "status": "weak_rhythm", "reason": "Too few sufficiently distinct onsets; no BPM or grid is returned."}
    envelope_rate = sample_rate / hop
    low = max(1, math.ceil(envelope_rate * 60 / args.bpm_max))
    high = math.floor(envelope_rate * 60 / args.bpm_min)
    correlations = autocorrelations(envelope, low, high)
    lag_peaks = [lag for lag, value in correlations.items()
                 if value >= parameters["minimum_correlation"]
                 and value >= correlations.get(lag - 1, -1)
                 and value >= correlations.get(lag + 1, -1)]
    candidates = []
    for lag in sorted(lag_peaks, key=lambda lag: -correlations[lag])[:12]:
        period = lag / envelope_rate
        fit, tolerance = fit_grid(period, onset_times, weights, duration, hop / sample_rate)
        if fit is None:
            continue
        grid_score, phase, grid, coverage, support, error = fit
        if support < parameters["minimum_grid_support"] or coverage < parameters["minimum_onset_coverage"]:
            continue
        candidates.append({
            "bpm": round(60 / period, 3), "period_s": round(period, 6),
            "phase_s": round(phase, 4), "autocorrelation": round(correlations[lag], 5),
            "onset_coverage": round(coverage, 5), "grid_support": round(support, 5),
            "weighted_onset_distance_to_grid_s": round(error, 5),
            "alignment_tolerance_s": round(tolerance, 5),
            "evidence_score": round(max(0, correlations[lag]) * grid_score, 5),
            "beat_grid_s": [round(float(point), 4) for point in grid],
            "grid_is_inferred": True,
        })
    candidates.sort(key=lambda item: -item["evidence_score"])
    if not candidates:
        return {**result, "status": "weak_rhythm", "reason": "No periodic candidate passed the reported correlation and grid-support gates; no BPM or grid is returned."}
    result.update(status="candidates_found", candidates=candidates[:5])
    best_period = candidates[0]["period_s"]
    for multiplier in (0.5, 2.0):
        period = best_period / multiplier
        bpm = 60 / period
        fit, tolerance = fit_grid(period, onset_times, weights, duration, hop / sample_rate)
        result["tempo_octave_checks"].append({
            "tempo_multiplier": multiplier, "bpm": round(bpm, 3),
            "within_requested_bpm_range": args.bpm_min <= bpm <= args.bpm_max,
            "onset_coverage": round(fit[3], 5) if fit else None,
            "grid_support": round(fit[4], 5) if fit else None,
            "alignment_tolerance_s": round(tolerance, 5),
            "interpretation": "Diagnostic alternative only; these statistics do not determine which pulse level a listener counts as the beat.",
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--duration", type=positive, help="analyze only the first N decoded seconds; default: entire stream")
    parser.add_argument("--bpm-min", type=positive, default=50.0)
    parser.add_argument("--bpm-max", type=positive, default=220.0)
    parser.add_argument("--min-duration", type=positive, default=4.0)
    parser.add_argument("--output", type=Path, help="also save this JSON to a file")
    args = parser.parse_args()
    if args.bpm_min >= args.bpm_max or args.bpm_min < 20 or args.bpm_max > 400:
        parser.error("require 20 <= bpm-min < bpm-max <= 400")
    if args.min_duration < 1:
        parser.error("min-duration must be at least 1 second")
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if np is None:
        missing.append("numpy")
    try:
        if missing:
            result, code = {"status": "dependency_missing", "missing": missing, "not_checked": NOT_CHECKED}, 1
        else:
            result, code = analyze(args), 0
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return code
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc), "not_checked": NOT_CHECKED}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
