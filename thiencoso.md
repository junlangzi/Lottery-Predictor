# Thiên Cơ Số – Hệ Thống Phân Tích & Thống Kê Xổ Số Kiến Thiết Miền Bắc (XSMB)

Ứng dụng Android chuyên sâu phục vụ phân tích, thống kê và dự đoán kết quả **Xổ Số Kiến Thiết Miền Bắc (XSMB)**. Ứng dụng kết hợp nhiều thuật toán toán học, phân tích chuỗi thời gian, kiểm thử lịch sử (Backtesting) và mô phỏng chiến lược trên nền tảng **Android (Kotlin + Jetpack Compose)** theo kiến trúc chuẩn **MVVM**.

![Platform](https://img.shields.io/badge/Platform-Android-green?logo=android)
![Language](https://img.shields.io/badge/Language-Kotlin-7F52FF?logo=kotlin)
![UI](https://img.shields.io/badge/UI-Jetpack%20Compose-4285F4?logo=jetpackcompose)
![Architecture](https://img.shields.io/badge/Architecture-MVVM-orange)
![Min SDK](https://img.shields.io/badge/Min%20SDK-26+-blue)

---

## 📖 Tổng Quan Ứng Dụng

**Thiên Cơ Số** được thiết kế như một trung tâm phân tích dữ liệu xổ số toàn diện, xử lý khối dữ liệu lịch sử hơn **7.500 kỳ mở thưởng XSMB** (từ năm 2005 đến hiện tại). 

Chương trình cho phép:
1. **Tính điểm toán học & Xếp hạng 100 con số (00–99)** thông qua hệ thống kết hợp đa thuật toán (Multi-Algorithm Fusion Engine).
2. **Kiểm thử chiến lược (Backtest)** trên dữ liệu lịch sử thực tế nhằm đo lường tỷ lệ trúng và độ ổn định của thuật toán theo thời gian.
3. **Thống kê chuyên sâu**: Lô gan, tần suất xuất hiện, nhịp lặp, ma trận lô rơi 10x10, thống kê đầu - đuôi.
4. **Kho thuật toán cộng đồng**: Cho phép tải về, chia sẻ và đồng bộ các công thức thuật toán tùy biến thông qua kết nối đám mây.
5. **Giả lập chơi thử (Paper Trading)**: Kiểm tra hiệu quả quản lý vốn và chiến lược cược mà không có rủi ro tài chính.

---

## 📸 Giao Diện Ứng Dụng (Demo Screenshots)

| Màn Hình | Chức Năng Chính |
|---|---|
| **Dự Đoán** | Bảng điểm 100 con số (00–99) + TOP 3 Golden Picks |
| **Thuật Toán** | Bật/tắt, tinh chỉnh trọng số & Kiểm thử Backtest |
| **Xem KQXS** | Tra cứu 27 giải + Thống kê tần suất / lô rơi / lô gan |
| **Chơi Thử** | Giả lập cược Lô/Đề/Xiên & Quản lý vốn ảo |
| **Cài Đặt** | Đồng bộ dữ liệu KQXS + Hướng dẫn chi tiết |

<p align="center">
  <img src="https://raw.githubusercontent.com/junlangzi/Thien-co-so/refs/heads/main/demo/1.jpg" alt="Màn hình chính Dự Đoán" width="18%"/> 
  <img src="https://raw.githubusercontent.com/junlangzi/Thien-co-so/refs/heads/main/demo/2.jpg" alt="Màn hình Thuật Toán" width="18%"/> 
  <img src="https://raw.githubusercontent.com/junlangzi/Thien-co-so/refs/heads/main/demo/3.jpg" alt="Màn hình KQXS" width="18%"/> 
  <img src="https://raw.githubusercontent.com/junlangzi/Thien-co-so/refs/heads/main/demo/4.jpg" alt="Màn hình Chơi Thử" width="18%"/> 
  <img src="https://raw.githubusercontent.com/junlangzi/Thien-co-so/refs/heads/main/demo/5.jpg" alt="Màn hình Cài Đặt" width="18%"/>
</p>

---

### 1. Động Cơ Dự Đoán & Kết Hợp Trọng Số (Prediction Engine)

Động cơ dự đoán hoạt động dựa trên nguyên lý **tính điểm tích lũy và điều chỉnh delta (Delta Score Balancing)**:

- **Điểm Gốc (Base Score)**: Mọi con số từ `00` đến `99` đều bắt đầu với mức điểm chuẩn là **100.0 điểm**.
- **Điều Chỉnh Delta**: Khi chạy hệ thống dự đoán cho một ngày cụ thể ($T$), ứng dụng sẽ truy xuất toàn bộ dữ liệu lịch sử **trước ngày $T$** (từ $T-1$ trở về quá khứ). Mỗi thuật toán đang bật sẽ tính toán một giá trị điểm thưởng/phạt ($\Delta S_i$) cho từng con số.
- **Tổng Hợp Trọng Số (Weighted Fusion)**:
  $$S_{final}(n) = S_{base} + \sum_{i=1}^{K} \left( w_i \times \Delta S_i(n) \right)$$
  *Trong đó:*
  - $S_{final}(n)$: Điểm số cuối cùng của con số $n \in [00, 99]$.
  - $w_i$: Trọng số do người dùng cấu hình cho thuật toán thứ $i$ (dải điều chỉnh từ $0.1\times$ đến $3.0\times$).
  - $\Delta S_i(n)$: Mức chênh lệch điểm số do thuật toán $i$ tính ra.
  - $K$: Số lượng thuật toán đang được kích hoạt.

- **Bảng Xếp Hạng & Phân Loại**:
  - Hệ thống sắp xếp 100 con số theo thứ tự điểm $S_{final}$ giảm dần.
  - **Top 3 Golden Picks**: 3 con số có điểm số cao nhất được gắn nhãn nổi bật làm bộ số chủ lực.
  - Phân nhóm bộ số theo thứ tự ưu tiên: Top 5, Top 10, Top 15, Top 20 và các nhóm vị trí chẵn/lẻ.

---

### 2. Chi Tiết Các Thuật Toán Demo Có Sẵn trong App

Ứng dụng được tích hợp sẵn **3 thuật toán Demo lõi** chạy trực tiếp trên thiết bị:

#### 🔹 Thuật Toán 01: [DEMO] Điểm Xuất Hiện & Tần Suất (V13)
- **Tần suất ngắn hạn & dài hạn**: Phân tích mật độ xuất hiện của con số trong các mốc chu kỳ 45 ngày và 180 ngày gần nhất.
- **Thưởng chu kỳ 7 ngày / 30 ngày**: Số có nhịp xuất hiện đều đặn trong tuần hoặc tháng được bổ sung điểm ưu tiên.
- **Bonus Láng Giềng Giải Đặc Biệt**: Các con số kề cận với 2 số cuối giải Đặc biệt của kỳ trước (ví dụ: ĐB về `56` thì `55` và `57` được cộng điểm láng giềng).
- **Phạt Lặp Top 3**: Trừ điểm đối với các con số đã liên tục lọt vào Top 3 dự đoán của những ngày ngay trước đó nhằm tránh ảo điểm.

#### 🔹 Thuật Toán 02: [DEMO] Số Ngày Chưa Về & Mốc Thưởng
- **Phân tích nhịp vắng mặt (Lô gan)**: Tính toán số ngày liên tiếp con số chưa xuất hiện trong bảng KQXS.
- **Mốc thưởng tiến trình**: Thưởng điểm bậc thang khi con số đạt đến các mốc thời gian vắng mặt lý tưởng (3 ngày, 7 ngày, 10 ngày, 15 ngày).
- **Trừ điểm siêu gan**: Tự động áp dụng hệ số điều chỉnh khi số ngày vắng mặt vượt mức rủi ro cho phép.

#### 🔹 Thuật Toán 03: [DEMO] Tối Ưu Toàn Diện (Final V2)
- **Mô hình đa chiều tích hợp**: Kết hợp phân tích trọng số tần suất 30 / 90 / 180 ngày với hệ số suy giảm thời gian (ST Decay).
- **Bản đồ nhiệt & Ngày trong tuần (Heatmap & Weekday)**: Phân tích quy luật xuất hiện của từng cặp số theo các thứ trong tuần.
- **Cơ chế chống dính (Antistick)**: Điều chỉnh cân bằng điểm số tránh việc ưu tiên lệch một nhóm số cố định.

---

### 3. Động Cơ Kiểm Thử Lịch Sử (Backtesting Engine)

Hệ thống Backtest cho phép kiểm chứng độ tin cậy của bộ tham số thuật toán trước khi áp dụng thực tế:

- **Phạm vi kiểm thử**: Tùy chọn 7 ngày, 14 ngày, 30 ngày, 60 ngày hoặc 90 ngày quá khứ.
- **Quy trình giả lập nối tiếp**:
  1. Tại mỗi ngày $t$ trong quá khứ, ứng dụng xóa toàn bộ dữ liệu từ ngày $t$ đến hiện tại khỏi bộ nhớ tạm.
  2. Chạy đợt tính toán dự đoán dựa trên dữ liệu từ $t-1$ trở về trước.
  3. Lấy Top N con số dự đoán tại ngày $t$ và so sánh trực tiếp với kết quả KQXS thực tế mở thưởng của ngày $t$.
  4. Đếm số lượng nháy trúng (1 nháy, 2 nháy, 3 nháy...) và kiểm tra trúng Giải Đặc biệt.
- **Chỉ số đầu ra**:
  - **Tỷ lệ trúng (Hit Rate %)**: Tỷ lệ số ngày có ít nhất 1 con số trong Top N trúng thưởng.
  - **Hiệu suất nháy (Total Hits)**: Tổng số lượt trúng gom lại trên toàn chu kỳ.
  - **Tỷ lệ sinh lời giả lập (ROI %)**: Tính toán lãi/lỗ giả định dựa trên tỷ lệ cược chuẩn.

---

### 4. Kho Thuật Toán Cộng Đồng (Community Algorithm Hub)

- **Kiến trúc kết nối**: Sử dụng Cloudflare Worker kết nối với cơ sở dữ liệu Cloudflare D1 & R2 Storage.
- **Tải & Chia sẻ**:
  - Người dùng có thể tải lên các cấu hình thuật toán đắc ý kèm mô tả và tên gọi.
  - Người dùng khác có thể duyệt danh sách, lọc theo lượt tải, đánh giá sao hoặc thời gian khởi tạo.
- **Đồng bộ an toàn**: Mã gói thuật toán được đóng gói dạng tệp cấu trúc JSON, xác thực định dạng trước khi nạp vào hệ thống cục bộ.

---

### 5. Giả Lập Đặt Cược (Trial Play Simulator)

Chức năng giả lập giao dịch giúp người dùng thử nghiệm chiến lược quản lý vốn:

- **Tài khoản vốn ảo**: Khởi tạo số dư ban đầu (ví dụ: 10.000.000đ).
- **Hỗ trợ đa dạng hình thức**:
  - **Lô Tô**: Tính theo điểm (1 điểm = 23.000đ, trúng 1 nháy = 80.000đ).
  - **Đề (Giải Đặc Biệt)**: Tỷ lệ 1:80.
  - **Lô Xiên**: Xiên 2 (1:10), Xiên 3 (1:40), Xiên 4 (1:100).
  - **Đầu / Đuôi**: Cược theo nhóm đầu/đuôi số.
- **Quyết toán tự động**: Tự động đối soát với kết quả XSMB sau giờ quay thưởng và cập nhật biến động số dư, vẽ biểu đồ tăng trưởng tài sản.

---

### 6. Thống Kê & Tra Cứu KQXS Chuyên Sâu

- **Bảng KQXS 27 Giải**: Hiển thị chi tiết truyền thống từ Giải Đặc biệt đến Giải Bảy.
- **Ma Trận Lô Rơi / Kẹp 10x10**: Trực quan hóa vị trí các cặp số xuất hiện trong ngày dưới dạng lưới 100 ô.
- **Phân Tích Đầu - Đuôi**: Thống kê số lượng lô tô về theo từng đầu số (0–9) và đít số (0–9), hỗ trợ phát hiện đầu/đít câm.
- **Bảng Thống Kê Lô Gan**: Danh sách Top 10 con số lâu về nhất kèm số ngày câm thực tế.

---

## 🛠️ Công Nghệ & Kiến Trúc Mã Nguồn

| Thành Phần | Công Nghệ Sử Dụng |
|---|---|
| **Ngôn Ngữ** | Kotlin 2.x |
| **Giao Diện UI** | Jetpack Compose + Material Design 3 |
| **Kiến Trúc** | MVVM (Model - View - ViewModel) + Clean Layering |
| **Bất Đồng Bộ** | Kotlin Coroutines & Flow |
| **Lưu Trữ Cục Bộ** | Android SharedPreferences + JSON Local Assets |
| **Lưu Trữ Đám Mây** | Cloudflare Worker + Cloudflare D1 Database / R2 |
| **Nền Tảng Hỗ Trợ** | Android SDK 26 (Android 8.0) đến SDK 36 (Android 15+) |

---

## 📁 Cấu Trúc Dự Án

```
app/src/main/java/com/example/lotterypredictor/
├── algorithms/                    # Động cơ dự đoán & thuật toán
│   ├── BaseAlgorithm.kt           # Interface chuẩn cho thuật toán
│   ├── Algorithm1Appearance.kt    # Thuật toán 01 - Tần suất & Xuất hiện
│   ├── Algorithm2DaysSinceLast.kt # Thuật toán 02 - Lô gan & Mốc thưởng
│   ├── Algorithm3PrizePosition.kt # Thuật toán 03 - Phạt vị trí giải
│   ├── Algorithm4ThirtyDayFreq.kt # Thuật toán 04 - Tần suất 30 ngày
│   ├── DynamicPythonAlgorithm.kt  # Trình thực thi công thức động
│   ├── PredictionEngine.kt        # Động cơ tổng hợp điểm & xếp hạng
│   ├── AnalyticsEngine.kt         # Động cơ thống kê KQXS chuyên sâu
│   └── AlgorithmOptimizer.kt      # Động cơ Backtest & tối ưu tham số
├── data/                          # Lớp dữ liệu & Repository
│   ├── model/                     # Data classes (LotteryRecord, Algorithm, v.v.)
│   └── repository/                # Repository xử lý dữ liệu lịch sử & Cloud Worker
├── ui/                            # Lớp giao diện Jetpack Compose
│   ├── components/                # Các thành phần UI dùng chung & Dialogs
│   ├── screens/                   # 5 màn hình chính (Prediction, Algorithms, Results, TrialPlay, Settings)
│   └── theme/                     # Cấu hình màu sắc, Typography, Shape (M3)
└── MainActivity.kt                # Activity chính & Khởi chạy ứng dụng
```

---

## ⚖️ Tuyên Bố Miễn Trừ Trách Nhiệm & Pháp Lý

- **Mục đích sử dụng**: Ứng dụng **Thiên Cơ Số** được phát triển thuần túy cho mục đích **thống kê toán học, phân tích dữ liệu lịch sử và giải trí**.
- **Không đảm bảo kết quả**: Các con số dự đoán và bảng xếp hạng điểm là kết quả của các mô hình toán học thống kê quá quá khứ, **không đảm bảo chính xác 100%** cho các kỳ quay thưởng tương lai.
- **Trách nhiệm người dùng**: Ứng dụng nghiêm cấm các hành vi lợi dụng dữ liệu cho mục đích cờ bạc bất hợp pháp. Người dùng hoàn toàn tự chịu trách nhiệm đối với mọi quyết định cá nhân.
- **Nguồn dữ liệu**: Dữ liệu kết quả xổ số được tổng hợp tự động từ các nguồn công khai minh bạch.

---

*Thiên Cơ Số • Phân Tích Dữ Liệu Minh Bạch, Trực Quan & Hiệu Quả*
