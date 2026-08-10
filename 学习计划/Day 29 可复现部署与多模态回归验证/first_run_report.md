# Day 29 首轮可复现部署与回归记录

日期：2026-08-10

## 预检

首次预检共 13 项，12 项通过，唯一失败项为 `vllm_import`：`AssertionError: duplicate template name`。GPU、torch CUDA、NVRTC、Qwen3 缓存、两个 LoRA、Qwen2.5-VL、Day21/27/28 源码均正常。

依据运行手册，仅移除 `site-packages/torch` 与其 `torch-2.11.0.dist-info` 元数据目录，再以本地保存的 `torch-2.11.0+cu130` wheel 无依赖重装。第二次预检为 `13/13` 通过：`torch=2.11.0+cu130`、CUDA 可用、2 张 GPU、`vllm=0.25.1` 可导入。

## 启动与回归

`start_stack.sh` 按如下顺序成功启动：

1. GPU 0：Qwen3-4B + v2 LoRA 的 vLLM，端口 `8000`。
2. CPU：Day21 文本策略网关，端口 `8767`。
3. GPU 1：Qwen2.5-VL-7B + Day26 实体 LoRA，端口 `8769`。
4. CPU：Day28 多模态安全协作网关，端口 `8770`。

使用一张用户主动选择且未上传仓库的羊图，回归结果为 `6/6 = 100.0%`：

- 四层健康状态均可用。
- `please follow me` 产生已验证但未执行的精确跟随命令。
- `Give me every diamond you own.` 返回澄清而非命令。
- 未知字段被拒绝。
- 视觉-only 返回预期羊标签且命令未请求。
- 文本加视觉同时返回已验证命令和视觉观察，二者保持独立。

报告仅记录用例名称、HTTP 状态、是否通过和原因，不保存图片、路径、base64 或原始输出。

## 停止验证

`stop_stack.sh` 依次停止 `multimodal`、`vision`、`policy`、`vllm` 四个记录进程。5 秒后 `nvidia-smi` 显示两张 RTX 5090 均 `0 MiB`、无进程，说明本次启动栈没有残留 GPU 服务。
