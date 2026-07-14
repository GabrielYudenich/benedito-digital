# Formato de projeto do Benedito Digital

O formato de projeto e aberto e funciona sem servidor. O material original nunca e
alterado pelo historico de edicao.

## Estrutura versionada

```text
projeto/
├── metadata/
│   ├── project.json
│   └── workspace.json
├── media/
│   ├── originals/
│   └── proxies/
├── frames/
│   └── originals/
│       └── <fonte-id>/
│           └── frame_000001.png
├── history/
│   └── operations/
├── objects/
│   └── sha256/
├── worktrees/
│   ├── principal/
│   └── nome-da-branch/
├── cache/
│   ├── jobs/
│   └── thumbnails/
└── exports/
    ├── previews/
    └── renders/
```

- `project.json` mantem os metadados existentes e a compatibilidade com projetos antigos.
- `workspace.json` registra branches, ponteiros de historico e originais conhecidos.
- `workspace.json.bak` preserva a ultima versao confirmada antes de cada gravacao.
- `history/operations` guarda uma operacao imutavel por arquivo JSON.
- `objects/sha256` guarda mascaras, tiles e outros artefatos sem duplicacao.
- `media/originals` guarda materiais imutaveis e `media/proxies` as copias leves.
- `frames/originals/<fonte-id>` guarda separadamente a sequência sem perda de cada fonte.
- `worktrees` materializa somente os arquivos necessarios para cada branch.
- `cache/jobs` registra checkpoints e `cache/thumbnails` conteudo recriavel.
- `exports` separa previews e renders finais do material de trabalho.

## Branches

Todo workspace comeca na branch `principal`. Uma nova branch aponta inicialmente para
o mesmo cabecalho da branch de origem e passa a divergir somente quando recebe uma
nova operacao. Criar uma branch nao copia videos nem frames.

## Projetos em outras pastas

A tela inicial pode registrar um workspace que esteja fora da pasta padrao de projetos,
inclusive em outro disco, unidade de rede ou pasta sincronizada. O registro local fica em
`.external-projects.json` dentro da pasta padrao e contem somente referencias de caminho.
O projeto e aberto e alterado no proprio local, sem copiar videos, frames ou objetos.
Referencias que deixarem de existir sao removidas automaticamente da lista.

## Operacoes

Uma operacao descreve uma alteracao editavel e pode referenciar artefatos com os pixels
exatos do resultado. Exemplos incluem `brush.stroke`, `frame.transform`, `frame.patch`
e `frame.reset`.

Cada operacao registra:

- identificador unico e operacao anterior;
- branch de origem e data em UTC;
- tipo, frame e parametros editaveis;
- artefatos identificados por SHA-256.

`frame.reset` nao apaga arquivos. Ele adiciona ao historico uma instrucao para voltar
ao frame original, mantendo a acao reversivel.

Pinceladas registram pontos, ferramenta, raio e valor da mascara. Ao final do traco, a
mascara PNG exata tambem e armazenada como objeto, preservando edicao e reproducao fiel.

Segmentos de cena e posicao de camera ficam em `metadata/camera_segments.json`, separados
por fonte. Eles guardam nome, primeiro frame, ultimo frame e confianca da sugestao. O arquivo
e pequeno e pode ser compartilhado sem copiar a sequencia de imagens.

Placas limpas ficam no worktree da branch em `clean_plates/<id>/`. Cada placa possui o fundo
mediano e a mascara das regioes estaveis. As operacoes `clean_plate.build` e
`clean_plate.apply` registram intervalo, diagnosticos, protecao de foreground e hashes dos
frames realmente modificados. `auto_dust.repair` registra a mascara automatica e o frame
resultante; limpar os pontos visuais nao altera o original.

## Processamento em chunks

Filtros e restauracoes por intervalo sao divididos em chunks de frames. Cada chunk so e
marcado como concluido depois que todos os seus frames e artefatos foram salvos. Uma
tarefa interrompida reutiliza os chunks confirmados e recomeca apenas o chunk incompleto.
Os checkpoints tambem mantem uma copia `.bak`; se o JSON principal ficar incompleto,
o Benedito recupera o ultimo chunk confirmado e preserva o arquivo corrompido.

## Versoes e recuperacao

O `workspace.json` usa `schema_version` independente da versao do aplicativo. O schema
atual e `2`. Projetos no schema `1` sao migrados automaticamente, com registro em
`schema_migrations`, sem reescrever operacoes, objetos ou originais.

Toda gravacao persistente e feita em arquivo temporario, sincronizada no disco e entao
substituida atomicamente. Se houver queda de energia entre essas etapas, a abertura tenta,
nesta ordem, o arquivo principal, uma copia temporaria completa e o backup anterior. O
arquivo principal invalido recebe o sufixo `.corrupt-<data>` e nao e apagado.

Schemas criados por uma versao futura nao sao rebaixados. O projeto permanece intacto e
precisa ser aberto por uma versao compativel do Benedito Digital.

## Originais

Um original registrado recebe SHA-256, tamanho e caminho. O arquivo nao e copiado para
o armazenamento de objetos. A verificacao posterior detecta substituicao ou corrupcao
do material de origem.

Um trecho passa a ser um original de trabalho independente e recebe `provenance` com nome
e tamanho da fonte, data de modificacao, inicio, final, container, codecs, formato de
trabalho e tratamento de audio. A fonte de 30 GB nao entra no historico nem no pacote
colaborativo. O formato recomendado usa MKV, FFV1 e PCM para evitar uma nova perda antes da
edicao frame a frame. MOV/ProRes e MP4/H.264 permanecem opcoes explicitas de compatibilidade.

O campo `audio_mode` registra `preserve`, `dual_mono_left`, `dual_mono_right` ou `mono_mix`.
Assim, a centralizacao de uma gravacao presente em apenas um canal e auditavel e nunca
altera silenciosamente o material de origem.

## Sincronizacao e merge local

Pacotes `.bdpack` transferem operacoes e objetos ausentes sem incluir o material
original. Na importacao, o Benedito verifica hashes dos originais, identificadores,
cadeia de pais, head, frames e objetos declarados antes de criar a branch.

A branch recebida permanece separada. Alteracoes em frames diferentes sao reaplicadas
automaticamente por referencia aos mesmos objetos SHA-256. Se os dois lados alteraram
o mesmo frame, a interface exige uma escolha explicita entre manter a versao atual ou
usar a recebida. O comparador mostra os dois resultados efetivos e um painel de diferenca
realcada antes da escolha. As decisoes geram operacoes `merge.replay` e `branch.merge`, mantendo
ambos os historicos auditaveis sem Git, nuvem ou porta de rede.

## Remote incremental

Uma pasta de equipe contém `.benedito-remote`, com snapshots por projeto e branch,
operações imutáveis e objetos deduplicados. `push` copia somente conteúdo ausente. `pull`
monta um pacote temporário apenas com objetos que o workspace ainda não possui e reutiliza
a mesma validação segura de `.bdpack`. Originais nunca entram no remote.
