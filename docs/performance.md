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
