# 地圖繪製工具 (MapPlot)

這是一個用於AGV(自動導引車輛)系統的地圖繪製工具，可視覺化車輛路徑和貨物位置等資訊。

## 功能介紹

- **車輛地圖繪製**: 視覺化車輛行駛路徑和導航點
- **貨物地圖繪製**: 視覺化貨物放置位置和方向
- **資料驗證**: 自動檢查地圖資料的正確性和完整性
- **圖形使用者介面**: 提供簡單易用的操作界面

### 資料驗證功能

工具包含兩種主要的驗證機制：

#### 檔案架構驗證
- 檢查每個CSV檔案是否包含所有必要欄位
- 驗證欄位名稱的正確性
- 檢查檔案格式和編碼

#### 資料內容驗證

1. 地址檔案 (Address.csv) 驗證：
   - MapVersion一致性檢查
   - AddressId 唯一性
   - TagId 唯一性
   - (X, Y) 座標唯一性
   - StorageStationId 唯一性
   - 充電站點資料完整性 (IsChargeStation 為 true 時的相關檢查)
   - AllowVehiclePosition 和 AllowCargoPosition 角度有效性 (只允許 0/90/180/270)

2. 路段檔案 (Section.csv) 驗證：
   - MapVersion一致性檢查
   - SectionId 唯一性
   - (FromAddressId, ToAddressId) 組合唯一性
   - 檢查是否存在反向路段
   - SectionPosition 與 AllowVehiclePosition 一致性
   - 檢查角度值有效性

3. 埠口檔案 (Port.csv) 驗證：
   - MapVersion一致性檢查
   - PortId 唯一性
   - AddressId 唯一性

4. 貨架檔案 (Shelf.csv) 驗證：
   - MapVersion一致性檢查
   - ShelfId 唯一性
   - AddressId 唯一性

#### 交叉檔案驗證

1. MapVersion 一致性：
   - 檢查所有檔案的 MapVersion 是否一致

2. 參照完整性：
   - 檢查 Address 檔案中的 (AddressId, StorageStationId) 是否對應到 Port/Shelf 檔案
   - 驗證 Section 檔案中的 FromAddressId 和 ToAddressId 是否存在於 Address 檔案
   - 確保 StorageStationId 數量與 Port/Shelf 檔案中的 AddressId 總數一致

3. 空間關係驗證：
   - 檢查 Section 檔案中的路段方向是否與實際座標計算出的角度一致
   - 驗證允許的車輛和貨物放置方向是否符合實際路段方向

## 安裝需求

此工具需要以下Python套件：

```
matplotlib
pandas
numpy
tkinter (Python 標準函式庫的一部分)
```

可透過以下指令安裝相依套件：

```bash
pip install matplotlib pandas numpy
```

## 使用方法

### 從圖形介面啟動

1. 執行主程式：

```bash
python main.py
```

2. 使用介面進行操作：
   - 點擊「選擇資料夾」按鈕選擇包含地圖資料的資料夾
   - 點擊「繪製車輛地圖」按鈕產生車輛路徑地圖
   - 點擊「繪製貨物地圖」按鈕產生貨物位置地圖

### 資料夾結構要求

所選的資料夾必須包含以下CSV檔案：
- `Address.csv`: 地址點位資料
- `Section.csv`: 路段連接資料
- `Port.csv`: 埠口位置資料
- `Shelf.csv`: 貨架位置資料

## 檔案結構說明

```
MapPlot/
├── main.py                     # 主程式入口點
├── mapplot/                    # 核心套件目錄
│   ├── __init__.py            
│   ├── base/                   # 基礎類別
│   │   ├── __init__.py
│   │   └── plotter_base.py     # 繪圖器基礎類別
│   ├── plotters/               # 繪圖器實現
│   │   ├── __init__.py
│   │   ├── cargo_map_plotter.py  # 貨物地圖繪製器
│   │   └── vehicle_map_plotter.py  # 車輛地圖繪製器
│   └── utils/                  # 工具函式
│       ├── __init__.py
│       ├── config.py           # 設定檔
│       ├── data_validator.py   # 資料驗證工具
│       ├── file_cross_validator.py  # 檔案交叉驗證
│       ├── file_utils.py       # 檔案操作工具
│       └── visualization.py    # 視覺化工具函式
├── ui/                         # 使用者介面
│   ├── __init__.py
│   └── map_plot_ui.py          # 圖形使用者介面
└── old/                        # 舊版程式碼(僅供參考)
    ├── map_plot_UI.py
    ├── plot_cargo_map.py
    ├── plot_map.py
    └── plotterBase.py
```

## 維護指南

### 擴展功能

#### 新增繪圖器

若要新增新的地圖繪製功能，請遵循以下步驟：

1. 在 `mapplot/plotters/` 目錄下建立新的繪圖器類別檔案
2. 從 `PlotterBase` 繼承基礎功能
3. 實作 `plot()` 方法
4. 在 UI 類別中整合新的繪圖器

範例：
```python
from ..base.plotter_base import PlotterBase

class NewMapPlotter(PlotterBase):
    def __init__(self):
        super().__init__()
        # 初始化特定屬性
        
    def plot(self):
        # 實作繪圖邏輯
```

#### 修改使用者介面

UI 相關程式碼位於 `ui/map_plot_ui.py`，要增加新功能按鈕或其他介面元素，請修改此檔案中的：

1. `_create_widgets()` 方法: 新增介面元件
2. `_layout_widgets()` 方法: 調整元件佈局

### 資料格式

此工具處理的CSV檔案應具有以下結構：

- **Address.csv**: 
  - 必須欄位: AddressId, X, Y, Direction
  
- **Section.csv**: 
  - 必須欄位: FromAddressId, ToAddressId, Distance

- **Port.csv**:
  - 必須欄位: PortId, AddressId

- **Shelf.csv**:
  - 必須欄位: ShelfId, PortId

### 常見問題排除

#### 找不到必要檔案

確認選擇的資料夾中包含所有必要的CSV檔案: Address.csv, Section.csv, Port.csv, Shelf.csv。

#### 資料格式錯誤

檢查CSV檔案是否具有正確的欄位和資料格式。可參考警報與異常資訊區域的詳細訊息。

#### 繪圖錯誤

若出現繪圖異常，請檢查以下項目：
- 確認CSV檔案中的座標資料格式正確
- 檢查是否有重複的地址ID或路段

## 日誌記錄

工具會在執行過程中記錄操作日誌，重要的警告和錯誤會顯示在UI的警報與異常區域中。

## 開發者資訊

此工具為MMR AGV系統的一部分，用於支援自動導引車輛的地圖管理和視覺化。
