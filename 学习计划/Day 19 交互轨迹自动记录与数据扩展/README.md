# Day 19：交互轨迹自动记录与数据扩展

## 今日目标

Day 15 的训练数据主要来自少量真实成功行为和人工审核改写。Day 17-18 已经证明 LoRA、命令白名单、vLLM 服务和真实 Minecraft 可以连通；Day 19 的第一步是让每一次真实游戏交互自动留下结构化轨迹，为扩大数据集提供依据。

本次不把日志直接当作训练数据。日志的作用是收集候选样本：哪些表达被正确映射、哪些被白名单拦截、哪些请求超时，以及游戏动作完成后返回了什么反馈。经过人工筛选和标注后，才可以加入下一轮 SFT 数据集。

## 记录位置与隐私

Mindcraft 的 `mindcraft_lora` 适配器会把每一局写入：

```text
学习计划/Day 19 交互轨迹自动记录与数据扩展/logs/
  mindcraft_interactions_command-router-<时间戳>.jsonl
```

`logs/` 已在根目录 `.gitignore` 中排除，日志不会被 GitHub 跟踪或上传。日志包含玩家输入和游戏反馈；分享日志前应先人工检查是否含有个人信息。

## JSONL 是什么

JSONL（JSON Lines）是“一行一条 JSON 记录”的文件格式。它适合不断追加，也方便 Python 逐行读取、筛选和转换。一次玩家操作通常会产生至少两条记录：

1. `player_request`：玩家说了什么，准备请求哪个网关。
2. `model_decision`：模型原始输出、白名单判定、最终返回给 Mindcraft 的内容和响应耗时。

动作结束后，如果 Mindcraft 将动作结果写入对话历史，还会产生：

3. `game_feedback`：上一条已执行命令和游戏系统反馈。

网关不可用或 HTTP 请求失败时会产生 `gateway_error`，帮助区分“模型没学会”与“服务没有连通”。

## 已监听的字段

`model_decision` 记录示例：

```json
{
  "event": "model_decision",
  "player_text": "please follow me",
  "raw_model_output": "!followPlayer(\"robot\", 3)",
  "guard": {
    "accepted": true,
    "kind": "command",
    "reason": "verified_command"
  },
  "returned_to_mindcraft": "!followPlayer(\"robot\", 3)",
  "latency_ms": 120
}
```

其中 `raw_model_output` 用于诊断模型，`guard` 用于诊断安全规则，`game_feedback` 用于观察执行层结果。三者不能混为同一个指标：命令通过白名单不必然表示游戏动作在复杂环境中完全成功。

## 使用方式

不需要新增启动命令。保持 Day18 的三个服务运行：

1. 远程 vLLM 服务，监听 `127.0.0.1:8000`。
2. 远程 Day18 命令网关，监听 `127.0.0.1:8765`。
3. 本地 SSH 隧道，将 `127.0.0.1:18765` 转发到远程网关。

然后在本地 `mindcraft-develop` 目录照常运行：

```powershell
node main.js
```

启动时控制台会打印本局 JSONL 日志路径。让 bot 执行命令或尝试未知表达后，退出游戏，再运行汇总脚本：

```powershell
python "学习计划\Day 19 交互轨迹自动记录与数据扩展\summarize_interaction_logs.py"
```

如果同时维护根目录的人工 `record.txt`，其中每行采用 `序号. 英文任务 T/F 可选备注` 格式，可生成一份人工审核队列：

```powershell
python "学习计划\Day 19 交互轨迹自动记录与数据扩展\build_review_queue.py"
```

它会把人工判定和最相近的 JSONL 轨迹合并到 `logs/review_queue.json`，并将失败项初步分类为：模型命令映射问题、白名单/参数缺口、执行环境失败或需要人工补充轨迹。这个文件不是训练集；只有补写了真实可用的标准答案、并确认游戏执行后，才能转入下一轮 SFT 数据。

适配器默认只接收 `robot: 消息` 格式的真实玩家聊天，避免服务器提示、药水效果等系统文本被当作玩家任务。若实际玩家名不是 `robot`，在 `profiles/mindcraft_lora.json` 的 `params.player_name` 中修改它。

## 第一批能力扩展

`extension_behaviors.json` 是第一批候选能力的可审计数据源，包含昼夜查询、交付 1 个原木、攻击苦力怕、搜索铁矿、吃苹果和合成铁剑。每条都已经对照 Mindcraft 源码确认存在对应动作 API，但尚未完成真实游戏验证，因此标记为 `source_api_confirmed_pending_game_test`。

生成不含候选能力的基线合并数据：

```powershell
python "学习计划\Day 19 交互轨迹自动记录与数据扩展\build_expanded_sft_dataset.py"
```

仅在明确进行实验训练时，才加入待验证能力：

```powershell
python "学习计划\Day 19 交互轨迹自动记录与数据扩展\build_expanded_sft_dataset.py" --include-provisional
```

发送到远程训练前，运行：

```powershell
python "学习计划\Day 19 交互轨迹自动记录与数据扩展\validate_expanded_sft_dataset.py"
```

实验模型通过离线评测后，仍需要在本地 Minecraft 逐条确认游戏动作。只有游戏验证成功的候选，才能写入生产白名单；路径失败、多步骤任务和自由知识问答不能靠简单追加 SFT 样本解决。

## 数据扩展规则

- 保留：白名单通过、游戏反馈符合预期、表达方式与已有样本不同的请求。
- 单独标记：模型输出正确但游戏因距离、工具、路径或库存而失败的请求；这属于执行环境问题，不应被误标为模型错误。
- 重点收集：被拦截的未知命令、数量表达、指代词、连续命令、否定和取消请求。
- 不直接训练：含私人聊天、无明确意图、服务超时、动作结果不清楚或未经人工确认的日志。
- 扩展新能力时，同时更新 SFT 数据、独立评测集和 `command_guard.py` 白名单；只修改其中一个会造成训练、评测与部署不一致。

## 验收标准

1. 启动 Mindcraft 后，控制台显示 `Mindcraft interaction log:` 及 `.jsonl` 文件路径。
2. 发送 `please follow me` 后，日志出现 `player_request` 和接受状态的 `model_decision`。
3. 发送一个未覆盖的复杂请求后，日志保留原始输出与 `unknown_command` 或 `unapproved_text` 原因，但游戏不会执行该内容。
4. 完成一项查询或动作后，如 Mindcraft 产生系统反馈，日志出现对应的 `game_feedback`。

## 第二批实验：扩展能力的实机验证

Day 19 扩展数据集训练完成：128 条训练样本、32 条独立评估样本，双卡 LoRA 共训练 96 steps。离线严格匹配结果为 31/32（96.875%）。唯一失分是 `do you have anything`：预期 `!inventory`，模型误答为问候语。这条评估数据不回填到本轮训练集；它会和后续真实交互中收集到的同类表达一起进入下一轮候选池，避免把测试题直接变成训练题。

首轮真实游戏测试的可公开结论见 [game_test_report.md](game_test_report.md)。原始 JSONL 仍只保留在被 Git 忽略的 `logs/` 目录。

`experimental_command_guard.py` 与 `vllm_experimental_gateway.py` 构成 Day 19 的隔离实验服务。它们在原有八条生产命令之外，仅临时允许以下六条已核对源码、但尚未完成实机验证的动作：

```text
!stats
!givePlayer("robot", "oak_log", 1)
!attack("creeper")
!searchForBlock("iron_ore", 32)
!consume("apple")
!craftRecipe("iron_sword", 1)
```

实验网关使用远程 `127.0.0.1:8766`，本地 SSH 隧道使用 `127.0.0.1:18766`。正式 Day 18 网关仍使用 8765/18765，正式 `command_guard.py` 不作改动。每项测试都必须验证“模型命令正确、白名单通过、游戏反馈符合预期”这三个层面；通过后才能进入正式白名单。
