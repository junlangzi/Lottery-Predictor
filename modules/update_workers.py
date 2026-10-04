# -*- coding: utf-8 -*-
# Module: modules/update_workers.py
# Contains: GuideSyncWorker, UpdateCheckWorker, PerformUpdateWorker

import logging
import shutil
import datetime
from pathlib import Path
from packaging.version import parse as parse_version

try:
    from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
except ImportError:
    pass

class GuideSyncWorker(QObject):
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(str)

    def __init__(self, base_dir, index_url):
        super().__init__()
        self.base_dir = base_dir
        self.guide_dir = self.base_dir / "guide"
        self.index_url = index_url
        self.logger = logging.getLogger("GuideSync")

    @pyqtSlot()
    def run_sync(self):
        import requests
        try:
            self.progress_signal.emit("Đang khởi tạo thư mục...")
            if self.guide_dir.exists():
                shutil.rmtree(self.guide_dir)
            self.guide_dir.mkdir(parents=True, exist_ok=True)

            self.progress_signal.emit("Đang tải danh mục hướng dẫn...")
            response = requests.get(self.index_url, timeout=15)
            response.raise_for_status()
            index_content = response.text
            
            index_path = self.guide_dir / "index.txt"
            index_path.write_text(index_content, encoding='utf-8')

            pattern = re.compile(r"\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]")
            matches = pattern.findall(index_content)

            total = len(matches)
            for i, (g_id, link, info) in enumerate(matches):
                self.progress_signal.emit(f"Đang tải mục {i+1}/{total}: {info}...")
                
                try:
                    sub_res = requests.get(link, timeout=15)
                    sub_res.raise_for_status()
                    content = sub_res.text
                    
                    safe_id = "".join(c for c in g_id if c.isalnum() or c in ('-','_'))
                    file_path = self.guide_dir / f"{safe_id}.txt"
                    file_path.write_text(content, encoding='utf-8')
                    
                except Exception as e:
                    self.logger.error(f"Lỗi tải mục {info}: {e}")

            self.finished_signal.emit(True, "Đồng bộ hoàn tất!")

        except Exception as e:
            self.logger.error(f"Lỗi đồng bộ hướng dẫn: {e}")
            self.finished_signal.emit(False, f"Lỗi: {e}")


class UpdateCheckWorker(QObject):
    finished_signal = pyqtSignal()
    update_info_signal = pyqtSignal(str, str, bool)
    commit_history_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, main_app_ref):
        super().__init__()
        self.main_app = main_app_ref
        self.logger = logging.getLogger("UpdateCheckWorker")

    @pyqtSlot()
    def run_check(self):
        try:
            app = self.main_app
            self.logger.info("Bắt đầu kiểm tra cập nhật ứng dụng...")

            current_html = app._format_version_info_for_display(
                app.current_app_version_info, "Phiên bản đang sử dụng"
            )
            
            update_file_url = ""
            if hasattr(app, 'update_file_url_edit') and app.update_file_url_edit:
                update_file_url = app.update_file_url_edit.text().strip()
            
            if not update_file_url:
                self.logger.error("URL file cập nhật chưa được cấu hình.")
                self.error_signal.emit("URL file cập nhật chưa được cấu hình trong tab Update.")
                self.finished_signal.emit()
                return

            online_content = app._fetch_online_content(update_file_url, service_type="update_check")
            if online_content is None:
                self.error_signal.emit(f"Không thể tải nội dung từ:\n{update_file_url}\n(Kiểm tra kết nối mạng và URL)")
                self.finished_signal.emit()
                return

            app.online_app_content_cache = online_content
            app.online_app_version_info = app._extract_app_version_info(online_content)
            online_html = app._format_version_info_for_display(
                app.online_app_version_info, "Phiên bản mới (Online):"
            )
            update_available = app._compare_versions(
                app.current_app_version_info, app.online_app_version_info
            )
            self.update_info_signal.emit(current_html, online_html, update_available)

            program_update_list_url = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/UPDATE.md"
            
            self.logger.info(f"Đang tải lịch sử cập nhật chương trình từ: {program_update_list_url}")
            markdown_content = app._fetch_online_content(program_update_list_url, service_type="update_check")
            
            if markdown_content:
                history_html_display = app._parse_markdown_update_list(markdown_content)
                self.commit_history_signal.emit(history_html_display)
            else:
                self.commit_history_signal.emit("<p>Không thể tải lịch sử cập nhật chương trình (kiểm tra kết nối mạng hoặc URL).</p>")

            self.logger.info("Kiểm tra cập nhật ứng dụng hoàn tất.")
        except Exception as e:
            self.logger.error(f"Lỗi nghiêm trọng trong UpdateCheckWorker: {e}", exc_info=True)
            self.error_signal.emit(f"Lỗi không mong muốn trong quá trình kiểm tra cập nhật: {type(e).__name__}")
        finally:
            self.finished_signal.emit()


class PerformUpdateWorker(QObject):
    finished_signal = pyqtSignal(bool, str)
    error_signal = pyqtSignal(str)

    def __init__(self, main_app_ref):
        super().__init__()
        self.main_app = main_app_ref
        self.logger = logging.getLogger("PerformUpdateWorker")

    @pyqtSlot()
    def run_update(self):
        try:
            app = self.main_app
            self.logger.info("Bắt đầu quá trình thực hiện cập nhật...")

            online_content = app.online_app_content_cache
            if not online_content:
                online_file_url_ui = ""
                if hasattr(app, 'update_file_url_edit') and app.update_file_url_edit:
                    online_file_url_ui = app.update_file_url_edit.text().strip()
                
                if not online_file_url_ui:
                    self.logger.error("URL file cập nhật không hợp lệ để tải lại.")
                    self.error_signal.emit("URL file cập nhật không hợp lệ.")
                    self.finished_signal.emit(False, "Lỗi: URL file cập nhật không hợp lệ.")
                    return
                
                self.logger.info(f"Cache nội dung cập nhật rỗng. Tải lại từ: {online_file_url_ui}")
                online_content = app._fetch_online_content(online_file_url_ui, service_type="update_check")
                if online_content is None:
                    self.error_signal.emit(f"Không thể tải lại nội dung file cập nhật từ:\n{online_file_url_ui}\n(Kiểm tra kết nối mạng và URL)")
                    self.finished_signal.emit(False, f"Lỗi: Không thể tải lại nội dung file cập nhật.")
                    return
                app.online_app_content_cache = online_content

            target_filename_from_ui = ""
            if hasattr(app, 'update_save_filename_edit') and app.update_save_filename_edit:
                target_filename_from_ui = app.update_save_filename_edit.text().strip()

            if not target_filename_from_ui:
                self.logger.error("Tên file lưu cập nhật không được để trống.")
                self.error_signal.emit("Tên file lưu cập nhật không được để trống.")
                self.finished_signal.emit(False, "Lỗi: Tên file lưu cập nhật không được để trống.")
                return
            

            current_script_to_replace_path = None
            if getattr(sys, 'frozen', False):
                app_dir = Path(sys.executable).parent
                current_script_to_replace_path = app_dir / target_filename_from_ui
                self.logger.warning(f"Ứng dụng đóng gói. Sẽ cố gắng cập nhật file tại: {current_script_to_replace_path}")
            else:
                running_main_py_path = Path(__file__).resolve()
                current_script_to_replace_path = running_main_py_path.parent / target_filename_from_ui
            
            self.logger.info(f"Đường dẫn file đích để cập nhật: {current_script_to_replace_path}")

            backup_file_path = current_script_to_replace_path.with_name(current_script_to_replace_path.name + ".bak-" + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
            made_backup = False

            if current_script_to_replace_path.exists():
                self.logger.info(f"File đích '{current_script_to_replace_path.name}' tồn tại. Sẽ tiến hành đổi tên thành '{backup_file_path.name}'.")
                if backup_file_path.exists():
                    try:
                        backup_file_path.unlink()
                        self.logger.info(f"Đã xóa file .bak cũ trước khi sao lưu: {backup_file_path.name}")
                    except OSError as e_del_old_bank:
                        self.logger.warning(f"Không thể xóa file .bak cũ '{backup_file_path.name}': {e_del_old_bank}. Tiếp tục...")
                
                try:
                    shutil.move(str(current_script_to_replace_path), str(backup_file_path))
                    self.logger.info(f"Đã đổi tên '{current_script_to_replace_path.name}' thành '{backup_file_path.name}'")
                    made_backup = True
                except Exception as e_rename_backup:
                    self.logger.error(f"Không thể đổi tên file '{current_script_to_replace_path.name}' để tạo backup: {e_rename_backup}", exc_info=True)
                    self.error_signal.emit(f"Lỗi tạo file sao lưu cho '{current_script_to_replace_path.name}':\n{e_rename_backup}")
                    self.finished_signal.emit(False, f"Lỗi: Không thể tạo file sao lưu.")
                    return
            else:
                self.logger.info(f"File đích '{current_script_to_replace_path.name}' không tồn tại. Sẽ tạo file mới.")

            try:
                if not isinstance(online_content, str):
                    self.logger.error(f"Nội dung tải về không phải là chuỗi, mà là: {type(online_content)}")
                    self.error_signal.emit("Lỗi: Nội dung tải về không hợp lệ (không phải dạng văn bản).")
                    self.finished_signal.emit(False, "Lỗi: Nội dung tải về không hợp lệ.")
                    if made_backup and backup_file_path.exists() and not current_script_to_replace_path.exists():
                        try: shutil.move(str(backup_file_path), str(current_script_to_replace_path)); self.logger.info(f"Khôi phục từ backup do nội dung tải về lỗi.")
                        except Exception as e_restore_bad_content: self.logger.error(f"Lỗi khôi phục backup (bad content): {e_restore_bad_content}")
                    return

                normalized_newlines_content = online_content.replace('\r\n', '\n').replace('\r', '\n')
                final_content_to_write = normalized_newlines_content

                current_script_to_replace_path.write_text(final_content_to_write, encoding='utf-8', newline='\n')
                self.logger.info(f"Cập nhật thành công nội dung của {current_script_to_replace_path.name}")

                if made_backup and backup_file_path.exists():
                    try:
                        backup_file_path.unlink()
                        self.logger.info(f"Đã xóa file sao lưu: {backup_file_path.name}")
                    except OSError as e_delete_bank:
                        self.logger.warning(f"Không thể xóa file sao lưu '{backup_file_path.name}' sau khi cập nhật thành công: {e_delete_bank}")
                
                self.finished_signal.emit(True, f"Đã cập nhật thành công file: {current_script_to_replace_path.name}\nVui lòng khởi động lại ứng dụng.")
            
            except IOError as e_io:
                self.logger.error(f"Lỗi IOError khi ghi nội dung cập nhật vào {current_script_to_replace_path.name}: {e_io}", exc_info=True)
                if made_backup and backup_file_path.exists():
                    self.logger.info(f"Lỗi ghi file mới. Đang cố gắng khôi phục từ backup '{backup_file_path.name}'...")
                    try:
                        if current_script_to_replace_path.exists():
                            current_script_to_replace_path.unlink()
                        shutil.move(str(backup_file_path), str(current_script_to_replace_path))
                        self.logger.info(f"Đã khôi phục thành công file gốc từ '{backup_file_path.name}'.")
                    except Exception as e_restore:
                        self.logger.error(f"KHÔNG THỂ KHÔI PHỤC file gốc từ backup '{backup_file_path.name}': {e_restore}. Hệ thống có thể ở trạng thái không ổn định.", exc_info=True)
                self.error_signal.emit(f"Lỗi khi ghi file cập nhật ({current_script_to_replace_path.name}):\n{e_io}")
                self.finished_signal.emit(False, f"Lỗi: Không thể ghi file cập nhật.")
            except Exception as e_write:
                self.logger.error(f"Lỗi không mong muốn khi ghi nội dung cập nhật vào {current_script_to_replace_path.name}: {e_write}", exc_info=True)
                if made_backup and backup_file_path.exists():
                    try:
                        if current_script_to_replace_path.exists(): current_script_to_replace_path.unlink()
                        shutil.move(str(backup_file_path), str(current_script_to_replace_path))
                        self.logger.info(f"Đã khôi phục từ backup do lỗi ghi không xác định.")
                    except Exception as e_restore_unknown: self.logger.error(f"Lỗi khôi phục backup (unknown write error): {e_restore_unknown}")
                self.error_signal.emit(f"Lỗi không xác định khi ghi file cập nhật ({current_script_to_replace_path.name}):\n{e_write}")
                self.finished_signal.emit(False, f"Lỗi: Không xác định khi ghi file cập nhật.")
        except Exception as e:
            self.logger.error(f"Lỗi nghiêm trọng trong PerformUpdateWorker: {e}", exc_info=True)
            self.error_signal.emit(f"Lỗi không mong muốn trong quá trình cập nhật: {type(e).__name__}")
            self.finished_signal.emit(False, f"Lỗi: Không mong muốn trong quá trình cập nhật.")
