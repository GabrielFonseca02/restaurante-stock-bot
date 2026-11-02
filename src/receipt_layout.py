"""Associação de itens e conferência de valores com evidência espacial.

Os valores do rodapé nunca são usados para inventar produtos ou preços.
"""
import re
import statistics
import unicodedata
from decimal import Decimal, ROUND_HALF_UP


MONEY = re.compile(r'(?<![\d.,])(-?\d+[.,]\d{2})(?!\d)')
QUANTITY = re.compile(r'(?<![\w.,])(\d+(?:[.,]\d+)?|[.,]\d+)\s*(KG|KGS|KS|UN|UND|UNID|PC|PCS|L|LT|ML|G)(?![A-Z])', re.I)


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.upper()) if not unicodedata.combining(c)).replace('×', 'X')


def numero(texto):
    return Decimal(texto.replace(',', '.'))


def dinheiro(valor):
    return float(Decimal(str(valor)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def cy(b):
    return (b['y1'] + b['y2']) / 2


def altura(b):
    return max(1, b['y2'] - b['y1'])


def escala(blocos):
    return statistics.median(altura(b) for b in blocos) if blocos else 20


def eh_rodape(texto):
    t = normalizar(texto)
    return bool(re.search(r'(?:TOTAL|TUTAL).*I(?:TEN|EN|TAN)|(?:VALOR|JALOR|VALAR|ALOR)\s+(?:TOTAL|A PAGAR)|FORMA.*PAGAMENTO', t))


def area_itens(blocos):
    fim = min((cy(b) for b in blocos if eh_rodape(b['texto'])), default=float('inf'))
    return [b for b in blocos if cy(b) < fim], fim


def ancora(b):
    texto = b['texto'].strip()
    # Índice do item e código podem vir juntos ou apenas o código.
    m = re.match(r'^(?:(?P<item>[\dJDO]{1,3})\s+)?(?P<codigo>[\dO]{1,14})\s+(?P<desc>.*[A-Za-zÀ-ÿ].*)$', texto)
    if not m:
        return None
    desc = m['desc']
    if re.search(r'DOCUMENTO|CNPJ|TOTAL|PAGAR|CEP|CHAVE|EMISSAO|RUA|LOJA|TRIB|PROTOCOLO', normalizar(desc)):
        return None
    # Blocos numéricos/quantidade não são descrições.
    if re.match(r'^(?:KG|UN|PC|G|L)\s*(?:X|[\d.,]|$)', normalizar(desc)):
        return None
    q = QUANTITY.search(desc)
    inline = q if q and re.search(r'\s*[Xx×]\s*\d+[.,]\d{2}', desc[q.end():]) else None
    if inline:
        desc = desc[:inline.start()].strip()
    if len(re.findall(r'[A-Za-zÀ-ÿ]', desc)) < 3:
        return None
    item = m['item']
    if item:
        item = item.translate(str.maketrans({'J':'0', 'D':'0', 'O':'0'}))
    return dict(bloco=b, descricao=desc, codigo=m['codigo'].replace('O','0'),
                item=int(item) if item and item.isdigit() else None, inline=inline)


def extrair_espacial(blocos):
    regiao, _ = area_itens(blocos)
    h = escala(regiao)
    ancoras = [a for b in regiao if (a := ancora(b))]
    # Código em bloco isolado + descrição em outro bloco na mesma linha.
    codigos = [b for b in regiao if re.fullmatch(r'\d{1,14}', b['texto'].strip())]
    for b in regiao:
        t = b['texto'].strip()
        if any(a['bloco'] is b for a in ancoras) or not re.search(r'[A-Za-zÀ-ÿ]{3}', t):
            continue
        if re.search(r'CNPJ|FISCAL|DOCUMENTO|TOTAL|PAGAR|CODIGO|DESCRI|UNIT|CNPJ|RUA|GOIANIA|AVENIDA|FONE|TELEFONE', normalizar(t)):
            continue
        candidatos = [c for c in codigos if c['x2'] < b['x1'] and abs(cy(c)-cy(b)) < h*.55]
        if candidatos:
            c = min(candidatos, key=lambda c:b['x1']-c['x2'])
            ancoras.append(dict(bloco=b, descricao=t, codigo=c['texto'].strip(), item=None, inline=None))
    ancoras.sort(key=lambda a: cy(a['bloco']))
    qblocos = []
    for b in regiao:
        t = b['texto'].strip().replace('×', 'x')
        q = QUANTITY.match(t)
        if q:
            qblocos.append((b, q))
    precos = [(b, numero(b['texto'].strip())) for b in regiao if MONEY.fullmatch(b['texto'].strip())]
    usados = set()
    produtos = []
    for i, a in enumerate(ancoras):
        b = a['bloco']
        proximo = cy(ancoras[i+1]['bloco']) if i+1<len(ancoras) else float('inf')
        anterior = cy(ancoras[i-1]['bloco']) if i else -float('inf')
        qtd_candidatos = [(qb, q) for qb,q in qblocos if cy(qb) >= cy(b)-h*.6 and cy(qb) < proximo-h*.3]
        if a['inline']:
            # Localiza a quantidade na string original para preservar preço inline.
            q = QUANTITY.search(b['texto'])
            qtd_candidatos = [(b,q)]
        if not qtd_candidatos:
            continue
        qb,q = min(qtd_candidatos, key=lambda p:abs(cy(p[0])-cy(b)))
        quantidade = numero(q[1])
        unidade = {'KGS':'KG','KS':'KG','UND':'UN','UNID':'UN','PC':'UN','PCS':'UN','LT':'L'}.get(q[2].upper(), q[2].upper())
        restante = qb['texto'][q.end():]
        inline_precos = MONEY.findall(restante)
        pu = numero(inline_precos[0]) if inline_precos else None
        total_inline = numero(inline_precos[-1]) if len(inline_precos) > 1 else None
        vizinhos = [(pb,p) for pb,p in precos if pb['x1'] >= qb['x1'] and abs(cy(pb)-cy(qb)) <= max(h,altura(qb))*.85 and cy(pb)>anterior+h*.2 and cy(pb)<proximo]
        vizinhos.sort(key=lambda p:p[0]['x1'])
        if pu is None and len(vizinhos)>=2:
            pu = vizinhos[0][1]
            vizinhos = vizinhos[1:]
        if pu is None:
            continue
        esperado = dinheiro(quantidade*pu)
        totais = [(pb,p) for pb,p in vizinhos if id(pb) not in usados and abs(float(p)-esperado)<=.03]
        if total_inline is not None and abs(float(total_inline)-esperado)<=.03:
            pt = total_inline
        elif totais:
            pb,pt = min(totais, key=lambda p:abs(cy(p[0])-cy(qb)))
            usados.add(id(pb))
        else:
            continue
        if quantidade<=0 or pu<=0 or (unidade=='UN' and quantidade!=quantidade.to_integral_value()):
            continue
        desc = a['descricao']
        # Continuação da descrição à direita, alinhada e antes da quantidade.
        for extra in sorted(regiao, key=lambda x:x['x1']):
            if extra is b or extra is qb or extra['x1'] < b['x2']-h*.3 or extra['x2'] > qb['x1'] or abs(cy(extra)-cy(b))>h*.5:
                continue
            if re.search(r'[A-Za-zÀ-ÿ]{3}', extra['texto']) and not ancora(extra):
                desc += ' '+extra['texto'].strip()
        produtos.append(dict(descricao=desc, quantidade=float(quantidade), unidade=unidade,
                             preco_unitario=float(pu), preco_total=float(pt), item=a['item'],
                             codigo=a['codigo'], origem_quantidade='ocr', metodo='associacao_espacial'))
    return produtos


def cancelamentos(blocos):
    eventos = []
    for b in blocos:
        m = re.search(r'CANCELAMENTO\s+DE\s+ITEM\s*:?\s*(\d+)', normalizar(b['texto']))
        if m:
            eventos.append(dict(item=int(m[1]), texto=b['texto']))
    return eventos


def aplicar_cancelamentos(blocos, produtos):
    ids = {e['item'] for e in cancelamentos(blocos)}
    for p in produtos:
        if p.get('item') in ids:
            p['cancelado'] = True
    return produtos


def rotulo_valor(blocos, padrao):
    h = escala(blocos)
    for b in sorted(blocos, key=cy):
        t = normalizar(b['texto'])
        if not re.search(padrao, t):
            continue
        inline = MONEY.findall(t)
        if inline:
            return float(numero(inline[-1]))
        candidatos = [(p, numero(p['texto'].strip())) for p in blocos
                      if p['x1'] > b['x2'] and abs(cy(p)-cy(b)) <= h*.8 and MONEY.fullmatch(p['texto'].strip())]
        if candidatos:
            return float(min(candidatos,key=lambda p:abs(cy(p[0])-cy(b)))[1])
    return None


def totais_declarados(blocos):
    return dict(bruto=rotulo_valor(blocos,r'^(?:VALOR|JALOR|VALAR|ALOR)\s+TOTAL\b'),
                liquido=rotulo_valor(blocos,r'^(?:VALOR|JALOR|VALAR|ALOR)\s+A PAGAR\b'))


def ajustes(blocos):
    """Cada rótulo monetário é usado uma vez; percentuais não viram valores."""
    h = escala(blocos)
    _, fim = area_itens(blocos)
    # Ajustes de rodapé ficam antes do pagamento, evitando textos promocionais.
    pagamento = min((cy(b) for b in blocos if re.search(r'FORMA.*PAGAMENTO', normalizar(b['texto']))), default=fim+h*8)
    eventos = []
    usados = set()
    for b in sorted(blocos,key=cy):
        t = normalizar(b['texto'])
        if cy(b)>pagamento or not re.match(r'^\s*(DESCONTO|ACRESCIMO)\b',t) or ' / ' in t:
            continue
        tipo = 'desconto' if t.startswith('DESCONTO') else 'acrescimo'
        candidatos = []
        if '%' not in t and (m := MONEY.search(t)):
            candidatos.append((b, numero(m[1]), True))
        for p in blocos:
            if id(p) in usados or abs(cy(p)-cy(b))>h*.65 or p['x1'] < b['x2']:
                continue
            texto = p['texto'].strip()
            if '%' in texto:
                continue
            m = MONEY.search(texto)
            if m and (texto.upper().startswith('R$') or MONEY.fullmatch(texto)):
                candidatos.append((p, numero(m[1]), texto.upper().startswith('R$') or m[1].startswith('-')))
        if not candidatos:
            continue
        # Valor com R$ ou sinal tem precedência sobre o subtotal após desconto.
        p,valor,_ = min(candidatos, key=lambda v:(not v[2],abs(cy(v[0])-cy(b)),v[0]['x1']))
        usados.add(id(p))
        valor = abs(valor)*(-1 if tipo=='desconto' else 1)
        eventos.append(dict(tipo=tipo, valor=float(valor), texto=b['texto'], origem=p['texto']))
    return eventos


def verificar_valor(blocos, produtos):
    declarados = totais_declarados(blocos)
    eventos = ajustes(blocos)
    ativos = [p for p in produtos if not p.get('cancelado')]
    bruto = sum((Decimal(str(p['preco_total'])) for p in ativos),Decimal(0))
    ajustes_total = sum((Decimal(str(e['valor'])) for e in eventos),Decimal(0))
    liquido = bruto+ajustes_total
    # Sem valor a pagar, VALOR TOTAL é conferido como bruto; nunca subtrair
    # desconto global de um total que pode já estar líquido por conveniência.
    modo = 'liquido' if declarados['liquido'] is not None else 'bruto'
    declarado = declarados[modo]
    calculado = dinheiro(liquido if modo=='liquido' else bruto)
    diferenca = dinheiro(Decimal(str(declarado))-Decimal(str(calculado))) if declarado is not None else None
    nao_resolvidos = [e for e in cancelamentos(blocos) if not any(p.get('item')==e['item'] and p.get('cancelado') for p in produtos)]
    status = 'NAO_VERIFICADO' if declarado is None else ('OK' if abs(diferenca)<=.02 and not nao_resolvidos else 'REVISAO_NECESSARIA')
    return dict(status=status,valor_declarado=declarado,valor_calculado=calculado,diferenca=diferenca,
                criterio=modo,valor_bruto_calculado=dinheiro(bruto),valor_liquido_calculado=dinheiro(liquido),
                valor_bruto_declarado=declarados['bruto'],valor_liquido_declarado=declarados['liquido'],
                ajustes=eventos,ajustes_total=dinheiro(ajustes_total),cancelamentos_nao_resolvidos=nao_resolvidos)


def verificar_quantidade(blocos, produtos, declarado):
    linhas = len(produtos)
    ativos = [p for p in produtos if not p.get('cancelado')]
    unidades = sum(int(p['quantidade']) if p['unidade']=='UN' else 1 for p in ativos)
    invalidos = [p for p in ativos if p['quantidade']<=0 or (p['unidade']=='UN' and abs(p['quantidade']-round(p['quantidade']))>.001)]
    regiao,_ = area_itens(blocos)
    ids = {a['item'] for b in regiao if (a:=ancora(b)) and a['item'] is not None}
    sequencia = bool(ids) and ids==set(range(1,max(ids)+1))
    # O índice impresso distingue número de linhas de unidades. Não decidir
    # simplesmente pelo candidato extraído que mais se aproxima do declarado.
    cancelados_documento = {e['item'] for e in cancelamentos(blocos) if e['item'] in ids}
    if sequencia and declarado==max(ids):
        modo = 'linhas'
    elif sequencia and cancelados_documento and declarado==max(ids)-len(cancelados_documento):
        modo = 'linhas_ativas'
    else:
        modo = 'unidades'
    calculado = linhas if modo=='linhas' else (len(ativos) if modo=='linhas_ativas' else unidades)
    diferenca = declarado-calculado if declarado is not None else None
    status = 'NAO_VERIFICADO' if declarado is None else ('OK' if diferenca==0 and not invalidos else 'REVISAO_NECESSARIA')
    return dict(status=status,itens_declarados=declarado,itens_calculados=calculado,
                linhas_extraidas=linhas,linhas_ativas=len(ativos),unidades_calculadas=unidades,
                linhas_documento=max(ids) if sequencia else None,criterio=modo,
                criterio_origem='sequencia_impressa' if modo.startswith('linhas') else 'sem_evidencia_de_contagem_por_linhas',
                diferenca=diferenca,produtos_com_quantidade_invalida=len(invalidos))
