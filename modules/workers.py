# -*- coding: utf-8 -*-
# Module: modules/workers.py
# Contains: ServerStatusCheckWorker, SignallingLogHandler

import logging
import sys

try:
    from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
except ImportError:
    pass

class ServerStatusCheckWorker(QObject):
    status_updated_signal = pyqtSignal(str, bool)
    finished_checking_signal = pyqtSignal()

    def __init__(self, main_app_ref):
        super().__init__()
        self.main_app = main_app_ref
        self.logger = logging.getLogger("ServerStatusWorker")

    @pyqtSlot()
    def run_check(self):
        self.logger.info("Bắt đầu kiểm tra trạng thái server (trong Worker)...")


        data_sync_url_from_config = self.main_app.config.get('DATA', 'sync_url', fallback="https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/data/xsmb-2-digits.json")
        data_sync_url = data_sync_url_from_config

        if hasattr(self.main_app, 'config_sync_url_edit') and self.main_app.config_sync_url_edit.text().strip():
            data_sync_url = self.main_app.config_sync_url_edit.text().strip()
            self.logger.debug(f"Sử dụng Data Sync URL từ tab Cài đặt: {data_sync_url}")
        elif hasattr(self.main_app, 'sync_url_input') and self.main_app.sync_url_input.text().strip():
            data_sync_url = self.main_app.sync_url_input.text().strip()
            self.logger.debug(f"Sử dụng Data Sync URL từ tab Main: {data_sync_url}")
        else:
            self.logger.debug(f"Sử dụng Data Sync URL từ file config/mặc định: {data_sync_url}")


        update_url_default = "https://raw.githubusercontent.com/junlangzi/Lottery-Predictor/refs/heads/main/main.py"
        update_url = update_url_default

        if hasattr(self.main_app, 'update_file_url_edit') and self.main_app.update_file_url_edit.text().strip():
            update_url = self.main_app.update_file_url_edit.text().strip()
            self.logger.debug(f"Sử dụng Update URL từ tab Update: {update_url}")
        else:
            self.logger.debug(f"Sử dụng Update URL mặc định: {update_url}")


        if data_sync_url != self.main_app._last_data_sync_url_checked or self.main_app._data_sync_server_online is None:
            self.logger.info(f"Kiểm tra Data Sync URL: {data_sync_url}")
            is_online = self.main_app._check_url_connectivity(data_sync_url)
            self.main_app._data_sync_server_online = is_online
            self.main_app._last_data_sync_url_checked = data_sync_url
            self.status_updated_signal.emit("Data Sync", is_online)
        else:
            self.logger.debug(f"Data Sync URL không đổi ({data_sync_url}), sử dụng trạng thái đã biết: {self.main_app._data_sync_server_online}")
            self.status_updated_signal.emit("Data Sync", self.main_app._data_sync_server_online if self.main_app._data_sync_server_online is not None else False)


        if update_url != self.main_app._last_update_url_checked or self.main_app._update_server_online is None:
            self.logger.info(f"Kiểm tra Update URL: {update_url}")
            is_online = self.main_app._check_url_connectivity(update_url)
            self.main_app._update_server_online = is_online
            self.main_app._last_update_url_checked = update_url
            self.status_updated_signal.emit("Update", is_online)
        else:
            self.logger.debug(f"Update URL không đổi ({update_url}), sử dụng trạng thái đã biết: {self.main_app._update_server_online}")
            self.status_updated_signal.emit("Update", self.main_app._update_server_online if self.main_app._update_server_online is not None else False)


        self.logger.info("Kiểm tra trạng thái server (trong Worker) hoàn tất.")
        self.finished_checking_signal.emit()


class SignallingLogHandler(logging.Handler, QObject):
    log_updated = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self._instance_closed = False

    def emit(self, record):
        if self._instance_closed:
            return
        try:
            msg = self.format(record)
            if self.parent() is not None and not self.signalsBlocked():
                 self.log_updated.emit(msg)
            elif self.parent() is None and not self.signalsBlocked():
                 self.log_updated.emit(msg)

        except RuntimeError as e:
            if "deleted" in str(e).lower() or "wrapped C/C++ object" in str(e).lower():
                self._instance_closed = True
                self._remove_from_logging_system()
            else:
                try:
                    self.handleError(record)
                except Exception:
                    pass
        except Exception:
            try:
                self.handleError(record)
            except Exception:
                pass

    def flush(self):
        if self._instance_closed:
            return
        super(SignallingLogHandler, self).flush()

    def close(self):
        if self._instance_closed:
            return
        self._instance_closed = True
        self._remove_from_logging_system()
        super(SignallingLogHandler, self).close()

    def _remove_from_logging_system(self):
        if not hasattr(logging, '_handlerList') or not hasattr(logging, '_acquireLock') or not hasattr(logging, '_releaseLock'):
            return
        logging._acquireLock()
        try:
            handler_found = False
            for i, h in enumerate(logging._handlerList):
                if h is self:
                    logging._handlerList.pop(i)
                    handler_found = True
                    break
        except RuntimeError:
            pass
        except Exception:
            pass
        finally:
            logging._releaseLock()
