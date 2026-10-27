# 数据、提示词和命令

所有路径示例相对于当前项目目录；脚本自身使用已安装技能的绝对路径。中间文件放项目 `work/`，交付文件放项目的正式输出目录。下文的 `SKILL_DIR` 由实际技能位置确定，不能照搬某台机器上的绝对路径。

## 宿主与依赖检查

有终端时，在当前任务的可写目录执行：

```bash
python3 "$SKILL_DIR/scripts/check_environment.py" --host muse --workspace . --report work/environment.json
```

`--host` 可选 `codex / muse / muse-code / other`，只是记录智能体已确认的宿主，不会探测账号或切换模型。检查使用临时文件验证工作目录可写性，结束时清理；只有 `--report` 会保存报告。报告已存在时拒绝覆盖，续跑使用新文件名。

`capabilities` 分别报告探测、抽帧、静音合成和带音轨合成的本地依赖是否就绪；不证明实际素材可处理。退出码 `1` 表示核心媒体依赖或工作目录不满足，`2` 表示参数／报告写入失败。缺 Pillow 仅影响联系表，缺 ffprobe 使用已有 FFmpeg 元数据降级；均会给出警告。网络、内置生图、外部生成服务与附件导出保持 `not_checked`，由智能体另行核实。

运行环境记录与生图／动作模型选择分开。Muse 会话中的媒体必须先落到它实际可访问的目录；本机路径与云端路径不可互换。交付使用宿主附件工具，不能只返回云端文件路径。

## 生成配置记录

需要生成时，在 `work/generation-selection.json` 分别记录 `image` 与 `motion` 的用户选择。这是智能体的任务记录，不是下方脚本自动读取的配置；每次构建请求时据此核对模型与渠道。

| 字段 | 记录内容 |
|---|---|
| `required` | 本任务是否需要该阶段生成；不需要时为 `false`，其余字段可省略 |
| `model` | 用户选择并核实的模型标识；渠道不开放选择时为 `null`，另用 `model_managed_by_channel: true` 标明 |
| `channel` | 用户选择的内置工具、API 提供商／配置名称或网页渠道 |
| `base_url` | 已确认的 API 基础地址；非 API 渠道为 `null`，已有配置可在用户选择该提供商后解析 |
| `confirmed_by` | 本次明确指定、同任务已确认、用户明确长期默认、明确沿用或授权助手选择的依据；不能用历史调用成功代替 |

另记录 `host`、`channel`、实际 `model` 和 `capability_check`，避免把 Flow／Muse 宿主名当作模型版本。能力检查至少覆盖所需的输入模式和规格；只有工具／官方文档确认才写 supported，未知写 `not_checked`。

## 运镜与创意记录

按 [运镜选择与对话](camera-direction.md) 保存 `work/camera-plan.json`：创意模式、选项／对话输入方式、用户原话、参考观察、逐镜源与目标帧区间、相机与主体运动、保留项、工作假设和未解决问题。它不改变下方媒体脚本的项目结构，也不会自动变成提供商 API 参数。生成时保存由计划编译出的真实完整提示词。

## 来源与舞蹈记录

`download_reference.py acquire` 自动保存本次获取的私有 `manifest.json`；以其已验证的 `files[].path` 作为媒体脚本输入。完整 URL 留在用户任务上下文，清单仅存来源类型、host 与输入摘要。不要把提取器完整元数据或临时链接作为交付附件。

舞蹈任务可保存 `work/dance-analysis.json`，字段按实际需要使用，未知保持 null／not_checked：

| 字段 | 含义 |
|---|---|
| `source_manifest` / `source_sha256` | 来源清单与视频摘要 |
| `timebase` | 实际视频帧率、VFR 标记、源帧号与 PTS 映射；秒和帧不互相凭空换算 |
| `beat_analysis` | 音轨状态、算法报告路径、候选 BPM／网格、人工核验状态；小节／downbeat 不从首峰自动编号 |
| `events[]` | `id`、`source_pts`／帧区间、可见性、证据帧、躯干／脚步／重心、左右手、表情、体态、动作质感 |
| `beat_alignment[]` | 动作事件 ID、候选拍点、时间偏差、误差范围、核验状态 |
| `camera_plan` | 引用现有运镜计划，不重复造一套相机控制参数 |
| `observations` / `interpretations` | 可见事实与情绪、力度等解释分开 |
| `changes` / `preserve` | 用户授权修改和需要保留的内容 |
| `dimension_scopes` | 按身份、动作、相机、音频分别记录可改与保留区间及验收方法；全片换身份不取消原运镜／动作保留要求 |
| `validation` | 技术、身份、动作、运镜、节拍、音频各自的 pass/fail/not_checked 及依据 |

这些是工作记录，不是提供商 API 字段。模型提示词仅编译所需信息；不要把未知字段填满来冒充精确测量。

不要记录 key、Authorization 或带凭据的 URL。精确私有端点仅留在本地工作记录；交付摘要保留模型和渠道名称。配置改变时更新记录并保留此前任务回执，不能让旧回执看起来使用了新模型。

## 项目与时间线

推荐保留 `reference/`、`prompts/`、`images/`、`clips/`、`jobs/` 和最终合成文件。目录按实际需要创建；只有提示词任务不需要空建媒体目录。

`project.json` 最小示例：

```json
{
  "mode": "recreate",
  "fps": "24",
  "width": 720,
  "height": 1280,
  "fit": "cover",
  "total_frames": 96,
  "audio": null,
  "clips": [
    {"id": "shot-01", "file": "clips/shot-01.mp4", "source_in_s": 0, "source_out_s": 4, "target_frames": 96}
  ]
}
```

- `mode`：`recreate / transition / reedit`。模式用于记录意图，不自动决定修改范围。
- `fps` 可为 `30000/1001`；`width/height` 是偶数。`fit=cover` 等比放大后居中裁切；`contain` 等比缩放后加黑边。主体不在中央时需自行确定裁切框，不能直接用默认居中覆盖重要内容。
- `clips` 的顺序就是最终顺序。`source_in_s/source_out_s` 是源素材取用秒区间；`target_frames` 是该片段在成片的帧数。脚本按指定比例变速、丢弃素材自带音轨，不决定艺术上是否应该变速。
- 可写 `output_start_frame/output_end_frame`，脚本会验证连续无缝、无重叠；未写则累计补全。总长以整数帧计算。
- 若源时间线边界为 `t0,t1,...`，先算每个累计边界 `round(t*fps)`，每镜帧数取相邻边界之差，不要分别四舍五入每镜时长再相加。
- `audio=null` 明确静音。需音轨时用 `{"file":"reference.mp4","source_in_s":0}`，映射该文件首个音频流，并重置 PTS，截到目标时长，短音频尾部补静音。混音、淡出、音频变速、字幕由任务后期脚本单独实现并记录，工具不会替用户猜测。
- VFR 源的原帧号与时间不呈固定比例。抽帧 index 保留真实 PTS；合成会明确转为项目的恒定帧率。旋转元数据不完整时需检查实际导出图像方向。

局部修改另外记录 `edit_ranges` 与 `protected_ranges`，每项包含源文件、源帧区间和目标帧区间。它们是人工/后期验收依据，当前脚本不会自动推断或验证画面未改。范围重叠、源目标变速和边界余量都须说明。仅配乐不应调用会重编码画面的 `render`；用 FFmpeg 视频流复制。

## 三层提示词

按镜头实际需要删减模板字段，不强行补充不可见事实。

```text
公共约束
参考输入及角色：图1=身份；图2=服装和面料；图3=构图/环境。
人物/环境必须保留：...
本镜允许变化：...
不可新增/不可改变：仅列实际容易出错的要素。

图像提示词
镜头编号与锚点：...
具体瞬间：人物姿态、表情、视线、服装；布料/物体的位置和形状。
画面组织：景别、角度、主体位置、前后景、光线、材料。
约束：身份/服装/构图；参考中的标签、色卡是否排除。

视频提示词
初始状态：...
时间阶段：0–a秒...；a–b秒...；b–结束...
运动主体及方向：人物...；前景物...；相机...
遮挡与揭示：换装/变化由何时、何处的遮挡掩盖。
结束状态：姿态、构图、前景是否完全退出。
保持不变：...
避免：与参考冲突的具体行为。
```

为每版保留实际发送的 `image_prompt.txt`、`video_prompt.txt` 和输入图片摘要；包括后来追加的限制。可另提供无注释的完整提示词供复制，但不能误称它是原作者原文。

## 本地媒体脚本

```bash
python3 "$SKILL_DIR/scripts/video_workbench.py" probe reference.mp4 --report work/probe.json
python3 "$SKILL_DIR/scripts/video_workbench.py" sample reference.mp4 --out-dir work/overview
python3 "$SKILL_DIR/scripts/video_workbench.py" sample reference.mp4 --start-frame 72 --end-frame 120 --step 1 --out-dir work/transition-frames
python3 "$SKILL_DIR/scripts/video_workbench.py" timeline project.json --report work/timeline.json
python3 "$SKILL_DIR/scripts/video_workbench.py" render project.json --out outputs/final-v1.mp4 --work work/render-v1
python3 "$SKILL_DIR/scripts/video_workbench.py" verify outputs/final-v1.mp4 --expected-frames 96 --width 720 --height 1280 --fps 24 --report work/technical-check.json
```

`sample` 默认约每秒一帧，输出最多 300 张，使用 `--max-frames` 显式调整；逐帧分析用 `--step 1`。联系表最多每页 48 张；`index.json` 记录源帧号和 PTS。输出目录必须不存在以防旧图混入。`render` 的工作目录与最终文件也须使用新版本名；它只做明确的片段取用、变速、尺寸规范化、拼接和指定音轨，不执行生成或语义验收。

`verify` 完整解码视频和音频，核对尺寸/帧数/帧率，失败返回非零。它不证明动作正确，也没有检查字幕、黑帧、保留区间或听感；这些需按制作参考补充。

## 异步视频任务

`job.json`：

```json
{
  "base_url": "https://api.x.ai/v1",
  "model": "grok-imagine-video-1.5",
  "prompt_file": "prompts/shot-01-video.txt",
  "duration": 4,
  "resolution": "720p",
  "aspect_ratio": "9:16",
  "image": "images/start.jpg",
  "last_frame": "images/end.jpg",
  "keyframes": [
    {"image": "images/side.jpg", "timestamp_s": 1},
    {"image": "images/reveal.jpg", "timestamp_s": 2}
  ]
}
```

这是用户已选择兼容 Grok 接口后的字段示例，不是默认模型或地址。`base_url/model` 必须来自本次确认的 `motion` 配置，使用前核对所选模型/服务支持的参数组合。`image/last_frame/keyframes` 都可省略；只有确需相应控制时填写。图像保持原字节发送；过大的图先另存压缩副本。提示词和图片路径相对于 `job.json`；工作回执路径相对于当前工作目录。

```bash
python3 "$SKILL_DIR/scripts/grok_video.py" prepare job.json
python3 "$SKILL_DIR/scripts/grok_video.py" submit job.json --state work/jobs/shot-01-v1.json
python3 "$SKILL_DIR/scripts/grok_video.py" poll job.json --state work/jobs/shot-01-v1.json
python3 "$SKILL_DIR/scripts/grok_video.py" download job.json --state work/jobs/shot-01-v1.json --out clips/shot-01-v1.mp4
```

`prepare` 不联网、不需要 key，也不占用任务状态。`submit/poll` 从 `VIDEO_API_KEY` 读取凭据；可用 `--key-env` 指定已存在的其他变量。不要把凭据放命令行参数。每次 `poll` 只查询一次，智能体按合理间隔继续。下载后运行媒体 `verify`。

结果链接失效时可对已完成任务执行 `poll ... --refresh` 查询新的链接，不重新生成。

同一个状态文件再次 `submit` 不重复发送 POST；输入或服务地址变了则拒绝复用。明确失败后的修正版应使用 `v2` 文件。若提交不确定而后从提供商记录找到请求 ID，可以执行：

```bash
python3 "$SKILL_DIR/scripts/grok_video.py" attach-id job.json --state work/jobs/shot-01-v1.json --request-id CONFIRMED_REQUEST_ID
```

不得捏造 ID 或绑定另一个任务。状态文件包含完整提示词、输入摘要与短期下载 URL，以 0600 保存；它属于私有工作记录。对外素材包使用去除临时 URL 的回执摘要（任务 ID、模型、参数、输入/输出摘要、状态），不直接打包环境配置、key 或含签名 URL 的内部状态。
