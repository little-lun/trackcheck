# -*- coding: utf-8 -*-
"""
video.py —— 从运阵录像抽时间线

三个信号：
  ① **帧间差分** → 暂停段（PvZ 暂停时画面基本不动，即使背景有轻微抖动）
  ② **红色横幅** → 旗帜波（"A huge wave of zombies is approaching!"）
  ③ 右侧进场区的僵尸像素占比 → 场上压力

用法：
  python tools/trackcheck/video.py <帧目录> [fps]
输出：逐秒表 + 暂停总时长 + 旗帜波时刻
"""
import os
import sys
from PIL import Image, ImageChops


def load(fn):
    return Image.open(fn).convert('RGB')


def diff_score(a, b):
    d = ImageChops.difference(a, b).convert('L')
    h = d.histogram()
    tot = sum(h)
    # 平均绝对差
    return sum(i * h[i] for i in range(256)) / float(tot)


def red_banner(im):
    """旗帜波横幅：中下部横向一片鲜红文字"""
    W, H = im.size
    px = im.load()
    x0, x1 = int(W * 0.10), int(W * 0.90)
    y0, y1 = int(H * 0.58), int(H * 0.80)
    red = tot = 0
    for y in range(y0, y1, 3):
        for x in range(x0, x1, 3):
            r, g, b = px[x, y]
            tot += 1
            if r > 120 and r > g * 2.0 and r > b * 2.0:
                red += 1
    return red / float(tot) if tot else 0.0


def main():
    folder = sys.argv[1]
    fps = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    files = sorted(f for f in os.listdir(folder) if f.endswith('.png'))

    prev = None
    rows = []
    for i, fn in enumerate(files):
        im = load(os.path.join(folder, fn))
        im2 = im.resize((320, int(320 * im.size[1] / im.size[0])))
        d = diff_score(prev, im2) if prev is not None else 99.0
        prev = im2
        rows.append((i / fps, d, red_banner(im)))

    diffs = sorted(r[1] for r in rows[1:])
    med = diffs[len(diffs) // 2]
    print('帧数 %d  帧间差分中位数 %.2f  最小 %.2f  最大 %.2f'
          % (len(rows), med, diffs[0], diffs[-1]))
    thr = max(0.35, diffs[0] * 3)
    print('暂停阈值 %.2f' % thr)
    print()
    print('  时刻(s)  差分   红幅   状态')
    paused_t = 0.0
    banners = []
    prev_b = False
    for t, d, r in rows:
        is_p = d < thr
        if is_p:
            paused_t += 1.0 / fps
        b = r > 0.010
        if b and not prev_b:
            banners.append(t)
        prev_b = b
        mark = 'PAUSE' if is_p else ''
        rb = '★' if b else ' '
        print('%8.1f %6.2f %6.4f %s %s' % (t, d, r, rb, mark))
    print()
    print('暂停合计 %.1fs / 总 %.1fs → 有效 %.1fs'
          % (paused_t, rows[-1][0] + 1, rows[-1][0] + 1 - paused_t))
    print('旗帜波(红幅)时刻: %s' % ['%.0fs' % x for x in banners])


if __name__ == '__main__':
    main()
