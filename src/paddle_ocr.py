from paddleocr import PaddleOCR
from pathlib import Path
import numpy as np


# Criamos o modelo uma única vez
ocr = PaddleOCR(
    text_detection_model_dir=str(Path(__file__).resolve().parents[1] / "models/PP-OCRv6_medium_det"),
    text_recognition_model_dir=str(Path(__file__).resolve().parents[1] / "models/PP-OCRv6_medium_rec"),
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)


def ler_com_paddle(imagem, retornar_blocos=False):
    resultados = ocr.predict(imagem)

    linhas = []
    blocos = []

    for resultado in resultados:
        dados = resultado.json

        if "res" in dados:
            dados = dados["res"]

        textos = dados.get("rec_texts", [])
        caixas = dados.get("rec_boxes", [])
        confiancas = dados.get("rec_scores", [])
        poligonos = dados.get("rec_polys", [])
        inclinacoes = []
        for p in poligonos:
            dx = p[1][0] - p[0][0]
            if dx > 20:
                inclinacoes.append((p[1][1] - p[0][1]) / dx)
        inclinacao = float(np.median(inclinacoes)) if inclinacoes else 0.0

        for i, texto in enumerate(textos):
            texto = texto.strip()

            if not texto:
                continue

            linhas.append(texto)

            if i < len(caixas):
                caixa = caixas[i]

                bloco = {
                    "texto": texto,
                    "x1": int(caixa[0]),
                    "y1": int(caixa[1]),
                    "x2": int(caixa[2]),
                    "y2": int(caixa[3]),
                }
                bloco['y1_original'] = bloco['y1']
                bloco['y2_original'] = bloco['y2']
                # Coordenadas virtuais: alinham as linhas sem deformar a foto.
                deslocamento = inclinacao * (caixa[0] + caixa[2]) / 2
                bloco["y1"] = int(caixa[1] - deslocamento)
                bloco["y2"] = int(caixa[3] - deslocamento)
                if i < len(poligonos):
                    ys = [float(p[1]) - inclinacao * float(p[0]) for p in poligonos[i]]
                    bloco['y1'] = round(min(ys))
                    bloco['y2'] = round(max(ys))

                if i < len(confiancas):
                    bloco["confianca"] = float(confiancas[i])

                blocos.append(bloco)

    texto_final = "\n".join(linhas)

    if retornar_blocos:
        return texto_final, blocos

    return texto_final
