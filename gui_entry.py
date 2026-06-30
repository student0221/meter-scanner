"""GUI 入口 - 用于 PyInstaller 打包"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from meter_scanner.gui.app import main

if __name__ == '__main__':
    main()
