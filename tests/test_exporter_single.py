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
