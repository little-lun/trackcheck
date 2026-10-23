# -*- coding: utf-8 -*-
"""
jobs.py —— 任务队列：建任务 / 逐种子推进 / 汇总 / 渲染成报告卡片

★ 为什么单独一层：同一套排队逻辑要跑在两种壳里 ——

    本地服务（app.py，桌面版）   后台线程 `while jobs.step(): pass`
    单文件网页（Pyodide）        前端 JS 每跑完一局 await 一次 step()

两边都是"一步一步推进"，所以这里**只管 step()，自己不碰线程/网络**。
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.trackcheck import config_dianbozhong as CFG   # noqa: E402
from tools.trackcheck import html_report as H            # noqa: E402
from tools.trackcheck import run as RUN                  # noqa: E402
from tools.trackcheck import spawn as SP                 # noqa: E402
from tools.trackcheck import ui                          # noqa: E402

esc_html = ui.esc_html       # render_job 里要用

JOBS = []
_seq = [0]


def _new_id():
    _seq[0] += 1
    return _seq[0]


def create_jobs(specs):
    """specs: [{name, kinds, seeds, field}] → 建好任务（**不跑**，等 step() 推进）"""
    from . import fields as F
    made = []
    for sp in specs:
        kinds = [k for k in (sp.get('kinds') or []) if k in SP.Z]
        fld = F.get(sp.get('field'))
        # ★ 场地禁出的僵尸（NE 无冰车 / RE 无舞王矿工潜水海豚）直接剔除
        kinds = [k for k in kinds if fld.allows(k)]
        if not kinds:
            continue
        seeds = max(1, min(30, int(sp.get('seeds') or 1)))
        tier, reason = ui.pick_tier(kinds)
        job = dict(id=_new_id(),
                   name=(sp.get('name') or '').strip() or ('组合 %d' % _seq[0]),
                   kinds=kinds, seeds=seeds, tier=tier,
                   solve=ui.SOLVE_ALIAS.get(tier, tier), reason=reason,
                   # ★ v0.2 阵解栏：None = 内置判定轨道；dict = 编辑出来的阵解
                   plan=(sp.get('plan') or None),
                   # ★ v0.2.2：每个出怪组各自带场地与阵型（来自「① 阵容布置」）
                   field=(sp.get('field') or 'PE'),
                   # ★ 2026-10-22：阵型名（裸名），报告里拼成 `[场地].名字`
                   layout=((sp.get('layout') or '').strip() or None),
                   array=(sp.get('array') or {}),
                   status='pending', progress=0, done=0, reports=[],
                   html=None, summary=None, seed_rows=None, error=None)
        JOBS.append(job)
        made.append(job)
    return made


def _deck_line(job):
    """报告头里的「选卡」一行 —— 有阵解就用阵解的卡组，没有就留空。

    ★ v0.2.2：以前这里写死"电波钟四档选卡"，阵型变成用户自己配之后没有意义了。
    """
    deck = ((job.get('plan') or {}).get('deck') or [])
    if not deck:
        return '<span class="dim">（没有选卡：未配置阵解）</span>'
    from . import plan as PL
    return '阵解选卡：' + '　'.join(PL.deck_label(c) for c in deck)


def _current():
    """正在跑的那组；没有就把第一个 pending 标成 running"""
    for j in JOBS:
        if j['status'] == 'running':
            return j
    for j in JOBS:
        if j['status'] == 'pending':
            j['status'] = 'running'
            return j
    return None


def step():
    """
    推进一个种子（= 一局模拟）。返回 None 表示队列空了。

    ★ 一次只跑一局：浏览器里一局要 1~2s（WASM 比 CPython 慢 2~3 倍），
      整组一起跑会把页面冻住；分开跑才能每局刷一次进度。
    """
    job = _current()
    if job is None:
        return None
    try:
        s = job['done']
        CFG.MODE = job['solve']          # ★ 阵解按 solve 走（中速 → 慢速档）
        CFG.KINDS_OVERRIDE = list(job['kinds'])
        CFG.FIELD = job.get('field') or 'PE'
        CFG.reset_spawn_state()          # 每组重新开始：红眼累计 / 逐波缓存清空
        from . import layout as LY
        arr = LY.to_engine(job.get('array') or {})
        r = RUN.run_once(s, plan=job.get('plan'), field=CFG.FIELD, array=arr)
        r['_tier'] = '%s / seed %d' % (job['tier'], s)
        job['reports'].append(r)
        job['done'] = s + 1
        job['progress'] = s + 1
        if job['done'] >= job['seeds']:
            _finalize(job)
    except Exception:
        job['status'] = 'error'
        job['error'] = traceback.format_exc(limit=6)
    return job


def run_all():
    """本地服务 / 命令行用：一直推到队列空"""
    while step() is not None:
        pass
    return JOBS


def _span(r):
    """常规波长（s）：第 1~9 波与第 11~19 波两段的平均"""
    ts = [w['t'] for w in r['waves']]
    if len(ts) < 20:
        return 0.0
    return ((ts[8] - ts[0]) / 800.0 + (ts[18] - ts[10]) / 800.0) / 2.0


def _finalize(job):
    """一组跑完：汇总 KPI → 逐种子明细 → 渲染代表局"""
    reports = job['reports']

    ok = sum(1 for r in reports if r['done'] and not r.get('fail'))
    spans = [_span(r) for r in reports if _span(r)]
    avg = sum(spans) / len(spans) if spans else 0

    # 只有"勾的就是那套预设"时才有录像可比：阵解要正好是 solve 档、且该档有录像
    is_preset = (set(job['kinds']) == set(CFG.TIERS.get(job['solve'], []))
                 and job['tier'] in H.VIDEO)
    ref = H.VIDEO.get(job['tier']) if is_preset else None
    dev = (100.0 * (avg / ref - 1)) if ref else None

    n = len(reports)
    job['summary'] = dict(
        n=n, ok=ok, avg=avg, dev=dev, ref=ref,
        sun=sum(r['sun_end'] for r in reports) / n,
        ice=sum(r['end_state']['ice_stock_perm'] for r in reports) / n,
        icecap=sum((r['end_state'].get('ice_cap') or 0) for r in reports) / n,
        rep=sum(r['end_state']['repairs'] for r in reports) / n,
        kn=sum(len(r['end_state']['kernel_log']) for r in reports) / n,
        crush=sum(r['end_state']['cars_crushed'] for r in reports),
        cov=sum(r.get('slow_cov', 0) for r in reports) / n,
        garlic=sum((r.get('garlic') or {}).get('n', 0) for r in reports) / n,
        fog=sum((r.get('fog') or {}).get('n', 0) for r in reports) / n,
        level=_worst_level(reports, dev),
    )
    job['seed_rows'] = [
        dict(seed=i, span=_span(r), fail=bool(r.get('fail')),
             ice=r['end_state']['ice_stock_perm'],
             rep=r['end_state']['repairs'],
             lost=len(r['end_state']['plants_lost']),
             crush=r['end_state']['cars_crushed'],
             lv=(lambda it: it[0]['lv'] if it else None)(H.classify(r, dev)))
        for i, r in enumerate(reports)]

    # 代表局：第一个没崩的；全崩就取第一个
    best = next((r for r in reports if not r.get('fail')), reports[0])
    job['html'] = render_job(job, best, dev)
    job['status'] = 'done'


def _worst_level(reports, dev):
    """最严重的一级 —— LEVEL_RANK 越小越严重（L0 < L1 < L2 < L3 < L4）。"""
    rank = 99
    lv = None
    for r in reports:
        for it in H.classify(r, dev):
            k = H.LEVEL_RANK[it['lv']]
            if k < rank:
                rank, lv = k, it['lv']
    return lv


def payload():
    """给前端轮询用的快照（**只带必要字段**，报告 HTML 已经在里面）"""
    return [dict(id=j['id'], name=j['name'], kinds=j['kinds'], seeds=j['seeds'],
                 field=j.get('field') or 'PE',
                 tier=j['tier'], solve=j.get('solve'), reason=j['reason'],
                 plan_name=((j.get('plan') or {}).get('name')),
                 status=j['status'], progress=j['progress'], html=j['html'],
                 summary=j['summary'], error=j['error'])
            for j in list(JOBS)]


def clear():
    JOBS.clear()


def _fmt_dev(dev):
    if dev is None:
        return '<span class="dim">自定义（无参照）</span>'
    cls = 'ok' if abs(dev) < 10 else 'warn'
    return '<b class="%s">%+.0f%%</b>' % (cls, dev)


def render_job(job, rep, dev):
    s = job['summary']
    lvl = s['level']
    badge = (H.level_badge(lvl) if lvl
             else '<span class="lv" style="background:#059669">零偏离</span>')

    rows = ''.join(
        '<tr><td>%d</td><td>%.2f s</td><td class="%s">%s</td><td>%d</td>'
        '<td>%d</td><td>%d</td><td>%d</td><td>%s</td></tr>'
        % (x['seed'], x['span'], 'bad' if x['fail'] else 'ok',
           '崩' if x['fail'] else '通',
           x['ice'], x['rep'], x['lost'], x['crush'],
           H.level_badge(x['lv']) if x['lv'] else '—')
        for x in job['seed_rows'])

    kinds_txt = '、'.join(job['kinds'])
    card = H.card_html(rep, dev)
    ice_txt = ('存冰 <b>%.1f</b>/%d' % (s['ice'], round(s.get('icecap') or 0))
               if s.get('icecap')
               else '存冰 <b class="dim">—</b><span class="dim">（夜场不存冰）</span>')

    struct_txt = ''
    if s.get('fog'):
        struct_txt = '<span>结构位补种 <b>%.1f</b> 次/局</span>' % s['fog']
    elif s.get('garlic'):
        struct_txt = '<span>大蒜换行 <b>%.0f</b> 次/局</span>' % s['garlic']

    # ★ v0.2.2：这组跑的是哪套阵解（空轨道 / 编辑出来的积木阵解）
    pname = (job.get('plan') or {}).get('name')
    if pname:
        from . import plan as PL
        pname = PL.full_name(job.get('plan'))
        plan_txt = ('<span class="jplan">阵解：<b>%s</b>（积木版）</span>'
                    % esc_html(pname))
    else:
        plan_txt = ('<span class="jplan dim">阵解：未配置'
                    '（空轨道 —— 只跑自然输出）</span>')
    # ★ v0.2.1：场地（PE 是默认，其它场地显式标出来）
    from . import fields as F
    fld = F.get(job.get('field'))
    field_txt = ('　<span class="jplan"><b>%s</b> · %s（%d 行）</span>'
                 % (fld.code, esc_html(fld.name), fld.rows)
                 if fld.code != 'PE' else '')
    # ★ 2026-10-22：阵型名 `[场地].名字`（`[场地].` 自动生成）
    layout_txt = ('　<span class="jplan">阵型：<b>%s</b></span>'
                  % esc_html('[%s].%s' % (fld.code, job['layout']))
                  if job.get('layout') else '')

    return ('<div class="job">'
            '<div class="jobhead">'
            '<div class="jacts"><button class="ghost noprint" data-pdf="%d" '
            'data-name="%s">⤓ 下载 PDF</button></div>'
            '<div class="jname">%s</div>'
            '<div class="jmeta">自动判定节奏 <b class="tier">%s</b>　%s　%s%s%s</div>'
            '<div class="jwhy">%s</div>'
            '<div class="jdeck">%s</div>'
            '</div>'
            '<div class="jstrip">'
            '<span>出怪（%d 种）：%s</span>'
            '<span>种子 <b>%d</b>　跑完 <b class="%s">%d / %d</b></span>'
            '<span>常规波长 <b>%.2f s</b>　偏差 %s</span>'
            '<span>减速覆盖 <b>%.0f%%</b>　核 <b>%.1f</b> 个/局　碾压 <b class="%s">%d</b></span>'
            '<span>阳光 <b>%.0f</b>　%s　补南瓜 <b>%.1f</b> 次</span>'
            '%s'
            '<span>最高等级 %s</span>'
            '</div>'
            '<details class="seedbox"><summary>逐种子明细（%d 局）</summary>'
            '<table class="mini"><tr><th>种子</th><th>常规波长</th><th>结果</th>'
            '<th>存冰</th><th>补南瓜</th><th>植物损失</th><th>冰车碾压</th><th>等级</th></tr>'
            '%s</table></details>'
            '%s'
            '</div>'
            % (job['id'], esc_html(job['name']), job['name'], job['tier'],
               badge, plan_txt, layout_txt, field_txt, job['reason'],
               _deck_line(job),
               len(job['kinds']), kinds_txt,
               job['seeds'], 'ok' if s['ok'] == s['n'] else 'bad', s['ok'], s['n'],
               s['avg'], _fmt_dev(dev),
               s['cov'], s['kn'], 'ok' if s['crush'] == 0 else 'bad', s['crush'],
               s['sun'], ice_txt, s['rep'], struct_txt,
               badge, s['n'], rows, card))
