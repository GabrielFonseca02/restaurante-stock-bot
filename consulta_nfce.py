"""Consulta os itens de uma NFC-e da SEFAZ de Goiás."""

import argparse
import asyncio
import sys
from urllib.parse import parse_qs, urlencode, urlsplit
from xml.etree import ElementTree

import aiohttp

import htmlhelper


def montar_url_itens(url: str) -> str:
    partes = urlsplit(url)
    if partes.scheme not in ("http", "https") or partes.netloc != "nfe.sefaz.go.gov.br":
        raise ValueError("Informe uma URL http/https de nfe.sefaz.go.gov.br.")

    parametro = parse_qs(partes.query).get("p", [""])[0]
    chave = parametro.split("|", 1)[0]
    if len(chave) != 44 or not chave.isascii() or not chave.isdigit():
        raise ValueError("A URL deve conter uma chave de 44 dígitos no parâmetro p.")

    return (
        f"{partes.scheme}://{partes.netloc}/nfeweb/sites/nfce/render/html/danfeNFCe?"
        + urlencode({"chNFe": chave})
    )


async def load_data(session: aiohttp.ClientSession, url: str, url_itens: str) -> str:
    # A primeira consulta estabelece os cookies usados para carregar os itens.
    async with session.get(url) as pagina:
        pagina.raise_for_status()
        await pagina.read()

    async with session.get(url_itens) as itens:
        itens.raise_for_status()
        return await itens.text()


def extrair_itens(resposta: str) -> list[dict[str, str]]:
    try:
        xml = ElementTree.fromstring(resposta)
    except ElementTree.ParseError as erro:
        raise ValueError("A SEFAZ retornou uma resposta XML inválida.") from erro

    html_nota = xml.findtext("./PARAMS/DANFE_NFCE_HTML")
    if not html_nota or not html_nota.strip():
        status = xml.findtext("STATUS") or "não informado"
        raise ValueError(f"A resposta não trouxe o HTML da nota (status: {status}).")

    soup = htmlhelper.parse_html(html_nota)
    table = soup.find("table", id="tabResult")
    if table is None:
        raise ValueError("A tabela de produtos não foi encontrada na nota.")

    itens_data = []
    for numero, produto in enumerate(table.find_all("tr"), start=1):
        if produto.find("th") is not None:
            continue
        spans = produto.find_all("span")
        if len(spans) < 6:
            raise ValueError(f"O produto na linha {numero} tem um formato inesperado.")

        item, quantidade, unidade, valor = (
            htmlhelper.texto_direto(spans[indice]) for indice in (0, 2, 3, 5)
        )
        if not all((item, quantidade, unidade, valor)):
            raise ValueError(f"O produto na linha {numero} tem campos vazios.")
        itens_data.append({
            "item": item,
            "quantidade": f"{quantidade} {unidade}",
            "valor": f"R$ {valor}",
        })

    if not itens_data:
        raise ValueError("A nota não contém produtos na tabela.")
    return itens_data


async def main(url: str, url_itens: str) -> None:
    headers = {"Referer": url, "User-Agent": "Mozilla/5.0"}
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        resposta = await load_data(session, url, url_itens)
    for item in extrair_itens(resposta):
        print(item)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL completa do QR Code da NFC-e de Goiás")
    args = parser.parse_args()
    try:
        url_itens = montar_url_itens(args.url)
        asyncio.run(main(args.url, url_itens))
    except TimeoutError:
        print("Erro: a SEFAZ não respondeu em até 30 segundos.", file=sys.stderr)
        sys.exit(1)
    except (aiohttp.ClientError, ValueError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
