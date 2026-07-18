# Day 16: LoRA 推理与 Mindcraft 安全接入

## 阶段目标

使用 Day 15 训练好的 LoRA 适配器，将玩家自然语言转换为 Mindcraft 命令；在真正发送给游戏前加入命令白名单和参数校验。

## 2026-07-16 已完成记录

- 在远程双 RTX 5090 环境完成 `Qwen/Qwen3-4B` 的 bf16 LoRA SFT。
- Day 15 数据集：训练集 80 条，评测集 20 条，数据集校验通过。
- 训练执行至第 60 步。多卡启动器在训练收尾阶段返回异常，但 checkpoint 已写入磁盘，不需要重训。
- 当前最佳 LoRA 适配器：`artifacts/qwen3_4b_mindcraft_lora/checkpoint-45`
- 最佳验证损失：`0.015119247138500214`
- 严格命令匹配：`19/20 = 95.0%`
- 评测报告：`artifacts/qwen3_4b_mindcraft_lora/command_eval.json`

## 评测发现的安全问题

失败样本：`are you there`

- 期望：`Hello! What can I help with?`
- 模型输出：`!hello`

`!hello` 不是当前 Mindcraft 支持的命令。因此不能把模型的任意输出直接发送给游戏；未知的 `!` 开头内容必须被拦截。

## 本目录文件

- `infer_mindcraft_command.py`：加载基础模型与 LoRA 适配器，支持单次或交互式推理。
- `command_guard.py`：白名单只放行当前数据集已验证的命令和问候回复。
- `test_inference.py`：英文严格匹配测试，外加不计入分数的中文探索测试。

## 远程运行

将本目录的三个 `.py` 文件上传到远程服务器后，在远程目录执行：

```bash
CUDA_VISIBLE_DEVICES=0 \
HF_HOME=/root/autodl-tmp/day15-sft/hf-cache \
HF_HUB_OFFLINE=1 \
python infer_mindcraft_command.py \
  --adapter_dir /root/autodl-tmp/day15-sft/artifacts/qwen3_4b_mindcraft_lora/checkpoint-45 \
  --prompt "please follow me"
```

运行冒烟测试：

```bash
CUDA_VISIBLE_DEVICES=0 \
HF_HOME=/root/autodl-tmp/day15-sft/hf-cache \
HF_HUB_OFFLINE=1 \
python test_inference.py \
  --adapter_dir /root/autodl-tmp/day15-sft/artifacts/qwen3_4b_mindcraft_lora/checkpoint-45 \
  --report_path inference_smoke_report.json
```

## 后续任务

1. 查看冒烟测试中的原始模型输出和白名单判定。
2. 记录失败或被拦截的表达，补入下一轮 SFT 数据。
3. 将通过白名单的命令接入本地 Mindcraft bot，进行端到端游戏测试。
