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
3. Revise a importação e, se desejar, crie o proxy leve.
4. Selecione a fonte na árvore e use `▶` para reproduzir. Marque ou desmarque
   `Reproduzir áudio` abaixo do player.
5. O vídeo e o proxy são referências. A restauração acontece nos frames.

**3. Extrair frames**
1. Expanda a fonte em `Mídia > Frames` e clique em `Extrair frames sem perda`, ou use
   o botão `Frames` no cabeçalho da árvore.
2. Mantenha `FPS = Original` para preservar a cadência do material.
3. Revise duração, resolução, quantidade estimada e espaço em disco.
4. Acompanhe porcentagem, etapa e tempo restante na Central de Progresso.
5. Ao concluir, expanda as páginas de 100 frames na árvore para abrir um quadro específico.

**4. Navegar e editar frames**
1. Vá para a aba `Frames`.
2. Use as setas do teclado para navegar.
3. Use `I` para início de intervalo e `O` para fim.
4. Edite com o brush e máscara quando necessário.
5. Em `Clone` ou `Healing`, clique com o botão direito para definir a fonte azul.
6. Arraste com o botão esquerdo sobre a sujeira; uma seleção ativa limita o retoque.
7. `Clone` copia a textura exatamente; `Healing` adapta luminosidade e cor ao destino.
8. Cada traço, Undo e Redo permanece registrado na branch sem alterar o original.

**5. Restaurar**
1. Ajuste o `Preset Global` e o `Perfil`.
2. Selecione o modelo em `Modelo ML` (DnCNN, SwinIR, Restormer).
3. Clique em `Restaurar frame atual` ou `Restaurar intervalo`.

**6. Upscale (Super-Resolution)**
1. Escolha o engine (`RRDB` ou `SwinIR SR`).
2. Selecione o peso e a escala (`x2` ou `x4`).
3. Execute `Upscale frame atual` ou `Upscale intervalo`.
4. Use `Ver upscale` para comparar.

**7. Preview e render**
1. Clique em `Preview` para gerar um trecho.
2. Clique em `Renderizar vídeo restaurado` para exportar.

**8. Gerenciar modelos**
1. Na tela inicial, abra `Configurações`.
2. Use o `Gerenciador de Modelos` para adicionar ou remover pesos custom.
3. No editor, também existe o botão `Adicionar peso (.pth)` para facilitar.

**9. Película e perfurações**
1. Selecione o intervalo na aba de frames.
2. Abra `Fluxos > Analisar danos nos frames` para criar marcações.
3. Use `Fluxos > Alinhar película pelas perfurações` para corrigir o registro.
4. Frames sem confiança suficiente permanecem intactos para revisão humana.

**10. Trabalhar em equipe**
1. Abra `Versionamento > Colaboração da equipe`.
2. Escolha uma pasta local, NAS ou sincronizada.
3. Use `Push` para publicar a branch ativa e `Pull` para trazer a branch do colega.
4. Compare e faça o merge pelo gerenciador visual de branches.

**11. Timeline e scopes**
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
