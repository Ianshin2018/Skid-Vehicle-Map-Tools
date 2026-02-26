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

from mapplot.plotters.vehicle_map_plotter import VehicleMapPlotter
from mapplot.plotters.cargo_map_plotter import CargoMapPlotter
from mapplot.utils.file_utils import validate_data_folder, load_map_data, load_and_validate_map_data
from mapplot.utils.data_cache import get_data_cache

# 引入模組
from ui.logging_utils import UILogHandler
from ui.status_display import StatusDisplay
from ui.data_loader import DataLoader
from ui.image_processor import ImageProcessor
from ui.date_filter import DateFilter
from ui.skid_handler import SkidHandler
from ui.preload_manager import PreloadManager

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "data"))
CONFIG_FILE_PATH = 'config.json'


class MapPlotUI:
    """
    地圖繪製使用者介面類別
    提供選擇資料夾和繪製地圖的圖形使用者介面
    """    
    def __init__(self, config=None):
        """初始化地圖繪製使用者介面"""
        self.root = tk.Tk()
        self._project_root = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))
        
        self._setup_window()
        self._image_scale = 0.2
        self._original_pil_img = None
        
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
            
        # 初始化模組
        self._init_modules()
        
        # 建立 UI 元件
        self._create_widgets()
        self._layout_widgets()
        self._setup_logging()
        
        # 初始化數據
        self.data_folder = None
        self.warnings = []
        self.errors = []
        
        # 初始化樓層快取
        self._floor_cache = {}
        self._floor_loading_status = {}
        
        # 根據配置設定 UI 狀態
        self._apply_config_to_ui()

        # 初始化數據緩存
        self._data_cache = get_data_cache()
        
        # 啟動預載
        self._preload_manager.start_async_preload()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()

    def _init_modules(self):
        """初始化所有功能模組"""
        # 日誌處理
        self._logging_handler = UILogHandler(self)
        
        # 狀態顯示
        self._status_display = StatusDisplay(self)
        
        # 資料載入
        self._data_loader = DataLoader(self, self._project_root)
        
        # 影像處理
        self._image_processor = ImageProcessor(self)
        
        # 日期篩選
        self._date_filter = DateFilter(self)
        
        # 打滑處理
        self._skid_handler = SkidHandler(self)
        
        # 預載管理
        self._preload_manager = PreloadManager(self, DATA_ROOT)

    def _setup_window(self):
        """設定視窗屬性"""
        self.root.minsize(300, 200)
        self.root.title("打滑數據顯示工具-V1.0.4")
        self._create_menu_bar()

    def _create_menu_bar(self):
        """建立功能表列（檔案、顯示、說明選單）"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 檔案選單
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="檔案", menu=file_menu)
        file_menu.add_command(label="匯入資料集", command=self._import_dataset)
        file_menu.add_command(label="匯出圖片", command=self._export_canvas_image)
        file_menu.add_separator()
        file_menu.add_command(label="結束", command=self._on_closing)

        # 顯示選單
        display_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="顯示", menu=display_menu)
        
        # 施工區域
        self._menu_show_zone_var = tk.IntVar(value=1)
        display_menu.add_checkbutton(
            label="施工區域",
            variable=self._menu_show_zone_var,
            command=self._on_menu_zone_toggled
        )
        
        # 打滑位置
        self._menu_show_highlight_var = tk.IntVar(value=1)
        display_menu.add_checkbutton(
            label="打滑位置",
            variable=self._menu_show_highlight_var,
            command=self._on_menu_highlight_toggled
        )

        # 說明選單
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="說明", menu=help_menu)
        help_menu.add_command(label="使用說明書", command=self._show_readme)
        help_menu.add_command(label="程式版本號", command=self._show_version)

    def _on_menu_zone_toggled(self):
        """功能表顯示施工區域切換"""
        if hasattr(self, '_show_zone_var'):
            self._show_zone_var.set(self._menu_show_zone_var.get())
        else:
            self._show_zone_var = tk.IntVar(value=self._menu_show_zone_var.get())
        self._toggle_layers()

    def _on_menu_highlight_toggled(self):
        """功能表顯示打滑位置切換"""
        if hasattr(self, '_show_highlight_var'):
            self._show_highlight_var.set(self._menu_show_highlight_var.get())
        else:
            self._show_highlight_var = tk.IntVar(value=self._menu_show_highlight_var.get())
        self._toggle_layers()

    def _sync_menu_checkboxes(self):
        """同步功能表核取方塊狀態"""
        if hasattr(self, '_show_zone_var'):
            self._menu_show_zone_var.set(self._show_zone_var.get())
        if hasattr(self, '_show_highlight_var'):
            self._menu_show_highlight_var.set(self._show_highlight_var.get())

    def _show_readme(self):
        """開啟使用說明書"""
        readme_path = os.path.join(self._project_root, "README.md")
        if os.path.exists(readme_path):
            import webbrowser
            webbrowser.open(f"file://{readme_path}")
        else:
            messagebox.showerror("錯誤", "找不到說明檔案：README.md")

    def _show_version(self):
        """顯示程式版本號"""
        version_info = "打滑數據顯示工具\n\n版本：V1.0.3\n\n功能說明：\n- 顯示樓層地圖\n- 施工區域顯示\n- 打滑位置標示\n- 資料篩選與分析"
        messagebox.showinfo("程式版本號", version_info)

    def _setup_logging(self):
        """設定日誌"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # 加入自訂的 UI 日誌處理器
        self._logging_handler.setLevel(logging.WARNING)
        self._logging_handler.setFormatter(logging.Formatter('%(message)s'))
        
        root_logger = logging.getLogger()
        root_logger.addHandler(self._logging_handler)

    def _create_plotters(self):
        """建立繪圖器物件"""
        self.vehicle_map_plotter = VehicleMapPlotter(config=self.config)
        self.cargo_map_plotter = CargoMapPlotter()

    def _create_widgets(self):
        """建立使用者介面元件"""
        self._create_plotters()
        self._create_checkbutton()
        self._create_status_frames()

    def _create_status_frames(self):
        """建立UI框架結構"""
        # 主容器
        self.main_container = ttk.Frame(self.root)

        # 上方區塊
        self.top_frame = ttk.Frame(self.main_container, height=30)

        # 狀態欄
        self.status_label = ttk.Label(self.top_frame, text="就緒", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        # 進度條
        self.progress_bar = ttk.Progressbar(self.top_frame, mode='determinate', length=200)
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=5)

        # 下方區塊
        self.bottom_frame = ttk.Frame(self.main_container)

        # 下方區塊分為三列
        self.left_panel = ttk.LabelFrame(self.bottom_frame, text="日期篩選")
        self.center_panel = ttk.Frame(self.bottom_frame)
        self.right_panel = ttk.LabelFrame(self.bottom_frame, text="打滑次數排名")

        # === 右側面板 ===
        self._skid_floor_label = ttk.Label(self.right_panel, text="請點選樓層按鈕")
        self._skid_floor_label.pack(pady=(5, 2), padx=5, anchor="w")

        self._show_vehicle_skid_var = tk.IntVar(value=0)
        self._show_vehicle_skid_check = ttk.Checkbutton(
            self.right_panel,
            text="顯示車輛位置",
            variable=self._show_vehicle_skid_var,
            command=self._on_show_vehicle_skid_changed
        )
        self._show_vehicle_skid_check.pack(pady=(0, 2), padx=5, anchor="w")

        _skid_frame = ttk.Frame(self.right_panel)
        _skid_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.skid_rank_tree = ttk.Treeview(
            _skid_frame,
            columns=("rank", "vehicle", "count"),
            show="headings",
            selectmode="browse"
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
        self.skid_rank_tree.bind("<ButtonRelease-1>", self._on_vehicle_rank_click)

        # === 左側面板：日期選擇 ===
        self._date_filter.create_date_panel(self.left_panel)

        # === 中間面板 ===
        self.status_frame = ttk.Frame(self.center_panel)

        # 警報區域
        self.warning_frame = ttk.LabelFrame(self.status_frame, text="警報資訊")
        self.warning_text = tk.Text(self.warning_frame, width=40, height=5, wrap=tk.WORD,
                                   background="#FFFFCC", foreground="#CC6600")
        self.warning_scrollbar = ttk.Scrollbar(self.warning_frame, orient=tk.VERTICAL,
                                           command=self.warning_text.yview)
        self.warning_text.config(yscrollcommand=self.warning_scrollbar.set)

        # 異常區域（放置於右側面板排名下方）
        self.error_frame = ttk.LabelFrame(self.right_panel, text="異常資訊")
        self.error_text = tk.Text(self.error_frame, width=20, height=5, wrap=tk.WORD,
                                background="#FFCCCC", foreground="#990000")
        self.error_scrollbar = ttk.Scrollbar(self.error_frame, orient=tk.VERTICAL,
                                         command=self.error_text.yview)
        self.error_text.config(yscrollcommand=self.error_scrollbar.set)

        # 唯讀狀態
        self.warning_text.config(state=tk.DISABLED)
        self.error_text.config(state=tk.DISABLED)

        # 打滑門檻滑桿
        self._skid_handler.create_skid_slider(self.status_frame)

        # 畫布框架
        self.canvas_frame = ttk.Frame(self.status_frame)

        # 畫布
        self.output_canvas = tk.Canvas(self.canvas_frame, width=400, height=300, bg="white", scrollregion=(0, 0, 400, 300))

        # 滾動條
        self.canvas_v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.output_canvas.yview)
        self.output_canvas.config(yscrollcommand=self.canvas_v_scrollbar.set)

        self.canvas_h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.output_canvas.xview)
        self.output_canvas.config(xscrollcommand=self.canvas_h_scrollbar.set)

        # 縮放按鈕（只保留 + / -，全圖改為下方 checkbox）
        self.zoom_in_btn = tk.Button(self.canvas_frame, text="+", width=2, command=self._zoom_in)
        self.zoom_out_btn = tk.Button(self.canvas_frame, text="-", width=2, command=self._zoom_out)

        # 地圖選項列：全圖 checkbox + 放大鏡 checkbox（置於滑桿與畫布之間）
        self._map_options_frame = ttk.Frame(self.status_frame)

        self._fullmap_var = tk.IntVar(value=0)
        self._fullmap_check = ttk.Checkbutton(
            self._map_options_frame,
            text="全圖",
            variable=self._fullmap_var,
            command=self._zoom_full,
        )
        self._fullmap_check.pack(side=tk.LEFT, padx=(5, 15))

        self._magnifier_var = tk.IntVar(value=0)
        self._magnifier_check = ttk.Checkbutton(
            self._map_options_frame,
            text="放大鏡",
            variable=self._magnifier_var,
            command=self._toggle_magnifier,
        )
        self._magnifier_check.pack(side=tk.LEFT, padx=5)
        
        # 放大鏡顯示區域 (120x120)
        self.magnifier_canvas = tk.Canvas(
            self.canvas_frame,
            width=120,
            height=120,
            bg="gray",
            highlightthickness=1,
            highlightbackground="black"
        )
        
        # 初始化放大鏡相關變數
        self._magnifier_enabled = False
        self._magnifier_last_pos = None
        self._magnifier_after_id = None
        
        # 事件綁定
        self.output_canvas.bind("<Configure>", self._image_processor._on_canvas_resize)
        self.output_canvas.bind("<ButtonPress-1>", self._image_processor._start_move)
        self.output_canvas.bind("<B1-Motion>", self._image_processor._move_canvas)
        self.output_canvas.bind("<Double-Button-1>", lambda *_: self._zoom_full())
        self.output_canvas.bind("<ButtonRelease-3>", self._image_processor._on_canvas_right_click)
        self.output_canvas.bind("<MouseWheel>", self._image_processor._on_mousewheel)
        self.output_canvas.bind("<Button-4>", self._image_processor._on_mousewheel)
        self.output_canvas.bind("<Button-5>", self._image_processor._on_mousewheel)
        self.output_canvas.bind("<Motion>", self._image_processor._on_canvas_mouse_move)

        # 樓層按鈕
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

        # 匯出按鈕（初始隱藏，點選樓層後才顯示於畫布下方）
        self.export_btn = ttk.Button(
            self.canvas_frame,
            text="匯出圖片",
            command=self._export_canvas_image
        )

    def _create_checkbutton(self):
        """建立核取方塊"""
        self.show_section_dist = tk.StringVar(value='1')
        self.show_tag_id = tk.StringVar(value='1')
        self.show_address_id = tk.StringVar(value='1')     
        self.show_zone = tk.IntVar(value=1)
        self.show_highlight = tk.IntVar(value=1)

    def _apply_config_to_ui(self):
        """將配置檔案應用到 UI 元件"""
        pass

    def _layout_widgets(self):
        """佈局使用者介面元件"""
        self.main_container.pack(fill=tk.BOTH, expand=True)
        self.top_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        self.bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        # 三列佈局
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=5)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        self.bottom_frame.rowconfigure(0, weight=1)
        self.bottom_frame.columnconfigure(0, weight=2)
        self.bottom_frame.columnconfigure(1, weight=6)
        self.bottom_frame.columnconfigure(2, weight=2)

        # 中間面板
        self.status_frame.pack(fill=tk.BOTH, expand=True)

        # 右側面板：異常資訊（排名下方）
        self.error_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.error_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 畫布
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.output_canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas_v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_h_scrollbar.grid(row=1, column=0, sticky="ew")
        # export_btn 初始隱藏，點選樓層後才顯示（row=2 右對齊）
        self.canvas_frame.rowconfigure(0, weight=1)
        self.canvas_frame.columnconfigure(0, weight=1)

        # 地圖選項列（全圖 + 放大鏡 checkbox）置於 canvas_frame 之前
        self._map_options_frame.pack(fill=tk.X, padx=5, pady=(0, 2), before=self.canvas_frame)

        self.output_canvas.update()
        canvas_w = self.output_canvas.winfo_width()
        self.zoom_in_btn.place(in_=self.output_canvas, x=canvas_w-50, y=10)
        self.zoom_out_btn.place(in_=self.output_canvas, x=canvas_w-25, y=10)

    # === 代理方法：讓原有程式碼向後相容 ===
    
    def add_warning(self, message):
        return self._status_display.add_warning(message)
    
    def add_error(self, message):
        return self._status_display.add_error(message)
    
    def clear_status_messages(self):
        return self._status_display.clear_messages()
    
    def show_image_on_canvas(self, pil_img):
        return self._image_processor.show_image_on_canvas(pil_img)
    
    def _zoom_in(self):
        return self._image_processor.zoom_in()
    
    def _zoom_out(self):
        return self._image_processor.zoom_out()
    
    def _zoom_full(self):
        """顯示全圖（重置縮放比例）"""
        return self._image_processor.zoom_full()
    
    def _toggle_magnifier(self):
        """切換放大鏡功能：啟用時顯示右下角方框，停用時隱藏"""
        self._magnifier_enabled = self._magnifier_var.get() == 1
        if self._magnifier_enabled:
            canvas_w   = self.output_canvas.winfo_width()
            canvas_h   = self.output_canvas.winfo_height()
            mag_size   = 120
            mag_margin = 10
            self.magnifier_canvas.place(in_=self.output_canvas,
                                        x=canvas_w - mag_size - mag_margin,
                                        y=canvas_h - mag_size - mag_margin)
        else:
            self.magnifier_canvas.delete("all")
            self.magnifier_canvas.place_forget()
    
    def _export_canvas_image(self):
        return self._image_processor.export_canvas_image()
    
    def _toggle_layers(self):
        return self._image_processor.toggle_layers()
    
    def _get_selected_dates(self):
        return self._date_filter.get_selected_dates()
    
    def _populate_date_list(self):
        return self._date_filter.populate_date_list()
    
    def _select_all_dates(self):
        return self._date_filter.select_all_dates()
    
    def _clear_date_selection(self):
        return self._date_filter.clear_date_selection()
    
    def _reload_highlights(self):
        selected_dates = self._get_selected_dates()
        return self._skid_handler.reload_highlights(selected_dates)
    
    def _update_skid_ranking(self, floor_label=None, selected_dates=None, addr_ids=None, sec_ids=None):
        return self._skid_handler.update_skid_ranking(floor_label, selected_dates, addr_ids, sec_ids)
    
    def _calc_highlight_counts(self, selected_dates):
        return self._skid_handler.calc_highlight_counts(selected_dates)
    
    def _slider_pos_to_threshold(self, pos):
        return self._skid_handler.slider_pos_to_threshold(pos)
    
    def _on_skid_slider_changed(self, value):
        return self._skid_handler._on_skid_slider_changed(value)
    
    def _apply_skid_threshold(self, value):
        return self._skid_handler.apply_skid_threshold(value)

    def _on_vehicle_rank_click(self, event):
        return self._skid_handler.on_vehicle_rank_click(event)

    def _on_show_vehicle_skid_changed(self):
        return self._skid_handler.on_show_vehicle_skid_changed()
    
    def _update_status(self, message):
        return self._preload_manager.update_status(message)
    
    def _floor_from_folder(self, folder_path):
        return self._preload_manager.floor_from_folder(folder_path)
    
    def _load_highlights(self, folder_path):
        return self._data_loader.load_highlights(folder_path)
    
    def _load_highlight_log(self, folder_path):
        return self._data_loader.load_highlight_log(folder_path)

    def _import_dataset(self):
        """匯入資料集：開啟檔案對話框，驗證並合併至 highlights.csv"""
        file_path = filedialog.askopenfilename(
            title="選擇資料集檔案",
            filetypes=[("CSV 檔案", "*.csv"), ("所有檔案", "*.*")]
        )
        if not file_path:
            return
        ok, msg, new_count = self._data_loader.import_highlight_dataset(file_path)
        if ok:
            messagebox.showinfo("匯入資料集", msg)
            # 若有新增記錄且已載入樓層，刷新日期面板與打滑排名
            if new_count > 0 and getattr(self, '_current_floor', None):
                self._date_filter.populate_date_list()
                self._skid_handler.regenerate_overlay()
        else:
            messagebox.showerror("匯入資料集", msg)

    def _load_zone_for_floor(self, folder_path):
        return self._data_loader.load_zone_for_floor(folder_path)
    
    def _load_zone_section_for_floor(self, folder_path):
        return self._data_loader.load_zone_section_for_floor(folder_path)
    
    def _get_highlights_by_dates(self, selected_dates):
        return self._data_loader.get_highlights_by_dates(selected_dates)
    
    def _get_highlights_for_floor(self, floor_label):
        return self._data_loader.get_highlights_for_floor(floor_label)
    
    # === 主要功能方法 ===
    
    def select_data_folder(self):
        """選擇地圖資料資料夾"""
        self.clear_status_messages()
        
        folder_path = filedialog.askdirectory(title="選擇包含地圖資料的資料夾")
        if not folder_path:
            return
            
        is_valid, missing_files = validate_data_folder(folder_path)
        if not is_valid:
            error_msg = f"在所選資料夾中找不到以下必要檔案：{', '.join(missing_files)}"
            self.add_error(error_msg)
            messagebox.showerror("缺少檔案", error_msg)
            self.data_folder = None
            return
            
        self.data_folder = folder_path
        logging.info(f"已選擇資料夾: {folder_path}")
        
        try:
            map_files = load_map_data(folder_path)
            logging.info("成功載入地圖檔案路徑")
            
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
            return
        
        except Exception as e:
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            filename, line, func, text = tb[-1]
            error_msg = f"錯誤: {str(e)} | 檔案: {filename} | 行數: {line}"
            logging.error(f"{error_msg} | 類型: {type(e).__name__}")
            self.add_error(error_msg)
            messagebox.showerror("錯誤", f"載入資料時發生錯誤: {str(e)}")
            self.data_folder = None
            return

    def plot_vehicle_map(self):
        """繪製車輛地圖"""
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

            # 執行繪圖
            self.vehicle_map_plotter.load()
            self.vehicle_map_plotter.execute()

            # 取得圖層
            self._base_pil_img = self.vehicle_map_plotter.get_base_image()
            self._overlay_pil_img = self.vehicle_map_plotter.get_overlay_image()

            # 合成圖層
            if self._base_pil_img and self._overlay_pil_img:
                if self._base_pil_img.size != self._overlay_pil_img.size:
                    self._overlay_pil_img = self._overlay_pil_img.resize(self._base_pil_img.size, Image.LANCZOS)

                self._combined_pil_img = Image.new("RGBA", self._base_pil_img.size)
                self._combined_pil_img.paste(self._base_pil_img, (0, 0))
                self._combined_pil_img.paste(self._overlay_pil_img, (0, 0), self._overlay_pil_img)
            else:
                self._combined_pil_img = self._base_pil_img

            # 建立圖層切換
            if not hasattr(self, "_show_highlight_var"):
                self._show_highlight_var = tk.IntVar(value=1)
                self._show_highlight_check = tk.Checkbutton(
                    self.canvas_frame,
                    text="顯示打滑位置",
                    variable=self._show_highlight_var,
                    command=self._toggle_vehicle_highlight
                )
                self._show_highlight_check.grid(row=2, column=0, sticky="w", pady=5, padx=5)

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

    def _toggle_vehicle_highlight(self):
        """切換車輛地圖的打滑位置顯示"""
        has_dates = bool(self._get_selected_dates()) if hasattr(self, 'date_checkboxes') else False
        if self._show_highlight_var.get() == 1 and has_dates:
            if hasattr(self, '_combined_pil_img') and self._combined_pil_img:
                self.show_image_on_canvas(self._combined_pil_img)
        else:
            if hasattr(self, '_base_pil_img') and self._base_pil_img:
                self.show_image_on_canvas(self._base_pil_img)

    def plot_cargo_map(self):
        """繪製貨物地圖"""
        try:
            if not self.data_folder:
                raise ValueError("請先選擇包含必要檔案的資料夾")

            invalid_address_ids = set()
            invalid_section_ids = set()

            if hasattr(self, 'map_data'):
                if 'invalid_cargo_address_ids' in self.map_data:
                    invalid_address_ids = self.map_data['invalid_cargo_address_ids']
                if 'invalid_cargo_section_ids' in self.map_data:
                    invalid_section_ids = self.map_data['invalid_cargo_section_ids']

            if invalid_address_ids or invalid_section_ids:
                self.cargo_map_plotter.set_invalid_ids(invalid_address_ids, invalid_section_ids)
                logging.info(f"已標記 {len(invalid_address_ids)} 個異常地址和 {len(invalid_section_ids)} 個異常路段")

            self.cargo_map_plotter.load()
            self.cargo_map_plotter.execute()

            self._cargo_base_pil_img = self.cargo_map_plotter.get_base_image()
            self._cargo_overlay_pil_img = self.cargo_map_plotter.get_overlay_image()

            if self._cargo_base_pil_img and self._cargo_overlay_pil_img:
                if self._cargo_base_pil_img.size != self._cargo_overlay_pil_img.size:
                    self._cargo_overlay_pil_img = self._cargo_overlay_pil_img.resize(self._cargo_base_pil_img.size, Image.LANCZOS)

                self._cargo_combined_pil_img = Image.new("RGBA", self._cargo_base_pil_img.size)
                self._cargo_combined_pil_img.paste(self._cargo_base_pil_img, (0, 0))
                self._cargo_combined_pil_img.paste(self._cargo_overlay_pil_img, (0, 0), self._cargo_overlay_pil_img)
            else:
                self._cargo_combined_pil_img = self._cargo_base_pil_img

            if not hasattr(self, "_cargo_show_highlight_var"):
                self._cargo_show_highlight_var = tk.IntVar(value=1)
                self._cargo_show_highlight_check = tk.Checkbutton(
                    self.canvas_frame,
                    text="顯示打滑位置",
                    variable=self._cargo_show_highlight_var,
                    command=self._toggle_cargo_highlight
                )
                self._cargo_show_highlight_check.grid(row=2, column=0, sticky="w", pady=5, padx=5)

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
        """切換貨物地圖的打滑位置顯示"""
        if self._cargo_show_highlight_var.get() == 1:
            if hasattr(self, '_cargo_combined_pil_img') and self._cargo_combined_pil_img:
                self.show_image_on_canvas(self._cargo_combined_pil_img)
        else:
            if hasattr(self, '_cargo_base_pil_img') and self._cargo_base_pil_img:
                self.show_image_on_canvas(self._cargo_base_pil_img)

    def _create_layer_checkbuttons(self):
        """建立圖層切換 checkbutton"""
        if not hasattr(self, "_show_zone_check"):
            self._show_zone_var = tk.IntVar(value=1)
            self._show_zone_check = tk.Checkbutton(
                self.canvas_frame,
                text="顯示施工區域",
                variable=self._show_zone_var,
                command=self._toggle_layers
            )
            self._show_zone_check.grid(row=2, column=0, sticky="w", pady=5, padx=5)

        if not hasattr(self, "_show_highlight_check"):
            self._show_highlight_var = tk.IntVar(value=1)
            self._show_highlight_check = tk.Checkbutton(
                self.canvas_frame,
                text="顯示打滑位置",
                variable=self._show_highlight_var,
                command=self._toggle_layers
            )
            self._show_highlight_check.grid(row=3, column=0, sticky="w", pady=5, padx=5)

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
            self._load_highlights(folder_path)
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
        from PIL import Image
        
        self._current_floor = self._floor_from_folder(folder_path)

        # 首次點選樓層時顯示打滑滑桿，並重置滑桿狀態
        self._skid_handler.show_skid_slider()
        self._skid_handler.reset_skid_slider()
        self._date_filter.enable_buttons()

        # 顯示匯出按鈕（放置於畫布下方右下角）
        if not self.export_btn.winfo_ismapped():
            self.export_btn.grid(row=2, column=0, columnspan=2, sticky="e", padx=5, pady=(3, 0))

        # 檢查是否有快取
        if hasattr(self, '_floor_cache') and self._current_floor in self._floor_cache:
            self._update_status(f"載入樓層 {self._current_floor}（使用快取）")
            logging.info(f"使用快取載入樓層 {self._current_floor}")

            cache = self._floor_cache[self._current_floor]
            self.data_folder = cache['folder_path']
            self.map_data = cache['map_data']
            self.vehicle_map_plotter = cache['plotter']

            self._base_pil_img = cache['base_img']
            self._zone_pil_img = cache.get('zone_img')
            self._overlay_pil_img = cache.get('overlay_img')
            self._combined_pil_img = cache.get('combined_img', cache['base_img'])

            # 如果快取中沒有 zone 圖層
            if self._zone_pil_img is None and hasattr(self, 'vehicle_map_plotter'):
                cache_plotter = cache.get('plotter')
                if cache_plotter:
                    original_plotter = self.vehicle_map_plotter
                    self.vehicle_map_plotter = cache_plotter
                    self._zone_pil_img = self._load_zone_for_floor(self.data_folder)
                    self._zone_section_pil_img = self._load_zone_section_for_floor(self.data_folder)
                    self.vehicle_map_plotter = original_plotter

                if self._zone_pil_img and self._zone_section_pil_img:
                    zone_img = self._zone_pil_img
                    if zone_img.size != self._zone_section_pil_img.size:
                        self._zone_section_pil_img = self._zone_section_pil_img.resize(zone_img.size, Image.LANCZOS)
                    self._zone_pil_img = Image.alpha_composite(zone_img, self._zone_section_pil_img)
                elif self._zone_section_pil_img:
                    self._zone_pil_img = self._zone_section_pil_img

                if self._zone_pil_img:
                    self._floor_cache[self._current_floor]['zone_img'] = self._zone_pil_img

            # 載入 highlight_log
            if not hasattr(self, 'highlight_log_df') or self.highlight_log_df is None:
                self._load_highlight_log(self.data_folder)

            # 填充日期列表
            self._populate_date_list()

            # 清除日期選擇
            for var in self.date_checkboxes.values():
                var.set(0)

            # 顯示底圖 + 施工區域
            if self._base_pil_img:
                self._create_layer_checkbuttons()
                
                if self._zone_pil_img:
                    result_img = self._base_pil_img.copy()
                    zone_img = self._zone_pil_img
                    if zone_img.size != result_img.size:
                        zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
                    result_img = Image.alpha_composite(result_img, zone_img)
                    self.show_image_on_canvas(result_img)
                else:
                    self.show_image_on_canvas(self._base_pil_img)

            self._update_status(f"就緒 - {self._current_floor}")
            self._update_skid_ranking(self._current_floor, selected_dates=[])
        else:
            # 沒有快取
            self._update_status(f"載入樓層 {self._current_floor}（完整載入）...")
            self.load_fixed_folder(folder_path)
            if self.data_folder:
                self._populate_date_list()
                self.plot_vehicle_map()
            self._update_skid_ranking(self._current_floor, selected_dates=[])

    def _on_closing(self):
        """關閉視窗時的處理"""
        self.root.destroy()


# 為了向後相容，需要導入 Image
from PIL import Image

