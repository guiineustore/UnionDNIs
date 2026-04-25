# CLAUDE.md — Guía de construcción: UnionDNIs

> Este archivo es la instrucción maestra para Claude Code.
> Léelo completo antes de escribir una sola línea de código.
> Sigue el orden exacto de las fases. No te saltes ningún paso.

---

## Contexto del Proyecto

**UnionDNIs** es una aplicación web local que imita el escáner de documentos de identidad.
El usuario sube dos fotos tomadas con el móvil (cara frontal y cara trasera de un DNI, NIE o pasaporte)
y obtiene un documento limpio en **PDF** (1 sola página con ambas caras), **Word** o **PNG**.

**Todo se procesa localmente.** Sin APIs externas. Sin cloud. Sin LLM.

---

## Entorno

- **OS**: Windows
- **Python**: 3.12 (en `c:\Users\Usuario\Desktop\Proyectos\UnionDNIs\venv\`)
- **Directorio del proyecto**: `c:\Users\Usuario\Desktop\Proyectos\UnionDNIs\`
- **Pip dentro del venv**: `.\venv\Scripts\pip.exe`
- **Python dentro del venv**: `.\venv\Scripts\python.exe`

### Dependencias ya instaladas en el venv

```
opencv-python, numpy, imutils, Pillow, fastapi, uvicorn[standard],
python-multipart, img2pdf, reportlab, python-docx, pytesseract
```

### Dependencia externa (binario del sistema)

Tesseract OCR necesita estar instalado como binario del sistema.
Si no está instalado, ejecutar:
```powershell
winget install UB-Mannheim.TesseractOCR
```
La ruta típica en Windows es: `C:\Program Files\Tesseract-OCR\tesseract.exe`

En `app/ocr.py`, configurar:
```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

---

## Estructura de Archivos a Crear

```
UnionDNIs/
├── app/
│   ├── __init__.py          (DONE — no tocar)
│   ├── utils.py             (DONE — revisar antes de continuar)
│   ├── scanner.py           (DONE — revisar antes de continuar)
│   ├── enhancer.py          (DONE — revisar antes de continuar)
│   ├── ocr.py               (PENDIENTE)
│   ├── exporter.py          (PENDIENTE)
│   └── main.py              (PENDIENTE)
├── static/
│   ├── index.html           (PENDIENTE)
│   ├── styles.css           (PENDIENTE)
│   └── app.js               (PENDIENTE)
├── uploads/                 (crear directorio vacío)
├── output/                  (crear directorio vacío)
├── requirements.txt         (DONE)
├── run.py                   (PENDIENTE)
└── README.md                (PENDIENTE)
```

---

## FASE 0 — Verificar archivos existentes

Antes de continuar, leer y verificar los 4 archivos ya creados:

1. `app/utils.py` — contiene: `order_points()`, `four_point_transform()`, `resize_with_aspect()`, `auto_canny()`
2. `app/scanner.py` — contiene: `detect_document()`, `apply_transform()`, métodos privados de detección
3. `app/enhancer.py` — contiene: `enhance_scan(image, mode)` con modos "color", "bw", "original"
4. `requirements.txt` — lista de dependencias

Crear los directorios vacíos si no existen:
```powershell
mkdir uploads, output -Force
```

---

## FASE 1 — `app/ocr.py` (OCR local con Tesseract)

### Propósito
Extraer texto de los documentos escaneados. Especialmente útil para la zona MRZ
(Machine Readable Zone) que aparece al final de los pasaportes y DNI modernos.

### Funciones a implementar

#### `check_tesseract_available() -> bool`
Verificar si el binario de Tesseract está presente en el sistema.
Si no está disponible, las funciones de OCR deben devolver cadenas vacías
en lugar de lanzar excepciones.

```python
def check_tesseract_available() -> bool:
    """Retorna True si Tesseract está instalado y accesible."""
    import shutil
    return shutil.which("tesseract") is not None or os.path.exists(
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
```

#### `extract_text(image: np.ndarray, lang: str = "spa+eng") -> str`
OCR general sobre la imagen completa del documento.

```python
def extract_text(image: np.ndarray, lang: str = "spa+eng") -> str:
    """
    Extrae todo el texto visible en la imagen.
    
    Args:
        image: Imagen BGR del documento ya corregido
        lang: Idiomas para Tesseract (spa+eng para DNI español)
        
    Returns:
        Texto extraído como string, o "" si Tesseract no está disponible
    """
```

Implementación:
1. Convertir imagen a escala de grises
2. Aplicar umbralización adaptativa para mejorar contraste
3. Usar `pytesseract.image_to_string(gray, lang=lang, config="--psm 6")`
4. Limpiar el resultado: strip(), eliminar líneas vacías múltiples
5. Capturar cualquier excepción y devolver ""

#### `extract_mrz(image: np.ndarray) -> dict`
Detectar y extraer la zona MRZ del pasaporte/DNI.

```python
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
```

Implementación:
1. Tomar la región inferior (30% de la altura) de la imagen
2. Convertir a gris y aplicar umbralización fuerte
3. Usar pytesseract con config `--psm 6 --oem 1 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<`
4. Detectar tipo por número de caracteres por línea (~44 = pasaporte, ~30 = DNI)
5. Si no hay MRZ detectado, devolver `{"detected": False, "raw": "", "lines": [], "type": "unknown"}`

#### `parse_mrz_fields(mrz_data: dict) -> dict`
Parsear los campos del MRZ.

```python
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
```

Implementación para DNI español (tipo ID1, 3 líneas × 30 chars):
- Línea 1: tipo doc (2) + país (3) + número (9) + dígito control + opcional (15)
- Línea 2: nacimiento (6) + dígito + sexo (1) + expiración (6) + dígito + nacionalidad (3) + ... 
- Línea 3: apellidos<<nombre

Implementación para pasaporte (tipo TD3, 2 líneas × 44 chars):
- Línea 1: 'P' + tipo (1) + país (3) + apellido<<nombre (39)
- Línea 2: número (9) + dígito + nacionalidad (3) + nacimiento (6) + dígito + sexo (1) + expiración (6) + dígito + personal (14) + dígito

Reemplazar `<` por espacio, manejar errores con try/except.

---

## FASE 2 — `app/exporter.py` (Generación de documentos)

### Propósito
Combinar las dos imágenes procesadas (cara frontal + cara trasera) en un documento final.

### Imports necesarios
```python
import io
import os
from datetime import datetime
import numpy as np
import cv2
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import docx
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
```

### Función auxiliar: `_bgr_to_pil(image: np.ndarray) -> Image`
Convierte imagen OpenCV (BGR) a PIL (RGB).

### Función auxiliar: `_pil_to_bytes(pil_image: Image, format: str = "JPEG") -> bytes`
Convierte PIL image a bytes para embeber en documentos.

### `export_pdf(front_image, back_image, output_path: str) -> str`

```python
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
```

**Implementación con ReportLab:**

```python
# Dimensiones A4 en puntos (1 pt = 1/72 pulgada)
width, height = A4   # 595.28 x 841.89 pts

c = canvas.Canvas(output_path, pagesize=A4)

# --- Encabezado ---
c.setFont("Helvetica-Bold", 10)
c.setFillColor(colors.HexColor("#2d3748"))
c.drawCentredString(width / 2, height - 30, title)
c.setFont("Helvetica", 8)
c.setFillColor(colors.HexColor("#718096"))
fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
c.drawCentredString(width / 2, height - 45, f"Generado: {fecha}")

# Línea divisora
c.setStrokeColor(colors.HexColor("#e2e8f0"))
c.setLineWidth(0.5)
c.line(30, height - 55, width - 30, height - 55)

# --- Área para imágenes ---
# Calcular espacio disponible: A4 alto (841) - encabezado (70) - margen inferior (30) - gap entre (20) - etiquetas (30) = ~692 pts
# Dividir en 2 imágenes de ~336 pts de alto cada una
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
    c.drawImage(img_reader, x_centered, y_front + (image_height - draw_h) / 2,
                width=draw_w, height=draw_h)
else:
    # Placeholder vacío
    c.setFillColor(colors.HexColor("#f7fafc"))
    c.rect(margin_x, y_front, available_width, image_height, fill=1, stroke=0)
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#a0aec0"))
    c.drawCentredString(width / 2, y_front + image_height / 2, "Cara frontal no proporcionada")

# Etiqueta frontal
c.setFont("Helvetica-Bold", 8)
c.setFillColor(colors.HexColor("#4a5568"))
c.drawCentredString(width / 2, y_front - 12, "▲ CARA FRONTAL")

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
    c.drawImage(img_reader_back, x_centered, y_back + (image_height - draw_h) / 2,
                width=draw_w, height=draw_h)
else:
    c.setFillColor(colors.HexColor("#f7fafc"))
    c.rect(margin_x, y_back, available_width, image_height, fill=1, stroke=0)

# Etiqueta trasera
c.drawCentredString(width / 2, y_back - 12, "▼ CARA TRASERA")

c.save()
return output_path
```

**Import adicional necesario:**
```python
from reportlab.lib.utils import ImageReader
```

---

### `export_word(front_image, back_image, output_path: str) -> str`

```python
def export_word(
    front_image: np.ndarray | None,
    back_image: np.ndarray | None,
    output_path: str,
    title: str = "Documento de Identidad"
) -> str:
    """
    Genera documento Word (.docx) con ambas caras en la misma página.
    """
```

Implementación:
1. `doc = docx.Document()`
2. Configurar márgenes: `doc.sections[0].top_margin = Cm(1.5)`, etc.
3. Añadir título centrado con estilo "Heading 1", color #2d3748
4. Añadir fecha pequeña centrada
5. Añadir separador horizontal
6. Para cada imagen (frontal y trasera):
   - Convertir numpy → PIL → bytes → io.BytesIO
   - `doc.add_paragraph("CARA FRONTAL").alignment = WD_ALIGN_PARAGRAPH.CENTER`
   - `doc.add_picture(BytesIO, width=Inches(5.5))` — max 5.5 pulgadas de ancho
   - Párrafo vacío de separación
7. `doc.save(output_path)`

---

### `export_image(front_image, back_image, output_path: str) -> str`

```python
def export_image(
    front_image: np.ndarray | None,
    back_image: np.ndarray | None,
    output_path: str
) -> str:
    """
    Genera una imagen PNG combinada (ambas caras una encima de la otra).
    Añade un fondo gris claro y padding entre las imágenes.
    """
```

Implementación:
1. Determinar ancho máximo entre las dos imágenes
2. Redimensionar ambas al mismo ancho manteniendo ratio
3. Crear canvas blanco: `canvas = np.full((alto_total + padding, max_width, 3), 240, dtype=np.uint8)`
4. Pegar frontal arriba, trasera abajo, con padding de 20px entre ellas
5. Guardar con `cv2.imwrite(output_path, canvas)`

---

## FASE 3 — `app/main.py` (API FastAPI)

### Imports
```python
import os
import uuid
import json
import shutil
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .scanner import detect_document, apply_transform
from .enhancer import enhance_scan
from .ocr import extract_text, extract_mrz, parse_mrz_fields, check_tesseract_available
from .exporter import export_pdf, export_word, export_image
```

### Configuración de la App

```python
app = FastAPI(
    title="UnionDNIs API",
    description="Escáner local de documentos de identidad",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Montar archivos estáticos (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")
```

### Modelos Pydantic

```python
class TransformRequest(BaseModel):
    session_id: str          # ID único de la sesión
    side: str                # "front" | "back"
    corners: list            # [[x,y],[x,y],[x,y],[x,y]] o None para auto
    enhance_mode: str = "color"  # "color" | "bw" | "original"

class ExportRequest(BaseModel):
    session_id: str
    format: str = "pdf"      # "pdf" | "word" | "image"
    include_ocr: bool = True
```

### Endpoints

---

#### `GET /`
```python
@app.get("/")
async def root():
    return FileResponse("static/index.html")
```

---

#### `POST /api/upload`

```python
@app.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    side: str = Form(...),      # "front" | "back"
    session_id: str = Form(None)
):
    """
    Sube una imagen (frontal o trasera) al servidor.
    Guarda la imagen en uploads/{session_id}/{side}_original.jpg
    Devuelve la detección automática de esquinas.
    
    Returns:
        {
            "session_id": str,
            "side": "front" | "back",
            "filename": str,
            "detection": {
                "corners": [[x,y],...] | null,
                "confidence": float,
                "method": str
            },
            "image_size": [width, height]
        }
    """
```

Implementación:
1. Si `session_id` es None, generar uno nuevo: `session_id = str(uuid.uuid4())[:8]`
2. Crear directorio: `uploads/{session_id}/`
3. Guardar el archivo como `{side}_original.jpg`
4. Leer con OpenCV: `img = cv2.imdecode(np.frombuffer(await file.read(), np.uint8), cv2.IMREAD_COLOR)`
5. Llamar `detect_document(img)` para obtener las esquinas
6. Devolver JSON con session_id, detection result e image_size

---

#### `POST /api/transform`

```python
@app.post("/api/transform")
async def transform_image(request: TransformRequest):
    """
    Aplica corrección de perspectiva y mejora de imagen.
    Guarda resultado en uploads/{session_id}/{side}_processed.jpg
    
    Si request.corners es None, usa detección automática.
    Si request.corners tiene 4 puntos, usa esos directamente.
    
    Returns:
        {
            "session_id": str,
            "side": str,
            "processed_path": str,
            "preview_url": str  # URL para ver preview
        }
    """
```

Implementación:
1. Cargar `uploads/{session_id}/{side}_original.jpg`
2. Si corners es None: usar `detect_document(img)` → extraer corners
3. Si corners es lista: usar directamente
4. Si no hay corners en ningún caso: devolver 400 con mensaje claro
5. Aplicar `apply_transform(img, corners)` → imagen corregida
6. Aplicar `enhance_scan(warped, request.enhance_mode)`
7. Guardar en `uploads/{session_id}/{side}_processed.jpg`
8. Devolver preview URL: `/api/preview/{session_id}/{side}`

---

#### `GET /api/preview/{session_id}/{side}`

```python
@app.get("/api/preview/{session_id}/{side}")
async def get_preview(session_id: str, side: str):
    """Devuelve la imagen procesada como JPEG para preview."""
```

Implementación:
- Construir ruta: `uploads/{session_id}/{side}_processed.jpg`
- Si no existe, intentar `uploads/{session_id}/{side}_original.jpg`  
- Si no existe ninguna: 404
- Devolver `FileResponse(path, media_type="image/jpeg")`

---

#### `POST /api/ocr`

```python
@app.post("/api/ocr")
async def run_ocr(session_id: str = Form(...), side: str = Form(...)):
    """
    Ejecuta OCR sobre la imagen procesada.
    
    Returns:
        {
            "available": bool,       # ¿Tesseract instalado?
            "text": str,             # Texto extraído
            "mrz": {                 # Datos MRZ
                "detected": bool,
                "raw": str,
                "lines": list,
                "type": str,
                "fields": dict       # Campos parseados
            }
        }
    """
```

Implementación:
1. `available = check_tesseract_available()`
2. Si no available: devolver `{"available": False, "text": "", "mrz": {}}`
3. Cargar imagen procesada
4. `text = extract_text(img)`
5. `mrz = extract_mrz(img)`
6. `fields = parse_mrz_fields(mrz)`
7. Devolver dict completo

---

#### `POST /api/export`

```python
@app.post("/api/export")
async def export_document(request: ExportRequest):
    """
    Genera el documento final combinando ambas caras.
    
    Returns:
        {
            "filename": str,
            "download_url": str,
            "format": str
        }
    """
```

Implementación:
1. Cargar imágenes procesadas de `uploads/{request.session_id}/`
   - `front_processed.jpg` si existe, else None
   - `back_processed.jpg` si existe, else None
   - Al menos una debe existir, sino 400
2. Generar nombre único: `dni_{session_id}_{timestamp}.{ext}`
3. Ruta de salida: `output/{filename}`
4. Según `request.format`:
   - `"pdf"` → `export_pdf(front, back, output_path)`
   - `"word"` → `export_word(front, back, output_path)`
   - `"image"` → `export_image(front, back, output_path)`
5. Devolver `{"filename": filename, "download_url": f"/api/download/{filename}"}`

---

#### `GET /api/download/{filename}`

```python
@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Descarga el documento generado."""
```

Implementación:
- Verificar que el archivo existe en `output/`
- Detectar content_type según extensión: pdf, docx, png
- Devolver `FileResponse` con `Content-Disposition: attachment`

---

#### `DELETE /api/session/{session_id}` (cleanup)

```python
@app.delete("/api/session/{session_id}")
async def cleanup_session(session_id: str):
    """Elimina los archivos temporales de la sesión."""
```

Implementación:
- `shutil.rmtree(f"uploads/{session_id}", ignore_errors=True)`
- Devolver `{"deleted": True}`

---

#### `GET /api/status`

```python
@app.get("/api/status")
async def status():
    """Healthcheck + info del sistema."""
    return {
        "status": "ok",
        "tesseract": check_tesseract_available(),
        "version": "1.0.0"
    }
```

---

## FASE 4 — `static/index.html` (Frontend)

### Estructura HTML5 completa

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Escáner local de DNI y pasaporte. Genera PDF, Word o imagen desde fotos de móvil.">
    <title>UnionDNIs — Escáner de Documentos</title>
    <link rel="stylesheet" href="/static/styles.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <!-- Header -->
    <header class="app-header">
        <div class="logo">
            <span class="logo-icon">🪪</span>
            <span class="logo-text">UnionDNIs</span>
        </div>
        <div class="status-badge" id="status-badge">
            <span class="status-dot"></span>
            <span>Local · Privado</span>
        </div>
    </header>

    <!-- Main content -->
    <main class="app-main">
        
        <!-- PASO 1: Subir imágenes -->
        <section class="step-section" id="step-upload">
            <div class="step-header">
                <div class="step-number">1</div>
                <h2>Sube las fotos del documento</h2>
            </div>
            
            <div class="upload-grid">
                <!-- Cara frontal -->
                <div class="upload-card" id="card-front">
                    <div class="upload-zone" id="drop-front">
                        <input type="file" id="input-front" accept="image/*" capture="environment" hidden>
                        <div class="upload-placeholder" id="placeholder-front">
                            <div class="upload-icon">📷</div>
                            <p class="upload-label">Cara <strong>frontal</strong></p>
                            <p class="upload-hint">Toca para abrir cámara<br>o arrastra una foto</p>
                            <button class="btn-upload" onclick="document.getElementById('input-front').click()">
                                Subir frontal
                            </button>
                        </div>
                        <div class="upload-preview" id="preview-front" hidden>
                            <img id="img-front" src="" alt="Vista previa cara frontal">
                            <div class="preview-actions">
                                <button class="btn-sm btn-secondary" onclick="retakePhoto('front')">↩ Cambiar</button>
                                <span class="detection-badge" id="detection-front"></span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Canvas para selección manual de esquinas -->
                    <div class="corner-selector" id="corner-selector-front" hidden>
                        <p class="corner-hint">Haz clic en las <strong>4 esquinas</strong> del documento en orden:<br>
                        1. Superior izq → 2. Superior der → 3. Inferior der → 4. Inferior izq</p>
                        <canvas id="canvas-front" class="corner-canvas"></canvas>
                        <div class="corner-controls">
                            <button class="btn-sm btn-danger" onclick="resetCorners('front')">🔄 Reiniciar</button>
                            <button class="btn-sm btn-primary" id="btn-apply-front" onclick="applyManualCorners('front')" disabled>✓ Aplicar</button>
                        </div>
                    </div>
                </div>

                <!-- Cara trasera (estructura idéntica con id="card-back") -->
                <div class="upload-card" id="card-back">
                    <div class="upload-zone" id="drop-back">
                        <input type="file" id="input-back" accept="image/*" capture="environment" hidden>
                        <div class="upload-placeholder" id="placeholder-back">
                            <div class="upload-icon">📷</div>
                            <p class="upload-label">Cara <strong>trasera</strong></p>
                            <p class="upload-hint">Toca para abrir cámara<br>o arrastra una foto</p>
                            <button class="btn-upload" onclick="document.getElementById('input-back').click()">
                                Subir trasera
                            </button>
                        </div>
                        <div class="upload-preview" id="preview-back" hidden>
                            <img id="img-back" src="" alt="Vista previa cara trasera">
                            <div class="preview-actions">
                                <button class="btn-sm btn-secondary" onclick="retakePhoto('back')">↩ Cambiar</button>
                                <span class="detection-badge" id="detection-back"></span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="corner-selector" id="corner-selector-back" hidden>
                        <p class="corner-hint">Haz clic en las <strong>4 esquinas</strong> del documento en orden:<br>
                        1. Superior izq → 2. Superior der → 3. Inferior der → 4. Inferior izq</p>
                        <canvas id="canvas-back" class="corner-canvas"></canvas>
                        <div class="corner-controls">
                            <button class="btn-sm btn-danger" onclick="resetCorners('back')">🔄 Reiniciar</button>
                            <button class="btn-sm btn-primary" id="btn-apply-back" onclick="applyManualCorners('back')" disabled>✓ Aplicar</button>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- PASO 2: Opciones de procesamiento -->
        <section class="step-section" id="step-options" hidden>
            <div class="step-header">
                <div class="step-number">2</div>
                <h2>Opciones</h2>
            </div>
            
            <div class="options-grid">
                <!-- Modo de imagen -->
                <div class="option-group">
                    <label class="option-label">Modo de imagen</label>
                    <div class="toggle-group" id="enhance-mode">
                        <button class="toggle-btn active" data-value="color">🎨 Color</button>
                        <button class="toggle-btn" data-value="bw">⬛ Escáner</button>
                        <button class="toggle-btn" data-value="original">📷 Original</button>
                    </div>
                </div>
                
                <!-- Formato de salida -->
                <div class="option-group">
                    <label class="option-label">Formato de salida</label>
                    <div class="toggle-group" id="output-format">
                        <button class="toggle-btn active" data-value="pdf">📄 PDF</button>
                        <button class="toggle-btn" data-value="word">📝 Word</button>
                        <button class="toggle-btn" data-value="image">🖼️ Imagen PNG</button>
                    </div>
                </div>
                
                <!-- OCR -->
                <div class="option-group">
                    <label class="option-label">Extracción de texto (OCR)</label>
                    <label class="switch">
                        <input type="checkbox" id="ocr-toggle" checked>
                        <span class="slider"></span>
                    </label>
                    <span class="option-hint">Leer texto y zona MRZ</span>
                </div>
            </div>
        </section>

        <!-- PASO 3: Procesar y descargar -->
        <section class="step-section" id="step-export" hidden>
            <div class="step-header">
                <div class="step-number">3</div>
                <h2>Generar documento</h2>
            </div>
            
            <div class="export-area">
                <!-- Preview procesado (lado a lado) -->
                <div class="processed-preview" id="processed-preview" hidden>
                    <div class="preview-pair">
                        <div class="preview-item">
                            <p class="preview-item-label">Cara Frontal (procesada)</p>
                            <img id="processed-front" src="" alt="Frontal procesada">
                        </div>
                        <div class="preview-item">
                            <p class="preview-item-label">Cara Trasera (procesada)</p>
                            <img id="processed-back" src="" alt="Trasera procesada">
                        </div>
                    </div>
                </div>
                
                <!-- Resultados OCR (colapsable) -->
                <details class="ocr-results" id="ocr-section" hidden>
                    <summary>🔍 Texto extraído (OCR)</summary>
                    <div class="ocr-content">
                        <div class="ocr-tabs">
                            <button class="tab-btn active" data-tab="fields">Campos</button>
                            <button class="tab-btn" data-tab="mrz">MRZ Raw</button>
                            <button class="tab-btn" data-tab="full">Texto completo</button>
                        </div>
                        <div class="tab-content" id="tab-fields">
                            <table class="ocr-table" id="ocr-fields-table">
                                <!-- Relleno dinámicamente por JS -->
                            </table>
                        </div>
                        <div class="tab-content" id="tab-mrz" hidden>
                            <pre class="mrz-raw" id="mrz-raw-text"></pre>
                        </div>
                        <div class="tab-content" id="tab-full" hidden>
                            <pre class="ocr-raw" id="ocr-full-text"></pre>
                        </div>
                    </div>
                </details>
                
                <!-- Botón de generación -->
                <div class="export-controls">
                    <button class="btn-primary btn-large" id="btn-generate" onclick="generateDocument()">
                        <span class="btn-icon">⚡</span>
                        Generar documento
                    </button>
                    
                    <!-- Estado de progreso -->
                    <div class="progress-area" id="progress-area" hidden>
                        <div class="progress-bar">
                            <div class="progress-fill" id="progress-fill"></div>
                        </div>
                        <p class="progress-text" id="progress-text">Procesando...</p>
                    </div>
                    
                    <!-- Resultado final -->
                    <div class="result-area" id="result-area" hidden>
                        <div class="result-card">
                            <span class="result-icon">✅</span>
                            <div class="result-info">
                                <p class="result-filename" id="result-filename"></p>
                                <a class="btn-download" id="btn-download" href="#" download>
                                    ⬇️ Descargar
                                </a>
                            </div>
                        </div>
                        <button class="btn-secondary btn-sm" onclick="resetAll()">
                            🔄 Escanear otro documento
                        </button>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <!-- Toast de notificaciones -->
    <div class="toast-container" id="toast-container"></div>

    <script src="/static/app.js"></script>
</body>
</html>
```

---

## FASE 5 — `static/styles.css`

### Sistema de diseño (variables CSS)

```css
:root {
    /* Paleta de colores — dark mode premium */
    --bg-primary: #0f1117;
    --bg-secondary: #1a1d2e;
    --bg-card: #1e2139;
    --bg-card-hover: #252849;
    --border-subtle: rgba(255,255,255,0.08);
    --border-active: rgba(99,102,241,0.6);
    
    /* Acentos */
    --accent-primary: #6366f1;      /* Indigo */
    --accent-primary-hover: #818cf8;
    --accent-secondary: #06b6d4;    /* Cyan */
    --accent-success: #10b981;      /* Emerald */
    --accent-danger: #ef4444;
    --accent-warning: #f59e0b;
    
    /* Texto */
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #475569;
    
    /* Gradientes */
    --gradient-hero: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
    --gradient-card: linear-gradient(145deg, #1e2139 0%, #252849 100%);
    
    /* Sombras */
    --shadow-card: 0 4px 24px rgba(0,0,0,0.4);
    --shadow-glow: 0 0 20px rgba(99,102,241,0.3);
    
    /* Tipografía */
    --font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
    
    /* Espaciado */
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 20px;
    --radius-xl: 28px;
    
    /* Transiciones */
    --transition-fast: 150ms ease;
    --transition-normal: 250ms ease;
    --transition-slow: 400ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

### Estilos principales a implementar

**Reset y base:**
```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
    font-family: var(--font-family);
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}
```

**Header:**
- Fondo con `backdrop-filter: blur(20px)` y borde inferior sutil
- Logo con gradiente de texto (`background-clip: text`)
- Status badge con punto pulsante en verde (animación CSS `pulse`)
- `position: sticky; top: 0; z-index: 100`

**step-section:**
- Card con glassmorphism: `background: var(--gradient-card)`, `border: 1px solid var(--border-subtle)`, `border-radius: var(--radius-xl)`
- Animación de entrada `fade-in-up` al aparecer (usar `@keyframes` + clase `.visible`)
- Separación entre secciones de al menos 24px

**upload-grid:**
- CSS Grid: `grid-template-columns: 1fr 1fr` en desktop, `1fr` en mobile (media query `max-width: 640px`)

**upload-zone:**
- Borde punteado con `border: 2px dashed var(--border-subtle)`
- Al hover: `border-color: var(--accent-primary)`, transición suave
- Al arrastrar (`dragover`): `background: rgba(99,102,241,0.1)`, borde sólido
- Altura mínima: 280px
- `cursor: pointer`

**Botones principales:**
```css
.btn-primary {
    background: var(--gradient-hero);
    color: white;
    border: none;
    padding: 14px 28px;
    border-radius: var(--radius-md);
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
    transition: var(--transition-normal);
    box-shadow: var(--shadow-glow);
}
.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(99,102,241,0.5);
}
.btn-primary:active { transform: translateY(0); }

.btn-large {
    padding: 18px 48px;
    font-size: 1.125rem;
    border-radius: var(--radius-lg);
}
```

**Toggle group:**
- Grupo de botones con fondo oscuro
- Botón activo: `background: var(--accent-primary)`, texto blanco
- Transición suave al cambiar

**Switch (toggle OCR):**
- CSS puro para el switch, estilo iOS moderno
- Color ON: `var(--accent-success)`

**detection-badge:**
- Verde con check si confianza > 0.6: `"✓ Detectado automáticamente"`
- Naranja con warning si confianza 0.3-0.6: `"⚠ Baja confianza — revisa manualmente"`
- Rojo con X si confianza < 0.3: `"✗ No detectado — selección manual requerida"`

**corner-canvas:**
- Canvas para dibujar las esquinas seleccionadas
- Cursor `crosshair`
- Puntos marcados con círculos numerados (1-4)
- Líneas conectando los puntos

**progress-bar:**
- Gradiente animado: `background: var(--gradient-hero)`
- Animación shimmer con `@keyframes`
- Transición fluida del ancho

**toast-container:**
- Posición `fixed; bottom: 24px; right: 24px`
- Toasts con entrada slide-in desde derecha
- Auto-dismiss tras 4 segundos
- Variantes: success (verde), error (rojo), info (azul)

**ocr-results (details/summary):**
- Summary con flecha animada al expandir
- Tabla de campos con alternancia de filas

**Responsive Media Queries:**
- `@media (max-width: 640px)`: stack vertical, botones full-width
- `@media (max-width: 390px)`: reducir padding, fuentes ligeramente menores

---

## FASE 6 — `static/app.js`

### Estado de la aplicación

```javascript
const state = {
    sessionId: null,
    front: { uploaded: false, corners: null, processed: false },
    back:  { uploaded: false, corners: null, processed: false },
    enhanceMode: 'color',
    outputFormat: 'pdf',
    includeOcr: true,
    manualCorners: { front: [], back: [] },
    ocrResults: { front: null, back: null }
};
```

### Funciones a implementar

#### `initApp()`
- Comprobar `/api/status` para ver si Tesseract está disponible
- Si no está: mostrar toast informativo y deshabilitar checkbox de OCR
- Configurar event listeners para drag & drop, inputs de archivo, toggles

#### `handleFileSelect(side, file)`
```javascript
async function handleFileSelect(side, file) {
    // 1. Validar que es imagen y pesa < 20MB
    // 2. Mostrar preview local inmediato (URL.createObjectURL)
    // 3. Mostrar loading skeleton en la card
    // 4. Subir al servidor con FormData
    // 5. Procesar respuesta: mostrar detection-badge según confianza
    // 6. Si confianza < 0.5: mostrar corner-selector automáticamente
    // 7. Si confianza >= 0.5: aplicar transform automáticamente
    // 8. Mostrar step-options si hay al menos una imagen subida
}
```

#### `uploadFile(side, file)` → Promise<response>
```javascript
async function uploadFile(side, file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('side', side);
    if (state.sessionId) formData.append('session_id', state.sessionId);
    
    const response = await fetch('/api/upload', { method: 'POST', body: formData });
    if (!response.ok) throw new Error('Error al subir imagen');
    return response.json();
}
```

#### `applyTransform(side, corners = null)` → Promise<void>
```javascript
async function applyTransform(side, corners = null) {
    const body = {
        session_id: state.sessionId,
        side,
        corners,
        enhance_mode: state.enhanceMode
    };
    
    const response = await fetch('/api/transform', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    
    if (!response.ok) throw new Error('Error al procesar imagen');
    
    const data = await response.json();
    
    // Actualizar preview procesado
    const img = document.getElementById(`processed-${side}`);
    img.src = `/api/preview/${state.sessionId}/${side}?t=${Date.now()}`;
    
    state[side].processed = true;
    checkShowExportSection();
}
```

#### Sistema de selección manual de esquinas

```javascript
function initCornerSelector(side) {
    const canvas = document.getElementById(`canvas-${side}`);
    const img = document.getElementById(`img-${side}`);
    
    // Ajustar canvas al tamaño de la imagen
    canvas.width = img.offsetWidth;
    canvas.height = img.offsetHeight;
    
    // Dibujar imagen en el canvas como fondo
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    
    state.manualCorners[side] = [];
    
    canvas.onclick = (e) => {
        if (state.manualCorners[side].length >= 4) return;
        
        const rect = canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left) * (img.naturalWidth / rect.width);
        const y = (e.clientY - rect.top) * (img.naturalHeight / rect.height);
        
        state.manualCorners[side].push([Math.round(x), Math.round(y)]);
        drawCorners(side);
        
        if (state.manualCorners[side].length === 4) {
            document.getElementById(`btn-apply-${side}`).disabled = false;
        }
    };
}

function drawCorners(side) {
    const canvas = document.getElementById(`canvas-${side}`);
    const img = document.getElementById(`img-${side}`);
    const ctx = canvas.getContext('2d');
    const pts = state.manualCorners[side];
    
    // Redibujar imagen de fondo
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    
    // Escala de coordenadas
    const scaleX = canvas.width / img.naturalWidth;
    const scaleY = canvas.height / img.naturalHeight;
    
    // Dibujar líneas entre puntos
    if (pts.length > 1) {
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(99,102,241,0.8)';
        ctx.lineWidth = 2;
        ctx.moveTo(pts[0][0] * scaleX, pts[0][1] * scaleY);
        for (let i = 1; i < pts.length; i++) {
            ctx.lineTo(pts[i][0] * scaleX, pts[i][1] * scaleY);
        }
        if (pts.length === 4) ctx.closePath();
        ctx.stroke();
    }
    
    // Dibujar círculos numerados
    const labels = ['1', '2', '3', '4'];
    pts.forEach((pt, i) => {
        // Círculo
        ctx.beginPath();
        ctx.arc(pt[0] * scaleX, pt[1] * scaleY, 12, 0, 2 * Math.PI);
        ctx.fillStyle = '#6366f1';
        ctx.fill();
        
        // Número
        ctx.fillStyle = 'white';
        ctx.font = 'bold 11px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(labels[i], pt[0] * scaleX, pt[1] * scaleY);
    });
}

function applyManualCorners(side) {
    const corners = state.manualCorners[side];
    if (corners.length !== 4) {
        showToast('Selecciona exactamente 4 esquinas', 'error');
        return;
    }
    document.getElementById(`corner-selector-${side}`).hidden = true;
    applyTransform(side, corners);
}

function resetCorners(side) {
    state.manualCorners[side] = [];
    const canvas = document.getElementById(`canvas-${side}`);
    const img = document.getElementById(`img-${side}`);
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    document.getElementById(`btn-apply-${side}`).disabled = true;
}
```

#### `generateDocument()`
```javascript
async function generateDocument() {
    showProgress(true);
    updateProgress(10, 'Verificando imágenes...');
    
    try {
        // Paso 1: OCR (si está habilitado)
        if (state.includeOcr) {
            updateProgress(30, 'Extrayendo texto...');
            // Llamar /api/ocr para cada cara procesada
            // Mostrar resultados en la sección OCR
        }
        
        updateProgress(60, 'Generando documento...');
        
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId,
                format: state.outputFormat,
                include_ocr: state.includeOcr
            })
        });
        
        if (!response.ok) throw new Error('Error al generar documento');
        
        const data = await response.json();
        
        updateProgress(100, '¡Listo!');
        
        setTimeout(() => {
            showProgress(false);
            showResult(data.filename, data.download_url);
        }, 500);
        
    } catch (err) {
        showProgress(false);
        showToast(`Error: ${err.message}`, 'error');
    }
}
```

#### `showToast(message, type = 'info')`
```javascript
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type]}</span><span>${message}</span>`;
    container.appendChild(toast);
    
    // Trigger animation
    requestAnimationFrame(() => toast.classList.add('toast-show'));
    
    // Auto-dismiss
    setTimeout(() => {
        toast.classList.remove('toast-show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
```

#### `checkShowExportSection()`
- Mostrar `step-export` solo cuando al menos una imagen haya sido procesada
- Animar con clase CSS

#### `resetAll()`
- Llamar `/api/session/{sessionId}` DELETE para limpiar archivos del servidor
- Resetear state completo
- Restaurar UI al estado inicial
- Nuevo sessionId en la próxima subida

#### Event listeners iniciales
```javascript
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    
    // Inputs de archivo
    document.getElementById('input-front').addEventListener('change', e => {
        if (e.target.files[0]) handleFileSelect('front', e.target.files[0]);
    });
    document.getElementById('input-back').addEventListener('change', e => {
        if (e.target.files[0]) handleFileSelect('back', e.target.files[0]);
    });
    
    // Drag & Drop en las zonas de upload
    ['front', 'back'].forEach(side => {
        const zone = document.getElementById(`drop-${side}`);
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-active'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('drag-active'));
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('drag-active');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) handleFileSelect(side, file);
        });
    });
    
    // Toggle buttons (enhance mode)
    document.querySelectorAll('#enhance-mode .toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#enhance-mode .toggle-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.enhanceMode = btn.dataset.value;
            // Re-aplicar transformación si ya hay imágenes procesadas
        });
    });
    
    // Toggle buttons (output format)
    document.querySelectorAll('#output-format .toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#output-format .toggle-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.outputFormat = btn.dataset.value;
        });
    });
    
    // OCR toggle
    document.getElementById('ocr-toggle').addEventListener('change', e => {
        state.includeOcr = e.target.checked;
    });
    
    // Tabs de OCR
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Mostrar tab correspondiente
        });
    });
});
```

---

## FASE 7 — `run.py` (Script de arranque)

```python
"""
Script de arranque para UnionDNIs.
Ejecutar con: python run.py
"""

import uvicorn
import sys
import os

def main():
    print("=" * 50)
    print("  UnionDNIs — Escáner de Documentos")
    print("=" * 50)
    print(f"  Servidor: http://localhost:8000")
    print(f"  Red local: http://0.0.0.0:8000")
    print(f"  Parar: Ctrl+C")
    print("=" * 50)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
```

---

## FASE 8 — `README.md`

Crear README con:
1. Descripción del proyecto
2. Requisitos (Python 3.12, Tesseract OCR)
3. Instalación paso a paso
4. Cómo arrancar (`python run.py`)
5. Cómo acceder desde el móvil (IP local)
6. Capturas de pantalla (omitir si no hay)
7. Licencia: MIT

---

## Notas importantes para Claude Code

### Manejo de errores
- TODOS los endpoints de FastAPI deben tener try/except y devolver errores HTTP con mensajes claros en español
- Las funciones de scanner.py tienen fallback si la detección falla
- El OCR debe degradar gracefully si Tesseract no está instalado

### Rutas y paths
- Usar siempre `pathlib.Path` para manejo de rutas, no string concatenation
- Los directorios `uploads/` y `output/` se crean automáticamente al arrancar

### Conversión de imágenes
- OpenCV usa BGR, Pillow usa RGB → siempre convertir con `cv2.cvtColor(img, cv2.COLOR_BGR2RGB)` al pasar a Pillow
- Al cargar con `cv2.imdecode` desde bytes de UploadFile: `np.frombuffer(file_bytes, np.uint8)`

### Frontend
- No usar ningún framework JS (vanilla JS puro)
- Compatible con Chrome, Firefox, Safari mobile
- El atributo `capture="environment"` en el input file activa la cámara trasera del móvil

### Sesiones
- No hay base de datos. Cada sesión es simplemente un directorio en `uploads/{session_id}/`
- Los archivos son temporales; el usuario puede borrarlos con DELETE /api/session/{id}

### Orden de construcción recomendado
1. Verificar archivos existentes (utils.py, scanner.py, enhancer.py)
2. Crear ocr.py
3. Crear exporter.py
4. Crear main.py
5. Crear static/styles.css
6. Crear static/index.html
7. Crear static/app.js
8. Crear run.py
9. Crear README.md
10. Probar: `.\venv\Scripts\python.exe run.py`

---

## Comando de arranque final

```powershell
cd c:\Users\Usuario\Desktop\Proyectos\UnionDNIs
.\venv\Scripts\python.exe run.py
```

Abrir en navegador: `http://localhost:8000`
