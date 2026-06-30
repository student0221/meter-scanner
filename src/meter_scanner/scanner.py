"""
DL/T 645-2007 电表通信参数自动探测器 — 核心扫描引擎

提供 MeterScanner 类，支持手动测试和自动遍历扫描。
"""

import csv
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from .exceptions import SerialPortError, ResponseTimeout
from .protocol import (
    WAKEUP_BYTES, BAUDRATES, DATABITS, PARITIES, STOPBITS,
    PARITY_MAP, CTRL_NORMAL_RESP, CTRL_ERROR_RESP,
    calc_checksum, build_read_addr_frame, strip_fe_prefix, verify_frame,
)

# 扫描结果类型
ScanResult = dict  # {baud, databits, parity, stopbits, success, message, raw, addr, timestamp}


class MeterScanner:
    """DL/T 645-2007 电表通信参数自动探测器。

    Attributes:
        port: 串口设备路径。
        timeout_ms: 单次应答等待超时（毫秒）。
        send_wakeup: 是否发送唤醒字节 0xFE。
        on_log: 日志回调 fn(msg: str, level: str)。
        on_result: 单次结果回调 fn(result: ScanResult)。
    """

    def __init__(
        self,
        port: str,
        baudrates: Optional[List[int]] = None,
        databits: Optional[List[int]] = None,
        parities: Optional[List[str]] = None,
        stopbits: Optional[List[int]] = None,
        timeout_ms: int = 1500,
        send_wakeup: bool = True,
        custom_frame: Optional[bytes] = None,
        log_all_rx: bool = False,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_result: Optional[Callable[[ScanResult], None]] = None,
    ):
        self.port = port
        self.baudrates = baudrates or BAUDRATES[:]
        self.databits = databits or DATABITS[:]
        self.parities = parities or PARITIES[:]
        self.stopbits = stopbits or STOPBITS[:]
        self.timeout_ms = timeout_ms
        self.send_wakeup = send_wakeup
        self.custom_frame = custom_frame
        self.log_all_rx = log_all_rx

        self.on_log = on_log
        self.on_result = on_result

        self._is_scanning = False
        self._scan_thread: Optional[threading.Thread] = None
        self._ser: Optional[serial.Serial] = None

        self.all_results: List[ScanResult] = []
        self.success_results: List[ScanResult] = []

    # ─── 生命周期 ───────────────────────────────────────

    def open_port(self) -> None:
        """打开串口（使用默认参数，后续动态调整）。"""
        try:
            self._ser = serial.Serial(self.port, timeout=1)
            self._log(f"串口已打开: {self.port}", "success")
        except Exception as e:
            raise SerialPortError(f"打开串口失败: {e}") from e

    def close_port(self) -> None:
        """关闭串口。"""
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self._log("串口已关闭", "info")

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # ─── 手动测试 ───────────────────────────────────────

    def try_once(
        self,
        baud: int,
        databits: int = 8,
        parity: str = 'E',
        stopbits: int = 1,
    ) -> ScanResult:
        """用指定参数发送一次读地址报文，返回结果。

        如果串口未打开，会自动打开并在测试后关闭。
        """
        auto_close = not self.is_open
        if auto_close:
            self.open_port()

        try:
            ok, msg, raw, addr = self._try_params(baud, databits, parity, stopbits)
            result = self._make_result(baud, databits, parity, stopbits, ok, msg, raw, addr)
            return result
        finally:
            if auto_close:
                self.close_port()

    # ─── 自动扫描 ───────────────────────────────────────

    def start_scan(self) -> None:
        """启动后台扫描线程。"""
        if self._is_scanning:
            return
        if not self.is_open:
            raise SerialPortError("请先打开串口")

        self._is_scanning = True
        self.all_results.clear()
        self.success_results.clear()

        self._scan_thread = threading.Thread(target=self._scan_worker, daemon=True)
        self._scan_thread.start()

    def stop_scan(self) -> None:
        """请求停止扫描（立即生效）。"""
        self._is_scanning = False

    @property
    def is_scanning(self) -> bool:
        return self._is_scanning

    def wait(self, timeout: Optional[float] = None) -> None:
        """阻塞等待扫描线程结束。"""
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=timeout)

    # ─── 导出 ───────────────────────────────────────────

    def export_csv(self, output_dir: str = '.') -> List[str]:
        """导出扫描结果到 CSV 文件。

        Returns:
            生成的文件路径列表。
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        files = []

        # 完整日志
        full_path = out / f"meter_scan_full_{ts}.csv"
        with open(full_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位',
                             '结果', '详情', '地址', '原始应答报文', '时间戳'])
            for i, r in enumerate(self.all_results, 1):
                writer.writerow([
                    i, r['baud'], r['databits'], r['parity'], r['stopbits'],
                    '成功' if r['success'] else '失败',
                    r['message'], r.get('addr', ''), r['raw'], r['timestamp'],
                ])
        files.append(str(full_path))

        # 成功摘要
        if self.success_results:
            suc_path = out / f"meter_scan_success_{ts}.csv"
            with open(suc_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位',
                                 '地址', '原始报文', '推荐'])
                for i, r in enumerate(self.success_results, 1):
                    writer.writerow([
                        i, r['baud'], r['databits'], r['parity'], r['stopbits'],
                        r.get('addr', ''), r['raw'], '★ 推荐' if i == 1 else '',
                    ])
            files.append(str(suc_path))

        # 配置代码
        if self.success_results:
            best = self.success_results[0]
            cfg_path = out / f"meter_config_{ts}.py"
            parity_name = PARITY_MAP.get(best['parity'], 'PARITY_NONE')
            stopbits_val = 'ONE' if best['stopbits'] == 1 else 'TWO'
            with open(cfg_path, 'w', encoding='utf-8') as f:
                f.write(f'''# 自动生成的电表串口配置
# 扫描时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# 串口: {self.port}

import serial

SERIAL_CONFIG = {{
    'port': '{self.port}',
    'baudrate': {best['baud']},
    'bytesize': {best['databits']},
    'parity': serial.{parity_name},
    'stopbits': serial.STOPBITS_{stopbits_val},
    'timeout': 1
}}

if __name__ == '__main__':
    ser = serial.Serial(**SERIAL_CONFIG)
    print(f"串口已打开: {{ser.port}} @ {{ser.baudrate}}")
    ser.close()
''')
            files.append(str(cfg_path))

        return files

    # ─── 内部方法 ───────────────────────────────────────

    def _log(self, msg: str, level: str = 'info') -> None:
        if self.on_log:
            self.on_log(msg, level)

    def _try_params(self, baud, databits, parity, stopbits):
        """尝试一组参数，返回 (ok, msg, raw, addr_hex)。"""
        parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}
        stop_map = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}
        timeout_sec = self.timeout_ms / 1000.0

        try:
            self._ser.baudrate = baud
            self._ser.bytesize = databits
            self._ser.parity = parity_map.get(parity, serial.PARITY_NONE)
            self._ser.stopbits = stop_map.get(stopbits, serial.STOPBITS_ONE)
            self._ser.timeout = timeout_sec

            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            time.sleep(0.05)

            frame = self.custom_frame if self.custom_frame else build_read_addr_frame()

            if self.send_wakeup:
                self._ser.write(WAKEUP_BYTES)
                time.sleep(0.1)

            self._ser.write(frame)
            self._ser.flush()
            time.sleep(0.1)

            response = b''
            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                if self._ser.in_waiting > 0:
                    chunk = self._ser.read(self._ser.in_waiting)
                    response += chunk
                    if 0x16 in chunk:
                        break
                time.sleep(0.05)

            if len(response) == 0:
                return False, "无应答", b'', ''

            ok, msg, addr = verify_frame(response)
            return ok, msg, response, addr

        except serial.SerialException as e:
            return False, f"串口错误: {e}", b'', ''
        except Exception as e:
            return False, f"异常: {e}", b'', ''

    def _make_result(self, baud, databits, parity, stopbits, ok, msg, raw, addr):
        return {
            'baud': baud, 'databits': databits, 'parity': parity,
            'stopbits': stopbits, 'success': ok, 'message': msg,
            'raw': raw.hex().upper() if raw else '',
            'addr': addr,
            'timestamp': datetime.now().strftime("%H:%M:%S"),
        }

    def _scan_worker(self) -> None:
        """后台扫描工作线程。"""
        combos = [
            (b, d, p, s)
            for b in self.baudrates
            for d in self.databits
            for p in self.parities
            for s in self.stopbits
        ]
        total = len(combos)

        for idx, (baud, databits, parity, stopbits) in enumerate(combos, 1):
            if not self._is_scanning:
                break

            params = f"{baud}/{databits}-{parity}-{stopbits}"
            self._log(f"[{idx}/{total}] {params} (超时{self.timeout_ms}ms) ...", 'trying')

            # TX 日志
            tx_frame = self.custom_frame if self.custom_frame else build_read_addr_frame()
            tx_hex = tx_frame.hex().upper()
            if self.send_wakeup:
                self._log(f"TX: FE FE FE FE {tx_hex}", 'tx')
            else:
                self._log(f"TX: {tx_hex}", 'tx')

            ok, msg, raw, addr = self._try_params(baud, databits, parity, stopbits)

            # RX 日志
            if raw:
                self._log(f"RX: {raw.hex().upper()}", 'rx')
            else:
                self._log("RX: (无应答)", 'rx')

            result = self._make_result(baud, databits, parity, stopbits, ok, msg, raw, addr)
            self.all_results.append(result)

            if ok:
                self._log(f"  ✅ {msg}", 'success')
                self.success_results.append(result)

            if self.on_result:
                self.on_result(result)

            time.sleep(0.3)

        self._is_scanning = False
        self._log(
            f"探测完成 | 成功 {len(self.success_results)}/{total}",
            'done',
        )
