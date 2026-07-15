# Política de segurança

## Versões suportadas

Ainda não existe uma versão estável suportada para produção. A branch `develop` recebe
correções durante o pré-lançamento; a branch `main` representa apenas marcos revisados.

## Relatar uma vulnerabilidade

Não abra uma issue pública com detalhes exploráveis, caminhos locais, mídias privadas ou
credenciais. Use o recurso **Report a vulnerability** na aba Security do repositório:

<https://github.com/GabrielYudenich/benedito-digital/security/advisories/new>

Inclua versão ou commit, sistema operacional, impacto, passos mínimos para reprodução e,
se possível, uma sugestão de mitigação. Remova dados pessoais e materiais de acervo.

O projeto fará triagem em melhor esforço e combinará a divulgação depois que houver uma
correção ou mitigação. Não há programa de recompensa financeira neste momento.

## Escopo sensível

Pacotes `.bdpack`, manifests de atualização, arquivos de projeto, pesos importados,
comandos FFmpeg e pastas remotas devem ser tratados como entradas não confiáveis. O Benedito
não deve abrir portas, executar arquivos baixados ou enviar mídia sem ação explícita.
