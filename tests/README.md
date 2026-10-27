# 离线测试

在仓库根目录运行：

```bash
python3 -B -m unittest discover -s tests -v
```

依赖：Python 3、NumPy，以及 PATH 中已有的 `ffmpeg`、`ffprobe`；FFmpeg 需要支持 `libx264` 和 AAC 编码。测试不会安装依赖、联网、读取浏览器登录状态或提交视频生成任务。缺少媒体依赖时，对应测试组会明确显示跳过，不能算作通过。

- `test_reference_download.py`：18 项获取和验证测试。远端下载替换为本地模拟后端；真实 FFmpeg 解码验证仅处理临时合成素材。
- `test_dance_metrics.py`：13 个 CLI 场景，覆盖已知 120 BPM、无节拍音频、静止与移动视频、尺寸与帧率归一化、时长限制及错误输入。
- `test_grok_video_duration.py`：3 项时长回归测试，覆盖整数秒（例如 `4`）序列化为 JSON 整数、分数秒（例如 `4.5`）保留精度，以及无效时长拒绝。HTTP 传输在测试中被拦截。

所有视频、音频、规格文件和输出 JSON 都在 `TemporaryDirectory` 内创建，测试结束后自动清理；无需下载或提交测试素材。`-B` 禁止在仓库中生成 Python 字节码缓存。
