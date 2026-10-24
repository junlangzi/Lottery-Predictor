# ⚠️ THÔNG BÁO QUAN TRỌNG: DỪNG CẬP NHẬT VÀ DỪNG DỰ ÁN (END-OF-LIFE - EOL)

> [!WARNING]
> ### THÔNG BÁO VỀ VIỆC DỪNG CẬP NHẬT VÀ XOÁ KHỎI DỰ ÁN
> **Chương trình sẽ dừng cập nhật và xoá khỏi dự án vào ngày 24/10/2026 bởi vì hành vi dự đoán xổ số là hành vi vi phạm pháp luật:**
>
> Theo **Nghị định 389/2026/NĐ-CP** của Chính phủ (có hiệu lực từ ngày 30/11/2026), hành vi cung cấp thông tin dự đoán trước kết quả xổ số sẽ bị xử phạt hành chính với các mức cụ thể như sau:
>
> **Mức phạt đối với hành vi dự đoán kết quả xổ số:**
> - **Đối với cá nhân:** Phạt tiền từ **80 triệu đồng** đến **100 triệu đồng**.
> - **Đối với tổ chức:** Phạt tiền từ **160 triệu đồng** đến **200 triệu đồng**.
>
> Toàn bộ mã nguồn và dữ liệu của dự án được lưu trữ chỉ nhằm mục đích nghiên cứu học thuật, tham khảo thuật toán tối ưu hóa di truyền (Genetic Algorithms) và xử lý dữ liệu thống kê khoa học. Người dùng tự chịu mọi trách nhiệm pháp lý nếu sử dụng phần mềm sai mục đích.

---

# Thiên Cơ Số ☯︎ - Hệ Thống Tính Toán & Phân Tích Kết Quả Xổ Số (KQXS)
**Phiên bản:** v6.2.0 - EOL (Ngày phát hành: 24/10/2026)  
**Phát triển bởi:** Thiên cơ số Studio  
**Môi trường:** Python 3.10+ | PyQt5 / PyQt6  

---

## 🌐 Hệ Sinh Thái Phần Mềm Thiên Cơ Số

Dự án **Thiên Cơ Số** được nghiên cứu và phát triển trên nhiều nền tảng nhằm phục vụ phân tích khoa học dữ liệu và mô phỏng số học:

1. 📱 **App Thiên Cơ Số (Android):**  
   Ứng dụng di động chuyên sâu phân tích, thống kê và mô phỏng chiến lược cho Xổ Số Kiến Thiết Miền Bắc (XSMB) viết bằng **Kotlin + Jetpack Compose** theo chuẩn kiến trúc MVVM.  
   👉 [Xem thông tin chi tiết App Android tại: thiencoso.md](https://github.com/junlangzi/Lottery-Predictor/blob/main/thiencoso.md)

2. 🖥️ **Thiên Cơ Số Studio PC Pro:**  
   Phiên bản máy trạm PC chuyên nghiệp tích hợp trí tuệ nhân tạo (AI Hybrid), động cơ di truyền Walk-Forward Validation (WF) đa nếp gấp và kho tham số AI Vault Store.  
   👉 [Xem thông tin chi tiết Studio PC Pro tại: thiencoso-studio.md](https://github.com/junlangzi/Lottery-Predictor/blob/main/thiencoso-studio.md)

3. 🔬 **Thiên Cơ Số - KQXS Research Lab (Thư mục này):**  
   Phần mềm phân tích dữ liệu, kiểm thử thuật toán và mô phỏng kết quả xổ số truyền thống và điện toán với giao diện trực quan PyQt.

---

## 📸 Hình Ảnh Giao Diện Chương Trình (Demo Screenshots)

### 1. Màn Hình Chính & Bảng Xếp Hạng Điểm Số Học
Bảng xếp hạng 100 con số từ `00` đến `99` được tính toán tự động dựa trên các thuật toán số học, tần suất chu kỳ và các bộ số ưu tiên (Top Golden Picks).
<p align="center">
  <img src="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/tcs1.png" alt="Màn hình chính Thiên Cơ Số - Bảng điểm dự đoán" width="95%"/>
</p>

---

### 2. Bảng Tra Cứu Kết Quả & Thống Kê Chuyên Sâu
Hiển thị đầy đủ 27 giải thưởng XSMB hoặc ma trận số Vietlott, đi kèm hệ thống phân tích nhịp lặp, tần suất xuất hiện, lô gan và ma trận rơi.
<p align="center">
  <img src="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/tcs2.png" alt="Bảng kết quả xổ số và thống kê tần suất" width="95%"/>
</p>

---

### 3. Tinh Chỉnh Thông Số & Tối Ưu Hóa Thuật Toán (Optimizer)
Cho phép người dùng tùy chỉnh tham số từng thuật toán, chạy tối ưu hóa tự động theo bước nhảy để tìm ra cấu hình trọng số có độ chính xác cao nhất.
<p align="center">
  <img src="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/tcs3.png" alt="Tinh chỉnh và tối ưu hóa thuật toán" width="95%"/>
</p>

---

### 4. Kiểm Thử Hiệu Suất Đa Khung Thời Gian (Backtest & Hit-Rate)
Đánh giá tỷ lệ trúng thưởng (Hit-Rate - HR) trên dữ liệu lịch sử thực tế, so sánh kết quả Top 3, Top 5, Top 10 với kết quả mở thưởng ngày hôm sau.
<p align="center">
  <img src="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/demo/tcs4.png" alt="Kiểm thử hiệu suất và đo lường tỷ lệ trúng thưởng" width="95%"/>
</p>

---

## 🎯 Các Tính Năng Nổi Bật

### 1. Đa Dạng Loại Hình Xổ Số
- **Xổ số Miền Bắc (XSMB):** Phân tích 27 giải, đầu đuôi 2 chữ số (00-99), gan cực đại, tần suất chu kỳ, bạc nhớ.
- **Vietlott Mega 6/45:** Ma trận 45 số (01-45), quay thưởng Thứ 4, Thứ 6, Chủ Nhật.
- **Vietlott Power 6/55:** Ma trận 55 số (01-55) + số đặc biệt Jackpot 2, quay Thứ 3, Thứ 5, Thứ 7.
- **Vietlott Lotto 5/35:** 5 số chính (01-35) + 1 số đặc biệt (01-12).
- **Vietlott Max 3D & Max 3D Pro:** Phân tích các bộ ba số từ 000-999.
- **Vietlott Keno:** Xổ số nhanh chu kỳ 5-10 phút.

### 2. Tối Ưu Tỷ Lệ Trúng (HR) Bám Sát Mốc Giải Thưởng Thấp Nhất
Hệ thống tính điểm được thiết kế bám sát cơ chế giải thưởng thực tế:
- **Mega 6/45 & Power 6/55:** Tối ưu sao cho Top 6 số điểm cao nhất phải có **tối thiểu 3 số trùng** với kết quả mở thưởng (mốc Giải Ba). Trùng 1 hoặc 2 số được tính là không trúng.
- **Lotto 5/35:** Tối ưu trúng thưởng ngay từ **1 số đặc biệt** (Giải Khuyến khích - 10.000đ, hòa vốn) hoặc **2 số chính** (Giải Năm - 30.000đ).
- **Điểm cộng tương quan cụm:** Các số trúng thưởng của ngày hôm sau nằm càng liền kề nhau trên bảng tính điểm của ngày hôm trước thì thuật toán càng được đánh giá cao.

### 3. Hỗ Trợ Tạo Thuật Toán Bằng AI (Gemini Studio)
Tích hợp tab **AI Gemini** cho phép người dùng nhập mô tả ý tưởng bằng ngôn ngữ tự nhiên tiếng Việt, hệ thống sẽ tự động sinh mã nguồn thuật toán Python hoàn chỉnh, tuân thủ lớp cơ sở `BaseAlgorithm`.

### 4. Đồng Bộ Dữ Liệu Tự Động Thông Minh (Smart Sync)
- Tự động lấy dữ liệu kỳ quay mới nhất từ nguồn chính thống.
- Kiểm tra tính toàn vẹn và loại bỏ kỳ quay trùng lặp.
- Đồng bộ sơ đồ kiến trúc tập tin tự động thông qua công cụ quản lý phiên bản `version.py`.

---

## 🛠️ Hướng Dẫn Cài Đặt & Sử Dụng

### Yêu Cầu Môi Trường
Cần cài đặt Python 3.10 trở lên và các thư viện phụ thuộc:
```bash
pip install PyQt5 requests astor psutil google-generativeai packaging pillow
```

### Khởi Chạy Ứng Dụng
1. Mở cửa sổ dòng lệnh tại thư mục `KQXS`:
   ```bash
   python main.py
   ```
2. Để đồng bộ hoặc quản lý số phiên bản hệ thống:
   ```bash
   python version.py
   ```

---

## ⚖️ Tuyên Bố Miễn Trừ Trách Nhiệm (Disclaimer)
- Phần mềm này được xây dựng độc quyền cho mục đích học thuật, nghiên cứu khoa học dữ liệu, lý thuyết xác suất thống kê và thuật toán tối ưu hoá số học.
- Chúng tôi **không khuyến khích, không hỗ trợ và không chịu trách nhiệm** cho bất kỳ hành vi cờ bạc, cá cược hoặc vi phạm pháp luật nào phát sinh từ việc sử dụng phần mềm.
- Dự án chính thức bước vào trạng thái **End-of-Life (EOL)** kể từ ngày 24/10/2026.
