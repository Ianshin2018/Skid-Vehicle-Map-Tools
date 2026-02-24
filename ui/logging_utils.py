"""
日誌處理工具模組
提供 UI 日誌處理的相關功能
"""
import logging


class UILogHandler(logging.Handler):
    """
    自訂 logging handler 用於將日誌訊息顯示在 UI 上
    """
    def __init__(self, ui_instance):
        """初始化 UI 日誌處理器
        
        Args:
            ui_instance: UI 物件實例，必須具有 add_error 和 add_warning 方法
        """
        super().__init__()
        self.ui_instance = ui_instance
        
    def emit(self, record):
        """處理日誌記錄
        
        Args:
            record: 日誌記錄物件
        """
        msg = self.format(record)
        if record.levelno >= logging.ERROR:
            # 使用執行緒安全的方法更新 UI
            self.ui_instance.root.after(0, lambda: self.ui_instance.add_error(msg))
        elif record.levelno >= logging.WARNING:
            # 使用執行緒安全的方法更新 UI
            self.ui_instance.root.after(0, lambda: self.ui_instance.add_warning(msg))

