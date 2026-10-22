# -*- coding: utf-8 -*-
"""
grid_dps.py —— 逐格火力表 + "僵尸死在第几列"预测

用户 2026-10-18 的要求：
    "格子可以有一个属性『曾哥 dps』，把可以攻击到这个格子的曾哥 dps 求和，
      僵尸在本格内走的时间 × dps 就是僵尸走过曾哥格子掉的血。"

这条把"单路总 dps"的粗糙判据细化成了逐格积分：

    累计掉血(c) = Σ_{k=c..9} dps(r,k) × 每格停留时间
    死亡列 = 使累计掉血首次 ≥ 僵尸血量的那一列
    → 只要 死亡列 比"该路最靠前的 CORE 植物"更靠右，就是安全的

曾的范围 [精 六]：触发 x−80 ~ x+160，rows = 自身 ±1；单体 dps = 80/1.93 = 41.45

用法：python -m tools.trackcheck.grid_dps [减速覆盖率]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from tools.trackcheck import config_dianbozhong as C
from tools.trackcheck import data as D

# 该路最靠前的 CORE 植物所在列（僵尸能吃到它的位置 = 列+0.5 左右）
CORE_COL = {1: 3, 2: 6, 3: 9, 4: 9, 5: 6, 6: 3}


def cell_dps(array, r, c, kinds=('忧郁菇',), samples=9):
    """
    僵尸穿过 (r,c) 这一格时，平均受到的 dps。

    做法：在格内取 samples 个采样点 x ∈ [center-40, center+40]，
    对每个植物求"命中该 x 的比例"，再乘它的 dps 求和。
    这比"只看格中心"准确 —— 格距 80 正好是曾范围的整数倍，
    只判格中心会把边界上的曾整批排除掉。
    """
    cx = D.cell_x(c)
    xs = [cx - 40 + 80.0 * i / (samples - 1) for i in range(samples)]
    total = 0.0
    who = []
    for (rr, cc), spec in array.items():
        p = spec.get('plant')
        if p not in kinds:
            continue
        g = D.PLANTS.get(p)
        if not g or not g.get('dmg') or g['rng'] is None:
            continue
        lo, hi = g['rng']
        half = g['rows'] // 2
        if not (rr - half <= r <= rr + half):
            continue
        x = D.cell_x(cc)
        hit = sum(1 for px in xs if x + lo <= px <= x + hi) / float(samples)
        if hit > 0:
            total += g['dmg'] * g.get('hits', 1) / (g['interval'] / 100.0) * hit
            who.append('%d-%d%s' % (rr, cc, '' if hit >= 0.99 else '(%.0f%%)' % (hit * 100)))
    return total, who


def melon_dps(r):
    """该路冰瓜对"本行最前那只"的期望 dps（直击 80 / 2.93s；溅射另算）。"""
    n = sum(1 for (rr, cc), sp in C.ARRAY.items()
            if rr == r and sp.get('plant') == '冰瓜')
    return n * 80 / 2.93, n


def death_col(r, kind, cov=0.95, with_melon=True):
    """僵尸从 9 列走进来，预测死在第几列（返回 (列, 累计血, 用时)）"""
    v = D.avg_speed(kind) * (cov * D.SLOW_ANIM + (1 - cov))
    t_per = D.CELL_W / v / 100.0
    hp = D.ZOMB[kind][0]
    m, _ = melon_dps(r) if with_melon else (0.0, 0)
    acc = 0.0
    for c in range(9, 0, -1):
        d, _ = cell_dps(C.ARRAY, r, c)
        d += m                      # 冰瓜打最前那只：单只追踪时按满额计
        acc += d * t_per
        if acc >= hp:
            return c, acc, (9 - c + 1) * t_per
    return 1, acc, 9 * t_per


def main():
    cov = float(sys.argv[1]) if len(sys.argv) > 1 else 0.95
    print('=' * 80)
    print('逐格「曾哥 dps」表（单体 41.45 dps/曾；格中心严格落在触发范围内）')
    print('=' * 80)
    print('  列 |' + ''.join('  %d 路 ' % r for r in range(1, 7)))
    print(' ----+' + '-' * 42)
    for c in range(9, 0, -1):
        line = '  %d  |' % c
        for r in range(1, 7):
            v, _ = cell_dps(C.ARRAY, r, c)
            line += ('%5.0f ' % v) if v else '    · '
        print(line)

    print()
    print('=' * 80)
    print('红眼"死在第几列"预测（减速覆盖率 %.0f%%）' % (cov * 100))
    print('=' * 80)
    print('  路 | 冰瓜数 | 死亡列 | CORE列 | 判定            | 用时')
    print(' ----+--------+--------+--------+-----------------+-------')
    for r in range(1, 7):
        c, acc, t = death_col(r, '红眼', cov)
        core = CORE_COL[r]
        _, nmel = melon_dps(r)
        ok = c >= core
        print('  %d  |   %d    |   %d    |   %d    | %-15s | %5.1fs'
              % (r, nmel, c, core, '✔ 不会破' if ok else '★ 会啃到 CORE', t))

    print()
    print('=' * 80)
    print('对照：无减速（cov=0）')
    print('=' * 80)
    for r in range(1, 7):
        c, acc, t = death_col(r, '红眼', 0.0)
        core = CORE_COL[r]
        print('  %d 路：死在第 %d 列（%.1fs）%s'
              % (r, c, t, '✔' if c >= core else '★ 会啃到第 %d 列的 CORE' % core))


if __name__ == '__main__':
    main()
