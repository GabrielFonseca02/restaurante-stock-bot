import cv2
import pyzbar.pyzbar as pyzbar

def scanner():
    cap = cv2.VideoCapture(0)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Não foi possível capturar o vídeo.")
            break

        URL = ""
        cv2.imshow("Frame",frame) 
        decodedObjects = pyzbar.decode(frame)
        for obj in decodedObjects:
            if len(obj) >=1:
                import webbrowser
                URL = obj.data.decode("utf-8")
                print(URL)
                exit()

        key = cv2.waitKey(1)
        if key == 27:
            break

    return URL

if __name__ == "__main__":
    scanner()