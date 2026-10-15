"""Compare architecture takes with segment 8 (live) and segment 10 (outro).

Pace is words per second of voiced audio. Pitch is the median fundamental.
Warmth is the spectral centroid of voiced frames: a lower centroid is warmer.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

ASSETS = Path(__file__).resolve().parents[2] / "docs" / "demo" / "assets"
TAKES = Path(__file__).resolve().parents[2] / "docs" / "demo" / "edit" / "takes"
SR = 16000

WORDS = {
    "seg8": 24,
    "seg10": 7,
    "take": 59,
}


def load(path: Path) -> np.ndarray:
    raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
    )
    return np.frombuffer(raw, dtype=np.float32)


def analyze(x: np.ndarray, words: int) -> dict:
    frame = int(0.040 * SR)
    hop = int(0.010 * SR)
    window = np.hanning(frame)
    f0s = []
    centroids = []
    voiced = 0
    total = 0
    min_lag = int(SR / 320)
    max_lag = int(SR / 90)
    for i in range(0, len(x) - frame, hop):
        total += 1
        seg = x[i : i + frame]
        rms = float(np.sqrt(np.mean(seg * seg) + 1e-12))
        if rms < 0.02:
            continue
        voiced += 1
        spec = np.abs(np.fft.rfft(seg * window))
        freqs = np.fft.rfftfreq(frame, 1 / SR)
        centroids.append(float(np.sum(freqs * spec) / (np.sum(spec) + 1e-12)))
        corr = np.correlate(seg, seg, mode="full")[frame - 1 :]
        region = corr[min_lag:max_lag]
        if region.size == 0 or corr[0] <= 0:
            continue
        lag = int(np.argmax(region)) + min_lag
        if corr[lag] / corr[0] > 0.35:
            f0s.append(SR / lag)
    speech_s = voiced * hop / SR
    return {
        "duration_s": round(len(x) / SR, 3),
        "speech_s": round(speech_s, 3),
        "wps": round(words / speech_s, 3) if speech_s else None,
        "f0_hz": round(float(np.median(f0s)), 1) if f0s else None,
        "centroid_hz": round(float(np.median(centroids)), 1) if centroids else None,
        "voiced_ratio": round(voiced / total, 3) if total else None,
    }


def main() -> None:
    files = {
        "seg8": ASSETS / "n08_live.mp3",
        "seg10": ASSETS / "n10_outro.mp3",
        "take1": TAKES / "take1_5j2vW83Kxe.mp3",
        "take2": TAKES / "take2_MB12l6jDCm.mp3",
        "take3": TAKES / "take3_huJDN0KvqL.mp3",
    }
    stats = {}
    for name, path in files.items():
        words = WORDS["take"] if name.startswith("take") else WORDS[name]
        stats[name] = analyze(load(path), words)
        print(name, stats[name], flush=True)
    ref_wps = (stats["seg8"]["wps"] + stats["seg10"]["wps"]) / 2
    ref_f0 = (stats["seg8"]["f0_hz"] + stats["seg10"]["f0_hz"]) / 2
    ref_c = (stats["seg8"]["centroid_hz"] + stats["seg10"]["centroid_hz"]) / 2
    print(f"reference midpoint wps={ref_wps:.3f} f0={ref_f0:.1f} centroid={ref_c:.1f}")
    for name in ("take1", "take2", "take3"):
        s = stats[name]
        # Normalize each distance by the gap between the two references, so a
        # take inside that gap scores near zero.
        dw = abs(s["wps"] - ref_wps) / max(0.05, abs(stats["seg8"]["wps"] - stats["seg10"]["wps"]))
        df = abs(s["f0_hz"] - ref_f0) / max(5.0, abs(stats["seg8"]["f0_hz"] - stats["seg10"]["f0_hz"]))
        dc = abs(s["centroid_hz"] - ref_c) / max(50.0, abs(stats["seg8"]["centroid_hz"] - stats["seg10"]["centroid_hz"]))
        score = dw + df + dc
        print(f"{name} distance pace={dw:.3f} pitch={df:.3f} warmth={dc:.3f} total={score:.3f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
