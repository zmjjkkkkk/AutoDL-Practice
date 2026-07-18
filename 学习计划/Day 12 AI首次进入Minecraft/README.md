# Day 12：AI 首次进入 Minecraft

> 日期：2026-07-10  
> 今日目标：先让 DeepSeek 驱动的 Mindcraft bot 加入本地 Minecraft 世界。

## 1. 今天能不能做

可以尝试。

当前已确认：

- Node.js 和 npm 已安装；
- Mindcraft npm 依赖已安装；
- `mineflayer` 可以正常加载；
- Minecraft LAN 端口已设置为 `55916`；
- DeepSeek API smoke test 已通过；
- Mindcraft 默认 profile 已改成 `profiles/deepseek_env.json`；
- Mindcraft 默认 Minecraft 版本已改成 `1.12.2`。

## 2. 先做最小连接，不做训练

今天的目标不是训练，也不是多卡。

今天只验证：

```text
Minecraft 1.12.2 世界
-> Open to LAN
-> Mindcraft bot 连接
-> bot 在游戏里发 hello / 执行简单聊天
```

只有 bot 能稳定进游戏，后面才谈任务、轨迹、训练数据。

## 3. Minecraft 侧操作

1. 打开 Minecraft Launcher；
2. 选择 Java Edition；
3. 新建或选择 `1.21.6` 安装项；
4. 启动游戏；
5. 进入一个单人世界；
6. 按 `Esc`；
7. 点击 `Open to LAN`；
8. 建议先开：
   - Game Mode: Survival 或 Creative 都可以；
   - Allow Cheats: ON；
9. 点击 `Start LAN World`；
10. 记下聊天栏显示的端口，例如：

```text
Local game hosted on port 55916
```

如果端口不是 `55916`，要把 Mindcraft 的 `settings.js` 里 `port` 改成实际端口。

## 4. Mindcraft 启动方式

进入项目目录：

```powershell
cd "C:\Users\china\Desktop\AutoDL + 开卡训练\学习计划\Day 11 Mindcraft训练项目启动\mindcraft-develop"
```

启动：

```powershell
node main.js
```

如果连接成功，Minecraft 世界里应该会出现名为 `deepseek_env` 的 bot。

Mindcraft 的网页 UI 当前使用：

```text
http://localhost:8081
```

之所以不用默认 `8080`，是因为本机可能已有旧的 Mindcraft/Node 进程占用该端口。

## 5. 如果遇到 unsupported protocol version

如果看到类似：

```text
unsupported protocol version: 1.21.11
```

说明当前 Minecraft 小版本太新，Mindcraft 当前依赖还不支持。

请在 Minecraft Launcher 里新建 `1.21.6` 安装项，并用 `1.21.6` 启动世界。

## 6. 如果看到 EADDRINUSE: 8080

如果看到：

```text
listen EADDRINUSE: address already in use ::1:8080
```

说明本机 `8080` 已经被旧进程占用。当前配置已改用 `8081`，重新运行即可。

如果还是报同类错误，先关闭之前运行 `node main.js` 的 PowerShell 窗口，或在那个窗口按 `Ctrl+C` 停止旧进程。

## 7. 如果 LAN 端口不是 55916

打开：

```text
学习计划/Day 11 Mindcraft训练项目启动/mindcraft-develop/settings.js
```

找到：

```js
"port": 55916,
```

改成 Minecraft 聊天栏显示的真实端口。

也可以临时在 PowerShell 里设置：

```powershell
$env:MINECRAFT_PORT="你的端口"
node main.js
```

## 6. 今天不要做什么

先不要：

- 跑多智能体任务；
- 开 `allow_insecure_coding`；
- 连公共服务器；
- 买多卡；
- 做训练。

Day 12 的胜利标准很简单：

> AI bot 成功加入 Minecraft `1.21.6` 世界，并能在聊天里回应。
