"""
資料載入模組
提供地圖資料、highlights、zone 等資料的載入功能
"""
import os
import logging
import pandas as pd
import io
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


class DataLoader:
    """
    資料載入類別
    負責載入和處理地圖相關資料
    """
    def __init__(self, ui_instance, project_root):
        """初始化資料載入器
        
        Args:
            ui_instance: UI 物件實例
            project_root: 專案根目錄路徑
        """
        self.ui = ui_instance
        self.project_root = project_root
        
    def load_highlights(self, folder_path=None):
        """
        嘗試從專案根目錄（與 main.py 同一層）讀取 highlights.csv，
        若找不到再到指定的 folder_path 搜尋。預期欄位: Floor, Type, Id
        """
        self.ui.highlights_df = None
        try:
            candidates = [
                os.path.join(self.project_root, "highlights.csv"),
                os.path.join(folder_path or "", "highlights.csv")
            ]
            csv_path = None
            for p in candidates:
                if p and os.path.isfile(p):
                    csv_path = p
                    break

            if not csv_path:
                logging.info(f"未找到 highlights.csv（搜尋路徑: {candidates}），跳過自動打滑方框設定")
                return

            df = pd.read_csv(csv_path, dtype=str).fillna("")
            logging.info(f"從 {csv_path} 載入 highlights.csv (共 {len(df)} 筆)")

            # 標準化欄位名稱
            cols = {c.lower(): c for c in df.columns}
            low = {k.lower(): v for k, v in cols.items()}
            # 需要 floor,type,id 三個欄位
            if not any(k in low for k in ("floor",)) or not any(k in low for k in ("type",)) or not any(k in low for k in ("id", "idx", "sectionid")):
                logging.warning("highlights.csv 欄位不足，需包含 Floor, Type, Id")
                return
            # 重新命名到統一欄位
            df = df.rename(columns={low.get("floor"): "Floor", low.get("type"): "Type", low.get("id", low.get("idx", low.get("sectionid"))): "Id"})
            df["Floor"] = df["Floor"].astype(str).str.strip().str.upper()
            df["Type"] = df["Type"].astype(str).str.strip().str.lower()
            df["Id"] = df["Id"].astype(str).str.strip()
            # 保留合法 Type
            df = df[df["Type"].isin(["address", "section"])]
            self.ui.highlights_df = df
        except Exception as e:
            logging.warning(f"讀取 highlights.csv 失敗: {e}")
            self.ui.highlights_df = None

    def load_highlight_log(self, folder_path=None):
        """
        讀取 highlight log CSV：優先於專案根目錄（與 main.py 同層）搜尋，
        若找不到再於 folder_path 搜尋。標準欄位: start_date, number, addressid, sectionid
        """
        try:
            filenames = ("highlights.csv", "highlight_log.csv", "highlights_log.csv")
            csv_path = None
            # 優先在專案根搜尋，再在 folder_path 搜尋
            search_paths = []
            for fname in filenames:
                search_paths.append(os.path.join(self.project_root, fname))
            for fname in filenames:
                search_paths.append(os.path.join(folder_path or "", fname))

            for p in search_paths:
                if p and os.path.isfile(p):
                    csv_path = p
                    break

            if not csv_path:
                logging.info(f"未找到 highlight log CSV（搜尋: {search_paths}），跳過載入")
                self.ui.highlight_log_df = None
                return

            df = pd.read_csv(csv_path, dtype=str).fillna("")
            df.columns = [c.strip().lower() for c in df.columns]

            # 確保欄位存在，若缺則建立空欄
            for col in ("start_date", "number", "addressid", "sectionid"):
                if col not in df.columns:
                    df[col] = ""

            # 只保留必要欄並標準化為字串
            df = df[["start_date", "number", "addressid", "sectionid"]].astype(str).apply(lambda s: s.str.strip())
            self.ui.highlight_log_df = df
            logging.info(f"從 {csv_path} 載入 highlight log，共 {len(df)} 筆記錄")
        except Exception as e:
            logging.warning(f"讀取 highlights CSV 失敗: {e}")
            self.ui.highlight_log_df = None

    def load_zone_for_floor(self, folder_path):
        """載入樓層的施工區域資料並產生圖層

        Args:
            folder_path: 樓層資料夾路徑

        Returns:
            PIL Image or None: 施工區域圖層（透明背景）
        """
        zone_csv_path = os.path.join(folder_path, 'zone.csv')
        if not os.path.exists(zone_csv_path):
            logging.info(f"未找到 zone.csv: {zone_csv_path}")
            return None

        try:
            # 讀取 zone.csv
            df_zone = pd.read_csv(zone_csv_path, dtype=str)
            logging.info(f"載入 zone CSV: {zone_csv_path} (共 {len(df_zone)} 筆)")

            # 獲取 AddressId 欄位
            if 'AddressId' not in df_zone.columns:
                logging.warning(f"zone CSV 缺少 AddressId 欄位")
                return None

            # 標準化欄位名稱（大小寫不敏感）
            df_zone.columns = [c.strip() for c in df_zone.columns]
            
            # 檢查是否有 zone_name 欄位
            has_zone_name = 'zone_name' in [c.lower() for c in df_zone.columns]
            
            # 標準化 zone_name 欄位名稱
            if has_zone_name:
                for c in df_zone.columns:
                    if c.lower() == 'zone_name':
                        df_zone['zone_name'] = df_zone[c].astype(str).str.strip()
                        break
            
            addressids = df_zone['AddressId'].str.strip().tolist()
            if not addressids:
                logging.warning("zone CSV 沒有有效的 addressid")
                return None

            logging.info(f"找到 {len(addressids)} 個施工位置")

            # 獲取 plotter 的座標字典
            if not hasattr(self.ui, 'vehicle_map_plotter') or self.ui.vehicle_map_plotter is None:
                return None

            x_dict = getattr(self.ui.vehicle_map_plotter, 'x_dict', {})
            y_dict = getattr(self.ui.vehicle_map_plotter, 'y_dict', {})

            if not x_dict or not y_dict:
                logging.warning("vehicle_map_plotter 沒有座標資料")
                return None

            # 建立透明圖層繪製 zone 方框
            # 獲取 figure 尺寸
            fig_size = (10, 8)  # 預設尺寸
            if hasattr(self.ui.vehicle_map_plotter, 'figure') and self.ui.vehicle_map_plotter.figure:
                fig_size = self.ui.vehicle_map_plotter.figure.get_size_inches()

            # 建立透明 figure
            zone_fig, zone_ax = plt.subplots(figsize=fig_size)

            # 設定座標範圍（從 plotter 獲取）
            if hasattr(self.ui.vehicle_map_plotter, 'figure') and self.ui.vehicle_map_plotter.figure.axes:
                orig_ax = self.ui.vehicle_map_plotter.figure.axes[0]
                zone_ax.set_xlim(orig_ax.get_xlim())
                zone_ax.set_ylim(orig_ax.get_ylim())
                zone_ax.set_aspect(orig_ax.get_aspect())

            # 隱藏座標軸
            zone_ax.set_axis_off()
            zone_ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
            for spine in zone_ax.spines.values():
                spine.set_visible(False)

            # 繪製淡藍色方框
            # 根據是否有 zone_name 來決定繪製方式
            if has_zone_name and 'zone_name' in df_zone.columns:
                # 按 zone_name 分組，每個分組畫一個大框
                logging.info(f"按 zone_name 分組繪製施工區域")
                
                for zone_name, group in df_zone.groupby('zone_name'):
                    # 收集該 zone 的所有座標
                    coords = []
                    valid_addressids = []
                    
                    for addr_id in group['AddressId']:
                        addr_id_str = str(addr_id).strip()
                        try:
                            ax = int(addr_id_str[1:4])
                            ay = int(addr_id_str[4:7])
                            key = (ax, ay)
                            
                            if key in x_dict and key in y_dict:
                                coords.append((x_dict[key], y_dict[key]))
                                valid_addressids.append(addr_id_str)
                        except Exception:
                            continue
                    
                    if not coords:
                        logging.warning(f"Zone '{zone_name}' 沒有有效的座標")
                        continue
                    
                    # 計算 bounding box
                    xs = [c[0] for c in coords]
                    ys = [c[1] for c in coords]
                    xmin, xmax = min(xs), max(xs)
                    ymin, ymax = min(ys), max(ys)
                    
                    # 加上 padding
                    padding = 6.0
                    xmin -= padding
                    ymin -= padding
                    width = (xmax - xmin) + 2 * padding
                    height = (ymax - ymin) + 2 * padding
                    
                    # 繪製該 zone 的方框
                    zone_rect = Rectangle(
                        (xmin, ymin), width, height,
                        linewidth=5,
                        edgecolor='skyblue',
                        facecolor='skyblue',
                        alpha=0.3,
                        zorder=5
                    )
                    zone_ax.add_patch(zone_rect)
                    
                    logging.info(f"繪製 zone '{zone_name}': {len(valid_addressids)} 個 addressid")
            else:
                # 沒有 zone_name，對每個 addressID 畫獨立小框
                logging.info(f"對每個 addressID 繪製獨立施工區域")
                
                valid_count = 0
                for addr_id in addressids:
                    addr_id_str = str(addr_id).strip()
                    
                    try:
                        ax = int(addr_id_str[1:4])
                        ay = int(addr_id_str[4:7])
                        key = (ax, ay)
                        
                        if key in x_dict and key in y_dict:
                            x = x_dict[key]
                            y = y_dict[key]
                            
                            # 每個 addressID 畫一個小方框（以該點為中心）
                            box_size = 8.0  # 方框大小
                            half_size = box_size / 2
                            
                            zone_rect = Rectangle(
                                (x - half_size, y - half_size), box_size, box_size,
                                linewidth=3,
                                edgecolor='skyblue',
                                facecolor='skyblue',
                                alpha=0.5,
                                zorder=5
                            )
                            zone_ax.add_patch(zone_rect)
                            valid_count += 1
                    except Exception:
                        continue
                
                logging.info(f"繪製了 {valid_count} 個施工區域框")

            # 保存為圖像
            buf = io.BytesIO()
            zone_fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0,
                           facecolor='none', transparent=True)
            buf.seek(0)
            zone_img = Image.open(buf).convert("RGBA").copy()
            buf.close()

            plt.close(zone_fig)

            logging.info(f"施工區域圖層已建立")
            return zone_img

        except Exception as e:
            logging.error(f"建立施工區域圖層失敗: {e}")
            return None

    def load_zone_section_for_floor(self, folder_path):
        """載入樓層的施工區域路段資料並產生圖層

        Args:
            folder_path: 樓層資料夾路徑

        Returns:
            PIL Image or None: 施工區域路段圖層（透明背景）
        """
        zone_section_csv_path = os.path.join(folder_path, 'zoneSection.csv')
        if not os.path.exists(zone_section_csv_path):
            logging.info(f"未找到 zoneSection.csv: {zone_section_csv_path}")
            return None

        try:
            # 讀取 zoneSection.csv
            df_zone_section = pd.read_csv(zone_section_csv_path, dtype=str)
            logging.info(f"載入 zoneSection CSV: {zone_section_csv_path} (共 {len(df_zone_section)} 筆)")

            # 獲取必要欄位
            if 'SectionId' not in df_zone_section.columns:
                logging.warning(f"zoneSection CSV 缺少 SectionId 欄位")
                return None

            if 'FromAddressId' not in df_zone_section.columns or 'ToAddressId' not in df_zone_section.columns:
                logging.warning(f"zoneSection CSV 缺少 FromAddressId 或 ToAddressId 欄位")
                return None

            # 標準化欄位名稱（大小寫不敏感）
            df_zone_section.columns = [c.strip() for c in df_zone_section.columns]
            
            # 檢查是否有 zone_name 欄位
            has_zone_name = 'zone_name' in [c.lower() for c in df_zone_section.columns]
            
            # 標準化 zone_name 欄位名稱
            if has_zone_name:
                for c in df_zone_section.columns:
                    if c.lower() == 'zone_name':
                        df_zone_section['zone_name'] = df_zone_section[c].astype(str).str.strip()
                        break
            
            # 獲取路段資料
            section_ids = df_zone_section['SectionId'].str.strip().tolist()
            from_addressids = df_zone_section['FromAddressId'].str.strip().tolist()
            to_addressids = df_zone_section['ToAddressId'].str.strip().tolist()
            
            if not section_ids:
                logging.warning("zoneSection CSV 沒有有效的 section id")
                return None

            logging.info(f"找到 {len(section_ids)} 個施工路段")

            # 獲取 plotter 的座標字典
            if not hasattr(self.ui, 'vehicle_map_plotter') or self.ui.vehicle_map_plotter is None:
                return None

            x_dict = getattr(self.ui.vehicle_map_plotter, 'x_dict', {})
            y_dict = getattr(self.ui.vehicle_map_plotter, 'y_dict', {})

            if not x_dict or not y_dict:
                logging.warning("vehicle_map_plotter 沒有座標資料")
                return None

            # 建立透明圖層繪製 zone section 方框
            # 獲取 figure 尺寸
            fig_size = (10, 8)  # 預設尺寸
            if hasattr(self.ui.vehicle_map_plotter, 'figure') and self.ui.vehicle_map_plotter.figure:
                fig_size = self.ui.vehicle_map_plotter.figure.get_size_inches()

            # 建立透明 figure
            zone_fig, zone_ax = plt.subplots(figsize=fig_size)

            # 設定座標範圍（從 plotter 獲取）
            if hasattr(self.ui.vehicle_map_plotter, 'figure') and self.ui.vehicle_map_plotter.figure.axes:
                orig_ax = self.ui.vehicle_map_plotter.figure.axes[0]
                zone_ax.set_xlim(orig_ax.get_xlim())
                zone_ax.set_ylim(orig_ax.get_ylim())
                zone_ax.set_aspect(orig_ax.get_aspect())

            # 隱藏座標軸
            zone_ax.set_axis_off()
            zone_ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
            for spine in zone_ax.spines.values():
                spine.set_visible(False)

            # 繪製淡藍色路段方框
            # 根據是否有 zone_name 來決定繪製方式
            if has_zone_name and 'zone_name' in df_zone_section.columns:
                # 按 zone_name 分組，每個分組畫一個大框
                logging.info(f"按 zone_name 分組繪製施工路段區域")
                
                for zone_name, group in df_zone_section.groupby('zone_name'):
                    # 收集該 zone 的所有路段座標
                    coords = []
                    valid_sections = []
                    
                    for idx, row in group.iterrows():
                        from_addr = str(row['FromAddressId']).strip()
                        to_addr = str(row['ToAddressId']).strip()
                        
                        try:
                            from_ax = int(from_addr[1:4])
                            from_ay = int(from_addr[4:7])
                            to_ax = int(to_addr[1:4])
                            to_ay = int(to_addr[4:7])
                            
                            from_key = (from_ax, from_ay)
                            to_key = (to_ax, to_ay)
                            
                            if from_key in x_dict and from_key in y_dict and to_key in x_dict and to_key in y_dict:
                                coords.append((x_dict[from_key], y_dict[from_key]))
                                coords.append((x_dict[to_key], y_dict[to_key]))
                                valid_sections.append(str(row['SectionId']).strip())
                        except Exception:
                            continue
                    
                    if not coords:
                        logging.warning(f"Zone '{zone_name}' 沒有有效的路段座標")
                        continue
                    
                    # 計算 bounding box
                    xs = [c[0] for c in coords]
                    ys = [c[1] for c in coords]
                    xmin, xmax = min(xs), max(xs)
                    ymin, ymax = min(ys), max(ys)
                    
                    # 加上 padding
                    padding = 6.0
                    xmin -= padding
                    ymin -= padding
                    width = (xmax - xmin) + 2 * padding
                    height = (ymax - ymin) + 2 * padding
                    
                    # 繪製該 zone 的方框
                    zone_rect = Rectangle(
                        (xmin, ymin), width, height,
                        linewidth=5,
                        edgecolor='skyblue',
                        facecolor='skyblue',
                        alpha=0.3,
                        zorder=5
                    )
                    zone_ax.add_patch(zone_rect)
                    
                    logging.info(f"繪製 zone '{zone_name}': {len(valid_sections)} 個路段")
            else:
                # 沒有 zone_name，對每個路段畫獨立小框
                logging.info(f"對每個路段繪製獨立施工區域")
                
                valid_count = 0
                for idx, row in df_zone_section.iterrows():
                    from_addr = str(row['FromAddressId']).strip()
                    to_addr = str(row['ToAddressId']).strip()
                    section_id = str(row['SectionId']).strip()
                    
                    try:
                        from_ax = int(from_addr[1:4])
                        from_ay = int(from_addr[4:7])
                        to_ax = int(to_addr[1:4])
                        to_ay = int(to_addr[4:7])
                        
                        from_key = (from_ax, from_ay)
                        to_key = (to_ax, to_ay)
                        
                        if from_key in x_dict and from_key in y_dict and to_key in x_dict and to_key in y_dict:
                            from_x = x_dict[from_key]
                            from_y = y_dict[from_key]
                            to_x = x_dict[to_key]
                            to_y = y_dict[to_key]
                            
                            # 計算路段的中點和寬度
                            mid_x = (from_x + to_x) / 2
                            mid_y = (from_y + to_y) / 2
                            
                            # 計算路段的 bounding box
                            xmin = min(from_x, to_x)
                            xmax = max(from_x, to_x)
                            ymin = min(from_y, to_y)
                            ymax = max(from_y, to_y)
                            
                            # 加上 padding
                            padding = 2.0
                            xmin -= padding
                            ymin -= padding
                            width = (xmax - xmin) + 2 * padding
                            height = (ymax - ymin) + 2 * padding
                            
                            # 確保最小尺寸
                            if width < 4:
                                width = 4
                            if height < 4:
                                height = 4
                            
                            # 繪製路段方框
                            zone_rect = Rectangle(
                                (xmin, ymin), width, height,
                                linewidth=3,
                                edgecolor='skyblue',
                                facecolor='skyblue',
                                alpha=0.5,
                                zorder=5
                            )
                            zone_ax.add_patch(zone_rect)
                            valid_count += 1
                    except Exception:
                        continue
                
                logging.info(f"繪製了 {valid_count} 個施工路段框")

            # 保存為圖像
            buf = io.BytesIO()
            zone_fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0,
                           facecolor='none', transparent=True)
            buf.seek(0)
            zone_img = Image.open(buf).convert("RGBA").copy()
            buf.close()

            plt.close(zone_fig)

            logging.info(f"施工路段區域圖層已建立")
            return zone_img

        except Exception as e:
            logging.error(f"建立施工路段區域圖層失敗: {e}")
            return None

    def calc_highlight_counts(self, selected_dates):
        """計算各 addressid 和 sectionid 在選定日期中的出現次數。

        Returns:
            tuple: (addr_counts dict, sec_counts dict) — {id_str: count}
        """
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

    def get_highlights_for_floor(self, floor_label):
        """
        根據 floor_label 回傳 (address_ids, section_ids) 兩個 list。
        規則（由使用者指定）：
          - 1F: number 101..115
          - 2F: number 116..137 和 140
          - 3F: number 138, 139
        每筆紀錄優先取 addressid（非空），若 addressid 空則取 sectionid；兩者皆空則跳過。
        number 需能轉為 int 才比對；回傳 id 會嘗試轉為 int（若為純數字）。
        """
        addr_ids = []
        sec_ids = []
        if getattr(self.ui, "highlight_log_df", None) is None or floor_label is None:
            return addr_ids, sec_ids

        df = self.ui.highlight_log_df.copy()

        def to_int_safe(s):
            try:
                return int(str(s).strip())
            except Exception:
                return None

        df["_num"] = df["number"].apply(to_int_safe)

        want_nums = set()
        if floor_label == "1F":
            want_nums.update(range(101, 116))
        elif floor_label == "2F":
            want_nums.update(range(116, 138))
            want_nums.add(140)
        elif floor_label == "3F":
            want_nums.update([138, 139])

        sel = df[df["_num"].isin(want_nums)]

        for _, row in sel.iterrows():
            addr = row.get("addressid", "")
            sec = row.get("sectionid", "")
            chosen = None
            chosen_type = None
            if isinstance(addr, str) and addr.strip() != "":
                chosen = addr.strip()
                chosen_type = "address"
            elif isinstance(sec, str) and sec.strip() != "":
                chosen = sec.strip()
                chosen_type = "section"
            else:
                continue

            # 轉為 int 若可能
            try:
                val = int(chosen)
            except Exception:
                val = chosen

            if chosen_type == "address":
                addr_ids.append(val)
            else:
                sec_ids.append(val)

        logging.info(f"樓層 {floor_label} 取得打滑方框：{len(addr_ids)} addresses, {len(sec_ids)} sections")
        return addr_ids, sec_ids

    def get_highlights_by_dates(self, selected_dates):
        """根據選擇的日期獲取打滑方框的 address 和 section IDs

        Args:
            selected_dates: 選擇的日期列表

        Returns:
            tuple: (address_ids, section_ids)
        """
        addr_ids = []
        sec_ids = []

        if not selected_dates or not hasattr(self.ui, 'highlight_log_df') or self.ui.highlight_log_df is None:
            return addr_ids, sec_ids

        try:
            # 過濾出選擇日期的記錄
            filtered_df = self.ui.highlight_log_df[self.ui.highlight_log_df['start_date'].isin(selected_dates)]

            for _, row in filtered_df.iterrows():
                addr = row.get("addressid", "")
                sec = row.get("sectionid", "")

                # 優先使用 addressid，若為空則使用 sectionid
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

