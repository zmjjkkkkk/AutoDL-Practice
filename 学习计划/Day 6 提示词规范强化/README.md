# Day 6：提示词规范强化

今天不使用 GPU，目标是通过提示词稳定公众号对话口吻。

## 重点

- 中文为主，英文短语自然点缀。
- “港真”随对话轮次逐渐增加。
- 保留中年说教和饭局点评感。
- 禁止虚构个人履历、导师关系和工作经历。
- 自动保存对话，并记录每轮“港真”出现次数。

## 使用

先生成四个典型轮次的 system prompt：

```powershell
python "学习计划\Day 6 提示词规范强化\build_system_prompt.py"
```

启动本地 API 对话：

```powershell
python "学习计划\Day 6 提示词规范强化\prompt_chat_agent.py"
```

退出后评测最新对话：

```powershell
python "学习计划\Day 6 提示词规范强化\evaluate_prompt_style.py"
```
