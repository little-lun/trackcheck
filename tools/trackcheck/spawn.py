# -*- coding: utf-8 -*-
"""
spawn.py —— 按《技术:出怪机制》生成出怪列表

原文要点（wiki 技术:出怪机制）：
  · 出怪列表长度 2000，**每 50 个为一波**，共 40 波 → **每波至多 50 只**
  · 生存无尽每轮 20 波，只用前 1000 个
  · 每波刷新时**严格按列表顺序**生成
  · 列表由：权重 / 级别 / 阶数 / 红眼数量上限 共同决定

★ 所以"饱和出怪"= 列表被填满 = **每波 50 只**。
  这意味着"每一波每一路每种僵尸都会来" —— **对策不能省**（用户原话）。

级别上限公式：
    int(int((当前波数 + 已完成选卡数 × 20) × 0.8) / 2) + 1 ，旗帜波 ×2.5 向零取整
"""

import random

# (级别, 权重, 阶数)  —— 权重为「轮数=1」的基准值，随轮数调整见 weight()
Z = {
    '普通': (1, 4000, 1), '旗帜': (1, 0, 1), '路障': (2, 4000, 1),
    '撑杆': (2, 2000, 2), '铁桶': (4, 3000, 1), '读报': (2, 1000, 1),
    '铁门': (4, 3500, 2), '橄榄': (7, 2000, 2), '舞王': (5, 1000, 2),
    '潜水': (3, 2000, 3), '冰车': (7, 2000, 3), '雪橇': (3, 2000, 3),
    '海豚': (3, 1500, 3), '小丑': (3, 1000, 3), '气球': (2, 2000, 3),
    '矿工': (4, 1000, 3), '跳跳': (4, 1000, 3), '蹦极': (3, 1000, 3),
    # ★ 2026-10-20 修：这里原来写 '梯子'，但 TIERS / engine / data 全用 **'扶梯'**，
    #   于是 极速档的扶梯在 `if k not in Z: continue` 里被静默丢掉 —— 从来没出过。
    '扶梯': (4, 1000, 3), '投篮': (5, 1500, 3),
    '白眼': (10, 1500, 4), '红眼': (10, 6000, 4),
}


def weight(kind, round_, flag=False):
    """轮数对权重的调整（wiki 原文）"""
    lv, w, tier = Z[kind]
    if kind == '普通':
        return 4000 - 180 * min(max(round_ - 4, 0), 20) if round_ >= 5 else 4000
    if kind == '路障':
        return 4000 - 150 * min(max(round_ - 4, 0), 20) if round_ >= 5 else 4000
    if kind == '红眼':
        # [维 09] 红眼：旗帜波 6000（全场最高），**非旗帜波只有 1000**
        return 6000 if flag else 1000
    return w


def level_cap(w, round_, flag=False):
    v = int(int((w + round_ * 20) * 0.8) / 2) + 1
    if flag:
        v = int(v * 2.5)
    return v


def tier_gate(tier, round_):
    """阶数 → 该僵尸最早从第几波出现"""
    if tier <= 1:
        return 1
    if tier == 2:
        return 5
    if tier == 3:
        return 10
    if tier == 4:
        return max(1, 15 - max(0, round_ - 9))
    return 1


def make_wave(w, round_, allowed, rng, flag=None, red_used=0, red_cap=50,
              saturated=False, red_quota=None):
    """
    生成一波（≤50 只）。
    allowed: 该档允许出现的种类集合

    ★ 饱和出怪（126F 之后，用户 2026-10-18 指出）
      wiki《技术:出怪机制》的"饱和"一节：126F 后
        ① **阶数**不再起限制作用   → 所有类型从 w1 就能出
        ② **级别上限**不再起限制作用（严格意义）→ 50 个位置全填满
        ③ **红眼数量上限**不再起限制作用 → 红眼只按权重出
      三条约束被"破坏"后，每波就是**纯加权随机的 50 只**。

      本函数 saturated=True 时关掉这三个开关，只保留：
        · 每波 ≤ 50 只
        · 蹦极仅旗帜波（这条是权重表里的独立规则，不属于"三个限制"）
    """
    is_flag = (w % 10 == 0) if flag is None else flag
    # 级别上限仍保留：饱和时轮数足够大，它允许填满 50 个位置，
    # 但不会让"16 只红眼"这种极端堆叠出现（完全取消会给出荒谬结果）
    cap = level_cap(w, round_, is_flag)

    pool = []
    for k in allowed:
        if k not in Z:
            continue
        if not saturated and w < tier_gate(Z[k][2], round_):
            continue
        # 红眼上限：wiki 明确「轮数 54 起固定 50」= 50/轮。
        # 126F 的「不再起限制作用」按「不再是主要瓶颈」理解，但上限本身仍在。
        if k == '红眼' and red_used >= red_cap and not is_flag:
            continue
        if k == '蹦极' and not is_flag:
            continue                      # 蹦极仅旗帜波
        wt = weight(k, round_, is_flag)
        if wt > 0:
            pool.append((k, wt))
    if not pool:
        pool = [('普通', 1)]

    total_w = sum(x[1] for x in pool)
    out, used_lv = [], 0
    red_n = 0
    tries = 0
    while len(out) < 50 and tries < 400:
        tries += 1
        r = rng.random() * total_w
        acc = 0
        pick = pool[-1][0]
        for k, wt in pool:
            acc += wt
            if r <= acc:
                pick = k
                break
        lv = Z[pick][0]
        if used_lv + lv > cap:
            continue
        # ★ 本波红眼配额：wiki 的上限是「每轮 50 只」，必须摊到 20 波，
        #   不能像以前那样前 10 波就吃光（那会造出 w1 七只红眼的假强度）。
        if pick == '红眼':
            if red_quota is not None and red_n >= red_quota:
                continue
            red_n += 1
        out.append(pick)
        used_lv += lv
    if is_flag:
        out.insert(0, '旗帜')
    return out


def composition(lst):
    """列表 → {种类: 只数}"""
    m = {}
    for k in lst:
        m[k] = m.get(k, 0) + 1
    return m
