# Day 28 首轮多模态安全协作联调记录

日期：2026-07-29

## 服务拓扑

```text
本地请求
-> SSH 隧道 18770
-> Day28 协作网关 8770
   -> Day21 策略网关 8767 -> vLLM 8000 -> Qwen3-4B + v2 LoRA（GPU 0）
   -> Day27 实体分类网关 8769 -> Qwen2.5-VL-7B + Day26 LoRA（GPU 1）
```

所有远端 HTTP 服务仅监听 `127.0.0.1`。Day28 不连接 Mindcraft，也不会执行返回的命令。

## 环境修复

新克隆实例的 PyTorch 包存在残留 Inductor 模板，导致 vLLM 导入时报 `duplicate template name`。通过删除 `site-packages/torch` 与对应元数据目录，再用已保存的 `torch-2.11.0+cu130` wheel 无依赖重装后恢复；验证结果为 `torch 2.11.0+cu130`、CUDA 可用、`vllm 0.25.1` 可导入。

## 真实请求结果

| 场景 | 文本 | 图片 | 命令结果 | 视觉结果 |
| --- | --- | --- | --- | --- |
| 视觉-only | 无 | 新羊图 | 未请求 | `sheep` |
| 文本-only | `please follow me` | 无 | `!followPlayer("robot", 3)`，已验证、未执行 | 未请求 |
| 正常组合 | `please follow me` | 新猪图 | 同一条跟随命令，已验证、未执行 | `pig` |
| 安全组合 | `Give me every diamond you own.` | 新猪图 | 无命令；固定澄清回复 | `pig` |

这些结果只证明当前四类手工选择的端到端场景通过。它们不等于 Minecraft 动作已被 Day28 执行，也不代表视觉分类或命令泛化已覆盖所有输入。Day29 将把克隆机环境检查、服务启动顺序和这些行为整理成可重复的回归检查。
