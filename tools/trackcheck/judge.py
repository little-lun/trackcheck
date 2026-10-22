# -*- coding: utf-8 -*-
"""
judge.py —— 判定型僵尸（小丑 / 蹦极 / 投篮）

这三类**不做逐帧模拟**，只按已有理论出"可行 / 不可行"的判定。
因为它们的关键不是"打了多少伤害"，而是"节奏对不对、格子配不配" ——
这一类问题用规则查表比模拟更准，也更省时间。

依据：
  小丑 → wiki 控丑八定式（按"曾处于第几列"分档）
  蹦极 → wiki 冰杀两条定式 + 用户给的性价比规则
  投篮 → wiki「十炮以上完收，四炮配冰也可」+ 伞罩底线
"""

from . import data as D


# ---------------------------------------------------------------- 小丑
# [精] 开盒区间：早爆 440~754cs(5%)，晚爆 1325~2275cs(95%)；开盒后 110cs 炸
# wiki 控丑定式，按"该路最靠前的曾所在列"分档
JOKER_RULE = {
    9: dict(need_ice_by=440, extra='需 5 列加喷或 8 列加曾', verdict='紧'),
    8: dict(need_ice_by=440, extra='需 5 列至少加一喷', verdict='紧'),
    7: dict(need_ice_by=400, extra='需 6 列曾或 4 列喷', verdict='中'),
    6: dict(need_ice_by=None, extra='走到曾射程时冰，或加足火力', verdict='中'),
    5: dict(need_ice_by=None, extra='没什么好办法，只能炸死或堆大喷', verdict='差'),
    4: dict(need_ice_by=None, extra='预判冰 + 全程减速 + 垫材', verdict='差'),
    3: dict(need_ice_by=400, extra='维持减速', verdict='中'),
    2: dict(need_ice_by=1000, extra='无', verdict='好'),
    1: dict(need_ice_by=1000, extra='无', verdict='好'),
}


def judge_joker(array, lanes=6):
    """按每路"最靠前的曾"判定丑抗档位"""
    out = []
    for r in range(1, lanes + 1):
        best = 0
        for c in range(1, 10):
            spec = array.get((r, c))
            if spec and spec.get('plant') == '忧郁菇':
                best = max(best, c)
        if best == 0:
            out.append(dict(row=r, gloom_col=0, verdict='无曾',
                            need_ice_by=None, extra='该路没有曾，小丑无阻拦'))
            continue
        # 找最近的更低档位
        col = min(JOKER_RULE, key=lambda k: abs(k - best))
        rule = JOKER_RULE.get(best) or JOKER_RULE[col]
        out.append(dict(row=r, gloom_col=best, verdict=rule['verdict'],
                        need_ice_by=rule['need_ice_by'], extra=rule['extra']))
    return out


def joker_summary(rows):
    """最紧的那一路决定整阵的丑抗"""
    order = {'好': 0, '中': 1, '紧': 2, '差': 3, '无曾': 4}
    worst = max(rows, key=lambda x: order.get(x['verdict'], 0))
    needs = [x['need_ice_by'] for x in rows if x['need_ice_by']]
    return dict(
        worst=worst,
        ice_deadline=min(needs) if needs else None,
        ok=worst['verdict'] in ('好', '中'),
    )


# ---------------------------------------------------------------- 蹦极
def judge_bungee(array, lanes=6, ice_cost=75):
    """
    对每个"可能被偷的格子"跑两条冰杀定式：
      ① 两曾   ② 一曾 + 一瓜 + 任意其他输出
    判据用 3 行 × 5 列的蹦极判定框（行 ±1、列 ±2）
    """
    umb = [(r, c) for (r, c), s in array.items() if s.get('plant') == '保护伞']
    glooms = [(r, c) for (r, c), s in array.items() if s.get('plant') == '忧郁菇']
    melons = [(r, c) for (r, c), s in array.items() if s.get('plant') == '冰瓜']
    fume = [(r, c) for (r, c), s in array.items()
            if s.get('plant') in ('大喷菇', '香蒲')]

    def n_gloom(r, c):
        return sum(1 for (rr, cc) in glooms if abs(rr - r) <= 1 and abs(cc - c) <= 2)

    def has_melon(r):
        return any(rr == r for (rr, cc) in melons)

    def has_other(r):
        return any(rr == r for (rr, cc) in fume)

    rows = []
    for (r, c), spec in sorted(array.items()):
        if not spec.get('plant'):
            continue
        if spec.get('plant') in ('荷叶', '存冰', '保护伞'):
            continue
        # [你] 蹦极的防御有两条：伞 或 冰杀结构。先看伞
        under_umb = any(abs(rr - r) <= 1 and abs(cc - c) <= 1 for (rr, cc) in umb)
        g = n_gloom(r, c)
        style = None
        if g >= 2:
            style = '① 两曾'
        elif g == 1 and has_melon(r) and (has_other(r) or True):
            style = '② 一曾+一瓜+输出'
        # 成本判断
        price = {'忧郁菇': 225, '冰瓜': 500, '双子花': 200, '大喷菇': 75,
                 '香蒲': 250, '玉米炮': 700}.get(spec['plant'], 100)
        if style is None:
            decision = '只能补种（' + str(price) + '）'
        elif spec['plant'] in ('双子花', '忧郁菇', '冰瓜'):
            decision = '必须冰（' + str(price) + ' > ' + str(ice_cost) + '）'
        elif price >= ice_cost * 2:
            decision = '值得冰'
        else:
            decision = '可以不冰（' + str(price) + ' ≤ 冰钱）'
        if under_umb:
            style = '伞'
            decision = '伞免疫，不用管'
        rows.append(dict(row=r, col=c, plant=spec['plant'], glooms=g,
                         style=style, price=price, decision=decision,
                         umbrella=under_umb))
    blind = [x for x in rows if x['style'] is None]
    return dict(rows=rows, blind=blind, ok=len(blind) == 0)


# ---------------------------------------------------------------- 投篮
def judge_catapult(array, n_cannon=0, has_ice=True, lanes=6):
    """
    投篮两条路：
      ① 伞罩底线（1、2 列）→ 免疫
      ② 炮数 ≥4 且带冰 → 可在它投掷前炸死
    """
    umb = [(r, c) for (r, c), s in array.items() if s.get('plant') == '保护伞']
    out = []
    for r0 in range(1, lanes + 1):
        covered = any(abs(r - r0) <= 1 and c <= 3 for (r, c) in umb)
        out.append(dict(row=r0, umbrella=covered,
                        by=[(r, c) for (r, c) in umb if abs(r - r0) <= 1 and c <= 3]))
    by_umbrella = all(x['umbrella'] for x in out)
    by_cannon = (n_cannon >= 4 and has_ice)
    return dict(rows=out, by_umbrella=by_umbrella, by_cannon=by_cannon,
                ok=by_umbrella or by_cannon)


# ---------------------------------------------------------------- 投篮（扩展）
def judge_catapult2(array, n_cannon=0, has_ice=True, kill_before_throw=False,
                    lanes=6):
    """
    [你] 投篮两条路：
      ① 伞罩底线 → 免疫
      ② **在它投掷前击杀**（DE.双冰无炮 就是走这条：不靠伞，靠冰+灰烬/输出）
         条件：n_cannon ≥ 4 且带冰；或显式声明"有能力在投掷前杀掉"
    """
    r = judge_catapult(array, n_cannon, has_ice, lanes)
    r['by_kill'] = bool(kill_before_throw) or (n_cannon >= 4 and has_ice)
    r['ok'] = r['by_umbrella'] or r['by_kill']
    return r


# ---------------------------------------------------------------- 气球（判定型）
def judge_balloon(n_cannon=0, has_ice=True, n_cat=0, has_blover=False,
                  formation='tight'):
    """
    [维 入门·气球] 炮数达到四配合冰即可稳定炸杀；无冰则需六炮。
    无炮：顶满构型两猫，后退构型一猫；不用猫用三叶也可。
    """
    if n_cannon >= 6:
        why, ok = '六炮以上，无冰也能炸', True
    elif n_cannon >= 4 and has_ice:
        why, ok = '四炮 + 冰，稳定炸杀', True
    elif n_cat >= (2 if formation == 'tight' else 1):
        why, ok = '%d 猫，够' % n_cat, True
    elif has_blover:
        why, ok = '三叶草兜底', True
    else:
        why, ok = '没有任何手段', False
    return dict(ok=ok, why=why)
