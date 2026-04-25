# Plan de Construcción — UnionDNIs

## Contexto
Proyecto UnionDNIs: aplicación web local que escanea documentos de identidad (DNI, NIE, pasaporte) desde fotos de móvil y genera PDF/Word/PNG.

## Estado Actual (FASE 0 completada)
Archivos verificados existentes:
- `app/__init__.py` ✓
- `app/utils.py` ✓
- `app/scanner.py` ✓
- `app/enhancer.py` ✓
- `requirements.txt` ✓

Tesseract OCR instalado vía winget.

## Fases Pendientes

### FASE 1 — `app/ocr.py` (OCR con Tesseract)
- `check_tesseract_available()`
- `extract_text()`
- `extract_mrz()`
- `parse_mrz_fields()`

### FASE 2 — `app/exporter.py` (Exportación documentos)
- `_bgr_to_pil()`, `_pil_to_bytes()`
- `export_pdf()`
- `export_word()`
- `export_image()`

### FASE 3 — `app/main.py` (API FastAPI)
- Configurar app, middleware, rutas estáticas
- Endpoints: `/`, `/api/upload`, `/api/transform`, `/api/preview`, `/api/ocr`, `/api/export`, `/api/download`, `/api/session`, `/api/status`

### FASE 4 — `static/index.html` (Frontend HTML)
- Estructura HTML5 completa con 3 secciones (upload, options, export)

### FASE 5 — `static/styles.css` (Estilos dark mode premium)
- Variables CSS, glassmorphism, animaciones, responsive

### FASE 6 — `static/app.js` (Lógica frontend)
- Estado, upload, transform, corner selector, OCR, export, toasts

### FASE 7 — `run.py` (Script arranque)

### FASE 8 — `README.md`

## Verificación Final
- Crear directorios `uploads/`, `output/`, `static/`
- Ejecutar: `.\venv\Scripts\python.exe run.py`
- Acceder: `http://localhost:8000`
