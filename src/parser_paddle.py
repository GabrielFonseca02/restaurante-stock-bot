import re


UNIDADES = {
    "KG": "KG",
    "KGS": "KG",
    "KS": "KG",       # erro possível do OCR
    "UN": "UN",
    "UND": "UN",
    "UNID": "UN",
    "PC": "UN",       # peça -> unidade
    "PCS": "UN",
    "L": "L",
    "LT": "L",
    "ML": "ML",
    "G": "G",
}


PALAVRAS_IGNORAR = [
    "DOCUMENTO",
    "FISCAL",
    "CONTINGENCIA",
    "AUTORIZACAO",
    "AUTORIZAÇÃO",
    "TOTAL",
    "PAGAMENTO",
    "PAGAR",
    "CHAVE",
    "ACESSO",
    "SEFAZ",
    "CONSUMIDOR",
    "NFC",
    "OPERADOR",
    "LOJA",
]


# =========================================================
# FUNÇÕES BÁSICAS
# =========================================================

def centro_x(bloco):
    return (bloco["x1"] + bloco["x2"]) / 2


def centro_y(bloco):
    return (bloco["y1"] + bloco["y2"]) / 2


def converter_numero(texto):
    texto = texto.strip()
    texto = texto.replace(",", ".")

    return float(texto)


def extrair_preco(texto):
    """
    Reconhece preços como:

        39.90
        39,90
        2.59

    Não aceita códigos grandes.
    """

    resultado = re.fullmatch(
        r"\s*(\d+[.,]\d{2})\s*",
        texto
    )

    if not resultado:
        return None

    return converter_numero(
        resultado.group(1)
    )


# =========================================================
# QUANTIDADE / UNIDADE
# =========================================================

def analisar_linha_quantidade(texto):
    """
    Reconhece linhas como:

        1.618 Kg x
        1,596 Kg x
        .814 Ks X
        1.000 Un x
        2.000 Un x
        PC X
        Un x
        00 PC x
        174 Kg x

    Retorna:
        quantidade lida pelo OCR
        unidade normalizada
    """

    texto = texto.strip().upper()

    padrao = re.search(
        r"(?P<qtd>"
        r"(?:\d+[.,]\d+)"
        r"|(?:[.,]\d+)"
        r"|(?:\d+)"
        r")?"
        r"\s*"
        r"(?P<unidade>"
        r"KG|KGS|KS|UN|UND|UNID|PC|PCS|ML|LT|L|G"
        r")"
        r"\s*[Xx]",
        texto,
        re.IGNORECASE
    )

    if not padrao:
        return None

    unidade = padrao.group(
        "unidade"
    ).upper()

    unidade = UNIDADES.get(
        unidade,
        unidade
    )

    quantidade_texto = padrao.group(
        "qtd"
    )

    quantidade = None

    if quantidade_texto:

        try:
            quantidade = converter_numero(
                quantidade_texto
            )

        except ValueError:
            quantidade = None

    return {
        "quantidade": quantidade,
        "unidade": unidade
    }


# =========================================================
# DESCRIÇÃO
# =========================================================

def limpar_descricao(texto):
    """
    Remove códigos do começo.

    7896773900066 NANT COMPLEITE 500G
                ↓
    NANT COMPLEITE 500G
    """

    texto = texto.strip()

    texto = re.sub(
        r"^\d{2,14}\s+",
        "",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def parece_descricao(texto):
    """
    Decide se um bloco parece ser uma descrição
    de produto.
    """

    texto_maiusculo = texto.upper()

    # Não pode ser linha de quantidade
    if analisar_linha_quantidade(texto) is not None:
        return False

    # Não pode ser preço
    if extrair_preco(texto) is not None:
        return False

    # Não queremos informações fiscais
    for palavra in PALAVRAS_IGNORAR:

        if palavra in texto_maiusculo:
            return False

    # Precisa conter letras suficientes
    letras = re.findall(
        r"[A-ZÀ-Ý]",
        texto_maiusculo
    )

    if len(letras) < 3:
        return False

    return True


# =========================================================
# PROCURA DA DESCRIÇÃO
# =========================================================

def encontrar_descricao(
    blocos,
    bloco_quantidade
):
    """
    A descrição normalmente está imediatamente
    acima da linha de quantidade.
    """

    y_quantidade = centro_y(
        bloco_quantidade
    )

    candidatos = []

    for bloco in blocos:

        texto = bloco["texto"]

        if not parece_descricao(texto):
            continue

        y = centro_y(bloco)

        distancia = (
            y_quantidade - y
        )

        # Descrição precisa estar acima
        # e relativamente próxima.
        if 5 <= distancia <= 70:

            candidatos.append(
                (
                    distancia,
                    bloco
                )
            )

    if not candidatos:
        return None

    # A descrição mais próxima ganha
    candidatos.sort(
        key=lambda item: item[0]
    )

    return candidatos[0][1]


# =========================================================
# PREÇO UNITÁRIO
# =========================================================

def encontrar_preco_unitario(
    blocos,
    bloco_quantidade,
    largura
):
    """
    No cupom analisado, preço unitário fica
    aproximadamente na coluna central.

    Exemplo:

        1.618 KG X        39.90
    """

    y_quantidade = centro_y(
        bloco_quantidade
    )

    candidatos = []

    for bloco in blocos:

        preco = extrair_preco(
            bloco["texto"]
        )

        if preco is None:
            continue

        x = centro_x(bloco)
        y = centro_y(bloco)

        # Coluna intermediária
        if not (
            largura * 0.45
            <= x
            <= largura * 0.72
        ):
            continue

        distancia_y = abs(
            y_quantidade - y
        )

        if distancia_y <= 35:

            candidatos.append(
                (
                    distancia_y,
                    preco,
                    bloco
                )
            )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda item: item[0]
    )

    return candidatos[0]


# =========================================================
# PREÇO TOTAL DO PRODUTO
# =========================================================

def encontrar_preco_total(
    blocos,
    bloco_descricao,
    largura
):
    """
    O total do produto aparece na coluna
    mais à direita e normalmente fica alinhado
    à descrição.
    """

    y_descricao = centro_y(
        bloco_descricao
    )

    candidatos = []

    for bloco in blocos:

        preco = extrair_preco(
            bloco["texto"]
        )

        if preco is None:
            continue

        x = centro_x(bloco)
        y = centro_y(bloco)

        # Coluna mais à direita
        if x < largura * 0.72:
            continue

        distancia_y = abs(
            y_descricao - y
        )

        if distancia_y <= 25:

            candidatos.append(
                (
                    distancia_y,
                    preco,
                    bloco
                )
            )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda item: item[0]
    )

    return candidatos[0]


# =========================================================
# CORREÇÃO MATEMÁTICA DA QUANTIDADE
# =========================================================

def corrigir_quantidade(
    quantidade_ocr,
    unidade,
    preco_unitario,
    preco_total
):
    """
    Usa a própria matemática do cupom.

    Exemplo:

        OCR:
            .814 Ks X

        preço unitário:
            39.90

        total:
            72.37

        quantidade real:

            72.37 / 39.90
            ≈ 1.814
    """

    if (
        preco_unitario is None
        or preco_total is None
        or preco_unitario == 0
    ):
        return quantidade_ocr

    quantidade_calculada = (
        preco_total / preco_unitario
    )

    # Primeiro tentamos confiar no OCR.
    if quantidade_ocr is not None:

        total_estimado = round(
            quantidade_ocr
            * preco_unitario,
            2
        )

        diferenca = abs(
            total_estimado
            - preco_total
        )

        # Pequenas diferenças podem ser
        # arredondamento do mercado.
        if diferenca <= 0.02:
            return quantidade_ocr

    # OCR estava errado ou perdeu quantidade.

    if unidade == "UN":

        quantidade_inteira = round(
            quantidade_calculada
        )

        # Produto por unidade deve ficar
        # próximo de inteiro.
        if abs(
            quantidade_calculada
            - quantidade_inteira
        ) <= 0.05:

            return float(
                quantidade_inteira
            )

    # Produtos por peso podem ter 3 casas
    return round(
        quantidade_calculada,
        3
    )


# =========================================================
# EXTRAÇÃO DOS PRODUTOS
# =========================================================

def _extrair_layout_original(blocos):
    """
    Parser principal do PaddleOCR.

    Usa as coordenadas X/Y para relacionar:

        descrição
        quantidade
        unidade
        preço unitário
        preço total
    """

    if not blocos:
        return []

    largura = max(
        bloco["x2"]
        for bloco in blocos
    )

    produtos = []

    for bloco_quantidade in blocos:

        dados_quantidade = analisar_linha_quantidade(
            bloco_quantidade["texto"]
        )

        if dados_quantidade is None:
            continue

        # ---------------------------------
        # DESCRIÇÃO
        # ---------------------------------

        bloco_descricao = encontrar_descricao(
            blocos,
            bloco_quantidade
        )

        if bloco_descricao is None:
            continue

        # ---------------------------------
        # PREÇO UNITÁRIO
        # ---------------------------------

        resultado_unitario = encontrar_preco_unitario(
            blocos,
            bloco_quantidade,
            largura
        )

        if resultado_unitario is None:
            continue

        preco_unitario = (
            resultado_unitario[1]
        )

        # ---------------------------------
        # TOTAL DO PRODUTO
        # ---------------------------------

        resultado_total = encontrar_preco_total(
            blocos,
            bloco_descricao,
            largura
        )

        if resultado_total is None:
            continue

        preco_total = (
            resultado_total[1]
        )

        # ---------------------------------
        # QUANTIDADE
        # ---------------------------------

        quantidade_ocr = (
            dados_quantidade["quantidade"]
        )

        unidade = (
            dados_quantidade["unidade"]
        )

        quantidade = corrigir_quantidade(
            quantidade_ocr,
            unidade,
            preco_unitario,
            preco_total
        )

        if quantidade is None:
            continue

        descricao = limpar_descricao(
            bloco_descricao["texto"]
        )

        produto = {
            "descricao": descricao,
            "quantidade": quantidade,
            "unidade": unidade,
            "preco_unitario": preco_unitario,
            "preco_total": preco_total
        }

        produtos.append(produto)

    return produtos


def agrupar_linhas(blocos):
    """Reúne colunas pela altura do texto, sem limites fixos em pixels."""
    linhas = []
    for bloco in sorted(blocos, key=centro_y):
        altura = max(1, bloco['y2'] - bloco['y1'])
        candidatos = [l for l in linhas if abs(centro_y(bloco)-l['y']) <= altura * .35]
        if candidatos:
            linha = min(candidatos, key=lambda l: abs(l['y']-centro_y(bloco)))
            linha['blocos'].append(bloco)
            linha['y'] = sum(centro_y(b) for b in linha['blocos'])/len(linha['blocos'])
        else:
            linhas.append({'y': centro_y(bloco), 'blocos': [bloco]})
    for linha in linhas:
        linha['texto'] = ' '.join(b['texto'] for b in sorted(linha['blocos'], key=lambda b:b['x1']))
    return linhas


def _extrair_layout_anterior(blocos):
    originais = [dict(b, y1=b.get('y1_original', b['y1']), y2=b.get('y2_original', b['y2'])) for b in blocos]
    antigos = _extrair_layout_original(originais)
    produtos = []
    descricao = None
    for linha in agrupar_linhas(blocos):
        texto = linha['texto'].replace('×', 'x')
        if re.search(r'(?:TOTAL.*ITENS|TOTAL.*IENS|VALOR.*TOTAL|VALOR.*PAGAR)', texto, re.I):
            break
        # Layout em duas linhas: código/descrição, depois quantidade x preço.
        cabecalho = re.match(r'^\s*\d{1,3}\s+[\dO]{4,14}\s+(.+)', texto)
        if cabecalho:
            descricao = cabecalho.group(1)
        qtd = re.search(r'(?:(\d+(?:[.,]\d+)?)\s*)?(KG|UN|N)?\s*x\s*(\d+[.,]\d{2})', texto, re.I)
        if qtd and descricao:
            precos = re.findall(r'\d+[.,]\d{2}(?!\d)', texto[qtd.end():])
            if precos:
                unitario = converter_numero(qtd.group(3))
                total = converter_numero(precos[-1])
                quantidade = converter_numero(qtd.group(1)) if qtd.group(1) else corrigir_quantidade(None, 'UN', unitario, total)
                produtos.append(dict(descricao=descricao, quantidade=quantidade,
                                     unidade='KG' if (qtd.group(2) or '').upper()=='KG' else 'UN',
                                     preco_unitario=unitario, preco_total=total))
                descricao = None
                continue
        # Layout tabular: descrição, quantidade/unidade e dois preços na mesma linha.
        tabela = re.search(r'(\d+(?:[.,]\d+)?)\s*(KG|UN)\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s*$', texto, re.I)
        if tabela:
            desc = texto[:tabela.start()].strip()
            desc = re.sub(r'^\d{1,3}\s+', '', desc)
            desc = limpar_descricao(desc)
            # Duas descrições na mesma linha indicam associação ambígua.
            ambiguo = re.search(r'\b\d{2,3}\s+\d{4,14}\s', desc)
            consistente = abs(converter_numero(tabela.group(1))*converter_numero(tabela.group(3))-converter_numero(tabela.group(4))) <= .03
            if parece_descricao(desc) and not ambiguo and consistente:
                produtos.append(dict(descricao=desc, quantidade=converter_numero(tabela.group(1)),
                                     unidade=tabela.group(2).upper(), preco_unitario=converter_numero(tabela.group(3)),
                                     preco_total=converter_numero(tabela.group(4))))
    return produtos if len(produtos) > len(antigos) else antigos


def extrair_produtos_paddle(blocos):
    from src.receipt_layout import extrair_espacial, aplicar_cancelamentos
    anterior = _extrair_layout_anterior(blocos)
    espacial = extrair_espacial(blocos)

    def qualidade(produtos):
        validos = sum(p['quantidade'] > 0 and
                      (p['unidade'] != 'UN' or abs(p['quantidade']-round(p['quantidade'])) <= .001) and
                      abs(p['quantidade']*p['preco_unitario']-p['preco_total']) <= .03 for p in produtos)
        return validos, -(len(produtos)-validos)

    escolhidos = espacial if espacial and qualidade(espacial) >= qualidade(anterior) else anterior
    return aplicar_cancelamentos(blocos, escolhidos)


# =========================================================
# VERIFICAÇÃO DA QUANTIDADE DE ITENS
# =========================================================

def extrair_total_itens_declarado(blocos):
    """
    Procura:

        QTD. TOTAL DE ITENS             16

    usando posição X/Y.
    """

    bloco_total = None

    for bloco in blocos:

        texto = bloco["texto"].upper()

        if (
            "TOTAL" in texto
            and "ITENS" in texto
        ):

            bloco_total = bloco
            break

    if bloco_total is None:
        return None

    y_total = centro_y(
        bloco_total
    )

    candidatos = []

    for bloco in blocos:

        texto = bloco["texto"].strip()

        # Queremos número inteiro puro
        if not re.fullmatch(
            r"\d{1,3}",
            texto
        ):
            continue

        # Número deve estar à direita
        if bloco["x1"] <= bloco_total["x2"]:
            continue

        y = centro_y(bloco)

        distancia_y = abs(
            y_total - y
        )

        if distancia_y <= 20:

            candidatos.append(
                (
                    distancia_y,
                    int(texto)
                )
            )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda item: item[0]
    )

    return candidatos[0][1]


def _verificar_quantidade_itens_anterior(
    blocos,
    produtos
):
    """
    Compara a quantidade de itens informada
    pelo cupom com a quantidade calculada.

    Produtos vendidos por unidade:
        quantidade entra na contagem.

        Exemplo:
            2 UN -> 2 itens

    Produtos vendidos por peso/volume:
        cada linha representa 1 item comercial.

        Exemplo:
            1.618 KG -> 1 item
    """

    declarado = extrair_total_itens_declarado(
        blocos
    )

    itens_calculados = 0

    for produto in produtos:

        unidade = produto["unidade"]

        quantidade = produto["quantidade"]

        if unidade == "UN":

            # Produtos vendidos por unidade
            itens_calculados += round(
                quantidade
            )

        else:

            # KG, L, ML, G etc.
            # representam uma linha de item
            itens_calculados += 1

    if declarado is None:

        return {
            "status": "NAO_VERIFICADO",
            "itens_declarados": None,
            "itens_calculados": itens_calculados,
            "linhas_extraidas": len(produtos),
            "diferenca": None
        }

    diferenca = (
        declarado
        - itens_calculados
    )

    if diferenca == 0:

        status = "OK"

    else:

        status = "REVISAO_NECESSARIA"

    return {
        "status": status,
        "itens_declarados": declarado,
        "itens_calculados": itens_calculados,
        "linhas_extraidas": len(produtos),
        "diferenca": diferenca
    }

def extrair_valor_total_declarado(blocos):
    """
    Procura no cupom:

        VALOR TOTAL R$        472.09

    e retorna:

        472.09
    """

    bloco_valor_total = None

    # Primeiro encontramos o texto "VALOR TOTAL"
    for bloco in blocos:

        texto = bloco["texto"].upper()

        if "VALOR TOTAL" in texto or "VALOR A PAGAR" in texto:
            bloco_valor_total = bloco
            break

    if bloco_valor_total is None:
        return None

    y_total = centro_y(
        bloco_valor_total
    )

    candidatos = []

    # Agora procuramos um preço na mesma linha,
    # normalmente à direita.
    for bloco in blocos:

        preco = extrair_preco(
            bloco["texto"]
        )

        if preco is None:
            continue

        # O valor precisa estar à direita
        # do texto "VALOR TOTAL"
        if bloco["x1"] <= bloco_valor_total["x2"]:
            continue

        y = centro_y(bloco)

        distancia_y = abs(
            y_total - y
        )

        # Mesma região horizontal
        if distancia_y <= 20:

            candidatos.append(
                (
                    distancia_y,
                    preco
                )
            )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda item: item[0]
    )

    return candidatos[0][1]

def _verificar_valor_total_anterior(
    blocos,
    produtos
):
    """
    Soma o preço total dos produtos e compara
    com o VALOR TOTAL informado no cupom.
    """

    valor_declarado = (
        extrair_valor_total_declarado(
            blocos
        )
    )

    valor_calculado = round(
        sum(
            produto["preco_total"]
            for produto in produtos
        ),
        2
    )

    if valor_declarado is None:

        return {
            "status": "NAO_VERIFICADO",
            "valor_declarado": None,
            "valor_calculado": valor_calculado,
            "diferenca": None
        }

    diferenca = round(
        valor_declarado
        - valor_calculado,
        2
    )

    # Permitimos até dois centavos de diferença
    # por causa de arredondamentos.
    if abs(diferenca) <= 0.02:

        status = "OK"

    else:

        status = "REVISAO_NECESSARIA"

    return {
        "status": status,
        "valor_declarado": valor_declarado,
        "valor_calculado": valor_calculado,
        "diferenca": diferenca
    }


def verificar_quantidade_itens(blocos, produtos):
    from src.receipt_layout import verificar_quantidade
    return verificar_quantidade(blocos, produtos, extrair_total_itens_declarado(blocos))


def verificar_valor_total(blocos, produtos):
    from src.receipt_layout import verificar_valor
    return verificar_valor(blocos, produtos)
