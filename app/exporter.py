"""
Módulo de exportación para generación de documentos finales.

Combina las imágenes procesadas (frontal + trasera) en un documento final
en formato PDF, Word (.docx) o imagen PNG.
"""

import io
import os
from datetime import datetime
import numpy as np
import cv2
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import docx
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Dimensiones estándar de documentos (en píxeles a 300 DPI)
# DNI/ID Card: 85.6 × 53.98 mm → a 300 DPI = 1012 × 638 px
# Pasaporte: 125 × 88 mm → a 300 DPI = 1476 × 1039 px
STANDARD_SIZES = {
    "id_card": (1012, 638),
    "passport": (1476, 1039),
}
DEFAULT_SIZE = (1012, 638)


def _normalize_image_size(image: np.ndarray, target_size: tuple = None) -> np.ndarray:
    """
    Redimensiona la imagen a un tamaño estándar manteniendo el aspect ratio.
    Rellena con blanco si el aspect ratio no coincide exactamente.

    Args:
        image: Imagen BGR numpy array
        target_size: (width, height) en píxeles. Si None, usa DEFAULT_SIZE.

    Returns:
        Imagen redimensionada al tamaño estándar, centrada sobre fondo blanco
    """
    if image is None:
        return None

    if target_size is None:
        target_size = DEFAULT_SIZE

    target_w, target_h = target_size
    h, w = image.shape[:2]

    scale = min(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)

    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

    return canvas


def _detect_document_type(front_image, back_image) -> str:
    """
    Detecta si es DNI/tarjeta o pasaporte basándose en el aspect ratio.
    """
    for img in [front_image, back_image]:
        if img is not None:
            h, w = img.shape[:2]
            ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 1
            if ratio > 1.5:
                return "id_card"
            elif ratio > 1.35:
                return "passport"
    return "id_card"


def _bgr_to_pil(image: np.ndarray) -> Image:
    """
    Convierte imagen OpenCV (BGR) a PIL (RGB).

    Args:
        image: numpy array en formato BGR

    Returns:
        Imagen PIL en formato RGB
    """
    if image is None:
        return None
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _pil_to_bytes(pil_image: Image, format: str = "JPEG") -> bytes:
    """
    Convierte imagen PIL a bytes para embeber en documentos.

    Args:
        pil_image: Imagen PIL
        format: Formato de salida (JPEG, PNG, etc.)

    Returns:
        Bytes de la imagen
    """
    buffer = io.BytesIO()
    pil_image.save(buffer, format=format, quality=95)
    return buffer.getvalue()


def export_pdf(
    front_image: np.ndarray | None,
    back_image: np.ndarray | None,
    output_path: str,
    title: str = "Documento de Identidad"
) -> str:
    """
    Genera PDF en UNA SOLA PÁGINA A4 con ambas caras del documento.

    Layout (vertical, A4 = 21cm × 29.7cm):
    ┌─────────────────────────────────┐
    │  [título pequeño + fecha]       │  ← encabezado 1cm
    │  ─────────────────────────────  │
    │                                 │
    │   ┌───────────────────────┐     │
    │   │                       │     │
    │   │   CARA FRONTAL        │     │  ← ~13cm de alto
    │   │                       │     │
    │   └───────────────────────┘     │
    │      [etiqueta "Frontal"]       │  ← 0.5cm
    │                                 │
    │   ┌───────────────────────┐     │
    │   │                       │     │
    │   │   CARA TRASERA        │     │  ← ~13cm de alto
    │   │                       │     │
    │   └───────────────────────┘     │
    │      [etiqueta "Trasera"]       │  ← 0.5cm
    └─────────────────────────────────┘

    Args:
        front_image: numpy array BGR o None (si solo hay una cara)
        back_image: numpy array BGR o None (si solo hay una cara)
        output_path: Ruta completa del PDF a generar

    Returns:
        output_path si éxito, lanza excepción si falla
    """
    # Dimensiones A4 en puntos (1 pt = 1/72 pulgada)
    width, height = A4  # 595.28 x 841.89 pts

    c = canvas.Canvas(output_path, pagesize=A4)

    # --- Encabezado ---
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#2d3748"))
    c.drawCentredString(width / 2, height - 30, title)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#718096"))
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.drawCentredString(width / 2, height - 45, f"Generado: {fecha}")

    # Línea divisoria
    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.setLineWidth(0.5)
    c.line(30, height - 55, width - 30, height - 55)

    # --- Normalizar ambas imágenes al mismo tamaño ---
    doc_type = _detect_document_type(front_image, back_image)
    target_size = STANDARD_SIZES.get(doc_type, DEFAULT_SIZE)
    front_image = _normalize_image_size(front_image, target_size)
    back_image = _normalize_image_size(back_image, target_size)

    # --- Área para imágenes ---
    margin_x = 30
    available_width = width - (2 * margin_x)
    image_height = 336

    # Imagen frontal (parte superior)
    y_front = height - 55 - 10 - image_height
    if front_image is not None:
        # Convertir numpy BGR → bytes JPEG
        pil_front = _bgr_to_pil(front_image)
        # Calcular dimensiones manteniendo aspect ratio dentro del espacio disponible
        img_bytes_front = _pil_to_bytes(pil_front)
        img_reader = ImageReader(io.BytesIO(img_bytes_front))
        iw, ih = pil_front.size
        scale = min(available_width / iw, image_height / ih)
        draw_w, draw_h = iw * scale, ih * scale
        x_centered = margin_x + (available_width - draw_w) / 2
        c.drawImage(
            img_reader, x_centered, y_front + (image_height - draw_h) / 2,
            width=draw_w, height=draw_h
        )
    else:
        # Placeholder vacío
        c.setFillColor(colors.HexColor("#f7fafc"))
        c.rect(margin_x, y_front, available_width, image_height, fill=1, stroke=0)
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.HexColor("#a0aec0"))
        c.drawCentredString(
            width / 2, y_front + image_height / 2,
            "Cara frontal no proporcionada"
        )

    # Etiqueta frontal
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#4a5568"))
    c.drawCentredString(width / 2, y_front - 12, "CARA FRONTAL")

    # Imagen trasera (parte inferior)
    gap = 25
    y_back = y_front - gap - image_height - 15
    if back_image is not None:
        pil_back = _bgr_to_pil(back_image)
        img_bytes_back = _pil_to_bytes(pil_back)
        img_reader_back = ImageReader(io.BytesIO(img_bytes_back))
        iw, ih = pil_back.size
        scale = min(available_width / iw, image_height / ih)
        draw_w, draw_h = iw * scale, ih * scale
        x_centered = margin_x + (available_width - draw_w) / 2
        c.drawImage(
            img_reader_back, x_centered, y_back + (image_height - draw_h) / 2,
            width=draw_w, height=draw_h
        )
    else:
        c.setFillColor(colors.HexColor("#f7fafc"))
        c.rect(margin_x, y_back, available_width, image_height, fill=1, stroke=0)

    # Etiqueta trasera
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#4a5568"))
    c.drawCentredString(width / 2, y_back - 12, "CARA TRASERA")

    c.save()
    return output_path


def export_word(
    front_image: np.ndarray | None,
    back_image: np.ndarray | None,
    output_path: str,
    title: str = "Documento de Identidad"
) -> str:
    """
    Genera documento Word (.docx) con ambas caras en la misma página.

    Args:
        front_image: numpy array BGR o None
        back_image: numpy array BGR o None
        output_path: Ruta completa del documento Word
        title: Título del documento

    Returns:
        output_path si éxito
    """
    doc = docx.Document()

    # Configurar márgenes (1.5 cm todos los lados)
    section = doc.sections[0]
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)

    # Título centrado
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run(title)
    title_run.font.size = Pt(16)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)

    # Fecha
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_run = date_para.add_run(f"Generado: {fecha}")
    date_run.font.size = Pt(9)
    date_run.font.color.rgb = RGBColor(0x71, 0x80, 0x96)

    # Separador horizontal
    doc.add_paragraph("_" * 50).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Normalizar ambas imágenes al mismo tamaño
    doc_type = _detect_document_type(front_image, back_image)
    target_size = STANDARD_SIZES.get(doc_type, DEFAULT_SIZE)
    front_image = _normalize_image_size(front_image, target_size)
    back_image = _normalize_image_size(back_image, target_size)

    # Imagen frontal
    if front_image is not None:
        pil_front = _bgr_to_pil(front_image)
        img_bytes = _pil_to_bytes(pil_front)
        img_stream = io.BytesIO(img_bytes)

        label_para = doc.add_paragraph("CARA FRONTAL")
        label_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        label_run = label_para.add_run()
        label_run.font.bold = True
        label_run.font.size = Pt(10)

        doc.add_picture(img_stream, width=Inches(5.5))
        doc.add_paragraph()  # Espacio

    # Imagen trasera
    if back_image is not None:
        pil_back = _bgr_to_pil(back_image)
        img_bytes = _pil_to_bytes(pil_back)
        img_stream = io.BytesIO(img_bytes)

        label_para = doc.add_paragraph("CARA TRASERA")
        label_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        label_run = label_para.add_run()
        label_run.font.bold = True
        label_run.font.size = Pt(10)

        doc.add_picture(img_stream, width=Inches(5.5))

    doc.save(output_path)
    return output_path


def export_image(
    front_image: np.ndarray | None,
    back_image: np.ndarray | None,
    output_path: str
) -> str:
    """
    Genera una imagen PNG combinada (ambas caras una encima de la otra).
    Ambas caras se normalizan al mismo tamaño antes de combinar.
    """
    padding = 20
    bg_color = 240

    if front_image is None and back_image is None:
        raise ValueError("Al menos una imagen debe ser proporcionada")

    doc_type = _detect_document_type(front_image, back_image)
    target_size = STANDARD_SIZES.get(doc_type, DEFAULT_SIZE)
    front_norm = _normalize_image_size(front_image, target_size)
    back_norm = _normalize_image_size(back_image, target_size)

    target_w, target_h = target_size
    images = [img for img in [front_norm, back_norm] if img is not None]

    if len(images) == 2:
        total_height = target_h * 2 + padding
    else:
        total_height = target_h

    canvas = np.full((total_height, target_w, 3), bg_color, dtype=np.uint8)

    y_offset = 0
    if front_norm is not None:
        canvas[0:target_h, 0:target_w] = front_norm
        y_offset = target_h + padding

    if back_norm is not None:
        canvas[y_offset:y_offset + target_h, 0:target_w] = back_norm

    cv2.imwrite(output_path, canvas)
    return output_path


def _choose_page_orientation(image: np.ndarray) -> tuple:
    """
    Elige el tamaño de página A4 según el aspect ratio de la imagen:
    landscape si es más ancha que alta, portrait en cualquier otro caso
    (incluido el cuadrado).
    """
    h, w = image.shape[:2]
    if w > h:
        return landscape(A4)
    return A4


def export_pdf_single(
    image: np.ndarray,
    output_path: str,
    title: str = "Documento"
) -> str:
    """
    Genera un PDF de una sola página con una única imagen, en la
    orientación A4 que mejor se ajusta a su aspect ratio. No fuerza
    ningún lienzo de tamaño fijo ni muestra placeholders: es para
    documentos de una sola cara (p.ej. Permiso de Circulación).
    """
    width, height = _choose_page_orientation(image)

    c = canvas.Canvas(output_path, pagesize=(width, height))

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#2d3748"))
    c.drawCentredString(width / 2, height - 30, title)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#718096"))
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.drawCentredString(width / 2, height - 45, f"Generado: {fecha}")

    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.setLineWidth(0.5)
    c.line(30, height - 55, width - 30, height - 55)

    margin_x = 30
    margin_bottom = 30
    available_width = width - (2 * margin_x)
    available_height = height - 55 - 10 - margin_bottom

    pil_image = _bgr_to_pil(image)
    img_bytes = _pil_to_bytes(pil_image)
    img_reader = ImageReader(io.BytesIO(img_bytes))
    iw, ih = pil_image.size
    scale = min(available_width / iw, available_height / ih)
    draw_w, draw_h = iw * scale, ih * scale
    x_centered = margin_x + (available_width - draw_w) / 2
    y_centered = margin_bottom + (available_height - draw_h) / 2

    c.drawImage(img_reader, x_centered, y_centered, width=draw_w, height=draw_h)

    c.save()
    return output_path
