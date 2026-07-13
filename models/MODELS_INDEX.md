# Modelos compatíveis

O Benedito Digital incorpora somente os arquivos de arquitetura necessários para carregar pesos compatíveis. Repositórios completos, exemplos, datasets e pesos de terceiros não fazem parte do projeto.

## Estrutura

    models/
      architectures/
        restormer/restormer_arch.py
        swinir/network_swinir.py
        unet_dust/unet.py
      weights/
      registry.json
      THIRD_PARTY_NOTICES.md

## Famílias nativas

- **SwinIR**: denoise e super-resolução; requer PyTorch e timm.
- **Restormer**: denoise e deblur; requer PyTorch e einops.
- **U-Net Dust**: geração de máscara por segmentação; requer PyTorch.
- **DnCNN / KAIR** e **BSRGAN / RRDB**: pesos podem ser importados pelo catálogo, observando a licença indicada.

## Pesos

Os dois pesos U-Net Dust de licença MIT são incluídos para oferecer detecção local imediatamente após a instalação. Seus hashes estão em models/weights/unet_dust/manifest.json.

Outros pesos são escolhidos pelo usuário e copiados transacionalmente para models/weights/<família> com SHA-256 registrado. Eles não são incluídos no instalador oficial.

Arquivos com licença review-upstream não devem ser redistribuídos até a confirmação dos termos na fonte original.
