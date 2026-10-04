# -*- coding: utf-8 -*-
# Module: modules/trial_play.py
# Contains: SquareQLabel, SimulationWorker, VnMoneySpinBox, TrialPlayTab

import os
import sys
import copy
import logging
import datetime
import random
from pathlib import Path

try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
        QLabel, QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QScrollArea, QTextEdit, QPlainTextEdit, QProgressBar,
        QListWidget, QListWidgetItem, QMessageBox, QSizePolicy, QFrame,
        QComboBox, QApplication, QRadioButton, QButtonGroup, QSplitter,
        QDialog, QFileDialog, QLineEdit, QTabWidget, QCalendarWidget,
        QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem,
        QStatusBar, QTextBrowser
    )
    from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal, pyqtSlot, QThread, QSize, QDate, QRect
    from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPalette, QIcon, QPixmap, QIntValidator, QDoubleValidator, QTextCursor
except ImportError:
    pass


class SquareQLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(300, 300)

    def heightForWidth(self, width: int) -> int:
        return 100

    def sizeHint(self) -> QSize:
        return QSize(100, 100)


class SimulationWorker(QObject):
    """Worker thread để chạy giả lập chơi thử."""
    progress_signal = pyqtSignal(int, int) 
    day_result_signal = pyqtSignal(dict)   
    finished_signal = pyqtSignal(dict)     
    error_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self, algo_instances, history_data, result_map, config, bet_strategies):
        super().__init__()
        self.algo_instances = algo_instances 
        self.history_data = history_data
        self.result_map = result_map
        self.config = config
        self.bet_strategies = bet_strategies
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        start_date = self.config['start_date']
        
        dates_to_run = []
        available_dates = sorted([d for d in self.result_map.keys() if d >= start_date])
        
        if self.config.get('mode') == 'range':
            end_date = self.config['end_date']
            current_d = start_date
            while current_d <= end_date:
                next_day = current_d + datetime.timedelta(days=1)
                if next_day in self.result_map:
                    dates_to_run.append(current_d)
                current_d += datetime.timedelta(days=1)
                
        elif self.config.get('mode') == 'count':
            limit = self.config['num_draws']
            count = 0
            for d in available_dates:
                if count >= limit: break
                next_day = d + datetime.timedelta(days=1)
                if next_day in self.result_map:
                    dates_to_run.append(d)
                    count += 1

        total_days = len(dates_to_run)
        if total_days == 0:
            self.error_signal.emit("Không tìm thấy kỳ quay phù hợp (Cần có dữ liệu ngày kế tiếp để đối chiếu).")
            return

        summary = {
            'total_days': total_days,
            'initial_balance': self.config['initial_capital'],
            'final_balance': 0,
            'wins': 0,
            'losses': 0,
            'history': []
        }
        
        current_balance = self.config['initial_capital']
        sorted_history = sorted(self.history_data, key=lambda x: x['date'])
        
        stop_completely = False 

        for idx, predict_date in enumerate(dates_to_run):
            if not self._is_running or stop_completely: break
            
            if current_balance < 1000: 
                self.log_signal.emit(f"<div style='color:red; font-weight:bold; border:1px solid red; padding:5px; margin:5px;'>⛔ Dừng chơi từ ngày {predict_date.strftime('%d/%m/%Y')}: ĐÃ HẾT VỐN!</div>")
                break

            current_history = [x for x in sorted_history if x['date'] <= predict_date]
            next_day = predict_date + datetime.timedelta(days=1)
            
            combined_scores = {} 
            valid_algo_run = False
            
            for algo in self.algo_instances:
                try:
                    preds = algo.predict(next_day, current_history)
                    if preds:
                        valid_algo_run = True
                        for num, score in preds.items():
                            combined_scores[num] = combined_scores.get(num, 0) + score
                except Exception: pass
            
            if not valid_algo_run or not combined_scores:
                self.log_signal.emit(f"Ngày {predict_date}: Thuật toán không trả về kết quả.")
                self.progress_signal.emit(idx + 1, total_days)
                continue

            sorted_preds = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)
            ranked_numbers = [num for num, score in sorted_preds]

            actual_result = self.result_map[next_day]
            actual_lotos = self._get_lotos_from_result(actual_result) 
            actual_special = self._get_special_loto(actual_result)
            from collections import Counter
            loto_counts = Counter(actual_lotos)

            day_total_cost = 0; day_total_win = 0; day_details = []
            
            for strategy in self.bet_strategies:
                if stop_completely: break
                
                positions = strategy['positions'] 
                bet_type = strategy['type']
                points = strategy['points']
                unit_cost = points * strategy['cost_per_point']
                unit_win_base = points * strategy['win_per_point']
                
                target_numbers = []
                valid_indices = True
                for pos in positions:
                    idx_val = pos - 1
                    if 0 <= idx_val < len(ranked_numbers):
                        target_numbers.append(ranked_numbers[idx_val])
                    else: valid_indices = False
                
                if not valid_indices or not target_numbers: continue

                if bet_type in ['Đề', 'Lô']:
                    for num in target_numbers:
                        if current_balance >= unit_cost:
                            current_balance -= unit_cost
                            day_total_cost += unit_cost
                            
                            is_win = False; win_val = 0; nhay_str = ""
                            if bet_type == 'Đề':
                                if num == actual_special: is_win = True; win_val = unit_win_base
                            else:
                                hits = loto_counts.get(num, 0)
                                if hits > 0: is_win = True; win_val = unit_win_base * hits
                                if hits > 1: nhay_str = f" ({hits} nháy)"
                            
                            current_balance += win_val
                            day_total_win += win_val
                            
                            w_str = f"+{win_val:,.0f}" if is_win else "0"
                            c_style = "color:green; font-weight:bold" if is_win else "color:#555"
                            stt = "🎯 TRÚNG" if is_win else "Trượt"
                            day_details.append(f"<span style='{c_style}'>[{bet_type}] {num}: {stt}{nhay_str} (Chi {unit_cost:,.0f}, Thu {w_str})</span>")
                        else:
                            day_details.append(f"<span style='color:red; font-weight:bold'>⛔ Dừng tại số {num}: Không đủ {unit_cost:,.0f}đ (Số dư: {current_balance:,.0f}đ)</span>")
                            stop_completely = True
                            break 
                    if stop_completely: break

                elif bet_type.startswith('Xiên'):
                    if current_balance >= unit_cost:
                        current_balance -= unit_cost
                        day_total_cost += unit_cost
                        
                        present_numbers = [n for n in target_numbers if n in loto_counts]
                        is_win = (len(present_numbers) == len(target_numbers))
                        
                        win_val = 0; detail_win_str = ""
                        if is_win:
                            multiplier = 1; hits_detail = []
                            for n in target_numbers: 
                                cnt = loto_counts[n]; multiplier *= cnt
                                hits_detail.append(f"{n}({cnt})")
                            win_val = unit_win_base * multiplier
                            detail_win_str = ", ".join(hits_detail)
                        
                        current_balance += win_val
                        day_total_win += win_val
                        
                        nums_str = "-".join(target_numbers)
                        w_str = f"+{win_val:,.0f}" if is_win else "0"
                        c_style = "color:green; font-weight:bold" if is_win else "color:#555"
                        stt = f"🎯 TRÚNG [{detail_win_str}]" if is_win else "Trượt"
                        day_details.append(f"<span style='{c_style}'>[{bet_type}] Bộ {nums_str}: {stt} (Chi {unit_cost:,.0f}, Thu {w_str})</span>")
                    else:
                        nums_str = "-".join(target_numbers)
                        day_details.append(f"<span style='color:red; font-weight:bold'>⛔ Dừng tại Bộ {nums_str}: Không đủ {unit_cost:,.0f}đ (Số dư: {current_balance:,.0f}đ)</span>")
                        stop_completely = True
                        break

            profit = day_total_win - day_total_cost
            if profit > 0: summary['wins'] += 1
            elif profit < 0: summary['losses'] += 1
            
            day_info = {
                'date': predict_date.strftime('%d/%m/%Y'),
                'next_day': next_day.strftime('%d/%m/%Y'),
                'numbers': day_details,
                'cost': day_total_cost,
                'win': day_total_win,
                'balance': current_balance
            }
            self.day_result_signal.emit(day_info)
            self.progress_signal.emit(idx + 1, total_days)

        summary['final_balance'] = current_balance
        self.finished_signal.emit(summary)

    def _get_lotos_from_result(self, result_dict):
        lotos = []
        ignore_keys = {'date', '_id', 'source', 'day_of_week', 'sign', 'created_at', 'updated_at', 'province_name', 'province_id'}
        for k, v in result_dict.items():
            if k in ignore_keys: continue
            vals = v if isinstance(v, list) else [v]
            for val in vals:
                s = str(val).strip()
                if len(s) >= 2 and s[-2:].isdigit(): lotos.append(s[-2:])
        return lotos

    def _get_special_loto(self, result_dict):
        val = result_dict.get('special', result_dict.get('dac_biet'))
        if val:
            s = str(val).strip()
            if len(s) >= 2 and s[-2:].isdigit(): return s[-2:]
        return None


class VnMoneySpinBox(QSpinBox):
    """SpinBox tùy chỉnh để hiển thị dấu chấm phân cách hàng nghìn."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setGroupSeparatorShown(True)

    def textFromValue(self, value):
        return "{:,}".format(value).replace(",", ".")

    def valueFromText(self, text):
        clean_text = text.replace(".", "")
        try:
            return int(clean_text)
        except ValueError:
            return 0


class TrialPlayTab(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.simulation_thread = None
        self.simulation_worker = None
        
        self.default_prices = {
            'Đề': {'cost': 1, 'win': 70}, 
            'Lô': {'cost': 22, 'win': 80},
            'Xiên 2': {'cost': 22, 'win': 220},
            'Xiên 3': {'cost': 22, 'win': 880},
            'Xiên 4': {'cost': 22, 'win': 8800},
        }
        
        self.init_ui()

    def showEvent(self, event):
        """Auto reload thuật toán khi mở tab"""
        self.refresh_algos()
        super().showEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        top_group = QGroupBox("Cấu Hình Chạy Thử")
        top_layout = QGridLayout(top_group)
        
        top_layout.addWidget(QLabel("Vốn ban đầu:"), 0, 0)
        self.capital_spin = VnMoneySpinBox()
        self.capital_spin.setRange(100, 1000000000)
        self.capital_spin.setValue(10000)
        self.capital_spin.setSuffix(".000 đ")
        top_layout.addWidget(self.capital_spin, 0, 1)
        
        btn_caps = QHBoxLayout()
        for v, l in [(5000, "5Tr"), (10000, "10Tr"), (50000, "50Tr")]:
            b = QPushButton(l)
            b.clicked.connect(lambda _, val=v: self.capital_spin.setValue(val))
            btn_caps.addWidget(b)
        top_layout.addLayout(btn_caps, 0, 2)

        self.radio_range = QRadioButton("Theo khoảng ngày")
        self.radio_count = QRadioButton("Theo số kỳ quay (gần nhất)")
        self.radio_count.setChecked(True)
        
        self.radio_range.toggled.connect(self.update_date_mode)
        self.radio_count.toggled.connect(self.update_date_mode)

        r_layout = QHBoxLayout()
        r_layout.addWidget(self.radio_range)
        r_layout.addWidget(self.radio_count)
        top_layout.addLayout(r_layout, 1, 0, 1, 3)
        
        self.date_stack = QtWidgets.QStackedWidget()
        
        p_range = QWidget()
        l_range = QHBoxLayout(p_range)
        l_range.setContentsMargins(0,0,0,0)
        self.d_from = QLineEdit(); b_from = QPushButton("📅")
        self.d_to = QLineEdit(); b_to = QPushButton("📅")
        b_from.clicked.connect(lambda: self.main_app.show_calendar_dialog_qt(self.d_from))
        b_to.clicked.connect(lambda: self.main_app.show_calendar_dialog_qt(self.d_to))
        l_range.addWidget(QLabel("Từ:")); l_range.addWidget(self.d_from); l_range.addWidget(b_from)
        l_range.addWidget(QLabel("Đến:")); l_range.addWidget(self.d_to); l_range.addWidget(b_to)
        
        p_count = QWidget()
        l_count = QHBoxLayout(p_count)
        l_count.setContentsMargins(0,0,0,0)
        self.d_start_cnt = QLineEdit(); b_start_cnt = QPushButton("📅")
        b_start_cnt.clicked.connect(lambda: self.main_app.show_calendar_dialog_qt(self.d_start_cnt))
        self.sp_draws = QSpinBox()
        self.sp_draws.setRange(1, 1000000)
        self.sp_draws.setValue(10)
        self.sp_draws.setSuffix(" kỳ")
        l_count.addWidget(QLabel("Bắt đầu từ:")); l_count.addWidget(self.d_start_cnt); l_count.addWidget(b_start_cnt)
        l_count.addWidget(QLabel("Số kỳ chạy:")); l_count.addWidget(self.sp_draws)
        
        self.date_stack.addWidget(p_range)
        self.date_stack.addWidget(p_count)
        self.update_date_mode() 
        top_layout.addWidget(self.date_stack, 2, 0, 1, 3)

        algo_group = QGroupBox("Chọn Thuật Toán")
        algo_layout = QVBoxLayout(algo_group)
        self.algo_list = QListWidget()
        self.algo_list.setToolTip("Chọn thuật toán để sử dụng dự đoán")
        algo_layout.addWidget(self.algo_list)
        
        lbl_hint = QLabel("<i>(Tự động cập nhật từ thư mục algorithms)</i>")
        lbl_hint.setStyleSheet("color: gray; font-size: 10px;")
        lbl_hint.setAlignment(Qt.AlignCenter)
        algo_layout.addWidget(lbl_hint)
        
        split_layout = QHBoxLayout()
        split_layout.addWidget(top_group, 60)
        split_layout.addWidget(algo_group, 40)
        layout.addLayout(split_layout)
        
        strat_group = QGroupBox("Cấu Hình Cách Chơi")
        strat_layout = QVBoxLayout(strat_group)
        
        self.strat_table = QtWidgets.QTableWidget(0, 4)
        self.strat_table.setHorizontalHeaderLabels(["Loại Hình", "Vị Trí (Rank)", "Điểm Cược", "Thao tác"])
        self.strat_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        strat_layout.addWidget(self.strat_table)
        
        note = QLabel("<i>* Vd: '1, 2' chọn Top 1 và Top 2. Xiên cần đủ số lượng vị trí khác nhau.</i>")
        note.setStyleSheet("color: gray; font-size: 11px;")
        strat_layout.addWidget(note)

        s_btns = QHBoxLayout()
        btn_add = QPushButton("➕ Thêm Cược")
        btn_add.clicked.connect(self.add_strategy_row)
        btn_price = QPushButton("⚙️ Cài Đặt Tỉ Lệ Thưởng")
        btn_price.clicked.connect(self.toggle_price)
        s_btns.addWidget(btn_add); s_btns.addWidget(btn_price); s_btns.addStretch()
        strat_layout.addLayout(s_btns)
        
        self.price_frame = QFrame()
        self.price_frame.setVisible(False)
        self.price_frame.setFrameShape(QFrame.StyledPanel)
        pf_layout = QGridLayout(self.price_frame)
        
        self.price_inputs = {}
        row = 0
        for k in ['Đề', 'Lô', 'Xiên 2', 'Xiên 3', 'Xiên 4']:
            pf_layout.addWidget(QLabel(k), row, 0)
            c = QDoubleSpinBox(); c.setRange(0,9999); c.setValue(self.default_prices[k]['cost']); c.setPrefix("Mua: ")
            w = QDoubleSpinBox(); w.setRange(0,99999); w.setValue(self.default_prices[k]['win']); w.setPrefix("Ăn: ")
            pf_layout.addWidget(c, row, 1); pf_layout.addWidget(w, row, 2)
            self.price_inputs[k] = {'cost': c, 'win': w}
            row+=1
            
        price_action_layout = QHBoxLayout()
        btn_save_price = QPushButton("💾 Lưu Cấu Hình")
        btn_save_price.clicked.connect(self.save_price_config)
        btn_save_price.setStyleSheet("font-weight: bold; color: green;")
        btn_reset_price = QPushButton("↩️ Reset Mặc Định")
        btn_reset_price.clicked.connect(self.reset_price_config)
        price_action_layout.addWidget(btn_save_price)
        price_action_layout.addWidget(btn_reset_price)
        pf_layout.addLayout(price_action_layout, row, 0, 1, 3)
        strat_layout.addWidget(self.price_frame)
        layout.addWidget(strat_group)
        
        ctrl = QHBoxLayout()
        self.btn_run = QPushButton("▶️ CHẠY MÔ PHỎNG")
        self.btn_run.setObjectName("AccentButton")
        self.btn_run.setMinimumHeight(40)
        self.btn_run.clicked.connect(self.start_simulation)
        self.btn_stop = QPushButton("⏹️ DỪNG")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_simulation)
        ctrl.addWidget(self.btn_run); ctrl.addWidget(self.btn_stop)
        layout.addLayout(ctrl)
        
        self.lbl_progress_text = QLabel("Sẵn sàng (0/0)")
        self.lbl_progress_text.setAlignment(Qt.AlignCenter)
        self.lbl_progress_text.setStyleSheet("font-weight: bold; color: #333; margin-bottom: 2px;")
        layout.addWidget(self.lbl_progress_text)

        self.p_bar = QProgressBar()
        self.p_bar.setTextVisible(False)
        self.p_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #f8f9fa;
                height: 15px;
            }
            QProgressBar::chunk {
                background-color: #28a745; 
            }
        """)
        self.p_bar.setValue(0)
        layout.addWidget(self.p_bar)
        
        self.log_view = QTextBrowser()
        layout.addWidget(self.log_view)
        
        self.lbl_sum = QLabel("")
        self.lbl_sum.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_sum)

    def update_date_mode(self):
        if self.radio_range.isChecked():
            self.date_stack.setCurrentIndex(0)
        elif self.radio_count.isChecked():
            self.date_stack.setCurrentIndex(1)

    def toggle_price(self):
        self.price_frame.setVisible(not self.price_frame.isVisible())

    def save_price_config(self):
        self.price_frame.setVisible(False)
        QMessageBox.information(self, "Đã Lưu", "Đã cập nhật tỉ lệ thưởng cho lần chạy tiếp theo!")

    def reset_price_config(self):
        confirm = QMessageBox.question(self, "Xác nhận", "Bạn có chắc muốn reset về tỉ lệ mặc định?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            for k, v in self.default_prices.items():
                if k in self.price_inputs:
                    self.price_inputs[k]['cost'].setValue(v['cost'])
                    self.price_inputs[k]['win'].setValue(v['win'])

    def add_strategy_row(self):
        r = self.strat_table.rowCount()
        self.strat_table.insertRow(r)
        cb = QComboBox(); cb.addItems(['Đề', 'Lô', 'Xiên 2', 'Xiên 3', 'Xiên 4'])
        self.strat_table.setCellWidget(r, 0, cb)
        le = QLineEdit(); le.setPlaceholderText("Vd: 1, 2")
        self.strat_table.setCellWidget(r, 1, le)
        sb = QSpinBox(); sb.setRange(1, 10000); sb.setValue(10)
        self.strat_table.setCellWidget(r, 2, sb)
        bn = QPushButton("Xóa"); bn.setStyleSheet("color: red")
        bn.clicked.connect(lambda: self.strat_table.removeRow(self.strat_table.currentRow()))
        self.strat_table.setCellWidget(r, 3, bn)

    def refresh_algos(self):
        """Cập nhật thuật toán thông minh, lọc file rác."""
        checked_items = set()
        for i in range(self.algo_list.count()):
            item = self.algo_list.item(i)
            if item.checkState() == Qt.Checked: checked_items.add(item.text())

        self.algo_list.clear()
        found_algos = set()
        
        if hasattr(self.main_app, 'algorithms') and self.main_app.algorithms:
            for name in self.main_app.algorithms.keys():
                found_algos.add(name)
        else:
            try:
                algo_dir = os.path.join(os.getcwd(), 'algorithms')
                if os.path.exists(algo_dir):
                    for f in os.listdir(algo_dir):
                        full_path = os.path.join(algo_dir, f)
                        if not os.path.isfile(full_path): continue
                        if not f.endswith('.py'): continue
                        if f == '__init__.py': continue
                        if f.startswith('template') or f.startswith('example') or f.startswith('test_'): continue
                        name = f[:-3] 
                        found_algos.add(name)
            except Exception: pass

        for name in sorted(list(found_algos)):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if name in checked_items: item.setCheckState(Qt.Checked)
            else: item.setCheckState(Qt.Unchecked)
            self.algo_list.addItem(item)
            
        if self.algo_list.count() == 0: self.algo_list.addItem("Không tìm thấy thuật toán nào!")

    def start_simulation(self):
        selected_algos = []
        for i in range(self.algo_list.count()):
            it = self.algo_list.item(i)
            if it.checkState() == Qt.Checked: selected_algos.append(it.text())
        
        if not selected_algos:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn ít nhất 1 thuật toán.")
            return

        algo_instances = []
        for name in selected_algos:
            inst = self.main_app.algorithm_instances.get(name)
            if inst: algo_instances.append(inst)
        
        if not algo_instances and len(selected_algos) > 0:
             QMessageBox.warning(self, "Lưu ý", "Các thuật toán chưa được khởi tạo đầy đủ. Vui lòng qua tab 'Thuật toán' để kiểm tra.")
             return

        if not algo_instances:
            QMessageBox.warning(self, "Lỗi", "Không thể tải instance thuật toán.")
            return

        try:
            config = {'initial_capital': self.capital_spin.value() * 1000}
            
            if self.radio_range.isChecked():
                config['mode'] = 'range'
                s = self.d_from.text(); e = self.d_to.text()
                if not s or not e: raise ValueError("Chưa chọn ngày.")
                config['start_date'] = datetime.datetime.strptime(s, '%d/%m/%Y').date()
                config['end_date'] = datetime.datetime.strptime(e, '%d/%m/%Y').date()
                if config['start_date'] > config['end_date']: raise ValueError("Ngày bắt đầu > Ngày kết thúc.")
            else:
                config['mode'] = 'count'
                s = self.d_start_cnt.text()
                if not s: raise ValueError("Chưa chọn ngày bắt đầu.")
                config['start_date'] = datetime.datetime.strptime(s, '%d/%m/%Y').date()
                config['num_draws'] = self.sp_draws.value()

            strategies = []
            rows = self.strat_table.rowCount()
            if rows == 0: raise ValueError("Chưa thêm cách chơi.")
            
            for r in range(rows):
                w_type = self.strat_table.cellWidget(r, 0); w_pos = self.strat_table.cellWidget(r, 1); w_pts = self.strat_table.cellWidget(r, 2)
                if not (w_type and w_pos and w_pts): continue
                
                b_type = w_type.currentText(); pos_str = w_pos.text(); points = w_pts.value()
                try: positions = [int(x.strip()) for x in pos_str.split(',') if x.strip().isdigit()]
                except: raise ValueError(f"Dòng {r+1}: Vị trí nhập sai định dạng.")
                if not positions: raise ValueError(f"Dòng {r+1}: Chưa nhập vị trí.")
                
                if len(positions) != len(set(positions)):
                    raise ValueError(f"Dòng {r+1}: Các vị trí chọn phải KHÁC NHAU (không được nhập trùng).")

                if b_type.startswith('Xiên'):
                    req = int(b_type.split(' ')[1])
                    if len(positions) != req: raise ValueError(f"Dòng {r+1}: {b_type} yêu cầu chọn đúng {req} vị trí.")
                
                strategies.append({
                    'type': b_type, 'positions': positions, 'points': points,
                    'cost_per_point': self.price_inputs[b_type]['cost'].value() * 1000,
                    'win_per_point': self.price_inputs[b_type]['win'].value() * 1000
                })

        except ValueError as e: QMessageBox.warning(self, "Lỗi nhập liệu", str(e)); return
        except Exception as e: QMessageBox.warning(self, "Lỗi", str(e)); return

        self.log_view.clear()
        self.log_view.append(f"<b>Khởi chạy giả lập với {len(algo_instances)} thuật toán...</b>")
        self.p_bar.setValue(0); 
        self.lbl_progress_text.setText("Đang khởi tạo...")
        self.lbl_sum.setText("Đang chạy...")
        
        self.simulation_thread = QThread()
        history = self.main_app.results
        res_map = {i['date']: i['result'] for i in history}
        
        self.simulation_worker = SimulationWorker(algo_instances, history, res_map, config, strategies)
        self.simulation_worker.moveToThread(self.simulation_thread)
        self.simulation_worker.progress_signal.connect(self.update_progress_bar)
        self.simulation_worker.day_result_signal.connect(self.display_day_result)
        self.simulation_worker.log_signal.connect(self.log_view.append)
        self.simulation_worker.error_signal.connect(lambda s: QMessageBox.warning(self, "Lỗi", s))
        self.simulation_worker.finished_signal.connect(self.on_finished)
        self.simulation_thread.started.connect(self.simulation_worker.run)
        self.simulation_thread.finished.connect(self.simulation_thread.deleteLater)
        self.btn_run.setEnabled(False); self.btn_stop.setEnabled(True)
        self.simulation_thread.start()

    def stop_simulation(self):
        if self.simulation_worker: self.simulation_worker.stop()

    def update_progress_bar(self, current, total):
        self.p_bar.setMaximum(total)
        self.p_bar.setValue(current)
        pct = int((current/total)*100) if total > 0 else 0
        self.lbl_progress_text.setText(f"Tiến độ: {current}/{total} ({pct}%)")

    def display_day_result(self, info):
        p = info['win'] - info['cost']
        c = "green" if p > 0 else "red" if p < 0 else "black"
        html = f"<div style='border-bottom:1px dashed #ccc; padding:4px;'><b>{info['date']}</b>: <span style='color:{c}'>{'+' if p>0 else ''}{p:,.0f}</span> (Số dư: {info['balance']:,.0f})<br>"
        for det in info['numbers']: html += f"&nbsp;&nbsp;{det}<br>"
        html += "</div>"
        self.log_view.append(html); self.log_view.moveCursor(QtGui.QTextCursor.End)

    def on_finished(self, sm):
        self.btn_run.setEnabled(True); self.btn_stop.setEnabled(False)
        self.simulation_thread.quit()
        profit = sm['final_balance'] - sm['initial_balance']
        pct = (profit / sm['initial_balance'] * 100) if sm['initial_balance'] > 0 else 0
        stt = "THẮNG LỚN" if pct > 20 else "CÓ LÃI" if pct > 0 else "THUA LỖ"
        color = "green" if profit > 0 else "red"
        msg = f"KẾT QUẢ: {stt} ({pct:.2f}%) | Lãi/Lỗ: {profit:,.0f} đ"
        self.lbl_sum.setText(msg); self.lbl_sum.setStyleSheet(f"font-size:16px; font-weight:bold; color:{color}; border:2px solid {color}; padding:8px; border-radius:4px;")
        self.log_view.append(f"<br><center><b>{msg}</b></center>")
        self.lbl_progress_text.setText(f"Hoàn thành ({sm['total_days']}/{sm['total_days']})")
