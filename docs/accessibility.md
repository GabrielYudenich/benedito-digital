# Acessibilidade

Em `Ajuda > Leitura e acessibilidade`, escolha escala de 90% a 150%, contraste elevado,
movimento reduzido e foco reforçado. As preferências ficam nos metadados do projeto.

Em `Propriedades > Configurar atalhos`, cada usuário pode redefinir as ações principais,
remover uma combinação deixando o campo vazio e restaurar os padrões. Conflitos são
rejeitados antes de salvar. As preferências ficam em `%LOCALAPPDATA%\Benedito Digital\shortcuts.json`
no Windows e não alteram nem são compartilhadas com o projeto.

Caps Lock e Num Lock são ignorados ao comparar atalhos. Assim, letras como `I`, `O` e
`Shift+S` funcionam da mesma maneira independentemente do estado dessas teclas, sem afetar
a digitação dentro de campos de texto.

Controles interativos participam da navegação por `Tab` e `Shift+Tab`. As setas navegam
frames somente quando o foco não está em um campo de texto, evitando perda de posição ao
editar números ou nomes.

Os atalhos `1` e `2` da escolha de importação também são ignorados enquanto o foco está
nos campos de minutagem. Assim, digitar `00:10:40` nunca troca a opção selecionada.

Atalhos principais:

- `←` e `→`: frame anterior e seguinte;
- `I` e `O`: início e fim do intervalo;
- `Ctrl+Z` e `Ctrl+Y`: desfazer e refazer;
- `Ctrl+Shift+T`: timeline;
- `Ctrl+Shift+C`: colaboração;
- `Ctrl+Shift+S`: scopes;
- `Shift+S`: revisão e estado do frame;
- `F8`: segunda tela;
- `Ctrl+Alt+P`: placa limpa;
- `Ctrl+Alt+S`: estabilização do trecho ativo;
- `F1`: ajuda.

As cores textuais principais são verificadas automaticamente contra contraste WCAG. Uma
avaliação humana com Narrador do Windows e diferentes ampliações continua recomendada.
