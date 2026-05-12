#!/usr/bin/env python3
"""
DL/T 645-2007 电表通信参数自动探测工具（命令行版）

功能：自动遍历串口参数组合，探测 DL/T 645-2007 协议智能电表的通信参数。
用法：python meter_scan.py
"""

import serial
import serial.tools.list_ports
import time
import struct
import sys
import csv
import argparse
from datetime import datetime

# ===== 默认配置 =====
WAKEUP_BYTES = bytes([0xFE, 0xFE, 0xFE, 0xFE])

BAUDRATES = [1200, 2400, 4800, 7200, 9600, 19200, 38400, 57600, 115200]
DATABITS = [8, 7]
PARITIES = ['N', 'E', 'O']
STOPBITS = [1, 2]

RESPONSE_TIMEOUT_MS = 1500
RETRY_DELAY = 0.5


def list_serial_ports():
    """列出所有可用串口"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ 未找到任何串口！")
        print("   请检查：")
        print("   - USB 转串口线是否已连接")
        print("   - 驱动是否已安装")
        sys.exit(1)
    print("\n可用串口列表：")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port.device} - {port.description}")
    return [p.device for p in ports]


def select_port():
    """交互式选择串口"""
    ports = list_serial_ports()
    while True:
        try:
            choice = input("\n请选择串口编号 (或输入完整路径如 COM3): ").strip()
            if choice.startswith('/dev/') or choice.upper().startswith('COM') or choice.startswith('tty'):
                return choice
            idx = int(choice)
            if 0 <= idx < len(ports):
                return ports[idx]
            print("编号超出范围，请重新选择")
        except ValueError:
            print("请输入数字编号或完整串口路径")


def calc_checksum(data):
    """DL/T645 校验码：模256和"""
    return sum(data) & 0xFF


def build_read_addr_frame():
    """构造读地址报文"""
    frame = bytearray([0x68, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0x68, 0x13, 0x00])
    frame.append(calc_checksum(frame))
    frame.append(0x16)
    return bytes(frame)


def strip_fe_prefix(data):
    """去除前导 FE 字节"""
    for i, byte in enumerate(data):
        if byte != 0xFE:
            return data[i:]
    return data


def verify_frame(data):
    """验证 DL/T645 帧，返回 (success, message, addr_hex)"""
    clean = strip_fe_prefix(data)

    if len(clean) < 12:
        return False, f"帧长度不足({len(clean)}字节)", ""

    if clean[0] != 0x68 or clean[7] != 0x68:
        return False, "起始符错误", ""
    if clean[-1] != 0x16:
        return False, "结束符错误", ""

    cs = calc_checksum(clean[:-2])
    if cs != clean[-2]:
        return False, f"校验码错误(计算{cs:02X}≠收到{clean[-2]:02X})", ""

    addr_bytes = clean[1:7]
    addr_str = ''.join(f'{b:02X}' for b in reversed(addr_bytes))

    ctrl = clean[8]
    if ctrl == 0x93:
        return True, f"正常应答 | 地址: {addr_str}", addr_str
    elif ctrl == 0xD1:
        err = clean[10] if len(clean) > 10 else 0
        return True, f"异常应答 | 错误码: {err:02X}", addr_str
    else:
        return True, f"应答控制码: {ctrl:02X} | 地址: {addr_str}", addr_str


def try_communication(port, baud, databits, parity, stopbits, timeout_ms):
    """尝试用指定参数通信"""
    timeout_sec = timeout_ms / 1000.0
    parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}
    stopbits_map = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}

    try:
        ser = serial.Serial(
            port=port, baudrate=baud, bytesize=databits,
            parity=parity_map.get(parity, serial.PARITY_NONE),
            stopbits=stopbits_map.get(stopbits, serial.STOPBITS_ONE),
            timeout=timeout_sec, write_timeout=1
        )

        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # 唤醒
        ser.write(WAKEUP_BYTES)
        time.sleep(0.1)

        # 发送读地址报文
        ser.write(build_read_addr_frame())
        ser.flush()
        time.sleep(0.1)

        # 读取应答
        response = b''
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                response += chunk
                if 0x16 in chunk:
                    break
            time.sleep(0.05)

        ser.close()

        if len(response) == 0:
            return False, "无应答", b''

        ok, msg, addr = verify_frame(response)
        return ok, msg, response

    except serial.SerialException as e:
        return False, f"串口错误: {e}", b''
    except Exception as e:
        return False, f"异常: {e}", b''


def export_to_csv(all_results, success_results, port, output_dir='.'):
    """导出扫描结果到 CSV"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 完整日志
    full_path = f"{output_dir}/meter_scan_full_{timestamp}.csv"
    with open(full_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位',
                         '结果', '详情', '原始应答报文', '时间戳'])
        for i, r in enumerate(all_results, 1):
            writer.writerow([
                i, r['baud'], r['databits'], r['parity'], r['stopbits'],
                '成功' if r['success'] else '失败',
                r['message'], r['raw'], r['timestamp']
            ])
    print(f"  📄 完整日志: {full_path}")

    # 成功结果
    if success_results:
        summary_path = f"{output_dir}/meter_scan_success_{timestamp}.csv"
        with open(summary_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位',
                             '电表地址/结果', '原始应答报文', '推荐'])
            for i, r in enumerate(success_results, 1):
                writer.writerow([
                    i, r['baud'], r['databits'], r['parity'], r['stopbits'],
                    r['message'], r['raw'], '★ 推荐' if i == 1 else ''
                ])
        print(f"  📄 成功摘要: {summary_path}")

    # 配置代码
    if success_results:
        best = success_results[0]
        config_path = f"{output_dir}/meter_config_{timestamp}.py"
        with open(config_path, 'w', encoding='utf-8') as f:
            parity_name = {'N': 'NONE', 'E': 'EVEN', 'O': 'ODD'}.get(best['parity'], 'NONE')
            stopbits_val = 'ONE' if best['stopbits'] == 1 else 'TWO'
            f.write(f'''# 自动生成的电表串口配置
# 扫描时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# 串口: {port}

import serial

SERIAL_CONFIG = {{
    'port': '{port}',
    'baudrate': {best['baud']},
    'bytesize': {best['databits']},
    'parity': serial.PARITY_{parity_name},
    'stopbits': serial.STOPBITS_{stopbits_val},
    'timeout': 1
}}

if __name__ == '__main__':
    ser = serial.Serial(**SERIAL_CONFIG)
    print(f"串口已打开: {{ser.port}} @ {{ser.baudrate}}")
    ser.close()
''')
        print(f"  📄 配置代码: {config_path}")

    return full_path


def main():
    parser = argparse.ArgumentParser(
        description='DL/T 645-2007 电表通信参数自动探测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例：
  python meter_scan.py                    # 交互式选择串口
  python meter_scan.py -p COM3            # 指定串口
  python meter_scan.py -p COM3 -t 2000    # 指定超时 2000ms
  python meter_scan.py --no-wakeup        # 不发送唤醒字节
        '''
    )
    parser.add_argument('-p', '--port', help='串口名称 (如 COM3, /dev/ttyUSB0)')
    parser.add_argument('-t', '--timeout', type=int, default=1500, help='响应超时 (ms, 默认1500)')
    parser.add_argument('--no-wakeup', action='store_true', help='不发送唤醒字节 FE')
    parser.add_argument('-o', '--output', default='.', help='CSV 输出目录 (默认当前目录)')

    args = parser.parse_args()

    print("=" * 60)
    print("  DL/T 645-2007 电表通信参数自动探测工具")
    print("  支持 CSV 导出 | 按 Ctrl+C 随时停止")
    print("=" * 60)

    port = args.port if args.port else select_port()
    print(f"\n目标串口: {port}")
    print(f"超时设置: {args.timeout} ms")
    print(f"唤醒字节: {'发送' if not args.no_wakeup else '跳过'}")

    total = len(BAUDRATES) * len(DATABITS) * len(PARITIES) * len(STOPBITS)
    print(f"参数组合: {total} 种")
    print(f"  波特率: {BAUDRATES}")
    print(f"  数据位: {DATABITS}")
    print(f"  校验位: {PARITIES}")
    print(f"  停止位: {STOPBITS}")
    print("\n开始探测...\n")

    all_results = []
    success_results = []
    count = 0

    try:
        for baud in BAUDRATES:
            for databits in DATABITS:
                for parity in PARITIES:
                    for stopbits in STOPBITS:
                        count += 1
                        params_str = f"{baud}/{databits}-{parity}-{stopbits}"
                        print(f"[{count}/{total}] {params_str} ... ", end='', flush=True)

                        ok, msg, raw = try_communication(port, baud, databits, parity, stopbits, args.timeout)

                        result = {
                            'baud': baud, 'databits': databits, 'parity': parity,
                            'stopbits': stopbits, 'success': ok, 'message': msg,
                            'raw': raw.hex().upper() if raw else '',
                            'timestamp': datetime.now().strftime("%H:%M:%S")
                        }
                        all_results.append(result)

                        if ok:
                            print(f"✅ {msg}")
                            success_results.append(result)
                        else:
                            print(f"❌ {msg}")

                        time.sleep(RETRY_DELAY)

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断探测")

    # 汇总
    print("\n" + "=" * 60)
    print("探测结果汇总")
    print("=" * 60)

    if not success_results:
        print("❌ 未找到任何匹配的通信参数！")
        print("\n可能原因：")
        print("  1. 串口线未正确连接（A接A，B接B）")
        print("  2. 电表未上电或未进入通信状态")
        print("  3. 电表需要特殊的唤醒流程")
        print("  4. 电表使用非标准波特率")
        print("  5. 电表使用 DL/T645-1997 旧规约")
    else:
        print(f"\n✅ 共找到 {len(success_results)} 个成功组合：\n")
        for i, r in enumerate(success_results, 1):
            marker = " ★ 推荐" if i == 1 else ""
            print(f"  [{i}] {r['baud']}/{r['databits']}-{r['parity']}-{r['stopbits']}{marker}")
            print(f"      {r['message']}")
            print()

        best = success_results[0]
        print("-" * 60)
        print(f"推荐参数: {best['baud']}/{best['databits']}-{best['parity']}-{best['stopbits']}")
        print("-" * 60)

    # CSV 导出
    if all_results:
        print()
        export_choice = input("是否导出 CSV 报告? (y/n): ").strip().lower()
        if export_choice in ('y', 'yes', '是', '1'):
            export_to_csv(all_results, success_results, port, args.output)
            print("\n导出完成！")
        else:
            print("跳过导出。")

    print("\n探测结束。")


if __name__ == '__main__':
    main()
