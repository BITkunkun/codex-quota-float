# Codex 宠物用量条

把 Codex 的用量放在桌面宠物头顶：两条线分别显示 **5 小时**和**一周**的剩余额度。用量条根据宠物图像的位置自动定位，宠物隐藏时也会隐藏；它本身没有自由拖动功能。

> 这是独立制作的 Windows 辅助工具，不是 OpenAI 官方产品，也不会修改 Codex 桌面程序。

## 界面与数据

| 界面 | 含义 |
| --- | --- |
| 青色线 · 5 小时 | 300 分钟窗口的剩余额度百分比 |
| 黄色线 · 一周 | 10,080 分钟窗口的剩余额度百分比 |

两条线每 60 秒自动更新。**右键点击用量条**可查看两个窗口的重置倒计时、可用重置卡次数，也可以手动刷新或退出。界面的“重置卡”是 Codex 返回的 *额度重置次数*，并非购买的通用 credits 余额。数据缺失时显示 `--`。

## 安装或从旧版升级

**适用环境：**Windows 版 Codex 桌面应用，已开启并显示桌面宠物。已在 Windows 11 和 Codex 桌面版 `26.924.2738.0` 上验证。打包好的 `.exe` 无需管理员权限或 Python。

1. 下载本仓库的 ZIP 并解压。
2. 在解压后的文件夹打开 PowerShell，运行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

安装脚本会关闭旧版用量窗、替换当前用户的安装文件、删除旧版留下的自由拖动位置记录，并立即启动新版。它还会在当前用户的 Windows“启动”文件夹中创建快捷方式。以后登录 Windows 后，程序会在后台等待宠物出现。

安装位置：`%LOCALAPPDATA%\CodexQuotaFloat`。如果宠物尚未显示，可在 Codex 中输入 `/pet`，或在 **设置 → Pets** 中显示宠物。选择 **Mini** 时没有宠物图像，用量条也不会出现。

## 工作方式与隐私

- 程序通过 Windows 辅助功能接口读取桌面宠物图像的屏幕边界，并把用量条固定在其上方。拖动宠物后，用量条会根据图像的新位置重新定位。
- 用量来自本机 Codex CLI 的 App Server 方法 `account/rateLimits/read`。剩余百分比按 `100 - usedPercent` 计算；倒计时来自 `resetsAt`。
- 不需要输入 API Key；程序不读取、导出或保存登录令牌，也不保存用量历史或窗口位置。刷新时会短暂启动本机的 `codex app-server` 进程。

参考：[OpenAI Docs — Pets](https://learn.chatgpt.com/docs/pets) 和 [Codex App Server 的 Rate limits](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt)。

## 卸载

在本仓库文件夹运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

脚本会退出用量条、移除启动快捷方式，并删除当前用户安装的文件。

## 从源码运行或构建

需要 Windows、Python 3.10 或更新版本，以及可用的 Codex CLI。

```powershell
python -m pip install -r .\requirements.txt
python .\app.py
```

生成单文件 `.exe`：

```powershell
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name CodexQuotaFloat .\app.py
```

构建结果位于 `dist\CodexQuotaFloat.exe`。第三方依赖许可见 [`licenses`](licenses)。

## 常见问题

**没有显示用量条？** 先确认桌面宠物正在显示，且未选中 Mini。程序只在检测到宠物图像时显示，不再单独浮在桌面其他位置。

**显示 `--` 或读取失败？** 确认 Codex 已登录且本机 CLI 可用，然后右键点击用量条手动刷新。若 Codex 更新后改变了 App Server 或宠物窗口结构，程序可能需要适配。

**倒计时与百分比为何不同？** 百分比表示窗口内剩余用量；倒计时表示该窗口何时重置，两者是独立信息。
