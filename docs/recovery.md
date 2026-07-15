# Recuperacao apos falhas

O Benedito Digital separa o historico de restauracao do estado visual da interface. Uma
falha em posicao, zoom ou painel nao apaga operacoes, frames restaurados nem originais.

## Protecoes atuais

- `workspace.json`, estado da interface e checkpoints usam gravacao atomica;
- a versao anterior valida fica em um arquivo `.bak` local;
- arquivos temporarios completos podem concluir uma gravacao interrompida;
- arquivos corrompidos sao preservados com o sufixo `.corrupt-<data>`;
- a interface informa quando recuperou ou migrou um projeto;
- schemas futuros sao bloqueados em vez de sofrer downgrade;
- um estado visual sem copia valida entra em modo protegido e nao e sobrescrito.

## O que fazer depois de uma recuperacao

1. Confirme a branch ativa e os ultimos frames trabalhados.
2. Verifique o original em **Projeto > Verificar original**.
3. Revise o ultimo chunk retomado antes de continuar.
4. Mantenha os arquivos `.corrupt-*` ate concluir o diagnostico e o backup.

## Limites atuais

A recuperacao cobre metadados, estado visual e checkpoints. Exportacoes FFmpeg e copias de
originais ainda precisam de uma politica unificada de espaco livre, diario transacional e
limpeza guiada de resultados parciais antes da primeira versao estavel.
