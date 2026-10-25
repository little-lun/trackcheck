# -*- coding: utf-8 -*-
"""
layout.py —— 阵容布置（场上植物）的数据模型 + PvZ Tools 阵型字符串编解码

★ 阵型字符串格式见 https://pvz.lmintlcx.com/files/rfc1437.txt（RFC1437）
  ① 标准 Base64（兼容 Base64URL）；
  ② 解码后整段与 0x54 异或；
  ③ 结果 = 若干字节的 **zlib 压缩数据** + 1 字节 RS；
  ④ RS：高 4 位 = 钉耙所在行（0 = 无；最上方为第 1 行），低 4 位 = 场景
     0 白天 / 1 黑夜 / 2 泳池 / 3 雾夜 / 4 屋顶 / 5 月夜；
  ⑤ 解压后是若干个 2 字节 GRID，泳池·雾夜 54 个，其余 45 个，
     按「从左到右、从上到下」排；
  ⑥ GRID 位域（bit0 = 梯子）：
        10~15 P  主要植物类型（0 = 无，1~48 = 代号 0~47）
            9 PI 主要植物是否模仿者
            8 PA 主要植物是否睡醒
          6~7 B  底部植物/墓碑：0 无 / 1 睡莲 / 2 花盆 / 3 墓碑
            5 BI 底部植物是否模仿者
            4 K  是否有南瓜壳
            3 KI 南瓜壳是否模仿者
            2 C  是否有咖啡豆
            1 CI 咖啡豆是否模仿者
            0 L  是否有梯子

★ 本库的内部表示（`array`）是一个稀疏 dict：
      {(row, col): {'plant': 名称或'模仿者:X' 或 None,
                    'pumpkin': bool, 'ladder': bool,
                    'awake': bool, 'base': '睡莲'|'花盆'|None, 'grave': bool}}
  只有"有内容"的格子才出现在 dict 里。
"""

import base64
import struct
import zlib

from . import data as D
from . import metainfo as MI

# 场景代号 → 场地；RFC1437 的 S 值
SCENE = {'DE': 0, 'NE': 1, 'PE': 2, 'FE': 3, 'RE': 4}
SCENE_BY_CODE = {v: k for k, v in SCENE.items()}
SIX_ROW = ('PE', 'FE')          # 这两个场地是 6 行 9 列 = 54 格

# 底部植物（B 位域）
BASE_NONE, BASE_LILY_B, BASE_POT_B, BASE_GRAVE = 0, 1, 2, 3
BASE_BY_NAME = {'睡莲': BASE_LILY_B, '花盆': BASE_POT_B, '荷叶': BASE_LILY_B}
NAME_BY_BASE = {BASE_LILY_B: '睡莲', BASE_POT_B: '花盆'}

MIMIC = '模仿者'

# 布局里不能当"主要植物"选的（它们是壳 / 基座 / 一次性）
GRID_HIDDEN = ('南瓜', '睡莲', '花盆')

# ★ 2026-10-22：底座（基座）规则 —— 用户口径（第二次修订）
#   · 水路 / 屋顶：底座**不是无条件强制**的 —— 空地可以不放底座，
#     但只要这一格**有植物**、**套了南瓜/梯子南瓜**、或是**玉米炮占的格子**，
#     就必须有底座（睡莲 / 花盆），且此时底座锁定勾上
#   · 草地（陆地）：**不能放睡莲**，花盆可有可无
BASE_LILY = '睡莲'
BASE_POT = '花盆'

# ★ 玉米炮占 1×2：头格是本体、尾格是右边的 (r, c+1)（与 engine.Cell.tail 一致）
COB = '玉米炮'
COB_SPAN = 2


def base_name(field_code, row):
    """这一格**唯一合法**的底座名（不代表必须有）"""
    from . import fields as F
    f = F.get(field_code)
    if row in f.water:
        return BASE_LILY
    return BASE_POT


def needs_base(field_code, row):
    """这一格是不是"水上/屋顶"这种没有底座就种不了东西的格子"""
    from . import fields as F
    f = F.get(field_code)
    return row in f.water or f.base_plant == BASE_POT


def base_options(field_code, row):
    """这一格允许的底座 → (可选列表, 这一格该用的底座名)

    · 水路 → ['睡莲']　天台 → ['花盆']　草地 → ['花盆']（不能放睡莲）
    放不放由格子内容决定（见 `base_locked()`），不再无条件强制。
    """
    return [base_name(field_code, row)], base_name(field_code, row)


def is_cob(cell):
    return split_mimic((cell or {}).get('plant') or '')[0] == COB


def base_locked(field_code, row, cell):
    """这一格的底座是否"必须有"（= 界面上锁定勾上）"""
    if not needs_base(field_code, row):
        return False
    cell = cell or {}
    return bool(cell.get('plant') or cell.get('pumpkin')
                or cell.get('ladder') or cell.get('grave'))


def cob_tail_rc(array, rc):
    """`rc` 若是某门玉米炮的尾格 → 返回炮头格键；否则 None"""
    r, c = rc
    head = (r, c - 1)
    if c - 1 < 1 or head not in (array or {}):
        return None
    return head if is_cob(array[head]) else None



def is_mimic(name):
    return isinstance(name, str) and name.startswith(MIMIC + ':')


def split_mimic(name):
    """'模仿者:寒冰菇' → ('寒冰菇', True)；普通名 → (名, False)"""
    if is_mimic(name):
        return name.split(':', 1)[1], True
    return name, False


def join_mimic(name, mimic):
    return (MIMIC + ':' + name) if mimic else name


def plant_code(name):
    """植物名 → RFC1437 代号（0~47）；未知返回 None"""
    core, _m = split_mimic(D.canon(name or ''))
    try:
        return MI.PLANT_CODES.index(core)
    except ValueError:
        return None


def code_plant(code):
    if 0 <= code < len(MI.PLANT_CODES):
        return MI.PLANT_CODES[code]
    return None


def blank_cell():
    return dict(plant=None, pumpkin=False, ladder=False, awake=True,
                base=None, grave=False)


def clean(cell):
    """去掉默认值；整格空则返回 None"""
    if not cell:
        return None
    out = dict(cell)
    out.pop('mimic', None)               # 旧字段，兼容
    base = out.get('base')
    if base == '荷叶':
        out['base'] = '睡莲'
    if not out.get('base'):
        out['base'] = None
    out['plant'] = out.get('plant') or None
    out['pumpkin'] = bool(out.get('pumpkin'))
    out['ladder'] = bool(out.get('ladder')) and out['pumpkin']
    out['awake'] = bool(out.get('awake', True))
    out['grave'] = bool(out.get('grave'))
    # ★ 2026-10-23：core 标签（丢了就算崩阵）—— 默认 False，不写进旧数据
    out['core'] = bool(out.get('core'))
    # ★ 2026-10-24：常磨损标签（自动选卡要带它 + 全场判定随时补）
    out['wear'] = bool(out.get('wear'))
    if (out['plant'] is None and not out['pumpkin'] and not out['base']
            and not out['grave'] and not out['core'] and not out['wear']):
        return None
    return out


def _rc(rc):
    """键归一化：接受 (r, c) / [r, c] / "r-c" / "r,c"：认不出返回 None"""
    if isinstance(rc, str):
        parts = rc.replace(',', '-').replace('_', '-').split('-')
        if len(parts) != 2:
            return None
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None
    try:
        return int(rc[0]), int(rc[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return None


def normalize(array):
    """把任意来源的 array 归一化：键转 int 元组、值走 clean()"""
    out = {}
    for rc, cell in (array or {}).items():
        k = _rc(rc)
        if k is None:
            continue
        cell = dict(cell or {})
        if cell.get('plant'):
            cell['plant'] = D.canon(cell['plant'])
            # 旧阵型里的「存冰」= 睡着的寒冰菇（只做导入兼容）
            if cell['plant'] == '存冰':
                cell['plant'] = '寒冰菇'
                cell['awake'] = False
            core, mimic = split_mimic(cell['plant'])
            cell['plant'] = join_mimic(core, mimic)
        v = clean(cell)
        if v:
            out[k] = v
    return out


# ══════════════════════════════════════════════════════════════════
# PvZ Tools 阵型字符串
# ══════════════════════════════════════════════════════════════════

def _rs_byte(scene, rake_row=0):
    return ((int(rake_row or 0) & 0x0F) << 4) | (int(scene) & 0x0F)


def encode(array, field_code='PE', rake_row=0):
    """array → 阵型字符串（标准 Base64）"""
    fld = field_code or 'PE'
    n = 54 if fld in SIX_ROW else 45
    buf = bytearray()
    arr = fix_bases(array, fld)
    for i in range(n):
        r, c = i // 9 + 1, i % 9 + 1
        cell = arr.get((r, c)) or {}
        g = 0
        name = cell.get('plant')
        if name:
            core, mimic = split_mimic(name)
            code = plant_code(core)
            if code is not None:
                g |= ((code + 1) & 0x3F) << 10      # P
                if mimic:
                    g |= 1 << 9                     # PI
                if cell.get('awake', True):
                    g |= 1 << 8                     # PA
        base = BASE_BY_NAME.get(cell.get('base') or '')
        if cell.get('grave'):
            base = BASE_GRAVE
        if base:
            g |= (base & 0x3) << 6                  # B
        if cell.get('pumpkin'):
            g |= 1 << 4                             # K
        if cell.get('ladder'):
            g |= 1 << 0                             # L
        buf += struct.pack('<H', g)
    raw = zlib.compress(bytes(buf), 9)
    # ★ RS 那一个字节**也在异或范围内**（RFC1437 §2：整段先异或，再取末字节为 RS）
    out = bytes(b ^ 0x54 for b in raw + bytes([_rs_byte(SCENE.get(fld, 2),
                                                        rake_row)]))
    return base64.b64encode(out).decode('ascii')


def decode(text, field_code=None):
    """阵型字符串 → (array, field_code, rake_row)

    `field_code` 给了就强制用这个场地（字符串里的场景位当参考）。
    """
    s = (text or '').strip()
    if not s:
        raise ValueError('阵型字符串是空的')
    s2 = s.replace('-', '+').replace('_', '/')
    s2 += '=' * (-len(s2) % 4)
    try:
        raw = base64.b64decode(s2, validate=False)
    except Exception as e:                                   # noqa: BLE001
        raise ValueError('不是合法的 Base64：%s' % e)
    if len(raw) < 2:
        raise ValueError('数据太短（至少要有 zlib 头 + RS）')
    body = bytes(b ^ 0x54 for b in raw)
    rs = body[-1]
    scene = rs & 0x0F
    rake = (rs >> 4) & 0x0F
    try:
        data = zlib.decompress(body[:-1])
    except Exception as e:                                   # noqa: BLE001
        raise ValueError('zlib 解压失败（阵型字符串可能被截断）：%s' % e)
    fld = (field_code or SCENE_BY_CODE.get(scene, 'PE')).upper()
    n = 54 if fld in SIX_ROW else 45
    if len(data) < n * 2:
        # 有的字符串按 54 格写、但场景是 5 行 → 就按实际长度推
        n = len(data) // 2
    arr = {}
    for i in range(n):
        g = struct.unpack_from('<H', data, i * 2)[0]
        r, c = i // 9 + 1, i % 9 + 1
        if r > (6 if fld in SIX_ROW else 5):
            continue
        p = (g >> 10) & 0x3F
        cell = blank_cell()
        if p:
            core = code_plant(p - 1)
            if core:
                mimic = bool(g & (1 << 9))
                awake = bool(g & (1 << 8))
                cell['plant'] = join_mimic(core, mimic)
                cell['awake'] = awake
        base = (g >> 6) & 0x3
        if base in (BASE_LILY_B, BASE_POT_B):
            cell['base'] = NAME_BY_BASE[base]
        elif base == BASE_GRAVE:
            cell['grave'] = True
        if g & (1 << 4):
            cell['pumpkin'] = True
        if g & (1 << 0):
            cell['ladder'] = True
        v = clean(cell)
        if v:
            arr[(r, c)] = v
    return arr, fld, rake


def fix_bases(array, field_code='PE'):
    """按场地规则校正底座 / 玉米炮占格（用户 2026-10-22 第二次修订）：

    · 底座只能是这一格该有的那种：水路 → 睡莲、屋顶 → 花盆、草地 → 花盆
      （草地上的睡莲会被清掉）
    · **空地可以不放底座**；但只要有植物 / 南瓜 / 梯子南瓜 / 玉米炮，
      水路与屋顶就必须补上底座
    · **水路不准搭梯**（梯子只能搭在陆地/屋顶的南瓜上）
    · **玉米炮占 1×2**：尾格（(r, c+1)）自动补成"只有底座、不能种东西"的占位格；
      头尾都**不许**套南瓜 / 搭梯
    """
    from . import fields as F
    out = {}
    water_rows = set(F.get(field_code).water)
    for rc, cell in normalize(array).items():
        cell = dict(cell)
        row = rc[0]
        if cell.get('base') and cell['base'] != base_name(field_code, row):
            cell['base'] = None                 # 草地上的睡莲
        if row in water_rows:
            cell['ladder'] = False              # ★ 水路南瓜不准搭梯
        if is_cob(cell):
            cell['pumpkin'] = False
            cell['ladder'] = False
        if base_locked(field_code, row, cell):
            cell['base'] = base_name(field_code, row)
        out[rc] = cell
    # 玉米炮的尾格：占位（只带底座）
    for rc in sorted(out):
        r, c = rc
        if not is_cob(out[rc]) or c + COB_SPAN - 1 > 9:
            continue
        tail = dict(out.get((r, c + 1)) or blank_cell())
        tail.update(plant=None, pumpkin=False, ladder=False, awake=True,
                    grave=False)
        tail['base'] = (BASE_LILY if r in water_rows else
                        (BASE_POT if needs_base(field_code, r) else None))
        v = clean(tail)
        if v:
            out[(r, c + 1)] = v
    return out


# ══════════════════════════════════════════════════════════════════
# PvZ Tools 旧格式（明文 CSV，人类可读）—— 2026-10-22 由用户提供的
# 《PE.电波钟无炮》阵型字符串破解
# ══════════════════════════════════════════════════════════════════
#
# 格式：`钉耙行,条目,条目,...`，每个条目是 6 个空格分隔的字段
#
#     ID 行 列  awake  f5  f6
#
#   · ID 是**十六进制**的 SeedType（`2A` = 42 = 忧郁菇、`10` = 16 = 睡莲、
#     `29` = 41 = 双子花、`2C` = 44 = 冰瓜、`2B` = 43 = 香蒲、`25` = 37 = 保护伞、
#     `A` = 10 = 大喷菇、`E` = 14 = 寒冰菇）
#   · `1E` = 30 = 南瓜壳，单独占一条，跟在主植物后面
#   · `30` = 48 = **梯子**（不是模仿者！破译依据：电波钟的 `30` 恰好只出现在
#     1-2 / 1-3 / 2-2 / 2-3 这四格，正好是四个梯子南瓜的位置）
#   · `awake` = 1/0，只对蘑菇有意义（忧郁菇/大喷菇 = 1，睡着的寒冰菇 = 0）
#   · f5 / f6 在样本里恒为 0（未知位，保留原样以便往返）
#   · 条目顺序 = 「睡莲/花盆 → 主植物 → 南瓜 → 梯子」（= RFC1437 §7 的推荐种植顺序）
#
# ⚠️ 与 Toolkit 格式的 ID 冲突：`30` 在 SeedType 里是「模仿者」，但 PvZ Tools
#    把它用成了梯子。本模块按 PvZ Tools 的用法解释；所以**旧格式不写模仿者主植物**
#    （遇到时退回 Toolkit 格式并提示）。
TOOLS_LADDER = 0x30
TOOLS_PUMPKIN = 0x1E


def encode_tools(array, field_code='PE', rake_row=0):
    """array → PvZ Tools 明文阵型字符串"""
    arr = fix_bases(array, field_code)
    rows = 6 if (field_code or 'PE') in SIX_ROW else 5
    items = []

    def add(code, r, c, awake=0):
        items.append('%X %d %d %d 0 0' % (code, r, c, awake))

    for (r, c) in sorted(arr):
        if r > rows:
            continue
        cell = arr[(r, c)]
        base = cell.get('base')
        if base in (BASE_LILY, BASE_POT):
            add(plant_code(base), r, c)
        name = cell.get('plant')
        if name:
            core, mimic = split_mimic(name)
            code = plant_code(core)
            if mimic or code is None:
                raise ValueError('PvZ Tools 旧格式不支持「%s」——'
                                 '请切到 PvZ Toolkit 格式' % name)
            # awake 只对蘑菇有意义（样本里 忧郁菇/大喷菇 = 1、寒冰菇 = 0，
            # 非蘑菇一律写 0）
            flag = 1 if (core in D.MUSHROOMS
                         and cell.get('awake', True)) else 0
            add(code, r, c, flag)
        if cell.get('pumpkin'):
            add(TOOLS_PUMPKIN, r, c)
        if cell.get('ladder'):
            add(TOOLS_LADDER, r, c)
        if cell.get('grave'):
            # 墓碑：样本里没有，按 Toolkit 的 B=3 思路用 0x1F（31）占位说明
            raise ValueError('PvZ Tools 旧格式无法表达墓碑 —— 请切到 Toolkit 格式')
    return '%d,%s' % (int(rake_row or 0), ','.join(items))


def decode_tools(text, field_code='PE'):
    """PvZ Tools 明文阵型字符串 → (array, field_code, rake_row)"""
    s = (text or '').strip().replace('\r', '').replace('\n', ' ')
    if not s:
        raise ValueError('阵型字符串是空的')
    parts = [p.strip() for p in s.split(',')]
    try:
        rake = int(parts[0] or 0)
    except ValueError:
        raise ValueError('第一项应该是钉耙行号（0 = 没有钉耙），实际是「%s」'
                         % parts[0])
    rows = 6 if (field_code or 'PE') in SIX_ROW else 5
    arr = {}
    for tok in parts[1:]:
        if not tok:
            continue
        f = tok.split()
        if len(f) < 3:
            raise ValueError('条目「%s」至少要 3 个字段（ID 行 列）' % tok)
        try:
            code = int(f[0], 16)
            r, c = int(f[1]), int(f[2])
        except ValueError:
            raise ValueError('条目「%s」的数字读不出来' % tok)
        awake = int(f[3]) if len(f) > 3 and f[3].isdigit() else 1
        if not (1 <= r <= 6 and 1 <= c <= 9) or r > rows:
            continue
        cell = arr.setdefault((r, c), blank_cell())
        if code == TOOLS_LADDER:
            cell['ladder'] = True
            cell['pumpkin'] = cell['pumpkin'] or False
            continue
        if code == TOOLS_PUMPKIN:
            cell['pumpkin'] = True
            continue
        name = code_plant(code)
        if name is None:
            continue
        if name in (BASE_LILY, BASE_POT):
            cell['base'] = name
            continue
        cell['plant'] = name
        # awake 只对蘑菇有意义；非蘑菇一律视为醒着（样本里它们都写 0）
        cell['awake'] = bool(awake) if name in D.MUSHROOMS else True
    out = {}
    for rc, cell in arr.items():
        v = clean(cell)
        if v:
            out[rc] = v
    return out, (field_code or 'PE'), rake


# 格式代号 ↔ 编解码函数（设置界面里选的就是这个 key）
FORMATS = {
    'tools': dict(label='PvZ Tools（旧，明文可读）',
                  note='明文的「ID 行 列 …」列表，人能直接读懂；'
                       '不支持模仿者主植物与墓碑',
                  encode=encode_tools, decode=decode_tools),
    'toolkit': dict(label='PvZ Toolkit（新，Base64+zlib）',
                    note='RFC1437：Base64 → 异或 0x54 → zlib + RS 字节；'
                         '支持模仿者 / 咖啡豆 / 墓碑等全部信息',
                    encode=encode, decode=decode),
}
DEFAULT_FORMAT = 'toolkit'


def encode_any(array, field_code='PE', fmt=None, rake_row=0):
    f = FORMATS.get(fmt or DEFAULT_FORMAT) or FORMATS[DEFAULT_FORMAT]
    return f['encode'](array, field_code, rake_row)


def decode_any(text, fmt=None, field_code=None):
    """自动认格式：带逗号的是旧格式，否则是新格式"""
    f = FORMATS.get(fmt or DEFAULT_FORMAT) or FORMATS[DEFAULT_FORMAT]
    if fmt is None and ',' in (text or ''):
        f = FORMATS['tools']
    if f is FORMATS['tools']:
        return f['decode'](text, field_code or 'PE')
    return f['decode'](text, field_code)


# ══════════════════════════════════════════════════════════════════
# 给界面用的清单
# ══════════════════════════════════════════════════════════════════

def catalog():
    """阵容布置界面要用的：可选植物、蘑菇名单、基座规则、代号码表"""
    from . import fields as F
    picks = [p for p in MI.PLANT_CODES if p not in GRID_HIDDEN]
    return dict(
        plants=picks,
        mimic=MIMIC,
        hidden=list(GRID_HIDDEN),
        cob=COB,
        cob_span=COB_SPAN,
        mushrooms=sorted(D.MUSHROOMS),
        base_for={f.code: dict(water=list(f.water),
                               base=f.base_plant, rows=f.rows)
                  for f in F.all_fields()},
        codes=[dict(code=i + 1, name=p, modeled=p in
                    {x['name'] for x in MI.PLANTS_MODEL})
               for i, p in enumerate(MI.PLANT_CODES)],
        scenes=SCENE,
        formats=[dict(id=k, label=v['label'], note=v['note'])
                 for k, v in FORMATS.items()],
        default_format=DEFAULT_FORMAT,
    )


def to_engine(array):
    """内部 array → 引擎 `Sim(array=...)` 的格式（key 用元组、值用 plant/pumpkin/ladder）

    ★ 「装着睡着的蘑菇的格子」在引擎里就是 `plant + awake=False`，
      阵图上写 `{"plant": "寒冰菇", "awake": false}` 即可。
    """
    out = {}
    for rc, cell in normalize(array).items():
        name = cell.get('plant')
        out[rc] = dict(plant=name,
                       awake=(None if cell.get('awake') is None
                              else bool(cell.get('awake'))),
                       pumpkin=bool(cell.get('pumpkin')),
                       ladder=bool(cell.get('ladder')),
                       # ★ 2026-10-23 用户：阵容布置可以给格子**贴 core 标签**
                       #   → 这一格丢了就按"崩阵"处理（不再只看植物名）
                       core=bool(cell.get('core')))
    return out


from_engine = to_engine
