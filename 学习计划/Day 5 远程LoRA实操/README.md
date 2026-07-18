# Day 5：远程单卡 LoRA 实操

目标：在 AutoDL 单卡 GPU 上，用 Qwen3-8B 跑通公众号口吻 LoRA 训练闭环。

## 文件说明

- `source_data/`：从 Day 4 复制来的原始 SFT JSONL。
- `prepare_dataset.py`：校验、去重并切分训练集/验证集。
- `train_lora.py`：使用 Transformers + PEFT 做 BF16 LoRA。
- `chat_lora.py`：加载基座模型与 LoRA adapter 做多轮对话。
- `requirements.txt`：训练依赖。

## 远程执行

```bash
cd /root/autodl-tmp/projects/day5-lora
python prepare_dataset.py
pip install -U -r requirements.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
mkdir -p /root/autodl-tmp/models/Qwen3-8B
modelscope download --model Qwen/Qwen3-8B --local_dir /root/autodl-tmp/models/Qwen3-8B
python train_lora.py --model /root/autodl-tmp/models/Qwen3-8B
python chat_lora.py --model /root/autodl-tmp/models/Qwen3-8B
```

训练产物默认保存在：

```text
outputs/wechat-qwen3-8b-lora/final_adapter
```

首次运行会下载 `Qwen/Qwen3-8B`，需要约十几 GB 的磁盘空间。
