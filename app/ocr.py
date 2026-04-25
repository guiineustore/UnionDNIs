"""
Módulo de OCR (Optical Character Recognition) para extracción de texto de documentos.

Usa Tesseract OCR para leer el texto de los documentos escaneados,
especialmente la zona MRZ (Machine Readable Zone) de pasaportes y DNI.

Todo se procesa localmente, sin APIs externas.
"""

import os
import re
import shutil
import numpy as np
import cv2


def check_tesseract_available() -> bool:
    """
    Verifica si Tesseract está instalado y accesible.

    Returns:
        True si Tesseract está disponible, False en caso contrario
    """
    # Verificar en PATH del sistema
    if shutil.which("tesseract") is not None:
        return True

    # Verificar ruta típica en Windows
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        return True

    return False


def extract_text(image: np.ndarray, lang: str = "spa+eng") -> str:
    """
    Extrae todo el texto visible en la imagen.

    Args:
        image: Imagen BGR del documento ya corregido
        lang: Idiomas para Tesseract (spa+eng para DNI español)

    Returns:
        Texto extraído como string, o "" si Tesseract no está disponible
    """
    if not check_tesseract_available():
        return ""

    try:
        import pytesseract
        # Configurar ruta de Tesseract en Windows
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        # Convertir a escala de grises
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Aplicar umbralización adaptativa para mejorar contraste
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )

        # Extraer texto con PSM 6 (bloque de texto uniforme)
        text = pytesseract.image_to_string(thresh, lang=lang, config="--psm 6")

        # Limpiar resultado: eliminar líneas vacías múltiples y espacios extra
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

    except Exception:
        return ""


def extract_mrz(image: np.ndarray) -> dict:
    """
    Extrae la zona MRZ (Machine Readable Zone) al final del documento.

    La MRZ típicamente ocupa el tercio inferior del documento.
    Para pasaporte: 2 líneas de 44 caracteres
    Para DNI: 3 líneas de 30 caracteres

    Returns:
        dict con:
            - "raw": texto MRZ raw
            - "lines": lista de líneas MRZ
            - "type": "passport" | "id_card" | "unknown"
            - "detected": bool
    """
    if not check_tesseract_available():
        return {"detected": False, "raw": "", "lines": [], "type": "unknown"}

    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        h, w = image.shape[:2]

        # Tomar región inferior (30% de la altura)
        y_start = int(h * 0.65)
        mrz_region = image[y_start:h].copy()

        # Convertir a gris
        if len(mrz_region.shape) == 3:
            gray = cv2.cvtColor(mrz_region, cv2.COLOR_BGR2GRAY)
        else:
            gray = mrz_region.copy()

        # Umbralización fuerte para máximo contraste
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Config para MRZ: solo caracteres válidos
        config = "--psm 6 --oem 1 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"

        # Extraer texto
        text = pytesseract.image_to_string(thresh, lang="eng", config=config)

        # Procesar líneas
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # Filtrar solo líneas que parecen MRZ (solo mayúsculas, números y <)
        mrz_lines = []
        for line in lines:
            # Una línea MRZ válida solo tiene A-Z, 0-9 y <
            if re.match(r'^[A-Z0-9<]+$', line):
                mrz_lines.append(line)

        # Determinar tipo de documento
        mrz_type = "unknown"
        if len(mrz_lines) == 2 and all(len(line) >= 40 for line in mrz_lines):
            mrz_type = "passport"  # TD3: 2 líneas x 44 chars
        elif len(mrz_lines) >= 2 and all(len(line) >= 25 for line in mrz_lines):
            mrz_type = "id_card"  # ID-1: 3 líneas x 30 chars

        detected = len(mrz_lines) >= 2

        return {
            "detected": detected,
            "raw": '\n'.join(mrz_lines),
            "lines": mrz_lines,
            "type": mrz_type
        }

    except Exception:
        return {"detected": False, "raw": "", "lines": [], "type": "unknown"}


def parse_mrz_fields(mrz_data: dict) -> dict:
    """
    Parsea los campos del MRZ según el estándar ICAO 9303.

    Returns:
        dict con campos como:
            - "document_number": str
            - "surname": str
            - "given_names": str
            - "birth_date": str (YYMMDD)
            - "expiry_date": str (YYMMDD)
            - "nationality": str
            - "sex": str
        (cada campo puede ser None si no se detectó)
    """
    fields = {
        "document_number": None,
        "surname": None,
        "given_names": None,
        "birth_date": None,
        "expiry_date": None,
        "nationality": None,
        "sex": None,
        "issuing_country": None,
        "personal_number": None
    }

    if not mrz_data.get("detected") or not mrz_data.get("lines"):
        return fields

    lines = mrz_data["lines"]
    mrz_type = mrz_data.get("type", "unknown")

    try:
        if mrz_type == "passport":
            # TD3: 2 líneas de 44 caracteres
            if len(lines) >= 2:
                line1 = lines[0].ljust(44)[:44]
                line2 = lines[1].ljust(44)[:44]

                # Línea 1: P<ESP APELLIDOS<<NOMBRE...
                # Tipo de documento (pos 0-1)
                # País emisor (pos 2-4)
                # Apellido<<Nombre (pos 5-43)
                fields["issuing_country"] = line1[2:5]

                # Nombre: formato "APELLIDOS<<NOMBRE" o "APELLIDOS<<NOMBRE<<MIDDLE"
                name_part = line1[5:].split('<<')
                if len(name_part) >= 1:
                    fields["surname"] = name_part[0].replace('<', ' ').strip()
                if len(name_part) >= 2:
                    fields["given_names"] = name_part[1].replace('<', ' ').strip()

                # Línea 2: Número doc + nacimiento + sexo + expiración + nacionalidad + personal
                # Número de documento (pos 0-8)
                fields["document_number"] = line2[0:9].replace('<', '').strip()

                # Nacionalidad (pos 10-12)
                fields["nationality"] = line2[10:13]

                # Fecha de nacimiento (pos 13-18) YYMMDD
                fields["birth_date"] = line2[13:19]

                # Sexo (pos 19)
                fields["sex"] = line2[19] if line2[19] in 'MF' else None

                # Fecha de expiración (pos 21-26) YYMMDD
                fields["expiry_date"] = line2[21:27]

                # Número personal (pos 28-41)
                fields["personal_number"] = line2[28:42].replace('<', '').strip()

        elif mrz_type == "id_card":
            # ID-1: 3 líneas de 30 caracteres (DNI español)
            if len(lines) >= 3:
                line1 = lines[0].ljust(30)[:30]
                line2 = lines[1].ljust(30)[:30]
                line3 = lines[2].ljust(30)[:30]

                # Línea 1: ID<ESP<NUMERO_DNI<<<...
                # Tipo (0-1) + País (2-4) + Número (5-13) + DV (14) + opcional (15-29)
                fields["issuing_country"] = line1[2:5]
                fields["document_number"] = line1[5:14].replace('<', '').strip()

                # Línea 2: Nacimiento + DV + Sexo + Expiración + DV + Nacionalidad + ...
                # Fecha nacimiento (0-5) YYMMDD
                fields["birth_date"] = line2[0:6]

                # Sexo (7)
                fields["sex"] = line2[7] if line2[7] in 'MF' else None

                # Fecha expiración (9-14) YYMMDD
                fields["expiry_date"] = line2[9:15]

                # Nacionalidad (16-18)
                fields["nationality"] = line2[16:19]

                # Línea 3: APELLIDOS<<NOMBRE
                name_part = line3.split('<<')
                if len(name_part) >= 1:
                    fields["surname"] = name_part[0].replace('<', ' ').strip()
                if len(name_part) >= 2:
                    fields["given_names"] = name_part[1].replace('<', ' ').strip()

    except Exception:
        pass

    return fields
