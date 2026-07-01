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
