"""Read-only preflight checks for the Day 21, 27, 28 deployment stack."""

import argparse
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path


def check(name: str, ok: bool, detail: str) -> dict:
    return {"name": name, "ok": ok, "detail": detail}


def path_check(name: str, path: Path) -> dict:
    return check(name, path.exists(), str(path))


def command_check(name: str, command: list[str]) -> dict:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
    detail = (completed.stdout or completed.stderr).strip().splitlines()
    return check(name, completed.returncode == 0, detail[-1] if detail else f"exit={completed.returncode}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/root/autodl-tmp"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--strict", action="store_true", help="exit non-zero if any required check fails")
    args = parser.parse_args()
    root = args.root
    site_packages = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    checks = [
        check("python", True, sys.version.split()[0]),
        command_check("torch_cuda", [sys.executable, "-c", "import torch; print(f'torch={torch.__version__}; cuda={torch.cuda.is_available()}; gpus={torch.cuda.device_count()}'); raise SystemExit(0 if torch.cuda.is_available() else 1)" ]),
        command_check("vllm_import", [sys.executable, "-c", "import vllm; print(vllm.__version__)" ]),
        path_check("nvrtc_builtins_13_0", site_packages / "nvidia" / "cu13" / "lib" / "libnvrtc-builtins.so.13.0"),
        path_check("qwen3_cache", root / "day15-sft" / "hf-cache"),
        path_check("qwen3_v2_adapter", root / "day19-sft" / "artifacts" / "qwen3_4b_mindcraft_lora_v2" / "adapter" / "adapter_model.safetensors"),
        path_check("qwen25vl_model", root / "models" / "Qwen2.5-VL-7B-Instruct" / "config.json"),
        path_check("qwen25vl_adapter", root / "day26-vision-lora" / "artifacts" / "qwen25vl_minecraft_entity_lora" / "adapter" / "adapter_model.safetensors"),
        path_check("day21_gateway", root / "day21-policy" / "day21_policy_gateway.py"),
        path_check("day21_guard", root / "day21-policy" / "experimental_command_guard.py"),
        path_check("day27_gateway", root / "day27-vision-service" / "vision_entity_gateway.py"),
        path_check("day28_gateway", root / "day28-multimodal-gateway" / "multimodal_gateway.py"),
    ]
    try:
        gpu_info = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        checks.append(check("nvidia_smi", gpu_info.returncode == 0, (gpu_info.stdout or gpu_info.stderr).strip()))
    except (OSError, subprocess.TimeoutExpired) as exc:
        checks.append(check("nvidia_smi", False, str(exc)))

    payload = {
        "schema_version": "1.0",
        "root": str(root),
        "python": sys.version.split()[0],
        "vllm_metadata_version": _version("vllm"),
        "checks": checks,
        "passed": sum(item["ok"] for item in checks),
        "total": len(checks),
    }
    payload["ok"] = payload["passed"] == payload["total"]
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.strict and not payload["ok"]:
        raise SystemExit(1)


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


if __name__ == "__main__":
    main()
