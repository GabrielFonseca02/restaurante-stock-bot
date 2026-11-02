import unittest
import json
from pathlib import Path
from src.parser_paddle import extrair_produtos_paddle, verificar_quantidade_itens, verificar_valor_total


def bloco(texto, x, y, largura=300):
    return dict(texto=texto, x1=x, x2=x+largura, y1=y, y2=y+20)


class ParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.casos = json.loads((Path(__file__).parent/'fixtures/parser-casos.json').read_text(encoding='utf-8'))

    def test_quantidade_preco_integrados_e_multiplicacao_unicode(self):
        blocos = [bloco('01 07898040082635 BATATA PALITO 2KG', 0, 0),
                  bloco('1 UN × 23,99 T01', 300, 25), bloco('23,99', 650, 25, 60)]
        produtos = extrair_produtos_paddle(blocos)
        self.assertEqual(len(produtos), 1)
        self.assertEqual(produtos[0]['preco_total'], 23.99)
        self.assertEqual(produtos[0]['descricao'], 'BATATA PALITO 2KG')

    def test_layout_tabular(self):
        blocos = [bloco('001 7897173600105 BROTOS ALFAFA', 0, 0),
                  bloco('1UN', 400, 0, 50), bloco('26,99', 500, 0, 60),
                  bloco('26,99', 600, 0, 60)]
        produtos = extrair_produtos_paddle(blocos)
        self.assertEqual(produtos[0]['descricao'], 'BROTOS ALFAFA')
        self.assertEqual(produtos[0]['preco_total'], 26.99)

    def test_nao_aceita_linha_tabular_com_conta_inconsistente(self):
        blocos = [bloco('001 7897173600105 BROTOS ALFAFA 2UN 26,99 26,99', 0, 0, 700)]
        self.assertEqual(extrair_produtos_paddle(blocos), [])

    def test_tres_cortes_com_codigo_separado_sem_x(self):
        blocos = self.casos['22']
        produtos = extrair_produtos_paddle(blocos)
        self.assertEqual([p['descricao'] for p in produtos], ['Picanha Grill Angus']*3)
        self.assertEqual([p['quantidade'] for p in produtos], [1.35,1.21,1.336])
        self.assertEqual([p['preco_total'] for p in produtos], [134.99,120.99,133.59])
        self.assertEqual(verificar_valor_total(blocos,produtos)['status'], 'OK')

    def test_quantidade_inline_nao_contamina_descricao(self):
        produtos = extrair_produtos_paddle(self.casos['49'])
        self.assertEqual([p['descricao'] for p in produtos], ['FLU BATATA KG','FLV BATATA KG'])
        self.assertEqual([p['quantidade'] for p in produtos], [2.15,1.915])
        self.assertEqual([p['preco_total'] for p in produtos], [15.03,13.39])

    def test_descontos_nao_duplicam_subtotal_nem_percentual(self):
        blocos = self.casos['32']
        produtos = extrair_produtos_paddle(blocos)
        self.assertEqual(produtos[1]['descricao'], 'ASPARGO VERDE IMPORTADO PR 450G')
        resultado = verificar_valor_total(blocos,produtos)
        self.assertEqual(resultado['valor_bruto_calculado'],99.97)
        self.assertEqual(resultado['ajustes_total'],-30)
        self.assertEqual(len(resultado['ajustes']),2)
        self.assertEqual(resultado['valor_liquido_calculado'],69.97)
        self.assertEqual(resultado['status'],'OK')

    def test_cancelamento_preserva_auditoria_e_exclui_da_soma(self):
        blocos = self.casos['10']
        produtos = extrair_produtos_paddle(blocos)
        self.assertEqual(len(produtos),3)
        self.assertTrue(produtos[0]['cancelado'])
        self.assertEqual([p['preco_total'] for p in produtos if not p.get('cancelado')],[14.79,16.99])
        self.assertEqual(verificar_valor_total(blocos,produtos)['valor_calculado'],31.78)
        self.assertEqual(verificar_quantidade_itens(blocos,produtos)['status'],'OK')

    def test_cancelamento_sem_item_identificado_nao_aprova(self):
        blocos = self.casos['10']
        produtos = extrair_produtos_paddle(blocos)[1:]
        self.assertEqual(verificar_valor_total(blocos,produtos)['status'],'REVISAO_NECESSARIA')

    def test_contagem_de_linhas_ativas_apos_cancelamento(self):
        from src.receipt_layout import verificar_quantidade
        blocos = self.casos['10']
        produtos = extrair_produtos_paddle(blocos)
        produtos[1]['quantidade'] = 2
        resultado = verificar_quantidade(blocos,produtos,2)
        self.assertEqual(resultado['criterio'],'linhas_ativas')
        self.assertEqual(resultado['status'],'OK')

    def test_contagem_por_linhas_com_evidencia_impressa(self):
        blocos = self.casos['50']
        produtos = extrair_produtos_paddle(blocos)
        resultado = verificar_quantidade_itens(blocos,produtos)
        self.assertEqual(resultado['linhas_documento'],7)
        self.assertEqual(resultado['unidades_calculadas'],9)
        self.assertEqual(resultado['criterio'],'linhas')
        self.assertEqual(resultado['status'],'OK')
        self.assertEqual(verificar_quantidade_itens(blocos,produtos[:-1])['status'],'REVISAO_NECESSARIA')

    def test_contagem_por_unidades_do_layout_anterior(self):
        blocos = self.casos['1']
        produtos = extrair_produtos_paddle(blocos)
        self.assertEqual(len(produtos),14)
        resultado = verificar_quantidade_itens(blocos,produtos)
        self.assertEqual(resultado['criterio'],'unidades')
        self.assertEqual(resultado['itens_calculados'],16)
        self.assertEqual(verificar_valor_total(blocos,produtos)['valor_calculado'],472.09)

    def test_acrescimo_global(self):
        blocos = [bloco('VALOR TOTAL R$',0,100),bloco('10,00',400,100,60),
                  bloco('ACRESCIMO R$ 2,00',0,125),bloco('VALOR A PAGAR R$',0,150),bloco('12,00',400,150,60)]
        produtos = [dict(quantidade=1,unidade='UN',preco_unitario=10,preco_total=10)]
        resultado = verificar_valor_total(blocos,produtos)
        self.assertEqual(resultado['ajustes_total'],2)
        self.assertEqual(resultado['valor_calculado'],12)
        self.assertEqual(resultado['status'],'OK')

    def test_percentual_sem_moeda_nao_vira_desconto(self):
        blocos = [bloco('DESCONTO 10%',0,0),bloco('VALOR A PAGAR R$',0,100),bloco('10,00',400,100,60)]
        produtos = [dict(quantidade=1,unidade='UN',preco_unitario=10,preco_total=10)]
        self.assertEqual(verificar_valor_total(blocos,produtos)['ajustes_total'],0)


if __name__ == '__main__':
    unittest.main()
