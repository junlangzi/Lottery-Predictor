# -*- coding: utf-8 -*-
"""
modules/json_bundle.py
Định nghĩa lớp JsonBundleAlgorithm và các hàm hỗ trợ để nạp và thực thi các thuật toán
được lưu dưới dạng bundle JSON (tổ hợp đa thuật toán con đã qua huấn luyện / tối ưu).
"""

import copy
import datetime
import json
import logging
import math
from collections import Counter, defaultdict
from pathlib import Path
from algorithms.base import BaseAlgorithm

bundle_logger = logging.getLogger("modules.json_bundle")


def is_json_bundle_file(file_path: Path) -> bool:
    """
    Kiểm tra xem một file có phải là file thuật toán JSON Bundle hợp lệ hay không.
    """
    try:
        p = Path(file_path)
        if not p.is_file() or p.suffix.lower() != '.json':
            return False
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False

        has_bundle = 'bundle_id' in data or 'bundle_name' in data
        has_formulas = 'formulas' in data and isinstance(data['formulas'], list) and len(data['formulas']) > 0
        has_active = 'active_algorithms' in data and isinstance(data['active_algorithms'], list) and len(data['active_algorithms']) > 0
        return (has_bundle and (has_formulas or has_active)) or has_formulas or has_active
    except Exception:
        return False


def compute_ranks(scores: dict[str, float]) -> dict[str, float]:
    """
    Chuẩn hóa điểm số theo thứ hạng (Rank Normalization).
    Trả về điểm số trong khoảng [1.0, 100.0] tương ứng với thứ hạng từ thấp đến cao.
    """
    sorted_items = sorted(scores.items(), key=lambda x: x[1])
    n = len(sorted_items)
    if n == 0:
        return {}
    ranks = {}
    i = 0
    while i < n:
        j = i
        while j < n - 1 and math.isclose(sorted_items[j + 1][1], sorted_items[i][1], rel_tol=1e-9, abs_tol=1e-9):
            j += 1
        avg_rank = (i + j + 2) / 2.0
        norm_rank = (avg_rank / float(n)) * 100.0
        for k in range(i, j + 1):
            ranks[sorted_items[k][0]] = norm_rank
        i = j + 1
    return ranks


def evaluate_appearance_formula(
    params: dict,
    date_to_predict: datetime.date,
    filtered_history: list,
    precomputed_context: dict = None
) -> dict[str, float]:
    """
    Tính toán điểm số cho 100 số (00..99) dựa trên bộ tham số tối ưu của công thức con
    (logic appearance_based_optimized_v13 / multi-feature lottery scoring).
    """
    scores = {f"{i:02d}": 0.0 for i in range(100)}
    if not filtered_history:
        return scores

    # 1. Trích xuất các tham số chính
    window_days = float(params.get("window_days", 60.0))
    decay = float(params.get("decay", params.get("recency_decay_rate", 0.95)))
    half_life = params.get("lag_half_life") or params.get("recency_halflife")
    half_life = float(half_life) if half_life is not None and float(half_life) > 0 else None

    exp_recency = float(params.get("exp_recency", 1.0))
    recency_mix = params.get("recency_mix")
    recency_mix = float(recency_mix) if recency_mix is not None else None

    special_boost = float(params.get("special_boost", 1.0))
    all_prize_boost = float(params.get("all_prize_boost", 1.0))

    gap_floor = float(params.get("gap_floor", 0.0))
    gap_cap = float(params.get("gap_cap", 100.0))
    absence_gain = float(params.get("absence_gain", 0.0))
    absence_power = float(params.get("absence_power", 1.0))
    absence_factor = float(params.get("absence_factor", 1.0))
    cold_penalty = float(params.get("cold_penalty", 0.0))
    hot_boost = float(params.get("hot_boost", 0.0))
    streak_break = float(params.get("streak_break", 0.0))

    modulo = params.get("modulo") or params.get("modulo_divisor")
    modulo = float(modulo) if modulo is not None and float(modulo) > 0 else None
    modulo_gain = float(params.get("modulo_gain", params.get("modulo_weight", 0.0)))

    phase_period = params.get("phase_period")
    phase_period = float(phase_period) if phase_period is not None and float(phase_period) > 0 else None
    phase_gain = float(params.get("phase_gain", 0.0))

    neighbor_gain = float(params.get("neighbor_gain", 0.0))
    digit_gain = float(params.get("digit_gain", 0.0))
    pair_cooccur_w = float(params.get("pair_cooccur_w", 0.0))

    poisson_gain = float(params.get("poisson_gain", 0.0))
    poisson_smoothing = float(params.get("poisson_smoothing_factor", 0.1))

    markov_gain = float(params.get("markov_gain", 0.0))
    scale = float(params.get("scale", 1.0))
    global_bias = float(params.get("global_bias", 0.0))
    reg_lambda = float(params.get("regularization_lambda", 0.0))

    # AI synthetic math parameters
    glorp = float(params.get("glorp", 0.0))
    vorl = float(params.get("vorl", 0.0))
    frib = float(params.get("frib", 0.0))
    lupa = float(params.get("lupa", 0.0))
    quizz = float(params.get("quizz", 0.0))
    tym = float(params.get("tym", 0.0))
    xente = float(params.get("xente", 0.0))
    zork = float(params.get("zork", 0.0))

    ai_weight_4 = float(params.get("ai_weight_4", 0.0))
    sigma = float(params.get("sigma", 5.0))
    tail_index = float(params.get("tail_index", 1.5))
    entropy_base = float(params.get("entropy_base", 2.0))

    # 2. Sử dụng hoặc tạo context lịch sử
    if precomputed_context is None:
        draw_entries = []
        last_seen = {}
        appearance_counts_window = Counter()
        total_prizes_window = 0

        for r in filtered_history:
            d = r['date']
            days_ago = (date_to_predict - d).days
            if days_ago < 1:
                continue

            r_dict = r.get('result', {}) if isinstance(r.get('result'), dict) else {k: v for k, v in r.items() if k != 'date'}
            # Trích xuất số giải đặc biệt
            sp_raw = r_dict.get('special') or r_dict.get('prize_special') or r_dict.get('gdb')
            sp_num = None
            if sp_raw is not None:
                try:
                    s_str = str(sp_raw).strip()
                    sp_num = int(s_str[-2:]) if len(s_str) >= 2 and s_str[-2:].isdigit() else (int(s_str) if s_str.isdigit() else None)
                except (ValueError, TypeError):
                    sp_num = None

            # Trích xuất toàn bộ số giải
            nums = []
            keys_to_ignore = {'date', '_id', 'source', 'day_of_week', 'sign', 'created_at', 'updated_at', 'province_name', 'province_id'}
            for k, val in r_dict.items():
                if k in keys_to_ignore:
                    continue
                v_list = val if isinstance(val, (list, tuple)) else [val]
                for item in v_list:
                    if item is None:
                        continue
                    try:
                        s_str = str(item).strip()
                        n_val = int(s_str[-2:]) if len(s_str) >= 2 and s_str[-2:].isdigit() else (int(s_str) if s_str.isdigit() else -1)
                        if 0 <= n_val <= 99:
                            nums.append(n_val)
                    except (ValueError, TypeError):
                        pass

            num_set = set(nums)
            for n_val in num_set:
                if n_val not in last_seen:
                    last_seen[n_val] = days_ago

            draw_entries.append((days_ago, sp_num, nums, num_set))

        last_draw = draw_entries[0] if draw_entries else None
        context = {
            'draw_entries': draw_entries,
            'last_seen': last_seen,
            'last_draw': last_draw
        }
    else:
        context = precomputed_context

    draw_entries = context['draw_entries']
    last_seen = context['last_seen']
    last_draw = context['last_draw']

    last_special = last_draw[1] if last_draw else None
    last_numbers_set = last_draw[3] if last_draw else set()

    # 3. Tính điểm theo từng số từ 00 đến 99
    recency_scores = [0.0] * 100
    absence_scores = [0.0] * 100
    window_counts = [0] * 100
    total_window_appearances = 0

    # Duyệt qua các kỳ quay trong cửa sổ window_days
    for days_ago, sp_num, nums_list, nums_set in draw_entries:
        if days_ago > window_days:
            continue

        if half_life is not None:
            decay_factor = math.exp(-days_ago * math.log(2.0) / half_life)
        else:
            decay_factor = decay ** min(days_ago, 100.0)

        for n_val in nums_set:
            is_special = (sp_num is not None and n_val == sp_num)
            weight = special_boost * decay_factor if is_special else all_prize_boost * decay_factor
            recency_scores[n_val] += weight
            window_counts[n_val] += 1
            total_window_appearances += 1

    # Tính điểm Absence, Modulo, Phase, Neighbor, Digit, Poisson, AI Math
    lambda_poisson = total_window_appearances / 100.0 if total_window_appearances > 0 else 0.27 * window_days

    for num in range(100):
        # A. Điểm recency
        r_score = recency_scores[num]
        if exp_recency != 1.0 and r_score > 0:
            r_score = r_score ** exp_recency

        # B. Điểm absence (gan)
        gap = float(last_seen.get(num, window_days + 10.0))
        eff_gap = max(0.0, min(gap, gap_cap) - gap_floor)
        a_score = (eff_gap ** absence_power) * absence_gain * absence_factor

        if cold_penalty > 0 and gap > 15.0:
            a_score -= cold_penalty * (gap - 15.0)

        if hot_boost > 0 and gap <= 3.0:
            a_score += hot_boost * (4.0 - gap)

        # C. Kết hợp Recency & Absence
        if recency_mix is not None:
            combined = recency_mix * r_score + (1.0 - recency_mix) * a_score
        else:
            combined = r_score + a_score

        # D. Modulo Harmonic
        if modulo is not None and modulo_gain > 0:
            mod_val = (num % modulo) / modulo
            combined += math.cos(2.0 * math.pi * mod_val) * modulo_gain
            if last_special is not None:
                mod_diff = ((num - last_special) % modulo) / modulo
                combined += math.cos(2.0 * math.pi * mod_diff) * (modulo_gain * 0.5)

        # E. Phase Periodic
        if phase_period is not None and phase_gain > 0:
            phase_val = num / phase_period
            combined += math.cos(2.0 * math.pi * phase_val) * phase_gain

        # F. Neighbor & Digit Sharing với GĐB kỳ trước
        if last_special is not None:
            if neighbor_gain > 0:
                diff = abs(num - last_special)
                dist = min(diff, 100 - diff)
                if dist <= 3:
                    combined += neighbor_gain * (1.0 - 0.25 * dist)

            if digit_gain > 0:
                head_match = 1.0 if (num // 10 == last_special // 10) else 0.0
                tail_match = 1.0 if (num % 10 == last_special % 10) else 0.0
                combined += digit_gain * (head_match + tail_match) * 0.5

        # G. Co-occurrence với các số kỳ trước
        if pair_cooccur_w > 0 and last_numbers_set:
            if num in last_numbers_set:
                combined += pair_cooccur_w * 0.5

        # H. Poisson Deviation
        if poisson_gain > 0:
            k_val = float(window_counts[num])
            denom = math.sqrt(lambda_poisson + poisson_smoothing + 1e-6)
            combined += poisson_gain * ((k_val - lambda_poisson) / denom)

        # I. AI Math Synthetics
        if glorp != 0.0 or vorl != 0.0:
            synth = (glorp * math.sin(num * frib + lupa) + vorl * math.cos(num * quizz + tym)) / 100.0
            synth += zork * (num % 10) * xente * 0.1
            combined += synth

        if ai_weight_4 > 0:
            diff_50 = (num - 50.0)
            tail = ai_weight_4 * math.exp(-(diff_50 * diff_50) / (2.0 * (sigma * sigma + 1e-6)))
            k_term = (window_counts[num] + 1.0) / (entropy_base + 1e-6)
            combined += tail * (k_term ** min(tail_index - 1.0, 2.0))

        # J. Bias & Scale
        combined += global_bias
        if reg_lambda > 0:
            combined *= (1.0 - reg_lambda)

        combined *= scale
        scores[f"{num:02d}"] = float(combined)

    return scores


class JsonBundleAlgorithm(BaseAlgorithm):
    """
    Thuật toán đa mô hình đóng gói trong file JSON (JSON Algorithm Bundle).
    Được tối ưu hóa bằng AI / Genetic Algorithm / Walk-forward ensemble.
    Tương thích hoàn toàn với BaseAlgorithm của Lottery Predictor.
    """

    def __init__(self, json_path=None, data_results_list=None, cache_dir=None):
        super().__init__(data_results_list=data_results_list, cache_dir=cache_dir)
        self.json_path = Path(json_path) if json_path else None
        self.bundle_data = {}
        self.bundle_id = ""
        self.bundle_name = "JSON Algorithm Bundle"
        self.active_formulas = []
        self.weights = {}
        self.normalization_mode = "rank"
        self.top_k = 3

        if self.json_path and self.json_path.exists():
            self.load_from_json(self.json_path)

    def load_from_json(self, json_path: Path):
        """Đọc và khởi tạo cấu hình từ file JSON bundle."""
        self.json_path = Path(json_path)
        with open(self.json_path, 'r', encoding='utf-8') as f:
            self.bundle_data = json.load(f)

        self.bundle_id = self.bundle_data.get("bundle_id", self.json_path.stem)
        self.bundle_name = self.bundle_data.get("bundle_name", self.bundle_id)

        # Lấy danh sách thuật toán con
        raw_formulas = self.bundle_data.get("active_algorithms") or self.bundle_data.get("formulas") or []
        self.active_formulas = raw_formulas

        # Trích xuất trọng số tốt nhất
        best_ind = self.bundle_data.get("best_individual", {})
        self.weights = copy.deepcopy(best_ind.get("weights", {}))
        best_params = best_ind.get("params", {})

        # Cập nhật parameters cho từng công thức nếu có trong best_individual.params
        for formula in self.active_formulas:
            f_id = formula.get("id")
            if f_id and f_id in best_params:
                formula["parameters"].update(best_params[f_id])
            if f_id and f_id in self.weights:
                formula["weight"] = self.weights[f_id]

        config_data = self.bundle_data.get("config", {})
        self.normalization_mode = config_data.get("normalization_mode", "rank")
        self.top_k = config_data.get("top_k", 3)

        desc = self.bundle_data.get("ai_advisor_summary")
        if not desc:
            hr = self.bundle_data.get("train_hit_rate", 0.0) * 100.0
            desc = f"Tổ hợp {len(self.active_formulas)} thuật toán AI tối ưu (HR: {hr:.1f}%)"

        self.config = {
            "description": desc,
            "calculation_logic": "json_bundle_ensemble",
            "bundle_id": self.bundle_id,
            "bundle_name": self.bundle_name,
            "normalization_mode": self.normalization_mode,
            "top_k": self.top_k,
            "parameters": {
                "active_algorithms_count": len(self.active_formulas),
                "normalization_mode": self.normalization_mode,
                "weights": self.weights
            }
        }
        self._log('info', f"Loaded JSON Bundle '{self.bundle_name}' with {len(self.active_formulas)} active formulas.")

    def get_config(self) -> dict:
        return self.config

    def predict(self, date_to_predict: datetime.date, historical_results: list) -> dict:
        """
        Dự đoán kết quả cho ngày `date_to_predict`.
        Tổng hợp điểm của tất cả các thuật toán con trong bundle theo trọng số và chuẩn hóa.
        """
        self._log('debug', f"JsonBundleAlgorithm '{self.bundle_name}' predicting for {date_to_predict}")
        scores = {f"{i:02d}": 0.0 for i in range(100)}

        if not historical_results:
            self._log('warning', "No historical data provided for JsonBundleAlgorithm.")
            return scores

        # Lọc lịch sử trước ngày dự đoán và sắp xếp mới nhất lên đầu
        filtered_history = [
            r for r in historical_results
            if isinstance(r.get('date'), datetime.date) and r['date'] < date_to_predict
        ]
        if not filtered_history:
            self._log('warning', f"No historical data before {date_to_predict}.")
            return scores

        filtered_history.sort(key=lambda x: x['date'], reverse=True)

        # Tạo context lịch sử chung cho tất cả các thuật toán con
        draw_entries = []
        last_seen = {}
        for r in filtered_history:
            d = r['date']
            days_ago = (date_to_predict - d).days
            if days_ago < 1:
                continue

            r_dict = r.get('result', {}) if isinstance(r.get('result'), dict) else {k: v for k, v in r.items() if k != 'date'}
            sp_raw = r_dict.get('special') or r_dict.get('prize_special') or r_dict.get('gdb')
            sp_num = None
            if sp_raw is not None:
                try:
                    s_str = str(sp_raw).strip()
                    sp_num = int(s_str[-2:]) if len(s_str) >= 2 and s_str[-2:].isdigit() else (int(s_str) if s_str.isdigit() else None)
                except (ValueError, TypeError):
                    sp_num = None

            nums_set = self.extract_numbers_from_dict(r_dict)
            for n_val in nums_set:
                if n_val not in last_seen:
                    last_seen[n_val] = days_ago

            draw_entries.append((days_ago, sp_num, list(nums_set), nums_set))

        context = {
            'draw_entries': draw_entries,
            'last_seen': last_seen,
            'last_draw': draw_entries[0] if draw_entries else None
        }

        # Đánh giá từng thuật toán con
        for formula in self.active_formulas:
            f_id = formula.get("id", "")
            f_name = formula.get("name", f_id)
            weight = self.weights.get(f_id, formula.get("weight", 1.0))
            params = formula.get("parameters", {})

            try:
                sub_scores = evaluate_appearance_formula(
                    params=params,
                    date_to_predict=date_to_predict,
                    filtered_history=filtered_history,
                    precomputed_context=context
                )

                # Chuẩn hóa theo normalization_mode
                if self.normalization_mode == "rank":
                    normalized_scores = compute_ranks(sub_scores)
                else:
                    min_val = min(sub_scores.values())
                    max_val = max(sub_scores.values())
                    diff = (max_val - min_val) if (max_val - min_val) > 1e-9 else 1.0
                    normalized_scores = {k: ((v - min_val) / diff) * 100.0 for k, v in sub_scores.items()}

                # Cộng dồn điểm số theo trọng số
                for num_str, score_val in normalized_scores.items():
                    scores[num_str] += weight * score_val

            except Exception as e:
                self._log('error', f"Error evaluating sub-formula '{f_name}' ({f_id}): {e}")

        # Làm tròn điểm
        scores = {k: round(v, 4) for k, v in scores.items()}
        self._log('info', f"JsonBundleAlgorithm generated {len(scores)} scores for {date_to_predict}.")
        return scores
