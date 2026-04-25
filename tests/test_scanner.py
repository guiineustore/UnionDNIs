"""Tests del motor de detección de documentos."""
import cv2
import numpy as np
from app.scanner import detect_document


def test_detects_synthetic_dni(synthetic_dni_image):
    """La detección debe encontrar las 4 esquinas del DNI sintético con alta confianza."""
    result = detect_document(synthetic_dni_image)

    assert result["corners"] is not None, "Debería detectar las esquinas del documento sintético"
    assert len(result["corners"]) == 4
    assert result["confidence"] >= 0.7, f"Confianza debería ser >= 0.7, fue {result['confidence']}"


def test_corners_are_close_to_ground_truth(synthetic_dni_image, synthetic_dni_corners):
    """Las esquinas detectadas deben estar a menos de 30 píxeles de las reales."""
    result = detect_document(synthetic_dni_image)
    assert result["corners"] is not None

    detected = np.array(result["corners"])
    expected = np.array(synthetic_dni_corners)

    detected_sorted = detected[np.argsort(detected[:, 0] + detected[:, 1])]
    expected_sorted = expected[np.argsort(expected[:, 0] + expected[:, 1])]

    distances = np.linalg.norm(detected_sorted - expected_sorted, axis=1)
    assert np.all(distances < 30), f"Esquinas demasiado lejos: {distances}"


def test_returns_none_on_blank_image():
    """En una imagen completamente blanca no hay nada que detectar."""
    blank = np.full((600, 800, 3), 255, dtype=np.uint8)
    result = detect_document(blank)
    assert result["corners"] is None
    assert result["confidence"] == 0.0


def test_rejects_low_aspect_ratio_blob():
    """Un cuadrado perfecto NO debe ser aceptado como documento (ratio 1.0)."""
    img = np.full((800, 800, 3), 80, dtype=np.uint8)
    cv2.rectangle(img, (200, 200), (600, 600), (240, 240, 240), -1)
    result = detect_document(img)
    assert result["corners"] is None, "Un cuadrado perfecto no es un DNI ni un pasaporte"


def test_confidence_higher_for_dni_ratio(synthetic_dni_image):
    """
    La confianza para un documento con ratio cercano a 1.586 (DNI)
    debe ser >= 0.75. Actualmente solo se calcula por área, no por ratio.
    """
    result = detect_document(synthetic_dni_image)
    assert result["corners"] is not None
    assert result["confidence"] >= 0.75, (
        f"DNI sintético con ratio 1.587 debería tener confianza >= 0.75, "
        f"obtuvo {result['confidence']}"
    )
