"""
狀態訊息顯示模組
提供警報和異常訊息的顯示功能
"""
import tkinter as tk
from datetime import datetime


class StatusDisplay:
    """
    狀態訊息顯示類別
    處理警報和異常訊息的顯示
    """
    def __init__(self, ui_instance):
        """初始化狀態顯示
        
        Args:
            ui_instance: UI 物件實例，必須具有 root, warnings, errors 等屬性
                        以及 warning_text, error_text 等 UI 元件
        """
        self.ui = ui_instance
        # 初始化訊息列表
        if not hasattr(ui_instance, 'warnings'):
            ui_instance.warnings = []
        if not hasattr(ui_instance, 'errors'):
            ui_instance.errors = []
    
    def add_warning(self, message):
        """新增警報訊息

        Args:
            message (str): 警報訊息
        """
        if message:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.ui.warnings.append(f"[{timestamp}] {message}")
            self._update_warning_display()

    def add_error(self, message):
        """新增異常訊息

        Args:
            message (str): 異常訊息
        """
        if message:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.ui.errors.append(f"[{timestamp}] {message}")
            self._update_error_display()

    def _update_warning_display(self):
        """更新警報顯示區域"""
        if not hasattr(self.ui, 'warning_text'):
            return
        self.ui.warning_text.config(state=tk.NORMAL)
        self.ui.warning_text.delete(1.0, tk.END)
        if self.ui.warnings:
            self.ui.warning_text.insert(tk.END, "\n".join(self.ui.warnings))
        else:
            self.ui.warning_text.insert(tk.END, "目前沒有警報資訊")
        self.ui.warning_text.config(state=tk.DISABLED)
        self.ui.warning_text.see(tk.END)  # 自動捲動到最新訊息

    def _update_error_display(self):
        """更新異常顯示區域"""
        if not hasattr(self.ui, 'error_text'):
            return
        self.ui.error_text.config(state=tk.NORMAL)
        self.ui.error_text.delete(1.0, tk.END)
        if self.ui.errors:
            self.ui.error_text.insert(tk.END, "\n".join(self.ui.errors))
        else:
            self.ui.error_text.insert(tk.END, "目前沒有異常資訊")
        self.ui.error_text.config(state=tk.DISABLED)
        self.ui.error_text.see(tk.END)  # 自動捲動到最新訊息

    def clear_messages(self):
        """清除所有警報與異常訊息"""
        self.ui.warnings = []
        self.ui.errors = []
        self._update_warning_display()
        self._update_error_display()

