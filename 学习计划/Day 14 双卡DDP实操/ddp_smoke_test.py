"""用一个小型神经网络验证单机双卡 DDP 是否真正工作。"""

import json
import os
import socket
import time
from pathlib import Path

import torch
import torch.distributed as dist
import torch.nn as nn
from torch.nn.parallel import DistributedDataParallel as DDP


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
INPUT_DIM = 1024
HIDDEN_DIM = 2048
OUTPUT_DIM = 128
STEPS = 20
BATCH_SIZE_PER_GPU = 256


def build_model() -> nn.Module:
    """构建一个足够小、但确实需要反向传播和梯度同步的网络。"""
    return nn.Sequential(
        nn.Linear(INPUT_DIM, HIDDEN_DIM),
        nn.GELU(),
        nn.Linear(HIDDEN_DIM, OUTPUT_DIM),
    )


def parameter_fingerprint(model: nn.Module, device: torch.device) -> float:
    """把模型参数压缩成一个数值，用于比较不同 rank 的参数是否一致。"""
    total = torch.zeros(1, device=device, dtype=torch.float64)
    for parameter in model.parameters():
        total += parameter.detach().double().sum()
    return total.item()


def main() -> None:
    # torchrun 会自动设置这些环境变量。
    local_rank = int(os.environ["LOCAL_RANK"])
    rank = int(os.environ["RANK"])
    world_size = int(os.environ["WORLD_SIZE"])

    if not torch.cuda.is_available():
        raise RuntimeError("当前 PyTorch 没有检测到 CUDA GPU。")
    if torch.cuda.device_count() < world_size:
        raise RuntimeError(
            f"可见 GPU 数量不足：检测到 {torch.cuda.device_count()} 张，但 torchrun 启动了 {world_size} 个进程。"
        )

    torch.cuda.set_device(local_rank)
    device = torch.device(f"cuda:{local_rank}")
    dist.init_process_group(backend="nccl")
    torch.manual_seed(20260714 + rank)

    model = build_model().to(device)
    ddp_model = DDP(model, device_ids=[local_rank], output_device=local_rank)
    optimizer = torch.optim.AdamW(ddp_model.parameters(), lr=3e-4)
    loss_fn = nn.MSELoss()

    if rank == 0:
        print(f"DDP 已启动：world_size={world_size}，NCCL 后端，主机={socket.gethostname()}")
    print(
        f"[rank {rank}] 使用 cuda:{local_rank} | "
        f"{torch.cuda.get_device_name(local_rank)}"
    )

    torch.cuda.synchronize(device)
    started_at = time.perf_counter()
    final_mean_loss = 0.0

    for step in range(1, STEPS + 1):
        # 每个 rank 故意使用不同的合成数据，DDP 会在 backward 时同步它们的梯度。
        features = torch.randn(BATCH_SIZE_PER_GPU, INPUT_DIM, device=device)
        labels = torch.randn(BATCH_SIZE_PER_GPU, OUTPUT_DIM, device=device)

        optimizer.zero_grad(set_to_none=True)
        predictions = ddp_model(features)
        loss = loss_fn(predictions, labels)
        loss.backward()
        optimizer.step()

        # 汇总各卡 loss，rank 0 输出的是双卡平均值，而不是单卡偶然值。
        mean_loss = loss.detach().clone()
        dist.all_reduce(mean_loss, op=dist.ReduceOp.AVG)
        final_mean_loss = mean_loss.item()

        if rank == 0 and step in {1, STEPS}:
            print(f"step={step:02d}/{STEPS} | 双卡平均 loss={final_mean_loss:.6f}")

    torch.cuda.synchronize(device)
    elapsed_seconds = time.perf_counter() - started_at

    # DDP 完成后，每个 rank 的参数应相同。收集指纹即可快速验证。
    local_fingerprint = torch.tensor(
        [parameter_fingerprint(ddp_model.module, device)],
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
            "world_size": world_size,
            "backend": "nccl",
            "gpu_count_visible": torch.cuda.device_count(),
            "gpus": [torch.cuda.get_device_name(index) for index in range(world_size)],
            "steps": STEPS,
            "batch_size_per_gpu": BATCH_SIZE_PER_GPU,
            "global_batch_size": BATCH_SIZE_PER_GPU * world_size,
            "final_mean_loss": final_mean_loss,
            "elapsed_seconds": elapsed_seconds,
            "parameter_fingerprints": fingerprints,
            "parameter_fingerprints_match": fingerprints_match,
        }
        report_path = OUTPUT_DIR / "ddp_smoke_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"双卡 DDP 验证完成，结果已保存：{report_path}")
        print(f"两张卡参数一致：{fingerprints_match}")

    dist.barrier()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
