"""Relatório das verificações e indícios; não usa totais como verdade textual."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw


PASTA = Path('resultados/avaliacao-001-051')


def main():
    resumo = json.loads((PASTA / 'resumo.json').read_text(encoding='utf-8'))
    hashes = {}
    linhas = []
    for item in resumo:
        caminho = Path(item['arquivo'])
        dados = json.loads((PASTA / f'{caminho.stem}.json').read_text(encoding='utf-8'))
        texto = (PASTA / f'{caminho.stem}.txt').read_text(encoding='utf-8') if 'erro' not in item else ''
        motivos, indicios = [], []
        if 'erro' in item:
            motivos.append(item['erro'])
        else:
            q, v = item['quantidade'], item['valor']
            if not item['linhas_extraidas']:
                motivos.append('nenhum produto estruturado')
            if q['status'] == 'NAO_VERIFICADO':
                motivos.append('quantidade declarada não localizada pelo parser')
            elif q['status'] != 'OK':
                motivos.append(f"quantidade: declarado {q['itens_declarados']}, calculado {q['itens_calculados']}")
            if v['status'] == 'NAO_VERIFICADO':
                motivos.append('valor declarado não localizado pelo parser')
            elif v['status'] != 'OK':
                motivos.append(f"valor: declarado {v['valor_declarado']:.2f}, calculado {v['valor_calculado']:.2f}")
            if re.search(r'DESCONTO|ACRESCIMO|ACRÉSCIMO', texto, re.I):
                indicios.append('descontos/acréscimos: parser não aplica ajustes ao total')
            if re.search(r'CANCELAMENTO|CANCELADO', texto, re.I):
                indicios.append('item cancelado: parser não exclui cancelamentos')
            invalidos = [p for p in dados['produtos'] if p['quantidade'] <= 0 or (p['unidade'] == 'UN' and abs(p['quantidade']-round(p['quantidade'])) > .001)]
            if invalidos:
                indicios.append(f'{len(invalidos)} produtos com quantidade zero/negativa ou UN fracionário: associação/inferência inválida')
            if re.search(r'\d[:;]\d{2}\b', texto):
                indicios.append('separador decimal possivelmente trocado; conferir horários antes de atribuir erro')
            if re.search(r'(?<![\d.,])\b\d{3,4}\s*KG\b', texto, re.I):
                indicios.append('quantidade em KG sem separador: possível perda de decimal')
            rotulos = [l.strip() for l in texto.splitlines() if re.search(r'TOTAL|PAGAR|ITENS|ÍTENS|IENS', l, re.I)]
            if q['status'] == 'NAO_VERIFICADO' and re.search(r'ITENS|IENS', texto, re.I):
                indicios.append('texto de contagem presente, mas rótulo/alinhamento não suportado')
            if v['status'] == 'NAO_VERIFICADO' and re.search(r'TOTAL|PAGAR', texto, re.I):
                indicios.append('texto de total presente, mas rótulo/alinhamento não suportado')
            baixa = item['blocos_baixa_confianca'] / max(1, item['blocos_detectados'])
            if baixa > .15:
                indicios.append(f'{baixa:.0%} dos blocos têm confiança menor que 0,80')
            if item['linhas_extraidas'] and q['status'] == 'REVISAO_NECESSARIA':
                indicios.append('itens ausentes/associação incorreta ou regra de contagem diferente; exige inspeção')
        digest = hashlib.sha256(caminho.read_bytes()).hexdigest()
        duplicado = hashes.get(digest, '')
        hashes.setdefault(digest, caminho.stem)
        linhas.append(dict(cupom=caminho.stem, aprovado=item['aprovado_verificacoes'],
                           produtos=item.get('linhas_extraidas', 0), motivos='; '.join(motivos),
                           indicios='; '.join(indicios), duplicado_de=duplicado,
                           rotulos=' | '.join(rotulos) if 'erro' not in item else ''))
    with (PASTA / 'diagnostico.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=linhas[0].keys())
        writer.writeheader()
        writer.writerows(linhas)
    aprovados = [l['cupom'] for l in linhas if l['aprovado']]
    falhas = [l for l in linhas if not l['aprovado']]
    estatisticas = dict(total=len(resumo), aprovados=len(aprovados), reprovados=len(falhas),
                        erros_execucao=sum('erro' in i for i in resumo),
                        quantidade=dict(Counter(i.get('quantidade', {}).get('status', 'ERRO') for i in resumo)),
                        valor=dict(Counter(i.get('valor', {}).get('status', 'ERRO') for i in resumo)),
                        sem_produtos=sum(i.get('linhas_extraidas', 0) == 0 for i in resumo),
                        com_produtos=sum(i.get('linhas_extraidas', 0) > 0 for i in resumo),
                        falhas_com_confianca_media_95=sum(not i['aprovado_verificacoes'] and (i.get('confianca_media') or 0) >= .95 for i in resumo),
                        segundos_total=round(sum(i['segundos'] for i in resumo), 2),
                        imagens_unicas=len(hashes), copias_identicas=sum(bool(l['duplicado_de']) for l in linhas))
    (PASTA / 'estatisticas.json').write_text(json.dumps(estatisticas, ensure_ascii=False, indent=2), encoding='utf-8')
    texto = ['# Avaliação dos cupons 001 a 051', '',
             f'{len(aprovados)} de {len(linhas)} passaram nas duas verificações ({len(aprovados)/len(linhas):.1%}).', '',
             'Critério: pelo menos um produto, quantidade com status OK e valor com status OK. '
             'NAO_VERIFICADO conta como falha. Totais iguais não comprovam descrições, códigos e quantidades individuais corretos. '
             'Não há transcrição manual de referência para medir a precisão real do OCR.', '',
             'Configuração congelada: PaddleOCR 3.7.0, paddlepaddle 3.2.0, PP-OCRv6_medium_det/rec locais; '
             'orientação/unwarping desativados; pré-processamento e parser atuais.', '',
             'Aprovados: ' + ', '.join(aprovados), '',
             f'Imagens repetidas por SHA-256 dentro da amostra: {sum(bool(l["duplicado_de"]) for l in linhas)}. '
             'Fotos distintas do mesmo documento não são detectadas por esse critério.', '',
             f"Execuções com erro: {estatisticas['erros_execucao']}; com algum produto estruturado: {estatisticas['com_produtos']}; sem produtos: {estatisticas['sem_produtos']}. "
             f"Tempo somado: {estatisticas['segundos_total']:.2f}s. Reprovações com confiança média ≥95%: {estatisticas['falhas_com_confianca_media_95']}.", '',
             'Quantidade: ' + str(estatisticas['quantidade']) + '. Valor: ' + str(estatisticas['valor']) + '.', '',
             '## Cupons que não passaram', '', '| Cupom | Produtos | Falha nas verificações | Indícios para investigar |',
             '|---|---:|---|---|']
    for l in falhas:
        texto.append(f"| [{l['cupom']}]({l['cupom']}.txt) | {l['produtos']} | {l['motivos']} | {l['indicios'] or 'Inspecionar foto e blocos para separar OCR de parser.'} |")
    texto += ['', '## Limitações identificadas no código', '',
              '- Parser antigo usa colunas fixas em 45–72% da largura e tolerâncias em pixels; layouts/resoluções diferentes quebram associações.',
              '- Parser tabular exige quantidade/unidade e dois preços na mesma linha; blocos unidos ou fragmentados e papel curvo geram perdas/associações ambíguas.',
              '- Os rótulos de conferência são restritos e os valores precisam estar à direita e próximos; rótulos fragmentados ficam NAO_VERIFICADO.',
              '- DESCONTO e acréscimos não são contabilizados. Comparar soma bruta com valor líquido pode reprovar leitura válida.',
              '- A contagem soma quantidades UN; algumas lojas declaram linhas comerciais, não unidades. É necessário identificar a regra do emissor.',
              '- A correção matemática de quantidade pode esconder falhas do OCR. É preciso guardar origem e sinalizar inferência para revisão.',
              '- O recorte usa limiar fixo 160 e retângulo mínimo, sem validar preservação do texto; pode cortar/girar papel.',
              '- Uma única inclinação mediana não corrige curvatura ou perspectiva variável. Orientação e unwarping estão desligados.', '',
              'As causas visuais confirmadas e exemplos específicos constam em revisao-visual.md. Os indícios automáticos acima não são diagnósticos confirmados.']
    (PASTA / 'relatorio.md').write_text('\n'.join(texto), encoding='utf-8')
    # Pranchas de inspeção; imagens originais não são modificadas.
    for pagina in range((len(resumo)+11)//12):
        canvas = Image.new('RGB', (1200, 1080), 'white')
        draw = ImageDraw.Draw(canvas)
        for pos, item in enumerate(resumo[pagina*12:(pagina+1)*12]):
            p = Path(item['arquivo'])
            img = ImageOps.contain(Image.open(p).convert('RGB'), (285, 325))
            x, y = (pos % 4)*300, (pos//4)*360
            canvas.paste(img, (x+(300-img.width)//2, y+25))
            draw.text((x+8,y+5), f"{p.stem}: {'OK' if item['aprovado_verificacoes'] else 'REVISAR'}", fill='black')
        canvas.save(PASTA / f'contato-{pagina+1}.jpg')
    print(json.dumps(dict(total=len(linhas), aprovados=len(aprovados), falhas=len(falhas),
                          falharam=[l['cupom'] for l in falhas]), ensure_ascii=False))


if __name__ == '__main__':
    main()
