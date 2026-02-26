"""
打滑資料處理模組
提供打滑門檻滑桿、排名更新等相關功能
"""
import logging
import tkinter as tk
from tkinter import ttk


class SkidHandler:
    """
    打滑資料處理類別
    負責處理打滑門檻滑桿、排名更新等功能
    """
    def __init__(self, ui_instance):
        """初始化打滑處理器
        
        Args:
            ui_instance: UI 物件實例
        """
        self.ui = ui_instance
        self._skid_after_id = None
        
    def create_skid_slider(self, parent):
        """建立打滑門檻滑桿
        
        Args:
            parent: 父框架
        """
        # 打滑門檻滑桿
        self.ui._skid_slider_var = tk.IntVar(value=1)
        self.ui._skid_slider_frame = ttk.Frame(parent)
        
        self.ui._skid_slider = tk.Scale(
            self.ui._skid_slider_frame,
            from_=1, to=1,
            orient=tk.HORIZONTAL,
            variable=self.ui._skid_slider_var,
            label="重複打滑門檻 (address/section 重複率≥)",
            showvalue=True,
            command=self._on_skid_slider_changed,
            bg="#FFFDE7",
            relief=tk.GROOVE,
            font=("", 8),
        )
        self.ui._skid_slider.pack(fill=tk.X, expand=True)
        
    def reset_skid_slider(self):
        """重置打滑門檻滑桿至初始狀態"""
        if not hasattr(self.ui, '_skid_slider'):
            return
        self.ui._skid_addr_counts = {}
        self.ui._skid_sec_counts = {}
        self.ui._skid_median = 1
        self.ui._skid_max_count = 1
        self.ui._skid_slider.config(
            from_=0, to=100,
            state=tk.DISABLED,
            label="重複打滑門檻 (address/section 重複率≥)"
        )
        self.ui._skid_slider_var.set(50)
        self._set_rank_tree_clickable(False)

    def show_skid_slider(self):
        """顯示打滑門檻滑桿"""
        if hasattr(self.ui, '_skid_slider_frame') and not self.ui._skid_slider_frame.winfo_ismapped():
            self.ui._skid_slider_frame.pack(fill=tk.X, padx=5, pady=(0, 2),
                                         before=self.ui._map_options_frame)

    def slider_pos_to_threshold(self, pos):
        """將滑桿位置 (0-100) 轉換為重複次數門檻。
        0 → 1（顯示全部），50 → 中位數，100 → 最大值。
        """
        median_c = getattr(self.ui, '_skid_median', 1)
        max_c = getattr(self.ui, '_skid_max_count', 1)
        if pos <= 50:
            # [0, 50] → [1, median_c]
            t = 1 + (median_c - 1) * (pos / 50.0)
        else:
            # [50, 100] → [median_c, max_c]
            t = median_c + (max_c - median_c) * ((pos - 50) / 50.0)
        return max(1, int(round(t)))

    def update_skid_slider_range(self, addr_counts, sec_counts):
        """根據 address+section 次數分佈設定滑桿"""
        if not hasattr(self.ui, '_skid_slider'):
            return
        all_counts = list(addr_counts.values()) + list(sec_counts.values())
        if not all_counts:
            self.ui._skid_slider.config(from_=0, to=100, state=tk.DISABLED)
            self.ui._skid_slider_var.set(50)
            self.ui._skid_median = 1
            self.ui._skid_max_count = 1
            return
        min_c = max(min(all_counts), 1)
        max_c = max(all_counts)
        mid_c = max((min_c + max_c) // 2, 1)
        self.ui._skid_median = mid_c
        self.ui._skid_max_count = max_c
        self.ui._skid_slider.config(from_=0, to=100, state=tk.NORMAL)
        self.ui._skid_slider_var.set(50)
        # 更新標籤顯示中間值門檻
        self.ui._skid_slider.config(label=f"重複打滑門檻 ≥{mid_c}次 (中間值:{mid_c} 最高:{max_c})")

    def _on_skid_slider_changed(self, value):
        """滑桿移動：立即更新標籤，debounce 後執行重繪"""
        try:
            threshold = self.slider_pos_to_threshold(int(float(value)))
            # 立即更新標籤
            if hasattr(self.ui, '_skid_slider'):
                median_c = getattr(self.ui, '_skid_median', 1)
                max_c = getattr(self.ui, '_skid_max_count', 1)
                self.ui._skid_slider.config(label=f"重複打滑門檻 ≥{threshold}次 (中間值:{median_c} 最高:{max_c})")
            # 取消上一次尚未執行的重繪任務
            if self._skid_after_id:
                self.ui.root.after_cancel(self._skid_after_id)
            # 150ms 後執行一次重繪
            self._skid_after_id = self.ui.root.after(150, lambda v=value: self.apply_skid_threshold(v))
        except Exception as e:
            logging.error(f"打滑滑桿移動失敗: {e}")

    def apply_skid_threshold(self, value):
        """依門檻重新生成 overlay 並更新排名"""
        try:
            threshold = self.slider_pos_to_threshold(int(float(value)))
            addr_counts = getattr(self.ui, '_skid_addr_counts', {})
            sec_counts = getattr(self.ui, '_skid_sec_counts', {})
            if not addr_counts and not sec_counts:
                return
            addr_ids = [aid for aid, cnt in addr_counts.items() if cnt >= threshold]
            sec_ids = [sid for sid, cnt in sec_counts.items() if cnt >= threshold]

            def cast_ids(lst):
                out = []
                for v in lst:
                    s = str(v).strip()
                    out.append(int(s) if s.isdigit() else s)
                return out

            if not hasattr(self.ui, 'vehicle_map_plotter'):
                return
            self.ui.vehicle_map_plotter.set_highlight_address_ids(cast_ids(addr_ids))
            self.ui.vehicle_map_plotter.set_highlight_section_ids(cast_ids(sec_ids))
            
            from PIL import Image
            if self.ui.vehicle_map_plotter.regenerate_overlay():
                self.ui._overlay_pil_img = self.ui.vehicle_map_plotter.get_overlay_image()
                result_img = None
                if hasattr(self.ui, '_base_pil_img') and self.ui._base_pil_img:
                    result_img = self.ui._base_pil_img.copy()
                    
                if result_img and hasattr(self.ui, '_zone_pil_img') and self.ui._zone_pil_img:
                    zone_img = self.ui._zone_pil_img
                    if zone_img.size != result_img.size:
                        zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
                    result_img = Image.alpha_composite(result_img, zone_img)
                if result_img and self.ui._overlay_pil_img:
                    overlay_img = self.ui._overlay_pil_img
                    if overlay_img.size != result_img.size:
                        overlay_img = overlay_img.resize(result_img.size, Image.LANCZOS)
                    result_img = Image.alpha_composite(result_img, overlay_img)
                self.ui._combined_pil_img = result_img
                
                show_highlight = getattr(self.ui, '_show_highlight_var', None)
                if show_highlight and show_highlight.get() == 1 and self.ui._combined_pil_img:
                    self.ui.show_image_on_canvas(self.ui._combined_pil_img)
                elif hasattr(self.ui, '_base_pil_img') and self.ui._base_pil_img:
                    self.ui.show_image_on_canvas(self.ui._base_pil_img)
            
            # 同步更新右側車輛排名
            selected_dates = self.get_selected_dates()
            self.update_skid_ranking(
                floor_label=getattr(self.ui, '_current_floor', None),
                selected_dates=selected_dates,
                addr_ids=addr_ids,
                sec_ids=sec_ids,
            )
        except Exception as e:
            logging.error(f"打滑滑桿套用門檻失敗: {e}")

    def get_selected_dates(self):
        """取得選擇的日期"""
        if hasattr(self.ui, '_get_selected_dates'):
            return self.ui._get_selected_dates()
        return []

    def update_skid_ranking(self, floor_label=None, selected_dates=None, addr_ids=None, sec_ids=None):
        """根據 highlight_log_df 更新右側面板指定樓層的打滑次數排名"""
        if not hasattr(self.ui, 'skid_rank_tree'):
            return

        # 清除現有資料
        for item in self.ui.skid_rank_tree.get_children():
            self.ui.skid_rank_tree.delete(item)

        if not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
            return

        # 更新樓層標籤
        if hasattr(self.ui, '_skid_floor_label') and floor_label:
            self.ui._skid_floor_label.config(text=f"{floor_label} 車輛打滑次數")

        _floor_check = {
            "1F": lambda n: 101 <= n <= 115,
            "2F": lambda n: (116 <= n <= 137) or n == 140,
            "3F": lambda n: n in (138, 139),
        }

        try:
            df = self.ui.highlight_log_df.copy()
            df['number'] = df['number'].astype(str).str.strip()
            df = df[df['number'].str.len() > 0]

            # 樓層過濾
            if floor_label and floor_label in _floor_check:
                check = _floor_check[floor_label]
                def _match(s):
                    try:
                        return check(int(s))
                    except Exception:
                        return False
                df = df[df['number'].apply(_match)]

            # 日期過濾
            if selected_dates is not None:
                df = df[df['start_date'].isin(selected_dates)]

            # 依滑桿門檻過濾
            if addr_ids is not None or sec_ids is not None:
                addr_set = set(str(a).strip() for a in (addr_ids or []))
                sec_set = set(str(s).strip() for s in (sec_ids or []))
                mask = (
                    df['addressid'].astype(str).str.strip().isin(addr_set) |
                    df['sectionid'].astype(str).str.strip().isin(sec_set)
                )
                df = df[mask]

            counts = df.groupby('number').size().reset_index(name='count')
            counts = counts.sort_values('count', ascending=False).reset_index(drop=True)
            for i, row in counts.iterrows():
                self.ui.skid_rank_tree.insert("", "end", values=(i + 1, row['number'], row['count']))
        except Exception as e:
            logging.error(f"更新打滑次數排名失敗: {e}")

    def reload_highlights(self, selected_dates):
        """根據選擇的日期重新載入打滑方框並重繪地圖"""
        try:
            # 依日期是否選擇，更新排名表格可點擊狀態
            self._set_rank_tree_clickable(bool(selected_dates))

            # 更新狀態
            if selected_dates:
                status_msg = f"更新打滑方框 ({len(selected_dates)} 個日期)..."
            else:
                status_msg = "清除打滑方框..."
                
            if hasattr(self.ui, '_update_status'):
                self.ui._update_status(status_msg)

            # 計算 address 和 section 次數分佈（依目前樓層過濾）
            current_floor = getattr(self.ui, '_current_floor', None)
            addr_counts, sec_counts = self.calc_highlight_counts(selected_dates, floor_label=current_floor)
            self.ui._skid_addr_counts = addr_counts
            self.ui._skid_sec_counts = sec_counts
            self.update_skid_slider_range(addr_counts, sec_counts)

            # 依目前滑桿門檻過濾
            pos = self.ui._skid_slider_var.get() if hasattr(self.ui, '_skid_slider_var') else 50
            threshold = self.slider_pos_to_threshold(pos)
            addr_ids = [aid for aid, cnt in addr_counts.items() if cnt >= threshold]
            sec_ids = [sid for sid, cnt in sec_counts.items() if cnt >= threshold]

            def cast_ids(lst):
                out = []
                for v in lst:
                    if isinstance(v, str):
                        s = v.strip()
                        if s.isdigit():
                            out.append(int(s))
                        else:
                            out.append(s)
                    else:
                        out.append(v)
                return out

            # 設定新的打滑方框 ID
            if hasattr(self.ui, 'vehicle_map_plotter'):
                self.ui.vehicle_map_plotter.set_highlight_address_ids(cast_ids(addr_ids))
                self.ui.vehicle_map_plotter.set_highlight_section_ids(cast_ids(sec_ids))

                # 只重新生成 overlay 圖層
                if self.ui.vehicle_map_plotter.regenerate_overlay():
                    self.ui._overlay_pil_img = self.ui.vehicle_map_plotter.get_overlay_image()

                    # 重新合成圖層
                    from PIL import Image
                    result_img = None
                    if self.ui._base_pil_img:
                        result_img = self.ui._base_pil_img.copy()
                        
                    if result_img and hasattr(self.ui, '_zone_pil_img') and self.ui._zone_pil_img:
                        zone_img = self.ui._zone_pil_img
                        if zone_img.size != result_img.size:
                            zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
                        result_img = Image.alpha_composite(result_img, zone_img)
                    
                    if result_img and self.ui._overlay_pil_img:
                        overlay_img = self.ui._overlay_pil_img
                        if overlay_img.size != result_img.size:
                            overlay_img = overlay_img.resize(result_img.size, Image.LANCZOS)
                        result_img = Image.alpha_composite(result_img, overlay_img)
                    
                    self.ui._combined_pil_img = result_img

                    # 根據 checkbutton 狀態顯示圖像
                    show_highlight = getattr(self.ui, '_show_highlight_var', None)
                    if show_highlight and show_highlight.get() == 1 and self.ui._combined_pil_img:
                        self.ui.show_image_on_canvas(self.ui._combined_pil_img)
                    elif self.ui._base_pil_img:
                        self.ui.show_image_on_canvas(self.ui._base_pil_img)

                    # 更新快取
                    if hasattr(self.ui, '_floor_cache') and hasattr(self.ui, '_current_floor') and self.ui._current_floor in self.ui._floor_cache:
                        self.ui._floor_cache[self.ui._current_floor]['overlay_img'] = self.ui._overlay_pil_img
                        self.ui._floor_cache[self.ui._current_floor]['combined_img'] = self.ui._combined_pil_img

                    # 更新狀態
                    floor_info = ""
                    if hasattr(self.ui, '_current_floor') and self.ui._current_floor:
                        floor_info = f" - {self.ui._current_floor}"
                    if hasattr(self.ui, '_update_status'):
                        self.ui._update_status(f"就緒{floor_info} ({len(addr_ids)} addresses, {len(sec_ids)} sections)")
                    logging.info(f"已更新打滑方框（{len(addr_ids)} addresses, {len(sec_ids)} sections）")
                else:
                    # 重新生成失敗，回退到完整重繪
                    logging.warning("重新生成 overlay 失敗，執行完整重繪")
                    if hasattr(self.ui, 'data_folder') and self.ui.data_folder:
                        self.ui.plot_vehicle_map()

            # 同步更新右側車輛排名
            self.update_skid_ranking(
                floor_label=getattr(self.ui, '_current_floor', None),
                selected_dates=selected_dates,
                addr_ids=addr_ids,
                sec_ids=sec_ids,
            )

        except Exception as e:
            logging.error(f"重新載入打滑方框失敗: {e}")

    def calc_highlight_counts(self, selected_dates, floor_label=None):
        """計算各 addressid 和 sectionid 在選定日期中的出現次數

        Args:
            selected_dates: 選定的日期列表
            floor_label: 樓層標籤（'1F'/'2F'/'3F'），若指定則只計算該樓層車輛的資料
        """
        from collections import Counter
        if not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
            return {}, {}
        if not selected_dates:
            return {}, {}
        df = self.ui.highlight_log_df
        df = df[df['start_date'].isin(selected_dates)]

        # 依樓層過濾（依車號判斷）
        _floor_check = {
            "1F": lambda n: 101 <= n <= 115,
            "2F": lambda n: (116 <= n <= 137) or n == 140,
            "3F": lambda n: n in (138, 139),
        }
        if floor_label and floor_label in _floor_check:
            check = _floor_check[floor_label]
            def _match(s):
                try:
                    return check(int(str(s).strip()))
                except Exception:
                    return False
            df = df[df['number'].apply(_match)]

        addrs = df['addressid'].astype(str).str.strip()
        addrs = addrs[(addrs != '') & (addrs != 'nan')]
        addr_counts = dict(Counter(addrs))
        secs = df['sectionid'].astype(str).str.strip()
        secs = secs[(secs != '') & (secs != 'nan')]
        sec_counts = dict(Counter(secs))
        return addr_counts, sec_counts

    def _set_rank_tree_clickable(self, enabled):
        """切換排名表格是否可點擊（透過 cursor 視覺提示與 selectmode）"""
        if not hasattr(self.ui, 'skid_rank_tree'):
            return
        if enabled:
            self.ui.skid_rank_tree.config(cursor="hand2", selectmode="browse")
        else:
            self.ui.skid_rank_tree.config(cursor="", selectmode="none")

    def on_show_vehicle_skid_changed(self):
        """顯示車輛打滑位置 checkbox 切換時的處理"""
        enabled = getattr(self.ui, '_show_vehicle_skid_var', None)
        if enabled and enabled.get() == 0:
            # 取消勾選 → 清除畫布上的高亮
            self.ui._image_processor._clear_vehicle_highlights()

    def on_vehicle_rank_click(self, event):
        """點擊右側車輛排名列時，在畫布上高亮該車輛的打滑方框"""
        try:
            # 未勾選「顯示車輛打滑位置」時不作動
            show_var = getattr(self.ui, '_show_vehicle_skid_var', None)
            if not show_var or show_var.get() == 0:
                return

            tree = self.ui.skid_rank_tree
            item = tree.identify_row(event.y)
            if not item:
                return
            values = tree.item(item, 'values')
            if not values or len(values) < 2:
                return
            vehicle_number = str(values[1]).strip()

            if not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
                return

            df = self.ui.highlight_log_df.copy()
            df['number'] = df['number'].astype(str).str.strip()

            selected_dates = self.get_selected_dates()
            if not selected_dates:
                return

            df = df[df['start_date'].isin(selected_dates)]
            df = df[df['number'] == vehicle_number]

            addr_ids = set(df['addressid'].astype(str).str.strip())
            addr_ids.discard('')
            addr_ids.discard('nan')

            sec_ids = set(df['sectionid'].astype(str).str.strip())
            sec_ids.discard('')
            sec_ids.discard('nan')

            self.ui._image_processor.highlight_vehicle_boxes(vehicle_number, addr_ids, sec_ids)
        except Exception as e:
            logging.error(f"點擊車輛排名失敗: {e}")

    def get_highlights_by_dates(self, selected_dates):
        """根據選擇的日期獲取打滑方框的 address 和 section IDs"""
        addr_ids = []
        sec_ids = []

        if not selected_dates or not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
            return addr_ids, sec_ids

        try:
            filtered_df = self.ui.highlight_log_df[self.ui.highlight_log_df['start_date'].isin(selected_dates)]

            for _, row in filtered_df.iterrows():
                addr = row.get("addressid", "")
                sec = row.get("sectionid", "")

                if isinstance(addr, str) and addr.strip() != "":
                    try:
                        val = int(addr.strip()) if addr.strip().isdigit() else addr.strip()
                        addr_ids.append(val)
                    except Exception:
                        addr_ids.append(addr.strip())
                elif isinstance(sec, str) and sec.strip() != "":
                    try:
                        val = int(sec.strip()) if sec.strip().isdigit() else sec.strip()
                        sec_ids.append(val)
                    except Exception:
                        sec_ids.append(sec.strip())

            logging.info(f"根據 {len(selected_dates)} 個日期過濾出 {len(addr_ids)} addresses, {len(sec_ids)} sections")

        except Exception as e:
            logging.error(f"過濾日期資料失敗: {e}")

        return addr_ids, sec_ids

