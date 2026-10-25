# -*- coding: utf-8 -*-
"""
build_web.py —— 把 trackcheck 打包成**一个 .html 文件**（纯前端，不用服务器）

原理：浏览器装不下 Python，就把 CPython 编译成的 WebAssembly 运行时
（Pyodide）连同我们的 engine/data/config/... 一起塞进这个 HTML：

    打开 HTML → 解包/下载 Pyodide → 把 .py 源码写进它的虚拟文件系统
              → `import tools.trackcheck.webbridge`
              → 前端把 fetch('/api/...') 转成对 webbridge 的调用

两种产物：

    trackcheck-v0.1.html        离线单文件：引擎内置（约 17MB），断网也能用
    trackcheck-v0.1-web.html    在线单文件：引擎从 CDN 取（约 100KB），首开需联网

用法：
    python -m tools.trackcheck.build_web                     # 两个都出到 dist/
    python -m tools.trackcheck.build_web --only offline
    python -m tools.trackcheck.build_web --deps D:\\pyodide   # 手动指定引擎目录
"""

import argparse
import base64
import json
import os
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.trackcheck import ui   # noqa: E402

VERSION = '0.3'
APP_VER = '0.3.10'        # 内部版本（0.x.n = 同一发布里的第 n 处改动）
PYODIDE = '0.29.5'
DIST_DIR = os.path.join(ROOT, 'tools', 'trackcheck', 'dist')

# 要打进包里的模块（顺序无关，import 会自己解决依赖）
SOURCES = ['__init__.py', 'data.py', 'fields.py', 'layout.py', 'spawn.py',
           'config_dianbozhong.py', 'engine.py', 'lookahead.py',
           'html_report.py', 'run.py', 'metainfo.py', 'plan.py', 'planui.py',
           'ui.py', 'jobs.py', 'webbridge.py',
           # ★ 2026-10-24：双语（i18n）+ 帮助页正文
           'i18n.py', 'help_text.py', 'i18n_bulk.py', 'spec_text_en.py']

# 引擎运行时文件：mjs 是入口，asm.js/wasm 是 CPython 本体，zip 是标准库
DIST_FILES = ['pyodide.mjs', 'pyodide.asm.js', 'pyodide.asm.wasm',
              'python_stdlib.zip', 'pyodide-lock.json']

CDN_BASES = ['https://unpkg.com/pyodide@%s/' % PYODIDE,
             'https://fastly.jsdelivr.net/npm/pyodide@%s/' % PYODIDE,
             'https://cdn.jsdelivr.net/npm/pyodide@%s/' % PYODIDE]


# ------------------------------------------------------------------ 引擎文件
def ensure_dist(deps):
    """找（或下载）Pyodide 运行时文件，返回 {文件名: bytes}"""
    os.makedirs(deps, exist_ok=True)
    out = {}
    for name in DIST_FILES:
        p = os.path.join(deps, name)
        if not os.path.exists(p) or os.path.getsize(p) < 1000:
            _download(name, p)
        with open(p, 'rb') as f:
            out[name] = f.read()
    return out


def _download(name, dest):
    last = None
    for base in CDN_BASES:
        try:
            print('  下载 %s ← %s' % (name, base), flush=True)
            with urllib.request.urlopen(base + name, timeout=180) as r, \
                    open(dest, 'wb') as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            if os.path.getsize(dest) > 1000:
                return
        except Exception as e:                                # noqa: BLE001
            last = e
    raise RuntimeError('拿不到 %s（最后错误：%s）—— 可以用 --deps 手动指定目录'
                       % (name, last))


# ------------------------------------------------------------------ 前端引导
# __LOADER__ 换成"从哪加载引擎"，其余部分两种产物完全相同。
BOOT_JS = r'''
(function(){
  'use strict';
  const HINT = __HINT__;
  const HINT_EN = __HINT_EN__;
  const PY_SRC = __PY_SRC__;
  const nativeFetch = window.fetch.bind(window);
  const boot = document.getElementById('boot');
  const msg = document.getElementById('boot-msg');
  /* ★ 用户 2026-10-24：启动壳也是用户可见文字 → 必须双语。
     语言来自 localStorage（页面本体还没渲染，问不到 Python）。 */
  let EN = false;
  try { EN = (localStorage.getItem('tc-lang') === 'en'); } catch (e){}
  const T = (cn, en) => (EN ? en : cn);
  const bootTitle = document.getElementById('boot-title');
  if (EN) document.title = 'trackcheck · PvZ Survival Endless research tool';
  if (bootTitle) bootTitle.textContent =
    T('TrackCheck · 正在启动运阵引擎…', 'TrackCheck · starting the engine…');
  if (msg) msg.textContent = T('首次打开会慢一点', 'the first launch takes a little longer');
  const say = t => { if (msg) msg.textContent = t; };
  const die = e => {
    console.error(e);
    if (msg) msg.innerHTML = '<b style="color:#b91c1c">'
      + T('引擎启动失败', 'the engine failed to start') + '</b><br>'
      + String((e && e.message) || e)
      + '<br><span style="color:#64748b">'
      + T('（网页版需要能执行 WebAssembly 的浏览器：Edge / Chrome / Firefox 新版）',
          '(the web build needs a browser that can run WebAssembly: a recent Edge / Chrome / Firefox)')
      + '</span>';
  };

  __LOADER__

  async function mountEngine(pyodide){
    pyodide.FS.mkdirTree('/lib/tools/trackcheck');
    pyodide.FS.writeFile('/lib/tools/__init__.py', '');
    pyodide.FS.writeFile('/lib/tools/trackcheck/__init__.py', '');
    for (const [name, src] of Object.entries(PY_SRC))
      pyodide.FS.writeFile('/lib/tools/trackcheck/' + name, src, {encoding: 'utf8'});
    pyodide.runPython(
      "import sys\nif '/lib' not in sys.path: sys.path.insert(0, '/lib')");
    pyodide.runPython('import tools.trackcheck.webbridge as _wb');
    return pyodide.globals.get('_wb');
  }

  let driving = false;
  async function drive(){
    /* 一局一局推进：每局之间让出主线程，进度条才动得起来 */
    if (driving) return;
    driving = true;
    try {
      for (;;){
        const st = JSON.parse(WB.step());
        if (st.error) console.error(st.error);
        if (st.idle) break;
        await new Promise(r => setTimeout(r, 16));
      }
    } catch (e){ console.error(e); }
    finally { driving = false; }
  }

  let WB = null;
  (async () => {
    try {
      say(T(HINT, HINT_EN));
      const pyodide = await bootPyodide();
      say(T('正在装载运阵引擎…', 'loading the engine…'));
      WB = await mountEngine(pyodide);
      // 从这里开始，页面上的 /api/* 都由 Python 直接回答
      window.fetch = function(input, init){
        const url = typeof input === 'string' ? input : ((input && input.url) || String(input));
        if (url.indexOf('/api/') !== 0) return nativeFetch(input, init);
        const q = url.indexOf('?');
        const path = q < 0 ? url : url.substr(0, q);
        const query = q < 0 ? '' : url.substr(q + 1);
        const body = (init && init.body) || '';
        if (path === '/api/quit')
          return Promise.resolve(new Response('{"ok":true}',
            {headers: {'Content-Type': 'application/json'}}));
        let spec;
        try { spec = JSON.parse(WB.handle(path, query, String(body))); }
        catch (e){ spec = {code: 500, ctype: 'application/json',
                           body: JSON.stringify({error: String(e)})}; }
        if (path === '/api/start') setTimeout(drive, 0);
        return Promise.resolve(new Response(spec.body,
          {status: spec.code, headers: {'Content-Type': spec.ctype}}));
      };
      // ★ 2026-10-24：网页版的整页 HTML 是**运行时**渲染的 —— 烘进文件里那份
      //   只是这个启动壳（否则语言切换、报告等都要重新打包）。
      //   先把存下来的语言喂给 Python，再让 Python 渲染真界面写进文档。
      //   ⚠️ 语言切换走 location.reload()：`document.write` 不能重复执行，
      //   第二次写会在同一个全局作用域里再声明一次 `const META` → SyntaxError。
      window.__TC_WEB__ = true;
      try {
        const want = localStorage.getItem('tc-lang');
        if (want) WB.handle('/api/setlang', '', JSON.stringify({lang: want}));
      } catch (e){ /* file:// 下 localStorage 可能不可用，忽略 */ }
      const idx = JSON.parse(WB.handle('/api/index', '', ''));
      if (idx.code === 200) {
        document.open(); document.write(idx.body); document.close();
      }
    } catch (e){ die(e); }
  })();
})();
'''
LOADER_OFFLINE = r'''
  /* ---- 离线版：引擎就在这个 HTML 里，一个请求都不发 ---- */
  const DIST = __DIST__;
  const b64bytes = b64 => {
    const s = atob(b64), u = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i);
    return u;
  };
  const b64text = b64 => new TextDecoder('utf-8').decode(b64bytes(b64));

  async function bootPyodide(){
    say(T('正在解包内置引擎（约 12MB，稍等）…', 'unpacking the built-in engine (~12MB)…'));
    // ① pyodide.asm.js 是普通脚本，注入后全局就有 _createPyodideModule
    const asmUrl = URL.createObjectURL(
      new Blob([b64text(DIST['pyodide.asm.js'])], {type: 'text/javascript'}));
    await new Promise((ok, no) => {
      const s = document.createElement('script');
      s.src = asmUrl;
      s.onload = () => { URL.revokeObjectURL(asmUrl); ok(); };
      s.onerror = () => no(new Error('内置引擎解包失败'));
      document.head.appendChild(s);
    });
    // ② 主模块
    const modUrl = URL.createObjectURL(
      new Blob([b64text(DIST['pyodide.mjs'])], {type: 'text/javascript'}));
    const mod = await import(modUrl);
    // ③ wasm 与标准库直接从内存给，不再走网络/磁盘
    const mem = {
      'pyodide.asm.wasm': new Blob([b64bytes(DIST['pyodide.asm.wasm'])],
                                   {type: 'application/wasm'}),
      'python_stdlib.zip': new Blob([b64bytes(DIST['python_stdlib.zip'])],
                                    {type: 'application/zip'})
    };
    const keep = window.fetch;
    window.fetch = function(u, o){
      const name = String((u && u.url) || u).split('/').pop().split('?')[0];
      if (mem[name]) return Promise.resolve(new Response(mem[name]));
      return keep.call(window, u, o);
    };
    const py = await mod.loadPyodide({
      indexURL: 'pyodide/',
      lockFileContents: b64text(DIST['pyodide-lock.json'])
    });
    window.fetch = nativeFetch;
    return py;
  }
'''

LOADER_CDN = r'''
  /* ---- 在线版：引擎从 CDN 取，浏览器会缓存 ---- */
  const CDNS = __CDNS__;
  async function bootPyodide(){
    let last = null;
    for (const base of CDNS){
      try {
        say(T('正在下载引擎（约 12MB，之后走缓存）：', 'downloading the engine (~12MB, cached afterwards): ') + base.split('/')[2]);
        const mod = await import(base + 'pyodide.mjs');
        return await mod.loadPyodide({indexURL: base});
      } catch (e){ console.warn('CDN 失败', base, e); last = e; }
    }
    throw last || new Error('所有 CDN 都连不上');
  }
'''

OVERLAY = '''
<div id="boot" style="position:fixed;inset:0;z-index:9999;background:#f6f8fb;
 display:flex;align-items:center;justify-content:center">
  <div style="text-align:center;max-width:560px;padding:0 20px">
    <div id="boot-title" style="font:600 16px -apple-system,'Segoe UI','Microsoft YaHei',sans-serif;
     color:#0f172a">TrackCheck · 正在启动运阵引擎…</div>
    <div id="boot-msg" style="font:13px/1.7 -apple-system,'Segoe UI','Microsoft YaHei',sans-serif;
     color:#64748b;margin-top:10px">首次打开会慢一点</div>
  </div>
</div>
'''


SHELL = '''<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>trackcheck v__VERSION__ · PVZ 生存无尽研究工具</title>
<style>body{margin:0;background:#f6f8fb}</style>
</head><body>
__OVERLAY__
__SCRIPT__
</body></html>
'''


def _js_json(obj):
    """塞进 <script> 里的 JSON：转义 </ 免得提前闭合标签"""
    return json.dumps(obj, ensure_ascii=False).replace('</', '<\\/')


def build(kind, out, deps):
    src = {}
    for name in SOURCES:
        p = os.path.join(ROOT, 'tools', 'trackcheck', name)
        with open(p, encoding='utf-8') as f:
            src[name] = f.read()

    if kind == 'offline':
        dist = ensure_dist(deps)
        payload = {n: base64.b64encode(b).decode('ascii') for n, b in dist.items()}
        loader = LOADER_OFFLINE.replace('__DIST__', _js_json(payload))
        hint, hint_en = '正在解包内置引擎…', 'unpacking the built-in engine…'
    else:
        loader = LOADER_CDN.replace('__CDNS__', _js_json(CDN_BASES))
        hint, hint_en = '正在下载引擎…', 'downloading the engine…'

    js = (BOOT_JS.replace('__PY_SRC__', _js_json(src))
                 .replace('__LOADER__', loader)
                 .replace('__HINT__', _js_json(hint))
                 .replace('__HINT_EN__', _js_json(hint_en)))
    # ★ 2026-10-24：整页 HTML 不再烘进来 —— 启动壳 + 运行时 `/api/index` 渲染，
    #   这样语言切换 / 以后的界面改动都不用重新打包（也避免 document.write 重复执行）。
    html = (SHELL.replace('__VERSION__', VERSION)
                 .replace('__OVERLAY__', OVERLAY)
                 .replace('__SCRIPT__', '<script>' + js + '</script>'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)
    return out, len(html.encode('utf-8'))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=DIST_DIR)
    ap.add_argument('--deps', default=None, help='Pyodide 运行时目录（缺了会自动下）')
    ap.add_argument('--only', choices=['offline', 'online', 'both'], default='both')
    a = ap.parse_args(argv)

    deps = a.deps or os.path.join(tempfile.gettempdir(),
                                 'trackcheck-pyodide-%s' % PYODIDE)
    todo = []
    if a.only in ('offline', 'both'):
        # ★ 2026-10-25 用户：内部版本的 html 用**完整内部版本号**命名
        #   （setup 只在 release 出、只用发布版本号）
        todo.append(('offline', 'trackcheck-%s.html' % APP_VER))
    if a.only in ('online', 'both'):
        todo.append(('online', 'trackcheck-%s-web.html' % APP_VER))

    for kind, name in todo:
        out, size = build(kind, os.path.join(a.out_dir, name), deps)
        print('%-8s %-28s %6.2f MB' % (kind, out, size / 1048576.0), flush=True)


if __name__ == '__main__':
    main()
