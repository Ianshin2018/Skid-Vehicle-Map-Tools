# TODO: 修改施工區域畫框邏輯

## 任務：將施工區域改成畫出 zone.csv 內每個 addressID 的區域

### 步驟 1: 修改 ui/map_plot_ui.py 中的 _load_zone_for_floor 方法
- [x] 1.1 讀取 zone.csv 時檢查是否有 zone_name 欄位
- [x] 1.2 如果有 zone_name，按分組畫框（每個 zone_name 一個大框）
- [x] 1.3 如果沒有 zone_name，對每個 addressID 畫獨立小框
- [x] 1.4 驗證每個 addressID 是否存在於 Address.csv 中

### 步驟 2: 新增 zoneSection.csv 處理方法 (_load_zone_section_for_floor)
- [x] 2.1 讀取 zoneSection.csv 時檢查是否有 zone_name 欄位
- [x] 2.2 如果有 zone_name，按分組畫框（每個 zone_name 一個大框）
- [x] 2.3 如果沒有 zone_name，對每個路段畫獨立小框
- [x] 2.4 驗證每個 FromAddressId 和 ToAddressId 是否存在於座標中
- [x] 2.5 合併 zone 和 zone_section 圖層

### 步驟 3: 測試與驗證
- [ ] 3.1 執行應用程式確認修改正常運作
- [ ] 3.2 檢查 1F/2F/3F 的施工區域顯示正確

###  dependent Files:
- ui/map_plot_ui.py (_load_zone_for_floor 方法)
- ui/map_plot_ui.py (_load_zone_section_for_floor 方法 - 新增)

### 修改說明:
- zone.csv: 如果有 `zone_name` 欄位，會按 zone_name 分組，每個分組畫一個大框；如果沒有，會對每個 addressID 畫一個獨立的小方框（8x8 大小）
- zoneSection.csv: 如果有 `zone_name` 欄位，會按 zone_name 分組，每個分組畫一個大框；如果沒有，會對每個路段畫一個獨立的小方框
- 兩層圖層會合併在一起顯示：施工位置（藍色）+ 施工路段（橙色）

