param(
    [switch]$SkipTests,
    [switch]$SkipMsi,
    [switch]$SkipApp,
    [switch]$AllowExternalFfmpeg,
    [string]$Version = "",
    [ValidateSet("native", "wix")]
    [string]$MsiEngine = "native"
)

$ErrorActionPreference = "Stop"
$BuildMutex = [Threading.Mutex]::new($false, "Local\BeneditoDigitalBuild")
if (-not $BuildMutex.WaitOne(0)) {
    throw "Já existe um build do Benedito Digital em andamento"
}
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ConfiguredVersion = (Get-Content -LiteralPath (Join-Path $RepoRoot "config.json") -Raw | ConvertFrom-Json).version
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $ConfiguredVersion
} elseif ($Version -ne $ConfiguredVersion) {
    throw "A versão solicitada ($Version) difere de config.json ($ConfiguredVersion)"
}
$Python = Join-Path $RepoRoot "venv\Scripts\python.exe"
$VendorBin = Join-Path $RepoRoot "vendor\ffmpeg\bin"
$DistDir = Join-Path $RepoRoot "dist"
$AppDir = Join-Path $DistDir "BeneditoDigital"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Ambiente virtual não encontrado em $Python"
}

if (-not $SkipTests) {
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Os testes falharam" }
}

if (-not $SkipApp) {
    & $Python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Instale requirements-build.txt antes de gerar o aplicativo"
    }
}

$Ffmpeg = Join-Path $VendorBin "ffmpeg.exe"
$Ffprobe = Join-Path $VendorBin "ffprobe.exe"
if ((-not (Test-Path $Ffmpeg) -or -not (Test-Path $Ffprobe)) -and -not $AllowExternalFfmpeg) {
    & (Join-Path $PSScriptRoot "prepare_ffmpeg.ps1")
}

Push-Location $RepoRoot
try {
    if (-not $SkipApp) {
        & $Python -m PyInstaller --noconfirm --clean "packaging\benedito.spec"
        if ($LASTEXITCODE -ne 0) { throw "Falha no PyInstaller" }
    } elseif (-not (Test-Path -LiteralPath (Join-Path $AppDir "Benedito Digital.exe"))) {
        throw "-SkipApp exige uma distribuicao existente em $AppDir"
    }

    if (-not $SkipMsi) {
        if ($MsiEngine -eq "wix") {
            $Wix = Get-Command wix -ErrorAction SilentlyContinue
            if ($null -eq $Wix) {
                throw "WiX Toolset não encontrado. Use -MsiEngine native ou instale o comando wix"
            }
            & wix build "packaging\windows\Package.wxs" -arch x64 -d "ProductVersion=$Version" -bindpath "AppSource=$AppDir" -o "dist\BeneditoDigital-$Version-x64.msi"
        } else {
            & $Python "scripts\build_msi.py" --source $AppDir --output "dist\BeneditoDigital-$Version-x64.msi" --version $Version
        }
        if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o MSI com $MsiEngine" }
    }
} finally {
    Pop-Location
    $BuildMutex.ReleaseMutex()
    $BuildMutex.Dispose()
}

Write-Output "Build concluído em $DistDir"
