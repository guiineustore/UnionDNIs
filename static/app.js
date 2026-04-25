/* ============================================
   UnionDNIs — Lógica Frontend (Vanilla JS)
   ============================================ */

/**
 * Estado de la aplicación
 */
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

/**
 * Inicializar la aplicación
 */
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

/**
 * Manejar selección de archivo
 */
async function handleFileSelect(side, file) {
    try {
        // Validar que es imagen
        if (!file.type.startsWith('image/')) {
            showToast('Por favor selecciona un archivo de imagen', 'error');
            return;
        }

        // Validar tamaño (< 20MB)
        if (file.size > 20 * 1024 * 1024) {
            showToast('La imagen no puede superar 20MB', 'error');
            return;
        }

        // Mostrar preview local inmediato
        const previewUrl = URL.createObjectURL(file);
        const imgElement = document.getElementById(`img-${side}`);
        imgElement.src = previewUrl;

        // Ocultar placeholder, mostrar preview
        document.getElementById(`placeholder-${side}`).hidden = true;
        document.getElementById(`preview-${side}`).hidden = false;

        // Subir al servidor
        showToast('Subiendo imagen...', 'info');

        const response = await uploadFile(side, file);

        // Actualizar estado
        state.sessionId = response.session_id;
        state[side].uploaded = true;
        state[side].corners = response.detection.corners;

        // Mostrar badge de detección
        updateDetectionBadge(side, response.detection);

        // Si confianza baja, mostrar selector de esquinas
        if (response.detection.confidence < 0.5) {
            showToast('Baja confianza — selecciona las esquinas manualmente', 'warning');
            initCornerSelector(side);
        } else {
            // Aplicar transform automáticamente
            await applyTransform(side, response.detection.corners);
        }

        // Mostrar sección de opciones
        checkShowOptionsSection();

    } catch (err) {
        console.error('Error:', err);
        showToast(`Error: ${err.message}`, 'error');
    }
}

/**
 * Subir archivo al servidor
 */
async function uploadFile(side, file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('side', side);
    if (state.sessionId) {
        formData.append('session_id', state.sessionId);
    }

    const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Error al subir imagen');
    }

    return response.json();
}

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

        const imgElement = document.getElementById(`img-${side}`);
        imgElement.src = `/api/preview/${state.sessionId}/${side}?original=1&t=${Date.now()}`;

        state[side].corners = data.detection.corners;
        state[side].processed = false;
        updateDetectionBadge(side, data.detection);

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

/**
 * Actualizar badge de detección
 */
function updateDetectionBadge(side, detection) {
    const badge = document.getElementById(`detection-${side}`);

    if (detection.corners === null) {
        badge.textContent = '✗ No detectado — selección manual';
        badge.className = 'detection-badge error';
    } else if (detection.confidence < 0.3) {
        badge.textContent = '✗ Baja confianza — manual';
        badge.className = 'detection-badge error';
    } else if (detection.confidence < 0.6) {
        badge.textContent = '⚠ Detectado (baja confianza)';
        badge.className = 'detection-badge warning';
    } else {
        badge.textContent = '✓ Detectado automáticamente';
        badge.className = 'detection-badge success';
    }
}

/**
 * Aplicar transformación de perspectiva
 */
async function applyTransform(side, corners = null) {
    const body = {
        session_id: state.sessionId,
        side: side,
        corners: corners,
        enhance_mode: state.enhanceMode
    };

    const response = await fetch('/api/transform', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Error al procesar imagen');
    }

    const data = await response.json();

    // Actualizar preview procesado
    const img = document.getElementById(`processed-${side}`);
    if (img) {
        img.src = `/api/preview/${state.sessionId}/${side}?t=${Date.now()}`;
    }

    state[side].processed = true;
    checkShowExportSection();
}

/**
 * Inicializar selector de esquinas
 */
function initCornerSelector(side) {
    const canvas = document.getElementById(`canvas-${side}`);
    const img = document.getElementById(`img-${side}`);

    // Asegurar que la imagen tenga dimensiones válidas
    if (!img.naturalWidth) {
        console.error('Imagen no cargada para', side);
        return;
    }

    // Ajustar canvas al tamaño de la imagen
    canvas.width = img.offsetWidth || img.naturalWidth;
    canvas.height = img.offsetHeight || img.naturalHeight;

    // Dibujar imagen en el canvas como fondo
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    state.manualCorners[side] = [];
    document.getElementById(`corner-selector-${side}`).hidden = false;

    canvas.onclick = (e) => {
        if (state.manualCorners[side].length >= 4) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = img.naturalWidth / rect.width;
        const scaleY = img.naturalHeight / rect.height;

        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        state.manualCorners[side].push([Math.round(x), Math.round(y)]);
        drawCorners(side);

        if (state.manualCorners[side].length === 4) {
            document.getElementById(`btn-apply-${side}`).disabled = false;
        }
    };
}

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

    // Mostrar selector de esquinas (sin ocultar el preview)
    const cornerSelector = document.getElementById(`corner-selector-${side}`);
    cornerSelector.hidden = false;

    // Cargar la imagen original en el elemento img
    const imgElement = document.getElementById(`img-${side}`);
    const newSrc = `/api/preview/${state.sessionId}/${side}?original=1&t=${Date.now()}`;

    // Resetear esquinas manuales
    state.manualCorners[side] = [];
    state[side].processed = false;
    state[side].corners = null;

    // Esperar a que la imagen cargue para inicializar canvas
    const initCanvas = () => {
        // Pequeño delay para asegurar que el DOM esté listo
        setTimeout(() => {
            initCornerSelector(side);
            showToast('Selecciona las 4 esquinas en orden: TL → TR → BR → BL', 'info');
        }, 50);
    };

    // Forzar recarga de imagen
    imgElement.src = newSrc;

    if (imgElement.complete && imgElement.naturalWidth) {
        // Imagen ya está cargada
        initCanvas();
    } else {
        imgElement.onload = initCanvas;
    }
}

/**
 * Dibujar esquinas seleccionadas
 */
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

/**
 * Aplicar esquinas manuales
 */
function applyManualCorners(side) {
    const corners = state.manualCorners[side];
    if (corners.length !== 4) {
        showToast('Selecciona exactamente 4 esquinas', 'error');
        return;
    }
    document.getElementById(`corner-selector-${side}`).hidden = true;
    applyTransform(side, corners);
}

/**
 * Resetear esquinas
 */
function resetCorners(side) {
    state.manualCorners[side] = [];
    const canvas = document.getElementById(`canvas-${side}`);
    const img = document.getElementById(`img-${side}`);
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    document.getElementById(`btn-apply-${side}`).disabled = true;
}

/**
 * Cambiar foto
 */
function retakePhoto(side) {
    state[side] = { uploaded: false, corners: null, processed: false };
    state.manualCorners[side] = [];

    document.getElementById(`placeholder-${side}`).hidden = false;
    document.getElementById(`preview-${side}`).hidden = true;
    document.getElementById(`corner-selector-${side}`).hidden = true;
    document.getElementById(`input-${side}`).value = '';

    // Resetear badge
    const badge = document.getElementById(`detection-${side}`);
    badge.textContent = '';
    badge.className = 'detection-badge';
}

/**
 * Mostrar sección de opciones
 */
function checkShowOptionsSection() {
    const optionsSection = document.getElementById('step-options');
    if (state.front.uploaded || state.back.uploaded) {
        optionsSection.hidden = false;
        setTimeout(() => optionsSection.classList.add('visible'), 100);
    }
}

/**
 * Mostrar sección de export
 */
function checkShowExportSection() {
    const exportSection = document.getElementById('step-export');
    if (state.front.processed || state.back.processed) {
        exportSection.hidden = false;
        setTimeout(() => exportSection.classList.add('visible'), 100);

        // Actualizar previews procesados
        if (state.front.processed) {
            document.getElementById('processed-front').src =
                `/api/preview/${state.sessionId}/front?t=${Date.now()}`;
        }
        if (state.back.processed) {
            document.getElementById('processed-back').src =
                `/api/preview/${state.sessionId}/back?t=${Date.now()}`;
        }

        document.getElementById('processed-preview').hidden = false;
    }
}

/**
 * Generar documento
 */
async function generateDocument() {
    showProgress(true);
    updateProgress(10, 'Verificando imágenes...');

    try {
        // Paso 1: OCR (si está habilitado)
        if (state.includeOcr) {
            updateProgress(30, 'Extrayendo texto...');

            if (state.front.processed) {
                state.ocrResults.front = await runOcr('front');
            }
            if (state.back.processed) {
                state.ocrResults.back = await runOcr('back');
            }

            displayOcrResults();
            document.getElementById('ocr-section').hidden = false;
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

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al generar documento');
        }

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

/**
 * Ejecutar OCR
 */
async function runOcr(side) {
    const formData = new FormData();
    formData.append('session_id', state.sessionId);
    formData.append('side', side);

    const response = await fetch('/api/ocr', {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        return null;
    }

    return response.json();
}

/**
 * Mostrar resultados OCR
 */
function displayOcrResults() {
    const fieldsTable = document.getElementById('ocr-fields-table');
    const mrzRaw = document.getElementById('mrz-raw-text');
    const fullText = document.getElementById('ocr-full-text');

    // Combinar resultados de ambas caras
    let allFields = {};
    let allMrzLines = [];
    let allText = [];

    ['front', 'back'].forEach(side => {
        const result = state.ocrResults[side];
        if (result) {
            if (result.mrz?.fields) {
                allFields = { ...allFields, ...result.mrz.fields };
            }
            if (result.mrz?.lines) {
                allMrzLines.push(...result.mrz.lines);
            }
            if (result.text) {
                allText.push(`=== Cara ${side === 'front' ? 'Frontal' : 'Trasera'} ===\n${result.text}`);
            }
        }
    });

    // Llenar tabla de campos
    fieldsTable.innerHTML = '';
    const fieldLabels = {
        document_number: 'Número de documento',
        surname: 'Apellidos',
        given_names: 'Nombre(s)',
        birth_date: 'Fecha de nacimiento',
        expiry_date: 'Fecha de caducidad',
        nationality: 'Nacionalidad',
        sex: 'Sexo',
        issuing_country: 'País emisor',
        personal_number: 'Número personal'
    };

    for (const [key, value] of Object.entries(allFields)) {
        if (value) {
            const row = fieldsTable.insertRow();
            row.innerHTML = `
                <th>${fieldLabels[key] || key}</th>
                <td>${value}</td>
            `;
        }
    }

    if (fieldsTable.rows.length === 0) {
        fieldsTable.innerHTML = '<tr><td colspan="2">No se detectaron campos MRZ</td></tr>';
    }

    // MRZ raw
    mrzRaw.textContent = allMrzLines.join('\n') || 'No se detectó MRZ';

    // Texto completo
    fullText.textContent = allText.join('\n\n') || 'No se extrajo texto';
}

/**
 * Mostrar/ocultar progreso
 */
function showProgress(show) {
    document.getElementById('progress-area').hidden = !show;
    document.getElementById('btn-generate').hidden = show;
}

/**
 * Actualizar barra de progreso
 */
function updateProgress(percent, text) {
    document.getElementById('progress-fill').style.width = `${percent}%`;
    document.getElementById('progress-text').textContent = text;
}

/**
 * Mostrar resultado final
 */
function showResult(filename, downloadUrl) {
    document.getElementById('result-filename').textContent = filename;
    document.getElementById('btn-download').href = downloadUrl;
    document.getElementById('result-area').hidden = false;
    document.getElementById('result-area').classList.add('visible');
}

/**
 * Resetear todo
 */
async function resetAll() {
    // Limpiar sesión en servidor
    if (state.sessionId) {
        try {
            await fetch(`/api/session/${state.sessionId}`, { method: 'DELETE' });
        } catch (err) {
            console.error('Error al limpiar sesión:', err);
        }
    }

    // Resetear estado
    state.sessionId = null;
    state.front = { uploaded: false, corners: null, processed: false };
    state.back = { uploaded: false, corners: null, processed: false };
    state.manualCorners = { front: [], back: [] };
    state.ocrResults = { front: null, back: null };

    // Resetear UI
    document.getElementById('step-export').hidden = true;
    document.getElementById('step-options').hidden = true;
    document.getElementById('ocr-section').hidden = true;
    document.getElementById('result-area').hidden = true;
    document.getElementById('processed-preview').hidden = true;

    retakePhoto('front');
    retakePhoto('back');

    // Ocultar secciones
    document.getElementById('step-upload').classList.remove('visible');
    setTimeout(() => {
        document.getElementById('step-upload').classList.add('visible');
    }, 100);

    showToast('Listo para escanear otro documento', 'success');
}

/**
 * Mostrar toast
 */
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

/* ============================================
   Event Listeners
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {
    initApp();

    // Inputs de archivo
    document.getElementById('input-front').addEventListener('change', e => {
        if (e.target.files[0]) handleFileSelect('front', e.target.files[0]);
    });
    document.getElementById('input-back').addEventListener('change', e => {
        if (e.target.files[0]) handleFileSelect('back', e.target.files[0]);
    });

    // Drag & Drop
    ['front', 'back'].forEach(side => {
        const zone = document.getElementById(`drop-${side}`);

        zone.addEventListener('dragover', e => {
            e.preventDefault();
            zone.classList.add('drag-active');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('drag-active');
        });

        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('drag-active');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                handleFileSelect(side, file);
            }
        });
    });

    // Toggle buttons (enhance mode)
    document.querySelectorAll('#enhance-mode .toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#enhance-mode .toggle-btn').forEach(b =>
                b.classList.remove('active'));
            btn.classList.add('active');
            state.enhanceMode = btn.dataset.value;
        });
    });

    // Toggle buttons (output format)
    document.querySelectorAll('#output-format .toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#output-format .toggle-btn').forEach(b =>
                b.classList.remove('active'));
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
            const tab = btn.dataset.tab;

            // Actualizar botones activos
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Mostrar tab correspondiente
            document.querySelectorAll('.tab-content').forEach(content => {
                content.hidden = true;
            });
            document.getElementById(`tab-${tab}`).hidden = false;
        });
    });
});
