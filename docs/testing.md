# Estratégia de testes

## Suíte automatizada

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

A suíte cobre domínio, workspace, colaboração, renderização, modelos, jobs, controladores
e componentes de interface que podem ser exercitados de forma determinística.

## Validação antes de pull request

```powershell
.\venv\Scripts\python.exe -m compileall -q run_gui.py benedito_cli.py src scripts
git diff --check
```

Mudanças de mídia devem começar pelo teste mais específico e depois executar a suíte completa.
Testes que dependem de FFmpeg devem usar arquivos pequenos e verificar streams, duração,
quantidade de frames e preservação de metadados relevantes.

## Interface

Uma alteração visual deve ser verificada com:

- abertura e fechamento real da janela;
- navegação por teclado e foco visível;
- progresso percentual, cancelamento e mensagens de erro;
- escala de interface e alto contraste;
- projeto vazio, mídia ausente e operação interrompida.

## Projetos grandes

O script `scripts/stress_large_project.py` mede a orquestração sem exigir um filme enorme.
Antes da versão estável ainda serão necessários ensaios com mídia real, pouco espaço em disco,
NAS, discos lentos e máquinas com memória limitada.
