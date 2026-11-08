"""Shared local-only project contracts. No network calls or artistic verdicts."""
from __future__ import annotations
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(root, value):
    root = Path(root).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path must stay inside project: {value}")
    return path


def bundle(root):
    root = Path(root).resolve()
    return root, read(root / "project.json"), read(root / "episode.json"), read(root / "facts.json"), read(root / "reference/analysis.json")


def rate(project):
    value = Fraction(str(project["output"]["fps"]))
    if value <= 0 or value > 240:
        raise ValueError("Set output.fps to a positive frame rate, at most 240")
    return value


def frame_at(seconds, fps):
    # Nonnegative half-up rounding, identical to JS Math.round.
    return math.floor(float(seconds) * float(fps) + .5)


def _spans(items, label, fps, total):
    if not items:
        raise ValueError(f"{label} is empty")
    ids, previous, intervals = set(), 0, {}
    for item in items:
        key = item.get("id")
        if not key or key in ids:
            raise ValueError(f"Missing or duplicate {label} id: {key}")
        ids.add(key)
        start, end = float(item["start"]), float(item["end"])
        if not math.isfinite(start + end) or start < 0:
            raise ValueError(f"Invalid {label} time: {key}")
        a, b = frame_at(start, fps), frame_at(end, fps)
        if a != previous or b <= a:
            raise ValueError(f"{label} has gap/overlap/empty span at {key}: {a}:{b}; expected {previous}")
        intervals[key] = (a, b)
        previous = b
    if previous != total:
        raise ValueError(f"{label} ends at frame {previous}, expected {total}")
    return intervals


def validate(root):
    root, project, episode, facts, reference = bundle(root)
    output = project["output"]
    for dim in ("width", "height"):
        value = output.get(dim)
        if not isinstance(value, int) or value < 2 or value % 2:
            raise ValueError(f"Set output.{dim} to a positive even integer")
    fps = rate(project)
    total = output.get("total_frames")
    if not isinstance(total, int) or total < 1:
        raise ValueError("Set output.total_frames from the intended complete duration")
    inside(root, output["file"])
    if not inside(root, project["renderer"]).is_file():
        raise ValueError("Editable renderer source is missing")
    audio = project.get("audio", {})
    if audio.get("mode") not in ("copy-full", "prepared", "none"):
        raise ValueError("Choose audio.mode: copy-full, prepared or none")
    if audio["mode"] == "none":
        if not audio.get("reason"):
            raise ValueError("Explain why this project should be silent")
    elif not inside(root, audio.get("source", "")).is_file():
        raise ValueError("Audio source is missing; do not silently output a silent movie")
    for font in project.get("fonts", []):
        if not Path(font["path"]).is_file() or not font.get("family"):
            raise ValueError(f"Font path/family is invalid: {font}")
    if not episode.get("title") or not episode.get("summary"):
        raise ValueError("Write the new topic title and explanation summary")
    chapters = _spans(episode.get("chapters", []), "chapters", fps, total)
    scenes = _spans(episode.get("scenes", []), "scenes", fps, total)
    for chapter in episode["chapters"]:
        for key in ("setup", "process", "result", "explanation", "example", "qualification"):
            if not str(chapter.get(key, "")).strip():
                raise ValueError(f"Chapter {chapter['id']} needs {key}; do not replace explanation with a counter")
        for demo in chapter.get("demos", []):
            if not inside(root, demo["file"]).is_file() or not demo.get("purpose"):
                raise ValueError(f"Missing demo or its explanatory purpose: {demo}")
    for scene in episode["scenes"]:
        for key in ("title", "opening", "development", "outcome", "action", "transition"):
            if not scene.get(key):
                raise ValueError(f"Scene {scene['id']} needs {key}")
        parent = scene.get("chapter_id")
        if parent not in chapters or not (chapters[parent][0] <= scenes[scene['id']][0] < scenes[scene['id']][1] <= chapters[parent][1]):
            raise ValueError(f"Scene {scene['id']} falls outside its chapter")
        if not scene.get("layers") or any(not x.get("element") or not x.get("purpose") for x in scene["layers"]):
            raise ValueError(f"Scene {scene['id']} needs elements with specific purposes")
    previous = 0
    for cue in episode.get("captions", []):
        a, b = frame_at(cue["start"], fps), frame_at(cue["end"], fps)
        if a < previous or b <= a or b > total or not cue.get("text"):
            raise ValueError(f"Invalid/overlapping caption: {cue}")
        previous = b
    sources = {x["id"]: x for x in facts.get("sources", [])}
    claims = {x["id"]: x for x in facts.get("claims", [])}
    if not claims or len(claims) != len(facts["claims"]):
        raise ValueError("Write a fact/teaching ledger with unique claim IDs")
    for claim in claims.values():
        status = claim.get("status")
        if status not in ("verified", "teaching", "inference") or not claim.get("text"):
            raise ValueError(f"Resolve or qualify unverified claim: {claim.get('id')}")
        if status == "teaching":
            if not claim.get("assumptions"):
                raise ValueError(f"Specify teaching assumptions: {claim['id']}")
        else:
            if not claim.get("source_ids") or not claim.get("evidence"):
                raise ValueError(f"Claim {claim['id']} needs real sources and evidence")
            for sid in claim["source_ids"]:
                source = sources.get(sid, {})
                if not source.get("checked_at") or not source.get("title") or not (source.get("url", "").startswith(("http://", "https://")) or (source.get("file") and inside(root, source["file"]).is_file())):
                    raise ValueError(f"Missing source/verification record: {sid}")
            if status == "inference" and not claim.get("qualification"):
                raise ValueError(f"Label the inference and its limits: {claim['id']}")
    for chapter in episode["chapters"]:
        if not chapter.get("fact_ids") or any(x not in claims for x in chapter["fact_ids"]):
            raise ValueError(f"Chapter {chapter['id']} must link to facts or declared teaching assumptions")
    if reference.get("reviewed") is not True or not reference.get("shots") or not reference.get("transfer"):
        raise ValueError("Complete the observed reference analysis before claiming style transfer")
    seen = set()
    for shot in reference["shots"]:
        if not shot.get("id") or shot["id"] in seen:
            raise ValueError("Reference shots require unique IDs")
        seen.add(shot["id"])
        if any(not shot.get(k) for k in ("title", "opening", "development", "outcome")) or float(shot["end"]) <= float(shot["start"]):
            raise ValueError(f"Observe reference first/middle/last: {shot.get('id')}")
        evidence = shot.get("evidence", [])
        if len(evidence) < 3:
            raise ValueError(f"Reference shot {shot['id']} needs three observed frames")
        for frame in evidence:
            if not inside(root, frame["image"]).is_file() or not float(shot["start"]) <= float(frame["time"]) <= float(shot["end"]):
                raise ValueError(f"Invalid reference frame evidence: {shot['id']}")
    return root, project, episode, facts, reference


def snapshot(root, project):
    root = Path(root).resolve()
    paths = {root / name for name in ("project.json", "episode.json", "facts.json", "reference/analysis.json", "package.json", "scripts/render.mjs")}
    for name in ("production", "assets", "audio"):
        folder = root / name
        if folder.is_dir():
            paths.update(x for x in folder.rglob("*") if x.is_file())
    paths.add(inside(root, project["renderer"]))
    if project["audio"]["mode"] != "none":
        paths.add(inside(root, project["audio"]["source"]))
    paths.update(Path(f["path"]).resolve() for f in project.get("fonts", []))
    return [{"path": str(p), "sha256": sha(p)} for p in sorted(paths) if p.is_file()]


def check_snapshot(items):
    return all(Path(x["path"]).is_file() and sha(x["path"]) == x["sha256"] for x in items)
