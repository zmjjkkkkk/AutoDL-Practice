# VS Code 通过 SSH 连接 AutoDL A100/H200 实例指南

> 目标：从本地 VS Code 连接到 AutoDL GPU 云主机，在 A100/H200 上完成大模型训练、微调、推理实验的基础环境搭建与自检。

## 1. 整体链路

```text
本地电脑 VS Code
    -> Remote - SSH 插件
    -> SSH 登录 AutoDL 实例
    -> A100/H200 GPU 服务器
    -> Conda/Python/CUDA/PyTorch/vLLM/Transformers
```

你需要准备：

- AutoDL 已开机的实例，显卡选择 A100 或 H200。
- AutoDL 控制台提供的 SSH 登录信息：公网 IP、端口、用户名、密码或密钥。
- 本地安装 VS Code。
- 本地安装 OpenSSH 客户端。
- VS Code 安装 `Remote - SSH` 插件。

## 2. 在 AutoDL 创建 GPU 实例

1. 登录 AutoDL 控制台。
2. 选择 GPU 机型：
   - A100：适合大多数微调、推理、LoRA/QLoRA、多卡训练入门。
   - H200：显存更大、带宽更高，适合更大模型、更长上下文、更高吞吐推理。
3. 选择镜像：
   - 初学推荐选择带 `PyTorch`、`CUDA`、`Conda`、`Jupyter` 的官方镜像。
   - 不建议一开始选过于精简的系统镜像，否则 CUDA/PyTorch 环境会花很多时间排错。
4. 开机后，在控制台找到 SSH 登录信息，通常形式类似：

```bash
ssh -p <端口号> root@<公网IP>
```

如果 AutoDL 页面提供的是密码登录，先用密码即可；后续再配置 SSH Key。

## 3. 本地检查 SSH 是否可用

Windows PowerShell 中执行：

```powershell
ssh -V
```

如果能输出 OpenSSH 版本，说明本地 SSH 客户端可用。

如果提示找不到 `ssh`，可在 Windows 设置中启用：

```text
设置 -> 应用 -> 可选功能 -> OpenSSH Client
```

## 4. 先用命令行测试连接

在 PowerShell 中执行 AutoDL 给出的命令：

```powershell
ssh -p <端口号> root@<公网IP>
```

首次连接会出现主机指纹确认：

```text
Are you sure you want to continue connecting?
```

输入：

```text
yes
```

然后输入 AutoDL 控制台提供的密码。能进入 Linux shell 就说明 SSH 链路正常。

连接成功后可执行：

```bash
hostname
nvidia-smi
pwd
```

看到 A100/H200 显卡信息后，说明实例和 GPU 都正常。

## 5. 配置 SSH Config，方便 VS Code 使用

在本地 Windows 打开或创建文件：

```text
C:\Users\<你的用户名>\.ssh\config
```

加入如下配置：

```sshconfig
Host autodl-a100
    HostName <公网IP>
    User root
    Port <端口号>
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

如果是 H200，可以写成：

```sshconfig
Host autodl-h200
    HostName <公网IP>
    User root
    Port <端口号>
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

保存后，在 PowerShell 中测试：

```powershell
ssh autodl-a100
```

或：

```powershell
ssh autodl-h200
```

如果能正常登录，说明 VS Code Remote SSH 也基本可以使用。

## 6. 使用 VS Code Remote SSH 连接

1. 打开 VS Code。
2. 安装插件：`Remote - SSH`。
3. 按 `Ctrl + Shift + P`。
4. 输入并选择：

```text
Remote-SSH: Connect to Host...
```

5. 选择 `autodl-a100` 或 `autodl-h200`。
6. 第一次连接时，VS Code 会在远端安装 `VS Code Server`。
7. 连接成功后，左下角会显示类似：

```text
SSH: autodl-a100
```

8. 在 VS Code 中选择：

```text
File -> Open Folder
```

推荐打开 AutoDL 数据盘目录，例如：

```bash
/root/autodl-tmp
```

不要把大型模型、数据集、训练输出长期放在系统盘目录，避免磁盘爆满。

## 7. 建议的远端目录结构

在 AutoDL 服务器上执行：

```bash
mkdir -p /root/autodl-tmp/projects
mkdir -p /root/autodl-tmp/datasets
mkdir -p /root/autodl-tmp/models
mkdir -p /root/autodl-tmp/outputs
```

推荐约定：

```text
/root/autodl-tmp/projects   放代码
/root/autodl-tmp/datasets   放数据集
/root/autodl-tmp/models     放模型权重
/root/autodl-tmp/outputs    放训练输出、日志、checkpoint
```

## 8. GPU 和 CUDA 环境自检

进入远端终端后，依次执行：

```bash
nvidia-smi
nvcc --version
python --version
conda --version
```

检查 PyTorch 是否能识别 GPU：

```bash
python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
print("cuda version:", torch.version.cuda)
print("gpu count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("gpu name:", torch.cuda.get_device_name(0))
PY
```

关键判断：

- `torch.cuda.is_available()` 应该是 `True`。
- A100 通常显示 `NVIDIA A100`。
- H200 通常显示 `NVIDIA H200`。
- 如果 GPU 可见但 PyTorch 不可用，多半是 PyTorch/CUDA 版本不匹配。

## 9. Conda 环境建议

如果镜像里已有可用环境，优先使用镜像自带环境。否则可以创建新环境：

```bash
conda create -n llm python=3.10 -y
conda activate llm
python -m pip install -U pip
```

安装常用包：

```bash
pip install -U transformers accelerate datasets peft trl sentencepiece protobuf
pip install -U einops scipy scikit-learn pandas matplotlib tqdm
```

安装 PyTorch 时要特别注意 CUDA 版本。常见做法是先查看驱动：

```bash
nvidia-smi
```

然后根据 PyTorch 官网给出的命令安装对应 CUDA 版本的 wheel。不要盲目混装多个 CUDA 版本。

## 10. A100 与 H200 的训练/推理注意点

### A100

- 架构：Ampere。
- 适合 BF16/FP16 训练和推理。
- 常见显存：40GB 或 80GB。
- 对 LoRA、QLoRA、7B/14B/32B 模型实验比较友好。

### H200

- 架构：Hopper。
- 显存和带宽通常比 H100/A100 更强。
- 更适合长上下文推理、大 batch 推理、更大模型训练。
- 软件栈建议使用较新的 PyTorch、CUDA、FlashAttention、vLLM。
- 如果遇到算子或编译错误，优先检查依赖是否支持 Hopper 架构。

## 11. 大模型推理最小示例

安装依赖：

```bash
pip install -U transformers accelerate sentencepiece
```

创建 `infer.py`：

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model_name = "/root/autodl-tmp/models/your-model"

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)

messages = [{"role": "user", "content": "请用三句话解释什么是大模型微调。"}]

if hasattr(tokenizer, "apply_chat_template"):
    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to(model.device)
else:
    inputs = tokenizer("请用三句话解释什么是大模型微调。", return_tensors="pt").to(model.device)

outputs = model.generate(
    inputs,
    max_new_tokens=256,
    do_sample=True,
    temperature=0.7,
)

print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

运行：

```bash
python infer.py
```

## 12. vLLM 推理服务示例

vLLM 适合高吞吐推理服务。安装前建议确认当前 CUDA/PyTorch 环境兼容。

```bash
pip install -U vllm
```

启动 OpenAI API 兼容服务：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model /root/autodl-tmp/models/your-model \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16
```

在远端测试：

```bash
curl http://127.0.0.1:8000/v1/models
```

如果想从本地访问远端服务，可以用 SSH 端口转发：

```powershell
ssh -L 8000:127.0.0.1:8000 autodl-a100
```

然后本地访问：

```text
http://127.0.0.1:8000/v1/models
```

## 13. LoRA 微调常用组件

常见技术栈：

- `transformers`：模型与 tokenizer 加载。
- `datasets`：数据集处理。
- `accelerate`：单机多卡/混合精度启动。
- `peft`：LoRA、QLoRA 等参数高效微调。
- `trl`：SFT、DPO 等训练流程。
- `bitsandbytes`：4-bit/8-bit 量化训练或加载。
- `deepspeed`：大模型多卡训练优化。

启动训练时常见命令形式：

```bash
accelerate launch train.py \
  --model_name_or_path /root/autodl-tmp/models/base-model \
  --dataset_path /root/autodl-tmp/datasets/my-data \
  --output_dir /root/autodl-tmp/outputs/exp001 \
  --bf16 true
```

多卡训练前检查：

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.device_count())"
```

## 14. VS Code 远端开发建议

推荐安装到远端的 VS Code 插件：

- Python
- Pylance
- Jupyter
- GitLens
- YAML
- Markdown All in One

常用操作：

- 远端终端：`Terminal -> New Terminal`
- 选择解释器：`Ctrl + Shift + P -> Python: Select Interpreter`
- 打开项目：`File -> Open Folder -> /root/autodl-tmp/projects/...`
- 查看端口：`Ports` 面板中可以转发 Jupyter、vLLM、TensorBoard 等服务端口。

## 15. 常见问题排查

### 连接不上 SSH

检查：

```powershell
ssh -vvv -p <端口号> root@<公网IP>
```

常见原因：

- AutoDL 实例没有开机。
- 公网 IP 或端口填错。
- 密码复制错误。
- 本地网络阻断了 SSH。
- VS Code SSH config 中缩进、HostName、Port 写错。

### VS Code 卡在 Installing VS Code Server

可尝试：

```bash
rm -rf ~/.vscode-server
```

然后重新连接。

如果网络较慢，第一次安装会等待较久。

### `nvidia-smi` 正常，但 PyTorch 找不到 CUDA

通常是 PyTorch 安装版本不对。检查：

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

解决思路：

- 使用镜像自带 PyTorch 环境。
- 重新创建 Conda 环境。
- 按 PyTorch 官方命令安装匹配 CUDA 的版本。

### 显存不足

可尝试：

- 减小 batch size。
- 减小 max sequence length。
- 开启 gradient checkpointing。
- 使用 BF16/FP16。
- 使用 LoRA/QLoRA。
- 推理时使用量化或 vLLM。
- 多卡时检查是否正确设置 tensor parallel 或 data parallel。

### 磁盘不足

检查：

```bash
df -h
du -h --max-depth=1 /root/autodl-tmp | sort -h
```

清理：

- 删除无用 checkpoint。
- 删除重复模型权重。
- 清理 pip/conda 缓存。
- 把数据和输出放到数据盘，不要堆在系统盘。

## 16. 建议学习路线

1. 熟悉 AutoDL 控制台：开机、关机、换镜像、查看 SSH 信息、管理数据盘。
2. 熟悉 SSH：命令行登录、SSH config、端口转发。
3. 熟悉 VS Code Remote SSH：远端打开目录、远端终端、远端 Python 解释器。
4. 熟悉 GPU 环境：`nvidia-smi`、CUDA、PyTorch、显存占用。
5. 跑通一个 Transformers 推理脚本。
6. 跑通一个 vLLM OpenAI API 服务。
7. 跑通一个 LoRA/QLoRA 微调任务。
8. 学习多卡训练：Accelerate、DeepSpeed、FSDP。
9. 学习性能优化：BF16、FlashAttention、KV Cache、Tensor Parallel、量化。

## 17. 最小验收清单

完成以下项目，就说明 VS Code -> SSH -> A100/H200 链路已经打通：

- 本地 PowerShell 可以 `ssh autodl-a100` 或 `ssh autodl-h200`。
- VS Code 可以通过 Remote SSH 连接实例。
- VS Code 可以打开 `/root/autodl-tmp/projects`。
- 远端终端执行 `nvidia-smi` 能看到 A100/H200。
- Python 中 `torch.cuda.is_available()` 返回 `True`。
- 能运行一个最小模型推理脚本。
- 能通过端口转发访问远端服务，例如 vLLM 或 TensorBoard。

