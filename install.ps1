$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'CodexQuotaFloat.exe'
$watchSource = Join-Path $PSScriptRoot 'watchdog.ps1'
$installDir = Join-Path $env:USERPROFILE 'CodexQuotaFloat'
$target = Join-Path $installDir 'CodexQuotaFloat.exe'
$watchTarget = Join-Path $installDir 'watchdog.ps1'
$watchPidFile = Join-Path $installDir 'watchdog.pid'
$taskName = 'CodexQuotaFloatWatch'
$oldInstallDir = Join-Path $env:LOCALAPPDATA 'CodexQuotaFloat'
$startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\CodexQuotaFloat.lnk'

if (-not (Test-Path -LiteralPath $source) -or -not (Test-Path -LiteralPath $watchSource)) {
    throw '安装文件不完整，请从完整交付文件夹运行 install.ps1。'
}

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) { Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue }

foreach ($dir in @($installDir, $oldInstallDir)) {
    $pidFile = Join-Path $dir 'watchdog.pid'
    $script = Join-Path $dir 'watchdog.ps1'
    if (Test-Path -LiteralPath $pidFile) {
        try { $watchId = [int](Get-Content -LiteralPath $pidFile -Raw) } catch { $watchId = 0 }
        if ($watchId -gt 0) {
            $watchProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $watchId" -ErrorAction SilentlyContinue
            if ($watchProcess -and $watchProcess.CommandLine -and
                $watchProcess.CommandLine.IndexOf($script, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                Stop-Process -Id $watchId -Force
                Wait-Process -Id $watchId -Timeout 5 -ErrorAction SilentlyContinue
            }
        }
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
    $exe = Join-Path $dir 'CodexQuotaFloat.exe'
    Get-Process CodexQuotaFloat -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $exe } |
        Stop-Process -Force
}

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
Remove-Item -LiteralPath $startup -Force -ErrorAction SilentlyContinue

$powerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction -Execute $powerShell -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchTarget`""
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

for ($attempt = 0; $attempt -lt 30 -and -not (Test-Path -LiteralPath $watchPidFile); $attempt++) {
    Start-Sleep -Milliseconds 200
}
if (-not (Test-Path -LiteralPath $watchPidFile) -or
    (Get-ScheduledTask -TaskName $taskName).State -ne 'Running') {
    throw '用量条后台监视器未能由 Windows 计划任务启动。'
}
Write-Host "已安装并启动：$target"
Write-Host 'Windows 登录后会自动启动监视器；每次打开 Codex 时，用量条会随宠物出现。'
