# TODO List - 依照 README.md 修改程式

## 修改項目清單

### Phase 1: 版本與基本 UI 更新 ✅ 完成
- [x] 1. 更新版本號為 V1.0.3
- [x] 2. 建立功能列 (Menu Bar) - 檔案/顯示選單
- [x] 3. 修正排名 checkbox 文字

### Phase 2: 按鈕功能 ✅ 完成
- [x] 4. 新增「全圖」按鈕
- [x] 5. 新增放大鏡 checkbox

### Phase 3: 放大鏡功能 ✅ 完成
- [x] 6. 建立放大鏡顯示區域 (160x160, 右下角)
- [x] 7. 實作 8 倍放大功能
- [x] 8. 加入 50ms 防抖延遲
- [x] 9. 位置快取機制 (<10 像素跳過更新)

### Phase 4: 其他功能 ✅ 完成
- [x] 10. image_processor.py 新增 zoom_full() 方法
- [x] 11. image_processor.py 新增放大鏡相關方法

---

## 已完成的修改摘要

### ui/map_plot_ui.py:
- 版本號: V1.0.0 → V1.0.3
- 新增 Menu Bar (檔案、顯示選單)
- 新增「全圖」按鈕 (zoom_full_btn)
- 新增放大鏡 checkbox 和顯示區域
- 排名 checkbox 文字從 "顯示車輛打滑位置(先選擇日期才可顯示)" 改為 "顯示車輛位置"

### ui/image_processor.py:
- 新增 zoom_full() 方法 - 重置縮放比例為預設值 0.2
- 新增 _on_canvas_mouse_move() 方法 - 處理放大鏡滑鼠移動
- 新增 _update_magnifier() 方法 - 更新放大鏡顯示 (8倍放大, 50ms防抖, 位置快取)

