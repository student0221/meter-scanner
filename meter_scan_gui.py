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
        self.root.geometry("900x700")
        self.root.minsize(900, 700)
        
        self.all_results = []
        self.success_results = []
        self.is_scanning = False
        self.scan_thread = None
        self.ser = None  # 复用串口
        
        self.build_ui()
        self.refresh_ports()
    
    def build_ui(self):
        # ===== 串口选择 =====
        port_frame = ttk.Frame(self.root)
        port_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(port_frame, text="串口:").pack(side='left')
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=25)
        self.port_combo.pack(side='left', padx=5)
        ttk.Button(port_frame, text="刷新", command=self.refresh_ports, width=6).pack(side='left', padx=3)
        
        self.serial_status_var = tk.StringVar(value="串口: 未打开")
        ttk.Label(port_frame, textvariable=self.serial_status_var, foreground='gray').pack(side='left', padx=(15, 0))
        
        # ===== 通信日志 =====
        log_frame = ttk.LabelFrame(self.root, text="通信日志", padding=5)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap='word', font=('Consolas', 10))
        self.log_text.pack(fill='both', expand=True)
        
        # ===== 自动探测区 =====
        scan_frame = ttk.LabelFrame(self.root, text="自动探测", padding=10)
        scan_frame.pack(fill='x', padx=10, pady=5)
        
        # 波特率
        ttk.Label(scan_frame, text="波特率:").grid(row=0, column=0, sticky='w')
        self.baud_frame = ttk.Frame(scan_frame)
        self.baud_frame.grid(row=0, column=1, columnspan=4, sticky='w', padx=5)
        self.baud_vars = {}
        for baud in [1200, 2400, 4800, 7200, 9600, 19200, 38400, 57600, 115200]:
            var = tk.BooleanVar(value=True)
            self.baud_vars[baud] = var
            ttk.Checkbutton(self.baud_frame, text=str(baud), variable=var).pack(side='left', padx=3)
        
        # 基础参数
        ttk.Label(scan_frame, text="数据位:").grid(row=1, column=0, sticky='w', pady=5)
        self.data_var = tk.StringVar(value="8")
        ttk.Combobox(scan_frame, textvariable=self.data_var, values=["7", "8"], width=5).grid(row=1, column=1, sticky='w', padx=5)
        
        ttk.Label(scan_frame, text="校验位:").grid(row=1, column=2, sticky='w', padx=(15, 0))
        self.parity_var = tk.StringVar(value="E")
        ttk.Combobox(scan_frame, textvariable=self.parity_var, values=["N", "E", "O"], width=5).grid(row=1, column=3, sticky='w', padx=5)
        
        ttk.Label(scan_frame, text="停止位:").grid(row=1, column=4, sticky='w', padx=(15, 0))
        self.stop_var = tk.StringVar(value="1")
        ttk.Combobox(scan_frame, textvariable=self.stop_var, values=["1", "2"], width=5).grid(row=1, column=5, sticky='w', padx=5)
        
        # 超时 + 唤醒
        ttk.Label(scan_frame, text="等待超时(ms):").grid(row=2, column=0, sticky='w', pady=5)
        self.timeout_var = tk.StringVar(value="1500")
        ttk.Entry(scan_frame, textvariable=self.timeout_var, width=10).grid(row=2, column=1, sticky='w', padx=5)
        
        self.wakeup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(scan_frame, text="先发唤醒 FE", variable=self.wakeup_var).grid(row=2, column=2, columnspan=2, sticky='w', padx=5)
        
        # 串口开关 + 探测按钮
        btn_frame = ttk.Frame(scan_frame)
        btn_frame.grid(row=3, column=0, columnspan=6, sticky='w', pady=5)
        
        self.open_btn = ttk.Button(btn_frame, text="🔌 打开串口", command=self.open_serial, width=12)
        self.open_btn.pack(side='left', padx=5)
        
        self.close_btn = ttk.Button(btn_frame, text="🔒 关闭串口", command=self.close_serial, width=12, state='disabled')
        self.close_btn.pack(side='left', padx=5)
        
        self.scan_btn = ttk.Button(btn_frame, text="▶ 开始探测", command=self.start_scan, width=12)
        self.scan_btn.pack(side='left', padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止", command=self.stop_scan, width=12, state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        self.export_btn = ttk.Button(btn_frame, text="📄 导出 CSV", command=self.export_csv, width=12, state='disabled')
        self.export_btn.pack(side='left', padx=5)
        
        ttk.Button(btn_frame, text="🗑 清空", command=self.clear_log, width=8).pack(side='left', padx=5)
        
        # ===== 进度 =====
        self.progress = ttk.Progressbar(self.root, mode='determinate')
        self.progress.pack(fill='x', padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="就绪 | 先打开串口，再开始探测")
        ttk.Label(self.root, textvariable=self.status_var).pack(anchor='w', padx=10)
        
        # ===== 结果 =====
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
            self.ser = serial.Serial(
                port=port,
                baudrate=9600,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5,
                write_timeout=1
            )
            self.serial_status_var.set(f"串口: 已打开 | {port}")
            self.open_btn.config(state='disabled')
            self.close_btn.config(state='normal')
            self.log(f"串口已打开: {port}", 'info')
        except Exception as e:
            messagebox.showerror("错误", f"打开串口失败: {e}")
    
    def close_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.serial_status_var.set("串口: 已关闭")
        self.open_btn.config(state='normal')
        self.close_btn.config(state='disabled')
        self.log("串口已关闭", 'info')
    
    def strip_fe_prefix(self, data):
        i = 0
        while i < len(data) and data[i] == 0xFE:
            i += 1
        return data[i:]
    
    def calc_checksum(self, data):
        return sum(data) & 0xFF
    
    def build_read_addr_frame(self):
        frame = bytearray([0x68, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0x68, 0x13, 0x00])
        frame.append(self.calc_checksum(frame))
        frame.append(0x16)
        return bytes(frame)
    
    def try_params(self, baud, databits, parity, stopbits, timeout_ms):
        """使用已打开的串口尝试一组参数，动态重配置"""
        if not self.ser or not self.ser.is_open:
            return False, "串口未打开", b''
        
        try:
            # 动态重配置串口参数
            self.ser.baudrate = baud
            self.ser.bytesize = databits
            self.ser.parity = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}[parity]
            self.ser.stopbits = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}[stopbits]
            self.ser.timeout = timeout_ms / 1000.0
            
            # 清空缓冲区
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.05)  # 参数切换后稍等
            
            # 发送唤醒
            if self.wakeup_var.get():
                self.ser.write(bytes([0xFE, 0xFE, 0xFE, 0xFE]))
                time.sleep(0.1)
            
            # 发送读地址报文
            self.ser.write(self.build_read_addr_frame())
            self.ser.flush()
            
            # 读取回复
            response = b''
            deadline = time.time() + (timeout_ms / 1000.0)
            while time.time() < deadline:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting)
                    response += chunk
                    if 0x16 in chunk:
                        break
                time.sleep(0.05)
            
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
        if not self.ser or not self.ser.is_open:
            self.log("错误: 串口未打开，请先点击【打开串口】", 'fail')
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
                        
                        ok, msg, raw = self.try_params(baud, databit, parity, stopbit, timeout_ms)
                        
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
