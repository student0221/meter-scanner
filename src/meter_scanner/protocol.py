"""
DL/T 645-2007 协议层

提供帧构造、校验、解析等底层协议功能。
"""

from typing import Tuple

# 常量
WAKEUP_BYTES = bytes([0xFE, 0xFE, 0xFE, 0xFE])

# 支持的通信参数范围
BAUDRATES = [1200, 2400, 4800, 7200, 9600, 19200, 38400, 57600, 115200]
DATABITS = [8, 7]
PARITIES = ['N', 'E', 'O']
STOPBITS = [1, 2]

# 校验位映射
PARITY_MAP = {
    'N': 'PARITY_NONE',
    'E': 'PARITY_EVEN',
    'O': 'PARITY_ODD',
}

# 控制码定义
CTRL_READ_ADDR = 0x13       # 读通信地址（主站请求）
CTRL_NORMAL_RESP = 0x93     # 正常应答（从站）
CTRL_ERROR_RESP = 0xD1      # 异常应答（从站）


def calc_checksum(data: bytes | bytearray) -> int:
    """计算 DL/T 645 校验码：从第一个字节到校验码之前所有字节的模 256 和。"""
    return sum(data) & 0xFF


def build_read_addr_frame() -> bytes:
    """构造读通信地址请求报文（动态计算校验码）。

    帧格式: 68 AA AA AA AA AA AA 68 13 00 CS 16
    """
    frame = bytearray([0x68, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0x68, 0x13, 0x00])
    frame.append(calc_checksum(frame))
    frame.append(0x16)
    return bytes(frame)


def strip_fe_prefix(data: bytes) -> bytes:
    """去除前导 0xFE 唤醒字节。

    某些电表或采集器会将唤醒字节回传，需要跳过这些字节找到真正的帧头。
    """
    for i, byte in enumerate(data):
        if byte != 0xFE:
            return data[i:]
    return data


def verify_frame(data: bytes) -> Tuple[bool, str, str]:
    """验证并解析 DL/T 645 应答帧。

    Args:
        data: 原始应答数据（可能包含前导 FE 字节）。

    Returns:
        (success, message, addr_hex)
        - success: 帧是否有效
        - message: 解析结果描述
        - addr_hex: 电表地址（十六进制字符串，低位在前）
    """
    clean = strip_fe_prefix(data)

    if len(clean) < 12:
        return False, f"帧长度不足({len(clean)}字节)", ""

    # 起始符检查
    if clean[0] != 0x68 or clean[7] != 0x68:
        return False, "起始符错误", ""

    # 结束符检查
    if clean[-1] != 0x16:
        return False, "结束符错误", ""

    # 校验码验证
    cs_calc = calc_checksum(clean[:-2])
    cs_recv = clean[-2]
    if cs_calc != cs_recv:
        return False, f"校验码错误(计算{cs_calc:02X}≠收到{cs_recv:02X})", ""

    # 地址域：字节 1~6，低位在前
    addr_bytes = clean[1:7]
    addr_str = ''.join(f'{b:02X}' for b in reversed(addr_bytes))

    # 控制码
    ctrl = clean[8]
    if ctrl == CTRL_NORMAL_RESP:
        return True, f"正常应答 | 地址: {addr_str}", addr_str
    elif ctrl == CTRL_ERROR_RESP:
        err = clean[10] if len(clean) > 10 else 0
        return True, f"异常应答 | 错误码: {err:02X}", addr_str
    else:
        return True, f"应答控制码: {ctrl:02X} | 地址: {addr_str}", addr_str


def frame_to_hex(data: bytes) -> str:
    """将帧数据转为大写十六进制字符串。"""
    return data.hex().upper()
