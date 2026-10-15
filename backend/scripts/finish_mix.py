"""Mux the already-built picture and voice. Music sits 18 dB under the voice."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(r"d:\hackathon\ai-opportunity-copilot\ai-opportunity-copilot")
DEMO = ROOT / "docs" / "demo"
EDIT = DEMO / "edit"
ASSETS = DEMO / "assets"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def esc(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def dur(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def main() -> None:
    picture = EDIT / "picture.mp4"
    total = dur(picture)
    music = EDIT / "music_bed.wav"
    subprocess.run([
        FFMPEG, "-y", "-i", str(ASSETS / "music.wav"),
        "-af", f"atrim=0:{total:.3f},asetpts=PTS-STARTPTS,loudnorm=I=-34:TP=-2:LRA=11,afade=t=out:st={max(0, total - 4):.3f}:d=4",
        "-t", f"{total:.3f}", str(music),
    ], check=True)
    final = DEMO / "demo_final.mp4"
    srt = DEMO / "demo_final.srt"
    subprocess.run([
        FFMPEG, "-y", "-i", str(picture), "-i", str(EDIT / "voice_norm.wav"), "-i", str(music),
        "-filter_complex",
        "[1:a][2:a]amix=inputs=2:duration=first:normalize=0:dropout_transition=0[a];"
        f"[0:v]subtitles='{esc(srt)}':fontsdir='{esc(ASSETS)}':force_style='FontName=IBM Plex Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,BackColour=&H96000000,Outline=1,Shadow=0,MarginV=48'[v]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
        "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", "-t", f"{total:.3f}", str(final),
    ], check=True)
    sheet = DEMO / "demo_final_frames.png"
    subprocess.run([
        FFMPEG, "-y", "-i", str(final),
        "-vf", "fps=1/5,scale=320:-2,tile=8x5",
        "-frames:v", "1", "-update", "1", str(sheet),
    ], check=True)
    final_d = dur(final)
    # Segment clock from the narration files, with a 2s hold after each except the last.
    order = [
        ("problem", "n01_problem.mp3"),
        ("title", "n02_title.mp3"),
        ("show", "n03_show.mp3"),
        ("questions", "n04_questions.mp3"),
        ("discover", "n05_discover.mp3"),
        ("brief", "n06_brief.mp3"),
        ("compare", "n07_compare.mp3"),
        ("impact", "n11_impact.mp3"),
        ("live", "n08_live.mp3"),
        ("architecture", "n09_architecture.mp3"),
        ("outro", "n10_outro.mp3"),
    ]
    cursor = 0.0
    segments = []
    for i, (key, name) in enumerate(order):
        voice = dur(ASSETS / name)
        end = cursor + voice + (2.0 if i < len(order) - 1 else 0)
        row = {"id": key, "start": round(cursor, 3), "end": round(end, 3), "voice_s": round(voice, 3)}
        if key == "live":
            row["caption"] = (EDIT / "live_label.txt").read_text(encoding="utf-8").strip()
            row["speedup"] = 6.2
        segments.append(row)
        cursor = end
    report = {
        "file": str(final),
        "srt": str(srt),
        "sheet": str(sheet),
        "duration_s": round(final_d, 3),
        "size_bytes": final.stat().st_size,
        "segments": segments,
    }
    (DEMO / "timeline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not (185 <= final_d <= 235):
        raise SystemExit(f"duration {final_d:.2f}s is outside 3:05-3:55")
    if final.stat().st_size > 150 * 1024 * 1024:
        raise SystemExit("over 150 MB")


if __name__ == "__main__":
    main()
