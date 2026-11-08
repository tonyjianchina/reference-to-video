#!/usr/bin/env python3
"""Build real reference and topic HTML from authored observations and knowledge."""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote
from common import check_snapshot, inside, read, sha, validate, write

SKILL = Path(__file__).resolve().parents[1]
escape = lambda text: html.escape(str(text), quote=True)


def paragraphs(text):
    return "".join(f"<p>{escape(x)}</p>" for x in str(text).split("\n") if x.strip())


def href(root, path):
    resolved = inside(root, path)
    if not resolved.is_file():
        raise ValueError(f"HTML asset does not exist: {path}")
    return quote(resolved.relative_to(root).as_posix(), safe="/")


def url(value):
    value = str(value or "")
    return escape(value) if value.startswith(("https://", "http://")) else None


def theme(reference):
    values = reference.get("style", {}).get("palette", {})
    if not isinstance(values, dict):
        values = {}
    defaults = {"background": "#f2eee6", "foreground": "#222b2b", "accent": "#8b4b35", "secondary": "#35656b"}
    for key, value in defaults.items():
        candidate = values.get(key, value)
        if not isinstance(candidate, str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", candidate):
            candidate = value
        defaults[key] = candidate
    def blend(a, b, ratio):
        return "#" + "".join(f"{round(int(a[i:i+2],16)*(1-ratio)+int(b[i:i+2],16)*ratio):02x}" for i in (1, 3, 5))
    bg, fg = defaults["background"], defaults["foreground"]
    return f"--bg:{bg};--fg:{fg};--accent:{defaults['accent']};--secondary:{defaults['secondary']};--muted:{blend(bg,fg,.72)};--line:{blend(bg,fg,.25)};--panel:{blend(bg,fg,.055)}"


def shell(root, name, title, body, reference):
    template = (SKILL / "assets/report-shell.html").read_text(encoding="utf-8")
    template = template.replace("@@TITLE@@", escape(title)).replace("@@THEME@@", theme(reference)).replace("@@BODY@@", body)
    (root / name).write_text(template, encoding="utf-8")


def nav(topic_exists):
    target = '<a href="topic.html">新话题图解</a>' if topic_exists else '<span class="small">新话题制作中</span>'
    return f'<nav class="top"><strong>参考 · 理解 · 再创作</strong><a href="index.html">入口</a><a href="reference.html">参考片拆解</a>{target}</nav>'


def time(seconds):
    return f"{int(float(seconds)//60):02d}:{int(float(seconds)%60):02d}"


def jump(seconds, can_play, label=None):
    text = escape(label or time(seconds))
    return f'<button class="time" data-seek="{float(seconds)}">{text}</button>' if can_play else f'<span class="small">{text}</span>'


def player(root, media, entries):
    if media:
        movie = f'<video data-main controls preload="metadata" playsinline src="{href(root,media)}"></video><div class="actions"><a href="{href(root,media)}">打开视频文件</a></div>'
    else:
        movie = '<div class="placeholder">影片尚未生成或本地媒体不可用；以下文字、图解和实际帧可独立阅读。</div>'
    buttons = []
    for i, item in enumerate(entries):
        text = f'<time>{time(item["start"])}</time>{escape(item["title"])}'
        if media:
            buttons.append(f'<button data-seek="{float(item["start"])}" data-start="{float(item["start"])}" data-end="{float(item["end"])}" aria-current="{str(i==0).lower()}">{text}</button>')
        else:
            buttons.append(f'<a href="#unit-{escape(item["id"])}">{text}</a>')
    return '<div class="screen"><div>'+movie+'</div><nav class="chapters" aria-label="章节定位">'+"".join(buttons)+'</nav></div>'


def triptych(root, frames):
    if not frames:
        return ""
    items = []
    for item in frames:
        path = item.get("image", item.get("file"))
        if not path:
            continue
        note = item.get("note", item.get("phase", ""))
        stamp = f'{float(item["time"]):.2f}s' if "time" in item else ""
        items.append(f'<figure><a href="{href(root,path)}" target="_blank"><img src="{href(root,path)}" loading="lazy" alt="{escape(note or stamp)}"></a><figcaption>{escape(stamp)} {escape(note)}</figcaption></figure>')
    return '<div class="triptych">'+"".join(items)+'</div>'


def progression(start, process, result):
    return '<div class="progression">'+"".join(f'<div><b>{label}</b>{paragraphs(value)}</div>' for label, value in (("建立",start),("过程",process),("后果",result)))+'</div>'


def readable(value):
    if isinstance(value, dict):
        return '<dl>'+"".join(f'<dt>{escape(k)}</dt><dd>{readable(v)}</dd>' for k,v in value.items())+'</dl>'
    if isinstance(value, list):
        return '<ul>'+"".join(f'<li>{readable(v)}</li>' for v in value)+'</ul>'
    return escape(value)


def reference_page(root, reference, topic_exists):
    if not reference.get("title") or not reference.get("summary") or not reference.get("shots"):
        raise ValueError("Observe and describe the reference before generating its HTML")
    media = reference.get("media")
    source = url(reference.get("source_url"))
    body = nav(topic_exists) + f'<header><div class="kicker">参考片 / 叙事与视听拆解</div><h1>{escape(reference["title"])}</h1><div class="lead">{paragraphs(reference["summary"])}</div>'
    if source:
        body += f'<a href="{source}" target="_blank" rel="noreferrer">打开原片来源 ↗</a>'
    body += '<div class="meta"><span>基于实际帧与连续片段观察</span><span>推断与未知另行标识</span></div></header>'
    body += player(root, media, reference.get("chapters", reference["shots"]))
    body += '<section><div class="kicker">01 / 视觉与空间</div><h2>画面怎样参与解释。</h2>' + readable(reference.get("style", {})) + '</section>'
    body += '<section><div class="kicker">02 / 按时间看发展</div><h2>每一段从哪里走到哪里。</h2>'
    for scene in reference["shots"]:
        body += f'<article class="scene" id="unit-{escape(scene["id"])}"><div class="scene-title">{jump(scene["start"],bool(media))}<h3>{escape(scene["title"])}</h3></div>'
        body += '<p class="small">'+escape(scene.get("kind", "待判断"))+' · '+escape(scene.get("confidence", "置信度未定"))+'</p>'
        body += triptych(root, scene.get("evidence", []))
        body += progression(scene.get("opening", ""), scene.get("development", ""), scene.get("outcome", ""))
        for key, label in (("motion", "动作怎样改变状态"),("layers","元素用途"),("sound","声音与画面")):
            if scene.get(key):
                body += f'<details><summary>{label}</summary>{readable(scene[key])}</details>'
        body += '</article>'
    body += '</section><section><div class="kicker">03 / 声音</div><h2>连续性、事件与来源。</h2>'+readable(reference.get("audio", {}))+'</section>'
    body += '<section><div class="kicker">04 / 迁移方法</div><h2>新主题借鉴什么。</h2>'
    for transfer in reference.get("transfer", []):
        body += f'<article class="callout"><h3>{escape(transfer.get("principle", ""))}</h3>{paragraphs(transfer.get("evidence", ""))}{paragraphs(transfer.get("target", ""))}{paragraphs(transfer.get("avoid", ""))}</article>'
    body += '</section>'
    if reference.get("uncertainties"):
        body += '<section><h2>仍需确认的部分</h2>'+readable(reference["uncertainties"])+'</section>'
    if reference.get("publishing"):
        body += '<details><summary>原片的发布包装与话题</summary>'+readable(reference["publishing"])+'</details>'
    body += '<footer>参考拆解记录制作观察；新话题的事实来源另行核验。</footer>'
    shell(root,"reference.html",reference["title"]+' · 拆解',body,reference)


def topic_page(root, project, episode, facts, reference):
    movie = inside(root, project["output"]["file"])
    receipt = root / "qa/render.json"
    available = False
    if movie.is_file() and receipt.is_file():
        record = read(receipt)
        available = record.get("movie_sha256")==sha(movie) and bool(record.get("inputs")) and check_snapshot(record["inputs"])
    proof = root / "qa/proofs.json"
    groups = read(proof).get("scenes",[]) if available and proof.is_file() and read(proof).get("movie_sha256")==sha(movie) else []
    sources = {x["id"]:x for x in facts.get("sources",[])}
    claims = {x["id"]:x for x in facts["claims"]}
    body = nav(True)+f'<header><div class="kicker">新话题 / 解释与探索</div><h1>{escape(episode["title"])}</h1><div class="lead">{paragraphs(episode["summary"])}</div></header>'
    body += player(root,project["output"]["file"] if available else None,episode["chapters"])
    if episode.get("narrative"):
        body += '<section><h2>从一个问题开始。</h2>'+paragraphs(episode["narrative"])+'</section>'
    for i, chapter in enumerate(episode["chapters"]):
        body += f'<section id="unit-{escape(chapter["id"])}"><div class="kicker">{i+1:02d} / {time(chapter["start"])}</div><h2>{escape(chapter["title"])}</h2>'
        body += paragraphs(chapter["explanation"])+progression(chapter["setup"],chapter["process"],chapter["result"])
        body += '<aside class="callout"><b>看一个具体例子</b>'+paragraphs(chapter["example"])+'</aside>'
        for demo in chapter.get("demos",[]):
            height = max(220,min(1000,int(demo.get("height",440))))
            body += f'<figure class="demo"><iframe sandbox="allow-scripts" loading="lazy" height="{height}" src="{href(root,demo["file"])}" title="{escape(demo["title"])}"></iframe><figcaption><b>{escape(demo["title"])}</b> · {escape(demo["purpose"])}</figcaption></figure>'
        body += '<p class="small">'+escape(chapter["qualification"])+'</p>'
        for cid in chapter["fact_ids"]:
            claim=claims[cid]
            status={"verified":"已核验","teaching":"教学假设","inference":"推导"}[claim["status"]]
            body += f'<div class="sources"><span class="badge">{status}</span>{escape(claim["text"])}'
            if claim.get("qualification"):
                body += ' · '+escape(claim["qualification"])
            if claim.get("assumptions"):
                body += ' · '+escape(claim["assumptions"])
            body += '<br>'
            for sid in claim.get("source_ids",[]):
                source=sources[sid]
                link=url(source.get("url")) or href(root,source["file"])
                body += f'<a href="{link}" target="_blank" rel="noreferrer">{escape(source["title"])}</a>'
            body += '</div>'
        for scene in (s for s in episode["scenes"] if s["chapter_id"]==chapter["id"]):
            actual=next((x for x in groups if x["scene_id"]==scene["id"]),None)
            if actual:
                body += '<details><summary>'+escape(scene["title"])+' · 实际成片首中尾</summary>'+triptych(root,actual["frames"])+'</details>'
        body += '</section>'
    body += '<footer>图解、例子与影片共用本次脚本和事实记录。<a href="facts.json">资料与限定</a> · <a href="episode.json">场景与文字</a>'
    if available and (root/'output/subtitles.srt').is_file():
        body += ' · <a href="output/subtitles.srt">字幕</a>'
    body += '</footer>'
    shell(root,"topic.html",episode["title"],body,reference)


def index(root, project, reference, topic_exists):
    body=nav(topic_exists)+f'<header><div class="kicker">参考 · 新话题 · 完整影片</div><h1>{escape(project["topic"])}</h1><p class="lead">先看参考怎样讲清楚，再探索新话题中的关系、例子和结果。</p></header><div class="entry-grid"><a class="entry" href="reference.html"><span class="kicker">REFERENCE</span><h2>参考视频拆解</h2><p>{escape(reference["title"])}</p></a>'
    body += '<a class="entry" href="topic.html"><span class="kicker">NEW TOPIC</span><h2>新话题图解与视频</h2><p>完整解释、交互例子、资料和影片。</p></a>' if topic_exists else '<div class="entry"><h2>新话题制作中</h2><p>参考分析已可阅读。</p></div>'
    body += '</div><footer>本地项目入口</footer>'
    shell(root,'index.html',project['topic'],body,reference)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path)
    parser.add_argument('--reference-only',action='store_true')
    args=parser.parse_args()
    root=args.project.resolve()
    if args.reference_only:
        project,reference=read(root/'project.json'),read(root/'reference/analysis.json')
        reference_page(root,reference,False)
        index(root,project,reference,False)
    else:
        root,project,episode,facts,reference=validate(root)
        reference_page(root,reference,True)
        topic_page(root,project,episode,facts,reference)
        index(root,project,reference,True)
    state=read(root/'STATE.json')
    state['stages']['reference_html']='authored'
    if not args.reference_only:
        state['stages']['topic_html']='authored'
    write(root/'STATE.json',state)
    print(json.dumps({'reference':str(root/'reference.html'),'topic':str(root/'topic.html') if not args.reference_only else None,'index':str(root/'index.html')},ensure_ascii=False))


if __name__=='__main__':
    try:
        main()
    except (ValueError,KeyError,TypeError,OSError) as error:
        print(f'ERROR: {error}',file=sys.stderr)
        sys.exit(1)
