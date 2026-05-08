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
        self.root.minsize(800, 600)
        
        # 数据存储
        self.all_results = []
        self.success_results = []
        self.is_scanning = False
        self.scan_thread = None
        
        self.build_ui()
        self.refresh_ports()
    
    def build_ui(self):
        # ===== 顶部配置区 =====
        config_frame = ttk.LabelFrame(self.root, text="串口配置", padding=10)
        config_frame.pack(fill='x', padx=10, pady=5)
        
        # 串口选择
        ttk.Label(config_frame, text="串口:").grid(row=0, column=0, sticky='w')
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(config_frame, textvariable=self.port_var, width=20)
        self.port_combo.grid(row=0, column=1, padx=5)
        ttk.Button(config_frame, text="刷新", command=self.refresh_ports, width=8).grid(row=0, column=2, padx=5)
        
        # 参数范围设置
        ttk.Label(config_frame, text="波特率:").grid(row=1, column=0, sticky='w', pady=5)
        self.baud_frame = ttk.Frame(config_frame)
        self.baud_frame.grid(row=1, column=1, columnspan=2, sticky='w')
        self.baud_vars = {}
        for i, baud in enumerate([1200, 2400, 4800, 7200, 9600, 19200, 38400, 57600, 115200]):
            var = tk.BooleanVar(value=True)
            self.baud_vars[baud] = var
            ttk.Checkbutton(self.baud_frame, text=str(baud), variable=var).pack(side='left', padx=3)
        
        ttk.Label(config_frame, text="数据位:").grid(row=2, column=0, sticky='w', pady=5)
        self.data_var = tk.StringVar(value="8")
        ttk.Radiobutton(config_frame, text="7", variable=self.data_var, value="7").grid(row=2, column=1, sticky='w')
        ttk.Radiobutton(config_frame, text="8", variable=self.data_var, value="8").grid(row=2, column=1, padx=50, sticky='w')
        
        ttk.Label(config_frame, text="校验位:").grid(row=3, column=0, sticky='w', pady=5)
        self.parity_frame = ttk.Frame(config_frame)
        self.parity_frame.grid(row=3, column=1, columnspan=2, sticky='w')
        self.parity_vars = {}
        for p, label in [('N', 'None'), ('E', 'Even'), ('O', 'Odd')]:
            var = tk.BooleanVar(value=True)
            self.parity_vars[p] = var
            ttk.Checkbutton(self.parity_frame, text=label, variable=var).pack(side='left', padx=5)
        
        ttk.Label(config_frame, text="停止位:").grid(row=4, column=0, sticky='w', pady=5)
        self.stop_var = tk.StringVar(value="1")
        ttk.Radiobutton(config_frame, text="1", variable=self.stop_var, value="1").grid(row=4, column=1, sticky='w')
        ttk.Radiobutton(config_frame, text="2", variable=self.stop_var, value="2").grid(row=4, column=1, padx=50, sticky='w')
        
        ttk.Label(config_frame, text="等待超时(ms):").grid(row=6, column=0, sticky='w', pady=5)
        self.timeout_var = tk.StringVar(value="1500")
        self.timeout_entry = ttk.Entry(config_frame, textvariable=self.timeout_var, width=10)
        self.timeout_entry.grid(row=6, column=1, sticky='w', padx=5)
        ttk.Label(config_frame, text="发完报文后等待应答的时间，超时则切换下一组参数").grid(row=6, column=2, sticky='w')
        
        # 唤醒选项
        self.wakeup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(config_frame, text="发送唤醒字节 (FE FE FE FE)", variable=self.wakeup_var).grid(row=7, column=0, columnspan=3, sticky='w', pady=5)
        
        # ===== 按钮区 =====
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        self.scan_btn = ttk.Button(btn_frame, text="▶ 开始探测", command=self.start_scan, width=15)
        self.scan_btn.pack(side='left', padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止", command=self.stop_scan, width=15, state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        # CSV 导出按钮
        self.export_btn = ttk.Button(btn_frame, text="📄 导出 CSV", command=self.export_csv, width=15, state='disabled')
        self.export_btn.pack(side='left', padx=5)
        
        ttk.Button(btn_frame, text="🗑 清空日志", command=self.clear_log, width=15).pack(side='right', padx=5)
        
        # ===== 进度条 =====
        self.progress = ttk.Progressbar(self.root, mode='determinate')
        self.progress.pack(fill='x', padx=10, pady=5)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var).pack(anchor='w', padx=10)
        
        # ===== 日志显示区 =====
        log_frame = ttk.LabelFrame(self.root, text="探测日志", padding=5)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap='word', font=('Consolas', 10))
        self.log_text.pack(fill='both', expand=True)
        
        # ===== 结果汇总区 =====
        result_frame = ttk.LabelFrame(self.root, text="成功结果", padding=5)
        result_frame.pack(fill='x', padx=10, pady=5)
        
        self.result_tree = ttk.Treeview(result_frame, columns=('params', 'address', 'raw'), show='headings', height=4)
        self.result_tree.heading('params', text='通信参数')
        self.result_tree.heading('address', text='电表地址/结果')
        self.result_tree.heading('raw', text='原始报文')
        self.result_tree.column('params', width=150)
        self.result_tree.column('address', width=250)
        self.result_tree.column('raw', width=400)
        self.result_tree.pack(fill='x')
    
    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [f"{p.device} - {p.description[:30]}" for p in ports]
        self.port_combo['values'] = port_list
        if port_list:
            self.port_combo.set(port_list[0])
    
    def log(self, msg, tag=''):
        self.log_text.insert('end', msg + '\n', tag)
        self.log_text.see('end')
        self.root.update_idletasks()
    
    def calc_checksum(self, data):
        return sum(data) & 0xFF
    
    def build_frame(self):
        frame = bytearray([
            0x68, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0x68, 0x13, 0x00
        ])
        frame.append(self.calc_checksum(frame))
        frame.append(0x16)
        return bytes(frame)
    
    def try_once(self, port, baud, databits, parity, stopbits):
        try:
            # 使用用户设置的超时时间（毫秒转秒）
            timeout_ms = int(self.timeout_var.get() or 1500)
            timeout_sec = timeout_ms / 1000.0
            
            ser = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=databits,
                parity={'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}[parity],
                stopbits={1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}[stopbits],
                timeout=timeout_sec,
                write_timeout=1
            )
            
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            if self.wakeup_var.get():
                ser.write(bytes([0xFE, 0xFE, 0xFE, 0xFE]))
                time.sleep(0.1)
            
            ser.write(self.build_frame())
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
            
            if len(response) >= 12 and response[0] == 0x68 and response[7] == 0x68 and response[-1] == 0x16:
                cs = self.calc_checksum(response[:-2])
                if cs == response[-2]:
                    ctrl = response[8]
                    if ctrl == 0x93:
                        addr = response[10:16].hex().upper() if len(response) > 15 else ''
                        return True, f"地址: {addr}", response
                    elif ctrl == 0xD1:
                        return True, f"异常应答", response
            
            return False, f"无有效应答 (超时{timeout_ms}ms)" if len(response) == 0 else "帧格式错误", response
            
        except Exception as e:
            return False, str(e), b''
    
    def scan_worker(self):
        port_full = self.port_var.get()
        port = port_full.split(' - ')[0] if ' - ' in port_full else port_full
        
        baudrates = [b for b, v in self.baud_vars.items() if v.get()]
        databits = [int(self.data_var.get())]
        parities = [p for p, v in self.parity_vars.items() if v.get()]
        stopbits = [int(self.stop_var.get())]
        
        total = len(baudrates) * len(databits) * len(parities) * len(stopbits)
        count = 0
        
        self.all_results = []
        self.success_results = []
        
        # 清空树形结果
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
                        self.log(f"[{count}/{total}] {params} ...", 'trying')
                        
                        ok, msg, raw = self.try_once(port, baud, databit, parity, stopbit)
                        
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
                            
                            # 添加到树形控件
                            self.result_tree.insert('', 'end', values=(
                                params,
                                msg,
                                raw.hex().upper()
                            ))
                        else:
                            self.log(f"  ❌ {msg}", 'fail')
                        
                        time.sleep(0.3)
        
        # 扫描结束
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
        
        # 选择保存路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"meter_scan_{timestamp}.csv"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            initialfile=default_name,
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
            
            # 同时导出成功结果摘要
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


def main():
    root = tk.Tk()
    # 设置主题
    style = ttk.Style()
    style.theme_use('clam')
    
    # 配置标签颜色
    app = MeterScannerGUI(root)
    
    # 配置日志标签颜色
    app.log_text.tag_config('success', foreground='green')
    app.log_text.tag_config('fail', foreground='red')
    app.log_text.tag_config('info', foreground='blue')
    app.log_text.tag_config('trying', foreground='gray')
    
    root.mainloop()

if __name__ == '__main__':
    main()
