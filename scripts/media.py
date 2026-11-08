#!/usr/bin/env python3
"""Local media inspection, final-file checks and encoded proof extraction."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from common import frame_at, inside, read, sha, validate, write


def run(args):
    process = subprocess.run(args, capture_output=True, text=True)
    if process.returncode:
        raise ValueError(f"{args[0]} failed: {process.stderr[-4000:]}")
    return process


def probe(file):
    if not Path(file).is_file():
        raise ValueError(f"A local readable media file is required: {file}")
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(file)]).stdout)


def pcm_hash(file, logs):
    logs.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    with tempfile.TemporaryFile(dir=logs) as errors:
        process = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(file), "-map", "0:a:0", "-vn", "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"], stdout=subprocess.PIPE, stderr=errors)
        for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
        if process.wait():
            errors.seek(0)
            raise ValueError("PCM decode failed: " + errors.read().decode("utf-8", "replace")[-3000:])
    return {"sha256_float_pcm": digest.hexdigest(), "bytes": size}


def interval_signals(log, prefix, duration):
    signals, active = [], None
    pattern = re.compile(rf"{prefix}_(start|end)\s*[:=]\s*(-?[0-9.]+)")
    for kind, text in pattern.findall(log):
        value = max(0, float(text))
        if kind == "start":
            active = value
        elif active is not None:
            signals.append({"start": active, "end": value, "duration": max(0, value - active)})
            active = None
    if active is not None and active < duration:
        signals.append({"start": active, "end": duration, "duration": duration - active})
    return signals


def verify(root):
    root, project, episode, _, _ = validate(root)
    file = inside(root, project["output"]["file"])
    digest, metadata = sha(file), probe(file)
    video = next((s for s in metadata["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ValueError("Final output has no video stream")
    fps = Fraction(str(project["output"]["fps"]))
    expected_frames = project["output"]["total_frames"]
    duration = expected_frames / float(fps)
    actual_frames = video.get("nb_frames")
    if actual_frames in (None, "N/A"):
        actual_frames = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(file)]).stdout.strip()
    checks = {
        "dimensions": (video["width"], video["height"]) == (project["output"]["width"], project["output"]["height"]),
        "fps": Fraction(video["r_frame_rate"]) == fps,
        "complete_frame_count": int(actual_frames) == expected_frames,
        "video_duration": abs(float(video.get("duration", metadata["format"]["duration"])) - duration) <= max(.02, 1 / float(fps)),
    }
    decoded = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(file), "-f", "null", "-"], capture_output=True, text=True)
    checks["full_decode"] = decoded.returncode == 0 and not decoded.stderr.strip()
    audio = next((s for s in metadata["streams"] if s["codec_type"] == "audio"), None)
    mode = project["audio"]["mode"]
    checks["audio_presence"] = (audio is None) if mode == "none" else (audio is not None)
    audio_result = {"mode": mode}
    if audio:
        audio_end = float(audio.get("start_time", 0)) + float(audio.get("duration", metadata["format"]["duration"]))
        checks["audio_coverage"] = float(audio.get("start_time", 0)) <= .1 and abs(audio_end - duration) <= .15
    if mode == "copy-full" and audio:
        logs = Path(project["logs_dir"])
        source = inside(root, project["audio"]["source"])
        source_track = next(s for s in probe(source)["streams"] if s["codec_type"] == "audio")
        original, exported = pcm_hash(source, logs), pcm_hash(file, logs)
        checks["pcm_identity"] = original == exported and (source_track.get("sample_rate"), source_track.get("channels")) == (audio.get("sample_rate"), audio.get("channels"))
        audio_result.update({"source": str(source), "original": original, "exported": exported, "same_decoded_samples": checks["pcm_identity"]})
    review = project.get("review", {})
    filters = ["blackdetect=d=0.08:pic_th=0.999:pix_th=0.02"]
    roi = review.get("motion_roi")
    if roi is not None:
        if len(roi) != 4 or any(not isinstance(x, (int, float)) for x in roi) or min(roi) < 0 or roi[2] <= 0 or roi[3] <= 0 or roi[0] + roi[2] > 1.000001 or roi[1] + roi[3] > 1.000001:
            raise ValueError("motion_roi is [x,y,width,height] normalized within the frame")
        x, y = int(roi[0] * video["width"]), int(roi[1] * video["height"])
        w, h = max(2, int(roi[2] * video["width"])), max(2, int(roi[3] * video["height"]))
        filters.append(f"crop={w}:{h}:{x}:{y}")
    filters.append(f"freezedetect=n=-60dB:d={review.get('freeze_seconds', 4)}")
    visual = run(["ffmpeg", "-hide_banner", "-i", str(file), "-an", "-vf", ",".join(filters), "-f", "null", "-"]).stderr
    candidates = []
    for kind, prefix in (("near_static", "freeze"), ("black", "black")):
        for interval in interval_signals(visual, prefix, duration):
            candidates.append({"kind": kind, **interval})
    if audio:
        sound = run(["ffmpeg", "-hide_banner", "-i", str(file), "-map", "0:a:0", "-vn", "-af", f"silencedetect=n=-50dB:d={review.get('silence_seconds', .35)}", "-f", "null", "-"]).stderr
        candidates.extend({"kind": "silence", **x} for x in interval_signals(sound, "silence", duration))
    candidates.sort(key=lambda x: (x["start"], x["kind"]))
    for i, candidate in enumerate(candidates):
        candidate["id"] = f"signal-{i + 1:04d}"
    if sha(file) != digest:
        raise ValueError("Final movie changed during verification")
    report = {"movie": str(file), "movie_sha256": digest, "mechanical_pass": all(checks.values()), "checks": checks,
              "video": {"width": video["width"], "height": video["height"], "fps": video["r_frame_rate"], "frames": int(actual_frames), "duration": duration},
              "audio": audio_result, "decode_errors": decoded.stderr, "signals": candidates,
              "motion_roi": roi, "limits": ["Signals are candidates, not artistic verdicts.", "Whole-frame motion checks may be influenced by caption changes." if roi is None else "Only the declared motion region was checked for freezes.", "A copied mixed soundtrack is not an isolated music stem."]}
    write(root / "qa/media.json", report)
    print(json.dumps({"mechanical_pass": report["mechanical_pass"], "checks": checks, "review_candidates": len(candidates)}, ensure_ascii=False))
    if not report["mechanical_pass"]:
        raise ValueError("Current movie failed mechanical verification; inspect qa/media.json")


def balanced(items):
    if len(items) == 1:
        return items[0]
    mid = len(items) // 2
    return "(" + balanced(items[:mid]) + "+" + balanced(items[mid:]) + ")"


def proofs(root, max_edge):
    root, project, episode, _, _ = validate(root)
    file = inside(root, project["output"]["file"])
    digest = sha(file)
    fps = Fraction(str(project["output"]["fps"]))
    target = root / "qa" / ("proofs-" + digest[:12])
    raw = root / ".render" / ("extract-" + digest[:12])
    target.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    groups, selected = [], set()
    for i, scene in enumerate(episode["scenes"]):
        start, end = frame_at(scene["start"], fps), frame_at(scene["end"], fps)
        length = end - start
        values = [start + min(frame_at(.4, fps), (length - 1) // 4), (start + end - 1) // 2, end - 1 - min(frame_at(.15, fps), (length - 1) // 4)]
        group = {"scene_id": scene["id"], "title": scene["title"], "frames": []}
        for phase, frame in zip(("first", "middle", "last"), values):
            selected.add(frame)
            name = f"scene-{i + 1:04d}-{phase}.jpg"
            group["frames"].append({"phase": phase, "frame": frame, "time": frame / float(fps), "file": (target / name).relative_to(root).as_posix()})
        groups.append(group)
    numbers = sorted(selected)
    expression = balanced([f"eq(n,{n})" for n in numbers])
    vf = f"select='{expression}',scale={max_edge}:{max_edge}:force_original_aspect_ratio=decrease"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(file), "-vf", vf, "-fps_mode", "vfr", "-q:v", "2", "-y", str(raw / "frame-%05d.jpg")])
    lookup = {frame: raw / f"frame-{i + 1:05d}.jpg" for i, frame in enumerate(numbers)}
    all_frames = [f for group in groups for f in group["frames"]]
    for i, frame in enumerate(all_frames):
        source = lookup[frame["frame"]]
        if not source.is_file():
            raise ValueError(f"Encoded frame missing: {frame['frame']}")
        shutil.copy2(source, root / frame["file"])
        shutil.copy2(source, target / f"sample-{i + 1:05d}.jpg")
    width, height = project["output"]["width"], project["output"]["height"]
    rows, thumb = (3, 360) if height > width else (5, 640)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-framerate", "1", "-i", str(target / "sample-%05d.jpg"), "-vf", f"scale={thumb}:-1,tile=3x{rows}:padding=4:margin=8:color=0x0b0d0c", "-q:v", "2", "-y", str(target / "contact-%03d.jpg")])
    sheets = [p.relative_to(root).as_posix() for p in sorted(target.glob("contact-*.jpg"))]
    if sha(file) != digest:
        raise ValueError("Final movie changed while extracting proofs")
    report = {"movie_sha256": digest, "provenance": "extracted from final encoded MP4", "scenes": groups, "contact_sheets": sheets}
    write(root / "qa/proofs.json", report)
    body = []
    for group in groups:
        images = "".join(f'<figure><img src="{Path(f["file"]).name}" alt="{f["phase"]}"><figcaption>{f["phase"]} · {f["time"]:.3f}s · frame {f["frame"]}</figcaption></figure>' for f in group["frames"])
        body.append(f'<section><h2>{html.escape(group["scene_id"])} · {html.escape(group["title"])}</h2><div>{images}</div></section>')
    page = '<!doctype html><meta charset="utf-8"><title>最终编码帧复核</title><style>body{background:#101514;color:#eee6d2;font:16px sans-serif;margin:24px}section{margin:32px 0}section>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0}img{width:100%}figcaption{padding:8px}</style><h1>最终MP4 · 首中尾帧</h1>' + "".join(body)
    (target / "index.html").write_text(page, encoding="utf-8")
    print(json.dumps({"encoded_frames": len(all_frames), "unique_frames": len(numbers), "contact_sheets": len(sheets), "gallery": str(target / "index.html")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--out", type=Path)
    sub.add_parser("verify").add_argument("project", type=Path)
    proof = sub.add_parser("proofs")
    proof.add_argument("project", type=Path)
    proof.add_argument("--max-edge", type=int, default=1280)
    args = parser.parse_args()
    if args.command == "inspect":
        result = probe(args.input)
        if args.out:
            write(args.out, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "verify":
        verify(args.project)
    else:
        if args.max_edge < 64:
            raise ValueError("Use a useful proof image resolution (at least 64px)")
        proofs(args.project, args.max_edge)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
