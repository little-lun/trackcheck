# -*- coding: utf-8 -*-
"""
run.py —— 命令行入口

用法：
    python -m tools.trackcheck.run                  # 跑默认配置（电波钟），10 个种子
    python -m tools.trackcheck.run --seeds 30       # 跑 30 个种子
    python -m tools.trackcheck.run --html out.html  # 额外输出 HTML 报告
    python -m tools.trackcheck.run --no-rescue      # 关掉救场层（看"纯轨道"能撑多久）
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.trackcheck import data as D
from tools.trackcheck.engine import Sim
from tools.trackcheck import config_dianbozhong as CFG


def _plan_slots(plan):
    """阵解里写的坑位/落点 → 引擎的 slots（写了的用阵解的，没写的沿用配置）"""
    def _rc(x):
        return tuple(x) if isinstance(x, (list, tuple)) and len(x) == 2 else x

    def _rcs(xs):
        return [_rc(x) for x in (xs or [])]

    ps = (plan or {}).get('slots') or {}
    kernel = ps.get('kernel')
    temp_ice = ps.get('temp_ice')
    fast_fog = ps.get('fast_fog')
    return dict(kernel=_rcs(kernel) or getattr(CFG, 'KERNEL_SLOTS', None),
                chili_slot=_rc(ps.get('chili')) or getattr(CFG, 'CHILI_SLOT', None),
                cherry_row=ps.get('cherry_row') or getattr(CFG, 'CHERRY_ROW', None),
                temp_ice=_rcs(temp_ice) or getattr(CFG, 'TEMP_ICE_SLOTS', None),
                fast_fog=_rcs(fast_fog) or getattr(CFG, 'FAST_LUNGBU_SPOTS', None),
                garlic=(_rcs(ps.get('garlic')) if 'garlic' in ps
                        else CFG.garlic_slots()),
                struct_fog=(_rcs(ps.get('struct_fog')) if 'struct_fog' in ps
                            else CFG.struct_fog_slots()))


def run_once(seed, rescue=None, plan=None, field=None, array=None):
    """
    plan = None  → **空轨道**（不排任何操作，只看自然输出能撑多久）
    plan = dict  → 用**阵解栏编辑出来的轨道**（plan.compile_plan）
    field = None → 用 CFG.FIELD（默认 PE）
    array = None → 用 CFG.ARRAY（PE.电波钟无炮的示例阵型，仅供帮助页的示例用）
    """
    if field is None:
        field = ((plan or {}).get('field') or getattr(CFG, 'FIELD', None) or 'PE')
    if array is None:
        array = CFG.ARRAY
    if rescue is None:
        # ★ v0.2.2：默认**不开内置救场层**。救场交给阵解里的那一层
        #   （`rescue` / `rescue_simple`）。只有显式跑"内置示例轨道"时才按档位开。
        builtin = (plan is None and getattr(CFG, 'BUILTIN', False))
        rescue = (getattr(CFG, 'RESCUE_BY_TIER', {}).get(
            CFG.MODE, getattr(CFG, 'RESCUE', True)) if builtin else False)
    else:
        builtin = (plan is None and getattr(CFG, 'BUILTIN', False))
    track_fn, rescue_tick, globals_tick = (CFG.track if builtin
                                           else (lambda w, ctx: [])), None, None
    cherry_cols = list(getattr(CFG, 'CHERRY_COLS', [8, 9, 7, 6]))
    if plan:
        from tools.trackcheck import plan as P
        track_fn, rescue_tick, globals_tick = P.compile_plan(plan)
        cherry_cols = list(((plan.get('slots') or {}).get('cherry_cols')
                            or cherry_cols))
    slots = _plan_slots(plan) if plan else dict(
        kernel=getattr(CFG, 'KERNEL_SLOTS', None),
        chili_slot=getattr(CFG, 'CHILI_SLOT', None),
        cherry_row=getattr(CFG, 'CHERRY_ROW', None),
        temp_ice=getattr(CFG, 'TEMP_ICE_SLOTS', None),
        fast_fog=getattr(CFG, 'FAST_LUNGBU_SPOTS', None),
        garlic=CFG.garlic_slots(),
        struct_fog=CFG.struct_fog_slots())
    # ★ 2026-10-23 运阵模型：选卡里带了**阵型成分**（例：FE.雾四炮带大喷菇）
    #   → 这种植物死了以后持续判定补种。只算"选卡里有 & 阵型里也有"的主植物；
    #     南瓜/睡莲这类壳与基座不算（它们各有维护/重建逻辑）。
    replant = set()
    if plan:
        from tools.trackcheck import plan as P
        deck_core = set()
        for c in (plan.get('deck') or []):
            deck_core.add(P.mimic_target(c) or c)
        arr_plants = set()
        for spec in (array or {}).values():
            nm = (spec or {}).get('plant')
            if nm:
                arr_plants.add(P.mimic_target(nm) or nm)
        action_cards = {'寒冰菇', '毁灭菇', '樱桃', '辣椒', '窝瓜', '三叶草',
                        '咖啡豆', '大蒜'}
        replant = (deck_core & arr_plants) - action_cards
    sim = Sim(array, track_fn, CFG.wave_script, seed=seed,              total_waves=20, sun0=None, skip_hp=getattr(CFG, 'SKIP_HP', 0),
              slots=slots, cherry_cols=cherry_cols,
              rescue=rescue, repair=getattr(CFG, 'REPAIR', True),
              allow_ash=getattr(CFG, 'RESCUE_ASH', True),
              stall_waves=getattr(CFG, 'STALL_WAVES', {}).get(CFG.MODE, True),
              rebuild=getattr(CFG, 'REBUILD_BY_TIER', {}).get(CFG.MODE, False),
              wogua_flag=getattr(CFG, 'WOGUA_FLAG_BY_TIER', {}).get(CFG.MODE, True),
              rescue_tick=rescue_tick, globals_tick=globals_tick,
              field=field, replant=replant,
              deck_names=[P.mimic_target(c) or c
                          for c in ((plan or {}).get('deck') or [])])
    sim.plan = plan
    r = sim.run()
    # 供报告层决定卡槽显示（极速关有冰车/投篮 → 卡槽里没有大蒜）
    r['_kinds'] = CFG.active_kinds()
    r['_plan'] = (plan or {}).get('name') if plan else None
    # ★ 2026-10-22：把阵解的**真实选卡**交给报告层 —— 否则 hover 里的"卡槽"
    #   还是按档位猜出来的旧模板（经典八炮会显示成电波钟那 10 张）。
    r['_deck'] = list((plan or {}).get('deck') or [])
    r['_field'] = field
    return r


def summarize(reports):
    n = len(reports)
    ok = sum(1 for r in reports if r['done'] and not r['broken'] and not r.get('fail'))
    done = sum(1 for r in reports if r['done'] and not r.get('fail'))
    gaps = [r['avg_gap'] for r in reports if r['avg_gap']]
    lost = [r['pumpkin_lost'] for r in reports]
    suns = [r['sun_end'] for r in reports]
    brk = {}
    warn = {}
    for r in reports:
        for b in r['broken']:
            key = b['what'] + ' @w' + str(b['wave'])
            brk[key] = brk.get(key, 0) + 1
        for x in r['log']:
            if x['sev'] == 'WARN':
                base = x['what'].split('（')[0].split('被')[0]
                warn[base] = warn.get(base, 0) + 1
    return dict(
        n=n, ok=ok, done=done,
        gap_min=min(gaps) if gaps else 0,
        gap_max=max(gaps) if gaps else 0,
        gap_avg=sum(gaps) / len(gaps) if gaps else 0,
        lost_avg=sum(lost) / n,
        sun_avg=sum(suns) / n,
        broken=brk, warn=warn,
        rescue_avg=sum(r.get('n_rescue', 0) for r in reports) / n,
        norescue_avg=sum(r.get('n_norescue', 0) for r in reports) / n,
        kill_avg=sum(r.get('n_kill', 0) for r in reports) / n,
        dps_avg=sum(r.get('dps', 0) for r in reports) / n,
        slow_avg=sum(r.get('slow_cov', 0) for r in reports) / n,
    )


def print_l2(reports, s):
    print('=' * 72)
    print('L2 动态模拟（%d 个种子 · 饱和出怪 · 轮数 %d）' % (s['n'], CFG.ROUND))
    print('=' * 72)
    print('跑完 20 波    %d / %d' % (s['done'], s['n']))
    print('零断裂+无崩阵 %d / %d' % (s['ok'], s['n']))
    print('平均波长      %.1f s  （%d ~ %d cs）'
          % (s['gap_avg'] / 100, s['gap_min'], s['gap_max']))
    print('南瓜打穿      %.1f 个 / 局（共 %d 个）'
          % (s['lost_avg'], sum(1 for v in CFG.ARRAY.values() if v.get('pumpkin'))))
    print('结余阳光      %.0f' % s['sun_avg'])
    print('救场          %.1f 次 / 局（垫材+窝瓜）；无牌 %.1f 次' % (s['rescue_avg'], s['norescue_avg']))
    print('输出          %.0f dps（模拟实测，含溢出伤害）' % s['dps_avg'])
    print('减速覆盖      %.1f%%（前场非冰车僵尸处于减速的时间占比）' % s['slow_avg'])
    print()

    fails = [r for r in reports if r.get('fail')]
    if fails:
        print('-' * 72)
        print('★ 崩阵 %d / %d 局（FATAL 立即终止）' % (len(fails), s['n']))
        seen = set()
        for r in fails:
            f = r['fail']
            key = (f['why'], f['wave'] // 3)
            if key in seen:
                continue
            seen.add(key)
            print()
            print('  [w%d  t=%6.1fs]  %s' % (f['wave'], f['t'] / 100.0, f['why']))
            if f.get('detail'):
                print('      └ %s' % f['detail'])
            ctx = [x for x in r['log']
                   if x['t'] <= f['t'] and x['row'] == f.get('row')
                   and x['sev'] in ('WARN', 'RESCUE', 'NORESCUE')]
            for x in ctx[-5:]:
                print('      · t=%6.1fs [%s] %s' % (x['t'] / 100.0, x['sev'], x['what']))
            if not ctx:
                print('      · 该路没有任何救场记录 —— 说明是"一瞬间被突破"，不是耗死')
    else:
        print('崩阵          无')

    if s['warn']:
        print()
        print('磨损（WARN，可补种，不计崩阵）')
        for k, v in sorted(s['warn'].items(), key=lambda x: -x[1])[:8]:
            print('  %-40s %d 次' % (k, v))

    print()
    print('冰道：累计覆盖 %.1f 格/局（当前残留 %.1f 格）；因冰道种不下 %d 次'
          % (sum(r.get('ice_touched', 0) for r in reports) / len(reports),
             sum(r.get('ice_cells', 0) for r in reports) / len(reports),
             sum(r.get('ice_blocks', 0) for r in reports)))
    cr = [c for r in reports for c in r.get('crush', [])]
    if cr:
        print('冰车碾压 %d 次（前 6 条）：' % len(cr))
        for c in cr[:6]:
            print('   w%d  %d-%d  %s' % (c['wave'], c['row'], c['col'], c['plant'] or '南瓜'))

    if s['broken']:
        print('-' * 72)
        print('轨道断裂（卡 CD / 阳光）：')
        for k, v in sorted(s['broken'].items(), key=lambda x: -x[1]):
            print('  %-24s %d 次' % (k, v))
    else:
        print('轨道断裂      无')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=10)
    ap.add_argument('--html', default=None)
    ap.add_argument('--wave', type=float, default=None,
                    help='名义平均波长（秒）。不给就用模拟算出来的平均值')
    ap.add_argument('--no-rescue', action='store_true', help='关闭救场层')
    ap.add_argument('--round', type=int, default=None, help='覆盖轮数（标定用）')
    ap.add_argument('--tier', default=None, help='覆盖出怪档位：慢速/变速/快速/极速')
    a = ap.parse_args()

    if a.round is not None:
        CFG.ROUND = a.round
    if a.tier:
        CFG.MODE = a.tier
    rescue = False if a.no_rescue else getattr(CFG, 'RESCUE', True)
    reports = [run_once(s, rescue) for s in range(a.seeds)]
    s = summarize(reports)

    # ---- L1 静态检查（用名义波长；没给就用模拟均值）
    from tools.trackcheck import l1
    n_sun = sum(1 for v in CFG.ARRAY.values() if v.get('plant') == '双子花')
    sun_rate = n_sun * 50 / 24.0
    avg_cs = (a.wave * 100) if a.wave else (s['gap_avg'] or 1250)
    L1 = l1.report(CFG.track, 4, avg_cs, sun_rate)

    print('=' * 72)
    print('L1 静态检查（零误差层）')
    print('=' * 72)
    print('循环 %d 波 × %.2fs = %.1fs' % (4, avg_cs / 100, L1['cycle_cs'] / 100))
    print('%-8s %-6s %-10s %-10s %-8s %s'
          % ('卡片', '用次', '实际间隔', '卡片CD', '余量', '结论'))
    for c in L1['cards']:
        print('%-8s %-6d %-10.1fs %-10.1fs %-8.1fs %s'
              % (c['card'], c['used'], c['gap'] / 100, c['cd'] / 100,
                 c['margin'] / 100, 'OK' if c['ok'] else '✗ 断裂'))
    print('运算量：轨道给 %d，需求 %d（4 波×2），缺口 %d → 由 IO 补'
          % (L1['ops_sum'], L1['ops_need'], L1['ops_need'] - L1['ops_sum']))
    print('阳光：收入 %d / 循环，支出 %d，净 %+d'
          % (L1['sun_income'], L1['sun_spend'], L1['sun_net']))
    print()

    print_l2(reports, s)

    # ---- 判定型僵尸（规则查表，不模拟）
    from tools.trackcheck import judge
    print()
    print('=' * 72)
    print('判定型：小丑 / 蹦极 / 投篮 / 气球')
    print('=' * 72)
    jk = judge.judge_joker(CFG.ARRAY)
    print('小丑（按每路最靠前的曾）')
    for x in jk:
        print('  %d 路  曾最前 %s 列  档位 %-3s  冰截止 %-6s  %s'
              % (x['row'], x['gloom_col'] or '—', x['verdict'],
                 ('%.1fs' % (x['need_ice_by'] / 100)) if x['need_ice_by'] else '—',
                 x['extra']))
    js = judge.joker_summary(jk)
    print('  → 整阵按最紧的一路：%s；冰最迟 %.1fs 生效'
          % (js['worst']['verdict'],
             (js['ice_deadline'] / 100) if js['ice_deadline'] else 0))

    bj = judge.judge_bungee(CFG.ARRAY)
    print('\n蹦极（伞 或 两条冰杀定式）')
    if bj['ok']:
        print('  → 全场每个可被偷的格子都满足「伞 或 定式」：没有偷盲')
    else:
        print('  → 不满足的格子：')
        for x in bj['blind']:
            print('     %d-%d %-4s（%d 曾）→ %s'
                  % (x['row'], x['col'], x['plant'], x['glooms'], x['decision']))

    cp = judge.judge_catapult2(CFG.ARRAY, n_cannon=getattr(CFG, 'N_CANNON', 0),
                               kill_before_throw=getattr(CFG, 'KILL_BEFORE_THROW', False))
    print('\n投篮')
    print('  ① 伞罩底线：%s' % ('是' if cp['by_umbrella'] else '否'))
    print('  ② 投掷前击杀：%s' % ('是' if cp['by_kill'] else '否'))
    print('  → %s' % ('可行' if cp['ok'] else '不可行'))

    bl = judge.judge_balloon(n_cannon=getattr(CFG, 'N_CANNON', 0), has_ice=True,
                             n_cat=getattr(CFG, 'N_CAT', 0),
                             has_blover=getattr(CFG, 'HAS_BLOVER', False))
    print('\n气球（判定型）')
    print('  %s → %s' % (bl['why'], '可行' if bl['ok'] else '不可行'))

    # ---- 期望型磨损
    r0 = reports[0]
    from tools.trackcheck import expect
    k_sim = (r0['pump_dmg'] / max(1, len(r0['waves']))) if r0.get('pump_dmg') is not None else 0
    eb = expect.balance_from_sim(k_sim, L1['cycle_cs'], 4,
                                 n_cards=getattr(CFG, 'PUMPKIN_CARDS', 1))
    print()
    print('=' * 72)
    print('期望型磨损（南瓜收支）')
    print('=' * 72)
    print('  k（需求）= %.0f 血/波　← 由模拟统计（南瓜总掉血 ÷ 波数），随节奏变化'
          % eb['k'])
    print('  供给 = 每循环可补 %.2f 个南瓜（%d 张卡）× 4000 / 4 波 = %.0f 血/波'
          % (eb['n_pump'], eb['n_cards'], eb['supply']))
    print('  → %s（占用供给 %.0f%%），每年修复阳光约 %.0f'
          % ('撑得住' if eb['ok'] else '净亏', eb['ratio'] * 100, eb['sun_fix']))

    print()
    print('=' * 72)
    print('第一局的逐波明细（seed=0）：')
    print(' 波  刷新(s)  间隔(s)  本波总血  剩余   阈值   刷新原因')
    for w in r0['waves']:
        print(' %2d  %7.2f  %7.2f  %8d  %5d  %.2f   %s'
              % (w['w'], w['t'] / 100, w['gap'] / 100, w['total_hp'],
                 w['remain'], w['thr'], w['reason'] or ''))

    if a.html:
        from tools.trackcheck.report import write_html
        write_html(a.html, reports, s, CFG, L1)
        print('\nHTML -> %s' % a.html)


if __name__ == '__main__':
    main()
