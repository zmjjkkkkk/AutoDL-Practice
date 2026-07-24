# Day 23: 视觉观察 API 与基准评测

## 本日目标

Day 22 已证明一张由用户手动选取的 Minecraft 截图可以经由 Qwen2.5-VL-7B 和严格 JSON 守卫，得到安全的只读观察。Day 23 将这个单次命令行流程封装为独立 HTTP API，方便本地客户端通过 SSH 隧道请求观察结果。

这不是游戏动作 API。它不调用 Day 21 的命令网关，不接收自然语言提示词，也不会控制 Mindcraft bot。

## 服务边界

```text
local screenshot selected by the player
-> SSH tunnel
-> Day 23 POST /observe
-> in-memory image validation and downscale
-> GPU 1 vLLM vision service
-> Day 22 observation guard
-> observation text and validated JSON

separate player command
-> Day 21 policy gateway
-> GPU 0 text LoRA service
-> exact command guard
-> Mindcraft action
```

视觉和动作链路只共享同一台远程机器，不共享请求、提示词或执行权限。

## 文件

- `vision_api_contract.json`：HTTP 请求、响应和安全边界。
- `vision_observation_gateway.py`：仅绑定 `127.0.0.1:8768` 的观察 API。
- `test_vision_observation_gateway.py`：离线验证图片解码、字段限制和内存缩放；不调用模型。
- `vision_benchmark_manifest.example.json`：私有截图人工标注清单的模板。
- `run_vision_benchmark.py`：经 Day 23 API 批量评测私有截图，并计算必需标签覆盖率。
- `test_vision_benchmark.py`：离线验证评测指标计算。

Day 23 通过 `PYTHONPATH` 复用 Day 22 的 `vision_observation_guard.py`，确保 CLI 测试和 HTTP API 使用同一份观察契约。

Day 23 同时复用 Day 22 的 `vision_output_schema.py`。当前 vLLM 部署使用兼容性更稳定的 `json_object` 模式；字段、列表长度和去重规则由紧凑提示词与 Day 22 守卫共同执行。守卫仍是唯一的最终接受或拒绝点。

## 小型视觉基准

视觉守卫的 `ok: true` 只代表结构和安全边界合格，不能证明每个视觉标签都事实正确。基准评测要求人工先标注一组私有图片的“必须出现”标签，再计算模型命中的比例。指标称为**必需标签覆盖率**：已命中的人工标签数除以人工标签总数；它不把模型额外描述的细节直接计为错误。

先复制模板为私有清单，并替换图片路径和人工标注。为了与模型输出上限一致，单张图最多标注 6 个必需方块和 4 个必需实体：

```powershell
Copy-Item vision_benchmark_manifest.example.json vision_benchmark_manifest.json
```

`vision_benchmark_manifest.json`、截图和报告均不提交 Git。通过本地 SSH 隧道评测：

```powershell
python run_vision_benchmark.py \
  --manifest vision_benchmark_manifest.json \
  --gateway-url http://127.0.0.1:18768
```

输出报告默认位于 `reports/vision_benchmark_report.json`，其中不包含 base64 图片数据或模型原始文本；为便于私有复盘，它只保留观察守卫已接受的结构化 `observation`。离线检查：

```powershell
python test_vision_benchmark.py
```

## 请求格式

`POST /observe` 只接受以下 JSON：

```json
{
  "image_base64": "base64 encoded PNG/JPEG/WebP bytes",
  "mime_type": "image/png"
}
```

图片只能是 PNG、JPEG 或 WebP；不接受 URL、远端文件路径、额外字段或玩家提示词。原始图片最大 8 MiB、图片像素最大 1600 万，服务在内存中压缩为最长边默认 768 像素的 JPEG，之后立即丢弃上传字节。

成功响应中不会回传模型原始文本，只返回守卫已接受的 `observation`；异常视觉输出会返回固定安全提示。该设计避免未经验证的模型内容继续流向客户端。

若上游 vLLM 拒绝请求，客户端只会收到通用 `502`；详细 HTTP 错误仅记录在远端网关终端，用于排查模型服务兼容性，不包含上传图片数据。

## 远端启动

先确保 Day 22 视觉 vLLM 服务运行于 `127.0.0.1:8001`。再新开终端：

```bash
cd /root/autodl-tmp/day23-vision-api
PYTHONPATH=/root/autodl-tmp/day22-vision \
python vision_observation_gateway.py \
  --vllm-url http://127.0.0.1:8001/v1 \
  --model minecraft-vision \
  --port 8768
```

检查：

```bash
curl http://127.0.0.1:8768/health
```

本地访问必须经过 SSH 隧道，例如将远端 `8768` 映射到本地 `18768`。截图、base64 请求体、报告和服务日志不应提交 Git。

若某张图被观察守卫拒绝，需要定位契约不兼容原因时，可暂时添加 `--debug-rejected-output` 重启网关。该开关只把最长 600 个字符的、经 Python 转义的模型输出打印到**远端当前终端**；它不会写入 HTTP 响应、报告或仓库。完成排查后，应不带该参数重启网关。

## 离线测试

在仓库根目录运行：

```powershell
python "学习计划\Day 23 视觉观察API与基准评测\test_vision_observation_gateway.py"
```

预期输出：

```text
Day 23 vision observation gateway tests passed: 4/4
```

## 首轮真实基准（2026-07-23）

已使用一张未上传仓库、由人工标注的 Minecraft 截图完成首轮端到端测试。结果如下：

- 基准样本数：`1`。
- 守卫接受样本：`1/1`，即接口、视觉服务和观察契约链路均成功工作。
- 必需标签覆盖率：`61.54%`。
- 场景类必需标签全部命中；方块类标签命中 `4/9`，表明远处、面积较小或材质细节仍可能漏检。

这不是“视觉准确率 61.54%”。当前只有一个私有样本，覆盖率仅用于定位模型遗漏并指导下一轮补充多种距离、光照、方块密度和实体场景。截图、人工标注清单及生成报告均保留在本地且已被 Git 忽略。
