"""Fixtures compartidos para los tests."""
import numpy as np
import cv2
import pytest


@pytest.fixture
def synthetic_dni_image():
    """
    Genera una imagen sintética que simula una foto de DNI:
    - Fondo gris oscuro (mesa)
    - Rectángulo blanco con ratio 1.586 (ID-1) en el centro
    - Algo de texto negro dentro para dar bordes interiores
    Tamaño total: 1200x900 px
    Documento: 800x504 px centrado
    """
    img = np.full((900, 1200, 3), 80, dtype=np.uint8)  # mesa gris oscuro

    # Rectángulo blanco del documento
    x1, y1 = 200, 198
    x2, y2 = 1000, 702
    cv2.rectangle(img, (x1, y1), (x2, y2), (245, 245, 245), -1)

    # Borde sutil del documento
    cv2.rectangle(img, (x1, y1), (x2, y2), (200, 200, 200), 2)

    # Texto simulado (líneas negras horizontales)
    for i, y in enumerate([280, 340, 400, 460, 520, 580]):
        cv2.line(img, (x1 + 60, y), (x1 + 400, y), (40, 40, 40), 3)

    return img


@pytest.fixture
def synthetic_dni_corners():
    """Esquinas conocidas del documento sintético (formato [[x,y], ...])."""
    return [[200, 198], [1000, 198], [1000, 702], [200, 702]]
