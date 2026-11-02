"""Reprocessa os mesmos blocos OCR, isolando a melhoria do parser."""
import json
from pathlib import Path
from src.parser_paddle import extrair_produtos_paddle, verificar_quantidade_itens, verificar_valor_total


def main():
    origem = Path('resultados/avaliacao-001-051')
    destino = Path('resultados/parser-melhorado')
    destino.mkdir(exist_ok=True)
    comparacao = []
    for numero in range(1, 52):
        nome = f'cupom-{numero:03d}'
        antes = json.loads((origem / f'{nome}.json').read_text(encoding='utf-8'))
        blocos = antes['blocos']
        produtos = extrair_produtos_paddle(blocos)
        q = verificar_quantidade_itens(blocos, produtos)
        v = verificar_valor_total(blocos, produtos)
        aprovado = bool(produtos) and q['status']=='OK' and v['status']=='OK'
        depois = dict(arquivo=antes['arquivo'], produtos=produtos, quantidade=q, valor=v, aprovado_verificacoes=aprovado)
        (destino/f'{nome}.json').write_text(json.dumps(depois,ensure_ascii=False,indent=2),encoding='utf-8')
        escrita = [nome, 'Descrição | Quantidade | Unidade | Unitário | Total | Situação']
        for p in produtos:
            escrita.append(f"{p['descricao']} | {p['quantidade']:g} | {p['unidade']} | {p['preco_unitario']:.2f} | {p['preco_total']:.2f} | {'CANCELADO' if p.get('cancelado') else 'ativo'}")
        escrita += [f"Ajustes: {v['ajustes_total']:.2f}", f"Valor calculado: {v['valor_calculado']:.2f}",
                    f"Quantidade: {q['status']} ({q['criterio']})", f"Valor: {v['status']}",
                    'Descrições preservam o OCR; esta escrita organiza os dados e não corrige letras por adivinhação.']
        (destino/f'{nome}.txt').write_text('\n'.join(escrita),encoding='utf-8')
        comp = dict(cupom=nome,antes=antes['aprovado_verificacoes'],depois=aprovado,
                    produtos_antes=len(antes['produtos']),produtos_depois=len(produtos),
                    quantidade_antes=antes['quantidade'],quantidade_depois=q,valor_antes=antes['valor'],valor_depois=v)
        comparacao.append(comp)
    (destino/'comparacao.json').write_text(json.dumps(comparacao,ensure_ascii=False,indent=2),encoding='utf-8')
    nantes = sum(c['antes'] for c in comparacao)
    ndepois = sum(c['depois'] for c in comparacao)
    relatorio = ['# Comparação do parser', '',
                 f'Aprovados: {nantes}/51 ({nantes/51:.1%}) → {ndepois}/51 ({ndepois/51:.1%}).', '',
                 'A comparação reutiliza exatamente os blocos da avaliação original, isolando mudanças de parser. '
                 'Não modifica a transcrição OCR original. Passar não comprova a grafia de todas as descrições.', '',
                 'Recuperados: '+', '.join(c['cupom'] for c in comparacao if not c['antes'] and c['depois'])+'.', '',
                 'Regressões: '+(', '.join(c['cupom'] for c in comparacao if c['antes'] and not c['depois']) or 'nenhuma')+'.', '',
                 '| Cupom | Produtos antes → depois | Quantidade depois | Valor depois |',
                 '|---|---:|---|---|']
    for c in comparacao:
        relatorio.append(f"| [{c['cupom']}]({c['cupom']}.txt) | {c['produtos_antes']} → {c['produtos_depois']} | {c['quantidade_depois']['status']} ({c['quantidade_depois']['criterio']}) | {c['valor_depois']['status']} |")
    relatorio += ['', '## Conferência dos casos evidentes', '',
                  '- 022: três linhas Picanha Grill Angus, código 207; 1,350/1,210/1,336 KG, unitário 99,99 e totais 134,99/120,99/133,59. Valores conferidos na foto.',
                  '- 049: duas linhas de batata, código 13504; 2,150/1,915 KG, unitário 6,99, totais 15,03/13,39. Quantidade/preço saíram da descrição e foram atribuídos aos campos corretos. Valores conferidos na foto.',
                  '- 032: mantém os preços brutos 29,99/34,99/34,99, registra dois descontos de 15,00 e calcula líquido 69,97. A continuação IMPORTADO PR 450G foi reunida à descrição do segundo aspargo.',
                  '- 010: registra três linhas; item 001 permanece para auditoria com cancelado=true. Dois produtos ativos somam 31,78.',
                  '- 050/051: mantém os sete produtos e o total 34,49; usa a sequência 01–07 como evidência de contagem por linhas, sem confundir com nove unidades.', '',
                  'A nova execução de OCR desses casos e do 001 está em ../parser-validacao-ocr/resumo.json. '
                  'As transcrições brutas e os blocos originais da avaliação de 51 cupons foram preservados.', '',
                  '## Limitações', '',
                  '- O parser anterior permanece como fallback para layouts ainda não cobertos. O candidato é escolhido pela consistência individual de quantidade × preço, e não por aproximação ao total do cupom.',
                  '- Inferências antigas ainda podem existir no fallback; quantidades zero e UN fracionário impedem aprovação da contagem.',
                  '- Sem sequência impressa completa, a regra de contagem por linhas ainda não é determinada. O resultado registra o critério adotado.',
                  '- Ajustes precisam de valor monetário explícito; não são derivados de percentuais. Cancelamento sem item identificado exige revisão.',
                  '- Texto coberto, separadores/dígitos perdidos e DANFE continuam exigindo tratamento adicional.']
    (destino/'relatorio.md').write_text('\n'.join(relatorio),encoding='utf-8')
    print(json.dumps(dict(aprovados_antes=sum(c['antes'] for c in comparacao),aprovados_depois=sum(c['depois'] for c in comparacao),
                         recuperados=[c['cupom'] for c in comparacao if not c['antes'] and c['depois']],
                         regressoes=[c['cupom'] for c in comparacao if c['antes'] and not c['depois']]),ensure_ascii=False))
    for c in comparacao:
        if c['cupom'] in ['cupom-010','cupom-022','cupom-032','cupom-049','cupom-050','cupom-051']:
            print(c['cupom'],c['produtos_antes'],c['produtos_depois'],c['quantidade_depois']['status'],c['valor_depois']['status'],c['valor_depois']['valor_calculado'])


if __name__ == '__main__':
    main()
