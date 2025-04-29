# --- START OF FILE algorithms/base.py ---
# -*- coding: utf-8 -*-

import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
import json
import datetime

# Sử dụng logger được cấu hình từ file chính (test.py)
# Lấy logger theo tên của module này để dễ dàng theo dõi log
base_logger = logging.getLogger(__name__) # Lấy logger với tên là "algorithms.base"

class BaseAlgorithm(ABC):
    """
    Lớp cơ sở trừu tượng cho tất cả các thuật toán dự đoán xổ số.

    Mỗi thuật toán cụ thể cần kế thừa từ lớp này và triển khai
    phương thức `predict()`.
    """

    def __init__(self, data_results_list=None, cache_dir=None):
        """
        Khởi tạo thuật toán cơ sở.

        Args:
            data_results_list (list, optional): Danh sách đầy đủ các kết quả lịch sử
                dưới dạng list của các dict {'date': date_obj, 'result': dict}.
                Mặc định là None, sẽ được gán danh sách rỗng nếu không cung cấp.
            cache_dir (str or Path, optional): Đường dẫn đến thư mục cache
                để thuật toán có thể lưu trữ các kết quả tính toán trung gian.
                Mặc định là None (không sử dụng cache).
        """
        # --- QUAN TRỌNG: Khởi tạo logger TRƯỚC khi gọi self._log ---
        # Lấy logger riêng cho từng instance của lớp con kế thừa
        # Ví dụ: logger sẽ có tên là "algorithms.base.FrequencyAnalysisAlgorithm"
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # --- KẾT THÚC KHỞI TẠO LOGGER ---

        # Khởi tạo config và các thuộc tính khác sau khi logger đã sẵn sàng
        self.config = {
            "description": "Thuật toán cơ sở (chưa có mô tả)",
            "calculation_logic": "base_logic", # Tên logic (có thể dùng để tham chiếu)
            "parameters": {} # Các tham số mặc định của thuật toán
        }
        self._raw_results_list = data_results_list if data_results_list is not None else []

        # Xử lý thư mục cache: đảm bảo là đối tượng Path và tồn tại
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                # Bây giờ gọi _log ở đây là an toàn vì self.logger đã tồn tại
                self._log('debug', f"Thư mục cache được thiết lập và đảm bảo tồn tại: {self.cache_dir}")
            except Exception as e:
                # Gọi _log ở đây cũng an toàn
                self._log('error', f"Không thể tạo hoặc truy cập thư mục cache {self.cache_dir}: {e}")
                self.cache_dir = None # Vô hiệu hóa cache nếu có lỗi

        # Lời gọi log cuối cùng trong __init__ (nếu có) cũng an toàn
        self._log('debug', f"Instance của {self.__class__.__name__} đã được khởi tạo.")

    def get_config(self) -> dict:
        """
        Trả về dictionary chứa cấu hình của thuật toán.

        Cấu hình thường bao gồm:
        - description (str): Mô tả ngắn về thuật toán.
        - calculation_logic (str): Mã định danh cho logic tính toán.
        - parameters (dict): Các tham số mà thuật toán sử dụng.

        Returns:
            dict: Dictionary cấu hình.
        """
        # Lớp con có thể ghi đè phương thức này hoặc chỉ cập nhật self.config trong __init__ của nó
        return self.config

    @abstractmethod
    def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
        """
        Phương thức trừu tượng để dự đoán kết quả cho một ngày cụ thể.
        **PHẢI** được triển khai bởi tất cả các lớp con kế thừa từ BaseAlgorithm.

        Args:
            date_to_predict (datetime.date): Ngày mà chúng ta muốn dự đoán KẾT QUẢ CHO.
                                            Ví dụ: predict(2023-10-26) là dự đoán cho KQ ngày 26/10.
            historical_results (list): Danh sách các dict kết quả lịch sử,
                                       mỗi dict có dạng {'date': date_obj, 'result': dict}.
                                       Quan trọng: Danh sách này CHỈ chứa dữ liệu của các ngày
                                       **TRƯỚC** `date_to_predict`.

        Returns:
            dict: Một dictionary chứa điểm số dự đoán cho các số từ "00" đến "99".
                  Ví dụ: {'01': 10.5, '23': -5.0, ..., '99': 2.1}.
                  Điểm số (thường là float) thể hiện mức độ "tự tin" hoặc "khả năng"
                  mà thuật toán này gán cho mỗi số. Đây thường là điểm số *delta* (thay đổi),
                  và ứng dụng chính sẽ tổng hợp điểm từ nhiều thuật toán.
                  Trả về dict rỗng `{}` nếu có lỗi hoặc không có dự đoán.
        """
        raise NotImplementedError("Phương thức predict() phải được triển khai bởi lớp con.")

    def get_results_in_range(self, start_date: datetime.date, end_date: datetime.date) -> list:
        """
        Lấy danh sách các kết quả lịch sử nằm trong một khoảng thời gian cụ thể (bao gồm cả ngày bắt đầu và kết thúc).

        Args:
            start_date (datetime.date): Ngày bắt đầu của khoảng thời gian.
            end_date (datetime.date): Ngày kết thúc của khoảng thời gian.

        Returns:
            list: Danh sách các dict kết quả trong khoảng thời gian đã cho.
                  Trả về danh sách rỗng nếu không có kết quả nào phù hợp.
        """
        if not self._raw_results_list:
            return []
        return [item for item in self._raw_results_list if start_date <= item['date'] <= end_date]

    def extract_numbers_from_dict(self, result_dict: dict) -> set:
        """
        Trích xuất TẤT CẢ các số có 2 chữ số từ một dictionary kết quả của một ngày.

        Hàm này xử lý các giá trị là số đơn lẻ, chuỗi số, hoặc nằm trong danh sách/tuple.
        Nó sẽ cố gắng lấy 2 chữ số CUỐI CÙNG nếu giá trị là số hoặc chuỗi dài hơn 2 ký tự.
        Nó cũng xử lý số có 1 chữ số.

        Args:
            result_dict (dict): Dictionary chứa kết quả của một ngày.
                Ví dụ: {'special': 12345, 'prize1': 67, 'prize7': ['01', '89', 5]}

        Returns:
            set: Một tập hợp (set) chứa các số nguyên (int) từ 0 đến 99 được tìm thấy trong dict.
                 Trả về set rỗng nếu đầu vào không phải dict hoặc không tìm thấy số hợp lệ.
        """
        numbers = set()
        if not isinstance(result_dict, dict):
            # Không nên log lỗi ở đây vì nó có thể được gọi với dữ liệu không hợp lệ
            # Chỉ cần trả về set rỗng
            # self._log('warning', "extract_numbers_from_dict nhận đầu vào không phải dict.")
            return numbers

        # Các key thường không chứa kết quả xổ số cần phân tích
        keys_to_ignore = {'date', '_id', 'source', 'day_of_week', 'sign', 'created_at', 'updated_at'}

        for key, value in result_dict.items():
            if key in keys_to_ignore:
                 continue

            values_to_check = []
            if isinstance(value, (list, tuple)):
                # Nếu giá trị là list hoặc tuple, duyệt qua từng phần tử
                values_to_check.extend(value)
            elif value is not None:
                # Nếu giá trị không phải list/tuple và không phải None, thêm nó vào để kiểm tra
                values_to_check.append(value)
            # Bỏ qua nếu value là None

            for item in values_to_check:
                try:
                    s_item = str(item).strip() # Chuyển thành chuỗi và loại bỏ khoảng trắng thừa
                    num = -1 # Giá trị mặc định nếu không parse được

                    if len(s_item) >= 2 and s_item[-2:].isdigit():
                        # Ưu tiên lấy 2 ký tự cuối nếu là số
                        num = int(s_item[-2:])
                    elif len(s_item) == 1 and s_item.isdigit():
                         # Xử lý trường hợp số có 1 chữ số
                         num = int(s_item)

                    # Chỉ thêm vào set nếu số nằm trong khoảng 00-99
                    if 0 <= num <= 99:
                        numbers.add(num)
                    # else: # Gỡ comment để debug nếu muốn biết các giá trị không hợp lệ bị bỏ qua
                    #     if s_item: # Chỉ log nếu chuỗi không rỗng
                    #         self._log('debug', f"Bỏ qua giá trị không hợp lệ (ngoài 0-99 hoặc không parse được): '{s_item}' từ key '{key}'")

                except (ValueError, TypeError):
                    # Bỏ qua nếu không thể chuyển đổi item thành chuỗi hoặc số
                    # Không nên log warning ở đây vì dữ liệu có thể chứa nhiều thứ không phải số
                    # self._log('warning', f"Không thể phân tích số từ item '{item}' (kiểu {type(item)}) trong key '{key}'")
                    pass # Tiếp tục vòng lặp
        return numbers

    # Phương thức ghi log nội bộ, sử dụng logger của instance
    def _log(self, level: str, message: str):
        """
        Ghi log một thông điệp với cấp độ được chỉ định.

        Sử dụng logger riêng của instance thuật toán (ví dụ: "algorithms.base.MyAlgorithm")
        để dễ dàng lọc và theo dõi log của từng thuật toán.

        Args:
            level (str): Cấp độ log (ví dụ: 'debug', 'info', 'warning', 'error', 'critical').
            message (str): Nội dung thông điệp cần ghi log.
        """
        # Lấy phương thức ghi log tương ứng từ logger của instance
        # Ví dụ: self.logger.info(message), self.logger.error(message)
        # Nếu level không hợp lệ, mặc định ghi ở cấp độ warning
        log_method = getattr(self.logger, level.lower(), self.logger.warning)
        try:
            # Đảm bảo logger đã được khởi tạo (kiểm tra lại cho chắc)
            if hasattr(self, 'logger') and self.logger:
                 log_method(message)
            else:
                 # Nếu logger chưa có vì lý do nào đó, in ra stderr
                 print(f"[FALLBACK LOG - {self.__class__.__name__} - {level.upper()}] {message}", file=sys.stderr)
        except Exception as log_err:
            # Đề phòng trường hợp có lỗi xảy ra ngay cả khi ghi log
            print(f"[LOGGING ERROR in {self.__class__.__name__}] Failed to log message: '{message}'. Error: {log_err}", file=sys.stderr)

# --- END OF FILE algorithms/base.py ---
