# Colaboração local

O Benedito colabora por uma pasta local, NAS ou serviço de sincronização. Não abre portas,
não executa servidor e nunca envia o vídeo original. A pasta contém operações pequenas e
somente os objetos de imagem alterados, deduplicados por SHA-256.

## Interface

1. Abra `Versionamento > Colaboração da equipe`.
2. Escolha uma pasta compartilhada.
3. Selecione uma branch local e use `Push`.
4. No outro computador, abra o mesmo projeto original e use `Pull`.
5. Revise a branch recebida e faça o merge visual pelo gerenciador de branches.

O projeto deve conservar o mesmo identificador em `metadata/project.json` e os hashes dos
originais precisam coincidir. Caminhos remotos são guardados somente no cache recriável.

## Linha de comando

```powershell
benedito.exe remote-init D:\EquipeBenedito
benedito.exe status "D:\Projetos\Rolo 1" D:\EquipeBenedito
benedito.exe push "D:\Projetos\Rolo 1" D:\EquipeBenedito --branch limpeza
benedito.exe pull "D:\Projetos\Rolo 1" D:\EquipeBenedito --branch limpeza
```

Escritas usam lock exclusivo, arquivos temporários e troca atômica. Snapshots não podem
escapar da pasta remota e objetos recebidos são verificados antes da importação.
