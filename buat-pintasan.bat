@echo off
rem Buat pintasan "Lamar Otomatis" di Desktop agar cukup satu klik.
setlocal
cd /d "%~dp0"

set "TARGET=%~dp0Lamar Otomatis.bat"
set "DESKTOP="
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%D"

if "%DESKTOP%"=="" (
    echo Tidak bisa menemukan folder Desktop.
    pause
    exit /b 1
)

powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%DESKTOP%\Lamar Otomatis.lnk');" ^
  "$s.TargetPath='%TARGET%';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation='%SystemRoot%\System32\shell32.dll,21';" ^
  "$s.Save()"

if errorlevel 1 (
    echo Gagal membuat pintasan.
    pause
    exit /b 1
)

echo Pintasan "Lamar Otomatis" sudah dibuat di Desktop.
pause
exit /b 0
