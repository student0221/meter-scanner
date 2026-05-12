"""
MeterScanner 自定义异常体系
"""


class MeterScannerError(Exception):
    """MeterScanner 基础异常"""
    pass


class SerialPortError(MeterScannerError):
    """串口通信相关错误"""
    pass


class FrameError(MeterScannerError):
    """帧解析/校验相关错误"""
    pass


class ResponseTimeout(MeterScannerError):
    """等待应答超时"""
    pass
