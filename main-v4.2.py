# -*- coding: utf-8 -*-
import os
import sys
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
import subprocess
from collections import Counter
from importlib import reload, util
from abc import ABC, abstractmethod
import re
import textwrap
import itertools  # Added for combination generation

try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFormLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QGroupBox,
        QComboBox, QSpinBox, QCheckBox, QScrollArea, QTextEdit, QProgressBar,
        QListWidget, QListWidgetItem, QDialog, QCalendarWidget, QMessageBox,
        QFileDialog, QStatusBar, QSplitter, QSizePolicy, QFrame, QRadioButton,
        QButtonGroup
    )
    from PyQt5.QtCore import Qt, QTimer, QDate, QObject, pyqtSignal, QThread, QSize, QRect
    from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QIntValidator, QDoubleValidator, QTextCursor, QFontDatabase, QPixmap, QPainter, QBrush
    HAS_PYQT5 = True
    print("PyQt5 library found.")
except ImportError as e:
    HAS_PYQT5 = False
    print(f"CRITICAL ERROR: PyQt5 library not found. Please install it: pip install PyQt5")
    print(f"Import Error: {e}")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Missing Library", "PyQt5 is required but not found.\nPlease install it using:\n\npip install PyQt5")
        root.destroy()
    except ImportError:
        pass
    sys.exit(1)


try:
    if sys.version_info < (3, 9):
        import astor
        HAS_ASTOR = True
    else:
        HAS_ASTOR = False
except ImportError:
    HAS_ASTOR = False

base_dir_for_log = Path(__file__).parent.resolve()
log_file_path = base_dir_for_log / "lottery_app_qt.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s'
)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s')
console_handler.setFormatter(formatter)
root_logger = logging.getLogger('')
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
root_logger.addHandler(console_handler)
root_logger.setLevel(logging.DEBUG)


main_logger = logging.getLogger("LotteryAppQt")
optimizer_logger = logging.getLogger("OptimizerQt")
style_logger = logging.getLogger("UIStyleQt")

try:
    script_dir_base = Path(__file__).parent.resolve()
    if str(script_dir_base) not in sys.path:
        sys.path.insert(0, str(script_dir_base))
    if 'algorithms.base' in sys.modules:
        try: reload(sys.modules['algorithms.base']); main_logger.debug("Reloaded algorithms.base.")
        except Exception: pass
    if 'algorithms' in sys.modules:
        try: reload(sys.modules['algorithms']); main_logger.debug("Reloaded algorithms package.")
        except Exception: pass

    from algorithms.base import BaseAlgorithm
    main_logger.info("Imported BaseAlgorithm successfully.")
except ImportError as e:
    print(f"Lỗi: Không thể import BaseAlgorithm từ algorithms.base: {e}", file=sys.stderr)
    main_logger.critical(f"Failed to import BaseAlgorithm: {e}", exc_info=True)
    class BaseAlgorithm(ABC):

        def __init__(self, data_results_list=None, cache_dir=None):
            self.config = {"description": "BaseAlgorithm Giả", "parameters": {}}
            self._raw_results_list = copy.deepcopy(data_results_list) if data_results_list else []
            self.cache_dir = cache_dir
            self.logger = logging.getLogger(f"DummyBase_{id(self)}")
            self._log('warning', f"Using Dummy BaseAlgorithm! Instance: {id(self)}")
        def get_config(self) -> dict: return copy.deepcopy(self.config)
        @abstractmethod
        def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
            self._log('error', "Phương thức predict() chưa được triển khai!")
            return {}
        def get_results_in_range(self, start_date: datetime.date, end_date: datetime.date) -> list:
            return [r for r in self._raw_results_list if start_date <= r.get('date') <= end_date]
        def extract_numbers_from_dict(self, result_dict: dict) -> set:
            numbers = set()
            if not isinstance(result_dict, dict): return numbers
            keys_to_ignore = {'date', '_id', 'source', 'day_of_week', 'sign', 'created_at', 'updated_at', 'province_name', 'province_id'}
            for key, value in result_dict.items():
                if key in keys_to_ignore: continue
                values_to_check = []
                if isinstance(value, (list, tuple)): values_to_check.extend(value)
                elif value is not None: values_to_check.append(value)
                for item in values_to_check:
                    if item is None: continue
                    try:
                        s_item = str(item).strip(); num = -1
                        if len(s_item) >= 2 and s_item[-2:].isdigit(): num = int(s_item[-2:])
                        elif len(s_item) == 1 and s_item.isdigit(): num = int(s_item)
                        if 0 <= num <= 99: numbers.add(num)
                    except (ValueError, TypeError, AttributeError): pass
            return numbers
        def _log(self, level: str, message: str):
            log_func = getattr(self.logger, level.lower(), self.logger.warning)
            log_func(f"[{self.__class__.__name__}] {message}")
    print("Cảnh báo: Sử dụng lớp BaseAlgorithm giả.", file=sys.stderr)
    main_logger.warning("Using dummy BaseAlgorithm class due to import failure.")
except Exception as base_import_err:
    print(f"Lỗi không xác định khi import BaseAlgorithm: {base_import_err}", file=sys.stderr)
    main_logger.critical(f"Unknown error importing BaseAlgorithm: {base_import_err}", exc_info=True)
    sys.exit(1)



class OptimizerEmbedded(QWidget):
    log_signal = pyqtSignal(str, str, str)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(float)
    best_update_signal = pyqtSignal(dict, tuple)
    finished_signal = pyqtSignal(str, bool, str)
    error_signal = pyqtSignal(str)

    def __init__(self, parent_widget: QWidget, base_dir: Path, main_app_instance):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        optimizer_logger.info("Initializing OptimizerEmbedded (PyQt5)...")
        self.base_dir = base_dir
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.base_dir / "config"
        self.algorithms_dir = self.base_dir / "algorithms"
        self.optimize_dir = self.base_dir / "optimize"
        self.calculate_dir = self.base_dir / "calculate"
        self.main_app = main_app_instance
        self.results_data = []
        self.loaded_algorithms = {}
        self.selected_algorithm_for_edit = None
        self.selected_algorithm_for_optimize = None
        self.editor_param_widgets = {}
        self.editor_original_params = {}
        self.optimizer_thread = None
        self.optimizer_queue = queue.Queue()
        self.optimizer_stop_event = threading.Event()
        self.optimizer_pause_event = threading.Event()
        self.optimizer_running = False
        self.optimizer_paused = False
        self.current_best_params = None
        self.current_best_score_tuple = (-1.0, -1.0, -1.0, -100.0)
        self.current_optimization_log_path = None
        self.current_optimize_target_dir = None
        self.optimizer_custom_steps = {}
        self.advanced_opt_widgets = {}
        self.can_resume = False
        self.combination_selection_checkboxes = {}
        self.current_combination_algos = []
        self.opt_start_time = 0.0
        self.opt_time_limit_sec = 0
        self.optimizer_timer = QTimer(self)
        self.optimizer_timer.timeout.connect(self._check_optimizer_queue)
        self.optimizer_timer_interval = 200

        self.display_timer = QTimer(self)
        self.display_timer.timeout.connect(self._update_optimizer_timer_display)
        self.display_timer_interval = 1000

        self.int_validator = QIntValidator()
        self.double_validator = QDoubleValidator()
        self.custom_steps_validator = QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression(r"^(?:[-+]?\d+(?:\.\d*)?(?:,\s*[-+]?\d+(?:\.\d*)?)*)?$")
        )
        self.weight_validator = QDoubleValidator()
        self.dimension_validator = QIntValidator(1, 9999)

        self.current_optimization_mode = 'auto_hill_climb' # 'auto_hill_climb' or 'generated_combinations'

        self.setup_ui()
        self.load_data()
        self.load_algorithms()
        self.update_status("Trình tối ưu sẵn sàng.")
        optimizer_logger.info("OptimizerEmbedded (PyQt5) initialized successfully.")

    def get_main_window(self):
        widget = self
        while widget is not None:
            if isinstance(widget, QMainWindow):
                return widget
            widget = widget.parent()
        return QApplication.activeWindow()

    def setup_ui(self):
        optimizer_logger.debug("Setting up optimizer embedded UI (PyQt5)...")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        top_groupbox = QGroupBox("Thông Tin Dữ Liệu (Optimizer)")
        top_layout = QGridLayout(top_groupbox)
        top_layout.setContentsMargins(10, 15, 10, 10)
        top_layout.setSpacing(10)

        top_layout.addWidget(QLabel("File dữ liệu:"), 0, 0, Qt.AlignLeft | Qt.AlignTop)
        self.data_file_path_label = QLabel("...")
        self.data_file_path_label.setWordWrap(True)
        self.data_file_path_label.setMinimumHeight(35)
        top_layout.addWidget(self.data_file_path_label, 0, 1)
        browse_button = QPushButton("Chọn File Khác...")
        browse_button.clicked.connect(self.browse_data_file)
        top_layout.addWidget(browse_button, 0, 2, Qt.AlignTop)
        reload_data_button = QPushButton("Tải lại Dữ liệu")
        reload_data_button.clicked.connect(self.load_data)
        top_layout.addWidget(reload_data_button, 0, 3, Qt.AlignTop)

        top_layout.addWidget(QLabel("Phạm vi:"), 1, 0, Qt.AlignLeft)
        self.data_range_label = QLabel("...")
        top_layout.addWidget(self.data_range_label, 1, 1, 1, 3)

        top_layout.setColumnStretch(1, 1)

        main_layout.addWidget(top_groupbox, 0)

        self.tab_widget = QTabWidget()

        main_layout.addWidget(self.tab_widget, 1)

        self.tab_select = QWidget()
        self.tab_edit = QWidget()
        self.tab_optimize = QWidget()

        self.tab_widget.addTab(self.tab_select, " Thuật Toán ♻️")
        self.tab_widget.addTab(self.tab_edit, " Chỉnh Sửa ✏")
        self.tab_widget.addTab(self.tab_optimize, " Tối Ưu Hóa 🚀")

        self.tab_widget.setTabEnabled(1, False)
        self.tab_widget.setTabEnabled(2, False)

        self.setup_select_tab()
        self.setup_edit_tab()
        self.setup_optimize_tab()

    def setup_select_tab(self):
        layout = QVBoxLayout(self.tab_select)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        control_frame = QWidget()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0,0,0,0)
        reload_button = QPushButton("Tải lại Danh sách Thuật toán")
        reload_button.clicked.connect(self.reload_algorithms)
        control_layout.addWidget(reload_button)
        control_layout.addStretch(1)
        layout.addWidget(control_frame)

        list_groupbox = QGroupBox("Danh sách thuật toán")
        list_layout = QVBoxLayout(list_groupbox)
        list_layout.setContentsMargins(5, 10, 5, 5)

        self.algo_scroll_area = QScrollArea()
        self.algo_scroll_area.setWidgetResizable(True)
        self.algo_scroll_area.setStyleSheet("QScrollArea { background-color: #FDFDFD; border: none; }")

        self.algo_scroll_widget = QWidget()
        self.algo_scroll_area.setWidget(self.algo_scroll_widget)
        self.algo_list_layout = QVBoxLayout(self.algo_scroll_widget)
        self.algo_list_layout.setAlignment(Qt.AlignTop)
        self.algo_list_layout.setSpacing(8)

        self.initial_algo_label = QLabel("Đang tải thuật toán...")
        self.initial_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_algo_label.setAlignment(Qt.AlignCenter)
        self.algo_list_layout.addWidget(self.initial_algo_label)

        list_layout.addWidget(self.algo_scroll_area)
        layout.addWidget(list_groupbox)

    def setup_edit_tab(self):
        layout = QVBoxLayout(self.tab_edit)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_frame.setFrameShadow(QFrame.Sunken)
        info_layout = QGridLayout(info_frame)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(6)

        info_layout.addWidget(QLabel("Thuật toán đang sửa:"), 0, 0, Qt.AlignLeft)
        self.edit_algo_name_label = QLabel("...")
        self.edit_algo_name_label.setStyleSheet(f"font-weight: bold; color: #007BFF; font-size: {self.main_app.get_font_size('title')}pt;")
        info_layout.addWidget(self.edit_algo_name_label, 0, 1)

        info_layout.addWidget(QLabel("Mô tả:"), 1, 0, Qt.AlignTop | Qt.AlignLeft)
        self.edit_algo_desc_label = QLabel("...")
        self.edit_algo_desc_label.setWordWrap(True)
        self.edit_algo_desc_label.setStyleSheet("color: #17a2b8;")
        info_layout.addWidget(self.edit_algo_desc_label, 1, 1)
        info_layout.setColumnStretch(1, 1)
        layout.addWidget(info_frame)

        splitter = QSplitter(Qt.Horizontal)

        param_groupbox = QGroupBox("Tham Số Có Thể Chỉnh Sửa")
        param_outer_layout = QVBoxLayout(param_groupbox)
        param_outer_layout.setContentsMargins(5, 10, 5, 5)

        param_scroll_area = QScrollArea()
        param_scroll_area.setWidgetResizable(True)
        param_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")

        self.edit_param_scroll_widget = QWidget()
        param_scroll_area.setWidget(self.edit_param_scroll_widget)
        self.edit_param_layout = QFormLayout(self.edit_param_scroll_widget)
        self.edit_param_layout.setLabelAlignment(Qt.AlignLeft)
        self.edit_param_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.edit_param_layout.setHorizontalSpacing(10)
        self.edit_param_layout.setVerticalSpacing(6)

        param_outer_layout.addWidget(param_scroll_area)
        splitter.addWidget(param_groupbox)

        explain_groupbox = QGroupBox("Giải Thích Thuật Toán")
        explain_layout = QVBoxLayout(explain_groupbox)
        explain_layout.setContentsMargins(5, 10, 5, 5)

        self.edit_explain_text = QTextEdit()
        self.edit_explain_text.setReadOnly(True)
        explain_font = self.main_app.get_qfont("code")
        self.edit_explain_text.setFont(explain_font)
        self.edit_explain_text.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #212529;
                border: 1px solid #CED4DA;
            }
        """)
        explain_layout.addWidget(self.edit_explain_text)
        splitter.addWidget(explain_groupbox)

        splitter.setSizes([splitter.width() // 2, splitter.width() // 2])

        layout.addWidget(splitter, 1)

        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addStretch(1)

        cancel_button = QPushButton("Hủy Bỏ")
        cancel_button.clicked.connect(self.cancel_edit)
        button_layout.addWidget(cancel_button)

        save_copy_button = QPushButton("Lưu Bản Sao...")
        save_copy_button.setObjectName("AccentButton")
        save_copy_button.clicked.connect(self.save_edited_copy)
        button_layout.addWidget(save_copy_button)
        layout.addWidget(button_frame)

    def setup_optimize_tab(self):
        # Layout chính cho tab Tối ưu hóa
        layout = QVBoxLayout(self.tab_optimize)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # === Phần Widget trên cùng (Thông tin thuật toán) ===
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0,0,0,0)
        top_layout.setSpacing(8)
        layout.addWidget(top_widget, 0) # Thêm widget này vào layout chính của tab

        # Khung chứa tên thuật toán đang tối ưu
        info_frame = QWidget()
        info_h_layout = QHBoxLayout(info_frame)
        info_h_layout.setContentsMargins(0,0,0,0)
        info_h_layout.addWidget(QLabel("Thuật toán tối ưu:"))
        self.opt_algo_name_label = QLabel("...")
        self.opt_algo_name_label.setStyleSheet(f"font-weight: bold; color: #28a745; font-size: {self.main_app.get_font_size('title')}pt;")
        info_h_layout.addWidget(self.opt_algo_name_label)
        info_h_layout.addStretch(1)
        top_layout.addWidget(info_frame) # Thêm vào layout trên cùng

        # === Phần Layout Ngang chứa các GroupBox cài đặt ===
        self.settings_container = QWidget()
        settings_h_layout = QHBoxLayout(self.settings_container)
        settings_h_layout.setContentsMargins(0, 0, 0, 0)
        settings_h_layout.setSpacing(10)
        top_layout.addWidget(self.settings_container) # Thêm layout ngang này vào layout trên cùng

        # === GroupBox 1: Cài Đặt Cơ Bản (Ngày tháng, thời gian) ===
        settings_groupbox = QGroupBox("Cài Đặt Cơ Bản")
        settings_layout = QGridLayout(settings_groupbox)
        settings_layout.setContentsMargins(10, 15, 10, 10)
        settings_layout.setVerticalSpacing(8)
        settings_layout.setHorizontalSpacing(0) # Giảm khoảng cách ngang nếu muốn

        settings_layout.addWidget(QLabel("Chọn khoảng thời gian tối ưu:"), 0, 0, 1, 4, Qt.AlignLeft)

        settings_layout.addWidget(QLabel("Từ ngày:"), 1, 0, Qt.AlignLeft)
        self.opt_start_date_edit = QLineEdit()
        self.opt_start_date_edit.setReadOnly(True)
        self.opt_start_date_edit.setAlignment(Qt.AlignCenter)
        self.opt_start_date_edit.setMinimumWidth(130)
        self.opt_start_date_edit.setToolTip("Ngày bắt đầu dữ liệu dùng để kiểm tra tối ưu.")
        settings_layout.addWidget(self.opt_start_date_edit, 1, 1)

        self.opt_start_date_button = QPushButton("📅")
        self.opt_start_date_button.setObjectName("CalendarButton")
        self.opt_start_date_button.setToolTip("Chọn ngày bắt đầu.")
        self.opt_start_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.opt_start_date_edit))
        settings_layout.addWidget(self.opt_start_date_button, 1, 2)

        settings_layout.addWidget(QLabel("Đến ngày:"), 2, 0, Qt.AlignLeft)
        self.opt_end_date_edit = QLineEdit()
        self.opt_end_date_edit.setReadOnly(True)
        self.opt_end_date_edit.setAlignment(Qt.AlignCenter)
        self.opt_end_date_edit.setMinimumWidth(130)
        self.opt_end_date_edit.setToolTip("Ngày kết thúc dữ liệu dùng để kiểm tra tối ưu (phải trước ngày cuối cùng trong file data).")
        settings_layout.addWidget(self.opt_end_date_edit, 2, 1)

        self.opt_end_date_button = QPushButton("📅")
        self.opt_end_date_button.setObjectName("CalendarButton")
        self.opt_end_date_button.setToolTip("Chọn ngày kết thúc.")
        self.opt_end_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.opt_end_date_edit))
        settings_layout.addWidget(self.opt_end_date_button, 2, 2)

        date_info_label = QLabel("(Ngày cuối < ngày cuối data 1 ngày)")
        date_info_label.setStyleSheet("font-style: italic; color: #6c757d;")
        settings_layout.addWidget(date_info_label, 3, 0, 1, 3, Qt.AlignLeft)

        settings_layout.addWidget(QLabel("Thời gian tối ưu tối đa (phút):"), 4, 0, Qt.AlignLeft)
        self.opt_time_limit_spinbox = QSpinBox()
        self.opt_time_limit_spinbox.setRange(1, 9999)
        self.opt_time_limit_spinbox.setValue(60)
        self.opt_time_limit_spinbox.setAlignment(Qt.AlignCenter)
        self.opt_time_limit_spinbox.setFixedWidth(80)
        self.opt_time_limit_spinbox.setToolTip("Giới hạn thời gian chạy tối đa cho một lần tối ưu.")
        settings_layout.addWidget(self.opt_time_limit_spinbox, 4, 1, Qt.AlignLeft)

        settings_layout.setColumnStretch(0, 0) # Cột label
        settings_layout.setColumnStretch(1, 0) # Cột input date/spinbox
        settings_layout.setColumnStretch(2, 0) # Cột button lịch
        settings_layout.setColumnStretch(3, 1) # Cột co giãn cuối
        settings_layout.setRowStretch(5, 1) # Đẩy các widget lên trên

        # Thêm GroupBox Cài đặt cơ bản vào layout ngang
        settings_h_layout.addWidget(settings_groupbox, 1) # Stretch factor 1

        # === GroupBox 2: Chế Độ Tối Ưu (MỚI) ===
        self.optimization_mode_groupbox = QGroupBox("Chế Độ Tối Ưu")
        mode_outer_layout = QVBoxLayout(self.optimization_mode_groupbox)
        mode_outer_layout.setContentsMargins(10, 15, 10, 10)
        mode_outer_layout.setSpacing(8)

        # Radio buttons chọn chế độ
        self.opt_mode_group = QButtonGroup(self)
        self.opt_mode_auto_radio = QRadioButton("Tối ưu Tự động (Hill Climb / Custom)")
        self.opt_mode_auto_radio.setChecked(True)
        self.opt_mode_auto_radio.toggled.connect(self._on_optimization_mode_changed)
        self.opt_mode_group.addButton(self.opt_mode_auto_radio)
        mode_outer_layout.addWidget(self.opt_mode_auto_radio)

        self.opt_mode_combo_radio = QRadioButton("Tạo Bộ Tham Số")
        self.opt_mode_combo_radio.toggled.connect(self._on_optimization_mode_changed)
        self.opt_mode_group.addButton(self.opt_mode_combo_radio)
        mode_outer_layout.addWidget(self.opt_mode_combo_radio)

        # Widget cài đặt cho Tạo Bộ Tham Số
        self.combo_gen_settings_widget = QWidget()
        combo_gen_layout = QHBoxLayout(self.combo_gen_settings_widget)
        combo_gen_layout.setContentsMargins(20, 5, 0, 0) # Thụt vào + top margin
        combo_gen_layout.setSpacing(8)
        combo_gen_layout.addWidget(QLabel("Số giá trị/tham số:"))
        self.combo_num_values_spinbox = QSpinBox()
        self.combo_num_values_spinbox.setRange(2, 50)
        self.combo_num_values_spinbox.setValue(10)
        self.combo_num_values_spinbox.setFixedWidth(60)
        combo_gen_layout.addWidget(self.combo_num_values_spinbox)
        self.combo_method_random_radio = QRadioButton("Random")
        self.combo_method_random_radio.setChecked(True)
        self.combo_method_adjacent_radio = QRadioButton("Liền Kề")
        combo_gen_layout.addWidget(self.combo_method_random_radio)
        combo_gen_layout.addWidget(self.combo_method_adjacent_radio)
        combo_gen_layout.addStretch(1)
        mode_outer_layout.addWidget(self.combo_gen_settings_widget) # Thêm vào groupbox chế độ
        self.combo_gen_settings_widget.setEnabled(False) # Ban đầu tắt

        mode_outer_layout.addStretch(1) # Đẩy các control lên trên

        # Thêm GroupBox Chế độ tối ưu vào layout ngang
        settings_h_layout.addWidget(self.optimization_mode_groupbox, 1) # Stretch factor 1

        # === GroupBox 3: Chi Tiết Tham Số (Đã sửa) ===
        self.custom_steps_groupbox = QGroupBox("Tùy Chỉnh tham số tối ưu (bước nhảy)")
        steps_outer_layout = QVBoxLayout(self.custom_steps_groupbox)
        steps_outer_layout.setContentsMargins(5, 10, 5, 5)
        steps_outer_layout.setSpacing(6)

        # Container và Scroll Area cho danh sách tham số
        self.param_scroll_widget_container = QWidget()
        param_scroll_layout = QVBoxLayout(self.param_scroll_widget_container)
        param_scroll_layout.setContentsMargins(0, 5, 0, 0)
        param_scroll_layout.setSpacing(4)

        adv_scroll_area = QScrollArea() # Giữ nguyên tên biến hoặc đổi nếu muốn
        adv_scroll_area.setWidgetResizable(True)
        adv_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")
        self.advanced_opt_params_widget = QWidget()
        adv_scroll_area.setWidget(self.advanced_opt_params_widget)
        self.advanced_opt_params_layout = QVBoxLayout(self.advanced_opt_params_widget)
        self.advanced_opt_params_layout.setAlignment(Qt.AlignTop)
        self.advanced_opt_params_layout.setSpacing(4)
        self.initial_adv_label = QLabel("Chọn thuật toán để xem tham số.")
        self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_adv_label.setAlignment(Qt.AlignCenter)
        self.advanced_opt_params_layout.addWidget(self.initial_adv_label)
        param_scroll_layout.addWidget(adv_scroll_area) # Thêm scroll area vào container

        # Thêm container chứa scroll vào layout của groupbox này
        steps_outer_layout.addWidget(self.param_scroll_widget_container)

        # Thêm GroupBox Tham số chi tiết vào layout ngang
        settings_h_layout.addWidget(self.custom_steps_groupbox, 2) # Stretch factor 2 (rộng hơn)

        # === GroupBox 4: Kết hợp với Thuật toán ===
        self.combination_groupbox = QGroupBox("Kết hợp với Thuật toán +")
        combo_outer_layout = QVBoxLayout(self.combination_groupbox)
        combo_outer_layout.setContentsMargins(5, 10, 5, 5)
        combo_outer_layout.setSpacing(6)

        combo_scroll_area = QScrollArea()
        combo_scroll_area.setWidgetResizable(True)
        combo_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")
        self.combination_scroll_widget = QWidget()
        combo_scroll_area.setWidget(self.combination_scroll_widget)
        self.combination_layout = QVBoxLayout(self.combination_scroll_widget)
        self.combination_layout.setAlignment(Qt.AlignTop)
        self.combination_layout.setSpacing(4)
        self.initial_combo_label = QLabel("Chọn thuật toán để tối ưu...")
        self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_combo_label.setAlignment(Qt.AlignCenter)
        self.combination_layout.addWidget(self.initial_combo_label)
        combo_outer_layout.addWidget(combo_scroll_area)

        # Thêm GroupBox Kết hợp vào layout ngang
        settings_h_layout.addWidget(self.combination_groupbox, 1) # Stretch factor 1

        # === Khung điều khiển (Start, Pause, Stop) ===
        control_frame = QWidget()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 5, 0, 5) # Điều chỉnh margins nếu cần
        control_layout.setSpacing(8) # Tăng khoảng cách nút
        self.opt_start_button = QPushButton("Bắt đầu Tối ưu")
        self.opt_start_button.setObjectName("AccentButton")
        self.opt_start_button.clicked.connect(self.start_optimization)
        control_layout.addWidget(self.opt_start_button)

        self.opt_resume_button = QPushButton("Tiếp tục Tối ưu")
        self.opt_resume_button.setObjectName("AccentButton")
        self.opt_resume_button.clicked.connect(self.resume_optimization_session)
        self.opt_resume_button.setEnabled(False)
        control_layout.addWidget(self.opt_resume_button)

        self.opt_pause_button = QPushButton("Tạm dừng")
        self.opt_pause_button.setObjectName("WarningButton")
        self.opt_pause_button.setEnabled(False)
        # Callback sẽ được connect trong update_optimizer_ui_state
        control_layout.addWidget(self.opt_pause_button)

        self.opt_stop_button = QPushButton("Dừng Hẳn")
        self.opt_stop_button.setObjectName("DangerButton")
        self.opt_stop_button.clicked.connect(self.stop_optimization)
        self.opt_stop_button.setEnabled(False)
        control_layout.addWidget(self.opt_stop_button)

        control_layout.addStretch(1)
        # Thêm khung điều khiển vào layout trên cùng (top_layout)
        top_layout.addWidget(control_frame)

        # === Khung Tiến trình (Progress Bar, Status, Time) ===
        progress_frame = QWidget()
        progress_layout = QGridLayout(progress_frame)
        progress_layout.setContentsMargins(0, 5, 0, 5)
        progress_layout.setVerticalSpacing(2)
        progress_layout.setHorizontalSpacing(8)
        self.opt_progressbar = QProgressBar()
        self.opt_progressbar.setTextVisible(False)
        self.opt_progressbar.setFixedHeight(22) # Có thể tăng chiều cao nếu muốn
        self.opt_progressbar.setRange(0, 100)
        self.opt_progressbar.setObjectName("OptimizeProgressBar")
        progress_layout.addWidget(self.opt_progressbar, 0, 0, 1, 4) # Span 4 cột

        self.opt_status_label = QLabel("Trạng thái: Chờ")
        self.opt_status_label.setStyleSheet("color: #6c757d;")
        progress_layout.addWidget(self.opt_status_label, 1, 0) # Cột 0

        self.opt_progress_label = QLabel("0%")
        self.opt_progress_label.setMinimumWidth(40)
        self.opt_progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_layout.addWidget(self.opt_progress_label, 1, 1) # Cột 1

        self.opt_time_static_label = QLabel("Thời gian còn lại:")
        self.opt_time_static_label.setStyleSheet("color: #6c757d;")
        progress_layout.addWidget(self.opt_time_static_label, 1, 2, Qt.AlignRight) # Cột 2, căn phải
        self.opt_time_static_label.setVisible(False)

        self.opt_time_remaining_label = QLabel("--:--:--")
        self.opt_time_remaining_label.setStyleSheet("font-weight: bold;")
        self.opt_time_remaining_label.setMinimumWidth(70)
        progress_layout.addWidget(self.opt_time_remaining_label, 1, 3, Qt.AlignLeft) # Cột 3, căn trái
        self.opt_time_remaining_label.setVisible(False)

        progress_layout.setColumnStretch(0, 1) # Cột status co giãn
        progress_layout.setColumnStretch(1, 0) # Cột progress label cố định
        progress_layout.setColumnStretch(2, 0) # Cột time static label cố định
        progress_layout.setColumnStretch(3, 0) # Cột time remaining cố định
        # Thêm khung tiến trình vào layout trên cùng (top_layout)
        top_layout.addWidget(progress_frame)

        # === GroupBox Nhật Ký Tối Ưu Hóa ===
        log_groupbox = QGroupBox("Nhật Ký Tối Ưu Hóa")
        log_outer_layout = QVBoxLayout(log_groupbox)
        log_outer_layout.setContentsMargins(5, 10, 5, 5)
        log_outer_layout.setSpacing(6)

        self.opt_log_text = QTextEdit()
        self.opt_log_text.setReadOnly(True)
        log_font = self.main_app.get_qfont("code")
        self.opt_log_text.setFont(log_font)
        self.opt_log_text.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #212529;
                border: 1px solid #CED4DA;
            }
        """)
        self._setup_log_formats() # Gọi hàm thiết lập format màu
        log_outer_layout.addWidget(self.opt_log_text, 1) # Tham số 1 để text edit co giãn

        # Khung chứa nút mở thư mục log
        log_button_frame = QWidget()
        log_button_layout = QHBoxLayout(log_button_frame)
        log_button_layout.setContentsMargins(0, 0, 0, 0)
        log_button_layout.addStretch(1)
        open_folder_button = QPushButton("Mở Thư Mục Tối Ưu")
        open_folder_button.clicked.connect(self.open_optimize_folder)
        log_button_layout.addWidget(open_folder_button)
        log_outer_layout.addWidget(log_button_frame)

        # Thêm GroupBox log vào layout chính của tab (layout)
        layout.addWidget(log_groupbox, 1) # Tham số 1 để groupbox này co giãn

    def _on_optimization_mode_changed(self, checked):
        if not checked:
            return # Only react when a button becomes checked

        sender = self.sender()
        if sender == self.opt_mode_auto_radio:
            self.current_optimization_mode = 'auto_hill_climb'
            self.combo_gen_settings_widget.setEnabled(False)
            self.param_scroll_widget_container.setEnabled(True)
            optimizer_logger.debug("Switched to Auto/Custom optimization mode.")
        elif sender == self.opt_mode_combo_radio:
            self.current_optimization_mode = 'generated_combinations'
            self.combo_gen_settings_widget.setEnabled(True)
            self.param_scroll_widget_container.setEnabled(False) # Disable custom step area
            optimizer_logger.debug("Switched to Generated Combinations optimization mode.")
        self._populate_advanced_optimizer_settings() # Re-populate to enable/disable correctly


    def _setup_log_formats(self):

        self.log_formats = {}
        base_font = self.main_app.get_qfont("code")
        bold_font = self.main_app.get_qfont("code_bold")
        bold_underline_font = self.main_app.get_qfont("code_bold_underline")

        def create_format(font, color_hex):
            fmt = QtGui.QTextCharFormat()
            fmt.setFont(font)
            fmt.setForeground(QColor(color_hex))
            return fmt

        self.log_formats["INFO"] = create_format(base_font, '#212529')
        self.log_formats["DEBUG"] = create_format(base_font, '#6c757d')
        self.log_formats["WARNING"] = create_format(base_font, '#ffc107')
        self.log_formats["ERROR"] = create_format(bold_font, '#dc3545')
        self.log_formats["CRITICAL"] = create_format(bold_underline_font, '#dc3545')
        self.log_formats["BEST"] = create_format(bold_font, '#28a745')
        self.log_formats["PROGRESS"] = create_format(base_font, '#17a2b8')
        self.log_formats["CUSTOM_STEP"] = create_format(base_font, '#6f42c1')
        self.log_formats["RESUME"] = create_format(bold_font, '#17a2b8')
        self.log_formats["COMBINE"] = create_format(base_font, "#fd7e14")
        self.log_formats["GEN_COMBO"] = create_format(base_font, "#E83E8C") # Pinkish for combo generation


    def browse_data_file(self):
        optimizer_logger.debug("Browsing for optimizer data file (PyQt5)...")
        initial_dir = str(self.data_dir)
        current_path_str = self.data_file_path_label.text()
        if current_path_str and current_path_str != "..." and Path(current_path_str).is_file():
            parent_dir = Path(current_path_str).parent
            if parent_dir.is_dir():
                initial_dir = str(parent_dir)

        filename, _ = QFileDialog.getOpenFileName(
            self.get_main_window(),
            "Chọn file dữ liệu JSON cho Optimizer",
            initial_dir,
            "JSON files (*.json);;All files (*.*)"
        )
        if filename:
            self.data_file_path_label.setText(filename)
            optimizer_logger.info(f"Optimizer data file selected by user: {filename}")
            self.load_data()

    def load_data(self):
        optimizer_logger.info("Loading lottery data for optimizer (PyQt5)...")
        self.results_data = []
        data_file_str = self.data_file_path_label.text()

        if not data_file_str or data_file_str == "...":
            default_path = self.data_dir / "xsmb-2-digits.json"
            if default_path.exists():
                data_file_str = str(default_path)
                self.data_file_path_label.setText(data_file_str)
            else:
                reply = QMessageBox.information(self.get_main_window(), "Chọn File Dữ Liệu",
                                               "Vui lòng chọn file dữ liệu JSON cho trình tối ưu.",
                                               QMessageBox.Ok | QMessageBox.Cancel)
                if reply == QMessageBox.Ok:
                    self.browse_data_file()
                    data_file_str = self.data_file_path_label.text()
                    if not data_file_str or data_file_str == "...":
                        self.update_status("Chưa chọn file dữ liệu cho trình tối ưu.")
                        self.data_range_label.setText("Chưa tải dữ liệu")
                        return
                else:
                    self.update_status("Chưa chọn file dữ liệu cho trình tối ưu.")
                    self.data_range_label.setText("Chưa tải dữ liệu")
                    return

        data_file_path = Path(data_file_str)
        self.data_file_path_label.setText(str(data_file_path))

        if not data_file_path.exists():
            optimizer_logger.error(f"Optimizer data file not found: {data_file_path}")
            QMessageBox.critical(self.get_main_window(), "Lỗi", f"File không tồn tại:\n{data_file_path}")
            self.data_range_label.setText("Lỗi file dữ liệu")
            return

        try:
            with open(data_file_path, 'r', encoding='utf-8') as f: raw_data = json.load(f)
            processed_results = []
            unique_dates = set()
            data_list_to_process = []
            if isinstance(raw_data, list): data_list_to_process = raw_data
            elif isinstance(raw_data, dict) and 'results' in raw_data and isinstance(raw_data.get('results'), dict):
                for date_str, result_dict in raw_data['results'].items():
                    if isinstance(result_dict, dict): data_list_to_process.append({'date': date_str, 'result': result_dict})
            else: raise ValueError("Định dạng JSON không hợp lệ.")
            for item in data_list_to_process:
                if not isinstance(item, dict): continue
                date_str_raw = item.get("date")
                if not date_str_raw: continue
                try:
                    date_str_cleaned = str(date_str_raw).split('T')[0]
                    date_obj = datetime.datetime.strptime(date_str_cleaned, '%Y-%m-%d').date()
                except ValueError: continue
                if date_obj in unique_dates: continue
                result_dict = item.get('result')
                if result_dict is None: result_dict = {k: v for k, v in item.items() if k != 'date'}
                if not result_dict: continue
                processed_results.append({'date': date_obj, 'result': result_dict})
                unique_dates.add(date_obj)

            if processed_results:
                processed_results.sort(key=lambda x: x['date'])
                self.results_data = processed_results
                start_date, end_date = self.results_data[0]['date'], self.results_data[-1]['date']
                self.data_range_label.setText(f"{start_date:%d/%m/%Y} - {end_date:%d/%m/%Y} ({len(self.results_data)} ngày)")
                self.update_status(f"Optimizer: Đã tải {len(self.results_data)} kết quả từ {data_file_path.name}")
                if not self.opt_start_date_edit.text() and len(self.results_data) > 1:
                    self.opt_start_date_edit.setText(start_date.strftime('%d/%m/%Y'))
                if not self.opt_end_date_edit.text() and len(self.results_data) > 1:
                    self.opt_end_date_edit.setText((end_date - datetime.timedelta(days=1)).strftime('%d/%m/%Y'))
            else:
                self.data_range_label.setText("Không có dữ liệu hợp lệ"); self.update_status("Optimizer: Không tải được dữ liệu.")
        except (json.JSONDecodeError, ValueError) as e:
            optimizer_logger.error(f"Optimizer: Invalid JSON/Data in {data_file_path.name}: {e}", exc_info=True)
            QMessageBox.critical(self.get_main_window(), "Lỗi Dữ Liệu (Optimizer)", f"File '{data_file_path.name}' không hợp lệ:\n{e}")
            self.data_range_label.setText("Lỗi định dạng file")
        except Exception as e:
            optimizer_logger.error(f"Optimizer: Unexpected error loading data: {e}", exc_info=True)
            QMessageBox.critical(self.get_main_window(), "Lỗi (Optimizer)", f"Lỗi khi tải dữ liệu:\n{e}")
            self.data_range_label.setText("Lỗi tải dữ liệu")

    def load_algorithms(self):
        optimizer_logger.info("Optimizer: Loading algorithms (PyQt5)...")
        main_window = self.get_main_window()

        while self.algo_list_layout.count() > 0:
            item = self.algo_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.initial_algo_label = QLabel("Đang tải thuật toán...")
        self.initial_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_algo_label.setAlignment(Qt.AlignCenter)
        self.algo_list_layout.addWidget(self.initial_algo_label)

        self.loaded_algorithms.clear()
        self.disable_edit_optimize_tabs()
        self.update_status("Optimizer: Đang tải thuật toán...")

        if not self.algorithms_dir.is_dir():
            QMessageBox.critical(main_window, "Lỗi Thư Mục", f"Không tìm thấy thư mục thuật toán:\n{self.algorithms_dir}")
            self.initial_algo_label.setText("Lỗi: Không tìm thấy thư mục thuật toán.")
            return

        try:
            algo_files = [f for f in self.algorithms_dir.glob('*.py') if f.is_file() and f.name not in ["__init__.py", "base.py"]]
        except Exception as e:
            QMessageBox.critical(main_window, "Lỗi", f"Lỗi đọc thư mục thuật toán:\n{e}")
            self.initial_algo_label.setText("Lỗi đọc thư mục thuật toán.")
            return

        count_success, count_fail = 0, 0
        data_copy_for_init = copy.deepcopy(self.results_data) if self.results_data else []
        cache_dir_for_init = self.calculate_dir
        loaded_algo_widgets = False
        for f_path in algo_files:
            module_name = f"algorithms.{f_path.stem}"; instance = None; config = None; class_name = None; module_obj = None
            display_name = f"{f_path.stem} ({f_path.name})"
            try:
                if module_name in sys.modules:
                    try: module_obj = reload(sys.modules[module_name])
                    except Exception:
                        try: del sys.modules[module_name]; module_obj = None
                        except KeyError: module_obj = None
                if module_obj is None:
                    spec = util.spec_from_file_location(module_name, f_path)
                    if spec and spec.loader:
                        module_obj = util.module_from_spec(spec)
                        sys.modules[module_name] = module_obj
                        spec.loader.exec_module(module_obj)
                    else: raise ImportError(f"Optimizer: Could not create spec/loader for {module_name}")
                if not module_obj: raise ImportError("Optimizer: Module object is None.")
                found_class = None
                for name, obj in inspect.getmembers(module_obj):
                    if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == module_name:
                        found_class = obj; class_name = name; display_name = f"{class_name} ({f_path.name})"; break
                if found_class:
                    try:
                        instance = found_class(data_results_list=data_copy_for_init, cache_dir=cache_dir_for_init)
                        config = instance.get_config()
                        if not isinstance(config, dict): config = {"description": "Config Error", "parameters": {}}
                        self.loaded_algorithms[display_name] = {'instance': instance, 'path': f_path, 'config': config, 'class_name': class_name, 'module_name': module_name}
                        self.create_optimizer_algorithm_ui_qt(display_name, config)
                        loaded_algo_widgets = True
                        count_success += 1
                    except Exception as init_err:
                        optimizer_logger.error(f"Optimizer: Error initializing/processing class {class_name}: {init_err}", exc_info=True)
                        if display_name in self.loaded_algorithms: del self.loaded_algorithms[display_name]
                        count_fail += 1
                else:
                    optimizer_logger.warning(f"No valid BaseAlgorithm subclass found in {f_path.name}")
                    count_fail += 1
            except ImportError as imp_err: optimizer_logger.error(f"Optimizer: Import error {f_path.name}: {imp_err}", exc_info=False); count_fail += 1
            except Exception as load_err: optimizer_logger.error(f"Optimizer: Error processing {f_path.name}: {load_err}", exc_info=True); count_fail += 1

        if loaded_algo_widgets and self.initial_algo_label:
            self.algo_list_layout.removeWidget(self.initial_algo_label)
            self.initial_algo_label.deleteLater()
            self.initial_algo_label = None
        elif not loaded_algo_widgets:
             self.initial_algo_label.setText("Không tìm thấy thuật toán hợp lệ.")

        status_msg = f"Optimizer: Tải {count_success} thuật toán"
        if count_fail > 0: status_msg += f" (lỗi: {count_fail})"
        self.update_status(status_msg)
        if count_fail > 0:
            QMessageBox.warning(main_window, "Lỗi Tải (Optimizer)", f"Lỗi tải {count_fail} file thuật toán.\nKiểm tra log.")
        self.check_resume_possibility()

    def create_optimizer_algorithm_ui_qt(self, display_name, config):

        if self.initial_algo_label:
             self.algo_list_layout.removeWidget(self.initial_algo_label)
             self.initial_algo_label.deleteLater()
             self.initial_algo_label = None

        algo_frame = QFrame()
        algo_frame.setFrameShape(QFrame.StyledPanel)
        algo_frame.setFrameShadow(QFrame.Raised)
        algo_frame.setLineWidth(1)
        algo_frame.setObjectName("CardFrame")

        algo_frame_layout = QHBoxLayout(algo_frame)
        algo_frame_layout.setContentsMargins(10, 8, 10, 8)

        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0,0,0,0)
        info_layout.setSpacing(2)

        try:
             algo_data = self.loaded_algorithms[display_name]
             class_name = algo_data.get('class_name', 'UnknownClass')
             file_name = algo_data.get('path', Path('unknown.py')).name
             desc = config.get("description", "N/A")
        except KeyError:
             class_name = "Error"; file_name = "error.py"; desc = "Lỗi tải thông tin thuật toán."

        display_string = f"{class_name} ({file_name})"
        name_file_label = QLabel(display_string)
        name_file_label.setFont(self.main_app.get_qfont("bold"))
        name_file_label.setStyleSheet(f"color: #212529;")
        info_layout.addWidget(name_file_label)

        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setFont(self.main_app.get_qfont("small"))
        desc_label.setStyleSheet("color: #5a5a5a;")
        desc_label.setToolTip(desc)
        info_layout.addWidget(desc_label)

        algo_frame_layout.addWidget(info_container, 1)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(5, 0, 0, 0)
        button_layout.setSpacing(4)
        button_layout.setAlignment(Qt.AlignTop)

        edit_button = QPushButton("Chỉnh Sửa")
        edit_button.setObjectName("ListAccentButton")
        edit_button.clicked.connect(lambda checked=False, name=display_name: self.trigger_select_for_edit(name))
        button_layout.addWidget(edit_button)

        optimize_button = QPushButton("Tối Ưu")
        optimize_button.setObjectName("ListAccentButton")
        optimize_button.clicked.connect(lambda checked=False, name=display_name: self.trigger_select_for_optimize(name))
        button_layout.addWidget(optimize_button)

        algo_frame_layout.addWidget(button_container)

        self.algo_list_layout.addWidget(algo_frame)
        if display_name in self.loaded_algorithms:
            self.loaded_algorithms[display_name]['ui_frame'] = algo_frame


    def reload_algorithms(self):
        optimizer_logger.info("Optimizer: Reloading algorithms (PyQt5)...")
        self.selected_algorithm_for_edit = None
        self.selected_algorithm_for_optimize = None
        self.disable_edit_optimize_tabs()
        self._clear_editor_fields()
        self._reset_advanced_opt_settings()
        self._clear_combination_selection()
        self.load_algorithms()
        self.check_resume_possibility()

    def trigger_select_for_edit(self, display_name):
        main_window = self.get_main_window()
        if display_name not in self.loaded_algorithms:
            QMessageBox.warning(main_window, "Lỗi", f"Không tìm thấy: {display_name}")
            return

        self.selected_algorithm_for_edit = display_name
        self.selected_algorithm_for_optimize = None
        self._clear_advanced_opt_fields()
        self._clear_combination_selection()

        self.populate_editor(display_name)
        self.tab_widget.setTabEnabled(1, True)
        self.tab_widget.setTabEnabled(2, False)
        self.tab_widget.setCurrentIndex(1)

        self.update_status(f"Optimizer: Đang chỉnh sửa: {self.loaded_algorithms[display_name]['class_name']}")
        self.check_resume_possibility()

    def trigger_select_for_optimize(self, display_name):

        main_window = self.get_main_window()
        if not self.main_app:
            optimizer_logger.error("Main app instance not found in trigger_select_for_optimize.")
            return
        if display_name not in self.loaded_algorithms:
            QMessageBox.warning(main_window, "Lỗi", f"Không tìm thấy thuật toán: {display_name}")
            return

        if self.optimizer_running:
            if self.selected_algorithm_for_optimize == display_name:
                optimizer_logger.debug(f"Optimizer running/paused for '{display_name}'. Switching to Optimize tab view.")
                try:
                    optimize_tab_index = -1
                    for i in range(self.tab_widget.count()):
                        if self.tab_widget.tabText(i).strip().startswith("Tối Ưu Hóa"):
                            optimize_tab_index = i
                            break
                    if optimize_tab_index != -1:
                        if not self.tab_widget.isTabEnabled(optimize_tab_index):
                             self.tab_widget.setTabEnabled(optimize_tab_index, True)
                        self.tab_widget.setCurrentIndex(optimize_tab_index)
                    else:
                        optimizer_logger.error("Could not find Optimize tab index.")
                except Exception as e_switch:
                     optimizer_logger.error(f"Error switching to Optimize tab: {e_switch}")
                return

            else:
                running_algo_short_name = self.selected_algorithm_for_optimize.split(' (')[0] if self.selected_algorithm_for_optimize else "khác"
                optimizer_logger.warning(f"Optimizer already running for '{self.selected_algorithm_for_optimize}'. Cannot start new optimization for '{display_name}'.")
                QMessageBox.critical(main_window, "Đang Chạy",
                                     f"Quá trình tối ưu hóa cho thuật toán '{running_algo_short_name}' đang chạy.\n\n"
                                     f"Vui lòng dừng quá trình hiện tại trước khi bắt đầu tối ưu một thuật toán khác.")
                return

        optimizer_logger.info(f"Selecting algorithm '{display_name}' for optimization setup.")
        self.selected_algorithm_for_optimize = display_name
        self.selected_algorithm_for_edit = None
        self._clear_editor_fields()

        self.populate_optimizer_info(display_name)
        self._populate_advanced_optimizer_settings()
        self._populate_combination_selection()

        try:
            edit_tab_index = -1
            optimize_tab_index = -1
            for i in range(self.tab_widget.count()):
                 tab_text = self.tab_widget.tabText(i).strip()
                 if tab_text.startswith("Chỉnh Sửa"):
                     edit_tab_index = i
                 elif tab_text.startswith("Tối Ưu Hóa"):
                     optimize_tab_index = i

            if edit_tab_index != -1: self.tab_widget.setTabEnabled(edit_tab_index, False)
            if optimize_tab_index != -1:
                 self.tab_widget.setTabEnabled(optimize_tab_index, True)
                 self.tab_widget.setCurrentIndex(optimize_tab_index)
            else:
                 optimizer_logger.error("Could not find Optimize tab index to enable/switch.")

        except Exception as e_tab:
             optimizer_logger.error(f"Error enabling/switching tabs: {e_tab}")


        algo_class_name = self.loaded_algorithms[display_name].get('class_name', display_name)
        self.update_status(f"Optimizer: Sẵn sàng tối ưu: {algo_class_name}")
        self._load_optimization_log()
        self.check_resume_possibility()

    def disable_edit_optimize_tabs(self):
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setTabEnabled(1, False)
            self.tab_widget.setTabEnabled(2, False)
            self._clear_advanced_opt_fields()
            self._clear_combination_selection()

        self.selected_algorithm_for_edit = None
        self.selected_algorithm_for_optimize = None
        self.check_resume_possibility()

    def populate_editor(self, display_name):
        self._clear_editor_fields()
        if display_name not in self.loaded_algorithms:
            return

        algo_data = self.loaded_algorithms[display_name]
        instance = algo_data['instance']
        config = algo_data['config']
        class_name = algo_data['class_name']

        self.edit_algo_name_label.setText(f"{class_name} ({algo_data['path'].name})")

        self.edit_algo_desc_label.setText(config.get("description", "N/A"))

        try:
            docstring = inspect.getdoc(instance.__class__)
            self.edit_explain_text.setPlainText(docstring if docstring else "Không có giải thích.")
        except Exception as e:
            self.edit_explain_text.setPlainText(f"Lỗi lấy docstring: {e}")

        parameters = config.get("parameters", {})
        self.editor_param_widgets = {}
        self.editor_original_params = copy.deepcopy(parameters)

        for name, value in parameters.items():
            if isinstance(value, (int, float)):
                param_label = QLabel(f"{name}:")
                param_input = QLineEdit(str(value))
                param_input.setAlignment(Qt.AlignRight)
                param_input.setFixedWidth(120)

                if isinstance(value, int):
                    param_input.setValidator(self.int_validator)
                else:
                    param_input.setValidator(self.double_validator)

                self.edit_param_layout.addRow(param_label, param_input)
                self.editor_param_widgets[name] = param_input


    def _clear_editor_fields(self):
        if hasattr(self, 'edit_algo_name_label'):
            self.edit_algo_name_label.setText("...")
        if hasattr(self, 'edit_algo_desc_label'):
            self.edit_algo_desc_label.setText("...")
        if hasattr(self, 'edit_explain_text'):
            self.edit_explain_text.clear()

        if hasattr(self, 'edit_param_layout'):
            while self.edit_param_layout.count() > 0:
                self.edit_param_layout.removeRow(0)

        self.editor_param_widgets = {}
        self.editor_original_params = {}

    def cancel_edit(self):
        self.selected_algorithm_for_edit = None
        self._clear_editor_fields()
        self.disable_edit_optimize_tabs()
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setCurrentIndex(0)
        self.update_status("Optimizer: Đã hủy chỉnh sửa.")

    def save_edited_copy(self):
        if not self.selected_algorithm_for_edit: return
        display_name = self.selected_algorithm_for_edit
        main_window = self.get_main_window()

        if display_name not in self.loaded_algorithms:
            QMessageBox.critical(main_window, "Lỗi", "Thuật toán không tồn tại.")
            return

        algo_data = self.loaded_algorithms[display_name]
        original_path = algo_data['path']
        class_name = algo_data['class_name']
        modified_params = {}

        try:
            for name, widget in self.editor_param_widgets.items():
                value_str = widget.text().strip()
                original_value = self.editor_original_params.get(name)
                if isinstance(original_value, float):
                    modified_params[name] = float(value_str)
                elif isinstance(original_value, int):
                    modified_params[name] = int(value_str)
        except ValueError as e:
            QMessageBox.critical(main_window, "Giá Trị Lỗi", f"Lỗi nhập số: {e}")
            return
        except Exception as e:
             QMessageBox.critical(main_window, "Lỗi Giao Diện", f"Lỗi đọc giá trị tham số: {e}")
             return

        final_params_for_save = self.editor_original_params.copy()
        final_params_for_save.update(modified_params)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_filename = f"{original_path.stem}_edited_{timestamp}.py"

        save_path_str, _ = QFileDialog.getSaveFileName(
            main_window,
            "Lưu Bản Sao Thuật Toán Đã Chỉnh Sửa",
            str(self.algorithms_dir / suggested_filename),
            "Python files (*.py);;All files (*.*)"
        )

        if not save_path_str:
            return

        save_path = Path(save_path_str)
        if save_path.resolve() == original_path.resolve():
            QMessageBox.critical(main_window, "Lỗi", "Không thể ghi đè file gốc.")
            return

        try:
            source_code = original_path.read_text(encoding='utf-8')
            modified_source = self.modify_algorithm_source_ast(source_code, class_name, final_params_for_save)
            if modified_source is None:
                raise ValueError("AST modification failed.")

            save_path.write_text(modified_source, encoding='utf-8')
            QMessageBox.information(main_window, "Lưu Thành Công", f"Đã lưu bản sao: {save_path.name}\n'Tải lại thuật toán' để dùng.")
            self.update_status(f"Optimizer: Đã lưu bản sao: {save_path.name}")
        except Exception as e:
            optimizer_logger.error(f"Error saving edited copy: {e}", exc_info=True)
            QMessageBox.critical(main_window, "Lỗi Lưu File", f"Không thể lưu bản sao:\n{e}")


    def modify_algorithm_source_ast(self, source_code, target_class_name, new_params):
        main_window = self.get_main_window()
        optimizer_logger.debug(f"Optimizer AST mod: Class '{target_class_name}', Params: {list(new_params.keys())}")
        try: tree = ast.parse(source_code)
        except SyntaxError as e: optimizer_logger.error(f"Optimizer: Syntax error parsing source: {e}"); return None
        class _SourceModifier(ast.NodeTransformer):
            def __init__(self, class_to_modify, params_to_update):
                self.target_class = class_to_modify; self.params_to_update = params_to_update; self.in_target_init = False; self.params_modified = False; self.imports_modified = False; self.current_class_name = None; super().__init__()
            def visit_ImportFrom(self, node):
                if node.level > 0:
                    fixed_module_path = f"algorithms.{node.module}" if node.module else "algorithms"
                    if node.module == 'base':
                        node.module = 'algorithms.base'
                        node.level = 0
                        self.imports_modified = True
                        optimizer_logger.debug(f"AST Fix: Changed 'from .base' to 'from algorithms.base'")
                    elif node.module:
                        node.module = fixed_module_path
                        node.level = 0
                        self.imports_modified = True
                        optimizer_logger.debug(f"AST Fix: Changed 'from .{node.module}' to 'from {fixed_module_path}'")
                return self.generic_visit(node)

            def visit_ClassDef(self, node):
                original_class = self.current_class_name; self.current_class_name = node.name
                if node.name == self.target_class: node.body = [self.visit(child) for child in node.body]
                else: self.generic_visit(node)
                self.current_class_name = original_class; return node
            def visit_FunctionDef(self, node):
                if node.name == '__init__' and self.current_class_name == self.target_class:
                     self.in_target_init = True; node.body = [self.visit(child) for child in node.body]; self.in_target_init = False
                else: self.generic_visit(node)
                return node
            def visit_Assign(self, node):
                if self.in_target_init and len(node.targets) == 1:
                    target = node.targets[0]
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self' and target.attr == 'config':
                         node.value = self.visit(node.value)
                         return node
                return self.generic_visit(node)
            def visit_Dict(self, node):
                if not self.in_target_init:
                    return self.generic_visit(node)

                param_key_index = -1
                param_value_node = None
                try:
                    if node.keys:
                        for i, key_node in enumerate(node.keys):
                            is_param_key = (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str) and key_node.value == 'parameters') or \
                                           (hasattr(ast, 'Str') and isinstance(key_node, ast.Str) and key_node.s == 'parameters')

                            if is_param_key:
                                param_key_index = i
                                param_value_node = node.values[i]
                                break
                except Exception as e_dict:
                     optimizer_logger.warning(f"Error checking dict keys during AST modification: {e_dict}")
                     return self.generic_visit(node)


                if param_key_index != -1 and isinstance(param_value_node, ast.Dict):
                    new_keys = []
                    new_values = []
                    modified_in_subdict = False

                    original_param_nodes = {}
                    if param_value_node.keys:
                        for k, v in zip(param_value_node.keys, param_value_node.values):
                            param_name_str = None
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                param_name_str = k.value
                            elif hasattr(ast, 'Str') and isinstance(k, ast.Str):
                                param_name_str = k.s

                            if param_name_str:
                                original_param_nodes[param_name_str] = (k, v)

                    for param_name, new_value in self.params_to_update.items():
                        if param_name in original_param_nodes:
                            p_key_node, p_val_node = original_param_nodes[param_name]
                            new_val_node = None

                            if sys.version_info >= (3, 8):
                                if isinstance(new_value, (int, float)):
                                    if new_value < 0:
                                        new_val_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=abs(new_value)))
                                    else:
                                        new_val_node = ast.Constant(value=new_value)
                                elif isinstance(new_value, str):
                                    new_val_node = ast.Constant(value=new_value)
                                elif isinstance(new_value, bool):
                                    new_val_node = ast.Constant(value=new_value)
                                elif new_value is None:
                                    new_val_node = ast.Constant(value=None)
                            else:
                                if isinstance(new_value, (int, float)):
                                    new_val_node = ast.Num(n=new_value)
                                elif isinstance(new_value, str):
                                    new_val_node = ast.Str(s=new_value)
                                elif isinstance(new_value, bool):
                                    new_val_node = ast.NameConstant(value=new_value)
                                elif new_value is None:
                                    new_val_node = ast.NameConstant(value=None)

                            if new_val_node is not None:
                                new_keys.append(p_key_node)
                                new_values.append(new_val_node)
                                modified_in_subdict = True
                            else:
                                new_keys.append(p_key_node)
                                new_values.append(p_val_node)

                    updated_keys = set(self.params_to_update.keys())
                    for name, (k_node, v_node) in original_param_nodes.items():
                        if name not in updated_keys:
                            new_keys.append(k_node)
                            new_values.append(v_node)

                    param_value_node.keys = new_keys
                    param_value_node.values = new_values
                    if modified_in_subdict:
                        self.params_modified = True

                return self.generic_visit(node)

        modifier = _SourceModifier(target_class_name, new_params)
        modified_tree = modifier.visit(tree)

        if not modifier.params_modified and not modifier.imports_modified:
            optimizer_logger.warning("Optimizer AST mod: No parameters or imports updated.")
        elif modifier.params_modified and modifier.imports_modified:
            optimizer_logger.info("Optimizer AST modification: Parameters and Imports updated.")
        elif modifier.params_modified:
            optimizer_logger.info("Optimizer AST modification: Parameters updated.")
        elif modifier.imports_modified:
            optimizer_logger.info("Optimizer AST modification: Imports updated.")

        try:
            if sys.version_info >= (3, 9):
                modified_code = ast.unparse(modified_tree)
            elif HAS_ASTOR:
                modified_code = astor.to_source(modified_tree)
            else:
                QMessageBox.critical(self.get_main_window(), "Lỗi Thư Viện", "Cần thư viện 'astor' cho Python < 3.9 để chỉnh sửa file thuật toán.\nCài đặt: pip install astor")
                return None
        except Exception as unparse_err:
            optimizer_logger.error(f"Error unparsing modified AST: {unparse_err}", exc_info=True)
            return None

        return modified_code

    def _populate_combination_selection(self):
        container_layout = self.combination_layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.combination_selection_checkboxes.clear()

        if not self.selected_algorithm_for_optimize:
            self.initial_combo_label = QLabel("Chưa chọn thuật toán.")
            self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(self.initial_combo_label)
            return

        target_algo_name = self.selected_algorithm_for_optimize
        available_algos = sorted(self.loaded_algorithms.keys())

        if len(available_algos) <= 1:
            self.initial_combo_label = QLabel("Không có thuật toán khác.")
            self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(self.initial_combo_label)
            return

        instruction_label = QLabel("Chọn thuật toán để chạy cùng:")
        instruction_label.setStyleSheet("font-style: italic;")
        container_layout.addWidget(instruction_label)

        for algo_name in available_algos:
            if algo_name == target_algo_name:
                continue
            class_name_only = algo_name.split(' (')[0]
            chk = QCheckBox(class_name_only)
            chk.setToolTip(algo_name)
            container_layout.addWidget(chk)
            self.combination_selection_checkboxes[algo_name] = chk

    def _clear_combination_selection(self):
        container_layout = self.combination_layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.combination_selection_checkboxes.clear()

        self.initial_combo_label = QLabel("Chọn thuật toán để tối ưu...")
        self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        container_layout.addWidget(self.initial_combo_label)

    def _get_selected_combination_algos(self) -> list[str]:
        return [name for name, chk in self.combination_selection_checkboxes.items() if chk.isChecked()]

    def _populate_advanced_optimizer_settings(self):
        container_layout = self.advanced_opt_params_layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.advanced_opt_widgets.clear()

        if not self.selected_algorithm_for_optimize:
            self.initial_adv_label = QLabel("Chưa chọn thuật toán.")
            self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(self.initial_adv_label)
            return

        display_name = self.selected_algorithm_for_optimize
        if display_name not in self.loaded_algorithms:
            error_label = QLabel("Lỗi: Thuật toán không tìm thấy.")
            error_label.setStyleSheet("color: #dc3545;")
            container_layout.addWidget(error_label)
            return

        algo_data = self.loaded_algorithms[display_name]
        parameters = algo_data['config'].get('parameters', {})
        numeric_params = {k: v for k, v in parameters.items() if isinstance(v, (int, float))}

        if not numeric_params:
            self.initial_adv_label = QLabel("Không có tham số số học.")
            self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(self.initial_adv_label)
            return

        header_frame = QWidget()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(5, 5, 5, 10)
        header_layout.addWidget(QLabel("Tham số"), 2)
        header_layout.addWidget(QLabel("Giá trị gốc"), 1)
        header_layout.addWidget(QLabel("Chế độ"), 1)
        header_layout.addWidget(QLabel("Bước (+/-) cách bởi dấu phẩy"), 3)
        container_layout.addWidget(header_frame)

        # Only show custom step controls if in 'auto_hill_climb' mode
        is_auto_mode = (self.current_optimization_mode == 'auto_hill_climb')
        header_frame.setVisible(is_auto_mode)

        for name, value in numeric_params.items():
            param_frame = QWidget()
            param_layout = QHBoxLayout(param_frame)
            param_layout.setContentsMargins(5, 2, 5, 2)

            if name not in self.optimizer_custom_steps:
                self.optimizer_custom_steps[name] = {'mode': 'Auto', 'steps': [], 'str_value': ""}

            param_state = self.optimizer_custom_steps[name]

            param_label = QLabel(name)
            param_layout.addWidget(param_label, 2)

            value_label = QLabel(f"{value:.4g}" if isinstance(value, float) else str(value))
            value_label.setStyleSheet("color: #6c757d;")
            param_layout.addWidget(value_label, 1)

            mode_combo = QComboBox()
            mode_combo.addItems(["Auto", "Custom"])
            mode_combo.setCurrentText(param_state['mode'])
            mode_combo.setFixedWidth(80)
            param_layout.addWidget(mode_combo, 1)

            steps_entry = QLineEdit(param_state.get('str_value', ''))
            steps_entry.setValidator(self.custom_steps_validator)
            steps_entry.setEnabled(param_state['mode'] == 'Custom')
            param_layout.addWidget(steps_entry, 3)

            mode_combo.currentTextChanged.connect(
                lambda text, n=name, mc=mode_combo, se=steps_entry: self._on_step_mode_change(n, mc, se)
            )
            steps_entry.textChanged.connect(
                lambda text, n=name, se=steps_entry: self._update_custom_steps(n, se)
            )

            container_layout.addWidget(param_frame)
            self.advanced_opt_widgets[name] = {'mode_combo': mode_combo, 'steps_entry': steps_entry}

            # Hide the frame if not in auto mode
            param_frame.setVisible(is_auto_mode)


    def _on_step_mode_change(self, param_name, mode_combo_widget, steps_entry_widget):

        new_mode = mode_combo_widget.currentText()
        if param_name in self.optimizer_custom_steps:
            self.optimizer_custom_steps[param_name]['mode'] = new_mode
            is_custom = (new_mode == 'Custom')
            steps_entry_widget.setEnabled(is_custom)
            if is_custom:
                steps_entry_widget.setFocus()
                self._update_custom_steps(param_name, steps_entry_widget)
            else:
                steps_entry_widget.setStyleSheet("")

    def _validate_custom_steps_input_bool(self, text):

        if not text: return True
        regex = QtCore.QRegularExpression(r"^(?:[-+]?\d+(?:\.\d*)?(?:,\s*[-+]?\d+(?:\.\d*)?)*)?$")
        match = regex.match(text)
        return match.hasMatch() and match.capturedLength() == len(text)


    def _update_custom_steps(self, param_name, steps_entry_widget):

        steps_str = steps_entry_widget.text().strip()
        error_style = "QLineEdit { border: 1px solid #dc3545; }"

        if param_name in self.optimizer_custom_steps:
            self.optimizer_custom_steps[param_name]['str_value'] = steps_str

            if self.optimizer_custom_steps[param_name]['mode'] == 'Custom':
                is_valid_syntax = self._validate_custom_steps_input_bool(steps_str)
                parse_error = False
                parsed_steps = []

                if is_valid_syntax and steps_str:
                    try:
                        original_value = None
                        if self.selected_algorithm_for_optimize and self.selected_algorithm_for_optimize in self.loaded_algorithms:
                             original_value = self.loaded_algorithms[self.selected_algorithm_for_optimize]['config'].get('parameters', {}).get(param_name)

                        if original_value is None:
                            raise ValueError(f"Cannot get original type for '{param_name}'.")

                        is_original_int = isinstance(original_value, int)
                        temp_parsed = []
                        for part in steps_str.split(','):
                            part = part.strip()
                            if part:
                                num_val = float(part)
                                if is_original_int:
                                    if num_val == int(num_val):
                                        temp_parsed.append(int(num_val))
                                    else:
                                        raise ValueError(f"Integer parameter '{param_name}' requires integer steps. Invalid step: '{part}'.")
                                else:
                                    temp_parsed.append(num_val)

                        if temp_parsed:
                            parsed_steps = sorted(list(set(temp_parsed)))

                    except (ValueError, KeyError, TypeError) as e:
                        parse_error = True
                        parsed_steps = []
                        optimizer_logger.warning(f"Error parsing custom steps for {param_name}: {e}")
                elif not is_valid_syntax and steps_str:
                    parse_error = True
                    parsed_steps = []
                else:
                    parse_error = False
                    parsed_steps = []


                self.optimizer_custom_steps[param_name]['steps'] = parsed_steps

                if parse_error:
                    steps_entry_widget.setStyleSheet(error_style)
                else:
                    steps_entry_widget.setStyleSheet("")

            else:
                self.optimizer_custom_steps[param_name]['steps'] = []
                steps_entry_widget.setStyleSheet("")


    def _reset_advanced_opt_settings(self):
        self.optimizer_custom_steps.clear()
        container_layout = self.advanced_opt_params_layout
        if container_layout:
            while container_layout.count() > 0:
                item = container_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.advanced_opt_widgets.clear()

        self.initial_adv_label = QLabel("Chọn thuật toán để xem tham số.")
        self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
        if container_layout:
            container_layout.addWidget(self.initial_adv_label)

    def _clear_advanced_opt_fields(self):
        self._reset_advanced_opt_settings()

    def populate_optimizer_info(self, display_name):
        if display_name in self.loaded_algorithms:
            class_name = self.loaded_algorithms[display_name]['class_name']
            filename = self.loaded_algorithms[display_name]['path'].name
            self.opt_algo_name_label.setText(f"{class_name} ({filename})")
        else:
            self.opt_algo_name_label.setText("Lỗi: Không tìm thấy thuật toán")
            self.opt_algo_name_label.setStyleSheet("color: #dc3545;")

    def start_optimization(self, initial_params=None, initial_score_tuple=None, initial_combination_algos=None):
        """
        Initiates the optimization process, either resuming or starting fresh.
        Gathers settings and delegates the actual work to a worker thread.
        For 'generated_combinations' mode, it gathers parameters for generation
        but the generation itself happens in the worker thread.
        """
        is_resuming = initial_params is not None and initial_score_tuple is not None
        main_window = self.get_main_window()

        if self.optimizer_running:
            QMessageBox.warning(main_window, "Đang Chạy", "Quá trình tối ưu hóa đang chạy.")
            return

        if not self.selected_algorithm_for_optimize:
            QMessageBox.critical(main_window, "Lỗi", "Chưa chọn thuật toán để tối ưu hóa.")
            return

        display_name = self.selected_algorithm_for_optimize
        if display_name not in self.loaded_algorithms:
            QMessageBox.critical(main_window, "Lỗi", f"Thuật toán '{display_name}' không còn được tải.")
            return

        algo_data = self.loaded_algorithms[display_name]
        original_params = algo_data['config'].get('parameters', {})
        numeric_params_check = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}

        # Check if there are numeric params only if NOT generating combinations
        # (Generating combinations might work even without optimizable params in the target,
        # though less useful, but we allow it structurally).
        if not numeric_params_check and self.current_optimization_mode != 'generated_combinations':
            QMessageBox.information(main_window, "Thông Báo", "Thuật toán này không có tham số số học để tối ưu (ở chế độ Auto/Custom).")
            # Allow proceeding if generating combinations, as it tests discrete sets.
            # return # Removed return to allow proceeding in combo mode

        if is_resuming and initial_combination_algos is not None:
            combination_algos_to_use = initial_combination_algos
        else:
            combination_algos_to_use = self._get_selected_combination_algos()

        # --- Lấy cài đặt chung ---
        start_d, end_d, time_limit_min = self._validate_common_opt_settings_qt()
        if start_d is None: # Validation failed
            return

        final_custom_steps_config = {}
        generation_params_for_worker = None # Dùng cho mode combo
        mode_to_run = self.current_optimization_mode # Lưu lại mode hiện tại

        if mode_to_run == 'auto_hill_climb':
            final_custom_steps_config, has_invalid_custom_steps = self._finalize_custom_steps_config_qt(original_params)
            if not numeric_params_check and not final_custom_steps_config: # Double check if absolutely nothing to optimize
                 QMessageBox.information(main_window, "Thông Báo", "Thuật toán không có tham số số học và không có bước tùy chỉnh nào được định nghĩa.")
                 return
            # Cho phép chạy ngay cả khi có invalid steps, chúng sẽ chạy ở chế độ Auto

        elif mode_to_run == 'generated_combinations':
            # --- THU THẬP THÔNG TIN CHO GENERATION (Không tạo ở đây) ---
            num_values_per_param = self.combo_num_values_spinbox.value()
            generation_method = "random" if self.combo_method_random_radio.isChecked() else "adjacent"
            # Tạo dict chứa các thông tin cần thiết để worker tạo combinations
            generation_params_for_worker = {
                'original_params': original_params,
                'num_values': num_values_per_param,
                'method': generation_method
            }
            optimizer_logger.info(f"Preparing to generate {num_values_per_param} values per param using '{generation_method}' method IN WORKER.")

            # Ước tính số lượng để cảnh báo người dùng nếu cần
            estimated_total = 1
            numeric_params_count = sum(1 for v in original_params.values() if isinstance(v, (int, float)))
            if numeric_params_count > 0:
                try:
                    # Sử dụng lũy thừa cẩn thận để tránh tràn số
                    if num_values_per_param > 0 and numeric_params_count > 0:
                         if num_values_per_param == 1:
                              estimated_total = 1
                         elif numeric_params_count * math.log(num_values_per_param) < math.log(sys.maxsize): # Check approx magnitude
                              estimated_total = num_values_per_param ** numeric_params_count
                         else:
                              estimated_total = float('inf') # Indicate potentially huge number
                except OverflowError:
                     estimated_total = float('inf') # Huge number if direct calculation overflows
                except Exception as est_err:
                     optimizer_logger.error(f"Error estimating combination count: {est_err}")
                     estimated_total = -1 # Indicate error in estimation

            if estimated_total == float('inf') or estimated_total > 100000: # Tăng ngưỡng cảnh báo
                display_estimate = "rất lớn (>100,000)" if estimated_total == float('inf') else f"khoảng {estimated_total}"
                reply = QMessageBox.question(main_window, "Số Lượng Lớn (Ước Tính)",
                                                f"Việc tạo và kiểm tra {display_estimate} bộ tham số có thể rất lâu và tốn nhiều bộ nhớ.\n\nBạn có muốn tiếp tục không?",
                                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                      return
            elif estimated_total == -1:
                 optimizer_logger.warning("Could not reliably estimate combination count, proceeding without warning.")
            # --- KẾT THÚC THU THẬP THÔNG TIN ---

        else:
             QMessageBox.critical(main_window, "Lỗi Chế Độ", f"Chế độ tối ưu không xác định: {mode_to_run}")
             return

        # Gọi hàm bắt đầu luồng worker với thông tin đã chuẩn bị
        self._start_optimization_worker_thread(
            display_name=display_name,
            start_date=start_d,
            end_date=end_d,
            time_limit_min=time_limit_min,
            custom_steps_config=final_custom_steps_config, # Dùng cho mode auto/custom
            generation_params=generation_params_for_worker, # Dùng cho mode combo
            combination_algos=combination_algos_to_use,
            initial_params=initial_params,
            initial_score_tuple=initial_score_tuple,
            is_resuming=is_resuming,
            mode=mode_to_run # Truyền mode đã xác định
        )

    def resume_optimization_session(self):
        optimizer_logger.info("Action: Resume optimization requested (PyQt5).")
        main_window = self.get_main_window()

        if self.optimizer_running:
            QMessageBox.warning(main_window, "Đang Chạy", "Tối ưu hóa đang chạy.")
            return
        if not self.selected_algorithm_for_optimize:
            QMessageBox.critical(main_window, "Lỗi", "Chưa chọn thuật toán để tiếp tục tối ưu.")
            return

        target_display_name = self.selected_algorithm_for_optimize
        if target_display_name not in self.loaded_algorithms:
            QMessageBox.critical(main_window, "Lỗi", f"Thuật toán '{target_display_name}' không còn được tải.")
            return

        algo_data = self.loaded_algorithms[target_display_name]
        optimize_target_dir = self.optimize_dir / algo_data['path'].stem
        success_dir = optimize_target_dir / "success"

        latest_json_path, latest_data = self.find_latest_successful_optimization(success_dir, algo_data['path'].stem)

        if not latest_json_path:
            QMessageBox.information(main_window, "Không Tìm Thấy", f"Không tìm thấy kết quả/trạng thái tối ưu đã lưu cho:\n{target_display_name}")
            return

        try:

            # Resume always uses 'auto_hill_climb' mode
            self.opt_mode_auto_radio.setChecked(True)
            self.current_optimization_mode = 'auto_hill_climb'
            self._populate_advanced_optimizer_settings()


            loaded_params = latest_data.get("params")
            loaded_score_tuple = tuple(latest_data.get("score_tuple"))
            loaded_range_str = latest_data.get("optimization_range")
            loaded_combo_algos_raw = latest_data.get("combination_algorithms", [])

            if not isinstance(loaded_params, dict) or \
               not isinstance(loaded_score_tuple, tuple) or \
               len(loaded_score_tuple) != 4 or \
               not isinstance(loaded_range_str, str) or \
               not isinstance(loaded_combo_algos_raw, list):
                raise ValueError("Dữ liệu JSON không hợp lệ.")

            try:
                start_s, end_s = loaded_range_str.split('_to_')
                loaded_start_date = datetime.datetime.strptime(start_s, '%Y-%m-%d').date()
                loaded_end_date = datetime.datetime.strptime(end_s, '%Y-%m-%d').date()
                self.opt_start_date_edit.setText(loaded_start_date.strftime('%d/%m/%Y'))
                self.opt_end_date_edit.setText(loaded_end_date.strftime('%d/%m/%Y'))
            except (ValueError, AttributeError) as date_err:
                raise ValueError(f"Lỗi phân tích ngày '{loaded_range_str}': {date_err}")

            current_numeric_keys = {k for k, v in algo_data['config'].get('parameters', {}).items() if isinstance(v, (int, float))}
            loaded_numeric_keys = {k for k, v in loaded_params.items() if isinstance(v, (int, float))}
            if current_numeric_keys != loaded_numeric_keys:
                reply = QMessageBox.question(main_window, "Tham Số Không Khớp",
                                             "Các tham số số học trong file trạng thái không khớp với thuật toán hiện tại.\n\nTiếp tục với tham số đã lưu?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            final_combo_algos_to_use = []
            missing_combo_algos = []
            for combo_name in loaded_combo_algos_raw:
                if combo_name in self.loaded_algorithms:
                    final_combo_algos_to_use.append(combo_name)
                else:
                    missing_combo_algos.append(combo_name)

            if missing_combo_algos:
                msg = f"Các thuật toán kết hợp sau đây đã được sử dụng trong lần chạy trước nhưng hiện không tìm thấy:\n\n- {', '.join(missing_combo_algos)}\n\nTiếp tục tối ưu mà không có các thuật toán này?"
                reply = QMessageBox.question(main_window, "Thiếu Thuật Toán Kết Hợp", msg,
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            self._populate_combination_selection()
            for name, chk in self.combination_selection_checkboxes.items():
                chk.setChecked(name in final_combo_algos_to_use)

            self._log_to_optimizer_display("INFO", f"TIẾP TỤC TỐI ƯU TỪ FILE: {latest_json_path.name}", tag="RESUME")
            self._log_to_optimizer_display("INFO", f"Tham số đích bắt đầu: {loaded_params}", tag="RESUME")
            self._log_to_optimizer_display("INFO", f"Điểm số bắt đầu: ({', '.join(f'{s:.3f}' for s in loaded_score_tuple)})", tag="RESUME")
            self._log_to_optimizer_display("INFO", f"Khoảng ngày: {self.opt_start_date_edit.text()} - {self.opt_end_date_edit.text()}", tag="RESUME")
            self._log_to_optimizer_display("INFO", f"Thuật toán kết hợp: {final_combo_algos_to_use or '(Không có)'}", tag="RESUME")

            _, _, time_limit_min = self._validate_common_opt_settings_qt(check_dates=False)
            if time_limit_min is None: return

            original_params = algo_data['config'].get('parameters', {})
            final_custom_steps_config, has_invalid_custom_steps = self._finalize_custom_steps_config_qt(original_params)
            if has_invalid_custom_steps:
                self._populate_advanced_optimizer_settings()


            self.start_optimization(initial_params=loaded_params,
                                    initial_score_tuple=loaded_score_tuple,
                                    initial_combination_algos=final_combo_algos_to_use)

        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            QMessageBox.critical(main_window, "Lỗi Tải Trạng Thái", f"Không thể tải trạng thái từ:\n{latest_json_path.name if latest_json_path else 'N/A'}\n\nLỗi: {e}")
        except Exception as e:
            optimizer_logger.error(f"Unexpected error resuming optimization: {e}", exc_info=True)
            QMessageBox.critical(main_window, "Lỗi Không Xác Định", f"Đã xảy ra lỗi khi chuẩn bị tiếp tục:\n{e}")


    def _validate_common_opt_settings_qt(self, check_dates=True):

        start_d, end_d = None, None
        main_window = self.get_main_window()

        if check_dates:
            start_s = self.opt_start_date_edit.text()
            end_s = self.opt_end_date_edit.text()
            if not start_s or not end_s:
                QMessageBox.warning(main_window, "Thiếu Ngày", "Vui lòng chọn ngày bắt đầu và kết thúc cho khoảng dữ liệu kiểm tra.")
                return None, None, None
            try:
                start_d = datetime.datetime.strptime(start_s, '%d/%m/%Y').date()
                end_d = datetime.datetime.strptime(end_s, '%d/%m/%Y').date()
            except ValueError:
                QMessageBox.critical(main_window, "Lỗi Ngày", "Định dạng ngày tháng không hợp lệ. Sử dụng định dạng dd/mm/yyyy.")
                return None, None, None

            if start_d > end_d:
                QMessageBox.warning(main_window, "Ngày Lỗi", "Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
                return None, None, None

            if not self.results_data or len(self.results_data) < 2:
                QMessageBox.critical(main_window, "Thiếu Dữ Liệu", "Cần ít nhất 2 ngày dữ liệu trong file đã tải để thực hiện tối ưu hóa.")
                return None, None, None

            min_data_date = self.results_data[0]['date']
            max_data_date = self.results_data[-1]['date']

            if start_d < min_data_date or end_d >= max_data_date:
                msg = (f"Khoảng ngày đã chọn ({start_s} - {end_s}) không hợp lệ.\n\n"
                       f"Dữ liệu có sẵn từ: {min_data_date:%d/%m/%Y} đến {max_data_date:%d/%m/%Y}.\n"
                       f"Ngày bắt đầu phải >= ngày đầu tiên của dữ liệu.\n"
                       f"Ngày kết thúc phải < ngày cuối cùng của dữ liệu ({max_data_date:%d/%m/%Y}).")
                QMessageBox.critical(main_window, "Lỗi Khoảng Ngày", msg)
                return None, None, None

        try:
            time_limit_min = self.opt_time_limit_spinbox.value()
            if time_limit_min <= 0:
                 QMessageBox.critical(main_window, "Lỗi Thời Gian", "Thời gian tối ưu tối đa phải lớn hơn 0 phút.")
                 return None, None, None
        except Exception as e:
             QMessageBox.critical(main_window, "Lỗi Thời Gian", f"Lỗi đọc giá trị thời gian tối ưu:\n{e}")
             return None, None, None

        return start_d, end_d, time_limit_min


    def _finalize_custom_steps_config_qt(self, original_params):

        # Only relevant if in auto/custom mode
        if self.current_optimization_mode != 'auto_hill_climb':
            return {}, False

        final_custom_steps_config = {}
        has_invalid_custom_steps = False
        invalid_params_details = []
        main_window = self.get_main_window()

        for name, widgets in self.advanced_opt_widgets.items():
            mode_combo = widgets.get('mode_combo')
            steps_entry = widgets.get('steps_entry')

            if not mode_combo or not steps_entry: continue

            mode = mode_combo.currentText()
            steps_str = steps_entry.text().strip()
            parsed_steps = []
            is_final_mode_custom = False
            param_state = self.optimizer_custom_steps.get(name, {'mode': 'Auto', 'steps': []})

            if mode == 'Custom':
                is_valid_syntax = self._validate_custom_steps_input_bool(steps_str)

                if is_valid_syntax and steps_str:
                    try:
                        original_value = original_params[name]
                        is_original_int = isinstance(original_value, int)
                        temp_parsed = []
                        for part in steps_str.split(','):
                            part = part.strip()
                            if part:
                                num_val = float(part)
                                if is_original_int:
                                    if num_val == int(num_val): temp_parsed.append(int(num_val))
                                    else: raise ValueError(f"Int param '{name}' step '{part}' invalid.")
                                else: temp_parsed.append(num_val)

                        if temp_parsed:
                             parsed_steps = sorted(list(set(temp_parsed)))
                             is_final_mode_custom = True
                        else:
                             has_invalid_custom_steps = True
                             invalid_params_details.append(f"{name} (bước trống hoặc toàn 0)")
                             optimizer_logger.warning(f"Custom steps for '{name}' resulted in empty list, defaulting to Auto.")


                    except (ValueError, KeyError, TypeError) as parse_err:
                        has_invalid_custom_steps = True
                        invalid_params_details.append(f"{name} (lỗi phân tích: {parse_err})")
                        optimizer_logger.warning(f"Error finalizing custom steps for {name}: {parse_err}")

                elif not is_valid_syntax and steps_str:
                    has_invalid_custom_steps = True
                    invalid_params_details.append(f"{name} (sai định dạng)")
                    optimizer_logger.warning(f"Invalid syntax for custom steps in '{name}', defaulting to Auto.")

                if has_invalid_custom_steps and is_final_mode_custom == False:
                    param_state['mode'] = 'Auto'
                    param_state['steps'] = []


            final_custom_steps_config[name] = {
                'mode': 'Custom' if is_final_mode_custom else 'Auto',
                'steps': parsed_steps if is_final_mode_custom else []
            }

            log_mode = final_custom_steps_config[name]['mode']
            log_steps = f", Steps={final_custom_steps_config[name]['steps']}" if log_mode == 'Custom' else ""
            optimizer_logger.info(f"Optimizer Start - Param '{name}': Final Mode={log_mode}{log_steps}")


        if has_invalid_custom_steps:
            QMessageBox.warning(main_window, "Bước Tùy Chỉnh Lỗi",
                                f"Một số cài đặt bước tùy chỉnh không hợp lệ và đã được đặt về chế độ 'Auto':\n\n- {', '.join(invalid_params_details)}\n\nKiểm tra lại định dạng và kiểu dữ liệu (số nguyên/thập phân).")

        return final_custom_steps_config, has_invalid_custom_steps

    def _start_optimization_worker_thread(self, display_name, start_date, end_date, time_limit_min,
                                          custom_steps_config, # Dùng cho auto/custom mode
                                          generation_params,   # Dùng cho combo mode
                                          combination_algos,
                                          initial_params=None, initial_score_tuple=None, is_resuming=False,
                                          mode='auto_hill_climb'): # Nhận mode từ start_optimization
        """
        Sets up the environment and starts the appropriate optimization worker thread
        based on the selected mode.
        """
        main_window = self.get_main_window()
        try:
            algo_data = self.loaded_algorithms[display_name]
        except KeyError:
            QMessageBox.critical(main_window, "Lỗi", f"Thuật toán '{display_name}' không tìm thấy khi bắt đầu tối ưu.")
            self.update_optimizer_ui_state() # Cập nhật UI về trạng thái chờ
            return

        # --- Thiết lập thư mục và log ---
        self.current_optimize_target_dir = self.optimize_dir / algo_data['path'].stem
        self.current_optimize_target_dir.mkdir(parents=True, exist_ok=True)
        success_dir = self.current_optimize_target_dir / "success"
        success_dir.mkdir(parents=True, exist_ok=True)
        self.current_optimization_log_path = self.current_optimize_target_dir / "optimization_qt.log"

        # --- Xóa log cũ và ghi thông tin bắt đầu ---
        if hasattr(self, 'opt_log_text'):
            self.opt_log_text.clear()
            if not is_resuming:
                 self._log_to_optimizer_display("INFO", "="*10 + " BẮT ĐẦU PHIÊN MỚI " + "="*10, tag="PROGRESS")
            else:
                 self._log_to_optimizer_display("INFO", "="*10 + " TIẾP TỤC PHIÊN " + "="*10, tag="RESUME")

            self._log_to_optimizer_display("INFO", f"Thuật toán đích: {display_name}", tag="INFO")
            self._log_to_optimizer_display("INFO", f"Thuật toán kết hợp: {combination_algos or '(Không có)'}", tag="COMBINE")
            self._log_to_optimizer_display("INFO", f"Khoảng ngày: {start_date:%d/%m/%Y} - {end_date:%d/%m/%Y}", tag="INFO")
            self._log_to_optimizer_display("INFO", f"Giới hạn thời gian: {time_limit_min} phút", tag="INFO")

            if mode == 'generated_combinations':
                # Lấy thông tin từ generation_params để ghi log chính xác hơn
                num_vals = generation_params.get('num_values', '?') if generation_params else '?'
                gen_meth = generation_params.get('method', '?') if generation_params else '?'
                self._log_to_optimizer_display("INFO", f"Chế độ: Tạo Bộ Tham Số (Worker sẽ tạo ~{num_vals} giá trị/{gen_meth})", tag="GEN_COMBO")
            else: # mode == 'auto_hill_climb'
                self._log_to_optimizer_display("INFO", "Chế độ: Tối ưu Tự động / Custom", tag="CUSTOM_STEP")
                # Log thêm chi tiết về custom steps nếu có
                if custom_steps_config:
                    for pname, pconfig in custom_steps_config.items():
                        if pconfig.get('mode') == 'Custom' and pconfig.get('steps'):
                            self._log_to_optimizer_display("DEBUG", f"  - Tham số '{pname}' (Custom): {pconfig['steps']}", tag="CUSTOM_STEP")

        # --- Xóa cache ---
        self._clear_cache_directory()

        # --- Reset trạng thái tối ưu ---
        self.optimizer_stop_event.clear()
        self.optimizer_pause_event.clear()
        self.optimizer_running = True
        self.optimizer_paused = False
        self.current_best_params = initial_params if is_resuming else None
        self.current_best_score_tuple = initial_score_tuple if is_resuming else (-1.0, -1.0, -1.0, -100.0)
        self.current_combination_algos = combination_algos
        # Lưu lại khoảng ngày dùng cho lần chạy này để lưu state nếu cần
        self.last_opt_range_start_str = start_date.strftime('%Y-%m-%d')
        self.last_opt_range_end_str = end_date.strftime('%Y-%m-%d')

        # --- Thiết lập thời gian và cập nhật UI ---
        self.opt_start_time = time.time()
        self.opt_time_limit_sec = time_limit_min * 60

        if hasattr(self, 'opt_progressbar'): self.opt_progressbar.setValue(0)
        if hasattr(self, 'opt_progress_label'): self.opt_progress_label.setText("0%")
        if hasattr(self, 'opt_time_static_label'): self.opt_time_static_label.setVisible(True)
        if hasattr(self, 'opt_time_remaining_label'):
            self.opt_time_remaining_label.setVisible(True)
            initial_time_str = time.strftime('%H:%M:%S' if self.opt_time_limit_sec >= 3600 else '%M:%S', time.gmtime(self.opt_time_limit_sec)) if self.opt_time_limit_sec >= 0 else "--:--:--"
            self.opt_time_remaining_label.setText(initial_time_str)

        self.update_optimizer_ui_state() # Cập nhật trạng thái các nút bấm, input fields

        # --- Chọn và chuẩn bị args cho luồng worker dựa trên mode ---
        optimizer_logger.info(f"Preparing worker thread for mode: {mode}")
        worker_target = None
        worker_args = () # Tuple trống mặc định

        if mode == 'auto_hill_climb':
            worker_target = self._optimization_worker
            # Args cho worker auto/custom: config steps tùy chỉnh được truyền vào
            worker_args = (
                display_name, start_date, end_date, self.opt_time_limit_sec,
                custom_steps_config, # Chứa thông tin mode (Auto/Custom) và steps cho từng param
                combination_algos,
                self.current_best_params, # initial_params đã được gán vào đây
                self.current_best_score_tuple # initial_score_tuple đã được gán vào đây
            )
            optimizer_logger.debug("Worker target set to _optimization_worker")
        elif mode == 'generated_combinations':
            worker_target = self._combination_optimization_worker
            # Args cho worker combo: generation_params được truyền vào để worker tự tạo list
            worker_args = (
                display_name, start_date, end_date, self.opt_time_limit_sec,
                generation_params, # Chứa original_params, num_values, method
                combination_algos,
                self.current_best_params, # Vẫn truyền, dù ít khi được dùng ở chế độ này
                self.current_best_score_tuple
            )
            optimizer_logger.debug("Worker target set to _combination_optimization_worker")
        else:
            main_logger.error(f"Invalid optimization mode '{mode}' cannot start worker thread.")
            QMessageBox.critical(main_window, "Lỗi Mode", f"Chế độ tối ưu không hợp lệ: {mode}")
            self.optimizer_running = False # Đặt lại cờ running
            self.update_optimizer_ui_state() # Reset UI về trạng thái chờ
            return

        # --- Tạo và khởi chạy luồng worker ---
        try:
            self.optimizer_thread = threading.Thread(
                target=worker_target,
                args=worker_args,
                name=f"Optimizer-{algo_data['path'].stem}-{mode}", # Thêm mode vào tên luồng cho dễ debug
                daemon=True
            )
            self.optimizer_thread.start()
            optimizer_logger.info(f"Optimizer worker thread '{self.optimizer_thread.name}' started.")
        except Exception as thread_start_err:
             main_logger.error(f"Failed to start optimizer worker thread: {thread_start_err}", exc_info=True)
             QMessageBox.critical(main_window, "Lỗi Luồng", f"Không thể bắt đầu luồng tối ưu:\n{thread_start_err}")
             self.optimizer_running = False
             self.update_optimizer_ui_state()
             return

        # --- Khởi động các timer kiểm tra queue và hiển thị thời gian ---
        if not self.optimizer_timer.isActive():
            self.optimizer_timer.start(self.optimizer_timer_interval)
        if not self.display_timer.isActive():
            self.display_timer.start(self.display_timer_interval)

        # --- Cập nhật status cuối cùng trước khi kết thúc hàm ---
        action_verb_status = "Tiếp tục" if is_resuming else "Bắt đầu"
        mode_desc = "Tạo Bộ Tham Số" if mode == 'generated_combinations' else "Tối ưu Tự động/Custom"
        self.update_status(f"Optimizer: {action_verb_status} {mode_desc} cho: {algo_data['class_name']}...")

    def pause_optimization(self):
        if self.optimizer_running and not self.optimizer_paused:
            self.optimizer_pause_event.set()
            self.optimizer_paused = True
            self.update_optimizer_ui_state()
            self.update_status("Optimizer: Đã tạm dừng.")
            self._log_to_optimizer_display("INFO", "[CONTROL] Tạm dừng tối ưu.", tag="WARNING")
            self._save_optimization_state(reason="paused")

    def resume_optimization(self):
        if self.optimizer_running and self.optimizer_paused:
            self.optimizer_pause_event.clear()
            self.optimizer_paused = False
            self.update_optimizer_ui_state()
            self.update_status("Optimizer: Tiếp tục tối ưu...")
            self._log_to_optimizer_display("INFO", "[CONTROL] Tiếp tục tối ưu.", tag="PROGRESS")

    def stop_optimization(self, force_stop=False):
        main_window = self.get_main_window()
        if self.optimizer_running:
            confirmed = force_stop
            if not force_stop:
                reply = QMessageBox.question(main_window, "Xác Nhận Dừng",
                                             "Bạn có chắc chắn muốn dừng quá trình tối ưu hóa không?\nKết quả tốt nhất hiện tại (nếu có) sẽ được lưu.",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    confirmed = True

            if confirmed:
                self._save_optimization_state(reason="stopped")
                self.optimizer_stop_event.set()

                if hasattr(self, 'opt_start_button'): self.opt_start_button.setEnabled(False)
                if hasattr(self, 'opt_resume_button'): self.opt_resume_button.setEnabled(False)
                if hasattr(self, 'opt_pause_button'):
                    self.opt_pause_button.setText("Đang dừng...")
                    self.opt_pause_button.setEnabled(False)
                if hasattr(self, 'opt_stop_button'): self.opt_stop_button.setEnabled(False)

                self.update_status("Optimizer: Đang yêu cầu dừng...")
                self._log_to_optimizer_display("WARNING", "[CONTROL] Yêu cầu dừng...", tag="WARNING")

                if self.optimizer_paused:
                    self.optimizer_pause_event.clear()

    def update_optimizer_ui_state(self):

        start_enabled, resume_enabled, pause_enabled, stop_enabled = False, False, False, False
        pause_text = "Tạm dừng"
        pause_callback = self.pause_optimization
        pause_style_obj_name = "WarningButton"

        if self.optimizer_running:
            start_enabled = False
            resume_enabled = False # Cannot resume while running
            stop_enabled = True
            if self.optimizer_paused:
                pause_enabled = True
                pause_text = "Tiếp tục"
                pause_callback = self.resume_optimization
            else:
                pause_enabled = True
                pause_text = "Tạm dừng"
                pause_callback = self.pause_optimization
        else: # Not running
            start_enabled = (self.selected_algorithm_for_optimize is not None)
            resume_enabled = self.can_resume # Only enable resume if not running and possible
            stop_enabled = False
            pause_enabled = False
            pause_text = "Tạm dừng"
            pause_callback = self.pause_optimization

            if hasattr(self, 'opt_status_label'): self.opt_status_label.setText("Trạng thái: Chờ")
            if hasattr(self, 'opt_time_remaining_label'): self.opt_time_remaining_label.setText("--:--:--")
            if hasattr(self, 'opt_time_static_label'): self.opt_time_static_label.setVisible(False)
            if hasattr(self, 'opt_time_remaining_label'): self.opt_time_remaining_label.setVisible(False)

            if self.optimizer_timer.isActive(): self.optimizer_timer.stop()
            if self.display_timer.isActive(): self.display_timer.stop()


        if hasattr(self, 'opt_start_button'): self.opt_start_button.setEnabled(start_enabled)
        if hasattr(self, 'opt_resume_button'): self.opt_resume_button.setEnabled(resume_enabled)
        if hasattr(self, 'opt_stop_button'): self.opt_stop_button.setEnabled(stop_enabled)
        if hasattr(self, 'opt_pause_button'):
            self.opt_pause_button.setEnabled(pause_enabled)
            self.opt_pause_button.setText(pause_text)
            self.opt_pause_button.setObjectName(pause_style_obj_name)
            try: self.opt_pause_button.clicked.disconnect()
            except TypeError: pass
            self.opt_pause_button.clicked.connect(pause_callback)
            self.main_app.apply_stylesheet() # Re-apply stylesheet for object name change

        settings_enabled = not self.optimizer_running

        # Enable/disable basic settings
        if hasattr(self, 'opt_start_date_edit'): self.opt_start_date_edit.setReadOnly(not settings_enabled)
        if hasattr(self, 'opt_start_date_button'): self.opt_start_date_button.setEnabled(settings_enabled)
        if hasattr(self, 'opt_end_date_edit'): self.opt_end_date_edit.setReadOnly(not settings_enabled)
        if hasattr(self, 'opt_end_date_button'): self.opt_end_date_button.setEnabled(settings_enabled)
        if hasattr(self, 'opt_time_limit_spinbox'): self.opt_time_limit_spinbox.setEnabled(settings_enabled)

        # Enable/disable optimization mode selection
        if hasattr(self, 'opt_mode_auto_radio'): self.opt_mode_auto_radio.setEnabled(settings_enabled)
        if hasattr(self, 'opt_mode_combo_radio'): self.opt_mode_combo_radio.setEnabled(settings_enabled)

        # Enable/disable combination generation settings (only if that mode is selected AND settings are enabled)
        is_combo_mode_selected = self.current_optimization_mode == 'generated_combinations'
        if hasattr(self, 'combo_gen_settings_widget'): self.combo_gen_settings_widget.setEnabled(settings_enabled and is_combo_mode_selected)

        # Enable/disable custom step parameter controls (only if that mode is selected AND settings are enabled)
        is_auto_mode_selected = self.current_optimization_mode == 'auto_hill_climb'
        if hasattr(self, 'param_scroll_widget_container'): self.param_scroll_widget_container.setEnabled(settings_enabled and is_auto_mode_selected)
        for name, widgets in self.advanced_opt_widgets.items():
             mode_combo = widgets.get('mode_combo')
             steps_entry = widgets.get('steps_entry')
             if mode_combo: mode_combo.setEnabled(settings_enabled and is_auto_mode_selected)
             if steps_entry:
                 is_custom_mode_for_param = mode_combo.currentText() == 'Custom' if mode_combo else False
                 steps_entry.setEnabled(settings_enabled and is_auto_mode_selected and is_custom_mode_for_param)

        # Enable/disable combination algorithm selection
        for name, chk in self.combination_selection_checkboxes.items():
            chk.setEnabled(settings_enabled)


    def _update_optimizer_timer_display(self):

        if not self.optimizer_running or not hasattr(self, 'opt_time_remaining_label'):
            if self.display_timer.isActive(): self.display_timer.stop()
            return

        if not hasattr(self, 'opt_start_time') or not hasattr(self, 'opt_time_limit_sec'):
             if self.display_timer.isActive(): self.display_timer.stop()
             return

        elapsed_time = time.time() - self.opt_start_time
        seconds_left = max(0, self.opt_time_limit_sec - elapsed_time)

        if seconds_left >= 0:
            time_str = time.strftime('%H:%M:%S' if seconds_left >= 3600 else '%M:%S', time.gmtime(seconds_left))
        else:
            time_str = "00:00"

        if hasattr(self, 'opt_time_remaining_label') and self.opt_time_remaining_label.isVisible():
            self.opt_time_remaining_label.setText(time_str)

    def _check_optimizer_queue(self):

        main_window = self.get_main_window()
        try:
            while not self.optimizer_queue.empty():
                message = self.optimizer_queue.get_nowait()
                msg_type = message.get("type")
                payload = message.get("payload")

                if msg_type == "log":
                    level = payload.get("level", "INFO")
                    text = payload.get("text", "")
                    tag = payload.get("tag", level.upper())
                    self._log_to_optimizer_display(level, text, tag)

                elif msg_type == "status":
                    if hasattr(self, 'opt_status_label'):
                         self.opt_status_label.setText(f"Trạng thái: {payload}")

                elif msg_type == "progress":
                    progress_val = 0.0
                    max_val = 100 # Default for percentage
                    text_override = None
                    if isinstance(payload, dict): # Handle combination mode progress
                        current = payload.get('current', 0)
                        total = payload.get('total', 1)
                        progress_val = int((current / total * 100) if total > 0 else 0)
                        text_override = f"{progress_val}% ({current}/{total})"
                    else: # Handle percentage progress
                        try: progress_val = int(float(payload) * 100.0)
                        except (ValueError, TypeError): pass

                    if hasattr(self, 'opt_progressbar'):
                         self.opt_progressbar.setRange(0, 100) # Always 0-100 for progress bar
                         self.opt_progressbar.setValue(progress_val)
                    if hasattr(self, 'opt_progress_label'):
                         self.opt_progress_label.setText(text_override if text_override else f"{progress_val}%")


                elif msg_type == "best_update":
                    self.current_best_params = payload.get("params")
                    self.current_best_score_tuple = payload.get("score_tuple", (-1.0, -1.0, -1.0, -100.0))

                elif msg_type == "finished":
                    if self.optimizer_timer.isActive(): self.optimizer_timer.stop()
                    if self.display_timer.isActive(): self.display_timer.stop()

                    self.optimizer_running = False
                    self.optimizer_paused = False
                    final_message_from_worker = payload.get("message", "Hoàn tất.")
                    success = payload.get("success", False)
                    reason = payload.get("reason", "completed")

                    if reason not in ["stopped", "paused"]:
                        self._save_optimization_state(reason=reason)

                    log_level, log_tag_prefix, msg_box_func, msg_box_title = "INFO", "[KẾT THÚC]", QMessageBox.information, "Kết Thúc Tối Ưu"
                    display_final_message = final_message_from_worker

                    if success:
                        log_level, log_tag_prefix = "BEST", "[HOÀN TẤT]"
                    elif reason == "time_limit":
                        log_level, log_tag_prefix = "BEST", "[HOÀN TẤT]"
                        time_limit_minutes_str = str(self.opt_time_limit_spinbox.value())
                        display_final_message = f"Đã hết thời gian tối ưu ({time_limit_minutes_str} phút)."
                        if self.current_best_params: display_final_message += " Kết quả tốt nhất đã được lưu."
                    elif reason == "stopped":
                        log_level, log_tag_prefix = "WARNING", "[ĐÃ DỪNG]"
                        display_final_message = "Quá trình tối ưu đã bị dừng bởi người dùng."
                        if self.current_best_params: display_final_message += " Kết quả tốt nhất đã được lưu."
                    elif reason == "no_improvement":
                         log_level, log_tag_prefix = "INFO", "[KẾT THÚC]"
                         display_final_message = "Quá trình tối ưu dừng do không có cải thiện thêm."
                         if self.current_best_params: display_final_message += " Kết quả tốt nhất đã được lưu."
                    elif reason == "no_params":
                        log_level, log_tag_prefix = "INFO", "[KẾT THÚC]"
                    elif reason == "resume_error" or reason == "initial_test_error":
                         log_level, log_tag_prefix, msg_box_func, msg_box_title = "ERROR", "[LỖI]", QMessageBox.warning, "Tối Ưu Kết Thúc Với Lỗi"
                    elif reason == "combo_mode_no_results":
                         log_level, log_tag_prefix, msg_box_func, msg_box_title = "WARNING", "[KẾT THÚC]", QMessageBox.warning, "Tối Ưu Kết Thúc"
                         display_final_message = "Hoàn thành kiểm tra các bộ tham số nhưng không có bộ nào cho kết quả hợp lệ."

                    else:
                        log_level, log_tag_prefix, msg_box_func, msg_box_title = "ERROR", "[LỖI]", QMessageBox.warning, "Tối Ưu Kết Thúc Với Lỗi"
                        display_final_message = f"Quá trình tối ưu kết thúc với lỗi (Lý do: {reason})."

                    self.update_status(f"Optimizer Kết thúc: {display_final_message.splitlines()[0]}")
                    self._log_to_optimizer_display(log_level, f"{log_tag_prefix} {display_final_message}", tag=log_level.upper())
                    if main_window: msg_box_func(main_window, msg_box_title, display_final_message)

                    if hasattr(self, 'opt_progressbar'): self.opt_progressbar.setValue(100)
                    if hasattr(self, 'opt_progress_label'): self.opt_progress_label.setText("100%")

                    self.check_resume_possibility()
                    self.update_optimizer_ui_state()

                    self.optimizer_thread = None
                    return

                elif msg_type == "error":
                    if self.optimizer_timer.isActive(): self.optimizer_timer.stop()
                    if self.display_timer.isActive(): self.display_timer.stop()

                    error_text = payload
                    self._log_to_optimizer_display("ERROR", f"[LỖI LUỒNG] {error_text}")
                    if main_window: QMessageBox.critical(main_window, "Lỗi Worker Tối Ưu", f"Đã xảy ra lỗi trong luồng tối ưu:\n\n{error_text}")
                    self.optimizer_running = False
                    self.update_optimizer_ui_state()
                    return

        except queue.Empty:
            pass
        except Exception as e:
            optimizer_logger.error(f"Error processing optimizer queue: {e}", exc_info=True)
            if self.optimizer_timer.isActive(): self.optimizer_timer.stop()
            if self.display_timer.isActive(): self.display_timer.stop()
            self.optimizer_running = False
            self.update_optimizer_ui_state()


    def _log_to_optimizer_display(self, level, text, tag=None):

        try:
            log_method = getattr(optimizer_logger, level.lower(), optimizer_logger.info)
            log_method(f"[OptimizerUI] {text}")

            if hasattr(self, 'opt_log_text'):
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                display_tag = tag if tag and tag in self.log_formats else level.upper()
                if display_tag == "CRITICAL": display_tag = "ERROR"
                log_format = self.log_formats.get(display_tag, self.log_formats["INFO"])

                cursor = self.opt_log_text.textCursor()
                cursor.movePosition(QTextCursor.End)
                full_log_line = f"{timestamp} [{level.upper()}] {text}\n"
                cursor.insertText(full_log_line, log_format)

                self.opt_log_text.ensureCursorVisible()

                if self.current_optimization_log_path:
                    try:
                        with open(self.current_optimization_log_path, "a", encoding="utf-8") as f:
                            f.write(f"{datetime.datetime.now().isoformat()} [{level.upper()}] {text}\n")
                    except IOError as log_write_err:
                        if not hasattr(self, '_log_write_error_logged'):
                            optimizer_logger.error(f"Failed to write to optimizer log file '{self.current_optimization_log_path}': {log_write_err}")
                            self._log_write_error_logged = True
            else:
                 if hasattr(self, '_log_write_error_logged'):
                     del self._log_write_error_logged

        except Exception as e:
             optimizer_logger.error(f"Error logging to optimizer display: {e}", exc_info=True)


    def _optimization_worker(self, target_display_name, start_date, end_date, time_limit_sec,
                             custom_steps_config, combination_algo_names,
                             initial_best_params=None, initial_best_score_tuple=None):
        # This worker handles the 'auto_hill_climb' mode (including custom steps)
        start_time = time.time()
        optimizer_worker_logger = logging.getLogger("OptimizerWorker")
        is_resuming = initial_best_params is not None and initial_best_score_tuple is not None
        optimizer_worker_logger.info(f"Starting Auto/Custom optimization worker (Resuming: {is_resuming})...")

        # --- Queue helper functions (same as before) ---
        def queue_log(level, text, tag=None):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                try: self.optimizer_queue.put({"type": "log", "payload": {"level": level, "text": text, "tag": tag}})
                except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (log): {q_err}")
        def queue_status(text):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "status", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (status): {q_err}")
        def queue_progress(value): # Accepts float 0.0 to 1.0
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "progress", "payload": min(max(0.0, value), 1.0)})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (progress): {q_err}")
        def queue_best_update(params, score_tuple):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "best_update", "payload": {"params": params, "score_tuple": score_tuple}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (best_update): {q_err}")
        def queue_finished(message, success=True, reason="finished"):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "finished", "payload": {"message": message, "success": success, "reason": reason}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (finished): {q_err}")
        def queue_error(text):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "error", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (error): {q_err}")
        # --- End Queue helper functions ---

        finish_reason = "completed"
        try:
            # --- Setup: Get algorithm data, source, parameters ---
            if target_display_name not in self.loaded_algorithms:
                 raise ValueError(f"Target algorithm '{target_display_name}' not loaded.")
            target_algo_data = self.loaded_algorithms[target_display_name]
            original_path = target_algo_data['path']; class_name = target_algo_data['class_name']
            original_params = target_algo_data['config'].get('parameters', {})
            try:
                source_code = original_path.read_text(encoding='utf-8')
            except Exception as read_err:
                raise RuntimeError(f"Failed to read source code for {original_path.name}: {read_err}")

            target_dir = self.current_optimize_target_dir
            params_to_optimize = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}
            param_names_ordered = list(params_to_optimize.keys())

            if not param_names_ordered:
                 queue_log("INFO", "Thuật toán đích không có tham số số học để tối ưu.")
                 queue_finished("Thuật toán đích không có tham số số học.", success=False, reason="no_params")
                 return
            # --- End Setup ---

            # --- Helper for running performance test ---
            def run_combined_perf_test_wrapper(target_params_test, combo_names, start_dt, end_dt):
                 return self.run_combined_performance_test(
                     target_display_name=target_display_name, target_algo_source=source_code, target_class_name=class_name,
                     target_params_to_test=target_params_test, combination_algo_display_names=combo_names,
                     test_start_date=start_dt, test_end_date=end_dt, optimize_target_dir=target_dir)

            def get_primary_score(perf_dict):
                 if not perf_dict: return (-1.0, -1.0, -1.0, -100.0)
                 return (perf_dict.get('acc_top_3_pct',0.0),
                         perf_dict.get('acc_top_5_pct',0.0),
                         perf_dict.get('acc_top_1_pct',0.0),
                         -perf_dict.get('avg_top10_repetition',100.0))
            # --- End Performance Test Helper ---

            current_best_params = {}
            current_best_perf = None
            current_best_score_tuple = initial_best_score_tuple if initial_best_score_tuple is not None else get_primary_score({})

            # --- Initial Performance Check (Original or Resumed) ---
            if is_resuming:
                queue_log("INFO", f"Tiếp tục tối ưu với tham số, điểm số đã tải.", tag="RESUME")
                current_best_params = initial_best_params.copy()
                queue_status("Kiểm tra hiệu suất tham số đã tải...")
                queue_progress(0.0)
                recalc_perf = run_combined_perf_test_wrapper(current_best_params, combination_algo_names, start_date, end_date)

                if self.optimizer_stop_event.is_set():
                    finish_reason = "stopped"
                    queue_log("WARNING", "Quá trình Tiếp tục tối ưu bị dừng trong khi tính toán lại hiệu suất.", tag="WARNING")
                    queue_finished("Dừng bởi người dùng trong khi tiếp tục.", success=False, reason=finish_reason)
                    return

                if recalc_perf is not None:
                    current_best_perf = recalc_perf
                    recalc_score = get_primary_score(recalc_perf)
                    if recalc_score != current_best_score_tuple:
                         queue_log("WARNING", f"Điểm tính lại ({recalc_score}) khác điểm tải ({initial_best_score_tuple}). Sử dụng điểm tính lại.", tag="WARNING")
                         current_best_score_tuple = recalc_score
                    queue_best_update(current_best_params, current_best_score_tuple)
                else:
                    queue_log("ERROR", "Lỗi khi kiểm tra lại hiệu suất của tham số đã tải.", tag="ERROR")
                    queue_finished("Lỗi kiểm tra lại hiệu suất tham số đã tải.", success=False, reason="resume_error")
                    return
            else:
                 queue_log("INFO", f"Bắt đầu tối ưu mới cho: {target_display_name}")
                 queue_status("Kiểm tra hiệu suất gốc...")
                 queue_progress(0.0)
                 initial_perf = run_combined_perf_test_wrapper(original_params, combination_algo_names, start_date, end_date)

                 if self.optimizer_stop_event.is_set():
                     finish_reason = "stopped"
                     queue_log("WARNING", "Quá trình tối ưu bị dừng trong khi kiểm tra hiệu suất gốc.", tag="WARNING")
                     queue_finished("Dừng bởi người dùng trong khi kiểm tra ban đầu.", success=False, reason=finish_reason)
                     return

                 if initial_perf is None:
                     queue_log("ERROR", "Lỗi kiểm tra hiệu suất ban đầu.", tag="ERROR")
                     queue_finished("Lỗi kiểm tra hiệu suất ban đầu.", success=False, reason="initial_test_error")
                     return

                 current_best_params = original_params.copy()
                 current_best_perf = initial_perf
                 current_best_score_tuple = get_primary_score(current_best_perf)
                 queue_log("INFO", f"Hiệu suất gốc: Top3={current_best_perf.get('acc_top_3_pct', 0.0):.2f}%, Top5={current_best_perf.get('acc_top_5_pct', 0.0):.2f}%, Top1={current_best_perf.get('acc_top_1_pct', 0.0):.2f}%, Lặp TB={current_best_perf.get('avg_top10_repetition', 0.0):.2f}")
                 queue_best_update(current_best_params, current_best_score_tuple)
            # --- End Initial Performance Check ---

            # --- Hill Climbing / Custom Step Optimization Loop ---
            MAX_ITERATIONS_PER_PARAM_AUTO = 10
            STALL_THRESHOLD = 2
            MAX_FULL_CYCLES = 5
            steps_done = 0

            for cycle in range(MAX_FULL_CYCLES):
                queue_log("INFO", f"--- Chu kỳ {cycle + 1}/{MAX_FULL_CYCLES} ---", tag="PROGRESS")
                params_changed_in_cycle = False

                for param_idx, param_name in enumerate(param_names_ordered):
                    if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                    while self.optimizer_pause_event.is_set():
                        if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                        time.sleep(0.5)
                    if finish_reason == "stopped": break
                    elapsed_time = time.time() - start_time
                    if elapsed_time >= time_limit_sec: finish_reason = "time_limit"; break

                    param_opt_config = custom_steps_config.get(param_name, {'mode': 'Auto', 'steps': []})
                    mode = param_opt_config['mode']
                    custom_steps = param_opt_config['steps']
                    original_value_for_turn = current_best_params[param_name]
                    is_float = isinstance(original_value_for_turn, float)

                    # -- Custom Step Mode --
                    if mode == 'Custom' and custom_steps:
                        queue_log("INFO", f"Tối ưu {param_name} (Chế độ: Custom, Các bước: {custom_steps})", tag="CUSTOM_STEP")
                        best_value_this_param = current_best_params[param_name]

                        for step_sign in [1, -1]:
                            for step_val in custom_steps:
                                if self.optimizer_stop_event.is_set(): finish_reason="stopped"; break
                                if time.time() - start_time >= time_limit_sec: finish_reason="time_limit"; break
                                if step_val == 0: continue

                                test_params = current_best_params.copy()
                                new_value = best_value_this_param + (step_sign * step_val)
                                test_params[param_name] = float(f"{new_value:.6g}") if is_float else int(round(new_value))

                                sign_char = '+' if step_sign > 0 else '-'
                                queue_status(f"Thử custom {sign_char}: {param_name}={test_params[param_name]} (bước {step_val})...")

                                perf_result = run_combined_perf_test_wrapper(test_params, combination_algo_names, start_date, end_date)
                                steps_done += 1
                                queue_progress(min(0.95, (time.time() - start_time) / time_limit_sec))

                                if self.optimizer_stop_event.is_set(): finish_reason="stopped"; break

                                if perf_result is not None:
                                    new_score = get_primary_score(perf_result)
                                    if new_score > current_best_score_tuple:
                                        queue_log("BEST", f"  -> Cải thiện ({sign_char} custom)! {param_name}={test_params[param_name]}. Score mới: {new_score}", tag="BEST")
                                        current_best_params = test_params.copy()
                                        current_best_perf = perf_result
                                        current_best_score_tuple = new_score
                                        best_value_this_param = new_value
                                        queue_best_update(current_best_params, current_best_score_tuple)
                                        params_changed_in_cycle = True
                                else:
                                    queue_log("WARNING", f"  -> Lỗi Test {sign_char} custom {param_name}={test_params[param_name]}.", tag="WARNING")
                            if finish_reason in ["stopped", "time_limit"]: break
                        if finish_reason in ["stopped", "time_limit"]: break
                    # -- End Custom Step Mode --

                    # -- Auto (Hill Climb) Mode --
                    else: # mode == 'Auto' or (mode == 'Custom' and not custom_steps)
                        step_base = abs(original_value_for_turn) * 0.05
                        if not is_float:
                            step = max(1, int(round(step_base)))
                        else:
                            if abs(original_value_for_turn) > 1e-9:
                                step = max(1e-6, step_base)
                            else:
                                step = 0.001
                        queue_log("INFO", f"Tối ưu {param_name} (Chế độ: Auto, Giá trị hiện tại={current_best_params[param_name]:.4g}, Bước ~ {step:.4g})", tag="PROGRESS")

                        for direction_sign in [1, -1]:
                            no_improve_streak = 0
                            params_at_dir_start = current_best_params.copy()
                            current_val_dir = params_at_dir_start[param_name]
                            dir_char = '+' if direction_sign > 0 else '-'; dir_text = 'tăng' if direction_sign > 0 else 'giảm'

                            for i in range(MAX_ITERATIONS_PER_PARAM_AUTO):
                                if self.optimizer_stop_event.is_set(): finish_reason="stopped"; break
                                if time.time() - start_time >= time_limit_sec: finish_reason="time_limit"; break

                                current_val_dir += (direction_sign * step)
                                test_params = params_at_dir_start.copy()
                                test_params[param_name] = float(f"{current_val_dir:.6g}") if is_float else int(round(current_val_dir))

                                queue_status(f"Thử {dir_text} (auto): {param_name}={test_params[param_name]:.4g}...")

                                perf_result = run_combined_perf_test_wrapper(test_params, combination_algo_names, start_date, end_date)
                                steps_done += 1
                                queue_progress(min(0.95, (time.time() - start_time) / time_limit_sec))

                                if self.optimizer_stop_event.is_set(): finish_reason="stopped"; break

                                if perf_result is not None:
                                    new_score = get_primary_score(perf_result)
                                    if new_score > current_best_score_tuple:
                                        queue_log("BEST", f"  -> Cải thiện ({dir_char} auto)! {param_name}={test_params[param_name]:.4g}. Score mới: {new_score}", tag="BEST")
                                        current_best_params = test_params.copy()
                                        params_at_dir_start = test_params.copy()
                                        current_val_dir = test_params[param_name]

                                        current_best_perf = perf_result
                                        current_best_score_tuple = new_score
                                        queue_best_update(current_best_params, current_best_score_tuple)
                                        params_changed_in_cycle = True
                                        no_improve_streak = 0
                                    else:
                                        no_improve_streak += 1
                                        queue_log("DEBUG", f"  -> Không cải thiện ({dir_char} auto) {param_name}={test_params[param_name]:.4g}. Streak: {no_improve_streak}")

                                    if no_improve_streak >= STALL_THRESHOLD:
                                        queue_log("DEBUG", f"    Dừng hướng {dir_char} cho {param_name} do không cải thiện {STALL_THRESHOLD} lần.")
                                        break
                                else:
                                    no_improve_streak += 1
                                    queue_log("WARNING", f"  -> Lỗi Test {dir_char} auto {param_name}={test_params[param_name]:.4g}. Streak: {no_improve_streak}", tag="WARNING")
                                    if no_improve_streak >= STALL_THRESHOLD:
                                        queue_log("DEBUG", f"    Dừng hướng {dir_char} cho {param_name} do lỗi test + không cải thiện.")
                                        break

                            if finish_reason in ["stopped", "time_limit"]: break
                        if finish_reason in ["stopped", "time_limit"]: break
                    # -- End Auto Mode --
                    if finish_reason in ["stopped", "time_limit"]: break # Break from param loop

                # Check stop/time limit after each parameter
                if finish_reason in ["stopped", "time_limit"]: break # Break from cycle loop

                # Check for stall after a full cycle
                if not params_changed_in_cycle and cycle > 0:
                    queue_log("INFO", f"Không có cải thiện nào trong chu kỳ {cycle + 1}. Dừng tối ưu.", tag="PROGRESS")
                    finish_reason = "no_improvement"
                    break
            # --- End Optimization Loop ---

            # --- Final Logging and Saving ---
            queue_progress(1.0)
            final_message = ""
            if finish_reason == "stopped": final_message = "Dừng bởi người dùng."
            elif finish_reason == "time_limit": final_message = f"Đã hết thời gian tối ưu ({time_limit_sec/60:.0f} phút)."
            elif finish_reason == "no_improvement": final_message = "Tối ưu dừng sớm do không cải thiện thêm."
            elif finish_reason == "no_params": final_message = "Thuật toán không có tham số để tối ưu."
            elif finish_reason == "resume_error": final_message = "Lỗi khi kiểm tra lại tham số đã tải."
            elif finish_reason == "initial_test_error": final_message = "Lỗi test hiệu suất ban đầu."
            elif finish_reason == "critical_error": final_message = "Lỗi nghiêm trọng trong worker."
            else: final_message = "Tối ưu hoàn tất."

            can_log_or_save = current_best_params is not None and finish_reason not in ["no_params", "resume_error", "initial_test_error", "critical_error"]

            if can_log_or_save:
                final_message += " Kết quả tốt nhất đã được lưu."
                queue_log("BEST", "="*10 + " TỐI ƯU KẾT THÚC " + "="*10, tag="BEST")
                queue_log("BEST", f"Lý do kết thúc: {finish_reason}", tag="BEST")
                queue_log("BEST", f"Tham số tốt nhất tìm được: {current_best_params}", tag="BEST")
                score_desc = "(Top3%, Top5%, Top1%, -AvgRepT10)"
                queue_log("BEST", f"Điểm số tốt nhất {score_desc}: ({', '.join(f'{s:.3f}' for s in current_best_score_tuple)})", tag="BEST")
                if current_best_perf:
                     queue_log("BEST", f"Chi tiết hiệu suất tốt nhất: Top3={current_best_perf.get('acc_top_3_pct',0.0):.2f}%, Top5={current_best_perf.get('acc_top_5_pct',0.0):.2f}%, Top1={current_best_perf.get('acc_top_1_pct',0.0):.2f}%, Lặp TB={current_best_perf.get('avg_top10_repetition',0.0):.2f}", tag="BEST")

                try:
                    final_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    success_dir = target_dir / "success"
                    success_dir.mkdir(parents=True, exist_ok=True)

                    perf_metric_for_name = current_best_perf.get('acc_top_3_pct', 0.0) if current_best_perf else 0.0
                    perf_str = f"top3_{perf_metric_for_name:.1f}"

                    success_filename_base = f"optimized_{target_algo_data['path'].stem}_{perf_str}_{final_timestamp}"

                    success_filename_py = success_filename_base + ".py"
                    final_py_path = success_dir / success_filename_py
                    final_mod_src = self.modify_algorithm_source_ast(source_code, class_name, current_best_params)
                    if final_mod_src:
                        final_py_path.write_text(final_mod_src, encoding='utf-8')
                    else:
                         queue_log("ERROR", "Lỗi khi tạo source code đã chỉnh sửa để lưu file .py cuối cùng.", tag="ERROR")


                    success_filename_json = success_filename_base + ".json"
                    final_json_path = success_dir / success_filename_json
                    final_save_data = {
                        "optimization_mode": "auto_hill_climb", # Indicate mode
                        "target_algorithm": target_display_name,
                        "params": current_best_params,
                        "performance": current_best_perf if current_best_perf else "N/A",
                        "score_tuple": list(current_best_score_tuple),
                        "combination_algorithms": combination_algo_names,
                        "optimization_range": f"{start_date:%Y-%m-%d}_to_{end_date:%Y-%m-%d}",
                        "optimization_duration_seconds": round(time.time() - start_time, 1),
                        "finish_reason": finish_reason,
                        "finish_timestamp": datetime.datetime.now().isoformat()
                    }
                    try:
                        final_json_path.write_text(json.dumps(final_save_data, indent=4, ensure_ascii=False), encoding='utf-8')
                        queue_log("BEST", f"Đã lưu kết quả tối ưu vào thư mục: {success_dir.relative_to(self.base_dir)}", tag="BEST")
                    except Exception as json_save_err:
                         queue_log("ERROR", f"Lỗi lưu file JSON kết quả cuối: {json_save_err}", tag="ERROR")
                         final_message += "\n(Lỗi lưu file JSON kết quả!)"

                except Exception as final_save_err:
                    queue_log("ERROR", f"Lỗi lưu kết quả cuối cùng: {final_save_err}", tag="ERROR")
                    final_message += "\n(Lỗi lưu file kết quả!)"
            elif not can_log_or_save and finish_reason not in ["no_params", "resume_error", "initial_test_error", "critical_error"]:
                 final_message = "Không tìm thấy tham số nào tốt hơn trạng thái bắt đầu hoặc đã xảy ra lỗi."
                 queue_log("INFO", "Không tìm thấy tham số tốt hơn hoặc đã xảy ra lỗi trong quá trình tối ưu.", tag="INFO")
            # --- End Final Logging and Saving ---

            is_successful_run = finish_reason in ["completed", "time_limit", "no_improvement"] and can_log_or_save

            queue_finished(final_message, success=is_successful_run, reason=finish_reason)

        except Exception as worker_err:
            finish_reason = "critical_error"
            optimizer_worker_logger.critical(f"Worker exception (Auto/Custom): {worker_err}", exc_info=True)
            queue_error(f"Lỗi nghiêm trọng trong luồng tối ưu: {worker_err}")
            queue_finished(f"Lỗi nghiêm trọng: {worker_err}", success=False, reason=finish_reason)

    def _combination_optimization_worker(self, target_display_name, start_date, end_date, time_limit_sec,
                                         generation_params, # Nhận dict chứa thông tin để tạo combinations
                                         combination_algo_names,
                                         initial_best_params=None, # Ít dùng nhưng giữ lại
                                         initial_best_score_tuple=None):
        """
        Worker thread for the 'Generated Combinations' optimization mode.
        Generates parameter combinations first, then tests their performance.
        """
        start_time = time.time()
        # Use a specific logger for this worker for clarity
        optimizer_worker_logger = logging.getLogger("OptimizerWorker.Combo")
        optimizer_worker_logger.info("Starting Generated Combinations optimization worker...")

        # --- Queue helper functions (định nghĩa các hàm nhỏ để gửi tín hiệu lên UI) ---
        def queue_log(level, text, tag=None):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                try: self.optimizer_queue.put({"type": "log", "payload": {"level": level, "text": text, "tag": tag}})
                except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (log): {q_err}")
        def queue_status(text):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "status", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (status): {q_err}")
        def queue_progress(current, total): # Format cho combo mode: gửi cả số hiện tại và tổng
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "progress", "payload": {"current": current, "total": total}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (progress): {q_err}")
        def queue_best_update(params, score_tuple):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "best_update", "payload": {"params": params, "score_tuple": score_tuple}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (best_update): {q_err}")
        def queue_finished(message, success=True, reason="finished"):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "finished", "payload": {"message": message, "success": success, "reason": reason}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (finished): {q_err}")
        def queue_error(text):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "error", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (error): {q_err}")
        # --- End Queue helper functions ---

        finish_reason = "completed" # Lý do kết thúc mặc định
        generated_combinations = [] # Danh sách combinations sẽ được tạo ở đây
        total_combinations = 0      # Tổng số combinations sẽ được cập nhật sau khi tạo
        current_best_params = None # Reset best params cho chế độ này
        current_best_perf = None
        # Bắt đầu từ điểm rất thấp để bất kỳ kết quả hợp lệ nào cũng tốt hơn
        current_best_score_tuple = (-1.0, -1.0, -1.0, -100.0)

        try:
            # --- Setup: Lấy thông tin thuật toán đích, source code ---
            optimizer_worker_logger.debug(f"Setting up worker for target: {target_display_name}")
            if target_display_name not in self.loaded_algorithms:
                 # Gửi lỗi nếu thuật toán không tìm thấy (dù đã kiểm tra trước đó)
                 raise ValueError(f"Target algorithm '{target_display_name}' not loaded in worker.")

            target_algo_data = self.loaded_algorithms[target_display_name]
            original_path = target_algo_data['path']
            class_name = target_algo_data['class_name']
            try:
                # Đọc mã nguồn của thuật toán gốc để có thể sửa đổi và chạy các phiên bản tạm thời
                source_code = original_path.read_text(encoding='utf-8')
                optimizer_worker_logger.debug(f"Successfully read source code for {original_path.name}")
            except Exception as read_err:
                raise RuntimeError(f"Worker failed to read source code for {original_path.name}: {read_err}")

            # Lấy đường dẫn thư mục tối ưu đã được tạo trước đó
            if not hasattr(self, 'current_optimize_target_dir') or not self.current_optimize_target_dir:
                 raise RuntimeError("Worker cannot determine optimize target directory.")
            target_dir = self.current_optimize_target_dir
            optimizer_worker_logger.debug(f"Using optimize target directory: {target_dir}")


            # === BƯỚC 1: TẠO BỘ THAM SỐ ===
            optimizer_worker_logger.info("Starting parameter combination generation phase...")
            queue_status("Đang tạo bộ tham số...")
            queue_log("INFO", "Bắt đầu tạo các bộ tham số kết hợp...", tag="GEN_COMBO")
            # Gửi tín hiệu progress ban đầu (0/1) để hiển thị thanh chạy trong lúc tạo
            queue_progress(0, 1)

            # Kiểm tra và lấy thông tin cần thiết để tạo combinations
            if not generation_params or not isinstance(generation_params, dict):
                raise ValueError("Worker received invalid generation_params.")
            orig_params_for_gen = generation_params.get('original_params')
            num_values_for_gen = generation_params.get('num_values')
            method_for_gen = generation_params.get('method')
            if not orig_params_for_gen or not num_values_for_gen or not method_for_gen:
                 raise ValueError("Worker missing detailed generation parameters (params, num_values, method).")
            optimizer_worker_logger.debug(f"Generation params: num_values={num_values_for_gen}, method='{method_for_gen}'")

            # Gọi hàm tạo combinations (hàm này sẽ chạy trong luồng worker này)
            generation_start_time = time.time()
            generated_combinations = self._generate_parameter_combinations(
                orig_params_for_gen, num_values_for_gen, method_for_gen
            )
            generation_duration = time.time() - generation_start_time
            optimizer_worker_logger.info(f"Parameter combination generation finished in {generation_duration:.2f} seconds.")

            # Kiểm tra kết quả tạo combinations
            if not generated_combinations:
                optimizer_worker_logger.error("Parameter generation returned an empty list.")
                queue_log("ERROR", "Không thể tạo bộ tham số nào (kết quả trống).", tag="ERROR")
                queue_finished("Tạo bộ tham số thất bại.", success=False, reason="combo_generation_failed")
                return # Kết thúc worker nếu không tạo được combinations

            # Cập nhật tổng số combinations và gửi thông báo/status
            total_combinations = len(generated_combinations)
            if total_combinations == 0: # Kiểm tra lại lần nữa phòng trường hợp logic _generate... có vấn đề
                 optimizer_worker_logger.error("Generated combinations list is empty after generation.")
                 queue_log("ERROR", "Danh sách bộ tham số rỗng sau khi tạo.", tag="ERROR")
                 queue_finished("Tạo bộ tham số thất bại (danh sách rỗng).", success=False, reason="combo_generation_failed_empty")
                 return

            queue_status(f"Đã tạo {total_combinations} bộ. Bắt đầu kiểm tra...")
            queue_log("INFO", f"Đã tạo thành công {total_combinations} bộ tham số.", tag="GEN_COMBO")
            # === KẾT THÚC TẠO BỘ THAM SỐ ===


            # --- Helper Functions cho Test Hiệu Suất ---
            # Định nghĩa hàm wrapper để gọi hàm test hiệu suất chính với các tham số cố định và thay đổi
            def run_combined_perf_test_wrapper(params_to_test_in_wrapper, combo_names_in_wrapper, start_dt_in_wrapper, end_dt_in_wrapper):
                 """Calls the main performance test function with necessary arguments."""
                 optimizer_worker_logger.debug(f"Calling run_combined_performance_test for params: {list(params_to_test_in_wrapper.keys())}")
                 # Truyền đầy đủ các tham số cần thiết cho hàm gốc
                 # Các giá trị như target_display_name, source_code, class_name, target_dir
                 # đã có sẵn trong scope của hàm worker này.
                 return self.run_combined_performance_test(
                     target_display_name=target_display_name,
                     target_algo_source=source_code,
                     target_class_name=class_name,
                     target_params_to_test=params_to_test_in_wrapper, # Tham số thay đổi
                     combination_algo_display_names=combo_names_in_wrapper,
                     test_start_date=start_dt_in_wrapper,
                     test_end_date=end_dt_in_wrapper,
                     optimize_target_dir=target_dir
                 )

            # Hàm tính điểm chính dựa trên kết quả performance (không đổi)
            def get_primary_score(perf_dict):
                 """Calculates the primary score tuple from performance dictionary."""
                 if not perf_dict: return (-1.0, -1.0, -1.0, -100.0)
                 # Ưu tiên Top3, Top5, Top1, sau đó là giảm thiểu lặp lại ở Top 10
                 return (perf_dict.get('acc_top_3_pct',0.0),
                         perf_dict.get('acc_top_5_pct',0.0),
                         perf_dict.get('acc_top_1_pct',0.0),
                         -perf_dict.get('avg_top10_repetition',100.0)) # Dấu trừ để tối thiểu hóa lặp lại
            # --- End Performance Test Helper ---


            # === BƯỚC 2: KIỂM TRA HIỆU SUẤT TỪNG BỘ ===
            optimizer_worker_logger.info(f"Starting performance testing for {total_combinations} parameter combinations...")
            # Reset progress bar về 0 cho giai đoạn kiểm tra
            queue_progress(0, total_combinations)

            # Vòng lặp qua từng bộ tham số đã tạo
            for idx, test_params in enumerate(generated_combinations):
                current_progress_idx = idx + 1 # Bắt đầu từ 1

                # --- Kiểm tra các tín hiệu điều khiển ---
                if self.optimizer_stop_event.is_set():
                    finish_reason = "stopped"
                    optimizer_worker_logger.info("Stop event detected during testing loop.")
                    break # Thoát khỏi vòng lặp for
                while self.optimizer_pause_event.is_set():
                    # Giữ trạng thái pause nếu đang pause
                    queue_status(f"Đã tạm dừng (đang ở bộ {current_progress_idx}/{total_combinations})")
                    if self.optimizer_stop_event.is_set():
                        finish_reason = "stopped"
                        optimizer_worker_logger.info("Stop event detected during pause.")
                        break # Thoát khỏi vòng lặp while
                    time.sleep(0.5) # Ngủ ngắn khi pause
                if finish_reason == "stopped":
                    break # Thoát khỏi vòng lặp for nếu đã stop trong lúc pause

                # --- Kiểm tra giới hạn thời gian ---
                elapsed_time = time.time() - start_time
                if elapsed_time >= time_limit_sec:
                    finish_reason = "time_limit"
                    optimizer_worker_logger.info("Time limit reached during testing loop.")
                    break # Thoát khỏi vòng lặp for

                # --- Cập nhật trạng thái và tiến trình ---
                queue_status(f"Kiểm tra bộ {current_progress_idx}/{total_combinations}...")
                queue_progress(current_progress_idx, total_combinations)

                # --- Thực hiện kiểm tra hiệu suất ---
                optimizer_worker_logger.debug(f"Running performance test for combination {current_progress_idx}")
                # Gọi hàm wrapper đã sửa lỗi
                perf_result = run_combined_perf_test_wrapper(
                    params_to_test_in_wrapper=test_params,
                    combo_names_in_wrapper=combination_algo_names,
                    start_dt_in_wrapper=start_date,
                    end_dt_in_wrapper=end_date
                )
                optimizer_worker_logger.debug(f"Performance test for combo {current_progress_idx} completed.")

                # Kiểm tra lại stop event ngay sau khi test xong (quan trọng nếu test lâu)
                if self.optimizer_stop_event.is_set():
                    finish_reason="stopped"
                    optimizer_worker_logger.info("Stop event detected immediately after performance test.")
                    break

                # --- Xử lý kết quả performance test ---
                if perf_result is not None:
                    new_score = get_primary_score(perf_result)
                    optimizer_worker_logger.debug(f"Combo {current_progress_idx} score: {new_score}")
                    # So sánh với điểm tốt nhất hiện tại
                    if new_score > current_best_score_tuple:
                        queue_log("BEST", f"Tìm thấy bộ tốt hơn! Bộ {current_progress_idx}/{total_combinations}. Score: {new_score}", tag="BEST")
                        optimizer_worker_logger.info(f"New best score found: {new_score} > {current_best_score_tuple} at index {idx}")
                        optimizer_worker_logger.debug(f"  Best Params Updated: {test_params}")
                        # Chỉ log params ở mức DEBUG để tránh làm đầy log
                        queue_log("DEBUG", f"  Params: {test_params}")

                        # Cập nhật giá trị tốt nhất
                        current_best_params = test_params.copy()
                        current_best_perf = perf_result
                        current_best_score_tuple = new_score
                        # Gửi tín hiệu cập nhật lên UI
                        queue_best_update(current_best_params, current_best_score_tuple)
                    else:
                        # Log ở mức DEBUG nếu không tốt hơn
                        optimizer_worker_logger.debug(f"Combination {current_progress_idx} score {new_score} not better than current best {current_best_score_tuple}")
                else:
                    # Log cảnh báo nếu test performance trả về None (lỗi)
                    queue_log("WARNING", f"Lỗi khi kiểm tra bộ tham số {current_progress_idx}.", tag="WARNING")
                    optimizer_worker_logger.warning(f"Performance test returned None for combination {current_progress_idx}.")

            # === KẾT THÚC VÒNG LẶP KIỂM TRA ===
            optimizer_worker_logger.info(f"Finished testing loop. Reason: {finish_reason}")

            # === BƯỚC 3: HOÀN TẤT VÀ LƯU KẾT QUẢ ===
            # Gửi tín hiệu progress cuối cùng để đảm bảo thanh chạy đến 100%
            queue_progress(total_combinations, total_combinations)

            # Xác định thông báo kết thúc dựa trên lý do dừng
            final_message = ""
            if finish_reason == "stopped":
                final_message = "Dừng bởi người dùng."
            elif finish_reason == "time_limit":
                final_message = f"Đã hết thời gian tối ưu ({time_limit_sec/60:.0f} phút)."
            elif finish_reason == "critical_error":
                final_message = "Lỗi nghiêm trọng trong worker." # Sẽ được ghi đè nếu lỗi xảy ra trong try-except này
            elif finish_reason == "combo_generation_failed":
                final_message = "Tạo bộ tham số thất bại."
            elif current_best_params is None: # Đã chạy xong nhưng không có kết quả nào tốt
                final_message = "Hoàn thành kiểm tra nhưng không tìm thấy bộ tham số nào cho kết quả hợp lệ."
                finish_reason = "combo_mode_no_results" # Cập nhật lý do chính xác hơn
            else: # finish_reason == 'completed' và có kết quả tốt nhất
                final_message = "Hoàn thành kiểm tra các bộ tham số."

            # Kiểm tra xem có kết quả để lưu không (chỉ lưu nếu có kết quả tốt nhất và không kết thúc do lỗi nghiêm trọng)
            can_log_or_save = current_best_params is not None and finish_reason not in [
                "critical_error", "combo_mode_no_results", "combo_generation_failed"
            ]

            if can_log_or_save:
                final_message += " Kết quả tốt nhất đã được lưu."
                # Ghi log tóm tắt kết quả tốt nhất
                queue_log("BEST", "="*10 + " TỐI ƯU KẾT THÚC (Bộ Tham Số) " + "="*10, tag="BEST")
                queue_log("BEST", f"Lý do kết thúc: {finish_reason}", tag="BEST")
                queue_log("BEST", f"Đã tạo và kiểm tra tổng cộng: {total_combinations} bộ", tag="BEST")
                queue_log("BEST", f"Tham số tốt nhất tìm được: {current_best_params}", tag="BEST")
                score_desc = "(Top3%, Top5%, Top1%, -AvgRepT10)"
                queue_log("BEST", f"Điểm số tốt nhất {score_desc}: ({', '.join(f'{s:.3f}' for s in current_best_score_tuple)})", tag="BEST")
                if current_best_perf:
                     # Log thêm chi tiết hiệu suất nếu có
                     queue_log("BEST", f"Chi tiết hiệu suất tốt nhất: Top3={current_best_perf.get('acc_top_3_pct',0.0):.2f}%, Top5={current_best_perf.get('acc_top_5_pct',0.0):.2f}%, Top1={current_best_perf.get('acc_top_1_pct',0.0):.2f}%, Lặp TB={current_best_perf.get('avg_top10_repetition',0.0):.2f}", tag="BEST")

                # --- Lưu file kết quả ---
                try:
                    optimizer_worker_logger.info("Saving best results found...")
                    final_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    success_dir = target_dir / "success" # Thư mục success đã được đảm bảo tồn tại
                    # Tạo tên file dựa trên kết quả
                    perf_metric_for_name = current_best_perf.get('acc_top_3_pct', 0.0) if current_best_perf else 0.0
                    perf_str = f"top3_{perf_metric_for_name:.1f}"
                    success_filename_base = f"optimized_combo_{target_algo_data['path'].stem}_{perf_str}_{final_timestamp}"
                    optimizer_worker_logger.debug(f"Base filename for saving: {success_filename_base}")

                    # Lưu file .py với tham số tốt nhất
                    success_filename_py = success_filename_base + ".py"
                    final_py_path = success_dir / success_filename_py
                    optimizer_worker_logger.debug(f"Attempting to save Python file: {final_py_path}")
                    final_mod_src = self.modify_algorithm_source_ast(source_code, class_name, current_best_params)
                    if final_mod_src:
                        final_py_path.write_text(final_mod_src, encoding='utf-8')
                        optimizer_worker_logger.info(f"Saved best parameters to Python file: {final_py_path.name}")
                    else:
                         queue_log("ERROR", "Lỗi khi tạo source code đã chỉnh sửa để lưu file .py cuối cùng.", tag="ERROR")
                         optimizer_worker_logger.error("Failed to generate modified source code for saving.")

                    # Lưu file .json với thông tin chi tiết
                    success_filename_json = success_filename_base + ".json"
                    final_json_path = success_dir / success_filename_json
                    optimizer_worker_logger.debug(f"Attempting to save JSON file: {final_json_path}")
                    final_save_data = {
                        "optimization_mode": "generated_combinations",
                        "target_algorithm": target_display_name,
                        "total_combinations_generated": total_combinations, # Thêm thông tin này
                        "params": current_best_params,
                        "performance": current_best_perf if current_best_perf else "N/A",
                        "score_tuple": list(current_best_score_tuple),
                        "combination_algorithms": combination_algo_names,
                        "optimization_range": f"{start_date:%Y-%m-%d}_to_{end_date:%Y-%m-%d}",
                        "optimization_duration_seconds": round(time.time() - start_time, 1),
                        "finish_reason": finish_reason,
                        "finish_timestamp": datetime.datetime.now().isoformat()
                    }
                    try:
                        # Ghi dữ liệu vào file JSON
                        final_json_path.write_text(json.dumps(final_save_data, indent=4, ensure_ascii=False), encoding='utf-8')
                        queue_log("BEST", f"Đã lưu kết quả tối ưu vào thư mục: {success_dir.relative_to(self.base_dir)}", tag="BEST")
                        optimizer_worker_logger.info(f"Saved optimization details to JSON file: {final_json_path.name}")
                    except Exception as json_save_err:
                         # Xử lý lỗi nếu không lưu được JSON
                         queue_log("ERROR", f"Lỗi lưu file JSON kết quả cuối: {json_save_err}", tag="ERROR")
                         optimizer_worker_logger.error(f"Failed to save JSON results file: {json_save_err}", exc_info=True)
                         final_message += "\n(Lỗi lưu file JSON kết quả!)"

                except Exception as final_save_err:
                    # Xử lý lỗi chung khi lưu file (ví dụ: không có quyền ghi)
                    queue_log("ERROR", f"Lỗi lưu kết quả cuối cùng: {final_save_err}", tag="ERROR")
                    optimizer_worker_logger.error(f"Error during final result saving: {final_save_err}", exc_info=True)
                    final_message += "\n(Lỗi lưu file kết quả!)"
            # --- Kết thúc lưu file ---

            # Xác định trạng thái thành công cuối cùng để gửi lên UI
            is_successful_run = finish_reason in ["completed", "time_limit"] and can_log_or_save
            optimizer_worker_logger.info(f"Worker sending finished signal. Success: {is_successful_run}, Reason: {finish_reason}")
            # Gửi tín hiệu hoàn tất cuối cùng
            queue_finished(final_message, success=is_successful_run, reason=finish_reason)

        except Exception as worker_err:
            # Xử lý các lỗi không mong muốn xảy ra trong toàn bộ quá trình của worker
            finish_reason = "critical_error" # Cập nhật lý do nếu có lỗi nghiêm trọng
            optimizer_worker_logger.critical(f"Worker encountered a critical exception: {worker_err}", exc_info=True)
            # Gửi tín hiệu lỗi và tín hiệu hoàn tất (với trạng thái lỗi)
            queue_error(f"Lỗi nghiêm trọng trong luồng tối ưu: {worker_err}")
            queue_finished(f"Lỗi nghiêm trọng: {worker_err}", success=False, reason=finish_reason)

        finally:
            optimizer_worker_logger.info("Combination optimization worker thread finished.")

    def _save_optimization_state(self, reason="unknown"):

        if not self.selected_algorithm_for_optimize or not self.current_optimize_target_dir or self.current_best_params is None:
            optimizer_logger.warning("Attempted to save state, but required info is missing.")
            return


        if self.current_optimization_mode == 'generated_combinations':
            optimizer_logger.info("Skipping state save for 'generated_combinations' mode.")
            return

        try:
            target_dir = self.current_optimize_target_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            algo_stem = self.loaded_algorithms[self.selected_algorithm_for_optimize]['path'].stem
            state_file_path = target_dir / f"optimization_state_{algo_stem}.json"

            start_date_str = getattr(self, 'last_opt_range_start_str', '')
            end_date_str = getattr(self, 'last_opt_range_end_str', '')
            optimization_range_str = f"{start_date_str}_to_{end_date_str}" if start_date_str and end_date_str else "unknown"

            state_data = {
                "target_algorithm": self.selected_algorithm_for_optimize,
                "params": self.current_best_params,
                "score_tuple": list(self.current_best_score_tuple),
                "combination_algorithms": self.current_combination_algos,
                "optimization_range": optimization_range_str,
                "save_reason": reason,
                "save_timestamp": datetime.datetime.now().isoformat()
            }
            state_file_path.write_text(json.dumps(state_data, indent=4, ensure_ascii=False), encoding='utf-8')
            self._log_to_optimizer_display("INFO", f"Đã lưu trạng thái tối ưu (Lý do: {reason}). File: {state_file_path.name}", tag="RESUME")
            self.check_resume_possibility()
        except Exception as e:
            self._log_to_optimizer_display("ERROR", f"Lỗi lưu trạng thái tối ưu: {e}", tag="ERROR")
            optimizer_logger.error(f"Error saving optimization state: {e}", exc_info=True)


    def run_combined_performance_test(self, target_display_name, target_algo_source, target_class_name,
                                       target_params_to_test, combination_algo_display_names,
                                       test_start_date, test_end_date, optimize_target_dir):
        target_instance = None
        combo_instances = {}
        temp_target_module_name = None
        temp_target_filepath = None
        worker_logger = logging.getLogger("OptimizerWorker.CombinedPerfTest")

        def queue_error_local(text):
             if hasattr(self, 'optimizer_queue') and isinstance(self.optimizer_queue, queue.Queue):
                 try: self.optimizer_queue.put({"type": "error", "payload": text})
                 except Exception as q_err: worker_logger.error(f"PerfTest: Failed to queue error '{text}': {q_err}")

        try:
            worker_logger.debug(f"Starting combined performance test for {target_class_name}")
            try:
                modified_source = self.modify_algorithm_source_ast(target_algo_source, target_class_name, target_params_to_test)
                if not modified_source:
                    raise RuntimeError("AST modification failed for performance test.")

                timestamp = int(time.time() * 10000) + random.randint(0, 9999)
                temp_target_filename = f"temp_perf_target_{target_class_name}_{timestamp}.py"
                temp_target_filepath = optimize_target_dir / temp_target_filename
                temp_target_filepath.write_text(modified_source, encoding='utf-8')

                optimize_target_dir.mkdir(parents=True, exist_ok=True)
                if not (optimize_target_dir / "__init__.py").exists():
                    (optimize_target_dir / "__init__.py").touch()
                if not (self.optimize_dir / "__init__.py").exists():
                    (self.optimize_dir / "__init__.py").touch()

                temp_target_module_name = f"optimize.{optimize_target_dir.name}.{temp_target_filename[:-3]}"

                worker_logger.debug(f"Importing temporary target module: {temp_target_module_name}")
                target_instance = self._import_and_instantiate_temp_algo(temp_target_filepath, temp_target_module_name, target_class_name)
                if not target_instance:
                    raise RuntimeError(f"Failed to load temporary target instance {target_class_name} from {temp_target_filepath}")
                worker_logger.debug(f"Successfully loaded temporary target instance.")

            except Exception as target_load_err:
                worker_logger.error(f"Failed loading TARGET {target_class_name} for perf test: {target_load_err}", exc_info=True)
                raise

            worker_logger.debug(f"Loading {len(combination_algo_display_names)} combination algorithms.")
            data_copy_for_combo = copy.deepcopy(self.results_data)
            for combo_name in combination_algo_display_names:
                if combo_name not in self.loaded_algorithms:
                    worker_logger.warning(f"Skipping unknown combination algorithm: {combo_name}")
                    continue
                try:
                     combo_data = self.loaded_algorithms[combo_name]
                     combo_instance = combo_data['instance'].__class__(
                         data_results_list=data_copy_for_combo,
                         cache_dir=self.calculate_dir
                     )
                     combo_instances[combo_name] = combo_instance
                     worker_logger.debug(f"Loaded combination instance: {combo_name}")
                except Exception as combo_load_err:
                     worker_logger.error(f"Failed loading COMBO instance {combo_name} for perf test: {combo_load_err}", exc_info=True)
                     if combo_name in combo_instances: del combo_instances[combo_name]

            worker_logger.debug(f"Starting performance loop from {test_start_date} to {test_end_date}")
            results_map = {r['date']: r['result'] for r in self.results_data}
            history_cache = {}
            sorted_results_for_cache = sorted(self.results_data, key=lambda x: x['date'])
            for i, r in enumerate(sorted_results_for_cache):
                 history_cache[r['date']] = sorted_results_for_cache[:i]

            stats = {'total_days_tested': 0, 'hits_top_1': 0, 'hits_top_3': 0, 'hits_top_5': 0, 'hits_top_10': 0, 'errors': 0, 'avg_top10_repetition': 0.0, 'max_top10_repetition_count': 0, 'top10_repetition_details': {}}
            all_top_10_combined_numbers = []

            current_date = test_start_date
            while current_date <= test_end_date:
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Performance test stopped by event.")
                    return None
                while self.optimizer_pause_event.is_set():
                    if self.optimizer_stop_event.is_set():
                        worker_logger.info("Performance test stopped during pause.")
                        return None
                    time.sleep(0.2)

                predict_date = current_date
                check_date = predict_date + datetime.timedelta(days=1)

                actual_result_dict = results_map.get(check_date)
                hist_data = history_cache.get(predict_date)

                if actual_result_dict is None or hist_data is None:
                    current_date += datetime.timedelta(days=1)
                    continue

                actual_numbers_set = set()
                if target_instance:
                    actual_numbers_set = target_instance.extract_numbers_from_dict(actual_result_dict)
                else:
                    worker_logger.error(f"Target instance is None for {predict_date}, cannot extract actual numbers.")
                    stats['errors'] += 1
                    current_date += datetime.timedelta(days=1)
                    continue

                if not actual_numbers_set:
                    stats['errors'] += 1
                    current_date += datetime.timedelta(days=1)
                    continue

                all_predictions_for_day = {}
                hist_copy_for_day = copy.deepcopy(hist_data)

                if target_instance:
                    try:
                        all_predictions_for_day[target_display_name] = target_instance.predict(predict_date, hist_copy_for_day)
                    except Exception as target_pred_err:
                        worker_logger.error(f"Error predicting TARGET {target_display_name} for {predict_date}: {target_pred_err}", exc_info=False)
                        all_predictions_for_day[target_display_name] = {}
                        stats['errors'] += 1
                else:
                    all_predictions_for_day[target_display_name] = {}
                    stats['errors'] += 1

                for combo_name, combo_inst in combo_instances.items():
                    try:
                        all_predictions_for_day[combo_name] = combo_inst.predict(predict_date, hist_copy_for_day)
                    except Exception as combo_pred_err:
                        worker_logger.error(f"Error predicting COMBO {combo_name} for {predict_date}: {combo_pred_err}", exc_info=False)
                        all_predictions_for_day[combo_name] = {}
                        stats['errors'] += 1

                combined_scores_raw = {f"{i:02d}": 0.0 for i in range(100)}
                valid_algo_count = 0

                for algo_name, scores_dict in all_predictions_for_day.items():
                    if not isinstance(scores_dict, dict) or not scores_dict:
                        continue

                    valid_algo_count += 1
                    for num_str, delta_val in scores_dict.items():
                        if isinstance(num_str, str) and len(num_str)==2 and num_str.isdigit():
                            try:
                                combined_scores_raw[num_str] += float(delta_val)
                            except (ValueError, TypeError):
                                worker_logger.warning(f"Invalid delta value '{delta_val}' for number '{num_str}' from {algo_name} on {predict_date}")
                                stats['errors'] += 1


                if valid_algo_count == 0:
                    stats['errors'] += 1
                    current_date += datetime.timedelta(days=1)
                    continue

                combined_scores_list = []
                base_score = 100.0
                for num_str, delta in combined_scores_raw.items():
                     try:
                         final_score = base_score + float(delta)
                         combined_scores_list.append((int(num_str), final_score))
                     except (ValueError, TypeError):
                         worker_logger.warning(f"Could not convert final score for '{num_str}' ({delta}) on {predict_date}")
                         stats['errors'] += 1

                if not combined_scores_list:
                    worker_logger.warning(f"No valid scores after combining for {predict_date}")
                    stats['errors'] += 1
                    current_date += datetime.timedelta(days=1)
                    continue

                sorted_preds = sorted(combined_scores_list, key=lambda x: x[1], reverse=True)

                pred_top_1 = {sorted_preds[0][0]} if sorted_preds else set()
                pred_top_3 = {p[0] for p in sorted_preds[:3]}
                pred_top_5 = {p[0] for p in sorted_preds[:5]}
                pred_top_10 = {p[0] for p in sorted_preds[:10]}

                if pred_top_1.intersection(actual_numbers_set): stats['hits_top_1'] += 1
                if pred_top_3.intersection(actual_numbers_set): stats['hits_top_3'] += 1
                if pred_top_5.intersection(actual_numbers_set): stats['hits_top_5'] += 1
                if pred_top_10.intersection(actual_numbers_set): stats['hits_top_10'] += 1

                all_top_10_combined_numbers.extend(list(pred_top_10))

                stats['total_days_tested'] += 1

                current_date += datetime.timedelta(days=1)

            total_tested = stats['total_days_tested']
            worker_logger.info(f"Performance loop finished. Total days successfully tested: {total_tested}")

            if total_tested > 0:
                stats['acc_top_1_pct'] = (stats['hits_top_1'] / total_tested) * 100.0
                stats['acc_top_3_pct'] = (stats['hits_top_3'] / total_tested) * 100.0
                stats['acc_top_5_pct'] = (stats['hits_top_5'] / total_tested) * 100.0
                stats['acc_top_10_pct'] = (stats['hits_top_10'] / total_tested) * 100.0

                if all_top_10_combined_numbers:
                    top10_counts = Counter(all_top_10_combined_numbers)
                    total_preds = len(all_top_10_combined_numbers)
                    unique_preds = len(top10_counts)
                    stats['avg_top10_repetition'] = total_preds / unique_preds if unique_preds > 0 else 0.0
                    stats['max_top10_repetition_count'] = max(top10_counts.values()) if top10_counts else 0
                    stats['top10_repetition_details'] = dict(top10_counts.most_common(5))
                else:
                    stats['avg_top10_repetition'] = 0.0
                    stats['max_top10_repetition_count'] = 0
                    stats['top10_repetition_details'] = {}
            else:
                stats['acc_top_1_pct'] = 0.0; stats['acc_top_3_pct'] = 0.0; stats['acc_top_5_pct'] = 0.0; stats['acc_top_10_pct'] = 0.0; stats['avg_top10_repetition'] = 0.0

            worker_logger.info(f"Performance test calculation complete. Stats: {stats}")
            return stats

        except Exception as e:
            worker_logger.error(f"Performance test failed critically: {e}", exc_info=True)
            queue_error_local(f"Lỗi nghiêm trọng trong quá trình kiểm tra hiệu suất: {e}")
            return None
        finally:
            worker_logger.debug("Cleaning up performance test resources.")
            target_instance = None
            combo_instances.clear()
            if temp_target_module_name and temp_target_module_name in sys.modules:
                try:
                    del sys.modules[temp_target_module_name]
                    worker_logger.debug(f"Removed temporary module: {temp_target_module_name}")
                except (KeyError, Exception) as del_err:
                     worker_logger.warning(f"Could not delete temp module {temp_target_module_name}: {del_err}")
            if temp_target_filepath and temp_target_filepath.exists():
                try:
                    temp_target_filepath.unlink()
                    worker_logger.debug(f"Deleted temporary file: {temp_target_filepath}")
                except OSError as unlink_err:
                    worker_logger.warning(f"Could not delete temp file {temp_target_filepath}: {unlink_err}")

    def _import_and_instantiate_temp_algo(self, temp_filepath, temp_module_name, class_name_hint):

        worker_logger = logging.getLogger("OptimizerWorker.ImportHelper")
        worker_logger.debug(f"Attempting to import {temp_module_name} from {temp_filepath}")
        instance = None
        module_obj = None
        try:
            if temp_module_name in sys.modules:
                try: del sys.modules[temp_module_name]
                except KeyError: pass
                worker_logger.debug(f"Removed existing module cache for {temp_module_name}")

            spec = util.spec_from_file_location(temp_module_name, temp_filepath)
            if not spec or not spec.loader:
                raise ImportError(f"Could not create module spec for {temp_module_name} at {temp_filepath}")

            module_obj = util.module_from_spec(spec)
            if module_obj is None:
                 raise ImportError(f"Could not create module from spec for {temp_module_name}")

            sys.modules[temp_module_name] = module_obj
            worker_logger.debug(f"Executing module {temp_module_name}")
            spec.loader.exec_module(module_obj)
            worker_logger.debug(f"Module {temp_module_name} executed.")

            temp_class = getattr(module_obj, class_name_hint, None)
            if not temp_class or not inspect.isclass(temp_class) or not issubclass(temp_class, BaseAlgorithm):
                 worker_logger.debug(f"Class hint '{class_name_hint}' not found or invalid. Searching module...")
                 for name, obj in inspect.getmembers(module_obj):
                     if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == temp_module_name:
                         temp_class = obj
                         worker_logger.debug(f"Found class '{name}' in {temp_module_name}")
                         break

            if not temp_class or not issubclass(temp_class, BaseAlgorithm):
                raise TypeError(f"No valid BaseAlgorithm subclass found in temporary module {temp_module_name}.")

            worker_logger.debug(f"Instantiating class {temp_class.__name__}")
            data_copy_for_instance = copy.deepcopy(self.results_data) if self.results_data else []
            instance = temp_class(data_results_list=data_copy_for_instance, cache_dir=self.calculate_dir)
            worker_logger.debug(f"Successfully instantiated {temp_class.__name__}")
            return instance

        except Exception as e:
            worker_logger.error(f"Import/Instantiate failed for {temp_filepath} (module: {temp_module_name}): {e}", exc_info=True)
            if temp_module_name and temp_module_name in sys.modules:
                try: del sys.modules[temp_module_name]
                except KeyError: pass
            return None

    def find_latest_successful_optimization(self, success_dir: Path, algo_stem: str):
        latest_file, latest_data, latest_timestamp = None, None, 0
        if success_dir.is_dir():
            try:
                # Look for both normal and combo optimized files
                patterns = [f"optimized_{algo_stem}_*_*.json", f"optimized_combo_{algo_stem}_*_*.json"]
                json_files = []
                for pattern in patterns:
                    json_files.extend(list(success_dir.glob(pattern)))
                optimizer_logger.debug(f"Scanning {success_dir} for patterns '{patterns}'. Found {len(json_files)} files.")

                for f_path in json_files:
                    try:
                        file_timestamp = 0
                        try:
                            parts = f_path.stem.split('_')
                            # Handle both naming conventions
                            file_ts_str = f"{parts[-2]}_{parts[-1]}"
                            file_dt = datetime.datetime.strptime(file_ts_str, "%Y%m%d_%H%M%S")
                            file_timestamp = file_dt.timestamp()
                        except (ValueError, IndexError, Exception):
                            file_timestamp = f_path.stat().st_mtime
                            optimizer_logger.debug(f"Using mtime {file_timestamp} for {f_path.name}")


                        if file_timestamp > latest_timestamp:
                             try:
                                 data = json.loads(f_path.read_text(encoding='utf-8'))
                                 # Check for required keys common to both modes
                                 if "params" in data and "score_tuple" in data and "optimization_range" in data and "combination_algorithms" in data:
                                     latest_timestamp = file_timestamp
                                     latest_file = f_path
                                     latest_data = data
                                     optimizer_logger.debug(f"Found newer valid result: {f_path.name} (ts: {file_timestamp})")
                                 else:
                                      optimizer_logger.warning(f"Skipping JSON {f_path.name}: Missing required keys.")
                             except json.JSONDecodeError:
                                 optimizer_logger.warning(f"Skipping invalid JSON file: {f_path.name}")
                             except Exception as read_err:
                                  optimizer_logger.warning(f"Error reading/parsing {f_path.name}: {read_err}")

                    except Exception as file_proc_err:
                         optimizer_logger.warning(f"Error processing file {f_path.name} in success dir: {file_proc_err}")
            except Exception as e:
                optimizer_logger.error(f"Error scanning success directory {success_dir}: {e}", exc_info=True)

        if latest_file:
            optimizer_logger.info(f"Latest successful optimization found: {latest_file.name}")
            # Do NOT use state file as fallback if a success file exists
            return latest_file, latest_data

        # Only check state file if NO success file was found
        optimizer_logger.debug("No success file found, checking for state file...")
        state_file_path = self.optimize_dir / algo_stem / f"optimization_state_{algo_stem}.json"
        if state_file_path.exists():
            optimizer_logger.debug(f"Found state file: {state_file_path.name}")
            try:
                 data = json.loads(state_file_path.read_text(encoding='utf-8'))
                 # Check for state file specific keys (or common keys if same format)
                 if "params" in data and "score_tuple" in data and "optimization_range" in data and "combination_algorithms" in data:
                     optimizer_logger.info(f"Using state file as fallback: {state_file_path.name}")
                     return state_file_path, data
                 else:
                     optimizer_logger.warning(f"State file {state_file_path.name} missing required keys.")
            except json.JSONDecodeError:
                 optimizer_logger.warning(f"State file {state_file_path.name} is invalid JSON.")
            except Exception as read_err:
                 optimizer_logger.warning(f"Error reading/parsing state file {state_file_path.name}: {read_err}")

        optimizer_logger.info("No suitable success or state file found.")
        return None, None

    def check_resume_possibility(self, event=None):

        target_algo = self.selected_algorithm_for_optimize
        can_resume_flag = False

        if target_algo and target_algo in self.loaded_algorithms:
            algo_data = self.loaded_algorithms[target_algo]
            algo_stem = algo_data['path'].stem
            optimize_target_dir = self.optimize_dir / algo_stem
            success_dir = optimize_target_dir / "success"
            latest_file, latest_data = self.find_latest_successful_optimization(success_dir, algo_stem)
            if latest_file and latest_data:
                # Check if the result was from 'auto_hill_climb' mode before enabling resume
                is_resumable_mode = latest_data.get('optimization_mode', 'auto_hill_climb') == 'auto_hill_climb'
                if is_resumable_mode:
                    can_resume_flag = True
                    optimizer_logger.debug(f"Resume possible for {target_algo} using file: {latest_file.name}")
                else:
                    optimizer_logger.debug(f"Found result file {latest_file.name}, but it's from 'generated_combinations' mode. Resume not applicable.")
            else:
                 optimizer_logger.debug(f"Resume not possible for {target_algo}: No valid file found.")

        self.can_resume = can_resume_flag

        if not self.optimizer_running:
            self.update_optimizer_ui_state()

    def update_status(self, message):

        optimizer_logger.info(f"Optimizer Status: {message}")
        if hasattr(self, 'opt_status_label'):
             self.opt_status_label.setText(f"Trạng thái: {message}")
             lower_msg = message.lower()
             if "lỗi" in lower_msg or "fail" in lower_msg:
                 self.opt_status_label.setStyleSheet("color: #dc3545;")
             elif "thành công" in lower_msg or "hoàn tất" in lower_msg:
                 self.opt_status_label.setStyleSheet("color: #28a745;")
             else:
                  self.opt_status_label.setStyleSheet("color: #6c757d;")
        else:
             optimizer_logger.warning("Optimizer status label not found.")


    def show_calendar_dialog_qt(self, target_line_edit: QLineEdit):

        if not self.results_data:
            QMessageBox.warning(self.get_main_window(), "Thiếu Dữ Liệu", "Chưa tải dữ liệu kết quả.")
            return

        min_date_dt = self.results_data[0]['date']
        max_date_dt = self.results_data[-1]['date']
        min_qdate = QDate(min_date_dt.year, min_date_dt.month, min_date_dt.day)
        max_qdate = QDate(max_date_dt.year, max_date_dt.month, max_date_dt.day)

        current_text = target_line_edit.text()
        current_qdate = QDate.currentDate()
        try:
            parsed_dt = datetime.datetime.strptime(current_text, '%d/%m/%Y').date()
            parsed_qdate = QDate(parsed_dt.year, parsed_dt.month, parsed_dt.day)
            if min_qdate <= parsed_qdate <= max_qdate:
                current_qdate = parsed_qdate
            else:
                 current_qdate = max_qdate
        except ValueError:
            current_qdate = max_qdate


        dialog = QDialog(self.get_main_window())
        dialog.setWindowTitle("Chọn Ngày")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setGridVisible(True)
        calendar.setMinimumDate(min_qdate)
        calendar.setMaximumDate(max_qdate)
        calendar.setSelectedDate(current_qdate)
        calendar.setStyleSheet("""
            QCalendarWidget QToolButton { color: black; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #E0E0E0; }
            QCalendarWidget QMenu { background-color: white; color: black; }
            QCalendarWidget QAbstractItemView:enabled { color: black; background-color: white; selection-background-color: #007BFF; selection-color: white; }
            QCalendarWidget QAbstractItemView:disabled { color: #CCCCCC; }
        """)

        layout.addWidget(calendar)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            selected_qdate = calendar.selectedDate()
            target_line_edit.setText(selected_qdate.toString("dd/MM/yyyy"))

    def _clear_cache_directory(self):

        cleared_count, error_count = 0, 0
        optimizer_logger.info(f"Clearing cache directory: {self.calculate_dir}")
        try:
            if self.calculate_dir.exists():
                for item in self.calculate_dir.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                            cleared_count += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            cleared_count += 1
                    except Exception as e:
                        optimizer_logger.error(f"Error removing cache item {item.name}: {e}")
                        error_count += 1
            if error_count > 0:
                 optimizer_logger.warning(f"Cache clear completed with {error_count} errors. Removed {cleared_count} items.")
            else:
                 optimizer_logger.info(f"Cache clear successful. Removed {cleared_count} items.")
        except Exception as e:
            optimizer_logger.error(f"Error accessing or iterating cache directory {self.calculate_dir}: {e}")

    def _load_optimization_log(self):

        if not self.selected_algorithm_for_optimize or self.selected_algorithm_for_optimize not in self.loaded_algorithms:
            return
        if not hasattr(self, 'opt_log_text'):
            return

        algo_data = self.loaded_algorithms[self.selected_algorithm_for_optimize]
        target_dir = self.optimize_dir / algo_data['path'].stem
        log_path = target_dir / "optimization_qt.log"
        self.current_optimization_log_path = log_path

        self.opt_log_text.clear()
        cursor = self.opt_log_text.textCursor()

        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue

                        tag = "INFO"
                        if "[ERROR]" in line or "[CRITICAL]" in line: tag = "ERROR"
                        elif "[WARNING]" in line: tag = "WARNING"
                        elif "[BEST]" in line: tag = "BEST"
                        elif "[DEBUG]" in line: tag = "DEBUG"
                        elif "[PROGRESS]" in line: tag = "PROGRESS"
                        elif "[CUSTOM_STEP]" in line: tag = "CUSTOM_STEP"
                        elif "[RESUME]" in line: tag = "RESUME"
                        elif "[COMBINE]" in line: tag = "COMBINE"
                        elif "[CONTROL]" in line: tag = "WARNING"
                        elif "[GEN_COMBO]" in line: tag = "GEN_COMBO"
                        elif line.startswith("==="): tag = "BEST" if "HOÀN TẤT" in line or "TỐI ƯU KẾT THÚC" in line else "PROGRESS"


                        log_format = self.log_formats.get(tag, self.log_formats["INFO"])
                        cursor.insertText(line + "\n", log_format)

                self.opt_log_text.moveCursor(QTextCursor.End)
            except Exception as e:
                cursor.insertText(f"LỖI ĐỌC LOG:\n{e}\n", self.log_formats["ERROR"])
                optimizer_logger.error(f"Error reading optimization log file {log_path}: {e}")
        else:
            cursor.insertText("Chưa có nhật ký tối ưu hóa cho thuật toán này.\n", self.log_formats["INFO"])

    def open_optimize_folder(self):

        target_dir_path = None
        main_window = self.get_main_window()

        if self.selected_algorithm_for_optimize and self.selected_algorithm_for_optimize in self.loaded_algorithms:
            algo_stem = self.loaded_algorithms[self.selected_algorithm_for_optimize]['path'].stem
            target_dir_path = self.optimize_dir / algo_stem
        else:
            target_dir_path = self.optimize_dir
            QMessageBox.information(main_window, "Thông Báo", f"Mở thư mục tối ưu chính:\n{target_dir_path}")

        if not target_dir_path: return

        try:
            target_dir_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(main_window, "Lỗi", f"Không thể tạo hoặc truy cập thư mục:\n{target_dir_path}\n\nLỗi: {e}")
            return

        url = QtCore.QUrl.fromLocalFile(str(target_dir_path.resolve()))
        if not QtGui.QDesktopServices.openUrl(url):
            QMessageBox.critical(main_window, "Lỗi", f"Không thể mở thư mục:\n{target_dir_path}")

    def _generate_parameter_combinations(self, original_params, num_values_per_param, method):
        """Generates parameter value sets and their combinations."""
        numeric_params = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}
        if not numeric_params:
            optimizer_logger.warning("No numeric parameters found for combination generation.")
            return []

        all_param_value_lists = []
        param_names_ordered = list(numeric_params.keys())

        for name in param_names_ordered:
            orig_val = numeric_params[name]
            values = self._generate_single_parameter_values(name, orig_val, num_values_per_param, method)
            if not values:
                optimizer_logger.error(f"Failed to generate values for parameter '{name}'. Aborting combination generation.")
                return []
            all_param_value_lists.append(values)
            optimizer_logger.debug(f"Generated values for '{name}': {values}")

        combinations_iter = itertools.product(*all_param_value_lists)
        param_combinations_list = []
        for combo_values in combinations_iter:
            param_dict = original_params.copy() # Start with all params
            param_dict.update(dict(zip(param_names_ordered, combo_values))) # Update numeric ones
            param_combinations_list.append(param_dict)

        optimizer_logger.info(f"Total combinations generated: {len(param_combinations_list)}")
        return param_combinations_list

    def _generate_single_parameter_values(self, param_name, original_value, num_values, method):
        """Generates a list of N values for a single parameter."""
        values = set()
        is_float = isinstance(original_value, float)

        if method == "random":
            # Define a range for random values (e.g., +/- 20% or a fixed range for small values)
            deviation = abs(original_value) * 0.2 if abs(original_value) > 1e-3 else 0.5
            if not is_float:
                 deviation = max(1, int(round(deviation))) # Ensure integer deviation is at least 1
            min_val = original_value - deviation
            max_val = original_value + deviation

            # Add original value first to ensure it's included
            values.add(original_value)

            while len(values) < num_values:
                if is_float:
                    rand_val = random.uniform(min_val, max_val)
                    # Round floats to a reasonable precision to avoid tiny differences
                    rand_val = float(f"{rand_val:.6g}")
                else:
                    rand_val = random.randint(int(round(min_val)), int(round(max_val)))
                values.add(rand_val)
                if len(values) >= num_values * 5 and len(values) < num_values : # Safety break if struggling to find unique values
                    optimizer_logger.warning(f"Struggling to generate {num_values} unique random values for '{param_name}' near {original_value}. Using {len(values)}.")
                    break


        elif method == "adjacent":
            values.add(original_value)
            num_each_side = (num_values - 1) // 2
            num_increase = num_each_side + ((num_values - 1) % 2) # Add extra if odd total
            num_decrease = num_each_side

            if is_float:
                step = max(abs(original_value) * 0.02, 1e-4) # Smaller step for floats
            else:
                step = 1 # Integer step

            # Generate increasing values
            current_val = original_value
            for _ in range(num_increase):
                current_val += step
                val_to_add = float(f"{current_val:.6g}") if is_float else int(round(current_val))
                values.add(val_to_add)

            # Generate decreasing values
            current_val = original_value
            for _ in range(num_decrease):
                current_val -= step
                val_to_add = float(f"{current_val:.6g}") if is_float else int(round(current_val))
                values.add(val_to_add)

        else:
            optimizer_logger.error(f"Unknown generation method: {method}")
            return []

        # Sort the results for consistency, especially for 'adjacent'
        return sorted(list(values))


class LotteryPredictionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lottery Predictor (v4.2.simple-ui - PyQt5)")
        main_logger.info("Initializing LotteryPredictionApp (PyQt5)...")

        self.font_family_base = 'Segoe UI'  # Default
        self.font_size_base = 10            # Default
        try:
            self.available_fonts = sorted(QFontDatabase().families())
            if not self.available_fonts: # Handle case where QFontDatabase returns empty
                main_logger.warning("QFontDatabase().families() returned an empty list. Using fallback font list.")
                # Provide a basic fallback list if Qt fails to provide system fonts
                self.available_fonts = ['Arial', 'Times New Roman', 'Courier New', 'Segoe UI', 'Tahoma', 'Verdana']
        except Exception as e_font_db:
            main_logger.error(f"Error initializing QFontDatabase().families(): {e_font_db}. Using fallback font list.", exc_info=True)
            self.available_fonts = ['Arial', 'Times New Roman', 'Courier New', 'Segoe UI', 'Tahoma', 'Verdana']
        # --- MODIFICATION END ---

        self.base_dir = Path(__file__).parent.resolve()
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.base_dir / "config"
        self.calculate_dir = self.base_dir / "calculate"
        self.algorithms_dir = self.base_dir / "algorithms"
        self.optimize_dir = self.base_dir / "optimize"
        self.tools_dir = self.base_dir / "tools"
        self.settings_file_path = self.config_dir / "settings.ini"

        self.config = configparser.ConfigParser(interpolation=None) # Initialize here

        self.results = []
        self.selected_date = None
        self.algorithms = {}
        self.algorithm_instances = {}
        self.loaded_tools = {} # Already added from previous step

        # self.font_family_base = 'Segoe UI' # MOVED UP
        # self.font_size_base = 10       # MOVED UP

        self.calculation_queue = queue.Queue()
        self.perf_queue = queue.Queue()
        self.calculation_threads = []
        self.intermediate_results = {}
        self._results_lock = threading.Lock()
        self.prediction_running = False
        self.performance_calc_running = False

        self.prediction_timer = QTimer(self)
        self.prediction_timer.timeout.connect(self.check_predictions_completion_qt)
        self.prediction_timer_interval = 200

        self.performance_timer = QTimer(self)
        self.performance_timer.timeout.connect(self._check_perf_queue)
        self.performance_timer_interval = 200

        self.optimizer_app_instance = None
        # self.available_fonts = sorted(QFontDatabase().families()) # MOVED UP

        self.create_directories()
        self._setup_validators()

        self.load_config() # Now calls after font attributes are definitely set
        self._setup_global_font() # Uses the now-set font attributes
        self.setup_main_ui_structure()
        self.apply_stylesheet()
        self._apply_window_size_from_config()

        self._populate_settings_tab_ui()

        self.load_data()
        self.load_algorithms()
        self.load_tools()

        if hasattr(self, 'optimizer_tab_frame'):
            try:
                self.optimizer_app_instance = OptimizerEmbedded(self.optimizer_tab_frame, self.base_dir, self)
                opt_layout = QVBoxLayout(self.optimizer_tab_frame)
                opt_layout.setContentsMargins(0,0,0,0)
                opt_layout.addWidget(self.optimizer_app_instance)
            except Exception as opt_init_err:
                main_logger.error(f"Failed to initialize OptimizerEmbedded: {opt_init_err}", exc_info=True)
                opt_error_layout = QVBoxLayout(self.optimizer_tab_frame)
                error_label = QLabel(f"Lỗi khởi tạo Optimizer:\n{opt_init_err}")
                error_label.setStyleSheet("color: #dc3545; padding: 20px;")
                error_label.setWordWrap(True)
                opt_error_layout.addWidget(error_label, alignment=Qt.AlignCenter)

        # self.populate_theme_settings_ui() # This is called within _populate_settings_tab_ui or should be updated if separate
        self.update_status("Ứng dụng sẵn sàng.")
        QTimer.singleShot(200, self._log_actual_window_size)

        main_logger.info("LotteryPredictionApp (PyQt5) initialization complete.")
        self.show()

    def _setup_global_font(self):

        try:
             qfont = self.get_qfont("base")
             QApplication.setFont(qfont)
             style_logger.info(f"Applied application font: {qfont.family()} {qfont.pointSize()}pt")
        except Exception as e:
             style_logger.error(f"Failed to set global application font: {e}", exc_info=True)

    def _setup_validators(self):

         self.dimension_validator = QIntValidator(1, 9999)
         self.weight_validator = QDoubleValidator()
         self.weight_validator.setNotation(QDoubleValidator.StandardNotation)


    def setup_main_ui_structure(self):

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("MainTabWidget")

        self.main_tab_frame = QWidget()
        self.optimizer_tab_frame = QWidget()
        self.tools_tab_frame = QWidget()
        self.settings_tab_frame = QWidget()
        self.info_tab_frame = QWidget()

        self.tab_widget.addTab(self.main_tab_frame, " Main 🏠")
        self.tab_widget.addTab(self.optimizer_tab_frame, " Tối ưu 🚀 ")
        self.tab_widget.addTab(self.tools_tab_frame, " Công Cụ 🛠️")
        self.tab_widget.addTab(self.settings_tab_frame, " Cài Đặt⚙️ ")

        main_layout.addWidget(self.tab_widget)

        self.setup_main_tab()
        self.setup_tools_tab()
        self.setup_settings_tab()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar_label = QLabel("Khởi tạo...")
        self.status_bar_label.setObjectName("StatusBarLabel")
        self.status_bar.addWidget(self.status_bar_label, 1)

        try:
            icon_path = self.config_dir / "logo.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                main_logger.info(f"Application icon set from {icon_path}")
        except Exception as e_icon:
            main_logger.warning(f"Error setting application icon: {e_icon}")


    def _log_actual_window_size(self):
        try:
            if self:
                main_logger.info(f"Window size: {self.width()}x{self.height()}, Geometry: {self.geometry().x()},{self.geometry().y()},{self.geometry().width()},{self.geometry().height()}")
        except Exception as e:
            main_logger.error(f"Error logging window size: {e}")

    def create_directories(self):
        try:
            for directory in [self.data_dir, self.config_dir, self.calculate_dir, self.algorithms_dir, self.optimize_dir, self.tools_dir]: # MODIFIED
                directory.mkdir(parents=True, exist_ok=True)
            for dir_path in [self.algorithms_dir, self.optimize_dir, self.tools_dir]: # MODIFIED
                init_file = dir_path / "__init__.py"
                if not init_file.exists():
                    init_file.touch()
            sample_data_file = self.data_dir / "xsmb-2-digits.json"
            if not sample_data_file.exists():
                main_logger.info(f"Creating sample data file: {sample_data_file}")
                today = datetime.date.today(); yesterday = today - datetime.timedelta(days=1)
                sample_data = [{'date': yesterday.strftime('%Y-%m-%d'), 'result': {'special': f"{random.randint(0,99999):05d}", 'prize1': f"{random.randint(0,99999):05d}", 'prize7_1': f"{random.randint(0,99):02d}"}},
                               {'date': today.strftime('%Y-%m-%d'), 'result': {'special': f"{random.randint(0,99999):05d}", 'prize1': f"{random.randint(0,99999):05d}", 'prize7_1': f"{random.randint(0,99):02d}"}}]
                try:
                    sample_data_file.write_text(json.dumps(sample_data, ensure_ascii=False, indent=2), encoding='utf-8')
                except IOError as e:
                    main_logger.error(f"Cannot write sample data file {sample_data_file}: {e}")
        except Exception as e:
             main_logger.error(f"Error creating directories: {e}", exc_info=True)





    def load_ui_theme_config(self):
        style_logger.info(f"Loading UI font theme from: {self.ui_theme_file_path}")
        self.ui_theme_config = configparser.ConfigParser(interpolation=None)
        defaults = self.get_default_theme_settings()
        try:
            if self.ui_theme_file_path.exists():
                self.ui_theme_config.read(self.ui_theme_file_path, encoding='utf-8')

            font_section = 'Fonts'
            if not self.ui_theme_config.has_section(font_section):
                self.ui_theme_config.add_section(font_section)

            self.font_family_base = self.ui_theme_config.get(
                font_section, 'family_base', fallback=defaults['Fonts']['family_base']
            )
            self.font_size_base = self.ui_theme_config.getint(
                font_section, 'size_base', fallback=defaults['Fonts']['size_base']
            )
            style_logger.info(f"UI font settings loaded: Family='{self.font_family_base}', Size={self.font_size_base}")

        except (configparser.Error, ValueError, TypeError) as e:
            style_logger.error(f"Error reading UI theme (fonts) from {self.ui_theme_file_path}: {e}. Using defaults.", exc_info=True)
            self.set_default_theme_values()

    def set_default_theme_values(self):
        style_logger.warning("Setting instance font variables to default.")
        defaults = self.get_default_theme_settings()
        self.font_family_base = defaults['Fonts']['family_base']
        self.font_size_base = defaults['Fonts']['size_base']

    def get_default_theme_settings(self) -> dict:
        return {
            'Fonts': {
                'family_base': 'Segoe UI',
                'size_base': 10,
            }
        }

    def save_ui_theme_config(self):
        style_logger.info(f"Saving UI font settings to: {self.ui_theme_file_path}")
        config_to_save = configparser.ConfigParser(interpolation=None)
        try:
            font_section = 'Fonts'
            config_to_save.add_section(font_section)
            config_to_save.set(font_section, 'family_base', self.theme_font_family_base_combo.currentText())
            config_to_save.set(font_section, 'size_base', str(self.theme_font_size_base_spinbox.value()))

            with open(self.ui_theme_file_path, 'w', encoding='utf-8') as configfile:
                config_to_save.write(configfile)

            QMessageBox.information(self, "Lưu Thành Công", "Đã lưu cài đặt font chữ.\nVui lòng khởi động lại ứng dụng để áp dụng thay đổi.")
            self.load_ui_theme_config()

        except (configparser.Error, ValueError, TypeError, IOError) as e:
            QMessageBox.critical(self, "Lỗi Lưu Font", f"Không thể lưu cài đặt font chữ:\n{e}")


    def reset_ui_theme_config(self):
        style_logger.warning("Resetting UI font theme to default.")
        reply = QMessageBox.question(self, "Xác Nhận",
                                     "Khôi phục cài đặt font chữ về mặc định?\nThao tác này sẽ xóa file 'ui_theme.ini' (nếu có) và yêu cầu khởi động lại ứng dụng để áp dụng.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if self.ui_theme_file_path.exists():
                    self.ui_theme_file_path.unlink()
                    style_logger.info(f"Deleted font theme file: {self.ui_theme_file_path}")

                self.set_default_theme_values()
                self.populate_theme_settings_ui()

                QMessageBox.information(self, "Khôi Phục Font", "Đã xóa cài đặt font chữ tùy chỉnh.\nVui lòng khởi động lại ứng dụng để sử dụng font mặc định.")
            except OSError as e:
                QMessageBox.critical(self, "Lỗi Xóa File", f"Không thể xóa file cấu hình font:\n{e}")
            except Exception as e:
                 QMessageBox.critical(self, "Lỗi Khôi Phục", f"Đã xảy ra lỗi khi khôi phục font:\n{e}")


    def populate_theme_settings_ui(self):

        style_logger.debug("Populating font settings UI elements.")
        try:
            if hasattr(self, 'theme_font_family_base_combo'):
                self.theme_font_family_base_combo.setCurrentText(self.font_family_base)
            if hasattr(self, 'theme_font_size_base_spinbox'):
                self.theme_font_size_base_spinbox.setValue(self.font_size_base)
        except Exception as e:
            style_logger.error(f"Error populating theme UI: {e}", exc_info=True)

    def apply_stylesheet(self):

        style_logger.debug("Applying application stylesheet...")
        try:
            COLOR_PRIMARY = '#007BFF'; COLOR_PRIMARY_DARK = '#0056b3'
            COLOR_SECONDARY = '#6c757d'; COLOR_SUCCESS = '#28a745'; COLOR_SUCCESS_DARK = '#1e7e34'
            COLOR_WARNING = '#ffc107'; COLOR_DANGER = '#dc3545'; COLOR_INFO = '#17a2b8'
            COLOR_TEXT_DARK = '#212529'; COLOR_TEXT_LIGHT = '#FFFFFF'
            COLOR_BG_LIGHT = '#FFFFFF'; COLOR_BG_WHITE = '#FFFFFF'; COLOR_BG_LIGHT_ALT = '#FAFAFA'
            COLOR_BG_HIT = '#d4edda'; COLOR_BG_SPECIAL = '#fff3cd'
            COLOR_ACCENT_PURPLE = '#6f42c1'; COLOR_TOOLTIP_BG = '#FFFFE0'
            COLOR_DISABLED_BG = '#e9ecef'; COLOR_DISABLED_FG = '#6c757d'; COLOR_BORDER = '#ced4da'
            COLOR_TAB_FG = COLOR_SUCCESS_DARK; COLOR_TAB_SELECTED_FG = COLOR_PRIMARY_DARK
            COLOR_TAB_BG = COLOR_BG_LIGHT; COLOR_TAB_SELECTED_BG = COLOR_BG_WHITE
            COLOR_TAB_INACTIVE_BG = '#E9E9E9'
            PB_TROUGH = COLOR_DISABLED_BG
            COLOR_CARD_BG = '#F0F0F0'

            stylesheet = f"""
                QMainWindow {{
                    background-color: {COLOR_BG_LIGHT};
                }}
                QWidget {{
                    color: {COLOR_TEXT_DARK};

                }}
                QTabWidget::pane {{
                    border: 1px solid {COLOR_BORDER};
                    border-top: none;
                    background: {COLOR_BG_WHITE};
                }}
                QTabBar::tab {{
                    background: {COLOR_TAB_INACTIVE_BG};
                    color: {COLOR_TAB_FG};
                    border: 1px solid {COLOR_BORDER};
                    border-bottom: none;
                    padding: 6px 12px;
                    font-weight: bold;
                    margin-right: 1px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }}
                QTabBar::tab:selected {{
                    background: {COLOR_TAB_SELECTED_BG};
                    color: {COLOR_TAB_SELECTED_FG};
                    border-color: {COLOR_BORDER};
                    border-bottom-color: {COLOR_TAB_SELECTED_BG};
                    margin-bottom: -1px;
                }}
                QTabBar::tab:!selected:hover {{
                    background: #E0E0E0;
                }}

                QGroupBox {{
                    font-weight: bold;
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 4px;
                    margin-top: 15px;
                    padding-top: 8px;
                    background-color: {COLOR_BG_LIGHT};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px 0 5px;
                    margin-left: 10px;
                    color: {COLOR_PRIMARY_DARK};
                    background-color: {COLOR_BG_LIGHT};
                }}

                QLabel#StatusBarLabel {{
                     padding: 3px 5px;
                }}
                QLabel#StatusBarLabel[status="error"] {{ color: {COLOR_DANGER}; }}
                QLabel#StatusBarLabel[status="success"] {{ color: {COLOR_SUCCESS}; }}
                QLabel#StatusBarLabel[status="info"] {{ color: {COLOR_INFO}; }}
                QLabel#StatusBarLabel[status="info"], QLabel#StatusBarLabel {{
                    color: {COLOR_SECONDARY};
                }}


                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
                    background-color: {COLOR_BG_WHITE};
                    border: 1px solid {COLOR_BORDER};
                    padding: 4px;
                    border-radius: 3px;
                    min-height: 22px;
                }}
                QLineEdit:read-only {{
                     background-color: {COLOR_DISABLED_BG};
                }}
                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QTextEdit:disabled, QTextEdit:read-only {{
                    background-color: {COLOR_DISABLED_BG};
                    color: {COLOR_DISABLED_FG};
                    border: 1px solid #D0D0D0;
                }}
                 QComboBox::drop-down {{ border: none; }}
                 QComboBox::down-arrow {{  }}


                QPushButton {{
                    background-color: #EFEFEF;
                    color: {COLOR_TEXT_DARK};
                    border: 1px solid #B0B0B0;
                    padding: 6px 12px;
                    border-radius: 3px;
                    min-width: 70px;
                    min-height: 23px;
                }}
                QPushButton:hover {{
                    background-color: #E0E0E0;
                    border-color: #A0A0A0;
                }}
                QPushButton:pressed {{
                    background-color: #D0D0D0;
                }}
                QPushButton:disabled {{
                    background-color: {COLOR_DISABLED_BG};
                    color: {COLOR_DISABLED_FG};
                    border-color: #D0D0D0;
                }}


                QPushButton#AccentButton {{
                    background-color: {COLOR_PRIMARY};
                    color: {COLOR_TEXT_LIGHT};
                    border-color: {COLOR_PRIMARY_DARK};
                    font-weight: bold;
                }}
                QPushButton#AccentButton:hover {{ background-color: {COLOR_PRIMARY_DARK}; }}
                QPushButton#AccentButton:pressed {{ background-color: {COLOR_PRIMARY_DARK}; }}

                QPushButton#WarningButton {{
                    background-color: {COLOR_WARNING};
                    color: {COLOR_TEXT_DARK};
                    border-color: #E0A800;
                    font-weight: bold;
                    padding: 8px 12px;
                }}
                QPushButton#WarningButton:hover {{ background-color: #ffad33; }}
                QPushButton#WarningButton:pressed {{ background-color: #ffad33; }}

                QPushButton#DangerButton {{
                    background-color: {COLOR_DANGER};
                    color: {COLOR_TEXT_LIGHT};
                    border-color: #b21f2d;
                    font-weight: bold;
                    padding: 5px 8px;
                    border-radius: 3px;
                    min-width: 130px;
                    max-width: 180px;
                    min-height: 23px;
                }}
                QPushButton#DangerButton:hover {{ background-color: #c82333; }}
                QPushButton#DangerButton:pressed {{ background-color: #c82333; }}

                QPushButton#SettingsButton {{
                    background-color: #EFEFEF;
                    color: {COLOR_TEXT_DARK};
                    border: 1px solid #B0B0B0;
                    padding: 5px 8px;
                    border-radius: 3px;
                    min-width: 60px;
                    max-width: 150px;
                    min-height: 23px;
                }}
                QPushButton#SettingsButton:hover {{
                    background-color: #E0E0E0;
                    border-color: #A0A0A0;
                }}
                QPushButton#SettingsButton:pressed {{
                    background-color: #D0D0D0;
                }}

                QPushButton#ListAccentButton {{
                     background-color: {COLOR_PRIMARY_DARK};
                     color: {COLOR_TEXT_LIGHT};
                     border-color: #004085;
                     padding: 4px 8px;
                     font-weight: bold;
                     font-size: {self.get_font_size("small")}pt;
                     min-width: 50px;
                }}
                 QPushButton#ListAccentButton:hover {{ background-color: #004085; }}
                 QPushButton#ListAccentButton:pressed {{ background-color: #004085; }}

                QPushButton#SmallNavButton {{
                    padding: 2px 4px;
                    min-width: 25px;
                    max-width: 30px;
                    font-size: {self.get_font_size("base")}pt;
                    background-color: #F0F0F0;
                    border: 1px solid #C0C0C0;
                    border-radius: 3px;
                    min-height: 20px;
                }}
                QPushButton#SmallNavButton:hover {{
                    background-color: #E0E0E0;
                }}
                QPushButton#SmallNavButton:pressed {{
                    background-color: #D0D0D0;
                }}


                QPushButton#CalendarButton {{
                    padding: 2px 3px;
                    min-width: 24px;
                    max-width: 24px;
                    min-height: 22px;
                    max-height: 22px;
                    font-size: {self.get_font_size("base") + 2}pt;
                    background-color: #F5F5F5;
                    border: 1px solid #C0C0C0;
                    border-radius: 3px;
                    color: {COLOR_TEXT_DARK};
                }}
                QPushButton#CalendarButton:hover {{
                    background-color: #E8E8E8;
                }}
                QPushButton#CalendarButton:pressed {{
                    background-color: #D8D8D8;
                }}


                QProgressBar {{
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 3px;
                    text-align: center;
                    background-color: {PB_TROUGH};
                }}
                 QProgressBar::chunk {{
                     border-radius: 2px;
                     background-color: {COLOR_INFO};
                     margin: 1px;
                 }}
                 QProgressBar#PredictionProgressBar::chunk {{ background-color: {COLOR_INFO}; }}
                 QProgressBar#PerformanceProgressBar::chunk {{ background-color: {COLOR_PRIMARY}; }}
                 QProgressBar#OptimizeProgressBar::chunk {{ background-color: {COLOR_SUCCESS}; }}
                 QProgressBar#OptimizeProgressBar {{
                    min-height: 18px;
                 }}


                QScrollArea {{
                    border: 1px solid {COLOR_BORDER};
                    background-color: {COLOR_BG_WHITE};
                }}
                 QScrollArea > QWidget > QWidget {{
                     background-color: {COLOR_BG_WHITE};
                 }}



                QListWidget {{
                     border: 1px solid {COLOR_BORDER};
                     background-color: {COLOR_BG_WHITE};
                 }}
                 QListWidget::item:selected {{
                     background-color: {COLOR_PRIMARY_DARK};
                     color: {COLOR_TEXT_LIGHT};
                 }}


                 QFrame#CardFrame {{
                     background-color: {COLOR_CARD_BG};
                     border-radius: 4px;
                     margin-bottom: 6px;


                 }}



                 QToolTip {{
                     background-color: {COLOR_TOOLTIP_BG};
                     color: {COLOR_TEXT_DARK};
                     border: 1px solid black;
                     padding: 2px;
                 }}
            """

            self.setStyleSheet(stylesheet)
            style_logger.info("Application stylesheet applied with CalendarButton and adjusted DangerButton size.")

        except Exception as e:
            style_logger.error(f"Error applying stylesheet: {e}", exc_info=True)


    def get_qfont(self, font_type: str) -> QFont:

        base_family = self.font_family_base
        base_size = self.font_size_base
        font = QFont(base_family, base_size)

        if font_type == "bold":
            font.setWeight(QFont.Bold)
        elif font_type == "title":
            font.setPointSize(base_size + 2)
            font.setWeight(QFont.Bold)
        elif font_type == "small":
            font.setPointSize(max(6, base_size - 2))
        elif font_type == "italic_small":
            font.setPointSize(max(6, base_size - 2))
            font.setItalic(True)
        elif font_type == "code":
            font.setFamily('Consolas')
            font.setPointSize(base_size)
            font.setStyleHint(QFont.Monospace)
        elif font_type == "code_bold":
            font.setFamily('Consolas')
            font.setPointSize(base_size)
            font.setWeight(QFont.Bold)
            font.setStyleHint(QFont.Monospace)
        elif font_type == "code_bold_underline":
            font.setFamily('Consolas')
            font.setPointSize(base_size)
            font.setWeight(QFont.Bold)
            font.setUnderline(True)
            font.setStyleHint(QFont.Monospace)

        return font

    def get_font_size(self, font_type: str) -> int:

        base_size = self.font_size_base
        if font_type == "base": return base_size
        if font_type == "bold": return base_size
        if font_type == "title": return base_size + 2
        if font_type == "small": return max(6, base_size - 2)
        if font_type == "italic_small": return max(6, base_size - 2)
        if font_type == "code": return base_size
        if font_type == "code_bold": return base_size
        if font_type == "code_bold_underline": return base_size
        return base_size

    def setup_main_tab(self):

        main_logger.debug("Setting up Main tab UI (PyQt5)...")
        main_tab_layout = QVBoxLayout(self.main_tab_frame)
        main_tab_layout.setContentsMargins(15, 15, 15, 15)
        main_tab_layout.setSpacing(10)

        top_h_layout = QHBoxLayout()
        top_h_layout.setSpacing(15)
        main_tab_layout.addLayout(top_h_layout, 0)

        info_groupbox = QGroupBox("Thông Tin Dữ Liệu 📒")
        info_layout = QGridLayout(info_groupbox)
        info_layout.setSpacing(10)
        info_layout.setContentsMargins(10, 15, 10, 10)

        info_layout.addWidget(QLabel("File:"), 0, 0, Qt.AlignLeft | Qt.AlignTop)
        self.data_file_path_label = QLabel("...")
        self.data_file_path_label.setWordWrap(True)
        self.data_file_path_label.setToolTip("Đường dẫn đến file dữ liệu JSON hiện tại.")
        self.data_file_path_label.setMinimumHeight(35)
        info_layout.addWidget(self.data_file_path_label, 0, 1)
        edit_data_button = QPushButton("Edit 📂")
        edit_data_button.setFixedWidth(50)
        edit_data_button.setToolTip("Thay đổi file dữ liệu chính 🖍")
        edit_data_button.clicked.connect(self.change_data_path)
        info_layout.addWidget(edit_data_button, 0, 2, Qt.AlignTop)

        info_layout.addWidget(QLabel("Time:"), 1, 0, Qt.AlignLeft)
        self.date_range_label = QLabel("...")
        self.date_range_label.setToolTip("Ngày bắt đầu và kết thúc của dữ liệu đã tải.")
        info_layout.addWidget(self.date_range_label, 1, 1, 1, 2)

        info_layout.addWidget(QLabel("Đồng bộ:"), 2, 0, Qt.AlignLeft)
        self.sync_url_input = QLineEdit()
        self.sync_url_input.setPlaceholderText("Nhập URL dữ liệu JSON để đồng bộ...")
        self.sync_url_input.setToolTip("URL của file JSON dữ liệu để tải về và thay thế file hiện tại.")
        info_layout.addWidget(self.sync_url_input, 2, 1)
        sync_button = QPushButton("Sync🔄")
        sync_button.setFixedWidth(80)
        sync_button.setToolTip("Tải dữ liệu từ URL và ghi đè file hiện tại (có sao lưu).")
        sync_button.clicked.connect(self.sync_data)
        info_layout.addWidget(sync_button, 2, 2)

        info_layout.setRowStretch(3, 1)
        info_layout.setColumnStretch(0, 0)
        info_layout.setColumnStretch(1, 10)
        info_layout.setColumnStretch(2, 0)
        top_h_layout.addWidget(info_groupbox, 5)

        control_groupbox = QGroupBox("Chọn Ngày để dự Đoán")
        control_layout = QVBoxLayout(control_groupbox)
        control_layout.setSpacing(8)
        control_layout.setContentsMargins(10, 15, 10, 10)

        date_control_frame = QWidget()
        date_control_h_layout = QHBoxLayout(date_control_frame)
        date_control_h_layout.setContentsMargins(0,0,0,0)
        date_control_h_layout.setSpacing(6)
        date_control_h_layout.addWidget(QLabel("Chọn ngày:"))
        self.selected_date_edit = QLineEdit()
        self.selected_date_edit.setReadOnly(True)
        self.selected_date_edit.setAlignment(Qt.AlignCenter)
        self.selected_date_edit.setMinimumWidth(125)
        self.selected_date_edit.setToolTip("Ngày thực hiện dự đoán.")
        date_control_h_layout.addWidget(self.selected_date_edit)

        self.date_calendar_button = QPushButton("📅")
        self.date_calendar_button.setObjectName("CalendarButton")
        self.date_calendar_button.setToolTip("Mở lịch để chọn ngày.")
        self.date_calendar_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.selected_date_edit))
        date_control_h_layout.addWidget(self.date_calendar_button)

        prev_day_button = QPushButton("◀")
        prev_day_button.setObjectName("SmallNavButton")
        prev_day_button.setToolTip("Chọn ngày trước đó trong dữ liệu.")
        prev_day_button.clicked.connect(self.select_previous_day)
        date_control_h_layout.addWidget(prev_day_button)
        next_day_button = QPushButton("▶️")
        next_day_button.setObjectName("SmallNavButton")
        next_day_button.setToolTip("Chọn ngày kế tiếp trong dữ liệu.")
        next_day_button.clicked.connect(self.select_next_day)
        date_control_h_layout.addWidget(next_day_button)
        date_control_h_layout.addStretch(1)

        self.predict_button = QPushButton("Dự Đoán")
        self.predict_button.setObjectName("AccentButton")
        self.predict_button.setMinimumWidth(90)
        self.predict_button.setToolTip("Chạy dự đoán cho ngày đã chọn bằng các thuật toán được kích hoạt.")
        self.predict_button.clicked.connect(self.start_prediction_process)
        date_control_h_layout.addWidget(self.predict_button)
        control_layout.addWidget(date_control_frame)

        self.predict_progress_frame = QWidget()
        predict_progress_v_layout = QVBoxLayout(self.predict_progress_frame)
        predict_progress_v_layout.setContentsMargins(5, 2, 5, 5)
        predict_progress_v_layout.setSpacing(2)
        self.predict_status_label = QLabel("Tiến trình dự đoán: Chưa chạy")
        self.predict_status_label.setObjectName("ProgressIdle")
        predict_progress_v_layout.addWidget(self.predict_status_label)
        self.predict_progressbar = QProgressBar()
        self.predict_progressbar.setObjectName("PredictionProgressBar")
        self.predict_progressbar.setTextVisible(False)
        self.predict_progressbar.setFixedHeight(10)
        self.predict_progressbar.setRange(0, 100)
        predict_progress_v_layout.addWidget(self.predict_progressbar)
        control_layout.addWidget(self.predict_progress_frame)
        self.predict_progress_frame.setVisible(False)
        control_layout.addStretch(1)
        top_h_layout.addWidget(control_groupbox, 4)

        bottom_splitter = QSplitter(Qt.Horizontal)
        main_tab_layout.addWidget(bottom_splitter, 1)

        left_groupbox = QGroupBox("Danh sách thuật toán ♻️")
        left_outer_layout = QVBoxLayout(left_groupbox)
        left_outer_layout.setContentsMargins(5, 5, 5, 5)
        left_outer_layout.setSpacing(8)
        top_spacer_algo = QFrame()
        top_spacer_algo.setFixedHeight(5)
        top_spacer_algo.setFrameShape(QFrame.NoFrame)
        left_outer_layout.addWidget(top_spacer_algo)
        reload_hint_frame = QWidget()
        reload_hint_layout = QHBoxLayout(reload_hint_frame)
        reload_hint_layout.setContentsMargins(0,0,0,0)
        reload_hint_layout.setSpacing(10)
        reload_algo_button = QPushButton("Tải lại thuật toán 🔃")
        reload_algo_button.setToolTip("Quét lại thư mục 'algorithms' và tải lại danh sách 🔃")
        reload_algo_button.clicked.connect(self.reload_algorithms)
        reload_hint_layout.addWidget(reload_algo_button)
        reload_hint_layout.addStretch(1)
        weight_hint_label = QLabel("Kích hoạt để bật Hệ số nhân.")
        weight_hint_label.setStyleSheet("font-style: italic; color: #6c757d;")
        reload_hint_layout.addWidget(weight_hint_label)
        left_outer_layout.addWidget(reload_hint_frame)
        self.algo_scroll_area = QScrollArea()
        self.algo_scroll_area.setWidgetResizable(True)
        self.algo_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")
        self.algo_scroll_widget = QWidget()
        self.algo_scroll_area.setWidget(self.algo_scroll_widget)
        self.algo_list_layout = QVBoxLayout(self.algo_scroll_widget)
        self.algo_list_layout.setAlignment(Qt.AlignTop)
        self.algo_list_layout.setSpacing(6)
        left_outer_layout.addWidget(self.algo_scroll_area)
        bottom_splitter.addWidget(left_groupbox)

        right_groupbox = QGroupBox("🧮 Hiệu suất Kết Hợp")
        right_layout = QVBoxLayout(right_groupbox)
        right_layout.setContentsMargins(5, 15, 5, 5)
        right_layout.setSpacing(8)
        date_range_frame = QWidget()
        date_range_layout = QHBoxLayout(date_range_frame)
        date_range_layout.setContentsMargins(0,0,0,0)
        date_range_layout.setSpacing(5)
        date_range_layout.addWidget(QLabel("Từ:"))
        self.perf_start_date_edit = QLineEdit()
        self.perf_start_date_edit.setReadOnly(True)
        self.perf_start_date_edit.setAlignment(Qt.AlignCenter)
        self.perf_start_date_edit.setMinimumWidth(110)
        self.perf_start_date_edit.setToolTip("Ngày bắt đầu khoảng tính hiệu suất.")
        date_range_layout.addWidget(self.perf_start_date_edit)

        self.perf_start_date_button = QPushButton("📅")
        self.perf_start_date_button.setObjectName("CalendarButton")
        self.perf_start_date_button.setToolTip("Chọn ngày bắt đầu.")
        self.perf_start_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.perf_start_date_edit))
        date_range_layout.addWidget(self.perf_start_date_button)

        date_range_layout.addSpacing(10)
        date_range_layout.addWidget(QLabel("Đến:"))
        self.perf_end_date_edit = QLineEdit()
        self.perf_end_date_edit.setReadOnly(True)
        self.perf_end_date_edit.setAlignment(Qt.AlignCenter)
        self.perf_end_date_edit.setMinimumWidth(110)
        self.perf_end_date_edit.setToolTip("Ngày kết thúc khoảng tính hiệu suất.")
        date_range_layout.addWidget(self.perf_end_date_edit)

        self.perf_end_date_button = QPushButton("📅")
        self.perf_end_date_button.setObjectName("CalendarButton")
        self.perf_end_date_button.setToolTip("Chọn ngày kết thúc.")
        self.perf_end_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.perf_end_date_edit))
        date_range_layout.addWidget(self.perf_end_date_button)

        date_range_layout.addStretch(1)
        self.perf_calc_button = QPushButton("Tính Toán")
        self.perf_calc_button.setObjectName("AccentButton")
        self.perf_calc_button.setToolTip("Tính toán hiệu suất kết hợp của các thuật toán được kích hoạt trong khoảng ngày đã chọn.")
        self.perf_calc_button.clicked.connect(self.calculate_combined_performance)
        date_range_layout.addWidget(self.perf_calc_button)
        right_layout.addWidget(date_range_frame)
        self.perf_progress_frame = QWidget()
        perf_progress_layout = QVBoxLayout(self.perf_progress_frame)
        perf_progress_layout.setContentsMargins(5, 0, 5, 5)
        perf_progress_layout.setSpacing(2)
        self.perf_status_label = QLabel("")
        self.perf_status_label.setObjectName("ProgressIdle")
        perf_progress_layout.addWidget(self.perf_status_label)
        self.perf_progressbar = QProgressBar()
        self.perf_progressbar.setObjectName("PerformanceProgressBar")
        self.perf_progressbar.setTextVisible(False)
        self.perf_progressbar.setFixedHeight(10)
        perf_progress_layout.addWidget(self.perf_progressbar)
        right_layout.addWidget(self.perf_progress_frame)
        self.perf_progress_frame.setVisible(False)
        right_layout.addWidget(QLabel("Kết quả:"))
        self.performance_text = QTextEdit()
        self.performance_text.setReadOnly(True)
        perf_font = self.get_qfont("code")
        self.performance_text.setFont(perf_font)
        self.performance_text.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #212529;
                border: 1px solid #CED4DA;
            }
        """)
        self._setup_performance_text_formats()
        self.load_performance_data()
        right_layout.addWidget(self.performance_text, 1)
        bottom_splitter.addWidget(right_groupbox)

        initial_splitter_sizes = [self.width() // 2, self.width() // 2] if self.width() > 100 else [450, 350]
        bottom_splitter.setSizes(initial_splitter_sizes)

        main_logger.debug("Main tab UI setup complete.")

    def setup_settings_tab(self):

        main_logger.debug("Setting up consolidated Settings tab UI (PyQt5)...")
        settings_tab_layout = QVBoxLayout(self.settings_tab_frame)
        settings_tab_layout.setContentsMargins(15, 15, 15, 15)
        settings_tab_layout.setSpacing(15)
        settings_tab_layout.setAlignment(Qt.AlignTop)

        settings_group = QGroupBox("⚙Cài Đặt Chung")
        settings_group_layout = QGridLayout(settings_group)
        settings_group_layout.setContentsMargins(10, 15, 10, 10)
        settings_group_layout.setHorizontalSpacing(10)
        settings_group_layout.setVerticalSpacing(12)

        settings_group_layout.addWidget(QLabel("📂 File dữ liệu:"), 0, 0, Qt.AlignLeft)
        self.config_data_path_edit = QLineEdit()
        self.config_data_path_edit.setToolTip("Đường dẫn đầy đủ đến file JSON chứa dữ liệu kết quả.")
        settings_group_layout.addWidget(self.config_data_path_edit, 0, 1, 1, 2)
        browse_button = QPushButton("📂")
        browse_button.setFixedWidth(40)
        browse_button.setToolTip("Chọn file dữ liệu JSON 📂")
        browse_button.clicked.connect(self.browse_data_file_settings)
        settings_group_layout.addWidget(browse_button, 0, 3)

        settings_group_layout.addWidget(QLabel("🔗 URL đồng bộ:"), 1, 0, Qt.AlignLeft)
        self.config_sync_url_edit = QLineEdit()
        self.config_sync_url_edit.setToolTip("URL để tải dữ liệu mới khi nhấn nút 'Sync' ở tab Main.")
        settings_group_layout.addWidget(self.config_sync_url_edit, 1, 1, 1, 3)

        settings_group_layout.addWidget(QLabel("💻 Kích thước cửa sổ:"), 2, 0, Qt.AlignLeft)
        size_frame = QWidget()
        size_layout = QHBoxLayout(size_frame)
        size_layout.setContentsMargins(0,0,0,0)
        size_layout.setSpacing(5)
        self.window_width_edit = QLineEdit()
        self.window_width_edit.setFixedWidth(80)
        self.window_width_edit.setAlignment(Qt.AlignCenter)
        self.window_width_edit.setValidator(self.dimension_validator)
        self.window_width_edit.setToolTip("Chiều rộng cửa sổ ứng dụng (pixels).")
        size_layout.addWidget(self.window_width_edit)
        size_layout.addWidget(QLabel(" x "))
        self.window_height_edit = QLineEdit()
        self.window_height_edit.setFixedWidth(80)
        self.window_height_edit.setAlignment(Qt.AlignCenter)
        self.window_height_edit.setValidator(self.dimension_validator)
        self.window_height_edit.setToolTip("Chiều cao cửa sổ ứng dụng (pixels).")
        size_layout.addWidget(self.window_height_edit)
        size_layout.addWidget(QLabel("(pixels)"))
        size_layout.addStretch(1)
        settings_group_layout.addWidget(size_frame, 2, 1, 1, 3)

        settings_group_layout.addWidget(QLabel("🔤 Font chữ (Cần khởi động lại):"), 3, 0, Qt.AlignLeft)
        font_frame = QWidget()
        font_layout = QHBoxLayout(font_frame)
        font_layout.setContentsMargins(0,0,0,0)
        font_layout.setSpacing(10)
        self.theme_font_family_base_combo = QComboBox()
        self.theme_font_family_base_combo.addItems(self.available_fonts)
        self.theme_font_family_base_combo.setToolTip("Chọn font chữ mặc định cho ứng dụng.")
        font_layout.addWidget(self.theme_font_family_base_combo, 0)

        font_layout.addWidget(QLabel("Cỡ:"))
        self.theme_font_size_base_spinbox = QSpinBox()
        self.theme_font_size_base_spinbox.setRange(8, 24)
        self.theme_font_size_base_spinbox.setToolTip("Chọn cỡ chữ mặc định (points).")
        self.theme_font_size_base_spinbox.setFixedWidth(60)
        font_layout.addWidget(self.theme_font_size_base_spinbox)

        font_layout.addStretch(1)

        settings_group_layout.addWidget(font_frame, 3, 1, 1, 3)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        settings_group_layout.addWidget(separator, 4, 0, 1, 4)

        settings_group_layout.addWidget(QLabel("⚙️ Quản lý file cấu hình khác:"), 5, 0, Qt.AlignLeft)

        self.config_listwidget = QListWidget()
        self.config_listwidget.setFixedHeight(80)
        self.config_listwidget.setToolTip("Double-click để tải file cấu hình đã chọn.")
        self.config_listwidget.itemDoubleClicked.connect(self.load_selected_config_qt)
        settings_group_layout.addWidget(self.config_listwidget, 6, 0, 1, 4)
        self.update_config_list()

        settings_tab_layout.addWidget(settings_group)

        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 10, 0, 0)

        button_layout.setSpacing(6)

        save_config_button = QPushButton("💾 Lưu Cấu Hình")
        save_config_button.setObjectName("SettingsButton")
        save_config_button.setToolTip("Lưu các cài đặt hiện tại vào file chính settings.ini\n(Cần khởi động lại để áp dụng thay đổi font).")
        save_config_button.clicked.connect(self.save_current_settings_to_main_config)
        button_layout.addWidget(save_config_button)

        save_new_cfg_button = QPushButton("💾 Lưu Mới...")
        save_new_cfg_button.setObjectName("SettingsButton")
        save_new_cfg_button.setToolTip("Lưu cấu hình hiện tại thành một file .ini mới.")
        save_new_cfg_button.clicked.connect(self.save_config_dialog)
        button_layout.addWidget(save_new_cfg_button)

        load_cfg_button = QPushButton("📂 Tải Cấu Hình...")
        load_cfg_button.setObjectName("SettingsButton")
        load_cfg_button.setToolTip("Tải và áp dụng cấu hình từ một file .ini đã lưu\n(Cần khởi động lại để áp dụng thay đổi font).")
        load_cfg_button.clicked.connect(self.load_config_dialog)
        button_layout.addWidget(load_cfg_button)

        reset_cfg_button = QPushButton("🔄 Reset Mặc Định")
        reset_cfg_button.setObjectName("DangerButton")
        reset_cfg_button.setToolTip("Khôi phục tất cả cài đặt (bao gồm font) về giá trị mặc định trong settings.ini\n(Cần khởi động lại để áp dụng).")
        reset_cfg_button.clicked.connect(self.reset_config)
        button_layout.addWidget(reset_cfg_button)

        button_layout.addStretch(1)

        settings_tab_layout.addWidget(button_frame)
        info_groupbox = QGroupBox("")

        info_group_layout = QVBoxLayout(info_groupbox)
        info_group_layout.setContentsMargins(10, 15, 10, 10)
        info_group_layout.setSpacing(8)

        version_label = QLabel(f"<b>Lottery Predictor v4.1</b> by Luvideez <br>(Ngày cập nhật: 03/05/2025)")
        version_label.setTextFormat(Qt.RichText)
        version_label.setAlignment(Qt.AlignCenter)
        info_group_layout.addWidget(version_label)

        libs_label = QLabel("<b>Thư viện sử dụng:</b>")
        libs_label.setAlignment(Qt.AlignCenter)
        info_group_layout.addWidget(libs_label)

        libs = f"Python {sys.version.split()[0]}, PyQt5"
        libs += ", requests"
        libs += ", astor" if HAS_ASTOR and sys.version_info < (3,9) else ""
        libs_val_label = QLabel(libs)
        libs_val_label.setStyleSheet("color: #17a2b8;")
        libs_val_label.setAlignment(Qt.AlignCenter)
        info_group_layout.addWidget(libs_val_label)

        sys_info_title_label = QLabel("<b>Thư mục gốc:</b>")
        sys_info_title_label.setAlignment(Qt.AlignCenter)
        info_group_layout.addWidget(sys_info_title_label)

        sys_info = f"{self.base_dir}"
        sys_info_label = QLabel(sys_info)
        sys_info_label.setTextFormat(Qt.RichText)
        sys_info_label.setStyleSheet("color: #17a2b8;")
        sys_info_label.setAlignment(Qt.AlignCenter)
        info_group_layout.addWidget(sys_info_label)


        settings_tab_layout.addWidget(info_groupbox)


        self._populate_settings_tab_ui()

        main_logger.debug("Consolidated Settings tab UI setup complete.")

    def _populate_settings_tab_ui(self):

        main_logger.debug("Populating Settings tab UI from config...")
        try:
            default_data_path = str(self.data_dir / "xsmb-2-digits.json")
            default_sync_url = "https://raw.githubusercontent.com/khiemdoan/vietnam-lottery-xsmb-analysis/main/data/xsmb-2-digits.json"
            default_width = 1200
            default_height = 800
            default_font_family = self.font_family_base
            default_font_size = self.font_size_base

            if hasattr(self, 'config_data_path_edit'):
                data_file = self.config.get('DATA', 'data_file', fallback=default_data_path)
                self.config_data_path_edit.setText(data_file)
            else:
                main_logger.warning("Widget 'config_data_path_edit' not found during UI population.")

            if hasattr(self, 'config_sync_url_edit'):
                sync_url = self.config.get('DATA', 'sync_url', fallback=default_sync_url)
                self.config_sync_url_edit.setText(sync_url)
                main_logger.debug(f"Setting config_sync_url_edit text to: '{sync_url}'")
            else:
                main_logger.warning("Widget 'config_sync_url_edit' not found during UI population.")


            if hasattr(self, 'window_width_edit'):
                width_str = self.config.get('UI', 'width', fallback=str(default_width))
                self.window_width_edit.setText(width_str)
            else:
                main_logger.warning("Widget 'window_width_edit' not found during UI population.")

            if hasattr(self, 'window_height_edit'):
                height_str = self.config.get('UI', 'height', fallback=str(default_height))
                self.window_height_edit.setText(height_str)
            else:
                main_logger.warning("Widget 'window_height_edit' not found during UI population.")


            if hasattr(self, 'theme_font_family_base_combo'):
                font_family = self.font_family_base
                index = self.theme_font_family_base_combo.findText(font_family, Qt.MatchFixedString)
                if index >= 0:
                     self.theme_font_family_base_combo.setCurrentIndex(index)
                else:
                     default_font_index = self.theme_font_family_base_combo.findText('Segoe UI', Qt.MatchFixedString)
                     if default_font_index >= 0: self.theme_font_family_base_combo.setCurrentIndex(default_font_index)
            else:
                 main_logger.warning("Widget 'theme_font_family_base_combo' not found during UI population.")

            if hasattr(self, 'theme_font_size_base_spinbox'):
                self.theme_font_size_base_spinbox.setValue(self.font_size_base)
            else:
                 main_logger.warning("Widget 'theme_font_size_base_spinbox' not found during UI population.")


        except Exception as e:
            main_logger.error(f"Error populating Settings tab UI: {e}", exc_info=True)
            QMessageBox.warning(self, "Lỗi UI", f"Không thể cập nhật đầy đủ giao diện cài đặt:\n{e}")

    def _setup_performance_text_formats(self):

        self.perf_text_formats = {}
        code_font = self.get_qfont("code")
        code_bold_font = self.get_qfont("code_bold")
        code_bold_underline_font = self.get_qfont("code_bold_underline")

        def create_format(font, color_hex, weight=None, underline=False):
            fmt = QtGui.QTextCharFormat()
            fmt.setFont(font)
            fmt.setForeground(QColor(color_hex))
            if weight: fmt.setFontWeight(weight)
            fmt.setFontUnderline(underline)
            return fmt

        fmt_header = create_format(code_bold_underline_font, '#0056b3')
        fmt_header.setFontPointSize(code_font.pointSize() + 1)
        self.perf_text_formats["section_header"] = fmt_header

        self.perf_text_formats["error"] = create_format(code_font, '#dc3545')

        self.perf_text_formats["normal"] = create_format(code_font, '#212529')






    def load_config(self, config_filename="settings.ini"):
        """
        Loads configuration from the specified file.
        Updates instance variables (like font settings, data path, sync url).
        Updates UI elements OUTSIDE the Settings tab (e.g., Main tab's sync url).
        Does NOT update UI elements directly within the Settings tab (handled by _populate_settings_tab_ui).
        """
        main_logger.info(f"Loading main config: {config_filename}...")
        is_main_settings = (config_filename == "settings.ini")
        config_path = self.config_dir / config_filename
        self.config = configparser.ConfigParser(interpolation=None)
        config_needs_saving = False

        try:
            if config_path.exists():
                read_files = self.config.read(config_path, encoding='utf-8')
                if not read_files:
                     main_logger.error(f"ConfigParser failed to read file (but exists): {config_path}. Check permissions or format. Falling back to defaults.")
                     self.set_default_config()
                     config_needs_saving = True
                else:
                     main_logger.info(f"Read config from {config_path}")
            else:
                main_logger.warning(f"Config file {config_path} not found. Setting defaults.")
                self.set_default_config()
                config_needs_saving = True


            default_data_path = str(self.data_dir / "xsmb-2-digits.json")
            default_sync_url = "https://raw.githubusercontent.com/khiemdoan/vietnam-lottery-xsmb-analysis/main/data/xsmb-2-digits.json"
            if not self.config.has_section('DATA'):
                main_logger.warning("Config missing [DATA] section. Adding default.")
                self.config.add_section('DATA')
                self.config.set('DATA','data_file', default_data_path)
                self.config.set('DATA','sync_url', default_sync_url)
                config_needs_saving = True

            data_file_from_config = self.config.get('DATA', 'data_file', fallback=default_data_path)
            sync_url_from_config = self.config.get('DATA', 'sync_url', fallback=default_sync_url)

            if hasattr(self, 'sync_url_input'):
                self.sync_url_input.setText(sync_url_from_config)
            if hasattr(self, 'data_file_path_label'):
                self.data_file_path_label.setText(data_file_from_config)
                self.data_file_path_label.setToolTip(data_file_from_config)

            default_width, default_height = 1200, 800
            default_font_family = 'Segoe UI'
            default_font_size = 10
            if not self.config.has_section('UI'):
                main_logger.warning("Config missing [UI] section. Adding default.")
                self.config.add_section('UI')
                self.config.set('UI', 'width', str(default_width))
                self.config.set('UI', 'height', str(default_height))
                self.config.set('UI', 'font_family_base', default_font_family)
                self.config.set('UI', 'font_size_base', str(default_font_size))
                config_needs_saving = True

            try:
                self.loaded_width = self.config.getint('UI', 'width', fallback=default_width)
                self.loaded_height = self.config.getint('UI', 'height', fallback=default_height)

                current_width_str = self.config.get('UI', 'width', fallback=str(default_width))
                current_height_str = self.config.get('UI', 'height', fallback=str(default_height))
                if current_width_str != str(self.loaded_width):
                    self.config.set('UI', 'width', str(self.loaded_width))
                    config_needs_saving = True
                if current_height_str != str(self.loaded_height):
                     self.config.set('UI', 'height', str(self.loaded_height))
                     config_needs_saving = True
            except (ValueError, configparser.Error) as e:
                main_logger.warning(f"Invalid window size in config: {e}. Using defaults ({default_width}x{default_height}).")
                self.loaded_width = default_width
                self.loaded_height = default_height
                self.config.set('UI', 'width', str(default_width))
                self.config.set('UI', 'height', str(default_height))
                config_needs_saving = True

            try:
                loaded_font_family = self.config.get('UI', 'font_family_base', fallback=default_font_family)
                if not self.available_fonts:
                    main_logger.error("System font list is empty! Using default font family.")
                    self.font_family_base = default_font_family
                    if loaded_font_family != default_font_family:
                        self.config.set('UI', 'font_family_base', default_font_family)
                        config_needs_saving = True
                elif loaded_font_family not in self.available_fonts:
                    main_logger.warning(f"Font '{loaded_font_family}' from config not found. Falling back to '{default_font_family}'.")
                    self.font_family_base = default_font_family
                    self.config.set('UI', 'font_family_base', self.font_family_base)
                    config_needs_saving = True
                else:
                    self.font_family_base = loaded_font_family

                original_size_str = self.config.get('UI', 'font_size_base', fallback=str(default_font_size))
                loaded_font_size = self.config.getint('UI', 'font_size_base', fallback=default_font_size)
                validated_font_size = max(8, min(24, loaded_font_size))
                self.font_size_base = validated_font_size
                if str(validated_font_size) != original_size_str:
                     self.config.set('UI', 'font_size_base', str(validated_font_size))
                     config_needs_saving = True

                main_logger.info(f"Loaded font instance vars: Family='{self.font_family_base}', Size={self.font_size_base}")

            except (ValueError, configparser.Error) as e:
                main_logger.warning(f"Invalid font settings in config: {e}. Using defaults for instance vars.")
                self.font_family_base = default_font_family
                self.font_size_base = default_font_size
                self.config.set('UI', 'font_family_base', default_font_family)
                self.config.set('UI', 'font_size_base', str(default_font_size))
                config_needs_saving = True


            if is_main_settings and config_needs_saving:
                 main_logger.info("Config needed saving after loading defaults/validation.")
                 self._save_default_config_if_needed(self.settings_file_path)

        except configparser.Error as e:
            main_logger.error(f"Error parsing config file {config_path}: {e}. Setting defaults.")
            self.set_default_config()
            self._apply_default_config_to_vars()
            if is_main_settings:
                 self._save_default_config_if_needed(self.settings_file_path)
        except Exception as e:
            main_logger.error(f"Unexpected error loading main config {config_path}: {e}", exc_info=True)
            self.set_default_config()
            self._apply_default_config_to_vars()
            if is_main_settings:
                 self._save_default_config_if_needed(self.settings_file_path)


    def _save_default_config_if_needed(self, config_path):
        """Saves the current self.config (assumed defaults) to the specified path."""
        try:
            if not self.config.has_section('DATA'): self.config.add_section('DATA')
            if not self.config.has_section('UI'): self.config.add_section('UI')
            with open(config_path, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            main_logger.info(f"Saved default/corrected configuration to: {config_path}")
        except IOError as e:
            main_logger.error(f"Failed to write default/corrected config file {config_path}: {e}")

    def apply_algorithm_config_states(self):
        """Applies enabled/weight states from self.config to algorithm UI widgets."""
        main_logger.debug("Applying algorithm config states from self.config...")
        config_changed = False
        if not hasattr(self, 'algorithms') or not self.algorithms:
            main_logger.warning("Cannot apply algorithm config states: Algorithm UI dictionary empty.")
            return

        for algo_name, algo_data in self.algorithms.items():
            chk_enable = algo_data.get('chk_enable')
            chk_weight = algo_data.get('chk_weight')
            weight_entry = algo_data.get('weight_entry')

            if not chk_enable or not chk_weight or not weight_entry:
                main_logger.warning(f"Missing UI widgets for algorithm '{algo_name}' in apply_algorithm_config_states.")
                continue

            config_section = algo_name

            try:
                self.config.add_section(config_section)
                main_logger.debug(f"Config section '{config_section}' not found. Creating defaults.")

                chk_enable.setChecked(True)
                chk_weight.setChecked(False)
                weight_entry.setText("1.0")

                self.config.set(config_section, 'enabled', 'True')
                self.config.set(config_section, 'weight_enabled', 'False')
                self.config.set(config_section, 'weight_value', '1.0')
                config_changed = True

            except configparser.DuplicateSectionError:
                main_logger.debug(f"Config section '{config_section}' already exists. Loading values.")
                try:
                    is_enabled = self.config.getboolean(config_section, 'enabled', fallback=True)
                    is_weight_enabled = self.config.getboolean(config_section, 'weight_enabled', fallback=False)
                    weight_value_str = self.config.get(config_section, 'weight_value', fallback="1.0")

                    if not self._is_valid_float_str(weight_value_str):
                        main_logger.warning(f"Invalid weight '{weight_value_str}' in config for '{config_section}'. Using '1.0'.")
                        weight_value_str = "1.0"

                    chk_enable.setChecked(is_enabled)
                    chk_weight.setChecked(is_weight_enabled)
                    weight_entry.setText(weight_value_str)

                except (configparser.NoOptionError, ValueError, Exception) as e:
                    main_logger.error(f"Error reading options from existing section '{config_section}': {e}. Setting defaults for UI.", exc_info=True)
                    chk_enable.setChecked(True)
                    chk_weight.setChecked(False)
                    weight_entry.setText("1.0")

            self._update_dependent_weight_widgets(algo_name)

        if config_changed:
            main_logger.info("Saving config after potentially adding/correcting algorithm sections.")
            try:
                 self.save_config("settings.ini")
            except Exception as e:
                 main_logger.error(f"Failed to save config after applying defaults/corrections: {e}", exc_info=True)

    def _apply_default_config_to_vars(self):
         """Updates UI elements based on the current self.config object (used after setting defaults)."""
         main_logger.debug("Applying default config values to UI elements...")
         data_file = self.config.get('DATA', 'data_file', fallback="")
         sync_url = self.config.get('DATA', 'sync_url', fallback="")
         if hasattr(self, 'config_data_path_edit'): self.config_data_path_edit.setText(data_file)
         if hasattr(self, 'config_sync_url_edit'): self.config_sync_url_edit.setText(sync_url)
         if hasattr(self, 'sync_url_input'): self.sync_url_input.setText(sync_url)

         width_str = self.config.get('UI', 'width', fallback="1200")
         height_str = self.config.get('UI', 'height', fallback="800")
         if hasattr(self, 'window_width_edit'): self.window_width_edit.setText(width_str)
         if hasattr(self, 'window_height_edit'): self.window_height_edit.setText(height_str)

         self.apply_algorithm_config_states()

    def set_default_config(self):
        """Sets the self.config object to default values."""
        main_logger.info("Setting self.config object to default values.")
        self.config = configparser.ConfigParser(interpolation=None)
        self.config['DATA'] = {
            'data_file': str(self.data_dir / "xsmb-2-digits.json"),
            'sync_url': "https://raw.githubusercontent.com/khiemdoan/vietnam-lottery-xsmb-analysis/main/data/xsmb-2-digits.json"
        }
        self.config['UI'] = {
            'width': '1200',
            'height': '800',
            'font_family_base': 'Segoe UI',
            'font_size_base': '10'
        }

    def save_config_from_settings_ui(self):
         """Saves the current state of the Settings UI fields to settings.ini."""
         main_logger.info("Saving configuration from Settings UI to settings.ini...")
         try:
            if not self.config.has_section('DATA'): self.config.add_section('DATA')
            self.config.set('DATA', 'data_file', self.config_data_path_edit.text())
            self.config.set('DATA', 'sync_url', self.config_sync_url_edit.text())

            if not self.config.has_section('UI'): self.config.add_section('UI')
            width_str = self.window_width_edit.text().strip()
            height_str = self.window_height_edit.text().strip()
            try: w = int(width_str) if width_str else 1200
            except ValueError: w = 1200
            try: h = int(height_str) if height_str else 800
            except ValueError: h = 800
            self.config.set('UI', 'width', str(w))
            self.config.set('UI', 'height', str(h))

            if hasattr(self, 'algorithms'):
                 for algo_name, algo_data in self.algorithms.items():
                     chk_enable = algo_data.get('chk_enable')
                     chk_weight = algo_data.get('chk_weight')
                     weight_entry = algo_data.get('weight_entry')
                     if not chk_enable or not chk_weight or not weight_entry: continue

                     config_section = algo_name
                     if not self.config.has_section(config_section): self.config.add_section(config_section)

                     self.config.set(config_section, 'enabled', str(chk_enable.isChecked()))
                     self.config.set(config_section, 'weight_enabled', str(chk_weight.isChecked()))
                     value_to_save = weight_entry.text().strip()
                     value_to_save = value_to_save if self._is_valid_float_str(value_to_save) else "1.0"
                     self.config.set(config_section, 'weight_value', value_to_save)


            with open(self.settings_file_path, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)

            if hasattr(self, 'sync_url_input'): self.sync_url_input.setText(self.config_sync_url_edit.text())
            self._apply_window_size_from_config()

            self.update_status("Đã lưu cấu hình chính (settings.ini)")
            QMessageBox.information(self, "Lưu Thành Công", "Cấu hình ứng dụng đã được lưu vào settings.ini.")

         except Exception as e:
             main_logger.error(f"Error saving config from Settings UI: {e}", exc_info=True)
             QMessageBox.critical(self, "Lỗi Lưu Cấu Hình", f"Không thể lưu cấu hình:\n{e}")

    def save_config(self, config_filename="settings.ini"):
        """Saves the current self.config object to the specified file."""
        main_logger.debug(f"Saving config object to file: {config_filename}...")
        save_path = self.config_dir / config_filename
        try:
            if not self.config.has_section('DATA'): self.config.add_section('DATA')
            if not self.config.has_section('UI'): self.config.add_section('UI')
            if not self.config.has_option('UI', 'width'): self.config.set('UI','width', '1200')
            if not self.config.has_option('UI', 'height'): self.config.set('UI','height', '800')
            if not self.config.has_option('DATA', 'data_file'): self.config.set('DATA', 'data_file', str(self.data_dir / "xsmb-2-digits.json"))
            if not self.config.has_option('DATA', 'sync_url'): self.config.set('DATA', 'sync_url', "https://raw.githubusercontent.com/khiemdoan/vietnam-lottery-xsmb-analysis/main/data/xsmb-2-digits.json")



            with open(save_path, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)

            if config_filename == "settings.ini":
                if hasattr(self, 'sync_url_input'):
                     self.sync_url_input.setText(self.config.get('DATA','sync_url', fallback=''))
                self._apply_window_size_from_config()

            main_logger.info(f"Configuration saved to: {save_path}")

        except Exception as e:
            main_logger.error(f"Error saving config object to '{config_filename}': {e}", exc_info=True)
            raise

    def save_current_settings_to_main_config(self):
        """Saves the current state of the Settings UI fields to settings.ini."""
        main_logger.info("Saving current settings from UI to settings.ini...")
        try:
            if not self.config.has_section('DATA'): self.config.add_section('DATA')
            self.config.set('DATA', 'data_file', self.config_data_path_edit.text())
            self.config.set('DATA', 'sync_url', self.config_sync_url_edit.text())

            if not self.config.has_section('UI'): self.config.add_section('UI')
            width_str = self.window_width_edit.text().strip()
            height_str = self.window_height_edit.text().strip()
            try: w = int(width_str) if width_str else 1200
            except ValueError: w = 1200
            try: h = int(height_str) if height_str else 800
            except ValueError: h = 800
            self.config.set('UI', 'width', str(w))
            self.config.set('UI', 'height', str(h))

            font_family = self.theme_font_family_base_combo.currentText()
            font_size = str(self.theme_font_size_base_spinbox.value())
            self.config.set('UI', 'font_family_base', font_family)
            self.config.set('UI', 'font_size_base', font_size)


            self.save_config("settings.ini")

            if hasattr(self, 'sync_url_input'):
                self.sync_url_input.setText(self.config_sync_url_edit.text())
            self._apply_window_size_from_config()
            self.font_family_base = font_family
            self.font_size_base = int(font_size)

            self.update_status("Đã lưu cấu hình vào settings.ini.")
            QMessageBox.information(self, "Lưu Thành Công",
                                    "Cấu hình đã được lưu vào settings.ini.\n"
                                    "Lưu ý: Thay đổi font chữ yêu cầu khởi động lại ứng dụng để có hiệu lực đầy đủ.")

        except Exception as e:
            main_logger.error(f"Error saving current settings to settings.ini: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Lưu Cấu Hình", f"Không thể lưu cấu hình vào settings.ini:\n{e}")

    def _apply_window_size_from_config(self):
        """Applies window size read from the self.config object."""
        try:
            width = self.config.getint('UI', 'width', fallback=1200)
            height = self.config.getint('UI', 'height', fallback=800)
            self.resize(width, height)
            main_logger.info(f"Applied window size from config: {width}x{height}")
            QTimer.singleShot(100, self._log_actual_window_size)
        except Exception as e:
            main_logger.error(f"Error applying window size from config: {e}")

    def _is_valid_float_str(self, s: str) -> bool:
        """Checks if a string can be converted to a float."""
        if not isinstance(s, str) or not s: return False
        try:
            float(s)
            if s.strip() in [".", "-", "+", "-.", "+."]: return False
            return True
        except ValueError:
            return False

    def save_config_dialog(self):
        """Opens a dialog to save the current configuration to a new INI file."""
        try:
            default_name = f"config_{datetime.datetime.now():%Y%m%d_%H%M}.ini"
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu Cấu Hình App Hiện Tại Thành File Mới",
                str(self.config_dir / default_name),
                "Config files (*.ini);;All files (*.*)"
            )
            if filename:
                new_filename = Path(filename).name
                protected_files = {"settings.ini", "performance_history.ini", "settings_optimizer.ini"}
                if new_filename.lower() in protected_files:
                    QMessageBox.warning(self, "Lưu Ý", f"Không nên ghi đè file hệ thống '{new_filename}'.\nVui lòng chọn tên khác.")
                    return

                temp_config_obj = configparser.ConfigParser(interpolation=None)

                if not temp_config_obj.has_section('DATA'): temp_config_obj.add_section('DATA')
                temp_config_obj.set('DATA', 'data_file', self.config_data_path_edit.text())
                temp_config_obj.set('DATA', 'sync_url', self.config_sync_url_edit.text())

                if not temp_config_obj.has_section('UI'): temp_config_obj.add_section('UI')
                w_str = self.window_width_edit.text(); h_str = self.window_height_edit.text()
                temp_config_obj.set('UI', 'width', w_str if w_str.isdigit() else '1200')
                temp_config_obj.set('UI', 'height', h_str if h_str.isdigit() else '800')
                temp_config_obj.set('UI', 'font_family_base', self.theme_font_family_base_combo.currentText())
                temp_config_obj.set('UI', 'font_size_base', str(self.theme_font_size_base_spinbox.value()))

                if hasattr(self, 'algorithms'):
                     for algo_name, algo_data in self.algorithms.items():
                         chk_enable = algo_data.get('chk_enable')
                         chk_weight = algo_data.get('chk_weight')
                         weight_entry = algo_data.get('weight_entry')
                         if not chk_enable or not chk_weight or not weight_entry: continue
                         sec = algo_name
                         if not temp_config_obj.has_section(sec): temp_config_obj.add_section(sec)
                         temp_config_obj.set(sec, 'enabled', str(chk_enable.isChecked()))
                         temp_config_obj.set(sec, 'weight_enabled', str(chk_weight.isChecked()))
                         w_val = weight_entry.text().strip()
                         temp_config_obj.set(sec, 'weight_value', w_val if self._is_valid_float_str(w_val) else "1.0")

                with open(filename, 'w', encoding='utf-8') as configfile:
                    temp_config_obj.write(configfile)

                self.update_config_list()
                QMessageBox.information(self, "Lưu Thành Công", f"Đã lưu cấu hình hiện tại vào:\n{new_filename}")
        except Exception as e:
            main_logger.error(f"Error in save_config_dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi", f"Đã xảy ra lỗi khi lưu file cấu hình mới:\n{e}")

    def load_config_dialog(self):
        """Opens a dialog to select and load an INI configuration file."""
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Chọn file cấu hình App (.ini)",
                str(self.config_dir),
                "Config files (*.ini);;All files (*.*)"
            )
            if filename:
                self.load_config_from_file(Path(filename).name)
        except Exception as e:
             QMessageBox.critical(self, "Lỗi", f"Đã xảy ra lỗi khi chọn file:\n{e}")

    def load_selected_config_qt(self, item: QListWidgetItem):
        """
        Loads the configuration file selected (double-clicked) in the QListWidget
        by calling the main load_config_from_file method.
        """
        if item:
            filename = item.text()
            main_logger.info(f"Config file selected from list (double-click): {filename}")

            try:
                self.load_config_from_file(filename)
            except Exception as e:
                main_logger.error(f"Unexpected error occurred when initiating load from selected config '{filename}': {e}", exc_info=True)
                QMessageBox.critical(self, "Lỗi Nghiêm Trọng", f"Đã xảy ra lỗi không mong muốn khi cố gắng tải file '{filename}':\n{e}")

        else:
            main_logger.warning("load_selected_config_qt called with no valid item.")

    def update_config_list(self):
        """Updates the QListWidget with available .ini configuration files."""
        try:
            if not hasattr(self, 'config_listwidget'): return
            self.config_listwidget.clear()
            if self.config_dir.exists():
                excluded_files = {"settings.ini", "performance_history.ini", "settings_optimizer.ini", "ui_theme.ini"}
                config_files = sorted([
                    f.name for f in self.config_dir.glob('*.ini')
                    if f.name.lower() not in excluded_files
                ])
                for filename in config_files:
                    self.config_listwidget.addItem(filename)
                main_logger.debug(f"Updated config list: Found {len(config_files)} files.")
            else:
                 main_logger.warning("Config directory does not exist, cannot update list.")
        except Exception as e:
            main_logger.error(f"Error updating config list: {e}")

    def reset_config(self):
        """Resets the main settings.ini configuration to default values and updates the UI."""
        reply = QMessageBox.question(
            self,
            "Xác nhận Khôi Phục Mặc Định",
            "Bạn có chắc chắn muốn khôi phục TẤT CẢ cài đặt (bao gồm đường dẫn, URL, kích thước, font chữ) về giá trị mặc định không?\n\n"
            "Thao tác này sẽ:\n"
            "1. Xóa file settings.ini hiện tại (nếu có).\n"
            "2. Tạo lại file settings.ini với giá trị mặc định.\n"
            "3. Tải lại dữ liệu và thuật toán theo cài đặt mặc định.\n\n"
            "Ứng dụng cần được khởi động lại để áp dụng font chữ mặc định.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            main_logger.info("Resetting main configuration (settings.ini) to default.")
            try:
                config_path = self.settings_file_path
                if config_path.exists():
                    try:
                        config_path.unlink()
                        main_logger.info(f"Deleted existing settings file: {config_path}")
                    except OSError as e:
                        QMessageBox.critical(self, "Lỗi Xóa", f"Không thể xóa file '{config_path.name}':\n{e}")
                        main_logger.error(f"Proceeding with reset despite failing to delete {config_path.name}.")

                self.set_default_config()

                self._save_default_config_if_needed(self.settings_file_path)

                self._apply_default_config_to_vars()

                self._populate_settings_tab_ui()

                self._apply_window_size_from_config()
                if hasattr(self, 'sync_url_input'):
                     sync_url = self.config.get('DATA', 'sync_url', fallback="")
                     self.sync_url_input.setText(sync_url)

                self.reload_algorithms()
                self.load_data()

                if self.optimizer_app_instance:
                     default_data_path = self.config.get('DATA', 'data_file', fallback="")
                     if default_data_path:
                          self.optimizer_app_instance.data_file_path_label.setText(default_data_path)
                          self.optimizer_app_instance.load_data()

                self.update_status("Đã khôi phục cấu hình chính (settings.ini) về mặc định.")
                QMessageBox.information(self, "Hoàn Tất", "Đã khôi phục cấu hình về mặc định.\nVui lòng khởi động lại ứng dụng để áp dụng font chữ mặc định.")

            except Exception as e:
                main_logger.error(f"Error during config reset process: {e}", exc_info=True)
                QMessageBox.critical(self, "Lỗi Khôi Phục", f"Đã xảy ra lỗi trong quá trình khôi phục:\n{e}")


    def load_config_from_file(self, filename):
        """
        Loads a specific configuration file (.ini) selected by the user,
        updates the application's state and UI accordingly.
        """
        config_path = self.config_dir / filename
        if not config_path.is_file():
            QMessageBox.warning(self, "Lỗi File",
                                f"File cấu hình '{filename}' không tồn tại trong thư mục:\n{self.config_dir}")
            return

        main_logger.info(f"Loading configuration from specific file: {filename}")
        try:
            self.load_config(filename)

            self._populate_settings_tab_ui()

            self._apply_window_size_from_config()

            self.reload_algorithms()
            self.load_data()

            if self.optimizer_app_instance:
                 new_data_path = self.config.get('DATA', 'data_file', fallback="")
                 if new_data_path:
                      self.optimizer_app_instance.data_file_path_label.setText(new_data_path)
                      self.optimizer_app_instance.load_data()

            self.update_status(f"Đã tải cấu hình từ: {filename}")
            QMessageBox.information(self, "Tải Thành Công",
                                    f"Đã tải và áp dụng cấu hình từ:\n{filename}\n\n"
                                    "Lưu ý: Nếu cấu hình này thay đổi font chữ, bạn cần khởi động lại ứng dụng để áp dụng đầy đủ.")

        except configparser.Error as e:
            main_logger.error(f"Error parsing selected config file '{filename}': {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Đọc Cấu Hình",
                                 f"Đã xảy ra lỗi khi đọc file cấu hình '{filename}':\n{e}\n\n"
                                 "Cấu hình hiện tại không thay đổi.")
        except Exception as e:
            main_logger.error(f"Unexpected error loading config from file '{filename}': {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Tải Cấu Hình",
                                 f"Đã xảy ra lỗi không mong muốn khi tải cấu hình từ '{filename}':\n{e}")

    def load_data(self):
        """Loads lottery result data based on the path in the current config."""
        self.results = []
        main_logger.info("Loading lottery data (PyQt5)...")
        try:
            if not self.config.has_section('DATA') or not self.config.has_option('DATA', 'data_file'):
                main_logger.warning("DATA section or data_file missing in config. Setting defaults.")
                self.set_default_config()
                self._apply_default_config_to_vars()
                self.save_config()

            data_file_str = self.config.get('DATA', 'data_file', fallback="")
            if not data_file_str:
                data_file_str = str(self.data_dir / "xsmb-2-digits.json")
                main_logger.warning(f"Config data_file empty, falling back to default path: {data_file_str}")
                self.config.set('DATA', 'data_file', data_file_str)
                if hasattr(self, 'config_data_path_edit'): self.config_data_path_edit.setText(data_file_str)
                self.save_config()

            data_file_path = Path(data_file_str)

            if hasattr(self, 'data_file_path_label'):
                self.data_file_path_label.setText(str(data_file_path))
                self.data_file_path_label.setToolTip(str(data_file_path))

            if not data_file_path.exists():
                self.update_status(f"Lỗi: File dữ liệu không tồn tại: {data_file_path.name}")
                if hasattr(self, 'date_range_label'): self.date_range_label.setText("Lỗi file")
                if data_file_path == self.data_dir / "xsmb-2-digits.json":
                    self.create_directories()
                    if data_file_path.exists():
                        main_logger.info("Sample data created. Reloading data...")
                        QTimer.singleShot(100, self.load_data)
                        return
                    else:
                        QMessageBox.critical(self, "Lỗi", f"Không tìm thấy hoặc không thể tạo file dữ liệu mẫu:\n{data_file_path}")
                        return
                else:
                    QMessageBox.critical(self, "Lỗi", f"Không tìm thấy file dữ liệu được chỉ định:\n{data_file_path}")
                    return

            main_logger.debug(f"Reading data from: {data_file_path}")
            with open(data_file_path, 'r', encoding='utf-8') as f: raw_data = json.load(f)

            processed_count, unique_dates, results_temp, data_list_to_process = 0, set(), [], []
            if isinstance(raw_data, list): data_list_to_process = raw_data
            elif isinstance(raw_data, dict) and 'results' in raw_data and isinstance(raw_data.get('results'), dict):
                for date_str, result_dict in raw_data['results'].items():
                    if isinstance(result_dict, dict): data_list_to_process.append({'date': date_str, 'result': result_dict})
            else: raise ValueError("Định dạng JSON không hợp lệ hoặc không được hỗ trợ.")

            for item in data_list_to_process:
                 if not isinstance(item, dict): continue
                 date_str_raw = item.get("date");
                 if not date_str_raw: continue
                 date_str_cleaned = str(date_str_raw).split('T')[0]
                 try: date_obj = datetime.datetime.strptime(date_str_cleaned, '%Y-%m-%d').date();
                 except ValueError: continue
                 if date_obj in unique_dates: continue
                 result_data = item.get('result');
                 if result_data is None: result_data = {k: v for k, v in item.items() if k != 'date'}
                 if not result_data: continue
                 results_temp.append({'date': date_obj, 'result': result_data}); unique_dates.add(date_obj); processed_count += 1

            if results_temp:
                results_temp.sort(key=lambda x: x['date'])
                self.results = results_temp
                start_date, end_date = self.results[0]['date'], self.results[-1]['date']
                start_ui, end_ui = start_date.strftime('%d/%m/%Y'), end_date.strftime('%d/%m/%Y')
                date_range_text = f"{start_ui} - {end_ui} ({len(self.results)} ngày)"
                if hasattr(self, 'date_range_label'): self.date_range_label.setText(date_range_text)
                main_logger.info(f"Data loaded: {len(self.results)} results from {start_date} to {end_date}")

                current_selection_str = ""
                if hasattr(self, 'selected_date_edit'): current_selection_str = self.selected_date_edit.text()
                needs_update = True
                if current_selection_str:
                    try:
                        current_selection_date = datetime.datetime.strptime(current_selection_str, '%d/%m/%Y').date()
                        if start_date <= current_selection_date <= end_date:
                            self.selected_date = current_selection_date
                            needs_update = False
                    except ValueError: pass

                if needs_update:
                    self.selected_date = end_date
                    if hasattr(self, 'selected_date_edit'): self.selected_date_edit.setText(end_ui)

                self._update_default_perf_dates(start_date, end_date)
                self.update_status(f"Đã tải {len(self.results)} kết quả từ {data_file_path.name}")

            else:
                if hasattr(self, 'date_range_label'): self.date_range_label.setText("Không có dữ liệu hợp lệ")
                self.selected_date = None
                if hasattr(self, 'selected_date_edit'): self.selected_date_edit.setText("")
                if hasattr(self, 'perf_start_date_edit'): self.perf_start_date_edit.setText("")
                if hasattr(self, 'perf_end_date_edit'): self.perf_end_date_edit.setText("")
                self.update_status(f"Không tìm thấy dữ liệu hợp lệ trong file: {data_file_path.name}")

        except (json.JSONDecodeError, ValueError) as e:
             QMessageBox.critical(self, "Lỗi Định Dạng Dữ Liệu", f"File '{data_file_path.name}' có định dạng JSON không hợp lệ hoặc cấu trúc dữ liệu không đúng:\n{e}")
             self.results = []
             if hasattr(self, 'date_range_label'): self.date_range_label.setText("Lỗi file")
             self.selected_date=None
             if hasattr(self, 'selected_date_edit'): self.selected_date_edit.setText("")
             if hasattr(self, 'perf_start_date_edit'): self.perf_start_date_edit.setText("")
             if hasattr(self, 'perf_end_date_edit'): self.perf_end_date_edit.setText("")
             self.update_status(f"Tải dữ liệu thất bại: Lỗi định dạng file {data_file_path.name}")
        except Exception as e:
             main_logger.error(f"Unexpected error loading data from {data_file_path}: {e}", exc_info=True)
             QMessageBox.critical(self, "Lỗi Tải Dữ Liệu", f"Đã xảy ra lỗi không mong muốn khi tải dữ liệu:\n{e}")
             self.results = []
             if hasattr(self, 'date_range_label'): self.date_range_label.setText("Lỗi tải")
             self.selected_date=None
             if hasattr(self, 'selected_date_edit'): self.selected_date_edit.setText("")
             if hasattr(self, 'perf_start_date_edit'): self.perf_start_date_edit.setText("")
             if hasattr(self, 'perf_end_date_edit'): self.perf_end_date_edit.setText("")
             self.update_status("Tải dữ liệu thất bại: Lỗi không xác định.")

    def _update_default_perf_dates(self, data_start_date, data_end_date):
        """Updates the default performance date range UI fields."""
        start_ui = data_start_date.strftime('%d/%m/%Y')
        end_ui = data_end_date.strftime('%d/%m/%Y')
        update_start, update_end = True, True

        if hasattr(self, 'perf_start_date_edit'):
            current_perf_start_str = self.perf_start_date_edit.text()
            if current_perf_start_str:
                try:
                    current_perf_start = datetime.datetime.strptime(current_perf_start_str, '%d/%m/%Y').date()
                    if data_start_date <= current_perf_start <= data_end_date:
                        update_start = False
                except ValueError: pass

        if hasattr(self, 'perf_end_date_edit'):
            current_perf_end_str = self.perf_end_date_edit.text()
            if current_perf_end_str:
                try:
                    current_perf_end = datetime.datetime.strptime(current_perf_end_str, '%d/%m/%Y').date()
                    if data_start_date <= current_perf_end <= data_end_date:
                        update_end = False
                except ValueError: pass

        if update_start and hasattr(self, 'perf_start_date_edit'):
            self.perf_start_date_edit.setText(start_ui)
        if update_end and hasattr(self, 'perf_end_date_edit'):
            self.perf_end_date_edit.setText(end_ui)

    def change_data_path(self):
        """Allows user to select a new data file, saves it to config, and reloads."""
        try:
            current_path_str = self.config.get('DATA', 'data_file', fallback='')
            initial_dir = str(self.data_dir)
            if current_path_str:
                 parent_dir = Path(current_path_str).parent
                 if parent_dir.is_dir():
                     initial_dir = str(parent_dir)

            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Chọn file dữ liệu JSON mới",
                initial_dir,
                "JSON files (*.json);;All files (*.*)"
            )

            if filename:
                new_path = Path(filename)
                self.config.set('DATA', 'data_file', str(new_path))
                if hasattr(self, 'config_data_path_edit'):
                     self.config_data_path_edit.setText(str(new_path))

                self.save_config()

                self.load_data()
                self.reload_algorithms()

                if self.optimizer_app_instance:
                    self.optimizer_app_instance.data_file_path_label.setText(str(new_path))
                    self.optimizer_app_instance.load_data()

                self.update_status(f"Đã chuyển sang file dữ liệu: {new_path.name}")
        except Exception as e:
             main_logger.error(f"Error changing data path: {e}", exc_info=True)
             QMessageBox.critical(self, "Lỗi", f"Đã xảy ra lỗi khi thay đổi file dữ liệu:\n{e}")

    def browse_data_file_settings(self):
        """Opens file dialog specifically for the data path in the Settings tab."""
        try:
            current_path_str = self.config_data_path_edit.text()
            initial_dir = str(self.data_dir)
            if current_path_str:
                parent_dir = Path(current_path_str).parent
                if parent_dir.is_dir():
                    initial_dir = str(parent_dir)

            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Chọn đường dẫn file dữ liệu JSON",
                initial_dir,
                "JSON files (*.json);;All files (*.*)"
            )
            if filename:
                self.config_data_path_edit.setText(filename)
        except Exception as e:
             QMessageBox.critical(self, "Lỗi", f"Lỗi duyệt file:\n{e}")

    def sync_data(self):
        """Downloads data from the sync URL and replaces the current data file."""
        url_to_sync = self.sync_url_input.text().strip()
        if not url_to_sync:
            QMessageBox.warning(self, "Thiếu URL", "Vui lòng nhập URL vào ô 'Đồng bộ' để tải dữ liệu.")
            return

        target_file_str = self.config.get('DATA', 'data_file', fallback=str(self.data_dir / "xsmb-2-digits.json"))
        target_file = Path(target_file_str)
        backup_file = target_file.with_suffix(target_file.suffix + '.bak')
        backed_up_successfully = False

        try: import requests
        except ImportError:
            QMessageBox.critical(self, "Thiếu Thư Viện", "Chức năng đồng bộ yêu cầu thư viện 'requests'.\nVui lòng cài đặt bằng lệnh:\n\npip install requests")
            return

        self.update_status(f"Đang tải dữ liệu từ URL...")
        QApplication.processEvents()

        try:
            main_logger.info(f"Attempting to download data from: {url_to_sync}")
            response = requests.get(url_to_sync, timeout=30, headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
            response.raise_for_status()
            main_logger.info(f"Download successful (Status: {response.status_code}). Size: {len(response.content)} bytes.")

            try:
                 downloaded_data = response.json()
                 is_valid_format = isinstance(downloaded_data, list) or \
                                  (isinstance(downloaded_data, dict) and 'results' in downloaded_data and isinstance(downloaded_data.get('results'), dict))
                 if not is_valid_format:
                     raise ValueError("Định dạng JSON tải về không hợp lệ (không phải list hoặc dict có key 'results').")
                 main_logger.info("Downloaded data appears to be valid JSON format.")
            except (json.JSONDecodeError, ValueError) as json_err:
                main_logger.error(f"Downloaded data validation failed: {json_err}")
                QMessageBox.critical(self, "Lỗi Dữ Liệu Tải Về", f"Dữ liệu tải về từ URL không phải là file JSON hợp lệ hoặc có cấu trúc không đúng:\n{json_err}")
                self.update_status("Đồng bộ thất bại: dữ liệu tải về không hợp lệ.")
                return

            if target_file.exists():
                try:
                    shutil.copy2(target_file, backup_file)
                    backed_up_successfully = True
                    main_logger.info(f"Backed up existing data file to: {backup_file.name}")
                except Exception as backup_err:
                    main_logger.error(f"Failed to backup data file: {backup_err}", exc_info=True)
                    reply = QMessageBox.warning(self, "Lỗi Sao Lưu", f"Không thể tạo file sao lưu cho:\n{target_file.name}\n\nLỗi: {backup_err}\n\nTiếp tục đồng bộ mà không sao lưu?",
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.No:
                        self.update_status("Đồng bộ đã hủy do lỗi sao lưu.")
                        return

            try:
                with open(target_file, 'wb') as f:
                    f.write(response.content)
                main_logger.info(f"Successfully wrote downloaded data to: {target_file.name}")
            except IOError as save_err:
                main_logger.error(f"Failed to write downloaded data to {target_file.name}: {save_err}", exc_info=True)
                QMessageBox.critical(self, "Lỗi Lưu File", f"Không thể ghi dữ liệu tải về vào file:\n{target_file.name}\n\nLỗi: {save_err}")
                if backed_up_successfully:
                    self._restore_backup(backup_file, target_file)
                self.update_status("Đồng bộ thất bại: lỗi ghi file.")
                return

            self.load_data()
            self.reload_algorithms()

            if self.optimizer_app_instance:
                 self.optimizer_app_instance.data_file_path_label.setText(str(target_file))
                 self.optimizer_app_instance.load_data()

            self.update_status("Đồng bộ dữ liệu thành công.")
            QMessageBox.information(self, "Hoàn Tất", f"Đã đồng bộ và cập nhật dữ liệu thành công từ:\n{url_to_sync}")

        except requests.exceptions.RequestException as req_err:
            main_logger.error(f"Failed to download data from {url_to_sync}: {req_err}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Kết Nối", f"Không thể tải dữ liệu từ URL:\n{url_to_sync}\n\nLỗi: {req_err}")
            self.update_status(f"Đồng bộ thất bại: lỗi kết nối hoặc URL không hợp lệ.")
            if backed_up_successfully: self._restore_backup(backup_file, target_file)
        except Exception as e:
            main_logger.error(f"Unexpected error during data sync: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Đồng Bộ", f"Đã xảy ra lỗi không mong muốn trong quá trình đồng bộ:\n{e}")
            self.update_status(f"Đồng bộ thất bại: lỗi không xác định.")
            if backed_up_successfully: self._restore_backup(backup_file, target_file)

    def _restore_backup(self, backup_path: Path, target_path: Path):
        """Attempts to restore a data file from its backup."""
        try:
            if backup_path.exists():
                shutil.move(str(backup_path), str(target_path))
                main_logger.info(f"Restored data file from backup: {backup_path.name}")
        except Exception as move_err:
            main_logger.error(f"Failed to restore data file from backup {backup_path.name}: {move_err}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Khôi Phục Sao Lưu", f"Lỗi nghiêm trọng: Không thể khôi phục file dữ liệu gốc từ bản sao lưu.\nFile sao lưu: {backup_path}\nLỗi: {move_err}\n\nVui lòng kiểm tra thủ công.")


    def load_algorithms(self):
        """Loads algorithms, creates their UI elements in the Main tab's scroll area."""
        main_logger.info("Scanning and loading algorithms for Main tab (PyQt5)...")

        if hasattr(self, 'algo_list_layout'):
            while self.algo_list_layout.count() > 0:
                item = self.algo_list_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            main_logger.error("Algorithm list layout (algo_list_layout) not found. Cannot load algorithm UI.")
            return

        self.algorithms.clear()
        self.algorithm_instances.clear()
        count_success, count_failed = 0, 0

        if not self.algorithms_dir.is_dir():
            main_logger.warning(f"Algorithms directory not found: {self.algorithms_dir}. Attempting to create.")
            try:
                self.create_directories()
            except Exception as e:
                main_logger.error(f"Failed to create algorithms directory: {e}")
                if hasattr(self, 'algo_list_layout'):
                    error_label = QLabel(f"Lỗi: Không tìm thấy thư mục thuật toán:\n{self.algorithms_dir}")
                    error_label.setStyleSheet("color: red; padding: 10px;")
                    self.algo_list_layout.addWidget(error_label)
                return
            if not self.algorithms_dir.is_dir():
                 main_logger.error("Algorithms directory still not found after creation attempt.")
                 if hasattr(self, 'algo_list_layout'):
                     error_label = QLabel(f"Lỗi: Không tìm thấy thư mục thuật toán:\n{self.algorithms_dir}")
                     error_label.setStyleSheet("color: red; padding: 10px;")
                     self.algo_list_layout.addWidget(error_label)
                 return

        try:
            algorithm_files_to_load = [
                f for f in self.algorithms_dir.glob('*.py')
                if f.is_file() and f.name not in ["__init__.py", "base.py"]
            ]
            main_logger.debug(f"Found {len(algorithm_files_to_load)} potential algorithm files.")
        except Exception as e:
            main_logger.error(f"Error scanning algorithms directory: {e}", exc_info=True)
            if hasattr(self, 'algo_list_layout'):
                 error_label = QLabel(f"Lỗi đọc thư mục thuật toán:\n{e}")
                 error_label.setStyleSheet("color: red; padding: 10px;")
                 self.algo_list_layout.addWidget(error_label)
            return

        if not algorithm_files_to_load:
             self.create_sample_algorithms()
             algorithm_files_to_load = [
                f for f in self.algorithms_dir.glob('*.py')
                if f.is_file() and f.name not in ["__init__.py", "base.py"]
            ]
             main_logger.info(f"Found {len(algorithm_files_to_load)} files after checking for samples.")


        results_copy_for_instances = copy.deepcopy(self.results) if self.results else []
        cache_dir_for_instances = self.calculate_dir

        initial_algo_label = None
        if not algorithm_files_to_load:
             initial_algo_label = QLabel("Không tìm thấy file thuật toán (.py) nào trong thư mục 'algorithms'.")
             initial_algo_label.setStyleSheet("font-style: italic; color: #6c757d; padding: 10px;")
             if hasattr(self, 'algo_list_layout'):
                 self.algo_list_layout.addWidget(initial_algo_label)

        for f_path in algorithm_files_to_load:
            main_logger.debug(f"Processing algorithm file: {f_path.name}")
            try:
                loaded_successfully = self.load_algorithm_from_file(
                    f_path, results_copy_for_instances, cache_dir_for_instances
                )
                if loaded_successfully:
                    count_success += 1
                else:
                    count_failed += 1
            except Exception as e:
                main_logger.error(f"Unexpected error loading {f_path.name}: {e}", exc_info=True)
                count_failed += 1

        status_msg = f"Đã tải {count_success} thuật toán (Main)"
        if count_failed > 0:
            status_msg += f", lỗi {count_failed} file"
        self.update_status(status_msg)

        if count_failed > 0 and count_success > 0:
            QMessageBox.warning(self, "Lỗi Tải Thuật Toán", f"Đã xảy ra lỗi khi tải {count_failed} file thuật toán.\nKiểm tra file log để biết chi tiết.")
        elif count_success == 0 and count_failed > 0:
            QMessageBox.critical(self, "Lỗi Tải Thuật Toán", f"Không thể tải bất kỳ thuật toán nào ({count_failed} lỗi).\nKiểm tra file log hoặc cấu trúc file thuật toán.")
        elif count_success == 0 and algorithm_files_to_load:
            QMessageBox.warning(self, "Không Tìm Thấy Thuật Toán", "Không tìm thấy lớp thuật toán hợp lệ nào (kế thừa từ BaseAlgorithm) trong các file .py.")
            if hasattr(self, 'algo_list_layout') and self.algo_list_layout.count() == 0:
                 if initial_algo_label is None:
                      initial_algo_label = QLabel("Không tìm thấy lớp thuật toán hợp lệ nào.")
                      initial_algo_label.setStyleSheet("font-style: italic; color: #6c757d; padding: 10px;")
                      self.algo_list_layout.addWidget(initial_algo_label)
                 else:
                      initial_algo_label.setText("Không tìm thấy lớp thuật toán hợp lệ nào.")


        self.apply_algorithm_config_states()

    def load_algorithm_from_file(self, algo_file_path: Path, data_results_list: list, cache_dir: Path) -> bool:
        """Loads a single algorithm, instantiates it, and creates its UI."""
        module_name = f"algorithms.{algo_file_path.stem}"
        success = False
        module_obj = None
        display_name = f"Unknown ({algo_file_path.name})"

        try:
            if module_name in sys.modules:
                main_logger.debug(f"Reloading module: {module_name}")
                try: module_obj = reload(sys.modules[module_name])
                except Exception as reload_err:
                    main_logger.warning(f"Failed to reload {module_name}, attempting full import: {reload_err}")
                    try: del sys.modules[module_name]
                    except KeyError: pass
                    module_obj = None
            else:
                 main_logger.debug(f"Importing module for the first time: {module_name}")

            if module_obj is None:
                 spec = util.spec_from_file_location(module_name, algo_file_path)
                 if spec and spec.loader:
                     module_obj = util.module_from_spec(spec)
                     sys.modules[module_name] = module_obj
                     spec.loader.exec_module(module_obj)
                 else:
                     main_logger.error(f"Could not create module spec/loader for {algo_file_path.name}")
                     return False
            if not module_obj:
                main_logger.error(f"Module object is None after loading attempt for {algo_file_path.name}")
                return False

            found_class = None
            found_class_name = None
            for name, obj in inspect.getmembers(module_obj):
                if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == module_name:
                    found_class = obj
                    found_class_name = name
                    display_name = f"{name} ({algo_file_path.name})"
                    main_logger.debug(f"Found valid algorithm class '{name}' in {algo_file_path.name}")
                    break

            if found_class:
                try:
                    main_logger.debug(f"Instantiating {found_class_name}...")
                    instance = found_class(data_results_list=data_results_list, cache_dir=cache_dir)
                    config = instance.get_config()
                    if not isinstance(config, dict):
                        main_logger.warning(f"get_config() for '{found_class_name}' did not return a dict. Using default.")
                        config = {"description": "Lỗi đọc config", "parameters":{}}

                    self.algorithm_instances[display_name] = instance
                    self.create_algorithm_ui_qt(display_name, config, algo_file_path.name)
                    success = True
                except Exception as inst_err:
                    main_logger.error(f"Error instantiating or getting config for class '{found_class_name}' in {algo_file_path.name}: {inst_err}", exc_info=True)
                    if display_name in self.algorithm_instances: del self.algorithm_instances[display_name]
                    if display_name in self.algorithms: del self.algorithms[display_name]
                    success = False
            else:
                main_logger.warning(f"No valid BaseAlgorithm subclass found in {algo_file_path.name}")
                success = False

        except ImportError as e:
            main_logger.error(f"Import error while processing {algo_file_path.name}: {e}", exc_info=False)
            success = False
        except Exception as e:
            main_logger.error(f"General error processing algorithm file {algo_file_path.name}: {e}", exc_info=True)
            success = False

        if not success and module_name in sys.modules:
             try:
                 if module_name in sys.modules and sys.modules[module_name] == module_obj:
                     del sys.modules[module_name]
             except KeyError: pass
             except NameError: pass


        return success

    def create_algorithm_ui_qt(self, algo_name, algo_config, algo_filename):
        """Creates the UI widget (card) for a single algorithm in the Main tab list."""
        try:
            if not hasattr(self, 'algo_list_layout'): return

            algo_frame = QFrame()
            algo_frame.setObjectName("CardFrame")
            algo_frame.setFrameShape(QFrame.StyledPanel)
            algo_frame.setFrameShadow(QFrame.Raised)
            algo_frame.setLineWidth(1)

            algo_layout = QVBoxLayout(algo_frame)
            algo_layout.setSpacing(6)
            algo_layout.setContentsMargins(10, 8, 10, 8)

            try: class_name_only = algo_name.split(' (')[0]
            except IndexError: class_name_only = algo_name
            display_string = f"{class_name_only} ({algo_filename})"
            name_file_label = QLabel(display_string)
            name_file_label.setFont(self.get_qfont("bold"))
            name_file_label.setStyleSheet("padding-bottom: 2px; color: #0056b3;")
            name_file_label.setToolTip(f"Thuật toán: {class_name_only}\nFile: {algo_filename}")
            algo_layout.addWidget(name_file_label)

            description = algo_config.get("description", "Không có mô tả.")
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setFont(self.get_qfont("small"))
            desc_label.setStyleSheet("color: #5a5a5a; padding-bottom: 6px;")
            desc_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            desc_label.setToolTip(description)
            algo_layout.addWidget(desc_label)

            control_row_widget = QWidget()
            control_row_layout = QHBoxLayout(control_row_widget)
            control_row_layout.setContentsMargins(0, 0, 0, 0)
            control_row_layout.setSpacing(10)

            chk_enable = QCheckBox("Kích hoạt")
            chk_enable.setToolTip("Bật/Tắt thuật toán này trong quá trình dự đoán và tính hiệu suất.")
            chk_enable.toggled.connect(lambda state, name=algo_name, chk=chk_enable: self.toggle_algorithm(name, chk))
            control_row_layout.addWidget(chk_enable)

            control_row_layout.addSpacing(5)

            chk_weight = QCheckBox("Hệ số:")
            chk_weight.setToolTip("Áp dụng hệ số nhân cho điểm số của thuật toán này khi kết hợp.")
            weight_entry = QLineEdit("1.0")
            weight_entry.setFixedWidth(70)
            weight_entry.setAlignment(Qt.AlignCenter)
            weight_entry.setValidator(self.weight_validator)
            weight_entry.setToolTip("Nhập hệ số nhân (số thực, ví dụ: 0.5, 1.0, 2.3).")

            chk_weight.toggled.connect(lambda state, name=algo_name, chk=chk_weight, entry=weight_entry: self.toggle_algorithm_weight(name, chk, entry))
            weight_entry.textChanged.connect(lambda text, name=algo_name, entry=weight_entry: self.save_algorithm_weight_from_ui(name, entry))

            chk_weight.setEnabled(False)
            weight_entry.setEnabled(False)

            control_row_layout.addWidget(chk_weight)
            control_row_layout.addWidget(weight_entry)
            control_row_layout.addStretch(1)

            algo_layout.addWidget(control_row_widget)

            self.algorithms[algo_name] = {
                'config': algo_config,
                'file': algo_filename,
                'chk_enable': chk_enable,
                'chk_weight': chk_weight,
                'weight_entry': weight_entry,
                'frame': algo_frame,
            }

            self.algo_list_layout.addWidget(algo_frame)

        except Exception as e:
            main_logger.error(f"Error creating UI for algorithm {algo_name}: {e}", exc_info=True)
            if algo_name in self.algorithms: del self.algorithms[algo_name]
            if algo_name in self.algorithm_instances: del self.algorithm_instances[algo_name]


    def toggle_algorithm(self, algo_name, chk_enable_widget):
        """Handles the toggling of the main 'Enable' checkbox for an algorithm."""
        new_main_state = chk_enable_widget.isChecked()
        state_text = "Bật" if new_main_state else "Tắt"
        main_logger.debug(f"Toggling algorithm '{algo_name}' to {state_text}")

        try:
            self._update_dependent_weight_widgets(algo_name)

            config_section = algo_name
            if not self.config.has_section(config_section): self.config.add_section(config_section)
            self.config.set(config_section, 'enabled', str(new_main_state))
            try:
                self.save_config("settings.ini")
            except Exception as save_err:
                 main_logger.error(f"Failed to save config after toggling {algo_name}: {save_err}", exc_info=True)
                 raise save_err

            self.update_status(f"Đã {state_text.lower()} thuật toán: {algo_name.split(' (')[0]}")

        except Exception as e:
            main_logger.error(f"Error toggling algorithm '{algo_name}': {e}", exc_info=True)
            try:
                chk_enable_widget.toggled.disconnect()
            except TypeError: pass
            try:
                chk_enable_widget.setChecked(not new_main_state)
                self._update_dependent_weight_widgets(algo_name)
            except Exception as revert_err:
                 main_logger.error(f"Error reverting checkbox state for '{algo_name}': {revert_err}")
            finally:
                 try:
                      chk_enable_widget.toggled.connect(lambda state, name=algo_name, chk=chk_enable_widget: self.toggle_algorithm(name, chk))
                 except Exception: pass

            QMessageBox.critical(self, "Lỗi Lưu Trạng Thái", f"Đã xảy ra lỗi khi lưu trạng thái kích hoạt cho thuật toán:\n{e}")

    def _update_dependent_weight_widgets(self, algo_name):
        """Helper to update weight widget states based on main checkbox state."""
        algo_data = self.algorithms.get(algo_name)
        if not algo_data: return

        chk_enable = algo_data.get('chk_enable')
        chk_weight = algo_data.get('chk_weight')
        weight_entry = algo_data.get('weight_entry')

        if not chk_enable or not chk_weight or not weight_entry: return

        main_enabled_state = chk_enable.isChecked()
        weight_checkbox_enabled_state = main_enabled_state
        weight_entry_enabled_state = main_enabled_state and chk_weight.isChecked()

        chk_weight.setEnabled(weight_checkbox_enabled_state)
        weight_entry.setEnabled(weight_entry_enabled_state)

    def toggle_algorithm_weight(self, algo_name, chk_weight_widget, weight_entry_widget):
        """Handles the toggling of the 'Weight Enable' checkbox."""
        algo_data = self.algorithms.get(algo_name)
        if not algo_data: return

        chk_enable = algo_data.get('chk_enable')
        if not chk_enable or not chk_enable.isChecked():
            chk_weight_widget.setChecked(False)
            weight_entry_widget.setEnabled(False)
            main_logger.debug(f"Weight toggle ignored for '{algo_name}': Main algorithm disabled.")
            return

        new_weight_state = chk_weight_widget.isChecked()
        state_text = "Bật" if new_weight_state else "Tắt"
        main_logger.debug(f"Toggling weight for algorithm '{algo_name}' to {state_text}")

        try:
            weight_entry_widget.setEnabled(new_weight_state)
            if new_weight_state:
                weight_entry_widget.setFocus()

            config_section = algo_name
            if not self.config.has_section(config_section): self.config.add_section(config_section)
            self.config.set(config_section, 'weight_enabled', str(new_weight_state))
            current_weight_text = weight_entry_widget.text().strip()
            weight_to_save = current_weight_text if self._is_valid_float_str(current_weight_text) else "1.0"
            if weight_entry_widget.text() != weight_to_save: weight_entry_widget.setText(weight_to_save)
            self.config.set(config_section, 'weight_value', weight_to_save)
            try:
                self.save_config("settings.ini")
            except Exception as save_err:
                 main_logger.error(f"Failed to save config after toggling weight for {algo_name}: {save_err}", exc_info=True)
                 raise save_err

            self.update_status(f"Đã {state_text.lower()} hệ số nhân cho: {algo_name.split(' (')[0]}")

        except Exception as e:
            main_logger.error(f"Error toggling weight enable for '{algo_name}': {e}", exc_info=True)
            try:
                chk_weight_widget.toggled.disconnect()
            except TypeError: pass
            try:
                chk_weight_widget.setChecked(not new_weight_state)
                weight_entry_widget.setEnabled(not new_weight_state)
            except Exception as revert_err:
                 main_logger.error(f"Error reverting weight checkbox state for '{algo_name}': {revert_err}")
            finally:
                 try:
                      chk_weight_widget.toggled.connect(lambda state, name=algo_name, chk=chk_weight_widget, entry=weight_entry_widget: self.toggle_algorithm_weight(name, chk, entry))
                 except Exception: pass

            QMessageBox.critical(self, "Lỗi Lưu Hệ Số", f"Đã xảy ra lỗi khi lưu trạng thái hệ số nhân:\n{e}")


    def save_algorithm_weight_from_ui(self, algo_name, weight_entry_widget):
        """Saves the weight value from the UI to config if it's valid and enabled."""
        if not weight_entry_widget.hasAcceptableInput():
            return


        algo_data = self.algorithms.get(algo_name)
        if not algo_data: return

        chk_enable = algo_data.get('chk_enable')
        chk_weight = algo_data.get('chk_weight')

        if chk_enable and chk_enable.isChecked() and chk_weight and chk_weight.isChecked():
             try:
                 weight_value = weight_entry_widget.text().strip()
                 if not self._is_valid_float_str(weight_value):
                     main_logger.warning(f"Weight validator passed but string '{weight_value}' invalid for {algo_name}. Skipping save.")
                     return

                 config_section = algo_name
                 if not self.config.has_section(config_section): self.config.add_section(config_section)

                 current_config_value = self.config.get(config_section, 'weight_value', fallback="1.0")
                 if weight_value != current_config_value:
                      self.config.set(config_section, 'weight_value', weight_value)
                      try:
                          self.save_config("settings.ini")
                          main_logger.debug(f"Saved weight '{weight_value}' for algorithm '{algo_name}'")
                      except Exception as save_err:
                           main_logger.error(f"Failed to save config after weight change for {algo_name}: {save_err}")

             except Exception as e:
                  main_logger.error(f"Error saving weight for '{algo_name}': {e}", exc_info=True)


    def reload_algorithms(self):
        """Clears and reloads algorithms for the Main tab and Optimizer tab."""
        self.update_status("Đang tải lại thuật toán...")
        QApplication.processEvents()

        self.load_algorithms()

        if self.optimizer_app_instance:
            self.optimizer_app_instance.reload_algorithms()

        self.update_status("Tải lại thuật toán hoàn tất.")


    def create_sample_algorithms(self):
        """Creates sample algorithm files if they don't exist (logic identical)."""
        main_logger.info("Creating sample algorithm files...")
        try:
            self.algorithms_dir.mkdir(parents=True, exist_ok=True)
            samples = {
                "frequency_analysis.py": textwrap.dedent("""
                    # -*- coding: utf-8 -*-
                    from algorithms.base import BaseAlgorithm
                    import datetime, json, logging
                    from collections import Counter

                    class FrequencyAnalysisAlgorithm(BaseAlgorithm):
                        def __init__(self, *args, **kwargs):
                            super().__init__(*args, **kwargs)
                            self.config = {"description": "Phân tích tần suất (nóng/lạnh) trong N ngày.", "parameters": {"history_days": 90, "hot_threshold_percent": 10, "cold_threshold_percent": 10, "hot_bonus": 20.0, "cold_bonus": 15.0, "neutral_penalty": -5.0}}
                            self._log('debug', f"{self.__class__.__name__} initialized.")
                        def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
                            scores = {f"{i:02d}": 0.0 for i in range(100)}
                            try: params = self.config.get('parameters', {}); hist_days = int(params.get('history_days', 90)); hot_p = max(1, min(49, float(params.get('hot_threshold_percent', 10)))); cold_p = max(1, min(49, float(params.get('cold_threshold_percent', 10)))); hot_b = float(params.get('hot_bonus', 20.0)); cold_b = float(params.get('cold_bonus', 15.0)); neut_p = float(params.get('neutral_penalty', -5.0))
                            except (ValueError, TypeError) as e: self._log('error', f"Invalid params: {e}"); return {}
                            start_date_limit = date_to_predict - datetime.timedelta(days=hist_days); relevant_history = [item for item in historical_results if item['date'] >= start_date_limit]
                            if not relevant_history: self._log('debug', f"No relevant history found for freq analysis up to {date_to_predict}."); return scores
                            counts = None; cache_file = None
                            if self.cache_dir:
                                end_date_for_cache = date_to_predict - datetime.timedelta(days=1); cache_key = f"freq_counts_{start_date_limit:%Y%m%d}_{end_date_for_cache:%Y%m%d}.json"; cache_file = self.cache_dir / cache_key
                                if cache_file.exists():
                                    try: counts_data = json.loads(cache_file.read_text(encoding='utf-8')); counts = {f"{int(k):02d}": v for k, v in counts_data.items() if k.isdigit()}; self._log('debug', f"Loaded counts from cache: {cache_file.name}")
                                    except Exception as e_cache: self._log('warning', f"Failed to load counts from cache {cache_file.name}: {e_cache}"); counts = None
                            if counts is None:
                                self._log('debug', f"Calculating counts for period {start_date_limit} to {date_to_predict - datetime.timedelta(days=1)}")
                                all_numbers = [f"{n:02d}" for day_data in relevant_history for n in self.extract_numbers_from_dict(day_data.get('result', {}))]
                                if not all_numbers: self._log('warning', "No numbers extracted from relevant history."); return scores
                                counts = dict(Counter(all_numbers))
                                self._log('debug', f"Calculated {len(counts)} unique number counts.")
                                if cache_file:
                                     try: cache_file.write_text(json.dumps({str(k): v for k, v in counts.items()}, indent=2), encoding='utf-8'); self._log('debug', f"Saved counts to cache: {cache_file.name}")
                                     except IOError as e_io: self._log('error', f"Failed to write counts to cache {cache_file.name}: {e_io}")
                            try:
                                if not counts: return scores
                                # Filter counts to only include '00' to '99' before sorting
                                valid_counts = {k:v for k,v in counts.items() if len(k)==2 and k.isdigit()}
                                if not valid_counts: self._log('warning', "No valid '00'-'99' counts found."); return scores

                                sorted_counts = sorted(valid_counts.items(), key=lambda item: item[1]); num_items = len(sorted_counts);
                                n_hot = max(1, int(num_items * hot_p / 100)); n_cold = max(1, int(num_items * cold_p / 100))
                                hot_numbers = {item[0] for item in sorted_counts[-n_hot:]}; cold_numbers = {item[0] for item in sorted_counts[:n_cold]}
                                self._log('debug', f"Identified {len(hot_numbers)} hot, {len(cold_numbers)} cold numbers.")

                                for num_str in scores.keys():
                                    if num_str in hot_numbers: scores[num_str] += hot_b
                                    elif num_str in cold_numbers: scores[num_str] += cold_b
                                    elif num_str in valid_counts: scores[num_str] += neut_p # Penalize neutral numbers that appeared
                                    # Numbers that never appeared get 0.0 initial score (no penalty/bonus)
                            except Exception as e: self._log('error', f"Error applying frequency bonuses: {e}", exc_info=True); return {}
                            self._log('debug', f"Frequency prediction complete for {date_to_predict}.")
                            return scores
                """).strip() + "\n",
                "date_relation.py": textwrap.dedent("""
                    # -*- coding: utf-8 -*-
                    from algorithms.base import BaseAlgorithm
                    import datetime, logging

                    class DateRelationAlgorithm(BaseAlgorithm):
                        def __init__(self, *args, **kwargs):
                            super().__init__(*args, **kwargs)
                            self.config = {"description": "Cộng điểm nếu số liên quan đến ngày/tháng/thứ/tổng.", "parameters": {"day_match_bonus": 25.0, "month_match_bonus": 15.0, "weekday_match_bonus": 10.0, "day_digit_bonus": 5.0, "sum_day_month_bonus": 8.0}}
                            self._log('debug', f"{self.__class__.__name__} initialized.")
                        def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
                            scores = {f'{i:02d}': 0.0 for i in range(100)}
                            try: params = self.config.get('parameters', {}); d_b = float(params.get('day_match_bonus', 25.0)); m_b = float(params.get('month_match_bonus', 15.0)); w_b = float(params.get('weekday_match_bonus', 10.0)); dd_b = float(params.get('day_digit_bonus', 5.0)); sum_b = float(params.get('sum_day_month_bonus', 8.0))
                            except (ValueError, TypeError) as e: self._log('error', f"Invalid params in DateRelation: {e}"); return {}
                            try:
                                day = date_to_predict.day
                                month = date_to_predict.month
                                weekday = date_to_predict.weekday() # Monday is 0, Sunday is 6
                                day_digits = str(day) # Digits of the day, e.g., '1', '5' for day 15

                                for i in range(100):
                                    num_str = f'{i:02d}'; delta = 0.0
                                    # Direct matches
                                    if i == day: delta += d_b
                                    if i == month: delta += m_b
                                    if i == weekday: delta += w_b # Matches 0-6 directly

                                    # Check if any digit of the day is present in the number
                                    if any(digit in num_str for digit in day_digits):
                                         delta += dd_b

                                    # Check if number matches sum of day and month (modulo 100)
                                    if i == (day + month) % 100:
                                         delta += sum_b

                                    scores[num_str] = delta
                                self._log('debug', f"Date relation prediction complete for {date_to_predict}")
                            except Exception as e: self._log('error', f"Error calculating date relations: {e}", exc_info=True); return {}
                            return scores
                """).strip() + "\n"
            }
            created_count = 0
            for filename, content in samples.items():
                filepath = self.algorithms_dir / filename
                if not filepath.exists():
                    try:
                        filepath.write_text(content, encoding='utf-8')
                        created_count += 1
                        main_logger.info(f"Created sample algorithm: {filename}")
                    except Exception as e:
                         main_logger.error(f"Could not write sample algorithm file '{filename}': {e}")
            if created_count > 0:
                QMessageBox.information(self, "Thuật Toán Mẫu", f"Đã tạo {created_count} file thuật toán mẫu trong thư mục 'algorithms'.\nVui lòng nhấn 'Tải lại thuật toán' để sử dụng.")
        except Exception as e:
             QMessageBox.critical(self, "Lỗi Tạo File Mẫu", f"Đã xảy ra lỗi khi tạo các file thuật toán mẫu:\n{e}")

    def show_calendar_dialog_qt(self, target_line_edit: QLineEdit, callback=None):
        """Shows a QCalendarWidget dialog to select a date."""
        if not self.results:
            QMessageBox.information(self, "Thiếu Dữ Liệu", "Chưa có dữ liệu kết quả để chọn ngày.")
            return

        min_date_dt = self.results[0]['date']
        max_date_dt = self.results[-1]['date']
        min_qdate = QDate(min_date_dt.year, min_date_dt.month, min_date_dt.day)
        max_qdate = QDate(max_date_dt.year, max_date_dt.month, max_date_dt.day)

        current_text = target_line_edit.text()
        current_qdate = QDate.currentDate()
        try:
            parsed_dt = datetime.datetime.strptime(current_text, '%d/%m/%Y').date()
            parsed_qdate = QDate(parsed_dt.year, parsed_dt.month, parsed_dt.day)
            if min_qdate <= parsed_qdate <= max_qdate:
                current_qdate = parsed_qdate
            else:
                 current_qdate = max_qdate
        except ValueError:
            current_qdate = max_qdate

        dialog = QDialog(self)
        dialog.setWindowTitle("Chọn Ngày")
        dialog.setModal(True)
        dialog_layout = QVBoxLayout(dialog)

        calendar = QCalendarWidget()
        calendar.setGridVisible(True)
        calendar.setMinimumDate(min_qdate)
        calendar.setMaximumDate(max_qdate)
        calendar.setSelectedDate(current_qdate)
        calendar.setStyleSheet("""
            QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #EAEAEA; }
            QCalendarWidget QToolButton { color: black; }
            QCalendarWidget QMenu { color: black; background-color: white; }
            QCalendarWidget QAbstractItemView:enabled { color: black; background-color: white; selection-background-color: #007BFF; selection-color: white; }
            QCalendarWidget QAbstractItemView:disabled { color: #AAAAAA; }
        """)

        dialog_layout.addWidget(calendar)

        try:
            hint_width = calendar.sizeHint().width()
            desired_min_width = max(450, int(hint_width * 1))
            calendar.setMinimumWidth(desired_min_width)
            main_logger.debug(f"Set calendar minimum width to: {desired_min_width} (Hint: {hint_width})")
        except Exception as e_cal_size:
            main_logger.warning(f"Could not set calendar minimum width, setting dialog minimum: {e_cal_size}")
            dialog.setMinimumWidth(500)


        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            selected_qdate = calendar.selectedDate()
            selected_date_obj = selected_qdate.toPyDate()
            selected_date_str = selected_date_obj.strftime('%d/%m/%Y')

            target_line_edit.setText(selected_date_str)

            if target_line_edit == self.selected_date_edit:
                self.selected_date = selected_date_obj
                main_logger.info(f"Main prediction date selected via calendar: {selected_date_obj}")
                self.update_status(f"Đã chọn ngày dự đoán: {selected_date_str}")

            if callback:
                 try: callback()
                 except Exception as cb_e: main_logger.error(f"Error executing calendar callback: {cb_e}")


    def select_previous_day(self):
        """Selects the previous available day in the results."""
        if not self.selected_date or not self.results: return
        try:
            current_index = -1
            for i, r in enumerate(self.results):
                if r['date'] == self.selected_date:
                    current_index = i
                    break

            if current_index > 0:
                previous_date = self.results[current_index - 1]['date']
                self.selected_date = previous_date
                if hasattr(self, 'selected_date_edit'):
                     self.selected_date_edit.setText(previous_date.strftime('%d/%m/%Y'))
                self.update_status(f"Đã chọn ngày: {previous_date:%d/%m/%Y}")
            else:
                self.update_status("Đang ở ngày đầu tiên trong dữ liệu.")
        except Exception as e:
             main_logger.error(f"Error selecting previous day: {e}")


    def select_next_day(self):
        """Selects the next available day in the results."""
        if not self.selected_date or not self.results: return
        try:
            current_index = -1
            for i, r in enumerate(self.results):
                if r['date'] == self.selected_date:
                    current_index = i
                    break

            if 0 <= current_index < len(self.results) - 1:
                next_date = self.results[current_index + 1]['date']
                self.selected_date = next_date
                if hasattr(self, 'selected_date_edit'):
                     self.selected_date_edit.setText(next_date.strftime('%d/%m/%Y'))
                self.update_status(f"Đã chọn ngày: {next_date:%d/%m/%Y}")
            else:
                self.update_status("Đang ở ngày cuối cùng trong dữ liệu.")
        except Exception as e:
             main_logger.error(f"Error selecting next day: {e}")


    def start_prediction_process(self):
        """Initiates the prediction process for the selected date."""
        if self.prediction_running:
            QMessageBox.warning(self, "Đang Chạy", "Quá trình dự đoán khác đang diễn ra.")
            return
        if not self.selected_date:
            QMessageBox.warning(self, "Chưa Chọn Ngày", "Vui lòng chọn ngày cần dự đoán.")
            return
        if not self.results:
            QMessageBox.warning(self, "Thiếu Dữ Liệu", "Không có dữ liệu lịch sử để thực hiện dự đoán.")
            return

        main_logger.info(f"Starting prediction process for date: {self.selected_date}")
        historical_data_for_prediction = [r for r in self.results if r['date'] < self.selected_date]
        if not historical_data_for_prediction:
            QMessageBox.warning(self, "Thiếu Lịch Sử", f"Không có dữ liệu lịch sử trước ngày {self.selected_date:%d/%m/%Y} để dự đoán.")
            return

        next_day_actual_result, next_day_actual_date = None, None
        next_day_dt = self.selected_date + datetime.timedelta(days=1)
        try:
            next_day_data_entry = next((r for r in self.results if r['date'] == next_day_dt), None)
            if next_day_data_entry:
                next_day_actual_result = next_day_data_entry['result']
                next_day_actual_date = next_day_dt
                main_logger.info(f"Found actual results for comparison date: {next_day_dt}")
        except Exception as e:
             main_logger.warning(f"Could not find or process results for comparison date {next_day_dt}: {e}")


        active_algorithm_instances = {}
        for algo_name, algo_data in self.algorithms.items():
             chk_enable = algo_data.get('chk_enable')
             instance = self.algorithm_instances.get(algo_name)
             if chk_enable and chk_enable.isChecked() and instance:
                 active_algorithm_instances[algo_name] = instance

        if not active_algorithm_instances:
            QMessageBox.warning(self, "Không Có Thuật Toán", "Không có thuật toán nào được kích hoạt trong danh sách.")
            return

        num_active_algos = len(active_algorithm_instances)
        active_names_str = ', '.join(active_algorithm_instances.keys())
        main_logger.info(f"Prediction using {num_active_algos} active algorithms: {active_names_str}")
        self.update_status(f"Bắt đầu dự đoán cho {self.selected_date:%d/%m/%Y} ({num_active_algos} thuật toán)...")

        self.prediction_running = True
        self.intermediate_results.clear()
        self.calculation_queue = queue.Queue()
        self.calculation_threads = []

        if self.calculate_dir.exists():
            main_logger.info(f"Clearing calculation cache: {self.calculate_dir}")
            try:
                for item in self.calculate_dir.iterdir():
                    try:
                        if item.is_file(): item.unlink()
                        elif item.is_dir(): shutil.rmtree(item)
                    except Exception as item_err:
                         main_logger.warning(f"Failed to delete cache item '{item.name}': {item_err}")
            except Exception as clear_cache_err:
                 main_logger.error(f"Error clearing cache directory: {clear_cache_err}", exc_info=True)


        try:
            if hasattr(self, 'predict_progress_frame'):
                self.predict_progress_frame.setVisible(True)
                if hasattr(self, 'predict_status_label'):
                     self.predict_status_label.setText("Đang chạy dự đoán...")
                     self.predict_status_label.setObjectName("ProgressRunning")
                if hasattr(self, 'predict_progressbar'):
                     self.predict_progressbar.setMaximum(num_active_algos)
                     self.predict_progressbar.setValue(0)
                QApplication.processEvents()
        except Exception as ui_err:
             main_logger.error(f"Error setting up prediction progress UI: {ui_err}", exc_info=True)


        hist_copy_for_threads = copy.deepcopy(historical_data_for_prediction)
        main_logger.info("Launching prediction worker threads...")
        for algo_name, instance in active_algorithm_instances.items():
            thread = threading.Thread(
                target=self.run_single_algorithm_prediction,
                args=(algo_name, instance, self.selected_date, hist_copy_for_threads),
                name=f"Predict-{algo_name[:20]}",
                daemon=True
            )
            self.calculation_threads.append(thread)
            thread.start()

        self._next_day_actual_result = next_day_actual_result
        self._next_day_actual_date = next_day_actual_date
        if not self.prediction_timer.isActive():
             self.prediction_timer.start(self.prediction_timer_interval)


    def run_single_algorithm_prediction(self, algo_name, algo_instance, date_to_predict, historical_results):
        """Worker thread function to run a single algorithm's predict method."""
        thread_name = threading.current_thread().name
        prediction_logger = logging.getLogger("PredictionWorker")
        prediction_logger.debug(f"[{thread_name}] Running predict for '{algo_name}' on {date_to_predict}")
        scores = {}
        success = False
        try:
            scores = algo_instance.predict(date_to_predict, historical_results)

            if not isinstance(scores, dict):
                prediction_logger.error(f"[{thread_name}] Algorithm '{algo_name}' predict() method returned type {type(scores)} instead of dict.")
                scores = {}
                success = False
            else:
                invalid_items = []
                for k, v in scores.items():
                    if not (isinstance(k, str) and len(k) == 2 and k.isdigit() and isinstance(v, (int, float))):
                        invalid_items.append((k, v))
                if invalid_items:
                    prediction_logger.warning(f"[{thread_name}] Algorithm '{algo_name}' returned {len(invalid_items)} invalid score items (key not '00'-'99' or value not number).")
                    scores = {k: v for k, v in scores.items() if (isinstance(k, str) and len(k) == 2 and k.isdigit() and isinstance(v, (int, float)))}

                success = True
                prediction_logger.debug(f"[{thread_name}] Prediction successful for '{algo_name}'. Items: {len(scores)}")

        except Exception as e:
            prediction_logger.error(f"[{thread_name}] Error running predict() for algorithm '{algo_name}': {e}", exc_info=True)
            scores = {}
            success = False
        finally:
            with self._results_lock:
                self.intermediate_results[algo_name] = scores
            self.calculation_queue.put(algo_name if success else None)
            prediction_logger.debug(f"[{thread_name}] Finished processing for '{algo_name}'. Success: {success}")


    def check_predictions_completion_qt(self):
        """Checks prediction queue and updates UI (Connected to QTimer)."""
        next_day_actual_result = getattr(self, '_next_day_actual_result', None)
        next_day_actual_date = getattr(self, '_next_day_actual_date', None)

        if not all(hasattr(self, w) and getattr(self, w) for w in ['predict_progress_frame', 'predict_progressbar', 'predict_status_label']):
            main_logger.warning("Prediction progress UI elements missing. Stopping timer.")
            if self.prediction_timer.isActive(): self.prediction_timer.stop()
            self.prediction_running = False
            if hasattr(self, '_next_day_actual_result'): del self._next_day_actual_result
            if hasattr(self, '_next_day_actual_date'): del self._next_day_actual_date
            return

        processed_signals = 0
        errors_signalled = 0
        try:
            while not self.calculation_queue.empty():
                signal = self.calculation_queue.get_nowait()
                processed_signals += 1
                if signal is None:
                    errors_signalled += 1
        except queue.Empty:
            pass
        except Exception as q_err:
             main_logger.error(f"Error reading prediction queue: {q_err}")


        total_threads = len(self.calculation_threads)
        completed_threads = total_threads - sum(1 for t in self.calculation_threads if t.is_alive())

        try:
            self.predict_progressbar.setValue(completed_threads)
            if self.prediction_running:
                 status_text = f"Đang chạy: ({completed_threads}/{total_threads}"
                 if errors_signalled > 0:
                     status_text += f" - {errors_signalled} lỗi"
                 status_text += ")"
                 self.predict_status_label.setText(status_text)
                 self.predict_status_label.setObjectName("ProgressRunning")
                 self.predict_status_label.style().unpolish(self.predict_status_label)
                 self.predict_status_label.style().polish(self.predict_status_label)
        except Exception as ui_err:
            main_logger.error(f"Error updating prediction progress UI: {ui_err}")
            if self.prediction_timer.isActive(): self.prediction_timer.stop()
            self.prediction_running = False
            if hasattr(self, '_next_day_actual_result'): del self._next_day_actual_result
            if hasattr(self, '_next_day_actual_date'): del self._next_day_actual_date
            return

        if completed_threads == total_threads:
            main_logger.info("All prediction threads completed.")
            if self.prediction_timer.isActive(): self.prediction_timer.stop()
            self.prediction_running = False

            final_status_text = ""
            final_status_obj_name = ""
            if errors_signalled > 0:
                final_status_text = f"Hoàn thành ({total_threads}/{total_threads} - {errors_signalled} lỗi)"
                final_status_obj_name = "ProgressError"
            else:
                final_status_text = f"Hoàn thành ({total_threads}/{total_threads})"
                final_status_obj_name = "ProgressSuccess"
            try:
                self.predict_status_label.setText(final_status_text)
                self.predict_status_label.setObjectName(final_status_obj_name)
                self.predict_status_label.style().unpolish(self.predict_status_label)
                self.predict_status_label.style().polish(self.predict_status_label)
            except Exception: pass


            self.update_status("Dự đoán hoàn tất. Đang tổng hợp kết quả...")
            QApplication.processEvents()

            with self._results_lock:
                collected_results = copy.deepcopy(self.intermediate_results)

            if not collected_results:
                QMessageBox.critical(self, "Lỗi", "Không thu thập được kết quả nào từ các thuật toán.")
                self.update_status("Dự đoán thất bại: không có kết quả.")
                if hasattr(self, '_next_day_actual_result'): del self._next_day_actual_result
                if hasattr(self, '_next_day_actual_date'): del self._next_day_actual_date
                return

            final_scores_dict = self.combine_algorithm_scores(collected_results)

            if not final_scores_dict:
                QMessageBox.critical(self, "Lỗi", "Không thể tổng hợp điểm số từ các thuật toán.")
                self.update_status("Dự đoán thất bại: lỗi tổng hợp điểm.")
                if hasattr(self, '_next_day_actual_result'): del self._next_day_actual_result
                if hasattr(self, '_next_day_actual_date'): del self._next_day_actual_date
                return

            final_scores_list = []
            try:
                for num_str, score in final_scores_dict.items():
                    if isinstance(num_str, str) and len(num_str) == 2 and num_str.isdigit() and isinstance(score, (int, float)):
                         final_scores_list.append((int(num_str), float(score)))
                    else:
                        main_logger.warning(f"Skipping invalid item during final score list creation: {num_str}:{score}")

                present_nums = {item[0] for item in final_scores_list}
                min_score = min((item[1] for item in final_scores_list), default=0.0)
                missing_score = min_score - 1000

                for i in range(100):
                    if i not in present_nums:
                        final_scores_list.append((i, missing_score))

                final_scores_list.sort(key=lambda item: item[1], reverse=True)
                final_scores_list = final_scores_list[:100]

            except Exception as prep_err:
                 main_logger.error(f"Error preparing final score list for display: {prep_err}", exc_info=True)
                 QMessageBox.critical(self, "Lỗi", f"Lỗi xử lý kết quả cuối cùng:\n{prep_err}")
                 self.update_status("Dự đoán thất bại: lỗi xử lý kết quả.")
                 if hasattr(self, '_next_day_actual_result'): del self._next_day_actual_result
                 if hasattr(self, '_next_day_actual_date'): del self._next_day_actual_date
                 return

            self.display_prediction_results_qt(final_scores_list, next_day_actual_result, next_day_actual_date)
            self.update_status(f"Đã hiển thị kết quả dự đoán cho ngày {self.selected_date:%d/%m/%Y}.")

            if hasattr(self, '_next_day_actual_result'): del self._next_day_actual_result
            if hasattr(self, '_next_day_actual_date'): del self._next_day_actual_date


    def combine_algorithm_scores(self, intermediate_results: dict) -> dict:
        """Combines prediction scores from multiple algorithms, applying weights from UI."""
        if not intermediate_results:
            main_logger.warning("combine_algorithm_scores called with no intermediate results.")
            return {f"{i:02d}": 100.0 for i in range(100)}

        main_logger.info(f"Combining scores from {len(intermediate_results)} algorithm results (applying weights)...")
        BASE_SCORE = 100.0
        combined_deltas = {f"{i:02d}": 0.0 for i in range(100)}
        valid_algo_count = 0
        algorithms_processed = []

        for algo_name, raw_scores_dict in intermediate_results.items():
            main_logger.debug(f"Processing results from: {algo_name}")
            algorithms_processed.append(algo_name)

            if not isinstance(raw_scores_dict, dict):
                main_logger.warning(f"Result from '{algo_name}' is not a dict. Skipping.")
                continue
            if not raw_scores_dict:
                main_logger.debug(f"Result from '{algo_name}' is empty. Skipping.")
                continue

            valid_algo_count += 1
            processed_scores_dict = copy.deepcopy(raw_scores_dict)

            weight_factor = 1.0
            apply_weight = False
            algo_ui_data = self.algorithms.get(algo_name)

            if algo_ui_data:
                chk_enable = algo_ui_data.get('chk_enable')
                chk_weight = algo_ui_data.get('chk_weight')
                weight_entry = algo_ui_data.get('weight_entry')

                main_is_enabled = chk_enable.isChecked() if chk_enable else False
                weight_is_enabled = chk_weight.isChecked() if chk_weight else False

                if main_is_enabled and weight_is_enabled:
                    if weight_entry:
                        weight_str = weight_entry.text().strip()
                        if self._is_valid_float_str(weight_str):
                            try:
                                weight_factor = float(weight_str)
                                apply_weight = True
                            except ValueError:
                                main_logger.warning(f"Invalid weight format '{weight_str}' for '{algo_name}'. Using 1.0.")
                                weight_factor = 1.0
                        else:
                            main_logger.warning(f"Invalid weight string '{weight_str}' for '{algo_name}'. Using 1.0.")
                            weight_factor = 1.0
                    else:
                        main_logger.warning(f"Weight entry widget not found for '{algo_name}'. Using 1.0.")
            else:
                 main_logger.warning(f"UI data not found for '{algo_name}' when checking weight. Using 1.0.")

            if apply_weight and weight_factor != 1.0:
                main_logger.debug(f"Applying weight factor {weight_factor:.3f} to '{algo_name}'.")
                temp_scores = {}
                num_multiplied = 0
                for num_str, delta_val in processed_scores_dict.items():
                    if isinstance(num_str, str) and len(num_str) == 2 and num_str.isdigit() and isinstance(delta_val, (int, float)):
                        try:
                            multiplied_delta = float(delta_val) * weight_factor
                            temp_scores[num_str] = multiplied_delta
                            num_multiplied += 1
                        except (ValueError, TypeError, OverflowError) as mult_err:
                            main_logger.warning(f"Error multiplying delta '{delta_val}' by weight {weight_factor} for number '{num_str}' in '{algo_name}': {mult_err}. Keeping original delta.")
                            temp_scores[num_str] = float(delta_val)
                    else:
                        pass
                processed_scores_dict = temp_scores
                main_logger.debug(f"Weighted scores calculated for {num_multiplied} numbers from '{algo_name}'.")

            numbers_processed_in_algo = 0
            errors_in_algo = 0
            for num_str, delta_val in processed_scores_dict.items():
                if isinstance(num_str, str) and len(num_str) == 2 and num_str.isdigit() and isinstance(delta_val, (int, float)):
                    try:
                        delta_float = float(delta_val)
                        combined_deltas[num_str] += delta_float
                        numbers_processed_in_algo += 1
                    except (ValueError, TypeError):
                        errors_in_algo += 1
                        main_logger.warning(f"Could not convert delta '{delta_val}' to float for number '{num_str}' from {algo_name}.")
                        continue
                else:
                     if isinstance(num_str, str) and num_str.isdigit():
                          errors_in_algo += 1
                          main_logger.warning(f"Invalid key format or non-numeric delta skipped from {algo_name}: key='{num_str}', value type={type(delta_val)}")


            if errors_in_algo > 0:
                 main_logger.warning(f"Skipped {errors_in_algo} invalid key/value pairs from '{algo_name}'.")
            main_logger.debug(f"Added {numbers_processed_in_algo} valid deltas from '{algo_name}'.")

        if valid_algo_count == 0:
            if algorithms_processed:
                 main_logger.error(f"No valid results returned from processed algorithms: {algorithms_processed}. Returning base scores.")
            else:
                 main_logger.error("No algorithms were processed. Returning base scores.")
            return {num: BASE_SCORE for num in combined_deltas.keys()}

        final_scores = {num: round(BASE_SCORE + delta, 2) for num, delta in combined_deltas.items()}
        main_logger.info(f"Successfully combined scores from {valid_algo_count} algorithms.")
        return final_scores


    def display_prediction_results_qt(self, sorted_predictions, next_day_actual_results, next_day_date):
        """Displays the prediction results in a new QDialog window."""
        if not sorted_predictions or not isinstance(sorted_predictions, list):
            main_logger.error("display_prediction_results_qt called with invalid predictions.")
            return

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Kết quả dự đoán - Ngày {self.selected_date:%d/%m/%Y}")
            dialog.resize(1250, 900)
            dialog.setMinimumSize(900, 700)
            dialog.setModal(False)
            flags = dialog.windowFlags()
            flags &= ~Qt.WindowContextHelpButtonHint
            dialog.setWindowFlags(flags)

            main_layout = QVBoxLayout(dialog)
            main_layout.setContentsMargins(10, 10, 10, 10)

            header_widget = QWidget()
            header_layout = QHBoxLayout(header_widget)
            header_layout.setContentsMargins(0,0,0,10)

            header_label = QLabel(f"Dự đoán dựa theo kết quả ngày: <b>{self.selected_date:%d/%m/%Y}</b>")
            header_label.setFont(self.get_qfont("title"))
            header_layout.addWidget(header_label)
            header_layout.addStretch(1)

            if next_day_date and next_day_actual_results:
                compare_label = QLabel(f"(So sánh KQ ngày: {next_day_date:%d/%m/%Y})")
                compare_label.setStyleSheet("font-style: italic; color: #007BFF;")
                header_layout.addWidget(compare_label)
            else:
                no_compare_label = QLabel("(Không có KQ ngày sau để so sánh)")
                no_compare_label.setStyleSheet("font-style: italic; color: #6c757d;")
                header_layout.addWidget(no_compare_label)
            main_layout.addWidget(header_widget)


            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setStyleSheet("QScrollArea { border: none; }")

            grid_container_widget = QWidget()
            scroll_area.setWidget(grid_container_widget)
            table_layout = QGridLayout(grid_container_widget)
            table_layout.setSpacing(4)


            actuals, spec = set(), -1
            if next_day_actual_results and isinstance(next_day_actual_results, dict):
                actuals = self.extract_numbers_from_result_dict(next_day_actual_results)
                spec_val = next_day_actual_results.get('special', next_day_actual_results.get('dac_biet'))
                if spec_val is not None:
                    try:
                        s = str(spec_val).strip()
                        if len(s) >= 2 and s[-2:].isdigit(): spec = int(s[-2:])
                        elif len(s) == 1 and s.isdigit(): spec = int(s)
                    except (ValueError, TypeError): spec = -1


            hit_bg_color = "#d4edda"; special_bg_color = "#fff3cd"; default_bg_color="#FFFFFF"
            hit_border_color = "#7fbf7f"; special_border_color="#ffcf40"; default_border_color="#D0D0D0"

            num_font = self.get_qfont("base")
            num_bold_font = self.get_qfont("bold")
            score_font = self.get_qfont("small")

            COLOR_HIT_FG, COLOR_SPECIAL_FG, COLOR_DEFAULT_FG = '#155724', '#856404', '#212529'
            COLOR_SCORE_HIT, COLOR_SCORE_SPECIAL, COLOR_SCORE_DEFAULT = '#1e7e34', '#b38600', '#6c757d'


            num_cols = 10
            for idx, (num, score) in enumerate(sorted_predictions):
                row, col = divmod(idx, num_cols)
                is_hit = num in actuals
                is_spec = num == spec

                cell_frame = QFrame()
                cell_layout = QVBoxLayout(cell_frame)
                cell_layout.setContentsMargins(5, 5, 5, 5)
                cell_layout.setSpacing(1)

                current_num_font = num_font
                current_num_color = COLOR_DEFAULT_FG
                current_score_color = COLOR_SCORE_DEFAULT
                current_bg_color = default_bg_color
                current_border_color = default_border_color

                if is_spec:
                    current_num_font = num_bold_font
                    current_num_color = COLOR_SPECIAL_FG
                    current_score_color = COLOR_SCORE_SPECIAL
                    current_bg_color = special_bg_color
                    current_border_color = special_border_color
                elif is_hit:
                    current_num_font = num_bold_font
                    current_num_color = COLOR_HIT_FG
                    current_score_color = COLOR_SCORE_HIT
                    current_bg_color = hit_bg_color
                    current_border_color = hit_border_color

                cell_frame.setStyleSheet(f"""
                    QFrame {{
                        border: 1px solid {current_border_color};
                        border-radius: 3px;
                        background-color: {current_bg_color};
                    }}
                """)


                label_num = QLabel(f"{num:02d}")
                label_num.setFont(current_num_font)
                label_num.setStyleSheet(f"color: {current_num_color}; background-color: transparent;")
                label_num.setAlignment(Qt.AlignCenter)

                label_score = QLabel(f"{score:.1f}")
                label_score.setFont(score_font)
                label_score.setStyleSheet(f"color: {current_score_color}; background-color: transparent;")
                label_score.setAlignment(Qt.AlignCenter)

                cell_layout.addWidget(label_num)
                cell_layout.addWidget(label_score)

                table_layout.addWidget(cell_frame, row, col)
                table_layout.setRowStretch(row, 1)
                table_layout.setColumnStretch(col, 1)


            main_layout.addWidget(scroll_area, 1)

            legend_frame = QWidget()
            legend_layout = QGridLayout(legend_frame)
            legend_layout.setContentsMargins(0, 10, 0, 0)
            legend_layout.setSpacing(5)
            legend_layout.setVerticalSpacing(8)

            legend_layout.addWidget(QLabel("<b>Chú thích:</b>"), 0, 0, 1, 3)

            hit_color_box = QLabel()
            hit_color_box.setFixedSize(18, 18)
            hit_color_box.setStyleSheet(f"background-color: {hit_bg_color}; border: 1px solid {hit_border_color};")
            legend_layout.addWidget(hit_color_box, 1, 0, Qt.AlignTop)
            legend_layout.addWidget(QLabel("Số trúng thưởng"), 1, 1, Qt.AlignTop)

            spec_color_box = QLabel()
            spec_color_box.setFixedSize(18, 18)
            spec_color_box.setStyleSheet(f"background-color: {special_bg_color}; border: 1px solid {special_border_color};")
            legend_layout.addWidget(spec_color_box, 2, 0, Qt.AlignTop)
            legend_layout.addWidget(QLabel("Số trúng GĐB"), 2, 1, Qt.AlignTop)

            legend_layout.setColumnStretch(2, 1)
            legend_layout.setRowStretch(3, 1)
            main_layout.addWidget(legend_frame)


            close_button_widget = QWidget()
            close_button_layout = QHBoxLayout(close_button_widget)
            close_button_layout.addStretch(1)
            close_button = QPushButton("Đóng")
            close_button.setObjectName("AccentButton")
            close_button.setFixedWidth(100)
            close_button.clicked.connect(dialog.accept)
            close_button_layout.addWidget(close_button)
            close_button_layout.addStretch(1)
            main_layout.addWidget(close_button_widget)

            dialog.show()
            main_logger.debug("Prediction results dialog displayed successfully.")

        except Exception as e:
             main_logger.error(f"Error displaying prediction results dialog: {e}", exc_info=True)
             QMessageBox.critical(self, "Lỗi Hiển Thị Kết Quả", f"Đã xảy ra lỗi khi hiển thị cửa sổ kết quả:\n{e}")



    def calculate_combined_performance(self):
        """Prepares and starts the performance calculation worker thread."""
        main_logger.info("Preparing for combined performance calculation...")

        if self.performance_calc_running:
            QMessageBox.warning(self, "Đang Chạy", "Quá trình tính hiệu suất khác đang diễn ra.")
            return

        start_d, end_d = None, None
        try:
            start_s = self.perf_start_date_edit.text()
            end_s = self.perf_end_date_edit.text()
            if not start_s or not end_s:
                QMessageBox.warning(self, "Thiếu Ngày", "Vui lòng chọn ngày bắt đầu và kết thúc cho khoảng tính hiệu suất.")
                return
            try:
                start_d = datetime.datetime.strptime(start_s, '%d/%m/%Y').date()
                end_d = datetime.datetime.strptime(end_s, '%d/%m/%Y').date()
            except ValueError as ve:
                QMessageBox.critical(self, "Lỗi Ngày", f"Định dạng ngày sai: {ve}")
                return
            if start_d > end_d:
                QMessageBox.warning(self, "Ngày Lỗi", "Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
                return

            if not self.results or len(self.results) < 2:
                QMessageBox.warning(self, "Thiếu Dữ Liệu", "Cần ít nhất 2 ngày dữ liệu để tính hiệu suất.")
                return
            min_d, max_d = self.results[0]['date'], self.results[-1]['date']
            if start_d < min_d or end_d > max_d:
                QMessageBox.warning(self, "Ngoài Phạm Vi", f"Khoảng TG ({start_s} - {end_s}) không hợp lệ.\nPhải nằm trong khoảng dữ liệu: [{min_d:%d/%m/%Y} - {max_d:%d/%m/%Y}]")
                return

        except Exception as e:
             main_logger.error(f"Error validating performance dates: {e}", exc_info=True)
             QMessageBox.critical(self, "Lỗi Ngày", f"Lỗi không xác định khi kiểm tra ngày:\n{e}")
             return

        active_inst = {}
        for algo_name, algo_data in self.algorithms.items():
            chk_enable = algo_data.get('chk_enable')
            instance = self.algorithm_instances.get(algo_name)
            if chk_enable and chk_enable.isChecked() and instance:
                 active_inst[algo_name] = instance

        if not active_inst:
            QMessageBox.warning(self, "Không Có Thuật Toán", "Vui lòng kích hoạt ít nhất một thuật toán để tính hiệu suất.")
            return
        active_names = list(active_inst.keys())
        main_logger.info(f"Calculating performance from {start_d} to {end_d} for algorithms: {active_names}")

        try:
            res_map = {r['date']: r['result'] for r in self.results}
            hist_cache = {}
            main_logger.debug("Building history cache for performance calculation...")
            sorted_results_for_cache = sorted(self.results, key=lambda x: x['date'])
            for i, r in enumerate(sorted_results_for_cache):
                hist_cache[r['date']] = sorted_results_for_cache[:i]
            main_logger.debug(f"History cache built: {len(hist_cache)} entries.")

            predict_dates_in_range = [start_d + datetime.timedelta(days=i) for i in range((end_d - start_d).days + 1)]
            valid_predict_dates = [
                p_date for p_date in predict_dates_in_range
                if p_date in hist_cache and (p_date + datetime.timedelta(days=1)) in res_map
            ]

            if not valid_predict_dates:
                QMessageBox.information(self, "Không Đủ Dữ Liệu", "Không tìm thấy ngày nào hợp lệ có đủ dữ liệu lịch sử và kết quả ngày sau trong khoảng đã chọn.")
                self.update_status("Tính hiệu suất thất bại: không đủ dữ liệu.")
                return

            total_days_to_test = len(valid_predict_dates)
            main_logger.info(f"Total valid days for performance test: {total_days_to_test} (From {valid_predict_dates[0]:%d/%m/%Y} to {valid_predict_dates[-1]:%d/%m/%Y})")
            date_range_str_for_status = f"{start_s} - {end_s}"

        except Exception as prep_err:
            main_logger.error(f"Error preparing data for performance calculation: {prep_err}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Chuẩn Bị Dữ Liệu", f"Đã xảy ra lỗi khi chuẩn bị dữ liệu:\n{prep_err}")
            return

        self.performance_calc_running = True
        self.perf_calc_button.setEnabled(False)

        try:
            self.perf_progress_frame.setVisible(True)
            initial_status_text = f"Đang tính: ({date_range_str_for_status} / {total_days_to_test} ngày - 0%)"
            self.perf_status_label.setText(initial_status_text)
            self.perf_status_label.setObjectName("ProgressRunning")
            self.perf_status_label.style().unpolish(self.perf_status_label)
            self.perf_status_label.style().polish(self.perf_status_label)
            self.perf_progressbar.setMaximum(total_days_to_test)
            self.perf_progressbar.setValue(0)
            QApplication.processEvents()
        except Exception as ui_err:
            main_logger.error(f"Failed to initialize/show performance progress UI: {ui_err}", exc_info=True)
            self.performance_calc_running = False
            if hasattr(self, 'perf_calc_button'): self.perf_calc_button.setEnabled(True)
            QMessageBox.critical(self, "Lỗi UI", f"Không thể hiển thị thanh tiến trình hiệu suất:\n{ui_err}")
            return

        main_logger.info("Starting performance calculation worker thread...")
        perf_thread = threading.Thread(
            target=self._performance_worker,
            args=( active_inst, res_map, hist_cache, valid_predict_dates, start_s, end_s, total_days_to_test ),
            name="PerfCalcWorker",
            daemon=True
        )
        perf_thread.start()

        if not self.performance_timer.isActive():
             self.performance_timer.start(self.performance_timer_interval)

        self.update_status(f"Bắt đầu tính hiệu suất ({total_days_to_test} ngày)...")


    def _performance_worker(self, active_instances, results_map, history_cache,
                           predict_dates_list, start_date_str, end_date_str, total_days):
        """Worker thread for calculating combined performance (logic identical)."""
        perf_logger = logging.getLogger("PerfWorker")
        perf_logger.info(f"Worker started for {len(predict_dates_list)} days.")

        stats = {
            'total_days_tested': 0, 'hits_top_1': 0, 'hits_top_3': 0, 'hits_top_5': 0, 'hits_top_10': 0,
            'special_hits_top_1': 0, 'special_hits_top_5': 0, 'special_hits_top_10': 0
        }
        errors_in_worker = 0
        date_range_str_for_status = f"{start_date_str} - {end_date_str}"

        try:
            for i, predict_dt in enumerate(predict_dates_list):
                try:
                    perf_logger.debug(f"Worker processing predict_dt: {predict_dt}")
                    check_dt = predict_dt + datetime.timedelta(days=1)
                    actual_res = results_map.get(check_dt)
                    hist_data = history_cache.get(predict_dt)

                    if actual_res is None or hist_data is None:
                        perf_logger.warning(f"Worker skipping day {predict_dt}: Missing actual ({actual_res is None}) or history ({hist_data is None}).")
                        errors_in_worker += 1
                        continue

                    day_results = {}
                    hist_copy_for_day = copy.deepcopy(hist_data)

                    for name, inst in active_instances.items():
                        try:
                            day_results[name] = inst.predict(predict_dt, hist_copy_for_day)
                        except Exception as algo_e:
                            perf_logger.error(f"Worker error in {name}.predict() on {predict_dt}: {algo_e}", exc_info=False)
                            day_results[name] = {}
                            errors_in_worker += 1

                    comb_scores = self.combine_algorithm_scores(day_results)
                    if not comb_scores:
                        perf_logger.warning(f"Combined scores empty for {predict_dt}")
                        errors_in_worker += 1
                        continue

                    valid_preds_day = []
                    for n_str, s_val in comb_scores.items():
                         if isinstance(n_str, str) and len(n_str)==2 and n_str.isdigit() and isinstance(s_val, (int,float)):
                              try: valid_preds_day.append((int(n_str), float(s_val)))
                              except (ValueError, TypeError): errors_in_worker += 1
                         else: errors_in_worker += 1
                    if not valid_preds_day:
                        perf_logger.warning(f"No valid combined predictions for {predict_dt} after validation.")
                        errors_in_worker += 1
                        continue
                    sorted_preds = sorted(valid_preds_day, key=lambda x: x[1], reverse=True)

                    actual_set = self.extract_numbers_from_result_dict(actual_res)
                    if not actual_set:
                        perf_logger.warning(f"Could not extract actual numbers for check_dt {check_dt}")
                        errors_in_worker += 1
                        continue

                    spec_val = actual_res.get('special', actual_res.get('dac_biet'))
                    actual_spec = -1
                    if spec_val is not None:
                         try:
                             s = str(spec_val).strip()
                             if len(s) >= 2 and s[-2:].isdigit(): actual_spec = int(s[-2:])
                             elif len(s) == 1 and s.isdigit(): actual_spec = int(s)
                         except (ValueError, TypeError): actual_spec = -1

                    pred_top_1 = sorted_preds[0][0] if sorted_preds else -1
                    pred_top_3 = {p[0] for p in sorted_preds[:3]}
                    pred_top_5 = {p[0] for p in sorted_preds[:5]}
                    pred_top_10 = {p[0] for p in sorted_preds[:10]}

                    if pred_top_1 != -1 and pred_top_1 in actual_set: stats['hits_top_1'] += 1
                    if actual_set.intersection(pred_top_3): stats['hits_top_3'] += 1
                    if actual_set.intersection(pred_top_5): stats['hits_top_5'] += 1
                    if actual_set.intersection(pred_top_10): stats['hits_top_10'] += 1

                    if actual_spec != -1:
                        if pred_top_1 == actual_spec: stats['special_hits_top_1'] += 1
                        if actual_spec in pred_top_5: stats['special_hits_top_5'] += 1
                        if actual_spec in pred_top_10: stats['special_hits_top_10'] += 1

                    stats['total_days_tested'] += 1

                except Exception as day_e:
                    perf_logger.error(f"Worker unexpected error processing day {predict_dt}: {day_e}", exc_info=True)
                    errors_in_worker += 1

                if (i + 1) % 10 == 0 or (i + 1) == total_days:
                    progress_payload = {
                        'current': i + 1, 'total': total_days,
                        'errors': errors_in_worker, 'range_str': date_range_str_for_status
                    }
                    if hasattr(self, 'perf_queue') and self.perf_queue:
                        try: self.perf_queue.put({'type': 'progress', 'payload': progress_payload})
                        except Exception as q_put_err: perf_logger.error(f"Error putting progress to queue: {q_put_err}")
                    else: perf_logger.warning("perf_queue not found in worker, cannot send progress.")

            finished_payload = {'stats': stats, 'errors': errors_in_worker}
            if hasattr(self, 'perf_queue') and self.perf_queue:
                try: self.perf_queue.put({'type': 'finished', 'payload': finished_payload})
                except Exception as q_put_err: perf_logger.error(f"Error putting finished payload to queue: {q_put_err}")
            else: perf_logger.warning("perf_queue not found in worker, cannot send finished signal.")
            perf_logger.info(f"Worker finished. Days successfully tested: {stats['total_days_tested']}, Total Errors: {errors_in_worker}")

        except Exception as worker_err:
            perf_logger.critical(f"Worker failed critically: {worker_err}", exc_info=True)
            if hasattr(self, 'perf_queue') and self.perf_queue:
                try: self.perf_queue.put({'type': 'error', 'payload': f"Lỗi nghiêm trọng worker: {worker_err}"})
                except Exception as q_put_err: perf_logger.error(f"Error putting critical error to queue: {q_put_err}")
            else: perf_logger.warning("perf_queue not found in worker, cannot send critical error.")


    def _check_perf_queue(self):
        """Checks the performance queue and updates the UI (Identical logic, targets PyQt widgets)."""
        widgets_to_check = ['perf_status_label', 'perf_progressbar', 'perf_calc_button', 'performance_text']
        widgets_ok = all(hasattr(self, w_name) and getattr(self, w_name)
                           for w_name in widgets_to_check)
        if not widgets_ok:
            main_logger.warning("Performance UI elements missing. Stopping performance queue check.")
            if self.performance_timer.isActive(): self.performance_timer.stop()
            self.performance_calc_running = False
            return

        try:
            while not self.perf_queue.empty():
                message = self.perf_queue.get_nowait()
                msg_type = message.get("type")
                payload = message.get("payload")

                if msg_type == "progress":
                    current = payload.get('current', 0)
                    total = payload.get('total', 1)
                    errors = payload.get('errors', 0)
                    range_str = payload.get('range_str', '...')
                    percent = (current / total * 100) if total > 0 else 0
                    status_text = f"Đang tính: ({range_str} / {total} ngày - {percent:.0f}%)"
                    if errors > 0: status_text += f" ({errors} lỗi)"
                    try:
                        self.perf_progressbar.setValue(current)
                        self.perf_status_label.setText(status_text)
                        self.perf_status_label.setObjectName("ProgressRunning")
                        self.perf_status_label.style().unpolish(self.perf_status_label)
                        self.perf_status_label.style().polish(self.perf_status_label)
                    except Exception as ui_err: main_logger.error(f"Error updating perf progress UI: {ui_err}")

                elif msg_type == "error":
                    error_msg = payload
                    main_logger.error(f"Error from performance worker: {error_msg}")
                    QMessageBox.critical(self, "Lỗi Tính Toán", f"Đã xảy ra lỗi trong quá trình tính hiệu suất:\n{error_msg}")
                    if self.performance_timer.isActive(): self.performance_timer.stop()
                    self.performance_calc_running = False
                    try:
                        self.perf_calc_button.setEnabled(True)
                        self.perf_status_label.setText(f"Thất bại: {error_msg}")
                        self.perf_status_label.setObjectName("ProgressError")
                        self.perf_status_label.style().unpolish(self.perf_status_label)
                        self.perf_status_label.style().polish(self.perf_status_label)
                        self.perf_progress_frame.setVisible(False)
                    except Exception: pass
                    self.update_status("Tính hiệu suất thất bại do lỗi.")
                    return

                elif msg_type == "finished":
                    main_logger.info("Performance calculation finished signal received.")
                    if self.performance_timer.isActive(): self.performance_timer.stop()
                    self.performance_calc_running = False
                    stats = payload.get('stats', {})
                    errors = payload.get('errors', 0)
                    total_tested = stats.get('total_days_tested', 0)

                    try:
                        self.perf_calc_button.setEnabled(True)
                        start_s = self.perf_start_date_edit.text()
                        end_s = self.perf_end_date_edit.text()
                        date_range_str_final = f"{start_s} - {end_s}"
                        final_status_text = ""
                        final_status_obj_name = ""

                        if total_tested == 0:
                             final_status_text = f"Hoàn thành: ({date_range_str_final} / 0 ngày)"
                             final_status_obj_name = "ProgressError"
                        elif errors > 0:
                             final_status_text = f"Hoàn thành: ({date_range_str_final} / {total_tested} ngày - {errors} lỗi)"
                             final_status_obj_name = "ProgressError"
                        else:
                             final_status_text = f"Hoàn thành: ({date_range_str_final} / {total_tested} ngày)"
                             final_status_obj_name = "ProgressSuccess"

                        self.perf_status_label.setText(final_status_text)
                        self.perf_status_label.setObjectName(final_status_obj_name)
                        self.perf_status_label.style().unpolish(self.perf_status_label)
                        self.perf_status_label.style().polish(self.perf_status_label)
                        QTimer.singleShot(3000, lambda: self.perf_progress_frame.setVisible(False) if hasattr(self, 'perf_progress_frame') else None)

                    except Exception as ui_err: main_logger.error(f"Error in final perf UI update: {ui_err}")

                    if total_tested > 0:
                        active_algo_details = []
                        active_names = [ n for n, d in self.algorithms.items() if d.get('chk_enable') and d['chk_enable'].isChecked()]
                        for name in active_names:
                            detail = name.split(' (')[0]
                            if name in self.algorithms:
                                algo_data = self.algorithms[name]
                                chk_weight = algo_data.get('chk_weight')
                                weight_entry = algo_data.get('weight_entry')
                                if chk_weight and chk_weight.isChecked() and weight_entry:
                                    w_val_str = weight_entry.text().strip()
                                    if self._is_valid_float_str(w_val_str):
                                        try:
                                            w_f = float(w_val_str)
                                            if w_f != 1.0: detail += f" [x{w_f:.2f}]"
                                        except ValueError: pass
                            active_algo_details.append(detail)

                        try:
                            self.performance_text.clear()
                            cursor = self.performance_text.textCursor()

                            def insert_perf_text(text, fmt_name="normal"):
                                fmt = self.perf_text_formats.get(fmt_name, self.perf_text_formats["normal"])
                                cursor.insertText(text, fmt)

                            insert_perf_text("=== KẾT QUẢ HIỆU SUẤT KẾT HỢP ===\n", "section_header")

                            algo_list_str = f"Thuật toán ({len(active_algo_details)}): {', '.join(active_algo_details)}"
                            max_len = 80
                            if len(algo_list_str) > max_len: algo_list_str = algo_list_str[:max_len-3] + "..."
                            insert_perf_text(f"{algo_list_str}\n")

                            if errors > 0: insert_perf_text(f"Số lỗi gặp phải: {errors}\n", "error")

                            insert_perf_text("\n--- Tỷ lệ trúng (Ít nhất 1 số trong Top) ---\n")
                            acc1=(stats['hits_top_1']/total_tested*100)if total_tested else 0
                            acc3=(stats['hits_top_3']/total_tested*100)if total_tested else 0
                            acc5=(stats['hits_top_5']/total_tested*100)if total_tested else 0
                            acc10=(stats['hits_top_10']/total_tested*100)if total_tested else 0
                            insert_perf_text(f"Top 1 : {stats['hits_top_1']:>4} / {total_tested:<4} ({acc1:6.1f}%)\n")
                            insert_perf_text(f"Top 3 : {stats['hits_top_3']:>4} / {total_tested:<4} ({acc3:6.1f}%)\n")
                            insert_perf_text(f"Top 5 : {stats['hits_top_5']:>4} / {total_tested:<4} ({acc5:6.1f}%)\n")
                            insert_perf_text(f"Top 10: {stats['hits_top_10']:>4} / {total_tested:<4} ({acc10:6.1f}%)\n\n")

                            insert_perf_text("--- Tỷ lệ trúng GĐB (Trong Top) ---\n")
                            s_acc1=(stats['special_hits_top_1']/total_tested*100)if total_tested else 0
                            s_acc5=(stats['special_hits_top_5']/total_tested*100)if total_tested else 0
                            s_acc10=(stats['special_hits_top_10']/total_tested*100)if total_tested else 0
                            insert_perf_text(f"Top 1 : {stats['special_hits_top_1']:>4} / {total_tested:<4} ({s_acc1:6.1f}%)\n")
                            insert_perf_text(f"Top 5 : {stats['special_hits_top_5']:>4} / {total_tested:<4} ({s_acc5:6.1f}%)\n")
                            insert_perf_text(f"Top 10: {stats['special_hits_top_10']:>4} / {total_tested:<4} ({s_acc10:6.1f}%)\n")

                        except Exception as text_err:
                            main_logger.error(f"Error updating performance text area: {text_err}")
                            self.performance_text.setPlainText(f"Lỗi hiển thị kết quả:\n{text_err}")

                        try:
                            hist_f = self.config_dir / "performance_history.ini"
                            cfg_hist = configparser.ConfigParser(interpolation=None)
                            if hist_f.exists(): cfg_hist.read(hist_f, encoding='utf-8')
                            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                            sec_name = f"Perf_{ts}_{start_s.replace('/','')}_{end_s.replace('/','')}"
                            save_data = {
                                'timestamp': datetime.datetime.now().isoformat(), 'start_date': start_s, 'end_date': end_s,
                                'algorithms_with_weights': ', '.join(active_algo_details), 'total_days_tested': str(total_tested), 'errors': str(errors),
                                **{k: str(stats.get(k, 0)) for k, v in stats.items() if k.startswith(('hits_', 'special_hits_'))},
                                'acc_top_1_pct': f"{acc1:.1f}", 'acc_top_3_pct': f"{acc3:.1f}", 'acc_top_5_pct': f"{acc5:.1f}", 'acc_top_10_pct': f"{acc10:.1f}",
                                'spec_acc_top_1_pct': f"{s_acc1:.1f}", 'spec_acc_top_5_pct': f"{s_acc5:.1f}", 'spec_acc_top_10_pct': f"{s_acc10:.1f}"
                            }
                            cfg_hist[sec_name] = save_data
                            with open(hist_f, 'w', encoding='utf-8') as f_hist: cfg_hist.write(f_hist)
                            main_logger.info(f"Saved performance results to: {hist_f.name}")
                        except Exception as save_hist_err:
                            main_logger.error(f"Error saving performance history: {save_hist_err}", exc_info=True)
                            QMessageBox.warning(self, "Lỗi Lưu History", f"Không thể lưu lịch sử hiệu suất:\n{save_hist_err}")

                        self.update_status("Tính toán và hiển thị hiệu suất thành công.")

                    else:
                         QMessageBox.information(self, "Không Có Kết Quả", "Không thể hoàn thành kiểm tra cho bất kỳ ngày nào trong khoảng đã chọn.")
                         self.performance_text.setPlainText("Không có dữ liệu hiệu suất để hiển thị.")
                         self.update_status("Tính hiệu suất thất bại: không có ngày hợp lệ.")

                    return

        except queue.Empty:
            pass
        except Exception as e:
            main_logger.error(f"Error checking/processing performance queue: {e}", exc_info=True)
            if self.performance_timer.isActive(): self.performance_timer.stop()
            self.performance_calc_running = False
            try:
                self.perf_calc_button.setEnabled(True)
                self.perf_status_label.setText(f"Lỗi Queue: {e}")
                self.perf_status_label.setObjectName("ProgressError")
                self.perf_status_label.style().unpolish(self.perf_status_label)
                self.perf_status_label.style().polish(self.perf_status_label)
                self.perf_progress_frame.setVisible(False)
            except Exception: pass
            return



    def load_performance_data(self):
        """Loads the last saved performance data into the QTextEdit."""
        try:
            hist_f = self.config_dir / "performance_history.ini"
            if not hasattr(self, 'performance_text'): return
            self.performance_text.clear()
            cursor = self.performance_text.textCursor()

            def insert_perf_text(text, fmt_name="normal"):
                fmt = self.perf_text_formats.get(fmt_name, self.perf_text_formats["normal"])
                cursor.insertText(text, fmt)

            if hist_f.exists():
                cfg_hist = configparser.ConfigParser(interpolation=None)
                try: cfg_hist.read(hist_f, encoding='utf-8')
                except Exception as read_err:
                    insert_perf_text(f"Lỗi đọc history:\n{read_err}\n", "error")
                    return

                if cfg_hist.sections():
                    last_sec_name = cfg_hist.sections()[-1]
                    last_data = cfg_hist[last_sec_name]
                    ts_str = last_data.get('timestamp', '')
                    ts_display = ts_str
                    try:
                        ts_dt = datetime.datetime.fromisoformat(ts_str)
                        ts_display = ts_dt.strftime('%d/%m/%Y %H:%M:%S')
                    except: pass

                    start_s = last_data.get('start_date','?')
                    end_s = last_data.get('end_date','?')

                    insert_perf_text(f"=== HIỆU SUẤT LẦN CUỐI ({start_s} - {end_s}, Lưu lúc: {ts_display}) ===\n", "section_header")

                    total_t = int(last_data.get('total_days_tested', 0))
                    algo_str_key = 'algorithms_with_weights' if 'algorithms_with_weights' in last_data else 'algorithms'
                    algo_str = f"Thuật toán: {last_data.get(algo_str_key, 'N/A')}"
                    max_len = 80
                    if len(algo_str) > max_len: algo_str = algo_str[:max_len-3] + "..."
                    insert_perf_text(f"{algo_str}\n")

                    errors = int(last_data.get('errors', 0))
                    if errors > 0: insert_perf_text(f"Lỗi: {errors}\n", "error")

                    insert_perf_text("\n--- Tỷ lệ trúng ---\n");
                    h1,h3,h5,h10=int(last_data.get('hits_top_1',0)),int(last_data.get('hits_top_3',0)),int(last_data.get('hits_top_5',0)),int(last_data.get('hits_top_10',0))
                    a1,a3,a5,a10=float(last_data.get('acc_top_1_pct','0.0')),float(last_data.get('acc_top_3_pct','0.0')),float(last_data.get('acc_top_5_pct','0.0')),float(last_data.get('acc_top_10_pct','0.0'))
                    insert_perf_text(f"Top 1 : {h1:>4} / {total_t:<4} ({a1:6.1f}%)\n");
                    insert_perf_text(f"Top 3 : {h3:>4} / {total_t:<4} ({a3:6.1f}%)\n");
                    insert_perf_text(f"Top 5 : {h5:>4} / {total_t:<4} ({a5:6.1f}%)\n");
                    insert_perf_text(f"Top 10: {h10:>4} / {total_t:<4} ({a10:6.1f}%)\n\n")

                    insert_perf_text("--- Tỷ lệ trúng GĐB ---\n");
                    sh1,sh5,sh10=int(last_data.get('special_hits_top_1',0)),int(last_data.get('special_hits_top_5',0)),int(last_data.get('special_hits_top_10',0));
                    sa1,sa5,sa10=float(last_data.get('spec_acc_top_1_pct','0.0')),float(last_data.get('spec_acc_top_5_pct','0.0')),float(last_data.get('spec_acc_top_10_pct','0.0'))
                    insert_perf_text(f"Top 1 : {sh1:>4} / {total_t:<4} ({sa1:6.1f}%)\n");
                    insert_perf_text(f"Top 5 : {sh5:>4} / {total_t:<4} ({sa5:6.1f}%)\n");
                    insert_perf_text(f"Top 10: {sh10:>4} / {total_t:<4} ({sa10:6.1f}%)\n")

                else:
                    insert_perf_text("Chưa có lịch sử hiệu suất nào được lưu.")
            else:
                insert_perf_text("Nhấn 'Tính Toán' để xem hiệu suất kết hợp của các thuật toán đang được kích hoạt.")

        except Exception as e:
             main_logger.error(f"Error loading performance history: {e}", exc_info=True)
             try:
                 self.performance_text.clear()
                 cursor = self.performance_text.textCursor()
                 insert_perf_text(f"Lỗi tải lịch sử hiệu suất:\n{e}", "error")
             except Exception: pass


    def extract_numbers_from_result_dict(self, result_dict: dict) -> set:
        """Extracts 2-digit lottery numbers from a result dictionary (Identical Logic)."""
        numbers = set()
        keys_to_ignore = {'date','_id','source','day_of_week','sign','created_at','updated_at','province_name','province_id'}
        if not isinstance(result_dict, dict):
            return numbers

        for key, value in result_dict.items():
            if key in keys_to_ignore:
                continue

            values_to_check = []
            if isinstance(value, (list, tuple)):
                values_to_check.extend(value)
            elif value is not None:
                values_to_check.append(value)

            for item in values_to_check:
                if item is None: continue
                try:
                    s_item = str(item).strip()
                    num = -1
                    if len(s_item) >= 2 and s_item[-2:].isdigit():
                        num = int(s_item[-2:])
                    elif len(s_item) == 1 and s_item.isdigit():
                        num = int(s_item)
                    if 0 <= num <= 99:
                        numbers.add(num)
                except (ValueError, TypeError):
                    pass
        return numbers

    def setup_tools_tab(self):
        main_logger.debug("Setting up Tools tab UI (PyQt5)...")
        tools_tab_layout = QVBoxLayout(self.tools_tab_frame)
        tools_tab_layout.setContentsMargins(15, 15, 15, 15)
        tools_tab_layout.setSpacing(10)

        control_frame = QWidget()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 0, 0, 0)
        reload_tools_button = QPushButton("Tải lại Danh sách Công cụ")
        reload_tools_button.setToolTip("Quét lại thư mục 'tools' và tải lại danh sách.")
        reload_tools_button.clicked.connect(self.reload_tools)
        control_layout.addWidget(reload_tools_button)
        control_layout.addStretch(1)
        tools_tab_layout.addWidget(control_frame)

        list_groupbox = QGroupBox("Danh sách Công cụ có sẵn (.pyw)")
        list_layout = QVBoxLayout(list_groupbox)
        list_layout.setContentsMargins(5, 10, 5, 5)

        self.tools_scroll_area = QScrollArea()
        self.tools_scroll_area.setWidgetResizable(True)
        self.tools_scroll_area.setStyleSheet("QScrollArea { background-color: #FDFDFD; border: none; }")

        self.tools_scroll_widget = QWidget()
        self.tools_scroll_area.setWidget(self.tools_scroll_widget)
        self.tools_list_layout = QVBoxLayout(self.tools_scroll_widget)
        self.tools_list_layout.setAlignment(Qt.AlignTop)
        self.tools_list_layout.setSpacing(8)

        self.initial_tools_label = QLabel("Đang tải công cụ...")
        self.initial_tools_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_tools_label.setAlignment(Qt.AlignCenter)
        self.tools_list_layout.addWidget(self.initial_tools_label)

        list_layout.addWidget(self.tools_scroll_area)
        tools_tab_layout.addWidget(list_groupbox)
        main_logger.debug("Tools tab UI setup complete.")

    def reload_tools(self):
        self.update_status("Đang tải lại danh sách công cụ...")
        QApplication.processEvents()
        self.load_tools()
        self.update_status("Tải lại công cụ hoàn tất.")

    def load_tools(self):
        main_logger.info("Scanning and loading tools for Tools tab (PyQt5)...")

        if not hasattr(self, 'tools_list_layout'):
            main_logger.error("Tools list layout (tools_list_layout) not found. Cannot load tool UI.")
            return

        # Clear existing tool UI elements
        while self.tools_list_layout.count() > 0:
            item = self.tools_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Ensure initial_tools_label is reset if it was removed
        if not hasattr(self, 'initial_tools_label') or not self.initial_tools_label:
             self.initial_tools_label = QLabel("Đang tải công cụ...")
             self.initial_tools_label.setStyleSheet("font-style: italic; color: #6c757d;")
             self.initial_tools_label.setAlignment(Qt.AlignCenter)
        # Add it back temporarily, it will be removed if tools are found
        if self.tools_list_layout.indexOf(self.initial_tools_label) == -1:
             self.tools_list_layout.addWidget(self.initial_tools_label)


        if not hasattr(self, 'loaded_tools'): # Should be initialized in __init__
            self.loaded_tools = {}
        self.loaded_tools.clear()
        count_success, count_failed = 0, 0

        if not self.tools_dir.is_dir():
            main_logger.warning(f"Tools directory not found: {self.tools_dir}.")
            self.initial_tools_label.setText(f"Lỗi: Không tìm thấy thư mục công cụ:\n{self.tools_dir}")
            return

        try:
            tool_files_to_load = [
                f for f in self.tools_dir.glob('*.pyw') # Scan for .pyw files
                if f.is_file()
            ]
            main_logger.debug(f"Found {len(tool_files_to_load)} potential .pyw tool files.")
        except Exception as e:
            main_logger.error(f"Error scanning tools directory: {e}", exc_info=True)
            self.initial_tools_label.setText(f"Lỗi đọc thư mục công cụ:\n{e}")
            return

        has_tools = False
        for tool_path in tool_files_to_load:
            if self.initial_tools_label and self.tools_list_layout.indexOf(self.initial_tools_label) != -1:
                self.tools_list_layout.removeWidget(self.initial_tools_label)
                self.initial_tools_label.deleteLater()
                self.initial_tools_label = None # Mark as removed

            main_logger.debug(f"Processing tool file: {tool_path.name}")
            try:
                tool_name, tool_desc = self.extract_tool_info_from_file(tool_path)
                self.loaded_tools[str(tool_path)] = {'name': tool_name, 'description': tool_desc, 'path': tool_path}
                self.create_tool_ui_qt(tool_name, tool_desc, tool_path)
                count_success += 1
                has_tools = True
            except Exception as e:
                main_logger.error(f"Error processing tool file {tool_path.name}: {e}", exc_info=True)
                count_failed += 1
         
        if not has_tools and self.initial_tools_label: # If no tools were successfully processed
             self.initial_tools_label.setText("Không tìm thấy file công cụ (.pyw) nào trong thư mục 'tools'.")


        status_msg = f"Đã tải {count_success} công cụ"
        if count_failed > 0:
            status_msg += f", lỗi {count_failed} file"
        self.update_status(status_msg)

        if count_failed > 0:
            QMessageBox.warning(self, "Lỗi Tải Công Cụ", f"Đã xảy ra lỗi khi tải {count_failed} file công cụ.\nKiểm tra file log để biết chi tiết.")

    def extract_tool_info_from_file(self, tool_path: Path):
        display_name = tool_path.name
        description = "Không có mô tả." # Default description

        try:
            source_code = tool_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source_code)

            # Attempt to get module-level docstring for description
            module_docstring = ast.get_docstring(tree)
            if module_docstring:
                description = module_docstring.strip().splitlines()[0] # Use first line

            # Search for setWindowTitle calls
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Attribute): # e.g., self.setWindowTitle, app.setWindowTitle
                        func_name = node.func.attr
                    elif isinstance(node.func, ast.Name): # e.g., setWindowTitle (if imported directly)
                        func_name = node.func.id

                    if func_name == 'setWindowTitle':
                        if node.args:
                            first_arg = node.args[0]
                            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str): # Python 3.8+
                                display_name = first_arg.value
                                break
                            elif hasattr(ast, 'Str') and isinstance(first_arg, ast.Str) and isinstance(first_arg.s, str): # Python < 3.8
                                display_name = first_arg.s
                                break
        except FileNotFoundError:
            main_logger.error(f"Tool file not found for info extraction: {tool_path}")
        except SyntaxError:
            main_logger.warning(f"Syntax error in tool file {tool_path.name}, cannot extract info via AST.")
        except Exception as e:
            main_logger.error(f"Error extracting info from {tool_path.name} using AST: {e}", exc_info=True)
        
        # Fallback for description if AST fails or no docstring: check for a specific comment
        if description == "Không có mô tả.":
             try:
                 with tool_path.open('r', encoding='utf-8', errors='ignore') as f:
                     for line in f:
                         stripped_line = line.strip()
                         if stripped_line.startswith('# DESC:'):
                             description = stripped_line[len('# DESC:'):].strip()
                             break
                         if stripped_line and not stripped_line.startswith('#'): # Stop if non-comment line found early
                             break
             except Exception as e_comment:
                 main_logger.warning(f"Could not read tool {tool_path.name} for comment-based description: {e_comment}")

        return display_name, description

    def create_tool_ui_qt(self, display_name, description, tool_path: Path):
        try:
            if not hasattr(self, 'tools_list_layout'): return

            tool_frame = QFrame()
            tool_frame.setObjectName("CardFrame")
            tool_frame.setFrameShape(QFrame.StyledPanel)
            tool_frame.setFrameShadow(QFrame.Raised)
            tool_frame.setLineWidth(1)

            tool_layout = QHBoxLayout(tool_frame)
            tool_layout.setSpacing(10)
            tool_layout.setContentsMargins(10, 8, 10, 8)

            info_widget = QWidget()
            info_v_layout = QVBoxLayout(info_widget)
            info_v_layout.setContentsMargins(0,0,0,0)
            info_v_layout.setSpacing(3)

            name_label = QLabel(display_name)
            name_label.setFont(self.get_qfont("bold"))
            name_label.setStyleSheet("color: #0056b3;")
            name_label.setToolTip(f"Tên công cụ: {display_name}")
            info_v_layout.addWidget(name_label)

            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setFont(self.get_qfont("small"))
            desc_label.setStyleSheet("color: #5a5a5a;")
            desc_label.setToolTip(description)
            info_v_layout.addWidget(desc_label)

            file_label = QLabel(f"File: {tool_path.name}")
            file_label.setFont(self.get_qfont("italic_small"))
            file_label.setStyleSheet("color: #6c757d;")
            info_v_layout.addWidget(file_label)

            tool_layout.addWidget(info_widget, 1)

            run_button = QPushButton("Chạy Tool")
            run_button.setObjectName("ListAccentButton")
            run_button.setToolTip(f"Chạy công cụ: {tool_path.name}")
            run_button.setFixedWidth(100)
            run_button.clicked.connect(lambda: self.run_tool(str(tool_path)))
            
            button_container = QWidget()
            button_v_layout = QVBoxLayout(button_container)
            button_v_layout.addWidget(run_button, alignment=Qt.AlignVCenter | Qt.AlignRight) # Align button
            button_v_layout.setContentsMargins(0,0,0,0)

            tool_layout.addWidget(button_container)

            self.tools_list_layout.addWidget(tool_frame)

        except Exception as e:
            main_logger.error(f"Error creating UI for tool {tool_path.name}: {e}", exc_info=True)

    def run_tool(self, tool_path_str: str):
        tool_path = Path(tool_path_str)
        main_logger.info(f"Attempting to run tool: {tool_path}")
        if not tool_path.exists():
            QMessageBox.critical(self, "Lỗi Chạy Tool", f"File công cụ không tồn tại:\n{tool_path}")
            self.update_status(f"Lỗi: File công cụ {tool_path.name} không tồn tại.")
            return

        try:
            interpreter = 'pythonw' if sys.platform == "win32" else 'python3'
            subprocess.Popen([interpreter, str(tool_path)])
            self.update_status(f"Đã khởi chạy công cụ: {tool_path.name}")
        except FileNotFoundError:
            try: # Fallback to 'python' if 'python3' or 'pythonw' not found
                 subprocess.Popen(['python', str(tool_path)])
                 self.update_status(f"Đã khởi chạy công cụ (với 'python'): {tool_path.name}")
            except FileNotFoundError:
                 QMessageBox.critical(self, "Lỗi Chạy Tool", f"Không tìm thấy trình thông dịch Python ('{interpreter}' hoặc 'python').\nHãy đảm bảo Python đã được cài đặt và thêm vào PATH.")
                 main_logger.error(f"Python interpreter not found when trying to run tool: {tool_path.name}")
                 self.update_status(f"Lỗi: Không tìm thấy trình thông dịch Python cho {tool_path.name}.")
            except Exception as e_fallback:
                 QMessageBox.critical(self, "Lỗi Chạy Tool", f"Đã xảy ra lỗi khi chạy công cụ (với 'python'):\n{tool_path.name}\n\nLỗi: {e_fallback}")
                 main_logger.error(f"Error running tool {tool_path.name} with 'python': {e_fallback}", exc_info=True)
                 self.update_status(f"Lỗi khi chạy {tool_path.name} với 'python'.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Chạy Tool", f"Đã xảy ra lỗi khi chạy công cụ:\n{tool_path.name}\n\nLỗi: {e}")
            main_logger.error(f"Error running tool {tool_path.name}: {e}", exc_info=True)
            self.update_status(f"Lỗi khi chạy {tool_path.name}.")

    def update_status(self, message: str):
        """Updates the status bar text and logs the message."""
        status_type = "info"
        lower_message = message.lower()
        if "lỗi" in lower_message or "fail" in lower_message or "error" in lower_message or "thất bại" in lower_message:
            status_type = "error"
        elif "success" in lower_message or "thành công" in lower_message or "hoàn tất" in lower_message:
            status_type = "success"

        if hasattr(self, 'status_bar_label'):
            self.status_bar_label.setText(f"Trạng thái: {message}")
            self.status_bar_label.setProperty("status", status_type)
            self.status_bar_label.style().unpolish(self.status_bar_label)
            self.status_bar_label.style().polish(self.status_bar_label)
            main_logger.info(f"Status Update: {message}")
        else:
            main_logger.info(f"Status Update (No Label): {message}")

    def closeEvent(self, event):
        """Handle window close event."""
        main_logger.info("Close event triggered.")
        if hasattr(self, 'optimizer_app_instance') and self.optimizer_app_instance and self.optimizer_app_instance.optimizer_running:
            reply = QMessageBox.question(self, 'Xác Nhận Thoát',
                                         "Quá trình tối ưu hóa đang chạy. Bạn có chắc chắn muốn thoát?\nQuá trình sẽ bị dừng.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                main_logger.info("User confirmed exit while optimizer running. Stopping optimizer.")
                try:
                     self.optimizer_app_instance.stop_optimization(force_stop=True)
                     time.sleep(0.1) # Give it a moment to process the stop
                except Exception as stop_err:
                     main_logger.error(f"Error stopping optimizer on close: {stop_err}")
                event.accept()
            else:
                main_logger.info("User cancelled exit.")
                event.ignore()
                return

        # Stop timers
        if hasattr(self, 'prediction_timer') and self.prediction_timer.isActive():
            self.prediction_timer.stop()
            main_logger.debug("Stopped prediction timer.")
        if hasattr(self, 'performance_timer') and self.performance_timer.isActive():
            self.performance_timer.stop()
            main_logger.debug("Stopped performance timer.")
        if hasattr(self, 'optimizer_app_instance') and self.optimizer_app_instance:
             if self.optimizer_app_instance.optimizer_timer.isActive():
                  self.optimizer_app_instance.optimizer_timer.stop()
                  main_logger.debug("Stopped optimizer queue timer.")
             if self.optimizer_app_instance.display_timer.isActive():
                  self.optimizer_app_instance.display_timer.stop()
                  main_logger.debug("Stopped optimizer display timer.")


        main_logger.info("Proceeding with application shutdown.")
        logging.shutdown()
        event.accept()


def main():
    """Main function: Initializes QApplication and runs the application."""
    try:
        if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
             QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
             print("Enabled Qt High DPI Scaling (AA_EnableHighDpiScaling).")
        if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
             QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
             print("Enabled Qt High DPI Pixmaps (AA_UseHighDpiPixmaps).")
    except Exception as e_dpi:
         print(f"Could not set Qt High DPI attributes: {e_dpi}")


    app = QApplication(sys.argv)
    app.setApplicationName("LotteryPredictorQt")
    app.setOrganizationName("LuviDeeZ")

    main_window = None

    try:
        main_logger.info("Creating LotteryPredictionApp instance...")
        main_window = LotteryPredictionApp()

        main_logger.info("Starting Qt event loop...")
        exit_code = app.exec_()
        main_logger.info(f"Qt event loop finished with exit code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        main_logger.critical(f"Unhandled critical error in main() execution: {e}", exc_info=True)
        traceback.print_exc()
        QMessageBox.critical(
            None,
            "Lỗi Nghiêm Trọng",
            f"Đã xảy ra lỗi khởi tạo hoặc lỗi nghiêm trọng không thể phục hồi:\n\n{e}\n\n"
            f"Ứng dụng sẽ đóng.\nKiểm tra file log để biết chi tiết:\n'{log_file_path}'."
        )
        sys.exit(1)

    finally:
        main_logger.info("Application shutdown sequence (finally block).")
        logging.shutdown()


if __name__ == "__main__":
    print(f"Running Python: {sys.version.split()[0]}")
    print(f"Base Directory: {Path(__file__).parent.resolve()}")
    print(f"Using PyQt5: {HAS_PYQT5}")
    print(f"Using Astor (for Py<3.9 AST write): {HAS_ASTOR}")
    print(f"Log file: {log_file_path}")

    main()

    main_logger.info("="*30 + " APPLICATION END (if not exited earlier) " + "="*30)