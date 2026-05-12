@echo off
chcp 65001 >nul
echo ==========================================
echo   DL/T 645 电表探测工具 - Windows 打包脚本
echo ==========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装依赖...
pip install pyserial pyinstaller -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

REM 安装本包（editable 模式）
echo [2/4] 安装 meter-scanner 包...
pip install -e . -q
if errorlevel 1 (
    echo [错误] 包安装失败
    pause
    exit /b 1
)

REM 打包 GUI 版本（使用 spec 文件，确保新包结构正确）
echo [3/4] 打包 GUI 版本...
pyinstaller --noconfirm --clean meter_scan_gui.spec

REM 如果 spec 方式失败，用 fallback 打包旧版入口
echo [4/4] 打包 CLI 版本...
pyinstaller --noconfirm --onefile --console --name "电表探测工具_CLI" --clean meter_scan.py

echo.
if exist "dist\电表探测工具.exe" (
    echo   GUI 版本: dist\电表探测工具.exe  [OK]
) else (
    echo   GUI 版本: 打包失败
)
if exist "dist\电表探测工具_CLI.exe" (
    echo   CLI 版本: dist\电表探测工具_CLI.exe  [OK]
) else (
    echo   CLI 版本: 打包失败
)
echo.
echo ==========================================
echo   文件位于 dist 目录下，可直接拷贝给其他人
echo   （无需安装 Python，绿色单文件）
echo ==========================================
pause
