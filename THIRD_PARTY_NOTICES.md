# 第三方来源与致谢

本文件说明本次融合使用的第三方资料、代码和依赖。不同来源分别遵循各自许可；这里不为整个仓库另行指定统一许可证。

## Seedance 案例索引

- 直接来源：[FizzEat/seedance-prompts-zh](https://github.com/FizzEat/seedance-prompts-zh)，整理者：王大锤。
- 使用快照：`86a32b17e99191fff56689c9e29e4b73343231f1`，原文件 `第一批.json`。
- 来源链：原仓库标明整理自 [Nuos/awesome-seedance](https://github.com/Nuos/awesome-seedance)，其上游为 [LearnPrompt/awesome-seedance](https://github.com/LearnPrompt/awesome-seedance)。感谢 Carl（卡尔的AI沃茨）、GoodCase.ai 与各条原帖作者。
- 整理内容许可：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，见[来源许可证](https://github.com/FizzEat/seedance-prompts-zh/blob/86a32b17e99191fff56689c9e29e4b73343231f1/LICENSE)。
- 本地文件：`references/seedance-index.json`。仅提取分类、中文标题、作者、原帖 URL、第三方复测结论和稳定度六项元数据，并添加来源说明；未复制完整提示词或 EverOS 脚本。
- 各条作者和原帖链接保留在索引中。复测资料来自 GoodCase.ai，未在本项目复测，不代表官方指标或跨模型成功率。

原创镜头卡 `references/camera-presets.json` 与离线查询脚本是本项目新增内容，不是原提示词库的全文转载。

## qiaomu-download

- 来源：[joeseesun/qiaomu-download](https://github.com/joeseesun/qiaomu-download)，作者：向阳乔木（乔向阳 / Joe，[@vista8](https://x.com/vista8)）。
- 使用版本：本地已安装的 `1.3.0`；安装副本没有可用 Git commit，因此以 [ORIGIN.md](vendor/qiaomu-download/ORIGIN.md) 中的原始 SHA-256 标识实际采用文件。
- 随包范围：`vendor/qiaomu-download/` 中的下载运行代码、适配器、必要引用文档与来源说明；不含用户配置、缓存、参考媒体或第三方后端二进制。
- 代码许可：[MIT License](vendor/qiaomu-download/LICENSE)，完整保留 `Copyright (c) 2026 向阳乔木` 及许可文本。
- 本地修改：yt-dlp 调用添加 `--ignore-config` 与 `--no-cache-dir`；外层 `scripts/download_reference.py` 提供独立参考视频入口、明确的 Cookie 策略、路径与完整解码验证、脱敏来源记录。
- `UPSTREAM_SKILL.md` 仅保留用于追溯；融合版执行策略以主技能及 [下载说明](references/source-download.md) 为准。

## 舞蹈提取方法

感谢用户提供的《舞蹈提取 Skill 包》的作者与分享者。原始附件没有可核实的包作者署名或许可证信息；其中的历史水印和引用作者不作为整包作者身份的依据。

本项目采用其逐秒观察、手势／表情／体态分轨、动作质感与运镜排查思路，重新整理为 `references/dance-analysis.md`。`beat_analysis.py` 和 `motion_check.py` 已重新实现，分别输出候选节拍与画面变化量，不保留原包将首峰视作小节首拍或把帧差视作人体动量的结论。原始 ZIP 与其完整文档不随仓库发布。

## 外部工具与间接依赖

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：通用媒体提取与下载，作为外部工具调用。
- [FFmpeg](https://ffmpeg.org/)：媒体探测、解码、抽帧与合成，作为外部工具调用。
- [NumPy](https://numpy.org/) 与 [Pillow](https://python-pillow.org/)：可选的数值分析和联系表依赖，不随包复制库本体。
- [ltaoo/wx_channels_download](https://github.com/ltaoo/wx_channels_download)：视频号可选本地后端。锁定版本的许可包含 Commons Clause，详见[适配说明](vendor/qiaomu-download/references/wechat-video.md)；后端二进制未打包，也不因本包包含 MIT 代码而改变其许可。
- [spotDL/spotify-downloader](https://github.com/spotDL/spotify-downloader)：qiaomu-download 的 Spotify 元数据匹配路线所参考的项目。保留的上游适配器有其来源记录；当前参考视频入口拒绝将 Spotify 音频链接当作视频。

感谢这些项目的作者、维护者和贡献者。
