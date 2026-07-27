# Day 27 视觉 LoRA 服务化与外部泛化评测

## 目标

Day26 在同一轮采集的留出集上将羊/猪严格分类从 `65.0%` 提升至 `95.0%`。Day27 使用 12 张新采集截图进行外部泛化评测，并仅在结果可接受时，将已训练的视觉 LoRA 封装为独立、只读的实体分类 HTTP 服务。

外部集目录为私有的 `vision_lora/{sheep,pig}/new`，羊和猪各 6 张。它们绝不参与 Day26 训练，也不应在 Day27 根据结果继续训练。

## 安全边界

- 服务只接受 base64 图片和 MIME 类型，不接受本地路径、URL、自由提示词或游戏命令。
- 分类范围固定为 `sheep`、`pig`；输出不在该集合则拒绝。
- 服务返回实体标签或无结果，不生成 Mindcraft 命令，也不调用 Day21 命令网关。
- 默认仅监听远程 `127.0.0.1:8769`；本地访问必须经 SSH 隧道。
- 原始截图、LoRA 权重、外部报告均被 Git 忽略。

## 远程流程

构建并校验外部清单：

```bash
cd /root/autodl-tmp/day27-vision-service

python build_external_manifest.py \
  --data-root /root/autodl-tmp/vision_lora \
  --output output

python validate_external_manifest.py \
  --manifest output/external_test.jsonl
```

评测基础模型和 Day26 LoRA：

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export LD_LIBRARY_PATH=/root/miniconda3/lib/python3.12/site-packages/nvidia/cu13/lib:${LD_LIBRARY_PATH}

CUDA_VISIBLE_DEVICES=0 python evaluate_entity_classifier.py \
  --model-dir /root/autodl-tmp/models/Qwen2.5-VL-7B-Instruct \
  --manifest output/external_test.jsonl \
  --report reports/external_base.json

CUDA_VISIBLE_DEVICES=0 python evaluate_entity_classifier.py \
  --model-dir /root/autodl-tmp/models/Qwen2.5-VL-7B-Instruct \
  --adapter-dir /root/autodl-tmp/day26-vision-lora/artifacts/qwen25vl_minecraft_entity_lora/adapter \
  --manifest output/external_test.jsonl \
  --report reports/external_lora.json

python compare_entity_reports.py \
  --baseline reports/external_base.json \
  --candidate reports/external_lora.json \
  --output reports/external_comparison.json
```

## 首轮外部评测与服务验证（2026-07-27）

本轮外部集由用户在 Day26 训练/测试集之外新采集的 12 张截图组成，`sheep` 与 `pig` 各 6 张。构建脚本以固定种子 `20260727` 打乱顺序，但不会重命名、移动或写回任何原始图片；这批图片没有参与 Day26 或 Day27 的训练。

在同一份外部清单、同一提示词、相同 `768` 最长边缩放和确定性生成设置下，基础 `Qwen2.5-VL-7B-Instruct` 的严格实体准确率为 `10/12 = 83.3%`；加载 Day26 视觉 LoRA 后为 `12/12 = 100.0%`，提升 `16.7` 个百分点。该结果说明 LoRA 在这一次小样本外部评测中优于基础模型，但 12 张图片不足以代表所有 Minecraft 世界、距离、光照或材质分布。

随后启动 `vision_entity_gateway.py`，它只监听远端 `127.0.0.1:8769`。本地通过 SSH 隧道 `127.0.0.1:18769` 完成两次独立请求：一张新羊图返回 `sheep`，一张新猪图返回 `pig`。服务仅接受图片 base64 与 MIME 类型，只返回封闭集合 `sheep`/`pig` 或失败结果；不接收路径、URL、自由提示词或游戏指令，也不连接 Mindcraft 命令链路。

启动独立服务仅在外部评测结束后进行：

```bash
CUDA_VISIBLE_DEVICES=0 python vision_entity_gateway.py \
  --model-dir /root/autodl-tmp/models/Qwen2.5-VL-7B-Instruct \
  --adapter-dir /root/autodl-tmp/day26-vision-lora/artifacts/qwen25vl_minecraft_entity_lora/adapter \
  --host 127.0.0.1 \
  --port 8769
```

本地 SSH 隧道：

```powershell
ssh -N -L 127.0.0.1:18769:127.0.0.1:8769 -p 26689 root@connect.bjb2.seetacloud.com
```

## 服务请求示例

`query_entity_gateway.py` 只读取本地图片，在内存中编码并发送；服务端不会获得本地文件路径。

```powershell
python "学习计划\Day 27 视觉LoRA服务化与外部泛化评测\query_entity_gateway.py" `
  --image "vision_lora\sheep\new\example.png" `
  --gateway-url http://127.0.0.1:18769
```

外部集的结果必须与 Day26 的留出集区分记录。即使外部准确率较低，也是一条有价值的泛化结论，不能回填进训练数据后重测。
