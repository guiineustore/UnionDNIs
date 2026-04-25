"""Tests de las utilidades de procesamiento."""
import io
import numpy as np
import cv2
from PIL import Image as PILImage

from app.utils import correct_exif_orientation


def _build_jpeg_with_exif_orientation(width: int, height: int, orientation: int) -> bytes:
    """
    Crea un JPEG con etiqueta EXIF Orientation explícita.
    El contenido visual es un rectángulo horizontal (w > h).
    """
    img = np.full((height, width, 3), 200, dtype=np.uint8)
    cv2.rectangle(img, (10, 10), (width - 10, height - 10), (50, 50, 50), -1)

    pil = PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    exif = pil.getexif()
    exif[0x0112] = orientation  # 0x0112 = Orientation tag

    buf = io.BytesIO()
    pil.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_orientation_1_no_change():
    """Orientation=1 (normal) no debe rotar la imagen."""
    jpeg = _build_jpeg_with_exif_orientation(400, 200, orientation=1)
    result = correct_exif_orientation(jpeg)
    assert result.shape[:2] == (200, 400), "Sin rotación debe conservar HxW=(200, 400)"


def test_orientation_6_rotates_to_portrait():
    """Orientation=6 (rotada 90° CW por la cámara) debe enderezarse."""
    jpeg = _build_jpeg_with_exif_orientation(400, 200, orientation=6)
    result = correct_exif_orientation(jpeg)
    assert result.shape[:2] == (400, 200), (
        f"Orientation=6 debe quedar en (400, 200) tras rotación. Obtuvo {result.shape[:2]}"
    )


def test_idempotent_on_already_corrected_image():
    """
    Aplicar `correct_exif_orientation` dos veces sobre la salida de la primera
    no debe producir una rotación adicional.
    """
    jpeg = _build_jpeg_with_exif_orientation(400, 200, orientation=6)
    first = correct_exif_orientation(jpeg)

    ok, buf = cv2.imencode(".jpg", first, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
    assert ok
    second = correct_exif_orientation(buf.tobytes())

    assert second.shape == first.shape, (
        f"La función debe ser idempotente: shape primera={first.shape}, "
        f"segunda={second.shape}"
    )
