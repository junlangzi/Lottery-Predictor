# -*- coding: utf-8 -*-
from algorithms.base import BaseAlgorithm
import datetime
import logging
from collections import Counter

class HistoryAppearancePointAlgorithm(BaseAlgorithm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {
            "description": "Tính điểm tối ưu, giảm mạnh lặp lại liên tục của 61 trong Top 3.",
            "calculation_logic": "appearance_based_optimized_v13",
            "parameters": {
                "short_term_days": 14,
                "frequency_window_short": 45,
                "frequency_window_long": 180,
                "base_point_short": 3.5,      # Giảm từ 3.8 xuống 3.5
                "base_point_long": 0.3,       # Tăng từ 0.25 lên 0.3
                "frequency_weight_short": 0.5,
                "frequency_weight_long": 0.25,# Tăng từ 0.2 lên 0.25
                "neighbor_bonus": 1.2,        # Giảm từ 1.5 xuống 1.2
                "neighbor_range": 5,          # Giảm từ 7 xuống 5
                "increment": 0.005,
                "bonus_after_3_days": 0.07,
                "bonus_long_absence": 0.8,
                "deduction_if_appeared_last_day": -0.02,
                "repeat_penalty_top": -0.5,   # Tăng từ -0.3 lên -0.5
                "repeat_window": 7,
                "repeat_threshold_penalty": -2.0, # Tăng từ -1.0 lên -2.0
                "repeat_threshold": 2,        # Giảm từ 3 xuống 2
                "repeat_streak_penalty": -0.8,# Phạt thêm cho chuỗi lặp dài
                "bonus_freq_5": 0.25,
                "cycle_7_bonus": 0.2,
                "cycle_30_bonus": 0.3,
                "special_multiplier": 2.0,    # Giảm từ 2.5 xuống 2.0
                "special_freq_multiplier": 3.0
            }
        }
        self.previous_tops = []  # Lưu trữ Top 3 của các ngày trước
        self._log('debug', f"{self.__class__.__name__} initialized.")

    def extract_numbers_from_dict(self, result_dict: dict) -> set:
        """Trích xuất tất cả các số (int, 2 chữ số cuối) từ dict kết quả."""
        numbers = set()
        if not isinstance(result_dict, dict):
            return numbers
        for key, value in result_dict.items():
            if key != 'date':
                try:
                    num = int(str(value).strip()[-2:]) if len(str(value)) >= 2 else int(value)
                    numbers.add(num)
                except (ValueError, TypeError):
                    continue
        return numbers

    def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
        """Dự đoán điểm, giảm mạnh lặp lại liên tục của 61 trong Top 3."""
        self._log('debug', f"Starting prediction for: {date_to_predict}")
        scores = {f'{i:02d}': 0.0 for i in range(100)}

        if not historical_results:
            self._log('warning', "No historical data provided.")
            return scores

        # Lấy tham số
        params = self.config.get('parameters', {})
        short_term_days = params.get('short_term_days', 14)
        freq_window_short = params.get('frequency_window_short', 45)
        freq_window_long = params.get('frequency_window_long', 180)
        base_point_short = params.get('base_point_short', 3.5)
        base_point_long = params.get('base_point_long', 0.3)
        freq_weight_short = params.get('frequency_weight_short', 0.5)
        freq_weight_long = params.get('frequency_weight_long', 0.25)
        neighbor_bonus = params.get('neighbor_bonus', 1.2)
        neighbor_range = params.get('neighbor_range', 5)
        increment = params.get('increment', 0.005)
        bonus_after_3_days = params.get('bonus_after_3_days', 0.07)
        bonus_long_absence = params.get('bonus_long_absence', 0.8)
        deduction_last_day = params.get('deduction_if_appeared_last_day', -0.02)
        repeat_penalty_top = params.get('repeat_penalty_top', -0.5)
        repeat_window = params.get('repeat_window', 7)
        repeat_threshold_penalty = params.get('repeat_threshold_penalty', -2.0)
        repeat_threshold = params.get('repeat_threshold', 2)
        repeat_streak_penalty = params.get('repeat_streak_penalty', -0.8)
        bonus_freq_5 = params.get('bonus_freq_5', 0.25)
        cycle_7_bonus = params.get('cycle_7_bonus', 0.2)
        cycle_30_bonus = params.get('cycle_30_bonus', 0.3)
        special_multiplier = params.get('special_multiplier', 2.0)
        special_freq_multiplier = params.get('special_freq_multiplier', 3.0)

        # Lọc lịch sử
        history = [r for r in historical_results if isinstance(r.get('date'), datetime.date) and r['date'] < date_to_predict]
        if not history:
            self._log('warning', f"No historical data before {date_to_predict}.")
            return scores
        history.sort(key=lambda x: x['date'])

        # Điểm ngắn hạn
        short_term_start = date_to_predict - datetime.timedelta(days=short_term_days)
        short_term_history = [h for h in history if h['date'] >= short_term_start]
        for day_data in reversed(short_term_history):
            days_ago = (date_to_predict - day_data['date']).days
            result_dict = day_data.get('result', {})
            numbers = self.extract_numbers_from_dict(result_dict)
            special_num = int(str(result_dict.get('special', '00'))[-2:])
            for num in numbers:
                point = base_point_short * (1 - 0.08 * days_ago)
                if num == special_num:
                    point *= special_multiplier
                scores[f'{num:02d}'] += point

        # Tần suất ngắn hạn và dài hạn
        freq_short_start = date_to_predict - datetime.timedelta(days=freq_window_short)
        freq_long_start = date_to_predict - datetime.timedelta(days=freq_window_long)
        freq_short = Counter()
        freq_long = Counter()
        special_freq_short = Counter()
        for day_data in history:
            result_dict = day_data.get('result', {})
            numbers = self.extract_numbers_from_dict(result_dict)
            special_num = int(str(result_dict.get('special', '00'))[-2:])
            if day_data['date'] >= freq_short_start:
                freq_short.update(numbers)
                special_freq_short[special_num] += 1
            if day_data['date'] >= freq_long_start:
                freq_long.update(numbers)

        for num in range(100):
            num_str = f'{num:02d}'
            scores[num_str] += freq_weight_short * freq_short[num]
            scores[num_str] += freq_weight_long * freq_long[num]
            if freq_short[num] > 5:
                scores[num_str] += bonus_freq_5
            if special_freq_short[num] > 5:
                scores[num_str] += special_freq_multiplier

        # Thưởng láng giềng
        if history:
            last_day = history[-1].get('result', {})
            special_last = int(str(last_day.get('special', '00'))[-2:])
            for offset in range(-neighbor_range, neighbor_range + 1):
                if offset != 0:
                    neighbor = (special_last + offset) % 100
                    scores[f'{neighbor:02d}'] += neighbor_bonus * (1 - 0.1 * abs(offset))

        # Thưởng chu kỳ
        for day_data in history:
            days_ago = (date_to_predict - day_data['date']).days
            if days_ago % 7 == 0 and days_ago <= 28:
                numbers = self.extract_numbers_from_dict(day_data.get('result', {}))
                for num in numbers:
                    scores[f'{num:02d}'] += cycle_7_bonus
            if days_ago % 30 == 0 and days_ago <= 180:
                numbers = self.extract_numbers_from_dict(day_data.get('result', {}))
                for num in numbers:
                    scores[f'{num:02d}'] += cycle_30_bonus

        # Thưởng số vắng lâu
        for num in range(100):
            num_str = f'{num:02d}'
            days_since = 0
            for day_data in reversed(history):
                if num in self.extract_numbers_from_dict(day_data.get('result', {})):
                    break
                days_since += 1
            scores[num_str] += days_since * increment
            if days_since >= 3:
                scores[num_str] += bonus_after_3_days
            if days_since >= 15 and freq_long[num] > 10:
                scores[num_str] += bonus_long_absence

        # Phạt nếu xuất hiện ngày trước
        if history and (date_to_predict - history[-1]['date']).days == 1:
            last_numbers = self.extract_numbers_from_dict(history[-1].get('result', {}))
            for num in last_numbers:
                scores[f'{num:02d}'] += deduction_last_day

        # Phạt lặp lại trong Top 3 của các ngày trước
        repeat_counts = Counter()
        streak_counts = Counter()  # Đếm chuỗi lặp liên tục
        for i, prev_top in enumerate(reversed(self.previous_tops[-repeat_window:])):
            repeat_counts.update(prev_top)
            for num in prev_top:
                if i == 0 or (i > 0 and num not in self.previous_tops[-i-1]):
                    streak_counts[num] = 1
                else:
                    streak_counts[num] += 1

        for num in range(100):
            num_str = f'{num:02d}'
            repeat_count = repeat_counts.get(num, 0)
            streak_count = streak_counts.get(num, 0)
            if repeat_count > 0:
                scores[num_str] += repeat_penalty_top * repeat_count
                if repeat_count >= repeat_threshold:  # Phạt mạnh nếu lặp ≥2 ngày
                    scores[num_str] += repeat_threshold_penalty
                if streak_count > 1:  # Phạt thêm cho chuỗi lặp liên tục
                    scores[num_str] += repeat_streak_penalty * (streak_count - 1)

        # Cập nhật Top 3 cho lần dự đoán này
        top_3 = [num for num, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]]
        self.previous_tops.append(top_3)
        if len(self.previous_tops) > repeat_window:
            self.previous_tops.pop(0)

        self._log('info', f"Prediction completed for {date_to_predict}. Top 3: {sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]}")
        return scores

# Kiểm tra thử
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.DEBUG)
    algo = HistoryAppearancePointAlgorithm()

    with open('sample_data.json', 'r') as f:
        data = json.load(f)

    for item in data:
        item['date'] = datetime.datetime.strptime(item['date'], "%Y-%m-%dT%H:%M:%S.%f").date()
        item['result'] = {k: v for k, v in item.items() if k != 'date'}

    # Dự đoán liên tục 10 ngày
    for i in range(10):
        date = datetime.date(2025, 3, 22 + i)
        scores = algo.predict(date, data)
        top_3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"Date {date}: Top 3 = {top_3}")