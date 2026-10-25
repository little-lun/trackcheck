# -*- coding: utf-8 -*-
"""
lookahead.py —— **预演-回溯**（bounded search + rollout）

用户 2026-10-23：
    "我们的模型基于计算，所以具有一定的预测能力，或者说是『预演-回溯』能力；
     如果可以估算最靠前的怪是否在破坏 core 之前被 io 打死，则可以不管，否则必须炸到。
     简化模拟工具一定要有部分『预演-回溯』能力（可以短暂的 DFS 或 BFS），
     就是说在轨道下一定可以找到极优解（就拿经典八炮来说，你可以在合理范围内
     （在固定行上滑动）搜索极优解使得即便是最靠前的僵尸被漏炸了也会被冰瓜或曾哥收掉）。
     广泛而言，所有用户没有定死的操作（除了落点滑动，还有救场、还有其它灵活的功能）
     都可以通过搜索得到极优解。"

所以这里提供三件东西：

  ① `dps_by_cell()`   这一路每一格"僵尸通过时吃多少 dps"（只用**场上活着的**植物）
  ② `io_eta()`        **前向推演**：这只僵尸会不会在吃到最靠前的 CORE 之前被自然输出打死？
                      返回 (会不会死, 还需多少 cs, 会吃到哪一格)
  ③ `best_aim()`      **有界搜索**：在"允许滑动的落点"里枚举候选爆心，
                      对每个候选做一次推演，取"总体收益最大"的那个解

★ 搜索规模刻意很小（候选 ≤ 40 个、每个候选一次推演），因为它要在每一发炮前跑一遍。
   这就是"短暂的 DFS"：不是把整局展开，而是"这个落点打下去，接下来这一路会怎样"。
"""
from tools.trackcheck import data as D

# 单个植物的"对该行某格"的持续 dps（不含溅射，溅射按 26/发 粗算为额外 26/interval）
def _plant_dps(spec):
    if spec.get('shoot'):
        sh = spec['shoot']
        n = (sh.get('front') or 1) + (sh.get('back') or 0)
        return (sh.get('dmg') or 0) * n / float(max(1, spec.get('interval') or 1)) * 100.0
    dmg = spec.get('dmg') or 0
    if not dmg:
        return 0.0
    hits = spec.get('hits') or 1
    return dmg * hits / float(max(1, spec.get('interval') or 1)) * 100.0


# ★ 2026-10-23：推演用的 dps **打 75 折**。
#   `dps_by_cell` 假设"每株植物 100% 时间都在打这只、从不换目标、自己也不会被吃"，
#   这在实战里做不到（多只僵尸分摊、植物被啃、冰瓜抛射有落点时间）。
#   打折不改变"能不能打死"的量级判断，但让"可以不管"这个结论变得**保守** ——
#   只有明显能打死的才不管，边缘情况一律按"必须炸/必须救"处理。
IO_DPS_HAIRCUT = 0.75

# ★ 2026-10-23：救场门控里"植物能撑多久"要打多少折。
#   `1.0` = 相信"僵尸啃完南瓜+植物才叫破坏 core"→ 门控过于宽松，
#   实测把经典八炮从 10/20 拉低到 8/20（推演说 1200cs 后死，实际这 1200cs 里
#   它已经把 1-5 玉米炮啃掉了）。所以救场门控退回到**更严格的语义**：
#   只有"在被摸到之前就死"才算不用管。
#   —— 用户原话就是"在**破坏 core 之前**被 io 打死"，这里按最保守的读法实现。
LA_EAT_TRUST = 0.0


def _covers(spec, prow, pcol, row, col):
    """这株植物能不能打到 (row, col) 这一格"""
    rows = spec.get('rows') or 1
    if rows < 6 and abs(prow - row) > rows // 2:
        return False
    rng = spec.get('rng')
    if rng is None:
        return True                      # 抛射 / 全场（香蒲、冰瓜、机枪）
    cx = D.cell_x(col)
    px = D.cell_x(pcol)
    return px + rng[0] <= cx <= px + rng[1]


def dps_by_cell(sim, row, slow=True):
    """这一路第 1~9 列，僵尸通过时受到的 dps。

    `slow=True` 时，把"能被冰系减速"算进去：本模型里减速覆盖率接近 100%
    （用户口径），所以按 `D.SLOW_ANIM` 折减僵尸速度，等价于 dps × (1/0.5)…
    这里不折减 dps，而是**交给 `io_eta` 用实际速度**去积分，避免重复计算。
    """
    out = {}
    for col in range(1, 10):
        tot = 0.0
        for (pr, pc), cell in sim.cells.items():
            name = cell.plant
            if not name or not getattr(cell, 'awake', True):
                continue
            spec = D.PLANTS.get(name)
            if not spec or not (spec.get('dmg') or spec.get('shoot')):
                continue
            if not _covers(spec, pr, pc, row, col):
                continue
            tot += _plant_dps(spec)
        out[col] = tot
    return out


def _base_speed(z):
    """这只僵尸**不被减速时**的速度（推演用的悲观速度）"""
    if getattr(z, 'phase', 'walk') == 'walk' and getattr(z, 'spd_alt', None):
        return z.spd_alt
    return getattr(z, 'spd', 0.0) or 0.0


# 推演里"IO 根本拦不住"的类型：
#   · 蹦极（从天上来，落地抓取是机制杀）
#   · 气球（飞越一切非对空植物）
#   · 冰车 / 投篮 —— 载具，**碾过即摧毁植物**，静态 dps 表对它无效
#     （除非本路有地刺/地刺王，见 `_has_spike`）
_IO_IMMUNE = {'蹦极', '气球'}


def _has_spike(sim, row):
    """本路有没有地刺类（载具的真对策：判定域重合 → 互相破坏）"""
    for col in range(1, 10):
        cell = sim.cells.get((row, col))
        if cell is not None and cell.plant:
            spec = D.PLANTS.get(cell.plant) or {}
            if spec.get('spike'):
                return True
    return False


def front_core_col(sim, row):
    """这一路最靠前的 CORE 植物在第几列（僵尸能吃到它）；没有返回 None"""
    best = None
    for col in range(1, 10):
        cell = sim.cells.get((row, col))
        if cell is None:
            continue
        nm = cell.plant
        if not nm:
            continue
        if nm in D.CORE_PLANTS or sim._is_core_cell((row, col)):
            best = col
    return best


def io_eta(sim, z, table=None):
    """**前向推演**：僵尸 z 会不会在被自然输出打死之前吃到本路最靠前的 CORE？

    返回 `(will_die, need_cs, reach_col)`：
      · will_die  True  = 路上就会死 → 这一只**可以不管**
      · need_cs   预计多少 cs 后死（不确定就给 None）
      · reach_col 它最多能推到第几列

    做法：从它现在的位置开始，一格一格往左走，用 `_speed_of`（已含减速）算
    每格用时，用该格 dps 扣血；血扣完就判死。不做逐 cs 模拟 —— 这是"短暂的推演"，
    目的只是"会不会死"，不必精确到 cs。

    ★★ 2026-10-24 用户报的"冰车没吃到 P/N"的真因就在这里：
      **载具（冰车 / 投篮车）碾过即摧毁植物**，所以"后面那些格子还有 dps"是假的 ——
      `dps_by_cell` 是静态表，它假设植物永远活着。于是推演得出"IO 会把它收掉"，
      `best_aim` 的硬约束就放它过关（`must=False`），炮去打人群了，车一路碾进来。
      → 现在载具直接判"IO 拦不住"（除非本路有地刺/地刺王，那才是 IO 的真对策）。
    """
    if z is None or not z.alive:
        return True, 0, None
    if z.kind in _IO_IMMUNE or (z.kind in ('冰车', '投篮') and not _has_spike(sim, z.row)):
        return False, None, None
    core_col = front_core_col(sim, z.row)
    if core_col is None:
        return False, None, None
    table = table if table is not None else dps_by_cell(sim, z.row)
    hp = z.hp
    x = z.x
    elapsed = 0.0
    # 走得比 core 列的"啃食点"再靠左一点才算吃到
    stop_x = D.cell_x(core_col) + D.EAT_OFFSET
    # ★ 2026-10-23：推演**按未减速的速度**算（悲观）。
    #   曾经直接用 `_speed_of`：那只僵尸此刻被冰冻着，就按"半速"推演出
    #   "1200cs 后死"，可 400cs 后冰化了、它按全速走完剩下的路，把 1-5 玉米炮啃了。
    #   实战里减速不可能一直续，推演必须按最坏情况（不减速）走。
    v = max(1e-6, sim._speed_of(z), _base_speed(z))
    while x > stop_x:
        col = max(1, min(9, int(round((x - 40) / 80.0)) + 1))
        nxt_x = max(stop_x, D.cell_x(col) - 40.0)
        if nxt_x >= x:                       # 已经在这一格的最左端
            nxt_x = max(stop_x, x - 40.0)
        span = x - nxt_x
        if span <= 0:
            break
        dt = span / v
        hp -= table.get(col, 0.0) * dt / 100.0 * IO_DPS_HAIRCUT
        elapsed += dt
        x = nxt_x
        if hp <= 0:
            return True, elapsed, col
    return False, None, max(1, min(9, int(round((x - 40) / 80.0)) + 1))


def _covered(sim, z, cx, cy, radius):
    """圆（cx,cy,R）与这一只的受击框相交？"""
    zl, zr = sim._dbox(z)
    zy = sim.zy(z.row)
    nx = zl if cx < zl else (zr if cx > zr else cx)
    ny = zy if cy < zy else (zy + D.DEF_HEIGHT if cy > zy + D.DEF_HEIGHT else cy)
    return (nx - cx) ** 2 + (ny - cy) ** 2 <= radius * radius


def best_aim(sim, row, radius, dy, dmg, cols=None, integer=False, tables=None):
    """**有界搜索**：在候选爆心里挑"总体收益最大"的那个。

    评分（对这个落点做一次推演）：
      · 打中：每只 +1（冰车 / 投篮车 / 巨人 **+3**），按"能打掉的血量"加权
      · 打死：额外 +2（硬目标 +5）—— 打死才是真的解决
      · **漏炸惩罚**：被这一炮纵向覆盖到的每一路，若"最靠前那只"没被打中，
        就用 `io_eta` 推演一次：**它能在吃到 CORE 之前被自然输出打死吗？**
        能 → 不惩罚（可以不管，用户 2026-10-23 口径）；不能 → **−8**（必须炸到）

    候选列 = 由"场上每只可伤僵尸反解出的列" + 0.5 步长的均匀网格，
    去重后**最多 40 个**（这就是"短暂的搜索"）。

    `integer=True` 返回整列（樱桃 / 辣椒这类要种在格子里）。
    """
    rows = sim._boom_rows(row, radius, dy)
    # ★ 2026-10-24：地下的矿工既打不到也不该被瞄（`_targetable`）
    zs = [z for r in rows for z in sim.by_row.get(r, ())
          if z.alive and z.hp > 0 and sim._dbox(z)[0] <= D.DMG_LINE
          and sim._targetable(z)]
    if not zs:
        # ★ 2026-10-25：**前瞻瞄准**。本波刚刷出来的僵尸还在 800 附近、
        #   没进可伤区，旧实现在这里返回 None → 调用方只好"对着空气炸 8.0 列"，
        #   白搭一发 3475cs 装填（PE.二十四炮 w1 的海豚就是这么漏过去的）。
        #   改成**按"能看见的最靠前的僵尸"落点**：爆炸判定域该盖不到还是盖不到，
        #   但爆心至少贴在僵尸身上，而不是钉死在 8.0。
        zs = [z for r in rows for z in sim.by_row.get(r, ())
              if z.alive and z.hp > 0 and sim._targetable(z)]
    if not zs:
        return None
    base = D.cell_x(1)
    cand = set()

    def _col_of(z):
        zl, zr = sim._dbox(z)
        return max(1.0, min(9.0, ((zr + radius - 1.0) - base) / 80.0 + 1.0))

    for z in zs:
        c0 = _col_of(z)
        for d in (-0.5, 0.0, 0.5):
            v = round((c0 + d) * 2) / 2.0
            if 1.0 <= v <= 9.0:
                cand.add(v)
    if cols:
        for c in cols:
            cand.add(float(c))
    for i in range(1, 18):
        c = round(1.0 + i * 0.5, 1)
        if c <= 9.0:
            cand.add(c)
    # ★ 2026-10-25：**落点没有射程限制**（玉米炮点哪打哪），候选就是整条草坪。
    cand = sorted(cand)
    if len(cand) > 40:
        # ★ 2026-10-25：原来直接 `[:40]` = 只留最左边 40 个（有偏）。
        #   改成**均匀抽稀**，整段射程都能被搜到。
        step = len(cand) / 40.0
        cand = [cand[min(len(cand) - 1, int(i * step))] for i in range(40)]

    # 每路"最靠前那只"是否必须炸（IO 能不能救）—— 每路只推演一次，缓存
    must = {}
    front = {}
    for r in rows:
        f = None
        for z in sim.by_row.get(r, ()):
            if not z.alive or z.hp <= 0:
                continue
            if sim._dbox(z)[0] > D.DMG_LINE:
                continue
            if not sim._targetable(z):
                continue
            if f is None or z.x < f.x:
                f = z
        front[r] = f
        if f is None:
            must[r] = False
            continue
        tabs = (tables or {}).get(r)
        will_die, _cs, _rc = io_eta(sim, f, tabs)
        must[r] = not will_die

    def _must_weight(r):
        """这条"必须炸"的前锋有多急 —— 越靠里、越是载具/巨人，权重越大。

        ★ 2026-10-24：一门炮只能挑一个列，`n_must` 只数个数会让
          "冰车已经推到 3 列"和"杂兵还在 8 列"同权 → 炮去打人群、车碾进来。
        """
        f = front.get(r)
        if f is None:
            return 0.0
        w = 3.0 if (f.kind in ('冰车', '投篮') or f.giant) else 1.0
        if f.x < 400:
            w *= 3.0                      # 已经推到 5 列以内 = 马上就要啃/碾
        elif f.x < 560:
            w *= 1.5
        return w


    best, best_key = None, None
    for c in cand:
        cx = base + (c - 1.0) * D.CELL_W
        cy = sim._aim_py(row, c) + dy
        # 硬约束：被这一炮纵向覆盖到的每一路，若"最靠前那只"必须炸（IO 救不了），
        # 就必须被打中 —— 否则这个候选**不可行**（用户 2026-10-23 口径）。
        feasible = True
        n_must = 0.0               # 这一炮盖住的"必须炸的前锋"有多急（加权）
        for r in rows:
            f = front.get(r)
            if f is None or not must.get(r):
                continue
            if _covered(sim, f, cx, cy, radius):
                n_must += _must_weight(r)
            else:
                feasible = False
        kills = 0.0
        dmgv = 0.0
        for z in zs:
            if not _covered(sim, z, cx, cy, radius):
                continue
            hard = (z.kind in ('冰车', '投篮') or z.giant)
            w = 3.0 if hard else 1.0
            dmgv += w * min(dmg, max(0.0, z.hp)) / float(dmg)
            if z.hp <= dmg:
                kills += w
        # 字典序：先"可行"，再"盖住多少个必须炸的前锋"，再"打死多少"，
        # 再"打掉多少血"，最后"别离第 8 列太远"。
        # ★ 2026-10-24：加了 `n_must` 这一级 —— 一门炮盖不住两个相隔很远的点时
        #   （人群在 8 列、冰车已经推到 5 列），旧实现会整体判"都不可行"然后
        #   按 kills 选人群，于是**冰车被静默丢掉**（慢速关 6-4 就是这么被碾的）。
        #   现在"必须炸的前锋优先"，宁可少杀几只杂兵。
        key = (1 if feasible else 0, n_must, round(kills, 3),
               round(dmgv, 3), -abs(c - 8.0))
        if best_key is None or key > best_key:
            best, best_key = c, key
    if best is None:
        return None
    return float(round(best)) if integer else round(best * 10) / 10.0


def io_will_hold(sim, z, tables=None):
    """救场用的极简版：这只僵尸会被自然输出收掉吗？（可以不管）"""
    will_die, _cs, _rc = io_eta(sim, z, (tables or {}).get(z.row)
                                if tables else None)
    return bool(will_die)
