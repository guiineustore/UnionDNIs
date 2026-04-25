"""
Módulo de mejora de imagen para documentos escaneados.

Aplica diferentes niveles de mejora según el modo seleccionado:
- color: mejora de contraste y nitidez manteniendo colores
- bw: modo "escáner" blanco/negro con alto contraste
- original: sin cambios
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def enhance_scan(image, mode="color"):
    """
    Mejora la imagen del documento escaneado.

    Args:
        image: Imagen BGR (numpy array)
        mode: "color" | "grayscale" | "bw" | "original"

    Returns:
        Imagen mejorada (numpy array BGR)
    """
    if mode == "original":
        return image
    elif mode == "bw":
        return _enhance_bw(image)
    elif mode == "grayscale":
        return _enhance_grayscale(image)
    else:
        return _enhance_color(image)


def _enhance_color(image):
    """
    Mejora de color: contraste adaptativo (CLAHE) + nitidez + balance de blancos.
    """
    image = _correct_waviness(image)

    # Convertir a LAB para ajustar luminosidad sin alterar color
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    # CLAHE (Contrast Limited Adaptive Histogram Equalization) 
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    
    # Recombinar canales
    lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
    enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    
    # Nitidez con unsharp mask
    enhanced = _unsharp_mask(enhanced)
    
    # Corrección de balance de blancos
    enhanced = _white_balance(enhanced)
    
    return enhanced


def _enhance_grayscale(image):
    """
    Modo grises: convierte a escala de grises con CLAHE y nitidez mejorada.
    Produce un resultado similar a una fotocopia de calidad.
    Mantiene tonos medios (no es binario como B/N).
    """
    image = _correct_waviness(image)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    blurred = cv2.GaussianBlur(enhanced, (0, 0), 1)
    sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0)

    sharpened = cv2.normalize(sharpened, None, 0, 255, cv2.NORM_MINMAX)

    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)


def _enhance_bw(image):
    """
    Modo escáner B/N: alta legibilidad, fondo blanco limpio, texto negro nítido.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Eliminar sombras usando morfología
    # Dilatar para crear fondo estimado, luego restar
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    bg = cv2.morphologyEx(gray, cv2.MORPH_DILATE, kernel)

    # Dividir imagen por fondo para normalizar iluminación
    normalized = cv2.divide(gray, bg, scale=255)

    # Umbralización adaptativa para texto nítido
    thresh = cv2.adaptiveThreshold(
        normalized, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21, 10
    )

    # Convertir de vuelta a BGR para mantener compatibilidad
    return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)


def _correct_waviness(image):
    """
    Intenta corregir la ondulación sutil del texto causada por curvatura
    de tarjetas plásticas.

    Usa un enfoque en dos pasos:
    1. Filtro bilateral para suavizar irregularidades sin perder bordes de texto
    2. Corrección geométrica suave basada en detección de líneas

    Esta corrección es conservadora: si no detecta ondulación significativa,
    devuelve la imagen sin cambios para no degradar la calidad.
    """
    h, w = image.shape[:2]

    smoothed = cv2.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)

    gray = cv2.cvtColor(smoothed, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi/180, threshold=80,
        minLineLength=w * 0.3,
        maxLineGap=10
    )

    if lines is None or len(lines) < 3:
        return smoothed

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(x2 - x1) > 0:
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
            if abs(angle) < 10:
                angles.append(angle)

    if len(angles) < 2:
        return smoothed

    angle_std = np.std(angles)

    if angle_std < 0.5:
        return smoothed

    mean_angle = np.mean(angles)
    if abs(mean_angle) > 0.1:
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, mean_angle, 1.0)
        corrected = cv2.warpAffine(smoothed, M, (w, h),
                                    borderMode=cv2.BORDER_REPLICATE)
        return corrected

    return smoothed


def _unsharp_mask(image, amount=1.5, radius=1):
    """
    Aplica máscara de enfoque (unsharp mask) para mejorar nitidez.
    """
    blurred = cv2.GaussianBlur(image, (0, 0), radius)
    sharpened = cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)
    return sharpened


def _white_balance(image):
    """
    Corrección automática de balance de blancos usando el algoritmo Gray World.
    Asume que el promedio de color de la escena debería ser gris neutro.
    """
    result = image.copy().astype(np.float32)
    avg_b = np.mean(result[:, :, 0])
    avg_g = np.mean(result[:, :, 1])
    avg_r = np.mean(result[:, :, 2])
    avg = (avg_b + avg_g + avg_r) / 3
    
    result[:, :, 0] *= avg / avg_b if avg_b > 0 else 1
    result[:, :, 1] *= avg / avg_g if avg_g > 0 else 1
    result[:, :, 2] *= avg / avg_r if avg_r > 0 else 1
    
    return np.clip(result, 0, 255).astype(np.uint8)
