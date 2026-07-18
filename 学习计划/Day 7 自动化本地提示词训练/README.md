# Day 7：自动化本地提示词训练

严格来说，本日执行的是自动化提示词测试与迭代，不更新模型权重。

## 一键运行十轮

```powershell
python "学习计划\Day 7 自动化本地提示词训练\auto_dialogue_runner.py"
```

程序将自动：

1. 读取 `questions.json`。
2. 在同一个上下文中依次提问十轮。
3. 每轮超时自动重试三次。
4. 每轮结束立即保存。
5. 统计“港真”、英文词和 API token。
6. 生成 JSON 与 Markdown 评测报告。

## 中断后续跑

```powershell
python "学习计划\Day 7 自动化本地提示词训练\auto_dialogue_runner.py" --resume
```

## 快速测试前两轮

```powershell
python "学习计划\Day 7 自动化本地提示词训练\auto_dialogue_runner.py" --max-turns 2
```
