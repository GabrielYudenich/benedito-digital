# Benedito Digital — Tutorial Rápido

> [!WARNING]
> Este tutorial acompanha uma versão de pré-lançamento. Preserve o material original,
> mantenha backups verificados e teste o fluxo com uma cópia antes de trabalhar no acervo.

Este guia explica o fluxo principal para restaurar vídeos com qualidade profissional.

**1. Criar projeto**
1. Abra o app e clique em `Criar Projeto`.
2. Defina nome, autor e descrição.
3. Abra o projeto recém-criado.

**2. Importar vídeo**
1. Na aba `Mídia`, clique em `+` e selecione o arquivo.
2. Escolha filme inteiro ou informe início e final do trecho antes da análise.
3. Para um trecho, escolha o formato de trabalho: `MKV sem perdas` é recomendado para
   preservação, `MOV ProRes` prioriza compatibilidade de edição e `MP4` ocupa menos espaço.
4. Revise a análise de áudio. Se um canal estiver silencioso, o Benedito recomenda
   duplicar o canal ativo nos dois lados; a origem permanece intocada.
5. Confirme a importação e, se desejar, crie o proxy leve.
6. Selecione a fonte na árvore e use `▶` para reproduzir. Marque ou desmarque
   `Reproduzir áudio` abaixo do player.
7. O vídeo e o proxy são referências. A restauração acontece nos frames.

**3. Extrair frames**
1. Expanda a fonte em `Mídia > Frames` e clique em `Extrair frames sem perda`, ou use
   o botão `Frames` no cabeçalho da árvore.
2. Mantenha `FPS = Original` para preservar a cadência do material.
3. Revise duração, resolução, quantidade estimada e espaço em disco.
4. Acompanhe porcentagem, etapa e tempo restante na Central de Progresso.
5. Ao concluir, expanda as páginas de 100 frames na árvore para abrir um quadro específico.

**4. Navegar e inspecionar frames**
1. Use `Ctrl + roda do mouse` para ampliar a região sob o cursor.
2. Segure o botão direito e arraste para mover o frame ampliado.
3. Use `Ajustar` para voltar à imagem inteira.
4. Use `Ocultar miniaturas`, ao lado da navegação de problemas, para maximizar a área
   de restauração sem perder as marcações do frame.
5. Use `Segunda tela` para duplicar o frame em uma janela independente, movê-la para
   outro monitor e alternar tela cheia com `F11`.
6. A barra `Navegar por todos os frames` muda o frame atual. A barra `Deslocar
   miniaturas` move apenas a faixa de imagens.
7. Altere as miniaturas com `🔍 − Menores` e `🔍 + Maiores`; não existe mais uma barra
   de zoom sem identificação.
8. Em `Revisão sem áudio`, escolha de `0.25x` a `4x`. Use `◀` para revisar voltando,
   `■` para pausar e `▶` para avançar pelo trecho de trabalho.

**4. Navegar e editar frames**
1. Vá para a aba `Frames`.
2. Use as setas do teclado para navegar.
3. Use `I` para início de intervalo e `O` para fim.
4. Edite com `Pincel` e `Borracha`; o controle `Brush` altera o raio real do traço.
5. Em `Clone` ou `Healing`, clique com o botão direito para definir a fonte azul.
6. Arraste com o botão esquerdo sobre a sujeira; uma seleção ativa limita o retoque.
7. `Clone` copia a textura exatamente; `Healing` adapta luminosidade e cor ao destino.
8. Cada traço, Undo e Redo permanece registrado na branch sem alterar o original.
9. Em `Auto sujeira`, primeiro detecte os pontos amarelos e depois escolha
   `Corrigir pontos detectados`. Também é possível ocultar ou apagar a detecção do frame.

**5. Separar cenas e construir uma placa limpa**
1. Digite o primeiro e o último frame em `Trecho de trabalho` — por exemplo, `61` e
   `817` — e clique em `Aplicar trecho`. Também é possível usar `I = atual` e `O = atual`.
2. A visão geral mostra o trecho ativo em roxo, o frame atual em branco e segmentos
   salvos em cores. Abra `Cenas/câmeras` e salve o intervalo como `Câmera 1`.
3. Salve o intervalo atual ou use a detecção automática de cortes. Ao escolher um
   segmento, estabilização, filtros, restauração e placa limpa passam a usar esse trecho.
4. No gerenciador de cenas, use `Estabilizar câmera` para aplicar estabilização automática
   somente ao segmento selecionado.
5. Para limitar a placa a uma parte do cenário, escolha `Retângulo` ou `Laço` no frame
   representativo, marque o fundo e depois use `Criar placa limpa`.
6. Ative `Usar a seleção atual como recorte em todo o trecho`. O mesmo recorte será
   reutilizado nos frames do segmento, sem depender de uma seleção separada em cada frame.
7. O Benedito alinha amostras, calcula um fundo mediano e mede se a câmera realmente
   permaneceu estática antes de alterar qualquer frame.
8. A aplicação usa somente sujeiras pequenas no fundo estável. Rostos, braços e outros
   movimentos grandes são protegidos e permanecem no frame original.
9. Se a câmera se mover além do limite seguro, a placa é preservada para inspeção, mas
   não é aplicada automaticamente. Estabilize ou reduza o segmento e tente novamente.

**6. Restaurar**
1. Ajuste o `Preset Global` e o `Perfil`.
2. Selecione o modelo em `Modelo ML` (DnCNN, SwinIR, Restormer).
3. Clique em `Restaurar frame atual` ou `Restaurar intervalo`.

**7. Upscale (Super-Resolution)**
1. Escolha o engine (`RRDB` ou `SwinIR SR`).
2. Selecione o peso e a escala (`x2` ou `x4`).
3. Execute `Upscale frame atual` ou `Upscale intervalo`.
4. Use `Ver upscale` para comparar.

**8. Preview e render**
1. Clique em `Preview` para gerar um trecho.
2. Clique em `Renderizar vídeo restaurado` para exportar.

**9. Gerenciar modelos**
1. Na tela inicial, abra `Configurações`.
2. Use o `Gerenciador de Modelos` para adicionar ou remover pesos custom.
3. No editor, também existe o botão `Adicionar peso (.pth)` para facilitar.

**10. Película e perfurações**
1. Selecione o intervalo na aba de frames.
2. Abra `Fluxos > Analisar danos nos frames` para criar marcações.
3. Use `Fluxos > Alinhar película pelas perfurações` para corrigir o registro.
4. Frames sem confiança suficiente permanecem intactos para revisão humana.

**11. Trabalhar em equipe**
1. Abra `Versionamento > Colaboração da equipe`.
2. Escolha uma pasta local, NAS ou sincronizada.
3. Use `Push` para publicar a branch ativa e `Pull` para trazer a branch do colega.
4. Compare e faça o merge pelo gerenciador visual de branches.

**12. Timeline e scopes**
1. Abra `Editar > Timeline multipista` para adicionar, cortar, mover e sobrepor clipes.
2. Selecione um clipe e use `Keyframes` para animar propriedades.
3. Use `Exibir > Scopes de cor` para histograma, waveform e vectorscope.
4. Renderize a timeline e acompanhe a Central de Progresso.

**Atalhos úteis**
1. `←` e `→` navegam frames.
2. `↑` vai para o primeiro frame.
3. `↓` vai para o último frame.
4. `I` define início do intervalo.
5. `O` define fim do intervalo.
6. `Ctrl + Scroll` dá zoom in/out.
7. `Ctrl + Shift + T` abre a timeline.
8. `Ctrl + Shift + C` abre a colaboração.
9. `Ctrl + Shift + S` abre os scopes.

**Dicas**
1. Use `Cinema` como preset padrão para equilíbrio.
2. Use `Nitro` quando quiser máxima qualidade.
3. O cache de miniaturas é persistente por projeto para acelerar a timeline.
4. Use FPS personalizado somente quando houver uma necessidade técnica específica.
5. Ocultar a Central de Progresso não interrompe a tarefa; o botão `Ver tarefa` a abre novamente.
