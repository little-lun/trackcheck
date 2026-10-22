# -*- coding: utf-8 -*-
"""
plan.py —— **阵解栏**的数据模型：可编辑的阵解 / 编译成引擎能跑的东西 / 校验

一份阵解 = 五层（v0.3）：

    阵解
     ├ 选卡      10 张卡（含模仿者）—— 后面所有"种什么"的选项都只从这里出
     ├ 节奏      C 系 C4io：N | AA' | I | I（可换系/换型/自定义拍）
     ├ 表层（轨道）每波一行；行内 = 若干"候选"（兜底链），候选里是"积木"序列
     │    · 行首积木 = 刷怪即刻（或很短延时）生效
     │    · 后面的积木要挂**触发器**：时间 / 卡片 CD / 距离 / 场况，可循环
     ├ 全场判定  持续判一个条件，成立就做（例：冰卡一好就补在永久存冰位）
     └ 救场      简化栏（交资源 + 排优先级，内部决定打什么）
                  详细栏（事件 → 多层兜底，逐条写死）

统一说法（v0.3 最重要的一条）：**阵解里只写植物名**。
    「点存冰」  → 在某个格子**种咖啡豆**（唤醒那格睡着的寒冰菇）
    「补存冰」  → 在某个格子**种寒冰菇**
    「查存冰数」→ 查**场上某植物数量** / 某格子**上面是什么植物**
"""

import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.trackcheck import config_dianbozhong as CFG   # noqa: E402
from tools.trackcheck import metainfo as MI              # noqa: E402

FORMAT = 'trackcheck-plan/3'
WAVES = 20


# ══════════════════════════════════════════════════════════════════
# 卡片名 ↔ 引擎内部卡名（引擎的卡表还叫「核 / 冰 / 垫材」）
# ══════════════════════════════════════════════════════════════════
CARD_KEY = {
    '毁灭菇': '核', '模仿毁灭菇': '模仿核',
    '寒冰菇': '冰', '模仿寒冰菇': '模仿冰',
    '樱桃': '樱桃', '辣椒': '辣椒', '窝瓜': '窝瓜',
    '小喷菇': '垫材', '花盆': '垫材2',
    '阳光菇': '垫材3', '胆小菇': '垫材4',
    '南瓜': '南瓜',
    '大蒜': '大蒜', '咖啡豆': '咖啡豆', '大喷菇': '大喷菇',
    '玉米炮': '玉米炮', '荷叶': '荷叶', '保护伞': '保护伞', '双子花': '双子花',
}
KEY_NAME = {v: k for k, v in CARD_KEY.items()}
# 四张垫材的植物名（校验时豁免"同一候选两张同名卡"）
PAD_NAMES = ('小喷菇', '花盆', '阳光菇', '胆小菇')

# 选卡：初代全部 48 张卡（SeedType 0~47）+ 模仿者（模仿者带二级选项，写成 `模仿者:寒冰菇`）
PLANT_ALL = MI.PLANTS
MIMIC = MI.MIMIC
ALL_CARDS = list(PLANT_ALL) + [MIMIC]

DEFAULT_DECK = ['寒冰菇', '模仿者:寒冰菇', '毁灭菇', '樱桃', '辣椒',
                '窝瓜', '小喷菇', '花盆', '南瓜', '咖啡豆']


def is_mimic(entry):
    return isinstance(entry, str) and entry.startswith(MIMIC + ':')


def mimic_target(entry):
    return entry.split(':', 1)[1] if is_mimic(entry) else None


def deck_op(entry):
    """选卡项 → 阵解里可用的积木名（模仿者 → 模仿X）"""
    t = mimic_target(entry)
    return (MIMIC[2:] if False else '模仿' + t) if t else entry


def norm_card(entry):
    """把 `模仿寒冰菇` 这类旧写法折成 `模仿者:寒冰菇`"""
    if not isinstance(entry, str):
        return entry
    if entry in (MIMIC,) or is_mimic(entry):
        return entry
    if entry.startswith('模仿') and entry[2:] in PLANT_ALL:
        return '%s:%s' % (MIMIC, entry[2:])
    return entry


def template(field='PE'):
    """一套**空的**阵解骨架（主界面新建阵解用；不含任何具体阵型的内容）。"""
    return norm(dict(
        format=FORMAT, name='新建阵解', note='',
        field=field,
        deck=[], rhythm=dict(system='C', id='C4io', name='C4io',
                             beats=['N', "AA'", 'I', 'I'],
                             gaps=[], pair='auto'),
        waves=[dict(w=w, role=role_of(w), sets=[]) for w in range(1, 21)],
        globals=[], rescue=[], rescue_simple=dict(enabled=False,
                                                 resources=[], targets=[]),
    ))


def deck_label(entry):
    """选卡里的一项 → 给人看的标签（'模仿者:寒冰菇' → '模仿寒冰菇'）"""
    entry = norm_card(entry)
    if is_mimic(entry):
        return '模仿' + entry.split(':', 1)[1]
    return entry


def deck_ops(deck):
    """这份选卡能让哪些积木出现"""
    return [deck_op(c) for c in (deck or [])]


def engine_card(op):
    """积木名 → 引擎卡名；None = 引擎还没这张卡"""
    if op in CARD_KEY:
        return CARD_KEY[op]
    return None

# v0.2 及更早的动作名 → 植物名（导入旧阵解时自动迁移）
LEGACY_OP = {
    '核': '毁灭菇', '模仿核': '模仿毁灭菇',
    '冰': '寒冰菇', '模仿冰': '模仿寒冰菇',
    '存冰': '咖啡豆', '救急冰': '咖啡豆',
    '种冰': '寒冰菇', '种冰2': '模仿寒冰菇', '种临时冰': '寒冰菇',
    '垫材': '小喷菇', '垫材2': '花盆',
    '垫材3': '阳光菇', '垫材4': '胆小菇', '种大喷': '大喷菇',
    # ★ 2026-10-22：特技「窝瓜压车」取消，退化成"在 5-9 种窝瓜"
    '窝瓜压车': '窝瓜',
}


# ══════════════════════════════════════════════════════════════════
# 积木目录
# ══════════════════════════════════════════════════════════════════
OPS = [
    dict(name='毁灭菇', group='灰烬', need_aim=True, aim_kind='cell',
         note='圆形 R=250（含纵向 30px 偏移）'),
    dict(name='模仿毁灭菇', group='灰烬', need_aim=True, aim_kind='cell',
         note='模仿者毁灭菇，效果相同、CD 独立'),
    dict(name='樱桃', group='灰烬', need_aim=True, aim_kind='cell', auto=True,
         note='R=115；不给落点则按"2-8 顺延"自动挑'),
    dict(name='辣椒', group='灰烬', need_aim=False, aim_kind='row',
         note='整行 1800；不给落点则自动挑最密的一行'),
    dict(name='寒冰菇', group='冰', need_aim=False, aim_kind='cell',
         note='落点是存冰位 → 就是"补存冰"；落点是普通格子 → 种下即冻'),
    dict(name='模仿寒冰菇', group='冰', need_aim=False, aim_kind='cell',
         note='同上，用模仿者那张冰卡'),
    dict(name='咖啡豆', group='冰', need_aim=True, aim_kind='cell', auto=True,
         note='在这一格种咖啡豆 → 唤醒那格**睡着的蘑菇**（若是寒冰菇则立刻全场冰冻）'),
    dict(name='窝瓜', group='卡', need_aim=False, aim_kind='cell',
         note='不给落点则按最危险的一路自动挑'),
    dict(name='小喷菇', group='卡', need_aim=False, aim_kind='row',
         note='垫材①：给行列就只在那格下；只给行就按该路固定垫材位'),
    dict(name='花盆', group='卡', need_aim=False, aim_kind='row',
         note='垫材②'),
    dict(name='阳光菇', group='卡', need_aim=False, aim_kind='row',
         note='垫材③（0/25 阳光、7.5s 充能）'),
    dict(name='胆小菇', group='卡', need_aim=False, aim_kind='row',
         note='垫材④。四张垫材轮着用，2 张短 cd 卡就能把一路巨人钉在炮的判定域里'),
    dict(name='南瓜', group='卡', need_aim=True, aim_kind='cell', note='补南瓜'),
    dict(name='大蒜', group='卡', need_aim=True, aim_kind='cell', note='换行'),
    dict(name='大喷菇', group='卡', need_aim=False, aim_kind='cell',
         note='结构位补大喷（不给落点则按 5-7 → 2-7）。'
              '⚠️ 新种的蘑菇是睡着的，要同一格再放一颗咖啡豆才输出'),
    dict(name='忧郁菇', group='卡', need_aim=True, aim_kind='cell', note='补曾'),
    dict(name='荷叶', group='卡', need_aim=True, aim_kind='cell', note=''),
    dict(name='保护伞', group='卡', need_aim=True, aim_kind='cell', note=''),
    dict(name='双子花', group='卡', need_aim=True, aim_kind='cell', note=''),
    # ★ 2026-10-22 用户口径：**轨道里能做的操作只有 P 和种植物（卡片）**。
    #   P 不指定具体哪一门炮，只看每门炮各自的 3475cs 装填；落点可带一位小数。
    dict(name='玉米炮', group='炮', need_aim=True, aim_kind='aim',
         note='**开炮（P）**：任意一门装填好的炮，爆炸 R=115 / 1800 即刻生效；'
              '落点可带一位小数（如 3-4.5），与僵尸受击框有重合就吃满 1800。'
              '**滑列落点**：列填 "front"（JSON 里 `"aim": [2, "front"]`）'
              '= 自动把圆挪到"这一路最靠前那只刚好被圆切到"的位置，'
              '最靠前的怪漏网时用它兜底'),
    # ---- v0.2.1 新增的积木
    dict(name='地刺', group='卡', need_aim=True, aim_kind='cell',
         note='不挡路、不被啃；101cs 一次 20，判定 x+21~+49'),
    dict(name='钢地刺', group='卡', need_aim=True, aim_kind='cell',
         note='同上，但一轮两次命中（共 40）'),
    dict(name='高坚果', group='卡', need_aim=True, aim_kind='cell',
         note='8000 血，挡得住撑杆/跳跳的跳越'),
    dict(name='双向射手', group='卡', need_aim=True, aim_kind='cell',
         note='前 1 发 + 后 2 发，各 20'),
    dict(name='机枪射手', group='卡', need_aim=True, aim_kind='cell',
         note='一次 4 发，各 20'),
    dict(name='火炬树桩', group='卡', need_aim=True, aim_kind='cell',
         note='让穿过它的豌豆变火豌豆（×2）'),
    dict(name='磁力菇', group='卡', need_aim=True, aim_kind='cell',
         note='吸走金属护具（R=270）'),
    dict(name='三叶草', group='卡', need_aim=False, aim_kind='none',
         note='**秒杀全场气球**'),
    dict(name='墓碑吞噬者', group='卡', need_aim=False, aim_kind='cell',
         note='直接清掉一格墓碑（NE 用）'),
]
# ★ 2026-10-22：**"窝瓜压车"这个操作取消了** —— 轨道里只写"在 5-9 种窝瓜"，
#   "什么时候种"交给触发器（例如"5 路冰车距 5-9 还有 N px"）。
#   旧阵解导入时按这个映射自动迁移。
OP_NAMES = [o['name'] for o in OPS]
OP_BY_NAME = {o['name']: o for o in OPS}


TRIGGERS = [
    dict(kind='spawn', label='刷怪即刻', params=[]),
    dict(kind='time', label='波内时间', params=['at']),
    dict(kind='after', label='上一块之后', params=['at']),
    dict(kind='card', label='卡片 CD 转好', params=['name', 'offset']),
    dict(kind='dist', label='距离', params=['zombie', 'row', 'col', 'axis', 'cmp', 'value']),
    dict(kind='state', label='场况', params=['what', 'cmp', 'value', 'row']),
    # ★ 2026-10-22：跨波锚点 —— "距上次某个积木生效 N cs 之后"
    dict(kind='since', label='距上次某积木生效后', params=['op', 'at']),
    dict(kind='all', label='全部满足', params=['of']),
    dict(kind='any', label='任一满足', params=['of']),
    dict(kind='not', label='取反', params=['of']),
]

GATES = TRIGGERS + [
    dict(kind='card_ready', label='卡片已转好', params=['card', 'offset']),
    dict(kind='card_ready_within', label='卡片 N 波内转好', params=['card', 'waves']),
    dict(kind='plant_count', label='场上某植物数量', params=['plant', 'cmp', 'value']),
    dict(kind='cell_is', label='某格是什么植物', params=['row', 'col', 'plant']),
    dict(kind='kernel_slack', label='核坑余量', params=['cmp', 'value']),
    dict(kind='prev', label='之前某波用了…', params=['back', 'target', 'set', 'op', 'negate']),
    dict(kind='always', label='总是', params=[]),
]

EVENTS = [
    dict(kind='zombie_in_window', label='僵尸进入窗口',
         params=['rows', 'col', 'window', 'min_hp', 'zombie']),
    dict(kind='heavy_near_core', label='重甲逼近 CORE', params=['rows', 'cells']),
    dict(kind='bare_core_threat', label='裸 CORE 要被砸', params=[]),
    dict(kind='cell_threat', label='某格植物被逼近', params=['row', 'col', 'cells']),
    dict(kind='plant_count', label='场上某植物数量', params=['plant', 'cmp', 'value']),
    dict(kind='wave', label='波次区间', params=['from', 'to']),
    dict(kind='always', label='总是', params=[]),
]

ZOMBIE_FILTERS = ['任意', '巨人', '冰车', '橄榄', '铁桶', '小丑', '撑杆', '海豚', '潜水']

# 节奏系 / 节奏型：**两套命名方案并行**（2021 传统 / 2026 新版，见 metainfo）
RHYTHM_SYSTEMS = MI.RHYTHMS

LAYOUT_LETTERS = {
    "AA'": ['樱桃', '辣椒'],
    'N': ['毁灭菇'], "N'": ['模仿毁灭菇'],
    "A'": ['辣椒'], 'A': ['樱桃'],
    "I'": ['模仿寒冰菇'], 'I': ['寒冰菇'],
    'W': ['窝瓜'], 'K': ['咖啡豆'],
    "C'": ['花盆'], 'C': ['小喷菇'],
    'P': ['玉米炮'],
    '核': ['毁灭菇'], '冰': ['寒冰菇'], '樱': ['樱桃'], '辣': ['辣椒'],
}

# 调整（用户 2026-10-21）：只有 w1 是起手，w2 / w11 / w12 都算常规波
ROLE_OF = {**{w: '旗波' for w in (10, 20)}, **{w: '收尾' for w in (9, 19)}}


def role_of(w):
    return '起手' if int(w or 0) == 1 else ROLE_OF.get(int(w or 0), '常规')


def is_regular(w):
    """能被"快捷布置阵解"填的波：除 w1（起手）与旗波以外"""
    return int(w or 0) > 1 and int(w or 0) not in (10, 20)


# ------------------------------------------------------------------ 编译
def _avg(ctx):
    return (ctx or {}).get('avg_gap') or 1250


def _cmp_ok(a, cmp_, b):
    return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b,
            '==': a == b, '!=': a != b}.get(cmp_ or '>=', False)


def kernel_slack(w, avg_cs):
    """核坑余量（cs）：离最近的固定核波（w11 / 下轮 w1）还剩多少"""
    nxt = 11 if w < 11 else WAVES + 1
    return (nxt - w) * (avg_cs or 1250) - 1500


def _card_key(name):
    return CARD_KEY.get(name, name)


def _prev_wave(w, back):
    prev = int(w or 1) - int(back or 1)
    while prev < 1:
        prev += WAVES
    return prev


def _cell(rc):
    if isinstance(rc, (list, tuple)) and len(rc) == 2:
        try:
            return (int(rc[0]), int(rc[1]))
        except (TypeError, ValueError):
            return None
    return None


def gate_ok(gate, ctx, w=None, hist=None):
    """候选条件 / 全场判定条件求值"""
    if not gate:
        return True
    k = gate.get('kind')
    ctx = ctx or {}
    now = ctx.get('t', 0)
    ready = ctx.get('card_ready') or {}
    if k in (None, 'always'):
        return True
    if k in ('card_ready', 'card'):
        key = _card_key(gate.get('card') or gate.get('name'))
        return ready.get(key, 0) + int(gate.get('offset') or 0) <= now
    if k == 'card_ready_within':
        key = _card_key(gate.get('card') or gate.get('name'))
        return ready.get(key, 0) <= now + _avg(ctx) * float(gate.get('waves') or 0.9)
    if k == 'plant_count':
        plant = gate.get('plant') or '寒冰菇'
        cnt = (ctx.get('plants') or {}).get(plant, 0)
        return _cmp_ok(cnt, gate.get('cmp'), gate.get('value'))
    if k == 'ice_stock':                     # 旧阵解兼容：等价于"场上寒冰菇数量"
        cnt = (ctx.get('plants') or {}).get('寒冰菇', ctx.get('ice_stock', 0))
        return _cmp_ok(cnt, gate.get('cmp'), gate.get('value'))
    if k == 'cell_is':
        rc = _cell((gate.get('row'), gate.get('col')))
        cur = (ctx.get('cells') or {}).get(rc)
        want = gate.get('plant')
        if want in (None, '', '空', '无'):
            return cur is None
        return cur == want
    if k == 'kernel_slack':
        return _cmp_ok(kernel_slack(w or ctx.get('wave') or 1, _avg(ctx)),
                       gate.get('cmp') or '>=', int(gate.get('value') or 0))
    if k == 'prev':
        return prev_fired(gate, ctx, w, hist)
    if k == 'not':
        return not gate_ok(gate.get('of'), ctx, w, hist)
    if k == 'all':
        return all(gate_ok(g, ctx, w, hist) for g in (gate.get('of') or []))
    if k == 'any':
        return any(gate_ok(g, ctx, w, hist) for g in (gate.get('of') or []))
    return True          # time/after/dist/state/spawn 是触发器，放错位置就当无条件


def prev_fired(gate, ctx, w=None, hist=None):
    """
    「之前某波的某个候选发生了」—— 拆 AA′ 就靠这条。

        {"kind":"prev","back":1,"target":"set","set":0}      上一波是不是候选 #1
        {"kind":"prev","back":1,"target":"set","op":"辣椒"}  上一波选中的候选里有没有辣椒
        {"kind":"prev","back":1,"target":"act","op":"樱桃"}  上一波樱桃**真打出去了**吗
        + "negate": true 取反
    """
    back = int(gate.get('back') or 1)
    target = gate.get('target') or 'set'
    pw = _prev_wave(w or ctx.get('wave') or 1, back)
    want_set = gate.get('set')
    op = LEGACY_OP.get(gate.get('op'), gate.get('op'))
    sel, got = None, []
    if target == 'act':
        got = [KEY_NAME.get(n, n) for n in
               (((ctx or {}).get('ops_by_wave') or {}).get(pw) or [])]
    else:
        h = (hist or {}).get(pw) or {}
        got = list(h.get('ops') or [])
        sel = h.get('set')
    ok = True
    if want_set not in (None, ''):
        ok = (sel == int(want_set))
    if op:
        ok = ok and (op in got)
    if want_set in (None, '') and not op and target == 'set':
        ok = sel is not None
    return (not ok) if gate.get('negate') else ok


def _blocks_acts(blocks, ctx):
    """一组的积木序列 → 引擎认识的 [{op, at, aim, trig}]"""
    now = (ctx or {}).get('t', 0)
    ready = (ctx or {}).get('card_ready') or {}
    prev_at = 0
    out = []
    for b in blocks or []:
        op = LEGACY_OP.get(b.get('op'), b.get('op'))
        trig = dict(b.get('trig') or {'kind': 'spawn'})
        at = int(b.get('at') or 0)
        kind = trig.get('kind')
        if kind == 'time':
            at += int(trig.get('at') or 0)
            trig = None
        elif kind == 'after':
            at = prev_at + int(trig.get('at') or 0)
            trig = None
        elif kind == 'card':
            name = trig.get('name') or op
            at += max(0, int(ready.get(_card_key(name), 0)) - now) \
                + int(trig.get('offset') or 0)
            trig = dict(trig, kind='card', name=name)
        elif kind == 'since':
            # ★ 2026-10-22：跨波锚点。编译期不折算，交给引擎在运行时求值
            #   —— 因为"上次生效"可能发生在上一波。
            trig = dict(trig, kind='since')
        elif kind in ('spawn', None):
            trig = None
        if b.get('repeat'):
            trig = dict(trig or {'kind': 'spawn'})
            trig['repeat'] = b['repeat']
        out.append(dict(op=op, at=at, aim=b.get('aim'), trig=(trig or None)))
        prev_at = at
    return out


def _wave_acts(row, ctx, hist=None):
    """一行：第一个 `when` 成立的候选胜出（= if / elif / else）"""
    if not row:
        return []
    w = int(row.get('w') or 0)
    c = {**(ctx or {}), 'wave': w}
    for i, st in enumerate(row.get('sets') or []):
        if gate_ok(st.get('when'), c, w, hist):
            acts = _blocks_acts(st.get('ops'), ctx)
            if hist is not None:
                hist[w] = dict(set=i, ops=[a['op'] for a in acts], when=st.get('when'))
            return acts
    if hist is not None:
        hist[w] = dict(set=None, ops=[])
    return []


def run_plan_op(sim, op, aim=None):
    """立刻执行一个积木；返回 True = 真的落地了"""
    op = LEGACY_OP.get(op, op)
    before = len(sim.actions)
    sim.do_action(dict(name=op, aim=aim, wave=max(1, sim.cur_wave), kind='act'))
    return any(a.get('ok') for a in sim.actions[before:])


def tick_globals(sim, rules):
    """全场判定层：每 tick 看一遍规则，条件成立就把积木做掉"""
    if not rules:
        return
    cd = sim.__dict__.setdefault('_plan_global_cd', {})
    last = sim.__dict__.setdefault('_plan_global_last', {})
    for i, r in enumerate(rules):
        if not r.get('enabled', True):
            continue
        rid = r.get('id') or ('g%d' % i)
        if cd.get(rid, -1) > sim.t:
            continue
        every = int(r.get('every') or 0)
        if every and sim.t - last.get(rid, -10 ** 9) < every:
            continue
        if not gate_ok(r.get('when'), sim.plan_ctx(), sim.cur_wave):
            continue
        ok = True
        for b in (r.get('ops') or []):
            if not run_plan_op(sim, b.get('op'), b.get('aim')):
                ok = False
                break
        if ok:
            cd[rid] = sim.t + int(r.get('cooldown') or 0)
            last[rid] = sim.t


# ------------------------------------------------------------------ 简化救场
def probe_target(sim, target):
    """这个"要保护的植物"现在有多危险？→ (余量px, 僵尸, 格子) 或 None"""
    prot = target.get('protect') or {}
    row, col = prot.get('row'), prot.get('col')
    if row in (None, '') or col in (None, ''):
        return None
    rc = (int(row), int(col))
    c = sim.cells.get(rc)
    if c is None or not c.plant:
        return None
    zs = [z for z in sim.by_row.get(rc[0], ())
          if z.alive and z.hp > 0 and z.x >= c.x - 40]
    # ★ 2026-10-22：冰车默认不当"救场对象"（垫材挡不住它），
    #   但救急卡（樱桃/辣椒/窝瓜）是能直接炸掉它的 → 由 include_icecar 打开。
    if not target.get('include_icecar'):
        zs = [z for z in zs if z.kind != '冰车']
    if not zs:
        return None
    z = min(zs, key=lambda x: x.x)
    return (z.x - c.x, z, rc)


def urgency_px(target):
    """急迫级：僵尸距目标还有多少像素就开始救（1 格 = 80px，45 = 刚好能啃到）"""
    v = target.get('urgency_cells')
    cells = 1.0 if v is None else float(v)
    return 45 + cells * 80.0


def run_rescue_resource(sim, res, row=None, target_rc=None):
    """用一份救场资源；返回 True = 用掉了

    ★ 2026-10-22：成功用掉的动作会打上 `rescue=True` —— 报告里要能分清
      「这张卡是**轨道计划内**用的，还是**救场层**临时用的」（用户：
      "樱桃当时并不是用于灰烬控丑而是救场，搞清楚为什么用卡"）。
    """
    n0 = len(sim.actions)
    ok = _run_rescue_resource(sim, res, row, target_rc)
    if ok:
        for a in sim.actions[n0:]:
            a['rescue'] = True
    return ok


def _run_rescue_resource(sim, res, row=None, target_rc=None):
    op = LEGACY_OP.get(res.get('op'), res.get('op'))
    # ★ 2026-10-22：卡还在 CD 就直接返回 False（去试下一份资源），
    #   不要走 do_action —— 那会往 broken 里塞一条"断轨：樱桃 CD 没好"，
    #   而救场资源的 CD 轮转是**正常现象**，不是断轨。
    card = _card_key(op)
    if op not in ('小喷菇', '花盆', '阳光菇', '胆小菇'):
        if sim.card_ready.get(card, 0) > sim.t:
            return False
    if op in ('小喷菇', '花盆', '阳光菇', '胆小菇'):
        card = _card_key(op)
        # ★ 2026-10-22 用户：「垫材视作救场而不是轨道」。
        #   救场资源可以给 `pad_col`：
        #     数字     → 种在**危险那一路的指定列**（炮阵要垫在 8 列这种判定域里）
        #     'front'  → 种在**僵尸脚下那一格**（动态选列，最贴合"什么时候真的需要"）
        col = res.get('pad_col')
        if col == 'front' and row is not None:
            zs = [z for z in sim.by_row.get(int(row), ())
                  if z.alive and z.hp > 0 and z.kind != '冰车']
            # ★ 2026-10-22：`only_giant` —— 垫材只用来钉**巨人**。
            #   路障 / 橄榄这种一炮就死的，用垫材纯属浪费经济。
            if res.get('only_giant'):
                zs = [z for z in zs if z.giant]
            if not zs:
                return False
            z = min(zs, key=lambda x: x.x)
            from tools.trackcheck import data as _D
            c0 = max(1, min(9, int((z.x - 40) // _D.CELL_W) + 1))
            for cc in (c0, c0 - 1, c0 + 1):
                if 1 <= cc <= 9 and sim.stall_at((int(row), cc), cards=(card,)):
                    return True
            return False
        if col is not None and row is not None:
            if sim.stall_at((int(row), int(col)), cards=(card,)):
                return True
        if res.get('aim'):
            return run_plan_op(sim, op, res.get('aim'))
        if sim.try_stall([row] if row else None, cards=(card,)):
            return True
        # 固定垫材位下不了（僵尸还没进 6 列窗口）→ 直接种在它前面那一格
        if target_rc:
            return bool(sim.stall_at((target_rc[0], min(9, int(target_rc[1]) + 1)),
                                     cards=(card,)))
        return False
    if op == '窝瓜' and not _cell(res.get('aim')):
        return bool(sim.try_wogua([row] if row else None))
    if op == '咖啡豆':
        aim = _cell(res.get('aim'))
        if aim is None:
            if sim._reserved('咖啡豆', within=800):
                return False          # 轨道马上要用这张卡，救场别抢
            return run_plan_op(sim, op, None)     # 自动挑一格装满的存冰
        if not (sim.ice_slots.get(aim) or sim.temp_ice.get(aim)):
            return False
        if not sim._try_card('咖啡豆'):
            return False
        sim.activate_ice(aim)
        sim.actions.append(dict(t=sim.t, wave=max(1, sim.cur_wave),
                                name='咖啡豆', ok=True))
        return True
    return run_plan_op(sim, op, res.get('aim'))


def tick_rescue_simple(sim, cfg):
    """
    简化救场栏：用户只给"资源"和"要保的植物 + 急迫级 + 优先级"，
    打什么牌、打哪一路由这里决定。
    """
    if not cfg or not cfg.get('enabled', True):
        return
    targets = list(cfg.get('targets') or [])
    if not targets:
        return
    cd = sim.__dict__.setdefault('_plan_simple_cd', {})
    for i in sorted(range(len(targets)),
                    key=lambda k: -float(targets[k].get('priority') or 0)):
        t = targets[i]
        tid = t.get('id') or ('t%d' % i)
        if cd.get(tid, -1) > sim.t:
            continue
        probe = probe_target(sim, t)
        if probe is None:
            continue
        gap, z, rc = probe
        if gap > urgency_px(t):
            continue
        used = False
        for res in (cfg.get('resources') or []):
            if run_rescue_resource(sim, res, row=rc[0], target_rc=rc):
                sim._log('RESCUE', '简化救场：%s 用 %s（%d 路，余量 %d px）'
                         % (tid, res.get('op'), rc[0], int(gap)),
                         row=rc[0], col=rc[1],
                         detail='僵尸 x=%d hp=%d' % (z.x, z.hp))
                cd[tid] = sim.t + int(t.get('cooldown') or 60)
                used = True
                break
        if not used:
            # 一份都用不了 → 过一会儿再看，别每 tick 都空转（会刷出成吨的"断裂"）
            cd[tid] = sim.t + int(t.get('every') or 30)


# ------------------------------------------------------------------ 编译入口
def compile_plan(plan):
    """→ (track_fn, rescue_tick, globals_tick)"""
    p = norm(plan or {})
    rows = {int(r['w']): r for r in (p.get('waves') or [])}
    rules = p.get('rescue') or []
    g_rules = p.get('globals') or []
    simple = p.get('rescue_simple') or {}
    hist = {}

    def track(w, ctx):
        if int(w or 0) <= 1:
            hist.clear()
        return _wave_acts(rows.get(int(w or 0)), ctx, hist)

    def rescue_tick(sim):
        tick_rescue_simple(sim, simple)
        return tick_rescue(sim, rules)

    def globals_tick(sim):
        tick_globals(sim, g_rules)

    return track, rescue_tick, globals_tick


# ------------------------------------------------------------------ 详细救场层
def _event_fired(sim, ev):
    k = (ev or {}).get('kind')
    if k in (None, 'always'):
        return True
    if k == 'wave':
        return int(ev.get('from') or 1) <= sim.cur_wave <= int(ev.get('to') or WAVES)
    if k == 'plant_count':
        return gate_ok(dict(kind='plant_count', plant=ev.get('plant'),
                            cmp=ev.get('cmp'), value=ev.get('value')), sim.plan_ctx())
    if k == 'cell_threat':
        p = probe_target(sim, dict(protect=dict(row=ev.get('row'), col=ev.get('col'))))
        if p is None:
            return False
        return p[0] <= 45 + float(ev.get('cells') or 1) * 80
    if k == 'zombie_in_window':
        rows = ev.get('rows') or [6, 5, 1]
        col = int(ev.get('col') or 6)
        lo, hi = ev.get('window') or (10, 75)
        cx = 40 + 80 * (col - 1)
        zfilter = ev.get('zombie') or '任意'
        min_hp = ev.get('min_hp') or 0
        for row in rows:
            for z in sim.by_row.get(row, ()):
                if not z.alive or z.hp <= 0 or z.kind == '冰车':
                    continue
                if z.stall_until > sim.t:
                    continue
                if not (cx + lo <= z.x <= cx + hi):
                    continue
                if z.hp <= min_hp and not z.giant:
                    continue
                if zfilter == '巨人' and not z.giant:
                    continue
                if zfilter not in ('任意', '巨人') and z.kind != zfilter:
                    continue
                return True
        return False
    if k == 'heavy_near_core':
        return _heavy_near_core(sim, ev)
    if k == 'bare_core_threat':
        return _bare_core_threat(sim)
    return False


def _heavy_near_core(sim, ev):
    from tools.trackcheck import data as D
    rows = ev.get('rows') or [6, 5, 2, 1]
    n = float(ev.get('cells') or 3)
    for row in rows:
        core = D.CORE_X.get(row)
        if core is None:
            continue
        for z in sim.by_row.get(row, ()):
            if not z.alive or z.hp <= 0:
                continue
            if not (z.giant or z.hp >= D.WOGUA_HP):
                continue
            if z.x <= core + n * 80:
                return True
    return False


def _bare_core_threat(sim):
    from tools.trackcheck import data as D
    for row in range(1, 7):
        for z in sim.by_row.get(row, ()):
            if not z.alive or z.kind == '冰车':
                continue
            if not (z.giant or z.hp > 800):
                continue
            c = sim._next_target(z)
            if c is None or c.plant not in D.CORE_PLANTS or c.pumpkin:
                continue
            if z.x <= c.x + D.ICE_EMERG_REACH:
                return True
    return False


def _run_rescue_op(sim, op, aim=None):
    op = LEGACY_OP.get(op, op)
    if op in ('小喷菇', '花盆', '阳光菇', '胆小菇'):
        rows = (aim or {}).get('rows') if isinstance(aim, dict) else None
        return bool(sim.try_stall(rows, cards=(_card_key(op),)))
    if op == '窝瓜' and not _cell(aim):
        rows = (aim or {}).get('rows') if isinstance(aim, dict) else None
        return bool(sim.try_wogua(rows))
    return run_plan_op(sim, op, aim)


def tick_rescue(sim, rules):
    """详细救场层：事件 → 多层兜底（哪一层全部落地就停）"""
    if not rules or not sim.rescue:
        return
    cd = sim.__dict__.setdefault('_plan_rescue_cd', {})
    for i, rule in enumerate(rules):
        rid = rule.get('id') or ('rule%d' % i)
        if cd.get(rid, -1) > sim.t:
            continue
        if not _event_fired(sim, rule.get('event')):
            continue
        done = False
        for lv in (rule.get('levels') or []):
            ops = lv.get('ops') if isinstance(lv, dict) else lv
            ok = True
            for b in (ops or []):
                if not _run_rescue_op(sim, b.get('op'), b.get('aim')):
                    ok = False
                    break
            if ok:
                done = True
                break
        # 成功了按 cooldown 冷却；失败了也退避一会儿，别每 tick 空转
        cd[rid] = sim.t + int(rule.get('cooldown') or 30) if done \
            else sim.t + int(rule.get('every') or 30)


# ------------------------------------------------------------------ 轨道串
#
# ★ 2026-10-22 用户口径（依据《轨道语言与运算量》§3.2 结构符号）：
#
#    `|`  隔离符  区分不同波次刷新的僵尸          → 一段 = 一波
#    `-`  刷新符  区分同一波中的过渡/刷新操作      → 同一波里的**第二个时机**
#                 （`-` 之前的操作不会导致刷新）
#    `/`  分场符  区分上下半场在同一时机的不同操作  → 同一时机的两组操作
#    `~`  波动符  串联两个基础节奏                 → 两套轨道逐循环摆动
#
#   解析只求"初步识别"：认得出分隔符、知道它意味着什么，
#   具体落点/时机/兜底**一律留空**让用户填。
TRACK_SEP = {'|': 'wave', '｜': 'wave', '-': 'late', '－': 'late',
             '/': 'split', '／': 'split', '~': 'variant', '～': 'variant'}
# 简写里"一次写一响"能代表一对炮的操作（核/冰/灰烬本来就只有一张卡）
PAIRABLE = {'P'}


def _track_chars(text):
    """把 `P|P` 拆成 [(字符, 分隔符)] —— 支持 `AA'`、`N'` 这种两字符记号"""
    s = ''.join((text or '').split())
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in TRACK_SEP:
            out.append(('', TRACK_SEP[ch]))
            i += 1
            continue
        two = s[i:i + 2]
        if two in LAYOUT_LETTERS:
            out.append((two, None))
            i += 2
            continue
        if ch in LAYOUT_LETTERS:
            out.append((ch, None))
        else:
            out.append((ch, 'unknown'))
        i += 1
    return out


def _letters(txt, pair, split, unknown):
    """一个片段里的记号 → 植物名列表。

    `split=True`（该片段用过 `/`）时**不按简写翻倍** —— 分场本身就表达了"一对"。
    """
    names = []
    for ch, sep in _track_chars(txt):
        if sep == 'unknown':
            if ch not in unknown:
                unknown.append(ch)
            continue
        if sep:                       # 片段里残留的分隔符（`/`）跳过
            continue
        for n in (LAYOUT_LETTERS.get(ch) or []):
            names.append(n)
            if pair and ch in PAIRABLE and not split:
                names.append(n)
    return names


def _parse_beat(seg, pair, unknown):
    """一段（两个 `|` 之间）→ beat

    `-` 把这一波切成多个时机：第 1 段是主时机（刷怪即刻），后面的都是"过渡"。
    `/` 表示同一时机的上下半场 —— 只记标记，落点留给用户。
    """
    parts = re.split(r'[-－]', seg)
    split = bool(re.search(r'[/／]', seg))

    def names_of(txt):
        return _letters(txt, pair, split, unknown)

    beat = dict(ops=names_of(parts[0]), late=[], split=split)
    for p in parts[1:]:
        grp = names_of(p)
        if grp:
            beat['late'].append(grp)
    return beat if (beat['ops'] or beat['late'] or split) else None


def resolve_pair(text, mode='auto'):
    """简写 / 复写 → 是否按"一次写 = 一对炮"翻倍

    · `short` 简写：`P|P|P|P` = 4 对炮（8 门）
    · `full`  复写：`PP|PP|PP|PP` = 4 对炮，`P` = 单门
    · `auto` 自动辨认：串里出现连续两个 P（`PP`）就按复写，否则按简写

    ★ 用户 2026-10-22：「简写与复写选项放入设置，涉及到对称操作写一个还是一对」
    """
    if mode == 'short':
        return True
    if mode == 'full':
        return False
    return not re.search(r'[Pp]{2,}', ''.join((text or '').split()))


def parse_track_full(text, pair=None):
    """轨道串 → {'variants': [[beat, …], …], 'unknown': [...], 'seps': [...]}

    `beat = dict(ops=[植物名…], late=[[植物名…]…], split=bool)`
      · `ops`   这一波的**主时机**（刷怪即刻）
      · `late`  用 `-` 分隔出来的后续时机（每个是一组操作）
      · `split` 这段里用过 `/` → 上下半场各自填落点
    `pair=None` = 自动辨认简写/复写（见 `resolve_pair`）。
    """
    raw = ''.join((text or '').split())
    # 去掉开头的节奏名标签（`N6s:` / `P4:` / `ch6：`），它不是操作
    m = re.match(r'^([A-Za-z]*\d+[A-Za-z]*)[:：]', raw)
    if m:
        raw = raw[m.end():]
    if pair is None:
        pair = resolve_pair(raw, 'auto')
    unknown, variants, seps = [], [], []
    for vt in re.split(r'[~～]', raw):
        beats = []
        for seg in re.split(r'[|｜]', vt):
            if not seg:
                continue
            b = _parse_beat(seg, pair, unknown)
            if b:
                beats.append(b)
        if beats:
            variants.append(beats)
    for ch in raw:
        if ch in TRACK_SEP:
            seps.append(ch)
    return dict(variants=variants, unknown=unknown, seps=seps, pair=pair)


def parse_track(text, pair=None):
    """"N|AA'|I|I" → [['毁灭菇'], ['樱桃','辣椒'], ['寒冰菇'], ['寒冰菇']]

    只取**主时机**（`-` 之后的忽略），给"看看认不认识"用。
    """
    d = parse_track_full(text, pair)
    out = []
    for beat in (d['variants'][0] if d['variants'] else []):
        if beat['ops']:
            out.append(list(beat['ops']))
    return out


# ------------------------------------------------------------------ 波长串
GAPS_KEY = 'gaps'


def parse_gaps(text):
    """波长串 → [秒, …]

    接受 `(9,9,9,9)`、`(9|9|9|9)`、`9 9 9 9`、`(18,18,9,9)`；
    也接受 cs 写法（任何一项 ≥ 100 时整串按 cs 解，如 `(1800,1800,900,900)`）。
    """
    s = (text or '').strip()
    if not s:
        return []
    s = s.strip('()（）[]').replace('|', ',').replace('｜', ',')
    s = s.replace('/', ',').replace('，', ',').replace(' ', ',')
    out = []
    for tok in s.split(','):
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = float(tok)
        except ValueError:
            raise ValueError('波长串里「%s」不是数字' % tok)
        if v <= 0:
            raise ValueError('波长必须 > 0（读到 %s）' % tok)
        out.append(v)
    if out and max(out) >= 100:          # 按 cs 写的
        out = [v / 100.0 for v in out]
    return out


def format_gaps(gaps, sep=','):
    if not gaps:
        return ''
    return '(' + sep.join(('%g' % float(g)) for g in gaps) + ')'


# ------------------------------------------------------------------ 波长校验
COB_CD = 3475                 # cs，每门炮的独立装填
LONG_CARD_CD = 5000           # cs，灰烬 / 冰的卡 CD（[精] 通通 50s）
P_MIN = 3600                  # 含 P 的循环，波长和的理论下限（35/36 是极限）
P_HARD = 3400                 # 34s 以下直接判不可能
C_MIN = 5400                  # 含长 CD 卡（灰烬 / 冰）的循环下限


def _is_long_card(name):
    from . import data as D
    core = name.split(':', 1)[1] if name.startswith('模仿者:') else name
    return core in ('毁灭菇', '樱桃', '辣椒', '窝瓜', '寒冰菇')


def _op_of_block(b):
    """积木/资源 → 植物名（含旧名迁移）"""
    if isinstance(b, dict):
        return LEGACY_OP.get(b.get('op'), b.get('op'))
    return LEGACY_OP.get(b, b)


def cycle_ops(beats):
    """一个循环里所有时机的操作名（按顺序拍平）"""
    out = []
    for beat in beats or []:
        out.extend(beat.get('ops') or [])
        for grp in (beat.get('late') or []):
            out.extend(grp or [])
    return out


def check_spectrum(beats, gaps, n_cob=None, deck=None):
    """**波长和校验**（用户 2026-10-22 口径）

    返回 `[dict(level='ok'|'warn'|'bad', msg=…), …]`

    规则：
      ① 含 P：波长和 ≥ 36s；34~35s 算极限（warn）；< 34s 直接不可能（bad）
         —— 并据此算「这个循环至少要几门炮」
      ② 含 C（长 CD 卡：灰烬 / 冰）：波长和 ≥ 54s，否则 warn
      ③ 波长和过去之后，循环的第一个操作必须重新可用（换算成"炮/卡都转好了"）
      ④ 不认识的记号不参与计算，只提示
    """
    out = []
    ops = cycle_ops(beats)
    gaps = [float(g) for g in (gaps or [])]
    if not gaps:
        # ★ 2026-10-22 用户口径：波长串**可选** ——
        #   IO 高的阵波长本来就难以精确控制，不填就不校验。
        return []
    L = sum(gaps) * 100.0                    # cs
    n_beat = len([b for b in (beats or []) if cycle_ops([b])])
    if n_beat and len(gaps) != n_beat:
        out.append(dict(level='warn',
                        msg='波长串有 %d 项，轨道有 %d 拍 —— 一般应相等'
                            % (len(gaps), n_beat)))
    if not ops:
        return out + [dict(level='warn', msg='轨道是空的')]

    # ---- ① P
    n_p = sum(1 for o in ops if o == '玉米炮')
    if n_p:
        if L < P_HARD:
            out.append(dict(level='bad',
                            msg='含 P 但波长和只有 %.2fs < 34s —— 一次装填（34.75s）'
                                '都走不完，这个循环不可能成立' % (L / 100.0)))
        elif L < P_MIN:
            out.append(dict(level='warn',
                            msg='含 P 且波长和 %.2fs 在 34~36s 的极限区：'
                                '刚好够一门炮装填一次，容错极低（建议 ≥ 36s）'
                                % (L / 100.0)))
        cap = L / COB_CD                 # 每门炮一个循环能打几发（可含小数）
        if cap < 1:
            out.append(dict(level='bad',
                            msg='循环 %.2fs 不到一次装填（%.2fs），P 打不出去'
                                % (L / 100.0, COB_CD / 100.0)))
        else:
            need = int(math.ceil(n_p / cap))
            msg = ('循环 %.2fs ≈ %.2f 个炮 CD → %d 发 P 至少要 **%d 门炮**'
                   % (L / 100.0, cap, n_p, need))
            if n_cob is None:
                out.append(dict(level='ok', msg=msg + '（阵型页数一下炮）'))
            elif n_cob < need:
                out.append(dict(level='bad',
                                msg=msg + '，但阵型里只有 %d 门 —— 差 %d 门'
                                    % (n_cob, need - n_cob)))
            else:
                out.append(dict(level='ok',
                                msg=msg + '（阵型里有 %d 门，够）' % n_cob))

    # ---- ② 长 CD 卡
    longs = [o for o in ops if _is_long_card(o)]
    if longs:
        copies = {}
        for name in longs:
            copies[name] = copies.get(name, 0) + 1
        if L < C_MIN:
            out.append(dict(level='warn',
                            msg='含长 CD 卡（%s）但波长和 %.2fs < 54s：'
                                '同一张卡的复用要靠模仿者或存冰顶'
                                % ('/'.join(sorted(set(longs))), L / 100.0)))
        per = max(1, int(L // LONG_CARD_CD))
        for name, u in sorted(copies.items()):
            base = name.split(':', 1)[1] if name.startswith('模仿者:') else name
            have = 1 + (1 if (deck and ('模仿者:' + base) in deck) else 0)
            # ★ 寒冰菇另有「存冰」这条免费路径（预置好、只需咖啡豆唤醒），
            #   所以只提示不判死
            if u > have * per:
                lvl = 'warn' if base in ('寒冰菇',) else 'bad'
                out.append(dict(level=lvl,
                                msg='%s 一个循环要用 %d 次，但只有 %d 张卡 × '
                                    '%d 次冷却 = %d 次%s'
                                    % (name, u, have, per, have * per,
                                       '（冰还能靠存冰顶）' if lvl == 'warn' else '')))

    # ---- ③ 首操作可行性
    first = ops[0]
    if first == '玉米炮':
        if L < COB_CD:
            pass                     # ①里已经报过"打不出去"
        elif n_cob is None or n_cob * (L / COB_CD) >= n_p:
            out.append(dict(level='ok',
                            msg='循环首操作「P」在下一循环开始时已有炮转好'))
    elif _is_long_card(first):
        if L < LONG_CARD_CD:
            out.append(dict(level='bad',
                            msg='循环首操作「%s」的卡 CD 是 50s，波长和只有 %.2fs '
                                '—— 下一循环开头还没转好' % (first, L / 100.0)))
        else:
            out.append(dict(level='ok',
                            msg='循环首操作「%s」在下一循环开始时已转好' % first))
    return out


def spectrum_report(plan=None, track=None, gaps=None, n_cob=None):
    """给界面用的波长校验（轨道 + 波长串 + 阵型炮数 → 结论）"""
    p = plan or {}
    rh = p.get('rhythm') or {}
    text = track if track is not None else '|'.join(rh.get('beats') or [])
    raw = gaps if gaps is not None else rh.get(GAPS_KEY)
    if isinstance(raw, str):
        try:
            g = parse_gaps(raw)
        except ValueError as e:
            return dict(ok=False, error=str(e))
    else:
        g = [float(x) for x in (raw or [])]
    mode = rh.get('pair') or 'auto'
    d = parse_track_full(text, None if mode == 'auto' else (mode == 'short'))
    beats = d['variants'][0] if d['variants'] else []
    ops = cycle_ops(beats)
    items = check_spectrum(beats, g, n_cob, p.get('deck'))
    return dict(ok=True, gaps=g, total=sum(g), beats=len(beats),
                n_p=sum(1 for o in ops if o == '玉米炮'),
                items=items, unknown=d['unknown'], pair=d.get('pair'))


def quick_layout(plan, track_text=None, pair=None, gaps_text=None):
    """
    把简式轨道铺进**常规波**（w2~w20，跳过旗波 w10/w20）。

    ★ 只填"做什么"：落点、时机、兜底一律留空，由用户补 ——
      这就是"快捷布置阵解"的全部职责。

    分隔符的处置（用户 2026-10-22）：
      · `|` → 下一波
      · `-` → 同一波里再排一组积木，触发器用「上一块之后」并把时间**留空**
      · `/` → 两组操作放进同一时机，落点全部留空（分场上/下半场自己填）
      · `~` → 两套轨道**逐循环交替**铺进去
    """
    p = norm(plan or {})
    rh = p.get('rhythm') or {}
    text = track_text if track_text is not None else \
        '|'.join(rh.get('beats') or [])
    if track_text is not None:
        # 轨迹串同步进 rhythm.beats，保证 JSON / 校验看到的是同一份
        rh['beats'] = [s.strip() for s in track_text.split('|')
                       if s.strip()] or rh.get('beats') or []
    mode = pair if pair is not None else (rh.get('pair') or 'auto')
    parsed = parse_track_full(text, None if mode == 'auto' else (mode == 'short'))
    variants = [v for v in parsed['variants'] if any(cycle_ops([b]) for b in v)]
    if not variants:
        return p, 0

    # 波长串
    raw_gaps = gaps_text if gaps_text is not None else rh.get(GAPS_KEY)
    if isinstance(raw_gaps, str):
        try:
            rh[GAPS_KEY] = parse_gaps(raw_gaps)
        except ValueError:
            rh[GAPS_KEY] = []
    rh['pair'] = mode
    p['rhythm'] = rh

    targets = [w for w in range(1, WAVES + 1) if is_regular(w)]
    rows = {int(r['w']): r for r in (p.get('waves') or [])}
    filled = 0
    cycle_i = 0          # 第几轮循环（用于 `~` 交替）
    beats = variants[0]
    for i, w in enumerate(targets):
        if i and i % len(beats) == 0:
            cycle_i += 1
            beats = variants[cycle_i % len(variants)]
        beat = beats[i % len(beats)]
        row = rows.get(w)
        if row is None:
            row = dict(w=w, role=role_of(w), sets=[])
            p['waves'].append(row)
            rows[w] = row
        row['role'] = role_of(w)
        blocks = [dict(op=op, aim=None, trig={'kind': 'spawn'})
                  for op in (beat.get('ops') or [])]
        for grp in (beat.get('late') or []):
            for op in grp or []:
                # `-` 之后的时机：留空给用户填（默认"上一块之后 + 0"）
                blocks.append(dict(op=op, aim=None,
                                   trig={'kind': 'after', 'at': 0}))
        row['sets'] = [dict(when={'kind': 'always'}, ops=blocks)]
        label = ' + '.join(b.get('op') for b in blocks) or '（空）'
        row['note'] = '快捷布置：' + label
        if beat.get('split'):
            row['note'] += '　· 分场（`/`）：上下半场的落点自己填'
        if len(variants) > 1:
            row['note'] += '　· 波动（`~`）第 %d 套' % (cycle_i % len(variants) + 1)
        filled += 1
    p['waves'].sort(key=lambda r: int(r['w']))
    return p, filled


# ------------------------------------------------------------------ 批量编辑 / 波次平移
def shift_waves(plan, sel, delta):
    """
    把选中的波次**整体**前移/后移 delta 个波次。

    ★ 语义：选中的波把内容搬到 w±delta；如果目标波也在选区里，那就是整块平移
      （不会互相覆盖）；目标波不在选区里就被覆盖（撤销可退回）。
      越界（<1 或 >WAVES）的波直接丢掉。
    """
    p = norm(plan)
    delta = int(delta or 0)
    sel = {int(x) for x in (sel or [])}
    if not delta or not sel:
        return p, 0
    rows = {int(r['w']): r for r in p['waves']}
    moved, taken = {}, {}
    order = sorted(sel, reverse=(delta > 0))
    for w in order:
        row = rows.get(w)
        if row is None:
            continue
        nw = w + delta
        if nw < 1 or nw > WAVES:
            continue
        new = json.loads(json.dumps(row))
        new['w'] = nw
        new['role'] = role_of(nw)
        moved[nw] = new
        taken[nw] = w
    if not moved:
        return p, 0
    for w in sorted(sel):
        if w in rows and w not in moved:
            rows.pop(w, None)
    rows.update(moved)
    p['waves'] = [rows[w] for w in sorted(rows)]
    missing = [w for w in range(1, WAVES + 1) if w not in rows]
    for w in missing:
        p['waves'].append(dict(w=w, role=role_of(w), sets=[], note=''))
    p['waves'].sort(key=lambda r: int(r['w']))
    return p, len(moved)


def batch_edit(plan, sel, op, data=None):
    """
    批量编辑：op = 'clear' | 'paste' | 'copy'（copy 只读，由调用方取内容）
    """
    p = norm(plan)
    sel = {int(x) for x in (sel or [])}
    if not sel:
        return p, 0
    if op == 'clear':
        for row in p['waves']:
            if int(row['w']) in sel:
                row['sets'] = []
                row['note'] = ''
        return p, len(sel)
    if op == 'paste':
        src = (data or {}).get('rows') or []
        if not src:
            return p, 0
        rows = {int(r['w']): r for r in p['waves']}
        n = 0
        for i, w in enumerate(sorted(sel)):
            tpl = src[i % len(src)]
            row = rows.get(w) or dict(w=w, role=role_of(w))
            row['sets'] = json.loads(json.dumps(tpl.get('sets') or []))
            row['note'] = tpl.get('note') or row.get('note') or ''
            row['role'] = role_of(w)
            if w not in rows:
                p['waves'].append(row)
                rows[w] = row
            n += 1
        p['waves'].sort(key=lambda r: int(r['w']))
        return p, n
    return p, 0


def pick_rows(plan, sel):
    """取选中波次的内容（复制用）"""
    p = norm(plan)
    sel = {int(x) for x in (sel or [])}
    return [dict(sets=r.get('sets') or [], note=r.get('note') or '')
            for r in p['waves'] if int(r['w']) in sel]


# ------------------------------------------------------------------ 校验
def validate(plan):
    out = []

    def bad(where, msg):
        out.append(dict(lv='error', where=where, msg=msg))

    def warn(where, msg):
        out.append(dict(lv='warn', where=where, msg=msg))

    deck = [norm_card(c) for c in (plan.get('deck') or [])]
    if len(deck) > 10:
        bad('选卡', '卡槽只有 10 个，现在填了 %d 张' % len(deck))
    dup = {c for c in deck if deck.count(c) > 1}
    if dup:
        bad('选卡', '重复带卡：%s' % '、'.join(sorted(dup)))
    for c in deck:
        base = MIMIC if c == MIMIC else (mimic_target(c) or c)
        if base not in PLANT_ALL and c != MIMIC:
            bad('选卡', '未知卡片 %r' % c)
        if c == MIMIC:
            bad('选卡', '模仿者要选模仿对象（写成 模仿者:植物名）')
    allowed = set(deck_ops(deck))

    def check_op(where, b):
        op = LEGACY_OP.get(b.get('op'), b.get('op'))
        if op not in OP_BY_NAME:
            bad(where, '未知积木 %r' % b.get('op'))
            return
        spec = OP_BY_NAME[op]
        # ★ 2026-10-22：P（玉米炮）只看**场上有没有炮**，跟卡槽无关
        #   —— 炮是阵型的一部分，不是"这次带没带这张卡"。
        if deck and op != '玉米炮' and op not in allowed:
            warn(where, '%s 不在选卡里 —— 这一块永远打不出去' % op)
        if op.startswith('模仿') and engine_card(op) is None:
            warn(where, '引擎还没建模「%s」—— 能写进阵解，但跑起来会被记为未知卡片' % op)
        if spec['need_aim'] and not b.get('aim') and not spec.get('auto'):
            warn(where, '%s 没填落点（会用默认策略）' % op)

    def walk_gate(where, g, w=None):
        if not isinstance(g, dict):
            return
        k = g.get('kind')
        if k == 'prev':
            back = int(g.get('back') or 1)
            if back < 1:
                bad(where, 'prev 回看波数必须 ≥ 1')
            elif back > WAVES - 1:
                bad(where, 'prev 回看 %d 波 —— 一轮只有 %d 波，永远看不到' % (back, WAVES))
            elif w is not None and back >= int(w or 1):
                warn(where, '第 %s 波回看 %d 波会绕到上一轮的 w%d'
                     % (w, back, _prev_wave(w or 1, back)))
            op = g.get('op')
            if op and LEGACY_OP.get(op, op) not in OP_BY_NAME:
                bad(where, 'prev 里的动作 %r 不存在' % op)
        elif k == 'cell_is':
            if g.get('row') in (None, '') or g.get('col') in (None, ''):
                bad(where, 'cell_is 没填格子')
        elif k == 'plant_count':
            if not g.get('plant'):
                warn(where, 'plant_count 没选植物（默认按寒冰菇算）')
        elif k in ('all', 'any', 'not'):
            for sub in (g.get('of') or []):
                walk_gate(where, sub, w)

    rows = plan.get('waves') or []
    if len(rows) != WAVES:
        warn('整体', '波数是 %d（一轮按 %d 波算；缺的行不会跑任何积木）'
             % (len(rows), WAVES))
    for row in rows:
        w = row.get('w')
        where = 'w%s' % w
        if not row.get('sets'):
            warn(where, '这一波没有任何候选（= 空操作）')
        for si, st in enumerate(row.get('sets') or []):
            sw = '%s 候选%d' % (where, si + 1)
            walk_gate(sw, st.get('when'), w)
            if not st.get('ops'):
                warn(sw, '候选里没有积木')
            seen = set()
            for b in st.get('ops') or []:
                check_op(sw, b)
                name = LEGACY_OP.get(b.get('op'), b.get('op'))
                # ★ 2026-10-22：P 不占卡片 CD（只看每门炮自己的装填），
                #   所以"同一候选里两块玉米炮"完全合法 —— 那就是一对炮。
                if name == '玉米炮':
                    continue
                # ★ 垫材是**机会性**的：窗口没开 / 卡没好就静默跳过，
                #   所以"同一候选里 1 路一张、6 路一张"完全合法，
                #   多路轮着垫正是它该有的写法。
                if name in PAD_NAMES:
                    continue
                key = _card_key(name)
                if key in CARD_KEY.values():
                    if key in seen:
                        bad(sw, '同一候选里两张同名卡 —— 第二块必然卡在 CD')
                    seen.add(key)
        if not any((st.get('when') or {}).get('kind') in (None, 'always')
                   for st in row.get('sets') or []):
            warn(where, '候选链没有"总是"兜底 —— 条件全不成立时这一波什么都不做')

    for i, g in enumerate(plan.get('globals') or []):
        gw = '全场 %s' % (g.get('id') or (i + 1))
        walk_gate(gw, g.get('when'))
        if not g.get('ops'):
            bad(gw, '没有积木')
        for b in g.get('ops') or []:
            check_op(gw, b)

    for rule in plan.get('rescue') or []:
        rid = rule.get('id') or '?'
        if not rule.get('levels'):
            bad('救场 %s' % rid, '没有任何兜底层')
        for i, lv in enumerate(rule.get('levels') or []):
            ops = lv.get('ops') if isinstance(lv, dict) else lv
            for b in ops or []:
                check_op('救场 %s 第%d层' % (rid, i + 1), b)

    simple = plan.get('rescue_simple') or {}
    for i, t in enumerate(simple.get('targets') or []):
        tw = '简化救场 %s' % (t.get('id') or (i + 1))
        prot = t.get('protect') or {}
        if prot.get('row') in (None, '') or prot.get('col') in (None, ''):
            bad(tw, '没填要保护的格子')
    if simple.get('targets') and not simple.get('resources'):
        warn('简化救场', '没有任何救场资源 —— 有危险也不会出手')

    # ---- 波长串校验（用户 2026-10-22）：**可选**，填了才校验
    rh = plan.get('rhythm') or {}
    gaps = rh.get(GAPS_KEY) or []
    if gaps:
        beats_txt = '|'.join(rh.get('beats') or [])
        d = parse_track_full(beats_txt, None)
        beats = (d['variants'][0] if d['variants'] else [])
        for it in check_spectrum(beats, gaps, None, deck):
            if it['level'] == 'bad':
                bad('波长', it['msg'])
            elif it['level'] == 'warn':
                warn('波长', it['msg'])
    return out


# ------------------------------------------------------------------ 序列化
def _mig_block(b):
    if isinstance(b, dict) and 'op' in b:
        was = b['op']
        b['op'] = LEGACY_OP.get(was, was)
        # ★ 2026-10-22：取消的「窝瓜压车」→ 「在 5-9 种窝瓜」；
        #   触发时机原本写死在引擎里，现在留给用户用触发器表达。
        if was == '窝瓜压车' and b['op'] == '窝瓜' and not b.get('aim'):
            b['aim'] = [5, 9]
    return b


def _mig_gate(g):
    if not isinstance(g, dict):
        return g
    if g.get('kind') == 'ice_stock':
        return dict(kind='plant_count', plant='寒冰菇',
                    cmp=g.get('cmp'), value=g.get('value'))
    if isinstance(g.get('of'), list):
        g['of'] = [_mig_gate(x) for x in g['of']]
    return g


def norm(plan):
    """补齐缺省字段 + 迁移旧版写法"""
    p = json.loads(json.dumps(plan or {}, ensure_ascii=False))
    p.setdefault('format', FORMAT)
    p.setdefault('name', '未命名阵解')
    p.setdefault('note', '')
    # ★ v0.2.1：阵解绑定场地（行数 / 水路 / 基座 / 昼夜都由它决定）
    p.setdefault('field', 'PE')
    p.setdefault('deck', list(DEFAULT_DECK))
    p.setdefault('rhythm', dict(system='C', id='C4io', name='C4io',
                                beats=['N', "AA'", 'I', 'I'],
                                gaps=[], pair='auto'))
    p.setdefault('waves', [])
    p.setdefault('globals', [])
    p.setdefault('rescue', [])
    p.setdefault('rescue_simple', dict(enabled=True, resources=[], targets=[]))
    p.setdefault('slots', {})
    p.setdefault('params', {})
    for row in p['waves']:
        row['w'] = int(row.get('w') or 0)
        row['role'] = role_of(row['w'])
        row.setdefault('sets', [])
        for st in row['sets']:
            st.setdefault('when', {'kind': 'always'})
            st['when'] = _mig_gate(st.get('when'))
            st['ops'] = [_mig_block(b) for b in (st.get('ops') or [])]
            for b in st['ops']:
                b.setdefault('trig', {'kind': 'spawn'})
    for g in p['globals']:
        g.setdefault('enabled', True)
        g['when'] = _mig_gate(g.get('when') or {'kind': 'always'})
        g['ops'] = [_mig_block(b) for b in (g.get('ops') or [])]
    for r in p['rescue']:
        for i, lv in enumerate(r.get('levels') or []):
            if isinstance(lv, dict):
                lv['ops'] = [_mig_block(b) for b in (lv.get('ops') or [])]
            else:
                r['levels'][i] = [_mig_block(b) for b in (lv or [])]
    rs = p['rescue_simple']
    rs.setdefault('enabled', True)
    rs.setdefault('resources', [])
    rs.setdefault('targets', [])
    for t in rs['targets']:
        t.setdefault('urgency_cells', 1)
        t.setdefault('priority', 10)
    rs['resources'] = [_mig_block(b) for b in (rs.get('resources') or [])]
    # 选卡：把「模仿寒冰菇」折成「模仿者:寒冰菇」，再滤掉不认识的
    deck = []
    for c in (p.get('deck') or []):
        c = norm_card(c)
        base = mimic_target(c) or c
        if c != MIMIC and base not in PLANT_ALL:
            continue
        deck.append(c)
    p['deck'] = deck[:10]
    # 节奏：只存 id，显示名按命名方案现算
    r = p.get('rhythm') or {}
    pid = r.get('id')
    if not pid:
        pid = r.get('name') or 'C4io'
        for q in MI.RHYTHM_BY_ID.values():
            if pid in (q.get('trad'), q.get('new'), q.get('id')):
                pid = q['id']
                break
        r['id'] = pid
    if not r.get('beats'):
        preset = MI.RHYTHM_BY_ID.get(r['id'])
        r['beats'] = list(preset['beats']) if preset else ['N', "AA'", 'I', 'I']
    r.setdefault('system', 'C')
    r.setdefault('name', r['id'])
    # ★ 2026-10-22：波长串 / 简写复写
    g = r.get('gaps')
    if isinstance(g, str):
        try:
            g = parse_gaps(g)
        except ValueError:
            g = []
    r['gaps'] = [float(x) for x in (g or []) if float(x) > 0]
    if r.get('pair') not in ('auto', 'short', 'full'):
        r['pair'] = 'auto'
    p['rhythm'] = r
    p['waves'].sort(key=lambda r: r['w'])
    return p


def to_json(plan):
    return json.dumps(norm(plan), ensure_ascii=False, indent=2)


def from_json(text):
    return norm(json.loads(text))


# ------------------------------------------------------------------ 存放
def _plans_dir():
    """
    阵解存在哪。

    ★ 打包成 exe 之后 `__file__` 在临时解包目录里（退出即删），
      所以桌面版必须存到用户目录，否则「保存」等于没保存。
    """
    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
        return os.path.join(base, 'TrackCheck', 'plans')
    return os.path.join(ROOT, 'tools', 'trackcheck', 'plans')


PLANS_DIR = _plans_dir()


def plot_prefix(field_code):
    """阵型名的场地前缀：`[PE].`（用于**阵型**命名，不是阵解名）"""
    return '[%s].' % (field_code or 'PE')


def layout_name(field_code, bare):
    """阵型的全名：`[PE].电波钟无炮`（`[场地].` 由 app 自动生成）"""
    return plot_prefix(field_code) + (bare_name(bare) or '未命名阵型')


def full_name(plan_dict):
    """阵解的显示 / 存盘名 —— 就是它自己的名字（不再加场地前缀）。

    ★ 2026-10-22 用户口径修正：`[场地].名字` 是**阵型**（阵容布置）的命名规则；
      阵解可以有若干套、还会被不同场地的出怪组复用，名字里带场地前缀反而会错配。
    """
    p = plan_dict or {}
    return bare_name(p.get('name')) or '未命名阵解'


def bare_name(name):
    """把可能带 `[PE].` 前缀的名字剥成裸名"""
    s = (name or '').strip()
    if s.startswith('['):
        i = s.find('].')
        if i > 0:
            return s[i + 2:].strip()
    return s


def _slug(name):
    s = ''.join(ch for ch in str(name or 'untitled')
                if ch not in '\\/:*?"<>|').strip() or 'untitled'
    return s[:60]


def save_file(plan_dict, name=None):
    p = norm(plan_dict)
    if name:
        p['name'] = bare_name(name)
    os.makedirs(PLANS_DIR, exist_ok=True)
    path = os.path.join(PLANS_DIR, _slug(full_name(p)) + '.json')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(to_json(p))
    return dict(ok=True, path=path, name=full_name(p))


def list_files():
    if not os.path.isdir(PLANS_DIR):
        return []
    return sorted(n[:-5] for n in os.listdir(PLANS_DIR) if n.endswith('.json'))


def load_file(name):
    path = os.path.join(PLANS_DIR, _slug(name) + '.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return from_json(f.read())


# ------------------------------------------------------------------ 目录（给 UI）
def catalog():
    return dict(
        format=FORMAT, waves=WAVES,
        ops=OPS, triggers=TRIGGERS, gates=GATES, events=EVENTS,
        zombies=ZOMBIE_FILTERS, rhythms=RHYTHM_SYSTEMS,
        cards=ALL_CARDS, plants=PLANT_ALL, mimic=MIMIC,
        card_key=CARD_KEY, default_deck=DEFAULT_DECK,
        engine_cards=MI.ENGINE_CARDS,
        layout_letters=LAYOUT_LETTERS,
        naming=dict(options=MI.NAMINGS, default=MI.DEFAULT_NAMING),
        roles={str(w): role_of(w) for w in range(1, WAVES + 1)},
        regular=[w for w in range(1, WAVES + 1) if is_regular(w)],
        # ★ 2026-10-22：轨道结构符号 / 简写复写 / 波长串
        track_seps=[dict(ch=k, kind=v) for k, v in TRACK_SEP.items()
                    if k in '|-/~'],
        pair_modes=[
            dict(id='auto', label='自动辨认（出现 PP 就当复写）'),
            dict(id='short', label='简写：P = 一对炮'),
            dict(id='full', label='复写：P = 单门炮（自己写 PP）'),
        ],
        pair_default='auto',
        gaps_key=GAPS_KEY,
        cob_cd=COB_CD, long_card_cd=LONG_CARD_CD,
        p_min=P_MIN, c_min=C_MIN,
    )


def rhythm_of(plan, naming=None):
    """阵解的节奏型显示名（按命名方案）"""
    return MI.rhythm_label((plan or {}).get('rhythm'), naming or MI.DEFAULT_NAMING)


# ------------------------------------------------------------------ 内置阵解
def _b(op, aim=None, trig=None, repeat=None):
    d = dict(op=op, aim=aim, trig=trig or {'kind': 'spawn'})
    if repeat:
        d['repeat'] = repeat
    return d


def _set(when, *ops):
    return dict(when=when or {'kind': 'always'}, ops=list(ops))


N = {'kind': 'card_ready', 'card': '毁灭菇'}
AA = {'kind': 'all', 'of': [{'kind': 'card_ready', 'card': '樱桃'},
                            {'kind': 'card_ready', 'card': '辣椒'}]}
ANY_ASH = {'kind': 'any', 'of': [{'kind': 'card_ready', 'card': '樱桃'},
                                 {'kind': 'card_ready', 'card': '辣椒'}]}
ICE1 = {'kind': 'plant_count', 'plant': '寒冰菇', 'cmp': '>=', 'value': 1}
ICE0 = {'kind': 'plant_count', 'plant': '寒冰菇', 'cmp': '<=', 'value': 0}

STOCK = [(3, 2), (3, 3), (4, 3), (5, 3)]
TEMP = [(2, 7), (5, 7)]


def default_dianbozhong():
    """把 `config_dianbozhong.track()` 的判定式轨道**转写成积木**（v0.3 说法）"""
    rows = []

    def row(w, sets, note=''):
        rows.append(dict(w=w, role=role_of(w), note=note, sets=sets))

    row(1, [_set(N, _b('毁灭菇', [2, 8]),
                 _b('寒冰菇', [2, 7], trig={'kind': 'time', 'at': 0}),
                 _b('模仿寒冰菇', [5, 7], trig={'kind': 'time', 'at': 400})),
            _set(ICE1, _b('咖啡豆')),
            _set(None, _b('寒冰菇', [2, 7]))],
        'C4io 锚点：2-9 反应核 + 两个前场临时存冰（I / I′ 各一张）')

    def regular(w, note):
        row(w, [
            _set({'kind': 'all', 'of': [N, ANY_ASH, {'kind': 'kernel_slack'}]},
                 _b('毁灭菇', [5, 9])),
            _set(AA, _b('樱桃', [2, 8]), _b('辣椒')),
            _set(ANY_ASH, _b('樱桃', [5, 8])),
            _set(ICE1, _b('咖啡豆')),
            _set(None, _b('寒冰菇', None, trig={'kind': 'card', 'name': '寒冰菇'})),
        ], note)

    regular(2, 'AA′：2-8 樱桃 + 5 路辣椒；缺一张就先拆开用')
    regular(3, '铺节奏')
    regular(4, '补 AA′ 的欠账')
    for w in list(range(5, 9)) + list(range(11, 19)):
        regular(w, 'C4io：N → AA′ → I → I，按 CD + 坑位择一拍')

    for w in (9, 19):
        row(w, [_set(ANY_ASH, _b('樱桃', [2, 8]), _b('辣椒')),
                _set(ICE1, _b('咖啡豆')),
                _set(None, _b('寒冰菇', None, trig={'kind': 'card', 'name': '寒冰菇'}))],
            '收尾波：照常控丑，但不点核（留给下一个旗波锚点）')

    row(10, [_set(None, _b('咖啡豆'),
                  # ★ 2026-10-22：「窝瓜压车」取消，改成"在 5-9 种窝瓜" +
                  #   由"5 路冰车快到 5-9"这个距离条件触发
                  _b('窝瓜', [5, 9], trig={'kind': 'dist', 'zombie': '冰车',
                                          'row': 5, 'col': 9, 'axis': 'x',
                                          'cmp': '<=', 'value': 80})),
             _set(ICE0, _b('寒冰菇', None, trig={'kind': 'card', 'name': '寒冰菇'}))],
        '旗波：冰杀蹦极 + 5 路冰车将近 5-9 时种窝瓜，保住核坑')
    row(20, [_set(None, _b('咖啡豆')),
             _set(ICE0, _b('寒冰菇', None, trig={'kind': 'card', 'name': '寒冰菇'}))],
        'w20：清账')

    rows.sort(key=lambda r: r['w'])

    return norm(dict(
        format=FORMAT,
        name='电波钟无炮',
        note='C4io 判定式轨道的积木化版本（内置判定轨道仍可用，两者可同场对比）',
        deck=list(DEFAULT_DECK),
        rhythm=dict(system='C', id='C4io', name='C4io', beats=['N', "AA'", 'I', 'I'],
                    note='4 拍循环；N=毁灭菇、A=樱桃、A′=辣椒、I=寒冰菇'),
        waves=rows,
        # 全场判定：冰卡一好就补在空着的永久存冰位
        globals=[
            dict(id='补存冰', enabled=True, every=50, cooldown=0,
                 note='冰卡一好就补：3-2 / 3-3 / 4-3 里第一格空着的',
                 when={'kind': 'all', 'of': [
                     {'kind': 'card_ready', 'card': '寒冰菇'},
                     {'kind': 'any', 'of': [
                         {'kind': 'cell_is', 'row': 3, 'col': 2, 'plant': ''},
                         {'kind': 'cell_is', 'row': 3, 'col': 3, 'plant': ''},
                         {'kind': 'cell_is', 'row': 4, 'col': 3, 'plant': ''}]}]},
                 ops=[_b('寒冰菇', 'stock')]),
        ],
        rescue_simple=dict(
            enabled=True,
            note=('岸路 2-6 的曾哥优先级最高，但可以等僵尸贴脸（急迫级 0 格）；'
                  '边路 1-5 的大喷差一格就该救（急迫级 1 格），优先级低一档'),
            resources=[_b('小喷菇'), _b('花盆'), _b('窝瓜')],
            targets=[
                dict(id='2-6 曾哥', protect={'row': 2, 'col': 6},
                     urgency_cells=0, priority=100, cooldown=60),
                dict(id='5-6 曾哥', protect={'row': 5, 'col': 6},
                     urgency_cells=0, priority=100, cooldown=60),
                dict(id='1-5 大喷', protect={'row': 1, 'col': 5},
                     urgency_cells=1, priority=30, cooldown=60),
                dict(id='6-5 大喷', protect={'row': 6, 'col': 5},
                     urgency_cells=1, priority=30, cooldown=60),
            ]),
        rescue=[
            dict(id='垫材', note='僵尸能打到 6 列就下；小喷菇→花盆→窝瓜 三层兜底',
                 cooldown=10,
                 event=dict(kind='zombie_in_window', rows=[6, 5, 1], col=6,
                            window=[10, 75], min_hp=500, zombie='任意'),
                 levels=[[_b('小喷菇')], [_b('花盆')], [_b('窝瓜')]]),
            dict(id='窝瓜强杀', note='重甲逼近 CORE 3 格内，垫材全 CD 也要拦',
                 cooldown=30,
                 event=dict(kind='heavy_near_core', rows=[6, 5, 2, 1], cells=3),
                 levels=[[_b('窝瓜')]]),
            dict(id='救急冰', note='裸 CORE 要被砸、且垫材/窝瓜都不可用',
                 cooldown=300,
                 event=dict(kind='bare_core_threat'),
                 levels=[[_b('咖啡豆')]]),
        ],
        slots=dict(kernel=list(CFG.KERNEL_SLOTS),
                   stock=STOCK, temp_ice=TEMP,
                   chili=list(CFG.CHILI_SLOT), cherry_row=CFG.CHERRY_ROW,
                   cherry_cols=list(CFG.CHERRY_COLS),
                   fast_fog=list(CFG.FAST_LUNGBU_SPOTS)),
        params=dict(skip_hp=CFG.SKIP_HP, stall_hp=CFG.STALL_HP,
                    tomato_x=CFG.TOMATO_X, tomato_hp=CFG.TOMATO_HP),
    ))


def builtin(name='电波钟无炮'):
    return default_dianbozhong()


# ══════════════════════════════════════════════════════════════════
# 示例：PE.经典八炮（常规炮阵，用户 2026-10-22 提供的阵型字符串）
# ══════════════════════════════════════════════════════════════════
CLASSIC8_STR = (
    '0,2C 1 2 0 0 0,1E 1 2 0 0 1,30 1 2 0 0 0,2C 1 3 0 0 0,1E 1 3 0 0 1,'
    '30 1 3 0 0 0,2C 1 4 0 0 0,1E 1 4 0 0 1,30 1 4 0 0 0,2F 1 5 0 0 0,'
    '2A 2 2 1 0 0,1E 2 2 0 0 1,30 2 2 0 0 0,25 2 3 0 0 0,1E 2 3 0 0 1,'
    '30 2 3 0 0 0,2C 2 4 0 0 0,1E 2 4 0 0 1,30 2 4 0 0 0,2F 2 5 0 0 0,'
    '10 3 1 0 0 0,2F 3 1 0 0 0,10 3 2 0 0 0,10 3 3 0 0 0,2F 3 3 0 0 0,'
    '10 3 4 0 0 0,10 3 5 0 0 0,2C 3 5 0 0 0,1E 3 5 0 0 0,10 3 6 0 0 0,'
    '25 3 6 0 0 0,1E 3 6 0 0 0,10 3 7 0 0 0,2A 3 7 1 0 0,1E 3 7 0 0 0,'
    '10 4 1 0 0 0,2F 4 1 0 0 0,10 4 2 0 0 0,10 4 3 0 0 0,2F 4 3 0 0 0,'
    '10 4 4 0 0 0,10 4 5 0 0 0,2C 4 5 0 0 0,1E 4 5 0 0 0,10 4 6 0 0 0,'
    '29 4 6 0 0 0,1E 4 6 0 0 0,10 4 7 0 0 0,2A 4 7 1 0 0,1E 4 7 0 0 0,'
    '2A 5 2 1 0 0,1E 5 2 0 0 1,30 5 2 0 0 0,25 5 3 0 0 0,1E 5 3 0 0 1,'
    '30 5 3 0 0 0,2C 5 4 0 0 0,1E 5 4 0 0 1,30 5 4 0 0 0,2F 5 5 0 0 0,'
    '2C 6 2 0 0 0,1E 6 2 0 0 1,30 6 2 0 0 0,2C 6 3 0 0 0,1E 6 3 0 0 1,'
    '30 6 3 0 0 0,2C 6 4 0 0 0,1E 6 4 0 0 1,30 6 4 0 0 0,2F 6 5 0 0 0')


def example_classic8():
    """PE.经典八炮：**常规炮阵的样板**（用户 2026-10-22 给的阵型字符串）

    阵型：8 门玉米炮（1-5 / 2-5 / 3-1 / 3-3 / 4-1 / 4-3 / 5-5 / 6-5）、
          10 张冰瓜、4 张忧郁菇、3 把保护伞、1 个双子花；岸路（2/5）2 列曾 + 梯子南瓜。
    阵解：**P4 = P|P|P|P(9,9,9,9)** —— 9s 一对炮，落点 2-8 / 5-8。

    两门炮的分工（**这是落点必须分开写的原因**）：
      仰 2-8 → 爆心 y = 2 路植物 y + 40，圆 R=115 纵向上盖住 **1/2/3/4 路**
      仰 5-8 → 同法盖住 **4/5/6 路**
    `aim` 留空时两门炮各自自动索敌，会一起挑"最密的那一路"→ 另三路整场没挨炸。

    边路（1/6）没有曾哥，红眼吃满 3 次炮（5400）后还差"约一个路障的输出"，
    所以按用户口径带满 **4 张垫材**（小喷菇/花盆/阳光菇/胆小菇）：
    巨人一锤就把 300hp 的垫材砸没（攻击是离散的，周期 330cs），
    所以 2 张短 cd 卡就能把一路巨人**钉在炮的判定域里打死**。
    """
    from . import layout as LY
    arr, _fld, _rake = LY.decode_tools(CLASSIC8_STR, 'PE')
    p = template('PE')
    p['name'] = '经典八炮'
    p['note'] = ('P4：P|P|P|P(9,9,9,9)，9s 一对炮。一门仰 2-8 盖 1~4 路、'
                 '一门仰 5-8 盖 4~6 路 —— **落点必须分开写**，留空会让两门炮'
                 '一起挑最密的一路、另三路整场不挨炸。'
                 '垫材属于**救场**（不进轨道）：只在边路巨人真的逼近时才垫一张，'
                 '循环狂垫会把阳光吃光。')
    # 这个阵基本不需要灰烬/冰 → 按用户口径带满 4 张垫材；
    # 咖啡豆留给"新种的蘑菇是睡着的"（补曾 / 补大喷要顺手唤醒）
    p['deck'] = ['玉米炮', '小喷菇', '花盆', '阳光菇', '胆小菇',
                 '南瓜', '樱桃', '辣椒', '窝瓜', '咖啡豆']
    p['rhythm'].update(system='P', id='P4', name='P4', beats=['P', 'P', 'P', 'P'],
                       gaps=[9, 9, 9, 9], pair='short')

    # ★★ 2026-10-22 用户：「垫材视作**救场**而不是轨道；一直循环垫垫材让经济压力不小」
    #   → 轨道里**只有炮**（和"两对炮好了才开"的条件块），
    #     垫材全部下沉到简化救场层：只在"边路有僵尸真的逼近这一门炮"时才垫一张，
    #     而且垫在 **8 列**（炮的判定域里），不是固定垫材位。
    PAD_COL = 8               # x=600，正好在炮的判定域（z.x∈[482,712]）正中
    # 8 门炮的格子（1×2 占格，记前格）—— 救场层的保护对象
    COBS = ((1, 5), (2, 5), (3, 1), (3, 3), (4, 1), (4, 3), (5, 5), (6, 5))

    def pair(at=700):
        return [_b('玉米炮', [2, 8], trig={'kind': 'time', 'at': at}),
                _b('玉米炮', [5, 8], trig={'kind': 'time', 'at': at})]

    def pad_bar():
        """收尾波的第二对炮：**只有"两对炮都好了"才开**（用户口径）
        —— 别再无限垫下去，直接开一对，另一对留给下一波。"""
        return [_b('玉米炮', [2, 8], trig={'kind': 'state', 'what': 'cobs_ready',
                                          'cmp': '>=', 'value': 4, 'ttl': 9000}),
                _b('玉米炮', [5, 8], trig={'kind': 'state', 'what': 'cobs_ready',
                                          'cmp': '>=', 'value': 4, 'ttl': 9000})]

    for r in p['waves']:
        w = int(r['w'])
        ops = pair()
        if w == 20:                     # 最后一波：不留余量，能开几对开几对
            ops += pad_bar()
        elif w in (9, 19):
            # 收尾：一旦两对炮（4 门）装填完毕就直接开一对（垫材由救场层按需出手）
            ops += pad_bar()
            r['note'] = '收尾：两对炮好了就开一对，另一对留给下一波（垫材按需，救场层管）'
        r['sets'] = [dict(when={'kind': 'always'}, ops=ops)]
    p['waves'][0]['note'] = '起手：一对炮打 2-8 / 5-8（垫材由救场层按需出手）'
    for w in (10, 20):
        next(x for x in p['waves'] if int(x['w']) == w)['note'] = \
            '旗波：一对炮（旗波出怪整体右移 40px，落点不变）'

    # ---- 简化救场层：把"救急卡"丢进去，贴脸才出手
    #   用户口径：「这些意外发生时樱桃、窝瓜这些救急卡肯定是好的、能用，
    #   丢进救急层（贴脸才救急）把它们种出去」。
    #   urgency_cells = 1（≈ 距目标 1 格 + 45px）—— =0 是纯"已经开始啃"，
    #   ★ 但灰烬的**结果导向口径是"种植即生效"**（`ASH_DELAY=0`），
    #     而救场层是在"僵尸已经贴到植物上"那一刻才判定的，
    #     所以这里留 1 格余量，让救急卡在它真贴上之前落地。
    #   （即：模型不计生效时延，救场策略仍然要提前一格，两回事。）
    #   资源顺序就是优先级：先炸（樱桃 R115）→ 再压（窝瓜）→ 再整行（辣椒）
    #   → 最后两张是垫材（挡住，让炮自己解决）。
    #   ★ 用户 2026-10-22：「垫材视作救场而不是轨道；一直循环垫垫材让经济压力不小」
    #     → 垫材**只在有人逼近这一门炮时才垫一张**（救场层按需出手），
    #       种在**僵尸脚下那一格**（`pad_col: 'front'`）—— 那一格就在炮的判定域里，
    #       僵尸停下来啃的时候仍然挨炮。
    #   urgency_cells = 2：僵尸走到"离炮还有 2 格"才出手（不是全程循环垫）。
    p['rescue_simple'] = dict(
        enabled=True,
        resources=[{'op': '樱桃'}, {'op': '窝瓜'}, {'op': '辣椒'},
                   {'op': '小喷菇', 'pad_col': 'front'},
                   {'op': '花盆', 'pad_col': 'front'},
                   {'op': '阳光菇', 'pad_col': 'front'},
                   {'op': '胆小菇', 'pad_col': 'front'}],
        targets=[dict(id='%d-%d 炮' % (r, c), protect={'row': r, 'col': c},
                      urgency_cells=2, priority=100 - 10 * c + r,
                      cooldown=50, include_icecar=True)
                 for (r, c) in COBS])
    p = norm(p)
    return dict(ok=True, field='PE', name='经典八炮',
                array={'%d-%d' % k: v for k, v in arr.items()},
                string=CLASSIC8_STR, plan=p)


def example_split_aa():
    """示例：**把 C4io 的 AA′ 拆到两波**（`prev` 条件最典型的用法）"""
    p = default_dianbozhong()
    p['name'] = '示例 · C4io 拆开 AA′'
    p['note'] = ('AA′ 拆到两波：第 x 波只打 A′（辣椒），第 x+1 波用 prev 条件'
                 '判断上一波是不是只用了 A′，是就补 A（樱桃），否则走原来的节奏')
    groups = list(range(5, 9)) + list(range(11, 19))

    def split_sets():
        return [
            _set({'kind': 'all', 'of': [
                {'kind': 'card_ready', 'card': '毁灭菇'},
                {'kind': 'card_ready', 'card': '樱桃'},
                {'kind': 'card_ready', 'card': '辣椒'}]},
                _b('毁灭菇', [5, 9])),
            _set({'kind': 'card_ready', 'card': '辣椒'}, _b('辣椒')),
            _set({'kind': 'card_ready', 'card': '樱桃'}, _b('樱桃', [2, 8])),
            _set(None, _b('咖啡豆')),
        ]

    makeup = dict(when={'kind': 'all', 'of': [
        {'kind': 'prev', 'back': 1, 'target': 'act', 'op': '辣椒'},
        {'kind': 'prev', 'back': 1, 'target': 'act', 'op': '樱桃',
         'negate': True}]},
        ops=[_b('樱桃', [2, 8])])

    for row in p['waves']:
        w = row['w']
        if w in groups:
            row['sets'] = split_sets()
            row['note'] = 'AA′ 拆开：双卡齐就一起打，否则先打 A′'
        elif (w - 1) in groups:
            row['sets'] = [json.loads(json.dumps(makeup))] + list(row['sets'])
            row['note'] = '上一波若只用了 A′，这里补 A；否则按原节奏走'
    return norm(p)


# ------------------------------------------------------------------ JSON 格式说明
def spec_text(what='plan'):
    """给用户/给 AI 看的格式说明（"i" 按钮里显示的就是这段）"""
    if what == 'plan':
        return _SPEC_PLAN.format(
            fmt=FORMAT, waves=WAVES,
            ops='、'.join(OP_NAMES),
            gates='、'.join(g['kind'] for g in GATES),
            triggers='、'.join(t['kind'] for t in TRIGGERS),
            events='、'.join(e['kind'] for e in EVENTS),
            cards='、'.join(ALL_CARDS),
            letters='；'.join('%s = %s' % (k, '+'.join(v))
                              for k, v in LAYOUT_LETTERS.items()))
    if what == 'spawn':
        return _SPEC_SPAWN
    if what == 'spawnmech':
        return _SPEC_SPAWN_MECH
    if what == 'layout':
        return _SPEC_LAYOUT
    if what == 'resultonly':
        return _SPEC_RESULT_ONLY
    return _SPEC_CONFIG


_SPEC_RESULT_ONLY = """# TrackCheck · 建模总原则：**结果导向**

简化模型里，操作"什么时候写完"就等于"结果什么时候出现"。
下面这些时延在原版里是真实存在的（`[精]` 有据可查），
但在本工具里**一律不计**，只作为注释保留：

| 项 | 原版数值 | 本工具 |
|---|---|---|
| 炮落点 | 落点是**准星**，爆炸中心 = 准星 x − 7 | **落点就是爆炸中心**，不折算 |
| 炮：开炮 → 爆炸 | 373~392cs（屋顶 359~392） | **0** |
| 樱桃 / 辣椒：放置 → 生效 | 100cs | **0** |
| 毁灭菇 / 白昼寒冰菇：放置 → 生效 | 298~299cs（含咖啡豆） | **0** |
| 白天蘑菇：点咖啡豆 → 唤醒 | 100cs | **0** |
| 子弹飞行时间 | 各有命中延迟（豌豆 34cs 等） | **不模拟子弹**，伤害在攻击那一瞬结算 |

## 为什么这么做

你要判断的是「**这条轨道能不能成立**」——落点、时机、运算量够不够。
子弹飞了几厘秒、咖啡豆什么时候醒，只改变毫厘级的时序，
却会让"我写的 `[2,8]` 到底炸在哪"变得难以预测。

## 例外（仍然保留的时延）

- 炮的**装填**（3475cs，每门独立）——这是硬约束，不是时延
- 灰烬 / 冰的**卡片 CD**（50s）——同理
- 冰冻 / 减速的**持续时长**（冰冻 400~600cs、减速 1000/2000cs）
- 忧郁菇一轮内 4 次命中的分摊（74/102/130/158cs）——这是它的伤害结构，不是飞行时间
"""


_SPEC_LAYOUT = """# TrackCheck 阵容布置 说明

## 界面上的每一项

| 位置 | 含义 |
|---|---|
| 场地 | PE 泳池（白天）/ FE 雾夜 / DE 白昼前院 / NE 黑夜前院 / RE 天台。决定行数、格高、y 坐标、水路、昼夜、浓雾、墓碑、斜坡、基座与禁出僵尸 |
| 阵型名 | 格式 `[场地].名字`，例如 `[PE].电波钟无炮`。`[场地].` 这一截由 app 自动生成，你只填后面的名字；换场地时前缀自动跟着变 |
| 主植物 | 除 南瓜 / 睡莲 / 花盆 之外的 45 张卡，另可写 `模仿者:X` |
| 醒着 | **只有蘑菇才有睡眠**。阵图里预置的常驻蘑菇视为已醒；寒冰菇 / 毁灭菇这类待触发的可以留成睡着 |
| 套南瓜 | 独立的 4000 血一层壳 |
| 搭梯 | 梯子南瓜：除巨人与冰车外的僵尸会**直接走过去**。**水路不能搭梯**（勾选框锁死）；
套南瓜必须先勾，梯子跟着南瓜走 |
| 有睡莲 / 花盆 | 基座。**空地可以先不放底座**；但只要这格有植物、套了南瓜或搭了梯，PE / FE 的水路与 RE 的屋顶就必须有底座（界面会自动锁定勾上）。草地只能放花盆，不能放睡莲 |
| 墓碑 | 只有 NE 会出现；墓碑吞噬者可以直接清掉 |

## 玉米炮（1×2）

玉米炮占**两格**：头格（你点的那格）是本体，**右边一格的列号大 1**的那格是尾格。
尾格在图上标「炮尾」，不能种东西、不能套南瓜。

- 水路 / 屋顶：**两格都要底座**（睡莲 / 花盆），生成字符串时会自动补上
- **不能套南瓜、不能搭梯**（这两个勾选框会锁死）
- 第 9 列放不下玉米炮（尾格越界）

## JSON（导入/导出用）

```json
{
  "field": "PE",
  "name": "电波钟无炮",
  "array": {
    "1-1": {"plant": "忧郁菇", "pumpkin": true, "ladder": false,
            "awake": true, "base": null, "grave": false},
    "3-2": {"plant": "寒冰菇", "awake": false, "base": "睡莲"},
    "3-4": {"plant": "玉米炮", "base": "睡莲", "pumpkin": false},
    "3-5": {"plant": null, "base": "睡莲"}
  }
}
```

- `name` 是**阵型名的裸名**（不带 `[PE].`），全名 = `[` + `field` + `].` + `name`
- 键是 `"行-列"`，行 1 在最上面、列 1 最靠近家门
- `plant` 为 `null` 表示这一格没有主植物（但可能只有南瓜 / 基座 / 墓碑）
- `awake: false` 只是"睡着"的标记，`寒冰菇 + awake:false` ≡ 引擎内部的「存冰」
- **底座规则**（`base`）：水上只能是 `睡莲`、屋顶/草地只能是 `花盆`；
  空地可以不写 `base`；写了植物 / `pumpkin` / `ladder` 或 `plant == "玉米炮"` 时，
  水上与屋顶的格子**必须**有 `base`（写文件时会自动补）
- **水路不会有 `ladder`**：梯子只能搭在陆地 / 屋顶的南瓜上，写进去也会被清掉
- 玉米炮的尾格在 JSON 里是一条 `plant: null` + `base: "睡莲"` 的记录（屋顶是花盆）

## PvZ Tools 阵型字符串（RFC1437）

点「生成字符串」/「导入」即可与 PvZ Tools 互通。编码规则：
Base64 → 整体异或 `0x54` → zlib 流 + 1 字节 RS（高 4 位钉耙行、低 4 位场景）。
场景代号：0 白天 / 1 黑夜 / 2 泳池 / 3 雾夜 / 4 屋顶 / 5 月夜。
每格 16 位：`P(10~15) PI(9) PA(8) B(6~7) BI(5) K(4) KI(3) C(2) CI(1) L(0)`。

## 注意

- 5 行场地（DE / NE / RE）只有 45 格，第 6 行的内容会被忽略
- 玉米炮占 **1×2**（尾格不能种、不能套南瓜；水上/屋顶两格都要底座）
- 阵地空格可以只放一个底座（睡莲 / 花盆），也可以什么都不放
"""


_SPEC_PLAN = """# TrackCheck 阵解 JSON 格式说明（format = {fmt}）

## 顶层

```json
{{
  "format": "{fmt}",
  "name": "电波钟无炮",
  "note": "给人看的说明",
  "field": "PE",
  "deck": ["寒冰菇","模仿者:寒冰菇","毁灭菇","樱桃","辣椒","窝瓜","小喷菇","花盆","南瓜","咖啡豆"],
  "rhythm": {{"system":"C","id":"C4io","beats":["N","AA'","I","I"]}},
  "waves":        [ ... ],
  "globals":      [ ... ],
  "rescue_simple":{{ ... }},
  "rescue":       [ ... ],
  "slots":        {{ ... }},
  "params":       {{ ... }}
}}
```

- `field`：场地代码，`PE`（默认）/ `FE` / `DE` / `NE` / `RE`。
  它决定行数、格高、y 坐标、水路、昼夜（蘑菇睡不睡）、浓雾、墓碑、斜坡、
  种植基座（水上要荷叶 / 屋顶要花盆）与**禁出僵尸**。
- `deck`：10 张卡。可选的是初代全部 **48** 张植物（含吸金磁）+ `模仿者`；
  **模仿者要写二级对象**，形如 `"模仿者:寒冰菇"`（= 旧写法的「模仿寒冰菇」）。
  当前引擎真正认识的是：寒冰菇 / 毁灭菇 / 樱桃 / 辣椒 / 窝瓜 / 小喷菇 / 花盆 /
  南瓜 / 大蒜 / 咖啡豆 / 大喷菇 / 忧郁菇 / 冰瓜 / 香蒲 / 荷叶 / 保护伞 / 双子花 /
  **玉米炮 / 地刺 / 钢地刺 / 高坚果 / 双向射手 / 机枪射手 / 火炬树桩 / 磁力菇 /
  三叶草 / 墓碑吞噬者**，以及 `模仿者:寒冰菇`、`模仿者:毁灭菇`；
  其余卡能选可写，跑起来会记「未知卡片」。
- `玉米炮` 的 `aim` 是**爆炸中心**（可以任意行，**行列都允许一位小数**，如 `[3, 7.5]`），
  不是"种在哪"。P 不指定具体哪一门炮 —— 引擎自动挑"装填好了、剩余 CD 最短"的那门，
  每门炮各自有 3475cs 的独立计时器；**忽略释放到爆炸的时延**（写下的那一刻就爆）。
- `rhythm.id` 是节奏型的**规范 id**（`C4io` / `N4` / `D5` / `I6` …）。
  显示名按「设置 → 节奏命名方案」在 **2021 传统 / 2026 新版 / 双轨**之间切换，
  所以 JSON 只存 id，不存显示名。
- 后文所有"种什么"都写**植物名**，不写"点存冰 / 补存冰"：
  - 唤醒存冰 = 在那一格**种咖啡豆**
  - 补存冰   = 在那一格**种寒冰菇**
  - 查存冰   = 查**场上寒冰菇数量**（plant_count）或**某格是什么植物**（cell_is）

## 蘑菇的睡眠（2026-10-22 用户口径）

- **阵图里本来就是醒的，永远醒着**：忧郁菇 / 大喷菇 / 磁力菇 … 这些常驻蘑菇照常工作。
- **阵图里的寒冰菇是睡着的**（这就是"存冰"）。
- **新种下的蘑菇一定是睡着的** —— 不管白天还是晚上；想让它干活，必须在**同一格**
  再种一颗 `咖啡豆`（`咖啡豆` 积木 + `aim` = 那一格）。
- **已经唤醒的蘑菇永远醒着**，不会到点又睡回去。
- 所以「种下即冻」「种下即炸」在模型里都做不到：先睡下，再用咖啡豆唤醒。

## 节奏（rhythm）

```json
"rhythm": {{"system": "C", "id": "P4", "beats": ["P","P","P","P"],
            "gaps": [9, 9, 9, 9], "pair": "auto"}}
```

- `beats` 是社区简式轨道，按 `|` 分隔；「快捷布置阵解」把它循环铺到
  w2~w{waves} 的常规波（跳过旗波 w10/w20），只填"做什么"，落点/时机/兜底留空。
- `gaps` 是**波长串**（秒）：每拍 → 下一波刷新的间隔。界面上写 `(9,9,9,9)` 或 `(9|9|9|9)`。
- `pair` 决定**对称操作写一个还是一对**：
  - `"auto"`（默认）出现连续两个 P（`PP`）就按复写，否则按简写
  - `"short"` 简写：`P|P|P|P` = 4 对炮（8 门）
  - `"full"` 复写：`PP|PP|PP|PP` 才是一对，`P` = 单门

### 轨道能认的分隔符

| 符 | 名称 | 快捷布置怎么处置 |
|---|---|---|
| `|` | 隔离符（换波） | 下一拍 |
| `-` | 刷新符（同一波的第二个时机） | 同一波里再排一组积木，触发器 = `after`，**时间留空** |
| `/` | 分场符（上下半场同时） | 两组操作进同一个时机，落点全部留空；分场本身就表示"一对"，不再按简写翻倍 |
| `~` | 波动符（两套节奏摆动） | 两套**逐循环交替**铺进去 |

字母表：{letters}

### 波长校验（`gaps` 填了就会查）

- 含 P：波长和 ≥ **36s**；34~35s 是极限（警告）；< 34s 直接不可能
- 含长 CD 卡（灰烬 / 冰，卡 CD 50s）：波长和 ≥ **54s**，否则警告
- 据此推算「这个循环至少要几门炮」：`ceil(发数 ÷ (波长和 ÷ 34.75s))`
  —— 例 `I-PP|I-PP|N|PP(18,18,9,9)`：54s ≈ 1.55 个炮 CD，6 发 P → **4 门炮**够
- 还会查"波长和过去之后，循环的第一个操作能不能重新用"

## 表层轨道（waves[]）

```json
{{"w": 5, "note": "",
  "sets": [
    {{"when": {{"kind":"all","of":[
                 {{"kind":"card_ready","card":"毁灭菇"}},
                 {{"kind":"card_ready_within","card":"樱桃","waves":0.9}},
                 {{"kind":"kernel_slack","cmp":">=","value":0}}]}},
     "ops": [
       {{"op":"毁灭菇","aim":[5,8],"trig":{{"kind":"spawn"}}}},
       {{"op":"寒冰菇","aim":[3,2],"trig":{{"kind":"card","name":"寒冰菇","offset":0}}}}
     ]}},
    {{"when": {{"kind":"always"}}, "ops": [ ... ]}}
  ]}}
```

`sets` 是**候选兜底链**：从上往下第一个 `when` 成立的候选胜出（= if / elif / else）。
`ops` 是**积木序列**：第一块 = 刷怪即刻，后面的靠触发器。

- `op` 只能填：{ops}
- `aim` = `[行, 列]`（行 1~6，列 1~9）；不给就用默认策略
- 触发器 `trig.kind` 只能填：{triggers}
  - `spawn` 刷怪即刻｜`time{{"at":cs}}` 波内时间｜`after{{"at":cs}}` 上一块之后
  - `card{{"name":"寒冰菇","offset":0}}` 卡片 CD 转好
  - `dist{{"zombie":"巨人","row":6,"col":6,"axis":"x","cmp":"<=","value":160}}` 距离
  - `state{{"what":"sun","cmp":">=","value":100}}` 场况
- 循环：给积木加 `"repeat": {{"every": 100, "times": 3}}`（`times` 省略 = 一直循环）
- 条件 `when.kind` 只能填：{gates}
  - `prev{{"back":1,"target":"act","op":"樱桃"}}` = 上一波**真的打出**了樱桃
    （`target:"set"` 看"选中的是哪个候选"；`"negate":true` 取反）

## 全场判定（globals[]）

```json
{{"id":"补存冰","enabled":true,"every":50,"cooldown":0,
  "when": {{"kind":"card_ready","card":"寒冰菇"}},
  "ops":  [{{"op":"寒冰菇","aim":[3,2]}}]}}
```
每 tick 判一次条件，成立就把 ops 依次做掉（中途有一块失败就放弃这一轮）。
`every` = 隔多少 cs 才判一次（0 = 每 tick 都判）。

## 简化救场（rescue_simple）

```json
{{"enabled": true,
  "resources": [{{"op":"小喷菇"}},{{"op":"窝瓜"}},{{"op":"咖啡豆","aim":[3,2]}}],
  "targets": [
    {{"id":"2-6 曾哥","protect":{{"row":2,"col":6}},
      "urgency_cells":0,"priority":100,"cooldown":60}}]}}
```
- `resources`：交给救场处理器的资源，按顺序试，用不了就换下一份
- `targets[].protect`：要保护的格子
- `urgency_cells`：僵尸距它还有几格就开始救（0 = 贴脸才救；1 = 差一格就救）
- `priority`：都在危险里时谁先救（数值大的先）

## 详细救场（rescue[]）

```json
{{"id":"垫材","cooldown":10,
  "event": {{"kind":"zombie_in_window","rows":[6,5,1],"col":6,
             "window":[10,75],"min_hp":500,"zombie":"任意"}},
  "levels": [[{{"op":"小喷菇"}}], [{{"op":"花盆"}}], [{{"op":"窝瓜"}}]]}}
```
`levels` 是兜底层：哪一层全部落地就停。`event.kind` 只能填：{events}

## 自然语言 → JSON（给 AI 用）

> 「w5：核好、樱桃辣椒都好的话先点核到 5-8；否则樱桃辣椒一起打；都不行就点存冰」
```json
{{"w":5,"sets":[
  {{"when":{{"kind":"all","of":[{{"kind":"card_ready","card":"毁灭菇"}},
      {{"kind":"card_ready","card":"樱桃"}},{{"kind":"card_ready","card":"辣椒"}}]}},
   "ops":[{{"op":"毁灭菇","aim":[5,8]}}]}},
  {{"when":{{"kind":"all","of":[{{"kind":"card_ready","card":"樱桃"}},
      {{"kind":"card_ready","card":"辣椒"}}]}},
   "ops":[{{"op":"樱桃","aim":[2,8]}},{{"op":"辣椒"}}]}},
  {{"when":{{"kind":"always"}},"ops":[{{"op":"咖啡豆","aim":[3,2]}}]}}]}}
```

> 「八炮 P4：每波一对炮打 8 列，波长 9 秒」
```json
{{"rhythm":{{"id":"P4","beats":["P","P","P","P"],
            "gaps":[9,9,9,9],"pair":"auto"}},
  "waves":[{{"w":2,"sets":[{{"when":{{"kind":"always"}},"ops":[
      {{"op":"玉米炮","aim":[3,8],"trig":{{"kind":"spawn"}}}},
      {{"op":"玉米炮","aim":[4,8],"trig":{{"kind":"spawn"}}}}]}}]}}]}}
```
（`pair:"short"` 时写一个 P 就会自动变成两门；上面是"自己写两块"的等价写法）

## 这个模型里"操作"只有两种

1. **P** —— `玉米炮`：不指定哪一门炮，只看每门炮各自的 3475cs 装填；
   爆炸 R=115 / 1800 **即刻生效**，落点可带一位小数。
2. **种植物（卡片）** —— 其余所有 op 都是"在某格种下某种植物"。
   种的瞬间就是触发（"种植即触发"的植物——樱桃 / 辣椒 / 窝瓜 / 核 —— 不额外算种植-生效时延）。

所以旧版的「窝瓜压车」这种**特技操作已经取消**：它就是
`窝瓜` + `aim:[5,9]` + 一个「5 路冰车距 5-9 还有 N px」的触发器。
"""

_SPEC_SPAWN_MECH = """# TrackCheck · 刷怪（刷新）机制说明

> 依据 `docs/知识库/02-核心-僵尸刷新机制.md`（R0/R1/R2/R3 四条基本规则，
> 来源：贴吧 5194693832、维基《生存无尽入门》六(四)、新旧读本）。
> **引擎按这个机制算，不套"运算量定律"** —— 运算量只是这套机制在长期实践里的经验总结。

## 四条规则

| 编号 | 规则 | 数值 |
|---|---|---|
| **R0** | 进场后固定刷第 1 波 | **6.0s** |
| **R0a** | w9/w19：本波僵尸全灭**或拖延 45s** → 红字 → **7.2s** 后刷下一波 | 45s / 7.2s |
| **R0b** | w20：全灭**或拖延 49s** → 白字 → **5s** 后结束 | 49s / 5s |
| **R1** | 任意两波间隔**绝不少于 6s** | 6.0s |
| **R2** | 本波剩余血量 / 本波总血量 < **随机阈值** → 激活刷新，**2s** 后刷出下一波 | 阈值 0.5~0.67（该波刷新瞬间就固定） |
| **R3** | 每波额外 roll 一个 **25~31s** 的强制刷新时间，到点必刷 | 25~31s |

所以实际波长由「**血量掉到阈值的那一刻**」和「R1 下限 / R3 上限」共同决定：

```
波长 = clamp( R1 6s , 血量跌破阈值 + 2s , R3 25~31s )
```

## 这对"什么时候开炮"意味着什么

- **炮不是"打了必刷"**，而是"把血打到阈值才刷"。
  一对炮（2 门）通常打不到阈值 → 这一波会靠 IO 继续磨，直到跌破阈值。
- 想让波长稳定在 9s，就要让**血量在 ~7s 掉到阈值**（+2s 真空 = 9s）。
  也就是说：**开炮时机要按"这一波的怪走到哪、还有多少血"手算**，没有捷径。
- 早期波（血少）一对炮就能打过阈值 → 波长会明显短于 9s；这是机制本身，不是 bug。

## 阵解里怎么表达"手算的时机"

| 触发器 | 用法 |
|---|---|
| `time`（波内时间） | 本波刷新后第 N cs 生效 |
| `since`（距上次某积木生效后） | **跨波锚点**：上一次「玉米炮」生效后 N cs 再开 —— 把 9s 节奏直接写出来 |
| `dist`（距离） | 某类僵尸离某格还有多少 px |
| `card`（卡片 CD） | 某张卡转好后 N cs |

例：P4 的 9s 一对炮 ——

```json
{"op":"玉米炮","aim":[2,8],"trig":{"kind":"since","op":"玉米炮","at":8800}}
```

（`at` 用 8800 而不是 9000：R2 激活后还有 2s 刷新真空，实际波长 ≈ 8.8 + 0.2
——真要 9s 就按实测微调。）
"""


_SPEC_SPAWN = """# TrackCheck 出怪列表 JSON 格式

```json
{"app":"trackcheck-spawn",
 "jobs":[{"name":"慢速关（预设）","kinds":["普通","路障","橄榄"],"seeds":5}]}
```

- `jobs[]`：一组要模拟的出怪
- `kinds`：允许出现的僵尸种类（中文名，见沙盘页的勾选项）
- `seeds`：跑几局（1~30）
- 只给 `{"jobs":[...]}` 也行，直接给数组也行
"""

_SPEC_CONFIG = """# TrackCheck 全场配置 JSON 格式

```json
{"format":"trackcheck-config/1",
 "spawns":[{"name":"慢速关","kinds":["普通","路障"],"seeds":3,"planId":"p1"}],
 "plans":[{"id":"p1","name":"电波钟无炮","plan":{ ... trackcheck-plan/3 ... }}]}
```

- `spawns`：出怪沙盘里的列表；`planId` 指向 `plans[].id`（空 = 用内置判定轨道）
- `plans`：阵解编辑里的多套阵解；`plan` 字段就是完整的阵解 JSON
- 导入时先建阵解，再把出怪按 `planId` 绑回去
"""


if __name__ == '__main__':
    p = default_dianbozhong()
    print('deck:', p['deck'])
    print('validate:', validate(p) or 'ok')
    print('parse N|AA\'|I|I ->', parse_track("N|AA'|I|I"))
    q, n = quick_layout(p, "N|AA'|I|I")
    print('quick_layout filled', n, 'regular waves')



