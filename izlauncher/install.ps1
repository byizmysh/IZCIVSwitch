param(
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Args
)
$ErrorActionPreference = 'Stop'
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction Stop).Source }
& $python -u (Join-Path $PSScriptRoot 'install.py') @Args
exit $LASTEXITCODE
