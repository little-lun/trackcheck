# -*- coding: utf-8 -*-
"""
engine.py —— 轨道验证器的模拟内核  v0.7

v0.7 修的五处「模型错误」（不是简化，是错）：
  ① **冰瓜没有减速**          → 整个游戏里唯一的常驻减速来源没了，僵尸全速推进
  ② **冰瓜只打单体、无溅射**   → 单发 80 被当成全部输出，实际 80 + 3×3 溅射 40
  ③ **一波 50 只同一帧全出**   → 真实是"按出怪列表顺序依次生成"，聚散程度差一个数量级
  ④ **阵外格子是 None**       → 核坑/灰烬位（5-8、2-7…）根本不存在，核永远"无处可点"
  ⑤ **非步行僵尸当步行者跑**   → 蹦极/气球/投篮/矿工/海豚被当成沿地面走的肉，直接"进家"

v0.7 新增的两层结构：
  · **救场层**：僵尸推进到 4.5 列内 → 用垫材/窝瓜救。这是无炮阵真正活着的原因，
               也是"边路大喷被啃 ≠ 破阵"的机制依据。
  · **分级报错**：CORE（曾/冰瓜/炮/香蒲）被毁 = 崩阵；
               大喷/南瓜/伞/存冰/花被毁 = 磨损，只记 WARN，不终止。

结论可信度：
  L1 静态层（卡 CD / 运算量 / 阳光）= 零假设、零误差。
  L2 动态层 = 看趋势与裕度，绝对值受 SPAWN_GAP / PUMPKIN_HP / EAT_DPS / SKIP_LIFE 影响。
"""

import random
import operator
from . import data as D
from . import fields as F

# ══════════════════════════════════════════════════════════════════
# 阵解积木（v0.2 阵解栏）—— 触发器与比较运算
#
# 轨道函数可以返回老格式 (name, off, aim)，也可以返回 dict：
#     {'op': '核', 'at': 0, 'aim': [2, 9], 'trig': {'kind': 'card', ...}}
# 引擎统一折成 4 元组，`trig` 为空时行为与老版完全一致。
# ══════════════════════════════════════════════════════════════════
_CMP = {
    '<': operator.lt, '<=': operator.le,
    '>': operator.gt, '>=': operator.ge,
    '==': operator.eq, '!=': operator.ne,
}
_TRIG_TTL = 2400          # 触发器最多等这么久（cs），超时记"断裂"

# ══ v0.3：统一说法 —— 阵解栏里只写植物名（寒冰菇 / 咖啡豆 / 毁灭菇 …），
#   引擎内部沿用旧的动作名。这两张表就是"旧名 ↔ 植物名"的唯一映射点。
_OP_ALIAS = {
    '核': '毁灭菇', '模仿核': '模仿毁灭菇',
    '冰': '寒冰菇', '模仿冰': '模仿寒冰菇',
    '存冰': '咖啡豆',
    '垫材': '小喷菇', '垫材2': '花盆', '垫材3': '阳光菇', '垫材4': '胆小菇',
    '种大喷': '大喷菇',
}
_CARD_OF = {
    '毁灭菇': '核', '模仿毁灭菇': '模仿核',
    '寒冰菇': '冰', '模仿寒冰菇': '模仿冰',
    '樱桃': '樱桃', '辣椒': '辣椒', '窝瓜': '窝瓜',
    '小喷菇': '垫材', '花盆': '垫材2',
    '阳光菇': '垫材3', '胆小菇': '垫材4',
    '南瓜': '南瓜',
    '大蒜': '大蒜', '咖啡豆': '咖啡豆', '大喷菇': '大喷菇',
    '玉米炮': '玉米炮', '荷叶': '荷叶', '保护伞': '保护伞',
    '双子花': '双子花',
    # v0.2.1：新增植物的卡片（名字与卡片同名，显式列出便于扩展）
    '三叶草': '三叶草', '墓碑吞噬者': '墓碑吞噬者',
    '火炬树桩': '火炬树桩', '地刺': '地刺', '钢地刺': '钢地刺',
    '高坚果': '高坚果', '双向射手': '双向射手',
    '机枪射手': '机枪射手', '磁力菇': '磁力菇',
}


def _num(v):
    """1.0 → '1'、1.5 → '1.5'（落点坐标的显示口径）"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return ('%d' % f) if f == int(f) else ('%.1f' % f)


def _imp_group(row, rows_n=6):
    """小鬼/拦截炮的分组：1~3 路 = low，其余 = high（一对拦截炮各管一半）"""
    return 'low' if int(row) <= 3 else 'high'


def _norm_act(a):
    """积木 → (name, off, aim, trig, extra)。顺手把旧动作名换成植物名（v0.3 统一说法）

    ★ 2026-10-24：第 5 项 `extra` 带炮的种类与拦截炮参数
      （`cob` = P/S/D、`imp_group` = low/high、`imp_when` = release/apex/land、
        `dyn_kinds` = 分离炮动态落点要打的僵尸种类）。
    """
    keys = ('cob', 'imp_group', 'imp_when', 'dyn_kinds')
    if isinstance(a, dict):
        extra = {k: a.get(k) for k in keys if a.get(k)}
        return (_OP_ALIAS.get(a.get('op'), a.get('op')),
                int(a.get('at') or 0), a.get('aim'), a.get('trig'), extra)
    if len(a) >= 5:
        return (_OP_ALIAS.get(a[0], a[0]), a[1], a[2], a[3], a[4] or {})
    if len(a) >= 4:
        return (_OP_ALIAS.get(a[0], a[0]), a[1], a[2], a[3], {})
    return (_OP_ALIAS.get(a[0], a[0]), a[1], a[2], None, {})


# ------------------------------------------------------------------ 实体
class _Rows(dict):
    """按行存的僵尸列表。★ 5 行场地没有第 6 路，查不到就返回空列表，
    免得所有"遍历某一路"的代码都要先判 row 存在（原来一查 6 就 KeyError）。"""

    def __init__(self, rows):
        super().__init__((r, []) for r in rows)

    def __missing__(self, key):
        return []


class Cell:
    """一个格子。南瓜是独立的一层血，先扣南瓜再扣植物。"""
    __slots__ = ('row', 'col', 'plant', 'plant_hp', 'pumpkin', 'pumpkin_hp',
                 'ladder', 'crater_until', 'atk_t', 'sun_t', 'x',
                 'iced', 'ice_until', 'ash_pending', 'tail', 'grave',
                 'cob_cd', 'awake', 'magnet_t', 'base', 'pops', 'grown',
                 'sun_born')

    def __init__(self, row, col, plant=None, pumpkin=False, ladder=False):
        self.row = row
        self.col = col
        self.x = D.cell_x(col)
        self.plant = plant
        self.plant_hp = D.PLANTS.get(plant, {}).get('hp', D.PLANT_HP_DEFAULT) if plant else 0
        self.pumpkin = pumpkin
        self.pumpkin_hp = D.PUMPKIN_HP if pumpkin else 0
        self.ladder = ladder
        self.crater_until = -1
        self.iced = False
        self.ice_until = -1
        # 灰烬已种下、还没爆（樱桃/辣椒/核）→ 冰车碾不掉它
        self.ash_pending = False
        # ★ 2026-10-22：玉米炮占 **1×2** —— 头格是本体，尾格只是"占位、不能种"
        self.tail = False
        # ★ NE 的墓碑：占格、要先被墓碑吞噬者清掉才能种
        self.grave = False
        # ★ 玉米炮的装填计时（下一个可开炮的时刻）
        self.cob_cd = 0
        # ★ 蘑菇的"睡着"状态（用户 2026-10-22）：
        #   阵图预置的格子里，只有寒冰菇/存冰 是睡的；其余（曾哥/大喷…）本来就是醒的。
        #   静夜里的"新种下的蘑菇一律睡"由 engine._plant_into 负责。
        self.awake = plant not in D.SLEEPING_AT_START
        self.magnet_t = 0
        # ★ 基座（水上=荷叶 / 屋顶=花盆）：阵型里预置的水上格子视为已有基座
        self.base = False
        # ★ 2026-10-22 地刺/地刺王：被"砸/碾"的次数（攒够 crush_hits 才消失）
        self.pops = 0
        # ★ 2026-10-22 阳光菇：是否已长大
        self.grown = False
        self.sun_born = 0
        self.atk_t = 0
        self.sun_t = 0

    def has_content(self):
        return self.plant is not None or self.pumpkin

    def occupied(self):
        """种不下（含玉米炮的尾格、墓碑）"""
        return self.has_content() or self.tail or self.grave

    def take_damage(self, dmg):
        """返回 'pumpkin' / 'plant' / None —— 这一下打穿了哪一层"""
        if self.pumpkin:
            self.pumpkin_hp -= dmg
            if self.pumpkin_hp <= 0:
                self.pumpkin = False
                self.pumpkin_hp = 0
                self.ladder = False      # 南瓜没了，梯子一起没
                return 'pumpkin'
            return None
        if self.plant:
            self.plant_hp -= dmg
            if self.plant_hp <= 0:
                self.plant = None
                return 'plant'
        return None

    def wreck(self):
        """一次性摧毁（冰车碾压 / 灰烬）"""
        plant, self.plant, self.plant_hp = self.plant, None, 0
        pump, self.pumpkin, self.pumpkin_hp = self.pumpkin, False, 0
        self.ladder = False
        return plant, pump

    @property
    def hp_now(self):
        return (self.pumpkin_hp if self.pumpkin else 0) + (self.plant_hp if self.plant else 0)


class Zombie:
    __slots__ = ('kind', 'row', 'x', 'hp', 'hp0', 'spd', 'dmg', 'uniform', 'giant',
                 'frozen_until', 'slowed_until', 'wave', 'alive', 'eating',
                 'stall_until', 'rescued', 'summoned', 'no_eat_x', 'smash_at', 'stall_n',
                 'min_x', 'box_in', 'fuse_in', 'joker_early',
                 'phase', 'vaulted', 'slid', 'armor', 'spd_alt', 'never_eat',
                 'hold_until', 'vault_until', 'vault_to_x',
                 'born_t', 'cat_at', 'eat_ready', 'joker_res',
                 'shield', 'shield0', 'total_hp0', 'daze_until', 'defused', 'rev',
                 'imp_out')

    def __init__(self, kind, row, x, wave, rng):
        self.kind = kind
        self.row = row
        self.x = x
        # ★ 2026-10-23 用户：二类防具（扶梯/报纸/铁门）只挡平射。
        #   `ZOMB` 里的血量是「本体 + 二类防具」，这里拆开：
        #     hp / hp0 = **本体**血（濒死、血量阈值都按本体算 —— 这才是原版语义）
        #     shield   = 二类防具剩余（只有 `pierce=False` 的伤害才扣它）
        sh = D.SHIELD2.get(kind, 0)
        self.shield = self.shield0 = sh
        self.hp = self.hp0 = D.ZOMB[kind][0] - sh
        self.total_hp0 = D.ZOMB[kind][0]
        self.daze_until = -1
        self.uniform = D.ZOMB[kind][3]
        self.giant = D.ZOMB[kind][5]
        v = rng.uniform(D.ZOMB[kind][1], D.ZOMB[kind][2])
        self.spd = D.avg_speed(kind, v)
        _rng = D.WALK_CS_RANGE.get(kind)
        if _rng:
            # ★ 2026-10-23：巨人（白眼/红眼）每只独立抽 420~590cs/列（表的正常随机区间）
            self.spd = D.CELL_W / rng.uniform(_rng[0], _rng[1])
        if kind == '冰车':
            self.spd = D.ice_car_speed(x)
        # 投篮车：匀速（表 216cs/列），就绪/投掷节奏见 `_tick_catapult`
        if kind == '投篮':
            self.spd = D.CELL_W / float(D.CATAPULT_WALK_CS)
        self.dmg = D.EAT_DPS
        self.frozen_until = -1
        self.slowed_until = -1
        self.wave = wave
        self.alive = True
        self.eating = None
        self.stall_until = -1
        self.stall_n = 0
        self.rescued = False
        self.summoned = False
        # ★ 2026-10-22：跳跳**不啃植物**（用户口径）→ 全程不进食，只往前走
        self.no_eat_x = None
        self.never_eat = (kind == '跳跳')
        self.smash_at = -1
        self.min_x = x
        # 小丑：box_in = 还有多少 cs 开盒；fuse_in < 0 表示还没开盒
        self.box_in = -1
        self.fuse_in = -1
        self.joker_early = False
        self.joker_res = None         # 小丑结局：'died' / 'boom' / 'blank'（炸空）
        self.defused = False          # ★ 磁力菇吸走盒子 → 永久无法爆炸
        self.rev = False              # ★ 矿工出土后**向右走**
        # ★ 2026-10-24 拦截炮：巨人**只投一次**小鬼（血量首次 ≤ 50% 时）
        self.imp_out = False
        # ★ 2026-10-22：分阶段速度 / 撑杆跳 / 舞王滑步 / 金属护具
        # ★ 2026-10-23（《僵尸时间表》）：**起步偏差**
        #   正值 = 生成后先停顿（足球/投篮车/撑杆的起步加速）；
        #   负值 = 一出场就已经在场内走了一段（跳跳 / 扶梯），改成把出生点左移。
        adj = D.SPAWN_ADJ_CS.get(kind, 0)
        self.hold_until = -1          # 正值那部分由 Sim 在真正刷出来时补（它知道 t）
        self.born_t = -1              # 真正刷出来的时刻（Sim 填）
        # 投篮车：cat_at = 下一次"投掷"的时刻（-1 = 还没就绪）
        self.cat_at = -1
        # 舞王/伴舞：eat_ready = 这个时刻之前不啃（表的"召唤到啃食"）
        self.eat_ready = -1
        if adj < 0:
            self.x = x + adj * self.spd
            self.min_x = self.x
        self.phase = 'run' if kind in ('撑杆', '海豚') else 'walk'
        self.vaulted = False
        self.vault_until = -1
        self.vault_to_x = 0.0
        self.slid = False
        # 磁力菇只吸得动**一类**金属护具；二类防具（铁门/扶梯）走 `shield`
        self.armor = 0 if kind in D.SHIELD2 else D.ARMOR.get(kind, 0)
        # 撑杆跳完改成"慢速"档（只有这一只有第二速度）
        if kind == '撑杆':
            n = D.ZOMB[kind][4]
            v2 = rng.uniform(*D.SPEED_TIER['慢速'])
            self.spd_alt = v2 * D.SPEED_K * (n + 1) / n
        elif kind == '海豚':
            # ★ 2026-10-23 图鉴：骑海豚 0.8s/格（`spd`），跳过后水豚消失 → 4.7s/格
            self.spd = D.CELL_W / 80.0            # 0.8s = 80cs
            self.spd_alt = D.CELL_W / 470.0       # 4.7s = 470cs
        elif kind == '矿工':
            # ★ 2026-10-24 完整模型：地下 1.2s/格、地上 7s/格（图鉴）
            self.spd = D.CELL_W / float(D.MINER_DIG_CS)
            self.spd_alt = D.CELL_W / float(D.MINER_WALK_CS)
            self.phase = 'dig'
        else:
            self.spd_alt = 0.0

    @property
    def total_hp(self):
        """本体 + 二类防具（波血量、剩余血量统计都用这个）"""
        return self.hp + self.shield


# ------------------------------------------------------------------ 模拟器
class Sim:
    def __init__(self, array, track, wave_script, seed=0,
                 total_waves=20, sun0=None, max_t=400000, skip_hp=0, slots=None,
                 rescue=True, repair=True, allow_ash=True, stall_waves=True,
                 cherry_cols=None, rebuild=False, wogua_flag=True,
                 rescue_tick=None, globals_tick=None, field='PE',
                 replant=None, deck_names=None):
        self.slots = slots or {}
        self.rng = random.Random(seed)
        self.skip_hp = skip_hp
        self.array = array
        # ★ v0.2.1：场地 —— 行数 / 格高 / y 坐标 / 水路 / 昼夜 / 基座 / 禁出
        self.fld = F.get(field)
        self.field_code = self.fld.code
        self.rows = self.fld.rows
        self.cells = {}
        # ★ 5 行场地跑 6 行阵型：第 6 行的植物在这个场地上不存在，直接丢掉
        #   （阵型是按场地摆的，跨场地复用时要显式说明，不能静默当"还在"）
        self.rows_dropped = sorted({r for (r, _c) in array if r > self.rows})
        for (r, c), spec in array.items():
            if r > self.rows:
                continue
            self.cells[(r, c)] = Cell(r, c, spec.get('plant'),
                                      spec.get('pumpkin', False),
                                      spec.get('ladder', False))
        # ★ v0.2.1：阵型里预置的格子视为**已有基座**（水上已种荷叶 / 屋顶已放花盆）；
        #   玉米炮占 1×2 → 尾格标 tail（占位、不能种）
        for (r, c), cell in list(self.cells.items()):
            if r in self.fld.water or self.fld.base_plant:
                cell.base = True
            # ★ 阵图预置的阳光菇视为已经长大（它是成熟阵型的一部分）
            if cell.plant == '阳光菇':
                cell.grown = True
            p = cell.plant
            if p and D.PLANTS.get(p, {}).get('span') == 2 and c + 1 <= 9:
                tcell = self.cells.get((r, c + 1))
                if tcell is None:
                    tcell = self.cells[(r, c + 1)] = Cell(r, c + 1)
                tcell.tail = True
                tcell.base = cell.base
        # ★★ 2026-10-22 用户：「FE 是夜场，蘑菇种植就醒着，不能存冰存核弹」
        #   夜场里**阵图预置的蘑菇全是醒的** —— 不存在"存冰"这种状态。
        #   （存冰位的记账在下面建好之后立刻清空，见 `ice_slots`。）
        if self.fld.night:
            for cc in self.cells.values():
                cc.awake = True
        # ★ NE：墓碑。开局在 5~9 列随机放几格（[01 §四.3]：场上墓碑 < 12 就补一个）
        if self.fld.graves:
            free = [(r, c) for r in self.fld.all_rows() for c in range(5, 10)
                    if (r, c) not in self.cells or not self.cells[(r, c)].occupied()]
            self.rng.shuffle(free)
            for rc in free[:4]:
                cell = self.cells.get(rc)
                if cell is None:
                    cell = self.cells[rc] = Cell(rc[0], rc[1])
                cell.grave = True
        self.track = track
        # ★ v0.3：阵解栏 —— 编辑出来的"全场判定层 / 救场层"由外部驱动（plan.py）
        self.rescue_tick = rescue_tick
        self.globals_tick = globals_tick
        self.plan = None
        self.wave_script = wave_script
        self.total_waves = total_waves
        # ★ 社区约定：表演视频每个 2F 开局 8000 阳光
        self.sun = D.SUN0 if sun0 is None else sun0
        self.sun_peak = self.sun
        self.sun_capped = False
        self.max_t = max_t
        self.rescue = rescue
        self.repair = repair
        self.rebuild = rebuild          # 快速/极速："死了就补"，CORE 被毁不判崩
        # ★ 2026-10-23 运阵模型：**选卡里带了阵型成分**（如 FE.雾四炮带大喷菇）
        #   → 这些植物死了以后持续判定补种，而不是只算一次损失。
        self.replant = set(replant or ())
        self.replant_q = []
        self.wogua_flag = wogua_flag    # w10 要不要窝瓜压冰车
        self.tomato_busy_until = -1
        self.tomato_used_at = -99999
        self._prev_acts = []
        self.stock_ice_cd = -1
        self.last_rescue = {}        # 每路最后一次被救的时刻（喂给饥饿修正）
        self.series = []              # 每秒采样：阳光/僵尸数/减速数/本波剩余
        # ★ 2026-10-20：逐波快照 —— 供 HTML 报告做 hover 明细
        #   （阳光 / 存冰 / 各卡 CD / 计划操作 / 僵尸阵线 / 场上植物）
        self.wave_snap = {}
        self.allow_ash = allow_ash
        self.stall_waves = stall_waves
        self.cherry_cols = cherry_cols or [8, 9, 7, 6]

        self.t = 0
        self.zombies = []
        self.by_row = _Rows(self._rows())
        self.queue = []                  # [(due_t, kind, row, x, wave)]
        self.waves = []
        self.actions = []
        self.card_ready = {k: 0 for k in D.CARDS}
        # ★ 2026-10-25 铲种炮（p）要知道选卡里有没有"炮套件"
        self.deck_names = list(deck_names or [])
        self.broken = []                 # 轨道断裂（卡 CD / 阳光）
        self.crush = []                  # 冰车碾压
        # ★ 2026-10-23：**每一次植物死亡**都记一条（谁、在哪、杀了什么）。
        #   报告里的"归因栏"和崩阵场地图都靠它；没有它就只能从日志文本里猜。
        self.deaths = []
        self.collapse_snap = None        # 崩阵那一刻的场上快照
        self.catapult = []               # 投篮车投掷（含被伞挡下的）
        self.joker_units = []            # 每只小丑的结局（早/晚 × 死/炸空/炸掉什么）
        self.cat_pending = []            # 滞空中的篮球（199cs 后落地结算）
        # ★ 2026-10-24 拦截炮（D）：**只有阵解里出现 D 时**才把小鬼实体化。
        #   没有 D 的阵解仍走"巨人死时把小鬼血量并入本波"的期望型处理（老基线不变）。
        self.imp_fly = []                # 在空中飞的小鬼
        self.imp_active = False          # 本局要不要模拟小鬼投掷
        self.imp_log = []                # 拦截/落地明细（报告用）
        self.log = []                    # 分级事件
        self.lost = {}                   # {(row,col): plant} 已丧失的植物
        self.ice_touched = set()
        self.pending = []            # 待结算的 AoE 命中（忧郁菇一轮 4 次）
        self.boom_q = []             # 待生效的灰烬（结果导向下 delay=0，当帧就结算）
        self.chili_q = []            # 待生效的辣椒
        self.fail = None
        self.events = []
        self.cur_wave = 0
        self.wave_meta = None
        self.done = False
        self.n_kill = 0
        # ★ 2026-10-19：存冰从"计数器"改成"逐格记账"。
        #   原来一个整数 ice_stock 只能表达"还剩几个"，无法表达
        #   「5-3 这一格要和辣椒共用」这条规则（用户点名要的）。
        #   现在每个存冰位记 满/空，5-3 的复用、优先补哪一格都能落地。
        self.ice_slots = {}
        for (r, c), spec in array.items():
            if r > self.rows:
                continue
            if spec.get('plant') == '存冰':
                self.ice_slots[(r, c)] = True
        # ★ 2026-10-22：夜场没有"存冰"这回事（蘑菇种下就醒，核弹也不能存）
        if self.fld.night:
            self.ice_slots.clear()
        # 前场临时存冰位（2-7 / 5-7）：开局空着，w1 用冰卡种上，不再补种
        self.temp_ice = {}
        for rc in (self.slots.get('temp_ice') or []):
            self.temp_ice[tuple(rc)] = False
        self.ice_refill_n = 0
        self.ice_temp_n = 0
        self.ice_refill_skip = 0
        self.ice_emerg_n = 0
        self.ice_emerg_cd = -1
        self.last_freeze_t = -99999
        self.ice_chili_reuse = 0
        self.joker_boom = []          # 真正炸了的小丑（含炸掉了什么）
        self.kernel_log = []          # 每次点核用的坑位（坑位记账）
        self.car_trails = {}          # id(冰车) → 它铺过的格子（车死则冰道消失）
        self.joker_row_n = {r: 0 for r in range(1, self.rows + 1)}
        self.wave_ctrl = {}           # 每波的控制手段：冰 / 灰烬 / 无
        self.bungee_risk = []         # 本波有蹦极却没点冰
        self.bungee_log = []          # ★ 2026-10-22：蹦极的逐波判定明细（保护伞/炮/冰/被偷）
        self._bungee_cur = None
        self._chili_freed_at = -1
        self.wogua_pending = None     # 窝瓜：种下待命 → 判定域命中即刻生效
        self.garlic_slots = [tuple(rc) for rc in (self.slots.get('garlic') or [])]
        self.garlic_swaps = []        # 大蒜换行记录（供报告）
        # ★ 极速关**有冰车/投篮**时：不带大蒜（会被碾），改在 2-7 / 5-7 种大喷抬丑抗
        self.struct_fog_slots = [tuple(rc) for rc in (self.slots.get('struct_fog') or [])]
        self.fog_fix = []             # [(t, wave, row, col)] 结构位大喷的每次补种
        self.rebuilds = []            # 快速/极速"死了就补"的重建记录
        self.row_min = {r: 9999 for r in range(1, self.rows + 1)}
        self.dmg_dealt = 0.0
        self.slow_samples = 0
        self.slow_hits = 0
        self.relaxed = False
        # 冰车审计：每辆冰车最靠左到过哪里、死因
        self.car_audit = []
        # v0.2.1：玉米炮开炮记录（t / 落点 / 用哪门炮）
        self.cob_shot = []

    # ------------------------------------------------ 场地坐标（v0.2.1）
    def py(self, row, col=1):
        """植物 y。★ 屋顶是**逐格**给的（前 5 列在斜坡上，每列 −20px）"""
        return self.fld.plant_y(row, col)

    def zy(self, row):
        """僵尸 y（后院 50+85(r−1) / 前院 50+100(r−1) / 屋顶 40+85(r−1)）"""
        return self.fld.zombie_y(row)

    def _rows(self):
        return self.fld.all_rows()

    def _water(self):
        return self.fld.water

    def _land(self):
        return self.fld.land

    # ------------------------------------------------ 存冰记账
    @property
    def ice_stock(self):
        """阵上还剩几个预置寒冰菇（含 2-7/5-7 两个前场临时位）"""
        return (sum(1 for v in self.ice_slots.values() if v)
                + sum(1 for v in self.temp_ice.values() if v))

    def _chili_slot(self):
        return self.slots.get('chili_slot')

    def _refill_ice(self):
        """
        用**冰卡**补一格预置冰。
        返回 ('ok', rc) / ('full', None) / ('reserve', rc)

        ★ 用户 2026-10-19 原话：
          「如果存冰位没有满，卡槽的冰一好就拿它补存冰
            （5-3 存冰位如果在下一波要复用辣椒，辣椒用了再补存冰）」
        → 所以 5-3 永远**最后**才补；如果只剩 5-3 空着、而辣椒又快好了，
          就这一波先不补，等辣椒打出去再补。
        """
        empty = [rc for rc, full in self.ice_slots.items() if not full]
        if not empty:
            return ('full', None)
        chili = self._chili_slot()
        empty.sort(key=lambda rc: (rc == chili, rc[0], rc[1]))
        rc = empty[0]
        if rc == chili and len(empty) == 1:
            cd = self.card_ready.get('辣椒', 0) - self.t
            if cd <= D.CHILI_RESERVE_CS:
                self.ice_refill_skip += 1
                return ('reserve', rc)
        self.ice_slots[rc] = True
        self.ice_refill_n += 1
        return ('ok', rc)

    def _use_stock_ice(self, why=''):
        """
        点掉一个预置寒冰菇 → 立即冰冻。
        优先点**不是 5-3** 的那几个，把 5-3 尽量留给辣椒。
        """
        # 先烧**前场临时位**（2-7/5-7）：它最容易被冰车压、被核坑占，
        # 留着不用就是浪费；再烧永久位里不是 5-3 的那几个。
        temp = [rc for rc, f in self.temp_ice.items() if f]
        if temp:
            rc = temp[0]
            self.temp_ice[rc] = False
            self._log('ICE', '点存冰 %d-%d（前场临时位 · 剩 %d 个）'
                      % (rc[0], rc[1], self.ice_stock))
            self._freeze()
            return True
        full = [rc for rc, f in self.ice_slots.items() if f]
        if not full:
            return False
        chili = self._chili_slot()
        full.sort(key=lambda rc: (rc == chili, rc[0], rc[1]))
        rc = full[0]
        self.ice_slots[rc] = False
        self._log('ICE', '点存冰 %d-%d（剩 %d 个）%s'
                  % (rc[0], rc[1], self.ice_stock, ('· ' + why) if why else ''))
        self._freeze()
        return True

    # ------------------------------------------------ 事件记录
    def _log(self, sev, what, row=None, detail='', col=None):
        self.log.append(dict(t=self.t, wave=self.cur_wave, sev=sev, what=what,
                             row=row, col=col, detail=detail))

    def _record_death(self, row, col, plant, by, x=None, cause=''):
        """记一次植物死亡：**什么僵尸在哪个格子杀死了什么植物**。"""
        self.deaths.append(dict(t=self.t, wave=self.cur_wave, row=row, col=col,
                                plant=plant or '南瓜',
                                by=getattr(by, 'kind', by) or '僵尸',
                                x=round(getattr(by, 'x', x if x is not None else 0)),
                                cause=cause))
        if plant and plant in self.replant:
            if not any(q['row'] == row and q['col'] == col
                       for q in self.replant_q):
                self.replant_q.append(dict(row=row, col=col, plant=plant,
                                           died=self.t))

    def _field_snapshot(self):
        """场上一张"二维坐标图"需要的全部数据（崩阵瞬间 / 2F 结束）。"""
        cells = []
        for (r, c) in sorted(self.cells):
            cell = self.cells[(r, c)]
            spec = self.array.get((r, c)) or {}
            if not (cell.plant or cell.pumpkin or cell.base or cell.grave
                    or cell.iced or cell.crater_until > self.t):
                continue
            cells.append(dict(
                row=r, col=c, init=spec.get('plant') or '',
                plant=cell.plant or '',
                plant_hp=round(cell.plant_hp) if cell.plant else 0,
                pumpkin=bool(cell.pumpkin),
                pumpkin_hp=round(cell.pumpkin_hp) if cell.pumpkin else 0,
                ladder=bool(cell.ladder), base=bool(cell.base),
                grave=bool(cell.grave), iced=bool(cell.iced),
                crater=bool(cell.crater_until > self.t),
                cob_cd=(round(max(0, cell.cob_cd - self.t))
                        if cell.plant == '玉米炮' else None),
                core=bool(spec.get('core'))))
        # ★ 2026-10-23：血量显示用「本体 + 二类防具」，否则铁门会显示成 270
        zs = [dict(kind=z.kind, row=z.row, x=round(z.x), hp=round(z.total_hp),
                   giant=bool(z.giant))
              for z in self.zombies if z.alive]
        acts = [dict(t=a['t'], name=a.get('name'), wave=a.get('wave'),
                     rc=(a.get('rc') or (tuple(a['aim'])
                                        if isinstance(a.get('aim'), (list, tuple))
                                        and len(a['aim']) == 2
                                        and not isinstance(a['aim'][1], str)
                                        else None)),
                     aid=a.get('aid') or a.get('id'))
                for a in self.actions
                if a.get('ok') and a.get('wave') == self.cur_wave]
        return dict(t=self.t, wave=self.cur_wave, rows=self.rows,
                    water=list(self.fld.water), cells=cells, zombies=zs,
                    actions=acts,
                    cards={k: max(0, round(v - self.t))
                           for k, v in self.card_ready.items()},
                    sun=round(self.sun), fail=(self.fail or None))

    def _fatal(self, why, detail='', row=None, col=None):
        """
        CORE 植物被毁 → 崩阵。
        ★ 但快速/极速关按用户口径是"死了就补"：摘掉的曾/瓜可以重建，
          所以这两档不判崩，改成进 rebuild 队列（报告里单列"重建 N 次"）。
          这不是放水 —— 重建消耗 200~450 阳光 + 一张卡，账会自己显形。
        """
        if self.rebuild:
            self.rebuilds.append(dict(t=self.t, wave=self.cur_wave,
                                      why=why, row=row, col=col, done=False, plant=None))
            self._log('REBUILD', '待重建：%s' % why, row=row, col=col,
                      detail='快速/极速关口径：死了就补，不判崩')
            return
        self._log('FATAL', why, row=row, col=col, detail=detail)
        if self.fail is None:
            self.fail = dict(why=why, detail=detail, wave=self.cur_wave,
                             t=self.t, row=row, col=col)
            # ★ 2026-10-23：把**崩阵那一瞬间**的场上情况定格下来（之后不再变）
            self.collapse_snap = self._field_snapshot()
        self.done = True

    # ------------------------------------------------ 出怪选行 / 出生点
    def _legal_rows(self, kind, w):
        """[维 09 §九.3] 这一只可以走哪几行。

        · 水路只允许 普/旗帜/路障/铁桶/潜水/海豚/气球（鸭子是普/路/桶自动转换）
        · 波数 < 5 的水路只允许海豚、潜水
        · 场地禁出（NE 无冰车、RE 无舞王/矿工/潜水/海豚）
        · 舞王只在中三路（五行前院）—— 由 `fld.allows` 处理
        """
        rows = []
        water_only = kind in D.WATER_ONLY
        land_only = kind in D.LAND_ONLY
        for r in self.fld.all_rows():
            if not self.fld.allows(kind, r):
                continue
            if water_only and r not in self.fld.water:
                continue
            if land_only and r not in self.fld.land:
                continue
            if w < 5 and r in self.fld.water and kind not in D.WATER_ONLY:
                continue
            rows.append(r)
        return rows or list(self.fld.all_rows())

    def _spawn_lane(self, kind, w):
        """按 [维 09 §九.1] 的三状态量（Weight / LastPicked / SecondLastPicked）
        给一只僵尸选行。

        `Weight_i` 在生存无尽里默认 1（刚丢过推车的行 0.5 / 0.01），
        所以平滑权重的差异完全来自 LastPicked / SecondLastPicked ——
        效果是"刚被选过的行权重变低、长期没出怪的行权重变高"，
        不会出现旧模型那种"同一路连刷一整波"的假聚集。
        """
        rows = self._legal_rows(kind, w)
        hist = self.__dict__.setdefault('_lane_hist', {})
        for r in self._rows():
            hist.setdefault(r, [0, 0])
        weight = {r: 1.0 for r in rows}
        # 推车惩罚：某行刚丢车 → 接下来 1~2 波压力大幅下降
        lost = self.__dict__.setdefault('_mower_lost_at', {})
        for r in rows:
            d = w - lost.get(r, -99)
            if d <= 1:
                weight[r] = 0.01
            elif d <= 2:
                weight[r] = 0.50
        total_w = sum(weight.values()) or 1.0
        smooth = {}
        for r in rows:
            wp = weight[r] / total_w
            last, second = hist[r]
            p_last = 6.0 * last * wp + 6.0 * wp - 0.75
            p_second = second * wp + wp - 0.25
            smooth[r] = wp * max(0.01, min(100.0, p_last + p_second))
        tot = sum(smooth.values())
        if tot <= 0:
            # [维 09 §九.2 推论 1] 所有行权重 0 → 必定第 6 行（或最后一行）
            pick = rows[-1]
        else:
            x = self.rng.random() * tot
            acc = 0.0
            pick = rows[-1]
            for r in rows:
                acc += smooth[r]
                if x <= acc:
                    pick = r
                    break
        # 插入事件：所有合法行 +1，被选中的行清零
        legal = set(self._legal_rows(kind, w))
        for r in self._rows():
            if r in legal:
                hist[r][0] += 1
                hist[r][1] += 1
        hist[pick][1] = hist[pick][0]
        hist[pick][0] = 0
        return pick

    def _spawn_x(self, kind, is_flag):
        """[维 09 §一] 按僵尸类型的出生点；旗帜波整体右移 40px。"""
        lo, hi = D.SPAWN_X_BY_TYPE.get(kind, D.SPAWN_X)
        if is_flag and kind != '旗帜':
            lo += D.SPAWN_X_FLAG_OFFSET
            hi += D.SPAWN_X_FLAG_OFFSET
        return float(self.rng.uniform(lo, hi))

    # ------------------------------------------------ 生成
    def spawn_wave(self, w):
        if w == 1:
            self.__dict__['_lane_hist'] = {}
            self.__dict__['_mower_lost_at'] = {}
        # ★ 2026-10-23：上一波没执行完的**循环**事件直接放弃（普通定时事件不受影响）
        self.events = [e for e in self.events
                       if e.get('rep_n') is None or e.get('wave') == w]
        # [你] 每 5 波补一次临时存冰（w1 种 2-7/5-7 两个，w7 补一次）
        # ★ 2026-10-19：删掉"每 5 波自动 +2"——
        #   用户的口径是「存冰位没满、卡槽的冰一好就拿它补存冰」，
        #   自动补会让这条永远不触发（存冰恒满，等于白送）。
        # ★★ 2026-10-20：**w9 整波锁死窝瓜**。
        #   实测（慢速 seed2）：w9 期间救场用窝瓜砸了 2 路红眼（159.3s），
        #   于是 w10 开场窝瓜在 CD，压车推迟到 191.7s ——
        #   而 5 路冰车 188.4s 就把 5-9 铺了（车头 638、车尾 718）。
        #   w9 有 45s 拖时间 + 7.2s 红字，跨过去要 67s+，所以锁 90s。
        #   w9 靠两张垫材扛，窝瓜必须留给 w10 的压车。
        if w == 9 and self.wogua_flag:
            self.tomato_busy_until = self.t + 9000
            self._log('INFO', 'w9 锁定窝瓜：整波不动，留给 w10 压冰车（保 5-9 核坑）')
        if w == 10 and self.wogua_flag:
            # ★ 无条件把窝瓜锁给这一波（不管 5-9 当时有没有冰）
            self.tomato_busy_until = self.t + D.TOMATO_RESERVE_CS
            self._log('INFO', 'w10 锁定窝瓜：整波只为压 5 路冰车')
            if (self.cells.get((5, 9)) or Cell(5, 9)).iced:
                c = self.cells.setdefault((5, 9), Cell(5, 9))
                c.iced = False
                c.ice_until = -1
                self._log('RESCUE', 'w10 刷新：清掉 5-9 残留冰道', row=5, col=9)
        if w in D.ICE_FLAG_CLEAR:
            self._clear_ice_trail()
        script = self.wave_script(w)
        is_flag = (w % 10 == 0)

        # ★★ 2026-10-23：**严格按原版出怪列表的顺序生成**。
        #   旧版把种类展开后 `shuffle` 一遍，等于把列表顺序彻底打乱 ——
        #   而原版"每波刷新时严格按列表预先设定的顺序依次生成"，
        #   顺序会通过 9.1 的 LastPicked / SecondLastPicked 影响选行。
        order = getattr(script, 'order', None)
        if order is None:
            kinds = []
            for kind, n in script.items():
                kinds.extend([kind] * n)
        else:
            kinds = list(order)

        total_hp = 0
        skip_hp = 0
        skips = []
        idx = 0
        for kind in kinds:
            if kind not in D.ZOMB:
                continue
            # ★ 2026-10-23：**场地禁出的僵尸不能计进本波血量**（NE 无冰车等）；
            #   否则 total_hp 虚高、刷波阈值被抬高，等于白送强度。
            if not self.fld.allows(kind):
                continue
            total_hp += D.ZOMB[kind][0]
            # ★ 分路（[维 09 §九]）：合法行 + 平滑权重（LastPicked / SecondLastPicked）
            row = self._spawn_lane(kind, w)
            if kind in D.SKIP_KINDS:
                hp0 = D.ZOMB[kind][0]
                skip_hp += hp0
                # ★ 不再用固定 15s 衰减：改成"按该路的实际 dps 被清掉"，
                #   否则四档出怪的波长会被这个常数抹平成一样的值。
                skips.append([float(hp0), D.SKIP_DPS.get(row, 150.0)])
                idx += 1
                continue
            # ★★ 2026-10-20 用户：「pvz 每一波出怪，所有的怪都是同一时刻内刷出来的，
            #   具体刷怪地点在第 10 列哪个点有微小差异。」
            #   → 同一时刻生成（没有僵尸间碰撞箱，允许重合），
            #     x 按 [维 09 §一] 的类型出生点 + 旗帜波整体右移 40。
            x = self._spawn_x(kind, is_flag)
            self.queue.append((self.t, kind, row, x, w))
            idx += 1

        thr = self.rng.uniform(*D.R2_THRESHOLD)
        hard = self.rng.randint(*D.R3_HARD)
        meta = dict(wave=w, t=self.t, total_hp=total_hp, thr=thr, hard=hard,
                    zs=[], skip_hp=skip_hp, skips=skips,
                    next_at=None, age=0, reason=None, stall=None, remain=total_hp)
        self.waves.append(meta)
        self.wave_meta = meta
        self.cur_wave = w

        # ★ 2026-10-23 用户：「空降落地和珊瑚一样，在简化模型下**忽略时延**，
        #   视为在特定区域突然出现」→ 每 20 波的收尾（w20）直接把三人组放进场，
        #   不走"落地/开啃"的时序（表里 珊瑚开啃 252 / 空降落地 575~594 都不计）。
        if w % 20 == 0:
            self._endgame_spawn(w)

        self._nuke_retry = 0
        self._wogua_retry = 0
        self.relaxed = bool(self.skip_hp and total_hp < self.skip_hp)
        # 把运行时状态喂给轨道函数，让它能按 CD 判定（而不是死按周期）
        # ★ v0.3：ctx 里还带 plants / cells / ops_by_wave，供
        #   「场上某植物数量」「某格是什么植物」「之前某波真的做了什么」这些条件用
        ctx = self.plan_ctx()
        ctx['wave'] = w
        ctx['fixed_off'] = bool(self.__dict__.get('_fixed_off'))
        acts = [_norm_act(a) for a in self.track(w, ctx)]   # (name, off, aim, trig, extra)
        self._prev_acts = [a[0] for a in acts]     # 供下一波判定"上一波是不是核"
        if self.relaxed:
            for name, off, aim, _t, _x in acts:
                self.log.append(dict(t=self.t + off, wave=w, sev='INFO', what='松弛',
                                     row=None, col=None,
                                     detail='本波总血 %d < %d，不烧卡' % (total_hp, self.skip_hp)))
            return meta
        for name, off, aim, trig, extra in acts:
            self._schedule(self.t + off, name, aim, w, trig=trig, extra=extra)

        # ---- 波角色 + 控制手段（控丑报告要用）
        ice_names = ('寒冰菇', '模仿寒冰菇', '咖啡豆', '冰', '模仿冰', '存冰')
        ash_names = ('毁灭菇', '模仿毁灭菇', '樱桃', '辣椒', '核', '模仿核')
        role = ('起手' if w == 1 else
                '旗波' if w in (10, 20) else
                '收尾' if w in (9, 19) else '常规')
        self.wave_ctrl[w] = dict(
            role=role,
            ice=min((off for nm, off, _a, _t, _x in acts if nm in ice_names), default=None),
            ash=min((off for nm, off, _a, _t, _x in acts if nm in ash_names), default=None),
            fog=('种大喷' in [nm for nm, _o, _a, _t, _x in acts]),
            acts=[nm for nm, _o, _a, _t, _x in acts],
            n_joker=script.get('小丑', 0),
            n_bungee=script.get('蹦极', 0),
            n=sum(script.values()),
        )
        if script.get('蹦极'):
            has_ice = any(nm in ice_names for nm, _o, _a, _t, _x in acts)
            # ★ 2026-10-22 用户：**炮不会被蹦极锁定**；保护伞覆盖的植物也不用管。
            #   所以"这一波要防蹦极"只在**真的有目标暴露**时才算 —— 否则不记风险，
            #   报告里也不会冒出"蹦极无冰"这种误报（经典八炮除炮外全在伞下）。
            self._bungee_resolve()          # 上一波若还没结算，先收尾
            self._bungee_cur = self._bungee_plan(w)
            if self._bungee_cur and self._bungee_cur.get('targets'):
                self.bungee_risk.append(dict(wave=w, n=script['蹦极'], ice=has_ice))

        # ---- hover 快照：计划内 / 机会性 分开记
        #   计划内 = N / A / A' / I / 窝瓜压车 / 种大喷（轨道明确排的动作）
        #   机会性 = 补存冰（卡一好就补）、垫材、救急窝瓜（临场反应，不算轨迹）
        opportunistic = {'寒冰菇', '模仿寒冰菇', '小喷菇', '花盆', '阳光菇', '胆小菇',
                         '窝瓜'}
        plan = [nm for nm, _o, _a, _t, _x in acts if nm not in opportunistic]
        extra = [nm for nm, _o, _a, _t, _x in acts if nm in opportunistic]
        self.wave_snap[w] = dict(
            w=w, t0=self.t, sun=round(self.sun), ice=self.ice_stock,
            cards={k: max(0, v - self.t) for k, v in self.card_ready.items()},
            plan=plan, extra=extra,
            n=sum(script.values()), n_joker=script.get('小丑', 0),
            n_bungee=script.get('蹦极', 0), n_car=script.get('冰车', 0),
            total_hp=total_hp, front={}, plants={}, pumpkin=0, alive=0, t_last=self.t,
        )
        return meta

    def _endgame_spawn(self, w):
        """w20 收尾三人组：珊瑚（后院）/ 空降（天台），**忽略时延**直接出现在场上。

        ★ 用户 2026-10-23 的完整口径：
          · RE（天台）空降区 = **所有行、第 5~9 列**
          · PE / FE 珊瑚刷新区 = **水路（3/4 路）第 6~9 列**
          · 在区域里**随机挑 3 个格子**，每格随机是 普僵 / 路障 / 铁桶
          · 忽略"落地 / 开啃"时延（表里 252 / 575~594cs 都不计）
        """
        eg = getattr(self.fld, 'endgame', None)
        if eg == 'coral':
            rows, cols = list(self.fld.water), list(range(6, 10))
        elif eg == 'airdrop':
            rows, cols = list(self.fld.all_rows()), list(range(5, 10))
        else:
            return
        cells = [(r, c) for r in rows for c in cols]
        if not cells:
            return
        pick = self.rng.sample(cells, min(3, len(cells)))
        for (r, c) in pick:
            kind = self.rng.choice(('普通', '路障', '铁桶'))
            z = Zombie(kind, r, D.cell_x(c), w, self.rng)
            z.born_t = self.t
            self.zombies.append(z)
            self.by_row[r].append(z)
            if self.wave_meta is not None:
                self.wave_meta['zs'].append(z)
                self.wave_meta['total_hp'] += z.total_hp0
                self.wave_meta['remain'] = self.wave_meta.get('remain', 0) + z.total_hp0
            self._log('INFO', 'w%d %s：%d-%d 出现 %s'
                      % (w, '珊瑚' if eg == 'coral' else '空降', r, c, kind),
                      row=r, col=c,
                      detail='用户口径：区域内随机 3 格 · 忽略落地时延')

    def _schedule(self, t, name, aim, w, kind='act', trig=None, due=None,
                  bid=None, mode=None, extra=None):
        """
        ★ v0.2：`trig` 是"触发器"（阵解栏里的积木可以挂条件）。
          None  → 老行为：到点就执行
          其它  → 到点后每 tick 求值，`fire` 执行 / `wait` 继续等 / `expire` 丢弃

        ★ 2026-10-24：`due` = **这一块积木"本应生效"的时刻**（名义时刻）。
          和 `t` 的区别：玩家/阵解说"9s 一对炮"时，如果这一拍恰好赶上炮在装填、
          引擎让事件"等 100cs 再试"，实际生效时刻就会晚。**定时链必须按名义时刻走**，
          否则每等一次就往后漂一点，几十秒后节奏就散了（实测：慢速关出现
          3000cs / 5600cs 的炮空窗，冰车正是从这些空窗里碾进来的）。

        ★ 2026-10-24：`extra` 带炮的种类（`cob` = P/S/D）与拦截炮参数
          （`imp_group` / `imp_when`）。
        """
        ev = dict(t=t, name=name, aim=aim, wave=w, kind=kind,
                  due=(t if due is None else due))
        if bid:
            ev['bid'] = bid
        if mode:
            ev['mode'] = mode
        if extra:
            ev.update(extra)
            if extra.get('cob') == 'D' or (trig or {}).get('kind') in ('imp',
                                                                      'imp_ground'):
                # 延迟炮 / 尾炸炮 = 要炸空中的（或刚落地的）小鬼 → 本局把小鬼实体化
                self.imp_active = True
        if trig:
            ev['trig'] = trig
            # ★ 2026-10-22：`since`（距上次某积木生效后）是跨波锚点，
            #   等待时间本身就是用户给的 at，所以 TTL 至少要覆盖它。
            ttl = trig.get('ttl')
            if ttl is None:
                if trig.get('kind') == 'imp':
                    # 拦截炮要等"巨人投出小鬼"，可能等很久（巨人要掉一半血）
                    ttl = 60000
                elif trig.get('kind') not in ('since', 'after_block'):
                    ttl = _TRIG_TTL
                else:
                    ttl = int(trig.get('at') or 0) + _TRIG_TTL
            ev['ttl'] = ttl
            if trig.get('repeat'):
                ev['repeat'] = trig['repeat']
        self.events.append(ev)

    def _eval_trig(self, trig):
        """
        触发器求值 → 'fire' / 'wait' / 'expire'

        支持的类型（和阵解栏 UI 一一对应）：
          card   某张卡 CD 转好（+offset）          ← "卡片 cd"
          dist   某类僵尸与某参照的距离              ← "距离"
          state  场上状态（存冰数 / 本路僵尸数 / 本波剩余血量）
          all / any / not   组合
          after  依赖前一块（由编译期折成 time，不走这里）
        """
        k = (trig or {}).get('kind')
        if k in (None, 'spawn', 'time', 'after'):
            return 'fire'
        if k == 'card':
            name = trig.get('name')
            if name not in self.card_ready:
                return 'expire'
            return ('fire' if self.card_ready[name] + trig.get('offset', 0) <= self.t
                    else 'wait')
        if k == 'dist':
            d = self._trig_dist(trig)
            if d is None:
                return 'wait'
            return 'fire' if _CMP[trig.get('cmp', '<=')](d, trig.get('value', 0)) else 'wait'
        if k == 'state':
            v = self._trig_state(trig)
            if v is None:
                return 'wait'
            return 'fire' if _CMP[trig.get('cmp', '>=')](v, trig.get('value', 0)) else 'wait'
        if k == 'after_block':
            # ★★ 2026-10-23 用户：「具备运算量的操作（N/P/A/A′…）必须是定时的，
            #   使用触发器『距某积木生效后若干时长』；每个积木唯一命名 波数-候选-序号」。
            #   → `id` 指到具体那一块（不是"任一同名操作"），这才是"定时"。
            fired = self.__dict__.setdefault('_block_fired', {})
            t0 = fired.get(trig.get('id'))
            if t0 is None:
                return 'wait'
            return ('fire' if self.t - t0 >= int(trig.get('at') or 0)
                    else 'wait')
        if k == 'since':
            # ★ 2026-10-22 用户口径：**距离上次某个积木生效 N cs 之后**
            #   —— 跨波锚点。例：上一波的「玉米炮」生效后 8800cs 再开炮，
            #   把 9s 节奏**用手算的时机**表达出来（而不是强制刷波）。
            op = trig.get('op')
            names = {op, _OP_ALIAS.get(op, op)} if op else set()
            last = None
            for a in self.actions:
                if a.get('name') in names and a.get('ok') is not False:
                    if last is None or a['t'] > last:
                        last = a['t']
            if last is None:
                last = (self.wave_meta or {}).get('t', self.t)
            return ('fire' if self.t - last >= int(trig.get('at') or 0)
                    else 'wait')
        if k == 'imp':
            # ★ 2026-10-24 拦截炮（D）：等"巨人投出的小鬼"飞到某个阶段再开炮。
            #   三个阶段由用户定：出手 / 最高点 / 落地前（`D.IMP_WINDOWS`）。
            lo, hi = D.IMP_WINDOWS.get(trig.get('when') or 'apex', (0.4, 0.6))
            grp = trig.get('group') or 'low'
            imps = [i for i in self.imp_fly
                    if not i.get('killed') and not i.get('ground')
                    and (grp == 'any' or _imp_group(i['row'], self.rows) == grp)]
            if not imps:
                return 'wait'
            prog = [(self.t - i['t0']) / float(max(1, i['t1'] - i['t0']))
                    for i in imps]
            if any(lo <= x < hi for x in prog):
                return 'fire'
            # 全飞过去了（已经落地）→ 这一发没意义了
            if all(x >= hi for x in prog):
                return 'expire'
            return 'wait'
        if k == 'imp_ground':
            # ★ 2026-10-25 尾炸炮（d）：等"已经落地、但还没开始啃植物"的小鬼。
            #   落地窗口只有 `IMP_GROUND_CS`，所以一落地就该炸。
            g = [i for i in self.imp_fly
                 if not i.get('killed') and i.get('ground')]
            return 'fire' if g else 'wait'
        if k == 'not':
            r = self._eval_trig(trig.get('of') or {})
            return {'fire': 'wait', 'wait': 'fire', 'expire': 'expire'}[r]
        if k in ('all', 'any'):
            rs = [self._eval_trig(t) for t in (trig.get('of') or [])]
            if k == 'all':
                if any(r == 'expire' for r in rs):
                    return 'expire'
                return 'fire' if all(r == 'fire' for r in rs) else 'wait'
            if any(r == 'fire' for r in rs):
                return 'fire'
            return 'expire' if all(r == 'expire' for r in rs) else 'wait'
        return 'fire'

    def _trig_dist(self, trig):
        """某类僵尸到参照物的距离（px，沿 x 轴；axis=row 时按行差×80）"""
        zs = [z for z in self.zombies if z.alive and z.hp > 0]
        kind = trig.get('zombie') or '任意'
        if kind == '巨人':
            zs = [z for z in zs if z.giant]
        elif kind != '任意':
            zs = [z for z in zs if z.kind == kind]
        if not zs:
            return None
        ref = trig.get('ref') or {}
        if ref.get('kind') == 'front':
            rows = ref.get('rows') or list(range(1, self.rows + 1))
            zs = [z for z in zs if z.row in rows]
            if not zs:
                return None
            z = min(zs, key=lambda x: x.x)
            return z.x if trig.get('axis', 'x') == 'x' else z.row
        r0 = ref.get('row', 1)
        c0 = ref.get('col', 9)
        if trig.get('axis', 'x') == 'x':
            zs = [z for z in zs if z.row == r0] if ref.get('same_row', True) else zs
            if not zs:
                return None
            z = min(zs, key=lambda x: x.x)
            return z.x - D.cell_x(c0)          # 正数 = 僵尸还在右边（没到）
        p = zs[0]
        return abs(p.row - r0) * 80.0

    def _trig_state(self, trig):
        what = trig.get('what')
        if what == 'ice_stock':
            return self.ice_stock
        if what == 'sun':
            return self.sun
        if what == 'zombies_in_row':
            row = trig.get('row') or 1
            return sum(1 for z in self.by_row.get(row, ()) if z.alive and z.hp > 0)
        if what == 'zombies_total':
            return sum(1 for z in self.zombies if z.alive and z.hp > 0)
        if what == 'wave_hp':
            return (self.wave_meta or {}).get('remain', 0)
        # ★ 2026-10-22 炮阵常用：**有几门炮装填完毕**
        #   用户口径：「收尾时如果两对炮好了，就别再无限垫了，直接开一对
        #   （另一对留到下一波）」。一对 = 2 门，两对 = 4 门。
        if what == 'cobs_ready':
            return sum(1 for c in self.cells.values()
                       if c.plant == '玉米炮' and c.plant_hp > 0
                       and c.cob_cd <= self.t)
        if what == 'cobs_total':
            return sum(1 for c in self.cells.values()
                       if c.plant == '玉米炮' and c.plant_hp > 0)
        # ★ 本路最靠前（最左）那只活僵尸的 x；本路空着返回 None（= 继续等）
        if what == 'front_x':
            row = trig.get('row') or 1
            zs = [z for z in self.by_row.get(row, ()) if z.alive and z.hp > 0]
            return min((z.x for z in zs), default=None)
        return None

    def _tick_spawn(self):
        if not self.queue:
            return
        due = [q for q in self.queue if q[0] <= self.t]
        if not due:
            return
        self.queue = [q for q in self.queue if q[0] > self.t]
        for _, kind, row, x, w in due:
            z = Zombie(kind, row, x, w, self.rng)
            z.born_t = self.t
            _adj = D.SPAWN_ADJ_CS.get(kind, 0)
            if _adj > 0:
                # 起步加速：《僵尸时间表》反解的常数偏差（橄榄 92 / 投篮 105 / 撑杆 136 …）
                z.hold_until = self.t + _adj
            if kind == '小丑':
                # ★ 2026-10-22 用户口径：早爆 / 晚爆的权重看**这一路最靠前的植物**在几列
                #   —— 前排（7~9 列）重点模拟早爆，后排（2~4 列）重点模拟晚爆。
                early = self.rng.random() < D.joker_early_p(self._front_plant_col(row))
                lo, hi = (D.JOKER_BOX_EARLY if early else D.JOKER_BOX_LATE)
                z.box_in = self.rng.randint(lo, hi)
                z.joker_early = early
                self.joker_row_n[z.row] = self.joker_row_n.get(z.row, 0) + 1
                setattr(self, '_joker_n', getattr(self, '_joker_n', 0) + 1)
            self.zombies.append(z)
            if w == self.cur_wave and self.wave_meta:
                self.wave_meta['zs'].append(z)

    # ------------------------------------------------ 行动
    def _reserved(self, name, within=800):
        """轨道在 within cs 内要用这张卡 → 救场不许抢（玩家会先看排程）"""
        for e in self.events:
            if e.get('name') == name and self.t <= e['t'] <= self.t + within:
                return True
        return False

    # ------------------------------------------------ 救场层的"预演-回溯"工具
    def wave_role(self, w=None):
        """这一波的角色（起手 / 常规 / 收尾 / 旗波）"""
        w = int(self.cur_wave if w is None else w)
        return ((self.wave_ctrl.get(w) or {}).get('role')
                or ('起手' if w == 1 else '旗波' if w in (10, 20)
                    else '收尾' if w in (9, 19) else '常规'))

    def incoming_dmg(self, z, horizon=300):
        """**已经排上队的伤害**里，有多少会落在这一只身上（预演-回溯用）

        ★ 2026-10-24 用户：「确认应用了回溯算法，保证不会因轨道中必然死的怪
          浪费救场资源」。所以救场前先问：这只怪已经被轨道"预定"打死了吗？
          · `boom_q`：已开炮/已种下的灰烬（结果导向下 fuse=0，多数当帧结算，
            但绝对时间轴里可能有排队的）
          · `pending`：AoE 命中队列（忧郁菇一轮 4 次命中）
          · `chili_q`：辣椒（整行）
        命中判定沿用引擎自己的几何口径。
        """
        tot = 0.0
        try:
            for item in self.boom_q:
                if item[0] > self.t + horizon:
                    continue
                row, col, radius, dmg = item[1], item[2], item[3], item[4]
                cx, cy = D.cell_x(col), self._aim_py(row, col) + D.PLANTS[
                    '玉米炮']['cob']['dy']
                zy = self.zy(z.row)
                if (z.x + 20 - cx) ** 2 + (zy + 20 - cy) ** 2 <= radius ** 2:
                    tot += dmg
            for _t, row, rows_n, lo, hi, dmg, _p in list(self.pending):
                if _t > self.t + horizon:
                    continue
                if abs(z.row - row) > max(0, rows_n // 2):
                    continue
                if lo <= z.x <= hi:
                    tot += dmg
            for _t, row in list(self.chili_q):
                if _t <= self.t + horizon and z.row == row:
                    tot += D.ASH_DMG
            # 轨道**还没生效**的灰烬/炮：按名义时刻看，近了也算"即将被打死"
            for e in self.events:
                if e['t'] > self.t + horizon:
                    continue
                nm = e.get('name')
                if nm not in ('毁灭菇', '模仿毁灭菇', '樱桃', '辣椒', '玉米炮'):
                    continue
                aim = e.get('aim')
                if not (isinstance(aim, (list, tuple)) and len(aim) == 2
                        and not isinstance(aim[1], str)):
                    continue
                r0, c0 = float(aim[0]), float(aim[1])
                if abs(z.row - r0) > 1.5:
                    continue
                if abs(D.cell_x(c0) - z.x) <= 130:
                    tot += D.ASH_DMG
        except Exception:                                    # noqa: BLE001
            return 0.0
        return tot

    def track_need_after(self, name, until):
        """轨道在 `until` 之前还要用这张卡吗（收尾波动用轨道资源的检查）"""
        for e in self.events:
            if e.get('name') == name and self.t < e['t'] <= until:
                return True
        return False

    def _try_card(self, name):
        if self.card_ready.get(name, 0) > self.t:
            return False
        cost = D.CARDS[name]['cost']
        if self.sun < cost:
            return False
        self.sun -= cost
        self.card_ready[name] = self.t + D.CARDS[name]['cd']
        # wave 用 max(1, ...)：开局 t<1s 时 cur_wave 还是 0，会让按波统计漏掉
        self.actions.append(dict(t=self.t, wave=max(1, self.cur_wave),
                                 name=name, ok=True))
        return True

    def _plant_ice(self, ev, aim, name, stock_only=False, temp_only=False):
        """
        种寒冰菇（I / I′）—— v0.3 的统一写法。

        · 落点是**存冰位**（睡眠位）→ 就是"补存冰"：种下去不冻，留着以后用咖啡豆唤醒
        · 落点是普通格子 / 没给落点 → 当场种下即冻（冰卡本来的用法）
        · `stock_only` / `temp_only`：老动作名（种冰 / 种临时冰）走自动挑位，
          只为兼容 v0.2 及更早的阵解，新阵解请直接写落点。
        """
        card = '冰' if name == '寒冰菇' else '模仿冰'
        if self.card_ready.get(card, 0) > self.t:
            self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                    why='%s CD 没好' % card))
            return
        pos = None
        if aim in ('stock', 'temp'):
            stock_only = (aim == 'stock')
            temp_only = (aim == 'temp')
        elif isinstance(aim, (tuple, list)) and len(aim) == 2:
            pos = (int(aim[0]), int(aim[1]))
        if pos is None and (stock_only or temp_only):
            stock_rcs = [rc for rc, f in self.ice_slots.items() if not f]
            temp_rcs = [rc for rc, f in self.temp_ice.items() if not f]
            if stock_only and stock_rcs:
                chili = self._chili_slot()
                stock_rcs.sort(key=lambda rc: (rc == chili, rc[0], rc[1]))
                pos = stock_rcs[0]
                if pos == chili and len(stock_rcs) == 1:
                    cd = self.card_ready.get('辣椒', 0) - self.t
                    if cd <= D.CHILI_RESERVE_CS:
                        self.ice_refill_skip += 1
                        self._log('INFO', '5-3 暂不补存冰（留给辣椒）',
                                  row=pos[0], col=pos[1],
                                  detail='辣椒 CD 剩 %.1fs，等它打出去再补' % (cd / 100.0))
                        return
            elif temp_rcs:
                pos = temp_rcs[0]
            elif stock_rcs:
                pos = stock_rcs[0]
            if pos is None:
                # ★ 2026-10-22 夜场（FE / NE）：蘑菇种下就醒 → **没有"存冰"这回事**，
                #   所以夜场写"补存冰"是阵解本身写错了，要明确告诉用户。
                why = ('夜场没有存冰位（蘑菇种下就醒、蘑菇阵不能存冰/存核）'
                       if self.fld.night else '没有空着的存冰位')
                self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                        why=why))
                return

        is_stock = pos is not None and pos in self.ice_slots
        is_temp = pos is not None and pos in self.temp_ice
        if is_stock and self.ice_slots[pos]:
            self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                    why='%d-%d 已经有寒冰菇了' % pos))
            return
        if is_temp and self.temp_ice[pos]:
            self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                    why='%d-%d 已经有寒冰菇了' % pos))
            return
        if pos is not None and not (is_stock or is_temp):
            cell = self.cells.get(pos)
            if cell is not None and (cell.iced or cell.crater_until > self.t):
                self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                        why='落点 %d-%d 种不下（冰道/弹坑）' % pos))
                return

        self.sun -= D.CARDS[card]['cost']
        self.card_ready[card] = self.t + D.CARDS[card]['cd']
        self.actions.append(dict(t=self.t, wave=ev['wave'], name=name, ok=True,
                                 rc=pos))
        if is_stock:
            self.ice_slots[pos] = True
            self.ice_refill_n += 1
            self._log('REPAIR', '补存冰 %d-%d（%s · 现有 %d 个）'
                      % (pos[0], pos[1], card, self.ice_stock), row=pos[0], col=pos[1],
                      detail='种一格寒冰菇留着以后唤醒')
            return
        if is_temp:
            self.temp_ice[pos] = True
            self.ice_temp_n += 1
            self._log('REPAIR', '前场临时存冰 %d-%d（%s）' % (pos[0], pos[1], card),
                      row=pos[0], col=pos[1], detail='现有 %d 个' % self.ice_stock)
            return
        if pos is not None:
            cell = self.cells.get(pos)
            if cell is None:
                cell = self.cells[pos] = Cell(pos[0], pos[1])
            if not self._base_ok(pos):
                if not self._seed_base(pos):
                    self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                            why='%d-%d 缺基座（荷叶/花盆）' % pos))
                    return
            self._plant_into(cell, '寒冰菇')
            if self.fld.night:
                # ★ 夜场（FE/NE）：蘑菇种下就醒 → 立刻全场冰冻。
                #   结果导向：种植即生效，没有"睡一夜再点豆"这一步。
                self._log('ICE', '种寒冰菇（%s）→ 夜场种下即醒 · 全场冰冻'
                          % card, row=pos[0], col=pos[1],
                          detail='夜场蘑菇免唤醒；冰冻时长同白天')
                self._freeze()
                return
            # 白天：**新种下的蘑菇一定是睡着的** → 先睡下，再用咖啡豆唤醒
            self._log('ICE', '种寒冰菇（%s）→ 睡下了，要咖啡豆唤醒才冻'
                      % card, row=pos[0], col=pos[1],
                      detail='新种的蘑菇一律先睡；唤醒后永久清醒')
            return
        self._log('ICE', '种寒冰菇（%s）→ 全场冰冻' % card,
                  row=pos[0] if pos else None, col=pos[1] if pos else None)
        self._freeze()

    def _use_coffee(self, ev, aim):
        """
        种咖啡豆 → 唤醒那一格**睡着的蘑菇** → 若是寒冰菇则立刻全场冰冻。

        ★ v0.3 统一说法：以前这一步叫"点存冰"。
        ★ 2026-10-22：咖啡豆唤醒的是"所在格的蘑菇"，不止存冰位；
          用户口径是「已经唤醒的蘑菇永远醒着」→ 唤醒后 cell.awake 永久为 True。
          没给落点就自动挑：先前场临时位，再永久存冰位，最后任意睡着的蘑菇。
        """
        pos = None
        if isinstance(aim, (tuple, list)) and len(aim) == 2:
            pos = (int(aim[0]), int(aim[1]))
        if pos is None:
            cand = ([rc for rc, f in self.temp_ice.items() if f]
                    + sorted([rc for rc, f in self.ice_slots.items() if f],
                             key=lambda rc: (rc == self._chili_slot(), rc[0], rc[1])))
            if not cand:
                # 退一步：场上任意一格睡着的蘑菇
                cand = [rc for rc, c in self.cells.items()
                        if c.plant and not c.awake and c.plant in D.MUSHROOMS]
            if not cand:
                why = ('夜场蘑菇种下就醒，没有睡着的蘑菇要唤醒（夜场不需要咖啡豆）'
                       if self.fld.night else '场上没有睡着的蘑菇可唤醒')
                self.broken.append(dict(t=self.t, wave=ev['wave'], what='咖啡豆',
                                        why=why))
                self.actions.append(dict(t=self.t, wave=ev['wave'],
                                         name='咖啡豆', ok=False))
                return
            pos = cand[0]
        cell = self.cells.get(pos)
        sleep_cell = (cell is not None and cell.plant in D.MUSHROOMS
                      and not cell.awake)
        if not (self.ice_slots.get(pos) or self.temp_ice.get(pos) or sleep_cell):
            self.broken.append(dict(t=self.t, wave=ev['wave'], what='咖啡豆',
                                    why='%d-%d 上没有睡着的蘑菇' % pos))
            return
        if not self._try_card('咖啡豆'):
            self.broken.append(dict(t=self.t, wave=ev['wave'], what='咖啡豆',
                                    why='咖啡豆 CD 没好'))
            self.actions.append(dict(t=self.t, wave=ev['wave'],
                                     name='咖啡豆', ok=False))
            return
        self.activate_ice(pos)
        self.actions.append(dict(t=self.t, wave=ev['wave'], name='咖啡豆', ok=True))

    def do_action(self, ev):
        name, aim = ev['name'], ev['aim']
        name = _OP_ALIAS.get(name, name)      # 旧动作名 → 植物名（v0.3 之前存下的阵解也能跑）
        # ══ 冰系：统一成「种寒冰菇」（落点是存冰位 = 补存冰）／「种咖啡豆」（唤醒存冰）
        if name in ('种冰', '种冰2', '种临时冰'):
            # 老动作名（内置判定轨道还在用）：自动挑位，只为兼容
            return self._plant_ice(ev, None,
                                   '模仿寒冰菇' if name == '种冰2' else '寒冰菇',
                                   stock_only=(name != '种临时冰'),
                                   temp_only=(name == '种临时冰'))
        if name in ('寒冰菇', '模仿寒冰菇'):
            return self._plant_ice(ev, aim, name)
        if name == '咖啡豆':
            return self._use_coffee(ev, aim)
        # ★ 2026-10-22 用户口径：**P（玉米炮）不是"种卡"** —— 它不占卡片 CD、
        #   不花阳光，只看**每门炮自己的 3475cs 装填计时器**。
        #   所以必须排在下面的卡片 CD / 阳光检查之前。
        if name == '玉米炮':
            return self._fire_cob(ev, aim)
        # ★ 用户："w10 窝瓜压冰车" —— 这是**固定起手动作**，不是救场。
        #   压哪一行由"最靠前的冰车"决定（`_pick_row` 已经优先挑冰车所在行）。
        if name == '窝瓜压车':
            # ★ 用户 2026-10-20：一波内所有僵尸**同一时刻**刷出，没有"晚出生"这回事。
            #   所以这里只需要等"本波第一帧把僵尸真正放进场"（spawn 与 schedule
            #   在同一 tick 的先后顺序），1~2 次重排就够，不是 6s 等待。
            if self.card_ready.get('窝瓜', 0) > self.t:
                if getattr(self, '_wogua_retry', 0) < 12:
                    self._wogua_retry = getattr(self, '_wogua_retry', 0) + 1
                    self._schedule(self.t + 300, name, aim, ev['wave'],
                                    due=ev.get('due'), bid=ev.get('bid'))
                return
            cars5 = [z for z in self.zombies
                     if z.alive and z.kind == '冰车' and z.row == 5]
            if not cars5:
                if getattr(self, '_wogua_retry', 0) < 12:
                    self._wogua_retry = getattr(self, '_wogua_retry', 0) + 1
                    self._schedule(self.t + 150, name, aim, ev['wave'],
                                    due=ev.get('due'), bid=ev.get('bid'))
                else:
                    self._wogua_retry = 0
                    self._log('INFO', 'w10 没有 5 路冰车（窝瓜省下）')
                return
            self._wogua_retry = 0
            if not self._try_card('窝瓜'):
                return
            # 种在 5-9。判定域 = [640, 720]：
            #   车头（碾压判定）一进这个区间，车尾（冰道前沿，+80）还在 720~800，
            #   **9 列还没被铺** → 5-9 干净，w11 的核一定落得下去。
            self.wogua_pending = dict(row=5, col=9, until=self.t + D.WOGUA_HOLD)
            if self.actions:
                self.actions[-1]['rc'] = (5, 9)
            self._log('RESCUE', 'w10 窝瓜种在 5-9，等车头进格',
                      row=5, col=9,
                      detail='判定域 [640,720] · 车尾还差一格没铺 9 列')
            return

        # ★ 指定坑被冰道盖住 → **等一下**，别急着退坑。
        #   实测：w11 开场那一刻（199.7s）正好有辆 5 路冰车死掉，它的冰道
        #   会在同一帧清掉；核如果死板按"此刻有冰道就退"就白退了。
        #   玩家动作是"等冰化/等车死"，最多等一两秒。所以这里最多重排 8 次（1.2s）。
        if name in ('毁灭菇', '模仿毁灭菇') and isinstance(aim, (tuple, list)):
            rc = tuple(aim)
            cell = self.cells.get(rc)
            blocked = (cell is not None and cell.iced
                       and cell.crater_until <= self.t
                       and not self.temp_ice.get(rc))
            if blocked and getattr(self, '_nuke_retry', 0) < 8:
                self._nuke_retry = getattr(self, '_nuke_retry', 0) + 1
                self._schedule(self.t + 150, name, aim, ev['wave'],
                                due=ev.get('due'), bid=ev.get('bid'))
                return
            self._nuke_retry = 0

        # ★ 快速关 w9 长间隔施工："种大喷，优先 5-7 其次 2-7"
        #   作用是用**结构**替代操作：下半场放羊时，这两株大喷替 2/5 路补 IO。
        # ★★ 2026-10-24 修 bug：这里的**写死兜底 `[(5,7),(2,7)]`** 会把任何
        #   "没写落点的大喷"都种到 5-7 / 2-7 —— 包括**救场层**的资源。
        #   实测后果：FE.雾四炮 的救场资源 `{op: 大喷菇}` 每波都在 5-7/2-7 种一株，
        #   被啃/被碾 → 进补种队列 → 反复刷"损失"，还会干扰"冰车没吃到 P"的判断。
        #   → 只认**阵解显式配置**的 `slots.fast_fog`；没配就直接不种。
        if name == '大喷菇':
            pos = None
            if isinstance(aim, (tuple, list)) and len(aim) == 2:
                pos = (int(aim[0]), int(aim[1]))
            spots = [pos] if pos else list(self.slots.get('fast_fog') or [])
            if not spots:
                self._log('INFO', '大喷菇没有指定落点，也没有配置 fast_fog 槽位 → 不种',
                          detail='避免写死 5-7/2-7 污染阵型')
                return
            for rc in spots:
                cell = self.cells.get(rc)
                if cell is None:
                    cell = self.cells[rc] = Cell(rc[0], rc[1])
                if cell.plant is not None or cell.iced or cell.crater_until > self.t:
                    continue
                if not self._try_card('大喷菇'):
                    return
                self._plant_into(cell, '大喷菇')
                self.actions.append(dict(t=self.t, wave=ev['wave'], name=name, ok=True))
                self._log('REPAIR', '长间隔补种大喷 %d-%d' % rc, row=rc[0], col=rc[1],
                          detail='下半场靠结构替代操作')
                return
            return

        # ★ 2026-10-22：阵解里的垫材是**机会性**的 —— 窗口没开 / 卡没好 / 格子被占
        #   都只是"这次没垫上"，**不算断轨**（用户：垫材的死亡不该反复报 L2，
        #   同理它的失败也不该刷断裂）。永远静默跳过。
        if name in D.PAD_OF_PLANT:
            card = D.PAD_OF_PLANT[name]
            if isinstance(aim, (tuple, list)) and len(aim) == 2:
                if self.stall_at(aim, cards=(card,)):
                    self.actions.append(dict(t=self.t, wave=ev['wave'], name=name, ok=True))
                return
            rows = [aim[0]] if isinstance(aim, (tuple, list)) and aim else None
            if self.try_stall(rows, cards=(card,)):
                self.actions.append(dict(t=self.t, wave=ev['wave'], name=name, ok=True))
            return

        card = _CARD_OF.get(name, name)
        if card not in D.CARDS:
            self.broken.append(dict(t=self.t, wave=ev['wave'], what=name, why='未知卡片'))
            return
        if self.card_ready.get(card, 0) > self.t:
            self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                    why='CD 没好（剩 %d cs）' % (self.card_ready[card] - self.t)))
            self.actions.append(dict(t=self.t, wave=ev['wave'], name=name, ok=False))
            return
        cost = D.CARDS[card]['cost']
        if self.sun < cost:
            self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                    why='阳光不够（差 %d）' % (cost - self.sun)))
            self.actions.append(dict(t=self.t, wave=ev['wave'], name=name, ok=False))
            return
        self.sun -= cost
        self.card_ready[card] = self.t + D.CARDS[card]['cd']
        self.actions.append(dict(t=self.t, wave=ev['wave'], name=name, ok=True))

        if name in ('毁灭菇', '模仿毁灭菇'):
            self._doom(aim)
            return
        if name == '樱桃':
            # ★ 2026-10-22：`[行, "front"]` = 滑列落点（**连同相邻行一起判**，
            #   因为樱桃 R=115 纵向也盖 3 行）；圆心口径 [精 六] = (x+40, y+40)
            # ★★ 2026-10-23：同样走 `lookahead.best_aim()` 的"预演-回溯"搜索
            #   （灰烬的落点是用户**没有定死**的灵活操作之一）。
            slide = (isinstance(aim, (list, tuple)) and len(aim) == 2
                     and isinstance(aim[1], str))
            if isinstance(aim, (list, tuple)) and len(aim) == 2:
                r = int(round(float(aim[0])))
                if slide:
                    from tools.trackcheck import lookahead as LA
                    tabs = {rr: LA.dps_by_cell(self, rr)
                            for rr in self._boom_rows(r, D.CHERRY_R, 40)}
                    got = LA.best_aim(self, r, D.CHERRY_R, 40, D.ASH_DMG,
                                      integer=True, tables=tabs)
                    c = int(got) if got is not None else \
                        int(self._slide_col(r, D.CHERRY_R, 40, -40, integer=True))
                else:
                    c = int(round(float(aim[1])))
            else:
                r = self.slots.get('cherry_row') or self._pick_row()
                cols = list(getattr(self, 'cherry_cols', None) or [8, 9, 7, 6])
                c = None
                # ★ 先看"滑到哪一列才真的盖得住最靠前那只"（多行口径），
                #   那一列能下就优先用它；不行再退回固定的 8/9/7/6 偏好。
                want = self._slide_col(r, D.CHERRY_R, 40, -40, integer=True)
                cand_list = [int(want)] + [x for x in cols if x != int(want)]
                for cand in cand_list:
                    cell_c = self.cells.get((r, cand))
                    if cell_c is None or not cell_c.iced:
                        c = cand
                        break
                if c is None:
                    c = cols[0]
            cell = self.cells.get((r, c))
            if cell is not None and cell.iced:
                self.broken.append(dict(t=self.t, wave=ev['wave'], what=name,
                                        why='落点 %d-%d 有冰道，种不下' % (r, c)))
                return
            self._boom(r, c, D.CHERRY_R, D.ASH_DMG)
            if self.actions:
                self.actions[-1]['rc'] = (r, c)
            return
        if name == '辣椒':
            r = (self.slots.get('chili_slot') or (self._pick_row(), 0))[0]
            # ★ 用户：5-3 存冰位如果这一波要复用辣椒，辣椒用了再补存冰。
            #   执行顺序就是：先把这个位置上的存冰点掉（顺带冻一次），
            #   腾出格子种辣椒；下一波再补存冰。
            chili = self._chili_slot()
            if chili and self.ice_slots.get(chili):
                self.ice_slots[chili] = False
                self._freeze()
                self.ice_chili_reuse += 1
                self._log('ICE', '5-3 存冰复用为辣椒位：先点冰，再种辣椒',
                          row=chili[0], col=chili[1],
                          detail='下一波（冰卡转好后）再补回存冰')
            self.chili_q.append((self.t + D.ASH_DELAY, r))
            for col in range(1, 10):
                cc = self.cells.get((r, col))
                if cc is not None:
                    cc.ash_pending = True
            if self.actions:
                self.actions[-1]['rc'] = (r, 5)
            return
        if name == '窝瓜':
            # ★ v0.3：给了落点就种在那格（"窝瓜压车"就退化成"在 5-9 种窝瓜"）
            if isinstance(aim, (tuple, list)) and len(aim) == 2:
                self._ash_cell(int(aim[0]), int(aim[1]), D.ASH_DMG)
                if self.actions:
                    self.actions[-1]['rc'] = (int(aim[0]), int(aim[1]))
                return
            r = self._pick_row()
            cand = [z for z in self.zombies if z.alive and z.row == r]
            if cand:
                # 种在"最靠前那只"所在的格 → 1 格宽判定域即刻生效，
                # 同格里的其他僵尸（同路重合的车/叠在一起的怪）一起吃 1800。
                t = min(cand, key=lambda z: z.x)
                col = max(1, min(9, int(round((t.x - 40) / 80.0)) + 1))
                self._ash_cell(r, col, D.ASH_DMG)
                if self.actions:
                    self.actions[-1]['rc'] = (r, col)
            return

        # ══════════════════════════════════════════════════════════════
        # v0.2.1 新增的植物动作
        # ══════════════════════════════════════════════════════════════
        if name == '三叶草':
            return self._blover(ev)
        if name == '墓碑吞噬者':
            return self._grave_eat(ev, aim)

    def _aim_py(self, row, col):
        """落点所在行的**植物 y**（允许小数行 → 相邻两行线性插值）

        ★ 2026-10-22 用户口径：P 的落点"允许行列坐标带一位小数"。
          行 1.5 = 1 路与 2 路正中；屋顶逐格给 y，所以列也要参与。
        """
        c = int(round(float(col)))
        c = max(1, min(9, c))
        r = float(row)
        r0 = int(r)
        frac = r - r0
        rows = sorted(self.fld.all_rows())
        if not rows:
            return D.plant_y(r0)
        r0 = max(rows[0], min(rows[-1], r0))
        nxt = r0 + 1 if r0 + 1 in rows else r0
        y0 = self.py(r0, c)
        y1 = self.py(nxt, c)
        return y0 + (y1 - y0) * frac

    def _cob_tail_col(self, row, radius, dy):
        """**尾炸落点**（`aim = [行, "tail"]`）：炸已落地、还没开始啃植物的小鬼

        与「分离炮动态落点」同一个扫法，只是目标换成 `imp_fly` 里 `ground=True` 的。
        返回列号；没有可炸的落地小鬼 → None。
        """
        rows = set(self._boom_rows(row, radius, dy))
        tg = [i for i in self.imp_fly
              if not i.get('killed') and i.get('ground') and i['row'] in rows]
        if not tg:
            return None
        lo = min(i['x'] for i in tg) - D.IMP_BOX
        hi = max(i['x'] for i in tg) + D.IMP_BOX
        cx_lo, cx_hi = D.cell_x(1), D.cell_x(9)
        best, best_n = None, -1
        cx = lo - radius
        while cx <= hi + radius:
            if cx_lo <= cx <= cx_hi:
                got = sum(1 for i in tg if abs(i['x'] - cx) <= radius)
                if got > best_n:
                    best, best_n = cx, got
            cx += 1.0
        if best is None:
            return None
        col = (best - 40.0) / float(D.CELL_W) + 1.0
        return max(1.0, min(9.0, round(col, 1)))

    def _cob_dyn_col(self, row, kinds, radius, dy):
        """**分离炮动态落点**（`aim = [行, "dyn"]`）：在列上滑动，找能全覆盖的那一点。

        口径（用户 2026-10-24）：
          · 只看**这一波新刷新的**、**kind 命中 `kinds` 的**僵尸；
          · 只看这个落点**纵向盖得到的那几行**（`_boom_rows`：本行 + 相邻行）；
          · 在列上滑动，目标是让它们**全部**落进爆炸圆（与受击框重合即吃满 1800）。

        返回 `(状态, 列号)`：
          `('none', None)` 本波根本没有这种僵尸 → 这一发不该打（省炮 + 省 3475cs）
          `('wait', None)` 有这种僵尸，但**还没走进炮的火力范围**（x 太大）→ 等它走近
          `('fire', col)`  找到列号（1~9，一位小数）
        """
        if not kinds:
            return ('none', None)
        rows = set(self._boom_rows(row, radius, dy))
        wave = self.cur_wave
        tg = [z for z in self.zombies
              if z.alive and z.row in rows and z.kind in kinds
              and (wave is None or z.wave == wave)]
        if not tg:
            return ('none', None)
        box = [(z, D.DEFENSE_BOX.get(z.kind, D.DEFENSE_BOX['默认'])) for z in tg]
        lo = min(z.x - b[0] for z, b in box)
        hi = max(z.x + b[1] for z, b in box)
        # 炮能打到的爆心范围：第 1 列 ~ 第 9 列
        cx_lo, cx_hi = D.cell_x(1), D.cell_x(9)
        mid = (lo + hi) / 2.0
        # 候选爆心：从"最靠左那只的左边"扫到"最靠右那只的右边"，步长 1px
        best, best_n, best_c = None, -1, None
        cx = lo - radius
        while cx <= hi + radius:
            if cx_lo <= cx <= cx_hi:
                got, miss = 0, []
                for z, b in box:
                    if (z.x - b[0]) - cx <= radius and (cx - (z.x + b[1])) <= radius:
                        got += 1
                    else:
                        miss.append(z)
                if got > best_n or (got == best_n and best is not None
                                    and abs(cx - mid) < abs(best - mid)):
                    best, best_n, best_c = cx, got, miss
            cx += 1.0
        if best is None:
            # 一个可用爆心都没有 → 目标还在炮的射程外
            return ('wait', None)
        # 漏掉的那些如果只是"还在炮口右边、还没走进来"，就别急着放这一发 ——
        # 等它走进来就能全覆盖（不然就白炸一半）
        if best_c and any((z.x - b[0]) - best > radius and z.x > cx_hi
                          for z, b in box if z in best_c):
            return ('wait', None)
        if best_c:
            self._log('WARN', '分离炮（动态落点）：%d 路还有 %d 只没盖到（本波目标 %d 只）'
                      % (int(round(row)), len(best_c), len(tg)),
                      row=int(round(row)),
                      detail='张得太开（或已经在炮口内侧），一门炮盖不全；'
                             '已取覆盖最多的那一点')
        col = (best - 40.0) / float(D.CELL_W) + 1.0
        return ('fire', max(1.0, min(9.0, round(col, 1))))

    def _boom_rows(self, row, radius, dy):
        """这个落点**纵向**能盖到哪几行（圆心 y = 该行植物 y + dy，与受击框最近点距 ≤ R）"""
        cy = self._aim_py(row, 1) + dy
        out = []
        for r in self._rows():
            zy = self.zy(r)
            ny = zy if cy < zy else (zy + D.DEF_HEIGHT if cy > zy + D.DEF_HEIGHT else cy)
            if abs(ny - cy) <= radius:
                out.append(r)
        return out

    def _targetable(self, z):
        """这只现在**能被植物选为目标 / 用作瞄点**吗？

        ★ 2026-10-24：矿工在地下时既打不到也看不见 —— 必须把它排除在
          "最靠前那只 / 选目标 / 炮的瞄点"之外。否则它挖到 x=20 一蹲，
          会把所有单目标伤害和炮的落点全吸走（实测经典八炮 15/20 → 4/20，
          红眼趁机啃掉 1-5 / 6-5 的玉米炮）。
        """
        return not (z.kind == '矿工' and getattr(z, 'phase', '') == 'dig')

    def _slide_col(self, row, radius=None, dy=None, head_dx=None, integer=False,
                   threat=False, allow_none=False):
        """**滑列落点**（用户 2026-10-22）：不写死第几列，而是让判定域
        "最靠前的那只僵尸"**恰好**被切到，剩下的距离全留给后面的怪。

        ★★ 用户 2026-10-22 修正：**要连同相邻行一起判**。
          炮的圆 R=115 纵向能盖 3~4 行、樱桃 R=115 也能盖 3 行，
          所以"最靠前"必须取**被这一炮盖到的所有行**里最靠前的那只，
          不是只看准星那一行。

        ★ `threat=True`：**先挑会造成不可逆损失的**（冰车 / 投篮车 / 巨人），
          没有才退回"最靠前那只"。原因：一炮横盖 3 行时，"最靠前"常常是
          已经被减速、还有时间处理的那只，而刚刷出来、正往阵里冲的冰车会被漏掉
          —— 冰车免疫减速、不被南瓜阻挡，漏一次就是碾掉一整格植物。
          （实测 FE.雾四炮：边路的冰车一路碾到 3 列，就是因为滑列滑到了更深的那只。）

        反解 `爆心 x = cell_x(col) − head_dx`：
            cx = 最靠前那只受击框的**右缘** + R − 1   ← 圆的最右位置，刚好切到它
            col = (cx − base) / 80 + 1
        `integer=True` 时取整列（樱桃/辣椒这类要种在格子里的）。
        """
        spec = D.PLANTS['玉米炮']['cob']
        r_ = spec['radius'] if radius is None else radius
        dy_ = spec['dy'] if dy is None else dy
        hx = spec['head_dx'] if head_dx is None else head_dx
        base = D.cell_x(1) - hx                     # col=1 时的爆心 x
        rows = self._boom_rows(row, r_, dy_)
        zs = [z for r in rows for z in self.by_row.get(r, ())
              if z.alive and z.hp > 0 and self._dbox(z)[0] <= D.DMG_LINE
              and self._targetable(z)]
        if not zs:
            # ★ 没有"可伤"的僵尸（新刷的还在 800 以外，`可伤条件 = 防御域左端 ≤ 800`）
            #   → 滑列落点算不出列。`allow_none=True` 时返回 None，让调用方**等一等**
            #   （别对着空气开炮：这一炮会打空，而且白进 3475cs 装填）。
            return None if allow_none else 8.0
        def _covers(z, cx0, cy0):
            zl, zr = self._dbox(z)
            zy = self.zy(z.row)
            nx = zl if cx0 < zl else (zr if cx0 > zr else cx0)
            ny = zy if cy0 < zy else (
                zy + D.DEF_HEIGHT if cy0 > zy + D.DEF_HEIGHT else cy0)
            return (nx - cx0) ** 2 + (ny - cy0) ** 2 <= r_ * r_

        def _score(cx0, cy0):
            n_threat = 0
            sc = 0.0
            for z in zs:
                if not _covers(z, cx0, cy0):
                    continue
                if z.kind in ('冰车', '投篮') or z.giant:
                    n_threat += 1
                    sc += 3.0
                else:
                    sc += 1.0
            return n_threat, sc

        if threat:
            # ★★ 2026-10-23 用户：「P、N 的范围足够；巨人、冰车受击判定域大，一定炸的到」
            #   → 以前这里只按"最靠前的那只"反解列，而且公式用 R 而不是
            #     `sqrt(R² − dy²)`，跨行时**差 5~10px 就漏掉一整辆冰车**。
            #   现在直接枚举候选列，用真实的圆-受击框距离算覆盖：
            #   先比"覆盖到的硬目标数"，再比总收益。
            step = 1.0 if integer else 0.1
            best, best_key = None, None
            n = int(round((9.0 - 1.0) / step))
            for i in range(n + 1):
                col0 = 1.0 + i * step
                cx0 = base + (col0 - 1.0) * D.CELL_W
                cy0 = self._aim_py(row, col0) + dy_
                nt, sc = _score(cx0, cy0)
                key = (nt, sc)
                # 覆盖相同时取更靠右（爆炸中心更靠近阵内 → 更安全）
                if best_key is None or key > best_key or (
                        key == best_key and col0 > best):
                    best, best_key = col0, key
            if best is not None:
                return float(round(best)) if integer else round(best, 1)
        front = min(zs, key=lambda z: z.x)
        _zl, zr = self._dbox(front)
        # 跨行时圆心到受击框有纵向距离 dy，水平可用半径只有 sqrt(R² − dy²)
        cy = self._aim_py(row, 1) + dy_
        zy = self.zy(front.row)
        ny = zy if cy < zy else (zy + D.DEF_HEIGHT if cy > zy + D.DEF_HEIGHT else cy)
        reach = (max(0.0, r_ * r_ - (ny - cy) ** 2)) ** 0.5
        cx = zr + reach - 1.0                      # −1：别卡在浮点边界上
        col = (cx - base) / float(D.CELL_W) + 1.0
        col = max(1.0, min(9.0, col))
        return float(round(col)) if integer else round(col, 1)

    def _fire_cob(self, ev, aim):
        """玉米炮开炮。`aim=(row, col)` 是**准星落点**（可以在任意行，可带小数）。

        [精 三] 释放到完成装填（CD）3475
        [精 八] 爆炸半径 R=115、伤害 1800；爆炸中心 x = 准星 x − 7、
                y = 落点行的植物 y + 40（非天台）

        ★ 2026-10-22 用户口径（P 操作）：
          · **不指定具体哪一门炮** —— 自动挑「装填好了、剩余 CD 最短」的那门，
            每门炮各自有 3475cs 的独立计时器
          · **忽略「释放→爆炸」时延**：写下的那一刻就结算爆炸（`COB_IGNORE_FUSE`）
          · 落点行列都允许一位小数；爆炸判定域是 R=115 的圆，
            与僵尸**受击框**有重合就吃满 1800
        """
        spec = D.PLANTS['玉米炮']['cob']
        cobs = [c for c in self.cells.values()
                if c.plant == '玉米炮' and c.plant_hp > 0]
        # ══ ★ 2026-10-25 铲种炮（p）：铲掉再种回来**刷新冷却**
        #   真实做法：铲掉那门炮 → 种回玉米投手 → 再升成炮（新种的炮是**满装填**的）。
        #   模型里按**结果导向**简化：
        #     · 要求选卡里同时有 `玉米投手` 和 `玉米炮`（"炮套件"）
        #     · 用**玉米炮卡**的 CD 当闸门（不是每门炮的 3475cs）
        #     · 花 100（玉米投手）+ 500（炮）阳光
        #     · 不计铲/种动画时延（与"P 不计释放时延"同一个口径）
        if (ev or {}).get('cob') == 'p':
            deck = set(self.deck_names or ())
            if not {'玉米投手', '玉米炮'} <= deck:
                self.broken.append(dict(t=self.t, wave=ev['wave'], what='铲种炮',
                                        why='选卡里没有炮套件（玉米投手 + 玉米炮）'))
                self.actions.append(dict(t=self.t, wave=ev.get('wave') or 1,
                                         name='铲种炮', ok=False))
                return
            if not cobs:
                self.broken.append(dict(t=self.t, wave=ev['wave'], what='铲种炮',
                                        why='场上没有玉米炮可铲'))
                return
            # ★ 2026-10-25 用户给的精确口径：
            #   阳光 = 2×玉米(100) + 炮(500 + 50n)，n = 场上当前玉米炮数量
            cost = (D.COB_SHOVEL_CORN * D.COB_SHOVEL_CORN_N
                    + D.COB_SHOVEL_BASE + D.COB_SHOVEL_PREMIUM * len(cobs))
            # 闸门 = 炮卡的 50s CD
            cd = self.card_ready.get('玉米炮', 0)
            if cd > self.t or self.sun < cost:
                n = getattr(self, '_cob_cd_wait', 0)
                if n < 24:
                    self._cob_cd_wait = n + 1
                    self._schedule(self.t + 100, '玉米炮', aim, ev.get('wave'),
                                   due=ev.get('due'), bid=ev.get('bid'),
                                   extra={'cob': 'p'})
                    return
                self._cob_cd_wait = 0
                self.broken.append(dict(
                    t=self.t, wave=ev['wave'], what='铲种炮',
                    why='炮卡没好（%d cs）或阳光不够（%d < %d）'
                        % (cd - self.t, self.sun, cost)))
                return
            self._cob_cd_wait = 0
            self.sun -= cost
            self.card_ready['玉米炮'] = self.t + D.COB_SHOVEL_CARD_CD
            gun = min(cobs, key=lambda c: c.cob_cd)
            gun.cob_cd = self.t + spec['cd']      # 新种的炮从满装填开始
            ready = [gun]
        else:
            if not cobs:
                self.broken.append(dict(t=self.t, wave=ev['wave'], what='玉米炮',
                                        why='场上没有玉米炮'))
                self.actions.append(dict(t=self.t, wave=ev.get('wave') or 1,
                                         name='玉米炮', ok=False))
                return
            ready = [c for c in cobs if c.cob_cd <= self.t]
        if not ready:
            # ★ 2026-10-23（用户报的 bug）：**不要因为"一时没装填好"就判轨道断裂**。
            #   真实玩家写的是"9s 一对炮"，如果这一拍恰好赶上 4 门炮都在装填，
            #   他会**等一两秒**再打，而不是把这一发作废。
            #   （之前的表现：经典八炮 w20 一刷新就报两条"所有炮都在装填"）
            n = getattr(self, '_cob_cd_wait', 0)
            if n < 24:                        # 最多等 2.4s
                self._cob_cd_wait = n + 1
                self._schedule(self.t + 100, '玉米炮', aim, ev.get('wave'),
                                due=ev.get('due'), bid=ev.get('bid'))
                return
            self._cob_cd_wait = 0
            self.broken.append(dict(t=self.t, wave=ev['wave'], what='玉米炮',
                                    why='所有炮都在装填（最早 %d cs 后）'
                                        % (min(c.cob_cd for c in cobs) - self.t)))
            self.actions.append(dict(t=self.t, wave=ev.get('wave') or 1,
                                     name='玉米炮', ok=False))
            return
        self._cob_cd_wait = 0
        if isinstance(aim, (tuple, list)) and len(aim) == 2 and aim[1] == 'imp':
            # ★ 2026-10-24 拦截炮（D）：**动态落点** —— 不写死第几列，而是
            #   "结果必须保证炸死所有被巨人抛出、正在空中飞的小鬼"。
            #   炸心取在**当前这群小鬼的重心**上（同一路时就是那一只）。
            grp = ev.get('imp_group') or 'low'
            imps = [i for i in self.imp_fly
                    if not i.get('killed')
                    and (grp == 'any' or _imp_group(i['row'], self.rows) == grp)]
            if imps:
                i0 = min(imps, key=lambda i: abs(i['x'] - D.DMG_LINE))
                row = float(i0['row'])
                col = max(1.0, min(9.0, (i0['x'] - 40) / 80.0 + 1))
            else:
                # 没有在飞的小鬼（比如巨人已经被打死）→ 打这一组的中路，别空放
                row = float(aim[0] or (2 if grp == 'low' else 5))
                zs = [z for z in self.by_row.get(int(row), ()) if z.alive]
                col = (max(1.0, min(9.0, (min(z.x for z in zs) - 40) / 80.0 + 1))
                       if zs else 8.0)
        elif isinstance(aim, (tuple, list)) and len(aim) == 2:
            row = float(aim[0])
            # ★ 滑列落点：`[行, "front"]` / `[行, "threat"]`
            #   ★★ 2026-10-23 用户：**必须带"预演-回溯"**——
            #   "如果可以估算最靠前的怪是否在破坏 core 之前被 io 打死，则可以不管，
            #     否则必须炸到"。所以这里不再用固定公式反解列，而是
            #     `lookahead.best_aim()`：枚举候选爆心 → 每个候选做一次推演 → 取最优。
            if isinstance(aim[1], str) and aim[1] == 'tail':
                # ★ 2026-10-25 尾炸炮（d）：炸**已经落地、还没开始啃植物**的小鬼。
                #   落点用它们的地面坐标，行取用户给的行 + 纵向盖得到的那几行。
                spec0 = D.PLANTS['玉米炮']['cob']
                col = self._cob_tail_col(row, spec0['radius'], spec0['dy'])
                if col is None:
                    n = getattr(self, '_cob_wait', 0)
                    if n < 6:
                        self._cob_wait = n + 1
                        self._schedule(self.t + 50, '玉米炮', aim, ev.get('wave'),
                                       due=ev.get('due'), bid=ev.get('bid'),
                                       extra={k: ev.get(k) for k in
                                              ('cob', 'imp_group', 'imp_when',
                                               'dyn_kinds') if ev.get(k)})
                        return
                    self._cob_wait = 0
                    self._log('INFO', '尾炸炮（d）：没有刚落地的空中小鬼 → 这一发跳过',
                              row=int(round(row)))
                    return
                self._cob_wait = 0
            elif isinstance(aim[1], str) and aim[1] == 'dyn':
                # ★ 2026-10-24 用户：「分离炮动态落点」——
                #   炮落到这一行，**在列上滑动**，保证"这一路和相邻路上的、
                #   这一波新刷新的、被选中的那几种僵尸"全部被炸死。
                spec0 = D.PLANTS['玉米炮']['cob']
                st, col = self._cob_dyn_col(row, (ev or {}).get('dyn_kinds') or [],
                                            spec0['radius'], spec0['dy'])
                if st != 'fire':
                    n = getattr(self, '_cob_wait', 0)
                    # 'none' 只给 0.3s 宽限（同一个 tick 里刷怪）；
                    # 'wait' 最多等 2s，等它走进炮的火力范围
                    limit = 6 if st == 'none' else 40
                    if n < limit:
                        self._cob_wait = n + 1
                        self._schedule(self.t + 50, '玉米炮', aim,
                                       ev.get('wave'), due=ev.get('due'),
                                       bid=ev.get('bid'),
                                       extra={k: ev.get(k) for k in
                                              ('cob', 'imp_group', 'imp_when',
                                               'dyn_kinds') if ev.get(k)})
                        return
                    # ★ 2026-10-24：等完还是没有目标 → **这一发直接不打**
                    #   （"分离炮动态落点"是"专门打某几种僵尸"用的；
                    #     本波没出这种僵尸就不该白搭一发炮 + 3475cs 装填）
                    self._cob_wait = 0
                    self._log('INFO',
                              '分离炮（动态落点）：本波没有目标僵尸 → 这一发跳过',
                              row=int(round(row)),
                              detail='种类：%s' % '、'.join(ev.get('dyn_kinds') or []))
                    return
                self._cob_wait = 0
            elif isinstance(aim[1], str):
                from tools.trackcheck import lookahead as LA
                spec0 = D.PLANTS['玉米炮']['cob']
                tabs = {r: LA.dps_by_cell(self, r)
                        for r in self._boom_rows(row, spec0['radius'], spec0['dy'])}
                col = LA.best_aim(self, row, spec0['radius'], spec0['dy'],
                                  spec0['dmg'], tables=tabs)
                # ★ 场上还没有"可伤"的僵尸 → **等**（玩家不会对着空气开炮）。
                #   刚刷出来的僵尸在 800 以外，`dbox` 还没进可伤区；
                #   这时开炮这一发就是白的，而且白搭 3475cs 装填。
                # ★★ 2026-10-24：**最多等 0.3s**。
                #   固定波长的阵"运算量必须定时"，等 2s 等于把这一拍整体推迟 2s
                #   —— 实测经典八炮的炮间隔被拖成 2845/905/2835/905，
                #   红眼就从这些空窗里把 1-5 / 6-5 的玉米炮啃了（15/20 → 4/20）。
                #   0.3s 足够覆盖"僵尸刚出生在 800 之外"的窗口，又不会破坏节奏。
                if col is None:
                    n = getattr(self, '_cob_wait', 0)
                    if n < 6:
                        self._cob_wait = n + 1
                        self._schedule(self.t + 50, '玉米炮', aim, ev.get('wave'),
                                       due=ev.get('due'), bid=ev.get('bid'))
                        return
                    self._cob_wait = 0
                    col = 8.0
                else:
                    self._cob_wait = 0
            else:
                col = float(aim[1])
        else:
            row = float(self._pick_row())
            zs = [z for z in self.by_row[int(row)] if z.alive]
            col = (max(1.0, min(9.0, (min(z.x for z in zs) - 40) / 80.0 + 1))
                   if zs else 8.0)
        if self.fld.family == 'roof':
            fuse = sum(spec['fuse_roof']) / 2.0
        elif int(round(row)) in self.fld.water:
            fuse = spec['fuse']
        else:
            fuse = sum(spec['fuse_land']) / 2.0
        if D.COB_IGNORE_FUSE:
            fuse = 0
        # 占一个装填位（按剩余 CD 最短的那门炮）
        # ★ 2026-10-25：**落点没有射程限制** —— 玉米炮是"点哪打哪"的迫击炮，
        #   准星可以移到草坪上任意一格（1-1 的炮打 9 列完全合法）。
        #   （曾一度误加过"±1.44 格射程"约束，已撤销：那是把 R=115 的爆炸半径
        #    错当成了瞄准限制。）
        # ★★ 2026-10-25 **bug**：这里必须把"等了多久"的计数器归零。
        #   原来只有"放弃"分支才归零，成功开炮时**残留**下来；每波攒 1~3，
        #   攒到 24（上限）之后**每一拍都直接放弃** —— PE.二十四炮 打到
        #   w10 就彻底不开炮（僵尸走进来把 2-7 的炮啃了），就是这么来的。
        self._cob_cd_wait = 0
        gun = min(ready, key=lambda c: c.cob_cd)
        gun.cob_cd = self.t + spec['cd']
        self.cob_shot.append(dict(t=self.t, row=row, col=col,
                                  gun=(gun.row, gun.col)))
        cx = D.cell_x(col) - spec['head_dx']
        cy = self._aim_py(row, col) + spec['dy']
        self.boom_q.append((self.t + fuse, row, col, spec['radius'], spec['dmg'],
                            spec['dy'], (cx, cy)))
        self.actions.append(dict(t=self.t, wave=ev.get('wave') or 1,
                                 name='玉米炮', ok=True, rc=(row, col)))
        # ★ 2026-10-22：炮阵的蹦极靠"炮炸"救 —— 爆炸判定域盖到目标格就算救下
        self._bungee_mark('cob', center=(cx, cy))
        # ★ 2026-10-24：拦截炮 —— 爆炸判定域盖到空中的小鬼就炸死它
        if self.imp_active:
            self._imp_kill(cx, cy, spec['radius'])
        self._log('ASH', '玉米炮开炮 → %s-%s（%s）'
                  % (_num(row), _num(col),
                     '即刻爆' if fuse == 0 else '%.0f cs 后爆' % fuse),
                  row=int(round(row)), col=int(round(col)),
                  detail='R=%d · 1800 · 爆心 x=%.1f y=%.1f · 第 %d-%d 门炮'
                         % (spec['radius'], cx, cy, gun.row, gun.col))

    def _tick_imp(self):
        """小鬼投掷 / 落地（★ 2026-10-24：**只有阵解里出现拦截炮 D 时才启用**）

        简化模型（见 `data.IMP_*`）：
          · 巨人血量首次 ≤ 50% 时投出小鬼（图鉴口径），只投一次
          · 小鬼沿抛物线飞 `IMP_FLIGHT_CS`，落点在巨人前方 `IMP_LAND_GAP_PX`
          · 拦截炮在三个窗口之一把它炸掉（`_fire_cob` 里判）；漏了就在落点
            按"并入本波血量、由该路 dps 清掉"处理（与旧的期望型口径一致）
        """
        if not self.imp_active:
            return
        for z in self.zombies:
            if not z.alive or not z.giant or z.imp_out:
                continue
            if z.hp > z.hp0 * D.IMP_THROW_HP_RATIO:
                continue
            z.imp_out = True
            lo, hi = D.imp_landing(z.x, self.fld.family)
            land_x = self.rng.uniform(lo, hi)
            T = self.rng.uniform(*D.IMP_FLIGHT_CS)
            self.imp_fly.append(dict(
                row=z.row, t0=self.t, t1=self.t + T, T=T,
                x0=z.x - D.IMP_RELEASE_DX, x1=land_x, x=z.x,
                h=D.IMP_RELEASE_DY,
                v0=(0.5 * D.IMP_G * T * T - D.IMP_RELEASE_DY) / T,
                killed=False, wave=z.wave, from_kind=z.kind))
            self._log('INFO', '%s 投出小鬼（%d 路，落点 x=%.0f，滞空 %.0fcs）'
                      % (z.kind, z.row, land_x, T), row=z.row,
                      detail='血量 %.0f / %.0f ≤ 50%%' % (z.hp, z.hp0))
        keep = []
        for i in self.imp_fly:
            dt = self.t - i['t0']
            p = min(1.0, max(0.0, dt / float(max(1, i['T']))))
            i['x'] = i['x0'] + (i['x1'] - i['x0']) * p
            i['h'] = max(0.0, D.IMP_RELEASE_DY + i['v0'] * dt
                         - 0.5 * D.IMP_G * dt * dt)
            if i.get('killed'):
                continue
            if self.t >= i['t1']:
                if i.get('ground'):
                    # 已经落地过：交给下面"地面窗口"那段处理
                    keep.append(i)
                    continue
                # 落地：★ 2026-10-25 给一个短暂的地面窗口（尾炸炮 d 能在这个窗口里炸掉它），
                #   窗口过了才并入本波血量（= 老口径，后场由 IO 负责）。
                i['land_t'] = self.t
                i['h'] = 0.0
                i['ground'] = True
                self.imp_log.append(dict(wave=i['wave'], row=i['row'],
                                         res='landed', t=self.t,
                                         x=round(i['x'])))
                self._log('INFO', '小鬼落地 %d 路 x=%.0f'
                          % (i['row'], i['x']), row=i['row'],
                          detail='地面窗口 %dcs（尾炸炮打得到），之后并入本波血量'
                                 % D.IMP_GROUND_CS)
                keep.append(i)
                continue
            keep.append(i)
        # 地面窗口结束 → 并入本波血量
        still = []
        for i in keep:
            if not i.get('ground'):
                still.append(i)
                continue
            if self.t - i.get('land_t', self.t) < D.IMP_GROUND_CS:
                still.append(i)
                continue
            m = self.wave_meta
            if m is not None:
                m['skip_hp'] += D.ZOMB['小鬼'][0]
                m['skips'].append([float(D.ZOMB['小鬼'][0]),
                                   D.SKIP_DPS.get(i['row'], 150.0)])
            self.imp_log.append(dict(wave=i['wave'], row=i['row'],
                                     res='merged', t=self.t,
                                     x=round(i['x'])))
        self.imp_fly = still

    def _imp_kill(self, cx, cy, radius):
        """炮的爆炸判定域盖到空中的小鬼 → 炸死（拦截成功）

        ★ 2026-10-24 用户澄清：这个游戏**没有 z 轴**，小鬼飞行时的高度**就映射在 y 轴上**
        （可以理解为"行轴"与"高度轴"复用同一个 y；y 在变，但小鬼最终落点不换行）。
        所以爆炸域和小鬼在**同一个二维坐标系**里，判定就是二维的：
          · 横向 `|小鬼x − 爆心x| ≤ R`
          · 纵向 小鬼的 y（= 该行 y − 离地高度）要落在爆心 y 的 ±R 范围内
        换算成"可达高度"就是 `R + IMP_BOX`：
        爆心在地面附近，往上够 R（115），再加上小鬼自身判定体的厚度（40）→ 155，
        而实测最高点只有 146 → **在最高点也炸得到**（与实战"三种时机都能拦"一致）。
        """
        if not self.imp_fly:
            return 0
        n = 0
        for i in self.imp_fly:
            if i.get('killed'):
                continue
            if abs(i['x'] - cx) > radius:
                continue
            if i['h'] > radius + D.IMP_BOX:
                continue
            i['killed'] = True
            n += 1
            self.imp_log.append(dict(wave=i['wave'], row=i['row'],
                                     res='killed', t=self.t,
                                     x=round(i['x']), h=round(i['h'])))
            self._log('ASH', '拦截成功：炸死 %d 路空中的小鬼（h=%.0f）'
                      % (i['row'], i['h']),
                      row=i['row'], detail='x=%.0f' % i['x'])
        self.imp_fly = [i for i in self.imp_fly if not i.get('killed')]
        return n

    def _blover(self, ev):
        """三叶草：秒杀全场气球（气球在本模型里是 SKIP 类的"进场即被清"，所以
        这里做的是**把本波气球那部分血量直接抹掉**，并记一条日志）。"""
        meta = self.wave_meta
        n = (self.wave_script(self.cur_wave) or {}).get('气球', 0) if meta else 0
        if not n:
            self._log('INFO', '三叶草：本波没有气球', detail='白放一张')
            return
        hp = D.ZOMB['气球'][0] * n
        if meta:
            meta['skip_hp'] = max(0, meta.get('skip_hp', 0) - hp)
            meta['total_hp'] = max(0, meta.get('total_hp', 0) - hp)
            meta['remain'] = max(0, meta.get('remain', 0) - hp)
        self._log('RESCUE', '三叶草吹走 %d 只气球（−%d 血）' % (n, hp),
                  detail='简化：气球一出现就被清掉，本波血量相应下调')

    def _grave_eat(self, ev, aim):
        """墓碑吞噬者：直接清除目标格的墓碑（[精 三] 吞碑 448~471cs）。"""
        pos = None
        if isinstance(aim, (tuple, list)) and len(aim) == 2:
            pos = (int(aim[0]), int(aim[1]))
        if pos is None:
            graves = [rc for rc, c in self.cells.items() if c.grave]
            if not graves:
                self._log('INFO', '墓碑吞噬者：场上没有墓碑')
                return
            pos = graves[0]
        cell = self.cells.get(pos)
        if cell is None or not cell.grave:
            self.broken.append(dict(t=self.t, wave=ev['wave'], what='墓碑吞噬者',
                                    why='%d-%d 没有墓碑' % pos))
            return
        cell.grave = False
        self._log('REPAIR', '墓碑吞噬者清掉 %d-%d 的墓碑' % pos,
                  row=pos[0], col=pos[1], detail='吞碑 ≈471cs · 该格现在可以种了')

    def _pick_row(self):
        cars = [z for z in self.zombies if z.alive and z.kind == '冰车']
        if cars:
            self._car_hint = max(cars, key=lambda z: z.x)
            return self._car_hint.row
        self._car_hint = None
        pool = {}
        for z in self.zombies:
            if z.alive and self._targetable(z):
                pool[z.row] = pool.get(z.row, 0) + z.total_hp
        return max(pool, key=pool.get) if pool else self.rng.choice(list(self._rows()))

    def _boom(self, row, col, radius, dmg, delay=None, center=None, src='ash'):
        """灰烬：排进队列，到点结算。

        ★ 种下即 `ash_pending = True` —— 用户："碾压不对已经触发的灰烬生效，
          而且可以把'种植即触发'的灰烬直接种在碾压判定区"。

        ★★ 结果导向（用户 2026-10-22）：**种植即生效** ——
          `D.ASH_DELAY` 在 `RESULT_ONLY` 下就是 0（白天咖啡豆唤醒的 299cs 也不计），
          所以这里实际上当帧就结算。真实时延值仍保留在 `data.py` 的注释里。

        ★ 2026-10-22：`center` 显式给爆心。`[精 六]` 明确：
          樱桃 / 毁灭菇的圆心都是 **(x+40, y+40)**，不是格子中心 ——
          以前按格子中心算，整体偏左偏上 40px。
        """
        d = D.ASH_DELAY if delay is None else delay
        if center is None:
            center = (D.cell_x(col) + 40, self.py(row, col) + 40)
        self.boom_q.append((self.t + d, row, col, radius, dmg, 0, center, src))
        c = self.cells.get((row, col))
        if c is None:
            c = self.cells[(row, col)] = Cell(row, col)
        c.ash_pending = True

    def _tick_boom(self):
        if not self.boom_q and not self.chili_q:
            return
        if self.boom_q:
            due = [b for b in self.boom_q if b[0] <= self.t]
            if due:
                self.boom_q = [b for b in self.boom_q if b[0] > self.t]
                for b in due:
                    row, col, radius, dmg = b[1], b[2], b[3], b[4]
                    dy = b[5] if len(b) > 5 else 0
                    center = b[6] if len(b) > 6 else None
                    _src = b[7] if len(b) > 7 else 'ash'
                    c = self.cells.get((int(round(row)), int(round(col))))
                    if c is not None:
                        c.ash_pending = False
                    self._apply_boom(row, col, radius, dmg, dy, center, _src)
        if self.chili_q:
            due = [c for c in self.chili_q if c[0] <= self.t]
            if due:
                self.chili_q = [c for c in self.chili_q if c[0] > self.t]
                for _, r, *rest in due:
                    for col in range(1, 10):
                        cc = self.cells.get((r, col))
                        if cc is not None and cc.ash_pending:
                            cc.ash_pending = False
                    for z in self.zombies:
                        if z.alive and z.row == r:
                            self._hurt(z, D.ASH_DMG, True, src='ash')
                            self.dmg_dealt += D.ASH_DMG
                    self._clear_ice_trail(row=r)
                    # ★ 用户："如果因 5-3 辣椒复用导致当时没能正常补存冰，
                    #   辣椒生效后立即补" —— 不再等下一波。
                    self._chili_freed_at = self.t

    def _ash_cell(self, row, col, dmg, half=40):
        """
        **窝瓜的一格宽判定域**（用户 2026-10-20 定的简化口径）：

          「窝瓜的"种植-索敌-攻击生效"时延忽略，直接视作一个 **1 格宽**的、
            1.8k 伤害**即刻生效**的攻击判定域（伤害判定一样，
            攻击判定域与受击判定域**有重合**就伤害生效）」

        所以这里不做"选最前一只"这种事 —— 判定域是 [cx−half, cx+half]，
        该行里**任何**受击框与之相交的僵尸都吃满 1800。

        这条正好解释了"一个窝瓜压死整条路的冰车"：
        同路冰车视觉重合 → 受击框完全重叠 → 全在判定域内 → 全部 1800。
        """
        cx = D.cell_x(col)
        lo, hi = cx - half, cx + half
        n = 0
        hit_giant = []
        for z in self.zombies:
            if not z.alive or z.row != row:
                continue
            zl, zr = self._dbox(z)
            if zr < lo or zl > hi:
                continue
            self._hurt(z, dmg, True, src='wogua')
            self.dmg_dealt += dmg
            n += 1
            if z.giant:
                hit_giant.append(z.kind)
        return n, hit_giant

    def _tick_wogua(self):
        """窝瓜待命 → 有僵尸踏进判定域就即刻生效"""
        p = self.wogua_pending
        if not p:
            return
        if self.t > p['until']:
            self.wogua_pending = None
            return
        n, _ = self._ash_cell(p['row'], p['col'], D.ASH_DMG)
        if not n:
            return
        self.wogua_pending = None
        self._log('RESCUE', '窝瓜生效 %d-%d：本格 %d 只各吃 1800'
                  % (p['row'], p['col'], n), row=p['row'], col=p['col'],
                  detail='1 格宽判定域 · 即刻生效')

    def _apply_boom(self, row, col, radius, dmg, dy_off=0, center=None, src='ash'):
        """
        灰烬爆炸 = **圆形判定**，且用「圆心到僵尸受击框最近点」的距离。

        ★ 用户 2026-10-19 指出：巨人受击框大，所以一颗核能炸到相邻好几路的巨人 ——
          2 路核可炸 1/2/5 路，5 路核可炸 2/5/6 路。
          这只有在「纵向用两套 y 坐标 + 框最近点」时才会自然成立：
            核在 2-7：圆心 y = plant_y(2) = 165
            5 路巨人受击框 y ∈ [390, 505] → 最近点 390 → dy = 225 < 250 ✔
            6 路巨人 y ∈ [475, 590] → dy = 310 > 250 ✘（实测也说炸不到）

        `center=(cx, cy)` 给了就**直接用**（P 的落点可以带小数，圆心不能再按整格还原）。
        """
        if center is not None:
            cx, cy = float(center[0]), float(center[1])
        else:
            hint = getattr(self, '_car_hint', None)
            if hint is not None and hint.row == row:
                col = max(1, min(9, int(round((hint.x - 40) / 80.0)) + 1))
            cx = D.cell_x(col)
            cy = self._aim_py(row, col) + dy_off
        r2 = radius * radius
        for z in self.zombies:
            if not z.alive:
                continue
            zl, zr = self._dbox(z)
            if zl > D.DMG_LINE:          # 防御域左端在 800 之外 → 还不可伤
                continue
            zy = self.zy(z.row)
            # 受击框上离圆心最近的点
            nx = zl if cx < zl else (zr if cx > zr else cx)
            ny = zy if cy < zy else (zy + D.DEF_HEIGHT if cy > zy + D.DEF_HEIGHT else cy)
            dx, dy = nx - cx, ny - cy
            if dx * dx + dy * dy <= r2:
                self._hurt(z, dmg, True, src=src)
                self.dmg_dealt += dmg

    def _doom(self, aim):
        """
        点核。**坑位记账**（用户 2026-10-19 点名："你并没有算坑位哦"）。

        ★ 关键：坑位是硬资源。一个坑炸完要 18000cs（180s）才能再用。
          w1 与 w11 相隔约 190s —— 刚好够复用同一个坑。
          如果在中间多插一次核，就要多占一个坑；插两次以上，
          180s 内同时在坑期的格子数会超过可用格数 → **核点不出去**。
          所以用户要求 w1 固定 2-9、w11 固定 5-9，其余波按判定插。

        aim 可以是 (row, col) 指定坑，也可以是 None（按优先级挑）。
        """
        slot = None
        if isinstance(aim, (tuple, list)) and len(aim) == 2:
            # ★ 指定坑：w1 → 2-9、w11 → 5-9
            r0, c0 = aim
            order = [(r0, c0)] + [rc for rc in self.slots.get('kernel', [])
                                  if rc != (r0, c0)]
            # 指定坑被冰道/核坑占了 → 按"同路往左退一格、再退到另一路"兜底
            for (r, c) in order:
                cell = self.cells.get((r, c))
                if cell is None:
                    cell = self.cells[(r, c)] = Cell(r, c)
                if cell.crater_until > self.t:
                    continue
                if self.temp_ice.get((r, c)):
                    continue
                if cell.iced:
                    continue
                slot = (r, c)
                break
            if slot is None:
                # 全部不行：就近硬点（清掉冰道），玩家不会让核烂手上
                for (r, c) in order:
                    cell = self.cells.get((r, c))
                    if cell is not None and cell.crater_until <= self.t:
                        slot = (r, c)
                        cell.iced = False
                        cell.ice_until = -1
                        self._log('INFO', '核坑兜底 %d-%d（清掉冰道）' % (r, c), row=r, col=c)
                        break
            designated = (slot == (r0, c0))
            if not designated:
                cell0 = self.cells.get((r0, c0))
                why = ('核坑期' if (cell0 and cell0.crater_until > self.t)
                       else '冰道' if (cell0 and cell0.iced)
                       else '临时存冰占位' if self.temp_ice.get((r0, c0))
                       else '不可用')
                self._log('INFO', '指定核坑 %d-%d 不可用（%s）→ 退到 %d-%d'
                          % (r0, c0, why, slot[0], slot[1]),
                          row=slot[0], col=slot[1],
                          detail='用户口径：w11 要先判 5-9 有没有冰道')
        else:
            designated = False
            for (r, c) in self.slots.get('kernel', [(5, 8)]):
                cell = self.cells.get((r, c))
                if cell is None:
                    cell = self.cells[(r, c)] = Cell(r, c)
                if cell.iced:
                    continue
                if cell.crater_until > self.t:
                    continue
                if self.temp_ice.get((r, c)):
                    continue
                slot = (r, c)
                break
            if slot is None:
                for (r, c) in self.slots.get('kernel', [(5, 8)]):
                    cell = self.cells.get((r, c))
                    if cell is not None and cell.crater_until <= self.t:
                        slot = (r, c)
                        cell.iced = False
                        cell.ice_until = -1
                        self._log('INFO', '核坑兜底 %d-%d（清掉冰道）' % (r, c), row=r, col=c)
                        break

        if slot is None:
            self.broken.append(dict(t=self.t, wave=self.cur_wave, what='核',
                                    why='所有核坑位都被冰道/核坑占住'))
            self.kernel_log.append(dict(t=self.t, wave=self.cur_wave, rc=None,
                                        ok=False, designated=False))
            return
        row, col = slot
        self._boom(row, col, D.DOOM_R, D.ASH_DMG, D.DOOM_DELAY)
        c = self.cells[(row, col)]
        c.crater_until = self.t + D.CRATER_CS
        if self.actions:
            self.actions[-1]['rc'] = (row, col)
        self.kernel_log.append(dict(t=self.t, wave=self.cur_wave, rc=(row, col),
                                    ok=True, designated=designated))

    def _freeze(self):
        self.last_freeze_t = self.t
        dur = self.rng.randint(*D.FREEZE_CS)
        for z in self.zombies:
            if not z.alive or z.kind == '冰车':
                continue
            d2 = self.rng.randint(300, 400) if z.slowed_until > self.t else dur
            z.frozen_until = max(z.frozen_until, self.t + d2)
            z.slowed_until = max(z.slowed_until, self.t + D.ICE_TOTAL_CS)
        # ★ 2026-10-22：冰真的生效了 → 被"冰杀定式"覆盖的蹦极目标保住了
        self._bungee_mark('ice')

    # ------------------------------------------------ 主循环
    def _arm_fixed_timeline(self):
        """把阵解的**绝对运算量时间轴**排进事件表（固定波长的阵）。

        ★ 2026-10-24：见 `plan._fixed_timeline`。要点是"运算量与刷波解耦" ——
          否则前方清兵慢 → 下一波迟迟不刷 → 炮跟着迟到 → 出现 3~5s 的炮空窗。
        """
        fixed = getattr(self.track, 'fixed', None) or []
        if fixed:
            # ★ 产能检查：一门炮 3475cs 装填 → N 门炮在任意 3475cs 窗口内最多 N 发。
            #   超产能的那几发**单独丢掉**（它们本来也打不出去），其余照绝对时刻走。
            #   例：FE.雾四炮 手写阵解的 w18~w20 挤了 6 发/3475cs（只有 4 门炮），
            #   表现为"w20 的 P 又多又乱" —— 现在会明确报出来并丢掉多余的。
            n_cob = sum(1 for c in self.cells.values()
                        if c.plant == '玉米炮' and c.plant_hp > 0)
            cap = max(1, n_cob)
            kept, recent = [], []
            for item in sorted(fixed, key=lambda x: int(x[0])):
                t = int(item[0])
                if item[1] == '玉米炮':
                    recent = [x for x in recent if t - x < 3475]
                    if len(recent) >= cap:
                        self._log('INFO', '跳过超产能的开炮（t=%d，%d 门炮 3475cs 内已 %d 发）'
                                  % (t, n_cob, len(recent)),
                                  detail='固定波长的阵必须与炮的产能匹配')
                        continue
                    recent.append(t)
                kept.append(item)
            fixed = kept
        for item in fixed:
            t, name, aim, w = item[0], item[1], item[2], item[3]
            bid = item[4] if len(item) > 4 else None
            self._schedule(max(0, int(t)), name, aim, w, bid=bid)

    def run(self):
        self._arm_fixed_timeline()
        while not self.done and self.t < self.max_t:
            self.t += D.TICK
            self._index()
            self._tick_spawn()
            self._tick_move()
            self._tick_miner()
            self._tick_icecar()
            self._tick_catapult()
            self._tick_basket()
            self._tick_imp()
            self._tick_spike_crush()
            self._tick_joker()
            self._tick_wogua()
            self._tick_garlic()
            self._tick_struct_fog()
            self._tick_chili_refill()
            self._tick_ice_refill()
            self._tick_ice_trail()
            self._tick_dying()
            self._check_fail()
            if self.done:
                break
            self._tick_rescue()
            self._tick_globals()
            self._tick_repair()
            self._tick_plants()
            self._tick_pending()
            self._tick_boom()
            self._tick_events()
            self._tick_skip()
            self._tick_slow_stat()
            self._tick_refresh()
            self._cleanup()
            if self.t % 100 == 0:
                alive = [z for z in self.zombies if z.alive]
                self.series.append(dict(
                    t=self.t, sun=round(self.sun),
                    alive=len(alive),
                    frozen=sum(1 for z in alive if z.frozen_until > self.t),
                    slowed=sum(1 for z in alive if z.slowed_until > self.t),
                    wave=(self.wave_meta['wave'] if self.wave_meta else 0),
                    remain=round(self.wave_meta['remain']) if self.wave_meta else 0,
                ))
                self._snap_tick(alive)
        return self.report()

    def _index(self):
        for r in self.by_row:
            self.by_row[r] = []
        for z in self.zombies:
            if z.alive:
                self.by_row[z.row].append(z)
                if z.x < self.row_min.get(z.row, 9999):
                    self.row_min[z.row] = z.x

    def _dbox(self, z):
        """僵尸防御域 [左界, 右界]。巨人明显比普通僵尸宽，且向左伸出一格。"""
        off, w = D.DEFENSE_BOX.get(z.kind, D.DEFENSE_BOX['默认'])
        return z.x + off, z.x + off + w

    def _spike_pop(self, cell, why, source=None):
        """地刺 / 地刺王 被"砸"或"碾"一次（用户 2026-10-22 的机制说明）。

        · `crush_hits = 1`（地刺）→ 第 1 次就碎
        · `crush_hits = 9`（地刺王）→ withstand 8、第 9 次才碎（= wiki 口径）
        · `pops_car = True`（地刺王）→ **与冰车/投篮车同归于尽**（wiki：
          "destroy specific zombies at the cost of themselves"）
        """
        spec = D.PLANTS.get(cell.plant or '') or {}
        if not spec.get('spike'):
            return False
        cell.pops += 1
        need = spec.get('crush_hits', 1)
        if cell.pops >= need:
            name = cell.plant
            cell.plant = None
            cell.plant_hp = 0
            cell.pops = 0
            self._log('WARN', '%d-%d 的%s被%s毁掉' % (cell.row, cell.col, name, why),
                      row=cell.row, col=cell.col,
                      detail='地刺 withstand 0 / 地刺王 withstand 8（第 9 次碎）')
            return True
        self._log('INFO', '%d-%d 的%s扛住一次%s（%d/%d）'
                  % (cell.row, cell.col, cell.plant, why, cell.pops, need),
                  row=cell.row, col=cell.col)
        return False

    def _is_tall(self, cell):
        """高坚果：撑杆 / 跳跳 / 海豚 跳不过去（[维] Tall-nut）"""
        if cell is None or not cell.plant:
            return False
        return bool(D.PLANTS.get(cell.plant, {}).get('tallnut'))

    # ------------------------------------------------ 基座 / 能否种（v0.2.1）
    def _plant_into(self, cell, name):
        """把植物种进一格，并处理**蘑菇的睡眠**。

        ★ 用户 2026-10-22 的完整口径：
          ① 已经唤醒的蘑菇永远醒着；
          ② 阵图里本来就是醒的（曾哥 / 大喷）永远醒着 —— 由 Cell 初始化保证；
          ③ 阵图里的寒冰菇是睡着的（= 存冰）；
          ④ **新种下的蘑菇一定是睡着的** —— 要它干活得先种一颗咖啡豆。
        """
        cell.plant = name
        cell.plant_hp = D.PLANTS.get(name, {}).get('hp', D.PLANT_HP_DEFAULT)
        # ★ 2026-10-22 用户：「FE 是夜场，蘑菇种植就醒着」
        #   → **只有白天场**新种的蘑菇才是睡着的；夜场种下即生效。
        if name in D.MUSHROOMS and not self.fld.night:
            cell.awake = False
            cell.atk_t = 0
            self._log('INFO', '新种下的%s（%d-%d）是睡着的'
                      % (name, cell.row, cell.col), row=cell.row, col=cell.col,
                      detail='用户口径：新种的蘑菇一律先睡，要咖啡豆唤醒')
        else:
            cell.awake = True
        cell.sun_born = self.t
        cell.grown = False
        return cell

    def _base_ok(self, rc, plant=None):
        """这一格能不能直接种 `plant`。

        ★ 用户 2026-10-22：「PE / FE 在水路空地上面种植物必须先进行种荷叶；
          RE 空地上面种植物必须先进行种花盆」
          → 要种的**不是**那个基座本身时，格子上必须先有基座。
        """
        row, col = rc[0], rc[1]
        if row not in self.by_row:
            return False
        req = self.fld.base_for(row)
        if not req or plant == req:
            return True
        cell = self.cells.get((row, col))
        if cell is None:
            return False
        return bool(cell.base or cell.plant == req)

    def _seed_base(self, rc):
        """给一格补上基座（荷叶 / 花盆）—— 供"必须先种基座"的场景记账用"""
        req = self.fld.base_for(rc[0])
        if not req:
            return True
        cell = self.cells.get(rc)
        if cell is None:
            cell = self.cells[rc] = Cell(rc[0], rc[1])
        if cell.base or cell.plant == req:
            return True
        if cell.plant is not None:
            return False
        cell.plant = req
        cell.plant_hp = D.PLANTS.get(req, {}).get('hp', D.PLANT_HP_DEFAULT)
        cell.base = True
        self._log('INFO', '先种基座 %s 在 %d-%d' % (req, rc[0], rc[1]),
                  row=rc[0], col=rc[1],
                  detail='水上要荷叶、屋顶要花盆（用户 2026-10-22 的口径）')
        return True

    def _speed_of(self, z):
        if z.kind == '冰车':
            return D.ice_car_speed(z.x)      # 冰车免疫减速
        # ★ 2026-10-22：分阶段速度。撑杆跳完之后回落"慢速"档（用户：一般的快速僵尸，
        #   飞跃第一个植物）—— 这里用 spd_alt（init 时按「慢速」档抽好）
        ph = getattr(z, 'phase', 'walk')
        s = z.spd_alt if (ph == 'walk' and z.spd_alt) else z.spd
        if z.slowed_until > self.t:
            # ★ 2026-10-24 用户口径：匀速（没有腿部动画）×0.4、两条腿走的 ×0.5
            s *= (D.SLOW_UNIFORM if D.is_uniform_move(z.kind, ph)
                  else D.SLOW_ANIM)
        return s

    def _anim_rate(self, z):
        """僵尸的**动画进度**倍率（非匀速被减速 → 0.5）。吃东西/举锤/开盒都用它"""
        return D.anim_rate(z.kind, getattr(z, 'phase', 'walk'),
                           slowed=z.slowed_until > self.t,
                           frozen=z.frozen_until > self.t)


    def _ice_trail(self, z):
        """
        冰车铺冰道。

        ★★ 2026-10-19 **上一版我做错了，这里改正**。
        我曾写"冰车被消灭时它铺的冰道一起消失" —— 这是**完全错误**的。
        真实规则（用户）：
          · 冰道是**格子属性，会持续保留**；
          · 只有两种消失方式：**辣椒烧化**、或**长间隔自然融化**；
          · 车死了、被窝瓜压了，冰道照样留着。

        真正让 "w11 的 5-9 一定干净" 成立的是**车头/车尾差一格**：
          · 冰车 `z.x` 是**车头**（碾压判定前沿）；
          · 冰道在**车尾** = `z.x + CAR_HEAD_GAP`（右一格，80px）；
          → 车头走到 col 8（x=600）时，车尾（x=680）才刚铺上 col 9。
            所以窝瓜只要在"车头还在 col 8 右边（x > 600）"时引爆，
            5-9 就永远不会被这辆车铺上。
            w10 的 `WOGUA_CAR_X = 720` 正好落在这个窗口里。
        """
        col = int(round((z.x + D.CAR_HEAD_GAP - 40) / 80.0)) + 1
        if 1 <= col <= 9:
            c = self.cells.get((z.row, col))
            if c is None:
                c = self.cells[(z.row, col)] = Cell(z.row, col)
            c.iced = True
            c.ice_until = self.t + D.ICE_TRAIL_TTL
            self.ice_touched.add((z.row, col))

    def _tick_ice_refill(self):
        """
        **波内即时补种**（用户原话："卡槽的冰一好就拿它补存冰"）。

        原来只在换波时补一次 → 20 波最多 20 次机会，还要跟冰卡 CD 对表，
        实际只补到 10 次，冰卡有 1/3 的产能被"等下一波"白白浪费。
        玩家真实动作是：眼睛盯着卡槽，一好就点下去种。
        所以改成每 2s 检查一次：有空位 + 卡好 + 阳光够 → 立刻补。
        """
        if self.t % 200:
            return
        chili = self._chili_slot()
        empty = [rc for rc, full in self.ice_slots.items() if not full]
        if not empty:
            return
        empty.sort(key=lambda rc: (rc == chili, rc[0], rc[1]))
        rc = empty[0]
        if rc == chili and len(empty) == 1:
            # 5-3 与辣椒共用：辣椒快好了就先不占
            if self.card_ready.get('辣椒', 0) - self.t <= D.CHILI_RESERVE_CS:
                return
        card = None
        for k in ('冰', '模仿冰'):
            if self.card_ready.get(k, 0) <= self.t:
                card = k
                break
        if card is None or self.sun < D.CARDS[card]['cost']:
            return
        self.sun -= D.CARDS[card]['cost']
        self.card_ready[card] = self.t + D.CARDS[card]['cd']
        self.ice_slots[rc] = True
        self.ice_refill_n += 1
        self.actions.append(dict(t=self.t, wave=self.cur_wave, name='种冰', ok=True))
        self._log('REPAIR', '补存冰 %d-%d（%s · 现有 %d 个）'
                  % (rc[0], rc[1], card, self.ice_stock), row=rc[0], col=rc[1],
                  detail='卡一好就补，不等下一波')

    def _tick_chili_refill(self):
        """
        5-3 复用辣椒位后的**即时补种**。

        用户 2026-10-19："如果因 5-3 辣椒复用导致当时没能正常补存冰，
        辣椒生效后立即补"。

        原来我是"下一波再补"，等于让 5-3 空整整一波（13~19s），
        这段时间冰卡即使转好也用不上 —— 直接少一次补种机会。
        现在辣椒一炸完（`_chili_freed_at`）就补，卡一好就补。
        """
        if getattr(self, '_chili_freed_at', -1) < 0:
            return
        chili = self._chili_slot()
        if not chili or self.ice_slots.get(chili):
            self._chili_freed_at = -1
            return
        card = None
        for k in ('冰', '模仿冰'):
            if self.card_ready.get(k, 0) <= self.t:
                card = k
                break
        if card is None:
            return
        self.sun -= D.CARDS[card]['cost']
        self.card_ready[card] = self.t + D.CARDS[card]['cd']
        self.ice_slots[chili] = True
        self.ice_refill_n += 1
        self._chili_freed_at = -1
        self.actions.append(dict(t=self.t, wave=self.cur_wave, name='种冰', ok=True))
        self._log('REPAIR', '辣椒生效后立即补回 5-3 存冰（%s · 现有 %d 个）'
                  % (card, self.ice_stock), row=chili[0], col=chili[1],
                  detail='用户口径：辣椒用了就补，不等下一波')

    def _tick_ice_trail(self):
        for c in self.cells.values():
            if c.iced and c.ice_until > 0 and self.t >= c.ice_until:
                c.iced = False
                c.ice_until = -1

    def _clear_ice_trail(self, row=None):
        for c in self.cells.values():
            if row is not None and c.row != row:
                continue
            c.iced = False
            c.ice_until = -1

    def _tick_dying(self):
        """巨人无临界；冰车临界仍能碾；其它掉头即无威胁"""
        for z in self.zombies:
            if not z.alive or z.hp <= 0:
                continue
            if z.giant or z.kind == '冰车':
                continue
            if z.hp < z.hp0 * D.DYING_RATIO:
                z.alive = False
                # ★ 2026-10-23：掉头走掉的小丑也算"炸之前就死了"
                if z.kind == '小丑' and z.joker_res is None:
                    z.joker_res = 'died'
                    self.joker_units.append(dict(
                        wave=z.wave, row=z.row, early=bool(z.joker_early),
                        res='died', killed=[], pads=[],
                        defused=bool(z.defused),
                        frozen=(z.frozen_until > self.t)))

    def _tick_catapult(self):
        """
        投篮车（Catapult）：**如实按《僵尸时间表》**（用户 2026-10-23）。

          · 生成后 **473cs** 就绪（表：投篮就绪）
          · 再加 **74cs** 投出第一个篮球（表：投篮就绪到投篮）
          · 之后每 **300cs** 再投一发（《精确数值》：投篮攻击间隔）

        对策判定（用户口径）：**陆路底线被伞覆盖**，或**在投掷前把它击杀** → 对策有效。
        目标 = 它**本路**最靠后的植物（底线）；被伞罩住就算挡下。
        """
        for z in self.zombies:
            if not z.alive or z.kind != '投篮':
                continue
            if z.frozen_until > self.t:
                continue                      # 冻住 = 动不了也投不出（简化口径）
            if z.born_t < 0:
                continue
            if z.cat_at < 0:
                z.cat_at = z.born_t + D.CATAPULT_READY + D.CATAPULT_THROW_DELAY
                continue
            if self.t < z.cat_at:
                continue
            z.cat_at = self.t + D.CATAPULT_INTERVAL
            self._catapult_throw(z)

    def _catapult_throw(self, z):
        """投一发篮球：打本路**底线**（最靠左）的植物，199cs 后落地。

        对策判定（用户 2026-10-23）：**投掷前把它击杀**，或**底线有伞** → 对策有效。
        所以落地那一刻才检查伞（这期间补伞也来得及）。
        """
        target = None
        for col in range(1, 10):
            c = self.cells.get((z.row, col))
            if c is not None and c.has_content():
                target = c
                break
        if target is None:
            return
        self.cat_pending.append(dict(t=self.t + D.BASKET_FLIGHT,
                                     rc=(target.row, target.col),
                                     wave=z.wave, row=z.row))

    def _tick_basket(self):
        """篮球落地结算：伞挡下 / 命中。"""
        if not self.cat_pending:
            return
        keep = []
        for b in self.cat_pending:
            if b['t'] > self.t:
                keep.append(b)
                continue
            rc = b['rc']
            cell = self.cells.get(rc)
            if cell is None or not cell.has_content():
                self.catapult.append(dict(t=self.t, wave=b['wave'], rc=rc,
                                          plant=None, verdict='目标已经没了'))
                continue
            if self._umbrella_covers(rc):
                self.catapult.append(dict(t=self.t, wave=b['wave'], rc=rc,
                                          plant=cell.plant, verdict='伞挡下'))
                self._log('INFO', '投篮的篮球被保护伞挡下 %d-%d' % rc,
                          row=rc[0], col=rc[1],
                          detail='用户口径：陆路底线被伞覆盖 → 对策有效')
                continue
            had, had_ladder = cell.plant, cell.ladder
            broke = cell.take_damage(D.BASKET_DMG)
            self.catapult.append(dict(t=self.t, wave=b['wave'], rc=rc,
                                      plant=had, verdict='命中 %d' % D.BASKET_DMG))
            self._log('WARN', '%d-%d 的%s被篮球砸中（%d）'
                      % (rc[0], rc[1], had or '南瓜', D.BASKET_DMG),
                      row=rc[0], col=rc[1],
                      detail='投篮车投掷前没被击杀 · 底线又没伞')
            if broke == 'plant':
                self._plant_lost(cell, had, None, by='投篮')
            elif broke == 'pumpkin':
                self._log('WARN', '南瓜被篮球砸穿 %d-%d' % rc,
                          row=rc[0], col=rc[1])
        self.cat_pending = keep

    def _summon(self, dancer):
        for i in range(D.DANCER_SUMMON_N):
            b = Zombie('伴舞', dancer.row, min(780, dancer.x + 8 - i * 6),
                       dancer.wave, self.rng)
            # ★ 表：召唤到伴舞啃食 151cs —— 召出来的这批要等这么久才能啃
            b.born_t = self.t
            b.eat_ready = self.t + D.DANCER_BACKUP_EAT_CS
            self.zombies.append(b)
            self.by_row[dancer.row].append(b)
            # ★ 伴舞必须计入本波血量，否则刷新判定看不见它们（波会被算短）
            if self.wave_meta is not None:
                self.wave_meta['zs'].append(b)
                self.wave_meta['total_hp'] += b.hp0

    def _front_plant_col(self, row):
        """这一路**最靠前（列号最大）**的植物在第几列；没有就 None

        用户 2026-10-22：小丑重点模拟哪一型由它决定。
        """
        best = None
        for col in range(1, 10):
            c = self.cells.get((row, col))
            if c is not None and (c.has_content() or c.tail):
                best = col
        return best

    def _umbrella_covers(self, rc):
        """这一格是不是被**叶子保护伞**罩住

        [知识库 05 / 记忆]：伞覆盖 **3×3 且含自身格**；放第 2 列才罩得住第 3 列的关键植物。
        """
        r, c = rc
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                cc = self.cells.get((r + dr, c + dc))
                if cc is not None and cc.plant == '保护伞':
                    return True
        return False

    def _is_umbrella(self, rc):
        cell = self.cells.get(rc)
        return cell is not None and cell.plant == '保护伞'

    def _ice_kill_cover(self, rc):
        """这一格是不是被「冰杀定式」覆盖（二曾 / 瓜曾喷）

        用户 2026-10-22：这类格子的植物**必须让寒冰菇真的生效**才保得住。
        简化口径：3×3 内的忧郁菇 ≥ 2（二曾），或者 1 曾 + 同路 3 格内有冰瓜（瓜曾喷）。
        """
        r, c = rc
        n_zeng = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                cc = self.cells.get((r + dr, c + dc))
                if cc is not None and cc.plant == '忧郁菇':
                    n_zeng += 1
        if n_zeng >= D.BUNGEE_ICE_KILL_ZENG:
            return True
        if n_zeng >= 1:
            for dc in (-3, -2, -1, 1, 2, 3):
                cc = self.cells.get((r, c + dc))
                if cc is not None and cc.plant in ('冰瓜', '冰西瓜'):
                    return True
        return False

    def _plant_status(self):
        """这一局结束时**全场每一株植物**的状态（报告总概述用）

        ★ 2026-10-22 用户要求：报告里所有固定文本都换成"按实际阵型 & 阵解"
          得到的可替换文本 —— 所以植物的初始 / 当前 / 血量 / 南瓜 / 梯子
          全部按格列出，界面只负责排版。
        """
        out = []
        for (r, c) in sorted(self.array):
            spec = self.array[(r, c)] or {}
            cell = self.cells.get((r, c))
            init = spec.get('plant') or ''
            now = (cell.plant if cell is not None else None) or ''
            max_hp = D.PLANTS.get(init, {}).get('hp', D.PLANT_HP_DEFAULT) if init else 0
            out.append(dict(
                row=r, col=c, init=init, now=now,
                hp=round(cell.plant_hp) if cell is not None and cell.plant else 0,
                max_hp=max_hp,
                pumpkin=bool(cell.pumpkin) if cell is not None else False,
                pumpkin_init=bool(spec.get('pumpkin')),
                pumpkin_hp=round(cell.pumpkin_hp) if cell is not None else 0,
                ladder=bool(cell.ladder) if cell is not None else False,
                alive=bool(now),
            ))
        return out

    def _bungee_plan(self, w):
        """蹦极的简化判定（用户 2026-10-22 口径）

        ★★ 用户原话：
          「炮不用管，因为不会被蹦极锁定；场上植物全都被保护伞覆盖（3×3）时
           不用额外操作处理蹦极；对于没有被保护伞覆盖却处于冰杀定式下的植物，
           必须寒冰菇生效冰冻落下来的蹦极；对于保护伞覆盖也没有处于冰杀定式下的
           植物，用炮炸蹦极。」

        → 所以候选里**根本不该出现玉米炮**，也不该出现伞覆盖的格子。
          只有"既不在伞下、也不在冰杀定式下"的才是真·裸奔目标（需要炮炸）。
        """
        if not self.wave_script(w).get('蹦极'):
            return None
        n = int(self.wave_script(w).get('蹦极') or 0)
        cand = []
        n_umbrella = 0          # 被伞罩住（含炮）→ 不用管
        n_cob_exempt = 0        # 玉米炮 → 不会被锁定
        n_pad_exempt = 0        # 垫材 → 本来就是消耗品，不值得为它防蹦极
        # ★ 2026-10-25 用户：「当场上**仅仅只有 1 个**阳光植物（葵 / 阳光菇 / 双子葵）时，
        #   这个阳光植物**不会被蹦极锁定**」→ 唯一的经济来源不会被掐断。
        sun_cells = [(r, c) for (r, c), cell in self.cells.items()
                     if (cell.plant or '') in D.SUN_PLANTS]
        lone_sun = sun_cells[0] if len(sun_cells) == 1 else None
        n_sun_exempt = 0
        for (r, c), cell in self.cells.items():
            if not (cell.plant or cell.tail):
                continue
            name = cell.plant or '玉米炮'
            # ★ 2026-10-23 用户：「保护伞在 3×3 内除了防篮球**也可以防蹦极**」
            #   → 保护伞自身、玉米炮、垫材都不进候选。
            if name == '玉米炮' or cell.tail or name in D.BUNGEE_SAFE_PLANTS:
                n_cob_exempt += 1
                continue
            if name in D.PAD_PLANT.values():
                n_pad_exempt += 1
                continue
            if lone_sun is not None and (r, c) == lone_sun:
                n_sun_exempt += 1
                continue
            if self._umbrella_covers((r, c)):
                n_umbrella += 1
                continue
            cand.append(dict(rc=(r, c), plant=name,
                             need=('ice' if self._ice_kill_cover((r, c)) else 'cob'),
                             saved=None))
        # 按"价值"排：曾 / 冰瓜 > 一般输出 > 其他；同价值取更靠后（玩家更在意的后场）
        rank = {'忧郁菇': 0, '冰瓜': 0, '冰西瓜': 0, '香蒲': 1, '双发射手': 1,
                '机枪射手': 1, '大喷菇': 2, '阳光菇': 3, '向日葵': 3}
        cand.sort(key=lambda t: (rank.get(t['plant'], 2), -t['rc'][1]))
        targets = cand[:n]
        return dict(wave=w, n=n, targets=targets,
                    stolen=[], saved_ice=0, saved_cob=0,
                    safe_umbrella=n_umbrella, cob_exempt=n_cob_exempt,
                    pad_exempt=n_pad_exempt, sun_exempt=n_sun_exempt,
                    exposed=len(cand))

    def _bungee_mark(self, kind, rc=None, center=None):
        """冰 / 炮 救下蹦极目标；`center=(cx,cy)` = 爆炸判定域（盖到那格就算救）"""
        b = getattr(self, '_bungee_cur', None)
        if not b:
            return
        for t in b['targets']:
            if t['saved']:
                continue
            if kind == 'ice':
                if t['need'] == 'ice':
                    t['saved'] = 'ice'
                    b['saved_ice'] += 1
                continue
            if kind == 'cob':
                tr, tc = t['rc']
                if center is None:
                    continue
                cx, cy = center
                px, py = D.cell_x(tc), self.py(tr, tc)
                if (px - cx) ** 2 + (py + 20 - cy) ** 2 <= 220 ** 2:
                    t['saved'] = 'cob'
                    b['saved_cob'] += 1

    def _bungee_resolve(self):
        """一波结束时结算：没被救下的目标被偷走"""
        b = getattr(self, '_bungee_cur', None)
        self._bungee_cur = None
        if not b:
            return
        for t in b['targets']:
            if t['saved']:
                continue
            r, c = t['rc']
            cell = self.cells.get((r, c))
            if cell is None or not cell.plant:
                continue
            name = cell.plant
            cell.plant, cell.plant_hp = None, 0
            cell.pumpkin, cell.pumpkin_hp = False, 0
            cell.ladder = False
            b['stolen'].append(dict(rc=(r, c), plant=name))
            self._record_death(r, c, name, '蹦极', x=D.cell_x(c), cause='偷走')
            self._log('BUNGEE', '蹦极偷走 %d-%d 的%s' % (r, c, name),
                      row=r, col=c,
                      detail='既不在保护伞 3×3 内，也不在冰杀定式下 → 只能靠炮炸，'
                             '这一波没炸到')
            self._log('WARN', '%d-%d %s被蹦极偷走' % (r, c, name), row=r, col=c,
                      detail='w%d 蹦极 %d 只' % (b['wave'], b['n']))
        self.bungee_log.append(b)

    def _tick_joker(self):
        """
        小丑实体（2026-10-19 用户：只做判定太简单）。

        为什么必须实体化：
          「是否严谨控丑」取决于**小丑开盒那一刻站在第几列** —— 这是位置问题。
          查表只能给出"需要 X 秒内点冰"，给不出"这一波到底炸没炸"。
          让它真的走一遍，炸率就是 **实际炸了几只 ÷ 本波小丑数**，不用建模公式。

        时间轴 [精 十]：
          早爆 5%   开盒 440~754cs   开盒后 110cs 炸
          晚爆 95%  开盒 1320~2270cs 开盒后 110cs 炸
          **冻结时开盒计时整段顺延** —— 这正是"早冰控丑"能生效的机制：
          冰把开盒时刻推到"它已经走进曾的射程、且身上带着减速"之后。
        """
        for z in self.zombies:
            if not z.alive or z.kind != '小丑' or z.defused:
                continue
            if z.frozen_until > self.t:
                continue                      # 冻住 → 计时停
            # ★ 2026-10-24：小丑两条腿走 → 减速时开盒 / 引信倒计时都只走 0.5 倍速
            tick = D.TICK * self._anim_rate(z)
            if z.fuse_in < 0:
                z.box_in -= tick
                if z.box_in <= 0:
                    z.fuse_in = D.JOKER_FUSE
                    self._log('JOKER', '小丑开盒（%.1f 列）x=%d'
                              % ((z.x - 40) / 80.0 + 1, z.x), row=z.row)
            else:
                z.fuse_in -= tick
                if z.fuse_in <= 0:
                    self._joker_blast(z)

    def _joker_blast(self, z):
        """爆炸：判定 x±20、y 0~+80，只炸自己这一行"""
        z.alive = False
        bx = z.x
        zy = self.zy(z.row)
        hit = []
        for col in range(1, 10):
            c = self.cells.get((z.row, col))
            if c is None or not c.has_content():
                continue
            if abs(c.x - bx) > D.JOKER_BOOM_DX:
                continue
            py = self.py(z.row)
            if not (zy - 10 <= py <= zy + D.JOKER_BOOM_H + 10):
                continue
            hit.append((col, c))
        # ★★ 2026-10-22 用户：「垫材甚至不该出现在损失名单里面。垫材的死亡不仅
        #   不影响控丑程度、也不应该反复报 L2」。
        #   → 炸到垫材 = 炸在"空地"上，按**炸空**算（垫材是消耗品，本来就是为了挨这一下）。
        pads = []
        killed = []
        for col, c in hit:
            plant, pump = c.wreck()
            nm = plant or '南瓜'
            if nm in D.PAD_PLANT.values() and not pump:
                pads.append('%d-%d %s' % (z.row, col, nm))
                continue
            killed.append('%d-%d %s' % (z.row, col, nm))
            self._record_death(z.row, col, nm, z, cause='小丑爆炸')
            if plant in D.CORE_PLANTS or self._is_core_cell((z.row, col)):
                self._fatal('小丑炸掉 %d-%d 的%s' % (z.row, col, plant),
                            'CORE 植物 · 控丑失败', row=z.row, col=col)
            elif plant and plant not in D.PAD_PLANT.values():
                self._log('WARN', '%d-%d %s被小丑炸毁' % (z.row, col, plant),
                          row=z.row, col=col, detail='小丑开盒 · 非 CORE · 可补种')
        self.joker_boom.append(dict(t=self.t, wave=self.cur_wave, row=z.row,
                                    x=round(bx), killed=killed, pads=pads,
                                    early=bool(z.joker_early)))
        z.joker_res = 'boom' if killed else 'blank'
        self.joker_units.append(dict(wave=self.cur_wave, row=z.row,
                                     early=bool(z.joker_early),
                                     res=z.joker_res, defused=False,
                                     killed=list(killed), pads=list(pads),
                                     frozen=(z.frozen_until > self.t)))
        if killed:
            msg = '小丑爆炸（%.1f 列）炸掉 %s' % ((bx - 40) / 80.0 + 1,
                                                 '、'.join(killed))
        elif pads:
            msg = ('小丑爆炸（%.1f 列）只炸掉垫材 %s → 按**炸空**算'
                   % ((bx - 40) / 80.0 + 1, '、'.join(pads)))
        else:
            msg = '小丑爆炸（%.1f 列）炸空' % ((bx - 40) / 80.0 + 1)
        self._log('JOKER', msg,
                  row=z.row, detail='%s（开盒 %.1fs，本波第 %d 只小丑）'
                  % ('早爆型' if z.joker_early else '晚爆型',
                     D.JOKER_BOX_EARLY[0] / 100.0 if z.joker_early else 13.2,
                     getattr(self, '_joker_n', 0)))

    def _tick_spike_crush(self):
        """巨人砸地刺（用户 2026-10-22）：「巨人可以破坏，其中要砸 1 次地刺、9 次钢地刺」。

        地刺类不挡路、不被啃，所以普通"找目标"的流程里根本不会把它当目标 ——
        巨人是**踩在上面砸**，这里单独处理。

        冰车/投篮车那一路在 `_tick_icecar` 里（碾压判定域重合 → 互相破坏）。
        """
        for z in self.zombies:
            if not z.alive or not z.giant:
                continue
            if z.frozen_until > self.t or z.stall_until > self.t:
                continue
            for col in range(1, 10):
                c = self.cells.get((z.row, col))
                if c is None or not c.plant:
                    continue
                if not D.PLANTS.get(c.plant, {}).get('spike'):
                    continue
                # 巨人的攻击判定域比普通僵尸宽（[精 六] 偏移 20 / 宽 50）
                if not (-40 <= z.x - c.x <= 100):
                    continue
                if z.smash_at <= 0:
                    z.smash_at = self.t + D.SMASH_INTERVAL / \
                        max(0.1, self._anim_rate(z))
                    continue
                if self.t < z.smash_at:
                    continue
                z.smash_at = self.t + D.SMASH_INTERVAL / \
                    max(0.1, self._anim_rate(z))
                self._spike_pop(c, '巨人砸')

    def _tick_icecar(self):
        for z in self.zombies:
            if not z.alive or z.kind != '冰车':
                continue
            # ★ 冰车临界（用户：虽然自己掉血、速度减慢，但**仍然有碾压能力**）
            #   血 < 1/3 起：自动掉血 60/s + 速度减半，碾压判定照旧
            crit = z.hp < z.hp0 * D.DYING_RATIO
            if crit:
                z.hp -= D.DYING_DPS_BIG * D.TICK / 100.0
            if z.frozen_until <= self.t:
                spd = D.ice_car_speed(z.x) * (0.5 if crit else 1.0)
                z.x -= spd * D.TICK
            z.min_x = min(z.min_x, z.x)
            self._ice_trail(z)                     # 车尾（z.x + 80）铺冰道
            for col in range(9, 0, -1):
                c = self.cells.get((z.row, col))
                if c is None or not c.has_content():
                    continue
                if abs(z.x - c.x) > 58:            # 车头（z.x）= 碾压判定
                    continue
                # ★★ 2026-10-22 用户：地刺/地刺王的"攻击判定域就是这个格子"，
                #   冰车/投篮车的碾压判定域与它重合时：**双方互相破坏**。
                #   地刺王（pops_car）能与车同归于尽；地刺只自己碎、车照样过去。
                #   因为判定域是整个格子（AoE），同一 tick 里压在这个格子上的
                #   所有车会**同时全部被破坏** —— 这就是"把地刺种在一堆冰车里"的用法。
                if (c.plant and D.PLANTS.get(c.plant, {}).get('spike')
                        and not c.ash_pending):
                    spec = D.PLANTS[c.plant]
                    if spec.get('pops_car'):
                        z.hp = 0
                        z.alive = False
                        self._log('RESCUE', '%d-%d 的%s与冰车同归于尽'
                                  % (z.row, col, c.plant), row=z.row, col=col,
                                  detail='地刺王 pops_car · 每次碾掉一格车')
                        self.crush.append(dict(t=self.t, wave=z.wave, row=z.row,
                                               col=col, plant=c.plant,
                                               killed_car=True))
                        self._spike_pop(c, '冰车碾压')
                    else:
                        self._spike_pop(c, '冰车碾压')
                        self.crush.append(dict(t=self.t, wave=z.wave, row=z.row,
                                               col=col, plant='地刺'))
                    break
                # ★ 用户："碾压不对已经触发的灰烬（包括窝瓜）生效，
                #   而且可以把'种植即触发'的灰烬直接种在碾压判定区。"
                if c.ash_pending:
                    continue
                plant, pump = c.wreck()
                if plant:
                    self._record_death(z.row, col, plant, z, cause='碾压')
                self.crush.append(dict(t=self.t, wave=z.wave, row=z.row,
                                       col=col, plant=plant))
                self.car_audit.append(dict(wave=z.wave, row=z.row,
                                           min_x=round(z.min_x),
                                           verdict='碾压 %d-%d %s' % (z.row, col, plant or '南瓜'),
                                           crush=True))
                if self.rebuild and plant:
                    self.rebuilds.append(dict(t=self.t, wave=z.wave,
                                              why='%d-%d %s被冰车碾掉' % (z.row, col, plant),
                                              row=z.row, col=col, done=False,
                                              plant=plant))
                if plant in D.CORE_PLANTS or self._is_core_cell((z.row, col)):
                    self._fatal('冰车碾压 %d-%d 的%s' % (z.row, col, plant),
                                '冰车不受减速、不被南瓜阻挡 · 碾压是机制杀',
                                row=z.row, col=col)
                elif plant in D.PAD_PLANT.values():
                    # 垫材被碾 = 消耗品用完，不计损失
                    self._log('INFO', '冰车碾掉垫材 %d-%d %s（消耗品，不计损失）'
                              % (z.row, col, plant), row=z.row, col=col)
                elif plant:
                    self._log('WARN', '冰车碾掉 %d-%d %s' % (z.row, col, plant),
                              row=z.row, col=col,
                              detail='可补种 · 冰道已铺在该格')
                    break

    def _tick_miner(self):
        """矿工（Digger）—— **完整模型**（图鉴 + 《精确数据》，用户 2026-10-24 点名）

        三段：
          ① `dig`  地下挖掘：1.2s/格，**不与植物交互**（不啃、不被啃），一路快到底线；
                   只有能打到地下的伤害才有效（`_hurt` 里判 `pierce`）。
          ② `stun` 出土 → 晕：出土 130cs + 眩晕 350cs（减速时 ×2）。
          ③ `walk` **向右走**：7s/格，从背后啃后场（`rev=True`）。

        挖掘时被磁力菇吸走镐子（`_magnet` 里 `pickaxe_gone()`）→
          **立即出土、向左走（正常方向）、不眩晕**。
        """
        for z in self.zombies:
            if not z.alive or z.kind != '矿工':
                continue
            if z.frozen_until > self.t or z.stall_until > self.t or z.daze_until > self.t:
                continue
            ph = z.phase
            if ph == 'dig':
                z.x -= z.spd * D.TICK
                z.min_x = min(z.min_x, z.x)
                if z.x <= D.MINER_TOP_X:
                    z.x = float(D.MINER_TOP_X)
                    z.phase = 'stun'
                    z.hold_until = self.t + D.MINER_SURFACE_CS + D.MINER_STUN_CS
                    self._log('INFO', '矿工出土 %d 路（x=%d）→ 眩晕 %.2fs'
                              % (z.row, int(z.x),
                                 (D.MINER_SURFACE_CS + D.MINER_STUN_CS) / 100.0),
                              row=z.row,
                              detail='出土 130cs + 晕 350cs；之后**向右**走 7s/格')
                continue
            if ph == 'stun':
                if self.t >= z.hold_until:
                    z.phase = 'walk'
                    z.rev = True
                    z.spd = z.spd_alt or z.spd
                    self._log('INFO', '矿工 %d 路醒来 → 向右啃后场' % z.row, row=z.row)
                continue
            # ---- walk：向右找最近的可啃植物
            target = None
            for col in range(1, 10):
                c = self.cells.get((z.row, col))
                if c is None or not c.has_content():
                    continue
                spec = D.PLANTS.get(c.plant) if c.plant else None
                if (spec and spec.get('no_eat')) or c.tail:
                    continue
                if c.ladder and not z.giant:
                    continue
                if c.x < z.x - D.EAT_OFFSET:
                    continue          # 已经在它身后
                target = c
                break
            if target is not None and z.x + D.EAT_OFFSET >= target.x:
                had = target.plant
                broke = target.take_damage(
                    D.EAT_DPS * D.TICK / 100.0 * self._anim_rate(z))
                if broke == 'plant':
                    self._plant_lost(target, had, z)
                elif broke == 'pumpkin':
                    self._log('WARN', '南瓜被矿工啃穿 %d-%d' % (target.row, target.col),
                              row=target.row, col=target.col)
            else:
                z.x += z.spd * D.TICK

    def _tick_move(self):
        for z in self.zombies:
            if not z.alive:
                continue
            if z.kind == '矿工':
                continue                  # ★ 矿工走路自成一套（见 `_tick_miner`）
            if z.frozen_until > self.t or z.stall_until > self.t:
                continue
            if z.daze_until > self.t:
                continue          # ★ 读报：报纸刚被打掉，发愣 1~2s（不前进也不啃）
            # ★ 起步偏差（《僵尸时间表》）：还没"起步完"就原地不动
            if z.hold_until > self.t:
                continue
            if z.kind == '冰车':
                continue
            # ★ 2026-10-23（《僵尸时间表》）：**撑杆起跳到落地 = 181cs**。
            #   滞空期间不前进、也不啃 —— 以前这里是瞬移（落点立刻生效），
            #   等于把这一跳的时间白白省掉了。落地那一刻才把 x 挪到落点。
            if z.vault_until > 0:
                if self.t >= z.vault_until:
                    z.x = z.vault_to_x
                    z.vault_until = -1
                else:
                    continue
            if z.no_eat_x is not None and z.x > z.no_eat_x:
                z.x -= self._speed_of(z) * D.TICK
                continue
            # ★ 跳跳：不啃植物，一路往前（会跳/越过，模型里就是不停）
            if z.never_eat:
                z.eating = None
                z.x -= self._speed_of(z) * D.TICK
                continue
            # ★ 2026-10-22 舞王滑步：走到 7 列（x≤520）时**快速滑一格**（后退 80px），
            #   滑完就起舞。用户：「走到第 7 列的滑步速度很快」。
            if z.kind == '舞王' and not z.slid and z.x <= D.DANCER_SLIDE_X:
                z.slid = True
                z.x += D.DANCER_SLIDE_PX
                z.phase = 'walk'
                self._log('INFO', '舞王滑步 %d 路：后退一格起舞' % z.row,
                          row=z.row, detail='滑步档 0.79~0.81（与带梯扶梯同档）'
                                           ' · 80px ≈ 100cs')
            # 舞王召伴舞：★ 2026-10-23 《僵尸时间表》—— **生成后 342cs** 最早自然召唤，
            #   之后按 `DANCER_CD` 循环；召出来后自己还要等 200cs 才能啃（表：召唤到舞王啃食）。
            if z.kind == '舞王':
                if z.summoned == 0:
                    z.summoned = z.born_t + D.DANCER_SUMMON_CS
                if self.t >= z.summoned:
                    z.summoned = self.t + D.DANCER_CD
                    z.eat_ready = self.t + D.DANCER_SELF_EAT_CS
                    self._summon(z)
            target = None
            for col in range(9, 0, -1):
                c = self.cells.get((z.row, col))
                if c is None or not c.has_content():
                    continue
                if c.has_content():
                    spec = D.PLANTS.get(c.plant) if c.plant else None
                    # ★ 地刺一类"不挡路、不被啃"的植物：僵尸直接走过去
                    if (spec and spec.get('no_eat')) or c.tail:
                        continue
                # ★ 2026-10-22 梯子南瓜：只有巨人和冰车起作用，其它僵尸**直接走过去**
                #   （用户：「植物会被巨人、车以外的其它僵尸直接无视」）
                if c.ladder and not z.giant:
                    continue
                if z.x < c.x - D.EAT_OFFSET:
                    continue          # ★ 已经走过这一格 → 继续往左找（原来会从背后啃）
                if z.x <= c.x + D.EAT_OFFSET:
                    target = c
                break
            # ★ 撑杆跳：飞跃第一个植物，落地在「目标植物 x − 70」[精 11.2]，
            #   高坚果挡得住（不跳，改成正常啃）
            if (z.kind == '撑杆' and not z.vaulted and target is not None
                    and not self._is_tall(target)):
                z.vaulted = True
                z.vault_until = self.t + D.ACT_CS['撑杆起跳到落地']
                z.vault_to_x = target.x - 70
                z.phase = 'walk'
                self._log('INFO', '撑杆跃过 %d-%d %s'
                          % (target.row, target.col, target.plant or '南瓜'),
                          row=target.row, col=target.col,
                          detail='滞空 %dcs（表）→ 落地 x=%d（目标 x−70）· 之后按慢速档走'
                                 % (D.ACT_CS['撑杆起跳到落地'], int(z.vault_to_x)))
                continue
            # ★ 2026-10-23 海豚骑海豚跳：与撑杆同构（飞跃第一个植物），
            #   但滞空 = 表的「海豚跳跃植物」232cs，落点沿用撑杆口径（目标 x−70）。
            #   跳过后水豚消失 → 速度回落到 4.7s/格（`spd_alt`），见 `_speed_of`。
            if (z.kind == '海豚' and not z.vaulted and target is not None
                    and not self._is_tall(target)):
                z.vaulted = True
                z.vault_until = self.t + D.ACT_CS['海豚跳跃植物']
                z.vault_to_x = target.x - 70
                z.phase = 'walk'
                self._log('INFO', '海豚跃过 %d-%d %s'
                          % (target.row, target.col, target.plant or '南瓜'),
                          row=target.row, col=target.col,
                          detail='滞空 %dcs → 落地 x=%d · 之后按 4.7s/格 走'
                                 % (D.ACT_CS['海豚跳跃植物'], int(z.vault_to_x)))
                continue
            if target is not None and target.plant == '大蒜':
                # ★★ 2026-10-20：大蒜不是"被啃的墙"，它**啃一口就换行**。
                #   [知识库 14] 1 路→2、6 路→5、中间路随机二选一。
                #   所以这里不进入普通啃食流程 —— 扣一口血就把它赶走。
                self._garlic(z, target)
                continue
            # ★★ 2026-10-25 **模型修正**：**小丑不啃植物**。
            #   小丑的"盒子里的小丑"是按**开盒计时器**（`_tick_joker`）走的，
            #   到点就原地炸，跟它面前有没有植物无关；原版里它会走到植物跟前
            #   站着等炸，**绝不会像普通僵尸那样啃**。
            #   原来让它走普通啃食分支，于是"小丑把 5 列玉米炮啃了"这种
            #   原版根本不存在的崩阵方式（FE.弦十四炮 6/6 都是这么崩的）。
            if z.kind == '小丑':
                continue
            if target is not None:
                # ★ 表：召唤到啃食（舞王 200cs / 伴舞 151cs）—— 这段时间内不啃
                if z.eat_ready > self.t:
                    continue
                z.eating = target
                # ★ 巨人：举锤砸（周期 330cs、单次 1800），不是"啃 100dps"
                if z.giant:
                    if z.smash_at <= 0:
                        z.smash_at = self.t + D.SMASH_INTERVAL
                    elif self.t >= z.smash_at:
                        had = target.plant
                        had_ladder = target.ladder
                        broke = target.take_damage(D.SMASH_DMG)
                        # ★ 2026-10-24：巨人两条腿走 → 减速时动作只剩 0.5 倍速，
                        #   举锤周期同步拉长（330 → 660cs）
                        z.smash_at = self.t + D.SMASH_INTERVAL / \
                            max(0.1, self._anim_rate(z))
                        if broke == 'plant':
                            self._plant_lost(target, had, z)
                        elif broke == 'pumpkin':
                            self._log('WARN', '南瓜被 %s 砸穿 %d-%d'
                                      % (z.kind, target.row, target.col),
                                      row=target.row, col=target.col, detail='南瓜 125 可补')
                    continue
                loss = z.dmg * D.TICK / 100.0 * self._anim_rate(z)
                had = target.plant
                had_ladder = target.ladder
                broke = target.take_damage(loss)
                if broke == 'plant':
                    self._plant_lost(target, had, z)
                elif broke == 'pumpkin':
                    self._log('WARN', '南瓜被打穿 %d-%d（%s）' % (target.row, target.col, z.kind),
                              row=target.row, col=target.col,
                              detail='南瓜 125 可补' + (' · 梯子一并消失' if had_ladder else ''))
            else:
                z.eating = None
                z.x -= self._speed_of(z) * D.TICK

    def _is_core_cell(self, rc):
        """这一格算不算 CORE：植物名命中 `D.CORE_PLANTS` **或** 用户贴了 core 标签"""
        cell = self.array.get(rc) or {}
        return bool(cell.get('core'))

    def _plant_lost(self, c, name, z, by=None):
        """`z` = 造成损失的僵尸；`by` 可以顶替它的名字/位置（篮球这类没有实体时用）"""
        _kind = (by or (z.kind if z is not None else '僵尸'))
        _x = (z.x if z is not None else c.x)
        if name not in D.PAD_PLANT.values():
            self._record_death(c.row, c.col, name, _kind, x=_x, cause='啃食')
        if name in D.CORE_PLANTS or self._is_core_cell((c.row, c.col)):
            self._fatal('%d-%d 的%s被%s啃掉' % (c.row, c.col, name, _kind),
                        'CORE 植物 · 阵线已被突破到 %d 列（x=%d）' % (c.col, _x),
                        row=c.row, col=c.col)
        else:
            if name in D.PAD_PLANT.values():
                # ★ 2026-10-22 用户：「垫材甚至不该出现在损失名单里面」
                #   —— 垫材就是拿来换僵尸一顿咬的消耗品，吃掉就吃掉，
                #     不进 plants_lost、也不升级成 L2。
                self._log('INFO', '垫材 %d-%d %s 被%s吃掉（消耗品，不计损失）'
                          % (c.row, c.col, name, _kind), row=c.row, col=c.col)
            else:
                self._log('WARN', '%d-%d %s被%s啃掉' % (c.row, c.col, name, _kind),
                          row=c.row, col=c.col, detail='非 CORE · 可补种')
        # ★ 快速/极速的"死了就补"：连非 CORE（大喷/荷叶/伞/花）也进重建队列。
        #   否则快速关没有救场，5-7 补种的大喷一被冰车碾就永远没了。
        if self.rebuild and c.row and c.col:
            spec = self.array.get((c.row, c.col))
            if spec and spec.get('plant') and not any(
                    r['row'] == c.row and r['col'] == c.col and not r['done']
                    for r in self.rebuilds):
                self.rebuilds.append(dict(t=self.t, wave=self.cur_wave,
                                          why='%d-%d %s被%s啃掉' % (c.row, c.col, name, _kind),
                                          row=c.row, col=c.col, done=False, plant=name))

    def _garlic(self, z, cell):
        """
        僵尸啃到大蒜 → 扣一口血 + **换行**。

        ★★ 2026-10-20 更正（用户）：**大蒜不能跨水陆** ——
          陆路僵尸吃蒜不会下水，水路僵尸吃蒜也不会爬上岸。
          所以换行的目标行必须**与当前行同属一种地形**。

        PE 场地（1/2/5/6 陆路、3/4 水池）四个合法边：

          2-9 大蒜 → 僵尸只能去 **1 路**   （3 路是水，去不了）
          5-9 大蒜 → 僵尸只能去 **6 路**   （4 路是水，去不了）
          反向：1→2、6→5；水路内部 3↔4

        这就是为什么极速关的 2-9 / 5-9 大蒜不是"分流"而是**单向驱赶**：
        岸路的压力整股灌进边路，边路的 CORE（3 列冰瓜）要独力吃下。
        """
        opts = D.GARLIC_SWAP.get(z.row) or ()
        # 双保险：再按地形过滤一遍（表写错也翻不了车）
        water = z.row in self.fld.water
        opts = tuple(r for r in opts if (r in self.fld.water) == water)
        if not opts:
            return
        bite = D.ASH_DMG if z.giant else D.GARLIC_BITE
        cell.plant_hp -= bite
        gone = cell.plant_hp <= 0
        if gone:
            cell.plant = None
            cell.plant_hp = 0
        old_row = z.row
        z.row = int(self.rng.choice(opts))
        # 换行后往回顶一点点（大蒜把僵尸推出去），避免它立刻又啃回同一格
        z.x += 6
        self.garlic_swaps.append(dict(t=self.t, wave=self.cur_wave, kind=z.kind,
                                      frm=old_row, to=z.row, col=cell.col,
                                      broke=gone))
        self._log('INFO', '大蒜换行：%s %d 路 → %d 路（%d-%d）'
                  % (z.kind, old_row, z.row, cell.row, cell.col),
                  row=cell.row, col=cell.col,
                  detail='大蒜剩 %d 血%s · 不跨水陆，目标行唯一'
                         % (max(0, cell.plant_hp),
                            '（这一口啃碎了）' if gone else ''))

    def _tick_garlic(self):
        """
        极速关的大蒜维护：2-9 / 5-9 空了就补（用大蒜卡，CD 7.5s）。
        被啃碎是常态 —— 一口 100 血、400 血能挨 4 口，两个位轮流碎。
        """
        if not self.garlic_slots or self.t % 100:
            return
        for rc in self.garlic_slots:
            cell = self.cells.get(rc)
            if cell is None:
                cell = self.cells[rc] = Cell(rc[0], rc[1])
            if cell.plant == '大蒜' and cell.plant_hp > 0:
                continue
            if cell.iced or cell.crater_until > self.t:
                continue
            if not self._try_card('大蒜'):
                return
            self._plant_into(cell, '大蒜')
            self._log('REPAIR', '补种大蒜 %d-%d' % rc, row=rc[0], col=rc[1],
                      detail='极速关：无冰车/投篮 → 核换大蒜，把岸路僵尸赶去边路')

    def _tick_struct_fog(self):
        """
        极速关（出怪里有冰车/投篮）：大蒜会被车碾掉，改用**结构**抬丑抗 ——
        在 2-7 / 5-7 种大喷。

        用户 2026-10-20（第 14 轮）："在有冰车或投篮车的极速关不应该带大蒜，
        而仅仅是 2-7,5-7 种大喷提高结构丑抗"。
        5-7 被车压的概率不低，被压就重试；大喷卡 7.5s CD 自己会限住频率。
        """
        if not self.struct_fog_slots or self.t % 100:
            return
        for rc in self.struct_fog_slots:
            cell = self.cells.get(rc)
            if cell is None:
                cell = self.cells[rc] = Cell(rc[0], rc[1])
            if cell.plant == '大喷菇' and cell.plant_hp > 0:
                continue
            if cell.plant is not None and cell.plant != '大喷菇':
                continue
            if cell.iced or cell.crater_until > self.t:
                continue
            if not self._try_card('大喷菇'):
                return
            self._plant_into(cell, '大喷菇')
            # 时间轴上的 F 标记由 _try_card 记的 action 负责，这里只记账
            self.fog_fix.append(dict(t=self.t, wave=max(1, self.cur_wave),
                                     row=rc[0], col=rc[1]))
            self._log('REPAIR', '结构补种大喷 %d-%d' % rc, row=rc[0], col=rc[1],
                      detail='极速关有冰车/投篮：大蒜会被碾，改种大喷抬丑抗')

    def _next_target(self, z):
        """这只僵尸接下来会啃哪一格（和 _tick_move 用同一套判定）"""
        for col in range(9, 0, -1):
            c = self.cells.get((z.row, col))
            if c is None or not c.has_content():
                continue
            spec = D.PLANTS.get(c.plant) if c.plant else None
            if spec and spec.get('no_eat'):
                continue                  # 地刺一类：走过去，不啃
            if c.ladder and not z.giant:
                continue                  # 梯子南瓜：除巨人外直接走过去
            if z.x < c.x - D.EAT_OFFSET:
                continue
            return c
        return None

    # ------------------------------------------------ 场况查询（阵解栏用）
    def plant_counts(self):
        """
        场上各植物的数量（阵解栏的条件要问"某种植物还有几个"）。

        ★ 存冰在阵上是"睡着的寒冰菇"：算 `存冰`，也同时算 `寒冰菇`，
          因为玩家脑子里的名字就是寒冰菇 —— 统一说法就靠这一层映射。
        """
        cnt = {}
        for c in self.cells.values():
            if not c.plant or c.plant == '存冰':
                continue
            cnt[c.plant] = cnt.get(c.plant, 0) + 1
        ice = self.ice_stock
        if ice:
            cnt['寒冰菇'] = cnt.get('寒冰菇', 0) + ice
            cnt['存冰'] = ice
        return cnt

    def plan_ctx(self):
        """给阵解的条件/触发器用的一份只读快照"""
        ops_by_wave = {}
        for a in self.actions:
            if a.get('ok'):
                ops_by_wave.setdefault(a.get('wave'), []).append(a['name'])
        return dict(
            t=self.t, wave=max(1, self.cur_wave),
            card_ready=dict(self.card_ready),
            avg_gap=self._avg_gap(), ice_stock=self.ice_stock, sun=self.sun,
            plants=self.plant_counts(),
            cells={rc: c.plant for rc, c in self.cells.items() if c.plant},
            ops_by_wave=ops_by_wave)

    def activate_ice(self, rc):
        """
        在 rc 落一颗咖啡豆 → 唤醒那格睡着的寒冰菇 → 立刻全场冰冻。

        ★ v0.3 统一说法：以前这一步叫"点存冰"，现在就是"在某格种咖啡豆"。
        """
        rc = tuple(rc)
        if self.temp_ice.get(rc):
            self.temp_ice[rc] = False
            self._log('ICE', '咖啡豆唤醒 %d-%d（前场临时位 · 剩 %d 个）'
                      % (rc[0], rc[1], self.ice_stock), row=rc[0], col=rc[1])
            self._freeze()
            return True
        if self.ice_slots.get(rc):
            self.ice_slots[rc] = False
            self.ice_coffee_n = getattr(self, 'ice_coffee_n', 0) + 1
            self._log('ICE', '咖啡豆唤醒 %d-%d（剩 %d 个）'
                      % (rc[0], rc[1], self.ice_stock), row=rc[0], col=rc[1])
            self._freeze()
            return True
        # ★ 2026-10-22：普通格子上睡着的蘑菇也能被咖啡豆唤醒
        #   （用户口径：咖啡豆唤醒"所在格的蘑菇"，唤醒后**永久清醒**）
        cell = self.cells.get(rc)
        if cell is not None and cell.plant in D.MUSHROOMS and not cell.awake:
            cell.awake = True
            if cell.plant == '寒冰菇':
                self._log('ICE', '咖啡豆唤醒 %d-%d 的寒冰菇 → 全场冰冻'
                          % (rc[0], rc[1]), row=rc[0], col=rc[1])
                self._freeze()
            else:
                self._log('ICE', '咖啡豆唤醒 %d-%d 的%s（永久清醒）'
                          % (rc[0], rc[1], cell.plant), row=rc[0], col=rc[1])
            return True
        return False

    def _tick_globals(self):
        """全场判定层：每 tick 让阵解看一眼"条件成立了吗"，成立就做"""
        if self.globals_tick is None:
            return
        try:
            self.globals_tick(self)
        except Exception:                                    # noqa: BLE001
            self.globals_tick = None       # 出过一次错就别每 tick 抛了

    # ------------------------------------------------ 救场层
    def _tick_rescue(self):
        """
        ★ 2026-10-18 按用户口径重写（原版是我自己推的，不对）

        用户原话：
          "橄榄跑到第 6 列时，如果感觉到有啃大喷的可能（判定依据可以是血量还比较高），
           就在这个格子里面下垫材，就挡得住。"
          "这个阵除了垫材，**唯一的救场就是窝瓜**，一般用来稳定缓解 **6 路**压力
           （1 路也可以，但 1 路压力比 6 路大的情况很少见）。"
          "w10 开始时需要它种在 5-9 压冰车腾出核坑位，这时候窝瓜不要被占用。"

        所以救场只有两条，而且都很窄：
          ① 垫材：只在 **1 / 6 路**、僵尸走到 **第 6 列**、且**血量还高**时下
             （普通僵尸 270 血，走到这儿基本已被冰瓜打死，不用浪费垫材）
          ② 窝瓜：只用于 **6 路**（1 路次选）减压；w10 保核坑期间禁用
        """
        # ★ 2026-10-22 修：阵解自带的救场层（`rescue_simple` / `rescue`）**不受**
        #   内置救场开关 `rescue` 管。原来先判 `self.rescue` 再判 `rescue_tick`，
        #   而"选了阵解"时 `run_once` 会把 `rescue` 置 False
        #   → 阵解里写的救场层一直是死代码，从来没跑过。
        if self.rescue_tick is not None:
            # ★ v0.2 阵解栏：救场层换成"编辑出来的规则"，由 plan 侧驱动
            self.rescue_tick(self)
            return
        if not self.rescue:
            return

        self.try_stall()
        if self.t < self.tomato_busy_until:
            self._rescue_ice_emergency()
            return
        self.try_wogua()
        self._rescue_ice_emergency()

    def stall_at(self, rc, cards=None):
        """
        在**指定格子**下垫材（小喷菇 / 花盆 / 阳光菇 / 胆小菇）挡僵尸。

        ★ v0.3：以前垫材只能下在固定的 STALL_SLOTS（1/5/6 列的 6 列位），
          那是"救场自动挑位"的口径。现在阵解里可以直接写"在某格种小喷菇"，
          这条是它的执行体。

        ★ 2026-10-22 用户口径：**巨人一锤就把 300hp 的垫材砸没**，
          所以钉住巨人的时长是砸击周期 `STALL_CS_GIANT`（330cs），不是啃食的 300cs。
          `self.pad_fail` 记录失败原因，供阵解层区分"没窗口"/"没卡"。
        """
        self.pad_fail = None
        cards = cards or D.PAD_CARDS
        rc = (int(rc[0]), int(rc[1]))
        cell = self.cells.get(rc)
        if cell is None:
            cell = self.cells[rc] = Cell(rc[0], rc[1])
        if cell.plant is not None or cell.tail or cell.grave:
            self.pad_fail = 'occupied'
            return False
        # ★ 水上要先荷叶、屋顶要先花盆（自动补基座）
        if not self._base_ok(rc):
            if not self._seed_base(rc):
                self.pad_fail = 'occupied'
                return False
        cx = D.cell_x(rc[1])
        zs = [z for z in self.by_row.get(rc[0], ())
              if z.alive and z.hp > 0 and z.kind != '冰车'
              and z.stall_until <= self.t
              and -40 <= z.x - cx <= 170]
        if not zs:
            self.pad_fail = 'no_target'
            return False
        used = next((nm for nm in cards if self._try_card(nm)), None)
        if used is None:
            self.pad_fail = 'no_card'
            return False
        z = min(zs, key=lambda x: x.x)
        self._plant_into(cell, D.PAD_PLANT.get(used, '小喷菇'))
        z.stall_until = self.t + (D.STALL_CS_GIANT if z.giant
                                  else (D.STALL_CS_SLOWED if z.slowed_until > self.t
                                        else D.STALL_CS))
        z.rescued = True
        z.stall_n = getattr(z, 'stall_n', 0) + 1
        self.last_rescue[z.row] = self.t
        self._log('RESCUE', '%s 种在 %d-%d（挡 %s，第 %d 张）'
                  % (used, rc[0], rc[1], z.kind, z.stall_n),
                  row=rc[0], col=rc[1],
                  detail='僵尸 x=%d hp=%d → 钉 %.1fs'
                         % (z.x, z.hp, (z.stall_until - self.t) / 100.0))
        return True

    def try_stall(self, rows=None, cards=None):
        """
        ① 垫材：1/6 路（5 路次之），只要僵尸能打到 6 列就下，CD 好了就下。

        ★ v0.2：从 `_tick_rescue` 里原样抽出来（行为不变），
          阵解栏的救场规则可以用 `rows` 限定只救哪几路，
          用 `cards` 限定只能用哪张垫材卡（轨道里排"垫材"时就这样调用）。
        """
        cands = []
        for row in (rows or (6, 5, 1)):
            if row not in self.by_row:
                continue                 # ★ 5 行场地没有 6 路
            col_spot = D.STALL_SLOTS.get(row)
            if col_spot is None:
                continue
            cx = D.cell_x(col_spot)
            # 窝瓜刚在这条路强杀过 → 战线前推，这几秒把垫材让给另一路
            if row == 6 and self.t - self.tomato_used_at < D.TOMATO_PUSH_CS:
                continue
            for z in self.by_row[row]:
                if z.kind == '冰车' or z.hp <= 0 or not z.alive:
                    continue
                if z.stall_until > self.t:
                    continue
                # 各路的落点不同：6 路/1 路在 6 列（cx=440），5 路在 7 列（cx=520）
                if not (cx + 10 <= z.x <= cx + 75):
                    continue
                # ★ 巨人只要还活着就必须处理（残血巨人照样一锤砸掉植物），
                #   所以血量门槛对巨人豁免 —— 用户：巨人必须打满血才解除威胁
                if z.hp <= D.STALL_HP and not z.giant:
                    continue
                if getattr(z, 'stall_n', 0) >= 8:
                    continue          # 同一只最多钉 8 次（≈48s），再多就是白喂
                # 危险度 = 距本路最靠前 CORE 的剩余距离（越小越危险）
                # ★ 再加上"饥饿"修正：某路太久没被救，威胁值下调（否则 1 路永远轮不到）
                # ★ 再加"已钉次数"惩罚：被钉了很多次的僵尸让位给新来的
                idle = self.t - self.last_rescue.get(row, 0)
                threat = (z.x - D.CORE_X.get(row, 200) - idle * D.HUNGER_K
                          + getattr(z, 'stall_n', 0) * 60)
                cands.append((threat, z.x, row, col_spot, z))
        if not cands:
            return False
        cands.sort(key=lambda c: c[:4])   # 同一时刻刷出 → x 会完全相同，别再比 Zombie
        _, _, row, col_spot, z = cands[0]
        if cards:
            used = next((nm for nm in cards if self._try_card(nm)), None)
        else:
            used = next((nm for nm in D.PAD_CARDS if self._try_card(nm)), None)
        if not used:
            self.pad_fail = 'no_card'
            return False
        z.stall_until = self.t + (D.STALL_CS_GIANT if z.giant
                                  else (D.STALL_CS_SLOWED if z.slowed_until > self.t
                                        else D.STALL_CS))
        z.rescued = True
        z.stall_n = getattr(z, 'stall_n', 0) + 1
        self.last_rescue[row] = self.t
        self._log('RESCUE', '%s 下在 %d-%d（挡 %s，第 %d 张）'
                  % (used, row, col_spot, z.kind, z.stall_n),
                  row=row, col=col_spot,
                  detail='僵尸 x=%d hp=%d → 钉 %.1fs'
                         % (z.x, z.hp, (z.stall_until - self.t) / 100.0))
        return True

    def try_wogua(self, rows=None):
        """
        ② 窝瓜：6 路巨人**开始对大喷做攻击动作**时强杀；另有"重甲逼近 CORE 3 格"
        的硬底线。★ v0.2：原样抽出，阵解栏可用 `rows` 限定救援路。
        """
        wogua = []
        for row in (rows or (6, 5, 2, 1)):
            if row not in self.by_row:
                continue                 # ★ 5 行场地没有 6 路
            lo, hi = D.WOGUA_WIN.get(row, (340, 480))
            for z in self.by_row[row]:
                if z.hp <= 0 or not z.alive or z.rescued and z.stall_until > self.t:
                    continue
                if not (lo <= z.x <= hi):
                    continue
                if not (z.giant or z.hp >= D.WOGUA_HP):
                    continue
                wogua.append((z.x - hi, z))
        if not wogua:
            return False
        wogua.sort(key=lambda p: p[0])    # 同上：不能用 (float, Zombie) 全序
        hit = wogua[0][1]
        if not self._try_card('窝瓜'):
            return False
        row = hit.row
        hp0 = hit.hp
        self._hurt(hit, D.ASH_DMG, True, src='wogua')
        hit.rescued = True
        self.tomato_used_at = self.t
        self._log('RESCUE', '窝瓜强杀 %d 路的%s' % (row, hit.kind), row=row,
                  detail='x=%d（%.1f 列）hp=%d → 战线前推，垫材转给另一路'
                         % (hit.x, (hit.x - 40) / 80.0 + 1, hp0))
        return True

    def _rescue_ice_emergency(self):
        """
        真·救急点存冰。

        ★ 触发条件收得很窄，只有一条真正成立：
          **某只僵尸下一口要落的格子，是一个"没南瓜的 CORE 植物"**。
          本阵里满足这条的其实只有 5-5 / 5-6 两个裸曾（1-3 / 6-3 的冰瓜都在南瓜里，
          1-4/1-5/6-4/6-5 的大喷不算 CORE）。红眼一锤 1800 就能秒掉 300 血的曾，
          而曾没了就是不可逆的崩阵 —— 拿一个存冰换，天经地义。

        另外还要满足：
          ① 距离上一次冰冻 > 3s（不要连着冻）
          ② 距离上一次救急 > 15s
          ③ 手上真的有存冰
        """
        if self.ice_stock <= 0 or self.t < self.ice_emerg_cd:
            return
        # ★ 2026-10-20：w19 / w20 期间**保住最后一个存冰**给 w20 的冰杀蹦极。
        #   实测变速 seed5：w19 救急把最后 1 个冰点掉（救的是 2-6 裸曾，150 阳光），
        #   结果 w20 蹦极没冰 —— 损失是整片后场，账完全不划算。
        if self.ice_stock <= 1 and self.cur_wave >= 19:
            return
        if self.t - self.last_freeze_t < D.ICE_EMERG_GAP:
            return
        # ★ 只有"别的牌全没了"才轮到存冰：
        #   两张垫材 + 窝瓜只要有一张转好，就先用它们，不许动轨道口粮。
        for k in ('垫材', '垫材2', '窝瓜'):
            if self.card_ready.get(k, 0) <= self.t:
                return
        hot = None
        for row in range(1, self.rows + 1):
            for z in self.by_row[row]:
                if not z.alive or z.kind == '冰车':
                    continue
                if not (z.giant or z.hp > 800):
                    continue
                c = self._next_target(z)
                if c is None or c.plant not in D.CORE_PLANTS or c.pumpkin:
                    continue
                if z.x > c.x + D.ICE_EMERG_REACH:      # 还在远处就不算"要砸"
                    continue
                if hot is None or z.x < hot.x:
                    hot = z
        if hot is None:
            return False
        if self._use_stock_ice('救急：%d 路 %s 要砸 %d-%d 的裸%s'
                               % (hot.row, hot.kind, hot.row,
                                  self._next_target(hot).col,
                                  self._next_target(hot).plant)):
            self.ice_emerg_cd = self.t + D.ICE_EMERG_CD
            self.ice_emerg_n += 1
            return True
        return False

    def _reserve_tomato(self):
        """
        w10 开局：窝瓜固定用于压冰车 / 保 5-9 核坑。

        ★ 2026-10-19 按档位收窄（用户）：
          慢速/变速 → 要压（有冰车、选卡里有窝瓜）
          快速      → 选卡里没有窝瓜，不压
          极速      → 出怪里根本没有冰车，不需要
        """
        if not self.wogua_flag:
            return
        self.tomato_busy_until = self.t + D.TOMATO_RESERVE_CS
        c = self.cells.get((5, 9))
        if c is not None and c.iced:
            c.iced = False
            c.ice_until = -1
            self._log('RESCUE', '窝瓜压 5-9 冰车，保核坑位', row=5, col=9,
                      detail='w10 固定动作 · 冰道已清')
        else:
            self._log('INFO', 'w10 预留窝瓜给 5-9 核坑', row=5, col=9,
                      detail='本轮救场不得占用窝瓜')
        # ★ 这里**不能**把窝瓜花掉 —— 真正的消耗在 `窝瓜压车` 动作里。
        #   原来先 `_try_card('窝瓜')` 预扣，导致 w10 真该压车时卡已在 CD。

    # ------------------------------------------------ 植物输出
    def _tick_sun(self, c, spec):
        """阳光生产：向日葵 25/24s、双子花 50/24s、阳光菇 小 15 → 大 25。

        ⚠️ 生产节奏（24s / 首次 ~6s / 阳光菇 120s 长大）用的是 wiki 常用值，
           没有在 [精] 里逐 cs 标注 —— 只影响经济收支，不影响波长与 CD 结论。
        """
        if spec.get('sun_small') is not None:
            if not c.grown and self.t - getattr(c, 'sun_born', 0) >= spec.get(
                    'grow_cs', 12000):
                c.grown = True
                self._log('INFO', '%d-%d 的阳光菇长大了' % (c.row, c.col),
                          row=c.row, col=c.col, detail='小 15 → 大 25')
            amount = spec['sun_big'] if c.grown else spec['sun_small']
        else:
            amount = spec['sun']
        c.sun_t += D.TICK
        if c.sun_t < spec['interval']:
            return
        c.sun_t = 0
        self.sun = min(D.SUN_CAP, self.sun + amount)
        if self.sun >= D.SUN_CAP:
            self.sun_capped = True
        if self.sun > self.sun_peak:
            self.sun_peak = self.sun

    def _tick_plants(self):
        for c in self.cells.values():
            if not c.plant:
                continue
            spec = D.PLANTS.get(c.plant)
            if not spec:
                continue
            # ★ 2026-10-22：白天场的蘑菇是**睡着的**，没被咖啡豆唤醒就完全无行为
            if not c.awake:
                continue
            if spec.get('sun') or spec.get('sun_small'):
                self._tick_sun(c, spec)
            # ★ 磁力菇：每 50cs 看一次，把范围内的金属护具吸走
            if spec.get('magnet'):
                c.magnet_t += D.TICK
                if c.magnet_t >= 50:
                    c.magnet_t = 0
                    self._magnet(c, spec['magnet'])
                continue
            if spec.get('shoot'):
                c.atk_t += D.TICK
                if c.atk_t >= spec['interval']:
                    c.atk_t = 0
                    self._shoot(c, spec)
                continue
            if not spec['interval'] or not spec['dmg']:
                continue
            c.atk_t += D.TICK
            if c.atk_t < spec['interval']:
                continue
            c.atk_t = 0
            self._attack(c, spec)

    def _magnet_has(self, z):
        """磁力菇还能从这只身上吸走东西吗（**只吸金属**，用户 2026-10-23）"""
        k = z.kind
        if k not in D.MAGNET_METAL or k in D.MAGNET_SKIP:
            return False
        if k in D.SHIELD2:
            return z.shield > 0
        if k in D.ARMOR:
            return z.armor > 0
        if k == '矿工':
            return z.phase == 'dig'      # 只有挖地时才有镐子可吸
        if k == '小丑':
            return not z.defused
        if k == '跳跳':
            return z.never_eat          # 还骑着跳跳杆
        return False

    def _magnet(self, c, rng_pair):
        """磁力菇：吸走**金属物件**（[精 六] R=270；对啃食者 R=320）。

        ★ 2026-10-23 用户更正：能吸的只有 7 种 ——
          铁桶 / 铁门 / 橄榄头盔 / 梯子 / 小丑的盒子 / 矿工的镐子 / 跳跳的跳跳杆。
          **报纸是纸、路障锥是塑料，吸不动**（上一版把报纸当"二类防具"一起吸掉了）。
        """
        r_norm, r_eat = rng_pair
        best = None
        for z in self.by_row[c.row]:
            if not z.alive or not self._magnet_has(z):
                continue
            r = r_eat if z.eating is not None else r_norm
            d = abs(z.x - c.x)
            if d <= r and (best is None or d < best[0]):
                best = (d, z)
        if best is None:
            return
        z = best[1]
        if z.kind in D.SHIELD2:
            # 二类防具（铁门 / 梯子）走 `shield`，吸走 = 盾清零，本体血不动
            drop = z.shield
            z.shield = 0
            self._log('REPAIR', '磁力菇吸走 %d 路 %s 的%s（−%d 二类防具血）'
                      % (z.row, z.kind,
                         '铁门' if z.kind == '铁门' else '梯子', drop),
                      row=c.row, col=c.col,
                      detail='R=%d · 剩下的只有本体血 %d' % (r_norm, z.hp))
            return
        if z.kind in D.ARMOR:
            drop = z.armor
            z.armor = 0
            z.hp0 = max(1, z.hp0 - drop)
            z.hp = min(z.hp, z.hp0)
            self._log('REPAIR', '磁力菇吸走 %d 路 %s 的金属护具（−%d 护甲血）'
                      % (z.row, z.kind, drop), row=c.row, col=c.col,
                      detail='R=%d · 剩下的只有本体血' % r_norm)
            return
        if z.kind == '小丑':
            # 盒子被吸走 → **永久无法爆炸**（正在开盒也一样，直接掐掉引信）
            z.defused = True
            z.fuse_in = -1
            z.box_in = 10 ** 9
            self._log('REPAIR', '磁力菇吸走 %d 路 小丑的盒子 → 它再也不会爆炸'
                      % z.row, row=c.row, col=c.col,
                      detail='盒子是金属；本体血 %d 照旧' % z.hp)
            return
        if z.kind == '矿工':
            # ★ 2026-10-24 用户：「挖掘时被磁力菇吸镐子 → **立即出土、向左走、不眩晕**」
            z.phase = 'walk'
            z.rev = False
            z.x = float(D.MINER_TOP_X)
            z.hold_until = -1
            self._log('REPAIR', '磁力菇吸走 %d 路 矿工的镐子 → 立即出土、向左走（不眩晕）'
                      % z.row, row=c.row, col=c.col,
                      detail='R=%d · 之后按 7s/格 正常啃' % r_norm)
            return
        if z.kind == '跳跳':
            # 跳跳杆被吸走 → 变普通步行僵尸，正常啃食、不再翻越
            z.never_eat = False
            z.spd = D.CELL_W / float(D.POGO_WALK_CS)
            z.spd_alt = 0.0
            z.phase = 'walk'
            self._log('REPAIR', '磁力菇吸走 %d 路 跳跳的跳跳杆 → 改为步行啃食'
                      % z.row, row=c.row, col=c.col,
                      detail='R=%d · 之后按 %.1fs/格 走' % (r_norm,
                                                          D.POGO_WALK_CS / 100.0))

    def _shoot(self, c, spec):
        """直线射手（双向射手 / 机枪射手 …）。

        简化模型：不做逐颗子弹飞行，**按命中延迟把伤害排进 pending**，
        判定沿用"攻击框与受击框相交"。火炬树桩在**同一行更右边**时，
        豌豆穿过它 → 伤害 ×2（[精 七] 火豌豆），并带 40/n 溅射（上限 13）。
        """
        sh = spec['shoot']
        dmg = sh['dmg']
        torch = self._torch_ahead(c)
        if torch:
            dmg *= torch['mult']
        for d in sh.get('delays', (25,)):
            for _ in range(sh.get('front', 1)):
                self.pending.append((self.t + d, c.row, 1, c.x + 60, 9000, dmg, False))
            for _ in range(sh.get('back', 0)):
                self.pending.append((self.t + d, c.row, 1, 0, c.x - 20, dmg, False))

    def _hurt(self, z, dmg, pierce=False, src=None):
        """对一只僵尸造成伤害。

        ★ 2026-10-23 用户给出的防具口径：
          二类防具（扶梯 / 报纸 / 铁门）**只挡平射** ——
          AoE、投掷子弹、喷雾(`pierce=True`) 直接打本体。
          一类防具折在总血量里（对非灰烬伤害等价），灰烬/炮/窝瓜 1800 直接击杀。

        ★★ 2026-10-24 用户：「矿工挖掘时**仅灰烬（P, A, A', N）**可以造成伤害，
          窝瓜 / 冰瓜 / 喷雾或别的其他的都不行」

        `src` = 伤害来源（'ash' 灰烬：樱桃 A / 辣椒 A' / 毁灭菇 N / 玉米炮 P；
                 'wogua' 窝瓜；None = 其它普通伤害）。
        `pierce=True` 的调用点：冰瓜(抛射) / 大喷菇·忧郁菇(喷雾穿透) / 溅射 /
        灰烬 / 玉米炮 / 窝瓜 / 篮球 / 小丑爆炸。
        """
        if dmg <= 0:
            return
        # 矿工在地下：**只有灰烬打得进去**（图鉴 "Vulnerable to ... " 的简化口径）
        if (z.kind == '矿工' and getattr(z, 'phase', '') == 'dig'
                and src != 'ash'):
            return
        if z.shield > 0 and not pierce:
            absorb = min(z.shield, dmg)
            z.shield -= absorb
            if z.shield <= 0 and z.kind == '读报':
                # 报纸被打破 → 发愣 1~2s，然后按 1.8s/格 暴走（图鉴）
                z.daze_until = self.t + self.rng.randint(*D.NEWS_DAZE)
                z.spd_alt = D.CELL_W / float(D.NEWS_RUSH_CS)
                z.phase = 'walk'
                self._log('INFO', '读报 %d 路的报纸被打掉 → 发愣 %dcs 后暴走（1.8s/格）'
                          % (z.row, int(z.daze_until - self.t)), row=z.row)
            dmg -= absorb
            if dmg <= 0:
                return
        z.hp -= dmg

    def _torch_ahead(self, c):
        """同一行里 c 右侧最近的活着的火炬树桩（豌豆会穿过它）"""
        for col in range(c.col + 1, 10):
            cc = self.cells.get((c.row, col))
            if cc is not None and cc.plant == '火炬树桩' and cc.awake:
                return D.PLANTS['火炬树桩']['torch']
        return None

    def _attack(self, c, spec):
        # [维 05] 可伤条件：防御域左端 ≤ 800
        # [精] "僵尸可伤条件：防御域左端 ≤ 800"
        #   x 取僵尸中心、防御域宽 72 → 左端 = x - 36。
        #   原来写成 x + 36 ≤ 800（把右端当左端），等于凭空砍掉 36px≈250cs 的可伤时间。
        def ok(z):
            # [精] "防御域左端 ≤ 800"。左界 = x + 横偏（普僵 +36，巨人 +0）
            # ★ 2026-10-24：矿工在地下时不可选（见 `_targetable`）
            return (z.alive and self._targetable(z)
                    and self._dbox(z)[0] <= D.DMG_LINE)

        if spec['rng'] is None:
            if spec['rows'] >= self.rows:
                cand = [z for r in range(1, self.rows + 1) for z in self.by_row[r] if ok(z)]
            else:
                cand = [z for z in self.by_row[c.row] if ok(z)]
            if not cand:
                return
            t = min(cand, key=lambda z: z.x)
            self._hurt(t, spec['dmg'], spec.get('pierce'))
            self.dmg_dealt += spec['dmg']
            if spec.get('splash'):
                # ★ 溅射：与僵尸**受击框**相交即算（不是比中心点）——
                #   用户指出的原理：受击框沾边就吃溅射，所以"看起来 61 像素，
                #   实际要广一些"。
                s_lo = t.x + D.SPLASH_LO
                s_hi = t.x + D.SPLASH_HI
                near = []
                for rr in range(c.row - 1, c.row + 2):
                    for z in self.by_row.get(rr, ()):
                        if z is t or not z.alive:
                            continue
                        zl, zr = self._dbox(z)
                        if zr >= s_lo and zl <= s_hi:
                            near.append(z)
                # [精 七] 伤害 = 574 / n，上限 26
                # [精 七] 伤害 = 574 / n（n = 溅射僵尸数，**不含被直击那只**），
                #   取整，上限 26，**下限 1**
                deal = spec['splash']
                if near and spec.get('splash_div'):
                    deal = max(1, min(spec['splash'],
                                      int(spec['splash_div'] / len(near))))
                for z in near:
                    self._hurt(z, deal, True)
                    self.dmg_dealt += deal
                    if spec.get('slow'):
                        z.slowed_until = max(z.slowed_until, self.t + D.CHILL_CS)
                if spec.get('slow'):
                    t.slowed_until = max(t.slowed_until, self.t + D.CHILL_CS)
            return

        lo, hi = spec['rng']
        lo_x, hi_x = c.x + lo, c.x + hi
        delays = spec.get('hit_delays')
        if delays:
            # ★ 忧郁菇的一轮是**4 次命中**（74/102/130/158cs 各 20 伤害）。
            #   以前合并成"一次 80"，会让"僵尸在 4 次命中之间死亡"这件事
            #   完全体现不出来 —— 死亡时刻、溢出、后续僵尸进射程全都不准。
            for d in delays:
                self.pending.append((self.t + d, c.row, spec['rows'], lo_x, hi_x,
                                     spec['dmg'], spec.get('pierce')))
            return
        # 大喷菇：一轮 1 次 20，立刻结算
        half = spec['rows'] // 2
        for rr in range(c.row - half, c.row + half + 1):
            lst = self.by_row.get(rr)
            if not lst:
                continue
            deal = spec['dmg']
            for z in lst:
                # ★ 用各自的防御框求相交（巨人的框宽得多，能多吃到左边一格）
                zl, zr = self._dbox(z)
                if ok(z) and zr >= lo_x and zl <= hi_x:
                    self._hurt(z, deal, spec.get('pierce'))
                    self.dmg_dealt += deal

    def _tick_events(self):
        """
        到点的事件 → 执行；带 `trig` 的先求值（fire/wait/expire）。

        ★ v0.2：阵解栏里的积木可以挂"卡片 CD / 距离 / 状态"触发器 ——
          这类条件不是编译期能算出来的，只能每 tick 看一眼。
        """
        if not self.events:
            return
        due, keep = [], []
        for e in self.events:
            if e['t'] > self.t:
                keep.append(e)
                continue
            trig = e.get('trig')
            if not trig:
                due.append(e)
                continue
            if 'born' not in e:
                e['born'] = self.t          # 从"够早"这一刻开始计时
            st = self._eval_trig(trig)
            if st == 'fire':
                due.append(e)
            elif st == 'wait':
                if self.t - e['born'] > e.get('ttl', _TRIG_TTL):
                    self.broken.append(dict(t=self.t, wave=e['wave'], what=e['name'],
                                            why='触发器超时（%s）'
                                                % (trig.get('kind') or '?')))
                else:
                    keep.append(e)
            # expire → 直接丢弃（条件是"再也不可能满足"）
        self.events = keep
        for e in due:
            n0 = len(self.actions)
            if e['kind'] == 'ice':
                self._freeze()
            else:
                self.do_action(e)
            # ★ 2026-10-23：把"落点"带进动作记录 —— 时间轴每个色块要标生效坐标，
            #   崩阵场地图也要知道本波每次操作打在哪。
            aim = e.get('aim')
            rc = None
            if (isinstance(aim, (list, tuple)) and len(aim) == 2
                    and not isinstance(aim[1], str)):
                rc = (aim[0], aim[1])
            for a in self.actions[n0:]:
                a.setdefault('aim', aim)
                if rc is not None and 'rc' not in a:
                    a['rc'] = rc
                a.setdefault('aid', (e.get('trig') or {}).get('anchor'))
            # ★ 2026-10-23：记下"这一块积木生效的时刻"，供 `after_block` 触发
            # ★★ 2026-10-24：**用实际生效时刻**（不是名义 `due`）。
            #   曾试过按名义时刻串链，结果变差 —— 原因是**刷波不是定时的**
            #   （波在"本波剩余血量跌破阈值"时才刷），所以"波号=拍号"这个前提不成立。
            #   定时的含义应该是"**操作之间的间隔恒定**"，也就是按实际生效时刻串。
            #   真正的定时杀手是"等"（等炮装填 / 等可伤僵尸），在下面 `_fire_cob`
            #   里把等待窗口压到 0.6s 以内。
            bid = e.get('bid') or (e.get('trig') or {}).get('anchor')
            if bid:
                self.__dict__.setdefault('_block_fired', {})[bid] = self.t
            self._repeat(e)

    def _repeat(self, e):
        """积木的"循环"：执行完再排下一次，直到次数用完或 while 不成立。

        ★ 2026-10-23 用户：「循环事件设定了次数，但是一旦下一波开始，
          没有执行的循环应当放弃。」→ 循环只在本波内有效。
        """
        rp = e.get('repeat')
        if not rp:
            return
        if self.cur_wave != e.get('wave'):
            return
        n = e.get('rep_n', 0) + 1
        times = rp.get('times')
        if times is not None and n >= int(times):
            return
        nxt = dict(e)
        nxt['t'] = self.t + int(rp.get('every') or 100)
        nxt['rep_n'] = n
        nxt['trig'] = rp.get('while') or {'kind': 'spawn'}
        nxt.pop('born', None)
        self.events.append(nxt)

    def _tick_pending(self):
        """结算到点的 AoE 命中（忧郁菇的 4 次命中分别落）"""
        if not self.pending:
            return
        due = [p for p in self.pending if p[0] <= self.t]
        if not due:
            return
        self.pending = [p for p in self.pending if p[0] > self.t]
        for _t, row, rows, lo_x, hi_x, dmg, _pie in due:
            half = rows // 2
            for rr in range(row - half, row + half + 1):
                for z in self.by_row.get(rr, ()):
                    if not z.alive:
                        continue
                    zl, zr = self._dbox(z)
                    if zl > D.DMG_LINE:
                        continue
                    if zr >= lo_x and zl <= hi_x:
                        self._hurt(z, dmg, _pie)
                        self.dmg_dealt += dmg

    def _tick_slow_stat(self):
        """统计前场僵尸处于减速状态的比例。

        这是用户给的校验指标：
        「实战中在轨道的 I 和冰瓜群体减速下，绝大多数时间几乎所有怪
          （免控的冰车除外）都处于减速状态」
        → 若模型算出来远低于此，说明减速模型（冰瓜索敌/溅射/持续）不对。
        """
        for z in self.zombies:
            if not z.alive or z.kind == '冰车' or z.x > 700:
                continue                  # 冰车免控；场外的不计
            self.slow_samples += 1
            if z.slowed_until > self.t:
                self.slow_hits += 1

    def _tick_skip(self):
        """非模拟僵尸按"所在路的实际 dps"被清掉（不是固定寿命）"""
        for m in self.waves:
            if m['skip_hp'] <= 0:
                continue
            loss = 0.0
            for e in m['skips']:
                if e[0] <= 0:
                    continue
                d = min(e[0], e[1] * D.TICK / 100.0)
                e[0] -= d
                loss += d
            m['skip_hp'] = max(0.0, m['skip_hp'] - loss)

    # ------------------------------------------------ 刷新
    def _avg_gap(self):
        """
        平均波长只统计**常规波**。

        ★ 2026-10-20：w9 / w19 是"拖满 45s + 红字 7.2s"的收尾波，
          w20 是清账波，它们的间隔不是"节奏"，混进去会把平均波长抬高。
          用户看报告时要能分清"常规波长"和"收尾波确实更长"。
        """
        # 只取"常规 → 常规"的相邻对
        bad = (9, 10, 19, 20)
        gaps = []
        for a, b in zip(self.waves, self.waves[1:]):
            if a['wave'] in bad or b['wave'] in bad:
                continue
            gaps.append(b['t'] - a['t'])
        if not gaps:
            ts = [m['t'] for m in self.waves[-4:]]
            if len(ts) < 2:
                return 1500
            return int((ts[-1] - ts[0]) / (len(ts) - 1))
        return int(sum(gaps[-6:]) / len(gaps[-6:]))

    def _k9_clear(self):
        """5-9 是否没有冰道：这是 w11 点 5-9 核的前提"""
        c = self.cells.get((5, 9))
        return not (c is not None and c.iced)

    def _snap_tick(self, alive):
        """
        每 1s 更新"当前波"的快照（HTML 报告 hover 用）。

        记的是**这一刻的现场**：阳光、存冰、各卡剩余 CD、场上植物、
        以及每路僵尸推到第几列。波结束时保留最后一帧，就是"本波打到哪了"。
        """
        w = self.cur_wave
        sn = self.wave_snap.get(w)
        if sn is None:
            return
        # ★★ 2026-10-20 用户："阵线栏应该写每一行僵尸所推进到的最深处，而不是本波结束的结果"。
        #   所以这里是**累积最小值**，不是快照（波末往往僵尸已死光，快照看不出危险）。
        #
        # ★ 同事要求："阵线显示参差不齐，有的显示了水路有的没有，统一都显示" ——
        #   所以固定输出 1~6 路，这一波没僵尸的填 None（报告里显示"无"）。
        #
        # ★ 用户认可的口径：海豚 / 矿工 / 小鬼 这一类"已脱离僵尸阵线"的僵尸**不进阵线**
        #   （它们会造成磨损，但不沿 1~6 路推进）。这类僵尸本来就在 SKIP_KINDS 里、
        #   不进 self.zombies，所以这里天然看不到 —— 用 FRONT_EXCLUDE 显式挡一道，
        #   防止以后有人把某种僵尸从 SKIP 里挪出来时又混进阵线。
        deep = sn.setdefault('front_raw', {})
        for z in alive:
            if z.kind in D.FRONT_EXCLUDE:
                continue
            col = (z.x - 40) / 80.0 + 1
            k = str(z.row)
            if deep.get(k) is None or col < deep[k]:
                deep[k] = col
        sn['front'] = {str(r): (round(deep[str(r)], 2)
                                if deep.get(str(r)) is not None else None)
                       for r in range(1, self.rows + 1)}
        sn['sun_end'] = round(self.sun)
        sn['ice_end'] = self.ice_stock     # ★ 波首的 sun / ice 保留在 spawn_wave 里，别覆盖
        sn['alive'] = len(alive)
        sn['cards_end'] = {k: max(0, v - self.t) for k, v in self.card_ready.items()}
        pc = {}
        for (rr, cc), cell in self.cells.items():
            if cell.plant:
                pc[cell.plant] = pc.get(cell.plant, 0) + 1
        sn['plants'] = pc
        sn['pumpkin'] = sum(1 for (rr, cc), cell in self.cells.items()
                            if self.array.get((rr, cc), {}).get('pumpkin') and cell.pumpkin)
        sn['t_last'] = self.t

    def _tick_refresh(self):
        m = self.wave_meta
        if m is None:
            if self.t >= D.R0_FIRST:
                self.spawn_wave(1)
            return
        if self.done:
            return
        m['age'] = self.t - m['t']
        remain = m['skip_hp']
        for z in m['zs']:
            if z.alive:
                remain += z.total_hp
        m['remain'] = remain

        w = m['wave']
        nxt = None
        # ★ w9/w19 的"拖时间"是**玩家策略**，不是机制。
        #   有巨人的档才需要拖（等炮装填 / 等巨人走到落点）；
        #   快速/极速档全是脆皮，玩家根本不会停 —— 硬编码成机制会让波长虚高 50%。
        if w in (9, 19) and self.stall_waves:
            if remain <= 0 or m['age'] >= D.FLAG_STALL:
                if m.get('stall') is None:
                    m['stall'] = self.t
                    m['reason'] = '清完' if remain <= 0 else '拖满 45s'
                    # ★ 2026-10-20：w9/w19 一进入"等红字"阶段就**锁住窝瓜**，
                    #   因为它必须留给下一波（w10 压冰车 / w20 清账）。
                    #   原来红字这 7.2s 里救场还能把窝瓜抢去砸红眼，
                    #   结果 w10 开局窝瓜在 CD，5-9 就被冰车铺了。
                    if w == 9:
                        self.tomato_busy_until = self.t + D.FLAG_DELAY + 8000
                if self.t - m['stall'] >= D.FLAG_DELAY:
                    nxt = self.t
        elif w == 20:
            if remain <= 0 or m['age'] >= D.FINAL_STALL:
                if m.get('stall') is None:
                    m['stall'] = self.t
                    m['reason'] = '清完' if remain <= 0 else '拖满 49s'
                if self.t - m['stall'] >= D.FINAL_DELAY:
                    self.done = True
                    return
        else:
            # ★★ 2026-10-25 用户：「**无论如何，最短波长为 6s**。本波刷新后最极限的
            #   情况下也必须 6s 才可以刷新下一波。」
            #   → 修正：以前把 R1 挂在"**设 trig 之前**"，于是最坏情况变成
            #     max(6s, T) + 2s真空 = 最少 8s。正确口径是
            #     `波长 = max(R1 6s, 血量跌破阈值 + 2s)`（R3 硬顶直接刷）。
            if m.get('trig') is None:
                if m['total_hp'] > 0 and remain / m['total_hp'] < m['thr']:
                    m['trig'] = self.t
                    m['reason'] = 'R2 血线 %.2f' % m['thr']
                elif m['age'] >= m['hard']:
                    m['trig'] = self.t
                    m['reason'] = 'R3 硬顶 %d' % m['hard']
            if m.get('trig') is not None:
                if m['age'] >= m['hard']:
                    nxt = self.t            # R3 到点必刷
                elif (self.t - m['trig'] >= D.R2_VACUUM
                      and m['age'] >= D.R1_MIN_GAP):
                    nxt = self.t

        if nxt is not None:
            self._bungee_resolve()      # ★ 2026-10-22：这一波的蹦极到点结算
            if w >= self.total_waves:
                self.done = True
                return
            self.spawn_wave(w + 1)

    def _check_fail(self):
        if self.fail:
            return
        for z in self.zombies:
            if z.alive and z.x <= -20:
                self._fatal('进家：%s / 第 %d 路' % (z.kind, z.row),
                            '走到 x=%d' % z.x, row=z.row)

    def _cleanup(self):
        for z in self.zombies:
            if z.alive and z.hp <= 0:
                z.alive = False
                self.n_kill += 1
                if z.kind == '小丑':
                    # ★ 2026-10-23：炸**之前**就死了 = 控丑成功（没炸）
                    z.joker_res = 'died'
                    self.joker_units.append(dict(
                        wave=z.wave, row=z.row, early=bool(z.joker_early),
                        res='died', killed=[], pads=[],
                        defused=bool(z.defused),
                        frozen=(z.frozen_until > self.t)))
                if z.kind == '冰车':
                    self.car_audit.append(dict(wave=z.wave, row=z.row,
                                               min_x=round(z.min_x),
                                               verdict='死在 x=%d（没摸到植物）' % round(z.min_x),
                                               crush=False))
                if z.kind == '白眼':
                    # 巨人丢小鬼：期望型（后场曾负责），按其所在路的 dps 清掉
                    if self.wave_meta:
                        m = self.wave_meta
                        m['skip_hp'] += D.ZOMB['小鬼'][0]
                        m['skips'].append([float(D.ZOMB['小鬼'][0]),
                                           D.SKIP_DPS.get(z.row, 150.0)])
        if self.t % 500 == 0:
            self.zombies = [z for z in self.zombies if z.alive]

    # ------------------------------------------------ 维护层（补南瓜）
    def _tick_repair(self):
        """
        南瓜是耗材，实战里是"边打边补"的。不补 → 任何阵都会被磨死，
        这不是轨道的问题，是没模拟玩家最基本的维护动作。
        双南瓜配置下两张卡共用同一条 CD（保守做法：只当一张用，需要时可改）。
        """
        if not self.repair:
            return
        need = []
        for (r, c), spec in self.array.items():
            if not spec.get('pumpkin'):
                continue
            cell = self.cells.get((r, c))
            if cell is None or cell.pumpkin:
                continue
            if cell.plant is None and not spec.get('plant'):
                continue                       # 已经彻底空的格子不用补
            need.append((r, c))
        # ★★ 2026-10-23 运阵模型：选卡带了的阵型成分 → 死了就持续判定补种。
        #   注意必须放在"没有南瓜要补就 return"之前，否则南瓜都完好时永远不补。
        for q in list(self.replant_q):
            rc = (q['row'], q['col'])
            cell = self.cells.get(rc)
            if cell is None or cell.plant is not None:
                self.replant_q.remove(q)
                continue
            if cell.iced or cell.crater_until > self.t or cell.grave or cell.tail:
                continue
            name = q['plant']
            if not self._base_ok(rc, name):
                continue
            if not self._try_card(name):
                continue
            self._plant_into(cell, name)
            self.replant_q.remove(q)
            self.replant_n = getattr(self, 'replant_n', 0) + 1
            self._log('REPAIR', '补种 %d-%d 的%s' % (rc[0], rc[1], name),
                      row=rc[0], col=rc[1],
                      detail='选卡带了这个阵型成分 → 死后持续判定补种')
        if not need:
            return
        need.sort(key=lambda rc: -rc[1])       # 前场优先
        for (r, c) in need:
            if not self._try_card('南瓜'):
                break
            cell = self.cells[(r, c)]
            cell.pumpkin = True
            cell.pumpkin_hp = D.PUMPKIN_HP
            cell.ladder = False                # 补南瓜 = 梯子没了
            self._log('REPAIR', '补南瓜 %d-%d' % (r, c), row=r, col=c,
                      detail='125 阳光 · 该格梯子已失效')

        # ★ 快速/极速关：CORE 植物毁掉后重建（"死了就补"）
        for rec in self.rebuilds:
            if rec['done']:
                continue
            rc = (rec['row'], rec['col'])
            spec = self.array.get(rc) or {}
            cell = self.cells.get(rc)
            if cell is None:
                rec['done'] = True
                continue
            if cell.plant is not None:
                rec['done'] = True
                continue
            pname = rec.get('plant') or spec.get('plant')
            if not pname:
                rec['done'] = True
                continue
            cost = D.PLANT_COST.get(pname, 200)
            if self.sun < cost:
                continue
            self.sun -= cost
            cell.plant = pname
            cell.plant_hp = D.PLANTS.get(pname, {}).get('hp', 300)
            rec['done'] = True
            self._log('REBUILD', '重建 %d-%d 的%s（%d 阳光）'
                      % (rc[0], rc[1], cell.plant, cost), row=rc[0], col=rc[1],
                      detail='w%d 被毁 → 补回' % rec['wave'])

    # ------------------------------------------------ 报告
    def report(self):
        pump = {}
        init = sum(D.PUMPKIN_HP for sp in self.array.values() if sp.get('pumpkin'))
        now = 0.0
        for (r, c), cell in self.cells.items():
            if self.array.get((r, c), {}).get('pumpkin'):
                pump['%d-%d' % (r, c)] = round(cell.pumpkin_hp)
                now += cell.pumpkin_hp
        lost_pump = sum(1 for (r, c), cell in self.cells.items()
                        if self.array.get((r, c), {}).get('pumpkin') and not cell.pumpkin)
        waves, prev = [], 0
        for m in self.waves:
            waves.append(dict(w=m['wave'], t=m['t'], gap=m['t'] - prev,
                              total_hp=m['total_hp'], remain=round(m.get('remain', 0)),
                              thr=round(m['thr'], 3), reason=m.get('reason')))
            prev = m['t']
        # ★★ 2026-10-20：wave_ctrl 里记的是 **track 排的计划**，
        #   但救急层 / 维护层还会补发动作（极速关的存冰就是救急点的）。
        #   表格要与时间轴一致，所以这里按**实际发生的 actions** 再聚合一遍：
        #     ice_act / ash_act = 相对波首的偏移（cs），garlic = 本波补了几次蒜
        t0_of = {w: (self.wave_snap.get(w) or {}).get('t0') for w in self.wave_ctrl}
        for a in self.actions:
            if not a.get('ok'):
                continue
            w = a.get('wave')
            if w not in self.wave_ctrl:
                continue
            t0 = t0_of.get(w)
            if t0 is None:
                continue
            off = a['t'] - t0
            wc = self.wave_ctrl[w]
            nm = a['name']
            if nm in ('冰', '模仿冰', '存冰'):
                if wc.get('ice_act') is None or off < wc['ice_act']:
                    wc['ice_act'] = off
            elif nm in ('核', '模仿核', '樱桃', '辣椒'):
                if wc.get('ash_act') is None or off < wc['ash_act']:
                    wc['ash_act'] = off
            elif nm == '大蒜':
                wc['garlic'] = wc.get('garlic', 0) + 1

        return dict(
            t_end=self.t,
            waves=waves,
            actions=self.actions,
            broken=self.broken,
            log=self.log,
            # ★ 2026-10-22：P（玉米炮）开炮记录 —— 时间 / 落点（可带小数）/ 用的哪门炮
            cob_shot=self.cob_shot,
            sun_end=round(self.sun),
            sun_peak=round(self.sun_peak),
            sun_capped=self.sun_capped,
            pumpkins=pump,
            pumpkin_lost=lost_pump,
            pump_dmg=round(init - now),
            crush=self.crush,
            deaths=self.deaths,
            field_snap=(self.collapse_snap or self._field_snapshot()),
            replant_n=getattr(self, 'replant_n', 0),
            # ★ 2026-10-23：预演-回溯的"省下的救场次数"（推演说会被 IO 收掉 → 不出手）
            la_skip_n=getattr(self, 'la_skip_n', 0),
            replant=list(sorted(self.replant)),
            ice_cells=sum(1 for c in self.cells.values() if c.iced),
            ice_touched=len(self.ice_touched),
            ice_blocks=sum(1 for b in self.broken if '冰道' in (b.get('why') or '')),
            fail=self.fail,
            done=self.done,
            n_kill=self.n_kill,
            dmg_dealt=round(self.dmg_dealt),
            dps=round(self.dmg_dealt / max(1.0, self.t / 100.0)),
            slow_cov=round(100.0 * self.slow_hits / self.slow_samples, 1) if self.slow_samples else 0.0,
            n_rescue=sum(1 for x in self.log if x['sev'] == 'RESCUE'),
            n_norescue=sum(1 for x in self.log if x['sev'] == 'NORESCUE'),
            n_warn=sum(1 for x in self.log if x['sev'] == 'WARN'),
            series=self.series,
            wave_snap={str(k): v for k, v in self.wave_snap.items()},
            # ★ 2026-10-20：来源/去向要**全量聚合**，不能只给前 40 条明细
            #   （上一版 detail[:40] 截断，导致 table 里 20+20=40 与总数 93 对不上）
            garlic=dict(n=len(self.garlic_swaps),
                        broke=sum(1 for g in self.garlic_swaps if g['broke']),
                        by_frm={str(r): sum(1 for g in self.garlic_swaps
                                            if g['frm'] == r) for r in range(1, self.rows + 1)},
                        by_to={str(r): sum(1 for g in self.garlic_swaps
                                           if g['to'] == r) for r in range(1, self.rows + 1)},
                        detail=self.garlic_swaps[:40]),
            # ★ 极速关有车时的替代方案：2-7 / 5-7 结构位大喷（补了几次、被碾几次）
            fog=dict(n=len(self.fog_fix),
                     crushed=sum(1 for c in self.crush
                                 if c.get('plant') == '大喷菇'
                                 and (c.get('row'), c.get('col'))
                                 in set(self.struct_fog_slots)),
                     detail=self.fog_fix[:40]),
            end_state=dict(
                ice_stock=self.ice_stock,
                ice_stock_perm=sum(1 for v in self.ice_slots.values() if v),
                # ★ 2026-10-22：阵上到底有几个存冰位（0 = 这个阵根本不带冰）
                #   —— 报告里的"存冰 0"警告只在 >0 时才发。
                ice_cap=len(self.ice_slots),
                ice_stock_temp=sum(1 for v in self.temp_ice.values() if v),
                ice_slots={'%d-%d' % rc: ('满' if v else '空')
                           for rc, v in self.ice_slots.items()},
                temp_ice={'%d-%d' % rc: ('满' if v else '空')
                          for rc, v in self.temp_ice.items()},
                ice_refill=self.ice_refill_n,
                ice_temp_planted=self.ice_temp_n,
                ice_refill_skip=self.ice_refill_skip,
                ice_emerg=self.ice_emerg_n,
                ice_used=sum(1 for x in self.log if x['sev'] == 'ICE'),
                ice_chili_reuse=self.ice_chili_reuse,
                row_min={r: (None if v > 9000 else round(v)) for r, v in self.row_min.items()},
                core_x=dict(D.CORE_X),
                cards={k: (0 if v <= self.t else round(v - self.t)) for k, v in self.card_ready.items()},
                cards_ready=sum(1 for v in self.card_ready.values() if v <= self.t),
                cars_spawned=len(self.car_audit),
                cars_crushed=sum(1 for c in self.car_audit if c.get('crush')),
                cars_min_x=(min((c['min_x'] for c in self.car_audit), default=None)),
                cars_min_margin=(min((c['min_x'] - D.CORE_X.get(c['row'], 200)
                                      for c in self.car_audit), default=None)),
                pumpkins_alive=sum(1 for (r, c), cell in self.cells.items()
                                   if self.array.get((r, c), {}).get('pumpkin') and cell.pumpkin),
                # ★ 2026-10-22：南瓜存活数的**分母**用"实际识别阵型"的结果，
                #   不再硬编码 24。
                pumpkins_init=sum(1 for sp in self.array.values() if sp.get('pumpkin')),
                plants_lost=[x['what'] for x in self.log if x['sev'] == 'WARN'],
                repairs=sum(1 for x in self.log if x['sev'] == 'REPAIR'),
                replant=getattr(self, 'replant_n', 0),
                kernel_log=self.kernel_log,
                joker=dict(
                    spawned=getattr(self, '_joker_n', 0),
                    spawned_rows={str(r): v for r, v in self.joker_row_n.items()},
                    booms=len(self.joker_boom),
                    boom_rows={str(r): sum(1 for b in self.joker_boom if b['row'] == r)
                               for r in range(1, self.rows + 1)},
                    # ★ 2026-10-22：控丑判定改成**按实际结果**分类，不再假设"只有 2/5 路会死"
                    boom_empty=sum(1 for b in self.joker_boom if not b['killed']),
                    boom_hit=sum(1 for b in self.joker_boom if b['killed']),
                    core_kill=sum(1 for b in self.joker_boom
                                  if any(k in ('忧郁菇', '冰瓜')
                                         for k in b['killed'])),
                    kill=[b for b in self.joker_boom if b['killed']],
                    detail=self.joker_boom[:60],
                    # ★ 2026-10-23：每只小丑的结局（早/晚 × 炸前死/炸空/炸掉什么）
                    units=self.joker_units,
                ),
                # ★ 2026-10-22：蹦极逐波明细（谁被偷 / 谁被伞·炮·冰救下）
                bungee=self.bungee_risk,
                bungee_detail=self.bungee_log,
                # ★ 2026-10-22：全场植物状态（报告总概述的表格用它，不写死任何文本）
                plants_end=self._plant_status(),
                wave_ctrl={str(k): v for k, v in self.wave_ctrl.items()},
                rebuilds=self.rebuilds,
                la_skip_n=getattr(self, 'la_skip_n', 0),
            ),
            car_audit=self.car_audit,
            catapult=self.catapult,
            kernel_log=self.kernel_log,
            joker=dict(
                spawned=getattr(self, '_joker_n', 0),
                booms=len(self.joker_boom),
                boom_rows={r: sum(1 for b in self.joker_boom if b['row'] == r)
                           for r in range(1, self.rows + 1)},
                boom_empty=sum(1 for b in self.joker_boom if not b['killed']),
                boom_hit=sum(1 for b in self.joker_boom if b['killed']),
                kill=[b for b in self.joker_boom if b['killed']],
                detail=self.joker_boom[:60],
                units=self.joker_units,
            ),
            bungee=self.bungee_risk,
            bungee_detail=self.bungee_log,
            # ★ 2026-10-24：拦截炮的小鬼明细（投出 / 拦截成功 / 落地）
            imp_log=self.imp_log,
            wave_ctrl={str(k): v for k, v in self.wave_ctrl.items()},
            rebuilds=self.rebuilds,
            avg_gap=round((self.waves[-1]['t'] - self.waves[0]['t']) /
                          max(1, len(self.waves) - 1)) if len(self.waves) > 1 else 0,
        )
