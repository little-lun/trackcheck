# -*- coding: utf-8 -*-
"""
l1.py —— 第一层：静态检查（纯离散数学，零误差）

这一层不模拟任何物理，只算三件事：
  ① 卡片 CD：轨道里同一张卡的最大使用频率 vs 卡片 CD
  ② 运算量：轨道覆盖多少运算量，够不够
  ③ 阳光：循环支出 vs 收入

★ 这一层的结论是**确定的**，不依赖速度/血量等任何假设。
  所以"轨道能不能跑"的第一道门槛应该由它来卡。
"""

from . import data as D

# ★ 这两个不是"排程动作"，是**随卡槽一好就补**的机会性动作
#   （用户口径：卡槽的冰一好就补种睡着的冰）。
#   它们没有固定节拍，所以不能拿 L1 的"最小间隔 vs CD"去卡 —— 那会把
#   "能补就补"误判成"必须每波补一次"。真正的约束由 L2 的动态记账回答。
OPPORTUNISTIC = {'种冰', '种冰2', '种临时冰'}   # 补种睡着的冰不算运算量


def card_pressure(track, waves_per_cycle, avg_wave_cs):
    """
    返回每张卡"名义上需要多快"vs"实际 CD 够不够"

    track(w) -> [(card, offset, aim), ...]
    waves_per_cycle: 一个循环几波
    avg_wave_cs:    一个循环多长（cs）
    """
    used = {}
    for i in range(1, waves_per_cycle + 1):
        for name, off, _ in track(i):
            if name in OPPORTUNISTIC:
                continue
            used.setdefault(name, []).append((i - 1) * avg_wave_cs + off)

    out = []
    for name, times in used.items():
        cd = D.CARDS.get(name, {}).get('cd', 0)
        n = len(times)
        # 一个循环内的间隔 + 跨循环的间隔
        if n >= 2:
            gap = min(b - a for a, b in zip(times, times[1:]))
        else:
            gap = waves_per_cycle * avg_wave_cs
        need_cd = gap
        out.append(dict(card=name, used=n, gap=gap, cd=cd,
                        ok=(cd <= need_cd),
                        margin=need_cd - cd))
    return out


def min_cycle_cs(track, waves_per_cycle):
    """轨道自洽所需的最小循环长度 = max(同卡最小间隔要求)"""
    used = {}
    for i in range(1, waves_per_cycle + 1):
        for name, off, _ in track(i):
            if name in OPPORTUNISTIC:
                continue
            used.setdefault(name, []).append((i - 1, off))
    need = 0
    for name, lst in used.items():
        cd = D.CARDS.get(name, {}).get('cd', 0)
        if len(lst) >= 2:
            gaps = [(lst[j + 1][0] - lst[j][0]) for j in range(len(lst) - 1)]
            # 单波内多次使用也计入
            need = max(need, cd / max(1, min(gaps)) if min(gaps) else cd)
        else:
            need = max(need, cd / waves_per_cycle)
    return need


def ops_audit(track, waves_per_cycle):
    """运算量：灰烬类 2，冰 0，窝瓜 1"""
    table = {'核': 2, '模仿核': 2, '樱桃': 1, '辣椒': 1, '窝瓜': 1,
             '冰': 0, '模仿冰': 0}
    per_wave = []
    for i in range(1, waves_per_cycle + 1):
        s = sum(table.get(n, 0) for n, _, _ in track(i))
        per_wave.append(s)
    return per_wave


def report(track, waves_per_cycle, avg_wave_cs, sun_in_per_s=0.0):
    waves_cs = waves_per_cycle * avg_wave_cs
    cp = card_pressure(track, waves_per_cycle, avg_wave_cs)
    ops = ops_audit(track, waves_per_cycle)
    spend = 0
    for i in range(1, waves_per_cycle + 1):
        for name, _, _ in track(i):
            spend += D.CARDS.get(name, {}).get('cost', 0)
    income = sun_in_per_s * waves_cs / 100.0
    return dict(
        cycle_cs=waves_cs,
        cards=cp,
        ops=ops,
        ops_sum=sum(ops),
        ops_need=2 * waves_per_cycle,
        sun_spend=spend,
        sun_income=round(income),
        sun_net=round(income - spend),
        ok=all(c['ok'] for c in cp) and sum(ops) >= 2 * waves_per_cycle * 0.4,
    )
