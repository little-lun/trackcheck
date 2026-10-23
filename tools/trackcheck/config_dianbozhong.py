# -*- coding: utf-8 -*-
"""
config_dianbozhong.py —— PE.电波钟无炮 的验证配置

阵型数据来自 `练习/PE.电波钟无炮/研讨笔记.md` §一，已与统计数对齐：
曾 15｜冰瓜 7｜大喷 4｜双花 6｜存冰 4｜伞 2｜香蒲 2｜荷叶 16｜南瓜 24

★ 2026-10-18 按四档实战视频 + 用户口述补的三条"阵的知识"：
  ① **5-8 核坑位会被冰道覆盖** → 中概率，被盖就**退到 5-7** 点核
  ② **1 路有樱桃、6 路没有其它灰烬运算量** → 核尽量点 **5 路**
  ③ **5-3 的存冰故意不补** → 那一格要留作**辣椒位**
"""

# ------------------------------------------------------------------ 阵型
from . import data as D      # noqa: E402  （_ice_ops 要用 MAX_ICE_STOCK / CARDS）

ARRAY = {}


def _p(r, c, plant=None, pumpkin=False, ladder=False):
    ARRAY[(r, c)] = dict(plant=plant, pumpkin=pumpkin, ladder=ladder)


# ★ 依据 `练习/PE.电波钟无炮/研讨笔记.md` §一「阵型总表」逐格重建
#   ∩ = 在南瓜内  梯 = 模仿者南瓜（预搭梯，共 4 个）
#   — = 空（前场 7~9 列为核坑 / 樱桃位）

# 1 路（边路）
_p(1, 1, '忧郁菇', True,  False)
_p(1, 2, '忧郁菇', True,  True)     # 梯
_p(1, 3, '冰瓜',   True,  True)     # 梯
_p(1, 4, '大喷菇', True,  False)
_p(1, 5, '大喷菇', False, False)

# 2 路（岸路）
_p(2, 1, '冰瓜',   True,  False)
_p(2, 2, '保护伞', True,  True)     # 梯
_p(2, 3, '冰瓜',   True,  True)     # 梯
_p(2, 4, '冰瓜',   True,  False)
_p(2, 5, '忧郁菇', False, False)
_p(2, 6, '忧郁菇', False, False)

# 3 路（水路）
_p(3, 1, '双子花', False, False)
_p(3, 2, '存冰',   False, False)
_p(3, 3, '存冰',   False, False)
_p(3, 4, '香蒲',   False, False)
_p(3, 5, '双子花', False, False)
_p(3, 6, '忧郁菇', True,  False)
_p(3, 7, '忧郁菇', True,  False)
_p(3, 8, '忧郁菇', True,  False)
_p(3, 9, '忧郁菇', True,  False)

# 4 路（水路）
_p(4, 1, '双子花', False, False)
_p(4, 2, '双子花', False, False)
_p(4, 3, '存冰',   False, False)
_p(4, 4, '双子花', False, False)
_p(4, 5, '双子花', False, False)
_p(4, 6, '香蒲',   True,  False)
_p(4, 7, '忧郁菇', True,  False)
_p(4, 8, '忧郁菇', True,  False)
_p(4, 9, '忧郁菇', True,  False)

# 5 路（岸路）—— 5-3 是存冰位，用掉后留作【辣椒位】
_p(5, 1, '保护伞', True,  False)
_p(5, 2, '忧郁菇', True,  False)
_p(5, 3, '存冰',   True,  False)
_p(5, 4, '冰瓜',   True,  False)
_p(5, 5, '忧郁菇', False, False)
_p(5, 6, '忧郁菇', False, False)

# 6 路（边路）
_p(6, 1, '冰瓜',   True,  False)
_p(6, 2, '忧郁菇', True,  False)
_p(6, 3, '冰瓜',   True,  False)
_p(6, 4, '大喷菇', True,  False)
_p(6, 5, '大喷菇', False, False)


# ------------------------------------------------------------------ 核坑位
# [你] 优先级从高到低。5 路优先（1 路有樱桃、6 路没有其它灰烬运算量）；
#      5-8 有中概率被冰道覆盖 → 被盖就退 5-7
# [你] 核坑位：5-8 优先（被冰道盖就退 5-7），尽量点 5 路
#      （1 路有樱桃、6 路没有别的灰烬，所以核别放 1/6 路）
#      再退才是 2 路前场；最后才是边路 —— 否则冰道一盖就"无处可点"
# [你] 2-7 / 5-7 / 5-8 最优先；**2-8 必须排除** —— 那是下一波 AA' 的樱桃位，
#      核占了它，第二天的 AA' 就执行不了。
# ★ 顺序即优先级：前 7 个是"判定波的插核坑"，**2-9 / 5-9 放最后**，
#   它们永远留给 w1 / w11 两个锚点（用户："否则坑位不够"）。
KERNEL_SLOTS = [(5, 8), (5, 7), (2, 7), (6, 8), (6, 9), (1, 8), (1, 9),
                (5, 9), (2, 9)]

# ★ 用户 2026-10-19："核坑优先级不是死的，而是根据对格子的需求让出来的"。
#   快速关不用 2 路的樱桃位 → 核固定走 2-8，把 5-7/5-8 让给大喷和樱桃。
KERNEL_AIM_BY_MODE = {'快速': (2, 8)}

# ★★ 2026-10-20 用户：极速关的出怪里**没有冰车、没有投篮车**时，
#   核弹没有目标（核本来就是用来炸车/巨人的），把 N 换成**大蒜**，
#   种在 2-9 / 5-9 —— 靠换行把岸路僵尸赶去边路和水路。
#   维护（被啃碎就补）由引擎 `_tick_garlic()` 每 1s 自动做。
GARLIC_SLOTS = {'极速': [(2, 9), (5, 9)]}

# ★★ 2026-10-20 用户（第 14 轮修正）：**带冰车或投篮车时不能带大蒜** ——
#   车会把大蒜连着格子一起碾掉，驱逐根本立不住；也别把核放回来。
#   极速关这时唯一的答案是"改结构"：在 **2-7 / 5-7 种大喷**尽可能抬高丑抗
#   （"极速关这么忙，也来不及做别的操作"）。被车压掉就补，由引擎每 1s 重试。
STRUCT_FOG_SLOTS = {'极速': [(2, 7), (5, 7)]}
CRUSH_KINDS = ('冰车', '投篮')


def active_kinds(tier=None):
    """本档实际允许出现的出怪（app 的勾选覆盖优先于 TIERS）"""
    tier = tier or MODE
    return list(KINDS_OVERRIDE if KINDS_OVERRIDE else TIERS[tier])


def garlic_slots(tier=None, kinds=None):
    """大蒜位 —— 只有极速关且**没有碾压车**时才成立"""
    tier = tier or MODE
    ks = set(active_kinds(tier) if kinds is None else kinds)
    if tier == '极速' and not (ks & set(CRUSH_KINDS)):
        return list(GARLIC_SLOTS.get(tier) or [])
    return []


def struct_fog_slots(tier=None, kinds=None):
    """结构位大喷 —— 极速关**有碾压车**时，大蒜让位给 2-7 / 5-7 的大喷"""
    tier = tier or MODE
    ks = set(active_kinds(tier) if kinds is None else kinds)
    if tier == '极速' and (ks & set(CRUSH_KINDS)):
        return list(STRUCT_FOG_SLOTS.get(tier) or [])
    return []
# 快速关 w9 长间隔补种的大喷位置（先 5-7，其次 2-7）
FAST_LUNGBU_SPOTS = [(5, 7), (2, 7), (5, 8)]

# ★ 用户 SOP（慢速关 w1）："2-7、5-7 两个临时存冰"。
#   这是**前场的临时位**，不是永久位：用得快、也最容易被冰车/核坑占掉，
#   但它给了开局 +2 的冰量。w1 时两张冰卡正好闲着（永久 4 位全满，补不了），
#   拿来种它们**零机会成本** —— 这也是"存冰收尾不够"的最后一块拼图。
TEMP_ICE_SLOTS = [(2, 7), (5, 7)]
CHILI_SLOT = (5, 3)
CHERRY_ROW = 2          # [你] w2/w7 的樱桃在 **2-8**（不是 1 路）
CHERRY_COLS = [8, 9, 7, 6]   # 2-8 有冰道就顺延，玩家不会硬种

N_CANNON = 0
N_CAT = 2
HAS_BLOVER = True
KILL_BEFORE_THROW = False
PUMPKIN_CARDS = 2       # 电波钟实战带双南瓜（一个复制）
MINE_HIT_BY_ASH = True  # 前场灰烬能覆盖矿工挖掘路径
SKIP_HP = 3000          # 本波总血低于此值不烧卡（松弛）

# ★ 救场层：中速及更慢的选卡带「窝瓜 + 小喷/花盆垫材」（运阵手册 §二）
#   ★ 2026-10-19 用户明确快速关选卡：
#     "冰、冰（复制）、咖啡豆、南瓜、核、樱桃、辣椒、曾哥套件（荷叶、大喷、曾哥）；
#      没有窝瓜没有垫材也不需要救场，死了就补"
#   → 所以救场按档位开关，快速/极速整层关掉。
RESCUE = True
RESCUE_BY_TIER = {'慢速': True, '变速': True, '快速': False, '极速': False}
# 旗波要不要窝瓜压冰车（w10）
#   慢速/变速：要（有冰车 + 选卡有窝瓜）
#   快速：选卡没窝瓜 → 不做
#   极速：出怪里根本没冰车 → 不需要
WOGUA_FLAG_BY_TIER = {'慢速': True, '变速': True, '快速': False, '极速': False}

# 快速/极速的"死了就补"：毁掉的 CORE 植物可以重建（不是崩阵）
REBUILD_BY_TIER = {'慢速': False, '变速': False, '快速': True, '极速': True}
# ★ 维护层：补南瓜（125 / 30s CD）—— 不模拟这个，任何阵都会被磨死
REPAIR = True
# ★ 救场能不能借用灰烬（樱桃/辣椒）？
#   C4io 的 AA' 固定在每 4 波的第 2 波，**灰烬零余量**：借一次 = 断一次控丑。
#   所以这里默认 False。打开它可以看到"救场换控丑"的代价（轨道断裂数会飙升）。
RESCUE_ASH = False

# ★ 救场参数（用户 2026-10-18 口径）
STALL_X_LO, STALL_X_HI = 380, 500   # 只在第 6 列这一格下垫材
STALL_HP = 500                      # 血量还高才垫（普通 270 不用垫）
TOMATO_X = 520                      # 窝瓜：进到 6.5 列以内才压
TOMATO_HP = 800                     # 只压值得压的（橄榄/铁桶/巨人）

# ------------------------------------------------------------------ 四档出怪
# 2022 无尽技术考级（用户给定，逐档照抄）
TIERS = {
    '慢速': ['普通', '路障', '橄榄', '小丑', '冰车', '矿工', '蹦极',
             '红眼', '白眼', '气球', '海豚'],
    '变速': ['普通', '读报', '橄榄', '小丑', '冰车', '投篮', '蹦极',
             '红眼', '气球', '潜水', '海豚'],
    '快速': ['普通', '读报', '橄榄', '小丑', '冰车', '舞王', '蹦极',
             '跳跳', '潜水', '气球', '海豚'],
    '极速': ['普通', '读报', '铁门', '小丑', '撑杆', '舞王', '蹦极',
             '跳跳', '潜水', '扶梯', '海豚'],
}

# ★ 关键结构差异：快速/极速**完全没有巨人**
TIER_HAS_GIANT = {'慢速': True, '变速': True, '快速': False, '极速': False}

MODE = '慢速'           # 当前档位，改这里切换
# ★ v0.2.2：`track()` 是 PE.电波钟无炮 的**示例轨道**，主界面已经不再使用它
#   （主界面没选阵解 = 空轨道）。只有回归测试 / 需要复现历史基线时才把它打开。
BUILTIN = False


def _pool(tier):
    lst = TIERS[tier]
    heavy = [z for z in lst if z in ('红眼', '白眼', '橄榄', '铁门', '扶梯', '冰车')]
    light = [z for z in lst if z not in heavy]
    return light, heavy


# ★ 只跑**饱和出怪**（用户 2026-10-18 明确：只打饱和出怪）
#   wiki《技术:出怪机制》饱和一节：126F 后
#     阶数 / 级别上限 / 红眼数量上限 **三条限制全部失效**
#   → 每波 = 纯加权随机填满 50 只，所有类型从 w1 就可能出现
#   （唯一保留的独立规则：蹦极仅旗帜波）
SATURATED = True

# ★ w9/w19 要不要拖时间？这是**打法**不是机制。
#   ★ 2026-10-20 用户纠正："快速关如果有空窗，可能是 w9 收尾没有尽力拖满时间……
#     时间挤一挤还是能挤出一个冰的"
#   → 收尾波的拖时间是**为了把卡 CD 挤出来**，这与"快速关几乎不操作"不矛盾：
#     常规波不停，但 w9/w19 这两波该拖。
#   拖满 45s + 红字 7.2s（[术语] w9/w19 清完后跳红字，7.2s 后刷下一波）。
STALL_WAVES = {'慢速': True, '变速': True, '快速': True, '极速': True}

# 轮数只影响**非饱和**模式下的权重衰减；饱和模式仍要用它算普通/路障的降权
#   轮数 = 已完成 flag 数 / 2 − 1；126F ⇒ 62
ROUND = 62

# ★★ 2026-10-20：给 app.py 用 —— 允许**临时覆盖**本档的允许出怪清单。
#   None = 用 TIERS[tier]（命令行 / 报告生成器的默认行为）。
#   设成列表时，make_wave 只从这份清单里抽（还是饱和 50 只/波）。
KINDS_OVERRIDE = None

_RED = {'used': 0, 'cache': {}}


def reset_spawn_state():
    """每个任务 / 每一局重新开始：红眼累计与逐波缓存都清空。"""
    _RED['used'] = 0
    _RED['cache'] = {}


def wave_script(w, tier=None):
    """按出怪清单 + 饱和规则生成一波（**严格按原版出怪列表**）。

    · 列表顺序保留（`spawn.Wave.order`），引擎按这个顺序生成、选行。
    · 红眼上限是**本轮累计**（[维 09 §七]：达到上限后非旗帜波立刻不再出），
      不再像旧版那样把 50 只硬摊到每一波。
    · 同一波会被引擎多次问到（蹦极判定、波角色、控丑统计）→ 必须缓存，
      否则红眼累计会被重复扣减。
    """
    from . import spawn
    import random as _r
    tier = tier or MODE
    allowed = list(KINDS_OVERRIDE if KINDS_OVERRIDE else TIERS[tier])
    key = (tier, tuple(allowed), ROUND, bool(SATURATED), w)
    if w == 1:
        # 新的一轮：红眼累计从 0 开始，逐波缓存清空
        _RED['used'] = 0
        _RED['cache'] = {}
    if key in _RED['cache']:
        return _RED['cache'][key]
    # ★ 不能用内置 hash()：Python 对 str 的 hash 每次进程都随机化，
    #   会导致同一配置每次跑出不同出怪（这也是之前结果乱跳的根源）。
    import zlib
    seed = zlib.crc32(('%s|%d|%d' % (tier, w, ROUND)).encode()) & 0xffffffff
    rng = _r.Random(seed)
    lst = spawn.make_wave(w, ROUND, allowed, rng,
                          red_used=_RED['used'],
                          saturated=SATURATED)
    _RED['used'] += lst.count('红眼')
    out = spawn.Wave(lst)
    _RED['cache'][key] = out
    return out


def track(w, ctx=None):
    """
    轨道 = **只描述"连续常规波"**，起手 / 旗波 / 收尾 各自另算。

    用户 2026-10-19 最重要的一条纠正：
      "轨道只是用来概述操作，死板执行会出错。无论是什么阵，轨道仅仅表示
       连续常规波的操作，起手、旗波、收尾都是需要另外灵活处理的。"

    所以 20 波拆成四层：

    ┌ 起手（w1/w2、w11/w12）…… 固定动作，不看 CD、不看场面
    │   w1 2-9 反应核 · w2 AA'(2-8 樱桃 + 5 路辣椒)
    │   w11 5-9 反应核 · w12 AA'
    ├ 旗波（w10 / w20）…… 只看两件事
    │   冰杀蹦极（早冰，同时完成本波控丑）
    │   w10 另加窝瓜压冰车（慢速/变速）
    │   ★ "w10 冰杀蹦极后不需要额外的 AA'"
    ├ 常规波（w3/4、w5~8、w13~18）…… C4io 的 N / AA' / I，按 CD + 坑位判定
    └ 收尾（w9 / w19 / w20）…… w9/w19 拖时间，w20 清账
        ★ "w9、w19、w20 共计使用 1~2 次冰减压"

    **补存冰与点冰的优先关系**（这一版新修的坑）：
      原来"补存冰"排在前面，会把冰卡吃掉，导致同一波真正要冻时 `冰` 卡在 CD
      → w10 冰杀蹦极直接 FAIL。现在改成：**本波要冻，就先冻，再用剩下的那张卡补**。
    """
    ctx = ctx or {}
    now = ctx.get('t', 0)
    ready = ctx.get('card_ready', {})
    avg = ctx.get('avg_gap') or 1250
    _AVG[0] = avg

    def ok(name):
        return ready.get(name, 0) <= now

    if w == 1:
        _LAST.clear()
        _LAST.update(freeze_w=-9, owe_aa=False, owe_chili=False,
                     split=(MODE == '快速'), last_n=0)

    main, freeze = [], False

    # ==================================================== 旗波
    if w in (10, 20):
        freeze = True
        if w == 10 and WOGUA_FLAG_BY_TIER.get(MODE, False):
            main.append(('窝瓜压车', 0, None))

    # ==================================================== 极速关：常规波不操作
    elif MODE == '极速':
        pass

    # ==================================================== 起手（固定）
    #   ★ 只对慢速/变速有意义：那是 C4io 的"锚点"。
    #     快速/极速是"逐波控丑（不规则）"，硬塞锚点反而会因为卡 CD 转不动
    #     而出现"整波没有任何控制"的空窗（上一版 w11/w12 就是这样）。
    elif w in (1, 11) and MODE in ('慢速', '变速'):
        if ok('核'):
            main.append(('核', 0, D.KERNEL_ANCHOR[w]))
        else:
            freeze = True
    elif w in (2, 12) and MODE in ('慢速', '变速'):
        main += _aa_ops(ok)
        if not main:
            freeze = True

    # ==================================================== 快速关
    #   ★ 用户 2026-10-19："快速关太快了，2F 里下不了 4 个核，间接导致 w20 冰枯竭。
    #     建议 w10~w20 采用与极速关一样的策略（在 w9 长间隔种大喷，优先 5-7 其次 2-7）"
    #
    #   于是快速关变成**上下半场不对称**（这正是《研讨笔记》§7.4 的原话）：
    #     w1~w9   ：逐波控丑（严谨），核坑按"对格子的需求"让位（优先 2-8）
    #     w9 长间隔：在 5-7 / 2-7 补大喷，用结构替代操作
    #     w10~w19 ：放羊（与极速关一样，不烧卡）
    #     w20     ：冰杀蹦极清账
    elif MODE == '快速':
        if w >= 10:
            # ★ 用户 2026-10-19："快速关 2 路是有限控丑、**5 路是严谨控丑**"。
            #   所以下半场不是全放羊：2 路放弃，但 5 路要继续控。
            #   顺序：灰烬（核 > 樱桃 > 辣椒，全砸 5 路）→ 冰（有存冰就点）。
            #   这也是《研讨笔记》§7.4「上 f 严谨控丑、下 f 放羊」的更准确版本——
            #   放的是 **2 路**，5 路不放。
            if ok('核'):
                main.append(('核', 0, KERNEL_AIM_BY_MODE.get('快速')))
            elif ok('樱桃'):
                main.append(('樱桃', 0, (5, 8)))
            elif ok('辣椒'):
                main.append(('辣椒', 0, None))
            elif ctx.get('ice_stock', D.MAX_ICE_STOCK) >= 1:
                freeze = True
        else:
            if _LAST['owe_chili']:
                _LAST['owe_chili'] = False
                if ok('辣椒'):
                    main.append(('辣椒', 0, None))
            if not main:
                if ok('核'):
                    # 核坑让位：5-7/5-8 要留给大喷与樱桃，核优先走 2-8
                    main.append(('核', 0, KERNEL_AIM_BY_MODE.get('快速')))
                elif ok('樱桃'):
                    _LAST['owe_chili'] = True
                    main.append(('樱桃', 0, (5, 8)))
                elif ok('辣椒'):
                    main.append(('辣椒', 0, None))
                else:
                    freeze = True
            if w == 9:
                # 长间隔施工：先 5-7，再 2-7
                main.append(('种大喷', 0, None))
                main.append(('种大喷', 0, None))

    # ==================================================== 慢速 / 变速
    else:
        # ---- w3 / w4：把节奏铺开，固定早冰
        #   ★ 但 w2 拆开打 AA' 时会欠一个辣椒（split 模式），要在这里还上，
        #     否则 owe_chili 会一直挂到判定波，白白多烧一次冰。
        if w in (3, 4):
            if _LAST['owe_chili'] and ok('辣椒'):
                _LAST['owe_chili'] = False
                main.append(('辣椒', 0, None))
            if not main:
                freeze = True
        # ---- 常规波 + 收尾波统一按判定走。
        #   ★ 用户 2026-10-19 纠正："收尾波的特性是在**执行常规波操作的基础上**
        #     额外补充拖时间或清账操作（慢速关、变速关 w9/w19 没有下早冰，控丑操作丢失）"。
        #   所以 w9 / w19 **不是**"什么都不做"，它们先照常控丑（该 N/AA'/I 就照做），
        #   拖时间由引擎的 45s stall 负责，清账交给 w20。
        #   上一版把 w9 写成 pass，等于白送两波没有控丑的窗口 —— 那是错的。
        #
        #   唯一保留的限制：不在**旗波前一波**点核（w9→w10、w19→w20），
        #   因为旗波自带冰，核留给下一段更值。
        # ---- 收尾波（w9 / w19）：**先早冰**，不点核。
        #   ★ 用户 2026-10-20 两次点名："w9、w19 没有下早冰，控丑操作丢失"。
        #   为什么必须在这里禁核：
        #     核卡 50s CD。若 w9 点核，核一路锁到 w13~w14，
        #     于是 w13~w18 六波全部退化成 I（早冰），
        #     冰需求直接翻倍 → 变速 w15~w18 存冰耗尽、空窗。
        #     这正是用户上一轮说的"变速 w15~w18 空窗"的根因 ——
        #     不是冰不够，是**核被 w9 偷走了**。
        #   w19 同理：w19 点核会让下一个 2F 的 w1（固定核）卡 CD。
        elif w in (9, 19):
            if _LAST['owe_aa']:
                # 上一波点了核 → 本波必须接 AA'（用户的成对口径优先于早冰）
                _LAST['owe_aa'] = False
                main += _aa_ops(ok)
            if not main:
                # ★ 下一波是旗波，**必须留一手冰给它**（w10/w20 的冰杀蹦极是硬要求）。
                #   实测变速偶发 w20 空窗就是这个：w19 把最后一个存冰点掉了。
                #   w9→w10 因为 w9 有 45s 拖时间 + 7.2s 红字，冰卡能转好；
                #   w19→w20 同理，但存冰先见底就没得救，所以这里设个下限。
                freeze = (ctx.get('ice_stock', D.MAX_ICE_STOCK) >= 2
                          or ok('冰') or ok('模仿冰'))

        elif 5 <= w <= 8 or 13 <= w <= 18:
            if w >= 13 and ctx.get('ice_stock', D.MAX_ICE_STOCK) <= 1:
                _LAST['split'] = True
            if _LAST['owe_aa']:
                _LAST['owe_aa'] = False
                main += _aa_ops(ok)
            elif _LAST['owe_chili']:
                _LAST['owe_chili'] = False
                if ok('辣椒'):
                    main.append(('辣椒', 0, None))
            if not main:
                # ★ 用户原话："核 CD 已经好，且樱桃、辣椒 CD **可以保证**能在
                #   N 的下一波后执行 AA'" —— 注意是"下一波能接上"，不是"现在就好"。
                #   所以判据用 `<= now + 一个波长`，否则 15s 波长下永远判不过。
                horizon = now + avg * 0.9
                if (ok('核')
                        and ready.get('樱桃', 0) <= horizon
                        and ready.get('辣椒', 0) <= horizon
                        and _kernel_slack(w) >= 0
                        and (w + 1) not in (10, 20)):
                    _LAST['owe_aa'] = True
                    _LAST['last_n'] = w
                    main.append(('核', 0, None))
                elif ok('樱桃') and ok('辣椒'):
                    # ★★ 2026-10-20 关键修正：**AA' 不是"核的附属品"**。
                    #   C4io = N | AA' | I | I 里，AA' 是独立的一拍 ——
                    #   核转不过来时（波长 10s < 核 CD 50s，20 波最多 4 次核），
                    #   完全可以直接打 AA' 做灰烬控丑，不必退化成冰。
                    #   上一版把 AA' 写成"点核后的下一波"，等于每 4 波只肯用 1 次灰烬，
                    #   剩下的波全去点冰 —— 这才是"存冰枯竭"的真正源头。
                    main += _aa_ops(ok)
                elif ok('樱桃') or ok('辣椒'):
                    # 只剩一张 → 按用户口径"拆开分两波用，全放 5 路"（像快速关那样）
                    _LAST['split'] = True
                    main += _aa_ops(ok)
                else:
                    freeze = True

    # ==================================================== 组装：先冻，再补
    fz = _freeze_ops(ctx, ok) if freeze else []
    avoid = None
    if freeze and ctx.get('ice_stock', D.MAX_ICE_STOCK) == 0:
        # 手上没存冰 → 这一次冰冻要花掉一张冰卡，补种只能用另一张
        avoid = '冰' if ok('冰') else '模仿冰'
    acts = fz + main + _refill_ops(ctx, ok, avoid=avoid)
    if w == 1 and MODE in ('慢速', '变速'):
        # 用户 SOP："w1 … 2-7、5-7 两个临时存冰"
        # ★ 快速/极速不种：快速关下半场放羊、存冰本来就满（4/4），
        #   而且 2-7 / 5-7 要留给 w9 长间隔补的大喷。
        acts = [('种临时冰', 0, None), ('种临时冰', 400, None)] + acts
    return acts


def _kernel_slack(w):
    """
    点完这次核，离最近的**固定核波**（w11 / 下一个 2F 的 w1）还剩多少余量（cs）。
    ≥ 0 才能点，否则会顶掉固定核。
    """
def _kernel_slack(w):
    """
    ★★ 2026-10-20 重写。原来写的是：
        `(下一个固定核波 - w) * 平均波长 − 核CD`
      它的隐含假设是"必须和 w11 / 下个 w1 复用同一个坑"，
      于是变速（9.9s 波长）算下来永远 < 0 → **整局只能点 w1、w11 两次核**。

    但用户的原话只是："w1 在 2-9、w11 在 5-9，**否则坑位不够**"。
    真正的约束有两条：

      ① 卡 CD：核卡 50s（由 `ok('核')` 单独保证，这里不用再算）
      ② **坑位数**：一局可用 9 个坑，每个 180s —— 判定波插核只用
         (5,8)/(5,7)/(2,7)/(6,8)/(6,9)/(1,8)/(1,9) 这 7 个，
         2-9 / 5-9 永远留给锚点。所以只要离固定核波还有 1.5 个波长，
         就不会"顶掉"它。

    返回 ≥ 0 表示允许点核。
    """
    avg = _AVG[0] or 1250
    nxt = 11 if w < 11 else 21
    return (nxt - w) * avg - 1500





_AVG = [1250]


def _aa_ops(ok):
    """
    AA' = 2-8 樱桃 + 5 路辣椒。
    ★ 用户："快速关…樱桃辣椒分两w使用且都砸 5 路"；
      变速后半场存冰枯竭时也可以这样拆（`_LAST['split']`）。
    """
    if _LAST.get('split'):
        # 拆开：这一波先樱桃（5 路），下一波再辣椒
        if ok('樱桃'):
            _LAST['owe_chili'] = True
            return [('樱桃', 0, (5, 8))]
        if ok('辣椒'):
            return [('辣椒', 0, None)]
        return []
    acts = []
    if ok('樱桃'):
        acts.append(('樱桃', 0, (2, 8)))
    if ok('辣椒'):
        acts.append(('辣椒', 0, None))
    return acts


def _refill_ops(ctx, ok, avoid=None):
    """补存冰：位子空着 + 卡槽里的冰（含复制冰）转好 → 补一格。
    avoid = 本波已经被"直接冰冻"花掉的那张卡，补种不许再抢它。"""
    stock = ctx.get('ice_stock', D.MAX_ICE_STOCK)
    acts = []
    if stock < D.MAX_ICE_STOCK:
        if ok('冰') and avoid != '冰':
            acts.append(('种冰', 0, None))
        elif ok('模仿冰') and avoid != '模仿冰':
            acts.append(('种冰2', 0, None))
    return acts


def _freeze_ops(ctx, ok):
    """点冰一次：优先用阵上的预置冰，没有才拿卡直接冻"""
    stock = ctx.get('ice_stock', D.MAX_ICE_STOCK)
    if stock > 0:
        return [('存冰', 0, None)]
    if ok('冰'):
        return [('冰', 0, None)]
    if ok('模仿冰'):
        return [('模仿冰', 0, None)]
    return []


_LAST = {}


TRACK_NAME = '判定式轨道（核+AA\' 成对触发 / 其余早冰控丑）'
