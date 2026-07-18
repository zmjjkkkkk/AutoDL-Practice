# 大模型应用与智能体学习记录

这是一个从 Day 1 到 Day 17 的阶段性学习仓库，记录我从远程 GPU 环境配置、RAG 问答、提示词工程与 LoRA 微调，逐步完成到 Minecraft 智能体训练、部署与真实游戏联调的过程。

仓库的定位是学习记录和项目作品集，而不是一个可直接用于生产环境的完整产品。文档中保留了实验目标、关键决策、失败排查和可复现脚本，方便向教授或面试官展示学习路径与实际产出。

## 项目亮点

### 1. 课程资料问答与风格对话智能体

- 支持 PDF、TXT、Markdown 资料读取，保留 PDF 文件名和页码用于溯源。
- 使用字符级 TF-IDF、文本切片、余弦相似度和中英文术语扩展完成 Top-K 检索。
- 实现“检索片段 -> 抽取式草稿 -> 大模型生成”的问答流程，并保存 JSON 对话日志。
- 从公众号文章语料构建风格画像，完成系统提示词、自动化多轮测试和 SFT 风格数据准备。
- 跑通 Qwen3-8B 的远程单卡 bf16 LoRA 训练、adapter 加载与人工纠偏续训流程。

### 2. 基于 LoRA 的 Mindcraft 游戏命令智能体

- 从真实成功行为和 Mindcraft 记忆轨迹构建 SFT 数据集：80 条训练样本、20 条独立评测样本，并校验命令语法与数据泄漏。
- 在双 RTX 5090 环境使用 `torchrun` 完成 Qwen/Qwen3-4B 的 bf16 LoRA 微调；最佳 `checkpoint-45` 验证损失为 `0.0151`。
- 在保留评测集上取得严格命令匹配 `19/20 = 95.0%`。
- 实现命令白名单和参数校验，未知模型输出不会直接执行；仅允许已验证的游戏命令与普通问候语。
- 构建远程 HTTP 推理网关、Windows SSH 隧道和 Mindcraft Node.js 适配器，打通“玩家聊天 -> LoRA 推理 -> 安全校验 -> 游戏动作”链路。
- 已在真实 Minecraft 局域网中验证跟随、停止、查询背包、查询附近方块、采集原木、合成木板、靠近玩家、搜索树木和问候等行为。

## 目录说明

```text
学习计划/
  Day 1 - Day 17/       阶段文档、脚本和实验记录
  Day 11 .../mindcraft-develop/
                         Mindcraft 上游项目快照及本项目的适配改动
data/                    本地原始学习语料（默认不上传）
简历.txt                 根据项目成果整理的简历项目描述（默认不上传）
multi-GPU training project/
                         独立 GitHub 项目，本仓库不重复嵌入
```

独立的多 GPU 训练实验项目请访问：[multi-GPU-training-project](https://github.com/zmjjkkkkk/multi-GPU-training-project)。

建议从以下文档阅读主线：

1. `Day 2 制作课件问答智能体/qa_agent.py`：最小 RAG 问答闭环。
2. `Day 5 远程LoRA实操/README.md` 至 `Day 8 LoRA项目收尾/README.md`：风格 LoRA 训练与提示词评测。
3. `Day 13 Mindcraft行为基线测试/README.md`：游戏智能体基线和轨迹数据来源。
4. `Day 15 Mindcraft真实轨迹SFT数据构造/README.md`：SFT 数据构造与训练。
5. `Day 16 LoRA推理与Mindcraft安全接入/README.md`、`Day 17 LoRA服务与Mindcraft联调/README.md`：安全推理服务与游戏内验证。

## 第三方项目与署名

本仓库部分内容基于开源项目 [mindcraft-bots/mindcraft](https://github.com/mindcraft-bots/mindcraft) 学习和二次开发。该项目采用 MIT License，版权声明已保留在：

`学习计划/Day 11 Mindcraft训练项目启动/mindcraft-develop/LICENSE`

我在此基础上完成的工作主要包括：行为基线记录、SFT 数据构造与校验、Qwen3-4B LoRA 训练与评测、命令白名单、Python 推理网关、SSH 隧道接入，以及 `src/models/mindcraft_lora.js` 适配器和对应 profile。

本仓库不声称 Mindcraft 框架、Minecraft bot 框架或其上游功能由本人从零实现。若基于本仓库继续分发或修改 Mindcraft 相关代码，请继续遵守其 MIT License，并保留原始版权声明。

## 安全与隐私

- 不提交 API Key、SSH 私钥、账号信息、局域网地址、个人聊天/游戏记录或机器配置截图。
- 不提交模型权重、Hugging Face 缓存、训练检查点和原始 PDF 语料；这些文件体积大，且可能包含版权或隐私风险。
- Mindcraft 的 `allow_insecure_coding` 应保持关闭；本项目只在隔离的本地局域网环境中测试，不应连接公共服务器。
- `.gitignore` 已默认排除上述内容。提交前仍建议运行 `git status --ignored` 和 `git diff --cached` 进行人工检查。

## 复现提示

不同阶段使用了本地 Windows、远程 AutoDL GPU 和 Minecraft 局域网环境。模型权重、远程端口、API Key 和原始语料均未包含在仓库中，因此建议先阅读每个 Day 文件夹中的 README，再按实际环境配置运行。

## 当前状态

Day 1-17 已完成归档。后续将以新的阶段目录继续迭代数据、评测集和游戏任务覆盖范围。
