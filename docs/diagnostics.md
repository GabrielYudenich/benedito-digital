# Diagnóstico de desenvolvimento

Ao executar `python run_gui.py` pelo código-fonte, o Benedito inicia automaticamente uma sessão de diagnóstico detalhada. Cada execução cria um arquivo próprio em:

```text
.benedito/logs/benedito-debug-AAAAmmddTHHMMSS-pidNNNN.log
```

Os 20 arquivos de sessão mais recentes são preservados. O diretório é ignorado pelo Git.

## O que é registrado

- data e hora com milissegundos, processo e thread;
- módulo, arquivo, linha e função que emitiram o evento;
- versão do Python, sistema, dependências e espaço em disco;
- etapas de inicialização e duração de cada etapa;
- exceções não tratadas da thread principal, threads secundárias e callbacks Tkinter;
- stack trace completo das falhas;
- criação, progresso, conclusão, cancelamento e falha de jobs;
- comandos, PID, saída de progresso, duração e erros de FFmpeg e FFprobe;
- falhas nativas capturáveis pelo `faulthandler` do Python.

O rastreamento não registra cada chamada Python bem-sucedida. Esse tipo de tracing tornaria a interface muito lenta e poderia gerar milhões de linhas durante um filme longo. Em caso de erro, o stack trace já preserva toda a cadeia de chamadas relevante.

## Produção

Quando `sys.frozen` está ativo, como no executável criado pelo PyInstaller e instalado pelo MSI, o diagnóstico é sempre desabilitado. Nenhum diretório ou arquivo de debug é criado, mesmo que `BENEDITO_DEBUG_LOG=1` esteja configurado.

O logger funcional usado pelas telas também opera sem arquivo no executável. Assim, importar módulos não cria mais uma pasta `logs` acidentalmente em `Program Files` ou no diretório atual.

## Configuração local

Para desativar temporariamente no código-fonte:

```powershell
$env:BENEDITO_DEBUG_LOG="0"
python run_gui.py
```

Para escolher outro diretório:

```powershell
$env:BENEDITO_DEBUG_LOG_DIR="D:\LogsBenedito"
python run_gui.py
```

Os arquivos podem conter caminhos locais, nomes de mídias, comandos e mensagens técnicas. Revise o conteúdo antes de anexá-lo a uma issue pública. Relatos de segurança devem seguir `SECURITY.md`.
