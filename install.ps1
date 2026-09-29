$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'CodexQuotaFloat.exe'
$watchSource = Join-Path $PSScriptRoot 'watchdog.ps1'
$installDir = Join-Path $env:LOCALAPPDATA 'CodexQuotaFloat'
$target = Join-Path $installDir 'CodexQuotaFloat.exe'
$watchTarget = Join-Path $installDir 'watchdog.ps1'
$watchPidFile = Join-Path $installDir 'watchdog.pid'
$startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\CodexQuotaFloat.lnk'

if (-not (Test-Path -LiteralPath $source) -or -not (Test-Path -LiteralPath $watchSource)) {
    throw '安装文件不完整，请从完整交付文件夹运行 install.ps1。'
}

if (Test-Path -LiteralPath $watchPidFile) {
    try { $watchId = [int](Get-Content -LiteralPath $watchPidFile -Raw) } catch { $watchId = 0 }
    if ($watchId -gt 0) {
        $watchProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $watchId" -ErrorAction SilentlyContinue
        if ($watchProcess -and $watchProcess.CommandLine -and
            $watchProcess.CommandLine.IndexOf($watchTarget, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            Stop-Process -Id $watchId -Force
            Wait-Process -Id $watchId -Timeout 5 -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $watchPidFile -Force -ErrorAction SilentlyContinue
}

Get-Process CodexQuotaFloat -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $target } |
    Stop-Process -Force

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        Copy-Item -LiteralPath $source -Destination $target -Force
        break
    } catch {
        if ($attempt -eq 19) { throw }
        Start-Sleep -Milliseconds 250
    }
}
Copy-Item -LiteralPath $watchSource -Destination $watchTarget -Force
Remove-Item -LiteralPath (Join-Path $installDir 'position.json') -Force -ErrorAction SilentlyContinue

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($startup)
$shortcut.TargetPath = Join-Path $PSHOME 'powershell.exe'
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchTarget`""
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = '打开 Codex 时显示宠物用量条'
$shortcut.Save()

Start-Process -FilePath $shortcut.TargetPath -ArgumentList $shortcut.Arguments -WindowStyle Hidden
for ($attempt = 0; $attempt -lt 20 -and -not (Test-Path -LiteralPath $watchPidFile); $attempt++) {
    Start-Sleep -Milliseconds 200
}
if (-not (Test-Path -LiteralPath $watchPidFile)) {
    throw '用量条后台监视器未能启动。'
}
Write-Host "已安装并启动：$target"
Write-Host '后台监视器已运行；Codex 再次打开时会自动恢复用量条。'
