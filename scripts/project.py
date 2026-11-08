#!/usr/bin/env python3
"""Initialize, validate, and gate a reference-to-video project."""
from __future__ import annotations
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import sys
from common import bundle, check_snapshot, inside, read, sha, snapshot, validate, write

SKILL = Path(__file__).resolve().parents[1]


def initialize(root, topic, reference):
    if not root.is_absolute() or root.resolve() == Path.home():
        raise ValueError("Use an absolute project directory, not the home directory")
    root = root.resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("Project directory is nonempty; resume it or choose a fresh directory")
    is_url = reference.startswith(("http://", "https://"))
    source = None if is_url else Path(reference).expanduser().resolve()
    if source is not None and not source.is_file():
        raise ValueError(f"Local reference does not exist: {source}")
    root.mkdir(parents=True, exist_ok=True)
    for folder in ("reference", "research", "production", "assets", "audio", "demos", "output", "qa", "publish"):
        (root / folder).mkdir()
    shutil.copytree(SKILL / "assets/project", root, dirs_exist_ok=True)
    media = None
    if source:
        target = root / "reference" / ("source" + source.suffix.lower())
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
        media = target.relative_to(root).as_posix()
    logs = Path.home() / "Library/Logs/AI工具/reference-to-video" / root.name if sys.platform == "darwin" else root / ".render/logs"
    project = {"schema_version": 1, "topic": topic, "reference_input": reference,
               "language": "zh-CN", "output": {"width": None, "height": None, "fps": None, "total_frames": None, "file": "output/film.mp4"},
               "renderer": "production/film.mjs", "fonts": [],
               "audio": {"mode": None, "source": None, "reason": ""},
               "render": {"workers": 2, "encoder_threads": 2, "crf": 18},
               "review": {"motion_roi": None, "freeze_seconds": 4, "silence_seconds": .35},
               "logs_dir": str(logs)}
    write(root / "project.json", project)
    write(root / "reference/analysis.json", {"title": "", "source_url": reference if is_url else None, "media": media,
          "reviewed": False, "summary": "", "style": {}, "shots": [], "audio": {}, "transfer": [], "uncertainties": [], "publishing": {}})
    write(root / "episode.json", {"title": topic, "summary": "", "narrative": "", "chapters": [], "scenes": [], "captions": []})
    write(root / "facts.json", {"sources": [], "claims": []})
    write(root / "STATE.json", {"stage": "initialized", "status": "working", "topic": topic,
          "requirements": [], "decisions": [], "corrections": [], "browser_task_space": None,
          "running": None, "stages": {k: "pending" for k in ("reference_html", "topic_html", "video", "review")}, "remaining": ["Observe reference", "Research new topic", "Author topic HTML and scenes", "Render and review final media"]})
    print(json.dumps({"project": str(root), "reference_media": media, "next": "Read contracts; observe reference and set output parameters"}, ensure_ascii=False))


def record_render(root):
    root, project, _, _, _ = validate(root)
    movie = inside(root, project["output"]["file"])
    if not movie.is_file():
        raise ValueError("Render a complete movie first")
    write(root / "qa/render.json", {"status": "rendered", "engine": "external", "movie_sha256": sha(movie), "inputs": snapshot(root, project)})
    print("Recorded external render; mechanical and artistic review still required")


def finish(root):
    root, project, episode, _, _ = validate(root)
    movie = inside(root, project["output"]["file"])
    digest = sha(movie)
    render, media, proofs, review = (read(root / x) for x in ("qa/render.json", "qa/media.json", "qa/proofs.json", "qa/review.json"))
    if render.get("movie_sha256") != digest or not check_snapshot(render.get("inputs", [])) or not render.get("inputs"):
        raise ValueError("Render inputs/movie changed; rebuild before finalization")
    if media.get("movie_sha256") != digest or not media.get("mechanical_pass"):
        raise ValueError("Current complete movie has not passed mechanical checks")
    if proofs.get("movie_sha256") != digest or review.get("media_sha256") != digest:
        raise ValueError("Encoded proofs/review are missing or stale")
    scene_ids = {x["id"] for x in episode["scenes"]}
    checked = review.get("scene_reviews", [])
    if len(checked) != len(scene_ids) or {x.get("scene_id") for x in checked} != scene_ids or any(x.get("status") != "pass" or not x.get("finding") or not x.get("evidence") or not all(x.get(k) for k in ("first", "middle", "last")) for x in checked):
        raise ValueError("Review every scene's encoded first/middle/last and resolve issues")
    expected = {"narrative", "depth", "visual_use", "reference_transfer", "readability", "continuity", "audio"}
    criteria = review.get("criteria", [])
    if len(criteria) != len(expected) or {x.get("id") for x in criteria} != expected or any(x.get("status") not in ("pass", "not_applicable") or not x.get("finding") or not x.get("evidence") for x in criteria):
        raise ValueError("Complete the actual quality findings; numeric success is not an artistic pass")
    candidates = {x["id"] for x in media.get("signals", [])}
    signals = review.get("signals", [])
    if {x.get("id") for x in signals} != candidates or any(x.get("decision") != "keep" or not x.get("finding") for x in signals):
        raise ValueError("Inspect and resolve all media candidates")
    browser = review.get("browser", {})
    if browser.get("status") != "pass" or not browser.get("evidence") or not browser.get("findings"):
        raise ValueError("Run real HTML and media browser checks")
    browser_pages = {"reference.html", "topic.html", "index.html"}
    browser_pages.update(demo["file"] for chapter in episode["chapters"] for demo in chapter.get("demos", []))
    for name in sorted(browser_pages):
        page = inside(root, name)
        if not page.is_file() or browser.get("html_sha256", {}).get(name) != sha(page):
            raise ValueError(f"Browser check missing or stale for {name}")
    if review.get("listening", {}).get("status") not in ("listened", "not_available", "not_required") or not review["listening"].get("finding"):
        raise ValueError("Record actual listening capability and result")
    if review.get("remaining") != []:
        raise ValueError("Resolve remaining required work")
    # Ensure locally cited evidence exists, rather than accepting an invented filename.
    for row in checked + criteria + [browser]:
        for item in row.get("evidence", []):
            if not inside(root, item).is_file():
                raise ValueError(f"Review evidence is missing: {item}")
    for group in proofs["scenes"]:
        if group["scene_id"] not in scene_ids or len(group["frames"]) != 3:
            raise ValueError("Encoded proof coverage is incomplete")
        for frame in group["frames"]:
            if not inside(root, frame["file"]).is_file():
                raise ValueError("An encoded proof image is missing")
    if {x["scene_id"] for x in proofs["scenes"]} != scene_ids:
        raise ValueError("Encoded proof scenes do not match the complete movie")
    manifest = {"status": "complete", "topic": project["topic"], "movie": str(movie), "movie_sha256": digest,
                "reference_html": str(root / "reference.html"), "topic_html": str(root / "topic.html"),
                "source": str(root / project["renderer"]), "limitations": review.get("limitations", []),
                "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "evidence": ["qa/render.json", "qa/media.json", "qa/proofs.json", "qa/review.json"]}
    write(root / "output/delivery.json", manifest)
    state = read(root / "STATE.json")
    state.update({"status": "complete", "stage": "verified_delivery", "running": None, "remaining": [], "artifacts": manifest})
    state["stages"] = {k: "verified" for k in ("reference_html", "topic_html", "video", "review")}
    write(root / "STATE.json", state)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("project", type=Path)
    init.add_argument("--topic", required=True)
    init.add_argument("--reference", required=True)
    for name in ("validate", "record-render", "finish"):
        sub.add_parser(name).add_argument("project", type=Path)
    args = parser.parse_args()
    if args.command == "init":
        initialize(args.project, args.topic, args.reference)
    elif args.command == "validate":
        _, p, e, _, _ = validate(args.project)
        print(json.dumps({"valid_plan": True, "chapters": len(e["chapters"]), "scenes": len(e["scenes"]), "total_frames": p["output"]["total_frames"], "quality_review": "not implied"}))
    elif args.command == "record-render":
        record_render(args.project)
    else:
        finish(args.project)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
