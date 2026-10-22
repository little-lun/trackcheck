# -*- coding: utf-8 -*-
"""
plan.py —— **阵解栏**的数据模型：可编辑的阵解 / 编译成引擎能跑的东西 / 校验

这一层把 PE.电波钟无炮 那套"写在 Python 里的判定式轨道"翻译成**可编辑的数据**：

    阵解
     ├ 节奏   C 系 C4io：N | AA' | I | I        ← 未来换系/换拍只动这里
     ├ 表层（轨道）  每波一行；行内 = 若干"候选"（兜底链），候选里是"积木"序列
     │    · 行首积木 = 刷怪即刻（或很短延时）生效
     │    · 后面的积木要挂**触发器**：时间 / 卡片 CD / 距离 / 状态，可循环
     └ 救场层  事件 → 有序的兜底层，每层若执行失败就退到下一层

积木（block）长得像这样：

    {"op": "核", "aim": [2, 9], "trig": {"kind": "spawn"}}
    {"op": "樱桃", "aim": [2, 8], "trig": {"kind": "time", "at": 250}}
    {"op": "窝瓜", "trig": {"kind": "dist", "zombie": "巨人",
                            "ref": {"kind": "cell", "row": 6, "col": 6},
                            "axis": "x", "cmp": "<=", "value": 160}}

候选（set）长得像这样 —— `when` 为假就整组跳过，试下一组（就是 if/elif/else）：

    {"when": {"kind": "card_ready", "card": "核"}, "ops": [ ... ]}
    {"when": {"kind": "always"},                  "ops": [ ... ]}

编译产物仍然是引擎认识的那个 `track(w, ctx) -> [积木]`（见 engine._norm_act），
所以**内置判定轨道一条没改**，两边可以同场对比。
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.trackcheck import data as D                    # noqa: E402
from tools.trackcheck import config_dianbozhong as CFG   # noqa: E402

FORMAT = 'trackcheck-plan/1'

# ------------------------------------------------------------------ 目录（给 UI 用）
# need_aim: 需要落点；aim_kind: cell=一个格子 / row=整行（或 None=自动）/ none=不需要
OPS = [
    # 灰烬
    dict(name='核',   group='灰烬', need_aim=True,  aim_kind='cell',
         note='毁灭菇，圆形 R=250（含纵向 30px 偏移）'),
    dict(name='模仿核', group='灰烬', need_aim=True, aim_kind='cell',
         note='模仿者核，效果同核，CD 独立'),
    dict(name='樱桃', group='灰烬', need_aim=True,  aim_kind='cell',
         note='R=115；不填落点则按 slots.cherry 走'),
    dict(name='辣椒', group='灰烬', need_aim=False, aim_kind='row',
         note='整行 1800；不填则自动挑最密的一行'),
    # 冰
    dict(name='冰',     group='冰', need_aim=False, aim_kind='none', note='冰卡：全场冰冻'),
    dict(name='模仿冰', group='冰', need_aim=False, aim_kind='none', note='模仿冰卡'),
    dict(name='存冰',   group='冰', need_aim=False, aim_kind='none',
         note='点阵上预置的存冰（不占卡 CD、不花钱）'),
    dict(name='种冰',   group='冰', need_aim=False, aim_kind='none', note='用冰卡补一格存冰'),
    dict(name='种冰2',  group='冰', need_aim=False, aim_kind='none', note='用模仿冰补一格存冰'),
    dict(name='种临时冰', group='冰', need_aim=False, aim_kind='none',
         note='前场 2-7 / 5-7 临时存冰（w1 固定动作）'),
    # 结构 / 救场
    dict(name='种大喷', group='结构', need_aim=False, aim_kind='none', note='长间隔补结构大喷'),
    dict(name='窝瓜压车', group='救场', need_aim=False, aim_kind='none',
         note='w10 固定：压 5-9 的冰车、保核坑'),
    dict(name='窝瓜',   group='救场', need_aim=False, aim_kind='none', note='自动挑最危险的一路'),
    dict(name='垫材',   group='救场', need_aim=False, aim_kind='none', note='小喷菇垫材'),
    dict(name='垫材2',  group='救场', need_aim=False, aim_kind='none', note='花盆垫材'),
]

OP_NAMES = [o['name'] for o in OPS]
OP_BY_NAME = {o['name']: o for o in OPS}

# 触发器目录
TRIGGERS = [
    dict(kind='spawn', label='刷怪即刻',  params=[]),
    dict(kind='time',  label='波内时间',  params=['at']),
    dict(kind='after', label='上一块之后', params=['at']),
    dict(kind='card',  label='卡片 CD 转好', params=['name', 'offset']),
    dict(kind='dist',  label='距离',      params=['zombie', 'ref', 'axis', 'cmp', 'value']),
    dict(kind='state', label='场况',      params=['what', 'cmp', 'value', 'row']),
    dict(kind='all',   label='全部满足',  params=['of']),
    dict(kind='any',   label='任一满足',  params=['of']),
    dict(kind='not',   label='取反',      params=['of']),
]

# 候选条件（和触发器同构，只是"问一次"而不是"等"）
GATES = TRIGGERS + [
    dict(kind='card_ready',        label='卡片已转好', params=['card', 'offset']),
    dict(kind='card_ready_within', label='卡片 N 波内转好', params=['card', 'waves']),
    dict(kind='ice_stock',         label='存冰数',     params=['cmp', 'value']),
    dict(kind='kernel_slack',      label='核坑余量',   params=['cmp', 'value']),
    # ★ 回看历史：前面某波的某个候选（或某个动作）到底发生了没有
    dict(kind='prev',              label='之前某波用了…',
         params=['back', 'target', 'set', 'op', 'negate']),
    dict(kind='always',            label='总是',       params=[]),
]

ZOMBIE_FILTERS = ['任意', '巨人', '冰车', '橄榄', '铁桶', '小丑', '撑杆', '海豚', '潜水']

RHYTHM_SYSTEMS = [
    dict(system='C', label='C 系（灰烬 + 冰）', beats=['N', "AA'", 'I', 'I'],
         presets=[dict(name='C4io', beats=['N', "AA'", 'I', 'I']),
                  dict(name='C4u', beats=['N', "AA'", 'I', 'I']),
                  dict(name='C6u', beats=['N', "AA'", 'N', "AA'", 'I', 'I'])]),
    dict(system='P', label='P 系（炮，预留）', beats=[], presets=[]),
    dict(system='S', label='S 系（无炮，预留）', beats=[], presets=[]),
    dict(system='自定义', label='自定义', beats=[], presets=[]),
]

WAVES = 20
ROLE_OF = {**{w: '起手' for w in (1, 2, 11, 12)},
           **{w: '旗波' for w in (10, 20)},
           **{w: '收尾' for w in (9, 19)}}


def role_of(w):
    return ROLE_OF.get(w, '常规')


# ------------------------------------------------------------------ 编译
def _avg(ctx):
    return (ctx or {}).get('avg_gap') or 1250


def _cmp_ok(a, cmp_, b):
    return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b,
            '==': a == b, '!=': a != b}.get(cmp_ or '>=', False)


def kernel_slack(w, avg_cs):
    """
    核坑余量（cs）：离最近的**固定核波**（w11 / 下个 2F 的 w1）还有多少余量。
    和 config_dianbozhong._kernel_slack 同一口径（见那边的注释）。
    """
    nxt = 11 if w < 11 else 21
    return (nxt - w) * (avg_cs or 1250) - 1500


def gate_ok(gate, ctx, w=None, hist=None):
    """候选条件求值。ctx = 引擎传进来的 {t, card_ready, avg_gap, ice_stock, ops_by_wave}"""
    if not gate:
        return True
    k = gate.get('kind')
    ctx = ctx or {}
    now = ctx.get('t', 0)
    ready = ctx.get('card_ready') or {}
    if k == 'always':
        return True
    if k in ('card_ready', 'card'):
        name = gate.get('card') or gate.get('name')
        return ready.get(name, 0) + int(gate.get('offset') or 0) <= now
    if k == 'card_ready_within':
        name = gate.get('card') or gate.get('name')
        return ready.get(name, 0) <= now + _avg(ctx) * float(gate.get('waves') or 0.9)
    if k == 'ice_stock':
        return _cmp_ok(ctx.get('ice_stock', D.MAX_ICE_STOCK), gate.get('cmp'), gate.get('value'))
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
    if k in ('time', 'after', 'dist', 'state', 'spawn'):
        return True          # 这些是"触发器"，放错位置就当作无条件
    return True


def _prev_wave(w, back):
    """往前数 back 波；越过 w1 就绕回上一个 2F 的末尾（20 波一轮）"""
    prev = int(w or 1) - int(back or 1)
    while prev < 1:
        prev += WAVES
    return prev


def prev_fired(gate, ctx, w=None, hist=None):
    """
    「之前某波的某个候选发生了」—— 候选引用历史用。

        {"kind": "prev", "back": 1, "target": "set", "set": 0}
            上一波是否由「候选 #1」胜出
        {"kind": "prev", "back": 1, "target": "set", "op": "辣椒"}
            上一波胜出的候选里是否含「辣椒」（拆 AA′ 就靠这条）
        {"kind": "prev", "back": 1, "target": "act", "op": "樱桃"}
            上一波里樱桃**是否真的打出去了**（卡 CD 卡住的不算）
        …再加 "negate": true 表示取反（"上一波只用了 A′、没打 A"）

    为什么 set 和 act 要分开：
      候选被选中 ≠ 里面的每块都真落地。若上一波选的是 `[樱桃, 辣椒]`，
      但樱桃当时在 CD，那实际只打了辣椒 —— 这时 target='act' 才看得见。
    """
    back = int(gate.get('back') or 1)
    target = gate.get('target') or 'set'
    pw = _prev_wave(w or ctx.get('wave') or 1, back)
    want_set = gate.get('set')
    op = gate.get('op')
    got, sel = [], None
    if target == 'act':
        got = list(((ctx or {}).get('ops_by_wave') or {}).get(pw) or [])
    else:
        h = (hist or {}).get(pw) or {}
        got = list(h.get('ops') or [])
        sel = h.get('set')
    ok = True
    if want_set is not None and want_set != '':
        ok = (sel == int(want_set)) if target != 'act' else ok
    if op:
        ok = ok and (op in got)
    if not want_set and not op and target == 'set':
        ok = sel is not None          # 只问"上一波有没有选出候选"
    return (not ok) if gate.get('negate') else ok


def _blocks_acts(blocks, ctx):
    """把一组的积木序列编译成 [{op, at, aim, trig}]（at = 相对本波开始的 cs）"""
    now = (ctx or {}).get('t', 0)
    ready = (ctx or {}).get('card_ready') or {}
    prev_at = 0
    out = []
    for b in blocks or []:
        op = b.get('op')
        trig = dict(b.get('trig') or {'kind': 'spawn'})
        at = int(b.get('at') or 0)
        kind = trig.get('kind')
        if kind == 'time':
            at = int(trig.get('at') or 0) + at
            trig = None
        elif kind == 'after':
            at = prev_at + int(trig.get('at') or 0)
            trig = None
        elif kind == 'card':
            name = trig.get('name') or op
            wait = max(0, int(ready.get(name, 0)) - now) + int(trig.get('offset') or 0)
            at = wait + at
            trig = dict(trig)          # 保留：万一别处又抢了这张卡，就继续等
            trig['kind'] = 'card'
            trig['name'] = name
        elif kind in ('spawn', None):
            trig = None
        if b.get('repeat'):
            trig = dict(trig or {'kind': 'spawn'})
            trig['repeat'] = b['repeat']
        out.append(dict(op=op, at=at, aim=b.get('aim'),
                        trig=(trig or None)))
        prev_at = at
    return out


def _wave_acts(row, ctx, hist=None):
    """
    一行的候选链：第一个 `when` 成立的候选胜出（= if / elif / else）。

    ★ `hist` 记「哪一波由哪个候选胜出、含哪些积木」，供后面的波用
      `{"kind": "prev", ...}` 回看 —— 拆开 AA′ 这类写法就靠它。
    """
    if not row:
        return []
    w = int(row.get('w') or 0)
    c = {**(ctx or {}), 'wave': w}
    for i, st in enumerate(row.get('sets') or []):
        if gate_ok(st.get('when'), c, w, hist):
            acts = _blocks_acts(st.get('ops'), ctx)
            if hist is not None:
                hist[w] = dict(set=i, ops=[a['op'] for a in acts],
                               when=st.get('when'))
            return acts
    if hist is not None:
        hist[w] = dict(set=None, ops=[])
    return []


def compile_plan(plan):
    """
    → (track_fn, rescue_tick)

    track_fn(w, ctx)       给引擎：返回积木列表（引擎自己 _norm_act）
    rescue_tick(sim)       给引擎：每 tick 调一次，按规则跑救场层

    ★ hist 是**这份阵解自己的**历史（每次 compile 一份），w1 时清空 ——
      不放进 CFG 的全局量里，避免两次运行互相污染。
    """
    rows = {int(r['w']): r for r in (plan.get('waves') or [])}
    rules = plan.get('rescue') or []
    hist = {}

    def track(w, ctx):
        if int(w or 0) <= 1:
            hist.clear()
        return _wave_acts(rows.get(w), ctx, hist)

    def rescue_tick(sim):
        return tick_rescue(sim, rules)

    return track, rescue_tick


# ------------------------------------------------------------------ 救场层
def _event_fired(sim, ev):
    """
    救场事件求值。事件都是"看一眼场上"的类型：

        {"kind": "always"}
        {"kind": "zombie_in_window", "rows": [6,5,1], "col": 6,
         "window": [10, 75], "min_hp": 500, "zombie": "任意"}
        {"kind": "heavy_near_core", "rows": [6,5,2,1], "cells": 3}
        {"kind": "bare_core_threat"}            ← 裸 CORE 要被砸了
        {"kind": "ice_stock", "cmp": "<=", "value": 1}
        {"kind": "wave", "from": 1, "to": 9}
    """
    k = (ev or {}).get('kind')
    if k in (None, 'always'):
        return True
    if k == 'wave':
        return int(ev.get('from') or 1) <= sim.cur_wave <= int(ev.get('to') or WAVES)
    if k == 'ice_stock':
        return _cmp_ok(sim.ice_stock, ev.get('cmp'), ev.get('value'))
    if k == 'zombie_in_window':
        rows = ev.get('rows') or [6, 5, 1]
        col = int(ev.get('col') or 6)
        lo, hi = ev.get('window') or (10, 75)
        cx = D.cell_x(col)
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
    if k == 'bare_core_threat':
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
    return False


def _run_rescue_op(sim, op, aim=None):
    """执行一个救场积木；返回 True/False（能不能落地）"""
    wave = max(1, sim.cur_wave)
    if op in ('垫材', '垫材2'):
        rows = (aim or {}).get('rows') if isinstance(aim, dict) else None
        return sim.try_stall(rows)
    if op == '窝瓜':
        rows = (aim or {}).get('rows') if isinstance(aim, dict) else None
        return sim.try_wogua(rows)
    if op == '救急冰':
        return bool(sim._rescue_ice_emergency())
    if op in D.CARDS:
        before = len(sim.actions)
        sim.do_action(dict(name=op, aim=None, wave=wave, kind='act'))
        return len(sim.actions) > before and sim.actions[-1].get('ok', False)
    return False


def tick_rescue(sim, rules):
    """
    救场层：**每 tick** 走一遍规则表。

    ★ 兜底的语义是"这一层没落地就试下一层"，不是"下一 tick 再试" ——
      层次顺序 = 玩家的临场优先级（垫材 → 垫材2 → 窝瓜 → 点冰 → 救急冰）。
    """
    if not sim.rescue:
        return
    cd = getattr(sim, '_plan_rescue_cd', None)
    if cd is None:
        cd = sim._plan_rescue_cd = {}
    for rule in rules:
        rid = rule.get('id') or rule.get('name') or 'rule'
        if cd.get(rid, -1) > sim.t:
            continue
        if not _event_fired(sim, rule.get('event')):
            continue
        levels = rule.get('levels') or []
        done = False
        for lv in levels:
            ops = lv.get('ops') if isinstance(lv, dict) else lv
            ok = True
            for b in (ops or []):
                if not _run_rescue_op(sim, b.get('op'), b.get('aim')):
                    ok = False
                    break
            if ok:
                done = True
                break
        if done:
            cd[rid] = sim.t + int(rule.get('cooldown') or 30)


# ------------------------------------------------------------------ 校验
def validate(plan):
    """静态体检：返回 [{lv: error|warn, where, msg}]"""
    out = []

    def bad(where, msg):
        out.append(dict(lv='error', where=where, msg=msg))

    def warn(where, msg):
        out.append(dict(lv='warn', where=where, msg=msg))

    def walk_gate(where, g, w=None):
        """查一遍条件树：prev 回看的合法性、未知动作名"""
        if not isinstance(g, dict):
            return
        k = g.get('kind')
        if k == 'prev':
            back = int(g.get('back') or 1)
            if back < 1:
                bad(where, 'prev 回看波数必须 ≥ 1')
            elif back > WAVES - 1:
                bad(where, 'prev 回看 %d 波 —— 一轮只有 %d 波，永远看不到'
                    % (back, WAVES))
            elif w is not None and back >= int(w or 1):
                warn(where, '第 %s 波回看 %d 波会绕到上一轮的 w%d（本局没有那么多历史）'
                     % (w, back, _prev_wave(w or 1, back)))
            op = g.get('op')
            if op and op not in OP_BY_NAME:
                bad(where, 'prev 里写的动作 %r 不存在（应该是积木名）' % op)
        elif k in ('all', 'any', 'not'):
            for sub in (g.get('of') or []):
                walk_gate(where, sub, w)

    rows = plan.get('waves') or []
    if len(rows) != WAVES:
        warn('整体', '波数是 %d（内置轨道按 %d 波算；缺的行不会跑任何积木）'
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
            seen_cards = set()
            for b in st.get('ops') or []:
                op = b.get('op')
                if op not in OP_BY_NAME:
                    bad(sw, '未知积木 %r' % op)
                    continue
                spec = OP_BY_NAME[op]
                if spec['need_aim'] and not b.get('aim'):
                    warn(sw, '%s 没填落点（会用默认策略）' % op)
                if op in D.CARDS:
                    if op in seen_cards:
                        bad(sw, '同一候选里 %s 用了两次 —— 第二块必然卡在 CD' % op)
                    seen_cards.add(op)
                trig = b.get('trig') or {}
                if trig.get('kind') and trig['kind'] not in [t['kind'] for t in TRIGGERS]:
                    bad(sw, '未知触发器 %r' % trig['kind'])
        if not any((st.get('when') or {}).get('kind') == 'always'
                   for st in row.get('sets') or []):
            warn(where, '候选链没有"总是"兜底 —— 条件全不成立时这一波什么都不做')
    for rule in plan.get('rescue') or []:
        rid = rule.get('id') or '?'
        if not rule.get('levels'):
            bad('救场 %s' % rid, '没有任何兜底层')
        for i, lv in enumerate(rule.get('levels') or []):
            ops = lv.get('ops') if isinstance(lv, dict) else lv
            for b in ops or []:
                if b.get('op') not in OP_BY_NAME and b.get('op') != '救急冰':
                    bad('救场 %s 第%d层' % (rid, i + 1), '未知积木 %r' % b.get('op'))
    return out


# ------------------------------------------------------------------ 序列化
def norm(plan):
    """补齐缺省字段，保证前后端拿到的形状一致"""
    p = json.loads(json.dumps(plan or {}, ensure_ascii=False))
    p.setdefault('format', FORMAT)
    p.setdefault('name', '未命名阵解')
    p.setdefault('rhythm', dict(system='C', name='C4io', beats=['N', "AA'", 'I', 'I']))
    p.setdefault('waves', [])
    p.setdefault('rescue', [])
    p.setdefault('slots', {})
    p.setdefault('params', {})
    for row in p['waves']:
        row.setdefault('role', role_of(int(row.get('w') or 0)))
        for st in row.get('sets') or []:
            st.setdefault('when', {'kind': 'always'})
            st.setdefault('ops', [])
            for b in st['ops']:
                b.setdefault('trig', {'kind': 'spawn'})
    return p


def to_json(plan):
    return json.dumps(norm(plan), ensure_ascii=False, indent=2)


def from_json(text):
    return norm(json.loads(text))


# ------------------------------------------------------------------ 存放
PLANS_DIR = os.path.join(ROOT, 'tools', 'trackcheck', 'plans')


def _slug(name):
    s = ''.join(ch for ch in str(name or 'untitled')
                if ch not in '\\/:*?"<>|').strip() or 'untitled'
    return s[:60]


def save_file(plan_dict, name=None):
    """存到 tools/trackcheck/plans/<名字>.json"""
    p = norm(plan_dict)
    if name:
        p['name'] = name
    os.makedirs(PLANS_DIR, exist_ok=True)
    path = os.path.join(PLANS_DIR, _slug(p.get('name')) + '.json')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(to_json(p))
    return dict(ok=True, path=path)


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


# ------------------------------------------------------------------ 内置阵解
def _b(op, aim=None, trig=None, repeat=None):
    d = dict(op=op, aim=aim, trig=trig or {'kind': 'spawn'})
    if repeat:
        d['repeat'] = repeat
    return d


def _set(when, *ops):
    return dict(when=when or {'kind': 'always'}, ops=list(ops))


N = {'kind': 'card_ready', 'card': '核'}
AA = {'kind': 'all', 'of': [{'kind': 'card_ready', 'card': '樱桃'},
                            {'kind': 'card_ready', 'card': '辣椒'}]}
ANY_ASH = {'kind': 'any', 'of': [{'kind': 'card_ready', 'card': '樱桃'},
                                 {'kind': 'card_ready', 'card': '辣椒'}]}
ICE1 = {'kind': 'ice_stock', 'cmp': '>=', 'value': 1}


def default_dianbozhong():
    """
    把 `config_dianbozhong.track()` 的判定式轨道**转写成积木**。

    ★ 这不是逐行等价的克隆：原版靠 `owe_aa / owe_chili / split` 这些跨波状态记忆，
      积木版把"下一波必须接上"这件事交给**下一波的那一行**自己写（看得到、改得动）。
      想跑原版就选"内置判定轨道"，想改就用这份当起点。
    """
    rows = []

    def row(w, sets, note=''):
        rows.append(dict(w=w, role=role_of(w), note=note, sets=sets))

    # ---- 起手
    row(1, [_set(N, _b('核', [2, 9]),
                 _b('种临时冰', trig={'kind': 'time', 'at': 0}),
                 _b('种临时冰', trig={'kind': 'time', 'at': 400})),
            _set(ICE1, _b('存冰')),
            _set(None, _b('种临时冰', trig={'kind': 'time', 'at': 0}))],
        'C4io 锚点：2-9 反应核 + 两个临时存冰')
    row(2, [_set(AA, _b('樱桃', [2, 8]), _b('辣椒')),
            _set(ANY_ASH, _b('樱桃', [2, 8])),
            _set(None, _b('存冰'))],
        'AA′：2-8 樱桃 + 5 路辣椒；缺一张就先拆开用')
    row(3, [_set(None, _b('存冰'))], '铺节奏，早冰控丑')
    row(4, [_set(ANY_ASH, _b('樱桃', [2, 8])),
            _set(None, _b('存冰'))], '补 AA′ 的欠账')

    # ---- 常规波（两个 8 波段）
    for w in list(range(5, 9)) + list(range(13, 19)):
        row(w, [
            _set({'kind': 'all', 'of': [N, ANY_ASH, {'kind': 'kernel_slack'}]},
                 _b('核', [5, 8])),
            _set(AA, _b('樱桃', [2, 8]), _b('辣椒')),
            _set(ANY_ASH, _b('樱桃', [5, 8])),
            _set(ICE1, _b('存冰')),
            _set(None, _b('冰', trig={'kind': 'card', 'name': '冰'})),
        ], 'C4io：N → AA′ → I → I，按 CD + 坑位择一拍')

    # ---- 起手（第二轮 2F）
    row(11, [_set(N, _b('核', [5, 9])),
             _set(ICE1, _b('存冰')),
             _set(None, _b('存冰'))],
        '第二个锚点：5-9 反应核（半场开局）')
    row(12, [_set(AA, _b('樱桃', [2, 8]), _b('辣椒')),
             _set(ANY_ASH, _b('樱桃', [2, 8])),
             _set(None, _b('存冰'))],
        'AA′（半场开局）')

    # ---- 收尾
    for w in (9, 19):
        row(w, [_set(ANY_ASH, _b('樱桃', [2, 8]), _b('辣椒')),
                _set(ICE1, _b('存冰')),
                _set(None, _b('冰', trig={'kind': 'card', 'name': '冰'}))],
            '收尾波：照常控丑，但**不点核**（留给下一个旗波/锚点）')

    # ---- 旗波
    row(10, [_set(None, _b('存冰'),
                  _b('窝瓜压车', trig={'kind': 'time', 'at': 0})),
             _set({'kind': 'ice_stock', 'cmp': '<=', 'value': 0},
                  _b('冰', trig={'kind': 'card', 'name': '冰'}))],
        '旗波：冰杀蹦极 + w10 窝瓜压车保 5-9 核坑')
    row(20, [_set(None, _b('存冰')),
             _set({'kind': 'ice_stock', 'cmp': '<=', 'value': 0},
                  _b('冰', trig={'kind': 'card', 'name': '冰'}))],
        'w20：清账')

    rows.sort(key=lambda r: r['w'])

    return norm(dict(
        format=FORMAT,
        name='PE.电波钟无炮',
        note='C4io 判定式轨道的积木化版本（内置判定轨道仍可用，两者可同场对比）',
        rhythm=dict(system='C', name='C4io', beats=['N', "AA'", 'I', 'I'],
                    note='4 拍循环；N=核、A=樱桃、A′=辣椒、I=冻'),
        waves=rows,
        rescue=[
            dict(id='垫材', note='僵尸能打到 6 列就下；垫材→垫材2→窝瓜 三层兜底',
                 cooldown=10,
                 event=dict(kind='zombie_in_window', rows=[6, 5, 1], col=6,
                            window=[10, 75], min_hp=500, zombie='任意'),
                 levels=[[_b('垫材')], [_b('垫材2')], [_b('窝瓜')]]),
            dict(id='窝瓜强杀', note='重甲逼近 CORE 3 格内，垫材全 CD 也要拦',
                 cooldown=30,
                 event=dict(kind='heavy_near_core', rows=[6, 5, 2, 1], cells=3),
                 levels=[[_b('窝瓜')]]),
            dict(id='救急冰', note='裸 CORE 要被砸、且垫材/窝瓜都不可用',
                 cooldown=300,
                 event=dict(kind='bare_core_threat'),
                 levels=[[_b('救急冰')], [_b('存冰')], [_b('冰')]]),
        ],
        slots=dict(kernel=list(CFG.KERNEL_SLOTS), temp_ice=list(CFG.TEMP_ICE_SLOTS),
                   chili=list(CFG.CHILI_SLOT), cherry_row=CFG.CHERRY_ROW,
                   cherry_cols=list(CFG.CHERRY_COLS),
                   fast_fog=list(CFG.FAST_LUNGBU_SPOTS)),
        params=dict(skip_hp=CFG.SKIP_HP, stall_hp=CFG.STALL_HP,
                    tomato_x=CFG.TOMATO_X, tomato_hp=CFG.TOMATO_HP),
    ))


def builtin(name='PE.电波钟无炮'):
    return default_dianbozhong()


def example_split_aa():
    """
    示例：**把 C4io 的 AA′ 拆到两波**（`prev` 条件最典型的用法）

    标准 C4io 要求 A（樱桃）和 A′（辣椒）在同一波一起打出。实战里两张卡同时
    不在 CD 是运气问题，拆开更稳 —— 但拆开就必须记住"上一波用的到底是 A 还是 A′"：

        w5  候选1 核（核好 + 坑位够）
            候选2 辣椒（当 樱桃没好、辣椒好）      ← 这一波只用了 A′
            候选3 冰
        w6  候选1 樱桃（当 上一波**打了辣椒、没打樱桃**）  ← 把欠的 A 补上
            候选2 核（核好）
            候选3 冰

    第 3 个条件就是 `{"kind": "prev", "target": "act", ...}`：它问的是
    "上一波**真正打出去**的动作"，而不是"上一波选了哪个候选"。
    """
    p = default_dianbozhong()
    p['name'] = '示例 · C4io 拆开 AA′'
    p['note'] = ('AA′ 拆到两波：第 x 波只打 A′（辣椒），第 x+1 波用 prev 条件'
                 '判断上一波是不是只用了 A′，是就补 A（樱桃），否则走原来的节奏')

    groups = list(range(5, 9)) + list(range(13, 19))

    def split_sets():
        """这一波：有双卡就一起打 AA′；只有辣椒就先打 A′（欠下的 A 由下一波补）"""
        return [
            {'when': {'kind': 'all', 'of': [
                {'kind': 'card_ready', 'card': '核'},
                {'kind': 'card_ready', 'card': '樱桃'},
                {'kind': 'card_ready', 'card': '辣椒'}]},
             'ops': [_b('核', [5, 8])]},
            {'when': {'kind': 'card_ready', 'card': '辣椒'},
             'ops': [_b('辣椒')]},          # ← 这一波只用了 A′
            {'when': {'kind': 'card_ready', 'card': '樱桃'},
             'ops': [_b('樱桃', [2, 8])]},
            {'when': {'kind': 'always'}, 'ops': [_b('存冰')]},
        ]

    def makeup_set():
        """下一波：上一波只打了 A′（= 打了辣椒、没打樱桃）→ 把 A 补上"""
        return {'when': {'kind': 'all', 'of': [
            {'kind': 'prev', 'back': 1, 'target': 'act', 'op': '辣椒'},
            {'kind': 'prev', 'back': 1, 'target': 'act', 'op': '樱桃',
             'negate': True}]},
            'ops': [_b('樱桃', [2, 8])]}

    for row in p['waves']:
        w = row['w']
        if w in groups:
            row['sets'] = split_sets()
            row['note'] = 'AA′ 拆开：双卡齐就一起打，否则先打 A′'
        elif (w - 1) in groups:
            row['sets'] = [makeup_set()] + list(row['sets'])
            row['note'] = '上一波若只用了 A′，这里补 A；否则按原节奏走'
    return norm(p)


def catalog():
    """给前端：可选积木 / 触发器 / 节奏 / 僵尸筛选项"""
    return dict(ops=OPS, triggers=TRIGGERS, gates=GATES,
                zombies=ZOMBIE_FILTERS, rhythms=RHYTHM_SYSTEMS, waves=WAVES,
                roles={str(w): role_of(w) for w in range(1, WAVES + 1)})


if __name__ == '__main__':
    p = default_dianbozhong()
    print(json.dumps(p, ensure_ascii=False, indent=2)[:1200])
    print('validate →', validate(p))
