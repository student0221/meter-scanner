"""
DL/T 645-2007 电表通信参数探测工具 — GUI 界面

基于 tkinter 的现代化操作界面。
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading

from ..scanner import MeterScanner
from ..protocol import BAUDRATES, DATABITS, PARITIES, STOPBITS


class ModernMeterScannerGUI:
    """电表通信参数探测工具 GUI"""

    # 配色方案
    C = {
        'bg':           '#1a1a2e',
        'card':         '#16213e',
        'card_light':   '#1e2a4a',
        'accent':       '#e94560',
        'accent_hover': '#c73d55',
        'text':         '#eaeaea',
        'text_sec':     '#a0a0a0',
        'text_dim':     '#6a6a8a',
        'success':      '#00d9a6',
        'warning':      '#ffc107',
        'error':        '#ff4757',
        'border':       '#2a2a4a',
        'input_bg':     '#0f0f23',
    }

    def __init__(self, root):
        self.root = root
        self.root.title("DL/T 645-2007 电表通信参数探测工具")
        self.root.geometry("1100x850")
        self.root.minsize(1000, 750)
        self.root.configure(bg=self.C['bg'])

        # DPI 感知
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.scanner: MeterScanner | None = None
        self._build_styles()
        self._build_ui()
        self._refresh_ports()

    # ─── 样式 ───────────────────────────────────────────

    def _build_styles(self):
        s = ttk.Style()
        s.theme_use('clam')

        s.configure('.', background=self.C['bg'], foreground=self.C['text'],
                     fieldbackground=self.C['input_bg'], font=('Microsoft YaHei', 10))
        s.configure('TLabel', background=self.C['bg'], foreground=self.C['text_sec'],
                     font=('Microsoft YaHei', 9))
        s.configure('Card.TLabelframe', background=self.C['card'], foreground=self.C['text'],
                     borderwidth=1, relief='solid', font=('Microsoft YaHei', 10, 'bold'))
        s.configure('Card.TLabelframe.Label', background=self.C['card'],
                     foreground=self.C['accent'], font=('Microsoft YaHei', 11, 'bold'))
        s.configure('Accent.TButton', background=self.C['accent'], foreground='#fff',
                     font=('Microsoft YaHei', 10, 'bold'), padding=(20, 8), relief='flat')
        s.map('Accent.TButton',
               background=[('active', self.C['accent_hover']), ('pressed', self.C['accent_hover'])])
        s.configure('Secondary.TButton', background='#2a2a5a', foreground=self.C['text'],
                     font=('Microsoft YaHei', 10), padding=(15, 6), relief='flat')
        s.map('Secondary.TButton', background=[('active', '#3a3a6a')])
        s.configure('TCombobox', fieldbackground=self.C['input_bg'], background=self.C['card'],
                     foreground=self.C['text'], arrowcolor=self.C['accent'], padding=5)
        s.configure('Horizontal.TProgressbar', background=self.C['accent'],
                     troughcolor=self.C['input_bg'], borderwidth=0)
        s.configure('Custom.Treeview', background=self.C['card'], foreground=self.C['text'],
                     fieldbackground=self.C['card'], rowheight=28, font=('Consolas', 10))
        s.configure('Custom.Treeview.Heading', background=self.C['card_light'],
                     foreground=self.C['accent'], font=('Microsoft YaHei', 10, 'bold'), relief='flat')
        s.map('Custom.Treeview', background=[('selected', self.C['accent_hover'])],
               foreground=[('selected', '#ffffff')])

    # ─── UI 构建 ────────────────────────────────────────

    def _build_ui(self):
        main = tk.Frame(self.root, bg=self.C['bg'])
        main.pack(fill='both', expand=True, padx=15, pady=15)

        # ── 标题 ──
        header = tk.Frame(main, bg=self.C['bg'])
        header.pack(fill='x', pady=(0, 15))

        tk.Label(header, text="⚡", font=('Segoe UI', 24),
                 bg=self.C['bg'], fg=self.C['accent']).pack(side='left')

        tf = tk.Frame(header, bg=self.C['bg'])
        tf.pack(side='left', padx=(10, 0))
        tk.Label(tf, text="DL/T 645-2007", font=('Microsoft YaHei', 16, 'bold'),
                 bg=self.C['bg'], fg=self.C['text']).pack(anchor='w')
        tk.Label(tf, text="电表通信参数探测工具", font=('Microsoft YaHei', 11),
                 bg=self.C['bg'], fg=self.C['text_sec']).pack(anchor='w')

        self.status_dot = tk.Canvas(header, width=12, height=12,
                                     bg=self.C['bg'], highlightthickness=0)
        self.status_dot.pack(side='right', padx=5)
        self._draw_dot('gray')

        self.status_lbl = tk.Label(header, text="串口未连接", font=('Microsoft YaHei', 10),
                                    bg=self.C['bg'], fg=self.C['text_dim'])
        self.status_lbl.pack(side='right')

        # ── 串口配置卡片 ──
        port_card = self._card(main, "串口配置")
        port_card.pack(fill='x', pady=(0, 10))
        pi = tk.Frame(port_card, bg=self.C['card'])
        pi.pack(fill='x')

        tk.Label(pi, text="串口", font=('Microsoft YaHei', 10),
                 bg=self.C['card'], fg=self.C['text_sec']).grid(row=0, column=0, sticky='w')
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(pi, textvariable=self.port_var, width=18,
                                        font=('Consolas', 10))
        self.port_combo.grid(row=0, column=1, padx=(8, 15), sticky='w')

        ttk.Button(pi, text="🔄 刷新", command=self._refresh_ports,
                   style='Secondary.TButton', width=10).grid(row=0, column=2, padx=(0, 15))

        self.open_btn = tk.Button(pi, text="🔌 打开串口", font=('Microsoft YaHei', 10, 'bold'),
                                   bg=self.C['success'], fg='#fff', activebackground='#00b894',
                                   relief='flat', padx=20, pady=6, cursor='hand2',
                                   command=self._open_serial)
        self.open_btn.grid(row=0, column=3, padx=(0, 8))

        self.close_btn = tk.Button(pi, text="🔒 关闭串口", font=('Microsoft YaHei', 10),
                                    bg='#2a2a5a', fg=self.C['text'], activebackground='#3a3a6a',
                                    relief='flat', padx=20, pady=6, cursor='hand2',
                                    command=self._close_serial, state='disabled')
        self.close_btn.grid(row=0, column=4)

        # ── 自定义报文卡片 ──
        custom_card = self._card(main, "自定义报文")
        custom_card.pack(fill='x', pady=(0, 10))

        ci = tk.Frame(custom_card, bg=self.C['card'])
        ci.pack(fill='x')

        tk.Label(ci, text="报文内容", font=('Microsoft YaHei', 10),
                 bg=self.C['card'], fg=self.C['text_sec']).grid(row=0, column=0, sticky='nw')

        self.custom_frame_text = scrolledtext.ScrolledText(
            ci, wrap='word', height=3, font=('Consolas', 10),
            bg=self.C['input_bg'], fg=self.C['text'], relief='solid', borderwidth=1,
            highlightbackground=self.C['border'], highlightcolor=self.C['accent'],
            padx=8, pady=5)
        self.custom_frame_text.grid(row=0, column=1, sticky='ew', padx=(8, 0), pady=3)
        ci.columnconfigure(1, weight=1)
        self.custom_frame_text.insert('1.0', '68 AA AA AA AA AA AA 68 13 00 DF 16')

        opt_frame = tk.Frame(ci, bg=self.C['card'])
        opt_frame.grid(row=1, column=1, sticky='w', padx=(8, 0), pady=(5, 0))

        self.hex_send_var = tk.BooleanVar(value=True)
        self._check(opt_frame, "十六进制发送（空格分隔）", self.hex_send_var).pack(side='left', padx=(0, 15))

        self.log_all_rx_var = tk.BooleanVar(value=True)
        self._check(opt_frame, "记录所有回复（含失败）", self.log_all_rx_var).pack(side='left', padx=(0, 15))

        tk.Label(opt_frame, text="留空则使用默认读地址报文", font=('Microsoft YaHei', 9),
                 bg=self.C['card'], fg=self.C['text_dim']).pack(side='left')

        # ── 自动探测卡片 ──
        scan_card = self._card(main, "自动探测")
        scan_card.pack(fill='x', pady=(0, 10))
        si = tk.Frame(scan_card, bg=self.C['card'])
        si.pack(fill='x')

        self._option_row(si, 0, "波特率", self._baud_checks)
        self._option_row(si, 1, "数据位", self._data_checks)
        self._option_row(si, 2, "校验位", self._parity_checks)
        self._option_row(si, 3, "停止位", self._stop_checks)

        # 超时
        tk.Label(si, text="等待超时", font=('Microsoft YaHei', 10),
                 bg=self.C['card'], fg=self.C['text_sec']).grid(row=4, column=0, sticky='w', pady=(8, 0))
        tf2 = tk.Frame(si, bg=self.C['card'])
        tf2.grid(row=4, column=1, sticky='w', pady=(8, 0), padx=(8, 0))

        self.timeout_var = tk.StringVar(value="1500")
        tk.Entry(tf2, textvariable=self.timeout_var, width=8, font=('Consolas', 11),
                 bg=self.C['input_bg'], fg=self.C['text'], relief='solid', borderwidth=1,
                 highlightbackground=self.C['border'], highlightcolor=self.C['accent'],
                 justify='center').pack(side='left')
        tk.Label(tf2, text="ms", font=('Microsoft YaHei', 10),
                 bg=self.C['card'], fg=self.C['text_dim']).pack(side='left', padx=(5, 20))

        self.wakeup_var = tk.BooleanVar(value=True)
        self._check(tf2, "先发唤醒 FE", self.wakeup_var).pack(side='left', padx=(15, 0))

        # 按钮行
        btn_row = tk.Frame(si, bg=self.C['card'])
        btn_row.grid(row=5, column=0, columnspan=6, sticky='w', pady=(15, 5))

        self.scan_btn = tk.Button(btn_row, text="▶ 开始探测", font=('Microsoft YaHei', 11, 'bold'),
                                   bg=self.C['accent'], fg='#fff', activebackground=self.C['accent_hover'],
                                   relief='flat', padx=30, pady=8, cursor='hand2',
                                   command=self._start_scan)
        self.scan_btn.pack(side='left', padx=(0, 10))

        self.stop_btn = tk.Button(btn_row, text="⏹ 停止", font=('Microsoft YaHei', 11),
                                   bg='#2a2a5a', fg=self.C['text'], activebackground='#3a3a6a',
                                   relief='flat', padx=25, pady=8, cursor='hand2',
                                   command=self._stop_scan, state='disabled')
        self.stop_btn.pack(side='left', padx=(0, 10))

        self.export_btn = tk.Button(btn_row, text="📄 导出 CSV", font=('Microsoft YaHei', 11),
                                     bg='#2a2a5a', fg=self.C['text'], activebackground='#3a3a6a',
                                     relief='flat', padx=25, pady=8, cursor='hand2',
                                     command=self._export_csv, state='disabled')
        self.export_btn.pack(side='left', padx=(0, 10))

        tk.Button(btn_row, text="🗑 清空日志", font=('Microsoft YaHei', 10),
                  bg=self.C['card'], fg=self.C['text_dim'], activebackground=self.C['card_light'],
                  relief='flat', padx=15, pady=6, cursor='hand2',
                  command=self._clear_log).pack(side='left')

        # ── 进度条 ──
        pf = tk.Frame(main, bg=self.C['bg'])
        pf.pack(fill='x', pady=(0, 8))
        self.progress = ttk.Progressbar(pf, mode='determinate', style='Horizontal.TProgressbar')
        self.progress.pack(fill='x')
        self.status_var = tk.StringVar(value="就绪 | 先打开串口，再开始探测")
        tk.Label(pf, textvariable=self.status_var, font=('Microsoft YaHei', 10),
                 bg=self.C['bg'], fg=self.C['text_sec']).pack(anchor='w', pady=(5, 0))

        # ── 日志 + 结果 ──
        cf = tk.Frame(main, bg=self.C['bg'])
        cf.pack(fill='both', expand=True)
        cf.columnconfigure(0, weight=1)
        cf.columnconfigure(1, weight=1)
        cf.rowconfigure(0, weight=1)

        # 日志
        log_card = self._card(cf, "通信日志")
        log_card.grid(row=0, column=0, sticky='nsew', padx=(0, 8))

        self.log_text = scrolledtext.ScrolledText(log_card, wrap='word', font=('Consolas', 10),
                                                   bg=self.C['input_bg'], fg=self.C['text'],
                                                   relief='flat', padx=8, pady=8,
                                                   selectbackground=self.C['accent'],
                                                   selectforeground='#fff')
        self.log_text.pack(fill='both', expand=True)
        for tag, color in [('trying', self.C['text_sec']),
                           ('success', self.C['success']),
                           ('fail', self.C['error']),
                           ('tx', '#6bb9ff'), ('rx', '#f9ca24')]:
            self.log_text.tag_configure(tag, foreground=color)
        self.log_text.tag_configure('success', font=('Consolas', 10, 'bold'))

        # 结果
        res_card = self._card(cf, "探测成功结果")
        res_card.grid(row=0, column=1, sticky='nsew')

        self.result_tree = ttk.Treeview(res_card, columns=('params', 'address', 'raw'),
                                         show='headings', height=15, style='Custom.Treeview')
        self.result_tree.heading('params', text='通信参数')
        self.result_tree.heading('address', text='地址')
        self.result_tree.heading('raw', text='原始报文')
        self.result_tree.column('params', width=140, anchor='center')
        self.result_tree.column('address', width=200, anchor='center')
        self.result_tree.column('raw', width=250, anchor='w')
        self.result_tree.pack(fill='both', expand=True)
        self.result_tree.bind('<Double-1>', self._copy_row)

        self.stats_var = tk.StringVar(value="成功: 0 | 总计: 0")
        tk.Label(res_card, textvariable=self.stats_var, font=('Microsoft YaHei', 10),
                 bg=self.C['card'], fg=self.C['text_sec']).pack(anchor='e', pady=(5, 0))

    # ─── 辅助构建 ───────────────────────────────────────

    def _card(self, parent, title):
        f = tk.LabelFrame(parent, text=f" {title} ", bg=self.C['card'], fg=self.C['accent'],
                           font=('Microsoft YaHei', 11, 'bold'), padx=15, pady=12,
                           relief='solid', borderwidth=1)
        return f

    def _option_row(self, parent, row, label, build_fn):
        tk.Label(parent, text=label, font=('Microsoft YaHei', 10),
                 bg=self.C['card'], fg=self.C['text_sec']).grid(row=row, column=0, sticky='nw', pady=3)
        f = tk.Frame(parent, bg=self.C['card'])
        f.grid(row=row, column=1, sticky='w', padx=(8, 0), pady=3)
        build_fn(f)

    def _baud_checks(self, parent):
        self.baud_vars = {}
        for b in BAUDRATES:
            v = tk.BooleanVar(value=True)
            self.baud_vars[b] = v
            self._check(parent, str(b), v).pack(side='left', padx=4)

    def _data_checks(self, parent):
        self.data_vars = {}
        for d in DATABITS:
            v = tk.BooleanVar(value=(d == 8))
            self.data_vars[d] = v
            self._check(parent, str(d), v).pack(side='left', padx=8)

    def _parity_checks(self, parent):
        self.parity_vars = {}
        for p, lbl in [('N', 'None'), ('E', 'Even'), ('O', 'Odd')]:
            v = tk.BooleanVar(value=(p == 'E'))
            self.parity_vars[p] = v
            self._check(parent, lbl, v).pack(side='left', padx=8)

    def _stop_checks(self, parent):
        self.stop_vars = {}
        for s in STOPBITS:
            v = tk.BooleanVar(value=(s == 1))
            self.stop_vars[s] = v
            self._check(parent, str(s), v).pack(side='left', padx=8)

    def _check(self, parent, text, var):
        cb = tk.Checkbutton(parent, text=text, variable=var,
                             bg=self.C['card'], activebackground=self.C['card_light'],
                             selectcolor=self.C['card'], fg=self.C['text_dim'],
                             activeforeground=self.C['text'], font=('Microsoft YaHei', 10),
                             cursor='hand2', highlightthickness=0)
        def _upd(*_a):
            cb.config(fg=self.C['accent'] if var.get() else self.C['text_dim'])
        var.trace_add('write', _upd)
        return cb

    def _draw_dot(self, color):
        self.status_dot.delete('all')
        self.status_dot.create_oval(1, 1, 11, 11, fill=color, outline='')

    # ─── 串口操作 ───────────────────────────────────────

    def _refresh_ports(self):
        import serial.tools.list_ports
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_var.set(ports[0])
            self._log(f"发现串口: {', '.join(ports)}")
        else:
            self.port_var.set('')
            self._log("未检测到串口", 'fail')

    def _open_serial(self):
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("提示", "请先选择串口")
            return
        try:
            self.scanner = MeterScanner(port)
            self.scanner.open_port()
            self.open_btn.config(state='disabled')
            self.close_btn.config(state='normal')
            self._draw_dot(self.C['success'])
            self.status_lbl.config(text=f"已连接 | {port}", fg=self.C['success'])
        except Exception as e:
            self._log(f"打开串口失败: {e}", 'fail')

    def _close_serial(self):
        if self.scanner:
            self.scanner.close_port()
            self.scanner = None
        self.open_btn.config(state='normal')
        self.close_btn.config(state='disabled')
        self._draw_dot('gray')
        self.status_lbl.config(text="串口未连接", fg=self.C['text_dim'])

    # ─── 扫描 ───────────────────────────────────────────

    def _start_scan(self):
        if not self.scanner or not self.scanner.is_open:
            messagebox.showwarning("提示", "请先打开串口")
            return

        bauds = [b for b, v in self.baud_vars.items() if v.get()]
        datas = [d for d, v in self.data_vars.items() if v.get()]
        pars = [p for p, v in self.parity_vars.items() if v.get()]
        stops = [s for s, v in self.stop_vars.items() if v.get()]

        if not all([bauds, datas, pars, stops]):
            messagebox.showwarning("提示", "请至少勾选一种波特率/数据位/校验位/停止位")
            return

        try:
            timeout = int(self.timeout_var.get() or 1500)
        except ValueError:
            timeout = 1500

        self.scanner.baudrates = bauds
        self.scanner.databits = datas
        self.scanner.parities = pars
        self.scanner.stopbits = stops
        self.scanner.timeout_ms = timeout
        self.scanner.send_wakeup = self.wakeup_var.get()
        self.scanner.custom_frame = self._parse_custom_frame()
        self.scanner.log_all_rx = self.log_all_rx_var.get()

        self.result_tree.delete(*self.result_tree.get_children())
        self.scan_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.export_btn.config(state='disabled')

        self.scanner.on_log = lambda msg, lvl: self.root.after(0, self._log, msg, lvl)
        self.scanner.on_result = lambda r: self.root.after(0, self._on_result, r)

        self.scanner.start_scan()

        # 监控扫描结束
        self._poll_scan_done()

    def _poll_scan_done(self):
        if self.scanner and self.scanner.is_scanning:
            self.root.after(200, self._poll_scan_done)
        else:
            self.scan_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            if self.scanner and self.scanner.success_results:
                self.export_btn.config(state='normal')
            total = len(self.scanner.all_results) if self.scanner else 0
            suc = len(self.scanner.success_results) if self.scanner else 0
            self.status_var.set(f"探测完成 | 成功 {suc}/{total}")
            self.progress.configure(value=100)

    def _stop_scan(self):
        if self.scanner:
            self.scanner.stop_scan()

    def _on_result(self, result):
        total = len(self.scanner.all_results)
        suc = len(self.scanner.success_results)
        self.progress.configure(value=0)  # will be updated by poll
        self.stats_var.set(f"成功: {suc} | 总计: {total}")
        if result['success']:
            display = result.get('addr') or result['message']
            self.result_tree.insert('', 'end',
                values=(f"{result['baud']}/{result['databits']}-{result['parity']}-{result['stopbits']}",
                        display, result['raw']))
        elif self.log_all_rx_var.get() and result['raw']:
            display = f"[{result['message']}]"
            self.result_tree.insert('', 'end',
                values=(f"{result['baud']}/{result['databits']}-{result['parity']}-{result['stopbits']}",
                        display, result['raw']))

    # ─── 导出 ───────────────────────────────────────────

    def _export_csv(self):
        if not self.scanner or not self.scanner.all_results:
            return
        path = filedialog.asksaveasfilename(
            title="保存 CSV", defaultextension=".csv",
            initialfile="meter_scan_results.csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if path:
            import csv
            from datetime import datetime
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f)
                w.writerow(['序号', '波特率', '数据位', '校验位', '停止位',
                            '结果', '详情', '地址', '原始报文', '时间戳'])
                for i, r in enumerate(self.scanner.all_results, 1):
                    w.writerow([i, r['baud'], r['databits'], r['parity'], r['stopbits'],
                                '成功' if r['success'] else '失败', r['message'],
                                r.get('addr', ''), r['raw'], r['timestamp']])
            self._log(f"已导出: {path}", 'success')

    # ─── 日志 / 工具 ────────────────────────────────────

    def _log(self, msg, tag=''):
        self.log_text.insert('end', f"{msg}\n", tag)
        self.log_text.see('end')

    def _parse_custom_frame(self):
        """解析自定义报文输入为 bytes，留空返回 None（使用默认报文）。"""
        text = self.custom_frame_text.get('1.0', 'end').strip()
        if not text:
            return None
        if self.hex_send_var.get():
            cleaned = text.replace(' ', '').replace(',', '').replace(';', '').replace('\n', '').replace('\t', '').replace('0x', '').replace('0X', '')
            try:
                return bytes(int(cleaned[i:i+2], 16) for i in range(0, len(cleaned), 2) if i+2 <= len(cleaned))
            except ValueError:
                self._log("自定义报文解析失败，使用默认报文", 'fail')
                return None
        else:
            return text.encode('utf-8')

    def _clear_log(self):
        self.log_text.delete('1.0', 'end')

    def _copy_row(self, _event):
        sel = self.result_tree.selection()
        if sel:
            vals = self.result_tree.item(sel[0], 'values')
            if vals:
                text = f"{vals[0]} | {vals[1]} | {vals[2]}"
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self._log(f"已复制: {text}", 'success')


def main():
    root = tk.Tk()
    ModernMeterScannerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
