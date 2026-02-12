"""
地圖繪製使用者介面模組
提供地圖繪製的圖形使用者介面
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import os
import logging
import json
from datetime import datetime
import io
from PIL import Image
from PIL import ImageTk

from mapplot.plotters.vehicle_map_plotter import VehicleMapPlotter
from mapplot.plotters.cargo_map_plotter import CargoMapPlotter
from mapplot.utils.file_utils import validate_data_folder, load_map_data, load_and_validate_map_data

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # 取得 ui\map_plot_ui.py 所在目錄
DATA_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "data"))

# 配置檔案路徑
CONFIG_FILE_PATH = 'config.json'

# 自訂 logging handler 用於將日誌訊息顯示在 UI 上
class UILogHandler(logging.Handler):
    """
    自訂 logging handler 用於將日誌訊息顯示在 UI 上
    """
    def __init__(self, ui_instance):
        """初始化 UI 日誌處理器
        
        Args:
            ui_instance: UI 物件實例，必須具有 add_error 和 add_warning 方法
        """
        super().__init__()
        self.ui_instance = ui_instance
        
    def emit(self, record):
        """處理日誌記錄
        
        Args:
            record: 日誌記錄物件
        """
        msg = self.format(record)
        if record.levelno >= logging.ERROR:
            # 使用執行緒安全的方法更新 UI
            self.ui_instance.root.after(0, lambda: self.ui_instance.add_error(msg))
        elif record.levelno >= logging.WARNING:
            # 使用執行緒安全的方法更新 UI
            self.ui_instance.root.after(0, lambda: self.ui_instance.add_warning(msg))


class MapPlotUI:
    """
    地圖繪製使用者介面類別
    提供選擇資料夾和繪製地圖的圖形使用者介面
    """    
    def __init__(self, config=None):
        """初始化地圖繪製使用者介面
        
        Args:
            config (dict): 配置檔案內容，若為 None 則使用預設配置
        """
        self.root = tk.Tk()
        self._setup_window()
        self._image_scale = 0.2
        self._original_pil_img = None
        self._create_widgets()
        # 初始化配置
        if config is None:
            self.config = {
                "grid_map": {
                    "enabled": False,
                    "spacing": 15,
                    "alignment_strength": 2.0
                },
                "display_options": {
                    "show_section_distance": False,
                    "show_tag_id": True,
                    "show_address_id": True
                }
            }
        else:
            self.config = config
            
        self._create_plotters()
        self.data_folder = None
        # 儲存警報與異常資訊的列表
        self.warnings = []
        self.errors = []
        self._create_widgets()
        self._layout_widgets()
        self._setup_logging()  # 設定日誌 (在 UI 元件建立之後，這樣才能正確顯示日誌)
        
        # 根據配置設定 UI 狀態
        self._apply_config_to_ui()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)  # 關閉視窗時保存配置
        self.root.mainloop()
        
    def _setup_logging(self):
        """設定日誌"""
        # 基本設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # 加入自訂的 UI 日誌處理器
        ui_handler = UILogHandler(self)
        ui_handler.setLevel(logging.WARNING)  # 只處理警告及以上等級的訊息
        ui_handler.setFormatter(logging.Formatter('%(message)s'))  # 簡潔格式，因為 UI 已有時間戳記
        
        # 獲取根日誌記錄器並加入處理器
        root_logger = logging.getLogger()
        root_logger.addHandler(ui_handler)
    def _setup_window(self):
        """設定視窗屬性"""
        self.root.minsize(300, 200)
        self.root.title("地圖繪製工具")
        
    def _create_plotters(self):
        """建立繪圖器物件"""
        self.vehicle_map_plotter = VehicleMapPlotter(config=self.config)
        self.cargo_map_plotter = CargoMapPlotter()
    def _create_widgets(self):
        """建立使用者介面元件"""
        # self._create_buttons()  # 移除
        self._create_checkbutton()
        self._create_status_frames()

    def _create_status_frames(self):
        """建立警報與異常顯示區域"""
        # 建立框架容器
        self.status_frame = ttk.Frame(self.root)
        
        # 建立警報區域
        self.warning_frame = ttk.LabelFrame(self.status_frame, text="警報資訊")
        self.warning_text = tk.Text(self.warning_frame, width=40, height=5, wrap=tk.WORD, 
                                   background="#FFFFCC", foreground="#CC6600")
        self.warning_scrollbar = ttk.Scrollbar(self.warning_frame, orient=tk.VERTICAL, 
                                           command=self.warning_text.yview)
        self.warning_text.config(yscrollcommand=self.warning_scrollbar.set)
        
        # 建立異常區域
        self.error_frame = ttk.LabelFrame(self.status_frame, text="異常資訊")
        self.error_text = tk.Text(self.error_frame, width=40, height=5, wrap=tk.WORD, 
                                background="#FFCCCC", foreground="#990000")
        self.error_scrollbar = ttk.Scrollbar(self.error_frame, orient=tk.VERTICAL, 
                                         command=self.error_text.yview)
        self.error_text.config(yscrollcommand=self.error_scrollbar.set)
        
        # 設定唯讀狀態
        self.warning_text.config(state=tk.DISABLED)
        self.error_text.config(state=tk.DISABLED)
        
        # 建立畫布專用框架
        self.canvas_frame = ttk.Frame(self.status_frame)

        # 新增畫布元件
        self.output_canvas = tk.Canvas(self.canvas_frame, width=400, height=300, bg="white", scrollregion=(0, 0, 400, 300))

        # 新增垂直滾動條
        self.canvas_v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.output_canvas.yview)
        self.output_canvas.config(yscrollcommand=self.canvas_v_scrollbar.set)

        # 新增水平滾動條
        self.canvas_h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.output_canvas.xview)
        self.output_canvas.config(xscrollcommand=self.canvas_h_scrollbar.set)

        # 新增放大縮小按鈕
        self.zoom_in_btn = tk.Button(self.canvas_frame, text="+", width=2, command=self._zoom_in)
        self.zoom_out_btn = tk.Button(self.canvas_frame, text="-", width=2, command=self._zoom_out)
        self.output_canvas.bind("<Configure>", self._on_canvas_resize)
        self.output_canvas.bind("<ButtonPress-1>", self._start_move)
        self.output_canvas.bind("<B1-Motion>", self._move_canvas)

        # 新增滑鼠滾輪縮放支援（Windows / Mac / Linux）
        # Windows / Mac: <MouseWheel>， event.delta (正負)
        # Linux: <Button-4> (up), <Button-5> (down)
        self.output_canvas.bind("<MouseWheel>", self._on_mousewheel)      # Windows / macOS
        self.output_canvas.bind("<Button-4>", self._on_mousewheel)       # Linux scroll up
        self.output_canvas.bind("<Button-5>", self._on_mousewheel)       # Linux scroll down

        # 新增三個樓層按鈕
        self.floor_buttons = []
        floor_info = [
            ("1F", os.path.join(DATA_ROOT, "..", "Map", "Garmin1F")),
            ("2F", os.path.join(DATA_ROOT, "..", "Map", "Garmin2F")),
            ("3F", os.path.join(DATA_ROOT, "..", "Map", "Garmin3F")),
        ]
        for idx, (label, folder) in enumerate(floor_info):
            btn = tk.Button(
                self.canvas_frame,
                text=label,
                width=4,
                command=lambda f=folder: self.load_and_plot_vehicle_map(f)
            )
            self.floor_buttons.append(btn)
            # 不要在這裡 place

    def _start_move(self, event):
        self.output_canvas.scan_mark(event.x, event.y)

    def _move_canvas(self, event):
        self.output_canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_canvas_resize(self, event):
        """畫布大小變化時，將放大縮小按鈕固定在右上角"""
        # 右邊預留一點間距
        btn_y = 10
        btn_margin = 10
        btn_spacing = 5
        btn_width = self.zoom_in_btn.winfo_reqwidth()
        canvas_w = event.width
        self.zoom_in_btn.place(in_=self.output_canvas, x=canvas_w - btn_width*2 - btn_spacing - btn_margin, y=btn_y)
        self.zoom_out_btn.place(in_=self.output_canvas, x=canvas_w - btn_width - btn_margin, y=btn_y) 
        # 固定樓層按鈕在畫布左上角
        for idx, btn in enumerate(self.floor_buttons):
            btn.place(in_=self.output_canvas, x=10, y=10+idx*35)
    def _create_buttons(self):
        """建立按鈕"""
        self.buttons = {
            # 'select_folder': tk.Button(...),  # 已移除
            # 'vehicle_map': tk.Button(...),    # 已移除
            'cargo_map': tk.Button(
                self.root, 
                text="繪製貨物地圖", 
                command=self.plot_cargo_map, 
                width=15, 
                height=2
            )
        }
                
    def select_data_folder(self):
        """選擇地圖資料資料夾"""
        # 清除之前的警報和異常
        self.clear_status_messages()
        
        folder_path = filedialog.askdirectory(title="選擇包含地圖資料的資料夾")
        if not folder_path:
            return
            
        # 驗證資料夾是否包含所有必要的檔案
        is_valid, missing_files = validate_data_folder(folder_path)
        if not is_valid:
            error_msg = f"在所選資料夾中找不到以下必要檔案：{', '.join(missing_files)}"
            self.add_error(error_msg)
            messagebox.showerror("缺少檔案", error_msg)
            self.data_folder = None  # 確保清除無效的資料夾
            #self._update_button_states()  # 更新按鈕狀態
            return
        self.data_folder = folder_path
        logging.info(f"已選擇資料夾: {folder_path}")
        try:
            # 載入地圖路徑資料
            map_files = load_map_data(folder_path)
            logging.info("成功載入地圖檔案路徑")                # 載入並驗證所有CSV檔案的資料欄位
            try:
                # 這裡會自動驗證所有檔案的欄位是否符合預期
                validation_result = load_and_validate_map_data(folder_path, strict=False)
                  # 顯示驗證錯誤資訊                
                if 'validation_errors' in validation_result and validation_result['validation_errors']:
                    # 先顯示總結錯誤訊息
                    logging.error("資料驗證錯誤: 檔案驗證失敗，發現錯誤")
                    
                    # 顯示每個詳細錯誤，使用 logging 而不是直接呼叫 add_error
                    for i, error in enumerate(validation_result['validation_errors'], 1):
                        logging.error(f"錯誤: {error}")
                
                # 顯示驗證警告資訊
                if 'validation_warnings' in validation_result and validation_result['validation_warnings']:
                    # 先顯示總結警告訊息
                    logging.warning(f"資料驗證警告: 發現 {len(validation_result['validation_warnings'])} 個警告")
                    
                    # 顯示每個詳細警告，使用 logging 而不是直接呼叫 add_warning
                    for i, warning in enumerate(validation_result['validation_warnings'], 1):
                        logging.warning(f"驗證警告: {warning}")
                
                self.map_data = validation_result
                
                # 設定車輛地圖繪製器
                self.vehicle_map_plotter.p_addr = map_files['address']
                self.vehicle_map_plotter.p_section = map_files['section']
                self.vehicle_map_plotter.save_path = map_files['save_path']
                
                # 設定貨物地圖繪製器
                self.cargo_map_plotter.p_addr = map_files['address']
                self.cargo_map_plotter.p_section = map_files['section']
                self.cargo_map_plotter.save_path = map_files['save_path']
                self.cargo_map_plotter.p_port = map_files['port']
                self.cargo_map_plotter.p_shelf = map_files['shelf']
                                                
                logging.info(f"已選擇資料夾: {folder_path}")
                messagebox.showinfo("成功", "已成功載入所有必要檔案並驗證欄位格式")
                
            except ValueError as ve:
                import traceback
                tb = traceback.extract_tb(ve.__traceback__)
                filename, line, func, text = tb[-1]
                error_msg = f"數值錯誤: {str(ve)} | 檔案: {filename} | 行數: {line}"
                logging.error(f"{error_msg} | 類型: {type(ve).__name__}")
                self.add_error(error_msg)
                messagebox.showerror("資料欄位錯誤", f"資料欄位驗證失敗: {str(ve)}")
                self.data_folder = None
                #self._update_button_states()
                return
            
            #self._update_button_states()  # 更新按鈕狀態
        
        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            error_msg = f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line}"
            logging.error(f"{error_msg} | 類型: {type(e).__name__}")
            self.add_error(error_msg)
            messagebox.showerror("錯誤", f"載入資料時發生錯誤: {str(e)}")
            self.data_folder = None
            #self._update_button_states()

    def plot_vehicle_map(self):
        """繪製車輛地圖（支援顯示原始圖與加框圖兩圖層切換）"""
        try:
            if not self.data_folder:
                raise ValueError("請先選擇包含必要檔案的資料夾")

            invalid_address_ids = set()
            invalid_section_ids = set()
            if hasattr(self, 'map_data'):
                if 'invalid_vehicle_address_ids' in self.map_data:
                    invalid_address_ids = self.map_data['invalid_vehicle_address_ids']
                if 'invalid_vehicle_section_ids' in self.map_data:
                    invalid_section_ids = self.map_data['invalid_vehicle_section_ids']

            if invalid_address_ids or invalid_section_ids:
                self.vehicle_map_plotter.set_invalid_ids(invalid_address_ids, invalid_section_ids)
                logging.info(f"已標記 {len(invalid_address_ids)} 個異常地址和 {len(invalid_section_ids)} 個異常路段")

            self.vehicle_map_plotter.set_show_section_dist(self.show_section_dist.get() == '1')
            self.vehicle_map_plotter.set_show_tag_id(self.show_tag_id.get() == '1')
            self.vehicle_map_plotter.set_show_address_id(self.show_address_id.get() == '1')

            # highlight list — 請確保型態與 df_addr['AddressId'] 一致
            highlight_ids = ['106508700', ' 103505600']
            highlight_ids = [int(str(i).strip()) for i in highlight_ids]
            self.vehicle_map_plotter.set_highlight_address_ids(highlight_ids)

            # 範例：要高亮的 sectionId（請依你的 df_section['SectionId'] 型態調整）
            highlight_section_ids = ['10389', '10471']  # <-- 改成你要的 sectionId list
            # 轉型（若 SectionId 為整數）
            try:
                highlight_section_ids = [int(str(s).strip()) for s in highlight_section_ids]
            except Exception:
                # 若 SectionId 為字串就保留原樣
                highlight_section_ids = [str(s).strip() for s in highlight_section_ids]
            self.vehicle_map_plotter.set_highlight_section_ids(highlight_section_ids)

                # 執行繪圖（PlotterBase.execute 會建立 figure 並在該 figure 上繪製）
            self.vehicle_map_plotter.load()
            self.vehicle_map_plotter.execute()

            # 取得第一圖層（PIL Image）
            base_pil = self.vehicle_map_plotter.get_base_image()
            # 取得第二圖層（matplotlib Figure -> PIL Image）
            fig = self.vehicle_map_plotter.get_figure()
            overlay_pil = None
            if fig is not None:
                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                overlay_pil = Image.open(buf).convert("RGBA").copy()
                buf.close()

            # 儲存於 UI instance 以便在按鈕切換時使用
            self._base_pil_img = base_pil if base_pil is not None else overlay_pil
            self._overlay_pil_img = overlay_pil if overlay_pil is not None else self._base_pil_img

            # 建立切換按鈕（只建立一次）
            if not hasattr(self, "_show_base_btn"):
                self._show_base_btn = tk.Button(self.canvas_frame, text="原始圖", width=8,
                                               command=lambda: self.show_image_on_canvas(self._base_pil_img))
                self._show_highlight_btn = tk.Button(self.canvas_frame, text="加框圖", width=8,
                                                     command=lambda: self.show_image_on_canvas(self._overlay_pil_img))
                # 放在 canvas_frame 的第 2 行（canvas 與 scrollbars 已佔用 row0,row1）
                self._show_base_btn.grid(row=2, column=0, sticky="w", pady=5, padx=5)
                self._show_highlight_btn.grid(row=2, column=1, sticky="w", pady=5, padx=5)

            # 預設顯示 overlay（加框圖）
            if self._overlay_pil_img:
                self.show_image_on_canvas(self._overlay_pil_img)
            elif self._base_pil_img:
                self.show_image_on_canvas(self._base_pil_img)

            logging.info("車輛地圖繪製完成")

        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            logging.error(f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
            messagebox.showerror("錯誤", f"繪製車輛地圖時發生錯誤: {str(e)}")
    
    def plot_cargo_map(self):
        """繪製貨物地圖"""
        try:
            if not self.data_folder:
                raise ValueError("請先選擇包含必要檔案的資料夾")
                
            # 從已載入的地圖資料中獲取無效 ID
            invalid_address_ids = set()
            invalid_section_ids = set()
            
            # 從驗證結果中直接獲取無效 ID
            if hasattr(self, 'map_data'):
                if 'invalid_cargo_address_ids' in self.map_data:
                    invalid_address_ids = self.map_data['invalid_cargo_address_ids']
                if 'invalid_cargo_section_ids' in self.map_data:
                    invalid_section_ids = self.map_data['invalid_cargo_section_ids']
            
            # 設定繪圖器的異常 ID
            if invalid_address_ids or invalid_section_ids:
                this.cargo_map_plotter.set_invalid_ids(invalid_address_ids, invalid_section_ids)
                logging.info(f"已標記 {len(invalid_address_ids)} 個異常地址和 {len(invalid_section_ids)} 個異常路段")
                
            this.cargo_map_plotter.load()
            this.cargo_map_plotter.execute()
            logging.info("貨物地圖繪製完成")
            messagebox.showinfo("成功", "貨物地圖繪製完成")
            
        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            logging.error(f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
            messagebox.showerror("錯誤", f"繪製貨物地圖時發生錯誤: {str(e)}")

    def _create_checkbutton(self):
        """建立核取方塊"""
        self.show_section_dist = tk.StringVar(value='1')
      
        # 新增顯示 Tag ID 的勾選框
        self.show_tag_id = tk.StringVar(value='1')

        # 新增顯示 Address ID 的勾選框
        self.show_address_id = tk.StringVar(value='1')     
        
    def _apply_config_to_ui(self):
        """將配置檔案應用到 UI 元件"""
        # 配置已套用
        pass
        
    def _apply_config_to_plotter_removed(self):
        """(已移除) 原本用於套用格子地圖配置"""
        spacing = self.config.get("grid_map", {}).get("spacing", 10)
        if hasattr(self, 'vehicle_map_plotter') and self.vehicle_map_plotter:
            self.vehicle_map_plotter.set_grid_spacing(spacing)
        self.grid_spacing_label.config(text=f"格子間距: {spacing}")
        
        # 設定對齊強度
        strength = self.config["grid_map"]["alignment_strength"]
        if hasattr(self, 'vehicle_map_plotter') and self.vehicle_map_plotter:
            self.vehicle_map_plotter.set_alignment_strength(strength)
        self.alignment_label.config(text=f"對齊強度: {strength:.1f}")
        
        # 設定顯示選項
        if "display_options" in self.config:
            display_opts = self.config["display_options"]
            self.show_section_dist.set('1' if display_opts.get("show_section_distance", False) else '0')
            this.show_tag_id.set('1' if display_opts.get("show_tag_id", True) else '0')
            this.show_address_id.set('1' if display_opts.get("show_address_id", True) else '0')
        
    def _save_config(self):
        """儲存目前的配置到檔案"""
        try:
            # 更新配置物件
            self.config["grid_map"]["enabled"] = self.use_grid_map.get()
            self.config["grid_map"]["spacing"] = self.vehicle_map_plotter.get_grid_spacing()
            self.config["grid_map"]["alignment_strength"] = self.vehicle_map_plotter.get_alignment_strength()
            
            # 更新顯示選項配置
            if "display_options" not in self.config:
                self.config["display_options"] = {}
            self.config["display_options"]["show_section_distance"] = self.show_section_dist.get() == '1'
            this.config["display_options"]["show_tag_id"] = this.show_tag_id.get() == '1'
            this.config["display_options"]["show_address_id"] = this.show_address_id.get() == '1'
            
            # 寫入檔案
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logging.info("配置已成功儲存")
        except Exception as e:
            logging.error(f"儲存配置時發生錯誤: {str(e)}")
            
    def _on_closing(self):
        """關閉視窗時的處理"""
        #self._save_config()  # 保存配置
        self.root.destroy()  # 關閉視窗
        
    def _update_button_states(self):
        """更新按鈕啟用/停用狀態"""
        if self.data_folder:
            # 只控制 cargo_map 按鈕
            self.buttons['cargo_map'].config(state=tk.NORMAL)
        else:
            self.buttons['cargo_map'].config(state=tk.DISABLED)

    def _layout_widgets(self):
        """佈局使用者介面元件"""
        # 按鈕區域移除
        # for key, button in self.buttons.items():
        #     button.pack(pady=5)

        self.status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.error_frame.pack(fill=tk.X, padx=5, pady=5)
        self.error_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.error_text.config(height=7)  # 固定高度

        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.output_canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas_v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.canvas_frame.rowconfigure(0, weight=1)
        self.canvas_frame.columnconfigure(0, weight=1)

        self.output_canvas.update()
        canvas_w = self.output_canvas.winfo_width()
        self.zoom_in_btn.place(in_=self.output_canvas, x=canvas_w-50, y=10)
        self.zoom_out_btn.place(in_=self.output_canvas, x=canvas_w-25, y=10)
    def add_warning(self, message):
        """新增警報訊息

        Args:
            message (str): 警報訊息
        """
        if message:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.warnings.append(f"[{timestamp}] {message}")
            self._update_warning_display()

    def add_error(self, message):
        """新增異常訊息

        Args:
            message (str): 異常訊息
        """
        if message:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.errors.append(f"[{timestamp}] {message}")
            self._update_error_display()

    def _update_warning_display(self):
        """更新警報顯示區域"""
        self.warning_text.config(state=tk.NORMAL)
        self.warning_text.delete(1.0, tk.END)
        if self.warnings:
            self.warning_text.insert(tk.END, "\n".join(self.warnings))
        else:
            self.warning_text.insert(tk.END, "目前沒有警報資訊")
        self.warning_text.config(state=tk.DISABLED)
        self.warning_text.see(tk.END)  # 自動捲動到最新訊息

    def _update_error_display(self):
        """更新異常顯示區域"""
        self.error_text.config(state=tk.NORMAL)
        self.error_text.delete(1.0, tk.END)
        if self.errors:
            self.error_text.insert(tk.END, "\n".join(self.errors))
        else:
            self.error_text.insert(tk.END, "目前沒有異常資訊")
        self.error_text.config(state=tk.DISABLED)
        self.error_text.see(tk.END)  # 自動捲動到最新訊息
        
    def clear_status_messages(self):
        """清除所有警報與異常訊息"""
        self.warnings = []
        self.errors = []
        self._update_warning_display()
        self._update_error_display()

    def show_image_on_canvas(self, pil_img):
        """將 PIL 影像依照畫布大小與縮放比例縮放並致中顯示於 output_canvas 上"""
        self._original_pil_img = pil_img  # 儲存原始圖片
        self._draw_scaled_image()

    def _draw_scaled_image(self):
        if self._original_pil_img is None:
            return
        canvas_width = self.output_canvas.winfo_width()
        canvas_height = self.output_canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            self.output_canvas.update()
            canvas_width = self.output_canvas.winfo_width()
            canvas_height = self.output_canvas.winfo_height()
        img_w, img_h = self._original_pil_img.size
        scale = self._image_scale
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        resized_img = self._original_pil_img.resize((new_w, new_h), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(resized_img)
        self.output_canvas.delete("all")

        # 讓圖片左上角永遠在(0,0)，scrollregion設為圖片大小
        self.output_canvas.create_image(0, 0, anchor="nw", image=self._tk_img)
        self.output_canvas.config(scrollregion=(0, 0, new_w, new_h))


        if getattr(self, "_canvas_first_show", True):
            if new_w > canvas_width:
                self.output_canvas.xview_moveto((new_w - canvas_width) / 2 / new_w)
            else:
                self.output_canvas.xview_moveto(0)
            if new_h > canvas_height:
                self.output_canvas.yview_moveto((new_h - canvas_height) / 2 / new_h)
            else:
                self.output_canvas.yview_moveto(0)
            self._canvas_first_show = False  

    def zoom_image(self, in_out):
        """縮放畫布上的影像

        Args:
            in_out (int): 縮放因子，正值放大，負值縮小
        """
        if not hasattr(self, '_original_pil_img') or self._original_pil_img is None:
            return

        # 計算新縮放比例
        new_scale = self._image_scale + in_out * 0.1
        if new_scale <= 0.1:
            new_scale = 0.1  # 設定最小縮放比例

        # 重新計算影像大小
        new_w = int(self._original_pil_img.width * new_scale)
        new_h = int(self._original_pil_img.height * new_scale)
        resized_img = self._original_pil_img.resize((new_w, new_h), Image.LANCZOS)

        # 更新顯示影像
        self.show_image_on_canvas(resized_img)

        # 更新當前縮放比例
        self._image_scale = new_scale

    def _zoom_in(self):
        """放大影像"""
        self._image_scale = min(self._image_scale * 1.2, 5.0)
        self._draw_scaled_image()

    def _zoom_out(self):
        """縮小影像"""
        self._image_scale = max(self._image_scale / 1.2, 0.01)
        self._draw_scaled_image()

    def _load_highlights(self, folder_path):
        """
        嘗試從專案根目錄（與 main.py 同一層）讀取 highlights.csv，
        若找不到再到指定的 folder_path 搜尋。預期欄位: Floor, Type, Id
        """
        self.highlights_df = None
        try:
            # 專案根目錄（ui 的上層為 mapplot，mapplot 的上層為專案根）
            project_root = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))
            candidates = [
                os.path.join(project_root, "highlights.csv"),
                os.path.join(folder_path or "", "highlights.csv")
            ]
            csv_path = None
            for p in candidates:
                if p and os.path.isfile(p):
                    csv_path = p
                    break

            if not csv_path:
                logging.info(f"未找到 highlights.csv（搜尋路徑: {candidates}），跳過自動高亮設定")
                return

            import pandas as _pd
            df = _pd.read_csv(csv_path, dtype=str).fillna("")
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
            self.highlights_df = df
        except Exception as e:
            logging.warning(f"讀取 highlights.csv 失敗: {e}")
            self.highlights_df = None

    def _load_highlight_log(self, folder_path):
        """
        讀取 highlight log CSV：優先於專案根目錄（與 main.py 同層）搜尋，
        若找不到再於 folder_path 搜尋。標準欄位: start_date, number, addressid, sectionid
        """
        try:
            import pandas as _pd
            project_root = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))
            filenames = ("highlights.csv", "highlight_log.csv", "highlights_log.csv")
            csv_path = None
            # 優先在專案根搜尋，再在 folder_path 搜尋
            search_paths = []
            for fname in filenames:
                search_paths.append(os.path.join(project_root, fname))
            for fname in filenames:
                search_paths.append(os.path.join(folder_path or "", fname))

            for p in search_paths:
                if p and os.path.isfile(p):
                    csv_path = p
                    break

            if not csv_path:
                logging.info(f"未找到 highlight log CSV（搜尋: {search_paths}），跳過載入")
                self.highlight_log_df = None
                return

            df = _pd.read_csv(csv_path, dtype=str).fillna("")
            df.columns = [c.strip().lower() for c in df.columns]

            # 確保欄位存在，若缺則建立空欄
            for col in ("start_date", "number", "addressid", "sectionid"):
                if col not in df.columns:
                    df[col] = ""

            # 只保留必要欄並標準化為字串
            df = df[["start_date", "number", "addressid", "sectionid"]].astype(str).apply(lambda s: s.str.strip())
            self.highlight_log_df = df
            logging.info(f"從 {csv_path} 載入 highlight log，共 {len(df)} 筆記錄")
        except Exception as e:
            logging.warning(f"讀取 highlights CSV 失敗: {e}")
            self.highlight_log_df = None

    def _floor_from_folder(self, folder_path):
        """
        從資料夾路徑或名稱猜測樓層標籤，回傳 '1F'/'2F'/'3F' 或 None。
        主要用於 floor 按鈕傳入的 folder_path。
        """
        base = os.path.basename(folder_path).upper()
        p = folder_path.replace("\\", "/").upper()
        # 明確判斷
        if "1F" in base or "GARMIN1F" in base or "/1F" in p or base.endswith("1F"):
            return "1F"
        if "2F" in base or "GARMIN2F" in base or "/2F" in p or base.endswith("2F"):
            return "2F"
        if "3F" in base or "GARMIN3F" in base or "/3F" in p or base.endswith("3F"):
            return "3F"
        return None

    def _get_highlights_for_floor(self, floor_label):
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
        if getattr(self, "highlight_log_df", None) is None or floor_label is None:
            return addr_ids, sec_ids

        df = self.highlight_log_df.copy()

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

        logging.info(f"樓層 {floor_label} 取得高亮：{len(addr_ids)} addresses, {len(sec_ids)} sections")
        return addr_ids, sec_ids

    def load_fixed_folder(self, folder_path):
        """讀取指定資料夾"""
        self.clear_status_messages()
        self.data_folder = folder_path
        is_valid, missing_files = validate_data_folder(folder_path)
        if not is_valid:
            error_msg = f"在所選資料夾中找不到以下必要檔案：{', '.join(missing_files)}"
            self.add_error(error_msg)
            messagebox.showerror("缺少檔案", error_msg)
            self.data_folder = None
            return
        try:
            map_files = load_map_data(folder_path)
            validation_result = load_and_validate_map_data(folder_path, strict=False)
            if 'validation_errors' in validation_result and validation_result['validation_errors']:
                logging.error("資料驗證錯誤: 檔案驗證失敗，發現錯誤")
                for error in validation_result['validation_errors']:
                    logging.error(f"錯誤: {error}")
            if 'validation_warnings' in validation_result and validation_result['validation_warnings']:
                logging.warning(f"資料驗證警告: 發現 {len(validation_result['validation_warnings'])} 個警告")
                for warning in validation_result['validation_warnings']:
                    logging.warning(f"驗證警告: {warning}")
            self.map_data = validation_result
            self.vehicle_map_plotter.p_addr = map_files['address']
            self.vehicle_map_plotter.p_section = map_files['section']
            self.vehicle_map_plotter.save_path = map_files['save_path']
            self.cargo_map_plotter.p_addr = map_files['address']
            self.cargo_map_plotter.p_section = map_files['section']
            self.cargo_map_plotter.save_path = map_files['save_path']
            self.cargo_map_plotter.p_port = map_files['port']
            self.cargo_map_plotter.p_shelf = map_files['shelf']
            logging.info(f"已選擇資料夾: {folder_path}")
            # 載入 highlights.csv（若存在）
            self._load_highlights(folder_path)
            # 載入 highlight_log.csv（若存在）
            self._load_highlight_log(folder_path)
        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            error_msg = f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line}"
            logging.error(f"{error_msg} | 類型: {type(e).__name__}")
            self.add_error(error_msg)
            messagebox.showerror("錯誤", f"載入資料時發生錯誤: {str(e)}")
            self.data_folder = None

    def load_and_plot_vehicle_map(self, folder_path):
        """載入指定資料夾並直接繪製車輛地圖"""
        # 推斷樓層並記錄，供 plot_vehicle_map 使用
        self._current_floor = self._floor_from_folder(folder_path)
        self.load_fixed_folder(folder_path)
        # 若資料夾載入成功才繪圖
        if self.data_folder:
            self.plot_vehicle_map()

    def plot_vehicle_map(self):
        """繪製車輛地圖（支援樓層對應的 highlights.csv）"""
        try:
            if not self.data_folder:
                raise ValueError("請先選擇包含必要檔案的資料夾")

            invalid_address_ids = set()
            invalid_section_ids = set()
            if hasattr(self, 'map_data'):
                if 'invalid_vehicle_address_ids' in self.map_data:
                    invalid_address_ids = self.map_data['invalid_vehicle_address_ids']
                if 'invalid_vehicle_section_ids' in self.map_data:
                    invalid_section_ids = self.map_data['invalid_vehicle_section_ids']

            if invalid_address_ids or invalid_section_ids:
                self.vehicle_map_plotter.set_invalid_ids(invalid_address_ids, invalid_section_ids)
                logging.info(f"已標記 {len(invalid_address_ids)} 個異常地址和 {len(invalid_section_ids)} 個異常路段")

            self.vehicle_map_plotter.set_show_section_dist(self.show_section_dist.get() == '1')
            self.vehicle_map_plotter.set_show_tag_id(self.show_tag_id.get() == '1')
            self.vehicle_map_plotter.set_show_address_id(self.show_address_id.get() == '1')

            # 由 highlights.csv 決定本次要高亮的 address / section
            addr_ids, sec_ids = self._get_highlights_for_floor(getattr(self, "_current_floor", None))

            # 若沒有 highlights，仍可用 UI code 指定預設（可保留或移除）
            if not addr_ids:
                # 預設範例（如需移除請刪掉這三行）
                # addr_ids = ['106508700', '103505600']
                addr_ids = []
            if not sec_ids:
                sec_ids = []

            # 轉換 id 型態（若原本是字串數字轉為 int）
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

            self.vehicle_map_plotter.set_highlight_address_ids(cast_ids(addr_ids))
            self.vehicle_map_plotter.set_highlight_section_ids(cast_ids(sec_ids))

            # 執行繪圖
            self.vehicle_map_plotter.load()
            self.vehicle_map_plotter.execute()

            # 取得圖像並顯示（保持原有邏輯）
            base_pil = self.vehicle_map_plotter.get_base_image()
            fig = self.vehicle_map_plotter.get_figure()
            overlay_pil = None
            if fig is not None:
                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
                buf.seek(0)
                overlay_pil = Image.open(buf).convert("RGBA").copy()
                buf.close()

            self._base_pil_img = base_pil if base_pil is not None else overlay_pil
            self._overlay_pil_img = overlay_pil if overlay_pil is not None else self._base_pil_img

            if not hasattr(self, "_show_base_btn"):
                self._show_base_btn = tk.Button(self.canvas_frame, text="原始圖", width=8,
                                               command=lambda: self.show_image_on_canvas(self._base_pil_img))
                self._show_highlight_btn = tk.Button(self.canvas_frame, text="加框圖", width=8,
                                                     command=lambda: self.show_image_on_canvas(self._overlay_pil_img))
                self._show_base_btn.grid(row=2, column=0, sticky="w", pady=5, padx=5)
                self._show_highlight_btn.grid(row=2, column=1, sticky="w", pady=5, padx=5)

            if self._overlay_pil_img:
                self.show_image_on_canvas(self._overlay_pil_img)
            elif self._base_pil_img:
                self.show_image_on_canvas(self._base_pil_img)

            logging.info("車輛地圖繪製完成")

        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            logging.error(f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
            messagebox.showerror("錯誤", f"繪製車輛地圖時發生錯誤: {str(e)}")

    def _on_mousewheel(self, event):
        """
        以滑鼠游標為焦點縮放畫布上的影像（支援 Windows/macOS/Linux）。
        修正：使用螢幕滑鼠座標轉換為 canvas widget 座標，並以 (new_w - canvas_w)/(new_h - canvas_h)
        作為分母計算 xview/yview 的 fraction，避免縮放時跳到最左或最右。
        """
        if not hasattr(self, '_original_pil_img') or self._original_pil_img is None:
            return

        old_scale = getattr(self, "_image_scale", 1.0)
        factor = 1.1

        # 判斷滾輪方向
        delta = 0
        if hasattr(event, 'delta') and event.delta:
            delta = event.delta
        elif hasattr(event, 'num'):
            # Linux: Button-4 up, Button-5 down
            if event.num == 4:
                delta = 1
            elif event.num == 5:
                delta = -1

        if delta > 0:
            new_scale = min(old_scale * factor, 5.0)
        else:
            new_scale = max(old_scale / factor, 0.05)

        if abs(new_scale - old_scale) < 1e-9:
            return

        # 確保 widget 尺寸與 scrollregion 更新準確
        self.output_canvas.update_idletasks()

        # 取得滑鼠在螢幕的絕對位置，再轉為 canvas widget 的相對座標（更穩定）
        try:
            px = self.output_canvas.winfo_pointerx()
            py = self.output_canvas.winfo_pointery()
            widget_x = px - self.output_canvas.winfo_rootx()
            widget_y = py - self.output_canvas.winfo_rooty()
        except Exception:
            # fallback 使用 event.x/event.y
            widget_x = getattr(event, 'x', 0)
            widget_y = getattr(event, 'y', 0)

        # 取得 canvas 上對應的 canvas-coords（包含當前滾動位移）
        canvas_x = self.output_canvas.canvasx(widget_x)
        canvas_y = self.output_canvas.canvasy(widget_y)

        # 轉回原始 image 座標（以 old_scale）
        img_x = canvas_x / old_scale
        img_y = canvas_y / old_scale

        # 設定新比例並重繪
        self._image_scale = new_scale
        self._draw_scaled_image()

        # 重新確保 widget 與 image 更新
        self.output_canvas.update_idletasks()

        # 計算新的 canvas 座標（image 在 canvas 中的坐標）
        new_canvas_x = img_x * new_scale
        new_canvas_y = img_y * new_scale

        # 計算新尺寸與 viewport
        new_w = max(int(self._original_pil_img.width * new_scale), 1)
        new_h = max(int(self._original_pil_img.height * new_scale), 1)
        canvas_w = max(self.output_canvas.winfo_width(), 1)
        canvas_h = max(self.output_canvas.winfo_height(), 1)

        # 計算 left/top（希望可視區的左上座標）
        desired_left = new_canvas_x - widget_x
        desired_top = new_canvas_y - widget_y

        # 計算 fraction，分母使用 scrollable range (new_w - canvas_w)
        scrollable_w = max(new_w - canvas_w, 1)
        scrollable_h = max(new_h - canvas_h, 1)

        frac_x = desired_left / float(scrollable_w)
        frac_y = desired_top / float(scrollable_h)

        frac_x = self._clamp(frac_x, 0.0, 1.0)
        frac_y = self._clamp(frac_y, 0.0, 1.0)

        try:
            self.output_canvas.xview_moveto(frac_x)
        except Exception:
            pass
        try:
            self.output_canvas.yview_moveto(frac_y)
        except Exception:
            pass