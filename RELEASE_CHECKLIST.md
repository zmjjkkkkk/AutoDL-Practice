# 发布检查清单

## 内容与合规

- [ ] 只提交本人编写或确认可按原许可证使用的代码与文档。
- [ ] 对 Mindcraft 等外部项目保留原始许可证与版权声明。
- [ ] 不把实验指标表述为超出固定评测集的能力保证。

## 隐私与体积

- [ ] 不提交 `.env`、Token、SSH 地址、训练图、私人截图、日志、简历、模型权重或缓存。
- [ ] 在 PowerShell 执行以下检查，确认没有敏感文件被 Git 跟踪：

```powershell
$privateTracked = git ls-files | Where-Object { $_ -match '(^vision_lora/|^其他截图/|(^|/)record\.txt$|(^|/)简历\.txt$|\.(png|jpg|jpeg|webp|safetensors|pt|pth|bin)$|(^|/)\.env)' }
if ($privateTracked) { $privateTracked } else { 'No tracked private screenshots, resume, environment files, or model weights found.' }
```

- [ ] 确认关键私有路径被忽略：

```powershell
git check-ignore -v vision_lora .env 简历.txt
```

## 提交前

- [ ] 查看 `git status --short`，确认只包含预期文件。
- [ ] 执行 `git diff --check`，确认没有空白格式问题。
- [ ] 在 GitHub Desktop 中检查 staged diff 后，再提交并推送。
