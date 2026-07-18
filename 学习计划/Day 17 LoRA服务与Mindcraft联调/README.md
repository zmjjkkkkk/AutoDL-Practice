# Day 17: LoRA 服务与 Mindcraft 联调

## 今日目标

把 Day 15 训练出的 LoRA 适配器从离线评测推进到可调用的安全命令服务，并为接入 Mindcraft bot 做准备。

## 已有依赖

- Day 15：基础模型缓存、`checkpoint-45` 适配器和 95% 严格命令匹配评测。
- Day 16：`infer_mindcraft_command.py`、`command_guard.py`、`test_inference.py`。

## 今日步骤

1. 上传并运行 Day 16 推理脚本，确认远程 GPU 推理和命令白名单正常。
2. 在本目录创建 HTTP 命令服务：接收玩家文本，返回白名单放行后的命令或拒绝结果。
3. 阅读 Mindcraft 当前的模型调用位置，确定如何把服务结果安全地交给 bot。
4. 完成游戏内最小联调：至少验证跟随、停止和查看背包。

## 安全约束

模型生成的内容不是可直接执行的指令。只有 `command_guard.py` 已验证的命令才能发送到 Mindcraft；未知命令和非批准文本一律不执行。

## 网关服务

`command_gateway.py` 是不依赖额外 Web 框架的 HTTP 服务。它启动时只加载一次基础模型和 LoRA 适配器，随后处理多个请求，避免每句话都重新加载 4B 模型。

它默认只监听远程服务器的 `127.0.0.1:8765`：外部网络不能直接访问。Windows 本地 Mindcraft 通过 SSH 隧道访问它。

接口：

- `GET /health`：服务存活检查。
- `POST /command`：JSON 请求体为 `{"text":"please follow me"}`；返回模型原始输出与白名单判定。

远程启动命令：

```bash
CUDA_VISIBLE_DEVICES=0 \
HF_HOME=/root/autodl-tmp/day15-sft/hf-cache \
HF_HUB_OFFLINE=1 \
python command_gateway.py \
  --adapter_dir /root/autodl-tmp/day15-sft/artifacts/qwen3_4b_mindcraft_lora/checkpoint-45
```

Windows 本地建立隧道：

```powershell
ssh -N -L 8765:127.0.0.1:8765 -p 17514 root@connect.bjb2.seetacloud.com
```

当前实际可用的本地端口为 `18765`，因为 Windows 拒绝绑定 `8765`：

```powershell
ssh -N -L 18765:127.0.0.1:8765 -p 17514 root@connect.bjb2.seetacloud.com
```

## Mindcraft 适配器

Mindcraft 源码新增 `src/models/mindcraft_lora.js`，它实现项目统一的 `sendRequest` 接口：提取最近一条玩家消息，调用 `http://127.0.0.1:18765/command`，只返回网关白名单已经批准的值。

Mindcraft 启动时也会发出内部提示；当没有玩家消息可路由时，适配器静默返回制表符，不会把安全回退文本发到游戏聊天栏。

Mindcraft 执行命令后会把执行结果追加到历史。适配器只在历史最后一条是新的玩家消息时才调用 LoRA，避免旧请求在执行结束后被重复生成和执行。

查询命令 `!nearbyBlocks` 与 `!inventory` 的执行结果不需要再次交给 LoRA：适配器只在这两条已验证查询之后，将 Mindcraft 返回的系统结果原样转述到游戏聊天栏。这样既能显示动态内容，也不会重复执行查询。

## 2026-07-17 联调记录

- 远程网关健康检查通过，Windows SSH 隧道已连通本地 `127.0.0.1:18765`。
- `please follow me` 已完成“本地请求 -> 隧道 -> 远程 LoRA -> 白名单”的端到端验证。
- 首次接入时发现启动内部提示会被说出，已改为静默处理。
- 首次游戏内 `show your inventory` 出现重复执行，原因是适配器重复读取历史中的旧玩家请求；已修复为仅处理历史最后一条的新玩家消息。
- 修复后游戏内 `show your inventory` 仅执行一次 `!inventory`，验证通过。
- 游戏内 `please follow me` 已触发一次 `!followPlayer("robot", 3)` 并正常开始跟随，验证通过。
- 游戏内 `stop` 已触发一次 `!stop` 并正常中断跟随，验证通过。
- 游戏内 `go chop four oak logs` 已正常触发资源采集，验证通过。
- 游戏内 `what blocks are nearby` 已正常执行 `!nearbyBlocks` 并在聊天栏显示实际查询结果，验证通过。
- 游戏内 `make wooden planks` 已正常触发 `!craftRecipe("oak_planks", 1)`，验证通过。
- 游戏内 `come closer` 已正常触发 `!goToPlayer("robot", 2)`，验证通过。
- 游戏内 `search for an oak tree again` 已正常触发 `!searchForBlock("oak_log", 32)`，验证通过。
- 游戏内 `hello there` 已返回批准的普通问候文本，验证通过。

## Day 17 结论

当前 LoRA 数据集覆盖的 8 条不同 Mindcraft 命令，以及普通问候回复，均已完成真实 Minecraft 游戏内验证。`collect_some_wood` 与 `collect_oak_logs` 两个语义意图使用相同的 `!collectBlocks("oak_log", 4)` 命令，已由资源采集测试共同覆盖。

端到端运行链路为：玩家聊天 -> Mindcraft `mindcraft_lora` 适配器 -> 本地 SSH 隧道 -> 远程 LoRA 网关 -> 命令白名单 -> Mindcraft 命令执行。所有未知模型命令仍由白名单拦截，不会被交给游戏执行。

`profiles/mindcraft_lora.example.json` 是实验 profile 模板。启动前必须把 `name` 替换为当前实际 bot 名称；该 profile 仅适合当前 8 个已训练命令与问候语，不应替代通用对话或复杂编码任务的模型。

当前已创建可直接使用的 `profiles/mindcraft_lora.json`，bot 名称为 `deepseek_env`。保留原来的 `profiles/deepseek_env.json` 不变；启动 LoRA 实验时显式使用新 profile，便于随时切回原模型。
