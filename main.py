"""
screen_guard_checker.py
对应 Kotlin isAppProtected() 的 Python 模拟版本

目录结构：
  ./img/          ← 放原始截图
  screen_guard_checker.py

用法：
  python screen_guard_checker.py
"""

import os
import sys
import glob
import tkinter as tk
from tkinter import ttk, font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np


# ──────────────────────────────────────────────
#  核心算法（严格对应 Kotlin）
# ──────────────────────────────────────────────

SIZE = 64


def is_app_protected(img: Image.Image) -> tuple[bool, dict]:
    """
    对应 Kotlin private fun isAppProtected(bitmap: Bitmap): Boolean

    Returns
    -------
    (is_protected, stats_dict)
    """

    # 1. 缩小到 64×64（对应 bitmap.scale(size, size, false)）
    scaled = img.resize((SIZE, SIZE), Image.NEAREST)

    # 2. 强制转 RGB（对应强制转 ARGB_8888 软件位图）
    rgb = scaled.convert("RGB")

    # 3. 一次性读取像素（对应 getPixels）
    pixels = np.array(rgb, dtype=np.float32)  # shape (64, 64, 3)

    # 4. 忽略边缘（对应 ignore = (size * 0.08).toInt()）
    ignore = int(SIZE * 0.08)  # == 5

    # 5. 采样（step=2，对应 Kotlin step）
    step = 2

    sum_l   = 0.0
    sum_sq  = 0.0
    count   = 0
    near_black = 0

    for y in range(ignore, SIZE - ignore, step):
        for x in range(ignore, SIZE - ignore, step):
            r, g, b = pixels[y, x]
            # 对应 val l = 0.299 * r + 0.587 * g + 0.114 * b
            l = 0.299 * r + 0.587 * g + 0.114 * b
            sum_l  += l
            sum_sq += l * l
            count  += 1
            if l < 10:            # 对应 if (l < 10) nearBlackCount++
                near_black += 1

    if count == 0:
        return False, {}

    # 6. 均值 & 方差（对应 Kotlin）
    mean     = sum_l / count
    variance = sum_sq / count - mean * mean

    # 7. 极值占比
    black_ratio = near_black / count

    # 8. 判断条件（直接对应 Kotlin 两行）
    is_nearly_uniform   = variance   < 15.0
    is_dominantly_black = black_ratio > 0.85 and mean < 15.0

    protected = is_nearly_uniform and is_dominantly_black

    stats = {
        "mean"              : mean,
        "variance"          : variance,
        "black_ratio"       : black_ratio,
        "count"             : count,
        "near_black"        : near_black,
        "is_nearly_uniform" : is_nearly_uniform,
        "is_dominantly_black": is_dominantly_black,
    }
    return protected, stats


# ──────────────────────────────────────────────
#  辅助：生成 64×64 可视化图（放大后显示）
# ──────────────────────────────────────────────

DISPLAY_SIZE = 256   # 展示时放大到这个尺寸
IGNORE_PX    = int(SIZE * 0.08)   # == 5


def make_processed_visual(img: Image.Image) -> Image.Image:
    """
    生成 64×64 缩放图，并在放大版上标出：
    - 红色边框 = 忽略区域
    - 青色网格 = 实际采样点
    """
    scaled = img.resize((SIZE, SIZE), Image.NEAREST).convert("RGB")

    # 放大到 DISPLAY_SIZE 方便肉眼观察
    big = scaled.resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.NEAREST)
    draw = ImageDraw.Draw(big, "RGBA")
    cell = DISPLAY_SIZE / SIZE

    # 忽略边缘半透明红色蒙版
    ig = IGNORE_PX * cell
    draw.rectangle(
        [(0, 0), (DISPLAY_SIZE - 1, DISPLAY_SIZE - 1)],
        outline=(255, 60, 60, 200), width=int(ig)
    )

    # 采样点 = 青色小圆点
    step = 2
    r = max(1, int(cell * 0.25))
    for y in range(IGNORE_PX, SIZE - IGNORE_PX, step):
        for x in range(IGNORE_PX, SIZE - IGNORE_PX, step):
            cx = int((x + 0.5) * cell)
            cy = int((y + 0.5) * cell)
            draw.ellipse(
                (cx - r, cy - r, cx + r, cy + r),
                fill=(0, 220, 220, 160)
            )
    return big


def make_result_image(protected: bool, stats: dict) -> Image.Image:
    """生成结果面板图（纯文字信息）"""
    W, H = DISPLAY_SIZE, DISPLAY_SIZE
    bg_color = (18, 18, 18)
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # 大标题颜色
    label_color = (220, 60, 60) if protected else (60, 200, 100)
    label_text  = "BLOCK" if protected else "PASS"

    # 尝试加载等宽字体，失败回退到默认
    try:
        fnt_big  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 32)
        fnt_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11)
    except Exception:
        fnt_big  = ImageFont.load_default()
        fnt_small = fnt_big

    # 状态大字
    draw.text((W // 2, 36), label_text, fill=label_color, font=fnt_big, anchor="mm")

    # 分割线
    draw.line([(16, 66), (W - 16, 66)], fill=(80, 80, 80), width=1)

    if stats:
        lines = [
            f"mean       : {stats['mean']:.2f}",
            f"variance   : {stats['variance']:.4f}",
            f"black_ratio: {stats['black_ratio']:.4f}",
            f"count      : {stats['count']}",
            f"near_black : {stats['near_black']}",
            "",
            f"uniform? (var<15)   {'✓' if stats['is_nearly_uniform'] else '✗'}",
            f"dom.black? (r>.85   {'✓' if stats['is_dominantly_black'] else '✗'}",
            f"           &μ<15)  ",
            "",
            f"→ isProtected: {protected}",
        ]
        y0 = 80
        for line in lines:
            col = (200, 200, 200)
            if "✓" in line:
                col = (60, 200, 100)
            elif "✗" in line:
                col = (220, 80, 80)
            elif "→" in line:
                col = label_color
            draw.text((16, y0), line, fill=col, font=fnt_small)
            y0 += 14

    return img


# ──────────────────────────────────────────────
#  GUI
# ──────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self, image_paths: list[str]):
        super().__init__()
        self.title("Screen Guard Checker")
        self.configure(bg="#1a1a1a")
        self.resizable(False, False)

        self.paths   = image_paths
        self.index   = 0

        self._build_ui()
        self._load_current()

    # ── 布局 ──────────────────────────────────
    def _build_ui(self):
        PANEL_W = DISPLAY_SIZE
        PANEL_H = DISPLAY_SIZE

        # ── 标题行
        title_bar = tk.Frame(self, bg="#111", pady=6)
        title_bar.pack(fill="x")
        tk.Label(
            title_bar, text="■ Screen Guard Checker",
            bg="#111", fg="#e0e0e0",
            font=("Courier", 12, "bold")
        ).pack(side="left", padx=12)

        # ── 三列面板
        panels_frame = tk.Frame(self, bg="#1a1a1a")
        panels_frame.pack(padx=12, pady=8)

        headers = ["Raw", "Processed (64×64)", "Result"]
        self.canvases = []
        for i, h in enumerate(headers):
            col = tk.Frame(panels_frame, bg="#1a1a1a")
            col.grid(row=0, column=i, padx=6)

            tk.Label(
                col, text=h, bg="#1a1a1a", fg="#888",
                font=("Courier", 9)
            ).pack(pady=(0, 4))

            canvas = tk.Canvas(
                col, width=PANEL_W, height=PANEL_H,
                bg="#0d0d0d", highlightthickness=1,
                highlightbackground="#333"
            )
            canvas.pack()
            self.canvases.append(canvas)

        # ── 信息行
        self.info_var = tk.StringVar()
        info_label = tk.Label(
            self, textvariable=self.info_var,
            bg="#1a1a1a", fg="#aaa",
            font=("Courier", 9), anchor="w", justify="left"
        )
        info_label.pack(fill="x", padx=18, pady=2)

        # ── 导航行
        nav = tk.Frame(self, bg="#1a1a1a", pady=8)
        nav.pack()

        btn_style = dict(
            bg="#2a2a2a", fg="#ccc",
            font=("Courier", 10),
            relief="flat", padx=16, pady=4,
            activebackground="#3a3a3a", activeforeground="#fff",
            cursor="hand2"
        )
        tk.Button(nav, text="◀  Prev", command=self._prev, **btn_style).pack(side="left", padx=6)

        self.nav_var = tk.StringVar()
        tk.Label(nav, textvariable=self.nav_var, bg="#1a1a1a", fg="#666",
                 font=("Courier", 10), width=12).pack(side="left")

        tk.Button(nav, text="Next  ▶", command=self._next, **btn_style).pack(side="left", padx=6)

    # ── 导航 ──────────────────────────────────
    def _prev(self):
        if self.index > 0:
            self.index -= 1
            self._load_current()

    def _next(self):
        if self.index < len(self.paths) - 1:
            self.index += 1
            self._load_current()

    # ── 加载 & 分析 ───────────────────────────
    def _load_current(self):
        path = self.paths[self.index]
        self.nav_var.set(f"{self.index + 1} / {len(self.paths)}")

        # 加载原图
        original = Image.open(path).convert("RGB")

        # 分析
        protected, stats = is_app_protected(original)

        # 三张显示图
        raw_disp      = original.copy()
        raw_disp.thumbnail((DISPLAY_SIZE, DISPLAY_SIZE), Image.LANCZOS)
        raw_padded    = _pad_to(raw_disp, DISPLAY_SIZE, DISPLAY_SIZE)

        processed_img = make_processed_visual(original)
        result_img    = make_result_image(protected, stats)

        # 刷新三个 canvas
        self._tk_images = []   # 防止 GC
        for canvas, pil_img in zip(
            self.canvases,
            [raw_padded, processed_img, result_img]
        ):
            tk_img = ImageTk.PhotoImage(pil_img)
            self._tk_images.append(tk_img)
            canvas.delete("all")
            canvas.create_image(DISPLAY_SIZE // 2, DISPLAY_SIZE // 2, image=tk_img)

        # 底部信息
        fname = os.path.basename(path)
        w, h  = original.size
        self.info_var.set(
            f"  {fname}  ({w}×{h})   "
            f"mean={stats.get('mean', 0):.1f}  "
            f"var={stats.get('variance', 0):.2f}  "
            f"black_ratio={stats.get('black_ratio', 0):.3f}"
        )

        # 终端输出
        verdict = "BLOCK (isProtected=true)" if protected else "PASS  (isProtected=false)"
        print(f"[{fname}]  {verdict}")
        if stats:
            print(f"  mean={stats['mean']:.2f}  variance={stats['variance']:.4f}"
                  f"  black_ratio={stats['black_ratio']:.4f}  count={stats['count']}")
        print()


def _pad_to(img: Image.Image, w: int, h: int) -> Image.Image:
    """居中填充到指定尺寸（黑色背景）"""
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    x = (w - img.width)  // 2
    y = (h - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


# ──────────────────────────────────────────────
#  入口
# ──────────────────────────────────────────────

def find_images(base_dir: str) -> list[str]:
    exts = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp")
    found = []
    for ext in exts:
        found.extend(glob.glob(os.path.join(base_dir, ext)))
    return sorted(found)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_dir    = os.path.join(script_dir, "img")

    if not os.path.isdir(img_dir):
        print(f"[Error] 找不到 ./img 目录: {img_dir}")
        print("请在脚本同级目录下创建 img/ 并放入截图。")
        sys.exit(1)

    paths = find_images(img_dir)
    if not paths:
        print(f"[Error] ./img 里没有找到图片 (png/jpg/jpeg/webp/bmp)")
        sys.exit(1)

    print(f"找到 {len(paths)} 张图片，开始分析...\n")
    print("=" * 55)

    app = App(paths)
    app.mainloop()


if __name__ == "__main__":
    main()