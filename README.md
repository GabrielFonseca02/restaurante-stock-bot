# restaurante-stock-bot

Leitor de cupons fiscais para automatizar a entrada de estoque em restaurantes com OCR.

# Digitalização de cupons com PaddleOCR

## Parser melhorado

As três melhorias de contagem, ajustes monetários/cancelamentos e associação
espacial estão implementadas em `src/receipt_layout.py` e integradas à API
existente em `src/parser_paddle.py`.

```powershell
.venv/Scripts/python.exe comparar_parser.py
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe avaliar_cupons.py --cupons 1 10 22 32 49 50 51 --saida resultados/parser-validacao-ocr
```

A comparação isolada com os blocos dos 51 cupons passou de 10 para 16
aprovações, sem regressões entre os dez aprovados anteriores. Os seis casos
recuperados foram 010, 022, 032, 049, 050 e 051. Esses casos e o 001 também
foram executados novamente pelo PaddleOCR e passaram nas duas verificações.
Veja `resultados/parser-melhorado/relatorio.md` e os arquivos `.txt`/`.json`
por cupom. A escrita organizada preserva letras do OCR, inclusive erros de
grafia, e não substitui o texto bruto original.

Os produtos cancelados permanecem no JSON para auditoria com `cancelado=true`;
consumidores da lista precisam ignorá-los ao lançar compras/estoque. Os valores
dos produtos permanecem brutos; `valor.ajustes` registra descontos/acréscimos
separados, e `valor.valor_liquido_calculado` apresenta a soma final. Percentuais
sem valor monetário explícito não são transformados em desconto.

A contagem registra `criterio`, `linhas_documento`, `linhas_ativas` e
`unidades_calculadas`. A sequência impressa dos índices serve de evidência
para contar linhas; não se escolhe a regra apenas para aproximar um resultado
extraído do número declarado. Quantidades zero/negativas e UN fracionário
impedem a aprovação. Cancelamento com item não identificado exige revisão.

Ambiente avaliado: Python 3.12, paddlepaddle 3.2.0 e paddleocr 3.7.0.
Os modelos PP-OCRv6_medium_det e PP-OCRv6_medium_rec ficam em `models/`.
Foram copiados do cache instalado porque o modelo de reconhecimento não
estava acessível ao processo restrito. Não é necessário treinar um modelo
para executar estes testes.

## Avaliação ampliada: cupons 001 a 051

As 87 imagens de `receipts/personal` foram numeradas até `cupom-087`.
O arquivo `receipts/personal/renomeacao.json` guarda os nomes anteriores
e hashes SHA-256 das 82 imagens renomeadas, preservando 001–005.
A ordem usada foi a ordenação natural dos nomes anteriores, incluindo cópias.

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe avaliar_cupons.py --inicio 1 --fim 51 --saida resultados/avaliacao-001-051
.venv/Scripts/python.exe diagnosticar_cupons.py
```

O relatório está em `resultados/avaliacao-001-051/relatorio.md`, com todas
as reprovações; `diagnostico.csv` permite filtrar; `estatisticas.json` guarda
as contagens. `revisao-visual.md` documenta exemplos confirmados de falhas
de OCR, pré-processamento, parser e conferência. `contato-*.jpg` são pranchas
das fotos originais para inspeção. A execução original fica em
`resultados/avaliacao-001-051.log`.

Passar significa ter produtos e status OK tanto na quantidade quanto no
valor. Não comprova transcrição exata dos itens. NAO_VERIFICADO conta como
reprovação nesse critério, inclusive em documentos sem uma contagem impressa.
O parser e OCR permaneceram iguais durante o lote; foram alteradas apenas
as ferramentas de avaliação e diagnóstico.

No PowerShell, na pasta do projeto:

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe avaliar_cupons.py
.venv/Scripts/python.exe main.py receipts/personal/cupom-001.jpeg --ocr paddle
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

A avaliação carrega o modelo uma vez e salva `resultados/cupom-00x.txt`
(transcrição), `.json` (produtos, blocos, confiança e conferências) e
`resultados/resumo.json`. Os arquivos são substituídos a cada execução.
`avaliacao.log` contém a execução utilizada na revisão.

O OCR preserva a imagem colorida, evita recortes de proporção inadequada
e compensa a inclinação nas coordenadas usadas para reunir colunas.
O parser aceita layouts em duas linhas e tabelas com quantidade/unidade
e preços na mesma linha. Limites de detecção 736 e 960 foram avaliados,
mas prejudicaram o primeiro cupom; a configuração padrão foi preservada.

Os resultados são candidatos para revisão. Uma soma correta não garante
descrições corretas; quantidades ausentes podem ser inferidas pela divisão
do total pelo preço unitário. As transcrições e confianças originais ficam
disponíveis para auditar essa inferência. O cupom 005 tem itens cobertos,
curvatura, descontos e valores com separadores perdidos; a lista de produtos
é parcial e deve ser revisada, mesmo que o texto tenha sido digitalizado.

Para ampliar a avaliação, mantenha uma referência manual de produtos e
valores por foto e compare descrição, quantidade, preço e total separadamente.
Fotografar o papel inteiro, plano e sem dedos sobre os produtos ajuda mais
que forçar correções numéricas. Quando disponível, o XML fiscal é uma fonte
mais exata de itens que a transcrição de uma foto.
