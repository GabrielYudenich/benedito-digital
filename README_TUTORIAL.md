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
7. Se o arquivo de preservação for grande e ainda não possuir proxy, o Benedito oferece
   criar uma cópia leve antes do primeiro play. O original, os frames e o render final
   não usam nem são alterados pelo proxy.
8. O vídeo e o proxy são referências. A restauração acontece nos frames.

**3. Extrair frames**
1. Expanda a fonte em `Mídia > Frames` e clique em `Extrair frames sem perda`, ou use
   o botão `Frames` no cabeçalho da árvore.
2. Mantenha `FPS = Original` para preservar a cadência do material.
3. Revise duração, resolução, quantidade estimada e espaço em disco.
4. Acompanhe porcentagem, etapa e tempo restante na Central de Progresso.
5. Ao concluir, clique em `Frames` no painel lateral. Escolha `Lista` ou `Miniaturas`,
   busque pelo número do frame e navegue pelas páginas sem carregar a sequência inteira.

**4. Navegar e inspecionar frames**
1. Use `Ctrl + roda do mouse` para ampliar a região sob o cursor.
2. Segure o botão direito e arraste para mover o frame ampliado.
3. Use `Ajustar` para voltar à imagem inteira.
4. As miniaturas ficam no painel lateral. Alterne para `Lista` quando quiser reservar
   mais espaço ou localizar frames apenas pelo número e estado.
5. Use `Segunda tela` para abrir uma janela independente em outro monitor. Escolha
   `Original`, `Resultado` ou `Comparar`; no último modo, mova o divisor para inspecionar
   as duas versões no mesmo frame. `F11` alterna a tela cheia.
6. A segunda tela possui frame anterior/seguinte, reprodução, velocidade e áudio em `1x`,
   além dos contadores centralizados de frame interno, tempo do projeto, tempo da fonte e
   tempo do trecho.
7. Ao iniciar a revisão, um buffer curto prepara previews 720p em paralelo. As duas telas
   reutilizam o mesmo cache em vez de decodificar o PNG duas vezes.
8. A barra `Navegar por todos os frames` muda o frame atual. O catálogo lateral acompanha
   o frame e troca de página automaticamente quando necessário.
9. Em `Revisão sem áudio`, escolha de `0.25x` a `4x`. Use `◀` para revisar voltando,
   `■` para pausar e `▶` para avançar pelo trecho de trabalho.

**5. Navegar e editar frames**
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
10. Pressione `Shift+S` ou abra `Editar > Estado do frame > Sinalizar` para registrar
    Poeira, Risco, Mancha, Perfuração, Revisar ou Aprovado com uma observação opcional.
11. O aviso aparece discretamente na visão geral e com sua própria cor no catálogo lateral.
    Use o filtro de estado para revisar somente um tipo de problema.
12. Para retirar frames que não entrarão no trabalho, navegue até o novo início e use
    `Editar > Corte não destrutivo > Definir frame atual como início útil`. Faça o mesmo
    com o final. Os PNGs e o vídeo original permanecem no projeto e o corte pode ser desfeito.
13. Para descartar apenas o resultado do frame aberto, use
    `Versionamento > Resetar frame para o original`.
14. Se estabilização, placa e restauração se misturarem, use
    `Versionamento > Resetar todos os resultados para os frames originais...`. O reset remove
    somente derivações e checkpoints da branch; vídeo, PNGs extraídos, proxy e placas salvas
    permanecem intactos.

**6. Separar posicionamentos e construir uma placa limpa**
1. Digite o primeiro e o último frame em `Trecho de trabalho` — por exemplo, `61` e
   `817`. O trecho fica ativo imediatamente; também é possível usar `I = atual` e `O = atual`.
2. A visão geral mostra o trecho ativo em roxo, o frame atual em branco, avisos em cores e
   posicionamentos salvos. Abra `Posicionamentos` e salve o intervalo como `Posição 1`.
3. Salve o intervalo atual ou use a detecção automática em sensibilidade Detalhada,
   Equilibrada ou Conservadora. Ao escolher um posicionamento, estabilização, filtros,
   restauração e placa limpa passam a usar esse trecho.
4. No gerenciador, use `Estabilizar posicionamento` para aplicar estabilização automática
   somente ao intervalo selecionado.
5. Se o resultado de apenas um posicionamento der errado, selecione-o e use
   `Resetar resultado`. Somente as derivações daquele intervalo serão descartadas; outros
   posicionamentos, frames extraídos e placas salvas permanecem intactos.
6. Antes de iniciar estabilização ou placa limpa, confirme obrigatoriamente se a operação
   vale para um posicionamento salvo, para o trecho atual ou para o filme inteiro no corte útil.
7. Ao concluir, escolha `Pré-renderizar` no mesmo gerenciador para gerar e abrir um MP4
   curto do posicionamento estabilizado antes do render final.
8. Para limitar a placa a uma parte do cenário, escolha `Retângulo` ou `Laço` no frame
   representativo, marque o fundo e depois use `Criar placa limpa`.
9. Abra `Restauração > Criar placa limpa do trecho` — a função também continua disponível
   no gerenciador de posicionamentos.
10. Ative `Usar a seleção atual como recorte em todo o trecho`. O mesmo recorte será
   reutilizado nos frames do segmento, sem depender de uma seleção separada em cada frame.
11. Escolha o primeiro frame do trecho, o frame atualmente aberto ou a amostra mais nítida
    como base visual. A mediana temporal identifica o que é fundo, mas não desfoca a placa.
12. Use `Reconstruir todo o fundo estático` para um resultado visível, ou o modo conservador
    para corrigir somente poeira e riscos. O Benedito cria uma placa RGBA: rostos, braços e
    movimentos detectados ficam transparentes e são protegidos novamente em cada frame.
13. Se a câmera se mover além do limite seguro, a placa é preservada para inspeção, mas
   não é aplicada automaticamente. Estabilize ou reduza o segmento e tente novamente.
14. Abra o botão `Placas limpas` ou `Restauração > Gerenciar e editar placas limpas` para
    visualizar a imagem gerada, seu caminho, intervalo e quantos frames foram alterados.
15. Em `Editar placa`, pinte poeira ou riscos e use `Remover ruído marcado`. Clone e Healing
    usam o botão direito para definir a origem e o botão esquerdo para aplicar o retoque.
16. Use `Tornar transparente` para retirar pessoas, objetos ou áreas inseguras da placa. O
    quadriculado mostra o alpha removido. `Manter como fundo` devolve uma área à placa.
17. Ao salvar, confirme `Sim` quando o Benedito perguntar se deve reaplicar. A placa e o alpha
    são definições; a layer antiga é desativada imediatamente e os composites só voltam a ser
    usados depois da reaplicação. A imagem original fica preservada em `plate_original.png`.
18. A aplicação cria uma camada não destrutiva, sem sobrescrever o frame original ou a
    estabilização. Se algum movimento ficar escondido, navegue até o frame, abra `Placas limpas`
    e escolha `Corrigir movimento no frame atual...`.
19. Também é possível abrir diretamente `Restauração > Corrigir camada da placa no frame atual`.
    Pinte com `Revelar frame original` sobre a pessoa ou objeto apagado.
    Use `Restaurar camada da placa` para desfazer partes da revelação e salve a correção.
20. Placas criadas antes deste fluxo aparecem como antigas no gerenciador. Use `Recriar placa`
    para repetir exatamente o intervalo com a nova base nítida e a máscara suavizada.

**7. Restaurar**
1. Abra `Propriedades > Abrir propriedades avançadas` para ajustar o `Preset Global` e
   o `Perfil` sem reduzir a área principal do frame.
2. Selecione o modelo em `Modelo ML` (DnCNN, SwinIR, Restormer).
3. Clique em `Restaurar frame atual` ou `Restaurar intervalo`.

**8. Upscale (Super-Resolution)**
1. Escolha o engine (`RRDB` ou `SwinIR SR`).
2. Selecione o peso e a escala (`x2` ou `x4`).
3. Execute `Upscale frame atual` ou `Upscale intervalo`.
4. Use `Ver upscale` para comparar.

**9. Preview e render**
1. Use `Restauração > Pré-renderizar trecho ativo` para gerar um MP4 do intervalo útil.
2. Use `Restauração > Renderizar resultado final` para exportar.
3. Na segunda tela, ative `Gravar contadores no render` somente quando desejar incorporar
   frame e timecodes visivelmente no arquivo final.

**10. Gerenciar modelos**
1. Na tela inicial, abra `Configurações`.
2. Use o `Gerenciador de Modelos` para adicionar ou remover pesos custom.
3. No editor, também existe o botão `Adicionar peso (.pth)` para facilitar.

**11. Película e perfurações**
1. Selecione o intervalo na aba de frames.
2. Abra `Fluxos > Analisar danos nos frames` para criar marcações.
3. Use `Fluxos > Alinhar película pelas perfurações` para corrigir o registro.
4. Frames sem confiança suficiente permanecem intactos para revisão humana.

**12. Trabalhar em equipe**
1. Abra `Versionamento > Colaboração da equipe`.
2. Escolha uma pasta local, NAS ou sincronizada.
3. Use `Push` para publicar a branch ativa e `Pull` para trazer a branch do colega.
4. Compare e faça o merge pelo gerenciador visual de branches.

**13. Timeline e scopes**
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
10. `Shift + S` abre o painel de revisão e estado do frame.
11. `Ctrl + Alt + P` abre a placa limpa e `Ctrl + Alt + S` estabiliza o trecho.
12. `F8` abre a segunda tela.
13. Abra `Propriedades > Configurar atalhos` para trocar ou remover qualquer atalho listado;
    as escolhas são pessoais e valem para todos os projetos desse usuário.

**Dicas**
1. Use `Cinema` como preset padrão para equilíbrio.
2. Use `Nitro` quando quiser máxima qualidade.
3. O cache de miniaturas é persistente por projeto para acelerar o catálogo lateral.
4. Use FPS personalizado somente quando houver uma necessidade técnica específica.
5. Ocultar a Central de Progresso não interrompe a tarefa; o botão `Ver tarefa` a abre novamente.
