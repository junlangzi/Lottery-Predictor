# -*- coding: utf-8 -*-
# File: optimize.py
# Role: GUI Application for Analyzing and Optimizing Lottery Prediction Algorithms (v1.3.3 - Always show advanced opt)

# ... (keep all imports and logging setup the same) ...
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import json
import traceback
import datetime
import shutil
import calendar
from pathlib import Path
import configparser
import importlib.util
import inspect
import random
import copy
import threading
import queue
import time
import ast
# --- Try importing astor, required for Python < 3.9 ---
try:
    # --- Logging Setup ---
    base_dir_for_log = Path(__file__).parent.resolve()
    log_file_path = base_dir_for_log / "lottery_app.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
        filename=log_file_path,
        filemode="a"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(name)s - [%(threadName)s] - %(message)s')
    root_logger = logging.getLogger('')
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
         root_logger.addHandler(console_handler)
    logger = logging.getLogger("AlgorithmOptimizerApp")
    # --- End Logging Setup ---

    if sys.version_info < (3, 9):
        import astor
        HAS_ASTOR = True
        logger.debug("Using 'astor' for AST unparsing.")
    else:
        HAS_ASTOR = False
        logger.debug("Using 'ast.unparse' (Python 3.9+).")
except ImportError:
    if sys.version_info < (3, 9):
        print("LỖI NGHIÊM TRỌNG: Cần thư viện 'astor' cho Python < 3.9. Cài đặt: pip install astor", file=sys.stderr)
        try:
            root_err = tk.Tk(); root_err.withdraw()
            messagebox.showerror("Thiếu Thư Viện", "Cần thư viện 'astor' cho phiên bản Python này.\nVui lòng cài đặt: pip install astor")
            root_err.destroy()
        except: pass
        sys.exit(1)
    else:
        HAS_ASTOR = False


import subprocess
from collections import Counter
from importlib import reload, util

# --- Import BaseAlgorithm ---
try:
    script_dir = Path(__file__).parent.resolve()
    if str(script_dir) not in sys.path: sys.path.insert(0, str(script_dir)); logger.info(f"Tạm thời thêm {script_dir} vào sys.path.")
    if 'algorithms.base' in sys.modules:
        try: reload(sys.modules['algorithms.base']); logger.debug("Reloaded algorithms.base module.")
        except Exception as reload_err: logger.warning(f"Could not reload algorithms.base: {reload_err}"); del sys.modules['algorithms.base']
    if 'algorithms' in sys.modules:
         try: reload(sys.modules['algorithms']); logger.debug("Reloaded algorithms package.")
         except Exception as reload_pkg_err: logger.warning(f"Could not reload algorithms package: {reload_pkg_err}")
    from algorithms.base import BaseAlgorithm
    logger.info("Imported BaseAlgorithm successfully.")
except ImportError as e:
    print(f"Lỗi: Không thể import BaseAlgorithm: {e}", file=sys.stderr); logger.critical(f"Failed to import BaseAlgorithm: {e}", exc_info=True)
    from abc import ABC, abstractmethod
    class BaseAlgorithm(ABC): # Dummy class
        def __init__(self, *args, **kwargs): self.config = {"description": "Base Giả", "calculation_logic": "dummy", "parameters": {}}; self._raw_results_list = []; self.cache_dir = None; self.logger = logging.getLogger("DummyBaseAlgorithm")
        def get_config(self): return self.config
        @abstractmethod
        def predict(self, *args, **kwargs): raise NotImplementedError
        def get_results_in_range(self, s, e): return []
        def extract_numbers_from_dict(self, d): return set()
        def _log(self, l, m): self.logger.log(getattr(logging, l.upper(), logging.WARNING), m)
    print("Cảnh báo: Sử dụng lớp BaseAlgorithm giả.", file=sys.stderr); logger.warning("Using dummy BaseAlgorithm class.")
except Exception as base_import_err:
    print(f"Lỗi không xác định khi import BaseAlgorithm: {base_import_err}", file=sys.stderr); logger.critical(f"Unknown error importing BaseAlgorithm: {base_import_err}", exc_info=True); sys.exit(1)

# --- Check tkcalendar ---
try:
    from tkcalendar import Calendar, DateEntry
    HAS_TKCALENDAR = True
    logger.info("tkcalendar library found.")
except ImportError:
    HAS_TKCALENDAR = False
    logger.warning("tkcalendar library not found. Calendar/DateEntry features limited. Install with: pip install tkcalendar")
    print("Cảnh báo: Không tìm thấy tkcalendar. pip install tkcalendar")


# --- Main Application Class ---
class AlgorithmOptimizerApp:
    # __init__
    def __init__(self, root):
        self.root = root
        self.root.title("Trình Phân Tích & Tối Ưu Thuật Toán Xổ Số (v1.3.3)") # Version bump
        self.root.geometry("1300x900")
        self.root.minsize(1000, 700)
        logger.info("Initializing AlgorithmOptimizerApp...")

        # --- Directories ---
        self.base_dir = Path(__file__).parent.resolve()
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.base_dir / "config"
        self.algorithms_dir = self.base_dir / "algorithms"
        self.optimize_dir = self.base_dir / "optimize"
        self.calculate_dir = self.base_dir / "calculate"
        logger.info(f"Base Dir: {self.base_dir}")
        logger.info(f"Algorithm Dir: {self.algorithms_dir}")
        logger.info(f"Optimize Dir: {self.optimize_dir}")
        logger.info(f"Cache Dir: {self.calculate_dir}")

        # --- Core Data & State ---
        self.config = configparser.ConfigParser(interpolation=None)
        self.results_data = []
        self.loaded_algorithms = {}
        self.selected_algorithm_for_edit = None
        self.selected_algorithm_for_optimize = None
        self.editor_param_vars = {}
        self.editor_original_params = {}

        # --- Optimization State ---
        self.optimizer_thread = None
        self.optimizer_queue = queue.Queue()
        self.optimizer_stop_event = threading.Event()
        self.optimizer_pause_event = threading.Event()
        self.optimizer_running = False
        self.optimizer_paused = False
        self.current_best_params = None
        self.current_best_score = -1.0
        self.current_optimization_log_path = None
        self.current_optimize_target_dir = None
        self.optimizer_custom_steps = {}
        # self.advanced_opt_frame_visible = False # REMOVED - Frame always visible
        self.advanced_opt_widgets = {}

        # --- UI Variables ---
        self.data_file_path_var = tk.StringVar()
        self.data_range_var = tk.StringVar(value="...")
        self.window_width_var = tk.StringVar()
        self.window_height_var = tk.StringVar()
        self.opt_start_date_var = tk.StringVar()
        self.opt_end_date_var = tk.StringVar()
        self.opt_time_limit_var = tk.StringVar(value="60")
        self.opt_status_var = tk.StringVar(value="Trạng thái: Chờ")
        self.opt_progress_pct_var = tk.StringVar(value="0%")

        # --- Setup ---
        self.create_directories()
        self.setup_styles()
        self.validate_dimension_cmd = self.root.register(self._validate_dimension_input)
        self.validate_numeric_cmd = self.root.register(self._validate_numeric_input)
        self.validate_int_cmd = self.root.register(self._validate_int_input)
        self.validate_custom_steps_cmd = self.root.register(self._validate_custom_steps_input)

        self.setup_ui()
        self.load_app_config()
        self.apply_window_size()
        self.load_data()
        self.load_algorithms()
        self.update_status("Ứng dụng sẵn sàng.")
        logger.info("AlgorithmOptimizerApp initialized successfully.")

    # create_directories remains the same
    def create_directories(self):
        """Tạo các thư mục cần thiết."""
        logger.debug("Đang tạo thư mục...")
        try:
            for directory in [self.data_dir, self.config_dir, self.algorithms_dir, self.optimize_dir, self.calculate_dir]:
                directory.mkdir(parents=True, exist_ok=True); logger.info(f"Đảm bảo thư mục tồn tại: {directory}")
            init_file = self.algorithms_dir / "__init__.py"
            if not init_file.exists(): init_file.touch(); logger.info(f"Đã tạo file rỗng: {init_file}")
            sample_data_file = self.data_dir / "xsmb-2-digits.json"
            if not sample_data_file.exists():
                logger.info(f"Đang tạo file dữ liệu mẫu: {sample_data_file}")
                today = datetime.date.today(); yesterday = today - datetime.timedelta(days=1)
                sample_data = [{"date": yesterday.strftime('%Y-%m-%d'), "result": {"special": f"{random.randint(0,99999):05d}", "prize1": f"{random.randint(0,99999):05d}", "prize7_1": f"{random.randint(0,99):02d}"}},
                               {"date": today.strftime('%Y-%m-%d'), "result": {"special": f"{random.randint(0,99999):05d}", "prize1": f"{random.randint(0,99999):05d}", "prize7_1": f"{random.randint(0,99):02d}"}}]
                try:
                    with open(sample_data_file, 'w', encoding='utf-8') as f: json.dump(sample_data, f, ensure_ascii=False, indent=2)
                    logger.info("Đã tạo file dữ liệu mẫu.")
                except IOError as e: logger.error(f"Không thể ghi file dữ liệu mẫu: {e}")
        except Exception as e: logger.error(f"Lỗi tạo thư mục/dữ liệu mẫu: {e}", exc_info=True); messagebox.showerror("Lỗi", f"Lỗi tạo thư mục/file mẫu:\n{e}")

    # setup_styles remains the same
    def setup_styles(self):
        """Thiết lập các style tùy chỉnh cho ttk widgets."""
        logger.debug("Đang thiết lập styles...")
        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        preferred_themes = ['clam', 'alt', 'default', 'vista', 'xpnative']
        selected_theme = self.style.theme_use()
        for theme in preferred_themes:
             if theme in available_themes:
                 try: self.style.theme_use(theme); selected_theme = theme; logger.info(f"Sử dụng theme: {theme}"); break
                 except tk.TclError: continue
        else: logger.warning(f"Không tìm thấy theme ưu tiên. Dùng mặc định: {selected_theme}")

        self.style.configure("TLabel", font=("Arial", 10))
        self.style.configure("Bold.TLabel", font=("Arial", 10, "bold"))
        self.style.configure("Title.TLabel", font=("Arial", 14, "bold"))
        self.style.configure("Header.TLabel", font=("Arial", 11, "bold"), background="#e0e0e0")
        self.style.configure("Info.TLabel", font=("Arial", 9), foreground="dimgray")
        self.style.configure("Error.TLabel", font=("Arial", 9), foreground="red")
        self.style.configure("Success.TLabel", font=("Arial", 9), foreground="green")
        self.style.configure("TButton", font=("Arial", 10), padding=5)
        self.style.configure("Accent.TButton", font=("Arial", 10, "bold"), foreground="white", background="#007bff"); self.style.map("Accent.TButton", background=[('active', '#0056b3')])
        self.style.configure("Danger.TButton", foreground="white", background="#dc3545"); self.style.map("Danger.TButton", background=[('active', '#c82333')])
        self.style.configure("Warning.TButton", foreground="black", background="#ffc107"); self.style.map("Warning.TButton", background=[('active', '#e0a800')])
        self.style.configure("TLabelframe", font=("Arial", 11, "bold"), padding=10)
        self.style.configure("TLabelframe.Label", font=("Arial", 11, "bold"))
        self.style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
        self.style.configure("TScrolledText", background="white", foreground="black")
        optimize_trough_color = '#E0E0E0' # Grey background
        optimize_bar_color = '#28A745' # Green bar
        self.style.configure("Optimize.Horizontal.TProgressbar",
                             troughcolor=optimize_trough_color,
                             background=optimize_bar_color,
                             thickness=20)
        logger.debug(f"Đã cấu hình style 'Optimize.Horizontal.TProgressbar' với màu thanh: {optimize_bar_color}")

    # setup_ui remains the same
    def setup_ui(self):
        """Xây dựng cấu trúc giao diện chính."""
        logger.debug("Đang thiết lập UI chính...")
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Top Frame: Data Info ---
        top_frame = ttk.LabelFrame(main_frame, text="Thông Tin Dữ Liệu", padding=10); top_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(top_frame, text="File dữ liệu:", style="Bold.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        data_entry = ttk.Entry(top_frame, textvariable=self.data_file_path_var, width=60); data_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(top_frame, text="Duyệt...", command=self.browse_data_file).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(top_frame, text="Tải lại Dữ liệu", command=self.load_data).grid(row=0, column=3, padx=5, pady=5)
        top_frame.columnconfigure(1, weight=1)
        ttk.Label(top_frame, text="Phạm vi:", style="Bold.TLabel").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Label(top_frame, textvariable=self.data_range_var).grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky=tk.W)

        # --- Notebook for Tabs ---
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tab_select = ttk.Frame(self.notebook, padding=10)
        self.tab_edit = ttk.Frame(self.notebook, padding=10)
        self.tab_optimize = ttk.Frame(self.notebook, padding=10)
        self.tab_config = ttk.Frame(self.notebook, padding=10)
        self.tab_about = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_select, text=" Chọn Thuật Toán ")
        self.notebook.add(self.tab_edit, text=" Chỉnh Sửa ")
        self.notebook.add(self.tab_optimize, text=" Tối Ưu Hóa ")
        self.notebook.add(self.tab_config, text=" Cấu Hình App ")
        self.notebook.add(self.tab_about, text=" Thông Tin ")

        self.notebook.tab(1, state="disabled") # Edit
        self.notebook.tab(2, state="disabled") # Optimize

        self.setup_select_tab()
        self.setup_edit_tab()
        self.setup_optimize_tab()
        self.setup_config_tab()
        self.setup_about_tab()

        # --- Status Bar ---
        self.status_bar = ttk.Label(self.root, text="Khởi tạo...", relief=tk.SUNKEN, anchor=tk.W, padding=(5, 2))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # setup_select_tab remains the same
    def setup_select_tab(self):
        """Thiết lập UI cho tab Chọn Thuật Toán."""
        logger.debug("Đang thiết lập tab Chọn Thuật Toán.")
        frame = self.tab_select
        control_frame = ttk.Frame(frame); control_frame.pack(fill=tk.X, pady=(0,10))
        ttk.Button(control_frame, text="Tải lại Danh sách Thuật toán", command=self.reload_algorithms).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Chọn để Chỉnh sửa", command=self.select_algo_for_edit, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Chọn để Tối ưu hóa", command=self.select_algo_for_optimize, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        list_frame = ttk.Frame(frame); list_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("Algorithm Name", "File Name", "Description"); self.algo_tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse")
        self.algo_tree.heading("Algorithm Name", text="Tên Thuật Toán"); self.algo_tree.heading("File Name", text="Tên File"); self.algo_tree.heading("Description", text="Mô Tả")
        self.algo_tree.column("Algorithm Name", width=250, minwidth=200, stretch=tk.NO); self.algo_tree.column("File Name", width=150, minwidth=120, stretch=tk.NO); self.algo_tree.column("Description", width=500, minwidth=300)
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.algo_tree.yview); hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.algo_tree.xview)
        self.algo_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set); vsb.pack(side=tk.RIGHT, fill=tk.Y); hsb.pack(side=tk.BOTTOM, fill=tk.X); self.algo_tree.pack(fill=tk.BOTH, expand=True)
        self.algo_tree.bind("<Double-1>", lambda e: self.select_algo_for_edit())

    # setup_edit_tab remains the same
    def setup_edit_tab(self):
        """Thiết lập UI cho tab Chỉnh Sửa."""
        logger.debug("Đang thiết lập tab Chỉnh Sửa.")
        frame = self.tab_edit
        info_frame = ttk.Frame(frame); info_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(info_frame, text="Thuật toán đang sửa:", style="Bold.TLabel").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.edit_algo_name_label = ttk.Label(info_frame, text="...", font=("Arial", 10, "bold"), foreground="navy"); self.edit_algo_name_label.grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(info_frame, text="Mô tả:", style="Bold.TLabel").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.edit_algo_desc_label = ttk.Label(info_frame, text="...", wraplength=600, justify=tk.LEFT, style="Info.TLabel"); self.edit_algo_desc_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        info_frame.columnconfigure(1, weight=1)
        paned_window = ttk.PanedWindow(frame, orient=tk.HORIZONTAL); paned_window.pack(fill=tk.BOTH, expand=True)
        param_frame_outer = ttk.LabelFrame(paned_window, text="Tham Số Có Thể Chỉnh Sửa", padding=10); paned_window.add(param_frame_outer, weight=1)
        param_canvas = tk.Canvas(param_frame_outer, borderwidth=0, highlightthickness=0); param_scrollbar = ttk.Scrollbar(param_frame_outer, orient=tk.VERTICAL, command=param_canvas.yview)
        self.edit_param_scrollable_frame = ttk.Frame(param_canvas); param_canvas.configure(yscrollcommand=param_scrollbar.set)
        param_canvas_window_id = param_canvas.create_window((0, 0), window=self.edit_param_scrollable_frame, anchor=tk.NW)
        param_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); param_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.edit_param_scrollable_frame.bind("<Configure>", lambda e, c=param_canvas: c.configure(scrollregion=c.bbox("all")))
        param_canvas.bind("<Configure>", lambda e, c=param_canvas, w=param_canvas_window_id: c.itemconfig(w, width=e.width))
        def _on_param_mousewheel(event, c=param_canvas):
            delta = 0;
            if event.num == 4: delta = -1
            elif event.num == 5: delta = 1
            elif hasattr(event, 'delta') and event.delta != 0: delta = -1 * int(event.delta / abs(event.delta) if abs(event.delta) > 3 else event.delta)
            if delta: c.yview_scroll(delta, "units")
        for widget in [param_canvas, self.edit_param_scrollable_frame]:
            widget.bind("<MouseWheel>", _on_param_mousewheel, add='+'); widget.bind("<Button-4>", _on_param_mousewheel, add='+'); widget.bind("<Button-5>", _on_param_mousewheel, add='+')
        explain_frame = ttk.LabelFrame(paned_window, text="Giải Thích Thuật Toán (Docstring)", padding=10); paned_window.add(explain_frame, weight=1)
        self.edit_explain_text = scrolledtext.ScrolledText(explain_frame, wrap=tk.WORD, height=10, width=50, font=("Arial", 9), state=tk.DISABLED, relief=tk.SUNKEN, borderwidth=1)
        self.edit_explain_text.pack(fill=tk.BOTH, expand=True)
        button_frame = ttk.Frame(frame); button_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(button_frame, text="Lưu Bản Sao...", command=self.save_edited_copy, style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Hủy Bỏ", command=self.cancel_edit).pack(side=tk.RIGHT, padx=5)

    # setup_optimize_tab: MODIFIED - Removed toggle button, grid advanced frame directly
    def setup_optimize_tab(self):
        """Thiết lập UI cho tab Tối Ưu Hóa (layout 2 cột, luôn hiện cài đặt)."""
        logger.debug("Đang thiết lập tab Tối Ưu Hóa (luôn hiện 2 cột).")
        frame = self.tab_optimize

        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        # --- Top section ---
        top_section = ttk.Frame(frame)
        top_section.grid(row=0, column=0, sticky="new")

        # --- Algorithm Info ---
        info_frame = ttk.Frame(top_section); info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(info_frame, text="Thuật toán tối ưu:", style="Bold.TLabel").pack(side=tk.LEFT, padx=5)
        self.opt_algo_name_label = ttk.Label(info_frame, text="...", font=("Arial", 10, "bold"), foreground="darkgreen"); self.opt_algo_name_label.pack(side=tk.LEFT, padx=5)

        # --- Grid Container for Settings ---
        self.settings_grid_frame = ttk.Frame(top_section)
        self.settings_grid_frame.pack(fill=tk.X, pady=5)
        self.settings_grid_frame.columnconfigure(0, weight=1, minsize=350)
        self.settings_grid_frame.columnconfigure(1, weight=1, minsize=350)
        self.settings_grid_frame.rowconfigure(0, weight=1) # Make row containing frames potentially grow

        # --- Basic Settings Frame (Column 0) ---
        settings_frame = ttk.LabelFrame(self.settings_grid_frame, text="Cài Đặt Cơ Bản", padding=10)
        settings_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew") # Stick to all sides of cell
        # Date range
        ttk.Label(settings_frame, text="Khoảng thời gian dữ liệu kiểm tra:", style="Bold.TLabel").grid(row=0, column=0, columnspan=4, sticky=tk.W, padx=5, pady=(0,5))
        ttk.Label(settings_frame, text="Từ ngày:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        start_entry = ttk.Entry(settings_frame, textvariable=self.opt_start_date_var, width=12, state="readonly", justify='center'); start_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="📅", width=2, command=lambda: self.show_calendar_dialog(self.opt_start_date_var)).grid(row=1, column=2, padx=2, pady=5)
        ttk.Label(settings_frame, text="Đến ngày:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        end_entry = ttk.Entry(settings_frame, textvariable=self.opt_end_date_var, width=12, state="readonly", justify='center'); end_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="📅", width=2, command=lambda: self.show_calendar_dialog(self.opt_end_date_var)).grid(row=2, column=2, padx=2, pady=5)
        ttk.Label(settings_frame, text="(Ngày cuối < ngày cuối data 1 ngày)", style='Info.TLabel').grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=10, pady=5)
        # Time limit
        ttk.Label(settings_frame, text="Thời gian tối ưu tối đa (phút):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        time_entry = ttk.Entry(settings_frame, textvariable=self.opt_time_limit_var, width=8, justify='center', validate='key', validatecommand=(self.validate_int_cmd, '%P')); time_entry.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)
        # --- REMOVED Advanced Settings Button ---
        # self.advanced_opt_toggle_button = ttk.Button(...)
        # self.advanced_opt_toggle_button.grid(...)

        # --- Advanced Optimization Settings Frame (Column 1 - ALWAYS VISIBLE) ---
        self.advanced_opt_frame = ttk.LabelFrame(self.settings_grid_frame, text="Cài Đặt Tối Ưu Nâng Cao", padding=10)
        self.advanced_opt_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew") # Grid directly, stick to all sides

        adv_canvas = tk.Canvas(self.advanced_opt_frame, borderwidth=0, highlightthickness=0)
        adv_scrollbar = ttk.Scrollbar(self.advanced_opt_frame, orient=tk.VERTICAL, command=adv_canvas.yview)
        self.advanced_opt_params_frame = ttk.Frame(adv_canvas)
        adv_canvas.configure(yscrollcommand=adv_scrollbar.set)
        adv_canvas_window_id = adv_canvas.create_window((0, 0), window=self.advanced_opt_params_frame, anchor=tk.NW)

        adv_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        adv_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.advanced_opt_params_frame.bind("<Configure>", lambda e, c=adv_canvas: c.configure(scrollregion=c.bbox("all")))
        adv_canvas.bind("<Configure>", lambda e, c=adv_canvas, w=adv_canvas_window_id: c.itemconfig(w, width=e.width))

        def _on_adv_opt_mousewheel(event, c=adv_canvas):
            delta = 0
            if event.num == 4: delta = -1
            elif event.num == 5: delta = 1
            elif hasattr(event, 'delta') and event.delta != 0: delta = -1 * int(event.delta / abs(event.delta) if abs(event.delta) > 3 else event.delta)
            if delta: c.yview_scroll(delta, "units")

        for widget in [adv_canvas, self.advanced_opt_params_frame]:
            widget.bind("<MouseWheel>", _on_adv_opt_mousewheel, add='+')
            widget.bind("<Button-4>", _on_adv_opt_mousewheel, add='+')
            widget.bind("<Button-5>", _on_adv_opt_mousewheel, add='+')
        ttk.Label(self.advanced_opt_params_frame, text="Chọn thuật toán để xem tham số.", style="Info.TLabel").pack(padx=10, pady=10)


        # --- Control Frame ---
        control_frame = ttk.Frame(top_section); control_frame.pack(fill=tk.X, pady=10)
        self.opt_start_button = ttk.Button(control_frame, text="Bắt đầu Tối ưu", command=self.start_optimization, style="Accent.TButton", width=15); self.opt_start_button.pack(side=tk.LEFT, padx=5)
        self.opt_pause_button = ttk.Button(control_frame, text="Tạm dừng", command=self.pause_optimization, state=tk.DISABLED, style="Warning.TButton", width=12); self.opt_pause_button.pack(side=tk.LEFT, padx=5)
        self.opt_stop_button = ttk.Button(control_frame, text="Dừng Hẳn", command=self.stop_optimization, state=tk.DISABLED, style="Danger.TButton", width=12); self.opt_stop_button.pack(side=tk.LEFT, padx=5)

        # --- Progress Bar and Status ---
        progress_frame = ttk.Frame(top_section); progress_frame.pack(fill=tk.X, pady=5)
        self.opt_progressbar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=300, mode='determinate', style="Optimize.Horizontal.TProgressbar")
        self.opt_progressbar.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        self.opt_progress_label = ttk.Label(progress_frame, textvariable=self.opt_progress_pct_var, width=5, anchor=tk.E)
        self.opt_progress_label.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(progress_frame, textvariable=self.opt_status_var).pack(side=tk.LEFT, padx=10)

        # --- Log Area ---
        log_frame = ttk.LabelFrame(frame, text="Nhật Ký Tối Ưu Hóa", padding=10)
        log_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self.opt_log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, width=80, font=("Courier New", 9), state=tk.DISABLED, relief=tk.SUNKEN, borderwidth=1)
        self.opt_log_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.opt_log_text.tag_config("INFO", foreground="black")
        self.opt_log_text.tag_config("DEBUG", foreground="gray")
        self.opt_log_text.tag_config("WARNING", foreground="orange")
        self.opt_log_text.tag_config("ERROR", foreground="red", font=("Courier New", 9, "bold"))
        self.opt_log_text.tag_config("CRITICAL", foreground="red", font=("Courier New", 9, "bold underline"))
        self.opt_log_text.tag_config("BEST", foreground="darkgreen", font=("Courier New", 9, "bold"))
        self.opt_log_text.tag_config("PROGRESS", foreground="blue")
        self.opt_log_text.tag_config("CUSTOM_STEP", foreground="purple")

        open_folder_button = ttk.Button(log_frame, text="Mở Thư Mục Tối Ưu", command=self.open_optimize_folder)
        open_folder_button.pack(pady=5, anchor=tk.E)

    # setup_config_tab remains the same
    def setup_config_tab(self):
        """Thiết lập UI cho tab Cấu Hình App."""
        logger.debug("Đang thiết lập tab Cấu Hình.")
        frame = self.tab_config
        size_frame = ttk.LabelFrame(frame, text="Kích Thước Cửa Sổ", padding=10); size_frame.pack(fill=tk.X, pady=5)
        ttk.Label(size_frame, text="Rộng (Width):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        width_entry = ttk.Entry(size_frame, textvariable=self.window_width_var, width=8, validate='key', validatecommand=(self.validate_dimension_cmd, '%P')); width_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(size_frame, text="Cao (Height):").grid(row=0, column=2, padx=15, pady=5, sticky=tk.W)
        height_entry = ttk.Entry(size_frame, textvariable=self.window_height_var, width=8, validate='key', validatecommand=(self.validate_dimension_cmd, '%P')); height_entry.grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(size_frame, text="pixels").grid(row=0, column=4, padx=5, pady=5, sticky=tk.W)
        save_button = ttk.Button(frame, text="Lưu Cấu Hình App", command=self.save_app_config, style="Accent.TButton"); save_button.pack(pady=15, anchor=tk.E)

    # setup_about_tab remains the same
    def setup_about_tab(self):
        """Thiết lập UI cho tab Thông Tin."""
        logger.debug("Đang thiết lập tab Thông Tin.")
        frame = self.tab_about
        about_frame = ttk.Frame(frame, padding=20); about_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(about_frame, text="Trình Phân Tích & Tối Ưu Thuật Toán Xổ Số v1.3.3", font=("Arial", 16, "bold")).pack(pady=(0, 20)) # Version bump
        ttk.Label(about_frame, text="Phiên bản: 1.3.3", style="Bold.TLabel").pack(anchor=tk.W, pady=2) # Version bump
        ttk.Label(about_frame, text=f"Ngày cập nhật: {datetime.date.today().strftime('%d/%m/%Y')}").pack(anchor=tk.W, pady=2)
        description = ("Ứng dụng này cho phép:\n"
                       "- Xem và chỉnh sửa các tham số số học trong file thuật toán.\n"
                       "- Lưu bản sao của thuật toán với tham số đã sửa.\n"
                       "- Tự động tối ưu hóa tham số của thuật toán đã chọn bằng cách thử nghiệm nhiều giá trị và đánh giá hiệu suất trên dữ liệu lịch sử.\n"
                       "- **Mới:** Tùy chỉnh bước nhảy (step) cho từng tham số khi tối ưu hóa.\n"
                       "- Tìm bộ tham số cho hiệu suất tốt nhất (ưu tiên tỷ lệ trúng Top 3) và lưu lại thuật toán tối ưu.\n\n"
                       "Lưu ý: Quá trình tối ưu có thể tốn nhiều thời gian và tài nguyên máy tính.")
        ttk.Label(about_frame, text="Mô tả:", style="Bold.TLabel").pack(anchor=tk.W, pady=(20, 2))
        ttk.Label(about_frame, text=description, wraplength=600, justify=tk.LEFT).pack(anchor=tk.W, pady=2)
        libs = f"Python {sys.version.split()[0]}, Tkinter/TTK"
        libs += ", astor" if HAS_ASTOR else ""
        libs += ", tkcalendar" if HAS_TKCALENDAR else ", (tkcalendar nên có)"
        ttk.Label(about_frame, text="Thư viện:", style="Bold.TLabel").pack(anchor=tk.W, pady=(20, 2))
        ttk.Label(about_frame, text=libs).pack(anchor=tk.W, pady=2)

    # --- Validation Methods (remains the same) ---
    def _validate_dimension_input(self, P): return P == "" or P.isdigit()
    def _validate_numeric_input(self, P):
        if P == "" or P == "-": return True
        if P.count('.') > 1: return False
        if P == ".": return True;
        if P == "-.": return True
        if P.endswith(".") and P[:-1].replace('-','',1).isdigit(): return True
        try: float(P); return True
        except ValueError: return False
    def _validate_int_input(self, P): return P == "" or P.isdigit()
    def _validate_custom_steps_input(self, P):
        if P == "": return True
        parts = P.split(',')
        try:
            for part in parts:
                part = part.strip()
                if part: float(part)
            return True
        except ValueError: return False

    # --- Config Handling (remains the same) ---
    def load_app_config(self):
        logger.info("Đang tải cấu hình ứng dụng...")
        config_path = self.config_dir / "settings_optimizer.ini"; default_width, default_height = 1300, 900
        try:
            self.config = configparser.ConfigParser(interpolation=None)
            if config_path.exists(): self.config.read(config_path, encoding='utf-8'); logger.info(f"Đã tải cấu hình từ: {config_path}")
            else: logger.warning(f"Không tìm thấy file cấu hình: {config_path}. Dùng mặc định.")
            w = self.config.getint('UI', 'width', fallback=default_width); h = self.config.getint('UI', 'height', fallback=default_height)
            self.window_width_var.set(str(max(1000, w))); self.window_height_var.set(str(max(700, h))) # Use minsize here
        except Exception as e:
            logger.error(f"Lỗi tải cấu hình: {e}", exc_info=True); self.window_width_var.set(str(default_width)); self.window_height_var.set(str(default_height))
            if not self.config.has_section('UI'): self.config.add_section('UI')
            self.config['UI'] = {'width': str(default_width), 'height': str(default_height)}
    def save_app_config(self):
        logger.info("Đang lưu cấu hình ứng dụng...")
        config_path = self.config_dir / "settings_optimizer.ini"
        try:
            if not self.config.has_section('UI'): self.config.add_section('UI')
            w_str = self.window_width_var.get().strip(); h_str = self.window_height_var.get().strip()
            try:
                 w = int(w_str) if w_str else 1300; h = int(h_str) if h_str else 900;
                 min_w, min_h = self.root.minsize() # Get current minsize
                 w = max(min_w, w); h = max(min_h, h);
                 self.config.set('UI', 'width', str(w)); self.config.set('UI', 'height', str(h))
            except ValueError: logger.error(f"Kích thước cửa sổ không hợp lệ '{w_str}'x'{h_str}'."); messagebox.showerror("Lỗi Lưu", "Kích thước cửa sổ không hợp lệ."); return
            with open(config_path, 'w', encoding='utf-8') as f: self.config.write(f)
            self.update_status("Đã lưu cấu hình ứng dụng."); logger.info(f"Đã lưu cấu hình vào: {config_path}")
            self.apply_window_size(); messagebox.showinfo("Lưu Thành Công", "Đã lưu cấu hình kích thước cửa sổ.")
        except Exception as e: logger.error(f"Lỗi lưu cấu hình: {e}", exc_info=True); messagebox.showerror("Lỗi Lưu", f"Không thể lưu cấu hình:\n{e}")
    def apply_window_size(self):
        try:
            w = int(self.window_width_var.get()); h = int(self.window_height_var.get()); min_w, min_h = self.root.minsize(); w = max(min_w, w); h = max(min_h, h)
            self.root.geometry(f"{w}x{h}"); logger.info(f"Đã áp dụng kích thước cửa sổ: {w}x{h}")
        except ValueError: logger.warning("Giá trị kích thước không hợp lệ, không thể áp dụng.")
        except Exception as e: logger.error(f"Lỗi áp dụng kích thước cửa sổ: {e}", exc_info=True)

    # --- Data Handling (remains the same) ---
    def browse_data_file(self):
        logger.debug("Đang duyệt file dữ liệu..."); initial_dir = self.data_dir; current_path = self.data_file_path_var.get()
        if current_path and Path(current_path).is_file(): initial_dir = Path(current_path).parent
        filename = filedialog.askopenfilename(title="Chọn file dữ liệu JSON", initialdir=initial_dir, filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if filename: self.data_file_path_var.set(filename); logger.info(f"Người dùng chọn file: {filename}"); self.load_data()
    def load_data(self):
        logger.info("Đang tải dữ liệu xổ số..."); self.results_data = []
        data_file_str = self.data_file_path_var.get()
        if not data_file_str:
             default_path = self.data_dir / "xsmb-2-digits.json"
             if default_path.exists(): self.data_file_path_var.set(str(default_path)); data_file_str = str(default_path); logger.info(f"Đường dẫn trống, dùng mặc định: {data_file_str}")
             else: messagebox.showinfo("Chọn File Dữ Liệu", "Vui lòng chọn file dữ liệu JSON."); self.browse_data_file(); data_file_str = self.data_file_path_var.get()
             if not data_file_str: self.update_status("Chưa chọn file dữ liệu."); self.data_range_var.set("Chưa tải dữ liệu"); return
        data_file_path = Path(data_file_str); self.data_file_path_var.set(str(data_file_path))
        if not data_file_path.exists(): logger.error(f"Không tìm thấy file: {data_file_path}"); messagebox.showerror("Lỗi", f"File không tồn tại:\n{data_file_path}"); self.data_range_var.set("Lỗi file dữ liệu"); return
        try:
            with open(data_file_path, 'r', encoding='utf-8') as f: raw_data = json.load(f)
            processed_results = []; unique_dates = set(); data_list_to_process = []
            if isinstance(raw_data, list): data_list_to_process = raw_data; logger.debug("Định dạng dữ liệu: List dict.")
            elif isinstance(raw_data, dict) and 'results' in raw_data and isinstance(raw_data.get('results'), dict):
                 logger.info("Phát hiện định dạng dict cũ, đang chuyển đổi...");
                 for date_str, result_dict in raw_data['results'].items():
                     if isinstance(result_dict, dict): data_list_to_process.append({'date': date_str, 'result': result_dict})
                 logger.debug("Chuyển đổi hoàn tất.")
            else: raise ValueError("Định dạng JSON không hợp lệ.")
            for item in data_list_to_process:
                if not isinstance(item, dict): continue
                date_str_raw = item.get("date"); date_obj = None;
                if not date_str_raw: continue
                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']:
                    try: date_obj = datetime.datetime.strptime(str(date_str_raw).split('T')[0], '%Y-%m-%d').date(); break
                    except ValueError: continue
                if date_obj is None: logger.warning(f"Không phân tích được ngày '{date_str_raw}'. Bỏ qua."); continue
                if date_obj in unique_dates: logger.warning(f"Ngày trùng lặp: {date_obj}. Bỏ qua."); continue
                result_dict = item.get('result');
                if result_dict is None: result_dict = {k: v for k, v in item.items() if k != 'date'}
                if not result_dict: logger.warning(f"Mục ngày {date_obj} không có dữ liệu kết quả. Bỏ qua."); continue
                processed_results.append({'date': date_obj, 'result': result_dict}); unique_dates.add(date_obj)
            if processed_results:
                processed_results.sort(key=lambda x: x['date']); self.results_data = processed_results
                start_date = self.results_data[0]['date']; end_date = self.results_data[-1]['date']
                self.data_range_var.set(f"{start_date:%d/%m/%Y} - {end_date:%d/%m/%Y} ({len(self.results_data)} ngày)")
                self.update_status(f"Đã tải {len(self.results_data)} kết quả từ {data_file_path.name}"); logger.info(f"Đã tải thành công {len(self.results_data)} kết quả.")
                if not self.opt_start_date_var.get() and len(self.results_data) > 1: self.opt_start_date_var.set(start_date.strftime('%d/%m/%Y'))
                if not self.opt_end_date_var.get() and len(self.results_data) > 1: self.opt_end_date_var.set((end_date - datetime.timedelta(days=1)).strftime('%d/%m/%Y'))
            else: self.data_range_var.set("Không có dữ liệu hợp lệ"); self.update_status("Không tải được dữ liệu."); logger.warning("Không tải được dữ liệu hợp lệ sau khi xử lý.")
        except FileNotFoundError: logger.error(f"FileNotFoundError: {data_file_path}")
        except (json.JSONDecodeError, ValueError) as e: logger.error(f"JSON/Dữ liệu không hợp lệ trong {data_file_path.name}: {e}", exc_info=True); messagebox.showerror("Lỗi Dữ Liệu", f"File '{data_file_path.name}' không hợp lệ:\n{e}"); self.data_range_var.set("Lỗi định dạng file")
        except Exception as e: logger.error(f"Lỗi không mong muốn khi tải dữ liệu: {e}", exc_info=True); messagebox.showerror("Lỗi", f"Lỗi khi tải dữ liệu:\n{e}"); self.data_range_var.set("Lỗi tải dữ liệu")

    # --- Algorithm Handling (remains the same) ---
    def load_algorithms(self):
        logger.info("Đang tải thuật toán..."); self.loaded_algorithms.clear(); self.algo_tree.delete(*self.algo_tree.get_children())
        self.disable_edit_optimize_tabs(); self.update_status("Đang tải thuật toán...")
        if not self.algorithms_dir.is_dir(): logger.warning(f"Thiếu thư mục algorithms: {self.algorithms_dir}"); messagebox.showwarning("Thiếu Thư Mục", f"Không tìm thấy:\n{self.algorithms_dir}"); self.update_status("Lỗi: Thiếu thư mục thuật toán."); return
        try: algo_files = [f for f in self.algorithms_dir.glob('*.py') if f.is_file() and f.name not in ["__init__.py", "base.py"]]
        except Exception as e: logger.error(f"Lỗi quét thư mục algorithms: {e}", exc_info=True); messagebox.showerror("Lỗi", f"Lỗi đọc thư mục:\n{e}"); return
        logger.info(f"Tìm thấy các file thuật toán tiềm năng: {[f.name for f in algo_files]}"); count_success = 0; count_fail = 0
        data_copy_for_init = copy.deepcopy(self.results_data) if self.results_data else []; cache_dir_for_init = self.calculate_dir
        for f_path in algo_files:
            module_name = f"algorithms.{f_path.stem}"; instance=None; config=None; class_name=None; module_obj=None; display_name=f"{f_path.stem}({f_path.name})"
            try:
                logger.debug(f"Đang xử lý file: {f_path.name}");
                if module_name in sys.modules:
                    try: module_obj = reload(sys.modules[module_name]); logger.debug(f"Đã nạp lại module: {module_name}")
                    except Exception as reload_err: logger.warning(f"Nạp lại thất bại {module_name}: {reload_err}. Đang tải mới."); del sys.modules[module_name]; module_obj = None
                if module_obj is None:
                    spec = util.spec_from_file_location(module_name, f_path)
                    if spec and spec.loader: module_obj = util.module_from_spec(spec); sys.modules[module_name] = module_obj; spec.loader.exec_module(module_obj); logger.debug(f"Đã tải module mới: {module_name}")
                    else: raise ImportError(f"Không tạo được spec/loader cho {module_name}")
                if not module_obj: raise ImportError("Đối tượng module là None.")
                found_class = None
                for name, obj in inspect.getmembers(module_obj):
                    if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == module_name:
                        found_class = obj; class_name = name; display_name = f"{class_name} ({f_path.name})"; logger.info(f"Tìm thấy lớp thuật toán hợp lệ: {class_name}"); break
                if found_class:
                    try:
                        instance = found_class(data_results_list=data_copy_for_init, cache_dir=cache_dir_for_init); config = instance.get_config()
                        if not isinstance(config, dict): logger.warning(f"Config không phải dict cho {class_name}. Dùng mặc định."); config = {"description": "Lỗi config", "parameters": {}}
                        self.loaded_algorithms[display_name] = {'instance': instance, 'path': f_path, 'config': config, 'class_name': class_name, 'module_name': module_name}
                        desc = config.get("description", "N/A"); self.algo_tree.insert("", tk.END, iid=display_name, values=(class_name, f_path.name, desc)); count_success += 1; logger.debug(f"Đã tải: {display_name}")
                    except Exception as init_err: logger.error(f"Lỗi khởi tạo lớp {class_name} từ {f_path.name}: {init_err}", exc_info=True); count_fail += 1
                else: logger.warning(f"Không tìm thấy lớp con BaseAlgorithm hợp lệ trong {f_path.name}"); count_fail += 1
            except ImportError as imp_err: logger.error(f"Lỗi import khi xử lý {f_path.name}: {imp_err}", exc_info=True); count_fail += 1
            except Exception as load_err: logger.error(f"Lỗi không mong muốn khi xử lý {f_path.name}: {load_err}", exc_info=True); count_fail += 1
        status_msg = f"Đã tải {count_success} thuật toán";
        if count_fail > 0: status_msg += f" (lỗi: {count_fail})"; messagebox.showwarning("Lỗi Tải", f"Lỗi tải {count_fail} file. Kiểm tra log.")
        self.update_status(status_msg); logger.info(f"Tải thuật toán hoàn tất. Thành công: {count_success}, Thất bại: {count_fail}")
    def reload_algorithms(self):
        logger.info("Đang tải lại thuật toán..."); self.selected_algorithm_for_edit = None; self.selected_algorithm_for_optimize = None
        self.disable_edit_optimize_tabs(); self._clear_editor_fields()
        self._reset_advanced_opt_settings() # Reset advanced settings on reload
        self.load_algorithms()

    # --- Algorithm Selection and Tab Control (remains the same) ---
    def get_selected_algorithm_display_name(self):
        selected_item = self.algo_tree.focus(); return selected_item if selected_item and selected_item in self.loaded_algorithms else None
    def select_algo_for_edit(self):
        display_name = self.get_selected_algorithm_display_name()
        if not display_name: messagebox.showwarning("Chưa Chọn", "Chọn thuật toán để chỉnh sửa."); return
        logger.info(f"Đã chọn thuật toán để sửa: {display_name}"); self.selected_algorithm_for_edit = display_name; self.selected_algorithm_for_optimize = None
        # self._reset_advanced_opt_settings() # No need to reset if always visible
        self._clear_advanced_opt_fields() # Clear fields instead
        self.populate_editor(display_name);
        self.notebook.tab(1, state="normal")
        self.notebook.tab(2, state="disabled")
        self.notebook.select(1); self.update_status(f"Đang chỉnh sửa: {self.loaded_algorithms[display_name]['class_name']}")
    def select_algo_for_optimize(self):
        display_name = self.get_selected_algorithm_display_name()
        if not display_name: messagebox.showwarning("Chưa Chọn", "Chọn thuật toán để tối ưu hóa."); return
        if self.optimizer_running: messagebox.showerror("Đang Chạy", "Quá trình tối ưu khác đang chạy."); return
        logger.info(f"Đã chọn thuật toán để tối ưu: {display_name}"); self.selected_algorithm_for_optimize = display_name; self.selected_algorithm_for_edit = None
        # self._reset_advanced_opt_settings() # No need to reset if always visible
        self._clear_advanced_opt_fields() # Clear fields instead
        self.populate_optimizer_info(display_name);
        self.notebook.tab(1, state="disabled")
        self.notebook.tab(2, state="normal")
        self.notebook.select(2); self.update_status(f"Sẵn sàng tối ưu: {self.loaded_algorithms[display_name]['class_name']}")
        self._load_optimization_log()
        self._populate_advanced_optimizer_settings() # Populate advanced settings

    def disable_edit_optimize_tabs(self):
        if hasattr(self, 'notebook') and self.notebook.winfo_exists():
             try:
                 self.notebook.tab(1, state="disabled")
                 self.notebook.tab(2, state="disabled")
                 # self._reset_advanced_opt_settings() # No need to hide
                 self._clear_advanced_opt_fields() # Clear fields when optimize tab disabled
             except tk.TclError: pass

    # --- Editor Logic (remains the same conceptually) ---
    def populate_editor(self, display_name):
        self._clear_editor_fields()
        if display_name not in self.loaded_algorithms:
            logger.error(f"Cannot populate editor: Algorithm '{display_name}' not found.")
            return
        algo_data = self.loaded_algorithms[display_name]
        instance = algo_data['instance']
        config = algo_data['config']
        class_name = algo_data['class_name']
        self.edit_algo_name_label.config(text=f"{class_name} ({algo_data['path'].name})")
        self.edit_algo_desc_label.config(text=config.get("description", "N/A"))
        try:
            docstring = inspect.getdoc(instance.__class__)
            self.edit_explain_text.config(state=tk.NORMAL)
            self.edit_explain_text.delete(1.0, tk.END)
            self.edit_explain_text.insert(tk.END, docstring if docstring else "N/A")
            self.edit_explain_text.config(state=tk.DISABLED)
        except Exception as e:
            logger.warning(f"Docstring error {class_name}: {e}")
            self.edit_explain_text.config(state=tk.NORMAL)
            self.edit_explain_text.delete(1.0, tk.END)
            self.edit_explain_text.insert(tk.END, f"Lỗi: {e}")
            self.edit_explain_text.config(state=tk.DISABLED)
        parameters = config.get("parameters", {})
        self.editor_param_vars = {}
        self.editor_original_params = copy.deepcopy(parameters)
        row_idx = 0
        param_canvas = self.edit_param_scrollable_frame.master

        def _on_edit_mousewheel(event, c=param_canvas):
            delta = 0
            if event.num == 4: delta = -1
            elif event.num == 5: delta = 1
            elif hasattr(event, 'delta') and event.delta != 0: delta = -1 * int(event.delta / abs(event.delta) if abs(event.delta) > 3 else event.delta)
            if delta: c.yview_scroll(delta, "units")

        for name, value in parameters.items():
            frame = self.edit_param_scrollable_frame
            if isinstance(value, (int, float)):
                var = tk.StringVar(value=str(value))
                self.editor_param_vars[name] = var
                lbl = ttk.Label(frame, text=f"{name}:")
                lbl.grid(row=row_idx, column=0, padx=5, pady=3, sticky=tk.W)
                entry = ttk.Entry(frame, textvariable=var, width=15, justify=tk.RIGHT, validate='key', validatecommand=(self.validate_numeric_cmd, '%P'))
                entry.grid(row=row_idx, column=1, padx=5, pady=3, sticky=tk.EW)
                entry.bind("<MouseWheel>", _on_edit_mousewheel, add='+'); entry.bind("<Button-4>", _on_edit_mousewheel, add='+'); entry.bind("<Button-5>", _on_edit_mousewheel, add='+')
                lbl.bind("<MouseWheel>", _on_edit_mousewheel, add='+'); lbl.bind("<Button-4>", _on_edit_mousewheel, add='+'); lbl.bind("<Button-5>", _on_edit_mousewheel, add='+')
                row_idx += 1
            else:
                lbl_name = ttk.Label(frame, text=f"{name}:"); lbl_name.grid(row=row_idx, column=0, padx=5, pady=3, sticky=tk.W)
                lbl_val = ttk.Label(frame, text=str(value), style="Info.TLabel"); lbl_val.grid(row=row_idx, column=1, padx=5, pady=3, sticky=tk.W)
                lbl_name.bind("<MouseWheel>", _on_edit_mousewheel, add='+'); lbl_name.bind("<Button-4>", _on_edit_mousewheel, add='+'); lbl_name.bind("<Button-5>", _on_edit_mousewheel, add='+')
                lbl_val.bind("<MouseWheel>", _on_edit_mousewheel, add='+'); lbl_val.bind("<Button-4>", _on_edit_mousewheel, add='+'); lbl_val.bind("<Button-5>", _on_edit_mousewheel, add='+')
                row_idx += 1
        self.edit_param_scrollable_frame.columnconfigure(1, weight=1)
        self.edit_param_scrollable_frame.bind("<MouseWheel>", _on_edit_mousewheel, add='+'); self.edit_param_scrollable_frame.bind("<Button-4>", _on_edit_mousewheel, add='+'); self.edit_param_scrollable_frame.bind("<Button-5>", _on_edit_mousewheel, add='+')

    def _clear_editor_fields(self):
        self.edit_algo_name_label.config(text="..."); self.edit_algo_desc_label.config(text="..."); self.editor_param_vars = {}; self.editor_original_params = {}
        for widget in self.edit_param_scrollable_frame.winfo_children(): widget.destroy()
        self.edit_explain_text.config(state=tk.NORMAL); self.edit_explain_text.delete(1.0, tk.END); self.edit_explain_text.config(state=tk.DISABLED)
    def cancel_edit(self):
        logger.info("Editing cancelled."); self.selected_algorithm_for_edit = None; self._clear_editor_fields(); self.disable_edit_optimize_tabs(); self.notebook.select(0); self.update_status("Đã hủy chỉnh sửa.")
    def save_edited_copy(self):
        if not self.selected_algorithm_for_edit: logger.warning("Save copy no selection."); return
        display_name = self.selected_algorithm_for_edit
        if display_name not in self.loaded_algorithms: logger.error(f"Save copy error: {display_name} not loaded."); messagebox.showerror("Lỗi", "Thuật toán không tồn tại."); return
        algo_data = self.loaded_algorithms[display_name]; original_path = algo_data['path']; class_name = algo_data['class_name']; modified_params = {}
        try:
            for name, var in self.editor_param_vars.items():
                value_str = var.get(); original_value = self.editor_original_params.get(name)
                if isinstance(original_value, float): modified_params[name] = float(value_str)
                elif isinstance(original_value, int): modified_params[name] = int(value_str)
        except ValueError as e: logger.error(f"Invalid numeric: {e}", exc_info=True); messagebox.showerror("Giá Trị Lỗi", f"Nhập số hợp lệ.\nLỗi: {e}"); return
        final_params_for_save = self.editor_original_params.copy(); final_params_for_save.update(modified_params)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); suggested_filename = f"{original_path.stem}_edited_{timestamp}.py"
        save_path_str = filedialog.asksaveasfilename(title="Lưu Bản Sao", initialdir=self.algorithms_dir, initialfile=suggested_filename, defaultextension=".py", filetypes=[("Python", "*.py"), ("All", "*.*")])
        if not save_path_str: logger.info("Save copy cancelled."); return
        save_path = Path(save_path_str)
        if save_path.exists() and save_path.resolve() == original_path.resolve(): messagebox.showerror("Lỗi", "Không thể ghi đè file gốc."); logger.error("Overwrite original attempt."); return
        try:
            logger.info(f"Reading: {original_path}"); source_code = original_path.read_text(encoding='utf-8')
            logger.info("Modifying AST..."); modified_source = self.modify_algorithm_source_ast(source_code, class_name, final_params_for_save)
            if modified_source is None: raise ValueError("AST modification failed.")
            logger.info(f"Writing: {save_path}"); save_path.write_text(modified_source, encoding='utf-8')
            messagebox.showinfo("Lưu OK", f"Đã lưu:\n{save_path.name}\n\nVui lòng 'Tải lại'.")
            self.update_status(f"Đã lưu: {save_path.name}"); logger.info(f"Saved copy: {save_path}")
        except Exception as e: logger.error(f"Error saving copy: {e}", exc_info=True); messagebox.showerror("Lỗi Lưu", f"Không thể lưu:\n{e}")

    # --- AST Modification (remains the same) ---
    def modify_algorithm_source_ast(self, source_code, target_class_name, new_params):
        logger.debug(f"AST mod: Class '{target_class_name}' (Params & Imports)")
        try: tree = ast.parse(source_code)
        except SyntaxError as e: logger.error(f"Syntax error parsing: {e}", exc_info=True); return None
        class _SourceModifier(ast.NodeTransformer):
            def __init__(self, class_to_modify, params_to_update):
                self.target_class = class_to_modify; self.params_to_update = params_to_update; self.in_target_init = False; self.params_modified = False; self.imports_modified = False; self.current_class_name = None; super().__init__()
            def visit_ImportFrom(self, node):
                if node.level > 0 and node.module == 'base': logger.debug(f"Fixing import: '.{node.module}' -> 'algorithms.{node.module}'"); node.module = f'algorithms.{node.module}'; node.level = 0; self.imports_modified = True
                elif node.level > 0 and node.module is None: logger.warning(f"Cannot auto-fix 'from . import ...' line: {node.lineno}")
                return self.generic_visit(node)
            def visit_ClassDef(self, node):
                original_class = self.current_class_name; self.current_class_name = node.name
                if node.name == self.target_class: logger.debug(f"Found target class: {node.name}"); node.body = [self.visit(child) for child in node.body]
                else: self.generic_visit(node)
                self.current_class_name = original_class; return node
            def visit_FunctionDef(self, node):
                if node.name == '__init__' and self.current_class_name == self.target_class:
                     logger.debug(f"Entering __init__ of {self.target_class}"); self.in_target_init = True; node.body = [self.visit(child) for child in node.body]; self.in_target_init = False; logger.debug(f"Exiting __init__")
                else: self.generic_visit(node)
                return node
            def visit_Assign(self, node):
                if self.in_target_init and len(node.targets) == 1:
                    target = node.targets[0]
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self' and target.attr == 'config':
                        logger.debug("Found 'self.config' assign."); node.value = self.visit(node.value); return node
                return self.generic_visit(node)
            def visit_Dict(self, node):
                 if not self.in_target_init: return self.generic_visit(node)
                 param_key_index = -1; param_value_node = None
                 try:
                     for i, key_node in enumerate(node.keys):
                         if key_node is not None and isinstance(key_node, ast.Constant) and isinstance(key_node.value, str) and key_node.value == 'parameters':
                             param_key_index = i; param_value_node = node.values[i]; logger.debug("Found 'parameters' key."); break
                 except AttributeError: return self.generic_visit(node)
                 if param_key_index != -1 and isinstance(param_value_node, ast.Dict):
                     logger.debug("Processing 'parameters' sub-dict."); new_keys = []; new_values = []; modified_in_subdict = False
                     original_param_nodes = {}
                     if param_value_node.keys is not None:
                          original_param_nodes = {k.value: (k,v) for k, v in zip(param_value_node.keys, param_value_node.values) if isinstance(k, ast.Constant)}
                     for param_name, new_value in self.params_to_update.items():
                         if param_name in original_param_nodes:
                             p_key_node, p_val_node = original_param_nodes[param_name]; new_val_node = None
                             if isinstance(new_value, (int, float)): new_val_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=abs(new_value))) if new_value < 0 else ast.Constant(value=new_value)
                             elif isinstance(new_value, str): new_val_node = ast.Constant(value=new_value)
                             elif isinstance(new_value, bool): new_val_node = ast.Constant(value=new_value)
                             elif new_value is None: new_val_node = ast.Constant(value=None)
                             if new_val_node is not None: new_keys.append(p_key_node); new_values.append(new_val_node); logger.debug(f"Updated '{param_name}' node to {new_value}"); modified_in_subdict = True
                             else: logger.warning(f"Unsupported type for '{param_name}': {type(new_value)}. Keep original."); new_keys.append(p_key_node); new_values.append(p_val_node)
                         else: logger.warning(f"Update param '{param_name}' not in original. Skip.")
                     updated_keys = set(self.params_to_update.keys())
                     for name, (k_node, v_node) in original_param_nodes.items():
                          if name not in updated_keys: new_keys.append(k_node); new_values.append(v_node)
                     param_value_node.keys = new_keys; param_value_node.values = new_values
                     if modified_in_subdict: self.params_modified = True
                 return self.generic_visit(node)

        modifier = _SourceModifier(target_class_name, new_params); modified_tree = modifier.visit(tree)
        if not modifier.params_modified and not modifier.imports_modified: logger.warning("AST mod finished, no params updated.")
        try:
            if hasattr(ast, 'unparse'): modified_code = ast.unparse(modified_tree); logger.debug("Unparsed using ast.unparse")
            elif HAS_ASTOR: modified_code = astor.to_source(modified_tree); logger.debug("Unparsed using astor")
            else: logger.critical("AST unparsing failed. Need Py 3.9+ or 'astor'."); return None
        except Exception as unparse_err: logger.error(f"Error unparsing AST: {unparse_err}", exc_info=True); return None
        return modified_code

    # --- Optimizer Logic ---

    # _toggle_advanced_opt_frame REMOVED

    # _populate_advanced_optimizer_settings: Sets initial entry state
    def _populate_advanced_optimizer_settings(self):
        """Fills the advanced optimization frame with controls for numeric parameters."""
        logger.debug("Populating advanced optimization settings frame.")
        for widget in self.advanced_opt_params_frame.winfo_children():
            widget.destroy()
        self.advanced_opt_widgets.clear()

        if not self.selected_algorithm_for_optimize:
            ttk.Label(self.advanced_opt_params_frame, text="Chưa chọn thuật toán.", style="Info.TLabel").pack(padx=10, pady=10)
            return

        display_name = self.selected_algorithm_for_optimize
        if display_name not in self.loaded_algorithms:
            ttk.Label(self.advanced_opt_params_frame, text="Lỗi: Thuật toán không tìm thấy.", style="Error.TLabel").pack(padx=10, pady=10)
            logger.error(f"Cannot populate advanced opts: Algorithm '{display_name}' not found.")
            return

        algo_data = self.loaded_algorithms[display_name]
        parameters = algo_data['config'].get('parameters', {})
        numeric_params = {k: v for k, v in parameters.items() if isinstance(v, (int, float))}

        if not numeric_params:
            ttk.Label(self.advanced_opt_params_frame, text="Không có tham số số học để tùy chỉnh.", style="Info.TLabel").pack(padx=10, pady=10)
            return

        # Add header row
        header_frame = ttk.Frame(self.advanced_opt_params_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="Tham số", style="Bold.TLabel", width=18).grid(row=0, column=0, padx=5, sticky=tk.W)
        ttk.Label(header_frame, text="Giá trị gốc", style="Bold.TLabel", width=10).grid(row=0, column=1, padx=5, sticky=tk.W)
        ttk.Label(header_frame, text="Chế độ", style="Bold.TLabel", width=8).grid(row=0, column=2, padx=5, sticky=tk.W)
        ttk.Label(header_frame, text="Bước (+/-)", style="Bold.TLabel", width=15).grid(row=0, column=3, padx=5, sticky=tk.W)

        canvas = self.advanced_opt_params_frame.master
        if isinstance(canvas, tk.Canvas):
            for widget in header_frame.winfo_children():
                widget.bind("<MouseWheel>", lambda e, c=canvas: self._on_adv_opt_mousewheel(e, c), add='+')
                widget.bind("<Button-4>", lambda e, c=canvas: self._on_adv_opt_mousewheel(e, c), add='+')
                widget.bind("<Button-5>", lambda e, c=canvas: self._on_adv_opt_mousewheel(e, c), add='+')

        row_idx = 1
        for name, value in numeric_params.items():
            param_frame = ttk.Frame(self.advanced_opt_params_frame)
            param_frame.pack(fill=tk.X)

            if name not in self.optimizer_custom_steps:
                self.optimizer_custom_steps[name] = {'mode': 'Auto', 'steps': [], 'str_var': tk.StringVar()}
            param_state = self.optimizer_custom_steps[name]

            name_lbl = ttk.Label(param_frame, text=name, width=18, anchor=tk.W); name_lbl.grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
            value_lbl = ttk.Label(param_frame, text=f"{value:.4g}" if isinstance(value, float) else str(value), width=10, anchor=tk.W, style="Info.TLabel"); value_lbl.grid(row=0, column=1, padx=5, pady=3, sticky=tk.W)
            mode_combo = ttk.Combobox(param_frame, values=["Auto", "Custom"], width=8, state="readonly"); mode_combo.set(param_state['mode']); mode_combo.grid(row=0, column=2, padx=5, pady=3, sticky=tk.W)
            steps_entry = ttk.Entry(param_frame, textvariable=param_state['str_var'], width=15, validate='key', validatecommand=(self.validate_custom_steps_cmd, '%P')); steps_entry.grid(row=0, column=3, padx=5, pady=3, sticky=tk.W)

            # --- Set initial state based on mode ---
            steps_entry.config(state=tk.NORMAL if param_state['mode'] == 'Custom' else tk.DISABLED)
            # --- End initial state ---

            mode_combo.bind("<<ComboboxSelected>>", lambda event, n=name, m=mode_combo, e=steps_entry: self._on_step_mode_change(n, m, e))
            param_state['str_var'].trace_add("write", lambda *args, n=name, v=param_state['str_var']: self._update_custom_steps(n, v))
            self.advanced_opt_widgets[name] = {'mode_combo': mode_combo, 'steps_entry': steps_entry}

            if isinstance(canvas, tk.Canvas):
                for widget in param_frame.winfo_children():
                    widget.bind("<MouseWheel>", lambda e, c=canvas: self._on_adv_opt_mousewheel(e, c), add='+')
                    widget.bind("<Button-4>", lambda e, c=canvas: self._on_adv_opt_mousewheel(e, c), add='+')
                    widget.bind("<Button-5>", lambda e, c=canvas: self._on_adv_opt_mousewheel(e, c), add='+')
            row_idx += 1

        self.advanced_opt_params_frame.update_idletasks()
        if isinstance(canvas, tk.Canvas):
             canvas.configure(scrollregion=canvas.bbox("all"))
             canvas.yview_moveto(0)

    # _on_step_mode_change: Ensures entry state matches mode
    def _on_step_mode_change(self, param_name, mode_combo_widget, steps_entry_widget):
        """Handles the change event for the step mode Combobox."""
        new_mode = mode_combo_widget.get()
        if param_name in self.optimizer_custom_steps:
            self.optimizer_custom_steps[param_name]['mode'] = new_mode
            # Set state: NORMAL if Custom, DISABLED if Auto
            new_state = tk.NORMAL if new_mode == 'Custom' else tk.DISABLED
            steps_entry_widget.config(state=new_state)

            if new_mode == 'Auto':
                logger.debug(f"Parameter '{param_name}' step mode set to Auto.")
                # Clear validation error color if switching to Auto
                steps_entry_widget.config(foreground='black')
            else: # Custom mode
                 logger.debug(f"Parameter '{param_name}' step mode set to Custom.")
                 steps_entry_widget.focus_set()
                 # Re-validate/parse steps when switching TO custom
                 self._update_custom_steps(param_name, self.optimizer_custom_steps[param_name]['str_var'])
        else:
            logger.warning(f"Parameter '{param_name}' not found in custom steps state during mode change.")

    # _update_custom_steps remains the same
    def _update_custom_steps(self, param_name, steps_var):
        """Parses the custom steps string and updates the state."""
        steps_str = steps_var.get()
        if param_name in self.optimizer_custom_steps:
            if self.optimizer_custom_steps[param_name]['mode'] == 'Custom':
                is_valid = self._validate_custom_steps_input(steps_str)
                entry_widget = self.advanced_opt_widgets.get(param_name, {}).get('steps_entry')
                if entry_widget:
                     entry_widget.config(foreground='black' if is_valid else 'red')
                if not is_valid:
                    if self.optimizer_custom_steps[param_name]['steps']: self.optimizer_custom_steps[param_name]['steps'] = []
                    return
                parsed_steps = []
                parts = steps_str.split(',')
                try:
                    if self.selected_algorithm_for_optimize and self.selected_algorithm_for_optimize in self.loaded_algorithms:
                        original_value = self.loaded_algorithms[self.selected_algorithm_for_optimize]['config']['parameters'].get(param_name)
                        if original_value is None: raise KeyError(f"Original value for {param_name} not found.")
                    else: raise ValueError("Algorithm not selected/loaded for type check.")
                    for part in parts:
                        part = part.strip()
                        if part:
                            num_val = float(part)
                            if isinstance(original_value, int): parsed_steps.append(int(num_val))
                            else: parsed_steps.append(num_val)
                    if parsed_steps != self.optimizer_custom_steps[param_name].get('steps'):
                        self.optimizer_custom_steps[param_name]['steps'] = parsed_steps
                        logger.debug(f"Updated custom steps for '{param_name}': {parsed_steps}")
                except (ValueError, KeyError, TypeError) as e:
                    logger.error(f"Error parsing steps for '{param_name}': '{steps_str}' ({e})")
                    self.optimizer_custom_steps[param_name]['steps'] = []
                    if entry_widget: entry_widget.config(foreground='red')
        else:
            logger.warning(f"Param '{param_name}' not found during custom steps update.")

    # _reset_advanced_opt_settings: Simplified, no hide logic
    def _reset_advanced_opt_settings(self):
        """Clears custom step data and widgets inside the advanced frame."""
        logger.debug("Resetting advanced optimization settings fields.")
        self.optimizer_custom_steps.clear()
        for widget in self.advanced_opt_params_frame.winfo_children():
            widget.destroy()
        self.advanced_opt_widgets.clear()
        # Add back the placeholder label
        ttk.Label(self.advanced_opt_params_frame, text="Chọn thuật toán để xem tham số.", style="Info.TLabel").pack(padx=10, pady=10)

    # NEW: Helper to clear advanced fields without removing frame
    def _clear_advanced_opt_fields(self):
         """Clears widgets and data related to advanced optimization settings."""
         logger.debug("Clearing advanced optimization fields.")
         self.optimizer_custom_steps.clear()
         for widget in self.advanced_opt_params_frame.winfo_children():
            widget.destroy()
         self.advanced_opt_widgets.clear()
         ttk.Label(self.advanced_opt_params_frame, text="Chọn thuật toán để xem tham số.", style="Info.TLabel").pack(padx=10, pady=10)


    def populate_optimizer_info(self, display_name):
        if display_name in self.loaded_algorithms: class_name = self.loaded_algorithms[display_name]['class_name']; self.opt_algo_name_label.config(text=f"{class_name} ({self.loaded_algorithms[display_name]['path'].name})")
        else: self.opt_algo_name_label.config(text="Lỗi: Không tìm thấy")

    # start_optimization remains the same
    def start_optimization(self):
        if self.optimizer_running: messagebox.showwarning("Đang Chạy", "Tối ưu hóa đang chạy."); return
        if not self.selected_algorithm_for_optimize: messagebox.showerror("Lỗi", "Chưa chọn thuật toán."); return
        display_name = self.selected_algorithm_for_optimize
        if display_name not in self.loaded_algorithms: messagebox.showerror("Lỗi", f"Thuật toán '{display_name}' không còn."); return

        algo_data = self.loaded_algorithms[display_name]; original_params = algo_data['config'].get('parameters', {})
        numeric_params = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}
        if not numeric_params: messagebox.showinfo("Thông Báo", "Không có tham số số học để tối ưu."); return
        start_s = self.opt_start_date_var.get(); end_s = self.opt_end_date_var.get()
        if not start_s or not end_s: messagebox.showwarning("Thiếu Ngày", "Chọn ngày BĐ/KT."); return
        try: start_d = datetime.datetime.strptime(start_s, '%d/%m/%Y').date(); end_d = datetime.datetime.strptime(end_s, '%d/%m/%Y').date()
        except ValueError: messagebox.showerror("Lỗi Ngày", "Định dạng ngày sai (dd/mm/yyyy)."); return
        if start_d > end_d: messagebox.showwarning("Ngày Lỗi", "Ngày BĐ phải <= ngày KT."); return
        if not self.results_data or len(self.results_data) < 2: messagebox.showerror("Thiếu Dữ Liệu", "Cần >= 2 ngày dữ liệu."); return
        min_data_date = self.results_data[0]['date']; max_data_date = self.results_data[-1]['date']
        if start_d < min_data_date or end_d >= max_data_date: messagebox.showerror("Lỗi Khoảng Ngày", f"Khoảng ngày ({start_s} - {end_s}) lỗi.\nYêu cầu: [{min_data_date:%d/%m/%Y} - {max_data_date:%d/%m/%Y}) (ngày KT < ngày cuối)."); return
        try: time_limit_min = int(self.opt_time_limit_var.get()); assert time_limit_min > 0
        except (ValueError, AssertionError): messagebox.showerror("Lỗi Thời Gian", "Nhập số phút > 0."); return

        final_custom_steps_config = {}
        has_invalid_custom_steps = False
        invalid_params = []
        for name, state in self.optimizer_custom_steps.items():
            mode = state.get('mode', 'Auto')
            steps = []
            steps_str = state.get('str_var', tk.StringVar()).get()
            if mode == 'Custom':
                if self._validate_custom_steps_input(steps_str):
                    parts = steps_str.split(',')
                    try:
                        parsed = []
                        original_value = original_params[name]
                        for part in parts:
                            part = part.strip()
                            if part:
                                num_val = float(part)
                                if isinstance(original_value, int): parsed.append(int(num_val))
                                else: parsed.append(num_val)
                        if parsed: steps = parsed
                        else: mode = 'Auto'; steps = []
                    except (ValueError, KeyError) as parse_err:
                        logger.error(f"Lỗi parse cuối cho '{name}': {parse_err}. Dùng Auto.")
                        mode = 'Auto'; steps = []; has_invalid_custom_steps = True; invalid_params.append(name)
                else:
                     logger.warning(f"Bước tùy chỉnh không hợp lệ cho '{name}' khi bắt đầu: '{steps_str}'. Dùng Auto.")
                     mode = 'Auto'; steps = []; has_invalid_custom_steps = True; invalid_params.append(name)
            final_custom_steps_config[name] = {'mode': mode, 'steps': steps}
            if mode == 'Custom': logger.info(f"Opt Start Prep - Param '{name}': Mode=Custom, Steps={steps}")
            else: logger.info(f"Opt Start Prep - Param '{name}': Mode=Auto")

        if has_invalid_custom_steps:
            messagebox.showwarning("Bước Không Hợp Lệ", f"Một số bước tùy chỉnh không hợp lệ:\n{', '.join(invalid_params)}\n\nChế độ 'Auto' sẽ được sử dụng.")
            for name in invalid_params:
                 if name in self.advanced_opt_widgets:
                      self.advanced_opt_widgets[name]['mode_combo'].set('Auto')
                      self.advanced_opt_widgets[name]['steps_entry'].config(state=tk.DISABLED, foreground='black')
                      if name in self.optimizer_custom_steps: self.optimizer_custom_steps[name]['mode'] = 'Auto'

        self.current_optimize_target_dir = self.optimize_dir / algo_data['path'].stem; self.current_optimize_target_dir.mkdir(parents=True, exist_ok=True)
        success_dir = self.current_optimize_target_dir / "success"; success_dir.mkdir(parents=True, exist_ok=True); self.current_optimization_log_path = self.current_optimize_target_dir / "optimization.log"
        self.opt_log_text.config(state=tk.NORMAL); self.opt_log_text.delete(1.0, tk.END); self.opt_log_text.config(state=tk.DISABLED)
        self._clear_cache_directory()
        self.optimizer_stop_event.clear(); self.optimizer_pause_event.clear(); self.optimizer_running = True; self.optimizer_paused = False
        self.opt_progressbar['value'] = 0; self.opt_progress_pct_var.set("0%")
        self.update_optimizer_ui_state()

        self.optimizer_thread = threading.Thread(
            target=self._optimization_worker,
            args=(display_name, start_d, end_d, time_limit_min * 60, final_custom_steps_config),
            name=f"Optimizer-{algo_data['path'].stem}",
            daemon=True
        )
        self.optimizer_thread.start(); self.root.after(100, self._check_optimizer_queue); self.update_status(f"Bắt đầu tối ưu: {algo_data['class_name']}...")

    # pause_optimization remains the same
    def pause_optimization(self):
        if self.optimizer_running and not self.optimizer_paused:
            self.optimizer_pause_event.set(); self.optimizer_paused = True; self.update_optimizer_ui_state(); self.update_status("Đã tạm dừng."); logger.info("Optimization paused.")
            self._log_to_optimizer_display("INFO", "[CONTROL] Tạm dừng.")
    # resume_optimization remains the same
    def resume_optimization(self):
        if self.optimizer_running and self.optimizer_paused:
            self.optimizer_pause_event.clear(); self.optimizer_paused = False; self.update_optimizer_ui_state(); self.update_status("Tiếp tục tối ưu..."); logger.info("Optimization resumed.")
            self._log_to_optimizer_display("INFO", "[CONTROL] Tiếp tục.")
    # stop_optimization remains the same
    def stop_optimization(self):
        if self.optimizer_running:
             if messagebox.askyesno("Xác Nhận Dừng", "Dừng tối ưu? Sẽ hoàn thành vòng hiện tại."):
                self.optimizer_stop_event.set(); self.opt_start_button.config(state=tk.DISABLED); self.opt_pause_button.config(text="Đang dừng...", state=tk.DISABLED); self.opt_stop_button.config(state=tk.DISABLED)
                self.update_status("Đang yêu cầu dừng..."); logger.info("Stop requested.")
                self._log_to_optimizer_display("WARNING", "[CONTROL] Yêu cầu dừng...")

    # update_optimizer_ui_state: Simplified, no toggle button logic
    def update_optimizer_ui_state(self):
        # Basic controls
        if self.optimizer_running:
            if self.optimizer_paused: self.opt_start_button.config(state=tk.DISABLED); self.opt_pause_button.config(text="Tiếp tục", command=self.resume_optimization, state=tk.NORMAL, style="Warning.TButton"); self.opt_stop_button.config(state=tk.NORMAL)
            else: self.opt_start_button.config(state=tk.DISABLED); self.opt_pause_button.config(text="Tạm dừng", command=self.pause_optimization, state=tk.NORMAL, style="Warning.TButton"); self.opt_stop_button.config(state=tk.NORMAL)
        else: self.opt_start_button.config(state=tk.NORMAL); self.opt_pause_button.config(text="Tạm dừng", command=self.pause_optimization, state=tk.DISABLED); self.opt_stop_button.config(state=tk.DISABLED); self.opt_status_var.set("Trạng thái: Chờ"); self.opt_progress_pct_var.set("0%")

        # Advanced settings controls
        # self.advanced_opt_toggle_button.config(state=adv_state) # REMOVED
        for name, widgets in self.advanced_opt_widgets.items():
             if self.optimizer_running:
                 widgets['mode_combo'].config(state=tk.DISABLED)
                 widgets['steps_entry'].config(state=tk.DISABLED)
             else: # Not running, enable based on mode
                 widgets['mode_combo'].config(state='readonly')
                 current_mode = 'Auto'
                 if name in self.optimizer_custom_steps:
                     current_mode = self.optimizer_custom_steps[name].get('mode', 'Auto')
                 widgets['steps_entry'].config(state=tk.NORMAL if current_mode == 'Custom' else tk.DISABLED)


    # _check_optimizer_queue remains the same
    def _check_optimizer_queue(self):
        """Kiểm tra queue định kỳ để nhận thông điệp từ luồng tối ưu."""
        try:
            while True:
                message = self.optimizer_queue.get_nowait()
                msg_type = message.get("type")
                payload = message.get("payload")
                if msg_type == "log":
                    level = payload.get("level", "INFO"); text = payload.get("text", ""); tag = payload.get("tag")
                    self._log_to_optimizer_display(level, text, tag)
                elif msg_type == "status": self.opt_status_var.set(f"Trạng thái: {payload}")
                elif msg_type == "progress":
                    progress_val = payload * 100; self.opt_progressbar['value'] = progress_val; self.opt_progress_pct_var.set(f"{progress_val:.0f}%")
                elif msg_type == "best_update":
                    self.current_best_params = payload.get("params"); self.current_best_score = payload.get("score", -1.0)
                elif msg_type == "finished":
                    self.optimizer_running = False; self.optimizer_paused = False; self.update_optimizer_ui_state()
                    final_message = payload.get("message", "Hoàn tất."); success = payload.get("success", False)
                    if success: self.update_status(final_message); self._log_to_optimizer_display("BEST", f"[HOÀN TẤT] {final_message}"); messagebox.showinfo("Hoàn Tất", final_message)
                    else: self.update_status(f"Kết thúc: {final_message}"); self._log_to_optimizer_display("ERROR", f"[KẾT THÚC] {final_message}"); messagebox.showwarning("Kết Thúc", f"Kết thúc:\n{final_message}")
                    self.opt_progress_pct_var.set("100%"); self.optimizer_thread = None; return
                elif msg_type == "error": self._log_to_optimizer_display("ERROR", f"[LỖI LUỒNG] {payload}")
        except queue.Empty: pass
        except Exception as e: logger.error(f"Lỗi xử lý optimizer queue: {e}", exc_info=True)
        if self.optimizer_running: self.root.after(200, self._check_optimizer_queue)

    # _log_to_optimizer_display remains the same
    def _log_to_optimizer_display(self, level, text, tag=None):
        """Logs message to file, console (if applicable), and the optimizer log ScrolledText widget."""
        try:
            log_method = getattr(logger, level.lower(), logger.info); log_method(f"[Optimizer] {text}")
            if hasattr(self, 'opt_log_text') and self.opt_log_text.winfo_exists():
                self.opt_log_text.config(state=tk.NORMAL); timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                display_tag = tag if tag and tag in self.opt_log_text.tag_names() else level.upper()
                if display_tag not in self.opt_log_text.tag_names(): display_tag = "INFO"
                self.opt_log_text.insert(tk.END, f"{timestamp} [{level.upper()}] {text}\n", display_tag)
                self.opt_log_text.see(tk.END); self.opt_log_text.config(state=tk.DISABLED)
                if self.current_optimization_log_path:
                    try:
                        with open(self.current_optimization_log_path, "a", encoding="utf-8") as f: f.write(f"{datetime.datetime.now().isoformat()} [{level.upper()}] {text}\n")
                    except Exception as log_write_err: logger.error(f"Không ghi vào log tối ưu {self.current_optimization_log_path}: {log_write_err}")
        except tk.TclError: logger.warning("Widget log tối ưu không còn.")
        except Exception as e: logger.error(f"Lỗi ghi log display/file: {e}", exc_info=True)

    # _optimization_worker: Corrected Indentation
    def _optimization_worker(self, display_name, start_date, end_date, time_limit_sec, custom_steps_config):
        start_time = time.time()
        # --- Setup code ---
        algo_data = self.loaded_algorithms[display_name]
        original_path = algo_data['path']
        class_name = algo_data['class_name']
        original_params = algo_data['config'].get('parameters', {})
        source_code = original_path.read_text(encoding='utf-8')
        target_dir = self.current_optimize_target_dir
        params_to_optimize = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}
        param_names_ordered = list(params_to_optimize.keys())
        if not param_names_ordered:
            self.optimizer_queue.put({"type": "finished", "payload": {"message": "Không có tham số số học.", "success": False}})
            return

        # --- Queue Helpers ---
        def queue_log(level, text, tag=None): self.optimizer_queue.put({"type": "log", "payload": {"level": level, "text": text, "tag": tag}})
        def queue_status(text): self.optimizer_queue.put({"type": "status", "payload": text})
        def queue_progress(value): self.optimizer_queue.put({"type": "progress", "payload": value})
        def queue_best_update(params, score): self.optimizer_queue.put({"type": "best_update", "payload": {"params": params, "score": score}})
        def queue_finished(message, success=True): self.optimizer_queue.put({"type": "finished", "payload": {"message": message, "success": success}})
        def queue_error(text): self.optimizer_queue.put({"type": "error", "payload": text})
        def run_perf_test_wrapper(params_test, start_dt, end_dt): return self.run_performance_test(source_code, class_name, params_test, start_dt, end_dt, target_dir)

        # --- Initial Run & Setup ---
        queue_log("INFO", f"Bắt đầu tối ưu {class_name}"); queue_log("INFO", f"Tham số gốc: {params_to_optimize}"); queue_log("INFO", f"Khoảng test: {start_date:%d/%m/%Y} - {end_date:%d/%m/%Y}")
        queue_status("Test tham số gốc..."); queue_progress(0.0)
        initial_perf = run_perf_test_wrapper(original_params, start_date, end_date)
        if initial_perf is None: queue_finished("Lỗi test ban đầu.", success=False); return

        def get_primary_score(perf_dict):
            if not perf_dict: return (-1.0, -1.0, -1.0, -100.0)
            return (perf_dict.get('acc_top_3_pct', 0.0), perf_dict.get('acc_top_5_pct', 0.0), perf_dict.get('acc_top_1_pct', 0.0), -perf_dict.get('avg_top10_repetition', 100.0))

        current_best_params = original_params.copy(); current_best_perf = initial_perf; current_best_score_tuple = get_primary_score(current_best_perf)
        queue_log("INFO", f"Perf gốc: Top3={initial_perf.get('acc_top_3_pct', 0.0):.2f}%, Top5={initial_perf.get('acc_top_5_pct', 0.0):.2f}%, Top1={initial_perf.get('acc_top_1_pct', 0.0):.2f}%, Lặp={initial_perf.get('avg_top10_repetition', 0.0):.2f}")
        queue_best_update(current_best_params, list(current_best_score_tuple))
        try:
            best_py_path = target_dir / "best_performing.py"; mod_src = self.modify_algorithm_source_ast(source_code, class_name, current_best_params)
            if mod_src: best_py_path.write_text(mod_src, encoding='utf-8')
            best_params_path = target_dir / "best_params.json"; save_data = {"params": current_best_params, "performance": current_best_perf, "score_tuple": list(current_best_score_tuple)}
            best_params_path.write_text(json.dumps(save_data, indent=4), encoding='utf-8'); queue_log("DEBUG", f"Lưu kết quả gốc vào {target_dir.name}")
        except Exception as save_err: queue_log("ERROR", f"Lỗi lưu kết quả gốc: {save_err}")

        # --- Optimization Loop ---
        MAX_ITERATIONS_PER_PARAM_AUTO = 10; STALL_THRESHOLD = 2; MAX_FULL_CYCLES = 5; steps_done = 0
        for cycle in range(MAX_FULL_CYCLES):
            queue_log("INFO", f"--- Chu kỳ Tối ưu {cycle + 1}/{MAX_FULL_CYCLES} ---"); params_changed_in_cycle = False
            for param_idx, param_name in enumerate(param_names_ordered):

                # --- FIX: Correct Indentation ---
                # Check Pause/Stop
                if self.optimizer_stop_event.is_set(): break # Level 3 indent (inside outer for)
                while self.optimizer_pause_event.is_set():     # Level 3 indent
                    queue_status("Đã tạm dừng...")         # Level 4 indent
                    time.sleep(0.5)                     # Level 4 indent
                    if self.optimizer_stop_event.is_set(): break # Level 4 indent (inside while)
                if self.optimizer_stop_event.is_set(): break # Level 3 indent (after while)
                # --- End Fix ---

                # --- Decide Step Mode ---
                param_opt_config = custom_steps_config.get(param_name, {'mode': 'Auto', 'steps': []})
                mode = param_opt_config['mode']; custom_steps = param_opt_config['steps']
                original_value_for_turn = current_best_params[param_name]; is_float = isinstance(original_value_for_turn, float)

                if mode == 'Custom' and custom_steps:
                    # --- Custom Step Logic ---
                    queue_log("INFO", f"Optimize {param_name} (Custom, Steps: {custom_steps})", tag="CUSTOM_STEP"); best_value_this_param = current_best_params[param_name]
                    for step_val in custom_steps: # Positive
                        if self.optimizer_stop_event.is_set() or time.time() - start_time > time_limit_sec: break;
                        if step_val == 0: continue
                        test_params = current_best_params.copy(); new_value = best_value_this_param + step_val
                        test_params[param_name] = float(f"{new_value:.6g}") if is_float else int(new_value)
                        queue_status(f"Thử custom +: {param_name}={test_params[param_name]:.4f} ({step_val})..."); perf_result = run_perf_test_wrapper(test_params, start_date, end_date); steps_done += 1; queue_progress(min(0.95, (time.time() - start_time) / time_limit_sec))
                        if perf_result:
                            new_score = get_primary_score(perf_result); queue_log("DEBUG", f"  (+) Điểm={new_score}", tag="CUSTOM_STEP")
                            if new_score > current_best_score_tuple:
                                queue_log("BEST", f"  -> Improve (+ custom)! {param_name}={test_params[param_name]:.4f}. Score: {new_score}", tag="BEST")
                                current_best_params = test_params.copy(); current_best_perf = perf_result; current_best_score_tuple = new_score; best_value_this_param = new_value
                                queue_best_update(current_best_params, list(current_best_score_tuple)); params_changed_in_cycle = True
                                try:
                                    best_py_path = target_dir / "best_performing.py"; mod_src = self.modify_algorithm_source_ast(source_code, class_name, current_best_params);
                                    if mod_src: best_py_path.write_text(mod_src, encoding='utf-8')
                                    best_params_path = target_dir / "best_params.json"; save_data = {"params": current_best_params, "performance": current_best_perf, "score_tuple": list(current_best_score_tuple)}; best_params_path.write_text(json.dumps(save_data, indent=4), encoding='utf-8')
                                except Exception as save_err: queue_log("ERROR", f"Lỗi lưu best (custom +): {save_err}")
                        else: queue_log("WARNING", f"  -> Test lỗi + custom {param_name}={test_params[param_name]:.4f}.", tag="WARNING")
                    for step_val in custom_steps: # Negative
                        if self.optimizer_stop_event.is_set() or time.time() - start_time > time_limit_sec: break;
                        if step_val == 0: continue
                        test_params = current_best_params.copy(); new_value = best_value_this_param - step_val
                        test_params[param_name] = float(f"{new_value:.6g}") if is_float else int(new_value)
                        queue_status(f"Thử custom -: {param_name}={test_params[param_name]:.4f} ({step_val})..."); perf_result = run_perf_test_wrapper(test_params, start_date, end_date); steps_done += 1; queue_progress(min(0.95, (time.time() - start_time) / time_limit_sec))
                        if perf_result:
                            new_score = get_primary_score(perf_result); queue_log("DEBUG", f"  (-) Điểm={new_score}", tag="CUSTOM_STEP")
                            if new_score > current_best_score_tuple:
                                queue_log("BEST", f"  -> Improve (- custom)! {param_name}={test_params[param_name]:.4f}. Score: {new_score}", tag="BEST")
                                current_best_params = test_params.copy(); current_best_perf = perf_result; current_best_score_tuple = new_score; best_value_this_param = new_value
                                queue_best_update(current_best_params, list(current_best_score_tuple)); params_changed_in_cycle = True
                                try:
                                    best_py_path = target_dir / "best_performing.py"; mod_src = self.modify_algorithm_source_ast(source_code, class_name, current_best_params);
                                    if mod_src: best_py_path.write_text(mod_src, encoding='utf-8')
                                    best_params_path = target_dir / "best_params.json"; save_data = {"params": current_best_params, "performance": current_best_perf, "score_tuple": list(current_best_score_tuple)}; best_params_path.write_text(json.dumps(save_data, indent=4), encoding='utf-8')
                                except Exception as save_err: queue_log("ERROR", f"Lỗi lưu best (custom -): {save_err}")
                        else: queue_log("WARNING", f"  -> Test lỗi - custom {param_name}={test_params[param_name]:.4f}.", tag="WARNING")
                else: # Auto Mode
                    # --- Auto Step Logic (Hill Climbing) ---
                    step = abs(original_value_for_turn) * 0.05 if abs(original_value_for_turn) > 1 else (0.05 if abs(original_value_for_turn) > 0.01 else 0.001)
                    if not is_float: step = max(1, int(step))
                    elif step == 0: step = 0.001
                    queue_log("INFO", f"Optimize {param_name} (Auto, Val={current_best_params[param_name]:.4f}, Step={step:.4f})")
                    no_improve_inc = 0; params_at_inc_start = current_best_params.copy(); current_val_inc = params_at_inc_start[param_name]
                    for i in range(MAX_ITERATIONS_PER_PARAM_AUTO): # Increase
                        if self.optimizer_stop_event.is_set() or time.time() - start_time > time_limit_sec: break
                        test_params = params_at_inc_start.copy(); current_val_inc += step; test_params[param_name] = float(f"{current_val_inc:.6g}") if is_float else int(current_val_inc)
                        queue_status(f"Thử tăng (auto): {param_name}={test_params[param_name]:.4f}..."); perf_result = run_perf_test_wrapper(test_params, start_date, end_date); steps_done += 1; queue_progress(min(0.95, (time.time() - start_time) / time_limit_sec))
                        if perf_result:
                            new_score = get_primary_score(perf_result); queue_log("DEBUG", f"  (+) Điểm={new_score}")
                            if new_score > current_best_score_tuple:
                                queue_log("BEST", f"  -> Improve (+ auto)! {param_name}={test_params[param_name]:.4f}. Score: {new_score}")
                                current_best_params = test_params.copy(); current_best_perf = perf_result; current_best_score_tuple = new_score; queue_best_update(current_best_params, list(current_best_score_tuple)); params_changed_in_cycle = True; no_improve_inc = 0
                                try:
                                    best_py_path = target_dir / "best_performing.py"; mod_src = self.modify_algorithm_source_ast(source_code, class_name, current_best_params);
                                    if mod_src: best_py_path.write_text(mod_src, encoding='utf-8')
                                    best_params_path = target_dir / "best_params.json"; save_data = {"params": current_best_params, "performance": current_best_perf, "score_tuple": list(current_best_score_tuple)}; best_params_path.write_text(json.dumps(save_data, indent=4), encoding='utf-8')
                                except Exception as save_err: queue_log("ERROR", f"Lỗi lưu best (auto +): {save_err}")
                            else: no_improve_inc += 1; queue_log("DEBUG", f"  -> No improve (+ auto, streak={no_improve_inc}).")
                            if no_improve_inc >= STALL_THRESHOLD: queue_log("DEBUG", f"  -> Stop increase (auto) {param_name}."); break
                        else: no_improve_inc += 1; queue_log("WARNING", f"  -> Test error + auto {param_name}={test_params[param_name]:.4f}.")
                        if no_improve_inc >= STALL_THRESHOLD: break
                    no_improve_dec = 0; params_at_dec_start = current_best_params.copy(); current_val_dec = params_at_dec_start[param_name]
                    for i in range(MAX_ITERATIONS_PER_PARAM_AUTO): # Decrease
                        if self.optimizer_stop_event.is_set() or time.time() - start_time > time_limit_sec: break
                        test_params = params_at_dec_start.copy(); current_val_dec -= step; test_params[param_name] = float(f"{current_val_dec:.6g}") if is_float else int(current_val_dec)
                        queue_status(f"Thử giảm (auto): {param_name}={test_params[param_name]:.4f}..."); perf_result = run_perf_test_wrapper(test_params, start_date, end_date); steps_done += 1; queue_progress(min(0.95, (time.time() - start_time) / time_limit_sec))
                        if perf_result:
                            new_score = get_primary_score(perf_result); queue_log("DEBUG", f"  (-) Điểm={new_score}")
                            if new_score > current_best_score_tuple:
                                queue_log("BEST", f"  -> Improve (- auto)! {param_name}={test_params[param_name]:.4f}. Score: {new_score}")
                                current_best_params = test_params.copy(); current_best_perf = perf_result; current_best_score_tuple = new_score; queue_best_update(current_best_params, list(current_best_score_tuple)); params_changed_in_cycle = True; no_improve_dec = 0
                                try:
                                    best_py_path = target_dir / "best_performing.py"; mod_src = self.modify_algorithm_source_ast(source_code, class_name, current_best_params);
                                    if mod_src: best_py_path.write_text(mod_src, encoding='utf-8')
                                    best_params_path = target_dir / "best_params.json"; save_data = {"params": current_best_params, "performance": current_best_perf, "score_tuple": list(current_best_score_tuple)}; best_params_path.write_text(json.dumps(save_data, indent=4), encoding='utf-8')
                                except Exception as save_err: queue_log("ERROR", f"Lỗi lưu best (auto -): {save_err}")
                            else: no_improve_dec += 1; queue_log("DEBUG", f"  -> No improve (- auto, streak={no_improve_dec}).")
                            if no_improve_dec >= STALL_THRESHOLD: queue_log("DEBUG", f"  -> Stop decrease (auto) {param_name}."); break
                        else: no_improve_dec += 1; queue_log("WARNING", f"  -> Test error - auto {param_name}={test_params[param_name]:.4f}.")
                        if no_improve_dec >= STALL_THRESHOLD: break

                # --- End of Auto/Custom Logic ---
                if self.optimizer_stop_event.is_set() or time.time() - start_time > time_limit_sec: break # Check after each parameter

            # --- End of Parameter Loop ---
            if time.time() - start_time > time_limit_sec or self.optimizer_stop_event.is_set(): break # Check after cycle
            if not params_changed_in_cycle: queue_log("INFO", f"No improve cycle {cycle + 1}. End early."); break # End early if no improvement

        # --- Final Reporting ---
        queue_progress(1.0); final_message = ""
        if self.optimizer_stop_event.is_set(): final_message = "Dừng bởi user. Kết quả tốt nhất đã lưu."
        elif time.time() - start_time > time_limit_sec: final_message = f"Hết giờ ({time_limit_sec/60:.0f} phút). Kết quả tốt nhất đã lưu."
        else: final_message = "Tối ưu hoàn tất. Kết quả tốt nhất đã lưu."
        queue_log("BEST", "="*10 + " TỐI ƯU HOÀN TẤT " + "="*10)
        queue_log("BEST", f"Params tốt nhất: {current_best_params}")
        score_desc = "(Top3%, Top5%, Top1%, -AvgRepT10)"; queue_log("BEST", f"Score tốt nhất {score_desc}: {current_best_score_tuple}")
        perf_details = (f"Hiệu suất: Top3={current_best_perf.get('acc_top_3_pct', 0.0):.2f}%, Top5={current_best_perf.get('acc_top_5_pct', 0.0):.2f}%, Top1={current_best_perf.get('acc_top_1_pct', 0.0):.2f}%, Lặp T10={current_best_perf.get('avg_top10_repetition', 0.0):.2f}")
        queue_log("BEST", perf_details)
        try:
            final_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); success_dir = target_dir / "success"; success_dir.mkdir(exist_ok=True)
            perf_str = f"top3_{current_best_perf.get('acc_top_3_pct', 0.0):.1f}"; success_filename_py = f"optimized_{algo_data['path'].stem}_{perf_str}_{final_timestamp}.py"
            success_filename_json = f"optimized_{algo_data['path'].stem}_{perf_str}_{final_timestamp}.json"
            final_py_path = success_dir / success_filename_py; mod_src = self.modify_algorithm_source_ast(source_code, class_name, current_best_params)
            if mod_src: final_py_path.write_text(mod_src, encoding='utf-8')
            final_json_path = success_dir / success_filename_json; save_data = {"params": current_best_params, "performance": current_best_perf, "score_tuple": list(current_best_score_tuple), "optimized_range": f"{start_date:%Y-%m-%d}_to_{end_date:%Y-%m-%d}"}
            final_json_path.write_text(json.dumps(save_data, indent=4), encoding='utf-8'); queue_log("BEST", f"Lưu kết quả cuối vào: {success_dir.relative_to(self.base_dir)}")
        except Exception as final_save_err: queue_log("ERROR", f"Lỗi lưu kết quả cuối: {final_save_err}")
        queue_finished(final_message, success=True)


    # run_performance_test remains the same
    def run_performance_test(self, original_source_code, class_name, params_to_test, test_start_date, test_end_date, optimize_target_dir):
        temp_algo_instance = None; temp_module_name = None; temp_filepath = None
        try:
            modified_source = self.modify_algorithm_source_ast(original_source_code, class_name, params_to_test)
            if not modified_source: raise RuntimeError("AST mod failed.")
            timestamp = int(time.time() * 10000) + random.randint(0, 9999)
            temp_filename = f"temp_{class_name}_{timestamp}.py"; temp_filepath = optimize_target_dir / temp_filename
            temp_filepath.write_text(modified_source, encoding='utf-8')
            temp_module_name = f"optimize.{optimize_target_dir.name}.{temp_filename[:-3]}"
            opt_init = self.optimize_dir / "__init__.py"; target_init = optimize_target_dir / "__init__.py"
            if not opt_init.exists(): opt_init.touch()
            if not target_init.exists(): target_init.touch()
            if temp_module_name in sys.modules: logger.warning(f"Remove existing module '{temp_module_name}'."); del sys.modules[temp_module_name]
            spec = util.spec_from_file_location(temp_module_name, temp_filepath)
            if not spec or not spec.loader: raise ImportError(f"No spec for {temp_module_name} from {temp_filepath}")
            temp_module = util.module_from_spec(spec); sys.modules[temp_module_name] = temp_module; spec.loader.exec_module(temp_module)
            temp_class = getattr(temp_module, class_name, None)
            if not temp_class or not issubclass(temp_class, BaseAlgorithm):
                fallback_class = None
                for name, obj in inspect.getmembers(temp_module):
                    if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == temp_module_name: fallback_class = obj; logger.warning(f"Class '{class_name}' not found, use '{name}'."); break
                if not fallback_class: raise TypeError(f"No valid class in {temp_module_name}.")
                temp_class = fallback_class
            temp_algo_instance = temp_class(data_results_list=copy.deepcopy(self.results_data), cache_dir=self.calculate_dir)
            perf_stats = self.calculate_performance_for_instance(temp_algo_instance, test_start_date, test_end_date)
            return perf_stats
        except Exception as e:
            log_func = self.optimizer_queue.put if self.optimizer_running else logger.error
            err_msg = f"Perf test error params {params_to_test}: {e}"
            if self.optimizer_running: log_func({"type": "log", "payload": {"level": "ERROR", "text": err_msg}})
            else: log_func(err_msg)
            logger.error(f"Perf test fail {temp_filepath}: {e}", exc_info=True); return None
        finally:
            temp_algo_instance = None
            if temp_module_name and temp_module_name in sys.modules:
                try: del sys.modules[temp_module_name]
                except Exception as del_err: logger.warning(f"Could not remove mod '{temp_module_name}': {del_err}")
            if temp_filepath and temp_filepath.exists():
                try: temp_filepath.unlink()
                except OSError as e:
                    log_func = self.optimizer_queue.put if self.optimizer_running else logger.warning
                    warn_msg = f"Could not delete temp file {temp_filepath.name}: {e}"
                    if self.optimizer_running: log_func({"type": "log", "payload": {"level": "WARNING", "text": warn_msg}})
                    else: log_func(warn_msg)

    # calculate_performance_for_instance remains the same
    def calculate_performance_for_instance(self, algo_instance, start_date, end_date):
        stats = {'total_days_tested': 0, 'hits_top_1': 0, 'hits_top_3': 0, 'hits_top_5': 0, 'hits_top_10': 0, 'errors': 0}; all_top_10_numbers = []
        if not self.results_data or not isinstance(self.results_data[0]['date'], datetime.date): return None
        results_map = {r['date']: r['result'] for r in self.results_data}; history_cache = {r['date']: self.results_data[:i] for i, r in enumerate(self.results_data)}
        current_date = start_date
        while current_date <= end_date:
            predict_date = current_date; check_date = predict_date + datetime.timedelta(days=1)
            actual_result_dict = results_map.get(check_date)
            if actual_result_dict is None: current_date += datetime.timedelta(days=1); continue
            hist_data = history_cache.get(predict_date)
            if hist_data is None: logger.warning(f"Perf Skip {predict_date:%Y-%m-%d}: No history."); current_date += datetime.timedelta(days=1); continue
            actual_numbers_set = algo_instance.extract_numbers_from_dict(actual_result_dict)
            if not actual_numbers_set: stats['errors'] += 1; current_date += datetime.timedelta(days=1); continue
            try:
                predicted_scores = algo_instance.predict(predict_date, copy.deepcopy(hist_data))
                if not isinstance(predicted_scores, dict) or not predicted_scores: stats['errors'] += 1; current_date += datetime.timedelta(days=1); continue
                sorted_preds = sorted([(int(n), s) for n, s in predicted_scores.items() if isinstance(n, str) and n.isdigit() and isinstance(s, (int, float))], key=lambda x: x[1], reverse=True)
                if not sorted_preds: stats['errors'] += 1; current_date += datetime.timedelta(days=1); continue
                pred_top_1 = {sorted_preds[0][0]}; pred_top_3 = {p[0] for p in sorted_preds[:3]}; pred_top_5 = {p[0] for p in sorted_preds[:5]}; pred_top_10 = {p[0] for p in sorted_preds[:10]}
                if pred_top_1.intersection(actual_numbers_set): stats['hits_top_1'] += 1
                if pred_top_3.intersection(actual_numbers_set): stats['hits_top_3'] += 1
                if pred_top_5.intersection(actual_numbers_set): stats['hits_top_5'] += 1
                if pred_top_10.intersection(actual_numbers_set): stats['hits_top_10'] += 1
                all_top_10_numbers.extend(list(pred_top_10)); stats['total_days_tested'] += 1
            except Exception as e: logger.error(f"Perf Error {predict_date:%Y-%m-%d}: {e}", exc_info=False); stats['errors'] += 1
            if self.optimizer_running:
                if self.optimizer_stop_event.is_set(): logger.warning("Stop in perf calc."); return None
                while self.optimizer_pause_event.is_set():
                    time.sleep(0.1);
                    if self.optimizer_stop_event.is_set(): logger.warning("Stop in pause perf calc."); return None
            current_date += datetime.timedelta(days=1)
        total_tested = stats['total_days_tested']
        if total_tested > 0:
            stats['acc_top_1_pct'] = (stats['hits_top_1'] / total_tested) * 100.0; stats['acc_top_3_pct'] = (stats['hits_top_3'] / total_tested) * 100.0
            stats['acc_top_5_pct'] = (stats['hits_top_5'] / total_tested) * 100.0; stats['acc_top_10_pct'] = (stats['hits_top_10'] / total_tested) * 100.0
            if all_top_10_numbers:
                top10_counts = Counter(all_top_10_numbers); stats['avg_top10_repetition'] = len(all_top_10_numbers) / len(top10_counts) if top10_counts else 0
                stats['max_top10_repetition_count'] = max(top10_counts.values()) if top10_counts else 0; stats['top10_repetition_details'] = dict(top10_counts.most_common(5))
            else: stats['avg_top10_repetition'] = 0.0; stats['max_top10_repetition_count'] = 0; stats['top10_repetition_details'] = {}
            return stats
        else:
            logger.warning(f"No days tested {algo_instance.__class__.__name__}."); stats['acc_top_1_pct'] = 0.0; stats['acc_top_3_pct'] = 0.0; stats['acc_top_5_pct'] = 0.0; stats['acc_top_10_pct'] = 0.0
            stats['avg_top10_repetition'] = 0.0; stats['max_top10_repetition_count'] = 0; stats['top10_repetition_details'] = {}; return stats

    # --- Utility Methods (Unchanged) ---
    def update_status(self, message):
        if hasattr(self, 'status_bar') and self.status_bar.winfo_exists():
            current = self.status_bar.cget("text")
            if message != current: self.status_bar.config(text=message); logger.info(f"Status: {message}"); self.root.update_idletasks()

    def show_calendar_dialog(self, target_var):
        if not HAS_TKCALENDAR: messagebox.showerror("Thiếu Thư Viện", "Cần 'tkcalendar'."); return
        if not self.results_data: messagebox.showwarning("Thiếu Dữ Liệu", "Chưa tải dữ liệu."); return
        win = tk.Toplevel(self.root); win.title("Chọn Ngày"); win.transient(self.root); win.grab_set(); win.geometry("300x300")
        current_val_str = target_var.get(); current_date = datetime.date.today()
        min_date = self.results_data[0]['date'] if self.results_data else datetime.date(2000, 1, 1)
        max_date = self.results_data[-1]['date'] if self.results_data else datetime.date.today()
        try:
            parsed_date = datetime.datetime.strptime(current_val_str, '%d/%m/%Y').date()
            if min_date <= parsed_date <= max_date: current_date = parsed_date
            else: current_date = max_date
        except ValueError: current_date = max_date
        cal = Calendar(win, selectmode='day', locale='vi_VN', date_pattern='dd/MM/yyyy', year=current_date.year, month=current_date.month, day=current_date.day, mindate=min_date, maxdate=max_date)
        cal.pack(pady=10, fill="both", expand=True)
        def _select_date(): target_var.set(cal.get_date()); win.destroy()
        ttk.Button(win, text="Chọn", command=_select_date, style="Accent.TButton").pack(pady=5)
        win.wait_window()

    def _clear_cache_directory(self):
        logger.info(f"Clearing cache: {self.calculate_dir}"); cleared = 0; errors = 0
        try:
            if self.calculate_dir.exists():
                for item in self.calculate_dir.iterdir():
                    try:
                        if item.is_file(): item.unlink(); cleared += 1
                        elif item.is_dir(): shutil.rmtree(item); cleared += 1
                    except Exception as item_err: logger.error(f"Failed remove cache '{item.name}': {item_err}"); errors += 1
                logger.info(f"Cache clear done. Removed {cleared}, errors {errors}.")
            else: logger.debug("Cache dir not found.")
        except Exception as e: logger.error(f"Cache clear error: {e}", exc_info=True)

    def _load_optimization_log(self):
        if not self.selected_algorithm_for_optimize: return
        if self.selected_algorithm_for_optimize not in self.loaded_algorithms:
             logger.error(f"Log load fail: Unloaded algo: {self.selected_algorithm_for_optimize}")
             try:
                 if hasattr(self, 'opt_log_text') and self.opt_log_text.winfo_exists():
                     self.opt_log_text.config(state=tk.NORMAL); self.opt_log_text.delete(1.0, tk.END)
                     self.opt_log_text.insert(tk.END, "Lỗi: Thuật toán không được tải.\n", "ERROR"); self.opt_log_text.config(state=tk.DISABLED)
             except tk.TclError: pass
             return
        algo_data = self.loaded_algorithms[self.selected_algorithm_for_optimize]
        target_dir = self.optimize_dir / algo_data['path'].stem
        log_path = target_dir / "optimization.log"; self.current_optimization_log_path = log_path
        if not hasattr(self, 'opt_log_text') or not self.opt_log_text.winfo_exists(): logger.warning("Log widget not available."); return
        try:
            self.opt_log_text.config(state=tk.NORMAL); self.opt_log_text.delete(1.0, tk.END)
            if log_path.exists():
                try:
                    log_content = log_path.read_text(encoding='utf-8'); lines = log_content.splitlines()
                    for line in lines:
                        tag = "INFO" # Default
                        # --- FIX: Corrected if/elif structure ---
                        if len(line) > 27 and line[26] == ' ':
                            level_match = line[27:].split(']', 1)[0].strip('[ ')
                            if level_match in self.opt_log_text.tag_names():
                                tag = level_match
                            elif level_match == "CRITICAL":
                                tag = "ERROR"
                        # Fallback check if format is different (use proper elif)
                        elif "[ERROR]" in line or "[CRITICAL]" in line:
                            tag = "ERROR"
                        elif "[WARNING]" in line:
                            tag = "WARNING"
                        elif "[BEST]" in line:
                            tag = "BEST"
                        elif "[DEBUG]" in line:
                            tag = "DEBUG"
                        elif "[PROGRESS]" in line:
                            tag = "PROGRESS"
                        elif "[CUSTOM_STEP]" in line:
                            tag = "CUSTOM_STEP"
                        # --- End Fix ---

                        self.opt_log_text.insert(tk.END, line + "\n", tag)
                    self.opt_log_text.see(tk.END); logger.info(f"Loaded log: {log_path.name}")
                except Exception as e:
                    logger.error(f"Failed read log {log_path.name}: {e}")
                    self.opt_log_text.insert(tk.END, f"Lỗi đọc file log:\n{e}\n", "ERROR")
            else:
                logger.info(f"Log not found: {log_path}")
                self.opt_log_text.insert(tk.END, "Chưa có nhật ký.\n", "INFO")
        except tk.TclError as e: logger.error(f"TclError on log widget: {e}")
        finally:
             if hasattr(self, 'opt_log_text') and self.opt_log_text.winfo_exists():
                  try: self.opt_log_text.config(state=tk.DISABLED)
                  except tk.TclError: pass

    def open_optimize_folder(self):
        target_dir = None
        if self.selected_algorithm_for_optimize and self.selected_algorithm_for_optimize in self.loaded_algorithms:
            algo_data = self.loaded_algorithms[self.selected_algorithm_for_optimize]; target_dir = self.optimize_dir / algo_data['path'].stem
        else: target_dir = self.optimize_dir
        if not target_dir: messagebox.showerror("Lỗi", "Không xác định được thư mục."); return
        try: target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e: messagebox.showerror("Lỗi", f"Không thể tạo thư mục:\n{target_dir}\nLỗi: {e}"); logger.error(f"Failed create dir {target_dir}: {e}"); return
        try:
            logger.info(f"Opening folder: {target_dir}")
            if sys.platform == "win32": os.startfile(target_dir)
            elif sys.platform == "darwin": subprocess.Popen(["open", str(target_dir)])
            else: subprocess.Popen(["xdg-open", str(target_dir)])
        except FileNotFoundError: messagebox.showerror("Lỗi", f"Lệnh mở thư mục lỗi/không có:\n{target_dir}"); logger.error(f"Cmd/Dir missing: {target_dir}")
        except Exception as e: logger.error(f"Failed open dir {target_dir}: {e}", exc_info=True); messagebox.showerror("Lỗi", f"Không thể mở thư mục:\n{e}")

# --- Main Execution (remains the same) ---
def main():
    root = None
    try:
        logger.info("--- Starting Algorithm Optimizer Application ---")
        root = tk.Tk()
        try:
            if sys.platform == "win32":
                from ctypes import windll
                try: windll.shcore.SetProcessDpiAwareness(2); logger.info("Set Per Monitor v2 DPI Awareness.")
                except (AttributeError, OSError):
                    try: windll.user32.SetProcessDPIAware(); logger.info("Set System DPI Awareness.")
                    except (AttributeError, OSError): logger.warning("Could not set DPI awareness.")
        except ImportError: logger.warning("ctypes import failed (DPI awareness setting skipped).")
        except Exception as dpi_e: logger.warning(f"Error setting DPI awareness: {dpi_e}")
        app = AlgorithmOptimizerApp(root); root.mainloop()
        logger.info("--- Algorithm Optimizer Application Closed ---")
    except Exception as e:
        logger.critical(f"Unhandled main exception: {e}", exc_info=True); traceback.print_exc()
        try:
            err_root = None
            if root is None or not root.winfo_exists(): err_root = tk.Tk(); err_root.withdraw()
            messagebox.showerror("Lỗi Nghiêm Trọng", f"Lỗi không mong muốn:\n{e}\n\nKiểm tra 'lottery_app.log'.")
            if err_root: err_root.destroy()
            if root and root.winfo_exists(): root.destroy()
        except Exception as final_err: print(f"Error showing final error: {final_err}", file=sys.stderr); print(f"\nCRITICAL ERROR:\n{e}\nCheck 'lottery_app.log'.", file=sys.stderr)
        sys.exit(1)
    finally: logging.shutdown()

if __name__ == "__main__":
    script_dir_main = Path(__file__).parent.resolve()
    if str(script_dir_main) not in sys.path: sys.path.insert(0, str(script_dir_main)); print(f"Info: Added script dir to path: {script_dir_main}")
    missing_libs = []
    if sys.version_info < (3, 9):
        try: import astor
        except ImportError: missing_libs.append("astor (pip install astor)")
    try: from tkcalendar import Calendar
    except ImportError: missing_libs.append("tkcalendar (pip install tkcalendar)")
    if missing_libs:
        error_message = "LỖI: Thiếu thư viện:\n\n" + "\n".join(missing_libs) + "\n\nVui lòng cài đặt và chạy lại."
        print(error_message, file=sys.stderr)
        try: root_err = tk.Tk(); root_err.withdraw(); messagebox.showerror("Thiếu Thư Viện", error_message); root_err.destroy()
        except Exception: pass
        sys.exit(1)
    print(f"Info: Log file: {log_file_path}")
    main()
