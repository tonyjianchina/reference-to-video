---
name: reference-to-video
description: 根据参考视频与新话题，逐镜拆解并输出参考HTML，再创作新话题交互HTML、原创脚本和完整视频，完成画面与声音验收。用于“照这个视频的叙事和样式做新主题”“参考片拆解后做成高质量视频”等完整制作请求；只下载、转写、压缩或发布已有视频时不触发。
---

# 参考视频到成片

由当前 Codex 会话完成分析、研究、编剧、画面编写、渲染和验收。脚本处理重复机械工作，不替代导演判断，不依赖额外 LLM API。默认交付参考拆解 HTML、新话题知识 HTML、完整 MP4、字幕和可编辑工程。用户只要求其中一部分时，以用户范围为准。

## 开始

已有参考和新话题就直接推进，不设置例行的选工具、审大纲、批准脚本关卡。已有脚本就保留用户要求的内容。只有缺少关键输入、真实访问受阻或需要未获授权的付费资源时才询问，并继续不依赖回答的工作。

在所属项目中新建独立制作目录。无所属项目时遵循用户工作区规则，不把主目录当工作区。把要求、素材来源、决定、已完成阶段、真实运行句柄和待解决项写入 `STATE.json`，跨轮次从此续做。

本机联网查阅、来源核验、平台操作和浏览器验收使用 `ego-browser` 技能及 `ego-browser nodejs`。一个制作目标保留一个 TaskSpace，编号记入状态；不因连接问题换空间、换搜索后端或抢用户桌面焦点。

下列变量由 Codex 设为实际绝对路径；初始化不会下载 URL、调用模型、购买资源、渲染样板视频或发布内容。现有工程非空时拒绝覆盖；续作读取现有文件。

```bash
python3 "$VIDEO_SKILL_DIR/scripts/project.py" init "$VIDEO_PROJECT_DIR" --topic "$VIDEO_NEW_TOPIC" --reference "$VIDEO_REFERENCE"
```

## 1. 看懂原片，先做参考 HTML

阅读 [references/reference-analysis.md](references/reference-analysis.md)。取得可观看素材并核验真实时长、画幅、帧率和音轨。`rea-video` 可用时复用其拆解能力；缺少 CLI 时用 FFmpeg 和 Codex 看图完成，不把额外项目安装当成前置阻塞。

逐镜观察首、中、尾；对动作、转场、声音有疑问时查看连续片段。拆开叙事推进、人物与道具、空间层次、文字层级、镜头运动、音乐与事件落点。区分观察、工具测量、推断与未知；候选切点不直接当最终镜头，OCR 行数不当叙事句数。

记录“为什么这一镜有用”和能迁移的方法，不只列黑底、字体、配色和特效。先产出可读的 `reference.html`，包含来源入口、实际帧、时码分镜、逐段发展、声音分析、不确定项和复刻路线。

## 2. 把新话题写成可解释的故事

阅读 [references/story-and-quality.md](references/story-and-quality.md)。核验新话题资料，维护 `facts.json`，区分事实、推导、教学假设、争议和未知。联网优先一手资料，医学、法律、金融和时效性事项按相应准确性要求处理。

选择适合话题的疑问、行动主体或贯穿道具。每个知识单元都有建立、过程、后果，解释具体关系或实例；关键规则必要时补充例外与限定。不能只报数字、堆术语或把所有内容压成三个图标。

每场写明首中尾状态、动作改变什么、元素用途和承接方式。章节数、镜头数、时长和配色从当前材料决定；美国选举、7分06秒、黑金宋体、无旁白、三州模型都不是全局模板。

## 3. 新话题 HTML 要能独立讲清楚

阅读 [references/contracts-and-commands.md](references/contracts-and-commands.md)，完成 `episode.json`。

创作 `topic.html`：有完整解释、具体例子、推导、限定和来源；重要机制加入可操作 SVG/Canvas/HTML 演示，操作确实改变结果并说明原因。视频未播放时页面也应成立，不能只是播放器、分镜表或 JSON。参考的视觉语言在适合处延续，按 `frontend-design` 的相关方法打磨版式。

`scripts/reports.py` 能生成两份 HTML 和入口页，支持本次新写的 `demos/` 演示。它是可修改的起点；参考有明确布局时按参考定制，不让通用框架决定影片风格。外部文案按数据转义，不能作为脚本执行。

## 4. 先做代表镜头，再做全片

阅读 [references/render-and-audio.md](references/render-and-audio.md)。二维、2.5D、图形和流程动画默认由 Codex 写场景并本地出片。实拍、真实录屏、照片或复杂3D参考选择对应素材和路线；缺少真实资产时解决具体缺口，不能用简陋图表冒充同等完成度。

从开头、核心机制、最复杂案例及转场选代表场景，渲染实际尺寸画面和短片，对照参考修改，再批量出片。这是内部质量检查，不是等用户批准的关卡。

Canvas 运行时接受新写的 `production/film.mjs`，负责分段并行编码、合并、音轨和进度；也可用适合参考的其他引擎。它没有默认政治人物、背景、字幕动画或样板成片。

动作按连续场景时间与事件编排，字幕只改变说明层，不驱动整段重播。人物行走、递物、投票、开关等要改变关系。景别、空间、例证和阅读停顿共同服务解释，不靠晃动、发光、粒子或计数循环填时长。

音乐、旁白、环境声、效果音分别规划。需要原片配乐时区分纯BGM与原混音；旧旁白或强事件音不适合时不能整轨覆盖新话题。仅在明确采用整条原混音且长度匹配时用 `copy-full`，比较解码 PCM。其他情况制作连续新混音，检查接缝、首尾与台词；不能每换字幕重启音乐。

## 5. 验收真实成品

```bash
python3 "$VIDEO_SKILL_DIR/scripts/project.py" validate "$VIDEO_PROJECT_DIR"
# Canvas路线：在项目安装package.json依赖，先由Codex实现film.mjs。
node "$VIDEO_PROJECT_DIR/scripts/render.mjs" frame --time 1 --out "$VIDEO_PROJECT_DIR/qa/frame.png"
node "$VIDEO_PROJECT_DIR/scripts/render.mjs" video
python3 "$VIDEO_SKILL_DIR/scripts/media.py" verify "$VIDEO_PROJECT_DIR"
python3 "$VIDEO_SKILL_DIR/scripts/media.py" proofs "$VIDEO_PROJECT_DIR"
python3 "$VIDEO_SKILL_DIR/scripts/reports.py" "$VIDEO_PROJECT_DIR"
```

查看最终编码 MP4 提取的所有场景首中尾、关键高分辨率帧和连续片段，检查文字、实际动作、因果桥梁、层次与重复。近静止、黑场、静音只是候选。保留停顿须有对应读图任务，不能统一贴“阅读需要”。

用 egolite 实测两份 HTML 的交互、章节跳转、片尾、窄屏布局及视频加载；本地播放器支持 Range。声称可持续访问的预览须独立托管并复查，否则交付本地文件，不把临时服务当持久链接。

按实际观察填写 `qa/review.json`，保留问题、修复和证据。`project.py finish` 只在机械检查、编码帧、资料、逐场审阅和 HTML 验收齐全且版本相符时写完成状态；不能自动宣布审美或事实正确。影片修改后更新相关检查并全长解码，不做无原因的重复全量测试。

最终给两份 HTML、完整 MP4、源码入口和实际验证结论。质感、素材或听审的具体限制如实说明；只有计划、静帧、半段影片或能播放的稀疏模板，不算高质量制作完成。

## 可选：发布

仅在用户明确要求本次发布时阅读 [references/publishing.md](references/publishing.md)。创建视频不自动授权公开发帖；已有发布授权时直接完成具体准备和提交，不设置例行确认。话题、活动、双封面与章节的方法可复用，活动名称和平台字段每次核对。
