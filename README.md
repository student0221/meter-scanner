# DL/T 645-2007 电表通信参数探测工具

自动遍历不同串口参数（波特率、数据位、校验位、停止位），探测 DL/T 645-2007 协议智能电表的通信参数。

## 快速开始

### 命令行

```bash
pip install pyserial
python meter_scan.py -p COM3
python meter_scan.py -p COM3 -t 2000
```

### 打包为 Windows exe

```bash
# 方式一：运行打包脚本
build.bat

# 方式二：手动打包
pip install pyinstaller
pyinstaller --onefile --windowed --name "电表探测工具" meter_scan_gui.py
pyinstaller --onefile --console --name "电表探测工具_CLI" meter_scan.py
```

## 功能

- 自动探测多种波特率和通信参数组合
- CSV 导出扫描结果
- DL/T 645 帧自动解析（地址、控制码、数据标识）
- FE 前缀自动过滤
- GUI 可视化界面
- Python API 可嵌入其他项目

## 支持波特率

1200 / 2400 / 4800 / 7200 / 9600 / 19200 / 38400 / 57600 / 115200 bps

## 项目结构

- `meter_scan.py` - CLI 版本（独立可运行）
- `meter_scan_gui.py` - GUI 版本（独立可运行）
- `src/meter_scanner/` - Python 包（可 pip install）
- `build.bat` - Windows 一键打包脚本
- `pyproject.toml` - 包配置

## License

MIT
