param(
    [Parameter(Mandatory=$true)][string]$CertificatePath,
    [Parameter(Mandatory=$true)][string]$CertificatePassword,
    [string]$MsiPath = "dist\BeneditoDigital-1.1.0-x64.msi",
    [ValidateSet("all", "executable", "msi")][string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$SignTool = (Get-Command signtool.exe -ErrorAction Stop).Source
$Executable = Join-Path $RepoRoot "dist\BeneditoDigital\Benedito Digital.exe"
$CommandLine = Join-Path $RepoRoot "dist\BeneditoDigital\benedito.exe"
$Msi = [IO.Path]::GetFullPath((Join-Path $RepoRoot $MsiPath))
$Targets = if ($Target -eq "executable") { @($Executable, $CommandLine) } elseif ($Target -eq "msi") { @($Msi) } else { @($Executable, $CommandLine, $Msi) }
foreach ($Artifact in $Targets) {
    if (-not (Test-Path -LiteralPath $Artifact -PathType Leaf)) { throw "Artefato não encontrado: $Artifact" }
    & $SignTool sign /f $CertificatePath /p $CertificatePassword /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Artifact
    if ($LASTEXITCODE -ne 0) { throw "Falha ao assinar $Artifact" }
    $Signature = Get-AuthenticodeSignature -LiteralPath $Artifact
    if ($Signature.Status -ne "Valid") { throw "Assinatura inválida em ${Artifact}: $($Signature.Status)" }
}
