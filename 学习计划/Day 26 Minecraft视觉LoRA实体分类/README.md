# Day 26 Minecraft 视觉 LoRA 实体分类

## 目标

Day25 已通过整图分辨率、全局切片与主体区域裁剪排除了网关和输入处理问题：视觉模型会将清晰的棕色羊误判为猪。本日针对这个真实错误训练一个受控的视觉 LoRA 分类器，只判断单主体截图中的 `sheep` 或 `pig`。

这是一个小范围验证，不宣称识别所有 Minecraft 实体。成功必须由从未参与训练的留出测试集证明。

## 私有数据结构

原始截图位于仓库根目录 `vision_lora/`，已被 `.gitignore` 忽略：

```text
vision_lora/
  sheep/
    train/  # 25 张
    test/   # 10 张，绝不参与训练
  pig/
    train/  # 25 张
    test/   # 10 张，绝不参与训练
```

文件名不承担标签含义。`build_vision_dataset.py` 根据目录生成固定随机顺序的 JSONL 清单，默认种子为 `20260726`，不会重命名或移动原图。

## 评测规则

- 分类输出只能是 `sheep` 或 `pig`。
- 测试集共 20 张，不参与训练、选择 epoch 或人工调参。
- 训练前和训练后都使用同一份测试清单、相同的确定性生成设置。
- 主要指标是精确分类准确率；报告保存预测、真实标签和是否命中，但不保存图片字节或模型原始回答。

建议成功标准：训练后留出集准确率高于基础模型，且不少于 `80%`。若达不到，记录失败与混淆案例，不通过改标签伪造提升。

## 远程流程

上传 Day26 脚本和私有 `vision_lora` 数据后，在远程机器运行：

```bash
cd /root/autodl-tmp/day26-vision-lora

python build_vision_dataset.py \
  --data-root /root/autodl-tmp/vision_lora \
  --output-dir output

python validate_vision_dataset.py \
  --train-manifest output/train.jsonl \
  --test-manifest output/test.jsonl
```

先评测基础模型：

```bash
CUDA_VISIBLE_DEVICES=0 python evaluate_vision_classifier.py \
  --model-dir /root/autodl-tmp/models/Qwen2.5-VL-7B-Instruct \
  --manifest output/test.jsonl \
  --report reports/base_test_report.json
```

训练只使用训练清单：

```bash
CUDA_VISIBLE_DEVICES=0 python train_vision_lora.py \
  --model-dir /root/autodl-tmp/models/Qwen2.5-VL-7B-Instruct \
  --train-manifest output/train.jsonl \
  --output-dir artifacts/qwen25vl_minecraft_entity_lora
```

再对同一留出集评测 LoRA：

```bash
CUDA_VISIBLE_DEVICES=0 python evaluate_vision_classifier.py \
  --model-dir /root/autodl-tmp/models/Qwen2.5-VL-7B-Instruct \
  --adapter-dir artifacts/qwen25vl_minecraft_entity_lora/adapter \
  --manifest output/test.jsonl \
  --report reports/lora_test_report.json
```

最后比较报告：

```bash
python compare_entity_reports.py \
  --baseline reports/base_test_report.json \
  --candidate reports/lora_test_report.json \
  --output reports/base_vs_lora.json
```

训练与评测使用 Transformers 直接加载模型，因此在这一阶段不需要启动 vLLM、8767、8768 或 SSH 隧道。训练结束后，才决定是否把通过留出集评测的视觉 LoRA 接入服务。

## 首轮结果（2026-07-26）

数据构建脚本以固定种子 `20260726` 对目录样本建立 JSONL 清单，校验确认训练集 50 张、测试集 20 张、每类均衡且文件路径无重叠。训练使用 50 张训练图、`12` 个 epoch、最长边 `768`，保存视觉 LoRA 适配器。

在同一份 20 张留出测试集上，基础 `Qwen2.5-VL-7B-Instruct` 的严格实体分类准确率为 `13/20 = 65.0%`；加载 LoRA 后为 `19/20 = 95.0%`，提升 `30.0` 个百分点。比较脚本逐图确认两份报告使用完全相同的测试图片。

唯一残余错误是一张 `sheep` 测试图仍被基础模型和 LoRA 同时预测为 `pig`。该图与 Day25 的棕色羊混淆一致，因此没有用别名或人工后处理把它改成正确结果。当前结论仅适用于本次羊/猪二分类、当前截图采集分布和固定留出集；后续仍需采集不同世界、距离、光照下的独立测试图验证泛化能力。
