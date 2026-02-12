"""
貨物地圖繪製器模組
提供貨物地圖的繪製功能
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


class CargoMapPlotter(PlotterBase):
    """
    貨物地圖繪製器類別
    繪製包含貨物運輸路徑的地圖
    """
    def __init__(self):
        """初始化貨物地圖繪製器"""
        super().__init__()
        self.drawn_sections = set()  # 用於追蹤已繪製的路段

    def plot(self, ax):
        """繪製貨物地圖"""
        df_addr = self.df_addr
        x_dict = self.x_dict
        y_dict = self.y_dict

        # 設定繪圖視窗大小
        fig_width = max(x_dict.values()) / 10
        fig_height = max(y_dict.values()) / 10
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        
        # 繪圖參數
        square_side_length = 2
        x_offset_text = 0
        y_offset_text = -3
        text_y = {}
        
        # 障礙物線條參數
        obs_line_l = square_side_length
        obs_line_offset = 1 * square_side_length
        obs_line_w = 3
        obs_color = 'silver'
        
        # 箭頭參數
        arrow_head_width = 1
        arrow_line_width = .006
        arrow_offset = square_side_length/2 + 0.3
        arrow_l = 1.5

        # 繪製每個地址點
        self._draw_address_points(
            ax, df_addr, x_dict, y_dict, 
            square_side_length, x_offset_text, y_offset_text, 
            text_y, obs_line_l, obs_line_offset, obs_line_w, 
            obs_color, arrow_head_width, arrow_line_width, 
            arrow_offset, arrow_l
        )

        # 繪製路段
        # self._draw_sections(
        #     ax, square_side_length, arrow_l, 
        #     arrow_head_width, arrow_line_width
        # )
        
        # 繪製貨物方向
        self._draw_cargo_directions(ax, square_side_length)
        
        # 繪製異常元素的驚嘆號
        if self.invalid_address_ids or self.invalid_section_ids:
            self.draw_invalid_elements(ax)
            logging.info(f'已在地圖上標示 {len(self.invalid_address_ids)} 個異常地址和 {len(self.invalid_section_ids)} 個異常路段')

        # 完成繪圖
        finalize_plot(self.save_path, 'cargo_map_plot_validation.png')

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
        for i in range(len(self.df_addr)):
            addr_x = df_addr.loc[i, 'addr_x']
            addr_y = df_addr.loc[i, 'addr_y']
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
            
            # 繪製方形，使用傳入的座標軸物件
            square = patches.Rectangle(
                xy=(x - square_side_length/2, y - square_side_length/2),
                width=square_side_length, 
                height=square_side_length,
                edgecolor=c, 
                facecolor='none' if isAllowCargoRotation else c
            )
            ax.add_patch(square)

            # 新增座標文字標籤，使用傳入的座標軸物件
            ax.text(
                x + x_offset_text, 
                y + y_offset_text, 
                f"{addr_x},{addr_y}", 
                ha='center', 
                va='bottom', 
                fontsize=10
            )

            # 新增 TagId 文字標籤 (如果存在)
            if pd.notna(df_addr.loc[i, 'TagId']):
                # 檢查文字是否會與現有文字重疊
                overlap = False
                if df_addr.loc[i, 'addr_x'] - 1 > 0 and (df_addr.loc[i, 'addr_x'] - 1, df_addr.loc[i, 'addr_y']) in x_dict:
                    x2 = x_dict[(df_addr.loc[i, 'addr_x'] - 1, df_addr.loc[i, 'addr_y'])]
                    if abs(x - x2) < 12:  # 調整閾值
                        overlap = True

                if overlap and (df_addr.loc[i, 'addr_x'] - 1, df_addr.loc[i, 'addr_y']) in text_y and text_y[(df_addr.loc[i, 'addr_x'] - 1, df_addr.loc[i, 'addr_y'])] == y + y_offset_text * 2:
                    ax.text(
                        x + x_offset_text, 
                        y + y_offset_text * 3, 
                        f"{int(df_addr.loc[i, 'TagId'])}", 
                        ha='center', 
                        va='bottom', 
                        fontsize=10
                    )
                    text_y[(df_addr.loc[i, 'addr_x'], df_addr.loc[i, 'addr_y'])] = y + y_offset_text * 4
                else:
                    ax.text(
                        x + x_offset_text, 
                        y + y_offset_text * 2, 
                        f"{int(df_addr.loc[i, 'TagId'])}", 
                        ha='center', 
                        va='bottom', 
                        fontsize=10
                    )
                    text_y[(df_addr.loc[i, 'addr_x'], df_addr.loc[i, 'addr_y'])] = y + y_offset_text * 2
            else:
                ax.text(
                    x + x_offset_text, 
                    y + y_offset_text * 2, 
                    f"{df_addr.loc[i, 'TagId']}", 
                    ha='center', 
                    va='bottom', 
                    fontsize=10
                )

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
                        obs_line_w, obs_color,
                        ax=ax  # 傳遞座標軸物件
                    )

            # 繪製允許貨物方向的箭頭 (如果不允許自由旋轉)
            if not isAllowCargoRotation:
                p = df_addr.loc[i, 'AllowCargoPosition']
                # Use isinstance to handle both Python types and numpy types
                allowCargoRotationList = p.split("/") if isinstance(p, str) else [str(int(p))]
                for dir in allowCargoRotationList:
                    draw_arrow(
                        x, y, dir, 
                        arrow_l, arrow_offset, 
                        arrow_head_width, arrow_line_width, 
                        'green', True,
                        ax=ax  # 傳遞座標軸物件
                    )

    def _draw_cargo_directions(self, ax, square_side_length):
        """
        繪製路段上的貨物方向
        
        Args:
            ax: matplotlib座標軸物件
            square_side_length (float): 方形邊長
        """
        df_section = self.df_section
        from_addr_x = self.from_addr_x
        to_addr_x = self.to_addr_x
        from_addr_y = self.from_addr_y
        to_addr_y = self.to_addr_y
        x_dict = self.x_dict
        y_dict = self.y_dict

        # 箭頭參數
        small_arrow_head_width = 0.4  # 更小的箭頭頭部寬度
        small_arrow_line_width = 0.003  # 更細的箭頭線條
        small_arrow_l = 0.8  # 更短的箭頭長度
        
        # 定義四個方向的顏色
        direction_colors = {
            'right': 'red',      # 向右路徑的箭頭顏色
            'left': 'blue',      # 向左路徑的箭頭顏色
            'up': 'green',       # 向上路徑的箭頭顏色
            'down': 'purple'     # 向下路徑的箭頭顏色
        }
        
        for i in range(len(df_section)):
            
            # 若 AllowCargoPosition 是 nan，則跳過當前迭代
            if pd.isna(df_section.loc[i, 'AllowCargoPosition']):
                logging.warning(f"在ID ({df_section.loc[i, 'SectionId']}) section 無有效的方向值 (NaN)，箭頭繪製已略過")
                continue
                
            # 獲取路徑的 AllowCargoPosition
            section_cargo_pos = str(df_section.loc[i, 'AllowCargoPosition'])
            cargo_positions = section_cargo_pos.split('/') if '/' in section_cargo_pos else [section_cargo_pos]
            
            # 橫向路徑
            if from_addr_y[i] == to_addr_y[i]:
                x_from = x_dict[(from_addr_x[i], from_addr_y[i])]
                x_to = x_dict[(to_addr_x[i], to_addr_y[i])]
                y = y_dict[(from_addr_x[i], from_addr_y[i])]
                
                # 計算箭頭位置（路徑中點）
                x_mid = (x_from + x_to) / 2
                
                if x_from < x_to:  # 向右的路徑
                    arrow_color = direction_colors['right']
                    for dir in cargo_positions:
                        draw_arrow(
                            x_mid + square_side_length/2, y, dir,
                            small_arrow_l, 0,
                            small_arrow_head_width, small_arrow_line_width,
                            arrow_color, False,
                            ax=ax  # 傳遞座標軸物件
                        )
                else:  # 向左的路徑
                    arrow_color = direction_colors['left']
                    for dir in cargo_positions:
                        draw_arrow(
                            x_mid - square_side_length/2, y, dir,
                            small_arrow_l, 0,
                            small_arrow_head_width, small_arrow_line_width,
                            arrow_color, False,
                            ax=ax  # 傳遞座標軸物件
                        )
                    
            else:  # 縱向路徑
                x = x_dict[(from_addr_x[i], from_addr_y[i])]
                y_from = y_dict[(from_addr_x[i], from_addr_y[i])]
                y_to = y_dict[(to_addr_x[i], to_addr_y[i])]
                
                # 計算箭頭位置（路徑中點）
                y_mid = (y_from + y_to) / 2
                
                if y_from < y_to:  # 向上的路徑
                    arrow_color = direction_colors['up']
                    for dir in cargo_positions:
                        draw_arrow(
                            x, y_mid + square_side_length/2, dir,
                            small_arrow_l, 0,
                            small_arrow_head_width, small_arrow_line_width,
                            arrow_color, False,
                            ax=ax  # 傳遞座標軸物件
                        )
                else:  # 向下的路徑
                    arrow_color = direction_colors['down']
                    for dir in cargo_positions:
                        draw_arrow(
                            x, y_mid - square_side_length/2, dir,
                            small_arrow_l, 0,
                            small_arrow_head_width, small_arrow_line_width,
                            arrow_color, False,
                            ax=ax  # 傳遞座標軸物件
                        )

    def _draw_sections(self, ax, square_side_length, arrow_l, arrow_head_width, arrow_line_width):
        """
        繪製路段
        
        Args:
            ax: matplotlib座標軸物件
            square_side_length (float): 方形邊長
            arrow_l (float): 箭頭長度
            arrow_head_width (float): 箭頭頭部寬度
            arrow_line_width (float): 箭頭線條寬度
        """
        df_section = self.df_section
        from_addr_x = self.from_addr_x
        to_addr_x = self.to_addr_x
        from_addr_y = self.from_addr_y
        to_addr_y = self.to_addr_y
        x_dict = self.x_dict
        y_dict = self.y_dict
        
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
                # 獲取路徑本身的 AllowCargoPosition
                section_allow_pos = str(df_section.loc[i, 'AllowCargoPosition']) if pd.notna(df_section.loc[i, 'AllowCargoPosition']) else "0/90/180/270"
                section_positions = section_allow_pos.split('/') if '/' in section_allow_pos else [section_allow_pos]
                
                # 計算座標
                x_from = x_dict[(from_addr_x[i], from_addr_y[i])]
                x_to = x_dict[(to_addr_x[i], to_addr_y[i])]
                y_from = y_dict[(from_addr_x[i], from_addr_y[i])]
                y_to = y_dict[(to_addr_x[i], to_addr_y[i])]
                
                if x_from is None or x_to is None or y_from is None or y_to is None:
                    logging.error(f"警告: 路徑段 {i} 的座標無效 - 從 ({from_addr_x[i]},{from_addr_y[i]}) 到 ({to_addr_x[i]},{to_addr_y[i]})")
                    continue

                # 橫向路徑
                if y_from == y_to:
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
                        
                else:  # 縱向路徑
                    # 確保箭頭不會因為offset而超過終點
                    if abs(y_from - y_to) <= 2 * connection_offset:
                        connection_offset = abs(y_from - y_to) / 2.5

                    # 設定箭頭參數
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
                
                # # 繪製箭頭，使用傳入的座標軸物件
                # color = 'purple' if len(section_positions) < 4 else 'grey'
                # arrow = ax.arrow(x_start, y_start, dx, dy, head_width=arrow_head_width, width=arrow_line_width, color=color)
                  # # 顯示區段距離
                # if self.showSectionDist and 'Distance' in df_section.columns and pd.notna(df_section.loc[i, 'Distance']):
                #     dist = df_section.loc[i, 'Distance']
                #     # 顯示在箭頭中點
                #     dist_x = x_start + dx/2
                #     dist_y = y_start + dy/2
                #     ax.text(dist_x, dist_y - 0.5, f"{int(dist)}cm", color='black', fontsize=8, ha='center', va='center')
            
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
