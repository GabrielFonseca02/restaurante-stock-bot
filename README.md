# restaurante-stock-bot

Leitura de QR Codes de cupons fiscais pela webcam e consulta dos produtos de
uma NFC-e.

## Estrutura

```text
restaurante-stock-bot/
├── main.py                 # Entrada: consulta de NFC-e pela webcam
├── requirements.txt        # Dependências Python
├── src/                    # Código da aplicação
│   ├── __init__.py
│   ├── scanner.py          # Leitura pela webcam
│   ├── consulta_nfce.py    # Funções de consulta e extração da NFC-e
│   └── htmlhelper.py       # Funções auxiliares de HTML
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
python main.py
```

Na raiz, também é possível usar `python -m src.consulta_nfce`. Se o terminal
estiver dentro de `src`, use `python consulta_nfce.py`.
O scanner retorna a URL para a consulta e libera a câmera. Pressione Esc
para cancelar. São aceitos os domínios `nfe.sefaz.go.gov.br` e
`nfeweb.sefaz.go.gov.br`.
