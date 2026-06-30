@echo off
echo ==========================================
echo   DL/T 645 Meter Scanner - Windows Build
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

REM Install dependencies
echo [1/4] Installing dependencies...
pip install pyserial pyinstaller -q
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

REM Install package in editable mode
echo [2/4] Installing meter-scanner package...
pip install -e . -q
if errorlevel 1 (
    echo [ERROR] Failed to install package
    pause
    exit /b 1
)

REM Build GUI version
echo [3/4] Building GUI version...
pyinstaller --noconfirm --clean meter_scan_gui.spec
if errorlevel 1 (
    echo [ERROR] GUI build failed
    pause
    exit /b 1
)

REM Build CLI version
echo [4/4] Building CLI version...
pyinstaller --noconfirm --onefile --console --name "MeterScanner_CLI" --paths src --clean cli_entry.py
if errorlevel 1 (
    echo [ERROR] CLI build failed
    pause
    exit /b 1
)

echo.
if exist "dist\MeterScanner.exe" (
    echo   GUI: dist\MeterScanner.exe  [OK]
) else (
    echo   GUI: Build failed
)
if exist "dist\MeterScanner_CLI.exe" (
    echo   CLI: dist\MeterScanner_CLI.exe  [OK]
) else (
    echo   CLI: Build failed
)
echo.
echo ==========================================
echo   Binaries are in the dist folder.
echo   (No Python required, single-file portable)
echo ==========================================
pause
