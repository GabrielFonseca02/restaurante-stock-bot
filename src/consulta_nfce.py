import htmlhelper
import aiohttp
import asyncio
from xml.etree import ElementTree
from tratamento_erros import ErroAplicacao, ErroConsulta, TratadorErros


try:
    import scanner
except (ImportError, OSError) as erro:
    raise SystemExit(TratadorErros.exibir(TratadorErros.falha_dependencias())) from erro

try:
    url = scanner.scanner()
except ErroAplicacao as erro:
    raise SystemExit(TratadorErros.exibir(erro)) from erro
except KeyboardInterrupt:
    raise SystemExit(130)

if url is None:
    raise SystemExit(
        TratadorErros.exibir(ErroAplicacao("Leitura do QR Code cancelada."))
    )

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/jxl,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Connection': 'keep-alive',
    'Referer': url,
    'Sec-Fetch-Dest': 'iframe',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-GPC': '1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not-A.Brand";v="99", "Brave";v="157", "Chromium";v="157"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"'
}

async def load_data(url):
    async with aiohttp.ClientSession() as session:
        get = await session.get(url, headers=headers)
        response = await get.text()
        html_inicial = htmlhelper.parse_html(response)
        iframe = html_inicial.find('iframe', {'class': 'iframe-danfe-nfce'})
        url_consulta = str(get.url.origin()) + iframe['src']
        url_consulta = url_consulta.replace('/render/danfeNFCe', '/render/html/danfeNFCe')

        get = await session.get(url_consulta, headers=headers)
        response = await get.text()

        return response

def extrair_itens(html):
    try:
        xml = ElementTree.fromstring(html)
    except ElementTree.ParseError as erro:
        raise TratadorErros.xml_invalido() from erro

    html_nota = xml.findtext("./PARAMS/DANFE_NFCE_HTML")
    if not html_nota or not html_nota.strip():
        status = xml.findtext("STATUS") or "não informado"
        raise ErroAplicacao(f"A resposta não trouxe o HTML da nota (status: {status}).")

    soup = htmlhelper.parse_html(html_nota)
    table = soup.find("table", id="tabResult")
    if table is None:
        raise ErroAplicacao("Não foi possível localizar a tabela de produtos na nota fiscal.")

    tr = table.find_all("tr")

    itens_data = []
    for produto in tr:
        if produto.find("th") is not None:
            continue

        span = produto.find_all("span")
        if len(span) < 5:
            raise ErroAplicacao("Uma linha de produto veio com campos faltando.")

        item = (span[0]).texto_direto
        quantidade = (span[2]).texto_direto
        unidade = (span[3]).texto_direto
        valor = (span[4]).texto_direto

        itens_data.append({
            "item": item,
            "quantidade": f"{quantidade} {unidade}",
            "valor": f"R$ {valor}",
        })

    return itens_data

def main():
    try:
        html_consulta = asyncio.run(load_data(url))
    except aiohttp.InvalidURL as erro:
        raise ErroConsulta("Não foi possível consultar a nota com a URL recebida.") from erro
    except (aiohttp.ClientError, TimeoutError, UnicodeError) as erro:
        timeout = aiohttp.client.DEFAULT_TIMEOUT.total
        raise ErroConsulta(TratadorErros.classificar_consulta(erro, timeout)) from erro

    print(extrair_itens(html_consulta))

try:
    main()
except ErroAplicacao as erro:
    raise SystemExit(TratadorErros.exibir(erro)) from erro
except KeyboardInterrupt:
    raise SystemExit(130)
