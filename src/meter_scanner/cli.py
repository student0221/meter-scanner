"""
meter-scanner CLI 入口

命令行界面，支持手动测试和自动扫描。
"""

import argparse
import sys

from .scanner import MeterScanner
from .protocol import BAUDRATES, DATABITS, PARITIES, STOPBITS


def list_ports():
    """列出可用串口并返回设备名列表。"""
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ 未找到任何串口")
        sys.exit(1)
    print("\n可用串口：")
    for i, p in enumerate(ports):
        print(f"  [{i}] {p.device} - {p.description}")
    return [p.device for p in ports]


def interactive_select_port():
    """交互式选择串口。"""
    ports = list_ports()
    while True:
        try:
            choice = input("\n选择串口编号 (或直接输入路径如 COM3): ").strip()
            if choice.startswith('/dev/') or choice.upper().startswith('COM') or choice.startswith('tty'):
                return choice
            idx = int(choice)
            if 0 <= idx < len(ports):
                return ports[idx]
            print("编号超出范围")
        except ValueError:
            print("请输入数字或路径")


def cli_log(msg, level='info'):
    """CLI 日志输出。"""
    colors = {
        'success': '\033[92m',
        'fail': '\033[91m',
        'error': '\033[91m',
        'tx': '\033[94m',
        'rx': '\033[93m',
        'trying': '\033[90m',
        'done': '\033[96m',
    }
    reset = '\033[0m'
    color = colors.get(level, '')
    print(f"{color}{msg}{reset}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description='DL/T 645-2007 电表通信参数自动探测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  meter-scanner                    # 交互式选择串口
  meter-scanner -p COM3            # 指定串口
  meter-scanner -p COM3 -t 2000    # 超时 2000ms
  meter-scanner --no-wakeup        # 不发送唤醒字节
  meter-scanner -o ./output        # 指定输出目录
        ''',
    )
    parser.add_argument('-p', '--port', help='串口名称 (如 COM3, /dev/ttyUSB0)')
    parser.add_argument('-t', '--timeout', type=int, default=1500, help='响应超时 ms (默认1500)')
    parser.add_argument('--no-wakeup', action='store_true', help='不发送唤醒字节')
    parser.add_argument('-o', '--output', default='.', help='CSV 输出目录')
    parser.add_argument('--list-ports', action='store_true', help='仅列出可用串口')

    args = parser.parse_args()

    if args.list_ports:
        list_ports()
        return

    print("=" * 60)
    print("  DL/T 645-2007 电表通信参数自动探测工具")
    print("  Ctrl+C 随时停止")
    print("=" * 60)

    port = args.port or interactive_select_port()
    print(f"\n串口: {port}")
    print(f"超时: {args.timeout} ms | 唤醒: {'发送' if not args.no_wakeup else '跳过'}")

    scanner = MeterScanner(
        port=port,
        timeout_ms=args.timeout,
        send_wakeup=not args.no_wakeup,
        on_log=cli_log,
    )

    try:
        scanner.open_port()

        print(f"\n参数组合: {len(scanner.baudrates)*len(scanner.databits)*len(scanner.parities)*len(scanner.stopbits)} 种")
        print("开始探测...\n")

        scanner.start_scan()
        scanner.wait()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        scanner.stop_scan()
        scanner.wait(timeout=3)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
    finally:
        scanner.close_port()

    # 结果汇总
    print("\n" + "=" * 60)
    if not scanner.success_results:
        print("❌ 未找到匹配的通信参数")
        print("\n可能原因:")
        print("  1. 串口线未正确连接")
        print("  2. 电表未上电")
        print("  3. 电表使用非标准波特率或 DL/T645-1997")
    else:
        print(f"✅ 找到 {len(scanner.success_results)} 个匹配:\n")
        for i, r in enumerate(scanner.success_results, 1):
            tag = " ★ 推荐" if i == 1 else ""
            print(f"  [{i}] {r['baud']}/{r['databits']}-{r['parity']}-{r['stopbits']}{tag}")
            print(f"      {r['message']}\n")

    # CSV 导出
    if scanner.all_results:
        try:
            choice = input("导出 CSV? (y/n): ").strip().lower()
            if choice in ('y', 'yes', '是'):
                files = scanner.export_csv(args.output)
                for f in files:
                    print(f"  📄 {f}")
        except (KeyboardInterrupt, EOFError):
            pass

    print("\n探测结束。")


if __name__ == '__main__':
    main()
