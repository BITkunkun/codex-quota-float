$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot 'CodexQuotaFloat.exe'
$pidFile = Join-Path $PSScriptRoot 'watchdog.pid'
$mutex = [System.Threading.Mutex]::new($false, 'Local\CodexQuotaFloatWatch')
$ownsMutex = $false
try {
    try {
        $ownsMutex = $mutex.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
        $ownsMutex = $true
    }
    if (-not $ownsMutex) { return }
    Set-Content -LiteralPath $pidFile -Value $PID -Encoding Ascii

    while (Test-Path -LiteralPath $exe) {
        try {
            $codex = Get-Process ChatGPT -ErrorAction SilentlyContinue |
                Where-Object { $_.Path -like '*\OpenAI.Codex_*\app\ChatGPT.exe' } |
                Select-Object -First 1
            $overlay = Get-Process CodexQuotaFloat -ErrorAction SilentlyContinue |
                Where-Object { $_.Path -eq $exe } |
                Select-Object -First 1
            if ($codex -and -not $overlay) {
                Start-Process -FilePath $exe
                Start-Sleep -Seconds 5
            }
        } catch {
            # The next poll retries if Codex is still running.
        }
        Start-Sleep -Seconds 2
    }
} finally {
    if ($ownsMutex) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
