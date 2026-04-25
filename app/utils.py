"""
Utilidades comunes para el procesamiento de imágenes de documentos.
"""

import numpy as np
import cv2


def order_points(pts):
    """
    Ordena 4 puntos en el orden: top-left, top-right, bottom-right, bottom-left.
    
    Usa la suma y diferencia de coordenadas para determinar la posición:
    - Top-left: menor suma (x+y)
    - Bottom-right: mayor suma (x+y)
    - Top-right: menor diferencia (y-x)
    - Bottom-left: mayor diferencia (y-x)
    
    Args:
        pts: Array de 4 puntos [(x,y), ...]
        
    Returns:
        Array ordenado de 4 puntos [tl, tr, br, bl]
    """
    rect = np.zeros((4, 2), dtype="float32")
    pts = np.array(pts, dtype="float32")

    # Sum: top-left has smallest, bottom-right has largest
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # Difference: top-right has smallest, bottom-left has largest
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def four_point_transform(image, pts):
    """
    Aplica transformación de perspectiva de 4 puntos para "aplanar" el documento.
    
    Calcula las dimensiones del rectángulo destino basándose en las distancias
    máximas entre las esquinas, luego aplica warpPerspective.
    
    Args:
        image: Imagen original (numpy array BGR)
        pts: 4 esquinas del documento [(x,y), ...]
        
    Returns:
        Imagen transformada (vista cenital del documento)
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # Compute width of the new image
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # Compute height of the new image
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    # Destination points for the transform
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")

    # Compute the perspective transform matrix and apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    return warped


def resize_with_aspect(image, width=None, height=None):
    """
    Redimensiona manteniendo relación de aspecto.
    
    Args:
        image: Imagen numpy array
        width: Ancho deseado (opcional)
        height: Alto deseado (opcional)
        
    Returns:
        Imagen redimensionada
    """
    (h, w) = image.shape[:2]

    if width is None and height is None:
        return image

    if width is not None:
        ratio = width / float(w)
        dim = (width, int(h * ratio))
    else:
        ratio = height / float(h)
        dim = (int(w * ratio), height)

    return cv2.resize(image, dim, interpolation=cv2.INTER_AREA)


def auto_canny(image, sigma=0.33):
    """
    Aplica Canny edge detection con umbrales automáticos basados en la mediana.

    Usa la mediana de la intensidad de píxeles para calcular los umbrales
    inferior y superior automáticamente. Esto produce resultados más
    consistentes que umbrales fijos.

    Args:
        image: Imagen en escala de grises
        sigma: Factor de ajuste para los umbrales (default 0.33)

    Returns:
        Imagen con bordes detectados (Canny)
    """
    v = np.median(image)
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    return cv2.Canny(image, lower, upper)


from PIL import Image as PILImage
from PIL import ExifTags
import io


def correct_exif_orientation(image_bytes: bytes) -> np.ndarray:
    """
    Lee una imagen desde bytes y aplica la corrección de orientación EXIF.

    Los móviles guardan la foto siempre en la misma orientación raw y añaden
    una etiqueta EXIF para indicar la rotación correcta. OpenCV ignora EXIF,
    así que debemos corregirlo manualmente.

    Args:
        image_bytes: Bytes raw del archivo de imagen

    Returns:
        Imagen BGR numpy array con orientación corregida
    """
    try:
        pil_image = PILImage.open(io.BytesIO(image_bytes))

        exif = pil_image.getexif()
        orientation_tag = None

        for tag_id, tag_name in ExifTags.TAGS.items():
            if tag_name == 'Orientation':
                orientation_tag = tag_id
                break

        if orientation_tag and orientation_tag in exif:
            orientation = exif[orientation_tag]

            transforms = {
                2: [PILImage.FLIP_LEFT_RIGHT],
                3: [PILImage.ROTATE_180],
                4: [PILImage.FLIP_TOP_BOTTOM],
                5: [PILImage.FLIP_LEFT_RIGHT, PILImage.ROTATE_90],
                6: [PILImage.ROTATE_270],
                7: [PILImage.FLIP_LEFT_RIGHT, PILImage.ROTATE_270],
                8: [PILImage.ROTATE_90],
            }

            if orientation in transforms:
                for transform in transforms[orientation]:
                    pil_image = pil_image.transpose(transform)

        rgb_array = np.array(pil_image)
        if len(rgb_array.shape) == 2:
            return cv2.cvtColor(rgb_array, cv2.COLOR_GRAY2BGR)
        elif rgb_array.shape[2] == 4:
            return cv2.cvtColor(rgb_array, cv2.COLOR_RGBA2BGR)
        else:
            return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)

    except Exception:
        return cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
