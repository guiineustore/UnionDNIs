# Permiso de Circulación — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir soporte de escaneo para Permiso de Circulación (una sola foto, cualquier orientación) con exportación a PDF/Word/Imagen que respete la orientación real del documento, sin romper el flujo existente de DNI/NIE/Pasaporte.

**Architecture:** Se añaden funciones de exportación de página única en `app/exporter.py` (probadas con TDD/pytest), se enruta `/api/export` según un nuevo campo `document_type` en `ExportRequest`, y se añade un selector de tipo de documento en el frontend que reutiliza sin cambios todo el pipeline existente de subida/rotación/ajuste manual de esquinas. Los cambios de HTML/CSS/JS se verifican manualmente al final (mismo patrón que el plan anterior del proyecto).

**Tech Stack:** Python 3.12, OpenCV, ReportLab, python-docx, Pillow, FastAPI, pytest, vanilla JS.

## Global Constraints

- Todos los endpoints FastAPI envuelven su lógica en try/except con mensajes de error en español (patrón existente en `app/main.py`).
- No se modifican `/api/upload`, `/api/transform`, `/api/rotate`, `/api/preview`, `/api/ocr` — son agnósticos al tipo de documento.
- No se modifica `app/scanner.py`.
- Las funciones existentes de exportación de DNI (`export_pdf`, `export_word`, `export_image`, `_normalize_image_size`, `STANDARD_SIZES`, `_detect_document_type`) permanecen intactas, sin tocar.
- venv en `.\venv\Scripts\` — usar `.\venv\Scripts\python.exe` y `.\venv\Scripts\pip.exe`.
- Plataforma Windows.
- Servidor de pruebas: `.\venv\Scripts\python.exe run.py`.
- Spec de referencia: `docs/superpowers/specs/2026-07-01-permiso-circulacion-design.md`.

---

## Task 1: Exportador — `_choose_page_orientation` + `export_pdf_single`

**Files:**
- Modify: `app/exporter.py`
- Test: `tests/test_exporter_single.py` (crear)

**Interfaces:**
- Produces: `_choose_page_orientation(image: np.ndarray) -> tuple` (devuelve `(width, height)` en puntos ReportLab).
- Produces: `export_pdf_single(image: np.ndarray, output_path: str, title: str = "Documento") -> str`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_exporter_single.py` con:

```python
"""Tests de las funciones de exportación de página única (Permiso de Circulación)."""
import os
import numpy as np
from reportlab.lib.pagesizes import A4, landscape

from app.exporter import _choose_page_orientation, export_pdf_single


def _portrait_image():
    return np.full((900, 600, 3), 255, dtype=np.uint8)


def _landscape_image():
    return np.full((600, 900, 3), 255, dtype=np.uint8)


def _square_image():
    return np.full((700, 700, 3), 255, dtype=np.uint8)


def test_choose_page_orientation_portrait_for_tall_image():
    assert _choose_page_orientation(_portrait_image()) == A4


def test_choose_page_orientation_landscape_for_wide_image():
    assert _choose_page_orientation(_landscape_image()) == landscape(A4)


def test_choose_page_orientation_square_defaults_to_portrait():
    assert _choose_page_orientation(_square_image()) == A4


def test_export_pdf_single_creates_file(tmp_path):
    output_path = str(tmp_path / "permiso.pdf")
    result = export_pdf_single(_portrait_image(), output_path, title="Permiso de Circulación")

    assert result == output_path
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


def test_export_pdf_single_landscape_image(tmp_path):
    output_path = str(tmp_path / "permiso_landscape.pdf")
    result = export_pdf_single(_landscape_image(), output_path, title="Permiso de Circulación")

    assert result == output_path
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0
```

- [ ] **Step 2: Ejecutar el test para confirmar que falla**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_exporter_single.py -v`

Expected: `ImportError`/`ModuleNotFoundError`-style collection error porque `_choose_page_orientation` y `export_pdf_single` todavía no existen en `app/exporter.py`.

- [ ] **Step 3: Commit el test fallando**

```bash
git add tests/test_exporter_single.py
git commit -m "test: agregar tests de exportación de página única (fallando)"
```

- [ ] **Step 4: Añadir `landscape` al import de ReportLab en `app/exporter.py`**

En `app/exporter.py`, línea 15, cambiar:

```python
from reportlab.lib.pagesizes import A4
```

por:

```python
from reportlab.lib.pagesizes import A4, landscape
```

- [ ] **Step 5: Implementar `_choose_page_orientation` y `export_pdf_single`**

En `app/exporter.py`, añadir al final del archivo (después de `export_image`):

```python
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
```

- [ ] **Step 6: Ejecutar los tests para verificar que pasan**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_exporter_single.py -v`
Expected: los 5 tests pasan.

- [ ] **Step 7: Commit**

```bash
git add app/exporter.py
git commit -m "feat(exporter): añadir export_pdf_single con auto-orientación de página"
```

---

## Task 2: Exportador — `export_word_single`

**Files:**
- Modify: `app/exporter.py`
- Test: `tests/test_exporter_single.py`

**Interfaces:**
- Consumes: `_bgr_to_pil`, `_pil_to_bytes` (ya existentes en `app/exporter.py`).
- Produces: `export_word_single(image: np.ndarray, output_path: str, title: str = "Documento") -> str`.

- [ ] **Step 1: Añadir el test que falla**

Añadir al final de `tests/test_exporter_single.py`:

```python
def test_export_word_single_creates_file(tmp_path):
    from app.exporter import export_word_single

    output_path = str(tmp_path / "permiso.docx")
    result = export_word_single(_landscape_image(), output_path, title="Permiso de Circulación")

    assert result == output_path
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


def test_export_word_single_portrait_image(tmp_path):
    from app.exporter import export_word_single

    output_path = str(tmp_path / "permiso_portrait.docx")
    result = export_word_single(_portrait_image(), output_path, title="Permiso de Circulación")

    assert result == output_path
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0
```

- [ ] **Step 2: Ejecutar para confirmar que falla**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_exporter_single.py -v -k word_single`
Expected: `ImportError` porque `export_word_single` no existe todavía.

- [ ] **Step 3: Añadir el import de `WD_ORIENT` en `app/exporter.py`**

En `app/exporter.py`, línea 21, cambiar:

```python
from docx.enum.text import WD_ALIGN_PARAGRAPH
```

por:

```python
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
```

- [ ] **Step 4: Implementar `export_word_single`**

En `app/exporter.py`, añadir al final del archivo:

```python
def export_word_single(
    image: np.ndarray,
    output_path: str,
    title: str = "Documento"
) -> str:
    """
    Genera un documento Word con una única imagen a página completa.
    Usa orientación landscape si la imagen es apaisada, para que la
    imagen no quede diminuta en una página portrait.
    """
    doc = docx.Document()
    section = doc.sections[0]

    h, w = image.shape[:2]
    if w > h:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width

    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run(title)
    title_run.font.size = Pt(16)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)

    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_run = date_para.add_run(f"Generado: {fecha}")
    date_run.font.size = Pt(9)
    date_run.font.color.rgb = RGBColor(0x71, 0x80, 0x96)

    doc.add_paragraph("_" * 50).alignment = WD_ALIGN_PARAGRAPH.CENTER

    pil_image = _bgr_to_pil(image)
    img_bytes = _pil_to_bytes(pil_image)
    img_stream = io.BytesIO(img_bytes)

    usable_width = section.page_width - section.left_margin - section.right_margin
    doc.add_picture(img_stream, width=usable_width)

    doc.save(output_path)
    return output_path
```

- [ ] **Step 5: Ejecutar los tests para verificar que pasan**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_exporter_single.py -v -k word_single`
Expected: los 2 tests pasan.

- [ ] **Step 6: Commit**

```bash
git add app/exporter.py tests/test_exporter_single.py
git commit -m "feat(exporter): añadir export_word_single con orientación landscape automática"
```

---

## Task 3: Exportador — `export_image_single`

**Files:**
- Modify: `app/exporter.py`
- Test: `tests/test_exporter_single.py`

**Interfaces:**
- Produces: `export_image_single(image: np.ndarray, output_path: str) -> str`.

- [ ] **Step 1: Añadir el test que falla**

Añadir al final de `tests/test_exporter_single.py`:

```python
def test_export_image_single_creates_file_with_padding(tmp_path):
    import cv2
    from app.exporter import export_image_single

    output_path = str(tmp_path / "permiso.png")
    image = _portrait_image()
    result = export_image_single(image, output_path)

    assert result == output_path
    saved = cv2.imread(output_path)
    assert saved is not None
    assert saved.shape[0] == image.shape[0] + 40
    assert saved.shape[1] == image.shape[1] + 40
```

- [ ] **Step 2: Ejecutar para confirmar que falla**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_exporter_single.py -v -k image_single`
Expected: `ImportError` porque `export_image_single` no existe todavía.

- [ ] **Step 3: Implementar `export_image_single`**

En `app/exporter.py`, añadir al final del archivo:

```python
def export_image_single(image: np.ndarray, output_path: str) -> str:
    """
    Exporta la imagen procesada como PNG con un margen blanco de acabado,
    sin normalizar a un tamaño de lienzo fijo (a diferencia de export_image,
    pensado para el par frontal/trasera del DNI).
    """
    padding = 20
    bg_color = 240

    h, w = image.shape[:2]
    canvas_img = np.full((h + 2 * padding, w + 2 * padding, 3), bg_color, dtype=np.uint8)
    canvas_img[padding:padding + h, padding:padding + w] = image

    cv2.imwrite(output_path, canvas_img)
    return output_path
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_exporter_single.py -v`
Expected: los 8 tests del archivo pasan.

- [ ] **Step 5: Commit**

```bash
git add app/exporter.py tests/test_exporter_single.py
git commit -m "feat(exporter): añadir export_image_single con margen de acabado"
```

---

## Task 4: Backend — enrutado de `/api/export` por `document_type`

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_main_export.py` (crear)

**Interfaces:**
- Consumes: `export_pdf_single`, `export_word_single`, `export_image_single` (Tasks 1-3).
- Produces: `ExportRequest.document_type: str` (default `"id"`), endpoint `/api/export` con branching por tipo.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_main_export.py` con:

```python
"""Tests del endpoint /api/export con document_type."""
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    upload_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setattr("app.main.UPLOAD_DIR", upload_dir)
    monkeypatch.setattr("app.main.OUTPUT_DIR", output_dir)
    return TestClient(app), upload_dir, output_dir


def test_export_vehicle_requires_front_processed(client):
    test_client, upload_dir, _ = client
    session_dir = upload_dir / "sess1"
    session_dir.mkdir()

    response = test_client.post("/api/export", json={
        "session_id": "sess1",
        "format": "pdf",
        "document_type": "vehicle"
    })

    assert response.status_code == 400
    assert "Permiso de Circulación" in response.json()["detail"]


def test_export_vehicle_generates_permiso_prefixed_pdf(client):
    test_client, upload_dir, output_dir = client
    session_dir = upload_dir / "sess2"
    session_dir.mkdir()

    image = np.full((900, 600, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(session_dir / "front_processed.jpg"), image)

    response = test_client.post("/api/export", json={
        "session_id": "sess2",
        "format": "pdf",
        "document_type": "vehicle"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["filename"].startswith("permiso_sess2_")
    assert (output_dir / data["filename"]).exists()


def test_export_id_default_still_works(client):
    test_client, upload_dir, output_dir = client
    session_dir = upload_dir / "sess3"
    session_dir.mkdir()

    image = np.full((638, 1012, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(session_dir / "front_processed.jpg"), image)

    response = test_client.post("/api/export", json={
        "session_id": "sess3",
        "format": "pdf"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["filename"].startswith("dni_sess3_")
```

- [ ] **Step 2: Ejecutar los tests para confirmar que fallan**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_main_export.py -v`

Expected: `test_export_vehicle_requires_front_processed` y `test_export_vehicle_generates_permiso_prefixed_pdf` FALLAN porque `ExportRequest` no acepta `document_type` (Pydantic lo ignora silenciosamente por defecto, así que en realidad el request pasa validación pero cae en la rama actual sin distinguir tipo — el nombre de archivo no empezará por `permiso_`). `test_export_id_default_still_works` debería PASAR ya (no-regresión).

- [ ] **Step 3: Commit los tests fallando**

```bash
git add tests/test_main_export.py
git commit -m "test: agregar tests de /api/export con document_type (fallando)"
```

- [ ] **Step 4: Actualizar el import de exporter en `app/main.py`**

En `app/main.py`, línea 28, cambiar:

```python
from .exporter import export_pdf, export_word, export_image
```

por:

```python
from .exporter import (
    export_pdf, export_word, export_image,
    export_pdf_single, export_word_single, export_image_single
)
```

- [ ] **Step 5: Añadir `document_type` a `ExportRequest`**

En `app/main.py`, localizar:

```python
class ExportRequest(BaseModel):
    session_id: str
    format: str = "pdf"      # "pdf" | "word" | "image"
    include_ocr: bool = True
```

Reemplazar por:

```python
class ExportRequest(BaseModel):
    session_id: str
    format: str = "pdf"          # "pdf" | "word" | "image"
    include_ocr: bool = True
    document_type: str = "id"    # "id" | "vehicle"
```

- [ ] **Step 6: Reescribir el endpoint `/api/export` con branching por tipo**

En `app/main.py`, reemplazar la función completa:

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
    try:
        session_dir = UPLOAD_DIR / request.session_id

        # Cargar imágenes procesadas
        front_path = session_dir / "front_processed.jpg"
        back_path = session_dir / "back_processed.jpg"

        front_image = cv2.imread(str(front_path)) if front_path.exists() else None
        back_image = cv2.imread(str(back_path)) if back_path.exists() else None

        if front_image is None and back_image is None:
            raise HTTPException(
                status_code=400,
                detail="Al menos una imagen procesada es requerida"
            )

        # Generar nombre único
        timestamp = uuid.uuid4().hex[:8]
        ext_map = {"pdf": "pdf", "word": "docx", "image": "png"}
        ext = ext_map.get(request.format, "pdf")
        filename = f"dni_{request.session_id}_{timestamp}.{ext}"
        output_path = OUTPUT_DIR / filename

        # Exportar según formato
        if request.format == "pdf":
            export_pdf(front_image, back_image, str(output_path))
        elif request.format == "word":
            export_word(front_image, back_image, str(output_path))
        elif request.format == "image":
            export_image(front_image, back_image, str(output_path))
        else:
            raise HTTPException(status_code=400, detail=f"Formato no soportado: {request.format}")

        return {
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "format": request.format
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar: {str(e)}")
```

por:

```python
@app.post("/api/export")
async def export_document(request: ExportRequest):
    """
    Genera el documento final. Para document_type="vehicle" usa la foto
    única del Permiso de Circulación con layout de página completa.
    Para document_type="id" (por defecto) combina frontal + trasera
    como hasta ahora.

    Returns:
        {
            "filename": str,
            "download_url": str,
            "format": str
        }
    """
    try:
        session_dir = UPLOAD_DIR / request.session_id
        ext_map = {"pdf": "pdf", "word": "docx", "image": "png"}
        ext = ext_map.get(request.format, "pdf")
        timestamp = uuid.uuid4().hex[:8]

        if request.document_type == "vehicle":
            front_path = session_dir / "front_processed.jpg"
            front_image = cv2.imread(str(front_path)) if front_path.exists() else None

            if front_image is None:
                raise HTTPException(
                    status_code=400,
                    detail="Se requiere la foto del Permiso de Circulación"
                )

            filename = f"permiso_{request.session_id}_{timestamp}.{ext}"
            output_path = OUTPUT_DIR / filename
            title = "Permiso de Circulación"

            if request.format == "pdf":
                export_pdf_single(front_image, str(output_path), title=title)
            elif request.format == "word":
                export_word_single(front_image, str(output_path), title=title)
            elif request.format == "image":
                export_image_single(front_image, str(output_path))
            else:
                raise HTTPException(status_code=400, detail=f"Formato no soportado: {request.format}")

        else:
            front_path = session_dir / "front_processed.jpg"
            back_path = session_dir / "back_processed.jpg"

            front_image = cv2.imread(str(front_path)) if front_path.exists() else None
            back_image = cv2.imread(str(back_path)) if back_path.exists() else None

            if front_image is None and back_image is None:
                raise HTTPException(
                    status_code=400,
                    detail="Al menos una imagen procesada es requerida"
                )

            filename = f"dni_{request.session_id}_{timestamp}.{ext}"
            output_path = OUTPUT_DIR / filename

            if request.format == "pdf":
                export_pdf(front_image, back_image, str(output_path))
            elif request.format == "word":
                export_word(front_image, back_image, str(output_path))
            elif request.format == "image":
                export_image(front_image, back_image, str(output_path))
            else:
                raise HTTPException(status_code=400, detail=f"Formato no soportado: {request.format}")

        return {
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "format": request.format
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar: {str(e)}")
```

- [ ] **Step 7: Ejecutar los tests para verificar que pasan**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_main_export.py -v`
Expected: los 3 tests pasan.

- [ ] **Step 8: Ejecutar la suite completa para asegurar no-regresión**

Run: `.\venv\Scripts\python.exe -m pytest -v`
Expected: todos los tests pasan (los existentes de scanner/rotate/utils + los nuevos de exporter/main).

- [ ] **Step 9: Commit**

```bash
git add app/main.py
git commit -m "feat(api): enrutar /api/export por document_type (id | vehicle)"
```

---

## Task 5: Frontend — HTML y CSS del selector de tipo de documento

**Files:**
- Modify: `static/index.html`
- Modify: `static/styles.css`

**Interfaces:**
- Produces (ids para JS de Task 6): `#step-document-type`, `#document-type-selector` (con botones `.toggle-btn[data-value="id"|"vehicle"]`), `#card-back` (ya existente, ahora ocultable), `#upload-label-front`, `#upload-hint-front`, `#btn-upload-front`, `#preview-item-front`, `#preview-item-back`, `#preview-label-front`.

- [ ] **Step 1: Insertar la sección de selector de tipo de documento**

En `static/index.html`, localizar:

```html
    <!-- Main content -->
    <main class="app-main">

        <!-- PASO 1: Subir imágenes -->
        <section class="step-section" id="step-upload">
```

Reemplazar por:

```html
    <!-- Main content -->
    <main class="app-main">

        <!-- PASO 0: Tipo de documento -->
        <section class="step-section" id="step-document-type">
            <div class="step-header">
                <div class="step-number">🗂️</div>
                <h2>Tipo de documento</h2>
            </div>
            <div class="toggle-group" id="document-type-selector">
                <button class="toggle-btn active" data-value="id">🪪 DNI / NIE / Pasaporte</button>
                <button class="toggle-btn" data-value="vehicle">🚗 Permiso de Circulación</button>
            </div>
        </section>

        <!-- PASO 1: Subir imágenes -->
        <section class="step-section" id="step-upload">
```

- [ ] **Step 2: Añadir ids a los textos de la tarjeta frontal (para poder cambiarlos por JS)**

En `static/index.html`, localizar:

```html
                        <div class="upload-placeholder" id="placeholder-front">
                            <div class="upload-icon">📷</div>
                            <p class="upload-label">Cara <strong>frontal</strong></p>
                            <p class="upload-hint">Toca para abrir cámara<br>o arrastra una foto</p>
                            <button class="btn-upload" onclick="document.getElementById('input-front').click()">
                                Subir frontal
                            </button>
                        </div>
```

Reemplazar por:

```html
                        <div class="upload-placeholder" id="placeholder-front">
                            <div class="upload-icon">📷</div>
                            <p class="upload-label" id="upload-label-front">Cara <strong>frontal</strong></p>
                            <p class="upload-hint" id="upload-hint-front">Toca para abrir cámara<br>o arrastra una foto</p>
                            <button class="btn-upload" id="btn-upload-front" onclick="document.getElementById('input-front').click()">
                                Subir frontal
                            </button>
                        </div>
```

- [ ] **Step 3: Añadir ids al bloque de preview procesado**

En `static/index.html`, localizar:

```html
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
```

Reemplazar por:

```html
                <div class="processed-preview" id="processed-preview" hidden>
                    <div class="preview-pair">
                        <div class="preview-item" id="preview-item-front">
                            <p class="preview-item-label" id="preview-label-front">Cara Frontal (procesada)</p>
                            <img id="processed-front" src="" alt="Frontal procesada">
                        </div>
                        <div class="preview-item" id="preview-item-back">
                            <p class="preview-item-label">Cara Trasera (procesada)</p>
                            <img id="processed-back" src="" alt="Trasera procesada">
                        </div>
                    </div>
                </div>
```

- [ ] **Step 4: Arreglar el recorte de la miniatura de preview para fotos verticales**

En `static/styles.css`, localizar:

```css
.upload-preview img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: var(--radius-lg);
}
```

Reemplazar por:

```css
.upload-preview img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    border-radius: var(--radius-lg);
}
```

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/styles.css
git commit -m "feat(ui): añadir selector de tipo de documento y ajustar preview para fotos verticales"
```

---

## Task 6: Frontend — lógica JS del selector de tipo de documento

**Files:**
- Modify: `static/app.js`

**Interfaces:**
- Consumes: ids del DOM de Task 5.
- Produces: `state.documentType`, `applyDocumentTypeUI()` (usable por futuras specs, p.ej. Ficha Técnica).

- [ ] **Step 1: Añadir `documentType` al estado**

En `static/app.js`, localizar:

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

Reemplazar por:

```javascript
const state = {
    sessionId: null,
    documentType: 'id',
    front: { uploaded: false, corners: null, processed: false },
    back:  { uploaded: false, corners: null, processed: false },
    enhanceMode: 'color',
    outputFormat: 'pdf',
    includeOcr: true,
    manualCorners: { front: [], back: [] },
    ocrResults: { front: null, back: null }
};
```

- [ ] **Step 2: Añadir `applyDocumentTypeUI()` y usarla en `initApp()`**

En `static/app.js`, localizar:

```javascript
async function initApp() {
    // Comprobar estado del servidor
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (!data.tesseract) {
            showToast('Tesseract no está instalado. El OCR no estará disponible.', 'warning');
            document.getElementById('ocr-toggle').disabled = true;
        }
    } catch (err) {
        console.error('Error al conectar con el servidor:', err);
        showToast('Error de conexión con el servidor', 'error');
    }

    // Mostrar sección de upload con animación
    setTimeout(() => {
        document.getElementById('step-upload').classList.add('visible');
    }, 100);
}
```

Reemplazar por:

```javascript
async function initApp() {
    // Comprobar estado del servidor
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (!data.tesseract) {
            showToast('Tesseract no está instalado. El OCR no estará disponible.', 'warning');
            document.getElementById('ocr-toggle').disabled = true;
        }
    } catch (err) {
        console.error('Error al conectar con el servidor:', err);
        showToast('Error de conexión con el servidor', 'error');
    }

    applyDocumentTypeUI();

    // Mostrar secciones iniciales con animación
    setTimeout(() => {
        document.getElementById('step-document-type').classList.add('visible');
        document.getElementById('step-upload').classList.add('visible');
    }, 100);
}

/**
 * Aplica al DOM los textos y la visibilidad de tarjetas según el tipo
 * de documento seleccionado (state.documentType).
 */
function applyDocumentTypeUI() {
    const isVehicle = state.documentType === 'vehicle';

    document.getElementById('card-back').hidden = isVehicle;

    const previewItemBack = document.getElementById('preview-item-back');
    if (previewItemBack) previewItemBack.hidden = isVehicle;

    const uploadLabel = document.getElementById('upload-label-front');
    const uploadHint = document.getElementById('upload-hint-front');
    const uploadBtn = document.getElementById('btn-upload-front');
    const previewLabel = document.getElementById('preview-label-front');

    if (isVehicle) {
        uploadLabel.innerHTML = '<strong>Permiso de Circulación</strong>';
        uploadHint.innerHTML = 'Toca para abrir cámara<br>o arrastra una foto';
        uploadBtn.textContent = 'Subir foto';
        if (previewLabel) previewLabel.textContent = 'Permiso de Circulación (procesado)';
    } else {
        uploadLabel.innerHTML = 'Cara <strong>frontal</strong>';
        uploadHint.innerHTML = 'Toca para abrir cámara<br>o arrastra una foto';
        uploadBtn.textContent = 'Subir frontal';
        if (previewLabel) previewLabel.textContent = 'Cara Frontal (procesada)';
    }
}
```

- [ ] **Step 3: Enviar `document_type` en `generateDocument()`**

En `static/app.js`, localizar:

```javascript
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId,
                format: state.outputFormat,
                include_ocr: state.includeOcr
            })
        });
```

Reemplazar por:

```javascript
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId,
                format: state.outputFormat,
                include_ocr: state.includeOcr,
                document_type: state.documentType
            })
        });
```

- [ ] **Step 4: Añadir el event listener del selector de tipo de documento**

En `static/app.js`, localizar:

```javascript
    // Toggle buttons (enhance mode)
    document.querySelectorAll('#enhance-mode .toggle-btn').forEach(btn => {
```

Reemplazar por:

```javascript
    // Selector de tipo de documento
    document.querySelectorAll('#document-type-selector .toggle-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (btn.dataset.value === state.documentType) return;

            document.querySelectorAll('#document-type-selector .toggle-btn').forEach(b =>
                b.classList.remove('active'));
            btn.classList.add('active');

            state.documentType = btn.dataset.value;
            await resetAll();
            applyDocumentTypeUI();
        });
    });

    // Toggle buttons (enhance mode)
    document.querySelectorAll('#enhance-mode .toggle-btn').forEach(btn => {
```

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat(ui): lógica JS del selector de tipo de documento"
```

---

## Task 7: Verificación end-to-end manual

**Files:** ninguno (testing exploratorio)

- [ ] **Step 1: Ejecutar la suite completa de tests**

Run: `.\venv\Scripts\python.exe -m pytest -v`
Expected: todos los tests pasan (scanner, rotate, utils, exporter_single, main_export).

- [ ] **Step 2: Arrancar el servidor**

Run: `.\venv\Scripts\python.exe run.py`
Expected: servidor escucha en `http://localhost:8000` sin errores.

- [ ] **Step 3: Probar el flujo de Permiso de Circulación en el navegador**

Usar las fotos de ejemplo en `docs/` (`WhatsApp Image 2026-07-01 at 13.29.01.jpeg`, orientación vertical, y `WhatsApp Image 2026-07-01 at 13.29.21.jpeg`, orientación horizontal). Verificar:

1. Al cargar la página, el selector "Tipo de documento" muestra "DNI/NIE/Pasaporte" activo por defecto y solo se ve la tarjeta "Cara frontal" + "Cara trasera".
2. Pulsar "🚗 Permiso de Circulación" → la tarjeta "trasera" desaparece, la tarjeta única pasa a decir "Permiso de Circulación".
3. Subir la foto vertical → la miniatura se ve completa (sin recortar por `object-fit`).
4. Si la detección automática falla (esperable dado el aspect ratio), usar el botón ✏️ para marcar las 4 esquinas manualmente sobre la cuadrícula/canvas.
5. Generar PDF → descargar → el PDF debe tener orientación portrait, la imagen debe ocupar la página casi completa (sin franjas blancas grandes ni recorte).
6. Repetir con la foto horizontal → el PDF generado debe salir en orientación landscape.
7. Repetir generación en Word e Imagen → verificar visualmente que ambos formatos también respetan la orientación y no aparecen placeholders de "cara trasera".
8. Volver a "DNI/NIE/Pasaporte" y confirmar que el flujo de dos caras sigue funcionando exactamente igual que antes (no-regresión).

- [ ] **Step 4: Commit final**

```bash
git add -A
git commit -m "chore: verificación end-to-end del soporte de Permiso de Circulación"
```

---

## Resumen de cambios por archivo

| Archivo | Cambios |
|---|---|
| `app/exporter.py` | + `_choose_page_orientation`, `export_pdf_single`, `export_word_single`, `export_image_single`; import de `landscape` y `WD_ORIENT` |
| `app/main.py` | + `ExportRequest.document_type`; `/api/export` enruta por tipo; import de las 3 funciones `_single` |
| `static/index.html` | + sección `#step-document-type`; ids nuevos en tarjeta frontal y preview procesado |
| `static/styles.css` | `.upload-preview img` cambia `object-fit: cover` → `contain` |
| `static/app.js` | + `state.documentType`, `applyDocumentTypeUI()`, listener del selector, `document_type` en el payload de export |
| `tests/test_exporter_single.py` | nuevo (8 tests) |
| `tests/test_main_export.py` | nuevo (3 tests) |
