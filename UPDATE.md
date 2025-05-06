# Update list


### 04/05/2025

**Update algorithms.py**

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
