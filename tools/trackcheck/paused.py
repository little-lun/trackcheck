# -*- coding: utf-8 -*-
"""
paused.py —— 从录像里剔除「GAME PAUSED」时段

暂停框特征：画面中上部一块**深灰蓝面板**（约 #3c3c4c），带浅色边框。
草坪是绿色（G 明显大于 R/B），所以判据取：
    中心区域里「暗 + 低彩度」像素的占比
    正常游戏 < 8%，暂停时 > 30%
"""
import os
import sys
from PIL import Image

TH = 0.18          # 暗灰像素占比阈值
REGION = (0.10, 0.06, 0.62, 0.55)   # 相对包围盒 (l, t, r, b)


def dark_ratio(path):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    l, t, r, b = [int(v * (w if i % 2 == 0 else h)) for i, v in enumerate(REGION)]
    px = im.crop((l, t, r, b)).getdata()
    n = ok = 0
    for R, G, B in px:
        n += 1
        mx = max(R, G, B)
        if mx < 115 and abs(R - G) < 28 and abs(G - B) < 32:
            ok += 1
    return ok / max(1, n)


def scan(folder, fps=1.0):
    files = sorted(os.listdir(folder))
    flags = []
    for fn in files:
        if not fn.endswith('.png'):
            continue
        flags.append(dark_ratio(os.path.join(folder, fn)) > TH)
    segs, cur = [], None
    for i, p in enumerate(flags):
        if p and cur is None:
            cur = i
        elif not p and cur is not None:
            segs.append((cur / fps, i / fps))
            cur = None
    if cur is not None:
        segs.append((cur / fps, len(flags) / fps))
    # 合并 1s 内的碎片
    merged = []
    for a, b in segs:
        if merged and a - merged[-1][1] <= 1.5:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    total = sum(b - a for a, b in merged)
    return merged, total, len(flags)


if __name__ == '__main__':
    folder = sys.argv[1]
    segs, total, n = scan(folder)
    print('帧数 %d（%ds）' % (n, n))
    print('暂停段 %d 段，合计 %.1fs（占 %.0f%%）'
          % (len(segs), total, 100 * total / max(1, n)))
    print('有效游戏时长 ≈ %.1fs = %.2f 分钟' % (n - total, (n - total) / 60))
    print('前 12 段：')
    for a, b in segs[:12]:
        print('   %6.1fs ~ %6.1fs  (%.1fs)' % (a, b, b - a))
