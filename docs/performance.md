# Desempenho e projetos grandes

Originais são copiados e calculados em streaming, proxies usam FFmpeg e restaurações por
intervalo são retomáveis. O checkpoint v2 guarda apenas o prefixo confirmado, mantendo
tamanho constante mesmo em projetos com centenas de milhares de frames.

Execute o ensaio sintético sem criar mídia pesada:

```powershell
.\venv\Scripts\python.exe scripts\stress_large_project.py --frames 250000 --chunk-size 5000
```

O comando mede duração, pico de memória, tamanho do checkpoint e frames por segundo. Ele
falha se ultrapassar o limite configurado. Esse ensaio valida o orquestrador; para release,
também teste um material real longo, pois desempenho de codec, disco e GPU depende da máquina.

## Primeiro teste com um filme grande

Ao selecionar um vídeo, o Benedito pergunta o que será importado antes de iniciar qualquer
análise. No modo de trecho, início e final ficam na própria janela inicial. A leitura dos
metadados começa somente depois da confirmação e leva a uma segunda tela de revisão:

- **Filme inteiro** copia e verifica o arquivo completo em streaming;
- **Somente um trecho** recebe início e final em `HH:MM:SS` antes da análise e cria um
  MKV lossless;
- ambos mostram dados estimados, espaço livre e reserva de segurança antes de começar.

Proxy e frames são etapas diferentes. O proxy é pequeno e serve ao player de referência;
os PNGs sem perda podem ocupar muito mais espaço e, por segurança, só são gerados após uma
confirmação própria. A árvore `Mídia` mostra `Frames (0)` e a ação de extração enquanto a
sequência não existe. Depois, mostra páginas de 100 quadros sem criar milhares de linhas de
interface ao mesmo tempo.

O trecho usa FFV1 intraframe e áudio PCM. Ele não adiciona uma compressão destrutiva antes
da restauração, mas pode ser maior que um vídeo de entrega comum. A origem recebe registro
de proveniência com nome, tamanho, data, intervalo e codecs usados.

Para o primeiro ensaio com um `.mov` de 30 GB:

1. trabalhe com uma cópia ou backup verificado do material insubstituível;
2. escolha inicialmente um trecho representativo de 30 a 120 segundos;
3. confira a estimativa conservadora de espaço para o trecho e para os PNGs;
4. extraia os frames e restaure poucos quadros antes de ampliar o intervalo;
5. cancele pela janela de progresso se precisar interromper; arquivos parciais do trecho
   são removidos automaticamente.

Importação, hashing, FFmpeg e extração trabalham em streaming. O arquivo de 30 GB não é
carregado inteiro na memória. A velocidade ainda depende do codec, do disco e da resolução.
