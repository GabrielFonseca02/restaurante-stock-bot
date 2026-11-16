# restaurante-stock-bot

Leitura de QR Codes de cupons fiscais pela webcam e consulta dos produtos de
uma NFC-e.

## Estrutura

```text
restaurante-stock-bot/
├── requirements.txt        # Dependências Python
├── src/                    # Código da aplicação
│   ├── __init__.py
│   ├── scanner.py          # Leitura pela webcam
│   ├── consulta_nfce.py    # Entrada da consulta de NFC-e
│   ├── htmlhelper.py       # Funções auxiliares de HTML
│   └── tratamento_erros.py # Mensagens de erro da leitura e da consulta
└── receipts/               # Imagens de cupons e QR Codes
```

## Instalação

No terminal, na pasta principal do projeto:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Execução

Ler um QR Code pela webcam:

```powershell
python -m src.scanner
```

## Consulta de NFC-e

Para ler o QR Code pela webcam e consultar os itens, execute na raiz:

```powershell
python src/consulta_nfce.py
```

Se o terminal estiver dentro de `src`, use `python consulta_nfce.py`.
O scanner retorna a URL para a consulta e libera a câmera. Pressione Esc
para cancelar. São aceitos os domínios `nfe.sefaz.go.gov.br` e
`nfeweb.sefaz.go.gov.br`.
