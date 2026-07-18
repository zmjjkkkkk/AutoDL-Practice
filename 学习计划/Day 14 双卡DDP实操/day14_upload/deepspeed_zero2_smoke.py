"""用 DeepSpeed ZeRO Stage 2 在单机双卡上完成一次最小训练。"""

import argparse
import json
import os
import time
from pathlib import Path

import deepspeed
import torch
import torch.distributed as dist
import torch.nn as nn


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
INPUT_DIM = 1024
HIDDEN_DIM = 2048
OUTPUT_DIM = 128
STEPS = 20
BATCH_SIZE_PER_GPU = 256


class TinyNetwork(nn.Module):
    """这里用小网络演示 ZeRO；未来可替换为语言模型或策略模型。"""

    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(INPUT_DIM, HIDDEN_DIM),
            nn.GELU(),
            nn.Linear(HIDDEN_DIM, OUTPUT_DIM),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.layers(features)


def parameter_fingerprint(model: nn.Module, device: torch.device) -> float:
    """将参数压缩为数值，用于验证 ZeRO 训练后的模型在各 rank 间一致。"""
    total = torch.zeros(1, device=device, dtype=torch.float64)
    for parameter in model.parameters():
        total += parameter.detach().double().sum()
    return total.item()


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSpeed ZeRO-2 双卡验证")
    # DeepSpeed 会统一注册 --deepspeed 和 --deepspeed_config，不能重复添加。
    parser = deepspeed.add_config_arguments(parser)
    args = parser.parse_args()

    local_rank = int(os.environ["LOCAL_RANK"])
    torch.cuda.set_device(local_rank)
    device = torch.device(f"cuda:{local_rank}")

    # DeepSpeed launcher 会设置 rank 等环境变量；此处建立 NCCL 通信组。
    deepspeed.init_distributed(dist_backend="nccl")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    torch.manual_seed(20260714 + rank)

    model = TinyNetwork()
    engine, _, _, _ = deepspeed.initialize(
        args=args,
        model=model,
        model_parameters=model.parameters(),
    )

    if rank == 0:
        print(f"DeepSpeed 已启动：world_size={world_size}，ZeRO Stage 2，bf16 已启用")
    print(f"[rank {rank}] 使用 cuda:{local_rank} | {torch.cuda.get_device_name(local_rank)}")

    torch.cuda.synchronize(device)
    started_at = time.perf_counter()
    final_mean_loss = 0.0

    for step in range(1, STEPS + 1):
        features = torch.randn(
            BATCH_SIZE_PER_GPU,
            INPUT_DIM,
            device=device,
            dtype=torch.bfloat16,
        )
        labels = torch.randn(
            BATCH_SIZE_PER_GPU,
            OUTPUT_DIM,
            device=device,
            dtype=torch.bfloat16,
        )

        predictions = engine(features)
        # bf16 训练时将 loss 转为 float32 计算，数值更稳定。
        loss = (predictions.float() - labels.float()).square().mean()
        engine.backward(loss)
        engine.step()

        mean_loss = loss.detach().clone()
        dist.all_reduce(mean_loss, op=dist.ReduceOp.AVG)
        final_mean_loss = mean_loss.item()
        if rank == 0 and step in {1, STEPS}:
            print(f"step={step:02d}/{STEPS} | 双卡平均 loss={final_mean_loss:.6f}")

    torch.cuda.synchronize(device)
    elapsed_seconds = time.perf_counter() - started_at

    local_fingerprint = torch.tensor(
        [parameter_fingerprint(engine.module, device)],
        device=device,
        dtype=torch.float64,
    )
    all_fingerprints = [torch.zeros_like(local_fingerprint) for _ in range(world_size)]
    dist.all_gather(all_fingerprints, local_fingerprint)
    fingerprints = [item.item() for item in all_fingerprints]
    fingerprints_match = max(fingerprints) - min(fingerprints) < 1e-8

    if rank == 0:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "launcher": "deepspeed --num_gpus=2",
            "deepspeed_version": deepspeed.__version__,
            "zero_stage": 2,
            "precision": "bf16",
            "world_size": world_size,
            "gpus": [torch.cuda.get_device_name(index) for index in range(world_size)],
            "batch_size_per_gpu": BATCH_SIZE_PER_GPU,
            "global_batch_size": BATCH_SIZE_PER_GPU * world_size,
            "steps": STEPS,
            "final_mean_loss": final_mean_loss,
            "elapsed_seconds": elapsed_seconds,
            "parameter_fingerprints": fingerprints,
            "parameter_fingerprints_match": fingerprints_match,
        }
        report_path = OUTPUT_DIR / "deepspeed_zero2_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"DeepSpeed ZeRO-2 验证完成，结果已保存：{report_path}")
        print(f"两张卡参数一致：{fingerprints_match}")

    dist.barrier()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
