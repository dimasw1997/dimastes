@echo off
rem Skrip bantu Windows: siapkan .venv, pasang dependensi, lalu jalankan CLI.
rem Contoh: jalankan.bat run
rem          jalankan.bat config
rem          jalankan.bat history --limit 10
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Membuat virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :gagal
)

if not exist ".venv\Scripts\python.exe" goto :gagal

echo [2/3] Memasang dependensi...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :gagal

if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo File .env dibuat dari .env.example. Sesuaikan dulu bila perlu.
    )
)

echo [3/3] Menjalankan program...
echo.
".venv\Scripts\python.exe" cli.py %*
exit /b %errorlevel%

:gagal
echo.
echo GAGAL menyiapkan Python. Pastikan Python 3.10 atau lebih baru sudah
echo terpasang dan ada di PATH. Cek dengan: python --version
pause
exit /b 1
