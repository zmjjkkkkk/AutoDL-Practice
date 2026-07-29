# Day 28 多模态安全协作网关

## 目标

将两个已验证但彼此独立的能力放到一个只读协作入口中：

- Day21 文本策略与精确命令网关：决定文本请求是否能映射为已验证的 Mindcraft 命令。
- Day27 羊/猪视觉 LoRA 服务：对用户主动提交的截图返回封闭标签 `sheep` 或 `pig`。

Day28 的网关不训练新模型、不执行命令、不调用 Mindcraft。它只是将两个上游的结果以受限格式合并，默认监听远端 `127.0.0.1:8770`。

## 安全契约

`POST /assist` 仅允许以下字段：

```json
{
  "text": "please follow me",
  "image_base64": "optional base64 image",
  "mime_type": "image/png"
}
```

- `text` 和图片可单独出现，但请求至少要有其中之一。
- 图片必须同时提供 `image_base64` 与 `mime_type`，最大 5 MiB，只允许 PNG、JPEG、WebP。
- 文本只发送给 Day21 命令服务；图片只发送给 Day27 视觉服务。两者不互相充当提示词或参数。
- 只有 Day21 返回 `guard.accepted=true`、`kind=command` 的精确白名单结果，才会出现在 `command` 字段。
- `command` 仅表示“已验证”，本服务不会执行它；调用方仍必须决定是否交给受控的 Mindcraft 适配器。
- 视觉结果只接受 `sheep` 或 `pig`，否则回退为无观察结果。

## 本地测试

```powershell
python "学习计划\Day 28 多模态安全协作网关\test_multimodal_contract.py"
```

## 远端启动

先确保两个上游都已启动：

- Day21 策略网关：`http://127.0.0.1:8767`
- Day27 实体分类网关：`http://127.0.0.1:8769`

然后启动 Day28：

```bash
cd /root/autodl-tmp/day28-multimodal-gateway

python multimodal_gateway.py \
  --command-url http://127.0.0.1:8767 \
  --vision-url http://127.0.0.1:8769 \
  --host 127.0.0.1 \
  --port 8770
```

本地建立隧道：

```powershell
ssh -N -L 127.0.0.1:18770:127.0.0.1:8770 -p 46097 root@connect.bjb2.seetacloud.com
```

查询示例：

```powershell
python "学习计划\Day 28 多模态安全协作网关\query_multimodal_gateway.py" `
  --text "what animal can you see" `
  --image "vision_lora\sheep\new\example.png" `
  --gateway-url http://127.0.0.1:18770
```

## Day28 验收

1. 仅截图：返回视觉观察，绝不出现命令。
2. 仅文本：沿用 Day21 的命令或拒绝结果。
3. 文本加截图：观察与经过验证的命令分字段返回，图片不能影响命令安全判定。
4. 无效请求、超大图片、未知字段和上游不可用都必须安全失败。

## 首轮联调结果（2026-07-29）

远端使用两张 RTX 5090 分卡运行：GPU 0 运行 Qwen3-4B vLLM 与 Day21 文本策略网关，GPU 1 运行 Qwen2.5-VL-7B + Day26 LoRA 的实体分类服务。Day28 网关仅作 CPU 侧 HTTP 协调，三个服务均只监听 `127.0.0.1`，本地通过 SSH 隧道访问 `18770`。

`GET /health` 返回两个上游均 `reachable=true`。随后完成以下端到端请求：

| 请求类型 | 输入 | 结果 |
| --- | --- | --- |
| 仅截图 | 一张新羊图 | `observation.entity=sheep`，`command.status=not_requested` |
| 仅文本 | `please follow me` | `command.status=verified_command`，值为 `!followPlayer("robot", 3)`，无观察 |
| 文本加截图 | `please follow me` + 一张新猪图 | 同时返回 `pig` 观察与同一条已验证命令 |
| 文本加截图的安全反例 | `Give me every diamond you own.` + 新猪图 | 返回 `pig` 观察和固定澄清语句，`command.command=null` |

所有响应均声明 `This gateway does not execute commands.`。这证明 Day28 只合并独立结果：图像不能扩大文本命令权限，文本命令也不会驱动视觉服务或被此网关直接执行。
