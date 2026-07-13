# Benedito Digital

[![Testes](https://github.com/GabrielYudenich/benedito-digital/actions/workflows/tests.yml/badge.svg?branch=develop)](https://github.com/GabrielYudenich/benedito-digital/actions/workflows/tests.yml)
[![Licença Apache 2.0](https://img.shields.io/badge/licen%C3%A7a-Apache%202.0-blue.svg)](LICENSE)
[![Status: pré-lançamento](https://img.shields.io/badge/status-pr%C3%A9--lan%C3%A7amento-orange.svg)](ROADMAP.md)

Software brasileiro, aberto e gratuito para restauração e edição de mídias.

O Benedito Digital trabalha localmente: vídeos, frames, modelos e resultados permanecem
no computador do usuário. Nenhum servidor é obrigatório para criar, editar ou recuperar
um projeto.

## Estado atual

> [!WARNING]
> O Benedito Digital ainda é um **pré-lançamento em desenvolvimento ativo**. Trabalhe
> sempre com cópias e backups verificáveis de materiais insubstituíveis. Ainda não há
> uma versão estável recomendada para produção.

A branch `develop` concentra a validação da próxima versão. A fundação atual inclui:

- importação transacional de originais grandes, com SHA-256, progresso e cancelamento;
- registro de projetos existentes em qualquer pasta local ou compartilhada, sem copiar a mídia;
- extração de frames em PNG sem perda por FFmpeg;
- fila de tarefas em segundo plano sem bloquear a interface;
- processamento retomável em chunks com checkpoints;
- branches locais que não duplicam o vídeo original;
- merge local com comparação lado a lado e mapa de diferenças por frame;
- histórico de pinceladas, máscaras, transformações e resets por frame;
- clone e healing no canvas, limitáveis por seleção e auditáveis por branch;
- armazenamento deduplicado de artefatos por conteúdo;
- restauração e filtros por intervalo com progresso real;
- detecção e alinhamento de película pelas perfurações laterais;
- colaboração incremental por pasta compartilhada com `push` e `pull`, sem portas abertas;
- timeline multipista com cortes, transições, áudio e keyframes;
- histograma RGB, waveform de luminância e vectorscope;
- preferências de contraste, foco, escala e movimento reduzido.

Guias: [película](docs/film-restoration.md), [colaboração](docs/collaboration.md),
[timeline e scopes](docs/timeline.md), [acessibilidade](docs/accessibility.md) e
[projetos grandes](docs/performance.md).

### Limitações conhecidas

- o instalador local de desenvolvimento ainda não possui assinatura digital pública;
- os fluxos precisam de validação adicional com acervos reais extensos e diferentes bitolas;
- o formato de projeto pode receber migrações antes da primeira versão estável;
- modelos opcionais exigem pesos obtidos legalmente pelo próprio usuário;
- colaboração simultânea usa sincronização por operações, não edição concorrente do mesmo frame.

## Interface acolhedora

- modo Guiado, Intermediário ou Avançado na criação do projeto;
- assistente de restauração em cinco etapas;
- Central de Progresso com porcentagem, etapa atual, tempo decorrido e estimativa;
- cancelamento seguro e opção para continuar trabalhando em segundo plano;
- preparação visual da extração com FPS detectado e quantidade estimada de frames;
- gerenciador visual de branches e histórico por frame;
- escala de leitura de 90% a 150%.

## Executar

Requisitos principais:

- Python 3.11 ou compatível;
- FFmpeg e FFprobe no `PATH`, em `vendor/ffmpeg/bin` ou no pacote Windows;
- dependências de `requirements.txt`.

No PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_gui.py
```

Colaboração pela linha de comando:

```powershell
python benedito_cli.py remote-init D:\EquipeBenedito
python benedito_cli.py push "D:\Projetos\Rolo 1" D:\EquipeBenedito --branch limpeza
python benedito_cli.py pull "D:\Projetos\Rolo 1" D:\EquipeBenedito --branch limpeza
```

No MSI, use os mesmos comandos através de `benedito.exe`.

## Testes

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

Consulte [a estratégia de testes](docs/testing.md) e [a arquitetura](docs/architecture.md).

## Formato aberto

O material original é imutável. Edições são representadas por operações e artefatos
endereçados por SHA-256, permitindo histórico local e sincronização futura sem enviar
novamente todo o material. Consulte [o formato de projeto](docs/project-format.md).

Para continuar um projeto armazenado em outro disco, NAS ou pasta sincronizada, use
**Importar Projeto**. O Benedito apenas registra o caminho e abre o workspace no local;
nenhum vídeo ou conjunto de frames é duplicado.

## Modelos de IA

O carregador usa adaptadores internos e somente os arquivos mínimos em `models/architectures`.
Os dois pesos U-Net Dust distribuídos sob MIT acompanham a aplicação para detecção local;
pesos opcionais de SwinIR e Restormer são importados pelo usuário com SHA-256 registrado.
Consulte [os avisos de terceiros](models/THIRD_PARTY_NOTICES.md) para créditos e licenças.

## Licença

O código do Benedito Digital é distribuído sob a licença Apache 2.0. Modelos, pesos e
componentes externos podem possuir licenças próprias e serão documentados separadamente.

## Participar

- leia [como contribuir](CONTRIBUTING.md) antes de abrir um pull request;
- consulte o [roadmap](ROADMAP.md) e o [changelog](CHANGELOG.md);
- mantenedores podem seguir o [checklist do GitHub](docs/github-maintenance.md);
- dúvidas de uso estão em [SUPPORT.md](SUPPORT.md);
- vulnerabilidades devem seguir [SECURITY.md](SECURITY.md), sem issue pública.

## Windows

O build padrão executa os testes, baixa e verifica o FFmpeg LGPL fixado, gera a pasta do aplicativo com PyInstaller e cria um MSI por usuário sem exigir WiX ou privilégios de administrador:

```powershell
pip install -r requirements-build.txt
.\scripts\build_windows.ps1 -Version 1.1.0
```

Os artefatos ficam em `dist/BeneditoDigital` e `dist/BeneditoDigital-1.1.0-x64.msi`. O download do FFmpeg é validado por SHA-256 conforme `packaging/ffmpeg-lock.json`; os binários gerados em `vendor/ffmpeg` não são commitados. Consulte [o guia de release Windows](docs/windows-release.md) para validação, assinatura e atualização de versão.
