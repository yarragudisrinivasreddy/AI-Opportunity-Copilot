"""Cut the film to the single-take cue sheet.

One narration file only: docs/demo/assets/narration_single_take.mp3.
Picture changes on every screen. The narration is not stretched or trimmed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "docs" / "demo"
CAP = DEMO / "capture"
INS = CAP / "inserts"
EDIT = DEMO / "edit" / "single"
ASSETS = DEMO / "assets"
FONT = ASSETS / "plex-500.ttf"
VOICE = ASSETS / "narration_single_take.mp3"
ARCH = Path(r"D:\hackathon\ai-opportunity-copilot\architecture_source\architecture_anim.mp4")
HERO = INS / "hero.png"
END = ASSETS / "end_card_thankyou_1920x1080.png"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

# Cue-sheet boundaries. Frames are the nearest 30 fps cut, so the film is 190.5 s.
BOUNDS = [0, 32.00, 40.64, 63.50, 76.19, 99.96, 111.00, 137.92, 149.84, 158.15, 183.54, 187.00, 190.50]
NAMES = [
    "problem", "title", "show", "questions", "discover", "brief",
    "compare", "impact", "live", "architecture", "outro", "endcard",
]


def run(args: list[str]) -> None:
    print(" ".join(str(a) for a in args[:8]), "...", flush=True)
    subprocess.run(args, check=True)


def dur(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def wh(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    w, h = out.stdout.strip().split(",")
    return int(w), int(h)


def esc(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def frames_for(bounds: list[float]) -> list[int]:
    cuts = [round(b * 30) for b in bounds]
    return [b - a for a, b in zip(cuts, cuts[1:])]


def encode(src_args: list[str], vf: str, frames: int, dest: Path) -> None:
    run([
        FFMPEG, "-y", *src_args,
        "-vf", vf, "-frames:v", str(frames), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ])


def fit_clip(src: Path, frames: int, dest: Path, ss: float = 0.0, extra: str = "") -> None:
    seconds = frames / 30
    src_d = max(0.1, dur(src) - ss)
    chain = [f"setpts=PTS*{seconds / src_d:.6f}", "scale=1920:1080:flags=lanczos,setsar=1"]
    if extra:
        chain.append(extra)
    chain.append("fps=30,format=yuv420p")
    encode(["-ss", f"{ss:.3f}", "-i", str(src)], ",".join(chain), frames, dest)


def scroll_still(src: Path, frames: int, dest: Path) -> None:
    seconds = frames / 30
    _w, h = wh(src)
    # A tall page travels once. A short page goes down and back so the frame never sits still.
    travel_guess = max(0, h - 1080)
    if travel_guess < 360:
        y = f"max(0\\,ih-1080)*(1-abs(2*t/{seconds:.3f}-1))"
    else:
        y = f"max(0\\,ih-1080)*min(1\\,t/{seconds:.3f})"
    vf = f"scale=1920:-2:flags=lanczos,crop=1920:1080:0:'{y}',fps=30,format=yuv420p"
    encode(["-loop", "1", "-i", str(src)], vf, frames, dest)


def title_card(frames: int, dest: Path) -> None:
    seconds = frames / 30
    vf = (
        f"scale=-2:1080:flags=lanczos,crop=1920:1080:"
        f"x='40+200*t/{seconds:.3f}':y=0,fps=30,format=yuv420p"
    )
    encode(["-loop", "1", "-i", str(HERO)], vf, frames, dest)


def outro_card(frames: int, dest: Path) -> None:
    still = EDIT / "compare_still.png"
    run([FFMPEG, "-y", "-ss", "2", "-i", str(CAP / "compare.mp4"), "-frames:v", "1", "-update", "1", str(still)])
    font = esc(FONT)
    vf = (
        "[0:v]scale=1560:-2:flags=lanczos[shot];"
        "color=c=0x0b1620:s=1920x1080:r=30[bg];"
        "[bg][shot]overlay=(W-w)/2:36,"
        f"drawtext=fontfile='{font}':text='y-srinivasreddy.web.app':fontcolor=0xf2a23a:fontsize=42:x=(w-text_w)/2:y=960,"
        f"drawtext=fontfile='{font}':text='Try the sample case':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=1016,"
        "format=yuv420p"
    )
    run([
        FFMPEG, "-y", "-loop", "1", "-i", str(still),
        "-filter_complex", vf, "-frames:v", str(frames), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ])


def end_card(frames: int, dest: Path) -> None:
    seconds = frames / 30
    font = esc(FONT)
    fade_out = max(0.2, seconds - 0.45)
    vf = (
        "scale=1920:1080:flags=lanczos,setsar=1,"
        f"drawtext=fontfile='{font}':text='y-srinivasreddy.web.app':fontcolor=white:fontsize=28:"
        "box=1:boxcolor=black@0.60:boxborderw=12:x=w-text_w-72:y=h-th-56,"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out:.3f}:d=0.45,format=yuv420p"
    )
    encode(["-loop", "1", "-i", str(END)], vf, frames, dest)


def live_segment(frames: int, dest: Path) -> None:
    src = CAP / "live.mp4"
    src_d = dur(src)
    head_n = 60
    tail_n = 45
    mid_n = frames - head_n - tail_n
    head_s = head_n / 30
    tail_s = tail_n / 30
    mid_src = max(0.4, src_d - head_s - tail_s)
    factor = mid_src / (mid_n / 30)
    head = EDIT / "_live_head.mp4"
    sped = EDIT / "_live_sped.mp4"
    tail = EDIT / "_live_tail.mp4"
    fit_clip(src, head_n, head, ss=0)
    run([
        FFMPEG, "-y", "-ss", f"{head_s:.3f}", "-t", f"{mid_src:.3f}", "-i", str(src),
        "-vf", f"setpts=PTS/{factor:.6f},fps=30,scale=1920:1080,format=yuv420p",
        "-frames:v", str(mid_n), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(sped),
    ])
    fit_clip(src, round(tail_s * 30), tail, ss=max(0, src_d - tail_s))
    font = esc(FONT)
    run([
        FFMPEG, "-y", "-i", str(head), "-i", str(sped), "-i", str(tail),
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0,"
        f"drawtext=fontfile='{font}':text='Live run, sped up':fontcolor=white:fontsize=32:"
        "box=1:boxcolor=0x0b1620@0.72:boxborderw=14:x=64:y=48,fps=30,format=yuv420p[v]",
        "-map", "[v]", "-frames:v", str(frames), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ])


def brief_segment(frames: int, dest: Path) -> None:
    clip_frames = min(frames - 90, round(dur(CAP / "brief.mp4") * 30))
    clip_frames = max(60, clip_frames)
    rest = frames - clip_frames
    part = EDIT / "_brief_clip.mp4"
    scroll = EDIT / "_brief_scroll.mp4"
    fit_clip(CAP / "brief.mp4", clip_frames, part)
    scroll_still(INS / "brief_full.png", rest, scroll)
    run([
        FFMPEG, "-y", "-i", str(part), "-i", str(scroll),
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,fps=30,format=yuv420p[v]",
        "-map", "[v]", "-frames:v", str(frames), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ])


def impact(frames: int, dest: Path) -> None:
    sources = [
        (CAP / "understand.mp4", 4.0),
        (CAP / "discover.mp4", 3.0),
        (CAP / "brief.mp4", 1.0),
        (CAP / "compare.mp4", 1.5),
    ]
    base, extra = divmod(frames, 4)
    parts = []
    for i, (src, ss) in enumerate(sources):
        n = base + (1 if i < extra else 0)
        part = EDIT / f"_impact_{i}.mp4"
        fit_clip(src, n, part, ss=ss)
        parts.append(part)
    run([
        FFMPEG, "-y", *[x for p in parts for x in ("-i", str(p))],
        "-filter_complex", "[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0,fps=30,format=yuv420p[v]",
        "-map", "[v]", "-frames:v", str(frames), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ])


def build_picture(counts: list[int]) -> Path:
    segs: list[Path] = []
    font = esc(FONT)
    label = (
        f"drawtext=fontfile='{font}':text='Illustrative scene, AI-generated':fontcolor=white:fontsize=28:"
        "box=1:boxcolor=0x0b1620@0.72:boxborderw=12:x=64:y=48"
    )
    for name, n in zip(NAMES, counts):
        dest = EDIT / f"seg_{name}.mp4"
        if name == "problem":
            fit_clip(ASSETS / "broll.mp4", n, dest, extra=label)
        elif name == "title":
            title_card(n, dest)
        elif name == "show":
            show = EDIT / "_show.mp4"
            und = EDIT / "_und.mp4"
            show_n = round(n * dur(CAP / "show.mp4") / (dur(CAP / "show.mp4") + dur(CAP / "understand.mp4")))
            fit_clip(CAP / "show.mp4", show_n, show)
            fit_clip(CAP / "understand.mp4", n - show_n, und)
            run([
                FFMPEG, "-y", "-i", str(show), "-i", str(und),
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,fps=30,format=yuv420p[v]",
                "-map", "[v]", "-frames:v", str(n), "-an",
                "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
            ])
        elif name == "questions":
            fit_clip(CAP / "questions.mp4", n, dest)
        elif name == "discover":
            fit_clip(CAP / "discover.mp4", n, dest)
        elif name == "brief":
            brief_segment(n, dest)
        elif name == "compare":
            scroll_still(INS / "compare_full.png", n, dest)
        elif name == "impact":
            impact(n, dest)
        elif name == "live":
            live_segment(n, dest)
        elif name == "architecture":
            hold = max(0, n - round(25.05 * 30))
            body = EDIT / "_arch_body.mp4"
            fit_clip(ARCH, n - hold, body)
            if hold:
                run([
                    FFMPEG, "-y", "-i", str(body),
                    "-vf", f"tpad=stop_mode=clone:stop_duration={hold / 30:.3f},fps=30,format=yuv420p",
                    "-frames:v", str(n), "-an",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
                ])
            else:
                dest = body
        elif name == "outro":
            outro_card(n, dest)
        elif name == "endcard":
            end_card(n, dest)
        segs.append(dest)
    concat = EDIT / "concat.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    picture = EDIT / "picture.mp4"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(picture)])
    return picture


def mix(picture: Path, final: Path) -> None:
    total = 190.5
    voice = EDIT / "voice.wav"
    run([
        FFMPEG, "-y", "-i", str(VOICE),
        "-af", f"apad=whole_dur={total:.3f},aformat=sample_rates=48000:channel_layouts=stereo",
        "-t", f"{total:.3f}", str(voice),
    ])
    music = EDIT / "music.wav"
    run([
        FFMPEG, "-y", "-i", str(ASSETS / "music.wav"),
        "-af",
        f"atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume=0.10,"
        f"afade=t=out:st=187:d=3.5,aformat=sample_rates=48000:channel_layouts=stereo",
        "-t", f"{total:.3f}", str(music),
    ])
    mixed = EDIT / "mixed.wav"
    run([
        FFMPEG, "-y", "-i", str(voice), "-i", str(music),
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:duration=first:normalize=0:dropout_transition=0,"
        "aformat=sample_rates=48000:channel_layouts=stereo[a]",
        "-map", "[a]", "-t", f"{total:.3f}", str(mixed),
    ])
    measured = subprocess.run(
        [FFMPEG, "-i", str(mixed), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    start = measured.stderr.rfind("{")
    end = measured.stderr.rfind("}")
    data = json.loads(measured.stderr[start:end + 1])
    norm = EDIT / "mixed_norm.wav"
    run([
        FFMPEG, "-y", "-i", str(mixed),
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11:"
        f"measured_I={data['input_i']}:measured_TP={data['input_tp']}:"
        f"measured_LRA={data['input_lra']}:measured_thresh={data['input_thresh']}:"
        "linear=true,aformat=sample_rates=48000:channel_layouts=stereo",
        str(norm),
    ])
    run([
        FFMPEG, "-y", "-i", str(picture), "-i", str(norm),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
        "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", "-t", f"{total:.3f}", str(final),
    ])


def main() -> int:
    EDIT.mkdir(parents=True, exist_ok=True)
    counts = frames_for(BOUNDS)
    picture = build_picture(counts)
    final = DEMO / "demo_final.mp4"
    mix(picture, final)
    srt_src = DEMO / "narration_single_take.srt"
    srt = DEMO / "demo_final.srt"
    srt.write_text(srt_src.read_text(encoding="utf-8"), encoding="utf-8")
    sheet = DEMO / "demo_final_frames.png"
    run([
        FFMPEG, "-y", "-i", str(final),
        "-vf", "fps=1/5,scale=320:-2,tile=8x5",
        "-frames:v", "1", "-update", "1", str(sheet),
    ])
    final_d = dur(final)
    report = {
        "file": str(final),
        "srt": str(srt),
        "sheet": str(sheet),
        "narration": "Eb9BvWNuuO",
        "duration_s": round(final_d, 3),
        "size_bytes": final.stat().st_size,
        "segments": [
            {"id": name, "start": BOUNDS[i], "end": BOUNDS[i + 1]}
            for i, name in enumerate(NAMES)
        ],
    }
    (DEMO / "timeline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if not (190 <= final_d <= 192):
        raise SystemExit(f"duration {final_d:.2f}s is outside 3:10–3:12")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
