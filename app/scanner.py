"""
Motor de detección y recorte de documentos de identidad.

Usa OpenCV para detectar automáticamente los bordes de un DNI, NIE o pasaporte
en una foto tomada con el móvil, y aplica corrección de perspectiva para
obtener una vista cenital limpia del documento.

Pipeline:
    1. Redimensionar para velocidad
    2. Preprocesar (gris, blur, morfología)
    3. Detectar bordes (Canny automático)
    4. Encontrar contornos con 4 vértices
    5. Validar aspect ratio del documento
    6. Aplicar transformación de perspectiva sobre la imagen original
"""

import cv2
import numpy as np
import imutils

from .utils import order_points, four_point_transform, auto_canny


# Aspect ratios conocidos de documentos de identidad
DOCUMENT_RATIOS = {
    "id_card": 1.586,    # ISO/IEC 7810 ID-1 (DNI, NIE, tarjeta de crédito)
    "passport": 1.414,   # ISO/IEC 7810 ID-3 (pasaporte)
}
RATIO_TOLERANCE = 0.35   # Tolerancia amplia para fotos con ángulo


def detect_document(image):
    """
    Detecta automáticamente los 4 vértices del documento en la imagen.
    
    Intenta múltiples estrategias de detección para maximizar la tasa de éxito:
    1. Canny estándar con contornos
    2. Umbralización adaptativa
    3. Canal de color más contrastado
    
    Args:
        image: Imagen BGR (numpy array) leída con cv2.imread
        
    Returns:
        dict con:
            - "corners": lista de 4 puntos [(x,y), ...] en coords de la imagen original,
                         o None si no se detectó el documento
            - "confidence": float 0-1 indicando confianza de la detección
            - "method": str indicando el método que tuvo éxito
    """
    orig = image.copy()
    
    # Ratio para mapear puntos de la imagen reducida → original
    ratio = image.shape[0] / 500.0
    resized = imutils.resize(image, height=500)
    
    # Intentar detección con múltiples métodos
    methods = [
        ("canny_standard", _detect_canny_standard),
        ("canny_aggressive", _detect_canny_aggressive),
        ("adaptive_threshold", _detect_adaptive),
        ("color_channel", _detect_color_channel),
    ]
    
    for method_name, method_func in methods:
        corners = method_func(resized)
        if corners is not None:
            # Escalar puntos de vuelta a la imagen original
            corners_original = (corners * ratio).astype(int)
            confidence = _calculate_confidence(corners, resized.shape)
            return {
                "corners": corners_original.tolist(),
                "confidence": round(confidence, 2),
                "method": method_name
            }
    
    return {
        "corners": None,
        "confidence": 0.0,
        "method": "none"
    }


def apply_transform(image, corners):
    """
    Aplica la transformación de perspectiva usando esquinas proporcionadas.
    
    Args:
        image: Imagen original BGR
        corners: Lista de 4 puntos [(x,y), ...]
        
    Returns:
        Imagen transformada (vista cenital del documento)
    """
    pts = np.array(corners, dtype="float32")
    return four_point_transform(image, pts)


def _detect_canny_standard(resized):
    """Detección con Canny estándar y GaussianBlur."""
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = auto_canny(blurred)
    
    # Dilatar para cerrar gaps en los bordes
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edged = cv2.dilate(edged, kernel, iterations=1)
    
    return _find_document_contour(edged)


def _detect_canny_aggressive(resized):
    """Detección con Canny más agresivo y operaciones morfológicas."""
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    
    # Morfología para limpiar la imagen
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel)
    
    edged = cv2.Canny(closed, 30, 120)
    
    # Dilatar más para cerrar gaps
    edged = cv2.dilate(edged, kernel, iterations=2)
    
    return _find_document_contour(edged)


def _detect_adaptive(resized):
    """Detección usando umbralización adaptativa."""
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 21, 5
    )
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    return _find_document_contour(thresh)


def _detect_color_channel(resized):
    """Detección usando el canal de color con más contraste."""
    # Probar cada canal BGR individualmente
    for i in range(3):
        channel = resized[:, :, i]
        blurred = cv2.GaussianBlur(channel, (5, 5), 0)
        edged = auto_canny(blurred)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edged = cv2.dilate(edged, kernel, iterations=1)
        
        contour = _find_document_contour(edged)
        if contour is not None:
            return contour
    
    return None


def _find_document_contour(edged):
    """
    Busca un contorno rectangular (4 vértices) en la imagen de bordes.
    
    Filtra contornos por:
    - Número de vértices (exactamente 4)
    - Área mínima (al menos 5% de la imagen)
    - Convexidad
    
    Args:
        edged: Imagen binaria de bordes
        
    Returns:
        Array de 4 puntos del contorno, o None
    """
    contours = cv2.findContours(
        edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    contours = imutils.grab_contours(contours)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
    
    image_area = edged.shape[0] * edged.shape[1]
    min_area = image_area * 0.05  # Mínimo 5% de la imagen
    
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
            
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        
        if len(approx) == 4 and cv2.isContourConvex(approx):
            pts = approx.reshape(4, 2).astype("float32")
            
            # Validar que parece un documento (aspect ratio razonable)
            if _validate_aspect_ratio(pts):
                return pts
    
    return None


def _validate_aspect_ratio(pts):
    """
    Valida que los 4 puntos forman un rectángulo con aspect ratio 
    compatible con un documento de identidad.
    """
    ordered = order_points(pts)
    (tl, tr, br, bl) = ordered
    
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    width = max(widthA, widthB)
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    height = max(heightA, heightB)
    
    if height == 0 or width == 0:
        return False
    
    ratio = max(width, height) / min(width, height)
    
    # Comprobar contra ratios conocidos
    for doc_type, expected_ratio in DOCUMENT_RATIOS.items():
        if abs(ratio - expected_ratio) < RATIO_TOLERANCE:
            return True
    
    # Aceptar cualquier ratio razonable (entre 1.0 y 2.0)
    return 1.0 <= ratio <= 2.0


def _calculate_confidence(corners, image_shape):
    """
    Calcula una puntuación de confianza basada en:
    - Proporción del área del contorno vs área de la imagen
    - Regularidad del cuadrilátero
    """
    area = cv2.contourArea(corners.reshape(-1, 1, 2).astype(np.float32))
    image_area = image_shape[0] * image_shape[1]
    area_ratio = area / image_area
    
    # Confianza alta si el documento ocupa entre 10% y 80% de la imagen
    if 0.10 <= area_ratio <= 0.80:
        confidence = 0.5 + (0.5 * min(area_ratio / 0.3, 1.0))
    else:
        confidence = max(0.2, area_ratio)
    
    return min(confidence, 1.0)
