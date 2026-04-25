# Fix Detección Automática + Rotación + Botón Manual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolver 3 problemas confirmados por el usuario tras aplicar IMPROVEMENTS.md: (1) la detección automática de esquinas falla con frecuencia, (2) los botones de rotación distorsionan la imagen y rompen la detección posterior, (3) no hay forma de forzar la corrección manual cuando la detección automática "tiene éxito" pero el resultado es incorrecto.

**Architecture:** Trabajo en TDD sobre la lógica Python pura (`app/scanner.py`, `app/utils.py`, `app/main.py`). Se introduce pytest como infraestructura de tests. Los cambios JS/HTML/CSS se prueban manualmente al final ya que son UI. Se mantienen los archivos existentes — sin reescritura completa, solo modificaciones quirúrgicas.

**Tech Stack:** Python 3.12, OpenCV, NumPy, Pillow (EXIF), FastAPI, pytest (nuevo), vanilla JS.

**Restricciones del entorno:**
- venv en `.\venv\Scripts\` — usar `.\venv\Scripts\python.exe` y `.\venv\Scripts\pip.exe`
- Plataforma Windows — usar `\` o forward slashes según contexto
- Servidor de pruebas: `.\venv\Scripts\python.exe run.py`

---

## Diagnóstico de los problemas

### Problema 1 — La detección automática falla con frecuencia

`app/scanner.py` aplica 4 métodos en cascada (`canny_standard`, `canny_aggressive`, `adaptive_threshold`, `color_channel`). El validador `_validate_aspect_ratio` es muy permisivo (acepta ratios 1.0–2.0) lo que puede dejar pasar cuadrados al azar como "documentos". Y el filtro `min_area = 5%` es bajo: contornos pequeños pasan el corte. Además, el `confidence` se calcula solo a partir del área — no penaliza cuadriláteros muy alejados de los aspect ratios canónicos del DNI/pasaporte.

### Problema 2 — La rotación distorsiona la imagen y rompe la detección

En `app/main.py:/api/rotate`, después de `cv2.rotate()` (que es lossless), se sobreescribe el archivo con `cv2.imwrite(str(original_path), rotated)` usando los parámetros JPEG por defecto (calidad 95). Eso introduce **una segunda recompresión JPEG** sobre la imagen ya comprimida al subir. Tras rotar 2-3 veces, los bordes de la imagen tienen artefactos JPEG visibles que confunden a Canny.

Además, `correct_exif_orientation` ya rota la imagen al hacer `/api/upload`. Si el usuario rota manualmente después, la imagen rotada se guarda en `_original.jpg` perdiendo el rastro EXIF original — pero eso es correcto. El problema real es la **recompresión** y posiblemente que la imagen rotada queda con artefactos en los bordes.

### Problema 3 — Falta botón de override manual

En `static/app.js:handleFileSelect()` el `initCornerSelector(side)` solo se invoca cuando `confidence < 0.5`. Si la detección "tiene éxito" pero recorta mal (p.ej. se queda con la mesa en vez del DNI), el usuario no tiene cómo forzar la selección manual. Hay que añadir un botón **"✏️ Ajustar esquinas"** siempre visible en la preview.

---

## File Structure

**Archivos a crear:**
- `tests/__init__.py` — vacío
- `tests/conftest.py` — fixtures pytest (imagen sintética de DNI)
- `tests/test_scanner.py` — tests de detección de esquinas
- `tests/test_main_rotate.py` — tests del endpoint de rotación (calidad JPEG)
- `tests/test_utils.py` — test de `correct_exif_orientation` (no doble rotación)
- `pytest.ini` — configuración mínima de pytest

**Archivos a modificar:**
- `requirements.txt` — añadir `pytest`, `httpx` (para TestClient)
- `app/scanner.py` — endurecer `_validate_aspect_ratio`, mejorar `_calculate_confidence`, subir `min_area`
- `app/main.py` — guardar JPEG con `IMWRITE_JPEG_QUALITY=100` en `/api/rotate` y `/api/upload`
- `static/index.html` — añadir botón "✏️ Ajustar esquinas" en ambas previews
- `static/app.js` — añadir función `openManualSelector(side)` que carga la imagen original sin condición de confidence
- `static/styles.css` — estilo para el nuevo botón (reutiliza `.btn-icon-sm`)

---

## Task 1: Configurar pytest y dependencias

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Añadir dependencias de testing a requirements.txt**

Añadir al final del archivo `requirements.txt`:

```
pytest>=8.0.0
httpx>=0.27.0
```

- [ ] **Step 2: Instalar las nuevas dependencias en el venv**

Run:
```
.\venv\Scripts\pip.exe install pytest httpx
```
Expected: instalación correcta sin errores.

- [ ] **Step 3: Crear pytest.ini en la raíz del proyecto**

Crear archivo `pytest.ini` con este contenido exacto:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 4: Crear tests/__init__.py vacío**

Crear archivo `tests/__init__.py` vacío (sin contenido).

- [ ] **Step 5: Crear tests/conftest.py con fixture de imagen sintética**

Crear `tests/conftest.py` con:

```python
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
```

- [ ] **Step 6: Verificar que pytest arranca**

Run: `.\venv\Scripts\python.exe -m pytest --collect-only`
Expected: `collected 0 items` (no hay tests todavía, pero pytest debe encontrar `tests/`).

- [ ] **Step 7: Commit**

```
git add requirements.txt pytest.ini tests/__init__.py tests/conftest.py
git commit -m "test: configurar pytest y fixture de imagen sintética"
```

---

## Task 2: Test failing — detección automática debe encontrar el DNI sintético

**Files:**
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_scanner.py` con:

```python
"""Tests del motor de detección de documentos."""
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
```

Añadir el import necesario al principio:
```python
import cv2
```

- [ ] **Step 2: Ejecutar los tests para confirmar que fallan apropiadamente**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_scanner.py -v`

Expected behaviour:
- `test_detects_synthetic_dni` → puede pasar o fallar dependiendo del estado actual
- `test_corners_are_close_to_ground_truth` → idem
- `test_returns_none_on_blank_image` → debe pasar (no hay contornos)
- `test_rejects_low_aspect_ratio_blob` → **DEBE FALLAR** porque actualmente `_validate_aspect_ratio` acepta ratios entre 1.0 y 2.0, incluido 1.0 (cuadrado).

Confirmar que al menos `test_rejects_low_aspect_ratio_blob` falla con el mensaje "Un cuadrado perfecto no es un DNI ni un pasaporte".

- [ ] **Step 3: Commit los tests fallando**

```
git add tests/test_scanner.py
git commit -m "test: agregar tests de detección de documento (fallando)"
```

---

## Task 3: Endurecer la validación de aspect ratio

**Files:**
- Modify: `app/scanner.py` (función `_validate_aspect_ratio`, líneas 205-232)

- [ ] **Step 1: Reemplazar `_validate_aspect_ratio` por una versión más estricta**

En `app/scanner.py`, localizar la función `_validate_aspect_ratio` (línea ~205) y reemplazarla por:

```python
def _validate_aspect_ratio(pts):
    """
    Valida que los 4 puntos forman un rectángulo con aspect ratio
    compatible con un documento de identidad.

    Estricto: solo acepta ratios cercanos a los conocidos
    (DNI/ID-1: 1.586, Pasaporte/ID-3: 1.414) con tolerancia.
    Rechaza cuadrados (ratio ~1.0) y rectángulos extremadamente alargados (>2.5).
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

    # Solo aceptar ratios cercanos a los documentos reales
    for expected_ratio in DOCUMENT_RATIOS.values():
        if abs(ratio - expected_ratio) < RATIO_TOLERANCE:
            return True

    return False
```

- [ ] **Step 2: Reducir RATIO_TOLERANCE para ser más estricto**

En `app/scanner.py`, línea ~29, cambiar:

```python
RATIO_TOLERANCE = 0.35   # Tolerancia amplia para fotos con ángulo
```

por:

```python
RATIO_TOLERANCE = 0.25   # Tolerancia ajustada — rechaza cuadrados y formas no-documento
```

- [ ] **Step 3: Subir `min_area` del 5% al 8% en `_find_document_contour`**

En `app/scanner.py`, línea ~185, cambiar:

```python
    min_area = image_area * 0.05  # Mínimo 5% de la imagen
```

por:

```python
    min_area = image_area * 0.08  # Mínimo 8% de la imagen — evita falsos positivos pequeños
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_scanner.py -v`

Expected:
- `test_rejects_low_aspect_ratio_blob` → PASA (cuadrado rechazado)
- `test_returns_none_on_blank_image` → PASA
- `test_detects_synthetic_dni` → PASA (DNI sintético tiene ratio 1.587)
- `test_corners_are_close_to_ground_truth` → PASA

Si algún test del DNI sintético falla, NO ablandar la validación. Revisar primero si el problema está en la generación del DNI sintético (ajustar conftest.py) o en `_calculate_confidence`.

- [ ] **Step 5: Commit**

```
git add app/scanner.py
git commit -m "fix(scanner): endurecer validación de aspect ratio para rechazar no-documentos"
```

---

## Task 4: Test failing — confidence debe penalizar ratios alejados del DNI

**Files:**
- Modify: `tests/test_scanner.py`

- [ ] **Step 1: Añadir test que mide la confianza relativa**

Añadir al final de `tests/test_scanner.py`:

```python
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
```

- [ ] **Step 2: Ejecutar y verificar que falla (o pasa marginalmente)**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_scanner.py::test_confidence_higher_for_dni_ratio -v`

Expected: puede pasar o fallar — si pasa, este test todavía es útil para evitar regresiones. Si falla, confirmar que el motivo es que la confianza es < 0.75.

- [ ] **Step 3: Mejorar `_calculate_confidence` para incluir penalización por ratio**

En `app/scanner.py`, reemplazar `_calculate_confidence` (línea ~235) por:

```python
def _calculate_confidence(corners, image_shape):
    """
    Calcula una puntuación de confianza basada en:
    - Proporción del área del contorno vs área de la imagen (40%)
    - Cercanía del aspect ratio a un documento conocido (60%)
    """
    area = cv2.contourArea(corners.reshape(-1, 1, 2).astype(np.float32))
    image_area = image_shape[0] * image_shape[1]
    area_ratio = area / image_area

    # Puntuación de área: óptimo entre 15% y 70% de la imagen
    if 0.15 <= area_ratio <= 0.70:
        area_score = 1.0
    elif area_ratio < 0.15:
        area_score = area_ratio / 0.15
    else:
        area_score = max(0.3, 1.0 - (area_ratio - 0.70) / 0.30)

    # Puntuación de aspect ratio
    ordered = order_points(corners)
    (tl, tr, br, bl) = ordered
    width = max(
        np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2)),
        np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    )
    height = max(
        np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2)),
        np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    )
    if width == 0 or height == 0:
        ratio_score = 0.0
    else:
        ratio = max(width, height) / min(width, height)
        best_diff = min(abs(ratio - r) for r in DOCUMENT_RATIOS.values())
        ratio_score = max(0.0, 1.0 - best_diff / RATIO_TOLERANCE)

    confidence = 0.4 * area_score + 0.6 * ratio_score
    return min(confidence, 1.0)
```

- [ ] **Step 4: Ejecutar todos los tests del scanner**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_scanner.py -v`

Expected: todos pasan, incluido el nuevo `test_confidence_higher_for_dni_ratio`.

- [ ] **Step 5: Commit**

```
git add app/scanner.py tests/test_scanner.py
git commit -m "feat(scanner): confidence ahora pondera aspect ratio (60%) además del área (40%)"
```

---

## Task 5: Test failing — la rotación no debe degradar la calidad JPEG

**Files:**
- Create: `tests/test_main_rotate.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_main_rotate.py` con:

```python
"""Test del endpoint de rotación: la calidad JPEG no debe degradarse."""
import io
import os
import shutil
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app, UPLOAD_DIR


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient con UPLOAD_DIR redirigido a tmp_path."""
    monkeypatch.setattr("app.main.UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir(exist_ok=True)
    return TestClient(app)


def _encode_jpeg(image: np.ndarray, quality: int = 95) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert ok
    return buf.tobytes()


def test_rotation_preserves_image_quality(client, synthetic_dni_image, tmp_path):
    """
    Rotar la imagen 4 veces (90° cada vez) debe devolver una imagen
    casi idéntica a la original. Si se recomprime con baja calidad
    en cada paso, la diferencia acumulada es alta.
    """
    image_bytes = _encode_jpeg(synthetic_dni_image, quality=95)

    upload_resp = client.post(
        "/api/upload",
        files={"file": ("front.jpg", image_bytes, "image/jpeg")},
        data={"side": "front"}
    )
    assert upload_resp.status_code == 200
    session_id = upload_resp.json()["session_id"]

    for _ in range(4):
        rotate_resp = client.post(
            "/api/rotate",
            data={"session_id": session_id, "side": "front", "degrees": 90}
        )
        assert rotate_resp.status_code == 200

    final_path = (tmp_path / "uploads") / session_id / "front_original.jpg"
    final_image = cv2.imread(str(final_path))

    diff = cv2.absdiff(synthetic_dni_image, final_image)
    mean_diff = float(np.mean(diff))

    assert mean_diff < 3.0, (
        f"Tras 4 rotaciones de 90°, la imagen debería ser casi idéntica a la original "
        f"(diff < 3.0). Obtuvo {mean_diff:.2f} — probablemente recompresión JPEG agresiva."
    )
```

- [ ] **Step 2: Ejecutar el test para confirmar que falla**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_main_rotate.py -v`

Expected: **FALLA** porque actualmente `cv2.imwrite` en `/api/rotate` usa calidad JPEG por defecto (95) sin pasar parámetros explícitos, y al rotar 4 veces se acumulan artefactos de recompresión. La diferencia media superará 3.0.

Si el test pasa de casualidad, subir el threshold de iteraciones de 4 a 8 hasta forzar el fallo.

- [ ] **Step 3: Commit el test fallando**

```
git add tests/test_main_rotate.py
git commit -m "test: agregar test de calidad de imagen tras rotación (fallando)"
```

---

## Task 6: Guardar JPEG con calidad máxima en upload y rotate

**Files:**
- Modify: `app/main.py` (líneas con `cv2.imwrite`)

- [ ] **Step 1: Añadir constante de calidad JPEG en `app/main.py`**

En `app/main.py`, después de la línea `OUTPUT_DIR.mkdir(exist_ok=True)` (~línea 52), añadir:

```python
# Parámetros JPEG de máxima calidad para imágenes intermedias
# (evita acumulación de artefactos al rotar/transformar varias veces)
JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 100]
```

- [ ] **Step 2: Reemplazar `cv2.imwrite(str(filepath), image)` en `/api/upload`**

En `app/main.py`, línea ~141 dentro de `upload_image()`, cambiar:

```python
        cv2.imwrite(str(filepath), image)
```

por:

```python
        cv2.imwrite(str(filepath), image, JPEG_PARAMS)
```

- [ ] **Step 3: Reemplazar `cv2.imwrite(str(original_path), rotated)` en `/api/rotate`**

En `app/main.py`, línea ~208 dentro de `rotate_image()`, cambiar:

```python
        cv2.imwrite(str(original_path), rotated)
```

por:

```python
        cv2.imwrite(str(original_path), rotated, JPEG_PARAMS)
```

- [ ] **Step 4: Reemplazar `cv2.imwrite(str(processed_path), enhanced)` en `/api/transform`**

En `app/main.py`, línea ~280 dentro de `transform_image()`, cambiar:

```python
        cv2.imwrite(str(processed_path), enhanced)
```

por:

```python
        cv2.imwrite(str(processed_path), enhanced, JPEG_PARAMS)
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_main_rotate.py -v`

Expected: PASA — la diferencia media tras 4 rotaciones está bajo 3.0.

- [ ] **Step 6: Ejecutar la suite completa para asegurar no-regresión**

Run: `.\venv\Scripts\python.exe -m pytest -v`

Expected: todos los tests pasan.

- [ ] **Step 7: Commit**

```
git add app/main.py
git commit -m "fix(main): guardar JPEG con calidad 100 para evitar artefactos por rotación"
```

---

## Task 7: Test failing — `correct_exif_orientation` no debe rotar dos veces

**Files:**
- Create: `tests/test_utils.py`

- [ ] **Step 1: Escribir el test**

Crear `tests/test_utils.py` con:

```python
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
```

- [ ] **Step 2: Ejecutar los tests**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_utils.py -v`

Expected:
- Los 3 tests deberían pasar con la implementación actual de `correct_exif_orientation` porque cuando se re-codifica la imagen con OpenCV se pierde el EXIF, y al re-leer no hay tag de orientación que aplicar.
- Si alguno falla, revisar la implementación. **Importante: estos tests son de NO-REGRESIÓN.** Documentan el comportamiento correcto y nos avisarán si una mejora futura lo rompe.

- [ ] **Step 3: Commit**

```
git add tests/test_utils.py
git commit -m "test: agregar tests de no-regresión para correct_exif_orientation"
```

---

## Task 8: Botón "Ajustar esquinas" siempre visible en HTML

**Files:**
- Modify: `static/index.html` (líneas 50-60 para front, 90-100 para back)

- [ ] **Step 1: Añadir el botón en la preview de la cara frontal**

En `static/index.html`, localizar el bloque `<div class="rotate-controls">` para `front` (líneas 53-57). Justo DESPUÉS de ese div, antes del cierre `</div>` de `.action-row`, añadir:

```html
                                    <button class="btn-icon-sm" onclick="openManualSelector('front')" title="Ajustar esquinas manualmente">✏️</button>
```

El bloque `.action-row` para front debe quedar así:

```html
                                <div class="action-row">
                                    <button class="btn-sm btn-secondary" onclick="retakePhoto('front')">↩ Cambiar</button>
                                    <div class="rotate-controls">
                                        <button class="btn-icon-sm" onclick="rotateImage('front', 270)" title="Rotar izquierda">↺</button>
                                        <button class="btn-icon-sm" onclick="rotateImage('front', 90)" title="Rotar derecha">↻</button>
                                        <button class="btn-icon-sm" onclick="rotateImage('front', 180)" title="Girar 180°">🔃</button>
                                        <button class="btn-icon-sm" onclick="openManualSelector('front')" title="Ajustar esquinas manualmente">✏️</button>
                                    </div>
                                </div>
```

- [ ] **Step 2: Añadir el botón en la preview de la cara trasera**

Localizar el bloque equivalente para `back` (líneas 91-97) y añadir el mismo botón con `'back'`:

```html
                                <div class="action-row">
                                    <button class="btn-sm btn-secondary" onclick="retakePhoto('back')">↩ Cambiar</button>
                                    <div class="rotate-controls">
                                        <button class="btn-icon-sm" onclick="rotateImage('back', 270)" title="Rotar izquierda">↺</button>
                                        <button class="btn-icon-sm" onclick="rotateImage('back', 90)" title="Rotar derecha">↻</button>
                                        <button class="btn-icon-sm" onclick="rotateImage('back', 180)" title="Girar 180°">🔃</button>
                                        <button class="btn-icon-sm" onclick="openManualSelector('back')" title="Ajustar esquinas manualmente">✏️</button>
                                    </div>
                                </div>
```

- [ ] **Step 3: Commit**

```
git add static/index.html
git commit -m "feat(ui): botón 'Ajustar esquinas' siempre visible en cada preview"
```

---

## Task 9: Implementar `openManualSelector(side)` en JS

**Files:**
- Modify: `static/app.js` (añadir nueva función)

- [ ] **Step 1: Añadir la función `openManualSelector` en app.js**

En `static/app.js`, justo DESPUÉS de la función `initCornerSelector(side)` (debe estar alrededor de la línea 258), añadir:

```javascript
/**
 * Abre el selector manual de esquinas a petición del usuario,
 * incluso si la detección automática tuvo confianza alta.
 * Carga la imagen original (sin recorte) y muestra el canvas.
 */
function openManualSelector(side) {
    if (!state.sessionId) {
        showToast('Sube primero una imagen', 'warning');
        return;
    }

    // Forzar carga de la imagen ORIGINAL (sin transform aplicado)
    const imgElement = document.getElementById(`img-${side}`);
    imgElement.src = `/api/preview/${state.sessionId}/${side}?original=1&t=${Date.now()}`;

    // Cuando termine de cargar, inicializar el selector
    imgElement.onload = () => {
        state[side].processed = false;
        initCornerSelector(side);
        showToast('Selecciona las 4 esquinas en orden: TL → TR → BR → BL', 'info');
        imgElement.onload = null;
    };
}
```

- [ ] **Step 2: Verificar manualmente en el navegador**

Run en otra terminal:
```
.\venv\Scripts\python.exe run.py
```

Abrir `http://localhost:8000`, subir una foto de DNI, y comprobar:
1. Tras la subida, aparece el botón ✏️ en la fila de acciones.
2. Al pulsar ✏️ se carga la imagen original y se muestra el canvas para seleccionar esquinas.
3. Tras marcar 4 puntos y pulsar ✓ Aplicar, la imagen se reprocesa con esas esquinas manuales.

Si hay errores de JS, revisar la consola del navegador (F12).

- [ ] **Step 3: Commit**

```
git add static/app.js
git commit -m "feat(ui): función openManualSelector para forzar selección de esquinas"
```

---

## Task 10: Verificación end-to-end manual

**Files:** ninguno (testing exploratorio)

- [ ] **Step 1: Ejecutar la suite completa de tests**

Run: `.\venv\Scripts\python.exe -m pytest -v`

Expected: todos los tests pasan (8+ tests entre scanner, rotate y utils).

- [ ] **Step 2: Arrancar el servidor**

Run: `.\venv\Scripts\python.exe run.py`

Expected: servidor escucha en `http://localhost:8000` sin errores.

- [ ] **Step 3: Probar el flujo completo en el navegador**

Casos a verificar uno por uno:
1. **Detección automática buena**: subir foto nítida de DNI sobre fondo contrastado → la app detecta y muestra "✓ Detectado automáticamente".
2. **Override manual sobre detección buena**: pulsar ✏️ → aparece canvas → marcar 4 esquinas → ✓ Aplicar → la imagen se re-procesa con las nuevas esquinas.
3. **Rotación sin pérdida**: subir foto, rotar 90° → 90° → 90° → 90° (vuelve a la posición inicial). La imagen final debe verse idéntica a la inicial (sin pixelación visible en los bordes).
4. **Detección automática falla**: subir foto borrosa o con fondo similar al DNI → debe aparecer el badge naranja/rojo de baja confianza y el canvas de selección manual debe abrirse automáticamente.
5. **Exportar PDF**: con ambas caras procesadas, generar PDF → descargar → verificar que ambas caras se ven correctamente y con el mismo tamaño.

- [ ] **Step 4: Documentar resultados**

Anotar en el commit final qué casos funcionaron y cuáles no. Si algo falla, abrir un nuevo plan.

- [ ] **Step 5: Commit final**

```
git add -A
git commit -m "chore: verificación end-to-end de fixes (detección + rotación + manual override)"
```

---

## Resumen de cambios por archivo (post-implementación)

| Archivo | Cambios |
|---|---|
| `requirements.txt` | + pytest, httpx |
| `pytest.ini` | nuevo |
| `tests/__init__.py` | nuevo (vacío) |
| `tests/conftest.py` | nuevo (fixtures) |
| `tests/test_scanner.py` | nuevo (5 tests) |
| `tests/test_main_rotate.py` | nuevo (1 test E2E) |
| `tests/test_utils.py` | nuevo (3 tests) |
| `app/scanner.py` | `RATIO_TOLERANCE` 0.35→0.25, `min_area` 5%→8%, `_validate_aspect_ratio` solo acepta ratios canónicos, `_calculate_confidence` pondera ratio+área |
| `app/main.py` | + constante `JPEG_PARAMS`, los 3 `cv2.imwrite` ahora pasan calidad 100 |
| `static/index.html` | + botón ✏️ "Ajustar esquinas" en ambas previews |
| `static/app.js` | + función `openManualSelector(side)` |

---

## Notas técnicas

### Por qué calidad JPEG 100 en lugar de PNG
PNG sería lossless ideal, pero cambiar el formato implicaría modificar todos los lectores y los URLs (.jpg → .png) además del frontend. Calidad 100 en JPEG produce artefactos despreciables (visibles solo a >10x zoom) y mantiene compatibilidad total con el código existente.

### Por qué no incluir el dewarping (Mejora 4 de IMPROVEMENTS.md)
Esa mejora ya está en el código actual y no es lo que el usuario reporta como problema. Tocarla podría introducir regresiones. Si tras estos fixes el dewarping sigue molestando, abrir un plan separado para revisarlo o desactivarlo por defecto.

### Sobre la idempotencia de EXIF
`correct_exif_orientation` se aplica SOLO en `/api/upload`. La imagen guardada ya no tiene EXIF (OpenCV no lo escribe). Por eso re-aplicarlo no rota dos veces. El test 7 documenta esto explícitamente.
