"""Test del endpoint de rotación: la calidad JPEG no debe degradarse."""
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
