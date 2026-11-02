"""Leitura simples de QR Codes em imagens de cupons fiscais."""

import cv2


def ler_qr_codes(caminho_imagem):
    """Retorna o conteúdo dos QR Codes encontrados na imagem."""
    imagem = cv2.imread(str(caminho_imagem))
    if imagem is None:
        raise FileNotFoundError(f"Não foi possível abrir a imagem: {caminho_imagem}")

    detector = cv2.QRCodeDetector()

    # A detecção múltipla também funciona para imagens com mais de um QR.
    sucesso, textos, _pontos, _retificados = detector.detectAndDecodeMulti(imagem)
    if sucesso:
        return [texto for texto in textos if texto]

    # Algumas versões/imagens funcionam melhor com a chamada individual.
    texto, _pontos, _retificado = detector.detectAndDecode(imagem)
    return [texto] if texto else []
