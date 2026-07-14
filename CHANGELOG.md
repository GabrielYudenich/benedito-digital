# Changelog

As mudanças relevantes deste projeto serão registradas aqui. O formato segue
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento seguirá
[Semantic Versioning](https://semver.org/lang/pt-BR/) a partir da primeira versão estável.

## [Unreleased]

### Adicionado

- workspace versionado com branches, histórico, merge visual e originais imutáveis;
- processamento retomável por chunks, fila em segundo plano, progresso e cancelamento;
- seleções, clone, healing, máscaras, filtros por intervalo e análise de danos;
- detecção de perfurações e alinhamento de película;
- colaboração incremental segura por pasta com CLI `push` e `pull`;
- timeline multipista com áudio, transições, keyframes e render FFmpeg;
- histograma RGB, waveform, vectorscope e preferências de acessibilidade;
- registro compacto de modelos e pesos U-Net Dust com créditos e hashes;
- build MSI, validação de release, manifesto de atualização e workflows GitHub Actions;
- migração versionada de workspaces e estados visuais antigos;
- recuperação automática de JSON e checkpoints após gravação interrompida, com backup e quarentena;
- importação guiada do filme inteiro ou de trecho lossless FFV1 com intervalo exato;
- estimativa e preflight de espaço livre para importação e sequências PNG.
- árvore de mídia por fonte com proxies e frames paginados;
- player de referência com áudio opcional por FFplay.
- formatos de trecho selecionáveis: MKV/FFV1, MOV/ProRes 422 HQ e MP4/H.264;
- análise de canais e centralização opcional de áudio presente somente em um lado.
- dropdowns escuros com contraste consistente no campo e na lista de opções;
- catálogo lateral não bloqueante, paginado e com cache gerado em segundo plano;
- zoom ancorado no cursor, pan com botão direito e render somente do viewport visível;
- visualização duplicada para um segundo monitor;
- ícones nas ferramentas de seleção, pintura, borracha, clone e healing.
- intervalos reutilizáveis por posicionamento de câmera, com detecção automática de cortes;
- placa limpa para câmera estática, com fundo mediano e proteção de foreground;
- menu de sujeira automática com detecção, correção, ocultação e remoção por frame.
- visão geral colorida para trecho ativo, posicionamentos, avisos e frame atual;
- reprodução silenciosa dos frames em ambos os sentidos, de `0.25x` a `4x`;
- recorte espacial reutilizável em todo o segmento de uma placa limpa.
- catálogo lateral paginado em lista ou miniaturas, com busca por número e filtro de estado;
- avisos coloridos no catálogo e na visão geral para cada estado de revisão do frame;
- painel destacável de revisão com observação, navegação e atalho `Shift+S`.

### Alterado

- repositórios completos de modelos foram substituídos por adaptadores mínimos e avisos;
- projetos grandes passam a usar proxies, chunks, checkpoints e deduplicação;
- versão interna elevada para `1.1.0` como candidata de pré-lançamento.
- frames de fontes diferentes passam a usar diretórios separados.
- pincel e borracha passam a interpolar o traço, respeitar o raio e salvar apenas ao soltar;
- miniaturas deixam a área inferior e passam ao catálogo lateral, preservando o canvas;
- trechos digitados ou definidos por `I` e `O` passam a ficar ativos sem botão de confirmação;
- cenas/câmeras passam a se chamar posicionamentos de câmera, com detecção mais sensível à composição;
- placas limpas passam a continuar sobre a derivação estabilizada quando ela estiver ativa.

### Segurança

- importação colaborativa valida hashes, caminhos, identidade do projeto e cadeia de operações;
- atualizações aceitam somente manifesto HTTPS e checksum antes de qualquer ação do usuário.

Não existe release estável publicada no momento.
