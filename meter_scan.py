import serial
import serial.tools.list_ports
import time
import struct
import sys
import csv
from datetime import datetime

# ===== 配置区域 =====
SERIAL_PORT = None
WAKEUP_BYTES = bytes([0xFE, 0xFE, 0xFE, 0xFE])
READ_ADDR_FRAME = bytes([
    0x68,
    0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA,
    0x68,
    0x13,
    0x00,
    0xDF,
    0x16
])

BAUDRATES = [1200, 2400, 4800, 7200, 9600, 19200, 38400, 57600, 115200]
DATABITS = [8, 7]
PARITIES = ['N', 'E', 'O']
STOPBITS = [1, 2]

# 超时设置（毫秒）：发完报文后等待应答的时间
RESPONSE_TIMEOUT_MS = 1500

# 两次尝试之间的间隔（秒）
RETRY_DELAY = 0.5


def list_serial_ports():
    """列出所有可用串口"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("未找到任何串口！")
        sys.exit(1)
    print("\n可用串口列表：")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port.device} - {port.description}")
    return [p.device for p in ports]


def select_port():
    """选择串口"""
    ports = list_serial_ports()
    if SERIAL_PORT:
        if SERIAL_PORT in ports:
            print(f"\n使用指定串口: {SERIAL_PORT}")
            return SERIAL_PORT
        else:
            print(f"\n指定的串口 {SERIAL_PORT} 不可用！")
    
    while True:
        try:
            choice = input("\n请选择串口编号 (或输入完整路径如 COM3): ").strip()
            # 尝试直接作为路径使用
            if choice.startswith('/dev/') or choice.startswith('COM') or choice.startswith('tty'):
                return choice
            idx = int(choice)
            if 0 <= idx < len(ports):
                return ports[idx]
            print("编号超出范围，请重新选择")
        except ValueError:
            print("请输入数字编号或完整串口路径")


def calc_checksum(data):
    """计算 DL/T645 校验码：从第一个字节到校验码之前所有字节的模256和"""
    return sum(data) & 0xFF


def verify_frame(data):
    """验证接收到的帧是否符合 DL/T645 格式"""
    if len(data) < 12:
        return False, "帧长度不足"
    
    # 检查起始符和结束符
    if data[0] != 0x68 or data[7] != 0x68:
        return False, "起始符错误"
    if data[-1] != 0x16:
        return False, "结束符错误"
    
    # 校验码验证
    cs = calc_checksum(data[:-2])
    if cs != data[-2]:
        return False, f"校验码错误 (计算={cs:02X}, 实际={data[-2]:02X})"
    
    # 解析控制码
    ctrl = data[8]
    if ctrl == 0x93:
        addr = data[10:16]
        addr_str = ''.join(f'{b:02X}' for b in addr)
        return True, f"正常应答，通信地址: {addr_str}"
    elif ctrl == 0xD1:
        err = data[10] if len(data) > 10 else 0
        return True, f"异常应答，错误码: {err:02X}"
    else:
        return True, f"应答控制码: {ctrl:02X}"


def build_read_addr_frame():
    """构造读地址报文（动态计算校验码）"""
    frame = bytearray([
        0x68,
        0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA,
        0x68,
        0x13,
        0x00
    ])
    cs = calc_checksum(frame)
    frame.append(cs)
    frame.append(0x16)
    return bytes(frame)


def export_to_csv(all_results, success_results, port):
    """导出扫描结果到 CSV 文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 导出完整扫描日志
    full_filename = f"meter_scan_full_{timestamp}.csv"
    with open(full_filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位', 
                        '结果', '详情', '原始应答报文', '时间戳'])
        for i, r in enumerate(all_results, 1):
            writer.writerow([
                i,
                r['baud'],
                r['databits'],
                r['parity'],
                r['stopbits'],
                '成功' if r['success'] else '失败',
                r['message'],
                r['raw'],
                r['timestamp']
            ])
    print(f"  📄 完整日志已导出: {full_filename}")
    
    # 2. 导出成功结果摘要
    if success_results:
        summary_filename = f"meter_scan_success_{timestamp}.csv"
        with open(summary_filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位', 
                            '电表地址/结果', '原始应答报文', '推荐'])
            for i, r in enumerate(success_results, 1):
                writer.writerow([
                    i,
                    r['baud'],
                    r['databits'],
                    r['parity'],
                    r['stopbits'],
                    r['message'],
                    r['raw'],
                    '★ 推荐' if i == 1 else ''
                ])
        print(f"  📄 成功结果已导出: {summary_filename}")
    
    # 3. 导出可直接使用的配置代码
    if success_results:
        best = success_results[0]
        code_filename = f"meter_config_{timestamp}.py"
        with open(code_filename, 'w', encoding='utf-8') as f:
            f.write(f'''# 自动生成的电表串口配置
# 扫描时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# 串口: {port}
# 探测到的电表通信参数

import serial

# 推荐配置（最优匹配）
METER_CONFIG = {{
    'port': '{port}',
    'baudrate': {best['baud']},
    'bytesize': {best['databits']},
    'parity': serial.PARITY_{'NONE' if best['parity']=='N' else 'EVEN' if best['parity']=='E' else 'ODD'},
    'stopbits': serial.STOPBITS_{'ONE' if best['stopbits']==1 else 'TWO'},
    'timeout': 1
}}

# 电表地址（十六进制）
METER_ADDRESS = '{best.get('addr', 'AA AA AA AA AA AA')}'

# 使用示例
if __name__ == '__main__':
    ser = serial.Serial(**METER_CONFIG)
    print(f"串口已打开: {{ser.port}}")
    print(f"配置: {{ser.baudrate}}/{{ser.bytesize}}-{{ser.parity}}-{{ser.stopbits}}")
    ser.close()
''')
        print(f"  📄 配置代码已导出: {code_filename}")
    
    return full_filename

    """将字符校验位转换为 pyserial 常量"""
    return {
        'N': serial.PARITY_NONE,
        'E': serial.PARITY_EVEN,
        'O': serial.PARITY_ODD,
    }.get(p, serial.PARITY_NONE)


def parse_stopbits(s):
    """将数字停止位转换为 pyserial 常量"""
    return {
        1: serial.STOPBITS_ONE,
        2: serial.STOPBITS_TWO,
    }.get(s, serial.STOPBITS_ONE)


def try_communication(port, baud, databits, parity, stopbits):
    """尝试用指定参数通信，返回 (success, message, raw_response)"""
    timeout_sec = RESPONSE_TIMEOUT_MS / 1000.0
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=databits,
            parity=parse_parity(parity),
            stopbits=parse_stopbits(stopbits),
            timeout=timeout_sec,
            write_timeout=1
        )
        
        # 清空缓冲区
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # 发送唤醒字节（可选，某些电表需要）
        ser.write(WAKEUP_BYTES)
        time.sleep(0.1)  # 唤醒后稍等片刻
        
        # 发送读地址报文
        frame = build_read_addr_frame()
        ser.write(frame)
        
        # 等待并读取应答
        ser.flush()
        time.sleep(0.1)  # 给电表一点处理时间（Td: 20ms~500ms）
        
        # 读取所有可用数据
        response = b''
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                response += chunk
                # 如果收到结束符 0x16，认为帧结束
                if 0x16 in chunk:
                    break
            time.sleep(0.05)
        
        ser.close()
        
        if len(response) == 0:
            return False, "无应答", b''
        
        # 验证帧
        ok, msg = verify_frame(response)
        return ok, msg, response
        
    except serial.SerialException as e:
        return False, f"串口错误: {e}", b''
    except Exception as e:
        return False, f"异常: {e}", b''


def main():
    print("=" * 60)
    print("DL/T 645-2007 电表通信参数自动探测工具")
    print("支持 CSV 导出 | 按 Ctrl+C 可随时停止")
    print("=" * 60)
    
    port = select_port()
    
    print(f"\n目标串口: {port}")
    print(f"遍历参数:")
    print(f"  波特率: {BAUDRATES}")
    print(f"  数据位: {DATABITS}")
    print(f"  校验位: {PARITIES} (N=None, E=Even, O=Odd)")
    print(f"  停止位: {STOPBITS}")
    print(f"  总组合数: {len(BAUDRATES)*len(DATABITS)*len(PARITIES)*len(STOPBITS)}")
    print(f"\n开始探测...\n")
    
    all_results = []    # 记录所有尝试（成功+失败）
    success_results = [] # 仅记录成功
    total = len(BAUDRATES) * len(DATABITS) * len(PARITIES) * len(STOPBITS)
    count = 0
    
    try:
        for baud in BAUDRATES:
            for databits in DATABITS:
                for parity in PARITIES:
                    for stopbits in STOPBITS:
                        count += 1
                        params_str = f"{baud}/{databits}-{parity}-{stopbits}"
                        print(f"[{count}/{total}] {params_str} ... ", end='', flush=True)
                        
                        ok, msg, raw = try_communication(port, baud, databits, parity, stopbits)
                        
                        result = {
                            'baud': baud,
                            'databits': databits,
                            'parity': parity,
                            'stopbits': stopbits,
                            'success': ok,
                            'message': msg,
                            'raw': raw.hex().upper() if raw else '',
                            'timestamp': datetime.now().strftime("%H:%M:%S")
                        }
                        all_results.append(result)
                        
                        if ok:
                            print(f"✅ 成功! {msg}")
                            # 尝试提取地址
                            if raw and len(raw) >= 16:
                                addr = raw[10:16].hex().upper() if raw[8] == 0x93 else ''
                                result['addr'] = addr
                            success_results.append(result)
                        else:
                            print(f"❌ {msg}")
                        
                        time.sleep(RETRY_DELAY)
                        
    except KeyboardInterrupt:
        print("\n\n用户中断探测")
    
    # ===== 结果汇总 =====
    print("\n" + "=" * 60)
    print("探测结果汇总")
    print("=" * 60)
    
    if not success_results:
        print("未找到任何匹配的通信参数！")
        print("\n可能原因：")
        print("  1. 串口线未正确连接（A接A，B接B）")
        print("  2. 电表未上电或未进入通信状态")
        print("  3. 电表需要特殊的唤醒流程")
        print("  4. 电表使用非标准波特率")
        print("  5. 电表使用 DL/T645-1997 旧规约")
    else:
        print(f"\n共找到 {len(success_results)} 个成功组合：\n")
        for i, r in enumerate(success_results, 1):
            marker = "★ 推荐" if i == 1 else ""
            print(f"  [{i}] {r['baud']}/{r['databits']}-{r['parity']}-{r['stopbits']} {marker}")
            print(f"      结果: {r['message']}")
            print(f"      原始报文: {r['raw']}")
            print()
        
        best = success_results[0]
        print("-" * 60)
        print(f"推荐参数: {best['baud']}/{best['databits']}-{best['parity']}-{best['stopbits']}")
        print(f"  波特率 : {best['baud']}")
        print(f"  数据位 : {best['databits']}")
        print(f"  校验位 : {best['parity']} ({'None' if best['parity']=='N' else 'Even' if best['parity']=='E' else 'Odd'})")
        print(f"  停止位 : {best['stopbits']}")
        print(f"  电表地址: {best.get('addr', 'N/A')}")
        print("-" * 60)
    
    # ===== CSV 导出 =====
    print("\n" + "=" * 60)
    export_choice = input("是否导出 CSV 报告? (y/n): ").strip().lower()
    if export_choice in ('y', 'yes', '是', '1'):
        exported = export_to_csv(all_results, success_results, port)
        print(f"\n导出完成！文件保存在当前目录。")
    else:
        print("跳过导出。")
    
    print("\n探测结束。")

if __name__ == '__main__':
    main()
