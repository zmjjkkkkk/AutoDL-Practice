# Day 14: 双卡 DDP 实操

今天不训练大模型，而是先完成一次真实的单机双卡数据并行训练。

## 本次要验证什么

- `torchrun` 能启动两个 Python 训练进程。
- rank 0 使用 GPU 0，rank 1 使用 GPU 1。
- 两个进程通过 NCCL 同步梯度。
- 训练结束后，两张卡上的模型参数保持一致。
- 程序把本次硬件和训练结果保存为 JSON 报告。

## 上传到 AutoDL

在本地 PowerShell 中执行，按提示输入新实例的密码：

```powershell
scp -P 52363 -r "C:\Users\china\Desktop\AutoDL + 开卡训练\学习计划\Day 14 双卡DDP实操" root@connect.bjb2.seetacloud.com:/root/autodl-tmp/day14-ddp
```

## 在远程服务器运行

先 SSH 登录，再执行：

```bash
cd /root/autodl-tmp/day14-ddp
torchrun --standalone --nproc_per_node=2 ddp_smoke_test.py
```

成功后会生成：

```text
output/ddp_smoke_report.json
```

其中 `parameter_fingerprints_match: true` 表示双卡梯度同步成功。

## 这和后续大模型训练的关系

这次用的是 DDP，即每张卡各有一份完整模型、各处理一部分数据、再同步梯度。后续训练更大模型时，DeepSpeed ZeRO 会在此基础上进一步拆分优化器状态、梯度或参数，从而减少单卡显存压力。

## DeepSpeed ZeRO Stage 2 验证

完成 DDP 后，安装 DeepSpeed：

```bash
pip install deepspeed
```

将本目录再次上传到服务器后，运行：

```bash
cd /root/autodl-tmp/day14-ddp
deepspeed --num_gpus=2 deepspeed_zero2_smoke.py --deepspeed --deepspeed_config ds_zero2_config.json
```

该命令会让 DeepSpeed 在两张 GPU 上启动训练，并启用 bf16 与 ZeRO Stage 2。结果保存为：

```text
output/deepspeed_zero2_report.json
```
