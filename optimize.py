# -*- coding: utf-8 -*-
# File: optimize_qt.py
# Role: GUI Application for Analyzing and Optimizing Lottery Prediction Algorithms (v1.3.3 PyQt5 - Always show advanced opt)

import os
import sys
import logging
import json
import traceback
import datetime
import shutil
import calendar # Keep for potential date logic if needed, but not UI
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
    log_file_path = base_dir_for_log / "lottery_app_qt.log" # Different log file
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
    # Prevent duplicate handlers if script is re-run in same console
    if not any(isinstance(h, logging.StreamHandler) and h.stream == sys.stdout for h in root_logger.handlers):
        root_logger.addHandler(console_handler)
    logger = logging.getLogger("AlgorithmOptimizerAppQt")
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
        # Cannot use tkinter messagebox here as we are moving to PyQt
        sys.exit(1)
    else:
        HAS_ASTOR = False

# --- PyQt5 Imports ---
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFormLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QMessageBox,
        QFileDialog, QTreeWidget, QTreeWidgetItem, QTextEdit, QProgressBar,
        QGroupBox, QSplitter, QScrollArea, QComboBox, QDialog, QCalendarWidget,
        QStatusBar, QHeaderView
    )
    from PyQt5.QtCore import (
        Qt, QThread, pyqtSignal, QObject, QTimer, QSize, QUrl, QDate, QLocale,
        QRegularExpression
    )
    from PyQt5.QtGui import (
        QIntValidator, QDoubleValidator, QTextCursor, QTextCharFormat, QColor,
        QFont, QDesktopServices, QRegularExpressionValidator
    )
    HAS_PYQT5 = True
    logger.info("PyQt5 library found.")
except ImportError as e:
    print(f"LỖI NGHIÊM TRỌNG: Cần thư viện 'PyQt5'. Cài đặt: pip install PyQt5", file=sys.stderr)
    logger.critical(f"PyQt5 not found: {e}")
    sys.exit(1)
# --- End PyQt5 Imports ---


import subprocess # Keep for Linux/Mac open folder fallback if needed
from collections import Counter
from importlib import reload, util

# --- Import BaseAlgorithm (Keep as is) ---
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

# --- QCalendarDialog ---
class QCalendarDialog(QDialog):
    """A simple dialog to select a date using QCalendarWidget."""
    # Signal emitting the selected QDate
    dateSelected = pyqtSignal(QDate)

    def __init__(self, parent=None, current_date=None, min_date=None, max_date=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn Ngày")
        self.setModal(True)
        self.locale = QLocale(QLocale.Vietnamese, QLocale.Vietnam) # For Vietnamese day/month names

        layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget(self)
        self.calendar.setLocale(self.locale)
        self.calendar.setGridVisible(True)
        # self.calendar.setFirstDayOfWeek(Qt.Monday) # Uncomment if needed

        if min_date:
            self.calendar.setMinimumDate(QDate(min_date.year, min_date.month, min_date.day))
        if max_date:
            self.calendar.setMaximumDate(QDate(max_date.year, max_date.month, max_date.day))
        if current_date:
            q_current = QDate(current_date.year, current_date.month, current_date.day)
            # Clamp current date within min/max if provided
            if min_date and q_current < self.calendar.minimumDate():
                q_current = self.calendar.minimumDate()
            if max_date and q_current > self.calendar.maximumDate():
                q_current = self.calendar.maximumDate()
            self.calendar.setSelectedDate(q_current)
        else:
             self.calendar.setSelectedDate(QDate.currentDate())

        layout.addWidget(self.calendar)

        # Ok and Cancel buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("Chọn", self)
        ok_button.clicked.connect(self.accept_selection)
        cancel_button = QPushButton("Hủy", self)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.calendar.activated.connect(self.accept_selection) # Double-click selects

    def accept_selection(self):
        self.dateSelected.emit(self.calendar.selectedDate())
        self.accept()

    def selected_date(self):
        return self.calendar.selectedDate()

# --- Optimizer Worker Communication (QObject for signals) ---
class OptimizerSignals(QObject):
    log = pyqtSignal(str, str, str) # level, text, tag
    status = pyqtSignal(str)
    progress = pyqtSignal(float)
    best_update = pyqtSignal(dict, float) # params_dict, score_float (using primary score for simplicity here)
    finished = pyqtSignal(str, bool) # message, success
    error = pyqtSignal(str)

# --- Main Application Class ---
class AlgorithmOptimizerApp(QMainWindow):
    # __init__
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trình Phân Tích & Tối Ưu Thuật Toán Xổ Số (v1.3.3 - PyQt5)") # Version bump
        self.setGeometry(100, 100, 1300, 900) # x, y, width, height
        self.setMinimumSize(1000, 700)
        logger.info("Initializing AlgorithmOptimizerAppQt...")

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
        self.config_parser = configparser.ConfigParser(interpolation=None) # Renamed from self.config
        self.results_data = []
        self.loaded_algorithms = {}
        self.selected_algorithm_for_edit = None
        self.selected_algorithm_for_optimize = None
        self.editor_param_widgets = {} # Store QLineEdit/QLabel widgets
        self.editor_original_params = {}

        # --- Optimization State ---
        self.optimizer_thread_obj = None # Store the QThread object
        self.optimizer_worker = None # Store the worker QObject
        self.optimizer_signals = OptimizerSignals() # Signals object
        self.optimizer_queue = queue.Queue() # Still using queue for worker -> signal bridge
        self.optimizer_stop_event = threading.Event()
        self.optimizer_pause_event = threading.Event()
        self.optimizer_running = False
        self.optimizer_paused = False
        self.current_best_params = None
        self.current_best_score_tuple = (-1.0, -1.0, -1.0, -100.0) # Store the tuple score
        self.current_optimization_log_path = None
        self.current_optimize_target_dir = None
        self.optimizer_custom_steps = {}
        self.advanced_opt_widgets = {} # Store widgets like {'param_name': {'mode_combo': QComboBox, 'steps_entry': QLineEdit}}

        # --- UI Variables (Direct widget access replaces these) ---
        # self.data_file_path_var = tk.StringVar() -> Use self.data_file_path_entry.text() / setText()
        # self.data_range_var = tk.StringVar() -> Use self.data_range_label.text() / setText()
        # self.window_width_var = tk.StringVar() -> Use self.width_entry.text() / setText()
        # ... and so on for opt_start_date, opt_end_date, opt_time_limit, opt_status, opt_progress_pct

        # --- Validators ---
        self.int_validator = QIntValidator()
        self.double_validator = QDoubleValidator()
        self.dimension_validator = QIntValidator(100, 10000) # Min/Max dimensions
        self.time_limit_validator = QIntValidator(1, 9999) # Min/Max time limit
        # Custom steps validation needs a custom approach or regex
        # Regex for comma-separated numbers (ints/floats, optional signs)
        custom_steps_regex = QRegularExpression(r"^\s*(-?\d+(\.\d+)?\s*(,\s*-?\d+(\.\d+)?\s*)*)?$")
        self.custom_steps_validator = QRegularExpressionValidator(custom_steps_regex)


        # --- Setup ---
        self.create_directories()
        # self.setup_styles() # Styles are handled by QSS now
        self.setup_ui()
        self.setup_signals() # Connect signals after UI is built
        self.load_app_config()
        self.apply_window_size() # Apply loaded size
        self.load_data()
        self.load_algorithms()
        self.update_status("Ứng dụng sẵn sàng.")
        logger.info("AlgorithmOptimizerAppQt initialized successfully.")


    # create_directories remains the same (backend logic)
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
        except Exception as e:
            logger.error(f"Lỗi tạo thư mục/dữ liệu mẫu: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi", f"Lỗi tạo thư mục/file mẫu:\n{e}")

    # setup_styles is replaced by QSS setup in main()

    def setup_ui(self):
        """Xây dựng cấu trúc giao diện chính."""
        logger.debug("Đang thiết lập UI chính...")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        # --- Top Frame: Data Info ---
        top_groupbox = QGroupBox("Thông Tin Dữ Liệu")
        top_layout = QGridLayout(top_groupbox)
        top_layout.addWidget(QLabel("File dữ liệu:"), 0, 0)
        self.data_file_path_entry = QLineEdit()
        self.data_file_path_entry.setReadOnly(True) # Read-only, set via browse
        top_layout.addWidget(self.data_file_path_entry, 0, 1)
        self.browse_data_button = QPushButton("Duyệt...")
        top_layout.addWidget(self.browse_data_button, 0, 2)
        self.reload_data_button = QPushButton("Tải lại Dữ liệu")
        top_layout.addWidget(self.reload_data_button, 0, 3)
        top_layout.addWidget(QLabel("Phạm vi:"), 1, 0)
        self.data_range_label = QLabel("...")
        top_layout.addWidget(self.data_range_label, 1, 1, 1, 3) # Span 3 columns
        top_layout.setColumnStretch(1, 1) # Make entry expand
        main_layout.addWidget(top_groupbox)

        # --- Notebook for Tabs ---
        self.notebook = QTabWidget()
        main_layout.addWidget(self.notebook)

        # Create tab widgets (these will be populated by setup_*_tab methods)
        self.tab_select = QWidget()
        self.tab_edit = QWidget()
        self.tab_optimize = QWidget()
        self.tab_config = QWidget()
        self.tab_about = QWidget()

        self.notebook.addTab(self.tab_select, " Chọn Thuật Toán ")
        self.notebook.addTab(self.tab_edit, " Chỉnh Sửa ")
        self.notebook.addTab(self.tab_optimize, " Tối Ưu Hóa ")
        self.notebook.addTab(self.tab_config, " Cấu Hình App ")
        self.notebook.addTab(self.tab_about, " Thông Tin ")

        self.notebook.setTabEnabled(1, False) # Edit
        self.notebook.setTabEnabled(2, False) # Optimize

        # Populate tabs
        self.setup_select_tab()
        self.setup_edit_tab()
        self.setup_optimize_tab()
        self.setup_config_tab()
        self.setup_about_tab()

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Khởi tạo...")

    def setup_select_tab(self):
        """Thiết lập UI cho tab Chọn Thuật Toán."""
        logger.debug("Đang thiết lập tab Chọn Thuật Toán.")
        layout = QVBoxLayout(self.tab_select)

        control_layout = QHBoxLayout()
        self.reload_algo_button = QPushButton("Tải lại Danh sách Thuật toán")
        self.select_edit_button = QPushButton("Chọn để Chỉnh sửa")
        self.select_optimize_button = QPushButton("Chọn để Tối ưu hóa")
        self.select_edit_button.setObjectName("AccentButton") # For QSS styling
        self.select_optimize_button.setObjectName("AccentButton")
        control_layout.addWidget(self.reload_algo_button)
        control_layout.addWidget(self.select_edit_button)
        control_layout.addWidget(self.select_optimize_button)
        control_layout.addStretch(1)
        layout.addLayout(control_layout)

        self.algo_tree = QTreeWidget()
        self.algo_tree.setColumnCount(3)
        self.algo_tree.setHeaderLabels(["Tên Thuật Toán", "Tên File", "Mô Tả"])
        self.algo_tree.setColumnWidth(0, 250)
        self.algo_tree.setColumnWidth(1, 150)
        # Let last column stretch
        self.algo_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.algo_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.algo_tree.setAlternatingRowColors(True) # Nice visual touch

        layout.addWidget(self.algo_tree)

    def setup_edit_tab(self):
        """Thiết lập UI cho tab Chỉnh Sửa."""
        logger.debug("Đang thiết lập tab Chỉnh Sửa.")
        main_layout = QVBoxLayout(self.tab_edit)

        # Info Section
        info_layout = QFormLayout()
        self.edit_algo_name_label = QLabel("...")
        self.edit_algo_name_label.setStyleSheet("font-weight: bold; color: navy;")
        self.edit_algo_desc_label = QLabel("...")
        self.edit_algo_desc_label.setWordWrap(True)
        info_layout.addRow(QLabel("<b>Thuật toán đang sửa:</b>"), self.edit_algo_name_label)
        info_layout.addRow(QLabel("<b>Mô tả:</b>"), self.edit_algo_desc_label)
        main_layout.addLayout(info_layout)

        # Paned Window -> QSplitter
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1) # Give splitter stretch factor

        # Parameters Frame (Left side of splitter)
        param_groupbox = QGroupBox("Tham Số Có Thể Chỉnh Sửa")
        param_scroll_area = QScrollArea()
        param_scroll_area.setWidgetResizable(True) # Important!
        param_scroll_content = QWidget() # Widget to hold the actual layout
        self.edit_param_layout = QGridLayout(param_scroll_content) # Layout inside scroll content
        self.edit_param_layout.setAlignment(Qt.AlignTop) # Align items to top
        param_scroll_area.setWidget(param_scroll_content)
        param_groupbox_layout = QVBoxLayout(param_groupbox)
        param_groupbox_layout.addWidget(param_scroll_area)
        splitter.addWidget(param_groupbox)

        # Explanation Frame (Right side of splitter)
        explain_groupbox = QGroupBox("Giải Thích Thuật Toán (Docstring)")
        explain_layout = QVBoxLayout(explain_groupbox)
        self.edit_explain_text = QTextEdit()
        self.edit_explain_text.setReadOnly(True)
        explain_layout.addWidget(self.edit_explain_text)
        splitter.addWidget(explain_groupbox)

        # Set initial splitter sizes (optional)
        splitter.setSizes([self.width() // 3, self.width() * 2 // 3])

        # Button Frame
        button_layout = QHBoxLayout()
        self.save_copy_button = QPushButton("Lưu Bản Sao...")
        self.save_copy_button.setObjectName("AccentButton")
        self.cancel_edit_button = QPushButton("Hủy Bỏ")
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_edit_button)
        button_layout.addWidget(self.save_copy_button)
        main_layout.addLayout(button_layout)

    def setup_optimize_tab(self):
        """Thiết lập UI cho tab Tối Ưu Hóa (layout 2 cột, luôn hiện cài đặt)."""
        logger.debug("Đang thiết lập tab Tối Ưu Hóa (luôn hiện 2 cột - PyQt).")
        main_layout = QVBoxLayout(self.tab_optimize)

        # --- Top section ---
        top_section_widget = QWidget()
        top_section_layout = QVBoxLayout(top_section_widget)
        top_section_layout.setContentsMargins(0,0,0,0) # Remove margins if needed

        # --- Algorithm Info ---
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("<b>Thuật toán tối ưu:</b>"))
        self.opt_algo_name_label = QLabel("...")
        self.opt_algo_name_label.setStyleSheet("font-weight: bold; color: darkgreen;")
        info_layout.addWidget(self.opt_algo_name_label)
        info_layout.addStretch(1)
        top_section_layout.addLayout(info_layout)

        # --- Grid Container for Settings ---
        settings_grid_widget = QWidget()
        settings_grid_layout = QGridLayout(settings_grid_widget)
        settings_grid_layout.setColumnStretch(0, 1)
        settings_grid_layout.setColumnStretch(1, 1)

        # --- Basic Settings Frame (Column 0) ---
        basic_settings_groupbox = QGroupBox("Cài Đặt Cơ Bản")
        basic_settings_layout = QGridLayout(basic_settings_groupbox)

        basic_settings_layout.addWidget(QLabel("<b>Khoảng thời gian dữ liệu kiểm tra:</b>"), 0, 0, 1, 4)
        basic_settings_layout.addWidget(QLabel("Từ ngày:"), 1, 0)
        self.opt_start_date_entry = QLineEdit()
        self.opt_start_date_entry.setPlaceholderText("dd/MM/yyyy")
        self.opt_start_date_entry.setReadOnly(True) # Read-only, set via calendar
        self.opt_start_date_button = QPushButton("📅")
        self.opt_start_date_button.setFixedWidth(35)
        basic_settings_layout.addWidget(self.opt_start_date_entry, 1, 1)
        basic_settings_layout.addWidget(self.opt_start_date_button, 1, 2)

        basic_settings_layout.addWidget(QLabel("Đến ngày:"), 2, 0)
        self.opt_end_date_entry = QLineEdit()
        self.opt_end_date_entry.setPlaceholderText("dd/MM/yyyy")
        self.opt_end_date_entry.setReadOnly(True)
        self.opt_end_date_button = QPushButton("📅")
        self.opt_end_date_button.setFixedWidth(35)
        basic_settings_layout.addWidget(self.opt_end_date_entry, 2, 1)
        basic_settings_layout.addWidget(self.opt_end_date_button, 2, 2)

        basic_settings_layout.addWidget(QLabel("(Ngày cuối < ngày cuối data 1 ngày)"), 3, 0, 1, 3) # Span 3

        basic_settings_layout.addWidget(QLabel("Thời gian tối ưu tối đa (phút):"), 4, 0)
        self.opt_time_limit_entry = QLineEdit("60")
        self.opt_time_limit_entry.setValidator(self.time_limit_validator)
        self.opt_time_limit_entry.setMaxLength(4)
        self.opt_time_limit_entry.setFixedWidth(60)
        basic_settings_layout.addWidget(self.opt_time_limit_entry, 4, 1, Qt.AlignLeft) # Align left
        basic_settings_layout.rowStretch(5) # Push content up

        settings_grid_layout.addWidget(basic_settings_groupbox, 0, 0)

        # --- Advanced Optimization Settings Frame (Column 1 - ALWAYS VISIBLE) ---
        self.advanced_opt_groupbox = QGroupBox("Cài Đặt Tối Ưu Nâng Cao")
        adv_opt_layout = QVBoxLayout(self.advanced_opt_groupbox)
        self.advanced_opt_scroll_area = QScrollArea()
        self.advanced_opt_scroll_area.setWidgetResizable(True)
        self.advanced_opt_params_widget = QWidget() # Content widget for scroll area
        self.advanced_opt_params_layout = QVBoxLayout(self.advanced_opt_params_widget) # Layout for content
        self.advanced_opt_params_layout.setAlignment(Qt.AlignTop)
        self.advanced_opt_scroll_area.setWidget(self.advanced_opt_params_widget)
        adv_opt_layout.addWidget(self.advanced_opt_scroll_area)
        # Initial placeholder
        self.advanced_opt_params_layout.addWidget(QLabel("Chọn thuật toán để xem tham số."))
        settings_grid_layout.addWidget(self.advanced_opt_groupbox, 0, 1)

        top_section_layout.addWidget(settings_grid_widget)

        # --- Control Frame ---
        control_layout = QHBoxLayout()
        self.opt_start_button = QPushButton("Bắt đầu Tối ưu")
        self.opt_pause_button = QPushButton("Tạm dừng")
        self.opt_stop_button = QPushButton("Dừng Hẳn")
        self.opt_start_button.setObjectName("AccentButton")
        self.opt_pause_button.setObjectName("WarningButton")
        self.opt_stop_button.setObjectName("DangerButton")
        self.opt_start_button.setFixedWidth(120)
        self.opt_pause_button.setFixedWidth(100)
        self.opt_stop_button.setFixedWidth(100)
        self.opt_pause_button.setEnabled(False)
        self.opt_stop_button.setEnabled(False)
        control_layout.addWidget(self.opt_start_button)
        control_layout.addWidget(self.opt_pause_button)
        control_layout.addWidget(self.opt_stop_button)
        control_layout.addStretch(1)
        top_section_layout.addLayout(control_layout)

        # --- Progress Bar and Status ---
        progress_layout = QHBoxLayout()
        self.opt_progressbar = QProgressBar()
        self.opt_progressbar.setRange(0, 100)
        self.opt_progressbar.setValue(0)
        self.opt_progressbar.setTextVisible(False) # Percentage label is separate
        self.opt_progress_label = QLabel("0%")
        self.opt_progress_label.setFixedWidth(40)
        self.opt_status_label = QLabel("Trạng thái: Chờ")
        progress_layout.addWidget(self.opt_progressbar, 1) # Stretch factor
        progress_layout.addWidget(self.opt_progress_label)
        progress_layout.addWidget(self.opt_status_label)
        progress_layout.addStretch(1) # Add stretch after status label too
        top_section_layout.addLayout(progress_layout)

        main_layout.addWidget(top_section_widget) # Add top section to main layout

        # --- Log Area ---
        log_groupbox = QGroupBox("Nhật Ký Tối Ưu Hóa")
        log_layout = QVBoxLayout(log_groupbox)
        self.opt_log_text = QTextEdit()
        self.opt_log_text.setReadOnly(True)
        self.opt_log_text.setFontFamily("Courier New")
        self.opt_log_text.setFontPointSize(9)
        log_layout.addWidget(self.opt_log_text, 1) # Stretch factor

        open_folder_layout = QHBoxLayout()
        self.open_opt_folder_button = QPushButton("Mở Thư Mục Tối Ưu")
        open_folder_layout.addStretch(1)
        open_folder_layout.addWidget(self.open_opt_folder_button)
        log_layout.addLayout(open_folder_layout)

        main_layout.addWidget(log_groupbox, 1) # Add log area, make it stretch vertically

    def setup_config_tab(self):
        """Thiết lập UI cho tab Cấu Hình App."""
        logger.debug("Đang thiết lập tab Cấu Hình.")
        layout = QVBoxLayout(self.tab_config)
        layout.setAlignment(Qt.AlignTop) # Align content to the top

        size_groupbox = QGroupBox("Kích Thước Cửa Sổ")
        size_layout = QFormLayout(size_groupbox) # Use QFormLayout for label-entry pairs

        self.width_entry = QLineEdit()
        self.width_entry.setValidator(self.dimension_validator)
        self.width_entry.setMaxLength(4)
        self.width_entry.setFixedWidth(80)

        self.height_entry = QLineEdit()
        self.height_entry.setValidator(self.dimension_validator)
        self.height_entry.setMaxLength(4)
        self.height_entry.setFixedWidth(80)

        size_layout.addRow("Rộng (Width):", self.width_entry)
        size_layout.addRow("Cao (Height):", self.height_entry)

        layout.addWidget(size_groupbox)

        button_layout = QHBoxLayout()
        self.save_config_button = QPushButton("Lưu Cấu Hình App")
        self.save_config_button.setObjectName("AccentButton")
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_config_button)

        layout.addStretch(1) # Push button to bottom
        layout.addLayout(button_layout)


    def setup_about_tab(self):
        """Thiết lập UI cho tab Thông Tin."""
        logger.debug("Đang thiết lập tab Thông Tin.")
        layout = QVBoxLayout(self.tab_about)
        layout.setContentsMargins(20, 20, 20, 20) # Padding
        layout.setAlignment(Qt.AlignTop)

        title_label = QLabel("Trình Phân Tích & Tối Ưu Thuật Toán Xổ Số v1.3.3")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        layout.addSpacing(20)

        layout.addWidget(QLabel("<b>Phiên bản:</b> 1.3.3")) # Use bold tag
        layout.addWidget(QLabel(f"<b>Ngày cập nhật:</b> {datetime.date.today().strftime('%d/%m/%Y')}"))

        layout.addSpacing(20)
        layout.addWidget(QLabel("<b>Mô tả:</b>"))
        description = ("Ứng dụng này cho phép:\n"
                       "- Xem và chỉnh sửa các tham số số học trong file thuật toán.\n"
                       "- Lưu bản sao của thuật toán với tham số đã sửa.\n"
                       "- Tự động tối ưu hóa tham số của thuật toán đã chọn bằng cách thử nghiệm nhiều giá trị và đánh giá hiệu suất trên dữ liệu lịch sử.\n"
                       "- **Mới:** Tùy chỉnh bước nhảy (step) cho từng tham số khi tối ưu hóa.\n"
                       "- Tìm bộ tham số cho hiệu suất tốt nhất (ưu tiên tỷ lệ trúng Top 3) và lưu lại thuật toán tối ưu.\n\n"
                       "Lưu ý: Quá trình tối ưu có thể tốn nhiều thời gian và tài nguyên máy tính.")
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addSpacing(20)
        layout.addWidget(QLabel("<b>Thư viện:</b>"))
        libs = f"Python {sys.version.split()[0]}, PyQt5"
        libs += ", astor" if HAS_ASTOR else ""
        # No tkcalendar equivalent needed here, it's internal now
        libs_label = QLabel(libs)
        layout.addWidget(libs_label)

        layout.addStretch(1) # Push content up

    def setup_signals(self):
        """Connect signals to slots."""
        # Top buttons
        self.browse_data_button.clicked.connect(self.browse_data_file)
        self.reload_data_button.clicked.connect(self.load_data)

        # Select Tab
        self.reload_algo_button.clicked.connect(self.reload_algorithms)
        self.select_edit_button.clicked.connect(self.select_algo_for_edit)
        self.select_optimize_button.clicked.connect(self.select_algo_for_optimize)
        self.algo_tree.itemDoubleClicked.connect(self.select_algo_for_edit) # Double click = edit

        # Edit Tab
        self.save_copy_button.clicked.connect(self.save_edited_copy)
        self.cancel_edit_button.clicked.connect(self.cancel_edit)

        # Optimize Tab
        self.opt_start_date_button.clicked.connect(lambda: self.show_calendar_dialog(self.opt_start_date_entry))
        self.opt_end_date_button.clicked.connect(lambda: self.show_calendar_dialog(self.opt_end_date_entry))
        self.opt_start_button.clicked.connect(self.start_optimization)
        self.opt_pause_button.clicked.connect(self.pause_or_resume_optimization) # One button toggles
        self.opt_stop_button.clicked.connect(self.stop_optimization)
        self.open_opt_folder_button.clicked.connect(self.open_optimize_folder)

        # Config Tab
        self.save_config_button.clicked.connect(self.save_app_config)

        # Optimizer Signals (from worker thread)
        self.optimizer_signals.log.connect(self._log_to_optimizer_display)
        self.optimizer_signals.status.connect(lambda s: self.opt_status_label.setText(f"Trạng thái: {s}"))
        self.optimizer_signals.progress.connect(self.update_optimizer_progress)
        self.optimizer_signals.best_update.connect(self.handle_best_update)
        self.optimizer_signals.finished.connect(self.handle_optimization_finished)
        self.optimizer_signals.error.connect(lambda e: self._log_to_optimizer_display("ERROR", f"[LỖI LUỒNG] {e}"))

        # Queue Check Timer
        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self._check_optimizer_queue)
        # Timer starts when optimization begins, interval set there.

    # --- Validation Methods ---
    # Using QValidators, these Tkinter methods are no longer directly needed
    # def _validate_dimension_input(self, P): ...
    # def _validate_numeric_input(self, P): ...
    # def _validate_int_input(self, P): ...

    def _validate_custom_steps_qt(self, text):
        """Validates custom steps input in a QLineEdit."""
        if not text: # Allow empty
             return True
        state, _ = self.custom_steps_validator.validate(text, 0)
        return state == QValidator.Acceptable

    def _apply_entry_validation_style(self, entry_widget, is_valid):
        """Applies visual style to an entry based on validity."""
        if is_valid:
            entry_widget.setStyleSheet("") # Reset to default/QSS
        else:
            entry_widget.setStyleSheet("color: red;")

    # --- Config Handling ---
    def load_app_config(self):
        logger.info("Đang tải cấu hình ứng dụng...")
        config_path = self.config_dir / "settings_optimizer_qt.ini" # Different config file
        default_width, default_height = 1300, 900
        try:
            self.config_parser = configparser.ConfigParser(interpolation=None)
            if config_path.exists():
                self.config_parser.read(config_path, encoding='utf-8')
                logger.info(f"Đã tải cấu hình từ: {config_path}")
            else:
                logger.warning(f"Không tìm thấy file cấu hình: {config_path}. Dùng mặc định.")
            w = self.config_parser.getint('UI', 'width', fallback=default_width)
            h = self.config_parser.getint('UI', 'height', fallback=default_height)
            # Use minimum size from QMainWindow
            min_w, min_h = self.minimumSize().width(), self.minimumSize().height()
            self.width_entry.setText(str(max(min_w, w)))
            self.height_entry.setText(str(max(min_h, h)))
        except Exception as e:
            logger.error(f"Lỗi tải cấu hình: {e}", exc_info=True)
            self.width_entry.setText(str(default_width))
            self.height_entry.setText(str(default_height))
            if not self.config_parser.has_section('UI'):
                self.config_parser.add_section('UI')
            self.config_parser['UI'] = {'width': str(default_width), 'height': str(default_height)}

    def save_app_config(self):
        logger.info("Đang lưu cấu hình ứng dụng...")
        config_path = self.config_dir / "settings_optimizer_qt.ini"
        try:
            if not self.config_parser.has_section('UI'):
                self.config_parser.add_section('UI')
            w_str = self.width_entry.text().strip()
            h_str = self.height_entry.text().strip()
            try:
                 w = int(w_str) if w_str else 1300
                 h = int(h_str) if h_str else 900
                 min_w, min_h = self.minimumSize().width(), self.minimumSize().height()
                 w = max(min_w, w)
                 h = max(min_h, h)
                 self.config_parser.set('UI', 'width', str(w))
                 self.config_parser.set('UI', 'height', str(h))
                 # Update line edits in case clamping changed values
                 self.width_entry.setText(str(w))
                 self.height_entry.setText(str(h))
            except ValueError:
                 logger.error(f"Kích thước cửa sổ không hợp lệ '{w_str}'x'{h_str}'.")
                 QMessageBox.critical(self, "Lỗi Lưu", "Kích thước cửa sổ không hợp lệ.")
                 return

            with open(config_path, 'w', encoding='utf-8') as f:
                self.config_parser.write(f)
            self.update_status("Đã lưu cấu hình ứng dụng.")
            logger.info(f"Đã lưu cấu hình vào: {config_path}")
            self.apply_window_size() # Apply immediately
            QMessageBox.information(self, "Lưu Thành Công", "Đã lưu cấu hình kích thước cửa sổ.")
        except Exception as e:
            logger.error(f"Lỗi lưu cấu hình: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Lưu", f"Không thể lưu cấu hình:\n{e}")

    def apply_window_size(self):
        try:
            w = int(self.width_entry.text())
            h = int(self.height_entry.text())
            min_w, min_h = self.minimumSize().width(), self.minimumSize().height()
            w = max(min_w, w)
            h = max(min_h, h)
            self.resize(w, h) # Use resize for QMainWindow
            logger.info(f"Đã áp dụng kích thước cửa sổ: {w}x{h}")
        except ValueError:
            logger.warning("Giá trị kích thước không hợp lệ, không thể áp dụng.")
        except Exception as e:
            logger.error(f"Lỗi áp dụng kích thước cửa sổ: {e}", exc_info=True)

    # --- Data Handling ---
    def browse_data_file(self):
        logger.debug("Đang duyệt file dữ liệu...")
        initial_dir = str(self.data_dir)
        current_path_str = self.data_file_path_entry.text()
        if current_path_str and Path(current_path_str).is_file():
             initial_dir = str(Path(current_path_str).parent)

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file dữ liệu JSON",
            initial_dir,
            "JSON files (*.json);;All files (*.*)"
        )
        if filename:
             self.data_file_path_entry.setText(filename)
             logger.info(f"Người dùng chọn file: {filename}")
             self.load_data()

    def load_data(self):
        logger.info("Đang tải dữ liệu xổ số...")
        self.results_data = []
        data_file_str = self.data_file_path_entry.text()

        if not data_file_str:
             default_path = self.data_dir / "xsmb-2-digits.json"
             if default_path.exists():
                 self.data_file_path_entry.setText(str(default_path))
                 data_file_str = str(default_path)
                 logger.info(f"Đường dẫn trống, dùng mặc định: {data_file_str}")
             else:
                 QMessageBox.information(self, "Chọn File Dữ Liệu", "Vui lòng chọn file dữ liệu JSON.")
                 self.browse_data_file() # Trigger browse
                 data_file_str = self.data_file_path_entry.text()
             if not data_file_str:
                 self.update_status("Chưa chọn file dữ liệu.")
                 self.data_range_label.setText("Chưa tải dữ liệu")
                 return

        data_file_path = Path(data_file_str)
        # Ensure the entry reflects the final path used
        self.data_file_path_entry.setText(str(data_file_path))

        if not data_file_path.exists():
            logger.error(f"Không tìm thấy file: {data_file_path}")
            QMessageBox.critical(self, "Lỗi", f"File không tồn tại:\n{data_file_path}")
            self.data_range_label.setText("Lỗi file dữ liệu")
            return

        try:
            # --- Keep the existing data processing logic ---
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
                processed_results.sort(key=lambda x: x['date'])
                self.results_data = processed_results
                start_date = self.results_data[0]['date']
                end_date = self.results_data[-1]['date']
                self.data_range_label.setText(f"{start_date:%d/%m/%Y} - {end_date:%d/%m/%Y} ({len(self.results_data)} ngày)")
                self.update_status(f"Đã tải {len(self.results_data)} kết quả từ {data_file_path.name}")
                logger.info(f"Đã tải thành công {len(self.results_data)} kết quả.")

                # Auto-fill optimizer dates if empty
                if not self.opt_start_date_entry.text() and len(self.results_data) > 1:
                    self.opt_start_date_entry.setText(start_date.strftime('%d/%m/%Y'))
                if not self.opt_end_date_entry.text() and len(self.results_data) > 1:
                    # End date must be one day before the last day in data
                    last_valid_end_date = end_date - datetime.timedelta(days=1)
                    self.opt_end_date_entry.setText(last_valid_end_date.strftime('%d/%m/%Y'))

            else:
                self.data_range_label.setText("Không có dữ liệu hợp lệ")
                self.update_status("Không tải được dữ liệu.")
                logger.warning("Không tải được dữ liệu hợp lệ sau khi xử lý.")

        except FileNotFoundError:
            logger.error(f"FileNotFoundError: {data_file_path}")
            # Already handled file existence check above
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"JSON/Dữ liệu không hợp lệ trong {data_file_path.name}: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Dữ Liệu", f"File '{data_file_path.name}' không hợp lệ:\n{e}")
            self.data_range_label.setText("Lỗi định dạng file")
        except Exception as e:
            logger.error(f"Lỗi không mong muốn khi tải dữ liệu: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi tải dữ liệu:\n{e}")
            self.data_range_label.setText("Lỗi tải dữ liệu")

    # --- Algorithm Handling ---
    def load_algorithms(self):
        logger.info("Đang tải thuật toán..."); self.loaded_algorithms.clear()
        self.algo_tree.clear() # Clear QTreeWidget
        self.disable_edit_optimize_tabs(); self.update_status("Đang tải thuật toán...")
        if not self.algorithms_dir.is_dir():
            logger.warning(f"Thiếu thư mục algorithms: {self.algorithms_dir}")
            QMessageBox.warning(self, "Thiếu Thư Mục", f"Không tìm thấy:\n{self.algorithms_dir}")
            self.update_status("Lỗi: Thiếu thư mục thuật toán."); return
        try:
            algo_files = [f for f in self.algorithms_dir.glob('*.py') if f.is_file() and f.name not in ["__init__.py", "base.py"]]
        except Exception as e:
            logger.error(f"Lỗi quét thư mục algorithms: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi", f"Lỗi đọc thư mục:\n{e}")
            return

        logger.info(f"Tìm thấy các file thuật toán tiềm năng: {[f.name for f in algo_files]}"); count_success = 0; count_fail = 0
        data_copy_for_init = copy.deepcopy(self.results_data) if self.results_data else []; cache_dir_for_init = self.calculate_dir

        for f_path in algo_files:
            module_name = f"algorithms.{f_path.stem}"; instance=None; config=None; class_name=None; module_obj=None; display_name=f"{f_path.stem}({f_path.name})"
            try:
                logger.debug(f"Đang xử lý file: {f_path.name}");
                # --- Keep module loading/reloading logic the same ---
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
                        desc = config.get("description", "N/A")
                        # Add to QTreeWidget
                        tree_item = QTreeWidgetItem([class_name, f_path.name, desc])
                        tree_item.setData(0, Qt.UserRole, display_name) # Store internal key
                        self.algo_tree.addTopLevelItem(tree_item)
                        count_success += 1; logger.debug(f"Đã tải: {display_name}")

                    except Exception as init_err: logger.error(f"Lỗi khởi tạo lớp {class_name} từ {f_path.name}: {init_err}", exc_info=True); count_fail += 1
                else: logger.warning(f"Không tìm thấy lớp con BaseAlgorithm hợp lệ trong {f_path.name}"); count_fail += 1
            except ImportError as imp_err: logger.error(f"Lỗi import khi xử lý {f_path.name}: {imp_err}", exc_info=True); count_fail += 1
            except Exception as load_err: logger.error(f"Lỗi không mong muốn khi xử lý {f_path.name}: {load_err}", exc_info=True); count_fail += 1

        status_msg = f"Đã tải {count_success} thuật toán";
        if count_fail > 0:
            status_msg += f" (lỗi: {count_fail})";
            QMessageBox.warning(self, "Lỗi Tải", f"Lỗi tải {count_fail} file. Kiểm tra log.")
        self.update_status(status_msg); logger.info(f"Tải thuật toán hoàn tất. Thành công: {count_success}, Thất bại: {count_fail}")

    def reload_algorithms(self):
        logger.info("Đang tải lại thuật toán..."); self.selected_algorithm_for_edit = None; self.selected_algorithm_for_optimize = None
        self.disable_edit_optimize_tabs(); self._clear_editor_fields()
        self._clear_advanced_opt_fields() # Reset advanced settings on reload
        self.load_algorithms()

    # --- Algorithm Selection and Tab Control ---
    def get_selected_algorithm_display_name(self):
        selected_items = self.algo_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            display_name = item.data(0, Qt.UserRole) # Retrieve stored key
            if display_name and display_name in self.loaded_algorithms:
                return display_name
        return None

    def select_algo_for_edit(self):
        display_name = self.get_selected_algorithm_display_name()
        if not display_name:
            QMessageBox.warning(self, "Chưa Chọn", "Chọn thuật toán để chỉnh sửa.")
            return
        logger.info(f"Đã chọn thuật toán để sửa: {display_name}"); self.selected_algorithm_for_edit = display_name; self.selected_algorithm_for_optimize = None
        self._clear_advanced_opt_fields() # Clear fields instead
        self.populate_editor(display_name);
        self.notebook.setTabEnabled(1, True) # Edit tab
        self.notebook.setTabEnabled(2, False) # Optimize tab
        self.notebook.setCurrentIndex(1); # Switch to Edit tab
        self.update_status(f"Đang chỉnh sửa: {self.loaded_algorithms[display_name]['class_name']}")

    def select_algo_for_optimize(self):
        display_name = self.get_selected_algorithm_display_name()
        if not display_name:
            QMessageBox.warning(self, "Chưa Chọn", "Chọn thuật toán để tối ưu hóa.")
            return
        if self.optimizer_running:
            QMessageBox.critical(self, "Đang Chạy", "Quá trình tối ưu khác đang chạy.")
            return
        logger.info(f"Đã chọn thuật toán để tối ưu: {display_name}"); self.selected_algorithm_for_optimize = display_name; self.selected_algorithm_for_edit = None
        self._clear_advanced_opt_fields() # Clear fields instead
        self.populate_optimizer_info(display_name);
        self.notebook.setTabEnabled(1, False) # Edit tab
        self.notebook.setTabEnabled(2, True) # Optimize tab
        self.notebook.setCurrentIndex(2); # Switch to Optimize tab
        self.update_status(f"Sẵn sàng tối ưu: {self.loaded_algorithms[display_name]['class_name']}")
        self._load_optimization_log()
        self._populate_advanced_optimizer_settings() # Populate advanced settings

    def disable_edit_optimize_tabs(self):
        if hasattr(self, 'notebook'):
            self.notebook.setTabEnabled(1, False) # Edit
            self.notebook.setTabEnabled(2, False) # Optimize
            self._clear_advanced_opt_fields() # Clear fields when optimize tab disabled


    # --- Editor Logic ---
    def populate_editor(self, display_name):
        self._clear_editor_fields()
        if display_name not in self.loaded_algorithms:
            logger.error(f"Cannot populate editor: Algorithm '{display_name}' not found.")
            return

        algo_data = self.loaded_algorithms[display_name]
        instance = algo_data['instance']
        config = algo_data['config']
        class_name = algo_data['class_name']

        self.edit_algo_name_label.setText(f"{class_name} ({algo_data['path'].name})")
        self.edit_algo_desc_label.setText(config.get("description", "N/A"))

        # Docstring
        try:
            docstring = inspect.getdoc(instance.__class__)
            self.edit_explain_text.setPlainText(docstring if docstring else "N/A")
        except Exception as e:
            logger.warning(f"Docstring error {class_name}: {e}")
            self.edit_explain_text.setPlainText(f"Lỗi lấy docstring: {e}")

        # Parameters
        parameters = config.get("parameters", {})
        self.editor_param_widgets = {}
        self.editor_original_params = copy.deepcopy(parameters)
        row_idx = 0

        # Clear previous widgets from layout
        while self.edit_param_layout.count():
            child = self.edit_param_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for name, value in parameters.items():
            if isinstance(value, (int, float)):
                lbl = QLabel(f"{name}:")
                entry = QLineEdit(str(value))
                if isinstance(value, int):
                    entry.setValidator(self.int_validator)
                else: # float
                    entry.setValidator(self.double_validator)
                entry.setAlignment(Qt.AlignRight)
                self.edit_param_layout.addWidget(lbl, row_idx, 0)
                self.edit_param_layout.addWidget(entry, row_idx, 1)
                self.editor_param_widgets[name] = entry # Store the QLineEdit
            else:
                # Display non-numeric params as labels
                lbl_name = QLabel(f"{name}:")
                lbl_val = QLabel(str(value))
                lbl_val.setStyleSheet("color: dimgray;") # Style as info
                self.edit_param_layout.addWidget(lbl_name, row_idx, 0)
                self.edit_param_layout.addWidget(lbl_val, row_idx, 1)
                # Optionally store the label if needed later, though unlikely for non-editable
                # self.editor_param_widgets[name] = lbl_val
            row_idx += 1
        self.edit_param_layout.setColumnStretch(1, 1) # Make entry column expand


    def _clear_editor_fields(self):
        self.edit_algo_name_label.setText("...")
        self.edit_algo_desc_label.setText("...")
        self.edit_explain_text.clear()
        self.editor_param_widgets = {}
        self.editor_original_params = {}
        # Clear widgets from the layout
        if hasattr(self, 'edit_param_layout'):
             while self.edit_param_layout.count():
                child = self.edit_param_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

    def cancel_edit(self):
        logger.info("Editing cancelled."); self.selected_algorithm_for_edit = None; self._clear_editor_fields(); self.disable_edit_optimize_tabs(); self.notebook.setCurrentIndex(0); self.update_status("Đã hủy chỉnh sửa.")

    def save_edited_copy(self):
        if not self.selected_algorithm_for_edit:
            logger.warning("Save copy called with no selection.")
            return
        display_name = self.selected_algorithm_for_edit
        if display_name not in self.loaded_algorithms:
            logger.error(f"Save copy error: Algorithm '{display_name}' not loaded.")
            QMessageBox.critical(self, "Lỗi", "Thuật toán được chọn không còn tồn tại.")
            return

        algo_data = self.loaded_algorithms[display_name]; original_path = algo_data['path']; class_name = algo_data['class_name']; modified_params = {}

        try:
            for name, widget in self.editor_param_widgets.items():
                 if isinstance(widget, QLineEdit): # Only process LineEdits
                    value_str = widget.text()
                    original_value = self.editor_original_params.get(name)
                    if isinstance(original_value, float):
                        modified_params[name] = float(value_str)
                    elif isinstance(original_value, int):
                        modified_params[name] = int(value_str)
        except ValueError as e:
            logger.error(f"Invalid numeric value during save: {e}", exc_info=True)
            QMessageBox.critical(self, "Giá Trị Lỗi", f"Vui lòng nhập giá trị số hợp lệ cho tất cả các tham số.\nLỗi: {e}")
            return

        final_params_for_save = self.editor_original_params.copy(); final_params_for_save.update(modified_params)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); suggested_filename = f"{original_path.stem}_edited_{timestamp}.py"

        save_path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu Bản Sao Thuật Toán",
            str(self.algorithms_dir / suggested_filename), # Initial path and filename
            "Python Files (*.py);;All Files (*.*)"
        )

        if not save_path_str:
            logger.info("Save edited copy cancelled by user.")
            return

        save_path = Path(save_path_str)

        # Prevent overwriting original file
        if save_path.exists() and save_path.resolve() == original_path.resolve():
             QMessageBox.critical(self, "Lỗi Lưu", "Không thể ghi đè lên file thuật toán gốc. Vui lòng chọn tên khác.")
             logger.error("Attempted to overwrite original algorithm file during save copy.")
             return

        try:
            logger.info(f"Reading original source: {original_path}"); source_code = original_path.read_text(encoding='utf-8')
            logger.info("Modifying AST for edited parameters...")
            modified_source = self.modify_algorithm_source_ast(source_code, class_name, final_params_for_save) # AST logic remains the same

            if modified_source is None:
                raise ValueError("AST modification failed (returned None).")

            logger.info(f"Writing modified source to: {save_path}"); save_path.write_text(modified_source, encoding='utf-8')
            QMessageBox.information(self, "Lưu Thành Công", f"Đã lưu bản sao thuật toán đã chỉnh sửa vào:\n{save_path.name}\n\nVui lòng 'Tải lại Danh sách Thuật toán' để sử dụng.")
            self.update_status(f"Đã lưu bản sao: {save_path.name}"); logger.info(f"Successfully saved edited copy to {save_path}")

        except Exception as e:
            logger.error(f"Error saving edited algorithm copy: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Lưu", f"Không thể lưu bản sao thuật toán:\n{e}")


    # --- AST Modification (KEEP AS IS - Backend Logic) ---
    def modify_algorithm_source_ast(self, source_code, target_class_name, new_params):
        logger.debug(f"AST mod: Class '{target_class_name}' (Params & Imports)")
        try: tree = ast.parse(source_code)
        except SyntaxError as e: logger.error(f"Syntax error parsing: {e}", exc_info=True); return None
        class _SourceModifier(ast.NodeTransformer):
            def __init__(self, class_to_modify, params_to_update):
                self.target_class = class_to_modify; self.params_to_update = params_to_update; self.in_target_init = False; self.params_modified = False; self.imports_modified = False; self.current_class_name = None; super().__init__()
            def visit_ImportFrom(self, node):
                # Attempt to fix relative imports like 'from .base import ...'
                if node.level > 0 and node.module == 'base':
                    logger.debug(f"Fixing relative import in AST: '.{node.module}' -> 'algorithms.{node.module}'")
                    node.module = f'algorithms.{node.module}' # Make it absolute relative to package
                    node.level = 0 # Set level to 0 for absolute import
                    self.imports_modified = True
                elif node.level > 0 and node.module is None: # Warn about 'from . import X' which is harder to fix automatically
                     logger.warning(f"Cannot automatically fix relative import 'from . import ...' at line {node.lineno}")
                return self.generic_visit(node)
            def visit_ClassDef(self, node):
                original_class = self.current_class_name; self.current_class_name = node.name
                if node.name == self.target_class:
                    logger.debug(f"AST Visitor: Found target class: {node.name}")
                    # Visit children of the target class
                    node.body = [self.visit(child) for child in node.body]
                else:
                    # Visit children of other classes normally
                    self.generic_visit(node)
                self.current_class_name = original_class # Restore context
                return node
            def visit_FunctionDef(self, node):
                if node.name == '__init__' and self.current_class_name == self.target_class:
                     logger.debug(f"AST Visitor: Entering __init__ of {self.target_class}")
                     self.in_target_init = True
                     # Visit children of the __init__ method
                     node.body = [self.visit(child) for child in node.body]
                     self.in_target_init = False
                     logger.debug(f"AST Visitor: Exiting __init__ of {self.target_class}")
                else:
                    # Visit children of other functions normally
                    self.generic_visit(node)
                return node
            def visit_Assign(self, node):
                # Look for assignments like 'self.config = {...}' within the target class's __init__
                if self.in_target_init and len(node.targets) == 1:
                    target = node.targets[0]
                    # Check if it's an attribute assignment to 'self.config'
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self' and target.attr == 'config':
                        logger.debug("AST Visitor: Found 'self.config' assignment.")
                        # Visit the value being assigned (likely a dict) to modify 'parameters' inside it
                        node.value = self.visit(node.value)
                        return node # Return the modified assignment node
                # Handle other assignments normally
                return self.generic_visit(node)
            def visit_Dict(self, node):
                 # Only modify dictionaries if we are inside the target __init__
                 # and specifically looking for the 'parameters' key within the 'self.config' dict
                 if not self.in_target_init:
                     return self.generic_visit(node) # Skip if not in target init

                 param_key_index = -1
                 param_value_node = None
                 try:
                     # Iterate through keys to find the 'parameters' key (must be a Constant string)
                     for i, key_node in enumerate(node.keys):
                         if key_node is not None and isinstance(key_node, ast.Constant) and isinstance(key_node.value, str) and key_node.value == 'parameters':
                             param_key_index = i
                             param_value_node = node.values[i] # Get the corresponding value node (should be a dict)
                             logger.debug("AST Visitor: Found 'parameters' key in dictionary.")
                             break
                 except AttributeError: # Handle cases where node.keys might be None (e.g., empty dict {})
                     return self.generic_visit(node)


                 # If 'parameters' key found and its value is a Dictionary node
                 if param_key_index != -1 and isinstance(param_value_node, ast.Dict):
                     logger.debug("AST Visitor: Processing 'parameters' sub-dictionary.")
                     new_keys = []
                     new_values = []
                     modified_in_subdict = False

                     # Build a map of original parameter names to their key/value AST nodes
                     original_param_nodes = {}
                     if param_value_node.keys is not None: # Ensure keys exist
                          original_param_nodes = {
                              k.value: (k, v)
                              for k, v in zip(param_value_node.keys, param_value_node.values)
                              if isinstance(k, ast.Constant) # Only consider constant string keys
                          }

                     # Update values for parameters present in new_params
                     for param_name, new_value in self.params_to_update.items():
                         if param_name in original_param_nodes:
                             p_key_node, p_val_node = original_param_nodes[param_name]
                             new_val_node = None

                             # Create new AST Constant node for the new value
                             if isinstance(new_value, (int, float)):
                                 # Handle negative numbers correctly using UnaryOp
                                 if new_value < 0:
                                     new_val_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=abs(new_value)))
                                 else:
                                     new_val_node = ast.Constant(value=new_value)
                             elif isinstance(new_value, str):
                                 new_val_node = ast.Constant(value=new_value)
                             elif isinstance(new_value, bool):
                                 new_val_node = ast.Constant(value=new_value) # True/False are constants in Python 3
                             elif new_value is None:
                                 new_val_node = ast.Constant(value=None) # None is a constant

                             if new_val_node is not None:
                                 new_keys.append(p_key_node) # Keep original key node
                                 new_values.append(new_val_node) # Use new value node
                                 logger.debug(f"AST Visitor: Updated '{param_name}' node value to {new_value}")
                                 modified_in_subdict = True
                             else:
                                 # Keep original if type is not supported for modification
                                 logger.warning(f"AST Visitor: Unsupported type for parameter '{param_name}': {type(new_value)}. Keeping original value.")
                                 new_keys.append(p_key_node)
                                 new_values.append(p_val_node)
                         else:
                             logger.warning(f"AST Visitor: Parameter '{param_name}' from update list not found in original 'parameters' dict. Skipping.")

                     # Add back parameters that were not in the update list
                     updated_keys = set(self.params_to_update.keys())
                     for name, (k_node, v_node) in original_param_nodes.items():
                          if name not in updated_keys:
                              new_keys.append(k_node)
                              new_values.append(v_node)

                     # Replace the keys and values of the 'parameters' dictionary node
                     param_value_node.keys = new_keys
                     param_value_node.values = new_values
                     if modified_in_subdict:
                         self.params_modified = True # Mark that we changed parameters

                 # Continue visiting other parts of the dictionary (if any)
                 return self.generic_visit(node)

        modifier = _SourceModifier(target_class_name, new_params); modified_tree = modifier.visit(tree)
        if not modifier.params_modified and not modifier.imports_modified:
            logger.warning("AST modification finished, but no parameters or imports seem to have been updated.")
        elif modifier.params_modified:
             logger.info("AST modification finished, parameters updated.")
        elif modifier.imports_modified:
             logger.info("AST modification finished, imports updated.")

        # Unparse the modified AST back into source code
        try:
            if hasattr(ast, 'unparse'): # Python 3.9+
                modified_code = ast.unparse(modified_tree)
                logger.debug("Unparsed modified AST using ast.unparse (Python 3.9+)")
            elif HAS_ASTOR: # Python < 3.9 with astor installed
                modified_code = astor.to_source(modified_tree)
                logger.debug("Unparsed modified AST using astor")
            else:
                # This case should ideally be prevented by checks at startup
                logger.critical("AST unparsing failed. Requires Python 3.9+ or the 'astor' library for older versions.")
                return None
        except Exception as unparse_err:
            logger.error(f"Error unparsing modified AST: {unparse_err}", exc_info=True)
            return None

        return modified_code


    # --- Optimizer Logic ---

    def _populate_advanced_optimizer_settings(self):
        """Fills the advanced optimization frame with controls for numeric parameters."""
        logger.debug("Populating advanced optimization settings frame (PyQt).")

        # Clear previous widgets first
        while self.advanced_opt_params_layout.count():
             item = self.advanced_opt_params_layout.takeAt(0)
             widget = item.widget()
             if widget:
                 widget.deleteLater()
        self.advanced_opt_widgets.clear() # Clear the tracking dict

        if not self.selected_algorithm_for_optimize:
            self.advanced_opt_params_layout.addWidget(QLabel("Chưa chọn thuật toán."))
            return

        display_name = self.selected_algorithm_for_optimize
        if display_name not in self.loaded_algorithms:
            err_label = QLabel("Lỗi: Thuật toán không tìm thấy.")
            err_label.setStyleSheet("color: red;")
            self.advanced_opt_params_layout.addWidget(err_label)
            logger.error(f"Cannot populate advanced opts: Algorithm '{display_name}' not found.")
            return

        algo_data = self.loaded_algorithms[display_name]
        parameters = algo_data['config'].get('parameters', {})
        numeric_params = {k: v for k, v in parameters.items() if isinstance(v, (int, float))}

        if not numeric_params:
            self.advanced_opt_params_layout.addWidget(QLabel("Không có tham số số học để tùy chỉnh."))
            return

        # Add header row using QHBoxLayout (simpler than grid for this)
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>Tham số</b>"), 3) # Stretch factors for rough sizing
        header_layout.addWidget(QLabel("<b>Giá trị gốc</b>"), 2)
        header_layout.addWidget(QLabel("<b>Chế độ</b>"), 1)
        header_layout.addWidget(QLabel("<b>Bước (+/-)</b>"), 3)
        self.advanced_opt_params_layout.addLayout(header_layout)

        # Add rows for each parameter
        for name, value in numeric_params.items():
            param_layout = QHBoxLayout()

            # Ensure state exists for this param
            if name not in self.optimizer_custom_steps:
                self.optimizer_custom_steps[name] = {'mode': 'Auto', 'steps': [], 'str_var': ""} # Store string directly now
            param_state = self.optimizer_custom_steps[name]

            name_lbl = QLabel(name)
            value_lbl = QLabel(f"{value:.4g}" if isinstance(value, float) else str(value))
            value_lbl.setStyleSheet("color: dimgray;")
            mode_combo = QComboBox()
            mode_combo.addItems(["Auto", "Custom"])
            mode_combo.setCurrentText(param_state['mode'])
            steps_entry = QLineEdit(param_state['str_var'])
            # No need for QValidator here, we validate on change/start
            steps_entry.setPlaceholderText("vd: 1, 0.5, 10")

            # Set initial state based on mode
            steps_entry.setEnabled(param_state['mode'] == 'Custom')
            # Reset style in case it was previously invalid
            self._apply_entry_validation_style(steps_entry, True)

            # Store widgets
            self.advanced_opt_widgets[name] = {'mode_combo': mode_combo, 'steps_entry': steps_entry}

            # Layout widgets with stretch factors
            param_layout.addWidget(name_lbl, 3)
            param_layout.addWidget(value_lbl, 2)
            param_layout.addWidget(mode_combo, 1)
            param_layout.addWidget(steps_entry, 3)
            self.advanced_opt_params_layout.addLayout(param_layout)

            # Connect signals for this row
            mode_combo.currentIndexChanged.connect(
                lambda index, n=name, m=mode_combo, e=steps_entry: self._on_step_mode_change(n, m, e)
            )
            # Validate and update state when text changes
            steps_entry.textChanged.connect(
                lambda text, n=name, e=steps_entry: self._update_custom_steps(n, text, e)
            )

        # Add a stretch at the end to push items up if the area is large
        self.advanced_opt_params_layout.addStretch(1)


    def _on_step_mode_change(self, param_name, mode_combo_widget, steps_entry_widget):
        """Handles the change event for the step mode Combobox."""
        new_mode = mode_combo_widget.currentText()
        logger.debug(f"Step mode change for '{param_name}' to '{new_mode}'")
        if param_name in self.optimizer_custom_steps:
            self.optimizer_custom_steps[param_name]['mode'] = new_mode
            is_custom = (new_mode == 'Custom')
            steps_entry_widget.setEnabled(is_custom)

            if is_custom:
                # Re-validate and update state when switching *to* Custom
                current_text = steps_entry_widget.text()
                self._update_custom_steps(param_name, current_text, steps_entry_widget)
                steps_entry_widget.setFocus()
            else: # Switched to Auto
                # Clear validation error style if switching to Auto
                self._apply_entry_validation_style(steps_entry_widget, True)
                # Optionally clear the text or parsed steps for Auto mode
                # self.optimizer_custom_steps[param_name]['steps'] = []
                # self.optimizer_custom_steps[param_name]['str_var'] = ""
                # steps_entry_widget.setText("")

        else:
            logger.warning(f"Parameter '{param_name}' not found in custom steps state during mode change.")


    def _update_custom_steps(self, param_name, steps_str, steps_entry_widget):
        """Parses the custom steps string, updates state, and validates visually."""
        if param_name not in self.optimizer_custom_steps:
             logger.warning(f"Param '{param_name}' not found during custom steps update.")
             return

        # Store the raw string input
        self.optimizer_custom_steps[param_name]['str_var'] = steps_str

        # Only parse and validate if mode is Custom
        if self.optimizer_custom_steps[param_name]['mode'] == 'Custom':
            is_valid = self._validate_custom_steps_qt(steps_str)
            self._apply_entry_validation_style(steps_entry_widget, is_valid)

            if not is_valid:
                if self.optimizer_custom_steps[param_name]['steps']: # Clear parsed steps if invalid
                    self.optimizer_custom_steps[param_name]['steps'] = []
                return # Stop if invalid

            # If valid, attempt to parse into numbers
            parsed_steps = []
            parts = steps_str.split(',')
            try:
                # Need original value type to parse correctly
                if self.selected_algorithm_for_optimize and self.selected_algorithm_for_optimize in self.loaded_algorithms:
                    original_value = self.loaded_algorithms[self.selected_algorithm_for_optimize]['config']['parameters'].get(param_name)
                    if original_value is None: raise KeyError(f"Original value for {param_name} not found for type check.")
                    is_original_int = isinstance(original_value, int)
                else:
                    # Should not happen if called correctly, but handle defensively
                    logger.warning(f"Cannot determine original type for '{param_name}' during step parse.")
                    # Default to float parsing if type unknown
                    is_original_int = False
                    # raise ValueError("Algorithm not selected/loaded for type check.") # Or raise error

                for part in parts:
                    part = part.strip()
                    if part:
                        num_val = float(part) # Parse as float first
                        # Convert to int only if original was int
                        parsed_steps.append(int(num_val) if is_original_int else num_val)

                # Update state only if parsed steps actually changed
                if parsed_steps != self.optimizer_custom_steps[param_name].get('steps'):
                    self.optimizer_custom_steps[param_name]['steps'] = parsed_steps
                    logger.debug(f"Updated parsed custom steps for '{param_name}': {parsed_steps}")

            except (ValueError, KeyError, TypeError) as e:
                logger.error(f"Error parsing valid steps string for '{param_name}': '{steps_str}' ({e})")
                self.optimizer_custom_steps[param_name]['steps'] = []
                # Mark as invalid visually again, even if regex passed initially
                self._apply_entry_validation_style(steps_entry_widget, False)
        # else: Mode is Auto, do nothing with steps_str parsing


    def _clear_advanced_opt_fields(self):
         """Clears widgets and data related to advanced optimization settings."""
         logger.debug("Clearing advanced optimization fields (PyQt).")
         self.optimizer_custom_steps.clear()
         # Clear widgets from the layout
         while self.advanced_opt_params_layout.count():
             item = self.advanced_opt_params_layout.takeAt(0)
             widget = item.widget()
             layout = item.layout()
             if widget:
                 widget.deleteLater()
             elif layout: # Need to clear widgets within the layout too
                 while layout.count():
                     sub_item = layout.takeAt(0)
                     sub_widget = sub_item.widget()
                     if sub_widget:
                         sub_widget.deleteLater()
                 # Optional: delete the layout itself if it was dynamically created
                 # layout.deleteLater() # Be careful with this if layout belongs to a parent widget

         self.advanced_opt_widgets.clear()
         # Add back the placeholder label
         self.advanced_opt_params_layout.addWidget(QLabel("Chọn thuật toán để xem tham số."))
         # Add stretch again
         self.advanced_opt_params_layout.addStretch(1)


    def populate_optimizer_info(self, display_name):
        if display_name in self.loaded_algorithms:
            class_name = self.loaded_algorithms[display_name]['class_name']
            filename = self.loaded_algorithms[display_name]['path'].name
            self.opt_algo_name_label.setText(f"{class_name} ({filename})")
        else:
            self.opt_algo_name_label.setText("Lỗi: Không tìm thấy thuật toán")
            self.opt_algo_name_label.setStyleSheet("color: red;")


    def start_optimization(self):
        if self.optimizer_running:
            QMessageBox.warning(self, "Đang Chạy", "Quá trình tối ưu hóa khác đang chạy.")
            return
        if not self.selected_algorithm_for_optimize:
            QMessageBox.critical(self, "Lỗi", "Chưa chọn thuật toán để tối ưu hóa.")
            return
        display_name = self.selected_algorithm_for_optimize
        if display_name not in self.loaded_algorithms:
            QMessageBox.critical(self, "Lỗi", f"Thuật toán '{display_name}' không còn được tải.")
            return

        algo_data = self.loaded_algorithms[display_name]; original_params = algo_data['config'].get('parameters', {})
        numeric_params = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}
        if not numeric_params:
            QMessageBox.information(self, "Thông Báo", "Thuật toán này không có tham số số học nào để tối ưu.")
            return

        # Validate Dates
        start_s = self.opt_start_date_entry.text(); end_s = self.opt_end_date_entry.text()
        if not start_s or not end_s:
            QMessageBox.warning(self, "Thiếu Ngày", "Vui lòng chọn ngày Bắt đầu và Kết thúc cho khoảng thời gian kiểm tra.")
            return
        try:
            start_d = datetime.datetime.strptime(start_s, '%d/%m/%Y').date()
            end_d = datetime.datetime.strptime(end_s, '%d/%m/%Y').date()
        except ValueError:
            QMessageBox.critical(self, "Lỗi Ngày", "Định dạng ngày không hợp lệ. Sử dụng định dạng dd/MM/yyyy.")
            return
        if start_d > end_d:
            QMessageBox.warning(self, "Ngày Lỗi", "Ngày Bắt đầu phải nhỏ hơn hoặc bằng Ngày Kết thúc.")
            return
        if not self.results_data or len(self.results_data) < 2:
             QMessageBox.critical(self, "Thiếu Dữ Liệu", "Cần ít nhất 2 ngày dữ liệu kết quả để thực hiện tối ưu.")
             return

        min_data_date = self.results_data[0]['date']; max_data_date = self.results_data[-1]['date']
        # Optimization requires predicting for end_d, which needs data for end_d + 1 day
        # So, end_d must be strictly less than the last date in the dataset.
        if start_d < min_data_date or end_d >= max_data_date:
            max_allowed_end_date = max_data_date - datetime.timedelta(days=1)
            QMessageBox.critical(self, "Lỗi Khoảng Ngày",
                                 f"Khoảng ngày kiểm tra ({start_s} - {end_s}) không hợp lệ.\n"
                                 f"Yêu cầu:\n"
                                 f"- Ngày Bắt đầu >= {min_data_date:%d/%m/%Y}\n"
                                 f"- Ngày Kết thúc <= {max_allowed_end_date:%d/%m/%Y} (phải trước ngày cuối cùng trong dữ liệu)")
            return

        # Validate Time Limit
        try:
            time_limit_min = int(self.opt_time_limit_entry.text())
            if time_limit_min <= 0: raise ValueError()
        except ValueError:
            QMessageBox.critical(self, "Lỗi Thời Gian", "Thời gian tối ưu tối đa phải là một số nguyên dương (phút).")
            return

        # Validate and Finalize Custom Steps Config
        final_custom_steps_config = {}
        has_invalid_custom_steps = False
        invalid_params_display = []
        for name, state in self.optimizer_custom_steps.items():
            mode = state.get('mode', 'Auto')
            steps = []
            steps_str = state.get('str_var', "") # Get stored string
            widget_ref = self.advanced_opt_widgets.get(name, {})
            entry_widget = widget_ref.get('steps_entry')
            combo_widget = widget_ref.get('mode_combo')

            if mode == 'Custom':
                is_valid_str = self._validate_custom_steps_qt(steps_str)
                if entry_widget: self._apply_entry_validation_style(entry_widget, is_valid_str)

                if is_valid_str:
                    # Attempt final parse before starting
                    parsed = []
                    parts = steps_str.split(',')
                    try:
                        original_value = original_params[name]
                        is_original_int = isinstance(original_value, int)
                        for part in parts:
                            part = part.strip()
                            if part:
                                num_val = float(part)
                                parsed.append(int(num_val) if is_original_int else num_val)

                        if parsed:
                             steps = parsed # Use parsed steps
                        else: # Valid format but no actual steps parsed (e.g., just commas)
                             logger.warning(f"Chuỗi bước tùy chỉnh hợp lệ nhưng trống cho '{name}'. Dùng Auto.")
                             mode = 'Auto'; steps = []
                             if combo_widget: combo_widget.setCurrentText('Auto')
                             if entry_widget: entry_widget.setEnabled(False); self._apply_entry_validation_style(entry_widget, True)


                    except (ValueError, KeyError) as parse_err:
                        logger.error(f"Lỗi parse cuối cùng cho bước tùy chỉnh '{name}' trước khi bắt đầu: {parse_err}. Dùng Auto.")
                        mode = 'Auto'; steps = []; has_invalid_custom_steps = True; invalid_params_display.append(name)
                        if combo_widget: combo_widget.setCurrentText('Auto')
                        if entry_widget: entry_widget.setEnabled(False); self._apply_entry_validation_style(entry_widget, False) # Mark as invalid visually

                else: # String format itself is invalid
                     logger.warning(f"Bước tùy chỉnh không hợp lệ cho '{name}' khi bắt đầu: '{steps_str}'. Dùng Auto.")
                     mode = 'Auto'; steps = []; has_invalid_custom_steps = True; invalid_params_display.append(name)
                     if combo_widget: combo_widget.setCurrentText('Auto')
                     if entry_widget: entry_widget.setEnabled(False); self._apply_entry_validation_style(entry_widget, False) # Mark as invalid visually

            # Store final decision for the worker
            final_custom_steps_config[name] = {'mode': mode, 'steps': steps}
            if mode == 'Custom': logger.info(f"Opt Start Prep - Param '{name}': Mode=Custom, Steps={steps}")
            else: logger.info(f"Opt Start Prep - Param '{name}': Mode=Auto")

        # Warn if any were reset to Auto
        if has_invalid_custom_steps:
            QMessageBox.warning(self, "Bước Không Hợp Lệ",
                                f"Một số cấu hình bước tùy chỉnh không hợp lệ và đã được đặt lại về 'Auto':\n"
                                f"{', '.join(invalid_params_display)}\n\n"
                                f"Vui lòng kiểm tra định dạng (số cách nhau bằng dấu phẩy).")
            # UI state already updated above

        # --- Prepare for thread ---
        self.current_optimize_target_dir = self.optimize_dir / algo_data['path'].stem
        self.current_optimize_target_dir.mkdir(parents=True, exist_ok=True)
        success_dir = self.current_optimize_target_dir / "success"; success_dir.mkdir(parents=True, exist_ok=True)
        self.current_optimization_log_path = self.current_optimize_target_dir / "optimization_qt.log"

        self.opt_log_text.clear() # Clear previous log display
        self._clear_cache_directory() # Clear calculation cache

        self.optimizer_stop_event.clear(); self.optimizer_pause_event.clear(); self.optimizer_running = True; self.optimizer_paused = False
        self.opt_progressbar.setValue(0); self.opt_progress_label.setText("0%")
        self.update_optimizer_ui_state() # Disable start, enable stop/pause

        # --- Create and Start Thread ---
        self.optimizer_thread_obj = QThread() # Parent thread for the worker
        self.optimizer_worker = OptimizerWorker(
            self.optimizer_queue, # Input queue for control (optional)
            self.optimizer_signals, # Signal object for output
            self.optimizer_stop_event,
            self.optimizer_pause_event,
            display_name,
            copy.deepcopy(self.loaded_algorithms), # Pass necessary data
            copy.deepcopy(self.results_data),
            self.calculate_dir,
            start_d,
            end_d,
            time_limit_min * 60,
            final_custom_steps_config,
            self.current_optimize_target_dir,
            self.base_dir
        )
        self.optimizer_worker.moveToThread(self.optimizer_thread_obj)

        # Connect thread signals
        self.optimizer_thread_obj.started.connect(self.optimizer_worker.run)
        # Use finished signal from worker, not thread, as worker controls completion logic
        self.optimizer_signals.finished.connect(self.optimizer_thread_obj.quit) # Quit thread on finish signal
        self.optimizer_worker.finished_internal.connect(self.optimizer_thread_obj.quit) # Backup quit
        self.optimizer_worker.finished_internal.connect(self.optimizer_worker.deleteLater) # Schedule worker deletion
        self.optimizer_thread_obj.finished.connect(self.optimizer_thread_obj.deleteLater) # Schedule thread deletion

        self.optimizer_thread_obj.start()

        # Start the queue check timer (checks every 200ms)
        if not self.queue_timer.isActive():
            self.queue_timer.start(200)

        self.update_status(f"Bắt đầu tối ưu: {algo_data['class_name']}...")

    def pause_or_resume_optimization(self):
        if not self.optimizer_running: return

        if self.optimizer_paused:
            # Resume
            self.optimizer_pause_event.clear()
            self.optimizer_paused = False
            self.update_optimizer_ui_state()
            self.update_status("Tiếp tục tối ưu...")
            logger.info("Optimization resumed.")
            self._log_to_optimizer_display("INFO", "[CONTROL] Tiếp tục.")
        else:
            # Pause
            self.optimizer_pause_event.set()
            self.optimizer_paused = True
            self.update_optimizer_ui_state()
            self.update_status("Đã tạm dừng.")
            logger.info("Optimization paused.")
            self._log_to_optimizer_display("INFO", "[CONTROL] Tạm dừng.")

    # pause_optimization REMOVED (merged into pause_or_resume_optimization)
    # resume_optimization REMOVED (merged into pause_or_resume_optimization)

    def stop_optimization(self):
        if self.optimizer_running:
             reply = QMessageBox.question(self, "Xác Nhận Dừng",
                                           "Bạn có chắc muốn dừng quá trình tối ưu hóa không?\n"
                                           "Luồng sẽ cố gắng hoàn thành vòng lặp hiện tại trước khi dừng hẳn.",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
             if reply == QMessageBox.Yes:
                self.optimizer_stop_event.set()
                # Visually indicate stopping state
                self.opt_start_button.setEnabled(False)
                self.opt_pause_button.setText("Đang dừng...")
                self.opt_pause_button.setEnabled(False)
                self.opt_stop_button.setEnabled(False)
                self.update_status("Đang yêu cầu dừng...")
                logger.info("Optimization stop requested.")
                self._log_to_optimizer_display("WARNING", "[CONTROL] Yêu cầu dừng...")
                # The worker thread will check the event and emit 'finished'

    def update_optimizer_ui_state(self):
        """Updates the enable/disable state of optimizer controls."""
        running = self.optimizer_running
        paused = self.optimizer_paused

        self.opt_start_button.setEnabled(not running)
        self.opt_stop_button.setEnabled(running) # Can always stop if running

        # Pause/Resume Button Logic
        self.opt_pause_button.setEnabled(running)
        if running:
            if paused:
                self.opt_pause_button.setText("Tiếp tục")
                self.opt_pause_button.setObjectName("WarningButton") # Style for Resume
            else:
                self.opt_pause_button.setText("Tạm dừng")
                self.opt_pause_button.setObjectName("WarningButton") # Style for Pause
        else:
            self.opt_pause_button.setText("Tạm dừng") # Default text when not running
            self.opt_pause_button.setEnabled(False)

        # Re-apply stylesheet to update button appearance if needed
        self.opt_pause_button.style().unpolish(self.opt_pause_button)
        self.opt_pause_button.style().polish(self.opt_pause_button)

        # Disable/Enable Advanced Settings Controls during optimization
        for name, widgets in self.advanced_opt_widgets.items():
            widgets['mode_combo'].setEnabled(not running)
            # Only enable entry if mode is 'Custom' AND not running
            is_custom = (widgets['mode_combo'].currentText() == 'Custom')
            widgets['steps_entry'].setEnabled(is_custom and not running)


    def update_optimizer_progress(self, value):
        """Slot to update the progress bar."""
        progress_val = int(value * 100)
        self.opt_progressbar.setValue(progress_val)
        self.opt_progress_label.setText(f"{progress_val}%")

    def handle_best_update(self, params_dict, score_tuple_list):
        """Slot to handle updates to the best parameters found."""
        # Convert list back to tuple if needed, ensure it matches scoring logic
        score_tuple = tuple(score_tuple_list)
        self.current_best_params = params_dict
        self.current_best_score_tuple = score_tuple
        # Optionally display the score somewhere if desired

    def handle_optimization_finished(self, message, success):
        """Slot called when the optimizer worker signals completion."""
        logger.info(f"Optimization finished signal received. Success: {success}, Msg: {message}")
        self.optimizer_running = False
        self.optimizer_paused = False
        self.update_optimizer_ui_state() # Reset button states
        self.opt_progressbar.setValue(100) # Ensure progress is 100%
        self.opt_progress_label.setText("100%")
        self.opt_status_label.setText(f"Trạng thái: {message}")

        if success:
            self.update_status(f"Tối ưu hoàn tất: {message}")
            self._log_to_optimizer_display("BEST", f"[HOÀN TẤT] {message}")
            QMessageBox.information(self, "Tối Ưu Hoàn Tất", message)
        else:
            # If stopped by user, it might still be considered 'success=False' by worker
            # Depending on implementation. Check message content.
            if "Dừng bởi user" in message:
                 self.update_status(f"Đã dừng: {message}")
                 self._log_to_optimizer_display("WARNING", f"[ĐÃ DỪNG] {message}")
                 QMessageBox.warning(self, "Tối Ưu Đã Dừng", message)
            else:
                self.update_status(f"Kết thúc với lỗi: {message}")
                self._log_to_optimizer_display("ERROR", f"[KẾT THÚC LỖI] {message}")
                QMessageBox.critical(self, "Tối Ưu Kết Thúc", f"Quá trình tối ưu kết thúc không thành công:\n{message}")

        # Stop the queue check timer
        if self.queue_timer.isActive():
            self.queue_timer.stop()

        # Clean up thread/worker references (optional, depends on deletion strategy)
        self.optimizer_thread_obj = None
        self.optimizer_worker = None

        # Important: Reload algorithms list in case the best one was saved
        # Or prompt the user to reload
        # self.reload_algorithms() # Consider if auto-reload is desired


    def _check_optimizer_queue(self):
        """
        DEPRECATED / Simplified: Primarily used if worker thread needs complex
        data transfer back that doesn't fit signals well, or for compatibility
        with the original direct queue usage. Signals are preferred.
        This can be kept minimal or removed if signals cover all communication.
        """
        try:
            # Process any remaining messages if direct queue usage is still needed
            # for some specific communication pattern not handled by signals.
            while True: # Process all available messages
                message = self.optimizer_queue.get_nowait()
                # Example: Handle a complex data structure message
                # msg_type = message.get("type")
                # if msg_type == "complex_data":
                #     payload = message.get("payload")
                #     self.process_complex_data(payload)
                logger.debug(f"Processing message from queue (legacy): {message.get('type', 'N/A')}")

        except queue.Empty:
            pass # No more messages
        except Exception as e:
            logger.error(f"Lỗi xử lý optimizer queue (legacy): {e}", exc_info=True)

        # Keep timer running only if optimization is active
        # if self.optimizer_running and not self.queue_timer.isActive():
        #      self.queue_timer.start(200)
        # elif not self.optimizer_running and self.queue_timer.isActive():
        #      self.queue_timer.stop()


    def _log_to_optimizer_display(self, level, text, tag=None):
        """Logs message to file, console, and the optimizer log QTextEdit."""
        # Log to file/console
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"[Optimizer] {text}")

        # Log to QTextEdit
        if hasattr(self, 'opt_log_text') and self.opt_log_text:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            level_upper = level.upper()
            log_entry = f"{timestamp} [{level_upper}] {text}"

            # Basic HTML formatting for color
            color = "black" # Default
            font_weight = "normal"
            text_decoration = "none"

            if tag == "BEST" or level_upper == "BEST":
                color = "darkgreen"
                font_weight = "bold"
            elif tag == "PROGRESS" or level_upper == "PROGRESS":
                 color = "blue"
            elif tag == "CUSTOM_STEP" or level_upper == "CUSTOM_STEP":
                 color = "purple"
            elif level_upper == "WARNING":
                color = "orange"
            elif level_upper == "ERROR":
                color = "red"
                font_weight = "bold"
            elif level_upper == "CRITICAL":
                color = "red"
                font_weight = "bold"
                text_decoration = "underline"
            elif level_upper == "DEBUG":
                color = "gray"

            html_log_entry = (
                f'<span style="color:{color}; font-weight:{font_weight}; text-decoration:{text_decoration};">'
                f'{log_entry.replace("<", "&lt;").replace(">", "&gt;")}</span>' # Basic HTML escape
            )

            self.opt_log_text.append(html_log_entry) # append handles scrolling
            # self.opt_log_text.moveCursor(QTextCursor.End) # Ensure scroll with append

            # Append to log file
            if self.current_optimization_log_path:
                try:
                    with open(self.current_optimization_log_path, "a", encoding="utf-8") as f:
                        f.write(f"{datetime.datetime.now().isoformat()} [{level_upper}] {text}\n")
                except Exception as log_write_err:
                    # Avoid logging storm, log only once or twice
                    if not hasattr(self, '_log_write_error_logged'):
                         logger.error(f"Không thể ghi vào file log tối ưu {self.current_optimization_log_path}: {log_write_err}")
                         self._log_write_error_logged = True


    # _optimization_worker MOVED to OptimizerWorker class


    # run_performance_test MOVED to OptimizerWorker class


    # calculate_performance_for_instance MOVED to OptimizerWorker class


    # --- Utility Methods ---
    def update_status(self, message):
        if hasattr(self, 'status_bar') and self.status_bar:
            current = self.status_bar.currentMessage()
            if message != current:
                self.status_bar.showMessage(message, 5000) # Show for 5 seconds
                logger.info(f"Status: {message}")
                # No need for root.update_idletasks() in PyQt

    def show_calendar_dialog(self, target_line_edit):
        """Shows a modal calendar dialog and updates the target QLineEdit."""
        if not self.results_data:
            QMessageBox.warning(self, "Thiếu Dữ Liệu", "Chưa tải dữ liệu kết quả.")
            return

        current_val_str = target_line_edit.text()
        current_date = None
        min_date = self.results_data[0]['date']
        max_date = self.results_data[-1]['date']
        # Determine max allowed date for start/end selection based on context
        # For end date, it must be less than max_date
        if target_line_edit == self.opt_end_date_entry:
             max_selectable_date = max_date - datetime.timedelta(days=1)
             if max_selectable_date < min_date: # Handle edge case: only 1 day of data
                 max_selectable_date = min_date
        else: # Start date can be up to max_date
             max_selectable_date = max_date


        try:
            parsed_date = datetime.datetime.strptime(current_val_str, '%d/%m/%Y').date()
            # Clamp parsed date within allowed range
            if min_date <= parsed_date <= max_selectable_date:
                current_date = parsed_date
            elif parsed_date < min_date:
                current_date = min_date
            else: # parsed_date > max_selectable_date
                current_date = max_selectable_date
        except ValueError:
            # Default to max allowed date if current text is invalid
            current_date = max_selectable_date

        dialog = QCalendarDialog(self, current_date=current_date, min_date=min_date, max_date=max_selectable_date)

        # Define a slot to receive the date and update the line edit
        def on_date_selected(qdate):
            target_line_edit.setText(qdate.toString("dd/MM/yyyy"))

        # Connect the dialog's signal to the slot
        dialog.dateSelected.connect(on_date_selected)

        dialog.exec_() # Show the dialog modally


    def _clear_cache_directory(self):
        # Keep the backend logic the same
        logger.info(f"Clearing cache directory: {self.calculate_dir}"); cleared = 0; errors = 0
        try:
            if self.calculate_dir.exists() and self.calculate_dir.is_dir():
                for item in self.calculate_dir.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                            cleared += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            cleared += 1 # Count directory as one item removed
                    except Exception as item_err:
                        logger.error(f"Failed to remove cache item '{item.name}': {item_err}")
                        errors += 1
                logger.info(f"Cache clear completed. Removed {cleared} items, encountered {errors} errors.")
            else:
                logger.debug("Cache directory does not exist or is not a directory.")
        except Exception as e:
            logger.error(f"Error occurred during cache clearing process: {e}", exc_info=True)


    def _load_optimization_log(self):
        if not self.selected_algorithm_for_optimize: return
        if self.selected_algorithm_for_optimize not in self.loaded_algorithms:
             logger.error(f"Cannot load optimization log: Algorithm '{self.selected_algorithm_for_optimize}' not loaded.")
             self.opt_log_text.setHtml('<font color="red">Lỗi: Thuật toán không được tải.</font>')
             return

        algo_data = self.loaded_algorithms[self.selected_algorithm_for_optimize]
        target_dir = self.optimize_dir / algo_data['path'].stem
        log_path = target_dir / "optimization_qt.log" # Use Qt log file name
        self.current_optimization_log_path = log_path

        self.opt_log_text.clear() # Clear existing content

        if log_path.exists() and log_path.is_file():
            logger.info(f"Loading optimization log: {log_path}")
            try:
                log_content = log_path.read_text(encoding='utf-8')
                lines = log_content.splitlines()
                html_lines = []
                for line in lines:
                    # Simple parsing based on log level marker
                    level = "INFO" # Default
                    color = "black"
                    font_weight = "normal"
                    text_decoration = "none"
                    log_text_part = line # Default to full line

                    try: # Robust parsing attempt
                        if len(line) > 27 and line[26] == ' ': # Check for ISO timestamp format
                           level_part = line[27:].split(']', 1)
                           if len(level_part) > 0:
                               parsed_level = level_part[0].strip('[ ')
                               if parsed_level in ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL", "BEST", "PROGRESS", "CUSTOM_STEP"]:
                                   level = parsed_level
                           # Take text after the level marker if possible
                           if len(level_part) > 1:
                               log_text_part = line[:27] + level_part[1] # Reconstruct with timestamp but without level tag

                    except Exception:
                        pass # Ignore parsing errors, use default level/color

                    # Determine formatting based on level
                    if level == "BEST": color = "darkgreen"; font_weight = "bold"
                    elif level == "PROGRESS": color = "blue"
                    elif level == "CUSTOM_STEP": color = "purple"
                    elif level == "WARNING": color = "orange"
                    elif level == "ERROR": color = "red"; font_weight = "bold"
                    elif level == "CRITICAL": color = "red"; font_weight = "bold"; text_decoration = "underline"
                    elif level == "DEBUG": color = "gray"

                    escaped_line = log_text_part.replace("<", "&lt;").replace(">", "&gt;")
                    html_lines.append(
                        f'<span style="font-family: Courier New, monospace; font-size: 9pt; color:{color}; font-weight:{font_weight}; text-decoration:{text_decoration};">'
                        f'{escaped_line}</span>'
                    )

                self.opt_log_text.setHtml("<br>".join(html_lines)) # Load all at once
                self.opt_log_text.moveCursor(QTextCursor.End) # Scroll to end
                logger.info(f"Successfully loaded and displayed log: {log_path.name}")

            except Exception as e:
                logger.error(f"Failed to read or parse optimization log file {log_path.name}: {e}")
                self.opt_log_text.setHtml(f'<font color="red">Lỗi đọc file log:<br>{e}</font>')
        else:
            logger.info(f"Optimization log file not found: {log_path}")
            self.opt_log_text.setHtml('<font color="gray">Chưa có nhật ký tối ưu hóa cho thuật toán này.</font>')

    def open_optimize_folder(self):
        target_dir = None
        if self.selected_algorithm_for_optimize and self.selected_algorithm_for_optimize in self.loaded_algorithms:
            algo_data = self.loaded_algorithms[self.selected_algorithm_for_optimize]; target_dir = self.optimize_dir / algo_data['path'].stem
        else:
            # If no algorithm selected for optimize, open the main optimize directory
            target_dir = self.optimize_dir

        if not target_dir:
             QMessageBox.critical(self, "Lỗi", "Không thể xác định thư mục tối ưu.")
             return

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Attempting to open folder: {target_dir}")
            # Use QDesktopServices for cross-platform opening
            url = QUrl.fromLocalFile(str(target_dir.resolve()))
            if not QDesktopServices.openUrl(url):
                 logger.error(f"QDesktopServices failed to open URL: {url.toString()}")
                 # Fallback for systems where QDesktopServices might fail (less common now)
                 try:
                     if sys.platform == "win32":
                         os.startfile(str(target_dir.resolve()))
                     elif sys.platform == "darwin":
                         subprocess.Popen(["open", str(target_dir.resolve())])
                     else: # Linux and other Unix-like
                         subprocess.Popen(["xdg-open", str(target_dir.resolve())])
                 except Exception as fallback_err:
                      logger.error(f"Fallback folder open failed: {fallback_err}", exc_info=True)
                      QMessageBox.warning(self, "Lỗi Mở Thư Mục", f"Không thể tự động mở thư mục:\n{target_dir}\n\nLỗi: {fallback_err}")

        except OSError as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo hoặc truy cập thư mục:\n{target_dir}\nLỗi: {e}"); logger.error(f"Failed create/access dir {target_dir}: {e}")
            return
        except Exception as e:
            logger.error(f"Unexpected error opening folder {target_dir}: {e}", exc_info=True);
            QMessageBox.critical(self, "Lỗi", f"Lỗi không mong muốn khi mở thư mục:\n{e}")

    # --- Override closeEvent ---
    def closeEvent(self, event):
        """Handle window close event."""
        logger.info("Close event triggered.")
        if self.optimizer_running:
            reply = QMessageBox.question(self, "Xác Nhận Thoát",
                                           "Quá trình tối ưu hóa đang chạy.\n"
                                           "Bạn có muốn dừng tối ưu và thoát không?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                logger.info("Stopping optimization due to close event.")
                self.optimizer_stop_event.set()
                # Give the thread a moment to acknowledge the stop event
                if self.optimizer_thread_obj and self.optimizer_thread_obj.isRunning():
                     # Don't wait indefinitely, worker should handle stop event gracefully
                     # self.optimizer_thread_obj.quit() # Ask thread to quit
                     self.optimizer_thread_obj.wait(1000) # Wait max 1 second
                event.accept() # Proceed with closing
                logger.info("Application closing after optimization stop request.")
            else:
                event.ignore() # Don't close
                logger.info("Close event ignored, optimization continues.")
        else:
            event.accept() # Close normally
            logger.info("Application closing normally.")


# --- Optimizer Worker Class (runs in QThread) ---
class OptimizerWorker(QObject):
    finished_internal = pyqtSignal() # Signal to ensure cleanup happens

    def __init__(self, queue_in, signals_out, stop_event, pause_event,
                 display_name, loaded_algorithms, results_data, calculate_dir,
                 start_date, end_date, time_limit_sec, custom_steps_config,
                 optimize_target_dir, base_dir, parent=None):
        super().__init__(parent)
        self.queue_in = queue_in
        self.signals = signals_out
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.display_name = display_name
        self.loaded_algorithms = loaded_algorithms # Receive copies
        self.results_data = results_data
        self.calculate_dir = calculate_dir
        self.start_date = start_date
        self.end_date = end_date
        self.time_limit_sec = time_limit_sec
        self.custom_steps_config = custom_steps_config
        self.target_dir = optimize_target_dir
        self.base_dir = base_dir
        # Need a logger instance accessible here too
        self.logger = logging.getLogger("OptimizerWorker")
        self.local_instance_cache = {} # Cache loaded instances during optimization


    def run(self):
        """The main optimization logic, moved from the App class."""
        self.logger.info(f"OptimizerWorker started for {self.display_name}")
        start_time = time.time()

        # --- Setup code (adapted from _optimization_worker) ---
        if self.display_name not in self.loaded_algorithms:
             self.signals.error.emit(f"Algorithm '{self.display_name}' not found in provided data.")
             self.signals.finished.emit("Lỗi: Thuật toán không tìm thấy.", False)
             self.finished_internal.emit()
             return

        algo_data = self.loaded_algorithms[self.display_name]
        original_path = algo_data['path']
        class_name = algo_data['class_name']
        original_params = algo_data['config'].get('parameters', {})
        try:
            source_code = original_path.read_text(encoding='utf-8')
        except Exception as e:
            self.signals.error.emit(f"Không thể đọc file nguồn: {original_path.name}: {e}")
            self.signals.finished.emit(f"Lỗi đọc file thuật toán: {e}", False)
            self.finished_internal.emit()
            return

        params_to_optimize = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}
        param_names_ordered = list(params_to_optimize.keys())

        if not param_names_ordered:
            self.signals.finished.emit("Không có tham số số học để tối ưu.", False)
            self.finished_internal.emit()
            return

        # --- Signal Helpers ---
        def sig_log(level, text, tag=None): self.signals.log.emit(level, text, tag or level.upper())
        def sig_status(text): self.signals.status.emit(text)
        def sig_progress(value): self.signals.progress.emit(value)
        def sig_best_update(params, score_tuple): self.signals.best_update.emit(params, list(score_tuple)) # Emit list
        def sig_finished(message, success=True): self.signals.finished.emit(message, success)
        def sig_error(text): self.signals.error.emit(text)

        # --- Performance Test Wrapper ---
        # Use self.run_performance_test directly
        # def run_perf_test_wrapper(params_test, start_dt, end_dt):
        #     return self.run_performance_test(source_code, class_name, params_test, start_dt, end_dt, self.target_dir)

        # --- Initial Run & Setup ---
        sig_log("INFO", f"Bắt đầu tối ưu {class_name} trong luồng worker."); sig_log("INFO", f"Tham số gốc: {params_to_optimize}"); sig_log("INFO", f"Khoảng test: {self.start_date:%d/%m/%Y} - {self.end_date:%d/%m/%Y}")
        sig_status("Kiểm tra hiệu suất tham số gốc..."); sig_progress(0.0)

        initial_perf = self.run_performance_test(source_code, class_name, original_params, self.start_date, self.end_date)

        if initial_perf is None:
            sig_log("ERROR", "Không thể hoàn thành kiểm tra hiệu suất ban đầu. Dừng tối ưu.")
            sig_finished("Lỗi khi kiểm tra hiệu suất ban đầu.", success=False);
            self.finished_internal.emit()
            return

        def get_primary_score(perf_dict):
            # Keep scoring consistent
            if not perf_dict: return (-1.0, -1.0, -1.0, -100.0) # Default bad score
            # Score = (Top3%, Top5%, Top1%, -AvgRepetition) - Higher is better
            return (
                perf_dict.get('acc_top_3_pct', 0.0),
                perf_dict.get('acc_top_5_pct', 0.0),
                perf_dict.get('acc_top_1_pct', 0.0),
                -perf_dict.get('avg_top10_repetition', 100.0) # Negate repetition, penalize high repetition
            )

        current_best_params = original_params.copy(); current_best_perf = initial_perf; current_best_score_tuple = get_primary_score(current_best_perf)
        sig_log("INFO", f"Hiệu suất gốc: Top3={initial_perf.get('acc_top_3_pct', 0.0):.2f}%, Top5={initial_perf.get('acc_top_5_pct', 0.0):.2f}%, Top1={initial_perf.get('acc_top_1_pct', 0.0):.2f}%, Lặp T10={initial_perf.get('avg_top10_repetition', 0.0):.2f}")
        sig_best_update(current_best_params, current_best_score_tuple)

        # Save initial best
        try:
            best_py_path = self.target_dir / "best_performing.py"
            mod_src = self.modify_algorithm_source_ast_worker(source_code, class_name, current_best_params) # Use worker's AST modify
            if mod_src:
                 best_py_path.write_text(mod_src, encoding='utf-8')
            else:
                 sig_log("ERROR", "Không thể tạo mã nguồn cho best_performing.py ban đầu.")

            best_params_path = self.target_dir / "best_params.json"
            save_data = {
                "params": current_best_params,
                "performance": current_best_perf,
                "score_tuple": list(current_best_score_tuple) # Store as list in JSON
            }
            best_params_path.write_text(json.dumps(save_data, indent=4, ensure_ascii=False), encoding='utf-8')
            sig_log("DEBUG", f"Đã lưu kết quả gốc vào thư mục: {self.target_dir.name}")
        except Exception as save_err:
            sig_log("ERROR", f"Lỗi lưu kết quả gốc: {save_err}")


        # --- Optimization Loop (Keep the core logic) ---
        MAX_ITERATIONS_PER_PARAM_AUTO = 10; STALL_THRESHOLD = 2; MAX_FULL_CYCLES = 5; steps_done = 0
        for cycle in range(MAX_FULL_CYCLES):
            if self.stop_event.is_set(): break # Check at start of cycle
            sig_log("INFO", f"--- Chu kỳ Tối ưu {cycle + 1}/{MAX_FULL_CYCLES} ---", tag="PROGRESS"); params_changed_in_cycle = False

            for param_idx, param_name in enumerate(param_names_ordered):

                # --- Check Pause/Stop ---
                if self.stop_event.is_set(): break
                while self.pause_event.is_set():
                    if self.stop_event.is_set(): break # Check stop event during pause
                    sig_status("Đã tạm dừng...")
                    time.sleep(0.5) # Sleep briefly while paused
                if self.stop_event.is_set(): break
                sig_status(f"Đang tối ưu chu kỳ {cycle+1}, tham số '{param_name}'...") # Update status more actively

                # --- Decide Step Mode ---
                param_opt_config = self.custom_steps_config.get(param_name, {'mode': 'Auto', 'steps': []})
                mode = param_opt_config['mode']; custom_steps = param_opt_config['steps']
                original_value_for_turn = current_best_params[param_name]; is_float = isinstance(original_value_for_turn, float)

                # --- Custom Step Logic ---
                if mode == 'Custom' and custom_steps:
                    sig_log("INFO", f"Tối ưu {param_name} (Chế độ: Custom, Bước: {custom_steps})", tag="CUSTOM_STEP"); best_value_this_param = current_best_params[param_name]
                    # Combine positive and negative steps for efficiency
                    steps_to_try = sorted(list(set([step_val for step_val in custom_steps if step_val != 0] + [-step_val for step_val in custom_steps if step_val != 0])))

                    for step_val in steps_to_try:
                        if self.stop_event.is_set() or time.time() - start_time > self.time_limit_sec: break
                        test_params = current_best_params.copy(); new_value = original_value_for_turn + step_val # Test relative to original value of this turn
                        # Apply type casting
                        test_params[param_name] = float(f"{new_value:.6g}") if is_float else int(new_value)

                        # Avoid re-testing the exact same parameter set if possible (simple check)
                        # This check is basic; more complex state tracking might be needed for true cycle prevention
                        if test_params == current_best_params: continue

                        sig_status(f"Thử custom: {param_name}={test_params[param_name]:.4f} (bước {step_val})...");
                        perf_result = self.run_performance_test(source_code, class_name, test_params, self.start_date, self.end_date)
                        steps_done += 1;
                        sig_progress(min(0.95, (time.time() - start_time) / self.time_limit_sec))

                        if perf_result:
                            new_score = get_primary_score(perf_result); sig_log("DEBUG", f"  Custom Test: {param_name}={test_params[param_name]:.4f} -> Score={new_score}", tag="CUSTOM_STEP")
                            if new_score > current_best_score_tuple:
                                sig_log("BEST", f"  -> Cải thiện (custom)! {param_name}={test_params[param_name]:.4f}. Score mới: {new_score}", tag="BEST")
                                current_best_params = test_params.copy(); current_best_perf = perf_result; current_best_score_tuple = new_score; best_value_this_param = new_value # Update best for this param turn
                                sig_best_update(current_best_params, current_best_score_tuple); params_changed_in_cycle = True
                                # Save intermediate best
                                try:
                                    best_py_path = self.target_dir / "best_performing.py"; mod_src = self.modify_algorithm_source_ast_worker(source_code, class_name, current_best_params);
                                    if mod_src: best_py_path.write_text(mod_src, encoding='utf-8')
                                    best_params_path = self.target_dir / "best_params.json"; save_data = {"params": current_best_params, "performance": current_best_perf, "score_tuple": list(current_best_score_tuple)}; best_params_path.write_text(json.dumps(save_data, indent=4, ensure_ascii=False), encoding='utf-8')
                                except Exception as save_err: sig_log("ERROR", f"Lỗi lưu best (custom): {save_err}")
                            # else: No improvement from this custom step
                        else: sig_log("WARNING", f"  -> Lỗi kiểm tra hiệu suất custom {param_name}={test_params[param_name]:.4f}.", tag="WARNING")

                    # After trying all custom steps, current_best_params holds the best found for this param turn

                # --- Auto Step Logic (Hill Climbing) ---
                else: # mode == 'Auto' or (mode == 'Custom' and not custom_steps)
                    # Determine initial step size (same logic as before)
                    current_val_auto = current_best_params[param_name] # Start from current best
                    step = abs(current_val_auto) * 0.05 if abs(current_val_auto) > 1 else (0.05 if abs(current_val_auto) > 0.01 else 0.001)
                    if step == 0: step = 0.001 # Ensure step is never zero for floats
                    if not is_float: step = max(1, int(round(step))) # Ensure integer step is at least 1

                    sig_log("INFO", f"Tối ưu {param_name} (Chế độ: Auto, Giá trị hiện tại={current_val_auto:.4f}, Bước={step:.4g})")

                    # --- Hill Climbing (combined search direction) ---
                    best_val_this_param = current_val_auto # Track best value found *for this parameter*
                    param_improved = True # Assume improvement possible initially

                    while param_improved:
                        param_improved = False # Reset for this iteration
                        if self.stop_event.is_set() or time.time() - start_time > self.time_limit_sec: break

                        directions_to_test = [step, -step] # Test increasing and decreasing

                        for direction_step in directions_to_test:
                             if self.stop_event.is_set() or time.time() - start_time > self.time_limit_sec: break

                             test_params = current_best_params.copy()
                             new_val = best_val_this_param + direction_step # Test relative to best found for this param so far
                             test_params[param_name] = float(f"{new_val:.6g}") if is_float else int(new_val)

                             # Avoid redundant checks if precision makes values equal
                             if test_params == current_best_params: continue

                             dir_str = "+" if direction_step > 0 else "-"
                             sig_status(f"Thử auto {dir_str}: {param_name}={test_params[param_name]:.4f}...")
                             perf_result = self.run_performance_test(source_code, class_name, test_params, self.start_date, self.end_date)
                             steps_done += 1
                             sig_progress(min(0.95, (time.time() - start_time) / self.time_limit_sec))

                             if perf_result:
                                 new_score = get_primary_score(perf_result)
                                 sig_log("DEBUG", f"  Auto Test ({dir_str}): {param_name}={test_params[param_name]:.4f} -> Score={new_score}")
                                 if new_score > current_best_score_tuple:
                                     sig_log("BEST", f"  -> Cải thiện (auto {dir_str})! {param_name}={test_params[param_name]:.4f}. Score mới: {new_score}", tag="BEST")
                                     # Update global best and best for this parameter
                                     current_best_params = test_params.copy(); current_best_perf = perf_result; current_best_score_tuple = new_score; best_val_this_param = new_val
                                     sig_best_update(current_best_params, current_best_score_tuple)
                                     params_changed_in_cycle = True
                                     param_improved = True # Found improvement, continue climbing for this param
                                     # Save intermediate best
                                     try:
                                         best_py_path = self.target_dir / "best_performing.py"; mod_src = self.modify_algorithm_source_ast_worker(source_code, class_name, current_best_params);
                                         if mod_src: best_py_path.write_text(mod_src, encoding='utf-8')
                                         best_params_path = self.target_dir / "best_params.json"; save_data = {"params": current_best_params, "performance": current_best_perf, "score_tuple": list(current_best_score_tuple)}; best_params_path.write_text(json.dumps(save_data, indent=4, ensure_ascii=False), encoding='utf-8')
                                     except Exception as save_err: sig_log("ERROR", f"Lỗi lưu best (auto {dir_str}): {save_err}")
                                     # Since we found improvement in this direction, break inner loop and climb again from new best
                                     break # Go back to start of while loop with new best_val_this_param
                                 # else: No improvement in this direction
                             else:
                                 sig_log("WARNING", f"  -> Lỗi kiểm tra hiệu suất auto ({dir_str}) {param_name}={test_params[param_name]:.4f}.", tag="WARNING")
                                 # Treat error as non-improvement for this step

                        # End of directions_to_test loop
                    # End of while param_improved loop (finished climbing for this param)

                # --- End of Auto/Custom Logic for one parameter ---
                if self.stop_event.is_set() or time.time() - start_time > self.time_limit_sec: break # Check after each parameter finishes

            # --- End of Parameter Loop (one full cycle) ---
            if time.time() - start_time > self.time_limit_sec or self.stop_event.is_set(): break # Check after cycle completes
            if not params_changed_in_cycle:
                sig_log("INFO", f"Không có cải thiện nào trong chu kỳ {cycle + 1}. Kết thúc sớm.", tag="PROGRESS")
                break # End cycles early if no improvement found

        # --- Final Reporting ---
        sig_progress(1.0); final_message = ""
        stopped_by_user = self.stop_event.is_set()
        time_limit_reached = time.time() - start_time > self.time_limit_sec

        if stopped_by_user:
            final_message = "Tối ưu hóa bị dừng bởi người dùng. Kết quả tốt nhất tìm được đã được lưu."
        elif time_limit_reached:
            final_message = f"Đã hết thời gian tối ưu ({self.time_limit_sec/60:.0f} phút). Kết quả tốt nhất tìm được đã được lưu."
        else:
            final_message = "Tối ưu hóa hoàn tất. Kết quả tốt nhất đã được lưu."

        sig_log("BEST", "="*10 + " TỐI ƯU HOÀN TẤT " + "="*10, tag="BEST")
        sig_log("BEST", f"Tham số tốt nhất cuối cùng: {current_best_params}", tag="BEST")
        score_desc = "(Top3%, Top5%, Top1%, -AvgRepT10)"; sig_log("BEST", f"Điểm tốt nhất {score_desc}: {current_best_score_tuple}", tag="BEST")
        perf_details = (f"Hiệu suất tương ứng: Top3={current_best_perf.get('acc_top_3_pct', 0.0):.2f}%, "
                        f"Top5={current_best_perf.get('acc_top_5_pct', 0.0):.2f}%, "
                        f"Top1={current_best_perf.get('acc_top_1_pct', 0.0):.2f}%, "
                        f"Lặp T10={current_best_perf.get('avg_top10_repetition', 0.0):.2f}")
        sig_log("BEST", perf_details, tag="BEST")

        # Save final result to success folder
        try:
            final_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            success_dir = self.target_dir / "success"; success_dir.mkdir(exist_ok=True) # Ensure exists
            # Create a meaningful filename
            perf_str = f"top3_{current_best_perf.get('acc_top_3_pct', 0.0):.1f}".replace('.', '_') # Make filename safe
            base_filename = f"optimized_{algo_data['path'].stem}_{perf_str}_{final_timestamp}"
            success_filename_py = f"{base_filename}.py"
            success_filename_json = f"{base_filename}.json"

            final_py_path = success_dir / success_filename_py
            final_mod_src = self.modify_algorithm_source_ast_worker(source_code, class_name, current_best_params)
            if final_mod_src:
                 final_py_path.write_text(final_mod_src, encoding='utf-8')
            else:
                 sig_log("ERROR", f"Không thể tạo mã nguồn python cuối cùng cho file {success_filename_py}")


            final_json_path = success_dir / success_filename_json
            final_save_data = {
                "params": current_best_params,
                "performance": current_best_perf,
                "score_tuple": list(current_best_score_tuple),
                "optimized_range": f"{self.start_date:%Y-%m-%d}_to_{self.end_date:%Y-%m-%d}",
                "status": final_message
            }
            final_json_path.write_text(json.dumps(final_save_data, indent=4, ensure_ascii=False), encoding='utf-8')
            sig_log("BEST", f"Đã lưu kết quả tối ưu cuối cùng vào thư mục: {success_dir.relative_to(self.base_dir)}", tag="BEST")
            final_message += f"\nĐã lưu kết quả vào: {success_dir.name}/{base_filename}.[py|json]"

        except Exception as final_save_err:
            sig_log("ERROR", f"Lỗi nghiêm trọng khi lưu kết quả tối ưu cuối cùng: {final_save_err}")
            final_message += "\nCẢNH BÁO: Không thể lưu file kết quả cuối cùng!"

        # Signal completion
        sig_finished(final_message, success=not (stopped_by_user or time_limit_reached)) # Success only if completed naturally
        self.finished_internal.emit() # Signal for thread cleanup
        self.logger.info(f"OptimizerWorker finished for {self.display_name}")


    def modify_algorithm_source_ast_worker(self, source_code, target_class_name, new_params):
        """AST modification logic, callable from the worker."""
        # This is the same AST modification logic as in the main app
        # It's duplicated here to be self-contained within the worker
        # Could be refactored into a shared utility function if preferred.
        self.logger.debug(f"[Worker AST] mod: Class '{target_class_name}' (Params & Imports)")
        try: tree = ast.parse(source_code)
        except SyntaxError as e: self.logger.error(f"[Worker AST] Syntax error parsing: {e}", exc_info=True); return None
        class _SourceModifier(ast.NodeTransformer):
            def __init__(self, class_to_modify, params_to_update):
                self.target_class = class_to_modify; self.params_to_update = params_to_update; self.in_target_init = False; self.params_modified = False; self.imports_modified = False; self.current_class_name = None; super().__init__()
            def visit_ImportFrom(self, node):
                if node.level > 0 and node.module == 'base':
                     # logger.debug(f"[Worker AST] Fixing relative import: '.{node.module}' -> 'algorithms.{node.module}'")
                     node.module = f'algorithms.{node.module}'; node.level = 0; self.imports_modified = True
                elif node.level > 0 and node.module is None:
                     # logger.warning(f"[Worker AST] Cannot auto-fix 'from . import ...' line: {node.lineno}")
                     pass
                return self.generic_visit(node)
            def visit_ClassDef(self, node):
                original_class = self.current_class_name; self.current_class_name = node.name
                if node.name == self.target_class:
                     # logger.debug(f"[Worker AST] Found target class: {node.name}")
                     node.body = [self.visit(child) for child in node.body]
                else: self.generic_visit(node)
                self.current_class_name = original_class; return node
            def visit_FunctionDef(self, node):
                if node.name == '__init__' and self.current_class_name == self.target_class:
                     # logger.debug(f"[Worker AST] Entering __init__ of {self.target_class}")
                     self.in_target_init = True; node.body = [self.visit(child) for child in node.body]; self.in_target_init = False; # logger.debug(f"[Worker AST] Exiting __init__")
                else: self.generic_visit(node)
                return node
            def visit_Assign(self, node):
                if self.in_target_init and len(node.targets) == 1:
                    target = node.targets[0]
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self' and target.attr == 'config':
                        # logger.debug("[Worker AST] Found 'self.config' assign.")
                        node.value = self.visit(node.value); return node
                return self.generic_visit(node)
            def visit_Dict(self, node):
                 if not self.in_target_init: return self.generic_visit(node)
                 param_key_index = -1; param_value_node = None
                 try:
                     for i, key_node in enumerate(node.keys):
                         if key_node is not None and isinstance(key_node, ast.Constant) and isinstance(key_node.value, str) and key_node.value == 'parameters':
                             param_key_index = i; param_value_node = node.values[i]; # logger.debug("[Worker AST] Found 'parameters' key.")
                             break
                 except AttributeError: return self.generic_visit(node)
                 if param_key_index != -1 and isinstance(param_value_node, ast.Dict):
                     # logger.debug("[Worker AST] Processing 'parameters' sub-dict.")
                     new_keys = []; new_values = []; modified_in_subdict = False
                     original_param_nodes = {}
                     if param_value_node.keys is not None:
                          original_param_nodes = {k.value: (k,v) for k, v in zip(param_value_node.keys, param_value_node.values) if isinstance(k, ast.Constant)}

                     # Update values for parameters present in new_params
                     for param_name, new_value in self.params_to_update.items():
                         if param_name in original_param_nodes:
                             p_key_node, p_val_node = original_param_nodes[param_name]; new_val_node = None
                             # Create new AST Constant node for the new value
                             if isinstance(new_value, (int, float)):
                                 # Handle negative numbers correctly using UnaryOp
                                 if new_value < 0:
                                     new_val_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=abs(new_value)))
                                 else:
                                     new_val_node = ast.Constant(value=new_value)
                             elif isinstance(new_value, str):
                                 new_val_node = ast.Constant(value=new_value)
                             elif isinstance(new_value, bool):
                                 new_val_node = ast.Constant(value=new_value) # True/False are constants in Python 3
                             elif new_value is None:
                                 new_val_node = ast.Constant(value=None) # None is a constant

                             if new_val_node is not None:
                                 new_keys.append(p_key_node) # Keep original key node
                                 new_values.append(new_val_node) # Use new value node
                                 # self.logger.debug(f"[Worker AST] Updated '{param_name}' node to {new_value}") # Optional debug log
                                 modified_in_subdict = True
                             else:
                                 # --- FIX START ---
                                 # Keep original if type is not supported for modification
                                 self.logger.warning(f"[Worker AST] Unsupported type for parameter '{param_name}': {type(new_value)}. Keeping original value.")
                                 new_keys.append(p_key_node)  # Keep original key node
                                 new_values.append(p_val_node) # Keep original value node
                                 # --- FIX END ---
                         else:
                             # Parameter from update list not found in original 'parameters' dict
                             self.logger.warning(f"[Worker AST] Parameter '{param_name}' from update list not found in original 'parameters' dict. Skipping.")
                             # Optionally, decide if you want to add it or just skip

                     # Add back parameters that were not in the update list
                     updated_keys = set(self.params_to_update.keys())
                     for name, (k_node, v_node) in original_param_nodes.items():
                          if name not in updated_keys:
                              new_keys.append(k_node)
                              new_values.append(v_node)

                     # Replace the keys and values of the 'parameters' dictionary node
                     param_value_node.keys = new_keys
                     param_value_node.values = new_values
                     if modified_in_subdict:
                         self.params_modified = True # Mark that we changed parameters

                 # Continue visiting other parts of the dictionary (if any)
                 return self.generic_visit(node)

        modifier = _SourceModifier(target_class_name, new_params); modified_tree = modifier.visit(tree)
        if not modifier.params_modified and not modifier.imports_modified:
            self.logger.warning("[Worker AST] mod finished, no params or imports updated.")
        # Unparse
        try:
            if hasattr(ast, 'unparse'): modified_code = ast.unparse(modified_tree); # self.logger.debug("[Worker AST] Unparsed using ast.unparse")
            elif HAS_ASTOR: modified_code = astor.to_source(modified_tree); # self.logger.debug("[Worker AST] Unparsed using astor")
            else: self.logger.critical("[Worker AST] Unparsing failed. Need Py 3.9+ or 'astor'."); return None
        except Exception as unparse_err: self.logger.error(f"[Worker AST] Error unparsing AST: {unparse_err}", exc_info=True); return None
        return modified_code


    def run_performance_test(self, original_source_code, class_name, params_to_test, test_start_date, test_end_date):
        """Performs a performance test for a given parameter set."""
        temp_algo_instance = None; temp_module_name = None; temp_filepath = None
        # Use a hash of parameters for potentially better caching/uniqueness if needed
        # param_hash = hashlib.md5(json.dumps(params_to_test, sort_keys=True).encode()).hexdigest()[:8]
        instance_key = json.dumps(params_to_test, sort_keys=True) # Key for instance cache

        if instance_key in self.local_instance_cache:
            temp_algo_instance = self.local_instance_cache[instance_key]
            self.logger.debug(f"Reusing cached instance for params: {params_to_test}")
        else:
            self.logger.debug(f"Creating new instance for params: {params_to_test}")
            try:
                modified_source = self.modify_algorithm_source_ast_worker(original_source_code, class_name, params_to_test)
                if not modified_source: raise RuntimeError("AST modification failed during performance test setup.")

                # Create a unique temporary filename/modulename
                timestamp = int(time.time() * 10000) + random.randint(0, 9999)
                temp_filename = f"temp_perf_{class_name}_{timestamp}.py"
                temp_filepath = self.target_dir / temp_filename
                temp_filepath.write_text(modified_source, encoding='utf-8')

                # Ensure __init__.py exists in target_dir and optimize_dir for relative imports
                opt_init = self.base_dir / "optimize" / "__init__.py"; target_init = self.target_dir / "__init__.py"
                if not opt_init.exists(): opt_init.touch()
                if not target_init.exists(): target_init.touch()

                # Create a unique module name within the optimization run's context
                # Example: optimize.algo_name_stem.temp_perf_ClassName_timestamp
                temp_module_name = f"optimize.{self.target_dir.name}.{temp_filename[:-3]}"

                # Unload existing module if it somehow exists (unlikely with unique names)
                if temp_module_name in sys.modules:
                    self.logger.warning(f"Removing potentially conflicting module before import: '{temp_module_name}'")
                    del sys.modules[temp_module_name]

                # Import the temporary module
                spec = util.spec_from_file_location(temp_module_name, temp_filepath)
                if not spec or not spec.loader:
                    raise ImportError(f"Could not create module spec for {temp_module_name} from {temp_filepath}")

                temp_module = util.module_from_spec(spec)
                sys.modules[temp_module_name] = temp_module # Register module before execution
                spec.loader.exec_module(temp_module) # Execute module code

                # Find the algorithm class within the loaded module
                temp_class = getattr(temp_module, class_name, None)
                if not temp_class or not issubclass(temp_class, BaseAlgorithm):
                    # Fallback: Find any valid BaseAlgorithm subclass if name doesn't match
                    fallback_class = None
                    for name, obj in inspect.getmembers(temp_module):
                        if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == temp_module_name:
                            fallback_class = obj
                            self.logger.warning(f"Class '{class_name}' not found by name in temp module, using found class '{name}'.")
                            break
                    if not fallback_class:
                         raise TypeError(f"No valid BaseAlgorithm subclass found in temporary module {temp_module_name}.")
                    temp_class = fallback_class

                # Instantiate the algorithm
                # Important: Pass DEEP COPIES of data if the algorithm modifies it internally
                temp_algo_instance = temp_class(data_results_list=copy.deepcopy(self.results_data), cache_dir=self.calculate_dir)
                self.local_instance_cache[instance_key] = temp_algo_instance # Cache the instance

            except Exception as e:
                self.signals.error.emit(f"Lỗi tạo instance thuật toán tạm thời cho params {params_to_test}: {e}")
                self.logger.error(f"Failed to create/load temporary algorithm instance ({temp_filepath}): {e}", exc_info=True)
                # Cleanup partially created stuff
                if temp_module_name and temp_module_name in sys.modules: del sys.modules[temp_module_name]
                if temp_filepath and temp_filepath.exists():
                     try: temp_filepath.unlink()
                     except OSError as unlink_e: self.logger.warning(f"Could not delete temp file {temp_filepath.name} after error: {unlink_e}")
                return None # Indicate failure

            finally:
                # --- Cleanup: Module references and temporary files ---
                # We specifically DO NOT clean up the module or file here if instance creation succeeded
                # because the instance holds references. Cleanup happens *after* calculation.
                # Clean up ONLY if instance creation failed in the try block.
                 pass


        # If instance obtained (either new or cached)
        if temp_algo_instance:
             try:
                  # Run the actual performance calculation
                  perf_stats = self.calculate_performance_for_instance(temp_algo_instance, test_start_date, test_end_date)
                  return perf_stats
             except Exception as calc_e:
                  self.signals.error.emit(f"Lỗi khi tính toán hiệu suất cho params {params_to_test}: {calc_e}")
                  self.logger.error(f"Error during performance calculation for {temp_algo_instance.__class__.__name__}: {calc_e}", exc_info=True)
                  return None # Indicate failure
             # finally:
                 # --- Instance cleanup ---
                 # If we didn't cache, we would clean up here. Since we cache, cleanup is harder.
                 # We might need a strategy to clear the cache periodically or when optimization finishes.
                 # For now, instances persist in the cache for the duration of the worker's run.
                 # If temp_filepath exists for the *current* instance creation (not cache hit), clean it up.
                 # if instance_key not in self.local_instance_cache: # This logic is flawed with current cache impl.
                 # if temp_module_name and temp_module_name in sys.modules:
                 #     try: del sys.modules[temp_module_name]
                 #     except Exception as del_err: self.logger.warning(f"Could not remove module '{temp_module_name}' after calculation: {del_err}")
                 # if temp_filepath and temp_filepath.exists():
                 #     try: temp_filepath.unlink()
                 #     except OSError as e: self.logger.warning(f"Could not delete temp file {temp_filepath.name} after calculation: {e}")

        else:
             # This should only happen if instance creation failed above and returned None
             return None


    def calculate_performance_for_instance(self, algo_instance, start_date, end_date):
        """Calculates hit rate statistics for a given algorithm instance and date range."""
        # --- Keep the core calculation logic the same ---
        stats = {'total_days_tested': 0, 'hits_top_1': 0, 'hits_top_3': 0, 'hits_top_5': 0, 'hits_top_10': 0, 'errors': 0}
        all_top_10_numbers = []

        if not self.results_data or not isinstance(self.results_data[0]['date'], datetime.date):
            self.logger.error("Performance calculation cannot proceed: Invalid or missing results data.")
            return None # Cannot calculate without data

        # Precompute map and history for efficiency
        # Ensure deep copies are used if algo_instance modifies history internally
        results_map = {r['date']: r['result'] for r in self.results_data}
        # Create history slices efficiently ONCE
        history_cache = {self.results_data[i]['date']: self.results_data[:i] for i in range(len(self.results_data))}

        current_date = start_date
        while current_date <= end_date:
            # Check stop/pause frequently within the loop
            if self.stop_event.is_set():
                 self.logger.info("Performance calculation stopped by user request.")
                 return None # Indicate calculation was aborted
            while self.pause_event.is_set():
                 if self.stop_event.is_set():
                     self.logger.info("Performance calculation stopped by user request during pause.")
                     return None
                 time.sleep(0.1) # Small sleep while paused


            predict_date = current_date
            check_date = predict_date + datetime.timedelta(days=1)

            actual_result_dict = results_map.get(check_date)
            # Need results for the *next* day to check predictions made for 'predict_date'
            if actual_result_dict is None:
                # self.logger.debug(f"Skipping perf check for {predict_date:%Y-%m-%d}: No result data for check date {check_date:%Y-%m-%d}")
                current_date += datetime.timedelta(days=1)
                continue # Move to the next day to predict

            # Get historical data *up to* the prediction date (exclusive)
            hist_data = history_cache.get(predict_date) # History ends *before* predict_date
            if hist_data is None: # Should not happen with precomputed cache, but check
                self.logger.warning(f"Performance calculation skipped for {predict_date:%Y-%m-%d}: History data unexpectedly missing.")
                current_date += datetime.timedelta(days=1)
                continue

            # Extract actual winning numbers for the check date
            try:
                # Use the instance's method to handle different data structures
                actual_numbers_set = algo_instance.extract_numbers_from_dict(actual_result_dict)
                if not actual_numbers_set: # If extraction returns empty set or None
                     # self.logger.warning(f"Could not extract actual numbers for {check_date:%Y-%m-%d}. Skipping day.")
                     stats['errors'] += 1 # Count as an error day for stats
                     current_date += datetime.timedelta(days=1)
                     continue
            except Exception as extract_err:
                self.logger.error(f"Error extracting actual numbers for {check_date:%Y-%m-%d}: {extract_err}")
                stats['errors'] += 1
                current_date += datetime.timedelta(days=1)
                continue

            # Make prediction using the algorithm instance
            try:
                # Pass a deep copy of history if the algorithm might modify it
                predicted_scores = algo_instance.predict(predict_date, copy.deepcopy(hist_data))

                if not isinstance(predicted_scores, dict) or not predicted_scores:
                    # self.logger.warning(f"Algorithm returned no valid predictions for {predict_date:%Y-%m-%d}. Skipping day.")
                    stats['errors'] += 1 # Count as error if no predictions
                    current_date += datetime.timedelta(days=1)
                    continue

                # Process predictions: Sort by score, take top N
                # Ensure keys are strings and can be converted to int for comparison
                valid_preds = []
                for n, s in predicted_scores.items():
                    num_str = str(n) # Ensure string
                    if num_str.isdigit() and isinstance(s, (int, float)):
                         valid_preds.append((int(num_str), float(s))) # Store as (int, float)
                    # else: ignore invalid prediction format

                if not valid_preds:
                     # self.logger.warning(f"No valid numeric predictions found for {predict_date:%Y-%m-%d} after filtering.")
                     stats['errors'] += 1
                     current_date += datetime.timedelta(days=1)
                     continue

                sorted_preds = sorted(valid_preds, key=lambda x: x[1], reverse=True)

                # Get sets of top predicted numbers (as integers)
                pred_top_1 = {sorted_preds[0][0]} if sorted_preds else set()
                pred_top_3 = {p[0] for p in sorted_preds[:3]}
                pred_top_5 = {p[0] for p in sorted_preds[:5]}
                pred_top_10 = {p[0] for p in sorted_preds[:10]}

                # Check for hits
                if pred_top_1.intersection(actual_numbers_set): stats['hits_top_1'] += 1
                if pred_top_3.intersection(actual_numbers_set): stats['hits_top_3'] += 1
                if pred_top_5.intersection(actual_numbers_set): stats['hits_top_5'] += 1
                if pred_top_10.intersection(actual_numbers_set): stats['hits_top_10'] += 1

                # Collect top 10 for repetition analysis
                all_top_10_numbers.extend(list(pred_top_10))
                stats['total_days_tested'] += 1 # Increment tested days only if prediction was successful

            except NotImplementedError:
                 self.logger.critical(f"Algorithm '{algo_instance.__class__.__name__}' does not implement 'predict'. Stopping calculation.", exc_info=True)
                 self.signals.error.emit(f"Lỗi nghiêm trọng: Thuật toán '{algo_instance.__class__.__name__}' thiếu hàm predict.")
                 return None # Fatal error for this instance
            except Exception as predict_err:
                self.logger.error(f"Error during prediction or processing for {predict_date:%Y-%m-%d}: {predict_err}", exc_info=False) # Log less verbosely in loop
                stats['errors'] += 1 # Count as an error day

            # Move to the next day
            current_date += datetime.timedelta(days=1)
            # End of while loop

        # --- Final calculation of percentages and repetition ---
        total_tested = stats['total_days_tested']
        if total_tested > 0:
            stats['acc_top_1_pct'] = (stats['hits_top_1'] / total_tested) * 100.0
            stats['acc_top_3_pct'] = (stats['hits_top_3'] / total_tested) * 100.0
            stats['acc_top_5_pct'] = (stats['hits_top_5'] / total_tested) * 100.0
            stats['acc_top_10_pct'] = (stats['hits_top_10'] / total_tested) * 100.0

            # Repetition analysis
            if all_top_10_numbers:
                top10_counts = Counter(all_top_10_numbers)
                # Avg repetition: total numbers predicted / unique numbers predicted
                stats['avg_top10_repetition'] = len(all_top_10_numbers) / len(top10_counts) if top10_counts else 0.0
                stats['max_top10_repetition_count'] = max(top10_counts.values()) if top10_counts else 0
                stats['top10_repetition_details'] = dict(top10_counts.most_common(5)) # Top 5 repeated numbers and their counts
            else: # Handle case where no top 10 numbers were collected (e.g., errors every day)
                stats['avg_top10_repetition'] = 0.0
                stats['max_top10_repetition_count'] = 0
                stats['top10_repetition_details'] = {}

            self.logger.debug(f"Performance calculation finished for {algo_instance.__class__.__name__}. Days tested: {total_tested}, Errors: {stats['errors']}")
            return stats
        else:
            # No days were successfully tested (e.g., errors every day or date range too small)
            self.logger.warning(f"No days successfully tested for {algo_instance.__class__.__name__} in the given range. Errors: {stats['errors']}")
            # Return stats dict with 0 percentages
            stats['acc_top_1_pct'] = 0.0; stats['acc_top_3_pct'] = 0.0; stats['acc_top_5_pct'] = 0.0; stats['acc_top_10_pct'] = 0.0
            stats['avg_top10_repetition'] = 0.0; stats['max_top10_repetition_count'] = 0; stats['top10_repetition_details'] = {}
            return stats # Return the structure even if empty


# --- Main Execution ---
def main():
    # Ensure QApplication is created first
    # Use existing instance if available (e.g., in interactive environments)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Apply a basic stylesheet (similar to ttk themes)
    # More complex QSS can be loaded from a file
    qss = """
        QMainWindow, QDialog {
            background-color: #f0f0f0; /* Light gray background */
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid silver;
            border-radius: 5px;
            margin-top: 10px; /* Space for title */
            padding: 10px;
             background-color: #f8f8f8; /* Slightly different group background */
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left; /* Position at the top left */
            padding: 0 3px;
            background-color: #f0f0f0; /* Match window background */
            left: 10px; /* Indent title slightly */
        }
        QPushButton {
            padding: 5px 10px;
            border: 1px solid #adadad;
            border-radius: 4px;
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #f6f7fa, stop: 1 #dadbde);
            min-width: 60px; /* Minimum width */
        }
        QPushButton:hover {
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #e6e7ea, stop: 1 #c6c7ca);
        }
        QPushButton:pressed {
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #dadbde, stop: 1 #f6f7fa);
        }
        QPushButton:disabled {
            background-color: #e0e0e0;
            color: #a0a0a0;
            border-color: #c0c0c0;
        }
        /* Accent Button Style */
        QPushButton#AccentButton {
            font-weight: bold;
            color: white;
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #007bff, stop: 1 #0056b3);
            border-color: #0056b3;
        }
        QPushButton#AccentButton:hover {
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #0069d9, stop: 1 #004fa3);
        }
         QPushButton#AccentButton:pressed {
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #0056b3, stop: 1 #007bff);
        }
        /* Danger Button Style */
        QPushButton#DangerButton {
            color: white;
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #dc3545, stop: 1 #c82333);
            border-color: #c82333;
        }
         QPushButton#DangerButton:hover {
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #d32535, stop: 1 #b02a37);
        }
        QPushButton#DangerButton:pressed {
             background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #c82333, stop: 1 #dc3545);
        }
        /* Warning Button Style */
        QPushButton#WarningButton {
            color: black; /* Dark text for yellow */
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #ffc107, stop: 1 #e0a800);
            border-color: #e0a800;
        }
        QPushButton#WarningButton:hover {
            background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #f8b907, stop: 1 #cfa000);
        }
         QPushButton#WarningButton:pressed {
             background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                             stop: 0 #e0a800, stop: 1 #ffc107);
        }

        QProgressBar {
            border: 1px solid grey;
            border-radius: 5px;
            text-align: center; /* Show percentage if text visible */
             background-color: #E0E0E0; /* Trough color */
        }
        QProgressBar::chunk {
            background-color: #28A745; /* Bar color (green) */
            width: 10px; /* Width of the chunks */
             margin: 1px;
             border-radius: 3px;
        }
        QTabWidget::pane { /* The tab content area */
            border-top: 1px solid #C2C7CB;
             background-color: #f8f8f8;
        }
        QTabBar::tab { /* The tab titles */
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                        stop: 0 #E1E1E1, stop: 0.4 #DDDDDD,
                                        stop: 0.5 #D8D8D8, stop: 1.0 #D3D3D3);
            border: 1px solid #C4C4C3;
            border-bottom-color: #C2C7CB; /* Match pane border */
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            min-width: 8ex;
            padding: 4px 10px;
        }
        QTabBar::tab:selected, QTabBar::tab:hover {
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                        stop: 0 #f8f8f8, stop: 0.4 #f3f3f3, /* Lighter when selected */
                                        stop: 0.5 #ededed, stop: 1.0 #f8f8f8);
        }
        QTabBar::tab:selected {
            border-color: #9B9B9B;
            border-bottom-color: #f8f8f8; /* Same as pane background */
        }
        QTabBar::tab:!selected {
            margin-top: 2px; /* Make non-selected tabs look slightly recessed */
        }
        QLineEdit { padding: 3px; border: 1px solid #ccc; border-radius: 3px; }
        QTextEdit { background-color: white; border: 1px solid #ccc; border-radius: 3px; }
        QTreeWidget { background-color: white; border: 1px solid #ccc; alternate-background-color: #f2f2f2; }
        QTreeWidget::item { padding: 3px; }
        QHeaderView::section { background-color: #e8e8e8; padding: 4px; border: 1px solid #d0d0d0; font-weight: bold;}
        QComboBox { padding: 3px 5px; border: 1px solid #ccc; border-radius: 3px; }
        QComboBox::drop-down { border: none; width: 15px;}
        QComboBox::down-arrow { image: url(:/qt-project.org/styles/commonstyle/images/downarraow-16.png); } /* Needs resource file or path */
        QScrollArea { border: none; }
    """
    app.setStyleSheet(qss)


    window = None
    try:
        logger.info("--- Starting Algorithm Optimizer Application (PyQt5) ---")
        # Set high DPI scaling based on Qt environment variables if needed
        # os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        # os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1" # or 0
        # os.environ["QT_SCALE_FACTOR"] = "1" # Manual scale factor

        window = AlgorithmOptimizerApp()
        window.show()
        exit_code = app.exec_()
        logger.info(f"--- Algorithm Optimizer Application Closed (Exit Code: {exit_code}) ---")
        sys.exit(exit_code)

    except Exception as e:
        logger.critical(f"Unhandled exception in PyQt main: {e}", exc_info=True)
        traceback.print_exc()
        # Attempt to show a final error message box if possible
        try:
            err_msg = f"Lỗi nghiêm trọng không mong muốn:\n{e}\n\nKiểm tra log file 'lottery_app_qt.log'."
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Lỗi Nghiêm Trọng")
            msg_box.setText(err_msg)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
        except Exception as final_err:
            # Fallback to printing if even the messagebox fails
            print(f"Error showing final error message box: {final_err}", file=sys.stderr)
            print(f"\nCRITICAL ERROR:\n{e}\nCheck 'lottery_app_qt.log'.", file=sys.stderr)
        sys.exit(1)
    finally:
        logging.shutdown()


if __name__ == "__main__":
    # Add script dir to path if needed (same as before)
    script_dir_main = Path(__file__).parent.resolve()
    if str(script_dir_main) not in sys.path:
        sys.path.insert(0, str(script_dir_main))
        print(f"Info: Added script directory to sys.path: {script_dir_main}")

    # Dependency checks (PyQt5 checked earlier, check astor)
    missing_libs = []
    if sys.version_info < (3, 9):
        try: import astor
        except ImportError: missing_libs.append("astor (pip install astor)")
    # No need to check tkcalendar

    if missing_libs:
        error_message = "LỖI: Thiếu thư viện:\n\n" + "\n".join(missing_libs) + "\n\nVui lòng cài đặt và chạy lại."
        print(error_message, file=sys.stderr)
        # Try showing a basic Qt message box before exiting
        try:
            temp_app = QApplication([])
            QMessageBox.critical(None, "Thiếu Thư Viện", error_message)
        except Exception:
            pass # Ignore if even this fails
        sys.exit(1)

    print(f"Info: Log file: {log_file_path}")
    main()