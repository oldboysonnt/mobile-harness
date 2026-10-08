# setup-manual.ps1 - 1-click: moi truong pentest THU CONG san sang (khong AI).
#
# May TRONG (chi co Windows + internet) van chay duoc: tu pip install packages,
# tu bootstrap AVD (cmdline-tools + system image ~1.5GB) khi thieu device,
# roi chay lai chain. Doctor in checklist thu gi con thieu.
#
# Phai cai san (khong the tu dong hoa):
#   1. Python 3.12+          - python.org/downloads (tick "Add to PATH")
#   2. Java runtime          - cho Burp (adoptium.net)
#   3. Burp Suite Pro + keygen - copy vao C:\Program Files\Burp\bin\
#      (BurpSuitePro\burpsuite_pro.jar + BurpSuitePro\BurpLoaderKeygen.jar)
# Neu dung -Apk: them jadx (jadx path trong mph.toml).
#
# Cach dung (chuot phai > Run with PowerShell, hoac tu terminal):
#   .\setup-manual.ps1                            # chi environment
#   .\setup-manual.ps1 -Apk C:\apps\target.apk    # + cai app, jadx, manifest, index
#   .\setup-manual.ps1 -Apk x.apk -Package com.foo.bar
#   .\setup-manual.ps1 -Serial <adb-serial>       # dung may vat ly (can root san)
#   them -NoPause neu go tu terminal khong muon dung cuoi
#   them -SkipBootstrap de KHONG tu tao AVD khi thieu device
param(
    [string]$Apk = "",
    [string]$Package = "",
    [string]$Serial = "",
    [switch]$SkipBootstrap,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

function Fail-Exit($msg) {
    Write-Host "[FAIL] $msg" -ForegroundColor Red
    if (-not $NoPause) { Read-Host "Nhan Enter de thoat" }
    exit 1
}

# --- buoc 0/3: python ---
function Find-Python {
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { return , @($c.Source) }
    $p = Get-Command py -ErrorAction SilentlyContinue
    if ($p) { return , @($p.Source, "-3") }
    return $null
}

$py = Find-Python
if (-not $py) {
    Fail-Exit "Khong thay python - cai Python 3.12+ tu python.org/downloads (tick 'Add to PATH') roi chay lai."
}
$pyExe = $py[0]
$pyExtra = @()
if ($py.Length -gt 1) { $pyExtra = @($py[1..($py.Length - 1)]) }

# --- buoc 1/3: python packages cua mph (tu pip install khi thieu) ---
Write-Host "== [1/3] kiem tra python packages (mph)" -ForegroundColor Cyan
& $pyExe ($pyExtra + @("-m", "mph", "--help")) *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "   thieu packages - tu cai: pip install -e . (can internet)" -ForegroundColor Yellow
    & $pyExe ($pyExtra + @("-m", "pip", "install", "-e", "."))
    if ($LASTEXITCODE -ne 0) {
        Fail-Exit "pip install -e . that bai - xem loi o tren (kiem tra internet)."
    }
    & $pyExe ($pyExtra + @("-m", "mph", "--help")) *> $null
    if ($LASTEXITCODE -ne 0) {
        Fail-Exit "van khong chay duoc 'python -m mph' sau khi install - bao loi repo."
    }
    Write-Host "   da cai xong packages." -ForegroundColor Green
} else {
    Write-Host "   ok." -ForegroundColor Green
}

# --- buoc 2/3: doctor - checklist moi truong (in, khong chan) ---
Write-Host "== [2/3] checklist moi truong (doctor)" -ForegroundColor Cyan
& $pyExe ($pyExtra + @("-m", "mph", "doctor"))
Write-Host "   (dong FAIL nao o tren = can cai thu cong xem phan dau file; chain van chay tiep)" -ForegroundColor DarkGray

# --- buoc 3/3: chain setup manual (fail-soft) + tu bootstrap khi thieu device ---
$mphArgs = @("-m", "mph", "setup", "manual")
if ($Apk)     { $mphArgs += @("--apk", $Apk) }
if ($Package) { $mphArgs += @("--package", $Package) }
if ($Serial)  { $mphArgs += @("--serial", $Serial) }

function Invoke-ManualChain {
    # stdout vao bien (de nhan dien "khong thay device") va Out-Host de
    # khong bi capture vao return value cua ham; stderr hien thang console
    & $pyExe ($pyExtra + $mphArgs) | Tee-Object -Variable chainOut | Out-Host
    return @{ code = $LASTEXITCODE; out = $chainOut }
}

Write-Host "== [3/3] chay chain setup manual" -ForegroundColor Cyan
Write-Host "   mph $($mphArgs -join ' ')" -ForegroundColor DarkGray
$res = Invoke-ManualChain
$code = $res.code
$out  = $res.out

if ($code -ne 0 -and -not $Serial -and -not $SkipBootstrap -and ($out -match "khong thay device")) {
    Write-Host ""
    Write-Host "== chua co AVD - bootstrap tu dong (lan dau tai system image ~1.5GB, co the rat lau)" -ForegroundColor Yellow
    & $pyExe ($pyExtra + @("-m", "mph", "setup", "run"))
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "== bootstrap OK - chay lai chain setup manual" -ForegroundColor Cyan
        $res = Invoke-ManualChain
        $code = $res.code
    } else {
        Write-Host "[FAIL] bootstrap that bai - xem loi o tren va workspace/logs/emulator.log" -ForegroundColor Red
    }
}

Write-Host ""
if ($code -eq 0) {
    Write-Host "=> TAT CA SAN SANG - bat dau pentest thu cong (xem CHEATSHEET.md)." -ForegroundColor Green
} else {
    Write-Host "=> MOT SO BUOC FAIL (xem bang [FAIL] o tren) - cac buoc khac van san sang." -ForegroundColor Yellow
    Write-Host "   Thiet ke 1 click: hien loi roi chay TIEP buoc sau." -ForegroundColor Yellow
}
if (-not $NoPause) { Read-Host "Nhan Enter de dong cua so" }
exit $code
