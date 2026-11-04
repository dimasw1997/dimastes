@echo off
rem Simpan perubahan ke GitHub dengan satu klik (Windows).
rem Contoh: simpan.bat
rem          simpan.bat "Perbaiki filter judul"
rem Skrip ini: git add -A -> commit -> tarik perubahan terbaru -> push.
rem Aman dipakai berkali-kali: kalau tidak ada perubahan, hanya push saja.
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PESAN=%~1"

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [GAGAL] Folder ini bukan repo Git.
    exit /b 1
)

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "CABANG=%%b"
if "%CABANG%"=="" set "CABANG=main"
echo [1/4] Cabang: %CABANG%

rem --- 1. Kumpulkan perubahan (file .env, *.db, dan debug/ otomatis diabaikan) ---
git add -A
git diff --cached --quiet
if errorlevel 1 (
    if "%PESAN%"=="" (
        for /f "tokens=1-3 delims=/-. " %%d in ("%DATE%") do set "TGL=%%f-%%e-%%d"
        set "PESAN=Update otomatis !TGL! %TIME:~0,5%"
    )
    echo [2/4] Commit: !PESAN!
    git commit -m "!PESAN!"
    if errorlevel 1 (
        echo [GAGAL] Commit ditolak. Periksa pesan di atas.
        exit /b 1
    )
) else (
    echo [2/4] Tidak ada perubahan baru yang perlu di-commit.
)

rem --- 2. Tarik perubahan terbaru supaya tidak bentrok ---
git ls-remote --exit-code --heads origin %CABANG% >nul 2>&1
if errorlevel 1 (
    echo [3/4] Cabang belum ada di GitHub, langsung dikirim.
) else (
    echo [3/4] Menarik perubahan terbaru dari GitHub...
    git pull --rebase --autostash origin %CABANG%
    if errorlevel 1 (
        echo.
        echo [GAGAL] Gagal menarik perubahan ^(rebase bentrok^).
        echo   1. Ketik:  git rebase --abort
        echo   2. Simpan salinan folder ini, lalu jalankan lagi simpan.bat
        exit /b 1
    )
)

rem --- 3. Kirim ke GitHub ---
echo [4/4] Mengirim ke GitHub...
git push origin %CABANG%
if errorlevel 1 (
    echo.
    echo [GAGAL] Push ditolak. Kemungkinan besar karena login GitHub belum tersimpan.
    echo   Jalankan sekali:  git push origin %CABANG%
    echo   lalu ikuti jendela login yang muncul ^(browser/password^).
    echo   Setelah sekali berhasil, login tersimpan di Windows Credential Manager
    echo   sehingga simpan.bat berikutnya tidak akan bertanya lagi.
    exit /b 1
)

echo.
echo Selesai. Perubahan sudah ada di GitHub ^(cabang %CABANG%^).
exit /b 0
