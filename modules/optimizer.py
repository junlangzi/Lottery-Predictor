# -*- coding: utf-8 -*-
# Module: modules/optimizer.py
# Contains: EvaluationWorker, AlgorithmEvaluationTab, OptimizerEmbedded

import os
import re
import ast
import sys
import copy
import json
import time
import math
import shutil
import logging
import datetime
import inspect
import random
import threading
import queue
import itertools
from pathlib import Path
from collections import Counter
from importlib import reload, util

try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
        QLabel, QLineEdit, QPushButton, QTabWidget, QGroupBox, QComboBox,
        QSpinBox, QDoubleSpinBox, QCheckBox, QScrollArea, QTextEdit,
        QProgressBar, QListWidget, QListWidgetItem, QDialog, QMessageBox,
        QFileDialog, QSplitter, QSizePolicy, QFrame, QRadioButton,
        QButtonGroup, QPlainTextEdit, QApplication, QCalendarWidget, QMainWindow
    )
    from PyQt5.QtCore import Qt, QTimer, QDate, QObject, pyqtSignal, QThread, pyqtSlot
    from PyQt5.QtGui import QFont, QColor, QBrush, QFontMetrics, QTextCursor, QIntValidator, QDoubleValidator, QRegularExpressionValidator
    from PyQt5.QtCore import QRegularExpression
except ImportError:
    pass

try:
    from algorithms.base import BaseAlgorithm
except ImportError:
    BaseAlgorithm = None

try:
    from modules.json_bundle import JsonBundleAlgorithm, is_json_bundle_file
except ImportError:
    JsonBundleAlgorithm = None
    is_json_bundle_file = lambda p: False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from modules.gemini_tab import AlgorithmGeminiBuilderTab
except ImportError:
    AlgorithmGeminiBuilderTab = None

try:
    if __import__('sys').version_info < (3, 9):
        import astor
        HAS_ASTOR = True
    else:
        HAS_ASTOR = False
except ImportError:
    HAS_ASTOR = False

# Loggers (mirrors main.py setup)
optimizer_logger = logging.getLogger("OptimizerQt")
main_logger = logging.getLogger("LotteryAppQt")

class EvaluationWorker(QObject):
    """Worker chạy nền để đánh giá hiệu suất thuật toán."""
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, algo_instances, results_data, num_periods):
        super().__init__()
        self.algo_instances = algo_instances
        self.results_data = results_data
        self.num_periods = num_periods
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            if not self.results_data or len(self.results_data) < 30:
                self.error_signal.emit("Dữ liệu lịch sử không đủ để đánh giá (cần ít nhất 30 ngày).")
                return

            sorted_data = sorted(self.results_data, key=lambda x: x['date'])
            current_end_date = sorted_data[-1]['date']
            
            periods = []
            
            for i in range(self.num_periods):
                period_entries = []
                temp_data = [x for x in sorted_data if x['date'] <= current_end_date]
                if len(temp_data) < 30: break 
                
                chunk = temp_data[-30:]
                if not chunk: break
                
                periods.append({
                    'index': i + 1,
                    'start_date': chunk[0]['date'],
                    'end_date': chunk[-1]['date'],
                    'entries': chunk
                })
                
                current_idx = sorted_data.index(chunk[0])
                if current_idx > 0:
                    current_end_date = sorted_data[current_idx - 1]['date']
                else:
                    break

            total_days_to_calc = sum(len(p['entries']) for p in periods)
            current_calc_count = 0
            
            stats_per_period = {}
            rank_frequency = {i: 0 for i in range(100)}
            
            history_cache = {}
            for i, r in enumerate(sorted_data):
                history_cache[r['date']] = sorted_data[:i]

            for period in periods:
                if not self._is_running: break
                
                p_idx = period['index']
                stats_per_period[p_idx] = {'top1': 0, 'top2': 0, 'top3': 0, 'total': 0, 
                                           'range': f"{period['start_date']:%d/%m} - {period['end_date']:%d/%m}"}
                
                for entry in period['entries']:
                    if not self._is_running: break
                    
                    try:
                        idx_in_full = sorted_data.index(entry)
                        if idx_in_full == 0: continue
                        
                        prev_entry = sorted_data[idx_in_full - 1]
                        predict_date_input = prev_entry['date']
                        actual_result_dict = entry['result']
                        
                        hist = history_cache.get(predict_date_input, [])
                        
                        combined_scores = {}
                        for algo in self.algo_instances:
                            try:
                                preds = algo.predict(entry['date'], hist)
                                if preds:
                                    for num, score in preds.items():
                                        combined_scores[num] = combined_scores.get(num, 0) + float(score)
                            except Exception: pass
                        
                        if not combined_scores: continue

                        sorted_preds = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
                        ranked_nums = [int(k) for k, v in sorted_preds if k.isdigit()]
                        
                        actual_lotos = set()
                        for k, v in actual_result_dict.items():
                            if k not in ['date', 'id', 'source']:
                                vals = v if isinstance(v, list) else [v]
                                for val in vals:
                                    s = str(val)
                                    if len(s) >= 2 and s[-2:].isdigit(): actual_lotos.add(int(s[-2:]))
                        
                        stats_per_period[p_idx]['total'] += 1
                        
                        hit_indices = []
                        for rank_idx, num in enumerate(ranked_nums[:100]):
                            if num in actual_lotos:
                                hit_indices.append(rank_idx)
                                rank_frequency[rank_idx] = rank_frequency.get(rank_idx, 0) + 1
                        
                        if any(idx == 0 for idx in hit_indices): stats_per_period[p_idx]['top1'] += 1
                        if any(idx <= 1 for idx in hit_indices): stats_per_period[p_idx]['top2'] += 1
                        if any(idx <= 2 for idx in hit_indices): stats_per_period[p_idx]['top3'] += 1

                    except Exception: continue
                    
                    current_calc_count += 1
                    self.progress_signal.emit(current_calc_count, total_days_to_calc)

            self.finished_signal.emit({
                'periods': stats_per_period,
                'rank_freq': rank_frequency,
                'total_samples': current_calc_count
            })

        except Exception as e:
            self.error_signal.emit(f"Lỗi luồng đánh giá: {e}")


class AlgorithmEvaluationTab(QWidget):
    def __init__(self, parent_optimizer, main_app):
        super().__init__(parent_optimizer)
        self.opt_parent = parent_optimizer
        self.main_app = main_app
        self.worker = None
        self.thread = None
        self.last_evaluation_results = None
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        top_group = QGroupBox("Chọn Thuật Toán Kết Hợp Đánh Giá")
        top_layout = QVBoxLayout(top_group)
        
        self.algo_list_widget = QListWidget()
        self.algo_list_widget.setFixedHeight(120)
        self.algo_list_widget.setSelectionMode(QListWidget.MultiSelection)
        self.algo_list_widget.setStyleSheet("background-color: white;")
        top_layout.addWidget(self.algo_list_widget)
        
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Tải lại DS")
        self.refresh_btn.clicked.connect(self.refresh_algo_list)
        self.select_all_btn = QPushButton("Chọn tất cả")
        self.select_all_btn.clicked.connect(self.select_all_algos)
        
        btn_layout.addWidget(QLabel("Số kỳ đánh giá (30 ngày/kỳ):"))
        self.period_spinbox = QSpinBox()
        self.period_spinbox.setRange(12, 120)
        self.period_spinbox.setValue(12)
        self.period_spinbox.setFixedWidth(60)
        btn_layout.addWidget(self.period_spinbox)

        self.run_btn = QPushButton("🚀 BẮT ĐẦU ĐÁNH GIÁ")
        self.run_btn.setObjectName("AccentButton")
        self.run_btn.clicked.connect(self.start_evaluation)
        
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.run_btn)
        top_layout.addLayout(btn_layout)
        
        layout.addWidget(top_group)

        res_group = QGroupBox("Kết Quả Đánh Giá")
        res_layout = QVBoxLayout(res_group)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(15)
        
        self.scroll_layout.addWidget(QLabel("<b>1. Độ chính xác Top 1-2-3 qua các giai đoạn:</b>"))
        self.accuracy_table = QtWidgets.QTableWidget()
        self.accuracy_table.setColumnCount(5)
        self.accuracy_table.setHorizontalHeaderLabels(["Giai đoạn", "Khoảng thời gian", "Top 1 (%)", "Top 2 (%)", "Top 3 (%)"])
        
        self.accuracy_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.accuracy_table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.accuracy_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.accuracy_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.accuracy_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.accuracy_table.setMinimumHeight(100)
        self.scroll_layout.addWidget(self.accuracy_table)
        
        self.scroll_layout.addWidget(QLabel("<b>2. Bản đồ nhiệt Tần suất xuất hiện (Vị trí 0-99) & Kết luận:</b>"))
        
        heatmap_container = QWidget()
        heatmap_layout = QHBoxLayout(heatmap_container)
        heatmap_layout.setContentsMargins(0, 0, 0, 0)
        heatmap_layout.setSpacing(10)

        grid_frame = QWidget()
        grid_layout = QVBoxLayout(grid_frame)
        grid_layout.setContentsMargins(0,0,0,0)
        grid_layout.addWidget(QLabel("<i>(Đậm: Hay về | Xanh nhạt: Ít về | Trắng: Trung bình)</i>"))
        
        self.rank_grid = QtWidgets.QTableWidget()
        self.rank_grid.setRowCount(10)
        self.rank_grid.setColumnCount(10)
        
        self.rank_grid.setVerticalHeaderLabels([f"R{i}" for i in range(10)])
        self.rank_grid.setHorizontalHeaderLabels([f"C{i}" for i in range(10)])
        
        self.rank_grid.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rank_grid.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rank_grid.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.rank_grid.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        
        font_header = QFont()
        font_header.setBold(True)
        self.rank_grid.horizontalHeader().setFont(font_header)
        self.rank_grid.verticalHeader().setFont(font_header)

        self.rank_grid.setMinimumSize(500, 480) 
        self.rank_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        grid_layout.addWidget(self.rank_grid)
        
        self.summary_container = QWidget()
        summary_layout = QVBoxLayout(self.summary_container)
        summary_layout.setContentsMargins(0, 20, 0, 0)
        
        self.summary_label = QLabel("Vui lòng chọn thuật toán và số kỳ đánh giá, sau đó nhấn 'Bắt Đầu'...")
        self.summary_label.setWordWrap(True)
        self.summary_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.summary_label.setStyleSheet("""
            QLabel {
                font-size: 10pt; 
                padding: 10px; 
                background-color: #FAFAFA; 
                border: 1px solid #CCCCCC;
                border-radius: 5px;
                color: #333;
            }
        """)
        
        summary_layout.addWidget(self.summary_label)

        summary_layout.addSpacing(10)
        self.export_btn = QPushButton("💾 Xuất File Sắp Xếp (.txt)")
        self.export_btn.setToolTip("Xuất danh sách các ô (00-99) đã được sắp xếp theo thứ tự xuất hiện nhiều nhất.")
        self.export_btn.setStyleSheet("padding: 8px; font-weight: bold;")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_rank_data)
        summary_layout.addWidget(self.export_btn)
        
        summary_layout.addStretch()

        heatmap_layout.addWidget(grid_frame, 7)
        heatmap_layout.addWidget(self.summary_container, 3) 

        self.scroll_layout.addWidget(heatmap_container)
        self.scroll_layout.addSpacing(20)
        
        self.scroll_area.setWidget(self.scroll_widget)
        res_layout.addWidget(self.scroll_area)
        layout.addWidget(res_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #f8f9fa;
                height: 25px;
                color: black;
                font-weight: bold;
                font-size: 11pt;
            }
            QProgressBar::chunk {
                background-color: #28a745; 
            }
        """)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

    def showEvent(self, event):
        self.refresh_algo_list()
        super().showEvent(event)

    def refresh_algo_list(self):
        self.algo_list_widget.clear()
        if self.opt_parent and hasattr(self.opt_parent, 'loaded_algorithms'):
            for name in self.opt_parent.loaded_algorithms.keys():
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.algo_list_widget.addItem(item)

    def select_all_algos(self):
        for i in range(self.algo_list_widget.count()): 
            self.algo_list_widget.item(i).setCheckState(Qt.Checked)

    def start_evaluation(self):
        selected_instances = []
        for i in range(self.algo_list_widget.count()):
            item = self.algo_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                algo_name = item.text()
                if algo_name in self.opt_parent.loaded_algorithms:
                    selected_instances.append(self.opt_parent.loaded_algorithms[algo_name]['instance'])
        
        if not selected_instances:
            QMessageBox.warning(self, "Chưa chọn thuật toán", "Vui lòng chọn ít nhất 1 thuật toán để đánh giá.")
            return

        num_periods = self.period_spinbox.value()

        self.run_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.summary_label.setText(f"<b>Đang tính toán dữ liệu {num_periods} kỳ... vui lòng đợi.</b>")
        self.summary_label.setStyleSheet("color: #007BFF; font-size: 11pt; padding: 15px; border: 1px solid #ccc; background: #fff;")
        
        self.thread = QThread()
        self.worker = EvaluationWorker(selected_instances, self.opt_parent.results_data, num_periods)
        self.worker.moveToThread(self.thread)
        
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.error_signal.connect(self.on_error)
        self.worker.finished_signal.connect(self.on_finished)
        
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def update_progress(self, current, total):
        pct = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"Đang xử lý: {pct}% ({current}/{total} kỳ quay)")

    def on_error(self, msg):
        QMessageBox.critical(self, "Lỗi", msg)
        self.run_btn.setEnabled(True)
        self.thread.quit()

    def on_finished(self, results):
        self.run_btn.setEnabled(True)
        self.thread.quit()
        self.last_evaluation_results = results
        self.display_results(results)
        self.export_btn.setEnabled(True)

    def export_rank_data(self):
        """Hàm xuất dữ liệu xếp hạng ra file txt."""
        if not self.last_evaluation_results:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Vui lòng chạy đánh giá trước khi xuất file.")
            return

        try:
            rank_freq = self.last_evaluation_results.get('rank_freq', {})
            
            all_ranks = []
            for i in range(100):
                count = rank_freq.get(i, 0)
                all_ranks.append((i, count))
            
            sorted_ranks = sorted(all_ranks, key=lambda x: x[1], reverse=True)
            
            result_strings = [f"{item[0]:02d}" for item in sorted_ranks]
            file_content = "-".join(result_strings)
            
            now = datetime.datetime.now()
            default_filename = f"arrange_{now.strftime('%H%M_%d_%m_%Y')}.txt"
            
            default_dir = self.main_app.algorithms_dir
            if not default_dir.exists():
                default_dir = Path.cwd()

            save_path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu File Sắp Xếp",
                str(default_dir / default_filename),
                "Text Files (*.txt);;All Files (*.*)"
            )

            if save_path_str:
                save_path = Path(save_path_str)
                save_path.write_text(file_content, encoding='utf-8')
                
                preview = file_content[:50] + "..." if len(file_content) > 50 else file_content
                QMessageBox.information(self, "Xuất File Thành Công", 
                                        f"Đã lưu file tại:\n{save_path.name}\n\nNội dung (preview):\n{preview}")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi Xuất File", f"Đã xảy ra lỗi khi xuất file:\n{e}")

    def display_results(self, data):
        periods = data['periods']
        self.accuracy_table.setRowCount(len(periods))
        sorted_p_ids = sorted(periods.keys())
        
        for row, p_id in enumerate(sorted_p_ids):
            stats = periods[p_id]
            total = stats['total'] if stats['total'] > 0 else 1
            
            p1 = (stats['top1'] / total) * 100
            p2 = (stats['top2'] / total) * 100
            p3 = (stats['top3'] / total) * 100
            
            self.accuracy_table.setItem(row, 0, QtWidgets.QTableWidgetItem(f"Mốc {p_id}"))
            self.accuracy_table.setItem(row, 1, QtWidgets.QTableWidgetItem(stats['range']))
            self.accuracy_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{p1:.1f}%"))
            self.accuracy_table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{p2:.1f}%"))
            
            item_p3 = QtWidgets.QTableWidgetItem(f"{p3:.1f}%")
            if p3 > 50:
                item_p3.setFont(QFont("Segoe UI", 9, QFont.Bold))
                item_p3.setForeground(QColor("green"))
            self.accuracy_table.setItem(row, 4, item_p3)

        header_height = self.accuracy_table.horizontalHeader().height()
        rows_height = sum([self.accuracy_table.rowHeight(i) for i in range(self.accuracy_table.rowCount())])
        total_height = header_height + rows_height + 5
        self.accuracy_table.setFixedHeight(total_height)

        rank_freq = data['rank_freq']
        all_counts = [rank_freq.get(i, 0) for i in range(100)]
        
        sorted_counts = sorted(all_counts, reverse=True)
        max_val = sorted_counts[0]
        min_val = sorted_counts[-1]
        top3_val = sorted_counts[2] if len(sorted_counts) > 2 else max_val
        top10_val = sorted_counts[9] if len(sorted_counts) > 9 else max_val

        for r in range(10):
            for c in range(10):
                rank_idx = r * 10 + c
                count = rank_freq.get(rank_idx, 0)
                
                item = QtWidgets.QTableWidgetItem(str(count))
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                
                bg_color = QColor("white")
                text_color = QColor("black")
                
                if count == max_val: 
                    bg_color = QColor("#D32F2F") 
                    text_color = QColor("white")
                elif count >= top3_val:
                    bg_color = QColor("#F57C00") 
                    text_color = QColor("white")
                elif count >= top10_val:
                    bg_color = QColor("#FFD54F")
                    text_color = QColor("black")
                elif count == min_val:
                    bg_color = QColor("#B3E5FC")
                    text_color = QColor("black")

                item.setBackground(QBrush(bg_color))
                item.setForeground(QBrush(text_color))
                self.rank_grid.setItem(r, c, item)

        sorted_ranks = sorted(rank_freq.items(), key=lambda x: x[1], reverse=True)
        top_5_ranks = sorted_ranks[:5]
        
        self.summary_label.setStyleSheet("""
            QLabel {
                font-size: 10pt; 
                padding: 10px; 
                background-color: #FFFFFF; 
                border: 2px solid #007BFF;
                border-radius: 8px;
                color: #212529;
            }
        """)

        summary_html = """
        <h3 style='color: #0056b3; margin-top:0; margin-bottom:5px;'>KẾT LUẬN</h3>
        <hr style='margin: 5px 0;'>
        """
        summary_html += f"<p style='margin: 3px 0;'>🔹 Đã check: <b style='color: #28a745;'>{data['total_samples']}</b> ngày</p>"
        summary_html += "<p style='margin: 3px 0;'>🔹 <b>Top 5 Vị trí (Rank) cao nhất:</b></p>"
        summary_html += "<ul style='margin-top:0; padding-left: 15px; margin-bottom: 0;'>"
        
        colors = ["#D32F2F", "#E64A19", "#F57C00", "#FBC02D", "#388E3C"] 
        
        for idx, (rank, count) in enumerate(top_5_ranks):
            pct = (count / data['total_samples'] * 100) if data['total_samples'] > 0 else 0
            color = colors[idx] if idx < len(colors) else "black"
            
            summary_html += f"<li style='margin-bottom: 2px;'>"
            summary_html += f"<b>#{idx+1}:</b> Vị trí <b style='color:{color}; font-size: 11pt;'>{rank:02d}</b> "
            summary_html += f"({pct:.1f}%)</li>"
            
        summary_html += "</ul>"
        
        self.summary_label.setText(summary_html)


class OptimizerEmbedded(QWidget):
    log_signal = pyqtSignal(str, str, str)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(float)
    best_update_signal = pyqtSignal(dict, tuple)
    finished_signal = pyqtSignal(str, bool, str)
    error_signal = pyqtSignal(str)

    def __init__(self, parent_widget: QWidget, base_dir: Path, main_app_instance):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        optimizer_logger.info("Initializing OptimizerEmbedded (PyQt5)...")
        self.base_dir = base_dir
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.base_dir / "config"
        self.algorithms_dir = self.base_dir / "algorithms"
        self.optimize_dir = self.base_dir / "optimize"
        self.calculate_dir = self.base_dir / "calculate"
        self.main_app = main_app_instance
        self.results_data = []
        self.loaded_algorithms = {}
        self.selected_algorithm_for_edit = None
        self.selected_algorithm_for_optimize = None
        self.editor_param_widgets = {}
        self.editor_original_params = {}
        self.optimizer_thread = None
        self.optimizer_queue = queue.Queue()
        self.optimizer_stop_event = threading.Event()
        self.optimizer_pause_event = threading.Event()
        self.optimizer_running = False
        self.optimizer_paused = False
        self.current_best_params = None
        self.current_best_score_tuple = (-1.0, -1.0, -1.0, -100.0)
        self.current_optimization_log_path = None
        self.current_optimize_target_dir = None
        self.optimizer_custom_steps = {}
        self.advanced_opt_widgets = {}
        self.can_resume = False
        self.combination_selection_checkboxes = {}
        self.current_combination_algos = []
        self.opt_start_time = 0.0
        self.opt_time_limit_sec = 0
        self.optimizer_timer = QTimer(self)
        self.optimizer_timer.timeout.connect(self._check_optimizer_queue)
        self.optimizer_timer_interval = 200
        self._is_fetching_online_algos = False
        self._is_refreshing_algos = False
        self.opt_initial_local_algo_label = None

        self.display_timer = QTimer(self)
        self.display_timer.timeout.connect(self._update_optimizer_timer_display)
        self.display_timer_interval = 1000

        self.int_validator = QIntValidator()
        self.double_validator = QDoubleValidator()
        self.custom_steps_validator = QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression(r"^(?:[-+]?\d+(?:\.\d*)?(?:,\s*[-+]?\d+(?:\.\d*)?)*)?$")
        )
        self.weight_validator = QDoubleValidator()
        self.dimension_validator = QIntValidator(1, 9999)


        self.gemini_builder_tab_instance = None
        self.gemini_builder_tab_instance_opt = None
        self.opt_initial_online_algo_label = None
        self.current_optimization_mode = 'auto_hill_climb'
        self.opt_initial_online_algo_label = None



        self.setup_ui()
        self.load_data()
        self.load_algorithms()
        self.update_status("Trình tối ưu sẵn sàng.")
        optimizer_logger.info("OptimizerEmbedded (PyQt5) initialized successfully.")

    def get_main_window(self):
        widget = self
        while widget is not None:
            if isinstance(widget, QMainWindow):
                return widget
            widget = widget.parent()
        return QApplication.activeWindow()

    def setup_ui(self):
        optimizer_logger.debug("Setting up optimizer embedded UI (PyQt5)...")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Đã loại bỏ card thông tin dữ liệu do optimizer mặc định dùng chung data chính của chương trình
        self.data_file_path_label = QLabel("...")
        self.data_file_path_label.setObjectName("PathDisplayLabel")
        self.data_file_path_label.setVisible(False)
        self.data_range_label = QLabel("...")
        self.data_range_label.setVisible(False)

        self.tab_widget = QTabWidget()

        self.tab_select = QWidget()
        self.tab_evaluation_frame = QWidget()
        self.tab_gemini_builder_frame = QWidget()
        self.tab_edit = QWidget()
        self.tab_optimize = QWidget()

        main_layout.addWidget(self.tab_widget, 1)

        self.tab_widget.addTab(self.tab_select, " Thuật Toán 🎰")
        self.tab_widget.addTab(self.tab_evaluation_frame, " Đánh Giá 📊")
        self.tab_widget.addTab(self.tab_gemini_builder_frame, " Tạo Thuật Toán 🧠")
        self.tab_widget.addTab(self.tab_edit, " Chỉnh Sửa ✍️")
        self.tab_widget.addTab(self.tab_optimize, " Tối Ưu Hóa 🚀")

        try:
            self.eval_tab_instance = AlgorithmEvaluationTab(self, self.main_app)
            eval_layout = QVBoxLayout(self.tab_evaluation_frame)
            eval_layout.setContentsMargins(0,0,0,0)
            eval_layout.addWidget(self.eval_tab_instance)
        except Exception as e:
            optimizer_logger.error(f"Failed to init Evaluation Tab: {e}")

        if HAS_GEMINI and AlgorithmGeminiBuilderTab is not None:
            if self.gemini_builder_tab_instance_opt is None:
                try:
                    self.gemini_builder_tab_instance_opt = AlgorithmGeminiBuilderTab(self.tab_gemini_builder_frame, self.main_app)
                    layout_gemini = QVBoxLayout(self.tab_gemini_builder_frame)
                    layout_gemini.setContentsMargins(0,0,0,0)
                    layout_gemini.addWidget(self.gemini_builder_tab_instance_opt)
                    optimizer_logger.info("Optimizer's Gemini Algorithm Builder sub-tab initialized successfully inside setup_ui.")
                    self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.tab_gemini_builder_frame), True)
                except Exception as e:
                    optimizer_logger.error(f"Failed to initialize AlgorithmGeminiBuilderTab: {e}", exc_info=True)
        else:
            layout_gemini = QVBoxLayout(self.tab_gemini_builder_frame)
            lbl_notice = QLabel("⚠️ Vui lòng cài đặt thư viện google-generativeai để sử dụng tính năng Tạo thuật toán bằng AI.")
            lbl_notice.setAlignment(Qt.AlignCenter)
            lbl_notice.setStyleSheet("font-size: 11pt; color: #dc2626; font-weight: bold; padding: 20px;")
            layout_gemini.addWidget(lbl_notice)

        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.tab_edit), False)
        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.tab_optimize), False)

        self.setup_select_tab()
        self.setup_edit_tab()
        self.setup_optimize_tab()

        
    def setup_select_tab(self):
        optimizer_logger.debug("Setting up Optimizer's Select Algorithm tab with two columns...")
        layout = QVBoxLayout(self.tab_select)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        control_frame_top = QWidget()
        control_layout_top = QHBoxLayout(control_frame_top)
        control_layout_top.setContentsMargins(0,0,0,0)
        control_layout_top.setSpacing(10)

        self.opt_algo_refresh_button = QPushButton("🔎 Tải danh sách thuật toán trên Server 📥")
        self.opt_algo_refresh_button.setObjectName("LightButton")
        self.opt_algo_refresh_button.setToolTip("Quét lại thư mục algorithms và tải lại danh sách thuật toán online.")
        self.opt_algo_refresh_button.clicked.connect(self._refresh_optimizer_algo_lists)

        control_layout_top.addStretch(1)
        control_layout_top.addWidget(self.opt_algo_refresh_button)
        layout.addWidget(control_frame_top)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        local_algo_group = QGroupBox("🎰 Thuật toán trên máy")
        local_algo_main_layout = QVBoxLayout(local_algo_group)
        local_algo_main_layout.setContentsMargins(5, 10, 5, 5)

        self.opt_local_algo_scroll_area = QScrollArea()
        self.opt_local_algo_scroll_area.setWidgetResizable(True)
        self.opt_local_algo_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")
        
        self.opt_local_algo_scroll_widget = QWidget()
        self.opt_local_algo_scroll_area.setWidget(self.opt_local_algo_scroll_widget)
        self.opt_local_algo_list_layout = QVBoxLayout(self.opt_local_algo_scroll_widget)
        self.opt_local_algo_list_layout.setAlignment(Qt.AlignTop)
        self.opt_local_algo_list_layout.setSpacing(8)
        
        if not hasattr(self, 'opt_initial_local_algo_label') or self.opt_initial_local_algo_label is None:
            self.opt_initial_local_algo_label = QLabel("Đang tải thuật toán trên máy...")
            self.opt_initial_local_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
            self.opt_initial_local_algo_label.setAlignment(Qt.AlignCenter)
        if self.opt_initial_local_algo_label.parentWidget() is None:
            self.opt_local_algo_list_layout.addWidget(self.opt_initial_local_algo_label)

        local_algo_main_layout.addWidget(self.opt_local_algo_scroll_area)
        splitter.addWidget(local_algo_group)

        online_column_widget = QWidget()
        online_column_main_layout = QVBoxLayout(online_column_widget)
        online_column_main_layout.setContentsMargins(0, 0, 0, 0) 
        online_column_main_layout.setSpacing(5)

        online_header_and_button_widget = QWidget()
        online_header_and_button_layout = QHBoxLayout(online_header_and_button_widget)
        online_header_and_button_layout.setContentsMargins(0, 5, 0, 0)
        
        online_title_label = QLabel("🎰 Danh sách Thuật toán Online")
        bold_font = self.main_app.get_qfont("bold") if hasattr(self.main_app, 'get_qfont') else QFont()
        if not hasattr(self.main_app, 'get_qfont'): bold_font.setBold(True)
        online_title_label.setFont(bold_font)
        online_header_and_button_layout.addWidget(online_title_label)
        
        online_header_and_button_layout.addSpacing(10)

        self.opt_algo_refresh_button.setText("🔎 Tải lại")

        online_header_and_button_layout.addWidget(self.opt_algo_refresh_button)
        online_header_and_button_layout.addStretch(1)

        online_column_main_layout.addWidget(online_header_and_button_widget)

        self.opt_online_algo_scroll_area = QScrollArea()
        self.opt_online_algo_scroll_area.setWidgetResizable(True)
        border_color_from_config = self.main_app.config.get('THEME_COLORS', 'COLOR_BORDER', fallback='#CED4DA') if hasattr(self.main_app, 'config') else '#CED4DA'
        self.opt_online_algo_scroll_area.setStyleSheet(f"QScrollArea {{ background-color: #FFFFFF; border: 1px solid {border_color_from_config}; }}")
        
        online_column_main_layout.addWidget(self.opt_online_algo_scroll_area, 1)
        splitter.addWidget(online_column_widget)

        QTimer.singleShot(0, lambda: splitter.setSizes([splitter.width() * 4 // 10, splitter.width() * 6 // 10]))

        if not hasattr(self, 'optimizer_local_algorithms_managed_ui'):
            self.optimizer_local_algorithms_managed_ui = {}
        if not hasattr(self, 'optimizer_online_algorithms_ui'):
            self.optimizer_online_algorithms_ui = {}

        self._show_initial_online_message()

        optimizer_logger.debug("Optimizer's Select Algorithm tab UI structure set up.")

        
    def _show_initial_online_message(self):
        """Hiển thị thông báo ban đầu cho khu vực thuật toán online."""
        if not hasattr(self, 'opt_online_algo_scroll_area'):
            return

        initial_widget = QWidget()
        layout = QVBoxLayout(initial_widget)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0, 10, 0, 0)

        label_text = ("<div style='text-align: center;'>"
                      "<br><br><br><br>"
                      "Nhấn <b>'Tải lại'</b> ở trên để lấy danh sách thuật toán online..."
                      "</div>")
        label = QLabel(label_text)
        label.setTextFormat(Qt.RichText)
        label.setStyleSheet("font-style: italic; color: #6c757d; padding: 20px;")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        old_widget = self.opt_online_algo_scroll_area.widget()
        if old_widget:
            old_widget.deleteLater()
        self.opt_online_algo_scroll_area.setWidget(initial_widget)
        self.opt_online_algo_list_layout = layout

    def setup_edit_tab(self):
        layout = QVBoxLayout(self.tab_edit)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_frame.setFrameShadow(QFrame.Sunken)
        info_layout = QGridLayout(info_frame)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(6)

        info_layout.addWidget(QLabel("Thuật toán đang sửa:"), 0, 0, Qt.AlignLeft)
        self.edit_algo_name_label = QLabel("...")
        self.edit_algo_name_label.setStyleSheet(f"font-weight: bold; color: #007BFF; font-size: {self.main_app.get_font_size('title')}pt;")
        info_layout.addWidget(self.edit_algo_name_label, 0, 1)

        info_layout.addWidget(QLabel("Mô tả:"), 1, 0, Qt.AlignTop | Qt.AlignLeft)
        self.edit_algo_desc_label = QLabel("...")
        self.edit_algo_desc_label.setWordWrap(True)
        self.edit_algo_desc_label.setStyleSheet("color: #17a2b8;")
        info_layout.addWidget(self.edit_algo_desc_label, 1, 1)
        info_layout.setColumnStretch(1, 1)
        layout.addWidget(info_frame)

        splitter = QSplitter(Qt.Horizontal)

        param_groupbox = QGroupBox("Tham Số Có Thể Chỉnh Sửa")
        param_outer_layout = QVBoxLayout(param_groupbox)
        param_outer_layout.setContentsMargins(5, 10, 5, 5)

        param_scroll_area = QScrollArea()
        param_scroll_area.setWidgetResizable(True)
        param_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")

        self.edit_param_scroll_widget = QWidget()
        param_scroll_area.setWidget(self.edit_param_scroll_widget)
        self.edit_param_layout = QFormLayout(self.edit_param_scroll_widget)
        self.edit_param_layout.setLabelAlignment(Qt.AlignLeft)
        self.edit_param_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.edit_param_layout.setHorizontalSpacing(10)
        self.edit_param_layout.setVerticalSpacing(6)

        param_outer_layout.addWidget(param_scroll_area)
        splitter.addWidget(param_groupbox)

        explain_groupbox = QGroupBox("Giải Thích Thuật Toán")
        explain_layout = QVBoxLayout(explain_groupbox)
        explain_layout.setContentsMargins(5, 10, 5, 5)

        self.edit_explain_text = QTextEdit()
        self.edit_explain_text.setReadOnly(True)
        explain_font = self.main_app.get_qfont("code")
        self.edit_explain_text.setFont(explain_font)
        self.edit_explain_text.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #212529;
                border: 1px solid #CED4DA;
            }
        """)
        explain_layout.addWidget(self.edit_explain_text)
        splitter.addWidget(explain_groupbox)

        splitter.setSizes([splitter.width() // 2, splitter.width() // 2])

        layout.addWidget(splitter, 1)

        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addStretch(1)

        cancel_button = QPushButton("Hủy Bỏ")
        cancel_button.clicked.connect(self.cancel_edit)
        button_layout.addWidget(cancel_button)

        save_copy_button = QPushButton("Lưu Bản Sao...")
        save_copy_button.setObjectName("AccentButton")
        save_copy_button.clicked.connect(self.save_edited_copy)
        button_layout.addWidget(save_copy_button)
        layout.addWidget(button_frame)

    def setup_optimize_tab(self):
        tab_main_layout = QVBoxLayout(self.tab_optimize)
        tab_main_layout.setContentsMargins(0, 0, 0, 0)
        tab_main_layout.setSpacing(0)

        opt_scroll = QScrollArea()
        opt_scroll.setWidgetResizable(True)
        opt_scroll.setFrameShape(QFrame.NoFrame)
        opt_scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        opt_container = QWidget()
        opt_container.setObjectName("OptimizeTabScrollContent")
        layout = QVBoxLayout(opt_container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        opt_scroll.setWidget(opt_container)
        tab_main_layout.addWidget(opt_scroll)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0,0,0,0)
        top_layout.setSpacing(8)
        top_widget.setMinimumHeight(320)
        layout.addWidget(top_widget, 0)

        info_frame = QWidget()
        info_h_layout = QHBoxLayout(info_frame)
        info_h_layout.setContentsMargins(0,0,0,0)
        info_h_layout.addWidget(QLabel("Thuật toán tối ưu:"))
        self.opt_algo_name_label = QLabel("...")
        self.opt_algo_name_label.setStyleSheet(f"font-weight: bold; color: #28a745; font-size: {self.main_app.get_font_size('title')}pt;")
        info_h_layout.addWidget(self.opt_algo_name_label)
        info_h_layout.addStretch(1)
        top_layout.addWidget(info_frame)

        self.settings_container = QWidget()
        self.settings_container.setMinimumHeight(220)
        settings_h_layout = QHBoxLayout(self.settings_container)
        settings_h_layout.setContentsMargins(0, 0, 0, 0)
        settings_h_layout.setSpacing(10)
        top_layout.addWidget(self.settings_container)

        settings_groupbox = QGroupBox("Cài Đặt Cơ Bản")
        settings_groupbox.setMinimumHeight(220)
        settings_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        settings_layout = QGridLayout(settings_groupbox)
        settings_layout.setContentsMargins(10, 15, 10, 10)
        settings_layout.setVerticalSpacing(6)
        settings_layout.setHorizontalSpacing(6)

        settings_layout.addWidget(QLabel("Khoảng thời gian tối ưu:"), 0, 0, 1, 3, Qt.AlignLeft)

        lbl_from = QLabel("Từ ngày:")
        lbl_from.setFixedWidth(65)
        settings_layout.addWidget(lbl_from, 1, 0, Qt.AlignLeft | Qt.AlignVCenter)

        self.opt_start_date_edit = QLineEdit()
        self.opt_start_date_edit.setReadOnly(True)
        self.opt_start_date_edit.setAlignment(Qt.AlignCenter)
        self.opt_start_date_edit.setMinimumWidth(100)
        self.opt_start_date_edit.setToolTip("Ngày bắt đầu dữ liệu dùng để kiểm tra tối ưu.")
        settings_layout.addWidget(self.opt_start_date_edit, 1, 1)

        self.opt_start_date_button = QPushButton("📅")
        self.opt_start_date_button.setObjectName("CalendarButton")
        self.opt_start_date_button.setToolTip("Chọn ngày bắt đầu.")
        self.opt_start_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.opt_start_date_edit))
        settings_layout.addWidget(self.opt_start_date_button, 1, 2)

        lbl_to = QLabel("Đến ngày:")
        lbl_to.setFixedWidth(65)
        settings_layout.addWidget(lbl_to, 2, 0, Qt.AlignLeft | Qt.AlignVCenter)

        self.opt_end_date_edit = QLineEdit()
        self.opt_end_date_edit.setReadOnly(True)
        self.opt_end_date_edit.setAlignment(Qt.AlignCenter)
        self.opt_end_date_edit.setMinimumWidth(100)
        self.opt_end_date_edit.setToolTip("Ngày kết thúc dữ liệu dùng để kiểm tra tối ưu (phải trước ngày cuối cùng trong file data).")
        settings_layout.addWidget(self.opt_end_date_edit, 2, 1)

        self.opt_end_date_button = QPushButton("📅")
        self.opt_end_date_button.setObjectName("CalendarButton")
        self.opt_end_date_button.setToolTip("Chọn ngày kết thúc.")
        self.opt_end_date_button.clicked.connect(lambda: self.show_calendar_dialog_qt(self.opt_end_date_edit))
        settings_layout.addWidget(self.opt_end_date_button, 2, 2)

        date_info_label = QLabel("(Ngày cuối < ngày cuối data 1 ngày)")
        date_info_label.setStyleSheet("font-style: italic; color: #64748b; font-size: 8.5pt;")
        settings_layout.addWidget(date_info_label, 3, 0, 1, 3, Qt.AlignLeft)

        lbl_time = QLabel("Thời gian tối đa:")
        lbl_time.setFixedWidth(95)
        settings_layout.addWidget(lbl_time, 4, 0, Qt.AlignLeft | Qt.AlignVCenter)

        time_box = QWidget()
        time_h_layout = QHBoxLayout(time_box)
        time_h_layout.setContentsMargins(0, 0, 0, 0)
        time_h_layout.setSpacing(4)

        self.opt_time_limit_spinbox = QSpinBox()
        self.opt_time_limit_spinbox.setRange(1, 9999)
        self.opt_time_limit_spinbox.setValue(60)
        self.opt_time_limit_spinbox.setAlignment(Qt.AlignCenter)
        self.opt_time_limit_spinbox.setFixedWidth(65)
        self.opt_time_limit_spinbox.setToolTip("Giới hạn thời gian chạy tối đa cho một lần tối ưu.")
        time_h_layout.addWidget(self.opt_time_limit_spinbox)
        time_h_layout.addWidget(QLabel("phút"))
        time_h_layout.addStretch(1)
        settings_layout.addWidget(time_box, 4, 1, 1, 2)

        self.delete_old_optimized_files_checkbox = QCheckBox("Xóa file cũ khi có file tốt hơn")
        self.delete_old_optimized_files_checkbox.setToolTip(
            "Nếu được chọn, khi một bộ tham số tối ưu mới tốt hơn được tìm thấy và lưu lại,\n"
            "các file tối ưu (.py và .json) có điểm số thấp hơn trong cùng thư mục 'success' của thuật toán này sẽ bị xóa."
        )
        self.delete_old_optimized_files_checkbox.setChecked(False)
        settings_layout.addWidget(self.delete_old_optimized_files_checkbox, 5, 0, 1, 3, Qt.AlignLeft)

        settings_layout.setColumnStretch(0, 0)
        settings_layout.setColumnStretch(1, 1)
        settings_layout.setColumnStretch(2, 0)
        settings_layout.setRowStretch(6, 1)

        settings_h_layout.addWidget(settings_groupbox, 1)

        self.optimization_mode_groupbox = QGroupBox("Chế Độ Tối Ưu")
        self.optimization_mode_groupbox.setMinimumHeight(220)
        self.optimization_mode_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        mode_outer_layout = QVBoxLayout(self.optimization_mode_groupbox)
        mode_outer_layout.setContentsMargins(10, 15, 10, 10)
        mode_outer_layout.setSpacing(6)

        self.opt_mode_group = QButtonGroup(self)
        self.opt_mode_auto_radio = QRadioButton("Tối ưu Tự động (Hill Climb / Custom)")
        self.opt_mode_auto_radio.setChecked(True)
        self.opt_mode_auto_radio.toggled.connect(self._on_optimization_mode_changed)
        self.opt_mode_group.addButton(self.opt_mode_auto_radio)
        mode_outer_layout.addWidget(self.opt_mode_auto_radio)

        self.opt_mode_combo_radio = QRadioButton("Tạo Bộ Tham Số")
        self.opt_mode_combo_radio.toggled.connect(self._on_optimization_mode_changed)
        self.opt_mode_group.addButton(self.opt_mode_combo_radio)
        mode_outer_layout.addWidget(self.opt_mode_combo_radio)

        self.combo_gen_settings_widget = QWidget()
        combo_gen_layout = QGridLayout(self.combo_gen_settings_widget)
        combo_gen_layout.setContentsMargins(16, 4, 4, 4)
        combo_gen_layout.setVerticalSpacing(4)
        combo_gen_layout.setHorizontalSpacing(6)

        combo_gen_layout.addWidget(QLabel("Số giá trị/tham số:"), 0, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.combo_num_values_spinbox = QSpinBox()
        self.combo_num_values_spinbox.setRange(2, 50)
        self.combo_num_values_spinbox.setValue(10)
        self.combo_num_values_spinbox.setFixedWidth(65)
        combo_gen_layout.addWidget(self.combo_num_values_spinbox, 0, 1, Qt.AlignLeft)

        combo_gen_layout.addWidget(QLabel("Số bộ tối đa:"), 1, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.combo_max_combinations_spinbox = QSpinBox()
        self.combo_max_combinations_spinbox.setRange(1, 5000000)
        self.combo_max_combinations_spinbox.setValue(20000)
        self.combo_max_combinations_spinbox.setFixedWidth(90)
        self.combo_max_combinations_spinbox.setToolTip("Giới hạn số lượng bộ tham số tối đa sẽ được tạo và kiểm tra.")
        combo_gen_layout.addWidget(self.combo_max_combinations_spinbox, 1, 1, Qt.AlignLeft)

        mode_outer_layout.addWidget(self.combo_gen_settings_widget)
        self.combo_gen_settings_widget.setEnabled(False)

        mode_outer_layout.addStretch(1)
        settings_h_layout.addWidget(self.optimization_mode_groupbox, 1)

        self.custom_steps_groupbox = QGroupBox("Tùy Chỉnh tham số tối ưu (bước nhảy)")
        self.custom_steps_groupbox.setMinimumHeight(220)
        self.custom_steps_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        steps_outer_layout = QVBoxLayout(self.custom_steps_groupbox)
        steps_outer_layout.setContentsMargins(5, 10, 5, 5)
        steps_outer_layout.setSpacing(6)

        self.param_scroll_widget_container = QWidget()
        param_scroll_layout = QVBoxLayout(self.param_scroll_widget_container)
        param_scroll_layout.setContentsMargins(0, 5, 0, 0)
        param_scroll_layout.setSpacing(4)

        adv_scroll_area = QScrollArea()
        adv_scroll_area.setWidgetResizable(True)
        adv_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")
        self.advanced_opt_params_widget = QWidget()
        adv_scroll_area.setWidget(self.advanced_opt_params_widget)
        self.advanced_opt_params_layout = QVBoxLayout(self.advanced_opt_params_widget)
        self.advanced_opt_params_layout.setAlignment(Qt.AlignTop)
        self.advanced_opt_params_layout.setSpacing(4)
        self.initial_adv_label = QLabel("Chọn thuật toán để xem tham số.")
        self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_adv_label.setAlignment(Qt.AlignCenter)
        self.advanced_opt_params_layout.addWidget(self.initial_adv_label)
        param_scroll_layout.addWidget(adv_scroll_area)

        steps_outer_layout.addWidget(self.param_scroll_widget_container)
        settings_h_layout.addWidget(self.custom_steps_groupbox, 2)

        self.combination_groupbox = QGroupBox("Kết hợp với Thuật toán +")
        self.combination_groupbox.setMinimumHeight(220)
        self.combination_groupbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        combo_outer_layout = QVBoxLayout(self.combination_groupbox)
        combo_outer_layout.setContentsMargins(5, 10, 5, 5)
        combo_outer_layout.setSpacing(6)

        combo_scroll_area = QScrollArea()
        combo_scroll_area.setWidgetResizable(True)
        combo_scroll_area.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")
        self.combination_scroll_widget = QWidget()
        combo_scroll_area.setWidget(self.combination_scroll_widget)
        self.combination_layout = QVBoxLayout(self.combination_scroll_widget)
        self.combination_layout.setAlignment(Qt.AlignTop)
        self.combination_layout.setSpacing(4)
        self.initial_combo_label = QLabel("Chọn thuật toán để tối ưu...")
        self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        self.initial_combo_label.setAlignment(Qt.AlignCenter)
        self.combination_layout.addWidget(self.initial_combo_label)
        combo_outer_layout.addWidget(combo_scroll_area)
        settings_h_layout.addWidget(self.combination_groupbox, 1)

        control_frame = QWidget()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 5, 0, 5)
        control_layout.setSpacing(8)
        self.opt_start_button = QPushButton("Bắt đầu Tối ưu")
        self.opt_start_button.setObjectName("AccentButton")
        self.opt_start_button.setMinimumWidth(130)
        self.opt_start_button.clicked.connect(self.start_optimization)
        control_layout.addWidget(self.opt_start_button)

        self.opt_resume_button = QPushButton("Tiếp tục Tối ưu")
        self.opt_resume_button.setObjectName("AccentButton")
        self.opt_resume_button.setMinimumWidth(130)
        self.opt_resume_button.clicked.connect(self.resume_optimization_session)
        self.opt_resume_button.setEnabled(False)
        control_layout.addWidget(self.opt_resume_button)

        self.opt_pause_button = QPushButton("Tạm dừng")
        self.opt_pause_button.setObjectName("WarningButton")
        self.opt_pause_button.setMinimumWidth(95)
        self.opt_pause_button.setEnabled(False)
        control_layout.addWidget(self.opt_pause_button)

        self.opt_stop_button = QPushButton("Dừng Hẳn")
        self.opt_stop_button.setObjectName("DangerButton")
        self.opt_stop_button.setMinimumWidth(95)
        self.opt_stop_button.clicked.connect(self.stop_optimization)
        self.opt_stop_button.setEnabled(False)
        control_layout.addWidget(self.opt_stop_button)
        
        control_layout.addSpacing(20)
        
        open_folder_button_control_bar = QPushButton("📂 Mở Thư Mục Tối Ưu")
        open_folder_button_control_bar.setToolTip("Mở thư mục chứa kết quả tối ưu của thuật toán này.")
        open_folder_button_control_bar.setMinimumWidth(180)
        open_folder_button_control_bar.clicked.connect(self.open_optimize_folder)
        control_layout.addWidget(open_folder_button_control_bar)

        control_layout.addStretch(1)
        top_layout.addWidget(control_frame)

        progress_frame = QWidget()
        progress_layout = QGridLayout(progress_frame)
        progress_layout.setContentsMargins(0, 5, 0, 5)
        progress_layout.setVerticalSpacing(2)
        progress_layout.setHorizontalSpacing(8)
        self.opt_progressbar = QProgressBar()
        self.opt_progressbar.setTextVisible(False)
        self.opt_progressbar.setFixedHeight(22)
        self.opt_progressbar.setRange(0, 100)
        self.opt_progressbar.setObjectName("OptimizeProgressBar")
        progress_layout.addWidget(self.opt_progressbar, 0, 0, 1, 4)

        self.opt_status_label = QLabel("Trạng thái: Chờ")
        self.opt_status_label.setStyleSheet("color: #6c757d;")
        progress_layout.addWidget(self.opt_status_label, 1, 0)

        self.opt_progress_label = QLabel("0%")
        self.opt_progress_label.setMinimumWidth(40)
        self.opt_progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_layout.addWidget(self.opt_progress_label, 1, 1)

        self.opt_time_static_label = QLabel("Thời gian còn lại:")
        self.opt_time_static_label.setStyleSheet("color: #6c757d;")
        progress_layout.addWidget(self.opt_time_static_label, 1, 2, Qt.AlignRight)
        self.opt_time_static_label.setVisible(False)

        self.opt_time_remaining_label = QLabel("--:--:--")
        self.opt_time_remaining_label.setStyleSheet("font-weight: bold;")
        self.opt_time_remaining_label.setMinimumWidth(70)
        progress_layout.addWidget(self.opt_time_remaining_label, 1, 3, Qt.AlignLeft)
        self.opt_time_remaining_label.setVisible(False)

        progress_layout.setColumnStretch(0, 1)
        progress_layout.setColumnStretch(1, 0)
        progress_layout.setColumnStretch(2, 0)
        progress_layout.setColumnStretch(3, 0)
        top_layout.addWidget(progress_frame)

        log_groupbox = QGroupBox("Nhật Ký Tối Ưu Hóa")
        log_outer_layout = QVBoxLayout(log_groupbox)
        log_outer_layout.setContentsMargins(5, 10, 5, 5)
        log_outer_layout.setSpacing(6)

        self.opt_log_text = QTextEdit()
        self.opt_log_text.setObjectName("OptimizeLogText")
        self.opt_log_text.setReadOnly(True)
        self.opt_log_text.setMinimumHeight(150)
        log_font = self.main_app.get_qfont("code")
        self.opt_log_text.setFont(log_font)
        self.opt_log_text.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #212529;
                border: 1px solid #CED4DA;
            }
        """)
        self._setup_log_formats()
        log_outer_layout.addWidget(self.opt_log_text, 1)

        layout.addWidget(log_groupbox, 1)

    def _on_optimization_mode_changed(self, checked):
        if not checked:
            return

        sender = self.sender()
        if sender == self.opt_mode_auto_radio:
            self.current_optimization_mode = 'auto_hill_climb'
            self.combo_gen_settings_widget.setEnabled(False)
            self.param_scroll_widget_container.setEnabled(True)
            optimizer_logger.debug("Switched to Auto/Custom optimization mode.")
        elif sender == self.opt_mode_combo_radio:
            self.current_optimization_mode = 'generated_combinations'
            self.combo_gen_settings_widget.setEnabled(True)
            self.param_scroll_widget_container.setEnabled(False)
            optimizer_logger.debug("Switched to Generated Combinations optimization mode.")
        self._populate_advanced_optimizer_settings()


    def _setup_log_formats(self):

        self.log_formats = {}
        base_font = self.main_app.get_qfont("code")
        bold_font = self.main_app.get_qfont("code_bold")
        bold_underline_font = self.main_app.get_qfont("code_bold_underline")

        def create_format(font, color_hex):
            fmt = QtGui.QTextCharFormat()
            fmt.setFont(font)
            fmt.setForeground(QColor(color_hex))
            return fmt

        self.log_formats["INFO"] = create_format(base_font, '#212529')
        self.log_formats["DEBUG"] = create_format(base_font, '#6c757d')
        self.log_formats["WARNING"] = create_format(base_font, '#ffc107')
        self.log_formats["ERROR"] = create_format(bold_font, '#dc3545')
        self.log_formats["CRITICAL"] = create_format(bold_underline_font, '#dc3545')
        self.log_formats["BEST"] = create_format(bold_font, '#28a745')
        self.log_formats["PROGRESS"] = create_format(base_font, '#17a2b8')
        self.log_formats["CUSTOM_STEP"] = create_format(base_font, '#6f42c1')
        self.log_formats["RESUME"] = create_format(bold_font, '#17a2b8')
        self.log_formats["COMBINE"] = create_format(base_font, "#fd7e14")
        self.log_formats["GEN_COMBO"] = create_format(base_font, "#E83E8C")


    def browse_data_file(self):
        optimizer_logger.debug("Browsing for optimizer data file (PyQt5)...")
        initial_dir = str(self.data_dir)
        current_path_str = self.data_file_path_label.text()
        if current_path_str and current_path_str != "..." and Path(current_path_str).is_file():
            parent_dir = Path(current_path_str).parent
            if parent_dir.is_dir():
                initial_dir = str(parent_dir)

        filename, _ = QFileDialog.getOpenFileName(
            self.get_main_window(),
            "Chọn file dữ liệu JSON cho Optimizer",
            initial_dir,
            "JSON files (*.json);;All files (*.*)"
        )
        if filename:
            self.data_file_path_label.setText(filename)
            optimizer_logger.info(f"Optimizer data file selected by user: {filename}")
            self.load_data()

    def load_data(self):
        optimizer_logger.info("Loading lottery data for optimizer (PyQt5)...")
        self.results_data = []
        data_file_str = self.data_file_path_label.text()

        if not data_file_str or data_file_str == "...":
            if hasattr(self.main_app, 'data_file_path') and self.main_app.data_file_path and Path(self.main_app.data_file_path).exists():
                data_file_str = str(self.main_app.data_file_path)
                self.data_file_path_label.setText(data_file_str)
            elif (self.data_dir / "xsmb-2-digits.json").exists():
                data_file_str = str(self.data_dir / "xsmb-2-digits.json")
                self.data_file_path_label.setText(data_file_str)
            else:
                reply = QMessageBox.information(self.get_main_window(), "Chọn File Dữ Liệu",
                                               "Vui lòng chọn file dữ liệu JSON cho trình tối ưu.",
                                               QMessageBox.Ok | QMessageBox.Cancel)
                if reply == QMessageBox.Ok:
                    self.browse_data_file()
                    data_file_str = self.data_file_path_label.text()
                    if not data_file_str or data_file_str == "...":
                        self.update_status("Chưa chọn file dữ liệu cho trình tối ưu.")
                        self.data_range_label.setText("Chưa tải dữ liệu")
                        return
                else:
                    self.update_status("Chưa chọn file dữ liệu cho trình tối ưu.")
                    self.data_range_label.setText("Chưa tải dữ liệu")
                    return

        data_file_path = Path(data_file_str)
        self.data_file_path_label.setText(str(data_file_path))

        if not data_file_path.exists():
            optimizer_logger.error(f"Optimizer data file not found: {data_file_path}")
            QMessageBox.critical(self.get_main_window(), "Lỗi", f"File không tồn tại:\n{data_file_path}")
            self.data_range_label.setText("Lỗi file dữ liệu")
            return

        try:
            with open(data_file_path, 'r', encoding='utf-8') as f: raw_data = json.load(f)
            processed_results = []
            unique_dates = set()
            data_list_to_process = []
            if isinstance(raw_data, list): data_list_to_process = raw_data
            elif isinstance(raw_data, dict) and 'results' in raw_data and isinstance(raw_data.get('results'), dict):
                for date_str, result_dict in raw_data['results'].items():
                    if isinstance(result_dict, dict): data_list_to_process.append({'date': date_str, 'result': result_dict})
            else: raise ValueError("Định dạng JSON không hợp lệ.")
            for item in data_list_to_process:
                if not isinstance(item, dict): continue
                date_str_raw = item.get("date")
                if not date_str_raw: continue
                try:
                    date_str_cleaned = str(date_str_raw).split('T')[0]
                    date_obj = datetime.datetime.strptime(date_str_cleaned, '%Y-%m-%d').date()
                except ValueError: continue
                if date_obj in unique_dates: continue
                result_dict = item.get('result')
                if result_dict is None: result_dict = {k: v for k, v in item.items() if k != 'date'}
                if not result_dict: continue
                processed_results.append({'date': date_obj, 'result': result_dict})
                unique_dates.add(date_obj)

            if processed_results:
                processed_results.sort(key=lambda x: x['date'])
                self.results_data = processed_results
                start_date, end_date = self.results_data[0]['date'], self.results_data[-1]['date']
                self.data_range_label.setText(f"{start_date:%d/%m/%Y} - {end_date:%d/%m/%Y} ({len(self.results_data)} ngày)")
                self.update_status(f"Optimizer: Đã tải {len(self.results_data)} kết quả từ {data_file_path.name}")
                if not self.opt_start_date_edit.text() and len(self.results_data) > 1:
                    self.opt_start_date_edit.setText(start_date.strftime('%d/%m/%Y'))
                if not self.opt_end_date_edit.text() and len(self.results_data) > 1:
                    self.opt_end_date_edit.setText((end_date - datetime.timedelta(days=1)).strftime('%d/%m/%Y'))
            else:
                self.data_range_label.setText("Không có dữ liệu hợp lệ"); self.update_status("Optimizer: Không tải được dữ liệu.")
        except (json.JSONDecodeError, ValueError) as e:
            optimizer_logger.error(f"Optimizer: Invalid JSON/Data in {data_file_path.name}: {e}", exc_info=True)
            QMessageBox.critical(self.get_main_window(), "Lỗi Dữ Liệu (Optimizer)", f"File '{data_file_path.name}' không hợp lệ:\n{e}")
            self.data_range_label.setText("Lỗi định dạng file")
        except Exception as e:
            optimizer_logger.error(f"Optimizer: Unexpected error loading data: {e}", exc_info=True)
            QMessageBox.critical(self.get_main_window(), "Lỗi (Optimizer)", f"Lỗi khi tải dữ liệu:\n{e}")
            self.data_range_label.setText("Lỗi tải dữ liệu")

    def load_algorithms(self):
        optimizer_logger.info("Optimizer: Loading algorithms (PyQt5) for Optimizer's select tab...")
        main_window = self.get_main_window()

        if not hasattr(self, 'opt_local_algo_list_layout'):
            optimizer_logger.error("Optimizer: opt_local_algo_list_layout is not initialized. Cannot clear UI for local algos.")
            return

        widgets_to_remove_from_local_list = []
        for i in range(self.opt_local_algo_list_layout.count()):
            item = self.opt_local_algo_list_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QFrame) and widget != getattr(self, 'opt_initial_local_algo_label', None):
                widgets_to_remove_from_local_list.append(widget)
            elif widget == getattr(self, 'opt_initial_local_algo_label', None) and self.algorithms_dir.is_dir():
                 pass

        for widget in widgets_to_remove_from_local_list:
            self.opt_local_algo_list_layout.removeWidget(widget)
            widget.deleteLater()

        if hasattr(self, 'optimizer_local_algorithms_managed_ui'):
            self.optimizer_local_algorithms_managed_ui.clear()
        

        self.loaded_algorithms.clear()
        self.update_status("Optimizer: Đang quét lại thuật toán trên máy...")

        if not self.algorithms_dir.is_dir():
            QMessageBox.critical(main_window, "Lỗi Thư Mục (Optimizer)", f"Không tìm thấy thư mục thuật toán:\n{self.algorithms_dir}")
            self._populate_optimizer_local_algorithms_list()
            return

        try:
            algo_files_py = [f for f in self.algorithms_dir.glob('*.py') if f.is_file() and f.name not in ["__init__.py", "base.py"]]
            algo_files_json = [f for f in self.algorithms_dir.glob('*.json') if f.is_file() and is_json_bundle_file(f)]
            optimizer_logger.debug(f"Optimizer: Found {len(algo_files_py)} py and {len(algo_files_json)} json potential algorithm files in {self.algorithms_dir}")
        except Exception as e:
            QMessageBox.critical(main_window, "Lỗi (Optimizer)", f"Lỗi đọc thư mục thuật toán:\n{e}")
            self._populate_optimizer_local_algorithms_list()
            return

        count_success, count_fail = 0, 0
        data_copy_for_init = copy.deepcopy(self.results_data) if self.results_data else []
        cache_dir_for_init = self.calculate_dir

        for f_path in algo_files_py:
            module_name = f"algorithms.{f_path.stem}"
            instance = None
            config = None
            class_name_found = None
            module_obj = None
            display_name_key = f"Unknown ({f_path.name})"

            optimizer_logger.debug(f"Optimizer: Processing file: {f_path.name}")
            try:
                if module_name in sys.modules:
                    optimizer_logger.debug(f"Optimizer: Reloading module: {module_name}")
                    try: module_obj = reload(sys.modules[module_name])
                    except Exception:
                        try: del sys.modules[module_name]
                        except KeyError: pass
                        module_obj = None
                else:
                    optimizer_logger.debug(f"Optimizer: Importing module for the first time: {module_name}")
                
                if module_obj is None:
                    spec = util.spec_from_file_location(module_name, f_path)
                    if spec and spec.loader:
                        module_obj = util.module_from_spec(spec)
                        sys.modules[module_name] = module_obj
                        spec.loader.exec_module(module_obj)
                    else: raise ImportError(f"Optimizer: Could not create spec/loader for {module_name} from {f_path}")
                if not module_obj: raise ImportError(f"Optimizer: Module object is None for {f_path.name}")

                found_class_obj = None
                for name, obj in inspect.getmembers(module_obj):
                    if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == module_name:
                        found_class_obj = obj; class_name_found = name
                        display_name_key = f"{class_name_found} ({f_path.name})"
                        break
                
                if found_class_obj:
                    try:
                        instance = found_class_obj(data_results_list=data_copy_for_init, cache_dir=cache_dir_for_init)
                        config = instance.get_config()
                        if not isinstance(config, dict): config = {"description": "Config Error", "parameters": {}}
                        self.loaded_algorithms[display_name_key] = {
                            'instance': instance, 'path': f_path, 'config': config,
                            'class_name': class_name_found, 'module_name': module_name
                        }
                        count_success += 1
                    except Exception as init_err:
                        optimizer_logger.error(f"Optimizer: Error init/config class {class_name_found} from {f_path.name}: {init_err}", exc_info=True)
                        if display_name_key in self.loaded_algorithms: del self.loaded_algorithms[display_name_key]
                        count_fail += 1
                else:
                    optimizer_logger.warning(f"Optimizer: No valid BaseAlgorithm subclass in {f_path.name}")
                    count_fail += 1
            except ImportError as imp_err:
                optimizer_logger.error(f"Optimizer: Import error {f_path.name}: {imp_err}", exc_info=False)
                count_fail += 1
            except Exception as load_err:
                optimizer_logger.error(f"Optimizer: General error {f_path.name}: {load_err}", exc_info=True)
                count_fail += 1
            finally:
                if not (found_class_obj and display_name_key in self.loaded_algorithms) and module_name in sys.modules:
                    if sys.modules[module_name] == module_obj:
                        try: del sys.modules[module_name]
                        except KeyError: pass

        for j_path in algo_files_json:
            display_name_key = f"Unknown ({j_path.name})"
            optimizer_logger.debug(f"Optimizer: Processing JSON bundle file: {j_path.name}")
            try:
                instance = JsonBundleAlgorithm(json_path=j_path, data_results_list=data_copy_for_init, cache_dir=cache_dir_for_init)
                config = instance.get_config()
                algo_title = f"[TCS] {instance.bundle_name or j_path.stem}"
                display_name_key = f"{algo_title} ({j_path.name})"
                self.loaded_algorithms[display_name_key] = {
                    'instance': instance, 'path': j_path, 'config': config,
                    'class_name': algo_title, 'module_name': f"algorithms.{j_path.stem}"
                }
                count_success += 1
                optimizer_logger.debug(f"Optimizer: Successfully registered JSON bundle: {display_name_key}")
            except Exception as j_err:
                optimizer_logger.error(f"Optimizer: Error loading JSON bundle {j_path.name}: {j_err}", exc_info=True)
                if display_name_key in self.loaded_algorithms: del self.loaded_algorithms[display_name_key]
                count_fail += 1

        self._populate_optimizer_local_algorithms_list()

        status_msg = f"Optimizer: Tải {count_success} thuật toán (local)"
        if count_fail > 0:
            status_msg += f" (lỗi: {count_fail})"
        self.update_status(status_msg)

        if count_fail > 0:
            QMessageBox.warning(main_window, "Lỗi Tải (Optimizer)", f"Lỗi tải {count_fail} file thuật toán cho Optimizer.\nKiểm tra log.")
        
        self.check_resume_possibility()
        optimizer_logger.info("Optimizer: Algorithm loading process finished.")

    def _create_optimizer_local_algorithm_card_qt(self,
                                                display_name_key: str,
                                                algo_name_for_display: str,
                                                description: str,
                                                algo_path: Path,
                                                algo_id: str | None,
                                                algo_date_str: str | None):
        optimizer_logger.debug(f"Optimizer: Creating local algo card UI for: {algo_name_for_display} (key: {display_name_key})")
        try:
            if not hasattr(self, 'opt_local_algo_list_layout'):
                optimizer_logger.error("Optimizer: opt_local_algo_list_layout not found, cannot add card.")
                return

            card_frame = QFrame()
            card_frame.setObjectName("CardFrame")
            card_layout = QVBoxLayout(card_frame)
            card_layout.setContentsMargins(8, 8, 8, 8)
            card_layout.setSpacing(5)

            clean_name = algo_name_for_display
            is_tcs = (algo_path and algo_path.suffix.lower() == '.json') or clean_name.startswith('[TCS]')
            if clean_name.startswith('[TCS] '):
                clean_name = clean_name[6:]
            elif clean_name.startswith('[TCS]'):
                clean_name = clean_name[5:]

            id_str = f" (ID: {algo_id})" if algo_id else ""
            if is_tcs:
                name_label_text_ui = f"<b style='color: #16a34a;'>[TCS]</b> {clean_name}{id_str}"
            else:
                name_label_text_ui = f"{clean_name}{id_str}"
            name_label = QLabel(name_label_text_ui)
            name_label.setFont(self.main_app.get_qfont("bold"))
            name_label.setWordWrap(True)
            name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            name_label.setMinimumWidth(1)
            card_layout.addWidget(name_label)

            desc_label = QLabel(description)
            desc_label.setFont(self.main_app.get_qfont("small"))
            desc_label.setWordWrap(True)
            desc_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            desc_label.setMinimumWidth(1)
            card_layout.addWidget(desc_label)
            
            file_info_parts = [f"File: {algo_path.name}"]
            if algo_date_str:
                file_info_parts.append(f"Ngày: {algo_date_str}")
            file_label = QLabel(" - ".join(file_info_parts))
            file_label.setFont(self.main_app.get_qfont("italic_small"))
            file_label.setStyleSheet("color: #6c757d;")
            file_label.setWordWrap(True)
            file_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            file_label.setMinimumWidth(1)
            card_layout.addWidget(file_label)

            button_container = QWidget()
            button_layout_h = QHBoxLayout(button_container)
            button_layout_h.setContentsMargins(0, 5, 0, 0)
            button_layout_h.setSpacing(5)

            edit_button = QPushButton("✍️ Sửa")
            edit_button.setObjectName("ListAccentButton")
            edit_button.setToolTip(f"Chỉnh sửa tham số của: {algo_name_for_display}")
            edit_button.clicked.connect(lambda checked=False, dn_key=display_name_key: self.trigger_select_for_edit(dn_key))

            optimize_button = QPushButton("🚀 Tối ưu")
            optimize_button.setObjectName("ListAccentButton")
            optimize_button.setToolTip(f"Tối ưu hóa thuật toán: {algo_name_for_display}")
            optimize_button.clicked.connect(lambda checked=False, dn_key=display_name_key: self.trigger_select_for_optimize(dn_key))
            
            delete_button = QPushButton("❎ Xóa")
            delete_button.setObjectName("DangerButton")
            delete_button.setToolTip(f"Xóa file thuật toán: {algo_path.name}")
            delete_button.clicked.connect(lambda checked=False, path_to_delete=algo_path: self._handle_delete_optimizer_local_algorithm(path_to_delete))

            button_layout_h.addWidget(edit_button, 1)
            button_layout_h.addWidget(optimize_button, 1)
            button_layout_h.addWidget(delete_button, 1)
            
            button_fixed_height = 32
            edit_button.setFixedHeight(button_fixed_height)
            edit_button.setMinimumWidth(85)
            optimize_button.setFixedHeight(button_fixed_height)
            optimize_button.setMinimumWidth(105)
            delete_button.setFixedHeight(button_fixed_height)
            delete_button.setMinimumWidth(85)
            

            card_layout.addWidget(button_container)

            self.opt_local_algo_list_layout.addWidget(card_frame)
            
            if not hasattr(self, 'optimizer_local_algorithms_managed_ui'):
                 self.optimizer_local_algorithms_managed_ui = {}
            self.optimizer_local_algorithms_managed_ui[str(algo_path)] = card_frame

        except Exception as e:
            optimizer_logger.error(f"Optimizer: Error creating local algorithm card UI for '{algo_name_for_display}': {e}", exc_info=True)

    
    def reload_algorithms(self):
        optimizer_logger.info("Optimizer: Reloading algorithms (PyQt5)...")
        self.selected_algorithm_for_edit = None
        self.selected_algorithm_for_optimize = None
        self.disable_edit_optimize_tabs()
        self._clear_editor_fields()
        self._reset_advanced_opt_settings()
        self._clear_combination_selection()
        self.load_algorithms()
        self.check_resume_possibility()

    

    
    def trigger_select_for_edit(self, display_name):
        main_window = self.get_main_window()
        if display_name not in self.loaded_algorithms:
            QMessageBox.warning(main_window, "Lỗi", f"Không tìm thấy: {display_name}")
            return

        self.selected_algorithm_for_edit = display_name
        self.selected_algorithm_for_optimize = None
        self._clear_advanced_opt_fields()
        self._clear_combination_selection()

        self.populate_editor(display_name)

        if hasattr(self, 'tab_widget'):
            edit_tab_widget = getattr(self, 'tab_edit', None)
            optimize_tab_widget = getattr(self, 'tab_optimize', None)

            if edit_tab_widget:
                edit_tab_index = self.tab_widget.indexOf(edit_tab_widget)
                if edit_tab_index != -1:
                    self.tab_widget.setTabEnabled(edit_tab_index, True)
                    self.tab_widget.setCurrentIndex(edit_tab_index)
                    optimizer_logger.debug(f"Enabled and switched to Edit tab (index {edit_tab_index}).")
                else:
                    optimizer_logger.error("Could not find Edit tab to enable/switch.")
            
            if optimize_tab_widget:
                optimize_tab_index = self.tab_widget.indexOf(optimize_tab_widget)
                if optimize_tab_index != -1:
                    self.tab_widget.setTabEnabled(optimize_tab_index, False)
                    optimizer_logger.debug(f"Disabled Optimize tab (index {optimize_tab_index}).")
            
        else:
            optimizer_logger.error("OptimizerEmbedded.tab_widget not found in trigger_select_for_edit.")


        self.update_status(f"Optimizer: Đang chỉnh sửa: {self.loaded_algorithms[display_name]['class_name']}")
        self.check_resume_possibility()

    def trigger_select_for_optimize(self, display_name):

        main_window = self.get_main_window()
        if not self.main_app:
            optimizer_logger.error("Main app instance not found in trigger_select_for_optimize.")
            return
        if display_name not in self.loaded_algorithms:
            QMessageBox.warning(main_window, "Lỗi", f"Không tìm thấy thuật toán: {display_name}")
            return

        if self.optimizer_running:
            if self.selected_algorithm_for_optimize == display_name:
                optimizer_logger.debug(f"Optimizer running/paused for '{display_name}'. Switching to Optimize tab view.")
                try:
                    optimize_tab_index = -1
                    for i in range(self.tab_widget.count()):
                        if self.tab_widget.tabText(i).strip().startswith("Tối Ưu Hóa"):
                            optimize_tab_index = i
                            break
                    if optimize_tab_index != -1:
                        if not self.tab_widget.isTabEnabled(optimize_tab_index):
                             self.tab_widget.setTabEnabled(optimize_tab_index, True)
                        self.tab_widget.setCurrentIndex(optimize_tab_index)
                    else:
                        optimizer_logger.error("Could not find Optimize tab index.")
                except Exception as e_switch:
                     optimizer_logger.error(f"Error switching to Optimize tab: {e_switch}")
                return

            else:
                running_algo_short_name = self.selected_algorithm_for_optimize.split(' (')[0] if self.selected_algorithm_for_optimize else "khác"
                optimizer_logger.warning(f"Optimizer already running for '{self.selected_algorithm_for_optimize}'. Cannot start new optimization for '{display_name}'.")
                QMessageBox.critical(main_window, "Đang Chạy",
                                     f"Quá trình tối ưu hóa cho thuật toán '{running_algo_short_name}' đang chạy.\n\n"
                                     f"Vui lòng dừng quá trình hiện tại trước khi bắt đầu tối ưu một thuật toán khác.")
                return

        optimizer_logger.info(f"Selecting algorithm '{display_name}' for optimization setup.")
        self.selected_algorithm_for_optimize = display_name
        self.selected_algorithm_for_edit = None
        self._clear_editor_fields()

        self.populate_optimizer_info(display_name)
        self._populate_advanced_optimizer_settings()
        self._populate_combination_selection()

        try:
            edit_tab_index = -1
            optimize_tab_index = -1
            for i in range(self.tab_widget.count()):
                 tab_text = self.tab_widget.tabText(i).strip()
                 if tab_text.startswith("Chỉnh Sửa"):
                     edit_tab_index = i
                 elif tab_text.startswith("Tối Ưu Hóa"):
                     optimize_tab_index = i

            if edit_tab_index != -1: self.tab_widget.setTabEnabled(edit_tab_index, False)
            if optimize_tab_index != -1:
                 self.tab_widget.setTabEnabled(optimize_tab_index, True)
                 self.tab_widget.setCurrentIndex(optimize_tab_index)
            else:
                 optimizer_logger.error("Could not find Optimize tab index to enable/switch.")

        except Exception as e_tab:
             optimizer_logger.error(f"Error enabling/switching tabs: {e_tab}")


        algo_class_name = self.loaded_algorithms[display_name].get('class_name', display_name)
        self.update_status(f"Optimizer: Sẵn sàng tối ưu: {algo_class_name}")
        self._load_optimization_log()
        self.check_resume_possibility()

    def disable_edit_optimize_tabs(self):
        if hasattr(self, 'tab_widget'):
            edit_tab_widget = getattr(self, 'tab_edit', None)
            optimize_tab_widget = getattr(self, 'tab_optimize', None)

            if edit_tab_widget:
                edit_tab_index = self.tab_widget.indexOf(edit_tab_widget)
                if edit_tab_index != -1:
                    self.tab_widget.setTabEnabled(edit_tab_index, False)
                    optimizer_logger.debug(f"Disabled Edit tab (index {edit_tab_index}) in disable_edit_optimize_tabs.")
            
            if optimize_tab_widget:
                optimize_tab_index = self.tab_widget.indexOf(optimize_tab_widget)
                if optimize_tab_index != -1:
                    self.tab_widget.setTabEnabled(optimize_tab_index, False)
                    optimizer_logger.debug(f"Disabled Optimize tab (index {optimize_tab_index}) in disable_edit_optimize_tabs.")
            
            gemini_tab_widget_frame = getattr(self, 'tab_gemini_builder_frame', None)
            if gemini_tab_widget_frame and HAS_GEMINI:
                gemini_tab_index = self.tab_widget.indexOf(gemini_tab_widget_frame)
                if gemini_tab_index != -1:
                    self.tab_widget.setTabEnabled(gemini_tab_index, True)
                    optimizer_logger.debug(f"Ensured Gemini tab (index {gemini_tab_index}) is enabled in disable_edit_optimize_tabs.")
                else:
                    optimizer_logger.warning("Could not find Gemini tab to ensure it's enabled in disable_edit_optimize_tabs.")

            self._clear_advanced_opt_fields()
            self._clear_combination_selection()

        self.selected_algorithm_for_edit = None
        self.selected_algorithm_for_optimize = None
        self.check_resume_possibility()

    def populate_editor(self, display_name):
        self._clear_editor_fields()
        if display_name not in self.loaded_algorithms:
            return

        algo_data = self.loaded_algorithms[display_name]
        instance = algo_data['instance']
        config = algo_data['config']
        class_name = algo_data['class_name']

        self.edit_algo_name_label.setText(f"{class_name} ({algo_data['path'].name})")

        self.edit_algo_desc_label.setText(config.get("description", "N/A"))

        try:
            docstring = inspect.getdoc(instance.__class__)
            self.edit_explain_text.setPlainText(docstring if docstring else "Không có giải thích.")
        except Exception as e:
            self.edit_explain_text.setPlainText(f"Lỗi lấy docstring: {e}")

        parameters = config.get("parameters", {})
        self.editor_param_widgets = {}
        self.editor_original_params = copy.deepcopy(parameters)

        for name, value in parameters.items():
            if isinstance(value, (int, float)):
                param_label = QLabel(f"{name}:")
                param_input = QLineEdit(str(value))
                param_input.setAlignment(Qt.AlignRight)
                param_input.setFixedWidth(120)

                if isinstance(value, int):
                    param_input.setValidator(self.int_validator)
                else:
                    param_input.setValidator(self.double_validator)

                self.edit_param_layout.addRow(param_label, param_input)
                self.editor_param_widgets[name] = param_input


    def _clear_editor_fields(self):
        if hasattr(self, 'edit_algo_name_label'):
            self.edit_algo_name_label.setText("...")
        if hasattr(self, 'edit_algo_desc_label'):
            self.edit_algo_desc_label.setText("...")
        if hasattr(self, 'edit_explain_text'):
            self.edit_explain_text.clear()

        if hasattr(self, 'edit_param_layout'):
            while self.edit_param_layout.count() > 0:
                self.edit_param_layout.removeRow(0)

        self.editor_param_widgets = {}
        self.editor_original_params = {}

    def cancel_edit(self):
        self.selected_algorithm_for_edit = None
        self._clear_editor_fields()
        self.disable_edit_optimize_tabs()
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setCurrentIndex(0)
        self.update_status("Optimizer: Đã hủy chỉnh sửa.")

    def _refresh_optimizer_algo_lists(self):
        if self._is_refreshing_algos:
            optimizer_logger.info("Optimizer: Refresh algorithms (local & online) already in progress. Ignoring request.")
            return

        self._is_refreshing_algos = True
        if hasattr(self, 'opt_algo_refresh_button'):
            self.opt_algo_refresh_button.setEnabled(False)

        optimizer_logger.info("Refreshing Optimizer's local and online algorithm lists...")
        self.update_status("Đang làm mới danh sách thuật toán (Optimizer)...")
        QApplication.processEvents()

        try:
            self.load_algorithms()
            self._fetch_and_populate_optimizer_online_algorithms_list()
            self.update_status("Làm mới danh sách thuật toán (Optimizer) hoàn tất.")
        except Exception as e:
            optimizer_logger.error(f"Error during _refresh_optimizer_algo_lists: {e}", exc_info=True)
            self.update_status(f"Lỗi khi làm mới danh sách: {type(e).__name__}")
        finally:
            self._is_refreshing_algos = False
            if hasattr(self, 'opt_algo_refresh_button'):
                self.opt_algo_refresh_button.setEnabled(True)

    def _populate_optimizer_local_algorithms_list(self):
        optimizer_logger.info("Optimizer: Populating Optimizer's local algorithms list for its 'Select Algorithm' tab...")

        if not hasattr(self, 'opt_local_algo_list_layout'):
            optimizer_logger.error("Optimizer: opt_local_algo_list_layout not found in OptimizerEmbedded during populate.")
            return


        if not self.loaded_algorithms:
            if not hasattr(self, 'opt_initial_local_algo_label') or self.opt_initial_local_algo_label is None:
                self.opt_initial_local_algo_label = QLabel("Không có thuật toán nào trên máy.")
                self.opt_initial_local_algo_label.setStyleSheet("font-style: italic; color: #6c757d;")
                self.opt_initial_local_algo_label.setAlignment(Qt.AlignCenter)
                if self.opt_local_algo_list_layout.indexOf(self.opt_initial_local_algo_label) == -1:
                    self.opt_local_algo_list_layout.addWidget(self.opt_initial_local_algo_label)
            else:
                self.opt_initial_local_algo_label.setText("Không có thuật toán nào trên máy.")
                self.opt_initial_local_algo_label.setVisible(True)
                if self.opt_local_algo_list_layout.indexOf(self.opt_initial_local_algo_label) == -1:
                    for i in reversed(range(self.opt_local_algo_list_layout.count())):
                        item = self.opt_local_algo_list_layout.itemAt(i)
                        widget = item.widget()
                        if widget and widget != self.opt_initial_local_algo_label :
                            self.opt_local_algo_list_layout.removeWidget(widget)
                            widget.deleteLater()
                    self.opt_local_algo_list_layout.addWidget(self.opt_initial_local_algo_label)


            optimizer_logger.info("Optimizer: No local algorithms loaded. Displaying placeholder message.")
            return
        else:
            if hasattr(self, 'opt_initial_local_algo_label') and self.opt_initial_local_algo_label is not None:
                self.opt_initial_local_algo_label.setVisible(False)
                optimizer_logger.debug("Optimizer: Local algorithms found. Hiding/removing placeholder label.")


        for display_name_key, algo_data in self.loaded_algorithms.items():
            try:
                algo_path = algo_data['path']
                if algo_path.suffix.lower() == '.json':
                    with open(algo_path, 'r', encoding='utf-8') as f:
                        bundle_data = json.load(f)
                    algo_name_display = f"[TCS] {bundle_data.get('bundle_name') or algo_path.stem}"
                    description = bundle_data.get("ai_advisor_summary") or algo_data.get('config', {}).get('description') or "Thuật toán JSON Bundle."
                    algo_id = bundle_data.get("bundle_id")
                    algo_date_str = bundle_data.get("trained_date", "")
                else:
                    content = algo_path.read_text(encoding='utf-8')
                    metadata = self.main_app._extract_metadata_from_py_content(content)
                    algo_name_display = metadata.get("name") or algo_data.get('class_name') or algo_path.stem
                    description = metadata.get("description") or algo_data.get('config', {}).get('description') or "Không có mô tả."
                    algo_id = metadata.get("id")
                    algo_date_str = metadata.get("date_str")

                self._create_optimizer_local_algorithm_card_qt(
                    display_name_key,
                    algo_name_display,
                    description,
                    algo_path,
                    algo_id,
                    algo_date_str
                )
            except Exception as e:
                optimizer_logger.error(f"Optimizer: Error creating UI card for local algo '{display_name_key}' in Optimizer's list: {e}", exc_info=True)

    def sync_data(self):
        """
        Thay vì viết lại logic, hàm này sẽ gọi trực tiếp tính năng đồng bộ 
        từ Main App (LotteryPredictionApp) để tận dụng cơ chế dọn dẹp file cũ.
        """
        if hasattr(self, 'main_app') and self.main_app:
            self.main_app.sync_data()
        else:
            QMessageBox.warning(self, "Lỗi Liên Kết", "Không tìm thấy kết nối đến ứng dụng chính (Main App).")

    def _fetch_and_populate_optimizer_online_algorithms_list(self):
        optimizer_logger.info("Optimizer: (Safe) Fetching and populating its online algorithms list...")

        if not hasattr(self, 'opt_online_algo_scroll_area'):
            optimizer_logger.error("Optimizer: opt_online_algo_scroll_area not found.")
            return

        old_content_widget = self.opt_online_algo_scroll_area.takeWidget()
        if old_content_widget:
            old_content_widget.deleteLater()

        new_content_widget = QWidget()
        self.opt_online_algo_list_layout = QVBoxLayout(new_content_widget)
        self.opt_online_algo_list_layout.setAlignment(Qt.AlignTop)
        self.opt_online_algo_list_layout.setSpacing(8)
        self.opt_online_algo_scroll_area.setWidget(new_content_widget)

        status_label = QLabel("Đang tải danh sách thuật toán online...")
        status_label.setStyleSheet("font-style: italic; color: #007bff; padding: 20px;")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setWordWrap(True)
        self.opt_online_algo_list_layout.addWidget(status_label)
        QApplication.processEvents()

        if hasattr(self, 'optimizer_online_algorithms_ui'):
            self.optimizer_online_algorithms_ui.clear()
        else:
            self.optimizer_online_algorithms_ui = {}

        if not self.main_app or not hasattr(self.main_app, 'config'):
            optimizer_logger.error("Optimizer: main_app or its config not available.")
            status_label.setText("Lỗi: Không thể truy cập cấu hình ứng dụng chính.")
            status_label.setStyleSheet("color: red; padding: 20px; font-style: italic;")
            return

        algo_list_url = self.main_app.config.get('DATA', 'algo_list_url', fallback="")
        if not algo_list_url:
            optimizer_logger.error("Optimizer: Online algorithm list URL is not configured.")
            status_label.setText("Lỗi: URL danh sách online chưa được cấu hình (trong Cài đặt của App).")
            status_label.setStyleSheet("color: red; padding: 20px; font-style: italic;")
            return

        online_list_content = self.main_app._fetch_online_content(algo_list_url, service_type="update_check")

        if online_list_content is None:
            status_label.setText(f"Lỗi tải danh sách online từ URL đã cấu hình.<br>(Kiểm tra kết nối mạng và URL: {algo_list_url})")
            status_label.setStyleSheet("color: red; padding: 20px; font-style: italic;")
            return

        if status_label.parentWidget() is not None:
            self.opt_online_algo_list_layout.removeWidget(status_label)
        status_label.deleteLater()

        parsed_online_algos = []
        if online_list_content:
            line_pattern = re.compile(r"\[([^\]]+?)\]-\[([^\]]+?)\]-\[([^\]]+?)\]-\[(ID:\s*\d{6})\]", re.IGNORECASE)
            lines = online_list_content.splitlines()
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                match = line_pattern.fullmatch(line)
                if match:
                    parsed_url, name, date_str, id_full_part = match.group(1).strip(), match.group(2).strip(), match.group(3).strip(), match.group(4).strip()
                    id_numeric_match = re.search(r"\d{6}", id_full_part)
                    if id_numeric_match:
                        actual_id = id_numeric_match.group(0)
                        parsed_online_algos.append({"url": parsed_url, "name": name, "date_str": date_str, "id": actual_id})
                    else:
                        optimizer_logger.warning(f"Optimizer: Cannot extract ID from '{id_full_part}' in line: {line}")
                else:
                    optimizer_logger.warning(f"Optimizer: Skipping malformed online algo line: '{line}'")

        if not parsed_online_algos:
            no_online_algos_label = QLabel("<div style='text-align: center;'><br><br><br><br>Không tìm thấy thuật toán nào trong danh sách online hoặc định dạng file không đúng.</div>")
            no_online_algos_label.setTextFormat(Qt.RichText)
            no_online_algos_label.setStyleSheet("font-style: italic; color: #6c757d; padding: 20px;")
            no_online_algos_label.setAlignment(Qt.AlignCenter)
            self.opt_online_algo_list_layout.addWidget(no_online_algos_label)
            return

        optimizer_logger.info(f"Optimizer: Parsed {len(parsed_online_algos)} online algorithms. Creating UI cards...")
        for online_algo_data in parsed_online_algos:
            self._create_optimizer_online_algorithm_card_qt(online_algo_data)

        optimizer_logger.info("Optimizer: Finished populating its online algorithms list.")

    def _get_optimizer_local_algorithm_metadata_by_id(self, target_id: str) -> tuple[Path | None, dict | None]:
         """Optimizer: Finds a local algorithm (from its own loaded_algorithms) by ID."""
         if not target_id: return None, None
         for algo_data in self.loaded_algorithms.values():
             algo_path = algo_data.get('path')
             if algo_path:
                 try:
                     content = algo_path.read_text(encoding='utf-8')
                     metadata = self.main_app._extract_metadata_from_py_content(content)
                     if metadata.get("id") == target_id:
                         return algo_path, metadata
                 except Exception:
                     continue
         return None, None

    def _create_optimizer_online_algorithm_card_qt(self, online_algo_data: dict):
         optimizer_logger.debug(f"Optimizer: Creating online algo card for: {online_algo_data.get('name')}")
         
         online_url = online_algo_data["url"]
         online_name = online_algo_data["name"]
         online_date_str = online_algo_data["date_str"]
         online_id = online_algo_data["id"]

         description = "Đang tải mô tả..."
         online_code_content = None
         try:
             import requests
             py_response = requests.get(online_url, timeout=10)
             py_response.raise_for_status()
             online_code_content = py_response.text
             metadata_from_online_code = self.main_app._extract_metadata_from_py_content(online_code_content)
             description = metadata_from_online_code.get("description") or "Không có mô tả trong code."
         except Exception as e_desc:
             description = f"Lỗi tải/xử lý mô tả: {type(e_desc).__name__}"
             optimizer_logger.warning(f"Optimizer: Failed to fetch/process desc for {online_name}: {e_desc}")

         card_frame = QFrame()
         card_frame.setObjectName("CardFrame")
         card_layout = QVBoxLayout(card_frame)
         name_label = QLabel(f"{online_name} (ID: {online_id})")
         name_label.setFont(self.main_app.get_qfont("bold"))
         card_layout.addWidget(name_label)
         desc_label = QLabel(description)
         desc_label.setFont(self.main_app.get_qfont("small")); desc_label.setWordWrap(True)
         card_layout.addWidget(desc_label)
         info_label = QLabel(f"Online Date: {online_date_str}")
         info_label.setFont(self.main_app.get_qfont("italic_small")); info_label.setStyleSheet("color: #5a5a5a;")
         card_layout.addWidget(info_label)

         button_container = QWidget()
         button_layout_h = QHBoxLayout(button_container)
         button_layout_h.setContentsMargins(0,5,0,0); button_layout_h.addStretch(1)

         local_algo_path, local_metadata = self._get_optimizer_local_algorithm_metadata_by_id(online_id)
         
         action_widget = None
         if local_algo_path and local_metadata:
             status_label_text = f"Đã có: {local_algo_path.name}"
             local_date_str = local_metadata.get("date_str")
             needs_update = False
             if local_date_str and online_date_str:
                 try:
                     online_dt = datetime.datetime.strptime(online_date_str, "%d/%m/%Y")
                     local_dt = datetime.datetime.strptime(local_date_str, "%d/%m/%Y")
                     if online_dt > local_dt: needs_update = True
                 except ValueError: pass
             
             if needs_update:
                 update_button = QPushButton("⬆️ Cập nhật")
                 update_button.setObjectName("AccentButton")
                 update_button.setToolTip(f"Cập nhật file local '{local_algo_path.name}'")
                 update_button.clicked.connect(lambda chk=False, o_data=online_algo_data, l_path=local_algo_path, o_content=online_code_content : self._handle_update_optimizer_online_algorithm(o_data, l_path, o_content))
                 action_widget = update_button
             else:
                 status_widget = QLabel(status_label_text + (" (Đã cập nhật)" if local_date_str else ""))
                 status_widget.setStyleSheet("color: green; font-style: italic;")
                 action_widget = status_widget
         else:
             download_button = QPushButton("⬇️ Tải về")
             download_button.setObjectName("AccentButton")
             download_button.setToolTip(f"Tải '{online_name}' vào thư mục algorithms của Optimizer")
             download_button.clicked.connect(lambda chk=False, o_data=online_algo_data, o_content=online_code_content : self._handle_download_optimizer_online_algorithm(o_data, o_content))
             action_widget = download_button
         
         if action_widget: button_layout_h.addWidget(action_widget)
         card_layout.addWidget(button_container)
         
         self.opt_online_algo_list_layout.addWidget(card_frame)
         self.optimizer_online_algorithms_ui[online_url] = card_frame


    def _handle_download_optimizer_online_algorithm(self, online_algo_data: dict, online_code_content: str | None = None):
         online_url = online_algo_data["url"]
         online_name = online_algo_data["name"]
         
         filename_from_url_obj = Path(online_url)
         target_filename = filename_from_url_obj.stem + ".py"
         save_path = self.algorithms_dir / target_filename

         optimizer_logger.info(f"Optimizer: Downloading '{online_name}' to {save_path}")
         self.update_status(f"Optimizer: Đang tải về {target_filename}...")
         QApplication.processEvents()

         try:
             final_code_content = online_code_content
             if final_code_content is None:
                 import requests
                 response = requests.get(online_url, timeout=15)
                 response.raise_for_status()
                 final_code_content = response.text
             
             if not isinstance(final_code_content, str):
                 raise ValueError("Nội dung tải về không phải là chuỗi.")

             normalized_content = final_code_content.replace('\r\n', '\n').replace('\r', '\n')
             save_path.write_text(normalized_content, encoding='utf-8', newline='\n')
             optimizer_logger.info(f"Optimizer: Downloaded and saved to {save_path}")
             QMessageBox.information(self.get_main_window(), "Tải Thành Công (Optimizer)", f"Đã tải '{target_filename}' vào '{self.algorithms_dir.name}'.")
             
             self._refresh_optimizer_algo_lists()
             if self.main_app:
                 self.main_app.reload_algorithms()
                 if hasattr(self.main_app, '_refresh_algo_management_page'):
                     self.main_app._refresh_algo_management_page()
             self.update_status(f"Optimizer: Tải thành công {target_filename}")

         except Exception as e:
             optimizer_logger.error(f"Optimizer: Error downloading/saving {online_name}: {e}", exc_info=True)
             QMessageBox.critical(self.get_main_window(), "Lỗi Tải (Optimizer)", f"Lỗi khi tải {target_filename}:\n{e}")
             self.update_status(f"Optimizer: Lỗi tải {target_filename}")


    def _handle_update_optimizer_online_algorithm(self, online_algo_data: dict, local_algo_path: Path, online_code_content: str | None = None):
         online_url = online_algo_data["url"]
         optimizer_logger.info(f"Optimizer: Updating '{local_algo_path.name}' from {online_url}")
         self.update_status(f"Optimizer: Đang cập nhật {local_algo_path.name}...")
         QApplication.processEvents()

         try:
             final_code_content = online_code_content
             if final_code_content is None:
                 import requests
                 response = requests.get(online_url, timeout=15)
                 response.raise_for_status()
                 final_code_content = response.text

             if not isinstance(final_code_content, str):
                 raise ValueError("Nội dung tải về không phải là chuỗi.")

             backup_path = local_algo_path.with_suffix(local_algo_path.suffix + ".bak")
             if local_algo_path.exists(): shutil.copy2(local_algo_path, backup_path)

             normalized_content = final_code_content.replace('\r\n', '\n').replace('\r', '\n')
             local_algo_path.write_text(normalized_content, encoding='utf-8', newline='\n')
             optimizer_logger.info(f"Optimizer: Updated {local_algo_path}")
             QMessageBox.information(self.get_main_window(), "Cập Nhật Thành Công (Optimizer)", f"Đã cập nhật:\n{local_algo_path.name}")

             self._refresh_optimizer_algo_lists()
             if self.main_app:
                 self.main_app.reload_algorithms()
             self.update_status(f"Optimizer: Cập nhật thành công {local_algo_path.name}")

         except Exception as e:
             optimizer_logger.error(f"Optimizer: Error updating {local_algo_path.name}: {e}", exc_info=True)
             QMessageBox.critical(self.get_main_window(), "Lỗi Cập Nhật (Optimizer)", f"Lỗi khi cập nhật {local_algo_path.name}:\n{e}")
             self.update_status(f"Optimizer: Lỗi cập nhật {local_algo_path.name}")

    def save_edited_copy(self):
        if not self.selected_algorithm_for_edit: return
        display_name = self.selected_algorithm_for_edit
        main_window = self.get_main_window()

        if display_name not in self.loaded_algorithms:
            QMessageBox.critical(main_window, "Lỗi", "Thuật toán không tồn tại.")
            return

        algo_data = self.loaded_algorithms[display_name]
        original_path = algo_data['path']
        class_name = algo_data['class_name']
        modified_params = {}

        try:
            for name, widget in self.editor_param_widgets.items():
                value_str = widget.text().strip()
                original_value = self.editor_original_params.get(name)
                if isinstance(original_value, float):
                    modified_params[name] = float(value_str)
                elif isinstance(original_value, int):
                    modified_params[name] = int(value_str)
        except ValueError as e:
            QMessageBox.critical(main_window, "Giá Trị Lỗi", f"Lỗi nhập số: {e}")
            return
        except Exception as e:
             QMessageBox.critical(main_window, "Lỗi Giao Diện", f"Lỗi đọc giá trị tham số: {e}")
             return

        final_params_for_save = self.editor_original_params.copy()
        final_params_for_save.update(modified_params)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if original_path.suffix.lower() == '.json':
            suggested_filename = f"{original_path.stem}_edited_{timestamp}.json"
            save_path_str, _ = QFileDialog.getSaveFileName(
                main_window,
                "Lưu Bản Sao Thuật Toán Đã Chỉnh Sửa",
                str(self.algorithms_dir / suggested_filename),
                "JSON files (*.json);;All files (*.*)"
            )
            if not save_path_str:
                return
            save_path = Path(save_path_str)
            if save_path.resolve() == original_path.resolve():
                QMessageBox.critical(main_window, "Lỗi", "Không thể ghi đè file gốc.")
                return
            try:
                with open(original_path, 'r', encoding='utf-8') as f:
                    bundle_data = json.load(f)
                if "config" not in bundle_data: bundle_data["config"] = {}
                for k, v in final_params_for_save.items():
                    if k.startswith("weight_"):
                        wid = k.replace("weight_", "")
                        if "best_individual" in bundle_data and "weights" in bundle_data["best_individual"]:
                            for full_wid in bundle_data["best_individual"]["weights"].keys():
                                if full_wid.startswith(wid):
                                    bundle_data["best_individual"]["weights"][full_wid] = v
                    elif k in bundle_data["config"]:
                        bundle_data["config"][k] = v
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(bundle_data, f, indent=2, ensure_ascii=False)
                QMessageBox.information(main_window, "Lưu Thành Công", f"Đã lưu bản sao: {save_path.name}\n'Tải lại thuật toán' để dùng.")
                self.update_status(f"Optimizer: Đã lưu bản sao: {save_path.name}")
                return
            except Exception as e:
                optimizer_logger.error(f"Error saving edited JSON bundle: {e}", exc_info=True)
                QMessageBox.critical(main_window, "Lỗi Lưu File", f"Không thể lưu bản sao:\n{e}")
                return

        suggested_filename = f"{original_path.stem}_edited_{timestamp}.py"

        save_path_str, _ = QFileDialog.getSaveFileName(
            main_window,
            "Lưu Bản Sao Thuật Toán Đã Chỉnh Sửa",
            str(self.algorithms_dir / suggested_filename),
            "Python files (*.py);;All files (*.*)"
        )

        if not save_path_str:
            return

        save_path = Path(save_path_str)
        if save_path.resolve() == original_path.resolve():
            QMessageBox.critical(main_window, "Lỗi", "Không thể ghi đè file gốc.")
            return

        try:
            source_code = original_path.read_text(encoding='utf-8')
            modified_source = self.modify_algorithm_source_ast(source_code, class_name, final_params_for_save)
            if modified_source is None:
                raise ValueError("AST modification failed.")

            save_path.write_text(modified_source, encoding='utf-8')
            QMessageBox.information(main_window, "Lưu Thành Công", f"Đã lưu bản sao: {save_path.name}\n'Tải lại thuật toán' để dùng.")
            self.update_status(f"Optimizer: Đã lưu bản sao: {save_path.name}")
        except Exception as e:
            optimizer_logger.error(f"Error saving edited copy: {e}", exc_info=True)
            QMessageBox.critical(main_window, "Lỗi Lưu File", f"Không thể lưu bản sao:\n{e}")


    def _handle_delete_optimizer_local_algorithm(self, algo_path_to_delete: Path):
        optimizer_logger.info(f"Optimizer: Request to delete local algorithm file: {algo_path_to_delete}")
        
        if not algo_path_to_delete or not isinstance(algo_path_to_delete, Path):
            optimizer_logger.error("Optimizer: Invalid path provided for deletion.")
            QMessageBox.critical(self.get_main_window(), "Lỗi Tham Số (Optimizer)", "Đường dẫn file không hợp lệ để xóa.")
            return

        main_window_ref = self.get_main_window()

        msg_box = QMessageBox(main_window_ref)
        msg_box.setWindowTitle("Xác nhận Xóa (Optimizer)")
        msg_box.setIcon(QMessageBox.Question)
        
        msg_box.setText("Bạn có chắc chắn muốn xóa file thuật toán này không?")
        
        informative_text_html = (
            f"<p><b>{algo_path_to_delete.name}</b></p>"
            "<p>Thao tác này sẽ xóa file vĩnh viễn và không thể hoàn tác!</p>"
        )
        msg_box.setInformativeText(informative_text_html)
        
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)

        reply = msg_box.exec_()
        
        if reply == QMessageBox.Yes:
            try:
                display_name_key_to_remove = None
                for dn_key, data_dict in self.loaded_algorithms.items():
                    if data_dict.get('path') == algo_path_to_delete:
                        display_name_key_to_remove = dn_key
                        break
                
                algo_path_to_delete.unlink()
                optimizer_logger.info(f"Optimizer: Successfully deleted algorithm file: {algo_path_to_delete}")
                self.update_status(f"Optimizer: Đã xóa {algo_path_to_delete.name}")

                if display_name_key_to_remove and display_name_key_to_remove in self.loaded_algorithms:
                    del self.loaded_algorithms[display_name_key_to_remove]
                    optimizer_logger.debug(f"Optimizer: Removed '{display_name_key_to_remove}' from self.loaded_algorithms.")
                
                path_str_key = str(algo_path_to_delete)
                if path_str_key in self.optimizer_local_algorithms_managed_ui:
                    del self.optimizer_local_algorithms_managed_ui[path_str_key]
                    optimizer_logger.debug(f"Optimizer: Removed UI reference for '{path_str_key}'.")
                
                self._populate_optimizer_local_algorithms_list() 
                
                if self.main_app:
                    self.main_app.reload_algorithms() 
                
                self.check_resume_possibility()

            except FileNotFoundError:
                optimizer_logger.warning(f"Optimizer: File to delete not found: {algo_path_to_delete} (possibly already deleted).")
                QMessageBox.warning(main_window_ref, "File Không Tìm Thấy (Optimizer)", f"Không tìm thấy file: {algo_path_to_delete.name}")
                self._populate_optimizer_local_algorithms_list()
                if self.main_app: self.main_app.reload_algorithms()
            except OSError as e_os:
                optimizer_logger.error(f"Optimizer: OSError deleting algorithm file {algo_path_to_delete}: {e_os}", exc_info=True)
                QMessageBox.critical(main_window_ref, "Lỗi Xóa File (Optimizer)", f"Không thể xóa file thuật toán:\n{algo_path_to_delete.name}\n\nLỗi hệ thống: {e_os}")
            except Exception as e_gen:
                optimizer_logger.error(f"Optimizer: Unexpected error during algorithm deletion {algo_path_to_delete}: {e_gen}", exc_info=True)
                QMessageBox.critical(main_window_ref, "Lỗi Không Xác Định (Optimizer)", f"Đã xảy ra lỗi không mong muốn khi xóa thuật toán:\n{e_gen}")
        else:
            optimizer_logger.info(f"Optimizer: Deletion of {algo_path_to_delete.name} cancelled by user.")
            self.update_status(f"Optimizer: Đã hủy xóa {algo_path_to_delete.name}.")

    def modify_algorithm_source_ast(self, source_code, target_class_name, new_params):
        main_window = self.get_main_window()
        optimizer_logger.debug(f"Optimizer AST mod: Class '{target_class_name}', Params: {list(new_params.keys())}")
        try: tree = ast.parse(source_code)
        except SyntaxError as e: optimizer_logger.error(f"Optimizer: Syntax error parsing source: {e}"); return None
        class _SourceModifier(ast.NodeTransformer):
            def __init__(self, class_to_modify, params_to_update):
                self.target_class = class_to_modify; self.params_to_update = params_to_update; self.in_target_init = False; self.params_modified = False; self.imports_modified = False; self.current_class_name = None; super().__init__()
            def visit_ImportFrom(self, node):
                if node.level > 0:
                    fixed_module_path = f"algorithms.{node.module}" if node.module else "algorithms"
                    if node.module == 'base':
                        node.module = 'algorithms.base'
                        node.level = 0
                        self.imports_modified = True
                        optimizer_logger.debug(f"AST Fix: Changed 'from .base' to 'from algorithms.base'")
                    elif node.module:
                        node.module = fixed_module_path
                        node.level = 0
                        self.imports_modified = True
                        optimizer_logger.debug(f"AST Fix: Changed 'from .{node.module}' to 'from {fixed_module_path}'")
                return self.generic_visit(node)

            def visit_ClassDef(self, node):
                original_class = self.current_class_name; self.current_class_name = node.name
                if node.name == self.target_class: node.body = [self.visit(child) for child in node.body]
                else: self.generic_visit(node)
                self.current_class_name = original_class; return node
            def visit_FunctionDef(self, node):
                if node.name == '__init__' and self.current_class_name == self.target_class:
                     self.in_target_init = True; node.body = [self.visit(child) for child in node.body]; self.in_target_init = False
                else: self.generic_visit(node)
                return node
            def visit_Assign(self, node):
                if self.in_target_init and len(node.targets) == 1:
                    target = node.targets[0]
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self' and target.attr == 'config':
                         node.value = self.visit(node.value)
                         return node
                return self.generic_visit(node)
            def visit_Dict(self, node):
                if not self.in_target_init:
                    return self.generic_visit(node)

                param_key_index = -1
                param_value_node = None
                try:
                    if node.keys:
                        for i, key_node in enumerate(node.keys):
                            is_param_key = (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str) and key_node.value == 'parameters') or \
                                           (hasattr(ast, 'Str') and isinstance(key_node, ast.Str) and key_node.s == 'parameters')

                            if is_param_key:
                                param_key_index = i
                                param_value_node = node.values[i]
                                break
                except Exception as e_dict:
                     optimizer_logger.warning(f"Error checking dict keys during AST modification: {e_dict}")
                     return self.generic_visit(node)


                if param_key_index != -1 and isinstance(param_value_node, ast.Dict):
                    new_keys = []
                    new_values = []
                    modified_in_subdict = False

                    original_param_nodes = {}
                    if param_value_node.keys:
                        for k, v in zip(param_value_node.keys, param_value_node.values):
                            param_name_str = None
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                param_name_str = k.value
                            elif hasattr(ast, 'Str') and isinstance(k, ast.Str):
                                param_name_str = k.s

                            if param_name_str:
                                original_param_nodes[param_name_str] = (k, v)

                    for param_name, new_value in self.params_to_update.items():
                        if param_name in original_param_nodes:
                            p_key_node, p_val_node = original_param_nodes[param_name]
                            new_val_node = None

                            if sys.version_info >= (3, 8):
                                if isinstance(new_value, (int, float)):
                                    if new_value < 0:
                                        new_val_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=abs(new_value)))
                                    else:
                                        new_val_node = ast.Constant(value=new_value)
                                elif isinstance(new_value, str):
                                    new_val_node = ast.Constant(value=new_value)
                                elif isinstance(new_value, bool):
                                    new_val_node = ast.Constant(value=new_value)
                                elif new_value is None:
                                    new_val_node = ast.Constant(value=None)
                            else:
                                if isinstance(new_value, (int, float)):
                                    new_val_node = ast.Num(n=new_value)
                                elif isinstance(new_value, str):
                                    new_val_node = ast.Str(s=new_value)
                                elif isinstance(new_value, bool):
                                    new_val_node = ast.NameConstant(value=new_value)
                                elif new_value is None:
                                    new_val_node = ast.NameConstant(value=None)

                            if new_val_node is not None:
                                new_keys.append(p_key_node)
                                new_values.append(new_val_node)
                                modified_in_subdict = True
                            else:
                                new_keys.append(p_key_node)
                                new_values.append(p_val_node)

                    updated_keys = set(self.params_to_update.keys())
                    for name, (k_node, v_node) in original_param_nodes.items():
                        if name not in updated_keys:
                            new_keys.append(k_node)
                            new_values.append(v_node)

                    param_value_node.keys = new_keys
                    param_value_node.values = new_values
                    if modified_in_subdict:
                        self.params_modified = True

                return self.generic_visit(node)

        modifier = _SourceModifier(target_class_name, new_params)
        modified_tree = modifier.visit(tree)

        if not modifier.params_modified and not modifier.imports_modified:
            optimizer_logger.warning("Optimizer AST mod: No parameters or imports updated.")
        elif modifier.params_modified and modifier.imports_modified:
            optimizer_logger.info("Optimizer AST modification: Parameters and Imports updated.")
        elif modifier.params_modified:
            optimizer_logger.info("Optimizer AST modification: Parameters updated.")
        elif modifier.imports_modified:
            optimizer_logger.info("Optimizer AST modification: Imports updated.")

        try:
            if sys.version_info >= (3, 9):
                modified_code = ast.unparse(modified_tree)
            elif HAS_ASTOR:
                modified_code = astor.to_source(modified_tree)
            else:
                QMessageBox.critical(self.get_main_window(), "Lỗi Thư Viện", "Cần thư viện 'astor' cho Python < 3.9 để chỉnh sửa file thuật toán.\nCài đặt: pip install astor")
                return None
        except Exception as unparse_err:
            optimizer_logger.error(f"Error unparsing modified AST: {unparse_err}", exc_info=True)
            return None

        return modified_code

    def _populate_combination_selection(self):
        container_layout = self.combination_layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.combination_selection_checkboxes.clear()

        if not self.selected_algorithm_for_optimize:
            self.initial_combo_label = QLabel("Chưa chọn thuật toán.")
            self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(self.initial_combo_label)
            return

        target_algo_name = self.selected_algorithm_for_optimize
        available_algos = sorted(self.loaded_algorithms.keys())

        if len(available_algos) <= 1:
            self.initial_combo_label = QLabel("Không có thuật toán khác.")
            self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(self.initial_combo_label)
            return

        instruction_label = QLabel("Chọn thuật toán để chạy cùng:")
        instruction_label.setStyleSheet("font-style: italic;")
        container_layout.addWidget(instruction_label)

        for algo_name in available_algos:
            if algo_name == target_algo_name:
                continue
            class_name_only = algo_name.split(' (')[0]
            chk = QCheckBox(class_name_only)
            chk.setToolTip(algo_name)
            container_layout.addWidget(chk)
            self.combination_selection_checkboxes[algo_name] = chk

    def _clear_combination_selection(self):
        container_layout = self.combination_layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.combination_selection_checkboxes.clear()

        self.initial_combo_label = QLabel("Chọn thuật toán để tối ưu...")
        self.initial_combo_label.setStyleSheet("font-style: italic; color: #6c757d;")
        container_layout.addWidget(self.initial_combo_label)

    def _get_selected_combination_algos(self) -> list[str]:
        return [name for name, chk in self.combination_selection_checkboxes.items() if chk.isChecked()]

    def _populate_advanced_optimizer_settings(self):
        container_layout = self.advanced_opt_params_layout
        while container_layout.count() > 0:
            item = container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.advanced_opt_widgets.clear()

        if not self.selected_algorithm_for_optimize:
            self.initial_adv_label = QLabel("Chưa chọn thuật toán.")
            self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(self.initial_adv_label)
            return

        display_name = self.selected_algorithm_for_optimize
        if display_name not in self.loaded_algorithms:
            error_label = QLabel("Lỗi: Thuật toán không tìm thấy.")
            error_label.setStyleSheet("color: #dc3545;")
            container_layout.addWidget(error_label)
            return

        algo_data = self.loaded_algorithms[display_name]
        parameters = algo_data['config'].get('parameters', {})
        numeric_params = {k: v for k, v in parameters.items() if isinstance(v, (int, float))}

        if not numeric_params:
            self.initial_adv_label = QLabel("Không có tham số số học.")
            self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
            container_layout.addWidget(self.initial_adv_label)
            return

        header_frame = QWidget()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(5, 5, 5, 10)
        header_layout.addWidget(QLabel("Tham số"), 2)
        header_layout.addWidget(QLabel("Giá trị gốc"), 1)
        header_layout.addWidget(QLabel("Chế độ"), 1)
        header_layout.addWidget(QLabel("Bước (+/-) cách bởi dấu phẩy"), 3)
        container_layout.addWidget(header_frame)

        is_auto_mode = (self.current_optimization_mode == 'auto_hill_climb')
        header_frame.setVisible(is_auto_mode)

        for name, value in numeric_params.items():
            param_frame = QWidget()
            param_layout = QHBoxLayout(param_frame)
            param_layout.setContentsMargins(5, 2, 5, 2)

            if name not in self.optimizer_custom_steps:
                self.optimizer_custom_steps[name] = {'mode': 'Auto', 'steps': [], 'str_value': ""}

            param_state = self.optimizer_custom_steps[name]

            param_label = QLabel(name)
            param_layout.addWidget(param_label, 2)

            value_label = QLabel(f"{value:.4g}" if isinstance(value, float) else str(value))
            value_label.setStyleSheet("color: #6c757d;")
            param_layout.addWidget(value_label, 1)

            mode_combo = QComboBox()
            mode_combo.addItems(["Auto", "Custom"])
            mode_combo.setCurrentText(param_state['mode'])
            mode_combo.setFixedWidth(80)
            param_layout.addWidget(mode_combo, 1)

            steps_entry = QLineEdit(param_state.get('str_value', ''))
            steps_entry.setValidator(self.custom_steps_validator)
            steps_entry.setEnabled(param_state['mode'] == 'Custom')
            param_layout.addWidget(steps_entry, 3)

            mode_combo.currentTextChanged.connect(
                lambda text, n=name, mc=mode_combo, se=steps_entry: self._on_step_mode_change(n, mc, se)
            )
            steps_entry.textChanged.connect(
                lambda text, n=name, se=steps_entry: self._update_custom_steps(n, se)
            )

            container_layout.addWidget(param_frame)
            self.advanced_opt_widgets[name] = {'mode_combo': mode_combo, 'steps_entry': steps_entry}

            param_frame.setVisible(is_auto_mode)


    def _on_step_mode_change(self, param_name, mode_combo_widget, steps_entry_widget):

        new_mode = mode_combo_widget.currentText()
        if param_name in self.optimizer_custom_steps:
            self.optimizer_custom_steps[param_name]['mode'] = new_mode
            is_custom = (new_mode == 'Custom')
            steps_entry_widget.setEnabled(is_custom)
            if is_custom:
                steps_entry_widget.setFocus()
                self._update_custom_steps(param_name, steps_entry_widget)
            else:
                steps_entry_widget.setStyleSheet("")

    def _validate_custom_steps_input_bool(self, text):

        if not text: return True
        regex = QtCore.QRegularExpression(r"^(?:[-+]?\d+(?:\.\d*)?(?:,\s*[-+]?\d+(?:\.\d*)?)*)?$")
        match = regex.match(text)
        return match.hasMatch() and match.capturedLength() == len(text)


    def _update_custom_steps(self, param_name, steps_entry_widget):

        steps_str = steps_entry_widget.text().strip()
        error_style = "QLineEdit { border: 1px solid #dc3545; }"

        if param_name in self.optimizer_custom_steps:
            self.optimizer_custom_steps[param_name]['str_value'] = steps_str

            if self.optimizer_custom_steps[param_name]['mode'] == 'Custom':
                is_valid_syntax = self._validate_custom_steps_input_bool(steps_str)
                parse_error = False
                parsed_steps = []

                if is_valid_syntax and steps_str:
                    try:
                        original_value = None
                        if self.selected_algorithm_for_optimize and self.selected_algorithm_for_optimize in self.loaded_algorithms:
                             original_value = self.loaded_algorithms[self.selected_algorithm_for_optimize]['config'].get('parameters', {}).get(param_name)

                        if original_value is None:
                            raise ValueError(f"Cannot get original type for '{param_name}'.")

                        is_original_int = isinstance(original_value, int)
                        temp_parsed = []
                        for part in steps_str.split(','):
                            part = part.strip()
                            if part:
                                num_val = float(part)
                                if is_original_int:
                                    if num_val == int(num_val):
                                        temp_parsed.append(int(num_val))
                                    else:
                                        raise ValueError(f"Integer parameter '{param_name}' requires integer steps. Invalid step: '{part}'.")
                                else:
                                    temp_parsed.append(num_val)

                        if temp_parsed:
                            parsed_steps = sorted(list(set(temp_parsed)))

                    except (ValueError, KeyError, TypeError) as e:
                        parse_error = True
                        parsed_steps = []
                        optimizer_logger.warning(f"Error parsing custom steps for {param_name}: {e}")
                elif not is_valid_syntax and steps_str:
                    parse_error = True
                    parsed_steps = []
                else:
                    parse_error = False
                    parsed_steps = []


                self.optimizer_custom_steps[param_name]['steps'] = parsed_steps

                if parse_error:
                    steps_entry_widget.setStyleSheet(error_style)
                else:
                    steps_entry_widget.setStyleSheet("")

            else:
                self.optimizer_custom_steps[param_name]['steps'] = []
                steps_entry_widget.setStyleSheet("")


    def _reset_advanced_opt_settings(self):
        self.optimizer_custom_steps.clear()
        container_layout = self.advanced_opt_params_layout
        if container_layout:
            while container_layout.count() > 0:
                item = container_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.advanced_opt_widgets.clear()

        self.initial_adv_label = QLabel("Chọn thuật toán để xem tham số.")
        self.initial_adv_label.setStyleSheet("font-style: italic; color: #6c757d;")
        if container_layout:
            container_layout.addWidget(self.initial_adv_label)

    def _clear_advanced_opt_fields(self):
        self._reset_advanced_opt_settings()

    def populate_optimizer_info(self, display_name):
        if display_name in self.loaded_algorithms:
            class_name = self.loaded_algorithms[display_name]['class_name']
            filename = self.loaded_algorithms[display_name]['path'].name
            self.opt_algo_name_label.setText(f"{class_name} ({filename})")
        else:
            self.opt_algo_name_label.setText("Lỗi: Không tìm thấy thuật toán")
            self.opt_algo_name_label.setStyleSheet("color: #dc3545;")

    def start_optimization(self, initial_params=None, initial_score_tuple=None, initial_combination_algos=None):
        """
        Initiates the optimization process, either resuming or starting fresh.
        Gathers settings and delegates the actual work to a worker thread.
        For 'generated_combinations' mode, it gathers parameters for generation
        but the generation itself happens in the worker thread.
        """
        is_resuming = initial_params is not None and initial_score_tuple is not None
        main_window = self.get_main_window()

        if self.optimizer_running:
            QMessageBox.warning(main_window, "Đang Chạy", "Quá trình tối ưu hóa đang chạy.")
            return

        if not self.selected_algorithm_for_optimize:
            QMessageBox.critical(main_window, "Lỗi", "Chưa chọn thuật toán để tối ưu hóa.")
            return

        display_name = self.selected_algorithm_for_optimize
        if display_name not in self.loaded_algorithms:
            QMessageBox.critical(main_window, "Lỗi", f"Thuật toán '{display_name}' không còn được tải.")
            return

        algo_data = self.loaded_algorithms[display_name]
        original_params = algo_data['config'].get('parameters', {})
        numeric_params_check = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}

        if not numeric_params_check and self.current_optimization_mode != 'generated_combinations':
            QMessageBox.information(main_window, "Thông Báo", "Thuật toán này không có tham số số học để tối ưu (ở chế độ Auto/Custom).")

        if is_resuming and initial_combination_algos is not None:
            combination_algos_to_use = initial_combination_algos
        else:
            combination_algos_to_use = self._get_selected_combination_algos()

        start_d, end_d, time_limit_min = self._validate_common_opt_settings_qt()
        if start_d is None:
            return

        final_custom_steps_config = {}
        generation_params_for_worker = None
        mode_to_run = self.current_optimization_mode

        if mode_to_run == 'auto_hill_climb':
            final_custom_steps_config, has_invalid_custom_steps = self._finalize_custom_steps_config_qt(original_params)
            if not numeric_params_check and not any(p_config.get('steps') for p_config in final_custom_steps_config.values() if p_config.get('mode') == 'Custom'):
                 QMessageBox.information(main_window, "Thông Báo", "Thuật toán không có tham số số học và không có bước tùy chỉnh nào được định nghĩa.")
                 return

        elif mode_to_run == 'generated_combinations':
            num_values_per_param = self.combo_num_values_spinbox.value()
            generation_method = "adjacent"
            max_combinations_to_generate = self.combo_max_combinations_spinbox.value()

            generation_params_for_worker = {
                'original_params': original_params,
                'num_values': num_values_per_param,
                'method': generation_method,
                'max_combinations': max_combinations_to_generate
            }
            optimizer_logger.info(f"Preparing to generate {num_values_per_param} adjacent values per param, max combinations: {max_combinations_to_generate}.")

            estimated_total_raw = 1
            numeric_params_count = sum(1 for v in original_params.values() if isinstance(v, (int, float)))

            if not numeric_params_count and num_values_per_param > 0 :
                optimizer_logger.warning("Generated Combinations mode selected, but the algorithm has no numeric parameters to vary.")
                QMessageBox.information(main_window, "Không có Tham Số Số Học",
                                        "Chế độ 'Tạo Bộ Tham Số' được chọn, nhưng thuật toán này không có tham số dạng số để tạo các biến thể.")
                return


            if numeric_params_count > 0:
                try:
                    if num_values_per_param > 0:
                         if num_values_per_param == 1:
                              estimated_total_raw = 1
                         elif numeric_params_count * math.log(num_values_per_param) < math.log(sys.maxsize):
                              estimated_total_raw = num_values_per_param ** numeric_params_count
                         else:
                              estimated_total_raw = float('inf')
                    else:
                        estimated_total_raw = 0
                except OverflowError:
                     estimated_total_raw = float('inf')
                except Exception as est_err:
                     optimizer_logger.error(f"Error estimating raw combination count: {est_err}")
                     estimated_total_raw = -1
            else:
                estimated_total_raw = 0


            actual_combinations_to_test = estimated_total_raw
            warning_title = "Số Lượng Lớn (Ước Tính)"
            warning_detail_message_base = ""

            if max_combinations_to_generate > 0:
                if estimated_total_raw == float('inf') or estimated_total_raw > max_combinations_to_generate:
                    actual_combinations_to_test = max_combinations_to_generate
                    warning_detail_message_base = (f"Số bộ tham số sẽ được giới hạn ở mức tối đa bạn đã đặt: {max_combinations_to_generate}.\n\n"
                                              f"Việc tạo và kiểm tra {int(actual_combinations_to_test)} bộ tham số")
                    warning_title = "Số Lượng Lớn (Đã Giới Hạn)"
                else:
                    actual_combinations_to_test = estimated_total_raw
                    warning_detail_message_base = f"Việc tạo và kiểm tra {int(actual_combinations_to_test)} bộ tham số"
            else:
                if estimated_total_raw == 0:
                    actual_combinations_to_test = 0
                    warning_detail_message_base = "Không có bộ tham số nào được tạo (do không có tham số số học hoặc số giá trị/tham số là 0)."
                else:
                    display_est_raw = "rất lớn" if estimated_total_raw == float('inf') else f"khoảng {int(estimated_total_raw)}"
                    warning_detail_message_base = f"Việc tạo và kiểm tra {display_est_raw} bộ tham số"
            
            WARNING_THRESHOLD = 100000

            if actual_combinations_to_test == 0 and numeric_params_count > 0:
                QMessageBox.information(main_window, "Không Tạo Bộ Nào",
                                        f"{warning_detail_message_base}\nVui lòng kiểm tra lại 'Số giá trị liền kề/tham số'.")
                return
            elif actual_combinations_to_test == float('inf') or actual_combinations_to_test > WARNING_THRESHOLD:
                full_warning_message = f"{warning_detail_message_base} có thể rất lâu và tốn nhiều bộ nhớ.\n\nBạn có muốn tiếp tục không?"
                reply = QMessageBox.question(main_window, warning_title,
                                                full_warning_message,
                                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                      return
            elif estimated_total_raw == -1:
                 optimizer_logger.warning("Could not reliably estimate combination count, proceeding without warning.")
        else:
             QMessageBox.critical(main_window, "Lỗi Chế Độ", f"Chế độ tối ưu không xác định: {mode_to_run}")
             return

        self._start_optimization_worker_thread(
            display_name=display_name,
            start_date=start_d,
            end_date=end_d,
            time_limit_min=time_limit_min,
            custom_steps_config=final_custom_steps_config,
            generation_params=generation_params_for_worker,
            combination_algos=combination_algos_to_use,
            initial_params=initial_params,
            initial_score_tuple=initial_score_tuple,
            is_resuming=is_resuming,
            mode=mode_to_run
        )

    def resume_optimization_session(self):
        optimizer_logger.info("Action: Resume optimization requested (PyQt5).")
        main_window = self.get_main_window()

        if self.optimizer_running:
            QMessageBox.warning(main_window, "Đang Chạy", "Tối ưu hóa đang chạy.")
            return
        if not self.selected_algorithm_for_optimize:
            QMessageBox.critical(main_window, "Lỗi", "Chưa chọn thuật toán để tiếp tục tối ưu.")
            return

        target_display_name = self.selected_algorithm_for_optimize
        if target_display_name not in self.loaded_algorithms:
            QMessageBox.critical(main_window, "Lỗi", f"Thuật toán '{target_display_name}' không còn được tải.")
            return

        algo_data = self.loaded_algorithms[target_display_name]
        optimize_target_dir = self.optimize_dir / algo_data['path'].stem
        success_dir = optimize_target_dir / "success"

        latest_json_path, latest_data = self.find_latest_successful_optimization(success_dir, algo_data['path'].stem)

        if not latest_json_path:
            QMessageBox.information(main_window, "Không Tìm Thấy", f"Không tìm thấy kết quả/trạng thái tối ưu đã lưu cho:\n{target_display_name}")
            return

        try:

            self.opt_mode_auto_radio.setChecked(True)
            self.current_optimization_mode = 'auto_hill_climb'
            self._populate_advanced_optimizer_settings()


            loaded_params = latest_data.get("params")
            loaded_score_tuple = tuple(latest_data.get("score_tuple"))
            loaded_range_str = latest_data.get("optimization_range")
            loaded_combo_algos_raw = latest_data.get("combination_algorithms", [])

            if not isinstance(loaded_params, dict) or \
               not isinstance(loaded_score_tuple, tuple) or \
               len(loaded_score_tuple) != 4 or \
               not isinstance(loaded_range_str, str) or \
               not isinstance(loaded_combo_algos_raw, list):
                raise ValueError("Dữ liệu JSON không hợp lệ.")

            try:
                start_s, end_s = loaded_range_str.split('_to_')
                loaded_start_date = datetime.datetime.strptime(start_s, '%Y-%m-%d').date()
                loaded_end_date = datetime.datetime.strptime(end_s, '%Y-%m-%d').date()
                self.opt_start_date_edit.setText(loaded_start_date.strftime('%d/%m/%Y'))
                self.opt_end_date_edit.setText(loaded_end_date.strftime('%d/%m/%Y'))
            except (ValueError, AttributeError) as date_err:
                raise ValueError(f"Lỗi phân tích ngày '{loaded_range_str}': {date_err}")

            current_numeric_keys = {k for k, v in algo_data['config'].get('parameters', {}).items() if isinstance(v, (int, float))}
            loaded_numeric_keys = {k for k, v in loaded_params.items() if isinstance(v, (int, float))}
            if current_numeric_keys != loaded_numeric_keys:
                reply = QMessageBox.question(main_window, "Tham Số Không Khớp",
                                             "Các tham số số học trong file trạng thái không khớp với thuật toán hiện tại.\n\nTiếp tục với tham số đã lưu?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            final_combo_algos_to_use = []
            missing_combo_algos = []
            for combo_name in loaded_combo_algos_raw:
                if combo_name in self.loaded_algorithms:
                    final_combo_algos_to_use.append(combo_name)
                else:
                    missing_combo_algos.append(combo_name)

            if missing_combo_algos:
                msg = f"Các thuật toán kết hợp sau đây đã được sử dụng trong lần chạy trước nhưng hiện không tìm thấy:\n\n- {', '.join(missing_combo_algos)}\n\nTiếp tục tối ưu mà không có các thuật toán này?"
                reply = QMessageBox.question(main_window, "Thiếu Thuật Toán Kết Hợp", msg,
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            self._populate_combination_selection()
            for name, chk in self.combination_selection_checkboxes.items():
                chk.setChecked(name in final_combo_algos_to_use)

            self._log_to_optimizer_display("INFO", f"TIẾP TỤC TỐI ƯU TỪ FILE: {latest_json_path.name}", tag="RESUME")
            self._log_to_optimizer_display("INFO", f"Tham số đích bắt đầu: {loaded_params}", tag="RESUME")
            self._log_to_optimizer_display("INFO", f"Điểm số bắt đầu: ({', '.join(f'{s:.3f}' for s in loaded_score_tuple)})", tag="RESUME")
            self._log_to_optimizer_display("INFO", f"Khoảng ngày: {self.opt_start_date_edit.text()} - {self.opt_end_date_edit.text()}", tag="RESUME")
            self._log_to_optimizer_display("INFO", f"Thuật toán kết hợp: {final_combo_algos_to_use or '(Không có)'}", tag="RESUME")

            _, _, time_limit_min = self._validate_common_opt_settings_qt(check_dates=False)
            if time_limit_min is None: return

            original_params = algo_data['config'].get('parameters', {})
            final_custom_steps_config, has_invalid_custom_steps = self._finalize_custom_steps_config_qt(original_params)
            if has_invalid_custom_steps:
                self._populate_advanced_optimizer_settings()


            self.start_optimization(initial_params=loaded_params,
                                    initial_score_tuple=loaded_score_tuple,
                                    initial_combination_algos=final_combo_algos_to_use)

        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            QMessageBox.critical(main_window, "Lỗi Tải Trạng Thái", f"Không thể tải trạng thái từ:\n{latest_json_path.name if latest_json_path else 'N/A'}\n\nLỗi: {e}")
        except Exception as e:
            optimizer_logger.error(f"Unexpected error resuming optimization: {e}", exc_info=True)
            QMessageBox.critical(main_window, "Lỗi Không Xác Định", f"Đã xảy ra lỗi khi chuẩn bị tiếp tục:\n{e}")


    def _validate_common_opt_settings_qt(self, check_dates=True):

        start_d, end_d = None, None
        main_window = self.get_main_window()

        if check_dates:
            start_s = self.opt_start_date_edit.text()
            end_s = self.opt_end_date_edit.text()
            if not start_s or not end_s:
                QMessageBox.warning(main_window, "Thiếu Ngày", "Vui lòng chọn ngày bắt đầu và kết thúc cho khoảng dữ liệu kiểm tra.")
                return None, None, None
            try:
                start_d = datetime.datetime.strptime(start_s, '%d/%m/%Y').date()
                end_d = datetime.datetime.strptime(end_s, '%d/%m/%Y').date()
            except ValueError:
                QMessageBox.critical(main_window, "Lỗi Ngày", "Định dạng ngày tháng không hợp lệ. Sử dụng định dạng dd/mm/yyyy.")
                return None, None, None

            if start_d > end_d:
                QMessageBox.warning(main_window, "Ngày Lỗi", "Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
                return None, None, None

            if not self.results_data or len(self.results_data) < 2:
                QMessageBox.critical(main_window, "Thiếu Dữ Liệu", "Cần ít nhất 2 ngày dữ liệu trong file đã tải để thực hiện tối ưu hóa.")
                return None, None, None

            min_data_date = self.results_data[0]['date']
            max_data_date = self.results_data[-1]['date']

            if start_d < min_data_date or end_d >= max_data_date:
                msg = (f"Khoảng ngày đã chọn ({start_s} - {end_s}) không hợp lệ.\n\n"
                       f"Dữ liệu có sẵn từ: {min_data_date:%d/%m/%Y} đến {max_data_date:%d/%m/%Y}.\n"
                       f"Ngày bắt đầu phải >= ngày đầu tiên của dữ liệu.\n"
                       f"Ngày kết thúc phải < ngày cuối cùng của dữ liệu ({max_data_date:%d/%m/%Y}).")
                QMessageBox.critical(main_window, "Lỗi Khoảng Ngày", msg)
                return None, None, None

        try:
            time_limit_min = self.opt_time_limit_spinbox.value()
            if time_limit_min <= 0:
                 QMessageBox.critical(main_window, "Lỗi Thời Gian", "Thời gian tối ưu tối đa phải lớn hơn 0 phút.")
                 return None, None, None
        except Exception as e:
             QMessageBox.critical(main_window, "Lỗi Thời Gian", f"Lỗi đọc giá trị thời gian tối ưu:\n{e}")
             return None, None, None

        return start_d, end_d, time_limit_min


    def _delete_inferior_optimized_files(self, success_dir: Path, current_best_score_tuple: tuple,
                                         current_best_py_path: Path, current_best_json_path: Path,
                                         worker_logger, queue_log_func,
                                         algo_stem_filter: str, prefix_filter: str = "optimized_"):
        """
        Deletes optimized .py and .json files in the success_dir if their score
        is inferior to the current_best_score_tuple.
        """
        worker_logger.info(f"Scanning '{success_dir}' to delete inferior files (prefix: '{prefix_filter}', stem: '{algo_stem_filter}'). Best current score: {current_best_score_tuple}")
        deleted_count = 0
        try:
            pattern_to_glob = f"{prefix_filter}{algo_stem_filter}_*.json"
            worker_logger.debug(f"Glob pattern for deletion scan: '{pattern_to_glob}' in '{success_dir}'")

            for old_json_path in success_dir.glob(pattern_to_glob):
                if old_json_path.resolve() == current_best_json_path.resolve():
                    worker_logger.debug(f"Skipping current best JSON file: {old_json_path.name}")
                    continue

                worker_logger.debug(f"Checking old JSON file: {old_json_path.name}")
                try:
                    old_data = json.loads(old_json_path.read_text(encoding='utf-8'))
                    old_score_tuple_raw = old_data.get("score_tuple")

                    if not isinstance(old_score_tuple_raw, list) or len(old_score_tuple_raw) != 4:
                        worker_logger.warning(f"Invalid or missing score_tuple in old file {old_json_path.name}. Skipping.")
                        continue
                    
                    old_score_tuple = tuple(old_score_tuple_raw)

                    if old_score_tuple < current_best_score_tuple:
                        worker_logger.info(f"Old score {old_score_tuple} < Current best {current_best_score_tuple}. Deleting {old_json_path.name}.")
                        
                        old_json_path.unlink()
                        queue_log_func("DEBUG", f"Đã xóa file JSON cũ: {old_json_path.name}", tag="INFO")

                        old_py_path = success_dir / (old_json_path.stem + ".py")
                        if old_py_path.exists():
                            old_py_path.unlink()
                            queue_log_func("DEBUG", f"Đã xóa file PY cũ: {old_py_path.name}", tag="INFO")
                        else:
                            worker_logger.warning(f"Corresponding .py file not found for deleted JSON: {old_py_path.name}")
                        deleted_count += 1
                    else:
                        worker_logger.debug(f"Old score {old_score_tuple} >= Current best. Keeping {old_json_path.name}.")

                except json.JSONDecodeError:
                    worker_logger.warning(f"Could not parse JSON from old file {old_json_path.name}. Skipping.")
                except FileNotFoundError:
                    worker_logger.warning(f"File {old_json_path.name} or its .py counterpart disappeared during check. Skipping.")
                except Exception as e_del_item:
                    worker_logger.error(f"Error processing/deleting old optimized file {old_json_path.name}: {e_del_item}", exc_info=False)
            
            if deleted_count > 0:
                queue_log_func("INFO", f"Đã xóa {deleted_count} bộ file tối ưu cũ hơn.", tag="BEST")
            else:
                worker_logger.info("No inferior files found to delete.")

        except Exception as e_scan:
            worker_logger.error(f"Error scanning/deleting old optimized files in {success_dir}: {e_scan}", exc_info=True)
            queue_log_func("ERROR", f"Lỗi khi dọn dẹp file tối ưu cũ: {e_scan}", tag="ERROR")

    def _finalize_custom_steps_config_qt(self, original_params):

        if self.current_optimization_mode != 'auto_hill_climb':
            return {}, False

        final_custom_steps_config = {}
        has_invalid_custom_steps = False
        invalid_params_details = []
        main_window = self.get_main_window()

        for name, widgets in self.advanced_opt_widgets.items():
            mode_combo = widgets.get('mode_combo')
            steps_entry = widgets.get('steps_entry')

            if not mode_combo or not steps_entry: continue

            mode = mode_combo.currentText()
            steps_str = steps_entry.text().strip()
            parsed_steps = []
            is_final_mode_custom = False
            param_state = self.optimizer_custom_steps.get(name, {'mode': 'Auto', 'steps': []})

            if mode == 'Custom':
                is_valid_syntax = self._validate_custom_steps_input_bool(steps_str)

                if is_valid_syntax and steps_str:
                    try:
                        original_value = original_params[name]
                        is_original_int = isinstance(original_value, int)
                        temp_parsed = []
                        for part in steps_str.split(','):
                            part = part.strip()
                            if part:
                                num_val = float(part)
                                if is_original_int:
                                    if num_val == int(num_val): temp_parsed.append(int(num_val))
                                    else: raise ValueError(f"Int param '{name}' step '{part}' invalid.")
                                else: temp_parsed.append(num_val)

                        if temp_parsed:
                             parsed_steps = sorted(list(set(temp_parsed)))
                             is_final_mode_custom = True
                        else:
                             has_invalid_custom_steps = True
                             invalid_params_details.append(f"{name} (bước trống hoặc toàn 0)")
                             optimizer_logger.warning(f"Custom steps for '{name}' resulted in empty list, defaulting to Auto.")


                    except (ValueError, KeyError, TypeError) as parse_err:
                        has_invalid_custom_steps = True
                        invalid_params_details.append(f"{name} (lỗi phân tích: {parse_err})")
                        optimizer_logger.warning(f"Error finalizing custom steps for {name}: {parse_err}")

                elif not is_valid_syntax and steps_str:
                    has_invalid_custom_steps = True
                    invalid_params_details.append(f"{name} (sai định dạng)")
                    optimizer_logger.warning(f"Invalid syntax for custom steps in '{name}', defaulting to Auto.")

                if has_invalid_custom_steps and is_final_mode_custom == False:
                    param_state['mode'] = 'Auto'
                    param_state['steps'] = []


            final_custom_steps_config[name] = {
                'mode': 'Custom' if is_final_mode_custom else 'Auto',
                'steps': parsed_steps if is_final_mode_custom else []
            }

            log_mode = final_custom_steps_config[name]['mode']
            log_steps = f", Steps={final_custom_steps_config[name]['steps']}" if log_mode == 'Custom' else ""
            optimizer_logger.info(f"Optimizer Start - Param '{name}': Final Mode={log_mode}{log_steps}")


        if has_invalid_custom_steps:
            QMessageBox.warning(main_window, "Bước Tùy Chỉnh Lỗi",
                                f"Một số cài đặt bước tùy chỉnh không hợp lệ và đã được đặt về chế độ 'Auto':\n\n- {', '.join(invalid_params_details)}\n\nKiểm tra lại định dạng và kiểu dữ liệu (số nguyên/thập phân).")

        return final_custom_steps_config, has_invalid_custom_steps

    def _start_optimization_worker_thread(self, display_name, start_date, end_date, time_limit_min,
                                          custom_steps_config,
                                          generation_params,
                                          combination_algos,
                                          initial_params=None, initial_score_tuple=None, is_resuming=False,
                                          mode='auto_hill_climb'):
        """
        Sets up the environment and starts the appropriate optimization worker thread
        based on the selected mode.
        """
        main_window = self.get_main_window()
        try:
            algo_data = self.loaded_algorithms[display_name]
        except KeyError:
            QMessageBox.critical(main_window, "Lỗi", f"Thuật toán '{display_name}' không tìm thấy khi bắt đầu tối ưu.")
            self.update_optimizer_ui_state()
            return

        self.current_optimize_target_dir = self.optimize_dir / algo_data['path'].stem
        self.current_optimize_target_dir.mkdir(parents=True, exist_ok=True)
        success_dir = self.current_optimize_target_dir / "success"
        success_dir.mkdir(parents=True, exist_ok=True)
        self.current_optimization_log_path = self.current_optimize_target_dir / "optimization_qt.log"

        if hasattr(self, 'opt_log_text'):
            self.opt_log_text.clear()
            if not is_resuming:
                 self._log_to_optimizer_display("INFO", "="*10 + " BẮT ĐẦU PHIÊN MỚI " + "="*10, tag="PROGRESS")
            else:
                 self._log_to_optimizer_display("INFO", "="*10 + " TIẾP TỤC PHIÊN " + "="*10, tag="RESUME")

            self._log_to_optimizer_display("INFO", f"Thuật toán đích: {display_name}", tag="INFO")
            self._log_to_optimizer_display("INFO", f"Thuật toán kết hợp: {combination_algos or '(Không có)'}", tag="COMBINE")
            self._log_to_optimizer_display("INFO", f"Khoảng ngày: {start_date:%d/%m/%Y} - {end_date:%d/%m/%Y}", tag="INFO")
            self._log_to_optimizer_display("INFO", f"Giới hạn thời gian: {time_limit_min} phút", tag="INFO")

            if mode == 'generated_combinations':
                num_vals = generation_params.get('num_values', '?') if generation_params else '?'
                gen_meth = generation_params.get('method', '?') if generation_params else '?'
                self._log_to_optimizer_display("INFO", f"Chế độ: Tạo Bộ Tham Số (Worker sẽ tạo ~{num_vals} giá trị/{gen_meth})", tag="GEN_COMBO")
            else:
                self._log_to_optimizer_display("INFO", "Chế độ: Tối ưu Tự động / Custom", tag="CUSTOM_STEP")
                if custom_steps_config:
                    for pname, pconfig in custom_steps_config.items():
                        if pconfig.get('mode') == 'Custom' and pconfig.get('steps'):
                            self._log_to_optimizer_display("DEBUG", f"  - Tham số '{pname}' (Custom): {pconfig['steps']}", tag="CUSTOM_STEP")

        self._clear_cache_directory()

        self.optimizer_stop_event.clear()
        self.optimizer_pause_event.clear()
        self.optimizer_running = True
        self.optimizer_paused = False
        self.current_best_params = initial_params if is_resuming else None
        self.current_best_score_tuple = initial_score_tuple if is_resuming else (-1.0, -1.0, -1.0, -100.0)
        self.current_combination_algos = combination_algos
        self.last_opt_range_start_str = start_date.strftime('%Y-%m-%d')
        self.last_opt_range_end_str = end_date.strftime('%Y-%m-%d')

        self.opt_start_time = time.time()
        self.opt_time_limit_sec = time_limit_min * 60

        if hasattr(self, 'opt_progressbar'): self.opt_progressbar.setValue(0)
        if hasattr(self, 'opt_progress_label'): self.opt_progress_label.setText("0%")
        if hasattr(self, 'opt_time_static_label'): self.opt_time_static_label.setVisible(True)
        if hasattr(self, 'opt_time_remaining_label'):
            self.opt_time_remaining_label.setVisible(True)
            initial_time_str = time.strftime('%H:%M:%S' if self.opt_time_limit_sec >= 3600 else '%M:%S', time.gmtime(self.opt_time_limit_sec)) if self.opt_time_limit_sec >= 0 else "--:--:--"
            self.opt_time_remaining_label.setText(initial_time_str)

        self.update_optimizer_ui_state()

        optimizer_logger.info(f"Preparing worker thread for mode: {mode}")
        worker_target = None
        worker_args = ()

        delete_old_files_flag = self.delete_old_optimized_files_checkbox.isChecked() if hasattr(self, 'delete_old_optimized_files_checkbox') else False
        optimizer_logger.info(f"Delete old optimized files flag: {delete_old_files_flag}")


        if mode == 'auto_hill_climb':
            worker_target = self._optimization_worker
            worker_args = (
                display_name, start_date, end_date, self.opt_time_limit_sec,
                custom_steps_config,
                combination_algos,
                self.current_best_params,
                self.current_best_score_tuple,
                delete_old_files_flag
            )
            optimizer_logger.debug("Worker target set to _optimization_worker")
        elif mode == 'generated_combinations':
            worker_target = self._combination_optimization_worker
            worker_args = (
                display_name, start_date, end_date, self.opt_time_limit_sec,
                generation_params,
                combination_algos,
                self.current_best_params,
                self.current_best_score_tuple,
                delete_old_files_flag
            )

        if mode == 'auto_hill_climb':
            worker_target = self._optimization_worker
            worker_args = (
                display_name, start_date, end_date, self.opt_time_limit_sec,
                custom_steps_config,
                combination_algos,
                self.current_best_params,
                self.current_best_score_tuple
            )
            optimizer_logger.debug("Worker target set to _optimization_worker")
        elif mode == 'generated_combinations':
            worker_target = self._combination_optimization_worker
            worker_args = (
                display_name, start_date, end_date, self.opt_time_limit_sec,
                generation_params,
                combination_algos,
                self.current_best_params,
                self.current_best_score_tuple
            )
            optimizer_logger.debug("Worker target set to _combination_optimization_worker")
        else:
            main_logger.error(f"Invalid optimization mode '{mode}' cannot start worker thread.")
            QMessageBox.critical(main_window, "Lỗi Mode", f"Chế độ tối ưu không hợp lệ: {mode}")
            self.optimizer_running = False
            self.update_optimizer_ui_state()
            return

        try:
            self.optimizer_thread = threading.Thread(
                target=worker_target,
                args=worker_args,
                name=f"Optimizer-{algo_data['path'].stem}-{mode}",
                daemon=True
            )
            self.optimizer_thread.start()
            optimizer_logger.info(f"Optimizer worker thread '{self.optimizer_thread.name}' started.")
        except Exception as thread_start_err:
             main_logger.error(f"Failed to start optimizer worker thread: {thread_start_err}", exc_info=True)
             QMessageBox.critical(main_window, "Lỗi Luồng", f"Không thể bắt đầu luồng tối ưu:\n{thread_start_err}")
             self.optimizer_running = False
             self.update_optimizer_ui_state()
             return

        if not self.optimizer_timer.isActive():
            self.optimizer_timer.start(self.optimizer_timer_interval)
        if not self.display_timer.isActive():
            self.display_timer.start(self.display_timer_interval)

        action_verb_status = "Tiếp tục" if is_resuming else "Bắt đầu"
        mode_desc = "Tạo Bộ Tham Số" if mode == 'generated_combinations' else "Tối ưu Tự động/Custom"
        self.update_status(f"Optimizer: {action_verb_status} {mode_desc} cho: {algo_data['class_name']}...")

    def pause_optimization(self):
        if self.optimizer_running and not self.optimizer_paused:
            self.optimizer_pause_event.set()
            self.optimizer_paused = True
            self.update_optimizer_ui_state()
            self.update_status("Optimizer: Đã tạm dừng.")
            self._log_to_optimizer_display("INFO", "[CONTROL] Tạm dừng tối ưu.", tag="WARNING")
            self._save_optimization_state(reason="paused")

    def resume_optimization(self):
        if self.optimizer_running and self.optimizer_paused:
            self.optimizer_pause_event.clear()
            self.optimizer_paused = False
            self.update_optimizer_ui_state()
            self.update_status("Optimizer: Tiếp tục tối ưu...")
            self._log_to_optimizer_display("INFO", "[CONTROL] Tiếp tục tối ưu.", tag="PROGRESS")

    def stop_optimization(self, force_stop=False):
        main_window = self.get_main_window()
        if self.optimizer_running:
            confirmed = force_stop
            if not force_stop:
                reply = QMessageBox.question(main_window, "Xác Nhận Dừng",
                                             "Bạn có chắc chắn muốn dừng quá trình tối ưu hóa không?\nKết quả tốt nhất hiện tại (nếu có) sẽ được lưu.",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    confirmed = True

            if confirmed:
                self.optimizer_stop_event.set()

                if hasattr(self, 'opt_start_button'): self.opt_start_button.setEnabled(False)
                if hasattr(self, 'opt_resume_button'): self.opt_resume_button.setEnabled(False)
                if hasattr(self, 'opt_pause_button'):
                    self.opt_pause_button.setText("Đang dừng...")
                    self.opt_pause_button.setEnabled(False)
                if hasattr(self, 'opt_stop_button'): self.opt_stop_button.setEnabled(False)

                self.update_status("Optimizer: Đang yêu cầu dừng...")
                self._log_to_optimizer_display("WARNING", "[CONTROL] Yêu cầu dừng...", tag="WARNING")

                if self.optimizer_paused:
                    self.optimizer_pause_event.clear()

    def update_optimizer_ui_state(self):

        start_enabled, resume_enabled, pause_enabled, stop_enabled = False, False, False, False
        pause_text = "Tạm dừng"
        pause_callback = self.pause_optimization
        pause_style_obj_name = "WarningButton"

        if self.optimizer_running:
            start_enabled = False
            resume_enabled = False
            stop_enabled = True
            if self.optimizer_paused:
                pause_enabled = True
                pause_text = "Tiếp tục"
                pause_callback = self.resume_optimization
            else:
                pause_enabled = True
                pause_text = "Tạm dừng"
                pause_callback = self.pause_optimization
        else:
            start_enabled = (self.selected_algorithm_for_optimize is not None)
            resume_enabled = self.can_resume
            stop_enabled = False
            pause_enabled = False
            pause_text = "Tạm dừng"
            pause_callback = self.pause_optimization

            if hasattr(self, 'opt_status_label'): self.opt_status_label.setText("Trạng thái: Chờ")
            if hasattr(self, 'opt_time_remaining_label'): self.opt_time_remaining_label.setText("--:--:--")
            if hasattr(self, 'opt_time_static_label'): self.opt_time_static_label.setVisible(False)
            if hasattr(self, 'opt_time_remaining_label'): self.opt_time_remaining_label.setVisible(False)

            if self.optimizer_timer.isActive(): self.optimizer_timer.stop()
            if self.display_timer.isActive(): self.display_timer.stop()


        if hasattr(self, 'opt_start_button'): self.opt_start_button.setEnabled(start_enabled)
        if hasattr(self, 'opt_resume_button'): self.opt_resume_button.setEnabled(resume_enabled)
        if hasattr(self, 'opt_stop_button'): self.opt_stop_button.setEnabled(stop_enabled)
        if hasattr(self, 'opt_pause_button'):
            self.opt_pause_button.setEnabled(pause_enabled)
            self.opt_pause_button.setText(pause_text)
            self.opt_pause_button.setObjectName(pause_style_obj_name)
            try: self.opt_pause_button.clicked.disconnect()
            except TypeError: pass
            self.opt_pause_button.clicked.connect(pause_callback)
            self.main_app.apply_stylesheet()

        settings_enabled = not self.optimizer_running

        if hasattr(self, 'opt_start_date_edit'): self.opt_start_date_edit.setReadOnly(not settings_enabled)
        if hasattr(self, 'opt_start_date_button'): self.opt_start_date_button.setEnabled(settings_enabled)
        if hasattr(self, 'opt_end_date_edit'): self.opt_end_date_edit.setReadOnly(not settings_enabled)
        if hasattr(self, 'opt_end_date_button'): self.opt_end_date_button.setEnabled(settings_enabled)
        if hasattr(self, 'opt_time_limit_spinbox'): self.opt_time_limit_spinbox.setEnabled(settings_enabled)

        if hasattr(self, 'opt_mode_auto_radio'): self.opt_mode_auto_radio.setEnabled(settings_enabled)
        if hasattr(self, 'opt_mode_combo_radio'): self.opt_mode_combo_radio.setEnabled(settings_enabled)

        is_combo_mode_selected = self.current_optimization_mode == 'generated_combinations'
        if hasattr(self, 'combo_gen_settings_widget'): self.combo_gen_settings_widget.setEnabled(settings_enabled and is_combo_mode_selected)

        is_auto_mode_selected = self.current_optimization_mode == 'auto_hill_climb'
        if hasattr(self, 'param_scroll_widget_container'): self.param_scroll_widget_container.setEnabled(settings_enabled and is_auto_mode_selected)
        for name, widgets in self.advanced_opt_widgets.items():
             mode_combo = widgets.get('mode_combo')
             steps_entry = widgets.get('steps_entry')
             if mode_combo: mode_combo.setEnabled(settings_enabled and is_auto_mode_selected)
             if steps_entry:
                 is_custom_mode_for_param = mode_combo.currentText() == 'Custom' if mode_combo else False
                 steps_entry.setEnabled(settings_enabled and is_auto_mode_selected and is_custom_mode_for_param)

        for name, chk in self.combination_selection_checkboxes.items():
            chk.setEnabled(settings_enabled)

        if hasattr(self, 'delete_old_optimized_files_checkbox'):
            self.delete_old_optimized_files_checkbox.setEnabled(settings_enabled)

        self.main_app.apply_stylesheet()


    def _update_optimizer_timer_display(self):

        if not self.optimizer_running or not hasattr(self, 'opt_time_remaining_label'):
            if self.display_timer.isActive(): self.display_timer.stop()
            return

        if not hasattr(self, 'opt_start_time') or not hasattr(self, 'opt_time_limit_sec'):
             if self.display_timer.isActive(): self.display_timer.stop()
             return

        elapsed_time = time.time() - self.opt_start_time
        seconds_left = max(0, self.opt_time_limit_sec - elapsed_time)

        if seconds_left >= 0:
            time_str = time.strftime('%H:%M:%S' if seconds_left >= 3600 else '%M:%S', time.gmtime(seconds_left))
        else:
            time_str = "00:00"

        if hasattr(self, 'opt_time_remaining_label') and self.opt_time_remaining_label.isVisible():
            self.opt_time_remaining_label.setText(time_str)

    def _check_optimizer_queue(self):

        main_window = self.get_main_window()
        try:
            while not self.optimizer_queue.empty():
                message = self.optimizer_queue.get_nowait()
                msg_type = message.get("type")
                payload = message.get("payload")

                if msg_type == "log":
                    level = payload.get("level", "INFO")
                    text = payload.get("text", "")
                    tag = payload.get("tag", level.upper())
                    self._log_to_optimizer_display(level, text, tag)

                elif msg_type == "status":
                    if hasattr(self, 'opt_status_label'):
                         self.opt_status_label.setText(f"Trạng thái: {payload}")

                elif msg_type == "progress":
                    progress_val = 0.0
                    max_val = 100
                    text_override = None
                    if isinstance(payload, dict):
                        current = payload.get('current', 0)
                        total = payload.get('total', 1)
                        progress_val = int((current / total * 100) if total > 0 else 0)
                        text_override = f"{progress_val}% ({current}/{total})"
                    else:
                        try: progress_val = int(float(payload) * 100.0)
                        except (ValueError, TypeError): pass

                    if hasattr(self, 'opt_progressbar'):
                         self.opt_progressbar.setRange(0, 100)
                         self.opt_progressbar.setValue(progress_val)
                    if hasattr(self, 'opt_progress_label'):
                         self.opt_progress_label.setText(text_override if text_override else f"{progress_val}%")


                elif msg_type == "best_update":
                    self.current_best_params = payload.get("params")
                    self.current_best_score_tuple = payload.get("score_tuple", (-1.0, -1.0, -1.0, -100.0))

                elif msg_type == "finished":
                    if self.optimizer_timer.isActive(): self.optimizer_timer.stop()
                    if self.display_timer.isActive(): self.display_timer.stop()

                    self.optimizer_running = False
                    self.optimizer_paused = False
                    final_message_from_worker = payload.get("message", "Hoàn tất.")
                    success = payload.get("success", False)
                    reason = payload.get("reason", "completed")

                    if reason == "stopped":
                        self._save_optimization_state(reason="stopped_by_user_request")
                    elif reason not in ["stopped", "paused"]:
                        self._save_optimization_state(reason=reason)

                    log_level, log_tag_prefix, msg_box_func, msg_box_title = "INFO", "[KẾT THÚC]", QMessageBox.information, "Kết Thúc Tối Ưu"
                    display_final_message = final_message_from_worker

                    if success:
                        log_level, log_tag_prefix = "BEST", "[HOÀN TẤT]"
                    elif reason == "time_limit":
                        log_level, log_tag_prefix = "BEST", "[HOÀN TẤT]"
                        time_limit_minutes_str = str(self.opt_time_limit_spinbox.value())
                        display_final_message = f"Đã hết thời gian tối ưu ({time_limit_minutes_str} phút)."
                        if self.current_best_params: display_final_message += " Kết quả tốt nhất đã được lưu."
                    elif reason == "stopped":
                        log_level, log_tag_prefix = "WARNING", "[ĐÃ DỪNG]"
                        display_final_message = "Quá trình tối ưu đã bị dừng bởi người dùng."
                        if self.current_best_params: display_final_message += " Kết quả tốt nhất đã được lưu."
                    elif reason == "no_improvement":
                         log_level, log_tag_prefix = "INFO", "[KẾT THÚC]"
                         display_final_message = "Quá trình tối ưu dừng do không có cải thiện thêm."
                         if self.current_best_params: display_final_message += " Kết quả tốt nhất đã được lưu."
                    elif reason == "no_params":
                        log_level, log_tag_prefix = "INFO", "[KẾT THÚC]"
                    elif reason == "resume_error" or reason == "initial_test_error":
                         log_level, log_tag_prefix, msg_box_func, msg_box_title = "ERROR", "[LỖI]", QMessageBox.warning, "Tối Ưu Kết Thúc Với Lỗi"
                    elif reason == "combo_mode_no_results":
                         log_level, log_tag_prefix, msg_box_func, msg_box_title = "WARNING", "[KẾT THÚC]", QMessageBox.warning, "Tối Ưu Kết Thúc"
                         display_final_message = "Hoàn thành kiểm tra các bộ tham số nhưng không có bộ nào cho kết quả hợp lệ."

                    else:
                        log_level, log_tag_prefix, msg_box_func, msg_box_title = "ERROR", "[LỖI]", QMessageBox.warning, "Tối Ưu Kết Thúc Với Lỗi"
                        display_final_message = f"Quá trình tối ưu kết thúc với lỗi (Lý do: {reason})."

                    self.update_status(f"Optimizer Kết thúc: {display_final_message.splitlines()[0]}")
                    self._log_to_optimizer_display(log_level, f"{log_tag_prefix} {display_final_message}", tag=log_level.upper())
                    if main_window: msg_box_func(main_window, msg_box_title, display_final_message)

                    if hasattr(self, 'opt_progressbar'): self.opt_progressbar.setValue(100)
                    if hasattr(self, 'opt_progress_label'): self.opt_progress_label.setText("100%")

                    self.check_resume_possibility()
                    self.update_optimizer_ui_state()

                    self.optimizer_thread = None
                    return

                elif msg_type == "error":
                    if self.optimizer_timer.isActive(): self.optimizer_timer.stop()
                    if self.display_timer.isActive(): self.display_timer.stop()

                    error_text = payload
                    self._log_to_optimizer_display("ERROR", f"[LỖI LUỒNG] {error_text}")
                    if main_window: QMessageBox.critical(main_window, "Lỗi Worker Tối Ưu", f"Đã xảy ra lỗi trong luồng tối ưu:\n\n{error_text}")
                    self.optimizer_running = False
                    self.update_optimizer_ui_state()
                    return

        except queue.Empty:
            pass
        except Exception as e:
            optimizer_logger.error(f"Error processing optimizer queue: {e}", exc_info=True)
            if self.optimizer_timer.isActive(): self.optimizer_timer.stop()
            if self.display_timer.isActive(): self.display_timer.stop()
            self.optimizer_running = False
            self.update_optimizer_ui_state()


    def _log_to_optimizer_display(self, level, text, tag=None):

        try:
            log_method = getattr(optimizer_logger, level.lower(), optimizer_logger.info)
            log_method(f"[OptimizerUI] {text}")

            if hasattr(self, 'opt_log_text'):
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                display_tag = tag if tag and tag in self.log_formats else level.upper()
                if display_tag == "CRITICAL": display_tag = "ERROR"
                log_format = self.log_formats.get(display_tag, self.log_formats["INFO"])

                cursor = self.opt_log_text.textCursor()
                cursor.movePosition(QTextCursor.End)
                full_log_line = f"{timestamp} [{level.upper()}] {text}\n"
                cursor.insertText(full_log_line, log_format)

                self.opt_log_text.ensureCursorVisible()

                if self.current_optimization_log_path:
                    try:
                        with open(self.current_optimization_log_path, "a", encoding="utf-8") as f:
                            f.write(f"{datetime.datetime.now().isoformat()} [{level.upper()}] {text}\n")
                    except IOError as log_write_err:
                        if not hasattr(self, '_log_write_error_logged'):
                            optimizer_logger.error(f"Failed to write to optimizer log file '{self.current_optimization_log_path}': {log_write_err}")
                            self._log_write_error_logged = True
            else:
                 if hasattr(self, '_log_write_error_logged'):
                     del self._log_write_error_logged

        except Exception as e:
             optimizer_logger.error(f"Error logging to optimizer display: {e}", exc_info=True)


    def _optimization_worker(self, target_display_name, start_date, end_date, time_limit_sec,
                             custom_steps_config, combination_algo_names,
                             initial_best_params=None, initial_best_score_tuple=None,
                             delete_old_files_flag=False):
        start_time = time.time()
        optimizer_worker_logger = logging.getLogger("OptimizerWorker")
        is_resuming = initial_best_params is not None and initial_best_score_tuple is not None
        optimizer_worker_logger.info(f"Starting Auto/Custom optimization worker (Resuming: {is_resuming}). Target: {target_display_name}")

        def queue_log(level, text, tag=None):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                try: self.optimizer_queue.put({"type": "log", "payload": {"level": level, "text": text, "tag": tag}})
                except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (log): {q_err}")
        def queue_status(text):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "status", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (status): {q_err}")
        def queue_progress(value):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "progress", "payload": min(max(0.0, value), 1.0)})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (progress): {q_err}")
        def queue_best_update(params, score_tuple):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "best_update", "payload": {"params": params, "score_tuple": score_tuple}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (best_update): {q_err}")
        def queue_finished(message, success=True, reason="finished"):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "finished", "payload": {"message": message, "success": success, "reason": reason}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (finished): {q_err}")
        def queue_error(text):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "error", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (error): {q_err}")

        throttling_enabled_opt = False
        sleep_duration_opt = 0.005
        if hasattr(self.main_app, 'cpu_throttling_enabled'):
            throttling_enabled_opt = self.main_app.cpu_throttling_enabled
        if hasattr(self.main_app, 'throttle_sleep_duration'):
            sleep_duration_opt = self.main_app.throttle_sleep_duration
        optimizer_worker_logger.debug(f"_optimization_worker Throttling: Enabled={throttling_enabled_opt}, Duration={sleep_duration_opt}s")

        finish_reason = "completed"
        try:
            if target_display_name not in self.loaded_algorithms:
                 raise ValueError(f"Target algorithm '{target_display_name}' not loaded in worker.")
            
            target_algo_data = self.loaded_algorithms[target_display_name]
            original_path = target_algo_data['path']
            class_name = target_algo_data['class_name']
            original_params = target_algo_data['config'].get('parameters', {})
            
            try:
                source_code = original_path.read_text(encoding='utf-8')
            except Exception as read_err:
                raise RuntimeError(f"Worker failed to read source code for {original_path.name}: {read_err}")

            if not hasattr(self, 'current_optimize_target_dir') or not self.current_optimize_target_dir:
                 raise RuntimeError("Worker cannot determine optimize target directory for _optimization_worker.")
            target_dir = self.current_optimize_target_dir
            
            params_to_optimize = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}
            param_names_ordered = list(params_to_optimize.keys())

            if not param_names_ordered:
                 queue_log("INFO", "Thuật toán đích không có tham số số học để tối ưu (chế độ Auto/Custom).")
                 queue_finished("Thuật toán đích không có tham số số học.", success=False, reason="no_params")
                 return

            def run_combined_perf_test_wrapper(target_params_test, combo_names, start_dt, end_dt):
                 return self.run_combined_performance_test(
                     target_display_name=target_display_name, target_algo_source=source_code, target_class_name=class_name,
                     target_params_to_test=target_params_test, combination_algo_display_names=combo_names,
                     test_start_date=start_dt, test_end_date=end_dt, optimize_target_dir=target_dir)

            def get_primary_score(perf_dict):
                 if not perf_dict: return (-1.0, -1.0, -1.0, -100.0)
                 return (perf_dict.get('acc_top_3_pct',0.0),
                         perf_dict.get('acc_top_5_pct',0.0),
                         perf_dict.get('acc_top_1_pct',0.0),
                         -perf_dict.get('avg_top10_repetition',100.0))

            current_best_params = {}
            current_best_perf = None
            current_best_score_tuple = initial_best_score_tuple if initial_best_score_tuple is not None else get_primary_score({})

            if is_resuming:
                queue_log("INFO", f"Tiếp tục tối ưu với tham số, điểm số đã tải.", tag="RESUME")
                current_best_params = initial_best_params.copy()
                queue_status("Kiểm tra hiệu suất tham số đã tải...")
                queue_progress(0.0)
                recalc_perf = run_combined_perf_test_wrapper(current_best_params, combination_algo_names, start_date, end_date)

                if self.optimizer_stop_event.is_set():
                    finish_reason = "stopped"
                    queue_log("WARNING", "Quá trình Tiếp tục tối ưu bị dừng trong khi tính toán lại hiệu suất.", tag="WARNING")
                    queue_finished("Dừng bởi người dùng trong khi tiếp tục.", success=False, reason=finish_reason)
                    return

                if recalc_perf is not None:
                    current_best_perf = recalc_perf
                    recalc_score = get_primary_score(recalc_perf)
                    if recalc_score != current_best_score_tuple:
                         queue_log("WARNING", f"Điểm tính lại ({recalc_score}) khác điểm tải ({initial_best_score_tuple}). Sử dụng điểm tính lại.", tag="WARNING")
                         current_best_score_tuple = recalc_score
                    queue_best_update(current_best_params, current_best_score_tuple)
                else:
                    queue_log("ERROR", "Lỗi khi kiểm tra lại hiệu suất của tham số đã tải.", tag="ERROR")
                    queue_finished("Lỗi kiểm tra lại hiệu suất tham số đã tải.", success=False, reason="resume_error")
                    return
            else:
                 queue_log("INFO", f"Bắt đầu tối ưu mới cho: {target_display_name}")
                 queue_status("Kiểm tra hiệu suất gốc...")
                 queue_progress(0.0)
                 initial_perf = run_combined_perf_test_wrapper(original_params, combination_algo_names, start_date, end_date)

                 if self.optimizer_stop_event.is_set():
                     finish_reason = "stopped"
                     queue_log("WARNING", "Quá trình tối ưu bị dừng trong khi kiểm tra hiệu suất gốc.", tag="WARNING")
                     queue_finished("Dừng bởi người dùng trong khi kiểm tra ban đầu.", success=False, reason=finish_reason)
                     return

                 if initial_perf is None:
                     queue_log("ERROR", "Lỗi kiểm tra hiệu suất ban đầu.", tag="ERROR")
                     queue_finished("Lỗi kiểm tra hiệu suất ban đầu.", success=False, reason="initial_test_error")
                     return

                 current_best_params = original_params.copy()
                 current_best_perf = initial_perf
                 current_best_score_tuple = get_primary_score(current_best_perf)
                 queue_log("INFO", f"Hiệu suất gốc: Top3={current_best_perf.get('acc_top_3_pct', 0.0):.2f}%, Top5={current_best_perf.get('acc_top_5_pct', 0.0):.2f}%, Top1={current_best_perf.get('acc_top_1_pct', 0.0):.2f}%, Lặp TB={current_best_perf.get('avg_top10_repetition', 0.0):.2f}")
                 queue_best_update(current_best_params, current_best_score_tuple)

            MAX_ITERATIONS_PER_PARAM_AUTO = 10
            STALL_THRESHOLD = 2
            MAX_FULL_CYCLES = 5
            steps_done_total = 0

            for cycle in range(MAX_FULL_CYCLES):
                queue_log("INFO", f"--- Chu kỳ {cycle + 1}/{MAX_FULL_CYCLES} ---", tag="PROGRESS")
                params_changed_in_cycle = False

                for param_idx, param_name in enumerate(param_names_ordered):
                    if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                    
                    if throttling_enabled_opt and sleep_duration_opt > 0:
                        time.sleep(sleep_duration_opt)
                        if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                        while self.optimizer_pause_event.is_set():
                            if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                            time.sleep(0.1)
                        if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break

                    while self.optimizer_pause_event.is_set():
                        if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                        time.sleep(0.5)
                    if finish_reason == "stopped": break
                    
                    elapsed_time_cycle = time.time() - start_time
                    if elapsed_time_cycle >= time_limit_sec: finish_reason = "time_limit"; break

                    param_opt_config = custom_steps_config.get(param_name, {'mode': 'Auto', 'steps': []})
                    mode = param_opt_config['mode']
                    custom_steps_for_param = param_opt_config['steps']
                    original_value_for_turn = current_best_params[param_name]
                    is_float_param = isinstance(original_value_for_turn, float)

                    if mode == 'Custom' and custom_steps_for_param:
                        queue_log("INFO", f"Tối ưu {param_name} (Chế độ: Custom, Các bước: {custom_steps_for_param})", tag="CUSTOM_STEP")
                        best_value_this_param_turn = current_best_params[param_name]

                        for step_sign in [1, -1]:
                            for step_val_abs in custom_steps_for_param:
                                if self.optimizer_stop_event.is_set(): finish_reason="stopped"; break
                                if time.time() - start_time >= time_limit_sec: finish_reason="time_limit"; break
                                if step_val_abs == 0: continue

                                test_params_custom = current_best_params.copy()
                                new_value_custom = best_value_this_param_turn + (step_sign * step_val_abs)
                                test_params_custom[param_name] = float(f"{new_value_custom:.6g}") if is_float_param else int(round(new_value_custom))

                                sign_char = '+' if step_sign > 0 else '-'
                                queue_status(f"Thử custom {sign_char}: {param_name}={test_params_custom[param_name]} (bước {step_val_abs})...")

                                perf_result_custom = run_combined_perf_test_wrapper(test_params_custom, combination_algo_names, start_date, end_date)
                                steps_done_total += 1
                                queue_progress(min(0.95, (time.time() - start_time) / time_limit_sec if time_limit_sec > 0 else 0.0))

                                if self.optimizer_stop_event.is_set(): finish_reason="stopped"; break

                                if perf_result_custom is not None:
                                    new_score_custom = get_primary_score(perf_result_custom)
                                    if new_score_custom > current_best_score_tuple:
                                        queue_log("BEST", f"  -> Cải thiện ({sign_char} custom)! {param_name}={test_params_custom[param_name]}. Score mới: {new_score_custom}", tag="BEST")
                                        current_best_params = test_params_custom.copy()
                                        current_best_perf = perf_result_custom
                                        current_best_score_tuple = new_score_custom
                                        best_value_this_param_turn = new_value_custom
                                        queue_best_update(current_best_params, current_best_score_tuple)
                                        params_changed_in_cycle = True
                                else:
                                    queue_log("WARNING", f"  -> Lỗi Test {sign_char} custom {param_name}={test_params_custom[param_name]}.", tag="WARNING")
                            if finish_reason in ["stopped", "time_limit"]: break
                        if finish_reason in ["stopped", "time_limit"]: break
                    
                    else:
                        step_base_auto = abs(original_value_for_turn) * 0.05
                        if not is_float_param:
                            step_auto = max(1, int(round(step_base_auto)))
                        else:
                            if abs(original_value_for_turn) > 1e-9:
                                step_auto = max(1e-6, step_base_auto)
                            else:
                                step_auto = 0.001
                        
                        queue_log("INFO", f"Tối ưu {param_name} (Chế độ: Auto, Giá trị hiện tại={current_best_params[param_name]:.4g}, Bước ~ {step_auto:.4g})", tag="PROGRESS")

                        for direction_sign_auto in [1, -1]:
                            no_improve_streak_auto = 0
                            params_at_dir_start_auto = current_best_params.copy()
                            current_val_for_dir_auto = params_at_dir_start_auto[param_name]
                            
                            dir_char_auto = '+' if direction_sign_auto > 0 else '-'; 
                            dir_text_auto = 'tăng' if direction_sign_auto > 0 else 'giảm'

                            for i_auto in range(MAX_ITERATIONS_PER_PARAM_AUTO):
                                if self.optimizer_stop_event.is_set(): finish_reason="stopped"; break
                                if time.time() - start_time >= time_limit_sec: finish_reason="time_limit"; break

                                current_val_for_dir_auto += (direction_sign_auto * step_auto)
                                test_params_auto = params_at_dir_start_auto.copy()
                                test_params_auto[param_name] = float(f"{current_val_for_dir_auto:.6g}") if is_float_param else int(round(current_val_for_dir_auto))

                                queue_status(f"Thử {dir_text_auto} (auto): {param_name}={test_params_auto[param_name]:.4g}...")

                                perf_result_auto = run_combined_perf_test_wrapper(test_params_auto, combination_algo_names, start_date, end_date)
                                steps_done_total += 1
                                queue_progress(min(0.95, (time.time() - start_time) / time_limit_sec if time_limit_sec > 0 else 0.0))

                                if self.optimizer_stop_event.is_set(): finish_reason="stopped"; break

                                if perf_result_auto is not None:
                                    new_score_auto = get_primary_score(perf_result_auto)
                                    if new_score_auto > current_best_score_tuple:
                                        queue_log("BEST", f"  -> Cải thiện ({dir_char_auto} auto)! {param_name}={test_params_auto[param_name]:.4g}. Score mới: {new_score_auto}", tag="BEST")
                                        current_best_params = test_params_auto.copy()
                                        params_at_dir_start_auto = test_params_auto.copy()
                                        current_val_for_dir_auto = test_params_auto[param_name]

                                        current_best_perf = perf_result_auto
                                        current_best_score_tuple = new_score_auto
                                        queue_best_update(current_best_params, current_best_score_tuple)
                                        params_changed_in_cycle = True
                                        no_improve_streak_auto = 0
                                    else:
                                        no_improve_streak_auto += 1
                                        queue_log("DEBUG", f"  -> Không cải thiện ({dir_char_auto} auto) {param_name}={test_params_auto[param_name]:.4g}. Streak: {no_improve_streak_auto}")

                                    if no_improve_streak_auto >= STALL_THRESHOLD:
                                        queue_log("DEBUG", f"    Dừng hướng {dir_char_auto} cho {param_name} do không cải thiện {STALL_THRESHOLD} lần.")
                                        break
                                else:
                                    no_improve_streak_auto += 1
                                    queue_log("WARNING", f"  -> Lỗi Test {dir_char_auto} auto {param_name}={test_params_auto[param_name]:.4g}. Streak: {no_improve_streak_auto}", tag="WARNING")
                                    if no_improve_streak_auto >= STALL_THRESHOLD:
                                        queue_log("DEBUG", f"    Dừng hướng {dir_char_auto} cho {param_name} do lỗi test + không cải thiện.")
                                        break

                            if finish_reason in ["stopped", "time_limit"]: break
                        if finish_reason in ["stopped", "time_limit"]: break
                
                if finish_reason in ["stopped", "time_limit"]: break

                if not params_changed_in_cycle and cycle > 0:
                    queue_log("INFO", f"Không có cải thiện nào trong chu kỳ {cycle + 1}. Dừng tối ưu.", tag="PROGRESS")
                    finish_reason = "no_improvement"
                    break
            
            queue_progress(1.0)
            final_message_worker = ""
            if finish_reason == "stopped": final_message_worker = "Dừng bởi người dùng."
            elif finish_reason == "time_limit": final_message_worker = f"Đã hết thời gian tối ưu ({time_limit_sec/60:.0f} phút)."
            elif finish_reason == "no_improvement": final_message_worker = "Tối ưu dừng sớm do không cải thiện thêm."
            elif finish_reason == "no_params": final_message_worker = "Thuật toán không có tham số để tối ưu (Auto/Custom)."
            elif finish_reason == "resume_error": final_message_worker = "Lỗi khi kiểm tra lại tham số đã tải."
            elif finish_reason == "initial_test_error": final_message_worker = "Lỗi test hiệu suất ban đầu."
            elif finish_reason == "critical_error": final_message_worker = "Lỗi nghiêm trọng trong worker."
            else: final_message_worker = "Tối ưu hoàn tất."

            can_log_or_save_final = current_best_params is not None and finish_reason not in ["no_params", "resume_error", "initial_test_error", "critical_error"]

            if can_log_or_save_final:
                final_message_worker += " Kết quả tốt nhất đã được lưu."
                queue_log("BEST", "="*10 + " TỐI ƯU KẾT THÚC (AUTO/CUSTOM) " + "="*10, tag="BEST")
                queue_log("BEST", f"Lý do kết thúc: {finish_reason}", tag="BEST")
                queue_log("BEST", f"Tham số tốt nhất tìm được: {current_best_params}", tag="BEST")
                score_desc_final = "(Top3%, Top5%, Top1%, -AvgRepT10)"
                queue_log("BEST", f"Điểm số tốt nhất {score_desc_final}: ({', '.join(f'{s:.3f}' for s in current_best_score_tuple)})", tag="BEST")
                if current_best_perf:
                     queue_log("BEST", f"Chi tiết hiệu suất tốt nhất: Top3={current_best_perf.get('acc_top_3_pct',0.0):.2f}%, Top5={current_best_perf.get('acc_top_5_pct',0.0):.2f}%, Top1={current_best_perf.get('acc_top_1_pct',0.0):.2f}%, Lặp TB={current_best_perf.get('avg_top10_repetition',0.0):.2f}", tag="BEST")

                try:
                    final_timestamp_save = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    success_dir_save = target_dir / "success"
                    success_dir_save.mkdir(parents=True, exist_ok=True)

                    perf_metric_for_filename = current_best_perf.get('acc_top_3_pct', 0.0) if current_best_perf else 0.0
                    perf_str_filename = f"top3_{perf_metric_for_filename:.1f}"
                    
                    base_algo_stem = target_algo_data['path'].stem
                    success_filename_base_save = f"optimized_{base_algo_stem}_{perf_str_filename}_{final_timestamp_save}"

                    success_filename_py_save = success_filename_base_save + ".py"
                    final_py_path_save = success_dir_save / success_filename_py_save
                    final_modified_source_save = self.modify_algorithm_source_ast(source_code, class_name, current_best_params)
                    if final_modified_source_save:
                        final_py_path_save.write_text(final_modified_source_save, encoding='utf-8')
                    else:
                         queue_log("ERROR", "Lỗi khi tạo source code đã chỉnh sửa để lưu file .py cuối cùng.", tag="ERROR")
                    
                    success_filename_json_save = success_filename_base_save + ".json"
                    final_json_path_save = success_dir_save / success_filename_json_save
                    final_save_data_json = {
                        "optimization_mode": "auto_hill_climb",
                        "target_algorithm": target_display_name,
                        "params": current_best_params,
                        "performance": current_best_perf if current_best_perf else "N/A",
                        "score_tuple": list(current_best_score_tuple),
                        "combination_algorithms": combination_algo_names,
                        "optimization_range": f"{start_date:%Y-%m-%d}_to_{end_date:%Y-%m-%d}",
                        "optimization_duration_seconds": round(time.time() - start_time, 1),
                        "finish_reason": finish_reason,
                        "finish_timestamp": datetime.datetime.now().isoformat()
                    }
                    try:
                        final_json_path_save.write_text(json.dumps(final_save_data_json, indent=4, ensure_ascii=False), encoding='utf-8')
                        queue_log("BEST", f"Đã lưu kết quả tối ưu vào thư mục: {success_dir_save.relative_to(self.base_dir)}", tag="BEST")

                        if delete_old_files_flag:
                            optimizer_worker_logger.info("Delete old files flag is True. Attempting to delete inferior files (Auto/Custom mode).")
                            self._delete_inferior_optimized_files(
                                success_dir=success_dir_save,
                                current_best_score_tuple=current_best_score_tuple,
                                current_best_py_path=final_py_path_save,
                                current_best_json_path=final_json_path_save,
                                worker_logger=optimizer_worker_logger,
                                queue_log_func=queue_log,
                                algo_stem_filter=base_algo_stem
                            )

                    except Exception as json_save_err_final:
                         queue_log("ERROR", f"Lỗi lưu file JSON kết quả cuối: {json_save_err_final}", tag="ERROR")
                         final_message_worker += "\n(Lỗi lưu file JSON kết quả!)"

                except Exception as final_save_err_overall:
                    queue_log("ERROR", f"Lỗi lưu kết quả cuối cùng: {final_save_err_overall}", tag="ERROR")
                    final_message_worker += "\n(Lỗi lưu file kết quả!)"
            elif not can_log_or_save_final and finish_reason not in ["no_params", "resume_error", "initial_test_error", "critical_error"]:
                 final_message_worker = "Không tìm thấy tham số nào tốt hơn trạng thái bắt đầu, hoặc không có thay đổi nào được áp dụng."
                 queue_log("INFO", "Không tìm thấy tham số tốt hơn hoặc không có thay đổi nào được áp dụng trong quá trình tối ưu.", tag="INFO")
            
            is_successful_run_final = finish_reason in ["completed", "time_limit", "no_improvement"] and can_log_or_save_final
            
            queue_finished(final_message_worker, success=is_successful_run_final, reason=finish_reason)

        except Exception as worker_err_critical:
            finish_reason = "critical_error"
            optimizer_worker_logger.critical(f"Worker exception (Auto/Custom Mode): {worker_err_critical}", exc_info=True)
            error_detail = f"Lỗi nghiêm trọng trong luồng tối ưu (Auto/Custom): {type(worker_err_critical).__name__} - {str(worker_err_critical)[:100]}"
            queue_error(error_detail) 
            queue_finished(f"Lỗi nghiêm trọng: {worker_err_critical}", success=False, reason=finish_reason)
        finally:
            optimizer_worker_logger.info(f"_optimization_worker finished. Reason: {finish_reason}")

    def _combination_optimization_worker(self, target_display_name, start_date, end_date, time_limit_sec,
                                         generation_params,
                                         combination_algo_names,
                                         initial_best_params=None,
                                         initial_best_score_tuple=None,
                                         delete_old_files_flag=False):
        start_time = time.time()
        optimizer_worker_logger = logging.getLogger("OptimizerWorker.Combo")
        optimizer_worker_logger.info(f"Starting Generated Combinations optimization worker. Target: {target_display_name}")

        def queue_log(level, text, tag=None):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                try: self.optimizer_queue.put({"type": "log", "payload": {"level": level, "text": text, "tag": tag}})
                except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (log): {q_err}")
        def queue_status(text):
            if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "status", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (status): {q_err}")
        def queue_progress(current, total):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "progress", "payload": {"current": current, "total": total}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (progress dict): {q_err}")
        def queue_best_update(params, score_tuple):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "best_update", "payload": {"params": params, "score_tuple": score_tuple}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (best_update): {q_err}")
        def queue_finished(message, success=True, reason="finished"):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "finished", "payload": {"message": message, "success": success, "reason": reason}})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (finished): {q_err}")
        def queue_error(text):
             if hasattr(self, 'optimizer_queue') and self.optimizer_queue:
                 try: self.optimizer_queue.put({"type": "error", "payload": text})
                 except Exception as q_err: optimizer_worker_logger.warning(f"Failed queue put (error): {q_err}")

        throttling_enabled_opt = False
        sleep_duration_opt = 0.005
        if hasattr(self.main_app, 'cpu_throttling_enabled'):
            throttling_enabled_opt = self.main_app.cpu_throttling_enabled
        if hasattr(self.main_app, 'throttle_sleep_duration'):
            sleep_duration_opt = self.main_app.throttle_sleep_duration
        optimizer_worker_logger.debug(f"_combination_optimization_worker Throttling: Enabled={throttling_enabled_opt}, Duration={sleep_duration_opt}s")

        finish_reason = "completed"
        generated_combinations_list = []
        total_combinations_count = 0
        current_best_params_combo = None
        current_best_perf_combo = None
        current_best_score_tuple_combo = (-1.0, -1.0, -1.0, -100.0)

        try:
            optimizer_worker_logger.debug(f"Setting up combo worker for target: {target_display_name}")
            if target_display_name not in self.loaded_algorithms:
                 raise ValueError(f"Target algorithm '{target_display_name}' not loaded in combo worker.")

            target_algo_data_combo = self.loaded_algorithms[target_display_name]
            original_path_combo = target_algo_data_combo['path']
            class_name_combo = target_algo_data_combo['class_name']
            
            try:
                source_code_combo = original_path_combo.read_text(encoding='utf-8')
                optimizer_worker_logger.debug(f"Successfully read source code for {original_path_combo.name}")
            except Exception as read_err_combo:
                raise RuntimeError(f"Combo worker failed to read source code for {original_path_combo.name}: {read_err_combo}")

            if not hasattr(self, 'current_optimize_target_dir') or not self.current_optimize_target_dir:
                 raise RuntimeError("Combo worker cannot determine optimize target directory.")
            target_dir_combo = self.current_optimize_target_dir
            optimizer_worker_logger.debug(f"Using optimize target directory: {target_dir_combo}")
            
            optimizer_worker_logger.info("Starting parameter combination generation phase...")
            queue_status("Đang tạo bộ tham số...")
            queue_log("INFO", "Bắt đầu tạo các bộ tham số kết hợp...", tag="GEN_COMBO")
            queue_progress(0, 1)

            if not generation_params or not isinstance(generation_params, dict):
                raise ValueError("Combo worker received invalid generation_params.")
            
            orig_params_for_gen_combo = generation_params.get('original_params')
            num_values_for_gen_combo = generation_params.get('num_values')
            method_for_gen_combo = generation_params.get('method')
            max_combinations_limit_worker = generation_params.get('max_combinations')
            
            if not orig_params_for_gen_combo or not isinstance(num_values_for_gen_combo, int) or not method_for_gen_combo:
                 raise ValueError("Combo worker missing detailed generation parameters (original_params, num_values, method).")
            optimizer_worker_logger.debug(f"Generation params: num_values={num_values_for_gen_combo}, method='{method_for_gen_combo}', max_combinations_limit={max_combinations_limit_worker}")

            generation_start_time_combo = time.time()
            generated_combinations_list = self._generate_parameter_combinations(
                orig_params_for_gen_combo, num_values_for_gen_combo, method_for_gen_combo,
                max_combinations_limit=max_combinations_limit_worker
            )
            generation_duration_combo = time.time() - generation_start_time_combo
            optimizer_worker_logger.info(f"Parameter combination generation finished in {generation_duration_combo:.2f} seconds.")

            if not generated_combinations_list:
                optimizer_worker_logger.error("Parameter generation returned an empty list.")
                queue_log("ERROR", "Không thể tạo bộ tham số nào (kết quả trống).", tag="ERROR")
                queue_finished("Tạo bộ tham số thất bại.", success=False, reason="combo_generation_failed")
                return

            total_combinations_count = len(generated_combinations_list)
            if total_combinations_count == 0:
                 optimizer_worker_logger.error("Generated combinations list is empty after generation.")
                 queue_log("ERROR", "Danh sách bộ tham số rỗng sau khi tạo.", tag="ERROR")
                 queue_finished("Tạo bộ tham số thất bại (danh sách rỗng).", success=False, reason="combo_generation_failed_empty")
                 return
            
            queue_status(f"Đã tạo {total_combinations_count} bộ. Bắt đầu kiểm tra...")
            queue_log("INFO", f"Đã tạo thành công {total_combinations_count} bộ tham số (giới hạn: {max_combinations_limit_worker if max_combinations_limit_worker else 'không'}).", tag="GEN_COMBO")


            def run_combined_perf_test_wrapper_combo(params_to_test_in_wrapper, combo_names_in_wrapper, start_dt_in_wrapper, end_dt_in_wrapper):
                 optimizer_worker_logger.debug(f"Calling run_combined_performance_test for params: {list(params_to_test_in_wrapper.keys())}")
                 return self.run_combined_performance_test(
                     target_display_name=target_display_name,
                     target_algo_source=source_code_combo,
                     target_class_name=class_name_combo,
                     target_params_to_test=params_to_test_in_wrapper,
                     combination_algo_display_names=combo_names_in_wrapper,
                     test_start_date=start_dt_in_wrapper,
                     test_end_date=end_dt_in_wrapper,
                     optimize_target_dir=target_dir_combo
                 )

            def get_primary_score_combo(perf_dict):
                 if not perf_dict: return (-1.0, -1.0, -1.0, -100.0)
                 return (perf_dict.get('acc_top_3_pct',0.0),
                         perf_dict.get('acc_top_5_pct',0.0),
                         perf_dict.get('acc_top_1_pct',0.0),
                         -perf_dict.get('avg_top10_repetition',100.0))

            optimizer_worker_logger.info(f"Starting performance testing for {total_combinations_count} parameter combinations...")
            queue_progress(0, total_combinations_count)

            for idx_combo, test_params_combo in enumerate(generated_combinations_list):
                current_progress_idx_combo = idx_combo + 1

                if self.optimizer_stop_event.is_set():
                    finish_reason = "stopped"
                    optimizer_worker_logger.info("Stop event detected during testing loop (Generated Combinations).")
                    break
                
                if throttling_enabled_opt and sleep_duration_opt > 0:
                    time.sleep(sleep_duration_opt)
                    if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                    while self.optimizer_pause_event.is_set():
                        if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                        time.sleep(0.1)
                    if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break

                while self.optimizer_pause_event.is_set():
                    queue_status(f"Đã tạm dừng (đang ở bộ {current_progress_idx_combo}/{total_combinations_count})")
                    if self.optimizer_stop_event.is_set(): finish_reason = "stopped"; break
                    time.sleep(0.5)
                if finish_reason == "stopped": break

                elapsed_time_combo = time.time() - start_time
                if elapsed_time_combo >= time_limit_sec:
                    finish_reason = "time_limit"
                    optimizer_worker_logger.info("Time limit reached during testing loop (Generated Combinations).")
                    break

                queue_status(f"Kiểm tra bộ {current_progress_idx_combo}/{total_combinations_count}...")
                queue_progress(current_progress_idx_combo, total_combinations_count)

                optimizer_worker_logger.debug(f"Running performance test for combination {current_progress_idx_combo}")
                perf_result_combo = run_combined_perf_test_wrapper_combo(
                    params_to_test_in_wrapper=test_params_combo,
                    combo_names_in_wrapper=combination_algo_names,
                    start_dt_in_wrapper=start_date,
                    end_dt_in_wrapper=end_date
                )
                optimizer_worker_logger.debug(f"Performance test for combo {current_progress_idx_combo} completed.")

                if self.optimizer_stop_event.is_set():
                    finish_reason="stopped"
                    optimizer_worker_logger.info("Stop event detected immediately after performance test (Generated Combinations).")
                    break

                if perf_result_combo is not None:
                    new_score_combo = get_primary_score_combo(perf_result_combo)
                    optimizer_worker_logger.debug(f"Combo {current_progress_idx_combo} score: {new_score_combo}")
                    if new_score_combo > current_best_score_tuple_combo:
                        queue_log("BEST", f"Tìm thấy bộ tốt hơn! Bộ {current_progress_idx_combo}/{total_combinations_count}. Score: {new_score_combo}", tag="BEST")
                        optimizer_worker_logger.info(f"New best score found (Generated Combinations): {new_score_combo} > {current_best_score_tuple_combo} at index {idx_combo}")
                        optimizer_worker_logger.debug(f"  Best Params Updated: {test_params_combo}")
                        queue_log("DEBUG", f"  Params: {test_params_combo}")

                        current_best_params_combo = test_params_combo.copy()
                        current_best_perf_combo = perf_result_combo
                        current_best_score_tuple_combo = new_score_combo
                        queue_best_update(current_best_params_combo, current_best_score_tuple_combo)
                    else:
                        optimizer_worker_logger.debug(f"Combination {current_progress_idx_combo} score {new_score_combo} not better than current best {current_best_score_tuple_combo}")
                else:
                    queue_log("WARNING", f"Lỗi khi kiểm tra bộ tham số {current_progress_idx_combo}.", tag="WARNING")
                    optimizer_worker_logger.warning(f"Performance test returned None for combination {current_progress_idx_combo}.")

            optimizer_worker_logger.info(f"Finished testing loop (Generated Combinations). Reason: {finish_reason}")

            queue_progress(total_combinations_count, total_combinations_count)

            final_message_combo = ""
            if finish_reason == "stopped": final_message_combo = "Dừng bởi người dùng."
            elif finish_reason == "time_limit": final_message_combo = f"Đã hết thời gian tối ưu ({time_limit_sec/60:.0f} phút)."
            elif finish_reason == "critical_error": final_message_combo = "Lỗi nghiêm trọng trong worker."
            elif finish_reason == "combo_generation_failed": final_message_combo = "Tạo bộ tham số thất bại."
            elif finish_reason == "combo_generation_failed_empty": final_message_combo = "Tạo bộ tham số thất bại (danh sách rỗng)."
            elif current_best_params_combo is None:
                final_message_combo = "Hoàn thành kiểm tra nhưng không tìm thấy bộ tham số nào cho kết quả hợp lệ."
                finish_reason = "combo_mode_no_results"
            else:
                final_message_combo = "Hoàn thành kiểm tra các bộ tham số."

            can_log_or_save_combo = current_best_params_combo is not None and finish_reason not in [
                "critical_error", "combo_mode_no_results", "combo_generation_failed", "combo_generation_failed_empty"
            ]

            if can_log_or_save_combo:
                final_message_combo += " Kết quả tốt nhất đã được lưu."
                queue_log("BEST", "="*10 + " TỐI ƯU KẾT THÚC (BỘ THAM SỐ) " + "="*10, tag="BEST")
                queue_log("BEST", f"Lý do kết thúc: {finish_reason}", tag="BEST")
                queue_log("BEST", f"Đã tạo và kiểm tra tổng cộng: {total_combinations_count} bộ", tag="BEST")
                queue_log("BEST", f"Tham số tốt nhất tìm được: {current_best_params_combo}", tag="BEST")
                score_desc_combo = "(Top3%, Top5%, Top1%, -AvgRepT10)"
                queue_log("BEST", f"Điểm số tốt nhất {score_desc_combo}: ({', '.join(f'{s:.3f}' for s in current_best_score_tuple_combo)})", tag="BEST")
                if current_best_perf_combo:
                     queue_log("BEST", f"Chi tiết hiệu suất tốt nhất: Top3={current_best_perf_combo.get('acc_top_3_pct',0.0):.2f}%, Top5={current_best_perf_combo.get('acc_top_5_pct',0.0):.2f}%, Top1={current_best_perf_combo.get('acc_top_1_pct',0.0):.2f}%, Lặp TB={current_best_perf_combo.get('avg_top10_repetition',0.0):.2f}", tag="BEST")

                try:
                    optimizer_worker_logger.info("Saving best results found (Generated Combinations)...")
                    final_timestamp_combo_save = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    success_dir_combo_save = target_dir_combo / "success"
                    success_dir_combo_save.mkdir(parents=True, exist_ok=True)

                    perf_metric_combo_filename = current_best_perf_combo.get('acc_top_3_pct', 0.0) if current_best_perf_combo else 0.0
                    perf_str_combo_filename = f"top3_{perf_metric_combo_filename:.1f}"
                    
                    base_algo_stem_combo = target_algo_data_combo['path'].stem
                    success_filename_base_combo_save = f"optimized_combo_{base_algo_stem_combo}_{perf_str_combo_filename}_{final_timestamp_combo_save}"
                    optimizer_worker_logger.debug(f"Base filename for saving (Generated Combinations): {success_filename_base_combo_save}")

                    success_filename_py_combo_save = success_filename_base_combo_save + ".py"
                    final_py_path_combo_save = success_dir_combo_save / success_filename_py_combo_save
                    optimizer_worker_logger.debug(f"Attempting to save Python file: {final_py_path_combo_save}")
                    final_mod_src_combo_save = self.modify_algorithm_source_ast(source_code_combo, class_name_combo, current_best_params_combo)
                    if final_mod_src_combo_save:
                        final_py_path_combo_save.write_text(final_mod_src_combo_save, encoding='utf-8')
                        optimizer_worker_logger.info(f"Saved best parameters to Python file: {final_py_path_combo_save.name}")
                    else:
                         queue_log("ERROR", "Lỗi khi tạo source code đã chỉnh sửa để lưu file .py cuối cùng (Generated Combinations).", tag="ERROR")
                         optimizer_worker_logger.error("Failed to generate modified source code for saving (Generated Combinations).")

                    success_filename_json_combo_save = success_filename_base_combo_save + ".json"
                    final_json_path_combo_save = success_dir_combo_save / success_filename_json_combo_save
                    optimizer_worker_logger.debug(f"Attempting to save JSON file: {final_json_path_combo_save}")
                    final_save_data_json_combo = {
                        "optimization_mode": "generated_combinations",
                        "target_algorithm": target_display_name,
                        "total_combinations_generated": total_combinations_count,
                        "generation_method": method_for_gen_combo,
                        "generation_num_values_per_param": num_values_for_gen_combo,
                        "params": current_best_params_combo,
                        "performance": current_best_perf_combo if current_best_perf_combo else "N/A",
                        "score_tuple": list(current_best_score_tuple_combo),
                        "combination_algorithms": combination_algo_names,
                        "optimization_range": f"{start_date:%Y-%m-%d}_to_{end_date:%Y-%m-%d}",
                        "optimization_duration_seconds": round(time.time() - start_time, 1),
                        "finish_reason": finish_reason,
                        "finish_timestamp": datetime.datetime.now().isoformat()
                    }
                    try:
                        final_json_path_combo_save.write_text(json.dumps(final_save_data_json_combo, indent=4, ensure_ascii=False), encoding='utf-8')
                        queue_log("BEST", f"Đã lưu kết quả tối ưu vào thư mục: {success_dir_combo_save.relative_to(self.base_dir)}", tag="BEST")
                        optimizer_worker_logger.info(f"Saved optimization details to JSON file: {final_json_path_combo_save.name}")
                        if delete_old_files_flag:
                            optimizer_worker_logger.info("Delete old files flag is True. Attempting to delete inferior files (Combo mode).")
                            self._delete_inferior_optimized_files(
                                success_dir=success_dir_combo_save,
                                current_best_score_tuple=current_best_score_tuple_combo,
                                current_best_py_path=final_py_path_combo_save,
                                current_best_json_path=final_json_path_combo_save,
                                worker_logger=optimizer_worker_logger,
                                queue_log_func=queue_log,
                                algo_stem_filter=base_algo_stem_combo,
                                prefix_filter="optimized_combo_"
                            )
                    except Exception as json_save_err_combo:
                         queue_log("ERROR", f"Lỗi lưu file JSON kết quả cuối (Generated Combinations): {json_save_err_combo}", tag="ERROR")
                         optimizer_worker_logger.error(f"Failed to save JSON results file (Generated Combinations): {json_save_err_combo}", exc_info=True)
                         final_message_combo += "\n(Lỗi lưu file JSON kết quả!)"

                except Exception as final_save_err_combo_overall:
                    queue_log("ERROR", f"Lỗi lưu kết quả cuối cùng (Generated Combinations): {final_save_err_combo_overall}", tag="ERROR")
                    optimizer_worker_logger.error(f"Error during final result saving (Generated Combinations): {final_save_err_combo_overall}", exc_info=True)
                    final_message_combo += "\n(Lỗi lưu file kết quả!)"

            is_successful_run_combo = finish_reason in ["completed", "time_limit"] and can_log_or_save_combo
            optimizer_worker_logger.info(f"Combo Worker sending finished signal. Success: {is_successful_run_combo}, Reason: {finish_reason}")
            queue_finished(final_message_combo, success=is_successful_run_combo, reason=finish_reason)

        except Exception as worker_err_critical_combo:
            finish_reason = "critical_error"
            optimizer_worker_logger.critical(f"Combo Worker encountered a critical exception: {worker_err_critical_combo}", exc_info=True)
            error_detail_combo = f"Lỗi nghiêm trọng trong luồng tạo bộ tham số: {type(worker_err_critical_combo).__name__} - {str(worker_err_critical_combo)[:100]}"
            queue_error(error_detail_combo)
            queue_finished(f"Lỗi nghiêm trọng: {worker_err_critical_combo}", success=False, reason=finish_reason)
        finally:
            optimizer_worker_logger.info("Combination optimization worker thread finished.")

    def _save_optimization_state(self, reason="unknown"):

        if not self.selected_algorithm_for_optimize or not self.current_optimize_target_dir or self.current_best_params is None:
            optimizer_logger.warning("Attempted to save state, but required info is missing.")
            return


        if self.current_optimization_mode == 'generated_combinations':
            optimizer_logger.info("Skipping state save for 'generated_combinations' mode.")
            return

        try:
            target_dir = self.current_optimize_target_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            algo_stem = self.loaded_algorithms[self.selected_algorithm_for_optimize]['path'].stem
            state_file_path = target_dir / f"optimization_state_{algo_stem}.json"

            start_date_str = getattr(self, 'last_opt_range_start_str', '')
            end_date_str = getattr(self, 'last_opt_range_end_str', '')
            optimization_range_str = f"{start_date_str}_to_{end_date_str}" if start_date_str and end_date_str else "unknown"

            state_data = {
                "target_algorithm": self.selected_algorithm_for_optimize,
                "params": self.current_best_params,
                "score_tuple": list(self.current_best_score_tuple),
                "combination_algorithms": self.current_combination_algos,
                "optimization_range": optimization_range_str,
                "save_reason": reason,
                "save_timestamp": datetime.datetime.now().isoformat()
            }
            state_file_path.write_text(json.dumps(state_data, indent=4, ensure_ascii=False), encoding='utf-8')
            self._log_to_optimizer_display("INFO", f"Đã lưu trạng thái tối ưu (Lý do: {reason}). File: {state_file_path.name}", tag="RESUME")
            self.check_resume_possibility()
        except Exception as e:
            self._log_to_optimizer_display("ERROR", f"Lỗi lưu trạng thái tối ưu: {e}", tag="ERROR")
            optimizer_logger.error(f"Error saving optimization state: {e}", exc_info=True)


    def run_combined_performance_test(self, target_display_name, target_algo_source, target_class_name,
                                       target_params_to_test, combination_algo_display_names,
                                       test_start_date, test_end_date, optimize_target_dir):
        target_instance = None
        combo_instances = {}
        temp_target_module_name = None
        temp_target_filepath = None
        
        worker_logger = logging.getLogger("OptimizerWorker.CombinedPerfTest")

        def queue_error_local(text):
             if hasattr(self, 'optimizer_queue') and isinstance(self.optimizer_queue, queue.Queue):
                 try: self.optimizer_queue.put({"type": "error", "payload": text})
                 except Exception as q_err_local: worker_logger.error(f"PerfTest: Failed to queue error '{text}': {q_err_local}")

        throttling_enabled_opt = False
        sleep_duration_opt = 0.005
        if hasattr(self.main_app, 'cpu_throttling_enabled'):
            throttling_enabled_opt = self.main_app.cpu_throttling_enabled
        if hasattr(self.main_app, 'throttle_sleep_duration'):
            sleep_duration_opt = self.main_app.throttle_sleep_duration

        try:
            worker_logger.debug(f"Starting combined performance test for {target_class_name} with params: {target_params_to_test}")
            
            try:
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected before AST modification in perf_test.")
                    return None

                modified_source = self.modify_algorithm_source_ast(target_algo_source, target_class_name, target_params_to_test)
                if not modified_source:
                    worker_logger.error("AST modification failed for performance test, returned no source.")
                    raise RuntimeError("AST modification failed for performance test (modify_algorithm_source_ast returned None).")

                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected after AST modification in perf_test.")
                    return None

                timestamp_suffix = int(time.time() * 10000) + random.randint(0, 9999)
                temp_target_filename = f"temp_perf_target_{target_class_name}_{timestamp_suffix}.py"
                
                if not optimize_target_dir or not isinstance(optimize_target_dir, Path):
                    worker_logger.error("optimize_target_dir is invalid or not provided to run_combined_performance_test.")
                    return None
                
                optimize_target_dir.mkdir(parents=True, exist_ok=True)
                temp_target_filepath = optimize_target_dir / temp_target_filename
                temp_target_filepath.write_text(modified_source, encoding='utf-8')
                worker_logger.debug(f"Temporary target file created: {temp_target_filepath}")

                if not (optimize_target_dir / "__init__.py").exists():
                    (optimize_target_dir / "__init__.py").touch()
                if not (self.optimize_dir / "__init__.py").exists():
                    (self.optimize_dir / "__init__.py").touch()
                
                relative_module_path = optimize_target_dir.relative_to(self.base_dir).parts
                temp_target_module_name = ".".join(relative_module_path) + "." + temp_target_filename[:-3]


                worker_logger.debug(f"Attempting to import temporary target module: {temp_target_module_name}")
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected before importing temporary module in perf_test.")
                    return None

                target_instance = self._import_and_instantiate_temp_algo(temp_target_filepath, temp_target_module_name, target_class_name)

                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected after importing temporary module in perf_test.")
                    return None

                if not target_instance:
                    worker_logger.error(f"Failed to load temporary target instance {target_class_name} from {temp_target_filepath}")
                    raise RuntimeError(f"Failed to load temporary target instance {target_class_name} from {temp_target_filepath}")
                worker_logger.debug(f"Successfully loaded temporary target instance: {type(target_instance)}")

            except Exception as target_load_err:
                worker_logger.error(f"Failed loading TARGET algorithm '{target_class_name}' for performance test: {target_load_err}", exc_info=True)
                return None

            worker_logger.debug(f"Loading {len(combination_algo_display_names)} combination algorithms for perf test.")
            data_copy_for_combo_perf = copy.deepcopy(self.results_data) if self.results_data else []
            
            for combo_name_perf in combination_algo_display_names:
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Stop event detected during combination algorithm loading in perf_test.")
                    return None
                if combo_name_perf not in self.loaded_algorithms:
                    worker_logger.warning(f"Skipping unknown combination algorithm in perf_test: {combo_name_perf}")
                    continue
                try:
                     combo_data_perf = self.loaded_algorithms[combo_name_perf]
                     combo_class_perf = combo_data_perf['instance'].__class__ 
                     combo_instance_perf = combo_class_perf(
                         data_results_list=data_copy_for_combo_perf,
                         cache_dir=self.calculate_dir
                     )
                     combo_instances[combo_name_perf] = combo_instance_perf
                     worker_logger.debug(f"Loaded combination instance for perf_test: {combo_name_perf}")
                except Exception as combo_load_err_perf:
                     worker_logger.error(f"Failed loading COMBO instance '{combo_name_perf}' for perf test: {combo_load_err_perf}", exc_info=True)
                     if combo_name_perf in combo_instances: del combo_instances[combo_name_perf]


            worker_logger.debug(f"Starting performance loop from {test_start_date} to {test_end_date}")
            results_map_perf = {r['date']: r['result'] for r in self.results_data} if self.results_data else {}
            history_cache_perf = {}
            if self.results_data:
                sorted_results_for_cache_perf = sorted(self.results_data, key=lambda x: x['date'])
                for i, r_perf in enumerate(sorted_results_for_cache_perf):
                     history_cache_perf[r_perf['date']] = sorted_results_for_cache_perf[:i]

            stats_perf = {'total_days_tested': 0, 'hits_top_1': 0, 'hits_top_3': 0, 'hits_top_5': 0, 
                          'hits_top_10': 0, 'errors': 0, 'avg_top10_repetition': 0.0, 
                          'max_top10_repetition_count': 0, 'top10_repetition_details': {}}
            all_top_10_combined_numbers_perf = []

            current_date_perf = test_start_date
            while current_date_perf <= test_end_date:
                if self.optimizer_stop_event.is_set():
                    worker_logger.info("Performance test stopped by event (start of date loop).")
                    return None
                
                if throttling_enabled_opt and sleep_duration_opt > 0:
                    time.sleep(sleep_duration_opt)
                    if self.optimizer_stop_event.is_set(): worker_logger.info("Performance test stopped by event (after sleep)."); return None
                    while self.optimizer_pause_event.is_set():
                        if self.optimizer_stop_event.is_set(): worker_logger.info("Performance test stopped during pause (inside sleep block)."); return None
                        time.sleep(0.1)
                    if self.optimizer_stop_event.is_set(): worker_logger.info("Performance test stopped by event (after pause check in sleep block)."); return None

                while self.optimizer_pause_event.is_set():
                    if self.optimizer_stop_event.is_set():
                        worker_logger.info("Performance test stopped during pause (main loop).")
                        return None
                    time.sleep(0.2)

                predict_date_perf = current_date_perf
                check_date_perf = predict_date_perf + datetime.timedelta(days=1)

                actual_result_dict_perf = results_map_perf.get(check_date_perf)
                hist_data_perf = history_cache_perf.get(predict_date_perf)

                if actual_result_dict_perf is None or hist_data_perf is None:
                    worker_logger.debug(f"Skipping {predict_date_perf}: actual_result is {actual_result_dict_perf is None}, hist_data is {hist_data_perf is None}")
                    stats_perf['errors'] +=1
                    current_date_perf += datetime.timedelta(days=1)
                    continue

                actual_numbers_set_perf = set()
                if target_instance: 
                    actual_numbers_set_perf = target_instance.extract_numbers_from_dict(actual_result_dict_perf)
                else:
                    worker_logger.error(f"target_instance is None for {predict_date_perf} in perf_test. This indicates a critical loading error.")
                    stats_perf['errors'] += 1
                    current_date_perf += datetime.timedelta(days=1)
                    continue
                
                if not actual_numbers_set_perf:
                    worker_logger.debug(f"No actual numbers extracted for check_date {check_date_perf}.")
                    stats_perf['errors'] += 1
                    current_date_perf += datetime.timedelta(days=1)
                    continue

                all_predictions_for_day_perf = {}
                hist_copy_for_day_perf = copy.deepcopy(hist_data_perf)

                if target_instance:
                    try:
                        if self.optimizer_stop_event.is_set(): worker_logger.info("Stop event before target predict in perf_test."); return None
                        all_predictions_for_day_perf[target_display_name] = target_instance.predict(predict_date_perf, hist_copy_for_day_perf)
                    except Exception as target_pred_err_perf:
                        worker_logger.error(f"Error predicting TARGET '{target_display_name}' for {predict_date_perf} in perf_test: {target_pred_err_perf}", exc_info=False)
                        all_predictions_for_day_perf[target_display_name] = {}
                        stats_perf['errors'] += 1
                else:
                    all_predictions_for_day_perf[target_display_name] = {}
                    stats_perf['errors'] += 1

                for combo_name_p, combo_inst_p in combo_instances.items():
                    try:
                        if self.optimizer_stop_event.is_set(): worker_logger.info("Stop event before combo predict in perf_test."); return None
                        all_predictions_for_day_perf[combo_name_p] = combo_inst_p.predict(predict_date_perf, hist_copy_for_day_perf)
                    except Exception as combo_pred_err_p:
                        worker_logger.error(f"Error predicting COMBO '{combo_name_p}' for {predict_date_perf} in perf_test: {combo_pred_err_p}", exc_info=False)
                        all_predictions_for_day_perf[combo_name_p] = {}
                        stats_perf['errors'] += 1

                combined_scores_raw_perf = {f"{i:02d}": 0.0 for i in range(100)}
                valid_algo_count_day = 0

                for algo_name_day, scores_dict_day in all_predictions_for_day_perf.items():
                    if not isinstance(scores_dict_day, dict) or not scores_dict_day:
                        continue

                    valid_algo_count_day += 1
                    for num_str_day, delta_val_day in scores_dict_day.items():
                        if isinstance(num_str_day, str) and len(num_str_day)==2 and num_str_day.isdigit():
                            try:
                                combined_scores_raw_perf[num_str_day] += float(delta_val_day)
                            except (ValueError, TypeError):
                                worker_logger.warning(f"Invalid delta value '{delta_val_day}' for number '{num_str_day}' from {algo_name_day} on {predict_date_perf}")
                                stats_perf['errors'] += 1
                
                if valid_algo_count_day == 0:
                    worker_logger.warning(f"No valid algorithm results for {predict_date_perf} in perf_test.")
                    stats_perf['errors'] += 1
                    current_date_perf += datetime.timedelta(days=1)
                    continue
                
                base_score_perf = 100.0
                combined_scores_list_perf = []
                for num_str_s, delta_s in combined_scores_raw_perf.items():
                     try:
                         final_score_s = base_score_perf + float(delta_s)
                         combined_scores_list_perf.append((int(num_str_s), final_score_s))
                     except (ValueError, TypeError):
                         worker_logger.warning(f"Could not convert final score for '{num_str_s}' (delta: {delta_s}) on {predict_date_perf}")
                         stats_perf['errors'] += 1
                
                if not combined_scores_list_perf:
                    worker_logger.warning(f"No valid scores after combining for {predict_date_perf} in perf_test")
                    stats_perf['errors'] += 1
                    current_date_perf += datetime.timedelta(days=1)
                    continue

                sorted_preds_perf = sorted(combined_scores_list_perf, key=lambda x: x[1], reverse=True)

                pred_top_1_p = {sorted_preds_perf[0][0]} if sorted_preds_perf else set()
                pred_top_3_p = {p[0] for p in sorted_preds_perf[:3]}
                pred_top_5_p = {p[0] for p in sorted_preds_perf[:5]}
                pred_top_10_p = {p[0] for p in sorted_preds_perf[:10]}

                if pred_top_1_p.intersection(actual_numbers_set_perf): stats_perf['hits_top_1'] += 1
                if pred_top_3_p.intersection(actual_numbers_set_perf): stats_perf['hits_top_3'] += 1
                if pred_top_5_p.intersection(actual_numbers_set_perf): stats_perf['hits_top_5'] += 1
                if pred_top_10_p.intersection(actual_numbers_set_perf): stats_perf['hits_top_10'] += 1

                all_top_10_combined_numbers_perf.extend(list(pred_top_10_p))
                stats_perf['total_days_tested'] += 1
                current_date_perf += datetime.timedelta(days=1)
            
            total_tested_perf = stats_perf['total_days_tested']
            worker_logger.info(f"Performance loop finished for perf_test. Total days successfully tested: {total_tested_perf}")

            if total_tested_perf > 0:
                stats_perf['acc_top_1_pct'] = (stats_perf['hits_top_1'] / total_tested_perf) * 100.0
                stats_perf['acc_top_3_pct'] = (stats_perf['hits_top_3'] / total_tested_perf) * 100.0
                stats_perf['acc_top_5_pct'] = (stats_perf['hits_top_5'] / total_tested_perf) * 100.0
                stats_perf['acc_top_10_pct'] = (stats_perf['hits_top_10'] / total_tested_perf) * 100.0

                if all_top_10_combined_numbers_perf:
                    top10_counts_perf = Counter(all_top_10_combined_numbers_perf)
                    total_predictions_in_top10_p = len(all_top_10_combined_numbers_perf)
                    unique_predictions_in_top10_p = len(top10_counts_perf)
                    stats_perf['avg_top10_repetition'] = total_predictions_in_top10_p / unique_predictions_in_top10_p if unique_predictions_in_top10_p > 0 else 0.0
                    stats_perf['max_top10_repetition_count'] = max(top10_counts_perf.values()) if top10_counts_perf else 0
                    stats_perf['top10_repetition_details'] = dict(top10_counts_perf.most_common(5))
                else:
                    stats_perf['avg_top10_repetition'] = 0.0
                    stats_perf['max_top10_repetition_count'] = 0
                    stats_perf['top10_repetition_details'] = {}
            else:
                stats_perf['acc_top_1_pct'] = 0.0; stats_perf['acc_top_3_pct'] = 0.0; 
                stats_perf['acc_top_5_pct'] = 0.0; stats_perf['acc_top_10_pct'] = 0.0; 
                stats_perf['avg_top10_repetition'] = 0.0
            
            worker_logger.info(f"Performance test calculation complete. Stats: {stats_perf}")
            return stats_perf

        except Exception as e_perf_critical:
            worker_logger.error(f"Performance test failed critically: {e_perf_critical}", exc_info=True)
            return None
        finally:
            worker_logger.debug("Cleaning up performance test resources (temp files, modules)...")
            target_instance = None
            combo_instances.clear()
            if temp_target_module_name and temp_target_module_name in sys.modules:
                try:
                    del sys.modules[temp_target_module_name]
                    worker_logger.debug(f"Removed temporary module from sys.modules: {temp_target_module_name}")
                except (KeyError, Exception) as del_err_module:
                     worker_logger.warning(f"Could not delete temp module '{temp_target_module_name}' from sys.modules: {del_err_module}")
            if temp_target_filepath and temp_target_filepath.exists():
                try:
                    temp_target_filepath.unlink()
                    worker_logger.debug(f"Deleted temporary python file: {temp_target_filepath}")
                except OSError as unlink_err_file:
                    worker_logger.warning(f"Could not delete temp python file '{temp_target_filepath}': {unlink_err_file}")

    def _import_and_instantiate_temp_algo(self, temp_filepath, temp_module_name, class_name_hint):

        worker_logger = logging.getLogger("OptimizerWorker.ImportHelper")
        worker_logger.debug(f"Attempting to import {temp_module_name} from {temp_filepath}")
        instance = None
        module_obj = None
        try:
            if temp_module_name in sys.modules:
                try: del sys.modules[temp_module_name]
                except KeyError: pass
                worker_logger.debug(f"Removed existing module cache for {temp_module_name}")

            spec = util.spec_from_file_location(temp_module_name, temp_filepath)
            if not spec or not spec.loader:
                raise ImportError(f"Could not create module spec for {temp_module_name} at {temp_filepath}")

            module_obj = util.module_from_spec(spec)
            if module_obj is None:
                 raise ImportError(f"Could not create module from spec for {temp_module_name}")

            sys.modules[temp_module_name] = module_obj
            worker_logger.debug(f"Executing module {temp_module_name}")
            spec.loader.exec_module(module_obj)
            worker_logger.debug(f"Module {temp_module_name} executed.")

            temp_class = getattr(module_obj, class_name_hint, None)
            if not temp_class or not inspect.isclass(temp_class) or not issubclass(temp_class, BaseAlgorithm):
                 worker_logger.debug(f"Class hint '{class_name_hint}' not found or invalid. Searching module...")
                 for name, obj in inspect.getmembers(module_obj):
                     if inspect.isclass(obj) and issubclass(obj, BaseAlgorithm) and obj is not BaseAlgorithm and obj.__module__ == temp_module_name:
                         temp_class = obj
                         worker_logger.debug(f"Found class '{name}' in {temp_module_name}")
                         break

            if not temp_class or not issubclass(temp_class, BaseAlgorithm):
                raise TypeError(f"No valid BaseAlgorithm subclass found in temporary module {temp_module_name}.")

            worker_logger.debug(f"Instantiating class {temp_class.__name__}")
            data_copy_for_instance = copy.deepcopy(self.results_data) if self.results_data else []
            instance = temp_class(data_results_list=data_copy_for_instance, cache_dir=self.calculate_dir)
            worker_logger.debug(f"Successfully instantiated {temp_class.__name__}")
            return instance

        except Exception as e:
            worker_logger.error(f"Import/Instantiate failed for {temp_filepath} (module: {temp_module_name}): {e}", exc_info=True)
            if temp_module_name and temp_module_name in sys.modules:
                try: del sys.modules[temp_module_name]
                except KeyError: pass
            return None

    def find_latest_successful_optimization(self, success_dir: Path, algo_stem: str):
        latest_file, latest_data, latest_timestamp = None, None, 0
        if success_dir.is_dir():
            try:
                patterns = [f"optimized_{algo_stem}_*_*.json", f"optimized_combo_{algo_stem}_*_*.json"]
                json_files = []
                for pattern in patterns:
                    json_files.extend(list(success_dir.glob(pattern)))
                optimizer_logger.debug(f"Scanning {success_dir} for patterns '{patterns}'. Found {len(json_files)} files.")

                for f_path in json_files:
                    try:
                        file_timestamp = 0
                        try:
                            parts = f_path.stem.split('_')
                            file_ts_str = f"{parts[-2]}_{parts[-1]}"
                            file_dt = datetime.datetime.strptime(file_ts_str, "%Y%m%d_%H%M%S")
                            file_timestamp = file_dt.timestamp()
                        except (ValueError, IndexError, Exception):
                            file_timestamp = f_path.stat().st_mtime
                            optimizer_logger.debug(f"Using mtime {file_timestamp} for {f_path.name}")


                        if file_timestamp > latest_timestamp:
                             try:
                                 data = json.loads(f_path.read_text(encoding='utf-8'))
                                 if "params" in data and "score_tuple" in data and "optimization_range" in data and "combination_algorithms" in data:
                                     latest_timestamp = file_timestamp
                                     latest_file = f_path
                                     latest_data = data
                                     optimizer_logger.debug(f"Found newer valid result: {f_path.name} (ts: {file_timestamp})")
                                 else:
                                      optimizer_logger.warning(f"Skipping JSON {f_path.name}: Missing required keys.")
                             except json.JSONDecodeError:
                                 optimizer_logger.warning(f"Skipping invalid JSON file: {f_path.name}")
                             except Exception as read_err:
                                  optimizer_logger.warning(f"Error reading/parsing {f_path.name}: {read_err}")

                    except Exception as file_proc_err:
                         optimizer_logger.warning(f"Error processing file {f_path.name} in success dir: {file_proc_err}")
            except Exception as e:
                optimizer_logger.error(f"Error scanning success directory {success_dir}: {e}", exc_info=True)

        if latest_file:
            optimizer_logger.info(f"Latest successful optimization found: {latest_file.name}")
            return latest_file, latest_data

        optimizer_logger.debug("No success file found, checking for state file...")
        state_file_path = self.optimize_dir / algo_stem / f"optimization_state_{algo_stem}.json"
        if state_file_path.exists():
            optimizer_logger.debug(f"Found state file: {state_file_path.name}")
            try:
                 data = json.loads(state_file_path.read_text(encoding='utf-8'))
                 if "params" in data and "score_tuple" in data and "optimization_range" in data and "combination_algorithms" in data:
                     optimizer_logger.info(f"Using state file as fallback: {state_file_path.name}")
                     return state_file_path, data
                 else:
                     optimizer_logger.warning(f"State file {state_file_path.name} missing required keys.")
            except json.JSONDecodeError:
                 optimizer_logger.warning(f"State file {state_file_path.name} is invalid JSON.")
            except Exception as read_err:
                 optimizer_logger.warning(f"Error reading/parsing state file {state_file_path.name}: {read_err}")

        optimizer_logger.info("No suitable success or state file found.")
        return None, None

    def check_resume_possibility(self, event=None):

        target_algo = self.selected_algorithm_for_optimize
        can_resume_flag = False

        if target_algo and target_algo in self.loaded_algorithms:
            algo_data = self.loaded_algorithms[target_algo]
            algo_stem = algo_data['path'].stem
            optimize_target_dir = self.optimize_dir / algo_stem
            success_dir = optimize_target_dir / "success"
            latest_file, latest_data = self.find_latest_successful_optimization(success_dir, algo_stem)
            if latest_file and latest_data:
                is_resumable_mode = latest_data.get('optimization_mode', 'auto_hill_climb') == 'auto_hill_climb'
                if is_resumable_mode:
                    can_resume_flag = True
                    optimizer_logger.debug(f"Resume possible for {target_algo} using file: {latest_file.name}")
                else:
                    optimizer_logger.debug(f"Found result file {latest_file.name}, but it's from 'generated_combinations' mode. Resume not applicable.")
            else:
                 optimizer_logger.debug(f"Resume not possible for {target_algo}: No valid file found.")

        self.can_resume = can_resume_flag

        if not self.optimizer_running:
            self.update_optimizer_ui_state()

    def update_status(self, message):

        optimizer_logger.info(f"Optimizer Status: {message}")
        if hasattr(self, 'opt_status_label'):
             self.opt_status_label.setText(f"Trạng thái: {message}")
             lower_msg = message.lower()
             if "lỗi" in lower_msg or "fail" in lower_msg:
                 self.opt_status_label.setStyleSheet("color: #dc3545;")
             elif "thành công" in lower_msg or "hoàn tất" in lower_msg:
                 self.opt_status_label.setStyleSheet("color: #28a745;")
             else:
                  self.opt_status_label.setStyleSheet("color: #6c757d;")
        else:
             optimizer_logger.warning("Optimizer status label not found.")


    def show_calendar_dialog_qt(self, target_line_edit: QLineEdit):

        if not self.results_data:
            QMessageBox.warning(self.get_main_window(), "Thiếu Dữ Liệu", "Chưa tải dữ liệu kết quả.")
            return

        min_date_dt = self.results_data[0]['date']
        max_date_dt = self.results_data[-1]['date']
        min_qdate = QDate(min_date_dt.year, min_date_dt.month, min_date_dt.day)
        max_qdate = QDate(max_date_dt.year, max_date_dt.month, max_date_dt.day)

        current_text = target_line_edit.text()
        current_qdate = QDate.currentDate()
        try:
            parsed_dt = datetime.datetime.strptime(current_text, '%d/%m/%Y').date()
            parsed_qdate = QDate(parsed_dt.year, parsed_dt.month, parsed_dt.day)
            if min_qdate <= parsed_qdate <= max_qdate:
                current_qdate = parsed_qdate
            else:
                 current_qdate = max_qdate
        except ValueError:
            current_qdate = max_qdate


        dialog = QDialog(self.get_main_window())
        dialog.setWindowTitle("Chọn Ngày")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setGridVisible(True)
        calendar.setMinimumDate(min_qdate)
        calendar.setMaximumDate(max_qdate)
        calendar.setSelectedDate(current_qdate)
        calendar.setStyleSheet("""
            QCalendarWidget QToolButton { color: black; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #E0E0E0; }
            QCalendarWidget QMenu { background-color: white; color: black; }
            QCalendarWidget QAbstractItemView:enabled { color: black; background-color: white; selection-background-color: #007BFF; selection-color: white; }
            QCalendarWidget QAbstractItemView:disabled { color: #CCCCCC; }
        """)

        layout.addWidget(calendar)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            selected_qdate = calendar.selectedDate()
            target_line_edit.setText(selected_qdate.toString("dd/MM/yyyy"))

    def _clear_cache_directory(self):

        cleared_count, error_count = 0, 0
        optimizer_logger.info(f"Clearing cache directory: {self.calculate_dir}")
        try:
            if self.calculate_dir.exists():
                for item in self.calculate_dir.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                            cleared_count += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            cleared_count += 1
                    except Exception as e:
                        optimizer_logger.error(f"Error removing cache item {item.name}: {e}")
                        error_count += 1
            if error_count > 0:
                 optimizer_logger.warning(f"Cache clear completed with {error_count} errors. Removed {cleared_count} items.")
            else:
                 optimizer_logger.info(f"Cache clear successful. Removed {cleared_count} items.")
        except Exception as e:
            optimizer_logger.error(f"Error accessing or iterating cache directory {self.calculate_dir}: {e}")

    def _load_optimization_log(self):

        if not self.selected_algorithm_for_optimize or self.selected_algorithm_for_optimize not in self.loaded_algorithms:
            return
        if not hasattr(self, 'opt_log_text'):
            return

        algo_data = self.loaded_algorithms[self.selected_algorithm_for_optimize]
        target_dir = self.optimize_dir / algo_data['path'].stem
        log_path = target_dir / "optimization_qt.log"
        self.current_optimization_log_path = log_path

        self.opt_log_text.clear()
        cursor = self.opt_log_text.textCursor()

        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue

                        tag = "INFO"
                        if "[ERROR]" in line or "[CRITICAL]" in line: tag = "ERROR"
                        elif "[WARNING]" in line: tag = "WARNING"
                        elif "[BEST]" in line: tag = "BEST"
                        elif "[DEBUG]" in line: tag = "DEBUG"
                        elif "[PROGRESS]" in line: tag = "PROGRESS"
                        elif "[CUSTOM_STEP]" in line: tag = "CUSTOM_STEP"
                        elif "[RESUME]" in line: tag = "RESUME"
                        elif "[COMBINE]" in line: tag = "COMBINE"
                        elif "[CONTROL]" in line: tag = "WARNING"
                        elif "[GEN_COMBO]" in line: tag = "GEN_COMBO"
                        elif line.startswith("==="): tag = "BEST" if "HOÀN TẤT" in line or "TỐI ƯU KẾT THÚC" in line else "PROGRESS"


                        log_format = self.log_formats.get(tag, self.log_formats["INFO"])
                        cursor.insertText(line + "\n", log_format)

                self.opt_log_text.moveCursor(QTextCursor.End)
            except Exception as e:
                cursor.insertText(f"LỖI ĐỌC LOG:\n{e}\n", self.log_formats["ERROR"])
                optimizer_logger.error(f"Error reading optimization log file {log_path}: {e}")
        else:
            cursor.insertText("Chưa có nhật ký tối ưu hóa cho thuật toán này.\n", self.log_formats["INFO"])

    def open_optimize_folder(self):

        target_dir_path = None
        main_window = self.get_main_window()

        if self.selected_algorithm_for_optimize and self.selected_algorithm_for_optimize in self.loaded_algorithms:
            algo_stem = self.loaded_algorithms[self.selected_algorithm_for_optimize]['path'].stem
            target_dir_path = self.optimize_dir / algo_stem
        else:
            target_dir_path = self.optimize_dir
            QMessageBox.information(main_window, "Thông Báo", f"Mở thư mục tối ưu chính:\n{target_dir_path}")

        if not target_dir_path: return

        try:
            target_dir_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(main_window, "Lỗi", f"Không thể tạo hoặc truy cập thư mục:\n{target_dir_path}\n\nLỗi: {e}")
            return

        url = QtCore.QUrl.fromLocalFile(str(target_dir_path.resolve()))
        if not QtGui.QDesktopServices.openUrl(url):
            QMessageBox.critical(main_window, "Lỗi", f"Không thể mở thư mục:\n{target_dir_path}")

    def _generate_parameter_combinations(self, original_params, num_values_per_param, method, max_combinations_limit=None):
        """Generates parameter value sets and their combinations, with an optional limit."""
        numeric_params = {k: v for k, v in original_params.items() if isinstance(v, (int, float))}
        if not numeric_params:
            optimizer_logger.warning("No numeric parameters found for combination generation.")
            return []

        all_param_value_lists = []
        param_names_ordered = list(numeric_params.keys())

        for name in param_names_ordered:
            orig_val = numeric_params[name]
            values = self._generate_single_parameter_values(name, orig_val, num_values_per_param, method)
            if not values:
                optimizer_logger.error(f"Failed to generate values for parameter '{name}'. Aborting combination generation.")
                return []
            all_param_value_lists.append(values)
            optimizer_logger.debug(f"Generated values for '{name}': {values}")

        combinations_iter = itertools.product(*all_param_value_lists)

        if max_combinations_limit is not None and max_combinations_limit > 0:
            estimated_total_before_limit = 1
            for p_list in all_param_value_lists:
                if len(p_list) > 0:
                     estimated_total_before_limit *= len(p_list)
                elif estimated_total_before_limit == 1 and not all_param_value_lists :
                     estimated_total_before_limit = 0


            if estimated_total_before_limit > max_combinations_limit:
                optimizer_logger.info(f"Raw estimated combinations ({estimated_total_before_limit}) > user limit ({max_combinations_limit}). Slicing...")
            else:
                optimizer_logger.info(f"Raw estimated combinations ({estimated_total_before_limit}) <= user limit ({max_combinations_limit}). No slicing needed for limit itself.")

            combinations_iter = itertools.islice(combinations_iter, max_combinations_limit)
            optimizer_logger.info(f"Will generate at most {max_combinations_limit} parameter sets due to user limit.")


        param_combinations_list = []
        for combo_values in combinations_iter:
            param_dict = original_params.copy()
            param_dict.update(dict(zip(param_names_ordered, combo_values)))
            param_combinations_list.append(param_dict)


        optimizer_logger.info(f"Total combinations actually generated: {len(param_combinations_list)}")
        return param_combinations_list

    def _generate_single_parameter_values(self, param_name, original_value, num_values, method):
        """Generates a list of N adjacent values for a single parameter."""
        values = set()
        is_float = isinstance(original_value, float)

        if num_values <= 0:
            optimizer_logger.warning(f"num_values for '{param_name}' is {num_values}, returning empty list.")
            return []
        if num_values == 1:
            return [original_value]

        values.add(original_value)
        num_around = num_values - 1
        num_increase = math.ceil(num_around / 2.0)
        num_decrease = math.floor(num_around / 2.0)

        if is_float:
            step = max(abs(original_value) * 0.02, 1e-4)
        else:
            step = 1

        current_val_inc = original_value
        for _ in range(int(num_increase)):
            current_val_inc += step
            val_to_add = float(f"{current_val_inc:.6g}") if is_float else int(round(current_val_inc))
            values.add(val_to_add)
            if len(values) >= num_values:
                break

        if len(values) < num_values:
            current_val_dec = original_value
            for _ in range(int(num_decrease)):
                current_val_dec -= step
                val_to_add = float(f"{current_val_dec:.6g}") if is_float else int(round(current_val_dec))
                values.add(val_to_add)
                if len(values) >= num_values:
                    break
        

        final_values = sorted(list(values))

        if len(final_values) > num_values:
            try:
                orig_idx = final_values.index(original_value)
            except ValueError:
                orig_idx = len(final_values) // 2

            needed_each_side = (num_values -1) // 2
            start_idx = max(0, orig_idx - needed_each_side)
            end_idx = start_idx + num_values
            if end_idx > len(final_values):
                end_idx = len(final_values)
                start_idx = max(0, end_idx - num_values)
            
            final_values = final_values[start_idx:end_idx]


        if not final_values and original_value is not None:
            optimizer_logger.warning(f"Could not generate distinct adjacent values for '{param_name}' around {original_value} with num_values={num_values}. Returning original value.")
            return [original_value]
        elif not final_values:
            optimizer_logger.error(f"Failed to generate any values for '{param_name}'. Returning empty list.")
            return []


        return final_values
