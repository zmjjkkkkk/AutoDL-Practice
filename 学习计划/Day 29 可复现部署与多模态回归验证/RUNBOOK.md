# Day 29 运行手册

## 1. 新克隆实例

SSH 地址以云平台当次显示为准，例如：

```bash
ssh -p <port> root@connect.bjb2.seetacloud.com
```

上传本目录后，先进入 `/root/autodl-tmp/day29-deployment`，运行：

```bash
python check_runtime.py --strict --report reports/day29_runtime_report.json
```

该检查失败时不要直接运行启动脚本。它不会修改环境；应先根据失败项补齐模型、适配器或源码。

## 2. 已知 vLLM 导入修复

若 `import vllm` 报 `AssertionError: duplicate template name`，常见原因是克隆镜像中的 `torch` 目录混有旧 Inductor 文件。确认 wheel 存在后，清理 PyTorch 本体并重装；不要删除 `nvidia/`、模型目录或项目目录。

```bash
python -m pip uninstall -y torch
rm -rf /root/miniconda3/lib/python3.12/site-packages/torch
rm -rf /root/miniconda3/lib/python3.12/site-packages/torch-2.11.0.dist-info
python -m pip install --no-deps \
  /root/autodl-tmp/torch-repair-wheel/torch-2.11.0-cp312-cp312-manylinux_2_28_x86_64.whl
python -c "import vllm; print(vllm.__version__)"
```

## 3. 启动与检查

```bash
chmod +x start_stack.sh stop_stack.sh
./start_stack.sh
```

启动顺序固定为：vLLM 8000（GPU 0）-> Day21 策略 8767 -> Day27 视觉 8769（GPU 1）-> Day28 协作 8770。日志位于 `runtime/logs/`，PID 位于 `runtime/pids.tsv`，均只留在远端实例。

## 4. 回归

选择一张私有图片，并只填写你人工确认的封闭标签；报告不会记录图片路径或内容：

```bash
python run_regression.py \
  --image /root/autodl-tmp/vision_lora/sheep/new/<image>.png \
  --expected-entity sheep \
  --report reports/day29_regression_report.json
```

它执行健康检查、跟随命令验证、越界转交澄清、无效请求拒绝、视觉-only 和组合请求。通过不意味着命令被执行，Day29 不连接 Mindcraft。

## 5. 本地隧道与停止

```powershell
ssh -N -L 127.0.0.1:18770:127.0.0.1:8770 -p <port> root@connect.bjb2.seetacloud.com
```

结束时：

```bash
./stop_stack.sh
```

然后关闭本地隧道。停止脚本只处理本次启动脚本记录且仍匹配的进程。
