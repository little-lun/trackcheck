# -*- coding: utf-8 -*-
"""
fields.py —— 场地模型（v0.2.1 新增）

在此之前引擎只认「泳池形状」：写死 6 行、3/4 路是水、一格 80×85。
这一版把场地抽成对象，FE / DE / NE / RE 各有自己的：

    行数 · 格高 · y 坐标 · 水路 · 昼夜（蘑菇睡不睡）· 浓雾 · 墓碑 ·
    斜坡（屋顶）· 种植基座（荷叶 / 花盆）· 禁出僵尸 · 关末机制

★ 来源
    [01] docs/知识库/01-基础-场地坐标与术语.md     （九场地表、行/列/半场、关末机制）
    [05] docs/知识库/05-数据-精确数值手册.md §二     （僵尸 y / 植物 y / 出生点）
    [维] https://plantsvszombies.wiki.gg/wiki/Plants_vs._Zombies

★ 关键口径
    ① **列宽恒为 80px**，只有格高与 y 原点随场地变（后院 85、前院 100、屋顶 85）。
    ② 屋顶植物 y 是**逐格**给的（前 5 列在斜坡上，每列 −20px），不是线性公式。
    ③ 「必须种荷花 / 花盆」是**基座**规则，不是"能不能种"：
       水上先种荷叶，屋顶先种花盆，然后才能在它上面种别的。
    ④ NE 的墓碑、FE 的浓雾、RE 的空降三人组都是**关末 / 持续机制**，
       这里只声明标志，具体结算在 engine 里。
"""

CELL_W = 80                 # 列宽，所有场地一致 [05 §二]

# ── 屋顶植物 y（[05 §二] 逐格表）：前 5 列在斜坡上，每列 −20；后 4 列平地
ROOF_PLANT_Y = {
    1: (170, 150, 130, 110, 90, 70, 70, 70, 70),
    2: (255, 235, 215, 195, 175, 155, 155, 155, 155),
    3: (340, 320, 300, 280, 260, 240, 240, 240, 240),
    4: (425, 405, 385, 365, 345, 325, 325, 325, 325),
    5: (510, 490, 470, 450, 430, 410, 410, 410, 410),
}

# ── 场地家族（决定 y 公式）：
#     backyard 后院 6 行 85：僵尸 y=50+85(r−1)、植物 y=80+85(r−1)
#     front    前院 5 行 100：僵尸 y=50+100(r−1)、植物 y=80+100(r−1)
#     roof     屋顶 5 行 85：僵尸 y=40+85(r−1)、植物 y 查表
FAMILY = {
    'backyard': dict(zombie_y0=50, plant_y0=80, gap=85),
    'front': dict(zombie_y0=50, plant_y0=80, gap=100),
    'roof': dict(zombie_y0=40, plant_y0=None, gap=85),
}


class Field:
    """一个场地。除了坐标与形状，还带"这个场地允许 / 禁止什么"的规则。"""

    __slots__ = ('code', 'name', 'family', 'rows', 'gap',
                 'water', 'land', 'night', 'fog', 'sky_sun', 'graves',
                 'slope', 'base_plant', 'endgame', 'ban', 'dancer_rows',
                 'note', 'level')

    def __init__(self, code, name, family, rows, *, water=(), night=False,
                 fog=False, sky_sun=True, graves=False, slope=False,
                 base_plant=None, endgame=None, ban=(), dancer_rows=None,
                 note='', level='full'):
        self.code = code
        self.name = name
        self.family = family
        self.rows = rows
        self.gap = FAMILY[family]['gap']
        self.water = tuple(water)
        self.land = tuple(r for r in range(1, rows + 1) if r not in self.water)
        self.night = night
        self.fog = fog
        self.sky_sun = sky_sun
        self.graves = graves
        self.slope = slope
        # 基座规则：水上 → 荷叶；全场地 → 花盆（屋顶）
        self.base_plant = base_plant
        self.endgame = endgame          # 'coral' / 'airdrop' / None
        self.ban = frozenset(ban)
        self.dancer_rows = tuple(dancer_rows) if dancer_rows else tuple(
            range(1, rows + 1))
        self.note = note
        self.level = level

    # ---------------------------------------------------------- 坐标
    def zombie_y(self, row):
        return FAMILY[self.family]['zombie_y0'] + self.gap * (row - 1)

    def plant_y(self, row, col=1):
        if self.family == 'roof':
            tbl = ROOF_PLANT_Y.get(row)
            if tbl:
                return tbl[max(0, min(8, col - 1))]
            return 170 + self.gap * (row - 1)
        return FAMILY[self.family]['plant_y0'] + self.gap * (row - 1)

    def plant_x(self, col):
        return 40 + CELL_W * (col - 1)

    def all_rows(self):
        return tuple(range(1, self.rows + 1))

    # ---------------------------------------------------------- 规则
    def is_water(self, row):
        return row in self.water

    def base_for(self, row):
        """这一格要先种什么才能种别的（None = 直接种）。

        ★ 用户 2026-10-22：「PE、FE 在水路空地上面种植物必须先进行种荷叶；
          对于 RE，空地上面种植物必须先进行种花盆」
          （第一次说的 NE 已确认为口误 → 就是 PE 和 FE，也就是有 3/4 路水的两个后院场地。）
        """
        if row in self.water:
            return '荷叶'
        if self.base_plant:
            return self.base_plant
        return None

    def allows(self, kind, row=None):
        """这种僵尸在这个场地 / 这一路能不能出"""
        if kind in self.ban:
            return False
        if row is not None and kind == '舞王' and row not in self.dancer_rows:
            return False
        return True

    def spawn_rows(self, kind, rng, water_only=(), land_only=()):
        """给一种僵尸挑一路：遵守水路 / 陆路 / 禁出 / 舞王中三路。

        ★ 抽签方式刻意与旧代码逐位对齐（`rng.choice` / `rng.randint` 都只消耗一次
          `_randbelow`），这样 PE 的随机流与之前完全一致 —— 四档回归的种子结果
          才能拿来当"行为没变"的证据。
        """
        if kind in water_only:
            cand = [r for r in self.water if self.allows(kind, r)]
            if cand:
                return cand[rng.randrange(len(cand))]
        elif kind in land_only:
            cand = [r for r in self.land if self.allows(kind, r)]
            if cand:
                return cand[rng.randrange(len(cand))]
        cand = [r for r in self.all_rows() if self.allows(kind, r)]
        if not cand:                     # 兜底：至少给一路，别把这一只吞掉
            cand = list(self.all_rows())
        return cand[rng.randrange(len(cand))]

    def to_dict(self):
        return dict(code=self.code, name=self.name, rows=self.rows,
                    gap=self.gap, water=list(self.water), night=self.night,
                    fog=self.fog, sky_sun=self.sky_sun, graves=self.graves,
                    slope=self.slope, base_plant=self.base_plant,
                    endgame=self.endgame, ban=sorted(self.ban),
                    note=self.note, level=self.level)


# ══════════════════════════════════════════════════════════════════
# 五个无尽场地
# ══════════════════════════════════════════════════════════════════
FIELDS = {
    # ---- 泳池（后院）：本库唯一被完整跑通的场地
    'PE': Field(
        'PE', '泳池无尽（白天）', 'backyard', 6, water=(3, 4),
        night=False, fog=False, sky_sun=True, endgame='coral',
        note='6 行 × 9 列，一格 80×85；3/4 路是水、1/2/5/6 是岸；'
             '开局阳光 8000、封顶 9990；出生点 x≈780~819；w20 珊瑚三人组',
        level='full'),

    # ---- 雾夜（后院）：形状同 PE，但夜间 + 浓雾 + 无天降阳光
    'FE': Field(
        'FE', '雾夜无尽', 'backyard', 6, water=(3, 4),
        night=True, fog=True, sky_sun=False, endgame='coral',
        note='与 PE 同一套坐标；夜间（蘑菇免唤醒、无天降阳光、'
             '前场浓雾：8~9 列在视野外）；**结果导向：冰/核不计 100cs 生效延迟**；'
             'w20 珊瑚三人组',
        level='full'),

    # ---- 白昼（前院）：5 行、格高 100、无水路
    'DE': Field(
        'DE', '白昼无尽（前院）', 'front', 5,
        night=False, sky_sun=True, dancer_rows=(2, 3, 4),
        ban=('潜水', '海豚'),
        note='5 行、Y 间距 100、无水路；有天降阳光；舞王只在中三路；'
             '不能出潜水 / 海豚',
        level='full'),

    # ---- 黑夜（前院）：5 行 + 无水路 + 无天降阳光 + 墓碑 + 无冰车
    'NE': Field(
        'NE', '黑夜无尽（前院）', 'front', 5,
        night=True, sky_sun=False, graves=True, ban=('冰车', '潜水', '海豚'),
        dancer_rows=(2, 3, 4),
        note='5 行 + 无水路 + 无天降阳光 + 有墓碑；**不会出冰车 / 潜水 / 海豚**；'
             '舞王只在中三路；w20 生成 / 摧毁墓碑',
        level='full'),

    # ---- 天台（屋顶）：5 行、后五列斜坡、必须花盆、空降三人组
    'RE': Field(
        'RE', '天台无尽', 'roof', 5,
        night=False, sky_sun=True, slope=True, base_plant='花盆',
        endgame='airdrop', ban=('潜水', '海豚', '舞王', '矿工'),
        note='5 行、后五列斜坡、**必须花盆**；僵尸 y 从 40 起、植物 y 逐格给；'
             '空降三人组（w20 蹦极投下 3 只，冰可冻结天空取消）；'
             '不能出潜水 / 海豚 / 舞王 / 矿工',
        level='full'),
}

FIELD_CODES = ('PE', 'FE', 'DE', 'NE', 'RE')


def get(code=None):
    """按代码取场地；给 None / 未知代码 → PE（保持旧行为）"""
    if not code:
        return FIELDS['PE']
    return FIELDS.get(str(code).upper(), FIELDS['PE'])


def codes():
    return list(FIELD_CODES)


def all_fields():
    return [FIELDS[c] for c in FIELD_CODES]


def models():
    """给界面 / metainfo 用的清单"""
    return dict(
        list=[FIELDS[c].to_dict() for c in FIELD_CODES],
        note='五个场地都已建模：行数 / 格高 / y 坐标 / 水路 / 昼夜 / 浓雾 / '
             '墓碑 / 斜坡 / 基座（荷叶·花盆）/ 禁出僵尸 / 关末机制。'
             'PE 有完整阵型配置与录像标定；其余四个场地的**数值层**与 PE 同一套'
             '（同一份精确数据），差异只在形状与场地规则。',
    )
