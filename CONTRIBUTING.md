# Como contribuir

Obrigado por ajudar o Benedito Digital a acolher pessoas com diferentes experiências
na preservação audiovisual. O projeto ainda está em pré-lançamento e aceita correções,
documentação, testes de usabilidade e implementações pequenas e verificáveis.

## Antes de começar

1. Procure uma issue existente ou abra uma proposta curta.
2. Use `develop` como base para mudanças em desenvolvimento.
3. Crie uma branch descritiva, como `feat/alinhamento-16mm` ou `fix/progresso-exportacao`.
4. Não inclua filmes, frames de acervos, projetos pessoais, segredos ou credenciais.
5. Não adicione modelos, pesos ou código de terceiros sem licença e proveniência documentadas.
6. Não adicione arquivos maiores que 20 MiB; use uma proposta para definir distribuição externa.

## Ambiente local

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_gui.py
```

Para ferramentas de build e empacotamento:

```powershell
pip install -r requirements-build.txt
```

## Qualidade

Antes do pull request, execute:

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe scripts\check_repository_hygiene.py
.\venv\Scripts\python.exe -m compileall -q run_gui.py benedito_cli.py src scripts
git diff --check
```

Mudanças visuais devem explicar o fluxo testado, incluindo progresso, cancelamento,
uso por teclado e comportamento para projetos grandes. Correções devem incluir teste de
regressão quando houver uma camada de testes adequada.

## Commits e pull requests

Use mensagens objetivas, preferencialmente no formato:

- `feat: adiciona alinhamento por perfurações`
- `fix: preserva áudio durante exportação`
- `docs: documenta colaboração por pasta`
- `test: cobre retomada de chunks`
- `build: prepara instalador Windows`

O pull request deve informar motivação, alterações, validação executada, riscos e imagens
quando a interface mudar. Mantenha cada PR focado; não corrija assuntos não relacionados.

## Princípios técnicos

- o original é imutável;
- operações editáveis são reproduzíveis e auditáveis;
- mídia pesada não pertence ao Git;
- tarefas longas exibem progresso e permitem cancelamento seguro;
- colaboração não abre portas nem envia originais automaticamente;
- recursos básicos continuam acessíveis sem GPU ou modelo de IA.

Consulte `docs/architecture.md`, `docs/project-format.md` e `ROADMAP.md` antes de alterar
formatos persistentes ou contratos de colaboração.
