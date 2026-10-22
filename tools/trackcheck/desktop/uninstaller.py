# -*- coding: utf-8 -*-
"""
uninstaller.py —— 卸载程序（打包成 Uninstall.exe，随安装包一起落进安装目录）

难点只有一个：**自己删自己**。做法是先把自身复制到 %TEMP%，
带着 `--from-temp` 重新启动自己，然后让原进程退出；临时副本再回头
清快捷方式 / 注册表 / 安装目录，最后请 cmd 延时把自己删掉。

★ 加 /S 是静默卸载，并且会等目录真的删干净再退出（方便脚本与自测）。
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import winsetup as W          # noqa: E402

TAG = '--from-temp'
SILENT = any(a.lower() == '/s' for a in sys.argv[1:])


def _relaunch_from_temp(folder):
    dst = os.path.join(tempfile.mkdtemp(prefix='trackcheck-uninst-'),
                       'Uninstall.exe')
    shutil.copy2(os.path.abspath(sys.executable), dst)
    return subprocess.Popen([dst, TAG, folder] + (['/S'] if SILENT else []),
                            creationflags=0x08000000, close_fds=True)


def _wipe(folder):
    W.remove_file(W.startmenu_link())
    W.remove_file(W.desktop_link())
    W.remove_uninstall_entry()
    # ★ 原进程刚退出时 exe 可能还被系统占着几秒：多试几次，别留半截目录
    for _ in range(12):
        shutil.rmtree(folder, ignore_errors=True)
        if not os.path.isdir(folder) or not os.listdir(folder):
            return True
        time.sleep(0.5)
    if not SILENT:
        W.info('安装目录没能完全删干净：\n%s\n\n可以手动删掉这个文件夹，'
               '不影响系统。' % folder)
    return False


def _self_destruct():
    """请 cmd 等一会儿再删掉临时副本（那时本进程已经退出）"""
    exe = os.path.abspath(sys.executable)
    subprocess.Popen('cmd /c ping -n 3 127.0.0.1 >nul & del /f /q "%s"' % exe,
                     shell=True, creationflags=0x08000000, close_fds=True)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == TAG:
        folder = sys.argv[2] if len(sys.argv) > 2 else W.install_dir()
        time.sleep(1.5)          # 等原进程（还占着安装目录里的 exe）退干净
        W.kill_running()
        _wipe(folder)
        _self_destruct()
        return

    folder = W.app_dir()          # ★ 改装到别的目录也认：以自己的位置为准
    if not SILENT and not W.ask('要卸载 %s v%s 吗？\n\n安装位置：%s\n\n'
                               '（快捷方式、"应用和功能"里的条目会一起清掉）'
                               % (W.APP_TITLE, W.APP_VER, folder)):
        return
    W.kill_running()
    # ★ 先把活儿交给 %TEMP% 里的副本，自己立刻退出 —— 否则删不掉自己的 exe
    _relaunch_from_temp(folder)
    if not SILENT:
        W.info('%s 正在卸载，稍等几秒。\n\n（安装目录、快捷方式、"应用和功能"'
               '里的条目都会被清掉）' % W.APP_TITLE)


if __name__ == '__main__':
    main()
