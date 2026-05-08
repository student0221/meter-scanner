import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime


class ModernMeterScannerGUI:
    """DL/T 645-2007 电表通信参数探测工具 — 现代化 UI 版本"""
    
    # 配色方案
    COLORS = {
        'bg': '#1a1a2e',
        'card_bg': '#16213e',
        'card_bg_light': '#1e2a4a',
        'accent': '#e94560',
        'accent_hover': '#c73d55',
        'text': '#eaeaea',
        'text_secondary': '#a0a0a0',
        'text_dim': '#6a6a8a',
        'success': '#00d9a6',
        'warning': '#ffc107',
        'error': '#ff4757',
        'border': '#2a2a4a',
        'input_bg': '#0f0f23',
        'button_bg': '#e94560',
        'button_secondary': '#2a2a5a',
        'progress_bg': '#0f0f23',
        'progress_fg': '#e94560',
    }
    
    def __init__(self, root):
        self.root = root
        self.root.title("DL/T 645-2007 电表通信参数探测工具")
        self.root.geometry("1100x850")
        self.root.minsize(1000, 750)
        self.root.configure(bg=self.COLORS['bg'])
        
        # 尝试设置 DPI 感知
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        
        self.all_results = []
        self.success_results = []
        self.is_scanning = False
        self.scan_thread = None
        self.ser = None
        
        self._setup_styles()
        self.build_ui()
        self.refresh_ports()
    
    def _setup_styles(self):
        """配置 ttk 样式"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # 全局配置
        self.style.configure('.',
            background=self.COLORS['bg'],
            foreground=self.COLORS['text'],
            fieldbackground=self.COLORS['input_bg'],
            font=('Microsoft YaHei', 10))
        
        # 标签
        self.style.configure('TLabel',
            background=self.COLORS['bg'],
            foreground=self.COLORS['text'],
            font=('Microsoft YaHei', 10))
        
        self.style.configure('TLabel',
            background=self.COLORS['bg'],
            foreground=self.COLORS['text_secondary'],
            font=('Microsoft YaHei', 9))
        
        # 标签框架
        self.style.configure('Card.TLabelframe',
            background=self.COLORS['card_bg'],
            foreground=self.COLORS['text'],
            borderwidth=1,
            relief='solid',
            font=('Microsoft YaHei', 10, 'bold'))
        
        self.style.configure('Card.TLabelframe.Label',
            background=self.COLORS['card_bg'],
            foreground=self.COLORS['accent'],
            font=('Microsoft YaHei', 11, 'bold'))
        
        # 按钮
        self.style.configure('Accent.TButton',
            background=self.COLORS['button_bg'],
            foreground='#ffffff',
            font=('Microsoft YaHei', 10, 'bold'),
            padding=(20, 8),
            relief='flat',
            borderwidth=0)
        
        self.style.map('Accent.TButton',
            background=[('active', self.COLORS['accent_hover']), ('pressed', self.COLORS['accent_hover'])],
            foreground=[('active', '#ffffff')])
        
        self.style.configure('Secondary.TButton',
            background=self.COLORS['button_secondary'],
            foreground=self.COLORS['text'],
            font=('Microsoft YaHei', 10),
            padding=(15, 6),
            relief='flat',
            borderwidth=0)
        
        self.style.map('Secondary.TButton',
            background=[('active', '#3a3a6a'), ('pressed', '#3a3a6a')],
            foreground=[('active', self.COLORS['text'])])
        
        # 下拉框
        self.style.configure('TCombobox',
            fieldbackground=self.COLORS['input_bg'],
            background=self.COLORS['card_bg'],
            foreground=self.COLORS['text'],
            arrowcolor=self.COLORS['accent'],
            padding=5)
        
        # 进度条
        self.style.configure('Horizontal.TProgressbar',
            background=self.COLORS['progress_fg'],
            troughcolor=self.COLORS['progress_bg'],
            borderwidth=0,
            lightcolor=self.COLORS['progress_fg'],
            darkcolor=self.COLORS['progress_fg'])
        
        # 树形视图
        self.style.configure('Custom.Treeview',
            background=self.COLORS['card_bg'],
            foreground=self.COLORS['text'],
            fieldbackground=self.COLORS['card_bg'],
            rowheight=28,
            font=('Consolas', 10))
        
        self.style.configure('Custom.Treeview.Heading',
            background=self.COLORS['card_bg_light'],
            foreground=self.COLORS['accent'],
            font=('Microsoft YaHei', 10, 'bold'),
            relief='flat')
        
        self.style.map('Custom.Treeview',
            background=[('selected', self.COLORS['accent_hover'])],
            foreground=[('selected', '#ffffff')])
    
    def build_ui(self):
        """构建现代化 UI"""
        # 主容器
        main_frame = tk.Frame(self.root, bg=self.COLORS['bg'])
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        # ===== 标题栏 =====
        header = tk.Frame(main_frame, bg=self.COLORS['bg'])
        header.pack(fill='x', pady=(0, 15))
        
        tk.Label(header, text="⚡", font=('Segoe UI', 24), 
                bg=self.COLORS['bg'], fg=self.COLORS['accent']).pack(side='left')
        
        title_frame = tk.Frame(header, bg=self.COLORS['bg'])
        title_frame.pack(side='left', padx=(10, 0))
        
        tk.Label(title_frame, text="DL/T 645-2007", 
                font=('Microsoft YaHei', 16, 'bold'),
                bg=self.COLORS['bg'], fg=self.COLORS['text']).pack(anchor='w')
        
        tk.Label(title_frame, text="电表通信参数探测工具", 
                font=('Microsoft YaHei', 11),
                bg=self.COLORS['bg'], fg=self.COLORS['text_secondary']).pack(anchor='w')
        
        # 串口状态指示器
        self.status_indicator = tk.Canvas(header, width=12, height=12, 
                                         bg=self.COLORS['bg'], highlightthickness=0)
        self.status_indicator.pack(side='right', padx=5)
        self._draw_status_circle('gray')
        
        self.serial_status_label = tk.Label(header, text="串口未连接",
                                           font=('Microsoft YaHei', 10),
                                           bg=self.COLORS['bg'], fg=self.COLORS['text_dim'])
        self.serial_status_label.pack(side='right')
        
        # ===== 串口配置卡片 =====
        port_card = tk.LabelFrame(main_frame, text=" 串口配置 ", 
                                  bg=self.COLORS['card_bg'],
                                  fg=self.COLORS['accent'],
                                  font=('Microsoft YaHei', 11, 'bold'),
                                  padx=15, pady=12,
                                  relief='solid', borderwidth=1)
        port_card.pack(fill='x', pady=(0, 10))
        
        port_inner = tk.Frame(port_card, bg=self.COLORS['card_bg'])
        port_inner.pack(fill='x')
        
        # 串口选择
        tk.Label(port_inner, text="串口", font=('Microsoft YaHei', 10),
                bg=self.COLORS['card_bg'], fg=self.COLORS['text_secondary']).grid(row=0, column=0, sticky='w')
        
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_inner, textvariable=self.port_var, 
                                       width=18, font=('Consolas', 10))
        self.port_combo.grid(row=0, column=1, padx=(8, 15), sticky='w')
        
        ttk.Button(port_inner, text="🔄 刷新", command=self.refresh_ports,
                  style='Secondary.TButton', width=10).grid(row=0, column=2, padx=(0, 15))
        
        # 串口开关按钮
        self.open_btn = tk.Button(port_inner, text="🔌 打开串口", 
                                  font=('Microsoft YaHei', 10, 'bold'),
                                  bg=self.COLORS['success'], fg='#ffffff',
                                  activebackground='#00b894',
                                  relief='flat', padx=20, pady=6,
                                  cursor='hand2', command=self.open_serial)
        self.open_btn.grid(row=0, column=3, padx=(0, 8))
        
        self.close_btn = tk.Button(port_inner, text="🔒 关闭串口",
                                   font=('Microsoft YaHei', 10),
                                   bg=self.COLORS['button_secondary'], 
                                   fg=self.COLORS['text'],
                                   activebackground='#3a3a6a',
                                   relief='flat', padx=20, pady=6,
                                   cursor='hand2', command=self.close_serial,
                                   state='disabled')
        self.close_btn.grid(row=0, column=4)
        
        # ===== 自动探测卡片 =====
        scan_card = tk.LabelFrame(main_frame, text=" 自动探测 ",
                                  bg=self.COLORS['card_bg'],
                                  fg=self.COLORS['accent'],
                                  font=('Microsoft YaHei', 11, 'bold'),
                                  padx=15, pady=12,
                                  relief='solid', borderwidth=1)
        scan_card.pack(fill='x', pady=(0, 10))
        
        scan_inner = tk.Frame(scan_card, bg=self.COLORS['card_bg'])
        scan_inner.pack(fill='x')
        
        # 波特率
        self._create_option_row(scan_inner, 0, "波特率", self._create_baud_checks)
        self._create_option_row(scan_inner, 1, "数据位", self._create_data_checks)
        self._create_option_row(scan_inner, 2, "校验位", self._create_parity_checks)
        self._create_option_row(scan_inner, 3, "停止位", self._create_stop_checks)
        
        # 超时和唤醒
        tk.Label(scan_inner, text="等待超时", font=('Microsoft YaHei', 10),
                bg=self.COLORS['card_bg'], fg=self.COLORS['text_secondary']).grid(row=4, column=0, sticky='w', pady=(8, 0))
        
        timeout_frame = tk.Frame(scan_inner, bg=self.COLORS['card_bg'])
        timeout_frame.grid(row=4, column=1, sticky='w', pady=(8, 0), padx=(8, 0))
        
        self.timeout_var = tk.StringVar(value="1500")
        timeout_entry = tk.Entry(timeout_frame, textvariable=self.timeout_var,
                                width=8, font=('Consolas', 11),
                                bg=self.COLORS['input_bg'], fg=self.COLORS['text'],
                                relief='solid', borderwidth=1,
                                highlightbackground=self.COLORS['border'],
                                highlightcolor=self.COLORS['accent'],
                                justify='center')
        timeout_entry.pack(side='left')
        tk.Label(timeout_frame, text="ms", font=('Microsoft YaHei', 10),
                bg=self.COLORS['card_bg'], fg=self.COLORS['text_dim']).pack(side='left', padx=(5, 20))
        
        self.wakeup_var = tk.BooleanVar(value=True)
        wakeup_cb = self._create_modern_check(timeout_frame, "先发唤醒 FE", self.wakeup_var)
        wakeup_cb.pack(side='left', padx=(15, 0))
        
        # 操作按钮行
        btn_row = tk.Frame(scan_inner, bg=self.COLORS['card_bg'])
        btn_row.grid(row=5, column=0, columnspan=6, sticky='w', pady=(15, 5))
        
        self.scan_btn = tk.Button(btn_row, text="▶ 开始探测",
                                  font=('Microsoft YaHei', 11, 'bold'),
                                  bg=self.COLORS['button_bg'], fg='#ffffff',
                                  activebackground=self.COLORS['accent_hover'],
                                  relief='flat', padx=30, pady=8,
                                  cursor='hand2', command=self.start_scan)
        self.scan_btn.pack(side='left', padx=(0, 10))
        
        self.stop_btn = tk.Button(btn_row, text="⏹ 停止",
                                  font=('Microsoft YaHei', 11),
                                  bg=self.COLORS['button_secondary'], 
                                  fg=self.COLORS['text'],
                                  activebackground='#3a3a6a',
                                  relief='flat', padx=25, pady=8,
                                  cursor='hand2', command=self.stop_scan,
                                  state='disabled')
        self.stop_btn.pack(side='left', padx=(0, 10))
        
        self.export_btn = tk.Button(btn_row, text="📄 导出 CSV",
                                    font=('Microsoft YaHei', 11),
                                    bg=self.COLORS['button_secondary'],
                                    fg=self.COLORS['text'],
                                    activebackground='#3a3a6a',
                                    relief='flat', padx=25, pady=8,
                                    cursor='hand2', command=self.export_csv,
                                    state='disabled')
        self.export_btn.pack(side='left', padx=(0, 10))
        
        tk.Button(btn_row, text="🗑 清空日志",
                  font=('Microsoft YaHei', 10),
                  bg=self.COLORS['card_bg'], fg=self.COLORS['text_dim'],
                  activebackground=self.COLORS['card_bg_light'],
                  relief='flat', padx=15, pady=6,
                  cursor='hand2', command=self.clear_log).pack(side='left')
        
        # ===== 进度条 =====
        progress_frame = tk.Frame(main_frame, bg=self.COLORS['bg'])
        progress_frame.pack(fill='x', pady=(0, 8))
        
        self.progress = ttk.Progressbar(progress_frame, mode='determinate',
                                        style='Horizontal.TProgressbar')
        self.progress.pack(fill='x')
        
        self.status_var = tk.StringVar(value="就绪 | 先打开串口，再开始探测")
        tk.Label(progress_frame, textvariable=self.status_var,
                font=('Microsoft YaHei', 10),
                bg=self.COLORS['bg'], fg=self.COLORS['text_secondary']).pack(anchor='w', pady=(5, 0))
        
        # ===== 左右分栏：日志 + 结果 =====
        content_frame = tk.Frame(main_frame, bg=self.COLORS['bg'])
        content_frame.pack(fill='both', expand=True)
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # 日志区域
        log_card = tk.LabelFrame(content_frame, text=" 通信日志 ",
                                 bg=self.COLORS['card_bg'],
                                 fg=self.COLORS['accent'],
                                 font=('Microsoft YaHei', 11, 'bold'),
                                 padx=10, pady=10,
                                 relief='solid', borderwidth=1)
        log_card.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        
        self.log_text = scrolledtext.ScrolledText(
            log_card, wrap='word',
            font=('Consolas', 10),
            bg=self.COLORS['input_bg'], fg=self.COLORS['text'],
            relief='flat', borderwidth=0,
            padx=8, pady=8,
            selectbackground=self.COLORS['accent'],
            selectforeground='#ffffff'
        )
        self.log_text.pack(fill='both', expand=True)
        
        # 配置日志标签颜色
        self.log_text.tag_configure('trying', foreground=self.COLORS['text_secondary'])
        self.log_text.tag_configure('success', foreground=self.COLORS['success'], font=('Consolas', 10, 'bold'))
        self.log_text.tag_configure('fail', foreground=self.COLORS['error'])
        self.log_text.tag_configure('timestamp', foreground=self.COLORS['text_dim'])
        self.log_text.tag_configure('tx', foreground='#6bb9ff')
        self.log_text.tag_configure('rx', foreground='#f9ca24')
        
        # 结果区域
        result_card = tk.LabelFrame(content_frame, text=" 探测成功结果 ",
                                    bg=self.COLORS['card_bg'],
                                    fg=self.COLORS['accent'],
                                    font=('Microsoft YaHei', 11, 'bold'),
                                    padx=10, pady=10,
                                    relief='solid', borderwidth=1)
        result_card.grid(row=0, column=1, sticky='nsew')
        
        columns = ('params', 'address', 'raw')
        self.result_tree = ttk.Treeview(result_card, columns=columns, 
                                        show='headings', height=15,
                                        style='Custom.Treeview')
        self.result_tree.heading('params', text='通信参数')
        self.result_tree.heading('address', text='地址')
        self.result_tree.heading('raw', text='原始报文')
        self.result_tree.column('params', width=140, anchor='center')
        self.result_tree.column('address', width=200, anchor='center')
        self.result_tree.column('raw', width=250, anchor='w')
        self.result_tree.pack(fill='both', expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(self.result_tree, orient='vertical', 
                                  command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        
        # 绑定双击复制
        self.result_tree.bind('<Double-1>', self.on_tree_double_click)
        
        # 统计信息
        self.stats_var = tk.StringVar(value="成功: 0 | 总计: 0")
        tk.Label(result_card, textvariable=self.stats_var,
                font=('Microsoft YaHei', 10),
                bg=self.COLORS['card_bg'], fg=self.COLORS['text_secondary']).pack(anchor='e', pady=(5, 0))
    
    def _draw_status_circle(self, color):
        """绘制串口状态指示灯"""
        self.status_indicator.delete('all')
        x, y = 6, 6
        r = 5
        self.status_indicator.create_oval(x-r, y-r, x+r, y+r, 
                                          fill=color, outline='')
    
    def _create_option_row(self, parent, row, label, create_func):
        """创建选项行"""
        tk.Label(parent, text=label, font=('Microsoft YaHei', 10),
                bg=self.COLORS['card_bg'], fg=self.COLORS['text_secondary']).grid(
                    row=row, column=0, sticky='nw', pady=3)
        frame = tk.Frame(parent, bg=self.COLORS['card_bg'])
        frame.grid(row=row, column=1, sticky='w', padx=(8, 0), pady=3)
        create_func(frame)
    
    def _create_baud_checks(self, parent):
        """创建波特率复选框"""
        self.baud_vars = {}
        for baud in [1200, 2400, 4800, 7200, 9600, 19200, 38400, 57600, 115200]:
            var = tk.BooleanVar(value=True)
            self.baud_vars[baud] = var
            self._create_modern_check(parent, str(baud), var).pack(side='left', padx=4)
    
    def _create_data_checks(self, parent):
        """创建数据位复选框"""
        self.data_vars = {}
        for val in [7, 8]:
            var = tk.BooleanVar(value=(val == 8))
            self.data_vars[val] = var
            self._create_modern_check(parent, str(val), var).pack(side='left', padx=8)
    
    def _create_parity_checks(self, parent):
        """创建校验位复选框"""
        self.parity_vars = {}
        for p, label in [('N', 'None'), ('E', 'Even'), ('O', 'Odd')]:
            var = tk.BooleanVar(value=(p == 'E'))
            self.parity_vars[p] = var
            self._create_modern_check(parent, label, var).pack(side='left', padx=8)
    
    def _create_stop_checks(self, parent):
        """创建停止位复选框"""
        self.stop_vars = {}
        for val in [1, 2]:
            var = tk.BooleanVar(value=(val == 1))
            self.stop_vars[val] = var
            self._create_modern_check(parent, str(val), var).pack(side='left', padx=8)
    
    def _create_modern_check(self, parent, text, var):
        """创建现代化复选框 — 使用系统原生样式，但文字颜色反馈状态"""
        cb = tk.Checkbutton(parent, text=text, variable=var,
                            bg=self.COLORS['card_bg'], 
                            activebackground=self.COLORS['card_bg_light'],
                            selectcolor=self.COLORS['card_bg'],
                            fg=self.COLORS['text_dim'],
                            activeforeground=self.COLORS['text'],
                            font=('Microsoft YaHei', 10),
                            cursor='hand2',
                            selectforeground=self.COLORS['accent'],
                            highlightthickness=0)
        
        def update(*args):
            cb.config(fg=self.COLORS['accent'] if var.get() else self.COLORS['text_dim'])
        
        var.trace_add('write', update)
        return cb
    
    def refresh_ports(self):
        """刷新串口列表"""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_var.set(ports[0])
            self.log(f"发现串口: {', '.join(ports)}")
        else:
            self.port_var.set('')
            self.log("未检测到串口", 'fail')
    
    def open_serial(self):
        """打开串口"""
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("警告", "请先选择串口")
            return
        try:
            self.ser = serial.Serial(port, timeout=1)
            self.open_btn.config(state='disabled')
            self.close_btn.config(state='normal')
            self._draw_status_circle(self.COLORS['success'])
            self.serial_status_label.config(text=f"已连接 | {port}", fg=self.COLORS['success'])
            self.log(f"串口已打开: {port}", 'success')
        except Exception as e:
            self.log(f"打开串口失败: {e}", 'fail')
    
    def close_serial(self):
        """关闭串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.open_btn.config(state='normal')
        self.close_btn.config(state='disabled')
        self._draw_status_circle('gray')
        self.serial_status_label.config(text="串口未连接", fg=self.COLORS['text_dim'])
        self.log("串口已关闭")
    
    def start_scan(self):
        """开始探测"""
        if self.is_scanning:
            return
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("警告", "请先打开串口")
            return
        
        baudrates = [b for b, v in self.baud_vars.items() if v.get()]
        databits = [d for d, v in self.data_vars.items() if v.get()]
        parities = [p for p, v in self.parity_vars.items() if v.get()]
        stopbits = [s for s, v in self.stop_vars.items() if v.get()]
        
        if not all([baudrates, databits, parities, stopbits]):
            messagebox.showwarning("警告", "请至少勾选一种波特率、数据位、校验位和停止位")
            return
        
        self.all_results.clear()
        self.success_results.clear()
        self.result_tree.delete(*self.result_tree.get_children())
        self.is_scanning = True
        self.scan_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.export_btn.config(state='disabled')
        
        self.scan_thread = threading.Thread(target=self.scan_worker, 
                                            args=(baudrates, databits, parities, stopbits))
        self.scan_thread.daemon = True
        self.scan_thread.start()
    
    def stop_scan(self):
        """停止探测"""
        self.is_scanning = False
        self.scan_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        if self.success_results:
            self.export_btn.config(state='normal')
        self.log("探测已停止")
    
    def scan_worker(self, baudrates, databits, parities, stopbits):
        """探测工作线程"""
        try:
            timeout_ms = int(self.timeout_var.get() or 1500)
        except ValueError:
            timeout_ms = 1500
        
        total = len(baudrates) * len(databits) * len(parities) * len(stopbits)
        count = 0
        
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
                        
                        self.root.after(0, lambda p=params, c=count, t=total: (
                            self.status_var.set(f"正在探测: {p} ({c}/{t})"),
                            self.progress.configure(value=(c / t) * 100)
                        ))
                        
                        self.log(f"[{count}/{total}] {params} (超时{timeout_ms}ms) ...", 'trying')
                        
                        # 记录 TX
                        tx_hex = self.build_read_addr_frame().hex().upper()
                        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        if self.wakeup_var.get():
                            self.log(f"[{ts}] TX: FE FE FE FE {tx_hex}")
                        else:
                            self.log(f"[{ts}] TX: {tx_hex}")
                        
                        ok, msg, raw, addr = self.try_params(baud, databit, parity, stopbit, timeout_ms)
                        
                        # 记录 RX
                        if raw:
                            ts_rx = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            self.log(f"[{ts_rx}] RX: {raw.hex().upper()}")
                        else:
                            self.log("RX: (无应答)")
                        
                        result = {
                            'baud': baud, 'databits': databit, 'parity': parity,
                            'stopbits': stopbit, 'success': ok, 'message': msg,
                            'raw': raw.hex().upper() if raw else '',
                            'addr': addr,
                            'timestamp': ts
                        }
                        self.all_results.append(result)
                        
                        if ok:
                            self.log(f"  ✅ {msg}", 'success')
                            self.success_results.append(result)
                            display_addr = addr if addr else msg
                            self.root.after(0, lambda r=result, a=display_addr: (
                                self.result_tree.insert('', 'end', 
                                    values=(f"{r['baud']}/{r['databits']}-{r['parity']}-{r['stopbits']}", 
                                           a, r['raw'])),
                                self.stats_var.set(f"成功: {len(self.success_results)} | 总计: {count}")
                            ))
                        else:
                            self.log(f"  ❌ {msg}", 'fail')
                        
                        time.sleep(0.3)
        
        self.is_scanning = False
        self.root.after(0, lambda: (
            self.scan_btn.config(state='normal'),
            self.stop_btn.config(state='disabled'),
            self.export_btn.config(state='normal' if self.success_results else 'disabled'),
            self.status_var.set(f"探测完成 | 成功 {len(self.success_results)}/{count}"),
            self.progress.configure(value=100)
        ))
    
    def try_params(self, baud, databits, parity, stopbits, timeout_ms):
        """尝试一组参数"""
        addr = ''
        if not self.ser or not self.ser.is_open:
            return False, "串口未打开", b'', addr
        
        try:
            self.ser.baudrate = baud
            self.ser.bytesize = databits
            self.ser.parity = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}[parity]
            self.ser.stopbits = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}[stopbits]
            self.ser.timeout = timeout_ms / 1000.0
            
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.05)
            
            if self.wakeup_var.get():
                self.ser.write(bytes([0xFE, 0xFE, 0xFE, 0xFE]))
                time.sleep(0.1)
            
            self.ser.write(self.build_read_addr_frame())
            self.ser.flush()
            
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
                return False, "无应答", b'', addr
            
            clean = self.strip_fe_prefix(response)
            if len(clean) < 12:
                return False, f"数据过短(去FE后{len(clean)}字节)", response, addr
            
            if clean[0] != 0x68 or clean[7] != 0x68 or clean[-1] != 0x16:
                return False, "帧头/帧尾错误", response, addr
            
            cs_calc = self.calc_checksum(clean[:-2])
            cs_recv = clean[-2]
            if cs_calc != cs_recv:
                return False, f"校验码错误(计算{cs_calc:02X}!=收到{cs_recv:02X})", response, addr
            
            addr_bytes = clean[1:7]
            addr = addr_bytes[::-1].hex().upper()
            
            ctrl = clean[8]
            l = clean[9]
            data_start = 10
            cs_pos = data_start + l
            
            if len(clean) < cs_pos + 2:
                return False, f"帧长度不足", response, addr
            
            if ctrl == 0x93:
                if l >= 10 and len(clean) >= data_start + 10 + 2:
                    di = clean[data_start:data_start + 4].hex().upper()
                    return True, f"地址:{addr} DI:{di}", response, addr
                elif l == 6 and len(clean) >= data_start + 6 + 2:
                    return True, f"地址:{addr}", response, addr
                else:
                    return True, f"地址:{addr}", response, addr
            elif ctrl == 0x91:
                if l >= 4 and len(clean) >= data_start + 4 + 2:
                    di = clean[data_start:data_start + 4].hex().upper()
                    data_val = clean[data_start + 4:cs_pos].hex().upper() if l > 4 else ''
                    if data_val:
                        return True, f"地址:{addr} DI:{di} 数据:{data_val}", response, addr
                    else:
                        return True, f"地址:{addr} DI:{di}", response, addr
                elif l > 0:
                    data_hex = clean[data_start:data_start + l].hex().upper()
                    return True, f"地址:{addr} 数据:{data_hex}", response, addr
                else:
                    return True, f"地址:{addr}", response, addr
            elif ctrl == 0xD1:
                return True, f"地址:{addr} 异常应答", response, addr
            else:
                return False, f"地址:{addr} 未知控制码{ctrl:02X}", response, addr
                
        except Exception as e:
            return False, str(e), b'', addr
    
    def build_read_addr_frame(self):
        """构建读地址报文"""
        return bytes([0x68, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA,
                     0x68, 0x13, 0x00, 0xDF, 0x16])
    
    def strip_fe_prefix(self, data):
        """去除前导 FE 字节"""
        for i, byte in enumerate(data):
            if byte != 0xFE:
                return data[i:]
        return data
    
    def calc_checksum(self, data):
        """计算校验和"""
        return sum(data) & 0xFF
    
    def export_to_csv(self):
        """导出 CSV"""
        if not self.all_results:
            return
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # 完整日志
            full_path = filedialog.asksaveasfilename(
                title="保存完整探测日志",
                defaultextension=".csv",
                initialfile=f"meter_scan_full_{ts}.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if full_path:
                with open(full_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位',
                                    '结果', '详情', '地址', '原始应答报文', '时间戳'])
                    for i, r in enumerate(self.all_results, 1):
                        writer.writerow([i, r['baud'], r['databits'], r['parity'],
                                       r['stopbits'], '成功' if r['success'] else '失败',
                                       r['message'], r['addr'], r['raw'], r['timestamp']])
                self.log(f"完整日志已保存: {full_path}", 'success')
            
            # 成功摘要
            if self.success_results:
                success_path = full_path.replace('_full_', '_success_') if full_path else f"meter_scan_success_{ts}.csv"
                with open(success_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['序号', '波特率', '数据位', '校验位', '停止位',
                                    '地址', '原始报文', '推荐'])
                    for i, r in enumerate(self.success_results, 1):
                        writer.writerow([
                            i, r['baud'], r['databits'], r['parity'], r['stopbits'],
                            r['addr'] if r['addr'] else r['message'], r['raw'],
                            '★ 推荐' if i == 1 else ''
                        ])
                self.log(f"成功摘要已保存: {success_path}", 'success')
        
        except Exception as e:
            self.log(f"导出失败: {e}", 'fail')
    
    def export_csv(self):
        """导出按钮回调"""
        threading.Thread(target=self.export_to_csv, daemon=True).start()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', 'end')
    
    def log(self, msg, tag=''):
        """线程安全的日志记录"""
        def _do_log():
            self.log_text.insert('end', f"{msg}\n", tag)
            self.log_text.see('end')
        
        if threading.current_thread() is threading.main_thread():
            _do_log()
        else:
            self.root.after(0, _do_log)
    
    def on_tree_double_click(self, event):
        """双击复制结果"""
        item = self.result_tree.selection()
        if item:
            values = self.result_tree.item(item[0], 'values')
            if values:
                text = f"{values[0]} | {values[1]} | {values[2]}"
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.log(f"已复制: {text}", 'success')


if __name__ == '__main__':
    root = tk.Tk()
    app = ModernMeterScannerGUI(root)
    root.mainloop()
