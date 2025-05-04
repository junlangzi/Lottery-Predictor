# Nguyên tắc viết thuật toán cho chương trình


***(update 04/05/2025 - chạy file algorithms.py để viết thuật toán)***  <br><br>

**Quy trình Viết Thuật Toán Mới**

<br> <br><br>
**Bước 1: Tạo File Thuật Toán** 


1. **Vị trí:** Tạo một file Python mới (đuôi .py) bên trong thư mục algorithms/ của dự án.
2. **Tên File:** Đặt tên file một cách gợi nhớ, sử dụng chữ thường và dấu gạch dưới nếu cần (ví dụ: trend\_following.py, gan\_based\_predictor.py). **Tránh đặt tên là \_\_init\_\_.py hoặc base.py.**
3. **(Khuyến nghị) Encoding:** Thêm dòng # -\*- coding: utf-8 -\*- ở đầu file nếu bạn dự định dùng tiếng Việt trong comment hoặc chuỗi.


**Bước 2: Import Các Thành Phần Cơ Bản**

1. **Import BaseAlgorithm:** Dòng quan trọng nhất là import lớp cơ sở từ file base.py:

    ```
    from algorithms.base import BaseAlgorithm
    ```

<br>
2. **Import Thư Viện Khác:** Import bất kỳ thư viện chuẩn Python nào bạn cần (ví dụ: datetime, logging, collections, math, random, json).

    ```
    import datetime
    import logging # Logger sẽ được lấy từ BaseAlgorithm, không cần cấu hình ở đây
    from collections import Counter
    # import numpy as np # Ví dụ nếu cần numpy (phải cài đặt riêng)
    ```

<br>

**Bước 3: Định Nghĩa Class Kế Thừa BaseAlgorithm**

1. **Khai Báo Class:** Tạo một class mới kế thừa trực tiếp từ BaseAlgorithm. Tên class nên theo quy ước PascalCase (ví dụ: TrendFollowingAlgorithm).

    ```
    class TrendFollowingAlgorithm(BaseAlgorithm):
        # Nội dung class sẽ viết ở các bước tiếp theo
        pass
    ```

<br>

**Bước 4: Triển Khai Phương Thức \_\_init\_\_ (Hàm Khởi Tạo)**
Đây là phần **bắt buộc** và cần tuân thủ cấu trúc sau:

1. **Gọi super().\_\_init\_\_():** Lệnh này phải được gọi **ngay đầu tiên** trong \_\_init\_\_ để khởi tạo các thành phần của lớp cha.
2. **Định Nghĩa self.config:** Tạo một thuộc tính instance tên là self.config. Giá trị của nó phải là một dictionary chứa ít nhất các key sau:
    * "description" (str): Một chuỗi mô tả ngắn gọn chức năng của thuật toán. Mô tả này sẽ hiển thị trong giao diện người dùng (cả tab Main và Optimizer).
    * "parameters" (dict): Một dictionary chứa các tham số mà thuật toán của bạn sử dụng.
        * **Key:** Tên tham số (dạng chuỗi, ví dụ: "window\_size", "ema\_alpha").
        * **Value:** Giá trị mặc định của tham số đó.
        * **Quan trọng cho Optimizer:** Để một tham số có thể được chỉnh sửa và tối ưu hóa trong tab Optimizer, giá trị mặc định của nó **phải là kiểu số (int hoặc float)**. OptimizerEmbedded sẽ chỉ hiển thị và xử lý các tham số số này. Các tham số có kiểu khác (string, boolean, list,...) sẽ không xuất hiện trong phần cài đặt tối ưu.
3. **(Tùy chọn) Khởi Tạo Thuộc Tính Khác:** Khởi tạo các biến instance khác mà thuật toán cần dùng để lưu trạng thái (ví dụ: self.moving\_average\_data = {}).
4. **(Khuyến nghị) Logging:** Sử dụng self.\_log('debug', '...') để ghi log thông báo khởi tạo thành công.

```
def __init__(self, data_results_list=None, cache_dir=None):
        # BƯỚC 4.1: Gọi __init__ của lớp cha ĐẦU TIÊN
        super().__init__(data_results_list=data_results_list, cache_dir=cache_dir)

        # BƯỚC 4.2: Định nghĩa self.config (BẮT BUỘC)
        self.config = {
            "description": "Phân tích xu hướng dựa trên đường trung bình động.",
            "calculation_logic": "trend_ema_v1", # Tên logic (tham khảo)
            "parameters": {
                # Các tham số CÓ THỂ tối ưu (vì là số)
                "ema_short_period": 12,         # int
                "ema_long_period": 26,          # int
                "signal_period": 9,             # int
                "trend_threshold": 0.5,         # float
                "positive_trend_bonus": 15.0,   # float
                "negative_trend_penalty": -10.0, # float

                # Tham số KHÔNG tối ưu được (vì là string)
                "calculation_mode": "simple"
            }
        }

        # BƯỚC 4.3: Khởi tạo thuộc tính khác (nếu cần)
        self.ema_cache = {}

        # BƯỚC 4.4: Ghi log (khuyến nghị)
        self._log('debug', f"{self.__class__.__name__} initialized successfully.")
```


<br>
**Bước 5: Triển Khai Phương Thức predict (Cốt Lõi)**
Đây là phương thức **bắt buộc** phải có và là nơi chứa logic dự đoán chính của bạn.

1. **Signature:** Phương thức phải có tên là predict và nhận các tham số: self, date\_to\_predict (kiểu datetime.date), và historical\_results (kiểu list). Nó phải trả về một dict.
2. **Khởi Tạo Scores:** Bắt đầu bằng việc tạo một dictionary scores với tất cả các số từ "00" đến "99" và điểm số ban đầu (thường là 0.0).

    ```
    scores = {f'{i:02d}': 0.0 for i in range(100)}
    ```

<br>
    <br>
3. **Truy Cập Tham Số:** Lấy các tham số từ self.config['parameters'] một cách an toàn bằng params.get('parameter\_name', default\_value).

    ```
    params = self.config.get('parameters', {})
    short_period = params.get('ema_short_period', 12)
    long_period = params.get('ema_long_period', 26)
    threshold = params.get('trend_threshold', 0.5)
    bonus = params.get('positive_trend_bonus', 15.0)
    # ... lấy các tham số khác
    ```

<br>
    <br>
4. **Viết Logic Tính Toán:** Sử dụng date\_to\_predict, historical\_results, và các params để thực hiện các phép tính của bạn.
5. **Cập Nhật Scores:** Dựa trên kết quả tính toán, cập nhật giá trị điểm số (score) cho các số tương ứng trong dictionary scores. Điểm số này thường là delta (thay đổi so với điểm gốc 100.0 mà main.py sử dụng khi kết hợp).
6. **Logging:** Sử dụng self.\_log để ghi lại các bước quan trọng, cảnh báo, hoặc lỗi.
7. **Trả Về Scores:** Kết thúc phương thức bằng lệnh return scores. Nếu có lỗi nghiêm trọng không thể phục hồi, hãy ghi log lỗi và return {} (dictionary rỗng).

```
def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
        # BƯỚC 5.2: Khởi tạo scores
        scores = {f'{i:02d}': 0.0 for i in range(100)}
        self._log('debug', f"Running {self.__class__.__name__} predict for {date_to_predict}")

        # BƯỚC 5.3: Lấy tham số
        params = self.config.get('parameters', {})
        short_period = params.get('ema_short_period', 12)
        # ... lấy các tham số khác

        if not historical_results:
            self._log('warning', "No historical data available for prediction.")
            return scores # Trả về điểm 0 nếu không có lịch sử

        try:
            # BƯỚC 5.4: Logic tính toán
            # Ví dụ: Lấy N ngày gần nhất, tính toán EMA, xác định xu hướng...
            recent_data = historical_results[-short_period:] # Lấy N ngày cuối
            # ... thực hiện tính toán phức tạp ...
            calculated_trend_strength = 0.8 # Giả sử tính được

            # BƯỚC 5.5: Cập nhật scores dựa trên logic
            if calculated_trend_strength > threshold:
                # Cộng điểm cho một số nhóm số nếu xu hướng dương
                for num_str in ['01', '05', '10', '15']:
                    if num_str in scores: # Kiểm tra key tồn tại
                        scores[num_str] += bonus
                self._log('debug', f"Positive trend detected ({calculated_trend_strength:.2f}), applying bonus.")
            # ... các logic cập nhật khác ...

        except Exception as e:
            # BƯỚC 5.6: Ghi log lỗi
            self._log('error', f"Error during prediction logic for {date_to_predict}: {e}", exc_info=True)
            # BƯỚC 5.7: Trả về dict rỗng khi có lỗi
            return {}

        self._log('info', f"Prediction completed for {date_to_predict}.")
        # BƯỚC 5.7: Trả về scores
        return scores
```


<br>
**Bước 6 (Tùy Chọn): Ghi Đè extract\_numbers\_from\_dict**
Nếu phương thức extract\_numbers\_from\_dict mặc định trong BaseAlgorithm không phù hợp với cách bạn muốn trích xuất số từ dữ liệu kết quả thô, bạn có thể định nghĩa lại phương thức này trong class của mình. Signature phải giống hệt: extract\_numbers\_from\_dict(self, result\_dict: dict) -> set.
**Bước 7 (Khuyến Nghị): Thêm Khối Test if \_\_name\_\_ == "\_\_main\_\_":**
Thêm một khối ở cuối file để bạn có thể chạy và kiểm thử thuật toán này một cách độc lập mà không cần chạy toàn bộ main.py.

```
# ... (code class của bạn ở trên) ...

# BƯỚC 7: Khối test (khuyến nghị)
if __name__ == "__main__":
    # Thiết lập logging cơ bản cho test độc lập
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Tạo dữ liệu mẫu (hoặc đọc từ file test)
    sample_history = [
        {'date': datetime.date(2023, 10, 24), 'result': {'dac_biet': '12345', 'nhat': '67890', 'bay': ['10', '25']}},
        {'date': datetime.date(2023, 10, 25), 'result': {'dac_biet': '98765', 'nhat': '43210', 'bay': ['05', '88']}},
    ]
    predict_for = datetime.date(2023, 10, 26)

    # Khởi tạo và chạy thuật toán
    print("Testing TrendFollowingAlgorithm...")
    algo_instance = TrendFollowingAlgorithm(data_results_list=sample_history)

    # Thay đổi tham số để test (tùy chọn)
    # algo_instance.config['parameters']['ema_short_period'] = 5
    # algo_instance.config['parameters']['threshold_value'] = 0.9

    print(f"Using parameters: {algo_instance.get_config()['parameters']}")

    predicted_scores = algo_instance.predict(predict_for, sample_history)

    print(f"\nPrediction for {predict_for}:")
    if predicted_scores:
        # In top 10 kết quả
        top_10 = sorted(predicted_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        print("Top 10 Predictions:")
        for num, score in top_10:
            print(f"  Number {num}: Score {score:.2f}")
    else:
        print("Prediction failed or returned empty.")
```


<br> <br>
**Tóm Tắt Các Phần Bắt Buộc:**

<br>

1. **File .py** trong thư mục algorithms/.
2. **Class kế thừa** từ algorithms.base.BaseAlgorithm.
3. **Phương thức \_\_init\_\_:**
    * Gọi super().\_\_init\_\_(...) đầu tiên.
    * Định nghĩa self.config (là dict) với key "parameters" (là dict).
4. **Phương thức predict:**
    * Signature: predict(self, date\_to\_predict, historical\_results).
    * Trả về: dict với key "00"-"99" và value là điểm số int/float.

Khi bạn hoàn thành các bước trên và lưu file, main.py sẽ có thể tải và sử dụng thuật toán của bạn khi khởi động hoặc khi nhấn "Tải lại thuật toán".
