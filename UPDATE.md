# Update list


### 01/12/2025

**Update ver 5.3.1**

Tối ưu lại thuật toán và fix số lượng file data khi sync

### 19/11/2025

**Update ver 5.3**

Update lại code để fix lỗi api Gemini sau khi Google update lại Studio
Thêm tab Kết quả xổ số để người dùng có thể xem trực quan hơn bảng kết quả

<br>

### 18/05/2025

**Update ver 5.2**

Fix 1 số bug tiềm tàng, sửa lỗi trùng lặp code
Sửa lại giao diện, gộp các phần trùng lặp, làm mới tab thuật toán.
Chuyển tab tạo thuật toán bằng Gemini vô tab Thuật toán.
Thêm thanh trạng thái check server data và server update online.
Tuỳ chỉnh lại tab Update!

<br>


### 18/05/2025

**Update ver 5.1**

Cập nhật phần tạo thuật toán online trực tiếp qua Gemini API 
Tuỳ chỉnh chế độ tối ưu thuật toán, thêm lựa chọn xoá thuật toán cũ khi tìm thấy thuật toán có thông số tốt hơn.
Di chuyển nút Mở thư mục tối ưu lên trên để mở rộng không gian cho nhật ký tối ưu.
Sửa lỗi tải thuật toán online trên server.


**Update ver 5.0**

Update lại phần tối ưu trong mục tối ưu thuật toán, giới hạn bộ số để tránh việc chiếm dụng nhiều ram </b>.<br> Tuỳ chỉnh lại giao diện cho đồng nhất.<br> cập nhật lại phần trạng thái chương trình dưới phần mềm.
Cập nhật phần tạo thuật toán online trực tiếp qua Gemini API 
Tuỳ chỉnh chế độ tối ưu thuật toán, thêm lựa chọn xoá thuật toán cũ khi tìm thấy thuật toán có thông số tốt hơn.
Di chuyển nút Mở thư mục tối ưu lên trên để mở rộng không gian cho nhật ký tối ưu.

<br>

### 17/05/2025

**Update ver 4.9**

Tối ưu việc sử dụng Ram và CPU

Tuỳ chỉnh tài nguyên CPU của chương trình

Bỏ hiển thị phần nhật ký hoạt động trong Cài đặt

Fix lỗi hiển thị giao diện update popup

<br>




### 16/05/2025

**Update ver 4.8**

Sửa lỗi update, xoá file tạm. 

Điều chỉnh khung hiển thị thuật toán trên máy trong tab Thuật toán

Định dạng lại nhật ký hoạt động trong Repo.

Fix nút copy lỗi.

Tối ưu thuật toán hoạt động. 

Di chuyển thanh Trạng thái hoạt động lên trên, hiển thị thông tin hệ thống xuống phía bên dưới...

<br>



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
