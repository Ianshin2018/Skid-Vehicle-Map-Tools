"""
預載管理模組
提供樓層資料的異步預載功能
"""
import logging
import threading
import time
import tkinter as tk
from mapplot.plotters.vehicle_map_plotter import VehicleMapPlotter
from mapplot.utils.file_utils import validate_data_folder, load_map_data, load_and_validate_map_data
from mapplot.utils.data_cache import get_data_cache


class PreloadManager:
    """
    預載管理類別
    負責處理樓層資料的異步預載功能
    """
    def __init__(self, ui_instance, data_root):
        """初始化預載管理器
        
        Args:
            ui_instance: UI 物件實例
            data_root: 資料根目錄
        """
        self.ui = ui_instance
        self.data_root = data_root
        
    def start_async_preload(self):
        """啟動後台線程異步加載所有樓層"""
        # 更新狀態
        self.update_status("開始預載樓層底圖...")
        self.ui.progress_bar['value'] = 0
        self.ui.progress_bar['maximum'] = 3

        # 在後台線程中執行預加載
        thread = threading.Thread(target=self._preload_floor_maps_async, daemon=True)
        thread.start()

    def update_status(self, message):
        """線程安全地更新狀態欄"""
        if hasattr(self.ui, 'status_label'):
            self.ui.root.after(0, lambda: self.ui.status_label.config(text=message))

    def update_progress(self, value):
        """線程安全地更新進度條"""
        if hasattr(self.ui, 'progress_bar'):
            self.ui.root.after(0, lambda: self.ui.progress_bar.config(value=value))

    def _preload_floor_maps_async(self):
        """在後台線程中預載所有樓層的底圖"""
        start_time = time.time()
        
        try:
            logging.info("開始預載所有樓層的底圖...")

            # 預先載入 highlight_log.csv
            self.ui._load_highlight_log(self.ui._project_root)

            # 定義三個樓層的資料夾路徑
            floor_configs = [
                ("1F", self.data_root.replace("data", "Map") + "/Garmin1F"),
                ("2F", self.data_root.replace("data", "Map") + "/Garmin2F"),
                ("3F", self.data_root.replace("data", "Map") + "/Garmin3F"),
            ]

            loaded_count = 0
            for floor_label, folder_path in floor_configs:
                self.update_status(f"正在載入 {floor_label} 底圖...")
                try:
                    # 驗證資料夾
                    is_valid, missing_files = validate_data_folder(folder_path)
                    if not is_valid:
                        logging.warning(f"樓層 {floor_label} 資料夾驗證失敗，跳過預載")
                        self.ui._floor_loading_status[floor_label] = 'failed'
                        loaded_count += 1
                        self.update_progress(loaded_count)
                        continue

                    # 嘗試從快取獲取數據
                    map_data = None
                    if hasattr(self.ui, '_data_cache') and self.ui._data_cache:
                        map_data = self.ui._data_cache.get_cached_data(folder_path)
                    
                    if map_data is None:
                        # 快取未命中，手動讀取 CSV
                        map_files = load_map_data(folder_path)
                        validation_result = load_and_validate_map_data(folder_path, strict=False, lightweight=True)
                        map_data = validation_result
                        
                        # 存入快取
                        if hasattr(self.ui, '_data_cache') and self.ui._data_cache:
                            self.ui._data_cache.load_csv_data(folder_path)
                            self.ui._data_cache.set_validation_result(folder_path, validation_result)
                    else:
                        # 快取命中
                        validation_result = map_data
                        map_files = load_map_data(folder_path)
                        logging.info(f"樓層 {floor_label} 使用快取數據")

                    # 創建該樓層專用的 plotter
                    floor_plotter = VehicleMapPlotter(config=self.ui.config)
                    floor_plotter.p_addr = map_files['address']
                    floor_plotter.p_section = map_files['section']
                    floor_plotter.save_path = map_files['save_path']

                    # 設定異常 ID
                    invalid_address_ids = validation_result.get('invalid_vehicle_address_ids', set()) if validation_result else set()
                    invalid_section_ids = validation_result.get('invalid_vehicle_section_ids', set()) if validation_result else set()
                    if invalid_address_ids or invalid_section_ids:
                        floor_plotter.set_invalid_ids(invalid_address_ids, invalid_section_ids)

                    # 設定顯示選項
                    floor_plotter.set_show_section_dist(self.ui.show_section_dist.get() == '1')
                    floor_plotter.set_show_tag_id(self.ui.show_tag_id.get() == '1')
                    floor_plotter.set_show_address_id(self.ui.show_address_id.get() == '1')

                    # 執行繪圖
                    floor_plotter.load()
                    floor_plotter.execute()

                    # 獲取底圖
                    base_img = floor_plotter.get_base_image()

                    # 預載打滑方框 overlay
                    overlay_img = self._preload_floor_overlay(floor_label, floor_plotter)

                    # 儲存到快取
                    self.ui._floor_cache[floor_label] = {
                        'plotter': floor_plotter,
                        'base_img': base_img,
                        'overlay_img': overlay_img,
                        'combined_img': base_img,
                        'map_data': validation_result,
                        'folder_path': folder_path,
                    }

                    self.ui._floor_loading_status[floor_label] = 'loaded'
                    loaded_count += 1
                    self.update_progress(loaded_count)
                    logging.info(f"樓層 {floor_label} 底圖+打滑方框預載完成 (尺寸: {base_img.size if base_img else 'N/A'})")
                    
                    # 啟用樓層按鈕
                    fl = floor_label
                    self.ui.root.after(0, lambda fl=fl: self._enable_floor_button(fl))

                except Exception as e:
                    logging.error(f"預載樓層 {floor_label} 失敗: {e}")
                    self.ui._floor_loading_status[floor_label] = 'failed'
                    loaded_count += 1
                    self.update_progress(loaded_count)
                    continue

            # 全部載入完成
            elapsed = time.time() - start_time
            self.update_status(f"就緒 - 已載入 {len(self.ui._floor_cache)}/3 個樓層 ({elapsed:.1f}秒)")
            logging.info(f"底圖預載完成，共載入 {len(self.ui._floor_cache)} 個樓層，耗時 {elapsed:.1f} 秒")

        except Exception as e:
            logging.error(f"預載樓層底圖時發生錯誤: {e}")
            self.update_status(f"預載失敗: {str(e)}")
        finally:
            # 重置進度條
            self.ui.root.after(2000, lambda: self.update_progress(0))

    def _preload_floor_overlay(self, floor_label, plotter):
        """預載指定樓層的打滑方框 overlay"""
        try:
            if not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
                return None

            # 依樓層篩選車輛編號範圍
            floor_nums = {
                '1F': set(range(101, 116)),
                '2F': set(range(116, 138)) | {140},
                '3F': {138, 139},
            }.get(floor_label, set())

            df = self.ui.highlight_log_df.copy()
            if floor_nums:
                def to_int_safe(s):
                    try:
                        return int(str(s).strip())
                    except Exception:
                        return None
                df['_num'] = df['number'].apply(to_int_safe)
                df = df[df['_num'].isin(floor_nums)]

            all_dates = list(df['start_date'].dropna().unique())
            if not all_dates:
                return None

            addr_counts, sec_counts = self._calc_highlight_counts(all_dates)
            all_counts = list(addr_counts.values()) + list(sec_counts.values())
            if not all_counts:
                return None

            # 計算預設門檻
            min_c = max(min(all_counts), 1)
            max_c = max(all_counts)
            threshold = max((min_c + max_c) // 2, 1)

            def cast_ids(lst):
                out = []
                for v in lst:
                    s = str(v).strip()
                    out.append(int(s) if s.isdigit() else s)
                return out

            addr_ids = cast_ids([aid for aid, cnt in addr_counts.items() if cnt >= threshold])
            sec_ids  = cast_ids([sid for sid, cnt in sec_counts.items()  if cnt >= threshold])

            plotter.set_highlight_address_ids(addr_ids)
            plotter.set_highlight_section_ids(sec_ids)
            if plotter.regenerate_overlay():
                overlay = plotter.get_overlay_image()
                logging.info(f"樓層 {floor_label} 打滑方框 overlay 預載完成（門檻≥{threshold}次）")
                return overlay
        except Exception as e:
            logging.warning(f"預載樓層 {floor_label} 打滑方框 overlay 失敗: {e}")
        return None

    def _calc_highlight_counts(self, selected_dates):
        """計算各 addressid 和 sectionid 的出現次數"""
        from collections import Counter
        if not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
            return {}, {}
        if not selected_dates:
            return {}, {}
        df = self.ui.highlight_log_df
        df = df[df['start_date'].isin(selected_dates)]
        addrs = df['addressid'].astype(str).str.strip()
        addrs = addrs[(addrs != '') & (addrs != 'nan')]
        addr_counts = dict(Counter(addrs))
        secs = df['sectionid'].astype(str).str.strip()
        secs = secs[(secs != '') & (secs != 'nan')]
        sec_counts = dict(Counter(secs))
        return addr_counts, sec_counts

    def _enable_floor_button(self, floor_label):
        """啟用指定樓層按鈕"""
        btn = self.ui.floor_buttons.get(floor_label)
        if btn:
            btn.config(state=tk.NORMAL)

    def floor_from_folder(self, folder_path):
        """從資料夾路徑猜測樓層標籤"""
        base = folder_path.replace("\\", "/").split("/")[-1].upper()
        
        if "1F" in base or "GARMIN1F" in base:
            return "1F"
        if "2F" in base or "GARMIN2F" in base:
            return "2F"
        if "3F" in base or "GARMIN3F" in base:
            return "3F"
        return None

