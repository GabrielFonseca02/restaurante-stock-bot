"""Avalia um intervalo de cupons e preserva evidências por arquivo."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from main import ler_cupom
from src.parser_paddle import extrair_produtos_paddle, verificar_quantidade_itens, verificar_valor_total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inicio', type=int, default=1)
    parser.add_argument('--fim', type=int, default=5)
    parser.add_argument('--saida', default='resultados')
    parser.add_argument('--cupons', type=int, nargs='+', help='Lista explícita de cupons; substitui inicio/fim')
    args = parser.parse_args()
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    resumo = []
    for numero in (args.cupons or range(args.inicio, args.fim + 1)):
        candidatos = list(Path('receipts/personal').glob(f'cupom-{numero:03d}.*'))
        caminho = candidatos[0] if len(candidatos) == 1 else Path(f'receipts/personal/cupom-{numero:03d}.jpeg')
        inicio = perf_counter()
        try:
            texto, blocos = ler_cupom(str(caminho), 'paddle')
            produtos = extrair_produtos_paddle(blocos)
            dados = dict(arquivo=str(caminho), segundos=round(perf_counter()-inicio, 2),
                         produtos=produtos, quantidade=verificar_quantidade_itens(blocos, produtos),
                         valor=verificar_valor_total(blocos, produtos), blocos=blocos)
            dados['aprovado_verificacoes'] = bool(produtos) and dados['quantidade']['status'] == 'OK' and dados['valor']['status'] == 'OK'
            dados['linhas_extraidas'] = len(produtos)
            dados['blocos_detectados'] = len(blocos)
            dados['confianca_media'] = round(sum(b.get('confianca', 0) for b in blocos)/len(blocos), 4) if blocos else None
            dados['blocos_baixa_confianca'] = sum(b.get('confianca', 0) < .8 for b in blocos)
            (destino / f'{caminho.stem}.txt').write_text(texto, encoding='utf-8')
        except Exception as erro:
            dados = dict(arquivo=str(caminho), erro=f'{type(erro).__name__}: {erro}', aprovado_verificacoes=False,
                         segundos=round(perf_counter()-inicio, 2))
        (destino / f'{caminho.stem}.json').write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
        resumo.append({k:v for k,v in dados.items() if k not in ('blocos', 'produtos')})
        (destino / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(resumo[-1], ensure_ascii=False), flush=True)
    (destino / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
