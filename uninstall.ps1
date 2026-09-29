$ErrorActionPreference = 'Stop'
$installDir = Join-Path $env:LOCALAPPDATA 'CodexQuotaFloat'
$target = Join-Path $installDir 'CodexQuotaFloat.exe'
$startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\CodexQuotaFloat.lnk'

Get-Process CodexQuotaFloat -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $target } |
    Stop-Process -Force

Remove-Item -LiteralPath $startup -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $installDir 'position.json') -Force -ErrorAction SilentlyContinue
if (Test-Path -LiteralPath $installDir) {
    Remove-Item -LiteralPath $installDir -ErrorAction SilentlyContinue
}
Write-Host '已卸载 Codex 额度悬浮窗。'
