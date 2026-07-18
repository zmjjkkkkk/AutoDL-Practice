# Day 13：Mindcraft 行为基线测试

> 日期：2026-07-13  
> 今日目标：不急着训练，先把 AI bot 的当前行为能力记录清楚。

## 1. 为什么先做基线测试

Day 12 已经证明 DeepSeek 驱动的 Mindcraft bot 可以进入 Minecraft，并能听懂简单人话、移动到玩家身边。

Day 13 要做的是把“感觉它能动”变成可复盘的数据：

- 哪些指令能听懂；
- 哪些指令会行动；
- 哪些指令能完成；
- 哪些失败值得后续训练；
- 日志和 memory 能不能转成训练样本。

## 2. 文件说明

```text
test_cases.json
```

行为测试清单。今天先覆盖聊天、移动、跟随、停止、收集、合成几类基础行为。

```text
behavior_test_logger.py
```

交互式记录脚本。你在 Minecraft 里一条条测试，同时在终端里记录结果。

```text
inspect_mindcraft_state.py
```

扫描 Mindcraft 当前 bot 目录，查看 `memory.json`、`last_profile.json`、历史记录等是否存在，并把 memory 快照复制到训练数据目录。

```text
extract_memory_to_sft.py
```

从 Mindcraft 的 `memory.json` 中抽取一版 SFT 草稿，用于后续训练数据雏形。

## 3. 建议测试流程

先启动 Minecraft `1.21.6` 世界，Open to LAN，端口 `55916`。

再启动 Mindcraft：

```powershell
cd "C:\Users\china\Desktop\AutoDL + 开卡训练\学习计划\Day 11 Mindcraft训练项目启动\mindcraft-develop"
node main.js
```

然后打开另一个 PowerShell，运行记录器：

```powershell
python "学习计划\Day 13 Mindcraft行为基线测试\behavior_test_logger.py"
```

你在 Minecraft 里按 `test_cases.json` 的指令逐条发给 bot，然后在记录器里填：

- 是否听懂；
- 是否行动；
- 是否成功；
- bot 回复；
- 观察到的行为；
- 失败类型；
- 备注。

## 4. 扫描当前 Mindcraft 状态

```powershell
python "学习计划\Day 13 Mindcraft行为基线测试\inspect_mindcraft_state.py"
```

这个脚本会读取：

```text
学习计划/Day 11 Mindcraft训练项目启动/mindcraft-develop/bots/deepseek_env/
```

并把 `memory.json` 快照保存到：

```text
data/mindcraft_training/raw_logs/
```

## 5. 抽取 SFT 草稿

```powershell
python "学习计划\Day 13 Mindcraft行为基线测试\extract_memory_to_sft.py"
```

输出位置：

```text
data/mindcraft_training/sft/
```

注意：这只是草稿，不代表可以直接高质量训练。它的价值是让我们看到 Mindcraft 轨迹如何变成训练格式。

## 6. Day 13 胜利标准

今天完成下面三件事就算成功：

- 有一份行为测试 JSON；
- 有一份 Mindcraft memory 快照；
- 有一份 SFT 草稿 JSONL。

