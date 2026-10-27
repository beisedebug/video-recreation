# Seedance、Grok、Veo（Flow）与 Muse Video：给用户的选择依据

官方资料核验：**2026-10-26**。这是文档能力比较，未进行同片、同参数的画质／速度／成功率测试，亦未验证当前账户权益。下一次实际生成前复核所选模型与渠道；版本、地区、套餐、输入模式会改变可用功能。不要从这张表推导其他版本也支持。

## 先分清模型与入口

本选择流程按用户已明确的含义：**SD = Seedance；Flow = 通过 Flow 使用 Veo；Muse = Muse Video 视频模型**。这四项按视频生成路线比较，不再要求用户辨认 Muse 是助手还是模型。即梦、豆包、火山 API 是 Seedance 的可能渠道；Grok 网页与 xAI API 也分别检查。

Flow 的底层模型按用户选择锁定为 Veo，不能因为工作台出现其他模型就静默改用。若运行该技能的宿主恰好是 Muse／Muse Code，另记为宿主信息，不影响这里的 Muse Video 选项。

记录三项即可：`host`（在哪个助手执行）、`channel`（网页／内置工具／具体 API 提供商）、`model`（实际模型标识，未暴露则由渠道管理）。技能有说明文档不等于具备对应 API 适配器。

## 用户选择卡

按当前需求展示相关差异，下面“适合”是根据能力作出的工作流建议，不是性能排名。

| 可选路线 | 文档确认的控制手段 | 适合先展示给哪类用户 | 需要说明的限制 |
|---|---|---|---|
| **Seedance 2.5：即梦／豆包或已开通 API** | 视频／图像／音频参考，首尾帧，视频编辑与延长，原生音视频；可参考镜头语言 | “沿用参考的节奏，但按我的想法改运镜” | 首尾帧与全模态参考模式互斥；网页功能不等于 API 功能；运镜以提示词和参考表达 |
| **Grok Imagine：按具体版本选择** | 1.5 的首尾帧与中间关键帧、图像参考、音频；另有指定版本的原视频编辑 | “我知道开头、中间、结尾该是什么构图”或“已有可调用的 Grok 流程” | 生成与编辑的型号、时长和分辨率限制不同；第三方兼容接口不自动等于官方 API |
| **Veo（通过 Flow）** | Veo 支持文字／图像生成、首尾帧、按版本支持素材参考和音频；Flow 提供制作界面 | “想在 Flow 中用 Veo 看结果、调镜头、串联场景” | 以 Veo 具体版本和输入模式为准；Flow 的相机调整须检查是否适用于当前 Veo 模式，不能借用其他模型能力 |
| **Muse Video** | 官方预览确认视频生成与原生音频；Meta AI 视频权益公告也提到 Muse 模型 | “想用 Muse 视频模型完成这段创意”或“已经在用 Muse 视频入口” | 先核实当前入口的模型、参考输入和控制项；首尾帧／关键帧／运镜参数公开资料不足，保持待验证，不作强弱结论 |

来源：[Seedance 2.5 官方发布](https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5)、[xAI 视频总览](https://docs.x.ai/developers/model-capabilities/video/overview)、[Flow 功能矩阵](https://support.google.com/flow/answer/16352836?hl=en)、[Muse Video 预览](https://ai.meta.com/blog/introducing-muse-image-muse-video-msl)。

可这样问：

> 这段需要参考原片动作，同时改变运镜。Seedance 可利用视频参考；Grok 1.5 可用关键帧约束分阶段构图；Veo 可以通过 Flow 的制作界面调整；Muse Video 也是候选，需先检查当前入口提供哪些参考控制。你可以直接选已有模型；不确定时，我会按你最在意的效果给建议。

用户已明确选定模型、渠道或长期默认时直接沿用，不强制再做四选一。只分析／只要提示词可保留模型无关版本，不为此索要登录或密钥。用户只说“你来选”是授权依据：根据任务与可用渠道给出简短理由并记录选择；若还涉及未明确的新增付费预算或素材上传边界，只补足实际缺项。

## 执行时核对的细节

### Seedance

2.5 官方发布于 2026-07-31，支持单次最长 30 秒。当前火山创建任务文档列出 2.5 支持 4–30 秒、最多 30 图／10 视频／10 音频，参考视频总时长最多 30 秒；2.0 的限额是 9 图／3 视频／3 音频、4–15 秒。每个请求还须检查模式和素材组合，不能只按总数量通过。

首尾帧模式与全模态参考模式互斥。要严格约束首尾图就使用相应模式；要借鉴视频动作／运镜就声明参考用途。参考生成、编辑、延长分别选择正确模式，不能承诺编辑未指定区域像素完全不变。

2.x 的运镜通过提示词与参考表达。当前文档中的 `camera_fixed`、`seed` 仅列 1.0 pro／fast 支持，不能把本技能的 `camera_phases`、轨迹、角度等工作记录直接作为 API 参数发送。具体模型 ID 取自所选账户与当前官方文档。

来源：[Seedance 2.5](https://seed.bytedance.com/zh/seedance2_5)、[创建视频任务 API](https://console.volcengine.com/ark/region:cn-beijing/docs/create-video-generation-task-api)、[2.0 提示指南](https://docs.volcengine.com/docs/ark/seedance-2-0-prompt-guide?lang=zh)。

### Grok Imagine

`grok-imagine-video-1.5` 的文档列有最长 15 秒、最多 14 张参考图、首尾帧与最多 4 个中间关键帧、原生音频。参考模式最高 720p；1080p 原生输出用于文生／图生模式。Lite 的能力不同，不能套用参考图与关键帧配置。

原视频编辑文档使用的是 `grok-imagine-video`，输入片段最多 8.7 秒，输出保持源时长和画幅、最高 720p；不能用生成参数强行设置编辑输出规格。不要把这项功能自动归给 1.5。

本包 `grok_video.py` 适配其说明中的生成／查询协议，不因此获得多参考、原视频编辑或所有版本能力。先读脚本支持的字段和所选提供商实际文档；未实现的路径要用已有专用工具或单独实现适配，不能把失败伪装成已提交。

来源：[总览](https://docs.x.ai/developers/model-capabilities/video/overview)、[参考模式](https://docs.x.ai/developers/model-capabilities/video/reference-to-video)、[视频编辑](https://docs.x.ai/developers/model-capabilities/video/editing)。

### Veo（通过 Flow）

Flow 当前帮助页列有多个模型；本路线只使用用户指定的 **Veo**。Veo 3.1 Quality 不支持 Ingredients，Lite／Fast 支持；续写使用 Lite。视频生成、参考生成与续写按 Veo 当前支持模式实现。Flow 帮助中由其他模型完成的上传视频编辑，不能记为 Veo 的能力；如核心需求只能用其他模型，说明这一限制并由用户选择是否改变后端。

Camera Adjustment／Reshoot 是官方已发布的运镜调整能力，包含改变机位、orbit、dolly 等；官方说明原片无相机运动时效果最好。历史发布不证明当前任一模型／账户均显示该按钮；选定 Flow 后先检查真实界面支持，再编写执行步骤。

Flow 网页操作与 Google 视频 API 分开。Gemini API 的三款 Veo 3.1 Preview 已于 **2026-10-22** 停用，不沿用旧 `*-preview` ID。Cloud GA `veo-3.1-generate-001` 当前支持 4／6／8 秒，参考图模式仅 8 秒；使用前继续核对当前产品入口与模型可用性。

来源：[Flow 模型矩阵](https://support.google.com/flow/answer/16352836?hl=en)、[上传视频编辑所用模型](https://support.google.com/flow/answer/16935718?hl=en)、[相机调整介绍](https://blog.google/innovation-and-ai/models-and-research/google-labs/flow-refine-videos/)、[API 弃用表](https://ai.google.dev/gemini-api/docs/deprecations)、[Cloud Veo 3.1](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate)。

### Muse Video

Muse Video 在 2026-07-07 获官方预览，含原生音频；2026-09-15 Meta One 公告列 Muse 模型驱动的视频生成权益。因此不要写“Muse 没有视频生成”。本次未检得可直接用于实现的 Muse Video 公共 API、完整运镜参数与首尾帧／参考限额文档；这些保持 `unverified`，不等同于功能不存在。

选择 Muse Video 后，检查用户指定入口实际暴露的输入模式、时长与音频选项，不再问用户是否指 Muse 助手。若只出现一个未说明底层模型的视频工具，记录“由渠道管理／尚未确认是否 Muse Video”；不能把它的成功调用当成 Muse Video 模型验证。必须通过当前入口说明或工具元数据建立对应关系。没有足够的接入能力时先完成通用镜头计划和提示词，明确生成尚未完成。

运行宿主的加载、文件与工具说明见 [Muse 适配](muse.md)。其中历史测试未公开底层版本，不能用来比较 Muse Video 的画质或运镜能力。Muse Spark 的视频理解也不是 Muse Video 的生成证据。

来源：[Muse 发布](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/)、[Muse Code](https://dev.meta.ai/docs/muse-code)、[模型目录](https://dev.meta.ai/docs/models)、[Muse Video 预览](https://ai.meta.com/blog/introducing-muse-image-muse-video-msl)、[Meta One 公告](https://about.fb.com/news/2026/09/introducing-meta-one-subscription-service-more-features-ai/)、[开发者总览](https://dev.meta.ai/docs/overview)。

## 选择后如何落地

将运镜计划转成该渠道实际接受的提示词与参考输入；记录已核实的 `reference_video / first_last_frame / keyframes / native_audio / video_edit` 能力和来源。没有实查的能力为 `not_checked`。不支持核心目标时，明确取舍并给替代路线，不静默更换平台或放弃保留条件。

成本、速度、成功率在本次没有对照实测。用户以价格或等待时间作选择依据时，查询所选地区／账号的当前价格与限额，不引用社区稳定度作预算估算。实际运镜遵循度通过代表镜头验证，遵循主技能的有限修正和续跑规则。
