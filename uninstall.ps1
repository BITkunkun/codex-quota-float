$ErrorActionPreference = 'Stop'
$installDir = Join-Path $env:USERPROFILE 'CodexQuotaFloat'
$oldInstallDir = Join-Path $env:LOCALAPPDATA 'CodexQuotaFloat'
$taskName = 'CodexQuotaFloatWatch'
$startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\CodexQuotaFloat.lnk'

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

foreach ($dir in @($installDir, $oldInstallDir)) {
    $watchTarget = Join-Path $dir 'watchdog.ps1'
    $watchPidFile = Join-Path $dir 'watchdog.pid'
    $target = Join-Path $dir 'CodexQuotaFloat.exe'
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
    }
    $overlayIds = @(Get-Process CodexQuotaFloat -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $target } |
        Select-Object -ExpandProperty Id)
    if ($overlayIds.Count -gt 0) {
        Stop-Process -Id $overlayIds -Force
        Wait-Process -Id $overlayIds -Timeout 5 -ErrorAction SilentlyContinue
    }
    foreach ($file in @($target, $watchTarget, $watchPidFile, (Join-Path $dir 'position.json'))) {
        for ($attempt = 0; $attempt -lt 20 -and (Test-Path -LiteralPath $file); $attempt++) {
            try {
                Remove-Item -LiteralPath $file -Force -ErrorAction Stop
            } catch {
                if ($attempt -eq 19) { throw }
                Start-Sleep -Milliseconds 250
            }
        }
    }
    if (Test-Path -LiteralPath $dir) { [System.IO.Directory]::Delete($dir) }
}
Remove-Item -LiteralPath $startup -Force -ErrorAction SilentlyContinue
Write-Host '已卸载 Codex 额度悬浮窗。'
