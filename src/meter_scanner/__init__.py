"""
meter-scanner — DL/T 645-2007 电表通信参数自动探测工具

用法:
    # 命令行
    meter-scanner -p COM3
    meter-scanner -p COM3 -t 2000

    # Python API
    from meter_scanner import MeterScanner
    scanner = MeterScanner('COM3', timeout_ms=1500)
    scanner.open_port()
    result = scanner.try_once(9600)
    scanner.close_port()
"""

from .scanner import MeterScanner
from .protocol import (
    BAUDRATES, DATABITS, PARITIES, STOPBITS,
    calc_checksum, build_read_addr_frame, verify_frame,
)
from .exceptions import MeterScannerError, SerialPortError, FrameError, ResponseTimeout

__version__ = "1.0.0"

__all__ = [
    'MeterScanner',
    'BAUDRATES', 'DATABITS', 'PARITIES', 'STOPBITS',
    'calc_checksum', 'build_read_addr_frame', 'verify_frame',
    'MeterScannerError', 'SerialPortError', 'FrameError', 'ResponseTimeout',
]
