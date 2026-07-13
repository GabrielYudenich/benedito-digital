param(
    [string]$MsiPath = "dist\BeneditoDigital-1.1.0-x64.msi",
    [ValidateRange(2, 60)]
    [int]$GuiSmokeSeconds = 8,
    [switch]$RequireSignature,
    [switch]$KeepExtracted
)

$ErrorActionPreference = "Stop"
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ResolvedMsi = if ([IO.Path]::IsPathRooted($MsiPath)) {
    [IO.Path]::GetFullPath($MsiPath)
} else {
    [IO.Path]::GetFullPath((Join-Path $RepoRoot $MsiPath))
}
if (-not (Test-Path -LiteralPath $ResolvedMsi -PathType Leaf)) {
    throw "MSI não encontrado: $ResolvedMsi"
}

$ExtractRoot = [IO.Path]::GetFullPath((Join-Path $env:TEMP ("benedito-msi-verify-" + [Guid]::NewGuid().ToString("N"))))
$TempPrefix = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
if (-not $ExtractRoot.StartsWith($TempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Destino temporário inseguro: $ExtractRoot"
}
$LogPath = Join-Path $env:TEMP "benedito-msi-verify.log"
$GuiProcess = $null

try {
    $Installer = Start-Process msiexec.exe -ArgumentList @(
        '/a',
        ('"' + $ResolvedMsi + '"'),
        '/qn',
        ('TARGETDIR="' + $ExtractRoot + '"'),
        '/l*v',
        ('"' + $LogPath + '"')
    ) -Wait -PassThru
    if ($Installer.ExitCode -ne 0) {
        $Tail = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Tail 80 } else { @() }
        throw "A extração MSI falhou com código $($Installer.ExitCode).`n$($Tail -join "`n")"
    }

    $Application = Get-ChildItem -LiteralPath $ExtractRoot -Recurse -Filter "Benedito Digital.exe" | Select-Object -First 1
    $CommandLine = Get-ChildItem -LiteralPath $ExtractRoot -Recurse -Filter "benedito.exe" | Select-Object -First 1
    $Ffmpeg = Get-ChildItem -LiteralPath $ExtractRoot -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    $License = Get-ChildItem -LiteralPath $ExtractRoot -Recurse -Filter "LICENSE.txt" | Where-Object { $_.FullName -match 'licenses\\ffmpeg' } | Select-Object -First 1
    $Provenance = Get-ChildItem -LiteralPath $ExtractRoot -Recurse -Filter "provenance.json" | Where-Object { $_.FullName -match 'licenses\\ffmpeg' } | Select-Object -First 1
    if ($null -eq $Application -or $null -eq $CommandLine -or $null -eq $Ffmpeg -or $null -eq $License -or $null -eq $Provenance) {
        throw "O MSI não contém todos os executáveis e avisos legais esperados"
    }

    $MsiSignature = Get-AuthenticodeSignature -LiteralPath $ResolvedMsi
    $ExeSignature = Get-AuthenticodeSignature -LiteralPath $Application.FullName
    $CliSignature = Get-AuthenticodeSignature -LiteralPath $CommandLine.FullName
    if ($RequireSignature -and ($MsiSignature.Status -ne "Valid" -or $ExeSignature.Status -ne "Valid" -or $CliSignature.Status -ne "Valid")) {
        throw "Assinatura obrigatoria ausente ou invalida (MSI: $($MsiSignature.Status); EXE: $($ExeSignature.Status); CLI: $($CliSignature.Status))"
    }

    $FfmpegVersion = & $Ffmpeg.FullName -hide_banner -version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "O FFmpeg empacotado não iniciou"
    }

    $CliHelp = & $CommandLine.FullName --help 2>&1
    if ($LASTEXITCODE -ne 0 -or ($CliHelp -join "`n") -notmatch "remote-init") {
        throw "A linha de comando empacotada nao iniciou corretamente"
    }

    $GuiProcess = Start-Process -FilePath $Application.FullName -PassThru
    Start-Sleep -Seconds $GuiSmokeSeconds
    if ($GuiProcess.HasExited) {
        throw "A GUI encerrou prematuramente com código $($GuiProcess.ExitCode)"
    }
    Stop-Process -Id $GuiProcess.Id -Force
    $GuiProcess = $null

    $Files = Get-ChildItem -LiteralPath $ExtractRoot -Recurse -File | Measure-Object Length -Sum
    [ordered]@{
        msi = $ResolvedMsi
        msi_size = (Get-Item -LiteralPath $ResolvedMsi).Length
        msi_sha256 = (Get-FileHash -LiteralPath $ResolvedMsi -Algorithm SHA256).Hash.ToLowerInvariant()
        extracted_files = $Files.Count
        extracted_size = $Files.Sum
        ffmpeg = ($FfmpegVersion | Select-Object -First 1)
        cli = ($CliHelp | Select-Object -First 1)
        gui_smoke_seconds = $GuiSmokeSeconds
        msi_signature = [string]$MsiSignature.Status
        executable_signature = [string]$ExeSignature.Status
        cli_signature = [string]$CliSignature.Status
        valid = $true
    } | ConvertTo-Json
} finally {
    if ($null -ne $GuiProcess -and -not $GuiProcess.HasExited) {
        Stop-Process -Id $GuiProcess.Id -Force
    }
    if (-not $KeepExtracted -and $ExtractRoot.StartsWith($TempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $ExtractRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
