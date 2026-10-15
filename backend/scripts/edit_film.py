"""Assemble demo_final.mp4, demo_final.srt, timeline.json, and a 5-second contact sheet.

Voice is loudness-normalized to -16 LUFS. Music sits about 18 dB under it.
Segment lengths follow the narration files. A 2 second hold separates segments.
Rejects a film shorter than 3:05 or longer than 3:55.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "docs" / "demo"
ASSETS = DEMO / "assets"
CAP = DEMO / "capture"
INS = CAP / "inserts"
WORK = DEMO / "edit"
FONT = ASSETS / "plex-500.ttf"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
GAP = 2.0
ARCH = Path(r"D:\hackathon\ai-opportunity-copilot\architecture_source\architecture_anim.mp4")

NARRATION = [
    ("problem", "n01_problem.mp3", [
        "Every morning, trucks arrive at a small factory with steel wire.",
        "Security writes the vehicle in a paper register.",
        "A clerk matches the delivery challan to the purchase order by hand.",
        "An inspector measures five pieces with a vernier caliper and writes the readings on a sheet.",
        "At night, someone types that sheet into Excel.",
        "The owner knows something should change.",
        "But vendors pitch AI for everything, and it is hard to tell what is worth buying, and harder to compare their proposals fairly.",
    ]),
    ("title", "n02_title.mp3", [
        "This is AI Opportunity Copilot.",
        "It helps a business decide where AI really helps, and what to ask vendors for.",
    ]),
    ("show", "n03_show.mp3", [
        "I describe the work in plain words.",
        "Names, phone numbers and emails are removed before analysis.",
        "Gemini turns my text into a process map.",
        "Every step is labelled: Observation, if I said it, or Assumption, if the model inferred it.",
        "I can edit, reorder, or add steps, and I confirm the map before anything continues.",
    ]),
    ("questions", "n04_questions.mp3", [
        "Then it asks a few questions, and they quote my own process: how often a step happens, what happens when a lot fails, where the records live.",
        "My answers change the estimates later.",
    ]),
    ("discover", "n05_discover.mp3", [
        "It proposes options.",
        "Each one shows the problem, the improvement, a value range and an effort range, always marked as an estimate, and where people stay involved.",
        "This view walks through the process step by step: what stays the same, what changes, what goes away.",
        "And when the right answer is a simple workflow, not AI, it says so.",
    ]),
    ("brief", "n06_brief.mp3", [
        "I choose one and get a brief I can hand to a vendor: scope, assumptions, risks, success measures.",
        "It is a proposal only. Nothing here builds software.",
    ]),
    ("compare", "n07_compare.mp3", [
        "Now the part owners find hardest: comparing proposals.",
        "These are simulated, and labelled that way.",
        "Gemini reads each proposal and extracts the facts.",
        "Then plain code scores five criteria and ranks them. The model never outputs a score.",
        "One proposal hid a line telling the evaluator to rank it first.",
        "It was detected, ignored, flagged, and ranked below the clean ones.",
    ]),
    ("impact", "n11_impact.mp3", [
        "In a few minutes, an owner gets a clear process map, honest options, a vendor-ready brief, and a fair way to compare proposals.",
        "People stay in charge of every decision.",
    ]),
    ("live", "n08_live.mp3", [
        "This is a live run on my own text, sped up.",
        "Each step ticks off when the backend finishes it, not on a timer.",
    ]),
    ("architecture", "n09_architecture.mp3", [
        "Under the hood: Firebase Hosting and anonymous sign-in, Cloud Run for the API, Gemini on Vertex for the reading, Firestore for cases.",
        "Personal text is removed before the model sees it, untrusted text is wrapped and scanned, and if the main model fails, a fallback model takes over.",
        "A live case costs about one rupee forty-five at list price.",
    ]),
    ("outro", "n10_outro.mp3", [
        "Try the sample case, no sign-in needed.",
    ]),
]


def run(args: list[str]) -> None:
    print(" ".join(args[:8]), "...", flush=True)
    subprocess.run(args, check=True)


def dur(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def esc(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def fit(src: Path, seconds: float, dest: Path, ss: float = 0.0, extra_vf: str = "") -> None:
    src_d = dur(src)
    stretch = "setpts=" in extra_vf
    available = max(0.1, src_d - ss)
    vf = []
    if extra_vf:
        vf.append(extra_vf)
    if not stretch and available + 0.05 < seconds:
        vf.append(f"tpad=stop_mode=clone:stop_duration={seconds - available + 0.05:.3f}")
    vf.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p")
    cmd = [FFMPEG, "-y", "-ss", f"{ss:.3f}"]
    if not stretch:
        cmd += ["-t", f"{seconds:.3f}"]
    cmd += [
        "-i", str(src), "-vf", ",".join(vf), "-an", "-t", f"{seconds:.3f}",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ]
    run(cmd)


def overlay_inserts(base: Path, inserts: list[tuple[Path, float, float]], dest: Path) -> None:
    if not inserts:
        return
    cmd = [FFMPEG, "-y", "-i", str(base)]
    for png, _a, _b in inserts:
        cmd += ["-i", str(png)]
    parts = []
    last = "[0:v]"
    for i, (_png, start, length) in enumerate(inserts, start=1):
        out = f"[v{i}]"
        parts.append(f"[{i}:v]scale=1600:-2:flags=lanczos[s{i}]")
        parts.append(
            f"{last}[s{i}]overlay=(W-w)/2:(H-h)/2:enable='between(t,{start:.3f},{(start + length):.3f})'{out}"
        )
        last = out
    parts.append(f"{last}format=yuv420p[vout]")
    cmd += [
        "-filter_complex", ";".join(parts), "-map", "[vout]",
        "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ]
    run(cmd)


def title_card(seconds: float, dest: Path) -> None:
    """Steady hero. No zoom, so the frame does not shake or crop the headline."""
    frames = max(2, round(seconds * 30))
    font = esc(FONT)
    vf = (
        f"[0:v]scale=1680:-2:flags=lanczos[hero];"
        f"color=c=0x0b1620:s=1920x1080:r=30[bg];"
        f"[bg][hero]overlay=(W-w)/2:150,"
        f"drawtext=fontfile='{font}':text='AI Opportunity Copilot':fontcolor=0xf2a23a:fontsize=52:x=(w-text_w)/2:y=48,"
        f"drawtext=fontfile='{font}':text='Where AI really helps, and what to ask vendors for.':fontcolor=white:fontsize=30:x=(w-text_w)/2:y=112,"
        f"format=yuv420p"
    )
    run([
        FFMPEG, "-y", "-loop", "1", "-i", str(INS / "hero.png"),
        "-filter_complex", vf, "-frames:v", str(frames),
        "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ])


def outro_card(seconds: float, compare_still: Path, dest: Path) -> None:
    frames = max(2, round(seconds * 30))
    font = esc(FONT)
    vf = (
        f"[0:v]scale=880:-2:flags=lanczos[a];"
        f"[1:v]scale=880:-2:flags=lanczos[b];"
        f"color=c=0x0b1620:s=1920x1080:r=30[bg];"
        f"[bg][a]overlay=40:180[c];"
        f"[c][b]overlay=980:180,"
        f"drawtext=fontfile='{font}':text='y-srinivasreddy.web.app':fontcolor=0xf2a23a:fontsize=42:x=40:y=760,"
        f"drawtext=fontfile='{font}':text='Try the sample case':fontcolor=white:fontsize=36:x=40:y=830,"
        f"format=yuv420p"
    )
    run([
        FFMPEG, "-y", "-loop", "1", "-i", str(INS / "hero.png"), "-loop", "1", "-i", str(compare_still),
        "-filter_complex", vf, "-frames:v", str(frames),
        "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ])


def live_segment(seconds: float, dest: Path) -> tuple[float, str]:
    """Keep the opening ticks and the finished map at real speed. Speed only the wait between them."""
    src = CAP / "live.mp4"
    src_d = dur(src)
    tail = min(1.8, src_d * 0.2)
    real = min(2.6, max(1.2, seconds - tail - 1.2), src_d - tail - 0.4)
    mid_src = max(0.3, src_d - real - tail)
    mid_out = max(0.4, seconds - real - tail)
    factor = mid_src / mid_out
    label = f"Live run, sped up {factor:.1f}x"
    (WORK / "live_label.txt").write_text(label, encoding="utf-8")
    font = esc(FONT)
    head = WORK / "_live_head.mp4"
    sped = WORK / "_live_sped.mp4"
    end = WORK / "_live_tail.mp4"
    fit(src, real, head, ss=0)
    run([
        FFMPEG, "-y", "-ss", f"{real:.3f}", "-t", f"{mid_src:.3f}", "-i", str(src),
        "-vf", f"setpts=PTS/{factor:.6f},fps=30,scale=1920:1080,format=yuv420p",
        "-an", "-t", f"{mid_out:.3f}", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(sped),
    ])
    fit(src, tail, end, ss=src_d - tail)
    run([
        FFMPEG, "-y", "-i", str(head), "-i", str(sped), "-i", str(end),
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(dest),
    ])
    return factor, label


def srt_time(t: float) -> str:
    if t < 0:
        t = 0
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues: list[tuple[float, float, str]], path: Path) -> None:
    lines = []
    for i, (a, b, text) in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{srt_time(a)} --> {srt_time(b)}")
        lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "tagline.txt").write_text("Where AI really helps,\nand what to ask vendors for.", encoding="utf-8")
    voice_d = {key: dur(ASSETS / name) for key, name, _lines in NARRATION}
    # n03 covers show then understand. Keep the spoken file once.
    show_part = min(9.0, dur(CAP / "show.mp4") - 0.1)
    und_part = voice_d["show"] - show_part

    compare_still = WORK / "compare_still.png"
    run([FFMPEG, "-y", "-ss", "1.0", "-i", str(CAP / "compare.mp4"), "-frames:v", "1", "-update", "1", str(compare_still)])

    pieces: list[tuple[str, Path, float]] = []

    problem = WORK / "seg_problem.mp4"
    fit(
        ASSETS / "broll.mp4", voice_d["problem"], problem,
        extra_vf=f"setpts=PTS*{voice_d['problem'] / dur(ASSETS / 'broll.mp4'):.6f}",
    )
    pieces.append(("problem", problem, voice_d["problem"]))

    title = WORK / "seg_title.mp4"
    title_card(voice_d["title"], title)
    pieces.append(("title", title, voice_d["title"]))

    show = WORK / "seg_show.mp4"
    und = WORK / "seg_understand.mp4"
    fit(CAP / "show.mp4", show_part, show)
    fit(CAP / "understand.mp4", und_part, und)
    show_und = WORK / "seg_show_understand.mp4"
    run([
        FFMPEG, "-y", "-i", str(show), "-i", str(und),
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(show_und),
    ])
    pieces.append(("show", show_und, voice_d["show"]))

    questions = WORK / "seg_questions.mp4"
    fit(CAP / "questions.mp4", voice_d["questions"], questions, ss=1.0)
    pieces.append(("questions", questions, voice_d["questions"]))

    discover = WORK / "seg_discover.mp4"
    fit(CAP / "discover.mp4", voice_d["discover"], discover)
    pieces.append(("discover", discover, voice_d["discover"]))

    brief = WORK / "seg_brief.mp4"
    fit(CAP / "brief.mp4", voice_d["brief"], brief)
    pieces.append(("brief", brief, voice_d["brief"]))

    compare = WORK / "seg_compare.mp4"
    fit(CAP / "compare.mp4", voice_d["compare"], compare)
    pieces.append(("compare", compare, voice_d["compare"]))

    impact_b = WORK / "seg_impact_b.mp4"
    impact_c = WORK / "seg_impact_c.mp4"
    half = voice_d["impact"] / 2
    fit(CAP / "brief.mp4", half, impact_b)
    fit(CAP / "compare.mp4", voice_d["impact"] - half, impact_c)
    impact = WORK / "seg_impact.mp4"
    run([
        FFMPEG, "-y", "-i", str(impact_b), "-i", str(impact_c),
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(impact),
    ])
    pieces.append(("impact", impact, voice_d["impact"]))

    live = WORK / "seg_live.mp4"
    factor, live_label = live_segment(voice_d["live"], live)
    pieces.append(("live", live, voice_d["live"]))

    arch = WORK / "seg_arch.mp4"
    arch_src_d = dur(ARCH)
    fit(
        ARCH, voice_d["architecture"], arch,
        extra_vf=f"setpts=PTS*{voice_d['architecture'] / arch_src_d:.6f}",
    )
    pieces.append(("architecture", arch, voice_d["architecture"]))

    outro = WORK / "seg_outro.mp4"
    outro_card(voice_d["outro"], compare_still, outro)
    pieces.append(("outro", outro, voice_d["outro"]))

    # Holds: 2s clone after every segment except the last.
    held: list[Path] = []
    for i, (key, path, seconds) in enumerate(pieces):
        out = WORK / f"hold_{key}.mp4"
        extra = GAP if i < len(pieces) - 1 else 0
        if extra:
            run([
                FFMPEG, "-y", "-i", str(path),
                "-vf", f"tpad=stop_mode=clone:stop_duration={extra:.3f},fps=30,format=yuv420p",
                "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(out),
            ])
        else:
            out = path
        held.append(out)

    concat = WORK / "concat.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in held), encoding="utf-8")
    silent_picture = WORK / "picture.mp4"
    run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c", "copy", str(silent_picture),
    ])

    # Voice, with 2s silence between narrations. n03 is one file for show+understand.
    voice_inputs: list[Path] = []
    cursor = 0.0
    cues: list[tuple[float, float, str]] = []
    timeline = []
    # Map piece key -> narration lines. show piece uses n03 lines.
    lines_for = {key: lines for key, _name, lines in NARRATION}
    audio_for = {key: ASSETS / name for key, name, _lines in NARRATION}
    for i, (key, _path, seconds) in enumerate(pieces):
        voice_inputs.append(audio_for[key])
        weights = [max(1, len(s)) for s in lines_for[key]]
        total_w = sum(weights)
        local = 0.0
        for sentence, w in zip(lines_for[key], weights):
            span = seconds * w / total_w
            cues.append((cursor + local, cursor + local + span - 0.05, sentence))
            local += span
        end = cursor + seconds + (GAP if i < len(pieces) - 1 else 0)
        timeline.append({
            "id": key,
            "start": round(cursor, 3),
            "end": round(end, 3),
            "voice_s": round(seconds, 3),
        })
        cursor = end
        if key == "live":
            timeline[-1]["caption"] = live_label
            timeline[-1]["speedup"] = round(factor, 2)

    srt_path = DEMO / "demo_final.srt"
    write_srt(cues, srt_path)

    # Build the voice bed: each narration padded with silence to voice_s, then GAP silence except last.
    voice_wavs = []
    for i, (key, _path, seconds) in enumerate(pieces):
        wav = WORK / f"voice_{key}.wav"
        pad = seconds + (GAP if i < len(pieces) - 1 else 0)
        run([
            FFMPEG, "-y", "-i", str(audio_for[key]),
            "-af", f"apad=whole_dur={pad:.3f},aformat=sample_rates=48000:channel_layouts=stereo",
            "-t", f"{pad:.3f}", str(wav),
        ])
        voice_wavs.append(wav)
    vconcat = WORK / "voice_concat.txt"
    vconcat.write_text("".join(f"file '{p.as_posix()}'\n" for p in voice_wavs), encoding="utf-8")
    voice = WORK / "voice.wav"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(vconcat), "-c", "copy", str(voice)])
    voice_n = WORK / "voice_norm.wav"
    run([
        FFMPEG, "-y", "-i", str(voice),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        str(voice_n),
    ])

    total = dur(silent_picture)
    music = WORK / "music_bed.wav"
    run([
        FFMPEG, "-y", "-i", str(ASSETS / "music.wav"),
        "-af", f"atrim=0:{total:.3f},asetpts=PTS-STARTPTS,loudnorm=I=-34:TP=-2:LRA=11,afade=t=out:st={max(0, total - 4):.3f}:d=4",
        "-t", f"{total:.3f}", str(music),
    ])

    final = DEMO / "demo_final.mp4"
    run([
        FFMPEG, "-y", "-i", str(silent_picture), "-i", str(voice_n), "-i", str(music),
        "-filter_complex",
        "[1:a][2:a]amix=inputs=2:duration=first:normalize=0:dropout_transition=0,aformat=sample_rates=48000:channel_layouts=stereo[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
        "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", "-t", f"{total:.3f}", str(final),
    ])

    sheet = DEMO / "demo_final_frames.png"
    run([
        FFMPEG, "-y", "-i", str(final),
        "-vf", "fps=1/5,scale=320:-2,tile=8x5",
        "-frames:v", "1", "-update", "1", str(sheet),
    ])
    final_d = dur(final)
    size = final.stat().st_size
    report = {
        "file": str(final),
        "srt": str(srt_path),
        "sheet": str(sheet),
        "duration_s": round(final_d, 3),
        "size_bytes": size,
        "live_caption": live_label,
        "segments": timeline,
    }
    (DEMO / "timeline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if not (185 <= final_d <= 235):
        raise SystemExit(f"duration {final_d:.2f}s is outside 3:05–3:55")
    if size > 150 * 1024 * 1024:
        raise SystemExit(f"file is {size} bytes, over 150 MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
