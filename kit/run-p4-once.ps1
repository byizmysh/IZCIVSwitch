# run-p4-once.ps1 -- one P4 attempt: restore save -> start engine -> send bridge -> wait -> summarize.
# Usage (run from this kit directory):
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\run-p4-once.ps1 -ConsoleIp <S2-IP> -PcIp <PC-IP> [-SkipRestore] [-FirmwareDump]
#
# Standard cycle (see README.md §6):
#   1) loader online -> run WITHOUT -SkipRestore (rewrites trigger save)
#   2) hard power-cycle the console, Load Game, back to Awaiting payload
#   3) run WITH -SkipRestore  (and -FirmwareDump if you want the system dump)
param(
  [Parameter(Mandatory = $true)][string]$ConsoleIp,
  [Parameter(Mandatory = $true)][string]$PcIp,
  [string]$Backup = '',
  [switch]$SkipRestore,
  [switch]$FirmwareDump
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$port = Join-Path $root 'port'
$send = Join-Path $root 'save-tools\send_js.py'
$restore = Join-Path $root 'save-tools\restore_save.py'
$bridge = Join-Path $port 'civ_bridge.js'
if (-not $Backup) { $Backup = Join-Path $root 'save-tools\trigger-recreate' }

$node = (Get-Command node -ErrorAction Stop).Source
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction Stop).Source }

# make sure the bridge knows where to dial out
$bridgeText = Get-Content $bridge -Raw
if ($bridgeText -match "'<PC_IP>'") {
  throw "civ_bridge.js PC_IP not set yet -- run: .\set-pc-ip.ps1 -PcIp $PcIp"
}

Write-Output '=== 1/3 restore save ==='
if ($SkipRestore) {
  Write-Output '(skipped: -SkipRestore)'
} else {
  & $python -u $restore $Backup $ConsoleIp 2>&1 | Select-Object -Last 3
}

Write-Output '=== 2/3 start engine ==='
if ($FirmwareDump) {
  $env:NS2_FIRMWARE_DUMP_DIR = Join-Path $port 'engine\dumps'
  Write-Output "(firmware dump dir: $env:NS2_FIRMWARE_DUMP_DIR)"
  $engineArgs = @('engine\run.cjs', '--dump-firmware', $PcIp)
} else {
  $engineArgs = @('engine\run.cjs', $PcIp)
}
$outLog = Join-Path $env:TEMP ('p4-engine-out-' + [guid]::NewGuid().ToString('N') + '.log')
$errLog = Join-Path $env:TEMP ('p4-engine-err-' + [guid]::NewGuid().ToString('N') + '.log')
$engine = Start-Process -FilePath $node -ArgumentList $engineArgs -WorkingDirectory $port `
  -PassThru -NoNewWindow -RedirectStandardOutput $outLog -RedirectStandardError $errLog

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 250
  if ((Test-Path $outLog) -and (Select-String -Path $outLog -Pattern 'Run folder:' -Quiet -ErrorAction SilentlyContinue)) { break }
  if ($engine.HasExited) { break }
}
Get-Content $outLog -ErrorAction SilentlyContinue | Select-Object -Last 3

Write-Output '=== 3/3 send bridge ==='
& $python -u $send $ConsoleIp $bridge 2>&1 | Select-Object -Last 3

Write-Output '=== engine waiting ==='
$engine.WaitForExit()
Write-Output ('engine exit=' + $engine.ExitCode)
Get-Content $outLog -ErrorAction SilentlyContinue | Select-Object -Last 12
$errText = Get-Content $errLog -ErrorAction SilentlyContinue
if ($errText) { Write-Output '--- stderr ---'; $errText | Select-Object -Last 6 }

Write-Output '=== summary ==='
$run = (Get-Content $outLog -ErrorAction SilentlyContinue | Select-String -Pattern 'Run folder: (.+)$' | Select-Object -Last 1)
if ($run) {
  $runDir = $run.Matches[0].Groups[1].Value.Trim()
  Write-Output ('run=' + $runDir)
  $res = Join-Path $runDir 'result.json'
  if (Test-Path $res) {
    $r = Get-Content $res -Raw | ConvertFrom-Json
    Write-Output ('verified=' + $r.verified + ' error=' + $r.error)
  }
  $pipe = Join-Path $runDir 'switch2\pipeline.json'
  if (Test-Path $pipe) {
    $p = Get-Content $pipe -Raw | ConvertFrom-Json
    foreach ($s in $p.stages) { Write-Output ('stage ' + $s.name + ' : ' + $s.status) }
  }
}
