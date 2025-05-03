import os
import sys
import logging
import json
import traceback
import datetime
import shutil
import random
import copy
import threading
import queue
import time
import ast
import subprocess
import itertools
import math
from collections import Counter
from importlib import reload, util
from abc import ABC, abstractmethod
import re
import textwrap
from pathlib import Path
import configparser
import importlib.util
import inspect

try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFormLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QGroupBox,
        QComboBox, QSpinBox, QCheckBox, QScrollArea, QTextEdit, QProgressBar,
        QListWidget, QListWidgetItem, QDialog, QCalendarWidget, QMessageBox,
        QFileDialog, QStatusBar, QSplitter, QSizePolicy, QFrame, QRadioButton
    )
    from PyQt5.QtCore import Qt, QTimer, QDate, QObject, pyqtSignal, QThread, QSize, QRect
    from PyQt5.QtGui import (
        QFont, QPalette, QColor, QIcon, QIntValidator, QDoubleValidator,
        QTextCursor, QFontDatabase, QPixmap, QPainter, QBrush, QRegularExpressionValidator
    )
    HAS_PYQT5 = True
    print("PyQt5 library found for Training App.")
except ImportError as e:
    HAS_PYQT5 = False
    print(f"CRITICAL ERROR: PyQt5 library not found. Please install it: pip install PyQt5")
    print(f"Import Error: {e}")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Missing Library", "PyQt5 is required.\nInstall: pip install PyQt5")
        root.destroy()
    except ImportError: pass
    sys.exit(1)

try:
    if sys.version_info < (3, 9):
        import astor
        HAS_ASTOR = True
        print("Astor library found (for Python < 3.9 AST writing).")
    else:
        HAS_ASTOR = False
        print("Using built-in ast.unparse (Python >= 3.9).")
except ImportError:
    HAS_ASTOR = False
    if sys.version_info < (3, 9):
        print("WARNING: Astor library not found. Parameter modification might fail on Python < 3.9.")
    else:
        print("Astor not needed for Python >= 3.9.")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
for handler in logging.getLogger('').handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.setLevel(logging.INFO)

trainer_logger = logging.getLogger("TrainerApp")
worker_logger = logging.getLogger("TrainingWorker")
style_logger = logging.getLogger("TrainerStyle")
modifier_logger = logging.getLogger("ASTModifier")
import_logger = logging.getLogger("TempAlgoImporter")

try:
    script_dir_base = Path(__file__).parent.resolve()
    if str(script_dir_base) not in sys.path: sys.path.insert(0, str(script_dir_base))
    if 'algorithms.base' in sys.modules:
        try: reload(sys.modules['algorithms.base']); trainer_logger.debug("Reloaded algorithms.base.")
        except Exception: pass
    if 'algorithms' in sys.modules:
        try: reload(sys.modules['algorithms']); trainer_logger.debug("Reloaded algorithms package.")
        except Exception: pass
    from algorithms.base import BaseAlgorithm
    trainer_logger.info("Imported BaseAlgorithm successfully.")
except ImportError as e:
    print(f"Lỗi: Không thể import BaseAlgorithm: {e}", file=sys.stderr)
    trainer_logger.critical(f"Failed to import BaseAlgorithm: {e}", exc_info=True)
    class BaseAlgorithm(ABC):
        """Lớp cơ sở giả khi import thất bại."""
        def __init__(self, data_results_list=None, cache_dir=None):
            self.config = {"description": "BaseAlgorithm Giả", "parameters": {}}
            self._raw_results_list = copy.deepcopy(data_results_list) if data_results_list else []
            self.cache_dir = cache_dir
            self.logger = logging.getLogger(f"DummyBase_{id(self)}")
            self._log('warning', f"Using Dummy BaseAlgorithm! Instance: {id(self)}")
        def get_config(self) -> dict: return copy.deepcopy(self.config)
        @abstractmethod
        def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict: return {}
        def get_results_in_range(self, start_date: datetime.date, end_date: datetime.date) -> list: return []
        def extract_numbers_from_dict(self, result_dict: dict) -> set: return set()
        def _log(self, level: str, message: str): getattr(self.logger, level.lower(), self.logger.warning)(f"[{self.__class__.__name__}] {message}")
    print("Cảnh báo: Sử dụng lớp BaseAlgorithm giả.", file=sys.stderr)
    trainer_logger.warning("Using dummy BaseAlgorithm class due to import failure.")
except Exception as base_import_err:
    print(f"Lỗi không xác định khi import BaseAlgorithm: {base_import_err}", file=sys.stderr)
    trainer_logger.critical(f"Unknown error importing BaseAlgorithm: {base_import_err}", exc_info=True)
    sys.exit(1)


COLOR_PRIMARY='#007BFF'
COLOR_PRIMARY_DARK='#0056b3'
COLOR_SECONDARY='#6c757d'
COLOR_SUCCESS='#28a745'
COLOR_SUCCESS_DARK='#1e7e34'
COLOR_WARNING='#ffc107'
COLOR_DANGER='#dc3545'
COLOR_INFO='#17a2b8'
COLOR_TEXT_DARK='#212529'
COLOR_TEXT_LIGHT='#FFFFFF'
COLOR_BG_LIGHT='#FFFFFF'
COLOR_BG_WHITE='#FFFFFF'
COLOR_BG_LIGHT_ALT='#FAFAFA'
COLOR_BG_HIT='#d4edda'
COLOR_BG_SPECIAL='#fff3cd'
COLOR_ACCENT_PURPLE='#6f42c1'
COLOR_TOOLTIP_BG='#FFFFE0'
COLOR_DISABLED_BG='#e9ecef'
COLOR_DISABLED_FG='#6c757d'
COLOR_BORDER='#ced4da'
COLOR_TAB_FG=COLOR_SUCCESS_DARK
COLOR_TAB_SELECTED_FG=COLOR_PRIMARY_DARK
COLOR_TAB_BG=COLOR_BG_LIGHT
COLOR_TAB_SELECTED_BG=COLOR_BG_WHITE
COLOR_TAB_INACTIVE_BG='#E9E9E9'
PB_TROUGH=COLOR_DISABLED_BG
COLOR_CARD_BG='#F8F9FA'
COLOR_TRAIN_PROGRESS=COLOR_ACCENT_PURPLE
MAIN_BG = COLOR_BG_WHITE


class TrainingApp(QMainWindow):
    log_signal = pyqtSignal(str, str, str)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, float, int, int)
    best_update_signal = pyqtSignal(dict, int)
    finished_signal = pyqtSignal(str, bool, str)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lottery Algorithm Optimizer (v1.5.0)")
        trainer_logger.info("Initializing TrainingApp...")

        self.base_dir = Path(__file__).parent.resolve()
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.base_dir / "config"
        self.algorithms_dir = self.base_dir / "algorithms"
        self.training_dir = self.base_dir / "training"
        self.calculate_dir = self.base_dir / "calculate"
        self.settings_file_path = self.config_dir / "training_settings.ini"
        self.icon_path = self.config_dir / "logo.png"

        self.config = configparser.ConfigParser(interpolation=None)
        self.loaded_algorithms = {}
        self.results_data = []

        self.selected_algorithm_for_train = None
        self.training_thread = None
        self.training_queue = queue.Queue()
        self.training_stop_event = threading.Event()
        self.training_pause_event = threading.Event()
        self.training_running = False
        self.training_paused = False
        self.current_best_params = None
        self.current_best_streak = 0
        self.current_training_target_dir = None
        self.current_combination_algos = []
        self.training_custom_steps = {}
        self.last_train_start_date_str = ""
        self.last_run_mode = "Explore"

        self.advanced_train_widgets = {}
        self.param_generation_widgets = {}
        self.combination_selection_checkboxes = {}

        self.can_resume_explore = False
        self.train_start_time = 0.0
        self.train_time_limit_sec = 0
        self.train_streak_limit = 0

        self.training_timer = QTimer(self)
        self.training_timer.timeout.connect(self._check_training_queue)
        self.training_timer_interval = 200

        self.display_timer = QTimer(self)
        self.display_timer.timeout.connect(self._update_training_timer_display)
        self.display_timer_interval = 1000

        self.int_validator = QIntValidator()
        self.double_validator = QDoubleValidator()
        self.custom_steps_validator = QRegularExpressionValidator(
            QtCore.QRegularExpression(r"^(?:[-+]?\d+(?:\.\d*)?(?:,\s*[-+]?\d+(?:\.\d*)?)*)?$")
        )
        self.dimension_validator = QIntValidator(1, 9999)

        self.font_family_base = 'Segoe UI'
        self.font_size_base = 10
        self.available_fonts = sorted(QFontDatabase().families())

        self.create_directories()
        self.load_config()
        self._setup_global_font()
        self.setup_main_ui_structure()
        self._setup_log_formats()
        self.apply_stylesheet()
        self._apply_window_size_from_config()
        self._set_window_icon()
        self.load_data()
        self.load_algorithms()
        self.update_status("Trình tối ưu chuỗi sẵn sàng.")
        self.show()
        trainer_logger.info("TrainingApp initialized successfully.")

    def _set_window_icon(self):
        """Sets the window icon."""
        if self.icon_path.exists():
            try:
                self.setWindowIcon(QIcon(str(self.icon_path)))
                trainer_logger.info(f"Window icon set from {self.icon_path}")
            except Exception as e:
                trainer_logger.error(f"Failed to set window icon: {e}")
        else:
            trainer_logger.warning(f"Window icon file not found: {self.icon_path}")

    def create_directories(self):
        """Creates necessary directories."""
        try:
            for directory in [self.data_dir, self.config_dir, self.calculate_dir, self.algorithms_dir, self.training_dir]:
                directory.mkdir(parents=True, exist_ok=True)
            for dir_path in [self.algorithms_dir, self.training_dir]:
                init_file = dir_path / "__init__.py"
                if not init_file.exists(): init_file.touch()
            sample_data_file = self.data_dir / "xsmb-2-digits.json"
            if not sample_data_file.exists():
                 trainer_logger.info(f"Sample data file not found: {sample_data_file}. App may need data.")
        except Exception as e:
             trainer_logger.error(f"Error creating directories: {e}", exc_info=True)

    def load_config(self):
        """Loads configuration from training_settings.ini."""
        trainer_logger.info(f"Loading training config from: {self.settings_file_path}")
        self.config = configparser.ConfigParser(interpolation=None)
        config_needs_saving = False
        try:
            if self.settings_file_path.exists():
                read_files = self.config.read(self.settings_file_path, encoding='utf-8')
                if not read_files:
                    trainer_logger.error(f"ConfigParser failed to read file: {self.settings_file_path}. Using defaults.")
                    self.set_default_config(); config_needs_saving = True
            else:
                trainer_logger.warning(f"Config file {self.settings_file_path} not found. Setting defaults.")
                self.set_default_config(); config_needs_saving = True

            if not self.config.has_section('DATA'):
                self.config.add_section('DATA')
                self.config.set('DATA', 'data_file', str(self.data_dir / "xsmb-2-digits.json")); config_needs_saving = True
            if not self.config.has_option('DATA', 'data_file'):
                 self.config.set('DATA', 'data_file', str(self.data_dir / "xsmb-2-digits.json")); config_needs_saving = True

            default_width, default_height = 1100, 900
            default_font_family = 'Segoe UI'; default_font_size = 10
            if not self.config.has_section('UI'):
                self.config.add_section('UI')
                self.config.set('UI', 'width', str(default_width)); self.config.set('UI', 'height', str(default_height))
                self.config.set('UI', 'font_family_base', default_font_family); self.config.set('UI', 'font_size_base', str(default_font_size))
                config_needs_saving = True
            try:
                self.loaded_width = self.config.getint('UI', 'width', fallback=default_width)
                self.loaded_height = self.config.getint('UI', 'height', fallback=default_height)
                if str(self.loaded_width) != self.config.get('UI', 'width', fallback=''): self.config.set('UI', 'width', str(self.loaded_width)); config_needs_saving = True
                if str(self.loaded_height) != self.config.get('UI', 'height', fallback=''): self.config.set('UI', 'height', str(self.loaded_height)); config_needs_saving = True
            except (ValueError, configparser.Error):
                 self.loaded_width = default_width; self.loaded_height = default_height
                 self.config.set('UI', 'width', str(default_width)); self.config.set('UI', 'height', str(default_height)); config_needs_saving = True
            try:
                loaded_font_family = self.config.get('UI', 'font_family_base', fallback=default_font_family)
                if loaded_font_family not in self.available_fonts:
                    self.font_family_base = default_font_family; self.config.set('UI', 'font_family_base', default_font_family); config_needs_saving = True
                else: self.font_family_base = loaded_font_family
                loaded_font_size = self.config.getint('UI', 'font_size_base', fallback=default_font_size)
                self.font_size_base = max(8, min(24, loaded_font_size))
                if str(self.font_size_base) != self.config.get('UI', 'font_size_base', fallback=''): self.config.set('UI', 'font_size_base', str(self.font_size_base)); config_needs_saving = True
            except (ValueError, configparser.Error):
                 self.font_family_base = default_font_family; self.font_size_base = default_font_size
                 self.config.set('UI', 'font_family_base', default_font_family); self.config.set('UI', 'font_size_base', str(default_font_size)); config_needs_saving = True

            if not self.config.has_section('TRAINING_LIMITS'):
                 self.config.add_section('TRAINING_LIMITS')
                 self.config.set('TRAINING_LIMITS', 'max_time_minutes', '60'); self.config.set('TRAINING_LIMITS', 'max_streak_days', '0'); config_needs_saving = True
            try:
                 self.default_time_limit_min = self.config.getint('TRAINING_LIMITS', 'max_time_minutes', fallback=60)
                 self.default_streak_limit_days = self.config.getint('TRAINING_LIMITS', 'max_streak_days', fallback=0)
                 if str(self.default_time_limit_min) != self.config.get('TRAINING_LIMITS', 'max_time_minutes', fallback=''): self.config.set('TRAINING_LIMITS', 'max_time_minutes', str(self.default_time_limit_min)); config_needs_saving = True
                 if str(self.default_streak_limit_days) != self.config.get('TRAINING_LIMITS', 'max_streak_days', fallback=''): self.config.set('TRAINING_LIMITS', 'max_streak_days', str(self.default_streak_limit_days)); config_needs_saving = True
            except (ValueError, configparser.Error):
                 self.default_time_limit_min = 60; self.default_streak_limit_days = 0
                 self.config.set('TRAINING_LIMITS', 'max_time_minutes', '60'); self.config.set('TRAINING_LIMITS', 'max_streak_days', '0'); config_needs_saving = True

            if config_needs_saving: self._save_config_file(self.settings_file_path)

        except Exception as e:
            trainer_logger.error(f"Error loading training config: {e}", exc_info=True)
            self.set_default_config(); self._save_config_file(self.settings_file_path)

    def set_default_config(self):
        """Sets the self.config object to default training values."""
        trainer_logger.info("Setting self.config object to default training values.")
        self.config = configparser.ConfigParser(interpolation=None)
        self.config['DATA'] = {'data_file': str(self.data_dir / "xsmb-2-digits.json")}
        self.config['UI'] = {'width': '1100', 'height': '800', 'font_family_base': 'Segoe UI', 'font_size_base': '10'}
        self.config['TRAINING_LIMITS'] = {'max_time_minutes': '60', 'max_streak_days': '0'}
        self.default_time_limit_min = 60
        self.default_streak_limit_days = 0

    def _save_config_file(self, config_path):
        """Internal helper to save the current self.config to a file."""
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as cf:
                self.config.write(cf)
            trainer_logger.info(f"Saved configuration to: {config_path}")
        except IOError as e:
            trainer_logger.error(f"Failed to write config file {config_path}: {e}")
            parent_widget = self if isinstance(self, QWidget) else None
            QMessageBox.critical(parent_widget, "Lỗi Lưu Config", f"Không thể ghi file:\n{config_path}\n{e}")

    def _setup_global_font(self):
        """Sets the default application font."""
        try:
            QApplication.setFont(self.get_qfont("base"))
            style_logger.info(f"Applied application font: {self.font_family_base} {self.font_size_base}pt")
        except Exception as e:
            style_logger.error(f"Failed to set global font: {e}")

    def get_qfont(self, font_type: str) -> QFont:
        """Helper to get QFont objects based on loaded theme."""
        base_family = self.font_family_base; base_size = self.font_size_base
        font = QFont(base_family, base_size)
        if font_type == "bold": font.setWeight(QFont.Bold)
        elif font_type == "title": font.setPointSize(base_size + 2); font.setWeight(QFont.Bold)
        elif font_type == "small": font.setPointSize(max(6, base_size - 2))
        elif font_type == "code": font.setFamily('Consolas'); font.setPointSize(base_size); font.setStyleHint(QFont.Monospace)
        elif font_type == "code_bold": font.setFamily('Consolas'); font.setPointSize(base_size); font.setWeight(QFont.Bold); font.setStyleHint(QFont.Monospace)
        elif font_type == "code_bold_underline": font.setFamily('Consolas'); font.setPointSize(base_size); font.setWeight(QFont.Bold); font.setUnderline(True); font.setStyleHint(QFont.Monospace)
        return font

    def apply_stylesheet(self):
        """Applies the application-wide stylesheet using defined COLOR constants."""
        style_logger.debug("Applying application stylesheet...")
        try:
            stylesheet = f"""
                QMainWindow {{
                    background-color: {MAIN_BG}; /* Consistent main background */
                }}
                QWidget {{ /* Default for most widgets unless overridden */
                    color: {COLOR_TEXT_DARK};
                    background-color: {MAIN_BG}; /* Explicit white background */
                    /* Font applied via QApplication.setFont */
                }}

                QLabel {{
                    background-color: transparent;
                }}

                QTabWidget::pane {{ /* The area where tab pages appear */
                    border: 1px solid {COLOR_BORDER};
                    border-top: none;
                    background: {MAIN_BG}; /* Make pane background consistent */
                }}
                 QWidget#SelectTabWidget, QWidget#RunTabWidget {{
                     background-color: {MAIN_BG}; /* Explicit white for tab content areas */
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
                    background: {MAIN_BG}; /* Match pane/tab background */
                    color: {COLOR_TAB_SELECTED_FG};
                    border-color: {COLOR_BORDER};
                    border-bottom-color: {MAIN_BG}; /* Make bottom blend with pane */
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
                    background-color: {MAIN_BG}; /* Consistent white background */
                }}
                 QGroupBox:disabled {{
                    border: 1px solid #D0D0D0;
                    background-color: {COLOR_DISABLED_BG};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px 0 5px;
                    margin-left: 10px;
                    color: {COLOR_PRIMARY_DARK};
                    background-color: {MAIN_BG}; /* Ensure title background matches */
                }}
                QGroupBox:disabled::title {{
                     color: {COLOR_DISABLED_FG};
                     background-color: {COLOR_DISABLED_BG};
                 }}

                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
                    background-color: {COLOR_BG_WHITE}; /* Fields usually have white bg */
                    border: 1px solid {COLOR_BORDER};
                    padding: 4px;
                    border-radius: 3px;
                    min-height: 22px;
                }}
                /* Radio button specific styling */
                QRadioButton {{
                     border: none;
                     background-color: transparent; /* Inherit background */
                     padding: 2px;
                }}
                 QRadioButton::indicator {{
                     width: 13px;
                     height: 13px;
                 }}
                QLineEdit:read-only {{
                     background-color: {COLOR_DISABLED_BG};
                }}
                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
                QComboBox:disabled, QTextEdit:disabled, QTextEdit:read-only,
                QRadioButton:disabled {{
                    background-color: {COLOR_DISABLED_BG};
                    color: {COLOR_DISABLED_FG};
                    border: 1px solid #D0D0D0;
                }}
                /* Ensure disabled radio button text is greyed out */
                 QRadioButton:disabled {{
                     color: {COLOR_DISABLED_FG};
                     background-color: transparent;
                 }}
                 QComboBox::drop-down {{ border: none; }}

                QPushButton {{
                    background-color: #EFEFEF;
                    color: {COLOR_TEXT_DARK};
                    border: 1px solid #B0B0B0;
                    padding: 6px 12px;
                    border-radius: 3px;
                    min-width: 70px;
                    min-height: 23px;
                }}
                QPushButton:hover {{ background-color: #E0E0E0; border-color: #A0A0A0; }}
                QPushButton:pressed {{ background-color: #D0D0D0; }}
                QPushButton:disabled {{ background-color: {COLOR_DISABLED_BG}; color: {COLOR_DISABLED_FG}; border-color: #D0D0D0; }}

                /* Button Object Names */
                QPushButton#AccentButton {{ background-color: {COLOR_PRIMARY}; color: {COLOR_TEXT_LIGHT}; border-color: {COLOR_PRIMARY_DARK}; font-weight: bold; }}
                QPushButton#AccentButton:hover {{ background-color: {COLOR_PRIMARY_DARK}; }}
                QPushButton#WarningButton {{ background-color: {COLOR_WARNING}; color: {COLOR_TEXT_DARK}; border-color: #E0A800; font-weight: bold; }}
                QPushButton#WarningButton:hover {{ background-color: #ffad33; }}
                QPushButton#DangerButton {{ background-color: {COLOR_DANGER}; color: {COLOR_TEXT_LIGHT}; border-color: #b21f2d; font-weight: bold; }}
                QPushButton#DangerButton:hover {{ background-color: #c82333; }}
                QPushButton#ListAccentButton {{ background-color: {COLOR_PRIMARY_DARK}; color: {COLOR_TEXT_LIGHT}; border-color: #004085; padding: 4px 8px; font-weight: bold; min-width: 50px; }}
                QPushButton#ListAccentButton:hover {{ background-color: #004085; }}
                QPushButton#CalendarButton {{ padding: 2px 3px; min-width: 24px; max-width: 24px; min-height: 22px; max-height: 22px; font-size: {self.get_qfont('base').pointSize() + 2}pt; background-color: #F5F5F5; border: 1px solid #C0C0C0; border-radius: 3px; color: {COLOR_TEXT_DARK}; }}
                QPushButton#CalendarButton:hover {{ background-color: #E8E8E8; }}

                /* Progress Bars */
                QProgressBar {{ border: 1px solid {COLOR_BORDER}; border-radius: 3px; text-align: center; background-color: {PB_TROUGH}; min-height: 18px; }}
                 QProgressBar::chunk {{ border-radius: 2px; background-color: {COLOR_TRAIN_PROGRESS}; margin: 1px; }}

                /* Scroll Area */
                QScrollArea {{
                    border: 1px solid {COLOR_BORDER};
                    background-color: {MAIN_BG}; /* Match main background */
                }}
                 QScrollArea > QWidget {{ /* Viewport */
                     background-color: {MAIN_BG};
                 }}
                 QScrollArea > QWidget > QWidget {{ /* Target scrollAreaWidgetContents */
                     background-color: {MAIN_BG}; /* Match main background */
                 }}
                 /* Specific scroll widgets */
                 QWidget#AlgoScrollWidget, QWidget#ComboScrollWidget, QWidget#AdvancedParamsScrollWidget {{
                     background-color: {MAIN_BG};
                 }}

                 /* Frames used as cards */
                 QFrame#CardFrame {{
                     background-color: {COLOR_CARD_BG}; /* Slightly off-white */
                     border: 1px solid #D8D8D8; /* Light border */
                     border-radius: 4px;
                     margin-bottom: 6px; /* Space between cards */
                 }}
                 QToolTip {{
                     background-color: {COLOR_TOOLTIP_BG};
                     color: {COLOR_TEXT_DARK};
                     border: 1px solid black;
                     padding: 2px;
                 }}

                /* Status Bar Label Styling */
                QLabel#StatusBarLabel {{
                    padding: 3px 5px;
                    background-color: transparent; /* Explicitly keep this one transparent */
                }}
                QLabel#StatusBarLabel[status="error"] {{ color: {COLOR_DANGER}; font-weight: bold; }}
                QLabel#StatusBarLabel[status="success"] {{ color: {COLOR_SUCCESS}; font-weight: bold; }}
                QLabel#StatusBarLabel[status="warning"] {{ color: {COLOR_WARNING}; font-weight: bold; }}
                QLabel#StatusBarLabel[status="info"] {{ color: {COLOR_SECONDARY}; }}
                QLabel#StatusBarLabel {{ color: {COLOR_SECONDARY}; }} /* Default */

                /* Training Log Text Edit Styling */
                QTextEdit#TrainingLogText {{
                    /* ---- MODIFIED HERE ---- */
                    background-color: transparent; /* Make log area background transparent */
                    color: {COLOR_TEXT_DARK};
                    border: 1px solid {COLOR_BORDER};
                    font-family: Consolas, monospace; /* Code font */
                    font-size: {self.get_qfont('code').pointSize()}pt;
                }}

                /* ---- ADDED HERE ---- */
                QWidget#LogButtonFrame {{
                    background-color: transparent; /* Ensure button container is transparent */
                }}
            """
            self.setStyleSheet(stylesheet)
            style_logger.info("Application stylesheet applied.")
        except Exception as e:
            style_logger.error(f"Error applying stylesheet: {e}", exc_info=True)

    def _apply_window_size_from_config(self):
        """Applies window size read from the self.config object."""
        try:
            width = self.loaded_width
            height = self.loaded_height
            self.resize(width, height)
            trainer_logger.info(f"Applied window size from config: {width}x{height}")
        except Exception as e:
            trainer_logger.error(f"Error applying window size: {e}")

    def setup_main_ui_structure(self):
        """Sets up the main window structure: TabWidget and StatusBar."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("MainTabWidget")

        self.tab_select = QWidget()
        self.tab_select.setObjectName("SelectTabWidget")
        self.tab_run = QWidget()
        self.tab_run.setObjectName("RunTabWidget")

        self.tab_widget.addTab(self.tab_select, " 🪟 Chọn Thuật Toán ")
        self.tab_widget.addTab(self.tab_run, " 🧠 Tối Ưu Chuỗi  ")

        main_layout.addWidget(self.tab_widget)

        self.tab_widget.setTabEnabled(1, False)

        self.setup_select_tab()
        self.setup_run_tab()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar_label = QLabel("Khởi tạo...")
        self.status_bar_label.setObjectName("StatusBarLabel")
        self.status_bar.addWidget(self.status_bar_label, 1)

    def setup_select_tab(self):
        """Sets up the Algorithm Selection tab UI."""
        layout = QVBoxLayout(self.tab_select); layout.setContentsMargins(10, 10, 10, 10); layout.setSpacing(10)
        data_groupbox = QGroupBox("Dữ Liệu"); data_layout = QGridLayout(data_groupbox); data_layout.setContentsMargins(10, 15, 10, 10); data_layout.setSpacing(10)
        data_layout.addWidget(QLabel("File data:"), 0, 0, Qt.AlignLeft | Qt.AlignTop); self.data_file_path_label = QLabel("..."); self.data_file_path_label.setWordWrap(True); self.data_file_path_label.setMinimumHeight(35); data_layout.addWidget(self.data_file_path_label, 0, 1)
        browse_button = QPushButton("📂..."); browse_button.clicked.connect(self.browse_data_file); browse_button.setFixedWidth(80); data_layout.addWidget(browse_button, 0, 2, Qt.AlignTop)
        reload_data_button = QPushButton("🔄 Data"); reload_data_button.clicked.connect(self.load_data); reload_data_button.setFixedWidth(100); data_layout.addWidget(reload_data_button, 0, 3, Qt.AlignTop)
        data_layout.addWidget(QLabel("Phạm vi:"), 1, 0, Qt.AlignLeft); self.data_range_label = QLabel("..."); data_layout.addWidget(self.data_range_label, 1, 1, 1, 3); data_layout.setColumnStretch(1, 1); layout.addWidget(data_groupbox)
        control_frame = QWidget(); control_layout = QHBoxLayout(control_frame); control_layout.setContentsMargins(0,0,0,0)
        reload_button = QPushButton("Tải lại Danh sách Thuật toán"); reload_button.clicked.connect(self.reload_algorithms); control_layout.addWidget(reload_button); control_layout.addStretch(1); layout.addWidget(control_frame)
        list_groupbox = QGroupBox("Danh sách thuật toán"); list_layout = QVBoxLayout(list_groupbox); list_layout.setContentsMargins(5, 10, 5, 5)
        self.algo_scroll_area = QScrollArea(); self.algo_scroll_area.setWidgetResizable(True);
        self.algo_scroll_widget = QWidget()
        self.algo_scroll_widget.setObjectName("AlgoScrollWidget")
        self.algo_scroll_area.setWidget(self.algo_scroll_widget)
        self.algo_list_layout = QVBoxLayout(self.algo_scroll_widget); self.algo_list_layout.setAlignment(Qt.AlignTop); self.algo_list_layout.setSpacing(8)
        self.initial_algo_label = QLabel("Đang tải thuật toán..."); self.initial_algo_label.setStyleSheet("font-style: italic; color: #6c757d;"); self.initial_algo_label.setAlignment(Qt.AlignCenter); self.algo_list_layout.addWidget(self.initial_algo_label)
        list_layout.addWidget(self.algo_scroll_area); layout.addWidget(list_groupbox, 1)

    def setup_run_tab(self):
        """Sets up the Optimization Run tab UI with a 2-column settings layout and Log at the Bottom."""
        tab_layout = QVBoxLayout(self.tab_run)
        tab_layout.setContentsMargins(10, 10, 10, 10); tab_layout.setSpacing(10)

        # --- Top Section: Settings (Takes stretch factor 2) ---
        settings_container_widget = QWidget()
        settings_h_layout = QHBoxLayout(settings_container_widget)
        settings_h_layout.setContentsMargins(0,0,0,0)
        settings_h_layout.setSpacing(10)
        tab_layout.addWidget(settings_container_widget, 2) # Settings area gets stretch 2

        # -- Column 1 (Left side of settings) --
        col1_widget = QWidget()
        col1_v_layout = QVBoxLayout(col1_widget)
        col1_v_layout.setContentsMargins(0,0,0,0)
        col1_v_layout.setSpacing(10)
        settings_h_layout.addWidget(col1_widget, 1) # Column 1 gets 1/3 of horizontal space

        info_frame = QWidget(); info_h_layout = QHBoxLayout(info_frame); info_h_layout.setContentsMargins(0,0,0,0)
        info_h_layout.addWidget(QLabel("Thuật toán tối ưu:"))
        self.train_algo_name_label = QLabel("...")
        self.train_algo_name_label.setStyleSheet(f"font-weight: bold; color: {COLOR_SUCCESS}; font-size: {self.get_qfont('title').pointSize()}pt;")
        info_h_layout.addWidget(self.train_algo_name_label); info_h_layout.addStretch(1)
        col1_v_layout.addWidget(info_frame)

        settings_groupbox = QGroupBox("⚙️Cài Đặt Tối Ưu")
        settings_layout = QGridLayout(settings_groupbox)
        settings_layout.setContentsMargins(10, 15, 10, 10)
        settings_layout.setVerticalSpacing(8); settings_layout.setHorizontalSpacing(10)
        settings_layout.addWidget(QLabel("📆Ngày bắt đầu:"), 0, 0)
        self.train_start_date_edit = QLineEdit(); self.train_start_date_edit.setReadOnly(True); self.train_start_date_edit.setAlignment(Qt.AlignCenter); self.train_start_date_edit.setMinimumWidth(130)
        settings_layout.addWidget(self.train_start_date_edit, 0, 1)
        self.train_start_date_button = QPushButton("📅"); self.train_start_date_button.setObjectName("CalendarButton"); self.train_start_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.train_start_date_edit))
        settings_layout.addWidget(self.train_start_date_button, 0, 2)
        settings_layout.addWidget(QLabel("⌛Giới hạn TG (phút):"), 1, 0)
        self.train_time_limit_spinbox = QSpinBox(); self.train_time_limit_spinbox.setRange(0, 9999); self.train_time_limit_spinbox.setValue(self.default_time_limit_min); self.train_time_limit_spinbox.setAlignment(Qt.AlignCenter); self.train_time_limit_spinbox.setFixedWidth(70); self.train_time_limit_spinbox.setToolTip("0 = không giới hạn.")
        settings_layout.addWidget(self.train_time_limit_spinbox, 1, 1, Qt.AlignLeft)
        settings_layout.addWidget(QLabel("👑Mục tiêu chuỗi:"), 2, 0)
        self.train_streak_limit_spinbox = QSpinBox(); self.train_streak_limit_spinbox.setRange(0, 999); self.train_streak_limit_spinbox.setValue(self.default_streak_limit_days); self.train_streak_limit_spinbox.setAlignment(Qt.AlignCenter); self.train_streak_limit_spinbox.setFixedWidth(70); self.train_streak_limit_spinbox.setToolTip("Dừng khi đạt chuỗi này. 0 = không giới hạn.")
        settings_layout.addWidget(self.train_streak_limit_spinbox, 2, 1, Qt.AlignLeft)
        settings_layout.setColumnStretch(3, 1)
        col1_v_layout.addWidget(settings_groupbox)

        self.combination_groupbox = QGroupBox("♻️Kết hợp với:")
        combo_outer_layout = QVBoxLayout(self.combination_groupbox); combo_outer_layout.setContentsMargins(5, 10, 5, 5)
        combo_scroll_area = QScrollArea(); combo_scroll_area.setWidgetResizable(True);
        combo_scroll_area.setFixedHeight(120)
        self.combination_scroll_widget = QWidget()
        self.combination_scroll_widget.setObjectName("ComboScrollWidget")
        combo_scroll_area.setWidget(self.combination_scroll_widget)
        self.combination_layout = QVBoxLayout(self.combination_scroll_widget); self.combination_layout.setAlignment(Qt.AlignTop); self.combination_layout.setSpacing(4)
        self.initial_combo_label = QLabel("Chọn..."); self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.combination_layout.addWidget(self.initial_combo_label)
        combo_outer_layout.addWidget(combo_scroll_area)
        col1_v_layout.addWidget(self.combination_groupbox)

        col1_v_layout.addStretch(1) # Add stretch at the end of Col 1

        # -- Column 2 (Right side of settings) --
        col2_container_widget = QWidget()
        col2_v_layout = QVBoxLayout(col2_container_widget)
        col2_v_layout.setContentsMargins(0,0,0,0)
        col2_v_layout.setSpacing(10)
        settings_h_layout.addWidget(col2_container_widget, 2) # Column 2 gets 2/3 of horizontal space

        self.param_gen_groupbox = QGroupBox("🎰Tạo Bộ Tham Số Tối Ưu")
        param_gen_layout = QGridLayout(self.param_gen_groupbox)
        param_gen_layout.setContentsMargins(10, 15, 10, 10)
        param_gen_layout.setVerticalSpacing(8); param_gen_layout.setHorizontalSpacing(10)
        self.param_gen_enable_checkbox = QCheckBox("Kích hoạt chế độ tạo bộ tham số")
        self.param_gen_enable_checkbox.stateChanged.connect(self._toggle_param_generation_mode)
        param_gen_layout.addWidget(self.param_gen_enable_checkbox, 0, 0, 1, 4)
        param_gen_layout.addWidget(QLabel("Số giá trị/tham số (N):"), 1, 0)
        self.param_gen_count_spinbox = QSpinBox()
        self.param_gen_count_spinbox.setRange(2, 100); self.param_gen_count_spinbox.setValue(10)
        self.param_gen_count_spinbox.setFixedWidth(70); self.param_gen_count_spinbox.setEnabled(False)
        param_gen_layout.addWidget(self.param_gen_count_spinbox, 1, 1)
        param_gen_layout.addWidget(QLabel("Loại giá trị:"), 2, 0)
        self.param_gen_mode_random_radio = QRadioButton("Random")
        self.param_gen_mode_seq_radio = QRadioButton("Sequential (Liền kề)")
        self.param_gen_mode_random_radio.setChecked(True); self.param_gen_mode_random_radio.setEnabled(False)
        self.param_gen_mode_seq_radio.setEnabled(False)
        gen_mode_layout = QHBoxLayout(); gen_mode_layout.setContentsMargins(0,0,0,0)
        gen_mode_layout.addWidget(self.param_gen_mode_random_radio)
        gen_mode_layout.addWidget(self.param_gen_mode_seq_radio)
        gen_mode_layout.addStretch()
        param_gen_layout.addLayout(gen_mode_layout, 2, 1, 1, 3)
        col2_v_layout.addWidget(self.param_gen_groupbox)

        self.param_generation_widgets = {
            'enable': self.param_gen_enable_checkbox, 'count': self.param_gen_count_spinbox,
            'mode_random': self.param_gen_mode_random_radio, 'mode_seq': self.param_gen_mode_seq_radio,
        }

        self.advanced_train_groupbox = QGroupBox("👈Chỉnh Tham Số Thủ Công")
        self.advanced_train_groupbox.setCheckable(False)
        adv_outer_layout = QVBoxLayout(self.advanced_train_groupbox)
        adv_outer_layout.setContentsMargins(5, 10, 5, 5)
        adv_scroll_area = QScrollArea(); adv_scroll_area.setWidgetResizable(True)
        self.advanced_train_params_widget = QWidget()
        self.advanced_train_params_widget.setObjectName("AdvancedParamsScrollWidget")
        adv_scroll_area.setWidget(self.advanced_train_params_widget)
        self.advanced_train_params_layout = QVBoxLayout(self.advanced_train_params_widget)
        self.advanced_train_params_layout.setAlignment(Qt.AlignTop)
        self.initial_adv_label = QLabel("✅Chọn thuật toán...")
        self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.advanced_train_params_layout.addWidget(self.initial_adv_label)
        adv_outer_layout.addWidget(adv_scroll_area)
        col2_v_layout.addWidget(self.advanced_train_groupbox, 1) # Advanced params take remaining vertical space in Col 2

        # --- Middle Section: Controls and Progress (Takes stretch factor 0 - minimum space) ---
        middle_controls_frame = QWidget()
        middle_controls_layout = QVBoxLayout(middle_controls_frame)
        middle_controls_layout.setContentsMargins(0, 10, 0, 5); middle_controls_layout.setSpacing(8)
        tab_layout.addWidget(middle_controls_frame) # Middle controls get stretch 0 (auto-size)

        control_frame = QWidget(); control_layout = QHBoxLayout(control_frame); control_layout.setContentsMargins(0,0,0,0); control_layout.setSpacing(6)
        self.train_start_button = QPushButton("⏯Bắt đầu Tối ưu"); self.train_start_button.setObjectName("AccentButton")
        self.train_start_button.clicked.connect(lambda: self.start_optimization())
        control_layout.addWidget(self.train_start_button)
        self.train_resume_button = QPushButton("⏩Tiếp tục (Explore)"); self.train_resume_button.setObjectName("AccentButton")
        self.train_resume_button.clicked.connect(self.resume_exploration_session)
        self.train_resume_button.setEnabled(False)
        control_layout.addWidget(self.train_resume_button)
        self.train_pause_button = QPushButton("⏸Tạm dừng"); self.train_pause_button.setObjectName("WarningButton"); self.train_pause_button.setEnabled(False)
        control_layout.addWidget(self.train_pause_button)
        self.train_stop_button = QPushButton("⏹Dừng Hẳn"); self.train_stop_button.setObjectName("DangerButton"); self.train_stop_button.clicked.connect(self.stop_optimization)
        self.train_stop_button.setEnabled(False)
        control_layout.addWidget(self.train_stop_button)
        control_layout.addStretch(1)
        middle_controls_layout.addWidget(control_frame)

        progress_frame = QWidget(); progress_layout = QGridLayout(progress_frame); progress_layout.setContentsMargins(0, 5, 0, 5); progress_layout.setVerticalSpacing(2); progress_layout.setHorizontalSpacing(8)
        self.train_progressbar = QProgressBar(); self.train_progressbar.setTextVisible(False); self.train_progressbar.setFixedHeight(22); self.train_progressbar.setRange(0, 100)
        progress_layout.addWidget(self.train_progressbar, 0, 0, 1, 5)
        self.train_status_label = QLabel("⚠️Trạng thái: Chờ"); self.train_status_label.setStyleSheet("color: #6c757d;"); self.train_status_label.setWordWrap(True)
        progress_layout.addWidget(self.train_status_label, 1, 0)
        self.train_streak_label = QLabel("🔓Chuỗi: 0 / Best: 0"); self.train_streak_label.setStyleSheet("font-weight: bold;"); self.train_streak_label.setMinimumWidth(100)
        progress_layout.addWidget(self.train_streak_label, 1, 1)
        self.train_progress_label = QLabel("0%"); self.train_progress_label.setMinimumWidth(40); self.train_progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_layout.addWidget(self.train_progress_label, 1, 2)
        self.train_time_static_label = QLabel("🕧 còn lại:"); self.train_time_static_label.setStyleSheet("color: #6c757d;"); self.train_time_static_label.setVisible(False)
        progress_layout.addWidget(self.train_time_static_label, 1, 3, Qt.AlignRight)
        self.train_time_remaining_label = QLabel("--:--:--"); self.train_time_remaining_label.setStyleSheet("font-weight: bold;"); self.train_time_remaining_label.setMinimumWidth(70); self.train_time_remaining_label.setVisible(False)
        progress_layout.addWidget(self.train_time_remaining_label, 1, 4, Qt.AlignLeft)
        progress_layout.setColumnStretch(0, 1); progress_layout.setColumnStretch(1, 0); progress_layout.setColumnStretch(2, 0); progress_layout.setColumnStretch(3, 0); progress_layout.setColumnStretch(4, 0)
        middle_controls_layout.addWidget(progress_frame)

        # --- Bottom Section: Log (Takes stretch factor 3) ---
        log_groupbox = QGroupBox("📄Nhật Ký Tối Ưu")
        log_outer_layout = QVBoxLayout(log_groupbox)
        log_outer_layout.setContentsMargins(5, 10, 5, 5); log_outer_layout.setSpacing(6)
        self.train_log_text = QTextEdit(); self.train_log_text.setObjectName("TrainingLogText"); self.train_log_text.setReadOnly(True)
        log_outer_layout.addWidget(self.train_log_text, 1) # Log text expands vertically within groupbox

        log_button_frame = QWidget()
        # ---- Set Object Name for Styling ----
        log_button_frame.setObjectName("LogButtonFrame")
        # -------------------------------------
        log_button_layout = QHBoxLayout(log_button_frame)
        log_button_layout.setContentsMargins(0, 0, 0, 0)
        # ---- Corrected Layout Order ----
        open_folder_button = QPushButton("📂Mở Thư Mục Tối ưu"); open_folder_button.clicked.connect(self.open_training_folder)
        log_button_layout.addWidget(open_folder_button) # Add button first
        log_button_layout.addStretch(1)                 # Add stretch AFTER button to push it right
        # --------------------------------
        log_outer_layout.addWidget(log_button_frame) # Add the frame containing the button layout

        # ---- Increased Stretch Factor for Log Group ----
        tab_layout.addWidget(log_groupbox, 3) # Log area gets stretch 3 (larger)

    def _setup_log_formats(self):
        """Sets up QTextCharFormat objects for styling the log display."""
        trainer_logger.debug("Setting up log formats...")
        self.log_formats = {}
        try:
            base_font = self.get_qfont("code")
            bold_font = self.get_qfont("code_bold")
            bold_underline_font = self.get_qfont("code_bold_underline")
        except Exception as font_err:
             trainer_logger.error(f"Error getting fonts for log formats: {font_err}. Using default QFont.")
             base_font = QFont()
             bold_font = QFont(); bold_font.setWeight(QFont.Bold)
             bold_underline_font = QFont(); bold_underline_font.setWeight(QFont.Bold); bold_underline_font.setUnderline(True)

        def create_format(font, color_hex):
             fmt = QtGui.QTextCharFormat()
             fmt.setFont(font)
             try:
                 fmt.setForeground(QColor(color_hex))
             except Exception as color_err:
                 trainer_logger.error(f"Error setting color '{color_hex}' for log format: {color_err}")
                 fmt.setForeground(QColor(COLOR_TEXT_DARK))
             return fmt

        self.log_formats["INFO"] = create_format(base_font, COLOR_TEXT_DARK)
        self.log_formats["DEBUG"] = create_format(base_font, COLOR_SECONDARY)
        self.log_formats["WARNING"] = create_format(base_font, COLOR_WARNING)
        self.log_formats["ERROR"] = create_format(bold_font, COLOR_DANGER)
        self.log_formats["CRITICAL"] = create_format(bold_underline_font, COLOR_DANGER)
        self.log_formats["BEST"] = create_format(bold_font, COLOR_SUCCESS)
        self.log_formats["PROGRESS"] = create_format(base_font, COLOR_INFO)
        self.log_formats["PARAM_STEP"] = create_format(base_font, COLOR_ACCENT_PURPLE)
        self.log_formats["PARAM_SET"] = create_format(base_font, '#fd7e14')
        self.log_formats["RESUME"] = create_format(bold_font, COLOR_INFO)
        self.log_formats["COMBINE"] = create_format(base_font, COLOR_PRIMARY)
        self.log_formats["HIT"] = create_format(base_font, COLOR_SUCCESS)
        self.log_formats["MISS"] = create_format(base_font, COLOR_DANGER)
        self.log_formats["GENERATE"] = create_format(base_font, COLOR_INFO)

        trainer_logger.info("Log formats created.")

    def browse_data_file(self):
        trainer_logger.debug("Browsing for training data file...")
        initial_dir = str(self.data_dir); current_path_str = ""
        if hasattr(self, 'data_file_path_label'): current_path_str = self.data_file_path_label.text()
        if current_path_str and current_path_str != "..." and Path(current_path_str).is_file():
            parent_dir = Path(current_path_str).parent;
            if parent_dir.is_dir(): initial_dir = str(parent_dir)
        filename, _ = QFileDialog.getOpenFileName(self, "Chọn file JSON", initial_dir, "JSON files (*.json);;All files (*.*)")
        if filename:
            new_path = Path(filename)
            if hasattr(self, 'data_file_path_label'):
                fm = self.data_file_path_label.fontMetrics()
                elided_text = fm.elidedText(str(new_path), Qt.ElideMiddle, self.data_file_path_label.width() - 5)
                self.data_file_path_label.setText(elided_text)
                self.data_file_path_label.setToolTip(str(new_path))
            trainer_logger.info(f"Data file selected: {new_path}")
            self.config.set('DATA', 'data_file', str(new_path))
            self._save_config_file(self.settings_file_path)
            self.load_data()

    def load_data(self):
        trainer_logger.info("Loading lottery data for optimization..."); self.results_data = []
        data_file_str = self.config.get('DATA', 'data_file', fallback="")
        config_changed = False
        if not data_file_str:
            data_file_str = str(self.data_dir / "xsmb-2-digits.json")
            self.config.set('DATA', 'data_file', data_file_str)
            config_changed = True
            trainer_logger.warning(f"Data file path empty in config, set to default: {data_file_str}")

        data_file_path = Path(data_file_str)
        if hasattr(self, 'data_file_path_label'):
            fm = self.data_file_path_label.fontMetrics()
            label_width = self.data_file_path_label.width() if self.data_file_path_label.width() > 20 else 400
            elided_text = fm.elidedText(str(data_file_path), Qt.ElideMiddle, label_width - 10)
            self.data_file_path_label.setText(elided_text)
            self.data_file_path_label.setToolTip(str(data_file_path))
        else:
             trainer_logger.warning("data_file_path_label not found during data load.")

        if config_changed:
            self._save_config_file(self.settings_file_path)

        if not data_file_path.exists():
            trainer_logger.error(f"Data file not found: {data_file_path}")
            QMessageBox.critical(self, "Lỗi", f"File dữ liệu không tồn tại:\n{data_file_path}")
            if hasattr(self, 'data_range_label'): self.data_range_label.setText("Lỗi file")
            return

        try:
            with open(data_file_path, 'r', encoding='utf-8') as f: raw_data = json.load(f)
            processed_results = []; unique_dates = set(); data_list_to_process = []
            if isinstance(raw_data, list): data_list_to_process = raw_data
            elif isinstance(raw_data, dict):
                results_val = raw_data.get('results')
                if isinstance(results_val, dict):
                    for date_str, result_dict in results_val.items():
                        if isinstance(result_dict, dict): result_dict_with_date = result_dict.copy(); result_dict_with_date['date'] = date_str; data_list_to_process.append(result_dict_with_date)
                elif isinstance(results_val, list): data_list_to_process = results_val
                else:
                     for date_str, result_dict in raw_data.items():
                         if isinstance(result_dict, dict):
                             try: datetime.datetime.strptime(date_str, '%Y-%m-%d'); result_dict_with_date = result_dict.copy(); result_dict_with_date['date'] = date_str; data_list_to_process.append(result_dict_with_date)
                             except ValueError: trainer_logger.warning(f"Skipping dict item with non-date key: {date_str}")
            else: raise ValueError("Định dạng JSON không được hỗ trợ hoặc không hợp lệ.")
            for item in data_list_to_process:
                if not isinstance(item, dict): continue
                date_str_raw = item.get("date")
                if not date_str_raw: continue
                try: date_obj = datetime.datetime.strptime(str(date_str_raw).split('T')[0], '%Y-%m-%d').date()
                except ValueError: trainer_logger.warning(f"Skipping invalid date format: {date_str_raw}"); continue
                if date_obj in unique_dates: trainer_logger.warning(f"Skipping duplicate date: {date_obj}"); continue
                result_dict = item.get('result', {k: v for k, v in item.items() if k != 'date'})
                if not result_dict or not isinstance(result_dict, dict): trainer_logger.warning(f"Skipping entry with missing/invalid result for date {date_obj}"); continue
                processed_results.append({'date': date_obj, 'result': result_dict}); unique_dates.add(date_obj)

            if processed_results:
                processed_results.sort(key=lambda x: x['date'])
                self.results_data = processed_results
                start_date, end_date = self.results_data[0]['date'], self.results_data[-1]['date']
                date_range_str = f"{start_date:%d/%m/%Y} - {end_date:%d/%m/%Y} ({len(self.results_data)} ngày)"
                if hasattr(self, 'data_range_label'): self.data_range_label.setText(date_range_str)
                self.update_status(f"Đã tải {len(self.results_data)} kết quả")
                if hasattr(self, 'train_start_date_edit') and not self.train_start_date_edit.text():
                    if len(self.results_data) >= 2: self.train_start_date_edit.setText(start_date.strftime('%d/%m/%Y'))
                    else: trainer_logger.warning("Not enough data points (< 2) to set default start date.")
            else:
                 if hasattr(self, 'data_range_label'): self.data_range_label.setText("Không có dữ liệu hợp lệ")
                 self.update_status("Không tải được dữ liệu hợp lệ.")

        except (json.JSONDecodeError, ValueError) as e:
            trainer_logger.error(f"Invalid JSON/Data format in {data_file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi Dữ Liệu", f"File '{data_file_path.name}' có định dạng không hợp lệ hoặc lỗi:\n{e}")
            if hasattr(self, 'data_range_label'): self.data_range_label.setText("Lỗi định dạng file")
        except Exception as e:
            trainer_logger.error(f"Unexpected error loading data: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi", f"Lỗi không mong muốn khi tải dữ liệu:\n{e}")
            if hasattr(self, 'data_range_label'): self.data_range_label.setText("Lỗi tải dữ liệu")

    def load_algorithms(self):
        """Loads algorithms for the Select tab."""
        trainer_logger.info("Trainer: Loading algorithms...")
        if hasattr(self, 'algo_list_layout'):
             layout_to_clear = self.algo_list_layout
             while layout_to_clear.count():
                 child = layout_to_clear.takeAt(0)
                 if child.widget(): child.widget().deleteLater()
        else: trainer_logger.error("Cannot clear algorithms: algo_list_layout not found."); return

        if not hasattr(self, 'initial_algo_label') or not self.initial_algo_label:
             self.initial_algo_label = QLabel("Đang tải...")
             self.initial_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
             self.initial_algo_label.setAlignment(Qt.AlignCenter)
             if hasattr(self, 'algo_list_layout'): self.algo_list_layout.addWidget(self.initial_algo_label)
             else: trainer_logger.error("Cannot add loading label: algo_list_layout not found.")
        else: self.initial_algo_label.setText("Đang tải..."); self.initial_algo_label.show()

        self.loaded_algorithms.clear()
        self.disable_run_tab()
        self.update_status("Trainer: Đang tải thuật toán...")

        if not self.algorithms_dir.is_dir():
            QMessageBox.critical(self, "Lỗi", f"Thư mục thuật toán không tồn tại:\n{self.algorithms_dir}")
            if self.initial_algo_label: self.initial_algo_label.setText("Lỗi: Thư mục thuật toán không tồn tại.")
            return

        algo_files = [f for f in self.algorithms_dir.glob('*.py') if f.is_file() and f.name not in ["__init__.py", "base.py"]]
        count_success, count_fail = 0, 0
        data_copy = copy.deepcopy(self.results_data) if self.results_data else []
        cache_dir = self.calculate_dir
        loaded_widgets = False

        for f_path in algo_files:
            module_name = f"algorithms.{f_path.stem}"
            instance = None; config = None; class_name = None; module_obj = None
            display_name = f"{f_path.stem} ({f_path.name})"
            try:
                if module_name in sys.modules:
                    try:
                        trainer_logger.debug(f"Reloading module: {module_name}")
                        if 'algorithms' in sys.modules:
                            try: reload(sys.modules['algorithms'])
                            except Exception as pkg_reload_err: trainer_logger.warning(f"Could not reload algorithms package: {pkg_reload_err}")
                        module_obj = reload(sys.modules[module_name])
                    except Exception as reload_err:
                        trainer_logger.warning(f"Failed to reload {module_name}, removing from sys.modules: {reload_err}")
                        try: del sys.modules[module_name]
                        except KeyError: pass
                        module_obj = None
                if module_obj is None:
                    trainer_logger.debug(f"Loading module from file: {f_path}")
                    spec = util.spec_from_file_location(module_name, f_path)
                    if spec and spec.loader:
                        module_obj = util.module_from_spec(spec)
                        if module_obj: sys.modules[module_name] = module_obj; spec.loader.exec_module(module_obj); trainer_logger.debug(f"Successfully loaded and executed {module_name}")
                        else: raise ImportError(f"util.module_from_spec returned None for {module_name}")
                    else: raise ImportError(f"Could not create spec or loader for {f_path}")
                if not module_obj: raise ImportError(f"Module object for {module_name} is None after loading attempt.")
                found_class = None
                for name, obj in inspect.getmembers(module_obj):
                    if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == module_name:
                        found_class = obj; class_name = name; display_name = f"{class_name} ({f_path.name})"; trainer_logger.debug(f"Found matching class '{class_name}' in {f_path.name}"); break
                if found_class:
                    try:
                        trainer_logger.debug(f"Instantiating {class_name}...")
                        instance = found_class(data_results_list=data_copy, cache_dir=cache_dir)
                        trainer_logger.debug(f"Getting config for {class_name} instance...")
                        config = instance.get_config()
                        if not isinstance(config, dict): trainer_logger.warning(f"Algorithm {class_name} get_config() did not return a dict. Using default."); config = {"description": "Lỗi Config", "parameters":{}}
                        elif "description" not in config: config["description"] = "Không có mô tả"
                        elif "parameters" not in config or not isinstance(config["parameters"], dict): config["parameters"] = {}
                        trainer_logger.debug(f"Storing algorithm {display_name}")
                        self.loaded_algorithms[display_name] = {'instance': instance, 'path': f_path, 'config': config, 'class_name': class_name, 'module_name': module_name}
                        self.create_algorithm_ui_qt(display_name, config)
                        loaded_widgets = True; count_success += 1
                    except Exception as init_err:
                        trainer_logger.error(f"Failed to initialize or get config for {class_name} from {f_path.name}: {init_err}", exc_info=True); count_fail += 1
                        if display_name in self.loaded_algorithms: del self.loaded_algorithms[display_name]
                else: trainer_logger.warning(f"No valid BaseAlgorithm subclass found in {f_path.name}"); count_fail += 1
            except Exception as load_err:
                trainer_logger.error(f"Error processing algorithm file {f_path.name}: {load_err}", exc_info=True); count_fail += 1
                if module_name in sys.modules:
                    try: del sys.modules[module_name]
                    except KeyError: pass

        if loaded_widgets and self.initial_algo_label:
            self.algo_list_layout.removeWidget(self.initial_algo_label); self.initial_algo_label.deleteLater(); self.initial_algo_label = None
        elif not loaded_widgets and self.initial_algo_label: self.initial_algo_label.setText("Không tìm thấy thuật toán hợp lệ.")

        status_msg = f"Trainer: Tải {count_success} thuật toán"
        if count_fail > 0: status_msg += f" (lỗi: {count_fail})"
        self.update_status(status_msg)

        if count_fail > 0 and count_success > 0: QMessageBox.warning(self, "Lỗi Tải Thuật Toán", f"Đã xảy ra lỗi khi tải {count_fail} file thuật toán.\nKiểm tra console log.")
        elif count_fail > 0 and count_success == 0: QMessageBox.critical(self, "Lỗi Tải Thuật Toán", f"Không thể tải bất kỳ thuật toán nào ({count_fail} lỗi).\nKiểm tra console log.")

        self.check_resume_possibility()

    def create_algorithm_ui_qt(self, display_name, config):
        """Creates the UI card for an algorithm in the Select tab."""
        if self.initial_algo_label and self.algo_list_layout.count() == 1:
            self.algo_list_layout.removeWidget(self.initial_algo_label); self.initial_algo_label.deleteLater(); self.initial_algo_label = None

        frame = QFrame(); frame.setFrameShape(QFrame.StyledPanel); frame.setFrameShadow(QFrame.Raised); frame.setLineWidth(1); frame.setObjectName("CardFrame")
        layout = QHBoxLayout(frame); layout.setContentsMargins(10, 8, 10, 8)
        info_container = QWidget(); info_layout = QVBoxLayout(info_container); info_layout.setContentsMargins(0,0,0,0); info_layout.setSpacing(2)
        class_name = self.loaded_algorithms[display_name]['class_name']
        file_name = self.loaded_algorithms[display_name]['path'].name
        desc = config.get("description", "N/A")
        name_label = QLabel(f"{class_name} ({file_name})"); name_label.setFont(self.get_qfont("bold"))
        desc_label = QLabel(desc); desc_label.setWordWrap(True); desc_label.setFont(self.get_qfont("small")); desc_label.setStyleSheet("color: #5a5a5a;")
        info_layout.addWidget(name_label); info_layout.addWidget(desc_label)
        layout.addWidget(info_container, 1)
        button = QPushButton("Tối ưu chuỗi"); button.setObjectName("ListAccentButton")
        button.clicked.connect(lambda checked=False, name=display_name: self.trigger_select_for_optimization(name))
        layout.addWidget(button)
        self.algo_list_layout.addWidget(frame)
        if display_name in self.loaded_algorithms: self.loaded_algorithms[display_name]['ui_frame'] = frame

    def reload_algorithms(self):
        """Clears and reloads algorithms."""
        trainer_logger.info("Reloading algorithms...")
        self.selected_algorithm_for_train = None
        self.disable_run_tab()
        self._reset_advanced_train_settings()
        self._reset_param_generation_settings()
        self._clear_combination_selection()
        self.load_algorithms()
        self.check_resume_possibility()

    def disable_run_tab(self):
        """Disables the Run/Optimize tab and clears related fields."""
        if hasattr(self, 'tab_widget'): self.tab_widget.setTabEnabled(1, False)
        self._clear_advanced_train_fields()
        self._reset_param_generation_settings()
        self._clear_combination_selection()
        self.selected_algorithm_for_train = None
        if hasattr(self, 'train_algo_name_label'): self.train_algo_name_label.setText("...")
        self.can_resume_explore = False
        if hasattr(self, 'train_resume_button'): self.train_resume_button.setEnabled(False)

    def trigger_select_for_optimization(self, display_name):
        """Selects an algorithm and prepares the Optimization Run tab."""
        if display_name not in self.loaded_algorithms:
            QMessageBox.warning(self, "Lỗi", f"Không tìm thấy thuật toán: {display_name}")
            return
        if self.training_running:
            if self.selected_algorithm_for_train == display_name: self.tab_widget.setCurrentIndex(1); return
            else: QMessageBox.critical(self, "Đang Chạy", "Quá trình tối ưu đang chạy. Dừng lại trước khi chọn thuật toán khác."); return

        trainer_logger.info(f"Selecting algorithm '{display_name}' for optimization.")
        self.selected_algorithm_for_train = display_name
        self.populate_run_tab_info(display_name)
        self._populate_advanced_train_settings()
        self._reset_param_generation_settings()
        self._populate_combination_selection()
        self.tab_widget.setTabEnabled(1, True)
        self.tab_widget.setCurrentIndex(1)
        algo_name = self.loaded_algorithms[display_name].get('class_name', display_name)
        self.update_status(f"Sẵn sàng tối ưu: {algo_name}")
        self._clear_training_log_display()
        self.check_resume_possibility()

    def populate_run_tab_info(self, display_name):
        """Populates the algorithm name label on the Run/Optimize tab."""
        if display_name in self.loaded_algorithms:
            class_name = self.loaded_algorithms[display_name]['class_name']
            filename = self.loaded_algorithms[display_name]['path'].name
            self.train_algo_name_label.setText(f"{class_name} ({filename})")
        else:
            self.train_algo_name_label.setText("Lỗi: Không tìm thấy")

    def _populate_advanced_train_settings(self):
        """Populates the manual parameter tuning section."""
        container_layout = self.advanced_train_params_layout
        while container_layout.count():
            item = container_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.advanced_train_widgets.clear()

        if not self.selected_algorithm_for_train:
            label = QLabel("Chưa chọn thuật toán."); label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(label); return
        display_name = self.selected_algorithm_for_train
        if display_name not in self.loaded_algorithms:
            label = QLabel("Lỗi: Thuật toán không tìm thấy."); label.setStyleSheet("color: #dc3545;")
            container_layout.addWidget(label); return

        params = self.loaded_algorithms[display_name]['config'].get('parameters', {})
        num_params = {k: v for k, v in params.items() if isinstance(v, (int, float))}

        if not num_params:
            label = QLabel("Thuật toán không có tham số số học."); label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(label); return

        header = QWidget(); h_layout = QHBoxLayout(header); h_layout.setContentsMargins(5, 5, 5, 10)
        h_layout.addWidget(QLabel("Tham số"), 2); h_layout.addWidget(QLabel("Giá trị gốc"), 1); h_layout.addWidget(QLabel("Chế độ"), 1); h_layout.addWidget(QLabel("Bước tùy chỉnh (+/- hoặc giá trị)"), 3); container_layout.addWidget(header)

        for name, value in num_params.items():
            p_frame = QWidget(); p_layout = QHBoxLayout(p_frame); p_layout.setContentsMargins(5, 2, 5, 2)
            if name not in self.training_custom_steps:
                 self.training_custom_steps[name] = {'mode': 'Auto', 'steps': [], 'str_value': ""}
            state = self.training_custom_steps[name]
            p_layout.addWidget(QLabel(name), 2)
            value_str = f"{value:.4g}" if isinstance(value, float) else str(value); p_layout.addWidget(QLabel(value_str), 1)
            combo = QComboBox(); combo.addItems(["Auto", "Custom"]); combo.setCurrentText(state['mode']); combo.setFixedWidth(80); p_layout.addWidget(combo, 1)
            entry = QLineEdit(state.get('str_value', '')); entry.setPlaceholderText("VD: 1, 2, 5 hoặc -0.1, 0.1"); entry.setValidator(self.custom_steps_validator); entry.setEnabled(state['mode'] == 'Custom'); p_layout.addWidget(entry, 3)
            combo.currentTextChanged.connect(lambda t, n=name, mc=combo, se=entry: self._on_step_mode_change(n, mc, se))
            entry.textChanged.connect(lambda t, n=name, se=entry: self._update_custom_steps(n, se))
            container_layout.addWidget(p_frame)
            self.advanced_train_widgets[name] = {'mode_combo': combo, 'steps_entry': entry}

        is_gen_mode = self.param_gen_enable_checkbox.isChecked()
        self.advanced_train_groupbox.setEnabled(not is_gen_mode)

    def _clear_combination_selection(self):
        """Clears the combination algorithm checkboxes."""
        container_layout = self.combination_layout
        while container_layout.count():
            item = container_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.combination_selection_checkboxes.clear()

        label = QLabel("Chọn...")
        label.setStyleSheet("font-style: italic; color: #6c757d;")
        if hasattr(self, 'combination_layout') and self.combination_layout:
            self.combination_layout.addWidget(label)

    def _populate_combination_selection(self):
        """Populates the checkbox list for combination algorithms."""
        container_layout = self.combination_layout
        while container_layout.count():
            item = container_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.combination_selection_checkboxes.clear()

        if not self.selected_algorithm_for_train:
            label = QLabel("Chưa chọn thuật toán."); label.setStyleSheet("font-style: italic;"); container_layout.addWidget(label); return

        target = self.selected_algorithm_for_train
        available = sorted(self.loaded_algorithms.keys())

        if len(available) <= 1:
            label = QLabel("Không có thuật toán khác để kết hợp."); label.setStyleSheet("font-style: italic;"); container_layout.addWidget(label); return

        found_others = False
        for name in available:
            if name == target: continue
            class_name = self.loaded_algorithms[name].get('class_name', name.split(' (')[0])
            chk = QCheckBox(class_name); chk.setToolTip(f"Thuật toán: {name}")
            container_layout.addWidget(chk)
            self.combination_selection_checkboxes[name] = chk
            found_others = True

        if not found_others:
             label = QLabel("Không có thuật toán khác."); label.setStyleSheet("font-style: italic;"); container_layout.addWidget(label)


    def _clear_combination_selection(self):
        """Clears the combination algorithm checkboxes."""
        container_layout = self.combination_layout
        while container_layout.count():
            item = container_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.combination_selection_checkboxes.clear()

        label = QLabel("Chọn...")
        label.setStyleSheet("font-style: italic; color: #6c757d;")
        if hasattr(self, 'combination_layout') and self.combination_layout:
            self.combination_layout.addWidget(label)

    def _on_step_mode_change(self, param_name, mode_combo_widget, steps_entry_widget):
        """Handles changes in the Auto/Custom combobox for manual tuning."""
        new_mode = mode_combo_widget.currentText()
        if param_name in self.training_custom_steps:
            self.training_custom_steps[param_name]['mode'] = new_mode
            is_custom = (new_mode == 'Custom')
            steps_entry_widget.setEnabled(is_custom)
            if is_custom: steps_entry_widget.setFocus(); self._update_custom_steps(param_name, steps_entry_widget)
            else: steps_entry_widget.setStyleSheet("")

    def _validate_custom_steps_input_bool(self, text):
        """Internal helper to check custom steps syntax (comma-separated numbers)."""
        if not text: return True
        regex = QtCore.QRegularExpression(r"^(?:[-+]?\d+(?:\.\d*)?(?:,\s*[-+]?\d+(?:\.\d*)?)*)?$")
        match = regex.match(text)
        return match.hasMatch() and match.capturedLength() == len(text)

    def _update_custom_steps(self, param_name, steps_entry_widget):
        """Updates the internal state and validates custom step input for manual tuning."""
        steps_str = steps_entry_widget.text().strip()
        error_style = "QLineEdit { border: 1px solid #dc3545; }"
        if param_name in self.training_custom_steps:
            state = self.training_custom_steps[param_name]; state['str_value'] = steps_str
            if state['mode'] == 'Custom':
                valid_syntax = self._validate_custom_steps_input_bool(steps_str); parse_err = False; parsed = []
                if valid_syntax and steps_str:
                    try:
                        orig_val = self.loaded_algorithms[self.selected_algorithm_for_train]['config']['parameters'][param_name]; is_int = isinstance(orig_val, int); tmp = []
                        for part in steps_str.split(','):
                            part = part.strip()
                            if part:
                                num = float(part)
                                if is_int:
                                    if num != int(num): raise ValueError(f"Tham số nguyên '{param_name}' chỉ chấp nhận bước là số nguyên.")
                                    tmp.append(int(num))
                                else: tmp.append(num)
                        if tmp: parsed = sorted(list(set(tmp)))
                    except ValueError as ve: parse_err = True; steps_entry_widget.setToolTip(str(ve)); trainer_logger.warning(f"Invalid custom step value for {param_name}: {ve}")
                    except Exception as e: parse_err = True; steps_entry_widget.setToolTip(f"Lỗi xử lý: {e}"); trainer_logger.warning(f"Error parsing custom steps for {param_name}: {e}")
                elif not valid_syntax and steps_str: parse_err = True; steps_entry_widget.setToolTip("Định dạng sai (dùng dấu phẩy để ngăn cách số).")
                state['steps'] = parsed; steps_entry_widget.setStyleSheet(error_style if parse_err else "")
                if not parse_err: steps_entry_widget.setToolTip("")
            else: state['steps'] = []; steps_entry_widget.setStyleSheet(""); steps_entry_widget.setToolTip("")

    def _reset_advanced_train_settings(self):
        """Clears the manual parameter tuning UI."""
        self.training_custom_steps.clear()
        container_layout = self.advanced_train_params_layout
        if container_layout:
            while container_layout.count(): child = container_layout.takeAt(0);
            if child.widget(): child.widget().deleteLater()
        self.advanced_train_widgets.clear()
        label = QLabel("Chọn thuật toán..."); label.setStyleSheet("font-style: italic; color: #6c757d;")
        if container_layout: container_layout.addWidget(label)
        if hasattr(self, 'advanced_train_groupbox'): self.advanced_train_groupbox.setEnabled(True)

    def _clear_advanced_train_fields(self):
        self._reset_advanced_train_settings()

    def _toggle_param_generation_mode(self, state):
        """Enables/disables parameter generation widgets and the manual tuning groupbox."""
        is_enabled = (state == Qt.Checked)
        trainer_logger.debug(f"Parameter generation mode toggled: {'ON' if is_enabled else 'OFF'}")
        self.param_generation_widgets['count'].setEnabled(is_enabled)
        self.param_generation_widgets['mode_random'].setEnabled(is_enabled)
        self.param_generation_widgets['mode_seq'].setEnabled(is_enabled)
        self.advanced_train_groupbox.setEnabled(not is_enabled)
        self.check_resume_possibility()

    def _reset_param_generation_settings(self):
        """Resets the parameter generation UI to its default state (disabled)."""
        if hasattr(self, 'param_gen_enable_checkbox'):
             self.param_gen_enable_checkbox.setChecked(False)
             self._toggle_param_generation_mode(Qt.Unchecked)
             self.param_generation_widgets['count'].setValue(10)
             self.param_generation_widgets['mode_random'].setChecked(True)
        else:
             trainer_logger.warning("Attempted to reset param generation UI before init.")

    def _populate_combination_selection(self):
        """Populates the checkbox list for combination algorithms."""
        container_layout = self.combination_layout
        while container_layout.count():
            item = container_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.combination_selection_checkboxes.clear()

        if not self.selected_algorithm_for_train:
            label = QLabel("Chưa chọn thuật toán."); label.setStyleSheet("font-style: italic;"); container_layout.addWidget(label); return

        target = self.selected_algorithm_for_train
        available = sorted(self.loaded_algorithms.keys())

        if len(available) <= 1:
            label = QLabel("Không có thuật toán khác để kết hợp."); label.setStyleSheet("font-style: italic;"); container_layout.addWidget(label); return

        found_others = False
        for name in available:
            if name == target: continue
            class_name = self.loaded_algorithms[name].get('class_name', name.split(' (')[0])
            chk = QCheckBox(class_name); chk.setToolTip(f"Thuật toán: {name}")
            container_layout.addWidget(chk)
            self.combination_selection_checkboxes[name] = chk
            found_others = True

        if not found_others:
             label = QLabel("Không có thuật toán khác."); label.setStyleSheet("font-style: italic;"); container_layout.addWidget(label)

    def _clear_combination_selection(self):
        """Clears the combination algorithm checkboxes."""
        container_layout = self.combination_layout
        while container_layout.count(): child = container_layout.takeAt(0);
        if child.widget(): child.widget().deleteLater()
        self.combination_selection_checkboxes.clear()
        label = QLabel("Chọn..."); label.setStyleSheet("font-style: italic; color: #6c757d;")
        if hasattr(self, 'combination_layout') and self.combination_layout: self.combination_layout.addWidget(label)

    def _get_selected_combination_algos(self) -> list[str]:
        """Returns a list of selected combination algorithm display names."""
        return [name for name, chk in self.combination_selection_checkboxes.items() if chk.isChecked()]

    def start_optimization(self, initial_params=None, initial_best_streak=0, initial_combination_algos=None):
        """Starts a new optimization session (either Explore or GenerateSets mode)."""
        is_resuming_explore = initial_params is not None
        if is_resuming_explore and not isinstance(initial_params, dict):
             error_msg = f"Lỗi Resume Nghiêm Trọng: Dữ liệu tham số để tiếp tục không hợp lệ!\nKiểu dữ liệu: {type(initial_params)}\nGiá trị: {initial_params}"
             trainer_logger.error(error_msg + f" | Value received: {initial_params}")
             QMessageBox.critical(self, "Lỗi Tiếp Tục (Resume)", error_msg); self.training_running = False; self.training_paused = False; self.update_training_ui_state(); return
        if self.training_running: QMessageBox.warning(self, "Đang Chạy", "Quá trình tối ưu đang chạy."); return
        if not self.selected_algorithm_for_train: QMessageBox.critical(self, "Lỗi", "Chưa chọn thuật toán."); return
        display_name = self.selected_algorithm_for_train
        if display_name not in self.loaded_algorithms: QMessageBox.critical(self, "Lỗi", f"Thuật toán '{display_name}' không còn được tải."); return

        algo_data = self.loaded_algorithms[display_name]; base_params = algo_data['config'].get('parameters', {}); num_params = {k: v for k, v in base_params.items() if isinstance(v, (int, float))}
        is_generate_sets_mode = self.param_gen_enable_checkbox.isChecked(); optimization_mode = "GenerateSets" if is_generate_sets_mode else "Explore"
        trainer_logger.info(f"Starting optimization in {optimization_mode} mode.")
        start_d, time_limit, streak_limit = self._validate_training_settings();
        if start_d is None: return
        combos = initial_combination_algos if is_resuming_explore and initial_combination_algos is not None else self._get_selected_combination_algos()
        custom_steps_config = {}; initial_param_sets_for_worker = []; gen_config = {}; initial_params_for_worker = None; initial_streak_for_worker = 0

        if optimization_mode == "Explore":
             current_start_params = initial_params if is_resuming_explore else base_params.copy()
             custom_steps_config, has_invalid = self._finalize_custom_steps_config(base_params)
             if has_invalid:
                 self._populate_advanced_train_settings()
                 if QMessageBox.warning(self, "Bước Tùy Chỉnh Lỗi", "Một số bước tùy chỉnh lỗi, đã đặt lại 'Auto'.\nTiếp tục?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No: return
             initial_param_sets_for_worker = [current_start_params]; initial_params_for_worker = current_start_params; initial_streak_for_worker = initial_best_streak
        elif optimization_mode == "GenerateSets":
             if not num_params: QMessageBox.information(self, "Thông Báo", "Thuật toán không có tham số số học để tạo bộ."); return
             gen_config['n_values'] = self.param_generation_widgets['count'].value(); gen_config['mode'] = "Random" if self.param_generation_widgets['mode_random'].isChecked() else "Sequential"
             trainer_logger.info(f"Configuring GenerateSets mode for worker: N={gen_config['n_values']}, Mode={gen_config['mode']}")
             initial_streak_for_worker = 0; initial_params_for_worker = base_params.copy(); initial_param_sets_for_worker = []
             self.update_status("Trainer: Chuẩn bị tạo bộ tham số..."); self._log_to_display("INFO", "Bắt đầu tạo bộ tham số trong luồng worker...", tag="GENERATE")

        self._start_optimization_worker_thread(
            display_name=display_name, start_date=start_d, time_limit_min=time_limit, streak_limit=streak_limit,
            optimization_mode=optimization_mode, initial_param_sets_list=initial_param_sets_for_worker,
            custom_steps_config=custom_steps_config, generation_config=gen_config, combination_algos=combos,
            initial_base_params=initial_params_for_worker, initial_best_streak=initial_streak_for_worker,
            is_resuming_explore=is_resuming_explore
        )

    def _generate_parameter_sets(self, base_params, num_values_per_param, mode):
        """Generates multiple parameter sets based on N and mode. Runs in worker."""
        numerical_params = {k: v for k, v in base_params.items() if isinstance(v, (int, float))}
        if not numerical_params: worker_logger.warning("No numerical parameters found for generation."); return []
        param_value_options = {}; rng = random.Random()
        worker_logger.info(f"Generating param sets: Base Params={list(numerical_params.keys())}, N={num_values_per_param}, Mode={mode}")

        for p_name, p_value in numerical_params.items():
            generated_values = {p_value}; attempts = 0; max_attempts = num_values_per_param * 10; is_int = isinstance(p_value, int)
            while len(generated_values) < num_values_per_param and attempts < max_attempts:
                attempts += 1; new_val = None
                if mode == "Sequential":
                    step = max(1, abs(int(round(p_value * 0.1)))) if is_int else abs(p_value * 0.1)
                    if step < 1e-6: step = 0.1 if abs(p_value) < 1 else 1.0
                    if step == 0: step = 1
                    step_index = (len(generated_values) // 2) + 1; direction = 1 if len(generated_values) % 2 != 0 else -1
                    new_val_raw = p_value + (direction * step * step_index); new_val = int(round(new_val_raw)) if is_int else float(f"{new_val_raw:.6g}")
                elif mode == "Random":
                    if is_int:
                         base_delta = max(1, abs(int(round(p_value * 0.05)))); spread = max(base_delta, abs(int(round(p_value * 0.25)))); rand_min = p_value - spread; rand_max = p_value + spread
                         if rand_min >= rand_max: rand_max = rand_min + 1; new_val = rng.randint(rand_min, rand_max)
                    else:
                         base_delta = 0.05 if abs(p_value) < 1 else 0.1; spread = max(base_delta, abs(p_value * 0.25)); rand_min = p_value - spread; rand_max = p_value + spread
                         if abs(rand_max - rand_min) < 1e-9: rand_max = rand_min + base_delta*2; new_val_raw = rng.uniform(rand_min, rand_max); new_val = float(f"{new_val_raw:.6g}")
                if new_val is not None and new_val != p_value: generated_values.add(new_val)
            if len(generated_values) < num_values_per_param: worker_logger.warning(f"Could only generate {len(generated_values)} unique values for {p_name} (requested {num_values_per_param}). Attempts: {attempts}")
            param_value_options[p_name] = sorted(list(generated_values)); worker_logger.debug(f"Generated values for {p_name}: {param_value_options[p_name]}")

        worker_logger.info("Combining generated values using Cartesian product...")
        param_names = list(param_value_options.keys()); estimated_size = 1
        try:
            if sys.version_info >= (3, 8):
                 lengths = [];
                 for name in param_names:
                     num_options = len(param_value_options[name]);
                     if num_options == 0: raise ValueError(f"Generated empty value list for parameter '{name}'."); lengths.append(num_options)
                 estimated_size = math.prod(lengths)
            else:
                 for name in param_names:
                     num_options = len(param_value_options[name]);
                     if num_options == 0: raise ValueError(f"Generated empty value list for parameter '{name}'.")
                     if estimated_size > float('inf') / num_options: estimated_size = float('inf'); break; estimated_size *= num_options
        except ValueError as size_e: worker_logger.error(f"Error estimating size: {size_e}"); estimated_size = float('inf')
        except OverflowError: worker_logger.error("OverflowError estimating size."); estimated_size = float('inf')
        except Exception as size_e: worker_logger.error(f"Error estimating size: {size_e}", exc_info=True); estimated_size = float('inf')

        COMBINATION_SIZE_LIMIT = 50_000_000
        if estimated_size == float('inf') or estimated_size > COMBINATION_SIZE_LIMIT:
            size_display = f"{int(estimated_size):,}" if estimated_size != float('inf') else f'>{COMBINATION_SIZE_LIMIT:,}'; limit_display = f"{COMBINATION_SIZE_LIMIT:,}"
            worker_logger.error(f"Combination size ({size_display}) exceeds limit ({limit_display}). Aborting."); raise ValueError(f"Quá nhiều bộ kết hợp ({size_display} > {limit_display}). Giảm N.")

        try:
            value_combinations_gen = itertools.product(*(param_value_options[name] for name in param_names))
            worker_logger.info(f"Cartesian product generator created (Est. size: {estimated_size:,}). Building list...")
            final_param_sets = []; count = 0; YIELD_INTERVAL = 10000; time_last_yield = time.time()
            for combo in value_combinations_gen:
                new_set = base_params.copy();
                for i, name in enumerate(param_names): new_set[name] = combo[i];
                final_param_sets.append(new_set); count += 1
                if count % YIELD_INTERVAL == 0:
                    if hasattr(self, 'training_stop_event') and self.training_stop_event.is_set(): worker_logger.info("Stop requested during param set construction."); return []
                    current_time = time.time();
                    if current_time - time_last_yield > 0.1: time.sleep(0.001); time_last_yield = current_time
        except MemoryError as me: worker_logger.error(f"MemoryError constructing product: {me}. Size: {estimated_size:,}."); raise MemoryError(f"Lỗi bộ nhớ khi tạo {estimated_size:,} bộ tham số. Giảm N.")
        except Exception as e: worker_logger.error(f"Error during Cartesian product: {e}", exc_info=True); raise e

        worker_logger.info(f"Finished generating {len(final_param_sets):,} parameter sets.")
        return final_param_sets

    def resume_exploration_session(self):
        """Loads the latest saved state and resumes training ONLY in Explore mode."""
        trainer_logger.info("--- Enter resume_exploration_session ---")

        if self.training_running:
            QMessageBox.warning(self, "Đang Chạy", "Quá trình tối ưu đang chạy.")
            trainer_logger.info("--- Exit resume_exploration_session (already running) ---")
            return
        if not self.selected_algorithm_for_train:
            QMessageBox.critical(self, "Lỗi", "Chưa chọn thuật toán.")
            trainer_logger.info("--- Exit resume_exploration_session (no algo selected) ---")
            return
        if self.param_gen_enable_checkbox.isChecked():
            QMessageBox.information(self, "Không Hỗ Trợ", "Chế độ 'Tạo Bộ Tham Số' không hỗ trợ tiếp tục.\nHãy bắt đầu một phiên mới.")
            trainer_logger.info("--- Exit resume_exploration_session (generate mode active) ---")
            return

        target_name = self.selected_algorithm_for_train
        if target_name not in self.loaded_algorithms:
            QMessageBox.critical(self, "Lỗi", f"Thuật toán '{target_name}' không còn được tải.")
            trainer_logger.info(f"--- Exit resume_exploration_session (algo '{target_name}' not loaded) ---")
            return

        try:
            algo_data = self.loaded_algorithms[target_name]
            algo_stem = algo_data['path'].stem
            train_dir = self.training_dir / algo_stem
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Nội Bộ", f"Không thể lấy thông tin thuật toán đã chọn:\n{e}")
            trainer_logger.error(f"Error getting algo data for '{target_name}' in resume: {e}")
            trainer_logger.info("--- Exit resume_exploration_session (error getting algo data) ---")
            return

        trainer_logger.info(f"Attempting to find state file for '{algo_stem}'")
        state_result = self.find_latest_training_state(train_dir, algo_stem)
        latest_file = state_result[0]
        latest_data = state_result[1]

        if latest_data is None:
            trainer_logger.warning(f"find_latest_training_state returned None data. Cannot resume.")
            QMessageBox.information(self, "Không Tìm Thấy", f"Không tìm thấy trạng thái 'Explore' hợp lệ đã lưu cho:\n{target_name}")
            trainer_logger.info("--- Exit resume_exploration_session (latest_data is None) ---")
            return

        trainer_logger.info(f"State data found for Explore mode in: {latest_file.name}")

        try:
            loaded_params = latest_data.get("best_params", None)
            streak = latest_data.get("best_streak")
            start_str = latest_data.get("start_date")
            combos_raw = latest_data.get("combination_algorithms", [])

            if not isinstance(loaded_params, dict):
                raise ValueError(f"Dữ liệu 'best_params' trong file trạng thái không phải là dictionary (kiểu: {type(loaded_params)}).")

            trainer_logger.info(f"Extracted from state file: params_type={type(loaded_params)}, streak={streak}, start_date='{start_str}'")

            if not isinstance(streak, int) or \
               not isinstance(start_str, str) or not isinstance(combos_raw, list):
                raise ValueError("Dữ liệu JSON trong file trạng thái không hợp lệ hoặc thiếu trường (streak/date/combos).")

            try:
                start_date_obj = datetime.datetime.strptime(start_str, '%d/%m/%Y').date()
                if self.results_data and len(self.results_data) >= 2:
                    min_d, max_d = self.results_data[0]['date'], self.results_data[-1]['date']
                    if not (min_d <= start_date_obj < max_d):
                        raise ValueError(f"Ngày bắt đầu đã lưu ({start_str}) nằm ngoài phạm vi ({min_d:%d/%m/%Y} - {max_d:%d/%m/%Y}).")
                    self.train_start_date_edit.setText(start_str)
                else:
                     raise ValueError("Không đủ dữ liệu để xác thực ngày bắt đầu.")
            except ValueError as date_err:
                QMessageBox.critical(self, "Lỗi Ngày Đã Lưu", f"Không thể dùng ngày từ file trạng thái:\n'{start_str}'\nLỗi: {date_err}\n\nVui lòng chọn lại.")
                trainer_logger.info("--- Exit resume_exploration_session (invalid date) ---")
                return

            current_numeric_keys = {k for k, v in algo_data['config'].get('parameters', {}).items() if isinstance(v, (int, float))}
            loaded_numeric_keys = {k for k, v in loaded_params.items() if isinstance(v, (int, float))}

            if current_numeric_keys != loaded_numeric_keys:
                msg = ("Tham số trong file trạng thái không hoàn toàn khớp với tham số số học của thuật toán hiện tại.\n\n"
                       f"Thiếu trong file: {current_numeric_keys - loaded_numeric_keys}\n"
                       f"Thêm trong file: {loaded_numeric_keys - current_numeric_keys}\n\n"
                       "Tiếp tục với tham số đã lưu (bỏ qua các khác biệt)?")
                if QMessageBox.question(self, "Tham Số Không Khớp", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No:
                    trainer_logger.info("--- Exit resume_exploration_session (user cancelled on param mismatch) ---")
                    return
                loaded_params = {k: v for k, v in loaded_params.items() if k in current_numeric_keys}

            missing_combos = [c for c in combos_raw if c not in self.loaded_algorithms]
            final_combos = [c for c in combos_raw if c in self.loaded_algorithms]
            if missing_combos:
                msg = f"Các thuật toán kết hợp sau từ file trạng thái không được tìm thấy:\n- {', '.join(missing_combos)}\n\nTiếp tục mà không có chúng?"
                if QMessageBox.question(self, "Thiếu Thuật Toán Kết Hợp", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No:
                    trainer_logger.info("--- Exit resume_exploration_session (user cancelled on missing combos) ---")
                    return

            self._populate_combination_selection()
            for name, chk in self.combination_selection_checkboxes.items():
                chk.setChecked(name in final_combos)
            self._log_to_display("INFO", f"TIẾP TỤC PHIÊN EXPLORE TỪ FILE: {latest_file.name}", tag="RESUME")
            self._log_to_display("INFO", f"  Tham số bắt đầu: {loaded_params}", tag="RESUME")
            self._log_to_display("INFO", f"  Chuỗi tốt nhất trước đó: {streak}", tag="RESUME")
            self._log_to_display("INFO", f"  Ngày bắt đầu: {start_str}", tag="RESUME")
            self._log_to_display("INFO", f"  Kết hợp: {final_combos or '(Không có)'}", tag="RESUME")

            trainer_logger.info(f"All checks passed in resume_exploration_session. Calling start_optimization...")

            self.start_optimization(initial_params=loaded_params,
                                    initial_best_streak=streak,
                                    initial_combination_algos=final_combos)

        except Exception as e:
            QMessageBox.critical(self, "Lỗi Tải Trạng Thái", f"Không thể tải hoặc xác thực trạng thái từ:\n{latest_file.name if latest_file else 'N/A'}\n\nLỗi: {e}")
            trainer_logger.error(f"Error loading/validating state file: {e}", exc_info=True)
            trainer_logger.info("--- Exit resume_exploration_session (exception during validation) ---")

        trainer_logger.info("--- Exit resume_exploration_session (normally after calling start_optimization or exception) ---")

    def _save_training_state(self, reason="unknown"):
        """Saves the current best state (params, streak) to a JSON file."""
        if not self.selected_algorithm_for_train or not self.current_training_target_dir or not isinstance(self.current_best_params, dict):
            trainer_logger.warning(f"Save state skipped (Reason: {reason}): Algo/Dir/Params missing or invalid type (Type: {type(self.current_best_params)}).")
            return
        try:
            target_dir = self.current_training_target_dir; target_dir.mkdir(parents=True, exist_ok=True)
            algo_stem = self.loaded_algorithms[self.selected_algorithm_for_train]['path'].stem
            state_filename = f"training_state_{algo_stem}.json"; state_filepath = target_dir / state_filename
            start_date_s = getattr(self, 'last_train_start_date_str', ''); current_mode = getattr(self, 'last_run_mode', 'Explore')
            state_data = {'target_algorithm': self.selected_algorithm_for_train, 'best_params': self.current_best_params, 'best_streak': self.current_best_streak, 'combination_algorithms': self.current_combination_algos, 'start_date': start_date_s, 'optimization_mode': current_mode, 'save_reason': reason, 'save_timestamp': datetime.datetime.now().isoformat()}
            state_filepath.write_text(json.dumps(state_data, indent=4, ensure_ascii=False), encoding='utf-8')
            self._log_to_display("INFO", f"Đã lưu trạng thái (Mode: {current_mode}, Reason: {reason}). File: {state_filename}", tag="RESUME"); self.check_resume_possibility()
        except KeyError: trainer_logger.error(f"Save state failed: Selected algorithm '{self.selected_algorithm_for_train}' not found.")
        except AttributeError as ae: trainer_logger.error(f"Save state failed: Attribute error - {ae}.")
        except Exception as e: self._log_to_display("ERROR", f"Lỗi lưu trạng thái tối ưu: {e}", tag="ERROR"); trainer_logger.error(f"Error saving optimization state: {e}", exc_info=True)

    def find_latest_training_state(self, training_dir: Path, algo_stem: str):
        """Finds and validates the training state file for a given algorithm."""
        trainer_logger.debug(f"Checking for state file for {algo_stem} in {training_dir}")
        state_file = training_dir / f"training_state_{algo_stem}.json"
        if state_file.exists():
            trainer_logger.debug(f"Found potential state file: {state_file.name}")
            try:
                 data = json.loads(state_file.read_text(encoding='utf-8')); required_keys = ["best_params", "best_streak", "start_date", "optimization_mode"]
                 if all(key in data for key in required_keys):
                     saved_mode = data.get("optimization_mode")
                     if saved_mode == "Explore":
                         if isinstance(data.get("best_params"), dict): trainer_logger.info(f"Using valid 'Explore' state file: {state_file.name}"); return state_file, data
                         else: trainer_logger.warning(f"State file {state_file.name} is 'Explore' but 'best_params' is not dict (type: {type(data.get('best_params'))}). Cannot use."); return None, None
                     else: trainer_logger.info(f"State file {state_file.name} is for mode '{saved_mode}', not 'Explore'. Cannot resume."); return None, None
                 else: trainer_logger.warning(f"State file {state_file.name} missing required keys ({required_keys})."); return None, None
            except json.JSONDecodeError as json_err: trainer_logger.warning(f"Error decoding JSON from state file {state_file.name}: {json_err}"); return None, None
            except Exception as e: trainer_logger.warning(f"Error reading/processing state file {state_file.name}: {e}"); return None, None
        else: trainer_logger.debug(f"State file not found: {state_file.name}"); return None, None



    def _start_optimization_worker_thread(self, display_name, start_date, time_limit_min, streak_limit,
                                         optimization_mode, initial_param_sets_list, custom_steps_config,
                                         generation_config, combination_algos,
                                         initial_base_params, initial_best_streak,
                                         is_resuming_explore):
        """Starts the optimization worker thread based on the selected mode."""
        try:
            algo_data = self.loaded_algorithms[display_name]
        except KeyError:
            QMessageBox.critical(self, "Lỗi", f"Thuật toán '{display_name}' không tìm thấy khi bắt đầu worker.")
            return

        if not isinstance(initial_base_params, dict):
            error_msg = f"Lỗi nghiêm trọng: Tham số ban đầu không phải là dictionary (kiểu: {type(initial_base_params)})."
            trainer_logger.critical(error_msg)
            QMessageBox.critical(self, "Lỗi Tham Số Worker", error_msg)
            self.update_status("Lỗi: Tham số worker không hợp lệ.")
            self.training_running = False
            self.update_training_ui_state()
            return

        self.current_training_target_dir = self.training_dir / algo_data['path'].stem
        self.current_training_target_dir.mkdir(parents=True, exist_ok=True)

        if hasattr(self, 'train_log_text'): self.train_log_text.clear()

        log_tag = "RESUME" if is_resuming_explore else "PROGRESS"
        title_verb = "TIẾP TỤC" if is_resuming_explore else "BẮT ĐẦU"
        mode_text = "Tạo Bộ Tham Số" if optimization_mode == "GenerateSets" else "Khám Phá (Explore)"
        self._log_to_display("INFO", f"={'='*10} {title_verb} PHIÊN TỐI ƯU ({mode_text}) {'='*10}", tag=log_tag)
        self._log_to_display("INFO", f"Thuật toán: {display_name}", tag=log_tag)
        self._log_to_display("INFO", f"Chế độ: {mode_text}", tag=log_tag)
        if optimization_mode == "GenerateSets" and generation_config:
             self._log_to_display("INFO", f"Cấu hình tạo bộ: N={generation_config.get('n_values', '?')}, Mode={generation_config.get('mode', '?')}", tag="GENERATE")
             self.update_status_label("Chuẩn bị tạo bộ tham số...")
        elif optimization_mode == "Explore":
             self._log_to_display("INFO", f"Số bộ tham số ban đầu: {len(initial_param_sets_list)}", tag=log_tag)
        self._log_to_display("INFO", f"Kết hợp với: {combination_algos or '(Không có)'}", tag=log_tag)
        self._log_to_display("INFO", f"Ngày Bắt đầu: {start_date:%d/%m/%Y}", tag=log_tag)
        time_str = f"{time_limit_min} phút" if time_limit_min > 0 else "Không giới hạn"
        streak_str = f"{streak_limit} ngày" if streak_limit > 0 else "Không giới hạn"
        self._log_to_display("INFO", f"Giới hạn TG: {time_str}", tag=log_tag)
        self._log_to_display("INFO", f"Mục tiêu chuỗi: {streak_str}", tag=log_tag)
        if is_resuming_explore:
             self._log_to_display("INFO", f"Tiếp tục từ chuỗi: {initial_best_streak}", tag=log_tag)
             self._log_to_display("INFO", f"Tiếp tục từ params: {initial_base_params}", tag="RESUME")
        elif optimization_mode == "GenerateSets":
              self._log_to_display("INFO", f"Tham số gốc: {initial_base_params}", tag="GENERATE")

        self._clear_calculation_cache()
        self.training_stop_event.clear()
        self.training_pause_event.clear()
        self.training_running = True
        self.training_paused = False
        self.current_best_params = copy.deepcopy(initial_base_params)
        self.current_best_streak = initial_best_streak
        self.current_combination_algos = combination_algos
        self.last_train_start_date_str = start_date.strftime('%d/%m/%Y')
        self.last_run_mode = optimization_mode
        self.train_start_time = time.time()
        self.train_time_limit_sec = time_limit_min * 60 if time_limit_min > 0 else 0
        self.train_streak_limit = streak_limit

        if hasattr(self, 'train_progressbar'): self.train_progressbar.setValue(0)
        if hasattr(self, 'train_progress_label'): self.train_progress_label.setText("0%")
        if hasattr(self, 'train_streak_label'): self.train_streak_label.setText(f"Chuỗi: 0 / Best: {self.current_best_streak}")

        show_timer = self.train_time_limit_sec > 0
        if hasattr(self, 'train_time_static_label'): self.train_time_static_label.setVisible(show_timer)
        if hasattr(self, 'train_time_remaining_label'): self.train_time_remaining_label.setVisible(show_timer)

        if show_timer:
            t_str = time.strftime('%H:%M:%S' if self.train_time_limit_sec >= 3600 else '%M:%S', time.gmtime(self.train_time_limit_sec))
            if hasattr(self, 'train_time_remaining_label'):
                 self.train_time_remaining_label.setText(t_str)
        else:
            if hasattr(self, 'train_time_remaining_label'):
                self.train_time_remaining_label.setText("--:--:--")

        self.update_training_ui_state()

        trainer_logger.info("Creating/starting optimization worker thread.")
        self.training_thread = threading.Thread(
            target=self._optimization_worker,
            args=(
                display_name,
                start_date,
                self.train_time_limit_sec,
                self.train_streak_limit,
                optimization_mode,
                initial_param_sets_list,
                custom_steps_config,
                generation_config,
                combination_algos,
                self.current_best_params,
                self.current_best_streak,
            ),
            name=f"Optimizer-{algo_data['path'].stem}",
            daemon=True
        )
        self.training_thread.start()

        if not self.training_timer.isActive(): self.training_timer.start(self.training_timer_interval)
        if show_timer and not self.display_timer.isActive(): self.display_timer.start(self.display_timer_interval)

        verb = "Tiếp tục (Explore)" if is_resuming_explore else "Bắt đầu"
        status_extra = " (Đang tạo bộ tham số...)" if optimization_mode == "GenerateSets" else ""
        self.update_status(f"Tìm chuỗi ngày {verb} tối ưu: {algo_data['class_name']}...{status_extra}")

    def _get_fixed_max_stall_cycles(self) -> int:
        """
        Trả về giá trị cố định được sử dụng cho MAX_STALL_CYCLES trong chế độ Explore.
        Hàm này đảm bảo giá trị được kiểm soát tập trung.
        """
        FIXED_VALUE = 20  # <<<====== ĐẶT GIÁ TRỊ CỐ ĐỊNH MONG MUỐN Ở ĐÂY (Ví dụ: 10)
        trainer_logger.debug(f"Providing fixed MAX_STALL_CYCLES value: {FIXED_VALUE}")
        return FIXED_VALUE

    # <<< HÀM _optimization_worker ĐÃ ĐƯỢC CHỈNH SỬA >>>
    def _optimization_worker(self, target_display_name, start_date, time_limit_sec, streak_limit,
                             optimization_mode, initial_param_sets_list, custom_steps_config,
                             generation_config, combination_algo_names,
                             initial_base_params, initial_best_streak):
        """The core optimization logic running in a separate thread."""
        start_time = time.time()
        worker_logger.info(f"Worker starting ({optimization_mode} mode) for {target_display_name} from {start_date}.")
        if optimization_mode == "Explore": worker_logger.info(f"Initial Best Streak: {initial_best_streak}, Params: {initial_base_params}")
        elif optimization_mode == "GenerateSets": worker_logger.info(f"GenerateSets mode configured with: {generation_config}")

        # --- Queue Helper Functions ---
        def queue_log(level, text, tag=None):
            self.training_queue.put({"type": "log", "payload": {"level": level, "text": text, "tag": tag}})
        def queue_status(text):
            self.training_queue.put({"type": "status", "payload": text})
        def queue_progress(payload):
            payload['mode'] = optimization_mode
            self.training_queue.put({"type": "progress", "payload": payload})
        def queue_best_update(p, s):
            self.training_queue.put({"type": "best_update", "payload": {"params": p, "streak": s}})
        def queue_finished(message, success=True, reason="finished", sets_tested=None):
             payload = {"message": message, "success": success, "reason": reason}
             if sets_tested is not None: payload["sets_tested"] = sets_tested
             self.training_queue.put({"type": "finished", "payload": payload})
        def queue_error(text):
            self.training_queue.put({"type": "error", "payload": text})
        # --- End Queue Helper Functions ---

        finish_reason = "completed"; current_best_params_worker = copy.deepcopy(initial_base_params); current_best_streak_worker = initial_best_streak
        param_sets_to_test_in_worker = []; total_sets_tested_count = 0

        try:
            # --- Algorithm and Data Setup ---
            if target_display_name not in self.loaded_algorithms: raise RuntimeError(f"Target algorithm '{target_display_name}' not found.")
            target_data = self.loaded_algorithms[target_display_name]; orig_path = target_data['path']; cls_name = target_data['class_name']
            orig_params_config = target_data['config'].get('parameters', {});
            numeric_param_keys = {k for k, v in orig_params_config.items() if isinstance(v, (int, float))}
            params_order = sorted(list(numeric_param_keys))
            worker_logger.debug(f"Numeric parameter keys for exploration order: {params_order}")
            try: src_code = orig_path.read_text(encoding='utf-8')
            except Exception as e: raise RuntimeError(f"Failed to read source code {orig_path}: {e}")
            target_dir = self.current_training_target_dir
            if not self.results_data or len(self.results_data) < 2: raise RuntimeError("Insufficient data loaded.");
            res_map = {r['date']: r['result'] for r in self.results_data}; hist_cache = {}; sorted_res = sorted(self.results_data, key=lambda x: x['date'])
            for i, r in enumerate(sorted_res): hist_cache[r['date']] = sorted_res[:i];
            max_date = sorted_res[-1]['date']; min_date = sorted_res[0]['date']
            if start_date not in hist_cache:
                 if start_date == min_date: raise RuntimeError(f"Start date {start_date:%d/%m/%Y} is first date, cannot use for prediction.")
                 else: raise RuntimeError(f"Internal Error: History cache missing for start date {start_date:%d/%m/%Y}.")
            # --- End Algorithm and Data Setup ---

            # --- Parameter Set Preparation ---
            if optimization_mode == "GenerateSets":
                 queue_status("Đang tạo bộ tham số..."); queue_log("INFO", "Bắt đầu tạo bộ tham số...", tag="GENERATE")
                 n_val = generation_config.get('n_values'); gen_mode = generation_config.get('mode')
                 if n_val is None or gen_mode is None: raise ValueError("Missing N or Mode in generation config.")
                 try: generated_sets = self._generate_parameter_sets(initial_base_params, n_val, gen_mode)
                 except (ValueError, MemoryError) as gen_err: worker_logger.error(f"Param gen failed: {gen_err}"); queue_log("ERROR", f"Lỗi tạo bộ: {gen_err}", tag="ERROR"); queue_finished(f"Lỗi tạo bộ: {gen_err}", success=False, reason="generation_error"); return
                 except Exception as gen_e: worker_logger.error(f"Unexpected error generating params: {gen_e}", exc_info=True); queue_log("ERROR", f"Lỗi không mong muốn tạo bộ: {gen_e}", tag="ERROR"); queue_finished(f"Lỗi không mong muốn tạo bộ: {gen_e}", success=False, reason="generation_error"); return
                 if not generated_sets: worker_logger.warning("Param generation yielded no sets."); queue_log("WARNING", "Không tạo được bộ tham số.", tag="WARNING"); queue_finished("Không tạo được bộ tham số.", success=False, reason="generation_error"); return
                 queue_log("INFO", f"Đã tạo {len(generated_sets)} bộ tham số.", tag="GENERATE"); param_sets_to_test_in_worker = generated_sets; queue_status(f"Chuẩn bị kiểm tra {len(param_sets_to_test_in_worker)} bộ...")
            else: # Explore mode
                param_sets_to_test_in_worker = initial_param_sets_list
            # --- End Parameter Set Preparation ---

            # --- Simulation and Prediction Helpers ---
            def simulate_streak(params_to_test, simulation_start_date, history_lookup, results_lookup, max_results_date):
                current_streak = 0; last_successful_date = None; simulation_current_date = simulation_start_date; day_index = 0
                while True:
                    day_index += 1
                    if self.training_stop_event.is_set(): return -1, "stopped", simulation_current_date
                    while self.training_pause_event.is_set():
                        if self.training_stop_event.is_set(): return -1, "stopped", simulation_current_date; time.sleep(0.2)
                    elapsed_time_total = time.time() - start_time
                    if time_limit_sec > 0 and elapsed_time_total >= time_limit_sec: return -2, "time_limit", simulation_current_date
                    predict_for_date = simulation_current_date; check_results_date = predict_for_date + datetime.timedelta(days=1)
                    historical_data_slice = history_lookup.get(predict_for_date); actual_result_dict = results_lookup.get(check_results_date)
                    if historical_data_slice is None: return current_streak, "missing_history", predict_for_date
                    if actual_result_dict is None or check_results_date > max_results_date: return current_streak, "end_of_data", predict_for_date
                    top3_predicted_numbers = get_combined_top3_prediction(params_to_test, predict_for_date, historical_data_slice)
                    if top3_predicted_numbers is None: return current_streak, "prediction_error", predict_for_date
                    actual_winning_numbers = self.extract_numbers_from_result_dict(actual_result_dict)
                    if not actual_winning_numbers: simulation_current_date += datetime.timedelta(days=1); continue
                    hit = bool(top3_predicted_numbers.intersection(actual_winning_numbers))
                    if hit:
                        current_streak += 1; last_successful_date = simulation_current_date
                        if streak_limit > 0 and current_streak >= streak_limit: return current_streak, "streak_limit_reached", predict_for_date
                        simulation_current_date += datetime.timedelta(days=1)
                    else: return current_streak, "streak_broken", predict_for_date

            def get_combined_top3_prediction(current_params, prediction_date, historical_data):
                temp_instance = None; temp_module_name = None; temp_filepath = None
                try:
                    modified_source = self._modify_algorithm_source_ast(src_code, cls_name, current_params)
                    if not modified_source: raise RuntimeError("AST modification failed.")
                    timestamp = int(time.time()*10000) + random.randint(0,9999); temp_filename = f"temp_train_target_{cls_name}_{timestamp}.py"; temp_filepath = target_dir / temp_filename
                    temp_filepath.write_text(modified_source, encoding='utf-8')
                    if not (target_dir.parent / "__init__.py").exists(): (target_dir.parent / "__init__.py").touch()
                    if not (target_dir / "__init__.py").exists(): (target_dir / "__init__.py").touch()
                    temp_module_name = f"training.{target_dir.name}.{temp_filename[:-3]}"
                    temp_instance = self._import_and_instantiate_temp_algo(temp_filepath, temp_module_name, cls_name)
                    if not temp_instance: raise RuntimeError("Failed to import/instantiate temp algo.")
                except Exception as setup_err: worker_logger.error(f"Error setting up temp algo: {setup_err}", exc_info=True); return None
                day_results = {}; history_copy = copy.deepcopy(historical_data)
                try:
                    pred_target = temp_instance.predict(prediction_date, history_copy)
                    day_results[target_display_name] = pred_target if isinstance(pred_target, dict) else {}
                except Exception as e: worker_logger.error(f"ERROR predicting TEMP {target_display_name}: {e}", exc_info=False); day_results[target_display_name] = {}
                for combo_name in combination_algo_names:
                    if combo_name in self.loaded_algorithms:
                        try:
                            history_copy_combo = copy.deepcopy(historical_data)
                            pred_combo = self.loaded_algorithms[combo_name]['instance'].predict(prediction_date, history_copy_combo)
                            day_results[combo_name] = pred_combo if isinstance(pred_combo, dict) else {}
                        except Exception as e: worker_logger.error(f"ERROR predicting COMBO {combo_name}: {e}", exc_info=False); day_results[combo_name] = {}
                    else: worker_logger.warning(f"Combo algo '{combo_name}' not found.")
                try:
                    combined_scores = self.combine_algorithm_scores(day_results); scores_list = []
                    for num_str, score in combined_scores.items():
                         if isinstance(num_str, str) and len(num_str) == 2 and num_str.isdigit() and isinstance(score, (int, float)):
                              try: scores_list.append((int(num_str), float(score)))
                              except (ValueError, TypeError): pass
                    scores_list.sort(key=lambda x: x[1], reverse=True); top3_numbers = {item[0] for item in scores_list[:3]}; return top3_numbers
                except Exception as combine_err: worker_logger.error(f"Error combining scores: {combine_err}", exc_info=True); return None
                finally:
                    if temp_instance: temp_instance = None
                    if temp_module_name and temp_module_name in sys.modules:
                        try: del sys.modules[temp_module_name]
                        except KeyError: pass
                    if temp_filepath and temp_filepath.exists():
                        try: temp_filepath.unlink()
                        except OSError as e: worker_logger.warning(f"Could not delete temp file {temp_filepath}: {e}")
            # --- End Simulation and Prediction Helpers ---

            # ==============================================
            # ===== MAIN OPTIMIZATION LOOP BY MODE =========
            # ==============================================

            if optimization_mode == "GenerateSets":
                # --- GenerateSets Mode Logic (Không thay đổi) ---
                worker_logger.info(f"Starting GenerateSets loop for {len(param_sets_to_test_in_worker)} sets.")
                total_sets_to_test = len(param_sets_to_test_in_worker)
                for idx, current_params_set in enumerate(param_sets_to_test_in_worker):
                    set_number = idx + 1; total_sets_tested_count = set_number
                    if self.training_stop_event.is_set(): finish_reason = "stopped"; break
                    while self.training_pause_event.is_set():
                        if self.training_stop_event.is_set(): finish_reason = "stopped"; break; queue_status(f"Tạm dừng (bộ {set_number}/{total_sets_to_test})"); time.sleep(0.5)
                    if finish_reason == "stopped": break
                    elapsed_time_total = time.time() - start_time;
                    if time_limit_sec > 0 and elapsed_time_total >= time_limit_sec: finish_reason = "time_limit"; break
                    params_str_short = {k: f'{v:.3g}' if isinstance(v,float) else v for k, v in current_params_set.items() if k in numeric_param_keys}
                    queue_log("INFO", f"--- Bắt đầu kiểm tra bộ #{set_number}/{total_sets_to_test}: {params_str_short}", tag="PARAM_SET"); queue_status(f"Kiểm tra bộ {set_number}/{total_sets_to_test}...")
                    set_streak, sim_reason, _ = simulate_streak(current_params_set, start_date, hist_cache, res_map, max_date)
                    if sim_reason == "stopped": finish_reason = "stopped"; break
                    if sim_reason == "time_limit": finish_reason = "time_limit"; break
                    if sim_reason == "prediction_error": queue_log("ERROR", f"Lỗi dự đoán khi kiểm tra bộ #{set_number}. Chuỗi cuối cùng: {max(0, set_streak)}", tag="ERROR")
                    elif sim_reason == "missing_history": queue_log("ERROR", f"Lỗi thiếu dữ liệu lịch sử khi kiểm tra bộ #{set_number}. Chuỗi cuối cùng: {max(0, set_streak)}", tag="ERROR")
                    queue_log("INFO", f"--- Kết thúc bộ #{set_number}: Chuỗi = {max(0, set_streak)} (Lý do: {sim_reason})", tag="PARAM_SET")
                    if set_streak > current_best_streak_worker:
                        current_best_streak_worker = set_streak; current_best_params_worker = copy.deepcopy(current_params_set)
                        queue_log("BEST", f"*** New Best Streak: {current_best_streak_worker}! (Set #{set_number}) Params: {params_str_short}", tag="BEST")
                        queue_best_update(current_best_params_worker, current_best_streak_worker);
                        self._save_training_state(reason="new_best_streak")
                    queue_progress({"current_set_idx": set_number, "total_sets": total_sets_to_test, "current_streak": max(0, set_streak), "best_streak": current_best_streak_worker})
                    if streak_limit > 0 and current_best_streak_worker >= streak_limit:
                        worker_logger.info(f"Best streak ({current_best_streak_worker}) meets target ({streak_limit}). Stopping GenerateSets.")
                        finish_reason = "streak_limit_reached"; break
                if finish_reason == "completed": finish_reason = "all_sets_tested"


            elif optimization_mode == "Explore":
                # --- Explore Mode Logic ---
                worker_logger.info("Starting Explore mode loop.");
                params_q = queue.Queue();
                for p in param_sets_to_test_in_worker: params_q.put(p);

                visited_params = {repr(p) for p in param_sets_to_test_in_worker};
                MAX_NEIGHBORS_PER_CYCLE = 1000; # Giữ nguyên hoặc thay đổi nếu muốn

                MAX_STALL_CYCLES = self._get_fixed_max_stall_cycles() # Lấy giá trị cố định

                stall_cycle_count = 0;
                exploration_cycle = 0;
                total_tests_count = 0
                current_params_explore = None # Khởi tạo

                while True: # Main Explore loop
                    # --- Check Stop Conditions ---
                    if self.training_stop_event.is_set(): finish_reason = "stopped"; break
                    while self.training_pause_event.is_set():
                        if self.training_stop_event.is_set(): finish_reason = "stopped"; break; queue_status(f"Tạm dừng (Explore Cycle {exploration_cycle})"); time.sleep(0.5)
                    if finish_reason == "stopped": break
                    elapsed_time_total = time.time() - start_time;
                    if time_limit_sec > 0 and elapsed_time_total >= time_limit_sec: finish_reason = "time_limit"; break
                    # --- End Check Stop Conditions ---

                    # --- Get Params or Generate Neighbors ---
                    if not params_q.empty():
                        current_params_explore = params_q.get() # Lấy từ hàng đợi
                        total_tests_count += 1
                    else:
                        # Hàng đợi trống, thử tạo hàng xóm
                        # <<< CHỈ KIỂM TRA ĐIỀU KIỆN DỪNG stall_cycle_count >= MAX_STALL_CYCLES >>>
                        if stall_cycle_count >= MAX_STALL_CYCLES:
                            worker_logger.info(f"Stopping Explore: Max stall cycles ({MAX_STALL_CYCLES}) reached without improvement.")
                            finish_reason = "no_improvement"; break

                        exploration_cycle += 1
                        stall_cycle_count += 1 # Tăng stall count vì phải tạo hàng xóm
                        queue_status(f"Explore Cycle {exploration_cycle}: Tạo hàng xóm (Best: {current_best_streak_worker}, Stall: {stall_cycle_count}/{MAX_STALL_CYCLES})...")

                        # --- START: Neighbor Generation Logic (Đã sửa lỗi kiểu dữ liệu và có logging) ---
                        worker_logger.info(f"Explore Cycle {exploration_cycle}: Starting neighbor generation from best params: {current_best_params_worker}")
                        neighbors = []
                        params_to_explore_from = current_best_params_worker
                        neighbors_added_this_cycle = 0
                        shuffled_param_order = random.sample(params_order, len(params_order))

                        for p_name in shuffled_param_order:
                             if neighbors_added_this_cycle >= MAX_NEIGHBORS_PER_CYCLE:
                                 worker_logger.debug(f"[{p_name}] Reached MAX_NEIGHBORS_PER_CYCLE ({MAX_NEIGHBORS_PER_CYCLE}). Stopping generation for this cycle.")
                                 break
                             worker_logger.debug(f"--- Generating for param: '{p_name}' ---")
                             param_custom_config = custom_steps_config.get(p_name, {'mode': 'Auto', 'steps': []})
                             current_value = params_to_explore_from.get(p_name, None)
                             if current_value is None:
                                 worker_logger.warning(f"Param '{p_name}' not found in current best params. Skipping.")
                                 continue
                             worker_logger.debug(f"[{p_name}] Base value: {current_value} (Type: {type(current_value)}), Mode: {param_custom_config['mode']}")
                             steps_to_try = []
                             final_type_is_float = False

                             if param_custom_config['mode'] == 'Custom' and param_custom_config['steps']:
                                 steps_to_try = param_custom_config['steps']
                                 original_is_float = isinstance(current_value, float); original_is_string = isinstance(current_value, str)
                                 if original_is_string:
                                     try: float(current_value); final_type_is_float = True
                                     except ValueError: final_type_is_float = False
                                 else: final_type_is_float = original_is_float
                                 worker_logger.debug(f"[{p_name}] Using custom steps: {steps_to_try} (Final type intent: {'float' if final_type_is_float else 'int'})")
                             else: # Auto mode
                                 base_step_factor = 0.05; min_float_step = 1e-6
                                 calc_value = current_value; original_is_float = isinstance(current_value, float); original_is_string = isinstance(current_value, str)
                                 if original_is_string:
                                     try: calc_value = float(current_value)
                                     except ValueError: worker_logger.warning(f"[{p_name}] Cannot convert string value '{current_value}' to float. Skipping this param."); continue
                                 calc_is_float = isinstance(calc_value, float); step = None
                                 if calc_is_float:
                                     step_calc = abs(calc_value) * base_step_factor
                                     if step_calc < min_float_step: step = 0.01 if abs(calc_value) < 1 else 0.1
                                     else: step = step_calc
                                 elif isinstance(calc_value, int): step = max(1, int(round(abs(calc_value) * base_step_factor)))
                                 else: worker_logger.error(f"[{p_name}] Unexpected type '{type(calc_value)}' after conversion. Skipping."); continue
                                 if step is None: worker_logger.error(f"[{p_name}] Step calculation failed. Skipping."); continue
                                 auto_steps_raw = [step * 0.5, step, step * 2.0]
                                 final_type_is_float = original_is_float or (original_is_string and isinstance(calc_value, float))
                                 if not final_type_is_float: steps_to_try = sorted(list({max(1, int(round(s))) for s in auto_steps_raw if max(1, int(round(s))) != 0}))
                                 else: steps_to_try = sorted(list({s for s in auto_steps_raw if abs(s) > min_float_step / 10.0}))
                                 worker_logger.debug(f"[{p_name}] Calculated base step: {step}. Auto steps to try: {steps_to_try} (Final type intent: {'float' if final_type_is_float else 'int'})")

                             if not steps_to_try: worker_logger.debug(f"[{p_name}] No valid steps generated. Moving to next param."); continue

                             for step_val in steps_to_try:
                                 if neighbors_added_this_cycle >= MAX_NEIGHBORS_PER_CYCLE: break
                                 for direction in [1, -1]:
                                     if neighbors_added_this_cycle >= MAX_NEIGHBORS_PER_CYCLE: break
                                     neighbor_params = params_to_explore_from.copy(); new_raw_value = None
                                     try:
                                         if 'calc_value' not in locals(): worker_logger.error(f"[{p_name}] Internal error: calc_value not defined. Skipping step."); continue
                                         new_raw_value = calc_value + (direction * step_val)
                                     except TypeError as e: worker_logger.error(f"[{p_name}] TypeError calculating new value: calc={calc_value}({type(calc_value)}), step={step_val}({type(step_val)}). Error: {e}. Skipping step."); continue
                                     if final_type_is_float: neighbor_params[p_name] = float(f"{new_raw_value:.6g}")
                                     else: neighbor_params[p_name] = int(round(new_raw_value))
                                     neighbor_repr = repr(neighbor_params); is_visited = neighbor_repr in visited_params
                                     worker_logger.debug(f"[{p_name}] Trying Step: {direction*step_val:+.4g} -> NewVal: {neighbor_params[p_name]} | Visited: {is_visited}")
                                     if not is_visited:
                                         neighbors.append(neighbor_params); visited_params.add(neighbor_repr); neighbors_added_this_cycle += 1
                                         worker_logger.debug(f"[{p_name}] --> Added neighbor {neighbor_params}. Count this cycle: {neighbors_added_this_cycle}")
                                         if neighbors_added_this_cycle >= MAX_NEIGHBORS_PER_CYCLE: break
                             if neighbors_added_this_cycle >= MAX_NEIGHBORS_PER_CYCLE: break
                        worker_logger.info(f"Explore Cycle {exploration_cycle}: Finished neighbor generation attempts. Total *new* neighbors added this cycle: {neighbors_added_this_cycle}")
                        # --- END: Neighbor Generation Logic ---

                        # --- Handle Neighbor Generation Results ---
                        if neighbors:
                            worker_logger.info(f"Explore Cycle {exploration_cycle}: Added {len(neighbors)} new neighbors to queue.")
                            for p in neighbors: params_q.put(p)
                            # Lấy hàng xóm ĐẦU TIÊN ra để kiểm tra NGAY trong vòng lặp này
                            current_params_explore = params_q.get()
                            total_tests_count += 1 # Tăng bộ đếm vì sắp kiểm tra hàng xóm đầu tiên này
                        else:
                            worker_logger.warning(f"Explore Cycle {exploration_cycle}: Failed to generate any *new* neighbors.")
                            # <<<====== ĐÃ LOẠI BỎ ĐIỀU KIỆN DỪNG SỚM Ở ĐÂY ======>>>
                            # Không còn break; nếu không tạo được hàng xóm mới.
                            # Vòng lặp sẽ tiếp tục, stall_cycle_count sẽ tăng ở lần lặp sau,
                            # và cuối cùng sẽ dừng bởi check stall_cycle_count >= MAX_STALL_CYCLES
                            # Đặt current_params_explore thành None để bỏ qua phần kiểm tra ở dưới cho vòng lặp này
                            current_params_explore = None
                        # --- End Handle Neighbor Generation Results ---
                    # --- End Get Params or Generate Neighbors ---


                    # --- Test the Current Parameter Set ---
                    # Bỏ qua kiểm tra nếu không có tham số nào được lấy ra (ví dụ: khi không tạo được neighbor)
                    if current_params_explore is None:
                         worker_logger.debug(f"Skipping simulation for iteration as no new params were dequeued or generated.")
                         continue # Chuyển sang vòng lặp tiếp theo để tăng stall_cycle_count

                    params_str_short_explore = {k: f'{v:.3g}' if isinstance(v,float) else v for k, v in current_params_explore.items() if k in numeric_param_keys}
                    queue_status(f"Explore Cycle {exploration_cycle}: Thử nghiệm #{total_tests_count} (Stall: {stall_cycle_count}/{MAX_STALL_CYCLES})...")
                    worker_logger.debug(f"Testing Explore set #{total_tests_count}: {params_str_short_explore}")

                    explore_streak, sim_reason_explore, _ = simulate_streak(current_params_explore, start_date, hist_cache, res_map, max_date)

                    if sim_reason_explore == "stopped": finish_reason = "stopped"; break
                    if sim_reason_explore == "time_limit": finish_reason = "time_limit"; break
                    if sim_reason_explore == "prediction_error": queue_log("ERROR", f"Lỗi dự đoán khi kiểm tra bộ #{total_tests_count}. Chuỗi cuối cùng: {max(0, explore_streak)}", tag="ERROR")
                    elif sim_reason_explore == "missing_history": queue_log("ERROR", f"Lỗi thiếu lịch sử khi kiểm tra bộ #{total_tests_count}. Chuỗi cuối cùng: {max(0, explore_streak)}", tag="ERROR")

                    # --- Update Best Results ---
                    if explore_streak > current_best_streak_worker:
                        previous_best = current_best_streak_worker
                        current_best_streak_worker = explore_streak
                        current_best_params_worker = copy.deepcopy(current_params_explore)
                        queue_log("BEST", f"*** New Best Streak: {current_best_streak_worker}! (Explore #{total_tests_count}, Prev Best: {previous_best}) Params: {params_str_short_explore}", tag="BEST")
                        queue_best_update(current_best_params_worker, current_best_streak_worker)
                        worker_logger.info(f"Reset stall count from {stall_cycle_count} to 0 due to new best streak: {current_best_streak_worker}")
                        stall_cycle_count = 0 # Reset stall count on improvement!
                        self._save_training_state(reason="new_best_streak")
                    # --- End Update Best Results ---

                    queue_progress({"current_streak": max(0, explore_streak), "best_streak": current_best_streak_worker})

                    # --- Check Streak Limit ---
                    if streak_limit > 0 and current_best_streak_worker >= streak_limit:
                        worker_logger.info(f"Best streak ({current_best_streak_worker}) meets target ({streak_limit}). Stopping Explore.")
                        finish_reason = "streak_limit_reached"; break
                    # --- End Check Streak Limit ---

                    current_params_explore = None # Reset cho vòng lặp tiếp theo

                # --- End Main Explore Loop ---
            # --- End Explore Mode Logic ---

            # =========================================
            # ===== END OPTIMIZATION LOOP BY MODE =====
            # =========================================

            # --- Final Logging and Cleanup ---
            # ... (Giữ nguyên như phiên bản trước) ...
            worker_logger.info(f"Worker loop finished. Reason: {finish_reason}")
            final_msg = ""; succ_flag = (current_best_streak_worker > 0)
            if finish_reason == "completed": final_msg = "Hoàn tất tối ưu."
            elif finish_reason == "all_sets_tested": final_msg = f"Đã kiểm tra tất cả {total_sets_tested_count} bộ."
            elif finish_reason == "stopped": final_msg = "Đã dừng bởi người dùng."
            elif finish_reason == "time_limit": final_msg = f"Đã dừng do hết giới hạn TG ({time_limit_sec/60:.0f} phút)."
            elif finish_reason == "streak_limit_reached": final_msg = f"Đã dừng do đạt mục tiêu chuỗi ({streak_limit} ngày)."
            elif finish_reason == "no_improvement": final_msg = f"Dừng do không cải thiện chuỗi sau {stall_cycle_count} chu kỳ khám phá."
            elif finish_reason == "no_params": final_msg = "Thuật toán không có tham số số học."; succ_flag = False
            elif finish_reason == "generation_error": final_msg = "Lỗi tạo bộ tham số."; succ_flag = False
            elif finish_reason == "critical_error": final_msg = "Lỗi nghiêm trọng worker."; succ_flag = False
            else: final_msg = f"Kết thúc với lý do không xác định: {finish_reason}"
            if current_best_streak_worker > 0 and current_best_params_worker:
                 if finish_reason not in ["no_params", "generation_error", "critical_error"]:
                      final_msg += f" Chuỗi tốt nhất: {current_best_streak_worker} ngày."
                      params_str_final = {k: f'{v:.4g}' if isinstance(v,float) else v for k, v in current_best_params_worker.items() if k in numeric_param_keys}
                      queue_log("BEST", f"={'='*10} TỐI ƯU KẾT THÚC ({optimization_mode}) {'='*10}", tag="BEST")
                      queue_log("BEST", f"Lý do: {finish_reason}", tag="BEST")
                      queue_log("BEST", f"Chuỗi dài nhất: {current_best_streak_worker}", tag="BEST")
                      queue_log("BEST", f"Với tham số: {params_str_final}", tag="BEST")
                      succ_flag = True
                      try:
                          final_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                          success_dir = target_dir / "success"; success_dir.mkdir(parents=True, exist_ok=True)
                          py_filename = f"trained_{target_data['path'].stem}_streak{current_best_streak_worker}_{final_timestamp}.py"; py_filepath = success_dir / py_filename
                          final_source_code = self._modify_algorithm_source_ast(src_code, cls_name, current_best_params_worker)
                          if final_source_code:
                              py_filepath.write_text(final_source_code, encoding='utf-8')
                              queue_log("BEST", f"Lưu file thuật toán: {py_filepath.name}", tag="BEST")
                          else: queue_log("ERROR", "Lỗi tạo source code cuối cùng để lưu.", tag="ERROR")
                      except Exception as save_e:
                          queue_log("ERROR", f"Lỗi lưu file .py cuối cùng: {save_e}", tag="ERROR")
                          worker_logger.error(f"Error saving best python file: {save_e}", exc_info=True)
            elif not succ_flag:
                 final_msg += " Không tìm thấy chuỗi nào."; queue_log("INFO", "Không tìm thấy chuỗi trúng nào trong quá trình tối ưu.")
            finish_payload_sets_tested = total_sets_tested_count if optimization_mode == "GenerateSets" else None
            queue_finished(final_msg, success=succ_flag, reason=finish_reason, sets_tested=finish_payload_sets_tested)

        except Exception as worker_err:
            # --- Global Error Handling for Worker ---
            finish_reason = "critical_error"
            worker_logger.critical(f"Unhandled exception in worker thread ({optimization_mode}): {worker_err}", exc_info=True)
            queue_error(f"Lỗi worker ({optimization_mode}): {worker_err}")
            queue_finished(f"Lỗi nghiêm trọng worker: {worker_err}", success=False, reason=finish_reason)

    def _validate_training_settings(self):
        """Validates start date and optimization limits."""
        start_d = None; start_s = self.train_start_date_edit.text()
        if not start_s: QMessageBox.warning(self, "Thiếu Ngày", "Vui lòng chọn ngày bắt đầu."); return None, None, None
        try: start_d = datetime.datetime.strptime(start_s, '%d/%m/%Y').date()
        except ValueError: QMessageBox.critical(self, "Lỗi Ngày", "Định dạng ngày bắt đầu sai (dd/MM/yyyy)."); return None, None, None
        if not self.results_data or len(self.results_data) < 2: QMessageBox.critical(self, "Thiếu Dữ Liệu", "Cần ít nhất 2 ngày dữ liệu."); return None, None, None
        min_d, max_d = self.results_data[0]['date'], self.results_data[-1]['date']
        if start_d < min_d or start_d >= max_d: QMessageBox.critical(self, "Lỗi Ngày", f"Ngày bắt đầu phải từ {min_d:%d/%m/%Y} đến trước {max_d:%d/%m/%Y}."); return None, None, None
        try:
            time_limit = self.train_time_limit_spinbox.value(); streak_limit = self.train_streak_limit_spinbox.value()
            if time_limit < 0: time_limit = 0;
            if streak_limit < 0: streak_limit = 0;
            if time_limit == 0 and streak_limit == 0:
                 if QMessageBox.question(self, "Cảnh báo", "Chưa đặt giới hạn thời gian hoặc chuỗi.\nTiếp tục không?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No: return None, None, None
        except Exception as e: QMessageBox.critical(self, "Lỗi Cài Đặt", f"Lỗi đọc giá trị giới hạn:\n{e}"); return None, None, None
        return start_d, time_limit, streak_limit

    def _finalize_custom_steps_config(self, original_params):
        """Validates and finalizes custom steps config for Explore mode."""
        final_config = {}; invalid_params = []; error_details = []
        for name, widgets in self.advanced_train_widgets.items():
            combo = widgets.get('mode_combo'); entry = widgets.get('steps_entry')
            if not combo or not entry: continue
            mode = combo.currentText(); steps_str = entry.text().strip(); parsed = []; is_final_custom = False
            state = self.training_custom_steps.get(name, {'mode': 'Auto', 'steps': [], 'str_value': ''})
            if mode == 'Custom':
                valid_syntax = self._validate_custom_steps_input_bool(steps_str); parse_error = False; error_msg = ""
                if valid_syntax and steps_str:
                    try:
                        orig_val = original_params[name]; is_int = isinstance(orig_val, int); tmp = []
                        for part in steps_str.split(','):
                            part = part.strip();
                            if part: num = float(part);
                            if is_int:
                                if num != int(num): raise ValueError("Bước phải nguyên")
                                tmp.append(int(num))
                            else: tmp.append(num)
                        if tmp: parsed = sorted(list(set(tmp))); is_final_custom = True
                        else: parse_error = True; error_msg = "Danh sách bước trống"
                    except ValueError as ve: parse_error = True; error_msg = f"Lỗi giá trị ({ve})"
                    except Exception as e: parse_error = True; error_msg = f"Lỗi xử lý ({e})"
                elif not valid_syntax and steps_str: parse_error = True; error_msg = "Sai định dạng"
                elif valid_syntax and not steps_str: is_final_custom = True; parsed = []
                if parse_error:
                    invalid_params.append(name); error_details.append(f"{name}: {error_msg}"); state['mode'] = 'Auto'; state['steps'] = []; is_final_custom = False
                    combo.setCurrentText("Auto"); entry.setStyleSheet(""); entry.setToolTip("")
            final_config[name] = {'mode': 'Custom' if is_final_custom else 'Auto', 'steps': parsed if is_final_custom else []}
            log_mode = final_config[name]['mode']; log_steps = f", Steps={final_config[name]['steps']}" if log_mode == 'Custom' and final_config[name]['steps'] else ""
            trainer_logger.info(f"Optimizer Start - Param '{name}': Final Mode={log_mode}{log_steps}")
        return final_config, bool(invalid_params)

    def pause_optimization(self):
        """Pauses the optimization process."""
        if self.training_running and not self.training_paused:
            self.training_pause_event.set(); self.training_paused = True; self.update_training_ui_state()
            self.update_status("Trainer: Đã tạm dừng tối ưu."); self._log_to_display("INFO", "[CONTROL] Tạm dừng.", tag="WARNING"); self._save_training_state(reason="paused")

    def resume_optimization(self):
        """Resumes the paused optimization process."""
        if self.training_running and self.training_paused:
            self.training_pause_event.clear(); self.training_paused = False; self.update_training_ui_state()
            self.update_status("Trainer: Tiếp tục tối ưu..."); self._log_to_display("INFO", "[CONTROL] Tiếp tục.", tag="PROGRESS")

    def stop_optimization(self, force_stop=False):
        """Stops the optimization process."""
        if self.training_running:
            confirmed = force_stop
            if not confirmed:
                reply = QMessageBox.question(self, "Xác Nhận Dừng", "Dừng tối ưu chuỗi?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes: confirmed = True
            if confirmed:
                trainer_logger.info("Stop confirmed. Signalling worker thread."); self._save_training_state(reason="stopped"); self.training_stop_event.set()
                if hasattr(self, 'train_start_button'): self.train_start_button.setEnabled(False)
                if hasattr(self, 'train_resume_button'): self.train_resume_button.setEnabled(False)
                if hasattr(self, 'train_pause_button'): self.train_pause_button.setText("Đang dừng..."); self.train_pause_button.setEnabled(False)
                if hasattr(self, 'train_stop_button'): self.train_stop_button.setEnabled(False)
                self.update_status("Trainer: Đang yêu cầu dừng..."); self._log_to_display("WARNING", "[CONTROL] Yêu cầu dừng...", tag="WARNING")
                if self.training_paused: self.training_pause_event.clear(); trainer_logger.debug("Cleared pause event during stop request.")

    def update_training_ui_state(self):
        """Updates the enable/disable state of optimization UI elements."""
        start_enabled, resume_enabled, pause_enabled, stop_enabled = False, False, False, False; pause_text = "⏸Tạm dừng"; pause_callback = self.pause_optimization; pause_style_obj_name = "WarningButton"
        is_generate_mode = False;
        if hasattr(self, 'param_gen_enable_checkbox'): is_generate_mode = self.param_gen_enable_checkbox.isChecked()
        if self.training_running:
            start_enabled = False; resume_enabled = False; stop_enabled = True
            if self.training_paused: pause_enabled = True; pause_text = "⏯Tiếp tục"; pause_callback = self.resume_optimization; pause_style_obj_name = "AccentButton"
            else: pause_enabled = True; pause_text = "⏸Tạm dừng"; pause_callback = self.pause_optimization; pause_style_obj_name = "WarningButton"
        else:
            start_enabled = (self.selected_algorithm_for_train is not None); resume_enabled = self.can_resume_explore; stop_enabled = False; pause_enabled = False; pause_text = "Tạm dừng"; pause_callback = self.pause_optimization; pause_style_obj_name = "WarningButton"
            if hasattr(self,'train_status_label'): self.train_status_label.setText("Trạng thái: Chờ"); self.train_status_label.setStyleSheet("color: #6c757d;")
            if hasattr(self,'train_streak_label'): self.train_streak_label.setText(f"Chuỗi: 0 / Best: {self.current_best_streak}")
            if hasattr(self,'train_time_remaining_label'): self.train_time_remaining_label.setText("--:--:--"); self.train_time_remaining_label.setVisible(False)
            if hasattr(self,'train_time_static_label'): self.train_time_static_label.setVisible(False)
            if self.training_timer.isActive(): self.training_timer.stop()
            if self.display_timer.isActive(): self.display_timer.stop()
        if hasattr(self,'train_start_button'): self.train_start_button.setEnabled(start_enabled)
        if hasattr(self,'train_resume_button'): self.train_resume_button.setEnabled(resume_enabled)
        if hasattr(self,'train_stop_button'): self.train_stop_button.setEnabled(stop_enabled)
        if hasattr(self,'train_pause_button'):
            self.train_pause_button.setEnabled(pause_enabled); self.train_pause_button.setText(pause_text)
            if self.train_pause_button.objectName() != pause_style_obj_name: self.train_pause_button.setObjectName(pause_style_obj_name); self.train_pause_button.style().unpolish(self.train_pause_button); self.train_pause_button.style().polish(self.train_pause_button)
            try: self.train_pause_button.clicked.disconnect()
            except TypeError: pass
            self.train_pause_button.clicked.connect(pause_callback)
        settings_enabled = not self.training_running
        if hasattr(self,'train_start_date_edit'): self.train_start_date_edit.setReadOnly(not settings_enabled)
        if hasattr(self,'train_start_date_button'): self.train_start_date_button.setEnabled(settings_enabled)
        if hasattr(self,'train_time_limit_spinbox'): self.train_time_limit_spinbox.setEnabled(settings_enabled)
        if hasattr(self,'train_streak_limit_spinbox'): self.train_streak_limit_spinbox.setEnabled(settings_enabled)
        for chk in self.combination_selection_checkboxes.values(): chk.setEnabled(settings_enabled)
        if hasattr(self, 'param_gen_enable_checkbox'):
            self.param_gen_enable_checkbox.setEnabled(settings_enabled); gen_widgets_enabled = settings_enabled and self.param_gen_enable_checkbox.isChecked()
            self.param_generation_widgets['count'].setEnabled(gen_widgets_enabled); self.param_generation_widgets['mode_random'].setEnabled(gen_widgets_enabled); self.param_generation_widgets['mode_seq'].setEnabled(gen_widgets_enabled)
        manual_tuning_enabled = settings_enabled and not is_generate_mode
        if hasattr(self, 'advanced_train_groupbox'):
            self.advanced_train_groupbox.setEnabled(manual_tuning_enabled)
            for widgets in self.advanced_train_widgets.values():
                combo = widgets.get('mode_combo'); entry = widgets.get('steps_entry')
                if combo: combo.setEnabled(manual_tuning_enabled)
                is_custom_mode = combo.currentText() == 'Custom' if combo else False
                if entry: entry.setEnabled(manual_tuning_enabled and is_custom_mode)

    def _update_training_timer_display(self):
        """Updates the remaining time label."""
        if not self.training_running or not hasattr(self,'train_time_remaining_label') or self.train_time_limit_sec <= 0:
            if self.display_timer.isActive(): self.display_timer.stop()
            if hasattr(self,'train_time_remaining_label'): self.train_time_remaining_label.setVisible(False)
            if hasattr(self,'train_time_static_label'): self.train_time_static_label.setVisible(False); return
        if hasattr(self,'train_time_remaining_label'): self.train_time_remaining_label.setVisible(True)
        if hasattr(self,'train_time_static_label'): self.train_time_static_label.setVisible(True)
        elapsed = time.time() - self.train_start_time; left = max(0, self.train_time_limit_sec - elapsed)
        time_str = time.strftime('%H:%M:%S' if left >= 3600 else '%M:%S', time.gmtime(left))
        if hasattr(self,'train_time_remaining_label') and self.train_time_remaining_label.isVisible(): self.train_time_remaining_label.setText(time_str)

    def _check_training_queue(self):
        """Processes messages from the optimization worker thread queue."""
        try:
            processed = False
            while not self.training_queue.empty():
                processed = True; message = self.training_queue.get_nowait(); msg_type = message.get("type"); payload = message.get("payload")
                if msg_type == "log": level = payload.get("level", "INFO"); text = payload.get("text", ""); tag = payload.get("tag"); self._log_to_display(level, text, tag)
                elif msg_type == "status": self.update_status_label(payload)
                elif msg_type == "progress": self._update_progress_display(payload)
                elif msg_type == "best_update": self._update_best_state(payload)
                elif msg_type == "finished": self._handle_training_finished(payload); return
                elif msg_type == "error": self._handle_training_error(payload); return
                else: trainer_logger.warning(f"Unknown message type in queue: {msg_type}")
        except queue.Empty: pass
        except Exception as e: trainer_logger.error(f"Error processing worker queue: {e}", exc_info=True); self._handle_training_error(f"Lỗi xử lý queue: {e}"); return

    def update_status_label(self, text):
        """Updates the status label in the progress area on the Run/Optimize tab."""
        if hasattr(self, 'train_status_label'):
             self.train_status_label.setWordWrap(True); display_text = text if text.startswith("Trạng thái:") else f"Trạng thái: {text}"; self.train_status_label.setText(display_text)

    def _update_progress_display(self, payload):
        """Updates progress bar and labels based on worker payload."""
        mode = payload.get('mode', 'Explore')
        if mode == 'GenerateSets':
            current_set = payload.get('current_set_idx', 0); total_sets = payload.get('total_sets', 1); current_streak_for_set = payload.get('current_streak', 0); best_streak_so_far = payload.get('best_streak', self.current_best_streak)
            percent = (current_set / total_sets * 100) if total_sets > 0 else 0; progress_text = f"{percent:.0f}% ({current_set}/{total_sets} bộ)"
            if hasattr(self, 'train_progressbar'): self.train_progressbar.setValue(int(percent))
            if hasattr(self, 'train_progress_label'): self.train_progress_label.setText(f"{percent:.0f}%")
            if hasattr(self, 'train_streak_label'): self.train_streak_label.setText(f"Bộ hiện tại: {current_streak_for_set} / Best: {best_streak_so_far}")
        else:
            current_day = payload.get('current_day_idx', 0); total_days = payload.get('total_sim_days', 1); current_streak = payload.get('current_streak', 0); best_streak = payload.get('best_streak', self.current_best_streak)
            display_percent = 0
            if self.train_time_limit_sec > 0: time_elapsed = time.time() - self.train_start_time; percent_time = (time_elapsed / self.train_time_limit_sec * 100); display_percent = max(0, min(100, percent_time))
            elif self.train_streak_limit > 0: display_percent = max(0, min(100, (best_streak / self.train_streak_limit * 100)))
            else: display_percent = 0
            if hasattr(self, 'train_progressbar'): self.train_progressbar.setValue(int(display_percent))
            if hasattr(self, 'train_progress_label'): self.train_progress_label.setText(f"{display_percent:.0f}%")
            if hasattr(self, 'train_streak_label'): self.train_streak_label.setText(f"Chuỗi: {current_streak} / Best: {best_streak}")

    def _update_best_state(self, payload):
        """Updates the application's tracked current best parameters and streak."""
        new_best_params = payload.get("params"); new_best_streak = payload.get("streak", 0)
        if new_best_params is not None and new_best_streak >= self.current_best_streak:
             if new_best_streak > self.current_best_streak: trainer_logger.info(f"UI Updated Best: Streak {self.current_best_streak} -> {new_best_streak}")
             elif new_best_streak == self.current_best_streak: trainer_logger.debug(f"UI Updated Best: Params changed for streak {new_best_streak}")
             self.current_best_params = copy.deepcopy(new_best_params); self.current_best_streak = new_best_streak
             if hasattr(self, 'train_streak_label'):
                 current_label_text = self.train_streak_label.text(); current_s_match = re.search(r'^(.*?:\s*\d+)\s*/', current_label_text)
                 current_s_text = current_s_match.group(1) if current_s_match else "Chuỗi: 0"; self.train_streak_label.setText(f"{current_s_text} / Best: {self.current_best_streak}")
        else: trainer_logger.debug(f"Ignored best update: Payload streak {new_best_streak} not better than {self.current_best_streak} or no params.")

    def _handle_training_finished(self, payload):
        """Handles the 'finished' signal from the worker."""
        trainer_logger.info("Optimization finished signal received.");
        if self.training_timer.isActive(): self.training_timer.stop();
        if self.display_timer.isActive(): self.display_timer.stop();
        self.training_running = False; self.training_paused = False; final_message = payload.get("message", "Hoàn tất."); success = payload.get("success", False); reason = payload.get("reason", "completed")
        if reason not in ["stopped", "paused", "critical_error", "load_error", "generation_error"]: self._save_training_state(reason=f"finished_{reason}")
        log_level, log_tag, msg_func, msg_title = "INFO", "[KẾT THÚC]", QMessageBox.information, "Tối Ưu Kết Thúc"; display_msg = final_message
        if success: log_level, log_tag = "BEST", "[HOÀN TẤT]"; msg_title = "Tối Ưu Hoàn Tất"
        elif reason == "time_limit": log_level, log_tag = "INFO", "[HẾT GIỜ]"; t_limit = str(self.train_time_limit_spinbox.value()) if hasattr(self,'train_time_limit_spinbox') else '?'; display_msg=f"Dừng do hết TG ({t_limit} phút)."; msg_title = "Hết Thời Gian"
        elif reason == "streak_limit_reached": log_level, log_tag = "BEST", "[ĐẠT MỤC TIÊU]"; s_limit=str(self.train_streak_limit_spinbox.value()) if hasattr(self,'train_streak_limit_spinbox') else '?'; display_msg=f"Dừng do đạt mục tiêu chuỗi ({s_limit} ngày)."; msg_title = "Đạt Mục Tiêu"
        elif reason == "stopped": log_level, log_tag = "WARNING", "[ĐÃ DỪNG]"; msg_func = QMessageBox.warning; display_msg="Đã dừng bởi người dùng."; msg_title = "Đã Dừng"
        elif reason == "no_improvement": log_level, log_tag = "INFO", "[KẾT THÚC]"; display_msg="Dừng do không cải thiện chuỗi."; msg_title = "Không Cải Thiện"
        elif reason == "all_sets_tested": log_level = "BEST" if self.current_best_streak > 0 else "INFO"; log_tag = "[HOÀN TẤT]" if self.current_best_streak > 0 else "[KẾT THÚC]"; display_msg = f"Đã kiểm tra tất cả {payload.get('sets_tested', '?')} bộ."; msg_title = "Hoàn Tất Kiểm Tra"
        elif reason == "no_params": log_level, log_tag = "INFO", "[KẾT THÚC]"; display_msg = "Không có tham số để tối ưu."; msg_title = "Không Có Tham Số"
        elif reason in ["resume_error", "initial_test_error", "load_error", "critical_error", "generation_error"]: log_level, log_tag, msg_func, msg_title = "ERROR", "[LỖI]", QMessageBox.critical, "Lỗi Tối Ưu"
        else: log_level, log_tag, msg_func, msg_title = "ERROR", "[LỖI]", QMessageBox.critical, "Lỗi Không Xác Định"; display_msg = f"Quá trình kết thúc lý do không rõ: {reason}\nMsg: {final_message}"
        if self.current_best_streak > 0 and self.current_best_params and reason not in ["no_params", "resume_error", "initial_test_error", "load_error", "critical_error", "generation_error"]: display_msg += f"\n\nChuỗi tốt nhất: {self.current_best_streak} ngày.";
        if reason not in ["stopped", "paused"]: display_msg += " Kết quả/trạng thái đã lưu."
        self.update_status(f"Tối ưu Kết thúc: {display_msg.splitlines()[0]}"); self._log_to_display(log_level, f"{log_tag} {display_msg}", tag=log_level.upper()); msg_func(self, msg_title, display_msg)
        if reason not in ["stopped", "critical_error", "load_error", "generation_error"]:
            if hasattr(self,'train_progressbar'): self.train_progressbar.setValue(100);
            if hasattr(self,'train_progress_label'): self.train_progress_label.setText("100%")
        self.check_resume_possibility(); self.update_training_ui_state(); self.training_thread = None

    def _handle_training_error(self, error_text):
        """Handles critical errors from the worker or queue processing."""
        trainer_logger.error(f"Handling optimization error: {error_text}");
        if self.training_timer.isActive(): self.training_timer.stop();
        if self.display_timer.isActive(): self.display_timer.stop();
        self._log_to_display("ERROR", f"[LỖI LUỒNG WORKER] {error_text}", tag="ERROR"); QMessageBox.critical(self, "Lỗi Worker Tối Ưu", f"Lỗi nghiêm trọng worker:\n\n{error_text}")
        self.training_running = False; self.training_paused = False; self.update_training_ui_state(); self.training_thread = None; self.update_status("Lỗi nghiêm trọng.")

    def _log_to_display(self, level, text, tag=None):
        """Appends a log message to the optimization log QTextEdit."""
        try:
            log_method = getattr(trainer_logger, level.lower(), trainer_logger.info); log_method(f"[OptimizerUI] {text}")
            if not hasattr(self, 'train_log_text'): return
            if not hasattr(self, 'log_formats') or not self.log_formats: trainer_logger.warning("Log formats not initialized."); self._setup_log_formats()
            display_tag = tag if tag and tag in self.log_formats else level.upper();
            if display_tag == "CRITICAL": display_tag = "ERROR";
            fmt = self.log_formats.get(display_tag, self.log_formats.get("INFO", QtGui.QTextCharFormat()))
            timestamp = datetime.datetime.now().strftime("%H:%M:%S"); full_log_line = f"{timestamp} [{level.upper()}] {text}\n"
            cursor = self.train_log_text.textCursor(); cursor.movePosition(QTextCursor.End); cursor.insertText(full_log_line, fmt); self.train_log_text.ensureCursorVisible()
        except Exception as e: trainer_logger.error(f"!!! CRITICAL Error in _log_to_display: {e}", exc_info=True); print(f"!!! LOG DISPLAY ERROR: {level} - {text} -> {e}", file=sys.stderr)

    def _clear_training_log_display(self):
        """Clears the log text display area."""
        if hasattr(self, 'train_log_text'): self.train_log_text.clear()

    def check_resume_possibility(self):
        """Checks if resuming the 'Explore' mode is possible."""
        target = self.selected_algorithm_for_train; can_resume = False
        allow_resume_check = (target and target in self.loaded_algorithms and not self.training_running and hasattr(self, 'param_gen_enable_checkbox') and not self.param_gen_enable_checkbox.isChecked())
        if allow_resume_check:
            algo_data = self.loaded_algorithms[target]; algo_stem = algo_data['path'].stem; train_dir = self.training_dir / algo_stem
            latest_file, latest_data = self.find_latest_training_state(train_dir, algo_stem)
            if latest_file and latest_data: can_resume = True; trainer_logger.debug(f"Resume possible for Explore on {target} using: {latest_file.name}")
            else: trainer_logger.debug(f"Resume not possible for Explore on {target} (no state file/wrong mode).")
        else:
             reason = "No algorithm" if not target else "Running" if self.training_running else "UI not ready" if not hasattr(self, 'param_gen_enable_checkbox') else "Generate mode active" if self.param_gen_enable_checkbox.isChecked() else "Unknown"
             trainer_logger.debug(f"Resume check skipped: {reason}")
        self.can_resume_explore = can_resume
        if not self.training_running: self.update_training_ui_state()

    def _clear_calculation_cache(self):
        """Clears temporary files from the calculation/cache directory."""
        cleared_count, error_count = 0, 0; cache_dir = self.calculate_dir
        trainer_logger.info(f"Attempting to clear cache directory: {cache_dir}")
        if not cache_dir.exists(): trainer_logger.info("Cache directory does not exist."); return
        if not cache_dir.is_dir(): trainer_logger.error(f"Cache path {cache_dir} is not a directory."); return
        try:
            for item in cache_dir.iterdir():
                try:
                    if item.is_file(): item.unlink(); cleared_count += 1
                    elif item.is_dir(): shutil.rmtree(item); cleared_count += 1
                except Exception as e: trainer_logger.error(f"Error removing cache item {item.name}: {e}"); error_count += 1
            if error_count > 0: trainer_logger.warning(f"Cache clear completed with {error_count} errors. Removed {cleared_count} items.")
            else: trainer_logger.info(f"Cache clear successful. Removed {cleared_count} items.")
        except Exception as e: trainer_logger.error(f"Error accessing cache directory {cache_dir}: {e}")

    def open_training_folder(self):
        """Opens the specific training directory for the selected algorithm."""
        target_path = None
        if self.selected_algorithm_for_train and self.selected_algorithm_for_train in self.loaded_algorithms:
            algo_stem = self.loaded_algorithms[self.selected_algorithm_for_train]['path'].stem; target_path = self.training_dir / algo_stem; trainer_logger.info(f"Opening specific training folder: {target_path}")
        else: target_path = self.training_dir; QMessageBox.information(self, "Thông Báo", f"Chưa chọn thuật toán.\nMở thư mục tối ưu chính:\n{target_path}"); trainer_logger.info(f"Opening main training folder: {target_path}")
        if not target_path: QMessageBox.critical(self, "Lỗi", "Không thể xác định đường dẫn."); return
        try: target_path.mkdir(parents=True, exist_ok=True)
        except OSError as e: QMessageBox.critical(self, "Lỗi Tạo Thư Mục", f"Không thể tạo/truy cập thư mục:\n{target_path}\n\nLỗi: {e}"); return
        url = QtCore.QUrl.fromLocalFile(str(target_path.resolve()))
        if not QtGui.QDesktopServices.openUrl(url): QMessageBox.critical(self, "Lỗi Mở Thư Mục", f"Không thể mở thư mục:\n{target_path}"); trainer_logger.error(f"QDesktopServices.openUrl failed for path: {target_path}")

    def update_status(self, message: str):
        """Updates the status bar label with styled text."""
        status_type="info"; lower_msg=message.lower()
        if any(x in lower_msg for x in ["lỗi", "fail", "thất bại", "error", "critical", "không thể"]): status_type="error"
        elif any(x in lower_msg for x in ["success", "thành công", "hoàn tất", "đã lưu", "tìm thấy"]): status_type="success"
        elif any(x in lower_msg for x in ["warn", "cảnh báo", "warning", "tạm dừng"]): status_type="warning"
        if hasattr(self,'status_bar_label'):
             display_text = message if message.startswith("Trạng thái:") else f"Trạng thái: {message}"; self.status_bar_label.setText(display_text); self.status_bar_label.setProperty("status", status_type)
             self.status_bar_label.style().unpolish(self.status_bar_label); self.status_bar_label.style().polish(self.status_bar_label); trainer_logger.info(f"Status Update ({status_type}): {message}")
        else: trainer_logger.info(f"Status Update (No Label) ({status_type}): {message}")

    def _modify_algorithm_source_ast(self, source_code, target_class_name, new_params):
        """Modifies algorithm source using AST."""
        modifier_logger.debug(f"AST Modify: Class='{target_class_name}', Params={list(new_params.keys())}")
        try: tree = ast.parse(source_code)
        except SyntaxError as e: modifier_logger.error(f"AST Parse Error: {e}"); return None
        class _SourceModifier(ast.NodeTransformer):
            def __init__(self, class_to_modify, params_to_update): self.target_class = class_to_modify; self.params_to_update = params_to_update; self.in_target_init = False; self.params_modified = False; self.imports_modified = False; self.current_class_name = None; super().__init__()
            def visit_ImportFrom(self, node):
                if node.level > 0:
                    original_module = node.module;
                    if node.module == 'base': node.module = 'algorithms.base'; node.level = 0; self.imports_modified = True; modifier_logger.debug(f"AST Fix Import: '.{original_module}' -> '{node.module}'")
                    elif node.module: node.module = f"algorithms.{node.module}"; node.level = 0; self.imports_modified = True; modifier_logger.debug(f"AST Fix Import: '.{original_module}' -> '{node.module}'")
                    else: modifier_logger.warning("AST Fix Import: Skipped 'from . import ...'.")
                return self.generic_visit(node)
            def visit_ClassDef(self, node): original_class = self.current_class_name; self.current_class_name = node.name; self.generic_visit(node); self.current_class_name = original_class; return node
            def visit_FunctionDef(self, node):
                if node.name == '__init__' and self.current_class_name == self.target_class: self.in_target_init = True; node.body = [self.visit(child) for child in node.body]; self.in_target_init = False
                else: self.generic_visit(node)
                return node
            def visit_Assign(self, node):
                if self.in_target_init and len(node.targets) == 1:
                    target = node.targets[0];
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self' and target.attr == 'config': node.value = self.visit(node.value); return node
                return self.generic_visit(node)
            def visit_Dict(self, node):
                if not self.in_target_init: return self.generic_visit(node)
                param_key_index = -1; param_value_node = None; is_config_dict = False
                try:
                    if node.keys:
                        key_names = set();
                        for k in node.keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str): key_names.add(k.value)
                            elif hasattr(ast, 'Str') and isinstance(k, ast.Str): key_names.add(k.s)
                        if 'description' in key_names and 'parameters' in key_names: is_config_dict = True
                        for i, key_node in enumerate(node.keys):
                            is_param_key = (isinstance(key_node, ast.Constant) and key_node.value == 'parameters') or (hasattr(ast, 'Str') and isinstance(key_node, ast.Str) and key_node.s == 'parameters')
                            if is_param_key: param_key_index = i; param_value_node = node.values[i]; break
                except Exception as e_dict_check: modifier_logger.warning(f"AST Warn: Error checking dict keys: {e_dict_check}"); return self.generic_visit(node)
                if is_config_dict and param_key_index != -1 and isinstance(param_value_node, ast.Dict):
                     modifier_logger.debug("AST Modifying 'parameters' sub-dictionary."); new_keys = []; new_values = []; modified_in_subdict = False; original_param_nodes = {}
                     if param_value_node.keys:
                         for k_node, v_node in zip(param_value_node.keys, param_value_node.values):
                             param_name_str = None;
                             if isinstance(k_node, ast.Constant) and isinstance(k_node.value, str): param_name_str = k_node.value
                             elif hasattr(ast, 'Str') and isinstance(k_node, ast.Str): param_name_str = k_node.s
                             if param_name_str: original_param_nodes[param_name_str] = (k_node, v_node)
                             else: new_keys.append(k_node); new_values.append(v_node)
                     updated_params = set()
                     for param_name, new_value in self.params_to_update.items():
                         if param_name in original_param_nodes:
                             p_key_node, _ = original_param_nodes[param_name]; new_val_node = None
                             if sys.version_info >= (3, 8):
                                 if isinstance(new_value, (int, float)): new_val_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=abs(new_value))) if new_value < 0 else ast.Constant(value=new_value)
                                 elif isinstance(new_value, str): new_val_node = ast.Constant(value=new_value)
                                 elif isinstance(new_value, bool): new_val_node = ast.Constant(value=new_value)
                                 elif new_value is None: new_val_node = ast.Constant(value=None)
                             else:
                                 if isinstance(new_value, (int, float)): new_val_node = ast.Num(n=new_value)
                                 elif isinstance(new_value, str): new_val_node = ast.Str(s=new_value)
                                 elif isinstance(new_value, bool): new_val_node = ast.NameConstant(value=new_value)
                                 elif new_value is None: new_val_node = ast.NameConstant(value=None)
                             if new_val_node is not None: new_keys.append(p_key_node); new_values.append(new_val_node); updated_params.add(param_name); modified_in_subdict = True
                             else: p_key_node_orig, p_val_node_orig = original_param_nodes[param_name]; new_keys.append(p_key_node_orig); new_values.append(p_val_node_orig); modifier_logger.warning(f"AST Skipped '{param_name}': Type {type(new_value)}")
                         else: modifier_logger.warning(f"AST Param '{param_name}' not in original dict.")
                     for name, (k_node, v_node) in original_param_nodes.items():
                          if name not in updated_params: new_keys.append(k_node); new_values.append(v_node)
                     param_value_node.keys = new_keys; param_value_node.values = new_values
                     if modified_in_subdict: self.params_modified = True; modifier_logger.debug("AST Updated 'parameters' sub-dict.")
                return self.generic_visit(node)
        modifier = _SourceModifier(target_class_name, new_params); modified_tree = modifier.visit(tree); ast.fix_missing_locations(modified_tree)
        if modifier.params_modified or modifier.imports_modified: log_parts = [];
        if modifier.params_modified: log_parts.append("Params updated");
        if modifier.imports_modified: log_parts.append("Imports fixed"); modifier_logger.info(f"AST Mod Summary for {target_class_name}: {', '.join(log_parts)}.")
        else: modifier_logger.warning(f"AST Mod: No changes for {target_class_name}.")
        try:
            if sys.version_info >= (3, 9): modified_code = ast.unparse(modified_tree)
            elif HAS_ASTOR: modified_code = astor.to_source(modified_tree)
            else: modifier_logger.critical("AST Unparse Error: Astor missing for Py < 3.9."); return None
            return modified_code
        except Exception as e: modifier_logger.error(f"AST Unparse Error: {e}", exc_info=True); return None

    def _import_and_instantiate_temp_algo(self, temp_filepath, temp_module_name, class_name_hint):
        """Imports a temporary algorithm module, finds the class, and instantiates it."""
        import_logger.debug(f"Importing temporary algo: Module='{temp_module_name}', File='{temp_filepath}'"); instance = None; module_obj = None
        if temp_module_name in sys.modules:
            try: del sys.modules[temp_module_name]; import_logger.debug(f"Removed cache for: {temp_module_name}")
            except KeyError: pass
        try:
            spec = util.spec_from_file_location(temp_module_name, temp_filepath);
            if not spec or not spec.loader: raise ImportError(f"No spec/loader for {temp_filepath}")
            module_obj = util.module_from_spec(spec);
            if not module_obj: raise ImportError(f"module_from_spec failed for {temp_module_name}")
            sys.modules[temp_module_name] = module_obj; import_logger.debug(f"Executing module {temp_module_name}..."); spec.loader.exec_module(module_obj); import_logger.debug(f"Module {temp_module_name} executed.")
            temp_class = None;
            if class_name_hint: temp_class = getattr(module_obj, class_name_hint, None);
            if not (inspect.isclass(temp_class) and issubclass(temp_class, BaseAlgorithm) and temp_class is not BaseAlgorithm): temp_class = None
            if temp_class is None:
                 for name, obj in inspect.getmembers(module_obj):
                     if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == temp_module_name: temp_class = obj; import_logger.debug(f"Found class by search: '{name}'"); break
            if not temp_class or not issubclass(temp_class, BaseAlgorithm):
                 if temp_module_name in sys.modules: del sys.modules[temp_module_name]; raise TypeError(f"No valid BaseAlgorithm subclass in {temp_module_name}.")
            import_logger.debug(f"Instantiating {temp_class.__name__}..."); data_copy = copy.deepcopy(self.results_data) if self.results_data else []; instance = temp_class(data_results_list=data_copy, cache_dir=self.calculate_dir); import_logger.debug(f"Instantiated {temp_class.__name__}"); return instance
        except Exception as e:
             import_logger.error(f"Failed import/instantiate {temp_filepath}: {e}", exc_info=True);
             if temp_module_name and temp_module_name in sys.modules:
                 try: del sys.modules[temp_module_name]
                 except KeyError: pass
             return None

    def extract_numbers_from_result_dict(self, result_dict: dict) -> set:
        """Extracts 2-digit lottery numbers from a result dictionary."""
        numbers = set(); keys_to_ignore = {'date', '_id', 'source', 'day_of_week', 'sign', 'created_at', 'updated_at', 'province_name', 'province_id', 'day', 'month', 'year'}
        if not isinstance(result_dict, dict): return numbers
        for key, value in result_dict.items():
            if key in keys_to_ignore or (isinstance(key, str) and key.startswith('_')): continue
            values_to_check = [];
            if isinstance(value, (list, tuple)): values_to_check.extend(value)
            elif value is not None: values_to_check.append(value)
            for item in values_to_check:
                if item is None: continue
                try:
                    s_item = str(item).strip(); num = -1
                    if len(s_item) >= 2 and s_item[-2:].isdigit(): num = int(s_item[-2:])
                    elif len(s_item) == 2 and s_item.isdigit(): num = int(s_item)
                    elif len(s_item) == 1 and s_item.isdigit(): num = int(s_item)
                    if 0 <= num <= 99: numbers.add(num)
                except (ValueError, TypeError): pass
        return numbers

    def combine_algorithm_scores(self, intermediate_results: dict) -> dict:
        """Combines prediction scores from multiple algorithms."""
        if not intermediate_results: return {f"{i:02d}": 100.0 for i in range(100)}
        BASE_SCORE = 100.0; combined_deltas = {f"{i:02d}": 0.0 for i in range(100)}; valid_algo_count = 0
        for algo_name, raw_scores in intermediate_results.items():
            if not isinstance(raw_scores, dict) or not raw_scores: continue
            valid_algo_count += 1
            for num_str, delta_or_score in raw_scores.items():
                 if isinstance(num_str, str) and len(num_str) == 2 and num_str.isdigit() and isinstance(delta_or_score, (int, float)):
                      try: combined_deltas[num_str] += float(delta_or_score)
                      except (ValueError, TypeError, KeyError): pass
        if valid_algo_count == 0: return {num: BASE_SCORE for num in combined_deltas.keys()}
        final_scores = {num: round(BASE_SCORE + delta, 4) for num, delta in combined_deltas.items()}
        return final_scores

    def show_calendar_dialog_qt(self, target_line_edit: QLineEdit, callback=None):
        """Shows a calendar dialog to select a date."""
        if not self.results_data or len(self.results_data) < 2: QMessageBox.warning(self, "Thiếu Dữ Liệu", "Cần ít nhất 2 ngày dữ liệu."); return
        min_date_dt = self.results_data[0]['date']; max_date_dt = self.results_data[-1]['date'] - datetime.timedelta(days=1)
        if max_date_dt < min_date_dt: QMessageBox.warning(self, "Không Đủ Dữ Liệu", f"Cần dữ liệu đến {(min_date_dt + datetime.timedelta(days=1)):%d/%m/%Y})."); return
        min_qdate = QDate(min_date_dt.year, min_date_dt.month, min_date_dt.day); max_qdate = QDate(max_date_dt.year, max_date_dt.month, max_date_dt.day)
        current_text = target_line_edit.text(); current_qdate = min_qdate
        try:
            parsed_dt = datetime.datetime.strptime(current_text, '%d/%m/%Y').date(); parsed_qdate = QDate(parsed_dt.year, parsed_dt.month, parsed_dt.day)
            if min_qdate <= parsed_qdate <= max_qdate: current_qdate = parsed_qdate
        except ValueError: pass
        dialog = QDialog(self); dialog.setWindowTitle("Chọn Ngày Bắt Đầu Tối Ưu"); dialog.setModal(True)
        layout = QVBoxLayout(dialog); calendar = QCalendarWidget(); calendar.setGridVisible(True); calendar.setMinimumDate(min_qdate); calendar.setMaximumDate(max_qdate); calendar.setSelectedDate(current_qdate)
        calendar.setStyleSheet("QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #EAEAEA; border: 1px solid #D0D0D0; } QCalendarWidget QToolButton { color: black; background-color: #F0F0F0; border: 1px solid #C0C0C0; padding: 3px; margin: 1px;} QCalendarWidget QToolButton:hover { background-color: #E0E0E0; } QCalendarWidget QMenu { background-color: white; } QCalendarWidget QSpinBox { padding: 2px; }")
        try: calendar.setMinimumWidth(max(450, int(calendar.sizeHint().width() * 1.1))); calendar.setMinimumHeight(max(300, int(calendar.sizeHint().height())))
        except Exception: dialog.setMinimumSize(500, 350)
        layout.addWidget(calendar); button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel); button_box.accepted.connect(dialog.accept); button_box.rejected.connect(dialog.reject); layout.addWidget(button_box)
        if dialog.exec_() == QDialog.Accepted:
            selected_qdate = calendar.selectedDate(); target_line_edit.setText(selected_qdate.toString("dd/MM/yyyy"))
            if callback:
                 try: callback()
                 except Exception as cb_e: trainer_logger.error(f"Calendar callback error: {cb_e}")

    def closeEvent(self, event):
        """Handle window close event."""
        trainer_logger.info("Close event triggered.")
        if self.training_running:
            reply = QMessageBox.question(self, 'Xác Nhận Thoát', 'Tối ưu đang chạy. Thoát?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                trainer_logger.info("User confirmed exit. Stopping optimization...")
                try: self.stop_optimization(force_stop=True); time.sleep(0.1)
                except Exception as e: trainer_logger.error(f"Error stopping optimization on close: {e}")
                event.accept()
            else: trainer_logger.info("User cancelled exit."); event.ignore(); return
        if hasattr(self,'training_timer') and self.training_timer.isActive(): self.training_timer.stop()
        if hasattr(self,'display_timer') and self.display_timer.isActive(): self.display_timer.stop()
        trainer_logger.info("Proceeding with application shutdown."); logging.shutdown(); event.accept()

def main_optimizer():
    """Initializes and runs the Optimization Application."""
    try:
        if hasattr(QtCore.Qt,'AA_EnableHighDpiScaling'): QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        if hasattr(QtCore.Qt,'AA_UseHighDpiPixmaps'): QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    except Exception as e: print(f"Warning: Could not set High DPI attributes: {e}")

    app = QApplication(sys.argv); app.setApplicationName("LotteryOptimizer")
    try:
        trainer_logger.info("Creating TrainingApp (Optimizer UI)...")
        main_window = TrainingApp()
        trainer_logger.info("Starting Qt event loop...")
        exit_code = app.exec_()
        trainer_logger.info(f"Qt event loop finished with exit code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        trainer_logger.critical(f"Unhandled critical error in application: {e}", exc_info=True); traceback.print_exc()
        try: QMessageBox.critical(None, "Lỗi Nghiêm Trọng", f"Lỗi không mong muốn:\n\n{e}\n\nỨng dụng sẽ đóng.")
        except: print(f"CRITICAL ERROR: {e}\nApp will close.", file=sys.stderr)
        sys.exit(1)
    finally: trainer_logger.info("Application shutdown sequence."); logging.shutdown()

if __name__ == "__main__":
    print("="*20 + " Lottery Optimizer Starting " + "="*20)
    print(f"Python Version: {sys.version.split()[0]}")
    base_app_dir = Path(__file__).parent.resolve(); print(f"App Base Dir: {base_app_dir}")
    print(f"PyQt5 Available: {HAS_PYQT5}")
    main_optimizer()
    print("="*20 + " Lottery Optimizer Finished " + "="*20)
