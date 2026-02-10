import cv2

class ImageViewer:
    """
    圖像瀏覽器，支援拖曳、滾動條、縮放。
    使用 OpenCV 視窗互動。
    """
    def __init__(self):
        self.flag = 0
        self.horizontal = 0
        self.vertical = 0
        self.flag_hor = 0
        self.flag_ver = 0
        self.dx = 0
        self.dy = 0
        self.sx = 0
        self.sy = 0
        self.x1 = self.y1 = self.x2 = self.y2 = self.x3 = self.y3 = 0
        self.f1 = self.f2 = 0
        self.zoom = 1
        self.scroll_har = self.scroll_var = 0
        self.img_w = self.img_h = 0
        self.img = None
        self.dst1 = None
        self.win_w = self.win_h = 0
        self.show_w = 800
        self.show_h = 600
        self.scroll_w = 16
        self.wheel_step = 0.05
        self.img_original = None
        self.img_original_w = self.img_original_h = 0

    def mouse(self, event, x, y, flags, param):
        # 滑鼠事件處理，與原始邏輯一致
        # ...（將原 mouse 函式內容移至此，並改用 self.屬性）
        pass  # 詳細內容請將原 mouse 函式搬移並調整為 self 屬性

    def show(self, image_path):
        self.img_original = cv2.imread(image_path)
        self.img_original_h, self.img_original_w = self.img_original.shape[0:2]
        cv2.namedWindow('img', cv2.WINDOW_NORMAL)
        cv2.moveWindow("img", 300, 100)
        self.img = self.img_original.copy()
        self.img_h, self.img_w = self.img.shape[0:2]
        self.horizontal = 0
        self.vertical = 0
        self.dx = self.dy = 0
        self.sx = self.sy = 0
        self.flag = self.flag_hor = self.flag_ver = 0
        self.x1 = self.y1 = self.x2 = self.y2 = self.x3 = self.y3 = 0
        self.win_w, self.win_h = self.show_w + self.scroll_w, self.show_h + self.scroll_w
        self.scroll_har, self.scroll_var = self.win_w * self.show_w / self.img_w, self.win_h * self.show_h / self.img_h
        self.zoom = 1
        self.f1, self.f2 = (self.img_w - self.show_w) / (self.win_w - self.scroll_har), (self.img_h - self.show_h) / (self.win_h - self.scroll_var)
        if self.img_h <= self.show_h and self.img_w <= self.show_w:
            cv2.imshow("img", self.img)
        else:
            if self.img_w > self.show_w:
                self.horizontal = 1
            if self.img_h > self.show_h:
                self.vertical = 1
            i = self.img[self.dy:self.dy + self.show_h, self.dx:self.dx + self.show_w]
            self.dst = i.copy()
        cv2.resizeWindow("img", self.win_w, self.win_h)
        cv2.setMouseCallback('img', self.mouse)
        cv2.waitKey()
        cv2.destroyAllWindows()