# Spec: Soporte de escaneo para Permiso de Circulación

**Fecha:** 2026-07-01
**Estado:** Aprobado para implementación

## Contexto

UnionDNIs solo soporta hoy DNI/NIE/Pasaporte, con un flujo de dos caras (frontal +
trasera) pensado para tarjetas ID-1/ID-3. El usuario necesita escanear también
Permisos de Circulación (documento de vehículo, tamaño A4 o A5 según antigüedad),
de los que por ahora solo interesa **una cara principal**.

Se investigó el código existente y se confirmó la causa raíz de que el PDF actual
"no quede cuadrado" para este tipo de documento: `exporter.py::_normalize_image_size`
fuerza cualquier imagen a un lienzo fijo apaisado (1012×638 px) con relleno blanco
alrededor. Una foto de Permiso de Circulación en vertical quedaría diminuta y
rodeada de blanco.

También se confirmó que **no hace falta tocar** `scanner.py` ni el pipeline de
subida/rotación/selección manual de esquinas:
- El ratio A4/A5 (√2 ≈ 1.414) coincide con el ratio de pasaporte ya aceptado por
  `_validate_aspect_ratio`, así que la detección automática puede funcionar por
  coincidencia.
- El selector manual de esquinas (`openManualSelector` / canvas en `app.js`) ya es
  genérico: dibuja la imagen completa en un `<canvas>` vía `drawImage`, que ignora
  el `object-fit` CSS y mapea clics linealmente — funciona para cualquier aspect
  ratio sin cambios.
- El endpoint `/api/rotate` y `apply_transform`/`four_point_transform` ya son
  agnósticos al tipo de documento.

Por tanto esta spec se centra en tres cosas: (1) exponer el nuevo tipo de
documento en la UI, (2) enrutar la exportación según el tipo, y (3) generar
PDF/Word/imagen de página única que respeten la orientación real de la foto.

## Alcance

**Incluido:**
- Selector de tipo de documento en el frontend: "DNI/NIE/Pasaporte" (existente,
  por defecto) vs "Permiso de Circulación" (nuevo, una sola foto).
- Nuevas funciones de exportación de página única (PDF, Word, imagen) que
  auto-orientan la página según el aspect ratio de la foto ya corregida, sin
  forzar un lienzo fijo ni mostrar placeholders de "cara trasera".
- Pequeño arreglo de CSS: `object-fit: cover` → `contain` en la miniatura de
  preview de subida, para que una foto vertical no se vea recortada antes de
  procesar.

**Explícitamente fuera de alcance (diferido):**
- Ficha Técnica / Tarjeta ITV (documento de 2 páginas) — se abordará en una
  iteración futura.
- Mejora de extracción OCR de DNI/NIE (número, nombre, domicilio, fecha de
  nacimiento; distinción de formato NIE vs DNI) — spec separada.
- Cambios en `scanner.py` (detección automática) — no son necesarios para esta
  spec; si en pruebas manuales resulta que la detección automática falla
  sistemáticamente para estos documentos, el usuario ya cuenta con el selector
  manual de esquinas como fallback funcional.

## Diseño

### 1. Frontend — selector de tipo de documento

- Nuevo grupo de toggle (mismo patrón visual que `enhance-mode`/`output-format`)
  insertado **antes** de `step-upload`, con dos opciones: `id` (🪪 DNI / NIE /
  Pasaporte, valor por defecto) y `vehicle` (🚗 Permiso de Circulación).
- Nuevo campo `state.documentType` (por defecto `'id'`). Persiste entre llamadas
  a `resetAll()`, igual que `enhanceMode`/`outputFormat` ya persisten hoy.
- Cambiar de tipo con una sesión en curso dispara un reset completo del flujo
  (equivalente a `resetAll()`) para evitar estados híbridos.
- Con `documentType === 'vehicle'`:
  - Se oculta `card-back` por completo (el usuario nunca sube una imagen "back").
  - El texto de `card-front` cambia: label "Permiso de Circulación" (en vez de
    "Cara frontal"), hint actualizado, texto del botón "Subir foto".
  - En `step-export`, la columna "Cara Trasera" de `processed-preview` se oculta.
- El resto del flujo (subir, badge de detección, rotar, ajustar esquinas
  manualmente, elegir modo de imagen) se reutiliza sin cambios, usando siempre
  `side = 'front'` internamente.
- Fix de CSS: `.upload-preview img { object-fit: cover }` → `object-fit: contain`.

### 2. Backend — enrutado por tipo de documento

- `ExportRequest` (en `app/main.py`) gana un campo `document_type: str = "id"`
  (valores válidos: `"id"`, `"vehicle"`).
- En `/api/export`:
  - Si `document_type == "vehicle"`: requiere que exista
    `front_processed.jpg` (si no, `HTTPException(400, "Se requiere la foto del
    Permiso de Circulación")`); se ignora cualquier `back_processed.jpg`; se
    llama a las nuevas funciones de exportación de página única con
    `title="Permiso de Circulación"`.
  - Si `document_type == "id"` (o ausente): comportamiento actual sin cambios
    (usa `export_pdf`/`export_word`/`export_image` existentes).
- Prefijo del nombre de archivo de salida: `"permiso_"` para `vehicle`,
  `"dni_"` para `id` (se mantiene el sufijo `{session_id}_{timestamp}.{ext}`).
- No se modifican `/api/upload`, `/api/transform`, `/api/rotate`,
  `/api/preview`, `/api/ocr` — son agnósticos al tipo de documento.

### 3. Exportador — funciones de página única

Nuevas funciones en `app/exporter.py` (las funciones existentes para DNI no se
tocan):

- `export_pdf_single(image, output_path, title) -> str`: elige orientación de
  página A4 (portrait si `height >= width` de la imagen, landscape si no) usando
  una función pura auxiliar `_choose_page_orientation(image) -> (width, height)`
  (testeable sin generar el PDF real). Dibuja encabezado (título + fecha, mismo
  estilo que el PDF de DNI) y escala la imagen a la página completa manteniendo
  aspect ratio (contain, centrada, márgenes ~1.5cm). Sin lienzo fijo de tamaño
  estándar, sin placeholder de cara trasera.
- `export_word_single(image, output_path, title) -> str`: mismo criterio de
  orientación; si la imagen es apaisada, la sección del `.docx` se configura en
  landscape (`WD_ORIENT.LANDSCAPE`, intercambiando `page_width`/`page_height`)
  para que la imagen no quede diminuta en una página portrait.
- `export_image_single(image, output_path) -> str`: exporta la imagen procesada
  con un margen blanco de acabado (padding, mismo estilo que el PNG de DNI),
  sin normalizar a un tamaño de lienzo fijo.

Estas funciones reutilizan `_bgr_to_pil` y `_pil_to_bytes` ya existentes.
`_normalize_image_size`, `STANDARD_SIZES` y `_detect_document_type` quedan
intactos y solo los usan las funciones de exportación de DNI.

### Manejo de errores

- Todos los endpoints ya envuelven su lógica en try/except con mensajes en
  español (patrón existente) — las nuevas ramas siguen el mismo patrón.
- Si `document_type` no es `"id"` ni `"vehicle"`, se trata como `"id"` por
  compatibilidad (valor por defecto), sin lanzar error — mantiene el contrato
  actual donde el campo no es estrictamente validado por un enum.

### Testing

- Tests unitarios (pytest, infraestructura ya existente) para
  `_choose_page_orientation`: imagen apaisada → landscape, imagen vertical →
  portrait, imagen cuadrada → portrait (caso borde, `height >= width`).
- Tests de humo para `export_pdf_single`/`export_word_single`/`export_image_single`:
  generan el archivo con una imagen sintética y verifican que el archivo existe
  y no está vacío (mismo nivel de detalle que los tests existentes del proyecto,
  que no inspeccionan contenido interno de PDF/DOCX).
- Verificación manual end-to-end con las fotos de ejemplo en `docs/` (Permiso de
  Circulación real, orientaciones variadas): subir, rotar si hace falta, ajustar
  esquinas manualmente, generar PDF, confirmar visualmente que la página queda
  bien orientada y sin bordes blancos excesivos.
