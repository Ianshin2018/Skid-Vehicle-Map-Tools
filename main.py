"""
地圖繪製工具主程式入口點
"""
import logging
import os
import json
import tkinter.messagebox as messagebox
from ui.map_plot_ui import MapPlotUI

# 配置檔案路徑
CONFIG_FILE_PATH = 'config.json'

# 預設配置
DEFAULT_CONFIG = {
    "grid_map": {
        "enabled": False,
        "spacing": 10,
        "alignment_strength": 1.0
    }
}

def load_or_create_config():
    """載入或建立配置檔案"""
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logging.info("已載入配置檔")
                return config
        else:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
                logging.info("已建立預設配置檔")
                return DEFAULT_CONFIG
    except Exception as e:
        logging.error(f"載入配置檔時發生錯誤: {str(e)}")
        return DEFAULT_CONFIG

def main():
    """主程式入口點"""
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logging.info("啟動地圖繪製工具")
        
        # 載入配置
        #config = load_or_create_config()
        config = DEFAULT_CONFIG  # 使用預設配置，忽略檔案讀取
        
        # 建立及啟動 UI，傳入配置
        app = MapPlotUI(config)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        filename, line, func, text = tb[-1]
        error_msg = f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}"
        logging.error(error_msg)
        messagebox.showerror("啟動錯誤", f"啟動地圖繪製工具時發生錯誤: {str(e)}")
if __name__ == "__main__":
    main()
