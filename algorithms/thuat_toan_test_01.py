# -*- coding: utf-8 -*-
from algorithms.base import BaseAlgorithm
import datetime
import logging
from collections import Counter

class DaysSinceLastAppearanceAlgorithm(BaseAlgorithm):
    """
    Thuật toán 1: Cộng điểm dựa trên số ngày một con số chưa xuất hiện,
    với các mốc thưởng và điểm cộng dồn.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {
            "description": "Cộng điểm dựa trên số ngày chưa xuất hiện, mốc thưởng, và thưởng ngày cuối.",
            "calculation_logic": "days_since_last_appearance_v1",
            "parameters": {
                "base_increment_per_day": 0.1,  # Điểm cộng cho mỗi ngày chưa xuất hiện
                "milestone_bonus": 0.1,         # Điểm thưởng tại mỗi mốc
                "milestones": [3, 7, 10, 15],   # Các mốc ngày thưởng (danh sách)
                "last_day_multiplier": 0.05,    # Điểm cộng thêm cho mỗi lần xuất hiện vào ngày gần nhất
                "progressive_start_day": 15,    # Ngày bắt đầu cộng dồn điểm tăng dần
                "progressive_increment": 0.1     # Điểm cộng thêm mỗi ngày sau mốc progressive_start_day
            }
        }
        self._log('debug', f"{self.__class__.__name__} initialized.")

    def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
        """Tính điểm dựa trên số ngày chưa xuất hiện."""
        self._log('debug', f"Starting prediction for: {date_to_predict}")
        scores = {f'{i:02d}': 0.0 for i in range(100)}

        if not historical_results:
            self._log('warning', "No historical data provided.")
            return scores

        # Lấy tham số
        params = self.config.get('parameters', {})
        try:
            base_inc = float(params.get('base_increment_per_day', 0.1))
            milestone_bonus = float(params.get('milestone_bonus', 0.1))
            milestones = [int(m) for m in params.get('milestones', [3, 7, 10, 15])]
            last_day_mult = float(params.get('last_day_multiplier', 0.05))
            prog_start_day = int(params.get('progressive_start_day', 15))
            prog_inc = float(params.get('progressive_increment', 0.1))
        except (ValueError, TypeError) as e:
            self._log('error', f"Invalid parameters in config: {e}. Using defaults.")
            # Sử dụng giá trị mặc định nếu có lỗi
            base_inc = 0.1
            milestone_bonus = 0.1
            milestones = [3, 7, 10, 15]
            last_day_mult = 0.05
            prog_start_day = 15
            prog_inc = 0.1

        # Lọc và sắp xếp lịch sử (chỉ cần làm một lần)
        history = [r for r in historical_results if isinstance(r.get('date'), datetime.date) and r['date'] < date_to_predict]
        if not history:
            self._log('warning', f"No historical data before {date_to_predict}.")
            return scores
        history.sort(key=lambda x: x['date'], reverse=True) # Sắp xếp giảm dần theo ngày (mới nhất trước)

        # Tính toán số ngày chưa xuất hiện cho mỗi số
        days_since_appearance = {}
        for num in range(100):
            found = False
            for i, day_data in enumerate(history):
                # Sử dụng extract_numbers_from_dict của base class
                numbers_in_day = self.extract_numbers_from_dict(day_data.get('result', {}))
                if num in numbers_in_day:
                    days_since_appearance[num] = i # i là số ngày kể từ ngày gần nhất (0 = ngày hôm qua)
                    found = True
                    break
            if not found:
                # Nếu không tìm thấy trong toàn bộ lịch sử đã lọc
                days_since_appearance[num] = len(history)

        # Tính điểm cho từng số
        for num in range(100):
            num_str = f'{num:02d}'
            days_absent = days_since_appearance[num]

            # 1. Điểm cơ bản theo ngày vắng mặt
            current_score = days_absent * base_inc

            # 2. Thưởng tại các mốc
            for milestone in sorted(milestones): # Đảm bảo mốc được sắp xếp
                if days_absent >= milestone:
                    current_score += milestone_bonus

            # 3. Thưởng cộng dồn từ mốc progressive_start_day
            if days_absent >= prog_start_day:
                # Số ngày vượt mốc (tính cả ngày mốc)
                days_past_progressive_start = days_absent - prog_start_day + 1
                # Tính tổng điểm cộng dồn (công thức tổng cấp số cộng)
                # Bonus ngày prog_start_day = 0*prog_inc
                # Bonus ngày prog_start_day+1 = 1*prog_inc
                # ...
                # Bonus ngày days_absent = (days_absent - prog_start_day) * prog_inc
                # Tổng = prog_inc * [0 + 1 + ... + (days_absent - prog_start_day)]
                # Tổng = prog_inc * n * (n+1) / 2  với n = days_absent - prog_start_day
                n = days_absent - prog_start_day
                progressive_bonus_total = prog_inc * n * (n + 1) / 2
                current_score += progressive_bonus_total
                # # Cách tính khác: cộng dồn từng ngày
                # progressive_bonus = 0.0
                # for d in range(prog_start_day, days_absent + 1):
                #     # Điểm cộng thêm tại ngày d so với ngày d-1
                #     additional_bonus_this_day = (d - prog_start_day) * prog_inc
                #     progressive_bonus += additional_bonus_this_day
                # current_score += progressive_bonus


            scores[num_str] = current_score # Gán điểm vắng mặt/thưởng mốc/cộng dồn

        # 4. Cộng điểm nếu xuất hiện nhiều lần vào ngày gần nhất (history[0])
        if history: # Chỉ thực hiện nếu có lịch sử
            last_day_data = history[0]
            # Sử dụng extract_numbers_from_dict của base class
            last_day_numbers = self.extract_numbers_from_dict(last_day_data.get('result', {}))
            # Đếm số lần xuất hiện của mỗi số trong ngày cuối
            last_day_counts = Counter(num for num in last_day_numbers if 0 <= num <= 99)

            for num, count in last_day_counts.items():
                if count > 0:
                    num_str = f'{num:02d}'
                    scores[num_str] += count * last_day_mult

        self._log('info', f"DaysSinceLastAppearance prediction completed for {date_to_predict}.")
        return scores

# Kiểm tra thử (cần file sample_data.json phù hợp)
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.DEBUG)
    algo = DaysSinceLastAppearanceAlgorithm()

    # Giả sử có file sample_data.json
    try:
        with open('sample_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Tạo file sample_data.json mẫu...")
        data = [{'date': (datetime.date.today() - datetime.timedelta(days=i)).isoformat(), 'result': {'special': f'{10+i:02d}', 'prize7_1': f'{20+i:02d}', 'prize7_2': f'{10+i:02d}' if i%2==0 else f'{30+i:02d}'}} for i in range(1, 30)]
        with open('sample_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    processed_data = []
    for item in data:
        try:
            # Chuyển đổi 'date' thành đối tượng date
            item['date'] = datetime.datetime.strptime(item['date'].split('T')[0], "%Y-%m-%d").date()
            # Đảm bảo 'result' là một dict
            if 'result' not in item or not isinstance(item['result'], dict):
                 # Cố gắng tạo 'result' từ các key khác nếu thiếu
                 item['result'] = {k: v for k, v in item.items() if k != 'date'}
            processed_data.append(item)
        except (ValueError, KeyError, TypeError) as e:
            print(f"Skipping invalid data item: {item}, error: {e}")


    predict_for_date = datetime.date.today()
    scores_result = algo.predict(predict_for_date, processed_data)
    top_10 = sorted(scores_result.items(), key=lambda x: x[1], reverse=True)[:10]
    print(f"\nPrediction for {predict_for_date}:")
    print("Top 10 highest scores:")
    for num, score in top_10:
        print(f"  Number {num}: {score:.3f}")

    lowest_10 = sorted(scores_result.items(), key=lambda x: x[1])[:10]
    print("\nTop 10 lowest scores:")
    for num, score in lowest_10:
        print(f"  Number {num}: {score:.3f}")