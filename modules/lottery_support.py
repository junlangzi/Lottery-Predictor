# Version: 6.2.0 - EOL
# Date: 24/10/2026
# -*- coding: utf-8 -*-
"""
modules/lottery_support.py
Cung cấp cấu hình, lịch quay, logic trích xuất kết quả, đánh giá trúng thưởng,
và đồng bộ thông minh cho tất cả các loại xổ số (XSMB và các dòng Vietlott).
"""

import os
import sys
import json
import shutil
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional

logger = logging.getLogger("modules.lottery_support")

LOTTERY_PROFILES: Dict[str, Dict[str, Any]] = {
    "xsmb": {
        "id": "xsmb",
        "name": "Xổ số Miền Bắc (XSMB)",
        "short_name": "XSMB",
        "file": "xsmb-2-digits.json",
        "format": "json",
        "prefix": "xsmb_",
        "num_classes": 100,
        "min_val": 0,
        "max_val": 99,
        "numbers": [f"{i:02d}" for i in range(100)],
        "int_numbers": list(range(100)),
        "num_cols": 10,
        "draw_days": [0, 1, 2, 3, 4, 5, 6],  # Thứ 2 -> Chủ Nhật
        "eval_picks": 3,
        "min_matches": 1,
        "prize_name": "Lô / Đề (Trùng ≥1 số)",
        "desc": "Quay 18h15 hàng ngày · 100 số (00–99), 27 giải thưởng",
    },
    "power_645": {
        "id": "power_645",
        "name": "Vietlott Mega 6/45",
        "short_name": "Mega 6/45",
        "file": "power645.jsonl",
        "format": "jsonl",
        "prefix": "POWER645_",
        "num_classes": 45,
        "min_val": 1,
        "max_val": 45,
        "numbers": [f"{i:02d}" for i in range(1, 46)],
        "int_numbers": list(range(1, 46)),
        "num_cols": 9,
        "draw_days": [2, 4, 6],  # Thứ 4 (2), Thứ 6 (4), Chủ Nhật (6)
        "eval_picks": 6,
        "min_matches": 3,
        "prize_name": "Giải Ba (Trùng ≥3/6 số, 30.000đ)",
        "desc": "Quay 18h00 Thứ 4, 6, CN · Chọn 6 số từ 01–45",
    },
    "power_655": {
        "id": "power_655",
        "name": "Vietlott Power 6/55",
        "short_name": "Power 6/55",
        "file": "power655.jsonl",
        "format": "jsonl",
        "prefix": "POWER655_",
        "num_classes": 55,
        "min_val": 1,
        "max_val": 55,
        "numbers": [f"{i:02d}" for i in range(1, 56)],
        "int_numbers": list(range(1, 56)),
        "num_cols": 11,
        "draw_days": [1, 3, 5],  # Thứ 3 (1), Thứ 5 (3), Thứ 7 (5)
        "eval_picks": 6,
        "min_matches": 3,
        "prize_name": "Giải Ba (Trùng ≥3/6 số chính, 50.000đ)",
        "desc": "Quay 18h00 Thứ 3, 5, 7 · Chọn 6 số từ 01–55",
    },
    "power_535": {
        "id": "power_535",
        "name": "Vietlott Lotto 5/35",
        "short_name": "Lotto 5/35",
        "file": "power535.jsonl",
        "format": "jsonl",
        "prefix": "POWER535_",
        "num_classes": 35,
        "min_val": 1,
        "max_val": 35,
        "numbers": [f"{i:02d}" for i in range(1, 36)],
        "int_numbers": list(range(1, 36)),
        "num_cols": 7,
        "draw_days": [0, 1, 2, 3, 4, 5, 6],  # Hàng ngày 13h00 & 21h00
        "eval_picks": 5,
        "min_matches": 2,
        "prize_name": "Giải Tư / KK (Trùng ≥2/5 số, 20.000đ)",
        "desc": "Quay 13h00 & 21h00 hàng ngày · Chọn 5 số từ 01–35",
    },
    "3d": {
        "id": "3d",
        "name": "Vietlott Max 3D / 3D+",
        "short_name": "Max 3D",
        "file": "3d.jsonl",
        "format": "jsonl",
        "prefix": "MAX3D_",
        "num_classes": 100,
        "min_val": 0,
        "max_val": 99,
        "numbers": [f"{i:02d}" for i in range(100)],
        "int_numbers": list(range(100)),
        "num_cols": 10,
        "draw_days": [0, 2, 4],  # Thứ 2 (0), Thứ 4 (2), Thứ 6 (4)
        "eval_picks": 2,
        "min_matches": 1,
        "prize_name": "Giải Bảy / Ba (Trùng ≥1 bộ)",
        "desc": "Quay 18h00 Thứ 2, 4, 6 · 100 số 2 chữ số cuối (00–99)",
    },
    "3d_pro": {
        "id": "3d_pro",
        "name": "Vietlott Max 3D Pro",
        "short_name": "Max 3D Pro",
        "file": "3d_pro.jsonl",
        "format": "jsonl",
        "prefix": "MAX3DPRO_",
        "num_classes": 100,
        "min_val": 0,
        "max_val": 99,
        "numbers": [f"{i:02d}" for i in range(100)],
        "int_numbers": list(range(100)),
        "num_cols": 10,
        "draw_days": [1, 3, 5],  # Thứ 3 (1), Thứ 5 (3), Thứ 7 (5)
        "eval_picks": 2,
        "min_matches": 1,
        "prize_name": "Giải Sáu (Trùng ≥1 bộ, 40.000đ)",
        "desc": "Quay 18h00 Thứ 3, 5, 7 · 100 số 2 chữ số cuối (00–99)",
    },
    "keno": {
        "id": "keno",
        "name": "Vietlott Keno",
        "short_name": "Keno",
        "file": "keno.jsonl",
        "format": "jsonl",
        "prefix": "KENO_",
        "num_classes": 80,
        "min_val": 1,
        "max_val": 80,
        "numbers": [f"{i:02d}" for i in range(1, 81)],
        "int_numbers": list(range(1, 81)),
        "num_cols": 10,
        "draw_days": [0, 1, 2, 3, 4, 5, 6],  # Hàng ngày 06h00–21h50
        "eval_picks": 1,
        "min_matches": 1,
        "prize_name": "Bậc 1 (Trùng 1/20 số)",
        "desc": "Quay 10 phút/kỳ hàng ngày · 80 số (01–80)",
    },
    "bingo18": {
        "id": "bingo18",
        "name": "Vietlott Bingo 18",
        "short_name": "Bingo 18",
        "file": "bingo18.jsonl",
        "format": "jsonl",
        "prefix": "BINGO18_",
        "num_classes": 6,
        "min_val": 1,
        "max_val": 6,
        "numbers": [str(i) for i in range(1, 7)],
        "int_numbers": list(range(1, 7)),
        "num_cols": 6,
        "draw_days": [0, 1, 2, 3, 4, 5, 6],  # Hàng ngày 06h00–21h55
        "eval_picks": 1,
        "min_matches": 1,
        "prize_name": "Trùng 1 số (1/3 xúc xắc)",
        "desc": "Quay 10 phút/kỳ hàng ngày · 6 số (1–6)",
    },
}

LOTTERY_ORDER = [
    "xsmb", "power_645", "power_655", "3d", "3d_pro", "power_535", "keno", "bingo18"
]


def get_lottery_profile(lottery_id: str) -> Dict[str, Any]:
    lid = str(lottery_id or "xsmb").strip().lower()
    return LOTTERY_PROFILES.get(lid, LOTTERY_PROFILES["xsmb"])


def get_lottery_prefix(lottery_id: str) -> str:
    prof = get_lottery_profile(lottery_id)
    return prof.get("prefix", "")


def get_data_filepath(lottery_id: str, data_dir: Path | str) -> Path:
    prof = get_lottery_profile(lottery_id)
    return Path(data_dir) / prof["file"]


def format_number_for_lottery(arg1: Any, arg2: Any = None) -> str:
    """Format số hiển thị phù hợp với từng loại xổ số. Hỗ trợ cả 2 thứ tự tham số."""
    if isinstance(arg1, str) and arg1.lower() in LOTTERY_PROFILES:
        lottery_id, num = arg1, arg2
    elif isinstance(arg2, str) and arg2.lower() in LOTTERY_PROFILES:
        num, lottery_id = arg1, arg2
    else:
        # arg1 might be lottery_id string not yet lowercase or default
        if isinstance(arg1, str) and not arg1.isdigit():
            lottery_id, num = arg1, arg2
        else:
            num, lottery_id = arg1, arg2 or "xsmb"

    prof = get_lottery_profile(str(lottery_id or "xsmb"))
    try:
        val = int(num)
    except (ValueError, TypeError):
        return str(num) if num is not None else ""

    if prof.get("id") == "bingo18":
        return str(val)
    return f"{val:02d}"



def is_valid_draw_date(d: datetime.date, lottery_id: str) -> bool:
    prof = get_lottery_profile(lottery_id)
    draw_days = prof.get("draw_days", list(range(7)))
    return d.weekday() in draw_days


def get_next_draw_date(current_date: datetime.date, lottery_id: str) -> datetime.date:
    """Tìm ngày quay kế tiếp gần nhất dựa theo lịch quay."""
    prof = get_lottery_profile(lottery_id)
    draw_days = set(prof.get("draw_days", list(range(7))))
    next_d = current_date + datetime.timedelta(days=1)
    for _ in range(14):
        if next_d.weekday() in draw_days:
            return next_d
        next_d += datetime.timedelta(days=1)
    return current_date + datetime.timedelta(days=1)


def get_prev_draw_date(current_date: datetime.date, lottery_id: str) -> datetime.date:
    """Tìm ngày quay trước đó gần nhất dựa theo lịch quay."""
    prof = get_lottery_profile(lottery_id)
    draw_days = set(prof.get("draw_days", list(range(7))))
    prev_d = current_date - datetime.timedelta(days=1)
    for _ in range(14):
        if prev_d.weekday() in draw_days:
            return prev_d
        prev_d -= datetime.timedelta(days=1)
    return current_date - datetime.timedelta(days=1)


def parse_lottery_file(filepath: Path | str) -> List[Dict[str, Any]]:
    """
    Đọc dữ liệu lịch sử từ file .json hoặc .jsonl, trả về danh sách các bản ghi đã sắp xếp theo ngày.
    Mỗi phần tử có dạng: {'date': datetime.date, 'result': ...}
    """
    p = Path(filepath)
    if not p.exists():
        return []

    raw_items = []
    try:
        if p.suffix.lower() == ".jsonl":
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            raw_items.append(json.loads(line))
                        except Exception:
                            pass
        else:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    raw_items = data
                elif isinstance(data, dict) and "results" in data:
                    for d_str, r_val in data["results"].items():
                        raw_items.append({"date": d_str, "result": r_val})
    except Exception as e:
        logger.error(f"Error loading lottery data file {p}: {e}")
        return []

    results_temp = []
    unique_entries = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        date_str_raw = item.get("date")
        if not date_str_raw:
            continue
        date_str_cleaned = str(date_str_raw).split("T")[0].split(" ")[0].strip()
        try:
            date_obj = datetime.datetime.strptime(date_str_cleaned, "%Y-%m-%d").date()
        except ValueError:
            continue

        draw_id = str(item.get("id") or "").strip()
        result_data = item.get("result")
        if result_data is None:
            result_data = {k: v for k, v in item.items() if k not in ("date", "process_time")}
        elif isinstance(result_data, list):
            result_data = {"result": result_data, "id": draw_id}
        elif isinstance(result_data, dict):
            if "id" not in result_data and draw_id:
                result_data["id"] = draw_id

        # Unique key preserves multi-draws per date (e.g. 5/35 draws with different ids or results)
        res_str = json.dumps(result_data, sort_keys=True, ensure_ascii=False) if isinstance(result_data, (dict, list)) else str(result_data)
        entry_key = (date_obj, draw_id) if draw_id else (date_obj, res_str)
        if entry_key in unique_entries:
            continue
        unique_entries.add(entry_key)

        results_temp.append({"date": date_obj, "result": result_data})

    def _draw_sort_key(x):
        d = x["date"]
        r = x.get("result")
        did = str(r.get("id", "")) if isinstance(r, dict) else ""
        return (d, did)

    results_temp.sort(key=_draw_sort_key)
    return results_temp


def extract_numbers_for_lottery_with_special(lottery_id: str, result_obj: Any) -> Tuple[Set[int], Optional[int]]:
    """
    Trích xuất tập hợp các số trúng thưởng và số đặc biệt (nếu có)
    theo quy cách của từng loại xổ số.
    Trả về (actual_numbers_set, special_number).
    """
    numbers: Set[int] = set()
    special: Optional[int] = None

    if result_obj is None:
        return numbers, special

    lid = str(lottery_id or "xsmb").strip().lower()

    # Trường hợp result_obj là list trực tiếp
    if isinstance(result_obj, (list, tuple)):
        raw_list = list(result_obj)
        for x in raw_list:
            try:
                numbers.add(int(x))
            except (ValueError, TypeError):
                pass
        return numbers, special

    # Trường hợp result_obj là dict
    if isinstance(result_obj, dict):
        # 1. Nếu có key 'result' bên trong
        inner_res = result_obj.get("result")
        if isinstance(inner_res, (list, tuple)):
            int_list = []
            for x in inner_res:
                try:
                    int_list.append(int(x))
                except (ValueError, TypeError):
                    pass

            if lid == "power_655":
                # Power 6/55: 6 số chính + số thứ 7 là số đặc biệt
                if len(int_list) >= 7:
                    numbers = set(int_list[:6])
                    special = int_list[6]
                else:
                    numbers = set(int_list[:6])
            elif lid == "power_645":
                numbers = set(int_list[:6])
            elif lid == "power_535":
                if len(int_list) >= 6:
                    numbers = set(int_list[:5])
                    special = int_list[5]
                else:
                    numbers = set(int_list[:5])
            elif lid == "keno":
                numbers = set(int_list[:20])
            elif lid == "bingo18":
                numbers = set(int_list[:3])
            else:
                numbers = set(int_list)
            return numbers, special

        # 2. Xổ số 3D / 3D Pro: dict với các giải
        if lid in ("3d", "3d_pro"):
            for k, val in result_obj.items():
                if k in ("date", "id", "process_time"):
                    continue
                v_list = val if isinstance(val, (list, tuple)) else [val]
                for item in v_list:
                    if item is None:
                        continue
                    s = str(item).strip()
                    try:
                        # 2 số cuối của bộ 3 số
                        if len(s) >= 2 and s[-2:].isdigit():
                            numbers.add(int(s[-2:]))
                        elif len(s) == 1 and s.isdigit():
                            numbers.add(int(s))
                    except Exception:
                        pass
            return numbers, special

        # 3. XSMB: Lô 2 số cuối của 27 giải
        keys_to_ignore = {"date", "_id", "source", "day_of_week", "sign", "created_at", "updated_at", "province_name", "province_id", "id"}
        for k, val in result_obj.items():
            if k in keys_to_ignore:
                continue
            v_list = val if isinstance(val, (list, tuple)) else [val]
            for item in v_list:
                if item is None:
                    continue
                s = str(item).strip()
                try:
                    if len(s) >= 2 and s[-2:].isdigit():
                        num = int(s[-2:])
                        if 0 <= num <= 99:
                            numbers.add(num)
                    elif len(s) == 1 and s.isdigit():
                        num = int(s)
                        if 0 <= num <= 99:
                            numbers.add(num)
                except Exception:
                    pass

        # Đặc biệt XSMB
        sp_val = result_obj.get("special") or result_obj.get("prize_special") or result_obj.get("dac_biet")
        if sp_val is not None:
            try:
                s = str(sp_val).strip()
                if len(s) >= 2 and s[-2:].isdigit():
                    special = int(s[-2:])
                elif len(s) == 1 and s.isdigit():
                    special = int(s)
            except Exception:
                pass

    return numbers, special


def extract_numbers_for_lottery(arg1: Any, arg2: Any = None) -> List[int]:
    """
    Trích xuất danh sách các số trúng thưởng từ kết quả xổ số.
    Hỗ trợ cả 2 thứ tự tham số: (lottery_id, result_obj) hoặc (result_obj, lottery_id).
    """
    if isinstance(arg1, str) and not isinstance(arg2, str):
        lottery_id, result_obj = arg1, arg2
    else:
        result_obj, lottery_id = arg1, arg2 or "xsmb"

    nums, _ = extract_numbers_for_lottery_with_special(lottery_id, result_obj)
    return sorted(list(nums))


def evaluate_win(lottery_id: str, sorted_predictions: List[Any], actual_data: Any) -> Dict[str, Any]:
    """
    Đánh giá trúng thưởng dựa trên luật giải thưởng nhỏ nhất của từng loại xổ số:
    - XSMB: Top 3 (hoặc 1/3/5/10), trùng ≥1 số là trúng (Lô).
    - Mega 6/45: Top 6 số có điểm cao nhất, trùng ≥3 số là trúng Giải Ba (30.000đ).
    - Power 6/55: Top 6 số, trùng ≥3 số chính là trúng Giải Ba (50.000đ).
    - Lotto 5/35: Top 5 số, trùng ≥2 số là trúng Giải Tư / Khuyến khích (20.000đ).
    - Max 3D / 3D+: Trùng ≥1 bộ số.
    - Max 3D Pro: Trùng ≥1 bộ số (Giải Sáu 40.000đ).
    - Keno: Trùng ≥1 số (Bậc 1).
    - Bingo 18: Trùng ≥1 số (1/3 xúc xắc).
    """
    prof = get_lottery_profile(lottery_id)
    eval_picks = int(prof.get("eval_picks", 3))
    min_matches = int(prof.get("min_matches", 1))
    prize_name = prof.get("prize_name", "Trúng thưởng")

    actual_set, special_num = extract_numbers_for_lottery_with_special(lottery_id, actual_data)
    picks = []
    for item in sorted_predictions[:eval_picks]:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            picks.append(int(item[0]))
        else:
            picks.append(int(item))

    matched_numbers = [num for num in picks if num in actual_set]
    match_count = len(matched_numbers)
    is_win = match_count >= min_matches

    # Chi tiết giải thưởng cụ thể nếu trúng cao hơn
    prize_detail = prize_name
    lid = prof.get("id")
    if is_win:
        if lid == "power_645":
            if match_count == 6:
                prize_detail = "🎉 JACKPOT (Trùng 6/6 số, tối thiểu 12 tỷ)"
            elif match_count == 5:
                prize_detail = "⭐ Giải Nhất (Trùng 5/6 số, 10.000.000đ)"
            elif match_count == 4:
                prize_detail = "✨ Giải Nhì (Trùng 4/6 số, 300.000đ)"
            else:
                prize_detail = "✓ Giải Ba (Trùng 3/6 số, 30.000đ)"
        elif lid == "power_655":
            if match_count == 6:
                prize_detail = "🎉 JACKPOT 1 (Trùng 6/6 số chính, tối thiểu 30 tỷ)"
            elif match_count == 5 and special_num in picks:
                prize_detail = "🎉 JACKPOT 2 (Trùng 5 số + Số đặc biệt, tối thiểu 3 tỷ)"
            elif match_count == 5:
                prize_detail = "⭐ Giải Nhất (Trùng 5/6 số, 40.000.000đ)"
            elif match_count == 4:
                prize_detail = "✨ Giải Nhì (Trùng 4/6 số, 500.000đ)"
            else:
                prize_detail = "✓ Giải Ba (Trùng 3/6 số, 50.000đ)"
        elif lid == "power_535":
            if match_count == 5:
                prize_detail = "🎉 Giải Nhất (Trùng 5/5 số)"
            elif match_count == 4:
                prize_detail = "⭐ Giải Nhì (Trùng 4/5 số)"
            elif match_count == 3:
                prize_detail = "✨ Giải Ba (Trùng 3/5 số)"
            else:
                prize_detail = "✓ Giải Tư / KK (Trùng 2/5 số, 20.000đ)"

    return {
        "is_win": is_win,
        "match_count": match_count,
        "eval_picks": eval_picks,
        "picks": picks,
        "matched_numbers": matched_numbers,
        "actual_set": actual_set,
        "special_num": special_num,
        "prize_name": prize_name,
        "prize_detail": prize_detail if is_win else f"Chưa trúng ({match_count}/{eval_picks} số, cần ≥{min_matches})",
    }


def detect_algorithm_lottery_type(algo_name: str, algo_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Nhận diện loại xổ số mà thuật toán nhắm tới dựa trên:
    - Metadata của JSON bundle (bundle_data.lottery_id, prefix)
    - Tên class, tên file hoặc tên hiển thị
    - ID của các công thức con bên trong bundle
    """
    if algo_data:
        instance = algo_data.get("instance")
        bundle_data = getattr(instance, "bundle_data", {}) if instance else {}
        if not bundle_data and isinstance(algo_data.get("bundle_data"), dict):
            bundle_data = algo_data["bundle_data"]

        if bundle_data:
            bid = bundle_data.get("lottery_id") or bundle_data.get("lottery_type")
            if bid and str(bid).lower() in LOTTERY_PROFILES:
                return str(bid).lower()

            raw_formulas = bundle_data.get("formulas") or bundle_data.get("active_algorithms") or []
            for f in raw_formulas:
                fname = (str(f.get("name", "")) + " " + str(f.get("id", ""))).upper()
                for pid, pprof in LOTTERY_PROFILES.items():
                    pfx = pprof.get("prefix", "").upper()
                    if pfx and pfx in fname:
                        return pid

        path_str = str(algo_data.get("path", ""))
        class_str = str(algo_data.get("class_name", ""))
        full_text = f"{algo_name} {class_str} {path_str}".upper()
    else:
        full_text = str(algo_name).upper()

    if "POWER645" in full_text or "MEGA645" in full_text or "6_45" in full_text or "6/45" in full_text:
        return "power_645"
    if "POWER655" in full_text or "6_55" in full_text or "6/55" in full_text:
        return "power_655"
    if "POWER535" in full_text or "LOTTO535" in full_text or "5_35" in full_text or "5/35" in full_text:
        return "power_535"
    if "MAX3DPRO" in full_text or "3D_PRO" in full_text or "3DPRO" in full_text:
        return "3d_pro"
    if "MAX3D" in full_text or "3D+" in full_text or "3D" in full_text:
        return "3d"
    if "KENO" in full_text:
        return "keno"
    if "BINGO18" in full_text or "BINGO" in full_text:
        return "bingo18"
    if "XSMB" in full_text or "MIENBAC" in full_text or "MIEN_BAC" in full_text:
        return "xsmb"

    return "xsmb"


def cleanup_temp_files(data_dir: Path | str) -> int:
    """Xóa tất cả các file tạm (.bak, .tmp, .temp, .download, .part) trong thư mục data."""
    p_dir = Path(data_dir)
    if not p_dir.exists():
        return 0
    deleted = 0
    try:
        for item in p_dir.iterdir():
            if not item.is_file():
                continue
            name_lower = item.name.lower()
            if any(ext in name_lower for ext in [".tmp", ".temp", ".part", ".download", ".bak-", ".bak"]):
                try:
                    item.unlink()
                    deleted += 1
                    logger.debug(f"Deleted temporary file: {item.name}")
                except Exception as del_err:
                    logger.warning(f"Failed to delete temp file {item.name}: {del_err}")
    except Exception as e:
        logger.error(f"Error cleaning temp files in {data_dir}: {e}")
    return deleted


def sync_lottery_data(lottery_id: str, data_dir: Path | str, force_github: bool = False, custom_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Thực hiện đồng bộ dữ liệu cho loại xổ số cụ thể vào thư mục data_dir.
    Sử dụng module sync thông minh từ dự án chính.
    Tự động xóa các file tạm sau khi đồng bộ thành công.
    Hỗ trợ custom_url để tải từ link cấu hình của người dùng.
    """
    target_data_dir = Path(data_dir)
    target_data_dir.mkdir(parents=True, exist_ok=True)
    lid = str(lottery_id or "xsmb").strip().lower()

    # Nạp module sync từ thư mục gốc nếu cần
    parent_dir = Path(__file__).resolve().parent.parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    import sync

    result_info = {"success": False, "message": "", "records": 0, "last_date": ""}
    try:
        if lid == "xsmb":
            res = sync.sync_xsmb(data_dir=target_data_dir, force_github=force_github, custom_url=custom_url)
            msg = res.get("message", "Đồng bộ XSMB hoàn tất")
            cnt = res.get("records") or res.get("total_records", 0)
            is_ok = bool(
                res.get("success")
                or res.get("status") in ("success", "up_to_date")
                or "thành công" in str(msg).lower()
                or (cnt > 0)
            )
            result_info["success"] = is_ok
            result_info["message"] = msg
            result_info["records"] = cnt
            result_info["last_date"] = str(res.get("last_date") or res.get("latest_date") or "")
        else:
            res_df = sync.smart_sync(lid, data_dir=target_data_dir, force_github=force_github, custom_url=custom_url)
            last_dt = sync.get_last_date(lid, data_dir=target_data_dir)
            cnt = sync.get_record_count(lid, data_dir=target_data_dir)
            prof = get_lottery_profile(lid)
            result_info["success"] = True
            result_info["records"] = cnt
            result_info["last_date"] = str(last_dt) if last_dt else ""
            result_info["message"] = f"Đồng bộ thành công {prof['name']}: {cnt:,} kỳ (mới nhất: {last_dt})"
    except Exception as e:
        logger.error(f"Error during smart_sync for {lid}: {e}", exc_info=True)
        result_info["success"] = False
        result_info["message"] = f"Lỗi đồng bộ {lid}: {e}"
    finally:
        # Xóa các file tạm sau khi đồng bộ
        cleanup_temp_files(target_data_dir)

    return result_info
