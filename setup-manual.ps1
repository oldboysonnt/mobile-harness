# setup-manual.ps1 - 1-click: moi truong pentest THU CONG san sang (khong AI).
# Buoc nao loi se IN LOI va chay TIEP buoc sau (fail-soft) - doc bang trang thai.
#
# Cach dung (chuot phai > Run with PowerShell, hoac tu terminal):
#   .\setup-manual.ps1                            # chi environment
#   .\setup-manual.ps1 -Apk C:\apps\target.apk    # + cai app, jadx, manifest, index
#   .\setup-manual.ps1 -Apk x.apk -Package com.foo.bar
#   .\setup-manual.ps1 -Serial <adb-serial>       # dung may vat ly (can root san)
#   them -NoPause neu go tu terminal khong muon dung cuoi
param(
    [string]$Apk = "",
    [string]$Package = "",
    [string]$Serial = "",
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Find-Python {
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { return , @($c.Source) }
    $p = Get-Command py -ErrorAction SilentlyContinue
    if ($p) { return , @($p.Source, "-3") }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "[FAIL] Khong thay python - cai Python 3.12 roi chay lai." -ForegroundColor Red
    if (-not $NoPause) { Read-Host "Nhan Enter de thoat" }
    exit 1
}

$pyExe = $py[0]
$pyExtra = @()
if ($py.Length -gt 1) { $pyExtra = @($py[1..($py.Length - 1)]) }

$mphArgs = @("-m", "mph", "setup", "manual")
if ($Apk)     { $mphArgs += @("--apk", $Apk) }
if ($Package) { $mphArgs += @("--package", $Package) }
if ($Serial)  { $mphArgs += @("--serial", $Serial) }

Write-Host "== mph setup manual: $($mphArgs -join ' ')" -ForegroundColor Cyan
& $pyExe ($pyExtra + $mphArgs)
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
    Write-Host "=> TAT CA SAN SANG - bat dau pentest thu cong (xem CHEATSHEET.md)." -ForegroundColor Green
} else {
    Write-Host "=> MOT SO BUOC FAIL (xem bang [FAIL] o tren) - cac buoc khac van san sang." -ForegroundColor Yellow
    Write-Host "   Thiet ke 1 click: hien loi roi chay TIEP buoc sau." -ForegroundColor Yellow
}
if (-not $NoPause) { Read-Host "Nhan Enter de dong cua so" }
exit $code
