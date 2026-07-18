# Day 9：Minecraft 智能体训练总体计划

> 项目方向：基于 Mindcraft，把大模型训练技术栈用于 Minecraft 智能体能力增强。  
> 核心目标：不是重新搭建 Minecraft bot 框架，而是在已有 Mindcraft 框架上做训练、评测、部署和延续。

## 1. 为什么这个方向可行

Mindcraft 已经完成了最难的一层：让大模型可以进入 Minecraft 环境，通过 Mineflayer 控制角色、执行任务、与其他智能体协作，并留下任务日志和评测结果。

这意味着我们不需要从零写一个 Minecraft 代理框架，而可以把研究重点放到更像“大模型训练项目”的问题上：

- 如何收集 Minecraft 任务轨迹；
- 如何把成功/失败样本转成训练数据；
- 如何训练一个更会规划、协作、执行命令的模型；
- 如何用 vLLM 把训练后的模型接回 Mindcraft；
- 如何用多卡训练、DeepSpeed、训推一体化和 910C 适配去扩展项目。

一句话：Mindcraft 给了环境和框架，我们做模型能力增强。

## 2. 项目定位

本项目聚焦具身智能体训练，而不是普通文本生成：

> 训练一个更懂 Minecraft 任务、能更稳定完成采集、合成、烹饪、建造与多智能体协作的 LLM Agent。

它的能力不只是“会聊天”，而是：

- 能理解任务目标；
- 能拆解步骤；
- 能调用已有指令；
- 能根据环境反馈调整计划；
- 能与其他智能体沟通；
- 能从失败轨迹中学习；
- 能通过 vLLM 接入 Mindcraft 框架。

## 3. Mindcraft 当前已有基础

根据当前本地 `mindcraft-develop` 项目结构，已经具备：

- `main.js`：主启动入口；
- `profiles/`：模型配置与 agent profile；
- `profiles/vllm.json`：已经支持本地 vLLM OpenAI-compatible API；
- `tasks/`：已有 crafting、cooking、construction 等任务集；
- `tasks/evaluation_script.py`：任务评测脚本；
- `src/models/vllm.js`：vLLM 模型接入逻辑；
- `minecollab.md`：多智能体任务与评测说明；
- `bots/`：运行后可产生 agent 记忆、日志和任务记录。

所以项目已经具备“训推闭环”的雏形。

## 4. 我们真正要做的训练

### 4.1 SFT 训练

先把 Mindcraft 中成功完成任务的轨迹整理成 SFT 数据。

输入可以包含：

- 当前任务目标；
- 背包状态；
- 附近环境；
- 历史对话；
- 可用指令；
- 上一步执行结果。

输出可以是：

- 下一步计划；
- 与队友沟通的话；
- 应该调用的 Minecraft 指令；
- 失败后的修正策略。

### 4.2 偏好训练

同一个任务可能有成功轨迹和失败轨迹。

可以构造偏好数据：

- chosen：更合理、更接近成功的行动；
- rejected：导致卡住、乱走、重复、幻觉或无效操作的行动。

后续可用于 DPO/ORPO 一类训练。

### 4.3 多智能体协作训练

Mindcraft 的 cooking、crafting、construction 任务天然包含多智能体协作。

重点训练：

- 分工；
- 汇报库存；
- 请求队友给物品；
- 解释合成路径；
- 避免重复劳动；
- 在 blocked actions 条件下调整计划。

## 5. 大模型技术栈如何自然融入

### 5.1 多卡训练

当训练数据增多、模型变大、上下文变长时，单卡会遇到显存和速度瓶颈。

多卡训练可用于：

- 扩大 batch size；
- 训练 7B/14B/32B 级别模型；
- 支持更长 Minecraft 轨迹上下文；
- 对比单卡与多卡的训练吞吐和效果。

### 5.2 DeepSpeed

DeepSpeed 用在训练阶段，尤其适合：

- LoRA/SFT 多卡训练；
- ZeRO-2 与 ZeRO-3 对比；
- 降低优化器状态和梯度的显存压力；
- 记录吞吐、显存占用、训练稳定性。

本项目中，DeepSpeed 不是装饰词，而是用来把 Minecraft 轨迹训练扩展到更大模型。

### 5.3 vLLM

vLLM 用在推理阶段。

训练后的模型或 LoRA 合并模型可以通过 vLLM 启动成 OpenAI-compatible API，然后 Mindcraft 通过 `profiles/vllm.json` 调用它。

典型链路：

```text
训练数据 -> LoRA/SFT -> 模型权重 -> vLLM 服务 -> Mindcraft profile -> Minecraft 任务评测
```

### 5.4 训推一体化

本项目最有价值的地方在于闭环：

```text
运行 Mindcraft 任务
-> 收集轨迹与结果
-> 清洗成训练数据
-> LoRA/SFT/DPO
-> vLLM 部署
-> 再跑 Mindcraft 任务
-> 对比成功率与失败类型
```

这比单纯训练一个聊天模型更像真实智能体研究。

### 5.5 910C / NPU 适配

910C 可以作为后期异构算力适配路线。

可研究：

- CUDA GPU 与 CANN/HCCL/NPU 软件栈差异；
- `torch_npu` 训练兼容性；
- LoRA 训练或推理能否迁移；
- vLLM Ascend 或 MindIE 部署路线；
- 同一模型在 GPU 与 NPU 上的吞吐、延迟和兼容性差异。

注意：910C 不作为第一阶段目标。第一阶段先用 GPU 把训练闭环打通。

## 6. 阶段路线

### 第一阶段：跑通 Mindcraft

- 安装 Node.js 依赖；
- 配置一个可用 profile；
- 用 API 或 vLLM 跑单个基础任务；
- 确认日志、memory、score 能被保存。

### 第二阶段：收集训练数据

- 选择 crafting 单智能体任务；
- 跑 baseline；
- 收集成功和失败轨迹；
- 编写数据转换脚本；
- 生成 SFT JSONL。

### 第三阶段：LoRA 训练

- 选择 Qwen/Llama 系列 instruct 模型；
- 训练 Minecraft 行动规划 LoRA；
- 保存 adapter；
- 合并或直接加载 adapter。

### 第四阶段：接回 Mindcraft

- 用 vLLM 启动训练后的模型；
- 修改 `profiles/vllm.json`；
- 用同一任务集评测；
- 对比训练前后成功率。

### 第五阶段：多卡与 DeepSpeed

- 扩大任务集；
- 增加多智能体任务；
- 用 DeepSpeed 多卡训练；
- 对比单卡、多卡、不同 ZeRO 配置。

### 第六阶段：910C/NPU 研究

- 确认可用机器与软件栈；
- 尝试模型加载、LoRA 推理、vLLM Ascend/MindIE；
- 记录兼容性问题。

## 7. 今日结论

这个方向可行，而且适合系统展示大模型训练技术栈。

Mindcraft 智能体项目可以体现：

- 数据闭环；
- 智能体行为训练；
- 多智能体协作；
- 多卡训练；
- DeepSpeed；
- vLLM 推理；
- 训推一体；
- 910C 异构适配。

港真，这个方向更像一个可以继续做深的科研训练项目。
