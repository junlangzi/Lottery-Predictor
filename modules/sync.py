# Version: 6.2.0
# Date: 24/10/2026
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync.py
Đồng bộ thông minh dữ liệu KQXS Vietlott và XSMB.

Luồng xử lý:
1. Kiểm tra gap thời gian so với kỳ mới nhất trong file local
2. Nếu gap lớn → tải toàn bộ dữ liệu từ GitHub
3. Crawl phần mới nhất từ nguồn trực tiếp (Vietlott AjaxPro / xoso.com.vn)
4. Merge dữ liệu (không trùng lặp) và lưu vào thư mục data/

Hỗ trợ các loại xổ số:
• XSMB           : Xổ số Miền Bắc (quay 18h15 hàng ngày)
• Power 6/55     : Quay 2 ngày/lần (Thứ 3, 5, 7)
• Power 6/45     : Quay 2 ngày/lần (Thứ 4, 6, Chủ Nhật)
• Lotto 5/35     : Quay 2 lần/ngày, từ Thứ Hai đến Chủ Nhật
• Max 3D         : Quay 2 ngày/lần (Thứ 2, 4, 6)
• Max 3D Pro     : Quay 2 ngày/lần (Thứ 3, 5, 7)
• Keno           : Quay khoảng 8 phút/lần
• Bingo18        : Quay khoảng 5 phút/lần
"""

from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pendulum
import polars as pl
import requests
from bs4 import BeautifulSoup
from loguru import logger

# XSMB 27-prize keys matching xsmb-2-digits.json
XSMB_PRIZE_KEYS = [
    "special", "prize1",
    "prize2_1", "prize2_2",
    "prize3_1", "prize3_2", "prize3_3", "prize3_4", "prize3_5", "prize3_6",
    "prize4_1", "prize4_2", "prize4_3", "prize4_4",
    "prize5_1", "prize5_2", "prize5_3", "prize5_4", "prize5_5", "prize5_6",
    "prize6_1", "prize6_2", "prize6_3",
    "prize7_1", "prize7_2", "prize7_3", "prize7_4",
]

def _parse_xoso_prizes_from_html(html: str) -> Optional[Dict[str, List[int]]]:
    """Trích xuất 27 giải XSMB từ HTML xoso.com.vn."""
    result = {}
    for cls in (
        "special-prize", "prize1", "prize2", "prize3",
        "prize4", "prize5", "prize6", "prize7",
    ):
        pat = re.compile(
            rf'class\s*=\s*["\']?{re.escape(cls)}["\']?[^>]*>([^<]+)',
            re.I,
        )
        nums = []
        for m in pat.finditer(html):
            digits = "".join(ch for ch in m.group(1) if ch.isdigit())
            if digits:
                try:
                    nums.append(int(digits))
                except Exception:
                    pass
        result[cls] = nums

    if result.get("special-prize"):
        return result

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for cls in (
            "special-prize", "prize1", "prize2", "prize3",
            "prize4", "prize5", "prize6", "prize7",
        ):
            if result.get(cls):
                continue
            nums = []
            for p in soup.find_all(attrs={"class": cls}):
                digits = "".join(ch for ch in p.get_text() if ch.isdigit())
                if digits:
                    try:
                        nums.append(int(digits))
                    except Exception:
                        pass
            result[cls] = nums
    except Exception:
        pass
    return result if any(result.values()) else None

def fetch_xoso_result_2digits(selected_date) -> Optional[Dict]:
    """Crawl đầy đủ 27 giải XSMB từ xoso.com.vn và lấy 2 số cuối (% 100)."""
    url = f"https://xoso.com.vn/xsmb-{selected_date:%d-%m-%Y}.html"
    html = ""
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=20)
        if r.ok:
            html = r.text
    except Exception as e:
        logger.warning(f"[xoso] HTTP lỗi {url}: {e}")
        return None

    if not html or "special-prize" not in html:
        try:
            url2 = f"https://xoso.com.vn/xsmb-{selected_date.day}-{selected_date.month}-{selected_date.year}.html"
            if url2 != url:
                r2 = requests.get(url2, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=20)
                if r2.ok:
                    html = r2.text
        except Exception:
            pass

    if not html or "special-prize" not in html:
        return None

    parsed = _parse_xoso_prizes_from_html(html)
    if not parsed or not parsed.get("special-prize"):
        return None

    def _pick(arr, n):
        arr = list(arr or [])
        return arr[:n] if len(arr) >= n else None

    p1 = _pick(parsed.get("prize1"), 1)
    p2 = _pick(parsed.get("prize2"), 2)
    p3 = _pick(parsed.get("prize3"), 6)
    p4 = _pick(parsed.get("prize4"), 4)
    p5 = _pick(parsed.get("prize5"), 6)
    p6 = _pick(parsed.get("prize6"), 3)
    p7 = _pick(parsed.get("prize7"), 4)
    if None in (p1, p2, p3, p4, p5, p6, p7):
        return None

    raw_vals = [parsed["special-prize"][0], p1[0]] + list(p2) + list(p3) + list(p4) + list(p5) + list(p6) + list(p7)
    digits = [int(v) % 100 for v in raw_vals]
    rec = {"date": f"{selected_date.isoformat()}T00:00:00.000"}
    for k, v in zip(XSMB_PRIZE_KEYS, digits):
        rec[k] = v
    return rec

def merge_xsmb_2digits_records(existing: list, new_recs: list) -> list:
    """Gộp các bản ghi XSMB theo ngày, bản ghi mới ghi đè bản ghi cũ cùng ngày."""
    by_d = {}
    for r in (existing or []) + (new_recs or []):
        if not isinstance(r, dict):
            continue
        raw_d = r.get("date") or r.get("ngay") or r.get("Date")
        if not raw_d:
            continue
        try:
            iso = str(raw_d).split("T")[0]
            by_d[iso] = r
        except Exception:
            pass
    keys = sorted(by_d.keys())
    return [by_d[k] for k in keys]

def load_xsmb_list(path: str) -> list:
    """Nạp danh sách kỳ quay XSMB từ file JSON."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def fetch_kqxs_json_from_github(timeout: int = 45):
    """Tải toàn bộ xsmb-2-digits.json từ GitHub."""
    headers = {
        "User-Agent": "ThienCoSo-KQXS-Sync/1.0",
        "Accept": "application/json",
    }
    last_err = None
    for url in (XSMB_GITHUB_RAW, XSMB_GITHUB_BACKUP):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list) or len(data) < 10:
                raise ValueError(f"JSON không phải list KQXS hợp lệ ({type(data)})")
            return data, url
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Không tải được KQXS từ GitHub: {last_err}")

HAS_CORE_XSMB = True


# ============================================================
# CẤU HÌNH CHUNG
# ============================================================

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = _DEFAULT_DATA_DIR

# Nếu số kỳ quay lý thuyết bị thiếu > GAP_THRESHOLD
# thì ưu tiên tải dữ liệu đầy đủ từ GitHub trước
GAP_THRESHOLD = 2

# Số page mới nhất sẽ crawl từ Vietlott sau khi đã có dữ liệu nền
LATEST_PAGES = 5

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/vietvudanh/vietlott-data/main/data"
XSMB_GITHUB_RAW = "https://raw.githubusercontent.com/junlangzi/data-kqxs/refs/heads/main/data/xsmb-2-digits.json"
XSMB_GITHUB_BACKUP = "https://raw.githubusercontent.com/vietvudanh/vietlott-data/main/data/xsmb-2-digits.json"

# ============================================================
# CẤU HÌNH TỪNG SẢN PHẨM
# ============================================================

PRODUCTS: Dict[str, Dict[str, Any]] = {
    # ----------------------------------------------------------
    # XỔ SỐ MIỀN BẮC (XSMB)
    # ----------------------------------------------------------
    "xsmb": {
        "name": "Xổ số Miền Bắc (XSMB)",
        "file": "xsmb-2-digits.json",
        "format": "json",
        "interval": timedelta(days=1),
        "desc": "Quay hàng ngày lúc 18h15 - 18h30",
        "page_size": 1,
        "num_thread": 1,
        "url": "https://xoso.com.vn",
        "body_template": {},
    },

    # ----------------------------------------------------------
    # POWER 6/55
    # Chu kỳ: 2 ngày/lần (Thứ 3, 5, 7)
    # ----------------------------------------------------------
    "power_655": {
        "name": "Vietlott Power 6/55",
        "file": "power655.jsonl",
        "format": "jsonl",
        "url": "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.Game655CompareWebPart,Vietlott.PlugIn.WebParts.ashx",
        "interval": timedelta(days=2),
        "desc": "Quay Thứ 3, 5, 7 lúc 18h00",
        "page_size": 6,
        "num_thread": 8,
        "body_template": {
            "ORenderInfo": {
                "SiteId": "main.frontend.vi",
                "SiteAlias": "main.vi",
                "UserSessionId": "",
                "SiteLang": "vi",
                "IsPageDesign": False,
                "ExtraParam1": "",
                "ExtraParam2": "",
                "ExtraParam3": "",
                "SiteURL": "",
                "WebPage": None,
                "SiteName": "Vietlott",
                "OrgPageAlias": None,
                "PageAlias": None,
                "RefKey": None,
                "FullPageAlias": None,
            },
            "Key": "23bbd667",
            "GameDrawId": "",
            "ArrayNumbers": [["" for _ in range(18)] for _ in range(5)],
            "CheckMulti": False,
            "PageIndex": 0,
        },
    },

    # ----------------------------------------------------------
    # POWER 6/45
    # Chu kỳ: 2 ngày/lần (Thứ 4, 6, Chủ Nhật)
    # ----------------------------------------------------------
    "power_645": {
        "name": "Vietlott Power 6/45",
        "file": "power645.jsonl",
        "format": "jsonl",
        "url": "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.Game645CompareWebPart,Vietlott.PlugIn.WebParts.ashx",
        "interval": timedelta(days=2),
        "desc": "Quay Thứ 4, 6, Chủ Nhật lúc 18h00",
        "page_size": 6,
        "num_thread": 8,
        "body_template": {
            "ORenderInfo": {
                "SiteId": "main.frontend.vi",
                "SiteAlias": "main.vi",
                "UserSessionId": "",
                "SiteLang": "vi",
                "IsPageDesign": False,
                "ExtraParam1": "",
                "ExtraParam2": "",
                "ExtraParam3": "",
                "SiteURL": "",
                "WebPage": None,
                "SiteName": "Vietlott",
                "OrgPageAlias": None,
                "PageAlias": None,
                "RefKey": None,
                "FullPageAlias": None,
            },
            "Key": "23bbd667",
            "GameDrawId": "",
            "ArrayNumbers": [["" for _ in range(18)] for _ in range(6)],
            "CheckMulti": False,
            "PageIndex": 0,
        },
    },

    # ----------------------------------------------------------
    # LOTTO 5/35
    # Chu kỳ: 2 lần/ngày (Thứ 2 - Chủ Nhật)
    # ----------------------------------------------------------
    "power_535": {
        "name": "Vietlott Lotto 5/35",
        "file": "power535.jsonl",
        "format": "jsonl",
        "url": "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.Game535CompareWebPart,Vietlott.PlugIn.WebParts.ashx",
        "interval": timedelta(hours=12),
        "desc": "Quay 2 lần/ngày (Thứ 2 - CN)",
        "page_size": 6,
        "num_thread": 8,
        "body_template": {
            "ORenderInfo": {
                "SiteId": "main.frontend.vi",
                "SiteAlias": "main.vi",
                "UserSessionId": "",
                "SiteLang": "vi",
                "IsPageDesign": False,
                "ExtraParam1": "",
                "ExtraParam2": "",
                "ExtraParam3": "",
                "SiteURL": "",
                "WebPage": None,
                "SiteName": "Vietlott",
                "OrgPageAlias": None,
                "PageAlias": None,
                "RefKey": None,
                "FullPageAlias": None,
            },
            "Key": "23bbd667",
            "GameDrawId": "",
            "ArrayNumbers": [["" for _ in range(18)] for _ in range(6)],
            "CheckMulti": False,
            "PageIndex": 0,
        },
    },

    # ----------------------------------------------------------
    # MAX 3D
    # Chu kỳ: 2 ngày/lần (Thứ 2, 4, 6)
    # ----------------------------------------------------------
    "3d": {
        "name": "Vietlott Max 3D",
        "file": "3d.jsonl",
        "format": "jsonl",
        "url": "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.GameMax3DCompareWebPart,Vietlott.PlugIn.WebParts.ashx",
        "interval": timedelta(days=2),
        "desc": "Quay Thứ 2, 4, 6 lúc 18h00",
        "page_size": 5,
        "num_thread": 8,
        "body_template": {
            "CheckMulti": 0,
            "GameDrawId": "",
            "GameId": "5",
            "ORenderInfo": {
                "SiteId": "main.frontend.vi",
                "SiteAlias": "main.vi",
                "UserSessionId": "",
                "SiteLang": "vi",
                "IsPageDesign": False,
                "ExtraParam1": "",
                "ExtraParam2": "",
                "ExtraParam3": "",
                "SiteURL": "",
                "WebPage": None,
                "SiteName": "Vietlott",
                "OrgPageAlias": None,
                "PageAlias": None,
                "RefKey": None,
                "FullPageAlias": None,
            },
            "PageIndex": 0,
            "number01": "123",
            "number02": "321",
        },
    },

    # ----------------------------------------------------------
    # MAX 3D PRO
    # Chu kỳ: 2 ngày/lần (Thứ 3, 5, 7)
    # ----------------------------------------------------------
    "3d_pro": {
        "name": "Vietlott Max 3D Pro",
        "file": "3d_pro.jsonl",
        "format": "jsonl",
        "url": "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.GameMax3DProCompareWebPart,Vietlott.PlugIn.WebParts.ashx",
        "interval": timedelta(days=2),
        "desc": "Quay Thứ 3, 5, 7 lúc 18h00",
        "page_size": 5,
        "num_thread": 8,
        "body_template": {
            "GameDrawId": "",
            "GameId": "7",
            "ORenderInfo": {
                "SiteId": "main.frontend.vi",
                "SiteAlias": "main.vi",
                "UserSessionId": "",
                "SiteLang": "vi",
                "IsPageDesign": False,
                "ExtraParam1": "",
                "ExtraParam2": "",
                "ExtraParam3": "",
                "SiteURL": "",
                "WebPage": None,
                "SiteName": "Vietlott",
                "OrgPageAlias": None,
                "PageAlias": None,
                "RefKey": None,
                "FullPageAlias": None,
            },
            "PageIndex": 0,
            "number01": "123",
            "number02": "321",
        },
    },

    # ----------------------------------------------------------
    # KENO
    # Chu kỳ: khoảng 8 phút / 1 kỳ
    # ----------------------------------------------------------
    "keno": {
        "name": "Vietlott Keno",
        "file": "keno.jsonl",
        "format": "jsonl",
        "url": "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.GameKenoCompareWebPart,Vietlott.PlugIn.WebParts.ashx",
        "interval": timedelta(minutes=8),
        "desc": "Quay ~8 phút/kỳ (hàng trăm kỳ/ngày)",
        "page_size": 6,
        "num_thread": 12,
        "body_template": {
            "DrawDate": "",
            "GameDrawNo": "",
            "GameId": "6",
            "ORenderInfo": {
                "SiteId": "main.frontend.vi",
                "SiteAlias": "main.vi",
                "UserSessionId": "",
                "SiteLang": "vi",
                "IsPageDesign": False,
                "ExtraParam1": "",
                "ExtraParam2": "",
                "ExtraParam3": "",
                "SiteURL": "",
                "WebPage": None,
                "SiteName": "Vietlott",
                "OrgPageAlias": None,
                "PageAlias": None,
                "RefKey": None,
                "FullPageAlias": None,
            },
            "OddEven": 2,
            "PageIndex": 1,
            "ProcessType": 0,
            "TotalRow": 112453,
            "UpperLower": 2,
            "number": "",
        },
    },

    # ----------------------------------------------------------
    # BINGO18
    # Chu kỳ: khoảng 5 phút / 1 kỳ
    # ----------------------------------------------------------
    "bingo18": {
        "name": "Vietlott Bingo 18",
        "file": "bingo18.jsonl",
        "format": "jsonl",
        "url": "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.GameBingoCompareWebPart,Vietlott.PlugIn.WebParts.ashx",
        "interval": timedelta(minutes=6),
        "desc": "Quay 6 phút/kỳ (06h05–21h53 hàng ngày)",
        "page_size": 6,
        "num_thread": 10,
        "body_template": {
            "ORenderInfo": {
                "SiteId": "main.frontend.vi",
                "SiteAlias": "main.vi",
                "UserSessionId": "",
                "SiteLang": "vi",
                "IsPageDesign": False,
                "ExtraParam1": "",
                "ExtraParam2": "",
                "ExtraParam3": "",
                "SiteURL": "",
                "WebPage": None,
                "SiteName": "Vietlott",
                "OrgPageAlias": None,
                "PageAlias": None,
                "RefKey": None,
                "FullPageAlias": None,
            },
            "GameId": "8",
            "GameDrawNo": "",
            "number": "",
            "DrawDate": "",
            "PageIndex": 1,
            "TotalRow": 45628,
        },
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Content-Type": "text/plain; charset=utf-8",
    "X-AjaxPro-Method": "ServerSideDrawResult",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://vietlott.vn",
    "Connection": "keep-alive",
    "Referer": "https://vietlott.vn/vi/trung-thuong/ket-qua-trung-thuong/winning-number-645",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

TIMEOUT = 25


# ============================================================
# HÀM TIỆN ÍCH ĐƯỜNG DẪN & DỮ LIỆU
# ============================================================

def set_data_dir(path: Path | str) -> Path:
    """Cập nhật thư mục lưu data toàn cục."""
    global DATA_DIR
    DATA_DIR = Path(path)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def get_local_path(product: str, data_dir: Path | str | None = None) -> Path:
    """Lấy đường dẫn file kết quả của một loại xổ số."""
    d = Path(data_dir) if data_dir else DATA_DIR
    return d / PRODUCTS[product]["file"]


def get_last_date(product: str, data_dir: Path | str | None = None) -> date | None:
    """Lấy ngày của kỳ quay mới nhất đang có trong file local."""
    path = get_local_path(product, data_dir)
    if not path.exists():
        return None
    try:
        if product == "xsmb" or path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list) or not data:
                return None
            best: date | None = None
            for r in data:
                d_str = r.get("date")
                if not d_str:
                    continue
                try:
                    iso = str(d_str).split("T")[0]
                    d = datetime.fromisoformat(iso).date()
                    if best is None or d > best:
                        best = d
                except Exception:
                    pass
            return best
        else:
            df = pl.read_ndjson(path)
            if df.is_empty():
                return None
            max_date = df["date"].max()
            if isinstance(max_date, date):
                return max_date
            return datetime.fromisoformat(str(max_date)).date()
    except Exception as e:
        logger.warning(f"[{product}] Không đọc được file local: {e}")
        return None


def get_record_count(product: str, data_dir: Path | str | None = None) -> int:
    """Đếm tổng số bản ghi kỳ quay trong file local."""
    path = get_local_path(product, data_dir)
    if not path.exists():
        return 0
    try:
        if product == "xsmb" or path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return len(data) if isinstance(data, list) else 0
        else:
            with open(path, "rb") as f:
                return sum(1 for _ in f)
    except Exception:
        return 0


# Lịch quay chi tiết của từng loại xổ số
# days: 0=Thứ 2, 1=Thứ 3, 2=Thứ 4, 3=Thứ 5, 4=Thứ 6, 5=Thứ 7, 6=Chủ Nhật
LOTTERY_SCHEDULES: Dict[str, Dict[str, Any]] = {
    # XSMB: Quay hàng ngày lúc 18h15 - 18h30
    "xsmb": {
        "type": "weekly",
        "draw_time": (18, 30),
        "days": {0, 1, 2, 3, 4, 5, 6},
    },
    # Mega 6/45: Thứ 4, Thứ 6, Chủ Nhật lúc 18h00 - 18h30
    "power_645": {
        "type": "weekly",
        "draw_time": (18, 30),
        "days": {2, 4, 6},
    },
    # Power 6/55: Thứ 3, Thứ 5, Thứ 7 lúc 18h00 - 18h30
    "power_655": {
        "type": "weekly",
        "draw_time": (18, 30),
        "days": {1, 3, 5},
    },
    # Max 3D / 3D+: Thứ 2, Thứ 4, Thứ 6 lúc 18h00 - 18h30
    "3d": {
        "type": "weekly",
        "draw_time": (18, 30),
        "days": {0, 2, 4},
    },
    # Max 3D Pro: Thứ 3, Thứ 5, Thứ 7 lúc 18h00 - 18h30
    "3d_pro": {
        "type": "weekly",
        "draw_time": (18, 30),
        "days": {1, 3, 5},
    },
    # Lotto 5/35: 2 lần/ngày lúc 13h00 và 21h00 (kết thúc ~13h15 và 21h15)
    "power_535": {
        "type": "slots_daily",
        "slots": [(13, 15), (21, 15)],
    },
    # Keno: Quay mỗi 10 phút từ 06h00 đến 21h50 hàng ngày (96 kỳ/ngày)
    "keno": {
        "type": "fast",
        "start": (6, 0),
        "end": (21, 50),
        "interval_minutes": 10,
        "max_draws": 96,
    },
    # Bingo 18: Quay mỗi 6 phút từ 06h05 đến 21h53 hàng ngày (96 kỳ/ngày)
    "bingo18": {
        "type": "fast",
        "start": (6, 5),
        "end": (21, 53),
        "interval_minutes": 6,
        "max_draws": 96,
    },
}


def count_today_records(path: Path | str, today_str: str) -> int:
    """Đếm nhanh số kỳ của ngày cụ thể từ đuôi file mà không cần load toàn bộ file."""
    p = Path(path)
    if not p.exists():
        return 0
    try:
        count = 0
        with open(p, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            buffer_size = min(size, 65536)
            f.seek(size - buffer_size)
            lines = f.read().decode("utf-8", errors="ignore").splitlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    if d.get("date") == today_str:
                        count += 1
                    else:
                        break
                except Exception:
                    continue
        return count
    except Exception:
        return 0


def calculate_expected_missing(
    product: str,
    last_date: date | None,
    data_dir: Path | str | None = None,
) -> float:
    """
    Tính chính xác số kỳ quay lý thuyết bị thiếu so với thời điểm hiện tại
    dựa trên lịch quay cụ thể của từng loại xổ số (ngày trong tuần & giờ mở thưởng).
    """
    if last_date is None:
        return 999.0

    now = pendulum.now("Asia/Ho_Chi_Minh")
    today = now.date()
    today_str = today.isoformat()

    sched = LOTTERY_SCHEDULES.get(product)
    if not sched:
        return 0.0

    stype = sched["type"]
    if stype == "weekly":
        draw_h, draw_m = sched["draw_time"]
        missing = 0
        cur = last_date + timedelta(days=1)
        while cur <= today:
            if cur.weekday() in sched["days"]:
                if cur < today:
                    missing += 1
                else:
                    draw_passed = (now.hour > draw_h or (now.hour == draw_h and now.minute >= draw_m))
                    if draw_passed:
                        missing += 1
            cur += timedelta(days=1)
        return float(missing)

    elif stype == "slots_daily":
        today_passed = sum(
            1 for sh, sm in sched["slots"]
            if (now.hour > sh or (now.hour == sh and now.minute >= sm))
        )
        path = get_local_path(product, data_dir)
        if last_date >= today:
            today_count = count_today_records(path, today_str)
            return float(max(0, today_passed - today_count))
        else:
            days_gap = (today - last_date).days
            intermediate = max(0, days_gap - 1) * len(sched["slots"])
            last_day_count = count_today_records(path, last_date.isoformat())
            last_day_missing = max(0, len(sched["slots"]) - last_day_count) if last_day_count > 0 else 0
            return float(last_day_missing + intermediate + today_passed)

    elif stype == "fast":
        sh, sm = sched["start"]
        eh, em = sched["end"]
        interval = sched["interval_minutes"]
        max_draws = sched["max_draws"]

        if now.hour < sh or (now.hour == sh and now.minute < sm):
            today_expected = 0
        elif now.hour > eh or (now.hour == eh and now.minute >= em):
            today_expected = max_draws
        else:
            elapsed = (now.hour - sh) * 60 + (now.minute - sm)
            today_expected = min(max_draws, max(0, elapsed // interval))

        path = get_local_path(product, data_dir)
        if last_date >= today:
            today_count = count_today_records(path, today_str)
            return float(max(0, today_expected - today_count))
        else:
            days_gap = (today - last_date).days
            past_missing = max(0, days_gap - 1) * max_draws
            last_day_count = count_today_records(path, last_date.isoformat())
            last_day_missing = max(0, max_draws - last_day_count) if last_day_count > 0 else 0
            return float(last_day_missing + past_missing + today_expected)

    return 0.0


def should_sync_from_github(product: str, data_dir: Path | str | None = None) -> bool:
    """Quyết định có nên tải dữ liệu từ GitHub hay không."""
    last_date = get_last_date(product, data_dir)
    expected = calculate_expected_missing(product, last_date, data_dir)
    if product in ("keno", "bingo18"):
        threshold = 40.0
    elif product == "power_535":
        threshold = 4.0
    else:
        threshold = float(GAP_THRESHOLD)
    logger.info(f"[{product}] last_date={last_date} | expected_missing≈{expected:.1f} kỳ (ngưỡng GitHub={threshold:.0f})")
    return expected > threshold


def get_lottery_status(product: str, data_dir: Path | str | None = None) -> dict:
    """Lấy thông tin trạng thái chi tiết của một loại xổ số."""
    if product not in PRODUCTS:
        return {"id": product, "exists": False, "status_text": "Không tồn tại"}

    cfg = PRODUCTS[product]
    path = get_local_path(product, data_dir)
    exists = path.exists()
    records = get_record_count(product, data_dir)
    last_date = get_last_date(product, data_dir)
    expected_missing = calculate_expected_missing(product, last_date, data_dir)

    is_lagging = expected_missing > (1 if product in ("keno", "bingo18") else 0)

    if not exists:
        status_text = "Chưa có file"
        status_type = "missing"
    elif is_lagging:
        status_text = f"⚠ Chậm ~{expected_missing:.0f} kỳ (mới nhất: {last_date})"
        status_type = "lagging"
    else:
        status_text = f"✓ Đã cập nhật ({last_date})"
        status_type = "ok"

    return {
        "id": product,
        "name": cfg["name"],
        "file": cfg["file"],
        "desc": cfg.get("desc", ""),
        "exists": exists,
        "records": records,
        "last_date": last_date.isoformat() if last_date else None,
        "expected_missing": expected_missing,
        "status_text": status_text,
        "status_type": status_type,
    }


def get_all_lottery_statuses(data_dir: Path | str | None = None) -> list[dict]:
    """Lấy trạng thái của toàn bộ 8 loại xổ số."""
    return [get_lottery_status(p, data_dir) for p in PRODUCTS]


# ============================================================
# 1. TẢI DỮ LIỆU TỪ GITHUB
# ============================================================

def download_from_github(product: str, data_dir: Path | str | None = None, custom_url: str | None = None) -> bool:
    """Tải file dữ liệu mới nhất từ repo GitHub về thư mục data/."""
    filename = PRODUCTS[product]["file"]
    if custom_url and custom_url.strip():
        url = custom_url.strip()
    elif product == "xsmb":
        url = XSMB_GITHUB_RAW
    else:
        url = f"{GITHUB_RAW_BASE}/{filename}"

    local_path = get_local_path(product, data_dir)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"[{product}] Đang tải từ GitHub/URL: {url}")
    try:
        resp = requests.get(url, timeout=60)
        if not resp.ok and product == "xsmb":
            # Thử URL dự phòng
            logger.info(f"[xsmb] Thử URL backup: {XSMB_GITHUB_BACKUP}")
            resp = requests.get(XSMB_GITHUB_BACKUP, timeout=60)

        resp.raise_for_status()

        # Backup file cũ nếu tồn tại
        if local_path.exists():
            backup = local_path.with_suffix(local_path.suffix + ".bak")
            try:
                local_path.rename(backup)
                logger.info(f"[{product}] Đã backup → {backup.name}")
            except Exception:
                pass

        local_path.write_bytes(resp.content)
        logger.success(f"[{product}] Đã tải xong ({len(resp.content)/1024:.1f} KB) → {local_path}")
        return True
    except Exception as e:
        logger.error(f"[{product}] Lỗi tải từ GitHub: {e}")
        return False


# ============================================================
# 2. CRAWL DỮ LIỆU MỚI TỪ VIETLOTT & XỔ SỐ
# ============================================================

def parse_power_result(html: str) -> list[dict]:
    """Parse kết quả Power 6/55, 6/45, Lotto 5/35."""
    soup = BeautifulSoup(html, "lxml")
    data = []
    for i, tr in enumerate(soup.select("table tr")):
        if i == 0:
            continue
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        try:
            row = {
                "date": datetime.strptime(tds[0].text.strip(), "%d/%m/%Y").strftime("%Y-%m-%d"),
                "id": tds[1].text.strip(),
                "result": [int(span.text) for span in tds[2].find_all("span") if span.text.strip() not in ("|", "")],
                "process_time": datetime.now().isoformat(),
            }
            data.append(row)
        except Exception:
            continue
    return data


def parse_keno_result(html: str) -> list[dict]:
    """Parse kết quả Keno."""
    soup = BeautifulSoup(html, "lxml")
    data = []
    for i, tr in enumerate(soup.select("table tr")):
        if i == 0:
            continue
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        try:
            td_a = tds[0].find_all("a")
            row = {
                "date": pendulum.from_format(td_a[0].text.strip(), "DD/MM/YYYY").to_date_string(),
                "id": td_a[1].text.strip(),
                "result": [int(span.text) for span in tds[1].find_all("span")],
                "big_small": tds[2].text.strip(),
                "odd_even": tds[3].text.strip(),
            }
            data.append(row)
        except Exception:
            continue
    return data


def parse_3d_result(html: str) -> list[dict]:
    """Parse kết quả Max 3D / Max 3D Pro từ HTML Vietlott."""
    soup = BeautifulSoup(html, "lxml")
    data = []
    for tr in soup.select("table tr"):
        txt = tr.get_text()
        m_id = re.search(r"id=(\d+)", str(tr)) or re.search(r"Kỳ quay:[^\d]*(\d+)", txt)
        m_date = re.search(r"Ngày:[^\d]*(\d{1,2}/\d{1,2}/\d{4})", txt)
        if not m_id or not m_date:
            continue
        draw_id = m_id.group(1).zfill(5)
        try:
            draw_date = pendulum.from_format(m_date.group(1), "DD/MM/YYYY").to_date_string()
        except Exception:
            continue

        res_dict: dict[str, list[str]] = {}
        current_prize: str | None = None
        for el in tr.find_all(["h5", "div"]):
            if el.name == "h5":
                h_text = el.text.strip().lower()
                if "đặc biệt" in h_text or "dac biet" in h_text:
                    current_prize = "Giải Đặc biệt"
                elif "nhất" in h_text or "nhat" in h_text:
                    current_prize = "Giải Nhất"
                elif "nhì" in h_text or "nhi" in h_text:
                    current_prize = "Giải Nhì"
                elif "ba" in h_text:
                    current_prize = "Giải ba"
                else:
                    current_prize = None
                if current_prize and current_prize not in res_dict:
                    res_dict[current_prize] = []
            elif el.name == "div" and "day_so_ket_qua_v2" in el.get("class", []):
                spans = el.find_all("span", class_="bong_tron")
                num_str = "".join(s.text.strip() for s in spans if s.text.strip().isdigit())
                if num_str and current_prize:
                    res_dict[current_prize].append(num_str)

        if res_dict:
            data.append({
                "date": draw_date,
                "id": draw_id,
                "result": res_dict,
            })
    return data


def parse_bingo18_result(html: str) -> list[dict]:
    """Parse kết quả Bingo18."""
    soup = BeautifulSoup(html, "lxml")
    data = []
    process_time = pendulum.now("Asia/Ho_Chi_Minh").to_iso8601_string()
    for i, tr in enumerate(soup.select("table tr")):
        if i == 0:
            continue
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        try:
            td_a = tds[0].find_all("a")
            date_str = pendulum.from_format(td_a[0].text.strip(), "DD/MM/YYYY").to_date_string() if td_a else None
            raw_id = td_a[1].text.strip() if len(td_a) > 1 else tds[0].text.strip()
            draw_id = str(raw_id).replace("#", "").strip()
            res_nums = [int(span.text) for span in tds[1].find_all("span") if span.text.strip().isdigit()]
            if not date_str or len(res_nums) != 3:
                continue
            tot_str = tds[2].text.strip() if len(tds) > 2 else ""
            total_val = int(tot_str) if tot_str.isdigit() else sum(res_nums)
            ls_str = tds[3].text.strip() if len(tds) > 3 else ("Lớn" if total_val > 10 else "Nhỏ")
            row = {
                "date": date_str,
                "id": draw_id,
                "result": res_nums,
                "total": total_val,
                "large_small": ls_str,
                "process_time": process_time,
            }
            data.append(row)
        except Exception:
            continue
    return data


PARSERS = {
    "power_655": parse_power_result,
    "power_645": parse_power_result,
    "power_535": parse_power_result,
    "3d": parse_3d_result,
    "3d_pro": parse_3d_result,
    "keno": parse_keno_result,
    "bingo18": parse_bingo18_result,
}


def fetch_one_page(product: str, page_index: int) -> list[dict]:
    """Gửi request lấy 1 page kết quả từ Vietlott."""
    if product not in PARSERS:
        return []
    cfg = PRODUCTS[product]
    body = cfg["body_template"].copy()
    body["PageIndex"] = page_index

    try:
        resp = requests.post(
            cfg["url"],
            data=json.dumps(body),
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if not resp.ok:
            logger.warning(f"[{product}] Page {page_index} fail: {resp.status_code}")
            return []

        res_json = resp.json()
        html = res_json.get("value", {}).get("HtmlContent", "")
        if not html:
            return []

        parser = PARSERS[product]
        return parser(html)
    except Exception as e:
        logger.error(f"[{product}] Lỗi page {page_index}: {e}")
        return []


def crawl_latest(product: str, pages: int = LATEST_PAGES) -> pl.DataFrame:
    """Crawl N page mới nhất từ Vietlott."""
    if product not in PARSERS:
        return pl.DataFrame()

    logger.info(f"[{product}] Bắt đầu crawl {pages} page mới nhất từ Vietlott...")

    all_rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=PRODUCTS[product]["num_thread"]) as pool:
        results = pool.map(lambda i: fetch_one_page(product, i), range(0, pages))
        for rows in results:
            all_rows.extend(rows)

    if not all_rows:
        logger.warning(f"[{product}] Không lấy được dữ liệu mới từ Vietlott")
        return pl.DataFrame()

    df = pl.DataFrame(all_rows)
    df = df.with_columns(pl.col("id").cast(pl.Utf8)).unique(subset=["id"])
    logger.info(
        f"[{product}] Crawl xong: {len(df)} records | "
        f"date {df['date'].min()} → {df['date'].max()} | "
        f"id {df['id'].min()} → {df['id'].max()}"
    )
    return df


def merge_and_save(product: str, new_df: pl.DataFrame, data_dir: Path | str | None = None) -> int:
    """Merge dữ liệu mới vào file local theo id (không trùng lặp). Trả về số record mới thêm."""
    path = get_local_path(product, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    added_count = 0
    if path.exists() and not new_df.is_empty():
        old_df = pl.read_ndjson(path)
        old_df = old_df.with_columns(pl.col("id").cast(pl.Utf8))

        existing_ids = set(old_df["id"].to_list())
        add_df = new_df.filter(~pl.col("id").is_in(existing_ids))
        added_count = len(add_df)

        if add_df.is_empty():
            logger.info(f"[{product}] Không có record mới để thêm")
            return 0

        final_df = pl.concat([old_df, add_df]).unique(subset=["id"]).sort(["date", "id"])
        logger.info(f"[{product}] Thêm {added_count} record mới → tổng {len(final_df)}")
    else:
        final_df = new_df.unique(subset=["id"]).sort(["date", "id"]) if not new_df.is_empty() else pl.DataFrame()
        added_count = len(final_df)

    if not final_df.is_empty():
        final_df.write_ndjson(path)
        logger.success(f"[{product}] Đã lưu → {path} ({len(final_df)} records)")

    return added_count


# ============================================================
# 3. ĐỒNG BỘ RIÊNG CHO XSMB
# ============================================================

def sync_xsmb(data_dir: Path | str | None = None, force_github: bool = False, custom_url: str | None = None) -> dict:
    """
    Đồng bộ xsmb-2-digits.json: kết hợp GitHub + crawl xoso.com.vn.
    Giữ nguyên quy tắc đồng bộ cũ của chương trình.
    """
    local_path = get_local_path("xsmb", data_dir)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_d = get_last_date("xsmb", data_dir)

    now = pendulum.now("Asia/Ho_Chi_Minh")
    draw_time_passed = (now.hour > 18 or (now.hour == 18 and now.minute >= 45))
    exp_d = now.date() if draw_time_passed else (now.date() - timedelta(days=1))
    gap = (exp_d - local_d).days if local_d else 999

    logger.info(f"[xsmb] local_date={local_d} | expected_date={exp_d} | gap={gap}")

    need_github = force_github or (local_d is None) or (gap >= 2)
    src_info = ""
    data: list[dict] = []

    # Bước 1: Tải từ GitHub nếu thiếu nhiều ngày hoặc chưa có file
    if need_github:
        logger.info(f"[xsmb] Gap={gap} kỳ (hoặc force) → ưu tiên tải từ GitHub/URL")
        if custom_url and custom_url.strip():
            download_from_github("xsmb", data_dir, custom_url=custom_url)
            src_info = f"Custom URL ({custom_url.split('/')[-1]})"
        elif HAS_CORE_XSMB:
            try:
                gh_data, gh_src = fetch_kqxs_json_from_github()
                if local_path.exists():
                    local_list = load_xsmb_list(str(local_path))
                    data = merge_xsmb_2digits_records(local_list, gh_data)
                else:
                    data = gh_data
                src_info = f"GitHub ({gh_src.split('/')[-1]})"
            except Exception as e:
                logger.warning(f"[xsmb] Core GitHub tải lỗi: {e}")
                download_from_github("xsmb", data_dir)
        else:
            download_from_github("xsmb", data_dir)

    # Đọc lại file hiện tại
    if not data and local_path.exists():
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []

    # Bước 2: Crawl bổ sung ngày mới nhất từ xoso.com.vn nếu thiếu
    local_d = get_last_date("xsmb", data_dir)
    if exp_d and (local_d is None or local_d < exp_d):
        logger.info(f"[xsmb] Crawl ngày mới nhất {exp_d} từ xoso.com.vn...")
        rec = None
        if HAS_CORE_XSMB:
            try:
                rec = fetch_xoso_result_2digits(exp_d)
            except Exception as e:
                logger.warning(f"[xsmb] xoso fetch lỗi: {e}")
        else:
            # Fallback parser nhẹ nếu không có module core
            try:
                u = f"https://xoso.com.vn/xsmb-{exp_d.strftime('%d-%m-%Y')}.html"
                r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if r.ok:
                    soup = BeautifulSoup(r.text, "lxml")
                    sp_el = soup.select_one(".special-prize, .prize-special, .gdb")
                    if sp_el:
                        digits = [c for c in sp_el.text if c.isdigit()]
                        if len(digits) >= 2:
                            sp_val = int("".join(digits[-2:]))
                            rec = {"date": exp_d.strftime("%Y-%m-%d"), "special": sp_val}
            except Exception as e:
                logger.warning(f"[xsmb] Crawl fallback lỗi: {e}")

        if rec:
            if HAS_CORE_XSMB:
                data = merge_xsmb_2digits_records(data, [rec])
            else:
                data_dict = {str(r.get("date", "")).split("T")[0]: r for r in data}
                data_dict[str(rec.get("date", "")).split("T")[0]] = rec
                data = sorted(data_dict.values(), key=lambda x: str(x.get("date", "")))
            src_info += (" + " if src_info else "") + f"xoso.com.vn ({exp_d})"
            logger.success(f"[xsmb] Đã crawl thành công ngày {exp_d}")

    # Ghi file
    if data:
        tmp = local_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        tmp.replace(local_path)
        final_d = get_last_date("xsmb", data_dir)
        msg = f"Đồng bộ thành công XSMB: {len(data):,} kỳ (mới nhất: {final_d}) [{src_info or 'Local'}]"
        logger.success(f"[xsmb] {msg}")
        return {
            "success": True,
            "status": "success",
            "product": "xsmb",
            "name": PRODUCTS["xsmb"]["name"],
            "records": len(data),
            "total_records": len(data),
            "last_date": final_d.isoformat() if final_d else None,
            "latest_date": final_d.isoformat() if final_d else None,
            "message": msg,
        }
    else:
        err_msg = "Không có dữ liệu XSMB nào được cập nhật."
        logger.error(f"[xsmb] {err_msg}")
        return {
            "success": False,
            "product": "xsmb",
            "name": PRODUCTS["xsmb"]["name"],
            "records": 0,
            "last_date": None,
            "message": err_msg,
        }


# ============================================================
# HÀM ĐỒNG BỘ CHÍNH
# ============================================================

def smart_sync(
    product: str,
    force_github: bool = False,
    pages: int = LATEST_PAGES,
    data_dir: Path | str | None = None,
    custom_url: str | None = None,
) -> dict:
    """
    Đồng bộ thông minh 1 sản phẩm xổ số.
    """
    if product not in PRODUCTS:
        msg = f"Sản phẩm không hỗ trợ: {product}. Các lựa chọn: {list(PRODUCTS.keys())}"
        logger.error(msg)
        return {"success": False, "product": product, "message": msg}

    if product == "xsmb":
        return sync_xsmb(data_dir=data_dir, force_github=force_github, custom_url=custom_url)

    logger.info(f"{'='*60}")
    logger.info(f"Bắt đầu smart_sync: {product} ({PRODUCTS[product]['name']})")

    # Bước 1: Quyết định có tải từ GitHub không
    need_github = force_github or (custom_url and custom_url.strip()) or should_sync_from_github(product, data_dir)
    if need_github:
        logger.info(f"[{product}] Gap lớn (hoặc force/custom URL) → ưu tiên tải từ GitHub/URL")
        ok = download_from_github(product, data_dir, custom_url=custom_url)
        if not ok:
            logger.warning(f"[{product}] Tải GitHub/URL thất bại, vẫn tiếp tục crawl Vietlott")
    else:
        logger.info(f"[{product}] Gap nhỏ → bỏ qua GitHub, chỉ crawl phần mới")

    # Bước 2: Crawl phần mới nhất từ Vietlott
    crawl_pages = pages
    if product in ("keno", "bingo18"):
        exp = calculate_expected_missing(product, get_last_date(product, data_dir), data_dir)
        if exp > 0:
            import math
            needed = int(math.ceil(exp / 6)) + 2
            crawl_pages = max(pages, min(20, needed))
    new_df = crawl_latest(product, pages=crawl_pages)

    # Bước 3: Merge & lưu
    added = merge_and_save(product, new_df, data_dir)

    # Thống kê cuối
    last = get_last_date(product, data_dir)
    total_recs = get_record_count(product, data_dir)
    msg = f"Hoàn tất {PRODUCTS[product]['name']}: thêm {added} kỳ mới, tổng {total_recs:,} kỳ (mới nhất: {last})"
    logger.info(f"[{product}] {msg}")

    return {
        "success": True,
        "product": product,
        "name": PRODUCTS[product]["name"],
        "records": total_recs,
        "added": added,
        "last_date": last.isoformat() if last else None,
        "message": msg,
    }


def smart_sync_all(
    force_github: bool = False,
    pages: int = LATEST_PAGES,
    data_dir: Path | str | None = None,
    products: list[str] | None = None,
) -> dict[str, dict]:
    """
    Đồng bộ danh sách sản phẩm hoặc tất cả sản phẩm.
    """
    target_products = products or list(PRODUCTS.keys())
    results = {}
    for product in target_products:
        try:
            res = smart_sync(product, force_github=force_github, pages=pages, data_dir=data_dir)
            results[product] = res
        except Exception as e:
            logger.exception(f"[{product}] Lỗi không mong muốn: {e}")
            results[product] = {"success": False, "product": product, "message": str(e)}
    return results


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Smart sync dữ liệu KQXS Vietlott & XSMB (tải GitHub khi gap lớn + crawl phần mới)"
    )
    parser.add_argument(
        "product",
        nargs="?",
        default="all",
        help=f"Tên sản phẩm hoặc 'all' (các sản phẩm: {', '.join(PRODUCTS.keys())})",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Thư mục lưu data (mặc định: data/)",
    )
    parser.add_argument(
        "--force-github",
        action="store_true",
        help="Bắt buộc tải lại từ GitHub dù gap nhỏ",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=LATEST_PAGES,
        help=f"Số page mới nhất cần crawl từ Vietlott (mặc định: {LATEST_PAGES})",
    )

    args = parser.parse_args()

    if args.data_dir:
        set_data_dir(args.data_dir)

    if args.product == "all":
        smart_sync_all(force_github=args.force_github, pages=args.pages, data_dir=args.data_dir)
    else:
        smart_sync(args.product, force_github=args.force_github, pages=args.pages, data_dir=args.data_dir)