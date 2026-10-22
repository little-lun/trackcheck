"""
video_report.py —— 把四档录像的标定结果汇总成一张表

输出：
  1. 每档的原始时长 / 暂停时长 / 有效时长
  2. 红字（旗标波）出现的时刻
  3. 相邻旗标波之间的有效时间 → 每波平均波长
  4. 与模拟器四档结果对比

用法：
    python -m tools.trackcheck.video_report
"""
import json
import os

import numpy as np

FILES = [
    ('慢速', 'tools/trackcheck/probe_slow.json'),
    ('变速', 'tools/trackcheck/open_变速.json'),
    ('快速', 'tools/trackcheck/open_快速.json'),
    ('极速', 'tools/trackcheck/open_极速.json'),
]

# 模拟器四档结果（run.py --tier）
SIM = {
    '慢速': 20.0, '变速': 11.7, '快速': 12.4, '极速': 13.9,
}


def segs(flags, fps, min_len=3, gap=8):
    idx = np.where(np.asarray(flags) == 1)[0]
    if len(idx) == 0:
        return []
    out, s, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - prev > gap:
            out.append((s, prev)); s = i
        prev = i
    out.append((s, prev))
    return [(a / fps, b / fps) for a, b in out if b - a + 1 >= min_len]


def flags_of(v, fps, thr, minlen=3, gap=8):
    return segs((np.asarray(v) >= thr).astype(int), fps, minlen, gap)


def main():
    print('%-6s %8s %8s %8s %7s %6s' % ('档', '原始', '暂停', '有效', '暂停%', '段数'))
    print('-' * 52)
    data = {}
    for name, path in FILES:
        if not os.path.exists(path):
            print('%-6s 缺文件 %s' % (name, path))
            continue
        d = json.load(open(path, encoding='utf-8'))
        fps = d['fps']
        n = d['n']
        total = n / float(fps)
        ps = sum(d['pause'])
        pause_s = ps / float(fps)
        seg = segs(d['pause'], fps)
        print('%-6s %7.1fs %7.1fs %7.1fs %6.1f%% %6d'
              % (name, total, pause_s, total - pause_s, 100 * pause_s / total, len(seg)))
        data[name] = dict(d=d, fps=fps, total=total, pause_s=pause_s,
                          pauses=seg, valid=total - pause_s)
    print()

    print('== 红字（旗标波）时刻')
    for name, it in data.items():
        d, fps = it['d'], it['fps']
        rs = flags_of(d['red_rows'], fps, 8, minlen=3, gap=12)
        print('  %-4s %d 处：%s' % (name, len(rs),
              ', '.join('%.1fs' % a for a, b in rs)))
    print()

    print('== 有效时长 → 平均波长（按"一局 20 波 = 2 个旗标波间隔"）')
    print('%-6s %10s %10s %12s %12s' % ('档', '旗标间隔', '间隔内暂停', '有效间隔', '每波(÷10)'))
    print('-' * 58)
    for name, it in data.items():
        d, fps = it['d'], it['fps']
        rs = flags_of(d['red_rows'], fps, 8, minlen=3, gap=12)
        if len(rs) < 2:
            print('%-6s  只有一个旗标波，无法定标' % name)
            continue
        a, b = rs[0][0], rs[1][0]
        p = np.asarray(d['pause'])
        ps = p[int(a * fps):int(b * fps)].sum() / float(fps)
        print('%-6s %9.1fs %9.1fs %11.1fs %11.2fs'
              % (name, b - a, ps, (b - a) - ps, ((b - a) - ps) / 10.0))
    print()

    print('== 与模拟器对比（模拟 = ROUND 20、2 seed 平均）')
    print('%-6s %12s %12s %10s' % ('档', '录像(每波)', '模拟', '偏差'))
    print('-' * 46)
    for name, it in data.items():
        d, fps = it['d'], it['fps']
        rs = flags_of(d['red_rows'], fps, 8, minlen=3, gap=12)
        if len(rs) < 2 or name not in SIM:
            continue
        a, b = rs[0][0], rs[1][0]
        p = np.asarray(d['pause'])
        ps = p[int(a * fps):int(b * fps)].sum() / float(fps)
        wave = ((b - a) - ps) / 10.0
        sim = SIM[name]
        print('%-6s %11.2fs %11.1fs %9.0f%%'
              % (name, wave, sim, 100 * (sim - wave) / wave))
    print()
    print('== 录像 vs L1 硬下限 12.5s（冰 CD 50s ÷ 4 波）')
    for name, it in data.items():
        d, fps = it['d'], it['fps']
        rs = flags_of(d['red_rows'], fps, 8, minlen=3, gap=12)
        if len(rs) < 2:
            continue
        a, b = rs[0][0], rs[1][0]
        p = np.asarray(d['pause'])
        ps = p[int(a * fps):int(b * fps)].sum() / float(fps)
        wave = ((b - a) - ps) / 10.0
        print('  %-4s %5.2fs  %s' % (name, wave, '✔ C4io 成立' if wave >= 12.5 else '✘ C4io 不成立'))


if __name__ == '__main__':
    main()
