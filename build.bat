@echo off
setlocal
cd /d "%~dp0"

set "VERSION=%~1"
if not defined VERSION for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "VERSION=%%i"

echo [1/5] Checking PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 goto :fail
)

echo [2/5] Building SendToKindle.exe (this takes a few minutes)...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SendToKindle --collect-all ebook_converter --collect-all ebook_converter_lib main.py
if errorlevel 1 goto :fail

echo [3/5] Copying poppler and docs...
xcopy /e /i /y poppler_bin dist\poppler_bin >nul
if errorlevel 1 goto :fail
copy /y README.md dist\ >nul
copy /y README.zh-CN.md dist\ >nul
copy /y requirements.txt dist\ >nul

echo [4/5] Running self-check...
start /wait "" "%CD%\dist\SendToKindle.exe" --check
if not exist dist\sendtokindle_check.log goto :checkfail
findstr /c:"RESULT: PASS" dist\sendtokindle_check.log >nul
if errorlevel 1 goto :checkfail
del /f /q dist\sendtokindle_check.log

echo [5/5] Creating release zip...
if not exist release mkdir release
powershell -NoProfile -Command "Compress-Archive -Path 'dist\*' -DestinationPath 'release\SendToKindle-%VERSION%-win64.zip' -Force"
if errorlevel 1 goto :fail

echo.
echo Done: release\SendToKindle-%VERSION%-win64.zip
pause
exit /b 0

:checkfail
echo Self-check FAILED. Log:
if exist dist\sendtokindle_check.log type dist\sendtokindle_check.log
goto :fail

:fail
echo.
echo BUILD FAILED
pause
exit /b 1
