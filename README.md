# Lottery-Predictor - Trình tính toán dự đoán xổ số

Chương trình được phát triển trên code **Python**.

Để chạy chương trình cần cài đặt Python và các gói bổ sung sau:

```
pip install PyQt5 requests astor
```


Tại thư mục chương trình, chạy file **app.py**

**Chương trình có các tính năng như sau:**

Dựa vào các thuật toán cung cấp trong thư mục algorithms, và file data kết quả xổ số xsmb-2-digits.json chương tình sẽ tính toán:

* Bảng xếp hạng các con số từ 00-99 theo số điểm từ thấp đến cao ( số điểm mặc định các con số ban đầu là 100, các số sẽ được trừ điểm, cộng điểm theo các thuật toán mà người dùng lựa chọn) - Chương trình sẽ sử dụng kết quả quay thưởng của ngày được chọn, và các kết quả trước đó để tính toán các con số ( và so sánh với bảng kết quả ngày hôm sau nếu đã có )
* Người dùng có thể kiểm tra độ chính xác của thuật toán trong các khoảng thời gian nhất định tại mục hiệu suất kết hợp. ( lấy top 3-5-10 số có điểm số cao nhất so sánh với kết quả quay thưởng ngày hôm sau )
* Tại tab tối ưu, người dùng có thể chỉnh sửa các thông số của từng thuật toán, hay tối ưu để thuật toán chính xác hơn.

**Tối ưu thuật toán:**

* Tại phần tối ưu thuật toán, người dùng có thể lựa chọn:
* Tối ưu 1 thuật toán trong 1 khoảng thời gian nhất định.
* Tôi ưu 1 thuật toán kết hợp với 1 hay nhiều thuật toán khác trong khoảng thời gian nhất định
* Tối ưu tiếp 1 thuật toán đang tối ưu dở lúc trước
* Tuỳ chỉnh thông số các bước nhảy theo từng chỉ số nhất định để tối ưu thuật toán ( Mặc định sẽ là auto tăng / giảm )
* Khi tối ưu thành công, lưu lại các thuật toán có các chỉ số chính xác cao hơn. (Lưu vào thư mục **optimize\\tên thuật toán\\success**)

(data xsmb-2-digits.json sử dụng của [Khiemdoan.](https://github.com/khiemdoan/vietnam-lottery-xsmb-analysis))

1 số hình ảnh của chương trình:

**Màn hình chính**

![image](https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/demo1.png)

**Màn hình kết quả tính toán:**

![image](https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/demo2.png)
**Chỉnh sửa thông số thuật toán:**

![image](https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/demo3.png)
**Tối ưu thuật toán:**

![image](https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/demo4.png)
Sơ lược về xây dựng thuật toán:

**Nguyên tắc chính để chương trình đọc được thuật toán:**

1. **Kế thừa BaseAlgorithm:** Lớp thuật toán của bạn phải kế thừa từ algorithms.base.BaseAlgorithm.
2. **File .py trong thư mục algorithms:** File chứa lớp thuật toán phải là file Python (.py) và nằm trong thư mục con algorithms. Tên file không được là \_\_init\_\_.py hay base.py.
3. **Phương thức \_\_init\_\_:**
    * Phải gọi super().\_\_init\_\_(\*args, \*\*kwargs) **ngay đầu tiên** để khởi tạo các thành phần cơ sở (như logger, data, cache).
    * Phải định nghĩa self.config là một dictionary chứa ít nhất:
        * "description" (str): Mô tả ngắn gọn thuật toán.
        * "parameters" (dict): Một dictionary chứa các tham số mà thuật toán sử dụng và giá trị mặc định của chúng. **Quan trọng:** Nếu muốn tham số có thể được tối ưu hóa trong tab "Tối ưu", giá trị mặc định của nó nên là kiểu int hoặc float.
4. **Phương thức predict:**
    * Phải triển khai phương thức predict(self, date\_to\_predict: datetime.date, historical\_results: list).
    * Phương thức này nhận ngày cần dự đoán và danh sách dữ liệu lịch sử trước ngày đó.
    * **Phải trả về** một dictionary có dạng {'00': score\_00, '01': score\_01, ..., '99': score\_99}. Các key là chuỗi số 2 chữ số, và value (score) là điểm số (thường là float) mà thuật toán gán cho số đó. Điểm số này thường là delta (thay đổi so với điểm cơ bản) và sẽ được main.py tổng hợp lại. Trả về {} nếu có lỗi.
5. **Encoding:** Nên có # -\*- coding: utf-8 -\*- ở đầu file.
6. **Logging:** Sử dụng self.\_log('debug', 'message'), self.\_log('info', 'message'), self.\_log('error', 'message') để ghi log. Logger này đã được cấu hình sẵn trong BaseAlgorithm.
7. **Helper:** Có thể sử dụng self.extract\_numbers\_from\_dict(result\_dict) để lấy tập hợp các số trúng thưởng từ kết quả của một ngày.

**Ví dụ: Thuật toán Trung Bình Xuất Hiện Đơn Giản (Simple Moving Average)**

```
# -*- coding: utf-8 -*-
from algorithms.base import BaseAlgorithm
import datetime
from collections import Counter
import logging # Có thể import nhưng nên dùng self._log

class SimpleMovingAverageAlgorithm(BaseAlgorithm):
    """
    Thuật toán tính điểm dựa trên trung bình số lần xuất hiện của một số
    trong N ngày lịch sử gần nhất. Số nào xuất hiện trung bình nhiều hơn
    sẽ có điểm cao hơn.
    """
    def __init__(self, *args, **kwargs):
        # BƯỚC 1: Gọi __init__ của lớp cha NGAY LẬP TỨC
        super().__init__(*args, **kwargs)

        # BƯỚC 2: Định nghĩa cấu hình self.config
        self.config = {
            "description": "Tính điểm dựa trên trung bình xuất hiện trong N ngày gần nhất.",
            "calculation_logic": "simple_moving_average_v1", # Tên logic để tham chiếu (tùy chọn)
            "parameters": {
                # Tham số có thể tối ưu (int/float)
                "window_days": 30,          # Số ngày lịch sử để xem xét (int)
                "base_score_multiplier": 10.0 # Hệ số nhân cho điểm trung bình (float)
                # Thêm các tham số khác nếu cần
            }
        }

        # BƯỚC 3: Ghi log khởi tạo (sau khi super init)
        self._log('debug', f"{self.__class__.__name__} initialized.")
        # Có thể thêm các khởi tạo khác cho thuật toán ở đây

    def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
        """
        Dự đoán điểm số dựa trên trung bình xuất hiện.
        """
        self._log('debug', f"SMA: Predicting for {date_to_predict}")
        # Khởi tạo điểm số mặc định (có thể là 0 hoặc điểm cơ sở khác)
        scores = {f'{i:02d}': 0.0 for i in range(100)}

        # 1. Lấy tham số từ config
        try:
            params = self.config.get('parameters', {})
            window_days = int(params.get('window_days', 30))
            multiplier = float(params.get('base_score_multiplier', 10.0))

            # Validate parameters (ví dụ: window_days phải > 0)
            if window_days <= 0:
                self._log('warning', f"SMA: window_days parameter ({window_days}) is not positive. Using default 30.")
                window_days = 30
        except (ValueError, TypeError) as e:
            self._log('error', f"SMA: Invalid parameters defined in config: {e}. Using defaults.")
            # Sử dụng giá trị mặc định an toàn nếu config lỗi
            window_days = 30
            multiplier = 10.0

        # 2. Lọc dữ liệu lịch sử liên quan
        if not historical_results:
            self._log('warning', "SMA: No historical data provided for prediction.")
            return scores # Trả về điểm 0 nếu không có lịch sử

        start_date_limit = date_to_predict - datetime.timedelta(days=window_days)
        # Lấy các kết quả có ngày >= start_date_limit VÀ < date_to_predict (đã được lọc sẵn bởi main.py)
        relevant_history = [r for r in historical_results if r.get('date') and r['date'] >= start_date_limit]

        if not relevant_history:
            self._log('info', f"SMA: No relevant history found within {window_days} days before {date_to_predict}.")
            return scores # Trả về điểm 0 nếu không có dữ liệu trong cửa sổ

        # 3. Đếm số lần xuất hiện
        appearance_counts = Counter()
        # Số ngày thực tế có dữ liệu trong cửa sổ, dùng để tính trung bình chính xác
        actual_days_in_window = len(relevant_history)
        self._log('debug', f"SMA: Using {actual_days_in_window} actual days in window (requested window: {window_days}).")

        for day_data in relevant_history:
            # Sử dụng helper từ BaseAlgorithm để lấy các số trúng thưởng
            numbers_in_day = self.extract_numbers_from_dict(day_data.get('result', {}))
            # Counter sẽ tự động đếm số lần xuất hiện của mỗi số
            appearance_counts.update(numbers_in_day)

        # 4. Tính điểm = (Trung bình xuất hiện) * multiplier
        if actual_days_in_window > 0:
            for num in range(100):
                count = appearance_counts.get(num, 0) # Lấy số lần đếm được, mặc định là 0
                average_appearance = count / actual_days_in_window
                # Gán điểm vào dictionary scores, key là chuỗi '00'..'99'
                scores[f'{num:02d}'] = round(average_appearance * multiplier, 3) # Làm tròn để tránh số quá lẻ
        else:
            # Trường hợp này không nên xảy ra nếu đã kiểm tra relevant_history ở trên
             self._log('warning', "SMA: actual_days_in_window is 0, returning zero scores.")
             return {f'{i:02d}': 0.0 for i in range(100)} # Trả về điểm 0

        self._log('debug', f"SMA: Prediction complete for {date_to_predict}. Example score '01': {scores.get('01', 'N/A')}")
        # Trả về dictionary điểm số
        return scores

# ---- Phần này tùy chọn: Dùng để test thuật toán độc lập ----
if __name__ == "__main__":
    # Thiết lập logging cơ bản để xem output khi chạy file này trực tiếp
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Tạo dữ liệu mẫu (hoặc đọc từ file JSON nếu bạn có)
    sample_history = [
        {'date': datetime.date(2023, 10, 20), 'result': {'special': 12345, 'prize7': ['01', 89]}},
        {'date': datetime.date(2023, 10, 21), 'result': {'special': 67801, 'prize1': 55}},
        {'date': datetime.date(2023, 10, 22), 'result': {'special': 99089, 'prize2': ['15', '01']}},
        # Thêm nhiều dữ liệu hơn để test window_days
    ]

    # Khởi tạo thuật toán
    algo = SimpleMovingAverageAlgorithm(data_results_list=sample_history) # Có thể truyền dữ liệu đầy đủ nếu muốn

    # Ngày muốn dự đoán
    predict_for_date = datetime.date(2023, 10, 23)

    # Lấy lịch sử trước ngày dự đoán
    history_for_predict = [r for r in sample_history if r['date'] < predict_for_date]

    # Gọi hàm predict
    predicted_scores = algo.predict(predict_for_date, history_for_predict)

    # In ra 10 số có điểm cao nhất
    print(f"\nPredicted scores for {predict_for_date}:")
    top_10 = sorted(predicted_scores.items(), key=lambda item: item[1], reverse=True)[:10]
    for num_str, score in top_10:
        print(f"  Number {num_str}: Score = {score:.3f}")

    # In cấu hình để kiểm tra
    print("\nAlgorithm Config:")
    import json
    print(json.dumps(algo.get_config(), indent=2))
```


<br>
<br>
<br>
<br>
