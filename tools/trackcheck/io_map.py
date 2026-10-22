# -*- coding: utf-8 -*-
"""
io_map.py —— 每路"击杀一只僵尸要多久 vs 它走到关键位置要多久"

★ 为什么不用"总 dps ≥ 总血量/波长"这个判据（用户 2026-10-18 纠正）：
   曾哥是 **AoE**：来 N 只时，每一只受到的 dps 几乎不变，总量翻 N 倍。
   所以"来一群红眼"和"来一只红眼"在时间上是同一个问题 ——
   只要单只能被杀掉，一群就能被杀掉（前提是它们都在范围里、且被减速）。

   正确判据：**击杀时间 T_kill ≤ 推进时间 T_move**
     T_kill = 僵尸血 / 该路对它的实际 dps
     T_move = 从进场(x=780)走到"关键位置"的距离 / 该路的实际推进速度
     实际推进速度 = 减速覆盖率 × 减速速度 + (1-覆盖率) × 正常速度

用法：python -m tools.trackcheck.io_map
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from tools.trackcheck import config_dianbozhong as C
from tools.trackcheck import data as D
from tools.trackcheck.engine import Sim, Zombie


def dps_against(row, kind, x0, secs=12):
    """在某路放一只僵尸，测这条自然输出在它身上砸出多少 dps。"""
    sim = Sim(C.ARRAY, C.track, C.wave_script, seed=0, total_waves=20, sun0=99999,
              skip_hp=0, slots={}, rescue=False, repair=False, allow_ash=False)
    sim.t = 5
    z = Zombie(kind, row, x0, 1, sim.rng)
    sim.zombies.append(z)
    t0 = sim.t
    n = int(secs * 100 / D.TICK)
    for _ in range(n):
        sim.t += D.TICK
        sim._index()
        sim._tick_move()
        sim._tick_dying()
        sim._tick_plants()
        if not z.alive:
            break
    return sim.dmg_dealt / ((sim.t - t0) / 100.0), z


def main():
    cov = float(sys.argv[1]) if len(sys.argv) > 1 else 0.95   # 减速覆盖率
    slow = D.SLOW_ANIM        # 非匀速僵尸减速系数
    print('减速覆盖率假设 %.0f%%（用户："绝大多数时间几乎所有怪都在减速"）' % (cov * 100))
    print()
    print('  路 | 僵尸 |  该路 dps | 击杀时间 | 推进时间 | 余量')
    print(' ----+------+-----------+----------+----------+------')
    # 关键位置 = 该路最靠前的 **CORE 植物**（僵尸能吃到它的位置）
    #   1 路 1-3 冰瓜(x=200) / 2 路 2-6 裸曾(x=440) / 3-4 路 9 列曾(x=680)
    #   5 路 5-6 裸曾(x=440) / 6 路 6-3 冰瓜(x=200)
    KEY = {1: 245, 2: 485, 3: 725, 4: 725, 5: 485, 6: 245}
    for row in range(1, 7):
        for kind in ('红眼', '白眼', '橄榄'):
            key_x = KEY[row]
            d, z = dps_against(row, kind, 780)
            hp = D.ZOMB[kind][0]
            v = D.avg_speed(kind)                       # px/cs（未减速）
            veff = v * (cov * slow + (1 - cov))
            t_kill = hp / d if d > 0 else 1e9
            t_move = (780 - key_x) / veff / 100.0
            margin = t_move - t_kill
            print('  %d  | %-4s | %8.0f  | %7.1fs | %7.1fs | %+5.1fs %s'
                  % (row, kind, d, t_kill, t_move, margin,
                     'OK' if margin > 0 else '★不足'))


if __name__ == '__main__':
    main()
