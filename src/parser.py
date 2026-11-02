import re


# Palavras que indicam linhas que não são produtos
PALAVRAS_IGNORAR = [
    "DOCUMENTO",
    "FISCAL",
    "CONTING",
    "AUTORIZ",
    "PAGAMENTO",
    "PAGAR",
    "CHAVE",
    "ACESSO",
    "CONSULTA",
    "SEFAZ",
    "CNPJ",
    "CPF",
    "NFC",
    "TRIBUT",
]


def converter_numero(valor: str) -> float:
    """
    Converte valores encontrados pelo OCR para float.

    Exemplos:
        "4,99"  -> 4.99
        "1,365" -> 1.365
        "39.90" -> 39.90
    """

    valor = valor.strip()
    valor = valor.replace(",", ".")

    return float(valor)


def limpar_descricao(linha: str) -> str:
    """
    Remove códigos numéricos e caracteres estranhos
    antes da descrição.

    Exemplo:

        "20030962 SALSA COMUM"

    vira:

        "SALSA COMUM"
    """

    linha = linha.strip()

    # Remove códigos grandes no início da linha
    linha = re.sub(
        r"^\D*\d{5,14}\s*",
        "",
        linha
    )

    # Remove símbolos estranhos no começo
    linha = re.sub(
        r"^[^A-Za-zÀ-ÿ]+",
        "",
        linha
    )

    # Remove múltiplos espaços
    linha = re.sub(
        r"\s+",
        " ",
        linha
    )

    return linha.strip()


def deve_ignorar(linha: str) -> bool:
    """
    Verifica se uma linha pertence ao cabeçalho,
    rodapé ou informações fiscais.
    """

    linha_maiuscula = linha.upper()

    for palavra in PALAVRAS_IGNORAR:
        if palavra in linha_maiuscula:
            return True

    if "HTTP" in linha_maiuscula:
        return True

    if "WWW." in linha_maiuscula:
        return True

    return False


def parece_descricao(linha: str) -> bool:
    """
    Verifica se uma linha parece conter
    uma descrição de produto.
    """

    if deve_ignorar(linha):
        return False

    # Conta quantas letras existem
    letras = re.findall(
        r"[A-Za-zÀ-ÿ]",
        linha
    )

    # Uma descrição precisa ter pelo menos 3 letras
    if len(letras) < 3:
        return False

    return True


def extrair_quantidade(linha: str):

    # Corrige alguns erros frequentes do OCR
    linha_corrigida = linha.upper()

    # Exemplo:
    # "1.365 49 X 4.31"
    # provavelmente "1.365 KG X 4.31"
    linha_corrigida = re.sub(
        r"(\d+[.,]\d+)\s+49\s+[Xx]",
        r"\1 KG X",
        linha_corrigida
    )

    padrao = re.compile(
        r"(\d+(?:[.,]\d+)?)"
        r"\s*"
        r"(KG|KGS|UN|UND|UNID|L|LT|ML|G)"
        r"\s*"
        r"[Xx]"
        r"\s*"
        r"(?:R\$)?"
        r"\s*"
        r"(\d+[.,]\d{2})",
        re.IGNORECASE
    )

    resultado = padrao.search(linha_corrigida)

    if not resultado:
        return None

    return {
        "quantidade": converter_numero(resultado.group(1)),
        "unidade": resultado.group(2).upper(),
        "preco_unitario": converter_numero(resultado.group(3))
    }

def extrair_preco(linha: str):
    """
    Verifica se a linha contém apenas um preço.

    Exemplos:

        2,38
        39.90
        R$ 21,89
    """

    padrao = re.compile(
        r"^[^\d]*"
        r"(\d+[.,]\d{2})"
        r"[^\d]*$"
    )

    resultado = padrao.match(linha)

    if not resultado:
        return None

    return converter_numero(
        resultado.group(1)
    )


def criar_produto_unitario(
    descricao: str,
    preco: float
):
    """
    Cria um produto quando não foi encontrada
    uma quantidade explícita.

    Neste caso assumimos 1 unidade.
    """

    return {
        "descricao": descricao,
        "quantidade": 1.0,
        "unidade": "UN",
        "preco_unitario": preco,
        "preco_total": preco
    }


def extrair_produtos(texto: str):
    """
    Recebe o texto bruto do OCR e tenta
    transformar em uma lista de produtos.

    Cada produto possui:

        descrição
        quantidade
        unidade
        preço unitário
        preço total
    """

    linhas = texto.splitlines()

    produtos = []

    # Produto que estamos montando
    descricao_pendente = None

    # Preço encontrado logo depois da descrição
    preco_pendente = None

    for linha in linhas:

        linha = linha.strip()

        if not linha:
            continue

        linha_maiuscula = linha.upper()
        if "TOTAL" in linha_maiuscula:
            break
        # ----------------------------------
        # FIM DA ÁREA DE PRODUTOS
        # ----------------------------------

        # Normalmente, depois daqui aparecem
        # pagamento, impostos, chave NFC-e etc.
        if (
            "QTD. TOTAL" in linha_maiuscula
            or "QTD TOTAL" in linha_maiuscula
            or "TOTAL DE ITENS" in linha_maiuscula
            or "VALOR TOTAL" in linha_maiuscula
            or "VALOR A PAGAR" in linha_maiuscula
        ):
            break

        if deve_ignorar(linha):
            continue

        # ----------------------------------
        # QUANTIDADE + UNIDADE + PREÇO
        # ----------------------------------

        dados_quantidade = extrair_quantidade(
            linha
        )

        if (
            dados_quantidade is not None
            and descricao_pendente is not None
        ):

            quantidade = (
                dados_quantidade["quantidade"]
            )

            unidade = (
                dados_quantidade["unidade"]
            )

            preco_unitario = (
                dados_quantidade["preco_unitario"]
            )

            # Se já encontramos um preço antes
            # dessa linha, provavelmente ele é
            # o preço total do produto.
            if preco_pendente is not None:

                preco_total = preco_pendente

            else:

                # Caso não exista preço total
                # explícito, calculamos.
                preco_total = round(
                    quantidade * preco_unitario,
                    2
                )

            produto = {
                "descricao": descricao_pendente,
                "quantidade": quantidade,
                "unidade": unidade,
                "preco_unitario": preco_unitario,
                "preco_total": preco_total
            }

            produtos.append(produto)

            # Produto concluído
            descricao_pendente = None
            preco_pendente = None

            continue

        # ----------------------------------
        # PREÇO SOZINHO
        # ----------------------------------

        preco = extrair_preco(linha)

        if (
            preco is not None
            and descricao_pendente is not None
        ):

            # Não criamos o produto ainda.
            #
            # Pode existir uma linha seguinte como:
            #
            # TOMATE SALADA
            # 6,81
            # 1,365 KG X 4,99
            #
            # Então guardamos temporariamente.
            preco_pendente = preco

            continue

        # ----------------------------------
        # DESCRIÇÃO
        # ----------------------------------

        if parece_descricao(linha):

            nova_descricao = limpar_descricao(
                linha
            )

            if not nova_descricao:
                continue

            # Já havia um produto pendente com preço,
            # mas nenhuma quantidade apareceu.
            #
            # Assumimos que foi comprado 1 UN.
            if (
                descricao_pendente is not None
                and preco_pendente is not None
            ):

                produto = criar_produto_unitario(
                    descricao_pendente,
                    preco_pendente
                )

                produtos.append(produto)

            # A nova linha passa a ser
            # o próximo produto
            descricao_pendente = nova_descricao
            preco_pendente = None

    # ----------------------------------
    # ÚLTIMO PRODUTO
    # ----------------------------------

    # Caso o cupom termine sem aparecer
    # outra descrição depois dele.
    if (
        descricao_pendente is not None
        and preco_pendente is not None
    ):

        produto = criar_produto_unitario(
            descricao_pendente,
            preco_pendente
        )

        produtos.append(produto)

    return produtos