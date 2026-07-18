"""Print the remote environment information needed before serving the Mindcraft LoRA with vLLM."""

import argparse
import json
import platform
import subprocess
import sys
import urllib.error
import urllib.request


def installed_version(module_name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(module_name)
    except Exception:
        return None


def get_json(url: str, timeout: int = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Check the vLLM serving environment.")
    parser.add_argument("--vllm-url", help="Optional vLLM base URL, for example http://127.0.0.1:8000/v1")
    args = parser.parse_args()

    report = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "vllm_version": installed_version("vllm"),
        "torch_version": installed_version("torch"),
    }

    try:
        import torch

        report["cuda_available"] = torch.cuda.is_available()
        report["gpu_count"] = torch.cuda.device_count()
        report["gpus"] = [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())]
    except Exception as exc:
        report["torch_error"] = str(exc)

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        report["nvidia_smi"] = result.stdout.strip() or result.stderr.strip()
    except Exception as exc:
        report["nvidia_smi_error"] = str(exc)

    if args.vllm_url:
        base_url = args.vllm_url.rstrip("/")
        try:
            report["vllm_models"] = get_json(f"{base_url}/models")
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            report["vllm_models_error"] = str(exc)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
