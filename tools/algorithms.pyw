# DESC: Chương trình tạo thuật toán bằng Gemini.
import sys
import os
import logging
import textwrap
import re
import threading
import queue
import time
import base64

from pathlib import Path
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFileDialog, QMessageBox, QWidget, QPlainTextEdit,
    QScrollArea, QSizePolicy, QGridLayout, QTabWidget, QProgressBar, QApplication,
    QTextBrowser
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QDesktopServices, QIcon
from PyQt5.QtCore import QUrl

CONFIG_DIR = Path("../config")
API_KEY_FILE = CONFIG_DIR / "gemini.api"
ICON_FILE = CONFIG_DIR / "logo.png"
ALGORITHMS_DIR_DEFAULT = Path("../algorithms")


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#000080"))
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            "\\bFalse\\b", "\\bNone\\b", "\\bTrue\\b", "\\band\\b", "\\bas\\b",
            "\\bassert\\b", "\\basync\\b", "\\bawait\\b", "\\bbreak\\b", "\\bclass\\b",
            "\\bcontinue\\b", "\\bdef\\b", "\\bdel\\b", "\\belif\\b", "\\belse\\b",
            "\\bexcept\\b", "\\bfinally\\b", "\\bfor\\b", "\\bfrom\\b", "\\bglobal\\b",
            "\\bif\\b", "\\bimport\\b", "\\bin\\b", "\\bis\\b", "\\blambda\\b",
            "\\bnonlocal\\b", "\\bnot\\b", "\\bor\\b", "\\bpass\\b", "\\braise\\b",
            "\\breturn\\b", "\\btry\\b", "\\bwhile\\b", "\\bwith\\b", "\\byield\\b",
            "\\bself\\b", "\\bin\\b", "\\bisinstance\\b", "\\bint\\b", "\\bfloat\\b",
            "\\bstr\\b", "\\blist\\b", "\\bdict\\b", "\\btuple\\b", "\\bset\\b", "\\bdatetime\\b"
        ]
        for word in keywords:
            rule = (re.compile(word), keywordFormat)
            self.highlightingRules.append(rule)

        selfFormat = QTextCharFormat()
        selfFormat.setForeground(QColor("#900090"))
        rule = (re.compile("\\bself\\."), selfFormat)
        self.highlightingRules.append(rule)

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#008000"))
        self.highlightingRules.append((re.compile("\".*?\""), stringFormat))
        self.highlightingRules.append((re.compile("'.*?'"), stringFormat))
        self.highlightingRules.append((re.compile("\"\"\"(.*?)\"\"\"", re.DOTALL), stringFormat))
        self.highlightingRules.append((re.compile("'''(.*?)'''", re.DOTALL), stringFormat))


        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#0000FF"))
        self.highlightingRules.append((re.compile("\\b[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?\\b"), numberFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#808080"))
        commentFormat.setFontItalic(True)
        self.highlightingRules.append((re.compile("#[^\n]*"), commentFormat))

        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#A020F0"))
        functionFormat.setFontWeight(QFont.Bold)
        self.highlightingRules.append((re.compile("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\()"), functionFormat))

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#2E8B57"))
        classFormat.setFontWeight(QFont.Bold)
        self.highlightingRules.append((re.compile("\\b[A-Z][a-zA-Z0-9_]*\\b"), classFormat))


    def highlightBlock(self, text):
        for pattern, format_obj in self.highlightingRules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, format_obj)



class GeminiWorker(QObject):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, api_key, prompt):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self._is_running = True

    def run(self):
        if not HAS_GEMINI:
            self.error_occurred.emit("Thư viện 'google-generativeai' chưa được cài đặt.")
            return

        try:
            self.status_update.emit("Đang cấu hình Gemini...")
            genai.configure(api_key=self.api_key)

            self.status_update.emit("Đang tạo mô hình Gemini...")
            model = genai.GenerativeModel('gemini-1.5-flash')

            self.status_update.emit("Đang gửi yêu cầu đến Gemini API...")
            response = model.generate_content(self.prompt)

            self.status_update.emit("Đã nhận phản hồi từ Gemini.")
            generated_text = response.text
            self.result_ready.emit(generated_text)

        except ValueError as ve:
             if "API_KEY" in str(ve) or "api key not valid" in str(ve).lower():
                  self.error_occurred.emit(f"Lỗi API Key: {ve}. Vui lòng kiểm tra lại.")
             else:
                  self.error_occurred.emit(f"Lỗi giá trị khi gọi Gemini: {ve}")
        except Exception as e:
            logging.error(f"Lỗi khi gọi Gemini API: {e}", exc_info=True)
            error_message = f"Lỗi giao tiếp với Gemini API: {type(e).__name__}. Chi tiết: {e}"
            if "api key not valid" in str(e).lower():
                 error_message = "Lỗi: API key không hợp lệ. Vui lòng kiểm tra lại."
            elif "permission denied" in str(e).lower() or "quota" in str(e).lower():
                 error_message = "Lỗi: Có thể API key hết hạn, hết quota hoặc không có quyền truy cập mô hình."
            elif "Deadline Exceeded" in str(e):
                 error_message = "Lỗi: Yêu cầu tới Gemini bị quá thời gian. Vui lòng thử lại."
            elif "resource exhausted" in str(e).lower():
                 error_message = "Lỗi: Tài nguyên hoặc quota đã hết. Vui lòng kiểm tra tài khoản Google AI/Cloud."
            self.error_occurred.emit(error_message)

class AlgorithmGeminiBuilderDialog(QDialog):
    def __init__(self, parent=None, algorithms_dir=None):
        super().__init__(parent)
        self.setWindowTitle("Algorithm Generation")
        self.setMinimumSize(850, 700)
        self.algorithms_dir = Path(algorithms_dir) if algorithms_dir else ALGORITHMS_DIR_DEFAULT
        self.generated_code = ""
        self.api_key = ""
        self.gemini_thread = None
        self.gemini_worker = None
        self.start_time = None

        self._set_window_icon()

        self._load_api_key()

        self._setup_ui()

    def _set_window_icon(self):
        """Sets the window icon if config/logo.png exists."""
        if ICON_FILE.is_file():
            self.setWindowIcon(QIcon(str(ICON_FILE)))
        else:
            logging.warning(f"Icon file not found: {ICON_FILE}")

    def _load_api_key(self):
        """Loads the API key from the encoded file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if API_KEY_FILE.is_file():
                encoded_key = API_KEY_FILE.read_bytes()
                self.api_key = base64.b64decode(encoded_key).decode('utf-8')
                logging.info(f"Loaded API key from {API_KEY_FILE}")
            else:
                self.api_key = ""
                logging.info(f"API key file not found: {API_KEY_FILE}. Key is empty.")
        except (IOError, base64.binascii.Error, UnicodeDecodeError) as e:
            logging.error(f"Failed to load or decode API key from {API_KEY_FILE}: {e}")
            self.api_key = ""

    def _save_api_key(self):
        """Saves the current API key to the encoded file."""
        key_to_save = self.api_key_edit.text().strip()
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            encoded_key = base64.b64encode(key_to_save.encode('utf-8'))
            API_KEY_FILE.write_bytes(encoded_key)
            self.api_key = key_to_save
            logging.info(f"Saved API key to {API_KEY_FILE}")
            return True
        except IOError as e:
            logging.error(f"Failed to save API key to {API_KEY_FILE}: {e}")
            QMessageBox.critical(self, "Lỗi Lưu API Key", f"Không thể lưu API key vào file:\n{e}")
            return False

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        generator_widget = QWidget()
        generator_layout = QVBoxLayout(generator_widget)
        generator_layout.setSpacing(10)

        info_form = QFormLayout()
        info_form.setSpacing(8)
        self.file_name_edit = QLineEdit()
        self.file_name_edit.setPlaceholderText("Ví dụ: advanced_frequency")
        self.file_name_edit.textChanged.connect(self._suggest_class_name)
        info_form.addRow("📗Tên file:", self.file_name_edit)

        self.class_name_edit = QLineEdit()
        self.class_name_edit.setPlaceholderText("Ví dụ: AdvancedFrequencyAlgorithm")
        info_form.addRow("📒Tên Lớp (Class):", self.class_name_edit)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Mô tả ngắn gọn về thuật toán")
        info_form.addRow("♻️Mô tả thuật toán:", self.description_edit)
        generator_layout.addLayout(info_form)

        logic_label = QLabel("✍️ Mô tả thuật toán (tiếng Việt hoặc Anh):")
        generator_layout.addWidget(logic_label)
        self.logic_description_edit = QPlainTextEdit()
        self.logic_description_edit.setPlaceholderText(
            "Ví dụ:\n"
            "- Tính điểm dựa trên tần suất xuất hiện trong 90 ngày qua.\n"
            "- Cộng thêm điểm nếu số đó là số lân cận (trong khoảng +/- 3) của giải đặc biệt ngày hôm trước.\n"
            "- Giảm điểm mạnh nếu số đó đã về trong 2 ngày liên tiếp gần đây.\n"
            "- Ưu tiên các số không xuất hiện trong 10 ngày gần nhất...\n"
            "(Càng chi tiết, Gemini càng tạo code tốt hơn)"
        )
        self.logic_description_edit.setMinimumHeight(120)
        generator_layout.addWidget(self.logic_description_edit)

        self.generate_button = QPushButton("🧠Tạo Thuật Toán")
        self.generate_button.setStyleSheet("padding: 8px;")
        self.generate_button.clicked.connect(self._generate_algorithm)
        generator_layout.addWidget(self.generate_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(10)
        generator_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Trạng thái: Sẵn sàng")
        self.status_label.setStyleSheet("color: #6c757d;")
        generator_layout.addWidget(self.status_label)

        code_label = QLabel("Nội dung thuật toán:")
        generator_layout.addWidget(code_label)
        self.generated_code_display = QPlainTextEdit()
        self.generated_code_display.setReadOnly(True)
        font = QFont("Consolas", 10)
        if not font.exactMatch(): font = QFont("Courier", 10)
        self.generated_code_display.setFont(font)

        self.generated_code_display.setMinimumHeight(200)
        self.highlighter = PythonSyntaxHighlighter(self.generated_code_display.document())
        generator_layout.addWidget(self.generated_code_display, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        self.copy_button = QPushButton("📄Sao chép")
        self.copy_button.setEnabled(False)
        self.copy_button.setStyleSheet("padding: 8px;")
        self.copy_button.clicked.connect(self._copy_generated_code)
        button_layout.addWidget(self.copy_button)

        self.save_button = QPushButton("💾 Lưu")
        self.save_button.setEnabled(False)
        self.save_button.setStyleSheet("padding: 8px;")
        self.save_button.clicked.connect(self._save_algorithm_file)
        button_layout.addWidget(self.save_button)

        generator_layout.addLayout(button_layout)

        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setSpacing(10)
        settings_layout.setAlignment(Qt.AlignTop)

        api_group = QWidget()
        api_layout = QHBoxLayout(api_group)
        api_layout.setContentsMargins(0,0,0,0)
        api_layout.addWidget(QLabel("🔑Gemini API Key:"))
        self.api_key_edit = QLineEdit(self.api_key)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Nhập API Key của Google AI Studio / Vertex AI")
        self.api_key_edit.editingFinished.connect(self._save_api_key)
        api_layout.addWidget(self.api_key_edit, 1)

        show_api_button = QPushButton("👁‍🗨Hiện")
        show_api_button.setCheckable(True)
        show_api_button.toggled.connect(self._toggle_api_key_visibility)
        api_layout.addWidget(show_api_button)

        settings_layout.addWidget(api_group)

        save_info_label = QLabel("<i>API Key sẽ được mã hóa và lưu tự động vào file <code>config/gemini.api</code> khi bạn thay đổi hoặc đóng cửa sổ.</i>")
        save_info_label.setWordWrap(True)
        save_info_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        settings_layout.addWidget(save_info_label)


        api_help_label = QLabel("<b>Hướng dẫn lấy Gemini API Key:</b>")
        settings_layout.addWidget(api_help_label)

        help_text_content = self._get_api_key_help_text()
        api_help_display = QTextBrowser()
        api_help_display.setOpenExternalLinks(True)
        api_help_display.setHtml(help_text_content.replace("\n", "<br/>").replace("https://aistudio.google.com/",'<a href="https://aistudio.google.com/">https://aistudio.google.com/</a>'))
        api_help_display.setFixedHeight(180)
        api_help_display.setStyleSheet("border: 1px solid #ccc; background-color: #f8f9fa; padding: 5px;")

        settings_layout.addWidget(api_help_display)
        settings_layout.addStretch(1)

        self.tab_widget.addTab(generator_widget, "🧩 Trình Tạo Thuật Toán")
        self.tab_widget.addTab(settings_widget, "⚙️ Cài Đặt")


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
        """Returns the help text for getting the API key."""
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
        """Gợi ý tên lớp dựa trên tên file (không có .py)."""
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
        """Kiểm tra các trường nhập liệu cần thiết."""
        self.api_key = self.api_key_edit.text().strip()
        file_name_base = self.file_name_edit.text().strip()
        class_name = self.class_name_edit.text().strip()
        logic_desc = self.logic_description_edit.toPlainText().strip()

        if not self.api_key:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng nhập Gemini API Key trong tab 'Cài Đặt'.")
            self.tab_widget.setCurrentIndex(1)
            self.api_key_edit.setFocus()
            return False
        if not HAS_GEMINI:
            QMessageBox.critical(self, "Thiếu Thư Viện", "Vui lòng cài đặt thư viện 'google-generativeai' bằng lệnh:\n\npip install google-generativeai")
            return False
        if not re.match(r"^[a-zA-Z0-9_]+$", file_name_base):
            QMessageBox.warning(self, "Tên file không hợp lệ", "Tên file chỉ nên chứa chữ cái, số và dấu gạch dưới (_).")
            self.tab_widget.setCurrentIndex(0)
            self.file_name_edit.setFocus()
            return False
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", class_name) or class_name == "BaseAlgorithm":
            QMessageBox.warning(self, "Tên lớp không hợp lệ", "Tên lớp phải là định danh Python hợp lệ và không trùng 'BaseAlgorithm'.")
            self.tab_widget.setCurrentIndex(0)
            self.class_name_edit.setFocus()
            return False
        if not logic_desc:
            QMessageBox.warning(self, "Thiếu Mô Tả Logic", "Vui lòng mô tả logic bạn muốn cho thuật toán.")
            self.tab_widget.setCurrentIndex(0)
            self.logic_description_edit.setFocus()
            return False
        return True

    def _get_base_algorithm_code(self) -> str:
        """Lấy nội dung code của lớp BaseAlgorithm."""
        try:
            base_path = Path(__file__).parent.parent / "algorithms" / "base.py"
            if not base_path.exists():
                 base_path = Path("algorithms") / "base.py"

            if base_path.exists():
                logging.info(f"Reading BaseAlgorithm from: {base_path}")
                return base_path.read_text(encoding='utf-8')
            else:
                logging.warning(f"BaseAlgorithm file not found at expected locations: {base_path}")
                return textwrap.dedent("""
                    # Base class (summary - file not found at expected location)
                    from abc import ABC, abstractmethod
                    import datetime
                    import logging
                    from pathlib import Path # Added Path

                    class BaseAlgorithm(ABC):
                        # Simplified init
                        def __init__(self, data_results_list=None, cache_dir=None):
                            self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
                            self.config = {"description": "Base", "parameters": {}}
                            self._raw_results_list = data_results_list if data_results_list is not None else []
                            self.cache_dir = Path(cache_dir) if cache_dir else None
                            # Assume basic logging setup happens elsewhere
                            # self._log('debug', f"{self.__class__.__name__} initialized.") # Can't use _log before it might be defined

                        def get_config(self) -> dict: return self.config

                        @abstractmethod
                        def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
                            # MUST return dict like {'00': score, ..., '99': score}
                            raise NotImplementedError

                        # Include simplified helper methods if needed by the prompt
                        def extract_numbers_from_dict(self, result_dict: dict) -> set:
                             # Simple placeholder if base.py not found
                             numbers = set()
                             if isinstance(result_dict, dict):
                                 # Simplified: check common keys like 'gdb', 'g1', etc.
                                 for key, value in result_dict.items():
                                     if isinstance(value, str) and value.isdigit() and len(value) >= 2:
                                         numbers.add(value[-2:])
                                     elif isinstance(value, list): # Handle lists like lo_to
                                         for item in value:
                                             if isinstance(item, str) and item.isdigit() and len(item) == 2:
                                                 numbers.add(item)
                             return {f"{int(n):02d}" for n in numbers if n.isdigit() and 0 <= int(n) <= 99} # Ensure 00-99 format


                        def _log(self, level: str, message: str):
                            log_method = getattr(self.logger, level.lower(), self.logger.info) # Default to info
                            log_method(message)
                """)
        except Exception as e:
            logging.error(f"Error reading base algorithm code: {e}")
            return f"# Error: Could not read base algorithm code: {e}"

    def _construct_prompt(self) -> str | None:
        """Xây dựng prompt chi tiết cho Gemini."""
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
        *   Thuật toán mới phải kế thừa từ lớp `BaseAlgorithm`. Dưới đây là nội dung của file `algorithms/base.py` mà lớp cha được định nghĩa:
            ```python
            {textwrap.indent(base_algo_code, '            ')}
            ```
        *   Lớp thuật toán mới sẽ được lưu vào file tên là `{full_file_name}` trong thư mục `algorithms`.
        *   Tên của lớp mới phải là `{class_name}`.
        *   Mô tả chung của thuật toán (dùng cho `self.config['description']`) là: "{algo_description}"

        **Yêu cầu chính:**
        Viết code Python đầy đủ cho lớp `{class_name}` bao gồm:
        1.  Import các thư viện cần thiết (ví dụ: `datetime`, `logging`, `collections`, `math`, `numpy` nếu cần tính toán phức tạp, `pathlib`). PHẢI import `BaseAlgorithm` từ `.base`.
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
            *   Sử dụng các hàm có sẵn từ `BaseAlgorithm`: `self.extract_numbers_from_dict(result_dict)` để lấy các số dạng '00'-'99' từ kết quả của một ngày, `self._log('level', 'message')` để ghi log (các level thông dụng: 'debug', 'info', 'warning', 'error').
            *   Nên có log debug ở đầu hàm (`self._log('debug', f"Predicting for {{date_to_predict}}")`) và log info ở cuối (`self._log('info', f"Prediction finished for {{date_to_predict}}. Generated {{len(scores)}} scores.")`).
            *   Xử lý các trường hợp ngoại lệ (ví dụ: không đủ dữ liệu `historical_results`, lỗi tính toán) một cách hợp lý. Nếu không thể tính toán, trả về dict `scores` với tất cả điểm là 0.0.
            *   Đảm bảo code trong `predict` hiệu quả, tránh lặp lại tính toán không cần thiết nếu có thể.

        **Định dạng Output:**
        Chỉ cung cấp phần code Python hoàn chỉnh cho file `{full_file_name}`.
        Bắt đầu bằng `# -*- coding: utf-8 -*-`.
        Tiếp theo là `# File: {full_file_name}`.
        Sau đó là import `BaseAlgorithm` và các thư viện cần thiết khác.
        Rồi đến định nghĩa lớp `{class_name}` và các phương thức của nó (`__init__`, `predict`).
        KHÔNG thêm bất kỳ giải thích, lời bình luận hay ```python ``` nào bên ngoài khối code chính.
        Đảm bảo code sạch sẽ, dễ đọc, tuân thủ PEP 8 và có thụt lề đúng chuẩn Python (4 dấu cách).
        """)

        return prompt.strip()


    def _generate_algorithm(self):
        """Bắt đầu quá trình tạo thuật toán."""
        if not self._validate_inputs():
            return

        if not self._save_api_key():
             QMessageBox.warning(self, "Lỗi Lưu Key", "Không thể lưu API key, vui lòng kiểm tra lại.")

        prompt = self._construct_prompt()
        if prompt is None:
            QMessageBox.critical(self, "Lỗi Tạo Prompt", "Không thể tạo yêu cầu cho Gemini.")
            return

        self.generated_code = ""
        self.generated_code_display.setPlainText("")
        self.save_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Trạng thái: Đang liên lạc với Gemini API...")
        self.status_label.setStyleSheet("color: #ffc107;")
        self.start_time = time.time()

        self.gemini_worker = GeminiWorker(self.api_key, prompt)
        self.gemini_thread = threading.Thread(target=self.gemini_worker.run, daemon=True)

        self.gemini_worker.result_ready.connect(self._handle_gemini_response)
        self.gemini_worker.error_occurred.connect(self._handle_gemini_error)
        self.gemini_worker.status_update.connect(self._update_status_from_worker)

        self.gemini_thread.start()

    def _update_status_from_worker(self, message):
        """Cập nhật status label từ worker thread."""
        if self.start_time:
             elapsed = time.time() - self.start_time
             self.status_label.setText(f"Trạng thái: {message} ({elapsed:.1f}s)")
        else:
             self.status_label.setText(f"Trạng thái: {message}")
        self.status_label.setStyleSheet("color: #070bff;")

    def _handle_gemini_response(self, generated_text):
        """Xử lý kết quả trả về từ Gemini."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        self.progress_bar.setVisible(False)
        self.generate_button.setEnabled(True)
        self.status_label.setText(f"Trạng thái: Đã nhận kết quả. Đang xử lý... ({elapsed:.1f}s)")
        self.status_label.setStyleSheet("color: #17a2b8;")
        logging.debug("Gemini response received:\n" + generated_text[:500] + "...")

        code_match = re.search(r"```(?:python)?\s*([\s\S]*?)\s*```", generated_text, re.IGNORECASE)
        if code_match:
            self.generated_code = code_match.group(1).strip()
            logging.info("Successfully extracted Python code block from Gemini response.")
        else:
            lines = generated_text.strip().splitlines()
            if lines and (lines[0].startswith("# -*- coding: utf-8 -*-") or lines[0].startswith("# File:") or lines[0].startswith("import ") or lines[0].startswith("from ")):
                 self.generated_code = "\n".join(lines)
                 logging.warning("Could not find ```python block, assuming response is code based on starting lines.")
            else:
                 logging.warning("Could not find ```python block and response does not start like Python code. Displaying raw response.")
                 self.generated_code = f"# --- RAW GEMINI RESPONSE (Could not extract Python code) ---\n# {generated_text}"
                 QMessageBox.warning(self, "Không tìm thấy Code", "Gemini đã phản hồi, nhưng không thể tự động trích xuất khối code Python. Vui lòng kiểm tra và chỉnh sửa thủ công.")


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


    def _handle_gemini_error(self, error_message):
        """Xử lý lỗi trả về từ worker."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        logging.error(f"Gemini worker error: {error_message}")
        QMessageBox.critical(self, "Lỗi Gemini API", error_message)

        self.generated_code = ""
        self.generated_code_display.setPlainText(f"# Lỗi xảy ra:\n# {error_message}")
        self.save_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.generate_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        status_text = f"Trạng thái: Lỗi - {error_message} ({elapsed:.1f}s)"
        if len(status_text) > 150:
            status_text = status_text[:147] + "..."
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet("color: #dc3545;")
        self.start_time = None


    def _copy_generated_code(self):
        """Copies the generated code to the clipboard."""
        code_to_copy = self.generated_code_display.toPlainText()
        if code_to_copy:
            clipboard = QApplication.clipboard()
            clipboard.setText(code_to_copy)
            self.status_label.setText("Trạng thái: Đã sao chép code vào clipboard!")
            self.status_label.setStyleSheet("color: #17a2b8;")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Trạng thái: Sẵn sàng"))
        else:
            QMessageBox.warning(self, "Chưa có Code", "Không có code nào để sao chép.")


    def _save_algorithm_file(self):
        """Lưu code đã tạo vào file."""
        if not self.generated_code or self.generated_code.startswith("# --- RAW GEMINI RESPONSE"):
            QMessageBox.warning(self, "Chưa có Code Hợp Lệ", "Chưa có code hợp lệ được tạo để lưu.")
            return

        file_name_base = self.file_name_edit.text().strip()
        if not re.match(r"^[a-zA-Z0-9_]+$", file_name_base):
            QMessageBox.warning(self, "Tên file không hợp lệ", "Vui lòng kiểm tra lại tên file (chỉ chữ cái, số, gạch dưới) trước khi lưu.")
            self.tab_widget.setCurrentIndex(0)
            self.file_name_edit.setFocus()
            return

        full_file_name = f"{file_name_base}.py"
        save_path = self.algorithms_dir / full_file_name

        if save_path.exists():
            reply = QMessageBox.question(self, "Ghi Đè File?",
                                         f"File '{full_file_name}' đã tồn tại trong thư mục '{self.algorithms_dir.name}'.\nBạn có muốn ghi đè không?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        try:
            self.algorithms_dir.mkdir(parents=True, exist_ok=True)
            save_path.write_text(self.generated_code, encoding='utf-8')
            QMessageBox.information(self, "Lưu Thành Công",
                                    f"Đã lưu thuật toán vào:\n{save_path}\n\n"
                                    "Bạn có thể cần 'Tải lại thuật toán' trong ứng dụng chính để sử dụng.")
            self.status_label.setText(f"Trạng thái: Đã lưu {full_file_name}")
            self.status_label.setStyleSheet("color: #28a745;")

        except IOError as e:
            QMessageBox.critical(self, "Lỗi Lưu File", f"Không thể lưu file thuật toán:\n{e}")
            self.status_label.setText("Trạng thái: Lỗi lưu file")
            self.status_label.setStyleSheet("color: #dc3545;")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Không Xác Định", f"Đã xảy ra lỗi khi lưu file:\n{e}")
            self.status_label.setText("Trạng thái: Lỗi không xác định khi lưu")
            self.status_label.setStyleSheet("color: #dc3545;")

    def closeEvent(self, event):
        """Handle the dialog closing event."""
        try:
            self._save_api_key()
        except Exception as e:
             logging.error(f"Error saving API key during closeEvent: {e}")

        if self.gemini_thread and self.gemini_thread.is_alive():
             logging.warning("Gemini thread is still alive upon closing dialog (daemon thread, should terminate with app).")

        super().closeEvent(event)

        app_instance = QApplication.instance()
        if app_instance:
             logging.debug("Attempting to quit QApplication event loop.")
             app_instance.quit()

        logging.warning("Attempting sys.exit(0) to terminate.")
        sys.exit(0)


def run_gemini_algorithm_builder(parent=None, algorithms_dir=None):
    if not HAS_GEMINI:
         QMessageBox.critical(parent, "Thiếu Thư Viện", "Chức năng này yêu cầu thư viện 'google-generativeai'.\nVui lòng cài đặt bằng lệnh:\n\npip install google-generativeai")
         return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    dialog = AlgorithmGeminiBuilderDialog(parent, algorithms_dir)
    dialog.exec_()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    app = QApplication(sys.argv)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    test_algo_dir = ALGORITHMS_DIR_DEFAULT
    test_algo_dir.mkdir(exist_ok=True)
    print(f"Testing Gemini builder, will save algorithms to: {test_algo_dir}")
    print(f"API Key will be loaded/saved from/to: {API_KEY_FILE}")

    if not ICON_FILE.is_file():
        try:
            print(f"INFO: Dummy icon {ICON_FILE} not found. Create it manually or ignore icon warning.")
        except Exception as e:
            print(f"Could not check/create dummy icon file: {e}")


    run_gemini_algorithm_builder(algorithms_dir=test_algo_dir)

    exit_code = app.exec_()
    logging.info(f"QApplication event loop finished with exit code: {exit_code}")
    sys.exit(exit_code)
