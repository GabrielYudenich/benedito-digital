# Release Windows

O Benedito Digital usa PyInstaller em modo `onedir` e gera um MSI por usuário. A instalação padrão fica em `%LOCALAPPDATA%\Benedito Digital`, cria um atalho no Menu Iniciar e não precisa de privilégios administrativos.

## Requisitos

- Windows 10 ou 11 x64;
- Python x64 3.11 ou 3.12;
- ambiente `venv` com `requirements.txt` e `requirements-build.txt` instalados;
- internet no primeiro preparo do FFmpeg;
- espaço livre para aproximadamente 3 GB entre downloads, build, distribuição e arquivos temporários.

O gerador MSI nativo usa `msilib`, removido do Python 3.13. O modo alternativo `-MsiEngine wix` permanece disponível para uma migração futura ao WiX.

## Build completo

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-build.txt
.\scripts\build_windows.ps1 -Version 1.1.0
```

O script:

1. executa a suíte de testes;
2. chama `scripts/prepare_ffmpeg.ps1` quando os binários ainda não existem;
3. valida o SHA-256 do arquivo fixado em `packaging/ffmpeg-lock.json`;
4. gera `dist/BeneditoDigital` com PyInstaller;
5. gera `dist/BeneditoDigital-<versão>-x64.msi` com o Windows Installer.

Opções úteis:

```powershell
.\scripts\build_windows.ps1 -Version 1.0.1 -SkipTests
.\scripts\build_windows.ps1 -Version 1.0.1 -SkipMsi
.\scripts\build_windows.ps1 -Version 1.0.1 -MsiEngine wix
```

## Verificação

```powershell
.\scripts\verify_windows_release.ps1 -MsiPath .\dist\BeneditoDigital-1.1.0-x64.msi
```

O verificador realiza uma extração administrativa pelo `msiexec`, confere GUI,
`benedito.exe`, FFmpeg, licença e proveniência, executa `benedito.exe --help` e mantém a
GUI aberta durante um smoke test curto. Use `-RequireSignature` nas releases assinadas.

Antes de publicar, também deve ser feito um ciclo manual em uma máquina Windows limpa:

- instalar pelo MSI;
- abrir pelo Menu Iniciar;
- criar um projeto e importar um vídeo curto;
- gerar proxy e extrair frames observando o progresso;
- exportar H.264 com áudio;
- desinstalar e confirmar a remoção do atalho.

## FFmpeg e licenças

O pacote Windows usa o build compartilhado LGPL da BtbN. A versão, URL imutável, checksum, commit do build e commit do FFmpeg estão em `packaging/ffmpeg-lock.json`. A licença e `provenance.json` são incorporados em `_internal/licenses/ffmpeg`.

Para atualizar o FFmpeg, altere o lockfile somente após confirmar os dados na release original e execute:

```powershell
.\scripts\prepare_ffmpeg.ps1 -Force
```

Nunca substitua o arquivo por uma URL `latest` mutável. As arquiteturas compactas e os dois
pesos U-Net Dust sob MIT acompanham o instalador. Pesos opcionais de SwinIR e Restormer
permanecem fora do pacote e são importados localmente pelo usuário.

## Versões e atualização

Use versões MSI com até três partes numéricas, por exemplo `1.2.0`. O `UpgradeCode` é estável e o `ProductCode` muda deterministicamente por versão. Um MSI mais novo detecta e remove a versão anterior, preservando uma única instalação registrada.

## Assinatura

Os artefatos locais não são assinados. A automação `.github/workflows/release.yml` assina
primeiro os dois executáveis, monta o MSI com esses binários e então assina o MSI. Configure
os segredos `WINDOWS_CERTIFICATE_BASE64` e `WINDOWS_CERTIFICATE_PASSWORD`.

```powershell
.\scripts\sign_windows_release.ps1 -CertificatePath certificado.pfx -CertificatePassword $env:CERT_PASSWORD
```

O certificado e suas senhas nunca devem entrar no repositório. Depois da assinatura, publique também o SHA-256 do MSI.
