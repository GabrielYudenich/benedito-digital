# Restauração de película

## Análise

Em `Fluxos > Analisar danos nos frames`, o Benedito procura poeira, riscos, manchas,
frames vazios, duplicações e alterações nas perfurações laterais. O relatório fica no
worktree da branch e apenas sugere marcações; nenhuma imagem é alterada automaticamente.

## Registro por perfurações

Use `Fluxos > Alinhar película pelas perfurações` depois de selecionar um intervalo.
O modo recomendado mantém o primeiro frame como referência. O modo progressivo usa o
frame anterior já alinhado e acompanha variações lentas do transporte.

Frames com confiança insuficiente são preservados sem alteração. Cada alinhamento aceito
gera uma operação `film.perforation_registration` contendo deslocamento, confiança,
quantidade de correspondências e o resultado exato identificado por SHA-256.

O método corrige translação. Rotação, escala ou deformações graves devem ser revisadas
manualmente ou tratadas pela estabilização automática.
