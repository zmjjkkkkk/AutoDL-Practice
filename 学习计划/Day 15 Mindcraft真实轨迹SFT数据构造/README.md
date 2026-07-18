# Day 15: Mindcraft 真实轨迹 SFT 数据构造

## 今天的目标

把 Day 13 的 10 条真实成功行为作为可追溯的种子，构造成可用于 LoRA SFT 的 JSONL 数据集。

这一步还不启动训练。小数据最容易出现的问题不是显卡不够，而是标签不准确、训练集和测试集泄漏，或者模型学到无效命令。先把数据做干净，再送到双卡环境训练。

## 什么是 SFT 数据

SFT（Supervised Fine-Tuning，监督微调）是一组“输入 -> 标准答案”的示范。例如：

```json
{
  "messages": [
    {"role": "system", "content": "You are a Minecraft agent..."},
    {"role": "user", "content": "collect 4 oak logs"},
    {"role": "assistant", "content": "!collectBlocks(\"oak_log\", 4)"}
  ]
}
```

基础模型本来就懂英语和一部分 Minecraft 常识；SFT 要强化的是“玩家自然语言 -> 当前 Mindcraft 可执行命令”的稳定映射。

## 数据来源与原则

- 来源：Day 13 的 `output/latest_behavior_baseline.json` 和真实记忆轨迹。
- 不使用基线输出中已损坏的中文 `observed_behavior` 字段。
- 每条命令都按当前 Mindcraft 源码中的实际函数名和参数格式编写。
- 每个真实种子扩写为人工审核的英文同义表达；扩写内容标记为 `human_reviewed_paraphrase`，不伪装成真实对话。
- 每个意图保留 2 条未进入训练集的表达用于评测，避免同一句换个文件又被当成“测试”。

`collect_some_wood` 的原始行为没有保存精确命令参数；本数据集明确采用项目策略“未指定木材时默认采集 4 个 oak_log”，并在元数据中标记为 `policy_specified`。以后有更完整的真实轨迹时，应优先替换这类策略标签。

## 生成与验证

在此目录执行：

```powershell
python build_sft_dataset.py
python validate_sft_dataset.py
```

会生成：

- `output/mindcraft_sft_train.jsonl`：80 条训练样本
- `output/mindcraft_sft_eval.jsonl`：20 条保留评测样本
- `output/mindcraft_sft_manifest.json`：来源、切分和命令统计

## 下一步

先人工抽查 JSONL 中的命令和回答，再在两张 RTX 5090 上做一次小规模 bf16 LoRA 训练。这里使用 Qwen3-4B：模型参数以 bf16 在每张 32GB 卡上完整加载，只有 LoRA 适配器参与反向传播，因此不必为这个小数据集引入 4-bit 量化的额外兼容风险。

远程训练命令：

```bash
cd /root/autodl-tmp/day15-sft
HF_HOME=/root/autodl-tmp/day15-sft/hf-cache torchrun --standalone --nproc_per_node=2 train_lora_sft.py
CUDA_VISIBLE_DEVICES=0 HF_HOME=/root/autodl-tmp/day15-sft/hf-cache python evaluate_lora_sft.py
```

训练后不能只看 loss，还要查看 `artifacts/qwen3_4b_mindcraft_lora/command_eval.json` 中的严格命令匹配率，确认输出仍符合 Mindcraft 的实际语法。

Day 15 的训练结果、模型恢复、评测与下一阶段的安全接入计划，已整理到 [Day 16 LoRA推理与Mindcraft安全接入](../Day%2016%20LoRA推理与Mindcraft安全接入/README.md)。
