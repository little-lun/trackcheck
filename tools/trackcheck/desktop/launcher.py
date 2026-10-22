# -*- coding: utf-8 -*-
"""
launcher.py —— 桌面版主程序（TrackCheck.exe）

做的事很简单：起一个只在 127.0.0.1 上的小服务，再把默认浏览器指过去。

    TrackCheck.exe = 这个启动器 + 一整套 Python 引擎（PyInstaller 打成一个 exe）

★ 打包成 windowed 之后没有控制台，任何异常都必须用 MessageBox 冒出来，
  否则用户只会看到"双击没反应"。
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


def main():
    # 界面靠这个开关决定要不要显示"退出程序"按钮
    os.environ['TRACKCHECK_DESKTOP'] = '1'
    try:
        from tools.trackcheck import app
    except Exception:                                        # noqa: BLE001
        return _err('TrackCheck 启动失败', traceback.format_exc(limit=8))

    # 30 分钟没心跳（浏览器页面关掉了）就自己退，免得后台一直挂着
    try:
        app.main(['--idle-exit', '1800'] + sys.argv[1:])
    except Exception:                                        # noqa: BLE001
        _err('TrackCheck 运行出错', traceback.format_exc(limit=8))


if __name__ == '__main__':
    main()
