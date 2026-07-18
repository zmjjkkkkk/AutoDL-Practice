# 双卡 DDP 验证结果

## 资源配置

- 服务器：AutoDL 北京 B 区 558 机
- GPU：2 x NVIDIA GeForce RTX 5090（每卡 32GB）
- CPU：32 核
- 内存：180GB
- 镜像：PyTorch 2.8.0 / Python 3.12 / Ubuntu 22.04 / CUDA 12.8
- 启动方式：`torchrun --standalone --nproc_per_node=2 ddp_smoke_test.py`

## 运行结果

```json
{
  "world_size": 2,
  "backend": "nccl",
  "gpu_count_visible": 2,
  "gpus": [
    "NVIDIA GeForce RTX 5090",
    "NVIDIA GeForce RTX 5090"
  ],
  "steps": 20,
  "batch_size_per_gpu": 256,
  "global_batch_size": 512,
  "final_mean_loss": 1.0272843837738037,
  "elapsed_seconds": 0.44542069360613823,
  "parameter_fingerprints": [
    13.599583286308839,
    13.599583286308839
  ],
  "parameter_fingerprints_match": true
}
```

## 结论

本次单机双卡 DDP 验证成功：

- `world_size: 2` 说明 `torchrun` 确实启动了两个训练进程。
- `backend: nccl` 说明两个进程使用 NVIDIA 的 GPU 通信库完成同步。
- 两张 RTX 5090 都被 PyTorch 识别并参与训练。
- 每卡 batch 为 256，双卡全局 batch 为 512，符合数据并行的预期。
- 两个参数指纹完全一致，且 `parameter_fingerprints_match: true`，证明每一步反向传播后的梯度同步有效，最终模型参数一致。

`elapsed_seconds` 只有约 0.45 秒，是因为该实验模型很小；它用于验证分布式链路，不应作为大模型训练吞吐量的性能结论。

下一阶段可在已验证的双卡 DDP 基础上接入 DeepSpeed，并使用真实的 Minecraft 行为轨迹构造训练任务。
