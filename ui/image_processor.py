"""
影像處理模組
提供圖片顯示、縮放、平移、圖層切換等功能
"""
import logging
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont


class ImageProcessor:
    """
    影像處理類別
    負責圖片顯示、縮放、平移等相關功能
    """
    def __init__(self, ui_instance):
        """初始化影像處理器
        
        Args:
            ui_instance: UI 物件實例
        """
        self.ui = ui_instance
        
    def show_image_on_canvas(self, pil_img):
        """將 PIL 影像依照畫布大小與縮放比例縮放並致中顯示於 output_canvas 上"""
        self.ui._original_pil_img = pil_img  # 儲存原始圖片
        self._draw_scaled_image()

    def _draw_scaled_image(self):
        if self.ui._original_pil_img is None:
            return
        canvas_width = self.ui.output_canvas.winfo_width()
        canvas_height = self.ui.output_canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            self.ui.output_canvas.update()
            canvas_width = self.ui.output_canvas.winfo_width()
            canvas_height = self.ui.output_canvas.winfo_height()
        img_w, img_h = self.ui._original_pil_img.size
        scale = self.ui._image_scale
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        resized_img = self.ui._original_pil_img.resize((new_w, new_h), Image.LANCZOS)
        self.ui._tk_img = ImageTk.PhotoImage(resized_img)
        self.ui.output_canvas.delete("all")

        # 讓圖片左上角永遠在(0,0)，scrollregion設為圖片大小
        self.ui.output_canvas.create_image(0, 0, anchor="nw", image=self.ui._tk_img)
        self.ui.output_canvas.config(scrollregion=(0, 0, new_w, new_h))

        if getattr(self.ui, "_canvas_first_show", True):
            if new_w > canvas_width:
                self.ui.output_canvas.xview_moveto((new_w - canvas_width) / 2 / new_w)
            else:
                self.ui.output_canvas.xview_moveto(0)
            if new_h > canvas_height:
                self.ui.output_canvas.yview_moveto((new_h - canvas_height) / 2 / new_h)
            else:
                self.ui.output_canvas.yview_moveto(0)
            self.ui._canvas_first_show = False

    def zoom_in(self):
        """放大影像"""
        self.ui._image_scale = min(self.ui._image_scale * 1.2, 5.0)
        self._draw_scaled_image()

    def zoom_out(self):
        """縮小影像"""
        self.ui._image_scale = max(self.ui._image_scale / 1.2, 0.01)
        self._draw_scaled_image()

    def zoom_image(self, in_out):
        """縮放畫布上的影像

        Args:
            in_out (int): 縮放因子，正值放大，負值縮小
        """
        if not hasattr(self.ui, '_original_pil_img') or self.ui._original_pil_img is None:
            return

        # 計算新縮放比例
        new_scale = self.ui._image_scale + in_out * 0.1
        if new_scale <= 0.1:
            new_scale = 0.1  # 設定最小縮放比例

        # 重新計算影像大小
        new_w = int(self.ui._original_pil_img.width * new_scale)
        new_h = int(self.ui._original_pil_img.height * new_scale)
        resized_img = self.ui._original_pil_img.resize((new_w, new_h), Image.LANCZOS)

        # 更新顯示影像
        self.show_image_on_canvas(resized_img)

        # 更新當前縮放比例
        self.ui._image_scale = new_scale

    def _start_move(self, event):
        """開始平移"""
        self.ui.output_canvas.scan_mark(event.x, event.y)

    def _move_canvas(self, event):
        """平移畫布"""
        self.ui.output_canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_canvas_resize(self, event):
        """畫布大小變化時，將放大縮小按鈕固定在右上角"""
        # 右邊預留一點間距
        btn_y = 10
        btn_margin = 10
        btn_spacing = 5
        btn_width = self.ui.zoom_in_btn.winfo_reqwidth()
        canvas_w = event.width
        self.ui.zoom_in_btn.place(in_=self.ui.output_canvas, x=canvas_w - btn_width*2 - btn_spacing - btn_margin, y=btn_y)
        self.ui.zoom_out_btn.place(in_=self.ui.output_canvas, x=canvas_w - btn_width - btn_margin, y=btn_y)
        # 固定樓層按鈕在畫布左上角
        for idx, btn in enumerate(self.ui.floor_buttons.values()):
            btn.place(in_=self.ui.output_canvas, x=10, y=10+idx*35)

    def _on_mousewheel(self, event):
        """
        以滑鼠游標為焦點縮放畫布上的影像（支援 Windows/macOS/Linux）。
        需按住 Ctrl 才觸發縮放；未按 Ctrl 時執行一般垂直捲動。
        """
        # 未按 Ctrl 時，交還給畫布做一般捲動
        if not (event.state & 0x4):
            delta = 0
            if hasattr(event, 'delta') and event.delta:
                delta = -1 if event.delta > 0 else 1
            elif hasattr(event, 'num'):
                delta = -1 if event.num == 4 else 1
            self.ui.output_canvas.yview_scroll(delta, "units")
            return

        if not hasattr(self.ui, '_original_pil_img') or self.ui._original_pil_img is None:
            return

        old_scale = getattr(self.ui, "_image_scale", 1.0)
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
        self.ui.output_canvas.update_idletasks()

        # 取得滑鼠在螢幕的絕對位置，再轉為 canvas widget 的相對座標
        try:
            px = self.ui.output_canvas.winfo_pointerx()
            py = self.ui.output_canvas.winfo_pointery()
            widget_x = px - self.ui.output_canvas.winfo_rootx()
            widget_y = py - self.ui.output_canvas.winfo_rooty()
        except Exception:
            widget_x = getattr(event, 'x', 0)
            widget_y = getattr(event, 'y', 0)

        # 取得 canvas 上對應的 canvas-coords（包含當前滾動位移）
        canvas_x = self.ui.output_canvas.canvasx(widget_x)
        canvas_y = self.ui.output_canvas.canvasy(widget_y)

        # 轉回原始 image 座標（以 old_scale）
        img_x = canvas_x / old_scale
        img_y = canvas_y / old_scale

        # 設定新比例並重繪
        self.ui._image_scale = new_scale
        self._draw_scaled_image()

        # 重新確保 widget 與 image 更新
        self.ui.output_canvas.update_idletasks()

        # 計算新的 canvas 座標（image 在 canvas 中的坐標）
        new_canvas_x = img_x * new_scale
        new_canvas_y = img_y * new_scale

        # 計算新尺寸與 viewport
        new_w = max(int(self.ui._original_pil_img.width * new_scale), 1)
        new_h = max(int(self.ui._original_pil_img.height * new_scale), 1)
        canvas_w = max(self.ui.output_canvas.winfo_width(), 1)
        canvas_h = max(self.ui.output_canvas.winfo_height(), 1)

        # 計算 left/top（希望可視區的左上座標）
        desired_left = new_canvas_x - widget_x
        desired_top = new_canvas_y - widget_y

        # 計算 fraction，分母使用 scrollable range
        scrollable_w = max(new_w - canvas_w, 1)
        scrollable_h = max(new_h - canvas_h, 1)

        frac_x = desired_left / float(scrollable_w)
        frac_y = desired_top / float(scrollable_h)

        frac_x = self._clamp(frac_x, 0.0, 1.0)
        frac_y = self._clamp(frac_y, 0.0, 1.0)

        try:
            self.ui.output_canvas.xview_moveto(frac_x)
        except Exception:
            pass
        try:
            self.ui.output_canvas.yview_moveto(frac_y)
        except Exception:
            pass

    def _clamp(self, v, lo, hi):
        """將 v 限制在 [lo, hi] 範圍內"""
        try:
            return max(lo, min(hi, v))
        except Exception:
            return lo

    def toggle_layers(self):
        """切換圖層顯示（施工區域和打滑位置）"""
        try:
            # 獲取各圖層的顯示狀態
            show_zone = getattr(self.ui, '_show_zone_var', None)
            if show_zone:
                show_zone = show_zone.get() == 1
            else:
                show_zone = True

            show_highlight = getattr(self.ui, '_show_highlight_var', None)
            if show_highlight:
                show_highlight = show_highlight.get() == 1
            else:
                show_highlight = True

            if not hasattr(self.ui, '_base_pil_img') or self.ui._base_pil_img is None:
                return

            # 從底圖開始
            result_img = self.ui._base_pil_img.copy()

            # 第二層：施工區域
            if show_zone and hasattr(self.ui, '_zone_pil_img') and self.ui._zone_pil_img:
                zone_img = self.ui._zone_pil_img
                if zone_img.size != result_img.size:
                    zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
                result_img = Image.alpha_composite(result_img, zone_img)

            # 第三層：打滑位置
            has_dates = bool(self.ui._get_selected_dates()) if hasattr(self.ui, '_get_selected_dates') else False
            if show_highlight and has_dates and hasattr(self.ui, '_overlay_pil_img') and self.ui._overlay_pil_img:
                overlay_img = self.ui._overlay_pil_img
                if overlay_img.size != result_img.size:
                    overlay_img = overlay_img.resize(result_img.size, Image.LANCZOS)
                result_img = Image.alpha_composite(result_img, overlay_img)

            # 顯示合成後的圖像
            self.show_image_on_canvas(result_img)

            # 更新狀態
            zone_status = "顯示" if show_zone else "隱藏"
            highlight_status = "顯示" if show_highlight else "隱藏"
            if hasattr(self.ui, '_update_status'):
                self.ui._update_status(f"圖層: 施工區域[{zone_status}] 打滑位置[{highlight_status}]")

        except Exception as e:
            logging.error(f"切換圖層失敗: {e}")

    def _on_canvas_right_click(self, event):
        """右鍵點擊畫布：若點到打滑位置則顯示 ID 與路徑資訊"""
        if not hasattr(self.ui, '_get_selected_dates'):
            return
        dates = self.ui._get_selected_dates()
        if not dates:
            return
            
        plotter = getattr(self.ui, 'vehicle_map_plotter', None)
        if not plotter:
            return
        hit_areas = getattr(plotter, 'highlight_hit_areas', [])
        xlim = getattr(plotter, '_ax_xlim', None)
        ylim = getattr(plotter, '_ax_ylim', None)
        base_img = getattr(self.ui, '_base_pil_img', None)
        if not hit_areas or not xlim or not ylim or not base_img:
            return

        # canvas 座標 → 全解析度圖片像素座標
        cx = self.ui.output_canvas.canvasx(event.x)
        cy = self.ui.output_canvas.canvasy(event.y)
        scale = self.ui._image_scale
        img_px_x = cx / scale
        img_px_y = cy / scale

        # 圖片像素 → matplotlib data 座標
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
        """在點擊位置旁顯示打滑位置資訊的浮動小視窗（4秒後自動關閉）"""
        # 關閉上一個
        prev = getattr(self.ui, '_highlight_popup', None)
        if prev:
            try:
                prev.destroy()
            except Exception:
                pass

        import tkinter as tk
        if info['type'] == 'address':
            text = f"Address ID：{info['id']}"
        else:
            text = (f"Section ID：{info['id']}\n"
                    f"起點 (From)：{info['from_addr']}\n"
                    f"終點 (To)：{info['to_addr']}")

        popup = tk.Toplevel(self.ui.root)
        popup.wm_overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

        frame = tk.Frame(popup, bd=1, relief=tk.SOLID, bg="#FFFDE7")
        frame.pack()
        tk.Label(frame, text=text, bg="#FFFDE7", fg="#333333",
                 padx=10, pady=6, justify=tk.LEFT,
                 font=("Microsoft YaHei", 9)).pack()

        self.ui._highlight_popup = popup
        popup.after(4000, lambda: popup.destroy() if popup.winfo_exists() else None)

    def highlight_vehicle_boxes(self, vehicle_number, addr_ids, sec_ids):
        """在畫布上高亮顯示特定車輛的打滑方框（黃色方框，4 秒後自動清除）"""
        try:
            plotter = getattr(self.ui, 'vehicle_map_plotter', None)
            if not plotter:
                return
            hit_areas = getattr(plotter, 'highlight_hit_areas', [])
            xlim = getattr(plotter, '_ax_xlim', None)
            ylim = getattr(plotter, '_ax_ylim', None)
            base_img = getattr(self.ui, '_base_pil_img', None)
            if not hit_areas or not xlim or not ylim or not base_img:
                return

            # 清除上一次的高亮
            self._clear_vehicle_highlights()

            img_w, img_h = base_img.size
            scale = self.ui._image_scale
            canvas = self.ui.output_canvas

            items_created = []
            for area in hit_areas:
                aid = str(area['id']).strip()
                if area['type'] == 'address' and aid in addr_ids:
                    match = True
                elif area['type'] == 'section' and aid in sec_ids:
                    match = True
                else:
                    match = False
                if not match:
                    continue

                # 資料座標 → 畫布像素座標
                cx1 = (area['xmin'] - xlim[0]) / (xlim[1] - xlim[0]) * img_w * scale
                cx2 = (area['xmax'] - xlim[0]) / (xlim[1] - xlim[0]) * img_w * scale
                cy1 = (ylim[1] - area['ymax']) / (ylim[1] - ylim[0]) * img_h * scale
                cy2 = (ylim[1] - area['ymin']) / (ylim[1] - ylim[0]) * img_h * scale

                rect_id = canvas.create_rectangle(
                    cx1, cy1, cx2, cy2,
                    outline='green', width=4, tags='vehicle_highlight'
                )
                items_created.append(rect_id)

            self.ui._vehicle_highlight_items = items_created

            if items_created:
                logging.info(f"車輛 {vehicle_number}: 高亮 {len(items_created)} 個打滑方框")
            else:
                logging.info(f"車輛 {vehicle_number}: 在目前畫布上找不到對應的打滑方框")
        except Exception as e:
            logging.error(f"高亮車輛方框失敗: {e}")

    def _clear_vehicle_highlights(self):
        """清除車輛高亮方框"""
        try:
            items = getattr(self.ui, '_vehicle_highlight_items', [])
            for item_id in items:
                try:
                    self.ui.output_canvas.delete(item_id)
                except Exception:
                    pass
            self.ui._vehicle_highlight_items = []
        except Exception as e:
            logging.error(f"清除高亮方框失敗: {e}")

    def export_canvas_image(self):
        """匯出當前畫布畫面（含圖例），讓使用者選擇儲存位置"""
        if not hasattr(self.ui, '_base_pil_img') or self.ui._base_pil_img is None:
            import tkinter.messagebox as messagebox
            messagebox.showwarning("警告", "請先載入地圖")
            return

        # 依 checkbutton 狀態重建合成圖
        show_zone = getattr(self.ui, '_show_zone_var', None)
        if show_zone:
            show_zone = show_zone.get() == 1
        else:
            show_zone = True
            
        show_highlight = getattr(self.ui, '_show_highlight_var', None)
        if show_highlight:
            show_highlight = show_highlight.get() == 1
        else:
            show_highlight = True

        result_img = self.ui._base_pil_img.copy().convert("RGBA")

        if show_zone and hasattr(self.ui, '_zone_pil_img') and self.ui._zone_pil_img:
            zone_img = self.ui._zone_pil_img.convert("RGBA")
            if zone_img.size != result_img.size:
                zone_img = zone_img.resize(result_img.size, Image.LANCZOS)
            result_img = Image.alpha_composite(result_img, zone_img)

        if show_highlight and hasattr(self.ui, '_overlay_pil_img') and self.ui._overlay_pil_img:
            overlay_img = self.ui._overlay_pil_img.convert("RGBA")
            if overlay_img.size != result_img.size:
                overlay_img = overlay_img.resize(result_img.size, Image.LANCZOS)
            result_img = Image.alpha_composite(result_img, overlay_img)

        # 建立圖例並水平拼接
        legend_img = self._build_legend_image(result_img.height, show_zone, show_highlight)
        combined = Image.new("RGBA", (result_img.width + legend_img.width, result_img.height), (255, 255, 255, 255))
        combined.paste(result_img, (0, 0))
        combined.paste(legend_img, (result_img.width, 0))

        # 選擇儲存位置
        import tkinter as tk
        from tkinter import filedialog
        floor_label = getattr(self.ui, '_current_floor', '')
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
        
        import tkinter.messagebox as messagebox
        messagebox.showinfo("成功", f"圖片已儲存至：\n{save_path}")
        logging.info(f"圖片已匯出至 {save_path}")

    def _build_legend_image(self, height, show_zone=True, show_highlight=True):
        """建立圖例 PIL Image，與地圖等高後拼接於右側"""
        legend_w = 230
        padding = 20
        item_h = 45
        swatch_w, swatch_h = 24, 18

        # 固定圖例項目
        items = [("行駛方向", (0, 0, 255), "arrow")]
        if show_zone:
            items.append(("施工區域", (135, 206, 235), "rect_filled"))
        if show_highlight:
            items.append(("打滑打滑方框位置", (255, 0, 0), "rect_outline"))
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

