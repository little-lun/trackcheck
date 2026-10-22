"""
compare_video.py —— 录像实测 vs 模拟器，同口径对照

录像口径：w10 红字 → w20 红字 的有效间隔 ÷ 10 波
模拟口径：t(w20) - t(w10) ÷ 10 波（**不是**总时长÷20，两者差很多）

用法：
    python -m tools.trackcheck.compare_video
"""
import sys

sys.path.insert(0, '.')

from tools.trackcheck import config_dianbozhong as C
from tools.trackcheck import run as R

VIDEO = {'慢速': 15.84, '变速': 12.30, '快速': 10.24, '极速': 8.56}
SEEDS = 5

print('录像 vs 模拟器（同口径：w10→w20 有效间隔 ÷ 10）')
print('=' * 68)
print('%-5s %9s %9s %8s %7s %s' % ('档', '录像', '模拟', '偏差', '跑完', '备注'))
print('-' * 68)
for tier in ('慢速', '变速', '快速', '极速'):
    C.MODE = tier
    spans, ok = [], 0
    for s in range(SEEDS):
        C._RED['plan'] = None
        r = R.run_once(s)
        ts = [w['t'] for w in r['waves']]
        if len(ts) >= 20:
            ok += 1
            spans.append((ts[19] - ts[9]) / 100.0)
    v = VIDEO[tier]
    if spans:
        m = sum(spans) / len(spans) / 10.0
        note = '吻合' if abs(m - v) / v < 0.15 else ('偏快' if m < v else '偏慢')
        print('%-5s %8.2fs %8.2fs %+7.0f%% %5d/%d %s'
              % (tier, v, m, 100 * (m - v) / v, ok, SEEDS, note))
    else:
        print('%-5s %8.2fs %9s %8s %5d/%d 跑不完（见报告）'
              % (tier, v, '—', '—', ok, SEEDS))
print('=' * 68)
