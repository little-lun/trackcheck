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

VERSION = '0.2.6'
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
RHYTHMS = [
    dict(system='C', label=dict(trad='C 系（灰烬 + 冰）', new='C（归入 P 大类，保留原名）'),
         presets=[
             dict(id='C4io', trad='C4io', new='C4io', beats=['N', "AA'", 'I', 'I'],
                  note='4 拍循环，参数用过怪量'),
             dict(id='C4u', trad='C4u', new='N4', beats=['I', 'N', 'I', 'N'],
                  note='夜间双冰 4 拍'),
             dict(id='C6u', trad='C6u', new='N6', beats=['I', 'N', 'I', 'N', 'N', 'P'],
                  note='夜间双冰 6 拍'),
         ]),
    dict(system='P', label=dict(trad='P 系（炮）', new='P（Pao 炮，无冰波，36s）'),
         presets=[
             dict(id='P4', trad='P4', new='P4', beats=['P', 'P', 'P', 'P']),
             dict(id='P5', trad='P5', new='P5', beats=['P'] * 5),
             dict(id='P6', trad='P6', new='P6', beats=['P'] * 6),
         ]),
    dict(system='S', label=dict(trad='S 系（白天单冰）', new='S（Single 单冰，36s）'),
         presets=[
             dict(id='S4', trad='S4', new='S4s', beats=['I', 'P', 'P', 'P'],
                  note='⚠️ 26 版的 S4s 才是旧 S4；26 版 S4 = 旧 S4*'),
             dict(id='S5', trad='S5', new='S5', beats=['I'] + ['P'] * 4),
             dict(id='S6', trad='S6', new='S6', beats=['I'] + ['P'] * 5),
         ]),
    dict(system='D', label=dict(trad='ch 系（白天双冰）', new='D（Day 双冰，36s）'),
         presets=[
             dict(id='D4', trad='ch4', new='D4', beats=['I', 'P', 'I', 'P']),
             dict(id='D5', trad='ch5', new='D5', beats=['I', 'P', 'I', 'P', 'P']),
             dict(id='D6', trad='ch6', new='D6', beats=['I', 'P', 'P', 'I', 'P', 'P']),
         ]),
    dict(system='I', label=dict(trad='I 系（连续冰波）', new='I（Ice 连续冰波）'),
         presets=[
             dict(id='I5', trad='I5', new='I5', beats=['I', 'P', 'I', 'P']),
             dict(id='I6', trad='c6i', new='I6', beats=['I', 'P'] * 3),
         ]),
    dict(system='F', label=dict(trad='（2021 归 I 系：c6x / i7）', new='F（Fifty 三冰，50s）'),
         presets=[
             dict(id='F6', trad='c6x', new='F6', beats=['I', 'P'] * 3),
             dict(id='F7', trad='i7', new='F7', beats=['I', 'P', 'I', 'P', 'I', 'P', 'P']),
         ]),
    dict(system='A', label=dict(trad='（2021 归 Cxu：c3n / c4n）', new='A（Ash 夜晚单冰，50s）'),
         presets=[
             dict(id='A4', trad='c4n', new='A4', beats=['P', 'C', 'C']),
             dict(id='A7', trad='c7n', new='A7', beats=['P', 'C', 'P', 'P', 'C']),
         ]),
    dict(system='N', label=dict(trad='Cxu（夜间双冰）', new='N（Night 夜间双冰，50s）'),
         presets=[
             dict(id='N4', trad='C4u', new='N4', beats=['I', 'P', 'I', 'N']),
             dict(id='N5', trad='C5u', new='N5', beats=['I', 'P', 'I', 'P', 'N']),
             dict(id='N6', trad='C6u', new='N6', beats=['I', 'P', 'I', 'P', 'N', 'P']),
             dict(id='N7', trad='C7u', new='N7', beats=['I', 'P', 'I', 'P', 'P', 'N', 'P']),
             dict(id='N8', trad='C8u', new='N8',
                  beats=['I', 'P', 'I', 'P', 'P', 'P', 'N', 'P']),
             dict(id='N9', trad='C9u', new='N9',
                  beats=['I', 'P', 'P', 'I', 'P', 'P', 'N', 'P', 'P']),
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
                          beats=p['beats'], note=p.get('note', ''))
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
              '血 270；被打死即消失；减速时速度 ×0.5'),
    dict(name='路障', level='full', hp=640, note='同普通，首饰 370 + 本体 270'),
    dict(name='铁桶', level='full', hp=1370, note='同普通，铁桶不减伤，只加血'),
    dict(name='读报', level='full', hp=420, note='同普通；报纸 150 + 本体 270，不模拟暴走'),
    dict(name='铁门', level='full', hp=1370, note='同普通；铁门不减伤，只加血'),
    dict(name='撑杆', level='full', hp=500,
         note='**快速档**（0.66~0.68）跑过来，遇到第一株植物**飞跃**它'
              '（落地在"目标植物 x − 70"，[精 11.2]），之后回落慢速档；'
              '高坚果挡得住（不跳，改成啃）'),
    dict(name='扶梯', level='full', hp=1000,
         note='**快速档**（0.66~0.68）的步行者（用户口径「速度较快的快速僵尸」）；'
              '梯子本身不模拟（不会真的给南瓜架梯）'),
    dict(name='橄榄', level='full', hp=1670, note='快走（0.66~0.68），血厚，被窝瓜/核照吃 1800'),
    dict(name='白眼', level='full', hp=3000,
         note='巨人：受击框 (x−35, 宽70)（正中央就跨格）；每 330cs 砸一次 1800；'
              '**必须打满 3000 才算解除**，没有低血豁免'),
    dict(name='红眼', level='full', hp=6000,
         note='同白眼，血 6000；这两只是"必须拖时间"的根源'),
    dict(name='冰车', level='full', hp=1350,
         note='速度由横坐标定（x≥700 时 0.25，x<400 时 0.10，中间线性）；'
              '碾压判定 + 铺冰道（**车死冰道不消失**）；受击框沿用默认（未标定，'
              '报告另出"每辆车最左到达 x"以便自证）'),
    dict(name='小丑', level='full', hp=500,
         note='盒内时间早/晚两档随机；爆炸按 3×3 结算，记 JOKER 日志；'
              '控丑判定看"本波有没有及时灰烬/冰冻"'),
    dict(name='舞王', level='full', hp=500,
         note='走到 7 列（x≤520）时**滑步**：按「滑步」档 0.79~0.81 后退一格'
              '（⚠️位移量 80px 待核），然后每 8s 召一批伴舞'),
    dict(name='伴舞', level='part', hp=270, note='由舞王召出，按普通僵尸走'),
    dict(name='矿工', level='full', hp=370,
         note='按步行者走（0.23~0.37），**不计入阵线**（视为已脱离阵线）；'
              '钻地/出土/晕眩不模拟'),
    dict(name='跳跳', level='full', hp=500,
         note='**不啃植物**，按「快速」档 0.66~0.68 一路往前'
              '（用户：速度仅比滑步慢一档）；跳跃轨迹不模拟'),
    dict(name='潜水', level='part', hp=270,
         note='只能在 3/4 路（水路）；潜行/浮出不模拟，按普通步行者'),
    dict(name='海豚', level='full', hp=500,
         note='只能在水路，按步行者走（水中 0.23~0.37）；冲锋段 0.89~0.91 不单独模拟；'
              '**不计入阵线**'),
    dict(name='气球', level='part', hp=290,
         note='匀速直走（当作一直在飞的步行者）；三叶草可一键清光（见植物侧）'),
    dict(name='蹦极', level='watch', hp=450,
         note='**只做风险提示**：本波有蹦极却没点冰 → 记 `蹦极风险`；'
              '抓取动作、被伞保护不模拟'),
    dict(name='投篮', level='part', hp=850,
         note='有独立出生点与速度；抛投不模拟（不会真的砸后场）'),
    dict(name='小鬼', level='full', hp=270,
         note='按步行者走（0.23~0.37），会真的啃植物；**不计入阵线**'
              '（巨人丢出的落点机制不模拟）'),
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
    dict(name='香蒲', level='part', note='只算防空（对蹦极/气球的存在感），对地输出忽略'),
    dict(name='双子花', level='full', note='每 2400cs +50 阳光；阳光封顶 9990'),
    dict(name='存冰', level='full', note='= 睡着的寒冰菇：占一格、有 300 血，被咖啡豆唤醒即全场冰冻'),
    dict(name='睡莲', level='part',
         note='占格；**水路基座** —— PE / FE 的水上空地必须先种睡莲才能种别的'
              '（用户 2026-10-22）'),
    dict(name='保护伞', level='watch', note='占格；对蹦极/投篮的保护不模拟，只在风险提示里体现'),
    dict(name='玉米炮', level='full',
         note='**1×2 占格**；开炮：CD 3475cs，释放到爆炸 378cs（陆路 373~376 / 屋顶 359~392），'
              '圆形 R=115 炸 1800，爆炸中心 y = 同行植物 y + 40、x = 准星 x − 7'),
    dict(name='小喷菇', level='part', note='垫材：0 阳光、7.5s 充能；落地后钉住一只僵尸一段时间'),
    dict(name='花盆', level='part',
         note='**屋顶基座**：RE 空地必须先放花盆；同时是第二张垫材（25 阳光、7.5s）'),
    dict(name='南瓜', level='full',
         note='独立 4000 血的一层壳，先扣南瓜再扣植物；补种消耗 125 阳光；'
              '**挂梯子的南瓜（梯子南瓜）会被巨人/车以外的僵尸直接无视**'),
    dict(name='咖啡豆', level='action',
         note='一次性：唤醒**所在格睡着的蘑菇**（不止存冰位）；白天场蘑菇是睡着的'),
    dict(name='毁灭菇', level='action', note='一次性：圆形 R=250 炸 1800，留下弹坑（一段时间不能种）'),
    dict(name='樱桃', level='action', note='一次性：圆形 R=115 炸 1800'),
    dict(name='辣椒', level='action', note='一次性：整行 1800，并烧掉该行冰道'),
    dict(name='窝瓜', level='action', note='一次性：1 格宽 1800，可指定落点（压冰车就是用这个）'),
    dict(name='寒冰菇', level='action',
         note='种下即"睡着"（白天场），被咖啡豆唤醒后全场冰冻 2000cs（含减速）'),
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
         note='吸走金属护具（R=270，对啃食者 320）：铁桶/铁门/橄榄/扶梯 → 只剩本体血'),
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
