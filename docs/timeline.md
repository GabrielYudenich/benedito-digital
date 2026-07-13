# Timeline multipista

Abra `Editar > Timeline multipista` ou pressione `Ctrl+Shift+T`.

- adicione vídeos e áudios em trilhas separadas;
- mova e apare clipes sem modificar a fonte;
- divida clipes em qualquer ponto interno;
- sobreponha clipes e crie crossfades;
- anime posição, escala, rotação, opacidade e volume com keyframes;
- renderize H.264 e AAC com porcentagem e cancelamento.

A timeline fica em `metadata/timeline.json`, formato aberto e versionado. Cada gravação
também cria uma operação `timeline.edit` com o arquivo exato no armazenamento de objetos.

Keyframes aceitam interpolação linear, suave ou em degrau. Posição, escala, rotação e
volume são avaliados durante o render. Opacidade estática e fades de transição também são
aplicados. Clipes de áudio são misturados no tempo correto da timeline.

## Scopes

Use `Exibir > Scopes de cor` ou `Ctrl+Shift+S` para abrir histograma RGB, waveform de
luminância e vectorscope do frame efetivo da branch. Os scopes mostram também faixa média
de luma e percentuais de preto ou branco recortados.
