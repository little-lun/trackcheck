# -*- coding: utf-8 -*-
"""
i18n.py —— 界面语言（中文 / English）

★ 2026-10-24 用户口径：
  ① **PVZ 原版的东西一律用原版英文名**（植物、僵尸、场地…）。
     例：小丑 = **Jack-in-the-Box Zombie**（不是 "Joker Zombie"）。
  ② **中文社区独创、本来就是字母的术语一律不变**：
     `P / A / A' / I / N` 等轨道符号、`io` 等术语、`DE/NE/PE/FE/RE` 等场地、
     `C4io / P4 / N6s` 等节奏 —— 只在帮助页的「语言说明 / Language notes」里解释。
  ③ 其余中文原生词按用户 2026-10-24 拍板的口径译（见 `WORDS` 里的注释）。

实现方式：**词典替换**。
  · `localize(text)` 先替换长句（`PHRASES`），再替换词条（`WORDS`，按长度降序），
    只在"呈现层"调用 —— 静态 HTML、报告 HTML、帮助正文。
  · 内部标识符（植物名做 key、阵解 JSON 里的字段）**绝不翻译**，
    否则前后端对不上。所以英文名只出现在显示位置。

为什么不做 gettext：这个项目的界面文字是拼在一大坨 HTML/JS 里的，
逐条 `t(...)` 包装要改几千处、且 JS 里还有"用中文串做比较"的逻辑。
统一在**输出前**做一次替换，风险最小、覆盖面最大。
"""

import json
import os

# ---------------------------------------------------------------- 语言状态
LANGS = [('zh', '中文'), ('en', 'English')]
LANG = 'zh'
_SET = os.path.join(os.path.expanduser('~'), '.trackcheck-settings.json')


def _load():
    global LANG
    try:
        with open(_SET, encoding='utf-8') as f:
            v = (json.load(f) or {}).get('lang')
        if v in dict(LANGS):
            LANG = v
    except Exception:
        pass


def set_lang(v):
    global LANG
    if v not in dict(LANGS):
        return LANG
    LANG = v
    try:
        d = {}
        if os.path.exists(_SET):
            with open(_SET, encoding='utf-8') as f:
                d = json.load(f) or {}
        d['lang'] = v
        with open(_SET, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass
    return LANG


def lang():
    return LANG


def is_en():
    return LANG == 'en'


_load()


# ---------------------------------------------------------------- 词条
# 官方英文名（plants / zombies）—— 全部来自 Almanac / wiki 的原版名
WORDS = {
    # ---- 轨道理论（用户 2026-10-24 定：直译）
    '轨道': 'Track', '运算量': 'Operation Count', '阵解': 'Solution',
    '阵型': 'Formation', '阵型字符串': 'formation string',
    '轨道语言': 'track language', '轨道简式': 'shorthand track',
    '波长': 'wavelength', '波长串': 'wavelength list', '节奏': 'rhythm',
    '节奏型': 'rhythm type', '节奏体系': 'rhythm system',
    '起手': 'Opening', '旗波': 'Flag Wave', '收尾': 'Finisher',
    '常规波': 'regular wave', '旗波重置': 'flag-wave reset',
    # ★ 冰杀蹦极：用户口径「通过冰冻延长输出窗口击杀蹦极」，建议用不定式形式
    '冰杀蹦极': 'Freeze-to-kill Bungee',
    # ---- 打法（用户 2026-10-24 定）
    '控丑': 'Explosion Prevention',      # = 阻止小丑爆炸
    '救场': 'Rescue', '垫材循环': 'padding loop', '存冰量': 'ice bank',
    '炮位': 'cob position', '运阵': 'running the formation',
    '出怪': 'spawn', '出怪列表': 'spawn list', '出怪沙盘': 'Spawn Sandbox',
    '选卡': 'Seed selection', '卡槽': 'seed slot', '铺种': 'planting',
    '补种': 'replant', '南瓜耐久': 'pumpkin durability', '冰道': 'ice trail',
    '核坑': 'Doom crater', '坑位': 'crater slot', '弹坑': 'crater',
    '推车': 'lawn mower', '小推车': 'lawn mower', '崩阵': 'formation collapse',
    '研磨': 'grind',
    # ---- 四档难度（用户 2026-10-24 定：直译）
    '慢速': 'Slow', '变速': 'Variable-speed', '快速': 'Fast', '极速': 'Very-fast',
    '慢速关': 'Slow run', '变速关': 'Variable-speed run',
    # ---- 出怪分组 / 备注（META 载荷用 `tr()` 精确查）
    '基础': 'Basic', '中级': 'Mid', '特殊': 'Special', '巨人': 'Giants',
    '中速': 'Medium',
    '仅旗帜波': 'Flag wave only', '格式': 'Format',
    # ---- 节奏表里的短名（`邻D6` = 相邻的 D6；`对/间` = 配对/交错）
    '邻': 'adjacent ', '对': 'paired ', '间': 'interleaved ',
    # ---- 波次角色 / 选卡简称（阵解编辑器里的标签）
    '常规': 'Regular', '起手': 'Opening', '收尾': 'Finisher',
    '核': 'Nuke', '冰': 'Ice', '模仿核': 'Imitator nuke',
    '模仿冰': 'Imitator ice', '垫材': 'Padding',
    # ---- 界面通用
    '设置': 'Settings', '帮助': 'Help', '关于': 'About',
    '阵容布置': 'Formation', '阵解编辑': 'Solution editor',
    '运行与报告': 'Run & report', '导入': 'Import', '导出': 'Export',
    '复制': 'Copy', '清空': 'Clear', '删除': 'Delete', '保存': 'Save',
    '取消': 'Cancel', '确定': 'OK', '关闭': 'Close', '添加': 'Add',
    '名称': 'Name', '次数': 'Runs', '结果': 'Result', '等级': 'Level',
    '种子': 'Seed', '通过': 'pass', '崩': 'fail', '可无尽': 'Endless-capable',
    '不可无尽': 'Not endless-capable', '跑完': 'finished',
    '常规波长': 'Regular wavelength', '植物损失': 'Plant losses',
    '冰车碾压': 'Zomboni crushes', '补南瓜': 'Pumpkin repairs',
    '逐种子明细': 'Per-seed details', '当前种子': 'Current seed',
    '语言': 'Language', '语言说明': 'Language notes',
    '中文': 'Chinese', '英文': 'English',
    '全程': 'Full', '部分': 'Partial', '仅提示': 'Hint only',
    '仅数据': 'Data only', '一次性': 'One-shot', '未建模': 'Not modeled',
    '仅坐标': 'Coords only',
}

# 句式级（整句替换，优先级最高）—— 帮助页 / 设置页这类成段文字
PHRASES = {
    # ---- 设置页「阵型字符串格式」两个选项（整句，别拆）
    'PvZ Tools（旧，明文可读）': 'PvZ Tools (old, plain text)',
    '明文的「ID 行 列 …」列表，人能直接读懂；不支持模仿者主植物与墓碑':
        'A plain-text “ID row column …” list that humans can read; '
        'Imitator main plants and gravestones are not supported',
    'PvZ Toolkit（新，Base64+zlib）': 'PvZ Toolkit (new, Base64+zlib)',
    'RFC1437：Base64 → 异或 0x54 → zlib + RS 字节；支持模仿者 / 咖啡豆 / 墓碑等全部信息':
        'RFC1437: Base64 → XOR 0x54 → zlib + RS bytes; carries everything, '
        'including Imitator / Coffee Bean / gravestones',
    # ---- 阵解编辑页那两行长提示（整句，别拆）
    '电波钟无炮': 'Radio Clock No Cobs',
    '种咖啡豆': 'Plant a Coffee Bean', '种寒冰菇': 'Plant an Ice-shroom',
    '种毁灭菇': 'Plant a Doom-shroom', '种樱桃': 'Plant a Cherry Bomb',
    '种辣椒': 'Plant a Jalapeno', '种窝瓜': 'Plant a Squash',
    '种小喷菇': 'Plant a Puff-shroom', '种花盆': 'Plant a Flower Pot',
    '种南瓜': 'Plant a Pumpkin', '种大喷菇': 'Plant a Fume-shroom',
    '种忧郁菇': 'Plant a Gloom-shroom', '种冰瓜': 'Plant a Winter Melon',
    '种香蒲': 'Plant a Cattail', '种保护伞': 'Plant an Umbrella Leaf',
    '种地刺': 'Plant a Spikeweed', '种地刺王': 'Plant a Spikerock',
    '种大蒜': 'Plant a Garlic', '种火炬树桩': 'Plant a Torchwood',
    '种三叶草': 'Plant a Blover', '种磁力菇': 'Plant a Magnet-shroom',
    '快捷布置只把「做什么」铺进常规波（20 波全填），落点 / 时机 / 兜底留给你填。':
        'Quick layout only fills “what to do” into the regular waves (all 20). '
        'Landing points, timings and fallbacks are left to you.',
    '<code>~</code> 两套节奏摆动；波长串写 <code>(9,9,9,9)</code> 或 <code>(9|9|9|9)</code>。':
        '<code>~</code> alternates two rhythms; the wavelength list takes '
        '<code>(9,9,9,9)</code> or <code>(9|9|9|9)</code>.',
    '格式 <code>[场地].名字</code>，<code>[场地].</code> 由 app 自动生成，只填后面的名字':
        'Format <code>[field].name</code> — the <code>[field].</code> prefix is '
        'generated automatically, type only the name',
    # ---- 静态标记里的成段提示（中间夹 <code>/<b>，拆开翻会把语序打乱）
    '''格式在「设置」里切：**PvZ Tools**（旧版，明文 <code>ID 行 列 …</code>，人能读懂，
      不支持模仿者/墓碑）与 **PvZ Toolkit**（新版，Base64 → 异或 0x54 → zlib + RS）。
      导入时会自动认出是哪一种。''':
        '''Switch the format in Settings: **PvZ Tools** (old format, plain text
      <code>ID row column …</code>, readable, no Imitator / gravestone) and
      **PvZ Toolkit** (new format, Base64 → XOR 0x54 → zlib + RS).
      The importer works out which one it is.''',
    '''下面所有"种什么"的选项都只从这 10 张里出。唤醒存冰 = 在某格<b>种咖啡豆</b>；
      补存冰 = 在某格<b>种寒冰菇</b>。''':
        '''Every “what to plant” option below comes only from these 10 cards. '
      'Wake an ice bank = plant a <b>Coffee Bean</b> on that cell; '
      'refill the ice bank = plant an <b>Ice-shroom</b> on that cell.''',
    '''（持续判一个条件，成立就做。
        例：冰卡一好就补在空着的永久存冰位）''':
        '''(evaluates a condition continuously; when it holds, act.
        E.g. refill the empty permanent ice bank as soon as the ice card is ready)''',
    '固定波长的阵，起手从连续节奏最快的点开始':
        'On a fixed-wavelength formation the opening starts at the fastest '
        'consecutive point of the rhythm',
    # ---- 拼出来的小片段（`'种' + 卡名`）
    '唤醒存冰 = 在某格': 'Wake an ice bank = on a cell ',
    '补存冰 = 在某格': 'Refill the ice bank = on a cell ',
    'PVZ 初代（1.0.0.1051 EN）生存无尽研究工具：布阵 → 出怪 → 阵解 → 跑运阵 → 出报告':
        'A research tool for PvZ 1 (1.0.0.1051 EN) Survival Endless: '
        'build the formation → pick spawns → write the solution → run → report',
    '① 阵容布置': '① Formation',
    '② 出怪沙盘': '② Spawn Sandbox',
    '③ 阵解编辑': '③ Solution editor',
    '④ 运行与报告': '④ Run & report',
    '帮助': 'Help',
    '设置 · 节奏命名方案': 'Settings · Rhythm naming',
    '设置 · 阵型字符串格式': 'Settings · Formation string format',
    '设置 · 轨道简写 / 复写': 'Settings · Track shorthand / pair form',
    '模型清单 · 植物': 'Model list · Plants',
    '模型清单 · 僵尸': 'Model list · Zombies',
    '模型清单 · 场地': 'Model list · Fields',
    '关于': 'About',
    '1. 场地 · 阵型名': '1. Field · Formation name',
    '2. 阵型（点格子编辑）': '2. Formation (click a cell to edit)',
    '3. 编辑格': '3. Cell editor',
    '4. 阵型字符串': '4. Formation string',
    '1. 出怪（勾选允许出现的僵尸）': '1. Spawns (tick the zombies allowed to appear)',
    '2. 待模拟列表': '2. Queue',
    '场地': 'Field', '阵型名': 'Formation name',
    '左键选格 → 下面编辑；同一行/列可以拖动框选（Shift 连选）':
        'Left-click a cell → edit below; drag along a row/column to select '
        '(hold Shift to extend)',
    '整行套南瓜': 'Pumpkin on row', '整行搭梯': 'Ladder on row',
    '> 墓碑</label>': '> Gravestone</label>',
    '（有植物/南瓜/玉米炮 → 必须有）': ' (plant / Pumpkin / Cob Cannon present - required)',
    '（空地可以先不放）': ' (an empty cell can stay bare)',
    '（草地上只能放花盆）': ' (on lawn only a Flower Pot can go here)',
    '（水路南瓜不能搭梯）': ' (a Pumpkin on water cannot carry a Ladder)',
    '（玉米炮不能搭）': ' (not on a Cob Cannon)',

    '清空阵型': 'Clear formation',
    '粘贴阵型字符串后点「导入」': 'Paste a formation string, then click Import',
    '推荐组合：': 'Presets: ', '全不选': 'Select none',
    '蹦极只在旗帜波出现；其余波会自动补普通':
        'Bungee Zombies only appear in flag waves; other waves auto-fill with Zombies',
    '给这组出怪起个名字': 'Name this spawn set',
    '模拟次数': 'Runs', '＋ 加入列表': '+ Add to queue',
    '导入 JSON': 'Import JSON', '导出 JSON': 'Export JSON', '退出程序': 'Quit',
    '（可以加多组，出怪列表可以存成 JSON 反复用）':
        '(You can queue several sets; spawn lists can be saved as JSON and reused)',
    '还没有排队的组合': 'Queue is empty',
    '加完出怪 → 去「③ 阵解编辑」配阵解并与出怪配对 → 再到「④ 运行与报告」开跑。':
        'After adding spawns → go to ③ Solution editor to write a solution and '
        'pair it with a spawn set → then ④ Run & report to start.',
    '（对称操作写一个还是一对）': '(write symmetric ops as one or as a pair)',
    '（哪些植物参与模拟、哪些只是占格、哪些还没建模）':
        '(which plants are simulated, which only occupy a cell, which are not modeled)',
    '格式在「设置」里切：': 'Switch the format in Settings: ',
    # ---- ③ 阵解编辑 / ①②④ 页面的其余文案（2026-10-24 第二批）
    '+ 加资源': '+ Add resource', '用哪套阵解': 'Which solution',
    '本路僵尸数': 'Zombies in this lane', '场上僵尸数': 'Zombies on field',
    '选中的候选': 'Selected candidate', '核坑有余量': 'Doom crater available',
    '未命名阵解': 'Untitled solution', '命名方案：': 'Naming scheme: ',
    '读取失败：': 'Load failed: ', '保存失败：': 'Save failed: ',
    '① 阵容布置': '① Formation', '② 出怪沙盘': '② Spawn Sandbox',
    '③ 阵解编辑': '③ Solution editor', '④ 运行与报告': '④ Run & report',
    '＋ 加入列表': '+ Add to queue', '⏻ 退出程序': '⏻ Quit',
    '▶ 开始模拟': '▶ Start', '自动判定节奏': 'Auto-detected rhythm',
    '（当前格式：': '(current format: ', '还没有字符串': 'No string yet',
    '⤓ 导出本套': '⤓ Export this', '启用简化救场': 'Enable simple rescue',
    '+ 再兜一层': '+ Add a fallback layer',
    '本波剩余血量': 'Wave HP remaining', '炮已装填门数': 'Cob Cannons loaded',
    '· 空存冰位': '· empty ice slot', '前场临时冰位': 'front temporary ice slot',
    '[场地].名字': '[field].name', '⤓ 生成字符串': '⤓ Generate string',
    '草地不能放睡莲': 'Lily Pad cannot go on lawn',
    '简化模型等价于': 'The simplified model is equivalent to ',
    '清空整个阵型？': 'Clear the whole formation?',
    '先勾几位僵尸吧': 'Tick some zombies first',
    '快速关（预设）': 'Fast (preset)', '✓ 没发现问题': '✓ No problems found',
    '（打开已保存）': '(open saved)', '真正打出的动作': 'Operations actually fired',
    '本路最靠前 x': 'Front-most x in this lane',
    '至少留一套阵解': 'Keep at least one solution',
    '删除这套阵解？': 'Delete this solution?',
    '，并按波长定时': ', timed by the wavelength list',
    '配置里没有阵解': 'No solution in this config',
    '还没有排队的组合': 'Queue is empty',
    '玉米炮占 1×2': 'Cob Cannon occupies 1×2',
    '出错（见控制台）': 'Error (see console)',
    '（先点一个格子）': '(click a cell first)',
    '（蘑菇才有睡眠）': '(only mushrooms sleep)',
    '（玉米炮不能套）': '(Cob Cannon cannot take a Pumpkin)',
    '（玉米炮不能搭）': '(Cob Cannon cannot take a Ladder)',
    '不会出现这种僵尸': 'This zombie cannot appear here',
    '模拟中…… 还有': 'Running… remaining ',
    '（该系暂无预设）': '(no presets in this family)',
    '不给（默认策略）': 'None (default policy)',
    '空着的永久存冰位': 'empty permanent ice slot',
    '没有可撤销的操作': 'Nothing to undo',
    '贴 core 标签': 'Tag as core',
    '（阵解页还没加载）': '(solution page not loaded yet)',
    '（空地可以先不放）': '(empty cells can be left blank)',
    '阵解编辑器还没就绪': 'Solution editor is not ready',
    '+ 加一条全场判定': '+ Add a global check',
    '+ 加一条救场规则': '+ Add a rescue rule',
    '还没有全场判定规则': 'No global checks yet',
    '还没有要保护的目标': 'No protected targets yet',
    '+ 加要保护的植物': '+ Add a plant to protect',
    '先勾选要复制的波次': 'Tick the waves to copy first',
    '（水路南瓜不能搭梯）': '(Pumpkin on water cannot take a Ladder)',
    '（草地上只能放花盆）': '(only a Flower Pot can go on lawn in this field)',
    '先把阵型字符串粘进来': 'Paste a formation string first',
    '生成 PDF 失败：': 'PDF generation failed: ',
    '指定爆心（可带小数）': 'Explosion centre (decimals allowed)',
    '复制失败，请手动选中': 'Copy failed — select it manually',
    '不是合法 JSON：': 'Not valid JSON: ',
    '在上面点一格开始编辑。': 'Click a cell above to start editing.',
    '已提交，后台开始跑……': 'Submitted — running in the background…',
    '旗波：快捷布置不会动它': 'Flag wave: quick layout leaves it alone',
    '+ 加一个候选（兜底）': '+ Add a candidate (fallback)',
    '（留空 = 一直循环）': '(blank = repeat forever)',
    '已装填完毕的玉米炮门数': 'Cob Cannons fully loaded',
    '（不绑阵解 · 空轨道）': '(no solution bound · empty track)',
    '（夜场锁定：蘑菇不会睡）': '(night field: mushrooms never sleep)',
    '阵解 JSON 格式说明': 'Solution JSON format spec',
    '存冰数（场上有几颗寒冰菇）': 'Ice count (Ice-shrooms on field)',
    '没填波长串 → 时机留空。': 'No wavelength list → timing left blank.',
    '—— 落点还空着，接着填吧': '— positions are still empty, fill them in',
    '不是合法的阵解 JSON：': 'Not a valid solution JSON: ',
    '（第 6 行的配置会被忽略）': '(the 6th row setting is ignored)',
    '已按底座 / 玉米炮规则校正': 'Corrected by base / Cob Cannon rules',
    '本路最靠前僵尸的 x（px）': 'x of the front-most zombie (px)',
    '出怪列表 JSON 格式说明': 'Spawn list JSON format spec',
    '全场配置 JSON 格式说明': 'Full config JSON format spec',
    '先点一个格子，按钮对那一行生效': 'Click a cell first; the button applies to that row',
    '勾选当前场地允许出现的所有僵尸':
        'Tick every zombie allowed on this field',
    '解释见「帮助 → 语言说明」。': 'See Help → Language notes.',
    '载入示例会新增一套阵解，继续？':
        'Loading the example will add a new solution. Continue?',
    '先勾选波次（左边每行的小方框）':
        'Tick some waves first (checkbox on each row on the left)',
    '1. 出怪（勾选允许出现的僵尸）':
        '1. Spawns (tick the zombies allowed to appear)',
    '列表和勾选都是空的，没东西可导出': 'Both the list and the ticks are empty',
    '基本信息 · 节奏 · 快捷布置': 'Basics · Rhythm · Quick layout',
    '剪贴板是空的（先勾选并「复制」）': 'Clipboard is empty (tick waves and Copy first)',
    '浏览器拦了新窗口，请允许弹窗后重试':
        'The browser blocked the new window — allow pop-ups and retry',
    '条件不成立就整组跳过、试下一个候选':
        'If the condition fails, skip the whole group and try the next candidate',
    '由 app 自动生成，只填后面的名字':
        'is generated by the app; just type the name after it',
}


# ---------------------------------------------------------------- 名字表
# ★★ 名字既是**显示文本**，也可能是**回传给服务器的标识符**
#   （选卡 deck、阵型 array、阵解里的 op 名都用中文名当 key）。
#   所以它们单独一张表：
#     · 报告（纯展示，不会回传）→ 用 `localize(text, names=True)` 翻译；
#     · 界面下拉框 → 只换显示文本（`meta_payload` 的 `enNames`），
#       `value` 保持中文。
#   页面 HTML/JS 本地化时 **names=False**，否则 `模仿者:` 这类前缀
#   会被翻掉、前端正则匹配不上，选卡/模仿逻辑就崩了。
NAMES = {
    # ---- 植物（官方名）
    '忧郁菇': 'Gloom-shroom', '大喷菇': 'Fume-shroom', '冰瓜': 'Winter Melon',
    '香蒲': 'Cattail', '双子花': 'Twin Sunflower', '双子向日葵': 'Twin Sunflower',
    '荷叶': 'Lily Pad', '睡莲': 'Lily Pad', '保护伞': 'Umbrella Leaf',
    '玉米炮': 'Cob Cannon', '大蒜': 'Garlic', '寒冰菇': 'Ice-shroom',
    '毁灭菇': 'Doom-shroom', '墓碑吞噬者': 'Grave Buster', '火炬树桩': 'Torchwood',
    '地刺王': 'Spikerock', '地刺': 'Spikeweed', '高坚果': 'Tall-nut',
    '坚果': 'Wall-nut', '杨桃': 'Starfruit', '缠绕海草': 'Tangle Kelp',
    '三叶草': 'Blover', '分裂射手': 'Split Pea', '双向射手': 'Split Pea',
    '机枪射手': 'Gatling Pea', '磁力菇': 'Magnet-shroom', '向日葵': 'Sunflower',
    '阳光菇': 'Sun-shroom', '小喷菇': 'Puff-shroom', '花盆': 'Flower Pot',
    '樱桃': 'Cherry Bomb', '樱桃炸弹': 'Cherry Bomb', '辣椒': 'Jalapeno',
    '窝瓜': 'Squash', '南瓜': 'Pumpkin', '咖啡豆': 'Coffee Bean',
    '土豆雷': 'Potato Mine', '大嘴花': 'Chomper', '胆小菇': 'Scaredy-shroom',
    '魅惑菇': 'Hypno-shroom', '寒冰射手': 'Snow Pea', '豌豆射手': 'Peashooter',
    '双发射手': 'Repeater', '三线射手': 'Threepeater', '仙人掌': 'Cactus',
    '星星果': 'Starfruit', '卷心菜投手': 'Cabbage-pult',
    '玉米投手': 'Kernel-pult', '西瓜投手': 'Melon-pult', '金盏花': 'Marigold',
    '吸金磁': 'Gold Magnet', '模仿者': 'Imitator', '海蘑菇': 'Sea-shroom',
    '路灯花': 'Plantern', '存冰': 'Ice bank', '垫材': 'Padding',
    '垫材2': 'Padding 2', '垫材3': 'Padding 3', '垫材4': 'Padding 4',
    # ---- 僵尸（官方名）
    '红眼': 'Giga-gargantuar', '白眼': 'Gargantuar', '小鬼': 'Imp',
    '普通': 'Zombie', '旗帜': 'Flag Zombie', '路障': 'Conehead Zombie',
    '撑杆': 'Pole Vaulting Zombie', '铁桶': 'Buckethead Zombie',
    '读报': 'Newspaper Zombie', '铁门': 'Screen Door Zombie',
    '橄榄': 'Football Zombie', '舞王': 'Dancing Zombie',
    '伴舞': 'Backup Dancer', '潜水': 'Snorkel Zombie', '冰车': 'Zomboni',
    '海豚': 'Dolphin Rider Zombie', '小丑': 'Jack-in-the-Box Zombie',
    '气球': 'Balloon Zombie', '矿工': 'Digger Zombie', '跳跳': 'Pogo Zombie',
    '蹦极': 'Bungee Zombie', '扶梯': 'Ladder Zombie', '梯子': 'Ladder Zombie',
    '投篮': 'Catapult Zombie', '雪人': 'Zombie Yeti',
    '雪橇': 'Zombie Bobsled Team', '鸭子': 'Ducky Tube Zombie', '僵博': 'Zombot',
}

# ---------------------------------------------------------------- 报表标签
# ★ 报告里出现的**短标签**（表格头、KPI、分节标题）。整条匹配，避免误伤正文。
LABELS = {
    # ---- 分级 / 问题表
    '等级': 'Level', '现象': 'Symptom', '判据 / 归因': 'Criterion / attribution',
    '怎么处理': 'What to do', '数值': 'Value', '说明': 'Note',
    '问题': 'Problem', '修法': 'Fix', '根因 / 说明': 'Cause / note',
    '根因': 'Cause', '含义': 'Meaning', '典型现象': 'Typical symptom',
    '结论': 'Conclusion', '严谨': 'Strict',
    # ---- KPI
    '常规波长': 'Regular wavelength', '偏差': 'Deviation',
    '含收尾段': 'Incl. finisher', '跑完': 'Finished',
    '减速覆盖': 'Slow coverage', '输出': 'Output',
    '阳光结余（8k 起）': 'Sun balance (from 8k)',
    '阳光结余（8000 起）': 'Sun balance (from 8000)',
    '南瓜损耗': 'Pumpkin wear', '存冰结余': 'Ice bank left',
    '冰车碾压': 'Zomboni crushes', '核/局': 'Nukes / run',
    '炸率(2/5路)': 'Boom rate (lanes 2/5)', '最高等级': 'Worst level',
    '南瓜存活': 'Pumpkins alive', '补南瓜': 'Pumpkin repairs',
    '植物损失': 'Plant losses', '结束卡槽': 'End seed slots',
    '零偏离': 'Zero deviation', '汇总': 'Summary',
    # ---- 总览 / 分节
    '总览': 'Overview',
    '本轮修了什么（v5.7）': 'What changed in this round (v5.7)',
    '分级口径（脱离设计怎么判）': 'Level definitions (how deviation is graded)',
    '逐档代表局（每档取第一个跑完的）':
        'Representative run per tier (first finished run of each)',
    '脱离设计清单（分级）': 'Deviation list (graded)',
    '轨道执行表（20 波）': 'Track execution (20 waves)',
    '结构位补种台账': 'Structure replant ledger',
    '大蒜台账（按阵解里实际种下的位置）':
        'Garlic ledger (by the cell actually planted from the solution)',
    '按阵解里排的补种动作统计': 'Counted from replant actions written in the solution',
    '补种次数': 'Replant count', '换行次数': 'Lane swaps',
    '啃碎次数': 'Chews', '来源': 'Source', '去向': 'Destination',
    '压力转移': 'Pressure shift', '被车碾': 'Crushed by Zomboni',
    '被压就补，不额外操作': 'Replant when crushed; no extra action',
    # ---- 逐波表
    '波': 'Wave', '角色': 'Role', '操作（不含补存冰）':
        'Operations (excluding ice-bank refills)',
    '生效时刻': 'Effective time', '出怪': 'Spawns', '波长': 'Wavelength',
    '本波': 'This wave', '卡槽': 'Seed slots', '阵线': 'Front line',
    '最深处': 'Deepest', '僵尸/减速': 'Zombies / slowed', '峰值': 'Peak',
    '阳光': 'Sun', '控丑': 'Explosion Prevention', '计划': 'Planned',
    '用卡': 'Cards used', '机会性': 'Opportunistic',
    # ---- 小丑
    '路': 'Lane', '早爆丑': 'Early-boom JitB', '晚爆丑': 'Late-boom JitB',
    '本档不出小丑。': 'This tier has no Jack-in-the-Box Zombies.',
    '水路不出小丑': 'No Jack-in-the-Box Zombies on water lanes',
    # ---- 投篮 / 蹦极
    '被打的底线植物': 'Backline plant hit', '命中次数': 'Hits',
    '本档的投篮车': 'Catapults in this tier',
    '全部在第一次投掷前被击杀': 'All killed before the first throw',
    '投篮对策有效': 'Catapult answer works',
    '本档不出蹦极。': 'This tier has no Bungee Zombies.',
    '不需要为蹦极做额外操作': 'No extra action needed for bungee',
    '蹦极': 'Bungee', '暴露的目标': 'Exposed targets',
    '冰杀救下': 'Saved by freeze', '炮炸救下': 'Saved by cob',
    '被偷': 'Stolen',
    # ---- 阵型状态
    '格': 'Cell', '阵型里': 'In formation', '结束状态': 'End state',
    '血量': 'HP', '南瓜': 'Pumpkin', '档': 'Tier', '录像': 'Video',
    '这一局没有阵型信息。': 'No formation data for this run.',
    '没了': 'gone', '南瓜没了': 'pumpkin gone',
    # ---- ③ 阵解编辑页（planui.MARKUP）
    '阵解库 · 多套阵解': 'Solution library · multiple solutions',
    '＋ 新建': '+ New', '⎘ 复制': '⎘ Copy', '✕ 删除': '✕ Delete',
    '⌸ 保存': '⌸ Save', '⤓ 导出本套': '⤓ Export this', '⤒ 导入': '⤒ Import',
    '已保存': 'Saved', '⤓ 导出全场配置': '⤓ Export full config',
    '⤒ 导入全场配置': '⤒ Import full config', '＋ 空模板': '+ Blank template',
    '基本信息 · 节奏 · 快捷布置': 'Basics · Rhythm · Quick layout',
    '（i = 刷怪机制说明）': '(i = how spawning works)',
    '（i = 建模原则：结果导向 / 哪些时延不计）':
        '(i = modeling principle: result-oriented / which delays are ignored)',
    '名称': 'Name', '节奏系': 'Rhythm family', '节奏型': 'Rhythm type',
    '轨道': 'Track', '波长串': 'Wavelength list', '起手拍': 'Opening beat',
    '⚡ 快捷布置阵解': '⚡ Quick layout', '✓ 校验': '✓ Validate',
    '快捷布置只把「做什么」铺进常规波（20 波全填），落点 / 时机 / 兜底留给你填。':
        'Quick layout only fills “what to do” into the regular waves (all 20 waves); '
        'positions / timing / fallbacks are left to you.',
    '轨道认得': 'The track understands', '波次、': 'next wave,',
    '同一波的第二个时机、': 'a second group in the same wave,',
    '上下半场、': 'upper / lower half,', '两套节奏摆动；波长串写':
        'alternating two rhythms; the wavelength list takes',
    '选卡 · 10 个卡槽': 'Seed selection · 10 slots',
    '表层阵解 · 轨道': 'Surface solution · Track',
    '（每波一行；行内是候选兜底链，行首积木 = 刷怪即刻生效）':
        '(one row per wave; a row is a fallback chain of candidates, '
        'the first block fires immediately on spawn)',
    '批量：': 'Batch: ', '全选': 'Select all', '反选': 'Invert',
    '清空勾选': 'Clear ticks', '← 整体前移一位': '← Shift all back one',
    '整体后移一位 →': 'Shift all forward one →',
    '⎗ 粘贴': '⎗ Paste', '⌫ 清空': '⌫ Clear', '↶ 撤销': '↶ Undo',
    '全场判定': 'Global checks',
    '（持续判一个条件，成立就做。例：冰卡一好就补在空着的永久存冰位）':
        '(evaluate a condition continuously; when true, act. '
        'E.g. refill an empty permanent ice slot as soon as the ice card is ready)',
    '+ 加一条全场判定': '+ Add a global check',
    '简化救场': 'Simple rescue',
    '（你只交资源 + 排优先级，打什么、打哪一路由内部决定）':
        '(you only give resources + priorities; what to use and which lane is decided internally)',
    '详细救场': 'Detailed rescue',
    '（事件 → 多层兜底：上一层没落地就试下一层）':
        '(event → multi-layer fallback: try the next layer if the previous did not fire)',
    '+ 加一条救场规则': '+ Add a rescue rule',
    '阵解 ↔ 出怪 匹配': 'Solution ↔ spawn pairing',
    '（左边是出怪沙盘里的列表，右边选它用哪套阵解）':
        '(left = the queue from Spawn Sandbox, right = which solution it uses)',
    '出怪列表还是空的': 'The spawn queue is still empty',
    '校验': 'Validate',
    '点「校验」看看这份阵解有没有明显问题':
        'Click “Validate” to check this solution for obvious problems',
    'JSON 格式说明': 'JSON format spec', '复制全文': 'Copy all',
    '下载 .md': 'Download .md',
}


def _ctx(s, k, v):
    """**只在"标签内容"位置**替换短词（`>词<`、`>词 `、` 词<`、`"词"`）。

    ★ 2026-10-24：不能对 1~2 字的词做无脑替换 —— 会把专有名词吃坏：
      `电波钟无炮` → `电Wave钟无炮`、`阵型字符串` → `Cell式字符串`。
      短词只可能作为独立标签出现，所以限定上下文就够了。
    """
    for a, b in (('>%s<', '>%s<'), ('>%s ', '>%s '), (' %s<', ' %s<'),
                 ('"%s"', '"%s"'), ('>%s　', '>%s　'), ('\n%s\n', '\n%s\n')):
        s = s.replace(a % k, b % v)
    return s


def _keys_desc(d):
    """按长度降序的键（缓存：这些词典在 import 之后就不再变）"""
    c = _SORTED.get(id(d))
    if c is None or c[0] != len(d):
        c = (len(d), sorted(d, key=len, reverse=True))
        _SORTED[id(d)] = c
    return c[1]


# ★ 2026-10-24：**JS 里拼出来的显示片段**（`'距' + x + '生效+'` 这种）。
#   它们在 `<script>` 里以"引号内字面量"的形式出现，逐词表不敢碰（会咬标识符），
#   所以单列一张表，只在 `names=False`（整页）时按 `'词'` 精确替换。
#   ⚠️ 只放**纯显示**的片段：`任意`（= 任意僵尸）、`旗波`（role 值）、`炮`/`特技`
#      （group 值）、`模仿`（模仿者前缀）这些是**数据**，绝不能进来。
JS_LITERALS = {
    # ★ 2026-10-24：炮积木 / 卡积木分离后的标签片段
    '<label>动作</label>': '<label>Action</label>',
    # 这两条只以**带引号字面量**的形式出现，走 BULK 会被_clean_bulk 当整句碎片丢掉
    '动作': 'Action',
    '冰相对谁、晚多久生效': 'what the ice is timed against, and how much later',
    '<div class="row"><label>落点</label>': '<div class="row"><label>Landing spot</label>',
    '>冰相对谁、晚多久生效<': '>what the ice is timed against, and how much later<',
    # ★ 2026-10-24：积木检查器里"分离炮动态落点"那几个短片段 + 「+ 炮」按钮
    ' · 动态落点（': ' · dynamic landing (',
    ' 路': ' lane',
    '）': ')',
    '.ops" title="直接放一块玉米炮（P 常规炮 + 滑动落点）">+ 炮</button>':
        '.ops" title="drop a Cob Cannon block directly '
        '(P regular cob + sliding landing spot)">+ Cob</button>',
    '上次': 'last ', '候选': 'Candidate', '全场': 'Global', '全程': 'Full',
    '即刻': 'Instant', '双轨': 'Dual', '取反': 'NOT ', '总是': 'Always',
    '打了': 'played ', '选了': 'picked ', '提示': 'Hint', '错误': 'Error',
    '警告': 'Warning', '通过': 'pass', '不可行': 'infeasible',
    '收起': 'Collapse', '编辑': 'Edit', '未知': 'unknown', '未选': 'none',
    '水平': 'Horizontal', '竖向': 'Vertical', '距': 'after ', '距 ': 'after ',
    '波内': 'in-wave ', '等到': 'when ', '等非': 'when not ', '上一波': 'last wave ',
    '炮尾': 'Cob tail', '目标': 'Target', '规则': 'Rule',
    '系：': ' family: ', '部分': 'Partial', '仅提示': 'Hint only',
    '仅数据': 'Data only', '阳光': 'Sun', '墓碑': 'grave', '组': 'set',
    '等': 'when ', '好': ' is ready', '非': 'NOT', '空': 'empty',
    '阵解': 'Solution',
    '<span class="mk tl" title="南瓜">🎃</span>':
        '<span class="mk tl" title="Pumpkin">🎃</span>',
    '<span class="mk tr" style="top:auto;bottom:1px" title="模仿者">M</span>':
        '<span class="mk tr" style="top:auto;bottom:1px" title="Imitator">M</span>',
    '<span class="mk tr" title="梯子">🪜</span>':
        '<span class="mk tr" title="Ladder">🪜</span>',
    '已选 ': 'Selected ', '已导出 ': 'Exported ', '已导入 ': 'Imported ',
    '全部完成': 'All done', ' 种': ' kinds', ' 组': ' sets', ' 行': ' row',
    ' 格': ' cells', ' 发': ' shots', ' 处': ' places', ' 波': ' waves',
    '失败：': 'failed: ', '存冰数': 'Ice bank', '导入 ': 'Import ',
    '继续？': 'Continue?',
    '全部': 'All',
    " · 拦截小鬼（动态）": " · interception (dynamic)",
    " · 滑动落点": " · sliding spot",
    " · 滑动落点（优先威胁）": " · sliding spot (threat first)",
    "滑动落点（按最靠前那只自动挑列）": "Sliding spot (auto-pick the column covering the leading zombie)",
    "拦截动态落点（炸空中的小鬼）": "Interception spot (blast the Imps in the air)",
    "<label style=\"margin-left:10px\">炮种</label>": "<label style=\"margin-left:10px\">Cob kind</label>",
    "P 常规炮": "P regular cob",
    "S 分离炮": "S separated cob",
    "D 拦截炮": "D interception cob",
    "<label style=\"margin-left:10px\">拦截时机</label>": "<label style=\"margin-left:10px\">Intercept at</label>",
    "投掷刚刚出手时": "Right as the throw starts",
    "飞行到最高点时": "At the apex of the flight",
    "小鬼将要落地时": "Just before the Imp lands",
    "<label style=\"margin-left:10px\">管哪几路</label>": "<label style=\"margin-left:10px\">Covers lanes</label>",
    "> 常磨损": "> Wear-prone",
    "常磨损 = 这个植物边打边掉，选卡要带它、": "Wear-prone = this plant keeps being worn down; the seed deck must include it ",
    "并在全场判定里挂「随时准备补」": "and a global check keeps it replanted",
    "同时会**按阵型自动选卡 + 自动填救场**。继续？": "It will also **auto-pick the seed deck from the formation and auto-fill the rescue layer**. Continue?",
    "）; 下表是**已参与模拟**的": "); the table below lists the ",
    "项，其余只当占格/未建模。</div>": " entries that **take part in the simulation**; the rest only occupy a cell",
    "后台跑一个本地服务 + 打开浏览器": "run a local server in the background and open a browser",
    "先建占位、后补卡片": "create placeholders first, fill in cards later",
    "被模仿的植物": "the imitated plant",
    "某一块具体积木": "one specific block",
    "组名": "group name",
    "阵型结构决定": "determined by the formation structure",
    "再触发": "trigger again",
    "点了没反应": "clicked and nothing happened",
    "看阵": "view formation",
    "等全部": "wait for all",
    # ---- 阵容编辑器的勾选框（JS 里 `> 套南瓜` 这样拼出来）
    '> 醒着': '> Awake', '> 套南瓜': '> Pumpkin', '> 搭梯（梯子南瓜）': '> Ladder',
    '> 墓碑': '> Gravestone', '> 有 花盆': '> Flower Pot', '> 有 睡莲': '> Lily Pad',
    '整行套南瓜': 'Pumpkin on row', '整行搭梯': 'Ladder on row',

    # ---- 选卡栏那句拼接提示（`'…张（含' + 名字 + '）；其中 …'`）
    ' 张（含': ' cards (incl. ', '）；其中 ': '); of which ',
    ' 张参与模拟，其余只当占格/未建模。</div>':
        ' cards are simulated; the rest only occupy a cell / are not modelled.</div>',
    '<option value="">（打开已保存）</option>':
        '<option value="">(open saved)</option>',

}


def _js_literals(s):
    """把 `<script>` 里 `'显示片段'` 形式的字面量换掉（连同引号一起匹配）。"""
    for k, v in JS_LITERALS.items():
        for q in ("'", '"'):
            a, b = q + k + q, q + v + q
            if a in s:
                s = s.replace(a, b)
    return s


# 报告里大量**数字 + 量词**是拼出来的（`2路 116`、`共 15 只`、`7~9 列`），
# 词典查不到，只能用规则。这些量词在中文语境里只会是"路 / 列 / 只 / 株"。
_NUM_RULES = [
    (r'(\d+)\s*[~\-–]\s*(\d+)\s*列', r'col \1-\2'),
    (r'(\d+)\s*[~\-–]\s*(\d+)\s*路', r'lanes \1-\2'),
    (r'(\d+)\s*列', r'col \1'),
    (r'(\d+)\s*路', r'lane \1'),
    (r'(\d+)\s*只', r'\1 zombies'),
    (r'(\d+)\s*株', r'\1 plants'),
]


# ★ 2026-10-24：报告页最后的**兜底扫尾**（只在 `names=True`，即报告这类
#   纯展示文本上用）。报告里没有标识符（植物名已经由 NAMES 换掉、轨道符号是 ASCII），
#   所以这里可以无条件替换 1~2 字的量词 / 短语；模板拼出来的
#   `共 <b>15</b> 只`、`lane 1 <b>-0.5</b> 列` 全靠它收尾。
RPT_WORDS = [
    ('波次', 'Waves'), ('波', ' wave'),
    ('共 ', 'total '), ('只、', ' zombies, '), ('株', ' plants'),
    ('只', ' zombies'), ('列', ' col'), ('路', ' lane'), ('次', ' times'),
    ('跑完', 'finished'), ('偏差', 'deviation'), ('核弹', 'Nuke'),
    ('核', 'nukes'), ('波次', 'Waves'), ('通', 'pass'), ('无', 'none'),
    ('有限', 'limited'), ('被偷', 'stolen'), ('植物', 'plants'),
    ('半场', ' half'), ('拍', ' beat'), ('层', ' layer'), ('格', ' cell'),
    ('个', ''), ('和', ' and '), ('与', ' and '), ('在', ' at '),
]


def _rpt_sweep(s):
    for a, b in RPT_WORDS:
        if a in s:
            s = s.replace(a, b)
    return s


def _num_rules(s):
    import re
    for a, b in _NUM_RULES:
        s = re.sub(a, b, s)
    return s


# 节奏表里的复合短名（`邻D6` / `对N6` / `间N7`）—— 前缀一个字 + 节奏码，
# 只在这类数据里出现，用规则比塞 3×N 条词条干净。
_LABEL_RULES = [(r'(?<![\u4e00-\u9fff])邻(?=[A-Z])', 'Adjacent '),
                (r'(?<![\u4e00-\u9fff])对(?=[A-Z])', 'Paired '),
                (r'(?<![\u4e00-\u9fff])间(?=[A-Z])', 'Interleaved ')]


def _label_rules(s):
    import re
    m = re.match(r'^垫材(\d*)$', s)
    if m:
        return 'Padding' + (' ' + m.group(1) if m.group(1) else '')
    for a, b in _LABEL_RULES:
        s = re.sub(a, b, s)
    return s


# ---------------------------------------------------------------- 载荷本地化
# 这些 key 的**值**是"回传给服务器的标识符 / 用户数据"，永不翻译。
_KEEP_KEYS = {'code', 'value', 'key', 'lang', 'langs', 'version', 'schema',
              'enNames', 'enMap', 'field', 'plant', 'mimic', 'mode', 'status',
              'fmt', 'op', 'do', 'kind', 'system', 'format', 'deck',
              'layout_letters', 'default_deck', 'engine_cards',
              'gaps', 'track_seps', 'regular', 'role', 'zombie'}
# 只有这些 key 的字符串值需要翻译（其余一律原样）
_TEXT_KEYS = {'note', 'label', 'trad', 'new', 'group', 'reason', 'tier', 'hint',
              'title', 'text', 'desc', 'summary', 'msg',
              'ash_txt', 'pads_txt'}


def _is_identifier(s):
    """`s` 是不是"回传给服务器的名字"（植物 / 僵尸 / 模仿者组合 / 卡片简称）。

    和 `_KEEP_KEYS` 互补：有些 key（`ops`）里既有标识符（`name`）又有显示文字
    （`group` / `note`），只能按**值**判断。
    """
    if s in NAMES:
        return True
    if s.startswith('模仿'):
        return True
    return False


def localize_obj(obj, names=True):
    """递归翻译一个 JSON 结构里**字符串值**（dict 的 key 一律不动）。"""
    if not is_en():
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _KEEP_KEYS:
                out[k] = v
            elif k in _TEXT_KEYS and isinstance(v, str):
                out[k] = tr(v) if names else localize(v, names=False)
            else:
                out[k] = localize_obj(v, names)
        return out
    if isinstance(obj, list):
        return [localize_obj(v, names) for v in obj]
    if isinstance(obj, tuple):
        return tuple(localize_obj(v, names) for v in obj)
    if isinstance(obj, str):
        if _is_identifier(obj):
            return obj
        return tr(obj) if names else localize(obj, names=False)
    return obj


def display_map():
    """给前端用的「整串 → 英文」表（只用于**文本节点 / option 显示**）。

    ★ 2026-10-24：为什么给前端而不是后端翻 —— 这些串是 JS 在浏览器里拼出来的
      （`'距' + x + '生效+'`、表格行、下拉选项），服务端根本看不到。前端按
      **整串精确匹配**替换文本节点，`value` 不动，所以不会碰标识符。
    """
    out = {}
    for d in (NAMES, WORDS, LABELS, PHRASES, BULK):
        for k, v in d.items():
            if len(k) >= 2 or k in NAMES:
                out.setdefault(k, v)
    return out


_SORTED = {}
_GUARD = '\x02'


def _guard_pairs():
    """`names=False`（整页本地化）时要**保护**的标识符。

    ★ 2026-10-24 事故：`模仿者` 被逐词表替换成 `Imitator`，JS 里的
      `mimic: '模仿者'` / `replace(/^模仿者:/, '')` 变成 `Imitator者` —— 选卡和
      模仿逻辑直接坏掉。植物 / 僵尸名同理（它们是 `option value`、阵型串的 key）。
      所以在做替换之前，先把这些"引号内 / 正则里的"出现换成**纯 ASCII 占位符**，
      最后再换回来 —— 占位符里不能留中文，否则长尾词条（如 `模仿` → `Imitator`）
      仍会咬进去。
    """
    ks = list(NAMES) + ['模仿者']
    out, back = [], []
    for i, k in enumerate(ks):
        g = '%s%d%s' % (_GUARD, i, '\x03')
        back.append((g, k))
        out.append(('"%s"' % k, '"%s"' % g))
        out.append(("'%s'" % k, "'%s'" % g))
    out.append(('模仿者:', _GUARD + 'r\x03' + ':'))
    back.append((_GUARD + 'r\x03', '模仿者'))
    return out, back


def localize(text, names=True):
    """把一段**呈现用**文本里的中文换成英文（LANG=en 时）。

    `names=True` 时连植物/僵尸名一起换（**只对纯展示内容**用，例：报告）。
    `names=False` 用在对**页面**做本地化时 —— 名字是标识符，不能动。
    """
    if not is_en() or not text:
        return text
    s = text
    if not names:
        # 顺序要紧：先换**引号内的显示片段**（含 HTML 小片段），再上标识符保护，
        # 否则 `"南瓜"` 被保护成占位符，`<span ... title="南瓜">` 这条整串就匹配不上了。
        s = _js_literals(s)
    pairs, back = ([], []) if names else _guard_pairs()
    for a, b in pairs:
        if a in s:
            s = s.replace(a, b)
    # ★ 2026-10-24：**数字模板先跑** —— 否则 `（拦截炮）` 这种短键会先把整句改坏，
    #   带数字的长句模板就再也匹配不上了（实测：拦截炮提示被切成半中半英）。
    s = _num_templates_in(s)
    for k in _keys_desc(BULK):
        if k in s:
            s = s.replace(k, BULK[k])
    for k in _keys_desc(PHRASES):
        if k in s:
            s = s.replace(k, PHRASES[k])
    for k in _keys_desc(WORDS):
        if len(k) <= 2:
            continue                      # 短词只在标签位置替换（见下）
        if k in s:
            s = s.replace(k, WORDS[k])
    if names:
        for k in _keys_desc(NAMES):
            if k in s:
                s = s.replace(k, NAMES[k])
        # 模型清单里的植物名走 `tr()` 精确匹配（`坚果` 等在 WORDS 里没有）
        for k in _keys_desc(NAMES):
            if len(k) <= 2:
                s = _ctx(s, k, NAMES[k])
    for k in _keys_desc(LABELS):
        if len(k) <= 2:
            continue
        if k in s:
            s = s.replace(k, LABELS[k])
    # 短词（1~2 字）走上下文替换，长的优先
    for d in (WORDS, LABELS):
        for k in _keys_desc(d):
            if len(k) > 2:
                continue
            v = WORDS.get(k) or LABELS.get(k)
            if v:
                s = _ctx(s, k, v)
    if not names:
        for g, k in back:                # 撤掉标识符占位符
            s = s.replace(g, k)
    s = _num_rules(s)
    if names:
        s = _rpt_sweep(s)
    return s


# ★ 2026-10-24：JSON 载荷（META / MODELS / 任务快照 / 阵解目录）里"只给人看"
#   的文字也要翻 —— 具体规则见下面 `localize_obj()` 的 `_KEEP_KEYS` / `_TEXT_KEYS`。


# ★ 2026-10-24：批量词条（整串界面文案 / 模型清单备注），由 `_tmp_trans_work.json`
#   经人工翻译后落到 `i18n_bulk.py`。查表优先级最高（最长整串先命中）。
try:
    from tools.trackcheck.i18n_bulk import BULK as _BULK
except Exception:                                            # noqa: BLE001
    _BULK = {}


def _clean_bulk(d):
    """丢掉会咬坏标识符的碎词条。

    ★ 事故复盘：`炮` → `cob` 把 `玉米炮` 咬成 `玉米cob`；`模仿` 把 `模仿者`
      咬成 `Imitator者`（选卡逻辑直接坏）。所以 1~2 字的、以及任何植物/僵尸名
      的**真子串**，一律不进批量表（这些位置本来也不需要翻译：要么是标识符，
      要么由 JS 的显示名替换负责）。
    """
    out = {}
    for k, v in d.items():
        if len(k) <= 1:
            continue
        # 只是某个植物/僵尸名的**片段**（`炮` ⊂ `玉米炮`）→ 会把名字咬坏
        #   ⚠️ 反过来（长句**包含**植物名）是允许的：整句替换是原子的。
        #   ★ 数字模板键（`循环 #s 要 # 个`）不含中文名，直接放行。
        if any(k in n for n in NAMES):
            continue
        # 整句优先：如果它只是某条 PHRASES 的一截，就丢掉（否则会把整句切碎）
        if any(k != p and k in p for p in PHRASES):
            continue
        out[k] = v
    return out


BULK = _clean_bulk(_BULK)


# ★ 2026-10-24：只给 `tr()`（**整串精确**查表）用的补充词条。
#   1~2 字的简称放进 `WORDS` 会被 `localize()` 的片段替换误伤（`炮` ⊂ `玉米炮`），
#   但整串查表是安全的，所以单列一张表。
TR_EXTRA = {
    '卡': 'Card', '炮': 'Cob', '自定义': 'Custom',
    '樱桃': 'Cherry', '辣椒': 'Chili', '窝瓜': 'Squash', '南瓜': 'Pumpkin',
    '垫材2': 'Padding 2', '垫材3': 'Padding 3', '垫材4': 'Padding 4',
    '模仿核': 'Imitator nuke', '模仿冰': 'Imitator ice',
    '补存冰': 'Refill ice bank',
}


def tr(s):
    """**没有上下文**的单个词/句（JSON 载荷里的值）→ 英文；查不到就原样返回。

    和 `localize()` 的区别：`localize` 为了不误伤专有名词，1~2 字短词只在
    标签位置替换；而 JSON 的值本身就是完整标签，必须允许精确匹配。

    ★ 2026-10-24：加一层**数字模板**查表 —— `循环 36s 要 1 个，单卡 CD 50s
      转不过来` 这种句子带数字，整串查表永远命中不了。所以把连续数字换成
      `#` 再查一次（`BULK` 里存成 `循环 #s 要 # 个…` 的键，值里用 `%s`），
      查到后再把原数字按顺序填回去。这样一句模板就够，不用为每个数字组合写一条。
    """
    if not is_en() or not s:
        return s
    v = TR_EXTRA.get(s)
    if v:
        return v
    for d in (BULK, PHRASES, WORDS, LABELS, NAMES):
        v = d.get(s)
        if v:
            return v
    v = _num_template(s)
    if v:
        return v
    v = _label_rules(s)
    if v != s:
        return v
    return localize(s, names=True)


_NUM_RE = None


def _num_templates_in(s):
    """把 `BULK` 里**含 `#` 的键**当成带数字的模板，在 `s` 里做子串替换。

    例：键 `　· 定时（距上一波 #s）` → 值 `　· timed (%ss after the previous wave)`，
    能把 `快捷布置：P（常规炮）　· 定时（距上一波 9s）` 里的尾巴翻掉，
    而前缀 `快捷布置：` 由普通 BULK 片段负责 —— 拼出来的长句不必逐句登记。
    """
    global _NUM_TPL
    if _NUM_TPL is None:
        import re as _re
        out = []
        for k, v in BULK.items():
            if '#' not in k:
                continue
            n = k.count('#')
            if v.count('%s') != n:
                continue
            # ⚠️ 不能靠 `re.escape(k).replace('\\#', …)` —— Python 3.7+ 的
            #   `re.escape` 已经**不转义 `#`** 了，那样写永远匹配不上（踩过）。
            pat = r'(\d+(?:\.\d+)?)'.join(_re.escape(part) for part in k.split('#'))
            out.append((_re.compile(pat), v))
        # 长的先试，避免短模板抢先
        out.sort(key=lambda t: -len(t[0].pattern))
        _NUM_TPL = out
    for rx, v in _NUM_TPL:
        if rx.search(s):
            s = rx.sub(lambda m, _v=v: _v % m.groups(), s)
    return s


_NUM_TPL = None


def _num_template(s):
    """数字模板查表：`循环 36s…` → 键 `循环 #s…` → 值里 `%s` 按顺序填回数字"""
    global _NUM_RE
    if _NUM_RE is None:
        import re as _re
        _NUM_RE = _re.compile(r'\d+(?:\.\d+)?')
    if not _NUM_RE.search(s):
        return None
    key = _NUM_RE.sub('#', s)
    tpl = BULK.get(key) or PHRASES.get(key) or WORDS.get(key) or LABELS.get(key)
    if not tpl:
        return None
    nums = _NUM_RE.findall(s)
    if tpl.count('%s') != len(nums):
        return None                  # 模板与数字数对不上 → 不敢乱填
    try:
        return tpl % tuple(nums)
    except Exception:                                        # noqa: BLE001
        return None


# ---------------------------------------------------------------- 术语表
# 帮助页「语言说明 / Language notes」—— 解释字母术语为什么原样保留
GLOSSARY_EN = [
    ('Track ops', 'P / A / A\' / I / N',
     'Cob Cannon / Cherry Bomb / Jalapeno / Ice-shroom / Doom-shroom. '
     'These single letters are the community shorthand for operation types.'),
    ('Operation Count', '运算量',
     'How much "tempo budget" an operation consumes. P counts as 1, A/A\' as 1, '
     'N as 2, I as 0 (ice is not an operation, it buys time).'),
    ('io', 'io',
     'Passive damage output from plants (Gloom-shroom, Winter Melon, Fume-shroom…). '
     'Written in lowercase, kept as-is.'),
    ('Field codes', 'DE / NE / PE / FE / RE',
     'DE = Day Endless (front lawn, day), NE = Night Endless (pool, night), '
     'PE = Pool Endless (pool, day), FE = Fog Endless (pool, night + fog), '
     'RE = Roof Endless. The two letters are the field, the trailing E is "Endless".'),
    ('Rhythm codes', 'C4io / P4 / N6s / P3n / S3',
     'Letter = operation type, number = how many per cycle, suffix = cycle length '
     'in seconds (s) or the "n" variant (a Nuke replacing a cob pair). '
     'io means the rhythm is driven by passive damage.'),
    ('Wave slots', 'I-PP | I-PP | N | PP',
     'Each `|`-separated beat is one wave. `-` inside a beat means "second group, '
     'later in the same wave". The wavelength list gives the **interval from the '
     'previous beat to this beat** (so the k-th wave waits `gaps[k]`).'),
]


def glossary_html():
    """帮助页里那段术语说明（中英各一份）。"""
    if is_en():
        rows = ''.join(
            '<tr><th style="white-space:nowrap">%s</th><td><code>%s</code></td>'
            '<td>%s</td></tr>' % (a, b, c) for a, b, c in GLOSSARY_EN)
        return ('<div class="helpsec"><h3>Language notes — terms kept in Latin letters</h3>'
                '<p class="hint">Most terms in this tool come from the Chinese '
                'Survival Endless community. Those that are already written in '
                'Latin letters are <b>kept unchanged</b> so that they still match '
                'the original posts, videos and spreadsheets. '
                'Everything else is translated; PVZ original content uses the '
                'official English names (e.g. 小丑 → <b>Jack-in-the-Box Zombie</b>).'
                '</p><table class="q">%s</table></div>' % rows)
    rows = ''.join(
        '<tr><th style="white-space:nowrap">%s</th><td><code>%s</code></td>'
        '<td>%s</td></tr>' % (a, b, c) for a, b, c in [
            ('轨道符号', 'P / A / A\' / I / N',
             '玉米炮 / 樱桃 / 辣椒 / 寒冰菇 / 毁灭菇，社区用单个字母表示操作类型。'),
            ('运算量', '运算量',
             '一次操作消耗多少"节奏预算"。P=1、A/A\'=1、N=2、I=0（冰不算运算量，是买时间）。'),
            ('io', 'io',
             '植物的被动输出（忧郁菇 / 冰瓜 / 大喷菇…），小写保留。'),
            ('场地', 'DE / NE / PE / FE / RE',
             'DE 白天前院、NE 黑夜泳池、PE 白天泳池、FE 雾夜泳池、RE 屋顶；末尾 E = Endless。'),
            ('节奏', 'C4io / P4 / N6s / P3n / S3',
             '字母=操作类型、数字=每循环用几个、后缀=循环长度（s）或 n 变体（核顶掉一对炮）；'
             'io = 由被动输出主导。'),
            ('波长串', 'I-PP | I-PP | N | PP',
             '每个 `|` 分隔的拍 = 一波；拍内的 `-` = 同一波里稍后的一组。'
             '波长串给的是**从前一拍生效到本拍生效**的间隔（第 k 波等 `gaps[k]`）。'),
        ])
    return ('<div class="helpsec"><h3>语言说明 · 为什么有些术语保留字母</h3>'
            '<p class="hint">本工具里绝大多数术语来自中文无尽社区。'
            '其中**本来就是字母**的那些（轨道符号、io、场地代号、节奏名）'
            '<b>一律原样保留</b>，这样它们仍能和原帖、视频、表格对得上；'
            '其余都翻译，PVZ 原版内容用官方英文名（例：小丑 → '
            '<b>Jack-in-the-Box Zombie</b>）。</p>'
            '<table class="q">%s</table></div>' % rows)
