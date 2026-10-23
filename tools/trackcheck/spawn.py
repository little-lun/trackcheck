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
    （已完成选卡数 = 轮数 + 1；一次选卡覆盖 2 个 flag）

红眼数量上限（[维 09 §七]）：
    初始 0 → 轮数 5 起每轮 +1 → 轮数 54 起固定 50；
    达到上限后**非旗帜波**立刻不再出红眼（旗帜波不受限）。

`make_wave()` 返回**有序**列表；`Wave` 同时保留 `{种类: 只数}` 便于统计。
"""

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
    # [维 09 §四] 表里剩下几项：雪人极低权重；伴舞/鸭子/小鬼/僵博 weight=0
    # （前三个是衍生/自动转换，僵博不出现在无尽）。保留在表里是为了"33 项"语义完整。
    '雪人': (4, 1, 1), '伴舞': (1, 0, 1), '鸭子': (1, 0, 1),
    '小鬼': (10, 0, 4), '僵博': (10, 0, 4),
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


def red_cap(round_):
    """本轮的**红眼数量上限**：[维 09 §七] 初始 0，轮数 5 起每轮 +1，54 起固定 50。"""
    if round_ < 5:
        return 0
    return min(50, round_ - 4)


def level_cap(w, round_, flag=False, levels_done=None):
    """每波级别上限。

    [维 09 §五] `int(int((当前波数 + 已完成选卡数 × 20) × 0.8) / 2) + 1`，
    旗帜波 ×2.5 向零取整。

    轮数 = 已完成 flag 数 / 2 − 1，而一次选卡覆盖 2 个 flag
    → **已完成选卡数 = 轮数 + 1**。
    """
    if levels_done is None:
        levels_done = max(0, round_ + 1)
    v = int(int((w + levels_done * 20) * 0.8) / 2) + 1
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


class Wave(dict):
    """一波出怪：既是 `{种类: 只数}`，又保留**原版出怪列表的顺序**（`order`）。

    原版是"严格按出怪列表预先设定的顺序依次生成" —— 顺序会影响选行
    （Weight / LastPicked / SecondLastPicked），所以不能像以前那样把种类展开后
    再 shuffle 一遍。
    """

    def __init__(self, lst):
        super().__init__(composition(lst))
        self.order = list(lst)


def make_wave(w, round_, allowed, rng, flag=None, red_used=0, cap=None,
              saturated=False, levels_done=None):
    """
    生成一波（≤50 只）的**有序出怪列表**。

    [维 09 §三/§四/§五/§六/§七] 原版口径：
      · 每 50 个为一波，每波至多 50 只
      · 加权随机逐个填列表，直到**级别总和**逼近级别上限
      · 阶数 / 红眼数量上限 / 级别上限 三个限制随轮数饱和

    `red_used` = 本轮**已经生成**的红眼累计数（非旗帜波达到上限后不再出红眼，
    立刻生效）。调用方负责跨波累计、在 w1 清零。
    """
    is_flag = (w % 10 == 0) if flag is None else flag
    if cap is None:
        cap = level_cap(w, round_, is_flag, levels_done)

    pool = []
    for k in allowed:
        if k not in Z:
            continue
        if not saturated and w < tier_gate(Z[k][2], round_):
            continue
        if k == '红眼' and red_used >= red_cap(round_) and not is_flag:
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
    # 原版是"填到级别上限为止"；饱和后上限足够大 → 填满 50 个位置。
    # 上限已经放不下任何一只时（低轮数早期）就停，不硬凑。
    # ★ 2026-10-23：**每波至多 50 只**（[维 09 §三]）—— 旗帜占其中一格，
    #   所以旗帜波只填 49 个随机位，再把旗帜插到最前面，总数仍是 50。
    target = 49 if is_flag else 50
    min_lv = min(Z[k][0] for k, _w in pool)
    tries = 0
    while len(out) < target and used_lv + min_lv <= cap and tries < 2000:
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
        if pick == '红眼':
            if not is_flag and red_used + red_n >= red_cap(round_):
                continue
            red_n += 1
        out.append(pick)
        used_lv += lv
    # 普僵三大类至少保留其一（[02 §四] 密度上限附则）
    # ★ 不能 insert（会顶成 51 只）—— 直接把最后一个非三大类的位置换成普通
    if not any(k in ('普通', '路障', '铁桶') for k in out):
        if out:
            out[-1] = '普通'
        else:
            out.append('普通')
    if is_flag:
        out.insert(0, '旗帜')
    return out


def composition(lst):
    """列表 → {种类: 只数}"""
    m = {}
    for k in lst:
        m[k] = m.get(k, 0) + 1
    return m
