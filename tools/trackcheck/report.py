# -*- coding: utf-8 -*-
"""report.py —— 生成自包含 HTML 报告（无外部依赖，双击即开）"""

import html


def _svg_bars(waves, w=1000, h=220):
    """每波间隔柱状图 + 剩余血量折线"""
    if not waves:
        return ''
    n = len(waves)
    max_gap = max(x['gap'] for x in waves) or 1
    bw = (w - 60) / n
    bars, line = [], []
    for i, x in enumerate(waves):
        bh = (x['gap'] / max_gap) * (h - 50)
        X = 40 + i * bw
        Y = h - 25 - bh
        bars.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#5b8def" opacity="0.75"/>'
                    % (X, Y, bw * 0.7, bh))
        bars.append('<text x="%.1f" y="%.1f" font-size="9" fill="#666" text-anchor="middle">%d</text>'
                    % (X + bw * 0.35, h - 10, x['w']))
        # 剩余比例折线
        ratio = (x['remain'] / x['total_hp']) if x['total_hp'] else 0
        ly = h - 25 - ratio * (h - 50)
        line.append('%.1f,%.1f' % (X + bw * 0.35, ly))
    return ('<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">'
            '<line x1="40" y1="%d" x2="%d" y2="%d" stroke="#ddd"/>'
            '%s<polyline points="%s" fill="none" stroke="#e2574c" stroke-width="2"/>'
            '<text x="4" y="20" font-size="10" fill="#888">柱=波长(最大%.1fs)</text>'
            '<text x="4" y="34" font-size="10" fill="#e2574c">线=波尾剩余血量比</text>'
            '</svg>') % (w, h, w, h - 25, w - 20, h - 25,
                         ''.join(bars), ' '.join(line), max_gap / 100)


def write_html(path, reports, summ, CFG, L1):
    r0 = reports[0]
    rows = []
    for x in r0['waves']:
        rows.append('<tr><td>%d</td><td>%.2f</td><td>%.2f</td><td>%d</td>'
                    '<td>%d</td><td>%.2f</td><td>%s</td></tr>'
                    % (x['w'], x['t'] / 100, x['gap'] / 100, x['total_hp'],
                       x['remain'], x['thr'], html.escape(x['reason'] or '')))

    c1 = []
    for c in L1['cards']:
        cls = 'ok' if c['ok'] else 'bad'
        c1.append('<tr class="%s"><td>%s</td><td>%d</td><td>%.1fs</td>'
                  '<td>%.1fs</td><td>%.1fs</td><td>%s</td></tr>'
                  % (cls, c['card'], c['used'], c['gap'] / 100, c['cd'] / 100,
                     c['margin'] / 100, 'OK' if c['ok'] else '断裂'))

    brk = ''.join('<li>%s × %d</li>' % (html.escape(k), v)
                  for k, v in sorted(summ['broken'].items(), key=lambda x: -x[1]))

    pupp = ''.join('<div class="cell">%s<br><b>%d</b></div>' % (k, v)
                   for k, v in sorted(r0['pumpkins'].items(),
                                      key=lambda x: (int(x[0].split('-')[0]), int(x[0].split('-')[1]))))

    doc = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>轨道验证器 · %(name)s</title>
<style>
body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
     background:#0f1115;color:#e6e6e6;margin:0;padding:28px 32px;line-height:1.7}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:28px 0 10px;color:#9ad}
.sub{color:#888;font-size:12px;margin-bottom:20px}
table{border-collapse:collapse;width:100%%;font-size:12px;margin:8px 0}
th,td{border-bottom:1px solid #262a33;padding:5px 8px;text-align:left}
th{color:#8b93a7;font-weight:500}
tr.ok td:nth-child(6){color:#3fb950} tr.bad td:nth-child(6){color:#f85149}
.cards{display:flex;flex-wrap:wrap;gap:10px}
.kpi{background:#171a21;border:1px solid #262a33;border-radius:8px;padding:12px 16px;min-width:130px}
.kpi b{display:block;font-size:22px;color:#fff}
.kpi span{font-size:11px;color:#8b93a7}
.cell{background:#171a21;border:1px solid #262a33;border-radius:6px;padding:6px 10px;font-size:11px;color:#8b93a7}
.cell b{color:#e6e6e6;font-size:13px}
.note{background:#1a1d24;border-left:3px solid #d29922;padding:10px 14px;font-size:12px;color:#c9d1d9;margin:14px 0}
.warn{border-left-color:#f85149}
</style></head><body>
<h1>轨道验证器 · %(name)s</h1>
<div class="sub">阵型：PE.电波钟无炮 ｜ 种子 %(n)d 个 ｜ 生成时间见文件属性</div>

<div class="cards">
  <div class="kpi"><b>%(ok)d/%(n)d</b><span>零断裂且跑完 20 波</span></div>
  <div class="kpi"><b>%(gap).1fs</b><span>平均波长</span></div>
  <div class="kpi"><b>%(lost).1f</b><span>南瓜平均打穿（共 24）</span></div>
  <div class="kpi"><b>%(sun)d</b><span>结余阳光</span></div>
</div>

<div class="note">
<b>L1 是确定层，L2 是近似层。</b>
L1（卡 CD / 运算量 / 阳光）不依赖任何物理假设，结论可以直接信；
L2（刷新、损耗）依赖速度与血量模型，看趋势不看小数点。
</div>

<h2>L1 · 卡 CD（零误差）</h2>
<div class="sub">循环 4 波 × %(wave).2fs = %(cyc).1fs</div>
<table><tr><th>卡片</th><th>用次</th><th>实际间隔</th><th>卡片 CD</th><th>余量</th><th>结论</th></tr>
%(c1)s</table>
<div class="sub">运算量：轨道给 %(ops)d，需求 %(need)d（4 波 × 2），缺口 %(gapops)d → 由 IO 补</div>
<div class="sub">阳光：收入 %(sinc)d / 循环，支出 %(sspd)d，净 %(snet)+d</div>

<h2>L2 · 逐波明细（seed 0）</h2>
%(svg)s
<table><tr><th>波</th><th>刷新(s)</th><th>间隔(s)</th><th>本波总血</th>
<th>波尾剩余</th><th>阈值</th><th>刷新原因</th></tr>
%(rows)s</table>

<h2>南瓜血线（seed 0 结束时）</h2>
<div class="cards">%(pupp)s</div>

<h2>轨道断裂</h2>
<ul style="font-size:12px;color:#f0883e">%(brk)s</ul>

<div class="note warn">
<b>已知误差来源（务必先读）：</b><br>
① 出怪脚本是<b>占位</b>，不是真实出怪 → L2 的绝对数值不可用，只能看趋势；<br>
② 僵尸速度基准 361cs/格 是由 06 的关键波长表反推的，与"普僵 4.7s/格"的社区口径冲突 30%%；<br>
③ 未建模：小丑爆炸、冰车碾压、矿工、蹦极、投篮、舞王召唤、珊瑚；<br>
④ 目标选择规则被简化（忧郁菇打范围内全部、冰瓜打最前一只）。
</div>
</body></html>""" % dict(
        name=html.escape(CFG.TRACK_NAME),
        n=summ['n'], ok=summ['ok'], gap=summ['gap_avg'] / 100,
        lost=summ['lost_avg'], sun=round(summ['sun_avg']),
        wave=L1['cycle_cs'] / 100 / 4, cyc=L1['cycle_cs'] / 100,
        c1=''.join(c1), ops=L1['ops_sum'], need=L1['ops_need'],
        gapops=L1['ops_need'] - L1['ops_sum'],
        sinc=L1['sun_income'], sspd=L1['sun_spend'], snet=L1['sun_net'],
        svg=_svg_bars(r0['waves']), rows=''.join(rows),
        pupp=pupp, brk=brk or '<li>无</li>',
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc)
