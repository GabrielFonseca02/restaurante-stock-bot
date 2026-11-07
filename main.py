from pathlib import Path 
import cv2
import numpy as np
import pyzbar.pyzbar as pyzbar



def main():
    imagem = Path("receipts/qrcodePoker.jpg")
    img = cv2.imread('receipts/qrcodePoker.jpg')

    if img is None:
        print(f"não consegui abrir a imagem")
    else:
        print(f"Tamanho: {img.shape[1]} × {img.shape[0]} pixels")
        
        decodeObjects = pyzbar.decode(img)
        print(decodeObjects)

main()