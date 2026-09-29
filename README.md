# Codex 额度速览

一个随 Codex 桌面版出现的 Windows 用量悬浮窗。打开 Codex，就能直接看到 5 小时额度、一周额度和可用重置卡次数，不用反复进入用量页面。

> 这是独立制作的辅助工具，不是 OpenAI 官方产品，也不会修改 Codex 桌面程序。

## 能看到什么

| 项目 | 显示内容 | 数据来源 |
| --- | --- | --- |
| 5 小时额度 | 剩余百分比、进度条、距离重置的时间 | 300 分钟用量窗口 |
| 一周额度 | 剩余百分比、进度条、距离重置的时间 | 10,080 分钟用量窗口 |
| 可用重置卡 | 可用次数 | `rateLimitResetCredits.availableCount` |

悬浮窗每 60 秒自动刷新，也可以点击右下角的“刷新”。关闭 Codex 窗口后，悬浮窗会隐藏；再次打开 Codex 时会出现。

**关于“重置卡”：**这里显示的是 Codex 返回的 *额度重置次数*，不是购买的通用 credits 余额。若服务没有提供某项数据，界面会显示 `--`，不会把未知值当作零。

## 快速安装

**适用环境：**Windows 版 Codex 桌面应用；已在 Windows 11 和 Codex 桌面版 `26.924.2738.0` 上验证。运行打包好的程序无需安装 Python，也无需管理员权限。

1. 下载本仓库的 ZIP，解压到任意文件夹。
2. 在解压后的文件夹中打开 PowerShell，运行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

3. 安装脚本会立即启动悬浮窗，并在当前用户的 Windows“启动”文件夹中创建快捷方式。以后登录 Windows，它会在后台等待 Codex 打开。

安装位置为 `%LOCALAPPDATA%\CodexQuotaFloat`。安装脚本只为当前用户配置启动项，不会修改 Codex 安装目录。

## 日常使用

- **移动：**拖动标题栏；位置自动保存。
- **临时隐藏：**点击右上角 `×`。下次关闭并重新打开 Codex 窗口时会再次显示。
- **立即刷新：**点击右下角“刷新”，或右键选择“立即刷新”。
- **退出：**右键选择“退出悬浮窗”。再次登录 Windows 后，后台程序会重新启动。

## 数据与隐私

程序调用本机 Codex CLI 的官方 App Server 方法 `account/rateLimits/read`。它使用你已经登录的 Codex 账号，不要求输入 API Key，也不会读取、导出或保存登录令牌。每次刷新时会短暂启动本机的 `codex app-server` 进程。

剩余百分比按 `100 - usedPercent` 计算；倒计时使用服务返回的 `resetsAt`。程序只保存悬浮窗位置到 `%LOCALAPPDATA%\CodexQuotaFloat\position.json`，不保存用量历史。

接口字段参考：[OpenAI Docs — Codex App Server 的 Rate limits](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt)。

## 卸载

在本仓库文件夹中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

脚本会关闭悬浮窗、移除当前用户的启动快捷方式，并删除安装的程序和窗口位置文件。

## 从源码运行或构建

源码只有 `app.py`，使用 Python 标准库。需要 Windows、Python 3.10 或更新版本，以及可用的 Codex CLI。

```powershell
python .\app.py
```

若要自行生成单文件 `.exe`：

```powershell
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name CodexQuotaFloat .\app.py
```

生成文件位于 `dist\CodexQuotaFloat.exe`。

## 常见问题

**显示 `--` 或读取失败？** 先确认 Codex 桌面版已登录，且它的 CLI 可用；然后点击“刷新”。如果 Codex 更新后调整了 App Server 返回字段，当前版本可能需要同步更新。

**为什么窗口没有显示？** 悬浮窗只在检测到 Windows Codex 桌面窗口时显示。如果刚点击过 `×`，关闭并重新打开 Codex 窗口即可。

**为什么重置倒计时和百分比不是同一个数？** 百分比表示窗口内还剩多少额度；倒计时表示这段额度何时重置。两者是独立信息。
