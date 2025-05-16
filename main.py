# Version: 4.6
# Date: 16/05/2025
# Update: Sửa lỗi update, xoá file tạm, định dạng lại nhật ký hoạt động trong Repo. Tối ưu thuật toán hoạt động...
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
import itertools
import xml.etree.ElementTree as ET
from packaging.version import parse as parse_version

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
    from PyQt5.QtCore import Qt, QTimer, QDate, QObject, pyqtSignal, QThread, QSize, QRect, pyqtSlot
    from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QIntValidator, QDoubleValidator, QTextCursor, QFontDatabase, QPixmap, QPainter, QBrush, QFontMetrics
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
        print("Astor library found (for Python < 3.9 AST writing).")
    else:
        HAS_ASTOR = False
        print("Astor library not needed (Python >= 3.9).")
except ImportError:
    HAS_ASTOR = False
    print("Astor library not found (may be needed for Python < 3.9 AST writing if not using Python >= 3.9).")

base_dir_for_log = Path(__file__).parent.resolve()
log_file_path = base_dir_for_log / "lottery_app_qt.log"

class SignallingLogHandler(logging.Handler, QObject):
    log_updated = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self._instance_closed = False

    def emit(self, record):
        if self._instance_closed:
            return
        try:
            msg = self.format(record)
            if self.parent() is not None and not self.signalsBlocked():
                 self.log_updated.emit(msg)
            elif self.parent() is None and not self.signalsBlocked():
                 self.log_updated.emit(msg)

        except RuntimeError as e:
            if "deleted" in str(e).lower() or "wrapped C/C++ object" in str(e).lower():
                self._instance_closed = True
                self._remove_from_logging_system()
            else:
                try:
                    self.handleError(record)
                except Exception:
                    pass
        except Exception:
            try:
                self.handleError(record)
            except Exception:
                pass

    def flush(self):
        if self._instance_closed:
            return
        super(SignallingLogHandler, self).flush()

    def close(self):
        if self._instance_closed:
            return
        self._instance_closed = True
        self._remove_from_logging_system()
        super(SignallingLogHandler, self).close()

    def _remove_from_logging_system(self):
        if not hasattr(logging, '_handlerList') or not hasattr(logging, '_acquireLock') or not hasattr(logging, '_releaseLock'):
            return
        logging._acquireLock()
        try:
            handler_found = False
            for i, h in enumerate(logging._handlerList):
                if h is self:
                    logging._handlerList.pop(i)
                    handler_found = True
                    break
        except RuntimeError:
            pass
        except Exception:
            pass
        finally:
            logging._releaseLock()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
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
algo_mgmnt_logger = logging.getLogger("AlgoManagementQt")

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

        self.current_optimization_mode = 'auto_hill_climb'

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
        layout = QVBoxLayout(self.tab_optimize)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0,0,0,0)
        top_layout.setSpacing(8)
        layout.addWidget(top_widget, 0)

        info_frame = QWidget()
        info_h_layout = QHBoxLayout(info_frame)
        info_h_layout.setContentsMargins(0,0,0,0)
        info_h_layout.addWidget(QLabel("Thuật toán tối ưu:"))
        self.opt_algo_name_label = QLabel("...")
        self.opt_algo_name_label.setStyleSheet(f"font-weight: bold; color: #28a745; font-size: {self.main_app.get_font_size('title')}pt;")
        info_h_layout.addWidget(self.opt_algo_name_label)
        info_h_layout.addStretch(1)
        top_layout.addWidget(info_frame)

        self.settings_container = QWidget()
        settings_h_layout = QHBoxLayout(self.settings_container)
        settings_h_layout.setContentsMargins(0, 0, 0, 0)
        settings_h_layout.setSpacing(10)
        top_layout.addWidget(self.settings_container)

        settings_groupbox = QGroupBox("Cài Đặt Cơ Bản")
        settings_layout = QGridLayout(settings_groupbox)
        settings_layout.setContentsMargins(10, 15, 10, 10)
        settings_layout.setVerticalSpacing(8)
        settings_layout.setHorizontalSpacing(0)

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

        settings_layout.setColumnStretch(0, 0)
        settings_layout.setColumnStretch(1, 0)
        settings_layout.setColumnStretch(2, 0)
        settings_layout.setColumnStretch(3, 1)
        settings_layout.setRowStretch(5, 1)

        settings_h_layout.addWidget(settings_groupbox, 1)

        self.optimization_mode_groupbox = QGroupBox("Chế Độ Tối Ưu")
        mode_outer_layout = QVBoxLayout(self.optimization_mode_groupbox)
        mode_outer_layout.setContentsMargins(10, 15, 10, 10)
        mode_outer_layout.setSpacing(8)

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

        self.combo_gen_settings_widget = QWidget()
        combo_gen_layout = QHBoxLayout(self.combo_gen_settings_widget)
        combo_gen_layout.setContentsMargins(20, 5, 0, 0)
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
        mode_outer_layout.addWidget(self.combo_gen_settings_widget)
        self.combo_gen_settings_widget.setEnabled(False)

        mode_outer_layout.addStretch(1)

        settings_h_layout.addWidget(self.optimization_mode_groupbox, 1)

        self.custom_steps_groupbox = QGroupBox("Tùy Chỉnh tham số tối ưu (bước nhảy)")
        steps_outer_layout = QVBoxLayout(self.custom_steps_groupbox)
        steps_outer_layout.setContentsMargins(5, 10, 5, 5)
        steps_outer_layout.setSpacing(6)

        self.param_scroll_widget_container = QWidget()
        param_scroll_layout = QVBoxLayout(self.param_scroll_widget_container)
        param_scroll_layout.setContentsMargins(0, 5, 0, 0)
        param_scroll_layout.setSpacing(4)

        adv_scroll_area = QScrollArea()
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
        param_scroll_layout.addWidget(adv_scroll_area)

        steps_outer_layout.addWidget(self.param_scroll_widget_container)

        settings_h_layout.addWidget(self.custom_steps_groupbox, 2)

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

        settings_h_layout.addWidget(self.combination_groupbox, 1)

        control_frame = QWidget()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 5, 0, 5)
        control_layout.setSpacing(8)
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
        control_layout.addWidget(self.opt_pause_button)

        self.opt_stop_button = QPushButton("Dừng Hẳn")
        self.opt_stop_button.setObjectName("DangerButton")
        self.opt_stop_button.clicked.connect(self.stop_optimization)
        self.opt_stop_button.setEnabled(False)
        control_layout.addWidget(self.opt_stop_button)

        control_layout.addStretch(1)
        top_layout.addWidget(control_frame)

        progress_frame = QWidget()
        progress_layout = QGridLayout(progress_frame)
        progress_layout.setContentsMargins(0, 5, 0, 5)
        progress_layout.setVerticalSpacing(2)
        progress_layout.setHorizontalSpacing(8)
        self.opt_progressbar = QProgressBar()
        self.opt_progressbar.setTextVisible(False)
        self.opt_progressbar.setFixedHeight(22)
        self.opt_progressbar.setRange(0, 100)
        self.opt_progressbar.setObjectName("OptimizeProgressBar")
        progress_layout.addWidget(self.opt_progressbar, 0, 0, 1, 4)

        self.opt_status_label = QLabel("Trạng thái: Chờ")
        self.opt_status_label.setStyleSheet("color: #6c757d;")
        progress_layout.addWidget(self.opt_status_label, 1, 0)

        self.opt_progress_label = QLabel("0%")
        self.opt_progress_label.setMinimumWidth(40)
        self.opt_progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_layout.addWidget(self.opt_progress_label, 1, 1)

        self.opt_time_static_label = QLabel("Thời gian còn lại:")
        self.opt_time_static_label.setStyleSheet("color: #6c757d;")
        progress_layout.addWidget(self.opt_time_static_label, 1, 2, Qt.AlignRight)
        self.opt_time_static_label.setVisible(False)

        self.opt_time_remaining_label = QLabel("--:--:--")
        self.opt_time_remaining_label.setStyleSheet("font-weight: bold;")
        self.opt_time_remaining_label.setMinimumWidth(70)
        progress_layout.addWidget(self.opt_time_remaining_label, 1, 3, Qt.AlignLeft)
        self.opt_time_remaining_label.setVisible(False)

        progress_layout.setColumnStretch(0, 1)
        progress_layout.setColumnStretch(1, 0)
        progress_layout.setColumnStretch(2, 0)
        progress_layout.setColumnStretch(3, 0)
        top_layout.addWidget(progress_frame)

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
        self._setup_log_formats()
        log_outer_layout.addWidget(self.opt_log_text, 1)

        log_button_frame = QWidget()
        log_button_layout = QHBoxLayout(log_button_frame)
        log_button_layout.setContentsMargins(0, 0, 0, 0)
        log_button_layout.addStretch(1)
        open_folder_button = QPushButton("Mở Thư Mục Tối Ưu")
        open_folder_button.clicked.connect(self.open_optimize_folder)
        log_button_layout.addWidget(open_folder_button)
        log_outer_layout.addWidget(log_button_frame)

        layout.addWidget(log_groupbox, 1)

    def _on_optimization_mode_changed(self, checked):
        if not checked:
            return

        sender = self.sender()
        if sender == self.opt_mode_auto_radio:
            self.current_optimization_mode = 'auto_hill_climb'
            self.combo_gen_settings_widget.setEnabled(False)
            self.param_scroll_widget_container.setEnabled(True)
            optimizer_logger.debug("Switched to Auto/Custom optimization mode.")
        elif sender == self.opt_mode_combo_radio:
            self.current_optimization_mode = 'generated_combinations'
            self.combo_gen_settings_widget.setEnabled(True)
            self.param_scroll_widget_container.setEnabled(False)
            optimizer_logger.debug("Switched to Generated Combinations optimization mode.")
        self._populate_advanced_optimizer_settings()


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
        self.log_formats["GEN_COMBO"] = create_format(base_font, "#E83E8C")


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

        if not numeric_params_check and self.current_optimization_mode != 'generated_combinations':
            QMessageBox.information(main_window, "Thông Báo", "Thuật toán này không có tham số số học để tối ưu (ở chế độ Auto/Custom).")

        if is_resuming and initial_combination_algos is not None:
            combination_algos_to_use = initial_combination_algos
        else:
            combination_algos_to_use = self._get_selected_combination_algos()

        start_d, end_d, time_limit_min = self._validate_common_opt_settings_qt()
        if start_d is None:
            return

        final_custom_steps_config = {}
        generation_params_for_worker = None
        mode_to_run = self.current_optimization_mode

        if mode_to_run == 'auto_hill_climb':
            final_custom_steps_config, has_invalid_custom_steps = self._finalize_custom_steps_config_qt(original_params)
            if not numeric_params_check and not final_custom_steps_config:
                 QMessageBox.information(main_window, "Thông Báo", "Thuật toán không có tham số số học và không có bước tùy chỉnh nào được định nghĩa.")
                 return

        elif mode_to_run == 'generated_combinations':
            num_values_per_param = self.combo_num_values_spinbox.value()
            generation_method = "random" if self.combo_method_random_radio.isChecked() else "adjacent"
            generation_params_for_worker = {
                'original_params': original_params,
                'num_values': num_values_per_param,
                'method': generation_method
            }
            optimizer_logger.info(f"Preparing to generate {num_values_per_param} values per param using '{generation_method}' method IN WORKER.")

            estimated_total = 1
            numeric_params_count = sum(1 for v in original_params.values() if isinstance(v, (int, float)))
            if numeric_params_count > 0:
                try:
                    if num_values_per_param > 0 and numeric_params_count > 0:
                         if num_values_per_param == 1:
                              estimated_total = 1
                         elif numeric_params_count * math.log(num_values_per_param) < math.log(sys.maxsize):
                              estimated_total = num_values_per_param ** numeric_params_count
                         else:
                              estimated_total = float('inf')
                except OverflowError:
                     estimated_total = float('inf')
                except Exception as est_err:
                     optimizer_logger.error(f"Error estimating combination count: {est_err}")
                     estimated_total = -1

            if estimated_total == float('inf') or estimated_total > 100000:
                display_estimate = "rất lớn (>100,000)" if estimated_total == float('inf') else f"khoảng {estimated_total}"
                reply = QMessageBox.question(main_window, "Số Lượng Lớn (Ước Tính)",
                                                f"Việc tạo và kiểm tra {display_estimate} bộ tham số có thể rất lâu và tốn nhiều bộ nhớ.\n\nBạn có muốn tiếp tục không?",
                                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                      return
            elif estimated_total == -1:
                 optimizer_logger.warning("Could not reliably estimate combination count, proceeding without warning.")

        else:
             QMessageBox.critical(main_window, "Lỗi Chế Độ", f"Chế độ tối ưu không xác định: {mode_to_run}")
             return

        self._start_optimization_worker_thread(
            display_name=display_name,
            start_date=start_d,
            end_date=end_d,
            time_limit_min=time_limit_min,
            custom_steps_config=final_custom_steps_config,
            generation_params=generation_params_for_worker,
            combination_algos=combination_algos_to_use,
            initial_params=initial_params,
            initial_score_tuple=initial_score_tuple,
            is_resuming=is_resuming,
            mode=mode_to_run
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
                                          custom_steps_config,
                                          generation_params,
                                          combination_algos,
                                          initial_params=None, initial_score_tuple=None, is_resuming=False,
                                          mode='auto_hill_climb'):
        """
        Sets up the environment and starts the appropriate optimization worker thread
        based on the selected mode.
        """
        main_window = self.get_main_window()
        try:
            algo_data = self.loaded_algorithms[display_name]
        except KeyError:
            QMessageBox.critical(main_window, "Lỗi", f"Thuật toán '{display_name}' không tìm thấy khi bắt đầu tối ưu.")
            self.update_optimizer_ui_state()
            return

        self.current_optimize_target_dir = self.optimize_dir / algo_data['path'].stem
        self.current_optimize_target_dir.mkdir(parents=True, exist_ok=True)
        success_dir = self.current_optimize_target_dir / "success"
        success_dir.mkdir(parents=True, exist_ok=True)
        self.current_optimization_log_path = self.current_optimize_target_dir / "optimization_qt.log"

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
                num_vals = generation_params.get('num_values', '?') if generation_params else '?'
                gen_meth = generation_params.get('method', '?') if generation_params else '?'
                self._log_to_optimizer_display("INFO", f"Chế độ: Tạo Bộ Tham Số (Worker sẽ tạo ~{num_vals} giá trị/{gen_meth})", tag="GEN_COMBO")
            else:
                self._log_to_optimizer_display("INFO", "Chế độ: Tối ưu Tự động / Custom", tag="CUSTOM_STEP")
                if custom_steps_config:
                    for pname, pconfig in custom_steps_config.items():
                        if pconfig.get('mode') == 'Custom' and pconfig.get('steps'):
                            self._log_to_optimizer_display("DEBUG", f"  - Tham số '{pname}' (Custom): {pconfig['steps']}", tag="CUSTOM_STEP")

        self._clear_cache_directory()

        self.optimizer_stop_event.clear()
        self.optimizer_pause_event.clear()
        self.optimizer_running = True
        self.optimizer_paused = False
        self.current_best_params = initial_params if is_resuming else None
        self.current_best_score_tuple = initial_score_tuple if is_resuming else (-1.0, -1.0, -1.0, -100.0)
        self.current_combination_algos = combination_algos
        self.last_opt_range_start_str = start_date.strftime('%Y-%m-%d')
        self.last_opt_range_end_str = end_date.strftime('%Y-%m-%d')

        self.opt_start_time = time.time()
        self.opt_time_limit_sec = time_limit_min * 60

        if hasattr(self, 'opt_progressbar'): self.opt_progressbar.setValue(0)
        if hasattr(self, 'opt_progress_label'): self.opt_progress_label.setText("0%")
        if hasattr(self, 'opt_time_static_label'): self.opt_time_static_label.setVisible(True)
        if hasattr(self, 'opt_time_remaining_label'):
            self.opt_time_remaining_label.setVisible(True)
            initial_time_str = time.strftime('%H:%M:%S' if self.opt_time_limit_sec >= 3600 else '%M:%S', time.gmtime(self.opt_time_limit_sec)) if self.opt_time_limit_sec >= 0 else "--:--:--"
            self.opt_time_remaining_label.setText(initial_time_str)

        self.update_optimizer_ui_state()

        optimizer_logger.info(f"Preparing worker thread for mode: {mode}")
        worker_target = None
        worker_args = ()

        if mode == 'auto_hill_climb':
            worker_target = self._optimization_worker
            worker_args = (
                display_name, start_date, end_date, self.opt_time_limit_sec,
                custom_steps_config,
                combination_algos,
                self.current_best_params,
                self.current_best_score_tuple
            )
            optimizer_logger.debug("Worker target set to _optimization_worker")
        elif mode == 'generated_combinations':
            worker_target = self._combination_optimization_worker
            worker_args = (
                display_name, start_date, end_date, self.opt_time_limit_sec,
                generation_params,
                combination_algos,
                self.current_best_params,
                self.current_best_score_tuple
            )
            optimizer_logger.debug("Worker target set to _combination_optimization_worker")
        else:
            main_logger.error(f"Invalid optimization mode '{mode}' cannot start worker thread.")
            QMessageBox.critical(main_window, "Lỗi Mode", f"Chế độ tối ưu không hợp lệ: {mode}")
            self.optimizer_running = False
            self.update_optimizer_ui_state()
            return

        try:
            self.optimizer_thread = threading.Thread(
                target=worker_target,
                args=worker_args,
                name=f"Optimizer-{algo_data['path'].stem}-{mode}",
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

        if not self.optimizer_timer.isActive():
            self.optimizer_timer.start(self.optimizer_timer_interval)
        if not self.display_timer.isActive():
            self.display_timer.start(self.display_timer_interval)

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
            resume_enabled = False
            stop_enabled = True
            if self.optimizer_paused:
                pause_enabled = True
                pause_text = "Tiếp tục"
                pause_callback = self.resume_optimization
            else:
                pause_enabled = True
                pause_text = "Tạm dừng"
                pause_callback = self.pause_optimization
        else:
            start_enabled = (self.selected_algorithm_for_optimize is not None)
            resume_enabled = self.can_resume
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
            self.main_app.apply_stylesheet()

        settings_enabled = not self.optimizer_running

        if hasattr(self, 'opt_start_date_edit'): self.opt_start_date_edit.setReadOnly(not settings_enabled)
        if hasattr(self, 'opt_start_date_button'): self.opt_start_date_button.setEnabled(settings_enabled)
        if hasattr(self, 'opt_end_date_edit'): self.opt_end_date_edit.setReadOnly(not settings_enabled)
        if hasattr(self, 'opt_end_date_button'): self.opt_end_date_button.setEnabled(settings_enabled)
        if hasattr(self, 'opt_time_limit_spinbox'): self.opt_time_limit_spinbox.setEnabled(settings_enabled)

        if hasattr(self, 'opt_mode_auto_radio'): self.opt_mode_auto_radio.setEnabled(settings_enabled)
        if hasattr(self, 'opt_mode_combo_radio'): self.opt_mode_combo_radio.setEnabled(settings_enabled)

        is_combo_mode_selected = self.current_optimization_mode == 'generated_combinations'
        if hasattr(self, 'combo_gen_settings_widget'): self.combo_gen_settings_widget.setEnabled(settings_enabled and is_combo_mode_selected)

        is_auto_mode_selected = self.current_optimization_mode == 'auto_hill_climb'
        if hasattr(self, 'param_scroll_widget_container'): self.param_scroll_widget_container.setEnabled(settings_enabled and is_auto_mode_selected)
        for name, widgets in self.advanced_opt_widgets.items():
             mode_combo = widgets.get('mode_combo')
             steps_entry = widgets.get('steps_entry')
             if mode_combo: mode_combo.setEnabled(settings_enabled and is_auto_mode_selected)
             if steps_entry:
                 is_custom_mode_for_param = mode_combo.currentText() == 'Custom' if mode_combo else False
                 steps_entry.setEnabled(settings_enabled and is_auto_mode_selected and is_custom_mode_for_param)

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
                    max_val = 100
                    text_override = None
                    if isinstance(payload, dict):
                        current = payload.get('current', 0)
                        total = payload.get('total', 1)
                        progress_val = int((current / total * 100) if total > 0 else 0)
                        text_override = f"{progress_val}% ({current}/{total})"
                    else:
                        try: progress_val = int(float(payload) * 100.0)
                        except (ValueError, TypeError): pass

                    if hasattr(self, 'opt_progressbar'):
                         self.opt_progressbar.setRange(0, 100)
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

                    if reason == "stopped":
                        self._save_optimization_state(reason="stopped_by_user_request")
                    elif reason not in ["stopped", "paused"]:
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
        start_time = time.time()
        optimizer_worker_logger = logging.getLogger("OptimizerWorker")
        is_resuming = initial_best_params is not None and initial_best_score_tuple is not None
        optimizer_worker_logger.info(f"Starting Auto/Custom optimization worker (Resuming: {is_resuming})...")

        def queue_log(level, text, tag=None):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                try: self.optimizer_queue.put({"type": "log", "payload": {"level": level, "text": text, "tag": tag}})
                except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (log): {q_err}")
        def queue_status(text):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "status", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (status): {q_err}")
        def queue_progress(value):
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

        finish_reason = "completed"
        try:
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

            current_best_params = {}
            current_best_perf = None
            current_best_score_tuple = initial_best_score_tuple if initial_best_score_tuple is not None else get_primary_score({})

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

                    else:
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
                    if finish_reason in ["stopped", "time_limit"]: break

                if finish_reason in ["stopped", "time_limit"]: break

                if not params_changed_in_cycle and cycle > 0:
                    queue_log("INFO", f"Không có cải thiện nào trong chu kỳ {cycle + 1}. Dừng tối ưu.", tag="PROGRESS")
                    finish_reason = "no_improvement"
                    break

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
                        "optimization_mode": "auto_hill_climb",
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

            is_successful_run = finish_reason in ["completed", "time_limit", "no_improvement"] and can_log_or_save

            queue_finished(final_message, success=is_successful_run, reason=finish_reason)

        except Exception as worker_err:
            finish_reason = "critical_error"
            optimizer_worker_logger.critical(f"Worker exception (Auto/Custom): {worker_err}", exc_info=True)
            queue_error(f"Lỗi nghiêm trọng trong luồng tối ưu: {worker_err}")
            queue_finished(f"Lỗi nghiêm trọng: {worker_err}", success=False, reason=finish_reason)

    def _combination_optimization_worker(self, target_display_name, start_date, end_date, time_limit_sec,
                                         generation_params,
                                         combination_algo_names,
                                         initial_best_params=None,
                                         initial_best_score_tuple=None):
        """
        Worker thread for the 'Generated Combinations' optimization mode.
        Generates parameter combinations first, then tests their performance.
        """
        start_time = time.time()
        optimizer_worker_logger = logging.getLogger("OptimizerWorker.Combo")
        optimizer_worker_logger.info("Starting Generated Combinations optimization worker...")

        def queue_log(level, text, tag=None):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                try: self.optimizer_queue.put({"type": "log", "payload": {"level": level, "text": text, "tag": tag}})
                except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (log): {q_err}")
        def queue_status(text):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "status", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (status): {q_err}")
        def queue_progress(current, total):
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

        finish_reason = "completed"
        generated_combinations = []
        total_combinations = 0
        current_best_params = None
        current_best_perf = None
        current_best_score_tuple = (-1.0, -1.0, -1.0, -100.0)

        try:
            optimizer_worker_logger.debug(f"Setting up worker for target: {target_display_name}")
            if target_display_name not in self.loaded_algorithms:
                 raise ValueError(f"Target algorithm '{target_display_name}' not loaded in worker.")

            target_algo_data = self.loaded_algorithms[target_display_name]
            original_path = target_algo_data['path']
            class_name = target_algo_data['class_name']
            try:
                source_code = original_path.read_text(encoding='utf-8')
                optimizer_worker_logger.debug(f"Successfully read source code for {original_path.name}")
            except Exception as read_err:
                raise RuntimeError(f"Worker failed to read source code for {original_path.name}: {read_err}")

            if not hasattr(self, 'current_optimize_target_dir') or not self.current_optimize_target_dir:
                 raise RuntimeError("Worker cannot determine optimize target directory.")
            target_dir = self.current_optimize_target_dir
            optimizer_worker_logger.debug(f"Using optimize target directory: {target_dir}")


            optimizer_worker_logger.info("Starting parameter combination generation phase...")
            queue_status("Đang tạo bộ tham số...")
            queue_log("INFO", "Bắt đầu tạo các bộ tham số kết hợp...", tag="GEN_COMBO")
            queue_progress(0, 1)

            if not generation_params or not isinstance(generation_params, dict):
                raise ValueError("Worker received invalid generation_params.")
            orig_params_for_gen = generation_params.get('original_params')
            num_values_for_gen = generation_params.get('num_values')
            method_for_gen = generation_params.get('method')
            if not orig_params_for_gen or not num_values_for_gen or not method_for_gen:
                 raise ValueError("Worker missing detailed generation parameters (params, num_values, method).")
            optimizer_worker_logger.debug(f"Generation params: num_values={num_values_for_gen}, method='{method_for_gen}'")

            generation_start_time = time.time()
            generated_combinations = self._generate_parameter_combinations(
                orig_params_for_gen, num_values_for_gen, method_for_gen
            )
            generation_duration = time.time() - generation_start_time
            optimizer_worker_logger.info(f"Parameter combination generation finished in {generation_duration:.2f} seconds.")

            if not generated_combinations:
                optimizer_worker_logger.error("Parameter generation returned an empty list.")
                queue_log("ERROR", "Không thể tạo bộ tham số nào (kết quả trống).", tag="ERROR")
                queue_finished("Tạo bộ tham số thất bại.", success=False, reason="combo_generation_failed")
                return

            total_combinations = len(generated_combinations)
            if total_combinations == 0:
                 optimizer_worker_logger.error("Generated combinations list is empty after generation.")
                 queue_log("ERROR", "Danh sách bộ tham số rỗng sau khi tạo.", tag="ERROR")
                 queue_finished("Tạo bộ tham số thất bại (danh sách rỗng).", success=False, reason="combo_generation_failed_empty")
                 return

            queue_status(f"Đã tạo {total_combinations} bộ. Bắt đầu kiểm tra...")
            queue_log("INFO", f"Đã tạo thành công {total_combinations} bộ tham số.", tag="GEN_COMBO")


            def run_combined_perf_test_wrapper(params_to_test_in_wrapper, combo_names_in_wrapper, start_dt_in_wrapper, end_dt_in_wrapper):
                 """Calls the main performance test function with necessary arguments."""
                 optimizer_worker_logger.debug(f"Calling run_combined_performance_test for params: {list(params_to_test_in_wrapper.keys())}")
                 return self.run_combined_performance_test(
                     target_display_name=target_display_name,
                     target_algo_source=source_code,
                     target_class_name=class_name,
                     target_params_to_test=params_to_test_in_wrapper,
                     combination_algo_display_names=combo_names_in_wrapper,
                     test_start_date=start_dt_in_wrapper,
                     test_end_date=end_dt_in_wrapper,
                     optimize_target_dir=target_dir
                 )

            def get_primary_score(perf_dict):
                 """Calculates the primary score tuple from performance dictionary."""
                 if not perf_dict: return (-1.0, -1.0, -1.0, -100.0)
                 return (perf_dict.get('acc_top_3_pct',0.0),
                         perf_dict.get('acc_top_5_pct',0.0),
                         perf_dict.get('acc_top_1_pct',0.0),
                         -perf_dict.get('avg_top10_repetition',100.0))


            optimizer_worker_logger.info(f"Starting performance testing for {total_combinations} parameter combinations...")
            queue_progress(0, total_combinations)

            for idx, test_params in enumerate(generated_combinations):
                current_progress_idx = idx + 1

                if self.optimizer_stop_event.is_set():
                    finish_reason = "stopped"
                    optimizer_worker_logger.info("Stop event detected during testing loop.")
                    break
                while self.optimizer_pause_event.is_set():
                    queue_status(f"Đã tạm dừng (đang ở bộ {current_progress_idx}/{total_combinations})")
                    if self.optimizer_stop_event.is_set():
                        finish_reason = "stopped"
                        optimizer_worker_logger.info("Stop event detected during pause.")
                        break
                    time.sleep(0.5)
                if finish_reason == "stopped":
                    break

                elapsed_time = time.time() - start_time
                if elapsed_time >= time_limit_sec:
                    finish_reason = "time_limit"
                    optimizer_worker_logger.info("Time limit reached during testing loop.")
                    break

                queue_status(f"Kiểm tra bộ {current_progress_idx}/{total_combinations}...")
                queue_progress(current_progress_idx, total_combinations)

                optimizer_worker_logger.debug(f"Running performance test for combination {current_progress_idx}")
                perf_result = run_combined_perf_test_wrapper(
                    params_to_test_in_wrapper=test_params,
                    combo_names_in_wrapper=combination_algo_names,
                    start_dt_in_wrapper=start_date,
                    end_dt_in_wrapper=end_date
                )
                optimizer_worker_logger.debug(f"Performance test for combo {current_progress_idx} completed.")

                if self.optimizer_stop_event.is_set():
                    finish_reason="stopped"
                    optimizer_worker_logger.info("Stop event detected immediately after performance test.")
                    break

                if perf_result is not None:
                    new_score = get_primary_score(perf_result)
                    optimizer_worker_logger.debug(f"Combo {current_progress_idx} score: {new_score}")
                    if new_score > current_best_score_tuple:
                        queue_log("BEST", f"Tìm thấy bộ tốt hơn! Bộ {current_progress_idx}/{total_combinations}. Score: {new_score}", tag="BEST")
                        optimizer_worker_logger.info(f"New best score found: {new_score} > {current_best_score_tuple} at index {idx}")
                        optimizer_worker_logger.debug(f"  Best Params Updated: {test_params}")
                        queue_log("DEBUG", f"  Params: {test_params}")

                        current_best_params = test_params.copy()
                        current_best_perf = perf_result
                        current_best_score_tuple = new_score
                        queue_best_update(current_best_params, current_best_score_tuple)
                    else:
                        optimizer_worker_logger.debug(f"Combination {current_progress_idx} score {new_score} not better than current best {current_best_score_tuple}")
                else:
                    queue_log("WARNING", f"Lỗi khi kiểm tra bộ tham số {current_progress_idx}.", tag="WARNING")
                    optimizer_worker_logger.warning(f"Performance test returned None for combination {current_progress_idx}.")

            optimizer_worker_logger.info(f"Finished testing loop. Reason: {finish_reason}")

            queue_progress(total_combinations, total_combinations)

            final_message = ""
            if finish_reason == "stopped":
                final_message = "Dừng bởi người dùng."
            elif finish_reason == "time_limit":
                final_message = f"Đã hết thời gian tối ưu ({time_limit_sec/60:.0f} phút)."
            elif finish_reason == "critical_error":
                final_message = "Lỗi nghiêm trọng trong worker."
            elif finish_reason == "combo_generation_failed":
                final_message = "Tạo bộ tham số thất bại."
            elif current_best_params is None:
                final_message = "Hoàn thành kiểm tra nhưng không tìm thấy bộ tham số nào cho kết quả hợp lệ."
                finish_reason = "combo_mode_no_results"
            else:
                final_message = "Hoàn thành kiểm tra các bộ tham số."

            can_log_or_save = current_best_params is not None and finish_reason not in [
                "critical_error", "combo_mode_no_results", "combo_generation_failed"
            ]

            if can_log_or_save:
                final_message += " Kết quả tốt nhất đã được lưu."
                queue_log("BEST", "="*10 + " TỐI ƯU KẾT THÚC (Bộ Tham Số) " + "="*10, tag="BEST")
                queue_log("BEST", f"Lý do kết thúc: {finish_reason}", tag="BEST")
                queue_log("BEST", f"Đã tạo và kiểm tra tổng cộng: {total_combinations} bộ", tag="BEST")
                queue_log("BEST", f"Tham số tốt nhất tìm được: {current_best_params}", tag="BEST")
                score_desc = "(Top3%, Top5%, Top1%, -AvgRepT10)"
                queue_log("BEST", f"Điểm số tốt nhất {score_desc}: ({', '.join(f'{s:.3f}' for s in current_best_score_tuple)})", tag="BEST")
                if current_best_perf:
                     queue_log("BEST", f"Chi tiết hiệu suất tốt nhất: Top3={current_best_perf.get('acc_top_3_pct',0.0):.2f}%, Top5={current_best_perf.get('acc_top_5_pct',0.0):.2f}%, Top1={current_best_perf.get('acc_top_1_pct',0.0):.2f}%, Lặp TB={current_best_perf.get('avg_top10_repetition',0.0):.2f}", tag="BEST")

                try:
                    optimizer_worker_logger.info("Saving best results found...")
                    final_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    success_dir = target_dir / "success"
                    perf_metric_for_name = current_best_perf.get('acc_top_3_pct', 0.0) if current_best_perf else 0.0
                    perf_str = f"top3_{perf_metric_for_name:.1f}"
                    success_filename_base = f"optimized_combo_{target_algo_data['path'].stem}_{perf_str}_{final_timestamp}"
                    optimizer_worker_logger.debug(f"Base filename for saving: {success_filename_base}")

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

                    success_filename_json = success_filename_base + ".json"
                    final_json_path = success_dir / success_filename_json
                    optimizer_worker_logger.debug(f"Attempting to save JSON file: {final_json_path}")
                    final_save_data = {
                        "optimization_mode": "generated_combinations",
                        "target_algorithm": target_display_name,
                        "total_combinations_generated": total_combinations,
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
                        optimizer_worker_logger.info(f"Saved optimization details to JSON file: {final_json_path.name}")
                    except Exception as json_save_err:
                         queue_log("ERROR", f"Lỗi lưu file JSON kết quả cuối: {json_save_err}", tag="ERROR")
                         optimizer_worker_logger.error(f"Failed to save JSON results file: {json_save_err}", exc_info=True)
                         final_message += "\n(Lỗi lưu file JSON kết quả!)"

                except Exception as final_save_err:
                    queue_log("ERROR", f"Lỗi lưu kết quả cuối cùng: {final_save_err}", tag="ERROR")
                    optimizer_worker_logger.error(f"Error during final result saving: {final_save_err}", exc_info=True)
                    final_message += "\n(Lỗi lưu file kết quả!)"

            is_successful_run = finish_reason in ["completed", "time_limit"] and can_log_or_save
            optimizer_worker_logger.info(f"Worker sending finished signal. Success: {is_successful_run}, Reason: {finish_reason}")
            queue_finished(final_message, success=is_successful_run, reason=finish_reason)

        except Exception as worker_err:
            finish_reason = "critical_error"
            optimizer_worker_logger.critical(f"Worker encountered a critical exception: {worker_err}", exc_info=True)
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
            worker_logger.debug(f"Starting combined performance test for {target_class_name} with params: {target_params_to_test}")
            try:
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected before AST modification.")
                    return None

                modified_source = self.modify_algorithm_source_ast(target_algo_source, target_class_name, target_params_to_test)
                if not modified_source:
                    worker_logger.error("AST modification failed for performance test, returned no source.")
                    raise RuntimeError("AST modification failed for performance test.")

                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected after AST modification.")
                    return None

                timestamp = int(time.time() * 10000) + random.randint(0, 9999)
                temp_target_filename = f"temp_perf_target_{target_class_name}_{timestamp}.py"
                temp_target_filepath = optimize_target_dir / temp_target_filename
                temp_target_filepath.write_text(modified_source, encoding='utf-8')
                worker_logger.debug(f"Temporary target file created: {temp_target_filepath}")


                optimize_target_dir.mkdir(parents=True, exist_ok=True)
                if not (optimize_target_dir / "__init__.py").exists():
                    (optimize_target_dir / "__init__.py").touch()
                if not (self.optimize_dir / "__init__.py").exists():
                    (self.optimize_dir / "__init__.py").touch()


                temp_target_module_name = f"optimize.{optimize_target_dir.name}.{temp_target_filename[:-3]}"

                worker_logger.debug(f"Importing temporary target module: {temp_target_module_name}")
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected before importing temporary module.")
                    return None

                target_instance = self._import_and_instantiate_temp_algo(temp_target_filepath, temp_target_module_name, target_class_name)

                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected after importing temporary module.")
                    return None

                if not target_instance:
                    worker_logger.error(f"Failed to load temporary target instance {target_class_name} from {temp_target_filepath}")
                    raise RuntimeError(f"Failed to load temporary target instance {target_class_name} from {temp_target_filepath}")
                worker_logger.debug(f"Successfully loaded temporary target instance: {type(target_instance)}")

            except Exception as target_load_err:
                worker_logger.error(f"Failed loading TARGET {target_class_name} for perf test: {target_load_err}", exc_info=True)
                raise

            worker_logger.debug(f"Loading {len(combination_algo_display_names)} combination algorithms.")
            data_copy_for_combo = copy.deepcopy(self.results_data) if self.results_data else []
            for combo_name in combination_algo_display_names:
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected during combination algorithm loading.")
                    return None
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
            results_map = {r['date']: r['result'] for r in self.results_data} if self.results_data else {}
            history_cache = {}
            if self.results_data:
                sorted_results_for_cache = sorted(self.results_data, key=lambda x: x['date'])
                for i, r in enumerate(sorted_results_for_cache):
                     history_cache[r['date']] = sorted_results_for_cache[:i]

            stats = {'total_days_tested': 0, 'hits_top_1': 0, 'hits_top_3': 0, 'hits_top_5': 0, 'hits_top_10': 0, 'errors': 0, 'avg_top10_repetition': 0.0, 'max_top10_repetition_count': 0, 'top10_repetition_details': {}}
            all_top_10_combined_numbers = []

            current_date = test_start_date
            while current_date <= test_end_date:
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Performance test stopped by event (start of date loop).")
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
                    worker_logger.debug(f"Skipping {predict_date}: actual_result_dict is {actual_result_dict is None}, hist_data is {hist_data is None}")
                    current_date += datetime.timedelta(days=1)
                    continue

                actual_numbers_set = set()
                if target_instance:
                    actual_numbers_set = target_instance.extract_numbers_from_dict(actual_result_dict)
                else:
                    worker_logger.error(f"Target instance is None for {predict_date}, cannot extract actual numbers. This shouldn't happen if import was successful.")
                    stats['errors'] += 1
                    current_date += datetime.timedelta(days=1)
                    continue

                if not actual_numbers_set:
                    worker_logger.debug(f"No actual numbers extracted for {check_date}.")
                    stats['errors'] += 1
                    current_date += datetime.timedelta(days=1)
                    continue

                all_predictions_for_day = {}
                hist_copy_for_day = copy.deepcopy(hist_data)

                if target_instance:
                    try:
                        if self.optimizer_stop_event.is_set(): worker_logger.info("Stop event before target predict."); return None
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
                        if self.optimizer_stop_event.is_set(): worker_logger.info("Stop event before combo predict."); return None
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
                    worker_logger.warning(f"No valid algorithm results for {predict_date}")
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
                    total_predictions_in_top10 = len(all_top_10_combined_numbers)
                    unique_predictions_in_top10 = len(top10_counts)
                    stats['avg_top10_repetition'] = total_predictions_in_top10 / unique_predictions_in_top10 if unique_predictions_in_top10 > 0 else 0.0
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
                            file_ts_str = f"{parts[-2]}_{parts[-1]}"
                            file_dt = datetime.datetime.strptime(file_ts_str, "%Y%m%d_%H%M%S")
                            file_timestamp = file_dt.timestamp()
                        except (ValueError, IndexError, Exception):
                            file_timestamp = f_path.stat().st_mtime
                            optimizer_logger.debug(f"Using mtime {file_timestamp} for {f_path.name}")


                        if file_timestamp > latest_timestamp:
                             try:
                                 data = json.loads(f_path.read_text(encoding='utf-8'))
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
            return latest_file, latest_data

        optimizer_logger.debug("No success file found, checking for state file...")
        state_file_path = self.optimize_dir / algo_stem / f"optimization_state_{algo_stem}.json"
        if state_file_path.exists():
            optimizer_logger.debug(f"Found state file: {state_file_path.name}")
            try:
                 data = json.loads(state_file_path.read_text(encoding='utf-8'))
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
            param_dict = original_params.copy()
            param_dict.update(dict(zip(param_names_ordered, combo_values)))
            param_combinations_list.append(param_dict)

        optimizer_logger.info(f"Total combinations generated: {len(param_combinations_list)}")
        return param_combinations_list

    def _generate_single_parameter_values(self, param_name, original_value, num_values, method):
        """Generates a list of N values for a single parameter."""
        values = set()
        is_float = isinstance(original_value, float)

        if method == "random":
            deviation = abs(original_value) * 0.2 if abs(original_value) > 1e-3 else 0.5
            if not is_float:
                 deviation = max(1, int(round(deviation)))
            min_val = original_value - deviation
            max_val = original_value + deviation

            values.add(original_value)

            while len(values) < num_values:
                if is_float:
                    rand_val = random.uniform(min_val, max_val)
                    rand_val = float(f"{rand_val:.6g}")
                else:
                    rand_val = random.randint(int(round(min_val)), int(round(max_val)))
                values.add(rand_val)
                if len(values) >= num_values * 5 and len(values) < num_values :
                    optimizer_logger.warning(f"Struggling to generate {num_values} unique random values for '{param_name}' near {original_value}. Using {len(values)}.")
                    break


        elif method == "adjacent":
            values.add(original_value)
            num_each_side = (num_values - 1) // 2
            num_increase = num_each_side + ((num_values - 1) % 2)
            num_decrease = num_each_side

            if is_float:
                step = max(abs(original_value) * 0.02, 1e-4)
            else:
                step = 1

            current_val = original_value
            for _ in range(num_increase):
                current_val += step
                val_to_add = float(f"{current_val:.6g}") if is_float else int(round(current_val))
                values.add(val_to_add)

            current_val = original_value
            for _ in range(num_decrease):
                current_val -= step
                val_to_add = float(f"{current_val:.6g}") if is_float else int(round(current_val))
                values.add(val_to_add)

        else:
            optimizer_logger.error(f"Unknown generation method: {method}")
            return []

        return sorted(list(values))

class SquareQLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(300, 300)

    def heightForWidth(self, width: int) -> int:
        return 100

    def sizeHint(self) -> QSize:
        return QSize(100, 100)


class LotteryPredictionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lottery Predictor (V4.5)")
        main_logger.info("Initializing LotteryPredictionApp (PyQt5)...")

        self.font_family_base = 'Segoe UI'
        self.font_size_base = 10
        try:
            self.available_fonts = sorted(QFontDatabase().families())
            if not self.available_fonts:
                main_logger.warning("QFontDatabase().families() returned an empty list. Using fallback font list.")
                self.available_fonts = ['Arial', 'Times New Roman', 'Courier New', 'Segoe UI', 'Tahoma', 'Verdana']
        except Exception as e_font_db:
            main_logger.error(f"Error initializing QFontDatabase().families(): {e_font_db}. Using fallback font list.", exc_info=True)
            self.available_fonts = ['Arial', 'Times New Roman', 'Courier New', 'Segoe UI', 'Tahoma', 'Verdana']

        self.base_dir = Path(__file__).parent.resolve()
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.base_dir / "config"
        self.calculate_dir = self.base_dir / "calculate"
        self.algorithms_dir = self.base_dir / "algorithms"
        self.optimize_dir = self.base_dir / "optimize"
        self.tools_dir = self.base_dir / "tools"
        self.settings_file_path = self.config_dir / "settings.ini"

        self.config = configparser.ConfigParser(interpolation=None)

        self.results = []
        self.selected_date = None
        self.algorithms = {}
        self.algorithm_instances = {}
        self.loaded_tools = {}
        self.local_algorithms_managed_ui = {}
        self.online_algorithms_ui = {}


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

        self.update_logger = logging.getLogger("AppUpdate")
        self.update_project_path_edit = None
        self.update_project_path_default_checkbox = None
        self.update_file_url_edit = None
        self.update_save_filename_edit = None
        self.update_check_button = None
        self.update_info_display_textedit = None
        self.update_perform_button = None
        self.update_restart_button = None
        self.update_exit_after_update_button = None
        self.update_commit_history_textedit = None
        self.current_app_version_info = {}
        self.online_app_version_info = {}
        self.online_app_content_cache = None
        self.check_update_thread = None
        self.check_update_worker = None
        self.perform_update_thread = None
        self.perform_update_worker = None
        self.copy_account_button_update_tab = None
        self.qr_code_label_update_tab = None
        self.info_groupbox_update = None

        self.create_directories()
        self._setup_validators()

        self.load_config()

        self._setup_global_font()
        self.setup_main_ui_structure()

        if hasattr(self, 'settings_log_display') and self.settings_log_display:
            self.signalling_log_handler = SignallingLogHandler()
            global formatter
            self.signalling_log_handler.setFormatter(formatter)
            self.signalling_log_handler.setLevel(logging.DEBUG)
            self.signalling_log_handler.log_updated.connect(self._append_log_to_settings_display)

            self.root_logger_instance = logging.getLogger('')
            self.root_logger_instance.addHandler(self.signalling_log_handler)
            main_logger.info("UI Log Handler for Settings tab initialized and added to root logger.")
        else:
            self.signalling_log_handler = None
            self.root_logger_instance = None
            main_logger.error("settings_log_display widget not found AFTER setup_main_ui_structure. Cannot initialize UI Log Handler.")

        self.apply_stylesheet()
        self._apply_window_size_from_config()

        main_tab_data_file = self.config.get('DATA', 'data_file', fallback=str(self.data_dir / "xsmb-2-digits.json"))
        main_tab_sync_url = self.config.get('DATA', 'sync_url', fallback="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json")

        if hasattr(self, 'data_file_path_label'):
            self.data_file_path_label.setText(main_tab_data_file)
            self.data_file_path_label.setToolTip(main_tab_data_file)
        if hasattr(self, 'sync_url_input'):
            self.sync_url_input.setText(main_tab_sync_url)


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

        app_instance = QApplication.instance()
        if app_instance:
            app_instance.aboutToQuit.connect(self.cleanup_on_quit)
        else:
            main_logger.warning("QApplication instance is None, cannot connect aboutToQuit signal.")


        QTimer.singleShot(1500, self.perform_auto_sync_if_needed)
        QTimer.singleShot(2500, self.perform_auto_update_check_if_needed)

        self.update_status("Ứng dụng sẵn sàng.")
        QTimer.singleShot(200, self._log_actual_window_size)

        main_logger.info("LotteryPredictionApp (PyQt5) initialization complete.")
        self.show()

    def cleanup_on_quit(self):
        """Được gọi khi QApplication chuẩn bị thoát."""
        main_logger.info("QApplication aboutToQuit. Đang dọn dẹp SignallingLogHandler.")
        if self.signalling_log_handler:
            if self.root_logger_instance:
                try:
                    self.root_logger_instance.removeHandler(self.signalling_log_handler)
                    main_logger.debug("Đã gỡ bỏ SignallingLogHandler khỏi root logger.")
                except RuntimeError as e_remove_rt:
                    main_logger.error(f"RuntimeError khi gỡ bỏ SignallingLogHandler khỏi root logger (đối tượng C++ có thể đã biến mất): {e_remove_rt}")
                    if hasattr(self.signalling_log_handler, '_instance_closed'):
                        self.signalling_log_handler._instance_closed = True
                except Exception as e_remove:
                    main_logger.error(f"Lỗi khi gỡ bỏ SignallingLogHandler khỏi root logger trong cleanup_on_quit: {e_remove}")

            try:
                self.signalling_log_handler.close()
                main_logger.debug("Đã gọi SignallingLogHandler.close().")
            except RuntimeError as e_close_rt:
                main_logger.error(f"RuntimeError khi đóng SignallingLogHandler (đối tượng C++ có thể đã biến mất): {e_close_rt}")
            except Exception as e_close:
                main_logger.error(f"Lỗi khi đóng SignallingLogHandler trong cleanup_on_quit: {e_close}")

            main_logger.info("Xử lý SignallingLogHandler trong cleanup_on_quit đã hoàn tất.")
            self.signalling_log_handler = None
        else:
            main_logger.info("SignallingLogHandler là None hoặc đã được dọn dẹp trong cleanup_on_quit.")

    def closeEvent(self, event):
        main_logger.info("Sự kiện closeEvent của QMainWindow được kích hoạt.")


        optimizer_cancelled_exit = False
        if hasattr(self, 'optimizer_app_instance') and self.optimizer_app_instance and \
           hasattr(self.optimizer_app_instance, 'optimizer_running') and self.optimizer_app_instance.optimizer_running:
            reply = QMessageBox.question(self, 'Xác Nhận Thoát',
                                         "Quá trình tối ưu hóa đang chạy. Bạn có chắc chắn muốn thoát?\nQuá trình sẽ bị dừng.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                main_logger.info("Người dùng xác nhận thoát khi optimizer đang chạy. Đang dừng optimizer.")
                try:
                    if hasattr(self.optimizer_app_instance, 'optimizer_timer') and self.optimizer_app_instance.optimizer_timer.isActive():
                         self.optimizer_app_instance.optimizer_timer.stop()
                    if hasattr(self.optimizer_app_instance, 'display_timer') and self.optimizer_app_instance.display_timer.isActive():
                         self.optimizer_app_instance.display_timer.stop()

                    self.optimizer_app_instance.stop_optimization(force_stop=True)
                    if self.optimizer_app_instance.optimizer_thread and self.optimizer_app_instance.optimizer_thread.is_alive():
                        self.optimizer_app_instance.optimizer_thread.join(timeout=0.5)
                except Exception as stop_err:
                    main_logger.error(f"Lỗi khi dừng optimizer khi đóng: {stop_err}")
            else:
                main_logger.info("Người dùng hủy thoát do optimizer đang chạy.")
                optimizer_cancelled_exit = True
                event.ignore()
                return

        if optimizer_cancelled_exit:
            return

        main_logger.info("Chấp nhận sự kiện đóng trong QMainWindow.")
        event.accept()

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

    def _extract_metadata_from_py_content(self, content: str) -> dict:
        """
        Trích xuất siêu dữ liệu (ID, Date, Description, Name) từ nội dung file Python.
        Sử dụng regex cho ID và Date, và AST hoặc regex cho Description và Name.
        """
        metadata = {"id": None, "date_str": None, "description": None, "name": None}
        try:
            match_id = re.search(r"#\s*ID:\s*(\d{6})", content, re.IGNORECASE)
            if match_id:
                metadata["id"] = match_id.group(1)

            match_date = re.search(r"#\s*Date:\s*(\d{2}/\d{2}/\d{4})", content, re.IGNORECASE)
            if match_date:
                metadata["date_str"] = match_date.group(1)

            desc_match = re.search(
                r'self\.config\s*=\s*\{.*?["\']description["\']\s*:\s*["\'](.*?)["\'],',
                content,
                re.DOTALL | re.IGNORECASE
            )
            if not desc_match:
                 desc_match = re.search(
                    r'self\.config\s*=\s*\{.*?["\']description["\']\s*:\s*["\'](.*?)["\']\s*\}',
                    content,
                    re.DOTALL | re.IGNORECASE
                )

            if desc_match:
                metadata["description"] = desc_match.group(1).strip()
            else:
                tree = ast.parse(content)
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        docstring = ast.get_docstring(node)
                        if docstring:
                            metadata["description"] = docstring.strip().splitlines()[0]
                            metadata["name"] = node.name
                            break
            
            if not metadata["name"]:
                if not 'tree' in locals():
                    tree = ast.parse(content)
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                         for sub_node in node.body:
                             if isinstance(sub_node, ast.FunctionDef) and sub_node.name == "__init__":
                                 metadata["name"] = node.name
                                 break
                         if metadata["name"]:
                             break

        except SyntaxError:
            algo_mgmnt_logger.warning(f"Lỗi cú pháp khi phân tích nội dung để lấy siêu dữ liệu.")
        except Exception as e:
            algo_mgmnt_logger.error(f"Lỗi trích xuất siêu dữ liệu từ nội dung: {e}")
        return metadata


    def setup_main_ui_structure(self):
        """Thiết lập cấu trúc giao diện người dùng chính của ứng dụng, bao gồm các tab."""
        main_logger.debug("Thiết lập cấu trúc UI chính (PyQt5)...")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("MainTabWidget")

        self.main_tab_frame = QWidget()
        self.algo_management_tab_frame = QWidget()
        self.optimizer_tab_frame = QWidget()
        self.tools_tab_frame = QWidget()
        self.settings_tab_frame = QWidget()
        self.update_tab_frame = QWidget()

        self.tab_widget.addTab(self.main_tab_frame, " Main 🏠")
        self.tab_widget.addTab(self.algo_management_tab_frame, "  Thuật Toán 🛠️")
        self.tab_widget.addTab(self.optimizer_tab_frame, " Tối ưu 🚀 ")
        self.tab_widget.addTab(self.tools_tab_frame, " Công Cụ 🧰")
        self.tab_widget.addTab(self.settings_tab_frame, " Cài Đặt ⚙️")
        self.tab_widget.addTab(self.update_tab_frame, " Update 🔄 ")

        main_layout.addWidget(self.tab_widget)

        self.setup_main_tab()
        self.setup_algo_management_tab()
        self.setup_tools_tab()
        self.setup_settings_tab()
        self.setup_update_tab()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar_label = QLabel("Khởi tạo...")
        self.status_bar_label.setObjectName("StatusBarLabel")
        self.status_bar.addWidget(self.status_bar_label, 1)

        try:
            icon_path = self.config_dir / "logo.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                main_logger.info(f"Icon ứng dụng được đặt từ: {icon_path}")
        except Exception as e_icon:
            main_logger.warning(f"Lỗi khi đặt icon ứng dụng: {e_icon}")

        main_logger.debug("Hoàn tất thiết lập cấu trúc UI chính.")


    def _log_actual_window_size(self):
        try:
            if self:
                main_logger.info(f"Window size: {self.width()}x{self.height()}, Geometry: {self.geometry().x()},{self.geometry().y()},{self.geometry().width()},{self.geometry().height()}")
        except Exception as e:
            main_logger.error(f"Error logging window size: {e}")

    def create_directories(self):
        try:
            for directory in [self.data_dir, self.config_dir, self.calculate_dir, self.algorithms_dir, self.optimize_dir, self.tools_dir]:
                directory.mkdir(parents=True, exist_ok=True)
            for dir_path in [self.algorithms_dir, self.optimize_dir, self.tools_dir]:
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
                    /* font-family: "{self.font_family_base}"; */ /* Removed to allow QFontDatabase to work better */
                    /* font-size: {self.font_size_base}pt; */   /* Removed to allow QFontDatabase to work better */
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
                    border-bottom-color: {COLOR_TAB_SELECTED_BG}; /* Hide bottom border of selected tab */
                    margin-bottom: -1px; /* Pull selected tab down slightly */
                }}
                QTabBar::tab:!selected:hover {{
                    background: #E0E0E0;
                }}

                QGroupBox {{
                    font-weight: bold;
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 4px;
                    margin-top: 15px; /* Space for title */
                    padding-top: 8px; /* Ensure content doesn't overlap with border/title */
                    background-color: {COLOR_BG_LIGHT}; /* Slightly different from QWidget for visual separation */
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px 0 5px;
                    margin-left: 10px;
                    color: {COLOR_PRIMARY_DARK};
                    background-color: {COLOR_BG_LIGHT}; /* Match GroupBox background */
                }}

                QLabel#StatusBarLabel {{
                     padding: 3px 5px;
                }}
                QLabel#StatusBarLabel[status="error"] {{ color: {COLOR_DANGER}; }}
                QLabel#StatusBarLabel[status="success"] {{ color: {COLOR_SUCCESS}; }}
                QLabel#StatusBarLabel[status="info"] {{ color: {COLOR_INFO}; }}
                QLabel#StatusBarLabel[status="info"], QLabel#StatusBarLabel {{ /* Default */
                    color: {COLOR_SECONDARY};
                }}


                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
                    background-color: {COLOR_BG_WHITE};
                    border: 1px solid {COLOR_BORDER};
                    padding: 4px;
                    border-radius: 3px;
                    min-height: 22px; /* Consistent height */
                }}
                QLineEdit:read-only {{
                     background-color: {COLOR_DISABLED_BG}; /* Slightly different for read-only */
                }}
                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QTextEdit:disabled, QTextEdit:read-only {{
                    background-color: {COLOR_DISABLED_BG};
                    color: {COLOR_DISABLED_FG};
                    border: 1px solid #D0D0D0; /* Lighter border for disabled */
                }}
                 QComboBox::drop-down {{ border: none; }}
                 QComboBox::down-arrow {{ image: url({str(self.config_dir / "down_arrow.png").replace(os.sep, '/')}); }} /* Example for custom arrow */


                QPushButton {{
                    background-color: #EFEFEF; /* Standard button color */
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
                    color: {COLOR_TEXT_DARK}; /* Dark text for better contrast on yellow */
                    border-color: #E0A800; /* Darker yellow for border */
                    font-weight: bold;
                    padding: 8px 12px; /* Slightly larger padding for emphasis */
                }}
                QPushButton#WarningButton:hover {{ background-color: #ffad33; }} /* Lighter yellow on hover */
                QPushButton#WarningButton:pressed {{ background-color: #ffad33; }}

                QPushButton#DangerButton {{
                    background-color: {COLOR_DANGER};
                    color: {COLOR_TEXT_LIGHT};
                    border-color: #b21f2d; /* Darker red for border */
                    font-weight: bold;
                    padding: 5px 8px; /* Adjusted padding */
                    border-radius: 3px;
                    min-width: 100px; /* Adjusted min-width */
                    /* max-width: 150px; */ /* Adjusted max-width - <--- XOÁ DÒNG NÀY */
                    min-height: 23px;
                }}
                QPushButton#DangerButton:hover {{ background-color: #c82333; }} /* Darker red on hover */
                QPushButton#DangerButton:pressed {{ background-color: #c82333; }}

                QPushButton#SettingsButton {{
                    background-color: #EFEFEF;
                    color: {COLOR_TEXT_DARK};
                    border: 1px solid #B0B0B0;
                    padding: 5px 8px;
                    border-radius: 3px;
                    min-width: 60px;
                    /* max-width: 150px; */ /* <--- XOÁ DÒNG NÀY */
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
                     background-color: {COLOR_PRIMARY_DARK}; /* Darker accent for list buttons */
                     color: {COLOR_TEXT_LIGHT};
                     border-color: #004085; /* Even darker border */
                     padding: 4px 8px; /* Smaller padding for list items */
                     font-weight: bold;
                     font-size: {self.get_font_size("small")}pt; /* Smaller font */
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
                    min-height: 22px; /* Match QLineEdit height */
                    max-height: 22px;
                    font-size: {self.get_font_size("base") + 2}pt; /* Slightly larger icon */
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
                    background-color: {PB_TROUGH}; /* Trough color */
                }}
                 QProgressBar::chunk {{
                     border-radius: 2px; /* Slightly rounded chunk */
                     background-color: {COLOR_INFO}; /* Default chunk color */
                     margin: 1px; /* Small margin around the chunk */
                 }}
                 QProgressBar#PredictionProgressBar::chunk {{ background-color: {COLOR_INFO}; }}
                 QProgressBar#PerformanceProgressBar::chunk {{ background-color: {COLOR_PRIMARY}; }}
                 QProgressBar#OptimizeProgressBar::chunk {{ background-color: {COLOR_SUCCESS}; }}
                 QProgressBar#OptimizeProgressBar {{
                    min-height: 18px; /* Specific height for this progress bar */
                 }}


                QScrollArea {{
                    border: 1px solid {COLOR_BORDER};
                    background-color: {COLOR_BG_WHITE};
                }}
                 QScrollArea > QWidget > QWidget {{ /* Target the viewport's immediate child if it's also a QWidget */
                     background-color: {COLOR_BG_WHITE}; /* Ensure scroll area content background */
                 }}



                QListWidget {{
                     border: 1px solid {COLOR_BORDER};
                     background-color: {COLOR_BG_WHITE};
                 }}
                 QListWidget::item:selected {{
                     background-color: {COLOR_PRIMARY_DARK};
                     color: {COLOR_TEXT_LIGHT};
                 }}


                 QFrame#CardFrame {{ /* For algorithm cards in Optimizer and Main tab */
                     background-color: {COLOR_CARD_BG};
                     border-radius: 4px;
                     margin-bottom: 6px;
                     /* border: 1px solid #D0D0D0; Removed to rely on StyledPanel shadow*/
                 }}


                 /* Default Tooltip Style - This will be used if Qt can render HTML tooltips */
                 /* If tooltips still don't show with complex HTML, this part might be too restrictive */
                 /* or the HTML content itself has issues. */
                 QToolTip {{
                     background-color: {COLOR_TOOLTIP_BG};
                     color: {COLOR_TEXT_DARK};
                     border: 1px solid black;
                     padding: 3px; /* Slightly more padding */
                     border-radius: 3px;
                     /* font-family: "{self.font_family_base}"; */ /* Explicit font for tooltip */
                     /* font-size: {self.get_font_size("small")}pt; */ /* Smaller font for tooltip */
                     /* max-width: 400px; */ /* Optional: constrain tooltip width */
                 }}
            """

            self.setStyleSheet(stylesheet)
            style_logger.info("Application stylesheet applied with updated and commented sections.")

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
        """Thiết lập giao diện người dùng cho tab Cài đặt."""
        main_logger.debug("Thiết lập giao diện tab Cài đặt (PyQt5)...")
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

        settings_group_layout.addWidget(QLabel("🔗 URL đồng bộ dữ liệu:"), 1, 0, Qt.AlignLeft)
        self.config_sync_url_edit = QLineEdit()
        self.config_sync_url_edit.setToolTip("URL để tải dữ liệu mới khi nhấn nút 'Sync' ở tab Main.")
        settings_group_layout.addWidget(self.config_sync_url_edit, 1, 1, 1, 3)

        self.auto_sync_checkbox = QCheckBox("  Tự động đồng bộ kết quả quay thưởng hàng ngày 📅  ")
        self.auto_sync_checkbox.setToolTip(
            "Nếu bật, chương trình sẽ tự động kiểm tra và đồng bộ dữ liệu từ URL trên khi khởi động."
        )
        settings_group_layout.addWidget(self.auto_sync_checkbox, 2, 1, 1, 3, Qt.AlignLeft)

        settings_group_layout.addWidget(QLabel("🔗 Link danh sách thuật toán:"), 3, 0, Qt.AlignLeft)
        self.config_algo_list_url_edit = QLineEdit()
        self.config_algo_list_url_edit.setToolTip("URL của file text chứa danh sách thuật toán online.")
        settings_group_layout.addWidget(self.config_algo_list_url_edit, 3, 1, 1, 3)

        settings_group_layout.addWidget(QLabel("💻 Kích thước cửa sổ:"), 4, 0, Qt.AlignLeft)
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
        settings_group_layout.addWidget(size_frame, 4, 1, 1, 3)

        settings_group_layout.addWidget(QLabel("🔤 Font chữ (Cần khởi động lại):"), 5, 0, Qt.AlignLeft)
        font_frame = QWidget()
        font_layout = QHBoxLayout(font_frame)
        font_layout.setContentsMargins(0,0,0,0)
        font_layout.setSpacing(10)
        self.theme_font_family_base_combo = QComboBox()
        self.theme_font_family_base_combo.addItems(self.available_fonts)
        self.theme_font_family_base_combo.setToolTip("Chọn font chữ mặc định cho ứng dụng.")
        font_layout.addWidget(self.theme_font_family_base_combo, 1)
        font_layout.addWidget(QLabel("Cỡ:"))
        self.theme_font_size_base_spinbox = QSpinBox()
        self.theme_font_size_base_spinbox.setRange(8, 24)
        self.theme_font_size_base_spinbox.setToolTip("Chọn cỡ chữ mặc định (points).")
        self.theme_font_size_base_spinbox.setFixedWidth(60)
        font_layout.addWidget(self.theme_font_size_base_spinbox)
        font_layout.addStretch(1)
        settings_group_layout.addWidget(font_frame, 5, 1, 1, 3)

        settings_group_layout.addWidget(QLabel("🔄 Tự động kiểm tra cập nhật:"), 6, 0, Qt.AlignLeft)
        auto_update_frame = QWidget()
        auto_update_layout = QHBoxLayout(auto_update_frame)
        auto_update_layout.setContentsMargins(0,0,0,0)
        auto_update_layout.setSpacing(10)

        self.auto_check_update_checkbox = QCheckBox("Bật khi khởi động")
        self.auto_check_update_checkbox.setToolTip(
            "Nếu bật, chương trình sẽ tự động kiểm tra cập nhật khi khởi động."
        )
        auto_update_layout.addWidget(self.auto_check_update_checkbox)

        self.update_notification_combo = QComboBox()
        self.update_notification_combo.setToolTip(
            "Cách thức thông báo nếu có bản cập nhật mới (khi tự động kiểm tra)."
        )
        self.update_notification_combo.addItem("Thông báo mỗi khi khởi động", "every_startup")
        self.update_notification_combo.addItem("Chỉ thông báo 1 lần cho phiên bản này", "once_per_version")
        self.update_notification_combo.setEnabled(False)
        auto_update_layout.addWidget(self.update_notification_combo)
        auto_update_layout.addStretch(1)
        
        self.auto_check_update_checkbox.toggled.connect(
            lambda checked: self.update_notification_combo.setEnabled(checked)
        )
        settings_group_layout.addWidget(auto_update_frame, 6, 1, 1, 3)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        settings_group_layout.addWidget(separator, 7, 0, 1, 4)

        settings_group_layout.addWidget(QLabel("⚙️ Quản lý file cấu hình khác:"), 8, 0, Qt.AlignLeft)
        self.config_listwidget = QListWidget()
        self.config_listwidget.setFixedHeight(80)
        self.config_listwidget.setToolTip("Double-click để tải file cấu hình đã chọn.")
        self.config_listwidget.itemDoubleClicked.connect(self.load_selected_config_qt)
        settings_group_layout.addWidget(self.config_listwidget, 9, 0, 1, 4)
        self.update_config_list()

        settings_tab_layout.addWidget(settings_group)

        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)

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

        load_cfg_button = QPushButton("📂 Tải Cấu Hình")
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

        log_display_group = QGroupBox("Nhật Ký Hoạt Động Chương Trình")
        log_display_group_layout = QVBoxLayout(log_display_group)
        log_display_group_layout.setContentsMargins(5, 10, 5, 5)

        self.settings_log_display = QTextEdit()
        self.settings_log_display.setReadOnly(True)
        log_font = self.get_qfont("code")
        if log_font:
             self.settings_log_display.setFont(log_font)
        else:
             fallback_font = QFont("Courier New", 9)
             self.settings_log_display.setFont(fallback_font)
             main_logger.warning("Could not get 'code' font from get_qfont, using fallback for settings log display.")

        self.settings_log_display.setMinimumHeight(150)
        self.settings_log_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.settings_log_display.setStyleSheet("""
            QTextEdit {
                background-color: #F0F0F0;
                color: #111111;
                border: 1px solid #C0C0C0;
                font-family: Consolas, 'Courier New', monospace;
            }
        """)
        log_display_group_layout.addWidget(self.settings_log_display)
        settings_tab_layout.addWidget(log_display_group, 1)

        self._populate_settings_tab_ui() 
        main_logger.debug("Hoàn tất thiết lập giao diện tab Cài đặt.")

    def _append_log_to_settings_display(self, message: str):
        if hasattr(self, 'settings_log_display') and self.settings_log_display:
            try:
                cursor = self.settings_log_display.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.settings_log_display.setTextCursor(cursor)
                self.settings_log_display.insertPlainText(message + '\n')
                self.settings_log_display.ensureCursorVisible()
            except Exception as e:
                print(f"ERROR updating settings_log_display: {e}", file=sys.stderr)

    def setup_update_tab(self):
        self.update_logger.info("Setting up Update tab UI...")
        update_tab_overall_layout = QVBoxLayout(self.update_tab_frame)
        update_tab_overall_layout.setContentsMargins(10, 10, 10, 10)
        update_tab_overall_layout.setSpacing(10)

        self.info_groupbox_update = QGroupBox("Thông Tin Ứng Dụng")
        info_group_main_layout_update = QGridLayout(self.info_groupbox_update)
        info_group_main_layout_update.setContentsMargins(10, 15, 10, 10)
        info_group_main_layout_update.setSpacing(20)

        left_info_widget_update = QWidget()
        left_info_widget_update.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_layout_update = QVBoxLayout(left_info_widget_update)
        left_layout_update.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        left_layout_update.setSpacing(8)

        if not self.current_app_version_info:
            try:
                running_file_path = Path(sys.argv[0] if hasattr(sys, 'frozen') else __file__).resolve()
                current_content = running_file_path.read_text(encoding='utf-8')
                self.current_app_version_info = self._extract_app_version_info(current_content)
            except Exception as e:
                self.update_logger.error(f"Could not read current app version in setup_update_tab: {e}")
                self.current_app_version_info = {"version": "N/A", "date": "N/A", "update_notes": "Lỗi đọc file"}
        version_str = self.current_app_version_info.get("version", "N/A")
        date_str = self.current_app_version_info.get("date", "N/A")

        version_label_update = QLabel(f"<b>Lottery Predictor V{version_str}</b> by Luvideez <br>(Ngày cập nhật: {date_str})")
        version_label_update.setTextFormat(Qt.RichText)
        left_layout_update.addWidget(version_label_update)

        libs_label_update = QLabel("<b>Thư viện sử dụng:</b>")
        left_layout_update.addWidget(libs_label_update)
        libs_update = f"Python {sys.version.split()[0]}, PyQt5"
        try: import requests; libs_update += ", requests"
        except ImportError: pass
        try: from packaging.version import parse; libs_update += ", packaging"
        except ImportError: pass
        global HAS_ASTOR
        if sys.version_info < (3,9) and HAS_ASTOR: libs_update += ", astor"

        libs_val_label_update = QLabel(libs_update)
        libs_val_label_update.setStyleSheet("color: #17a2b8;")
        left_layout_update.addWidget(libs_val_label_update)
        sys_info_title_label_update = QLabel("<b>Thư mục gốc:</b>")
        left_layout_update.addWidget(sys_info_title_label_update)
        sys_info_update = f"{self.base_dir}"
        sys_info_label_update = QLabel(sys_info_update)
        sys_info_label_update.setTextFormat(Qt.RichText)
        sys_info_label_update.setStyleSheet("color: #17a2b8;")
        sys_info_label_update.setWordWrap(True)
        left_layout_update.addWidget(sys_info_label_update)
        left_layout_update.addStretch(1)
        info_group_main_layout_update.addWidget(left_info_widget_update, 0, 0)

        middle_info_widget_update = QWidget()
        middle_info_widget_update.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        middle_layout_update = QVBoxLayout(middle_info_widget_update)
        middle_layout_update.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        middle_layout_update.setSpacing(10)
        support_title_label_update = QLabel("Ủng hộ chương trình bằng cách sau:")
        support_title_label_update.setFont(self.get_qfont("bold"))
        middle_layout_update.addWidget(support_title_label_update)
        bank_label_update = QLabel("Ngân hàng: <b>CAKE BY VPBANK</b>")
        bank_label_update.setTextFormat(Qt.RichText)
        middle_layout_update.addWidget(bank_label_update)
        account_num_widget_update = QWidget()
        account_num_h_layout_update = QHBoxLayout(account_num_widget_update)
        account_num_h_layout_update.setContentsMargins(0,0,0,0)
        account_num_label_update = QLabel("Số tài khoản: 0987575432")

        self.copy_account_button_update_tab = QPushButton("COPY")
        self.copy_account_button_update_tab.setFixedSize(QSize(90, 35))
        self.copy_account_button_update_tab.setToolTip("Sao chép số tài khoản vào clipboard")
        try: self.copy_account_button_update_tab.clicked.disconnect()
        except TypeError: pass
        self.copy_account_button_update_tab.clicked.connect(self._copy_account_number)

        account_num_h_layout_update.addWidget(account_num_label_update)
        account_num_h_layout_update.addWidget(self.copy_account_button_update_tab)
        account_num_h_layout_update.addStretch()
        middle_layout_update.addWidget(account_num_widget_update)
        owner_label_update = QLabel("Chủ tài khoản: NGO THE QUAN")
        middle_layout_update.addWidget(owner_label_update)
        middle_layout_update.addStretch(1)
        info_group_main_layout_update.addWidget(middle_info_widget_update, 0, 1)

        right_info_widget_update = QWidget()
        right_layout_update = QVBoxLayout(right_info_widget_update)
        right_layout_update.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        self.qr_code_label_update_tab = SquareQLabel()
        self._display_qr_code(target_label=self.qr_code_label_update_tab)
        right_layout_update.addWidget(self.qr_code_label_update_tab, 0)
        info_group_main_layout_update.addWidget(right_info_widget_update, 0, 2)

        info_group_main_layout_update.setColumnStretch(0, 1)
        info_group_main_layout_update.setColumnStretch(1, 1)
        info_group_main_layout_update.setColumnStretch(2, 0)
        update_tab_overall_layout.addWidget(self.info_groupbox_update)


        update_main_groupbox = QGroupBox("Cập Nhật Ứng Dụng")
        update_group_layout_main = QVBoxLayout(update_main_groupbox)

        update_settings_widget = QWidget()
        update_settings_form = QFormLayout(update_settings_widget)
        update_settings_form.setSpacing(8)
        update_settings_form.setContentsMargins(0,0,0,10)

        project_path_layout = QHBoxLayout()
        self.update_project_path_edit = QLineEdit("https://github.com/junlangzi/Lottery-Predictor/")
        self.update_project_path_default_checkbox = QCheckBox("Mặc định")
        self.update_project_path_default_checkbox.setChecked(True)
        project_path_layout.addWidget(self.update_project_path_edit, 1)
        project_path_layout.addWidget(self.update_project_path_default_checkbox)
        update_settings_form.addRow("Đường dẫn dự án:", project_path_layout)

        self.update_file_url_edit = QLineEdit()
        update_settings_form.addRow("Link file cập nhật:", self.update_file_url_edit)

        save_and_check_layout = QHBoxLayout()
        save_and_check_layout.setSpacing(8)
        save_and_check_layout.addWidget(QLabel("Lưu tên file thành:"))
        self.update_save_filename_edit = QLineEdit("main.py")
        self.update_save_filename_edit.setFixedWidth(150)
        save_and_check_layout.addWidget(self.update_save_filename_edit)
        self.update_check_button = QPushButton("Kiểm tra cập nhật")
        self.update_check_button.clicked.connect(self._handle_check_for_updates_thread)
        save_and_check_layout.addWidget(self.update_check_button)
        save_and_check_layout.addStretch(1)
        update_settings_form.addRow(save_and_check_layout)

        update_group_layout_main.addWidget(update_settings_widget)

        update_content_splitter = QSplitter(Qt.Horizontal)

        update_info_container_widget = QWidget()
        update_info_layout = QVBoxLayout(update_info_container_widget)
        update_info_layout.setContentsMargins(0,0,0,0)
        update_info_layout.addWidget(QLabel("<b>Thông tin cập nhật:</b>"))
        self.update_info_display_textedit = QTextEdit()
        self.update_info_display_textedit.setReadOnly(True)
        self.update_info_display_textedit.setFont(self.get_qfont("code"))
        update_info_layout.addWidget(self.update_info_display_textedit, 1)

        self.update_perform_button = QPushButton("Cập nhật ngay?")
        self.update_perform_button.setObjectName("AccentButton")
        self.update_perform_button.setVisible(False)
        self.update_perform_button.clicked.connect(self._handle_perform_update_thread)
        update_info_layout.addWidget(self.update_perform_button)

        update_actions_layout = QHBoxLayout()
        self.update_restart_button = QPushButton("Khởi động lại")
        self.update_restart_button.setVisible(False)
        self.update_restart_button.clicked.connect(self._handle_restart_application)
        self.update_exit_after_update_button = QPushButton("Thoát")
        self.update_exit_after_update_button.setVisible(False)
        self.update_exit_after_update_button.clicked.connect(self.close)
        update_actions_layout.addStretch()
        update_actions_layout.addWidget(self.update_restart_button)
        update_actions_layout.addWidget(self.update_exit_after_update_button)
        update_actions_layout.addStretch()
        update_info_layout.addLayout(update_actions_layout)
        update_content_splitter.addWidget(update_info_container_widget)

        commit_history_container_widget = QWidget()
        commit_history_layout = QVBoxLayout(commit_history_container_widget)
        commit_history_layout.setContentsMargins(0,0,0,0)
        commit_history_layout.addWidget(QLabel("<b>Lịch sử cập nhật Repository:</b>"))
        self.update_commit_history_textedit = QTextEdit()
        self.update_commit_history_textedit.setReadOnly(True)
        self.update_commit_history_textedit.setFont(self.get_qfont("code"))
        commit_history_layout.addWidget(self.update_commit_history_textedit, 1)
        update_content_splitter.addWidget(commit_history_container_widget)

        QTimer.singleShot(0, lambda: update_content_splitter.setSizes([update_content_splitter.width() // 2, update_content_splitter.width() // 2]))


        update_group_layout_main.addWidget(update_content_splitter, 1)
        update_tab_overall_layout.addWidget(update_main_groupbox, 1)

        self.update_project_path_edit.textChanged.connect(self._update_file_link_from_project_path)
        self.update_project_path_default_checkbox.toggled.connect(self._update_file_link_from_project_path)
        self.update_project_path_default_checkbox.toggled.connect(
            lambda checked: self.update_project_path_edit.setEnabled(not checked)
        )
        self.update_project_path_edit.setEnabled(not self.update_project_path_default_checkbox.isChecked())
        self._update_file_link_from_project_path()

        self._display_current_version_info()
        self.update_logger.info("Update tab UI setup complete with revised layout.")

    def _extract_app_version_info(self, file_content: str) -> dict:
        """Trích xuất thông tin phiên bản từ nội dung file."""
        info = {"version": "N/A", "date": "N/A", "update_notes": "N/A"}
        if not file_content:
            return info
        lines = file_content.splitlines()
        try:
            for line_num, line_text in enumerate(lines):
                if line_num >= 5:
                    break
                if line_text.lower().startswith("# version:"):
                    info["version"] = line_text.split(":", 1)[1].strip()
                elif line_text.lower().startswith("# date:"):
                    info["date"] = line_text.split(":", 1)[1].strip()
                elif line_text.lower().startswith("# update:"):
                    info["update_notes"] = line_text.split(":", 1)[1].strip()

            if info["version"] != "N/A":
                try:
                    parse_version(info["version"])
                except Exception:
                    self.update_logger.warning(f"Chuỗi phiên bản '{info['version']}' không theo chuẩn. Sử dụng nguyên trạng.")

            if info["date"] != "N/A":
                try:
                    datetime.datetime.strptime(info["date"], "%d/%m/%Y")
                except ValueError:
                    self.update_logger.warning(f"Chuỗi ngày '{info['date']}' không theo định dạng dd/mm/yyyy. Sử dụng nguyên trạng.")
        except Exception as e:
            self.update_logger.error(f"Lỗi khi phân tích thông tin phiên bản ứng dụng: {e}")
        return info

    def _format_version_info_for_display(self, info_dict: dict, title_prefix: str) -> str:
        """Định dạng thông tin phiên bản thành chuỗi HTML để hiển thị."""
        if not info_dict:
            return f"<div style='font-family: {self.get_qfont('code').family()}; font-size: {self.get_font_size('code')}pt;'>" \
                   f"<b>{title_prefix}</b><br>Không có thông tin.<br></div>"

        version = info_dict.get('version', 'N/A')
        date_val = info_dict.get('date', 'N/A')
        update_notes = info_dict.get('update_notes', 'N/A')

        update_notes_escaped = update_notes.replace('<', '<').replace('>', '>').replace('\n', '<br>                     ')

        font_family_code = self.get_qfont('code').family()
        font_size_code = self.get_font_size('code')

        return (
            f"<div style='font-family: \"{font_family_code}\", monospace; font-size: {font_size_code}pt;'>"
            f"<b>{title_prefix}</b><br>"
            f"  <b>Phiên bản:</b> {version}<br>"
            f"  <b>Ngày phát hành:</b> {date_val}<br>"
            f"  <b>Nội dung cập nhật:</b> {update_notes_escaped}<br>"
            f"</div>"
        )
    def _display_current_version_info(self):
        """Hiển thị thông tin phiên bản hiện tại lên UI của tab Update."""
        if self.update_info_display_textedit:
            try:
                if getattr(sys, 'frozen', False):
                    current_file_to_read = Path(sys.executable).parent / self.update_save_filename_edit.text()
                    if not current_file_to_read.exists():
                        current_file_to_read = Path(__file__).resolve()
                else:
                    current_file_to_read = Path(__file__).resolve()

                self.update_logger.info(f"Đọc thông tin phiên bản từ: {current_file_to_read}")
                current_content = current_file_to_read.read_text(encoding='utf-8')
                self.current_app_version_info = self._extract_app_version_info(current_content)
            except Exception as e:
                self.update_logger.error(f"Không thể đọc thông tin phiên bản từ file hiện tại: {e}")
                self.current_app_version_info = {"version": "Lỗi đọc", "date": "Lỗi đọc", "update_notes": "Lỗi đọc file"}

            formatted_info = self._format_version_info_for_display(
                self.current_app_version_info, "Phiên bản đang chạy:"
            )
            self.update_info_display_textedit.setHtml(formatted_info)

    def _fetch_online_content(self, url: str, timeout=15) -> str | None:
        """Tải nội dung từ URL (ví dụ: file Python online, Atom feed)."""
        import requests

        self.update_logger.info(f"Đang tải nội dung từ: {url}")
        self.update_status(f"Đang kết nối tới {url.split('/')[2]}...")
        QApplication.processEvents()
        try:
            response = requests.get(url, timeout=timeout, headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
            response.raise_for_status()
            self.update_logger.info(f"Tải thành công nội dung từ {url} (Status: {response.status_code})")
            self.update_status(f"Tải thành công từ {url.split('/')[-1]}.")
            return response.text
        except requests.exceptions.RequestException as e:
            self.update_logger.error(f"Lỗi mạng khi tải {url}: {e}")
            self.update_status(f"Lỗi mạng khi tải {url.split('/')[-1]}.")
            return None
        except Exception as e:
            self.update_logger.error(f"Lỗi không mong muốn khi tải {url}: {e}")
            self.update_status(f"Lỗi không xác định khi tải {url.split('/')[-1]}.")
            return None

    def _parse_github_atom_feed(self, atom_content: str) -> str:
        """Phân tích Atom feed từ GitHub và định dạng thành HTML."""
        if not atom_content:
            return "<p>Không thể tải lịch sử commit.</p>"
        self.update_logger.info("Đang phân tích GitHub Atom feed...")
        try:
            root = ET.fromstring(atom_content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            repo_name_text = "Repository"
            feed_title_node = root.find('atom:title', ns)
            if feed_title_node is not None and feed_title_node.text:
                 match_repo = re.search(r"Recent Commits to ([^:]+):", feed_title_node.text)
                 if match_repo:
                     repo_name_text = match_repo.group(1)

            font_family_code = self.get_qfont('code').family()
            font_size_code = self.get_font_size('code')

            formatted_history = [f"<div style='font-family: \"{font_family_code}\", monospace; font-size: {font_size_code}pt;'>"]
            formatted_history.append(f"<b>Lịch sử cập nhật ({repo_name_text})</b><br>")

            entries_found = 0
            for entry in root.findall('atom:entry', ns):
                if entries_found >= 20:
                    break
                title_node = entry.find('atom:title', ns)
                updated_node = entry.find('atom:updated', ns)

                title = title_node.text.strip() if title_node is not None and title_node.text else "N/A"
                updated_str = updated_node.text.strip() if updated_node is not None and updated_node.text else "N/A"

                dt_display = updated_str
                if updated_str != "N/A":
                    try:
                        utc_dt = datetime.datetime.strptime(updated_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                        vn_tz = datetime.timezone(datetime.timedelta(hours=7))
                        vn_dt = utc_dt.astimezone(vn_tz)
                        dt_display = vn_dt.strftime("%d-%m-%Y %H:%M:%S (GMT+7)")
                    except ValueError:
                        dt_display = updated_str + " (UTC)"

                title_escaped = title.replace('<', '<').replace('>', '>').replace('\n', '<br>                 ')

                formatted_history.append(f"<b>Ngày giờ:</b><br>  {dt_display}")
                formatted_history.append(f"<br>")
                formatted_history.append(f"<b>Hoạt động</b><br>  {title_escaped}")
                formatted_history.append("<hr style='border:none; border-top:1px dashed #ccc; margin:3px 0;'>")
                entries_found += 1

            if entries_found == 0:
                formatted_history.append("<br><i>Không có commit nào trong lịch sử hoặc lỗi parse.</i>")

            formatted_history.append("</div>")
            return "".join(formatted_history)
        except ET.ParseError as e:
            self.update_logger.error(f"Lỗi ParseError XML cho Atom feed: {e}")
            return f"<p>Lỗi parse XML Atom feed: {e}</p>"
        except Exception as e:
            self.update_logger.error(f"Lỗi phân tích Atom feed: {e}")
            return f"<p>Lỗi xử lý lịch sử commit: {e}</p>"

    def _compare_versions(self, current_info: dict, online_info: dict) -> bool:
        """
        So sánh phiên bản và ngày tháng.
        Trả về True nếu có bản cập nhật mới (online > current).
        """
        if not current_info or not online_info:
            self.update_logger.warning("So sánh phiên bản: Thiếu thông tin hiện tại hoặc online.")
            return False
        try:
            current_ver_str = current_info.get("version", "0.0.0")
            online_ver_str = online_info.get("version", "0.0.0")
            current_date_str = current_info.get("date", "01/01/1970")
            online_date_str = online_info.get("date", "01/01/1970")

            self.update_logger.info(f"So sánh: Hiện tại='{current_ver_str}' ({current_date_str}), Online='{online_ver_str}' ({online_date_str})")

            current_v = parse_version(current_ver_str)
            online_v = parse_version(online_ver_str)

            date_format = "%d/%m/%Y"
            current_d = datetime.datetime.strptime(current_date_str, date_format).date()
            online_d = datetime.datetime.strptime(online_date_str, date_format).date()

            if online_v > current_v:
                self.update_logger.info(f"Có cập nhật: Phiên bản online {online_v} > phiên bản hiện tại {current_v}")
                return True
            if online_v == current_v and online_d > current_d:
                self.update_logger.info(f"Có cập nhật: Cùng phiên bản {online_v}, nhưng ngày online {online_d} > ngày hiện tại {current_d}")
                return True

            self.update_logger.info(f"Không có cập nhật: Online ({online_v}, {online_d}) so với Hiện tại ({current_v}, {current_d})")
            return False
        except Exception as e:
            self.update_logger.error(f"Lỗi khi so sánh phiên bản: {e}")
            return False

    def _update_file_link_from_project_path(self):
        """
        Tự động cập nhật trường "Link file cập nhật" dựa trên "Đường dẫn dự án"
        nếu checkbox "Mặc định" được chọn và đường dẫn dự án là mặc định.
        """
        if not (hasattr(self, 'update_project_path_default_checkbox') and
                hasattr(self, 'update_project_path_edit') and
                hasattr(self, 'update_file_url_edit')):
            self.update_logger.warning("_update_file_link_from_project_path: Thiếu widget UI.")
            return

        use_default_project_path = self.update_project_path_default_checkbox.isChecked()
        project_path_text = self.update_project_path_edit.text().strip()
        default_project_url = "https://github.com/junlangzi/Lottery-Predictor/"
        default_raw_file_url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/main.py"

        self.update_project_path_edit.setEnabled(not use_default_project_path)

        if use_default_project_path:
            self.update_project_path_edit.setText(default_project_url)
            self.update_file_url_edit.setText(default_raw_file_url)
            self.update_file_url_edit.setEnabled(False)
        else:
            self.update_file_url_edit.setEnabled(True)
            if self.update_file_url_edit.text() == default_raw_file_url and project_path_text != default_project_url:
                self.update_file_url_edit.setText("")

    def _handle_check_for_updates_thread(self):
        """Xử lý việc kiểm tra cập nhật trong một luồng riêng."""
        if hasattr(self, 'update_check_button') and self.update_check_button:
            self.update_check_button.setEnabled(False)
        self.update_status("Đang kiểm tra cập nhật...")
        QApplication.processEvents()

        self.check_update_thread = QThread(self)
        self.check_update_worker = UpdateCheckWorker(self)
        self.check_update_worker.moveToThread(self.check_update_thread)

        self.check_update_worker.finished_signal.connect(self._on_check_update_finished)
        self.check_update_worker.update_info_signal.connect(self._display_update_check_results)
        self.check_update_worker.commit_history_signal.connect(
            lambda history_html: self.update_commit_history_textedit.setHtml(history_html)
            if hasattr(self, 'update_commit_history_textedit') and self.update_commit_history_textedit else None
        )
        self.check_update_worker.error_signal.connect(
            lambda error_msg: (
                QMessageBox.warning(self, "Lỗi Kiểm Tra Cập Nhật", error_msg),
                self.update_status(f"Lỗi kiểm tra cập nhật: {error_msg.splitlines()[0]}")
            )
        )
        self.check_update_thread.started.connect(self.check_update_worker.run_check)
        self.check_update_thread.finished.connect(self.check_update_thread.deleteLater)
        self.check_update_worker.finished_signal.connect(self.check_update_thread.quit)
        self.check_update_worker.finished_signal.connect(self.check_update_worker.deleteLater)

        self.check_update_thread.start()

    def _on_check_update_finished(self):
        """Slot được gọi khi luồng kiểm tra cập nhật hoàn thành."""
        if hasattr(self, 'update_check_button') and self.update_check_button:
            self.update_check_button.setEnabled(True)
        self.update_logger.info("Luồng kiểm tra cập nhật đã hoàn thành.")
        self.check_update_thread = None
        self.check_update_worker = None

    def _display_update_check_results(self, current_info_html, online_info_html, update_available):
        """Hiển thị kết quả kiểm tra cập nhật lên UI."""
        full_html_for_tab = ""
        status_message_for_bar = ""

        if update_available:
            full_html_for_tab += "<div style='color: green; font-weight: bold;'>Có bản cập nhật mới!</div><br>"
            full_html_for_tab += online_info_html
            full_html_for_tab += "<br><hr style='border-top: 1px solid #ccc; margin: 5px 0;'><br>"
            full_html_for_tab += current_info_html
            if hasattr(self, 'update_perform_button') and self.update_perform_button:
                self.update_perform_button.setVisible(True)
            status_message_for_bar = "Có bản cập nhật mới!"
        else:
            full_html_for_tab += "<div style='color: blue; font-weight: bold;'>Bạn đang dùng phiên bản mới nhất.</div><br><br>"
            full_html_for_tab += current_info_html
            if hasattr(self, 'update_perform_button') and self.update_perform_button:
                self.update_perform_button.setVisible(False)
            status_message_for_bar = "Đang dùng phiên bản mới nhất."

        if hasattr(self, 'update_info_display_textedit') and self.update_info_display_textedit:
            self.update_info_display_textedit.setHtml(full_html_for_tab)
        self.update_status(status_message_for_bar)

        is_auto_checking = False
        if self.config.has_section('UPDATE_CHECK'):
            is_auto_checking = self.config.getboolean('UPDATE_CHECK', 'auto_check_on_startup', fallback=False)

        if is_auto_checking and update_available:
            self.update_logger.info("Xử lý thông báo cập nhật tự động.")
            notification_frequency = self.config.get('UPDATE_CHECK', 'notification_frequency', fallback='every_startup')
            skipped_version_config = self.config.get('UPDATE_CHECK', 'skipped_version', fallback='')
            
            online_version_str = self.online_app_version_info.get("version", "N/A")

            if notification_frequency == 'once_per_version' and online_version_str == skipped_version_config:
                self.update_logger.info(f"Bỏ qua thông báo cho phiên bản {online_version_str} đã được skip.")
                return

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Có Cập Nhật Mới")
            msg_box.setIcon(QMessageBox.Information)
            
            version_text = self.online_app_version_info.get("version", "N/A")
            date_text = self.online_app_version_info.get("date", "N/A")
            notes_text = self.online_app_version_info.get("update_notes", "Không có ghi chú.")
            
            msg_box.setText(f"Đã tìm thấy phiên bản mới: <b>{version_text}</b> (Ngày: {date_text})")
            msg_box.setInformativeText(f"Nội dung cập nhật:\n{notes_text}\n\nBạn có muốn cập nhật ngay không?")

            update_button = msg_box.addButton("Cập nhật ngay", QMessageBox.AcceptRole)
            skip_button = msg_box.addButton("Bỏ qua", QMessageBox.RejectRole)
            
            if notification_frequency == 'every_startup':
                 dont_notify_again_button = msg_box.addButton("Không hỏi lại cho phiên bản này", QMessageBox.DestructiveRole)
            else:
                 dont_notify_again_button = None


            msg_box.setDefaultButton(update_button)
            msg_box.exec_()

            clicked_button = msg_box.clickedButton()

            if clicked_button == update_button:
                self.update_logger.info("Người dùng chọn 'Cập nhật ngay' từ thông báo tự động.")
                update_tab_index = -1
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.widget(i) == self.update_tab_frame:
                        update_tab_index = i
                        break
                if update_tab_index != -1:
                    self.tab_widget.setCurrentIndex(update_tab_index)
                    if hasattr(self, 'update_perform_button') and self.update_perform_button.isVisible():
                        self._handle_perform_update_thread()
                    else:
                        self.update_logger.warning("Nút 'Cập nhật ngay' trên tab Update không hiển thị, không thể tự động kích hoạt.")
                else:
                    self.update_logger.error("Không tìm thấy tab Update để chuyển tới.")

            elif clicked_button == skip_button:
                self.update_logger.info("Người dùng chọn 'Bỏ qua' cập nhật.")
                if notification_frequency == 'once_per_version':
                    self.config.set('UPDATE_CHECK', 'skipped_version', online_version_str)
                    self.save_config("settings.ini")
                    self.update_logger.info(f"Đã lưu phiên bản {online_version_str} vào danh sách skip.")
            
            elif dont_notify_again_button and clicked_button == dont_notify_again_button:
                 self.update_logger.info(f"Người dùng chọn 'Không hỏi lại cho phiên bản này' ({online_version_str}).")
                 self.config.set('UPDATE_CHECK', 'notification_frequency', 'once_per_version')
                 self.config.set('UPDATE_CHECK', 'skipped_version', online_version_str)
                 if hasattr(self, 'update_notification_combo'):
                    idx = self.update_notification_combo.findData('once_per_version')
                    if idx != -1: self.update_notification_combo.setCurrentIndex(idx)
                 self.save_config("settings.ini")


    def _handle_perform_update_thread(self):
        """Xử lý việc thực hiện cập nhật trong một luồng riêng."""
        if hasattr(self, 'update_perform_button') and self.update_perform_button:
            self.update_perform_button.setEnabled(False)
        self.update_status("Đang thực hiện cập nhật...")
        QApplication.processEvents()

        self.perform_update_thread = QThread(self)
        self.perform_update_worker = PerformUpdateWorker(self)
        self.perform_update_worker.moveToThread(self.perform_update_thread)

        self.perform_update_worker.finished_signal.connect(self._on_perform_update_finished)
        self.perform_update_worker.error_signal.connect(
             lambda error_msg: (
                QMessageBox.critical(self, "Lỗi Cập Nhật", error_msg),
                self.update_status(f"Cập nhật thất bại: {error_msg.splitlines()[0]}"),
                self.update_perform_button.setEnabled(True) if hasattr(self, 'update_perform_button') else None
            )
        )
        self.perform_update_thread.started.connect(self.perform_update_worker.run_update)
        self.perform_update_thread.finished.connect(self.perform_update_thread.deleteLater)
        self.perform_update_worker.finished_signal.connect(self.perform_update_thread.quit)
        self.perform_update_worker.finished_signal.connect(self.perform_update_worker.deleteLater)

        self.perform_update_thread.start()

    def _on_perform_update_finished(self, success, message):
        """Slot được gọi khi luồng thực hiện cập nhật hoàn thành."""
        if success:
            QMessageBox.information(self, "Cập Nhật Thành Công", message)
            self.update_status("Cập nhật thành công. Khởi động lại để áp dụng.")
            if hasattr(self, 'update_perform_button') and self.update_perform_button:
                self.update_perform_button.setVisible(False)
            if hasattr(self, 'update_restart_button') and self.update_restart_button:
                self.update_restart_button.setVisible(True)
            if hasattr(self, 'update_exit_after_update_button') and self.update_exit_after_update_button:
                self.update_exit_after_update_button.setVisible(True)
        else:
            if hasattr(self, 'update_perform_button') and self.update_perform_button:
                self.update_perform_button.setEnabled(True)
        self.perform_update_thread = None
        self.perform_update_worker = None


    def _handle_restart_application(self):
        """Xử lý việc khởi động lại ứng dụng."""
        self.update_logger.info("Đang yêu cầu khởi động lại ứng dụng...")
        try:
            self.close()
            QApplication.processEvents()

            python_executable = sys.executable
            script_path = Path(sys.argv[0] if hasattr(sys, 'frozen') else __file__).resolve()

            if getattr(sys, 'frozen', False):
                executable_to_run = sys.executable
                args_for_run = sys.argv
                self.update_logger.info(f"Khởi động lại ứng dụng đóng gói: {executable_to_run} {' '.join(args_for_run)}")
                if sys.platform == "win32":
                     subprocess.Popen([executable_to_run] + args_for_run[1:], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                else:
                    os.execv(executable_to_run, args_for_run)
            else:
                self.update_logger.info(f"Khởi động lại script: {python_executable} {script_path} {' '.join(sys.argv[1:])}")
                if sys.platform == "win32":
                    subprocess.Popen([python_executable, str(script_path)] + sys.argv[1:], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                else:
                    os.execv(python_executable, [python_executable, str(script_path)] + sys.argv[1:])

            QApplication.instance().quit()

        except Exception as e:
            self.update_logger.error(f"Không thể khởi động lại ứng dụng: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Khởi Động Lại", f"Không thể tự động khởi động lại ứng dụng: {e}\nVui lòng khởi động lại thủ công.")

    def _copy_account_number(self):
        """Copies the account number to the clipboard."""
        try:
            clipboard = QApplication.clipboard()
            account_number = "0987575432"
            clipboard.setText(account_number)
            self.update_status(f"Đã sao chép số tài khoản: {account_number}")
            
            original_text = self.copy_account_button.text()

            self.copy_account_button.setText("COPY!")
            self.copy_account_button.setEnabled(False)
            
            QTimer.singleShot(2000, lambda: (
                self.copy_account_button.setText(original_text),
                self.copy_account_button.setEnabled(True)
            ))
        except Exception as e:
            main_logger.error(f"Lỗi sao chép số tài khoản: {e}", exc_info=True)
            QMessageBox.warning(self, "Lỗi Sao Chép", f"Không thể sao chép: {e}")
            
    def _display_qr_code(self, target_label: SquareQLabel):
        """Loads a Base64 QR code string and displays it in the target_label."""
        if not target_label:
            main_logger.error("target_label không tồn tại khi gọi _display_qr_code.")
            return

        base64_qr_data_only = "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"

        if base64_qr_data_only == "PASTE_YOUR_BASE64_QR_CODE_DATA_HERE" or not base64_qr_data_only:
            placeholder_text = ("<i><b>QR Code sẽ hiển thị ở đây.</b><br>"
                                "Để thay đổi, sửa biến <b>base64_qr_data_only</b> trong file code Python, phương thức <b>_display_qr_code</b>.</i>")
            target_label.setText(placeholder_text)
            target_label.setFont(self.get_qfont("small"))
            target_label.setStyleSheet("font-style: italic; color: #4A4A4A; border: 1px dashed #AAAAAA; padding: 10px; background-color: #F0F0F0;")
            target_label.setWordWrap(True)
            return

        try:
            image_data = QtCore.QByteArray.fromBase64(base64_qr_data_only.encode('utf-8'))
            pixmap = QPixmap()
            if not pixmap.loadFromData(image_data, "PNG"):
                main_logger.error("Không thể tải QPixmap từ dữ liệu Base64.")
                target_label.setText("Lỗi tải QR (dữ liệu Base64 không hợp lệ hoặc không phải PNG).")
                target_label.setStyleSheet("color: red; font-weight: bold; border: 1px solid red;")
                return

            if not pixmap.isNull():
                target_label.setPixmap(pixmap)
                target_label.setStyleSheet("")
                main_logger.info("Đã hiển thị mã QR từ chuỗi Base64.")
            else:
                main_logger.error("QPixmap bị null sau khi tải từ dữ liệu Base64.")
                target_label.setText("Lỗi hiển thị QR (pixmap null).")
                target_label.setStyleSheet("color: red; font-weight: bold; border: 1px solid red;")

        except Exception as e:
            main_logger.error(f"Lỗi nghiêm trọng khi xử lý mã QR Base64: {e}", exc_info=True)
            target_label.setText(f"Lỗi QR:\n{e}")
            target_label.setStyleSheet("color: red; font-weight: bold; border: 1px solid red;")
            target_label.setWordWrap(True)

    def _populate_local_algorithms_management_list(self):
        algo_mgmnt_logger.info("Populating local algorithms list for management tab...")
        
        if hasattr(self, 'local_algo_manage_list_layout'):
            while self.local_algo_manage_list_layout.count() > 0:
                item = self.local_algo_manage_list_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            algo_mgmnt_logger.error("local_algo_manage_list_layout not found.")
            return

        self.local_algorithms_managed_ui.clear()

        if not hasattr(self, 'initial_local_algo_manage_label') or not self.initial_local_algo_manage_label:
            self.initial_local_algo_manage_label = QLabel("Đang tải thuật toán trên máy...")
            self.initial_local_algo_manage_label.setStyleSheet("font-style: italic; color: #6c757d;")
            self.initial_local_algo_manage_label.setAlignment(Qt.AlignCenter)
        
        if self.local_algo_manage_list_layout.indexOf(self.initial_local_algo_manage_label) == -1:
            self.local_algo_manage_list_layout.addWidget(self.initial_local_algo_manage_label)
        else:
            self.initial_local_algo_manage_label.setText("Đang tải thuật toán trên máy...")
            self.initial_local_algo_manage_label.setStyleSheet("font-style: italic; color: #6c757d;")


        if not self.algorithms_dir.is_dir():
            algo_mgmnt_logger.warning(f"Algorithms directory not found: {self.algorithms_dir}")
            if self.initial_local_algo_manage_label:
                 self.initial_local_algo_manage_label.setText(f"Lỗi: Không tìm thấy thư mục thuật toán:\n{self.algorithms_dir}")
                 self.initial_local_algo_manage_label.setStyleSheet("color: red;")
            return

        local_algo_files = [
            f for f in self.algorithms_dir.glob('*.py')
            if f.is_file() and f.name not in ["__init__.py", "base.py"]
        ]

        if not local_algo_files:
            if self.initial_local_algo_manage_label: 
                 self.initial_local_algo_manage_label.setText("Không có thuật toán nào trên máy.")
                 if self.local_algo_manage_list_layout.indexOf(self.initial_local_algo_manage_label) == -1:
                     self.local_algo_manage_list_layout.addWidget(self.initial_local_algo_manage_label)
            return
        
        if self.initial_local_algo_manage_label and \
           self.local_algo_manage_list_layout.indexOf(self.initial_local_algo_manage_label) != -1:
            self.local_algo_manage_list_layout.removeWidget(self.initial_local_algo_manage_label)
            self.initial_local_algo_manage_label.deleteLater()
            self.initial_local_algo_manage_label = None 


        for algo_path in local_algo_files:
            try: 
                content = algo_path.read_text(encoding='utf-8')
                metadata = self._extract_metadata_from_py_content(content) 
                
                algo_name_display = metadata.get("name") or algo_path.stem
                description = metadata.get("description") or "Không có mô tả."
                algo_id = metadata.get("id")
                algo_date_str = metadata.get("date_str")

                display_name_for_optimizer = f"{algo_name_display} ({algo_path.name})"

                card_frame = QFrame()
                card_frame.setObjectName("CardFrame")
                card_layout = QVBoxLayout(card_frame)
                card_layout.setContentsMargins(8,8,8,8)
                card_layout.setSpacing(5)

                name_label_text = algo_name_display
                if algo_id: name_label_text += f" (ID: {algo_id})"
                name_label = QLabel(name_label_text)
                name_label.setFont(self.get_qfont("bold"))
                name_label.setWordWrap(True)
                card_layout.addWidget(name_label)

                desc_label = QLabel(description)
                desc_label.setFont(self.get_qfont("small"))
                desc_label.setWordWrap(True)
                card_layout.addWidget(desc_label)
                
                file_info_text = f"File: {algo_path.name}"
                if algo_date_str: file_info_text += f" - Ngày file: {algo_date_str}"
                file_label = QLabel(file_info_text)
                file_label.setFont(self.get_qfont("italic_small"))
                file_label.setStyleSheet("color: #6c757d;")
                card_layout.addWidget(file_label)

                button_container = QWidget()
                button_container_layout = QHBoxLayout(button_container)
                button_container_layout.setContentsMargins(0,5,0,0)
                button_container_layout.setSpacing(5) 
                button_container_layout.addStretch(1)

                edit_button = QPushButton(" 🔨 Sửa  ")
                edit_button.setObjectName("ListAccentButton")
                edit_button.setToolTip(f"Chỉnh sửa tham số thuật toán: {algo_name_display}")
                edit_button.clicked.connect(
                    lambda checked=False, dn=display_name_for_optimizer: self._handle_manage_tab_edit_request(dn)
                )
                button_container_layout.addWidget(edit_button)

                optimize_button = QPushButton("🚀 Tối ưu")
                optimize_button.setObjectName("ListAccentButton")
                optimize_button.setToolTip(f"Tối ưu hóa thuật toán: {algo_name_display}")
                optimize_button.clicked.connect(
                    lambda checked=False, dn=display_name_for_optimizer: self._handle_manage_tab_optimize_request(dn)
                )
                button_container_layout.addWidget(optimize_button)
                
                delete_button = QPushButton("❎ Xóa") 
                delete_button.setObjectName("DangerButton") 
                delete_button.setToolTip(f"Xóa file thuật toán: {algo_path.name}")
                delete_button.clicked.connect(lambda checked=False, p=algo_path: self._handle_delete_local_algorithm(p))
                button_container_layout.addWidget(delete_button)
                
                card_layout.addWidget(button_container)

                self.local_algo_manage_list_layout.addWidget(card_frame)
                self.local_algorithms_managed_ui[str(algo_path)] = card_frame

            except AttributeError as ae: 
                if "_extract_metadata_from_py_content" in str(ae):
                    algo_mgmnt_logger.critical(f"CRITICAL: Method _extract_metadata_from_py_content not found in LotteryPredictionApp for {algo_path.name}. Please define it.")
                    error_item = QLabel(f"Lỗi nghiêm trọng khi xử lý {algo_path.name}: Thiếu phương thức nội bộ.")
                    error_item.setStyleSheet("color: red; font-weight: bold;")
                    self.local_algo_manage_list_layout.addWidget(error_item)
                else: 
                    algo_mgmnt_logger.error(f"AttributeError creating UI for local algorithm {algo_path.name}: {ae}", exc_info=True)
                    error_item = QLabel(f"Lỗi thuộc tính khi tải {algo_path.name}: {ae}")
                    error_item.setStyleSheet("color: red;")
                    self.local_algo_manage_list_layout.addWidget(error_item)
            except Exception as e:
                algo_mgmnt_logger.error(f"Error creating UI for local algorithm {algo_path.name}: {e}", exc_info=True)
                error_item = QLabel(f"Lỗi tải {algo_path.name}: {e}")
                error_item.setStyleSheet("color: red;")
                self.local_algo_manage_list_layout.addWidget(error_item)

            except AttributeError as ae: 
                if "_extract_metadata_from_py_content" in str(ae):
                    algo_mgmnt_logger.critical(f"CRITICAL: Method _extract_metadata_from_py_content not found in LotteryPredictionApp for {algo_path.name}. Please define it.")
                    error_item = QLabel(f"Lỗi nghiêm trọng khi xử lý {algo_path.name}: Thiếu phương thức nội bộ.")
                    error_item.setStyleSheet("color: red; font-weight: bold;")
                    self.local_algo_manage_list_layout.addWidget(error_item)
                else:
                    algo_mgmnt_logger.error(f"AttributeError creating UI for local algorithm {algo_path.name}: {ae}", exc_info=True)
                    error_item = QLabel(f"Lỗi thuộc tính khi tải {algo_path.name}: {ae}")
                    error_item.setStyleSheet("color: red;")
                    self.local_algo_manage_list_layout.addWidget(error_item)
            except Exception as e:
                algo_mgmnt_logger.error(f"Error creating UI for local algorithm {algo_path.name}: {e}", exc_info=True)
                error_item = QLabel(f"Lỗi tải {algo_path.name}: {e}")
                error_item.setStyleSheet("color: red;")
                self.local_algo_manage_list_layout.addWidget(error_item)

            except AttributeError as ae:
                if "_extract_metadata_from_py_content" in str(ae):
                    algo_mgmnt_logger.critical(f"CRITICAL: Method _extract_metadata_from_py_content not found in LotteryPredictionApp for {algo_path.name}. Please define it.")
                    error_item = QLabel(f"Lỗi nghiêm trọng khi xử lý {algo_path.name}: Thiếu phương thức nội bộ.")
                    error_item.setStyleSheet("color: red; font-weight: bold;")
                    self.local_algo_manage_list_layout.addWidget(error_item)
                else:
                    algo_mgmnt_logger.error(f"AttributeError creating UI for local algorithm {algo_path.name}: {ae}", exc_info=True)
                    error_item = QLabel(f"Lỗi thuộc tính khi tải {algo_path.name}: {ae}")
                    error_item.setStyleSheet("color: red;")
                    self.local_algo_manage_list_layout.addWidget(error_item)
            except Exception as e:
                algo_mgmnt_logger.error(f"Error creating UI for local algorithm {algo_path.name}: {e}", exc_info=True)
                error_item = QLabel(f"Lỗi tải {algo_path.name}: {e}")
                error_item.setStyleSheet("color: red;")
                self.local_algo_manage_list_layout.addWidget(error_item)

    def _handle_delete_local_algorithm(self, algo_path: Path):
        algo_mgmnt_logger.info(f"Attempting to delete local algorithm: {algo_path}")
        
        reply = QMessageBox.question(self, "Xác nhận Xóa",
                                     f"Bạn có chắc chắn muốn xóa file thuật toán này không?\n\n{algo_path.name}\n\nThao tác này không thể hoàn tác!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                algo_path.unlink()
                algo_mgmnt_logger.info(f"Successfully deleted algorithm file: {algo_path}")
                self.update_status(f"Đã xóa thuật toán: {algo_path.name}")

                self._populate_local_algorithms_management_list()
                
                self.reload_algorithms()

            except OSError as e:
                algo_mgmnt_logger.error(f"Error deleting algorithm file {algo_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "Lỗi Xóa File", f"Không thể xóa file thuật toán:\n{algo_path.name}\n\nLỗi: {e}")
            except Exception as e:
                algo_mgmnt_logger.error(f"Unexpected error during algorithm deletion {algo_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "Lỗi Không Xác Định", f"Đã xảy ra lỗi không mong muốn khi xóa thuật toán:\n{e}")

    def _fetch_and_populate_online_algorithms_list(self):
        """
        Tìm nạp danh sách thuật toán từ URL được cấu hình,
        sau đó tìm nạp chi tiết (mô tả) cho từng thuật toán và điền vào UI.
        """
        algo_mgmnt_logger.info("Đang tìm nạp và điền danh sách thuật toán online...")
        
        if hasattr(self, 'online_algo_list_layout'):
            while self.online_algo_list_layout.count() > 0:
                item = self.online_algo_list_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        else:
            algo_mgmnt_logger.error("online_algo_list_layout không tìm thấy.")
            return

        self.online_algorithms_ui.clear()

        if not hasattr(self, 'initial_online_algo_label') or not self.initial_online_algo_label:
            self.initial_online_algo_label = QLabel("Đang tải danh sách thuật toán online...")
            self.initial_online_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
            self.initial_online_algo_label.setAlignment(Qt.AlignCenter)
        
        if self.online_algo_list_layout.indexOf(self.initial_online_algo_label) == -1:
            self.online_algo_list_layout.addWidget(self.initial_online_algo_label)
        else: 
            self.initial_online_algo_label.setText("Đang tải danh sách thuật toán online...")
            self.initial_online_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        
        QApplication.processEvents()

        algo_list_url = self.config.get('DATA', 'algo_list_url', fallback="")
        if not algo_list_url:
            algo_mgmnt_logger.error("URL danh sách thuật toán chưa được cấu hình.")
            if self.initial_online_algo_label:
                self.initial_online_algo_label.setText("Lỗi: URL danh sách thuật toán chưa được cấu hình trong Cài đặt.")
                self.initial_online_algo_label.setStyleSheet("color: red;")
            return

        online_list_content = None
        try:
            import requests 
            response = requests.get(algo_list_url, timeout=15)
            response.raise_for_status()
            online_list_content = response.text
            algo_mgmnt_logger.info(f"Đã tìm nạp thành công danh sách thuật toán từ: {algo_list_url}")
        except requests.exceptions.RequestException as e:
            algo_mgmnt_logger.error(f"Không thể tìm nạp danh sách thuật toán online từ {algo_list_url}: {e}", exc_info=True)
            if self.initial_online_algo_label:
                self.initial_online_algo_label.setText(f"Lỗi tải danh sách online (mạng/URL):\n{e}")
                self.initial_online_algo_label.setStyleSheet("color: red;")
            return
        except Exception as e: 
            algo_mgmnt_logger.error(f"Lỗi không xác định khi tìm nạp danh sách online: {e}", exc_info=True)
            if self.initial_online_algo_label:
                self.initial_online_algo_label.setText(f"Lỗi không xác định khi tải danh sách:\n{e}")
                self.initial_online_algo_label.setStyleSheet("color: red;")
            return
        
        parsed_online_algos = []
        if online_list_content:
            line_pattern = re.compile(r"\[([^\]]+?)\]-\[([^\]]+?)\]-\[([^\]]+?)\]-\[(ID:\s*\d{6})\]", re.IGNORECASE)
            
            lines = online_list_content.splitlines()
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                match = line_pattern.fullmatch(line)
                if match:
                    parsed_url = match.group(1).strip()
                    name = match.group(2).strip()
                    date_str = match.group(3).strip()
                    id_full_part_in_brackets = match.group(4).strip()

                    id_numeric_match = re.search(r"\d{6}", id_full_part_in_brackets)
                    if id_numeric_match:
                        actual_id = id_numeric_match.group(0)
                        parsed_online_algos.append({
                            "url": parsed_url,
                            "name": name,
                            "date_str": date_str,
                            "id": actual_id,
                            "raw_line_for_debug": line 
                        })
                        algo_mgmnt_logger.debug(f"Parsed online algo: URL='{parsed_url}', Name='{name}', Date='{date_str}', ID='{actual_id}'")
                    else:
                        algo_mgmnt_logger.warning(f"Không thể trích xuất số ID từ '{id_full_part_in_brackets}' trong dòng: {line_num+1} -> '{line}'")
                else:
                    algo_mgmnt_logger.warning(f"Bỏ qua dòng không đúng định dạng regex {line_num+1} trong danh sách online: '{line}'")

        if not parsed_online_algos:
            if self.initial_online_algo_label:
                self.initial_online_algo_label.setText("Không tìm thấy thuật toán nào trong danh sách online hoặc định dạng file không đúng.")
                self.initial_online_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
            if self.initial_online_algo_label and self.online_algo_list_layout.indexOf(self.initial_online_algo_label) == -1:
                 self.online_algo_list_layout.addWidget(self.initial_online_algo_label)
            return
        
        if self.initial_online_algo_label and \
           self.online_algo_list_layout.indexOf(self.initial_online_algo_label) != -1:
            self.online_algo_list_layout.removeWidget(self.initial_online_algo_label)
            self.initial_online_algo_label.deleteLater()
            self.initial_online_algo_label = None

        algo_mgmnt_logger.info(f"Đã parse được {len(parsed_online_algos)} thuật toán online. Đang tạo UI cards...")
        for online_algo_data in parsed_online_algos:
            self._create_online_algorithm_card_qt(online_algo_data)
        
        algo_mgmnt_logger.info("Hoàn tất việc điền danh sách thuật toán online.")

    def _get_local_algorithm_metadata_by_id(self, target_id: str) -> tuple[Path | None, dict | None]:
        """Finds a local algorithm by its ID and returns its path and metadata."""
        if not target_id: return None, None
        for algo_file in self.algorithms_dir.glob("*.py"):
            if algo_file.is_file() and algo_file.name not in ["__init__.py", "base.py"]:
                try:
                    content = algo_file.read_text(encoding='utf-8')
                    metadata = self._extract_metadata_from_py_content(content)
                    if metadata.get("id") == target_id:
                        return algo_file, metadata
                except Exception:
                    continue
        return None, None

    def _create_online_algorithm_card_qt(self, online_algo_data: dict):
        """Creates a UI card for a single online algorithm."""
        algo_mgmnt_logger.debug(f"Creating UI card for online algo: {online_algo_data.get('name')}")
        
        online_url = online_algo_data["url"]
        online_name = online_algo_data["name"]
        online_date_str = online_algo_data["date_str"]
        online_id = online_algo_data["id"]

        description = "Đang tải mô tả..."
        online_code_content = None
        try:
            import requests
            py_response = requests.get(online_url, timeout=10)
            py_response.raise_for_status()
            online_code_content = py_response.text
            metadata_from_online_code = self._extract_metadata_from_py_content(online_code_content)
            description = metadata_from_online_code.get("description") or "Không có mô tả trong code."
            id_from_code = metadata_from_online_code.get("id")
            if id_from_code and id_from_code != online_id:
                algo_mgmnt_logger.warning(f"ID mismatch for {online_name}: List ID='{online_id}', Code ID='{id_from_code}'. Using list ID.")
        except requests.exceptions.RequestException as e:
            description = "Lỗi tải mô tả (mạng)."
            algo_mgmnt_logger.warning(f"Failed to fetch .py content for description of {online_name}: {e}")
        except Exception as e_desc:
            description = "Lỗi xử lý mô tả."
            algo_mgmnt_logger.warning(f"Failed to extract description for {online_name}: {e_desc}")


        card_frame = QFrame()
        card_frame.setObjectName("CardFrame")
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(8,8,8,8)
        card_layout.setSpacing(5)

        name_label_text = online_name
        name_label = QLabel(name_label_text)
        name_label.setFont(self.get_qfont("bold"))
        name_label.setWordWrap(True)
        card_layout.addWidget(name_label)

        desc_label = QLabel(description)
        desc_label.setFont(self.get_qfont("small"))
        desc_label.setWordWrap(True)
        card_layout.addWidget(desc_label)

        info_text = f"ID: {online_id} - Online Date: {online_date_str}"
        info_label = QLabel(info_text)
        info_label.setFont(self.get_qfont("italic_small"))
        info_label.setStyleSheet("color: #5a5a5a;")
        card_layout.addWidget(info_label)

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0,5,0,0)
        button_layout.addStretch(1)

        local_algo_path, local_metadata = self._get_local_algorithm_metadata_by_id(online_id)
        
        action_widget = None

        if local_algo_path and local_metadata:
            status_label_text = f"Đã có: {local_algo_path.name}"
            local_date_str = local_metadata.get("date_str")
            needs_update = False
            if local_date_str and online_date_str:
                try:
                    online_dt = datetime.datetime.strptime(online_date_str, "%d/%m/%Y")
                    local_dt = datetime.datetime.strptime(local_date_str, "%d/%m/%Y")
                    if online_dt > local_dt:
                        needs_update = True
                        status_label_text += f" (Local: {local_date_str} - Cần cập nhật)"
                    else:
                        status_label_text += f" (Local: {local_date_str} - Đã cập nhật)"
                except ValueError:
                    status_label_text += " (Lỗi so sánh ngày)"
                    algo_mgmnt_logger.warning(f"Date parse error comparing online {online_date_str} and local {local_date_str} for ID {online_id}")
            
            if needs_update:
                update_button = QPushButton("⬆️ Cập nhật")
                update_button.setObjectName("AccentButton")
                update_button.setToolTip(f"Cập nhật file local '{local_algo_path.name}' bằng phiên bản online.")
                update_button.clicked.connect(lambda chk=False, o_data=online_algo_data, l_path=local_algo_path, o_content=online_code_content : self._handle_update_online_algorithm(o_data, l_path, o_content))
                action_widget = update_button
            else:
                status_widget = QLabel(status_label_text)
                status_widget.setStyleSheet("color: green; font-style: italic;")
                action_widget = status_widget
        else:
            download_button = QPushButton("⬇️ Tải về")
            download_button.setObjectName("AccentButton")
            download_button.setToolTip(f"Tải và lưu thuật toán '{online_name}' vào thư mục algorithms.")
            download_button.clicked.connect(lambda chk=False, o_data=online_algo_data, o_content=online_code_content : self._handle_download_online_algorithm(o_data, o_content))
            action_widget = download_button
        
        if action_widget:
            button_layout.addWidget(action_widget)
        card_layout.addWidget(button_container)
        
        self.online_algo_list_layout.addWidget(card_frame)
        self.online_algorithms_ui[online_url] = card_frame


    def _handle_download_online_algorithm(self, online_algo_data: dict, online_code_content: str | None = None):
        online_url = online_algo_data["url"]
        online_name = online_algo_data["name"]
        
        filename_from_url_obj = Path(online_url)
        target_filename = filename_from_url_obj.stem + ".py"
        save_path = self.algorithms_dir / target_filename

        algo_mgmnt_logger.info(f"Downloading algorithm '{online_name}' from {online_url} to {save_path}")
        self.update_status(f"Đang tải về {target_filename}...")
        QApplication.processEvents()

        if save_path.exists():
            reply = QMessageBox.question(self, "File Tồn Tại",
                                         f"File '{target_filename}' đã tồn tại. Ghi đè?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                self.update_status("Tải về bị hủy do file đã tồn tại.")
                return
        
        try:
            if online_code_content is None: 
                import requests
                response = requests.get(online_url, timeout=15)
                response.raise_for_status()
                online_code_content = response.text
            
            save_path.write_text(online_code_content, encoding='utf-8')
            algo_mgmnt_logger.info(f"Successfully downloaded and saved to {save_path}")
            QMessageBox.information(self, "Tải Thành Công", f"Đã tải và lưu thuật toán:\n{target_filename}")
            self.update_status(f"Đã tải thành công: {target_filename}")
            
            self._refresh_algo_management_page() 
            self.reload_algorithms() 

        except requests.exceptions.RequestException as e:
            algo_mgmnt_logger.error(f"Network error downloading {online_url}: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Tải", f"Lỗi mạng khi tải {target_filename}:\n{e}")
            self.update_status(f"Lỗi tải {target_filename}.")
        except IOError as e:
            algo_mgmnt_logger.error(f"IOError saving {save_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Lưu File", f"Không thể lưu file {target_filename}:\n{e}")
            self.update_status(f"Lỗi lưu {target_filename}.")
        except Exception as e:
            algo_mgmnt_logger.error(f"Unexpected error downloading/saving {online_name}: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Không Xác Định", f"Lỗi khi tải {target_filename}:\n{e}")
            self.update_status(f"Lỗi không xác định khi tải {target_filename}.")


    def _handle_update_online_algorithm(self, online_algo_data: dict, local_algo_path: Path, online_code_content: str | None = None):
        online_url = online_algo_data["url"]
        online_name = online_algo_data["name"]
        
        algo_mgmnt_logger.info(f"Updating local algorithm '{local_algo_path.name}' from {online_url}")
        self.update_status(f"Đang cập nhật {local_algo_path.name}...")
        QApplication.processEvents()

        try:
            if online_code_content is None:
                import requests
                response = requests.get(online_url, timeout=15)
                response.raise_for_status()
                online_code_content = response.text

            backup_path = local_algo_path.with_suffix(local_algo_path.suffix + ".bak")
            try:
                if local_algo_path.exists():
                    shutil.copy2(local_algo_path, backup_path)
                    algo_mgmnt_logger.info(f"Backed up '{local_algo_path.name}' to '{backup_path.name}'")
            except Exception as e_backup:
                algo_mgmnt_logger.warning(f"Could not create backup for {local_algo_path.name}: {e_backup}")

            local_algo_path.write_text(online_code_content, encoding='utf-8')
            algo_mgmnt_logger.info(f"Successfully updated {local_algo_path}")
            QMessageBox.information(self, "Cập Nhật Thành Công", f"Đã cập nhật thuật toán:\n{local_algo_path.name}")
            self.update_status(f"Đã cập nhật thành công: {local_algo_path.name}")

            self._refresh_algo_management_page()
            self.reload_algorithms()

        except requests.exceptions.RequestException as e:
            algo_mgmnt_logger.error(f"Network error updating {online_url}: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Cập Nhật", f"Lỗi mạng khi cập nhật {local_algo_path.name}:\n{e}")
            self.update_status(f"Lỗi cập nhật {local_algo_path.name}.")
        except IOError as e:
            algo_mgmnt_logger.error(f"IOError saving updated {local_algo_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Lưu File", f"Không thể ghi đè file {local_algo_path.name}:\n{e}")
            self.update_status(f"Lỗi lưu khi cập nhật {local_algo_path.name}.")
        except Exception as e:
            algo_mgmnt_logger.error(f"Unexpected error updating {local_algo_path.name}: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Không Xác Định", f"Lỗi khi cập nhật {local_algo_path.name}:\n{e}")
            self.update_status(f"Lỗi không xác định khi cập nhật {local_algo_path.name}.")            

    def _populate_settings_tab_ui(self):
        """Điền dữ liệu từ config vào các widget trên tab Cài đặt."""
        main_logger.debug("Điền dữ liệu từ config vào giao diện tab Cài đặt...")
        try:
            default_data_path = str(self.data_dir / "xsmb-2-digits.json")
            default_sync_url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json"
            default_algo_list_url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor-Algorithms/refs/heads/main/update.lpa"
            default_auto_sync = False
            default_width = 1200
            default_height = 1000
            default_font_family = 'Segoe UI'
            default_font_size = 10
            default_auto_check_update = False
            default_update_notification_frequency = 'every_startup'


            if hasattr(self, 'config_data_path_edit'):
                data_file = self.config.get('DATA', 'data_file', fallback=default_data_path)
                self.config_data_path_edit.setText(data_file)
            else:
                main_logger.warning("Widget 'config_data_path_edit' không tìm thấy khi điền UI.")

            if hasattr(self, 'config_sync_url_edit'):
                sync_url = self.config.get('DATA', 'sync_url', fallback=default_sync_url)
                self.config_sync_url_edit.setText(sync_url)
            else:
                main_logger.warning("Widget 'config_sync_url_edit' không tìm thấy khi điền UI.")

            if hasattr(self, 'config_algo_list_url_edit'):
                algo_list_url = self.config.get('DATA', 'algo_list_url', fallback=default_algo_list_url)
                self.config_algo_list_url_edit.setText(algo_list_url)
            else:
                main_logger.warning("Widget 'config_algo_list_url_edit' không tìm thấy khi điền UI.")

            if hasattr(self, 'auto_sync_checkbox'):
                auto_sync = self.config.getboolean('DATA', 'auto_sync_on_startup', fallback=default_auto_sync)
                self.auto_sync_checkbox.setChecked(auto_sync)
            else:
                main_logger.warning("Widget 'auto_sync_checkbox' không tìm thấy khi điền UI.")

            if hasattr(self, 'window_width_edit'):
                width_str = self.config.get('UI', 'width', fallback=str(default_width))
                self.window_width_edit.setText(width_str)
            else:
                main_logger.warning("Widget 'window_width_edit' không tìm thấy khi điền UI.")

            if hasattr(self, 'window_height_edit'):
                height_str = self.config.get('UI', 'height', fallback=str(default_height))
                self.window_height_edit.setText(height_str)
            else:
                main_logger.warning("Widget 'window_height_edit' không tìm thấy khi điền UI.")

            if hasattr(self, 'theme_font_family_base_combo'):
                font_family_from_config = self.config.get('UI', 'font_family_base', fallback=default_font_family)
                index = self.theme_font_family_base_combo.findText(self.font_family_base, Qt.MatchFixedString)
                if index >= 0:
                     self.theme_font_family_base_combo.setCurrentIndex(index)
                else:
                     index_settings = self.theme_font_family_base_combo.findText(font_family_from_config, Qt.MatchFixedString)
                     if index_settings >=0: self.theme_font_family_base_combo.setCurrentIndex(index_settings)
                     else:
                        default_font_index = self.theme_font_family_base_combo.findText(default_font_family, Qt.MatchFixedString)
                        if default_font_index >= 0: self.theme_font_family_base_combo.setCurrentIndex(default_font_index)
                        else: self.theme_font_family_base_combo.setCurrentIndex(0)
            else:
                 main_logger.warning("Widget 'theme_font_family_base_combo' không tìm thấy khi điền UI.")

            if hasattr(self, 'theme_font_size_base_spinbox'):
                self.theme_font_size_base_spinbox.setValue(self.font_size_base)
            else:
                 main_logger.warning("Widget 'theme_font_size_base_spinbox' không tìm thấy khi điền UI.")
            
            if hasattr(self, 'auto_check_update_checkbox'):
                auto_check = self.config.getboolean('UPDATE_CHECK', 'auto_check_on_startup', fallback=default_auto_check_update)
                self.auto_check_update_checkbox.setChecked(auto_check)
                if hasattr(self, 'update_notification_combo'):
                    self.update_notification_combo.setEnabled(auto_check)
            else:
                main_logger.warning("Widget 'auto_check_update_checkbox' không tìm thấy khi điền UI.")

            if hasattr(self, 'update_notification_combo'):
                freq = self.config.get('UPDATE_CHECK', 'notification_frequency', fallback=default_update_notification_frequency)
                idx = self.update_notification_combo.findData(freq)
                if idx != -1:
                    self.update_notification_combo.setCurrentIndex(idx)
                else:
                    idx_fallback = self.update_notification_combo.findData(default_update_notification_frequency)
                    if idx_fallback != -1: self.update_notification_combo.setCurrentIndex(idx_fallback)
            else:
                main_logger.warning("Widget 'update_notification_combo' không tìm thấy khi điền UI.")

        except Exception as e:
            main_logger.error(f"Lỗi khi điền dữ liệu vào tab Cài đặt: {e}", exc_info=True)
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
            default_sync_url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json"
            default_algo_list_url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor-Algorithms/refs/heads/main/update.lpa"
            default_auto_sync = 'False'

            if not self.config.has_section('DATA'):
                main_logger.warning("Config missing [DATA] section. Adding default.")
                self.config.add_section('DATA')
                config_needs_saving = True
            
            if not self.config.has_option('DATA', 'data_file'):
                self.config.set('DATA','data_file', default_data_path)
                config_needs_saving = True
            if not self.config.has_option('DATA', 'sync_url'):
                self.config.set('DATA','sync_url', default_sync_url)
                config_needs_saving = True
            if not self.config.has_option('DATA', 'algo_list_url'):
                self.config.set('DATA','algo_list_url', default_algo_list_url)
                config_needs_saving = True
            if not self.config.has_option('DATA', 'auto_sync_on_startup'):
                self.config.set('DATA', 'auto_sync_on_startup', default_auto_sync)
                config_needs_saving = True

            default_width, default_height = 1200, 800
            default_font_family = 'Segoe UI'
            default_font_size = 10
            if not self.config.has_section('UI'):
                main_logger.warning("Config missing [UI] section. Adding default.")
                self.config.add_section('UI')
                config_needs_saving = True

            if not self.config.has_option('UI', 'width'):
                self.config.set('UI', 'width', str(default_width))
                config_needs_saving = True
            if not self.config.has_option('UI', 'height'):
                self.config.set('UI', 'height', str(default_height))
                config_needs_saving = True
            if not self.config.has_option('UI', 'font_family_base'):
                self.config.set('UI', 'font_family_base', default_font_family)
                config_needs_saving = True
            if not self.config.has_option('UI', 'font_size_base'):
                self.config.set('UI', 'font_size_base', str(default_font_size))
                config_needs_saving = True

            try:
                self.loaded_width = self.config.getint('UI', 'width')
                self.loaded_height = self.config.getint('UI', 'height')

                current_width_str = self.config.get('UI', 'width')
                current_height_str = self.config.get('UI', 'height')
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
                loaded_font_family = self.config.get('UI', 'font_family_base')
                if not self.available_fonts:
                    main_logger.error("System font list is empty! Using default font family for instance var.")
                    self.font_family_base = default_font_family
                    if loaded_font_family != default_font_family:
                        self.config.set('UI', 'font_family_base', default_font_family)
                        config_needs_saving = True
                elif loaded_font_family not in self.available_fonts:
                    main_logger.warning(f"Font '{loaded_font_family}' from config not found. Falling back to '{default_font_family}' for instance var.")
                    self.font_family_base = default_font_family
                    self.config.set('UI', 'font_family_base', self.font_family_base)
                    config_needs_saving = True
                else:
                    self.font_family_base = loaded_font_family

                original_size_str = self.config.get('UI', 'font_size_base')
                loaded_font_size = self.config.getint('UI', 'font_size_base')
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
         """
         Cập nhật các biến thành viên và một số widget UI dựa trên đối tượng self.config hiện tại.
         Thường được gọi sau khi self.config đã được đặt về giá trị mặc định.
         """
         main_logger.debug("Áp dụng các giá trị config mặc định vào biến và một số UI.")
         
         data_file = self.config.get('DATA', 'data_file', fallback=str(self.data_dir / "xsmb-2-digits.json"))
         sync_url = self.config.get('DATA', 'sync_url', fallback="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json")
         algo_list_url = self.config.get('DATA', 'algo_list_url', fallback="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor-Algorithms/refs/heads/main/update.lpa")

         width_str = self.config.get('UI', 'width', fallback="1200")
         height_str = self.config.get('UI', 'height', fallback="800")
         self.font_family_base = self.config.get('UI', 'font_family_base', fallback='Segoe UI')
         self.font_size_base = self.config.getint('UI', 'font_size_base', fallback=10)
         self.loaded_width = int(width_str)
         self.loaded_height = int(height_str)

         if hasattr(self, 'config_data_path_edit'): self.config_data_path_edit.setText(data_file)
         if hasattr(self, 'config_sync_url_edit'): self.config_sync_url_edit.setText(sync_url)
         if hasattr(self, 'config_algo_list_url_edit'): self.config_algo_list_url_edit.setText(algo_list_url)
         
         if hasattr(self, 'window_width_edit'): self.window_width_edit.setText(width_str)
         if hasattr(self, 'window_height_edit'): self.window_height_edit.setText(height_str)

         if hasattr(self, 'theme_font_family_base_combo'):
            index = self.theme_font_family_base_combo.findText(self.font_family_base, Qt.MatchFixedString)
            if index >=0: self.theme_font_family_base_combo.setCurrentIndex(index)
            else: self.theme_font_family_base_combo.setCurrentIndex(0)
         if hasattr(self, 'theme_font_size_base_spinbox'):
            self.theme_font_size_base_spinbox.setValue(self.font_size_base)

         if hasattr(self, 'sync_url_input'): self.sync_url_input.setText(sync_url)
         if hasattr(self, 'data_file_path_label'):
             self.data_file_path_label.setText(data_file)
             self.data_file_path_label.setToolTip(data_file)


         self.apply_algorithm_config_states()

    def set_default_config(self):
        """Thiết lập đối tượng self.config về các giá trị mặc định."""
        main_logger.info("Thiết lập đối tượng self.config về giá trị mặc định.")
        self.config = configparser.ConfigParser(interpolation=None)
        self.config['DATA'] = {
            'data_file': str(self.data_dir / "xsmb-2-digits.json"),
            'sync_url': "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json",
            'algo_list_url': "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor-Algorithms/refs/heads/main/update.lpa",
            'auto_sync_on_startup': 'False'
        }
        self.config['UI'] = {
            'width': '1200',
            'height': '1000',
            'font_family_base': 'Segoe UI',
            'font_size_base': '10'
        }
        self.config['UPDATE_CHECK'] = {
            'auto_check_on_startup': 'False',
            'notification_frequency': 'every_startup',
            'skipped_version': ''
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
        """Lưu đối tượng self.config hiện tại vào file được chỉ định."""
        main_logger.debug(f"Lưu đối tượng config vào file: {config_filename}...")
        save_path = self.config_dir / config_filename
        try:
            if not self.config.has_section('DATA'): self.config.add_section('DATA')
            if not self.config.has_section('UI'): self.config.add_section('UI')
            
            if not self.config.has_option('DATA', 'data_file'): 
                self.config.set('DATA', 'data_file', str(self.data_dir / "xsmb-2-digits.json"))
            if not self.config.has_option('DATA', 'sync_url'): 
                self.config.set('DATA', 'sync_url', "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json")
            if not self.config.has_option('DATA', 'algo_list_url'):
                self.config.set('DATA', 'algo_list_url', "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor-Algorithms/refs/heads/main/update.lpa")

            if not self.config.has_option('UI', 'width'): self.config.set('UI','width', '1200')
            if not self.config.has_option('UI', 'height'): self.config.set('UI','height', '800')
            if not self.config.has_option('UI', 'font_family_base'): self.config.set('UI','font_family_base', 'Segoe UI')
            if not self.config.has_option('UI', 'font_size_base'): self.config.set('UI','font_size_base', '10')

            with open(save_path, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)

            if config_filename == "settings.ini":
                if hasattr(self, 'sync_url_input'):
                     self.sync_url_input.setText(self.config.get('DATA','sync_url', fallback=''))
                self._apply_window_size_from_config()

            main_logger.info(f"Cấu hình đã được lưu vào: {save_path}")

        except Exception as e:
            main_logger.error(f"Lỗi khi lưu đối tượng config vào '{config_filename}': {e}", exc_info=True)
            raise

    def save_current_settings_to_main_config(self):
        """Lưu trạng thái hiện tại của các trường trong UI Cài đặt vào file settings.ini."""
        main_logger.info("Lưu cấu hình từ UI Cài đặt vào settings.ini...")
        try:
            if not self.config.has_section('DATA'): self.config.add_section('DATA')
            self.config.set('DATA', 'data_file', self.config_data_path_edit.text())
            self.config.set('DATA', 'sync_url', self.config_sync_url_edit.text())
            self.config.set('DATA', 'algo_list_url', self.config_algo_list_url_edit.text())
            if hasattr(self, 'auto_sync_checkbox'):
                self.config.set('DATA', 'auto_sync_on_startup', str(self.auto_sync_checkbox.isChecked()))

            if not self.config.has_section('UI'): self.config.add_section('UI')
            width_str = self.window_width_edit.text().strip()
            height_str = self.window_height_edit.text().strip()
            try: w = int(width_str) if width_str else 1200
            except ValueError: w = 1200
            try: h = int(height_str) if height_str else 1000
            except ValueError: h = 1000
            self.config.set('UI', 'width', str(w))
            self.config.set('UI', 'height', str(h))

            font_family = self.theme_font_family_base_combo.currentText()
            font_size = str(self.theme_font_size_base_spinbox.value())
            self.config.set('UI', 'font_family_base', font_family)
            self.config.set('UI', 'font_size_base', font_size)

            if not self.config.has_section('UPDATE_CHECK'):
                self.config.add_section('UPDATE_CHECK')
            if hasattr(self, 'auto_check_update_checkbox'):
                self.config.set('UPDATE_CHECK', 'auto_check_on_startup', str(self.auto_check_update_checkbox.isChecked()))
            if hasattr(self, 'update_notification_combo'):
                self.config.set('UPDATE_CHECK', 'notification_frequency', self.update_notification_combo.currentData())

            if hasattr(self, 'algorithms'):
                 for algo_name, algo_data in self.algorithms.items():
                     chk_enable = algo_data.get('chk_enable')
                     chk_weight = algo_data.get('chk_weight')
                     weight_entry = algo_data.get('weight_entry')
                     if not chk_enable or not chk_weight or not weight_entry: continue

                     config_section_name = algo_name
                     if not self.config.has_section(config_section_name):
                         self.config.add_section(config_section_name)

                     self.config.set(config_section_name, 'enabled', str(chk_enable.isChecked()))
                     self.config.set(config_section_name, 'weight_enabled', str(chk_weight.isChecked()))
                     value_to_save = weight_entry.text().strip()
                     value_to_save = value_to_save if self._is_valid_float_str(value_to_save) else "1.0"
                     self.config.set(config_section_name, 'weight_value', value_to_save)

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
            main_logger.error(f"Lỗi khi lưu cấu hình từ UI Cài đặt: {e}", exc_info=True)
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
        """Mở hộp thoại để lưu cấu hình hiện tại (từ UI Cài đặt) ra một file .ini mới."""
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
                protected_files = {"settings.ini", "performance_history.ini", "settings_optimizer.ini", "ui_theme.ini"}
                if new_filename.lower() in protected_files:
                    QMessageBox.warning(self, "Lưu Ý", f"Không nên ghi đè file hệ thống '{new_filename}'.\nVui lòng chọn tên khác.")
                    return

                temp_config_obj = configparser.ConfigParser(interpolation=None)

                if not temp_config_obj.has_section('DATA'): temp_config_obj.add_section('DATA')
                temp_config_obj.set('DATA', 'data_file', self.config_data_path_edit.text())
                temp_config_obj.set('DATA', 'sync_url', self.config_sync_url_edit.text())
                temp_config_obj.set('DATA', 'algo_list_url', self.config_algo_list_url_edit.text())
                if hasattr(self, 'auto_sync_checkbox'):
                    temp_config_obj.set('DATA', 'auto_sync_on_startup', str(self.auto_sync_checkbox.isChecked()))

                if not temp_config_obj.has_section('UI'): temp_config_obj.add_section('UI')
                w_str = self.window_width_edit.text(); h_str = self.window_height_edit.text()
                temp_config_obj.set('UI', 'width', w_str if w_str.isdigit() else '1200')
                temp_config_obj.set('UI', 'height', h_str if h_str.isdigit() else '1000')
                temp_config_obj.set('UI', 'font_family_base', self.theme_font_family_base_combo.currentText())
                temp_config_obj.set('UI', 'font_size_base', str(self.theme_font_size_base_spinbox.value()))
                
                if not temp_config_obj.has_section('UPDATE_CHECK'):
                    temp_config_obj.add_section('UPDATE_CHECK')
                if hasattr(self, 'auto_check_update_checkbox'):
                    temp_config_obj.set('UPDATE_CHECK', 'auto_check_on_startup', str(self.auto_check_update_checkbox.isChecked()))
                if hasattr(self, 'update_notification_combo'):
                    temp_config_obj.set('UPDATE_CHECK', 'notification_frequency', self.update_notification_combo.currentData())
                temp_config_obj.set('UPDATE_CHECK', 'skipped_version', '')

                if hasattr(self, 'algorithms'):
                     for algo_name, algo_data in self.algorithms.items():
                         chk_enable = algo_data.get('chk_enable')
                         chk_weight = algo_data.get('chk_weight')
                         weight_entry = algo_data.get('weight_entry')
                         if not chk_enable or not chk_weight or not weight_entry: continue
                         
                         sec_name = algo_name
                         if not temp_config_obj.has_section(sec_name): temp_config_obj.add_section(sec_name)
                         temp_config_obj.set(sec_name, 'enabled', str(chk_enable.isChecked()))
                         temp_config_obj.set(sec_name, 'weight_enabled', str(chk_weight.isChecked()))
                         w_val = weight_entry.text().strip()
                         temp_config_obj.set(sec_name, 'weight_value', w_val if self._is_valid_float_str(w_val) else "1.0")

                with open(filename, 'w', encoding='utf-8') as configfile:
                    temp_config_obj.write(configfile)

                self.update_config_list()
                QMessageBox.information(self, "Lưu Thành Công", f"Đã lưu cấu hình hiện tại vào:\n{new_filename}")
        except Exception as e:
            main_logger.error(f"Lỗi trong save_config_dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi", f"Đã xảy ra lỗi khi lưu file cấu hình mới:\n{e}")

    def _apply_default_config_to_vars(self):
         """
         Cập nhật các biến thành viên và một số widget UI dựa trên đối tượng self.config hiện tại.
         Thường được gọi sau khi self.config đã được đặt về giá trị mặc định.
         """
         main_logger.debug("Áp dụng các giá trị config mặc định vào biến và một số UI.")
         
         data_file = self.config.get('DATA', 'data_file', fallback=str(self.data_dir / "xsmb-2-digits.json"))
         sync_url = self.config.get('DATA', 'sync_url', fallback="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json")
         algo_list_url = self.config.get('DATA', 'algo_list_url', fallback="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor-Algorithms/refs/heads/main/update.lpa")
         auto_sync_default = self.config.getboolean('DATA', 'auto_sync_on_startup', fallback=False)


         width_str = self.config.get('UI', 'width', fallback="1200")
         height_str = self.config.get('UI', 'height', fallback="1000")
         self.font_family_base = self.config.get('UI', 'font_family_base', fallback='Segoe UI')
         self.font_size_base = self.config.getint('UI', 'font_size_base', fallback=10)
         self.loaded_width = int(width_str)
         self.loaded_height = int(height_str)

         if hasattr(self, 'config_data_path_edit'): self.config_data_path_edit.setText(data_file)
         if hasattr(self, 'config_sync_url_edit'): self.config_sync_url_edit.setText(sync_url)
         if hasattr(self, 'config_algo_list_url_edit'): self.config_algo_list_url_edit.setText(algo_list_url)
         if hasattr(self, 'auto_sync_checkbox'): self.auto_sync_checkbox.setChecked(auto_sync_default)
         
         if hasattr(self, 'window_width_edit'): self.window_width_edit.setText(width_str)
         if hasattr(self, 'window_height_edit'): self.window_height_edit.setText(height_str)

         if hasattr(self, 'theme_font_family_base_combo'):
            index = self.theme_font_family_base_combo.findText(self.font_family_base, Qt.MatchFixedString)
            if index >=0: self.theme_font_family_base_combo.setCurrentIndex(index)
            else: self.theme_font_family_base_combo.setCurrentIndex(0)
         if hasattr(self, 'theme_font_size_base_spinbox'):
            self.theme_font_size_base_spinbox.setValue(self.font_size_base)

         if hasattr(self, 'sync_url_input'): self.sync_url_input.setText(sync_url)
         if hasattr(self, 'data_file_path_label'):
             self.data_file_path_label.setText(data_file)
             self.data_file_path_label.setToolTip(data_file)

         self.apply_algorithm_config_states()

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
            "Bạn có chắc chắn muốn khôi phục TẤT CẢ cài đặt (bao gồm đường dẫn, URL, kích thước, font chữ, cài đặt cập nhật) về giá trị mặc định không?\n\n"
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

    def perform_auto_update_check_if_needed(self):
        main_logger.info("Kiểm tra điều kiện tự động kiểm tra cập nhật ứng dụng khi khởi động...")
        if not self.config.has_section('UPDATE_CHECK'):
            main_logger.warning("Config thiếu section UPDATE_CHECK, không thể kiểm tra auto-update check.")
            return

        if not self.config.getboolean('UPDATE_CHECK', 'auto_check_on_startup', fallback=False):
            main_logger.info("Tự động kiểm tra cập nhật ứng dụng bị tắt trong cấu hình.")
            return

        self.update_logger.info("Kích hoạt tự động kiểm tra cập nhật ứng dụng...")
        self.update_status("Đang tự động kiểm tra cập nhật ứng dụng...")
        QApplication.processEvents()
        self._handle_check_for_updates_thread()

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

    def perform_auto_sync_if_needed(self):
        main_logger.info("Kiểm tra điều kiện tự động đồng bộ khi khởi động...")
        if not hasattr(self, 'config') or not self.config.has_section('DATA'):
            main_logger.warning("Config chưa được tải hoặc thiếu section DATA, không thể kiểm tra auto-sync.")
            return

        if not self.config.getboolean('DATA', 'auto_sync_on_startup', fallback=False):
            main_logger.info("Tự động đồng bộ bị tắt trong cấu hình.")
            return

        sync_url = self.config.get('DATA', 'sync_url', fallback="").strip()
        if not sync_url:
            main_logger.warning("Không có URL đồng bộ được cấu hình, không thể tự động đồng bộ.")
            return

        if not self.results:
            main_logger.info("Không có dữ liệu local hoặc lỗi tải dữ liệu. Thử tự động đồng bộ...")
            self.update_status("Đang tự động đồng bộ do không có dữ liệu local...")
            QApplication.processEvents()
            self.sync_data()
            return

        try:
            latest_local_date = self.results[-1]['date']
            current_datetime = datetime.datetime.now()
            today_date = current_datetime.date()
            yesterday_date = today_date - datetime.timedelta(days=1)
            sync_time_threshold = datetime.time(18, 50)

            main_logger.info(f"Kiểm tra auto-sync: Local mới nhất={latest_local_date}, Hôm nay={today_date}, Ngưỡng giờ={sync_time_threshold}")

            if latest_local_date == today_date:
                main_logger.info("Dữ liệu đã là ngày hiện tại. Không cần tự động đồng bộ.")
                self.update_status("Dữ liệu đã được cập nhật mới nhất (auto-sync).")
                return

            if latest_local_date == yesterday_date:
                if current_datetime.time() < sync_time_threshold:
                    main_logger.info(f"Dữ liệu từ hôm qua, nhưng trước {sync_time_threshold}. Không tự động đồng bộ.")
                    self.update_status(f"Dữ liệu từ hôm qua, chưa đến giờ đồng bộ tự động (trước {sync_time_threshold.strftime('%H:%M')}).")
                    return
                else:
                    main_logger.info(f"Dữ liệu từ hôm qua và sau {sync_time_threshold}. Kích hoạt tự động đồng bộ.")
                    self.update_status(f"Đang tự động đồng bộ (dữ liệu hôm qua, sau {sync_time_threshold.strftime('%H:%M')})...")
                    QApplication.processEvents()
                    self.sync_data()
                    return

            if latest_local_date < yesterday_date:
                main_logger.info("Dữ liệu cũ hơn ngày hôm qua. Kích hoạt tự động đồng bộ.")
                self.update_status("Đang tự động đồng bộ (dữ liệu cũ)...")
                QApplication.processEvents()
                self.sync_data()
                return
            
            if latest_local_date > today_date:
                main_logger.warning(f"Dữ liệu local ({latest_local_date}) mới hơn ngày hiện tại ({today_date}). Không tự động đồng bộ.")
                self.update_status(f"Dữ liệu local mới hơn ngày hiện tại. Không tự động đồng bộ.")
                return

        except IndexError:
            main_logger.warning("Danh sách results rỗng khi kiểm tra auto-sync (sau khi check self.results ban đầu). Thử đồng bộ...")
            self.update_status("Đang tự động đồng bộ do dữ liệu local có vấn đề...")
            QApplication.processEvents()
            self.sync_data()
        except Exception as e:
            main_logger.error(f"Lỗi trong quá trình kiểm tra tự động đồng bộ: {e}", exc_info=True)
            self.update_status(f"Lỗi kiểm tra tự động đồng bộ: {e}")

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

            self.display_prediction_results_qt(final_scores_list, next_day_actual_result, next_day_actual_date, collected_results)
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

    def _get_frequency_info(self, number_to_check: int, end_date_for_stats: datetime.date, periods: list[int], historical_data: list) -> dict:
        """
        Calculates frequency of a number in historical data for given periods ending at end_date_for_stats.
        """
        frequency_stats = {}
        num_str_to_check = f"{number_to_check:02d}"

        for period_days in periods:
            start_date_limit = end_date_for_stats - datetime.timedelta(days=period_days -1)
            relevant_history_for_period = [
                item for item in historical_data
                if item['date'] >= start_date_limit and item['date'] <= end_date_for_stats
            ]

            count = 0
            if relevant_history_for_period:
                all_numbers_in_period = []
                for day_data in relevant_history_for_period:
                    extracted_nums = self.extract_numbers_from_result_dict(day_data.get('result', {}))
                    all_numbers_in_period.extend([f"{n:02d}" for n in extracted_nums])

                count = all_numbers_in_period.count(num_str_to_check)
            frequency_stats[period_days] = count
        return frequency_stats

    def _get_last_appearance_info(self, number_to_check: int, end_date_for_stats: datetime.date, historical_data: list) -> tuple[datetime.date | None, int | None]:
        """
        Finds the last appearance date and days_ago for a number.
        """
        last_appearance_date = None
        days_ago = None
        num_to_check_set = {number_to_check}

        sorted_relevant_history = sorted(
            [item for item in historical_data if item['date'] <= end_date_for_stats],
            key=lambda x: x['date'],
            reverse=True
        )

        for day_data in sorted_relevant_history:
            extracted_nums = self.extract_numbers_from_result_dict(day_data.get('result', {}))
            if num_to_check_set.intersection(extracted_nums):
                last_appearance_date = day_data['date']
                days_ago = (end_date_for_stats - last_appearance_date).days
                break
        return last_appearance_date, days_ago

    def _get_average_interval_info(self, number_to_check: int, end_date_for_stats: datetime.date, periods: list[int], historical_data: list) -> dict:
        """
        Calculates the average appearance interval for a number.
        """
        interval_stats = {}
        num_to_check_set = {number_to_check}

        for period_days in periods:
            start_date_limit = end_date_for_stats - datetime.timedelta(days=period_days - 1)
            relevant_history_for_period = sorted(
                [item for item in historical_data if start_date_limit <= item['date'] <= end_date_for_stats],
                key=lambda x: x['date']
            )

            appearance_dates = []
            for day_data in relevant_history_for_period:
                extracted_nums = self.extract_numbers_from_result_dict(day_data.get('result', {}))
                if num_to_check_set.intersection(extracted_nums):
                    appearance_dates.append(day_data['date'])

            if len(appearance_dates) < 2:
                interval_stats[period_days] = "N/A"
            else:
                intervals = []
                for i in range(len(appearance_dates) - 1):
                    intervals.append((appearance_dates[i+1] - appearance_dates[i]).days)
                avg_interval = sum(intervals) / len(intervals) if intervals else 0
                interval_stats[period_days] = f"{avg_interval:.1f}" if intervals else "N/A"
        return interval_stats

    def _generate_prediction_cell_tooltip(self, number_to_check: int, combined_score: float,
                                         prediction_reference_date: datetime.date,
                                         all_algorithm_scores: dict,
                                         historical_data_for_stats: list) -> str:
        """
        Generates a rich HTML tooltip for a predicted number cell.
        """
        
        num_str_to_check_tooltip = f"{number_to_check:02d}"

        tooltip_lines = [
            f"<div style='font-family: {self.font_family_base}; font-size: {self.font_size_base-1}pt;'>",
            f"<b>Số: {number_to_check:02d}</b> (Điểm tổng hợp: {combined_score:.1f})",
            "<hr style='margin: 2px 0;'>"
        ]

        tooltip_lines.append("<b>Điểm chi tiết từ thuật toán:</b>")
        algo_scores_found = False
        if isinstance(all_algorithm_scores, dict):
            for algo_name, algo_results in all_algorithm_scores.items():
                if isinstance(algo_results, dict):
                    score_for_this_num_str = algo_results.get(num_str_to_check_tooltip)
                    if score_for_this_num_str is not None:
                        try:
                            score_val = float(score_for_this_num_str)
                            if abs(score_val) > 1e-6:
                                display_algo_name = algo_name.split(' (')[0]
                                weight_info = ""
                                if algo_name in self.algorithms:
                                    algo_data_main = self.algorithms[algo_name]
                                    if algo_data_main.get('chk_enable') and algo_data_main['chk_enable'].isChecked() and \
                                       algo_data_main.get('chk_weight') and algo_data_main['chk_weight'].isChecked() and \
                                       algo_data_main.get('weight_entry'):
                                        weight_val_str = algo_data_main['weight_entry'].text()
                                        try:
                                            weight_f = float(weight_val_str)
                                            if abs(weight_f - 1.0) > 1e-6:
                                                weight_info = f" (hs: {weight_f:.2f})"
                                        except ValueError:
                                            pass
                                tooltip_lines.append(f"  - {display_algo_name}{weight_info}: {score_val:.1f}")
                                algo_scores_found = True
                        except (ValueError, TypeError) as e:
                            main_logger.warning(f"Could not parse score '{score_for_this_num_str}' for {num_str_to_check_tooltip} from {algo_name}: {e}")
        if not algo_scores_found:
             tooltip_lines.append("  <em>(Không có đóng góp điểm riêng lẻ)</em>")

        stats_end_date = prediction_reference_date - datetime.timedelta(days=1)
        periods_for_stats = [30, 100, 365]

        tooltip_lines.append(f"<hr style='margin: 2px 0;'><b>Tần suất xuất hiện (đến {stats_end_date:%d/%m/%Y}):</b>")
        try:
            freq_info = self._get_frequency_info(number_to_check, stats_end_date, periods_for_stats, historical_data_for_stats)
            for period in periods_for_stats:
                tooltip_lines.append(f"  - {period} ngày gần nhất: {freq_info.get(period, 'N/A')} lần")
        except Exception as e_freq:
            main_logger.error(f"Error getting frequency info for tooltip (num: {number_to_check}): {e_freq}", exc_info=True)
            tooltip_lines.append("  <em>Lỗi tính tần suất</em>")

        tooltip_lines.append(f"<hr style='margin: 2px 0;'><b>Lần cuối xuất hiện (đến {stats_end_date:%d/%m/%Y}):</b>")
        try:
            last_date, days_ago = self._get_last_appearance_info(number_to_check, stats_end_date, historical_data_for_stats)
            if last_date and days_ago is not None:
                tooltip_lines.append(f"  - Ngày: {last_date:%d/%m/%Y} (Cách đây {days_ago} ngày)")
            else:
                tooltip_lines.append("  - <em>Chưa xuất hiện trong dữ liệu</em>")
        except Exception as e_last:
            main_logger.error(f"Error getting last appearance info for tooltip (num: {number_to_check}): {e_last}", exc_info=True)
            tooltip_lines.append("  <em>Lỗi tính lần cuối xuất hiện</em>")

        tooltip_lines.append(f"<hr style='margin: 2px 0;'><b>Khoảng cách xuất hiện TB (đến {stats_end_date:%d/%m/%Y}):</b>")
        try:
            interval_info = self._get_average_interval_info(number_to_check, stats_end_date, periods_for_stats, historical_data_for_stats)
            for period in periods_for_stats:
                tooltip_lines.append(f"  - Trong {period} ngày gần nhất: {interval_info.get(period, 'N/A')} ngày")
        except Exception as e_interval:
            main_logger.error(f"Error getting average interval info for tooltip (num: {number_to_check}): {e_interval}", exc_info=True)
            tooltip_lines.append("  <em>Lỗi tính khoảng cách TB</em>")

        tooltip_lines.append("</div>")
        final_tooltip_html = "<br>".join(tooltip_lines)
        return final_tooltip_html

    

    def display_prediction_results_qt(self, sorted_predictions, next_day_actual_results, next_day_date, collected_algo_scores: dict):
        """Displays the prediction results in a new QDialog window with detailed tooltips."""
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
                        s_val = str(spec_val).strip()
                        if len(s_val) >= 2 and s_val[-2:].isdigit(): spec = int(s_val[-2:])
                        elif len(s_val) == 1 and s_val.isdigit(): spec = int(s_val)
                    except (ValueError, TypeError): spec = -1


            hit_bg_color = "#d4edda"; special_bg_color = "#fff3cd"; default_bg_color="#FFFFFF"
            hit_border_color = "#7fbf7f"; special_border_color="#ffcf40"; default_border_color="#D0D0D0"

            num_font = self.get_qfont("base")
            num_bold_font = self.get_qfont("bold")
            score_font = self.get_qfont("small")

            COLOR_HIT_FG, COLOR_SPECIAL_FG, COLOR_DEFAULT_FG = '#155724', '#856404', '#212529'
            COLOR_SCORE_HIT, COLOR_SCORE_SPECIAL, COLOR_SCORE_DEFAULT = '#1e7e34', '#b38600', '#6c757d'

            historical_data_for_tooltip = [r for r in self.results if r['date'] < self.selected_date]

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

                tooltip_text = self._generate_prediction_cell_tooltip(
                    num, score, self.selected_date, collected_algo_scores, historical_data_for_tooltip
                )
                cell_frame.setToolTip(tooltip_text)

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

    def setup_algo_management_tab(self):
        algo_mgmnt_logger.debug("Setting up Algorithm Management tab UI (PyQt5)...")
        tab_layout = QVBoxLayout(self.algo_management_tab_frame)
        tab_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.setSpacing(10)

        control_frame = QFrame()
        control_frame_layout = QHBoxLayout(control_frame)
        control_frame_layout.setContentsMargins(0,0,0,0)
        self.algo_mgmnt_refresh_button = QPushButton("♻️Tải thuật toán online")
        self.algo_mgmnt_refresh_button.setToolTip("Tải lại danh sách thuật toán trên máy và danh sách thuật toán online.")
        self.algo_mgmnt_refresh_button.clicked.connect(self._refresh_algo_management_page)
        control_frame_layout.addWidget(self.algo_mgmnt_refresh_button)
        control_frame_layout.addStretch(1)
        tab_layout.addWidget(control_frame)

        splitter = QSplitter(Qt.Horizontal)

        local_algo_group = QGroupBox("🎰Thuật toán trên máy")
        local_algo_layout = QVBoxLayout(local_algo_group)
        local_algo_layout.setContentsMargins(5, 10, 5, 5)

        self.local_algo_manage_scroll_area = QScrollArea()
        self.local_algo_manage_scroll_area.setWidgetResizable(True)
        self.local_algo_manage_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")
        
        self.local_algo_manage_widget = QWidget()
        self.local_algo_manage_scroll_area.setWidget(self.local_algo_manage_widget)
        self.local_algo_manage_list_layout = QVBoxLayout(self.local_algo_manage_widget)
        self.local_algo_manage_list_layout.setAlignment(Qt.AlignTop)
        self.local_algo_manage_list_layout.setSpacing(8)
        
        self.initial_local_algo_manage_label = QLabel("🎰Đang tải thuật toán trên máy...")
        self.initial_local_algo_manage_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_local_algo_manage_label.setAlignment(Qt.AlignCenter)
        self.local_algo_manage_list_layout.addWidget(self.initial_local_algo_manage_label)

        local_algo_layout.addWidget(self.local_algo_manage_scroll_area)
        splitter.addWidget(local_algo_group)

        online_algo_group = QGroupBox("📡Danh sách Thuật toán Online")
        online_algo_layout = QVBoxLayout(online_algo_group)
        online_algo_layout.setContentsMargins(5, 10, 5, 5)

        self.online_algo_scroll_area = QScrollArea()
        self.online_algo_scroll_area.setWidgetResizable(True)
        self.online_algo_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")

        self.online_algo_widget = QWidget()
        self.online_algo_scroll_area.setWidget(self.online_algo_widget)
        self.online_algo_list_layout = QVBoxLayout(self.online_algo_widget)
        self.online_algo_list_layout.setAlignment(Qt.AlignTop)
        self.online_algo_list_layout.setSpacing(8)

        self.initial_online_algo_label = QLabel("Nhấn 'Tải lại' để lấy danh sách thuật toán online...")
        self.initial_online_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_online_algo_label.setAlignment(Qt.AlignCenter)
        self.online_algo_list_layout.addWidget(self.initial_online_algo_label)
        
        online_algo_layout.addWidget(self.online_algo_scroll_area)
        splitter.addWidget(online_algo_group)

        tab_layout.addWidget(splitter, 1)

        QTimer.singleShot(0, lambda: splitter.setSizes([self.width() // 3, self.width() * 2 // 3]))

        self.local_algorithms_managed_ui = {}
        self.online_algorithms_ui = {}

        self._populate_local_algorithms_management_list()
        algo_mgmnt_logger.debug("Algorithm Management tab UI structure set up.")

    def _refresh_algo_management_page(self):
        algo_mgmnt_logger.info("Refreshing Algorithm Management page...")
        self.update_status("Đang làm mới danh sách thuật toán quản lý...")
        QApplication.processEvents()

        self._populate_local_algorithms_management_list()
        self._fetch_and_populate_online_algorithms_list()

        self.update_status("Làm mới danh sách thuật toán quản lý hoàn tất.")

    def _handle_manage_tab_edit_request(self, display_name_for_optimizer):
        """Handles edit request from Algorithm Management tab."""
        algo_mgmnt_logger.info(f"Edit request for '{display_name_for_optimizer}' from Algo Management Tab.")
        if self.optimizer_app_instance:
            optimizer_tab_index = -1
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.optimizer_tab_frame:
                    optimizer_tab_index = i
                    break
            
            if optimizer_tab_index != -1:
                self.tab_widget.setCurrentIndex(optimizer_tab_index)
                self.optimizer_app_instance.trigger_select_for_edit(display_name_for_optimizer)
            else:
                algo_mgmnt_logger.error("Optimizer tab frame (optimizer_tab_frame) not found when handling edit request.")
                QMessageBox.critical(self, "Lỗi Giao Diện", "Không tìm thấy tab Tối ưu.")
        else:
            algo_mgmnt_logger.error("Optimizer instance (optimizer_app_instance) not available for edit request.")
            QMessageBox.critical(self, "Lỗi Hệ Thống", "Trình tối ưu chưa được khởi tạo.")

    def _handle_manage_tab_optimize_request(self, display_name_for_optimizer):
        """Handles optimize request from Algorithm Management tab."""
        algo_mgmnt_logger.info(f"Optimize request for '{display_name_for_optimizer}' from Algo Management Tab.")
        if self.optimizer_app_instance:
            optimizer_tab_index = -1
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.optimizer_tab_frame:
                    optimizer_tab_index = i
                    break
            
            if optimizer_tab_index != -1:
                self.tab_widget.setCurrentIndex(optimizer_tab_index)
                self.optimizer_app_instance.trigger_select_for_optimize(display_name_for_optimizer)
            else:
                algo_mgmnt_logger.error("Optimizer tab frame (optimizer_tab_frame) not found when handling optimize request.")
                QMessageBox.critical(self, "Lỗi Giao Diện", "Không tìm thấy tab Tối ưu.")
        else:
            algo_mgmnt_logger.error("Optimizer instance (optimizer_app_instance) not available for optimize request.")
            QMessageBox.critical(self, "Lỗi Hệ Thống", "Trình tối ưu chưa được khởi tạo.")

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

        while self.tools_list_layout.count() > 0:
            item = self.tools_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not hasattr(self, 'initial_tools_label') or not self.initial_tools_label:
             self.initial_tools_label = QLabel("Đang tải công cụ...")
             self.initial_tools_label.setStyleSheet("font-style: italic; color: #6c757d;")
             self.initial_tools_label.setAlignment(Qt.AlignCenter)
        if self.tools_list_layout.indexOf(self.initial_tools_label) == -1:
             self.tools_list_layout.addWidget(self.initial_tools_label)


        if not hasattr(self, 'loaded_tools'):
            self.loaded_tools = {}
        self.loaded_tools.clear()
        count_success, count_failed = 0, 0

        if not self.tools_dir.is_dir():
            main_logger.warning(f"Tools directory not found: {self.tools_dir}.")
            self.initial_tools_label.setText(f"Lỗi: Không tìm thấy thư mục công cụ:\n{self.tools_dir}")
            return

        try:
            tool_files_to_load = [
                f for f in self.tools_dir.glob('*.pyw')
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
                self.initial_tools_label = None

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
         
        if not has_tools and self.initial_tools_label:
             self.initial_tools_label.setText("Không tìm thấy file công cụ (.pyw) nào trong thư mục 'tools'.")


        status_msg = f"Đã tải {count_success} công cụ"
        if count_failed > 0:
            status_msg += f", lỗi {count_failed} file"
        self.update_status(status_msg)

        if count_failed > 0:
            QMessageBox.warning(self, "Lỗi Tải Công Cụ", f"Đã xảy ra lỗi khi tải {count_failed} file công cụ.\nKiểm tra file log để biết chi tiết.")

    def extract_tool_info_from_file(self, tool_path: Path):
        display_name = tool_path.name
        description = "Không có mô tả."

        try:
            source_code = tool_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source_code)

            module_docstring = ast.get_docstring(tree)
            if module_docstring:
                description = module_docstring.strip().splitlines()[0]

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    elif isinstance(node.func, ast.Name):
                        func_name = node.func.id

                    if func_name == 'setWindowTitle':
                        if node.args:
                            first_arg = node.args[0]
                            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                                display_name = first_arg.value
                                break
                            elif hasattr(ast, 'Str') and isinstance(first_arg, ast.Str) and isinstance(first_arg.s, str):
                                display_name = first_arg.s
                                break
        except FileNotFoundError:
            main_logger.error(f"Tool file not found for info extraction: {tool_path}")
        except SyntaxError:
            main_logger.warning(f"Syntax error in tool file {tool_path.name}, cannot extract info via AST.")
        except Exception as e:
            main_logger.error(f"Error extracting info from {tool_path.name} using AST: {e}", exc_info=True)
        
        if description == "Không có mô tả.":
             try:
                 with tool_path.open('r', encoding='utf-8', errors='ignore') as f:
                     for line in f:
                         stripped_line = line.strip()
                         if stripped_line.startswith('# DESC:'):
                             description = stripped_line[len('# DESC:'):].strip()
                             break
                         if stripped_line and not stripped_line.startswith('#'):
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
            button_v_layout.addWidget(run_button, alignment=Qt.AlignVCenter | Qt.AlignRight)
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
            try:
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
        """Xử lý sự kiện đóng cửa sổ chính."""
        main_logger.info("Close event triggered for QMainWindow.")

        if hasattr(self, 'check_update_thread') and self.check_update_thread and self.check_update_thread.isRunning():
            self.update_logger.info("Stopping update check thread...")
            self.check_update_thread.quit()
            if not self.check_update_thread.wait(1000):
                self.update_logger.warning("Update check thread did not finish in time.")
        self.check_update_thread = None

        if hasattr(self, 'perform_update_thread') and self.perform_update_thread and self.perform_update_thread.isRunning():
            self.update_logger.info("Stopping perform update thread...")
            self.perform_update_thread.quit()
            if not self.perform_update_thread.wait(1000):
                self.update_logger.warning("Perform update thread did not finish in time.")
        self.perform_update_thread = None

        if hasattr(self, 'prediction_timer') and self.prediction_timer.isActive():
            self.prediction_timer.stop()
            main_logger.debug("Stopped prediction timer.")
        if hasattr(self, 'performance_timer') and self.performance_timer.isActive():
            self.performance_timer.stop()
            main_logger.debug("Stopped performance timer.")

        optimizer_was_running_and_cancelled_exit = False
        if hasattr(self, 'optimizer_app_instance') and self.optimizer_app_instance:
            if hasattr(self.optimizer_app_instance, 'optimizer_timer') and self.optimizer_app_instance.optimizer_timer.isActive():
                self.optimizer_app_instance.optimizer_timer.stop()
                main_logger.debug("Stopped optimizer queue timer (from main app close).")
            if hasattr(self.optimizer_app_instance, 'display_timer') and self.optimizer_app_instance.display_timer.isActive():
                self.optimizer_app_instance.display_timer.stop()
                main_logger.debug("Stopped optimizer display timer (from main app close).")

            if hasattr(self.optimizer_app_instance, 'optimizer_running') and self.optimizer_app_instance.optimizer_running:
                reply = QMessageBox.question(self, 'Xác Nhận Thoát',
                                             "Quá trình tối ưu hóa đang chạy. Bạn có chắc chắn muốn thoát?\nQuá trình sẽ bị dừng.",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    main_logger.info("User confirmed exit while optimizer running. Stopping optimizer.")
                    try:
                        self.optimizer_app_instance.stop_optimization(force_stop=True)
                    except Exception as stop_err:
                        main_logger.error(f"Error stopping optimizer on close: {stop_err}")
                else:
                    main_logger.info("User cancelled exit due to running optimizer.")
                    optimizer_was_running_and_cancelled_exit = True
                    event.ignore()
                    return

        if optimizer_was_running_and_cancelled_exit:
            return

        main_logger.info("Accepting close event. Application will now quit.")
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


class UpdateCheckWorker(QObject):
    finished_signal = pyqtSignal()
    update_info_signal = pyqtSignal(str, str, bool)
    commit_history_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, main_app_ref):
        super().__init__()
        self.main_app = main_app_ref

    @pyqtSlot()
    def run_check(self):
        try:
            app = self.main_app
            app.update_logger.info("UpdateCheckWorker: Bắt đầu kiểm tra.")

            current_html = app._format_version_info_for_display(
                app.current_app_version_info, "Phiên bản đang sử dụng"
            )
            update_file_url = app.update_file_url_edit.text().strip()
            commit_history_url = "https://github.com/junlangzi/Lottery-Predictor/commits/main.atom"

            if not update_file_url:
                self.error_signal.emit("URL file cập nhật chưa được cấu hình.")
                self.finished_signal.emit()
                return

            online_content = app._fetch_online_content(update_file_url)
            if online_content is None:
                self.error_signal.emit(f"Không thể tải nội dung từ:\n{update_file_url}")
                self.finished_signal.emit()
                return

            app.online_app_content_cache = online_content
            app.online_app_version_info = app._extract_app_version_info(online_content)
            online_html = app._format_version_info_for_display(
                app.online_app_version_info, "Phiên bản mới (Online):"
            )
            update_available = app._compare_versions(
                app.current_app_version_info, app.online_app_version_info
            )
            self.update_info_signal.emit(current_html, online_html, update_available)

            app.update_logger.info(f"UpdateCheckWorker: Đang tải lịch sử commit từ {commit_history_url}")
            atom_feed_content = app._fetch_online_content(commit_history_url)
            if atom_feed_content:
                history_html_display = app._parse_github_atom_feed(atom_feed_content)
                self.commit_history_signal.emit(history_html_display)
            else:
                self.commit_history_signal.emit("<p>Không thể tải lịch sử commit.</p>")

            app.update_logger.info("UpdateCheckWorker: Kiểm tra hoàn tất.")
        except Exception as e:
            self.main_app.update_logger.error(f"Lỗi nghiêm trọng trong UpdateCheckWorker: {e}", exc_info=True)
            self.error_signal.emit(f"Lỗi không mong muốn trong quá trình kiểm tra: {e}")
        finally:
            self.finished_signal.emit()

class PerformUpdateWorker(QObject):
    finished_signal = pyqtSignal(bool, str)
    error_signal = pyqtSignal(str)

    def __init__(self, main_app_ref):
        super().__init__()
        self.main_app = main_app_ref

    @pyqtSlot()
    def run_update(self):
        try:
            app = self.main_app
            app.update_logger.info("PerformUpdateWorker: Bắt đầu quá trình cập nhật.")

            online_content = app.online_app_content_cache
            if not online_content:
                online_file_url_ui = app.update_file_url_edit.text().strip()
                if not online_file_url_ui:
                    self.error_signal.emit("URL file cập nhật không hợp lệ.")
                    self.finished_signal.emit(False, "Lỗi: URL file cập nhật không hợp lệ.")
                    return
                app.update_logger.info(f"Tải lại nội dung từ: {online_file_url_ui}")
                online_content = app._fetch_online_content(online_file_url_ui)
                if online_content is None:
                    self.error_signal.emit(f"Không thể tải lại nội dung file cập nhật từ:\n{online_file_url_ui}")
                    self.finished_signal.emit(False, f"Lỗi: Không thể tải lại nội dung file cập nhật.")
                    return

            target_filename_from_ui = app.update_save_filename_edit.text().strip()
            if not target_filename_from_ui:
                self.error_signal.emit("Tên file lưu cập nhật không được để trống.")
                self.finished_signal.emit(False, "Lỗi: Tên file lưu cập nhật không được để trống.")
                return
            if not target_filename_from_ui.lower().endswith((".py", ".pyw")):
                 app.update_logger.info(f"Tên file đích '{target_filename_from_ui}' không có đuôi .py hoặc .pyw chuẩn.")


            current_script_to_replace_path = None
            if getattr(sys, 'frozen', False):
                app_dir = Path(sys.executable).parent
                current_script_to_replace_path = app_dir / target_filename_from_ui
                app.update_logger.warning(f"Ứng dụng đóng gói. Sẽ cố gắng cập nhật file tại: {current_script_to_replace_path}")
            else:
                current_script_to_replace_path = Path(__file__).resolve().parent / target_filename_from_ui
            
            app.update_logger.info(f"Đường dẫn file đích để cập nhật: {current_script_to_replace_path}")

            backup_file_path = current_script_to_replace_path.with_name(current_script_to_replace_path.name + ".bank")
            made_backup = False

            if current_script_to_replace_path.exists():
                app.update_logger.info(f"File đích '{current_script_to_replace_path.name}' tồn tại. Sẽ tiến hành đổi tên thành '{backup_file_path.name}'.")
                if backup_file_path.exists():
                    try:
                        backup_file_path.unlink()
                        app.update_logger.info(f"Đã xóa file .bank cũ trước khi sao lưu: {backup_file_path.name}")
                    except OSError as e_del_old_bank:
                        app.update_logger.warning(f"Không thể xóa file .bank cũ '{backup_file_path.name}': {e_del_old_bank}. Tiếp tục...")
                
                try:
                    current_script_to_replace_path.rename(backup_file_path)
                    app.update_logger.info(f"Đã đổi tên '{current_script_to_replace_path.name}' thành '{backup_file_path.name}'")
                    made_backup = True
                except Exception as e_rename_backup:
                    app.update_logger.error(f"Không thể đổi tên file '{current_script_to_replace_path.name}' để tạo backup '.bank': {e_rename_backup}")
                    self.error_signal.emit(f"Lỗi tạo file sao lưu '.bank' cho '{current_script_to_replace_path.name}':\n{e_rename_backup}")
                    self.finished_signal.emit(False, f"Lỗi: Không thể tạo file sao lưu '.bank'.")
                    return
            else:
                app.update_logger.info(f"File đích '{current_script_to_replace_path.name}' không tồn tại. Sẽ tạo file mới.")

            try:
                if not isinstance(online_content, str):
                    app.update_logger.error(f"Nội dung tải về không phải là chuỗi, mà là: {type(online_content)}")
                    self.error_signal.emit("Lỗi: Nội dung tải về không hợp lệ (không phải dạng văn bản).")
                    self.finished_signal.emit(False, "Lỗi: Nội dung tải về không hợp lệ.")
                    if made_backup and backup_file_path.exists() and not current_script_to_replace_path.exists():
                        try: backup_file_path.rename(current_script_to_replace_path); app.update_logger.info(f"Khôi phục từ backup do nội dung tải về lỗi.")
                        except: pass
                    return

                normalized_newlines_content = online_content.replace('\r\n', '\n').replace('\r', '\n')
                final_content_to_write = normalized_newlines_content

                current_script_to_replace_path.write_text(final_content_to_write, encoding='utf-8')
                app.update_logger.info(f"Cập nhật thành công nội dung của {current_script_to_replace_path.name}")

                if made_backup and backup_file_path.exists():
                    try:
                        backup_file_path.unlink()
                        app.update_logger.info(f"Đã xóa file sao lưu '.bank': {backup_file_path.name}")
                    except OSError as e_delete_bank:
                        app.update_logger.warning(f"Không thể xóa file sao lưu '.bank' '{backup_file_path.name}' sau khi cập nhật thành công: {e_delete_bank}")
                
                self.finished_signal.emit(True, f"Đã cập nhật thành công file: {current_script_to_replace_path.name}\nVui lòng khởi động lại ứng dụng.")
            
            except IOError as e_io:
                app.update_logger.error(f"Lỗi IOError khi ghi nội dung cập nhật vào {current_script_to_replace_path.name}: {e_io}")
                if made_backup and backup_file_path.exists():
                    app.update_logger.info(f"Lỗi ghi file mới. Đang cố gắng khôi phục từ backup '{backup_file_path.name}'...")
                    try:
                        if current_script_to_replace_path.exists():
                            current_script_to_replace_path.unlink()
                        
                        backup_file_path.rename(current_script_to_replace_path)
                        app.update_logger.info(f"Đã khôi phục thành công file gốc từ '{backup_file_path.name}'.")
                    except Exception as e_restore:
                        app.update_logger.error(f"KHÔNG THỂ KHÔI PHỤC file gốc từ backup '{backup_file_path.name}': {e_restore}. Hệ thống có thể ở trạng thái không ổn định.")
                self.error_signal.emit(f"Lỗi khi ghi file cập nhật ({current_script_to_replace_path.name}):\n{e_io}")
                self.finished_signal.emit(False, f"Lỗi: Không thể ghi file cập nhật.")
            except Exception as e_write:
                app.update_logger.error(f"Lỗi không mong muốn khi ghi nội dung cập nhật vào {current_script_to_replace_path.name}: {e_write}")
                if made_backup and backup_file_path.exists():
                    try:
                        if current_script_to_replace_path.exists(): current_script_to_replace_path.unlink()
                        backup_file_path.rename(current_script_to_replace_path)
                        app.update_logger.info(f"Đã khôi phục từ backup do lỗi ghi không xác định.")
                    except: pass
                self.error_signal.emit(f"Lỗi không xác định khi ghi file cập nhật ({current_script_to_replace_path.name}):\n{e_write}")
                self.finished_signal.emit(False, f"Lỗi: Không xác định khi ghi file cập nhật.")
        except Exception as e:
            self.main_app.update_logger.error(f"Lỗi nghiêm trọng trong PerformUpdateWorker: {e}", exc_info=True)
            self.error_signal.emit(f"Lỗi không mong muốn trong quá trình cập nhật: {e}")
            self.finished_signal.emit(False, f"Lỗi: Không mong muốn trong quá trình cập nhật.")

def main():
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
        if HAS_PYQT5:
            QMessageBox.critical(
                None,
                "Lỗi Nghiêm Trọng",
                f"Đã xảy ra lỗi khởi tạo hoặc lỗi nghiêm trọng không thể phục hồi:\n\n{e}\n\n"
                f"Ứng dụng sẽ đóng.\nKiểm tra file log để biết chi tiết:\n'{log_file_path}'."
            )
        else:
            print(f"CRITICAL ERROR (main): {e}\nLog file: {log_file_path}")
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
