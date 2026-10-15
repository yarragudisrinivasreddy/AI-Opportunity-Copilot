"""Replace narration 9 only, retime the architecture picture, and append the end card.

Segments 1-8 and 10 keep their existing picture and voice. Captions stay in the
sidecar .srt and are not burned onto the screens.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "docs" / "demo"
EDIT = DEMO / "edit"
ASSETS = DEMO / "assets"
FONT = ASSETS / "plex-500.ttf"
ARCH = Path(r"D:\hackathon\ai-opportunity-copilot\architecture_source\architecture_anim.mp4")
TAKE = EDIT / "takes" / "take3_huJDN0KvqL.mp3"
END_PNG = ASSETS / "end_card_thankyou_1920x1080.png"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
GAP = 2.0
END_S = 3.0

# Film order. Impact is narration 11 and plays before the live line.
SEGMENTS = [
    ("problem", "hold_problem.mp4", [
        "Every morning, trucks arrive at a small factory with steel wire.",
        "Security writes the vehicle in a paper register.",
        "A clerk matches the delivery challan to the purchase order by hand.",
        "An inspector measures five pieces with a vernier caliper and writes the readings on a sheet.",
        "At night, someone types that sheet into Excel.",
        "The owner knows something should change.",
        "But vendors pitch AI for everything, and it is hard to tell what is worth buying, and harder to compare their proposals fairly.",
    ]),
    ("title", "hold_title.mp4", [
        "This is AI Opportunity Copilot.",
        "It helps a business decide where AI really helps, and what to ask vendors for.",
    ]),
    ("show", "hold_show.mp4", [
        "I describe the work in plain words.",
        "Names, phone numbers and emails are removed before analysis.",
        "Gemini turns my text into a process map.",
        "Every step is labelled: Observation, if I said it, or Assumption, if the model inferred it.",
        "I can edit, reorder, or add steps, and I confirm the map before anything continues.",
    ]),
    ("questions", "hold_questions.mp4", [
        "Then it asks a few questions, and they quote my own process: how often a step happens, what happens when a lot fails, where the records live.",
        "My answers change the estimates later.",
    ]),
    ("discover", "hold_discover.mp4", [
        "It proposes options.",
        "Each one shows the problem, the improvement, a value range and an effort range, always marked as an estimate, and where people stay involved.",
        "This view walks through the process step by step: what stays the same, what changes, what goes away.",
        "And when the right answer is a simple workflow, not AI, it says so.",
    ]),
    ("brief", "hold_brief.mp4", [
        "I choose one and get a brief I can hand to a vendor: scope, assumptions, risks, success measures.",
        "It is a proposal only. Nothing here builds software.",
    ]),
    ("compare", "hold_compare.mp4", [
        "Now the part owners find hardest: comparing proposals.",
        "These are simulated, and labelled that way.",
        "Gemini reads each proposal and extracts the facts.",
        "Then plain code scores five criteria and ranks them. The model never outputs a score.",
        "One proposal hid a line telling the evaluator to rank it first.",
        "It was detected, ignored, flagged, and ranked below the clean ones.",
    ]),
    ("impact", "hold_impact.mp4", [
        "In a few minutes, an owner gets a clear process map, honest options, a vendor-ready brief, and a fair way to compare proposals.",
        "People stay in charge of every decision.",
    ]),
    ("live", "hold_live.mp4", [
        "This is a live run on my own text, sped up.",
        "Each step ticks off when the backend finishes it, not on a timer.",
    ]),
    ("architecture", "hold_architecture_new.mp4", [
        "Under the hood: Firebase Hosting and anonymous sign-in, Cloud Run for the API, Gemini on Vertex for the reading, Firestore for cases.",
        "Personal text is removed before the model sees it, untrusted text is wrapped and scanned, and if the main model fails, a fallback model takes over.",
        "A live case costs about one rupee forty-five at list price.",
    ]),
    ("outro", "seg_outro.mp4", [
        "Try the sample case, no sign-in needed.",
    ]),
    ("endcard", "seg_endcard.mp4", []),
]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    print(" ".join(args[:10]), "...", flush=True)
    return subprocess.run(args, check=True, capture_output=True, text=True)


def dur(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def esc(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def loudness(path: Path) -> dict[str, float]:
    proc = subprocess.run(
        [FFMPEG, "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.S)
    if not match:
        raise RuntimeError(proc.stderr[-2000:])
    data = json.loads(match.group(0))
    return {key: float(data[key]) for key in ("input_i", "input_tp", "input_lra", "input_thresh")}


def match_loudness(src: Path, dest: Path) -> dict[str, float]:
    """Match the other segments: about -16 LUFS, true peak -2.8 dBTP."""
    measured = loudness(src)
    run([
        FFMPEG, "-y", "-i", str(src),
        "-af",
        "loudnorm=I=-16:TP=-2.8:LRA=11:"
        f"measured_I={measured['input_i']}:"
        f"measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:"
        "linear=true:print_format=summary,"
        "aformat=sample_rates=48000:channel_layouts=stereo",
        str(dest),
    ])
    return loudness(dest)


def srt_time(t: float) -> str:
    ms = max(0, int(round(t * 1000)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> int:
    shutil.copyfile(TAKE, ASSETS / "n09_architecture.mp3")
    norm = EDIT / "n09_matched.wav"
    after = match_loudness(TAKE, norm)
    print("matched", after, flush=True)
    voice_d = dur(norm)
    voice_frames = max(1, math.ceil(voice_d * 30 - 1e-6))
    arch_frames = voice_frames + round(GAP * 30)
    arch_d = arch_frames / 30

    src_d = dur(ARCH)
    body = EDIT / "arch_body.mp4"
    run([
        FFMPEG, "-y", "-i", str(ARCH),
        "-vf", f"setpts=PTS*{voice_d / src_d:.8f},fps=30,scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p",
        "-frames:v", str(voice_frames), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(body),
    ])
    hold = EDIT / "hold_architecture_new.mp4"
    run([
        FFMPEG, "-y", "-i", str(body),
        "-vf", f"tpad=stop_mode=clone:stop_duration={GAP:.3f},fps=30,format=yuv420p",
        "-frames:v", str(arch_frames), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(hold),
    ])

    font = esc(FONT)
    end = EDIT / "seg_endcard.mp4"
    run([
        FFMPEG, "-y", "-loop", "1", "-i", str(END_PNG),
        "-vf",
        "scale=1920:1080:flags=lanczos,setsar=1,"
        f"drawtext=fontfile='{font}':text='y-srinivasreddy.web.app':fontcolor=white:fontsize=28:"
        "box=1:boxcolor=black@0.60:boxborderw=12:x=w-text_w-72:y=h-th-56,"
        "fade=t=in:st=0:d=0.3,fade=t=out:st=2.700:d=0.3,format=yuv420p",
        "-frames:v", str(round(END_S * 30)), "-an",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", str(end),
    ])

    prefix = 0.0
    for key, name, _lines in SEGMENTS:
        if key == "architecture":
            break
        prefix += dur(EDIT / name)
    outro_d = dur(EDIT / "seg_outro.mp4")
    # Segment 10 in the existing voice bed. Do not move or re-level it.
    outro_audio_at = 190.80

    voice = EDIT / "voice_v2.wav"
    run([
        FFMPEG, "-y",
        "-i", str(EDIT / "voice_norm.wav"),
        "-i", str(norm),
        "-f", "lavfi", "-t", f"{END_S:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-filter_complex",
        f"[0:a]atrim=0:{prefix:.6f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[head];"
        f"[1:a]apad=whole_dur={arch_d:.6f},atrim=0:{arch_d:.6f},asetpts=PTS-STARTPTS[arch];"
        f"[0:a]atrim={outro_audio_at:.6f}:{outro_audio_at + 2.56:.6f},asetpts=PTS-STARTPTS,aresample=48000,"
        f"apad=whole_dur={outro_d:.6f},aformat=channel_layouts=stereo[outro];"
        f"[2:a]aformat=channel_layouts=stereo[tail];"
        f"[head][arch][outro][tail]concat=n=4:v=0:a=1[a]",
        "-map", "[a]", str(voice),
    ])

    concat = EDIT / "concat_v2.txt"
    lines = []
    for _key, name, _text in SEGMENTS:
        lines.append(f"file '{(EDIT / name).as_posix()}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    picture = EDIT / "picture_v2.mp4"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(picture)])

    total = dur(picture)
    music = EDIT / "music_bed_v2.wav"
    run([
        FFMPEG, "-y", "-i", str(ASSETS / "music.wav"),
        "-af",
        f"atrim=0:{total:.3f},asetpts=PTS-STARTPTS,loudnorm=I=-34:TP=-2:LRA=11,"
        f"afade=t=out:st={max(0, total - END_S):.3f}:d={END_S:.3f},"
        "aformat=sample_rates=48000:channel_layouts=stereo",
        "-t", f"{total:.3f}", str(music),
    ])

    final = DEMO / "demo_final.mp4"
    run([
        FFMPEG, "-y", "-i", str(picture), "-i", str(voice), "-i", str(music),
        "-filter_complex",
        "[1:a][2:a]amix=inputs=2:duration=first:normalize=0:dropout_transition=0,"
        "aformat=sample_rates=48000:channel_layouts=stereo[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
        "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", "-t", f"{total:.3f}", str(final),
    ])

    # Sidecar only. Nothing is burned over the app screens.
    cursor = 0.0
    cues: list[tuple[float, float, str]] = []
    timeline = []
    for key, name, sentences in SEGMENTS:
        length = dur(EDIT / name)
        if key == "architecture":
            spoken = voice_d
        elif key == "endcard":
            spoken = 0.0
        elif key == "outro":
            spoken = 2.56
        else:
            spoken = max(0.1, length - GAP)
        if sentences:
            weights = [max(1, len(s)) for s in sentences]
            total_w = sum(weights)
            local = 0.0
            for sentence, weight in zip(sentences, weights):
                span = spoken * weight / total_w
                cues.append((cursor + local, cursor + local + span - 0.05, sentence))
                local += span
        timeline.append({
            "id": key,
            "start": round(cursor, 3),
            "end": round(cursor + length, 3),
            "voice_s": round(spoken, 3),
        })
        cursor += length

    srt = DEMO / "demo_final.srt"
    blocks = []
    for i, (a, b, text) in enumerate(cues, start=1):
        blocks.append(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n")
    srt.write_text("\n".join(blocks), encoding="utf-8")

    final_d = dur(final)
    report = {
        "file": str(final),
        "srt": str(srt),
        "duration_s": round(final_d, 3),
        "size_bytes": final.stat().st_size,
        "segment9_creation": "huJDN0KvqL",
        "segment9_voice_s": round(voice_d, 3),
        "segment9_loudness": after,
        "segments": timeline,
    }
    (DEMO / "timeline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if not (195 <= final_d <= 220):
        raise SystemExit(f"duration {final_d:.2f}s is outside 3:15–3:40")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
