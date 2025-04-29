# -*- coding: utf-8 -*-
from algorithms.base import BaseAlgorithm
import datetime
import logging
from collections import Counter, defaultdict

class ThirtyDayFrequencyPenaltyAlgorithm(BaseAlgorithm):
    """
    Thuật toán 3: Trừ điểm cho các số ít xuất hiện và cộng điểm
    cho các số chưa xuất hiện trong 30 ngày gần nhất.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {
            "description": "Trừ/cộng điểm dựa trên tần suất xuất hiện trong 30 ngày.",
            "calculation_logic": "thirty_day_frequency_penalty_v1",
            "parameters": {
                "history_days": 30,
                "min_appearance_penalty": -0.1, # Phạt cho nhóm ít xuất hiện nhất
                "penalty_increment": -0.1,      # Phạt tăng thêm cho nhóm ít tiếp theo
                "never_appeared_bonus": 0.5     # Thưởng cho số chưa từng xuất hiện
            }
        }
        self._log('debug', f"{self.__class__.__name__} initialized.")

    def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
        """Tính điểm dựa trên tần suất xuất hiện 30 ngày."""
        self._log('debug', f"Starting prediction for: {date_to_predict}")
        scores = {f'{i:02d}': 0.0 for i in range(100)}

        # Lấy tham số
        params = self.config.get('parameters', {})
        try:
            hist_days = int(params.get('history_days', 30))
            min_penalty = float(params.get('min_appearance_penalty', -0.1))
            penalty_inc = float(params.get('penalty_increment', -0.1))
            never_bonus = float(params.get('never_appeared_bonus', 0.5))
        except (ValueError, TypeError) as e:
            self._log('error', f"Invalid parameters in config: {e}. Using defaults.")
            hist_days = 30
            min_penalty = -0.1
            penalty_inc = -0.1
            never_bonus = 0.5

        # Lọc lịch sử cho 30 ngày
        start_date_limit = date_to_predict - datetime.timedelta(days=hist_days)
        history = [r for r in historical_results if isinstance(r.get('date'), datetime.date) and start_date_limit <= r['date'] < date_to_predict]

        if not history:
            self._log('warning', f"No historical data found within the last {hist_days} days before {date_to_predict}.")
            # Nếu không có history, tất cả các số đều chưa xuất hiện
            for num_str in scores.keys():
                scores[num_str] = never_bonus
            self._log('info', f"ThirtyDayFrequencyPenalty applying 'never_appeared_bonus' to all numbers due to lack of history.")
            return scores

        # Đếm tần suất xuất hiện
        number_counts = Counter()
        for day_data in history:
            # Sử dụng extract_numbers_from_dict của base class
            numbers_in_day = self.extract_numbers_from_dict(day_data.get('result', {}))
            number_counts.update(numbers_in_day) # Counter sẽ đếm số nguyên

        # Phân loại số đã xuất hiện và chưa xuất hiện
        all_possible_numbers = set(range(100))
        appeared_numbers_int = set(number_counts.keys())
        never_appeared_int = all_possible_numbers - appeared_numbers_int

        # Cộng điểm cho số chưa xuất hiện
        for num_int in never_appeared_int:
            num_str = f'{num_int:02d}'
            scores[num_str] += never_bonus
            # self._log('debug', f"Number {num_str} never appeared, bonus: {never_bonus}")

        # Phân nhóm số đã xuất hiện theo tần suất
        frequency_groups = defaultdict(list)
        for num_int, count in number_counts.items():
             if 0 <= num_int <= 99: # Đảm bảo chỉ xử lý số 00-99
                frequency_groups[count].append(num_int)

        # Sắp xếp các tần suất xuất hiện (từ thấp đến cao)
        sorted_frequencies = sorted(frequency_groups.keys())

        # Áp dụng điểm phạt tăng dần cho các nhóm tần suất thấp
        current_penalty = min_penalty
        if sorted_frequencies:
            self._log('debug', f"Applying penalties starting from {current_penalty} for {len(sorted_frequencies)} frequency groups.")
        for freq in sorted_frequencies:
            numbers_in_group = frequency_groups[freq]
            # self._log('debug', f"Applying penalty {current_penalty:.2f} to {len(numbers_in_group)} numbers with frequency {freq}")
            for num_int in numbers_in_group:
                num_str = f'{num_int:02d}'
                scores[num_str] += current_penalty

            # Giảm điểm phạt cho nhóm tần suất tiếp theo (penalty_inc thường là âm)
            current_penalty += penalty_inc

        self._log('info', f"ThirtyDayFrequencyPenalty prediction completed for {date_to_predict}.")
        return scores

# Kiểm tra thử (cần file sample_data.json phù hợp)
if __name__ == "__main__":
    import json
    from pathlib import Path
    logging.basicConfig(level=logging.DEBUG)
    algo = ThirtyDayFrequencyPenaltyAlgorithm()

    # Giả sử có file sample_data.json
    try:
         if not Path('sample_data.json').exists():
             print("Tạo file sample_data.json mẫu...")
             data = [{'date': (datetime.date.today() - datetime.timedelta(days=i)).isoformat(), 'result': {'special': f'{10+i:02d}', 'prize7_1': f'{20+i:02d}', 'prize7_2': f'{10+i:02d}' if i%5!=0 else f'{30+i:02d}'}} for i in range(1, 40)]
             with open('sample_data.json', 'w', encoding='utf-8') as f:
                 json.dump(data, f, indent=2)

         with open('sample_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file sample_data.json.")
        data = []
    except json.JSONDecodeError:
        print("Lỗi: File sample_data.json không hợp lệ.")
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

    # Lọc ra những số có điểm dương (chưa xuất hiện)
    positive_scores = {k: v for k, v in scores_result.items() if v > 0}
    sorted_positive = sorted(positive_scores.items(), key=lambda x: x[1], reverse=True)

    print(f"\nPrediction for {predict_for_date}:")
    if sorted_positive:
        print("Numbers with positive scores (likely never appeared):")
        for num, score in sorted_positive[:10]:
            print(f"  Number {num}: {score:.3f}")
    else:
        print("No numbers with positive scores found.")

    # Lọc ra những số bị trừ điểm
    penalized_scores = {k: v for k, v in scores_result.items() if v < 0}
    sorted_penalized = sorted(penalized_scores.items(), key=lambda x: x[1]) # Ít âm nhất trước

    if sorted_penalized:
        print("\nNumbers with penalties (lowest penalty first):")
        for num, score in sorted_penalized[:10]:
            print(f"  Number {num}: {score:.3f}")
    else:
        print("\nNo numbers with penalties found.")