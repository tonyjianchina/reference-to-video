# 文件约定与命令

所有项目路径用实际绝对路径；媒体、演示和生产资产放项目内，字体可以引用系统字体绝对路径。不要把以下示意数据当已完成的观察或真实题目。

## project.json

初始化后由 Codex 根据原片和新内容填写：

```json
{
  "schema_version": 1,
  "topic": "新话题",
  "language": "zh-CN",
  "output": {"width": 1080, "height": 1920, "fps": "30/1", "total_frames": 2700, "file": "output/film.mp4"},
  "renderer": "production/film.mjs",
  "fonts": [{"path": "/系统中的实际字体路径", "family": "FilmText"}],
  "audio": {"mode": "prepared", "source": "audio/final.wav", "reason": "本次新稿与配乐的连续混音"},
  "render": {"workers": 2, "encoder_threads": 2, "crf": 18},
  "review": {"motion_roi": [0, 0.25, 1, 0.68], "freeze_seconds": 4, "silence_seconds": 0.35},
  "logs_dir": "/实际日志目录"
}
```

这里的90秒、竖版、帧率、字体和检测区域都是语法例子。时长未给时，按参考节奏与新题的解释需要推定并记录理由，不能为了省事缩成几十秒样片。`total_frames/fps` 是完整计划片长。motion_roi为归一化x/y/宽/高，按当前主体与字幕位置选择。

## reference/analysis.json

```json
{
  "title": "原片标题",
  "source_url": "https://原片的实际页面",
  "media": "reference/source.mp4",
  "reviewed": false,
  "summary": "基于观察的叙事和制作概述",
  "style": {
    "palette": {"background":"#111111","foreground":"#eeeeee","accent":"#c59954","secondary":"#84aebb"},
    "typography": "实际字体层级及未知项",
    "composition": "空间和字幕区怎样分工",
    "camera": "实际景别和镜头变化",
    "motion": "动作事件及其用途"
  },
  "shots": [{
    "id":"ref-01","start":0,"end":8,"title":"实际场景",
    "kind":"2D动画（观察判断）","confidence":"中；软件未知",
    "opening":"首帧观察","development":"中段变化","outcome":"末段状态",
    "motion":"动作改变了什么","layers":[{"element":"某道具","purpose":"解释用途"}],
    "evidence":[
      {"time":0.3,"image":"reference/frames/01-first.jpg","note":"实际观察"},
      {"time":4,"image":"reference/frames/01-middle.jpg","note":"实际变化"},
      {"time":7.7,"image":"reference/frames/01-last.jpg","note":"实际后果"}
    ]
  }],
  "audio":{"人声":"实际观察或未知","配乐":"类型、连续性和来源判断","效果音":"经复核的事件与候选"},
  "transfer":[{"principle":"可迁移手法","evidence":"原片具体证据","target":"新话题怎么用","avoid":"不适合照搬什么"}],
  "uncertainties":["仍不知道的具体事项"],
  "publishing":{"caption":"原文案观察","hashtags":[],"activity":"以实际页面为准"}
}
```

`reviewed` 只在看过后改为true。每单元至少三个实际取帧证据，短单元可重复同一帧但要说明。源媒体无法合法取得时media可为null，仍须实际看过并取得允许的证据；不要编媒体文件或软件名。

参考阶段先运行：

```bash
python3 "$VIDEO_SKILL_DIR/scripts/media.py" inspect "$VIDEO_REF_PATH" --out "$VIDEO_PROJECT_DIR/reference/probe.json"
python3 "$VIDEO_SKILL_DIR/scripts/reports.py" "$VIDEO_PROJECT_DIR" --reference-only
```

## facts.json

`sources` 每条含 `id,title,url或file,checked_at`，可补充kind。`claims` 每条含 `id,text,status,source_ids,evidence,qualification`。

- verified：实际核验的事实，非空source_ids与具体evidence。
- inference：基于来源的推导，除上述字段还写清qualification。
- teaching：明确教学情境，可无外部来源，但必须写assumptions和适用边界。
- unresolved/unverified：研究中可暂存，不能通过完整制作验证。

账本是引用与限定记录，不是自动事实核验器。不要凭一串URL自称已经核实。

## episode.json

```json
{
  "title":"新主题标题","summary":"独立可读的总解释","narrative":"悬念和贯穿对象怎样连接各段",
  "chapters":[{
    "id":"chapter-01","start":0,"end":90,"title":"知识单元",
    "setup":"建立","process":"具体过程","result":"可观察后果",
    "explanation":"完整解释，可多段，不只是标题和数字",
    "example":"具体案例或独立计算",
    "qualification":"前提、边界、例外或模型限定",
    "fact_ids":["claim-01"],
    "demos":[{"file":"demos/mechanism.html","title":"可操作机制","purpose":"改变什么、如何看结果","height":480}]
  }],
  "scenes":[{
    "id":"scene-01","chapter_id":"chapter-01","start":0,"end":90,"title":"场景",
    "opening":"首段状态","development":"中段发展","outcome":"尾段结果",
    "action":"谁如何行动，改变什么","transition":"怎样承接下一段",
    "layers":[{"element":"实体或说明层","purpose":"解释什么"}],
    "reference_ids":["ref-01"]
  }],
  "captions":[{"start":0,"end":5,"text":"实际字幕纯文本"}]
}
```

章节和场景按帧对齐、无遗漏地覆盖全片，scene必须属于对应chapter。字幕可有解释性留白，但不能重叠或超出片长。旁白和各场景可以按需要增加字段；不要把这个90秒单场示意当实际分镜方案。

`demos/` 写本次新的自包含HTML/SVG/Canvas交互，内嵌需要的数据。报告iframe以allow-scripts沙箱运行，不能依赖跨源读取同目录JSON。交互真正改变机制结果；没有可交互机制的主题由Codex选择合适的探索方式。

## 命令

脚本位于技能scripts目录；渲染和服务脚本由init复制到项目scripts目录。

```bash
python3 "$VIDEO_SKILL_DIR/scripts/project.py" validate "$VIDEO_PROJECT_DIR"
node "$VIDEO_PROJECT_DIR/scripts/render.mjs" frame --time 2 --out "$VIDEO_PROJECT_DIR/qa/representative.png"
node "$VIDEO_PROJECT_DIR/scripts/render.mjs" video
# 其他引擎实际出片后，用record-render记录当前可编辑输入和影片哈希。
python3 "$VIDEO_SKILL_DIR/scripts/project.py" record-render "$VIDEO_PROJECT_DIR"
python3 "$VIDEO_SKILL_DIR/scripts/media.py" verify "$VIDEO_PROJECT_DIR"
python3 "$VIDEO_SKILL_DIR/scripts/media.py" proofs "$VIDEO_PROJECT_DIR"
python3 "$VIDEO_SKILL_DIR/scripts/reports.py" "$VIDEO_PROJECT_DIR"
node "$VIDEO_PROJECT_DIR/scripts/serve.mjs" 8361
```

不要对Canvas运行时已生成的receipt再次用record-render覆盖；该命令是外部引擎的收据，不是假装执行渲染的捷径。proofs输出最终编码帧、联系表和可浏览取帧页；不是源代码重画的预览。机检生成qa/media.json，不会填写艺术评价。

## review.json 与完成

按实际看图和浏览器操作填写，不能照抄以下结构当通过记录：

```json
{
  "media_sha256":"当前最终MP4的SHA256",
  "scene_reviews":[{"scene_id":"scene-01","status":"revise","first":"实际首态","middle":"实际中态","last":"实际尾态","finding":"观察到的问题或完成情况","evidence":["qa/实际文件.jpg"]}],
  "criteria":[{"id":"narrative","status":"revise","finding":"实际观察","evidence":["qa/实际文件.jpg"]}],
  "signals":[{"id":"signal-0001","decision":"revise","finding":"逐项复核实际候选"}],
  "browser":{"status":"pending","findings":"实际操作和结果","evidence":["qa/实际浏览器截图.png"],"html_sha256":{"reference.html":"实际哈希","topic.html":"实际哈希","index.html":"实际哈希"}},
  "listening":{"status":"not_available","finding":"实际具备的能力和验证范围"},
  "limitations":[],
  "remaining":["还没有完成的实际工作"]
}
```

criteria需七项：narrative、depth、visual_use、reference_transfer、readability、continuity、audio。信号列表对应当前qa/media.json，改片后重新生成；不能删除候选绕过复核。evidence用真实项目相对路径。已解决的评价才能pass，不能把必要缺失写成not_applicable。

浏览器检查后计算当前三份主HTML及所有chapter.demos文件的SHA256，写入html_sha256，键为项目相对路径（例如demos/mechanism.html）；交互改过也须重验。填写真实工具和结果。所有环节完成再运行：

```bash
python3 "$VIDEO_SKILL_DIR/scripts/project.py" finish "$VIDEO_PROJECT_DIR"
```

缺记录、错误音轨、不完整帧数、漏场景、未审候选、剩余工作和旧版本证据都会阻止完成。该门槛验证证据齐全与版本一致，不会自动知道故事是否有趣、引用是否真的支持断言。
