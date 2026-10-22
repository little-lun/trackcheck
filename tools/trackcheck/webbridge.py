# -*- coding: utf-8 -*-
"""
webbridge.py —— 单文件网页版的"后端"

只在浏览器里的 CPython（Pyodide）中被 import，作用是把页面上那些
`fetch('/api/...')` 翻译成对 jobs.py / ui.py 的调用。

和 app.py 的区别只有"谁来驱动 step()"：
    服务端  → 后台线程 while step(): pass
    浏览器  → 前端 JS 每跑完一局 await 一次 step()，好让进度条动起来

约定：所有函数的返回值都是 **JSON 字符串**（JS 那边 JSON.parse 一次即可）。
"""

import json
import os
import sys
from urllib.parse import parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.trackcheck import jobs as JB   # noqa: E402
from tools.trackcheck import plan as PL   # noqa: E402
from tools.trackcheck import ui           # noqa: E402

JSON_CT = 'application/json; charset=utf-8'


def _spec(code, ctype, body):
    return json.dumps({'code': code, 'ctype': ctype, 'body': body},
                      ensure_ascii=False)


def _json(code, obj):
    return _spec(code, JSON_CT, json.dumps(obj, ensure_ascii=False))


def handle(path, query='', body=''):
    """模拟一次 /api 请求 → {'code', 'ctype', 'body'}"""
    try:
        if path == '/api/meta':
            return _json(200, ui.meta_payload())
        # ---- 阵解栏（网页版：能编能校验；存盘请用「导出 JSON」）
        if path == '/api/plan/catalog':
            return _json(200, PL.catalog())
        if path == '/api/plan/default':
            return _json(200, PL.default_dianbozhong())
        if path == '/api/plan/template':
            q = parse_qs(query or '')
            return _json(200, PL.template((q.get('field') or ['PE'])[0]))
        if path == '/api/example/array':
            from tools.trackcheck import config_dianbozhong as CFG
            return _json(200, dict(
                ok=True, field='PE', name='电波钟无炮',
                array={'%d-%d' % k: dict(plant=v.get('plant'),
                                         pumpkin=bool(v.get('pumpkin')),
                                         ladder=bool(v.get('ladder')),
                                         base=('睡莲' if k[0] in (3, 4) else None))
                       for k, v in CFG.ARRAY.items()}))
        if path == '/api/plan/example':
            return _json(200, PL.example_split_aa())
        if path == '/api/plan/list':
            return _json(200, {'names': []})
        if path == '/api/plan/load':
            return _json(404, {'error': '网页版没有磁盘，请用「导入 JSON」'})
        if path == '/api/spec':
            q = parse_qs(query or '')
            what = (q.get('what') or ['plan'])[0]
            return _spec(200, 'text/plain; charset=utf-8', PL.spec_text(what))
        if path == '/api/plan/quick':
            try:
                d = json.loads(body or '{}')
            except Exception:
                return _json(400, {'error': 'bad json'})
            p, n = PL.quick_layout(d.get('plan') or {}, d.get('track') or '',
                                   d.get('pair'), d.get('gaps'))
            return _json(200, {'ok': True, 'plan': p, 'filled': n})
        if path == '/api/plan/spectrum':
            try:
                d = json.loads(body or '{}')
            except Exception:
                return _json(400, {'error': 'bad json'})
            return _json(200, PL.spectrum_report(
                d.get('plan') or {}, d.get('track'), d.get('gaps'),
                d.get('n_cob')))
        if path == '/api/plan/batch':
            try:
                d = json.loads(body or '{}')
            except Exception:
                return _json(400, {'error': 'bad json'})
            op = d.get('op') or 'clear'
            if op == 'shift':
                p, n = PL.shift_waves(d.get('plan') or {}, d.get('waves') or [],
                                      int(d.get('delta') or 0))
            else:
                p, n = PL.batch_edit(d.get('plan') or {}, d.get('waves') or [],
                                     op, d.get('data') or {})
            return _json(200, {'ok': True, 'plan': p, 'n': n})
        if path == '/api/plan/validate':
            try:
                d = json.loads(body or '{}')
            except Exception:
                return _json(400, {'error': 'bad json'})
            return _json(200, {'issues': PL.validate(d.get('plan') or {})})
        if path == '/api/plan/save':
            return _json(200, {'ok': False,
                               'error': '网页版不能写磁盘 —— 用「导出 JSON」保存'})
        if path == '/api/layout/catalog':
            from tools.trackcheck import layout as LY
            return _json(200, LY.catalog())
        if path == '/api/layout/encode':
            from tools.trackcheck import layout as LY
            try:
                d = json.loads(body or '{}')
            except Exception:
                return _json(400, {'ok': False, 'error': 'bad json'})
            try:
                fmt = d.get('fmt') or None
                s = LY.encode_any(d.get('array') or {}, d.get('field') or 'PE',
                                  fmt, int(d.get('rake') or 0))
                f = LY.FORMATS.get(fmt or LY.DEFAULT_FORMAT) or {}
                return _json(200, {'ok': True, 'string': s,
                                   'fmt': fmt or LY.DEFAULT_FORMAT,
                                   'fmt_label': f.get('label', '')})
            except Exception as e:                           # noqa: BLE001
                return _json(500, {'ok': False, 'error': str(e)})
        if path == '/api/layout/decode':
            from tools.trackcheck import layout as LY
            try:
                d = json.loads(body or '{}')
            except Exception:
                return _json(400, {'ok': False, 'error': 'bad json'})
            try:
                txt = d.get('string') or ''
                fmt = d.get('fmt') or None
                arr, fld, rake = LY.decode_any(txt, fmt, d.get('field') or None)
                used = fmt or ('tools' if ',' in txt else LY.DEFAULT_FORMAT)
                f = LY.FORMATS.get(used) or {}
                return _json(200, {'ok': True,
                                   'array': {'%d-%d' % k: v
                                             for k, v in arr.items()},
                                   'field': fld, 'rake': rake,
                                   'fmt': used, 'fmt_label': f.get('label', '')})
            except Exception as e:                           # noqa: BLE001
                return _json(500, {'ok': False, 'error': str(e)})
        if path == '/api/jobs':
            return _json(200, {'jobs': JB.payload()})
        if path == '/api/ping':
            return _json(200, {'ok': True})
        if path == '/api/clear':
            JB.clear()
            return _json(200, {'ok': True})
        if path == '/api/start':
            try:
                d = json.loads(body or '{}')
            except Exception:
                return _json(400, {'error': 'bad json'})
            made = JB.create_jobs(d.get('jobs') or [])
            return _json(200, {'ok': True, 'ids': [j['id'] for j in made]})
        if path == '/api/pdf':
            raw = (parse_qs(query or '').get('id') or ['0'])[0]
            try:
                jid = int(raw)
            except ValueError:
                jid = 0
            job = next((j for j in JB.JOBS if j['id'] == jid), None)
            if job is None or not job.get('html'):
                return _json(404, {'error': 'job not ready'})
            # ★ 浏览器里没有"无头打印"可调：回打印页，前端开新窗口 window.print()
            return _spec(200, 'text/html; charset=utf-8',
                         ui.job_print_html(job, autoprint=True))
        return _json(404, {'error': 'not found'})
    except Exception as e:                                   # noqa: BLE001
        return _json(500, {'error': '%s: %s' % (type(e).__name__, e)})


def step():
    """推进一个种子（JS 每调用一次，页面就多一局的进度）"""
    try:
        j = JB.step()
    except Exception as e:                                   # noqa: BLE001
        return json.dumps({'idle': True, 'error': '%s: %s' % (type(e).__name__, e)},
                          ensure_ascii=False)
    if j is None:
        return json.dumps({'idle': True}, ensure_ascii=False)
    return json.dumps({'idle': False, 'id': j['id'], 'status': j['status'],
                       'progress': j['progress'], 'seeds': j['seeds']},
                      ensure_ascii=False)
