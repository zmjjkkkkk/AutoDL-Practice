# Day 18：vLLM 部署与高并发推理

## 今天的目标

Day 17 的 `command_gateway.py` 直接使用 Transformers 和 PEFT 加载 Qwen3-4B 与 LoRA。它已经验证了安全链路，但每个服务进程自己管理模型推理，不适合作为后续并发服务的实现。

Day 18 使用 vLLM 托管基座模型和 Day 15 的 LoRA 适配器，并保留独立的命令白名单网关：

```text
Minecraft 玩家聊天
-> Mindcraft 适配器
-> SSH 隧道
-> vLLM 安全网关（8765，白名单）
-> vLLM OpenAI 兼容服务（8000，Qwen3-4B + LoRA）
```

这样，vLLM 负责高效生成；`command_guard.py` 仍负责决定模型输出能否变成游戏动作。两层职责不能混在一起。

## 为什么现在学习 vLLM

- **Transformers + PEFT**：适合训练、调试和单次推理，Day 16-17 已经使用。
- **vLLM**：专门优化模型服务，模型加载一次后可以处理多个请求，并提供 OpenAI 兼容 HTTP 接口。
- **LoRA 服务**：vLLM 可在启动时通过 `--enable-lora` 和 `--lora-modules` 挂载适配器；请求的 `model` 字段使用适配器名称。

Qwen3 默认可能启用 thinking。我们的任务要求输出一条精确的游戏命令，因此服务端固定 `enable_thinking=false`，避免推理文本干扰命令白名单。

## 本目录文件

- `check_vllm_environment.py`：远程环境预检，查看 GPU、PyTorch、vLLM 与本地服务模型列表。
- `vllm_command_gateway.py`：保持 Day 17 的 `GET /health`、`POST /command` 接口，但把生成请求转发到 vLLM，再调用本目录的命令白名单。
- `command_guard.py`：当前 SFT 数据集对应的命令白名单和参数校验。Day 18 已自包含该文件与固定系统提示词，迁移本目录时不再依赖 Day 16/17 的远程文件。

## 远程预检

先把本目录上传到已有远程训练目录，例如：

```bash
cd /root/autodl-tmp/day15-sft
python /root/autodl-tmp/day18-vllm/check_vllm_environment.py
```

如果未安装 vLLM，先在远程实例中安装。安装前不要停止或修改现有的 Day 17 网关；vLLM 的 PyTorch/CUDA 兼容性要以远程实际环境为准。

```bash
pip install -U vllm
python /root/autodl-tmp/day18-vllm/check_vllm_environment.py
```

## 启动 vLLM + LoRA

Day 15 的 LoRA rank 是 `16`，因此 `--max-lora-rank` 设为 `16`。当前实验固定使用一张 GPU，控制资源占用并方便排查服务问题。

本次在 RTX 5090 环境启动 vLLM `0.25.1` 时，FlashInfer sampler 初始化出现兼容性报错；加入 `VLLM_USE_FLASHINFER_SAMPLER=0` 后使用回退采样器，服务可正常启动。该参数只影响采样实现，不改变 LoRA 权重和命令白名单。

```bash
VLLM_USE_FLASHINFER_SAMPLER=0 \
CUDA_VISIBLE_DEVICES=0 \
HF_HOME=/root/autodl-tmp/day15-sft/hf-cache \
HF_HUB_OFFLINE=1 \
vllm serve Qwen/Qwen3-4B \
  --host 127.0.0.1 \
  --port 8000 \
  --enable-lora \
  --lora-modules mindcraft-lora=/root/autodl-tmp/day15-sft/artifacts/qwen3_4b_mindcraft_lora/checkpoint-45 \
  --max-lora-rank 16 \
  --max-model-len 2048 \
  --gpu-memory-utilization 0.80 \
  --default-chat-template-kwargs '{"enable_thinking": false}'
```

说明：`vllm serve` 提供 OpenAI 兼容的 `/v1/chat/completions` 接口。上述 `mindcraft-lora` 是服务别名，不是文件夹名；安全网关会在请求中使用它。

## 启动安全网关

在第二个远程终端中运行：

```bash
cd /root/autodl-tmp/day18-vllm
python vllm_command_gateway.py \
  --vllm-url http://127.0.0.1:8000/v1 \
  --model mindcraft-lora \
  --port 8765
```

网关仍只监听 `127.0.0.1:8765`。Windows 端继续使用 Day 17 的 SSH 隧道与 Mindcraft 适配器，不需要修改 `mindcraft_lora.js`：

```powershell
ssh -N -L 18765:127.0.0.1:8765 -p <SSH端口> root@connect.bjb2.seetacloud.com
```

## 验证顺序

1. 运行 `check_vllm_environment.py --vllm-url http://127.0.0.1:8000/v1`，确认 `/v1/models` 中有 `mindcraft-lora`。
2. 使用 `curl http://127.0.0.1:8765/health` 检查安全网关和 vLLM 后端。
3. 向 `/command` 发送 `please follow me`，预期白名单通过 `!followPlayer("robot", 3)`。
4. 再连接 Minecraft，复测 Day 17 的命令；仍以“只执行一次、未知命令被拒绝”为验收标准。

## 本次完成记录

- 在双 RTX 5090 远程实例完成 vLLM `0.25.1` 安装与环境预检。
- `/v1/models` 同时返回基座模型 `Qwen/Qwen3-4B` 与 LoRA 服务别名 `mindcraft-lora`，确认 `checkpoint-45` 已被服务加载。
- `POST /command` 对 `please follow me` 返回 `!followPlayer("robot", 3)`，并被白名单标记为 `verified_command`。
- 经 SSH 隧道连接本地 Mindcraft 后，真实游戏复测通过；采集原木时观察到路径执行层可能为接近目标额外破坏相连方块，后续将作为“严格数量采集”优化项处理。

## 注意事项

- vLLM 是推理服务，不替代 LoRA 训练、数据校验和命令白名单。
- 不启用运行时动态加载 LoRA；当前只在启动时加载本地已验证的 `checkpoint-45`。
- vLLM 与 Day 17 原网关不要同时绑定 `8765`；测试 vLLM 方案前先停止旧网关，或给其中一个服务换端口。
- 不要将 vLLM 直接绑定到 `0.0.0.0`，也不要跳过 SSH 隧道。
