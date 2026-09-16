@echo off
REM ==================================================
REM   UnionDNIs - Arranque del servidor local
REM   Doble clic en este archivo para iniciar la app.
REM ==================================================

cd /d "%~dp0"

echo ==================================================
echo    UnionDNIs - Escaner de Documentos
echo ==================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] No se encuentra el entorno virtual.
    echo.
    echo Esperaba encontrarlo en:
    echo    %~dp0venv\Scripts\python.exe
    echo.
    echo Para crearlo, abre PowerShell en esta carpeta y ejecuta:
    echo    python -m venv venv
    echo    .\venv\Scripts\pip.exe install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo  Servidor:  http://localhost:8000
echo  Para parar: pulsa Ctrl+C en esta ventana
echo.
echo Iniciando...
echo.

"venv\Scripts\python.exe" run.py

echo.
echo El servidor se ha detenido.
pause
