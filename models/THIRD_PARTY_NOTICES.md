# Modelos e componentes de terceiros

O Benedito Digital incorpora somente os dois pesos U-Net Dust já distribuídos sob MIT no projeto de origem. Os demais pesos são importados pelo usuário, que deve observar a licença e a finalidade de cada modelo.

## Arquiteturas compatíveis

| Família | Uso no Benedito | Licença | Autoria / fonte |
|---|---|---|---|
| SwinIR | redução de ruído e super-resolução | Apache-2.0 | Jingyun Liang e colaboradores — <https://github.com/JingyunLiang/SwinIR> |
| Restormer | redução de ruído e desfoque | MIT | Syed Waqas Zamir e colaboradores — <https://github.com/swz30/Restormer> |
| PyTorch U-Net Dust | máscara de poeira | MIT | Joris van Vugt, 2018 — <https://github.com/jvanvugt/pytorch-unet> |

As licenças originais permanecem junto às cópias compactas em models/architectures. O Benedito não incorpora os repositórios completos e não carrega automaticamente arquiteturas fora dessa estrutura.

## Pesos

Os pesos U-Net incluídos possuem origem, tamanho e SHA-256 em models/weights/unet_dust/manifest.json.

Pesos podem ter termos diferentes do código da arquitetura. O catálogo visual mostra review-upstream quando a licença ainda precisa ser confirmada. Um peso com licença desconhecida não deve ser redistribuído com o programa.

## Estrutura compacta

    models/
      architectures/
        swinir/network_swinir.py
        restormer/restormer_arch.py
        unet_dust/unet.py
      weights/
        unet_dust/*.pth

## FFmpeg no instalador Windows

O instalador Windows pode incluir um build compartilhado LGPL do FFmpeg e do FFprobe, produzido pelo projeto BtbN/FFmpeg-Builds: <https://github.com/BtbN/FFmpeg-Builds>. Esses executáveis são processos separados e permanecem sob a LGPL 2.1 ou posterior.

A versão, o pacote imutável, o SHA-256, o commit do sistema de build e o commit do FFmpeg ficam registrados em packaging/ffmpeg-lock.json. O script scripts/prepare_ffmpeg.ps1 verifica o pacote antes de utilizá-lo e copia a licença original para o instalador.
