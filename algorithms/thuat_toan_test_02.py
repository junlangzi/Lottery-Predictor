# -*- coding: utf-8 -*-
from algorithms.base import BaseAlgorithm
import datetime
import logging

class PrizePositionPenaltyAlgorithm(BaseAlgorithm):
    """
    Thuật toán 2: Trừ điểm dựa trên vị trí giải thưởng ngược lại
    của ngày gần nhất trong lịch sử.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {
            "description": "Trừ điểm dựa trên vị trí giải thưởng ngược của ngày gần nhất.",
            "calculation_logic": "prize_position_penalty_v1",
            "parameters": {
                "penalty_multiplier": 0.1
                # Không cần tham số vị trí đặc biệt vì mapping sẽ xử lý
            }
        }
        # Mapping key giải thưởng tới vị trí ngược (1 là cuối cùng, 27 là ĐB)
        # QUAN TRỌNG: Phải khớp chính xác với cấu trúc key trong file JSON data/result của bạn!
        self.prize_key_to_reverse_position = {
            # Giải 7 (4 giải) - Vị trí 1, 2, 3, 4
            'prize7_1': 4, 'prize7_2': 3, 'prize7_3': 2, 'prize7_4': 1,
            # Các biến thể tên khác cho giải 7
            'giai7_1': 4, 'giai7_2': 3, 'giai7_3': 2, 'giai7_4': 1,
            '7.1': 4, '7.2': 3, '7.3': 2, '7.4': 1,

            # Giải 6 (3 giải) - Vị trí 5, 6, 7
            'prize6_1': 7, 'prize6_2': 6, 'prize6_3': 5,
            'giai6_1': 7, 'giai6_2': 6, 'giai6_3': 5,
            '6.1': 7, '6.2': 6, '6.3': 5,

            # Giải 5 (6 giải) - Vị trí 8 .. 13
            'prize5_1': 13, 'prize5_2': 12, 'prize5_3': 11, 'prize5_4': 10, 'prize5_5': 9, 'prize5_6': 8,
            'giai5_1': 13, 'giai5_2': 12, 'giai5_3': 11, 'giai5_4': 10, 'giai5_5': 9, 'giai5_6': 8,
            '5.1': 13, '5.2': 12, '5.3': 11, '5.4': 10, '5.5': 9, '5.6': 8,

            # Giải 4 (4 giải) - Vị trí 14 .. 17
            'prize4_1': 17, 'prize4_2': 16, 'prize4_3': 15, 'prize4_4': 14,
            'giai4_1': 17, 'giai4_2': 16, 'giai4_3': 15, 'giai4_4': 14,
            '4.1': 17, '4.2': 16, '4.3': 15, '4.4': 14,

            # Giải 3 (6 giải) - Vị trí 18 .. 23
            'prize3_1': 23, 'prize3_2': 22, 'prize3_3': 21, 'prize3_4': 20, 'prize3_5': 19, 'prize3_6': 18,
            'giai3_1': 23, 'giai3_2': 22, 'giai3_3': 21, 'giai3_4': 20, 'giai3_5': 19, 'giai3_6': 18,
            '3.1': 23, '3.2': 22, '3.3': 21, '3.4': 20, '3.5': 19, '3.6': 18,

            # Giải 2 (2 giải) - Vị trí 24, 25
            'prize2_1': 25, 'prize2_2': 24,
            'giai2_1': 25, 'giai2_2': 24,
            '2.1': 25, '2.2': 24,

            # Giải 1 (1 giải) - Vị trí 26
            'prize1': 26, 'giai1': 26, '1': 26,

            # Giải Đặc biệt (1 giải) - Vị trí 27
            'special': 27, 'dac_biet': 27, '0': 27, 'DB': 27
        }
        self._log('debug', f"{self.__class__.__name__} initialized.")

    def _extract_number_from_value(self, value) -> int | None:
        """Helper to extract the last 2 digits as int, returns None if invalid."""
        if value is None: return None
        try:
            s_item = str(value).strip()
            num = -1
            if len(s_item) >= 2 and s_item[-2:].isdigit():
                num = int(s_item[-2:])
            elif len(s_item) == 1 and s_item.isdigit():
                num = int(s_item)

            if 0 <= num <= 99:
                return num
        except (ValueError, TypeError):
            pass
        return None

    def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
        """Trừ điểm dựa trên vị trí giải thưởng ngược của ngày gần nhất."""
        self._log('debug', f"Starting prediction for: {date_to_predict}")
        scores = {f'{i:02d}': 0.0 for i in range(100)}

        if not historical_results:
            self._log('warning', "No historical data provided.")
            return scores

        # Lấy tham số
        params = self.config.get('parameters', {})
        try:
            penalty_mult = float(params.get('penalty_multiplier', 0.1))
        except (ValueError, TypeError) as e:
            self._log('error', f"Invalid parameters in config: {e}. Using defaults.")
            penalty_mult = 0.1

        # Lọc và lấy ngày gần nhất
        history = [r for r in historical_results if isinstance(r.get('date'), datetime.date) and r['date'] < date_to_predict]
        if not history:
            self._log('warning', f"No historical data before {date_to_predict}.")
            return scores
        history.sort(key=lambda x: x['date'], reverse=True) # Sắp xếp giảm dần
        last_day_data = history[0]
        last_day_result = last_day_data.get('result')

        if not last_day_result or not isinstance(last_day_result, dict):
            self._log('warning', f"No valid result dictionary found for the last historical day: {last_day_data.get('date')}")
            return scores

        self._log('debug', f"Applying penalties based on results from: {last_day_data.get('date')}")

        # Lặp qua các giải thưởng trong kết quả ngày cuối
        keys_processed_count = 0
        for prize_key, prize_value in last_day_result.items():
            reverse_position = self.prize_key_to_reverse_position.get(str(prize_key).lower()) # Chuẩn hóa key về chữ thường

            if reverse_position is None:
                # self._log('debug', f"Skipping unknown prize key: '{prize_key}'")
                continue # Bỏ qua nếu key không có trong mapping

            keys_processed_count += 1
            penalty_base = penalty_mult * reverse_position

            # Xử lý giá trị giải thưởng (có thể là số, chuỗi, hoặc list)
            values_to_check = []
            if isinstance(prize_value, (list, tuple)):
                values_to_check.extend(prize_value)
            else:
                values_to_check.append(prize_value)

            for value in values_to_check:
                number = self._extract_number_from_value(value)
                if number is not None:
                    num_str = f'{number:02d}'
                    scores[num_str] -= penalty_base # Trừ điểm
                    # self._log('debug', f"Applied penalty {penalty_base:.2f} to {num_str} from prize {prize_key} (Pos {reverse_position})")

        if keys_processed_count == 0:
             self._log('warning', f"No prize keys from result dict matched the mapping for date {last_day_data.get('date')}. Check mapping vs data structure.")

        self._log('info', f"PrizePositionPenalty prediction completed for {date_to_predict}.")
        return scores

# Kiểm tra thử (cần file sample_data.json với cấu trúc giải thưởng chi tiết)
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.DEBUG)
    algo = PrizePositionPenaltyAlgorithm()

    # Giả sử có file sample_data.json với cấu trúc giải chuẩn
    try:
        # Tạo sample data nếu không có
        if not Path('sample_data_detailed.json').exists():
             print("Tạo sample_data_detailed.json...")
             sample_detailed = []
             today = datetime.date.today()
             for i in range(1, 5):
                 day = today - datetime.timedelta(days=i)
                 res = {
                     'special': f'{10000+i}', 'prize1': f'{20000+i}',
                     'prize2_1': f'{30000+i}', 'prize2_2': f'{31000+i}',
                     'prize3_1': f'{40000+i}', 'prize3_2': f'{41000+i}', 'prize3_3': f'{42000+i}', 'prize3_4': f'{43000+i}', 'prize3_5': f'{44000+i}', 'prize3_6': f'{45000+i}',
                     'prize4_1': f'{5000+i}', 'prize4_2': f'{5100+i}', 'prize4_3': f'{5200+i}', 'prize4_4': f'{5300+i}',
                     'prize5_1': f'{6000+i}', 'prize5_2': f'{6100+i}', 'prize5_3': f'{6200+i}', 'prize5_4': f'{6300+i}', 'prize5_5': f'{6400+i}', 'prize5_6': f'{6500+i}',
                     'prize6_1': f'{700+i}', 'prize6_2': f'{710+i}', 'prize6_3': f'{720+i}',
                     'prize7_1': f'{i*10+1:02d}', 'prize7_2': f'{i*10+2:02d}', 'prize7_3': f'{i*10+3:02d}', 'prize7_4': f'{i*10+4:02d}'
                 }
                 # Tạo trùng lặp cố ý
                 if i % 2 == 0: res['prize7_1'] = res['prize7_2']

                 sample_detailed.append({'date': day.isoformat(), 'result': res})
             with open('sample_data_detailed.json', 'w', encoding='utf-8') as f: json.dump(sample_detailed, f, indent=2)


        with open('sample_data_detailed.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file sample_data_detailed.json.")
        data = []
    except json.JSONDecodeError:
        print("Lỗi: File sample_data_detailed.json không hợp lệ.")
        data = []

    processed_data = []
    for item in data:
        try:
            item['date'] = datetime.datetime.strptime(item['date'].split('T')[0], "%Y-%m-%d").date()
            if 'result' not in item or not isinstance(item['result'], dict):
                 item['result'] = {k: v for k, v in item.items() if k != 'date'}
            processed_data.append(item)
        except (ValueError, KeyError, TypeError) as e:
            print(f"Skipping invalid data item: {item}, error: {e}")

    predict_for_date = datetime.date.today()
    scores_result = algo.predict(predict_for_date, processed_data)

    # Lọc ra những số bị trừ điểm
    penalized_scores = {k: v for k, v in scores_result.items() if v < 0}
    sorted_penalized = sorted(penalized_scores.items(), key=lambda x: x[1]) # Sắp xếp theo điểm phạt (ít âm nhất trước)

    print(f"\nPrediction for {predict_for_date}:")
    if sorted_penalized:
        print("Numbers with penalties (lowest penalty first):")
        for num, score in sorted_penalized[:15]: # Hiển thị 15 số bị phạt ít nhất
            print(f"  Number {num}: {score:.3f}")
    else:
        print("No penalties applied (check history or mapping).")