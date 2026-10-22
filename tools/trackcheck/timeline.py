"""timeline.py —— 导出某一局的完整事件时间轴（排障用）

用法：
    python -m tools.trackcheck.timeline 慢速 2      # 档位, seed
    python -m tools.trackcheck.timeline 慢速 2 --all  # 连同用卡一起列
"""
import argparse
import sys

sys.path.insert(0, '.')

from tools.trackcheck import config_dianbozhong as C
from tools.trackcheck import run as R


def show(tier, seed, show_all=False, tail=None):
    C.MODE = tier
    C._RED['plan'] = None
    r = R.run_once(seed)
    f = r.get('fail')
    print('=' * 74)
    print('%s  seed=%d   总 %.1fs   跑到 w%d   减速覆盖 %.1f%%   %s'
          % (tier, seed, r['t_end'] / 100.0, len(r['waves']), r['slow_cov'],
             ('崩：' + f['why']) if f else '跑完 20 波'))
    if f:
        print('   └ %s   @ %.1fs  w%d' % (f.get('detail') or '', f['t'] / 100.0, f['wave']))
    print('=' * 74)

    # 逐波
    print('\n【逐波刷新】')
    print(' 波  刷新(s)  间隔(s)   本波血   剩余    阈值  刷新原因')
    prev = 0
    for w in r['waves']:
        gap = (w['t'] - prev) / 100.0
        prev = w['t']
        print(' %2d  %7.2f  %7.2f  %7d  %6d   %.2f  %s'
              % (w['w'], w['t'] / 100.0, gap, w['total_hp'], w['remain'],
                 w['thr'], w['reason'] or ''))

    # 事件时间轴
    ev = []
    for e in r.get('log', []):
        ev.append((e['t'], e['sev'], e.get('what', ''),
                   ' '.join('%s=%s' % (k, v) for k, v in e.items()
                            if k in ('row', 'col', 'detail') and v is not None)))
    for a in r.get('actions', []):
        if a.get('ok') or show_all:
            ev.append((a['t'], 'CARD' if a.get('ok') else 'CARD✘',
                       a['name'], 'w%d' % a['wave']))
    for b in r.get('broken', []):
        ev.append((b['t'], 'BROKEN', b.get('what', ''), b.get('why', '')))
    ev.sort(key=lambda x: x[0])
    if tail:
        ev = ev[-tail:]

    print('\n【事件时间轴】')
    for t, sev, what, det in ev:
        print(' %7.2fs  %-7s %-26s %s' % (t / 100.0, sev, what, det))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('tier')
    ap.add_argument('seed', type=int)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--tail', type=int, default=0)
    a = ap.parse_args()
    show(a.tier, a.seed, a.all, a.tail or None)
