# video-recreation

从参考视频拆镜、反推提示词并制作复刻视频，也支持指定转场重做、已有素材重剪、配乐与字幕调整。

现在可直接输入**视频分享链接或本地视频**。内置下载入口把素材获取、验证与后续提取连接起来；舞蹈视频另有逐秒动作、候选节拍、手势／表情／体态和动作质感分析。

支持 **沿用原运镜、局部改运镜、按自己的想法重设计**。既可以选镜头卡，也可以用日常语言描述效果，技能会区分相机运动与人物动作，整理为逐镜计划。

生成前检查 **生图模型、动作模型及各自 API 地址／调用渠道**。本次已指定、同任务已确认与用户明确长期默认的选择继续沿用，只补问缺失项，不在聊天中收集 API Key。

## 链接下载与舞蹈提取

```text
$video-recreation
提取这个链接里的舞蹈，先下载并验证视频，再分析动作、手势、表情、节拍和原运镜。
这次只要完整提示词和动作表，不生成视频。
链接：粘贴实际视频分享链接
```

需要复刻时也可以直接说：“换成我提供的角色跳同一支舞，保留动作和音乐，最后两秒拉远；视频用 Veo（Flow）。”链接获取、舞蹈分析、运镜创意和生成范围分别记录，已说清的内容直接采用。

- [下载与导入](references/source-download.md)：`download_reference.py doctor` 只检查本地依赖；`acquire SOURCE --out-dir NEW_WORKDIR` 下载或导入并完整解码验证。随包包含下载运行代码，不依赖另装 qiaomu-download 技能；仍需本机下载／媒体工具。
- [舞蹈精细分析](references/dance-analysis.md)：逐秒索引与关键转折抽帧、左右手／脚／重心、表情／体态、候选节拍和运镜证据。
- `scripts/beat_analysis.py` 与 `scripts/motion_check.py` 提供离线诊断。BPM／拍点是候选，帧差是画面变化量，都不代表已经达到舞蹈复刻要求。
- 默认匿名获取链接，不自动打开平台客户端、安装后端或更新全局工具。受限链接按实际失败状态恢复，已获取的视频保持来源记录。

## 创意运镜入口

```text
$video-recreation
复刻附件视频，保留人物、服装、故事和音乐。
第 2 镜改成从正面缓慢推近，人物继续原动作；其他镜头沿用原片。
我也可能直接选镜头卡，或通过对话补充想法。
生成渠道未确定时，请按 Seedance、Grok、Veo（Flow）、Muse Video 的实际能力给我选项。
```

- [运镜选择与对话](references/camera-direction.md)：直接选镜头、自然语言理解、保留／修改范围、镜头计划与验收。
- [平台与模型选择](references/model-selection.md)：2026-10-26 官方资料核验，比较 Seedance、Grok、Veo（Flow）、Muse Video 的视频能力。
- `scripts/camera_library.py list`：15 张原创镜头卡，包含运镜、变焦、固定视角与剪辑类型；`show orbit` 展开一张，`search "绕人物"` 查关键词候选。
- `scripts/camera_library.py examples "手持"`：82 条 Seedance 社区案例元数据，保留原作者与链接。本地查找无需 EverOS 或 API Key；语义、否定和修改范围由智能体结合上下文理解。

选择镜头卡不代表所有模型都能精确执行，也不替用户选择新的生成服务。实际支持项按所选渠道检查，质量按试片验收。

完整的安装、模型选择、复刻、转场重做、重剪和交付步骤，见 [操作手册](操作手册.md)。手册附有可复制的需求模板、终端命令和 Muse 实测记录。

## Codex

将完整目录安装到当前 Codex 的个人技能目录，使用 `$video-recreation` 并提供参考视频。已有安装时更新对应目录即可；具体目录遵循当前宿主配置。

## Muse（muse.ai 网页／桌面）

把完整技能包附给 Muse，并发送：

> 请加载附件中的 video-recreation，先读取 SKILL.md 和 references/muse.md，检查当前环境的工具和媒体依赖，再按我提供的参考视频执行。支持我直接选择运镜或用对话表达想法；需要生成时复用已确定的生图、动作模型与渠道，只补问缺失项。输出成片、完整提示词与素材；尚未完成的步骤请明确标出。

加载整个目录；单独粘贴 `SKILL.md` 会缺少引用文档和脚本。当前会话的加载、文件访问和工具能力需要实际确认。详细步骤见 [Muse 适配](references/muse.md)。

## Muse Code

在已安装 Muse Code 的环境，针对本地完整技能目录执行：

```bash
muse skills validate ./video-recreation
muse skills install ./video-recreation --scope user
muse skills inspect video-recreation
```

这是 Muse Code 的命令，不适用于 muse.ai 网页端。已有 Codex 技能可能被自动发现，先用 `muse skills list` 检查，避免重复安装。参见 [官方技能文档](https://dev.meta.ai/docs/muse-code/extending)。

## 环境与依赖

本地媒体链路需要 Python 3.9+、FFmpeg；联系表需要 Pillow，ffprobe 可选。脚本渲染使用 libx264 和 AAC 编码器。

下载／导入完整验证需要 ffprobe；普通站点下载另需 yt-dlp。新增舞蹈节拍与画面变化量诊断需要 NumPy 和 ffprobe。缺少可选能力不会阻断其他已经就绪的分析工作；各脚本报告具体缺项。

```bash
python3 scripts/check_environment.py --host muse --workspace . --report work/environment.json
```

环境检查不联网、不安装依赖、不读取凭据。它只报告本地依赖；生图、动作生成、网络权限和附件导出由当前平台另行核实。Muse Image 可作为用户选择的生图渠道，动作视频仍独立选择；本包没有独立 Muse Image API 客户端。

## 内容

- [操作手册](操作手册.md)：从提交参考视频到下载成片的完整操作步骤。
- [SKILL.md](SKILL.md)：范围、工作流和验收要求。
- [references/generation.md](references/generation.md)：模型选择、权限和续跑。
- [references/production.md](references/production.md)：拆镜、换装转场与重剪。
- [references/schema.md](references/schema.md)：时间线、提示词模板和命令。
- [references/muse.md](references/muse.md)：Muse／Muse Code 的运行说明。
- `scripts/video_workbench.py`：探测、抽帧、合成和完整解码检查。
- `scripts/grok_video.py`：兼容 Grok 协议的视频任务准备、提交、查询与下载。

## 验证状态

可复跑的离线检查位于 `tests/`，运行方法和依赖见 [测试说明](tests/README.md)。测试使用临时生成的音视频，不上传参考素材、不调用付费生成服务。

下载与舞蹈融合版在本机以合成媒体验证节拍边界情况、帧差采样一致性和本地导入，并离线检查下载结果处理；未把这些检查称为真实平台链接下载实测。用户附件中的指定模型、固定时长、默认角色、发布与超分步骤没有作为默认执行规则导入。

2026-10-26 的扩展新增离线镜头卡、社区案例索引和对话工作流。新增脚本已做离线命令验证；平台比较依据官方文档，未在本次调用付费生成或核验各账户权益。下面保留上游历史记录，不表示本次重复实测。

2026 年 10 月 16–17 日，在 Muse 网页端完成了一次 5 秒舞蹈测试：加载完整技能包、检查环境、分析参考、生成两版关键帧、生成视频、合成原音乐并下载附件。成片为 704×1248、24 fps、120 帧，本地完整解码通过。

这次跑通了生成和交付流程，舞蹈复刻验收仍未通过：人物外观、抬脚、手臂高度、重复动作和结尾姿态与参考有差异。这里只验证了 5 秒片段，尚未完成整段复刻。工具未返回模型版本，记录为“由渠道管理”。详细结果见 [操作手册第 10 节](操作手册.md#10-这次-muse-测试验证了什么)。

macOS 的环境检查测试及“探测→抽帧→重剪→完整解码”离线媒体验证也已通过。Muse Code 的安装命令未在本次测试中执行；其他账号、入口和模型渠道仍需按实际环境检查。

反推提示词是根据参考整理出的复刻方案，不能当作原作者原始提示词。

## 致谢与来源

感谢以下作者与项目的开放分享，使本项目能够把镜头参考、视频获取与舞蹈分析连接起来：

- **[FizzEat / 王大锤](https://github.com/FizzEat/seedance-prompts-zh)**：感谢 Seedance 中文标题、镜头分类和案例整理。本项目使用其中 82 条案例元数据，保留原作者、原帖链接和第三方复测说明；整理内容遵循 CC BY 4.0。
- **[Nuos/awesome-seedance](https://github.com/Nuos/awesome-seedance)**、其上游 **[LearnPrompt/awesome-seedance](https://github.com/LearnPrompt/awesome-seedance)** 与 **[GoodCase.ai](https://goodcase.ai)**：感谢案例整理与复测资料，也感谢 Carl（卡尔的AI沃茨）及每一位原帖创作者。
- **[向阳乔木（joeseesun）](https://github.com/joeseesun/qiaomu-download)**：感谢 qiaomu-download 的视频下载与适配能力。随包保留 MIT 版权和许可证，[来源记录](vendor/qiaomu-download/ORIGIN.md)列明版本、原始文件摘要及本地修改。
- **《舞蹈提取 Skill 包》的作者与分享者**：感谢逐秒动作、手势、表情、体态、节拍和运镜分析的方法参考。附件未提供明确的包作者署名，因此不推测其身份；原始附件不随仓库发布。

- 感谢X好友 [AI art gallery] (https://x.com/sandmrk) 提供的舞蹈解析思路 和素材

同时感谢 [yt-dlp](https://github.com/yt-dlp/yt-dlp)、[FFmpeg](https://ffmpeg.org/) 等基础工具，以及视频号可选后端 [ltaoo/wx_channels_download](https://github.com/ltaoo/wx_channels_download)。这些外部项目遵循各自许可证。


各来源的使用范围与许可见 [第三方来源说明](THIRD_PARTY_NOTICES.md)。
