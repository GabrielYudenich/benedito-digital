param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$LockPath = Join-Path $RepoRoot "packaging\ffmpeg-lock.json"
$DownloadRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot "downloads\ffmpeg"))
$VendorRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot "vendor\ffmpeg"))
$StageRoot = [IO.Path]::GetFullPath((Join-Path $DownloadRoot "stage"))

function Assert-WorkspaceChild([string]$Path) {
    $prefix = $RepoRoot.TrimEnd('\') + '\'
    if (-not $Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Caminho fora do projeto recusado: $Path"
    }
}

Assert-WorkspaceChild $DownloadRoot
Assert-WorkspaceChild $VendorRoot
Assert-WorkspaceChild $StageRoot

if (-not (Test-Path -LiteralPath $LockPath)) {
    throw "Lockfile do FFmpeg não encontrado: $LockPath"
}
$Lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
$ArchivePath = Join-Path $DownloadRoot $Lock.archive_name
$ExpectedHash = $Lock.archive_sha256.ToLowerInvariant()

New-Item -ItemType Directory -Path $DownloadRoot -Force | Out-Null
if ($Force -or -not (Test-Path -LiteralPath $ArchivePath)) {
    Write-Output "Baixando FFmpeg $($Lock.ffmpeg_version)..."
    Invoke-WebRequest -Uri $Lock.archive_url -OutFile $ArchivePath -UseBasicParsing
}

$ActualHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualHash -ne $ExpectedHash) {
    Remove-Item -LiteralPath $ArchivePath -Force
    throw "Checksum inválido do FFmpeg. Esperado $ExpectedHash; recebido $ActualHash"
}
Write-Output "Checksum SHA-256 confirmado."

Remove-Item -LiteralPath $StageRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $StageRoot -Force
$PackageRoot = Get-ChildItem -LiteralPath $StageRoot -Directory | Select-Object -First 1
if ($null -eq $PackageRoot -or -not (Test-Path -LiteralPath (Join-Path $PackageRoot.FullName "bin\ffmpeg.exe"))) {
    throw "Estrutura inesperada no pacote do FFmpeg"
}

$PreparedRoot = Join-Path $DownloadRoot "prepared"
Remove-Item -LiteralPath $PreparedRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path (Join-Path $PreparedRoot "bin"),(Join-Path $PreparedRoot "legal") -Force | Out-Null
Copy-Item -Path (Join-Path $PackageRoot.FullName "bin\*") -Destination (Join-Path $PreparedRoot "bin") -Force
Get-ChildItem -LiteralPath $PackageRoot.FullName -File | Where-Object {
    $_.Name -match '^(LICENSE|COPYING|README|VERSION)'
} | Copy-Item -Destination (Join-Path $PreparedRoot "legal") -Force

$Manifest = [ordered]@{
    prepared_at_utc = [DateTime]::UtcNow.ToString("o")
    provider = $Lock.provider
    release_tag = $Lock.release_tag
    ffmpeg_version = $Lock.ffmpeg_version
    variant = $Lock.variant
    license = $Lock.license
    archive_url = $Lock.archive_url
    archive_sha256 = $ActualHash
    build_source = $Lock.build_source
    ffmpeg_source = $Lock.ffmpeg_source
    files = @(
        Get-ChildItem -LiteralPath (Join-Path $PreparedRoot "bin") -File | Sort-Object Name | ForEach-Object {
            [ordered]@{
                name = $_.Name
                size = $_.Length
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }
    )
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PreparedRoot "provenance.json") -Encoding UTF8

Remove-Item -LiteralPath $VendorRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path (Split-Path -Parent $VendorRoot) -Force | Out-Null
Move-Item -LiteralPath $PreparedRoot -Destination $VendorRoot
Remove-Item -LiteralPath $StageRoot -Recurse -Force
Write-Output "FFmpeg preparado em $VendorRoot"
