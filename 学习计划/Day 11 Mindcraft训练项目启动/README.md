# Day 11：Mindcraft 训练项目启动

> 今日任务：评估 `mindcraft-develop`，确认训练切入点，并把项目从“应用问答”转向“Minecraft 智能体训练”。

## 1. 当前项目状态

当前目录中已有：

```text
mindcraft-develop/
```

这是 Mindcraft 项目主体。它已经提供：

- Minecraft bot 框架；
- 多模型 API 接入；
- vLLM profile；
- crafting/cooking/construction 任务；
- 多智能体协作任务；
- 评测脚本；
- 运行日志与 memory 保存机制。

所以我们不需要重写框架。

## 2. 我们的切入点

我们只做训练与评测增强：

1. 跑 baseline；
2. 收集任务轨迹；
3. 清洗成训练数据；
4. LoRA/SFT 训练；
5. vLLM 部署训练后模型；
6. 接回 Mindcraft；
7. 再跑任务并比较成功率。

## 3. 推荐从哪个任务开始

先从单智能体 crafting 开始。

原因：

- 任务结构清楚；
- 成功率容易判断；
- 不需要复杂建造评测；
- 不需要打开 insecure coding；
- 数据容易转成训练样本。

示例任务文件：

```text
mindcraft-develop/tasks/basic/single_agent.json
```

示例任务：

```text
gather_oak_logs
```

## 4. 不建议一开始做什么

暂时不建议一上来就做：

- construction；
- 多智能体协作；
- insecure coding；
- 公共服务器；
- 910C；
- 多卡训练。

这些都能做，但它们应该放在 baseline 和数据闭环之后。

## 5. 训练数据应该长什么样

第一版 SFT 数据可以长这样：

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a Minecraft agent. Complete the task using valid actions."
    },
    {
      "role": "user",
      "content": "Goal: Collect at least four oak logs. Inventory: wooden_axe x1. Recent observation: ..."
    },
    {
      "role": "assistant",
      "content": "I should find nearby oak trees, move to one, and collect logs until I have at least four."
    }
  ]
}
```

后续可以把输出改成更结构化：

```json
{
  "thought": "Need oak logs. I already have an axe.",
  "message": "I will collect oak logs now.",
  "action": "!collectBlocks oak_log 4"
}
```

## 6. 训练后如何接回 Mindcraft

Mindcraft 已经有：

```text
mindcraft-develop/profiles/vllm.json
```

训练后模型可以用 vLLM 启动：

```bash
vllm serve /path/to/model --host 0.0.0.0 --port 8000
```

然后让 Mindcraft profile 指向：

```text
http://127.0.0.1:8000/v1
```

## 7. Day 11 结论

项目路线改为：

```text
Mindcraft 框架
-> Minecraft 任务日志
-> 轨迹数据集
-> LoRA/SFT
-> DeepSpeed 多卡扩展
-> vLLM 推理接入
-> Mindcraft 任务评测
-> 继续收集失败样本并迭代
```

这条路线比单纯做问答助手更适合展示“大模型训练与智能体能力增强”。

