# -*- coding: utf-8 -*-
"""
app.py —— 本地 Web 应用：**自由勾选出怪 → 自动判定节奏 → 选阵解 → 跑运阵 → 出报告**

分层：界面文案在 ui.py，排队/推进在 jobs.py，这一层只做两件事 ——
把 HTTP 请求翻成对它们的调用，以及"调本机 Edge/Chrome 无头打印"出 PDF。

用法：
    python -m tools.trackcheck.app                 # 起服务并打开浏览器
    python -m tools.trackcheck.app --port 8800
    python -m tools.trackcheck.app --no-open
    python -m tools.trackcheck.app --idle-exit 300 # 5 分钟没心跳就自己退（桌面版用）
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.trackcheck import config_dianbozhong as CFG   # noqa: E402
from tools.trackcheck import jobs as JB                  # noqa: E402
from tools.trackcheck import plan as PL                  # noqa: E402
from tools.trackcheck import ui                          # noqa: E402


# ------------------------------------------------------------------ PDF 报告
# ★ 不引第三方库：直接调本机 Edge / Chrome 的**无头打印**，拿到的 PDF
#   与屏幕上的报告同款（中文字体、SVG 时间轴都在）。找不到浏览器时退回
#   "打印页 + window.print()"，用户在对话框里选"另存为 PDF"。
_BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]


def html_to_pdf(html):
    """无头浏览器打印成 PDF；没有浏览器或失败时返回 None"""
    exe = next((p for p in _BROWSERS if os.path.exists(p)), None)
    if exe is None:
        return None
    tmp = tempfile.mkdtemp(prefix='trackcheck-pdf-')
    try:
        src = os.path.join(tmp, 'report.html')
        out = os.path.join(tmp, 'report.pdf')
        with open(src, 'w', encoding='utf-8') as f:
            f.write(html)
        cmd = [exe, '--headless=new', '--disable-gpu', '--no-first-run',
               '--no-default-browser-check', '--virtual-time-budget=3000',
               '--user-data-dir=' + os.path.join(tmp, 'profile'),
               '--no-pdf-header-footer', '--print-to-pdf=' + out,
               pathlib.Path(src).as_uri()]
        subprocess.run(cmd, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            with open(out, 'rb') as f:
                return f.read()
        return None
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pdf_response(job):
    """优先真 PDF；本机没有 Edge/Chrome 时回打印页（前端开窗 window.print）"""
    pdf = html_to_pdf(ui.job_print_html(job))
    if pdf:
        return ('application/pdf',
                'attachment; filename="trackcheck-report-%d.pdf"' % job['id'],
                pdf)
    return 'text/html; charset=utf-8', None, ui.job_print_html(job, autoprint=True)


# ------------------------------------------------------------------ 后台跑任务
_worker = [None]
_last_ping = [time.time()]


def _worker_loop():
    """
    一直推进到队列空才退出。

    ★ 不能写成 `for j in jobs` —— 用户在跑的过程中再点一次"开始"，
      新任务会永远停在 pending（上一版就是这个 bug）。
    """
    try:
        while JB.step() is not None:
            pass
    finally:
        CFG.KINDS_OVERRIDE = None
        _worker[0] = None


def start_jobs(specs):
    """建任务并确保有线程在推进它"""
    made = JB.create_jobs(specs)
    if made and (_worker[0] is None or not _worker[0].is_alive()):
        th = threading.Thread(target=_worker_loop, daemon=True)
        _worker[0] = th
        th.start()
    return made


# ------------------------------------------------------------------ HTTP
class Server(ThreadingHTTPServer):
    """
    ★ 必须关掉 allow_reuse_address。

    Windows 的 SO_REUSEADDR 语义和 Linux 不同：它允许**第二个 socket 绑同一个端口**
    （而不是只允许 TIME_WAIT 复用）。HTTPServer 默认开着它，于是"重复双击"时
    第二个实例会静默抢占 8765，前端连到哪个进程全看运气 —— 而且我那句
    "端口占用就打开已有实例"的分支永远不会触发。
    """
    allow_reuse_address = False
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        return self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            return self._send(200, ui.page_html(), 'text/html; charset=utf-8')
        if path == '/api/meta':
            return self._json(ui.meta_payload())
        if path == '/api/jobs':
            return self._json({'jobs': JB.payload()})
        if path == '/api/ping':
            _last_ping[0] = time.time()
            return self._json({'ok': True})
        # ---- 阵解栏
        if path == '/api/plan/catalog':
            return self._json(PL.catalog())
        if path == '/api/plan/default':
            return self._json(PL.default_dianbozhong())
        if path == '/api/plan/template':
            q = parse_qs(urlsplit(self.path).query)
            fld = (q.get('field') or ['PE'])[0]
            return self._json(PL.template(fld))
        if path == '/api/example/array':
            return self._json(dict(ok=True, field='PE',
                                   name='电波钟无炮',
                                   array={'%d-%d' % k: dict(
                                       plant=v.get('plant'),
                                       pumpkin=bool(v.get('pumpkin')),
                                       ladder=bool(v.get('ladder')),
                                       base=('睡莲' if k[0] in (3, 4) else None))
                                          for k, v in CFG.ARRAY.items()}))
        if path == '/api/example/classic8':
            try:
                return self._json(PL.example_classic8())
            except Exception as e:                           # noqa: BLE001
                return self._json({'ok': False, 'error': str(e)}, 500)
        if path.startswith('/api/example/fe4'):
            q = parse_qs(urlsplit(self.path).query)
            rid = (q.get('rid') or ['N6s'])[0]
            try:
                return self._json(PL.example_fe4(rid))
            except Exception as e:                           # noqa: BLE001
                return self._json({'ok': False, 'error': str(e)}, 500)
        if path == '/api/plan/example':
            return self._json(PL.example_split_aa())
        if path == '/api/spec':
            q = parse_qs(urlsplit(self.path).query)
            what = (q.get('what') or ['plan'])[0]
            return self._send(200, PL.spec_text(what), 'text/plain; charset=utf-8')
        if path == '/api/layout/catalog':
            from tools.trackcheck import layout as LY
            return self._json(LY.catalog())
        if path == '/api/plan/list':
            return self._json({'names': PL.list_files()})
        if path == '/api/plan/load':
            q = parse_qs(urlsplit(self.path).query)
            name = (q.get('name') or [''])[0]
            p = PL.load_file(name)
            if p is None:
                return self._json({'error': 'not found'}, 404)
            return self._json(p)
        if path == '/api/quit':
            self._json({'ok': True})
            threading.Timer(0.3, lambda: os._exit(0)).start()
            return
        if path == '/api/pdf':
            q = parse_qs(urlsplit(self.path).query)
            try:
                jid = int((q.get('id') or ['0'])[0])
            except ValueError:
                jid = 0
            job = next((j for j in JB.JOBS if j['id'] == jid), None)
            if job is None or not job.get('html'):
                return self._json({'error': 'job not ready'}, 404)
            ctype, disp, body = pdf_response(job)
            if disp is None:
                return self._send(200, body, ctype)
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Disposition', disp)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        return self._json({'error': 'not found'}, 404)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b'{}'
        path = self.path.split('?')[0]
        if path == '/api/start':
            try:
                d = json.loads(raw or b'{}')
            except Exception:
                return self._json({'error': 'bad json'}, 400)
            made = start_jobs(d.get('jobs') or [])
            return self._json({'ok': True, 'ids': [j['id'] for j in made]})
        if path == '/api/plan/validate':
            try:
                d = json.loads(raw or b'{}')
            except Exception:
                return self._json({'error': 'bad json'}, 400)
            return self._json({'issues': PL.validate(d.get('plan') or {})})
        if path == '/api/plan/quick':
            try:
                d = json.loads(raw or b'{}')
            except Exception:
                return self._json({'error': 'bad json'}, 400)
            try:
                p, n = PL.quick_layout(d.get('plan') or {}, d.get('track') or '',
                                       d.get('pair'), d.get('gaps'))
                return self._json({'ok': True, 'plan': p, 'filled': n})
            except Exception as e:                           # noqa: BLE001
                return self._json({'error': str(e)}, 500)
        if path == '/api/plan/spectrum':
            try:
                d = json.loads(raw or b'{}')
            except Exception:
                return self._json({'error': 'bad json'}, 400)
            try:
                return self._json(PL.spectrum_report(
                    d.get('plan') or {}, d.get('track'), d.get('gaps'),
                    d.get('n_cob')))
            except Exception as e:                           # noqa: BLE001
                return self._json({'ok': False, 'error': str(e)}, 500)
        if path == '/api/plan/batch':
            try:
                d = json.loads(raw or b'{}')
            except Exception:
                return self._json({'error': 'bad json'}, 400)
            try:
                op = d.get('op') or 'clear'
                if op == 'shift':
                    p, n = PL.shift_waves(d.get('plan') or {}, d.get('waves') or [],
                                          int(d.get('delta') or 0))
                else:
                    p, n = PL.batch_edit(d.get('plan') or {}, d.get('waves') or [],
                                         op, d.get('data') or {})
                return self._json({'ok': True, 'plan': p, 'n': n})
            except Exception as e:                           # noqa: BLE001
                return self._json({'error': str(e)}, 500)
        if path == '/api/plan/save':
            try:
                d = json.loads(raw or b'{}')
            except Exception:
                return self._json({'error': 'bad json'}, 400)
            try:
                return self._json(PL.save_file(d.get('plan') or {}, d.get('name')))
            except Exception as e:                           # noqa: BLE001
                return self._json({'ok': False, 'error': str(e)}, 500)
        if path == '/api/layout/encode':
            from tools.trackcheck import layout as LY
            try:
                d = json.loads(raw or b'{}')
            except Exception:
                return self._json({'ok': False, 'error': 'bad json'}, 400)
            try:
                fmt = d.get('fmt') or None
                s = LY.encode_any(d.get('array') or {}, d.get('field') or 'PE',
                                  fmt, int(d.get('rake') or 0))
                f = LY.FORMATS.get(fmt or LY.DEFAULT_FORMAT) or {}
                return self._json({'ok': True, 'string': s,
                                   'fmt': fmt or LY.DEFAULT_FORMAT,
                                   'fmt_label': f.get('label', '')})
            except Exception as e:                           # noqa: BLE001
                return self._json({'ok': False, 'error': str(e)}, 500)
        if path == '/api/layout/decode':
            from tools.trackcheck import layout as LY
            try:
                d = json.loads(raw or b'{}')
            except Exception:
                return self._json({'ok': False, 'error': 'bad json'}, 400)
            try:
                txt = d.get('string') or ''
                fmt = d.get('fmt') or None
                arr, fld, rake = LY.decode_any(txt, fmt, d.get('field') or None)
                used = fmt or ('tools' if ',' in txt else LY.DEFAULT_FORMAT)
                f = LY.FORMATS.get(used) or {}
                return self._json({'ok': True,
                                   'array': {'%d-%d' % k: v
                                             for k, v in arr.items()},
                                   'field': fld, 'rake': rake,
                                   'fmt': used, 'fmt_label': f.get('label', '')})
            except Exception as e:                           # noqa: BLE001
                return self._json({'ok': False, 'error': str(e)}, 500)
        if path == '/api/clear':
            JB.clear()
            return self._json({'ok': True})
        return self._json({'error': 'not found'}, 404)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--no-open', action='store_true')
    ap.add_argument('--idle-exit', type=float, default=0,
                    help='这么久没收到页面心跳就退出（0 = 不退）')
    a = ap.parse_args(argv)

    url = 'http://%s:%d/' % (a.host, a.port)
    try:
        srv = Server((a.host, a.port), Handler)
    except OSError:
        # ★ 双击第二次时很常见：上一实例还开着。直接把浏览器指过去，正常退出（exit 0），
        #   这样启动脚本不会停在 pause 上。
        print('端口 %d 已被占用 —— 应该已经有一个沙盘在跑，直接打开它：%s'
              % (a.port, url), flush=True)
        if not a.no_open:
            webbrowser.open(url)
        return
    print('出怪沙盘 -> %s   （Ctrl+C 结束）' % url, flush=True)
    if not a.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    if a.idle_exit > 0:
        _last_ping[0] = time.time()

        def _watch():
            while True:
                time.sleep(5)
                if time.time() - _last_ping[0] > a.idle_exit:
                    os._exit(0)
        threading.Thread(target=_watch, daemon=True).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nbye')


if __name__ == '__main__':
    main()
