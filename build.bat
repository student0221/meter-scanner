@echo off
chcp 65001 >nul
echo ==========================================
echo   电表通信参数探测工具 - 打包脚本
echo ==========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 安装依赖
echo [1/4] 安装依赖...
pip install pyserial pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 打包单文件 exe
echo.
echo [2/4] 打包单文件 EXE（无控制台窗口）...
pyinstaller --clean --onefile --windowed --name "电表通信参数探测工具" ^
    --add-data "meter_scan_gui.py;." ^
    --hidden-import serial ^
    --hidden-import serial.tools.list_ports ^
    meter_scan_gui.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo [3/4] 复制说明文件...
if exist "README.md" copy "README.md" "dist\" >nul

echo.
echo [4/4] 打包完成！
echo.
echo 输出目录: dist\
echo 可执行文件: dist\电表通信参数探测工具.exe
echo.
pause
