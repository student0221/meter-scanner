import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime


class MeterScannerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DL/T 645-2007 电表通信参数探测工具")
        self.root.geometry("1000x800")
        self.root.minsize(1000, 800)
        
        # 数据存储
        self.all_results = []
        self.success_results = []
        self.is_scanning = False
        self.scan_thread = None
        self.ser = None  # 手动串口对象
        
        self.build_ui()
        self.refresh_ports()
    
    def build_ui(self):
        # ===== 第1行：串口配置 + 手动控制 =====
        port_frame = ttk.LabelFrame(self.root, text="串口配置", padding=10)
        port_frame.pack(fill='x', padx=10, pady=5)
        
        # 串口选择
        ttk.Label(port_frame, text="串口:").grid(row=0, column=0, sticky='w')
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=18)
        self.port_combo.grid(row=0, column=1, padx=5)
        ttk.Button(port_frame, text="刷新", command=self.refresh_ports, width=6).grid(row=0, column=2, padx=3)
        
        # 波特率
        ttk.Label(port_frame, text="波特率:").grid(row=0, column=3, sticky='w', padx=(15,0))
        self.baud_var = tk.StringVar(value="9600")
        self.baud_combo = ttk.Combobox(port_frame, textvariable=self.baud_var, values=[1200,2400,4800,7200,9600,19200,38400,57600,115200], width=8)
        self.baud_combo.grid(row=0, column=4, padx=3)
        
        # 数据位
        ttk.Label(port_frame, text="数据位:").grid(row=0, column=5, sticky='w', padx=(10,0))
        self.data_var = tk.StringVar(value="8")
        ttk.Combobox(port_frame, textvariable=self.data_var, values=["7","8"], width=5).grid(row=0, column=6, padx=3)
        
        # 校验位
        ttk.Label(port_frame, text="校验:").grid(row=0, column=7, sticky='w', padx=(10,0))
        self.parity_var = tk.StringVar(value="E")
        ttk.Combobox(port_frame, textvariable=self.parity_var, values=["N","E","O"], width=5).grid(row=0, column=8, padx=3)
        
        # 停止位
        ttk.Label(port_frame, text="停止位:").grid(row=0, column=9, sticky='w', padx=(10,0))
        self.stop_var = tk.StringVar(value="1")
        ttk.Combobox(port_frame, textvariable=self.stop_var, values=["1","2"], width=5).grid(row=0, column=10, padx=3)
        
        # 打开/关闭串口按钮
        self.open_btn = ttk.Button(port_frame, text="🔌 打开串口", command=self.open_serial, width=12)
        self.open_btn.grid(row=0, column=11, padx=(15,3))
        self.close_btn = ttk.Button(port_frame, text="🔒 关闭串口", command=self.close_serial, width=12, state='disabled')
        self.close_btn.grid(row=0, column=12, padx=3)
        
        # 串口状态
        self.serial_status_var = tk.StringVar(value="串口状态: 未打开")
        ttk.Label(port_frame, textvariable=self.serial_status_var, foreground='gray').grid(row=1, column=0, columnspan=13, sticky='w', pady=(5,0))
        
        # ===== 第2行：手动发送区 =====
        manual_frame = ttk.LabelFrame(self.root, text="手动发送报文 (十六进制, 空格分隔)", padding=10)
        manual_frame.pack(fill='x', padx=10, pady=5)
        
        self.tx_entry = ttk.Entry(manual_frame, font=('Consolas', 11))
        self.tx_entry.pack(fill='x', side='left', expand=True, padx=(0,5))
        self.tx_entry.insert(0, "68 AA AA AA AA AA AA 68 13 00 DF 16")
        
        self.wakeup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(manual_frame, text="先发唤醒 FE", variable=self.wakeup_var).pack(side='left', padx=5)
        
        ttk.Button(manual_frame, text="📤 发送", command=self.manual_send, width=10).pack(side='left', padx=5)
        ttk.Button(manual_frame, text="🗑 清空日志", command=self.clear_log, width=10).pack(side='left', padx=5)
        
        # ===== 第3行：日志显示区 =====
        log_frame = ttk.LabelFrame(self.root, text="通信日志", padding=5)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap='word', font=('Consolas', 10))
        self.log_text.pack(fill='both', expand=True)
        
        # ===== 第4行：自动探测区 =====
        scan_frame = ttk.LabelFrame(self.root, text="自动探测参数", padding=10)
        scan_frame.pack(fill='x', padx=10, pady=5)
        
        # 波特率多选
        ttk.Label(scan_frame, text="波特率:").grid(row=0, column=0, sticky='w')
        self.baud_frame = ttk.Frame(scan_frame)
        self.baud_frame.grid(row=0, column=1, columnspan=3, sticky='w', padx=5)
        self.baud_vars = {}
        for baud in [1200, 2400, 4800, 7200, 9600, 19200, 38400, 57600, 115200]:
            var = tk.BooleanVar(value=True)
            self.baud_vars[baud] = var
            ttk.Checkbutton(self.baud_frame, text=str(baud), variable=var).pack(side='left', padx=3)
        
        # 超时
        ttk.Label(scan_frame, text="等待超时(ms):").grid(row=1, column=0, sticky='w', pady=5)
        self.timeout_var = tk.StringVar(value="1500")
        ttk.Entry(scan_frame, textvariable=self.timeout_var, width=10).grid(row=1, column=1, sticky='w', padx=5)
        ttk.Label(scan_frame, text="发完报文后等待应答的时间").grid(row=1, column=2, sticky='w')
        
        # 探测按钮
        btn_frame = ttk.Frame(scan_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, sticky='w', pady=5)
        
        self.scan_btn = ttk.Button(btn_frame, text="▶ 开始探测", command=self.start_scan, width=15)
        self.scan_btn.pack(side='left', padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止", command=self.stop_scan, width=15, state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        self.export_btn = ttk.Button(btn_frame, text="📄 导出 CSV", command=self.export_csv, width=15, state='disabled')
        self.export_btn.pack(side='left', padx=5)
        
        # ===== 第5行：进度与结果 =====
        self.progress = ttk.Progressbar(self.root, mode='determinate')
        self.progress.pack(fill='x', padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="就绪 | 先打开串口，可手动发送测试")
        ttk.Label(self.root, textvariable=self.status_var).pack(anchor='w', padx=10)
        
        # 结果表格
        result_frame = ttk.LabelFrame(self.root, text="探测成功结果", padding=5)
        result_frame.pack(fill='x', padx=10, pady=5)
        
        self.result_tree = ttk.Treeview(result_frame, columns=('params', 'address', 'raw'), show='headings', height=3)
        self.result_tree.heading('params', text='通信参数')
        self.result_tree.heading('address', text='电表地址/结果')
        self.result_tree.heading('raw', text='原始应答报文')
        self.result_tree.column('params', width=150)
        self.result_tree.column('address', width=250)
        self.result_tree.column('raw', width=450)
        self.result_tree.pack(fill='x')
    
    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [f"{p.device} - {p.description[:30]}" for p in ports]
        self.port_combo['values'] = port_list
        if port_list and not self.port_var.get():
            self.port_combo.set(port_list[0])
    
    def log(self, msg, tag=''):
        self.log_text.insert('end', msg + '\n', tag)
        self.log_text.see('end')
        self.root.update_idletasks()
    
    def get_port_name(self):
        port_full = self.port_var.get()
        return port_full.split(' - ')[0] if ' - ' in port_full else port_full
    
    def open_serial(self):
        port = self.get_port_name()
        if not port:
            messagebox.showwarning("提示", "请先选择串口")
            return
        
        try:
            baud = int(self.baud_var.get())
            databits = int(self.data_var.get())
            parity = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}[self.parity_var.get()]
            stopbits = int(self.stop_var.get())
            
            self.ser = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=databits,
                parity=parity,
                stopbits={1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}[stopbits],
                timeout=1,
                write_timeout=1
            )
            
            self.serial_status_var.set(
                f"串口状态: 已打开 | {port} @ {baud}/{databits}-{self.parity_var.get()}-{stopbits}"
            )
            self.open_btn.config(state='disabled')
            self.close_btn.config(state='normal')
            self.log(f"串口已打开: {port} @ {baud}/{databits}-{self.parity_var.get()}-{stopbits}", 'info')
            
        except Exception as e:
            messagebox.showerror("错误", f"打开串口失败: {e}")
    
    def close_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.serial_status_var.set("串口状态: 已关闭")
        self.open_btn.config(state='normal')
        self.close_btn.config(state='disabled')
        self.log("串口已关闭", 'info')
    
    def hex_to_bytes(self, hex_str):
        """将十六进制字符串（空格分隔）转为 bytes"""
        hex_str = hex_str.strip().replace(' ', '')
        if len(hex_str) % 2 != 0:
            return None, "十六进制字符串长度必须是偶数"
        try:
            return bytes.fromhex(hex_str), None
        except ValueError as e:
            return None, f"十六进制格式错误: {e}"
    
    def strip_fe_prefix(self, data):
        """去掉开头的 FE 字节，找到第一个 68"""
        i = 0
        while i < len(data) and data[i] == 0xFE:
            i += 1
        return data[i:]
    
    def manual_send(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("提示", "串口未打开，请先点击【打开串口】")
            return
        
        hex_str = self.tx_entry.get().strip()
        tx_bytes, err = self.hex_to_bytes(hex_str)
        if err:
            messagebox.showerror("格式错误", err)
            return
        
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            if self.wakeup_var.get():
                self.ser.write(bytes([0xFE, 0xFE, 0xFE, 0xFE]))
                self.log(f"TX(唤醒): FE FE FE FE", 'trying')
                time.sleep(0.1)
            
            self.ser.write(tx_bytes)
            self.log(f"TX: {tx_bytes.hex().upper()}", 'trying')
            self.ser.flush()
            
            # 读取回复
            time.sleep(0.2)
            response = b''
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting)
                    response += chunk
                    if 0x16 in chunk:
                        break
                time.sleep(0.05)
            
            if len(response) == 0:
                self.log("RX: (无应答)", 'fail')
                return
            
            self.log(f"RX: {response.hex().upper()}", 'info')
            
            # 解析帧
            clean = self.strip_fe_prefix(response)
            if len(clean) < 12:
                self.log(f"  ⚠️ 去掉FE前缀后数据不足: {clean.hex().upper()}", 'fail')
                return
            
            if clean[0] != 0x68 or clean[7] != 0x68 or clean[-1] != 0x16:
                self.log(f"  ❌ 帧头/帧尾错误: 首={clean[0]:02X}, 中={clean[7]:02X}, 尾={clean[-1]:02X}", 'fail')
                return
            
            cs_calc = sum(clean[:-2]) & 0xFF
            cs_recv = clean[-2]
            if cs_calc != cs_recv:
                self.log(f"  ❌ 校验码错误: 计算={cs_calc:02X}, 收到={cs_recv:02X}", 'fail')
                return
            
            ctrl = clean[8]
            l = clean[9]
            addr = clean[1:7].hex().upper()
            
            # 控制码解析
            is_response = (ctrl & 0x80) != 0
            has_follow = (ctrl & 0x20) != 0
            func = ctrl & 0x1F
            
            func_names = {
                0x01: "读数据", 0x02: "读后续数据", 0x03: "重读数据",
                0x04: "写数据", 0x08: "广播校时", 0x10: "写设备地址",
                0x12: "更改通信速率", 0x13: "修改密码", 0x14: "最大需量清零",
                0x15: "电表清零", 0x16: "事件清零"
            }
            func_name = func_names.get(func, f"未知功能(0x{func:02X})")
            
            dir_str = "从站应答" if is_response else "主站请求"
            self.log(f"  ✅ 帧格式正确 | 方向: {dir_str} | 功能: {func_name}", 'success')
            self.log(f"  地址: {addr} | 控制码: {ctrl:02X} | L={l} | CS={cs_recv:02X}", 'success')
            
            # 如果有数据域，解析 DI
            if l > 0 and len(clean) >= 12 + l:
                di = clean[10:14].hex().upper() if l >= 4 else clean[10:10+l].hex().upper()
                self.log(f"  数据标识(DI): {di}", 'success')
                
                if l > 4:
                    data_val = clean[14:10+l].hex().upper()
                    self.log(f"  数据值: {data_val}", 'success')
            
        except Exception as e:
            self.log(f"发送异常: {e}", 'fail')
    
    def calc_checksum(self, data):
        return sum(data) & 0xFF
    
    def build_read_addr_frame(self):
        frame = bytearray([0x68, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0x68, 0x13, 0x00])
        frame.append(self.calc_checksum(frame))
        frame.append(0x16)
        return bytes(frame)
    
    def try_once(self, port, baud, databits, parity, stopbits, timeout_ms):
        try:
            timeout_sec = timeout_ms / 1000.0
            ser = serial.Serial(
                port=port, baudrate=baud, bytesize=databits,
                parity={'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}[parity],
                stopbits={1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}[stopbits],
                timeout=timeout_sec, write_timeout=1
            )
            
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            ser.write(bytes([0xFE, 0xFE, 0xFE, 0xFE]))
            time.sleep(0.1)
            
            ser.write(self.build_read_addr_frame())
            ser.flush()
            
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
            
            # 去掉 FE 前缀
            clean = self.strip_fe_prefix(response)
            if len(clean) < 12:
                return False, f"数据过短(去FE后{len(clean)}字节)", response
            
            if clean[0] != 0x68 or clean[7] != 0x68 or clean[-1] != 0x16:
                return False, "帧头/帧尾错误", response
            
            cs = self.calc_checksum(clean[:-2])
            if cs != clean[-2]:
                return False, f"校验码错误(计算{cs:02X}!=收到{clean[-2]:02X})", response
            
            ctrl = clean[8]
            if ctrl == 0x93:
                addr = clean[10:16].hex().upper() if len(clean) > 15 else ''
                return True, f"地址: {addr}", response
            elif ctrl == 0xD1:
                return True, f"异常应答", response
            else:
                return False, f"未知控制码{ctrl:02X}", response
            
        except Exception as e:
            return False, str(e), b''
    
    def scan_worker(self):
        port = self.get_port_name()
        if not port:
            self.log("错误: 未选择串口", 'fail')
            self.is_scanning = False
            return
        
        baudrates = [b for b, v in self.baud_vars.items() if v.get()]
        databits = [int(self.data_var.get())]
        parities = [self.parity_var.get()]
        stopbits = [int(self.stop_var.get())]
        timeout_ms = int(self.timeout_var.get() or 1500)
        
        total = len(baudrates) * len(databits) * len(parities) * len(stopbits)
        count = 0
        
        self.all_results = []
        self.success_results = []
        
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        for baud in baudrates:
            if not self.is_scanning:
                break
            for databit in databits:
                for parity in parities:
                    for stopbit in stopbits:
                        if not self.is_scanning:
                            break
                        
                        count += 1
                        params = f"{baud}/{databit}-{parity}-{stopbit}"
                        
                        self.status_var.set(f"正在探测: {params} ({count}/{total})")
                        self.progress['value'] = (count / total) * 100
                        self.log(f"[{count}/{total}] {params} (超时{timeout_ms}ms) ...", 'trying')
                        
                        ok, msg, raw = self.try_once(port, baud, databit, parity, stopbit, timeout_ms)
                        
                        result = {
                            'baud': baud, 'databits': databit, 'parity': parity,
                            'stopbits': stopbit, 'success': ok, 'message': msg,
                            'raw': raw.hex().upper() if raw else '',
                            'timestamp': datetime.now().strftime("%H:%M:%S")
                        }
                        self.all_results.append(result)
                        
                        if ok:
                            self.log(f"  ✅ 成功! {msg}", 'success')
                            result['addr'] = raw[10:16].hex().upper() if len(raw) > 15 and raw[8] == 0x93 else ''
                            self.success_results.append(result)
                            self.result_tree.insert('', 'end', values=(params, msg, raw.hex().upper()))
                        else:
                            self.log(f"  ❌ {msg}", 'fail')
                        
                        time.sleep(0.3)
        
        self.is_scanning = False
        self.scan_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        
        if self.success_results:
            self.status_var.set(f"探测完成! 找到 {len(self.success_results)} 个匹配参数")
            self.export_btn.config(state='normal')
            self.log("\n" + "="*50, 'info')
            self.log(f"探测完成! 共 {len(self.success_results)} 个成功组合", 'success')
            best = self.success_results[0]
            self.log(f"推荐参数: {best['baud']}/{best['databits']}-{best['parity']}-{best['stopbits']}", 'success')
        else:
            self.status_var.set("探测完成，未找到匹配参数")
            self.log("\n未找到任何匹配的通信参数", 'fail')
            self.log("请检查: 1.串口连接 2.电表上电 3.接线(A-A, B-B)", 'info')
        
        self.progress['value'] = 100
    
    def start_scan(self):
        if self.is_scanning:
            return
        
        self.is_scanning = True
        self.scan_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.export_btn.config(state='disabled')
        self.log_text.delete(1.0, 'end')
        self.progress['value'] = 0
        
        self.scan_thread = threading.Thread(target=self.scan_worker, daemon=True)
        self.scan_thread.start()
    
    def stop_scan(self):
        self.is_scanning = False
        self.status_var.set("用户停止探测")
        self.log("\n用户停止探测", 'info')
    
    def export_csv(self):
        if not self.all_results:
            messagebox.showwarning("无数据", "没有扫描结果可导出")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            initialfile=f"meter_scan_{timestamp}.csv",
            title="导出扫描结果"
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位', 
                                '结果', '详情', '原始应答报文', '时间戳'])
                for i, r in enumerate(self.all_results, 1):
                    writer.writerow([
                        i, r['baud'], r['databits'], r['parity'], r['stopbits'],
                        '成功' if r['success'] else '失败',
                        r['message'], r['raw'], r['timestamp']
                    ])
            
            if self.success_results:
                summary_path = filepath.replace('.csv', '_success.csv')
                with open(summary_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位', 
                                    '电表地址/结果', '原始报文', '推荐'])
                    for i, r in enumerate(self.success_results, 1):
                        writer.writerow([
                            i, r['baud'], r['databits'], r['parity'], r['stopbits'],
                            r['message'], r['raw'], '★ 推荐' if i == 1 else ''
                        ])
                
                messagebox.showinfo("导出成功", 
                    f"完整日志: {filepath}\n成功摘要: {summary_path}")
            else:
                messagebox.showinfo("导出成功", f"文件已保存: {filepath}")
                
        except Exception as e:
            messagebox.showerror("导出失败", str(e))
    
    def clear_log(self):
        self.log_text.delete(1.0, 'end')
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.all_results = []
        self.success_results = []
        self.export_btn.config(state='disabled')
        self.status_var.set("已清空")
    
    def on_closing(self):
        self.close_serial()
        self.root.destroy()


def main():
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')
    
    app = MeterScannerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    app.log_text.tag_config('success', foreground='green')
    app.log_text.tag_config('fail', foreground='red')
    app.log_text.tag_config('info', foreground='blue')
    app.log_text.tag_config('trying', foreground='gray')
    
    root.mainloop()


if __name__ == '__main__':
    main()
