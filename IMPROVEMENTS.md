# IMPROVEMENTS.md — Plan de Mejoras v1.1

> **Para:** Claude Code  
> **Contexto:** Lee primero `CLAUDE.md` (plan original v1.0). Este archivo describe las mejoras a aplicar sobre el código existente.  
> **Regla:** NO borres ni reescribas archivos enteros. Aplica cambios quirúrgicos sobre el código existente.

---

## Resumen de Mejoras

| # | Mejora | Impacto | Archivos afectados |
|---|---|---|---|
| 1 | **Rotación de imagen** pre-proceso | 🔴 Alto | `main.py`, `app.js`, `index.html`, `styles.css` |
| 2 | **Normalizar tamaño** de ambas caras en el documento | 🔴 Alto | `exporter.py` |
| 3 | **Modo grises** (entre color y B/N) | 🟡 Medio | `enhancer.py`, `index.html`, `app.js` |
| 4 | **Corrección de ondulación** del texto (dewarping suave) | 🟡 Medio | `enhancer.py` |
| 5 | **Corrección EXIF** automática al subir foto | 🟢 Bajo | `main.py` |

---

## MEJORA 1 — Rotación de imagen pre-proceso

### Problema
No existe forma de rotar la imagen antes de procesarla. Si el usuario toma la foto girada (vertical cuando debería ser horizontal, o al revés), el resultado sale mal orientado.

### Solución

#### 1.1 Backend: Nuevo endpoint `POST /api/rotate`

**Archivo:** `app/main.py` — Añadir DESPUÉS del endpoint `/api/upload` (aprox. línea 158)

```python
@app.post("/api/rotate")
async def rotate_image(
    session_id: str = Form(...),
    side: str = Form(...),       # "front" | "back"
    degrees: int = Form(...)     # 90, 180, 270 (sentido horario)
):
    """
    Rota la imagen original y re-ejecuta la detección automática.
    
    Args:
        session_id: ID de la sesión
        side: "front" o "back"
        degrees: Grados de rotación en sentido horario (90, 180, 270)
    
    Returns:
        {
            "session_id": str,
            "side": str,
            "degrees": int,
            "detection": { ... },  # Re-detección tras rotar
            "image_size": [w, h]
        }
    """
    try:
        if degrees not in [90, 180, 270]:
            raise HTTPException(status_code=400, detail="degrees debe ser 90, 180 o 270")
        
        if side not in ["front", "back"]:
            raise HTTPException(status_code=400, detail="side debe ser 'front' o 'back'")
        
        session_dir = UPLOAD_DIR / session_id
        original_path = session_dir / f"{side}_original.jpg"
        
        if not original_path.exists():
            raise HTTPException(status_code=404, detail="Imagen no encontrada")
        
        # Cargar imagen
        image = cv2.imread(str(original_path))
        if image is None:
            raise HTTPException(status_code=400, detail="Error al leer imagen")
        
        # Rotar usando cv2.rotate() — es lossless sobre la matriz numpy
        rotate_map = {
            90: cv2.ROTATE_90_CLOCKWISE,
            180: cv2.ROTATE_180,
            270: cv2.ROTATE_90_COUNTERCLOCKWISE
        }
        rotated = cv2.rotate(image, rotate_map[degrees])
        
        # Sobreescribir la imagen original con la versión rotada
        cv2.imwrite(str(original_path), rotated)
        
        # Eliminar imagen procesada anterior (si existe)
        processed_path = session_dir / f"{side}_processed.jpg"
        if processed_path.exists():
            processed_path.unlink()
        
        # Re-detectar esquinas en la imagen rotada
        detection = detect_document(rotated)
        h, w = rotated.shape[:2]
        
        return {
            "session_id": session_id,
            "side": side,
            "degrees": degrees,
            "detection": detection,
            "image_size": [w, h]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al rotar: {str(e)}")
```

#### 1.2 Frontend: Botones de rotación en la preview

**Archivo:** `static/index.html` — Dentro de `preview-actions` (tanto en `preview-front` como en `preview-back`)

Buscar este bloque (línea ~50-53 para front, ~83-86 para back):
```html
<div class="preview-actions">
    <button class="btn-sm btn-secondary" onclick="retakePhoto('front')">↩ Cambiar</button>
    <span class="detection-badge" id="detection-front"></span>
</div>
```

Reemplazar por:
```html
<div class="preview-actions">
    <div class="action-row">
        <button class="btn-sm btn-secondary" onclick="retakePhoto('front')">↩ Cambiar</button>
        <div class="rotate-controls">
            <button class="btn-icon-sm" onclick="rotateImage('front', 270)" title="Rotar izquierda">
                ↺
            </button>
            <button class="btn-icon-sm" onclick="rotateImage('front', 90)" title="Rotar derecha">
                ↻
            </button>
            <button class="btn-icon-sm" onclick="rotateImage('front', 180)" title="Girar 180°">
                🔃
            </button>
        </div>
    </div>
    <span class="detection-badge" id="detection-front"></span>
</div>
```

Hacer lo mismo para `back`, cambiando `'front'` por `'back'` en los onclick.

#### 1.3 Frontend: Función JS de rotación

**Archivo:** `static/app.js` — Añadir DESPUÉS de la función `uploadFile()` (aprox. línea 122)

```javascript
/**
 * Rotar imagen en el servidor
 */
async function rotateImage(side, degrees) {
    try {
        showToast(`Rotando ${degrees}°...`, 'info');
        
        const formData = new FormData();
        formData.append('session_id', state.sessionId);
        formData.append('side', side);
        formData.append('degrees', degrees);
        
        const response = await fetch('/api/rotate', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al rotar');
        }
        
        const data = await response.json();
        
        // Actualizar preview con imagen rotada (cache bust con timestamp)
        const imgElement = document.getElementById(`img-${side}`);
        imgElement.src = `/api/preview/${state.sessionId}/${side}?original=1&t=${Date.now()}`;
        
        // Actualizar detección
        state[side].corners = data.detection.corners;
        state[side].processed = false;
        updateDetectionBadge(side, data.detection);
        
        // Si la detección es buena, re-aplicar transform automáticamente
        if (data.detection.confidence >= 0.5) {
            await applyTransform(side, data.detection.corners);
            showToast('Imagen rotada y procesada ✓', 'success');
        } else {
            showToast('Imagen rotada — selecciona esquinas manualmente', 'warning');
            initCornerSelector(side);
        }
        
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    }
}
```

#### 1.4 Backend: endpoint para servir imagen original (para preview post-rotación)

**Archivo:** `app/main.py` — Modificar el endpoint `GET /api/preview/{session_id}/{side}` (línea 224)

Añadir soporte para query param `original`:

```python
from fastapi import Query

@app.get("/api/preview/{session_id}/{side}")
async def get_preview(session_id: str, side: str, original: Optional[int] = Query(None)):
    """Devuelve la imagen procesada o la original como JPEG para preview."""
    try:
        session_dir = UPLOAD_DIR / session_id
        
        # Si se pide explícitamente la original
        if original:
            original_path = session_dir / f"{side}_original.jpg"
            if original_path.exists():
                return FileResponse(str(original_path), media_type="image/jpeg")
        
        processed_path = session_dir / f"{side}_processed.jpg"

        # Si no existe procesada, devolver original
        if not processed_path.exists():
            original_path = session_dir / f"{side}_original.jpg"
            if original_path.exists():
                return FileResponse(str(original_path), media_type="image/jpeg")
            raise HTTPException(status_code=404, detail="Imagen no encontrada")

        return FileResponse(str(processed_path), media_type="image/jpeg")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 1.5 CSS: Estilos para botones de rotación

**Archivo:** `static/styles.css` — Añadir al final o junto a los estilos de `.preview-actions`

```css
/* --- Controles de rotación --- */
.action-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    gap: 8px;
}

.rotate-controls {
    display: flex;
    gap: 4px;
}

.btn-icon-sm {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255,255,255,0.1);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-size: 1.1rem;
    cursor: pointer;
    transition: var(--transition-fast);
}

.btn-icon-sm:hover {
    background: rgba(99,102,241,0.3);
    border-color: var(--accent-primary);
    transform: scale(1.1);
}

.btn-icon-sm:active {
    transform: scale(0.95);
}
```

---

## MEJORA 2 — Normalizar tamaño de ambas caras en el documento de salida

### Problema
Actualmente cada imagen se escala independientemente para encajar en su espacio disponible. Si la cara frontal se tomó desde más lejos y la trasera más de cerca, salen con tamaños diferentes en el PDF/Word/imagen. Esto se ve descuidado.

### Solución: Normalizar a dimensiones estándar de DNI

Un DNI/tarjeta ISO ID-1 mide **85.6 × 53.98 mm** (ratio 1.586:1).
Un pasaporte ISO ID-3 mide **125 × 88 mm** (ratio 1.42:1).

#### 2.1 Nueva función en `app/exporter.py`

**Añadir al principio del archivo, después de los imports (aprox. línea 22):**

```python
# Dimensiones estándar de documentos (en píxeles a 300 DPI)
# DNI/ID Card: 85.6 × 53.98 mm → a 300 DPI = 1012 × 638 px
# Pasaporte: 125 × 88 mm → a 300 DPI = 1476 × 1039 px
STANDARD_SIZES = {
    "id_card": (1012, 638),   # width, height
    "passport": (1476, 1039),
}
DEFAULT_SIZE = (1012, 638)  # DNI como default


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
    
    # Calcular escala manteniendo aspect ratio
    scale = min(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Redimensionar con INTER_LANCZOS4 para máxima calidad
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    
    # Crear canvas blanco del tamaño objetivo
    canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)
    
    # Centrar la imagen en el canvas
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
    return "id_card"  # default
```

#### 2.2 Modificar `export_pdf()` en `app/exporter.py`

**Antes de dibujar las imágenes** (justo después de calcular `image_height` en línea ~117), añadir la normalización:

Buscar el bloque (aprox. líneas 112-117):
```python
    # --- Área para imágenes ---
    # Calcular espacio disponible: ...
    margin_x = 30
    available_width = width - (2 * margin_x)
    image_height = 336
```

Reemplazar por:
```python
    # --- Normalizar ambas imágenes al mismo tamaño ---
    doc_type = _detect_document_type(front_image, back_image)
    target_size = STANDARD_SIZES.get(doc_type, DEFAULT_SIZE)
    front_image = _normalize_image_size(front_image, target_size)
    back_image = _normalize_image_size(back_image, target_size)
    
    # --- Área para imágenes ---
    margin_x = 30
    available_width = width - (2 * margin_x)
    image_height = 336
```

#### 2.3 Modificar `export_word()` en `app/exporter.py`

**Antes de añadir las imágenes al documento Word** (justo antes del bloque `# Imagen frontal`, aprox. línea 225):

Añadir:
```python
    # Normalizar ambas imágenes al mismo tamaño
    doc_type = _detect_document_type(front_image, back_image)
    target_size = STANDARD_SIZES.get(doc_type, DEFAULT_SIZE)
    front_image = _normalize_image_size(front_image, target_size)
    back_image = _normalize_image_size(back_image, target_size)
```

#### 2.4 Modificar `export_image()` en `app/exporter.py`

**Reemplazar completamente** la función `export_image` (líneas 258-315):

```python
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
    bg_color = 240  # Gris claro

    if front_image is None and back_image is None:
        raise ValueError("Al menos una imagen debe ser proporcionada")

    # Normalizar ambas imágenes al mismo tamaño
    doc_type = _detect_document_type(front_image, back_image)
    target_size = STANDARD_SIZES.get(doc_type, DEFAULT_SIZE)
    front_norm = _normalize_image_size(front_image, target_size)
    back_norm = _normalize_image_size(back_image, target_size)

    # Determinar dimensiones del canvas final
    target_w, target_h = target_size
    images = [img for img in [front_norm, back_norm] if img is not None]
    
    if len(images) == 2:
        total_height = target_h * 2 + padding
    else:
        total_height = target_h
    
    # Crear canvas
    canvas = np.full((total_height, target_w, 3), bg_color, dtype=np.uint8)
    
    y_offset = 0
    if front_norm is not None:
        canvas[0:target_h, 0:target_w] = front_norm
        y_offset = target_h + padding
    
    if back_norm is not None:
        canvas[y_offset:y_offset + target_h, 0:target_w] = back_norm

    cv2.imwrite(output_path, canvas)
    return output_path
```

---

## MEJORA 3 — Modo grises (entre color y B/N)

### Problema
El enhancer solo tiene 3 modos: `color`, `bw` (blanco/negro puro con umbralización), `original`. El usuario quiere un modo intermedio de **escala de grises** que mantenga los tonos pero sin color — como una fotocopia de calidad.

### Solución

#### 3.1 Añadir modo "grayscale" en `app/enhancer.py`

**Modificar la función `enhance_scan()`** (línea 15-31):

```python
def enhance_scan(image, mode="color"):
    """
    Mejora la imagen del documento escaneado.
    
    Args:
        image: Imagen BGR (numpy array)
        mode: "color" | "grayscale" | "bw" | "original"
        
    Returns:
        Imagen mejorada (numpy array BGR)
    """
    if mode == "original":
        return image
    elif mode == "bw":
        return _enhance_bw(image)
    elif mode == "grayscale":
        return _enhance_grayscale(image)
    else:
        return _enhance_color(image)
```

**Añadir la función `_enhance_grayscale()`** después de `_enhance_color()` (aprox. línea 57):

```python
def _enhance_grayscale(image):
    """
    Modo grises: convierte a escala de grises con CLAHE y nitidez mejorada.
    Produce un resultado similar a una fotocopia de calidad.
    Mantiene tonos medios (no es binario como B/N).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # CLAHE para mejorar contraste local
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Nitidez
    blurred = cv2.GaussianBlur(enhanced, (0, 0), 1)
    sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0)
    
    # Normalizar rango para maximizar contraste
    sharpened = cv2.normalize(sharpened, None, 0, 255, cv2.NORM_MINMAX)
    
    # Convertir de vuelta a BGR para mantener compatibilidad
    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
```

#### 3.2 Añadir botón en el HTML

**Archivo:** `static/index.html` — En el toggle-group de "Modo de imagen" (línea ~114-118)

Buscar:
```html
<div class="toggle-group" id="enhance-mode">
    <button class="toggle-btn active" data-value="color">🎨 Color</button>
    <button class="toggle-btn" data-value="bw">⬛ Escáner</button>
    <button class="toggle-btn" data-value="original">📷 Original</button>
</div>
```

Reemplazar por:
```html
<div class="toggle-group" id="enhance-mode">
    <button class="toggle-btn active" data-value="color">🎨 Color</button>
    <button class="toggle-btn" data-value="grayscale">🩶 Grises</button>
    <button class="toggle-btn" data-value="bw">⬛ Escáner</button>
    <button class="toggle-btn" data-value="original">📷 Original</button>
</div>
```

El JS ya maneja dinámicamente cualquier valor de `data-value`, así que no necesita cambios.

#### 3.3 Backend: El endpoint `/api/transform` ya acepta `enhance_mode` como string libre

Verificar que `TransformRequest.enhance_mode` acepte "grayscale". El modelo Pydantic actual ya lo permite porque es un `str`, no un `Literal`. ✅ Sin cambios necesarios.

---

## MEJORA 4 — Corrección de ondulación del texto (dewarping suave)

### Problema
Cuando se fotografía un DNI o tarjeta plástica que está ligeramente curvada (lo cual es muy común con tarjetas de plástico), la corrección de perspectiva 2D (warpPerspective) no puede compensar la curvatura 3D de la superficie. El resultado es que el texto aparece ondulado — como si estuviera escrito sobre olas.

### Diagnóstico técnico
```
                     Realidad 3D:
              ╱────────╲                    La tarjeta tiene una 
           ╱──────────────╲                curva convexa. La perspectiva
          ╱────────────────╲               la aplana pero NO endereza
         ╱──────────────────╲              las líneas de texto.
```

### Solución: Dewarping suave con detección de líneas

No vamos a implementar deep learning (sería excesivo para este caso). En su lugar, aplicaremos una técnica de **dewarping basada en detección de líneas horizontales** usando Hough Transform, combinada con un **filtro bilateral** para suavizar sin perder bordes.

#### 4.1 Añadir función de dewarping en `app/enhancer.py`

**Añadir al final del archivo:**

```python
def _correct_waviness(image):
    """
    Intenta corregir la ondulación sutil del texto causada por curvatura
    de tarjetas plásticas.
    
    Usa un enfoque en dos pasos:
    1. Filtro bilateral para suavizar irregularidades sin perder bordes de texto
    2. Corrección geométrica suave basada en detección de líneas
    
    Esta corrección es conservadora: si no detecta ondulación significativa,
    devuelve la imagen sin cambios para no degradar la calidad.
    """
    h, w = image.shape[:2]
    
    # Paso 1: Filtro bilateral — suaviza "noise" de curvatura pero preserva bordes
    # d=9: diámetro del vecindario, sigmaColor=75: filtro en color, sigmaSpace=75: filtro en espacio
    smoothed = cv2.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)
    
    # Paso 2: Detectar líneas horizontales para estimar curvatura
    gray = cv2.cvtColor(smoothed, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    # Buscar líneas horizontales con Hough
    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi/180, threshold=80,
        minLineLength=w * 0.3,   # Líneas de al menos 30% del ancho
        maxLineGap=10
    )
    
    if lines is None or len(lines) < 3:
        # No hay suficientes líneas para estimar curvatura
        return smoothed
    
    # Analizar la inclinación de las líneas detectadas
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(x2 - x1) > 0:
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
            if abs(angle) < 10:  # Solo líneas casi horizontales
                angles.append(angle)
    
    if len(angles) < 2:
        return smoothed
    
    # Si la variación de ángulos es significativa, hay ondulación
    angle_std = np.std(angles)
    
    if angle_std < 0.5:
        # Curvatura insignificante, no aplicar corrección adicional
        return smoothed
    
    # Corrección: aplicar rotación media para alinear + suavizado extra
    mean_angle = np.mean(angles)
    if abs(mean_angle) > 0.1:
        # Rotar ligeramente para alinear texto con horizontal
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, mean_angle, 1.0)
        corrected = cv2.warpAffine(smoothed, M, (w, h),
                                    borderMode=cv2.BORDER_REPLICATE)
        return corrected
    
    return smoothed
```

#### 4.2 Integrar el dewarping en los modos de mejora

**Modificar `_enhance_color()` y `_enhance_grayscale()`** para aplicar `_correct_waviness()` como primer paso.

En `_enhance_color()` (línea 34), añadir como primera línea del cuerpo:
```python
def _enhance_color(image):
    """..."""
    # Corregir ondulación sutil de tarjetas plásticas
    image = _correct_waviness(image)
    
    # El resto del código existente sigue igual...
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    # ...
```

En `_enhance_grayscale()` (la función nueva de la Mejora 3), añadir como primera línea:
```python
def _enhance_grayscale(image):
    """..."""
    # Corregir ondulación sutil
    image = _correct_waviness(image)
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # ...
```

**NO aplicar** en `_enhance_bw()` — el modo B/N ya aplica umbralización agresiva que minimiza la ondulación visualmente.

**NO aplicar** en modo `original` — el usuario quiere la imagen sin alteraciones.

---

## MEJORA 5 — Corrección automática de orientación EXIF

### Problema
Las fotos tomadas con móvil suelen tener metadatos EXIF que indican la rotación, pero la imagen raw se guarda siempre en la misma orientación. OpenCV ignora estos metadatos, así que la imagen puede aparecer girada 90° al cargarla.

### Solución

#### 5.1 Añadir función de corrección EXIF en `app/utils.py`

**Añadir al final de `app/utils.py`:**

```python
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
    # Primero intentar con PIL para leer EXIF
    try:
        pil_image = PILImage.open(io.BytesIO(image_bytes))
        
        # Buscar la etiqueta de orientación EXIF
        exif = pil_image.getexif()
        orientation_tag = None
        
        for tag_id, tag_name in ExifTags.TAGS.items():
            if tag_name == 'Orientation':
                orientation_tag = tag_id
                break
        
        if orientation_tag and orientation_tag in exif:
            orientation = exif[orientation_tag]
            
            # Aplicar transformación según orientación EXIF
            # https://www.impulseadventure.com/photo/exif-orientation.html
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
        
        # Convertir PIL → OpenCV BGR
        rgb_array = np.array(pil_image)
        if len(rgb_array.shape) == 2:
            # Imagen en grises
            return cv2.cvtColor(rgb_array, cv2.COLOR_GRAY2BGR)
        elif rgb_array.shape[2] == 4:
            # Imagen con alpha (RGBA)
            return cv2.cvtColor(rgb_array, cv2.COLOR_RGBA2BGR)
        else:
            return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    
    except Exception:
        # Fallback: decodificar con OpenCV directamente (sin corrección EXIF)
        return cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
```

#### 5.2 Usar `correct_exif_orientation()` en el endpoint `/api/upload`

**Archivo:** `app/main.py` — En el endpoint `upload_image()` (aprox. línea 130-133)

Buscar:
```python
        # Leer y guardar imagen
        file_bytes = await file.read()
        image = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
```

Reemplazar por:
```python
        # Leer y guardar imagen (con corrección de orientación EXIF)
        file_bytes = await file.read()
        
        from .utils import correct_exif_orientation
        image = correct_exif_orientation(file_bytes)
```

También añadir el import al principio del archivo:
```python
from .utils import correct_exif_orientation
```

---

## Resumen de cambios por archivo

| Archivo | Modificaciones |
|---|---|
| `app/main.py` | + endpoint `/api/rotate`, + query param `original` en `/api/preview`, + import y uso de `correct_exif_orientation` en `/api/upload` |
| `app/enhancer.py` | + función `_enhance_grayscale()`, + función `_correct_waviness()`, + llamada a `_correct_waviness` en `_enhance_color` y `_enhance_grayscale`, + modo "grayscale" en `enhance_scan()` |
| `app/exporter.py` | + constantes `STANDARD_SIZES` y `DEFAULT_SIZE`, + funciones `_normalize_image_size()` y `_detect_document_type()`, + normalización en `export_pdf`, `export_word`, `export_image` |
| `app/utils.py` | + función `correct_exif_orientation()` |
| `static/index.html` | + botones de rotación (↺ ↻ 🔃) en ambas previews, + botón "🩶 Grises" en el toggle de modos |
| `static/styles.css` | + estilos para `.action-row`, `.rotate-controls`, `.btn-icon-sm` |
| `static/app.js` | + función `rotateImage()` |

---

## Orden de implementación recomendado

1. **Mejora 5** (EXIF) — Es prerequisito, invisible, previene rotaciones fantasma
2. **Mejora 1** (Rotación) — La más pedida por el usuario
3. **Mejora 3** (Grises) — Fácil y rápida
4. **Mejora 2** (Normalizar tamaño) — Mejora visual del documento final
5. **Mejora 4** (Dewarping) — La más compleja, la menos predecible

---

## Comando para Claude Code

```
Lee el archivo IMPROVEMENTS.md en el directorio del proyecto.
Aplica las 5 mejoras en el orden indicado en "Orden de implementación recomendado".
NO reescribas archivos enteros — modifica quirúrgicamente solo las secciones indicadas.
Verifica con: .\venv\Scripts\python.exe run.py
```

---

## Notas técnicas para Claude Code

### Sobre el dewarping (Mejora 4)
- Esta corrección es **conservadora**: si no detecta curvatura significativa (angle_std < 0.5), no toca la imagen
- Es mucho mejor ser conservador que agresivo — una corrección mal aplicada empeora el resultado
- Si en testing produce artefactos, reducir el `sigmaColor` del filtro bilateral de 75 a 50

### Sobre la normalización (Mejora 2)
- Usar `cv2.INTER_LANCZOS4` para redimensionar: es el algoritmo de mayor calidad de OpenCV
- El fondo blanco de relleno (cuando el aspect ratio no coincide exactamente) es intencional: simula el borde de una fotocopia real

### Sobre EXIF (Mejora 5)
- Usar Pillow para leer EXIF, no OpenCV — OpenCV no tiene soporte fiable de EXIF
- La corrección se aplica ANTES de guardar la imagen original, así todas las operaciones posteriores ya trabajan con la orientación correcta
