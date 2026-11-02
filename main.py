import sys
import os
import json

import cv2
import numpy as np
import pytesseract
from src.parser_paddle import (
    extrair_produtos_paddle,
    verificar_quantidade_itens,
    verificar_valor_total
)
from src.parser import extrair_produtos
from src.qr_reader import ler_qr_codes


def configurar_tesseract():
    """
    Procura o executável do Tesseract no Windows.
    """

    caminhos_possiveis = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]

    for caminho in caminhos_possiveis:
        if os.path.exists(caminho):
            pytesseract.pytesseract.tesseract_cmd = caminho
            return


def ordenar_pontos(pontos):
    """
    Ordena os quatro pontos de um retângulo:

    0 = superior esquerdo
    1 = superior direito
    2 = inferior direito
    3 = inferior esquerdo
    """

    pontos = pontos.reshape(4, 2)

    ordenados = np.zeros(
        (4, 2),
        dtype="float32"
    )

    soma = pontos.sum(axis=1)
    diferenca = np.diff(
        pontos,
        axis=1
    )

    ordenados[0] = pontos[np.argmin(soma)]
    ordenados[2] = pontos[np.argmax(soma)]

    ordenados[1] = pontos[np.argmin(diferenca)]
    ordenados[3] = pontos[np.argmax(diferenca)]

    return ordenados


def corrigir_perspectiva(imagem, pontos):
    """
    Recebe os quatro cantos aproximados do cupom
    e gera uma imagem reta.
    """

    pontos = ordenar_pontos(pontos)

    superior_esquerdo = pontos[0]
    superior_direito = pontos[1]
    inferior_direito = pontos[2]
    inferior_esquerdo = pontos[3]

    largura1 = np.linalg.norm(
        inferior_direito - inferior_esquerdo
    )

    largura2 = np.linalg.norm(
        superior_direito - superior_esquerdo
    )

    largura = int(
        max(largura1, largura2)
    )

    altura1 = np.linalg.norm(
        superior_direito - inferior_direito
    )

    altura2 = np.linalg.norm(
        superior_esquerdo - inferior_esquerdo
    )

    altura = int(
        max(altura1, altura2)
    )

    destino = np.array(
        [
            [0, 0],
            [largura - 1, 0],
            [largura - 1, altura - 1],
            [0, altura - 1],
        ],
        dtype="float32"
    )

    matriz = cv2.getPerspectiveTransform(
        pontos,
        destino
    )

    imagem_corrigida = cv2.warpPerspective(
        imagem,
        matriz,
        (largura, altura)
    )

    return imagem_corrigida


def detectar_cupom(imagem):
    """
    Procura uma região clara, grande e alongada
    que provavelmente corresponde ao cupom.
    """

    cinza = cv2.cvtColor(
        imagem,
        cv2.COLOR_BGR2GRAY
    )

    borrada = cv2.GaussianBlur(
        cinza,
        (5, 5),
        0
    )

    # Procura principalmente o papel claro
    _, mascara = cv2.threshold(
        borrada,
        160,
        255,
        cv2.THRESH_BINARY
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (21, 21)
    )

    mascara = cv2.morphologyEx(
        mascara,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2
    )

    # Arquivo útil para debug
    cv2.imwrite(
        "debug_mascara.jpg",
        mascara
    )

    contornos, _ = cv2.findContours(
        mascara,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contornos:
        return None

    altura, largura = imagem.shape[:2]

    area_imagem = altura * largura

    candidatos = []

    for contorno in contornos:

        area = cv2.contourArea(
            contorno
        )

        # Ignora regiões pequenas
        if area < area_imagem * 0.10:
            continue

        retangulo = cv2.minAreaRect(
            contorno
        )

        (_, _), (w, h), _ = retangulo

        if w == 0 or h == 0:
            continue

        maior = max(w, h)
        menor = min(w, h)

        proporcao = maior / menor

        # Cupom tende a ser alto e estreito
        if proporcao > 1.5:

            candidatos.append(
                (
                    area,
                    retangulo
                )
            )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda x: x[0],
        reverse=True
    )

    retangulo = candidatos[0][1]

    caixa = cv2.boxPoints(
        retangulo
    )

    caixa = np.int32(
        caixa
    )

    return caixa.reshape(
        4,
        1,
        2
    )


def salvar_debug_paddle(blocos):
    """
    Salva os textos e suas coordenadas
    encontradas pelo PaddleOCR.
    """

    with open(
        "debug_paddle.json",
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            blocos,
            arquivo,
            indent=4,
            ensure_ascii=False
        )

    print(
        "Coordenadas do PaddleOCR salvas em "
        "debug_paddle.json"
    )


def ler_cupom(
    caminho_imagem,
    motor_ocr="tesseract"
):
    """
    Abre o cupom, tenta recortá-lo,
    corrige a perspectiva e executa o OCR.

    Retorna:

        texto
        blocos

    No Tesseract, blocos fica vazio.

    No PaddleOCR, blocos contém texto +
    coordenadas + confiança.
    """

    imagem = cv2.imread(
        caminho_imagem
    )

    if imagem is None:
        raise FileNotFoundError(
            f"Não foi possível abrir a imagem: "
            f"{caminho_imagem}"
        )

    # O retângulo da região clara pode cortar texto ou girar o papel.
    # Paddle detecta linhas inclinadas diretamente na foto original.
    contorno = detectar_cupom(imagem)
    if contorno is not None and motor_ocr == 'paddle':
        candidato = corrigir_perspectiva(imagem, contorno)
        if candidato.shape[0] / candidato.shape[1] < 2.5:
            contorno = None

    if contorno is not None:

        print(
            "Cupom detectado. "
            "Corrigindo perspectiva..."
        )

        imagem = corrigir_perspectiva(
            imagem,
            contorno
        )

        cv2.imwrite(
            "cupom_recortado.jpg",
            imagem
        )

    else:

        print(
            "Usando a foto original (sem recorte confiável)."
        )

    # =====================================
    # PADDLE OCR
    # =====================================

    if motor_ocr == "paddle":

        print(
            "OCR utilizado: PaddleOCR"
        )

        # Importação feita somente quando
        # realmente usamos PaddleOCR.
        from src.paddle_ocr import (
            ler_com_paddle
        )

        texto, blocos = ler_com_paddle(
            imagem,
            retornar_blocos=True
        )

        return texto, blocos

    # =====================================
    # TESSERACT
    # =====================================

    print(
        "OCR utilizado: Tesseract"
    )

    cinza = cv2.cvtColor(
        imagem,
        cv2.COLOR_BGR2GRAY
    )

    texto = pytesseract.image_to_string(
        cinza,
        lang="por",
        config="--oem 3 --psm 3"
    )

    return texto, []


def main():

    configurar_tesseract()

    if len(sys.argv) < 2:

        print("Uso:")
        print()
        print(
            "python main.py caminho_imagem "
            "--ocr paddle"
        )
        print()
        print(
            "python main.py caminho_imagem "
            "--ocr tesseract"
        )

        return

    caminho_imagem = sys.argv[1]

    # Modo de protótipo: testa o QR sem iniciar OCR ou carregar modelos.
    if "--qr-only" in sys.argv:
        try:
            codigos = ler_qr_codes(caminho_imagem)
            if codigos:
                print("QR Code(s) encontrado(s):")
                for codigo in codigos:
                    print(codigo)
            else:
                print("Nenhum QR Code legível encontrado.")
        except Exception as erro:
            print(f"Erro ao ler QR Code: {erro}")
        return

    # Tesseract é o padrão
    motor_ocr = "tesseract"

    if "--ocr" in sys.argv:

        indice = sys.argv.index(
            "--ocr"
        )

        if indice + 1 < len(sys.argv):

            motor_ocr = (
                sys.argv[indice + 1]
                .lower()
            )

    if motor_ocr not in [
        "tesseract",
        "paddle"
    ]:

        print(
            f"OCR inválido: {motor_ocr}"
        )

        print(
            "Use 'tesseract' ou 'paddle'."
        )

        return

    try:

        texto, blocos = ler_cupom(
            caminho_imagem,
            motor_ocr
        )

        # Se foi PaddleOCR,
        # salvamos também as posições.
        if (
            motor_ocr == "paddle"
            and blocos
        ):

            salvar_debug_paddle(
                blocos
            )

        print(
            "\n"
            "=========================="
        )

        print(
            "TEXTO EXTRAÍDO DO CUPOM"
        )

        print(
            "==========================\n"
        )

        print(
            texto
        )

        # =================================
        # PARSER
        # =================================

        if motor_ocr == "paddle" and blocos:
            produtos = extrair_produtos_paddle(blocos)
        else:
            produtos = extrair_produtos(texto)

        # =====================================
        # VERIFICAÇÕES DO CUPOM
        # =====================================

        verificacao = None
        verificacao_valor = None

        if motor_ocr == "paddle" and blocos:

            verificacao = verificar_quantidade_itens(
                blocos,
                produtos
            )

            verificacao_valor = verificar_valor_total(
                blocos,
                produtos
            )
                
        print("\n""==========================")

        print("PRODUTOS IDENTIFICADOS")
       

        print("==========================\n")
        

        print(
            json.dumps(
                produtos,
                indent=4,
                ensure_ascii=False
            )
        )
        # =====================================
        # MOSTRAR VERIFICAÇÃO DA QUANTIDADE
        # =====================================

        if verificacao is not None:

            print(
                "\n=========================="
            )

            print(
                "VERIFICAÇÃO DA QUANTIDADE"
            )

            print(
                "==========================\n"
            )

            print(
                json.dumps(
                    verificacao,
                    indent=4,
                    ensure_ascii=False
                )
            )

            if verificacao["status"] == "OK":

                print(
                    "\n✅ Quantidade de itens conferida."
                )

            elif verificacao["status"] == "REVISAO_NECESSARIA":

                print(
                    "\n⚠️ Quantidade de itens não confere."
                )


            # =====================================
            # MOSTRAR VERIFICAÇÃO DO VALOR
            # =====================================

            if verificacao_valor is not None:

                print(
                    "\n=========================="
                )

                print(
                    "VERIFICAÇÃO DO VALOR"
                )

                print(
                    "==========================\n"
                )

                print(
                    json.dumps(
                        verificacao_valor,
                        indent=4,
                        ensure_ascii=False
                    )
                )

                if verificacao_valor["status"] == "OK":

                    print("\n✅ Valor total conferido.")
                elif verificacao_valor["status"] == "REVISAO_NECESSARIA":

                    print( "\n⚠️ Valor total não confere.")
                
    except Exception as erro:
        print(f"Erro: {erro}")
                
            


if __name__ == "__main__":
    main()
