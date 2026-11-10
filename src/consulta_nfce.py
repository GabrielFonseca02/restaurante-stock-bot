"""Lê o QR Code de uma NFC-e de Goiás pela câmera e consulta seus itens."""

import argparse
import asyncio
import re
import sys
from urllib.parse import parse_qs, urlencode, urlsplit
from xml.etree import ElementTree

import aiohttp
from yarl import URL

if __package__:
    from . import htmlhelper
    from .tratamento_erros import ErroAplicacao, ErroConsulta, TratadorErros
else:
    import htmlhelper
    from tratamento_erros import ErroAplicacao, ErroConsulta, TratadorErros


MAX_TENTATIVAS = 3
TIMEOUT_SEGUNDOS = 30


def normalizar_url_nfce(url: str) -> str:
    """Converte os separadores codificados do QR Code sem decodificar outros campos."""
    partes = urlsplit(url.strip())
    query = re.sub(r"%7c", "|", partes.query, flags=re.IGNORECASE)
    return partes._replace(query=query).geturl()


def montar_url_itens(url: str) -> str:
    try:
        partes = urlsplit(url)
    except ValueError as erro:
        raise ErroAplicacao("O QR Code contém uma URL inválida.") from erro

    dominios = {"nfe.sefaz.go.gov.br", "nfeweb.sefaz.go.gov.br"}
    if partes.scheme not in ("http", "https") or partes.netloc.lower() not in dominios:
        raise ErroAplicacao("O QR Code deve conter uma URL http/https da NFC-e de Goiás.")

    parametro = parse_qs(partes.query).get("p", [""])[0]
    chave = parametro.split("|", 1)[0]
    if len(chave) != 44 or not chave.isascii() or not chave.isdigit():
        raise ErroAplicacao("A URL deve conter uma chave de 44 dígitos no parâmetro p.")

    return (
        f"{partes.scheme}://{partes.netloc}/nfeweb/sites/nfce/render/html/danfeNFCe?"
        + urlencode({"chNFe": chave})
    )


async def load_data(session: aiohttp.ClientSession, url: str, url_itens: str) -> str:
    # As duas requisições compartilham a sessão.
    # Impede que aiohttp/yarl transforme os separadores em %7C novamente.
    async with session.get(URL(normalizar_url_nfce(url), encoded=True)) as pagina:
        pagina.raise_for_status()
        await pagina.read()

    async with session.get(url_itens) as itens:
        itens.raise_for_status()
        return await itens.text()


def extrair_itens(resposta: str) -> list[dict[str, str]]:
    try:
        xml = ElementTree.fromstring(resposta)
    except ElementTree.ParseError as erro:
        raise TratadorErros.xml_invalido() from erro

    html_nota = xml.findtext("./PARAMS/DANFE_NFCE_HTML")
    if not html_nota or not html_nota.strip():
        status = xml.findtext("STATUS") or "não informado"
        raise ErroAplicacao(f"A resposta não trouxe o HTML da nota (status: {status}).")

    soup = htmlhelper.parse_html(html_nota)
    table = soup.find("table", id="tabResult")
    if table is None:
        raise ErroAplicacao("A tabela de produtos não foi encontrada na nota.")

    itens_data = []
    for numero, produto in enumerate(table.find_all("tr"), start=1):
        if produto.find("th") is not None:
            continue
        spans = produto.find_all("span")
        if len(spans) < 6:
            raise ErroAplicacao(f"O produto na linha {numero} tem um formato inesperado.")

        item, quantidade, unidade, valor = (
            htmlhelper.texto_direto(spans[indice]) for indice in (0, 2, 3, 5)
        )
        if not all((item, quantidade, unidade, valor)):
            raise ErroAplicacao(f"O produto na linha {numero} tem campos vazios.")
        itens_data.append({
            "item": item,
            "quantidade": f"{quantidade} {unidade}",
            "valor": f"R$ {valor}",
        })

    if not itens_data:
        raise ErroAplicacao("A nota não contém produtos na tabela.")
    return itens_data


async def main(url: str, url_itens: str) -> None:
    url = normalizar_url_nfce(url)
    headers = {"Referer": url, "User-Agent": "Mozilla/5.0"}
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SEGUNDOS)

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                resposta = await load_data(session, url, url_itens)
            break
        except (aiohttp.ClientError, TimeoutError, UnicodeError) as erro:
            mensagem = TratadorErros.classificar_consulta(erro, TIMEOUT_SEGUNDOS)
            if tentativa == MAX_TENTATIVAS:
                raise ErroConsulta(
                    f"{mensagem} Consulta encerrada após {tentativa} tentativas."
                ) from erro
            await asyncio.sleep(tentativa)
    for item in extrair_itens(resposta):
        print(item)


def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        try:
            if __package__:
                from .scanner import scanner
            else:
                from scanner import scanner
        except (ImportError, OSError) as erro:
            raise TratadorErros.falha_dependencias() from erro

        url = scanner()
        if url is None:
            print("Leitura do QR Code cancelada.", file=sys.stderr)
            return 1

        url_itens = montar_url_itens(url)
        asyncio.run(main(url, url_itens))
    except ErroAplicacao as erro:
        return TratadorErros.exibir(erro)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(cli())
