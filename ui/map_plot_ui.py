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
from PIL import Image
from PIL import ImageTk

from mapplot.plotters.vehicle_map_plotter import VehicleMapPlotter
from mapplot.plotters.cargo_map_plotter import CargoMapPlotter
from mapplot.utils.file_utils import validate_data_folder, load_map_data, load_and_validate_map_data
from mapplot.utils.data_cache import get_data_cache

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

        # 初始化數據緩存
        self._data_cache = get_data_cache()
        
        # 預載所有樓層的底圖（使用後台線程異步加載）
        self._floor_cache = {}  # 儲存每個樓層的資料：{floor_label: {plotter, base_img, overlay_img, map_data, ...}}
        self._floor_loading_status = {}  # 儲存各樓層的加載狀態
        self._start_async_preload()

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
        self.root.title("打滑數據顯示工具-V1.0.0")
        
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
        """建立UI框架結構"""
        # === 建立主容器 ===
        self.main_container = ttk.Frame(self.root)

        # === 上方區塊 ===
        self.top_frame = ttk.Frame(self.main_container, height=30)

        # 狀態欄
        self.status_label = ttk.Label(self.top_frame, text="就緒", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        # 匯出按鈕
        self.export_btn = ttk.Button(self.top_frame, text="匯出顯示圖片", command=self._export_canvas_image)
        self.export_btn.pack(side=tk.RIGHT, padx=5, pady=5)

        # 進度條
        self.progress_bar = ttk.Progressbar(self.top_frame, mode='determinate', length=200)
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=5)

        # === 下方區塊 ===
        self.bottom_frame = ttk.Frame(self.main_container)

        # 下方區塊分為三列：左側(2) 中間(6) 右側(2)
        self.left_panel = ttk.LabelFrame(self.bottom_frame, text="日期篩選")
        self.center_panel = ttk.Frame(self.bottom_frame)
        self.right_panel = ttk.LabelFrame(self.bottom_frame, text="打滑次數排名")

        # === 右側面板：當前樓層打滑次數排名 ===
        self._skid_floor_label = ttk.Label(self.right_panel, text="請點選樓層按鈕")
        self._skid_floor_label.pack(pady=(5, 2), padx=5, anchor="w")

        _skid_frame = ttk.Frame(self.right_panel)
        _skid_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.skid_rank_tree = ttk.Treeview(
            _skid_frame,
            columns=("rank", "vehicle", "count"),
            show="headings",
            selectmode="none"
        )
        self.skid_rank_tree.heading("rank", text="名次")
        self.skid_rank_tree.heading("vehicle", text="車號")
        self.skid_rank_tree.heading("count", text="次數")
        self.skid_rank_tree.column("rank", width=40, anchor="center", stretch=False)
        self.skid_rank_tree.column("vehicle", width=55, anchor="center", stretch=False)
        self.skid_rank_tree.column("count", width=45, anchor="center", stretch=False)

        _skid_sb = ttk.Scrollbar(_skid_frame, orient=tk.VERTICAL, command=self.skid_rank_tree.yview)
        self.skid_rank_tree.config(yscrollcommand=_skid_sb.set)
        self.skid_rank_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        _skid_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # === 左側面板：日期選擇控件 ===
        # 標籤
        date_label = ttk.Label(self.left_panel, text="選擇日期:")
        date_label.pack(pady=(5, 2), padx=5, anchor="w")

        # 創建一個可滾動的框架來容納 checkbox
        # 外框架
        self.date_canvas = tk.Canvas(self.left_panel, borderwidth=0, highlightthickness=0, width=150)
        date_scrollbar = ttk.Scrollbar(self.left_panel, orient=tk.VERTICAL, command=self.date_canvas.yview)
        self.date_checkbox_frame = ttk.Frame(self.date_canvas)

        # 將內部框架嵌入到 canvas 中
        self.date_canvas_window = self.date_canvas.create_window((0, 0), window=self.date_checkbox_frame, anchor="nw")

        # 配置滾動
        self.date_canvas.configure(yscrollcommand=date_scrollbar.set)

        # 佈局
        self.date_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
        date_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # 綁定框架大小變化事件
        self.date_checkbox_frame.bind("<Configure>", self._on_date_frame_configure)
        self.date_canvas.bind("<Configure>", self._on_date_canvas_configure)

        # 綁定滑鼠滾輪事件
        self.date_canvas.bind("<MouseWheel>", self._on_date_list_mousewheel)  # Windows/Mac
        self.date_canvas.bind("<Button-4>", self._on_date_list_mousewheel)    # Linux scroll up
        self.date_canvas.bind("<Button-5>", self._on_date_list_mousewheel)    # Linux scroll down

        # 儲存 checkbox 變數的字典：{date_string: IntVar}
        self.date_checkboxes = {}

        # 按鈕框架
        date_btn_frame = ttk.Frame(self.left_panel)
        date_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        # 全選按鈕（點選樓層前禁用）
        self._date_select_all_btn = ttk.Button(date_btn_frame, text="全選", width=5,
                                               state=tk.DISABLED, command=self._select_all_dates)
        self._date_select_all_btn.pack(side=tk.LEFT, padx=1)

        # 清除選擇按鈕（點選樓層前禁用）
        self._date_clear_btn = ttk.Button(date_btn_frame, text="清除", width=5,
                                          state=tk.DISABLED, command=self._clear_date_selection)
        self._date_clear_btn.pack(side=tk.LEFT, padx=1)

        # 重新載入按鈕（點選樓層前禁用）
        self._date_reload_btn = ttk.Button(date_btn_frame, text="重載", width=5,
                                           state=tk.DISABLED, command=self._reload_highlights)
        self._date_reload_btn.pack(side=tk.LEFT, padx=1)

        # === 中間面板包含原有的所有功能 ===
        # 建立框架容器（原 status_frame）
        self.status_frame = ttk.Frame(self.center_panel)

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

        # 打滑門檻滑桿（放置於異常資訊與畫布之間）
        self._skid_slider_var = tk.IntVar(value=1)
        self._skid_slider_frame = ttk.Frame(self.status_frame)
        self._skid_slider = tk.Scale(
            self._skid_slider_frame,
            from_=1, to=1,
            orient=tk.HORIZONTAL,
            variable=self._skid_slider_var,
            label="重複打滑門檻 (address/section 重複率≥)",
            showvalue=True,
            command=self._on_skid_slider_changed,
            bg="#FFFDE7",
            relief=tk.GROOVE,
            font=("", 8),
        )
        self._skid_slider.pack(fill=tk.X, expand=True)

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
        self.output_canvas.bind("<ButtonRelease-3>", self._on_canvas_right_click)

        # 新增滑鼠滾輪縮放支援（Windows / Mac / Linux）
        # Windows / Mac: <MouseWheel>， event.delta (正負)
        # Linux: <Button-4> (up), <Button-5> (down)
        self.output_canvas.bind("<MouseWheel>", self._on_mousewheel)      # Windows / macOS
        self.output_canvas.bind("<Button-4>", self._on_mousewheel)       # Linux scroll up
        self.output_canvas.bind("<Button-5>", self._on_mousewheel)       # Linux scroll down

        # 新增三個樓層按鈕（預載完成前禁用）
        self.floor_buttons = {}
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
                state=tk.DISABLED,
                command=lambda f=folder: self.load_and_plot_vehicle_map(f)
            )
            self.floor_buttons[label] = btn
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
        for idx, btn in enumerate(self.floor_buttons.values()):
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
            #highlight_ids = ['106508700', ' 103505600']
            #highlight_ids = [int(str(i).strip()) for i in highlight_ids]
            #self.vehicle_map_plotter.set_highlight_address_ids(highlight_ids)

            # 範例：要高亮的 sectionId（請依你的 df_section['SectionId'] 型態調整）
            #highlight_section_ids = ['10389', '10471']  # <-- 改成你要的 sectionId list
            # 轉型（若 SectionId 為整數）
            #try:
                #highlight_section_ids = [int(str(s).strip()) for s in highlight_section_ids]
           # except Exception:
                # 若 SectionId 為字串就保留原樣
                #highlight_section_ids = [str(s).strip() for s in highlight_section_ids]
            #self.vehicle_map_plotter.set_highlight_section_ids(highlight_section_ids)

                # 執行繪圖（PlotterBase.execute 會建立 figure 並在該 figure 上繪製）
            self.vehicle_map_plotter.load()
            self.vehicle_map_plotter.execute()

            # 取得第一圖層（原始底圖）
            self._base_pil_img = self.vehicle_map_plotter.get_base_image()
            # 取得第二圖層（純方框圖層，透明背景）
            self._overlay_pil_img = self.vehicle_map_plotter.get_overlay_image()

            # 建立合成圖（底圖 + 方框）
            if self._base_pil_img and self._overlay_pil_img:
                # 確保兩個圖層尺寸一致
                if self._base_pil_img.size != self._overlay_pil_img.size:
                    # 調整 overlay 尺寸以匹配 base
                    self._overlay_pil_img = self._overlay_pil_img.resize(self._base_pil_img.size, Image.LANCZOS)

                # 合成圖層：底圖 + 方框
                self._combined_pil_img = Image.new("RGBA", self._base_pil_img.size)
                self._combined_pil_img.paste(self._base_pil_img, (0, 0))
                self._combined_pil_img.paste(self._overlay_pil_img, (0, 0), self._overlay_pil_img)
            else:
                self._combined_pil_img = self._base_pil_img

            # 預設顯示合成圖（加框圖）
            if self._combined_pil_img:
                self.show_image_on_canvas(self._combined_pil_img)
            elif self._base_pil_img:
                self.show_image_on_canvas(self._base_pil_img)

            logging.info("車輛地圖繪製完成")

        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            logging.error(f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
            messagebox.showerror("錯誤", f"繪製車輛地圖時發生錯誤: {str(e)}")
    
    def _on_canvas_right_click(self, event):
        """右鍵點擊畫布：若點到高亮方框則顯示 ID 與路徑資訊"""
        if not self._get_selected_dates():
            return
        plotter = getattr(self, 'vehicle_map_plotter', None)
        if not plotter:
            return
        hit_areas = getattr(plotter, 'highlight_hit_areas', [])
        xlim = getattr(plotter, '_ax_xlim', None)
        ylim = getattr(plotter, '_ax_ylim', None)
        base_img = getattr(self, '_base_pil_img', None)
        if not hit_areas or not xlim or not ylim or not base_img:
            return

        # canvas 座標（含滾動偏移）→ 全解析度圖片像素座標
        cx = self.output_canvas.canvasx(event.x)
        cy = self.output_canvas.canvasy(event.y)
        scale = self._image_scale
        img_px_x = cx / scale
        img_px_y = cy / scale

        # 圖片像素 → matplotlib data 座標（線性映射）
        img_w, img_h = base_img.size
        data_x = xlim[0] + (img_px_x / img_w) * (xlim[1] - xlim[0])
        data_y = ylim[1] - (img_px_y / img_h) * (ylim[1] - ylim[0])

        # 尋找第一個包含點擊座標的方框
        clicked = None
        for area in hit_areas:
            if area['xmin'] <= data_x <= area['xmax'] and area['ymin'] <= data_y <= area['ymax']:
                clicked = area
                break

        if clicked:
            self._show_highlight_popup(event, clicked)

    def _show_highlight_popup(self, event, info):
        """在點擊位置旁顯示高亮方框資訊的浮動小視窗（4秒後自動關閉）"""
        # 關閉上一個（若存在）
        prev = getattr(self, '_highlight_popup', None)
        if prev:
            try:
                prev.destroy()
            except Exception:
                pass

        if info['type'] == 'address':
            text = f"Address ID：{info['id']}"
        else:
            text = (f"Section ID：{info['id']}\n"
                    f"起點 (From)：{info['from_addr']}\n"
                    f"終點 (To)：{info['to_addr']}")

        popup = tk.Toplevel(self.root)
        popup.wm_overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

        frame = tk.Frame(popup, bd=1, relief=tk.SOLID, bg="#FFFDE7")
        frame.pack()
        tk.Label(frame, text=text, bg="#FFFDE7", fg="#333333",
                 padx=10, pady=6, justify=tk.LEFT,
                 font=("Microsoft YaHei", 9)).pack()

        self._highlight_popup = popup
        popup.after(4000, lambda: popup.destroy() if popup.winfo_exists() else None)

    def _toggle_vehicle_highlight(self):
        """切換車輛地圖的高亮方框顯示"""
        has_dates = bool(self._get_selected_dates()) if hasattr(self, 'date_checkboxes') else False
        if self._show_highlight_var.get() == 1 and has_dates:
            # 勾選且有選擇日期：顯示合成圖（底圖 + 方框）
            if hasattr(self, '_combined_pil_img') and self._combined_pil_img:
                self.show_image_on_canvas(self._combined_pil_img)
        else:
            # 取消勾選或無日期：顯示底圖（含施工區域，不含高亮）
            if hasattr(self, '_base_pil_img') and self._base_pil_img:
                self.show_image_on_canvas(self._base_pil_img)

    def plot_cargo_map(self):
        """繪製貨物地圖(支援顯示原始圖與加框圖兩圖層切換)"""
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
                self.cargo_map_plotter.set_invalid_ids(invalid_address_ids, invalid_section_ids)
                logging.info(f"已標記 {len(invalid_address_ids)} 個異常地址和 {len(invalid_section_ids)} 個異常路段")

            # 執行繪圖(PlotterBase.execute 會建立 figure 並在該 figure 上繪製)
            self.cargo_map_plotter.load()
            self.cargo_map_plotter.execute()

            # 取得第一圖層（原始底圖）
            self._cargo_base_pil_img = self.cargo_map_plotter.get_base_image()
            # 取得第二圖層（純方框圖層，透明背景）
            self._cargo_overlay_pil_img = self.cargo_map_plotter.get_overlay_image()

            # 建立合成圖（底圖 + 方框）
            if self._cargo_base_pil_img and self._cargo_overlay_pil_img:
                # 確保兩個圖層尺寸一致
                if self._cargo_base_pil_img.size != self._cargo_overlay_pil_img.size:
                    # 調整 overlay 尺寸以匹配 base
                    self._cargo_overlay_pil_img = self._cargo_overlay_pil_img.resize(self._cargo_base_pil_img.size, Image.LANCZOS)

                # 合成圖層：底圖 + 方框
                self._cargo_combined_pil_img = Image.new("RGBA", self._cargo_base_pil_img.size)
                self._cargo_combined_pil_img.paste(self._cargo_base_pil_img, (0, 0))
                self._cargo_combined_pil_img.paste(self._cargo_overlay_pil_img, (0, 0), self._cargo_overlay_pil_img)
            else:
                self._cargo_combined_pil_img = self._cargo_base_pil_img

            # 建立圖層切換 checkbutton（只建立一次）
            if not hasattr(self, "_cargo_show_highlight_var"):
                self._cargo_show_highlight_var = tk.IntVar(value=1)  # 預設勾選，顯示方框
                self._cargo_show_highlight_check = tk.Checkbutton(
                    self.canvas_frame,
                    text="顯示高亮方框",
                    variable=self._cargo_show_highlight_var,
                    command=self._toggle_cargo_highlight
                )
                # 放在 canvas_frame 的第 2 行
                self._cargo_show_highlight_check.grid(row=2, column=0, sticky="w", pady=5, padx=5)

            # 預設顯示合成圖（加框圖）
            if self._cargo_combined_pil_img:
                self.show_image_on_canvas(self._cargo_combined_pil_img)
            elif self._cargo_base_pil_img:
                self.show_image_on_canvas(self._cargo_base_pil_img)

            logging.info("貨物地圖繪製完成")

        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            logging.error(f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line} | 類型: {type(e).__name__}")
            messagebox.showerror("錯誤", f"繪製貨物地圖時發生錯誤: {str(e)}")

    def _toggle_cargo_highlight(self):
        """切換貨物地圖的高亮方框顯示"""
        if self._cargo_show_highlight_var.get() == 1:
            # 勾選：顯示合成圖（底圖 + 方框）
            if hasattr(self, '_cargo_combined_pil_img') and self._cargo_combined_pil_img:
                self.show_image_on_canvas(self._cargo_combined_pil_img)
        else:
            # 取消勾選：只顯示底圖
            if hasattr(self, '_cargo_base_pil_img') and self._cargo_base_pil_img:
                self.show_image_on_canvas(self._cargo_base_pil_img)

    def _create_checkbutton(self):
        """建立核取方塊"""
        self.show_section_dist = tk.StringVar(value='1')
      
        # 新增顯示 Tag ID 的勾選框
        self.show_tag_id = tk.StringVar(value='1')

        # 新增顯示 Address ID 的勾選框
        self.show_address_id = tk.StringVar(value='1')     
        
        # 新增顯示施工區域的勾選框（預設勾選）
        self.show_zone = tk.IntVar(value=1)
        
        # 新增顯示高亮方框的勾選框（預設勾選）
        self.show_highlight = tk.IntVar(value=1)
        
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
            self.show_tag_id.set('1' if display_opts.get("show_tag_id", True) else '0')
            self.show_address_id.set('1' if display_opts.get("show_address_id", True) else '0')
        
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
            self.config["display_options"]["show_tag_id"] = self.show_tag_id.get() == '1'
            self.config["display_options"]["show_address_id"] = self.show_address_id.get() == '1'
            
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
        # === 主容器佈局：上下兩個區塊 ===
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # 上方區塊（固定高度）
        self.top_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        # 下方區塊（可擴展）
        self.bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        # === 下方區塊的三列佈局：2:6:2 ===
        # 左側面板（權重 2）
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # 中間面板（權重 6）- 包含所有現有功能
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=5)

        # 右側面板（權重 2）
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        # 設定列權重（使其可垂直擴展）
        self.bottom_frame.rowconfigure(0, weight=1)

        # 設定欄權重（比例 2:6:2）
        self.bottom_frame.columnconfigure(0, weight=2)
        self.bottom_frame.columnconfigure(1, weight=6)
        self.bottom_frame.columnconfigure(2, weight=2)

        # === 中間面板內的原有功能佈局 ===
        self.status_frame.pack(fill=tk.BOTH, expand=True)
        # 異常資訊欄已隱藏（功能保留，移除 pack 即不顯示）
        # self.error_frame.pack(fill=tk.X, padx=5, pady=5)
        # self.error_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # self.error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # self.error_text.config(height=7)

        # 打滑門檻滑桿（異常資訊下方、畫布上方）—— 初始隱藏，點選樓層後顯示

        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
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

    def _load_zone_for_floor(self, folder_path):
        """載入樓層的施工區域資料並產生圖層

        Args:
            folder_path: 樓層資料夾路徑

        Returns:
            PIL Image or None: 施工區域圖層（透明背景）
        """
        import pandas as pd
        import io

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
            if not hasattr(self, 'vehicle_map_plotter') or self.vehicle_map_plotter is None:
                return None

            x_dict = getattr(self.vehicle_map_plotter, 'x_dict', {})
            y_dict = getattr(self.vehicle_map_plotter, 'y_dict', {})

            if not x_dict or not y_dict:
                logging.warning("vehicle_map_plotter 沒有座標資料")
                return None

            # 建立透明圖層繪製 zone 方框
            import matplotlib.pyplot as plt

            # 獲取 figure 尺寸
            fig_size = (10, 8)  # 預設尺寸
            if hasattr(self.vehicle_map_plotter, 'figure') and self.vehicle_map_plotter.figure:
                fig_size = self.vehicle_map_plotter.figure.get_size_inches()

            # 建立透明 figure
            zone_fig, zone_ax = plt.subplots(figsize=fig_size)

            # 設定座標範圍（從 plotter 獲取）
            if hasattr(self.vehicle_map_plotter, 'figure') and self.vehicle_map_plotter.figure.axes:
                orig_ax = self.vehicle_map_plotter.figure.axes[0]
                zone_ax.set_xlim(orig_ax.get_xlim())
                zone_ax.set_ylim(orig_ax.get_ylim())
                zone_ax.set_aspect(orig_ax.get_aspect())

            # 隱藏座標軸
            zone_ax.set_axis_off()
            zone_ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
            for spine in zone_ax.spines.values():
                spine.set_visible(False)

            # 繪製淡藍色方框
            from matplotlib.patches import Rectangle
            
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

    def _load_zone_section_for_floor(self, folder_path):
        """載入樓層的施工區域路段資料並產生圖層

        Args:
            folder_path: 樓層資料夾路徑

        Returns:
            PIL Image or None: 施工區域路段圖層（透明背景）
        """
        import pandas as pd
        import io

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
            if not hasattr(self, 'vehicle_map_plotter') or self.vehicle_map_plotter is None:
                return None

            x_dict = getattr(self.vehicle_map_plotter, 'x_dict', {})
            y_dict = getattr(self.vehicle_map_plotter, 'y_dict', {})

            if not x_dict or not y_dict:
                logging.warning("vehicle_map_plotter 沒有座標資料")
                return None

            # 建立透明圖層繪製 zone section 方框
            import matplotlib.pyplot as plt

            # 獲取 figure 尺寸
            fig_size = (10, 8)  # 預設尺寸
            if hasattr(self.vehicle_map_plotter, 'figure') and self.vehicle_map_plotter.figure:
                fig_size = self.vehicle_map_plotter.figure.get_size_inches()

            # 建立透明 figure
            zone_fig, zone_ax = plt.subplots(figsize=fig_size)

            # 設定座標範圍（從 plotter 獲取）
            if hasattr(self.vehicle_map_plotter, 'figure') and self.vehicle_map_plotter.figure.axes:
                orig_ax = self.vehicle_map_plotter.figure.axes[0]
                zone_ax.set_xlim(orig_ax.get_xlim())
                zone_ax.set_ylim(orig_ax.get_ylim())
                zone_ax.set_aspect(orig_ax.get_aspect())

            # 隱藏座標軸
            zone_ax.set_axis_off()
            zone_ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
            for spine in zone_ax.spines.values():
                spine.set_visible(False)

            # 繪製淡藍色路段方框
            from matplotlib.patches import Rectangle, FancyArrowPatch
            import matplotlib.patches as mpatches
            
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

    def _start_async_preload(self):
        """啟動後台線程異步加載所有樓層"""
        import threading

        # 更新狀態
        self._update_status("開始預載樓層底圖...")
        self.progress_bar['value'] = 0
        self.progress_bar['maximum'] = 3

        # 在後台線程中執行預加載
        thread = threading.Thread(target=self._preload_floor_maps_async, daemon=True)
        thread.start()

    def _update_status(self, message):
        """線程安全地更新狀態欄"""
        if hasattr(self, 'status_label'):
            self.root.after(0, lambda: self.status_label.config(text=message))

    def _update_progress(self, value):
        """線程安全地更新進度條"""
        if hasattr(self, 'progress_bar'):
            self.root.after(0, lambda: self.progress_bar.config(value=value))

    def _preload_floor_maps_async(self):
        """在後台線程中預載所有樓層的底圖（優化版：使用快取 + 跳過驗證）"""
        import time
        start_time = time.time()
        
        try:
            logging.info("開始預載所有樓層的底圖...")

            # 預先載入 highlight_log.csv（所有樓層共用）
            project_root = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))
            self._load_highlight_log(project_root)

            # 定義三個樓層的資料夾路徑
            floor_configs = [
                ("1F", os.path.join(DATA_ROOT, "..", "Map", "Garmin1F")),
                ("2F", os.path.join(DATA_ROOT, "..", "Map", "Garmin2F")),
                ("3F", os.path.join(DATA_ROOT, "..", "Map", "Garmin3F")),
            ]

            loaded_count = 0
            for floor_label, folder_path in floor_configs:
                self._update_status(f"正在載入 {floor_label} 底圖...")
                try:
                    # 驗證資料夾
                    is_valid, missing_files = validate_data_folder(folder_path)
                    if not is_valid:
                        logging.warning(f"樓層 {floor_label} 資料夾驗證失敗，跳過預載")
                        self._floor_loading_status[floor_label] = 'failed'
                        loaded_count += 1
                        self._update_progress(loaded_count)
                        continue

                    # 優化：嘗試從快取獲取數據，避免重複讀取 CSV
                    map_data = None
                    if hasattr(self, '_data_cache') and self._data_cache:
                        map_data = self._data_cache.get_cached_data(folder_path)
                    
                    if map_data is None:
                        # 快取未命中，手動讀取 CSV（使用輕量級模式，跳過驗證）
                        map_files = load_map_data(folder_path)
                        # 使用 lightweight=True 跳過昂貴的驗證過程
                        validation_result = load_and_validate_map_data(folder_path, strict=False, lightweight=True)
                        map_data = validation_result
                        
                        # 存入快取
                        if hasattr(self, '_data_cache') and self._data_cache:
                            self._data_cache.load_csv_data(folder_path)
                            self._data_cache.set_validation_result(folder_path, validation_result)
                    else:
                        # 快取命中，使用已載入的數據
                        validation_result = map_data
                        map_files = load_map_data(folder_path)
                        logging.info(f"樓層 {floor_label} 使用快取數據")

                    # 創建該樓層專用的 plotter
                    floor_plotter = VehicleMapPlotter(config=self.config)
                    floor_plotter.p_addr = map_files['address']
                    floor_plotter.p_section = map_files['section']
                    floor_plotter.save_path = map_files['save_path']

                    # 設定異常 ID（從快取的驗證結果）
                    invalid_address_ids = validation_result.get('invalid_vehicle_address_ids', set()) if validation_result else set()
                    invalid_section_ids = validation_result.get('invalid_vehicle_section_ids', set()) if validation_result else set()
                    if invalid_address_ids or invalid_section_ids:
                        floor_plotter.set_invalid_ids(invalid_address_ids, invalid_section_ids)

                    # 設定顯示選項
                    floor_plotter.set_show_section_dist(self.show_section_dist.get() == '1')
                    floor_plotter.set_show_tag_id(self.show_tag_id.get() == '1')
                    floor_plotter.set_show_address_id(self.show_address_id.get() == '1')

                    # 執行繪圖（生成底圖，但不設定高亮）
                    floor_plotter.load()
                    floor_plotter.execute()

                    # 獲取底圖
                    base_img = floor_plotter.get_base_image()

                    # 預載高亮 overlay（全部日期 + 預設門檻）
                    overlay_img = self._preload_floor_overlay(floor_label, floor_plotter)

                    # 儲存到快取
                    self._floor_cache[floor_label] = {
                        'plotter': floor_plotter,
                        'base_img': base_img,
                        'overlay_img': overlay_img,
                        'combined_img': base_img,  # 初始合成圖先用底圖，點樓層時加入 zone
                        'map_data': validation_result,
                        'folder_path': folder_path,
                    }

                    self._floor_loading_status[floor_label] = 'loaded'
                    loaded_count += 1
                    self._update_progress(loaded_count)
                    logging.info(f"樓層 {floor_label} 底圖+高亮預載完成 (尺寸: {base_img.size if base_img else 'N/A'})")
                    fl = floor_label
                    self.root.after(0, lambda fl=fl: self._enable_floor_button(fl))

                except Exception as e:
                    logging.error(f"預載樓層 {floor_label} 失敗: {e}")
                    self._floor_loading_status[floor_label] = 'failed'
                    loaded_count += 1
                    self._update_progress(loaded_count)
                    continue

            # 全部載入完成
            elapsed = time.time() - start_time
            self._update_status(f"就緒 - 已載入 {len(self._floor_cache)}/3 個樓層 ({elapsed:.1f}秒)")
            logging.info(f"底圖預載完成，共載入 {len(self._floor_cache)} 個樓層，耗時 {elapsed:.1f} 秒")

        except Exception as e:
            logging.error(f"預載樓層底圖時發生錯誤: {e}")
            self._update_status(f"預載失敗: {str(e)}")
        finally:
            # 重置進度條
            self.root.after(2000, lambda: self._update_progress(0))

    def _preload_floor_overlay(self, floor_label, plotter):
        """在背景預載指定樓層的高亮 overlay（全部日期、預設門檻）。
        回傳 PIL Image 或 None（失敗時）。
        """
        try:
            if not hasattr(self, 'highlight_log_df') or self.highlight_log_df is None:
                return None

            # 依樓層篩選車輛編號範圍，取得該樓層所有日期
            floor_nums = {
                '1F': set(range(101, 116)),
                '2F': set(range(116, 138)) | {140},
                '3F': {138, 139},
            }.get(floor_label, set())

            df = self.highlight_log_df.copy()
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

            # 計算預設門檻（與 _update_skid_slider_range 一致）
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
                logging.info(f"樓層 {floor_label} 高亮 overlay 預載完成（門檻≥{threshold}次）")
                return overlay
        except Exception as e:
            logging.warning(f"預載樓層 {floor_label} 高亮 overlay 失敗: {e}")
        return None

    def _enable_floor_button(self, floor_label):
        """啟用指定樓層按鈕（預載完成後從主執行緒呼叫）"""
        btn = self.floor_buttons.get(floor_label)
        if btn:
            btn.config(state=tk.NORMAL)

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

    def _export_canvas_image(self):
        """匯出當前畫布畫面（含圖例），讓使用者選擇儲存位置"""
        if not hasattr(self, '_base_pil_img') or self._base_pil_img is None:
            messagebox.showwarning("警告", "請先載入地圖")
            return

        # 依 checkbutton 狀態重建合成圖（全解析度）
        show_zone = getattr(self, '_show_zone_var', tk.IntVar(value=1)).get() == 1
        show_highlight = getattr(self, '_show_highlight_var', tk.IntVar(value=1)).get() == 1

        result_img = self._base_pil_img.copy().convert("RGBA")

        if show_zone and hasattr(self, '_zone_pil_img') and self._zone_pil_img:
            zone_img = self._zone_pil_img.convert("RGBA")
            if zone_img.size != result_img.size:
                zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
            result_img = Image.alpha_composite(result_img, zone_img)

        if show_highlight and hasattr(self, '_overlay_pil_img') and self._overlay_pil_img:
            overlay_img = self._overlay_pil_img.convert("RGBA")
            if overlay_img.size != result_img.size:
                overlay_img = overlay_img.resize(result_img.size, Image.LANCZOS)
            result_img = Image.alpha_composite(result_img, overlay_img)

        # 建立圖例並水平拼接
        legend_img = self._build_legend_image(result_img.height, show_zone, show_highlight)
        combined = Image.new("RGBA", (result_img.width + legend_img.width, result_img.height), (255, 255, 255, 255))
        combined.paste(result_img, (0, 0))
        combined.paste(legend_img, (result_img.width, 0))

        # 選擇儲存位置
        floor_label = getattr(self, '_current_floor', '')
        default_name = f"map_{floor_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG 圖片", "*.png"), ("JPEG 圖片", "*.jpg"), ("所有檔案", "*.*")],
            title="選擇圖片儲存位置",
            initialfile=default_name
        )
        if not save_path:
            return

        export_img = combined.convert("RGB") if save_path.lower().endswith(('.jpg', '.jpeg')) else combined
        export_img.save(save_path)
        messagebox.showinfo("成功", f"圖片已儲存至：\n{save_path}")
        logging.info(f"圖片已匯出至 {save_path}")

    def _build_legend_image(self, height, show_zone=True, show_highlight=True):
        """建立圖例 PIL Image，與地圖等高後拼接於右側

        Args:
            height: 與地圖相同的高度（px）
            show_zone: 是否顯示施工區域項目
            show_highlight: 是否顯示打滑高亮項目

        Returns:
            PIL.Image: RGBA 圖例圖像
        """
        from PIL import ImageDraw, ImageFont

        legend_w = 230
        padding = 20
        item_h = 45
        swatch_w, swatch_h = 24, 18

        # 固定圖例項目（依當前圖層狀態決定是否顯示）
        items = [("行駛方向", (0, 0, 255), "arrow")]
        if show_zone:
            items.append(("施工區域", (135, 206, 235), "rect_filled"))
        if show_highlight:
            items.append(("打滑高亮位置", (255, 0, 0), "rect_outline"))
        items.append(("異常地址", (255, 0, 0), "exclaim"))
        items.append(("異常路段", (255, 165, 0), "exclaim"))

        img = Image.new("RGBA", (legend_w, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        # 左側分隔線
        draw.line([(1, 0), (1, height - 1)], fill=(180, 180, 180, 255), width=2)

        # 嘗試載入中文字型
        font_title = font_body = None
        for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"):
            try:
                font_title = ImageFont.truetype(fp, 18)
                font_body = ImageFont.truetype(fp, 14)
                break
            except Exception:
                continue
        if font_title is None:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        draw.text((padding, padding), "圖例", fill=(0, 0, 0), font=font_title)

        y = padding + 42
        for label, color, style in items:
            sx = padding + 2
            lx = sx + swatch_w + 12
            cy = y + swatch_h // 2

            if style == "rect_filled":
                draw.rectangle([sx, y, sx + swatch_w, y + swatch_h], fill=color, outline=color)
            elif style == "rect_outline":
                draw.rectangle([sx, y, sx + swatch_w, y + swatch_h], outline=color, width=3)
            elif style == "arrow":
                draw.line([(sx, cy), (sx + swatch_w - 6, cy)], fill=color, width=3)
                draw.polygon([
                    (sx + swatch_w, cy),
                    (sx + swatch_w - 8, cy - 5),
                    (sx + swatch_w - 8, cy + 5),
                ], fill=color)
            elif style == "exclaim":
                draw.text((sx + 7, y - 2), "!", fill=color, font=font_title)

            draw.text((lx, y + 1), label, fill=(0, 0, 0), font=font_body)
            y += item_h

        return img

    def _update_skid_ranking(self, floor_label=None, selected_dates=None, addr_ids=None, sec_ids=None):
        """根據 highlight_log_df 更新右側面板指定樓層的打滑次數排名。

        Args:
            floor_label: '1F'/'2F'/'3F'，限制只看該樓層車輛
            selected_dates: 日期清單，若提供則只計算這些日期的事件
            addr_ids: 已過濾的 addressid 集合（滑桿門檻）；None 表示不限制
            sec_ids:  已過濾的 sectionid 集合（滑桿門檻）；None 表示不限制
        """
        if not hasattr(self, 'skid_rank_tree'):
            return

        # 清除現有資料
        for item in self.skid_rank_tree.get_children():
            self.skid_rank_tree.delete(item)

        if not hasattr(self, 'highlight_log_df') or self.highlight_log_df is None:
            return

        # 更新樓層標籤
        if hasattr(self, '_skid_floor_label') and floor_label:
            self._skid_floor_label.config(text=f"{floor_label} 車輛打滑次數")

        _floor_check = {
            "1F": lambda n: 101 <= n <= 115,
            "2F": lambda n: (116 <= n <= 137) or n == 140,
            "3F": lambda n: n in (138, 139),
        }

        try:
            df = self.highlight_log_df.copy()
            df['number'] = df['number'].astype(str).str.strip()
            df = df[df['number'].str.len() > 0]

            # 樓層過濾
            if floor_label and floor_label in _floor_check:
                check = _floor_check[floor_label]
                def _match(s):
                    try:
                        return check(int(s))
                    except Exception:
                        return False
                df = df[df['number'].apply(_match)]

            # 日期過濾（滑桿觸發時傳入）
            if selected_dates is not None:
                df = df[df['start_date'].isin(selected_dates)]

            # 依滑桿門檻過濾：只計算出現在 addr_ids / sec_ids 裡的事件
            if addr_ids is not None or sec_ids is not None:
                addr_set = set(str(a).strip() for a in (addr_ids or []))
                sec_set = set(str(s).strip() for s in (sec_ids or []))
                mask = (
                    df['addressid'].astype(str).str.strip().isin(addr_set) |
                    df['sectionid'].astype(str).str.strip().isin(sec_set)
                )
                df = df[mask]

            counts = df.groupby('number').size().reset_index(name='count')
            counts = counts.sort_values('count', ascending=False).reset_index(drop=True)
            for i, row in counts.iterrows():
                self.skid_rank_tree.insert("", "end", values=(i + 1, row['number'], row['count']))
        except Exception as e:
            logging.error(f"更新打滑次數排名失敗: {e}")

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
        """載入指定資料夾並直接繪製車輛地圖（優先使用快取）"""
        # 推斷樓層並記錄
        self._current_floor = self._floor_from_folder(folder_path)

        # 首次點選樓層時顯示打滑滑桿，並啟用日期篩選按鈕
        if hasattr(self, '_skid_slider_frame') and not self._skid_slider_frame.winfo_ismapped():
            self._skid_slider_frame.pack(fill=tk.X, padx=5, pady=(0, 2),
                                         before=self.canvas_frame)
        for btn_attr in ('_date_select_all_btn', '_date_clear_btn', '_date_reload_btn'):
            btn = getattr(self, btn_attr, None)
            if btn:
                btn.config(state=tk.NORMAL)

        # 檢查是否有快取
        if hasattr(self, '_floor_cache') and self._current_floor in self._floor_cache:
            self._update_status(f"載入樓層 {self._current_floor}（使用快取）")
            logging.info(f"使用快取載入樓層 {self._current_floor}")

            # 從快取中獲取資料
            cache = self._floor_cache[self._current_floor]
            self.data_folder = cache['folder_path']
            self.map_data = cache['map_data']
            self.vehicle_map_plotter = cache['plotter']

            # 設置底圖和圖層
            self._base_pil_img = cache['base_img']
            self._zone_pil_img = cache.get('zone_img')  # 施工區域圖層
            self._overlay_pil_img = cache.get('overlay_img')  # 高亮圖層
            self._combined_pil_img = cache.get('combined_img', cache['base_img'])

            # 如果快取中沒有 zone 圖層，嘗試產生
            if self._zone_pil_img is None and hasattr(self, 'vehicle_map_plotter'):
                # 使用快取中的 plotter 來產生 zone 圖層
                cache_plotter = cache.get('plotter')
                if cache_plotter:
                    # 暫時將 vehicle_map_plotter 設為 cache_plotter 以獲取座標
                    original_plotter = self.vehicle_map_plotter
                    self.vehicle_map_plotter = cache_plotter
                    self._zone_pil_img = self._load_zone_for_floor(self.data_folder)
                    self._zone_section_pil_img = self._load_zone_section_for_floor(self.data_folder)
                    # 恢復原來的 plotter
                    self.vehicle_map_plotter = original_plotter
                else:
                    self._zone_pil_img = self._load_zone_for_floor(self.data_folder)
                    self._zone_section_pil_img = self._load_zone_section_for_floor(self.data_folder)

                # 合併 zone 和 zone_section 圖層
                if self._zone_pil_img and self._zone_section_pil_img:
                    # 調整尺寸一致
                    zone_img = self._zone_pil_img
                    zone_section_img = self._zone_section_pil_img
                    if zone_img.size != zone_section_img.size:
                        zone_section_img = zone_section_img.resize(zone_img.size, Image.LANCZOS)
                    # 合併兩個圖層
                    self._zone_pil_img = Image.alpha_composite(zone_img, zone_section_img)
                elif self._zone_section_pil_img:
                    self._zone_pil_img = self._zone_section_pil_img

                if self._zone_pil_img:
                    self._floor_cache[self._current_floor]['zone_img'] = self._zone_pil_img
                    logging.info(f"施工區域圖層已產生並存入快取，尺寸: {self._zone_pil_img.size}")
                else:
                    logging.warning(f"無法為樓層 {self._current_floor} 產生施工區域圖層")

            # 載入 highlight_log.csv（若尚未預載才重新讀取）
            if not hasattr(self, 'highlight_log_df') or self.highlight_log_df is None:
                self._load_highlight_log(self.data_folder)

            # 填充日期列表（根據樓層過濾）
            self._populate_date_list()

            # 清除日期選擇（不觸發重繪）
            for var in self.date_checkboxes.values():
                var.set(0)

            # 顯示底圖 + 施工區域（初始沒有高亮）
            if self._base_pil_img:
                # 建立圖層切換 checkbutton（只建立一次）
                self._create_layer_checkbuttons()
                
                # 自動顯示施工區域圖層（如果存在）
                if self._zone_pil_img:
                    # 合成底圖 + 施工區域
                    result_img = self._base_pil_img.copy()
                    zone_img = self._zone_pil_img
                    if zone_img.size != result_img.size:
                        zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
                    result_img = Image.alpha_composite(result_img, zone_img)
                    self.show_image_on_canvas(result_img)
                else:
                    self.show_image_on_canvas(self._base_pil_img)

            self._update_status(f"就緒 - {self._current_floor}")
            logging.info(f"樓層 {self._current_floor} 載入完成（使用快取）")
            self._update_skid_ranking(self._current_floor)
        else:
            # 沒有快取，使用原有流程
            self._update_status(f"載入樓層 {self._current_floor}（完整載入）...")
            logging.info(f"樓層 {self._current_floor} 無快取，執行完整載入")
            self.load_fixed_folder(folder_path)
            # 若資料夾載入成功才繪圖
            if self.data_folder:
                # 填充日期列表
                self._populate_date_list()
                self.plot_vehicle_map()
            self._update_skid_ranking(self._current_floor)

    def _create_layer_checkbuttons(self):
        """建立圖層切換 checkbutton（顯示施工區域和高亮方框）"""
        if not hasattr(self, "_show_zone_check"):
            # 施工區域 checkbutton
            self._show_zone_var = tk.IntVar(value=1)
            self._show_zone_check = tk.Checkbutton(
                self.canvas_frame,
                text="顯示施工區域",
                variable=self._show_zone_var,
                command=self._toggle_layers
            )
            self._show_zone_check.grid(row=2, column=0, sticky="w", pady=5, padx=5)

        if not hasattr(self, "_show_highlight_check"):
            # 高亮方框 checkbutton
            self._show_highlight_var = tk.IntVar(value=1)
            self._show_highlight_check = tk.Checkbutton(
                self.canvas_frame,
                text="顯示高亮方框",
                variable=self._show_highlight_var,
                command=self._toggle_layers
            )
            self._show_highlight_check.grid(row=3, column=0, sticky="w", pady=5, padx=5)

    def _toggle_layers(self):
        """切換圖層顯示（施工區域和高亮方框）"""
        try:
            # 獲取各圖層的顯示狀態
            show_zone = getattr(self, '_show_zone_var', tk.IntVar(value=1)).get() == 1
            show_highlight = getattr(self, '_show_highlight_var', tk.IntVar(value=1)).get() == 1

            if not hasattr(self, '_base_pil_img') or self._base_pil_img is None:
                return

            # 從底圖開始
            result_img = self._base_pil_img.copy()

            # 第二層：施工區域（如果存在且顯示）
            if show_zone and hasattr(self, '_zone_pil_img') and self._zone_pil_img:
                # 調整尺寸
                zone_img = self._zone_pil_img
                if zone_img.size != result_img.size:
                    zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
                result_img = Image.alpha_composite(result_img, zone_img)

            # 第三層：高亮方框（需有選擇日期才合成）
            has_dates = bool(self._get_selected_dates()) if hasattr(self, 'date_checkboxes') else False
            if show_highlight and has_dates and hasattr(self, '_overlay_pil_img') and self._overlay_pil_img:
                # 調整尺寸
                overlay_img = self._overlay_pil_img
                if overlay_img.size != result_img.size:
                    overlay_img = overlay_img.resize(result_img.size, Image.LANCZOS)
                result_img = Image.alpha_composite(result_img, overlay_img)

            # 顯示合成後的圖像
            self.show_image_on_canvas(result_img)

            # 更新狀態
            zone_status = "顯示" if show_zone else "隱藏"
            highlight_status = "顯示" if show_highlight else "隱藏"
            self._update_status(f"圖層: 施工區域[{zone_status}] 高亮方框[{highlight_status}]")

        except Exception as e:
            logging.error(f"切換圖層失敗: {e}")

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

            # 根據使用者選擇的日期決定要高亮的 address / section
            selected_indices = self.date_listbox.curselection() if hasattr(self, 'date_listbox') else []
            selected_dates = [self.date_listbox.get(i) for i in selected_indices] if selected_indices else []

            # 使用選擇的日期過濾高亮數據
            addr_ids, sec_ids = self._get_highlights_by_dates(selected_dates)

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

            # 取得第一圖層（原始底圖）
            self._base_pil_img = self.vehicle_map_plotter.get_base_image()
            # 取得第二圖層（純方框圖層，透明背景）
            self._overlay_pil_img = self.vehicle_map_plotter.get_overlay_image()

            # 建立合成圖（底圖 + 方框）
            if self._base_pil_img and self._overlay_pil_img:
                # 確保兩個圖層尺寸一致
                if self._base_pil_img.size != self._overlay_pil_img.size:
                    # 調整 overlay 尺寸以匹配 base
                    self._overlay_pil_img = self._overlay_pil_img.resize(self._base_pil_img.size, Image.LANCZOS)

                # 合成圖層：底圖 + 方框
                self._combined_pil_img = Image.new("RGBA", self._base_pil_img.size)
                self._combined_pil_img.paste(self._base_pil_img, (0, 0))
                self._combined_pil_img.paste(self._overlay_pil_img, (0, 0), self._overlay_pil_img)
            else:
                self._combined_pil_img = self._base_pil_img

            # 建立圖層切換 checkbutton（只建立一次）
            if not hasattr(self, "_show_highlight_var"):
                self._show_highlight_var = tk.IntVar(value=1)  # 預設勾選，顯示方框
                self._show_highlight_check = tk.Checkbutton(
                    self.canvas_frame,
                    text="顯示高亮方框",
                    variable=self._show_highlight_var,
                    command=self._toggle_vehicle_highlight
                )
                # 放在 canvas_frame 的第 2 行
                self._show_highlight_check.grid(row=2, column=0, sticky="w", pady=5, padx=5)

            # 根據 checkbutton 狀態顯示圖像
            if self._show_highlight_var.get() == 1 and self._combined_pil_img:
                self.show_image_on_canvas(self._combined_pil_img)
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

    def _clamp(self, v, lo, hi):
        """將 v 限制在 [lo, hi] 範圍內（helper）。"""
        try:
            return max(lo, min(hi, v))
        except Exception:
            # 若傳入非數值或發生錯誤，回傳邊界值以避免崩潰
            return lo if v is None else lo

    def _on_date_frame_configure(self, event):
        """當日期框架內容變化時更新滾動區域"""
        self.date_canvas.configure(scrollregion=self.date_canvas.bbox("all"))

    def _on_date_canvas_configure(self, event):
        """當 canvas 大小變化時調整內部框架寬度"""
        canvas_width = event.width
        self.date_canvas.itemconfig(self.date_canvas_window, width=canvas_width)

    def _on_date_list_mousewheel(self, event):
        """處理日期列表的滑鼠滾輪事件"""
        if hasattr(event, 'delta') and event.delta:
            # Windows/Mac
            self.date_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif hasattr(event, 'num'):
            # Linux
            if event.num == 4:
                self.date_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.date_canvas.yview_scroll(1, "units")

    def _populate_date_list(self):
        """填充日期列表（根據當前選擇的樓層過濾）"""
        try:
            # 清除現有的所有 checkbox
            for widget in self.date_checkbox_frame.winfo_children():
                widget.destroy()
            self.date_checkboxes.clear()

            if not hasattr(self, 'highlight_log_df') or self.highlight_log_df is None:
                no_data_label = ttk.Label(self.date_checkbox_frame, text="(無資料)")
                no_data_label.pack(pady=5, padx=5, anchor="w")
                return

            # 根據當前樓層過濾資料
            df = self.highlight_log_df.copy()

            # 如果有當前樓層，則過濾對應的 number 範圍
            if hasattr(self, '_current_floor') and self._current_floor:
                def to_int_safe(s):
                    try:
                        return int(str(s).strip())
                    except Exception:
                        return None

                df["_num"] = df["number"].apply(to_int_safe)

                # 根據樓層定義 number 範圍
                want_nums = set()
                if self._current_floor == "1F":
                    want_nums.update(range(101, 116))
                elif self._current_floor == "2F":
                    want_nums.update(range(116, 138))
                    want_nums.add(140)
                elif self._current_floor == "3F":
                    want_nums.update([138, 139])

                # 過濾符合樓層的記錄
                if want_nums:
                    df = df[df["_num"].isin(want_nums)]
                    logging.info(f"樓層 {self._current_floor} 過濾後剩餘 {len(df)} 筆記錄")

            # 獲取唯一日期並排序
            dates = df['start_date'].unique()
            dates = sorted([d for d in dates if d and d.strip()])

            if not dates:
                floor_info = f" ({self._current_floor})" if hasattr(self, '_current_floor') and self._current_floor else ""
                no_data_label = ttk.Label(self.date_checkbox_frame, text=f"(無日期資料{floor_info})")
                no_data_label.pack(pady=5, padx=5, anchor="w")
                return

            # 以週為單位分組（ISO week，週一為起點）
            from datetime import datetime
            week_groups = {}  # {(iso_year, iso_week): [date_str, ...]}
            for d in dates:
                try:
                    dt = datetime.strptime(d.strip(), "%Y/%m/%d")
                except ValueError:
                    try:
                        dt = datetime.strptime(d.strip(), "%Y-%m-%d")
                    except ValueError:
                        continue
                iso = dt.isocalendar()
                key = (iso[0], iso[1])
                week_groups.setdefault(key, []).append(d)

            # 依週序排列，標籤顯示該週內實際有資料的首尾日期
            def _fmt(ds):
                try:
                    dt = datetime.strptime(ds.strip(), "%Y/%m/%d")
                    return f"{dt.month}/{dt.day}"
                except Exception:
                    return ds.strip()

            self._week_to_dates = {}
            for key in sorted(week_groups.keys()):
                group = week_groups[key]
                first, last = _fmt(group[0]), _fmt(group[-1])
                label = f"W{key[1]:02d}  {first}~{last}" if first != last else f"W{key[1]:02d}  {first}"
                self._week_to_dates[label] = week_groups[key]
                var = tk.IntVar(value=0)
                cb = ttk.Checkbutton(
                    self.date_checkbox_frame,
                    text=label,
                    variable=var,
                    command=self._on_date_checkbox_changed
                )
                cb.pack(anchor="w", padx=1, pady=0)
                self.date_checkboxes[label] = var

            floor_info = f"樓層 {self._current_floor} " if hasattr(self, '_current_floor') and self._current_floor else ""
            logging.info(f"已載入 {floor_info}{len(self._week_to_dates)} 週（共 {len(dates)} 個日期）")

        except Exception as e:
            logging.error(f"填充日期列表失敗: {e}")

    def _get_selected_dates(self):
        """回傳目前勾選週次所對應的所有日期字串列表"""
        if not hasattr(self, 'date_checkboxes'):
            return []
        week_to_dates = getattr(self, '_week_to_dates', {})
        result = []
        for label, var in self.date_checkboxes.items():
            if var.get() == 1:
                result.extend(week_to_dates.get(label, [label]))
        return result

    def _on_date_checkbox_changed(self):
        """當用戶變更 checkbox 時的處理"""
        try:
            # 獲取選中的日期
            selected_dates = self._get_selected_dates()

            if not selected_dates:
                logging.info("未選擇任何日期")
            else:
                logging.info(f"已選擇日期: {selected_dates}")

            # 自動重新繪製地圖
            self._reload_highlights()

        except Exception as e:
            logging.error(f"日期選擇處理失敗: {e}")

    def _select_all_dates(self):
        """全選所有日期"""
        for var in self.date_checkboxes.values():
            var.set(1)
        self._reload_highlights()

    def _clear_date_selection(self):
        """清除日期選擇"""
        for var in self.date_checkboxes.values():
            var.set(0)
        # 清除高亮並重繪
        self._reload_highlights()

    def _reload_highlights(self):
        """根據選擇的日期重新載入高亮並重繪地圖（僅更新方框圖層）"""
        try:
            # 獲取當前選擇的日期（從 checkbox，週次展開為實際日期）
            selected_dates = self._get_selected_dates() if hasattr(self, 'date_checkboxes') else []

            # 更新狀態
            if selected_dates:
                self._update_status(f"更新高亮 ({len(selected_dates)} 個日期)...")
            else:
                self._update_status("清除高亮...")

            # 計算 address 和 section 次數分佈，更新滑桿範圍（初始值=中位數，位置在正中央）
            addr_counts, sec_counts = self._calc_highlight_counts(selected_dates)
            self._skid_addr_counts = addr_counts
            self._skid_sec_counts = sec_counts
            self._update_skid_slider_range(addr_counts, sec_counts)

            # 依目前滑桿門檻（0-100位置→實際次數）過濾 address 和 section highlights
            pos = self._skid_slider_var.get() if hasattr(self, '_skid_slider_var') else 50
            threshold = self._slider_pos_to_threshold(pos)
            addr_ids = [aid for aid, cnt in addr_counts.items() if cnt >= threshold]
            sec_ids = [sid for sid, cnt in sec_counts.items() if cnt >= threshold]

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

            # 設定新的高亮 ID
            if hasattr(self, 'vehicle_map_plotter'):
                self.vehicle_map_plotter.set_highlight_address_ids(cast_ids(addr_ids))
                self.vehicle_map_plotter.set_highlight_section_ids(cast_ids(sec_ids))

                # 只重新生成 overlay 圖層，不重繪底圖
                if self.vehicle_map_plotter.regenerate_overlay():
                    # 成功重新生成 overlay，更新顯示
                    self._overlay_pil_img = self.vehicle_map_plotter.get_overlay_image()

                    # 重新合成圖層：底圖 + 施工區域 + 高亮
                    result_img = self._base_pil_img.copy() if self._base_pil_img else None
                    
                    # 如果有施工區域圖層，先合成施工區域
                    if result_img and hasattr(self, '_zone_pil_img') and self._zone_pil_img:
                        zone_img = self._zone_pil_img
                        if zone_img.size != result_img.size:
                            zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
                        result_img = Image.alpha_composite(result_img, zone_img)
                    
                    # 再合成高亮圖層
                    if result_img and self._overlay_pil_img:
                        overlay_img = self._overlay_pil_img
                        if overlay_img.size != result_img.size:
                            overlay_img = overlay_img.resize(result_img.size, Image.LANCZOS)
                        result_img = Image.alpha_composite(result_img, overlay_img)
                    
                    self._combined_pil_img = result_img

                    # 根據 checkbutton 狀態顯示圖像
                    if hasattr(self, '_show_highlight_var') and self._show_highlight_var.get() == 1 and self._combined_pil_img:
                        self.show_image_on_canvas(self._combined_pil_img)
                    elif self._base_pil_img:
                        self.show_image_on_canvas(self._base_pil_img)

                    # 更新快取
                    if hasattr(self, '_floor_cache') and hasattr(self, '_current_floor') and self._current_floor in self._floor_cache:
                        self._floor_cache[self._current_floor]['overlay_img'] = self._overlay_pil_img
                        self._floor_cache[self._current_floor]['combined_img'] = self._combined_pil_img

                    # 更新狀態
                    floor_info = f" - {self._current_floor}" if hasattr(self, '_current_floor') else ""
                    self._update_status(f"就緒{floor_info} ({len(addr_ids)} addresses, {len(sec_ids)} sections)")
                    logging.info(f"已更新高亮（{len(addr_ids)} addresses, {len(sec_ids)} sections）")
                else:
                    # 重新生成失敗，回退到完整重繪
                    logging.warning("重新生成 overlay 失敗，執行完整重繪")
                    if hasattr(self, 'data_folder') and self.data_folder:
                        self.plot_vehicle_map()

            # 同步更新右側車輛排名，與地圖狀態保持一致
            self._update_skid_ranking(
                floor_label=getattr(self, '_current_floor', None),
                selected_dates=selected_dates,
                addr_ids=addr_ids,
                sec_ids=sec_ids,
            )

        except Exception as e:
            logging.error(f"重新載入高亮失敗: {e}")

    def _get_highlights_by_dates(self, selected_dates):
        """根據選擇的日期獲取高亮的 address 和 section IDs

        Args:
            selected_dates: 選擇的日期列表

        Returns:
            tuple: (address_ids, section_ids)
        """
        addr_ids = []
        sec_ids = []

        if not selected_dates or not hasattr(self, 'highlight_log_df') or self.highlight_log_df is None:
            return addr_ids, sec_ids

        try:
            # 過濾出選擇日期的記錄
            filtered_df = self.highlight_log_df[self.highlight_log_df['start_date'].isin(selected_dates)]

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

    def _calc_highlight_counts(self, selected_dates):
        """計算各 addressid 和 sectionid 在選定日期中的出現次數。

        Returns:
            tuple: (addr_counts dict, sec_counts dict) — {id_str: count}
        """
        from collections import Counter
        if not hasattr(self, 'highlight_log_df') or self.highlight_log_df is None:
            return {}, {}
        if not selected_dates:
            return {}, {}
        df = self.highlight_log_df
        df = df[df['start_date'].isin(selected_dates)]
        addrs = df['addressid'].astype(str).str.strip()
        addrs = addrs[(addrs != '') & (addrs != 'nan')]
        addr_counts = dict(Counter(addrs))
        secs = df['sectionid'].astype(str).str.strip()
        secs = secs[(secs != '') & (secs != 'nan')]
        sec_counts = dict(Counter(secs))
        return addr_counts, sec_counts

    def _update_skid_slider_range(self, addr_counts, sec_counts):
        """根據 address+section 次數分佈設定滑桿（0-100 正規化）。
        位置 0 = 門檻最低（顯示全部），50 = 範圍中間值（永遠在正中央），100 = 最高重複率。
        中間值 = (min + max) // 2，例如 1~4 取 2，1~5 取 3。
        """
        if not hasattr(self, '_skid_slider'):
            return
        all_counts = list(addr_counts.values()) + list(sec_counts.values())
        if not all_counts:
            self._skid_slider.config(from_=0, to=100, state=tk.DISABLED)
            self._skid_slider_var.set(50)
            self._skid_median = 1
            self._skid_max_count = 1
            return
        min_c = max(min(all_counts), 1)
        max_c = max(all_counts)
        mid_c = max((min_c + max_c) // 2, 1)
        self._skid_median = mid_c
        self._skid_max_count = max_c
        self._skid_slider.config(from_=0, to=100, state=tk.NORMAL)
        self._skid_slider_var.set(50)
        # 更新標籤顯示中間值門檻
        self._skid_slider.config(label=f"重複打滑門檻 ≥{mid_c}次 (中間值:{mid_c} 最高:{max_c})")

    def _slider_pos_to_threshold(self, pos):
        """將滑桿位置 (0-100) 轉換為重複次數門檻。
        0 → 1（顯示全部），50 → 中位數，100 → 最大值。
        分段線性映射，確保 50 永遠對應中位數。
        """
        median_c = getattr(self, '_skid_median', 1)
        max_c = getattr(self, '_skid_max_count', 1)
        if pos <= 50:
            # [0, 50] → [1, median_c]
            t = 1 + (median_c - 1) * (pos / 50.0)
        else:
            # [50, 100] → [median_c, max_c]
            t = median_c + (max_c - median_c) * ((pos - 50) / 50.0)
        return max(1, int(round(t)))

    def _on_skid_slider_changed(self, value):
        """滑桿移動：立即更新標籤（輕量），debounce 150ms 後才執行重繪。"""
        try:
            threshold = self._slider_pos_to_threshold(int(float(value)))
            # 立即更新標籤，讓使用者感覺有即時回饋
            if hasattr(self, '_skid_slider'):
                median_c = getattr(self, '_skid_median', 1)
                max_c = getattr(self, '_skid_max_count', 1)
                self._skid_slider.config(label=f"重複打滑門檻 ≥{threshold}次 (中間值:{median_c} 最高:{max_c})")
            # 取消上一次尚未執行的重繪任務
            if getattr(self, '_skid_after_id', None):
                self.root.after_cancel(self._skid_after_id)
            # 150ms 後執行一次重繪（停止拖曳後才更新畫面）
            self._skid_after_id = self.root.after(150, lambda v=value: self._apply_skid_threshold(v))
        except Exception as e:
            logging.error(f"打滑滑桿移動失敗: {e}")

    def _apply_skid_threshold(self, value):
        """依門檻重新生成 overlay 並更新排名（由 debounce 呼叫）。"""
        try:
            threshold = self._slider_pos_to_threshold(int(float(value)))
            addr_counts = getattr(self, '_skid_addr_counts', {})
            sec_counts = getattr(self, '_skid_sec_counts', {})
            if not addr_counts and not sec_counts:
                return
            addr_ids = [aid for aid, cnt in addr_counts.items() if cnt >= threshold]
            sec_ids = [sid for sid, cnt in sec_counts.items() if cnt >= threshold]

            def cast_ids(lst):
                out = []
                for v in lst:
                    s = str(v).strip()
                    out.append(int(s) if s.isdigit() else s)
                return out

            if not hasattr(self, 'vehicle_map_plotter'):
                return
            self.vehicle_map_plotter.set_highlight_address_ids(cast_ids(addr_ids))
            self.vehicle_map_plotter.set_highlight_section_ids(cast_ids(sec_ids))
            if self.vehicle_map_plotter.regenerate_overlay():
                self._overlay_pil_img = self.vehicle_map_plotter.get_overlay_image()
                result_img = self._base_pil_img.copy() if hasattr(self, '_base_pil_img') and self._base_pil_img else None
                if result_img and hasattr(self, '_zone_pil_img') and self._zone_pil_img:
                    zone_img = self._zone_pil_img
                    if zone_img.size != result_img.size:
                        zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
                    result_img = Image.alpha_composite(result_img, zone_img)
                if result_img and self._overlay_pil_img:
                    overlay_img = self._overlay_pil_img
                    if overlay_img.size != result_img.size:
                        overlay_img = overlay_img.resize(result_img.size, Image.LANCZOS)
                    result_img = Image.alpha_composite(result_img, overlay_img)
                self._combined_pil_img = result_img
                if hasattr(self, '_show_highlight_var') and self._show_highlight_var.get() == 1 and self._combined_pil_img:
                    self.show_image_on_canvas(self._combined_pil_img)
                elif hasattr(self, '_base_pil_img') and self._base_pil_img:
                    self.show_image_on_canvas(self._base_pil_img)
            # 同步更新右側車輛排名
            selected_dates = self._get_selected_dates() if hasattr(self, 'date_checkboxes') else []
            self._update_skid_ranking(
                floor_label=getattr(self, '_current_floor', None),
                selected_dates=selected_dates,
                addr_ids=addr_ids,
                sec_ids=sec_ids,
            )
        except Exception as e:
            logging.error(f"打滑滑桿套用門檻失敗: {e}")