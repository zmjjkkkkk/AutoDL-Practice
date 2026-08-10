# Day 29 可复现部署与多模态回归验证

## 目标

Day29 将 Day28 已验证的多模态协作链路整理成可重复运行的交付前流程。它不训练模型、不扩大命令能力，也不执行 Minecraft 动作；它解决的是新克隆实例如何安全检查、启动、验证和停止服务。

```text
check_runtime.py
-> start_stack.sh
-> run_regression.py
-> stop_stack.sh
```

## 文件说明

- `check_runtime.py`：只读检查 GPU、torch/CUDA、vLLM、NVRTC、模型、LoRA 和源码依赖。默认不修改环境。
- `start_stack.sh`：按依赖顺序启动 GPU 0 的文本服务、GPU 1 的视觉服务和 Day28 协作网关；只绑定 loopback，并记录自身启动的 PID。
- `stop_stack.sh`：按反向顺序停止 `start_stack.sh` 记录且进程特征匹配的服务。
- `run_regression.py`：调用 Day28 接口检查健康状态、文本命令、安全澄清、无效请求，以及可选的视觉-only/组合请求。
- `regression_contract.py` 与 `test_regression_contract.py`：不依赖模型的离线响应判定测试。
- `RUNBOOK.md`：克隆环境、已知 PyTorch 修复、启动、隧道、回归和停止说明。

## 安全边界

- 所有远端服务均监听 `127.0.0.1`；本地访问必须经过 SSH 隧道。
- 启动脚本在发现目标端口已有响应或 PID 记录仍在运行时会退出，不会接管未知进程。
- 停止脚本仅对 PID 文件中、且 `/proc/<pid>/cmdline` 与预期服务特征相符的进程发送 `TERM`。
- 回归报告不保存图片、图片路径、base64、模型原始输出或任何可执行结果之外的敏感内容。
- Day29 只验证 Day28 返回的“已验证但未执行”命令，不连接 Mindcraft 适配器。

## 本地代码检查

```powershell
python "学习计划\Day 29 可复现部署与多模态回归验证\test_regression_contract.py"
```

## 远端最短流程

```bash
cd /root/autodl-tmp/day29-deployment

python check_runtime.py --strict --report reports/day29_runtime_report.json

chmod +x start_stack.sh stop_stack.sh
./start_stack.sh

# 选一张用户主动选择、不会上传仓库的图片；只写 expected entity，不写路径到报告。
python run_regression.py \
  --image /root/autodl-tmp/vision_lora/sheep/new/example.png \
  --expected-entity sheep \
  --report reports/day29_regression_report.json

./stop_stack.sh
```

实际 SSH 端口和图片文件名以本次实例为准，详见 `RUNBOOK.md`。

## 首轮结果（2026-08-10）

在新克隆的双 RTX 5090 实例上，首次 `check_runtime.py --strict` 成功发现 vLLM 导入失败：其余模型、LoRA、网关源码与 NVRTC 依赖均存在，但 `torch` 存在旧 Inductor 模板残留。按照 `RUNBOOK.md` 仅清理 PyTorch 本体并用已保存 wheel 重装后，预检达到 `13/13` 通过。

随后 `start_stack.sh` 成功按依赖顺序启动 vLLM `8000`、Day21 `8767`、Day27 `8769` 和 Day28 `8770`。使用一张用户主动选择的私有羊图运行 `run_regression.py`，6 项检查全部通过：健康状态、跟随命令验证、越界转交澄清、无效请求拒绝、视觉-only、文本加视觉，结果为 `6/6 = 100.0%`。报告不记录图片路径、内容、base64 或原始模型输出。

最后 `stop_stack.sh` 依次停止 multimodal、vision、policy、vLLM 四个由本次启动脚本记录的进程；等待 5 秒后两张 GPU 均显示 `0 MiB`，且 `nvidia-smi` 无残留进程。该结果证明脚本在本次实例上完成了“预检 -> 启动 -> 回归 -> 停止”的闭环，但不代表对其他 CUDA、PyTorch、vLLM 版本组合的兼容性保证。
