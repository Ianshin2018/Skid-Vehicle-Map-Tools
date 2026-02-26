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
        # 子日期 checkbox 變數  week_label → {date_str → IntVar}
        self._date_child_vars = {}
        # 展開狀態  week_label → bool
        self._week_expand_states = {}
        # (week_row_frame, children_frame)
        self._week_frames = {}
        # 展開符號 label  week_label → tk.Label
        self._expand_labels = {}

    def create_date_panel(self, parent):
        """建立日期選擇面板

        Args:
            parent: 父框架
        """
        date_label = ttk.Label(parent, text="選擇日期:")
        date_label.pack(pady=(5, 2), padx=5, anchor="w")

        # 創建一個可滾動的框架來容納 checkbox
        self.ui.date_canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0, width=150)
        date_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.ui.date_canvas.yview)
        self.ui.date_checkbox_frame = ttk.Frame(self.ui.date_canvas)

        # 將內部框架嵌入到 canvas 中
        self.ui.date_canvas_window = self.ui.date_canvas.create_window(
            (0, 0), window=self.ui.date_checkbox_frame, anchor="nw"
        )

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
        self.ui._date_select_all_btn = ttk.Button(
            date_btn_frame, text="全選", width=5,
            state=tk.DISABLED, command=self.select_all_dates
        )
        self.ui._date_select_all_btn.pack(side=tk.LEFT, padx=1)

        # 清除選擇按鈕
        self.ui._date_clear_btn = ttk.Button(
            date_btn_frame, text="清除", width=5,
            state=tk.DISABLED, command=self.clear_date_selection
        )
        self.ui._date_clear_btn.pack(side=tk.LEFT, padx=1)

    def populate_date_list(self):
        """填充日期列表（根據當前選擇的樓層過濾）"""
        try:
            # 清除現有的所有 widget 和狀態
            for widget in self.ui.date_checkbox_frame.winfo_children():
                widget.destroy()
            self.ui.date_checkboxes.clear()
            self._date_child_vars.clear()
            self._week_expand_states.clear()
            self._week_frames.clear()
            self._expand_labels.clear()

            if not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
                ttk.Label(self.ui.date_checkbox_frame, text="(無資料)").pack(
                    pady=5, padx=5, anchor="w"
                )
                return

            # 根據當前樓層過濾資料
            df = self.ui.highlight_log_df.copy()

            if hasattr(self.ui, '_current_floor') and self.ui._current_floor:
                def to_int_safe(s):
                    try:
                        return int(str(s).strip())
                    except Exception:
                        return None

                df["_num"] = df["number"].apply(to_int_safe)

                want_nums = set()
                if self.ui._current_floor == "1F":
                    want_nums.update(range(101, 116))
                elif self.ui._current_floor == "2F":
                    want_nums.update(range(116, 138))
                    want_nums.add(140)
                elif self.ui._current_floor == "3F":
                    want_nums.update([138, 139])

                if want_nums:
                    df = df[df["_num"].isin(want_nums)]
                    logging.info(f"樓層 {self.ui._current_floor} 過濾後剩餘 {len(df)} 筆記錄")

            # 獲取唯一日期並排序
            dates = df['start_date'].unique()
            dates = sorted([d for d in dates if d and d.strip()])

            if not dates:
                floor_info = (
                    f" ({self.ui._current_floor})"
                    if hasattr(self.ui, '_current_floor') and self.ui._current_floor
                    else ""
                )
                ttk.Label(
                    self.ui.date_checkbox_frame, text=f"(無日期資料{floor_info})"
                ).pack(pady=5, padx=5, anchor="w")
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

            def _fmt_short(ds):
                """週標籤用短格式：月/日"""
                try:
                    dt = datetime.strptime(ds.strip(), "%Y/%m/%d")
                    return f"{dt.month}/{dt.day}"
                except Exception:
                    return ds.strip()

            def _fmt_child(ds):
                """子節點日期格式：月/日 (週X)"""
                weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
                for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(ds.strip(), fmt)
                        wd = weekday_names[dt.weekday()]
                        return f"{dt.month}/{dt.day} (週{wd})"
                    except ValueError:
                        continue
                return ds.strip()

            self._week_to_dates = {}
            for key in sorted(week_groups.keys()):
                group = week_groups[key]
                first, last = _fmt_short(group[0]), _fmt_short(group[-1])
                week_label = (
                    f"W{key[1]:02d}  {first}~{last}"
                    if first != last
                    else f"W{key[1]:02d}  {first}"
                )
                self._week_to_dates[week_label] = group

                # --- 週次列 ---
                week_row = ttk.Frame(self.ui.date_checkbox_frame)
                week_row.pack(anchor="w", fill=tk.X, padx=0, pady=0)

                # 展開符號
                expand_lbl = tk.Label(
                    week_row, text="+", width=2, cursor="hand2",
                    font=("", 9, "bold"), fg="#555555"
                )
                expand_lbl.pack(side=tk.LEFT, padx=(2, 0))

                # 週次 checkbox
                week_var = tk.IntVar(value=0)
                cb = ttk.Checkbutton(
                    week_row,
                    text=week_label,
                    variable=week_var,
                    command=lambda lbl=week_label: self._on_week_check(lbl),
                )
                cb.pack(side=tk.LEFT, padx=(0, 2))

                # --- 子日期列 (預設隱藏) ---
                children_frame = ttk.Frame(self.ui.date_checkbox_frame)
                # 不 pack，保持隱藏

                date_vars = {}
                for d in group:
                    dvar = tk.IntVar(value=0)
                    date_cb = ttk.Checkbutton(
                        children_frame,
                        text=_fmt_child(d),
                        variable=dvar,
                        command=lambda lbl=week_label: self._on_date_check(lbl),
                    )
                    date_cb.pack(anchor="w", padx=(24, 0), pady=0)
                    date_vars[d] = dvar

                # 儲存參照
                self._date_child_vars[week_label] = date_vars
                self._week_expand_states[week_label] = False
                self._week_frames[week_label] = (week_row, children_frame)
                self._expand_labels[week_label] = expand_lbl
                self.ui.date_checkboxes[week_label] = week_var

                # 綁定展開符號點擊
                expand_lbl.bind(
                    "<Button-1>",
                    lambda _, lbl=week_label: self._toggle_expand(lbl)
                )

            floor_info = (
                f"樓層 {self.ui._current_floor} "
                if hasattr(self.ui, '_current_floor') and self.ui._current_floor
                else ""
            )
            logging.info(
                f"已載入 {floor_info}{len(self._week_to_dates)} 週（共 {len(dates)} 個日期）"
            )

        except Exception as e:
            logging.error(f"填充日期列表失敗: {e}")

    # ------------------------------------------------------------------
    # 展開 / 收合
    # ------------------------------------------------------------------

    def _toggle_expand(self, week_label):
        """切換週次展開/收合狀態"""
        expanded = self._week_expand_states.get(week_label, False)
        week_row, children_frame = self._week_frames[week_label]
        expand_lbl = self._expand_labels[week_label]

        if expanded:
            children_frame.pack_forget()
            expand_lbl.config(text="+")
            self._week_expand_states[week_label] = False
        else:
            children_frame.pack(anchor="w", fill=tk.X, after=week_row)
            expand_lbl.config(text="-")
            self._week_expand_states[week_label] = True

    # ------------------------------------------------------------------
    # Checkbox 聯動
    # ------------------------------------------------------------------

    def _on_week_check(self, week_label):
        """週次 checkbox 被點擊時：同步所有子日期的勾選狀態"""
        val = self.ui.date_checkboxes[week_label].get()
        for dvar in self._date_child_vars.get(week_label, {}).values():
            dvar.set(val)
        self._on_date_checkbox_changed()

    def _on_date_check(self, week_label):
        """子日期 checkbox 被點擊時：更新父週次 checkbox 狀態"""
        child_vals = [
            dvar.get()
            for dvar in self._date_child_vars.get(week_label, {}).values()
        ]
        # 全選 → 週次勾選；其餘（部分或全不選）→ 週次取消
        if all(v == 1 for v in child_vals):
            self.ui.date_checkboxes[week_label].set(1)
        else:
            self.ui.date_checkboxes[week_label].set(0)
        self._on_date_checkbox_changed()

    # ------------------------------------------------------------------
    # 日期查詢 / 全選 / 清除
    # ------------------------------------------------------------------

    def get_selected_dates(self):
        """回傳目前勾選的所有日期字串列表"""
        if not hasattr(self.ui, 'date_checkboxes'):
            return []
        result = []
        for label in self.ui.date_checkboxes:
            child_vars = self._date_child_vars.get(label, {})
            if child_vars:
                for d, dvar in child_vars.items():
                    if dvar.get() == 1:
                        result.append(d)
            else:
                # 回退：無子節點時以週次 checkbox 決定
                if self.ui.date_checkboxes[label].get() == 1:
                    result.extend(self._week_to_dates.get(label, [label]))
        return result

    def select_all_dates(self):
        """全選所有日期"""
        for label, var in self.ui.date_checkboxes.items():
            var.set(1)
            for dvar in self._date_child_vars.get(label, {}).values():
                dvar.set(1)
        self.reload_highlights()

    def clear_date_selection(self):
        """清除日期選擇"""
        for label, var in self.ui.date_checkboxes.items():
            var.set(0)
            for dvar in self._date_child_vars.get(label, {}).values():
                dvar.set(0)
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
            self.reload_highlights()
        except Exception as e:
            logging.error(f"日期選擇處理失敗: {e}")

    # ------------------------------------------------------------------
    # Canvas 事件
    # ------------------------------------------------------------------

    def _on_date_frame_configure(self, _):
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
