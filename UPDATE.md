# Update list

### 15/05/2025

**Update ver 4.5**

Bổ sung phần Nhật ký hoạt động trong mục cài đặt, thêm chế độ tự động Sync file kết quả xổ số khi chương trình khởi động. Cập nhật thêm chế độ update khi có phiên bản mới

<br>

### 13/05/2025

**Update ver 4.4**


Update thêm thông tin điểm và lịch sử xuất hiện từng con số trong bảng dự đoán kết quả hàng ngày

<br>



### 09/05/2025

**Update ver 4.3**


Update thêm tab thuật toán, có thể check tải về các thuật toán online, đồng thời xoá, update các thuật toán cũ trên máy

<br><br>


### 08/05/2025

**Update ver 4.2**


Thêm tab công cụ để bổ sung các tính năng mới, chuyển các chương trình tạo thuật toán, tối ưu chuỗi ngày vào trong folder tools


<br><br>


### 04/05/2025

**Update  [algorithms.py](https://github.com/junlangzi/Lottery-Predictor/blob/main/algorithms.py "algorithms.py")**

Chương trình sử dụng API GEMINI hỗ trợ viết thuật toán bằng cách mô tả, chỉ cần mô tả cách thức hoạt động của thuật toán, chương trình sẽ trả về toàn bộ code thuật toán để sử dụng một cách nhanh chóng

<br><br>


### 03/05/2025

**Update V4.1**

Thêm mục chế độ tối ưu vào trong mục tối ưu thuật toán. Sẽ có 2 lựa chọn

* Tối ưu tự động ( auto ) tự động tối ưu theo các chỉ số có sẵn.
* Tạo bộ tham số. Khi người dùng chọn mục này, mỗi tham số sẽ tạo thêm bộ số tương ứng, máy sẽ kết hợp toàn bộ các thông số mới thành 1 tổ hợp rất nhiều các thuật toán mới với toàn bộ các thông số đó, rồi sau đó chạy lần lượt từng thuật toán

Số lượng có thể vô cùng lớn ( chú ý )

**Cập nhật [date-optimize-v1.5.py](https://github.com/junlangzi/Lottery-Predictor/blob/main/date-optimize-v1.5.py "date-optimize-v1.5.py")**

Chương trình sẽ tối ưu thuật toán, sao cho ra chuỗi ngày có kết quả top 3 trùng với kết quả ngày hôm sau tuỳ theo cài đặt yêu cầu ( chạy gần tương tự như tối ưu thuật toán ) Data thuật toán sẽ được lưu ở trong thư mục **Training**

**Lưu ý⚠️ Chế độ tạo bộ tham số có thể tạo cực kỳ nhiều bộ số và toàn bộ thông tin sẽ lưu hết ở trong RAM, bởi vậy những thuật toán có nhiều tham số, khi chọn mốc 10 tham số có thể lên đến trăm triệu đến cả tỉ bộ tham số có thể load đến hàng chục GB ram, nên chú ý trước khi lựa chọn chế độ này**
