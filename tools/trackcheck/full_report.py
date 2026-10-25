"""full_report.py —— 四档各跑 N 局，输出详细运阵报告（Markdown）"""
import sys
from collections import Counter

sys.path.insert(0, '.')

from tools.trackcheck import config_dianbozhong as C
from tools.trackcheck import run as R

VIDEO = {'慢速': 15.84, '变速': 12.30, '快速': 10.24, '极速': 8.56}
N = int(sys.argv[1]) if len(sys.argv) > 1 else 8
OUT = 'tools/trackcheck/out_report.md'

lines = []


def w(s=''):
    lines.append(s)


def stat(xs):
    if not xs:
        return '—'
    xs = sorted(xs)
    return '%.2f (%.2f~%.2f)' % (sum(xs) / len(xs), xs[0], xs[-1])


w('# PE.电波钟无炮 · 运阵报告')
w()
w('> 模拟器：`tools/trackcheck`　阵型：15曾/7冰瓜/4大喷/6双花/4格睡着的冰/2伞/2香蒲，24南瓜（4梯）')
w('> 每档 %d 局；波长口径 = w10→w20 的间隔 ÷ 10 波（与录像同口径）' % N)
w()
w('## 一、总览')
w()
w('| 档 | 录像 | 模拟 | 偏差 | 跑完 | 减速覆盖 | 输出 |')
w('|---|---|---|---|---|---|---|')

detail = []
for tier in ('慢速', '变速', '快速', '极速'):
    C.MODE = tier
    ok = 0
    spans, covs, dpss, suns, pumps = [], [], [], [], []
    cards = Counter()
    fails = []
    wave_gaps = []
    for s in range(N):
        C.reset_spawn_state()
        r = R.run_once(s)
        ts = [x['t'] for x in r['waves']]
        if len(ts) >= 20:
            ok += 1
            spans.append((ts[19] - ts[9]) / 100.0 / 10.0)
            for a, b in zip(ts[:-1], ts[1:]):
                wave_gaps.append((b - a) / 100.0)
        if r.get('fail'):
            fails.append((s, r['fail']['why'], r['fail']['t'] / 100.0, len(r['waves'])))
        covs.append(r['slow_cov'])
        dpss.append(r['dps'])
        suns.append(r['sun_end'])
        pumps.append(r['pumpkin_lost'])
        for a in r['actions']:
            if a['ok']:
                cards[a['name']] += 1

    avg = sum(spans) / len(spans) if spans else 0
    dev = (avg - VIDEO[tier]) / VIDEO[tier] * 100 if spans else 0
    w('| %s | %.2fs | %s | %+.0f%% | **%d/%d** | %.0f%% | %.0f dps |'
      % (tier, VIDEO[tier], ('%.2fs' % avg) if spans else '—', dev, ok, N,
         sum(covs) / len(covs), sum(dpss) / len(dpss)))
    detail.append(dict(tier=tier, ok=ok, spans=spans, covs=covs, dpss=dpss,
                       suns=suns, pumps=pumps, cards=cards, fails=fails,
                       gaps=wave_gaps))

w()
w('## 二、逐档明细')
for d in detail:
    t = d['tier']
    w()
    w('### %s（%d/%d 跑完）' % (t, d['ok'], N))
    w()
    if d['spans']:
        w('- **波长**：%s s　（录像 %.2fs，偏差 %+.0f%%）'
          % (stat(d['spans']), VIDEO[t],
             (sum(d['spans']) / len(d['spans']) - VIDEO[t]) / VIDEO[t] * 100))
    if d['gaps']:
        gs = sorted(d['gaps'])
        w('- **单波间隔**：中位 %.1fs｜最短 %.1fs｜最长 %.1fs｜≥40s 的长波 %d 次'
          % (gs[len(gs) // 2], gs[0], gs[-1], sum(1 for x in gs if x >= 40)))
    w('- **减速覆盖**：%.0f%%（均值）　**输出**：%.0f dps'
      % (sum(d['covs']) / len(d['covs']), sum(d['dpss']) / len(d['dpss'])))
    w('- **阳光结余**：%.0f　**南瓜损耗**：%.1f 个/局'
      % (sum(d['suns']) / len(d['suns']), sum(d['pumps']) / len(d['pumps'])))
    w('- **用卡（全 %d 局合计）**：%s'
      % (N, '、'.join('%s×%d' % (k, v) for k, v in d['cards'].most_common())))
    if d['fails']:
        w('- **崩阵**：' + '；'.join('seed%d %s @%.0fs(w%d)' % (s, why, tt, wv)
                                   for s, why, tt, wv in d['fails']))
    else:
        w('- **崩阵**：无')

w()
w('## 三、结论')
w()
w('（见正文）')

open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
print('\n-> %s' % OUT)
