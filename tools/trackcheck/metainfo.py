# -*- coding: utf-8 -*-
"""
metainfo.py —— 全局元信息：命名方案、节奏表、**模型清单**

三块内容：

1. `NAMINGS`：节奏命名的两套方案（2021 传统 / 2026 新版）＋ 双轨显示。
   依据 `docs/知识库/08-维基-节奏体系与命名规范.md`（该篇取代 04 的命名部分）。
   ★ PE.电波钟无炮 的 C4io 在两套方案下**写法相同**（C 系保留原名），
     只有 C4u / C6u 这类夜间双冰会变成 N4 / N6。

2. `RHYTHMS`：节奏系 + 节奏型，每个都带 `trad` / `new` 两个名字与简式轨道。

3. `PLANTS` / `ZOMBIES` / `FIELDS`：**已经建模到什么程度**的清单，
   `note` 一律用自然语言写"简化模型等价于什么"，供设置页展示、也供回答"做了什么"。
"""

VERSION = '1.0.0'
SCHEMA = 'trackcheck-plan/3'

from . import fields as _fl

NAMINGS = [
    dict(id='2026', label='2026 新版',
         note='P/S/D/I/F/A/N 七类；字母只在开头；参数 = 减速×2 + 加速×1'),
    dict(id='2021', label='2021 传统',
         note='C/P/S/ch/Cxu/I 六类；本库旧文献的写法（ch5 = 今天的 D5）'),
    dict(id='both', label='双轨：新名（旧名）',
         note='知识库默认写法，两者都给'),
]
DEFAULT_NAMING = 'both'


def fmt(cell, naming):
    """把一个 {trad,new,same} 的名字按当前方案拼出来"""
    if not cell:
        return ''
    trad, new = cell.get('trad') or '', cell.get('new') or ''
    if naming == '2021':
        return trad or new
    if naming == '2026':
        return new or trad
    if trad and new and trad != new:
        return '%s（%s）' % (new, trad)
    return new or trad


# ------------------------------------------------------------------ 节奏
# ★★ 2026-10-22 用户：「节奏型选项范围太小（不包含 P3n；其实官方命名体系也不包含 P3n，
#   这个节奏名的含义是把 P3 中的一对炮换成了核弹）」→ 按《节奏体系全谱》《节奏命名规范》
#   与 26 版速查表把库补全。
#
#   每个 preset：
#     id     = 26 版名（C 系保留原名；官方没有的自造名单独在 note 里说明）
#     trad   = 2021 版 / 更早的旧名
#     new    = 26 版名（多数与 id 相同）
#     beats  = 简式轨道（**一对炮写 PP**，速查表写 P），供「快捷布置阵解」直接填
#     gaps   = 波长串（秒）；None = 文档没给确定值（快捷布置留空让用户自己填）
#     ice    = 一循环的冰波数（0/1/2/3）
#     note   = 说明
RHYTHMS = [
    dict(system='C', label=dict(trad='C 系（灰烬 + 冰，无炮；26 版归入 P 大类）',
                                new='C（历史遗留，保留原名）'),
         presets=[
             dict(id='C4io', trad='C4io', new='C4io',
                  beats=['N', "AA'", 'PP', 'I'], gaps=[None, None, None, None],
                  ice=1, note='4 波 50s；参数=过怪量 4。AA′ 可换成 PP / I（看阵）'),
             dict(id='C3', trad='C3', new='C3', beats=["AA'", 'I', 'PP'],
                  gaps=[None, None, None], ice=1, note='3 波；参数=过怪量 3'),
             dict(id='C2', trad='C2', new='C2', beats=['I', 'PP'],
                  gaps=[None, None], ice=1, note='2 波；参数=过怪量 2'),
         ]),
    dict(system='P', label=dict(trad='P 系（炮，0 冰波，36s）',
                                new='P（Pao）'),
         presets=[
             dict(id='P3', trad='P3', new='P3', beats=['PP', 'PP', 'PP'],
                  gaps=[12, 12, 12], ice=0, note='12s 一对炮，6 炮循环'),
             dict(id='P3n', trad='P3-n', new='P3-n', beats=['PP', 'PP', 'N'],
                  gaps=[12, 12, 12], ice=0,
                  note='**P3 把一对炮换成核弹**（-xn 后缀，x=1 可省）。'
                       '官方体系里没有这个叫法，是社区自造名；'
                       'P3-n 是纯伤害解，没有止血手段，晚一次就永久落后'),
             dict(id='P4', trad='P4', new='P4', beats=['PP', 'PP', 'PP', 'PP'],
                  gaps=[9, 9, 9, 9], ice=0, note='9s 一对炮，8 炮循环（经典八炮）'),
             dict(id='P5', trad='P5', new='P5', beats=['PP'] * 5,
                  gaps=[7.2] * 5, ice=0, note='7.2s 一对炮，10 炮循环（经典十炮）'),
             dict(id='P5-2i', trad='ch7', new='P5-2i',
                  beats=['PP', 'PP', 'PPI', 'PP', 'PPI'],
                  gaps=[6, 6, 9, 6, 9], ice=2, note='旧称 ch7，26 版改名 P5-2i'),
             dict(id='P6', trad='P6', new='P6', beats=['PP'] * 6,
                  gaps=[6] * 6, ice=0, note='6s 一对炮，12 炮 = 自然上限'),
             dict(id='P6-2i', trad='', new='P6-2i',
                  beats=['PP', 'PP', 'PP', 'PP', 'PPI', 'PPI'],
                  gaps=[6] * 6, ice=2, note='12 炮 + 两张冰'),
             dict(id='P6-2n', trad='', new='P6-2n',
                  beats=['PP', 'PP', 'PP', 'PP', 'N', 'N'],
                  gaps=[6] * 6, ice=0, note='12 炮里有两发核；8 炮就够'),
         ]),
    dict(system='S', label=dict(trad='S 系（白天单冰，36s）', new='S（Single 单冰）'),
         presets=[
             dict(id='S3', trad='S3', new='S3', beats=['I-PP', 'PP'],
                  gaps=[24, 12], ice=1, note='24+12；边路大喷在慢节奏下容易死'),
             dict(id='S4', trad='S4*', new='S4', beats=['I-PP', 'PP', 'PP'],
                  gaps=[20, 7.5, 7.5], ice=1,
                  note='⚠️ 26 版 S4 ← 旧 S4*；旧文献的 "S4" 其实指 S4s'),
             dict(id='S4u', trad='', new='S4u', beats=['I-PP', 'PP', 'PP'],
                  gaps=[20, 9, 6], ice=1, note='冰波/加速波一长一短，总长不变'),
             dict(id='S4s', trad='S4', new='S4s', beats=['I-PP', 'PP', 'PP'],
                  gaps=[18, 9, 9], ice=1, note='⚠️ 26 版 S4s ← 旧 S4'),
             dict(id='S5', trad='S5', new='S5', beats=['I-PP', 'PP', 'PP', 'PP'],
                  gaps=[18, 6, 6, 6], ice=1, note='18+6×3；8 炮'),
             dict(id='S5s', trad='', new='S5s', beats=['I-PP', 'PP', 'PP', 'PP'],
                  gaps=[12.5, 7.5, 7.5, 7.5], ice=1, note='冰波缩短版'),
             dict(id='S6', trad='S6', new='S6', beats=['I-PP'] + ['PP'] * 4,
                  gaps=[12] + [6] * 4, ice=1, note='12+6×4；10 炮'),
         ]),
    dict(system='D', label=dict(trad='ch 系（白天双冰，36s）', new='D（Day 双冰）'),
         presets=[
             dict(id='D4', trad='ch4', new='D4', beats=['I-PP', 'I-PP'],
                  gaps=[18, 18], ice=2, note='18×2；4 炮'),
             dict(id='D4u', trad='ch4u', new='D4u', beats=['I-PP', 'I-PP'],
                  gaps=[16, 19], ice=2, note='长短波（冰杀矿工）'),
             dict(id='D4b', trad='ch4*', new='D4b', beats=['I-PP', 'I-PP'],
                  gaps=[20, 20], ice=2, note='延长版'),
             dict(id='D5', trad='ch5', new='D5', beats=['I-PP', 'I-PP', 'PP'],
                  gaps=[15, 15, 6], ice=2, note='15+15+6；6 炮'),
             dict(id='D5u', trad='ch5u', new='D5u', beats=['I-PP', 'I-PP', 'PP'],
                  gaps=[13, 16, 6], ice=2, note='挤出 13s 打 7 列冰车'),
             dict(id='D5s', trad='', new='D5s', beats=['I-PP', 'I-PP', 'PP'],
                  gaps=[13.6, 13.6, 7.5], ice=2, note='冰波缩短版'),
             dict(id='D5b', trad='ch5*', new='D5b', beats=['I-PP', 'I-PP', 'PP'],
                  gaps=[17, 17, 6], ice=2, note='延长版'),
             dict(id='D6', trad='ch6', new='D6', beats=['I-PP', 'PP', 'I-PP', 'PP'],
                  gaps=[12, 6, 12, 6], ice=2, note='12+6+12+6；8 炮（常用 11.5 防丑）'),
             dict(id='D6n', trad='ch6-n', new='D6n',
                  beats=['I-PP', 'I-PP', 'N', 'PP'],
                  gaps=[13, 13, 6, 6], ice=2, note='双冰里有一发用核'),
             dict(id='邻D6', trad='邻ch6', new='邻D6',
                  beats=['I-PP', 'I-PP', 'PP', 'PP'],
                  gaps=[12, 12, 6, 6], ice=2, note='"邻"在 26 版是默认、可省略'),
         ]),
    dict(system='I', label=dict(trad='I 系（白昼连续冰波）', new='I（Ice 连续冰波）'),
         presets=[
             dict(id='I6', trad='c6i', new='I6', beats=['I-PP', 'I-PP', 'I-PP'],
                  gaps=[13, 13, 13], ice=3, note='13×3；6 炮'),
             dict(id='I5', trad='', new='I5', beats=['I-PP', 'I-PP'],
                  gaps=[14, 14], ice=2, note='14×2.5；5 炮（勿与旧称 I5=D5# 混淆）'),
             dict(id='I4', trad='', new='I4', beats=['I-PP', 'I-PP'],
                  gaps=[17.55, 17.55], ice=2, note='17.55×2；4 炮'),
         ]),
    dict(system='F', label=dict(trad='（2021 归 I/C 系：c6x / i7）',
                                new='F（Fifty 三冰，50s）'),
         presets=[
             dict(id='F6', trad='c6x', new='F6', beats=['I-PP', 'I-PP', 'I-PP'],
                  gaps=[16, 19, 19], ice=3, note='50s 三冰；4 炮'),
             dict(id='F7', trad='i7', new='F7', beats=['I-PP', 'I-PP', 'I-PP', 'PP'],
                  gaps=[15, 15, 15, 6], ice=3, note='6 炮'),
             dict(id='F7n', trad='c7i / ch4-n', new='F7n',
                  beats=['I-PP', 'I-PP', 'I-N', 'PP'],
                  gaps=[18, 18, 12, 6], ice=3, note='4 炮'),
             dict(id='F8', trad='c8x / 间c8i', new='F8',
                  beats=['I-PP', 'I-PP', 'PP', 'I-PP', 'PP'],
                  gaps=[12, 12, 6, 12, 6], ice=3, note='8 炮'),
             dict(id='F8n', trad='邻c8i / c6i-n', new='F8n',
                  beats=['I-PP', 'I-PP', 'I-PP', 'N', 'PP'],
                  gaps=[13, 13, 13, 6, 6], ice=3, note='6 炮'),
         ]),
    dict(system='A', label=dict(trad='（2021 归 Cxu：c3n / c4n / c7n）',
                                new='A（Ash 夜晚单冰，50s）'),
         presets=[
             dict(id='A3', trad='c3n', new='A3', beats=['I-N', 'N'],
                  gaps=[25, 25], ice=1, note='0 炮'),
             dict(id='A4', trad='c4n / s3n', new='A4', beats=['PP', 'C', 'C'],
                  gaps=[21, 14, 14], ice=1,
                  note='`C` 是占位符，按顺序填 N / N′ / I'),
             dict(id='A7', trad='c7n / s5n', new='A7',
                  beats=['PP', 'C', 'PP', 'PP', 'C'],
                  gaps=[12.5, 7.5, 12.5, 12.5, 7.5], ice=1, note='6 炮'),
         ]),
    dict(system='N', label=dict(trad='Cxu 系（夜间双冰）', new='N（Night 夜间双冰，50s）'),
         presets=[
             dict(id='N4', trad='C4u', new='N4', beats=['I-PP', 'I-N'],
                  gaps=[25, 25], ice=2, note='25×2；2 炮'),
             dict(id='N5', trad='C5u', new='N5', beats=['I-PP', 'I-PP', 'N'],
                  gaps=[22, 22, 6], ice=2, note='22+22+6；3 炮'),
             dict(id='N5s', trad='c5u', new='N5s', beats=['I-PP', 'I-PP', 'N'],
                  gaps=[20, 20, 10], ice=2, note='冰波缩短版'),
             dict(id='N6', trad='', new='N6', beats=['I-PP', 'I-PP', 'N', 'PP'],
                  gaps=[20, 20, 7.5, 7.5], ice=2, note='20+20+7.5×2；4 炮'),
             dict(id='N6s', trad='C6u / c6u', new='N6s',
                  beats=['I-PP', 'I-PP', 'N', 'PP'],
                  gaps=[18, 18, 9, 9], ice=2,
                  note='**18+18+9+9 = 54s**；4 炮。'
                       '⚠️ 别和 N6（20,20,7.5×2）搞混 —— 差 2 秒'),
             dict(id='N6d', trad='', new='N6d', beats=['I-PP', 'I-N', 'N', 'PP'],
                  gaps=[20, 20, 7.5, 7.5], ice=2, note='4 炮'),
             dict(id='对N6', trad='对c6u', new='对N6',
                  beats=['I-PP', 'PP', 'I-PP', 'N'],
                  gaps=[19, 6, 19, 6], ice=2, note='6 炮'),
             dict(id='N7', trad='C7u', new='N7',
                  beats=['I-PP', 'I-PP', 'PP', 'N', 'PP'],
                  gaps=[18, 18, 6, 6, 6], ice=2, note='5 炮'),
             dict(id='N7u', trad='', new='N7u',
                  beats=['I-PP', 'I-PP', 'PP', 'N', 'PP'],
                  gaps=[16, 19, 6, 6, 6], ice=2, note='5 炮'),
             dict(id='间N7', trad='间c7u', new='间N7',
                  beats=['I-PP', 'PP', 'I-PP', 'N', 'PP'],
                  gaps=[18, 6, 18, 6, 6], ice=2, note='6 炮'),
             dict(id='N8', trad='C8u', new='N8',
                  beats=['I-PP', 'I-PP', 'PP', 'PP', 'N', 'PP'],
                  gaps=[13, 13, 6, 6, 6, 6], ice=2, note='7 炮'),
             dict(id='对N8', trad='对c8u', new='对N8',
                  beats=['I-PP', 'PP', 'PP', 'I-PP', 'N', 'PP'],
                  gaps=[13, 6, 6, 13, 6, 6], ice=2, note='7 炮'),
             dict(id='间N8', trad='间c8u', new='间N8',
                  beats=['I-PP', 'PP', 'I-PP', 'PP', 'N', 'PP'],
                  gaps=[13, 6, 13, 6, 6, 6], ice=2, note='8 炮'),
             dict(id='N9', trad='C9u', new='N9',
                  beats=['I-PP', 'PP', 'I-PP', 'PP', 'N', 'PP', 'PP'],
                  gaps=[12, 6, 12, 6, 6, 6, 6], ice=2, note='8 炮'),
         ]),
    dict(system='自定义', label=dict(trad='自定义', new='自定义'), presets=[]),
]

RHYTHM_BY_ID = {p['id']: p for r in RHYTHMS for p in r['presets']}


def rhythm_label(rhythm, naming=DEFAULT_NAMING):
    """节奏型显示名（plan.rhythm 里存的是 id）"""
    if not rhythm:
        return ''
    pid = rhythm.get('id') or rhythm.get('name') or ''
    p = RHYTHM_BY_ID.get(pid)
    if p:
        return fmt(p, naming)
    return fmt(dict(trad=rhythm.get('name'), new=rhythm.get('id')), naming)


def system_label(system, naming=DEFAULT_NAMING):
    for r in RHYTHMS:
        if r['system'] == system:
            return fmt(r['label'], naming)
    return system


def rhythm_catalog(naming=DEFAULT_NAMING):
    """给前端：每个系 + 每个节奏型的两种名字都带上"""
    out = []
    for r in RHYTHMS:
        out.append(dict(
            system=r['system'],
            label=fmt(r['label'], naming),
            labels=r['label'],
            presets=[dict(id=p['id'], label=fmt(p, naming),
                          trad=p.get('trad'), new=p.get('new'),
                          beats=p['beats'], gaps=p.get('gaps') or [],
                          ice=p.get('ice', 0), note=p.get('note', ''))
                     for p in r['presets']]))
    return out


# ------------------------------------------------------------------ 植物（选卡）
# 初代 47 张常规卡 + 模仿者
PLANTS = [
    '豌豆射手', '向日葵', '樱桃', '坚果', '土豆雷', '寒冰射手', '大嘴花', '双发射手',
    '小喷菇', '阳光菇', '大喷菇', '墓碑吞噬者', '魅惑菇', '胆小菇', '寒冰菇', '毁灭菇',
    '睡莲', '窝瓜', '三线射手', '缠绕海草', '辣椒', '地刺', '火炬树桩', '高坚果',
    '海蘑菇', '路灯花', '仙人掌', '三叶草', '分裂射手', '杨桃', '南瓜', '磁力菇',
    '卷心菜投手', '花盆', '玉米投手', '咖啡豆', '大蒜', '保护伞', '金盏花', '西瓜投手',
    '机枪射手', '双子花', '忧郁菇', '香蒲', '冰瓜', '吸金磁', '地刺王', '玉米炮',
]

# ★ PvZ Tools / Tools 阵型字符串（RFC1437）用的植物代号：code = index + 1
#   顺序 = 游戏内 SeedType 0..47，**不要改**，否则导入导出的阵型会错位。
PLANT_CODES = PLANTS
MIMIC = '模仿者'

# 引擎真正认识、能打出效果的卡（其余卡在阵解里只会被校验标红）
ENGINE_CARDS = ['寒冰菇', '模仿寒冰菇', '毁灭菇', '模仿毁灭菇', '樱桃', '辣椒', '窝瓜',
                '小喷菇', '花盆', '南瓜', '大蒜', '咖啡豆', '大喷菇',
                '忧郁菇', '冰瓜', '香蒲', '荷叶', '保护伞', '双子花', '玉米炮',
                '地刺', '地刺王', '寒冰射手', '西瓜投手']


# ------------------------------------------------------------------ 模型清单
# level: full=走位/受击/生死全程；part=参与伤害与血量，但专项机制简化；
#        watch=只做风险提示，不模拟动作；data=只有数据表，没进模拟
ZOMBIES = [
    dict(name='普通', level='full', hp=270,
         note='按速度表非匀速直走（0.23~0.37×0.47 折算），受击框 (x+10, 宽42)，'
              '血 270；被打死即消失；减速时**位移与动画都 ×0.5**（两条腿走）'),
    dict(name='路障', level='full', hp=640, note='同普通，首饰 370 + 本体 270'),
    dict(name='铁桶', level='full', hp=1370, note='同普通，铁桶不减伤，只加血'),
    dict(name='读报', level='full', hp=420,
         note='报纸 150（**二类防具**：只挡平射）+ 本体 270；'
              '报纸被打掉后发愣 1~2s，然后 1.8s/格 暴走'),
    dict(name='铁门', level='full', hp=1370, note='**二类防具**：沙门 1100 只挡平射，AoE / 投掷 / 喷雾直接打本体 270'),
    dict(name='撑杆', level='full', hp=500,
         note='**快速档**（0.66~0.68）跑过来，遇到第一株植物**飞跃**它'
              '（落地在"目标植物 x − 70"，[精 11.2]），之后回落慢速档；'
              '高坚果挡得住（不跳，改成啃）'),
    dict(name='扶梯', level='full', hp=1000,
         note='**快速档**（0.66~0.68）的步行者（用户口径「速度较快的快速僵尸」）；'
              '梯子 500 是**二类防具**（只挡平射）；梯子本身不模拟（不会真的给南瓜架梯）'),
    dict(name='橄榄', level='full', hp=1670, note='快走（0.66~0.68），血厚，被窝瓜/核照吃 1800'),
    dict(name='白眼', level='full', hp=3000,
         note='巨人：受击框 (x−35, 宽70)（正中央就跨格）；每 330cs 砸一次 1800'
              '（**被减速时动作减半 → 660cs**）；血量首次 ≤ 50%（1500）时投出小鬼；'
              '**必须打满 3000 才算解除**，没有低血豁免'),
    dict(name='红眼', level='full', hp=6000,
         note='同白眼，血 6000（首次 ≤ 3000 时投出小鬼）；'
              '这两只是"必须拖时间"的根源'),
    dict(name='冰车', level='full', hp=1350,
         note='速度由横坐标定（x≥700 时 0.25，x<400 时 0.10，中间线性）；'
              '碾压判定 + 铺冰道（**车死冰道不消失**）；'
              '受击框 (-10, 宽100)（向右伸出一截，与被碾植物同格时也算命中）；'
               '**免疫冰冻与减速**'),
    dict(name='小丑', level='full', hp=500,
         note='**实体化**：盒子早/晚两档随机；走到第几列炸是位置问题，'
              '所以逐只记结局（炸前被打死 / 炸空 / 炸掉哪个 core）；'
               '**被减速时开盒与引信倒计时只走 0.5 倍速**'),
    dict(name='舞王', level='full', hp=500,
         note='走到 7 列（x≤520）时**滑步**：按「滑步」档 0.79~0.81 后退一格'
              '（⚠️位移量 80px 待核），然后每 8s 召一批伴舞；'
              '跳舞段行走 **5.5s/格**（图鉴，比原来快 35% 的「中速」慢）'),
    dict(name='伴舞', level='part', hp=270, note='由舞王召出，按普通僵尸走；速度同舞王（图鉴 5.5s/格）'),
    dict(name='矿工', level='full', hp=370,
         note='**完整模型**：地下 1.2s/格 挖到底线（不与植物交互；'
              '**只有灰烬 P/A/A′/N 打得到**，窝瓜·冰瓜·喷雾都不行）'
              '→ 出土 130cs + 眩晕 350cs → **向右** 7s/格 啃后场；'
              '挖掘中被磁力菇吸走镐子 → 立即出土、向左走、不眩晕；'
               '**挖掘段是匀速**（减速 ×0.4），出土后按两腿算（×0.5）'),
    dict(name='跳跳', level='full', hp=500,
         note='**不啃植物**，按「快速」档 0.66~0.68 一路往前'
              '（用户：速度仅比滑步慢一档）；跳跃轨迹不模拟；'
               '**匀速僵尸** → 减速时只减位移（×0.4）'),
    dict(name='潜水', level='part', hp=270,
         note='水路专用；**不走路、不咬人** —— 血量并入本波总血，'
              '按它所在路的 dps 逐格扣掉（潜行/浮出不模拟）'),
    dict(name='海豚', level='full', hp=500,
         note='只能在水路。**骑海豚段 0.8s/格**（1.0 px/cs），跳过第一个植物后'
              '水豚消失 → 4.7s/格；出场先「离岸」136cs。**不计入阵线**；'
               '**骑海豚冲锋段是匀速**（减速 ×0.4），之后按两腿算（×0.5）'),
    dict(name='气球', level='part', hp=290,
         note='**不走路** —— 血量并入本波总血按路 dps 扣；三叶草可一键清光（见植物侧）；'
              '**飞行是匀速** → 减速只减位移（×0.4）'),
    dict(name='蹦极', level='watch', hp=450,
         note='**不走路，只按波做判定**：本波最多 n 只，按价值挑「既不在伞下、'
              '也不在冰杀定式下」的植物当目标 → 冰杀定式那格要冰、其余要炮盖到；'
              '都没覆盖就偷走。炮不会被锁定，垫材不算目标'),
    dict(name='投篮', level='full', hp=850,
         note='**完整模型**：216cs/格 步行；生成 473cs 就绪 + 74cs 首投，'
              '之后每 300cs 一发；篮球 199cs 后落地砸本路最靠左的植物（75 伤害），'
              '落地那一刻有伞就挡下；投掷前击杀即无效；'
               '**车是匀速** → 减速只减位移（×0.4），投掷间隔不变'
               '（用户 2026-10-24 确认）'),
    dict(name='小鬼', level='full', hp=270,
         note='落地后按步行者走（0.23~0.37），会真的啃植物；**不计入阵线**。'
              '**飞行段完整建模**（仅在阵解用了拦截炮 D 时启用）：巨人血量 ≤ 50% 投出，'
              '标准斜抛（起抛高度 88px、横向 3.07px/cs、滞空 110~125cs、'
              '最高点 127~146px），落点取 [精]「巨人坐标与小鬼落点坐标」实测表；'
              '**高度走的是 y 轴**（游戏没有 z 轴，行轴与高度轴复用同一个 y）'
              '→ 拦截炮在最高点也炸得到'),
    dict(name='旗帜', level='data', hp=270, note='旗帜波整体右移 40px 已实现；僵尸本体按普通处理'),
    dict(name='雪人', level='data', hp=1350, note='只有数据表，出怪里不可选，未进模拟'),
]

# level: full=参与伤害结算与存活；part=作为格子上的植物存在（有血、会被啃），
#        action=只作为"一次性操作"存在；todo=只在选卡里可选，引擎没有行为
PLANTS_MODEL = [
    dict(name='忧郁菇', level='full',
         note='每 193cs 一轮、一轮 **4 次命中**（74/102/130/158cs 各 20），'
              '3×3 范围；用"受击框相交"判命中，不是中心点'),
    dict(name='大喷菇', level='full', note='每 143cs 一次 20 伤害，单行，命中范围 +60~+400'),
    dict(name='冰瓜', level='full',
         note='每 293cs 抛一发：直击 80 + 3×3 溅射（574/n，上限 26、下限 1），'
              '命中即挂 1000cs 减速 —— 全阵唯一常驻减速源'),
    dict(name='香蒲', level='part',
         note='只作为 **CORE** 记入崩阵判定（占一格、可被啃）；'
              '**不产生任何输出**（防空与对地都没模拟）'),
    dict(name='双子花', level='full', note='每 2400cs +50 阳光；阳光封顶 9990'),
    dict(name='睡莲', level='part',
         note='占格；**水路基座** —— PE / FE 的水上空地必须先种睡莲才能种别的'
              '（用户 2026-10-22）'),
    dict(name='保护伞', level='part',
         note='占格；**3×3（含自身格）**挡住投篮的篮球、'
              '也让蹦极跳过这一格；本身不产生输出'),
    dict(name='玉米炮', level='full',
         note='**1×2 占格**；开炮 CD 3475cs；圆形 R=115 炸 1800；'
              '**轨道里写的落点就是爆炸中心**（结果导向，不做"准星 −7"折算，'
              '也不计释放→爆炸的 378cs），爆心 y = 同行植物 y + 40'),
    dict(name='小喷菇', level='part',
         note='垫材：0 阳光、7.5s 充能；落地后钉住一只僵尸一段时间'),
    dict(name='胆小菇', level='part',
         note='只当**垫材 4**：25 阳光、7.5s 充能，落地钉住一只僵尸；'
              '不产生任何输出'),
    dict(name='花盆', level='part',
         note='**屋顶基座**：RE 空地必须先放花盆；同时是第二张垫材（25 阳光、7.5s）'),
    dict(name='南瓜', level='full',
         note='独立 4000 血的一层壳，先扣南瓜再扣植物；补种消耗 125 阳光；'
              '**挂梯子的南瓜（梯子南瓜）会被巨人/车以外的僵尸直接无视**'),
    dict(name='咖啡豆', level='action',
         note='一次性：唤醒**所在格睡着的蘑菇**；白天场蘑菇种下就是睡着的'),
    dict(name='毁灭菇', level='action', note='一次性：圆形 R=250 炸 1800，留下弹坑（一段时间不能种）'),
    dict(name='樱桃', level='action', note='一次性：圆形 R=115 炸 1800'),
    dict(name='辣椒', level='action', note='一次性：整行 1800，并烧掉该行冰道'),
    dict(name='窝瓜', level='action', note='一次性：1 格宽 1800，可指定落点（压冰车就是用这个）'),
    dict(name='寒冰菇', level='action',
         note='种下即"睡着"（白天场），被咖啡豆唤醒后全场冰冻 2000cs（含减速）。'
              '阵图里写 `awake: false` 就是「装着睡着的冰的格子」'),
    dict(name='墓碑吞噬者', level='action',
         note='简化：**直接清除目标格的墓碑**（[精 三] 吞碑 448~471cs）'),
    dict(name='火炬树桩', level='part',
         note='让穿过它的豌豆变火豌豆：伤害 ×2，并带 40/n 溅射（上限 13）'),
    dict(name='地刺', level='full',
         note='**不挡路、不被啃**（普通僵尸直接走过去）：101cs 一次 20 伤害，'
              '判定就是这一格（x+21~+49）。巨人砸 **1 次**就毁；被冰车/投篮车碾到即毁'),
    dict(name='地刺王', level='full',
         note='同地刺，但每 101cs **两次**命中（30/68cs 各 20 → 共 40）；'
              '巨人要砸 **9 次**（withstand 8，第 9 次碎）；'
              '**能与冰车/投篮车同归于尽**（每次碾掉一格车，自己 −1 次）'),
    dict(name='高坚果', level='full',
         note='8000 血；**挡得住撑杆/跳跳的跳越**（撑杆改成啃）'),
    dict(name='三叶草', level='action', note='**秒杀全场气球**（简化：直接扣掉本波气球那部分血量）'),
    dict(name='分裂射手', level='full',
         note='前 1 发 + 后 2 发，各 20（[精 5.2] 25 / 25、50）'),
    dict(name='机枪射手', level='full',
         note='一次 4 发、各 20（[精 5.2] 32、49、65、82）'),
    dict(name='磁力菇', level='full',
         note='吸走**金属物件**（R=270，对啃食者 320）—— 只有这 7 种：'
              '铁桶 / 铁门 / 橄榄头盔 / 梯子 / 小丑的盒子（→ 永不爆炸）/ '
              '矿工的镐子（→ 立即出土、向左走、不眩晕）/ 跳跳的跳跳杆'
              '（→ 变步行啃食）。**报纸（纸）和路障锥（塑料）吸不动**'),
    dict(name='向日葵', level='full',
         note='每 24s 产 25 阳光（⚠️ 生产节奏用 wiki 常用值，未逐 cs 核对）'),
    dict(name='阳光菇', level='full',
         note='小的时候每 24s 产 15 阳光，约 120s 后长大变成 25；阵图里预置的视为已长大'),
    dict(name='大蒜', level='full',
         note='换行：2-9→1 路、5-9→6 路（不跨水陆）；每口 100 伤害；被车碾即失效'),
]

PLANTS_TODO = [p for p in PLANTS if p not in
               {x['name'] for x in PLANTS_MODEL}]

FIELDS = _fl.models()['list']
FIELDS_NOTE = _fl.models()['note']


def models():
    """给设置页 / /api/models 用的一份完整清单"""
    return dict(
        version=VERSION, schema=SCHEMA,
        naming=dict(options=NAMINGS, default=DEFAULT_NAMING),
        rhythms=rhythm_catalog(DEFAULT_NAMING),
        plants=dict(
            all=PLANTS, mimic=MIMIC, engine=ENGINE_CARDS,
            modeled=PLANTS_MODEL,
            pending=PLANTS_TODO,
        ),
        zombies=ZOMBIES,
        fields=dict(list=FIELDS, note=FIELDS_NOTE),
        summary=dict(
            plants_modeled=len(PLANTS_MODEL),
            zombies_modeled=len([z for z in ZOMBIES if z['level'] in ('full', 'part')]),
            fields_playable=[f['code'] for f in FIELDS],
            fields=list(_fl.codes()),
        ),
    )
