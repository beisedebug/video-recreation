# video-recreation

从参考视频拆镜、反推提示词并制作复刻视频，也支持指定转场重做、已有素材重剪、配乐与字幕调整。

生成前分别确认 **生图模型、动作模型及各自 API 地址／调用渠道**。同一任务已确认的选择继续沿用，不在聊天中收集 API Key。

完整的安装、模型选择、复刻、转场重做、重剪和交付步骤，见 [操作手册](操作手册.md)。手册附有可复制的需求模板、终端命令和 Muse 实测记录。

## Codex

将完整目录安装到当前 Codex 的个人技能目录，使用 `$video-recreation` 并提供参考视频。已有安装时更新对应目录即可；具体目录遵循当前宿主配置。

## Muse（muse.ai 网页／桌面）

把完整技能包附给 Muse，并发送：

> 请加载附件中的 video-recreation，先读取 SKILL.md 和 references/muse.md，检查当前环境的工具和媒体依赖，再按我提供的参考视频执行。需要生成时先分别询问生图、动作模型及各自 API 地址或调用渠道。输出成片、完整提示词与素材；尚未完成的步骤请明确标出。

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

2026 年 10 月 16–17 日，在 Muse 网页端完成了一次 5 秒舞蹈测试：加载完整技能包、检查环境、分析参考、生成两版关键帧、生成视频、合成原音乐并下载附件。成片为 704×1248、24 fps、120 帧，本地完整解码通过。

这次跑通了生成和交付流程，舞蹈复刻验收仍未通过：人物外观、抬脚、手臂高度、重复动作和结尾姿态与参考有差异。这里只验证了 5 秒片段，尚未完成整段复刻。工具未返回模型版本，记录为“由渠道管理”。详细结果见 [操作手册第 10 节](操作手册.md#10-这次-muse-测试验证了什么)。

macOS 的环境检查测试及“探测→抽帧→重剪→完整解码”离线媒体验证也已通过。Muse Code 的安装命令未在本次测试中执行；其他账号、入口和模型渠道仍需按实际环境检查。

反推提示词是根据参考整理出的复刻方案，不能当作原作者原始提示词。
