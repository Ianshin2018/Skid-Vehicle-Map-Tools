"""
資料載入模組
提供地圖資料、highlights、zone 等資料的載入功能
"""
import os
import logging
import pandas as pd
import io
from PIL import Image, ImageDraw
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

            # 建立透明 figure（與底圖同尺寸）
            zone_fig, zone_ax = plt.subplots(figsize=fig_size)
            zone_fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

            # 設定座標範圍（從 plotter 獲取）
            if hasattr(self.ui.vehicle_map_plotter, 'figure') and self.ui.vehicle_map_plotter.figure.axes:
                orig_ax = self.ui.vehicle_map_plotter.figure.axes[0]
                zone_ax.set_xlim(orig_ax.get_xlim())
                zone_ax.set_ylim(orig_ax.get_ylim())

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
                    
                    # 繪製淡藍色大方框：粗框 + 半透明填充
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
                            box_size = 8.0
                            half_size = box_size / 2
                            
                            # 繪製小方框
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

            # 保存為圖像（固定尺寸，不裁切）
            buf = io.BytesIO()
            zone_fig.savefig(buf, format='png', pad_inches=0,
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

    def _data_to_pixel(self, data_x, data_y, W, H, xlim, ylim):
        """將資料座標轉換為像素座標
        
        Args:
            data_x: 資料 X 座標
            data_y: 資料 Y 座標
            W: 圖片寬度（像素）
            H: 圖片高度（像素）
            xlim: X 座標範圍 (min, max)
            ylim: Y 座標範圍 (min, max)
            
        Returns:
            tuple: (pixel_x, pixel_y) 像素座標
        """
        px = (data_x - xlim[0]) / (xlim[1] - xlim[0]) * W
        py = H - (data_y - ylim[0]) / (ylim[1] - ylim[0]) * H
        return int(px), int(py)
    
    def _data_to_pixel_box(self, x1, y1, x2, y2, W, H, xlim, ylim):
        """將資料座標的邊界框轉換為像素座標（確保順序正確）
        
        Args:
            x1, y1: 第一個點的資料座標
            x2, y2: 第二個點的資料座標
            W: 圖片寬度（像素）
            H: 圖片高度（像素）
            xlim: X 座標範圍 (min, max)
            ylim: Y 座標範圍 (min, max)
            
        Returns:
            tuple: (px1, py1, px2, py2) 像素座標（確保 px2>=px1, py2>=py1）
        """
        px1 = int((x1 - xlim[0]) / (xlim[1] - xlim[0]) * W)
        px2 = int((x2 - xlim[0]) / (xlim[1] - xlim[0]) * W)
        py1 = int(H - (y1 - ylim[0]) / (ylim[1] - ylim[0]) * H)
        py2 = int(H - (y2 - ylim[0]) / (ylim[1] - ylim[0]) * H)
        
        # 確保座標順序正確（rectangle 需要 x2>=x1, y2>=y1）
        if px1 > px2:
            px1, px2 = px2, px1
        if py1 > py2:
            py1, py2 = py2, py1
            
        return px1, py1, px2, py2

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

            # 建立透明 figure（與底圖同尺寸）
            fig_size = (10, 8)  # 預設尺寸
            if hasattr(self.ui.vehicle_map_plotter, 'figure') and self.ui.vehicle_map_plotter.figure:
                fig_size = self.ui.vehicle_map_plotter.figure.get_size_inches()

            zone_fig, zone_ax = plt.subplots(figsize=fig_size)
            zone_fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

            # 設定座標範圍（從 plotter 獲取）
            if hasattr(self.ui.vehicle_map_plotter, 'figure') and self.ui.vehicle_map_plotter.figure.axes:
                orig_ax = self.ui.vehicle_map_plotter.figure.axes[0]
                zone_ax.set_xlim(orig_ax.get_xlim())
                zone_ax.set_ylim(orig_ax.get_ylim())

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
                    
                    # 繪製淡藍色大方框：粗框 + 半透明填充
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
                            
                            # 繪製路段小方框
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

            # 保存為圖像（固定尺寸，不裁切）
            buf = io.BytesIO()
            zone_fig.savefig(buf, format='png', pad_inches=0,
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

    def _load_map_valid_ids(self):
        """從各樓層的 Address.csv 與 Section.csv 載入所有有效 ID 集合。

        Returns:
            tuple: (valid_address_ids: set[str], valid_section_ids: set[str])
        """
        map_root = os.path.join(self.project_root, "Map")
        floor_dirs = ["Garmin1F", "Garmin2F", "Garmin3F"]
        valid_addr = set()
        valid_sec = set()

        for floor_dir in floor_dirs:
            addr_path = os.path.join(map_root, floor_dir, "Address.csv")
            sec_path = os.path.join(map_root, floor_dir, "Section.csv")

            if os.path.isfile(addr_path):
                try:
                    df_a = pd.read_csv(addr_path, dtype=str)
                    for col in df_a.columns:
                        if col.strip().lower() == "addressid":
                            valid_addr.update(df_a[col].astype(str).str.strip().tolist())
                            break
                except Exception as e:
                    logging.warning(f"載入 {addr_path} 失敗: {e}")

            if os.path.isfile(sec_path):
                try:
                    df_s = pd.read_csv(sec_path, dtype=str)
                    for col in df_s.columns:
                        if col.strip().lower() == "sectionid":
                            valid_sec.update(df_s[col].astype(str).str.strip().tolist())
                            break
                except Exception as e:
                    logging.warning(f"載入 {sec_path} 失敗: {e}")

        logging.info(
            f"地圖有效 ID 載入完成：{len(valid_addr)} 個 addressid，{len(valid_sec)} 個 sectionid"
        )
        return valid_addr, valid_sec

    def import_highlight_dataset(self, file_path):
        """匯入外部 highlights 資料集至現有資料中。

        驗證流程：
          1. 欄位檢查：必須包含 start_date, number, addressid, sectionid
          2. 格式驗證：過濾 start_date 或 number 為空的無效列
          3. 地圖驗證：比對各樓層 Address.csv / Section.csv，
                       addressid 與 sectionid 均不符地圖資料者排除，不匯入
          4. 重複比對：與現有 highlight_log_df 比對必要欄位，完全相同的列略過
          5. 若有新記錄則合併並存回 highlights.csv，同時更新記憶體資料

        Returns:
            tuple: (ok: bool, message: str, new_count: int)
        """
        REQUIRED = ["start_date", "number", "addressid", "sectionid"]
        _EMPTY = {"", "nan", "NaN", "None"}

        def _is_valid_field(val):
            return str(val).strip() not in _EMPTY

        try:
            df_new = pd.read_csv(file_path, dtype=str).fillna("")
            df_new.columns = [c.strip().lower() for c in df_new.columns]

            # 1. 欄位驗證
            missing = [c for c in REQUIRED if c not in df_new.columns]
            if missing:
                return False, f"匯入失敗：缺少必要欄位 {missing}", 0

            # 只保留必要欄並標準化
            df_new = df_new[REQUIRED].astype(str).apply(lambda s: s.str.strip())
            total_count = len(df_new)

            # 2. 格式驗證：start_date 與 number 不可為空或 'nan'
            fmt_mask = (
                df_new['start_date'].apply(_is_valid_field) &
                df_new['number'].apply(_is_valid_field)
            )
            df_valid = df_new[fmt_mask]
            invalid_count = total_count - len(df_valid)

            # 3. 地圖驗證：addressid 與 sectionid 均不符地圖資料 → 排除，不匯入
            valid_addr_ids, valid_sec_ids = self._load_map_valid_ids()
            geo_invalid_rows = []
            df_importable = df_valid  # 預設全部可匯入
            if valid_addr_ids or valid_sec_ids:
                def _is_geo_invalid(row):
                    addr = row['addressid']
                    sec = row['sectionid']
                    addr_ok = _is_valid_field(addr) and addr in valid_addr_ids
                    sec_ok = _is_valid_field(sec) and sec in valid_sec_ids
                    return not addr_ok and not sec_ok

                geo_mask = df_valid.apply(_is_geo_invalid, axis=1)
                geo_invalid_rows = df_valid[geo_mask][
                    ['start_date', 'number', 'addressid', 'sectionid']
                ].values.tolist()
                df_importable = df_valid[~geo_mask]  # 排除地圖異常列
            geo_invalid_count = len(geo_invalid_rows)

            # 4. 與現有資料比對，找出真正新增的記錄（僅對通過地圖驗證的資料）
            existing = getattr(self.ui, 'highlight_log_df', None)
            if existing is None or existing.empty:
                df_merged = df_importable
                new_count = len(df_importable)
                dup_count = 0
            else:
                existing_keys = set(
                    zip(existing['start_date'], existing['number'],
                        existing['addressid'], existing['sectionid'])
                )
                dup_mask = df_importable.apply(
                    lambda r: (r['start_date'], r['number'], r['addressid'], r['sectionid'])
                    not in existing_keys,
                    axis=1
                )
                df_really_new = df_importable[dup_mask]
                new_count = len(df_really_new)
                dup_count = len(df_importable) - new_count

                if new_count > 0:
                    df_merged = pd.concat([existing, df_really_new], ignore_index=True)
                else:
                    msg = self._build_import_msg(
                        file_path, total_count, 0, dup_count, invalid_count,
                        geo_invalid_count, geo_invalid_rows
                    )
                    return True, msg, 0

            # 5. 存回 highlights.csv
            csv_path = os.path.join(self.project_root, "highlights.csv")
            df_merged.to_csv(csv_path, index=False)

            # 6. 更新記憶體資料
            self.ui.highlight_log_df = df_merged

            msg = self._build_import_msg(
                file_path, total_count, new_count, dup_count, invalid_count,
                geo_invalid_count, geo_invalid_rows
            )
            logging.info(
                f"匯入資料集：{file_path}，"
                f"總計 {total_count}，新增 {new_count}，"
                f"重複 {dup_count}，格式異常 {invalid_count}，地圖異常 {geo_invalid_count}"
            )
            return True, msg, new_count

        except Exception as e:
            logging.error(f"匯入資料集失敗: {e}")
            return False, f"匯入失敗：{e}", 0

    def _build_import_msg(self, file_path, total, new_count, dup_count,
                          invalid_count, geo_invalid_count, geo_invalid_rows):
        """組合匯入結果提示訊息"""
        msg = (
            f"匯入來源：{os.path.basename(file_path)}\n"
            f"資料總筆數：{total} 筆\n"
            f"成功匯入：{new_count} 筆\n"
            f"重複略過：{dup_count} 筆\n"
            f"格式異常：{invalid_count} 筆\n"
            f"地圖不符：{geo_invalid_count} 筆"
        )
        remarks = []
        if invalid_count > 0:
            remarks.append(f"有 {invalid_count} 筆缺少 start_date 或 number 欄位值")
        if dup_count > 0 and new_count == 0:
            remarks.append("所有有效記錄已存在，略過匯入")
        if geo_invalid_count > 0:
            remarks.append(
                f"有 {geo_invalid_count} 筆的 addressid 與 sectionid "
                f"均無法對應各樓層地圖資料，已排除（不匯入）"
            )
            # 顯示前 5 筆異常明細
            preview = geo_invalid_rows[:5]
            detail_lines = ["  異常明細（前5筆）："]
            for row in preview:
                detail_lines.append(
                    f"  日期={row[0]}  車號={row[1]}  "
                    f"addressid={row[2]}  sectionid={row[3]}"
                )
            remarks.append("\n".join(detail_lines))
        if remarks:
            msg += "\n\n備註：\n" + "\n".join(f"・{r}" for r in remarks)
        return msg

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

