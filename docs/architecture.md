# Arquitetura

O Benedito Digital mantém a interface em Python/Tkinter e delega mídia para FFmpeg, OpenCV
e modelos locais. O objetivo é preservar responsividade sem carregar filmes inteiros na memória.

## Camadas

- `src/core`: contratos independentes da GUI, operações, colaboração, análise e utilitários;
- `src/lib/modules/project`: workspace, armazenamento e estado persistente;
- `src/lib/modules/frame`: máscaras e restauração por frame;
- `src/lib/modules/video`: renderização e integração FFmpeg;
- `src/gui/controllers`: coordenação entre diálogos, jobs e domínio;
- `src/gui/dialogs`: fluxos visuais focados e canceláveis;
- `src/gui/screens`: composição das telas principais;
- `models`: registro, adaptadores mínimos, pesos redistribuíveis e avisos de terceiros.

## Invariantes

1. O original importado é imutável e identificado por SHA-256.
2. Uma edição gera operação auditável; artefatos são endereçados pelo conteúdo.
3. Branches e remotes não duplicam automaticamente a mídia original.
4. Operações longas são executadas fora da thread da interface.
5. Checkpoints permitem retomar sem listas proporcionais ao tamanho do filme.
6. Pacotes e manifests externos são validados antes de alterar o workspace.

## Persistência e colaboração

O formato está descrito em `docs/project-format.md`. A colaboração em pasta usa objetos
imutáveis e operações incrementais sob `.benedito-remote`, com lock atômico e sem servidor.
O vídeo original deve ser disponibilizado separadamente pela equipe e validado pelo hash.

## Evolução

Antes da primeira versão estável, mudanças de esquema devem incluir migração, teste de
compatibilidade e documentação. Código de domínio novo deve permanecer testável sem Tkinter.
