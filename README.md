# 基于 LoRA 与 vLLM 的 Mindcraft 游戏命令智能体

这是一个从大模型训练基础逐步推进到游戏智能体联调的学习型工程仓库。当前仓库的核心成果是：在开源 Mindcraft 框架之上，训练并部署一个将玩家英文自然语言映射为受控 Minecraft 动作的 LoRA 命令智能体。

仓库覆盖 Day 1 至 Day 18 的学习记录，但本 README 只聚焦目前仍可复核、可继续迭代的 Mindcraft 主线。早期目录保留为个人学习过程和脚本归档；原始学习语料、模型权重、缓存和运行记录均不在仓库中，也不作为可复现产物承诺。

## 项目定位

Mindcraft 已经提供 Minecraft bot、游戏交互、动作执行与对话框架。本项目不重复实现这些基础设施，而是完成其中“垂直命令模型”这一层的训练与接入：

```text
玩家聊天
-> Mindcraft Node.js 适配器
-> 本地 SSH 隧道
-> 远程命令安全网关
-> vLLM OpenAI 兼容推理服务
-> Qwen3-4B + LoRA 适配器
-> 命令白名单与参数校验
-> Mindcraft 已有动作执行器
-> Minecraft 世界反馈
```

这个项目是一个**受限命令路由智能体**，不是通用 Minecraft 大模型助手。当前只覆盖数据集中定义的命令和一个普通问候语；模型未覆盖的表达或命令会被安全网关拒绝，而不会直接交给游戏执行。

## 已完成成果

### 1. 数据构造与质量控制

- 以 Day 13 真实游戏成功行为和 Mindcraft 记忆轨迹为种子，构造监督微调（SFT）样本。
- 对英文同义表达进行人工审核，形成 10 个语义意图标签；其中包含 8 种可执行命令模板和 1 种允许的问候文本。两个“采集橡木”语义意图会映射到同一条采集命令。
- 按意图组织为 80 条训练样本和 20 条独立评测样本，避免同一句或近似改写同时出现在训练与评测中。
- 编写数据校验脚本，检查 JSONL 格式、消息角色、命令语法、允许命令范围及训练/测试泄漏。

当前允许的游戏动作包括：停止、查看背包、查询附近方块、靠近玩家、跟随玩家、搜索橡木、采集 4 个橡木原木和合成橡木木板。

### 2. 双 GPU LoRA 微调与离线评测

- 基座模型：`Qwen/Qwen3-4B`。
- 训练方式：在双 RTX 5090 环境中使用 `torchrun` 启动 DDP（分布式数据并行），以 bf16 精度进行 LoRA 监督微调。
- 训练完成 60 steps；最佳模型为 `checkpoint-45`，验证损失为 `0.015119`。
- 在 20 条未参与训练的保留集上，以“输出是否与期望命令完全一致”为标准，取得 `19/20 = 95.0%` 严格匹配率。
- 错误案例显示模型曾生成未定义的 `!hello` 命令。该观察直接推动了后续命令白名单设计，而不是把离线指标当作游戏安全性的替代品。

### 3. 推理服务与安全边界

模型输出不是游戏动作。本项目将生成和执行拆分为两层：

1. **生成层**：Qwen3-4B 加载 LoRA，依据玩家输入产生候选文本或命令。
2. **安全层**：`command_guard.py` 只接受完全匹配的白名单命令、固定问候文本及指定参数；空输出、未知命令、多行内容和普通自由文本都会被拒绝。

安全网关提供两个最小 HTTP 接口：

- `GET /health`：检查网关和上游模型服务是否可访问。
- `POST /command`：接收 `{"text": "please follow me"}`，返回原始模型输出及白名单判定结果。

网关仅监听远程机器的 `127.0.0.1:8765`，不直接暴露公网。Windows 本地游戏端通过 SSH 本地端口转发访问该服务，形成“远程 GPU 可用、外部网络不可直连”的部署边界。

### 4. vLLM 服务化部署

Day 17 的原型网关直接由 Transformers 和 PEFT 承担推理。Day 18 将模型托管切换为 vLLM：

- 使用 vLLM `0.25.1` 启动 OpenAI 兼容的 `/v1/chat/completions` 服务。
- 在服务启动时挂载 Day 15 的 `checkpoint-45` LoRA，并以 `mindcraft-lora` 作为请求模型别名。
- 通过 `/v1/models` 验证基座模型 `Qwen/Qwen3-4B` 与 LoRA 适配器均被服务发现。
- 对 Qwen3 固定关闭 thinking 输出，避免推理过程文本干扰精确命令解析。
- 在当前 RTX 5090 环境中，为绕过 FlashInfer sampler 初始化兼容问题，使用 `VLLM_USE_FLASHINFER_SAMPLER=0` 回退采样实现；该处理不修改 LoRA 权重或安全规则。

这里验证的是“LoRA 能否被 vLLM 稳定托管并接回游戏”，而不是吞吐量基准测试。当前尚未开展多并发压测，不能将本项目表述为已经验证高并发性能的生产服务。

### 5. 真实 Minecraft 联调

在本地 Minecraft 局域网与真实 Mindcraft bot 中，已完成下列端到端验证：

- `please follow me`：触发一次 `!followPlayer("robot", 3)`。
- `stop`：触发 `!stop` 并停止当前动作。
- `show your inventory`：触发一次 `!inventory`，并在游戏内回传动态背包结果。
- `what blocks are nearby`：触发 `!nearbyBlocks`，并在游戏内回传动态查询结果。
- `go chop four oak logs`：触发 `!collectBlocks("oak_log", 4)`。
- `make wooden planks`、`come closer`、`search for an oak tree again` 与问候语：均完成游戏内验证。

联调中修复了启动内部提示被错误发送、历史消息导致命令重复执行等问题。另观察到采集动作的路径执行层可能为了接近目标而额外破坏相连方块，因此“命令数量参数正确”不等于“世界中严格只破坏对应数量方块”；该问题已记录为后续严格采集模式的优化项。

## 仓库结构

```text
学习计划/
  Day 1 - Day 8/                         早期大模型应用、提示词与 LoRA 学习归档
  Day 9 Minecraft智能体方向规划/          项目方向与阶段目标
  Day 10 - Day 14/                        Mindcraft 环境、首次入游戏、行为基线与 DDP 准备
  Day 15 Mindcraft真实轨迹SFT数据构造/     数据集生成、校验、训练与评测脚本
  Day 16 LoRA推理与Mindcraft安全接入/      命令白名单和本地推理验证
  Day 17 LoRA服务与Mindcraft联调/          HTTP 网关、SSH 隧道与游戏适配器
  Day 18 vLLM部署与高并发推理/             vLLM 服务化、迁移说明和自包含安全网关
  Day 19 交互轨迹自动记录与数据扩展/         本地 JSONL 交互日志、汇总与数据筛选规则

简历.txt                                  本地简历项目描述，已被 .gitignore 排除
.gitignore                                隐私、权重、缓存、日志和运行产物排除规则
```

推荐阅读顺序：

1. [Day 9 方向规划](<学习计划/Day 9 Minecraft智能体方向规划/Minecraft智能体训练总体计划.md>)：理解为何选择 Mindcraft 与 LoRA。
2. [Day 13 行为基线](<学习计划/Day 13 Mindcraft行为基线测试/README.md>)：理解真实轨迹如何成为训练数据来源。
3. [Day 15 数据构造](<学习计划/Day 15 Mindcraft真实轨迹SFT数据构造/README.md>)：查看 SFT 数据原则、切分和训练评测方式。
4. [Day 16 安全接入](<学习计划/Day 16 LoRA推理与Mindcraft安全接入/README.md>)：查看模型输出为何必须经过白名单。
5. [Day 17 游戏联调](<学习计划/Day 17 LoRA服务与Mindcraft联调/README.md>)：查看 HTTP、SSH 与 Mindcraft 适配器如何串联。
6. [Day 18 vLLM 部署](<学习计划/Day 18 vLLM部署与高并发推理/README.md>)：查看 vLLM 如何替换直接 Transformers 推理。

## 环境与复现边界

本项目跨越本地 Windows、远程 AutoDL GPU 和 Minecraft 局域网三类环境。仓库中保留代码、说明和少量不含敏感信息的评测报告，但以下内容不会上传：

- API Key、SSH 私钥、账号信息、局域网地址、个人聊天和游戏运行记录；
- 原始语料、原始 PDF、模型权重、LoRA checkpoint、Hugging Face 缓存和训练日志；
- `node_modules`、Minecraft bot 运行目录、截图和个人机器配置。

因此，克隆仓库后不能直接完成训练或进入游戏。复现时需要自行准备 Qwen3-4B 权重、合法的 Minecraft 环境、远程 GPU、LoRA checkpoint 或重新运行 Day 15 的训练流程，并根据各 Day README 配置路径与端口。

## 第三方项目与署名

Mindcraft 相关代码基于开源项目 [mindcraft-bots/mindcraft](https://github.com/mindcraft-bots/mindcraft) 学习和二次开发。其 MIT License 与版权声明保留在：

`学习计划/Day 11 Mindcraft训练项目启动/mindcraft-develop/LICENSE`

本人完成的工作包括行为基线记录、SFT 数据构造与校验、Qwen3-4B LoRA 训练和评测、命令白名单、Python/vLLM 网关、SSH 隧道接入，以及 `src/models/mindcraft_lora.js` 适配器和实验 profile。本仓库不声称 Mindcraft 框架、Minecraft bot 框架或其上游功能由本人从零实现；继续分发或修改相关代码时应遵守其 MIT License 并保留原始版权声明。

## 当前状态与下一步

Day 1-18 已完成归档。Day 19 正在为真实游戏交互加入本地 JSONL 自动记录：玩家请求、模型输出、白名单判定、服务异常和游戏系统反馈将用于后续人工筛选。当前端到端链路已打通：LoRA 离线评测、vLLM 服务、命令安全网关、SSH 隧道和真实 Minecraft 游戏验证均已完成。

下一步计划扩大训练样本和独立评测集，重点补充同义表达、歧义请求、未知命令和数量边界案例；随后重新训练并比较验证损失、严格匹配率与真实游戏执行效果。在能力扩展前，任何新命令都需要同时补充训练数据、离线评测和白名单规则。
