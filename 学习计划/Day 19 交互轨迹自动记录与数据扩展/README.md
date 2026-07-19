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
