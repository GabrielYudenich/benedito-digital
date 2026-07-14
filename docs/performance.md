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
- **Somente um trecho** recebe início e final em `HH:MM:SS` antes da análise e oferece
  MKV/FFV1 sem perdas, MOV/ProRes 422 HQ ou MP4/H.264 de alta qualidade;
- ambos mostram dados estimados, espaço livre e reserva de segurança antes de começar.

Proxy e frames são etapas diferentes. O proxy é pequeno e serve ao player de referência;
os PNGs sem perda podem ocupar muito mais espaço e, por segurança, só são gerados após uma
confirmação própria. A árvore `Mídia` mostra `Frames (0)` e a ação de extração enquanto a
sequência não existe. Depois, mostra páginas de 100 quadros sem criar milhares de linhas de
interface ao mesmo tempo.

O padrão recomendado usa MKV com FFV1 intraframe e áudio PCM. Ele não adiciona compressão
destrutiva antes da restauração, mas pode ser maior que um vídeo de entrega comum. MOV com
ProRes 422 HQ e PCM oferece ampla compatibilidade profissional, com compressão visualmente
sem perdas. MP4 com H.264 e AAC gera um arquivo menor, porém com perdas, e deve ser usado
como cópia prática ou entrega, não como matriz de preservação.

Durante a análise do trecho, uma amostra dos dois primeiros canais é medida. Se apenas um
lado tiver sinal, a revisão recomenda duplicar esse canal nos dois lados. Também é possível
preservar os canais exatamente como chegaram ou misturá-los ao centro. A escolha afeta
somente a cópia de trabalho e fica registrada na proveniência.

Para o primeiro ensaio com um `.mov` de 30 GB:

1. trabalhe com uma cópia ou backup verificado do material insubstituível;
2. escolha inicialmente um trecho representativo de 30 a 120 segundos;
3. confira a estimativa conservadora de espaço para o trecho e para os PNGs;
4. extraia os frames e restaure poucos quadros antes de ampliar o intervalo;
5. cancele pela janela de progresso se precisar interromper; arquivos parciais do trecho
   são removidos automaticamente.

Importação, hashing, FFmpeg e extração trabalham em streaming. O arquivo de 30 GB não é
carregado inteiro na memória. A velocidade ainda depende do codec, do disco e da resolução.

## Navegação dos frames

O catálogo lateral pagina 40 miniaturas ou 100 itens de lista por vez. Miniaturas ausentes
são geradas em segundo plano, e tamanhos já existentes no cache são reaproveitados antes de
decodificar novamente um PNG grande. Arrastar rapidamente o slider também agrupa eventos
antes de carregar o frame.

O zoom renderiza apenas o viewport visível, em vez de criar uma imagem ampliada gigante na
memória. `Ctrl + roda` ancora o zoom no cursor e botão direito + arrasto move a imagem. O
catálogo lateral pode alternar para lista, e `Segunda tela` abre uma visualização independente
para monitores adicionais. Essa janela escolhe original, resultado ou comparação por divisor
sem duplicar os PNGs. A reprodução reutiliza o cache atual; áudio fica limitado a `1x` para
manter sincronismo e os contadores são calculados a partir do FPS e da proveniência do trecho.

O corte útil em `Editar > Corte não destrutivo` apenas grava os limites utilizados por preview
e render. Frames fora do corte ficam cinza no catálogo, mas não são removidos do disco. Assim,
é possível retirar frames 1–60 de um trabalho sem reconstruir a sequência e restaurá-los depois.

## Posicionamentos e placa limpa

A detecção de posicionamentos lê no máximo cerca de 360 amostras distribuídas pela sequência e
refina somente os cortes candidatos. Ela não carrega todos os frames de um filme longo na
memória. A sensibilidade pode ser Detalhada, Equilibrada ou Conservadora, e os intervalos
salvos podem ser reutilizados por estabilização, filtros e restauração.

A placa limpa usa no máximo 15 amostras do intervalo para construir o fundo mediano. Ao
aplicar, somente o frame atual, os dois vizinhos, a placa e as máscaras ficam na memória.
Objetos grandes que diferem do fundo são tratados como foreground protegido. Por segurança,
uma câmera considerada móvel impede a aplicação automática e mantém os frames intactos.

Quando existe estabilização manual ou automática ativa, a placa usa essa sequência como
entrada e grava o resultado na mesma derivação estabilizada. Uma seleção espacial pode ser
reutilizada como recorte em todo o segmento, evitando centenas de máscaras repetidas.

A reprodução da aba Frames é silenciosa e limitada ao trecho ativo. Ela usa o FPS conhecido
da referência, permite `0.25x`, `0.5x`, `1x`, `2x` e `4x` e pula posições intermediárias se
a decodificação de PNGs grandes não acompanhar o relógio, mantendo a interface responsiva.

Durante o play, quatro workers preparam antecipadamente até 24 previews em no máximo
1280×720. Tela principal e segunda tela compartilham o mesmo par Original/Resultado. No
projeto real de 3.927 PNGs, o benchmark local sustentou 29,0 fps com a comparação aberta
para uma fonte de 29,97 fps. Ao pausar, o editor volta a carregar o frame na resolução total.

Arquivos lossless grandes continuam podendo exigir proxy no player de referência. Na primeira
tentativa de reprodução direta de uma fonte acima de 512 MiB, o Benedito oferece criar o proxy.
Ele serve somente ao preview e nunca entra no render final.
