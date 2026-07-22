"""Report whether this machine is ready to host the Day 22 vision service."""

import importlib.metadata
import json
import platform

import torch


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main():
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "vllm_version": package_version("vllm"),
        "cuda_available": torch.cuda.is_available(),
        "gpu_count": torch.cuda.device_count(),
        "gpus": [
            torch.cuda.get_device_name(index)
            for index in range(torch.cuda.device_count())
        ],
        "recommended_model": "Qwen/Qwen2.5-VL-7B-Instruct",
        "recommended_gpu": "GPU 1, separate from the existing text command service",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
