# UnionDNIs — Escáner de Documentos de Identidad

Aplicación web local que escanea documentos de identidad (DNI, NIE, pasaporte) desde fotos de móvil y genera documentos en PDF, Word o imagen.

**Todo se procesa localmente.** Sin APIs externas. Sin cloud. Sin LLM.

## Características

- 📷 **Subida desde móvil**: Toma fotos con la cámara trasera del móvil
- 🔍 **Detección automática**: Detecta bordes del documento y corrige perspectiva
- 🎨 **Mejora de imagen**: Modo color, escáner B/N o original
- 📄 **Múltiples formatos**: Exporta a PDF, Word (.docx) o imagen PNG
- 🔍 **OCR integrado**: Extrae texto y zona MRZ (si Tesseract está instalado)
- 🔒 **100% local**: Tus datos nunca salen de tu dispositivo

## Requisitos

- **Python 3.12**
- **Windows** (para Tesseract OCR)
- **Tesseract OCR** (binario del sistema)

## Instalación

### 1. Instalar Tesseract OCR

```powershell
winget install UB-Mannheim.TesseractOCR
```

La ruta típica de instalación es: `C:\Program Files\Tesseract-OCR\tesseract.exe`

### 2. Clonar/navegar al proyecto

```powershell
cd C:\Users\Usuario\Desktop\Proyectos\UnionDNIs
```

### 3. Activar entorno virtual

```powershell
.\venv\Scripts\activate
```

### 4. Instalar dependencias

```powershell
pip install -r requirements.txt
```

## Cómo arrancar

```powershell
.\venv\Scripts\python.exe run.py
```

El servidor arrancará en:
- **Local**: http://localhost:8000
- **Red local**: http://0.0.0.0:8000

## Cómo usar desde el móvil

1. Arranca el servidor en tu PC
2. Encuentra tu IP local (ej: `192.168.1.XX`)
3. Abre en el móvil: `http://<TU_IP>:8000`
4. Sube fotos del DNI/pasaporte (frontal y trasera)
5. Genera el documento y descarga

## Formatos de salida

| Formato | Descripción |
|---------|-------------|
| **PDF** | Página A4 con ambas caras, ideal para imprimir |
| **Word** | Documento .docx editable |
| **Imagen** | PNG combinado con ambas caras |

## OCR y MRZ

Si Tesseract está instalado, la aplicación puede:
- Extraer todo el texto visible del documento
- Detectar la zona MRZ (Machine Readable Zone)
- Parsear campos: número de documento, nombre, fecha de nacimiento, caducidad, nacionalidad

## Estructura del proyecto

```
UnionDNIs/
├── app/
│   ├── __init__.py
│   ├── utils.py          # Funciones de utilidad (order_points, etc.)
│   ├── scanner.py        # Detección de documentos
│   ├── enhancer.py       # Mejora de imagen
│   ├── ocr.py            # OCR con Tesseract
│   ├── exporter.py       # Exportación a PDF/Word/Imagen
│   └── main.py           # API FastAPI
├── static/
│   ├── index.html        # Frontend
│   ├── styles.css        # Estilos dark mode
│   └── app.js            # Lógica frontend
├── uploads/              # Imágenes temporales
├── output/               # Documentos generados
├── requirements.txt
├── run.py
└── README.md
```

## Tecnologías

- **Backend**: FastAPI, OpenCV, Pillow, pytesseract
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Exportación**: ReportLab (PDF), python-docx (Word)

## Licencia

MIT
