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
- build MSI, validação de release, manifesto de atualização e workflows GitHub Actions.

### Alterado

- repositórios completos de modelos foram substituídos por adaptadores mínimos e avisos;
- projetos grandes passam a usar proxies, chunks, checkpoints e deduplicação;
- versão interna elevada para `1.1.0` como candidata de pré-lançamento.

### Segurança

- importação colaborativa valida hashes, caminhos, identidade do projeto e cadeia de operações;
- atualizações aceitam somente manifesto HTTPS e checksum antes de qualquer ação do usuário.

Não existe release estável publicada no momento.
