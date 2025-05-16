# Lottery-Predictor - Chương trình tính toán - dự đoán kết quả xổ số

Chương trình được phát triển trên code **Python**.

Lịch sử Update của chương trình: [Xem ở đây - Update](https://github.com/junlangzi/Lottery-Predictor/blob/main/UPDATE.md)  <br>
Cách để viết các thuật toán ở đây: [ALGORITHMS](https://github.com/junlangzi/Lottery-Predictor/blob/main/ALGORITHMS.md)  ***  (update 08/05/2025 - chạy file algorithms.py trong folder tools hoặc kích hoạt nhanh ở tab Công cụ để viết thuật toán)

Để chạy chương trình cần cài đặt Python và các gói bổ sung sau:

```
pip install PyQt5 requests astor psutil google-generativeai packaging
```

Tại thư mục chương trình, chạy file **main.py**

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

**Update:**

Thêm chương trình tối ưu chuỗi ngày: **date-optimize-v1.5.py**

Chương trình sẽ tối ưu thuật toán, sao cho ra chuỗi ngày có kết quả top 3 trùng với kết quả ngày hôm sau tuỳ theo cài đặt yêu cầu ( chạy gần tương tự như tối ưu thuật toán ) 
Data thuật toán sẽ được lưu ở trong thư mục Training

Thêm chương trình **algorithms.py** để hỗ trợ viết thuật toán bằng API GEMINI
Các bạn chỉ cần chạy chương trình, điền API GEMINI vào mục cài đặt, sau đó điền các thông tin cần thiết và mô tả chi tiết thuật toán mà mình muốn viết, code sẽ được tạo ra một cách vô cùng nhanh chóng.

<br><br>

**1 số hình ảnh của chương trình:**

**Màn hình chính**

![image](https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/demo1.png)

**Màn hình kết quả tính toán:**

![image](https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/demo2.png)
**Chỉnh sửa thông số thuật toán:**

![image](https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/demo3.png)
**Tối ưu thuật toán:**

![image](https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/demo4.png)
