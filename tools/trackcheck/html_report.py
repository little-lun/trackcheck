"""
html_report.py —— 把模拟结果做成可看的 HTML 运阵报告

用法：
    python -m tools.trackcheck.html_report            # 四档 × 4 局汇总
    python -m tools.trackcheck.html_report 4          # 指定每档局数
    python -m tools.trackcheck.html_report 6 慢速     # 只跑某一档

输出：tools/trackcheck/out_report.html（自包含，无外部依赖）
"""
import sys
from collections import Counter

sys.path.insert(0, '.')

from tools.trackcheck import config_dianbozhong as C
from tools.trackcheck import run as R
from tools.trackcheck import data as D
from tools.trackcheck import plan as PL

# 垫材 = 消耗品（小喷菇 / 花盆 / 阳光菇 / 胆小菇）—— 不进损失清单、不计磨损
PAD_PLANTS = tuple(D.PAD_PLANT.values())


def _deck_key(entry):
    """选卡条目 → 引擎里的**卡片键**（用于查 card_ready）"""
    e = str(entry)
    if e.startswith('模仿者:'):
        t = e.split(':', 1)[1]
        return {'寒冰菇': '模仿冰', '毁灭菇': '模仿核'}.get(t, '模仿' + t)
    return PL.CARD_KEY.get(e, e)


# 引擎内部的旧动作名 → 植物名（hover 的"用卡"要统一显示成植物名）
_ACTION_ALIAS = {'垫材': '小喷菇', '垫材2': '花盆', '垫材3': '阳光菇',
                 '垫材4': '胆小菇', '核': '毁灭菇', '冰': '寒冰菇'}


def _chill_hint(r):
    """本波"临场用卡"的归因（计划内 vs 救场）—— 用户要"搞清楚为什么用卡\""""
    acts = r.get('actions') or []
    out = {}
    for a in acts:
        if not a.get('ok'):
            continue
        w = a.get('wave')
        nm = _ACTION_ALIAS.get(a['name'], a['name'])
        rec = out.setdefault(w, {})
        e = rec.setdefault(nm, dict(plan=0, rescue=0))
        if a.get('rescue'):
            e['rescue'] += 1
        else:
            e['plan'] += 1
    return out


def _card_label(entry):
    """选卡里的一项 → 显示名（'模仿者:寒冰菇' → '模仿冰'）"""
    e = str(entry)
    if e.startswith('模仿者:'):
        return '模仿' + e.split(':', 1)[1]
    return e

# ★ v0.2.2：这里原来是 PE.电波钟无炮 四档的**实机录像波长**（15.84/12.30/10.24/8.56）。
#   阵型改成用户自己配之后，没有可比的录像了 → 清空，报告里偏差显示「自定义（无参照）」。
VIDEO = {}
CARD_COLOR = {
    '核': '#dc2626', '模仿核': '#f87171',
    '冰': '#2563eb', '模仿冰': '#60a5fa', '存冰': '#93c5fd',
    '樱桃': '#ea580c', '辣椒': '#991b1b',
    '窝瓜': '#65a30d',
    '垫材': '#94a3b8', '垫材2': '#cbd5e1',
    '南瓜': '#d97706',
}
SEV_COLOR = {'WARN': '#f59e0b', 'FATAL': '#dc2626', 'RESCUE': '#0ea5e9',
             'REPAIR': '#10b981', 'NORESCUE': '#be123c', 'INFO': '#94a3b8',
             'JOKER': '#7c3aed', 'REBUILD': '#0891b2'}

# ★★ 2026-10-20 用户要求："除了色块，用社区通用简写字母标记。
#   核弹 = N，樱桃 = A，辣椒 = A'，冰 = I，垫材 = C。"
#   并且"A 和 A' 经常重合害得我没法分辨" —— 所以灰烬泳道**拆成三行**
#   （N / A / A' 各占一行），重叠问题从结构上消灭。
ABBR = {
    '核': 'N', '模仿核': 'N',
    '樱桃': 'A',
    '辣椒': "A'",
    '冰': 'I', '模仿冰': 'I', '存冰': 'I',
    '窝瓜': 'W', '窝瓜压车': 'W',
    '垫材': 'C', '垫材2': 'C',
    '种大喷': 'F', '大喷菇': 'F', '种冰': '·', '种冰2': '·', '种临时冰': '·',
    # ★ 2026-10-22：P（玉米炮）单独一条泳道 —— 炮阵的核心操作必须能一眼数出来
    '玉米炮': 'P',
    # ★ 极速关的 N 换成大蒜（2-9 / 5-9），它也是**结构性动作**，要画出来
    '大蒜': '·',
    # ★★ 2026-10-22：垫材现在是**四张独立的卡**（小喷菇 / 花盆 / 阳光菇 / 胆小菇），
    #   以前只认 '垫材'/'垫材2' 两个内部别名 → 新名字查不到缩写，落到默认泳道（I 道），
    #   画出一个灰色的 '?'。这里补齐，并把默认泳道改到 CW 行。
    '小喷菇': 'C', '花盆': 'C', '阳光菇': 'C', '胆小菇': 'C',
    '垫材3': 'C', '垫材4': 'C',
    # 其它"种植物"类动作：结构维护，画在 CW 行的小点
    '南瓜': '·', '荷叶': '·', '睡莲': '·', '保护伞': '·', '双子花': '·',
    '寒冰菇': 'I', '毁灭菇': 'N', '模仿寒冰菇': 'I', '模仿毁灭菇': 'N',
    '三叶草': '·', '墓碑吞噬者': '·', '地刺': '·', '钢地刺': '·',
    '高坚果': '·', '双向射手': '·', '机枪射手': '·', '火炬树桩': '·',
    '磁力菇': '·', '咖啡豆': '·', '向日葵': '·',
}
ABBR_COLOR = {
    'P': '#7c3aed',
    'N': '#b91c1c', 'A': '#ea580c', "A'": '#7f1d1d',
    'I': '#1d4ed8', 'W': '#4d7c0f', 'C': '#94a3b8', 'F': '#0891b2', '·': '#cbd5e1',
}
ABBR_DESC = {'P': '玉米炮', 'N': '核弹', 'A': '樱桃', "A'": '辣椒', 'I': '冰',
             'W': '窝瓜', 'C': '垫材', 'F': '补大喷'}

# 泳道：(缩写, y_top, height)。None = 波次行
LANES = [
    (None,  4, 22),
    ('P',  28, 14),
    ('N',  43, 13),
    ('A',  57, 13),
    ("A'", 71, 13),
    ('I',  85, 16),
    ('CW', 102, 16),
]
LANE_OF = {'P': 1, 'N': 2, 'A': 3, "A'": 4, 'I': 5, 'W': 6, 'C': 6, 'F': 6, '·': 6}
GRAPH_TOP = 122
GRAPH_H = 74
SUN_TOP = 202
SUN_H = 56
TL_H = 270

# ★★ 2026-10-20 用户要求：偏离设计要**分级**，而不是一律标红。
#   「评定这是：能补的、在人类游戏手感和游戏直觉内可以避免的、致命的或者其它更多档」
#   例：变速 w19 控丑缺失 = 人类手感内可避免；边路 5 列大喷死 = 同时属"能补"。
LEVELS = [
    ('L0', '致命', '#b91c1c',
     '控丑空窗 / 冰慢一拍 / 蹦极无冰 / CORE 被毁，且**人类也挤不出资源来阻止**',
     '后果不可逆（CORE 死 / 后场被偷光），没有任何补救'),
    ('L1', '人类手感内可避免', '#ea580c',
     '同样是**致命事件**，但造成它的原因人类能设法阻止'
     '（只差一个冰 / 卡差两秒 / 换个顺序就能挤出来）',
     '属"手滑"不属"设计错"：练临场补一手即可'),
    ('L2', '能补', '#ca8a04',
     '不在设计内的损失（非 CORE 植物死 / 被碾），但阵有冗余、阳光能补回',
     '合理运阵下不该发生；发生了就付阳光'),
    ('L3', '正常磨损', '#0f766e',
     '必然发生、且设计已预留补偿（南瓜磨损 —— 选卡带南瓜就是为补它）',
     '不用管，算进日常开销'),
    ('L4', '模型伪影', '#64748b',
     '波长偏差 ≥ 10% 引起的现象',
     '不是打法问题，需重新标定'),
]
LEVEL_RANK = {k: i for i, (k, *_) in enumerate(LEVELS)}
LEVEL_NAME = {k: v for k, v, *_ in LEVELS}
LEVEL_COLOR = {k: c for k, v, c, *_ in LEVELS}


def svg_for(r, W=1180):
    """
    一局的轨道时间轴（SVG）。

    ★ 2026-10-20 改造：
      · 灰烬泳道拆成 **N / A / A′ 三行** —— 用户说"A 和 A′ 经常重合害得我分不清"，
        分行之后从结构上不可能重合。
      · 每个色块都带**社区通用简写字母**（N/A/A′/I/W/C），竖排写在条上，
        颜色只是辅助，字母才是主标识。
      · 每一波覆盖一条透明热区（class=wvhot），hover 出明细窗口。
    """
    t_end = max(1.0, r['t_end'] / 100.0)
    H = TL_H
    pad_l = 58
    plot_w = W - pad_l - 8

    def X(t_cs):
        return pad_l + (t_cs / 100.0) / t_end * plot_w

    out = []
    add = out.append
    add('<svg viewBox="0 0 %d %d" class="tl" xmlns="http://www.w3.org/2000/svg">' % (W, H))

    # 泳道背景 + 标签（左边写缩写，右边写中文，便于对照）
    for i, (ab, y, h) in enumerate(LANES):
        add('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
            % (pad_l, y, plot_w, h, '#f8fafc' if i % 2 == 0 else '#ffffff'))
        if ab is None:
            add('<text x="%d" y="%d" class="lk">%s</text>' % (pad_l - 6, y + h // 2 + 3, '波次'))
        else:
            if ab == 'CW':
                lab, txt = 'C/W', '垫/窝'
            else:
                lab, txt = ab, ABBR_DESC[ab]
            add('<text x="%d" y="%d" class="lk ab-l">%s</text>'
                % (pad_l - 6, y + h // 2 + 3, lab))
            pass

    # 波次：竖线 + 编号
    for wv in r['waves']:
        x = X(wv['t'])
        is_flag = wv['w'] % 10 == 0
        add('<line x1="%.1f" y1="4" x2="%.1f" y2="%d" stroke="%s" stroke-width="%s" opacity="0.5"/>'
            % (x, x, GRAPH_TOP + GRAPH_H, '#dc2626' if is_flag else '#94a3b8',
               '1.4' if is_flag else '0.8'))
        add('<text x="%.1f" y="16" class="wl%s">%d</text>'
            % (x, ' flag' if is_flag else '', wv['w']))

    # 操作：色块 + 字母
    #   ★ 同一泳道、同一时刻（±4px）的同类操作**只标一次字母** ——
    #     否则垫材这种一波下两张的会画出两个叠在一起的 C，反而看不清。
    labelled = set()
    for a in r.get('actions', []):
        if not a.get('ok'):
            continue
        nm = a['name']
        ab = ABBR.get(nm, '·')
        lane = LANE_OF.get(ab, 6)          # 认不出来的动作放 CW 行，别再掉进 I 道
        _, y, hgt = LANES[lane]
        x = X(a['t'])
        col = ABBR_COLOR.get(ab, '#64748b')
        if ab == '·':
            # 维护性动作（补存冰 / 补大蒜）：只画一个小点，不占字母空间（不算轨迹）
            # 大蒜用棕色、半径略大，跟补存冰区分开
            r0 = 2.2 if nm == '大蒜' else 1.3
            add('<circle cx="%.1f" cy="%d" r="%.1f" fill="%s"/>'
                % (x, y + hgt - 3, r0, '#a16207' if nm == '大蒜' else col))
            continue
        add('<rect x="%.1f" y="%d" width="3.6" height="%d" fill="%s" rx="1"/>'
            % (x, y + 2, hgt - 4, col))
        slot = (lane, round(x / 9.0))
        if slot in labelled:
            continue
        labelled.add(slot)
        # 字母**横排**放在色块右侧 —— 竖排读起来太费劲，用户要的是"一眼认出来"
        add('<text class="ab" x="%.1f" y="%d" fill="%s">%s</text>'
            % (x + 4.2, y + hgt // 2 + 3, col, ab))

    # 事件
    for e in r.get('log', []):
        sev = e['sev']
        if sev not in ('WARN', 'FATAL', 'NORESCUE'):
            continue
        x = X(e['t'])
        col = SEV_COLOR.get(sev, '#64748b')
        add('<circle cx="%.1f" cy="%d" r="%.1f" fill="%s"/>'
            % (x, GRAPH_TOP - 4, 3.4 if sev == 'FATAL' else 2.4, col))

    # 僵尸数 / 减速数 折线
    ser = r.get('series', [])
    if ser:
        maxz = max(1, max(p['alive'] for p in ser))

        def pts(key, base, h):
            return ' '.join('%.1f,%.1f' % (X(p['t']), base + h - p[key] / maxz * h) for p in ser)
        add('<polyline fill="none" stroke="#0ea5e9" stroke-width="1.2" opacity="0.85" points="%s"/>'
            % pts('slowed', GRAPH_TOP, GRAPH_H))
        add('<polyline fill="none" stroke="#1e293b" stroke-width="1.4" points="%s"/>'
            % pts('alive', GRAPH_TOP, GRAPH_H))
        add('<text x="%d" y="%d" class="lk">僵尸/减速</text>' % (pad_l - 6, GRAPH_TOP + 10))
        add('<text x="%d" y="%d" class="lk2">峰值 %d 只</text>' % (W - 6, GRAPH_TOP + 10, maxz))

    # 阳光曲线
    if ser:
        maxs = max(1, max(p['sun'] for p in ser))
        mins = min(p['sun'] for p in ser)
        rng = max(1, maxs - mins)
        p = ' '.join('%.1f,%.1f' % (X(q['t']), SUN_TOP + SUN_H - (q['sun'] - mins) / rng * SUN_H)
                     for q in ser)
        add('<rect x="%d" y="%d" width="%d" height="%d" fill="#f8fafc"/>' % (pad_l, SUN_TOP, plot_w, SUN_H))
        add('<polyline fill="none" stroke="#d97706" stroke-width="1.4" points="%s"/>' % p)
        add('<text x="%d" y="%d" class="lk">阳光</text>' % (pad_l - 6, SUN_TOP + SUN_H // 2))
        add('<text x="%d" y="%d" class="lk2">%d ~ %d</text>' % (W - 6, SUN_TOP + SUN_H // 2, mins, maxs))

    # 时间刻度
    step = 20 if t_end < 500 else 50
    tt = 0
    while tt <= t_end:
        x = X(tt * 100)
        add('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#e2e8f0" stroke-width="0.6"/>'
            % (x, GRAPH_TOP, x, SUN_TOP + SUN_H))
        add('<text x="%.1f" y="%d" class="tx">%ds</text>' % (x, H - 3, tt))
        tt += step

    # ---- hover 热区（最后画，盖在最上层）
    wv = r['waves']
    for k, cur in enumerate(wv):
        t0 = cur['t']
        t1 = wv[k + 1]['t'] if k + 1 < len(wv) else r['t_end']
        x0, x1 = X(t0), X(t1)
        add('<rect class="wvhot" data-w="%d" x="%.1f" y="0" width="%.1f" height="%d" '
            'fill="#000" fill-opacity="0" style="cursor:crosshair"/>'
            % (cur['w'], x0, max(2.0, x1 - x0), H))

    add('</svg>')
    return '\n'.join(out)


def _md(t):
    """只把 **...** 变成 <b>，别的一概不解析（模板里本来就混着 HTML）"""
    import re as _re
    return _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', str(t))


CARD_ABBR = {'核': 'N', '模仿核': 'N', '冰': 'I', '模仿冰': 'I',
             '樱桃': 'A', '辣椒': "A'", '窝瓜': 'W', '垫材': 'C', '垫材2': 'C',
             '咖啡豆': '咖', '大喷菇': '喷'}
PLANT_SHORT = {'忧郁菇': '曾', '冰瓜': '瓜', '大喷菇': '喷', '保护伞': '伞',
               '双子花': '花', '存冰': '冰', '香蒲': '猫', '荷叶': '叶'}
# ★★ 2026-10-20 用户："卡槽显示具体一点……南瓜、曾哥套件（荷叶、大喷、曾哥）、咖啡豆
#   等等，也写进卡槽栏，但是不用简写了，使用社区通用名即可。"
#   所以卡槽栏按**该档真实选卡**逐张列 —— 有社区简记的用简记（N / A / A′ / I / W / C / C′），
#   没有简记的直接写通用名（南瓜 / 荷叶 / 大喷 / 曾哥 / 咖啡豆）。
#   顺序 = 游戏里卡槽从左到右。
DECK = {
    '慢速': [('冰', 'I'), ('模仿冰', 'I′'), ('核', 'N'), ('樱桃', 'A'), ('辣椒', "A'"),
             ('窝瓜', 'W'), ('垫材', 'C'), ('垫材2', "C'"), ('南瓜', '南瓜'),
             ('咖啡豆', '咖啡豆')],
    '快速': [('冰', 'I'), ('模仿冰', 'I′'), ('核', 'N'), ('樱桃', 'A'), ('辣椒', "A'"),
             ('南瓜', '南瓜'), ('荷叶', '荷叶'), ('大喷菇', '大喷'), ('忧郁菇', '曾哥'),
             ('咖啡豆', '咖啡豆')],
    # ★ 2026-10-20 用户："极速关的选卡没有 I（复制），带了咖啡豆；
    #   另外极速出怪没有投篮车和冰车，把 N 换成大蒜，种植并维护 2-9 / 5-9 大蒜。"
    '极速': [('冰', 'I'), ('大蒜', '大蒜'), ('樱桃', 'A'), ('辣椒', "A'"),
             ('南瓜', '南瓜'), ('南瓜2', '南瓜′'), ('咖啡豆', '咖啡豆'),
             ('荷叶', '荷叶'), ('大喷菇', '大喷'), ('忧郁菇', '曾哥')],
}
DECK['变速'] = DECK['慢速']
# ★ 2026-10-20：**中速**是 app.py 新加的节奏（只出白眼、不出红眼），
#   阵解照抄慢速（拖时间 + 垫材 + w10 窝瓜压车），只是灰烬更宽裕。
#   卡槽显示也用慢速那 10 张。
DECK['中速'] = DECK['慢速']


def deck_for(tier, kinds=None):
    """
    该档**真实**选卡。

    ★ 用户 2026-10-20（第 14 轮）："在有冰车或投篮车的极速关不应该带大蒜" ——
      车会把大蒜连格子一起碾掉，所以极速关只有**没有车**时才带大蒜；
      有车时卡槽里就没有这张（也不把核顶回去：极速阵解本来不带核）。
      抬丑抗靠 2-7 / 5-7 的大喷，那是卡槽里已有的「大喷」。
    """
    d = list(DECK.get(tier) or DECK.get('慢速') or [])
    if tier == '极速' and kinds and ({'冰车', '投篮'} & set(kinds)):
        d = [x for x in d if x[0] != '大蒜']
    return d


CARD_ORDER = ('核', '冰', '模仿冰', '樱桃', '辣椒', '窝瓜', '垫材', '垫材2')


def hover_json(r):
    """
    每一波的 hover 明细（序列化成 JSON 放进页面，前端 JS 负责弹窗）。

    内容按用户点名的清单：阳光 / 存冰 / 各卡槽 CD / 本波计划操作
    （临场减压冰、垫材**不算**计划内，单独列"临场"）/ 僵尸推进阵线 / 场上植物。
    """
    snap = r.get('wave_snap', {}) or {}
    ctrl = r.get('end_state', {}).get('wave_ctrl', {}) or {}
    waves = r['waves']

    # ★ 2026-10-20 用户："如果有 L0 / L1 / L2 的事件发生，小窗口中写出来"
    #   L3（设计内预算）和 L4（模型问题）不进小窗 —— 它们在清单里看就够了。
    ev_by_w = {}
    for it in classify(r):
        if it['lv'] not in ('L0', 'L1', 'L2'):
            continue
        for w in it.get('ws') or []:
            ev_by_w.setdefault(w, []).append(it)

    out = {}
    used_by_w = _chill_hint(r)
    # ★ 2026-10-22：阵上到底有没有存冰 —— 没有就整段不显示，
    #   有的话分母也用**阵图里的实际存冰位数**（不再是写死的 4）。
    ice_cap = (r.get('end_state') or {}).get('ice_cap')
    if ice_cap is None:
        ice_cap = (r.get('end_state') or {}).get('ice_stock_perm', 0)
    for k, wv in enumerate(waves):
        w = wv['w']
        t0 = wv['t']
        t1 = waves[k + 1]['t'] if k + 1 < len(waves) else r['t_end']
        sn = snap.get(str(w), {}) or {}
        v = ctrl.get(str(w), {}) or {}

        plan = [CARD_ABBR.get(x, x) for x in sn.get('plan', [])]
        extra = [CARD_ABBR.get(x, x) for x in sn.get('extra', [])]

        # ★★ 2026-10-22 用户：「樱桃当时并不是用于灰烬控丑而是救场，搞清楚为什么用卡」。
        #   → 控丑判定只看**轨道计划内**的灰烬/冰；救场层临时用的卡不算控丑手段。
        ash_plan = [a for a in (sn.get('plan') or ())
                    if a in ('核', '模仿核', '樱桃', '辣椒')]
        ice_plan = [a for a in (sn.get('plan') or ())
                    if a in ('冰', '模仿冰', '寒冰菇', '模仿寒冰菇')]
        if ash_plan:
            how = '灰烬控丑（%s）' % '＋'.join(CARD_ABBR.get(a, a) for a in ash_plan)
            how_c = '#059669'
        elif ice_plan:
            how = '计划点冰控丑'
            how_c = '#1d4ed8'
        elif not v.get('n_joker'):
            how, how_c = '本波无小丑', '#94a3b8'
        elif r.get('_tier', '').startswith('极速'):
            how, how_c = '策略性放弃（极速关不点火）', '#94a3b8'
        else:
            how, how_c = '无控丑操作（小丑靠 IO / 溅射处理）', '#94a3b8'

        # 卡槽：**有阵解就用阵解的真实选卡**（没有才退回按档位猜的旧表）
        cards = sn.get('cards', {}) or {}
        tier0 = r.get('_tier', '').split(' / ')[0]
        deck_plan = r.get('_deck') or []
        if deck_plan:
            deck = [(_deck_key(c), _card_label(c)) for c in deck_plan]
        else:
            deck = deck_for(tier0, r.get('_kinds'))
        cells = []
        for k2, lab in deck:
            # ★ 南瓜（复制）在模型里与南瓜共用同一张卡的 CD —— 不编一个假的独立 CD，
            #   直接显示同一个值，并在脚注里写明"共用模型"
            v2 = cards.get(k2 if k2 in cards else k2.rstrip('2'))
            if k2 == '南瓜2' and v2 is not None:
                lab = '南瓜′'
            if v2 is None:
                # 对局中不重建的卡（荷叶 / 曾哥）和未建模 CD 的卡（咖啡豆）
                cells.append('<span class="cdx" style="color:#64748b">%s —</span>' % lab)
            elif v2 > 0:
                cells.append('<span class="cdx" style="color:#f59e0b">%s %.1fs</span>'
                             % (lab, v2 / 100.0))
            else:
                cells.append('<span class="cdx" style="color:#4ade80">%s 好</span>' % lab)
        cd_html = ''.join(cells)

        # ★ 2026-10-20 用户："阵线显示参差不齐，有的显示水路有的没显示，统一都显示"
        #   → 固定 6 路；这一波没有僵尸进场的路写"无"。
        front = sn.get('front', {}) or {}
        fr = []
        for rr in ('1', '2', '3', '4', '5', '6'):
            col = front.get(rr)
            water = ' class="water"' if rr in ('3', '4') else ''
            if col is None:
                fr.append('<span%s style="color:#64748b">%s路 无</span>' % (water, rr))
            else:
                cls = '#f87171' if col < 7 else ('#fbbf24' if col < 9 else '#64748b')
                fr.append('<span%s style="color:%s">%s路 <b>%.1f</b> 列</span>'
                          % (water, cls, rr, col))
        fr_html = '　'.join(fr)

        pc = sn.get('plants', {}) or {}
        pl = ' '.join('%s%d' % (PLANT_SHORT.get(p2, p2), n2)
                      for p2, n2 in sorted(pc.items(), key=lambda x: -x[1]))

        role = v.get('role', '')
        flag = ' 🚩' if w % 10 == 0 else ''
        head = ('<h4>w%d%s <span style="font-weight:400;color:#94a3b8">'
                '%s ｜ %.1fs → %.1fs（%.1fs）</span></h4>'
                % (w, flag, role, t0 / 100.0, t1 / 100.0, (t1 - t0) / 100.0))
        body = ['<div><span class="k2">控丑</span> '
                '<b style="color:%s">%s</b></div>' % (how_c, how),
                '<div><span class="k2">计划</span> %s</div>'
                % (' '.join('<b>%s</b>' % x for x in plan) if plan else '—')]
        # ★ 2026-10-22 用户：「搞清楚为什么用卡」—— 逐张列出本波真的用掉的卡，
        #   并标出它是**计划内**还是**救场层**临时用的。
        used = used_by_w.get(w) or {}
        if used:
            seg = []
            for nm2, cnt in sorted(used.items(), key=lambda x: -x[1]['plan'] - x[1]['rescue']):
                why = []
                if cnt['plan']:
                    why.append('计划 ×%d' % cnt['plan'])
                if cnt['rescue']:
                    why.append('<span style="color:#0ea5e9">救场 ×%d</span>'
                               % cnt['rescue'])
                seg.append('<b>%s</b><span class="k2">（%s）</span>'
                           % (PLANT_SHORT.get(nm2, nm2), ' · '.join(why)))
            body.append('<div><span class="k2">用卡</span> %s</div>' % '　'.join(seg))
        if extra:
            body.append('<div><span class="k2">机会性</span> '
                        '<span style="color:#cbd5e1">%s</span>'
                        '<span class="k2">（自动选址 / 不入轨迹，明细见上面的「用卡」）</span></div>'
                        % ' '.join(extra))
        evs = ev_by_w.get(w) or []
        if evs:
            body.append('<div class="sep"></div>')
            for it in evs:
                body.append('<div>%s　<b>%s</b></div>'
                            % (level_badge(it['lv']), _md(it['what'])))
        body += ['<div class="sep"></div>',
                 '<div><span class="k2">本波</span> %d 只 ｜ 小丑 %d ｜ 冰车 %d ｜ 总血 %.0fk</div>'
                 % (sn.get('n', 0), sn.get('n_joker', 0), sn.get('n_car', 0),
                    sn.get('total_hp', 0) / 1000.0),
                 '<div><span class="k2">阳光</span> %s → %s%s</div>'
                 % (sn.get('sun', '—'), sn.get('sun_end', sn.get('sun', '—')),
                    (' ｜ <span class="k2">存冰</span> %s → %s / %d'
                     % (sn.get('ice', '—'), sn.get('ice_end', sn.get('ice', '—')),
                        ice_cap)) if ice_cap else ''),
                 '<div><span class="k2">卡槽</span> %s</div>'
                 '<div class="k2" style="font-size:10px">'
                 '— = 这局没有启用这张卡（建阵固定 / 未建模它的补种）；'
                 '南瓜′ 与南瓜共用同一份 CD 模型</div>'
                 % (cd_html or '—'),
                 '<div class="sep"></div>',
                 '<div><span class="k2">阵线</span> %s</div>'
                 '<div class="k2" style="font-size:10px">'
                 '整波推到的<strong>最深处</strong>（列数越小越靠前）；'
                 '海豚 / 矿工 / 小鬼 不计入阵线</div>' % fr_html,
                 '<div><span class="k2">植物</span> %s ｜ 南瓜 <b>%d</b>/24</div>'
                 % (pl or '—', sn.get('pumpkin', 0))]
        out[str(w)] = {'html': head + ''.join(body)}
    return out


def _squeeze(r, w):
    """
    这一波玩家还能不能"挤"出一手控制？

    用户 2026-10-20 的分级原则：
      「一个事件可以致命（L0），但是造成这个事件具备一定的原因、
        且**人类能设法阻止这个原因**就算 L1；即便在最优假设下人类
        也绝不可能阻止原因，则记作 L0。」

    所以这里要回答的是"原因能不能被阻止"，而不是"结果严重不严重"。
    判据（按人类实际会做的事排优先级）：

      ① 手上还有存冰 → 直接点，能阻止
      ② 某张卡 3s 内就好 → 等两秒、把上一波的操作挪一下，能挤出来
      ③ 某张卡当时是"好"的（=0）却没被排上 → 纯粹忘了，能阻止
      ④ 存冰 0 且冰 / 樱桃 / 辣椒 / 核 全在 CD 深处 → 人力不可及
    """
    sn = (r.get('wave_snap') or {}).get(str(w)) or {}
    ice = sn.get('ice', 0)
    if ice and ice >= 1:
        return True, '波首还有 %d 个存冰没点' % ice

    cards = sn.get('cards', {}) or {}
    ready = []
    near = []
    for k in ('冰', '模仿冰', '樱桃', '辣椒', '核', '模仿核'):
        v = cards.get(k)
        if v is None:
            continue
        lab = CARD_ABBR.get(k, k)
        if v <= 0:
            ready.append(lab)
        elif v <= 300:
            near.append('%s %.1fs' % (lab, v / 100.0))
    if ready:
        return True, '%s 当时就是好的（只是没排上）' % '、'.join(ready)
    if near:
        return True, '%s 后就转好，等一下 / 挪一下顺序就能挤出来' % '、'.join(near)

    worst = sorted(((cards.get(k, 0), CARD_ABBR.get(k, k))
                    for k in ('冰', '樱桃', '辣椒', '核')), reverse=True)
    return False, '存冰 0，且 %s 分别在 %.1fs / %.1fs / %.1fs / %.1fs 后' % (
        '、'.join(x[1] for x in worst), worst[0][0] / 100.0, worst[1][0] / 100.0,
        worst[2][0] / 100.0, worst[3][0] / 100.0)


def _judge_control(r, gaps):
    """
    控丑空窗 / 蹦极无冰这类**事件本身是 L0**，看原因能否被阻止决定降不降级。
    返回 (level, 说明文字)
    """
    blocked = []
    free = []
    for g in gaps:
        can, why = _squeeze(r, g)
        (free if can else blocked).append((g, why))
    if blocked:
        g, why = blocked[0]
        return 'L0', ('w%d 这一波**怎么都挤不出来**（%s）—— 即便最优操作也做不到阻止，'
                      '所以不能降级' % (g, why))
    g, why = free[0]
    return 'L1', ('事件本身致命，但原因可阻止：%s。人类会为这一个冰临时改操作'
                  '（挪上一波的冰 / 等两秒 / 换点灰烬的顺序）' % why)


def classify(r, dev=None):
    """
    把"脱离设计的情况"分级（用户 2026-10-20 定稿的口径）。

    ★ 核心不是"严重度排序"，而是**归因**：

        L0  事件致命，且**人类也阻止不了原因**（最优操作下仍会发生）
        L1  事件同样致命，但**原因人类能设法阻止**（少一个冰、卡差两秒、换顺序）
        L2  不在设计内的损失，但阵有冗余、阳光能补（非 CORE 植物死 / 被碾）
        L3  必然发生且设计已预留补偿（南瓜磨损 —— 选卡专门带南瓜来补）
        L4  模型自己的偏差（波长），与打法无关

    特别注意两条容易搞反的：
      · **边路 5 列大喷死 = L2**，不是 L3 —— 阵里确实有冗余，但"合理运阵下绝对不会死"，
        它不在设计中，只是能补。
      · **南瓜磨损 = L3** —— 它必然发生，而且设计者就是靠选卡带南瓜（极速关甚至
        南瓜 + 复制南瓜）来吸收这份损耗，所以它是设计内的预算，不是"偏离"。
    """
    es = r.get('end_state', {}) or {}
    tier = r.get('_tier', '').split(' / ')[0]
    seen = {}
    out = []

    def add(lv, what, why, fix, ws=None):
        key = (lv, what)
        if key in seen:
            return
        seen[key] = 1
        out.append(dict(lv=lv, what=what, why=why, fix=fix, ws=list(ws or [])))

    f = r.get('fail')
    # ★★ 2026-10-22：最常见的误配置 —— **阵解里排了 P，但阵型里根本没画玉米炮**。
    #   这时所有 P 都会报"场上没有玉米炮"，最后以"进家：橄榄 / 第 N 路"收尾，
    #   看起来像"模型算错了"，其实是阵型/阵解没对上。必须顶到第一条说清楚。
    n_nocob = sum(1 for b in (r.get('broken') or [])
                  if '场上没有玉米炮' in (b.get('why') or ''))
    if n_nocob:
        add('L0', '阵型里没有玉米炮，但阵解里排了 %d 次开炮（P）' % n_nocob,
            '<b>这不是模拟的锅</b>：炮全部打不出去，僵尸一路走到进家。'
            '先到「① 阵容布置」把 8 门炮画上去，或者把这一组出怪绑到有炮的那套阵型上。'
            '（阵解里的 P 只看<b>场上有没有炮</b>，与卡槽无关）',
            '补阵型，或换阵解', ws=[])
    if f:
        why = f['why'] or ''
        head = '僵尸进家' if '进家' in why else '崩阵'
        add('L0', '%s：%s' % (head, why),
            'w%d · %.1fs —— %s' % (f['wave'], f['t'] / 100.0,
                                   '一路走到房子，整局作废' if '进家' in why
                                   else 'CORE 已经没了，不可逆'),
            f.get('detail') or '必须改轨道', ws=[f['wave']])

    core = ('忧郁菇', '冰瓜', '香蒲', '玉米炮')
    for e in r.get('log', []):
        if e['sev'] != 'WARN':
            continue
        nm, row = e['what'], e.get('row')
        if any(k in nm for k in core):
            add('L0', nm, 'CORE 植物被毁 —— 不可逆', '必须改轨道', ws=[e['wave']])
        elif row in (1, 6) and '大喷' in nm:
            add('L2', nm,
                '边路 5 列大喷 —— <b>不在设计中</b>：这一株是 IO 冗余，'
                '合理运阵下绝对不会死（红眼走到那儿之前就该被窝瓜/垫材吃掉）',
                '能补：75 阳光种回。它不属"正常磨损"', ws=[e['wave']])
        else:
            add('L2', nm, '非 CORE 耗材被啃 —— 不在设计中，但阵有冗余', '阳光可补',
                ws=[e['wave']])

    # ---- 控丑空窗（事件级 L0，看原因能不能被阻止）
    gap_rows = {}
    for row in (2, 5):
        lv, gaps = _control_level(r, row)
        if lv == '有限':
            for g in gaps:
                gap_rows.setdefault(g, []).append(row)
    if gap_rows:
        ws = sorted(gap_rows)
        tag = '、'.join('w%d（%s 路）' % (g, '、'.join(map(str, gap_rows[g]))) for g in ws[:6])
        lv, why = _judge_control(r, ws)
        add(lv, '控丑空窗：%s' % tag,
            why + '　<b>后果</b>：小丑在这一波开盒可能炸到岸路 6 列眼曾 → 直接死 CORE',
            '不用改轨道' if lv == 'L1' else '必须重新排这一波的操作', ws=ws)

    # ---- 蹦极无冰（同样：事件级 L0）
    # ★ 2026-10-22 用户：**只在"真的有植物暴露"时才谈防蹦极**。
    #   炮不会被蹦极锁定；伞覆盖的不用管 —— 所以候选为空就不该报这一条
    #   （经典八炮除炮外全在伞下，根本不欠这方面操作）。
    for b in (es.get('bungee_detail') or []):
        if not (b.get('targets') or []):
            continue
        if b.get('saved_ice') and not b.get('stolen'):
            continue
        lv, why = _judge_control(r, [b['wave']])
        need_ice = [t for t in (b.get('targets') or []) if t.get('need') == 'ice']
        add(lv, 'w%d 蹦极没处理干净' % b['wave'],
            why + ('　<b>暴露目标</b>：%s（冰杀定式，必须点冰）'
                   % '、'.join('%d-%d %s' % (t['rc'][0], t['rc'][1], t['plant'])
                              for t in need_ice)
                   if need_ice else
                   '　<b>暴露目标</b>：%s（伞与冰杀定式都没覆盖 → 用炮炸）'
                   % '、'.join('%d-%d %s' % (t['rc'][0], t['rc'][1], t['plant'])
                              for t in (b.get('targets') or []))),
            '看到蹦极先点冰 / 留一对炮' if lv == 'L1' else '这一波必须腾出冰或炮',
            ws=[b['wave']])

    # ★ 2026-10-22 用户：「垫材还是出现了，不要将其死亡视作 L2 磨损」
    #   → 垫材（小喷菇 / 花盆 / 阳光菇 / 胆小菇）是消耗品：
    #     它的"下不了 / 被啃 / 被碾"一律不算磨损，不进这份清单。
    for b in r.get('broken', []):
        if b['what'] in ('种冰', '种冰2', '种临时冰') or b['what'] in PAD_PLANTS:
            continue
        add('L2', '断轨：%s' % b['what'], 'w%d · %s' % (b['wave'], b['why']),
            '卡 CD 撞车；下一波补，不致命', ws=[b['wave']])

    for c in r.get('crush', []):
        pl = c['plant'] or '南瓜'
        if pl in PAD_PLANTS:
            continue                       # 垫材被碾 = 用完一张，不算损失
        if any(k in pl for k in core):
            add('L0', '冰车碾掉 %d-%d %s' % (c['row'], c['col'], pl),
                'CORE 被碾 —— 不可逆', '必须改轨道', ws=[c.get('wave')])
        else:
            add('L2', '冰车碾掉 %d-%d %s' % (c['row'], c['col'], pl),
                '非 CORE / 临时施工位（%s 档无救场），不在设计中' % tier, '重建即可',
                ws=[c.get('wave')])

    # ---- 南瓜：这是**设计内的预算**，不是偏离
    rep = es.get('repairs', 0)
    plost = r.get('pumpkin_lost', 0)
    if rep or plost:
        add('L3', '南瓜磨损：补了 %d 次%s' % (rep, ('，掉了 %d 个' % plost) if plost else ''),
            '<b>必然发生</b>：红眼锤、小丑炸、冰车蹭都会掉南瓜。'
            '设计者就是靠选卡带南瓜（极速关甚至南瓜＋复制南瓜）来吸收这份损耗',
            '不用管，算进日常开销')

    # ★ 2026-10-22 用户：「对于没有存冰的阵不要进行存冰量警告，不过有存冰的阵也一定要警告」
    #   → 判据是**阵型里到底有没有寒冰菇**，不是"引擎默认的存冰位有没有填满"。
    ice_cap = es.get('ice_cap')
    if ice_cap is None:                      # 老报告没这个字段 → 退回旧行为
        ice_cap = es.get('ice_stock_perm', 0)
    if ice_cap and es.get('ice_stock_perm', 0) == 0 and tier != '极速':
        add('L2', '结束存冰 0（阵上共 %d 个存冰位）' % ice_cap,
            '下一个循环开局要先现补冰',
            '选卡带满存冰 / 收尾少点一次')

    if dev is not None and abs(dev) >= 10:
        add('L4', '波长偏差 %+.0f%%' % dev,
            '模型清血速度与实战不一致（刷怪 / 灰烬对数）',
            '重新标定，与打法无关')

    out.sort(key=lambda x: LEVEL_RANK[x['lv']])
    return out


def level_badge(lv):
    return ('<span class="lv" style="background:%s">%s %s</span>'
            % (LEVEL_COLOR[lv], lv, LEVEL_NAME[lv]))


def divergence_html(r, dev=None):
    items = classify(r, dev)
    if not items:
        return '<div class="note ok">零偏离：整局没有出现任何脱离设计的现象。</div>'
    rows = ''.join(
        '<tr><td>%s</td><td>%s</td><td class="dim">%s</td><td class="dim">%s</td></tr>'
        % (level_badge(it['lv']), _md(it['what']), _md(it['why']), _md(it['fix']))
        for it in items)
    top = items[0]['lv']
    return ('\n  <table class="mini wide divg">\n'
            '    <tr><th>等级</th><th>现象</th><th>判据 / 归因</th><th>怎么处理</th></tr>\n'
            '    ' + rows + '\n  </table>\n'
            '  <div class="dim small">最高等级：' + level_badge(top) +
            '　（L0 即使最优操作也阻止不了 → 必须改轨道；L1 原因可被人力阻止 → 练手感；'
            'L2 不在设计内但能补；L3 设计内的预算；L4 模型问题）</div>\n')


def garlic_html(r):
    """
    大蒜台账 —— **只有阵解里真的用了大蒜**才出现，内容全部按实际数据生成。

    ★ 2026-10-20 更正：大蒜**不能跨水陆** —— 岸路的大蒜只能把僵尸赶去相邻的边路
      （3/4 路是水池，陆路僵尸下不去）。它不是"分流"，而是**单向驱赶**。
    """
    g = r.get('garlic') or {}
    n = g.get('n', 0)
    if not n:
        return ''
    # 全量聚合（引擎已算好）；老数据没有 by_frm 就退回按明细统计
    frm = {int(k): v for k, v in (g.get('by_frm') or {}).items() if v}
    to = {int(k): v for k, v in (g.get('by_to') or {}).items() if v}
    if not frm:
        for x in g.get('detail', []):
            frm[x['frm']] = frm.get(x['frm'], 0) + 1
            to[x['to']] = to.get(x['to'], 0) + 1

    def bar(d):
        return '　'.join('%d路 %d' % (k, v) for k, v in sorted(d.items())) or '—'

    return '''
  <table class="mini">
    <tr><th>大蒜台账（按阵解里实际种下的位置）</th><th>数值</th><th>说明</th></tr>
    <tr><td>换行次数</td><td class="b">%d</td><td>僵尸被大蒜赶走的次数（不跨水陆，去向唯一）</td></tr>
    <tr><td>啃碎次数</td><td>%d</td><td>大蒜 400 血、一口 100 → 每 4 口碎一次</td></tr>
    <tr><td>来源</td><td colspan="2" style="text-align:left">%s</td></tr>
    <tr><td>去向</td><td colspan="2" style="text-align:left">%s</td></tr>
    <tr><td class="b">压力转移</td><td colspan="2" style="text-align:left" class="dim">岸路的压力整股灌进相邻边路 —— 边路吃不吃得下看下面植物状态</td></tr>
  </table>''' % (n, g.get('broke', 0), bar(frm), bar(to))


def fog_html(r):
    """结构位补种台账 —— **只有阵解里真的补种过结构位**才出现，内容按实际数据生成"""
    f = r.get('fog') or {}
    n = f.get('n', 0)
    if not n:
        return ''
    return '''
  <table class="mini">
    <tr><th>结构位补种台账</th><th>数值</th><th>说明</th></tr>
    <tr><td>补种次数</td><td class="b">%d</td><td>按阵解里排的补种动作统计</td></tr>
    <tr><td>被车碾</td><td class="%s">%d</td><td>被压就补，不额外操作</td></tr>
  </table>''' % (n, 'bad' if f.get('crushed') else '', f.get('crushed', 0))


def wave_table(r):
    """20 波的轨道执行表 —— 直接回答"每一波有没有早冰或灰烬控丑"""
    tier = r.get('_tier', '').split(' / ')[0]
    ctrl = r.get('end_state', {}).get('wave_ctrl', {})
    jb = {b['wave']: b for b in r.get('end_state', {}).get('joker', {}).get('detail', [])}
    rows = []
    for w in range(1, 21):
        v = ctrl.get(str(w))
        if not v:
            continue
        acts = [a for a in v['acts'] if a not in ('种冰', '种冰2', '种临时冰')]
        # 用**实际发生**的动作（track 排的 + 救急/维护补发的），与时间轴一致
        ice = v.get('ice_act', v['ice'])
        ash = v.get('ash_act', v['ash'])
        if ash is not None:
            how, cls = '灰烬控丑（%s）' % '、'.join(a for a in acts if a in
                                           ('核', '模仿核', '樱桃', '辣椒')), 'ok'
        elif ice is not None:
            how, cls = '早冰控丑（%+.1fs 生效）' % ((ice + 299) / 100.0), 'ok'
        elif v['n_joker'] == 0:
            how, cls = '本波无小丑', 'dim'
        elif tier == '极速':
            # ★ 极速关整档"不操作"是策略（靠结构与炸率兜底），不是漏操作
            how, cls = '策略性放弃（极速关不点火）', 'dim'
        else:
            how, cls = '<b>无控制</b>', 'bad'
        boom = jb.get(w)
        rows.append('<tr><td>%d</td><td>%s</td><td>%s</td><td class="%s">%s</td>'
                    '<td>%d</td><td>%s</td></tr>'
                    % (w, v['role'], '、'.join(acts) or '—', cls, how, v['n_joker'],
                       ('炸了 1 只（x=%d）' % boom['x']) if boom else '—'))
    return '''
  <table class="mini wide">
    <tr><th>波</th><th>角色</th><th>操作（不含补存冰）</th><th>控丑手段</th>
        <th>小丑</th><th>爆炸</th></tr>
    %s
  </table>''' % ''.join(rows)


def kernel_table(r):
    es = r.get('end_state', {})
    kl = es.get('kernel_log', [])
    if not kl:
        return '<div class="dim small">本档不点核。</div>'
    rows = []
    for k in kl:
        rows.append('<tr><td>w%d</td><td>%.1fs</td><td>%s</td><td>%s</td></tr>'
                    % (k['wave'], k['t'] / 100.0,
                       ('%d-%d' % tuple(k['rc'])) if k['rc'] else '无坑可点',
                       '<span class="ok">指定坑</span>' if k['designated'] else '退坑'))
    # 坑位峰值占用
    ev = []
    for k in kl:
        if k['rc']:
            ev.append((k['t'], 1))
            ev.append((k['t'] + 18000, -1))
    ev.sort()
    cur = peak = 0
    for _, d in ev:
        cur += d
        peak = max(peak, cur)
    return '''
  <table class="mini">
    <tr><th>核</th><th>时刻</th><th>坑位</th><th>是否指定</th></tr>
    %s
    <tr><td class="b">坑位峰值</td><td class="b">%d 个</td>
        <td colspan="2">可用坑 9 个（2-7/2-9/5-7/5-8/5-9/1-8/1-9/6-8/6-9）</td></tr>
  </table>''' % (''.join(rows), peak)


def _control_level(r, row=None):
    """控丑等级的**按实际结果**判定（用户 2026-10-22 口径）

    · **严谨控丑**：每一只小丑要么在爆炸前被打死，要么爆炸**炸空**
      （= 一个植物都没炸到）
    · **有限控丑**：炸到植物的概率极低（这里取 < 5%）
    · 否则：失控

    不再假设"只有 2/5 路的小丑会死 CORE"这类某一阵型专属的口径 ——
    阵型换了，判定照样成立。
    """
    es = r.get('end_state', {}) or {}
    j = es.get('joker') or {}
    spawned = j.get('spawned', 0)
    booms = j.get('booms', 0)
    hit = j.get('boom_hit', 0)
    if not spawned:
        return '本档不出小丑', []
    # 炸空 = 该次爆炸 killed 为空
    detail = j.get('detail') or []
    hit_waves = sorted({b.get('wave') for b in detail if b.get('killed')})
    if hit == 0:
        return '严谨', []
    rate = 100.0 * hit / max(1, booms)
    if rate < 5.0:
        return '有限', hit_waves
    return '失控', hit_waves


def joker_table(r):
    """控丑台账：**按实际模拟结果**逐路给数字与具体后果（不再写死任何阵型文本）"""
    es = r.get('end_state', {}) or {}
    j = es.get('joker') or {}
    n = j.get('spawned', 0)
    if not n:
        return '<div class="dim small">本档不出小丑。</div>'
    sp = j.get('spawned_rows', {}) or {}
    bo = j.get('boom_rows', {}) or {}
    # 逐路的"炸到了什么"：从 detail 里按行聚合
    hits_by_row = {}
    for b in (j.get('detail') or []):
        if b.get('killed'):
            hits_by_row.setdefault(b['row'], []).append(b)
    rows = []
    for rr in sorted(int(x) for x in sp):
        s = sp.get(str(rr), 0)
        b = bo.get(str(rr), 0) if str(rr) in bo else bo.get(rr, 0)
        hb = hits_by_row.get(rr, [])
        dmg = '—'
        if hb:
            seen = []
            for x in hb[:3]:
                seen.append('w%s 炸 %s' % (x.get('wave'), '、'.join(x['killed'])))
            dmg = '；'.join(seen) + ('…' if len(hb) > 3 else '')
        rows.append(
            '<tr><td><b>%d 路</b></td><td>%d</td><td>%d</td><td>%d</td>'
            '<td class="%s">%s</td></tr>'
            % (rr, s, b, len(hb), 'ok' if not hb else 'bad', dmg))
    lvl, waves = _control_level(r)
    lvl_cls = 'ok' if lvl == '严谨' else ('warn' if lvl == '有限' else 'bad')
    span = ('空窗 w' + ',w'.join(str(x) for x in waves[:6])
            + ('…' if len(waves) > 6 else '')) if waves else '—'
    n_pad = sum(len(b.get('pads') or []) for b in (j.get('detail') or []))
    pad_note = ('　另外炸掉垫材 <b>%d</b> 张 —— 垫材是消耗品，'
                '<b>按炸空算</b>，不计入控丑也不进损失名单。' % n_pad) if n_pad else ''
    return '''
  <table class="mini">
    <tr><th>路</th><th>出现</th><th>爆炸</th><th>炸到植物</th><th>具体炸了什么</th></tr>
    %s
    <tr><td class="b">控丑等级</td><td colspan="4" class="%s">
        <b>%s</b>　<span class="dim">%s</span>
        <br><span class="dim">口径：每只小丑要么炸前死亡、要么炸空 = 严谨；
        炸到植物的概率 &lt; 5%% = 有限。**炸到垫材 = 炸空**（消耗品不算植物）。
        早爆 / 晚爆的权重按「这一路最靠前的植物在第几列」取
        （7~9 列重点模拟早爆，2~4 列重点模拟晚爆）。</span>%s</td></tr>
  </table>''' % (''.join(rows), lvl_cls, lvl, span, pad_note)


def catapult_table(r):
    """投篮台账（用户 2026-10-23 口径）：**底线有伞** 或 **投掷前击杀** = 对策有效。"""
    rec = r.get('catapult') or []
    if not rec:
        return ('<div class="ok small">本档的投篮车<b>全部在第一次投掷前被击杀</b>'
                '（生成 → 就绪 473cs → 投掷 74cs，也就是 547cs 内）'
                '→ <b>投篮对策有效</b>。</div>')
    blocked = [x for x in rec if x.get('verdict') == '伞挡下']
    hits = [x for x in rec if str(x.get('verdict', '')).startswith('命中')]
    gone = [x for x in rec if x.get('verdict') == '目标已经没了']
    lost = [x for x in hits if x.get('plant')]
    rows = []
    seen = {}
    for x in hits:
        k = (x['rc'][0], x['rc'][1], x.get('plant'))
        seen[k] = seen.get(k, 0) + 1
    for (rr, cc, pl), n in sorted(seen.items(), key=lambda kv: -kv[1])[:12]:
        rows.append('<tr><td>%d-%d</td><td>%s</td><td class="bad">%d</td></tr>'
                    % (rr, cc, pl or '—', n))
    tail = ''
    if rows:
        tail = ('<table class="mini"><tr><th>被打的底线植物</th><th>植物</th>'
                '<th>命中次数</th></tr>%s</table>' % ''.join(rows))
    lvl = 'ok' if not hits else 'bad'
    return '''
  <div class="%s small">投篮投出 <b>%d</b> 发：<b>%d</b> 发被保护伞挡下，'
  <b>%d</b> 发命中，<b>%d</b> 发目标已经没了。<br>
  <span class="dim">口径（用户 2026-10-23）：陆路底线被伞覆盖，或**在投掷前把它击杀**
  → 对策有效。投掷节奏按《僵尸时间表》：就绪 473cs + 74cs，之后每 300cs 一发；
  篮球滞空 199cs（473+74+199 = 746cs，正好是社区"加速波无伤上限 7.46s"）。</span></div>%s
''' % (lvl, len(rec), len(blocked), len(hits), len(gone), tail)


def bungee_table(r):
    """蹦极台账：**按实际判定**列出"谁被偷 / 谁被伞·炮·冰救下"（用户 2026-10-22 口径）"""
    es = r.get('end_state', {}) or {}
    det = es.get('bungee_detail') or []
    if not det:
        return '<div class="dim small">本档不出蹦极。</div>'
    risky = [b for b in det if (b.get('targets') or [])]
    if not risky:
        # ★ 用户 2026-10-22：炮不会被蹦极锁定；伞覆盖的也不用管；垫材是消耗品。
        #   全都在伞下 → 直接说"不用额外操作"，别报风险。
        tot = sum(b.get('n', 0) for b in det)
        return ('<div class="ok small">本档蹦极 <b>%d</b> 只，'
                '落点都在**保护伞覆盖范围内**（玉米炮不会被蹦极锁定，垫材是消耗品）'
                '→ <b>不需要为蹦极做额外操作</b>。</div>' % tot)
    rows = []
    n_ok = len(det) - len(risky)
    for b in risky:
        tg = b.get('targets') or []
        by_ice = [t for t in tg if t.get('saved') == 'ice']
        by_cob = [t for t in tg if t.get('saved') == 'cob']
        stolen = b.get('stolen') or []
        def fmt(lst, show_need=False):
            if not lst:
                return '—'
            return '、'.join('%d-%d%s' % (x['rc'][0], x['rc'][1], x['plant'])
                            for x in lst)
        rows.append(
            '<tr><td>w%s</td><td>%d</td><td class="dim">%s</td>'
            '<td class="ok">%s</td><td class="ok">%s</td>'
            '<td class="%s">%s</td></tr>'
            % (b.get('wave'), b.get('n', 0), fmt(tg), fmt(by_ice), fmt(by_cob),
               'bad' if stolen else 'dim', fmt(stolen)))
    n_stolen = sum(len(b.get('stolen') or []) for b in det)
    return '''
  <table class="mini">
    <tr><th>波</th><th>蹦极</th><th>暴露的目标</th><th>冰杀救下</th><th>炮炸救下</th><th>被偷</th></tr>
    %s
    <tr><td class="b">结论</td><td colspan="5" class="%s">
      被偷 <b>%d</b> 株　<span class="dim">口径：玉米炮不会被蹦极锁定；
      伞覆盖的不用管；没伞但在「冰杀定式」（二曾 / 瓜曾喷）下的必须让寒冰菇生效；
      其余用炮炸。另外 %d 波蹦极全部落在伞下 → 无需操作。</span></td></tr>
  </table>''' % (''.join(rows), 'ok' if not n_stolen else 'bad', n_stolen, n_ok)


def plant_status_html(r):
    """全场植物状态表（报告总概述）—— **完全按实际阵型逐格生成**"""
    st = (r.get('plants_end')
          or (r.get('end_state') or {}).get('plants_end')
          or [])
    if not st:
        return '<div class="dim small">这一局没有阵型信息。</div>'
    lost = [x for x in st if x.get('init') and not x.get('alive')]
    changed = [x for x in st if x.get('init') and x.get('now') and x['now'] != x['init']]
    pump0 = sum(1 for x in st if x.get('pumpkin_init'))
    pump1 = sum(1 for x in st if x.get('pumpkin'))
    rows = []
    for x in st:
        nm = x.get('now') or ''
        if not x.get('init') and not nm and not x.get('pumpkin'):
            continue
        hp = x.get('hp') or 0
        mx = x.get('max_hp') or 0
        bar = ''
        if nm and mx:
            pct = max(0, min(100, round(100.0 * hp / mx)))
            cls = 'ok' if pct >= 60 else ('warn' if pct >= 25 else 'bad')
            bar = ('<span class="%s">%d/%d</span>' % (cls, hp, mx))
        stat = ('<span class="ok">在</span>' if nm
                else ('<span class="bad">没了</span>' if x.get('init') else '<span class="dim">空</span>'))
        if x.get('init') and nm and x['now'] != x['init']:
            stat = '<span class="warn">被换成%s</span>' % nm
        pump = ('🎃%d' % x['pumpkin_hp']) if x.get('pumpkin') else (
            '<span class="bad">南瓜没了</span>' if x.get('pumpkin_init') else '')
        rows.append('<tr><td class="b">%d-%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                    % (x['row'], x['col'], x.get('init') or '—', stat, bar,
                       pump + ('🪜' if x.get('ladder') else '')))
    return '''
  <table class="mini">
    <tr><th>格</th><th>阵型里</th><th>结束状态</th><th>血量</th><th>南瓜</th></tr>
    %s
    <tr><td class="b">汇总</td><td colspan="4">
      阵型共 <b>%d</b> 格有植物　·　结束存活 <b class="%s">%d</b> 株　·
      损失 <b class="%s">%d</b> 株%s　·　南瓜 <b>%d/%d</b> 完好</td></tr>
  </table>''' % (''.join(rows), sum(1 for x in st if x.get('init')),
                 'ok' if not lost else 'bad', sum(1 for x in st if x.get('alive')),
                 'ok' if not lost else 'bad', len(lost),
                 ('（%s）' % '、'.join('%d-%d %s' % (x['row'], x['col'], x['init'])
                                     for x in lost[:6])
                  + ('…' if len(lost) > 6 else '')) if lost else '',
                 pump1, pump0)


def legend_html():
    """时间轴图例：字母为主，颜色为辅"""
    items = [('P', '玉米炮'), ('N', '核弹'), ('A', '樱桃'), ("A'", '辣椒'),
             ('I', '冰 / 存冰'), ('W', '窝瓜'), ('C', '垫材'), ('F', '补大喷')]
    out = ['<div class="legend big">', '<span class="lg-t">时间轴字母</span>']
    for ab, name in items:
        out.append('<span><b style="color:%s">%s</b> %s</span>'
                   % (ABBR_COLOR[ab], ab, name))
    out.append('<span><b style="color:#a16207">·</b> 补大蒜</span>')
    out.append('<span><b style="color:#cbd5e1">·</b> 补存冰</span>')
    out.append('<span style="margin-left:10px" class="dim">'
               '（P / N / A / A′ 各占一行，不会叠在一起；'
               '点状标记是维护性动作，不算轨迹。鼠标悬停任一波可看该波明细）</span></div>')
    return ''.join(out)


def card_html(r, dev=None):
    f = r.get('fail')
    res = ('<span class="bad">崩：%s</span>' % f['why']) if f else '<span class="ok">跑完 20 波</span>'
    es = r.get('end_state', {}) or {}
    cards = es.get('cards', {})
    dark = [(k, v) for k, v in cards.items() if v > 0]
    dark_html = ('、'.join('%s 还剩 %.1fs' % (k, v / 100.0) for k, v in dark)
                 if dark else '<span class="ok">全部亮着</span>')

    ts = [w['t'] for w in r['waves']]
    # 与总览同一口径：常规波长 = (w1→w9)/8 与 (w11→w19)/8 的平均
    span = (((ts[8] - ts[0]) / 800.0 + (ts[18] - ts[10]) / 800.0) / 2.0
            if len(ts) >= 20 else 0)

    lost = es.get('plants_lost', [])
    lost_html = ('、'.join(lost[:8]) + ('…' if len(lost) > 8 else '')) if lost else '无'

    items = classify(r, dev)
    top = items[0]['lv'] if items else None
    top_html = (level_badge(top) if top
                else '<span class="lv" style="background:#059669">零偏离</span>')

    import json as _json
    hj = _json.dumps(hover_json(r), ensure_ascii=False)

    tpl = '''
<div class="card">
  <div class="chead">
    <b>__TIER__</b>　__RES__　__TOP__
    <span class="dim">总 __T__s｜w__NW__ 波｜波长 __SPAN__s｜减速 __COV__%｜__DPS__ dps</span>
  </div>
  <div class="kpis">
    <div class="k"><span>阳光结余（8000 起）</span><b class="__SUNCLS__">__SUN__</b>
      <span style="font-size:10px;color:#94a3b8">峰值 __SUNPEAK__</span></div>
    <div class="k"><span>南瓜存活</span><b>__PK__ / __PK0__</b></div>
    <div class="k"><span>补南瓜</span><b>__REP__ 次</b></div>
    <div class="k"><span>植物损失</span><b>__NLOST__</b></div>
    <div class="k"><span>结束卡槽</span><b class="sm">__DARK__</b></div>
  </div>
  <div class="sec">全场植物状态（结束那一刻 · 按实际阵型逐格列出）</div>
  __PSTATUS__
  <div class="sec">脱离设计清单（分级）</div>
  __DIVG__
  <div class="sec">时间轴（字母标记 · 悬停看明细）</div>
  __SVG__
  __LEGEND__
  <div class="sec">轨道执行表（20 波）</div>
  __WT__
  __GARLIC__
  __FOG__
  <div class="grid3">__KT__ __JT__ __BT__</div>
  __CT__
  <div class="dim small">损失清单：__LOST__</div>
  <script type="application/json" class="wvjson">__JSON__</script>
</div>'''
    rep = [
        ('__TIER__', r.get('_tier', '')),
        ('__RES__', res),
        ('__TOP__', top_html),
        ('__T__', '%.0f' % (r['t_end'] / 100.0)),
        ('__NW__', str(len(r['waves']))),
        ('__SPAN__', '%.2f' % span),
        ('__COV__', '%.0f' % r.get('slow_cov', 0)),
        ('__DPS__', '%d' % r.get('dps', 0)),
        ('__SUN__', '%d' % r.get('sun_end', 0)),
        ('__SUNCLS__', 'warn' if r.get('sun_capped') else ''),
        ('__SUNPEAK__', ('%d ⚠触顶（经济溢出）' % r.get('sun_peak', 0))
         if r.get('sun_capped') else '%d' % r.get('sun_peak', 0)),
        ('__ICECLS__', 'bad' if es.get('ice_stock_perm', 0) == 0 else 'ok'),
        ('__ICE__', str(es.get('ice_stock_perm', 0))),
        ('__ICEMAX__', str(len(es.get('ice_slots') or {}) or 4)),
        ('__ICETMP__', ''),
        ('__PK__', str(es.get('pumpkins_alive', 0))),
        ('__PK0__', str(es.get('pumpkins_init', 0))),
        ('__REP__', str(es.get('repairs', 0))),
        ('__NLOST__', str(len(lost))),
        ('__DARK__', dark_html),
        ('__DIVG__', divergence_html(r, dev)),
        ('__PSTATUS__', plant_status_html(r)),
        ('__SVG__', svg_for(r)),
        ('__LEGEND__', legend_html()),
        ('__WT__', wave_table(r)),
        ('__KT__', kernel_table(r)),
        ('__JT__', joker_table(r)),
        ('__BT__', bungee_table(r)),
        ('__CT__', catapult_table(r)),
        ('__GARLIC__', garlic_html(r)),
        ('__FOG__', fog_html(r)),
        ('__LOST__', lost_html),
        ('__JSON__', hj),
    ]
    for k, v in rep:
        tpl = tpl.replace(k, v)
    return tpl


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    only = sys.argv[2] if len(sys.argv) > 2 else None
    tiers = [only] if only else ['慢速', '变速', '快速', '极速']

    rows = []
    cards = []
    for tier in tiers:
        C.MODE = tier
        ok = 0
        spans, cov, dps, suns, pumps = [], [], [], [], []
        ices, crushes, refills, uses, temps = [], [], [], [], []
        kns, jbn, jhit = [], [], []
        sunmax = [0]
        raw = []
        card_cnt = Counter()
        best = None
        for s in range(n):
            C._RED['plan'] = None
            r = R.run_once(s)
            r['_tier'] = '%s / seed %d' % (tier, s)
            r['_rescue'] = C.RESCUE_BY_TIER.get(tier, True)
            ts = [w['t'] for w in r['waves']]
            if len(ts) >= 20:
                ok += 1
                # ★ 2026-10-20：平均波长只算**常规波**。
                #   w9→w10、w19→w20 是"拖满 45s + 红字 7.2s"的收尾段，
                #   混进去会把快速/极速的波长虚抬 30~60%。
                a = (ts[8] - ts[0]) / 100.0 / 8.0      # w1→w9
                b = (ts[18] - ts[10]) / 100.0 / 8.0    # w11→w19
                spans.append((a + b) / 2.0)
                raw.append((ts[19] - ts[0]) / 100.0 / 19.0)
                if best is None:
                    best = r
            cov.append(r['slow_cov'])
            dps.append(r['dps'])
            suns.append(r['sun_end'])
            if r.get('sun_peak', 0) > sunmax[0]:
                sunmax[0] = r.get('sun_peak', 0)
            pumps.append(r['pumpkin_lost'])
            _es = r.get('end_state', {}) or {}
            ices.append(_es.get('ice_stock_perm', 0))
            temps.append(_es.get('ice_stock_temp', 0))
            crushes.append(_es.get('cars_crushed', 0))
            refills.append(_es.get('ice_refill', 0))
            uses.append(_es.get('ice_used', 0))
            kns.append(len(_es.get('kernel_log', [])))
            jbn.append(_es.get('joker', {}).get('spawn25', 0))
            jhit.append(_es.get('joker', {}).get('boom25', 0))
            for a in r['actions']:
                if a['ok']:
                    card_cnt[a['name']] += 1
        if best is None:
            best = r
            best['_tier'] = '%s / seed %d（崩）' % (tier, n - 1)
        avg = sum(spans) / len(spans) if spans else 0
        ref = VIDEO.get(tier)
        dev = ((avg - ref) / ref * 100) if (spans and ref) else 0
        rows.append(dict(tier=tier, ok=ok, avg=avg, dev=dev,
                         cov=sum(cov) / len(cov), dps=sum(dps) / len(dps),
                         sun=sum(suns) / len(suns), pump=sum(pumps) / len(pumps),
                         sunmax=sunmax[0],
                         cards=card_cnt,
                         ice=sum(ices) / len(ices), crush=sum(crushes),
                         temp=sum(temps) / len(temps),
                         raw=(sum(raw) / len(raw)) if raw else 0,
                         kn=sum(kns) / len(kns), jbn=sum(jbn), jhit=sum(jhit),
                         refill=sum(refills) / len(refills), use=sum(uses) / len(uses)))
        _items = classify(best, dev)
        rows[-1]['lvl'] = _items[0]['lv'] if _items else None
        best['_dev'] = dev
        cards.append(best)

    h = ['<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">',
         '<title>trackcheck · 运阵报告</title><style>',
         '''body{font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
           margin:0;padding:24px 28px;background:#fff;color:#0f172a}
         h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:26px 0 10px;
           padding-left:8px;border-left:3px solid #2563eb}
         .sub{color:#64748b;font-size:12px;margin-bottom:18px}
         table{border-collapse:collapse;width:100%;font-size:13px}
         th,td{border-bottom:1px solid #e2e8f0;padding:6px 8px;text-align:right}
         th:first-child,td:first-child{text-align:left}
         th{background:#f8fafc;font-weight:600;color:#475569}
         .ok{color:#059669;font-weight:600}.bad{color:#dc2626;font-weight:600}
         .dim{color:#64748b;font-size:12px}.small{font-size:11px}
         .card{border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;
           margin:14px 0;background:#fff}
         .chead{margin-bottom:10px}
         .kpis{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px}
         .k{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;
           padding:6px 10px;min-width:98px}
         .k span{display:block;color:#64748b;font-size:11px}
         .k b{font-size:15px}.k b.sm{font-size:11px;font-weight:500;color:#b45309}
         svg.tl{width:100%;height:auto;display:block;margin-top:8px;
           border:1px solid #e2e8f0;border-radius:6px;background:#fff}
         svg .lk{font-size:9px;fill:#475569;text-anchor:end}
         svg .lk2{font-size:8px;fill:#94a3b8;text-anchor:end}
         svg .tx{font-size:9px;fill:#94a3b8;text-anchor:middle}
         svg .wl{font-size:8.5px;fill:#64748b;text-anchor:middle}
         svg .wl.flag{fill:#dc2626;font-weight:700;font-size:9.5px}
         .sec{font-size:12.5px;font-weight:700;color:#334155;margin:14px 0 6px;
           padding-left:7px;border-left:3px solid #cbd5e1}
         .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
         table.mini.wide{font-size:11px}
         table.mini.wide td:nth-child(3){font-size:10.5px;color:#0f172a}
         .ledgers{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:14px;margin:12px 0 6px}
         table.mini{font-size:11.5px;width:100%}
         table.mini th,table.mini td{padding:3px 6px}
         table.mini td:nth-child(2){text-align:right;white-space:nowrap}
         table.mini td:nth-child(3),table.mini th:nth-child(3){text-align:left;font-size:10.5px;color:#64748b}
         table.mini td.b,table.mini td.b th{font-weight:700}
         .ok{color:#059669;font-weight:600}.warn{color:#d97706;font-weight:600}
         .lv{display:inline-block;color:#fff;border-radius:4px;padding:1px 6px;
           font-size:10.5px;font-weight:700;white-space:nowrap}
         .legend.big{gap:16px;font-size:12px;background:#f8fafc;border:1px solid #e2e8f0;
           border-radius:6px;padding:8px 12px;margin-top:8px;align-items:center;
           flex-wrap:wrap;display:flex;color:#334155}
         .legend.big .lg-t{font-size:11px;color:#64748b;font-weight:700;margin-right:2px}
         .legend.big b{font-family:ui-monospace,Consolas,monospace;font-size:13.5px;
           margin-right:3px}
         svg .ab{font-size:6.6px;font-weight:700;
           font-family:ui-monospace,Consolas,monospace}
         svg .ab-l{font-weight:700;fill:#334155}
         svg rect.wvhot:hover{fill:#2563eb;fill-opacity:0.07}
         .note{padding:8px 12px;border-radius:6px;font-size:12px;margin:6px 0}
         .note.ok{background:#ecfdf5;color:#065f46}
         table.divg td{text-align:left;vertical-align:top}
         table.divg td:first-child{white-space:nowrap}
         table.divg tr:hover{background:#f8fafc}
         .tip{position:fixed;z-index:999;background:#0f172a;color:#e2e8f0;
           border-radius:8px;padding:10px 12px;font-size:11.5px;line-height:1.6;
           box-shadow:0 10px 30px rgba(15,23,42,.35);pointer-events:none;
           display:none;max-width:430px;border:1px solid #334155}
         .tip h4{margin:0 0 6px;font-size:12.5px;color:#fff;font-weight:700}
         .tip .k2{color:#94a3b8}
         .tip .sep{height:1px;background:#334155;margin:6px 0}
         .tip b{color:#fff}
         .tip .lv{font-size:10px;padding:0 5px}
         .tip .water{opacity:.55}
         .tip .cdx{display:inline-block;min-width:74px;margin-right:2px}
         .legend{display:flex;gap:14px;font-size:11px;color:#475569;margin:6px 0 0}
         .legend i{display:inline-block;width:9px;height:9px;border-radius:2px;
           margin-right:4px;vertical-align:-1px}
         ''', '</style></head><body>',
         '<h1>trackcheck · 运阵报告</h1>',
         '<div class="sub">模拟器 tools/trackcheck ｜ 阵型：15曾 / 7冰瓜 / 4大喷 / 6双花 / 4存冰 / 2伞 / 2香蒲 ｜ 24南瓜（4梯）</div>',
         '<h2>总览</h2><table>',
         '<tr><th>档</th><th>录像</th><th>常规波长</th><th>偏差</th>'
         '<th>含收尾段</th><th>跑完</th>'
         '<th>减速覆盖</th><th>输出</th><th>阳光结余（8k 起）</th><th>南瓜损耗</th>'
         '<th>存冰结余</th><th>冰车碾压</th><th>核/局</th>'
         '<th>炸率(2/5路)</th><th>最高等级</th></tr>']
    for r in rows:
        h.append('<tr><td><b>%s</b></td><td>%.2fs</td><td>%.2fs</td>'
                 '<td class="%s">%+.0f%%</td><td class="dim">%.2fs</td>'
                 '<td>%d/%d</td><td>%.0f%%</td>'
                 '<td>%.0f dps</td><td class="%s">%.0f</td><td>%.1f</td>'
                 '<td class="%s">%.1f / 4</td><td class="%s">%d</td>'
                 '<td>%.1f</td><td>%d / %d</td><td>%s</td></tr>'
                 % (r['tier'], VIDEO.get(r['tier']) or 0, r['avg'],
                    'ok' if abs(r['dev']) < 15 else 'dim', r['dev'], r['raw'],
                    r['ok'], n, r['cov'], r['dps'],
                    'warn' if r.get('sunmax', 0) >= 9990 else '', r['sun'], r['pump'],
                    'ok' if r['ice'] + r['temp'] >= 1 else 'warn',
                    r['ice'] + r['temp'],
                    'ok' if r['crush'] == 0 else 'bad', r['crush'],
                    r['kn'], r['jhit'], r['jbn'],
                    (level_badge(r['lvl']) if r.get('lvl')
                     else '<span class="lv" style="background:#059669">零偏离</span>')))
    h.append('</table>')

    h.append("""<h2>本轮修了什么（v5.7）</h2>
    <table>
      <tr><th>问题</th><th>说明</th><th>修法</th></tr>
      <tr><td><b>大蒜换行跨了水陆</b><br>
          <span class="dim">"陆路僵尸吃大蒜不会去水路，水路僵尸吃大蒜也不会去陆路"</span></td>
          <td>上一版抄了"相邻两路随机二选一"的通用说法，把 2 路写成 <code>→ 1 或 3 路</code>、
              5 路写成 <code>→ 4 或 6 路</code>。3/4 路是**水池**，陆路僵尸根本下不去 ——
              所以实际只有唯一去向，不存在"分流"。<br>
              这也解释了为什么 2-9 / 5-9 的大蒜是**单向驱赶**：<br>
              <b>2-9 → 只能去 1 路</b>　<b>5-9 → 只能去 6 路</b></td>
          <td>换行表改成 <code>{1:2, 2:1, 3:4, 4:3, 5:6, 6:5}</code>，
              并在 <code>_garlic()</code> 里**按地形再过滤一遍**（表写错也翻不了车）。<br>
              实测（10 局）：来源 <b>2路 257 / 5路 143</b>，去向 <b>1路 257 / 6路 143</b> ——
              一条都没跑错。<br>
              连带效应：岸路压力不再被水路的忧郁菇分担，**全部灌进边路**，
              南瓜修补 2 → <b>27 次/局</b>，波长 9.16 → 9.40s（+10%），但 CORE 仍零损失、等级仍 L3。</td></tr>
      <tr><td><b>极速关选卡写错了</b></td>
          <td>之前给极速关列了 `I′`（复制冰）却没有**咖啡豆** ——
              PE 是白天场地，冰菇种下去不点咖啡豆根本不会生效。
              而且极速关本来就不带复制冰。</td>
          <td>极速选卡改为：<b>冰 / 大蒜 / 樱桃 / 辣椒 / 南瓜 / 南瓜′ / 咖啡豆 /
              荷叶 / 大喷 / 曾哥</b>（无 I′，有咖啡豆）。</td></tr>
      <tr><td><b>极速关不该带核</b></td>
          <td>极速关的出怪里**没有冰车、没有投篮车**（实测 20 波：铁门 272、撑杆 146、
              潜水 136、海豚 109、跳跳 85、小丑 79、舞王 79、读报 62 …… 冰车 0、投篮 0）。
              核弹本来是用来炸车和巨人的，没有目标就纯属浪费一个卡位。</td>
          <td>把 <b>N 换成大蒜</b>，种在 <b>2-9 / 5-9</b> 并持续维护。
              大蒜 400 血、一口 100（啃 4 口碎），靠换行把岸路僵尸单向赶去边路
              （2 路→1 路、5 路→6 路，不跨水陆）。实测 95 次换行 / 23 次啃碎。
              报告新增<b>大蒜台账</b>（换行次数 / 啃碎次数 / 来源 / 去向）。</td></tr>
    </table>
    <table>
      <tr><th>问题</th><th>根因 / 说明</th><th>修法</th></tr>
      <tr><td><b>开局阳光不是社区的 8k</b></td>
          <td>社区运阵表演视频约定俗成：**每个 2F 开局 8000 阳光**。
              设计意图是两头兼顾 —— 既不轻易摸到 9990 上限（真打到就说明经济特别好），
              又给了极大的亏损空间（运阵不被阳光限制，同时还能看出经济状况）。
              之前模拟按 1000 跑，等于把"经济压力"放大了 8 倍。</td>
          <td>默认 `SUN0 = 8000`，并把阳光**封顶 9990**（`SUN_CAP`）。
              报告里 KPI 直接写"阳光结余（8000 起）"，旁边挂**峰值**；
              一旦某局真的触顶会标红 `⚠触顶`。</td></tr>
      <tr><td><b>阵线参差不齐</b></td>
          <td>之前只输出"这一波有僵尸的路"，3/4 路（水路）常常整行消失。</td>
          <td>固定输出 1~6 路，没僵尸写"无"（水路降权）。
              海豚 / 矿工 / 小鬼 这类**已脱离阵线**的僵尸不计入 —— 见下。</td></tr>
    </table>
    <table>
      <tr><th>问题</th><th>根因</th><th>修法</th></tr>
      <tr><td><b>刷怪时序</b><br>
          <span class="dim">"所有的怪都是同一时刻内刷出来的，刷怪地点的微小差异在简化模型中忽略"</span></td>
          <td>之前按 <code>SPAWN_GAP 6~16cs</code> 逐只错开生成。这个加工有两个副作用：
              ① 人为拉长波长；② 造出"第二辆冰车晚出生"这种<b>不存在</b>的两难。</td>
          <td>所有僵尸 <code>due = 刷新时刻</code>，出生点固定第 10 列。
              于是"同路冰车视觉重合"自动成立 —— 一个窝瓜压死整条路是<b>机制结果</b>，
              不需要额外假设。w11 落 5-9 不再有两难。</td></tr>
      <tr><td><b>窝瓜的判定形态</b><br>
          <span class="dim">"视作一个 1 格宽的、1.8k 伤害即刻生效的攻击判定域"</span></td>
          <td>之前是"种下 → 等 6s 出怪结束 → 选中一只 → 扣血"，
              等于给窝瓜编了一套不属于它的时延和索敌逻辑。</td>
          <td>重写成 <code>_ash_cell()</code>：判定域 <code>[cx−40, cx+40]</code>，
              与受击框**相交即生效**，对本行所有相交僵尸各 1800，无时延。
              <b>这同时解释了"为什么窝瓜能 100% 保住 5-9"</b>：
              车头进 [640,720] 就爆，而车尾（冰道前沿，+80）还在 720~800，9 列还没被铺。</td></tr>
      <tr><td><b>变速"冰不够"</b><br>
          <span class="dim">"变速关最后存冰结余这么多，你说冰不够我不信"</span></td>
          <td>用户质疑得对。<b>冰一直是够的</b>，账能平（慢速 121 供 / 97 消 / 剩 24；
              变速 114 / 92 / 剩 22）。真正的原因是三条叠加：
              ① <code>_kernel_slack</code> 要求"必须和下个固定核复用同一个坑"，
              变速波长下永远为负 → <b>整局只点 2 次核</b>；
              ② AA' 被写成"点核后的下一波"，于是每 4 波只肯用 1 次灰烬，
              其余全退化成冰；③ w19 救急把最后一个冰点掉，w20 冰杀蹦极没冰。</td>
          <td>① <code>_kernel_slack</code> 改成按<b>坑位数</b>判定（9 个坑、2-9/5-9 只留给锚点），
              核从 2 → 4 次；② <b>AA' 独立化</b>（不再依附核），樱桃辣椒 50s CD 各 4 次都用上；
              ③ 救急层在 w19/w20 保住最后一个冰。结果：<b>空窗 0</b>，存冰 3.8。</td></tr>
      <tr><td><b>波长口径</b></td>
          <td>刷怪改成同刻后，四档波长整体偏快 19~24%（极速只差 6%）。
              极速是"纯 IO、不操作"，它准 → IO 模型准；其余档偏快 → 灰烬+冰的等效清血被高估约 1.25 倍。</td>
          <td>不篡改机制，把偏差记成显式标定系数 <code>R2_CALIB = 0.80</code>
              （<code>R2_THRESHOLD = wiki 0.50~0.65 × 0.80</code>）。
              调完四档 <b>−2% / −3% / −8% / +4%</b>。
              将来若把灰烬对数修准，把系数调回 1.0 即可。</td></tr>
      <tr><td><b>1/6 路"不致死"的理由写错了</b></td>
          <td>之前写"CORE 在 3 列，7~8 列炸不到"。结论对，过程错。</td>
          <td>改为：<b>边路小丑在 6 列就被双大喷打死 / 早爆炸空</b>
              （1-4/1-5、6-4/6-5 的火力线）。真正受小丑威胁的 CORE 是
              <b>岸路 6 列眼曾（2-6 / 5-6）</b>，而边路小丑走不到能威胁它的位置。</td></tr>
      <tr><td><b>极速关的"不操作"被当成缺陷</b></td>
          <td>空窗统计把极速关 16 个常规波全标红，但那是<b>策略</b>不是漏操作。</td>
          <td>控丑台账改三态：严谨 / 有限（列出空窗波号）/ <b>策略性放弃</b>。</td></tr>
    </table>""")
    h.append(legend_html())
    h.append("""<h2>分级口径（脱离设计怎么判）</h2>
    <table>
      <tr><th>等级</th><th>含义</th><th>典型现象</th><th>怎么处理</th></tr>
      <tr><td>%s</td><td>不可接受</td><td>%s</td><td>%s</td></tr>
      <tr><td>%s</td><td>练手感就能补</td><td>%s</td><td>%s</td></tr>
      <tr><td>%s</td><td>付阳光就能补</td><td>%s</td><td>%s</td></tr>
      <tr><td>%s</td><td>本来就正常</td><td>%s</td><td>%s</td></tr>
      <tr><td>%s</td><td>模型的问题</td><td>%s</td><td>%s</td></tr>
    </table>
    <div class="dim small" style="margin-top:6px">
      判定原则：先问"玩家能不能靠看场面补一手" —— 能，就是 L1（不是设计错）；
      再问"补的代价是不是只有阳光" —— 是，就是 L2；
      再看"这是不是本来就这么打" —— 是，就是 L3。L4 只归因于模型，不归因于打法。
    </div>""" % (
        level_badge('L0'), LEVELS[0][3], LEVELS[0][4],
        level_badge('L1'), LEVELS[1][3], LEVELS[1][4],
        level_badge('L2'), LEVELS[2][3], LEVELS[2][4],
        level_badge('L3'), LEVELS[3][3], LEVELS[3][4],
        level_badge('L4'), LEVELS[4][3], LEVELS[4][4],
    ))

    h.append('<h2>逐档代表局（每档取第一个跑完的）</h2>')
    for c in cards:
        h.append(card_html(c, c.get('_dev')))

    h.append('<div class="sub" style="margin-top:26px">'
             '时间轴读法：顶部数字是波号（红色=旗帜波，竖线贯穿）。'
             '泳道自上而下是 <b>N</b>（核）/ <b>A</b>（樱桃）/ <b>A′</b>（辣椒）/ '
             '<b>I</b>（冰·存冰）/ <b>C·W·F</b>（垫材·窝瓜·补大喷）—— '
             'N / A / A′ 各占一行，不会叠在一起。补存冰只画淡色小点（不算轨迹）。'
             '两个折线区是「僵尸数(黑)与减速数(蓝)」「阳光」。'
             '<b>鼠标悬停任一波</b>可看该波明细（阳光 / 存冰 / 卡槽 CD / 计划与临场操作 / '
             '僵尸阵线 / 场上植物）。'
             '</div>')
    h.append('''<script>
(function(){
  var tip=null;
  function ensure(){
    if(!tip){tip=document.createElement('div');tip.className='tip';document.body.appendChild(tip);}
    return tip;
  }
  function show(e){
    var el=e.currentTarget, card=el.closest('.card');
    if(!card) return;
    var node=card.querySelector('script.wvjson');
    if(!node) return;
    var data; try{data=JSON.parse(node.textContent);}catch(err){return;}
    var d=data[el.getAttribute('data-w')];
    if(!d) return;
    var t=ensure(); t.innerHTML=d.html; t.style.display='block'; move(e);
  }
  function move(e){
    if(!tip||tip.style.display==='none') return;
    var x=e.clientX+16, y=e.clientY+16, r=tip.getBoundingClientRect();
    if(x+r.width>window.innerWidth-8) x=e.clientX-r.width-16;
    if(y+r.height>window.innerHeight-8) y=e.clientY-r.height-16;
    if(x<6) x=6; if(y<6) y=6;
    tip.style.left=x+'px'; tip.style.top=y+'px';
  }
  function hide(){ if(tip) tip.style.display='none'; }
  var hots=document.querySelectorAll('rect.wvhot');
  for(var i=0;i<hots.length;i++){
    hots[i].addEventListener('mouseenter',show);
    hots[i].addEventListener('mousemove',move);
    hots[i].addEventListener('mouseleave',hide);
  }
  document.addEventListener('scroll',hide,true);
})();
</script>''')
    h.append('</body></html>')

    # 收尾：把说明文字里手写的 **粗体** 统一换成 <b>（单行内匹配，不跨行，
    # 所以不会误伤 <script> 里的 JSON / JS）
    import re as _re
    body = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', '\n'.join(h))
    out = 'tools/trackcheck/out_report.html'
    open(out, 'w', encoding='utf-8').write(body)
    print('-> %s' % out)
    for r in rows:
        print('%s  跑完 %d/%d  波长 %.2fs (%+.0f%%)  减速 %.0f%%  阳光 %.0f  '
              '存冰 %.1f/4（补 %.1f / 点 %.1f）  冰车碾压 %d'
              % (r['tier'], r['ok'], n, r['avg'], r['dev'], r['cov'], r['sun'],
                 r['ice'], r['refill'], r['use'], r['crush']))


if __name__ == '__main__':
    main()
