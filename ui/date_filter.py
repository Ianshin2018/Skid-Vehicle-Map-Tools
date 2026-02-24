"""
日期篩選模組
提供日期選擇 UI 和相關功能
"""
import logging
import tkinter as tk
from tkinter import ttk
from datetime import datetime


class DateFilter:
    """
    日期篩選類別
    負責處理日期選擇 UI 和相關功能
    """
    def __init__(self, ui_instance):
        """初始化日期篩選器
        
        Args:
            ui_instance: UI 物件實例
        """
        self.ui = ui_instance
        # 週次對應日期的映射
        self._week_to_dates = {}
        
    def create_date_panel(self, parent):
        """建立日期選擇面板
        
        Args:
            parent: 父框架
        """
        # 左側面板：日期選擇控件
        date_label = ttk.Label(parent, text="選擇日期:")
        date_label.pack(pady=(5, 2), padx=5, anchor="w")

        # 創建一個可滾動的框架來容納 checkbox
        self.ui.date_canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0, width=150)
        date_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.ui.date_canvas.yview)
        self.ui.date_checkbox_frame = ttk.Frame(self.ui.date_canvas)

        # 將內部框架嵌入到 canvas 中
        self.ui.date_canvas_window = self.ui.date_canvas.create_window((0, 0), window=self.ui.date_checkbox_frame, anchor="nw")

        # 配置滾動
        self.ui.date_canvas.configure(yscrollcommand=date_scrollbar.set)

        # 佈局
        self.ui.date_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
        date_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # 綁定框架大小變化事件
        self.ui.date_checkbox_frame.bind("<Configure>", self._on_date_frame_configure)
        self.ui.date_canvas.bind("<Configure>", self._on_date_canvas_configure)

        # 綁定滑鼠滾輪事件
        self.ui.date_canvas.bind("<MouseWheel>", self._on_date_list_mousewheel)
        self.ui.date_canvas.bind("<Button-4>", self._on_date_list_mousewheel)
        self.ui.date_canvas.bind("<Button-5>", self._on_date_list_mousewheel)

        # 儲存 checkbox 變數的字典
        self.ui.date_checkboxes = {}

        # 按鈕框架
        date_btn_frame = ttk.Frame(parent)
        date_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        # 全選按鈕
        self.ui._date_select_all_btn = ttk.Button(date_btn_frame, text="全選", width=5,
                                               state=tk.DISABLED, command=self.select_all_dates)
        self.ui._date_select_all_btn.pack(side=tk.LEFT, padx=1)

        # 清除選擇按鈕
        self.ui._date_clear_btn = ttk.Button(date_btn_frame, text="清除", width=5,
                                          state=tk.DISABLED, command=self.clear_date_selection)
        self.ui._date_clear_btn.pack(side=tk.LEFT, padx=1)


    def populate_date_list(self):
        """填充日期列表（根據當前選擇的樓層過濾）"""
        try:
            # 清除現有的所有 checkbox
            for widget in self.ui.date_checkbox_frame.winfo_children():
                widget.destroy()
            self.ui.date_checkboxes.clear()

            if not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
                no_data_label = ttk.Label(self.ui.date_checkbox_frame, text="(無資料)")
                no_data_label.pack(pady=5, padx=5, anchor="w")
                return

            # 根據當前樓層過濾資料
            df = self.ui.highlight_log_df.copy()

            # 如果有當前樓層，則過濾對應的 number 範圍
            if hasattr(self.ui, '_current_floor') and self.ui._current_floor:
                def to_int_safe(s):
                    try:
                        return int(str(s).strip())
                    except Exception:
                        return None

                df["_num"] = df["number"].apply(to_int_safe)

                # 根據樓層定義 number 範圍
                want_nums = set()
                if self.ui._current_floor == "1F":
                    want_nums.update(range(101, 116))
                elif self.ui._current_floor == "2F":
                    want_nums.update(range(116, 138))
                    want_nums.add(140)
                elif self.ui._current_floor == "3F":
                    want_nums.update([138, 139])

                # 過濾符合樓層的記錄
                if want_nums:
                    df = df[df["_num"].isin(want_nums)]
                    logging.info(f"樓層 {self.ui._current_floor} 過濾後剩餘 {len(df)} 筆記錄")

            # 獲取唯一日期並排序
            dates = df['start_date'].unique()
            dates = sorted([d for d in dates if d and d.strip()])

            if not dates:
                floor_info = f" ({self.ui._current_floor})" if hasattr(self.ui, '_current_floor') and self.ui._current_floor else ""
                no_data_label = ttk.Label(self.ui.date_checkbox_frame, text=f"(無日期資料{floor_info})")
                no_data_label.pack(pady=5, padx=5, anchor="w")
                return

            # 以週為單位分組
            week_groups = {}
            for d in dates:
                try:
                    dt = datetime.strptime(d.strip(), "%Y/%m/%d")
                except ValueError:
                    try:
                        dt = datetime.strptime(d.strip(), "%Y-%m-%d")
                    except ValueError:
                        continue
                iso = dt.isocalendar()
                key = (iso[0], iso[1])
                week_groups.setdefault(key, []).append(d)

            # 依週序排列
            def _fmt(ds):
                try:
                    dt = datetime.strptime(ds.strip(), "%Y/%m/%d")
                    return f"{dt.month}/{dt.day}"
                except Exception:
                    return ds.strip()

            self._week_to_dates = {}
            for key in sorted(week_groups.keys()):
                group = week_groups[key]
                first, last = _fmt(group[0]), _fmt(group[-1])
                label = f"W{key[1]:02d}  {first}~{last}" if first != last else f"W{key[1]:02d}  {first}"
                self._week_to_dates[label] = week_groups[key]
                var = tk.IntVar(value=0)
                cb = ttk.Checkbutton(
                    self.ui.date_checkbox_frame,
                    text=label,
                    variable=var,
                    command=self._on_date_checkbox_changed
                )
                cb.pack(anchor="w", padx=1, pady=0)
                self.ui.date_checkboxes[label] = var

            floor_info = f"樓層 {self.ui._current_floor} " if hasattr(self.ui, '_current_floor') and self.ui._current_floor else ""
            logging.info(f"已載入 {floor_info}{len(self._week_to_dates)} 週（共 {len(dates)} 個日期）")

        except Exception as e:
            logging.error(f"填充日期列表失敗: {e}")

    def get_selected_dates(self):
        """回傳目前勾選週次所對應的所有日期字串列表"""
        if not hasattr(self.ui, 'date_checkboxes'):
            return []
        result = []
        for label, var in self.ui.date_checkboxes.items():
            if var.get() == 1:
                result.extend(self._week_to_dates.get(label, [label]))
        return result

    def select_all_dates(self):
        """全選所有日期"""
        for var in self.ui.date_checkboxes.values():
            var.set(1)
        self.reload_highlights()

    def clear_date_selection(self):
        """清除日期選擇"""
        for var in self.ui.date_checkboxes.values():
            var.set(0)
        self.reload_highlights()

    def reload_highlights(self):
        """觸發重新載入打滑方框"""
        if hasattr(self.ui, '_reload_highlights'):
            self.ui._reload_highlights()

    def _on_date_checkbox_changed(self):
        """當用戶變更 checkbox 時的處理"""
        try:
            selected_dates = self.get_selected_dates()

            if not selected_dates:
                logging.info("未選擇任何日期")
            else:
                logging.info(f"已選擇日期: {selected_dates}")

            # 自動重新繪製地圖
            self.reload_highlights()

        except Exception as e:
            logging.error(f"日期選擇處理失敗: {e}")

    def _on_date_frame_configure(self, event):
        """當日期框架內容變化時更新滾動區域"""
        self.ui.date_canvas.configure(scrollregion=self.ui.date_canvas.bbox("all"))

    def _on_date_canvas_configure(self, event):
        """當 canvas 大小變化時調整內部框架寬度"""
        canvas_width = event.width
        self.ui.date_canvas.itemconfig(self.ui.date_canvas_window, width=canvas_width)

    def _on_date_list_mousewheel(self, event):
        """處理日期列表的滑鼠滾輪事件"""
        if hasattr(event, 'delta') and event.delta:
            self.ui.date_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif hasattr(event, 'num'):
            if event.num == 4:
                self.ui.date_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.ui.date_canvas.yview_scroll(1, "units")

    def enable_buttons(self):
        """啟用日期篩選按鈕"""
        for btn_attr in ('_date_select_all_btn', '_date_clear_btn'):
            btn = getattr(self.ui, btn_attr, None)
            if btn:
                btn.config(state=tk.NORMAL)

