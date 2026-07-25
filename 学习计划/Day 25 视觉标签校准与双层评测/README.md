# Day 25：视觉标签校准与双层评测

## 为什么需要第二把尺子

Day 24 的 `30.66%` 是严格精确匹配基线：人工标签与模型标签必须逐字一致才计分。这个分数必须保留，因为它反映了系统能否输出预期的规范标识。

但 Day 24 也发现一类不同的问题：模型可能将通用的 `chest` 写成 `oak_chest`。这不是正确的 Minecraft 精确标识，却与“可见箱子”的粗粒度事实有关。若把它和“把羊看成 character”都视为同样的错误，就无法知道下一步应该改命名规范、提示词，还是模型能力。

Day 25 因此同时输出两套指标：

1. **严格覆盖率**：不做任何映射，保持 Day 24 的精确规则。
2. **别名校准覆盖率**：只应用 `label_aliases.json` 中人工审核过、方向明确的同义映射。

别名校准不是新准确率，更不能替代严格指标。它只是把“命名粒度差异”从“完全没有识别”中分离出来。

## 初始别名规则

当前 [label_aliases.json](label_aliases.json) 仅包含一条保守规则：

```json
"oak_chest": "chest"
```

它的含义是：当模型输出 `oak_chest`、人工必需标签为 `chest` 时，严格评测仍记为未命中，校准评测可额外记为同义命中。

以下情况不得作为别名：

- `oak_log` 与 `acacia_log`：树种不同，属于真实识别差异。
- `character` 与 `sheep` 或 `donkey`：类别过于笼统，不能伪装成具体生物识别。
- `sandstone` 与 `smooth_sandstone_stairs`：材质或形状不同。

新增别名必须有明确语义理由，并应在提交信息中说明来源；不能依据“这样能提高分数”来增加别名。

## 运行

Day25 不调用模型，也不需要重启远端服务。它读取 Day24 的私有报告，并将校准结果写入新的私有报告：

```powershell
python "学习计划\Day 25 视觉标签校准与双层评测\analyze_calibrated_benchmark.py" `
  --report "学习计划\Day 24 多场景视觉基准与漏检分析\reports\vision_benchmark_report.json" `
  --aliases "学习计划\Day 25 视觉标签校准与双层评测\label_aliases.json" `
  --output "学习计划\Day 25 视觉标签校准与双层评测\reports\calibrated_benchmark_report.json"
```

输出包含全局和每个案例的严格覆盖率、校准覆盖率、别名带来的额外命中，以及实际使用过的别名。报告仍被 Git 忽略，因为其中含有私有人工标注与已验证观察标签。

## 离线测试

```powershell
python "学习计划\Day 25 视觉标签校准与双层评测\test_analyze_calibrated_benchmark.py"
```

预期输出：

```text
Day 25 calibrated benchmark tests passed: 2/2
```

## 安全边界

该脚本只分析本地 JSON 报告，不读取图片、不调用网络、不修改视觉模型或命令网关。视觉输出仍然只是只读线索，任何游戏动作仍须经过 Day21 命令策略与精确白名单。

## 定向观察模式

Day25 还为 Day23 API 增加了固定观察侧重点：`overview`、`blocks`、`entities`、`hazards`。它们不是用户自由提示词，而是服务端写死的枚举；四种模式都要求同一份 JSON 契约并经过同一观察守卫。

例如，对一张本地私有截图发起实体定向观察：

```powershell
python "学习计划\Day 25 视觉标签校准与双层评测\query_focused_observation.py" `
  --image "学习计划\Day 24 多场景视觉基准与漏检分析\private\entity_present.png" `
  --focus entities `
  --gateway-url http://127.0.0.1:18768
```

实体模式明确禁止 `character`、`animal`、`mob` 等泛化词；模型不确定时应返回空列表。该约束不会把空列表伪装成识别成功，但能避免泛化词污染后续精确评测。

## 同图定向对比

不要只凭一条模型回复判断定向模式是否有效。`compare_observation_focus.py` 会对同一张私有图片分别调用多个固定模式，并使用 Day24 的人工标签计算每个模式的严格覆盖率：

```powershell
python "学习计划\Day 25 视觉标签校准与双层评测\compare_observation_focus.py" `
  --manifest "学习计划\Day 24 多场景视觉基准与漏检分析\vision_benchmark_manifest.json" `
  --case-id entity_present `
  --focuses overview entities `
  --gateway-url http://127.0.0.1:18768 `
  --output "学习计划\Day 25 视觉标签校准与双层评测\reports\entity_focus_comparison.json"
```

同理，可用 `--case-id indoor_dense --focuses overview blocks` 检查方块定向模式。报告包含守卫验证后的观察对象和精确标签覆盖率，但仍不保存图片字节或模型原始文本。

### 首轮定向对比（2026-07-25）

在一个实体案例和一个室内高密度案例上进行同图对比后，定向模式没有带来精确命中提升：

- 实体案例：`overview` 总体严格覆盖率为 `28.57%`，`entities` 为 `14.29%`；两种模式的具体实体命中均为 `0%`。实体模式将泛化的 `character` 改为 `player`，但人工标签是另一种具体生物，因此仍是错误识别。
- 室内案例：`overview` 与 `blocks` 的总体严格覆盖率均为 `20.00%`，都只命中 `chest`；方块定向未改善对磨石、砂岩台阶等细粒度方块的识别。

这两次结果不代表所有图片上定向提示都无效，但足以说明不能把它默认接入主观察链路。`overview` 仍是默认模式；定向模式目前只作为受控实验工具。下一轮更值得测试的是输入分辨率与细粒度识别之间的关系，而不是继续堆叠提示词。

## 分辨率 A/B 测试

Day23 默认将图片缩放到最长边 `768`，这有利于稳定控制上下文长度，但可能损失细小方块纹理和远处实体。下一步使用相同模型、相同 6 张私有图片、相同人工标签，只将 Day23 网关的 `--max-image-side` 改为 `1024`，并与现有 `768` 报告做严格对照。

实验成功条件不是“模型回答看起来更详细”，而是同时满足：

1. 守卫接受率不降低。
2. 同一份人工标签下的严格必需标签覆盖率提高。
3. 提升能够在室内高密度或实体等目标案例中体现，而不只来自额外场景词。

`1024` 若触发上游上下文长度错误，则改用 `896`，不改变其他参数。对照脚本：

```powershell
python "学习计划\Day 25 视觉标签校准与双层评测\compare_resolution_reports.py" `
  --baseline "学习计划\Day 24 多场景视觉基准与漏检分析\reports\vision_benchmark_report.json" `
  --candidate "学习计划\Day 25 视觉标签校准与双层评测\reports\vision_benchmark_1024.json" `
  --output "学习计划\Day 25 视觉标签校准与双层评测\reports\resolution_768_vs_1024.json"
```

### 首轮分辨率对比（2026-07-25）

在相同模型、相同 6 张私有截图、相同人工标签与 `temperature=0` 条件下，将最长边从 `768` 提升至 `1024` 后：

- 守卫接受率保持 `100.00%`（`6/6`），没有因更高分辨率产生格式拒绝。
- 严格必需标签平均覆盖率从 `30.66%` 提升至 `34.00%`，增益为 `3.33` 个百分点。
- `entity_present` 从 `14.29%` 提升至 `28.57%`；`indoor_dense` 从 `0.00%` 提升至 `20.00%`，说明高分辨率对两个重点弱项有帮助。
- `daylight_open_near` 从 `57.14%` 降至 `42.86%`；其余 3 个案例不变。因此，这不是所有场景的一致提升。

当前可将 `1024` 作为观察网关的默认最长边，但严格覆盖率而非单次自然语言描述仍是判断依据。后续应针对近景开放场景保留专项样本，避免只看均值而掩盖退化。

## 局部切片观察实验

提高整图分辨率到 `1280` 后，继续提高输入尺寸没有带来可测收益，因此本日也验证了另一种思路：把一张截图按固定网格裁为局部区域，让视觉模型把同样的预算集中在局部细节上。

`tiled_observation.py` 会把每一块分别发送到已有的 Day23 只读 `/observe` API；每块都必须先通过 Day22 观察守卫。`run_tiled_benchmark.py` 只合并这些已验证的标签，并保留既有上限：`visible_blocks` 最多 6 个、`visible_entities` 最多 4 个。它不连接 Day21 命令网关，也不会触发游戏动作。

第一轮固定为 `2x2` 网格与 `10%` 重叠，并使用与整图 `1280` 相同的 6 张私有截图及人工标签。结果如下：

- 守卫接受率保持 `100.00%`（`6/6`）。
- 整图 `1280` 的严格覆盖率为 `34.00%`；全局切片为 `31.65%`，下降 `2.35` 个百分点。
- `daylight_open_far` 提升 `9.09` 个百分点，`water_or_height_hazard` 提升 `11.11` 个百分点。
- `entity_present` 下降 `14.29` 个百分点，`indoor_dense` 下降 `20.00` 个百分点。

因此，不能将“所有场景都切片并直接合并”作为默认观察策略。局部裁剪可能丢失场景语境，多个切片的标签并集也会带来噪声，或在标签数量上限下挤出关键信息。整图 `1280` 仍是默认模式。

接下来只诊断两个退化案例，避免重复调用全部 24 次：

```powershell
python "学习计划\Day 25 视觉标签校准与双层评测\run_tiled_benchmark.py" `
  --manifest "学习计划\Day 24 多场景视觉基准与漏检分析\vision_benchmark_manifest.json" `
  --gateway-url http://127.0.0.1:18768 `
  --case-id entity_present --case-id indoor_dense `
  --report "学习计划\Day 25 视觉标签校准与双层评测\reports\tiled_hard_cases_diagnostic.json"
```

该诊断报告仅保存每块守卫已验证的观察与缩放元数据，不保存截图字节或模型原始文本。只有找到了可泛化的选择规则，才考虑将切片用于某一类特定场景。

### 两个退化案例的诊断

对 `entity_present` 与 `indoor_dense` 重新运行 8 次局部观察后，平均严格覆盖率仅为 `7.14%`。逐块检查表明它们的失败原因不同：

- 室内案例：右上切片确实返回了 `oak_wooden_chest`，但合并器按切片顺序收集标签，左上切片已经先占满 6 个方块名额，因此该线索没有进入最终观察结果。这是合并顺序与命名粒度的问题，不等同于“模型完全没有看见箱子”。`sandstone` 也不能在严格层直接当作 `smooth_sandstone` 或台阶类方块。
- 实体案例：各切片给出 `player`、`wool`、`cow` 等不一致线索，却没有在 `visible_entities` 中给出人工标注的具体实体。这是实体细粒度识别失败；不能把 `wool`、`cow` 或泛化实体强行映射为目标实体。

因此，下一步不再尝试全局网格并集。室内类问题可研究保守的标签规范化和更合理的证据排序；实体类问题则需要针对明确视觉区域的局部裁剪评测，且仍须以严格标签命中作为成功条件。

## 指定区域实体观察

`query_region_observation.py` 是单区域的只读观察工具。调用者必须显式提供裁剪坐标，脚本只将该区域送往 Day23 `/observe` API，并可使用服务端固定的 `entities` 模式；它不接受自由提示词，也不连接命令网关。

对 `entity_present` 的人工复核表明，羊位于画面中央前景。可先用覆盖主体及少量上下文的区域测试：

```powershell
python "学习计划\Day 25 视觉标签校准与双层评测\query_region_observation.py" `
  --image "学习计划\Day 24 多场景视觉基准与漏检分析\private\entity_present.png" `
  --left 850 --top 480 --right 1600 --bottom 1200 `
  --focus entities `
  --gateway-url http://127.0.0.1:18768 `
  --output "学习计划\Day 25 视觉标签校准与双层评测\reports\entity_present_center_region.json"
```

成功条件很严格：守卫接受，且 `visible_entities` 中出现 `sheep`。`player`、`cow`、`wool` 等其他线索都不能算命中。该测试仅验证“明确主体区域是否有助于实体识别”，不把区域结果自动并入整图观察。

### 首轮主体区域结果

使用中央前景区域 `left=850, top=480, right=1600, bottom=1200` 后，网关实际将完整的 `750x720` 裁剪图发送给模型，没有发生缩放。守卫接受了结果，但模型以 `0.9` 置信度输出 `pig`，而人工标注的具体实体为 `sheep`。

这条负例排除了三个常见归因：不是整图分辨率不足，不是全局切片合并挤掉标签，也不是实体被远处背景淹没。模型已看见并分类主体，但把 Minecraft 中棕色羊的纹理误判为猪。严格层和校准层都不能将 `pig -> sheep` 映射；那会把错误分类伪装成成功。

因此，若下一阶段要显著提高具体实体命中率，应构建带实体类别标注的 Minecraft 截图数据集，并对视觉模型进行受控的视觉 SFT/LoRA 训练及留出集评测。当前 Day25 的网关、缩放、切片与区域裁剪实验到此已经完成了足够的错误归因。

## 首轮校准结果（2026-07-25）

使用 Day24 的 6 个私有案例运行校准分析，结果如下：

- 严格必需标签平均覆盖率：`30.66%`。
- 别名校准覆盖率：`34.00%`。
- 校准增益：`3.33` 个百分点。
- 实际应用的别名：仅 `indoor_dense` 中的 `oak_chest -> chest`。

该结果没有掩盖实体、树种或方块变体的识别不足。相反，增益较小表明主问题仍是视觉模型对细粒度物体的识别能力，而不是标签字符串格式。严格指标继续作为主指标；校准指标只服务于错误归因。
