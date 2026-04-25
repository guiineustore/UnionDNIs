"""
Script de arranque para UnionDNIs.
Ejecutar con: python run.py
"""

import uvicorn
import sys
import os


def main():
    print("=" * 50)
    print("  UnionDNIs — Escáner de Documentos")
    print("=" * 50)
    print(f"  Servidor: http://localhost:8000")
    print(f"  Red local: http://0.0.0.0:8000")
    print(f"  Parar: Ctrl+C")
    print("=" * 50)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
