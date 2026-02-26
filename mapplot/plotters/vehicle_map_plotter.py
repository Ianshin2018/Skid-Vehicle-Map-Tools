"""
車輛地圖繪製器模組
提供車輛地圖的繪製功能
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np
import sys
import logging
from datetime import datetime

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']  # 嘗試多種可能的字型
plt.rcParams['axes.unicode_minus'] = False
from ..base.plotter_base import PlotterBase
from ..utils.visualization import (
    setup_figure, 
    draw_square, 
    draw_obstacle_line, 
    draw_arrow, 
    finalize_plot
)


class VehicleMapPlotter(PlotterBase):    
    """
    車輛地圖繪製器類別
    繪製包含車輛行駛路徑的地圖
    """
    def __init__(self, config=None):
        """初始化車輛地圖繪製器
        
        Args:
            config (dict, optional): 配置檔案，若為 None 則使用預設設定
        """
        super().__init__()
        self.drawn_sections = set()  # 用於追蹤已繪製的路段
        # Grid map 參數
        if config and "grid_map" in config:
            # 從配置檔案初始化
            self.use_grid_map = config["grid_map"]["enabled"]
            self.grid_spacing = config["grid_map"]["spacing"]
            self.alignment_strength = config["grid_map"]["alignment_strength"]
        else:
            # 使用預設值
            self.use_grid_map = False  # 是否使用格子地圖模式
            self.grid_spacing = 15  # 格子間距，預設為 15
            self.alignment_strength = 2.0  # 對齊強度，數值越大對齊越嚴格
            
        self.alignment_threshold = 0.5  # 對齊閾值，用於判斷是否在同一線上

        self.highlight_address_ids = set()
        self.figure = None  # 新增 figure 屬性
        
    def set_grid_map_enabled(self, enabled):
        """
        設定是否啟用格子地圖模式
        
        Args:
            enabled (bool): 是否啟用格子地圖模式
        """
        self.use_grid_map = enabled
        
    def set_grid_spacing(self, spacing):
        """
        設定格子間距
        
        Args:
            spacing (float): 格子間距，必須大於 0
        """
        if spacing > 0:
            self.grid_spacing = spacing
        return self.grid_spacing
    
    def get_grid_spacing(self):
        """
        獲取當前格子間距
        
        Returns:
            float: 當前格子間距
        """
        return self.grid_spacing
    
    def set_alignment_threshold(self, threshold):
        """
        設定對齊閾值
        
        Args:
            threshold (float): 對齊閾值，用於判斷站點是否在同一線上
        """
        if threshold > 0:
            self.alignment_threshold = threshold
        return self.alignment_threshold
        
    def get_alignment_threshold(self):
        """
        獲取當前對齊閾值
        
        Returns:
        float: 當前對齊閾值        
        """
        return self.alignment_threshold
    
    def set_alignment_strength(self, strength):
        """
        設定對齊強度
        
        Args:
            strength (float): 對齊強度，數值越大對齊越嚴格 (建議範圍: 1.0-5.0)
        """
        if strength > 0:
            self.alignment_strength = strength
        return self.alignment_strength
        
    def get_alignment_strength(self):
        """
        獲取當前對齊強度
        
        Returns:
            float: 當前對齊強度        """
        return self.alignment_strength
        
    def _align_coordinates_by_distance(self, x_dict, y_dict):
        """
        根據實際距離對齊座標，讓在同一水平或垂直線上的站點整齊排列
        使用改進的對齊算法來解決座標偏移問題
        
        Args:
            x_dict (dict): 原始X座標字典
            y_dict (dict): 原始Y座標字典
            
        Returns:
            tuple: (aligned_x_dict, aligned_y_dict) 對齊後的座標字典
        """
        aligned_x_dict = x_dict.copy()
        aligned_y_dict = y_dict.copy()
        
        # 獲取所有座標點
        coords = [(key, x_dict[key], y_dict[key]) for key in x_dict.keys()]
        
        if len(coords) <= 1:
            return aligned_x_dict, aligned_y_dict
        
        # 使用更直接的對齊方法
        aligned_x_dict = self._direct_align_coordinates(aligned_x_dict, is_x_axis=True)
        aligned_y_dict = self._direct_align_coordinates(aligned_y_dict, is_x_axis=False)
        
        return aligned_x_dict, aligned_y_dict
    
    def _direct_align_coordinates(self, coord_dict, is_x_axis=True):
        """
        直接對齊座標，使用固定閾值和簡單聚類
        
        Args:
            coord_dict: 座標字典
            is_x_axis: 是否為X軸座標
            
        Returns:
            dict: 對齊後的座標字典
        """
        if len(coord_dict) <= 1:
            return coord_dict        # 根據對齊強度調整閾值
        # 特別針對座標差距為1-2的情況，確保能夠對齊
        base_threshold = self.alignment_threshold * (3.0 / self.alignment_strength)
        # 確保閾值足夠大以處理您的具體問題（31 vs 32，差距=1）
        effective_threshold = max(2.0, base_threshold)
        
        # 獲取所有座標值和對應鍵
        items = list(coord_dict.items())
        items.sort(key=lambda x: x[1])  # 按座標值排序
          # 使用簡單的距離聚類
        clusters = []
        if items:
            current_cluster = [items[0]]
            
            for i in range(1, len(items)):
                prev_coord = current_cluster[-1][1]
                curr_coord = items[i][1]
                distance = abs(curr_coord - prev_coord)
                  # print(f"Debug: Comparing {prev_coord} and {curr_coord}, distance = {distance}")
                
                # 如果距離小於閾值，加入當前聚類
                if distance <= effective_threshold:
                    current_cluster.append(items[i])
                    # print(f"Debug: Added to current cluster (distance {distance} <= threshold {effective_threshold})")
                else:
                    # 完成當前聚類，開始新聚類
                    clusters.append(current_cluster)
                    current_cluster = [items[i]]
                    # print(f"Debug: Started new cluster (distance {distance} > threshold {effective_threshold})")
            
            # 添加最後一個聚類
            clusters.append(current_cluster)
          # print(f"Debug: Final clusters: {clusters}")
        
        # 對每個聚類內的點使用相同座標（平均值）
        result_dict = coord_dict.copy()
        for cluster in clusters:
            if len(cluster) > 1:
                # 計算聚類內座標的平均值
                avg_coord = sum(item[1] for item in cluster) / len(cluster)
                
                # 將聚類內所有點設置為平均座標
                for key, _ in cluster:
                    result_dict[key] = avg_coord
        
        return result_dict
    
    def _smart_align_coordinates(self, coords, coord_dict, coordinate_index, is_x_axis=True):
        """
        使用智能聚類方法對座標進行對齊
        
        Args:
            coords: 所有座標點 [(key, x, y), ...]
            coord_dict: 要更新的座標字典
            coordinate_index: 座標索引 (1=x, 2=y)
            is_x_axis: 是否為X軸對齊
            
        Returns:
            dict: 更新後的座標字典
        """
        # 提取目標座標值
        coordinate_values = [coord[coordinate_index] for coord in coords]
        coordinate_keys = [coord[0] for coord in coords]
        
        # 使用自適應閾值進行聚類
        clusters = self._adaptive_clustering(coordinate_values, coordinate_keys)
        
        # 對每個聚類內的點使用相同座標（平均值）
        for cluster in clusters:
            if len(cluster) > 1:
                # 計算聚類內座標的加權平均值
                cluster_coords = [coord_dict[key] for key in cluster]
                avg_coord = sum(cluster_coords) / len(cluster_coords)
                
                # 將聚類內所有點設置為平均座標
                for key in cluster:
                    coord_dict[key] = avg_coord
        
        return coord_dict
    
    def _adaptive_clustering(self, values, keys):
        """
        自適應聚類算法，根據數據分佈動態調整閾值
        
        Args:
            values: 座標值列表
            keys: 對應的鍵值列表
            
        Returns:
            list: 聚類結果，每個聚類包含應該對齊的鍵值
        """
        if len(values) <= 1:
            return [[keys[0]]] if keys else []
        
        # 計算相鄰座標間的距離
        sorted_pairs = sorted(zip(values, keys))
        distances = []
        for i in range(1, len(sorted_pairs)):
            dist = abs(sorted_pairs[i][0] - sorted_pairs[i-1][0])
            distances.append(dist)
        
        if not distances:
            return [[key] for key in keys]
          # 使用動態閾值：取距離的統計特徵，並結合對齊強度
        distances.sort()
        median_dist = distances[len(distances) // 2]
        min_dist = min(distances)
        
        # 動態閾值：考慮對齊強度的影響
        # 對齊強度越大，閾值越小，對齊越嚴格
        base_threshold = max(min_dist * 2, median_dist * 0.3)
        dynamic_threshold = min(
            base_threshold / self.alignment_strength,  # 根據對齊強度調整
            self.alignment_threshold  # 但不超過原設定閾值
        )
        
        # 使用動態閾值進行聚類
        clusters = []
        current_cluster = [sorted_pairs[0][1]]  # 第一個點開始新聚類
        
        for i in range(1, len(sorted_pairs)):
            prev_value = sorted_pairs[i-1][0]
            curr_value = sorted_pairs[i][0]
            curr_key = sorted_pairs[i][1]
            
            # 如果距離小於動態閾值，加入當前聚類
            if abs(curr_value - prev_value) <= dynamic_threshold:
                current_cluster.append(curr_key)
            else:
                # 否則，完成當前聚類並開始新聚類
                clusters.append(current_cluster)
                current_cluster = [curr_key]
        
        # 添加最後一個聚類
        clusters.append(current_cluster)
        
        return clusters
        
    def _calculate_coordinates(self):
        """
        計算座標，支援格子地圖模式或實際座標模式（含對齊功能）
        
        Returns:
            tuple: (x_dict, y_dict) 座標字典
        """
        if self.use_grid_map:
            return self._calculate_grid_coordinates()
        else:
            # 使用實際座標，但進行對齊處理
            return self._align_coordinates_by_distance(self.x_dict, self.y_dict)
    
    def _calculate_grid_coordinates(self):
        """
        計算格子地圖座標
        
        Returns:
            tuple: (grid_x_dict, grid_y_dict) 格子座標字典
        """
        grid_x_dict = {}
        grid_y_dict = {}
        
        # 獲取所有座標點
        for addr_key in self.x_dict.keys():
            addr_x, addr_y = addr_key
            
            # 使用格子間距計算新座標
            grid_x = addr_x * self.grid_spacing
            grid_y = addr_y * self.grid_spacing
            
            grid_x_dict[addr_key] = grid_x
            grid_y_dict[addr_key] = grid_y
        
        return grid_x_dict, grid_y_dict
    def plot(self, ax):
        """繪製車輛地圖（使用傳入的 ax，不要建立新的 fig/ax）"""
        df_addr = self.df_addr
        # 計算顯示座標
        display_x_dict, display_y_dict = self._calculate_coordinates()

        if not self.use_grid_map:
            self.x_dict = display_x_dict
            self.y_dict = display_y_dict

        # 圖片尺寸由 PlotterBase 統一設定為 95×160 英寸，此處不再調整

        # 繪圖參數...
        square_side_length = 2
        x_offset_text = 0
        y_offset_text = -5
        text_y = {}
        obs_line_l = square_side_length
        obs_line_offset = 1 * square_side_length
        obs_line_w = 3
        obs_color = 'silver'
        arrow_head_width = 1
        arrow_line_width = .006
        arrow_offset = square_side_length/2 + 0.3
        arrow_l = 1.5

        # 使用傳入的 ax 繪製所有元素
        self._draw_address_points(
            ax, df_addr, display_x_dict, display_y_dict,
            square_side_length, x_offset_text, y_offset_text,
            text_y, obs_line_l, obs_line_offset, obs_line_w,
            obs_color, arrow_head_width, arrow_line_width,
            arrow_offset, arrow_l
        )

        self._draw_sections(
            ax, square_side_length, arrow_l,
            arrow_head_width, arrow_line_width,
            display_x_dict, display_y_dict
        )

        if self.invalid_address_ids or self.invalid_section_ids:
            self._draw_invalid_elements(ax)
            logging.info(f'已在地圖上標示 {len(self.invalid_address_ids)} 個異常地址和 {len(self.invalid_section_ids)} 個異常路段')

        # 不要在這裡呼叫 finalize_plot()（UI 會決定是否儲存或顯示）
        # 也不要建立新的 fig/ax（改為使用 PlotterBase.execute 建的 figure）

    def set_highlight_section_ids(self, section_id_list):
        """代理到父類設定 highlight_section_ids（確保呼叫安全）"""
        try:
            super().set_highlight_section_ids(section_id_list)
        except Exception:
            self.highlight_section_ids = set(section_id_list) if section_id_list else set()
        logging.info(f'已設定 {len(getattr(self, "highlight_section_ids", set()))} 個高亮路段')
    def get_figure(self):
        """回傳父類所設定的 figure（含高亮）"""
        return getattr(self, "figure", None)

    def _draw_address_points(
        self, ax, df_addr, x_dict, y_dict, 
        square_side_length, x_offset_text, y_offset_text, 
        text_y, obs_line_l, obs_line_offset, obs_line_w, 
        obs_color, arrow_head_width, arrow_line_width, 
        arrow_offset, arrow_l
    ):
        """
        繪製所有地址點
        
        Args:
            ax: matplotlib座標軸物件
            df_addr (DataFrame): 地址資料
            x_dict (dict): X座標字典
            y_dict (dict): Y座標字典
            其他參數: 繪圖設定參數
        """
        for i in range(len(df_addr)):
            addr_x = df_addr.loc[i, 'addr_x']
            addr_y = df_addr.loc[i, 'addr_y']
            
            # 使用調整後的座標，而不是原始座標
            coord_key = (addr_x, addr_y)
            if coord_key in x_dict and coord_key in y_dict:
                x = x_dict[coord_key]
                y = y_dict[coord_key]
            else:
                x = df_addr.loc[i, 'X']
                y = df_addr.loc[i, 'Y']
            
            # 判斷是否允許貨物旋轉
            isAllowCargoRotation = df_addr.loc[i, 'AllowCargoPosition'] == "0/90/180/270"
            
            # 根據不同的站點類型設定顏色
            if df_addr.loc[i, 'IsChargeStation']:
                c = 'red'  # 充電站
            elif pd.isna(df_addr.loc[i, 'StorageStationId']):
                c = 'lime'  # 非儲存站
            else:
                c = 'blue'  # 儲存站
            
            # 繪製方形
            square = patches.Rectangle(
                xy=(x - square_side_length/2, y - square_side_length/2),
                width=square_side_length, 
                height=square_side_length,
                edgecolor=c, 
                facecolor='none' if isAllowCargoRotation else c
            )
            ax.add_patch(square)

            # 新增座標文字標籤 (根據設定決定是否顯示)
            if self.showAddressId:
                # 根據IsNarrowStation決定文字顏色
                text_color = 'yellow' if df_addr.loc[i, 'IsNarrowStation'] else 'white'
                
                ax.text(
                    x + x_offset_text, 
                    y + y_offset_text, 
                    f"[1{addr_x:03d}{addr_y:03d}{0:02d}]", 
                    ha='center', 
                    va='bottom', 
                    fontsize=8,
                    color=text_color,  # 文字顏色根據IsNarrowStation決定
                    bbox=dict(facecolor='black', alpha=0.8, edgecolor='none', pad=1.5)  # 背景顏色設為黑色
                )

            # 新增 TagId 文字標籤 (根據設定和數據存在決定是否顯示)
            if self.showTagId and pd.notna(df_addr.loc[i, 'TagId']):
                # 檢查文字是否會與現有文字重疊
                overlap = False
                if df_addr.loc[i, 'addr_x'] - 1 > 0 and (df_addr.loc[i, 'addr_x'] - 1, df_addr.loc[i, 'addr_y']) in x_dict:
                    x2 = x_dict[(df_addr.loc[i, 'addr_x'] - 1, df_addr.loc[i, 'addr_y'])]
                    if abs(x - x2) < 12:  # 調整閾值
                        overlap = True

                ax.text(
                    x + x_offset_text,
                    y + y_offset_text * 1.5,  # Reduced from 2 to 1.6 to bring labels closer
                    f"{int(df_addr.loc[i, 'TagId'])}",
                    ha='center',
                    va='bottom',
                    fontsize=8,
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1.5)
                )
                text_y[(df_addr.loc[i, 'addr_x'], df_addr.loc[i, 'addr_y'])] = y + y_offset_text * 1.6

            # 繪製已知障礙物
            if pd.notna(df_addr.loc[i, 'KnownObstacle']):
                knownObstacle_list = []
                # Use isinstance to handle both Python float and numpy.float64
                if isinstance(df_addr.loc[i, 'KnownObstacle'], (float, np.floating)):
                    knownObstacle_list = [str(int(df_addr.loc[i, 'KnownObstacle']))]
                else:
                    knownObstacle_list = df_addr.loc[i, 'KnownObstacle'].split("/")
                
                for dir in knownObstacle_list:
                    draw_obstacle_line(
                        x, y, dir, 
                        obs_line_l, obs_line_offset, 
                        obs_line_w, obs_color
                    )            # 繪製允許車輛位置的箭頭
            if pd.notna(df_addr.loc[i, 'AllowVehiclePosition']):
                allowVehiclePosition_list = []
                # Use isinstance to handle both Python float and numpy.float64
                if isinstance(df_addr.loc[i, 'AllowVehiclePosition'], (float, np.floating)):
                    allowVehiclePosition_list = [str(int(df_addr.loc[i, 'AllowVehiclePosition']))]
                else:
                    allowVehiclePosition_list = df_addr.loc[i, 'AllowVehiclePosition'].split("/")
                
                for dir in allowVehiclePosition_list:
                    draw_arrow(
                        x, y, dir, 
                        arrow_l, arrow_offset, 
                        arrow_head_width, arrow_line_width, 
                        'gold', False
                    )

    def _draw_sections(self, ax, square_side_length, arrow_l, arrow_head_width, arrow_line_width, display_x_dict=None, display_y_dict=None):
        """
        繪製路段
        
        Args:
            ax: matplotlib座標軸物件
            square_side_length (float): 方形邊長
            arrow_l (float): 箭頭長度
            arrow_head_width (float): 箭頭頭部寬度
            arrow_line_width (float): 箭頭線條寬度
            display_x_dict (dict, optional): 顯示用的X座標字典，若為None則使用self.x_dict
            display_y_dict (dict, optional): 顯示用的Y座標字典，若為None則使用self.y_dict
        """
        df_section = self.df_section
        from_addr_x = self.from_addr_x
        to_addr_x = self.to_addr_x
        from_addr_y = self.from_addr_y
        to_addr_y = self.to_addr_y
        # 使用傳入的顯示座標字典，如果沒有傳入則使用原始座標
        x_dict = display_x_dict if display_x_dict is not None else self.x_dict
        y_dict = display_y_dict if display_y_dict is not None else self.y_dict

        # 重設已繪製路段集合
        self.drawn_sections = set()
        
        for i in range(len(df_section)):
            connection_offset = square_side_length + arrow_l + 0.5
            
            # 建立此路段的唯一識別符
            section_id_forward = f"{from_addr_x[i]},{from_addr_y[i]}->{to_addr_x[i]},{to_addr_y[i]}"
            
            # 檢查此路段是否已繪製過
            if section_id_forward in self.drawn_sections:
                logging.error(f"警告: 發現重複路段! 路段從 ({from_addr_x[i]},{from_addr_y[i]}) 到 ({to_addr_x[i]},{to_addr_y[i]})")
            else:
                # 將此路段加入已繪製路段集合
                self.drawn_sections.add(section_id_forward)
            
            # 檢查起點和終點是否都存在於地址資料中
            from_exists = ((self.df_addr['addr_x'] == from_addr_x[i]) & (self.df_addr['addr_y'] == from_addr_y[i])).any()
            to_exists = ((self.df_addr['addr_x'] == to_addr_x[i]) & (self.df_addr['addr_y'] == to_addr_y[i])).any()
            
            if not from_exists or not to_exists:
                logging.error(f"警告: 路徑段 {i} 的站點不存在 - 從 ({from_addr_x[i]},{from_addr_y[i]}) 到 ({to_addr_x[i]},{to_addr_y[i]})")
                continue  # 跳過此路徑段的繪製
            
            try:
                # 獲取兩端點和路徑本身的 AllowVehiclePosition
                from_allow_pos = str(self.df_addr.loc[self.df_addr['addr_x'] == from_addr_x[i]].loc[self.df_addr['addr_y'] == from_addr_y[i], 'AllowVehiclePosition'].values[0])
                to_allow_pos = str(self.df_addr.loc[self.df_addr['addr_x'] == to_addr_x[i]].loc[self.df_addr['addr_y'] == to_addr_y[i], 'AllowVehiclePosition'].values[0])
                section_allow_pos = str(df_section.loc[i, 'AllowVehiclePosition']) if pd.notna(df_section.loc[i, 'AllowVehiclePosition']) else "0/90/180/270"
                
                from_positions = from_allow_pos.split('/') if '/' in from_allow_pos else [from_allow_pos]
                to_positions = to_allow_pos.split('/') if '/' in to_allow_pos else [to_allow_pos]
                section_positions = section_allow_pos.split('/') if '/' in section_allow_pos else [section_allow_pos]
                
                # 判斷路徑方向
                section_direction = None
                warning = False
                x_from = x_dict[(from_addr_x[i], from_addr_y[i])]
                x_to = x_dict[(to_addr_x[i], to_addr_y[i])]
                y_from = y_dict[(from_addr_x[i], from_addr_y[i])]
                y_to = y_dict[(to_addr_x[i], to_addr_y[i])]
                logging.debug(f"讀取 ({from_addr_x[i]},{from_addr_y[i]}) -> ({to_addr_x[i]},{to_addr_y[i]})")
                logging.debug(f"對齊後座標 ({x_from},{y_from}) -> ({x_to},{y_to})")
                
                if x_from is None or x_to is None or y_from is None or y_to is None:
                    logging.error(f"警告: 路徑段 {i} 的座標無效 - 從 ({from_addr_x[i]},{from_addr_y[i]}) 到 ({to_addr_x[i]},{to_addr_y[i]})")
                    continue                # 橫向路徑 - 使用容忍度來判斷是否在同一條水平線上
                tolerance = 0.1  # 設定容忍度
                
                # 在格子地圖模式下，所有路徑都繪製，不管方向
                if self.use_grid_map:
                    # 格子地圖模式：直接計算兩點間的直線箭頭
                    x_start = x_from
                    y_start = y_from
                    dx = x_to - x_from
                    dy = y_to - y_from
                    
                    # 計算路徑方向（用於日誌）
                    if abs(dx) > abs(dy):
                        section_direction = '90' if dx > 0 else '270'
                    else:
                        section_direction = '0' if dy > 0 else '180'
                        
                    warning = False  # 格子地圖模式不檢查方向限制
                
                elif abs(y_from - y_to) <= tolerance:  # Y座標相近，視為橫向路徑
                    if x_from < x_to:
                        section_direction = '90'  # 向右
                        if ('90' not in from_positions or '90' not in to_positions or '90' not in section_positions):
                            warning = True
                            logging.error(f"警告: 路徑方向與允許方向不符 ({from_addr_x[i]},{from_addr_y[i]}) -> ({to_addr_x[i]},{to_addr_y[i]})")
                            logging.debug(f"方向: {section_direction}")
                            logging.debug(f"起點允許方向: {from_positions}")
                            logging.debug(f"終點允許方向: {to_positions}")
                            logging.debug(f"路段允許方向: {section_positions}")
                    else:
                        section_direction = '270'  # 向左
                        if ('270' not in from_positions or '270' not in to_positions or '270' not in section_positions):
                            warning = True
                            logging.error(f"警告: 路徑方向與允許方向不符 ({from_addr_x[i]},{from_addr_y[i]}) -> ({to_addr_x[i]},{to_addr_y[i]})")
                            logging.debug(f"方向: {section_direction}")
                            logging.debug(f"起點允許方向: {from_positions}")
                            logging.debug(f"終點允許方向: {to_positions}")
                            logging.debug(f"路段允許方向: {section_positions}")
                    
                    # 確保箭頭不會因為offset而超過終點
                    if abs(x_from - x_to) <= 2 * connection_offset:
                        connection_offset = abs(x_from - x_to) / 2.5

                    # 設定箭頭參數
                    if x_from < x_to:
                        x_start = x_from + connection_offset
                        y_start = y_dict[(from_addr_x[i], from_addr_y[i])]
                        dx = x_to - x_from - 2 * connection_offset
                        dy = 0
                    else:
                        x_start = x_from - connection_offset
                        y_start = y_dict[(from_addr_x[i], from_addr_y[i])]
                        dx = x_to - x_from + 2 * connection_offset
                        dy = 0                        
                elif abs(x_from - x_to) <= tolerance:  # X座標相近，視為縱向路徑
                    if y_from < y_to:
                        section_direction = '0'  # 向上
                        if ('0' not in from_positions or '0' not in to_positions or '0' not in section_positions):
                            warning = True
                            logging.error(f"警告: 路徑方向與允許方向不符 ({from_addr_x[i]},{from_addr_y[i]}) -> ({to_addr_x[i]},{to_addr_y[i]})")
                            logging.debug(f"方向: {section_direction}")
                            logging.debug(f"起點允許方向: {from_positions}")
                            logging.debug(f"終點允許方向: {to_positions}")
                            logging.debug(f"路段允許方向: {section_positions}")
                    else:
                        section_direction = '180'  # 向下
                        if ('180' not in from_positions or '180' not in to_positions or '180' not in section_positions):
                            warning = True
                            logging.error(f"警告: 路徑方向與允許方向不符 ({from_addr_x[i]},{from_addr_y[i]}) -> ({to_addr_x[i]},{to_addr_y[i]})")
                            logging.debug(f"方向: {section_direction}")
                            logging.debug(f"起點允許方向: {from_positions}")
                            logging.debug(f"終點允許方向: {to_positions}")
                            logging.debug(f"路段允許方向: {section_allow_pos}")

                    # 確保箭頭不會因為offset而超過終點
                    if abs(y_from - y_to) <= 2 * connection_offset:
                        connection_offset = abs(y_from - y_to) / 2.5                    # 設定箭頭參數
                    if y_from < y_to:
                        x_start = x_dict[(from_addr_x[i], from_addr_y[i])]
                        y_start = y_from + connection_offset
                        dx = 0
                        dy = y_to - y_from - 2 * connection_offset
                    else:
                        x_start = x_dict[(from_addr_x[i], from_addr_y[i])]
                        y_start = y_from - connection_offset
                        dx = 0
                        dy = y_to - y_from + 2 * connection_offset
                        
                else:
                    # 對角線路徑或其他方向的路徑
                    logging.debug(f"繪製對角線路徑 ({from_addr_x[i]},{from_addr_y[i]}) -> ({to_addr_x[i]},{to_addr_y[i]}), 座標差異: X={abs(x_from - x_to)}, Y={abs(y_from - y_to)}")
                    
                    # 計算直線箭頭
                    x_start = x_from
                    y_start = y_from
                    dx = x_to - x_from
                    dy = y_to - y_from
                    
                    # 計算主要方向
                    if abs(dx) > abs(dy):
                        section_direction = '90' if dx > 0 else '270'
                    else:
                        section_direction = '0' if dy > 0 else '180'
                  
                # 根據方向決定箭頭顏色：橫向(左右)使用藍色，縱向(上下)使用綠色
                if section_direction in ['90', '270']:  # 橫向：左右方向
                    arrow_color = 'blue'
                else:  # section_direction in ['0', '180']: 縱向：上下方向
                    arrow_color = 'blue'

                # 繪製箭頭，使用傳入的座標軸物件
                arrow = ax.arrow(x_start, y_start, dx, dy, head_width=arrow_head_width, width=arrow_line_width, color=arrow_color)
                
                # 如果有方向不符，繪製警告標誌
                if warning:
                    # 計算警告標誌的位置（箭頭中點）
                    warning_x = x_start + dx/2
                    warning_y = y_start + dy/2
                    ax.text(warning_x, warning_y + 1, '!', color='red', fontsize=20, fontweight='bold', ha='center', va='center')                # 顯示區段距離
                if self.showSectionDist and 'Distance' in df_section.columns and pd.notna(df_section.loc[i, 'Distance']):
                    dist = df_section.loc[i, 'Distance']

                    # Check if the section is vertical (up/down) and distance < 800cm
                    is_vertical = section_direction in ['0', '180']
                    is_short = dist < 700

                    if is_vertical and is_short:
                        # For vertical short paths, place label on the lower arrow
                        # Find the lower y position (min of y_start and y_start+dy)
                        dist_x = x_start + dx/2
                        dist_y = min(y_start, y_start + dy)  # Lower position
                        ax.text(dist_x, dist_y - 0.5, f"{int(dist)}cm", color='red', fontsize=8, ha='center', va='center')
                    else:
                        # Default: show at arrow midpoint
                        dist_x = x_start + dx/2
                        dist_y = y_start + dy/2
                        ax.text(dist_x, dist_y - 0.5, f"{int(dist)}cm", color='red', fontsize=8, ha='center', va='center')
            
            except IndexError as e:
                import traceback
                tb = traceback.extract_tb(e.__traceback__)
                filename, line, func, text = tb[-1]
                logging.error(f"索引錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
                continue  # 跳過此路徑段的繪製
            
            except Exception as e:
                import traceback
                tb = traceback.extract_tb(e.__traceback__)
                filename, line, func, text = tb[-1]
                logging.error(f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
                continue  # 跳過此路徑段的繪製

    def _draw_invalid_elements(self, ax):
        """
        在車輛地圖上標示所有異常元素
        
        Args:
            ax: matplotlib座標軸物件
        """
        # 繪製異常地址的驚嘆號
        for addr_id in self.invalid_address_ids:
            addr_rows = self.df_addr[self.df_addr['AddressId'] == addr_id]
            if not addr_rows.empty:
                x = addr_rows['X'].values[0]
                y = addr_rows['Y'].values[0]
                # 繪製紅色驚嘆號
                ax.text(x, y, '!', color='red', fontsize=20, fontweight='bold', ha='center', va='center')
                logging.info(f'在異常地址 {addr_id} ({x}, {y}) 處繪製驚嘆號')
        
        # 繪製異常路段的驚嘆號
        for section_id in self.invalid_section_ids:
            section_rows = self.df_section[self.df_section['SectionId'] == section_id]
            if not section_rows.empty:
                from_addr_id = section_rows['FromAddressId'].values[0]
                to_addr_id = section_rows['ToAddressId'].values[0]
                
                # 找到起點坐標
                from_addr_x = int(str(from_addr_id)[1:4])
                from_addr_y = int(str(from_addr_id)[4:7])
                from_x = self.x_dict.get((from_addr_x, from_addr_y))
                from_y = self.y_dict.get((from_addr_x, from_addr_y))
                
                # 找到終點坐標
                to_addr_x = int(str(to_addr_id)[1:4])
                to_addr_y = int(str(to_addr_id)[4:7])
                to_x = self.x_dict.get((to_addr_x, to_addr_y))
                to_y = self.y_dict.get((to_addr_x, to_addr_y))
                
                if from_x and from_y and to_x and to_y:
                    # 計算路段中點並繪製橘色驚嘆號
                    mid_x = (from_x + to_x) / 2
                    mid_y = (from_y + to_y) / 2
                    ax.text(mid_x, mid_y, '!', color='orange', fontsize=20, fontweight='bold', ha='center', va='center')
                    logging.info(f'在異常路段 {section_id} ({from_addr_id}->{to_addr_id}) 中點 ({mid_x}, {mid_y}) 處繪製驚嘆號')
    
    def get_figure(self):
        """回傳父類所設定的 figure（含高亮）"""
        return getattr(self, "figure", None)
