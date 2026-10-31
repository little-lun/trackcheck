# -*- coding: utf-8 -*-
"""
appwin.py —— 桌面版主程序（TrackCheck.exe）：**原生窗口**，不再借浏览器

    TrackCheck.exe = 这个启动器 + 一整套 Python 引擎（PyInstaller 打成一个 exe）

做法：
  ① 起那个只在 127.0.0.1 上的小服务（界面、报告、PDF 全走它，逻辑一行没改）；
  ② 用 **pywebview** 开一个原生窗口（Windows 上是 Edge WebView2 内核）指向它 ——
     没有地址栏、没有标签页、没有书签栏，就是一个正经的应用窗口；
  ③ `private_mode=False` + `storage_path` 让 localStorage / 缓存**落到磁盘**，
     于是语言、阵型草稿、出怪列表这些本地设置关掉再开还在；
  ④ 本地文件对话框走 **HTTP `/api/native`**（`native_dlg.py` 的 comdlg32），
     **不用 pywebview 的 js_api** —— 实测那条桥会把解释器卡死（页面一调 api，
     整个 Python 侧不再响应，连本地服务都停摆）。

★ 打包成 windowed 之后没有控制台，任何异常都必须用 MessageBox 冒出来，
  否则用户只会看到"双击没反应"。
★ pywebview / WebView2 起不来时**自动退回浏览器模式** —— 宁可难看，也不能打不开。
"""

import ctypes
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _err(title, text):
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    except Exception:                                        # noqa: BLE001
        print(title, text)


def _log(msg):
    """排障日志：设了 `TRACKCHECK_LOG` 就追加写一行（打包版没有控制台）"""
    path = os.environ.get('TRACKCHECK_LOG')
    if not path:
        return
    try:
        import time
        with open(path, 'a', encoding='utf-8') as f:
            f.write('%.2f %s\n' % (time.time(), msg))
    except OSError:
        pass


def data_dir():
    """本地配置/草稿目录（`%LOCALAPPDATA%\\TrackCheck`）"""
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'TrackCheck')
    for sub in ('', 'webview', 'exports'):
        try:
            os.makedirs(os.path.join(d, sub) if sub else d, exist_ok=True)
        except OSError:
            pass
    return d


def run_window(port=None, debug=False):
    """起服务 + 开原生窗口。返回 True = 正常走过（窗口被关掉）"""
    import threading

    import webview

    from tools.trackcheck import app as APP

    _log('run_window start port=%s' % port)
    # ★ 端口扫描：8765 优先；被别的实例占着就顺延 —— 宁可换端口，
    #   也不要让窗口指向一个"看起来在监听、其实不响应"的僵尸服务。
    srv, url = None, None
    for p in ([port] if port else []) + list(range(8765, 8776)):
        srv, url = APP.create_server('127.0.0.1', p)
        if srv is not None:
            break
    _log('server=%s url=%s' % ('ok' if srv else 'NONE', url))
    if srv is None:
        raise RuntimeError('没有可用端口（8765~8775 都被占用）')
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _log('serve_forever thread started')

    data = data_dir()
    win = webview.create_window(
        'TrackCheck · PVZ 生存无尽研究工具', url,
        width=1500, height=950, min_size=(1080, 680),
        resizable=True, text_select=True,
        background_color='#0b1220',
        confirm_close=False)
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'trackcheck.ico')
    _log('window created, starting webview')
    webview.start(gui='edgechromium', debug=bool(debug),
                  private_mode=False,           # localStorage 落盘
                  storage_path=os.path.join(data, 'webview'),
                  icon=icon if os.path.exists(icon) else None)
    _log('webview exited')
    return win is not None


def main(argv=None):
    os.environ['TRACKCHECK_DESKTOP'] = '1'
    args = list(sys.argv[1:] if argv is None else argv)
    debug = '--debug' in args
    port = None
    if '--port' in args:
        try:
            port = int(args[args.index('--port') + 1])
        except (IndexError, ValueError):
            port = None

    try:
        run_window(port=port, debug=debug)
        return
    except Exception:                                        # noqa: BLE001
        err = traceback.format_exc(limit=8)
        _log('FAILED: ' + err)

    # ---- 退回浏览器模式：宁可难看，也不能打不开
    try:
        _err('TrackCheck：原生窗口起不来，改用浏览器打开',
             '通常是系统缺 Edge WebView2 运行时。\n'
             '程序会照常运行，只是界面开在浏览器里。\n\n' + err[-1200:])
    except Exception:                                        # noqa: BLE001
        pass
    try:
        from tools.trackcheck import app as APP
        APP.main(['--idle-exit', '1800'] + args)
    except Exception:                                        # noqa: BLE001
        _err('TrackCheck 运行出错', traceback.format_exc(limit=8))


if __name__ == '__main__':
    main()
