"""
API FastAPI para UnionDNIs - Escáner local de documentos de identidad.

Servidores endpoints para:
- Subida de imágenes (frontal/trasera)
- Detección automática de esquinas y corrección de perspectiva
- OCR y extracción de MRZ
- Exportación a PDF, Word o imagen
"""

import os
import uuid
import json
import shutil
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .scanner import detect_document, apply_transform
from .enhancer import enhance_scan
from .ocr import extract_text, extract_mrz, parse_mrz_fields, check_tesseract_available
from .exporter import export_pdf, export_word, export_image
from .utils import correct_exif_orientation


# =============================================
# Configuración de la App
# =============================================

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

# Parámetros JPEG de máxima calidad para imágenes intermedias
# (evita acumulación de artefactos al rotar/transformar varias veces)
JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 100]

# Montar archivos estáticos (frontend)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass  # El directorio static puede no existir aún


# =============================================
# Modelos Pydantic
# =============================================

class TransformRequest(BaseModel):
    session_id: str          # ID único de la sesión
    side: str                # "front" | "back"
    corners: Optional[list]  # [[x,y],[x,y],[x,y],[x,y]] o None para auto
    enhance_mode: str = "color"  # "color" | "bw" | "original"


class ExportRequest(BaseModel):
    session_id: str
    format: str = "pdf"      # "pdf" | "word" | "image"
    include_ocr: bool = True


# =============================================
# Endpoints
# =============================================

@app.get("/")
async def root():
    """Sirve el frontend HTML."""
    index_path = Path("static/index.html")
    if not index_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "Frontend no disponible. Ejecuta desde el directorio del proyecto."}
        )
    return FileResponse(str(index_path))


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
    try:
        # Validar side
        if side not in ["front", "back"]:
            raise HTTPException(status_code=400, detail="side debe ser 'front' o 'back'")

        # Generar o usar session_id existente
        if not session_id:
            session_id = str(uuid.uuid4())[:8]

        # Crear directorio de sesión
        session_dir = UPLOAD_DIR / session_id
        session_dir.mkdir(exist_ok=True, parents=True)

        # Leer y guardar imagen (con corrección de orientación EXIF)
        file_bytes = await file.read()
        image = correct_exif_orientation(file_bytes)

        if image is None:
            raise HTTPException(status_code=400, detail="Archivo de imagen inválido")

        # Guardar imagen original
        filename = f"{side}_original.jpg"
        filepath = session_dir / filename
        cv2.imwrite(str(filepath), image, JPEG_PARAMS)

        # Detectar documento automáticamente
        detection = detect_document(image)
        h, w = image.shape[:2]

        return {
            "session_id": session_id,
            "side": side,
            "filename": filename,
            "detection": detection,
            "image_size": [w, h]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar imagen: {str(e)}")


@app.post("/api/rotate")
async def rotate_image(
    session_id: str = Form(...),
    side: str = Form(...),
    degrees: int = Form(...)
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
            "detection": { ... },
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

        image = cv2.imread(str(original_path))
        if image is None:
            raise HTTPException(status_code=400, detail="Error al leer imagen")

        rotate_map = {
            90: cv2.ROTATE_90_CLOCKWISE,
            180: cv2.ROTATE_180,
            270: cv2.ROTATE_90_COUNTERCLOCKWISE
        }
        rotated = cv2.rotate(image, rotate_map[degrees])

        cv2.imwrite(str(original_path), rotated, JPEG_PARAMS)

        processed_path = session_dir / f"{side}_processed.jpg"
        if processed_path.exists():
            processed_path.unlink()

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
            "preview_url": str
        }
    """
    try:
        session_dir = UPLOAD_DIR / request.session_id
        original_path = session_dir / f"{request.side}_original.jpg"

        if not original_path.exists():
            raise HTTPException(status_code=404, detail="Imagen original no encontrada")

        # Cargar imagen
        image = cv2.imread(str(original_path))
        if image is None:
            raise HTTPException(status_code=400, detail="Error al leer imagen")

        # Determinar esquinas
        corners = request.corners
        if corners is None:
            # Detección automática
            detection = detect_document(image)
            if detection["corners"] is None:
                raise HTTPException(
                    status_code=400,
                    detail="No se pudo detectar el documento automáticamente. Por favor selecciona las esquinas manualmente."
                )
            corners = detection["corners"]

        # Aplicar transformación de perspectiva
        transformed = apply_transform(image, corners)

        # Aplicar mejora de imagen
        enhanced = enhance_scan(transformed, request.enhance_mode)

        # Guardar imagen procesada
        processed_path = session_dir / f"{request.side}_processed.jpg"
        cv2.imwrite(str(processed_path), enhanced, JPEG_PARAMS)

        return {
            "session_id": request.session_id,
            "side": request.side,
            "processed_path": str(processed_path),
            "preview_url": f"/api/preview/{request.session_id}/{request.side}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar imagen: {str(e)}")


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


@app.post("/api/ocr")
async def run_ocr(
    session_id: str = Form(...),
    side: str = Form(...)
):
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
    try:
        available = check_tesseract_available()

        if not available:
            return {
                "available": False,
                "text": "",
                "mrz": {}
            }

        session_dir = UPLOAD_DIR / session_id
        processed_path = session_dir / f"{side}_processed.jpg"

        if not processed_path.exists():
            raise HTTPException(status_code=404, detail="Imagen procesada no encontrada")

        # Cargar imagen
        image = cv2.imread(str(processed_path))
        if image is None:
            raise HTTPException(status_code=400, detail="Error al leer imagen")

        # Extraer texto y MRZ
        text = extract_text(image)
        mrz = extract_mrz(image)
        fields = parse_mrz_fields(mrz)

        return {
            "available": True,
            "text": text,
            "mrz": {
                "detected": mrz.get("detected", False),
                "raw": mrz.get("raw", ""),
                "lines": mrz.get("lines", []),
                "type": mrz.get("type", "unknown"),
                "fields": fields
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en OCR: {str(e)}")


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


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Descarga el documento generado."""
    try:
        file_path = OUTPUT_DIR / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado")

        # Detectar content_type según extensión
        ext = filename.split(".")[-1].lower()
        content_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "png": "image/png"
        }
        media_type = content_types.get(ext, "application/octet-stream")

        return FileResponse(
            str(file_path),
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}")
async def cleanup_session(session_id: str):
    """Elimina los archivos temporales de la sesión."""
    try:
        session_dir = UPLOAD_DIR / session_id
        shutil.rmtree(str(session_dir), ignore_errors=True)

        return {"deleted": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al limpiar: {str(e)}")


@app.get("/api/status")
async def status():
    """Healthcheck + info del sistema."""
    return {
        "status": "ok",
        "tesseract": check_tesseract_available(),
        "version": "1.0.0"
    }
