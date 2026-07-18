# Day 10：Mindcraft 项目准备工作

> 项目准备：Minecraft 智能体训练项目。  
> 目标：确认环境、依赖、数据目录和训练闭环的准备事项。

## 1. 本地负责什么

本地 Windows 主要负责：

- 阅读 Mindcraft 项目结构；
- 编辑 profile、任务文件和训练数据脚本；
- 整理任务日志；
- 生成 SFT/DPO 数据；
- 写规划文档和实验记录。

本地可以尝试跑 Mindcraft，但真正训练和 vLLM 服务建议放到远程 GPU。

## 2. 远程 GPU 负责什么

远程 AutoDL/GPU 主要负责：

- LoRA/SFT 训练；
- DeepSpeed 多卡训练；
- vLLM 推理服务；
- 批量任务评测；
- 长时间实验与日志保存。

## 3. Mindcraft 依赖方向

Mindcraft 本身是 Node.js 项目，核心依赖在：

```text
mindcraft-develop/package.json
```

安装通常是：

```bash
cd mindcraft-develop
npm install
```

任务评测相关 Python 依赖在：

```text
mindcraft-develop/requirements.txt
```

安装通常是：

```bash
pip install -r requirements.txt
```

## 4. 训练侧依赖方向

训练侧依赖和之前 LoRA 项目类似：

- `torch`
- `transformers`
- `datasets`
- `accelerate`
- `peft`
- `trl`
- `deepspeed`
- `vllm`

这些不建议全装在本地 Windows。等连上远程 GPU 后再装。

## 5. 数据目录建议

后续训练数据单独放：

```text
data/mindcraft_training/
  raw_logs/
  processed_trajectories/
  sft/
  preference/
  eval_results/
```

含义：

- `raw_logs/`：Mindcraft 原始运行日志；
- `processed_trajectories/`：清洗后的任务轨迹；
- `sft/`：监督微调数据；
- `preference/`：偏好训练数据；
- `eval_results/`：训练前后评测结果。

## 6. 准备工作优先级

第一优先级不是训练，而是跑通 baseline。

顺序应该是：

1. 能启动 Mindcraft；
2. 能跑一个基础任务；
3. 能保存 memory/log/result；
4. 能从日志里抽取一次完整轨迹；
5. 再开始训练数据构造。

## 7. 风险提示

Mindcraft 允许模型写代码时会有安全风险。项目 README 也提醒过，`allow_insecure_coding` 默认关闭。

第一阶段建议：

- 只跑基础 crafting 任务；
- 不打开 insecure coding；
- 不连公共服务器；
- 优先本地 LAN 或隔离环境；
- 远程实验尽量使用容器或干净机器。
