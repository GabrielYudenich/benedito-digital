# Integração planejada do LTX-2

Esta avaliação foi feita em 13 de julho de 2026 a partir do repositório e do catálogo oficiais da Lightricks. A integração será opcional e experimental.

## Onde o modelo pode ajudar

- **Retake de um intervalo**: regenerar uma região temporal delimitada de um vídeo.
- **Interpolação entre frames-chave**: produzir movimento entre imagens de referência.
- **Vídeo para vídeo**: reconstruções generativas guiadas por texto ou condicionamento visual.

Essas operações não são restauração arquivística determinística. O modelo pode inventar textura, objetos, rostos ou movimento. Por isso, o Benedito deve salvar o resultado em uma derivação separada, manter o original intacto e registrar modelo, hashes, prompt, seed e intervalo usados. Filtros clássicos, retoque manual e modelos especializados continuam sendo a opção padrão para preservação fiel.

## Requisitos observados

- Python 3.12 ou superior;
- CUDA superior a 12.7;
- PyTorch aproximadamente 2.7;
- checkpoint distilled principal de aproximadamente 46,1 GB;
- upscaler espacial de aproximadamente 996 MB nos fluxos de dois estágios;
- Gemma 3 adicional para codificação de texto;
- dimensões múltiplas de 32 e quantidade de frames no formato `8k + 1` em fluxos atuais.

O requisito é muito superior ao dos filtros normais do Benedito. A interface deverá verificar GPU, VRAM, RAM, disco e versões antes de oferecer a execução.

## Instalação segura

O LTX-2 não será incorporado ao MSI. O modelo oficial exige aceite de termos no Hugging Face e pode exigir autenticação, além de tornar o instalador impraticavelmente grande.

O fluxo planejado é:

1. instalar normalmente o Benedito sem o LTX-2;
2. abrir **Modelos > Modelos instalados e créditos**;
3. escolher a instalação opcional do LTX-2 e ler/aceitar os termos na fonte oficial;
4. baixar os arquivos com progresso, retomada, estimativa de disco e verificação de integridade;
5. armazenar o ambiente e os pesos no diretório local do usuário, nunca dentro da pasta protegida do programa;
6. executar a inferência em um worker isolado e local, sem enviar o filme para servidores.

O catálogo atual apenas apresenta a integração planejada e os requisitos oficiais. O botão de instalação só deve ser habilitado quando o worker, a verificação de hardware e o aceite de licença estiverem implementados.

## Licença

O código, os pesos e os derivados do LTX-2 usam o **LTX-2 Community License Agreement**, não a licença Apache 2.0 do Benedito. A licença exige preservação de avisos e cópia dos termos em redistribuições, contém restrições de uso e exige licença comercial paga para entidades com receita anual a partir de US$ 10 milhões. Antes de distribuir qualquer componente, a versão vigente dos termos deve ser revisada.

Fontes oficiais:

- <https://github.com/Lightricks/LTX-2>
- <https://huggingface.co/Lightricks/LTX-2.3>

## Etapas de implementação

1. diagnóstico de hardware e espaço;
2. gerenciador de downloads autenticados e retomáveis;
3. ambiente Python/CUDA isolado do aplicativo principal;
4. adaptador inicial para interpolação e retake de trechos curtos;
5. jobs com progresso por etapa e cancelamento;
6. proveniência completa e comparação lado a lado;
7. testes de memória, falhas e fidelidade antes de liberar a função por padrão.
