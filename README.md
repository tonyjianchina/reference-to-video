# 参考视频到成片 · Reference to Video

一个由 Codex 执行的视频制作技能。输入参考视频和新话题，完成原片拆解、新内容研究、交互图解、原创分镜与动画，并验收真正编码后的影片。

**参考视频 → 参考拆解 HTML → 新话题交互 HTML → 完整 MP4、字幕与可编辑工程。**

## 安装

将本仓库放入 Codex 的技能目录。以下命令适用于目标目录尚不存在的情况：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/tonyjianchina/reference-to-video.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/reference-to-video"
```

使用时让 Codex 加载 [SKILL.md](SKILL.md)：

```text
用 $reference-to-video
参考视频：https://……（也可以是本地文件）
新话题：……
```

可以附上已有脚本、受众、片长、画幅和声音要求；未指定的制作参数由当前参考与话题决定。

## 运行条件

- Codex：负责观察、研究、编剧、画面代码和实际质量判断；不需要另配 LLM API。
- Python 3.10+、Node.js 20.11+、FFmpeg / ffprobe。
- Canvas 路线在每个视频工程中安装 `assets/project/package.json` 的依赖；中文字体通过工程配置指定。
- 浏览器流程使用 `ego-browser` 技能及 egolite。`rea-video` 和 `frontend-design` 可提供拆解与版式能力；缺少 `rea-video` CLI 时可用 FFmpeg 取帧和 Codex 观察完成拆解。

音频与素材根据实际任务准备；本仓库包含制作指令、脚本和模板，视频工程在独立目录中生成。

## 制作与验收

1. 看原片的真实画面与连续片段，区分观察、测量、推断和未知，先生成参考拆解 HTML。
2. 核验新话题资料，建立事实与教学假设记录，写清具体案例、过程、后果和限定。
3. 创作能独立解释机制的新话题 HTML；交互操作实际改变状态和结果。
4. 按参考设计环境、人物、道具与镜头，先看代表场景，再渲染全片。场景动作按连续时间推进。
5. 对最终 MP4 全长解码、核对帧数和音轨、提取逐场首中尾，并实际检查连续动作、文字同步和 HTML 播放交互。修改后重新验收受影响的内容。

脚本负责重复机械工作；美术、故事与事实判断由执行技能的 Codex 完成。初始化提供的是制作工程，具体影片需要针对新话题编写。

`project.py finish` 要求当前影片、生产输入、编码帧证据、逐场审阅、检测候选处置及网页验收版本一致，才会写入完成状态。

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | 技能入口与完整制作流程 |
| [references/reference-analysis.md](references/reference-analysis.md) | 参考片的叙事、画面、声音拆解 |
| [references/story-and-quality.md](references/story-and-quality.md) | 脚本、动作、知识深度与质量要求 |
| [references/contracts-and-commands.md](references/contracts-and-commands.md) | 工程数据、命令及验收记录格式 |
| [references/render-and-audio.md](references/render-and-audio.md) | 渲染、音轨与预览 |
| [references/publishing.md](references/publishing.md) | 用户要求发布时的话题、活动、封面及提交流程 |

## 已验证的范围

2026-11-08 使用一个新的架空图书借还话题完成独立试跑：两份 HTML、有效交互、720×1280 / 24fps / 432帧的18秒静音影片、逐场编码帧审阅及真实浏览器验收。

工具另通过中文及单引号路径、7.5fps、完整帧数、AAC整轨解码PCM一致性、新PCM混音导出、大量抽帧条件、短音轨与错误音轨拒绝、旧生产输入及旧网页证据拒绝等检查。

短片试跑验证工作流和检查机制；长片叙事、事实准确性、艺术表现和声音听感仍需在每次制作中审阅。
