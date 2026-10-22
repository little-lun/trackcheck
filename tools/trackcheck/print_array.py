"""print_array.py —— 输出模拟器当前执行的阵图，用于人工核对"""
import sys
sys.path.insert(0, '.')
from tools.trackcheck import config_dianbozhong as C
from tools.trackcheck import data as D

SHORT = {'忧郁菇': '曾', '冰瓜': '瓜', '大喷菇': '喷', '保护伞': '伞',
         '双子花': '花', '存冰': '冰', '香蒲': '蒲', '玉米炮': '炮'}

rows = []
for r in range(1, 7):
    cells = []
    for c in range(1, 10):
        v = C.ARRAY.get((r, c))
        if not v:
            cells.append('·')
            continue
        name = SHORT.get(v['plant'], v['plant'])
        mark = '梯' if v.get('ladder') else ('∩' if v.get('pumpkin') else '')
        cells.append(name + mark)
    rows.append(cells)

print('| 行\\列 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |')
print('|---|---|---|---|---|---|---|---|---|---|')
for r in range(1, 7):
    tag = '%d 路' % r
    if r in (3, 4):
        tag += '(水)'
    print('| **%s** | %s |' % (tag, ' | '.join(rows[r-1])))

print()
cnt = {}
pk = lad = 0
for v in C.ARRAY.values():
    cnt[v['plant']] = cnt.get(v['plant'], 0) + 1
    pk += 1 if v['pumpkin'] else 0
    lad += 1 if v.get('ladder') else 0
print('植物：' + '、'.join('%s×%d' % (k, n) for k, n in sorted(cnt.items(), key=lambda x: -x[1])))
print('南瓜 %d（其中梯子 %d）' % (pk, lad))
print()
print('关键位：')
print('  核坑优先序 %s' % (C.KERNEL_SLOTS[:5],))
print('  辣椒位 %s   樱桃 %d 路（列序 %s）' % (C.CHILI_SLOT, C.CHERRY_ROW, C.CHERRY_COLS))
print('  垫材落点 %s' % D.STALL_SLOTS)
