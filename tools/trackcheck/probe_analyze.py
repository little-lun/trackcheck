"""分析 video_probe 输出的时间序列：暂停分段 / 红字白字峰值"""
import json
import sys

import numpy as np


def segments(flags, fps):
    """把 0/1 序列切成 [(start_s, end_s, dur_s)]"""
    out = []
    i, n = 0, len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j < n and flags[j]:
                j += 1
            out.append((i / float(fps), j / float(fps), (j - i) / float(fps)))
            i = j
        else:
            i += 1
    return out


def peaks(vals, fps, k=4.0, min_len=3):
    """高于 median+k*IQR 且持续 >= min_len 帧的段"""
    v = np.asarray(vals, dtype=float)
    med = np.median(v)
    q1, q3 = np.percentile(v, 25), np.percentile(v, 75)
    thr = med + k * max(q3 - q1, 1e-4)
    out = []
    i, n = 0, len(v)
    while i < n:
        if v[i] >= thr:
            j = i
            while j < n and v[j] >= thr:
                j += 1
            if j - i >= min_len:
                out.append((i / float(fps), j / float(fps),
                            float(v[i:j].max()), float(v[i:j].mean())))
            i = j
        else:
            i += 1
    return out, thr, med


def main():
    d = json.load(open(sys.argv[1], encoding='utf-8'))
    fps = d['fps']
    print('总时长 %.1fs（%d 帧 @ %dfps）' % (d['n'] / float(fps), d['n'], fps))
    seg = segments(d['pause'], fps)
    tot = sum(s[2] for s in seg)
    print('\n== 暂停 %d 段，合计 %.1fs（%.1f%%）' % (len(seg), tot, 100 * tot / (d['n'] / float(fps))))
    lens = sorted(s[2] for s in seg)
    print('   时长分布：最短 %.2fs / 中位 %.2fs / 最长 %.2fs' %
          (lens[0], lens[len(lens) // 2], lens[-1]))
    print('   前 20 段：')
    for s, e, du in seg[:20]:
        print('     %6.2f ~ %6.2f  (%.2fs)' % (s, e, du))

    for name in ('red', 'white'):
        pk, thr, med = peaks(d[name], fps)
        print('\n== %s 峰值段 %d 个（阈值 %.4f，median %.4f）' % (name, len(pk), thr, med))
        for s, e, mx, mn in pk[:24]:
            print('     %6.2f ~ %6.2f  (%.2fs)  max=%.4f' % (s, e, e - s, mx))


if __name__ == '__main__':
    main()
