$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'CodexQuotaFloat.exe'
$installDir = Join-Path $env:LOCALAPPDATA 'CodexQuotaFloat'
$target = Join-Path $installDir 'CodexQuotaFloat.exe'
$startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\CodexQuotaFloat.lnk'

if (-not (Test-Path -LiteralPath $source)) {
    throw '未找到 CodexQuotaFloat.exe，请从完整交付文件夹运行 install.ps1。'
}

Get-Process CodexQuotaFloat -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $target } |
    Stop-Process -Force

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $target -Force

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($startup)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = '打开 Codex 时显示用量悬浮窗'
$shortcut.Save()

Start-Process -FilePath $target
Write-Host "已安装并启动：$target"
Write-Host '下次登录 Windows 后会自动在后台等待 Codex 打开。'
