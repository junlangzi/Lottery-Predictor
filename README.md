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

# Thiên Cơ Số ☯︎ - PC AI Genetic Studio Pro (v6.2.0 - EOL)
**Tác giả & Phát triển:** Thiên cơ số Studio  
**Phiên bản:** v6.2.0 - EOL (Ngày phát hành: 24/10/2026)  
**Nền tảng:** Python 3.10+ | PyQt5 / PyQt6  

---

## 📖 Giới Thiệu Chung

**Thiên Cơ Số ☯︎** là phần mềm máy tính chuyên dụng phân tích thống kê xác suất, tối ưu hóa thuật toán và mô phỏng số học xổ số truyền thống và điện toán. Phần mềm tích hợp công nghệ AI kết hợp giải thuật di truyền (Genetic Algorithm & AI Hybrid) để đánh giá hiệu suất (Hit-Rate - HR), phát hiện chu kỳ và mô phỏng quản lý vốn đầu tư.

---

## 🎯 Các Tính Năng Cốt Lõi

### 1. Hỗ Trợ Đầy Đủ Các Loại Hình Xổ Số
- **Xổ số Miền Bắc (XSMB):** Phân tích 27 giải quay, đầu đuôi 2 chữ số (00-99), gan cực đại, tần suất chu kỳ, bạc nhớ.
- **Vietlott Mega 6/45:** Ma trận 45 số (01-45), quay thưởng Thứ 4, Thứ 6, Chủ Nhật.
- **Vietlott Power 6/55:** Ma trận 55 số (01-55) + 1 số đặc biệt jackpot 2, quay Thứ 3, Thứ 5, Thứ 7.
- **Vietlott Lotto 5/35:** 5 số chính (01-35) + 1 số đặc biệt (01-12).
- **Vietlott Max 3D & Max 3D Pro:** Các bộ ba số từ 000-999 theo các giải thưởng đa dạng.
- **Vietlott Keno:** Xổ số nhanh chu kỳ 5-10 phút với ma trận 80 số.

### 2. Chuẩn Hóa Tối Ưu Hóa Theo Cơ Cấu Giải Thưởng Thấp Nhất
Hệ thống tính điểm và tối ưu hóa tỷ lệ trúng (Hit-Rate) được thiết kế bám sát cơ chế trúng thưởng thực tế từ mốc giải thấp nhất:
- **Mega 6/45:** Điểm Hit-Rate chỉ được tính khi Top 6 số dự đoán chứa **tối thiểu 3 số trùng** khớp với kết quả (mốc Giải Ba - 30.000đ).
- **Power 6/55:** Top 6 số phải chứa **tối thiểu 3 số trùng** với kết quả (mốc Giải Ba - 50.000đ).
- **Lotto 5/35:** Trúng chỉ cần **1 số đặc biệt** (Giải Khuyến khích - 10.000đ, hòa vốn) hoặc **2 số chính** (Giải Năm - 30.000đ).
- **Điểm cộng tương quan cụm:** Các bộ số trùng thưởng càng nằm liền kề nhau trong bảng xếp hạng điểm số thì thuật toán càng được đánh giá cao và tối ưu độ ổn định.

### 3. Bộ Thuật Toán Di Truyền (Genetic Optimization & Walk-Forward)
- Tối ưu hóa tham số đa điểm (Multi-point mutation & recombination).
- Đánh giá chéo đa nếp gấp Walk-Forward Validation (WF) chống hiện tượng Overfitting (học vẹt).
- Kiểm tra rò rỉ dữ liệu (Holdout & Data Leakage Prevention).
- Tích hợp mô hình ngôn ngữ lớn (Ollama / Gemini AI Studio) hỗ trợ phân tích và tự động sinh mã thuật toán mới.

### 4. Hệ Thống Đồng Bộ Dữ Liệu Thông Minh (Smart Sync)
- Tự động lấy dữ liệu kỳ quay mới nhất từ nguồn chính thống Vietlott và XSMB.
- Cơ chế Smart Sync: So khớp ngày gần nhất, tự động chuyển đổi crawl trực tiếp hoặc tải gói đồng bộ dự phòng.
- Tránh trùng lặp kỳ quay và kiểm tra tính toàn vẹn của dữ liệu tự động.

### 5. Quản Lý & Tự Động Đồng Bộ Phiên Bản (`version.py`)
- Công cụ GUI/CLI `version.py` độc lập: Tự động quét và đồng bộ số phiên bản, ngày cập nhật cho `main.py` và toàn bộ 21+ modules trong hệ thống.
- Khi khởi động, chương trình quét toàn bộ sơ đồ kiến trúc tập tin (Architecture Manifest) để đảm bảo không bị thiếu tập tin hoặc lệch phiên bản.

---

## 🛠️ Yêu Cầu Cài Đặt & Khởi Chạy

### 1. Cài đặt Python & Thư viện
Yêu cầu Python phiên bản 3.10 trở lên:
```bash
pip install PyQt5 PyQt6 requests astor psutil google-generativeai packaging pillow
```

### 2. Khởi chạy chương trình
- Chạy giao diện chính:
  ```bash
  python main.py
  ```
- Hoặc chạy giao diện phòng lab nghiên cứu KQXS:
  ```bash
  python KQXS/main.py
  ```
- Chạy công cụ đồng bộ phiên bản:
  ```bash
  python version.py
  ```
- Chạy kiểm thử tự động (Self-Test Suite):
  ```bash
  python main.py --self-test
  ```

---

## 📁 Cấu Trúc Dự Án

```
├── main.py                  # Entry Point chính khởi động ứng dụng
├── version.py               # Công cụ quản lý và đồng bộ phiên bản modules
├── logo.png                 # Logo biểu tượng Thái Cực (Yin-Yang) chuẩn
├── moduls/                  # Các module giao diện PyQt6, AI Vault, Genetic Engine
│   ├── main_window.py       # Cửa sổ làm việc chính Studio
│   ├── genetic_engine.py    # Nhân thuật toán di truyền Walk-Forward
│   ├── algorithm_compiler.py# Trình biên dịch thuật toán động
│   ├── ai_vault.py          # Kho lưu trữ thông số mô hình AI
│   └── ...
├── KQXS/                    # Module phòng Lab nghiên cứu tính toán XS
│   ├── main.py              # Ứng dụng phân tích dữ liệu KQXS PyQt5
│   ├── modules/             # Các worker, optimizer, tin tức, hỗ trợ Vietlott
│   ├── algorithms/          # Thư mục chứa các thuật toán số học
│   ├── config/              # Cấu hình hệ thống, logo, version marker
│   └── data/                # Dữ liệu kết quả quay thưởng lịch sử
└── data/                    # Dữ liệu kết quả quay thưởng xổ số (JSON/JSONL)
```

---

## ⚖️ Tuyên Bố Miễn Trừ Trách Nhiệm (Disclaimer)
1. Phần mềm được viết hoàn toàn cho mục đích học thuật, nghiên cứu khoa học dữ liệu, lý thuyết xác suất thống kê và thuật toán tối ưu hoá di truyền.
2. Tác giả và đội ngũ phát triển **không khuyến khích, không hỗ trợ và không chịu trách nhiệm** cho bất kỳ hành vi cờ bạc, cá cược hoặc vi phạm pháp luật nào phát sinh từ việc sử dụng phần mềm.
3. Dự án chính thức bước vào trạng thái **End-of-Life (EOL)** kể từ ngày 24/10/2026.
