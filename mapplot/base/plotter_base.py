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
        self.plot()
        
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

    def plot(self):
        """繪製地圖（基礎類別不實作，由子類別覆寫）"""
        logging.info('基礎繪圖器無法直接繪製')
        raise NotImplementedError("這個方法應該由子類別實作")
