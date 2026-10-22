# -*- coding: utf-8 -*-
"""
expect.py —— 期望型磨损（矿工 / 小鬼 / 海豚 / 水路铁桶）

这一类不做逐只模拟，只算"每波造成的磨损期望"，然后和南瓜卡的供给做差：

    需求 k = Σ 各来源每波磨损（血/波）
    供给 s = (循环时长 / 南瓜CD) × 南瓜HP / 循环波数
    判定：k ≤ s → 撑得住；k > s → 南瓜会净亏，必须靠中场间隔/松弛关补

矿工特判：**挖掘途中会不会在前场被灰烬** —— 会的话磨损直接归零。
"""

from . import data as D


# 各来源的默认参数（⚠️ 都可调）
# per_wave: 每波出现频率（只/波，按出怪权重粗估）
# hp: 该僵尸血量
# reach: 它要走的距离（格）
# def_dps: 落点附近防御对它的等效 dps
SRC = {
    '矿工':   dict(per_wave=0.6, hp=370,  reach=0.0, def_dps=45,
                   note='从后场出土，走进曾的火力圈'),
    '小鬼':   dict(per_wave=0.5, hp=270,  reach=0.0, def_dps=60,
                   note='落 3 列，直接进曾/冰瓜范围'),
    '海豚':   dict(per_wave=0.4, hp=500,  reach=1.0, def_dps=40,
                   note='跳过前场，落 6 列啃南瓜'),
    '水路铁桶': dict(per_wave=0.3, hp=1370, reach=0.0, def_dps=35,
                   note='仅"无 I 波"，慢慢走到 6 列'),
}


def wear_per_wave(src=SRC, eat_dps=D.EAT_DPS):
    """
    单只磨损 = 它在该位置存活的时间 × 啃食 dps
    存活时间 = 血量 / 落点防御 dps
    """
    out = {}
    for name, p in src.items():
        alive_cs = p['hp'] / p['def_dps'] * 100        # cs
        wear = eat_dps * alive_cs / 100.0              # 血
        out[name] = dict(per_wave=p['per_wave'],
                         wear_each=wear,
                         wear=wear * p['per_wave'],
                         note=p['note'])
    return out


def balance_from_sim(k, cycle_cs, waves_per_cycle, n_cards=1,
                     pumpkin_hp=D.PUMPKIN_HP, pumpkin_cd=D.CARDS['南瓜']['cd']):
    """
    [你] 期望要**从模拟里取**，不是拍 def_dps：
      k = 模拟跑出的"南瓜总掉血 / 波数"（血/波）→ 自动随节奏变化（越快磨损越大）
      n_cards: 南瓜卡张数（极速关要带**双南瓜**：南瓜 + 模仿南瓜）
    """
    n_pump = (cycle_cs / pumpkin_cd) * n_cards
    supply = pumpkin_hp * n_pump / waves_per_cycle
    return dict(k=k, supply=supply, n_pump=round(n_pump, 2), n_cards=n_cards,
                ok=(k <= supply), ratio=(k / supply) if supply else 0,
                sun_fix=125 * min(1.0, k / pumpkin_hp) if pumpkin_hp else 0)


def balance(mine_flag, cycle_cs, waves_per_cycle, pumpkin_hp=D.PUMPKIN_HP,
            pumpkin_cd=D.CARDS['南瓜']['cd'], src=SRC):
    """
    mine_flag: 前场灰烬能否在矿工挖掘途中炸到它（True = 能，磨损归零）
    """
    w = wear_per_wave(src)
    if mine_flag:
        w['矿工']['wear'] = 0.0

    k = sum(v['wear'] for v in w.values())              # 每波需求
    n_pump = cycle_cs / pumpkin_cd                       # 一循环能补几个南瓜
    supply = pumpkin_hp * n_pump / waves_per_cycle       # 折算到每波
    return dict(
        detail=w,
        k=k,
        supply=supply,
        n_pump=round(n_pump, 2),
        ok=(k <= supply),
        ratio=(k / supply) if supply else 0,
        sun_fix=125 * min(1.0, k / pumpkin_hp) if pumpkin_hp else 0,
    )
