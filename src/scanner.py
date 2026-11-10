from contextlib import suppress

import cv2
import pyzbar.pyzbar as pyzbar

if __package__:
    from .tratamento_erros import ErroAplicacao, TratadorErros
else:
    from tratamento_erros import ErroAplicacao, TratadorErros


def scanner():
    cap = None
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise ErroAplicacao("Não foi possível abrir a webcam.")

        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                raise ErroAplicacao("Não foi possível capturar o vídeo.")

            cv2.imshow("Frame", frame)
            for obj in pyzbar.decode(frame):
                if obj.type == "QRCODE":
                    try:
                        return obj.data.decode("utf-8")
                    except UnicodeDecodeError as erro:
                        raise TratadorErros.qr_invalido() from erro

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or cv2.getWindowProperty("Frame", cv2.WND_PROP_VISIBLE) < 1:
                return None
    except cv2.error as erro:
        raise TratadorErros.falha_webcam() from erro
    finally:
        if cap is not None:
            with suppress(cv2.error):
                cap.release()
        with suppress(cv2.error):
            cv2.destroyAllWindows()

if __name__ == "__main__":
    url = scanner()
    if url:
        print(url)
