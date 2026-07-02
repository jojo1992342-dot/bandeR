@echo off
setlocal
cd /d "%~dp0"

set "FFMPEG_BIN=C:\Users\Jonathan\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"
set "FFPROBE_BIN=C:\Users\Jonathan\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe"

set "WHISPER_CPP_BIN=C:\Users\Jonathan\Downloads\whisper-bin-x64\Release\whisper-cli.exe"
set "WHISPER_MODEL=C:\Users\Jonathan\Downloads\whisper-bin-x64\ggml-small-q8_0.bin"

echo Demarrage de Bande Rythmo Local Studio...
echo Whisper CLI: %WHISPER_CPP_BIN%
echo Whisper model: %WHISPER_MODEL%
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -m app.main
    goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    python -m app.main
    goto :eof
)

echo Python est introuvable. Installez Python 3.11+ puis relancez ce fichier.
pause

