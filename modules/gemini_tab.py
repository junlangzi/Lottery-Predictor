# -*- coding: utf-8 -*-
# Module: modules/gemini_tab.py
# Contains: GeminiModelFetcherWorker, GeminiWorker, FetchModelsWorker, AlgorithmGeminiBuilderTab

import os
import re
import time
import base64
import logging
import datetime
import textwrap
from pathlib import Path

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
        QPushButton, QComboBox, QProgressBar, QPlainTextEdit, QMessageBox,
        QApplication, QFileDialog
    )
    from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal, QThread
    from PyQt5.QtGui import QFont
except ImportError:
    pass

class GeminiModelFetcherWorker(QObject):
    """Worker chuyên để lấy danh sách các model khả dụng từ API Key."""
    models_received = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        if not HAS_GEMINI:
            self.error_occurred.emit("Thư viện google-generativeai chưa được cài đặt.")
            return

        try:
            genai.configure(api_key=self.api_key)
            
            available_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    model_name = m.name.replace("models/", "")
                    available_models.append(model_name)
            
            if not available_models:
                available_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
                
            self.models_received.emit(available_models)

        except Exception as e:
            self.error_occurred.emit(f"Lỗi lấy danh sách model: {str(e)}")


class GeminiWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(self, api_key, model_name, full_prompt):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.full_prompt = full_prompt

    def run(self):
        try:
            if not self.api_key:
                raise ValueError("API Key is missing.")
            
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
            
            response = model.generate_content(self.full_prompt)
            
            if response.text:
                code = response.text.strip()
                if "```python" in code:
                    code = code.split("```python")[1].split("```")[0]
                elif "```" in code:
                    code = code.split("```")[1].split("```")[0]
                
                self.finished.emit(code.strip())
            else:
                self.error.emit("AI không trả về nội dung.")
        except Exception as e:
            self.error.emit(str(e))


class FetchModelsWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(list)
    error = QtCore.pyqtSignal(str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            genai.configure(api_key=self.api_key)
            
            models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    models.append(m.name)
            
            models.sort(reverse=True)
            
            self.finished.emit(models)
        except Exception as e:
            self.error.emit(str(e))


class AlgorithmGeminiBuilderTab(QWidget):
    def __init__(self, parent_widget: QWidget, main_app_instance):
        super().__init__(parent_widget)
        self.main_app = main_app_instance

        self.CONFIG_DIR = self.main_app.config_dir
        self.API_KEY_FILE = self.CONFIG_DIR / "gemini.api"
        self.ALGORITHMS_DIR = self.main_app.algorithms_dir

        self.generated_code = ""
        self.api_key = ""
        self.gemini_thread = None
        self.gemini_worker = None
        self.start_time = None

        self.logger = logging.getLogger("GeminiAlgoBuilderTab")

        self.PRIORITY_MODELS = [
            "models/gemini-2.5-flash",
            "models/gemini-2.0-flash", 
            "models/gemini-1.5-flash",
            "models/gemini-1.5-pro",
            "models/gemini-pro"
        ]

        self._load_api_key()
        self._setup_ui()

    def _load_api_key(self):
        """Tải API Key và Model đã lưu từ file."""
        self.api_key = ""
        self.last_saved_model = ""
        
        api_file = Path("config/gemini.api")
        if api_file.exists():
            try:
                content = api_file.read_text(encoding="utf-8").strip()
                if content:
                    if "|" in content:
                        self.api_key = content.split("|")[0]
                        self.last_saved_model = content.split("|")[1]
                    else:
                        try:
                            self.api_key = base64.b64decode(content.encode("utf-8")).decode("utf-8")
                        except:
                            self.api_key = content
            except Exception: pass

    def _save_api_key(self, api_key):
        """Lưu API Key kèm theo Model đang chọn vào file theo định dạng KEY|MODEL."""
        try:
            current_model = self.model_combo.currentText()
            if api_key:
                content = f"{api_key}|{current_model}"
                self.API_KEY_FILE.write_text(content, encoding="utf-8")
                self.api_key = api_key
                # self.logger.info(f"Đã lưu API Key và model: {current_model}")
        except Exception as e:
            self.logger.error(f"Lỗi khi lưu API key và model: {e}")

    def _save_api_key_if_changed(self):
        """Saves the API key only if it has changed."""
        key_to_save = self.api_key_edit.text().strip()
        if key_to_save == self.api_key:
            return True

        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            encoded_key = base64.b64encode(key_to_save.encode('utf-8'))
            self.API_KEY_FILE.write_bytes(encoded_key)
            self.api_key = key_to_save
            self.logger.info(f"Saved API key to {self.API_KEY_FILE}")
            self.status_label.setText("Trạng thái: Đã lưu API Key mới.")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Trạng thái: Sẵn sàng") if self.status_label.text().startswith("Trạng thái: Đã lưu API Key") else None)
            return True
        except IOError as e:
            self.logger.error(f"Failed to save API key to {self.API_KEY_FILE}: {e}")
            QMessageBox.critical(self, "Lỗi Lưu API Key", f"Không thể lưu API key vào file:\n{e}")
            return False
        except Exception as e_gen:
            self.logger.error(f"General error saving API key: {e_gen}")
            QMessageBox.critical(self, "Lỗi Lưu API Key", f"Lỗi không xác định khi lưu API key:\n{e_gen}")
            return False


    def _get_api_key_help_text_plain(self) -> str:
        """Returns the help text for API key as plain text for tooltip."""
        return textwrap.dedent("""
        Hướng dẫn lấy Gemini API Key:
        1. Truy cập Google AI Studio: https://aistudio.google.com/
           (Hoặc Google Cloud Console nếu dùng Vertex AI)
        2. Đăng nhập bằng tài khoản Google của bạn.
        3. Trong Google AI Studio:
           - Nhấp vào "Get API key" ở thanh bên trái.
           - Nhấp vào "Create API key in new project" (hoặc chọn dự án có sẵn).
           - Sao chép API key được tạo ra.
        4. Dán API key vào ô bên cạnh.

        Lưu ý: Giữ API key của bạn bí mật.
        Việc sử dụng API có thể phát sinh chi phí.
        """)


    def _load_model_preference(self):
        """Tải tên model và danh sách model đã lưu từ file config."""
        if hasattr(self.main_app, 'config') and self.main_app.config.has_section('GEMINI'):
            cached_models_str = self.main_app.config.get('GEMINI', 'cached_models', fallback="")
            if cached_models_str:
                cached_list = [m.strip() for m in cached_models_str.split(',') if m.strip()]
                if cached_list:
                    self.model_combo.clear()
                    self.model_combo.addItems(cached_list)
            
            saved_model = self.main_app.config.get('GEMINI', 'model_name', fallback="")
            if saved_model:
                self.model_combo.setCurrentText(saved_model)
        else:
            self.model_combo.setCurrentText("gemini-1.5-flash")

    def _save_model_preference(self):
        """Lưu tên model hiện tại vào config."""
        current_model = self.model_combo.currentText().strip()
        if hasattr(self.main_app, 'config'):
            if not self.main_app.config.has_section('GEMINI'):
                self.main_app.config.add_section('GEMINI')
            
            self.main_app.config.set('GEMINI', 'model_name', current_model)
            if hasattr(self.main_app, 'save_config'):
                self.main_app.save_config("settings.ini")

    def _fetch_available_models(self):
        """Bắt đầu quét model bằng luồng riêng (Thread)."""
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng nhập API Key trước khi quét.")
            self.api_key_edit.setFocus()
            return

        self.btn_fetch_models.setEnabled(False)
        self.btn_fetch_models.setText("...")
        self.status_label.setText("⏳ Đang kết nối tới Google để lấy danh sách model...")
        self.status_label.setStyleSheet("color: orange;")

        self.fetch_worker = FetchModelsWorker(api_key)
        self.fetch_worker.finished.connect(self._on_models_fetched)
        self.fetch_worker.error.connect(self._on_models_fetch_error)
        
        self.fetch_worker.start()

    def _on_models_fetched(self, models):
        self.btn_fetch_models.setEnabled(True)
        self.btn_fetch_models.setText("🔄")
        self.model_combo.clear()
        
        if not models:
            self.model_combo.addItem("Không tìm thấy model nào")
            return

        model_names = [m.name if hasattr(m, 'name') else str(m) for m in models]
        model_names.sort() 
        self.model_combo.addItems(model_names)

        target_index = -1
        
        if hasattr(self, 'last_saved_model') and self.last_saved_model:
            target_index = self.model_combo.findText(self.last_saved_model)

        if target_index == -1:
            for i in range(self.model_combo.count()):
                name = self.model_combo.itemText(i).lower()
                if "2.5-flash" in name and not any(x in name for x in ["preview", "pro", "tts", "lite"]):
                    target_index = i
                    break

        if target_index == -1:
            for i in range(self.model_combo.count()):
                if "2.5-flash" in self.model_combo.itemText(i).lower():
                    target_index = i
                    break

        if target_index != -1:
            self.model_combo.setCurrentIndex(target_index)
        else:
            self.model_combo.setCurrentIndex(0)
            
        self.status_label.setText(f"✅ Đã chọn: {self.model_combo.currentText()}")
        self._save_current_settings()

    def _on_models_fetch_error(self, error_msg):
        """Được gọi khi Worker gặp lỗi."""
        self.btn_fetch_models.setEnabled(True)
        self.btn_fetch_models.setText("🔄 Quét")
        self.status_label.setText("❌ Lỗi quét model.")
        self.status_label.setStyleSheet("color: red;")
        
        QMessageBox.critical(self, "Lỗi Kết Nối", f"Không thể lấy danh sách model:\n\n{error_msg}\n\nKiểm tra lại Internet hoặc API Key.")


    def _setup_ui(self):
        """Thiết lập giao diện tối ưu không gian (Single Row Config & Actions)."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        config_group = QGroupBox("Cấu hình Kết nối")
        top_row_layout = QHBoxLayout(config_group)
        top_row_layout.setContentsMargins(10, 15, 10, 10)
        top_row_layout.setSpacing(8)

        top_row_layout.addWidget(QLabel("API Key:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Dán API Key vào đây...")
        self.api_key_edit.setMinimumWidth(200)
        self.api_key_edit.editingFinished.connect(self._save_current_settings) 
        top_row_layout.addWidget(self.api_key_edit, 2)

        self.btn_toggle_api = QPushButton("👁")
        self.btn_toggle_api.setCheckable(True)
        self.btn_toggle_api.setFixedWidth(50)
        self.btn_toggle_api.toggled.connect(self._toggle_api_key_visibility)
        top_row_layout.addWidget(self.btn_toggle_api)

        top_row_layout.addSpacing(15)
        
        top_row_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(180)
        self.model_combo.setMaxVisibleItems(20)
        self.model_combo.currentIndexChanged.connect(self._save_current_settings)
        top_row_layout.addWidget(self.model_combo, 1)

        self.btn_fetch_models = QPushButton("🔄")
        self.btn_fetch_models.setToolTip("Quét danh sách Model mới")
        self.btn_fetch_models.setFixedWidth(65)
        self.btn_fetch_models.clicked.connect(self._fetch_available_models)
        top_row_layout.addWidget(self.btn_fetch_models)

        main_layout.addWidget(config_group)

        info_group = QGroupBox("Thông tin Code Output")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(10, 15, 10, 10)
        
        row_info = QHBoxLayout()
        row_info.addWidget(QLabel("File Name:"))
        self.file_name_edit = QLineEdit()
        self.file_name_edit.setPlaceholderText("vd: logic_2026")
        row_info.addWidget(self.file_name_edit)
        
        row_info.addSpacing(15)
        
        row_info.addWidget(QLabel("Class Name:"))
        self.class_name_edit = QLineEdit()
        self.class_name_edit.setPlaceholderText("vd: Logic2026Algorithm")
        row_info.addWidget(self.class_name_edit)
        info_layout.addLayout(row_info)
        
        main_layout.addWidget(info_group)

        row_desc = QHBoxLayout()
        row_desc.addWidget(QLabel("Mô tả thuật toán:"))
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("vd: Thuật toán dựa trên tần suất xuất hiện...")
        row_desc.addWidget(self.description_edit)
        info_layout.addLayout(row_desc)
        
        main_layout.addWidget(QLabel("<b>Mô tả ý tưởng thuật toán (Prompt):</b>"))
        self.logic_description_edit = QPlainTextEdit()
        self.logic_description_edit.setPlaceholderText("Nhập logic bạn muốn AI viết...")
        self.logic_description_edit.setMinimumHeight(80)
        main_layout.addWidget(self.logic_description_edit)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        self.generate_button = QPushButton("🚀 TẠO CODE")
        self.generate_button.setObjectName("PredictButton")
        self.generate_button.setMinimumHeight(30)
        self.generate_button.setMinimumWidth(140)
        self.generate_button.setCursor(Qt.PointingHandCursor)
        self.generate_button.clicked.connect(self._generate_algorithm)
        action_bar.addWidget(self.generate_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(100)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        action_bar.addWidget(self.progress_bar)

        self.status_label = QLabel("Sẵn sàng.")
        self.status_label.setStyleSheet("color: #555; font-style: italic;")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        action_bar.addWidget(self.status_label, 1)

        self.copy_button = QPushButton("📋 Copy")
        self.copy_button.setObjectName("LightButton")
        self.copy_button.setMinimumWidth(95)
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy_generated_code)
        
        self.save_button = QPushButton("💾 Lưu File")
        self.save_button.setObjectName("LightButton")
        self.save_button.setMinimumWidth(110)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.clicked.connect(self._save_algorithm_file)

        action_bar.addWidget(self.copy_button)
        action_bar.addWidget(self.save_button)

        main_layout.addLayout(action_bar)

        self.generated_code_display = QPlainTextEdit()
        self.generated_code_display.setReadOnly(True)
        self.generated_code_display.setFont(self.main_app.get_qfont("code"))
        self.generated_code_display.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ccc;")
        main_layout.addWidget(self.generated_code_display, 1)

        self._load_saved_settings()




    def _toggle_api_key_visibility(self, checked):
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            sender = self.sender()
            if sender: sender.setText("Ẩn")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            sender = self.sender()
            if sender: sender.setText("Hiện")

    def _get_api_key_help_text(self) -> str:
        return textwrap.dedent("""
        1. Truy cập Google AI Studio: https://aistudio.google.com/
           (Hoặc Google Cloud Console nếu dùng Vertex AI)
        2. Đăng nhập bằng tài khoản Google của bạn.
        3. Trong Google AI Studio:
           - Nhấp vào "Get API key" ở thanh bên trái.
           - Nhấp vào "Create API key in new project" (hoặc chọn dự án có sẵn).
           - Sao chép API key được tạo ra.
        4. Dán API key vào ô trên.

        <b>Lưu ý:</b> Giữ API key của bạn bí mật và an toàn. Không chia sẻ công khai.
        Việc sử dụng API có thể phát sinh chi phí tuỳ theo chính sách của Google.
        """)

    def _suggest_class_name(self, filename_base):
        class_name = "".join(word.capitalize() for word in filename_base.split('_') if word)
        class_name = re.sub(r'[^a-zA-Z0-9_]', '', class_name)
        if class_name and class_name[0].isdigit():
            class_name = "_" + class_name
        if not class_name:
            class_name = "MyGeminiAlgorithm"
        else:
            class_name = class_name + "Algorithm"

        current_class_name = self.class_name_edit.text()
        if not current_class_name or current_class_name == getattr(self, "_last_suggested_class_name", ""):
             self.class_name_edit.setText(class_name)
        self._last_suggested_class_name = class_name


    def _validate_inputs(self) -> bool:
        """
        Kiểm tra tính hợp lệ của các thông tin đầu vào trước khi gửi yêu cầu tới Gemini.
        Trả về True nếu tất cả hợp lệ, ngược lại trả về False.
        """
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập Gemini API Key.")
            self.api_key_edit.setFocus()
            return False

        logic_desc = self.logic_description_edit.toPlainText().strip()
        if not logic_desc or len(logic_desc) < 10:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng mô tả logic thuật toán chi tiết hơn (tối thiểu 10 ký tự).")
            self.logic_description_edit.setFocus()
            return False

        file_name = self.file_name_edit.text().strip()
        if not file_name:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên file (ví dụ: my_algo).")
            self.file_name_edit.setFocus()
            return False
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', file_name):
            QtWidgets.QMessageBox.warning(self, "Lỗi tên file", "Tên file chỉ được chứa chữ cái, số, dấu gạch ngang (-) và gạch dưới (_).")
            self.file_name_edit.setFocus()
            return False

        class_name = self.class_name_edit.text().strip()
        if not class_name:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên Class (ví dụ: MyAlgorithm).")
            self.class_name_edit.setFocus()
            return False
        
        if not class_name[0].isalpha() or not class_name.isalnum():
            QtWidgets.QMessageBox.warning(self, "Lỗi tên Class", "Tên Class phải bắt đầu bằng chữ cái và không chứa ký tự đặc biệt.")
            self.class_name_edit.setFocus()
            return False

        try:
            algo_desc = self.description_edit.text().strip()
            if not algo_desc:
                QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập mô tả ngắn gọn về chức năng của thuật toán.")
                self.description_edit.setFocus()
                return False
        except AttributeError:
            QtWidgets.QMessageBox.critical(self, "Lỗi hệ thống", "Widget 'description_edit' chưa được khởi tạo trong giao diện.")
            return False

        return True

    def _get_base_algorithm_code(self) -> str:
        base_py_path = self.main_app.algorithms_dir / "base.py"
        if base_py_path.exists():
            self.logger.info(f"Reading BaseAlgorithm from: {base_py_path.resolve()}")
            return base_py_path.read_text(encoding='utf-8')
        else:
            self.logger.warning(
                f"BaseAlgorithm file not found at: {base_py_path.resolve()}. Using hardcoded summary."
            )
            return textwrap.dedent("""
                # Base class (summary - file not found at expected location)
                from abc import ABC, abstractmethod
                import datetime
                import logging
                from pathlib import Path

                class BaseAlgorithm(ABC):
                    def __init__(self, data_results_list=None, cache_dir=None):
                        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
                        self.config = {"description": "Base", "parameters": {}}
                        self._raw_results_list = data_results_list if data_results_list is not None else []
                        self.cache_dir = Path(cache_dir) if cache_dir else None
                        # self._log('debug', f"{self.__class__.__name__} initialized.")

                    def get_config(self) -> dict: return self.config

                    @abstractmethod
                    def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
                        raise NotImplementedError

                    def extract_numbers_from_dict(self, result_dict: dict) -> set:
                         numbers = set()
                         if isinstance(result_dict, dict):
                             for key, value in result_dict.items():
                                 if key in {'date','_id','source','day_of_week','sign','created_at','updated_at','province_name','province_id'}: continue
                                 values_to_check = []
                                 if isinstance(value, (list, tuple)): values_to_check.extend(value)
                                 elif value is not None: values_to_check.append(value)
                                 for item in values_to_check:
                                     if item is None: continue
                                     try:
                                         s_item = str(item).strip(); num = -1
                                         if len(s_item) >= 2 and s_item[-2:].isdigit(): num = int(s_item[-2:])
                                         elif len(s_item) == 1 and s_item.isdigit(): num = int(s_item)
                                         if 0 <= num <= 99: numbers.add(f"{num:02d}") # Trả về chuỗi 2 chữ số
                                     except (ValueError, TypeError): pass
                         return {n for n in numbers if n.isdigit() and 0 <= int(n) <= 99}


                    def _log(self, level: str, message: str):
                        log_method = getattr(self.logger, level.lower(), self.logger.info)
                        log_method(f"[{self.__class__.__name__}] {message}")
            """)

    def _construct_prompt(self) -> str | None:
        file_name_base = self.file_name_edit.text().strip()
        full_file_name = f"{file_name_base}.py"
        class_name = self.class_name_edit.text().strip()
        algo_description = self.description_edit.text().strip().replace('"', '\\"')
        logic_description = self.logic_description_edit.toPlainText().strip()
        base_algo_code = self._get_base_algorithm_code()

        if not algo_description:
            algo_description = f"Algorithm generated based on user description for {class_name}"

        prompt = textwrap.dedent(f"""
        Bạn là một lập trình viên Python chuyên nghiệp, chuyên tạo các thuật toán dự đoán xổ số cho một ứng dụng cụ thể.
        Nhiệm vụ của bạn là tạo ra ĐOẠN CODE PYTHON HOÀN CHỈNH cho một lớp thuật toán mới dựa trên mô tả của người dùng.

        **Bối cảnh:**
        *   Hãy viết thuật toán kế thừa từ BaseAlgorithm, sử dụng hàm predict(self, date_to_predict, historical_results) và trả về dictionary gồm các key từ '00' đến '99' với giá trị là điểm số (float). Không định nghĩa lại lớp BaseAlgorithm mà hãy dùng from algorithms.base import BaseAlgorithm. Thuật toán mới phải kế thừa từ lớp `BaseAlgorithm`. Dưới đây là nội dung của file `algorithms/base.py` mà lớp cha được định nghĩa:
            ```python
            {textwrap.indent(base_algo_code, '            ')}
            ```
        *   Lớp thuật toán mới sẽ được lưu vào file tên là `{full_file_name}` trong thư mục `algorithms`.
        *   Tên của lớp mới phải là `{class_name}`.
        *   Mô tả chung của thuật toán (dùng cho `self.config['description']`) là: "{algo_description}"

        **Yêu cầu chính:**
        Viết code Python đầy đủ cho lớp `{class_name}` bao gồm:
        1.  Import các thư viện cần thiết (ví dụ: `datetime`, `logging`, `collections`, `math`, `numpy` nếu cần tính toán phức tạp, `pathlib`). PHẢI import `BaseAlgorithm` từ `algorithms.base` (LƯU Ý: trong code kết quả, dòng import phải là `from algorithms.base import BaseAlgorithm`).
        2.  Định nghĩa lớp `{class_name}` kế thừa từ `BaseAlgorithm`. (`class {class_name}(BaseAlgorithm):`)
        3.  Triển khai phương thức `__init__(self, *args, **kwargs)`:
            *   Phải gọi `super().__init__(*args, **kwargs)`.
            *   Khởi tạo `self.config` với `description` đã cho và một dictionary `parameters` rỗng (hoặc nếu bạn suy luận được tham số từ mô tả logic, hãy thêm chúng vào đây với giá trị mặc định hợp lý).
            *   Ví dụ: `self.config = {{'description': "{algo_description}", 'parameters': {{'param1': default_value}} }}`
            *   Có thể khởi tạo các thuộc tính khác nếu cần cho logic (ví dụ: `self.some_data = {{}}`).
            *   Thêm dòng log debug báo hiệu khởi tạo: `self._log('debug', f"{{self.__class__.__name__}} initialized.")`
        4.  Triển khai phương thức `predict(self, date_to_predict: datetime.date, historical_results: list) -> dict`:
            *   Phương thức này nhận ngày cần dự đoán (`date_to_predict`) và danh sách kết quả lịch sử (`historical_results`) **trước** ngày đó. `historical_results` là list của dict, mỗi dict có dạng `{{'date': date_obj, 'result': dict_ket_qua_ngay_do}}`.
            *   **Logic cốt lõi:** Dựa vào mô tả logic do người dùng cung cấp dưới đây để tính toán điểm số.
            *   **Mô tả Logic của người dùng:**
                ```
                {textwrap.indent(logic_description, '                ')}
                ```
            *   **Quan trọng:** Phương thức `predict` **PHẢI** trả về một dictionary chứa điểm số (float hoặc int) cho TẤT CẢ các số từ "00" đến "99". Ví dụ: `{{'00': 10.5, '01': -2.0, ..., '99': 5.0}}`. Nếu không có điểm cho số nào đó, hãy trả về 0.0 cho số đó. Khởi tạo `scores = {{f'{{i:02d}}': 0.0 for i in range(100)}}` là một khởi đầu tốt.
            *   Sử dụng các hàm có sẵn từ `BaseAlgorithm`: `self.extract_numbers_from_dict(result_dict)` để lấy các số dạng chuỗi '00'-'99' từ kết quả của một ngày, `self._log('level', 'message')` để ghi log (các level thông dụng: 'debug', 'info', 'warning', 'error').
            *   Nên có log debug ở đầu hàm (`self._log('debug', f"Predicting for {{date_to_predict}}")`) và log info ở cuối (`self._log('info', f"Prediction finished for {{date_to_predict}}. Generated {{len(scores)}} scores.")`).
            *   Xử lý các trường hợp ngoại lệ (ví dụ: không đủ dữ liệu `historical_results`, lỗi tính toán) một cách hợp lý. Nếu không thể tính toán, trả về dict `scores` với tất cả điểm là 0.0.
            *   Đảm bảo code trong `predict` hiệu quả, tránh lặp lại tính toán không cần thiết nếu có thể.
        5.  Hãy viết chi tiết các tham số trong `self.config['parameters']`, để sau này người dùng còn có thể sử dụng công cụ để tinh chỉnh, tối ưu từng tham số cụ thể để tăng tính chính xác khi chạy thuật toán. Các giá trị mặc định cho tham số nên là số (int hoặc float).

        **Định dạng Output:**
        Chỉ cung cấp phần code Python hoàn chỉnh cho file `{full_file_name}`.
        Bắt đầu bằng `# -*- coding: utf-8 -*-`.
        Tiếp theo là `# File: {full_file_name}`.
        Sau đó là import `BaseAlgorithm` từ `algorithms.base` và các thư viện cần thiết khác.
        Rồi đến định nghĩa lớp `{class_name}` và các phương thức của nó (`__init__`, `predict`).
        KHÔNG thêm bất kỳ giải thích, lời bình luận hay ```python ``` nào bên ngoài khối code chính.
        Đảm bảo code sạch sẽ, dễ đọc, tuân thủ PEP 8 và có thụt lề đúng chuẩn Python (4 dấu cách).
        """)
        return prompt.strip()

    def _generate_algorithm(self):
        if not self._validate_inputs():
            return

        api_key = self.api_key_edit.text().strip()
        model_name = self.model_combo.currentText()
        
        full_prompt = self._construct_prompt()
        
        if not full_prompt:
            return

        self.generate_button.setEnabled(False)
        self.generated_code_display.setPlaceholderText("Đang tạo thuật toán, vui lòng đợi...")
        self.progress_bar.setVisible(True)
        self.start_time = time.time()
        
        self.gemini_worker = GeminiWorker(api_key, model_name, full_prompt)
        
        self.gemini_worker.finished.connect(self._on_generation_finished)
        self.gemini_worker.error.connect(self._handle_gemini_error)
        
        self.gemini_worker.start()

    def _on_generation_finished(self, code: str):
        """
        Hàm này được gọi tự động khi GeminiWorker hoàn thành việc tạo code.
        Nó sẽ nhận 'code' (chuỗi văn bản) từ AI và hiển thị lên UI.
        """
        self.generated_code = code 
        
        self.generated_code_display.setPlainText(code)
        
        self.generate_button.setEnabled(True)
        self.generate_button.setText("🚀 TẠO LẠI CODE")
        self.save_button.setEnabled(True)
        self.copy_button.setEnabled(True)
        
        self.progress_bar.setVisible(False)
        
        elapsed = time.time() - self.start_time
        self.status_label.setText(f"✅ Đã tạo xong! ({elapsed:.1f}s)")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        
        QtWidgets.QMessageBox.information(self, "Thành công", "AI đã viết xong code thuật toán cho bạn!")

    def _handle_gemini_error(self, error_message):
        """Xử lý lỗi API và hiển thị popup có nút Auto chuyển model."""
        self.generate_button.setEnabled(True)
        self.generate_button.setText("🚀 TẠO CODE")
        self.progress_bar.setVisible(False)
        self.status_label.setText("❌ Lỗi API hoặc Model.")
        self.status_label.setStyleSheet("color: red;")

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Lỗi Model / API")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setText("Model hiện tại không dùng được hoặc gặp lỗi API.")
        
        auto_button = msg_box.addButton("Chuyển Model Tự Động (Auto)", QMessageBox.ActionRole)
        close_button = msg_box.addButton("Đóng", QMessageBox.RejectRole)
        
        msg_box.exec_()

        if msg_box.clickedButton() == auto_button:
            self._auto_switch_and_retry()

    def _auto_switch_and_retry(self):
        """Tự động tìm model tiếp theo trong danh sách ưu tiên và thực hiện tạo lại code."""
        current_model = self.model_combo.currentText().strip()
        
        full_current_model = current_model if current_model.startswith("models/") else f"models/{current_model}"
            
        next_model = None
        
        if full_current_model in self.PRIORITY_MODELS:
            current_idx = self.PRIORITY_MODELS.index(full_current_model)
            if current_idx + 1 < len(self.PRIORITY_MODELS):
                next_model = self.PRIORITY_MODELS[current_idx + 1]
        else:
            next_model = self.PRIORITY_MODELS[0]

        if next_model:
            self.model_combo.setCurrentText(next_model)
            self.status_label.setText(f"🔄 Đang thử model: {next_model}...")
            
            QtCore.QTimer.singleShot(800, self._generate_algorithm)
        else:
            self.status_label.setText("❌ Đã thử hết các model thông dụng nhưng không thành công.")
            QMessageBox.critical(self, "Lỗi", "Không còn model nào trong danh sách ưu tiên để thử lại.")

    def _update_status_from_worker(self, message):
        if self.start_time:
             elapsed = time.time() - self.start_time
             self.status_label.setText(f"Trạng thái: {message} ({elapsed:.1f}s)")
        else:
             self.status_label.setText(f"Trạng thái: {message}")
        self.status_label.setStyleSheet("color: #007bff;")

    def _handle_gemini_response(self, generated_text):
        elapsed = time.time() - self.start_time if self.start_time else 0
        self.progress_bar.setVisible(False)
        self.generate_button.setEnabled(True)
        self.status_label.setText(f"Trạng thái: Đã nhận kết quả. Đang xử lý... ({elapsed:.1f}s)")
        self.status_label.setStyleSheet("color: #17a2b8;")
        self.logger.debug("Gemini response received:\n" + generated_text[:500] + "...")

        code_match = re.search(r"```(?:python)?\s*([\s\S]*?)\s*```", generated_text, re.IGNORECASE)
        if code_match:
            self.generated_code = code_match.group(1).strip()
            self.logger.info("Successfully extracted Python code block from Gemini response.")
            self.generated_code = self.generated_code.replace("from .base import BaseAlgorithm", "from algorithms.base import BaseAlgorithm")
        else:
            lines_resp = generated_text.strip().splitlines()
            if lines_resp and (lines_resp[0].startswith("# -*- coding: utf-8 -*-") or lines_resp[0].startswith("# File:") or lines_resp[0].startswith("import ") or lines_resp[0].startswith("from ")):
                 self.generated_code = "\n".join(lines_resp)
                 self.logger.warning("Could not find ```python block, assuming response is code based on starting lines.")
                 self.generated_code = self.generated_code.replace("from .base import BaseAlgorithm", "from algorithms.base import BaseAlgorithm")
            else:
                 self.logger.warning("Could not find ```python block and response does not start like Python code. Displaying raw response.")
                 self.generated_code = f"# --- RAW GEMINI RESPONSE (Could not extract Python code) ---\n# {generated_text}"
                 QMessageBox.warning(self, "Không tìm thấy Code", "Gemini đã phản hồi, nhưng không thể tự động trích xuất khối code Python. Vui lòng kiểm tra và chỉnh sửa thủ công.")

        if self.generated_code and not self.generated_code.startswith("# --- RAW GEMINI RESPONSE"):
            today = datetime.date.today()
            date_str = today.strftime("%d/%m/%Y")
            date_comment_line = f"# Date: {date_str}\n"
            
            lines = self.generated_code.splitlines(True)
            
            inserted_date_comment = False
            if len(lines) >= 2 and \
               lines[0].strip() == "# -*- coding: utf-8 -*-" and \
               lines[1].strip().startswith("# File:"):
                new_lines = lines[:2] + [date_comment_line] + lines[2:]
                self.generated_code = "".join(new_lines)
                inserted_date_comment = True
            elif len(lines) >= 1 and lines[0].strip() == "# -*- coding: utf-8 -*-":
                new_lines = lines[:1] + [date_comment_line] + lines[1:]
                self.generated_code = "".join(new_lines)
                inserted_date_comment = True
            
            if not inserted_date_comment:
                self.generated_code = date_comment_line + self.generated_code
            
            self.logger.info(f"Added date comment to generated code: {date_comment_line.strip()}")

        self.generated_code_display.setPlainText(self.generated_code)

        if self.generated_code and not self.generated_code.startswith("# --- RAW GEMINI RESPONSE"):
            self.save_button.setEnabled(True)
            self.copy_button.setEnabled(True)
            status_message = f"Trạng thái: Đã tạo code thành công. Sẵn sàng để lưu. ({elapsed:.1f}s)"
            status_color = "#28a745;"
        else:
             self.save_button.setEnabled(False)
             self.copy_button.setEnabled(True)
             status_message = f"Trạng thái: Không trích xuất được code. Hiển thị phản hồi thô. ({elapsed:.1f}s)"
             status_color = "#ffc107;"

        self.status_label.setText(status_message)
        self.status_label.setStyleSheet(f"color: {status_color};")
        self.start_time = None



    def _copy_generated_code(self):
        code_to_copy = self.generated_code_display.toPlainText()
        if code_to_copy:
            clipboard = QApplication.clipboard()
            clipboard.setText(code_to_copy)
            self.status_label.setText("Trạng thái: Đã sao chép code vào clipboard!")
            self.status_label.setStyleSheet("color: #17a2b8;")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Trạng thái: Sẵn sàng") if self.status_label.text().startswith("Trạng thái: Đã sao chép") else None)
        else:
            QMessageBox.warning(self, "Chưa có Code", "Không có code nào để sao chép.")

    def _save_algorithm_file(self):
        if not self.generated_code or self.generated_code.startswith("# --- RAW GEMINI RESPONSE"):
            QMessageBox.warning(self, "Chưa có Code Hợp Lệ", "Chưa có code hợp lệ được tạo để lưu.")
            return

        file_name_base = self.file_name_edit.text().strip()
        if not re.match(r"^[a-zA-Z0-9_]+$", file_name_base):
            QMessageBox.warning(self, "Tên file không hợp lệ", "Vui lòng kiểm tra lại tên file (chỉ chữ cái, số, gạch dưới) trước khi lưu.")
            self.file_name_edit.setFocus()
            return

        full_file_name = f"{file_name_base}.py"
        save_path = self.ALGORITHMS_DIR / full_file_name

        if save_path.exists():
            reply = QMessageBox.question(self, "Ghi Đè File?",
                                         f"File '{full_file_name}' đã tồn tại trong thư mục '{self.ALGORITHMS_DIR.name}'.\nBạn có muốn ghi đè không?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        try:
            self.ALGORITHMS_DIR.mkdir(parents=True, exist_ok=True)
            save_path.write_text(self.generated_code, encoding='utf-8')
            
            QMessageBox.information(self, "Lưu Thành Công",
                                    f"Đã lưu thuật toán vào:\n{save_path.resolve()}\n\n"
                                    "Các danh sách thuật toán sẽ được tự động làm mới.")
            
            self.status_label.setText(f"Trạng thái: Đã lưu {full_file_name}")
            self.status_label.setStyleSheet("color: #28a745;")

            if self.main_app:
                self.main_app.reload_algorithms()
                if hasattr(self.main_app, 'update_status'):
                    self.main_app.update_status(f"Đã lưu và tải lại thuật toán: {full_file_name}")

        except IOError as e:
            QMessageBox.critical(self, "Lỗi Lưu File", f"Không thể lưu file thuật toán:\n{e}")
            self.status_label.setText("Trạng thái: Lỗi lưu file")
            self.status_label.setStyleSheet("color: #dc3545;")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Không Xác Định", f"Đã xảy ra lỗi khi lưu file:\n{e}")


    def _save_current_settings(self):
        """Lưu Model và API Key vào cả settings.ini và config/gemini.api."""
        api_key = self.api_key_edit.text().strip()
        model = self.model_combo.currentText().strip()

        if hasattr(self.main_app, 'config'):
            if not self.main_app.config.has_section('GEMINI'):
                self.main_app.config.add_section('GEMINI')
            
            self.main_app.config.set('GEMINI', 'api_key', api_key)
            self.main_app.config.set('GEMINI', 'selected_model', model)
            
            models_list = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            if models_list and "Không tìm thấy" not in models_list[0]:
                self.main_app.config.set('GEMINI', 'cached_models', ",".join(models_list))

            try:
                with open('settings.ini', 'w', encoding='utf-8') as configfile:
                    self.main_app.config.write(configfile)
            except Exception as e:
                self.logger.error(f"Lỗi lưu settings.ini: {e}")

        if api_key:
            try:
                if not os.path.exists("config"):
                    os.makedirs("config")
                encoded_str = base64.b64encode(api_key.encode("utf-8")).decode("utf-8")
                with open("config/gemini.api", "w", encoding="utf-8") as f:
                    f.write(encoded_str)
            except Exception as e:
                self.logger.error(f"Lỗi lưu file API: {e}")


    def _load_saved_settings(self):
        """
        Load Model từ settings.ini và giải mã API Key từ config/gemini.api
        """
        if hasattr(self.main_app, 'config'):
            if self.main_app.config.has_option('GEMINI', 'cached_models'):
                cached = self.main_app.config.get('GEMINI', 'cached_models')
                if cached:
                    self.model_combo.blockSignals(True)
                    self.model_combo.clear()
                    self.model_combo.addItems(cached.split(','))
                    self.model_combo.blockSignals(False)

            if self.main_app.config.has_option('GEMINI', 'selected_model'):
                last_model = self.main_app.config.get('GEMINI', 'selected_model')
                self.model_combo.setCurrentText(last_model)

        try:
            import os
            import base64
            
            if os.path.exists("config/gemini.api"):
                with open("config/gemini.api", "r", encoding="utf-8") as f:
                    encrypted_content = f.read().strip()
                
                if encrypted_content:
                    decoded_bytes = base64.b64decode(encrypted_content)
                    real_api_key = decoded_bytes.decode("utf-8")
                    
                    self.api_key_edit.setText(real_api_key)
        except Exception as e:
            print(f"Lỗi đọc file API: {e}")
