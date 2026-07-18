# Mindcraft 项目初步阅读记录

## 1. 已读关键文件

- `README.md`
- `minecollab.md`
- `package.json`
- `profiles/vllm.json`
- `src/models/vllm.js`
- `tasks/basic/single_agent.json`
- `tasks/evaluation_script.py`

## 2. 关键发现

### 2.1 已支持 vLLM

`profiles/vllm.json` 中已经有 vLLM 配置：

```json
{
  "name": "vllm",
  "model": {
    "api": "vllm",
    "model": "Qwen/Qwen2.5-1.5B-Instruct",
    "url": "http://127.0.0.1:8000/v1"
  },
  "embedding": "openai"
}
```

这说明训练后的本地模型可以通过 vLLM 接入 Mindcraft。

### 2.2 已有任务评测

`minecollab.md` 说明了任务类型：

- crafting；
- cooking；
- construction；
- multi-agent collaboration。

这对训练非常关键，因为我们不只是生成文本，而是可以看任务是否成功完成。

### 2.3 已有 baseline 任务

`tasks/basic/single_agent.json` 里有 `gather_oak_logs`。

这个任务适合作为第一版实验：

- 目标明确；
- 评测简单；
- 不涉及危险代码执行；
- 适合生成第一批训练轨迹。

### 2.4 vLLM 接入代码较直接

`src/models/vllm.js` 使用 OpenAI-compatible API 调用本地 vLLM 服务。

后续训练后的模型只要能被 vLLM serve，就可以被 Mindcraft 调用。

## 3. 初步可行性判断

可行，而且路线清楚。

最小闭环是：

```text
运行 gather_oak_logs
-> 保存日志
-> 抽取成功/失败轨迹
-> 生成 SFT 数据
-> 训练 LoRA
-> vLLM 部署
-> 再跑 gather_oak_logs
-> 比较成功率
```

## 4. 暂时不碰的部分

- construction task；
- insecure coding；
- 多智能体任务；
- 910C；
- DeepSpeed 多卡；
- 大规模任务并行。

它们不是不要，而是应该放在第一轮闭环之后。

## 5. 下一步建议

下一步不是直接训练，而是先跑原版 Mindcraft baseline。

要确认：

- Node.js 版本；
- `npm install` 是否成功；
- Minecraft Java Edition 或任务 server 是否可用；
- `node main.js --task_path tasks/basic/single_agent.json --task_id gather_oak_logs` 是否能跑；
- 日志保存在哪里；
- 成功/失败结果如何读取。

