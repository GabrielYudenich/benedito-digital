# Manutenção do GitHub

Este checklist prepara o repositório sem apresentar o pré-lançamento como versão estável.

## Metadados recomendados

- descrição: `Restauração audiovisual local, aberta e acessível — Seu Benedito dá um jeito!`;
- website: deixar vazio até existir uma página oficial mantida;
- tópicos: `video-restoration`, `film-restoration`, `vhs`, `ffmpeg`, `opencv`, `python`,
  `tkinter`, `digital-preservation`, `accessibility`, `open-source`;
- manter Issues e Security Advisories habilitados;
- habilitar Discussions apenas quando houver capacidade para moderação comunitária.

## Branches

- `main`: marcos revisados e documentação apresentada ao público;
- `develop`: integração do próximo pré-lançamento;
- branches curtas: correções e funcionalidades enviadas por pull request.

Em `main`, exigir pull request, conversa resolvida e o check `windows-tests`. Em `develop`,
exigir o mesmo check e bloquear force push depois da primeira publicação. Administradores
podem manter bypass somente para recuperação documentada.

## Segurança e dependências

- manter secret scanning e push protection habilitados;
- habilitar private vulnerability reporting;
- habilitar Dependabot security updates;
- revisar permissões do GitHub Actions e usar `contents: read` por padrão;
- nunca colocar certificados, tokens ou mídias em Secrets de ambiente não necessário.

## Assinatura Windows

O workflow de release aceita os Secrets:

- `WINDOWS_CERTIFICATE_BASE64`: certificado PFX codificado em Base64;
- `WINDOWS_CERTIFICATE_PASSWORD`: senha do PFX.

Use certificado de assinatura de código emitido para o mantenedor ou organização. Não use
certificado improvisado para simular confiança pública. Restrinja os Secrets ao ambiente de
release e revise logs antes de publicar o MSI.

## Publicação

1. Enviar `develop` e aguardar o workflow de testes.
2. Abrir um draft pull request para `main`, mantendo a marca de pré-lançamento.
3. Resolver a auditoria e os testes de campo do `ROADMAP.md`.
4. Atualizar `CHANGELOG.md`, versão, manifesto e documentação.
5. Criar uma tag `vX.Y.Z` apenas para uma versão intencionalmente publicável.
6. Conferir assinatura, SHA-256, instalação, abertura, CLI e desinstalação do MSI.
7. Publicar como **pre-release** até que os critérios da primeira versão estável sejam cumpridos.

Não envie o MSI pelo Git. O workflow deve anexá-lo ao GitHub Release.
