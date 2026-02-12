"""
基礎繪圖器模組
提供地圖繪製的基礎功能和資料處理
"""
import datetime
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import io
from PIL import Image

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']  # 嘗試多種可能的字型
plt.rcParams['axes.unicode_minus'] = False


class PlotterBase:
    """
    地圖繪製基礎類別
    提供地圖資料載入、預處理和基本繪製功能
    """
    def __init__(self) -> None:
        """初始化基礎繪圖器"""
        self.p_addr = '../config/alpha_hsinchu1FDemoLine/Map/Address.csv'
        self.p_section = '../config/alpha_hsinchu1FDemoLine/Map/Section.csv'
        self.save_path = './map_plot'
        self.showSectionDist = True
        self.showTagId = True
        self.showAddressId = True
        self.df_addr = None
        self.df_section = None
        self.x_dict = {}
        self.y_dict = {}
        self.invalid_address_ids = set()
        self.invalid_section_ids = set()
        self.figure = None
        self.base_image = None  # 儲存第一圖層（PIL Image）

        # highlight sets
        self.highlight_address_ids = set()
        self.highlight_section_ids = set()

        # 設定日誌
        self._setup_logging()
        
    def _setup_logging(self):
        """設定日誌"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    def set_show_section_dist(self, show_section_dist):
        """設定是否顯示路段距離"""
        self.showSectionDist = show_section_dist
        
    def set_show_tag_id(self, show_tag_id):
        """設定是否顯示 Tag ID"""
        self.showTagId = show_tag_id
        
    def set_show_address_id(self, show_address_id):
        """設定是否顯示 Address ID"""
        self.showAddressId = show_address_id
        
    def set_invalid_ids(self, invalid_address_ids, invalid_section_ids):
        """
        設定異常的地址ID和路段ID
        
        Args:
            invalid_address_ids (set): 異常的addressId集合
            invalid_section_ids (set): 異常的sectionId集合
        """
        self.invalid_address_ids = invalid_address_ids if invalid_address_ids else set()
        self.invalid_section_ids = invalid_section_ids if invalid_section_ids else set()
        logging.info(f'已設定 {len(self.invalid_address_ids)} 個異常地址和 {len(self.invalid_section_ids)} 個異常路段')

    def execute(self):
        """執行地圖繪製流程"""
        self.load()
        self.preprocess_address()
        self.preprocess_section()

        # 建立 figure/ax，傳給子類繪圖
        self.figure, ax = plt.subplots()
        # 讓子類在傳入的 ax 上繪製主體
        self.plot(ax)

        # --- 隱藏座標軸（移除刻度 / 比例尺外觀） ---
        try:
            ax.set_axis_off()
            ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
            for spine in ax.spines.values():
                spine.set_visible(False)
        except Exception:
            pass

        # --- 儲存「原始輸出圖片」（第一圖層） ---
        try:
            buf = io.BytesIO()
            # 儲存當前 figure（此時尚未加 highlight 方框）
            # 使用 pad_inches=0 去除周圍空白邊距，facecolor 指定底色
            self.figure.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, facecolor='white')
            buf.seek(0)
            self.base_image = Image.open(buf).convert("RGBA").copy()
            buf.close()
        except Exception as e:
            logging.warning(f"無法儲存 base image: {e}")
            self.base_image = None

        # --- 在同一個 ax 上加上 highlight 方框（第二圖層） ---
        # address highlights（單點方框）
        if hasattr(self, "highlight_address_ids") and self.highlight_address_ids:
            try:
                # 統一用字串比較，同時嘗試數值比較以避免型別不一致問題
                want_addrs = [str(s).strip() for s in self.highlight_address_ids]
                logging.info(f"欲高亮地址 (raw): {want_addrs}")
                df_addr = self.df_addr.copy()
                df_addr['_addr_str'] = df_addr['AddressId'].astype(str).str.strip()

                found_addrs = set()
                for want in want_addrs:
                    matched = df_addr[df_addr['_addr_str'] == want]
                    if matched.empty:
                        # 嘗試數值比較（若雙方都是純數字形式）
                        try:
                            want_int = int(want)
                            matched = df_addr[df_addr['_addr_str'].apply(lambda s: s.isdigit() and int(s) == want_int)]
                        except Exception:
                            matched = df_addr[df_addr['_addr_str'] == want]  # 保持空結果
                    if matched.empty:
                        logging.debug(f"欲高亮地址 {want} 未在 df_addr 找到")
                        continue
                    # 對於找到的每一筆都畫框（避免只取第一筆）
                    for _, r in matched.iterrows():
                        x, y = r['X'], r['Y']
                        rect = plt.Rectangle((x-2, y-2), 4, 4, linewidth=5, edgecolor='red', facecolor='none', zorder=10)
                        ax.add_patch(rect)
                        found_addrs.add(str(r['AddressId']).strip())
                missing_addrs = set(want_addrs) - found_addrs
                if missing_addrs:
                    logging.warning(f"以下高亮地址在 df_addr 找不到：{missing_addrs}")
            except Exception as e:
                logging.debug(f"處理 address highlights 時例外: {e}")

        # section highlights: 使用字串比對，並記錄日誌
        if hasattr(self, "highlight_section_ids") and self.highlight_section_ids:
            # 轉成字串集合（去除空白）
            want_set = set([str(s).strip() for s in self.highlight_section_ids])
            logging.info(f"欲高亮路段: {want_set}")
            # 將 df_section 中 SectionId 都轉成字串一次（效能可接受）
            df_sec = self.df_section.copy()
            df_sec['_sec_str'] = df_sec['SectionId'].astype(str).str.strip()

            found = set()
            for _, sec_row in df_sec[df_sec['_sec_str'].isin(want_set)].iterrows():
                sec_id_str = str(sec_row['SectionId']).strip()
                found.add(sec_id_str)
                from_addr = sec_row['FromAddressId']
                to_addr = sec_row['ToAddressId']

                # 解析 address id -> (addr_x, addr_y)
                try:
                    def addr_to_key(a):
                        s = str(a)
                        ax_k = int(s[1:4])
                        ay_k = int(s[4:7])
                        return (ax_k, ay_k)
                    k1 = addr_to_key(from_addr)
                    k2 = addr_to_key(to_addr)
                except Exception:
                    logging.warning(f"Section {sec_row['SectionId']} 的 AddressId 格式錯誤 (From:{from_addr} To:{to_addr})")
                    continue

                x1 = self.x_dict.get(k1)
                y1 = self.y_dict.get(k1)
                x2 = self.x_dict.get(k2)
                y2 = self.y_dict.get(k2)

                if None in (x1, y1, x2, y2):
                    logging.warning(f"無法取得路段 {sec_row['SectionId']} 的顯示座標 (keys: {k1},{k2})")
                    continue

                # 畫粗線代表高亮路段（保留原有視覺提示）
                try:
                    ax.plot([x1, x2], [y1, y2], color='orange', linewidth=3.5, zorder=9)
                except Exception as e:
                    logging.debug(f"繪製高亮路段 {sec_row['SectionId']} 失敗: {e}")

                # 計算包含兩個地址的外框（bounding box），並繪製該方框
                try:
                    pad = 4.0  # 外框 padding（視覺可調）
                    xmin = min(x1, x2) - pad
                    ymin = min(y1, y2) - pad
                    width = abs(x2 - x1) + 2 * pad
                    height = abs(y2 - y1) + 2 * pad

                    # 若寬或高為 0（同一點），給最小值以便能看到方框
                    min_side = 8.0
                    if width <= 0:
                        width = min_side
                        xmin = min(x1, x2) - width / 2
                    if height <= 0:
                        height = min_side
                        ymin = min(y1, y2) - height / 2

                    bbox_rect = plt.Rectangle((xmin, ymin), width, height,
                                              linewidth=5, edgecolor='red', facecolor='none', zorder=11)
                    ax.add_patch(bbox_rect)
                except Exception as e:
                    logging.debug(f"繪製路段外框 {sec_row['SectionId']} 失敗: {e}")

            missing = want_set - found
            if missing:
                logging.warning(f"以下高亮路段在 df_section 找不到：{missing}")

        # 可能需要刷新或調整座標
        try:
            ax.autoscale_view()
        except Exception:
            pass

    def load(self):
        """載入地圖資料"""
        logging.info(f'載入資料自 {self.p_addr} 和 {self.p_section}')
        try:
            self.df_addr = pd.read_csv(self.p_addr)
            self.df_section = pd.read_csv(self.p_section)            
            logging.info('資料成功載入')
        except FileNotFoundError as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            logging.error(f"錯誤: 找不到 CSV 檔案。{e} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
            raise

    def preprocess_address(self):
        """預處理地址資料"""
        # 保存原始座標用於距離計算（保持原始公分單位）
        self.df_addr['X_original'] = self.df_addr['X'].copy()
        self.df_addr['Y_original'] = self.df_addr['Y'].copy()
        
        # 縮放座標用於繪圖顯示（先除以100轉成公尺，再除以額外係數放大顯示）
        self.df_addr['X'] = self.df_addr['X'] * 2 / 100  # 放大2倍顯示
        self.df_addr['Y'] = self.df_addr['Y'] * 2 / 100  # 放大2倍顯示
        addressId = self.df_addr.pop('AddressId')
        self.addr_x = pd.Series()
        self.addr_y = pd.Series()

        for i in range(0, len(addressId)):
            self.addr_x[i] = int(str(addressId[i])[1:4])
            self.addr_y[i] = int(str(addressId[i])[4:7])
        self.df_addr.insert(1, 'addr_x', self.addr_x)
        self.df_addr.insert(2, 'addr_y', self.addr_y)
        # 將AddressId加回df_addr以便之後使用
        self.df_addr.insert(0, 'AddressId', addressId)

        self.x_dict = {}
        self.y_dict = {}

        # 迭代 DataFrame 中的每一行
        for index, row in self.df_addr.iterrows():
            x_addr_value = row['addr_x']
            y_addr_value = row['addr_y']
            x_value = row['X']
            y_value = row['Y']            # 更新字典的鍵值對
            self.x_dict[(x_addr_value, y_addr_value)] = x_value
            self.y_dict[(x_addr_value, y_addr_value)] = y_value

    def preprocess_section(self):
        """預處理路段資料"""
        from_addressId = self.df_section.pop('FromAddressId')
        to_addressId = self.df_section.pop('ToAddressId')
        self.from_addr_x = pd.Series()
        self.from_addr_y = pd.Series()

        for i in range(0, len(self.df_section)):
            self.from_addr_x[i] = int(str(from_addressId[i])[1:4])
            self.from_addr_y[i] = int(str(from_addressId[i])[4:7])
        self.to_addr_x = pd.Series()
        self.to_addr_y = pd.Series()

        for i in range(0, len(to_addressId)):
            self.to_addr_x[i] = int(str(to_addressId[i])[1:4])
            self.to_addr_y[i] = int(str(to_addressId[i])[4:7])
        
        # 將FromAddressId和ToAddressId加回df_section以便之後使用
        self.df_section.insert(0, 'FromAddressId', from_addressId)
        self.df_section.insert(1, 'ToAddressId', to_addressId)
        
        # 計算路段距離（基於Address的XY座標）
        self._calculate_section_distances(from_addressId, to_addressId)

        
    def draw_exclamation_mark(self, ax, x, y, size=0.5, color='red'):
        """
        在指定位置繪製驚嘆號
        
        Args:
            ax: matplotlib座標軸物件
            x (float): X座標
            y (float): Y座標
            size (float): 驚嘆號大小
            color (str): 顏色
        """
        ax.text(x, y, '!', color=color, fontsize=20, fontweight='bold', ha='center', va='center')
    
    def draw_invalid_elements(self, ax):
        """
        在地圖上標示所有異常元素
        
        Args:
            ax: matplotlib座標軸物件
        """
        # 繪製異常地址的驚嘆號
        if self.invalid_address_ids:
            for address_id in self.invalid_address_ids:
                address_row = self.df_addr[self.df_addr['AddressId'] == address_id]
                if not address_row.empty:
                    x = address_row['X'].values[0]
                    y = address_row['Y'].values[0]
                    self.draw_exclamation_mark(ax, x, y)
                    logging.info(f'在地址 {address_id} ({x}, {y}) 處繪製驚嘆號')
        
        # 繪製異常路段的驚嘆號
        if self.invalid_section_ids:
            for section_id in self.invalid_section_ids:
                section_row = self.df_section[self.df_section['SectionId'] == section_id]
                if not section_row.empty:
                    # 取得路段的起點和終點
                    from_addr_id = section_row['FromAddressId'].values[0]
                    to_addr_id = section_row['ToAddressId'].values[0]
                    
                    # 查詢起點坐標
                    from_addr_row = self.df_addr[self.df_addr['AddressId'] == from_addr_id]
                    to_addr_row = self.df_addr[self.df_addr['AddressId'] == to_addr_id]
                    
                    if not from_addr_row.empty and not to_addr_row.empty:
                        # 計算路段中點
                        x1 = from_addr_row['X'].values[0]
                        y1 = from_addr_row['Y'].values[0]
                        x2 = to_addr_row['X'].values[0]
                        y2 = to_addr_row['Y'].values[0]
                        
                        # 在路段中點繪製驚嘆號
                        mid_x = (x1 + x2) / 2
                        mid_y = (y1 + y2) / 2
                        self.draw_exclamation_mark(ax, mid_x, mid_y, color='orange')
                        logging.info(f'在路段 {section_id} 中點 ({mid_x}, {mid_y}) 處繪製驚嘆號')

    def _calculate_section_distances(self, from_addressId, to_addressId):
        """
        根據起點和終點的地址座標計算路段距離
        
        Args:
            from_addressId (Series): 起點地址ID序列
            to_addressId (Series): 終點地址ID序列
        """
        # 如果已經有Distance欄位且不想覆蓋，則跳過計算
        if 'Distance' in self.df_section.columns:
            logging.info("路段資料已包含 'Distance' 欄位，將使用現有數值")
            return
            
        # 建立Distance欄位
        distances = []
        
        # 為每個路段計算距離
        for i in range(len(self.df_section)):
            # 獲取起點和終點的座標
            from_addr = from_addressId[i]
            to_addr = to_addressId[i]
            
            # 在df_addr中查詢原始座標（未縮放的）
            from_xy = self.df_addr[self.df_addr['AddressId'] == from_addr][['X_original', 'Y_original']].values
            to_xy = self.df_addr[self.df_addr['AddressId'] == to_addr][['X_original', 'Y_original']].values
            
            # 確保找到了座標
            if len(from_xy) > 0 and len(to_xy) > 0:
                # 計算歐氏距離（以公分為單位）
                dx = from_xy[0][0] - to_xy[0][0]  # 原始座標已經是公分單位
                dy = from_xy[0][1] - to_xy[0][1]  # 原始座標已經是公分單位
                distance = np.sqrt(dx**2 + dy**2)
                distances.append(int(distance))  # 轉為整數
            else:
                # 如果找不到座標，設為0
                distances.append(0)
                logging.warning(f"無法找到地址座標 (從:{from_addr} 到:{to_addr})，設定距離為0")
                
        # 將計算好的距離添加到DataFrame中
        self.df_section['Distance'] = distances
        logging.info(f"已自動計算並新增 'Distance' 欄位 (共 {len(distances)} 個路段)")

    def plot(self, ax):
        """繪製地圖（基礎類別不實作，由子類別覆寫）"""
        logging.info('基礎繪圖器無法直接繪製')
        raise NotImplementedError("這個方法應該由子類別實作")
        
    def set_highlight_address_ids(self, address_id_list):
        """設定要高亮顯示的 addressID 清單"""
        self.highlight_address_ids = set(address_id_list)

    def set_highlight_section_ids(self, section_id_list):
        """設定要高亮顯示的 sectionID 清單"""
        self.highlight_section_ids = set(section_id_list)

    def get_figure(self):
        """回傳 matplotlib Figure（含高亮方框）"""
        return getattr(self, "figure", None)

    def get_base_image(self):
        """回傳 PIL Image（第一圖層）"""
        return getattr(self, "base_image", None)
    
    def _draw_address_points(self, ax, df_addr, x_dict, y_dict, *args, **kwargs):
        """
        預設安全實作：當子類未實作 _draw_address_points 時使用。
        簡單在每個地址位置畫小方塊，避免 AttributeError。
        """
        try:
            if df_addr is None or df_addr.empty:
                return
            square_side = kwargs.get('square_side_length', 2)
            for i in range(len(df_addr)):
                # 優先使用對齊後座標字典，否則使用 df 中的 X, Y
                key = (int(df_addr.loc[i, 'addr_x']) if 'addr_x' in df_addr.columns else None,
                       int(df_addr.loc[i, 'addr_y']) if 'addr_y' in df_addr.columns else None)
                if key[0] is not None and key in x_dict and key in y_dict:
                    x = x_dict[key]
                    y = y_dict[key]
                else:
                    x = df_addr.loc[i, 'X']
                    y = df_addr.loc[i, 'Y']
                rect = plt.Rectangle((x - square_side/2, y - square_side/2),
                                     square_side, square_side,
                                     linewidth=1, edgecolor='gray', facecolor='none', alpha=0.6)
                ax.add_patch(rect)
        except Exception as e:
            logging.exception("PlotterBase._draw_address_points 預設繪製失敗: %s", e)