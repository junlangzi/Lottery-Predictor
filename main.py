# Version: 6.0.0
# Date: 04/10/2026
# Update: Tái cấu trúc toàn bộ code<br>Thay đổi nâng cấp giao diện<br>Hỗ trợ sử dụng thuật toán tối ưu từ chương trình Thiên cơ số Studio PC pro<br>Tối ưu lại quy trình update, sync data

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
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
import math
import base64
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat


import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFormLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QGroupBox,
        QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QScrollArea, QTextEdit, QProgressBar,
        QListWidget, QListWidgetItem, QDialog, QCalendarWidget, QMessageBox,
        QFileDialog, QStatusBar, QSplitter, QSizePolicy, QFrame, QRadioButton,
        QButtonGroup, QPlainTextEdit, QTextBrowser
    )
    from PyQt5.QtCore import Qt, QTimer, QDate, QObject, pyqtSignal, QThread, QSize, QRect, pyqtSlot
    from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QIntValidator, QDoubleValidator, QTextCursor, QFontDatabase, QPixmap, QPainter, QBrush, QFontMetrics
    HAS_PYQT5 = True

except ImportError as e:
    HAS_PYQT5 = False
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
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

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


# ── Logging setup ──────────────────────────────────────────────────────────────
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


# ── Kiểm tra và tự động tải modules khi chạy lần đầu ─────────────────────────
def check_and_download_required_files():
    base_dir = Path(__file__).parent.resolve()
    repo_raw = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/main"
    cdn_raw = "https://cdn.jsdelivr.net/gh/junlangzi/Lottery-Predictor@main"

    # Danh sách tất cả file cần thiết để chương trình hoạt động trọn vẹn
    required_files = [
        # 1. Các module chức năng cốt lõi
        ("modules/__init__.py", True),
        ("modules/workers.py", True),
        ("modules/ui_helpers.py", True),
        ("modules/gemini_tab.py", True),
        ("modules/optimizer.py", True),
        ("modules/trial_play.py", True),
        ("modules/news_widget.py", True),
        ("modules/update_workers.py", True),
        ("modules/json_bundle.py", True),

        # 2. Thuật toán nền tảng & thuật toán mẫu
        ("algorithms/__init__.py", True),
        ("algorithms/base.py", True),
        ("algorithms/thuat_toan_01.py", False),
        ("algorithms/thuat_toan_test_01.py", False),
        ("algorithms/thuat_toan_test_02.py", False),
        ("algorithms/thuat_toan_test_03.py", False),

        # 3. Dữ liệu kết quả xổ số
        ("data/xsmb-2-digits.json", True),

        # 4. Cấu hình & biểu tượng
        ("config/logo.png", False),
        ("config/settings.ini", False),

        # 5. Công cụ bổ trợ
        ("tools/__init__.py", False),
        ("tools/date-optimize.pyw", False),

        # 6. Hướng dẫn sử dụng
        ("guide/index.txt", False),
        ("guide/guide.txt", False),
    ]

    # Tạo trước các thư mục cần thiết
    for folder in ["modules", "algorithms", "data", "config", "tools", "guide", "cache", "calculate", "logs", "optimize", "training"]:
        (base_dir / folder).mkdir(parents=True, exist_ok=True)

    missing_files = [item for item in required_files if not (base_dir / item[0]).exists()]
    if not missing_files:
        return

    main_logger.warning(f"Phát hiện thiếu {len(missing_files)} file/module cần thiết. Đang chuẩn bị tải từ GitHub (junlangzi/Lottery-Predictor)...")

    # Hiển thị hộp thoại giao diện trực quan thông báo cho người dùng
    app = None
    dialog = None
    progress_bar = None
    status_label = None
    file_label = None

    if HAS_PYQT5:
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)

            dialog = QDialog()
            dialog.setWindowTitle("Lottery Predictor - Tải Tài Nguyên Ban Đầu")
            dialog.setFixedSize(520, 220)
            dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                    border: 1px solid #cbd5e1;
                    border-radius: 12px;
                }
                QLabel {
                    color: #1e293b;
                    font-family: 'Segoe UI', sans-serif;
                }
                QProgressBar {
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    background-color: #e2e8f0;
                    text-align: center;
                    font-weight: bold;
                    color: #0f172a;
                    height: 22px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b4d8, stop:1 #0077b6);
                    border-radius: 5px;
                }
            """)

            d_layout = QVBoxLayout(dialog)
            d_layout.setContentsMargins(24, 20, 24, 20)
            d_layout.setSpacing(10)

            title_lbl = QLabel("🚀 <b>Đang tải tài nguyên & module lần đầu...</b>")
            title_lbl.setStyleSheet("font-size: 11pt; color: #0077b6;")
            d_layout.addWidget(title_lbl)

            status_label = QLabel(f"Phát hiện thiếu {len(missing_files)} file/module cần thiết cho ứng dụng.\nĐang tự động tải về từ GitHub chính thức...")
            status_label.setStyleSheet("font-size: 9.5pt; color: #475569;")
            status_label.setWordWrap(True)
            d_layout.addWidget(status_label)

            d_layout.addSpacing(5)

            file_label = QLabel("Đang kết nối tới máy chủ GitHub...")
            file_label.setStyleSheet("font-size: 9pt; font-weight: 600; color: #0284c7;")
            d_layout.addWidget(file_label)

            progress_bar = QProgressBar()
            progress_bar.setRange(0, len(missing_files))
            progress_bar.setValue(0)
            d_layout.addWidget(progress_bar)

            dialog.show()
            app.processEvents()
        except Exception as e_dlg:
            main_logger.debug(f"Không thể khởi tạo hộp thoại tải: {e_dlg}")
            dialog = None

    import urllib.request
    import ssl
    try:
        ssl_ctx = ssl.create_default_context()
    except Exception:
        ssl_ctx = ssl._create_unverified_context()

    success_count = 0
    failed_critical = []

    for idx, (rel_path, is_critical) in enumerate(missing_files, 1):
        target_path = base_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if file_label:
            file_label.setText(f"Đang tải ({idx}/{len(missing_files)}): {rel_path} ...")
        if progress_bar:
            progress_bar.setValue(idx - 1)
        if app:
            app.processEvents()

        main_logger.info(f"Đang tải ({idx}/{len(missing_files)}): {rel_path}...")

        urls_to_try = [
            f"{repo_raw}/{rel_path}",
            f"{cdn_raw}/{rel_path}"
        ]

        downloaded = False
        for url in urls_to_try:
            for attempt in range(1, 3):
                try:
                    req = urllib.request.Request(
                        url,
                        headers={
                            'User-Agent': 'LotteryPredictor-Bootstrap/6.0',
                            'Accept': '*/*'
                        }
                    )
                    try:
                        resp = urllib.request.urlopen(req, timeout=15, context=ssl_ctx)
                    except Exception:
                        unverified_ctx = ssl._create_unverified_context()
                        resp = urllib.request.urlopen(req, timeout=15, context=unverified_ctx)

                    with resp, open(target_path, 'wb') as out_f:
                        out_f.write(resp.read())

                    if target_path.exists() and target_path.stat().st_size >= 0:
                        downloaded = True
                        success_count += 1
                        main_logger.info(f"Tải thành công: {rel_path} ({target_path.stat().st_size} bytes)")
                        break
                except Exception as dl_err:
                    main_logger.warning(f"Thử lần {attempt} tải {rel_path} từ {url} không thành công: {dl_err}")
            if downloaded:
                break

        if not downloaded and is_critical:
            failed_critical.append(rel_path)

        if progress_bar:
            progress_bar.setValue(idx)
        if app:
            app.processEvents()

    if file_label:
        if failed_critical:
            file_label.setText(f"⚠️ Có {len(failed_critical)} file tải thất bại. Vui lòng kiểm tra mạng.")
            file_label.setStyleSheet("font-size: 9pt; font-weight: 600; color: #dc2626;")
        else:
            file_label.setText("✅ Hoàn tất tải toàn bộ tài nguyên! Đang khởi động...")
            file_label.setStyleSheet("font-size: 9.5pt; font-weight: 600; color: #16a34a;")
        if app:
            app.processEvents()
            QtCore.QThread.msleep(600)

    if dialog:
        try:
            dialog.close()
            dialog.deleteLater()
        except Exception:
            pass

    main_logger.info(f"Hoàn tất quá trình tải tài nguyên: {success_count}/{len(missing_files)} file.")
    if failed_critical:
        msg = f"Không thể tải các module quan trọng sau từ GitHub:\n" + "\n".join(f"- {f}" for f in failed_critical)
        main_logger.critical(msg)
        if HAS_PYQT5 and app:
            try:
                QMessageBox.critical(None, "Lỗi Tải Module", f"{msg}\n\nVui lòng kiểm tra lại kết nối internet.")
            except Exception:
                pass

check_and_download_required_files()


# ── BaseAlgorithm import ───────────────────────────────────────────────────────
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
    print(f"Loi: Khong the import BaseAlgorithm tu algorithms.base: {e}", file=sys.stderr)
    main_logger.critical(f"Failed to import BaseAlgorithm: {e}", exc_info=True)
    class BaseAlgorithm(ABC):
        def __init__(self, data_results_list=None, cache_dir=None):
            self.config = {"description": "BaseAlgorithm Gia", "parameters": {}}
            self._raw_results_list = copy.deepcopy(data_results_list) if data_results_list else []
            self.cache_dir = cache_dir
            self.logger = logging.getLogger(f"DummyBase_{id(self)}")
            self._log('warning', f"Using Dummy BaseAlgorithm! Instance: {id(self)}")
        def get_config(self) -> dict: return copy.deepcopy(self.config)
        @abstractmethod
        def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
            self._log('error', "Phuong thuc predict() chua duoc trien khai!")
            return {}
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
    main_logger.warning("Using dummy BaseAlgorithm class due to import failure.")
except Exception as base_import_err:
    print(f"Loi khong xac dinh khi import BaseAlgorithm: {base_import_err}", file=sys.stderr)
    main_logger.critical(f"Unknown error importing BaseAlgorithm: {base_import_err}", exc_info=True)
    sys.exit(1)


# ── Import từ các module ───────────────────────────────────────────────────────
# Helper: tải một file module còn thiếu từ GitHub về
def _download_missing_module(module_rel_path: str) -> bool:
    """Tải xuống một file module bị thiếu từ GitHub. Trả về True nếu thành công."""
    _base_dir = Path(__file__).parent.resolve()
    _dest = _base_dir / module_rel_path
    _dest.parent.mkdir(parents=True, exist_ok=True)
    _urls = [
        f"https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/main/{module_rel_path}",
        f"https://cdn.jsdelivr.net/gh/junlangzi/Lottery-Predictor@main/{module_rel_path}",
    ]
    import urllib.request, ssl as _ssl
    _ctx_list = []
    try:
        _ctx_list.append(ssl.create_default_context())
    except Exception:
        pass
    try:
        _unverified = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        _unverified.check_hostname = False
        _unverified.verify_mode = _ssl.CERT_NONE
        _ctx_list.append(_unverified)
    except Exception:
        pass
    _ctx_list.append(None)
    for _url in _urls:
        for _ctx in _ctx_list:
            try:
                _req = urllib.request.Request(_url, headers={'User-Agent': 'LotteryPredictor-Bootstrap/6.0'})
                _kwargs = {"timeout": 25}
                if _ctx is not None:
                    _kwargs["context"] = _ctx
                with urllib.request.urlopen(_req, **_kwargs) as _resp:
                    _data = _resp.read()
                if _data:
                    with open(_dest, 'wb') as _f:
                        _f.write(_data)
                    main_logger.info(f"Đã tải bổ sung: {module_rel_path} ({len(_data)} bytes)")
                    return True
            except Exception as _e:
                main_logger.debug(f"Thử tải {_url} thất bại: {_e}")
    main_logger.error(f"Không thể tải {module_rel_path} từ bất kỳ nguồn nào.")
    return False

def _safe_import_modules():
    """Import tất cả các module, tự động tải bổ sung nếu thiếu."""
    import importlib
    _module_map = {
        "modules/workers.py":        ("modules.workers",        ["ServerStatusCheckWorker", "SignallingLogHandler"]),
        "modules/ui_helpers.py":     ("modules.ui_helpers",     ["PythonSyntaxHighlighter"]),
        "modules/gemini_tab.py":     ("modules.gemini_tab",     ["GeminiModelFetcherWorker", "GeminiWorker", "FetchModelsWorker", "AlgorithmGeminiBuilderTab"]),
        "modules/optimizer.py":      ("modules.optimizer",      ["EvaluationWorker", "AlgorithmEvaluationTab", "OptimizerEmbedded"]),
        "modules/trial_play.py":     ("modules.trial_play",     ["SquareQLabel", "SimulationWorker", "VnMoneySpinBox", "TrialPlayTab"]),
        "modules/news_widget.py":    ("modules.news_widget",    ["NewsFetcherWorker", "ScrollingNewsWidget"]),
        "modules/update_workers.py": ("modules.update_workers", ["GuideSyncWorker", "UpdateCheckWorker", "PerformUpdateWorker"]),
        "modules/json_bundle.py":    ("modules.json_bundle",    ["JsonBundleAlgorithm", "is_json_bundle_file"]),
    }
    _results = {}
    for _rel_path, (_mod_name, _symbols) in _module_map.items():
        for _attempt in range(2):
            try:
                if _mod_name in sys.modules:
                    _mod = sys.modules[_mod_name]
                else:
                    _mod = importlib.import_module(_mod_name)
                for _sym in _symbols:
                    _results[_sym] = getattr(_mod, _sym)
                break
            except (ImportError, ModuleNotFoundError) as _e:
                if _attempt == 0:
                    main_logger.warning(f"Thiếu module '{_mod_name}', đang tải bổ sung...")
                    if _download_missing_module(_rel_path):
                        # Xóa cache để import lại sạch
                        for _k in list(sys.modules.keys()):
                            if _k == _mod_name or _k.startswith(_mod_name + "."):
                                del sys.modules[_k]
                        continue
                # Attempt 1 failed or download failed
                main_logger.critical(f"Không thể import '{_mod_name}': {_e}")
                try:
                    QMessageBox.critical(None, "Lỗi Module Nghiêm Trọng",
                        f"Không thể tải module bắt buộc:\n  {_mod_name}\n\n"
                        f"Lỗi: {_e}\n\nVui lòng kiểm tra kết nối internet và thử lại.")
                except Exception:
                    pass
                sys.exit(1)
    return _results

_imported = _safe_import_modules()
ServerStatusCheckWorker   = _imported["ServerStatusCheckWorker"]
SignallingLogHandler      = _imported["SignallingLogHandler"]
PythonSyntaxHighlighter   = _imported["PythonSyntaxHighlighter"]
GeminiModelFetcherWorker  = _imported["GeminiModelFetcherWorker"]
GeminiWorker              = _imported["GeminiWorker"]
FetchModelsWorker         = _imported["FetchModelsWorker"]
AlgorithmGeminiBuilderTab = _imported["AlgorithmGeminiBuilderTab"]
EvaluationWorker          = _imported["EvaluationWorker"]
AlgorithmEvaluationTab    = _imported["AlgorithmEvaluationTab"]
OptimizerEmbedded         = _imported["OptimizerEmbedded"]
SquareQLabel              = _imported["SquareQLabel"]
SimulationWorker          = _imported["SimulationWorker"]
VnMoneySpinBox            = _imported["VnMoneySpinBox"]
TrialPlayTab              = _imported["TrialPlayTab"]
NewsFetcherWorker         = _imported["NewsFetcherWorker"]
ScrollingNewsWidget       = _imported["ScrollingNewsWidget"]
GuideSyncWorker           = _imported["GuideSyncWorker"]
UpdateCheckWorker         = _imported["UpdateCheckWorker"]
PerformUpdateWorker       = _imported["PerformUpdateWorker"]
JsonBundleAlgorithm       = _imported["JsonBundleAlgorithm"]
is_json_bundle_file       = _imported["is_json_bundle_file"]



class LotteryPredictionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lottery Predictor (v6.0.0)")
        main_logger.info("Initializing LotteryPredictionApp (PyQt5)...")
        self.signalling_log_handler = None
        self.root_logger_instance = None

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

        self.kqxs_tab_frame = None
        self.kqxs_date_label = None
        self.kqxs_calendar_button = None
        self.kqxs_result_labels = {}
        self.available_kqxs_dates = set()


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

        self.current_process = psutil.Process(os.getpid()) if HAS_PSUTIL else None
        self.cpu_throttling_enabled = False
        self.throttle_sleep_duration = 0.005

        self.server_data_sync_status_label = QLabel("🟢 Server Data Sync: Online")
        self.server_data_sync_status_label.setObjectName("ServerStatusLabel")
        self.server_update_status_label = QLabel("🟢 Server Update: Online")
        self.server_update_status_label.setObjectName("ServerStatusLabel")
        self.ram_usage_label = QLabel("💾 RAM: N/A")
        self.ram_usage_label.setObjectName("StatBadge")
        self.cpu_usage_label = QLabel("🖥️ CPU: N/A")
        self.cpu_usage_label.setObjectName("StatBadge")
        self.system_ram_label = QLabel("🔋 System RAM: N/A")
        self.system_ram_label.setObjectName("StatBadge")

        self.system_stats_timer = QTimer(self)
        self.system_stats_timer.timeout.connect(self._update_system_stats)
        self.system_stats_timer.start(2000)

        self.server_status_timer = QTimer(self)
        self.server_status_timer.timeout.connect(self._check_server_statuses_thread)
        self.server_status_timer.start(600000)
        self._last_data_sync_url_checked = ""
        self._last_update_url_checked = ""
        self._data_sync_server_online = None
        self._update_server_online = None

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
        self.setMinimumSize(600, 500)

        self.create_directories()
        self._setup_validators()

        self.load_config()
        self._apply_performance_settings()
        self._setup_global_font()
        self.setup_main_ui_structure()

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

        self._setup_bottom_status_bar()
        self._update_system_stats()


        QTimer.singleShot(1500, self.perform_auto_sync_if_needed)
        QTimer.singleShot(2500, self.perform_auto_update_check_if_needed)
        QTimer.singleShot(3500, self._check_server_statuses_thread)

        self.update_status("Ứng dụng sẵn sàng.")
        QTimer.singleShot(200, self._log_actual_window_size)
        self.start_news_fetcher()

        main_logger.info("LotteryPredictionApp (PyQt5) initialization complete.")
        self.show()


    @pyqtSlot(str, bool)
    def _handle_server_status_updated(self, service_name: str, is_online: bool):
        """Slot để nhận tín hiệu và cập nhật UI trạng thái server."""
        main_logger.debug(f"Slot _handle_server_status_updated: Service='{service_name}', Online={is_online}")
        if service_name == "Data Sync":
            self._update_server_status_label(self.server_data_sync_status_label, "Data Sync", is_online)
        elif service_name == "Update":
            self._update_server_status_label(self.server_update_status_label, "Update", is_online)

    def start_news_fetcher(self):
        """Khởi chạy luồng tải tin tức."""
        self.news_thread = QThread()
        self.news_worker = NewsFetcherWorker()
        self.news_worker.moveToThread(self.news_thread)
        
        self.news_thread.started.connect(self.news_worker.run)
        self.news_worker.news_received.connect(self.on_news_received)
        self.news_worker.news_received.connect(self.news_thread.quit)
        self.news_worker.news_received.connect(self.news_worker.deleteLater)
        self.news_thread.finished.connect(self.news_thread.deleteLater)
        
        self.news_thread.start()

    def on_news_received(self, news_lines):
        """Nhận dữ liệu tin tức và cập nhật widget."""
        if hasattr(self, 'news_ticker_widget'):
            main_logger.info(f"Đã tải {len(news_lines)} dòng tin tức.")
            self.news_ticker_widget.set_news(news_lines)

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

    def on_tab_changed(self, index):
        if self.tab_widget.widget(index) == self.trial_play_tab:
            self.trial_play_tab.refresh_algos()
            if not self.trial_play_tab.date_from.text() and len(self.results) > 10:
                end_d = self.results[-2]['date']
                start_d = end_d - datetime.timedelta(days=30)
                self.trial_play_tab.date_to.setText(end_d.strftime('%d/%m/%Y'))
                self.trial_play_tab.date_from.setText(start_d.strftime('%d/%m/%Y'))


    def _apply_performance_settings(self):
        main_logger.info("Applying performance settings from config...")
        if not self.config.has_section('PERFORMANCE'):
            main_logger.warning("PERFORMANCE section not found in config. Using defaults.")
            self.config.add_section('PERFORMANCE')
            self.config.set('PERFORMANCE', 'set_process_priority', 'True')
            self.config.set('PERFORMANCE', 'priority_level_windows', 'BELOW_NORMAL_PRIORITY_CLASS')
            self.config.set('PERFORMANCE', 'priority_level_unix', '5')
            self.config.set('PERFORMANCE', 'enable_cpu_throttling', 'True')
            self.config.set('PERFORMANCE', 'throttle_sleep_duration', '0.005')
            try:
                self.save_config("settings.ini")
            except Exception as e:
                main_logger.error(f"Failed to save config with default PERFORMANCE section: {e}")


        set_priority = self.config.getboolean('PERFORMANCE', 'set_process_priority', fallback=True)
        
        if HAS_PSUTIL and self.current_process and set_priority:
            try:
                if sys.platform == "win32":
                    priority_str = self.config.get('PERFORMANCE', 'priority_level_windows', fallback='BELOW_NORMAL_PRIORITY_CLASS')
                    priority_val = getattr(psutil, priority_str, psutil.BELOW_NORMAL_PRIORITY_CLASS)
                else:
                    priority_val = self.config.getint('PERFORMANCE', 'priority_level_unix', fallback=5)
                
                self.current_process.nice(priority_val)
                main_logger.info(f"Set process priority to: {priority_val} (Platform: {sys.platform})")
            except Exception as e:
                main_logger.error(f"Failed to set process priority: {e}")
        
        self.cpu_throttling_enabled = self.config.getboolean('PERFORMANCE', 'enable_cpu_throttling', fallback=True)
        try:
            self.throttle_sleep_duration = self.config.getfloat('PERFORMANCE', 'throttle_sleep_duration', fallback=0.005)
            if self.throttle_sleep_duration < 0: self.throttle_sleep_duration = 0.0
            if self.throttle_sleep_duration > 1: self.throttle_sleep_duration = 1.0
        except ValueError:
            main_logger.warning("Invalid throttle_sleep_duration in config, using default.")
            self.throttle_sleep_duration = 0.005
        
        main_logger.info(f"CPU Throttling: {'Enabled' if self.cpu_throttling_enabled else 'Disabled'}, Sleep Duration: {self.throttle_sleep_duration}s")

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


    def _setup_bottom_status_bar(self):
        self.bottom_status_bar = QStatusBar()
        self.setStatusBar(self.bottom_status_bar)

        spacer = QLabel(" ⭐ ")

        self.bottom_status_bar.addPermanentWidget(self.server_data_sync_status_label)
        self.bottom_status_bar.addPermanentWidget(QLabel("   "))
        self.bottom_status_bar.addPermanentWidget(self.server_update_status_label)
        self.bottom_status_bar.addPermanentWidget(QLabel("   "))

        self.bottom_status_bar.addPermanentWidget(self.ram_usage_label)
        self.bottom_status_bar.addPermanentWidget(QLabel("   "))
        self.bottom_status_bar.addPermanentWidget(self.cpu_usage_label)
        self.bottom_status_bar.addPermanentWidget(QLabel("   "))
        self.bottom_status_bar.addPermanentWidget(self.system_ram_label)
        main_logger.info("Bottom status bar with server and system stats initialized.")

    def _check_url_connectivity(self, url: str, timeout=5) -> bool:
        """Kiểm tra kết nối đến một URL cụ thể."""
        try:
            import requests
            response = requests.head(url, timeout=timeout, headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
            return 200 <= response.status_code < 400
        except ImportError:
            main_logger.warning("Thư viện 'requests' không có, không thể kiểm tra trạng thái server.")
            return False
        except requests.exceptions.RequestException as e:
            main_logger.debug(f"Lỗi kết nối khi kiểm tra URL '{url}': {type(e).__name__} - {e}")
            return False
        except Exception as e_gen:
            main_logger.warning(f"Lỗi không xác định khi kiểm tra URL '{url}': {type(e_gen).__name__} - {e_gen}")
            return False

    def _update_server_status_label(self, label_widget: QLabel, service_name: str, is_online: bool):
        """Cập nhật text và style cho một label trạng thái server."""
        if is_online:
            label_widget.setText(f"🟢 Server {service_name}: Online")
        else:
            label_widget.setText(f"🔴 Server {service_name}: Offline")
        label_widget.setTextFormat(Qt.PlainText)

    
    def _check_server_statuses_thread(self):
        """Khởi chạy luồng kiểm tra trạng thái server."""
        if hasattr(self, '_server_status_worker_thread') and self._server_status_worker_thread is not None:
            try:
                if self._server_status_worker_thread.isRunning():
                    main_logger.debug("Luồng kiểm tra trạng thái server vẫn đang chạy, bỏ qua lần này.")
                    return
            except RuntimeError:
                main_logger.debug("RuntimeError caught checking previous server status thread; it was likely deleted. Proceeding to create a new one.")
                self._server_status_worker_thread = None

        self._server_status_worker_object = ServerStatusCheckWorker(self)
        self._server_status_worker_thread = QThread(self)

        self._server_status_worker_object.moveToThread(self._server_status_worker_thread)

        self._server_status_worker_object.status_updated_signal.connect(self._handle_server_status_updated)
        self._server_status_worker_object.finished_checking_signal.connect(self._server_status_worker_thread.quit)
        
        self._server_status_worker_thread.finished.connect(self._server_status_worker_object.deleteLater)
        self._server_status_worker_thread.finished.connect(self._server_status_worker_thread.deleteLater)
        self._server_status_worker_thread.finished.connect(self._clear_server_status_thread_ref)

        self._server_status_worker_thread.started.connect(self._server_status_worker_object.run_check)
        self._server_status_worker_thread.start()
        main_logger.info("Đã khởi chạy luồng kiểm tra trạng thái server bằng QThread và Worker.")

    def _update_system_stats(self):
        if not HAS_PSUTIL or not self.current_process:
            self.ram_usage_label.setText("💾 RAM: N/A")
            self.cpu_usage_label.setText("🖥️ CPU: N/A")
            self.system_ram_label.setText("🔋 System RAM: N/A")
            return

        try:
            mem_info = self.current_process.memory_info()
            ram_usage_mb = mem_info.rss / (1024 * 1024)
            self.ram_usage_label.setText(f"💾 RAM {ram_usage_mb:.1f} MB")

            cpu_percent_process_single_core = self.current_process.cpu_percent(interval=0.1)
            
            num_logical_cores = psutil.cpu_count(logical=True)

            if num_logical_cores and num_logical_cores > 0:
                cpu_percent_system_total = cpu_percent_process_single_core / num_logical_cores
                self.cpu_usage_label.setText(f"🖥️ CPU {cpu_percent_system_total:.1f}%")
            else:
                self.cpu_usage_label.setText(f"🖥️ CPU {cpu_percent_process_single_core:.1f}%")
                main_logger.warning("Could not get number of CPU cores. Displaying process CPU % relative to 1 core (fallback).")

            sys_mem = psutil.virtual_memory()
            sys_ram_free_gb = sys_mem.available / (1024 * 1024 * 1024)
            sys_ram_total_gb = sys_mem.total / (1024 * 1024 * 1024)
            self.system_ram_label.setText(f"🔋 System RAM {sys_ram_free_gb:.1f}/{sys_ram_total_gb:.1f} GB")

        except psutil.NoSuchProcess:
            main_logger.warning("Process not found for psutil, stopping system stats updates.")
            self.system_stats_timer.stop()
            self.ram_usage_label.setText("💾 RAM: Lỗi")
            self.cpu_usage_label.setText("🖥️ CPU: Lỗi")
            self.system_ram_label.setText("🔋 System RAM: Lỗi")
        except Exception as e:
            main_logger.error(f"Error updating system stats: {e}", exc_info=False)

    def _clear_server_status_thread_ref(self):
        main_logger.debug("Server status worker thread finished. Clearing Python reference to QThread.")
        self._server_status_worker_thread = None


    def setup_main_ui_structure(self):
        """Thiết lập cấu trúc giao diện người dùng chính của ứng dụng."""
        main_logger.debug("Thiết lập cấu trúc UI chính (PyQt5)...")

        self.top_status_toolbar = QtWidgets.QToolBar("TopStatusToolBar")
        self.top_status_toolbar.setMovable(False)
        self.top_status_toolbar.setFloatable(False)
        self.top_status_toolbar.setObjectName("TopStatusToolBar")
        self.top_status_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.status_bar_label = QLabel("🟢 Hoạt động: Đang dùng phiên bản mới nhất.")
        self.status_bar_label.setObjectName("StatusBarLabel")
        self.status_bar_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.top_status_toolbar.addWidget(self.status_bar_label)
        
        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.top_status_toolbar.addWidget(spacer_left)

        btn_prev_news = QPushButton("◀") 
        btn_prev_news.setObjectName("SmallNavButton")
        btn_prev_news.setFixedSize(28, 24)
        btn_prev_news.setCursor(Qt.PointingHandCursor)
        btn_prev_news.setToolTip("Tin trước đó")
        self.top_status_toolbar.addWidget(btn_prev_news)

        news_title_label = QLabel(" Tin tức: ")
        news_font = self.get_qfont("bold")
        news_title_label.setFont(news_font)
        news_title_label.setStyleSheet("color: #475569; font-weight: bold; margin-left: 5px; margin-right: 5px;") 
        self.top_status_toolbar.addWidget(news_title_label)

        btn_next_news = QPushButton("▶") 
        btn_next_news.setObjectName("SmallNavButton")
        btn_next_news.setFixedSize(28, 24)
        btn_next_news.setCursor(Qt.PointingHandCursor)
        btn_next_news.setToolTip("Tin tiếp theo")
        self.top_status_toolbar.addWidget(btn_next_news)
        
        self.top_status_toolbar.addWidget(QLabel(" "))

        self.news_ticker_widget = ScrollingNewsWidget()
        self.news_ticker_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.top_status_toolbar.addWidget(self.news_ticker_widget)
        
        btn_prev_news.clicked.connect(self.news_ticker_widget.prev_news)
        btn_next_news.clicked.connect(self.news_ticker_widget.next_news)

        self.top_status_toolbar.addWidget(QLabel("  "))

        self.top_version_label = QLabel("Phiên bản: 6.0.0")
        self.top_version_label.setObjectName("TopVersionLabel")
        self.top_status_toolbar.addWidget(self.top_version_label)

        self.addToolBar(Qt.TopToolBarArea, self.top_status_toolbar)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(6, 4, 6, 6)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("MainTabWidget")

        self.main_tab_frame = QWidget()
        self.kqxs_tab_frame = QWidget()
        self.trial_play_tab = TrialPlayTab(self)
        self.optimizer_tab_frame = QWidget()
        self.tools_tab_frame = QWidget()
        self.settings_tab_frame = QWidget()
        self.help_tab_frame = QWidget()
        self.update_tab_frame = QWidget()
        
        self.tab_widget.addTab(self.main_tab_frame, "🏠 Main")
        self.tab_widget.addTab(self.optimizer_tab_frame, "🔧 Thuật toán")
        self.tab_widget.addTab(self.trial_play_tab, "🎮 Chơi Thử")
        self.tab_widget.addTab(self.kqxs_tab_frame, "🔍 Xem KQXS")
        self.tab_widget.addTab(self.tools_tab_frame, "💼 Công Cụ")
        self.tab_widget.addTab(self.settings_tab_frame, "⚙️ Cài Đặt")
        self.tab_widget.addTab(self.help_tab_frame, "📖 Hướng Dẫn") 
        self.tab_widget.addTab(self.update_tab_frame, "🔄 Update")

        main_layout.addWidget(self.tab_widget)

        self.setup_main_tab()
        self.setup_kqxs_tab()
        self.setup_tools_tab()
        self.setup_settings_tab()
        self.setup_help_tab()
        self.setup_update_tab()

        try:
            icon_path = self.config_dir / "logo.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                main_logger.info(f"Icon ứng dụng được đặt từ: {icon_path}")
            else:
                main_logger.warning(f"Icon file not found at {icon_path}, skipping setWindowIcon.")
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

    def update_kqxs_tab(self, target_date: datetime.date):
        """Cập nhật tab Xem KQXS: Chỉ hiển thị 2 số cuối (Loto) và thống kê."""
        main_logger.info(f"Updating KQXS tab for date: {target_date}")
        if not hasattr(self, 'kqxs_date_label') or not self.kqxs_date_label:
            return

        d_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        day_of_week = d_names[target_date.weekday()]
        self.kqxs_date_label.setText(f"<b>XSMB {day_of_week} {target_date:%d-%m-%Y}</b>")

        current_entry = next((r for r in self.results if r['date'] == target_date), None)
        result_data = current_entry['result'] if current_entry else None

        if result_data is None:
            main_logger.warning(f"No data found for {target_date}")
            for key in self.kqxs_result_labels:
                for label in self.kqxs_result_labels[key]: label.setText("")
            self.stats_nhay_label.setText("Không có dữ liệu.")
            self.stats_roi_label.setText("Wait...")
            self.stats_top_gan_label.setText("Wait...")
            self.stats_gan_ve_label.setText("Wait...")
            self.stats_head_tail_label.setText("Wait...")
            return
        
        prize_map = {
            'db': ['special', 'dac_biet'], 'nhat': ['prize1', 'giai_nhat'],
            'nhi': ['prize2_1', 'prize2_2'], 
            'ba': ['prize3_1', 'prize3_2', 'prize3_3', 'prize3_4', 'prize3_5', 'prize3_6'],
            'tu': ['prize4_1', 'prize4_2', 'prize4_3', 'prize4_4'],
            'nam': ['prize5_1', 'prize5_2', 'prize5_3', 'prize5_4', 'prize5_5', 'prize5_6'],
            'sau': ['prize6_1', 'prize6_2', 'prize6_3'],
            'bay': ['prize7_1', 'prize7_2', 'prize7_3', 'prize7_4']
        }

        all_loto_today = []

        for key, labels in self.kqxs_result_labels.items():
            possible_keys = prize_map.get(key, [])
            if not possible_keys: continue
            
            for i, label in enumerate(labels):
                current_prize_key = possible_keys[i] if i < len(possible_keys) else ""
                
                if not current_prize_key or current_prize_key not in result_data:
                    alt_key = current_prize_key.replace("prize", "giai")
                    if alt_key in result_data: current_prize_key = alt_key

                raw_val = result_data.get(current_prize_key)
                if raw_val is not None:
                    loto_val = self._get_loto(raw_val)
                    
                    label.setText(loto_val)
                    
                    if loto_val.isdigit():
                        all_loto_today.append(loto_val)
                else:
                    label.setText("")

        
        from collections import Counter
        loto_counts = Counter(all_loto_today)
        multi_hit = [f"<b style='color:red'>{k}</b> ({v} nháy)" for k, v in loto_counts.items() if v >= 2]
        if multi_hit:
            self.stats_nhay_label.setText(", ".join(multi_hit))
            self.stats_nhay_label.setTextFormat(Qt.RichText)
        else:
            self.stats_nhay_label.setText("Không có lô nào về nhiều nháy.")

        heads = {i: 0 for i in range(10)}
        tails = {i: 0 for i in range(10)}
        for loto in all_loto_today:
            if len(loto) == 2:
                h, t = int(loto[0]), int(loto[1])
                heads[h] += 1
                tails[t] += 1
        
        ht_html = "<table width='100%' border='0' cellspacing='0' cellpadding='2'>"
        ht_html += "<tr><td width='50%' valign='top'><b>Đầu (Số lần)</b></td><td width='50%' valign='top'><b>Đuôi (Số lần)</b></td></tr>"
        for i in range(10):
            h_val = heads[i]
            t_val = tails[i]
            h_str = f"<span style='color:red'><b>{h_val}</b></span>" if h_val == 0 else (f"<b>{h_val}</b>" if h_val >= 4 else f"{h_val}")
            t_str = f"<span style='color:red'><b>{t_val}</b></span>" if t_val == 0 else (f"<b>{t_val}</b>" if t_val >= 4 else f"{t_val}")
            ht_html += f"<tr><td>Đầu {i}: {h_str}</td><td>Đuôi {i}: {t_str}</td></tr>"
        ht_html += "</table>"
        self.stats_head_tail_label.setText(ht_html)
        self.stats_head_tail_label.setTextFormat(Qt.RichText)

        history_data = [r for r in self.results if r['date'] < target_date]
        
        yesterday_lotos = set()
        if history_data:
            last_data = history_data[-1]
            raw_nums = self.extract_numbers_from_result_dict(last_data['result'])
            yesterday_lotos = {f"{n:02d}" for n in raw_nums}
        
        roi_list = sorted([L for L in set(all_loto_today) if L in yesterday_lotos])
        if roi_list:
            self.stats_roi_label.setText(", ".join(roi_list))
        else:
            self.stats_roi_label.setText("Không có lô rơi từ kỳ trước.")

        gan_days = {f"{i:02d}": 0 for i in range(100)}
        
        if history_data:
            sorted_history = sorted(history_data, key=lambda x: x['date'], reverse=True)
            found_numbers = set()
            for idx, entry in enumerate(sorted_history):
                entry_date = entry['date']
                days_diff = (target_date - entry_date).days
                day_lotos = self.extract_numbers_from_result_dict(entry['result'])
                day_loto_strs = {f"{n:02d}" for n in day_lotos}
                
                for num_str in list(gan_days.keys()):
                    if num_str in found_numbers: continue
                    if num_str in day_loto_strs:
                        gan_days[num_str] = days_diff
                        found_numbers.add(num_str)
            
            max_days = (target_date - sorted_history[-1]['date']).days + 1
            for num_str in gan_days:
                if num_str not in found_numbers: gan_days[num_str] = max_days

        today_gan_stats = []
        for loto in set(all_loto_today):
            days = gan_days.get(loto, 0)
            today_gan_stats.append((loto, days))
        
        today_gan_stats.sort(key=lambda x: x[1], reverse=True)
        
        if today_gan_stats:
            gan_ve_html = ""
            for loto, days in today_gan_stats[:5]:
                if days > 5:
                    gan_ve_html += f"Số <b>{loto}</b> (gan {days} ngày)<br>"
            if not gan_ve_html: gan_ve_html = "Không có số gan nào (tất cả đều < 5 ngày)."
            self.stats_gan_ve_label.setText(gan_ve_html)
            self.stats_gan_ve_label.setTextFormat(Qt.RichText)
        else:
            self.stats_gan_ve_label.setText("N/A")

        missing_numbers = []
        for i in range(100):
            num_str = f"{i:02d}"
            if num_str not in all_loto_today:
                missing_numbers.append((num_str, gan_days.get(num_str, 0)))
        
        missing_numbers.sort(key=lambda x: x[1], reverse=True)
        
        top_gan_html = ""
        for loto, days in missing_numbers[:3]:
             top_gan_html += f"Số <b style='color:red; font-size:12pt'>{loto}</b>: chưa về <b>{days}</b> ngày<br>"
        
        self.stats_top_gan_label.setText(top_gan_html)
        self.stats_top_gan_label.setTextFormat(Qt.RichText)

    def select_previous_kqxs_day(self):
        """Chọn và hiển thị kết quả của ngày có dữ liệu trước đó."""
        try:
            full_text = self.kqxs_date_label.text()
            date_str = full_text.split(" ")[-1].replace('</b>', '')
            
            current_date = datetime.datetime.strptime(date_str, "%d-%m-%Y").date()
            sorted_dates = sorted(list(self.available_kqxs_dates), reverse=True)
            
            found_index = -1
            for i, date in enumerate(sorted_dates):
                if date == current_date:
                    found_index = i
                    break

            if found_index != -1 and found_index < len(sorted_dates) - 1:
                prev_date = sorted_dates[found_index + 1]
                self.update_kqxs_tab(prev_date)
            else:
                self.update_status("Đang ở ngày đầu tiên trong dữ liệu.")
        except (ValueError, IndexError):
            self.update_status("Không thể xác định ngày trước đó.")

    def select_next_kqxs_day(self):
        """Chọn và hiển thị kết quả của ngày có dữ liệu kế tiếp."""
        try:
            full_text = self.kqxs_date_label.text()
            date_str = full_text.split(" ")[-1].replace('</b>', '')

            current_date = datetime.datetime.strptime(date_str, "%d-%m-%Y").date()
            sorted_dates = sorted(list(self.available_kqxs_dates))

            found_index = -1
            for i, date in enumerate(sorted_dates):
                if date == current_date:
                    found_index = i
                    break

            if found_index != -1 and found_index < len(sorted_dates) - 1:
                next_date = sorted_dates[found_index + 1]
                self.update_kqxs_tab(next_date)
            else:
                self.update_status("Đang ở ngày cuối cùng trong dữ liệu.")
        except (ValueError, IndexError):
            self.update_status("Không thể xác định ngày kế tiếp.")

    def show_kqxs_calendar(self):
        """Hiển thị lịch chỉ cho phép chọn những ngày có dữ liệu."""
        if not self.available_kqxs_dates:
            QMessageBox.warning(self, "Thiếu Dữ Liệu", "Không có dữ liệu ngày nào để lựa chọn.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Chọn Ngày Xem Kết Quả")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setGridVisible(True)

        min_date = min(self.available_kqxs_dates)
        max_date = max(self.available_kqxs_dates)
        calendar.setMinimumDate(QDate(min_date.year, min_date.month, min_date.day))
        calendar.setMaximumDate(QDate(max_date.year, max_date.month, max_date.day))
        
        selectable_format = QTextCharFormat()
        selectable_format.setFontWeight(QFont.Bold)
        selectable_format.setForeground(QColor("blue"))
        
        for date_obj in self.available_kqxs_dates:
            q_date = QDate(date_obj.year, date_obj.month, date_obj.day)
            calendar.setDateTextFormat(q_date, selectable_format)
            
        layout.addWidget(calendar)
        
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            selected_qdate = calendar.selectedDate()
            selected_date_obj = selected_qdate.toPyDate()

            if selected_date_obj in self.available_kqxs_dates:
                self.update_kqxs_tab(selected_date_obj)
            else:
                QMessageBox.warning(self, "Ngày không hợp lệ", "Vui lòng chọn một ngày được đánh dấu (có dữ liệu).")

    def _on_ana_link_clicked(self, url):
        """Xử lý khi bấm vào link trong bảng kết quả phân tích (Đã bỏ dấu ?)."""
        url_str = url.toString()
        if url_str == "cmd:view_max_freq_dates":
            dates_list = getattr(self, '_current_max_freq_dates', [])
            if not dates_list:
                return
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Danh Sách Ngày Xuất Hiện Nhiều Nhất")
            dialog.setMinimumSize(400, 500)
            
            flags = dialog.windowFlags()
            flags = flags & ~Qt.WindowContextHelpButtonHint
            dialog.setWindowFlags(flags)

            layout = QVBoxLayout(dialog)
            
            info = QLabel(f"Tổng cộng: {len(dates_list)} ngày đạt kỷ lục.")
            info.setStyleSheet("font-weight: bold; color: #0056b3; font-size: 11pt; margin-bottom: 5px;")
            layout.addWidget(info)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText("\n".join(dates_list))
            text_edit.setFont(self.get_qfont("code"))
            layout.addWidget(text_edit)
            
            btn_close = QPushButton("Đóng")
            btn_close.clicked.connect(dialog.accept)
            layout.addWidget(btn_close)
            
            dialog.exec_()


    def setup_gemini_creator_tab(self):
        """Thiết lập giao diện cho tab Tạo Thuật Toán bằng Gemini."""
        main_logger.debug("Setting up Algorithm Gemini Creator tab UI...")
        if not HAS_GEMINI:
            layout = QVBoxLayout(self.gemini_creator_tab_frame)
            error_label = QLabel(
                "Tính năng tạo thuật toán bằng Gemini yêu cầu thư viện 'google-generativeai'.\n"
                "Vui lòng cài đặt bằng lệnh: <code>pip install google-generativeai</code><br>"
                "Sau đó khởi động lại ứng dụng."
            )
            error_label.setTextFormat(Qt.RichText)
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setWordWrap(True)
            error_label.setStyleSheet("padding: 20px; color: #dc3545; font-weight: bold;")
            layout.addWidget(error_label)
            main_logger.warning("Gemini library not found. Gemini creator tab shows error message.")
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.gemini_creator_tab_frame:
                    self.tab_widget.setTabEnabled(i, False)
                    self.tab_widget.setTabText(i, self.tab_widget.tabText(i) + " (Lỗi)")
                    break
            return

        try:
            self.gemini_creator_tab_instance = AlgorithmGeminiBuilderTab(self.gemini_creator_tab_frame, self)
            layout = QVBoxLayout(self.gemini_creator_tab_frame)
            layout.setContentsMargins(0,0,0,0)
            layout.addWidget(self.gemini_creator_tab_instance)
            main_logger.info("Algorithm Gemini Creator tab initialized successfully.")
        except Exception as e:
            main_logger.error(f"Failed to initialize AlgorithmGeminiBuilderTab: {e}", exc_info=True)
            layout = QVBoxLayout(self.gemini_creator_tab_frame)
            error_label = QLabel(f"Lỗi khởi tạo tab tạo thuật toán:\n{e}")
            error_label.setStyleSheet("color: red;")
            layout.addWidget(error_label)
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.gemini_creator_tab_frame:
                    self.tab_widget.setTabEnabled(i, False)
                    self.tab_widget.setTabText(i, self.tab_widget.tabText(i) + " (Lỗi Khởi Tạo)")
                    break


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
            stylesheet = f"""
                /* =========================================================
                   LOTTERY PREDICTOR - 3D EMBOSSED / NEUMORPHIC MODERN THEME
                   ========================================================= */

                QMainWindow {{
                    background-color: #f0f2f5;
                }}

                QWidget {{
                    color: #1e293b;
                    font-family: "{self.font_family_base}", "Segoe UI", sans-serif;
                }}

                /* ---- TOP STATUS TOOLBAR ---- */
                QToolBar#TopStatusToolBar {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f1f5f9);
                    border-bottom: 1px solid #cbd5e1;
                    border-top: none;
                    border-left: none;
                    border-right: none;
                    padding: 5px 12px;
                    min-height: 38px;
                }}

                QLabel#StatusBarLabel {{
                    background-color: #ffffff;
                    border: 1px solid #d0d7de;
                    border-bottom: 2px solid #b0b8c4;
                    border-radius: 12px;
                    padding: 3px 12px;
                    font-weight: 600;
                    color: #1e293b;
                    min-width: 250px;
                }}
                QLabel#StatusBarLabel[status="error"] {{
                    background-color: #fef2f2;
                    border-color: #fca5a5;
                    border-bottom: 2px solid #ef4444;
                    color: #b91c1c;
                }}
                QLabel#StatusBarLabel[status="success"] {{
                    background-color: #f0fdf4;
                    border-color: #86efac;
                    border-bottom: 2px solid #22c55e;
                    color: #15803d;
                }}
                QLabel#StatusBarLabel[status="info"] {{
                    background-color: #f0f9ff;
                    border-color: #7dd3fc;
                    border-bottom: 2px solid #0284c7;
                    color: #0369a1;
                }}

                QLabel#TopVersionLabel {{
                    color: #475569;
                    font-size: 9.5pt;
                    font-weight: 500;
                    padding-left: 10px;
                    padding-right: 8px;
                }}

                /* ---- 3D PILL / SEGMENTED CONTROL TAB BAR ---- */
                QTabWidget#MainTabWidget {{
                    background-color: transparent;
                }}

                QTabWidget#MainTabWidget::pane {{
                    border: none;
                    background-color: transparent;
                    padding-top: 4px;
                }}

                QTabWidget#MainTabWidget QTabBar {{
                    background-color: transparent;
                    qproperty-drawBase: 0;
                    border: none;
                }}

                QTabWidget#MainTabWidget QTabBar::tab {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #e8ecf2);
                    color: #334155;
                    border: 1px solid #cbd5e1;
                    border-bottom: 2px solid #94a3b8;
                    border-radius: 8px;
                    padding: 5px 8px;
                    margin-right: 2px;
                    margin-top: 2px;
                    margin-bottom: 4px;
                    font-weight: 600;
                    font-size: 9pt;
                }}

                QTabWidget#MainTabWidget QTabBar::tab:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #dbeafe);
                    color: #0077b6;
                    border-color: #7dd3fc;
                    border-bottom: 2px solid #0077b6;
                }}

                QTabWidget#MainTabWidget QTabBar::tab:selected {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00c4cc, stop:0.06 #00b4d8, stop:1 #0077b6);
                    color: #ffffff;
                    border: 1px solid #005f73;
                    border-top: 1px solid #48cae4;
                    border-bottom: 3px solid #003d52;
                    border-radius: 8px;
                    padding: 5px 12px;
                    font-weight: bold;
                }}

                /* ---- 3D CARD CONTAINERS (QGroupBox) ---- */
                QGroupBox {{
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-right: 2px solid #cbd5e1;
                    border-bottom: 3px solid #cbd5e1;
                    border-radius: 12px;
                    margin-top: 16px;
                    padding: 16px 12px 12px 12px;
                    font-weight: bold;
                    font-size: 10.5pt;
                    color: #0f172a;
                }}

                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    left: 12px;
                    top: 1px;
                    padding: 2px 8px;
                    background-color: transparent;
                    color: #0f172a;
                    font-weight: bold;
                    font-size: 10.5pt;
                }}

                /* ---- ALGORITHM CARD ITEM (QFrame#CardFrame) ---- */
                QFrame#CardFrame {{
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-right: 1.5px solid #d1d9e6;
                    border-bottom: 2.5px solid #cbd5e1;
                    border-radius: 10px;
                    margin-bottom: 6px;
                    padding: 8px 12px;
                }}

                QFrame#CardFrame:hover {{
                    border-color: #94a3b8;
                    border-bottom: 2.5px solid #64748b;
                    background-color: #fafbfd;
                }}

                /* ---- 3D BUTTONS ---- */
                QPushButton, QPushButton#LightButton, QPushButton#SettingsButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.08 #f8fafc, stop:1 #e8ecf2);
                    color: #1e293b;
                    border: 1px solid #cbd5e1;
                    border-top: 1px solid #ffffff;
                    border-bottom: 2px solid #94a3b8;
                    border-radius: 8px;
                    padding: 4px 8px;
                    font-weight: 600;
                    min-width: 55px;
                    min-height: 24px;
                }}

                QPushButton#LightButton {{
                    min-width: 75px;
                }}

                QPushButton:hover, QPushButton#LightButton:hover, QPushButton#SettingsButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.08 #f0f9ff, stop:1 #e0f2fe);
                    border-color: #00b4d8;
                    border-bottom: 2px solid #0077b6;
                    color: #0077b6;
                }}

                QPushButton:pressed, QPushButton#LightButton:pressed, QPushButton#SettingsButton:pressed {{
                    background: #cbd5e1;
                    border-top: 2px solid #94a3b8;
                    border-bottom: 1px solid #94a3b8;
                    padding-top: 2px;
                }}

                QPushButton:disabled {{
                    background: #f1f5f9;
                    color: #94a3b8;
                    border: 1px solid #e2e8f0;
                    border-bottom: 1px solid #e2e8f0;
                }}

                /* 🎯 3D DỰ ĐOÁN BUTTON (Teal/Cyan Gradient 3D Tactile Button) */
                QPushButton#PredictButton, QPushButton#AccentButton, QPushButton#ListAccentButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00c4cc, stop:0.08 #00b4d8, stop:1 #0077b6);
                    color: #ffffff;
                    border: 1px solid #0077b6;
                    border-top: 1px solid #48cae4;
                    border-bottom: 3px solid #004b73;
                    border-radius: 8px;
                    padding: 4px 14px;
                    font-weight: bold;
                    font-size: 9.5pt;
                    min-height: 25px;
                    min-width: 80px;
                }}

                QPushButton#PredictButton:hover, QPushButton#AccentButton:hover, QPushButton#ListAccentButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #22d3ee, stop:0.08 #06b6d4, stop:1 #0284c7);
                    border-color: #0284c7;
                    border-top: 1px solid #67e8f9;
                    border-bottom: 3px solid #0369a1;
                }}

                QPushButton#PredictButton:pressed, QPushButton#AccentButton:pressed, QPushButton#ListAccentButton:pressed {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #006080, stop:1 #0077b6);
                    border-top: 2px solid #00364d;
                    border-bottom: 1px solid #00364d;
                    padding-top: 2px;
                }}

                /* 🧮 3D TÍNH TOÁN BUTTON (Warm Golden Amber 3D Tactile Button) */
                QPushButton#CalcButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fef6e4, stop:0.08 #f7dfa5, stop:1 #d9ad5b);
                    color: #4a3200;
                    border: 1px solid #c49942;
                    border-top: 1px solid #fff5dd;
                    border-bottom: 3px solid #946e1c;
                    border-radius: 8px;
                    padding: 5px 14px;
                    font-weight: bold;
                    font-size: 10pt;
                    min-height: 25px;
                    min-width: 140px;
                }}

                QPushButton#CalcButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fff9ec, stop:0.08 #fae7b8, stop:1 #e2b969);
                    border-color: #b58832;
                    border-bottom: 3px solid #825f14;
                    color: #2e1f00;
                }}

                QPushButton#CalcButton:pressed {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c49638, stop:1 #b58529);
                    border-top: 2px solid #73530f;
                    border-bottom: 1px solid #73530f;
                    padding-top: 2px;
                }}

                /* ☁ SYNC BUTTON */
                QPushButton#SyncButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.08 #f0f9ff, stop:1 #e0f2fe);
                    color: #0369a1;
                    border: 1px solid #7dd3fc;
                    border-top: 1px solid #ffffff;
                    border-bottom: 2px solid #0284c7;
                    border-radius: 8px;
                    font-weight: bold;
                    padding: 4px 10px;
                    min-height: 24px;
                    min-width: 95px;
                }}

                QPushButton#SyncButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e0f2fe, stop:1 #bae6fd);
                    border-color: #0284c7;
                    border-bottom: 2px solid #0369a1;
                }}

                QPushButton#SyncButton:pressed {{
                    background: #bae6fd;
                    border-top: 2px solid #0369a1;
                    border-bottom: 1px solid #0369a1;
                    padding-top: 2px;
                }}

                /* Small Navigation Buttons (<, >) */
                QPushButton#SmallNavButton {{
                    padding: 2px 4px;
                    min-width: 26px;
                    max-width: 32px;
                    min-height: 22px;
                    max-height: 26px;
                    font-weight: bold;
                    font-size: 10pt;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #e8ecf2);
                    border: 1px solid #cbd5e1;
                    border-bottom: 2px solid #94a3b8;
                    border-radius: 6px;
                    color: #1e293b;
                }}

                QPushButton#SmallNavButton:hover {{
                    background: #ffffff;
                    border-color: #00b4d8;
                    color: #0077b6;
                }}

                QPushButton#SmallNavButton:pressed {{
                    background: #cbd5e1;
                    border-top: 2px solid #94a3b8;
                    border-bottom: 1px solid #94a3b8;
                    padding-top: 2px;
                }}

                /* Calendar Button (📅) */
                QPushButton#CalendarButton {{
                    padding: 2px 4px;
                    min-width: 26px;
                    max-width: 30px;
                    min-height: 22px;
                    max-height: 26px;
                    font-size: 11pt;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #e8ecf2);
                    border: 1px solid #cbd5e1;
                    border-bottom: 2px solid #94a3b8;
                    border-radius: 6px;
                }}

                QPushButton#CalendarButton:hover {{
                    background: #ffffff;
                    border-color: #00b4d8;
                }}

                QPushButton#CalendarButton:pressed {{
                    background: #cbd5e1;
                    border-top: 2px solid #94a3b8;
                    border-bottom: 1px solid #94a3b8;
                    padding-top: 2px;
                }}

                /* ----------------- INPUT FIELDS & COMBOBOX ----------------- */
                QLineEdit, QSpinBox, QDoubleSpinBox {{
                    background-color: #ffffff;
                    border: 1px solid #d1d9e6;
                    border-top: 1px solid #b8c4d6;
                    border-radius: 7px;
                    padding: 4px 6px;
                    min-height: 24px;
                    color: #1e293b;
                }}

                QComboBox {{
                    background-color: #ffffff;
                    border: 1px solid #d1d9e6;
                    border-top: 1px solid #b8c4d6;
                    border-radius: 7px;
                    padding-left: 8px;
                    padding-right: 24px;
                    padding-top: 4px;
                    padding-bottom: 4px;
                    min-height: 24px;
                    color: #1e293b;
                }}

                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                    border: 1.5px solid #00b4d8;
                    background-color: #ffffff;
                }}

                QLineEdit:read-only {{
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    color: #334155;
                }}

                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
                    background-color: #f1f5f9;
                    color: #94a3b8;
                    border: 1px solid #e2e8f0;
                }}


                /* Modern Pill Path Display */
                QLabel#PathDisplayLabel {{
                    background-color: #f8fafc;
                    border: 1px solid #d1d9e6;
                    border-top: 1px solid #b8c4d6;
                    border-radius: 7px;
                    padding: 4px 8px;
                    color: #1e293b;
                    font-size: 9.5pt;
                }}

                /* ----------------- 3D CHECKBOX ----------------- */
                QCheckBox {{
                    spacing: 6px;
                    font-weight: 600;
                    color: #1e293b;
                }}

                QCheckBox::indicator {{
                    width: 17px;
                    height: 17px;
                    border-radius: 4px;
                    border: 1px solid #cbd5e1;
                    border-bottom: 2px solid #94a3b8;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #edf1f7);
                }}

                QCheckBox::indicator:hover {{
                    border-color: #00b4d8;
                    background: #f0f9ff;
                }}

                QCheckBox::indicator:checked {{
                    border: 1px solid #0077b6;
                    border-bottom: 2px solid #00507a;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00b4d8, stop:1 #0077b6);
                }}

                QCheckBox::indicator:disabled {{
                    border-color: #e2e8f0;
                    background: #f1f5f9;
                }}

                /* ----------------- TEXT LOG & DISPLAY (3D Sunken Box) ----------------- */
                QTextEdit#PerformanceTextEdit, QTextEdit {{
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #d1d9e6;
                    border-top: 2px solid #94a3b8;
                    border-radius: 8px;
                    padding: 8px;
                }}

                /* ----------------- BOTTOM STATUS BAR ----------------- */
                QStatusBar {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8fafc, stop:1 #eef2f6);
                    border-top: 1px solid #cbd5e1;
                    color: #334155;
                    min-height: 32px;
                }}

                QStatusBar::item {{
                    border: none;
                }}

                QLabel#StatBadge {{
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-bottom: 2px solid #94a3b8;
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-weight: 600;
                    color: #1e293b;
                    font-size: 9pt;
                }}

                QLabel#ServerStatusLabel {{
                    padding: 2px 6px;
                    font-weight: 600;
                    color: #334155;
                    font-size: 9.5pt;
                }}

                /* ----------------- MODERN SCROLLBAR ----------------- */
                QScrollArea {{
                    border: none;
                    background-color: transparent;
                }}

                QScrollBar:vertical {{
                    border: none;
                    background: #f1f5f9;
                    width: 12px;
                    margin: 0px;
                    border-radius: 6px;
                }}

                QScrollBar::handle:vertical {{
                    background: #cbd5e1;
                    min-height: 25px;
                    border-radius: 6px;
                }}

                QScrollBar::handle:vertical:hover {{
                    background: #94a3b8;
                }}

                QScrollBar::handle:vertical:pressed {{
                    background: #64748b;
                }}

                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    border: none;
                    background: none;
                    height: 0px;
                }}

                QScrollBar:horizontal {{
                    border: none;
                    background: #f1f5f9;
                    height: 12px;
                    margin: 0px;
                    border-radius: 6px;
                }}

                QScrollBar::handle:horizontal {{
                    background: #cbd5e1;
                    min-width: 25px;
                    border-radius: 6px;
                }}

                QScrollBar::handle:horizontal:hover {{
                    background: #94a3b8;
                }}

                QScrollBar::handle:horizontal:pressed {{
                    background: #64748b;
                }}

                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    border: none;
                    background: none;
                    width: 0px;
                }}

                /* Progress Bar */
                QProgressBar {{
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #e2e8f0;
                    height: 12px;
                }}
                QProgressBar::chunk {{
                    border-radius: 4px;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00b4d8, stop:1 #0077b6);
                }}

                QToolTip {{
                    background-color: #1e293b;
                    color: #ffffff;
                    border: 1px solid #0f172a;
                    padding: 5px 8px;
                    border-radius: 6px;
                    font-size: 9pt;
                }}
            """

            self.setStyleSheet(stylesheet)

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
        main_tab_layout.setContentsMargins(12, 10, 12, 12)
        main_tab_layout.setSpacing(12)

        top_h_layout = QHBoxLayout()
        top_h_layout.setSpacing(12)
        main_tab_layout.addLayout(top_h_layout, 0)

        # 🗄️ Card: Thông Tin Dữ Liệu
        info_groupbox = QGroupBox("🗄️ Thông Tin Dữ Liệu")
        info_layout = QGridLayout(info_groupbox)
        info_layout.setSpacing(10)
        info_layout.setContentsMargins(12, 16, 12, 12)

        lbl_file = QLabel("Đường dẫn file:")
        lbl_file.setStyleSheet("font-weight: 600; color: #334155;")
        info_layout.addWidget(lbl_file, 0, 0, Qt.AlignLeft | Qt.AlignVCenter)

        self.data_file_path_label = QLabel("...")
        self.data_file_path_label.setObjectName("PathDisplayLabel")
        self.data_file_path_label.setWordWrap(False)
        self.data_file_path_label.setToolTip("Đường dẫn đến file dữ liệu JSON hiện tại.")
        self.data_file_path_label.setMinimumHeight(28)
        info_layout.addWidget(self.data_file_path_label, 0, 1)

        edit_data_button = QPushButton("Edit")
        edit_data_button.setObjectName("LightButton")
        edit_data_button.setMinimumWidth(86)
        edit_data_button.setToolTip("Thay đổi file dữ liệu chính 🖍")
        edit_data_button.clicked.connect(self.change_data_path)
        info_layout.addWidget(edit_data_button, 0, 2, Qt.AlignVCenter)

        lbl_time = QLabel("Thời gian dữ liệu:")
        lbl_time.setStyleSheet("font-weight: 600; color: #334155;")
        info_layout.addWidget(lbl_time, 1, 0, Qt.AlignLeft | Qt.AlignVCenter)

        self.date_range_label = QLabel("...")
        self.date_range_label.setStyleSheet("color: #1e293b; font-weight: 500;")
        self.date_range_label.setToolTip("Ngày bắt đầu và kết thúc của dữ liệu đã tải.")
        info_layout.addWidget(self.date_range_label, 1, 1, Qt.AlignVCenter)

        sync_button = QPushButton("☁ Sync")
        sync_button.setObjectName("SyncButton")
        sync_button.setMinimumWidth(100)
        sync_button.setToolTip("Đồng bộ dữ liệu kết quả XSMB.")
        sync_button.clicked.connect(self.sync_data)
        info_layout.addWidget(sync_button, 1, 2, Qt.AlignVCenter)

        self.sync_url_input = QLineEdit()
        self.sync_url_input.setVisible(False)

        info_layout.setRowStretch(2, 1)
        info_layout.setColumnStretch(0, 0)
        info_layout.setColumnStretch(1, 10)
        info_layout.setColumnStretch(2, 0)
        info_layout.setColumnMinimumWidth(2, 105)
        top_h_layout.addWidget(info_groupbox, 5)

        # 📅 Card: Chọn Ngày Cài Đặt Dự Đoán
        control_groupbox = QGroupBox("📅 Chọn Ngày Cài Đặt Dự Đoán")
        control_layout = QVBoxLayout(control_groupbox)
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(12, 16, 12, 12)

        date_control_frame = QWidget()
        date_control_h_layout = QHBoxLayout(date_control_frame)
        date_control_h_layout.setContentsMargins(0, 0, 0, 0)
        date_control_h_layout.setSpacing(6)

        self.selected_date_edit = QLineEdit()
        self.selected_date_edit.setReadOnly(True)
        self.selected_date_edit.setAlignment(Qt.AlignCenter)
        self.selected_date_edit.setFixedWidth(125)
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

        next_day_button = QPushButton("▶")
        next_day_button.setObjectName("SmallNavButton")
        next_day_button.setToolTip("Chọn ngày kế tiếp trong dữ liệu.")
        next_day_button.clicked.connect(self.select_next_day)
        date_control_h_layout.addWidget(next_day_button)

        self.predict_button = QPushButton("🎯 Dự Đoán")
        self.predict_button.setObjectName("PredictButton")
        self.predict_button.setCursor(Qt.PointingHandCursor)
        self.predict_button.setToolTip("Chạy dự đoán cho ngày đã chọn.")
        self.predict_button.clicked.connect(self.start_prediction_process)
        date_control_h_layout.addWidget(self.predict_button)

        date_control_h_layout.addStretch(1)

        control_layout.addWidget(date_control_frame)

        sort_settings_frame = QWidget()
        sort_layout = QHBoxLayout(sort_settings_frame)
        sort_layout.setContentsMargins(0, 0, 0, 0)
        sort_layout.setSpacing(6)
        sort_layout.setAlignment(Qt.AlignLeft) 

        lbl_sort = QLabel("Sắp xếp:")
        lbl_sort.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lbl_sort.setStyleSheet("font-weight: 600; color: #334155;")
        sort_layout.addWidget(lbl_sort)

        self.pred_sort_combo = QComboBox()
        self.pred_sort_combo.addItems(["Cao ➔ Thấp", "Thấp ➔ Cao", "Custom"])
        self.pred_sort_combo.setToolTip("Chọn cách sắp xếp kết quả dự đoán.")
        self.pred_sort_combo.setFixedWidth(165)
        sort_layout.addWidget(self.pred_sort_combo)

        self.pred_file_btn = QPushButton("🔍 Tìm")
        self.pred_file_btn.setObjectName("LightButton")
        self.pred_file_btn.setMinimumWidth(95)
        self.pred_file_btn.setEnabled(False)
        self.pred_file_btn.setToolTip("Chọn file txt chứa thứ tự sắp xếp (ví dụ: 90-80-03...)")
        self.pred_file_btn.clicked.connect(self.load_predict_sort_file)
        sort_layout.addWidget(self.pred_file_btn)

        self.pred_file_label = QLabel("")
        self.pred_file_label.setStyleSheet("color: gray; font-style: italic; font-size: 9pt;")
        sort_layout.addWidget(self.pred_file_label)
        sort_layout.addStretch(1)

        self.pred_sort_combo.currentIndexChanged.connect(
            lambda idx: self.pred_file_btn.setEnabled(idx == 2)
        )
        control_layout.addWidget(sort_settings_frame)

        self.predict_progress_frame = QWidget()
        predict_progress_v_layout = QVBoxLayout(self.predict_progress_frame)
        predict_progress_v_layout.setContentsMargins(5, 2, 5, 5)
        predict_progress_v_layout.setSpacing(2)
        self.predict_status_label = QLabel("Tiến trình: Chưa chạy")
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

        # 🔀 Card: Danh sách thuật toán
        left_groupbox = QGroupBox("🔀 Danh sách thuật toán")
        left_outer_layout = QVBoxLayout(left_groupbox)
        left_outer_layout.setContentsMargins(10, 14, 10, 10)
        left_outer_layout.setSpacing(6)

        reload_hint_frame = QWidget()
        reload_hint_layout = QHBoxLayout(reload_hint_frame)
        reload_hint_layout.setContentsMargins(0, 0, 0, 0)
        reload_hint_layout.setSpacing(8)

        reload_algo_button = QPushButton("🔄 Tải lại thuật toán")
        reload_algo_button.setObjectName("LightButton")
        reload_algo_button.setToolTip("Quét lại thư mục 'algorithms' và tải lại danh sách 🔃")
        reload_algo_button.clicked.connect(self.reload_algorithms)
        reload_hint_layout.addStretch(1)
        reload_hint_layout.addWidget(reload_algo_button)

        left_outer_layout.addWidget(reload_hint_frame)

        self.algo_scroll_area = QScrollArea()
        self.algo_scroll_area.setWidgetResizable(True)
        self.algo_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.algo_scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.algo_scroll_widget = QWidget()
        self.algo_scroll_widget.setStyleSheet("background-color: transparent;")
        self.algo_scroll_area.setWidget(self.algo_scroll_widget)
        self.algo_list_layout = QVBoxLayout(self.algo_scroll_widget)
        self.algo_list_layout.setAlignment(Qt.AlignTop)
        self.algo_list_layout.setSpacing(6)
        self.algo_list_layout.setContentsMargins(0, 2, 4, 2)
        left_outer_layout.addWidget(self.algo_scroll_area)
        bottom_splitter.addWidget(left_groupbox)

        # 📊 Card: Hiệu suất Kết Hợp
        right_groupbox = QGroupBox("📊 Hiệu suất Kết Hợp")
        right_layout = QVBoxLayout(right_groupbox)
        right_layout.setContentsMargins(10, 14, 10, 10)
        right_layout.setSpacing(8)

        date_range_frame = QWidget()
        date_range_layout = QHBoxLayout(date_range_frame)
        date_range_layout.setContentsMargins(0, 0, 0, 0)
        date_range_layout.setSpacing(5)

        lbl_tu = QLabel("Từ:")
        lbl_tu.setStyleSheet("font-weight: 600; color: #334155;")
        date_range_layout.addWidget(lbl_tu)

        self.perf_start_date_edit = QLineEdit()
        self.perf_start_date_edit.setReadOnly(True)
        self.perf_start_date_edit.setAlignment(Qt.AlignCenter)
        self.perf_start_date_edit.setMinimumWidth(85)
        date_range_layout.addWidget(self.perf_start_date_edit)

        self.perf_start_date_button = QPushButton("📅")
        self.perf_start_date_button.setObjectName("CalendarButton")
        self.perf_start_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.perf_start_date_edit))
        date_range_layout.addWidget(self.perf_start_date_button)

        date_range_layout.addSpacing(4)
        lbl_den = QLabel("Đến:")
        lbl_den.setStyleSheet("font-weight: 600; color: #334155;")
        date_range_layout.addWidget(lbl_den)

        self.perf_end_date_edit = QLineEdit()
        self.perf_end_date_edit.setReadOnly(True)
        self.perf_end_date_edit.setAlignment(Qt.AlignCenter)
        self.perf_end_date_edit.setMinimumWidth(85)
        date_range_layout.addWidget(self.perf_end_date_edit)

        self.perf_end_date_button = QPushButton("📅")
        self.perf_end_date_button.setObjectName("CalendarButton")
        self.perf_end_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.perf_end_date_edit))
        date_range_layout.addWidget(self.perf_end_date_button)

        date_range_layout.addSpacing(6)
        self.perf_calc_button = QPushButton("🧮 Tính Toán")
        self.perf_calc_button.setObjectName("CalcButton")
        self.perf_calc_button.setMinimumWidth(150)
        self.perf_calc_button.clicked.connect(self.calculate_combined_performance)
        date_range_layout.addWidget(self.perf_calc_button)
        right_layout.addWidget(date_range_frame)

        perf_sort_frame = QWidget()
        perf_sort_layout = QHBoxLayout(perf_sort_frame)
        perf_sort_layout.setContentsMargins(0, 0, 0, 0)
        perf_sort_layout.setSpacing(6)
        perf_sort_layout.setAlignment(Qt.AlignLeft)

        lbl_sort_perf = QLabel("Sắp xếp:")
        lbl_sort_perf.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lbl_sort_perf.setStyleSheet("font-weight: 600; color: #334155;")
        perf_sort_layout.addWidget(lbl_sort_perf)

        self.perf_sort_combo = QComboBox()
        self.perf_sort_combo.addItems(["Cao ➔ Thấp", "Thấp ➔ Cao", "Custom"])
        self.perf_sort_combo.setFixedWidth(165)
        perf_sort_layout.addWidget(self.perf_sort_combo)

        self.perf_file_btn = QPushButton("🔍 Tìm")
        self.perf_file_btn.setObjectName("LightButton")
        self.perf_file_btn.setMinimumWidth(95)
        self.perf_file_btn.setEnabled(False)
        self.perf_file_btn.clicked.connect(self.load_perf_sort_file)
        perf_sort_layout.addWidget(self.perf_file_btn)

        self.perf_file_label = QLabel("")
        self.perf_file_label.setStyleSheet("color: gray; font-style: italic; font-size: 9pt;")
        perf_sort_layout.addWidget(self.perf_file_label)
        perf_sort_layout.addStretch(1)

        self.perf_sort_combo.currentIndexChanged.connect(
            lambda idx: self.perf_file_btn.setEnabled(idx == 2)
        )
        right_layout.addWidget(perf_sort_frame)

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

        self.performance_text = QTextEdit()
        self.performance_text.setObjectName("PerformanceTextEdit")
        self.performance_text.setReadOnly(True)
        perf_font = self.get_qfont("code")
        self.performance_text.setFont(perf_font)
        self._setup_performance_text_formats()
        self.load_performance_data()
        right_layout.addWidget(self.performance_text, 1)
        bottom_splitter.addWidget(right_groupbox)

        initial_splitter_sizes = [self.width() // 2, self.width() // 2] if self.width() > 100 else [450, 350]
        bottom_splitter.setSizes(initial_splitter_sizes)

        self.predict_custom_sort_data = []
        self.perf_custom_sort_data = []

        main_logger.debug("Main tab UI setup complete.")

    def _get_loto(self, value) -> str:
        """Lấy 2 chữ số cuối từ một giá trị giải thưởng."""
        if value is None:
            return ""
        s_val = str(value).strip()
        if len(s_val) >= 2 and s_val[-2:].isdigit():
            return s_val[-2:]
        elif s_val.isdigit():
            return f"{int(s_val):02d}"
        return "N/A"

    def setup_kqxs_tab(self):
        """Thiết lập giao diện cho tab Xem KQXS (Chia 2 tab con: Xem Kết Quả & Phân Tích)."""
        main_logger.debug("Setting up KQXS Tab with sub-tabs...")
        
        if self.kqxs_tab_frame.layout():
            QWidget().setLayout(self.kqxs_tab_frame.layout())
            
        main_layout = QVBoxLayout(self.kqxs_tab_frame)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        self.kqxs_sub_tab_widget = QTabWidget()
        main_layout.addWidget(self.kqxs_sub_tab_widget)

        self.view_results_tab = QWidget()
        self._init_kqxs_view_tab_ui(self.view_results_tab)
        self.kqxs_sub_tab_widget.addTab(self.view_results_tab, " 📅 Xem Kết Quả ")

        self.analysis_tab = QWidget()
        self._init_kqxs_analysis_tab_ui(self.analysis_tab)
        self.kqxs_sub_tab_widget.addTab(self.analysis_tab, " 📊 Phân Tích Chuyên Sâu  ")

    def _init_kqxs_view_tab_ui(self, parent_widget):
        """Khởi tạo giao diện xem kết quả ngày (Giao diện cũ)."""
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top_bar_widget = QWidget()
        top_bar_layout = QHBoxLayout(top_bar_widget)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.kqxs_prev_button = QPushButton("◀")
        self.kqxs_prev_button.setObjectName("SmallNavButton")
        self.kqxs_prev_button.setToolTip("Xem kết quả ngày trước đó")
        self.kqxs_prev_button.clicked.connect(self.select_previous_kqxs_day)
        
        self.kqxs_date_label = QLabel("<b>Xổ số Miền Bắc...</b>")
        self.kqxs_date_label.setFont(self.get_qfont("title"))
        self.kqxs_date_label.setAlignment(Qt.AlignCenter)

        self.kqxs_calendar_button = QPushButton("📅")
        self.kqxs_calendar_button.setToolTip("Mở lịch để xem kết quả của ngày khác")
        self.kqxs_calendar_button.setObjectName("CalendarButton")
        self.kqxs_calendar_button.clicked.connect(self.show_kqxs_calendar)
        
        self.kqxs_next_button = QPushButton("▶")
        self.kqxs_next_button.setObjectName("SmallNavButton")
        self.kqxs_next_button.setToolTip("Xem kết quả ngày kế tiếp")
        self.kqxs_next_button.clicked.connect(self.select_next_kqxs_day)

        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(self.kqxs_prev_button)
        top_bar_layout.addWidget(self.kqxs_date_label)
        top_bar_layout.addWidget(self.kqxs_calendar_button)
        top_bar_layout.addWidget(self.kqxs_next_button)
        top_bar_layout.addStretch(1)
        
        layout.addWidget(top_bar_widget)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(5)
        
        left_container = QGroupBox("Bảng Kết Quả")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(5, 10, 5, 5)
        
        results_container = QWidget()
        main_results_layout = QHBoxLayout(results_container)
        main_results_layout.setSpacing(0)
        main_results_layout.setContentsMargins(0,0,0,0)

        prize_names_widget = QWidget()
        prize_names_layout = QVBoxLayout(prize_names_widget)
        prize_names_layout.setContentsMargins(0,0,0,0)
        prize_names_layout.setSpacing(0)
        prize_names_widget.setFixedWidth(100)

        numbers_widget = QWidget()
        numbers_layout = QVBoxLayout(numbers_widget)
        numbers_layout.setContentsMargins(0,0,0,0)
        numbers_layout.setSpacing(0)

        main_results_layout.addWidget(prize_names_widget)
        main_results_layout.addWidget(numbers_widget, 1)

        self.kqxs_result_labels = {}

        def create_label(text="", is_prize_name=False):
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            font = self.get_qfont("bold")
            if is_prize_name:
                font.setPointSize(self.get_font_size("small"))
                label.setFont(font)
                label.setStyleSheet("border: 1px solid #E0E0E0; background-color: #F0F0F0; color: #333;")
            else:
                font.setPointSize(self.get_font_size("title"))
                label.setFont(font)
                label.setStyleSheet("border: 1px solid #E0E0E0; background-color: white; color: #000;")
            return label
        
        def create_centered_row(num_count):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0,0,0,0)
            row_layout.setSpacing(0)
            labels = []
            for _ in range(num_count):
                label = create_label()
                labels.append(label)
                row_layout.addWidget(label, 1)
            return row_widget, labels
        
        prizes = [
            ("db", "Đặc biệt", 1), ("nhat", "Giải nhất", 1), ("nhi", "Giải nhì", 2),
            ("ba", "Giải ba", 6), ("tu", "Giải tư", 4), ("nam", "Giải năm", 6),
            ("sau", "Giải sáu", 3), ("bay", "Giải bảy", 4)
        ]

        prize_names_layout.addStretch(1)
        numbers_layout.addStretch(1)

        for key, name, count in prizes:
            num_rows = 1
            if key in ['ba', 'nam']: num_rows = 2
            
            prize_label_container = QWidget()
            prize_label_layout = QHBoxLayout(prize_label_container)
            prize_label_layout.setContentsMargins(0,0,0,0)
            prize_label = create_label(name, is_prize_name=True)
            prize_label_layout.addWidget(prize_label)
            prize_names_layout.addWidget(prize_label_container, num_rows)
            
            self.kqxs_result_labels[key] = []
            
            if num_rows == 1:
                row_widget, labels = create_centered_row(count)
                if key == 'db':
                    labels[0].setStyleSheet("border: 1px solid #E0E0E0; background-color: #FFFACD; color: red; font-size: 22pt; font-weight: bold;")
                numbers_layout.addWidget(row_widget, 1)
                self.kqxs_result_labels[key] = labels
            else:
                row1_widget, labels1 = create_centered_row(3)
                row2_widget, labels2 = create_centered_row(3)
                numbers_layout.addWidget(row1_widget, 1)
                numbers_layout.addWidget(row2_widget, 1)
                self.kqxs_result_labels[key] = labels1 + labels2
        
        prize_names_layout.addStretch(1)
        numbers_layout.addStretch(1)
        left_layout.addWidget(results_container)
        
        right_container = QGroupBox("Thống Kê Trong Ngày")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(5, 10, 5, 5)
        right_layout.setSpacing(10)

        self.stats_scroll = QScrollArea()
        self.stats_scroll.setWidgetResizable(True)
        self.stats_scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        stats_widget = QWidget()
        self.stats_content_layout = QVBoxLayout(stats_widget)
        self.stats_content_layout.setAlignment(Qt.AlignTop)
        self.stats_content_layout.setSpacing(15)

        self.stats_nhay_label = QLabel("Đang tải...")
        self.stats_nhay_label.setWordWrap(True)
        self.stats_content_layout.addWidget(self._create_styled_stat_box("⚡ Loto về nhiều nháy", self.stats_nhay_label))

        self.stats_roi_label = QLabel("Đang tải...")
        self.stats_roi_label.setWordWrap(True)
        self.stats_content_layout.addWidget(self._create_styled_stat_box("🍂 Loto Rơi (từ hôm qua)", self.stats_roi_label))

        self.stats_top_gan_label = QLabel("Đang tải...")
        self.stats_top_gan_label.setWordWrap(True)
        self.stats_content_layout.addWidget(self._create_styled_stat_box("🥶 Top 3 Gan Lì (Chưa về)", self.stats_top_gan_label))

        self.stats_gan_ve_label = QLabel("Đang tải...")
        self.stats_gan_ve_label.setWordWrap(True)
        self.stats_content_layout.addWidget(self._create_styled_stat_box("🔥 Số Hiếm (Gan đã về hôm nay)", self.stats_gan_ve_label))

        self.stats_head_tail_label = QLabel("Đang tải...")
        self.stats_head_tail_label.setWordWrap(True)
        font_mono = QFont("Consolas", 10)
        font_mono.setStyleHint(QFont.Monospace)
        self.stats_head_tail_label.setFont(font_mono)
        self.stats_content_layout.addWidget(self._create_styled_stat_box("📊 Thống kê Đầu - Đuôi", self.stats_head_tail_label))

        self.stats_scroll.setWidget(stats_widget)
        right_layout.addWidget(self.stats_scroll)

        content_splitter.addWidget(left_container)
        content_splitter.addWidget(right_container)
        content_splitter.setStretchFactor(0, 6)
        content_splitter.setStretchFactor(1, 4)

        layout.addWidget(content_splitter, 1)


    def _init_kqxs_analysis_tab_ui(self, parent_widget):
        """Khởi tạo giao diện tab Phân tích chuyên sâu (Đã Fix lỗi chuyển trang)."""
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        control_group = QGroupBox("Bộ lọc Tra Cứu")
        control_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum) 
        
        control_layout = QGridLayout(control_group)
        control_layout.setContentsMargins(10, 10, 10, 10)
        control_layout.setVerticalSpacing(5)
        
        control_layout.addWidget(QLabel("Nhập số (VD: 68, 86):"), 0, 0)
        self.ana_numbers_edit = QLineEdit()
        self.ana_numbers_edit.setPlaceholderText("Nhập 1 số hoặc bộ số...")
        self.ana_numbers_edit.setToolTip("Nhập số cần tra cứu, cách nhau bởi dấu phẩy.")
        control_layout.addWidget(self.ana_numbers_edit, 0, 1)
        
        self.ana_btn_analyze = QPushButton("🔍 TRA CỨU")
        self.ana_btn_analyze.setObjectName("AccentButton")
        self.ana_btn_analyze.setCursor(Qt.PointingHandCursor)
        self.ana_btn_analyze.setMinimumWidth(125)
        self.ana_btn_analyze.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        control_layout.addWidget(self.ana_btn_analyze, 0, 2, 2, 1)
        
        control_layout.addWidget(QLabel("Thời gian:"), 1, 0)
        date_layout = QHBoxLayout()
        date_layout.setSpacing(5)
        
        self.ana_start_date = QLineEdit()
        self.ana_end_date = QLineEdit()
        self.ana_btn_start = QPushButton("📅"); self.ana_btn_start.setFixedWidth(36)
        self.ana_btn_end = QPushButton("📅"); self.ana_btn_end.setFixedWidth(36)
        
        self.ana_btn_start.clicked.connect(lambda: self.show_calendar_dialog_qt(self.ana_start_date))
        self.ana_btn_end.clicked.connect(lambda: self.show_calendar_dialog_qt(self.ana_end_date))
        
        self.ana_chk_all_time = QCheckBox("Toàn bộ thời gian")
        self.ana_chk_all_time.setChecked(True)
        self.ana_chk_all_time.toggled.connect(self._toggle_ana_date_inputs)
        
        date_layout.addWidget(self.ana_start_date)
        date_layout.addWidget(self.ana_btn_start)
        date_layout.addWidget(QLabel("-"))
        date_layout.addWidget(self.ana_end_date)
        date_layout.addWidget(self.ana_btn_end)
        date_layout.addWidget(self.ana_chk_all_time)
        
        control_layout.addLayout(date_layout, 1, 1)
        control_layout.setColumnStretch(1, 1)
        
        layout.addWidget(control_group)
        self._toggle_ana_date_inputs(True)
        self.ana_btn_analyze.clicked.connect(self._perform_kqxs_analysis)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_box = QGroupBox("Kết Quả Tổng Hợp")
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        self.ana_summary_browser = QTextBrowser()
        self.ana_summary_browser.setOpenExternalLinks(False)
        self.ana_summary_browser.setOpenLinks(False)
        self.ana_summary_browser.anchorClicked.connect(self._on_ana_link_clicked)
        
        left_layout.addWidget(self.ana_summary_browser)
        splitter.addWidget(left_box)
        
        right_box = QGroupBox("Chi Tiết Theo Thời Gian")
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(5, 5, 5, 5)
        self.ana_tree_widget = QtWidgets.QTreeWidget()
        self.ana_tree_widget.setHeaderLabels(["Thời gian", "Số lượng", "Tỉ lệ %", "Ghi chú"])
        self.ana_tree_widget.setColumnWidth(0, 140)
        self.ana_tree_widget.setColumnWidth(1, 70)
        self.ana_tree_widget.setColumnWidth(2, 70)
        right_layout.addWidget(self.ana_tree_widget)
        splitter.addWidget(right_box)
        
        splitter.setSizes([400, 600])
        layout.addWidget(splitter, 1)

    def _toggle_ana_date_inputs(self, checked):
        """Helper để ẩn/hiện ô nhập ngày khi chọn 'Toàn bộ'."""
        enabled = not checked
        self.ana_start_date.setEnabled(enabled)
        self.ana_end_date.setEnabled(enabled)
        self.ana_btn_start.setEnabled(enabled)
        self.ana_btn_end.setEnabled(enabled)

    def _perform_kqxs_analysis(self):
        """Thực hiện logic phân tích số liệu KQXS (Logic Nháy Bộ Số & Link xem chi tiết)."""
        
        nums_str = self.ana_numbers_edit.text().strip()
        if not nums_str:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập ít nhất 1 con số.")
            return
            
        try:
            target_numbers = set()
            for x in nums_str.replace(' ', ',').split(','):
                if x.strip():
                    val = int(x.strip())
                    if 0 <= val <= 99: 
                        target_numbers.add(f"{val:02d}")
            if not target_numbers: raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Lỗi nhập liệu", "Vui lòng nhập các số từ 00 đến 99.")
            return

        target_numbers = sorted(list(target_numbers))
        target_display = ", ".join(target_numbers)
        is_single_search = (len(target_numbers) == 1)
        
        if not self.results:
            QMessageBox.warning(self, "Lỗi", "Chưa có dữ liệu KQXS.")
            return

        sorted_data = sorted(self.results, key=lambda x: x['date'])
        start_date = sorted_data[0]['date']
        end_date = sorted_data[-1]['date']
        
        if not self.ana_chk_all_time.isChecked():
            try:
                s_txt = self.ana_start_date.text()
                e_txt = self.ana_end_date.text()
                if not s_txt or not e_txt: raise ValueError
                s = datetime.datetime.strptime(s_txt, '%d/%m/%Y').date()
                e = datetime.datetime.strptime(e_txt, '%d/%m/%Y').date()
                if s > e: 
                    QMessageBox.warning(self, "Lỗi ngày", "Ngày bắt đầu phải nhỏ hơn ngày kết thúc.")
                    return
                start_date, end_date = s, e
            except ValueError:
                QMessageBox.warning(self, "Lỗi ngày", "Ngày không hợp lệ.")
                return

        filtered_data = [r for r in sorted_data if start_date <= r['date'] <= end_date]
        total_draws = len(filtered_data)
        
        if total_draws == 0:
            self.ana_summary_browser.setHtml("<h3 style='color:red'>Không tìm thấy kỳ quay nào.</h3>")
            self.ana_tree_widget.clear()
            return

        hits_count = 0
        special_hits_count = 0
        yearly_stats = {} 
        
        current_streak = 0
        current_streak_start_date = None
        max_streak = 0
        max_streak_range = "N/A"
        
        current_gap = 0
        gap_start_date = filtered_data[0]['date']
        max_gap = 0
        max_gap_range = "N/A"
        
        max_freq_val = 0
        max_freq_dates = [] 
        
        co_occurrence = Counter()

        def analyze_day_result(result_dict):
            day_loto_strs = []
            keys_to_ignore = {'date', '_id', 'source', 'day_of_week', 'sign', 'created_at', 'updated_at', 'province_name', 'province_id'}
            for k, v in result_dict.items():
                if k in keys_to_ignore: continue
                vals = v if isinstance(v, (list, tuple)) else [v]
                for val in vals:
                    if val is not None:
                        s = str(val).strip()
                        if len(s) >= 2 and s[-2:].isdigit(): day_loto_strs.append(s[-2:])
                        elif len(s) == 1 and s.isdigit(): day_loto_strs.append(f"{int(s):02d}")
            
            counts_per_target = []
            for target in target_numbers:
                counts_per_target.append(day_loto_strs.count(target))
            
            freq_in_day = min(counts_per_target) if counts_per_target else 0
            
            is_hit = freq_in_day > 0
            
            special_val = result_dict.get('special', result_dict.get('dac_biet', ''))
            is_special = False
            if special_val:
                s_str = str(special_val).strip()
                if len(s_str) >= 2 and s_str[-2:] in target_numbers:
                    is_special = True
            
            return is_hit, freq_in_day, day_loto_strs, is_special

        for entry in filtered_data:
            d = entry['date']
            y, m = d.year, d.month
            
            if y not in yearly_stats: 
                yearly_stats[y] = {'draws': 0, 'hits': 0, 'months': {}}
            if m not in yearly_stats[y]['months']:
                yearly_stats[y]['months'][m] = {'draws': 0, 'hits': 0, 'dates': []}
                
            yearly_stats[y]['draws'] += 1
            yearly_stats[y]['months'][m]['draws'] += 1
            
            is_hit, freq, day_lotos_list, is_spec = analyze_day_result(entry['result'])
            
            if is_hit:
                hits_count += 1
                yearly_stats[y]['hits'] += 1
                yearly_stats[y]['months'][m]['hits'] += 1
                
                note = f"{freq} nháy" if freq > 1 else ""
                if is_spec: note = f"{note} (GĐB)" if note else "(GĐB)"
                yearly_stats[y]['months'][m]['dates'].append(f"{d.day} {note}")
                
                if is_spec: special_hits_count += 1
                
                if current_streak == 0: current_streak_start_date = d
                current_streak += 1
                
                if current_streak > max_streak:
                    max_streak = current_streak
                    max_streak_range = f"{current_streak_start_date.strftime('%d/%m/%Y')} - {d.strftime('%d/%m/%Y')}"
                elif current_streak == max_streak and max_streak > 0:
                    max_streak_range = f"{current_streak_start_date.strftime('%d/%m/%Y')} - {d.strftime('%d/%m/%Y')}"

                if current_gap > max_gap:
                    max_gap = current_gap
                    gap_end_date_real = d - datetime.timedelta(days=1)
                    max_gap_range = f"{gap_start_date.strftime('%d/%m/%Y')} - {gap_end_date_real.strftime('%d/%m/%Y')}"
                current_gap = 0
                gap_start_date = d + datetime.timedelta(days=1)
                
                if freq > max_freq_val:
                    max_freq_val = freq
                    max_freq_dates = [d.strftime('%d/%m/%Y')]
                elif freq == max_freq_val and freq > 0:
                    max_freq_dates.append(d.strftime('%d/%m/%Y'))
                
                if is_single_search:
                    target = target_numbers[0]
                    others = [n for n in day_lotos_list if n != target]
                    co_occurrence.update(others)
            else:
                current_streak = 0
                current_streak_start_date = None
                if current_gap == 0: gap_start_date = d
                current_gap += 1

        current_dry_spell = current_gap
        if current_dry_spell > max_gap:
            max_gap = current_dry_spell
            end_gap_date = end_date
            max_gap_range = f"{gap_start_date.strftime('%d/%m/%Y')} - {end_gap_date.strftime('%d/%m/%Y')}"

        
        max_freq_display_html = ""
        if max_freq_val > 0:
            limit_show = 5
            if len(max_freq_dates) <= limit_show:
                max_freq_display_html = ", ".join(max_freq_dates)
            else:
                self._current_max_freq_dates = max_freq_dates 
                shown = ", ".join(max_freq_dates[:3])
                max_freq_display_html = f"{shown}, ... (<a href='cmd:view_max_freq_dates' style='color:#007BFF;'>Xem toàn bộ {len(max_freq_dates)} ngày</a>)"
        else:
            max_freq_display_html = "Chưa xuất hiện lần nào"

        html = f"""
        <style>
            .highlight {{ color: #007bff; font-weight: bold; }}
            .success {{ color: #28a745; font-weight: bold; }}
            .danger {{ color: #dc3545; font-weight: bold; }}
            .warning {{ color: #fd7e14; font-weight: bold; }}
            td {{ padding: 4px 0; vertical-align: top; }}
        </style>
        
        <h3 style='margin:0; color:#333;'>KẾT QUẢ: <span style='color:#d63384; font-size:16pt'>{target_display}</span></h3>
        <div style='color:#666; font-size:9pt; margin-bottom:10px'>
            Giai đoạn: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')} ({total_draws} kỳ)
        </div>
        <hr style='border: 0; border-top: 1px solid #ddd;'>
        
        <table width='100%'>
            <tr>
                <td width='40%'>🔢 <b>Tổng xuất hiện:</b></td>
                <td class='success'>{hits_count} lần <span style='font-weight:normal; color:#333'>({(hits_count/total_draws*100) if total_draws else 0:.2f}%)</span></td>
            </tr>
            <tr>
                <td>🏆 <b>Về Đặc Biệt:</b></td>
                <td class='danger'>{special_hits_count} lần</td>
            </tr>
            <tr>
                <td>⏳ <b>Trung bình cứ:</b></td>
                <td><b>{total_draws/hits_count if hits_count else 0:.1f}</b> kỳ về 1 lần</td>
            </tr>
            <tr>
                <td colspan='2'><hr style='border:0; border-top:1px dashed #ccc'></td>
            </tr>
            <tr>
                <td>🌵 <b>Gan cực đại (Max):</b></td>
                <td><b>{max_gap}</b> ngày <br><span style='font-size:9pt; color:#666'>({max_gap_range})</span></td>
            </tr>
            <tr>
                <td>💧 <b>Gan hiện tại:</b></td>
                <td class='warning'>{current_dry_spell} ngày chưa về</td>
            </tr>
            <tr>
                <td colspan='2'><hr style='border:0; border-top:1px dashed #ccc'></td>
            </tr>
            <tr>
                <td>🔥 <b>Thông liên tiếp (Max):</b></td>
                <td><b>{max_streak}</b> ngày <br><span style='font-size:9pt; color:#666'>({max_streak_range})</span></td>
            </tr>
            <tr>
                <td>⚡ <b>Nhiều nhất 1 ngày:</b></td>
                <td><b>{max_freq_val}</b> nháy <br><span style='font-size:9pt; color:#666'>({max_freq_display_html})</span></td>
            </tr>
        </table>
        """
        
        if is_single_search and hits_count > 0:
            html += "<hr style='border:0; border-top:1px solid #ddd; margin-top:10px'>"
            html += "<div style='margin-bottom:5px'><b>💡 Cặp số hay về cùng (Top 5):</b></div>"
            most_common = co_occurrence.most_common(5)
            for num, cnt in most_common:
                pct = (cnt / hits_count * 100)
                html += f"<div style='margin-left:10px'>- Số <b>{num}</b>: {cnt} lần ({pct:.1f}%)</div>"
                
        self.ana_summary_browser.setHtml(html)
        
        self.ana_tree_widget.clear()
        
        current_year = datetime.date.today().year
        
        for y in sorted(yearly_stats.keys(), reverse=True):
            y_data = yearly_stats[y]
            y_hits = y_data['hits']
            y_draws = y_data['draws']
            y_pct = (y_hits / y_draws * 100) if y_draws else 0
            
            y_note = ""
            if y == current_year: y_note = "(Năm hiện tại)"
            
            item_year = QtWidgets.QTreeWidgetItem(self.ana_tree_widget)
            item_year.setText(0, f"Năm {y}")
            item_year.setText(1, str(y_hits))
            item_year.setText(2, f"{y_pct:.1f}%")
            item_year.setText(3, y_note)
            
            font = item_year.font(0)
            font.setBold(True)
            item_year.setFont(0, font)
            item_year.setBackground(0, QBrush(QColor("#f0f0f0")))
            for i in range(1, 4): item_year.setBackground(i, QBrush(QColor("#f0f0f0")))
            
            for m in sorted(y_data['months'].keys(), reverse=True):
                m_data = y_data['months'][m]
                m_hits = m_data['hits']
                m_draws = m_data['draws']
                m_pct = (m_hits / m_draws * 100) if m_draws else 0
                
                dates_str = ", ".join(m_data['dates'])
                if not dates_str: dates_str = "-"
                else: dates_str = f"Ngày về: {dates_str}"
                
                item_month = QtWidgets.QTreeWidgetItem(item_year)
                item_month.setText(0, f"Tháng {m}")
                item_month.setText(1, str(m_hits))
                item_month.setText(2, f"{m_pct:.1f}%")
                item_month.setText(3, dates_str)
                
                if m_hits > 0:
                    item_month.setForeground(1, QBrush(QColor("#28a745")))
                    item_month.setFont(1, font)
                else:
                    item_month.setForeground(0, QBrush(QColor("#888")))

        self.ana_tree_widget.expandAll()

    def _create_styled_stat_box(self, title, content_label):
        """Helper tạo khung thống kê đẹp mắt."""
        box = QGroupBox(title)
        box.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; color: #0056b3; border: 1px solid #ccc; border-radius: 5px; margin-top: 8px; 
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
        """)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(5, 10, 5, 5)
        content_label.setStyleSheet("color: #333; font-weight: normal;")
        layout.addWidget(content_label)
        return box

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
        self.config_sync_url_edit.setObjectName("SettingsUrlLineEdit")
        self.config_sync_url_edit.setToolTip("URL để tải dữ liệu mới khi nhấn nút 'Sync' ở tab Main.")
        settings_group_layout.addWidget(self.config_sync_url_edit, 1, 1, 1, 3)

        self.auto_sync_checkbox = QCheckBox("  Tự động đồng bộ kết quả quay thưởng hàng ngày 📅  ")
        settings_group_layout.addWidget(self.auto_sync_checkbox, 2, 1, 1, 3, Qt.AlignLeft)

        settings_group_layout.addWidget(QLabel("🔗 Link danh sách thuật toán:"), 3, 0, Qt.AlignLeft)
        self.config_algo_list_url_edit = QLineEdit()
        self.config_algo_list_url_edit.setObjectName("SettingsUrlLineEdit")
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
        

        settings_group_layout.addWidget(QLabel("🚀 Hiệu năng CPU:"), 7, 0, Qt.AlignLeft | Qt.AlignTop)

        perf_frame = QFrame()
        perf_layout = QVBoxLayout(perf_frame)
        perf_layout.setContentsMargins(0,0,0,0)
        perf_layout.setSpacing(5)

        self.set_priority_checkbox = QCheckBox("Giảm ưu tiên tiến trình (nhường CPU cho app khác)")
        self.set_priority_checkbox.setToolTip(
            "Nếu bật, ứng dụng sẽ chạy với ưu tiên thấp hơn, có thể giúp hệ thống mượt hơn khi app chạy nền.\n"
            "Thay đổi có hiệu lực sau khi lưu và khởi động lại app."
        )
        perf_layout.addWidget(self.set_priority_checkbox)

        priority_details_frame = QWidget()
        priority_details_layout = QHBoxLayout(priority_details_frame)
        priority_details_layout.setContentsMargins(20,0,0,0)
        priority_details_layout.addWidget(QLabel("Mức ưu tiên Windows:"))
        self.priority_windows_combo = QComboBox()
        win_priorities = ['IDLE_PRIORITY_CLASS', 'BELOW_NORMAL_PRIORITY_CLASS', 'NORMAL_PRIORITY_CLASS', 
                          'ABOVE_NORMAL_PRIORITY_CLASS', 'HIGH_PRIORITY_CLASS', 'REALTIME_PRIORITY_CLASS']
        self.priority_windows_combo.addItems(win_priorities)
        priority_details_layout.addWidget(self.priority_windows_combo)
        priority_details_layout.addWidget(QLabel("Unix (nice):"))
        self.priority_unix_spinbox = QSpinBox()
        self.priority_unix_spinbox.setRange(-20, 19)
        priority_details_layout.addWidget(self.priority_unix_spinbox)
        priority_details_layout.addStretch(1)
        perf_layout.addWidget(priority_details_frame)

        self.set_priority_checkbox.toggled.connect(priority_details_frame.setEnabled)


        self.enable_throttling_checkbox = QCheckBox("Bật điều tiết CPU (chèn sleep)")
        self.enable_throttling_checkbox.setToolTip(
            "Nếu bật, ứng dụng sẽ chèn một khoảng nghỉ nhỏ vào các vòng lặp tính toán nặng để giảm tải CPU.\n"
            "Có thể làm chậm một chút các tác vụ đó. Thay đổi có hiệu lực ngay."
        )
        perf_layout.addWidget(self.enable_throttling_checkbox)

        throttle_details_frame = QWidget()
        throttle_details_layout = QHBoxLayout(throttle_details_frame)
        throttle_details_layout.setContentsMargins(20,0,0,0)
        throttle_details_layout.addWidget(QLabel("Thời gian sleep (giây):"))
        self.throttle_duration_spinbox = QDoubleSpinBox()
        self.throttle_duration_spinbox.setDecimals(4)
        self.throttle_duration_spinbox.setRange(0.0000, 1.0)
        self.throttle_duration_spinbox.setSingleStep(0.001)
        self.throttle_duration_spinbox.setValue(0.005)
        self.throttle_duration_spinbox.setToolTip("Thời gian nghỉ (tính bằng giây) sẽ được chèn vào. Càng lớn CPU càng giảm, app càng chậm.")
        throttle_details_layout.addWidget(self.throttle_duration_spinbox)
        throttle_details_layout.addStretch(1)
        perf_layout.addWidget(throttle_details_frame)

        self.enable_throttling_checkbox.toggled.connect(throttle_details_frame.setEnabled)

        settings_group_layout.addWidget(perf_frame, 7, 1, 1, 3)


        settings_group_layout.addWidget(QLabel("⚙️ Quản lý file cấu hình khác:"), 9, 0, Qt.AlignLeft)
        self.config_listwidget = QListWidget()
        settings_group_layout.addWidget(self.config_listwidget, 10, 0, 1, 4)
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

        

        self._populate_settings_tab_ui() 
        main_logger.debug("Hoàn tất thiết lập giao diện tab Cài đặt.")

    def setup_help_tab(self):
        """Thiết lập giao diện tab Hướng dẫn sử dụng (Đã chỉnh sửa độ rộng ô chọn ngày)."""
        main_logger.debug("Setting up Help tab UI (Compact)...")
        
        layout = QVBoxLayout(self.help_tab_frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.StyledPanel)
        control_frame.setStyleSheet("QFrame { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 4px; }")
        
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(5, 5, 5, 5)
        control_layout.setSpacing(10)
        
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(5)
        self.guide_mode_group = QButtonGroup(self)
        self.guide_radio_online = QRadioButton("Xem Online")
        self.guide_radio_offline = QRadioButton("Xem Offline")
        self.guide_mode_group.addButton(self.guide_radio_online)
        self.guide_mode_group.addButton(self.guide_radio_offline)
        
        self.guide_radio_online.setChecked(True)
        self.guide_radio_online.toggled.connect(self._on_guide_mode_changed)
        
        mode_layout.addWidget(QLabel("<b>Chế độ:</b>"))
        mode_layout.addWidget(self.guide_radio_online)
        mode_layout.addWidget(self.guide_radio_offline)
        
        control_layout.addLayout(mode_layout)
        
        line1 = QFrame()
        line1.setFrameShape(QFrame.VLine); line1.setFrameShadow(QFrame.Sunken)
        control_layout.addWidget(line1)

        sync_layout = QHBoxLayout()
        sync_layout.setSpacing(5)
        
        self.guide_auto_sync_chk = QCheckBox("Tự động đồng bộ")
        self.guide_auto_sync_chk.setToolTip("Tự động tải hướng dẫn mới nhất về máy tính.")
        
        self.guide_sync_period_combo = QComboBox()
        self.guide_sync_period_combo.addItems(["7 ngày", "10 ngày", "30 ngày", "Tùy chỉnh"])
        self.guide_sync_period_combo.setFixedWidth(125) 
        self.guide_sync_period_combo.currentIndexChanged.connect(self._on_guide_period_changed)
        
        self.guide_custom_days_spin = QSpinBox()
        self.guide_custom_days_spin.setRange(1, 365)
        self.guide_custom_days_spin.setSuffix(" ngày")
        self.guide_custom_days_spin.setFixedWidth(85)
        self.guide_custom_days_spin.setVisible(False)

        sync_layout.addWidget(self.guide_auto_sync_chk)
        sync_layout.addWidget(self.guide_sync_period_combo)
        sync_layout.addWidget(self.guide_custom_days_spin)
        
        control_layout.addLayout(sync_layout)

        line2 = QFrame()
        line2.setFrameShape(QFrame.VLine); line2.setFrameShadow(QFrame.Sunken)
        control_layout.addWidget(line2)

        btn_layout = QHBoxLayout()
        self.guide_sync_btn = QPushButton("🔄 Đồng bộ ngay")
        self.guide_sync_btn.setToolTip("Tải dữ liệu mới nhất từ Server về máy.")
        self.guide_sync_btn.clicked.connect(self._sync_guide_now)
        
        self.guide_reload_btn = QPushButton("Tải lại")
        self.guide_reload_btn.setToolTip("Tải lại giao diện các tab.")
        self.guide_reload_btn.clicked.connect(self._load_guide_interface)

        btn_layout.addWidget(self.guide_sync_btn)
        btn_layout.addWidget(self.guide_reload_btn)
        
        control_layout.addLayout(btn_layout)
        control_layout.addStretch(1)

        layout.addWidget(control_frame)

        self.guide_sub_tab_widget = QTabWidget()
        self.guide_sub_tab_widget.setDocumentMode(True)
        self.guide_sub_tab_widget.currentChanged.connect(self._on_guide_sub_tab_changed)
        
        layout.addWidget(self.guide_sub_tab_widget)

        self.guide_data_list = [] 

        self._load_guide_config()
        self._load_guide_interface()
        
        QTimer.singleShot(5000, self._check_auto_sync_guide)

    def _on_guide_period_changed(self, index):
        """Hiện/Ẩn spinbox tùy chỉnh ngày."""
        self.guide_custom_days_spin.setVisible(index == 3)

    def _on_guide_mode_changed(self, checked):
        if checked:
            self._load_guide_interface()

    def _load_guide_config(self):
        """Đọc cấu hình guide từ file settings.ini."""
        if self.config.has_section('GUIDE'):
            auto_sync = self.config.getboolean('GUIDE', 'auto_sync', fallback=False)
            days = self.config.getint('GUIDE', 'sync_days', fallback=7)
            last_sync = self.config.get('GUIDE', 'last_sync_date', fallback="")
            
            self.guide_auto_sync_chk.setChecked(auto_sync)
            
            if days == 7: self.guide_sync_period_combo.setCurrentIndex(0)
            elif days == 10: self.guide_sync_period_combo.setCurrentIndex(1)
            elif days == 30: self.guide_sync_period_combo.setCurrentIndex(2)
            else: 
                self.guide_sync_period_combo.setCurrentIndex(3)
                self.guide_custom_days_spin.setValue(days)
        else:
            self.guide_auto_sync_chk.setChecked(False)
            self.guide_sync_period_combo.setCurrentIndex(0)

    def _save_guide_config(self):
        """Lưu cấu hình guide vào settings.ini."""
        if not self.config.has_section('GUIDE'):
            self.config.add_section('GUIDE')
        
        self.config.set('GUIDE', 'auto_sync', str(self.guide_auto_sync_chk.isChecked()))
        
        idx = self.guide_sync_period_combo.currentIndex()
        days = 7
        if idx == 1: days = 10
        elif idx == 2: days = 30
        elif idx == 3: days = self.guide_custom_days_spin.value()
        
        self.config.set('GUIDE', 'sync_days', str(days))
        
        self.save_config()

    def _sync_guide_now(self):
        """Bắt đầu quá trình đồng bộ."""
        if hasattr(self, 'guide_sync_worker_thread') and self.guide_sync_worker_thread.isRunning():
            QMessageBox.warning(self, "Đang chạy", "Quá trình đồng bộ đang diễn ra.")
            return

        self.guide_sync_btn.setEnabled(False)
        self.guide_reload_btn.setEnabled(False)
        self.update_status("Đang đồng bộ hướng dẫn...")

        index_url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/guide/index.txt"
        
        self.guide_sync_thread = QThread()
        self.guide_sync_worker = GuideSyncWorker(self.base_dir, index_url)
        self.guide_sync_worker.moveToThread(self.guide_sync_thread)
        
        self.guide_sync_worker.progress_signal.connect(lambda msg: self.update_status(msg))
        self.guide_sync_worker.finished_signal.connect(self._on_guide_sync_finished)
        
        self.guide_sync_thread.started.connect(self.guide_sync_worker.run_sync)
        self.guide_sync_thread.finished.connect(self.guide_sync_thread.deleteLater)
        
        self.guide_sync_thread.start()

    def _on_guide_sync_finished(self, success, message):
        self.guide_sync_btn.setEnabled(True)
        self.guide_reload_btn.setEnabled(True)
        self.guide_sync_thread.quit()
        
        if success:
            if not self.config.has_section('GUIDE'): self.config.add_section('GUIDE')
            self.config.set('GUIDE', 'last_sync_date', datetime.date.today().strftime("%Y-%m-%d"))
            self.save_config()
            
            QMessageBox.information(self, "Thành công", message)
            
            if self.guide_radio_offline.isChecked():
                self._load_guide_interface()
            else:
                reply = QMessageBox.question(self, "Chuyển chế độ", "Dữ liệu đã tải về. Bạn có muốn chuyển sang chế độ Xem Offline không?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.guide_radio_offline.setChecked(True)
        else:
            QMessageBox.critical(self, "Lỗi đồng bộ", message)
            self.update_status(message)

    def _check_auto_sync_guide(self):
        """Kiểm tra xem có cần tự động đồng bộ không."""
        if not self.guide_auto_sync_chk.isChecked():
            return

        last_sync_str = self.config.get('GUIDE', 'last_sync_date', fallback="")
        if not last_sync_str:
            main_logger.info("Chưa đồng bộ lần nào. Auto-sync kích hoạt.")
            self._sync_guide_now()
            return

        try:
            last_date = datetime.datetime.strptime(last_sync_str, "%Y-%m-%d").date()
            today = datetime.date.today()
            
            idx = self.guide_sync_period_combo.currentIndex()
            threshold_days = 7
            if idx == 1: threshold_days = 10
            elif idx == 2: threshold_days = 30
            elif idx == 3: threshold_days = self.guide_custom_days_spin.value()
            
            delta = (today - last_date).days
            if delta >= threshold_days:
                main_logger.info(f"Auto-sync kích hoạt (Lần cuối: {delta} ngày trước).")
                self._sync_guide_now()
                
        except ValueError:
            pass

    def _load_guide_interface(self):
        """Tải danh sách các tab con dựa trên index (Online hoặc Offline)."""
        self.guide_sub_tab_widget.clear()
        self.guide_data_list = []
        
        is_online = self.guide_radio_online.isChecked()
        index_content = ""

        if is_online:
            self.update_status("Đang tải mục lục hướng dẫn Online...")
            url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/guide/index.txt"
            content = self._fetch_online_content(url, service_type="generic")
            if content:
                index_content = content
            else:
                self.guide_sub_tab_widget.addTab(QLabel("Không thể tải mục lục Online."), " Lỗi ")
                return
        else:
            guide_dir = self.base_dir / "guide"
            index_path = guide_dir / "index.txt"
            if not index_path.exists():
                lbl = QLabel("Chưa có dữ liệu Offline.\nVui lòng nhấn nút 'Đồng bộ ngay' để tải về.")
                lbl.setAlignment(Qt.AlignCenter)
                self.guide_sub_tab_widget.addTab(lbl, " Thông báo ")
                return
            
            try:
                index_content = index_path.read_text(encoding='utf-8')
            except Exception as e:
                self.guide_sub_tab_widget.addTab(QLabel(f"Lỗi đọc file index: {e}"), " Lỗi ")
                return

        pattern = re.compile(r"\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]")
        matches = pattern.findall(index_content)
        
        if not matches:
            self.guide_sub_tab_widget.addTab(QLabel("Mục lục trống hoặc sai định dạng."), " Trống ")
            return

        for g_id, link, info in matches:
            self.guide_data_list.append({
                'id': g_id,
                'link': link,
                'info': info
            })
            
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            browser.setHtml(f"<h3 style='color:gray'>Đang tải nội dung cho: {info}...</h3>")
            
            padded_title = f" {info} "
            
            self.guide_sub_tab_widget.addTab(browser, padded_title)

        self.update_status(f"Đã tải {len(matches)} mục hướng dẫn.")
        
        if self.guide_sub_tab_widget.count() > 0:
            self._on_guide_sub_tab_changed(0)

    def _on_guide_sub_tab_changed(self, index):
        """Khi chuyển tab con, tải nội dung HTML tương ứng."""
        if index < 0 or index >= len(self.guide_data_list):
            return
            
        current_widget = self.guide_sub_tab_widget.widget(index)
        if not isinstance(current_widget, QTextBrowser):
            return
            
        
        data = self.guide_data_list[index]
        is_online = self.guide_radio_online.isChecked()
        
        html_content = ""
        
        if is_online:
            url = data['link']
            content = self._fetch_online_content(url, service_type="generic")
            if content:
                html_content = content
            else:
                html_content = "<h3 style='color:red'>Lỗi tải nội dung từ Server.</h3>"
        else:
            safe_id = "".join(c for c in data['id'] if c.isalnum() or c in ('-','_'))
            file_path = self.base_dir / "guide" / f"{safe_id}.txt"
            
            if file_path.exists():
                try:
                    html_content = file_path.read_text(encoding='utf-8')
                except Exception as e:
                    html_content = f"<h3 style='color:red'>Lỗi đọc file: {e}</h3>"
            else:
                html_content = f"<h3 style='color:orange'>File offline không tồn tại ({file_path.name}).<br>Vui lòng Đồng bộ lại.</h3>"

        font = self.get_qfont("base")
        # font.setPointSize(font.pointSize() + 1)
        current_widget.setFont(font)
        
        if not is_online:
            current_widget.setSearchPaths([str(self.base_dir / "guide")])
            
        current_widget.setHtml(html_content)

    
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
        update_settings_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

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
        self.update_check_button = QPushButton("🔄 Kiểm tra cập nhật")
        self.update_check_button.clicked.connect(self._handle_check_for_updates_thread)
        save_and_check_layout.addWidget(self.update_check_button)
        save_and_check_layout.addStretch(1)
        update_settings_form.addRow(save_and_check_layout)

        update_group_layout_main.addWidget(update_settings_widget)

        update_content_splitter = QSplitter(Qt.Horizontal)

        update_info_container_widget = QWidget()
        update_info_layout = QVBoxLayout(update_info_container_widget)
        update_info_layout.setContentsMargins(0,0,0,0)
        update_info_layout.addWidget(QLabel("<b>📥Thông tin cập nhật:</b>"))
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
        commit_history_layout.addWidget(QLabel("<b>📖Lịch sử cập nhật chương trình:</b>"))
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

    def _fetch_online_content(self, url: str, timeout=15, service_type="generic") -> str | None:
        """
        Tải nội dung từ URL.
        service_type có thể là "data_sync", "update_check", "algo_list", "commit_history" để kiểm tra trạng thái cụ thể.
        """
        import requests

        server_online_flag = True
        server_name_for_message = "máy chủ"

        if service_type == "data_sync":
            if hasattr(self, '_data_sync_server_online') and self._data_sync_server_online is False:
                server_online_flag = False
                server_name_for_message = "Server Data Sync"
        elif service_type in ["update_check", "commit_history"]:
            if hasattr(self, '_update_server_online') and self._update_server_online is False:
                server_online_flag = False
                server_name_for_message = "Server Update"

        if not server_online_flag:
            self.update_logger.warning(f"Từ chối tải từ {url} do {server_name_for_message} đang offline.")
            self.update_status(f"Không thể tải từ {url.split('/')[-1]} (mạng offline).")
            return None

        self.update_logger.info(f"Đang tải nội dung từ: {url} (Service: {service_type})")
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

    def _parse_markdown_update_list(self, md_content: str) -> str:
         self.update_logger.info("Đang phân tích danh sách cập nhật Markdown...")
         if not md_content:
             return "<p>Không có nội dung cập nhật để hiển thị.</p>"

         html_output = []
         font_family_code = self.get_qfont('code').family()
         font_size_code = self.get_font_size('code')
         
         html_output.append(f"<div style='font-family: \"{font_family_code}\", monospace; font-size: {font_size_code}pt; line-height: 1.4;'>")
         
         update_entries_raw = re.split(r'(?=### \d{2}/\d{2}/\d{4})', md_content)
         
         entries_found = 0
         first_entry_processed = False

         for entry_raw in update_entries_raw:
             entry_raw = entry_raw.strip()
             if not entry_raw or entry_raw.lower().startswith("# update list"):
                 continue

             if first_entry_processed:
                 html_output.append("<hr style='border:none; border-top:1px dashed #ccc; margin:15px 0;'>")
             first_entry_processed = True

             lines = entry_raw.splitlines()
             if not lines:
                 continue

             date_line = lines.pop(0).strip() 
             date_match = re.match(r"### (\d{2}/\d{2}/\d{4})", date_line)
             date_str = date_match.group(1) if date_match else "Không rõ ngày"
             
             html_output.append(f"<div style='margin-bottom: 10px;'>")
             html_output.append(f"<p style='margin-top:0; margin-bottom: 3px;'><b style='color: red;'>Ngày cập nhật: {date_str}</b></p>")

             version_line_found = False
             notes_content_html = ""
             
             for line_content in lines:
                 line_strip = line_content.strip()
                 
                 if not version_line_found:
                     version_match = re.match(r"\*\*(Update ver .*?|Update \[.*?\]\(.*?\)|Update .*?)\*\*", line_strip, re.IGNORECASE)
                     if version_match:
                         version_text_raw = version_match.group(1).strip()
                         version_text_html = re.sub(r"\[([^\]]+?)\]\(([^)]+?)\)", r"<a href='\2' style='color: #0056b3; text-decoration:none;'>\1</a>", version_text_raw)
                         html_output.append(f"<p style='margin-top:0; margin-bottom: 5px;'><b style='color: blue;'>Phiên bản: {version_text_html}</b></p>")
                         version_line_found = True
                         continue
                 
                 if line_strip:
                     processed_line_html = re.sub(r"\[([^\]]+?)\]\(([^)]+?)\)", r"<a href='\2' style='color: #0056b3; text-decoration:none;'>\1</a>", line_content)
                     if processed_line_html.strip().lower() == "<br>" or processed_line_html.strip().lower() == "<br><br>":
                         notes_content_html += processed_line_html.strip()
                     else:
                         notes_content_html += processed_line_html + "<br>"
             
             if notes_content_html:
                 if notes_content_html.endswith("<br>"):
                     original_last_note_line = ""
                     temp_notes_lines_for_check = [l.strip() for l in lines if l.strip()]
                     if temp_notes_lines_for_check:
                         for l_idx in range(len(lines)-1, -1, -1):
                             current_line_to_check = lines[l_idx].strip()
                             is_a_version_line = bool(re.match(r"\*\*(Update ver .*?|Update \[.*?\]\(.*?\)|Update .*?)\*\*", current_line_to_check, re.IGNORECASE))
                             if not is_a_version_line :
                                 original_last_note_line = current_line_to_check.lower()
                                 break
                     if not (original_last_note_line == "<br>" or original_last_note_line == "<br><br>"):
                         notes_content_html = notes_content_html[:-4]

                 html_output.append("<b>Nội dung:</b><br><div style='padding-left: 15px; margin-top: 3px;'>")
                 html_output.append(notes_content_html)
                 html_output.append("</div>")

             html_output.append("</div>")
             entries_found +=1

         if entries_found == 0:
             html_output.append("<p><i>Không có mục cập nhật nào được tìm thấy hoặc định dạng file không đúng.</i></p>")

         html_output.append("</div>")
         return "".join(html_output)

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
            status_message_for_bar = " Có bản cập nhật mới!"
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
            
            msg_box.setTextFormat(Qt.RichText)
            msg_box.setText(f" Đã tìm thấy phiên bản mới: <b>{version_text}</b> (Ngày: {date_text})")
            
            informative_html_content = f"<p>Nội dung cập nhật:</p>{notes_text}<p>Bạn có muốn cập nhật ngay không?</p>"
            msg_box.setInformativeText(informative_html_content)

            update_button = msg_box.addButton(" Cập nhật ngay", QMessageBox.AcceptRole)
            skip_button = msg_box.addButton(" Bỏ qua", QMessageBox.RejectRole)
            
            if notification_frequency == 'every_startup':
                 dont_notify_again_button = msg_box.addButton("Không hỏi lại bản này", QMessageBox.DestructiveRole)
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

            original_text = self.copy_account_button_update_tab.text()
            self.copy_account_button_update_tab.setText("COPY!")
            self.copy_account_button_update_tab.setEnabled(False)

            QTimer.singleShot(2000, lambda: (
                self.copy_account_button_update_tab.setText(original_text),
                self.copy_account_button_update_tab.setEnabled(True)
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
        for json_file in self.algorithms_dir.glob("*.json"):
            if json_file.is_file() and is_json_bundle_file(json_file):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        bundle_data = json.load(f)
                    if bundle_data.get("bundle_id") == target_id or bundle_data.get("session_id") == target_id:
                        meta = {
                            "id": bundle_data.get("bundle_id"),
                            "name": bundle_data.get("bundle_name"),
                            "auth": bundle_data.get("trained_by", "AI Optimizer"),
                            "date": bundle_data.get("trained_date", ""),
                        }
                        return json_file, meta
                except Exception:
                    continue
        return None, None

    
    
    

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
            default_set_process_priority = True
            default_priority_windows = 'BELOW_NORMAL_PRIORITY_CLASS'
            default_priority_unix = 5
            default_enable_cpu_throttling = True
            default_throttle_sleep_duration = 0.005

            if not self.config.has_section('DATA'):
                self.config.add_section('DATA')
            if not self.config.has_section('UI'):
                self.config.add_section('UI')
            if not self.config.has_section('UPDATE_CHECK'):
                self.config.add_section('UPDATE_CHECK')
            if not self.config.has_section('PERFORMANCE'):
                self.config.add_section('PERFORMANCE')


            if hasattr(self, 'config_data_path_edit'):
                data_file = self.config.get('DATA', 'data_file', fallback=default_data_path)
                self.config_data_path_edit.setText(data_file)
            else: main_logger.warning("Widget 'config_data_path_edit' không tìm thấy.")

            if hasattr(self, 'config_sync_url_edit'):
                sync_url = self.config.get('DATA', 'sync_url', fallback=default_sync_url)
                self.config_sync_url_edit.setText(sync_url)
            else: main_logger.warning("Widget 'config_sync_url_edit' không tìm thấy.")

            if hasattr(self, 'config_algo_list_url_edit'):
                algo_list_url = self.config.get('DATA', 'algo_list_url', fallback=default_algo_list_url)
                self.config_algo_list_url_edit.setText(algo_list_url)
            else: main_logger.warning("Widget 'config_algo_list_url_edit' không tìm thấy.")

            if hasattr(self, 'auto_sync_checkbox'):
                auto_sync = self.config.getboolean('DATA', 'auto_sync_on_startup', fallback=default_auto_sync)
                self.auto_sync_checkbox.setChecked(auto_sync)
            else: main_logger.warning("Widget 'auto_sync_checkbox' không tìm thấy.")

            if hasattr(self, 'window_width_edit'):
                width_str = self.config.get('UI', 'width', fallback=str(default_width))
                self.window_width_edit.setText(width_str)
            else: main_logger.warning("Widget 'window_width_edit' không tìm thấy.")

            if hasattr(self, 'window_height_edit'):
                height_str = self.config.get('UI', 'height', fallback=str(default_height))
                self.window_height_edit.setText(height_str)
            else: main_logger.warning("Widget 'window_height_edit' không tìm thấy.")

            if hasattr(self, 'theme_font_family_base_combo'):
                font_family_to_set = self.font_family_base
                index = self.theme_font_family_base_combo.findText(font_family_to_set, Qt.MatchFixedString)
                if index >= 0:
                    self.theme_font_family_base_combo.setCurrentIndex(index)
                else:
                    main_logger.warning(f"Font '{font_family_to_set}' không tìm thấy trong combo, dùng index 0.")
                    self.theme_font_family_base_combo.setCurrentIndex(0)
            else: main_logger.warning("Widget 'theme_font_family_base_combo' không tìm thấy.")

            if hasattr(self, 'theme_font_size_base_spinbox'):
                font_size_to_set = self.font_size_base
                self.theme_font_size_base_spinbox.setValue(font_size_to_set)
            else: main_logger.warning("Widget 'theme_font_size_base_spinbox' không tìm thấy.")

            if hasattr(self, 'auto_check_update_checkbox'):
                auto_check = self.config.getboolean('UPDATE_CHECK', 'auto_check_on_startup', fallback=default_auto_check_update)
                self.auto_check_update_checkbox.setChecked(auto_check)
                if hasattr(self, 'update_notification_combo'):
                    self.update_notification_combo.setEnabled(auto_check)
            else: main_logger.warning("Widget 'auto_check_update_checkbox' không tìm thấy.")

            if hasattr(self, 'update_notification_combo'):
                freq = self.config.get('UPDATE_CHECK', 'notification_frequency', fallback=default_update_notification_frequency)
                idx = self.update_notification_combo.findData(freq)
                if idx != -1:
                    self.update_notification_combo.setCurrentIndex(idx)
                else:
                    idx_fallback = self.update_notification_combo.findData(default_update_notification_frequency)
                    if idx_fallback != -1: self.update_notification_combo.setCurrentIndex(idx_fallback)
                    else: self.update_notification_combo.setCurrentIndex(0)
            else: main_logger.warning("Widget 'update_notification_combo' không tìm thấy.")
            
            if hasattr(self, 'set_priority_checkbox'):
                set_prio = self.config.getboolean('PERFORMANCE', 'set_process_priority', fallback=default_set_process_priority)
                self.set_priority_checkbox.setChecked(set_prio)
                priority_details_widget = self.priority_windows_combo.parentWidget() if hasattr(self, 'priority_windows_combo') else None
                if priority_details_widget:
                    priority_details_widget.setEnabled(set_prio)
            else: main_logger.warning("Widget 'set_priority_checkbox' không tìm thấy.")

            if hasattr(self, 'priority_windows_combo'):
                prio_win_str = self.config.get('PERFORMANCE', 'priority_level_windows', fallback=default_priority_windows)
                idx_win = self.priority_windows_combo.findText(prio_win_str, Qt.MatchFixedString)
                if idx_win != -1: self.priority_windows_combo.setCurrentIndex(idx_win)
                else: self.priority_windows_combo.setCurrentText(default_priority_windows)
            else: main_logger.warning("Widget 'priority_windows_combo' không tìm thấy.")
            
            if hasattr(self, 'priority_unix_spinbox'):
                prio_unix_val = self.config.getint('PERFORMANCE', 'priority_level_unix', fallback=default_priority_unix)
                self.priority_unix_spinbox.setValue(prio_unix_val)
            else: main_logger.warning("Widget 'priority_unix_spinbox' không tìm thấy.")

            if hasattr(self, 'enable_throttling_checkbox'):
                enable_th = self.config.getboolean('PERFORMANCE', 'enable_cpu_throttling', fallback=default_enable_cpu_throttling)
                self.enable_throttling_checkbox.setChecked(enable_th)
                throttle_details_widget = self.throttle_duration_spinbox.parentWidget() if hasattr(self, 'throttle_duration_spinbox') else None
                if throttle_details_widget:
                    throttle_details_widget.setEnabled(enable_th)
            else: main_logger.warning("Widget 'enable_throttling_checkbox' không tìm thấy.")

            if hasattr(self, 'throttle_duration_spinbox'):
                try:
                    th_dur_str = self.config.get('PERFORMANCE', 'throttle_sleep_duration', fallback=str(default_throttle_sleep_duration))
                    th_dur = float(th_dur_str)
                except ValueError:
                    main_logger.warning(f"Invalid float value for throttle_sleep_duration: '{th_dur_str}'. Using default.")
                    th_dur = default_throttle_sleep_duration
                self.throttle_duration_spinbox.setValue(th_dur)
            else: main_logger.warning("Widget 'throttle_duration_spinbox' không tìm thấy.")

        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            main_logger.error(f"Lỗi config (section/option) khi điền tab Cài đặt: {e}. Có thể cần tạo lại config.", exc_info=True)
            QMessageBox.warning(self, "Lỗi Config", f"Thiếu section/option trong file config:\n{e}\nMột số cài đặt có thể không được tải đúng.")
        except ValueError as e:
            main_logger.error(f"Lỗi giá trị (ValueError) khi điền tab Cài đặt: {e}. Kiểm tra kiểu dữ liệu trong config.", exc_info=True)
            QMessageBox.warning(self, "Lỗi Giá Trị Config", f"Giá trị không hợp lệ trong file config:\n{e}\nMột số cài đặt có thể không được tải đúng.")
        except Exception as e:
            main_logger.error(f"Lỗi không mong muốn khi điền tab Cài đặt: {e}", exc_info=True)
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
        self.config['PERFORMANCE'] = {
            'set_process_priority': 'True',
            'priority_level_windows': 'BELOW_NORMAL_PRIORITY_CLASS',
            'priority_level_unix': '5',
            'enable_cpu_throttling': 'True',
            'throttle_sleep_duration': '0.005'
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
            if hasattr(self, 'config_data_path_edit'):
                self.config.set('DATA', 'data_file', self.config_data_path_edit.text().strip())
            if hasattr(self, 'config_sync_url_edit'):
                self.config.set('DATA', 'sync_url', self.config_sync_url_edit.text().strip())
            if hasattr(self, 'config_algo_list_url_edit'):
                self.config.set('DATA', 'algo_list_url', self.config_algo_list_url_edit.text().strip())
            if hasattr(self, 'auto_sync_checkbox'):
                self.config.set('DATA', 'auto_sync_on_startup', str(self.auto_sync_checkbox.isChecked()))

            if not self.config.has_section('UI'): self.config.add_section('UI')
            width_str = self.window_width_edit.text().strip() if hasattr(self, 'window_width_edit') else str(self.loaded_width)
            height_str = self.window_height_edit.text().strip() if hasattr(self, 'window_height_edit') else str(self.loaded_height)
            try: w = int(width_str) if width_str.isdigit() else self.loaded_width
            except ValueError: w = self.loaded_width
            try: h = int(height_str) if height_str.isdigit() else self.loaded_height
            except ValueError: h = self.loaded_height
            self.config.set('UI', 'width', str(w))
            self.config.set('UI', 'height', str(h))
            self.loaded_width = w
            self.loaded_height = h

            font_family = self.theme_font_family_base_combo.currentText() if hasattr(self, 'theme_font_family_base_combo') else self.font_family_base
            font_size = str(self.theme_font_size_base_spinbox.value()) if hasattr(self, 'theme_font_size_base_spinbox') else str(self.font_size_base)
            self.config.set('UI', 'font_family_base', font_family)
            self.config.set('UI', 'font_size_base', font_size)
            self.font_family_base = font_family
            self.font_size_base = int(font_size)


            if not self.config.has_section('UPDATE_CHECK'): self.config.add_section('UPDATE_CHECK')
            if hasattr(self, 'auto_check_update_checkbox'):
                self.config.set('UPDATE_CHECK', 'auto_check_on_startup', str(self.auto_check_update_checkbox.isChecked()))
            if hasattr(self, 'update_notification_combo'):
                self.config.set('UPDATE_CHECK', 'notification_frequency', self.update_notification_combo.currentData())

            if not self.config.has_section('PERFORMANCE'): self.config.add_section('PERFORMANCE')
            if hasattr(self, 'set_priority_checkbox'):
                self.config.set('PERFORMANCE', 'set_process_priority', str(self.set_priority_checkbox.isChecked()))
            if hasattr(self, 'priority_windows_combo'):
                self.config.set('PERFORMANCE', 'priority_level_windows', self.priority_windows_combo.currentText())
            if hasattr(self, 'priority_unix_spinbox'):
                self.config.set('PERFORMANCE', 'priority_level_unix', str(self.priority_unix_spinbox.value()))
            
            if hasattr(self, 'enable_throttling_checkbox'):
                enable_throttle_val = self.enable_throttling_checkbox.isChecked()
                self.config.set('PERFORMANCE', 'enable_cpu_throttling', str(enable_throttle_val))
                self.cpu_throttling_enabled = enable_throttle_val
            if hasattr(self, 'throttle_duration_spinbox'):
                throttle_duration_val = self.throttle_duration_spinbox.value()
                self.config.set('PERFORMANCE', 'throttle_sleep_duration', f"{throttle_duration_val:.4f}")
                self.throttle_sleep_duration = throttle_duration_val
            
            if self.cpu_throttling_enabled:
                main_logger.info(f"CPU Throttling applied from settings: Enabled, Duration={self.throttle_sleep_duration:.4f}s")
            else:
                main_logger.info(f"CPU Throttling applied from settings: Disabled")


            if hasattr(self, 'algorithms'):
                 for algo_name, algo_data in self.algorithms.items():
                     chk_enable = algo_data.get('chk_enable')
                     chk_weight = algo_data.get('chk_weight')
                     weight_entry = algo_data.get('weight_entry')
                     if not chk_enable or not chk_weight or not weight_entry:
                         main_logger.warning(f"Thiếu widget UI cho thuật toán '{algo_name}' khi lưu config.")
                         continue

                     config_section_name = algo_name
                     if not self.config.has_section(config_section_name):
                         self.config.add_section(config_section_name)

                     self.config.set(config_section_name, 'enabled', str(chk_enable.isChecked()))
                     self.config.set(config_section_name, 'weight_enabled', str(chk_weight.isChecked()))
                     
                     value_to_save = weight_entry.text().strip()
                     if not self._is_valid_float_str(value_to_save):
                         value_to_save = "1.0"
                         weight_entry.setText(value_to_save)
                     self.config.set(config_section_name, 'weight_value', value_to_save)

            self.save_config("settings.ini")

            if hasattr(self, 'sync_url_input') and hasattr(self, 'config_sync_url_edit'):
                self.sync_url_input.setText(self.config_sync_url_edit.text().strip())
            
            self._apply_window_size_from_config()
            

            self.update_status("Đã lưu cấu hình vào settings.ini.")
            QMessageBox.information(self, "Lưu Thành Công",
                                    "Cấu hình đã được lưu vào settings.ini.\n"
                                    "Lưu ý: Một số thay đổi (font, ưu tiên tiến trình) yêu cầu khởi động lại ứng dụng để có hiệu lực đầy đủ.\n"
                                    "Điều tiết CPU có hiệu lực ngay.")

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
                
                self.available_kqxs_dates = {r['date'] for r in self.results}
                if hasattr(self, 'update_kqxs_tab'):
                    self.update_kqxs_tab(end_date)

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
    def _cleanup_old_backups(self, target_file: Path, keep_limit: int = 3):
        """
        Tìm và xóa các file backup cũ, chỉ giữ lại 'keep_limit' file mới nhất.
        Dựa trên tên file để sắp xếp (vì tên chứa ngày giờ: .bak-YYYYMMDDHHMMSS).
        """
        try:
            parent_dir = target_file.parent.resolve()
            
            base_name = target_file.name
            
            backup_files = []
            if parent_dir.exists():
                for f in parent_dir.iterdir():
                    if f.is_file() and f.name.startswith(f"{base_name}.bak-"):
                        backup_files.append(f)

            backup_files.sort(key=lambda x: x.name, reverse=True)

            main_logger.info(f"Tìm thấy {len(backup_files)} file backup.")

            if len(backup_files) <= keep_limit:
                return

            files_to_delete = backup_files[keep_limit:]
            
            deleted_count = 0
            for f in files_to_delete:
                try:
                    f.unlink()
                    deleted_count += 1
                    main_logger.info(f"Cleaned up old backup: {f.name}")
                except OSError as e:
                    main_logger.warning(f"Failed to delete old backup {f.name}: {e}")
            
            if deleted_count > 0:
                main_logger.info(f"Đã xóa {deleted_count} file backup cũ, giữ lại {keep_limit} file mới nhất.")

        except Exception as e:
            main_logger.error(f"Error during backup cleanup: {e}", exc_info=True)

    def _crawl_xsmb_result(self, selected_date: datetime.date) -> dict | None:
        """Crawl kết quả XSMB của ngày selected_date từ xoso.com.vn và chuyển đổi sang định dạng 2 số cuối (% 100)."""
        url = f"https://xoso.com.vn/xsmb-{selected_date:%d-%m-%Y}.html"
        main_logger.info(f"Đang crawl XSMB từ: {url}")
        
        resp_text = None
        # Ưu tiên dùng cloudscraper để vượt qua Cloudflare nếu có
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(url, timeout=15)
            if resp.status_code == 200:
                resp_text = resp.text
        except Exception as e:
            main_logger.warning(f"cloudscraper request thất bại: {e}, thử dùng requests...")

        if not resp_text:
            try:
                import requests
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    resp_text = resp.text
            except Exception as e:
                main_logger.error(f"requests fetch thất bại: {e}")
                return None

        if not resp_text:
            return None

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp_text, 'lxml')

            def get_prizes(class_name):
                elements = soup.find_all(attrs={'class': class_name})
                nums = []
                for p in elements:
                    t = p.text.strip()
                    if t.isdigit():
                        nums.append(int(t))
                return nums

            special = get_prizes('special-prize')
            prize1 = get_prizes('prize1')
            prize2 = get_prizes('prize2')
            prize3 = get_prizes('prize3')
            prize4 = get_prizes('prize4')
            prize5 = get_prizes('prize5')
            prize6 = get_prizes('prize6')
            prize7 = get_prizes('prize7')

            if (len(special) < 1 or len(prize1) < 1 or len(prize2) < 2 or
                len(prize3) < 6 or len(prize4) < 4 or len(prize5) < 6 or
                len(prize6) < 3 or len(prize7) < 4):
                main_logger.warning(f"Dữ liệu chưa đầy đủ 27 giải trên {url} (special={len(special)}, p1={len(prize1)})")
                return None

            record = {
                "date": f"{selected_date:%Y-%m-%d}T00:00:00.000",
                "special": special[0] % 100,
                "prize1": prize1[0] % 100,
                "prize2_1": prize2[0] % 100,
                "prize2_2": prize2[1] % 100,
                "prize3_1": prize3[0] % 100,
                "prize3_2": prize3[1] % 100,
                "prize3_3": prize3[2] % 100,
                "prize3_4": prize3[3] % 100,
                "prize3_5": prize3[4] % 100,
                "prize3_6": prize3[5] % 100,
                "prize4_1": prize4[0] % 100,
                "prize4_2": prize4[1] % 100,
                "prize4_3": prize4[2] % 100,
                "prize4_4": prize4[3] % 100,
                "prize5_1": prize5[0] % 100,
                "prize5_2": prize5[1] % 100,
                "prize5_3": prize5[2] % 100,
                "prize5_4": prize5[3] % 100,
                "prize5_5": prize5[4] % 100,
                "prize5_6": prize5[5] % 100,
                "prize6_1": prize6[0] % 100,
                "prize6_2": prize6[1] % 100,
                "prize6_3": prize6[2] % 100,
                "prize7_1": prize7[0] % 100,
                "prize7_2": prize7[1] % 100,
                "prize7_3": prize7[2] % 100,
                "prize7_4": prize7[3] % 100,
            }
            return record
        except Exception as e:
            main_logger.error(f"Lỗi khi trích xuất kết quả từ {url}: {e}", exc_info=True)
            return None

    def _append_records_to_json_file(self, target_file: Path, new_records: list) -> bool:
        """Ghi nối các bản ghi kết quả mới vào file JSON dữ liệu xsmb-2-digits."""
        if not new_records:
            return False
        try:
            existing_data = []
            if target_file.exists():
                with open(target_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    main_logger.error(f"File {target_file} không phải định dạng list JSON.")
                    return False

            existing_dates = set()
            for item in existing_data:
                d = item.get('date', '')
                if d:
                    existing_dates.add(d[:10])

            added_count = 0
            for rec in new_records:
                d_str = rec.get('date', '')[:10]
                if d_str not in existing_dates:
                    existing_data.append(rec)
                    existing_dates.add(d_str)
                    added_count += 1

            if added_count == 0:
                main_logger.info("Tất cả bản ghi crawl được đã tồn tại trong file dữ liệu.")
                return True

            existing_data.sort(key=lambda x: x.get('date', ''))

            # Tạo bản sao lưu trước khi ghi
            if target_file.exists():
                timestamp_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                backup_file = target_file.with_suffix(target_file.suffix + f'.bak-{timestamp_str}')
                try:
                    shutil.copy2(target_file, backup_file)
                    self._cleanup_old_backups(target_file, keep_limit=3)
                except Exception as b_err:
                    main_logger.warning(f"Lỗi tạo backup: {b_err}")

            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            main_logger.info(f"Đã cập nhật thêm {added_count} bản ghi vào {target_file.name}")
            return True
        except Exception as e:
            main_logger.error(f"Lỗi khi ghi dữ liệu vào {target_file}: {e}", exc_info=True)
            return False

    def _sync_from_github(self, target_file: Path, sync_url: str) -> bool:
        """Tải dữ liệu mới nhất từ GitHub raw URL và cập nhật vào file đích."""
        try:
            import requests
            main_logger.info(f"Tải dữ liệu từ GitHub: {sync_url}")
            self.update_status("Đang tải dữ liệu từ GitHub...")
            QApplication.processEvents()

            response = requests.get(sync_url, timeout=30, headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
            response.raise_for_status()

            downloaded_data = response.json()
            if not isinstance(downloaded_data, list):
                raise ValueError("Dữ liệu GitHub không phải là list JSON hợp lệ.")

            if target_file.exists():
                timestamp_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                backup_file = target_file.with_suffix(target_file.suffix + f'.bak-{timestamp_str}')
                try:
                    shutil.copy2(target_file, backup_file)
                    self._cleanup_old_backups(target_file, keep_limit=3)
                except Exception as b_err:
                    main_logger.warning(f"Lỗi tạo backup: {b_err}")

            with open(target_file, 'wb') as f:
                f.write(response.content)

            main_logger.info(f"Tải thành công từ GitHub: {target_file.name} ({len(downloaded_data)} ngày)")
            return True
        except Exception as e:
            main_logger.error(f"Lỗi khi tải từ GitHub ({sync_url}): {e}", exc_info=True)
            return False

    def sync_data(self, is_auto: bool = False):
        """
        Quy tắc đồng bộ dữ liệu:
        - Nếu data kết quả chậm hơn ngày hiện tại 1 ngày:
          + Từ 00:00 đến 18h45: thông báo chờ quay thưởng.
          + Từ 18h45 đến 23h59p59s: crawl trực tiếp từ xoso.com.vn và cập nhật vào xsmb-2-digits.json.
        - Nếu dữ liệu data cũ > 2 ngày:
          + Sync data trực tiếp từ file GitHub lấy data JSON mới nhất.
          + Sau đó chạy lại bước kiểm tra trên.
        """
        main_logger.info(f"Bắt đầu yêu cầu đồng bộ dữ liệu (is_auto={is_auto})...")

        if hasattr(self, '_data_sync_server_online') and self._data_sync_server_online is False:
            main_logger.warning("Đồng bộ hủy: Server Data Sync offline.")
            if not is_auto:
                QMessageBox.warning(self, "Không có kết nối", "Không thể đồng bộ dữ liệu do không có kết nối mạng. Vui lòng kiểm tra kết nối.")
            self.update_status("Đồng bộ thất bại: Không có kết nối mạng.")
            return

        target_file_str = self.config.get('DATA', 'data_file', fallback=str(self.data_dir / "xsmb-2-digits.json"))
        target_file = Path(target_file_str)
        if not target_file.exists():
            default_path = self.data_dir / "xsmb-2-digits.json"
            if default_path.exists():
                target_file = default_path

        sync_url = self.config.get('DATA', 'sync_url', fallback="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json").strip()
        if hasattr(self, 'sync_url_input') and self.sync_url_input and self.sync_url_input.text().strip():
            sync_url = self.sync_url_input.text().strip()

        # 1. Xác định ngày mới nhất hiện tại trong dữ liệu
        today = datetime.date.today()
        latest_date = None
        if self.results:
            latest_date = self.results[-1]['date']
        elif target_file.exists():
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    tmp_data = json.load(f)
                    if isinstance(tmp_data, list) and tmp_data:
                        d_str = tmp_data[-1].get('date', '')[:10]
                        latest_date = datetime.datetime.strptime(d_str, '%Y-%m-%d').date()
            except Exception:
                pass

        days_diff = (today - latest_date).days if latest_date else 999

        # 2. Nếu dữ liệu data cũ > 2 ngày (hoặc chưa có dữ liệu): tải trước từ GitHub
        if days_diff > 2:
            self.update_status("Dữ liệu cũ hơn 2 ngày, đang đồng bộ từ GitHub...")
            QApplication.processEvents()
            success = self._sync_from_github(target_file, sync_url)
            if success:
                self.load_data()
                self.reload_algorithms()
                if self.optimizer_app_instance:
                    self.optimizer_app_instance.load_data()
                latest_date = self.results[-1]['date'] if self.results else None
                days_diff = (today - latest_date).days if latest_date else 999
            else:
                main_logger.warning("Không thể tải từ GitHub, tiếp tục kiểm tra...")

        # 3. Nếu vẫn còn ngày trong quá khứ bị thiếu (ví dụ: thiếu ngày hôm qua)
        if latest_date and (today - latest_date).days >= 2:
            curr_date = latest_date + datetime.timedelta(days=1)
            past_records = []
            while curr_date < today:
                self.update_status(f"Đang crawl kết quả ngày {curr_date.strftime('%d/%m/%Y')}...")
                QApplication.processEvents()
                rec = self._crawl_xsmb_result(curr_date)
                if rec:
                    past_records.append(rec)
                curr_date += datetime.timedelta(days=1)

            if past_records:
                self._append_records_to_json_file(target_file, past_records)
                self.load_data()
                self.reload_algorithms()
                if self.optimizer_app_instance:
                    self.optimizer_app_instance.load_data()
                latest_date = self.results[-1]['date'] if self.results else None
                days_diff = (today - latest_date).days if latest_date else 999

        # 4. Kiểm tra điều kiện theo quy tắc:
        now = datetime.datetime.now()
        drawing_cutoff = datetime.time(18, 45)

        # 4.1. Đã có kết quả ngày hôm nay
        if days_diff <= 0:
            msg = f"Dữ liệu đã được cập nhật mới nhất (đã có kết quả ngày hôm nay: {latest_date.strftime('%d/%m/%Y')})."
            self.update_status(msg)
            if not is_auto:
                QMessageBox.information(self, "Đã Cập Nhật Mới Nhất", msg)
            return

        # 4.2. Chậm hơn ngày hiện tại 1 ngày
        if days_diff == 1:
            if now.time() < drawing_cutoff:
                # Từ 0 giờ đến 18h45: thông báo chờ quay thưởng
                msg = (f"Chờ quay thưởng: Kết quả XSMB hôm nay ({today.strftime('%d/%m/%Y')}) sẽ mở thưởng từ 18h15 - 18h45.\n\n"
                       f"Dữ liệu hiện tại đã đầy đủ đến ngày {latest_date.strftime('%d/%m/%Y')}." )
                self.update_status(f"Chờ quay thưởng XSMB hôm nay ({today.strftime('%d/%m/%Y')} - sau 18h45)")
                if not is_auto:
                    QMessageBox.information(self, "Chờ Quay Thưởng", msg)
                return
            else:
                # Từ 18h45 đến 23h59p59s: xử lý đồng bộ trực tiếp
                self.update_status(f"Đang đồng bộ trực tiếp kết quả XSMB ngày {today.strftime('%d/%m/%Y')} từ xoso.com.vn...")
                QApplication.processEvents()
                today_rec = self._crawl_xsmb_result(today)
                if today_rec:
                    self._append_records_to_json_file(target_file, [today_rec])
                    self.load_data()
                    self.reload_algorithms()
                    if self.optimizer_app_instance:
                        self.optimizer_app_instance.load_data()
                    msg = f"Đã cập nhật kết quả XSMB ngày hôm nay ({today.strftime('%d/%m/%Y')}) thành công!"
                    self.update_status(msg)
                    if not is_auto:
                        QMessageBox.information(self, "Đồng Bộ Thành Công", msg)
                else:
                    msg = (f"Chưa có kết quả đầy đủ cho ngày hôm nay ({today.strftime('%d/%m/%Y')}) trên hệ thống xoso.com.vn.\n\n"
                           f"Vui lòng đợi vài phút để hệ thống cập nhật giải rồi bấm Sync lại!")
                    self.update_status("Chưa có kết quả XSMB hôm nay trên máy chủ.")
                    if not is_auto:
                        QMessageBox.warning(self, "Chưa Có Kết Quả", msg)
                return

        # 4.3. Trường hợp vẫn chưa đồng bộ được do lỗi mạng hoặc file
        msg = f"Dữ liệu hiện tại đến ngày {latest_date.strftime('%d/%m/%Y') if latest_date else 'chưa có'}. Vui lòng kiểm tra lại kết nối mạng."
        self.update_status(msg)
        if not is_auto:
            QMessageBox.warning(self, "Thông Báo Đồng Bộ", msg)

    def perform_auto_sync_if_needed(self):
        """Kiểm tra điều kiện tự động đồng bộ khi khởi động."""
        main_logger.info("Kiểm tra điều kiện tự động đồng bộ khi khởi động...")
        if not hasattr(self, 'config') or not self.config.has_section('DATA'):
            main_logger.warning("Config chưa được tải hoặc thiếu section DATA, bỏ qua auto-sync.")
            return

        if not self.config.getboolean('DATA', 'auto_sync_on_startup', fallback=False):
            main_logger.info("Tự động đồng bộ bị tắt trong cấu hình.")
            return

        self.sync_data(is_auto=True)

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
        main_logger.info("Scanning and loading algorithms for Main tab (PyQt5)...")
        main_window = self

        if hasattr(self, 'algo_list_layout'):
            while self.algo_list_layout.count() > 0:
                item = self.algo_list_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            if hasattr(self, 'initial_main_algo_label') and self.initial_main_algo_label is not None:
                self.initial_main_algo_label = None
        else:
            main_logger.error("Main tab's algorithm list layout (algo_list_layout) not found.")
            return

        self.algorithms.clear()
        self.algorithm_instances.clear()
        count_success, count_failed = 0, 0

        if not self.algorithms_dir.is_dir():
            main_logger.warning(f"Algorithm directory not found: {self.algorithms_dir}")
            if not hasattr(self, 'initial_main_algo_label') or self.initial_main_algo_label is None:
                self.initial_main_algo_label = QLabel(f"Lỗi: Không tìm thấy thư mục thuật toán:\n{self.algorithms_dir}")
                self.initial_main_algo_label.setStyleSheet("color: red; padding: 10px;")
                self.initial_main_algo_label.setAlignment(Qt.AlignCenter)
                self.initial_main_algo_label.setWordWrap(True)
                if hasattr(self, 'algo_list_layout'):
                     self.algo_list_layout.addWidget(self.initial_main_algo_label)
            else:
                 self.initial_main_algo_label.setText(f"Lỗi: Không tìm thấy thư mục thuật toán:\n{self.algorithms_dir}")
                 self.initial_main_algo_label.setVisible(True)
            return

        try:
            py_files = [
                f for f in self.algorithms_dir.glob('*.py')
                if f.is_file() and f.name not in ["__init__.py", "base.py"]
            ]
            json_files = [
                f for f in self.algorithms_dir.glob('*.json')
                if f.is_file() and is_json_bundle_file(f)
            ]
            algorithm_files_to_load = py_files + json_files
            main_logger.debug(f"Main App: Found {len(algorithm_files_to_load)} potential algorithm files ({len(py_files)} py, {len(json_files)} json).")
        except Exception as e:
            main_logger.error(f"Error scanning algorithms directory: {e}", exc_info=True)
            if not hasattr(self, 'initial_main_algo_label') or self.initial_main_algo_label is None:
                self.initial_main_algo_label = QLabel(f"Lỗi đọc thư mục thuật toán:\n{e}")
                self.initial_main_algo_label.setStyleSheet("color: red; padding: 10px;")
                self.initial_main_algo_label.setAlignment(Qt.AlignCenter)
                self.initial_main_algo_label.setWordWrap(True)
                if hasattr(self, 'algo_list_layout'):
                    self.algo_list_layout.addWidget(self.initial_main_algo_label)
            else:
                self.initial_main_algo_label.setText(f"Lỗi đọc thư mục thuật toán:\n{e}")
                self.initial_main_algo_label.setVisible(True)
            return

        if not algorithm_files_to_load:
             self.create_sample_algorithms()
             py_files = [
                f for f in self.algorithms_dir.glob('*.py')
                if f.is_file() and f.name not in ["__init__.py", "base.py"]
             ]
             json_files = [
                f for f in self.algorithms_dir.glob('*.json')
                if f.is_file() and is_json_bundle_file(f)
             ]
             algorithm_files_to_load = py_files + json_files
             if not algorithm_files_to_load:
                if not hasattr(self, 'initial_main_algo_label') or self.initial_main_algo_label is None:
                    self.initial_main_algo_label = QLabel("Không tìm thấy file thuật toán (.py, .json) nào trong thư mục 'algorithms'.")
                    self.initial_main_algo_label.setStyleSheet("font-style: italic; color: #6c757d; padding: 10px;")
                    self.initial_main_algo_label.setAlignment(Qt.AlignCenter)
                    self.initial_main_algo_label.setWordWrap(True)
                    if hasattr(self, 'algo_list_layout'):
                        self.algo_list_layout.addWidget(self.initial_main_algo_label)
                else:
                    self.initial_main_algo_label.setText("Không tìm thấy file thuật toán (.py, .json) nào trong thư mục 'algorithms'.")
                    self.initial_main_algo_label.setVisible(True)


        results_copy_for_instances = copy.deepcopy(self.results) if self.results else []
        cache_dir_for_instances = self.calculate_dir
        
        any_card_created = False
        for f_path in algorithm_files_to_load:
            main_logger.debug(f"Main App: Processing algorithm file: {f_path.name}")
            try:
                if f_path.suffix.lower() == '.json':
                    loaded_successfully = self.load_algorithm_from_json(
                        f_path, results_copy_for_instances, cache_dir_for_instances
                    )
                else:
                    loaded_successfully = self.load_algorithm_from_file(
                        f_path, results_copy_for_instances, cache_dir_for_instances
                    )
                if loaded_successfully:
                    count_success += 1
                    any_card_created = True
                else:
                    count_failed += 1
            except Exception as e:
                main_logger.error(f"Main App: Unexpected error loading {f_path.name}: {e}", exc_info=True)
                count_failed += 1
        
        if not any_card_created and algorithm_files_to_load:
            if not hasattr(self, 'initial_main_algo_label') or self.initial_main_algo_label is None:
                self.initial_main_algo_label = QLabel("Không thể tải giao diện cho bất kỳ thuật toán nào.\nKiểm tra log để biết chi tiết.")
                self.initial_main_algo_label.setStyleSheet("color: red; font-style: italic; padding: 10px;")
                self.initial_main_algo_label.setAlignment(Qt.AlignCenter)
                self.initial_main_algo_label.setWordWrap(True)
                if hasattr(self, 'algo_list_layout'):
                    self.algo_list_layout.addWidget(self.initial_main_algo_label)
            else:
                self.initial_main_algo_label.setText("Không thể tải giao diện cho bất kỳ thuật toán nào.\nKiểm tra log để biết chi tiết.")
                self.initial_main_algo_label.setVisible(True)

        status_msg = f"Đã tải {count_success} thuật toán (Main)"
        if count_failed > 0:
            status_msg += f", lỗi {count_failed} file"
        self.update_status(status_msg)
        
        if count_failed > 0 and main_window:
            QMessageBox.warning(main_window, "Lỗi Tải Thuật Toán (Main)",
                                f"Đã xảy ra lỗi khi tải {count_failed} file thuật toán cho tab Main.\n"
                                "Kiểm tra file log để biết chi tiết.")

        self.apply_algorithm_config_states()

    def load_algorithm_from_file(self, algo_file_path: Path, data_results_list: list, cache_dir: Path) -> bool:
        """Loads a single algorithm, instantiates it, and creates its UI.
        Nếu file .py thực chất chứa nội dung JSON (TCS bundle), tự động chuyển sang load_algorithm_from_json."""
        # ── Nhận dạng sớm: file .py có chứa JSON không? ──────────────────────────
        try:
            raw_text = algo_file_path.read_text(encoding='utf-8').strip()
            if raw_text.startswith('{') or raw_text.startswith('['):
                try:
                    json.loads(raw_text)
                    # Nội dung là JSON hợp lệ → xử lý như TCS bundle
                    main_logger.info(
                        f"load_algorithm_from_file: '{algo_file_path.name}' có nội dung JSON, "
                        f"chuyển sang load_algorithm_from_json."
                    )
                    if is_json_bundle_file is not None and is_json_bundle_file(algo_file_path):
                        return self.load_algorithm_from_json(algo_file_path, data_results_list, cache_dir)
                    # Nếu is_json_bundle_file kiểm tra cụ thể hơn và trả False, thử anyway
                    return self.load_algorithm_from_json(algo_file_path, data_results_list, cache_dir)
                except (json.JSONDecodeError, ValueError):
                    pass  # Không phải JSON → tiếp tục import bình thường
        except Exception:
            pass

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

    def load_algorithm_from_json(self, json_file_path: Path, data_results_list: list, cache_dir: Path) -> bool:
        """Loads a JSON bundle algorithm, instantiates it, and creates its UI."""
        display_name = f"JSON Bundle ({json_file_path.name})"
        try:
            main_logger.debug(f"Main App: Instantiating JsonBundleAlgorithm from {json_file_path.name}...")
            instance = JsonBundleAlgorithm(
                json_path=json_file_path,
                data_results_list=data_results_list,
                cache_dir=cache_dir
            )
            config = instance.get_config()
            algo_title = instance.bundle_name or json_file_path.stem
            display_name = f"[TCS] {algo_title} ({json_file_path.name})"

            self.algorithm_instances[display_name] = instance
            self.create_algorithm_ui_qt(display_name, config, json_file_path.name)
            main_logger.info(f"Main App: Successfully loaded JSON bundle algorithm '{display_name}'")
            return True
        except Exception as e:
            main_logger.error(f"Main App: Error loading JSON bundle algorithm {json_file_path.name}: {e}", exc_info=True)
            if display_name in self.algorithm_instances:
                del self.algorithm_instances[display_name]
            if display_name in self.algorithms:
                del self.algorithms[display_name]
            return False

    def create_algorithm_ui_qt(self, algo_name, algo_config, algo_filename):
        try:
            if not hasattr(self, 'algo_list_layout'):
                main_logger.error(f"Cannot create UI for {algo_name}: algo_list_layout missing.")
                return

            if hasattr(self, 'initial_main_algo_label') and self.initial_main_algo_label is not None:
                if self.algo_list_layout.indexOf(self.initial_main_algo_label) != -1:
                    self.algo_list_layout.removeWidget(self.initial_main_algo_label)
                self.initial_main_algo_label.deleteLater()
                self.initial_main_algo_label = None

            algo_frame = QFrame()
            algo_frame.setObjectName("CardFrame")
            algo_frame.setFrameShape(QFrame.StyledPanel)
            algo_frame.setFrameShadow(QFrame.Raised)
            algo_frame.setLineWidth(1)

            algo_layout = QVBoxLayout(algo_frame)
            algo_layout.setSpacing(3)
            algo_layout.setContentsMargins(10, 8, 10, 8)

            try: class_name_only = algo_name.rsplit(' (', 1)[0]
            except IndexError: class_name_only = algo_name
            algo_num = len(self.algorithms) + 1

            clean_title = class_name_only
            is_tcs = algo_filename.lower().endswith('.json') or clean_title.startswith('[TCS]') or clean_title.startswith('TCS')
            if clean_title.startswith('[TCS] '):
                clean_title = clean_title[6:]
            elif clean_title.startswith('[TCS]'):
                clean_title = clean_title[5:]
            elif clean_title.startswith('TCS '):
                clean_title = clean_title[4:]

            # Dòng 1: Tên thuật toán
            if is_tcs:
                algo_title_label = QLabel(f"{algo_num}. <b style='color: #16a34a;'>[TCS]</b> {clean_title}")
            else:
                algo_title_label = QLabel(f"{algo_num}. {clean_title}")
            algo_title_label.setFont(self.get_qfont("bold"))
            algo_title_label.setStyleSheet("color: #0f172a; font-weight: bold; font-size: 10pt; padding-bottom: 0px;")
            algo_title_label.setToolTip(f"Thuật toán: {class_name_only}")
            algo_layout.addWidget(algo_title_label)

            # Dòng 2: Tên file trong ngoặc đơn xuống 1 dòng dưới
            algo_file_label = QLabel(f"({algo_filename})")
            algo_file_label.setStyleSheet("color: #0284c7; font-size: 8.5pt; font-weight: 500; padding-bottom: 2px;")
            algo_file_label.setToolTip(f"File nguồn: {algo_filename}")
            algo_layout.addWidget(algo_file_label)

            description = algo_config.get("description", "Không có mô tả.")
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setFont(self.get_qfont("small"))
            desc_label.setStyleSheet("color: #64748b; padding-bottom: 3px; font-size: 9pt;")
            desc_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            desc_label.setToolTip(description)
            algo_layout.addWidget(desc_label)

            control_row_widget = QWidget()
            control_row_layout = QHBoxLayout(control_row_widget)
            control_row_layout.setContentsMargins(0, 2, 0, 0)
            control_row_layout.setSpacing(8)

            chk_enable = QCheckBox("Kích hoạt")
            chk_enable.setToolTip("Bật/Tắt thuật toán này trong quá trình dự đoán và tính hiệu suất.")
            chk_enable.toggled.connect(lambda state, name=algo_name, chk=chk_enable: self.toggle_algorithm(name, chk))
            control_row_layout.addWidget(chk_enable)

            # Nút hệ số đặt ngay cạnh nút kích hoạt
            chk_weight = QCheckBox("Hệ số:")
            chk_weight.setToolTip("Áp dụng hệ số nhân cho điểm số của thuật toán này khi kết hợp.")
            weight_entry = QLineEdit("1.0")
            weight_entry.setFixedWidth(50)
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

            self.update_status(f"Đã {state_text.lower()} thuật toán: {algo_name.rsplit(' (', 1)[0]}")

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

            self.update_status(f"Đã {state_text.lower()} hệ số nhân cho: {algo_name.rsplit(' (', 1)[0]}")

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

    def load_predict_sort_file(self):
        self._load_custom_sort_file(is_prediction=True)

    def load_perf_sort_file(self):
        self._load_custom_sort_file(is_prediction=False)

    def _load_custom_sort_file(self, is_prediction=True):
        """Hàm chung để tải và parse file sắp xếp."""
        target_label = self.pred_file_label if is_prediction else self.perf_file_label
        
        initial_dir = str(self.algorithms_dir)
        filename, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Sắp Xếp", initial_dir, "Text Files (*.txt);;All Files (*.*)"
        )
        
        if filename:
            try:
                path = Path(filename)
                content = path.read_text(encoding='utf-8').strip()
                
                raw_items = re.split(r'[\-\s,]+', content)
                valid_numbers = []
                for item in raw_items:
                    if item.isdigit():
                        num = int(item)
                        if 0 <= num <= 99:
                            valid_numbers.append(num)
                
                seen = set()
                unique_numbers = []
                for n in valid_numbers:
                    if n not in seen:
                        unique_numbers.append(n)
                        seen.add(n)

                if not unique_numbers:
                    QMessageBox.warning(self, "Lỗi File", "File không chứa số hợp lệ (00-99).")
                    return

                if is_prediction:
                    self.predict_custom_sort_data = unique_numbers
                else:
                    self.perf_custom_sort_data = unique_numbers
                
                target_label.setText(path.name)
                target_label.setToolTip(f"Đã tải {len(unique_numbers)} số.\nThứ tự: {unique_numbers[:10]}...")
                QMessageBox.information(self, "Thành Công", f"Đã tải {len(unique_numbers)} số từ file để sắp xếp.")

            except Exception as e:
                QMessageBox.critical(self, "Lỗi Đọc File", f"Không thể đọc file:\n{e}")

    def _apply_sorting_logic(self, score_list, sort_mode_idx, custom_order=None):
        """
        Sắp xếp danh sách (số, điểm) dựa trên chế độ.
        score_list: list of (number, score) tuples.
        sort_mode_idx: 0 (Cao->Thấp), 1 (Thấp->Cao), 2 (Theo File).
        custom_order: list of int (chỉ dùng khi mode == 2).
        Trả về: list đã sắp xếp.
        """
        if sort_mode_idx == 0:
            return sorted(score_list, key=lambda x: x[1], reverse=True)
        elif sort_mode_idx == 1:
            return sorted(score_list, key=lambda x: x[1], reverse=False)
        elif sort_mode_idx == 2 and custom_order:
            order_map = {num: i for i, num in enumerate(custom_order)}
            return sorted(score_list, key=lambda x: order_map.get(x[0], 9999))
        else:
            return sorted(score_list, key=lambda x: x[1], reverse=True)


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

                sort_mode = self.pred_sort_combo.currentIndex()
                final_scores_list = self._apply_sorting_logic(
                    final_scores_list, sort_mode, self.predict_custom_sort_data
                )
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

        try:
            perf_sort_mode = self.perf_sort_combo.currentIndex()
            perf_custom_data = self.perf_custom_sort_data if perf_sort_mode == 2 else []
            
            if perf_sort_mode == 2 and not perf_custom_data:
                QMessageBox.warning(self, "Thiếu File Sắp Xếp", "Bạn chọn sắp xếp theo file nhưng chưa tải file nào. Vui lòng chọn file .txt hoặc đổi chế độ.")
                self.performance_calc_running = False
                self.perf_calc_button.setEnabled(True)
                return
        except Exception as e:
            main_logger.error(f"Error getting sort settings: {e}")
            perf_sort_mode = 0
            perf_custom_data = []

        main_logger.info("Starting performance calculation worker thread...")
        perf_thread = threading.Thread(
            target=self._performance_worker,
            args=( active_inst, res_map, hist_cache, valid_predict_dates, start_s, end_s, total_days_to_test, perf_sort_mode, perf_custom_data ),
            name="PerfCalcWorker",
            daemon=True
        )
        perf_thread.start()

        if not self.performance_timer.isActive():
             self.performance_timer.start(self.performance_timer_interval)

        self.update_status(f"Bắt đầu tính hiệu suất ({total_days_to_test} ngày)...")


    def _performance_worker(self, active_instances_main, results_map_main, history_cache_main,
                           predict_dates_list_main, start_date_str_main, end_date_str_main, total_days_main,
                           sort_mode, custom_sort_data):
        """Worker thread for calculating combined performance (Tab Main)."""
        perf_logger_main = logging.getLogger("MainTabPerfWorker")
        perf_logger_main.info(f"MainTab PerfWorker started for {len(predict_dates_list_main)} days. Active Algos: {list(active_instances_main.keys())}")

        stats_main = {
            'total_days_tested': 0, 'hits_top_1': 0, 'hits_top_3': 0, 'hits_top_5': 0, 'hits_top_10': 0,
            'special_hits_top_1': 0, 'special_hits_top_5': 0, 'special_hits_top_10': 0
        }
        errors_in_worker_main = 0
        date_range_str_for_status_main = f"{start_date_str_main} - {end_date_str_main}"

        throttling_enabled_main_tab = self.cpu_throttling_enabled
        sleep_duration_main_tab = self.throttle_sleep_duration
        perf_logger_main.debug(f"MainTab PerfWorker Throttling: Enabled={throttling_enabled_main_tab}, Duration={sleep_duration_main_tab}s")

        try:
            for i_main, predict_dt_main in enumerate(predict_dates_list_main):
                try:
                    if throttling_enabled_main_tab and sleep_duration_main_tab > 0:
                        time.sleep(sleep_duration_main_tab)

                    perf_logger_main.debug(f"MainTab PerfWorker processing predict_dt: {predict_dt_main}")
                    check_dt_main = predict_dt_main + datetime.timedelta(days=1)
                    actual_res_main = results_map_main.get(check_dt_main)
                    hist_data_main = history_cache_main.get(predict_dt_main)

                    if actual_res_main is None or hist_data_main is None:
                        perf_logger_main.warning(f"MainTab PerfWorker skipping day {predict_dt_main}: Missing actual ({actual_res_main is None}) or history ({hist_data_main is None}).")
                        errors_in_worker_main += 1
                        continue

                    day_results_main = {}
                    hist_copy_for_day_main = copy.deepcopy(hist_data_main)

                    for name_main, inst_main in active_instances_main.items():
                        try:
                            day_results_main[name_main] = inst_main.predict(predict_dt_main, hist_copy_for_day_main)
                        except Exception as algo_e_main:
                            perf_logger_main.error(f"MainTab PerfWorker error in {name_main}.predict() on {predict_dt_main}: {algo_e_main}", exc_info=False)
                            day_results_main[name_main] = {}
                            errors_in_worker_main += 1
                    
                    comb_scores_main = self.combine_algorithm_scores(day_results_main)
                    if not comb_scores_main:
                        perf_logger_main.warning(f"Combined scores empty for {predict_dt_main} in MainTab PerfWorker")
                        errors_in_worker_main += 1
                        continue
                    
                    valid_preds_day_main = []
                    for n_str_m, s_val_m in comb_scores_main.items():
                         if isinstance(n_str_m, str) and len(n_str_m)==2 and n_str_m.isdigit() and isinstance(s_val_m, (int,float)):
                              try: valid_preds_day_main.append((int(n_str_m), float(s_val_m)))
                              except (ValueError, TypeError): errors_in_worker_main += 1
                         else: errors_in_worker_main += 1
                    
                    if not valid_preds_day_main:
                        perf_logger_main.warning(f"No valid combined predictions for {predict_dt_main} (MainTab) after validation.")
                        errors_in_worker_main += 1
                        continue
                    
                    try:
                        sorted_preds_main = self._apply_sorting_logic(
                            valid_preds_day_main, sort_mode, custom_sort_data
                        )
                    except Exception as sort_err:
                        perf_logger_main.error(f"Error sorting in worker: {sort_err}. Using default sort.")
                        sorted_preds_main = sorted(valid_preds_day_main, key=lambda x: x[1], reverse=True)

                    actual_set_main = self.extract_numbers_from_result_dict(actual_res_main)
                    if not actual_set_main:
                        perf_logger_main.warning(f"Could not extract actual numbers for check_dt {check_dt_main} (MainTab)")
                        errors_in_worker_main += 1
                        continue

                    spec_val_main = actual_res_main.get('special', actual_res_main.get('dac_biet'))
                    actual_spec_main = -1
                    if spec_val_main is not None:
                         try:
                             s_main = str(spec_val_main).strip()
                             if len(s_main) >= 2 and s_main[-2:].isdigit(): actual_spec_main = int(s_main[-2:])
                             elif len(s_main) == 1 and s_main.isdigit(): actual_spec_main = int(s_main)
                         except (ValueError, TypeError): actual_spec_main = -1

                    pred_top_1_main_num = sorted_preds_main[0][0] if sorted_preds_main else -1
                    pred_top_3_main_set = {p[0] for p in sorted_preds_main[:3]}
                    pred_top_5_main_set = {p[0] for p in sorted_preds_main[:5]}
                    pred_top_10_main_set = {p[0] for p in sorted_preds_main[:10]}

                    if pred_top_1_main_num != -1 and pred_top_1_main_num in actual_set_main: stats_main['hits_top_1'] += 1
                    if actual_set_main.intersection(pred_top_3_main_set): stats_main['hits_top_3'] += 1
                    if actual_set_main.intersection(pred_top_5_main_set): stats_main['hits_top_5'] += 1
                    if actual_set_main.intersection(pred_top_10_main_set): stats_main['hits_top_10'] += 1

                    if actual_spec_main != -1:
                        if pred_top_1_main_num == actual_spec_main: stats_main['special_hits_top_1'] += 1
                        if actual_spec_main in pred_top_5_main_set: stats_main['special_hits_top_5'] += 1
                        if actual_spec_main in pred_top_10_main_set: stats_main['special_hits_top_10'] += 1
                    
                    stats_main['total_days_tested'] += 1

                except Exception as day_e_main:
                    perf_logger_main.error(f"MainTab PerfWorker unexpected error processing day {predict_dt_main}: {day_e_main}", exc_info=True)
                    errors_in_worker_main += 1
                
                if (i_main + 1) % 5 == 0 or (i_main + 1) == total_days_main:
                    progress_payload_main = {
                        'current': i_main + 1, 'total': total_days_main,
                        'errors': errors_in_worker_main, 'range_str': date_range_str_for_status_main
                    }
                    if hasattr(self, 'perf_queue') and self.perf_queue:
                        try: self.perf_queue.put({'type': 'progress', 'payload': progress_payload_main})
                        except Exception as q_put_err_main: perf_logger_main.error(f"Error putting progress to MainTab queue: {q_put_err_main}")
                    else: perf_logger_main.warning("MainTab perf_queue not found in LotteryPredictionApp, cannot send progress.")

            finished_payload_main = {'stats': stats_main, 'errors': errors_in_worker_main}
            if hasattr(self, 'perf_queue') and self.perf_queue:
                try: self.perf_queue.put({'type': 'finished', 'payload': finished_payload_main})
                except Exception as q_put_err_main_fin: perf_logger_main.error(f"Error putting finished payload to MainTab queue: {q_put_err_main_fin}")
            else: perf_logger_main.warning("MainTab perf_queue not found, cannot send finished signal.")

            perf_logger_main.info(f"MainTab PerfWorker finished. Days successfully tested: {stats_main['total_days_tested']}, Total Errors: {errors_in_worker_main}")

        except Exception as worker_err_main_critical:
            perf_logger_main.critical(f"MainTab PerfWorker failed critically: {worker_err_main_critical}", exc_info=True)
            if hasattr(self, 'perf_queue') and self.perf_queue:
                try: self.perf_queue.put({'type': 'error', 'payload': f"Lỗi nghiêm trọng worker (MainTab): {worker_err_main_critical}"})
                except Exception as q_put_err_main_crit: perf_logger_main.error(f"Error putting critical error to MainTab queue: {q_put_err_main_crit}")
            else: perf_logger_main.warning("MainTab perf_queue not found, cannot send critical error.")

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

        if hasattr(self, 'tool_count_label'):
            self.tool_count_label.setText(f"🛠Số lượng công cụ: {count_success}")

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
            info_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            info_v_layout = QVBoxLayout(info_widget)
            info_v_layout.setContentsMargins(0,0,0,0)
            info_v_layout.setSpacing(3)

            name_label = QLabel(display_name)
            name_label.setFont(self.get_qfont("bold"))
            name_label.setStyleSheet("color: #0056b3;")
            name_label.setToolTip(f"Tên công cụ: {display_name}")
            name_label.setWordWrap(True)
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
            file_label.setWordWrap(True)
            info_v_layout.addWidget(file_label)

            tool_layout.addWidget(info_widget, 1)

            run_button = QPushButton("Chạy Tool")
            run_button.setObjectName("ListAccentButton")
            run_button.setToolTip(f"Chạy công cụ: {tool_path.name}")
            run_button.setMinimumWidth(125)
            run_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
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
            icon = "🔴"
        elif "success" in lower_message or "thành công" in lower_message or "hoàn tất" in lower_message or "mới nhất" in lower_message or "sẵn sàng" in lower_message:
            status_type = "success"
            icon = "🟢"
        else:
            icon = "🔵"

        if hasattr(self, 'status_bar_label'):
            self.status_bar_label.setText(f"{icon} Hoạt động: {message}")
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
    try:
        if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
             QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
             QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
         pass

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
        sys.exit(1)
    finally:
        main_logger.info("Application shutdown sequence (finally block).")
        logging.shutdown()


if __name__ == "__main__":
    main()

    main_logger.info("="*30 + " APPLICATION END (if not exited earlier) " + "="*30)
