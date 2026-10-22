"""
video_analyze.py —— 一次扫描拿到录像的全部标定指标

合并了 video_probe（暂停）与 text_scan（红白字）两套判据，避免重复解码。

用法：
    python -m tools.trackcheck.video_analyze "xx.mp4" --json out.json

输出（10fps 时间序列）：
    pause        1 = 暂停面板（深灰蓝矩形）存在
    red_rowmax   上中横带内「单行红色像素数 ÷ 宽度」的最大值
    red_rows     红色像素数超过该带宽度 12% 的「行数」（一行文字有 6~12 行）
    white_rowmax 同上，纯白
    white_rows   同上，纯白
    field        右侧进场区「非草坪」像素占比

标定依据：
    暂停面板   t=95s 实测，内部纯色竖带 (R,G,B)≈(66,66,91)、(61,60,84)
               → G≈R 且 B−G≈+25；正常画面 G 明显占优
    红字       t=191s 实测 "A HUGE WAVE OF ZOMBIES IS APPROACHING!"
               位于 y≈0.44，横跨 ~70% 屏宽，暗红 + 黑描边
"""
import argparse
import json
import subprocess
import sys

import numpy as np

FFMPEG = ("C:/Users/Welun_Laptop/.workbuddy/binaries/python/envs/default/"
          "Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe")

PAUSE_BANDS = ((0.248, 0.318), (0.662, 0.726))
PAUSE_Y = (0.30, 0.78)

BAND_Y = (0.34, 0.64)        # 横幅文字所在横带（红字实测 y≈0.44）
BAND_X = (0.05, 0.80)

FIELD_BOX = (0.62, 0.15, 0.97, 0.85)


def analyze(path, fps=10, width=480, height=376):
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-i', path,
           '-vf', 'fps=%d,scale=%d:%d' % (fps, width, height),
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10 ** 8)
    FS = width * height * 3

    by0, by1 = int(height * BAND_Y[0]), int(height * BAND_Y[1])
    bx0, bx1 = int(width * BAND_X[0]), int(width * BAND_X[1])
    bw = bx1 - bx0
    fy0, fy1 = int(height * FIELD_BOX[1]), int(height * FIELD_BOX[3])
    fx0, fx1 = int(width * FIELD_BOX[0]), int(width * FIELD_BOX[2])

    out = dict(fps=fps, n=0, pause=[], red_rowmax=[], red_rows=[],
               white_rowmax=[], white_rows=[], field=[])
    idx = 0
    while True:
        buf = p.stdout.read(FS)
        if len(buf) < FS:
            break
        a = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3).astype(np.int16)

        # 暂停
        ok = 0
        for x0, x1 in PAUSE_BANDS:
            sub = a[int(height * PAUSE_Y[0]):int(height * PAUSE_Y[1]),
                    int(width * x0):int(width * x1)]
            R = float(sub[:, :, 0].mean()); G = float(sub[:, :, 1].mean())
            B = float(sub[:, :, 2].mean())
            if R < 95 and abs(G - R) < 12 and (B - G) > 15:
                ok += 1
        out['pause'].append(1 if ok >= 1 else 0)

        # 文字
        sub = a[by0:by1, bx0:bx1]
        r, g, b = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
        rmask = (r > 110) & (g < 78) & (b < 78) & (r > g * 2) & (r > b * 2)
        wmask = (r > 232) & (g > 232) & (b > 226)
        rr = rmask.sum(axis=1)
        wr = wmask.sum(axis=1)
        out['red_rowmax'].append(float(rr.max()) / bw)
        out['red_rows'].append(int((rr > bw * 0.12).sum()))
        out['white_rowmax'].append(float(wr.max()) / bw)
        out['white_rows'].append(int((wr > bw * 0.12).sum()))

        # 进场区密度
        fs = a[fy0:fy1, fx0:fx1]
        fr, fg, fb = fs[:, :, 0], fs[:, :, 1], fs[:, :, 2]
        busy = ((fr > 110) | (fr > fg + 25)) & ~((fg > fb + 30) & (fg > 90))
        out['field'].append(float(busy.mean()))

        idx += 1
        if idx % 1000 == 0:
            sys.stderr.write('  %d 帧\n' % idx)
            sys.stderr.flush()
    try:
        p.stdout.close(); p.wait()
    except Exception:
        pass
    out['n'] = idx
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--fps', type=int, default=10)
    ap.add_argument('--json', required=True)
    a = ap.parse_args()
    d = analyze(a.video, a.fps)
    json.dump(d, open(a.json, 'w', encoding='utf-8'))
    print('总帧 %d（%.1fs）  暂停 %d 帧（%.1fs）'
          % (d['n'], d['n'] / float(a.fps),
             sum(d['pause']), sum(d['pause']) / float(a.fps)))
    print('-> %s' % a.json)


if __name__ == '__main__':
    main()
