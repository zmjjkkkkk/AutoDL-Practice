# Day 8：LoRA 项目收尾

目标：加载 Day 5 的旧 adapter，用最终纠偏数据继续训练 1 个 epoch，输出最终版 adapter。

## 数据原则

- 保留 Day 5 的有效训练/验证数据。
- 不回灌 Day 7 的低分自动回答。
- 新增 10 条人工纠偏样本，重点修复虚构履历、模板口癖、主客观混淆。

## 远程执行

将整个 Day 8 文件夹上传到：

```text
/root/autodl-tmp/projects/day8
```

整理数据：

```bash
cd /root/autodl-tmp/projects/day8
python build_final_dataset.py
```

继续训练一轮：

```bash
python train_final_round.py \
  --model /root/autodl-tmp/models/Qwen3-8B \
  --adapter /root/autodl-tmp/projects/day5-lora/outputs/wechat-qwen3-8b-lora/final_adapter \
  --epochs 1
```

最终 adapter：

```text
outputs/wechat-agent-final-v2/final_adapter_v2
```

启动最终智能体：

```bash
python chat_final_agent.py \
  --model /root/autodl-tmp/models/Qwen3-8B \
  --adapter /root/autodl-tmp/projects/day8/outputs/wechat-agent-final-v2/final_adapter_v2
```
