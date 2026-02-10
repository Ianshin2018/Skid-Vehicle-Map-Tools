"""
視覺化工具模組
提供地圖繪製的通用視覺化功能
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np
import logging

# 設定 matplotlib 字型選項
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


def setup_figure(x_max, y_max, extra_width=0):
    """
    設定繪圖視窗大小
    
    Args:
        x_max (float): X 軸最大值
        y_max (float): Y 軸最大值
        extra_width (float, optional): 額外的寬度，預設為 0
        
    Returns:
        matplotlib.figure.Figure: 圖形物件
    """
    fig_width = x_max / 10 + extra_width
    fig_height = y_max / 10
    fig = plt.figure(figsize=(fig_width, fig_height))
    return fig


def draw_square(x, y, side_length, color, is_filled=False):
    """
    繪製正方形
    
    Args:
        x (float): 正方形中心的 X 座標
        y (float): 正方形中心的 Y 座標
        side_length (float): 正方形邊長
        color (str): 正方形邊框顏色
        is_filled (bool): 是否填充，預設為 False
        
    Returns:
        patches.Rectangle: 正方形物件
    """
    square = patches.Rectangle(
        xy=(x - side_length/2, y - side_length/2),
        width=side_length, 
        height=side_length,
        edgecolor=color, 
        facecolor=color if is_filled else 'none'
    )
    plt.gca().add_patch(square)
    return square


def draw_arrow(x, y, direction, length=1, offset=0, head_width=0.5, width=0.01, color='black', fill=False, ax=None):
    """
    繪製方向箭頭
    
    Args:
        x (float): 起點X座標
        y (float): 起點Y座標
        direction (str): 方向角度，支援 '0', '90', '180', '270'
        length (float): 箭頭長度
        offset (float): 起點偏移量
        head_width (float): 箭頭頭部寬度
        width (float): 箭頭線條寬度
        color (str): 箭頭顏色
        fill (bool): 是否填充箭頭頭部
        ax (matplotlib.axes.Axes, optional): 要繪製於其上的座標軸物件，若為None則使用目前的座標軸
    """
    if ax is None:
        ax = plt.gca()
        
    
    # 檢查 direction 是否為 NaN
    if pd.isna(direction):
        logging.warning(f"在座標 ({x}, {y}) 發現無效的方向值 (NaN)，箭頭繪製已略過")
        return
        
    # 方向角度轉換為弧度
    try:
        angle_deg = int(direction)
    except (ValueError, TypeError):
        logging.warning(f"在座標 ({x}, {y}) 發現無效的方向值 '{direction}'，箭頭繪製已略過")
        return
        
    angle_rad = np.deg2rad(angle_deg)
    
    # 計算偏移後的起點
    offset_x = offset * np.sin(angle_rad)
    offset_y = offset * np.cos(angle_rad)
    x_start = x + offset_x
    y_start = y + offset_y
    
    # 計算箭頭終點的相對位移
    dx = length * np.sin(angle_rad)
    dy = length * np.cos(angle_rad)
    
    # 繪製箭頭
    ax.arrow(x_start, y_start, dx, dy, head_width=head_width, width=width, color=color, length_includes_head=True)


def draw_obstacle_line(x, y, direction, length=1, offset=0.5, width=1, color='silver', ax=None):
    """
    繪製障礙物線條
    
    Args:
        x (float): 中心點X座標
        y (float): 中心點Y座標
        direction (str): 方向角度，支援 '0', '90', '180', '270'
        length (float): 線條長度
        offset (float): 起點偏移量
        width (float): 線條寬度
        color (str): 線條顏色
        ax (matplotlib.axes.Axes, optional): 要繪製於其上的座標軸物件，若為None則使用目前的座標軸
    """
    if ax is None:
        ax = plt.gca()
        
    # 方向角度轉換為弧度
    angle_deg = int(direction)
    angle_rad = np.deg2rad(angle_deg)
    
    # 根據方向計算垂直方向，用於線條繪製
    perp_angle_rad = angle_rad + np.pi / 2
    
    # 計算線條的兩端點
    half_length = length / 2
    x1 = x + half_length * np.sin(perp_angle_rad)
    y1 = y + half_length * np.cos(perp_angle_rad)
    x2 = x - half_length * np.sin(perp_angle_rad)
    y2 = y - half_length * np.cos(perp_angle_rad)
    
    # 加入偏移
    offset_x = offset * np.sin(angle_rad)
    offset_y = offset * np.cos(angle_rad)
    x1 += offset_x
    y1 += offset_y
    x2 += offset_x
    y2 += offset_y
    
    # 繪製線條
    ax.plot([x1, x2], [y1, y2], color=color, linewidth=width)


def finalize_plot(save_path, filename, show_plot=False):
    """
    完成繪圖，隱藏座標軸並儲存圖形
    
    Args:
        save_path (str): 儲存路徑
        filename (str): 檔案名稱
        show_plot (bool, optional): 是否顯示圖形，預設為 False
    """
    # 移除座標軸
    plt.axis('off')
    
    # 移除標籤和刻度
    plt.xticks([])
    plt.yticks([])
    
    # 儲存圖形
    plt.savefig(f"{save_path}/{filename}")
    
    # 顯示圖形（如果需要）
    if show_plot:
        plt.show()
