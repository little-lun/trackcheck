# -*- coding: utf-8 -*-
"""
ui.py —— 界面与文案：出怪清单、自动判定节奏、整页 HTML、报告打印页

★ 这一层**不碰网络、不碰线程**，只有一个作用：算出"用户看到的东西"。
  所以同一个 `page_html()` 既能给本地服务用（app.py），
  也能在打包单文件网页时被 build_web.py 直接算好、写进 HTML 里。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.trackcheck import config_dianbozhong as CFG   # noqa: E402
from tools.trackcheck import data as D                   # noqa: E402
from tools.trackcheck import html_report as H            # noqa: E402
from tools.trackcheck import spawn as SP                 # noqa: E402


# ------------------------------------------------------------------ 出怪选项
# 分组只影响界面排版，不参与到任何判定里。
KIND_GROUPS = [
    ('基础', ['普通', '路障', '撑杆', '铁桶']),
    ('中级', ['读报', '铁门', '橄榄', '舞王', '潜水', '冰车', '海豚', '小丑']),
    ('特殊', ['气球', '矿工', '跳跳', '蹦极', '扶梯', '投篮']),
    ('巨人', ['白眼', '红眼']),
]

# 四档推荐组合 = 现在跑得通的那四套（TIERS 原文）
PRESET_ORDER = ['慢速', '变速', '快速', '极速']


def kind_meta():
    """给前端用的出怪清单（等级 / 血量 / 分组）"""
    out = []
    for gi, (gname, ks) in enumerate(KIND_GROUPS):
        for k in ks:
            z = SP.Z.get(k)
            if z is None:
                continue
            hp = D.ZOMB.get(k)
            hp = hp[0] if isinstance(hp, (list, tuple)) else None
            out.append(dict(name=k, group=gname, gi=gi,
                            level=z[0], hp=hp or 0,
                            note='仅旗帜波' if k == '蹦极' else ''))
    return out


def meta_payload():
    from tools.trackcheck import layout as L
    return dict(
        kinds=kind_meta(),
        presets=[dict(name=t, kinds=list(CFG.TIERS[t])) for t in PRESET_ORDER],
        layout=L.catalog(),
        # ★ 桌面版（TrackCheck.exe）才显示"退出程序"按钮并按心跳自动退出；
        #   单文件网页版没有可退的进程。
        desktop=bool(os.environ.get('TRACKCHECK_DESKTOP')),
    )


# ------------------------------------------------------------------ 自动判定节奏
# ★ 阵解只有四套，但节奏有五档：**中速**复用慢速的阵解（拖时间 + 垫材 + 窝瓜压车），
#   只是怪更轻一档。所以这里把"节奏"和"阵解"分开：tier 用于显示，solve 用于跑。
SOLVE_ALIAS = {'中速': '慢速'}

_GIANT_RED = '红眼'
_GIANT_WHITE = '白眼'
_HEAVY_NON_GIANT = {'橄榄', '铁桶'}


def pick_tier(kinds):
    """
    从出怪推节奏。**规则从上往下读，哪个先符合就是哪个**（用户 2026-10-20 定）。

        含红眼 + 白眼      → 慢速
        含红眼、无白眼      → 变速
        含白眼、无红眼      → 中速（阵解同慢速）
        无巨人，但有橄榄/铁桶 → 快速
        其余               → 极速

    为什么这样排：红眼是"必须拖时间 + 必须垫材兜底"的那一档；
    白眼的锤子只有 3000 血、走得也慢，压力比红眼低一档，但仍要拖时间，
    所以给它一个"中速"（阵解照抄慢速，只是不需要那么多灰烬）。
    没有巨人时就只看"有没有硬壳"：橄榄/铁桶顶着 IO 硬推，才需要逐波控丑；
    连硬壳都没有，剩下那些（撑杆/铁门/扶梯/跳跳/海豚/潜水）靠结构与 IO 就能吃，直接放羊。
    """
    ks = set(kinds)
    red = _GIANT_RED in ks
    white = _GIANT_WHITE in ks

    if red and white:
        return '慢速', ('含红眼 + 白眼：最强的一档，红眼 6000 血必须拖时间打，'
                       '白眼还要防锤击')
    if red:
        return '变速', '含红眼、无白眼：要拖时间，但没有 3000 血的白眼同时压着，节奏可以拆开分摊'
    if white:
        return '中速', ('含白眼、无红眼：白眼 3000 血、走得更慢，压力比红眼低一档，'
                       '波长可以放宽')
    if ks & _HEAVY_NON_GIANT:
        hard = '、'.join(sorted(ks & _HEAVY_NON_GIANT))
        return '快速', '无巨人但有%s：硬壳顶着自然输出硬推，要看逐波清场' % hard
    # ★ v0.2.2：这里只描述"出怪强度"，不再给具体打法（以前写的是电波钟的战术）
    cars = '、'.join(k for k in ('冰车', '投篮') if k in ks)
    tail = '（含%s：注意碾压与抛投）' % cars if cars else '（无巨人、无硬壳）'
    return '极速', '无巨人、无橄榄/铁桶：剩下的都是靠结构与自然输出能吃的脆皮' + tail



# ------------------------------------------------------------------ 页面
def page_html():
    """整页 HTML（阵解栏的样式/标记/脚本从 planui.py 拼进来）"""
    from tools.trackcheck import metainfo as MI
    from tools.trackcheck import planui as PU
    meta = json.dumps(meta_payload(), ensure_ascii=False)
    models = json.dumps(MI.models(), ensure_ascii=False).replace('</', '<\\/')
    return (PAGE.replace('/*__META__*/', meta)
                .replace('/*__MODELS__*/', models)
                .replace('__PLANPAGE__', PU.MARKUP)
                .replace('</style></head>', PU.STYLE + '</style></head>')
                .replace('</body></html>', PU.SCRIPT + '</body></html>'))


PAGE = r'''<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>trackcheck · PVZ 生存无尽研究工具</title>
<style>
body{font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
 margin:0;padding:20px 26px 60px;background:#f6f8fb;color:#0f172a}
h1{font-size:19px;margin:0 0 2px}
.sub{color:#64748b;font-size:12.5px;margin-bottom:16px}
.topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.gear{border:1px solid #e2e8f0;background:#fff;border-radius:10px;width:34px;height:34px;
 font-size:17px;line-height:1;cursor:pointer;color:#475569;flex:none;margin-top:2px}
.gear:hover{border-color:#93c5fd;color:#2563eb}
.gear.on{background:#2563eb;border-color:#2563eb;color:#fff}
table.modeltab{width:100%;border-collapse:collapse;font-size:12px}
table.modeltab th,table.modeltab td{border-bottom:1px solid #f1f5f9;padding:4px 6px;
 text-align:left;vertical-align:top}
table.modeltab th{color:#475569;font-weight:600;background:#f8fafc}
table.modeltab td.n{white-space:nowrap}
.lvtag{display:inline-block;font-size:10.5px;border-radius:4px;padding:0 5px;margin-right:4px}
.lv-full{background:#dcfce7;color:#166534}.lv-part{background:#fef9c3;color:#854d0e}
.lv-watch{background:#e0e7ff;color:#3730a3}.lv-data{background:#f1f5f9;color:#64748b}
.lv-todo{background:#fee2e2;color:#991b1b}.lv-shape{background:#e0f2fe;color:#075985}
.lv-none{background:#f1f5f9;color:#64748b}.lv-action{background:#fae8ff;color:#86198f}
.panel{background:#fff;border:1px solid #e2e8f0;border-radius:10px;
 padding:14px 16px;margin-bottom:14px}
.ptitle{font-size:13px;font-weight:700;color:#334155;margin-bottom:10px;
 padding-left:8px;border-left:3px solid #2563eb}
.grp{display:flex;gap:8px;align-items:flex-start;margin-bottom:8px;flex-wrap:wrap}
.gname{font-size:11.5px;color:#94a3b8;width:34px;flex:none;padding-top:6px;text-align:right}
.kzs{display:flex;gap:6px;flex-wrap:wrap;flex:1}
.kz{display:inline-flex;align-items:center;gap:5px;border:1px solid #e2e8f0;
 background:#f8fafc;border-radius:6px;padding:4px 9px;cursor:pointer;font-size:12.5px;
 user-select:none;transition:.12s}
.kz:hover{border-color:#93c5fd;background:#eff6ff}
.kz.on{background:#dbeafe;border-color:#3b82f6;color:#1e3a8a;font-weight:600}
.kz input{display:none}
.kz em{font-style:normal;color:#94a3b8;font-size:10.5px}
.kz.on em{color:#3b82f6}
.kz.off{opacity:.42;cursor:not-allowed;background:#f8fafc;border-style:dashed}
.kz.off em.ban{color:#dc2626;font-weight:600}
.presets{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px;
 padding-top:10px;border-top:1px dashed #e2e8f0}
.presets span.lab{font-size:12px;color:#64748b}
button{font:inherit;font-size:12.5px;border:1px solid #cbd5e1;background:#fff;
 border-radius:6px;padding:5px 12px;cursor:pointer;transition:.12s}
button:hover{border-color:#94a3b8;background:#f8fafc}
button.primary{background:#2563eb;border-color:#2563eb;color:#fff;font-weight:600}
button.primary:hover{background:#1d4ed8}
button.ghost{color:#64748b}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
input[type=text],input[type=number]{font:inherit;font-size:12.5px;border:1px solid #cbd5e1;
 border-radius:6px;padding:5px 9px;outline:none}
input[type=text]{width:190px}
input[type=number]{width:62px}
input:focus{border-color:#3b82f6}
table.q{width:100%;border-collapse:collapse;font-size:12.5px}
table.q th,table.q td{border-bottom:1px solid #eef2f7;padding:6px 8px;text-align:left}
table.q th{background:#f8fafc;color:#475569;font-weight:600;font-size:12px}
table.q td.dim{color:#64748b;font-size:11.5px}
.hint{font-size:12px;color:#64748b}
.job{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;
 margin-bottom:18px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.jobhead{border-bottom:1px solid #eef2f7;padding-bottom:8px;margin-bottom:8px}
.jname{font-size:15px;font-weight:700}
.jmeta{font-size:12px;color:#475569;margin-top:2px}
.jmeta .tier{color:#1d4ed8}
.jwhy{font-size:11.5px;color:#94a3b8;margin-top:1px}
.jdeck{font-size:11px;color:#64748b;margin-top:2px;
 font-family:ui-monospace,Consolas,"Microsoft YaHei",monospace}
.jacts{float:right}
.jacts button{font-size:11.5px;padding:3px 9px}
.jstrip{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:#475569;
 background:#f8fafc;border:1px solid #eef2f7;border-radius:8px;padding:7px 11px;margin-bottom:10px}
.jstrip b{color:#0f172a}
.seedbox{margin:0 0 10px}
.seedbox summary{cursor:pointer;font-size:12px;color:#2563eb;padding:3px 0}
.prog{font-size:12px;color:#64748b}
/* ---- 报告卡片（与 html_report 同款） ---- */
.card{border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px;background:#fff}
.chead{margin-bottom:10px}
.dim{color:#64748b;font-size:12px}.small{font-size:11px}
.kpis{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:10px}
.k{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:5px 9px;min-width:98px}
.k span{display:block;color:#64748b;font-size:10.5px}
.k b{font-size:14.5px}.k b.sm{font-size:11px;font-weight:500;color:#b45309}
svg.tl{width:100%;height:auto;border:1px solid #e2e8f0;border-radius:6px;background:#fff;display:block}
svg .lk{font-size:9.5px;fill:#475569;text-anchor:end}
svg .lk2{font-size:8.5px;fill:#94a3b8;text-anchor:end}
svg .tx{font-size:9px;fill:#94a3b8;text-anchor:middle}
svg .wl{font-size:8.5px;fill:#64748b;text-anchor:middle}
svg .wl.flag{fill:#dc2626;font-weight:700;font-size:9.5px}
svg .ab{font-size:8px;font-weight:700;font-family:ui-monospace,Consolas,monospace}
svg .rc{font-size:5px;font-family:ui-monospace,Consolas,monospace}
svg .ab-l{font-weight:700;fill:#334155}
.sec{font-size:12.5px;font-weight:700;color:#334155;margin:13px 0 6px;
 padding-left:7px;border-left:3px solid #cbd5e1}
.lv{display:inline-block;color:#fff;border-radius:4px;padding:1px 6px;
 font-size:10.5px;font-weight:700;white-space:nowrap}
.ok{color:#059669;font-weight:600}.bad{color:#dc2626;font-weight:600}.warn{color:#d97706;font-weight:600}
table.mini{font-size:11.5px;width:100%;border-collapse:collapse}
table.mini th,table.mini td{padding:3px 6px;border-bottom:1px solid #e2e8f0;text-align:left;
 vertical-align:top}
table.mini td:nth-child(2){text-align:right;white-space:nowrap}
table.mini.wide{font-size:11px}
table.mini.wide td:nth-child(3){font-size:10.5px;color:#0f172a}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
.ledgers{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:14px;margin:12px 0 6px}
.legend.big{display:flex;gap:14px;font-size:11.5px;background:#f8fafc;border:1px solid #e2e8f0;
 border-radius:6px;padding:7px 11px;margin-top:8px;align-items:center;flex-wrap:wrap;color:#334155}
.legend.big b{font-family:ui-monospace,Consolas,monospace;font-size:13px;margin-right:3px}
.tip{position:fixed;z-index:999;background:#0f172a;color:#e2e8f0;border-radius:8px;
 padding:10px 12px;font-size:11.5px;line-height:1.6;box-shadow:0 10px 30px rgba(15,23,42,.35);
 display:none;max-width:430px;border:1px solid #334155;pointer-events:none}
.tip h4{margin:0 0 6px;font-size:12.5px;color:#fff}
.tip .k2{color:#94a3b8}.tip .sep{height:1px;background:#334155;margin:6px 0}
.tip b{color:#fff}.tip .water{opacity:.55}.tip .cdx{display:inline-block;min-width:74px;margin-right:2px}
/* ---- 阵容布置（v0.2.2） ---- */
table.lygrid{border-collapse:separate;border-spacing:3px;font-size:11.5px;user-select:none}
table.lygrid th{font-weight:600;color:#94a3b8;font-size:11px;padding:0 2px;text-align:center}
table.lygrid th.rl{width:26px;text-align:right;padding-right:4px}
table.lygrid td{padding:0}
.lyc{width:74px;height:52px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;
 cursor:pointer;position:relative;display:flex;flex-direction:column;align-items:center;
 justify-content:center;gap:1px;transition:.1s;overflow:hidden}
.lyc:hover{border-color:#93c5fd}
.lyc.water{background:#e0f2fe;border-color:#bae6fd}
.lyc.roof{background:#fef3c7;border-color:#fde68a}
.lyc.empty{color:#cbd5e1}
.lyc.tail{background:#f1f5f9;color:#94a3b8;border-style:dashed}
.lyc.sel{outline:2px solid #2563eb;outline-offset:-2px}
.lyc .pn{font-weight:600;color:#0f172a;line-height:1.15;text-align:center;
 padding:0 2px;word-break:break-all;max-height:26px;overflow:hidden}
.lyc .mk{position:absolute;font-size:10px;line-height:1}
.lyc .mk.tl{left:2px;top:1px}.lyc .mk.tr{right:2px;top:1px}
.lyc .mk.bl{left:2px;bottom:1px}.lyc .mk.br{right:2px;bottom:1px}
.lyc .pm{position:absolute;inset:2px;border:2px solid #f59e0b;border-radius:5px;
 pointer-events:none}
.lyedit{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-start}
.lyedit .col{display:flex;flex-direction:column;gap:7px;min-width:200px}
.lyedit label.hint{cursor:pointer;display:flex;align-items:center;gap:6px}
.lyedit label.lock{opacity:.55;cursor:default}
.lyedit select{font:inherit;font-size:12.5px;border:1px solid #cbd5e1;border-radius:6px;
 padding:5px 8px;min-width:170px;outline:none}
.helpsec{font-size:13px;line-height:1.85;color:#334155}
.helpsec h3{font-size:13.5px;margin:16px 0 6px;color:#1e3a8a}
.helpsec code{background:#f1f5f9;border-radius:4px;padding:1px 5px;font-size:12px}
.helpsec pre{background:#0f172a;color:#e2e8f0;border-radius:8px;padding:10px 12px;
 font-size:11.5px;overflow:auto;line-height:1.6}
.helpsec table{border-collapse:collapse;font-size:12px;margin:6px 0}
.helpsec th,.helpsec td{border-bottom:1px solid #eef2f7;padding:4px 8px;text-align:left}
</style></head>
<body>
<div class="topbar">
  <div>
    <h1>trackcheck</h1>
    <div class="sub">PVZ 初代（1.0.0.1051 EN）生存无尽研究工具：布阵 → 出怪 → 阵解 → 跑运阵 → 出报告</div>
  </div>
  <button class="gear" id="gear" title="设置">⚙</button>
</div>
<div class="tabs">
  <button data-tab="layout" class="on">① 阵容布置</button>
  <button data-tab="spawn">② 出怪沙盘</button>
  <button data-tab="plan">③ 阵解编辑</button>
  <button data-tab="run">④ 运行与报告</button>
  <button data-tab="help">帮助</button>
</div>

<div id="tab-layout">
  <div class="panel">
    <div class="ptitle">1. 场地 · 阵型名</div>
    <div class="row">
      <label class="hint">场地
        <select id="ly-field" style="min-width:220px"></select></label>
      <span class="hint" id="ly-fieldnote"></span>
    </div>
    <div class="row" style="margin-top:6px">
      <label class="hint">阵型名</label>
      <span class="hint" id="ly-prefix" style="font-family:ui-monospace,Consolas,monospace;
        background:#f1f5f9;border-radius:5px;padding:3px 7px;color:#475569"></span>
      <input type="text" id="ly-name" style="width:190px" placeholder="电波钟无炮">
      <span class="hint">格式 <code>[场地].名字</code>，<code>[场地].</code> 由 app 自动生成，只填后面的名字</span>
    </div>
  </div>
  <div class="panel">
    <div class="ptitle">2. 阵型（点格子编辑）
      <i class="info" data-spec="layout"></i></div>
    <div class="row">
      <span class="hint">左键选格 → 下面编辑；同一行/列可以拖动框选（Shift 连选）</span>
      <button class="ghost" id="ly-clear">清空阵型</button>
      <button class="ghost" id="ly-rowpk">整行套南瓜</button>
      <button class="ghost" id="ly-rowld">整行搭梯</button>
    </div>
    <div id="ly-grid-wrap"><table id="ly-grid" class="lygrid"></table></div>
    <div class="hint" id="ly-stat" style="margin-top:8px"></div>
  </div>
  <div class="panel">
    <div class="ptitle">3. 编辑格 <span class="hint" id="ly-cellname"
      style="font-weight:400"></span></div>
    <div id="ly-editor" class="lyedit"></div>
  </div>
  <div class="panel">
    <div class="ptitle">4. 阵型字符串
      <span class="hint" id="ly-fmtlab" style="font-weight:400"></span></div>
    <div class="row">
      <input type="text" id="ly-str" placeholder="粘贴阵型字符串后点「导入」"
             style="width:420px;font-family:ui-monospace,Consolas,monospace">
      <button id="ly-imp">⤒ 导入</button>
      <button id="ly-exp">⤓ 生成字符串</button>
      <button class="ghost" id="ly-copy">复制</button>
      <span class="hint" id="ly-strmsg"></span>
    </div>
    <div class="hint">
      格式在「设置」里切：**PvZ Tools**（旧版，明文 <code>ID 行 列 …</code>，人能读懂，
      不支持模仿者/墓碑）与 **PvZ Toolkit**（新版，Base64 → 异或 0x54 → zlib + RS）。
      导入时会自动认出是哪一种。
    </div>
  </div>
</div>

<div id="tab-spawn" style="display:none">

<div class="panel">
  <div class="ptitle">1. 出怪（勾选允许出现的僵尸）</div>
  <div id="kinds"></div>
  <div class="presets"><span class="lab">推荐组合：</span><span id="presets"></span>
    <button class="ghost" id="selnone">全不选</button>
    <span class="hint" id="pickinfo"></span>
    <span class="hint" style="margin-left:8px">蹦极只在旗帜波出现；其余波会自动补普通</span>
  </div>
</div>

<div class="panel">
  <div class="ptitle">2. 待模拟列表
    <i class="info" data-spec="spawn"></i></div>
  <div class="row">
    <input type="text" id="name" placeholder="给这组出怪起个名字">
    <label class="hint">模拟次数 <input type="number" id="seeds" value="5" min="1" max="30"></label>
    <button id="add">＋ 加入列表</button>
    <button class="ghost" id="imp">⤒ 导入 JSON</button>
    <button class="ghost" id="exp">⤓ 导出 JSON</button>
    <button class="ghost" id="quit" style="display:none">⏻ 退出程序</button>
    <input type="file" id="file" accept=".json,application/json" style="display:none">
    <span class="hint">（可以加多组，出怪列表可以存成 JSON 反复用）</span>
  </div>
  <div class="hint" id="fieldnote" style="margin-top:6px"></div>
  <table class="q"><thead><tr><th style="width:30%">名称</th><th>出怪</th>
    <th style="width:64px">次数</th><th style="width:60px"></th></tr></thead>
    <tbody id="queue"><tr><td colspan="4" class="dim">还没有排队的组合</td></tr></tbody></table>
  <div class="hint" style="margin-top:8px">
    加完出怪 → 去「③ 阵解编辑」配阵解并与出怪配对 → 再到「④ 运行与报告」开跑。
  </div>
</div>

</div>

<div id="tab-settings" style="display:none">
  <div class="panel">
    <div class="ptitle">设置 · 节奏命名方案</div>
    <div id="set-naming" class="row" style="gap:14px;flex-wrap:wrap"></div>
    <div class="hint" id="set-naming-note" style="margin-top:6px"></div>
  </div>
  <div class="panel">
    <div class="ptitle">设置 · 阵型字符串格式</div>
    <div id="set-arrayfmt" class="row" style="gap:14px;flex-wrap:wrap"></div>
    <div class="hint" id="set-arrayfmt-note" style="margin-top:6px"></div>
  </div>
  <div class="panel">
    <div class="ptitle">设置 · 轨道简写 / 复写
      <span class="hint" style="font-weight:400">（对称操作写一个还是一对）</span></div>
    <div id="set-pair" class="row" style="gap:14px;flex-wrap:wrap"></div>
    <div class="hint" id="set-pair-note" style="margin-top:6px"></div>
  </div>
  <div class="panel">
    <div class="ptitle">模型清单 · 植物
      <span class="hint" style="font-weight:400">（哪些植物参与模拟、哪些只是占格、哪些还没建模）</span></div>
    <div id="set-plants"></div>
  </div>
  <div class="panel">
    <div class="ptitle">模型清单 · 僵尸</div>
    <div id="set-zombies"></div>
  </div>
  <div class="panel">
    <div class="ptitle">模型清单 · 场地</div>
    <div id="set-fields"></div>
  </div>
  <div class="panel">
    <div class="ptitle">关于</div>
    <div id="set-about" class="hint"></div>
  </div>
</div>
<div id="tab-run" style="display:none">
  <div class="panel">
    <div class="ptitle">3. 运行
      <span class="hint" style="font-weight:400">（左边这列来自出怪沙盘，右边是它用哪套阵解）</span></div>
    <div id="runmap"></div>
    <div class="row" style="margin-top:12px">
      <button class="primary" id="start">▶ 开始模拟</button>
      <button class="ghost" id="clear">清空结果</button>
      <span class="hint" id="status"></span>
    </div>
  </div>
  <div id="results"></div>
</div>
__PLANPAGE__
<div id="tab-help" style="display:none">
  <div class="panel">
    <div class="ptitle">怎么用（四步）</div>
    <div class="helpsec">
      <h3>① 阵容布置</h3>
      <p>先选<b>场地</b>（PE / FE / DE / NE / RE），起一个<b>阵型名</b>
      （格式 <code>[场地].名字</code>，<code>[场地].</code> 由 app 自动生成，只填后面的名字），
      再点格子把植物摆上去。
      每格可以设：主植物（含模仿者）、<b>是否套南瓜</b>、<b>是否搭梯</b>（必须先有南瓜）、
      <b>是否有睡莲/花盆</b>（水路、屋顶有东西时会自动锁上）。
      也可以在下面直接<b>粘贴 PvZ Tools 的阵型字符串</b>导入，或用「生成字符串」导出。</p>
      <h3>② 出怪沙盘</h3>
      <p>勾选这一关允许出现的僵尸，起个名字点「加入列表」。可以加多组（不同出怪组合）。</p>
      <h3>③ 阵解编辑</h3>
      <p>阵解 = 「节奏 + 每波做什么 + 全场判定 + 救场」。如果只想看自然输出能撑多久，
      这一步可以跳过（不选阵解就是"什么都不做"的空轨道）。
      所有出现 JSON 的地方都有一个小 <b>i</b>，点开能复制/下载格式说明 —— 直接交给 AI 生成阵解。</p>
      <p><b>轨道里只有两种操作</b>：<b>P</b>（玉米炮，不指定哪一门）和
      <b>种植物</b>（卡片）。轨道串认得
      <code>|</code>（换波）、<code>-</code>（同一波的第二个时机）、
      <code>/</code>（上下半场）、<code>~</code>（两套节奏摆动）；
      右边的「波长串」写 <code>(9,9,9,9)</code>，会自动校验波长和够不够炮 / 卡的 CD 转完。</p>
      <h3>④ 运行与报告</h3>
      <p>点「开始模拟」。报告里有：波长、偏差、减速覆盖、存冰/阳光/补南瓜台账、
      逐波时间轴、轨道执行表；右上角可以下载 PDF。</p>
      <p class="hint">注意：本工具是<b>模型</b>，不是游戏本体。哪些植物/僵尸/场地建模到什么程度，
      见右上角齿轮里的「模型清单」。</p>
    </div>
  </div>

  <div class="panel">
    <div class="ptitle">使用示例：PE.电波钟无炮（C4io）</div>
    <div class="helpsec">
      <p>下面的示例<b>不在</b>主界面里，只是给你看"一个完整配置长什么样"。
      点按钮会把它载入到 ① 阵容布置 / ③ 阵解编辑 里，可以照着改。</p>
      <p><b>节奏</b>：C<sub>4</sub>io —— 4 拍循环 <code>N | AA′ | I | I</code>
      （N = 毁灭菇、A = 樱桃、A′ = 辣椒、I = 寒冰菇），常规波长 ≈ 15.4~15.9s。
      2016 年后的写法在两套命名方案下都叫 C4io（C 系未废止，归入 P 大类）。</p>
      <p><b>阵型要点</b>：6 行 9 列泳池；3/4 路是水路；3-2 / 3-3 / 4-3 / 5-3 是永久存冰位；
      2-7 / 5-7 是前场临时位；5-8 是主核坑。</p>
      <div class="row" style="margin-top:8px">
        <button id="help-load">载入示例阵容</button>
        <button id="help-plan">载入示例阵解</button>
        <button id="help-classic8">载入 PE.经典八炮（炮阵样板）</button>
 <button id="help-fe4">载入 FE.雾四炮（少炮重 IO 样板）</button>
        <span class="hint" id="help-msg"></span>
      </div>
      <h3>示例阵型字符串（PvZ Tools）</h3>
      <pre id="help-str">（点「载入示例阵容」后会自动填进 ①）</pre>
    </div>
  </div>
</div>
<div class="tip" id="tip"></div>

<script>
const META = /*__META__*/;
const MODELS = /*__MODELS__*/;
let queue = [];
let rendered = new Set();
let polling = null;

/* ================= ① 阵容布置 ================= */
const LY = { field: localStorage.getItem('tc.field') || 'PE', array: {}, sel: null,
             name: localStorage.getItem('tc.layoutname') || '' };
const LYC = META.layout || { plants: [], mushrooms: [], base_for: {}, mimic: '模仿者' };
const LY_MUSH = new Set(LYC.mushrooms || []);

function lyEsc(s){ return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function lyFields(){ return (MODELS.fields && MODELS.fields.list) || []; }
function lyFieldInfo(code){
  return lyFields().find(f => f.code === code) || { code: 'PE', rows: 6, water: [], base_plant: null };
}
function lyCell(r, c){ return LY.array[r + '-' + c] || null; }
function lySetCell(r, c, cell){
  const k = r + '-' + c;
  const v = cell && (cell.plant || cell.pumpkin || cell.base || cell.grave) ? cell : null;
  if (v) LY.array[k] = v; else delete LY.array[k];
}
function lyIsMush(name){
  const core = String(name || '').replace(/^模仿者:/, '');
  return LY_MUSH.has(core);
}
/* ★ 2026-10-23 用户：夜场（NE / FE）蘑菇**不可能睡眠**，勾选框锁定为"醒着" */
function lyIsNight(){ return !!lyFieldInfo(LY.field).night; }
function lyNeedsBase(r){
  const f = lyFieldInfo(LY.field);
  return (f.water || []).indexOf(r) >= 0 || !!f.base_plant;
}
function lyBaseName(){
  const f = lyFieldInfo(LY.field);
  return f.base_plant || '睡莲';
}
/* ★ 2026-10-22 用户口径（第二次修订）：
   · 水路 / 屋顶：空地**可以不放底座**（底座不再无条件锁定）；
     但只要这格有植物 / 套了南瓜 / 搭了梯 / 是玉米炮，就必须有底座并锁定勾上
   · 草地：**不能放睡莲**，花盆可有可无
   · **水路不准搭梯**（梯子只能搭在陆地 / 屋顶的南瓜上） */
function lyBaseRule(r){
  const f = lyFieldInfo(LY.field);
  if ((f.water || []).indexOf(r) >= 0)
    return { name: '睡莲', need: true, water: true };
  if (f.base_plant) return { name: f.base_plant, need: true, water: false };
  return { name: '花盆', need: false, water: false };
}
/* 这一格是不是某门玉米炮的尾格 → 返回炮头列号，否则 0 */
function lyCobHeadCol(r, c){
  if (c - 1 < 1) return 0;
  const head = lyCell(r, c - 1);
  return head && lyCobCore(head.plant) ? c - 1 : 0;
}
function lyCobCore(name){ return String(name || '').replace(/^模仿者:/, '') === (LYC.cob || '玉米炮'); }
function lyHasCob(r, c){ const cell = lyCell(r, c); return !!(cell && lyCobCore(cell.plant)); }
/* 阵型里有多少门玉米炮（尾格不算）—— 波长校验要它 */
function plCobCount(){
  const f = lyFieldInfo(LY.field);
  const rows = f.rows || 6;
  let n = 0;
  Object.keys(LY.array).forEach(k => {
    const r = +k.split('-')[0];
    if (r > rows) return;
    if (lyCobCore((LY.array[k] || {}).plant)) n++;
  });
  return n;
}

/* ★ 2026-10-22 命名规则（用户口径）：**阵型**命名 `[场地].名字`，
   `[场地].` 这一截由 app 自动生成 —— 输入框里只填裸名字。 */
const LY_NAME_KEY = 'tc.layoutname';
function lyBareName(name){
  let s = String(name === undefined || name === null ? '' : name).trim();
  if (s.charAt(0) === '['){
    const i = s.indexOf('].');
    if (i > 0) s = s.slice(i + 2).trim();
  }
  return s;
}
function lyFullName(fieldCode){
  const fld = fieldCode || LY.field;
  return '[' + fld + '].' + (lyBareName(LY.name) || '未命名阵型');
}
function lyRenderName(){
  const pre = document.getElementById('ly-prefix');
  const inp = document.getElementById('ly-name');
  if (pre) pre.textContent = '[' + LY.field + '].';
  if (inp && document.activeElement !== inp) inp.value = lyBareName(LY.name);
}

function lyRenderField(){
  const sel = document.getElementById('ly-field');
  sel.innerHTML = lyFields().map(f =>
    '<option value="' + f.code + '">' + f.code + ' · ' + f.name +
    '（' + f.rows + ' 行）</option>').join('');
  sel.value = LY.field;
  const f = lyFieldInfo(LY.field);
  document.getElementById('ly-fieldnote').textContent = f.note || '';
}

function lyRenderGrid(){
  const f = lyFieldInfo(LY.field);
  const rows = f.rows || 6;
  let h = '<tr><th class="rl"></th>';
  for (let c = 1; c <= 9; c++) h += '<th>' + c + '</th>';
  h += '</tr>';
  for (let r = 1; r <= rows; r++) {
    h += '<tr><th class="rl">' + r + '</th>';
    for (let c = 1; c <= 9; c++) {
      const cell = lyCell(r, c) || {};
      const water = (f.water || []).indexOf(r) >= 0;
      const roof = !!f.base_plant;
      const tailHead = lyCobHeadCol(r, c);
      const cls = ['lyc'];
      if (water) cls.push('water');
      if (roof) cls.push('roof');
      if (tailHead) cls.push('tail');
      if (!cell.plant && !cell.pumpkin && !cell.base && !cell.grave && !tailHead)
        cls.push('empty');
      if (LY.sel && LY.sel[0] === r && LY.sel[1] === c) cls.push('sel');
      const name = cell.plant || (tailHead ? '炮尾' : (cell.grave ? '墓碑' : ''));
      let mk = '';
      if (cell.pumpkin) mk += '<span class="mk tl" title="南瓜">🎃</span>';
      if (cell.ladder) mk += '<span class="mk tr" title="梯子">🪜</span>';
      if (cell.base) mk += '<span class="mk bl" title="' + cell.base + '">◦</span>';
      if (cell.plant && lyIsMush(cell.plant) && cell.awake === false)
        mk += '<span class="mk br" title="睡着">💤</span>';
      if (/^模仿者:/.test(cell.plant || ''))
        mk += '<span class="mk tr" style="top:auto;bottom:1px" title="模仿者">M</span>';
      h += '<td><div class="' + cls.join(' ') + '" data-r="' + r + '" data-c="' + c + '">'
        + (cell.pumpkin ? '<div class="pm"></div>' : '')
        + '<div class="pn">' + (name ? esc(name.replace('模仿者:', 'M·')) : '·') + '</div>'
        + mk + '</div></td>';
    }
    h += '</tr>';
  }
  const tb = document.getElementById('ly-grid');
  tb.innerHTML = h;
  tb.querySelectorAll('.lyc').forEach(el => {
    el.onclick = () => { LY.sel = [+el.dataset.r, +el.dataset.c]; lyRenderGrid(); lyRenderEditor(); };
  });
  lyRenderStat();
}

function lyRenderStat(){
  const f = lyFieldInfo(LY.field);
  const rows = f.rows || 6;
  const n = Object.keys(LY.array).length;
  const plants = Object.values(LY.array).filter(x => x.plant).length;
  document.getElementById('ly-stat').textContent =
    '阵型 ' + lyFullName() + '　·　已放 ' + plants + ' 株植物（' + n +
    ' 个格子有内容）· 场地 ' + LY.field +
    ' · ' + rows + ' 行 × 9 列' + (f.rows < 6 ? '（第 6 行的配置会被忽略）' : '');
}

function lyRenderEditor(){
  const box = document.getElementById('ly-editor');
  if (!LY.sel){
    document.getElementById('ly-cellname').textContent = '（先点一个格子）';
    box.innerHTML = '<div class="hint">在上面点一格开始编辑。</div>';
    return;
  }
  const [r, c] = LY.sel;
  document.getElementById('ly-cellname').textContent = '　' + r + '-' + c;
  const cell = Object.assign({ plant: null, pumpkin: false, ladder: false,
                               awake: true, base: null, grave: false },
                             lyCell(r, c) || {});
  const cur = cell.plant || '';
  const isMimic = /^模仿者:/.test(cur);
  const core = isMimic ? cur.split(':')[1] : cur;
  const baseRule = lyBaseRule(r);
  const tailHead = lyCobHeadCol(r, c);          // >0 = 这格是某门炮的尾格
  const isCob = lyCobCore(cur);
  // 底座：有植物 / 南瓜 / 梯子 / 玉米炮 → 水上屋顶必须锁死勾上；空地可以自由
  const baseLocked = baseRule.need &&
    !!(cell.plant || cell.pumpkin || cell.ladder || tailHead);
  const baseOn = baseLocked ? true : !!cell.base;
  const noCover = isCob || !!tailHead;          // 玉米炮头尾都不许南瓜/梯子
  const noLadder = noCover || baseRule.water;   // ★ 水路不准搭梯
  const opt = (list, v) => list.map(x =>
    '<option value="' + lyEsc(x) + '"' + (x === v ? ' selected' : '') + '>'
    + lyEsc(x) + '</option>').join('');
  box.innerHTML =
    '<div class="col">'
    + '<div class="hint">主植物</div>'
    + (tailHead
       ? '<div class="hint" style="color:#c44">这格被 ' + r + '-' + tailHead
         + ' 的玉米炮占着（1×2 的尾格），不能种东西</div>'
       : '<select id="ly-plant"><option value="">（空地）</option>'
         + opt(LYC.plants || [], core)
         + '<option value="' + LYC.mimic + '"' + (isMimic ? ' selected' : '') + '>'
         + LYC.mimic + '（模仿）</option></select>'
         + (isMimic ? '<select id="ly-mimic">' + opt(LYC.plants || [], core) + '</select>' : ''))
    + '<label class="hint' + (lyIsMush(cur) ? '' : ' lock') + '">'
    + '<input type="checkbox" id="ly-awake"'
    + ((lyIsMush(cur) && lyIsNight()) || cell.awake !== false ? ' checked' : '')
    + (lyIsMush(cur) ? '' : ' disabled')
    + (lyIsMush(cur) && lyIsNight() ? ' disabled' : '') + '> 醒着'
    + (lyIsMush(cur) && lyIsNight() ? '（夜场锁定：蘑菇不会睡）' : '（蘑菇才有睡眠）')
    + '</label>'
    + '</div>'
    + '<div class="col">'
    + '<div class="hint">附加</div>'
    + '<label class="hint' + (noCover ? ' lock' : '') + '">'
    + '<input type="checkbox" id="ly-pumpkin"'
    + (cell.pumpkin && !noCover ? ' checked' : '')
    + (noCover ? ' disabled' : '') + '> 套南瓜'
    + (noCover ? '（玉米炮不能套）' : '') + '</label>'
    + '<label class="hint' + (cell.pumpkin && !noLadder ? '' : ' lock') + '">'
    + '<input type="checkbox" id="ly-ladder"'
    + (cell.ladder && !noLadder ? ' checked' : '')
    + (cell.pumpkin && !noLadder ? '' : ' disabled') + '> 搭梯（梯子南瓜）'
    + (baseRule.water && !noCover ? '（水路南瓜不能搭梯）'
       : (noCover ? '（玉米炮不能搭）' : '')) + '</label>'
    + '<label class="hint' + (baseLocked ? ' lock' : '') + '">'
    + '<input type="checkbox" id="ly-base"' + (baseOn ? ' checked' : '')
    + (baseLocked ? ' disabled' : '') + '> 有 ' + baseRule.name
    + (baseLocked
       ? '（有植物/南瓜/玉米炮 → 必须有）'
       : (baseRule.need ? '（空地可以先不放）' : '（草地上只能放花盆）')) + '</label>'
    + '<label class="hint"><input type="checkbox" id="ly-grave"'
    + (cell.grave ? ' checked' : '') + '> 墓碑</label>'
    + '<label class="hint" title="core = 这个格子是阵型的核心植物（丢了就是崩阵）">'
    + '<input type="checkbox" id="ly-core"'
    + (cell.core ? ' checked' : '') + '> 贴 core 标签</label>'
    + '</div>'
    + '<div class="col"><div class="hint">说明</div><div class="hint" '
    + 'style="max-width:280px">主植物里没有 南瓜 / 睡莲 / 花盆 —— 它们是壳和基座，'
    + '用右边的勾选框表示。<b>草地不能放睡莲</b>，但可以放花盆。'
    + '<b>玉米炮占 1×2</b>（右边一格是它的尾格，水上/屋顶两格都要底座，'
    + '且不能套南瓜）。模仿者在阵型字符串里占 PI 位。</div></div>';

  const plantSel = document.getElementById('ly-plant');
  if (plantSel) plantSel.onchange = () => {
    const v = plantSel.value;
    let name = v;
    if (v === LYC.mimic) {
      const guess = core && (LYC.plants || []).indexOf(core) >= 0 ? core
        : ((LYC.plants || [])[0] || '寒冰菇');
      name = LYC.mimic + ':' + guess;
    }
    if (lyCobCore(name) && c + (LYC.cob_span || 2) - 1 > 9){
      alert('玉米炮占 1×2（右边一格也算它的），第 9 列放不下');
      plantSel.value = cur; return;
    }
    cell.plant = name || null;
    if (cell.plant && lyIsMush(cell.plant) && cell.awake === undefined) cell.awake = false;
    if (!cell.plant) cell.awake = true;
    lyOnPlantChanged(r, c, cell);
  };
  const mimSel = document.getElementById('ly-mimic');
  if (mimSel) mimSel.onchange = () => {
    cell.plant = LYC.mimic + ':' + mimSel.value;
    lyOnPlantChanged(r, c, cell);
  };
  const wake = document.getElementById('ly-awake');
  wake.onchange = () => { cell.awake = wake.checked; lySetCell(r, c, cell); lyRenderGrid(); };
  const pk = document.getElementById('ly-pumpkin');
  pk.onchange = () => {
    cell.pumpkin = pk.checked;
    if (!pk.checked) cell.ladder = false;
    if (cell.pumpkin && baseRule.need) cell.base = baseRule.name;
    lySetCell(r, c, cell); lyRenderGrid(); lyRenderEditor();
  };
  const ld = document.getElementById('ly-ladder');
  ld.onchange = () => {
    cell.ladder = ld.checked && !noLadder;
    if (cell.ladder && baseRule.need) cell.base = baseRule.name;
    lySetCell(r, c, cell); lyRenderGrid(); lyRenderEditor();
  };
  const bs = document.getElementById('ly-base');
  bs.onchange = () => { cell.base = bs.checked ? baseRule.name : null;
                        lySetCell(r, c, cell); lyRenderGrid(); };
  const gv = document.getElementById('ly-grave');
  gv.onchange = () => { cell.grave = gv.checked; lySetCell(r, c, cell); lyRenderGrid(); };
  const ce = document.getElementById('ly-core');
  if (ce) ce.onchange = () => { cell.core = ce.checked; lySetCell(r, c, cell); lyRenderGrid(); };
}

/* 改了主植物后的连锁反应：玉米炮 → 清掉南瓜/梯子、补底座、清空尾格 */
function lyOnPlantChanged(r, c, cell){
  const rule = lyBaseRule(r);
  if (rule.water) cell.ladder = false;          // 水路不准搭梯
  if (lyIsNight() && cell.plant && lyIsMush(cell.plant)) cell.awake = true;
  if (lyCobCore(cell.plant)){
    cell.pumpkin = false; cell.ladder = false;
    if (rule.need) cell.base = rule.name;
    const t = lyCell(r, c + 1);
    if (t){                      // 尾格：只留底座，清掉内容
      t.plant = null; t.pumpkin = false; t.ladder = false; t.awake = true;
      if (rule.need) t.base = rule.name;
      lySetCell(r, c + 1, t);
    }
  } else if (rule.need && cell.plant){
    cell.base = rule.name;      // 水上/屋顶种东西必须有底座
  }
  lySetCell(r, c, cell); lyRenderGrid(); lyRenderEditor();
}

function lyRender(){ lyRenderField(); lyRenderName(); lyRenderGrid();
                     lyRenderEditor(); lyRenderFormatLabel(); }

/* 导入/载入之后统一按规则理顺：草地清睡莲、有内容的水上屋顶补底座、
   玉米炮的尾格清干净。返回改动格数。 */
function lyNormalizeRules(){
  let n = 0;
  Object.keys(LY.array).forEach(k => {
    const r = +k.split('-')[0];
    const rule = lyBaseRule(r);
    const v = LY.array[k];
    if (v.base && v.base !== rule.name) { v.base = null; n++; }
    if (rule.water && v.ladder) { v.ladder = false; n++; }   // 水路不准搭梯
    // 夜场：蘑菇不会睡 → 一律醒着
    if (lyIsNight() && v.plant && lyIsMush(v.plant) && v.awake !== true) {
      v.awake = true; n++;
    }
    if (lyCobCore(v.plant)) {
      if (v.pumpkin || v.ladder) { v.pumpkin = false; v.ladder = false; n++; }
      if (rule.need && !v.base) { v.base = rule.name; n++; }
    }
    if (rule.need && (v.plant || v.pumpkin || v.ladder) && !v.base) {
      v.base = rule.name; n++;
    }
  });
  // 尾格：不能有内容
  Object.keys(LY.array).forEach(k => {
    const r = +k.split('-')[0], c = +k.split('-')[1];
    if (!lyCobHeadCol(r, c)) return;
    const t = LY.array[k];
    if (t.plant || t.pumpkin || t.ladder || t.grave) {
      t.plant = null; t.pumpkin = false; t.ladder = false;
      t.awake = true; t.grave = false; n++;
    }
    const rule = lyBaseRule(r);
    if (rule.need && !t.base) { t.base = rule.name; n++; }
  });
  return n;
}

function lyArrayForExport(){
  const out = {};
  const f = lyFieldInfo(LY.field);
  const rows = f.rows || 6;
  const key = (r, c) => r + '-' + c;
  Object.keys(LY.array).forEach(k => {
    const cell = LY.array[k];
    const r = +k.split('-')[0];
    if (r > rows) return;
    const v = Object.assign({}, cell);
    const rule = lyBaseRule(r);
    if (v.base && v.base !== rule.name) v.base = null;   // 草地上的睡莲
    if (rule.water) v.ladder = false;                    // 水路不准搭梯
    if (lyIsNight() && v.plant && lyIsMush(v.plant)) v.awake = true;  // 夜场不睡
    if (lyCobCore(v.plant)) { v.pumpkin = false; v.ladder = false; }
    // 有植物 / 南瓜 / 梯子 → 水上、屋顶必须补底座（空地可以没有）
    if (rule.need && (v.plant || v.pumpkin || v.ladder)) v.base = rule.name;
    if (!v.base) delete v.base;
    out[k] = v;
  });
  // 玉米炮：1×2 —— 尾格只带底座，不能有内容
  Object.keys(out).forEach(k => {
    const v = out[k];
    const r = +k.split('-')[0], c = +k.split('-')[1];
    if (!lyCobCore(v.plant) || c + (LYC.cob_span || 2) - 1 > 9) return;
    const rule = lyBaseRule(r);
    const t = Object.assign({}, out[key(r, c + 1)] || {});
    t.plant = null; t.pumpkin = false; t.ladder = false;
    t.awake = true; t.grave = false;
    if (rule.need) t.base = rule.name; else delete t.base;
    out[key(r, c + 1)] = t;
  });
  return out;
}

document.getElementById('ly-field').onchange = ev => {
  LY.field = ev.target.value;
  localStorage.setItem('tc.field', LY.field);
  LY.sel = null;
  if (typeof plSetField === 'function') plSetField(LY.field);
  lyNormalizeRules();               // 夜场切换时把蘑菇改成醒着
  lyRender();
  syncKinds();                      // ★ 换场地 → 重新按禁出规则锁定出怪勾选
};
document.getElementById('ly-name').oninput = ev => {
  LY.name = lyBareName(ev.target.value);
  localStorage.setItem(LY_NAME_KEY, LY.name);
  lyRenderStat();
};
document.getElementById('ly-clear').onclick = () => {
  if (!confirm('清空整个阵型？')) return;
  LY.array = {}; LY.sel = null; lyRender();
};
document.getElementById('ly-rowpk').onclick = () => {
  if (!LY.sel) { alert('先点一个格子，按钮对那一行生效'); return; }
  const [r] = LY.sel;
  const rule = lyBaseRule(r);
  for (let c = 1; c <= 9; c++) {
    if (lyHasCob(r, c) || lyCobHeadCol(r, c)) continue;   // 玉米炮头/尾不能套
    const cell = Object.assign({ plant: null, pumpkin: false, ladder: false,
                                 awake: true, base: null, grave: false }, lyCell(r, c) || {});
    cell.pumpkin = true;
    if (rule.need) cell.base = rule.name;                 // 套南瓜必须有底座
    lySetCell(r, c, cell);
  }
  lyRender();
};
document.getElementById('ly-rowld').onclick = () => {
  if (!LY.sel) { alert('先点一个格子，按钮对那一行生效'); return; }
  const [r] = LY.sel;
  if (lyBaseRule(r).water) { alert('水路不能搭梯（梯子只能搭在陆地 / 屋顶的南瓜上）'); return; }
  for (let c = 1; c <= 9; c++) {
    const cell = lyCell(r, c);
    if (cell && cell.pumpkin) { cell.ladder = true; lySetCell(r, c, cell); }
  }
  lyRender();
};
/* ---------------- 阵型字符串格式（设置项） ---------------- */
const FMT_KEY = 'tc.arrayfmt';
function tcArrayFmt(){
  const ok = (LYC.formats || []).map(f => f.id);
  const v = localStorage.getItem(FMT_KEY);
  return ok.indexOf(v) >= 0 ? v : (LYC.default_format || 'toolkit');
}
function tcSetArrayFmt(v){
  localStorage.setItem(FMT_KEY, v);
  renderSettings();
  lyRenderFormatLabel();
}
function lyRenderFormatLabel(){
  const el = document.getElementById('ly-fmtlab');
  if (!el) return;
  const f = (LYC.formats || []).find(x => x.id === tcArrayFmt());
  el.textContent = f ? '（当前格式：' + f.label + '）' : '';
}

document.getElementById('ly-exp').onclick = async () => {
  const r = await fetch('/api/layout/encode', { method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ array: lyArrayForExport(), field: LY.field,
                           fmt: tcArrayFmt() }) });
  const d = await r.json();
  if (!d.ok) { document.getElementById('ly-strmsg').textContent = '生成失败：' + (d.error || ''); return; }
  document.getElementById('ly-str').value = d.string;
  document.getElementById('ly-strmsg').textContent =
    '已按「' + d.fmt_label + '」生成（' + d.string.length + ' 字符）';
};
document.getElementById('ly-imp').onclick = async () => {
  const s = document.getElementById('ly-str').value.trim();
  if (!s) { alert('先把阵型字符串粘进来'); return; }
  const r = await fetch('/api/layout/decode', { method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ string: s, field: LY.field }) });
  const d = await r.json();
  if (!d.ok) { document.getElementById('ly-strmsg').textContent = '导入失败：' + (d.error || ''); return; }
  LY.field = d.field; LY.array = {}; LY.sel = null;
  Object.keys(d.array).forEach(k => {
    const v = d.array[k];
    LY.array[k] = Object.assign({ plant: null, pumpkin: false, ladder: false,
                                  awake: true, base: null, grave: false }, v);
  });
  localStorage.setItem('tc.field', LY.field);
  document.getElementById('ly-strmsg').textContent =
    '已按「' + d.fmt_label + '」导入 ' + Object.keys(d.array).length +
    ' 格（场地 ' + d.field + (d.rake ? ' · 钉耙第 ' + d.rake + ' 行' : '') + '）';
  const fixed = lyNormalizeRules();
  if (fixed)
    document.getElementById('ly-strmsg').textContent +=
      '　已按底座 / 玉米炮规则校正 ' + fixed + ' 处';
  lyRender(); syncKinds();
};
document.getElementById('ly-copy').onclick = () => {
  const el = document.getElementById('ly-str');
  if (!el.value) { document.getElementById('ly-strmsg').textContent = '还没有字符串'; return; }
  el.select(); document.execCommand('copy');
  document.getElementById('ly-strmsg').textContent = '已复制';
};

/* ---------------- 帮助页：载入 PE.电波钟无炮 示例 ---------------- */
async function tcLoadExampleArray(){
  const msg = document.getElementById('help-msg');
  const r = await fetch('/api/example/array');
  const d = await r.json();
  if (!d.ok) { msg.textContent = '载入失败'; return; }
  LY.field = d.field || 'PE';
  LY.array = {};
  Object.keys(d.array).forEach(k => {
    LY.array[k] = Object.assign({ plant: null, pumpkin: false, ladder: false,
                                  awake: true, base: null, grave: false }, d.array[k]);
  });
  LY.sel = null;
  if (d.name) {
    LY.name = lyBareName(d.name);
    localStorage.setItem(LY_NAME_KEY, LY.name);
  }
  localStorage.setItem('tc.field', LY.field);
  lyNormalizeRules();
  lyRender();
  // 顺手把示例阵型字符串填到帮助页
  const e = await fetch('/api/layout/encode', { method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ array: lyArrayForExport(), field: LY.field }) });
  const ed = await e.json();
  if (ed.ok) {
    document.getElementById('help-str').textContent = ed.string;
    document.getElementById('ly-str').value = ed.string;
  }
  msg.textContent = '已把示例阵容「' + lyFullName() + '」载入「① 阵容布置」';
  tcTab('layout');
}
async function tcLoadExamplePlan(){
  const msg = document.getElementById('help-msg');
  if (typeof plAddExamplePlan !== 'function') { msg.textContent = '阵解编辑器还没就绪'; return; }
  const n = await plAddExamplePlan();
  msg.textContent = '已把示例阵解「' + n + '」加入「③ 阵解编辑」的阵解库';
  tcTab('plan');
}
document.getElementById('help-load').onclick = tcLoadExampleArray;
document.getElementById('help-plan').onclick = tcLoadExamplePlan;

/* ★ 2026-10-22：PE.经典八炮 —— 常规炮阵的样板（阵型 + P4 阵解一起载入） */
async function tcLoadClassic8(){
  const msg = document.getElementById('help-msg');
  // 阵解编辑器还没 boot 过（没进过 ③ 页）→ 先把 catalog 拉下来
  if (typeof plEnterPlan === 'function' && (typeof PLAN === 'undefined' || !PLAN.cat)) {
    try { await plEnterPlan(); } catch (e) {}
  }
  const r = await fetch('/api/example/classic8');
  const d = await r.json();
  if (!d.ok) { msg.textContent = '载入失败：' + (d.error || ''); return; }
  LY.field = d.field || 'PE';
  LY.array = {};
  Object.keys(d.array || {}).forEach(k => {
    LY.array[k] = Object.assign({ plant: null, pumpkin: false, ladder: false,
                                  awake: true, base: null, grave: false }, d.array[k]);
  });
  LY.name = lyBareName(d.name || '经典八炮');
  localStorage.setItem(LY_NAME_KEY, LY.name);
  localStorage.setItem('tc.field', LY.field);
  LY.sel = null;
  lyNormalizeRules();
  lyRender();
  if (typeof plAddBank === 'function' && d.plan) {
    plAddBank(d.plan, d.name || '经典八炮');
  }
  msg.textContent = '已载入「' + lyFullName() + '」的阵型与 P4 阵解（9s 一对炮）';
  tcTab('layout');
}
document.getElementById('help-classic8').onclick = tcLoadClassic8;

/* ★ 2026-10-22：FE.雾四炮 —— 少炮重 IO 阵的样板（夜场；阵型 + N6s 阵解一起载入）
   四个阵解都在 `example_fe4(rid)` 里：N6s / P3n / S3 / C4io。 */
async function tcLoadFe4(){
  const msg = document.getElementById('help-msg');
  if (typeof plEnterPlan === 'function' && (typeof PLAN === 'undefined' || !PLAN.cat)) {
    try { await plEnterPlan(); } catch (e) {}
  }
  const r = await fetch('/api/example/fe4');
  const d = await r.json();
  if (!d.ok) { msg.textContent = '载入失败：' + (d.error || ''); return; }
  LY.field = d.field || 'FE';
  LY.array = {};
  Object.keys(d.array || {}).forEach(k => {
    LY.array[k] = Object.assign({ plant: null, pumpkin: false, ladder: false,
                                  awake: true, base: null, grave: false }, d.array[k]);
  });
  LY.name = lyBareName(d.name || '雾四炮');
  localStorage.setItem(LY_NAME_KEY, LY.name);
  localStorage.setItem('tc.field', LY.field);
  LY.sel = null;
  lyNormalizeRules();
  lyRender();
  if (typeof plAddBank === 'function' && d.plan) {
    plAddBank(d.plan, d.name || '雾四炮');
  }
  msg.textContent = '已载入「' + lyFullName() + '」的阵型与 N6s 阵解'
    + '（54s 循环、双冰单核；换 P3n / S3 / C4io 请在「节奏型」里选）';
  tcTab('layout');
}
document.getElementById('help-fe4').onclick = tcLoadFe4;

lyRender();

/* ---------------- 出怪勾选 ---------------- */
const kindsEl = document.getElementById('kinds');
const sel = new Set();
const groups = {};
META.kinds.forEach(k => (groups[k.group] = groups[k.group] || []).push(k));
Object.keys(groups).forEach(g => {
  const row = document.createElement('div'); row.className = 'grp';
  const nm = document.createElement('div'); nm.className = 'gname'; nm.textContent = g;
  const box = document.createElement('div'); box.className = 'kzs';
  groups[g].forEach(k => {
    const lab = document.createElement('label'); lab.className = 'kz';
    lab.dataset.k = k.name;
    lab.innerHTML = '<input type="checkbox"><span>' + k.name + '</span>' +
                    (k.hp ? '<em>' + k.hp + '</em>' : '') +
                    (k.note ? '<em>' + k.note + '</em>' : '');
    lab.onclick = e => { e.preventDefault(); toggle(k.name); };
    box.appendChild(lab);
  });
  row.appendChild(nm); row.appendChild(box); kindsEl.appendChild(row);
});
function toggle(k){
  if (lyBanned().has(k)) { document.getElementById('pickinfo').textContent =
      '「' + k + '」在当前场地不会出现，不能选'; return; }
  if (sel.has(k)) sel.delete(k); else sel.add(k);
  syncKinds();
}
/* ★ 2026-10-22：场地有出怪限制的，直接在沙盘里锁掉、不让选
   （DE/NE/RE 不出水生怪；RE 还不出 舞王 / 矿工）。 */
function lyBanned(){
  const f = lyFieldInfo(LY.field);
  return new Set((f.ban || []));
}
function syncKinds(){
  const ban = lyBanned();
  [...sel].forEach(k => { if (ban.has(k)) sel.delete(k); });
  document.querySelectorAll('.kz').forEach(el => {
    const k = el.dataset.k;
    const off = ban.has(k);
    el.classList.toggle('on', sel.has(k));
    el.classList.toggle('off', off);
    el.title = off ? ('场地 ' + LY.field + ' 不会出现这种僵尸') : '';
    if (off && el.dataset.was !== '1') {
      el.dataset.was = '1';
      const em = el.querySelector('em.ban');
      if (!em) {
        const s = document.createElement('em');
        s.className = 'ban'; s.textContent = '场地禁出';
        el.appendChild(s);
      }
    } else if (!off && el.dataset.was === '1') {
      el.dataset.was = '0';
      const em = el.querySelector('em.ban');
      if (em) em.remove();
    }
  });
  const info = document.getElementById('pickinfo');
  const nban = META.kinds.filter(k => ban.has(k.name)).length;
  info.textContent = (sel.size ? ('已选 ' + sel.size + ' 种') : '未选')
    + (nban ? ('　（场地 ' + LY.field + ' 禁出 ' + nban + ' 种，已锁定）') : '');
}
function setSel(list){
  sel.clear(); list.forEach(k => sel.add(k)); syncKinds();
}
const presetsEl = document.getElementById('presets');
META.presets.forEach(p => {
  const b = document.createElement('button');
  b.textContent = p.name; b.onclick = () => { setSel(p.kinds); document.getElementById('name').value = p.name + '关'; };
  presetsEl.appendChild(b);
});
/* ★ 2026-10-22：推荐组合增加「全出怪」—— 勾选这个场地**允许出现的所有僵尸**
   （自动排除场地禁出的：DE/NE 无水生、NE 无冰车、RE 无舞王/矿工…） */
{
  const all = document.createElement('button');
  all.textContent = '全出怪';
  all.title = '勾选当前场地允许出现的所有僵尸';
  all.onclick = () => {
    const ban = lyBanned();
    setSel(META.kinds.map(k => k.name).filter(n => !ban.has(n)));
    document.getElementById('name').value = '全出怪·' + LY.field;
  };
  presetsEl.appendChild(all);
}
document.getElementById('selnone').onclick = () => setSel([]);
renderFieldPick();

/* ---------------- 待模拟列表 ---------------- */
function renderQueue(){
  const tb = document.getElementById('queue');
  if (!queue.length){
    tb.innerHTML = '<tr><td colspan="4" class="dim">还没有排队的组合</td></tr>';
    return;
  }
  tb.innerHTML = queue.map((j, i) =>
    '<tr><td><b>' + esc(j.name) + '</b>' +
    (j.field && j.field !== 'PE' ? ' <span class="pltag">' + esc(j.field) + '</span>' : '') +
    '</td><td class="dim">' + esc(j.kinds.join('、')) +
    '</td><td>' + j.seeds + '</td><td><button class="ghost" data-i="' + i + '">删除</button></td></tr>'
  ).join('');
  tb.querySelectorAll('button[data-i]').forEach(b => {
    b.onclick = () => { queue.splice(+b.dataset.i, 1); renderQueue(); };
  });
  if (typeof renderRunMap === 'function') renderRunMap();
}
function esc(s){ return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

document.getElementById('add').onclick = () => {
  if (!sel.size){ alert('先勾几位僵尸吧'); return; }
  const nm = document.getElementById('name').value.trim() ||
             ('组合 ' + (queue.length + 1));
  const n = Math.max(1, Math.min(30, +document.getElementById('seeds').value || 1));
  queue.push({ name: nm, kinds: [...sel], seeds: n, field: LY.field,
               array: lyArrayForExport() });
  document.getElementById('name').value = '';
  renderQueue();
};

/* ---------------- 场地选择（v0.2.1 起移到「① 阵容布置」） ---------------- */
function renderFieldPick(){
  const note = document.getElementById('fieldnote');
  if (!note) return;
  const list = (MODELS.fields && MODELS.fields.list) || [];
  const f = list.find(x => x.code === LY.field);
  note.textContent = f ? ('当前场地：' + f.code + ' · ' + f.name + '　' + f.note) : '';
}

/* ---------------- 出怪列表：导入 / 导出 JSON ----------------
   文件格式（都认）：
     {"app":"trackcheck-spawn","jobs":[{"name":..,"kinds":[..],"seeds":n}]}
     [{"name":..,"kinds":[..],"seeds":n}]
     ["普通","路障",...]                     ← 单组
     {"组名":["普通",...], ...}               ← 多组
*/
function normJobs(d){
  const known = new Set(META.kinds.map(k => k.name));
  let arr = [];
  if (Array.isArray(d) && d.every(x => typeof x === 'string')) arr = [{ kinds: d }];
  else if (Array.isArray(d)) arr = d;
  else if (d && Array.isArray(d.jobs)) arr = d.jobs;
  else if (d && Array.isArray(d.kinds)) arr = [d];
  else if (d && typeof d === 'object'){
    arr = Object.keys(d).map(k => {
      const v = d[k];
      if (Array.isArray(v)) return { name: k, kinds: v };
      if (v && Array.isArray(v.kinds)) return Object.assign({ name: k }, v);
      return null;
    }).filter(Boolean);
  }
  return arr.map((x, i) => {
    let ks = (x && (x.kinds || x.zombies)) || (typeof x === 'string' ? [x] : []);
    if (typeof ks === 'string') ks = ks.split(/[,，、\s]+/);
    ks = (ks || []).filter(k => known.has(k));
    return { name: String((x && x.name) || ('导入 ' + (i + 1))),
             kinds: ks,
             field: (x && x.field) || 'PE',
             seeds: Math.max(1, Math.min(30, +(x && x.seeds) || 1)) };
  }).filter(x => x.kinds.length);
}

document.getElementById('exp').onclick = () => {
  let jobs = queue.slice();
  if (!jobs.length && sel.size){
    jobs = [{ name: document.getElementById('name').value.trim() || '当前勾选',
              kinds: [...sel],
              field: LY.field,
              array: lyArrayForExport(),
              seeds: Math.max(1, Math.min(30, +document.getElementById('seeds').value || 1)) }];
  }
  if (!jobs.length){ alert('列表和勾选都是空的，没东西可导出'); return; }
  const data = { app: 'trackcheck-spawn', version: 1,
                 savedAt: new Date().toISOString(), jobs: jobs };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '出怪列表.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  document.getElementById('status').textContent = '已导出 ' + jobs.length + ' 组';
};

document.getElementById('imp').onclick = () => document.getElementById('file').click();
document.getElementById('file').onchange = ev => {
  const f = ev.target.files && ev.target.files[0];
  if (!f) return;
  const rd = new FileReader();
  rd.onload = () => {
    let d;
    try { d = JSON.parse(rd.result); }
    catch (err){ alert('不是合法的 JSON：' + err.message); return; }
    const jobs = normJobs(d);
    if (!jobs.length){ alert('文件里没有可用的出怪组合（僵尸名要能对上）'); return; }
    if (queue.length){
      const rep = confirm('列表里已有 ' + queue.length + ' 组。\n确定 = 用文件内容替换；取消 = 追加在后面。');
      queue = rep ? jobs : queue.concat(jobs);
    } else queue = jobs;
    renderQueue();
    document.getElementById('status').textContent = '已导入 ' + jobs.length + ' 组';
  };
  rd.readAsText(f, 'utf-8');
  ev.target.value = '';
};

/* ---------------- 单组报告 → PDF ----------------
   后端优先调本机 Edge/Chrome 无头打印（真 PDF）；
   找不到浏览器时后端回一张打印页，这里把它写进新窗口自动打印（另存为 PDF）。
*/
document.addEventListener('click', async e => {
  const b = e.target.closest ? e.target.closest('button[data-pdf]') : null;
  if (!b) return;
  const url = '/api/pdf?id=' + b.dataset.pdf;
  const old = b.textContent;
  b.disabled = true; b.textContent = '生成中…';
  try {
    const r = await fetch(url);
    const ct = r.headers.get('Content-Type') || '';
    if (ct.includes('application/pdf')){
      const blob = await r.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (b.dataset.name || '运阵报告').replace(/[\\/:*?"<>|]/g, '_') + '.pdf';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    } else {
      const w = window.open('', '_blank');
      if (w){ w.document.write(await r.text()); w.document.close(); }
      else alert('浏览器拦了新窗口，请允许弹窗后重试');
    }
  } catch (err){
    alert('生成 PDF 失败：' + err.message);
  } finally {
    b.disabled = false; b.textContent = old;
  }
});

/* ---------------- 桌面版：心跳 + 退出 ----------------
   桌面版 TrackCheck.exe 是"后台跑一个本地服务 + 打开浏览器"：
   这里每 10s 打一次心跳，关掉页面之后服务会自己退（--idle-exit）。
*/
if (META.desktop){
  const q = document.getElementById('quit');
  q.style.display = '';
  q.onclick = async () => {
    if (!confirm('退出 TrackCheck？（这个页面会失效，可以直接关掉）')) return;
    try { await fetch('/api/quit'); } catch (e){}
    document.body.innerHTML =
      '<div class="panel" style="margin:60px auto;max-width:520px;text-align:center">'
      + '<div class="ptitle" style="border:0;padding:0">已退出</div>'
      + 'TrackCheck 已经关闭，这个页面可以关掉了。</div>';
  };
  setInterval(() => fetch('/api/ping').catch(() => {}), 10000);
  fetch('/api/ping').catch(() => {});
}

/* ---------------- 运行页：阵解 ↔ 出怪 对照 ---------------- */
function renderRunMap(){
  const box = document.getElementById('runmap');
  if (!box) return;
  if (!queue.length){
    box.innerHTML = '<div class="hint">出怪列表是空的 —— 先去「① 出怪沙盘」加几组</div>';
    return;
  }
  const bank = (typeof PLAN !== 'undefined' && PLAN.bank) ? PLAN.bank : [];
  box.innerHTML = '<table class="maptable"><tr><th>出怪组</th><th>种类</th>'
    + '<th>次数</th><th>阵解</th></tr>' + queue.map(function (it, i) {
      const b = bank.find(function (x) { return x.id === it.planId; });
      const name = b ? (b.plan.name || b.id) : '<span class="dim">（不绑阵解 · 空轨道）</span>';
      return '<tr><td><b>' + esc(it.name) + '</b></td><td class="dim">'
        + esc((it.kinds || []).join('、')) + '</td><td>' + (it.seeds || 1)
        + '</td><td>' + name + '</td></tr>';
    }).join('') + '</table>';
  if (!bank.length){
    box.innerHTML += '<div class="hint" style="margin-top:6px">'
      + '还没打开过「阵解编辑」—— 那几组会全部按空轨道跑（只跑自然输出）。</div>';
  }
}

document.getElementById('start').onclick = async () => {
  if (!queue.length){ alert('列表是空的'); return; }
  const bank = (typeof PLAN !== 'undefined' && PLAN.bank) ? PLAN.bank : [];
  const jobs = queue.map(function (it) {
    const b = bank.find(function (x) { return x.id === it.planId; });
    const job = { name: it.name, kinds: it.kinds, seeds: it.seeds,
                  field: it.field || LY.field,
                  layout: lyBareName(LY.name),
                  array: it.array || lyArrayForExport() };
    if (b) job.plan = b.plan;
    return job;
  });
  const payload = { jobs: jobs };
  document.getElementById('status').textContent = '已提交，后台开始跑……';
  const r = await fetch('/api/start', { method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  const d = await r.json();
  if (!d.ok){ document.getElementById('status').textContent = '提交失败：' + (d.error || ''); return; }
  rendered.clear();
  document.getElementById('results').innerHTML = '';
  poll();
};

document.getElementById('clear').onclick = async () => {
  await fetch('/api/clear', { method:'POST' });
  rendered.clear();
  document.getElementById('results').innerHTML = '';
  document.getElementById('status').textContent = '';
  if (polling){ clearTimeout(polling); polling = null; }
};

/* ---------------- 轮询与渲染 ---------------- */
async function poll(){
  const r = await fetch('/api/jobs');
  const d = await r.json();
  const box = document.getElementById('results');
  let running = 0;
  d.jobs.forEach(j => {
    if (j.status === 'running' || j.status === 'pending') running++;
    // ★ 每组一个固定 slot，**按任务顺序**建，内容后填 ——
    //   否则"先建占位、后补卡片"会让第 2 组的占位跑到第 1 组报告上面去。
    let el = document.getElementById('slot-' + j.id);
    if (!el){
      el = document.createElement('div');
      el.id = 'slot-' + j.id;
      el.className = 'slot';
      box.appendChild(el);
    }
    if (j.html){
      if (!rendered.has(j.id)){ rendered.add(j.id); el.innerHTML = j.html; }
    } else {
      el.innerHTML = '<div class="job"><div class="jname">' + esc(j.name) + '</div>' +
        '<div class="prog">自动判定节奏 <b>' + j.tier + '</b>　' +
        (j.status === 'pending' ? '排队中…'
          : j.status === 'error' ? '<span class="bad">出错（见控制台）</span>'
          : ('模拟中 ' + j.progress + ' / ' + j.seeds)) + '</div></div>';
    }
  });
  document.getElementById('status').textContent = running
    ? ('模拟中…… 还有 ' + running + ' 组') : (d.jobs.length ? '全部完成' : '');
  if (running) polling = setTimeout(poll, 700);
}

/* ---------------- 时间轴 tooltip ---------------- */
const tip = document.getElementById('tip');
function bindTips(){ /* 用事件委托，无需逐个绑定 */ }
function findHot(t){
  while (t && t !== document.body){
    if (t.classList && t.classList.contains('wvhot')) return t;
    t = t.parentNode;
  }
  return null;
}
document.addEventListener('mouseover', e => {
  const el = findHot(e.target);
  if (!el) return;
  const card = el.closest('.card');
  if (!card) return;
  const node = card.querySelector('script.wvjson');
  if (!node) return;
  let data; try { data = JSON.parse(node.textContent); } catch (err) { return; }
  const d = data[el.getAttribute('data-w')];
  if (!d) return;
  tip.innerHTML = d.html; tip.style.display = 'block'; moveTip(e);
});
document.addEventListener('mousemove', moveTip);
document.addEventListener('mouseout', e => {
  if (!findHot(e.target)) return;
  tip.style.display = 'none';
});
function moveTip(e){
  if (tip.style.display !== 'block') return;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + 16, y = e.clientY + 16;
  if (x + w > innerWidth - 8) x = e.clientX - w - 16;
  if (y + h > innerHeight - 8) y = e.clientY - h - 16;
  if (x < 6) x = 6; if (y < 6) y = 6;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
window.addEventListener('scroll', () => { tip.style.display = 'none'; }, true);

/* ---------------- 设置（齿轮） ---------------- */
const NAMING_KEY = 'tc.naming';
function tcNaming() {
  const ok = (MODELS.naming.options || []).map(o => o.id);
  const v = localStorage.getItem(NAMING_KEY);
  return ok.indexOf(v) >= 0 ? v : (MODELS.naming.default || 'both');
}
function tcSetNaming(v) {
  localStorage.setItem(NAMING_KEY, v);
  renderSettings();
  // class 脚本里的 PLAN 是词法全局，不是 window 属性 —— 得用 typeof 判断
  if (typeof plRender === 'function' && typeof PLAN !== 'undefined' && PLAN.cat) {
    try { plRender(); } catch (e) {}
  }
}
const LV_TAG = { full: '全程', part: '部分', watch: '仅提示', data: '仅数据',
                 action: '一次性', todo: '未建模', shape: '仅坐标', none: '未建模' };
function lvTag(lv) {
  return '<span class="lvtag lv-' + lv + '">' + (LV_TAG[lv] || lv) + '</span>';
}
function tcTab(which) {
  const map = { layout: 'tab-layout', spawn: 'tab-spawn', plan: 'planpage',
                run: 'tab-run', settings: 'tab-settings', help: 'tab-help' };
  Object.keys(map).forEach(function (k) {
    const el = document.getElementById(map[k]);
    if (el) el.style.display = (k === which ? '' : 'none');
  });
  for (const b of document.querySelectorAll('.tabs button'))
    b.classList.toggle('on', b.dataset.tab === which);
  const g = document.getElementById('gear');
  if (g) g.classList.toggle('on', which === 'settings');
  if (which === 'settings') renderSettings();
  if (which === 'layout') lyRender();
  if (which === 'spawn') renderFieldPick();
  if (which === 'plan' && typeof plEnterPlan === 'function') plEnterPlan();
  if (which === 'run' && typeof renderRunMap === 'function') renderRunMap();
}
function renderSettings() {
  const cur = tcNaming();
  document.getElementById('set-naming').innerHTML = (MODELS.naming.options || []).map(function (o) {
    return '<label class="hint" style="cursor:pointer">'
      + '<input type="radio" name="tc-naming" value="' + o.id + '"'
      + (o.id === cur ? ' checked' : '') + '> <b>' + o.label + '</b>'
      + '<span class="hint">(' + o.note + ')</span></label>';
  }).join('');
  const opt = (MODELS.naming.options || []).find(function (o) { return o.id === cur; });
  document.getElementById('set-naming-note').textContent = opt ? opt.note : '';
  for (const el of document.querySelectorAll('input[name="tc-naming"]')) {
    el.onchange = function () { tcSetNaming(el.value); };
  }

  // ★ 2026-10-22：阵型字符串格式（PvZ Tools 旧 / PvZ Toolkit 新）
  const af = tcArrayFmt();
  const fmts = LYC.formats || [];
  document.getElementById('set-arrayfmt').innerHTML = fmts.map(function (o) {
    return '<label class="hint" style="cursor:pointer">'
      + '<input type="radio" name="tc-arrayfmt" value="' + o.id + '"'
      + (o.id === af ? ' checked' : '') + '> <b>' + o.label + '</b>'
      + '<span class="hint">(' + o.note + ')</span></label>';
  }).join('');
  const afo = fmts.find(function (o) { return o.id === af; });
  document.getElementById('set-arrayfmt-note').textContent = afo
    ? ('当前：' + afo.label + '　·　' + afo.note) : '';
  for (const el of document.querySelectorAll('input[name="tc-arrayfmt"]')) {
    el.onchange = function () { tcSetArrayFmt(el.value); };
  }

  // ★ 2026-10-22：轨道简写 / 复写（对称操作写一个还是一对）
  const pmBox = document.getElementById('set-pair');
  if (pmBox) {
    const modes = (typeof PLAN !== 'undefined' && PLAN.cat && PLAN.cat.pair_modes) || [];
    const curPm = (typeof plPairMode === 'function') ? plPairMode() : 'auto';
    pmBox.innerHTML = modes.map(function (o) {
      return '<label class="hint" style="cursor:pointer">'
        + '<input type="radio" name="tc-pair" value="' + o.id + '"'
        + (o.id === curPm ? ' checked' : '') + '> <b>' + o.label + '</b></label>';
    }).join('') || '<span class="hint">（阵解页还没加载）</span>';
    for (const el of document.querySelectorAll('input[name="tc-pair"]')) {
      el.onchange = function () { plSetPairMode(el.value); };
    }
    const noteEl = document.getElementById('set-pair-note');
    if (noteEl) {
      noteEl.innerHTML = '简写：<code>P|P|P|P</code> = 一对炮 × 4（8 门）；'
        + '复写：<code>PP|PP|PP|PP</code> 才是一对。'
        + '分场写法 <code>P/P</code> 本身就表示一对，不会再翻倍。'
        + '核 / 冰 / 灰烬只有一张卡，不参与翻倍。';
    }
  }

  const pl = MODELS.plants || {};
  const box = function (list) {
    return list.map(function (p) {
      return '<tr><td class="n">' + esc(p.name) + '</td><td class="n">' + lvTag(p.level) + '</td>'
        + '<td>' + esc(p.note || '') + '</td></tr>';
    }).join('');
  };
  document.getElementById('set-plants').innerHTML =
    '<div class="hint" style="margin-bottom:6px">选卡里可选 ' + (pl.all || []).length
    + ' 张（含' + esc(pl.mimic || '模仿者') + '）；其中 '
    + (pl.modeled || []).length + ' 张参与模拟，其余只当占格/未建模。</div>'
    + '<table class="modeltab"><tr><th style="width:110px">植物</th>'
    + '<th style="width:76px">程度</th><th>简化模型等价于</th></tr>'
    + box(pl.modeled || []) + '</table>'
    + '<div class="hint" style="margin-top:8px">只在选卡里可选、还没有行为的：'
    + (pl.pending || []).map(function (x) { return '<span class="pltag">' + esc(x) + '</span>'; }).join(' ')
    + '</div>';

  document.getElementById('set-zombies').innerHTML =
    '<table class="modeltab"><tr><th style="width:86px">僵尸</th>'
    + '<th style="width:76px">程度</th><th style="width:64px">总血</th>'
    + '<th>简化模型等价于</th></tr>'
    + (MODELS.zombies || []).map(function (z) {
      return '<tr><td class="n">' + esc(z.name) + '</td><td class="n">' + lvTag(z.level)
        + '</td><td class="n">' + (z.hp || '') + '</td><td>' + esc(z.note || '') + '</td></tr>';
    }).join('') + '</table>';

  const f = MODELS.fields || {};
  document.getElementById('set-fields').innerHTML =
    '<table class="modeltab"><tr><th style="width:56px">场地</th>'
    + '<th style="width:150px">名称</th><th style="width:76px">程度</th>'
    + '<th>简化模型等价于</th></tr>'
    + (f.list || []).map(function (x) {
      return '<tr><td class="n"><b>' + esc(x.code) + '</b></td><td>' + esc(x.name)
        + '</td><td class="n">' + lvTag(x.level) + '</td><td>' + esc(x.note) + '</td></tr>';
    }).join('') + '</table>'
    + '<div class="hint" style="margin-top:8px">' + esc(f.note || '') + '</div>';

  document.getElementById('set-about').innerHTML =
    'TrackCheck <b>' + esc(MODELS.version) + '</b>　·　阵解 JSON schema <code>'
    + esc(MODELS.schema) + '</code>　·　研究基线：PVZ 1.0.0.1051（EN）'
    + '<br>网页版不能写磁盘：阵解请用「导出 JSON」；桌面版保存到 %APPDATA%\\TrackCheck\\plans。';
}

/* ---------------- demo：?demo=1 自动排两组并开跑 ---------------- */
window.addEventListener('load', () => {
  if (!location.search.includes('demo')) return;
  setSel(META.presets[2].kinds);
  queue.push({ name: '快速关（预设）', kinds: META.presets[2].kinds, seeds: 3 });
  setSel(['普通', '路障', '白眼', '铁桶', '撑杆', '读报']);
  queue.push({ name: '自定义 · 只出白眼（应判中速）', kinds: [...sel], seeds: 3 });
  renderQueue();
  document.getElementById('start').click();
});
</script>
</body></html>
'''



def esc_html(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _page_css():
    """抠出主页面 <style> 里的卡片样式，PDF 页复用它，保证和屏幕同款"""
    try:
        return PAGE.split('<style>', 1)[1].split('</style>', 1)[0]
    except IndexError:
        return ''


def job_print_html(job, autoprint=False):
    """一组任务的**独立**报告页（单文件，可直接打印/存 PDF）"""
    name = job.get('name') or ('组 %s' % job.get('id'))
    js = ('<script>window.addEventListener("load",function(){window.print()});</script>'
          if autoprint else '')
    return ('<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">'
            '<title>%s · 运阵报告</title><style>%s\n'
            '@page{size:A4 landscape;margin:8mm}'
            'body{padding:0;background:#fff}'
            '.job{border:none;box-shadow:none;margin:0;padding:0}'
            '.tip,.noprint,.seedbox{display:none!important}'
            '</style></head><body>%s%s</body></html>'
            % (esc_html(name), _page_css(), job.get('html') or '', js))
